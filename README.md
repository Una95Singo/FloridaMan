# FloridaMan

A map-led workspace for expert review of hurricane-linked catastrophe-bond hypotheses.
The interface follows SPEC_AMENDMENT_A003.md. A geographic view leads into evidence, correction, exact-version approval and a readable memo.

## Run the V2 workflow

Prerequisites: Python 3.12+, Node 22 and npm.

```sh
./scripts/run-demo.sh
```

Open http://127.0.0.1:8000 and select **Open demo workspace**.
This is an isolated synthetic replay. It uses a real API and persistent database. It sends no email and publishes nothing to GitHub.

1. Inspect a claim and its pinned source.
2. Correct or challenge the claim. Record the reason.
3. Authorize a replacement replay. The original deadline remains in effect.
4. Review and approve the exact replacement version.
5. Release that version as the operator. Download its PDF or Markdown memo.

## What is implemented

- Responsive React interface with MapLibre geography and an SVG fallback from the same Natural Earth data.
- Mobile disclosure, evidence comparison, correction forms and decision history.
- FastAPI with SQLAlchemy persistence; SQLite for the local replay, PostgreSQL for the deployment configuration.
- Server-side roles, sessions, CSRF checks, stale-version rejection, deadline holds and digest-bound approval.
- The contract review deadline (next 09:00/21:00 UTC window, first request plus twelve hours, or decision horizon) and an operation lookup so a reviewer can recover a decision after a network timeout without recording it twice.
- A separate release action and memo exports generated from the released packet.
- An OIDC integration and an operated private-packet importer. These require deployment validation.

## What is not ready for live operation

The local replay is working. Live analytical runs, independent semantic QC, delivery subscriptions, public Git/email distribution and hypothesis scoring are not implemented in V2.
The structural checks in `server/domain.py` do not establish the truth of an analytical claim.
The production API blocks model execution and publication until those integrations exist.
Container orchestration, real OIDC/MFA, PostgreSQL concurrency and backup recovery require deployment tests.
No deployment or live distribution is authorized by this branch.

Read [operations](deploy/OPERATIONS.md) for setup and [acceptance status](deploy/ACCEPTANCE.md) for tested scope and remaining work.

## Code layout

| Path | Purpose |
|---|---|
| `web/` | Map, review and memo UI |
| `server/` | Persistent workflow, identity integration, private import and export API |
| `scripts/` | Local launch and real-browser verification |
| `tests/v2/` | Workflow and authorization tests |
| `compose.yaml` | Self-hosted application, database and reverse proxy |
| `floridaman/` | Legacy v1 pipeline, including its explicit reasoner stub |
| `site/`, `watch/` | Existing static surface and historical records |

The old scheduled workflow no longer opens public issues containing drafts. Its replacement checks NHC feed availability only. A source outage fails the job; it is not reported as analytical silence.

## Verify

```sh
pip install -r requirements-test.txt
python -m unittest discover -s tests
python -m pytest tests/v2 -q
npm --prefix web ci
npm --prefix web run build
```

For browser checks, see [operations](deploy/OPERATIONS.md). CI runs the server tests, frontend build and full browser replay.
