#!/usr/bin/env bash
# Keep the laptop-hosted live app reachable until the Vultr deployment takes over:
# every 60 s check the Cloudflare quick tunnel; if it is down, start a new one and record its
# URL in deploy/.tunnel_url.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INTERVAL_S=60

start_tunnel() {
  pkill -f "cloudflared tunnel --no-autoupdate" 2>/dev/null || true
  : >/tmp/pp_tunnel.log
  nohup cloudflared tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:8080 >/tmp/pp_tunnel.log 2>&1 &
  for _ in $(seq 1 40); do
    url="$(grep -aoE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/pp_tunnel.log | head -1 || true)"
    [ -n "$url" ] && break
    sleep 1
  done
  [ -n "${url:-}" ] || return 1
  for _ in $(seq 1 20); do curl -fsS --max-time 10 "$url/api/healthz" >/dev/null 2>&1 && break; sleep 3; done
  echo "$url" >"$ROOT/deploy/.tunnel_url"
  echo "$(date) live at $url"
}

failures=0
while true; do
  url="$(cat "$ROOT/deploy/.tunnel_url" 2>/dev/null || true)"
  if [ -n "$url" ] && curl -fsS --max-time 15 "$url/api/healthz" >/dev/null 2>&1; then
    failures=0
  else
    failures=$((failures + 1))
    if [ "$failures" -ge 2 ] || [ -z "$url" ]; then
      echo "$(date) tunnel down; restarting"
      start_tunnel && failures=0
    fi
  fi
  sleep "$INTERVAL_S"
done
