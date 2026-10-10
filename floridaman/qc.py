"""QC reviewer gate for FloridaMan v1 — checks 1-8 as executable code.

Implements the mechanical contract in
``agents-qc-reviewer-agent.md`` (``~/workspace/github-finish/floridaman/``):
check 1 source resolution, check 2 independent recomputation, check 3
units and dimensions, check 4 freshness, check 5 falsification present,
check 6 language audit, check 7 expert-handoff completeness, check 8
prior grounding.

Doctrine (from DESIGN_THESIS.md): two kinds of wrong. A disproven
hypothesis is the job working; a miscalculation, stale source, or
ungrounded claim is a DEFECT. This module catches defects before the
expert ever sees them. It never re-judges the hypothesis itself.

Design notes
------------
* Deterministic: every input the checker needs arrives through
  ``QcContext``. The live NHC "latest advisory" and the bond universe
  are injected, never scraped inside the checks, so the acceptance
  tests can pin them.
* ``fetch`` is injectable for tests; the default does a best-effort
  ``urllib`` fetch with a timeout and NEVER raises — an unreachable
  page is recorded as unverifiable, not an exception.
* Cross-bullet kt-to-mph reconciliation is out of scope for v1: only
  same-sentence kt/mph pairs are verified, so figures drawn from
  different bullet sources are never spuriously paired.
* v1 does not attempt live NHC page parsing; freshness is decided
  from the injected ``latest_advisory_number`` / ``advisory_vintage``.
  Whatever the heartbeat operator knows, it must inject.

Usage
-----
    from floridaman.qc import review, write_qc_record, QcContext
    ctx = QcContext(universe_csv_path="bond-universe.csv",
                    latest_advisory_number="6",
                    advisory_vintage={"4": {"max_winds_mph": 45},
                                      "5A": {"max_winds_mph": 65},
                                      "6": {"max_winds_mph": 70}})
    verdict = review("watch/isaias/trace-20261008-001.md", ctx)
    write_qc_record(verdict, "watch/isaias/qc-20261008-001.md")
    print(verdict.verdict)   # "PASS" or "BLOCKED"
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

FetchFn = Callable[[str], Optional[str]]


def default_fetch(url: str, timeout: float = 10.0) -> Optional[str]:
    """Best-effort page fetch. Returns text or None. Never raises."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "FloridaMan-QC/1.0 (+https://singolab.com)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(200_000)
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")
    except Exception:
        return None


@dataclass
class QcContext:
    """Everything the checks need, injected for determinism.

    * ``universe_csv_path`` — ground-truth bond universe CSV.
    * ``latest_advisory_number`` — e.g. "6". The newest NHC advisory
      number known at validation time (supplied by the heartbeat).
    * ``latest_advisory_descriptor`` — used when the trace's trigger
      cites no advisory number (e.g. "7:20 AM CT alert"). Compared
      after normalisation.
    * ``advisory_vintage`` — number -> {"max_winds_mph": int, ...}.
      Known advisory history so the checker can spot a trace whose
      figures belong to an older advisory than the one it cites.
    * ``fetch`` — url -> page text | None. Injectable; default is
      best-effort urllib, never raising.
    * ``now_utc`` — validation timestamp for the record.
    """

    universe_csv_path: str
    latest_advisory_number: Optional[str] = None
    latest_advisory_descriptor: Optional[str] = None
    advisory_vintage: Dict[str, Dict] = field(default_factory=dict)
    fetch: FetchFn = default_fetch
    now_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CheckResult:
    number: int
    name: str
    status: str  # "PASS" | "NOTE" | "BLOCKER"
    detail: str


@dataclass
class Verdict:
    """Result of :func:`review`. ``verdict`` is "PASS" or "BLOCKED"."""

    trace_path: str
    storm: str
    run_id: str
    verdict: str
    checks: List[CheckResult]
    blockers: List[str]
    notes: List[str]
    validated_at: str


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

MONEY_RE = re.compile(
    r"\$([\d,]+(?:\.\d+)?)\s*(bn|billion|mm|m|million)?", re.IGNORECASE
)
URL_RE = re.compile(r"https?://[^\s\)\]>\"']+")
ATT_WORDS_RE = re.compile(r"\b(att|attach|attaches|attachment|attachments)\b", re.I)
EXH_WORDS_RE = re.compile(r"\b(exh|exhaustion|exhaustions)\b", re.I)
QUALIFIER_RE = re.compile(
    r"(above|below|under|over|up\s+to|around|about|approximately|nearly|almost|sub-|~)\s*$",
    re.I,
)
VAGUE_ATTR_RE = re.compile(
    r"\b(analysts?\s+say|sources?\s+say|experts?\s+say|it\s+is\s+(widely\s+)?believed"
    r"|reports\s+suggest|some\s+say)\b",
    re.I,
)
CAT_RE = re.compile(r"\b(?:Category|Cat)\s*(\d)\b\+?", re.I)
MPH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mph", re.I)
MB_RE = re.compile(r"(\d{3,4})\s*mb\b", re.I)
KT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*kt\b", re.I)
ADVISORY_RE = re.compile(r"Advisory\s+(\d+[A-Z]?)", re.I)
ALERT_DESC_RE = re.compile(
    r"(\d{1,2}:\d{2}\s*(?:AM|PM)\s*(?:CT|ET|CDT|EDT|UTC))\s+(?:NHC\s+)?alert", re.I
)

SAFFIR_SIMPSON = {1: (74, 95), 2: (96, 110), 3: (111, 129), 4: (130, 156), 5: (157, 400)}
# Broad central-pressure plausibility per category (mb). Loose on purpose:
# only grossly implausible pairings are defects.
MB_PLAUSIBLE = {
    0: (985, 1020),  # tropical storm
    1: (975, 995),
    2: (960, 982),
    3: (940, 968),
    4: (915, 948),
    5: (850, 925),
}


def _section(text: str, heading: str) -> str:
    """Return the markdown section under a heading containing `heading`."""
    lines = text.splitlines()
    buf: List[str] = []
    in_section = False
    for line in lines:
        if line.startswith("#"):
            if in_section:
                break
            if heading.lower() in line.lower():
                in_section = True
            continue
        if in_section:
            buf.append(line)
    return "\n".join(buf)


def _advisory_order(num: str):
    """Sortable key for advisory numbers: '5A' > '5'."""
    m = re.match(r"(\d+)([A-Z]?)", num, re.I)
    return (int(m.group(1)), m.group(2).upper()) if m else (0, "")


def _normalise_descriptor(desc: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\b(nhc|alert)\b", "", desc, flags=re.I)).strip().lower()


def _money_to_millions(number: str, unit: Optional[str]) -> float:
    val = float(number.replace(",", ""))
    if unit and unit.lower() in ("bn", "billion"):
        val *= 1000.0
    return val  # house unit is USD millions; bare "$" assumed millions


def _fmt_m(millions: float) -> str:
    """Format a USD-millions value the way the traces write it."""
    if millions >= 1000:
        return f"${millions / 1000:g}bn"
    return f"${millions:g}m"


def _sentences(text: str) -> List[str]:
    # Split on sentence-ending punctuation or blank lines only — NOT on
    # single newlines, so wrapped markdown lines stay one sentence and
    # mid-sentence conditionals ("if the storm holds\nintensity...")
    # are not orphaned from their "if".
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n\s*\n", text) if s.strip()]


# ---------------------------------------------------------------------------
# Universe loading
# ---------------------------------------------------------------------------

@dataclass
class Tranche:
    deal: str
    tranche: str
    attachment_m: Optional[float]
    exhaustion_m: Optional[float]


def load_universe(csv_path: str) -> List[Tranche]:
    """Read the bond universe CSV. 'not disclosed'/empty -> None."""
    tranches: List[Tranche] = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            def num(key: str) -> Optional[float]:
                raw = (row.get(key) or "").strip().lower()
                if not raw or "not disclosed" in raw:
                    return None
                try:
                    return float(raw.replace(",", ""))
                except ValueError:
                    return None

            tranches.append(
                Tranche(
                    deal=(row.get("deal") or "").strip(),
                    tranche=(row.get("tranche") or "").strip(),
                    attachment_m=num("attachment_usd_m"),
                    exhaustion_m=num("exhaustion_usd_m"),
                )
            )
    return tranches


# ---------------------------------------------------------------------------
# Check 1 — source resolution (contract check 1)
# ---------------------------------------------------------------------------

def check_1_source_resolution(text: str, ctx: QcContext,
                              blockers: List[str], notes: List[str]) -> CheckResult:
    name = "Source resolution"
    inputs = _section(text, "inputs")
    if not inputs.strip():
        blockers.append("B1-check1 — no 'Inputs and sources' section found.")
        return CheckResult(1, name, "BLOCKER", "Missing Inputs section.")

    urls = URL_RE.findall(inputs)
    if not urls:
        blockers.append("B1-check1 — Inputs section cites no retrievable URL.")
        return CheckResult(1, name, "BLOCKER", "No URLs in Inputs.")

    dead: List[str] = []
    live: List[str] = []
    for url in dict.fromkeys(urls):  # de-dupe, keep order
        page = ctx.fetch(url)
        (live if page else dead).append(url)
    for url in dead:
        blockers.append(
            f"B1-check1 — dead/unverifiable source: {url} "
            "(fetch failed; a claim depending on it cannot be grounded)."
        )

    vague = sorted(set(VAGUE_ATTR_RE.findall(inputs)))
    for _ in vague:
        blockers.append(
            "B1-check1 — vague attribution in Inputs "
            "(e.g. 'analysts say'); name the source or drop the claim."
        )

    # Bullets with an explicit "Source:" marker but no URL are blockers;
    # bullets with no source marker at all are notes (named attribution
    # such as "via PNJ" or a backticked dataset resolves elsewhere).
    # Group each bullet with its wrapped continuation lines before
    # judging source presence (a "Source:" URL often sits on the next line).
    bullets: List[str] = []
    for line in inputs.splitlines():
        if re.match(r"\s*[-*]\s+\S", line):
            bullets.append(line.strip())
        elif bullets and line.strip():
            bullets[-1] += " " + line.strip()

    for s in bullets:
        if "source:" in s.lower() and not URL_RE.search(s):
            blockers.append(f"B1-check1 — 'Source:' marker with no URL: {s[:90]}")
        elif not URL_RE.search(s) and "`" not in s and "via " not in s.lower():
            notes.append(f"N-check1 — input bullet with no retrievable source: {s[:90]}")

    detail_bits = [f"{len(live)} URL(s) retrievable"]
    if dead:
        detail_bits.append(f"{len(dead)} unreachable")
    status = "BLOCKER" if dead or vague else ("NOTE" if notes else "PASS")
    return CheckResult(1, name, status, "; ".join(detail_bits) + ".")


# ---------------------------------------------------------------------------
# Check 2 — independent recomputation (contract check 2)
# ---------------------------------------------------------------------------

def check_2_recomputation(text: str, ctx: QcContext,
                          blockers: List[str], notes: List[str]) -> CheckResult:
    name = "Independent recomputation"
    tranches = load_universe(ctx.universe_csv_path)
    attachments = [(t.attachment_m, t) for t in tranches if t.attachment_m is not None]
    exhaustions = [(t.exhaustion_m, t) for t in tranches if t.exhaustion_m is not None]

    def matches(pairs, value: float) -> List[Tranche]:
        return [t for v, t in pairs if math.isclose(v, value, abs_tol=0.6)]

    checked = 0
    wrong_field = 0
    for m in MONEY_RE.finditer(text):
        raw = m.group(0)
        value = _money_to_millions(m.group(1), m.group(2))
        window = text[max(0, m.start() - 120):m.start()]

        # Qualitative bands ("above $1bn", "sub-$500m", "$400m+") are not
        # term claims; they are exempt from field matching.
        after = text[m.end():m.end() + 1]
        if QUALIFIER_RE.search(window[-40:]) or after == "+":
            continue

        att_hits = [e.end() for e in ATT_WORDS_RE.finditer(window)]
        exh_hits = [e.end() for e in EXH_WORDS_RE.finditer(window)]
        last_att = max(att_hits) if att_hits else -1
        last_exh = max(exh_hits) if exh_hits else -1
        if last_att > last_exh:
            claimed = "attachment"
        elif last_exh > last_att:
            claimed = "exhaustion"
        else:
            claimed = "unknown"

        att_match = matches(attachments, value)
        exh_match = matches(exhaustions, value)
        checked += 1

        if claimed == "attachment":
            if att_match:
                continue
            if exh_match:
                t = exh_match[0]
                max_att = max(v for v, _ in attachments)
                wrong_field += 1
                blockers.append(
                    f"B2-check2 — wrong-field figure: {raw} claimed as an attachment "
                    f"matches no attachment in the universe; it is the exhaustion of "
                    f"{t.deal} {t.tranche} (CSV exhaustion_usd_m={t.exhaustion_m:g}). "
                    f"Maximum attachment in the universe is {_fmt_m(max_att)}."
                )
            else:
                blockers.append(
                    f"B2-check2 — ungrounded figure: {raw} claimed as an attachment "
                    f"matches no attachment_usd_m in bond-universe.csv."
                )
        elif claimed == "exhaustion":
            if exh_match:
                continue
            if att_match:
                t = att_match[0]
                blockers.append(
                    f"B2-check2 — wrong-field figure: {raw} claimed as exhaustion "
                    f"is the attachment of {t.deal} {t.tranche} "
                    f"(CSV attachment_usd_m={t.attachment_m:g})."
                )
            else:
                blockers.append(
                    f"B2-check2 — ungrounded figure: {raw} claimed as exhaustion "
                    f"matches no exhaustion_usd_m in bond-universe.csv."
                )
        else:  # unknown field: accept if it matches either field
            if att_match or exh_match:
                continue
            blockers.append(
                f"B2-check2 — ungrounded figure: {raw} matches no "
                f"attachment_usd_m or exhaustion_usd_m in bond-universe.csv."
            )

    storm_figs = sorted(
        set(MPH_RE.findall(inputs := _section(text, "inputs"))
            + MB_RE.findall(inputs)),
        key=float,
    )
    detail = (f"{checked} $-figure(s) recomputed against bond-universe.csv; "
              f"{wrong_field} wrong-field; "
              f"storm input figures present ({', '.join(storm_figs) or 'none'}) "
              f"verified under check 4.")
    status = "BLOCKER" if any(b.startswith("B2-check2") for b in blockers) else "PASS"
    return CheckResult(2, name, status, detail)


# ---------------------------------------------------------------------------
# Check 3 — units and dimensions (contract check 3)
# ---------------------------------------------------------------------------

def check_3_units(text: str, ctx: QcContext,
                  blockers: List[str], notes: List[str]) -> CheckResult:
    name = "Units and dimensions"
    problems = 0

    # Saffir-Simpson band checks: pair a "Category N" mention with an mph
    # figure ONLY within the same sentence, so a forward-motion "15 mph"
    # two sentences away is never paired with "Cat 2".
    for sent in _sentences(text):
        cat_m = CAT_RE.search(sent)
        mph_m = MPH_RE.search(sent)
        if cat_m and mph_m:
            cat = int(cat_m.group(1))
            lo, hi = SAFFIR_SIMPSON.get(cat, (0, 0))
            mph_val = float(mph_m.group(1))
            if not (lo <= mph_val <= hi):
                problems += 1
                blockers.append(
                    f"B3-check3 — Saffir-Simpson mismatch: 'Category {cat}' paired with "
                    f"{mph_val:g} mph, outside the Cat {cat} band [{lo}-{hi}] mph."
                )
            mb_m = MB_RE.search(sent)
            if mb_m:
                mb = float(mb_m.group(1))
                plo, phi = MB_PLAUSIBLE.get(cat, MB_PLAUSIBLE[0])
                if not (plo <= mb <= phi):
                    problems += 1
                    blockers.append(
                        f"B3-check3 — implausible central pressure: {mb:g} mb paired with "
                        f"Category {cat} (plausible band {plo}-{phi} mb)."
                    )

    # Same-sentence kt -> mph conversions only (v1 scope: figures drawn
    # from different bullet sources are never spuriously paired).
    for sent in _sentences(text):
        kt_m = KT_RE.search(sent)
        mph_m = MPH_RE.search(sent)
        if kt_m and mph_m:
            expected = float(kt_m.group(1)) * 1.15078
            actual = float(mph_m.group(1))
            if abs(expected - actual) > 3.0:
                problems += 1
                blockers.append(
                    f"B3-check3 — unit conversion error: {kt_m.group(1)} kt = "
                    f"{expected:.1f} mph, but the draft states {actual:g} mph."
                )

    status = "BLOCKER" if problems else "PASS"
    detail = "Saffir-Simpson bands, mb plausibility, and same-sentence kt->mph checked."
    return CheckResult(3, name, status, detail if not problems else f"{detail} {problems} problem(s).")


# ---------------------------------------------------------------------------
# Check 4 — freshness (contract check 4)
# ---------------------------------------------------------------------------

def check_4_freshness(text: str, ctx: QcContext,
                      blockers: List[str], notes: List[str]) -> CheckResult:
    name = "Freshness"
    trigger = _section(text, "trigger")
    inputs = _section(text, "inputs")

    adv_nums = ADVISORY_RE.findall(trigger)
    cited = adv_nums[0] if adv_nums else None
    desc_m = ALERT_DESC_RE.search(trigger)
    cited_desc = _normalise_descriptor(desc_m.group(1)) if desc_m else None

    # Primary wind figure: "max sustained winds X mph", else first mph in Inputs.
    primary = None
    m = re.search(r"max sustained winds?\s+(\d+(?:\.\d+)?)\s*mph", inputs, re.I)
    if m:
        primary = float(m.group(1))
    else:
        m = MPH_RE.search(inputs)
        if m:
            primary = float(m.group(1))

    if cited and ctx.latest_advisory_number:
        parts: List[str] = []
        if _advisory_order(cited) != _advisory_order(ctx.latest_advisory_number):
            older = _advisory_order(cited) < _advisory_order(ctx.latest_advisory_number)
            parts.append(
                f"draft cites Advisory {cited} but the latest published advisory "
                f"at validation time is Advisory {ctx.latest_advisory_number}"
                + (" — the draft is stale" if older
                   else " — the draft is ahead of the injected latest")
            )
        # Internal vintage mismatch: do the draft's figures belong to the
        # advisory it cites, or to an older one?
        if primary is not None and cited in ctx.advisory_vintage:
            cited_winds = ctx.advisory_vintage[cited].get("max_winds_mph")
            if cited_winds is not None and not math.isclose(primary, cited_winds, abs_tol=5):
                older_match = [
                    adv for adv, vals in ctx.advisory_vintage.items()
                    if vals.get("max_winds_mph") is not None
                    and math.isclose(vals["max_winds_mph"], primary, abs_tol=5)
                    and _advisory_order(adv) < _advisory_order(cited)
                ]
                if older_match:
                    old = max(older_match, key=_advisory_order)
                    parts.append(
                        f"the draft's {primary:g} mph figure matches Advisory {old}'s "
                        f"vintage ({ctx.advisory_vintage[old]['max_winds_mph']} mph), "
                        f"not the cited Advisory {cited} ({cited_winds} mph)"
                    )
        if parts:
            blockers.append("B1-check4 — " + "; ".join(parts) + ".")
            return CheckResult(4, name, "BLOCKER",
                               f"Draft cites Advisory {cited}; latest injected is Advisory {ctx.latest_advisory_number}.")
        return CheckResult(4, name, "PASS",
                           f"Draft cites Advisory {cited}; matches latest injected.")

    if cited_desc and ctx.latest_advisory_descriptor:
        want = _normalise_descriptor(ctx.latest_advisory_descriptor)
        if cited_desc == want:
            return CheckResult(4, name, "PASS",
                               f"Draft trigger '{desc_m.group(1)}' matches latest injected advisory.")
        blockers.append(
            f"B1-check4 — stale advisory: draft trigger '{desc_m.group(1)}' does not match "
            f"the latest advisory '{ctx.latest_advisory_descriptor}'."
        )
        return CheckResult(4, name, "BLOCKER", "Trigger descriptor mismatch.")

    notes.append(
        "N-check4 — freshness unverifiable: the trace cites "
        f"{'Advisory ' + cited if cited else 'no advisory number'} but no "
        "matching latest-advisory was injected in ctx; confirm the advisory is current."
    )
    return CheckResult(4, name, "NOTE", "Latest advisory not injected; could not confirm.")


# ---------------------------------------------------------------------------
# Check 5 — falsification present (contract check 5)
# ---------------------------------------------------------------------------

def check_5_falsification(text: str, ctx: QcContext,
                          blockers: List[str], notes: List[str]) -> CheckResult:
    name = "Falsification"
    section = _section(text, "falsification")
    if not section.strip():
        blockers.append("B5-check5 — no Falsification section; hypothesis has no kill conditions.")
        return CheckResult(5, name, "BLOCKER", "Missing Falsification section.")
    bullets = [l for l in section.splitlines()
               if re.match(r"\s*(?:[-*]|\d+[.)])\s+\S", l)]
    if len(bullets) < 2:
        blockers.append(
            f"B5-check5 — Falsification section has {len(bullets)} concrete kill "
            "condition(s); at least 2 required."
        )
        return CheckResult(5, name, "BLOCKER", f"Only {len(bullets)} kill condition(s).")
    vague = [b for b in bullets if len(b.strip()) < 30]
    if vague:
        notes.append(f"N-check5 — {len(vague)} falsification bullet(s) look thin: {vague[0][:70]}")
    return CheckResult(5, name, "NOTE" if vague else "PASS",
                       f"{len(bullets)} kill conditions stated.")


# ---------------------------------------------------------------------------
# Check 6 — language audit (contract check 6)
# ---------------------------------------------------------------------------

_HEDGE_WORDS = ("range", "between", "~", "about", "approximately", "likely", "unlikely",
                "indicative", "order", "sub-", "above", "below", "over", "under",
                "around", "roughly", "floor", "ceiling", "plausible", "hedge")

def check_6_language(text: str, ctx: QcContext,
                     blockers: List[str], notes: List[str]) -> CheckResult:
    name = "Language audit"
    low = text.lower()

    if "indicative" not in low:
        blockers.append("B6-check6 — the word 'indicative' never appears.")

    # "marks" in the pricing sense is banned; the negating disclaimer
    # ("indicative, not marks") is the only allowed occurrence.
    for m in re.finditer(r"marks", text, re.I):
        sent = next((s for s in _sentences(text) if m.group(0) in s), "")
        if re.search(r"\bnot\s+marks\b|\bno\s+marks\b", sent, re.I):
            continue
        blockers.append(
            f"B6-check6 — pricing-sense 'marks' language: {sent.strip()[:110]}"
        )

    # Point estimates: a bare $- or %-figure stated as a CONCLUSION
    # ("losses will reach $500m") without range/hedge. Parenthetical term
    # restatements ("Hestia Re B ($405m att, ...)") and figures carrying an
    # att/exh label or qualifier are not conclusions; the rule stays
    # conservative to avoid false positives.
    hypo = _section(text, "hypothesis")
    conclusion_re = re.compile(
        r"\b(will be|will reach|totals?|equals?|amounts?\s+to|"
        r"expected\s+(?:loss|to be)|is\s+estimated\s+at)\b", re.I)
    for sent in _sentences(hypo):
        if not conclusion_re.search(sent):
            continue
        for m in list(MONEY_RE.finditer(sent)) + list(re.finditer(r"\d+(?:\.\d+)?\s*%", sent)):
            window = sent[max(0, m.start() - 25):m.end() + 25]
            if (QUALIFIER_RE.search(sent[max(0, m.start() - 30):m.start()])
                    or ATT_WORDS_RE.search(window) or EXH_WORDS_RE.search(window)):
                continue
            if any(h in sent.lower() for h in _HEDGE_WORDS):
                continue
            blockers.append(
                f"B6-check6 — point-estimate conclusion without range/hedge: {sent.strip()[:110]}"
            )
            break  # one blocker per sentence is enough

    if not re.search(r"confidence\s*:\s*(low|medium|high)", low):
        blockers.append("B6-check6 — no stated confidence level (expected 'Confidence: LOW/MEDIUM/HIGH').")

    status = "BLOCKER" if any(b.startswith("B6-check6") for b in blockers) else "PASS"
    return CheckResult(6, name, status, "indicative/marks/point-estimate/confidence audit complete.")


# ---------------------------------------------------------------------------
# Check 7 — expert handoff (contract check 7)
# ---------------------------------------------------------------------------

def check_7_handoff(text: str, ctx: QcContext,
                    blockers: List[str], notes: List[str]) -> CheckResult:
    name = "Expert handoff"
    section = _section(text, "where am i wrong")
    if not section.strip():
        blockers.append("B7-check7 — no 'where am I wrong?' section for the expert.")
        return CheckResult(7, name, "BLOCKER", "Missing expert handoff.")
    questions = [l for l in section.splitlines()
                 if re.match(r"\s*(?:[-*]|\d+[.)])\s+\S", l)]
    if len(questions) < 3:
        blockers.append(
            f"B7-check7 — only {len(questions)} 'where am I wrong?' question(s); at least 3 required."
        )
        return CheckResult(7, name, "BLOCKER", f"Only {len(questions)} question(s).")
    boilerplate = sum(1 for q in questions if len(q.strip()) < 40)
    if boilerplate:
        notes.append(f"N-check7 — {boilerplate} question(s) look boilerplate; expert should weigh specificity.")
    return CheckResult(7, name, "NOTE" if boilerplate else "PASS",
                       f"{len(questions)} 'where am I wrong?' questions.")


# ---------------------------------------------------------------------------
# Check 8 — prior grounding (contract check 8)
# ---------------------------------------------------------------------------

_ESTIMATE_WORDS = ("expected", "likely", "unlikely", "estimat", "projection",
                   "prior", "base rate", "historical", "climatolog", "plausible")
_GROUNDING_WORDS = ("historical", "climatolog", "prior", "base rate", "literature",
                    "observed", "reported", "measured", "based on", "according to",
                    "nhc", "artemis", "pcs", "run 00", "per run", "season")
_HEDGE_ONLY = ("likely", "unlikely", "may", "could", "might", "would",
               "expected", "indicative", "approximately", "~", "hedge", "conditional")

def check_8_grounding(text: str, ctx: QcContext,
                      blockers: List[str], notes: List[str]) -> CheckResult:
    name = "Prior grounding"
    body = _section(text, "hypothesis") + "\n" + _section(text, "exposure")
    flagged = 0
    for sent in _sentences(body):
        s = sent.lower()
        if not any(w in s for w in _ESTIMATE_WORDS):
            continue
        grounded = any(w in s for w in _GROUNDING_WORDS)
        # A conditional ("if X, then Y") is not presented as fact.
        hedged = any(w in s for w in _HEDGE_ONLY) or "if " in s
        if grounded:
            continue
        flagged += 1
        if not hedged:
            blockers.append(
                f"B8-check8 — estimate presented as fact with no prior/grounding: {sent.strip()[:110]}"
            )
        else:
            notes.append(
                f"N-check8 — material estimate without cited base rate/prior (flag-note, hedged): {sent.strip()[:110]}"
            )
    status = ("BLOCKER" if any(b.startswith("B8-check8") for b in blockers)
              else "NOTE" if flagged else "PASS")
    return CheckResult(8, name, status,
                       f"{flagged} ungrounded estimate(s) flagged." if flagged else "Estimates grounded or hedged.")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

_CHECK_FNS = [
    check_1_source_resolution,
    check_2_recomputation,
    check_3_units,
    check_4_freshness,
    check_5_falsification,
    check_6_language,
    check_7_handoff,
    check_8_grounding,
]

_CHECK_NAMES = [
    "Source resolution", "Independent recomputation", "Units and dimensions",
    "Freshness", "Falsification", "Language audit", "Expert handoff",
    "Prior grounding",
]


def _run_id_and_storm(trace_path: str):
    p = Path(trace_path)
    m = re.search(r"trace-(\d{8})-(\d+)\.md$", p.name)
    run_id = m.group(2) if m else "???"
    storm = p.parent.name if p.parent.name not in ("", ".") else "unknown"
    return run_id, storm


def review(trace_path: str, ctx: QcContext) -> Verdict:
    """Run all 8 checks on a draft trace. Returns a :class:`Verdict`.

    A single unresolved blocker yields verdict "BLOCKED". Notes never
    block — they go to the expert.
    """
    text = Path(trace_path).read_text(encoding="utf-8")
    run_id, storm = _run_id_and_storm(trace_path)
    blockers: List[str] = []
    notes: List[str] = []
    checks: List[CheckResult] = []
    for i, fn in enumerate(_CHECK_FNS, start=1):
        checks.append(fn(text, ctx, blockers, notes))
    verdict = "BLOCKED" if blockers else "PASS"
    return Verdict(
        trace_path=str(trace_path),
        storm=storm,
        run_id=run_id,
        verdict=verdict,
        checks=checks,
        blockers=list(blockers),
        notes=list(notes),
        validated_at=ctx.now_utc.astimezone(timezone.utc).isoformat(timespec="seconds"),
    )


def write_qc_record(verdict: Verdict, out_path: str) -> str:
    """Write the QC record markdown (shaped like watch/isaias/qc-20261009-004.md)."""
    trace_name = Path(verdict.trace_path).name
    L: List[str] = []
    L.append(f"# QC record — {verdict.storm} watch run {verdict.run_id} ({trace_name})")
    L.append("")
    L.append("*Reviewer: QC agent (mechanical validation only — hypothesis not re-judged).*")
    L.append(f"*Validated: {verdict.validated_at}.*")
    L.append("")
    L.append(f"## Verdict: {verdict.verdict}")
    L.append("")
    L.append("## Per-check results")
    L.append("")
    for c in verdict.checks:
        L.append(f"**{c.number}. {c.name} — {c.status}.** {c.detail}")
        L.append("")
    if verdict.blockers:
        L.append("## Blockers (must fix before publication)")
        L.append("")
        for b in verdict.blockers:
            L.append(f"**{b}**")
            L.append("")
    if verdict.notes:
        L.append("## Notes for the expert")
        L.append("")
        for n in verdict.notes:
            L.append(f"- {n}")
            L.append("")
    L.append("*If this record passed something wrong, that is the reviewer's defect, recorded the same way.*")
    L.append("")
    Path(out_path).write_text("\n".join(L), encoding="utf-8")
    return out_path


def main(argv: Optional[List[str]] = None) -> int:
    """CLI for the heartbeat workflow. Exit 0 = PASS, 2 = BLOCKED, 1 = error."""
    ap = argparse.ArgumentParser(description="FloridaMan QC reviewer gate (checks 1-8).")
    ap.add_argument("--trace", required=True, help="Draft trace markdown to review.")
    ap.add_argument("--universe", required=True, help="bond-universe.csv path.")
    ap.add_argument("--storm", default=None, help="Storm slug (default: parent dir name).")
    ap.add_argument("--latest-advisory", default=None, help="Latest NHC advisory number, e.g. 6.")
    ap.add_argument("--latest-descriptor", default=None, help="Latest advisory descriptor, e.g. '7:20 AM CT alert'.")
    ap.add_argument("--advisory-vintage-json", default=None,
                    help="JSON mapping advisory number -> {max_winds_mph: int}.")
    ap.add_argument("--out", default=None, help="QC record output path (default: qc-<trace-stem>.md next to trace).")
    args = ap.parse_args(argv)

    vintage = {}
    if args.advisory_vintage_json:
        vintage = json.loads(args.advisory_vintage_json)

    ctx = QcContext(
        universe_csv_path=args.universe,
        latest_advisory_number=args.latest_advisory,
        latest_advisory_descriptor=args.latest_descriptor,
        advisory_vintage=vintage,
    )
    try:
        verdict = review(args.trace, ctx)
    except Exception as exc:  # noqa: BLE001 — CLI must report, not traceback
        print(f"QC ERROR: {exc}")
        return 1

    trace_p = Path(args.trace)
    m = re.search(r"trace-(\d{8}-\d+)\.md$", trace_p.name)
    default_out = str(trace_p.parent / f"qc-{m.group(1)}.md") if m else str(trace_p.parent / "qc-record.md")
    out = args.out or default_out
    write_qc_record(verdict, out)
    print(f"QC {verdict.verdict}: {out} ({len(verdict.blockers)} blocker(s), {len(verdict.notes)} note(s))")
    return 0 if verdict.verdict == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
