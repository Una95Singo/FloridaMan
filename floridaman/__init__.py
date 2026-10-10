"""FloridaMan pipeline core — the working ingest/trigger/draft half of v1.

Implements the trigger and draft stages of the storm-watch agent contract
(``agents-storm-watch-agent.md``):

- ``ingest``    — "Inputs": live NHC public advisory data (SPEC TRC-003).
- ``triggers``  — "Triggers": material-change detection, TRG-001..TRG-005.
- ``draft``     — "Output contract" (draft half): builds the trace markdown
                  shaped exactly like ``watch/<storm>/trace-*.md``.
- ``run``       — CLI entry point (ARC-002: operated, human-supervised runs).

The second half of v1 — QC validation, the expert gate, and publishing —
is implemented in this package by the pipeline-gate builder:

- ``qc``        — the 8 mechanical checks from ``agents-qc-reviewer-agent.md``
                  as executable code; emits the QC record and a PASS/BLOCKED
                  verdict. Nothing publishes without it.
- ``gate``      — the expert gate: on QC PASS, opens a GitHub issue with the
                  hypothesis + "where am I wrong?" questions and pauses for
                  the human expert's approve/correct.
- ``publish``   — commits an approved trace + QC record into
                  ``watch/<storm>/`` via git (push left to the operator).

Stdlib only. No secrets, tokens, or credentials anywhere in this package.
"""

__all__ = ["ingest", "triggers", "draft", "run", "qc", "gate", "publish"]
