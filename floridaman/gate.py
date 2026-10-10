"""Expert gate for FloridaMan v1 — the human stays the judge.

Implements the expert-review gate from the agentic SDLC spec and
``agents-qc-reviewer-agent.md`` ("the hypothesis itself is the expert's
to judge"): after :mod:`floridaman.qc` returns PASS, this module opens
a GitHub issue on the repo containing the hypothesis and the
"where am I wrong?" questions, records a *pending* state file, and
pauses. ``check_resolution()`` later reads the issue's comments:
an ``APPROVE`` comment resumes toward publish; a ``CORRECT`` /
``REQUEST CHANGES`` comment resumes with the expert's correction
attached. Nothing is published until the expert approves.

v1 semantics (deliberately narrow):
  * Approval marker: a comment whose body starts with ``APPROVE``
    (case-insensitive).
  * Correction marker: a comment containing ``CORRECT`` or
    ``REQUEST CHANGES`` (case-insensitive). The full comment body is
    stored as the correction for the watch agent to apply.
  * Comments are scanned oldest-first; the FIRST marker-bearing
    comment decides. Later discussion does not override it (v1).

GitHub access goes through the injectable ``GitHub`` protocol.
Two real implementations ship:

  * :class:`GhCliGitHub` — shells out to the ``gh`` CLI (uses the
    operator's existing ``gh auth`` session; no token handling here).
  * :class:`UrllibGitHub` — talks to the REST API with ``urllib``;
    the token comes ONLY from the ``GITHUB_TOKEN`` environment
    variable. It is never hardcoded, never logged, never committed.

No secrets appear in this file. Tests inject a fake implementing the
protocol.

CLI::

    python -m floridaman.gate open --trace watch/isaias/trace-20261009-004.md \\
        --qc-record watch/isaias/qc-20261009-004.md --storm isaias \\
        --repo OWNER/REPO --state-dir /tmp/gate-state
    python -m floridaman.gate status --state /tmp/gate-state/gate-004.json --repo OWNER/REPO
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Protocol


# ---------------------------------------------------------------------------
# GitHub interface (injectable)
# ---------------------------------------------------------------------------

class GitHub(Protocol):
    """Minimal GitHub surface the gate needs."""

    def create_issue(self, repo: str, title: str, body: str) -> int:
        """Open an issue; return its number."""
        ...

    def list_comments(self, repo: str, issue_number: int) -> List[dict]:
        """Return comments as dicts with at least 'body' (oldest first)."""
        ...


class GhCliGitHub:
    """GitHub via the ``gh`` CLI. Uses the operator's ``gh auth`` session.

    Raises RuntimeError with a clear message if ``gh`` is missing or
    the call fails. Never touches tokens directly.
    """

    def _run(self, *args: str) -> str:
        try:
            out = subprocess.run(
                ["gh", *args], capture_output=True, text=True, timeout=60, check=True
            )
        except FileNotFoundError:
            raise RuntimeError("gh CLI not found on PATH; cannot open the review issue.")
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"gh failed: {exc.stderr.strip()[:300]}")
        return out.stdout.strip()

    def create_issue(self, repo: str, title: str, body: str) -> int:
        out = self._run("issue", "create", "--repo", repo,
                        "--title", title, "--body", body)
        m = re.search(r"/issues/(\d+)", out)
        if not m:
            raise RuntimeError(f"could not parse issue number from gh output: {out!r}")
        return int(m.group(1))

    def list_comments(self, repo: str, issue_number: int) -> List[dict]:
        out = self._run("api", f"repos/{repo}/issues/{issue_number}/comments",
                        "--paginate", "-q",
                        ".[] | [.created_at, .user.login, .body] | @tsv")
        comments = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                created_at, author, body = parts
                comments.append({"created_at": created_at, "author": author, "body": body})
        return comments


class UrllibGitHub:
    """GitHub via the REST API with urllib. Token from ``GITHUB_TOKEN`` env only."""

    API = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise RuntimeError("GITHUB_TOKEN is not set in the environment.")

    def _request(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            self.API + path, data=data, method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "FloridaMan-Gate/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            raise RuntimeError(f"GitHub API call failed: {exc}")

    def create_issue(self, repo: str, title: str, body: str) -> int:
        res = self._request("POST", f"/repos/{repo}/issues",
                            {"title": title, "body": body})
        return int(res["number"])

    def list_comments(self, repo: str, issue_number: int):
        res = self._request("GET", f"/repos/{repo}/issues/{issue_number}/comments")
        return [{"created_at": c.get("created_at"), "author": (c.get("user") or {}).get("login"),
                 "body": c.get("body", "")} for c in res]


# ---------------------------------------------------------------------------
# Gate state
# ---------------------------------------------------------------------------

def _extract_hypothesis(trace_text: str) -> str:
    lines = trace_text.splitlines()
    buf: List[str] = []
    in_h = False
    for line in lines:
        if line.startswith("#"):
            if in_h:
                break
            if "hypothesis" in line.lower():
                in_h = True
            continue
        if in_h:
            buf.append(line)
    return "\n".join(buf).strip()


def _extract_questions(trace_text: str) -> List[str]:
    lines = trace_text.splitlines()
    buf: List[str] = []
    in_q = False
    for line in lines:
        if line.startswith("#"):
            if in_q:
                break
            if "where am i wrong" in line.lower():
                in_q = True
            continue
        if in_q:
            buf.append(line)
    return [l.strip() for l in buf
            if re.match(r"\s*(?:[-*]|\d+[.)])\s+\S", l)]


def _run_id(trace_path: str) -> str:
    m = re.search(r"trace-\d{8}-(\d+)\.md$", Path(trace_path).name)
    return m.group(1) if m else "???"


def open_review_issue(trace_path: str, qc_record_path: str, storm: str,
                      repo: str, github: GitHub,
                      state_dir: str = ".") -> str:
    """Open the expert-review issue and pause.

    Writes a pending-state JSON file and returns its path. The caller
    (heartbeat workflow) stops here: publishing happens only after
    :func:`check_resolution` reports ``approved``.
    """
    trace_text = Path(trace_path).read_text(encoding="utf-8")
    hypothesis = _extract_hypothesis(trace_text)
    questions = _extract_questions(trace_text)
    run = _run_id(trace_path)

    title = f"[expert review] {storm.title()} watch run {run} — hypothesis for judgment"
    body_lines = [
        f"QC verdict: **PASS** (`{Path(qc_record_path).name}`).",
        "",
        "The QC gate validated mechanics only (grounding, computation,",
        "freshness, completeness). The hypothesis below is yours to judge.",
        "",
        "## Hypothesis (indicative, not marks)",
        "",
        hypothesis,
        "",
        "## Where am I wrong?",
        "",
    ]
    for i, q in enumerate(questions, 1):
        body_lines.append(f"{i}. {re.sub(r'^\s*(?:[-*]|\d+[.)])\s+', '', q)}")
    body_lines += [
        "",
        "---",
        "Reply **APPROVE** to release this run for publication, or",
        "**CORRECT:** followed by your correction to send it back to the watch agent.",
        f"Full trace: `{trace_path}` · QC record: `{qc_record_path}`",
    ]
    issue_number = github.create_issue(repo, title, "\n".join(body_lines))

    state = {
        "run_id": run,
        "storm": storm,
        "trace_path": str(trace_path),
        "qc_record_path": str(qc_record_path),
        "repo": repo,
        "issue_number": issue_number,
        "status": "pending",
        "opened_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "correction": None,
    }
    state_path = str(Path(state_dir) / f"gate-{run}.json")
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    Path(state_path).write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state_path


def check_resolution(state_path: str, github: GitHub) -> str:
    """Read issue comments and resolve the pending gate.

    Returns the new status: ``approved``, ``correction_requested``,
    or ``pending`` (no marker comment yet). Updates the state file.
    """
    state = json.loads(Path(state_path).read_text(encoding="utf-8"))
    comments = github.list_comments(state["repo"], state["issue_number"])
    status = "pending"
    correction = None
    for c in comments:  # oldest first; first marker wins (v1)
        body = (c.get("body") or "").strip()
        if re.match(r"(?i)^approve\b", body):
            status = "approved"
            break
        if re.search(r"(?i)\b(correct\b|request changes)\b", body):
            status = "correction_requested"
            correction = body
            break
    state["status"] = status
    state["correction"] = correction
    state["resolved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    Path(state_path).write_text(json.dumps(state, indent=2), encoding="utf-8")
    return status


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="FloridaMan expert gate.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_open = sub.add_parser("open", help="Open the expert-review issue and pause.")
    p_open.add_argument("--trace", required=True)
    p_open.add_argument("--qc-record", required=True)
    p_open.add_argument("--storm", required=True)
    p_open.add_argument("--repo", required=True, help="OWNER/REPO.")
    p_open.add_argument("--state-dir", default=".")
    p_open.add_argument("--via", choices=["gh", "urllib"], default="gh",
                        help="GitHub access method (urllib needs GITHUB_TOKEN).")

    p_status = sub.add_parser("status", help="Check whether the expert resolved the gate.")
    p_status.add_argument("--state", required=True, help="Gate state JSON from 'open'.")
    p_status.add_argument("--repo", default=None, help="Override repo in state file.")
    p_status.add_argument("--via", choices=["gh", "urllib"], default="gh")

    args = ap.parse_args(argv)
    github: GitHub = GhCliGitHub() if args.via == "gh" else UrllibGitHub()
    try:
        if args.cmd == "open":
            path = open_review_issue(args.trace, args.qc_record, args.storm,
                                     args.repo, github, args.state_dir)
            print(f"Gate OPEN (pending expert review). State: {path}")
        else:
            if args.repo:  # allow override without editing the state file
                st = json.loads(Path(args.state).read_text(encoding="utf-8"))
                st["repo"] = args.repo
                Path(args.state).write_text(json.dumps(st, indent=2), encoding="utf-8")
            status = check_resolution(args.state, github)
            print(f"Gate status: {status}")
    except RuntimeError as exc:
        print(f"GATE ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
