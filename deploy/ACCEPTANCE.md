# V2 implementation acceptance record

## Result
Date: 2026-10-10. Base: e7801ad7e4afe29d1fb7c2eeb5d7b0ce726fb60a.
Status: working synthetic vertical slice; not production acceptance.
The delivered patch identifies the exact implementation commit.

## Verified behavior
| Check | Result | Evidence |
|---|---|---|
| Existing QC regression tests | 7 passed | `python -m unittest discover -s tests` |
| API workflow and security tests | 15 passed | `python -m pytest tests/v2 -q` |
| Production frontend build | Passed | `npm --prefix web run build` |
| Desktop and phone user journey | Passed | `scripts/browser-check.cjs`; 1440×1000 and 390×844 |
| Approval, correction, replacement and release | Passed in synthetic mode | Actual FastAPI server and SQLite; no browser-only state simulation |
| Private draft, CSRF, assigned expert, recent authentication | Passed | Direct API tests |
| Expired review and changed source | Release rejected | Direct API tests |
| Repeated release request | Same release returned | API idempotency test |
| PDF and Markdown | Approved digest retained; PDF text selectable | API test and real browser download |
| WebGL unavailable | Geographic SVG fallback works | Browser screenshots; actual Natural Earth coordinates |

Browser: headless Chromium 133, Playwright, Linux. The browser had no usable WebGL context.
The native MapLibre path was built but not visually validated with a working GPU.
Two dependency deprecation warnings remain. Vite reports a large map bundle.
CI is supplied but has not run on GitHub because the integration rejected branch creation.

## Visual scope
The build follows the approved deep-blue geographic surface, ivory reading panel, serif headings and restrained teal actions.
The phone starts with one summary and one primary action. Details expand after an explicit action.
Coastal bands are decorative styling. They do not encode bathymetry, hazard intensity or insured exposure.
The forecast geometry and contracts are labelled synthetic. Geographic land data is real and separately attributed.

## Handoff traceability
These statuses describe partial implementation; they do not close the parent requirements.

| Handoff scope | Implementation | Remaining acceptance |
|---|---|---|
| PR1 / WF-01, WF-13 | Persistent case state; server permissions; operated replay; immutable packet identity | Real OIDC/MFA, pinned universe integration, deployed PostgreSQL concurrency, model authorization queue |
| PR2 / WF-02, WF-03, WF-10, WF-11 | Map-first case, phone disclosure, sources and unknown-data treatment | Structured copy contract integration, multiple-case navigation, supported financial ranges |
| PR3 / WF-04–06 | Correction/challenge, replay, digest-bound approval, stale-version and deadline holds | Actual model/QC workers, source polling integration, operation-status recovery after a timeout |
| PR4 / WF-07, WF-08, WF-12 | Separate synthetic release; consistent packet, Markdown and selectable PDF | Sanitized live projection, Git mirror, durable outbox, subscriptions and partial-publication recovery |
| PR5 / WF-09, WF-14 | Automated regression evidence and actual screen captures | Outcome scoring, deployed-stack exercise, complete SDLC ledger and user comprehension study |
| VG-01 | Map-first responsive composition verified at 390 and 1440 pixels | 360- and 768-pixel reference checks |
| VG-02 | Claim/source navigation and source vintage implemented | Exact return-scroll preservation |
| VG-03 | Unknown losses show no numeric scale or fabricated range | Verified live exposure integration |
| VG-04 | Acknowledgement plus server permission/version/deadline gates tested | Deployed identity-provider acceptance |
| VG-05 | Memo derives from approved packet | Geographic figure in PDF; full visual export acceptance |
| VG-06 | Semantic controls and visible focus styles present | 200% text, screen-reader and contrast audit |
| VG-07 | WebGL fallback demonstrated; map failure does not remove review panel | Failed source retry control and full network-failure acceptance |
| VG-08 | Actual screenshots supplied with the package | GitHub PR blocked by connector permissions |

## Security and deployment boundaries
- Demo identity is available only in explicit demo mode and through a loopback connection.
- Production sign-in uses the OIDC integration; its real Keycloak flow has not been exercised.
- Production model execution and release return 503 until live adapters exist.
- Packet and audit immutability is application-enforced. Database administrators can alter storage. No external tamper-evident anchor is claimed.
- The structural validator does not prove numerical or semantic correctness. Independent analytical QC remains required.
- The private importer is a privileged operator CLI. It trusts the supplied independent QC attestation; it does not cryptographically authenticate that attestation.
- The current UI centers on one active case. Do not import multiple concurrent cases for operational use.
- Deadline rejection is enforced on reads and decisions. There is no background reminder worker.
- Production review-window scheduling and decision-horizon integration remain to be completed; imported packets currently use a maximum twelve-hour deadline.
- Container startup, PostgreSQL races, migrations, backup recovery and OIDC/MFA have not been tested on a self-hosted deployment.
- No email, live financial analysis, public Git release or deployment occurred.

## Apply and continue
Use the patch in the delivery package against the recorded base, or run the complete source tree directly.
Run `scripts/run-demo.sh` from the repository root. Do not expose the loopback demo publicly.
Before live operation, finish the remaining acceptance items and obtain the deployment/publication sign-off required by SPEC Amendment A-003.
