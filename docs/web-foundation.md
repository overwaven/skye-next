# Web foundation: decisions, contracts, and Stage 0 lab

Accepted defaults: the owner approved PLAN.md section 13 on 2026-11-07.
This document records implementation decisions, not a claim that production web chat exists.

## Decision record

- Keep `web/` as its existing separate Git repository. It is not yet a parent-repository
  submodule and must be deployed from an explicit web checkout/revision. Root Python
  contracts remain authoritative; CI must check both checkouts together. No history was
  removed and no existing component was reinstalled. Before a release, record the web
  repository remote and matching immutable revisions in deployment configuration.
- Personal account first. Existing user/chat scopes stay unchanged. Projects organize
  instructions and threads; they do not isolate personal memory, files, skills or apps.
- One Python runtime/writer/scheduler. HTTP and Telegram will call a shared turn service.
  Stage 0's HTTP lab is a separate executable, not mounted in the real app.
- Use aiohttp for HTTP, Authlib's async HTTPX OAuth client for PKCE/code exchange, and
  its maintained JOSE successor `joserfc` for signature/claim validation. These began as
  spike dependencies and are now runtime dependencies for the opt-in Stage 3 API.
  Never accept unsigned JWTs. See `web-cutover.md` for the current gated implementation.
- Use Pydantic JSON Schema → `json-schema-to-typescript`; Python validates the wire,
  TypeScript types are generated, not a separate domain model. The generator requires
  both sibling checkouts. Runtime response validation remains an API-stage task.
- Add Playwright + axe as web dev dependencies, pytest-aiohttp for isolated HTTP tests.
  Do not add an AI SDK, frontend state framework, external queue, ORM or second UI kit.

## Persistence and retention decision

The current SQLite `agent_messages` contains conversation replay content. Logs contain
metadata, not message bodies. These are separate systems; documentation must say so.

For Stage 2, preserve existing history until explicit clear/delete, and make that policy
visible before first web account connection. Do not silently expire legacy sessions in
this foundation. Canonical visible transcript follows the same explicit-delete policy.
New event replay is bounded to **24 hours or 10,000 events per personal account**, whichever
is reached first. Prefer resource IDs/revisions in invalidations; do not retain raw
provider events, thoughts, arbitrary tool args/results or credentials. Cursor expiry
returns `cursor_expired` and requires a snapshot. These limits are contracts to implement
in Stage 2/4, **not a running janitor** in Stage 0.

Media retains existing deployment-configured count/idle-TTL/byte limits (defaults include
50 personal files and 30 idle days). Expired bytes leave an unavailable transcript reference.
Clearing a thread clears model replay and visible content/search/event payload references,
not wallet accounting records. Invoice/usage records remain for reconciliation without
message text. Archive is not deletion. Memory deletion does not rewrite old messages.
Backups can still contain deleted data until their operator-managed expiry; disclose this.
No browser localStorage transcript or draft is written by Stage 1.

Production sessions: opaque hashed server-side sessions, 7-day idle / 30-day absolute expiry,
rotation at login, revocation, Secure HttpOnly SameSite=Lax host-only cookie. Stage 0 uses
in-memory 15-minute lab sessions only; they cannot authenticate against the real database.

## Contract seam

`src/skye/web_contracts.py` defines v1 request/error/project/thread/message/run/event shapes.
`scripts/export_web_contracts.py` prints JSON Schema without accessing any database.

```bash
# In web/, with the Python checkout at ..
npm run contracts
npm run contracts:check
```

Events are typed allowlisted unions (`message.created`, `run.changed`, `resource.changed`),
not provider response blobs. A null cost with pending/unknown state is not zero spend.
Client requests cannot supply owner/payer IDs. API services resolve ownership from session.
IDs are opaque; cursors are account-bound at the future API layer. All errors have a
safe message, recovery instruction, code, request ID, retry flag and optional field errors.

Send is `POST /threads/:id/messages`, idempotent by account + thread + request ID;
snapshot is `GET /threads/:id/messages?before=<cursor>&limit=<bounded>`; updates use revision
preconditions. Commands never auto-replay after an uncertain response. API routes and
idempotency storage are Stage 2–4 work; Stage 0 does not expose a fake send endpoint.

## Migration map and safe transcript experiment

| Legacy record | Canonical target | Must preserve |
| --- | --- | --- |
| Custom `telegram_projects` | Project + first thread | ID lookup, instructions, exact session reference |
| Built-in Skye project | Unassigned default thread | Default-only instructions and old ID binding |
| Unmigrated private `conversations(user_id, 0)` | Same default thread, once | No lazy-migration duplication |
| Group/topic conversation | Existing group/thread binding | Chat scope; never expose in personal navigation |
| Empty project/session | Empty thread | No fabricated messages or model run |
| Automation | Explicit target thread + destination policy | Never resolve active project at fire time |

`tests/fixtures/web_history.json` contains eight **synthetic** cases: delivery, unproven
fallback, voice, files/images, empty project, old private, group topic and cancellation.
`history_projection.py` intentionally extracts only user text and explicit `send_message`
or `send_voice` calls with a matching successful `sent` result. It omits all assistant
prose, unproven fallback delivery, unknown media and tool secrets. Group fixture coverage
tests parsing, **not authorization**; ownership filtering must happen before projection.
It is not invoked against live data. A production migration needs transport receipts to
prove fallback/media delivery and must report unknown history rather than expose it.

### Backup, cutover, rollback rehearsal contract

1. Stop bot/web/scheduler before a migration; take an SQLite online-backup API snapshot
   (or a quiesced full SQLite/WAL set), copy the media volume and record checksums/version.
   A bare copy of an actively written SQLite file without WAL is not a valid backup.
2. Run migration against a **copy** first. Validate `PRAGMA integrity_check`, ownership,
   thread/session mappings, project counts, no repeated imports and unchanged wallet totals.
3. Use an explicit schema version, transaction and durable mapping table. Restart twice
   in fixtures and prove the second migration changes nothing.
4. Retain old lookup compatibility during cutover. Do not drop legacy tables in the first release.
5. Before new writes, restore the complete backup if rehearsal fails. After new writes,
   disable web and deploy compatible code; never restore an old wallet/transcript snapshot
   as ordinary rollback. Production migration/restore code belongs to Stage 2.

## Run the local transport lab

The lab binds **127.0.0.1:8091** only and contains no bot/database wiring. Fixture mode
is explicitly synthetic, cannot use a public origin and is never mounted in production.
Its cookie grants access only to four numbered probe events. Access logging is disabled
so OIDC callback codes do not land in logs. Do not put credentials in shell commands.

```bash
# Root terminal 1
uv run python scripts/web_spike.py --fixture

# web/ terminal 2: same-origin development rewrite, no browser CORS bypass
SKYE_SPIKE_ORIGIN=http://127.0.0.1:8091 npm run dev -- --hostname localhost

# Root terminal 3
uv run python scripts/probe_web_stream.py
```

The probe creates a local synthetic session with Origin validation, checks early heartbeat
arrival, then reconnects through **Next.js** with Last-Event-ID=2 and verifies only 3/4
replay. Next's rewrite changes Host; the lab trusts the configured forwarded public host
only from loopback and the exact internal host `127.0.0.1:8091`. This lab-specific trust
rule is not a production reverse-proxy configuration.

Production ingress will route `/api/v1/` directly to Python, preserve the validated public
host, disable SSE buffering, set an adequate read timeout, and keep compression from
batching events. Actual production-ingress behavior remains unverified until Stage 9.

## Verify real Telegram login (blocked until operator setup)

Set `SKYE_OIDC_CLIENT_ID`, `SKYE_OIDC_CLIENT_SECRET`, and `SKYE_SPIKE_PUBLIC_ORIGIN` in
the process environment securely. Set `SKYE_SPIKE_EXPECTED_USER_ID` to the known numeric
Telegram ID of the account used for the test; the callback fails on a mismatch and
reports only a boolean on a match. Use a registered HTTPS development origin routed to
the lab; BotFather must list the exact callback:
`https://<registered-host>/api/v1/spike/auth/callback`.

Run the lab **without `--fixture`**, visit `/api/v1/spike/auth/start`, and approve in Telegram.
The result exposes only verification booleans, not tokens, names, phone numbers or claims.
No actual Skye account is linked or read. Confirm `profile.id` is returned, code-flow nonce
round-trips, an existing account ID matches, and cancel/replay/expiry fail safely.

RS256 and issuer/audience/expiry/issued-at/subject/nonce validation are fail-closed. If
Telegram does not echo the nonce in this flow, investigate against official docs rather
than deleting validation to get a green screen. No UserInfo request or refresh is made.
Production additionally needs JWKS caching/rotation, durable transactions/sessions,
account lookup/linking, access rules, CSRF on all mutations and login rate limits.

**Live update 2026-11-07:** one real existing account completed the flow through the
registered `/auth/callback`; signature, issuer, audience, nonce and `profile.id` matched.
Telegram returned `id` as a canonical decimal string, now accepted only in that strict
form (floats/booleans/leading zeros fail). A second real account, the two-account
isolation exit gate and the production cutover remain open. The temporary isolated handler
and Caddy routes must be removed after verification; see `web-cutover.md`.
