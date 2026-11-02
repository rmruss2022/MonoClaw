# Admin Hub

One place for every app's admin panel, admin tools, and docs. Sibling to the
App Catalog (`/apps`), but admin-facing. Zero-dep Python stdlib server.

**Live:** https://admin.bedrock.casa

## Run
```
ADMIN_PORT=18834 ADMIN_BASE= python3 server.py
```
Served in production by `admin-hub.service` (systemd) on `127.0.0.1:18834`.

## Deploy (how it got onto bedrock.casa)
1. `admin-hub.service` → runs `server.py` on `:18834` (unit committed here; installed at `/etc/systemd/system/`).
2. Cloudflare bedrock tunnel (`587e53e4…`): added DNS CNAME `admin` → `<tid>.cfargotunnel.com` (proxied) and an ingress rule `admin.bedrock.casa` → `http://127.0.0.1:18834`, both additive.

## Add an app
Edit the `APP_PANELS`, `OPS`, or `DOCS` lists in `server.py`. The Recilia admin
panel and its docs are served directly by the hub (`/app/recilia`, `/app/recilia/doc/*`).
