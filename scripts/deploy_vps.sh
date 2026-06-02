#!/usr/bin/env bash
# AMRO one-shot VPS deploy (Ubuntu 22.04+)
# Run as root on the server:
#   curl -fsSL https://raw.githubusercontent.com/oud075-alt/AMRO/main/scripts/deploy_vps.sh | bash
# Or after clone:
#   bash scripts/deploy_vps.sh

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/amro}"
REPO_URL="${REPO_URL:-https://github.com/oud075-alt/AMRO.git}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="amro"
BIND_HOST="127.0.0.1"
BIND_PORT="8000"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

detect_public_ip() {
  curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null \
    || curl -fsS --max-time 5 https://ifconfig.me 2>/dev/null \
    || hostname -I | awk '{print $1}'
}

PUBLIC_IP="$(detect_public_ip)"
PUBLIC_ORIGIN="${PUBLIC_ORIGIN:-http://${PUBLIC_IP}}"

echo "==> Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git nginx curl ufw unzip

echo "==> Cloning/updating AMRO at ${APP_DIR}..."
if [[ -d "${APP_DIR}/.git" ]]; then
  git -C "${APP_DIR}" fetch origin
  git -C "${APP_DIR}" checkout "${BRANCH}"
  git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"
else
  mkdir -p "$(dirname "${APP_DIR}")"
  git clone --branch "${BRANCH}" --depth 1 "${REPO_URL}" "${APP_DIR}"
fi

cd "${APP_DIR}"

echo "==> Python virtualenv + dependencies..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install gunicorn -q

if [[ ! -f .env ]]; then
  echo "==> Creating .env from template..."
  cp .env.production.example .env
  SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed -i "s|^APP_SECRET_KEY=.*|APP_SECRET_KEY=${SECRET}|" .env
  sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=${PUBLIC_ORIGIN}|" .env
  sed -i "s|^WEBHOOK_BASE_URL=.*|WEBHOOK_BASE_URL=${PUBLIC_ORIGIN}|" .env
  sed -i "s|^POCKETBASE_URL=.*|POCKETBASE_URL=http://127.0.0.1:8090|" .env
  echo ""
  echo "IMPORTANT: Edit API keys before production use:"
  echo "  nano ${APP_DIR}/.env"
  echo ""
fi

echo "==> systemd service..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=AMRO Web Trial
After=network.target

[Service]
User=root
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind ${BIND_HOST}:${BIND_PORT} --workers 1 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "==> PocketBase (login) + Nginx..."
if [[ -f "${APP_DIR}/scripts/install_pocketbase_vps.sh" ]]; then
  PUBLIC_ORIGIN="${PUBLIC_ORIGIN}" APP_DIR="${APP_DIR}" bash "${APP_DIR}/scripts/install_pocketbase_vps.sh"
else
  echo "WARN: install_pocketbase_vps.sh not found — skipping PocketBase"
fi

echo "==> UFW firewall..."
ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 'Nginx Full' >/dev/null 2>&1 || true
echo "y" | ufw enable >/dev/null 2>&1 || true

sleep 2
echo ""
echo "==> Health check..."
if curl -fsS "http://127.0.0.1/health" >/dev/null; then
  curl -sS "http://127.0.0.1/health"
  echo ""
else
  echo "Health check failed. Logs:"
  journalctl -u "${SERVICE_NAME}" -n 40 --no-pager
  exit 1
fi

echo ""
echo "=============================================="
echo " AMRO deployed"
echo " Dashboard: ${PUBLIC_ORIGIN}/"
echo " Health:    ${PUBLIC_ORIGIN}/health"
echo " Edit env:  nano ${APP_DIR}/.env"
echo " Logs:      journalctl -u ${SERVICE_NAME} -f"
echo "=============================================="
