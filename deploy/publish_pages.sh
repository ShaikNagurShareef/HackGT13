#!/usr/bin/env bash
# Rebuild the GitHub Pages site (live app via live.json, offline demo fallback) and publish it.
# Keeps the live.json that tunnel_watchdog.sh maintains.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAGES="$ROOT/deploy/.ghpages"
BASE="/PathPulse/"

(cd "$ROOT/frontend" && VITE_BASE="$BASE" VITE_LIVE_CONFIG=1 npx vite build >/dev/null)
rsync -a --delete --exclude .git --exclude live.json "$ROOT/frontend/dist/" "$PAGES/"
touch "$PAGES/.nojekyll"
git -C "$PAGES" add -A
git -C "$PAGES" diff --cached --quiet && { echo "Pages already up to date"; exit 0; }
git -C "$PAGES" commit -q -m "deploy: rebuild Pages site"
git -C "$PAGES" push -q origin gh-pages
echo "published https://shaiknagurshareef.github.io$BASE"
