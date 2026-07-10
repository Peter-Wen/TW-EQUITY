#!/bin/zsh
set -e

APP_DIR="/Users/peterwen/Public/twse-limit-up-site"
PYTHON="/Users/peterwen/Public/finance-python-env/bin/python"
URL="http://127.0.0.1:8055"

cd "$APP_DIR"

if lsof -iTCP:8055 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "TW-EQUITY is already running."
  echo "Opening $URL"
  open "$URL"
  exit 0
fi

echo "Starting TW-EQUITY..."
echo "Opening $URL"
(sleep 2; open "$URL") &

exec "$PYTHON" -B app.py
