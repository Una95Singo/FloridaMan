# SPEC Amendment A-003 — v2/R1 direction authorization

**Status:** APPROVED by owner 2026-10-10 ~14:18 EDT.

**Date:** 2026-10-10
**Authorizing decision:** Owner message 2026-10-10 ~14:07 EDT: "Yes authorize
v2 is meant to be a game changer", following delivery of the v2 handoff review
(~14:05 EDT) and confirmed scope of work 2026-10-10 ~14:15 EDT ("Draft the spec
amendment first").
**Supersedes:** The claimed authorization basis of Amendment A-002
("the user's latest instruction in this conversation", dated 9 October 2026).
A-002's *content* is otherwise carried forward; only its basis is replaced by
this explicit decision.

## 1. What changes

**OPN-004 — SUPERSEDED.** The "zero interactive visual surfaces / dashboard
ships = defect" rule is retired. R1 ships an interactive case workspace: the
expert opens on the hypothesis and its evidence, investigates geography,
contract terms and evidence changes, and acts through an authenticated review
rail (approve / correct / challenge / hold). It is an investigation instrument,
not a wall of ungrounded indicators. The first viewport shows the indicative
range, conclusion, horizon and uncertainty — hypothesis before data.

**OPN-003 — EXPANDED, not removed.** The self-hosted rendered case workspace
becomes the primary interface. The public GitHub repo remains the open
evidence mirror and contains approved projections only; drafts, rejected QC
detail, sessions and subscriber addresses stay private. Repo commits alone are
insufficient for nontechnical readers.

**Review surface.** Authenticated phone-capable review (Keycloak OIDC, MFA,
server-managed sessions) supersedes the email-only memo-and-reply loop. Email
is retained for review requests, deadline reminders, hold notices and optional
subscriber notifications — with in-app status as the canonical record.

**Memo export.** Deterministic PDF and Markdown memo generated from the
approved packet; memo, public page and Git record resolve to the same packet
digest. No fresh model rewriting during export.

**Architecture.** Self-hosted modular monolith on owner-controlled Linux
(Caddy, React, FastAPI, PostgreSQL, Keycloak, rootless Podman, local inference
with a separately evaluated model). GitHub Actions/Pages become a public
mirror, not the runtime. Scheduler detects events; every model run requires a
separate operator authorization.

**Build target.** The FloridaMan-V2-Muse-Handoff.zip pack (V2-workflow-1.0,
integrity verified 2026-10-10) is adopted as the build target, executed per
its BUILD_SLICES.md (PR1–PR5) in a test environment. The Astra v1 design pack
is retired as a build target; its 18 acceptance tests and PRD remain reference
material. The Astra v1–v4 roadmap numbering is displaced by the v2 slice plan.

## 2. What is retained (unchanged)

Event-triggered initiation; full traceability; falsifiability; expert
authority (pipeline halts without the expert); QC independence; no autonomous
publication; indicative ranges only, never point estimates; the pricing term
remains excluded from generated analytical outputs; silence is a result;
failure is not silence; no model may infer intact aggregate retention from a
quiet hurricane count; weather and financial outcomes scored separately;
Artemis-derived fields under quarantine until a recorded permission basis
exists; singolab.com is a link-only gateway, never a runtime dependency.

## 3. What this amendment does NOT authorize

Unsupervised model runs. Trading actions, price feeds, portfolio optimization
or portfolio import. New-issue, loss-creep or collateral agents (deferred to
later releases with their own start gates). Any live deploy, real email send
or publication without the owner's explicit sign-off. Backdating approvals or
rewriting history — legacy artifacts are recorded as legacy_unverified until
evidence supports their status.

## 4. Precedence

This amendment > the retained signed SPEC > the v2 pack's derived
implementation decisions. Where the v2 pack's narrative documents conflict
with the retained SPEC, the contradiction is documented and the stricter
publication/data-integrity behavior holds until the owner resolves it.

---
*Owner sign-off: Una — approved in chat 2026-10-10 ~14:18 EDT. Date: 2026-10-10.*
*Committed to the repo alongside SPEC.md; the A-002 record is annotated to
point here as the true authorization basis.*
