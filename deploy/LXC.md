# Native deployment on Proxmox LXC (without Docker)

This distribution contains Python source code and a systemd installer, **not a Docker image**. It is intended for an existing Debian/Ubuntu LXC running systemd. Run commands **inside** the LXC unless stated otherwise.

## Requirements

- Debian 12/13 or a supported Ubuntu release, systemd, apt and Internet access for apt/pip.
- Root access inside the LXC; sufficient free disk/RAM.
- Network connectivity to providers if cloud models are used.
- No Docker, privileged LXC or nesting setting is necessary for this deployment.

## Option A — build/install directly from Git

```bash
apt-get update && apt-get install -y git
git clone https://github.com/lpioro/ai-gateway.git /root/ai-gateway-src
cd /root/ai-gateway-src
bash scripts/install-lxc.sh
```

## Option B — install a package produced on GitHub

Go to GitHub Actions → **Native LXC package** → a successful run → Artifacts, and download `ai-gateway-lxc-<sha>`. The artifact contains a `.tar.gz` file and `SHA256SUMS`. Published version-tag releases also attach them to GitHub Releases.

Transfer the downloaded files to the LXC and check the checksum:

```bash
sha256sum -c SHA256SUMS
tar xzf ai-gateway-lxc-<sha>.tar.gz
cd ai-gateway
bash scripts/install-lxc.sh
```

This uses apt and pip **inside the LXC**, not a precompiled binary. The installer preserves an existing `/etc/ai-gateway/gateway.env` and SQLite data in `/var/lib/ai-gateway`.

## LAN access

Default listens on `127.0.0.1:8080` only. To allow other LAN devices:

```bash
hostname -I
nano /etc/ai-gateway/gateway.env
# Set LAN_BIND_IP to the actual LAN IP of this LXC (not the Proxmox host IP).
systemctl restart ai-gateway
systemctl status ai-gateway --no-pager
curl http://127.0.0.1:8080/healthz  # works with default loopback binding
```

After changing `LAN_BIND_IP`, use `curl http://<LAN_IP>:8080/healthz`. Open `http://<LAN_IP>:8080` in your browser.

**Security:** the current UI uses a password header over HTTP, which is not safe on an untrusted/shared LAN. Use an HTTPS reverse proxy, firewall allowlisting and improve authentication before using it outside a tightly controlled lab. Never expose port 8080 publicly.

## Operations

```bash
systemctl status ai-gateway
journalctl -u ai-gateway -n 100 --no-pager
systemctl restart ai-gateway
systemctl stop ai-gateway
```

To update from Git, run `git pull --ff-only` in the source checkout and rerun `bash scripts/install-lxc.sh`. For versioned releases, unpack a new tarball and rerun the installer. Keep backups of `/var/lib/ai-gateway/gateway.db` before updating. The installer updates the app files and virtual environment, not the settings or database.

## Ollama

Inside a native LXC, `host.docker.internal` is not a standard host alias. Use `OLLAMA_BASE_URL=http://<OLLAMA_SERVER_IP>:11434`, or `http://127.0.0.1:11434` if Ollama is running in the same LXC. Ensure Ollama is listening at that address and restrict access to the Ollama API.

## Diagnostics

If the service fails, check `journalctl -u ai-gateway -e --no-pager`. If port 8080 is already occupied, edit `LAN_PORT` in `/etc/ai-gateway/gateway.env` and restart. If `curl` gives a response but the UI cannot connect, check the browser network console and your Proxmox/LXC firewall.
