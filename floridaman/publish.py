"""Publish step for FloridaMan v1 — commit an approved trace + QC record.

Implements the publication half of the delivery contract: after the QC
gate passes AND the expert gate approves, :func:`publish` copies the
trace and its QC record into ``watch/<storm>/`` inside the repo and
commits them with ``git`` via subprocess.

Deliberately NOT done here:
  * Pushing. The operator pushes (``git push``) after inspecting the
    commit. Network publication stays a human decision.
  * Approving. Callers must have run :mod:`floridaman.gate` to
    ``approved`` first; this module does not re-check (v1 keeps the
    gate in the gate module, not here).

Never invents paths: the trace and QC record paths are taken exactly
as passed; the destination is always ``<repo_dir>/watch/<storm>/``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _git(repo_dir: str, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", repo_dir, *args],
            capture_output=True, text=True, timeout=60, check=True,
        )
    except FileNotFoundError:
        raise RuntimeError("git not found on PATH.")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"git {' '.join(args)} failed: {exc.stderr.strip()[:300]}")
    return out.stdout.strip()


def _run_id(trace_path: str) -> str:
    m = re.search(r"trace-\d{8}-(\d+)\.md$", Path(trace_path).name)
    return m.group(1) if m else "???"


def publish(trace_path: str, qc_path: str, storm: str, repo_dir: str,
            message: Optional[str] = None) -> str:
    """Commit trace + QC record into ``watch/<storm>/``. Returns the commit SHA.

    Raises RuntimeError on any failure (missing files, not a git repo,
    git errors). Does NOT push — the operator runs ``git push``.
    """
    trace_p = Path(trace_path)
    qc_p = Path(qc_path)
    for p, label in ((trace_p, "trace"), (qc_p, "QC record")):
        if not p.is_file():
            raise RuntimeError(f"{label} not found: {p}")

    repo = Path(repo_dir)
    if not repo.is_dir():
        raise RuntimeError(f"repo_dir not found: {repo}")
    _git(str(repo), "rev-parse", "--git-dir")  # fails loudly if not a repo

    dest_dir = repo / "watch" / storm
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_trace = dest_dir / trace_p.name
    dest_qc = dest_dir / qc_p.name
    shutil.copy2(trace_p, dest_trace)
    shutil.copy2(qc_p, dest_qc)

    _git(str(repo), "add", str(dest_trace.relative_to(repo)),
         str(dest_qc.relative_to(repo)))
    run = _run_id(trace_path)
    msg = message or (
        f"Publish {storm.title()} watch traces — run {run} "
        f"(trace + QC record, expert-approved)"
    )
    _git(str(repo), "commit", "-m", msg)
    return _git(str(repo), "rev-parse", "HEAD")
