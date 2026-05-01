# Deploying dialogos-neo

This directory holds drop-in configs for typical self-hosted setups.

## Layout assumed by the systemd unit

```
/var/lib/chatapp/                      # working dir, owned by chatapp:chatapp (0750)
└── profiles/                          # PROFILES_ROOT (chmod 0700)
    └── ...
/etc/chatapp/secret.env                # API_TOKEN, API_KEY_*  (0600)
/etc/chatapp/keys.yaml                 # optional YAML keystore (0600)
/etc/systemd/system/chatapp.service    # copy of deploy/chatapp.service
```

## Initial setup

```bash
sudo useradd -r -m -d /var/lib/chatapp chatapp
sudo install -d -o chatapp -g chatapp -m 0750 /var/lib/chatapp
sudo install -d -o chatapp -g chatapp -m 0700 /var/lib/chatapp/profiles
sudo install -d -o root    -g root    -m 0750 /etc/chatapp
sudo install -m 0600 -o chatapp -g chatapp deploy/secret.env.example /etc/chatapp/secret.env
sudo install -m 0644 deploy/chatapp.service /etc/systemd/system/

# Install the package globally (or use a venv at /opt/chatapp/.venv).
sudo pip install /path/to/dialogos-neo

sudo systemctl daemon-reload
sudo systemctl enable --now chatapp.service
sudo systemctl status chatapp
```

## Reverse proxy

Pick one:

- **Caddy** (recommended for solo use): copy `Caddyfile`, edit the hostname,
  `sudo systemctl reload caddy`. Caddy handles TLS automatically.
- **nginx**: copy `nginx.conf` to `/etc/nginx/sites-available/chatapp`,
  symlink, and reload. TLS via certbot or your own certs.

The proxy MUST disable response buffering (`flush_interval -1` for Caddy,
`proxy_buffering off` for nginx) — SSE streams will otherwise stall until
a timeout.

## Authentication

The `/api/*` routes are protected by `Authorization: Bearer $API_TOKEN` (set
in `secret.env`). The browser UI is unauthenticated by default — the design
assumes one of:

1. **Tailscale / Wireguard**: bind only on the VPN address.
2. **HTTP Basic auth at the proxy**: see commented blocks in `Caddyfile`
   and `nginx.conf`. Exempt `/api/*` and `/healthz` from Basic auth so
   automation keeps working.
3. **OIDC**: front the whole site with `oauth2-proxy` if you need real
   multi-user accounts.

## Docker

```bash
docker build -t dialogos-neo -f deploy/Dockerfile .
docker run --rm -p 8080:8080 \
    -e API_TOKEN="$(openssl rand -hex 32)" \
    -e API_KEY_ANTHROPIC_MAIN="$ANTHROPIC_API_KEY" \
    -v $PWD/examples/profiles:/data/profiles \
    dialogos-neo
```

## Backups & operations

- **Backup** = `tar` or `rsync` of `PROFILES_ROOT`. There is no DB.
- **Profile authoring** is filesystem-first: `mkdir`, edit `profile.toml`
  and `system.md` over SSH, `systemctl status chatapp` to confirm the
  process is running. No app restart needed for a profile change — it's
  reloaded on each request.
- **History rotation** is manual: `mv history.md archive/2025.md` when a
  conversation gets too long for the model context window. Future versions
  may add an in-app "archive current conversation" button.
- **Lock files** (`<profile>/.lock`) are cleaned up on normal request
  completion. After a hard kill, remove stale locks with `find profiles -name '.lock' -delete`.
