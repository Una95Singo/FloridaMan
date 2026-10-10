import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowLeft,
  ArrowRight,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  Check,
  CheckCircle2,
  Clock3,
  FileText,
  Compass,
  BookOpen,
  Layers,
  Download,
  LogOut,
  ShieldCheck,
  Info,
  Search,
  X,
  RefreshCw,
  ExternalLink,
} from "lucide-react";
import "@fontsource/source-serif-4/400.css";
import "@fontsource/source-serif-4/500.css";
import "@fontsource/source-sans-3/400.css";
import "@fontsource/source-sans-3/500.css";
import "@fontsource/source-sans-3/600.css";
import StormMap from "./StormMap";
import "./style.css";
async function api(path, options = {}) {
  const r = await fetch("/api" + path, options);
  if (!r.ok) {
    let b;
    try {
      b = await r.json();
    } catch {}
    throw Error(
      typeof b?.detail === "string"
        ? b.detail
        : "The request could not be completed. Please retry.",
    );
  }
  return r.json();
}
const date = (s) =>
  new Date(s).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
const states = {
  review_pending: "Awaiting your review",
  revision_requested: "New analysis requested",
  approved: "Approved · awaiting release",
  published: "Released",
  held: "Publication on hold",
  queued: "Awaiting an authorized run",
  blocked: "Checks blocked",
};
function App() {
  const [session, setSession] = useState(null),
    [releases, setReleases] = useState([]),
    [cases, setCases] = useState([]),
    [view, setView] = useState(
      new URLSearchParams(location.search).get("view") || "watch",
    ),
    [expanded, setExpanded] = useState(false),
    [selected, setSelected] = useState(null),
    [claim, setClaim] = useState("C01"),
    [sourceTab, setSourceTab] = useState("change"),
    [responseType, setResponseType] = useState("correct"),
    [text, setText] = useState(""),
    [reason, setReason] = useState(""),
    [ack, setAck] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [audit, setAudit] = useState([]),
    [memo, setMemo] = useState("");
  const current = cases[0];
  const publicRelease =
    releases.find((r) => r.id === selected) || releases.at(-1);
  const p =
    session?.authenticated &&
    current &&
    view !== "archive" &&
    view !== "memo" &&
    !selected
      ? current.packet
      : publicRelease?.packet;
  async function refresh() {
    const s = await api("/session");
    setSession(s);
    setReleases(await api("/releases"));
    if (s.authenticated) setCases(await api("/cases"));
    else setCases([]);
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    const pop = () => {
      setView(new URLSearchParams(location.search).get("view") || "watch");
      setExpanded(false);
    };
    addEventListener("popstate", pop);
    return () => removeEventListener("popstate", pop);
  }, []);
  function go(v) {
    setView(v);
    setError("");
    setNotice("");
    setAck(false);
    history.pushState({}, "", v === "watch" ? "/" : "/?view=" + v);
    setTimeout(() => document.querySelector(".panel-title")?.focus(), 0);
  }
  async function signIn() {
    setBusy(true);
    setError("");
    try {
      if (session?.demo) {
        const r = await fetch("/auth/demo", { method: "POST" });
        if (!r.ok)
          throw Error(
            "Demo sign-in is available only on the local test server.",
          );
        await refresh();
        setSelected(null);
        go("reviews");
      } else location.href = "/auth/login";
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function action(type, extra = {}) {
    setBusy(true);
    setError("");
    try {
      const result = await api("/cases/" + current.id + "/actions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": session.csrf,
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          action: type,
          expected_digest: current.digest,
          ...extra,
        }),
      });
      setCases([result]);
      setSelected(null);
      await refresh();
      go(type === "release" ? "archive" : "reviews");
      setNotice(
        type === "approve"
          ? "Approved. Waiting for operator release."
          : type === "release"
            ? "The synthetic release and its memo are now available."
            : type === "run"
              ? "The replacement packet passed checks. A new review is required."
              : "Your decision was saved. Nothing was published.",
      );
      setText("");
      setReason("");
    } catch (e) {
      setError(e.message);
      await refresh();
    } finally {
      setBusy(false);
    }
  }
  async function openAudit() {
    try {
      setAudit(await api("/cases/" + current.id + "/audit"));
      go("audit");
    } catch (e) {
      setError(e.message);
    }
  }
  async function openMemo(r) {
    setSelected(r.id);
    go("memo");
    setMemo("");
    try {
      const res = await fetch("/api/releases/" + r.id + "/memo.md");
      if (!res.ok) throw Error("Memo unavailable");
      setMemo(await res.text());
    } catch (e) {
      setError(e.message);
    }
  }
  const renderNav = (mobile = false) => (
    <nav
      className={mobile ? "mobile-nav" : "desktop-nav"}
      aria-label={mobile ? "Mobile navigation" : "Main navigation"}
    >
      {[
        ["watch", "Watch", Compass],
        ["reviews", "Reviews", FileText],
        ["archive", "Archive", BookOpen],
      ].map(([id, label, Icon]) => (
        <button
          key={id}
          className={view === id ? "active" : ""}
          onClick={() => {
            setSelected(null);
            go(id);
          }}
        >
          <Icon size={19} />
          <span>{label}</span>
          {id === "reviews" && current?.state === "review_pending" && <i />}
        </button>
      ))}
    </nav>
  );
  const tag = (
    <span className={"pill " + (current?.state === "held" ? "amber" : "")}>
      {current?.state === "approved" ? (
        <CheckCircle2 size={13} />
      ) : (
        <Clock3 size={13} />
      )}{" "}
      {states[current?.state] || "Illustrative approved release"}
    </span>
  );
  const contractRows = () =>
    p.bonds.map((b) => (
      <button
        className="contract-row"
        key={b.id}
        onClick={() => {
          setClaim("C02");
          go("contract");
        }}
      >
        <span>
          <strong>{b.name}</strong>
          <small>
            {p.mode === "demo" ? "Illustrative contract" : "Contract"} ·{" "}
            {b.trigger}
          </small>
        </span>
        <ChevronRight size={17} />
      </button>
    ));
  if (!session || !p)
    return (
      <div className="boot">
        <div className="brand">FloridaMan</div>
        <p>
          {error ||
            (!session
              ? "Opening the watch…"
              : "No approved release is available yet.")}
        </p>
        {session && !session.authenticated && (
          <button onClick={signIn}>Expert sign in</button>
        )}
        {session?.authenticated && <p>No cases await your review.</p>}
        {error && <button onClick={() => location.reload()}>Try again</button>}
      </div>
    );
  return (
    <>
      <div className="environment">
        <span className="status-dot" />{" "}
        {session.demo ? "Synthetic demonstration" : "Operated workspace"}
        <span className="env-detail">
          {session.demo
            ? "Real workflow · illustrative storm and contracts"
            : "Expert judgment before publication"}
        </span>
      </div>
      <header className="app-header">
        <button
          className="brand"
          onClick={() => {
            setSelected(null);
            go("watch");
          }}
        >
          FloridaMan<span className="brand-period">.</span>
        </button>
        {renderNav()}
        <div className="account">
          {session.authenticated ? (
            <>
              <span className="account-name">{session.name}</span>
              <button
                className="avatar"
                aria-label="Sign out"
                onClick={async () => {
                  await fetch("/auth/logout", {
                    method: "POST",
                    headers: { "X-CSRF-Token": session.csrf },
                  });
                  await refresh();
                  go("watch");
                }}
              >
                <LogOut size={17} />
              </button>
            </>
          ) : (
            <button className="signin" onClick={signIn} disabled={busy}>
              {session.demo ? "Open demo workspace" : "Expert sign in"}
              <ArrowRight size={15} />
            </button>
          )}
        </div>
      </header>
      <main
        className={
          "workspace " + (expanded ? "expanded " : "") + "view-" + view
        }
      >
        <section className="geography">
          <StormMap packet={p} />
        </section>
        <section
          className={
            "reading-panel " + (view === "watch" ? "watch-panel" : "full-panel")
          }
          aria-label="Analysis and review"
        >
          {view === "watch" && (
            <button
              className="sheet-handle"
              aria-label={expanded ? "Collapse analysis" : "Expand analysis"}
              onClick={() => setExpanded(!expanded)}
            >
              <span />
              {expanded ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
            </button>
          )}
          <div className="panel-scroll">
            {error && (
              <div className="feedback error" role="alert">
                <Info size={18} />
                <span>{error}</span>
                <button aria-label="Dismiss error" onClick={() => setError("")}>
                  <X size={16} />
                </button>
              </div>
            )}
            {notice && (
              <div className="feedback success" role="status">
                <CheckCircle2 size={18} />
                {notice}
              </div>
            )}
            {view === "watch" && (
              <>
                <div className="desktop-only">{tag}</div>
                <p className="eyebrow">The current view</p>
                <h2 tabIndex="-1" className="panel-title">
                  {p.mode === "demo" ? (
                    <>
                      The track moved. <br />
                      Has the risk?
                    </>
                  ) : (
                    p.title
                  )}
                </h2>
                <p className="lede">
                  {p.mode === "demo"
                    ? "Two watched contracts need a closer look."
                    : p.summary}
                </p>
                <div className="quiet-line">
                  <i />
                  Indicative · Exposure uncertain
                </div>
                <div className="expand-content">
                  <section className="section">
                    <h3>What changed</h3>
                    <p>{p.change}</p>
                    <button
                      className="inline-link"
                      onClick={() => {
                        setClaim("C01");
                        go("evidence");
                      }}
                    >
                      Compare the advisories
                      <ArrowRight size={15} />
                    </button>
                  </section>
                  <section className="section">
                    <h3>What remains unknown</h3>
                    <p className="muted">
                      Insured exposure and prior eligible losses.
                    </p>
                  </section>
                  <div className="contracts">{contractRows()}</div>
                </div>
                <button
                  className="primary watch-action"
                  onClick={() => {
                    if (window.innerWidth < 768 && !expanded) setExpanded(true);
                    else {
                      setClaim("C01");
                      go("evidence");
                    }
                  }}
                >
                  {expanded ? "Inspect evidence" : "Review analysis"}
                  <ArrowRight size={17} />
                </button>
                <div className="panel-footer desktop-only">
                  <span>{p.sources[0]?.title}</span>
                  <span>{date(p.as_of)}</span>
                </div>
              </>
            )}
            {view === "evidence" && (
              <>
                <button className="back" onClick={() => go("watch")}>
                  <ArrowLeft size={17} />
                  Back to the watch
                </button>
                <p className="eyebrow">Trace the claim</p>
                <h2 className="panel-title" tabIndex="-1">
                  What supports
                  <br />
                  this view?
                </h2>
                <div className="claim-quote">
                  “{p.claims.find((c) => c.id === claim)?.text}”
                </div>
                <div className="source-row">
                  <FileText size={23} />
                  <span>
                    <strong>
                      {
                        p.sources.find(
                          (s) =>
                            s.id ===
                            p.claims.find((c) => c.id === claim)?.source_id,
                        )?.title
                      }
                    </strong>
                    <small>
                      {p.mode === "demo"
                        ? "Illustrative source"
                        : "Pinned source"}{" "}
                      · {date(p.as_of)}
                    </small>
                  </span>
                  <ShieldCheck size={17} />
                </div>
                <div
                  className="segments"
                  role="tablist"
                  aria-label="Evidence details"
                >
                  {["change", "source"].map((t) => (
                    <button
                      key={t}
                      role="tab"
                      aria-selected={sourceTab === t}
                      onClick={() => setSourceTab(t)}
                    >
                      {t === "change" ? "Change" : "Source"}
                    </button>
                  ))}
                </div>
                {sourceTab === "change" ? (
                  <div className="comparison">
                    <div>
                      <span>Previous</span>
                      <p>{p.claims.find((c) => c.id === claim)?.previous}</p>
                    </div>
                    <div>
                      <span>Latest</span>
                      <p>{p.claims.find((c) => c.id === claim)?.current}</p>
                    </div>
                  </div>
                ) : (
                  <section className="section source-detail">
                    {(() => {
                      const s = p.sources.find(
                        (s) =>
                          s.id ===
                          p.claims.find((c) => c.id === claim)?.source_id,
                      );
                      return (
                        <>
                          <p>{s.excerpt}</p>
                          {s.url && /^https?:\/\//.test(s.url) && (
                            <a
                              href={s.url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              Open original source
                            </a>
                          )}
                          <dl>
                            <dt>Source version</dt>
                            <dd>{s.version}</dd>
                            <dt>Issued</dt>
                            <dd>{date(s.issued_at)}</dd>
                            <dt>Retrieved</dt>
                            <dd>{date(s.retrieved_at)}</dd>
                            <dt>Reuse basis</dt>
                            <dd>{s.rights}</dd>
                          </dl>
                        </>
                      );
                    })()}
                  </section>
                )}
                <div className="caution">
                  <Info size={17} />
                  <p>{p.claims.find((c) => c.id === claim)?.limitation}</p>
                </div>
                <button
                  className="primary"
                  onClick={() =>
                    session.authenticated ? go("reviews") : signIn()
                  }
                >
                  {session.authenticated
                    ? "Open expert review"
                    : session.demo
                      ? "Open demo review"
                      : "Sign in to review"}
                  <ArrowRight size={16} />
                </button>
              </>
            )}
            {view === "contract" && (
              <>
                <button className="back" onClick={() => go("watch")}>
                  <ArrowLeft size={17} />
                  Back to the watch
                </button>
                <p className="eyebrow">Contract investigation</p>
                <h2 className="panel-title" tabIndex="-1">
                  What could change
                  <br />
                  the assessment?
                </h2>
                <div className="contracts">
                  {p.bonds.map((b) => (
                    <div key={b.id} className="contract-detail">
                      <h3>{b.name}</h3>
                      <p className="muted">{b.trigger}</p>
                      <dl>
                        <dt>Attachment</dt>
                        <dd>Not available</dd>
                        <dt>Prior eligible losses</dt>
                        <dd>Unknown</dd>
                        <dt>Insured exposure</dt>
                        <dd>Not available</dd>
                      </dl>
                    </div>
                  ))}
                </div>
                <div className="caution">
                  <Info size={18} />
                  <p>
                    Unknown losses cannot be placed on a numeric scale. No
                    payout estimate is supported.
                  </p>
                </div>
                <button
                  className="primary"
                  onClick={() => {
                    setClaim("C02");
                    go("evidence");
                  }}
                >
                  Inspect the evidence
                  <ArrowRight size={17} />
                </button>
              </>
            )}
            {view === "reviews" &&
              (!session.authenticated || !current ? (
                <>
                  <p className="eyebrow">Expert workspace</p>
                  <h2 className="panel-title" tabIndex="-1">
                    Your judgment.
                    <br />A clear next step.
                  </h2>
                  <p className="lede">Private analysis stays behind sign-in.</p>
                  <p className="muted">
                    {session.demo
                      ? "Open the isolated demo to review evidence, record a correction and release a synthetic memo."
                      : "Sign in to see the cases assigned to you."}
                  </p>
                  <button className="primary" disabled={busy} onClick={signIn}>
                    {session.demo ? "Open demo workspace" : "Sign in"}
                    <ArrowRight size={17} />
                  </button>
                </>
              ) : (
                <>
                  {tag}
                  <p className="eyebrow">Expert workspace</p>
                  <h2 className="panel-title" tabIndex="-1">
                    {current?.state === "held"
                      ? "A fresh view is needed."
                      : current?.state === "approved"
                        ? "Judgment recorded."
                        : current?.state === "revision_requested"
                          ? "The correction stays."
                          : "Ready for your judgment."}
                  </h2>
                  <p className="lede">{current?.packet.conclusion}</p>
                  <div className="section">
                    <h3>What remains unknown</h3>
                    {p.unknowns.map((u) => (
                      <div className="unknown-row" key={u}>
                        <span>?</span>
                        {u}
                      </div>
                    ))}
                  </div>
                  <div className="version-line">
                    <FileText size={18} />
                    <div>
                      Version {p.version} · Sources pinned
                      <small>
                        Review by {date(current?.deadline)}
                        <br />
                        {new Date(current?.deadline)
                          .toISOString()
                          .slice(11, 16)}{" "}
                        UTC
                      </small>
                    </div>
                  </div>
                  {current?.packet.correction && (
                    <div className="correction-note">
                      <b>Expert response retained</b>
                      <p>{current.packet.correction.text}</p>
                      <small>
                        Synthetic replay: retained for judgment; no model
                        interpretation claimed.
                      </small>
                    </div>
                  )}
                  {current?.state === "review_pending" && (
                    <>
                      <button className="primary" onClick={() => go("approve")}>
                        Review this version
                        <ArrowRight size={17} />
                      </button>
                      <div className="secondary-actions">
                        <button
                          onClick={() => {
                            setResponseType("correct");
                            go("respond");
                          }}
                        >
                          Correct
                        </button>
                        <button
                          onClick={() => {
                            setResponseType("challenge");
                            go("respond");
                          }}
                        >
                          Challenge
                        </button>
                      </div>
                    </>
                  )}
                  {["revision_requested", "queued", "blocked"].includes(
                    current?.state,
                  ) && (
                    <>
                      <p className="muted">
                        An operator must authorize the replacement. The original
                        deadline is retained.
                      </p>
                      <button
                        className="primary"
                        disabled={busy}
                        onClick={() => action("run")}
                      >
                        {busy ? "Running…" : "Authorize replay & recheck"}
                        <RefreshCw size={17} />
                      </button>
                    </>
                  )}
                  {current?.state === "approved" && (
                    <>
                      <p className="muted">
                        Nothing has been published. The operator releases this
                        exact version after final checks.
                      </p>
                      <button
                        className="primary"
                        onClick={() => go("release-confirm")}
                      >
                        Review operator release
                        <ArrowRight size={17} />
                      </button>
                    </>
                  )}
                  {current?.state === "held" && (
                    <>
                      <div className="caution">
                        <Clock3 size={17} />
                        <p>
                          {current.hold_reason || "Review overdue"}. Approval
                          and release are disabled.
                        </p>
                      </div>
                      <label htmlFor="reopen">Reason for a fresh cycle</label>
                      <textarea
                        id="reopen"
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder="Explain why this case needs a fresh review."
                      />
                      <button
                        className="primary"
                        disabled={busy || reason.trim().length < 10}
                        onClick={() => action("reopen", { reason })}
                      >
                        Open fresh review cycle
                      </button>
                    </>
                  )}
                  {current?.state === "published" && (
                    <button
                      className="primary"
                      onClick={() => {
                        setSelected(current.release_id);
                        go("archive");
                      }}
                    >
                      Open the release
                      <ArrowRight size={17} />
                    </button>
                  )}
                  <div className="review-links">
                    <button
                      onClick={() => {
                        setClaim("C01");
                        go("evidence");
                      }}
                    >
                      Inspect evidence
                    </button>
                    <button onClick={openAudit}>Decision history</button>
                  </div>
                </>
              ))}
            {view === "approve" && current && (
              <>
                <button className="back" onClick={() => go("reviews")}>
                  <ArrowLeft size={17} />
                  Back to review
                </button>
                <span className="pill">
                  <ShieldCheck size={14} />
                  Checks passed · Private draft
                </span>
                <h2 className="panel-title" tabIndex="-1">
                  Approve one
                  <br />
                  exact version.
                </h2>
                <p className="lede">{p.conclusion}</p>
                <div className="section">
                  <h3>What remains unknown</h3>
                  <p>{p.unknowns.join(" and ")}.</p>
                </div>
                <div className="version-line">
                  <FileText size={18} />
                  <div>
                    Version {p.version}
                    <small>Review by {date(current.deadline)}</small>
                  </div>
                </div>
                <details>
                  <summary>Version and check details</summary>
                  <code>{current.digest}</code>
                  <ul className="checks">
                    {current.qc.checks.map((c) => (
                      <li key={c.name}>
                        <Check size={14} />
                        {c.name.replaceAll("_", " ")}
                      </li>
                    ))}
                  </ul>
                </details>
                <label className="acknowledgement">
                  <input
                    type="checkbox"
                    checked={ack}
                    onChange={(e) => setAck(e.target.checked)}
                  />
                  <span>I reviewed this version and its uncertainty.</span>
                </label>
                <button
                  className="primary"
                  disabled={!ack || busy || current.state !== "review_pending"}
                  onClick={() => action("approve", { acknowledged: true })}
                >
                  {busy ? "Recording…" : "Approve this version"}
                  <Check size={17} />
                </button>
                <p className="fineprint">
                  Approval does not publish. Operator release follows.
                </p>
              </>
            )}
            {view === "respond" && (
              <>
                <button className="back" onClick={() => go("reviews")}>
                  <ArrowLeft size={17} />
                  Back to review
                </button>
                <p className="eyebrow">
                  {responseType === "correct"
                    ? "Expert correction"
                    : "Expert challenge"}
                </p>
                <h2 className="panel-title" tabIndex="-1">
                  Where should
                  <br />
                  the view change?
                </h2>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    action(responseType, { claim_id: claim, text, reason });
                  }}
                >
                  <label htmlFor="claim">Claim</label>
                  <select
                    id="claim"
                    value={claim}
                    onChange={(e) => setClaim(e.target.value)}
                  >
                    {p.claims.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.id} · {c.text}
                      </option>
                    ))}
                  </select>
                  <label htmlFor="change">
                    {responseType === "correct"
                      ? "What should change?"
                      : "What is your counter-view?"}
                  </label>
                  <textarea
                    id="change"
                    value={text}
                    minLength={10}
                    maxLength={2000}
                    required
                    onChange={(e) => setText(e.target.value)}
                    placeholder="State the replacement or disputed interpretation."
                  />
                  <label htmlFor="reason">Why?</label>
                  <textarea
                    id="reason"
                    value={reason}
                    minLength={10}
                    maxLength={2000}
                    required
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Explain the evidence or missing assumption."
                  />
                  <p className="fineprint">
                    Your response is recorded with this version. A replacement
                    needs new checks and expert review.
                  </p>
                  <button className="primary" disabled={busy}>
                    {busy
                      ? "Saving…"
                      : responseType === "correct"
                        ? "Save correction"
                        : "Request investigation"}
                    <ArrowRight size={17} />
                  </button>
                </form>
              </>
            )}
            {view === "release-confirm" && current && (
              <>
                <button className="back" onClick={() => go("reviews")}>
                  <ArrowLeft size={17} />
                  Back to review
                </button>
                <p className="eyebrow">Operator release</p>
                <h2 className="panel-title" tabIndex="-1">
                  Release the
                  <br />
                  approved version.
                </h2>
                <p className="lede">
                  The public view and memo will use exactly the packet the
                  expert approved.
                </p>
                <div className="section">
                  <h3>Release destination</h3>
                  <p>
                    {session.demo
                      ? "This isolated demonstration archive. No Git push or email is sent."
                      : "Configured public evidence mirror."}
                  </p>
                </div>
                <div className="version-line">
                  <ShieldCheck size={20} />
                  <div>
                    Version {p.version}
                    <small>Approved by {current.approval?.name}</small>
                  </div>
                </div>
                <p className="muted">
                  The server will recheck the source version, review deadline,
                  QC record and approval digest.
                </p>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => action("release")}
                >
                  {busy ? "Releasing…" : "Release approved version"}
                  <ArrowRight size={17} />
                </button>
              </>
            )}
            {view === "archive" && (
              <>
                <p className="eyebrow">The public record</p>
                <h2 className="panel-title" tabIndex="-1">
                  A view you
                  <br />
                  can trace.
                </h2>
                <p className="lede">
                  Approved records, their evidence and the memo that carries
                  them.
                </p>
                <div className="archive-list">
                  {[...releases].reverse().map((r) => (
                    <article className="archive-item" key={r.id}>
                      <span className="pill">
                        <CheckCircle2 size={13} />
                        Synthetic release · Version {r.packet.version}
                      </span>
                      <h3>{r.packet.title}</h3>
                      <p>{r.packet.conclusion}</p>
                      <small>{date(r.published_at)}</small>
                      <button
                        className="inline-link"
                        onClick={() => openMemo(r)}
                      >
                        Read the memo
                        <ArrowRight size={16} />
                      </button>
                    </article>
                  ))}
                </div>
                <div className="caution">
                  <Info size={17} />
                  <p>
                    All records in this environment are synthetic. No live
                    financial view has been published.
                  </p>
                </div>
              </>
            )}
            {view === "memo" && (
              <>
                <button className="back" onClick={() => go("archive")}>
                  <ArrowLeft size={17} />
                  Back to archive
                </button>
                <p className="eyebrow">The review memo</p>
                <h2 className="panel-title" tabIndex="-1">
                  A clear view.
                  <br />
                  An inspectable record.
                </h2>
                <div className="export-row">
                  <a
                    className="primary"
                    href={"/api/releases/" + publicRelease.id + "/memo.pdf"}
                  >
                    <Download size={17} />
                    Download PDF
                  </a>
                  <a
                    className="secondary"
                    href={"/api/releases/" + publicRelease.id + "/memo.md"}
                    aria-label="Download Markdown memo"
                  >
                    <FileText size={19} />
                  </a>
                </div>
                <article className="memo-paper">
                  {memo.split("\n\n").map((b, i) =>
                    b.startsWith("## ") ? (
                      <section key={i}>
                        <h3>{b.split("\n")[0].replace("## ", "")}</h3>
                        <p>{b.split("\n").slice(1).join("\n")}</p>
                      </section>
                    ) : b.startsWith("# ") ? (
                      <h3 className="memo-heading" key={i}>
                        {b.replace("# ", "")}
                      </h3>
                    ) : (
                      <p key={i}>{b}</p>
                    ),
                  )}
                </article>
              </>
            )}
            {view === "audit" && (
              <>
                <button className="back" onClick={() => go("reviews")}>
                  <ArrowLeft size={17} />
                  Back to review
                </button>
                <p className="eyebrow">Decision history</p>
                <h2 className="panel-title" tabIndex="-1">
                  Judgment leaves
                  <br />a record.
                </h2>
                {audit.length ? (
                  audit.map((a) => (
                    <article className="audit-row" key={a.id}>
                      <span className="audit-dot" />
                      <h3>{a.action.replaceAll("_", " ")}</h3>
                      <small>
                        {date(a.at)} · {a.actor}
                      </small>
                      <p>
                        {typeof a.detail === "string"
                          ? a.detail
                          : a.detail.reason ||
                            a.detail.state ||
                            JSON.stringify(a.detail)}
                      </p>
                    </article>
                  ))
                ) : (
                  <p className="muted">
                    No decisions yet. Corrections, approvals and releases will
                    appear here.
                  </p>
                )}
              </>
            )}
          </div>
        </section>
      </main>
      {renderNav(true)}
    </>
  );
}
createRoot(document.getElementById("root")).render(<App />);
