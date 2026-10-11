# V2 implementation acceptance record

## Result
Date: 2026-10-11. Base: e7801ad7e4afe29d1fb7c2eeb5d7b0ce726fb60a. Branch: codex/v2-map-workflow.
Status: working synthetic vertical slice; not production acceptance.
The handoff patch (original commit 7e9965584ed216d5fe6571f1b5252e376e07439d) was re-applied with `git am`
and verified again in a fresh environment. Two defects found during that verification are fixed on this branch.

## Verified behavior (current branch, 2026-10-11)
| Check | Result | Evidence |
|---|---|---|
| Existing QC regression tests | 7 passed | `python -m unittest discover -s tests` |
| API workflow, security and deadline tests | 27 passed | `python -m pytest tests/v2 -q` |
| Production frontend build | Passed | `npm --prefix web run build` (Vite 6, one large-chunk warning) |
| Desktop and phone user journey | Passed, 3 consecutive runs | `scripts/check-browser.sh`; 1440×1000 and 390×844 |
| No horizontal overflow at reference widths | Passed | 360×740, 768×1024, 1440×900 and 390×844; `test-evidence/watch-*.png` |
| Approval, correction, replacement and release | Passed in synthetic mode | Real FastAPI server and SQLite; no browser-only state simulation |
| Private draft, CSRF, assigned expert, recent authentication | Passed | Direct API tests |
| Expired review and changed source | Release rejected | Direct API tests |
| Repeated release request | Same release returned | API idempotency test |
| Operation recovery after an interrupted response | Passed | Browser check aborts the approval response after the server processed it; the client recovers the result by idempotency key; the audit holds exactly one approval |
| Operation lookup is private and actor-scoped | Passed | API tests: 401 without a session, 404 for another subject's key |
| Review deadline rule | Passed | `tests/v2/test_deadline.py`: next 09:00/21:00 UTC window, first request plus 12 hours, or decision horizon, whichever is earliest |
| PDF and Markdown | Approved digest retained; PDF text selectable | API test and real browser download |
| Native MapLibre (WebGL) map | Rendered and captured | `browser-results.json` records `map_path: maplibre-webgl`; Chromium 141 headless with SwiftShader |
| WebGL unavailable | Geographic SVG fallback works | Demonstrated in the original handoff environment (Chromium 133, no WebGL); not re-captured here |

Environment: Python 3.13, Node 22, Playwright 1.56.1, headless Chromium 141, Linux container.
Two dependency deprecation warnings remain (authlib httpx). Vite reports a large map bundle.

## Defects fixed during verification
| Defect | Effect | Fix |
|---|---|---|
| Navigation race after an action | The post-action refresh forced the view back to the review panel and undid a navigation the reviewer made while the request was pending | Navigate first, then refresh (`web/src/main.jsx`) |
| Map crash on packet version change | `Style is not done loading` thrown when the layer-visibility effect ran against a freshly recreated map; React unmounted the whole page | Guard the effect on the layer's existence (`web/src/StormMap.jsx`) |
| Browser check port reuse | Back-to-back runs probed a server that was still shutting down and then failed with connection refused | Launcher waits for a free port and verifies its own server process (`scripts/check-browser.sh`) |

## Added on this branch beyond the handoff
- `GET /api/cases/{id}/operations/{key}`: a signed-in actor can recover the saved result of their own mutation after a network timeout. The UI reuses the idempotency key for a retry of the same payload.
- `server.domain.review_deadline`: the contract deadline rule. Used by the operated importer for new cases and by `reopen` outside demo mode. The demo keeps a two-hour deadline so a replay can be exercised in one sitting.
- Operator-only controls (replacement run, release, fresh cycle) render only for a session with the operator role. The server enforced this already; the interface now matches.
- Browser evidence records the browser version, the geography path that rendered (`maplibre-webgl` or `svg-fallback`) and the viewports checked.

## Visual scope
The build follows the approved deep-blue geographic surface, ivory reading panel, serif headings and restrained teal actions.
The phone starts with one summary and one primary action. Details expand after an explicit action.
Coastal bands are decorative styling. They do not encode bathymetry, hazard intensity or insured exposure.
The forecast geometry and contracts are labelled synthetic. Geographic land data is real and separately attributed.

## Handoff traceability
These statuses describe partial implementation; they do not close the parent requirements.

| Handoff scope | Implementation | Remaining acceptance |
|---|---|---|
| PR1 / WF-01, WF-13 | Persistent case state; server permissions; operated replay; immutable packet identity; contract deadline rule | Real OIDC/MFA, pinned universe integration, deployed PostgreSQL concurrency, model authorization queue |
| PR2 / WF-02, WF-03, WF-10, WF-11 | Map-first case, phone disclosure, sources and unknown-data treatment | Structured copy contract integration, multiple-case navigation, supported financial ranges |
| PR3 / WF-04–06 | Correction/challenge, replay, digest-bound approval, stale-version and deadline holds, operation recovery after a timeout | Actual model/QC workers, source polling integration |
| PR4 / WF-07, WF-08, WF-12 | Separate synthetic release; consistent packet, Markdown and selectable PDF | Sanitized live projection, Git mirror, durable outbox, subscriptions and partial-publication recovery |
| PR5 / WF-09, WF-14 | Automated regression evidence and actual screen captures | Outcome scoring, deployed-stack exercise, complete SDLC ledger and user comprehension study |
| VG-01 | Map-first responsive composition verified at 360, 390, 768 and 1440 pixels without horizontal overflow | 200% text and keyboard walkthrough |
| VG-02 | Claim/source navigation and source vintage implemented | Exact return-scroll preservation |
| VG-03 | Unknown losses show no numeric scale or fabricated range | Verified live exposure integration |
| VG-04 | Acknowledgement plus server permission/version/deadline gates tested; operator controls role-scoped | Deployed identity-provider acceptance |
| VG-05 | Memo derives from approved packet | Geographic figure in PDF; full visual export acceptance |
| VG-06 | Semantic controls and visible focus styles present | 200% text, screen-reader and contrast audit |
| VG-07 | WebGL path captured here; fallback captured in the handoff environment; map failure does not remove review panel | Failed source retry control and full network-failure acceptance |
| VG-08 | Actual screenshots regenerated on this branch | Reviewer sign-off |

## Security and deployment boundaries
- Demo identity is available only in explicit demo mode and through a loopback connection.
- Production sign-in uses the OIDC integration; its real Keycloak flow has not been exercised.
- Production model execution and release return 503 until live adapters exist.
- Packet and audit immutability is application-enforced. Database administrators can alter storage. No external tamper-evident anchor is claimed.
- The structural validator does not prove numerical or semantic correctness. Independent analytical QC remains required.
- The private importer is a privileged operator CLI. It trusts the supplied independent QC attestation; it does not cryptographically authenticate that attestation.
- The current UI centers on one active case. Do not import multiple concurrent cases for operational use.
- Deadline rejection is enforced on reads and decisions. There is no background reminder worker.
- The deadline rule is implemented; the decision horizon is read from an optional `decision_horizon` packet field, which the fixtures do not set.
- Container startup, PostgreSQL races, migrations, backup recovery and OIDC/MFA have not been tested on a self-hosted deployment.
- No email, live financial analysis, public Git release or deployment occurred.

## Apply and continue
Run `scripts/run-demo.sh` from the repository root. Do not expose the loopback demo publicly.
Before live operation, finish the remaining acceptance items and obtain the deployment/publication sign-off required by SPEC Amendment A-003.
