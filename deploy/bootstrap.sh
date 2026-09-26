#!/usr/bin/env bash
# One-time server setup on a fresh Vultr Ubuntu 24.04 VM. Run as root:
#   ssh root@<ip> 'bash -s' < deploy/bootstrap.sh <domain>
set -euo pipefail

DOMAIN="${1:?usage: bootstrap.sh <domain e.g. pathpulse.tech>}"

apt-get update -y
apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl rsync ufw
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' |
  gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  >/etc/apt/sources.list.d/caddy-stable.list
apt-get update -y
apt-get install -y caddy

id pathpulse >/dev/null 2>&1 || useradd --system --create-home --home-dir /home/pathpulse --shell /bin/bash pathpulse
mkdir -p /srv/pathpulse/{app,artifacts,web} /var/log/caddy
chown -R pathpulse:pathpulse /srv/pathpulse
sudo -u pathpulse bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'

echo "DOMAIN=${DOMAIN}" >/etc/default/caddy
mkdir -p /etc/systemd/system/caddy.service.d
cat >/etc/systemd/system/caddy.service.d/env.conf <<'EOF'
[Service]
EnvironmentFile=/etc/default/caddy
EOF

ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

systemctl daemon-reload
echo "bootstrap done for ${DOMAIN}. Next: run deploy/deploy.sh from your laptop."
