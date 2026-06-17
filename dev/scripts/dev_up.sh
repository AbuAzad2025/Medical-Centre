#!/usr/bin/env bash
set -euo pipefail
echo "[*] Killing anything on :5001 ..."
lsof -ti :5001 | xargs -r kill -9 || true
echo "[*] Safe boot on 5001 ..."
APP_SAFE_BOOT=1 flask --app app.py run -p 5001


