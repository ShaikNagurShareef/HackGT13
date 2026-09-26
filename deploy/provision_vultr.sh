#!/usr/bin/env bash
# Create the PathPro VM on Vultr (Atlanta, Ubuntu 24.04, 2 GB) using VULTR_API_KEY from
# backend/.env. Writes the server IP to deploy/.host. Safe to re-run: reuses an existing VM.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/backend/.env"
API="https://api.vultr.com/v2"
LABEL="pathpulse"
KEY_PATH="$HOME/.ssh/pathpulse_ed25519"

VULTR_API_KEY="$(grep -E '^VULTR_API_KEY=' "$ENV_FILE" | cut -d= -f2-)"
[ -n "$VULTR_API_KEY" ] || { echo "VULTR_API_KEY is empty in backend/.env"; exit 1; }
auth=(-H "Authorization: Bearer $VULTR_API_KEY" -H "Content-Type: application/json")
jqpy() { python3 -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

existing="$(curl -fsS "${auth[@]}" "$API/instances?label=$LABEL" | jqpy "next((i['id'] for i in d['instances']), '')")"
if [ -z "$existing" ]; then
  [ -f "$KEY_PATH" ] || ssh-keygen -t ed25519 -N '' -C 'pathpulse-deploy' -f "$KEY_PATH" >/dev/null
  key_id="$(curl -fsS "${auth[@]}" -X POST "$API/ssh-keys" \
    -d "{\"name\":\"pathpulse-$(date +%s)\",\"ssh_key\":\"$(cat "$KEY_PATH.pub")\"}" | jqpy "d['ssh_key']['id']")"
  os_id="$(curl -fsS "${auth[@]}" "$API/os?per_page=500" |
    jqpy "next(o['id'] for o in d['os'] if o['name'].startswith('Ubuntu 24.04') and 'x64' in o['name'])")"
  echo "==> creating VM (atl, vc2-1c-2gb, os $os_id)"
  existing="$(curl -fsS "${auth[@]}" -X POST "$API/instances" -d "{
    \"region\":\"atl\",\"plan\":\"vc2-1c-2gb\",\"os_id\":$os_id,\"label\":\"$LABEL\",
    \"hostname\":\"$LABEL\",\"sshkey_id\":[\"$key_id\"],\"backups\":\"disabled\"}" | jqpy "d['instance']['id']")"
fi

echo "==> waiting for VM $existing"
for _ in $(seq 1 60); do
  read -r status ip < <(curl -fsS "${auth[@]}" "$API/instances/$existing" |
    jqpy "d['instance']['server_status'] + ' ' + d['instance']['main_ip']")
  if [ "$status" = "ok" ] && [ "$ip" != "0.0.0.0" ]; then break; fi
  sleep 10
done
echo "$ip" >"$ROOT/deploy/.host"
echo "==> VM ready at $ip (saved to deploy/.host). Point your domain's A record to it."
