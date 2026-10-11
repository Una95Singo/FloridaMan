import os, uuid
from datetime import timedelta

os.environ["FM_DEMO"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import pytest
import server.app as service
from server.domain import now, digest


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    service.engine = engine
    service.Factory = sessionmaker(engine, expire_on_commit=False)
    service.Base.metadata.create_all(engine)
    service.seed()
    with TestClient(service.app) as c:
        yield c
    engine.dispose()


def login(c):
    assert c.post("/auth/demo").status_code == 200
    return c.get("/api/session").json()["csrf"]


def case(c):
    return c.get("/api/cases").json()[0]


def act(c, csrf, action, packet=None, key=None, **kw):
    p = packet or case(c)
    return c.post(
        "/api/cases/demo-gulf/actions",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key or str(uuid.uuid4())},
        json={"action": action, "expected_digest": p["digest"], **kw},
    )


def test_private_and_public_boundary(client):
    assert client.get("/api/cases").status_code == 401
    public = client.get("/api/releases").json()
    assert len(public) == 1 and public[0]["packet"]["version"] == 1
    assert "approval" not in public[0]
    assert client.get("/api/cases/demo-gulf/audit").status_code == 401


def test_csrf_and_role_enforcement(client):
    token = login(client)
    assert act(client, "wrong", "approve", acknowledged=True).status_code == 403
    with service.Factory() as db:
        user = db.scalars(select(service.Login)).first()
        u = dict(user.data)
        u["roles"] = ["operator"]
        user.data = u
        db.commit()
    assert act(client, token, "approve", acknowledged=True).status_code == 403


def test_approval_is_not_publication(client):
    t = login(client)
    assert act(client, t, "approve", acknowledged=False).status_code == 409
    r = act(client, t, "approve", acknowledged=True)
    assert r.status_code == 200 and r.json()["state"] == "approved"
    assert len(client.get("/api/releases").json()) == 1


def test_correction_recheck_keeps_deadline_and_history(client):
    t = login(client)
    before = case(client)
    r = act(
        client,
        t,
        "correct",
        claim_id="C01",
        text="Do not imply insured exposure from this track.",
        reason="No exposure dataset supports this inference.",
    )
    assert r.status_code == 200 and r.json()["state"] == "revision_requested"
    assert act(client, t, "approve", acknowledged=True).status_code == 409
    replacement = act(client, t, "run").json()
    assert (
        replacement["packet"]["version"] == 3
        and replacement["deadline"] == before["deadline"]
    )
    assert replacement["packet"]["correction"]["claim_id"] == "C01"
    assert before["digest"] != replacement["digest"]
    assert (
        act(client, t, "approve", packet=before, acknowledged=True).status_code == 409
    )
    with service.Factory() as db:
        assert db.get(service.Record, "packet:" + before["digest"]) is not None


def test_challenge_validation(client):
    t = login(client)
    assert (
        act(
            client,
            t,
            "challenge",
            claim_id="missing",
            text="Question this interpretation.",
            reason="A different source may change it.",
        ).status_code
        == 422
    )
    assert (
        act(
            client,
            t,
            "challenge",
            claim_id="C01",
            text="Question this interpretation.",
            reason="A different source may change it.",
        ).json()["state"]
        == "revision_requested"
    )


def test_expired_deadline_holds_even_direct_api(client):
    t = login(client)
    with service.Factory() as db:
        r = db.get(service.Record, "case:demo-gulf")
        d = dict(r.data)
        d["deadline"] = (now() - timedelta(seconds=1)).isoformat()
        r.data = d
        db.commit()
    assert act(client, t, "approve", acknowledged=True).status_code == 409
    assert case(client)["state"] == "held"


def test_source_change_invalidates_approval(client):
    t = login(client)
    assert act(client, t, "approve", acknowledged=True).status_code == 200
    act(client, t, "simulate_source_change")
    assert act(client, t, "release").status_code == 409
    assert case(client)["state"] == "held"
    assert len(client.get("/api/releases").json()) == 1


def test_reopen_is_explicit(client):
    t = login(client)
    act(client, t, "simulate_source_change")
    act(client, t, "approve", acknowledged=True)
    assert act(client, t, "reopen", reason="short").status_code == 409
    r = act(
        client, t, "reopen", reason="Fresh evidence requires another review."
    ).json()
    assert r["cycle"] == 2 and r["state"] == "queued" and "previous_deadline" in r


def test_release_requires_current_approval_and_is_idempotent(client):
    t = login(client)
    assert act(client, t, "release").status_code == 409
    assert act(client, t, "approve", acknowledged=True).status_code == 200
    p = case(client)
    key = str(uuid.uuid4())
    a = act(client, t, "release", packet=p, key=key)
    b = act(client, t, "release", packet=p, key=key)
    assert a.status_code == 200 and a.json() == b.json()
    releases = client.get("/api/releases").json()
    assert len(releases) == 2
    r = client.get("/api/releases/" + a.json()["release_id"]).json()
    assert r["digest"] == digest(r["packet"]) == p["digest"]


def test_reused_key_cannot_change_request(client):
    t = login(client)
    p = case(client)
    key = str(uuid.uuid4())
    assert (
        act(client, t, "approve", packet=p, key=key, acknowledged=True).status_code
        == 200
    )
    assert act(client, t, "release", packet=p, key=key).status_code == 409


def test_memo_is_selectable_and_digest_bound(client):
    r = client.get("/api/releases").json()[0]
    md = client.get("/api/releases/" + r["id"] + "/memo.md")
    assert r["digest"] in md.text and "Financial impact" in md.text
    pdf = client.get("/api/releases/" + r["id"] + "/memo.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    import fitz

    doc = fitz.open(stream=pdf.content, filetype="pdf")
    text = "".join(p.get_text() for p in doc)
    assert "FloridaMan" in text and r["id"] in text


def test_audit_and_logout(client):
    t = login(client)
    act(client, t, "approve", acknowledged=True)
    audit = client.get("/api/cases/demo-gulf/audit").json()
    assert audit[0]["actor"] == "demo-reviewer"
    assert client.post("/auth/logout", headers={"X-CSRF-Token": t}).status_code == 200
    assert client.get("/api/cases").status_code == 401


def test_assigned_expert_is_enforced(client):
    token = login(client)
    original = case(client)
    with service.Factory() as db:
        row = db.get(service.Record, "case:demo-gulf")
        data = dict(row.data)
        data["assigned_expert"] = "another-expert"
        row.data = data
        user = db.scalars(select(service.Login)).first()
        data = dict(user.data)
        data["roles"] = ["expert"]
        user.data = data
        db.commit()
    assert client.get("/api/cases").json() == []
    assert client.get("/api/cases/demo-gulf/audit").status_code == 403
    assert (
        act(client, token, "approve", packet=original, acknowledged=True).status_code
        == 403
    )


def test_production_publication_fails_closed(client, monkeypatch):
    token = login(client)
    assert act(client, token, "approve", acknowledged=True).status_code == 200
    monkeypatch.setattr(service, "DEMO", False)
    assert act(client, token, "release").status_code == 503
    assert len(client.get("/api/releases").json()) == 1
    assert client.post("/auth/demo").status_code == 403


def test_recent_authentication_required(client):
    token = login(client)
    with service.Factory() as db:
        row = db.scalars(select(service.Login)).first()
        data = dict(row.data)
        data["created_at"] = (now() - timedelta(minutes=16)).isoformat()
        row.data = data
        db.commit()
    assert act(client, token, "approve", acknowledged=True).status_code == 401


def test_operation_lookup_recovers_a_completed_mutation(client):
    t = login(client)
    p = case(client)
    key = str(uuid.uuid4())
    # Unknown before the mutation completes; the client must not assume failure
    # or success from a timeout alone.
    assert client.get("/api/cases/demo-gulf/operations/" + key).status_code == 404
    first = act(client, t, "approve", packet=p, key=key, acknowledged=True)
    assert first.status_code == 200
    found = client.get("/api/cases/demo-gulf/operations/" + key)
    assert found.status_code == 200
    assert found.json()["status"] == "succeeded"
    assert found.json()["result"] == first.json()
    assert client.get("/api/cases/demo-gulf/operations/short").status_code == 422


def test_operation_lookup_is_private_and_scoped_to_the_actor(client):
    t = login(client)
    p = case(client)
    key = str(uuid.uuid4())
    assert act(client, t, "approve", packet=p, key=key, acknowledged=True).status_code == 200
    client.post("/auth/logout", headers={"X-CSRF-Token": t})
    assert client.get("/api/cases/demo-gulf/operations/" + key).status_code == 401
    # A different subject with the same key sees nothing.
    login(client)
    with service.Factory() as db:
        user = db.scalars(select(service.Login)).first()
        u = dict(user.data)
        u["sub"] = "someone-else"
        user.data = u
        db.commit()
    assert client.get("/api/cases/demo-gulf/operations/" + key).status_code == 404


def test_reopen_outside_demo_uses_the_review_window_rule(client, monkeypatch):
    from server.domain import review_deadline

    t = login(client)
    act(client, t, "simulate_source_change")
    act(client, t, "approve", acknowledged=True)
    assert act(client, t, "release").status_code == 409  # held: source changed
    monkeypatch.setattr(service, "DEMO", False)
    r = act(client, t, "reopen", reason="Fresh evidence requires another review.")
    assert r.status_code == 200
    data = r.json()
    expected = review_deadline(data["first_requested"])
    from datetime import datetime

    assert datetime.fromisoformat(data["deadline"]) == expected
    assert data["previous_deadline"] != data["deadline"]
