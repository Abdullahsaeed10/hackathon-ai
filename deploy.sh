#!/usr/bin/env bash
# Deploy Verdict to a Vultr Ubuntu 24.04 server.
# Usage: VULTR_HOST=1.2.3.4 VULTR_USER=root bash deploy.sh

set -euo pipefail

HOST="${VULTR_HOST:?set VULTR_HOST}"
USER="${VULTR_USER:-root}"
APP_DIR="/opt/verdict"

echo "==> Syncing files to ${USER}@${HOST}:${APP_DIR}"
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='data/' --exclude='.env' \
  ./ "${USER}@${HOST}:${APP_DIR}/"

echo "==> Running remote setup"
ssh "${USER}@${HOST}" bash -s <<'REMOTE'
set -euo pipefail
cd /opt/verdict

# System dependencies
apt-get update -qq
apt-get install -y -qq python3-pip python3-venv

# Python venv
[ -d venv ] || python3 -m venv venv
venv/bin/pip install --quiet --upgrade pip
venv/bin/pip install --quiet -r requirements.txt

# Playwright chromium
venv/bin/python -m playwright install chromium --with-deps 2>/dev/null || true

# Create data dirs
mkdir -p data/verdicts data/uploads

# Copy env file if it doesn't exist
[ -f .env ] || cp .env.example .env
echo ""
echo "ACTION REQUIRED: edit /opt/verdict/.env and set GEMINI_API_KEY, then restart."
echo ""

# Systemd unit
cat > /etc/systemd/system/verdict.service <<'SVC'
[Unit]
Description=Verdict AI Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/verdict
ExecStart=/opt/verdict/venv/bin/gunicorn \
  --worker-class gevent \
  --workers 1 \
  --bind 0.0.0.0:80 \
  --timeout 300 \
  --keep-alive 30 \
  app:app
Restart=always
RestartSec=5
EnvironmentFile=/opt/verdict/.env

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable verdict
systemctl restart verdict
systemctl status verdict --no-pager
REMOTE

echo ""
echo "==> Deploy complete. Verdict is running at http://${HOST}"
echo "    If first deploy: ssh ${USER}@${HOST} 'nano /opt/verdict/.env' and set GEMINI_API_KEY"
