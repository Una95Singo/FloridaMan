# FloridaMan V2: run and review

## Current delivery boundary
The app implements the complete synthetic review journey with real persistence and real exports.
It is not yet a live autonomous analyst. Live model execution and public Git/email delivery remain disabled.
The source packet importer provides an operated integration seam; it does not invent verified source data.
The existing public website and historical watch files are unchanged by this branch.

## Run the working demo
Prerequisites: Python 3.12+, Node 22+, npm. From the repository root:

    ./scripts/run-demo.sh

Open http://127.0.0.1:8000. Select Open demo workspace.
Inspect evidence, save a correction, authorize the replay, acknowledge the replacement, approve, then release it.
Open Archive to download its PDF and Markdown memo. Reload to verify saved state.
The synthetic identity is enabled only in explicit demo mode and accepts sign-in only from loopback.
Never expose this demo process on a public interface. No real email or Git publication occurs in demo mode.

## Operated deployment preparation
Use the included Containerfile-compatible Dockerfile and compose.yaml with rootless Podman or a compatible Compose runner.
The production app uses PostgreSQL, a private OIDC provider and a TLS reverse proxy.
Create an independent hostname; singolab.com is only a link to it.
Provide secret values through the host's secret management. Do not commit .env.
Replace container tags with the operator's vetted immutable image digests before deployment.
The container integration has not been executed in this environment; no Docker or Podman runtime is available here.

## Keycloak configuration
Create a confidential OIDC client called floridaman. Disable direct access grants and implicit flow.
Enable the standard authorization-code flow and require PKCE S256.
Set the exact redirect URI to https://YOUR_HOST/auth/callback. Do not use a wildcard.
Create realm roles expert and operator. Assign only the needed roles to each account.
Add an ID-token claim mapper named fm_roles that contains the authorized role strings.
Require a second factor in the realm authentication flow. The API requires acr=2 for production login.
Configure an ACR-to-authentication-level mapping and ID-token claim that reflects the completed MFA flow.
Test a real sign-in, rejected role, rejected non-MFA login, session expiry and logout before enabling the service.
Set OIDC_ISSUER, OIDC_CLIENT_ID and OIDC_CLIENT_SECRET to that client.
Set PROXY_IP to the actual trusted Caddy address. Do not trust forwarded headers from every address.

## Import a live packet for private review
Use the packet shape in server/domain.py as a contract reference. Do not use synthetic values as live inputs.
Each live source requires its captured excerpt, URL, source version, issue/retrieval times and rights basis.
Supply an independent QC record with PASS, input_digest, reviewer and evidence_refs.
The digest is SHA-256 over the canonical JSON serialization implemented by server.domain.digest.

    python -m server.operator --packet /private/packet.json --qc-record /private/qc.json --expert-subject EXPERT_OIDC_SUB --operator OPERATOR_ID

The command creates a private review record only. Publication remains blocked until a live source-verification and mirror adapter is implemented and tested.
This fail-closed boundary is intentional. A configured identity provider does not make live analytical outputs valid.

## Verification
    pip install -r requirements-test.txt
    python -m unittest discover -s tests
    python -m pytest tests/v2 -q
    npm --prefix web ci
    npm --prefix web run build

For real-browser integration checks, install Playwright outside the source tree and its Chromium browser, then run:

    npm install --prefix /tmp/fm-browser playwright@1.56.1
    /tmp/fm-browser/node_modules/.bin/playwright install chromium
    PLAYWRIGHT_MODULE=/tmp/fm-browser/node_modules/playwright ./scripts/check-browser.sh

The browser script starts a disposable loopback server and exercises the actual API and database.
Set PLAYWRIGHT_MODULE or CHROMIUM_PATH only when using a separately installed browser runtime.
The resulting screenshots, memo and browser-results.json are written to test-evidence/.

## Backup and restore gate
Back up PostgreSQL with encrypted off-host storage. Retain both records and sessions under a documented retention policy.
Restore into an isolated database and verify packet digests, approvals and release identity before production sign-off.
The one-hour RPO and four-hour RTO are targets; this build has not established them through a restore exercise.
