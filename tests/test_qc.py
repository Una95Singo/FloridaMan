"""Acceptance and unit tests for floridaman.qc (stdlib unittest only).

Fixtures are the real watch traces from
``~/workspace/github-finish/floridaman/watch/isaias/``, copied to a
temporary directory (never mutated in place). Bond ground truth is the
real committed ``bond-universe.csv`` — no invented bond data.

The mandatory test is ``test_run001_blocked_with_both_defects``: the
real QC review BLOCKED trace-20261008-001.md for exactly two defects
(stale advisory vintage + wrong-field attachment figure), and the
checker must reproduce both from the trace text + injected context —
no special-casing of the fixture.
"""

import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from floridaman.qc import QcContext, review, write_qc_record

SOURCE_REPO = Path.home() / "workspace/github-finish/floridaman"
UNIVERSE = str(SOURCE_REPO / "bond-universe.csv")
FIXTURE_001 = SOURCE_REPO / "watch/isaias/trace-20261008-001.md"
FIXTURE_004 = SOURCE_REPO / "watch/isaias/trace-20261009-004.md"

FIXED_NOW = datetime(2026, 10, 9, 12, 35, tzinfo=timezone.utc)


def stub_fetch(url: str):
    """Deterministic stand-in for live page fetches."""
    return "<html><body>stub page</body></html>"


def ctx_001():
    """Context reproducing the real run-001 validation moment.

    Advisory 6 (70 mph) was the latest published; the trace cites
    Advisory 5A but its 45 mph figure belongs to Advisory 4.
    """
    return QcContext(
        universe_csv_path=UNIVERSE,
        latest_advisory_number="6",
        advisory_vintage={
            "4": {"max_winds_mph": 45},
            "5A": {"max_winds_mph": 65},
            "6": {"max_winds_mph": 70},
        },
        fetch=stub_fetch,
        now_utc=FIXED_NOW,
    )


def ctx_004():
    """Context for the passing fixture: the draft's own trigger is latest."""
    return QcContext(
        universe_csv_path=UNIVERSE,
        latest_advisory_number=None,
        latest_advisory_descriptor="7:20 AM CT alert",
        advisory_vintage={"10": {"max_winds_mph": 105}},
        fetch=stub_fetch,
        now_utc=FIXED_NOW,
    )


def _good_trace() -> str:
    """Minimal synthetic trace that should PASS every check."""
    return """# Watch trace — Test Storm — run 099

*Draft. Not published. Awaiting QC review and expert review.*

## Trigger

TRG-001: NHC Advisory 6 (10:00 PM CDT) — material intensification.

## Inputs and sources

- NHC Advisory 6 via example tracker (accessed Oct 9, 2026): max sustained
  winds 70 mph, moving north 10 mph. Source: https://example.com/advisory-6
- Bond universe: `bond-universe.csv` (10 deals, 26 tranches).

## Exposure mapping

Hestia Re 2025-1 B (Kin; FL named storm; per-occurrence; att $405m /
exh $605m): in the footprint.

## Hypothesis (indicative, not marks)

If the forecast verifies, no attachment is likely threatened. The most
sensitive position is Hestia Re B ($405m att, per-occurrence, FL).

Confidence: MEDIUM. Track confidence is high; intensity is the uncertainty.

## Falsification conditions

- Landfall at Cat 3+ → re-examine Hestia Re B against damage reports.
- Landfall below Cat 1 → "no attachment threat" confirmed.

## Where am I wrong? (for the expert)

1. Is the Hestia Re B sensitivity ranking right given Kin's book concentration?
2. Should Bayou Re move up if the track shifts 50 km west?
3. Is the aggregate-erosion read too generous given the quiet season?
"""


class TestAcceptanceFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="floridaman-qc-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _copy(self, fixture: Path) -> str:
        dest = str(Path(self.tmp) / fixture.name)
        shutil.copy2(fixture, dest)
        return dest

    def test_run001_blocked_with_both_defects(self):
        """MANDATORY: run 001 must BLOCK on both historical defects.

        (a) STALE ADVISORY VINTAGE — cites Advisory 5A, uses Advisory 4's
        45 mph figure, while Advisory 6 is latest.
        (b) WRONG-FIELD FIGURE — $15.309bn listed as an attachment; it is
        the Everglades Re II 2024-1 A exhaustion (attachment is $13.309bn).
        """
        trace = self._copy(FIXTURE_001)
        verdict = review(trace, ctx_001())

        self.assertEqual(verdict.verdict, "BLOCKED")
        self.assertEqual(len(verdict.blockers), 2,
                         f"expected exactly 2 blockers, got: {verdict.blockers}")
        blockers_text = "\n".join(verdict.blockers)

        # Defect (a): stale advisory.
        self.assertTrue("Advisory 6" in blockers_text or "stale" in blockers_text,
                        f"stale-advisory signature missing:\n{blockers_text}")
        # Defect (b): wrong-field figure.
        self.assertTrue("15.309" in blockers_text or "exhaustion" in blockers_text,
                        f"wrong-field signature missing:\n{blockers_text}")

        # The record must carry both too.
        record_path = str(Path(self.tmp) / "qc-20261008-001.md")
        write_qc_record(verdict, record_path)
        record = Path(record_path).read_text(encoding="utf-8")
        self.assertIn("## Verdict: BLOCKED", record)
        self.assertIn("## Per-check results", record)
        self.assertIn("## Blockers (must fix before publication)", record)
        self.assertIn("4. Freshness — BLOCKER", record)
        self.assertIn("2. Independent recomputation — BLOCKER", record)

    def test_run004_passes(self):
        """The corrected run-004 draft must PASS with its own advisory latest."""
        trace = self._copy(FIXTURE_004)
        verdict = review(trace, ctx_004())

        self.assertEqual(verdict.verdict, "PASS",
                         f"expected PASS, got blockers: {verdict.blockers}")
        self.assertEqual(verdict.blockers, [])
        record_path = str(Path(self.tmp) / "qc-20261009-004.md")
        write_qc_record(verdict, record_path)
        record = Path(record_path).read_text(encoding="utf-8")
        self.assertIn("## Verdict: PASS", record)
        for n in range(1, 9):
            self.assertIn(f"**{n}. ", record)


class TestCheckSemantics(unittest.TestCase):
    def _review_synthetic(self, trace_text: str, **ctx_kw) -> object:
        tmp = tempfile.mkdtemp(prefix="floridaman-qc-syn-")
        self.addCleanup(shutil.rmtree, tmp, True)
        trace = str(Path(tmp) / "trace-20261009-099.md")
        Path(trace).write_text(trace_text, encoding="utf-8")
        ctx_kw_final = dict(
            universe_csv_path=UNIVERSE,
            latest_advisory_number="6",
            advisory_vintage={"6": {"max_winds_mph": 70}},
            fetch=stub_fetch,
            now_utc=FIXED_NOW,
        )
        ctx_kw_final.update(ctx_kw)
        ctx = QcContext(**ctx_kw_final)
        return review(trace, ctx)

    def test_clean_synthetic_passes(self):
        verdict = self._review_synthetic(_good_trace())
        self.assertEqual(verdict.verdict, "PASS",
                         f"expected PASS, got: {verdict.blockers}")

    def test_saffir_simpson_mismatch_blocks(self):
        trace = _good_trace().replace(
            "winds 70 mph",
            "winds 140 mph (Category 2)")
        verdict = self._review_synthetic(
            trace, advisory_vintage={"6": {"max_winds_mph": 140}})
        self.assertEqual(verdict.verdict, "BLOCKED")
        self.assertTrue(any("Saffir-Simpson" in b for b in verdict.blockers),
                        f"Saffir-Simpson signature missing: {verdict.blockers}")

    def test_pricing_marks_language_blocks(self):
        trace = _good_trace().replace(
            "## Hypothesis (indicative, not marks)",
            "## Hypothesis\n\nSecondary marks suggest 82 cents on the dollar.")
        verdict = self._review_synthetic(trace)
        self.assertEqual(verdict.verdict, "BLOCKED")
        self.assertTrue(any("marks" in b for b in verdict.blockers),
                        f"marks signature missing: {verdict.blockers}")

    def test_missing_falsification_blocks(self):
        trace = _good_trace().replace("## Falsification conditions", "## Outlook")
        verdict = self._review_synthetic(trace)
        self.assertEqual(verdict.verdict, "BLOCKED")
        self.assertTrue(any("Falsification" in b for b in verdict.blockers),
                        f"falsification signature missing: {verdict.blockers}")

    def test_stale_cited_advisory_blocks(self):
        trace = _good_trace().replace("NHC Advisory 6", "NHC Advisory 4")
        verdict = self._review_synthetic(trace)
        self.assertEqual(verdict.verdict, "BLOCKED")
        self.assertTrue(any("stale" in b or "Advisory 6" in b for b in verdict.blockers),
                        f"staleness signature missing: {verdict.blockers}")


if __name__ == "__main__":
    unittest.main()
