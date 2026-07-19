#!/usr/bin/env bash
# Expose the local Tagr web app via a Cloudflare quick tunnel (no account required).
# Usage:
#   ./scripts/cloudflare-tunnel.sh              # default http://127.0.0.1:8787
#   TAGR_URL=http://localhost:8787 ./scripts/cloudflare-tunnel.sh
#
# For a permanent named tunnel with your own domain, set CLOUDFLARE_TUNNEL_TOKEN
# from Cloudflare Zero Trust -> Networks -> Tunnels, then use:
#   cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN"

set -euo pipefail

TAGR_URL="${TAGR_URL:-http://127.0.0.1:8787}"

if [[ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]]; then
  echo "Starting named Cloudflare tunnel (token provided)..."
  exec cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN"
fi

echo "Starting quick Cloudflare tunnel -> ${TAGR_URL}"
echo "Public URL will appear below (https://*.trycloudflare.com)"
echo "Press Ctrl+C to stop."
exec cloudflared tunnel --no-autoupdate --url "$TAGR_URL"
