# Frankfurt Docker deployment

The production checkout is `/root/skye-next` on `ssh de` (31.97.216.135).
The Compose project is `skye-production`. Compose automatically combines `compose.yaml` and `compose.override.yaml`.

- `skye`: Telegram polling, scheduler and the account API, one SQLite writer.
- `web`: production Next.js standalone server.
- `caddy`: static website, chat ingress, automatic HTTPS and persistent certificates.

Public endpoints are https://skye-bot.com and https://chat.skye-bot.com.
The exact Telegram OIDC callback is https://chat.skye-bot.com/api/v1/auth/callback.
API routes go to Python; UI routes go to Next.js. Client internal-token headers
are stripped at ingress. Access logs are disabled so callback queries are not logged.
The Python and Next.js host ports bind to loopback only (8090 and 18780).

Secrets live in the root-only `.env`, never in this document or client variables.
DOCKER_GID must match the host Docker socket group (987 on this VPS).
Named volumes retain the database, media, sandbox work and Caddy certificates.
The initial database was initialized offline, then backed up and migrated with
`scripts/migrate_threads.py` before starting the bot. The backup and migration
report are in `/data/backups/initial-canonical` inside the data volume.
There was no existing production database on this server.

Inspect from the checkout:

```sh
docker compose ps
docker compose logs --tail 100 skye web caddy
docker compose config --quiet
```

For a future approved update, build with `docker compose build`, then apply it
with `docker compose up -d --wait`. This replaces changed containers while
retaining named volumes. Never use `down -v` or prune production data.
Use `docker compose restart SERVICE` when only a restart is needed.
The legacy `scripts/deploy.sh` targets host Caddy and prunes static releases;
it is not the deployment entry point for this Docker-only setup.

Pushing to `master` runs `.github/workflows/deploy.yml`, which over SSH resets
`/root/skye-next` to `origin/master`, keeps the root-only `.env`, runs
`docker compose config`, builds, applies with `--wait`, and checks that
`/api/v1/session` still answers `401` without a session. It targets this host
(`31.97.216.135`) with its pinned host-key fingerprint, so the repository must
keep `compose.yaml`, `compose.override.yaml` and `Caddyfile` in sync with
production: the workflow discards uncommitted changes in the checkout.

The Docker daemon starts at boot; all three services use `unless-stopped`.
Health checks verify the Python authentication boundary and the Next.js server.
The optional Dozzle profile is not enabled. The separate Hermes VPN services,
network namespaces and firewall rules are outside this deployment.

New Telegram accounts must message the bot before signing into web chat.
A full interactive Telegram login requires the account owner; HTTP checks alone
do not prove a completed login or an actual model/tool/payment round trip.

Storage is declared external to protect it from Compose project teardown.
The first startup containers are retained stopped as `skye-initial-bot`,
`skye-initial-web`, and `skye-initial-caddy`; `skye-initial-migration` is the
completed offline initializer. They can be deleted later with owner approval.
