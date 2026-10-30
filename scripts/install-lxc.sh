#!/usr/bin/env bash
set -Eeuo pipefail

# Native Debian/Ubuntu installation inside an existing Proxmox LXC.
# Run from the extracted release directory as root. No Docker required.
if (( EUID != 0 )); then echo "Run as root: sudo bash scripts/install-lxc.sh" >&2; exit 1; fi
if [[ ! -f requirements.txt || ! -f app/main.py ]]; then echo "Run from the project/release root." >&2; exit 1; fi
if ! command -v apt-get >/dev/null; then echo "Only Debian/Ubuntu apt-based guests are supported." >&2; exit 1; fi

APP_DIR=/opt/ai-gateway
DATA_DIR=/var/lib/ai-gateway
ETC_DIR=/etc/ai-gateway
USER_NAME=ai-gateway

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends python3 python3-venv python3-pip ca-certificates
if ! id "$USER_NAME" &>/dev/null; then
  useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$USER_NAME"
fi
install -d -m 0750 -o root -g "$USER_NAME" "$APP_DIR" "$ETC_DIR"
install -d -m 0750 -o "$USER_NAME" -g "$USER_NAME" "$DATA_DIR"
cp -a app "$APP_DIR/"
cp requirements.txt "$APP_DIR/"
chown -R root:"$USER_NAME" "$APP_DIR"
chmod -R o-rwx "$APP_DIR"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --disable-pip-version-check -r "$APP_DIR/requirements.txt"
if [[ ! -f "$ETC_DIR/gateway.env" ]]; then
  password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  cat > "$ETC_DIR/gateway.env" <<EOF
GATEWAY_PASSWORD=$password
DATABASE_PATH=$DATA_DIR/gateway.db
LAN_BIND_IP=127.0.0.1
LAN_PORT=8080
FORCE_LOCAL_ONLY=false
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:4b
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
EOF
fi
chown root:"$USER_NAME" "$ETC_DIR/gateway.env"
chmod 0640 "$ETC_DIR/gateway.env"
install -m 0644 scripts/ai-gateway.service /etc/systemd/system/ai-gateway.service
systemctl daemon-reload
systemctl enable --now ai-gateway
systemctl restart ai-gateway
echo "Installation finished. LAN remains disabled by default (127.0.0.1)."
echo "Edit /etc/ai-gateway/gateway.env and change LAN_BIND_IP to the LXC LAN IP, then run: systemctl restart ai-gateway"
echo "Check status: systemctl status ai-gateway"
