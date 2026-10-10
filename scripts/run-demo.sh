#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-v2.txt
npm --prefix web ci
npm --prefix web run build
export FM_DEMO=true
export DATABASE_URL="sqlite:///./floridaman-v2.db"
printf '\nOpen http://127.0.0.1:8000 and choose Open demo workspace.\n\n'
exec python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
