#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

echo "=== ACA Platform → Railway ==="

if ! command -v railway >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "Installing Railway CLI..."
    brew install railway
  else
    echo "Railway CLI not found and Homebrew is unavailable."
    echo "Install it with: bash <(curl -fsSL railway.com/install.sh)"
    exit 1
  fi
fi

echo
echo "Railway will open the browser for login if needed."
railway login

echo
echo "Creating a fresh Railway project/service and doing the first deploy..."
railway up --new --name aca-platform-server

echo
echo "Adding persistent volume at /data..."
railway volume add --mount-path /data

LEGACY="../aca_system_db.json"
if [ -f "$LEGACY" ]; then
  echo
  echo "Found existing ACA database: $LEGACY"
  read -r -p "Upload it to Railway for one-time import? [Y/n] " answer
  answer="${answer:-Y}"
  if [[ "$answer" =~ ^[Yy]$ ]]; then
    railway volume files upload "$LEGACY" /aca_system_db.json
    echo "Existing data uploaded to the persistent volume."
  fi
fi

echo
echo "Redeploying with persistent storage attached..."
railway up

echo
echo "Generating public HTTPS domain..."
railway domain

echo
echo "Done."
echo "Run: railway domain list"
echo "Then open: https://YOUR-DOMAIN/health"
echo
echo "IMPORTANT: in Railway Dashboard enable:"
echo "  Service → Settings → Deploy → Serverless → ON"
echo "This keeps free-tier usage low. The ACA client includes cold-start retries."
