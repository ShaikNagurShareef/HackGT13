#!/usr/bin/env bash
# Build locally and ship to the VM. Usage: deploy/deploy.sh <ssh-host> <domains>
#   e.g. deploy/deploy.sh root@203.0.113.7 "pathpro.tech, 203-0-113-7.sslip.io"
# <domains> is Caddy's site list: every name gets HTTPS and is an allowed origin.
set -euo pipefail

HOST="${1:?usage: deploy.sh <ssh-host> <domain>}"
DOMAINS="${2:?usage: deploy.sh <ssh-host> <domains>}"
ORIGINS="$(echo "$DOMAINS" | tr ',' '\n' | sed -E 's/^ *//; s/ *$//; /^$/d; s#^#https://#' | paste -sd, -)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(basename "$(readlink "$ROOT/artifacts/current")")"

echo "==> building frontend"
(cd "$ROOT/frontend" && npm ci --no-audit --no-fund && npm run build)

echo "==> shipping code, artifacts ($VERSION), and web build"
rsync -az --delete -e "${RSYNC_RSH:-ssh}" \
  --exclude '.git' --exclude 'node_modules' --exclude '.venv' --exclude 'cache' \
  --exclude 'data/raw' --exclude 'data/interim' --exclude 'artifacts' --exclude 'frontend' \
  --exclude 'backend/.env' --exclude '__pycache__' \
  "$ROOT/" "$HOST:/srv/pathpulse/app/"
rsync -az -e "${RSYNC_RSH:-ssh}" "$ROOT/artifacts/$VERSION" "$HOST:/srv/pathpulse/artifacts/"
rsync -az --delete -e "${RSYNC_RSH:-ssh}" "$ROOT/frontend/dist/" "$HOST:/srv/pathpulse/web/"
if [ -f "$ROOT/backend/.env" ]; then
  rsync -az -e "${RSYNC_RSH:-ssh}" --chmod=F600 "$ROOT/backend/.env" "$HOST:/srv/pathpulse/app/backend/.env"
fi

echo "==> installing and restarting"
${RSYNC_RSH:-ssh} "$HOST" bash -s <<EOF
set -euo pipefail
cd /srv/pathpulse/app
ln -sfn "/srv/pathpulse/artifacts/$VERSION" /srv/pathpulse/artifacts/current
touch backend/.env
# Production values always win over whatever the laptop .env had for these.
sed -i -E '/^(ALLOWED_ORIGINS|ARTIFACTS_DIR|APP_ENV)=/d' backend/.env
printf 'ALLOWED_ORIGINS=%s\nARTIFACTS_DIR=/srv/pathpulse/artifacts/current\nAPP_ENV=production\n' "$ORIGINS" >>backend/.env
chmod 600 backend/.env
chown -R pathpulse:pathpulse /srv/pathpulse
# The service runs with ProtectHome=true, so the venv must use the system Python, not a
# uv-managed interpreter under /home.
sudo -u pathpulse /home/pathpulse/.local/bin/uv sync --python-preference only-system \
  --package pathpulse-backend --frozen --no-dev --python /usr/bin/python3.12
cp deploy/pathpulse.service /etc/systemd/system/pathpulse.service
cp deploy/Caddyfile /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable --now pathpulse
systemctl restart pathpulse
systemctl reload caddy || systemctl restart caddy
sleep 2
curl -fsS http://127.0.0.1:8000/healthz >/dev/null && echo "API healthy"
EOF

for origin in ${ORIGINS//,/ }; do
  echo "==> smoke test $origin"
  curl -fsS --max-time 30 "$origin/api/healthz" && echo && echo "deployed $VERSION to $origin" ||
    echo "$origin not reachable yet (DNS or certificate still pending)"
done
