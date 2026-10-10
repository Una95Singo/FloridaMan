"""CLI entry point for the pipeline core: ingest -> triggers -> draft.

Implements ARC-002 (operated, human-supervised runs — not autonomous): an
operator invokes one check, and the pipeline does the analytical legwork
up to the draft stage. QC, the expert gate, and publishing belong to
sibling builders.

Usage:
    python -m floridaman.run --storm isaias --once

``--storm`` accepts a storm name, an NHC ATCF id, or a wallet, matched
against the live NHC Atlantic RSS (see ``ingest.find_storm``). Examples:
``isaias``, ``AL092026``, ``AT4``. The ATCF scheme is basin ("AL") +
two-digit storm number + year ("AL092026"); the number is assigned by NHC
per season and discovered from the RSS feed, never hardcoded — so
``--storm`` for a future storm is just its name as NHC spells it.

Flow:
1. Discover active storms from the NHC RSS; match ``--storm``.
2. Fetch + parse the public advisory (and discussion) -> Advisory.
3. Load the previous snapshot; evaluate triggers (TRG-001..003).
4. If any fired: load the bond universe, draft the trace with the
   configured Reasoner (default: StubReasoner), write
   ``trace-<YYYYMMDD>-<NNN>.md``, print the path. TRG-003 also marks the
   watch closed in state.
5. If none fired: print SILENCE and exit 0 (TRG-005 — silence is
   correct; no draft, no output). The heartbeat log line goes to stdout
   for the operator's scheduler to capture.

``--once`` performs exactly one check now. The 12h heartbeat cadence
(TRG-004) is the scheduler's job — the operator's cron/systemd timer
invokes this; ``triggers.heartbeat_due`` is available for schedulers that
want to skip invocations, but ``--once`` always checks because the
operator explicitly asked for a check.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from floridaman import draft as draft_mod
from floridaman import ingest, triggers

DEFAULT_STATE_DIR = Path.home() / ".floridaman" / "state"
DEFAULT_WATCH_ROOT = Path.cwd() / "watch"

EXIT_OK = 0
EXIT_STORM_NOT_FOUND = 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="floridaman",
        description="FloridaMan pipeline core: NHC ingest -> triggers -> draft trace.",
    )
    p.add_argument("--storm", required=True,
                   help="Storm name, ATCF id (e.g. AL092026), or wallet (e.g. AT4).")
    p.add_argument("--once", action="store_true",
                   help="Perform exactly one check now.")
    p.add_argument("--force", action="store_true",
                   help="Check even if the storm's watch is closed.")
    p.add_argument("--watch-root", default=str(DEFAULT_WATCH_ROOT),
                   help="Parent dir for watch/<storm>/ output (default: ./watch).")
    p.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR),
                   help="Dir for the JSON state file (default: ~/.floridaman/state).")
    p.add_argument("--universe", default="",
                   help="Path to bond-universe.csv (default: alongside --watch-root).")
    return p


def emit_github_outputs(advisory) -> None:
    """Write the advisory identity to $GITHUB_OUTPUT when running in Actions.

    The watch workflow's QC step consumes ``advisory`` (number, e.g. "13A")
    and ``advisory_descriptor`` (human-readable, e.g. "Advisory 13A issued
    2026-10-09T23:49:43Z") for check 4 (freshness). No-op outside Actions.
    """
    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        return
    number = advisory.advisory_number or ""
    descriptor = f"Advisory {number}".strip()
    if advisory.issued_utc:
        descriptor += f" issued {advisory.issued_utc}"
    try:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"advisory={number}\n")
            fh.write(f"advisory_descriptor={descriptor}\n")
    except OSError as exc:  # never fail a run on output plumbing
        print(f"Warning: could not write $GITHUB_OUTPUT: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    now = datetime.now(timezone.utc)

    storms = ingest.discover_storms()
    match = ingest.find_storm(storms, args.storm)
    if match is None:
        active = ", ".join(s.get("name") or "?" for s in storms) or "none"
        print(f"Storm '{args.storm}' not found in the NHC Atlantic RSS. "
              f"Active: {active}.", file=sys.stderr)
        return EXIT_STORM_NOT_FOUND

    advisory = ingest.fetch_advisory(match)
    storm_id = advisory.storm_id or match.get("atcf") or args.storm.lower()
    emit_github_outputs(advisory)

    state = triggers.load_state(args.state_dir)
    entry = state.get(storm_id, {})
    previous = entry.get("snapshot")  # None on first sighting -> TRG-001

    fired = triggers.evaluate(previous, advisory, entry.get("last_run_utc"))
    if entry.get("closed") and not args.force:
        fired = []

    # Always refresh the check timestamp (heartbeat bookkeeping, TRG-004).
    entry["snapshot"] = advisory.to_dict()
    entry["last_run_utc"] = now.isoformat()
    state[storm_id] = entry

    if not fired:
        triggers.save_state(args.state_dir, state)
        print("SILENCE — no trigger fired; nothing drafted, nothing published. "
              "(TRG-005: no trigger, no output)")
        return EXIT_OK

    watch_dir = Path(args.watch_root) / (advisory.name or storm_id).lower()
    universe_path = args.universe or str(Path(args.watch_root).parent / "bond-universe.csv")
    universe = draft_mod.load_universe(universe_path)
    if not universe:
        print(f"Warning: bond universe empty or unreadable at {universe_path}; "
              "drafting with zero tranches.", file=sys.stderr)

    reasoner = draft_mod.StubReasoner()  # swap for a real Reasoner here
    reasoning = reasoner.reason(advisory, universe, draft_mod.prior_trace_texts(watch_dir))
    run_number = draft_mod.next_run_number(watch_dir)
    text = draft_mod.build_trace(advisory, fired, universe, reasoning, run_number,
                                 generated_utc=now)
    path = draft_mod.write_trace(watch_dir, text, run_number, generated_utc=now)

    if "TRG-003" in fired:
        entry["closed"] = True  # landfall/dissipation closes the watch
    triggers.save_state(args.state_dir, state)

    print(f"DRAFT — triggers fired: {', '.join(fired)}")
    print(f"Trace written: {path}")
    print("Status: draft only. Awaiting QC + expert review before any publication.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
