#!/bin/sh
# Real-browser workflow check against a disposable loopback server.
# Set PLAYWRIGHT_MODULE to a Playwright install outside the source tree, and
# CHROMIUM_PATH only when using a separately installed browser binary.
set -eu
export FM_DEMO=true
port="${BROWSER_CHECK_PORT:-8011}"
test_database=$(mktemp /tmp/floridaman-browser-XXXXXX.db)
server_log=$(mktemp /tmp/floridaman-browser-server-XXXXXX.log)
export DATABASE_URL="sqlite:///$test_database"
export BASE_URL="http://127.0.0.1:$port"
# Back-to-back runs: a server from the previous run may still be releasing the
# port. Wait until nothing answers there, so the readiness probe below cannot
# be satisfied by a process that is about to exit.
python3 - "$port" <<'PY'
import socket, sys, time
port = int(sys.argv[1])
for _ in range(100):
    s = socket.socket()
    s.settimeout(0.2)
    try:
        s.connect(("127.0.0.1", port))
    except OSError:
        break
    finally:
        s.close()
    time.sleep(0.2)
else:
    raise SystemExit(f"Port {port} is still in use")
PY
python3 -m uvicorn server.app:app --host 127.0.0.1 --port "$port" > "$server_log" 2>&1 &
server_pid=$!
cleanup() {
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
  rm -f "$test_database"
}
trap cleanup EXIT
python3 - "$server_pid" "$BASE_URL" <<'PY'
import os, sys, time, urllib.request
pid, base = int(sys.argv[1]), sys.argv[2]
for _ in range(100):
    try:
        os.kill(pid, 0)
    except OSError:
        raise SystemExit("The test server exited before it became ready")
    try:
        urllib.request.urlopen(base + "/api/health", timeout=1)
        break
    except Exception:
        time.sleep(0.2)
else:
    raise SystemExit("The test server did not become ready")
PY
printf 'Test server log: %s\n' "$server_log"
node scripts/browser-check.cjs
