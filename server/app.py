"""Self-hosted FloridaMan API. Private records never enter a public response implicitly."""

import os, secrets, hashlib, json, io, hmac
from pathlib import Path
from datetime import timedelta, datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, RedirectResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import create_engine, String, Text, JSON, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from pydantic import BaseModel, Field, ConfigDict
from authlib.integrations.starlette_client import OAuth
from .domain import now, stamp, digest, fixture, qc, review_deadline

DEMO = os.getenv("FM_DEMO", "false").lower() == "true"
DB = os.getenv("DATABASE_URL", "sqlite:///./floridaman-v2.db")
SECRET = os.getenv("SESSION_SECRET")
if not SECRET:
    if not DEMO:
        raise RuntimeError("SESSION_SECRET is required outside isolated demo mode")
    SECRET = secrets.token_hex(32)
if not DEMO and len(SECRET) < 32:
    raise RuntimeError("Use a session secret of at least 32 characters")
engine = create_engine(
    DB, connect_args={"check_same_thread": False} if DB.startswith("sqlite") else {}
)
Factory = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "records"
    key: Mapped[str] = mapped_column(String(180), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    data: Mapped[dict] = mapped_column(JSON)


class Login(Base):
    __tablename__ = "sessions"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


Base.metadata.create_all(engine)


def getdb():
    with Factory() as db:
        yield db


def put(db, key, kind, data):
    row = db.get(Record, key)
    if row:
        row.data = data
    else:
        db.add(Record(key=key, kind=kind, data=data))
    return data


def audit(db, actor, action, case, detail):
    ident = secrets.token_hex(12)
    put(
        db,
        "audit:" + ident,
        "audit",
        {
            "id": ident,
            "actor": actor,
            "action": action,
            "case_id": case,
            "detail": detail,
            "at": stamp(),
        },
    )


def save_packet(db, p):
    dg = digest(p)
    key = "packet:" + dg
    if not db.get(Record, key):
        put(db, key, "packet", p)
    return dg


def seed():
    if not DEMO:
        return
    with Factory() as db:
        if db.get(Record, "case:demo-gulf"):
            return
        p = fixture()
        dg = save_packet(db, p)
        put(
            db,
            "source:demo-gulf",
            "source",
            {"version": p["source_version"], "verified_at": stamp()},
        )
        put(
            db,
            "case:demo-gulf",
            "case",
            {
                "id": "demo-gulf",
                "digest": dg,
                "state": "review_pending",
                "deadline": (now() + timedelta(hours=2)).isoformat(),
                "first_requested": stamp(),
                "cycle": 1,
                "qc": qc(p),
                "approval": None,
                "release_id": None,
            },
        )
        # Public fixture is a separate, explicitly synthetic immutable release.
        public = fixture(1)
        public["title"] = "A watch worth keeping."
        public["summary"] = "Follow a synthetic storm from forecast to expert judgment."
        pd = save_packet(db, public)
        put(
            db,
            "release:demo-release-1",
            "release",
            {
                "id": "demo-release-1",
                "digest": pd,
                "packet": public,
                "published_at": stamp(),
                "reviewer": "Synthetic fixture",
                "status": "published",
                "mode": "demo",
            },
        )
        db.commit()


seed()
app = FastAPI(title="FloridaMan", version="2.1.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET,
    session_cookie="fm_oidc",
    https_only=not DEMO,
    same_site="lax",
)
oauth = OAuth()
if os.getenv("OIDC_ISSUER"):
    oauth.register(
        name="identity",
        client_id=os.environ["OIDC_CLIENT_ID"],
        client_secret=os.environ["OIDC_CLIENT_SECRET"],
        server_metadata_url=os.environ["OIDC_ISSUER"].rstrip("/")
        + "/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid profile email",
            "code_challenge_method": "S256",
        },
    )


@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if request.url.path.startswith(
        ("/api/session", "/api/cases", "/api/operations", "/auth")
    ):
        response.headers["Cache-Control"] = "no-store"
    return response


def session_user(request: Request, db: Session):
    sid = request.cookies.get("fm_session", "")
    row = db.get(Login, hashlib.sha256(sid.encode()).hexdigest()) if sid else None
    if not row or datetime.fromisoformat(row.data["expires"]) < now():
        raise HTTPException(401, "Sign in to open the private review.")
    if datetime.fromisoformat(row.data["last_seen"]) + timedelta(minutes=30) < now():
        raise HTTPException(401, "Your session expired. Sign in again.")
    data = dict(row.data)
    data["last_seen"] = stamp()
    row.data = data
    db.commit()
    return data


def require(request, db, role=None, mutation=False):
    u = session_user(request, db)
    if role and role not in u["roles"]:
        raise HTTPException(403, "This action requires " + role + " permission.")
    if mutation:
        if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), u["csrf"]):
            raise HTTPException(403, "Invalid request token.")
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "Invalid request origin.")
    return u


def start_session(db, subject, name, roles):
    sid = secrets.token_urlsafe(48)
    db.add(
        Login(
            key=hashlib.sha256(sid.encode()).hexdigest(),
            data={
                "sub": subject,
                "name": name,
                "roles": roles,
                "csrf": secrets.token_urlsafe(32),
                "created_at": stamp(),
                "last_seen": stamp(),
                "expires": (now() + timedelta(hours=12)).isoformat(),
            },
        )
    )
    db.commit()
    return sid


@app.get("/api/session")
def session(request: Request, db=Depends(getdb)):
    try:
        u = session_user(request, db)
        return {
            "authenticated": True,
            "name": u["name"],
            "roles": u["roles"],
            "csrf": u["csrf"],
            "demo": DEMO,
        }
    except HTTPException:
        return {
            "authenticated": False,
            "demo": DEMO,
            "oidc_available": bool(os.getenv("OIDC_ISSUER")),
        }


@app.post("/auth/demo")
def demo_login(request: Request, db=Depends(getdb)):
    # Demo identity is only available when explicitly enabled on loopback.
    if not DEMO or request.client.host not in ["127.0.0.1", "::1", "testclient"]:
        raise HTTPException(403, "Demo sign-in is disabled.")
    if request.headers.get("origin") and request.headers["origin"].rstrip("/") != str(
        request.base_url
    ).rstrip("/"):
        raise HTTPException(403, "Invalid origin")
    sid = start_session(db, "demo-reviewer", "Demo reviewer", ["expert", "operator"])
    response = JSONResponse({"ok": True, "mode": "isolated demo"})
    response.set_cookie(
        "fm_session", sid, httponly=True, secure=False, samesite="strict", max_age=43200
    )
    return response


@app.get("/auth/login")
async def login(request: Request):
    if not os.getenv("OIDC_ISSUER"):
        raise HTTPException(503, "Identity provider is not configured.")
    return await oauth.identity.authorize_redirect(
        request, str(request.url_for("callback")), prompt="login", max_age=900
    )


@app.get("/auth/callback", name="callback")
async def callback(request: Request, db=Depends(getdb)):
    token = await oauth.identity.authorize_access_token(request)
    info = token.get("userinfo")
    if not info:
        raise HTTPException(401, "Identity verification failed.")
    if str(info.get("acr", "")) != "2":
        raise HTTPException(403, "Multi-factor authentication is required.")
    # Configure a Keycloak mapper for this dedicated claim; never trust browser-supplied roles.
    roles = [r for r in info.get("fm_roles", []) if r in ["expert", "operator"]]
    if not roles:
        raise HTTPException(403, "No FloridaMan role is assigned.")
    sid = start_session(db, info["sub"], info.get("name", "Reviewer"), roles)
    request.session.clear()
    response = RedirectResponse("/?view=reviews")
    response.set_cookie(
        "fm_session", sid, httponly=True, secure=True, samesite="lax", max_age=43200
    )
    return response


@app.post("/auth/logout")
def logout(request: Request, db=Depends(getdb)):
    require(request, db, mutation=True)
    sid = request.cookies.get("fm_session", "")
    row = db.get(Login, hashlib.sha256(sid.encode()).hexdigest())
    if row:
        db.delete(row)
        db.commit()
    r = JSONResponse({"ok": True})
    r.delete_cookie("fm_session")
    return r


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "demo" if DEMO else "operated", "version": "2.1.0"}


@app.get("/api/releases")
def releases(db=Depends(getdb)):
    return [
        r.data
        for r in db.scalars(select(Record).where(Record.kind == "release")).all()
        if r.data["status"] in ["published", "withdrawn"]
    ]


@app.get("/api/releases/{id}")
def release(id: str, db=Depends(getdb)):
    r = db.get(Record, "release:" + id)
    if not r or r.data["status"] not in ["published", "withdrawn"]:
        raise HTTPException(404, "Release unavailable")
    return r.data


@app.get("/api/cases")
def cases(request: Request, db=Depends(getdb)):
    u = require(request, db)
    result = []
    for r in db.scalars(select(Record).where(Record.kind == "case")).all():
        c = dict(r.data)
        if (
            c.get("assigned_expert")
            and c["assigned_expert"] != u["sub"]
            and "operator" not in u["roles"]
        ):
            continue
        if (
            c["state"] in ["review_pending", "approved"]
            and datetime.fromisoformat(c["deadline"]) <= now()
        ):
            c["state"] = "held"
            c["hold_reason"] = "Review overdue"
            r.data = c
        p = db.get(Record, "packet:" + c["digest"]).data
        result.append({**c, "packet": p})
    db.commit()
    return result


@app.get("/api/cases/{id}/audit")
def history(id: str, request: Request, db=Depends(getdb)):
    u = require(request, db)
    case = db.get(Record, "case:" + id)
    if not case:
        raise HTTPException(404, "Case unavailable")
    if (
        case.data.get("assigned_expert")
        and case.data["assigned_expert"] != u["sub"]
        and "operator" not in u["roles"]
    ):
        raise HTTPException(403, "This case is assigned to another expert.")
    return sorted(
        [
            r.data
            for r in db.scalars(select(Record).where(Record.kind == "audit")).all()
            if r.data["case_id"] == id
        ],
        key=lambda a: a["at"],
    )


@app.get("/api/cases/{id}/operations/{key}")
def operation(id: str, key: str, request: Request, db=Depends(getdb)):
    """Recover the outcome of a mutation after a network timeout.

    A timeout does not imply failure. The client asks for its own
    idempotency key before retrying; a saved result is returned unchanged.
    The lookup is scoped to the signed-in subject, so one reviewer cannot read
    another reviewer's operations by guessing a key.
    """
    u = require(request, db)
    if not 8 <= len(key) <= 128:
        raise HTTPException(422, "An idempotency key is required.")
    op = db.get(Record, "op:" + digest([u["sub"], id, key]))
    if not op:
        raise HTTPException(404, "No completed operation has this key.")
    return {"status": "succeeded", "result": op.data["result"]}


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    expected_digest: str
    acknowledged: bool = False
    claim_id: str | None = None
    text: str = Field(default="", max_length=2000)
    reason: str = Field(default="", max_length=2000)


@app.post("/api/cases/{id}/actions")
def act(id: str, body: Action, request: Request, db=Depends(getdb)):
    role = (
        "operator"
        if body.action in ["run", "release", "reopen", "simulate_source_change"]
        else "expert"
    )
    u = require(request, db, role, True)
    key = request.headers.get("Idempotency-Key", "")
    if not 8 <= len(key) <= 128:
        raise HTTPException(422, "An idempotency key is required.")
    opkey = "op:" + digest([u["sub"], id, key])
    op = db.get(Record, opkey)
    if op:
        if op.data["request_digest"] != digest(body.model_dump()):
            raise HTTPException(
                409, "This request key was already used for different content."
            )
        return op.data["result"]
    row = db.scalar(select(Record).where(Record.key == "case:" + id).with_for_update())
    if not row:
        raise HTTPException(404, "Case unavailable")
    # Recheck after the case lock: concurrent retries may have completed while waiting.
    op = db.get(Record, opkey)
    if op:
        if op.data["request_digest"] != digest(body.model_dump()):
            raise HTTPException(
                409, "This request key was already used for different content."
            )
        return op.data["result"]
    c = dict(row.data)
    p = db.get(Record, "packet:" + c["digest"]).data
    if (
        role == "expert"
        and c.get("assigned_expert")
        and c["assigned_expert"] != u["sub"]
    ):
        raise HTTPException(403, "This case is assigned to another expert.")
    if body.expected_digest != c["digest"]:
        raise HTTPException(409, "This version changed. Review the new version.")
    if body.action in ["approve", "release"]:
        if datetime.fromisoformat(u["created_at"]) + timedelta(minutes=15) < now():
            raise HTTPException(401, "Sign in again before approving or releasing.")
        source = db.get(Record, "source:" + id)
        if (
            datetime.fromisoformat(c["deadline"]) <= now()
            or not source
            or source.data["version"] != p["source_version"]
        ):
            c["state"] = "held"
            c["hold_reason"] = (
                "Review overdue"
                if datetime.fromisoformat(c["deadline"]) <= now()
                else "Source changed or unavailable"
            )
            row.data = c
            audit(db, u["sub"], "held", id, c["hold_reason"])
            db.commit()
            raise HTTPException(409, c["hold_reason"])
        if c["qc"]["verdict"] != "PASS" or c["qc"]["input_digest"] != c["digest"]:
            raise HTTPException(409, "This packet has not passed its required checks.")
    if body.action in ["correct", "challenge"]:
        if c["state"] not in ["review_pending", "held"]:
            raise HTTPException(409, "This version is no longer open for a response.")
        if len(body.text.strip()) < 10 or len(body.reason.strip()) < 10:
            raise HTTPException(
                422, "Explain the change and the reason (at least 10 characters each)."
            )
        if body.claim_id not in {x["id"] for x in p["claims"]}:
            raise HTTPException(422, "Choose a claim in this version.")
        c["correction"] = {
            "claim_id": body.claim_id,
            "text": body.text,
            "reason": body.reason,
            "actor": u["sub"],
            "at": stamp(),
            "action": body.action,
        }
        c["approval"] = None
        if c["state"] != "held":
            c["state"] = "revision_requested"
    elif body.action == "run":
        if c["state"] not in ["revision_requested", "queued", "blocked"]:
            raise HTTPException(409, "No replacement run is requested.")
        if not DEMO:
            raise HTTPException(
                503,
                "Live model execution is not configured. No analysis was generated.",
            )
        p = fixture(p["version"] + 1, c.get("correction"))
        p["source_version"] = db.get(Record, "source:" + id).data["version"]
        c["digest"] = save_packet(db, p)
        c["qc"] = qc(p)
        c["state"] = "review_pending" if c["qc"]["verdict"] == "PASS" else "blocked"
        c["approval"] = None
        c["run_authorization"] = {
            "actor": u["sub"],
            "at": stamp(),
            "mode": "synthetic replay",
        }
    elif body.action == "approve":
        if c["state"] != "review_pending" or not body.acknowledged:
            raise HTTPException(
                409, "Review and acknowledge the current pending version."
            )
        c["approval"] = {
            "actor": u["sub"],
            "name": u["name"],
            "digest": c["digest"],
            "at": stamp(),
        }
        c["state"] = "approved"
    elif body.action == "release":
        if (
            c["state"] != "approved"
            or not c.get("approval")
            or c["approval"]["digest"] != c["digest"]
        ):
            raise HTTPException(
                409, "Expert approval for this exact version is required."
            )
        if not DEMO:
            raise HTTPException(
                503,
                "Production publication is disabled until source verification and the public mirror are configured.",
            )
        rid = "release-" + c["digest"][:16]
        put(
            db,
            "release:" + rid,
            "release",
            {
                "id": rid,
                "digest": c["digest"],
                "packet": p,
                "published_at": stamp(),
                "reviewer": "Demo reviewer",
                "status": "published",
                "mode": "demo",
            },
        )
        c["state"] = "published"
        c["release_id"] = rid
    elif body.action == "reopen":
        if c["state"] != "held" or len(body.reason.strip()) < 10:
            raise HTTPException(409, "A held case and an explicit reason are required.")
        c["previous_deadline"] = c["deadline"]
        requested = now()
        c["first_requested"] = requested.isoformat()
        c["deadline"] = (
            (requested + timedelta(hours=2)).isoformat()
            if DEMO
            else review_deadline(requested, p.get("decision_horizon")).isoformat()
        )
        c["cycle"] += 1
        c["state"] = "queued"
        c["approval"] = None
    elif body.action == "simulate_source_change" and DEMO:
        s = db.get(Record, "source:" + id)
        s.data = {
            "version": "demo-advisory-" + secrets.token_hex(3),
            "verified_at": stamp(),
        }
    else:
        raise HTTPException(422, "Unknown action")
    row.data = c
    audit(
        db,
        u["sub"],
        body.action,
        id,
        {"digest": c["digest"], "state": c["state"], "reason": body.reason},
    )
    result = {**c, "packet": p}
    put(
        db,
        opkey,
        "operation",
        {"request_digest": digest(body.model_dump()), "result": result},
    )
    db.commit()
    return result


@app.get("/api/releases/{id}/memo.md")
def memo_md(id: str, db=Depends(getdb)):
    r = release(id, db)
    return Response(
        memo_text(r),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="FloridaMan-{id}.md"'},
    )


def memo_text(r):
    p = r["packet"]
    sections = [
        ("Decision needed", p["decision"]),
        (
            "Current view",
            p["conclusion"]
            + " Confidence: "
            + p["confidence"]
            + ". "
            + p["confidence_reason"],
        ),
        ("What changed", p["change"]),
        ("Why it matters", p["summary"]),
        (
            "Evidence and assumptions",
            p["method"]
            + "\n"
            + "\n".join(
                s["id"] + ": " + s["title"] + " (" + s["version"] + "). " + s["excerpt"]
                for s in p["sources"]
            ),
        ),
        ("What remains unknown", "; ".join(p["unknowns"])),
        (
            "What would change this view",
            "\n".join(
                x["text"] + " Review by " + x["deadline"] for x in p["conditions"]
            ),
        ),
        (
            "Review and version",
            r["reviewer"]
            + " | "
            + r["published_at"]
            + " | Version "
            + str(p["version"])
            + "\nRelease "
            + r["id"]
            + "\nSHA-256 "
            + r["digest"],
        ),
    ]
    return (
        "# FloridaMan\n\n"
        + (
            "SYNTHETIC DEMONSTRATION — not live analysis\n\n"
            if p["mode"] == "demo"
            else ""
        )
        + "# "
        + p["title"]
        + "\n\n"
        + "\n\n".join(
            "## " + str(i + 1) + ". " + title + "\n" + body
            for i, (title, body) in enumerate(sections)
        )
    )


@app.get("/api/releases/{id}/memo.pdf")
def memo_pdf(id: str, db=Depends(getdb)):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_LEFT
    from xml.sax.saxutils import escape

    r = release(id, db)
    out = io.BytesIO()
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "Helvetica"
    styles["Normal"].fontSize = 10
    styles["Normal"].leading = 15
    styles["Title"].fontName = "Times-Roman"
    styles["Title"].alignment = TA_LEFT
    styles["Heading2"].textColor = HexColor("#096779")
    flow = []
    for block in memo_text(r).split("\n\n"):
        sty = (
            styles["Heading2"]
            if block.startswith("## ")
            else styles["Title"] if block.startswith("# ") else styles["Normal"]
        )
        flow.extend(
            [
                Paragraph(escape(block.lstrip("# ")).replace("\n", "<br/>"), sty),
                Spacer(1, 10),
            ]
        )

    def footer(c, doc):
        c.setFont("Helvetica", 8)
        c.drawString(42, 25, "FloridaMan | " + r["id"])
        c.drawRightString(553, 25, str(doc.page))

    SimpleDocTemplate(
        out,
        rightMargin=42,
        leftMargin=42,
        topMargin=44,
        bottomMargin=42,
        title="FloridaMan review memo",
    ).build(flow, onFirstPage=footer, onLaterPages=footer)
    return Response(
        out.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="FloridaMan-{id}.pdf"'},
    )


WEB = Path(__file__).resolve().parent.parent / "web" / "dist"
if WEB.exists():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")
    app.mount("/geo", StaticFiles(directory=WEB / "geo"), name="geo")

    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")
