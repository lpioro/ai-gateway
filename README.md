# AI Gateway LAN

Public open-source self-hosted AI chat gateway. UI and conversation database remain on your host; using cloud providers sends prompts to those providers.

## Features

- Responsive ChatGPT-inspired web UI, model selector, streaming responses
- SQLite chat history and chat deletion API
- Ollama (local), OpenAI, Groq and Gemini via OpenAI-compatible Chat Completions endpoints
- Server-enforced `FORCE_LOCAL_ONLY=true` mode
- Docker Compose, Proxmox LXC deployment example
- GitHub Actions: pytest + GHCR image build

**Security warning:** This is an MVP prototype. The UI sends a shared password in a request header. Do not expose directly to the Internet or untrusted LAN. Use a strong password, TLS behind a proxy, firewall rules and stronger session authentication before multi-user deployment.

## Install natively in Proxmox LXC (no Docker)

Use the native installer on Debian/Ubuntu inside your existing LXC:

```bash
apt-get update && apt-get install -y git
git clone https://github.com/lpioro/ai-gateway.git /root/ai-gateway-src
cd /root/ai-gateway-src
bash scripts/install-lxc.sh
```

It configures a Python virtual environment, a dedicated system user, SQLite persistence in `/var/lib/ai-gateway`, settings in `/etc/ai-gateway/gateway.env` and a systemd service. Default bind is loopback only. GitHub Actions also provides a downloadable native `tar.gz` package. See [full LXC instructions](deploy/LXC.md).

## Run locally with Docker

```bash
cp .env.example .env
# Edit .env: change GATEWAY_PASSWORD
docker compose up -d --build
```

Open http://127.0.0.1:8080 (loopback only by default). To expose on your LAN intentionally, set `LAN_BIND_IP` to the LAN IP of your Docker host, and restrict access at firewall level.

For local Ollama, configure a reachable `OLLAMA_BASE_URL` from inside the container. Example: `http://host.docker.internal:11434`, provided Ollama listens on the matching host interface.

## GHCR / Proxmox LXC

Image: `ghcr.io/lpioro/ai-gateway:latest` (available after a successful GitHub Actions build and package publication).

```bash
cp .env.example .env
docker compose -f deploy/compose.ghcr.yaml pull
docker compose -f deploy/compose.ghcr.yaml up -d
```

GHCR package visibility must be changed to public separately if anonymous pulls are desired. Docker inside LXC needs appropriate nesting configuration and host security review; a Proxmox VM is the more isolated option.

## API

- `GET /healthz` — basic health check
- `GET /api/models` — configured models
- `GET /api/chats` — history list
- `GET /api/chats/{id}` — messages
- `DELETE /api/chats/{id}` — delete chat
- `POST /api/chat` — SSE stream

Protected routes require an `X-Gateway-Password` header.

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

No API keys or real personal data belong in the repository. MIT licensed.
