#!/usr/bin/env bash
# One command from keys to a live site: deploy/go.sh <domain>   (e.g. pathpulse.tech)
# Steps: verify keys -> provision Vultr VM -> bootstrap -> deploy -> load Tiger Data -> smoke test.
set -euo pipefail

DOMAIN="${1:?usage: deploy/go.sh <domain>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY_PATH="$HOME/.ssh/pathpulse_ed25519"
export GIT_SSH_COMMAND="ssh -i $KEY_PATH"

echo "==> 1/6 checking sponsor keys"
(cd "$ROOT/backend" && uv run --package pathpulse-backend python -m app.tools.check_keys) || {
  echo "Some keys failed; fix backend/.env and re-run."; exit 1; }

echo "==> 2/6 provisioning Vultr"
[ -f "$ROOT/deploy/.host" ] || bash "$ROOT/deploy/provision_vultr.sh"
IP="$(cat "$ROOT/deploy/.host")"
HOST="root@$IP"
SSH=(ssh -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new "$HOST")
for _ in $(seq 1 30); do "${SSH[@]}" true 2>/dev/null && break; sleep 5; done

echo "==> 3/6 bootstrapping server"
"${SSH[@]}" 'bash -s' -- "$DOMAIN" <"$ROOT/deploy/bootstrap.sh"

echo "==> 4/6 deploying app"
RSYNC_RSH="ssh -i $KEY_PATH" bash "$ROOT/deploy/deploy.sh" "$HOST" "$DOMAIN" || true

echo "==> 5/6 loading Tiger Data"
if grep -qE '^DATABASE_URL=.+' "$ROOT/backend/.env"; then
  (cd "$ROOT" && uv run --package pathpulse-data python -m pathpulse_data.db.load_tiger)
fi

echo "==> 6/6 smoke test"
echo "DNS for $DOMAIN -> $(dig +short "$DOMAIN" | tail -1) (should be $IP)"
curl -fsS --max-time 20 "https://$DOMAIN/api/healthz" && echo && echo "LIVE: https://$DOMAIN" ||
  echo "HTTPS not up yet (DNS/TLS can take a few minutes). Direct check: http://$IP/api/healthz"
