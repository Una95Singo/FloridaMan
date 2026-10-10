#!/bin/sh
set -eu
export FM_DEMO=true
test_database=$(mktemp /tmp/floridaman-browser-XXXXXX.db)
export DATABASE_URL="sqlite:///$test_database"
export BASE_URL="http://127.0.0.1:8011"
python3 -m uvicorn server.app:app --host 127.0.0.1 --port 8011 > /tmp/floridaman-browser-server.log 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true; rm -f "$test_database"' EXIT
python3 - <<'PY'
import urllib.request,time
for i in range(40):
 try: urllib.request.urlopen('http://127.0.0.1:8011/api/health');break
 except Exception:time.sleep(.2)
else:raise RuntimeError('Server did not start')
PY
node scripts/browser-check.cjs
