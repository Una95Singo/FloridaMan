# FloridaMan v1 — Scoping Specification

*Draft. Requires owner sign-off before build (see §8).*
*Companion documents: `DESIGN_THESIS.md` (the why), `agents/storm-watch-agent.md`
(the how, agent 1 of 2).*

## 1. Intent

v1 exists to prove — against a real storm happening right now — that the ILS
hurricane-watch workflow can be done differently: not a dashboard a human
opens, but an event-triggered agent that does the analytical legwork with a
fully traceable trail, arrives with a falsifiable hypothesis about the
"so what," and submits itself to a senior expert's judgment. The proof is
public, timestamped, and scored against reality after the event. If v1 does
not demonstrate all four principles (trigger, traceability, hypothesis,
expert-in-the-loop) on Tropical Storm Isaias, v1 has failed.

Out of scope for this document: whether the thesis is right. That is what v1
is for.

## 2. Scope boundary

**In:** one storm (Isaias), one agent pair (storm-watch + QC reviewer),
one curated bond sample, public markdown traces and hypotheses, one
post-event scorecard.

**Out:** everything else. The won't-have list in §4 is binding, not
aspirational. v2+ agents (first-read, creep, collateral, mark-validation)
do not get designed, scaffolded, or "prepared for" in v1. No hooks, no
placeholders, no "we'll figure it out in build."

**Timebox:** Isaias made landfall ~Oct 9, 2026. v1's live window is days,
not weeks. Anything that cannot ship inside that window is cut.

## 3. Requirements (EARS style)

One SHALL per requirement. Uppercase SHALL is binding; SHOULD is
recommended; MAY is permitted. Requirements are grouped by concern.

### Triggers (TRG)

- **TRG-001:** WHEN the NHC names, upgrades, or downgrades a watched tropical
  cyclone, the storm-watch agent SHALL run an exposure analysis.
- **TRG-002:** WHEN a new NHC advisory changes forecast category (≥1) or
  landfall track (≥100 km), the storm-watch agent SHALL run an exposure
  analysis.
- **TRG-003:** WHEN landfall occurs or the storm dissipates, the storm-watch
  agent SHALL publish a final hypothesis and close the watch.
- **TRG-004:** The storm-watch agent SHALL evaluate triggers on a heartbeat
  of at most 12 hours while a storm is watched.
- **TRG-005:** WHEN the heartbeat finds no trigger fired, the agent SHALL
  publish nothing. Silence is correct behavior, and the heartbeat log SHALL
  record "no trigger, no output."

### Traceability (TRC)

- **TRC-001:** Every factual claim in a published trace SHALL link to its
  source (URL or named dataset + access date).
- **TRC-002:** Every number in a published trace SHALL show its derivation or
  be labeled an estimate with the estimation method stated.
- **TRC-003:** Every published hypothesis SHALL cite the NHC advisory number
  and timestamp it was computed from.
- **TRC-004:** The QC reviewer agent SHALL independently recompute 100% of
  numbers before a hypothesis publishes; any unreproducible number SHALL
  block publication.

### Hypothesis (HYP)

- **HYP-001:** Every published hypothesis SHALL state its conclusion as a
  range, never a point estimate, and SHALL be labeled "indicative."
- **HYP-002:** Every published hypothesis SHALL include explicit falsification
  conditions: what would prove it wrong, what to watch, by when.
- **HYP-003:** Every published hypothesis SHALL end with the specific
  questions the senior expert should challenge ("where am I wrong?").
- **HYP-004:** Every published hypothesis SHALL carry a confidence level and
  the key uncertainties behind it.
- **HYP-005:** The word "marks," or any presentation of secondary-market
  pricing, SHALL NOT appear in v1 outputs. Indicative ranges only.

### Expert loop (EXP)

- **EXP-001:** No hypothesis SHALL publish without senior-expert review.
- **EXP-002:** Every expert correction SHALL be recorded in the trace with
  what changed, why, and who made it.
- **EXP-003:** Corrections SHALL be carried forward as persistent agent
  context for subsequent runs of the same storm.

### Openness (OPN)

- **OPN-001:** The storm-watch agent definition SHALL live in `agents/` in
  the public repo, licensed for reuse.
- **OPN-002:** The QC reviewer agent definition SHALL live in `agents/` in
  the public repo, licensed for reuse.
- **OPN-003:** Every trace and hypothesis SHALL be committed to
  `watch/isaias/` in the public repo, inspectable by anyone without
  credentials.
- **OPN-004:** v1 SHALL ship zero interactive visual surfaces. The only
  rendered artifacts are markdown traces, hypotheses, and the scorecard.
  Anything resembling a dashboard is a defect.

### Scoring and calibration (SCR)

- **SCR-001:** Within 72 hours of storm dissipation, the agent SHALL publish
  a scorecard comparing each timestamped hypothesis against actual outcomes:
  what was right, what was wrong, and what the next version should do
  differently.
- **SCR-002:** The scorecard SHALL distinguish hypothesis errors (expected,
  scored) from mechanical errors (calculation, sourcing, staleness — target
  zero, each one recorded as a defect with a fix).
- **SCR-003:** Confidence levels SHALL be recorded alongside outcomes so
  calibration can be measured as the sample grows.

### Architecture (ARC)

- **ARC-001:** FloridaMan SHALL operate independently of singolab.com: own
  repo, own artifacts, no runtime dependency on the gateway.
- **ARC-002:** v1 runs SHALL be operated (scheduled human-supervised runs of
  the open-source agent definitions), not autonomous. Full autonomy is
  explicitly not claimed in v1.

## 4. MoSCoW

**Must-have (v1 ships iff all of these hold):**
- Storm-watch agent definition in `agents/` (exists; frozen for v1)
- QC reviewer agent definition in `agents/` + validation gate in the
  pipeline (draft → validate → expert → publish)
- Curated bond universe: ≥8 real outstanding US hurricane-exposed cat bonds,
  schema-defined (sponsor, size, trigger type, attachment/exhaustion,
  expected loss, coupon, maturity, covered area), sourced from the Artemis
  public directory, committed to the repo
- Live Isaias watch: traces + hypotheses in `watch/isaias/`, all
  requirements in §3 satisfied
- Design thesis in repo (exists)
- Post-event scorecard per SCR-001

**Should-have:**
- singolab.com gateway link to the live watch/trace
- Calibration log seeded from the Isaias runs (thin with n=1 storm, but the
  mechanism exists)

**Could-have:**
- Standalone deployment home for the trace (repo-as-home suffices for v1)
- README/CONTRIBUTING polish

**Won't-have (v1) — binding:**
- Any dashboard, cockpit, or interactive visual surface
- New-issue screener, loss-creep, collateral, or mark-validation agents
- Secondary-market pricing or dealer marks in any output
- Full Artemis directory ingestion or scraper
- Model-version change impact analysis
- Autonomous unsupervised operation

## 5. Acceptance criteria (measurable)

v1 is accepted iff, verified by inspection of the repo:

1. `watch/isaias/` contains ≥1 trace per NHC trigger event in §TRG and a
   `latest.md` hypothesis, all committed while the storm was active.
2. 100% of published hypotheses contain: source-linked claims (TRC-001),
   derived-or-labeled numbers (TRC-002), advisory citation (TRC-003),
   range-not-point conclusions labeled indicative (HYP-001), falsification
   conditions (HYP-002), "where am I wrong?" questions (HYP-003), and
   confidence + uncertainties (HYP-004).
3. 100% of published hypotheses have an attached QC validation record
   showing independent recomputation of all numbers (TRC-004); zero
   hypotheses published with unresolved QC flags.
4. 100% of expert corrections appear in traces per EXP-002.
5. Heartbeat log shows ≥1 "no trigger, no output" entry (TRG-005) — silence
   demonstrated, not just claimed.
6. Post-event scorecard published within 72h of dissipation per SCR-001,
   with the error-type split per SCR-002.
7. Repo contains zero interactive visual surfaces (OPN-004).
8. The word "marks" (in the pricing sense) appears in zero published
   outputs (HYP-005).
9. All v1 hypotheses were timestamped before the outcomes they predict
   were known (verifiable from commit timestamps vs. event timeline).

## 6. Assumptions

- A1: NHC public advisory data remains accessible for the storm's duration.
- A2: The Artemis public deal directory remains accessible for universe
  curation.
- A3: The owner is available as the senior expert reviewer on roughly a
  12-hour cadence during the watch. If A3 fails, the pipeline halts at the
  expert gate rather than publishing unreviewed — this is by design
  (EXP-001), not a failure mode to work around.
- A4: A curated sample of ≥8 bonds is sufficient to demonstrate the
  workflow; full-universe coverage is not needed to prove the thesis.

## 7. Open questions (decisions needed, not deferred to build)

- OQ-1: Bond universe selection — owner confirms the ≥8 bonds, or delegates
  selection criteria (proposal: largest/most representative US
  wind-exposed 144A bonds outstanding per Artemis). Owner: Una. Needed
  before first live run.
- OQ-2: singolab.com gateway link copy and placement. Owner: Una.
  Should-have; may ship after v1 acceptance.
- OQ-3: This spec itself — owner sign-off per §8.

## 8. Sign-off

Build SHALL NOT begin until the owner signs off on this spec. Sign-off
covers scope (§2), the binding requirements (§3), and the won't-have list
(§4). Changes after sign-off go through a spec amendment, not hallway
decisions.

Owner sign-off: Una Singo (via chat) Date: 2026-10-08

Decisions at sign-off: (1) bond universe selection DELEGATED — curator picks the largest/most representative US wind-exposed 144A bonds from Artemis; (2) singolab.com gateway link DEFERRED — ships after v1 acceptance; (3) scope, requirements (§3), and won't-have list (§4) APPROVED as written.
