#!/usr/bin/env bash
# (Re)start the full live app from this machine with no cloud accounts:
# uvicorn API + Caddy (deploy/Caddyfile.local) + Cloudflare quick tunnel, and keep the Mac awake.
# Prints the public https://*.trycloudflare.com URL (it changes on every restart).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
pkill -f "uvicorn app.main:create_app" 2>/dev/null || true
pkill -f "caddy run --config deploy/Caddyfile.local" 2>/dev/null || true
pkill -f "cloudflared tunnel --no-autoupdate" 2>/dev/null || true

(cd "$ROOT/frontend" && npx vite build >/dev/null)
(cd "$ROOT/backend" && nohup uv run --package pathpulse-backend uvicorn app.main:create_app --factory \
  --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1 --log-level warning \
  >/tmp/pp_api.log 2>&1 &)
(cd "$ROOT" && PP_ROOT="$ROOT" nohup caddy run --config deploy/Caddyfile.local --adapter caddyfile \
  >/tmp/pp_caddy.log 2>&1 &)
pgrep -x caffeinate >/dev/null || (nohup caffeinate -dimsu >/dev/null 2>&1 &)
(nohup cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8080 >/tmp/pp_tunnel.log 2>&1 &)

for _ in $(seq 1 40); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/pp_tunnel.log | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done
echo "$URL" >"$ROOT/deploy/.tunnel_url"
sleep 5
curl -fsS --max-time 20 "$URL/api/healthz" >/dev/null && echo "LIVE: $URL" || echo "tunnel starting: $URL"
