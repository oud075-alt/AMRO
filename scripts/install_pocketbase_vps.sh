#!/usr/bin/env bash
# Install PocketBase on AMRO VPS (Ubuntu) + nginx /pb proxy + systemd
# Run as root:
#   bash /opt/amro/scripts/install_pocketbase_vps.sh
#
# Safe to re-run. Does not overwrite an existing .env (only fixes placeholder POCKETBASE_URL).

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/amro}"
PB_BIN="${APP_DIR}/pocketbase"
PB_DATA="${APP_DIR}/pb_data"
PB_BIND_HOST="127.0.0.1"
PB_BIND_PORT="8090"
PB_SERVICE="pocketbase"
AMRO_SERVICE="${AMRO_SERVICE:-amro}"
BIND_HOST="127.0.0.1"
BIND_PORT="8000"
NGINX_SITE="/etc/nginx/sites-available/amro"

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
PB_PUBLIC_URL="${PUBLIC_ORIGIN}/pb"

download_pocketbase() {
  apt-get install -y -qq unzip curl 2>/dev/null || true
  if [[ -x "${PB_BIN}" ]]; then
    echo "==> PocketBase binary already present"
    return
  fi
  echo "==> Downloading PocketBase (linux amd64)..."
  local version tag asset url tmp
  tag="$(curl -fsSL --max-time 20 \
    -H 'User-Agent: AMRO-Deploy' \
    https://api.github.com/repos/pocketbase/pocketbase/releases/latest \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")"
  version="${tag#v}"
  asset="pocketbase_${version}_linux_amd64.zip"
  url="https://github.com/pocketbase/pocketbase/releases/download/${tag}/${asset}"
  tmp="$(mktemp)"
  curl -fsSL --max-time 120 -o "${tmp}" "${url}"
  unzip -qo "${tmp}" -d "${APP_DIR}"
  rm -f "${tmp}"
  chmod +x "${PB_BIN}"
  echo "    Installed ${PB_BIN} (${tag})"
}

install_systemd() {
  echo "==> systemd ${PB_SERVICE}..."
  cat > "/etc/systemd/system/${PB_SERVICE}.service" <<EOF
[Unit]
Description=PocketBase (AMRO auth)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
ExecStart=${PB_BIN} serve --http=${PB_BIND_HOST}:${PB_BIND_PORT} --dir=${PB_DATA}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable "${PB_SERVICE}"
  systemctl restart "${PB_SERVICE}"
}

patch_env() {
  local env_file="${APP_DIR}/.env"
  [[ -f "${env_file}" ]] || return 0
  if grep -qE '^POCKETBASE_URL=(https?://your-pocketbase-domain\.com|)$' "${env_file}" \
     || ! grep -q '^POCKETBASE_URL=' "${env_file}"; then
    if grep -q '^POCKETBASE_URL=' "${env_file}"; then
      sed -i "s|^POCKETBASE_URL=.*|POCKETBASE_URL=http://${PB_BIND_HOST}:${PB_BIND_PORT}|" "${env_file}"
    else
      echo "POCKETBASE_URL=http://${PB_BIND_HOST}:${PB_BIND_PORT}" >> "${env_file}"
    fi
    echo "==> Set POCKETBASE_URL=http://${PB_BIND_HOST}:${PB_BIND_PORT} in .env"
    systemctl restart "${AMRO_SERVICE}" 2>/dev/null || true
  fi
}

write_nginx() {
  echo "==> Nginx site (AMRO + /pb PocketBase proxy)..."
  cat > "${NGINX_SITE}" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${PUBLIC_IP} _;

    client_max_body_size 20m;

    location /pb/ {
        rewrite ^/pb/(.*)\$ /\$1 break;
        proxy_pass http://${PB_BIND_HOST}:${PB_BIND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }

    location / {
        proxy_pass http://${BIND_HOST}:${BIND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
    }
}
EOF
  ln -sf "${NGINX_SITE}" /etc/nginx/sites-enabled/amro
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl reload nginx
}

wait_for_pb() {
  local i
  for i in $(seq 1 30); do
    if curl -fsS "http://${PB_BIND_HOST}:${PB_BIND_PORT}/api/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

echo "==> AMRO PocketBase install (${APP_DIR})"
[[ -d "${APP_DIR}" ]] || { echo "Missing ${APP_DIR} — deploy AMRO first."; exit 1; }

download_pocketbase
install_systemd
write_nginx
patch_env

echo "==> Waiting for PocketBase..."
if ! wait_for_pb; then
  echo "PocketBase health failed. Logs:"
  journalctl -u "${PB_SERVICE}" -n 40 --no-pager
  exit 1
fi

echo ""
echo "=============================================="
echo " PocketBase OK"
echo " Admin UI:  ${PB_PUBLIC_URL}/_/"
echo " Health:    ${PB_PUBLIC_URL}/api/health"
echo " Backend:   POCKETBASE_URL=http://${PB_BIND_HOST}:${PB_BIND_PORT}"
echo ""
echo " ขั้นตอนต่อ (ครั้งเดียว):"
echo "  1) เปิด ${PB_PUBLIC_URL}/_/ สร้าง Superuser"
echo "     ให้ตรงกับ POCKETBASE_ADMIN_EMAIL/PASSWORD ใน .env"
echo "  2) Settings → Application → App URL = ${PB_PUBLIC_URL}"
echo "  3) Settings → Auth providers → Google (Client ID/Secret)"
echo "     Redirect URI ใน Google Console:"
echo "       ${PB_PUBLIC_URL}/api/oauth2-redirect"
echo "  4) git pull แล้ว restart amro ถ้ายังไม่ได้ frontend ล่าสุด"
echo "  5) ทดสอบ Login ที่ ${PUBLIC_ORIGIN}/"
echo "=============================================="
