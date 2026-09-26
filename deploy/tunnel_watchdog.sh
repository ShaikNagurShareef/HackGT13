#!/usr/bin/env bash
# Keep the live app reachable from the stable GitHub Pages URL, with no cloud accounts:
# every 60 s check the Cloudflare quick tunnel; if it is down, start a new one and publish its
# URL as live.json on the gh-pages branch (the Pages front end reads it at load time).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAGES_DIR="$ROOT/deploy/.ghpages"
REPO="https://github.com/ShaikNagurShareef/HackGT13.git"
INTERVAL_S=60

publish() {
  local url="$1"
  [[ "$url" =~ ^https://[a-z0-9-]+\.trycloudflare\.com$ ]] || { echo "refusing to publish '$url'"; return 1; }
  [ -d "$PAGES_DIR/.git" ] || git clone -q --branch gh-pages --depth 1 "$REPO" "$PAGES_DIR"
  git -C "$PAGES_DIR" pull -q --rebase origin gh-pages || true
  printf '{"api":"%s","updated":"%s"}\n' "$url" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$PAGES_DIR/live.json"
  git -C "$PAGES_DIR" add live.json
  git -C "$PAGES_DIR" -c user.name="Shareef0612" -c user.email="noreply@github.com" \
    commit -q -m "live: point Pages at the current PathPulse tunnel" || return 0
  git -C "$PAGES_DIR" push -q origin gh-pages && echo "$(date) published $url"
}

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
  publish "$url"
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
