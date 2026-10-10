"""Draft the watch-trace markdown for a fired trigger.

Implements the draft half of the "Output contract" in
``agents-storm-watch-agent.md``: each run produces a trace
(``watch/<storm>/trace-<timestamp>.md``) shaped EXACTLY like the reference
trace (same section headers, same ordering). This module handles the
mechanical assembly:

- loads the bond universe from ``bond-universe.csv`` (the universe is the
  CSV; no bond data is ever invented here),
- assembles the **Trigger** and **Inputs and sources** sections from real
  advisory data,
- calls a :class:`Reasoner` for **Exposure mapping**, **Hypothesis**,
  **Falsification conditions**, and **Where am I wrong?**,
- writes the ``trace-<timestamp>.md`` file.

The reasoning step is an explicit LLM interface. To plug in a real
reasoner: implement the :class:`Reasoner` protocol — ``reason(advisory,
universe, prior_traces) -> Reasoning`` — in your own code and pass the
instance to :func:`build_trace`. Your implementation configures its own
model access; floridaman reads no credentials, defines no key env-vars,
imports no vendor SDKs, and never sends anything anywhere. The shipped
:class:`StubReasoner` emits a clearly-labeled template trace (every
estimate marked STUB, no invented conclusions) so the pipeline is
exercisable end-to-end without a model.

Deliberate non-goal: this module does NOT produce ``latest.md`` (the
current-best hypothesis artifact) — that is the publish builder's job,
after QC validation (SPEC TRC-004) and expert review (EXP-001). Drafts are
written with a "Draft. Not published. Awaiting QC + expert review."
banner. Doctrine: hypotheses are "indicative" ranges, never points, and
the word "marks" in the secondary-market pricing sense never appears.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from floridaman.ingest import Advisory

# ---------------------------------------------------------------------------
# Bond universe
# ---------------------------------------------------------------------------

@dataclass
class Bond:
    """One tranche row from bond-universe.csv. The CSV is the universe:
    this module never invents or alters bond terms."""

    deal: str = ""
    sponsor: str = ""
    tranche: str = ""
    size_usd_m: str = ""
    trigger_type: str = ""
    trigger_detail: str = ""
    attachment_usd_m: str = ""
    exhaustion_usd_m: str = ""
    expected_loss_pct: str = ""
    spread_pct: str = ""
    maturity: str = ""
    covered_area: str = ""
    artemis_url: str = ""
    notes: str = ""


def load_universe(csv_path: str | Path) -> list[Bond]:
    """Load the bond universe. Missing/unparseable file -> [] (never raises)."""
    bonds: list[Bond] = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                known = {f for f in Bond.__dataclass_fields__}
                bonds.append(Bond(**{k: (row.get(k) or "") for k in known}))
    except OSError:
        pass
    return bonds


# ---------------------------------------------------------------------------
# Reasoner interface
# ---------------------------------------------------------------------------

@dataclass
class Reasoning:
    """The reasoner's contribution: markdown bodies for the four
    judgmental sections, in order."""

    exposure_mapping: str = ""
    hypothesis: str = ""
    falsification_conditions: str = ""
    where_am_i_wrong: str = ""


class Reasoner(Protocol):
    """Interface for the judgmental half of the trace.

    A real implementation receives the normalized advisory, the bond
    universe, and prior traces (newest first, raw markdown) and returns
    the four sections. How it reasons — an LLM call, rules, a human —
    is its own business. It must obey the agent contract: ranges not
    points, "indicative" labeling, source-linked claims, and no
    secondary-market pricing language.
    """

    def reason(self, advisory: Advisory, universe: list[Bond],
               prior_traces: list[str]) -> Reasoning:
        ...


class StubReasoner:
    """Template reasoner: emits a clearly-labeled stub trace.

    Every estimate is marked STUB and no conclusions are invented — the
    sections exist so the pipeline's shape is exercisable end-to-end.
    A stub trace must never be mistaken for analysis: the banner stays.
    """

    def reason(self, advisory: Advisory, universe: list[Bond],
               prior_traces: list[str]) -> Reasoning:
        deals = sorted({b.deal for b in universe if b.deal})
        return Reasoning(
            exposure_mapping=(
                "[STUB] Exposure mapping not computed — plug in a real "
                f"Reasoner. Universe on file: {len(universe)} tranches across "
                f"{len(deals)} deals. Prior traces available: {len(prior_traces)}."
            ),
            hypothesis=(
                "[STUB] No indicative hypothesis — a real Reasoner must supply "
                "ranges (never points), labeled indicative, with confidence "
                "level and key uncertainties."
            ),
            falsification_conditions=(
                "[STUB] A real Reasoner must state what would prove the "
                "hypothesis wrong, what to watch, and by when."
            ),
            where_am_i_wrong=(
                "[STUB] A real Reasoner must end with the specific questions "
                "a senior expert should challenge."
            ),
        )


# ---------------------------------------------------------------------------
# Trace assembly
# ---------------------------------------------------------------------------

def prior_trace_texts(watch_dir: str | Path, limit: int = 5) -> list[str]:
    """Read prior trace-*.md files, newest first (never raises)."""
    traces = sorted(Path(watch_dir).glob("trace-*.md"))
    texts = []
    for p in reversed(traces[-limit:]):
        try:
            texts.append(p.read_text(encoding="utf-8"))
        except OSError:
            continue
    return texts


def next_run_number(watch_dir: str | Path) -> int:
    """Next run number = max existing trace run suffix + 1 (1-based)."""
    import re
    n = 0
    for p in Path(watch_dir).glob("trace-*.md"):
        m = re.search(r"trace-\d{8}-(\d+)\.md$", p.name)
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def build_trace(advisory: Advisory, fired: list[str], universe: list[Bond],
                reasoning: Reasoning, run_number: int,
                generated_utc: datetime | None = None) -> str:
    """Assemble the full trace markdown.

    Section headers and ordering match the reference trace exactly:
    Trigger / Inputs and sources / Exposure mapping /
    Hypothesis (indicative, not marks) / Falsification conditions /
    Where am I wrong? (for the expert).
    """
    gen = generated_utc or datetime.now(timezone.utc)
    name = advisory.name or "Unknown storm"
    stype = advisory.storm_type or "Tropical cyclone"
    adv_no = advisory.advisory_number or "unknown advisory number"
    issued = advisory.issued_utc or "unknown issue time"

    trigger_lines = _trigger_section(advisory, fired)
    inputs_lines = _inputs_section(advisory, universe)

    return f"""# Watch trace — {stype} {name} — run {run_number:03d}

*Draft. Not published. Awaiting QC + expert review.*

## Trigger

{trigger_lines}

## Inputs and sources

{inputs_lines}

## Exposure mapping

{reasoning.exposure_mapping}

## Hypothesis (indicative, not marks)

{reasoning.hypothesis}

## Falsification conditions

{reasoning.falsification_conditions}

## Where am I wrong? (for the expert)

{reasoning.where_am_i_wrong}
"""


def _trigger_section(advisory: Advisory, fired: list[str]) -> str:
    ids = "/".join(fired) if fired else "none"
    winds = f"{advisory.max_winds_mph:g} mph" if advisory.max_winds_mph is not None else "unknown winds"
    cat = advisory.category or "unknown category"
    pres = f"{advisory.min_pressure_mb:g} mb" if advisory.min_pressure_mb is not None else "unknown pressure"
    adv_no = advisory.advisory_number or "?"
    issued = advisory.issued_utc or "unknown time"
    name = advisory.name or "storm"
    return (
        f"{ids}: NHC Advisory {adv_no} ({issued}) — {name} at {winds}, "
        f"category {cat}, {pres}. Fired triggers: {', '.join(fired) if fired else 'none'}."
    )


def _inputs_section(advisory: Advisory, universe: list[Bond]) -> str:
    lat = f"{advisory.lat:.1f}N" if advisory.lat is not None else "?"
    lon = f"{abs(advisory.lon):.1f}W" if advisory.lon is not None else "?"
    lines = [
        f"- NHC Advisory {advisory.advisory_number or '?'} "
        f"({advisory.issued_utc or 'unknown time'}): {advisory.storm_type or 'cyclone'} "
        f"{advisory.name or ''} at {lat} {lon}; "
        f"{advisory.max_winds_mph:g} mph sustained, {advisory.min_pressure_mb:g} mb."
        if advisory.max_winds_mph is not None and advisory.min_pressure_mb is not None
        else f"- NHC advisory data (partial parse): position {lat} {lon}.",
    ]
    if advisory.movement_dir_deg is not None and advisory.movement_mph is not None:
        lines.append(
            f"- Movement: {advisory.movement_dir_deg}° at {advisory.movement_mph:g} mph."
        )
    if advisory.forecast_peak_mph is not None:
        lines.append(f"- Forecast peak intensity: {advisory.forecast_peak_mph:g} mph (NHC discussion).")
    if advisory.landfall_window_text:
        lines.append(f"- Landfall: {advisory.landfall_window_text}")
    if advisory.watches_warnings:
        lines.append(f"- Watches/warnings (raw):\n\n```\n{advisory.watches_warnings[:1500]}\n```")
    if advisory.source_url:
        lines.append(f"- Source: {advisory.source_url}")
    if advisory.parse_notes:
        lines.append("- Parse notes: " + "; ".join(advisory.parse_notes))
    deals = sorted({b.deal for b in universe if b.deal})
    lines.append(
        f"- Bond universe: `bond-universe.csv` ({len(universe)} tranches, {len(deals)} deals). "
        "Terms taken as-is from the CSV; nothing invented."
    )
    return "\n".join(lines)


def write_trace(watch_dir: str | Path, text: str, run_number: int,
                generated_utc: datetime | None = None) -> Path:
    """Write ``trace-<YYYYMMDD>-<NNN>.md`` into the watch dir. Returns the path."""
    gen = generated_utc or datetime.now(timezone.utc)
    watch = Path(watch_dir)
    watch.mkdir(parents=True, exist_ok=True)
    path = watch / f"trace-{gen.strftime('%Y%m%d')}-{run_number:03d}.md"
    path.write_text(text, encoding="utf-8")
    return path
