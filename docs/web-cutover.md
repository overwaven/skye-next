# Canonical threads and authenticated web reads

Implementation date: 2026-11-07, with a live OIDC and server-copy rehearsal update the
same day. This extends the Stage 0–1 foundation. **Both runtime flags default to false**
(the production bot was not restarted with them). The live bot/database were not migrated
or modified; migration was rehearsed only on server-side copies. No payment, provider
account or public web-client release was changed.

## Status and release gates

Stage 2's canonical storage, offline migration/backfill, receipts, activity projection,
delivery state, thread selection and shared admission/settlement core are implemented.
Stage 3's feature-gated authentication and owner-scoped read API are implemented, along
with Next.js read-only account views.

**Live verification completed:** the isolated handler completed a real Telegram OIDC
round-trip through the registered `https://chat.skye-bot.com/auth/callback`: signature,
issuer, audience, nonce and an existing-account match passed. Telegram returned `id` as
a canonical decimal string, so the verifier now accepts only `[1-9][0-9]{0,18}` strings
or positive JSON integers; floats, booleans, leading zeros and out-of-range values fail.
No conversation, wallet or resource content was read or changed by the lab.

**Server-copy rehearsal completed:** SQLite's online backup API and media copy were taken
from the live volume into a private directory; migration created 13 project threads and
5 group bindings, projected 28 allowlisted historical messages across 13 private threads,
and a repeat run imported zero. Original runtime history, wallets, ledger, projects,
group bindings, session references and media hashes matched the source; integrity and
foreign keys passed; restoring the backup into a separate file reproduced all preserved
data. This is not yet a rehearsal on the production path or an approval to stop the bot.

Do not mark the combined production exit gates passed:

- **Two-account gate:** only one real existing account has completed login. A second
  account must still show isolated API/UI/stream results before the Stage 3 exit can pass.
- **Cutover:** the actual database/media have not been migrated, the bot has not been
  restarted with flags, and the web API is not deployed. That requires an explicit
  maintenance window and a fresh backup.
- Legacy projection is conservative: user text, user attachment references (unresolved),
  and assistant `send_message` calls with a successful tool result. Assistant prose,
  failed/unproven fallback, tool output, voice content and unknown media stay omitted.
  The API returns per-thread `partial`/`empty` coverage; the UI discloses incompleteness.
- New confirmed Telegram text, voice, image and document deliveries now create canonical
  receipts per successful Telegram message, with opaque attachment references and only a
  short-lived allowlisted activity projection. Real-message tests with the bot restarted
  under the flags are still required; no live migration has occurred.
- Provider response references/usage snapshots are recorded when available. Usage that
  is missing or estimated is **not** automatically charged or treated as free. It enters
  `run_reconciliation`, blocks new paid admission after delivery until resolved, and
  requires explicit operator evidence via `scripts/reconcile_run.py`. This is new
  operational work and needs an actual-provider exercise before paid web sending.
- Production ingress/TLS for the Next.js client and internal API token, operational
  restore, and real-account acceptance remain release work. Web send, streams, uploads
  and resource CRUD are still not exposed.
- A temporary isolated OIDC verification service (`skye-oidc-verification`) and two
  Caddy paths (`/api/v1/spike/auth/start`, `/auth/callback`) are active **only** for this
  test. They must be stopped and removed after the second account test; see cleanup below.

## Storage and compatibility

`threads.py` installs version 1 explicitly, never from ordinary `Database.open()`:

- Existing `telegram_projects` remains the project authority, gaining a revision and
  an update trigger. No duplicate memory/connector/skill/wallet store is introduced.
- Custom projects get an initial thread retaining the exact session reference.
- Built-in Skye becomes an unassigned default thread, retaining its legacy lookup and
  default-only instructions. Independent unassigned threads do not inherit those
  instructions, even when selected through Skye's Telegram picker.
- Unmigrated private conversations retain their references. Duplicate or cross-owner
  session references and unresolved private automation targets fail for operator review.
- Group/topic bindings remain chat-scoped and never enter personal web navigation.
- Existing private automations are pinned once to the selection at migration. New private
  automations bind to the executing canonical thread, or the explicitly selected thread
  when created outside a turn. They never resolve the current project when firing.
- Deleting a custom project keeps its threads/history, now unassigned; automation targets
  do not move. Deleting built-in Skye is still prohibited.
- `/reset` clears the selected thread's runtime and visible messages, not memory, other
  threads or wallet accounting. Clearing an active run is rejected with feedback.
- Canonical run IDs, funding/settings snapshots and settlement markers are durable.
  Runtime keys use canonical threads; Telegram stop/scheduler checks remain aware of
  them. Restart marks unfinished runs interrupted without replaying them.

There is one in-process `TurnService`, injected into both Telegram and the HTTP app.
It serializes per thread and payer across admission, execution and settlement. A durable
request key prevents re-execution; wallet debit/ledger, free usage and the settlement
marker commit atomically. An intentional `/retry` is a new request, not an automatic
replay. Safe visible text is recorded only after successful delivery, per Telegram
message receipt. A network acknowledgement lost before receipt persistence is still
ambiguous; exactly-once external Telegram delivery is not promised.

The Telegram cutover is opt-in. `/threads` lists up to 20 loaded choices for the current
project; `/threads new <title>` creates and selects an independent thread. The store
loads up to 200 recent account threads. Larger-history navigation/pagination remains a
later UI/API refinement. Browser navigation never changes Telegram selection.

## Offline backup and migration

Do this only in an approved maintenance window, with bot, scheduler and web **stopped**.
The script does not stop services for you. First rehearse against copies.

```bash
uv run python scripts/migrate_threads.py \
  --database /path/to/skye.db \
  --media /path/to/files \
  --backup /path/to/new-private-backup-directory \
  --confirm-stopped
```

The backup path must be new and outside the source media directory. It is created with
0700 permissions. SQLite's backup API captures the complete database snapshot, including
WAL content; media is copied alongside it. `migration.json` records import counts,
SHA-256 checksums, projection counts and per-thread `partial`/`empty` coverage. Migration
is additive and repeat-safe, preserves legacy lookups, and checks SQLite integrity. The
backfill uses a frozen per-thread `history_cutovers` maximum row id, so later runtime
messages cannot be imported after clear/reset. An ambiguous mapping aborts the data
transaction; any preceding schema additions remain safely retryable.

Verify counts, owners, original session references, project instructions, wallet totals,
media and integrity on the copy. Repeat migration and check zero new imports. The
2026-11-07 rehearsal did this on a private server-side copy of the live volume, including
restore into a different DB. It still does not authorize the real cutover.

Before new writes, restore the complete backed-up DB/media set if needed. After new
writes, disable the features and retain compatible code/data; **never restore a stale
wallet snapshot as routine rollback**. Old Telegram code cannot navigate newly created
independent threads, although their canonical records are retained for re-enablement.

## Configuration and ingress

Python environment, after migration and the real-provider gate:

```dotenv
SKYE_CANONICAL_THREADS=true
SKYE_WEB_ENABLED=true
SKYE_WEB_HOST=127.0.0.1
SKYE_WEB_PORT=8090
SKYE_WEB_ORIGIN=https://your-registered-host.example
SKYE_OIDC_CLIENT_ID=<from BotFather>
SKYE_OIDC_CLIENT_SECRET=<from BotFather>
SKYE_WEB_INTERNAL_TOKEN=<independent random secret, at least 32 characters>
```

Next.js server environment:

```dotenv
SKYE_WEB_ENABLED=true
SKYE_WEB_ORIGIN=https://your-registered-host.example
SKYE_WEB_API_ORIGIN=http://127.0.0.1:8090
SKYE_WEB_INTERNAL_TOKEN=<same independent server-to-server secret>
```

Keep all secrets out of commands, committed files, client bundles and `NEXT_PUBLIC_*`.
The internal token is not a user credential: every account request still requires the
opaque browser session and owner authorization. A separate token is needed because
Node's current Fetch ignores custom `Host` overrides; do not replace it with arbitrary
forwarded-header trust. The server-only adapter forwards only the session cookie and
the internal token, never all browser cookies/headers or an owner supplied by the browser.

One HTTPS origin routes `/api/v1/*` directly to Python and UI paths to Next.js. Register
the exact callback in BotFather and set `SKYE_OIDC_CALLBACK_PATH` to `/auth/callback`
(default on Skye's BotFather registration) or `/api/v1/auth/callback`. On 2026-11-07
Telegram accepted `/auth/callback`, while a newly registered `/api/v1/auth/callback`
returned a misleading `redirect_uri required` page even though the URL was registered.
Do not move to the legacy widget to work around this. Preserve the public Host at ingress,
strip client-supplied `X-Skye-Internal-Token`, and
keep Python on a private listener/network. Use a private service address and bind
`0.0.0.0` only when necessary inside a protected container network. Public per-client
rate limits belong at ingress; the app's bounded limiter uses the real socket peer,
not spoofable `X-Forwarded-For` (10 auth requests/minute/peer).

Disable callback query-string logging at **every** proxy. aiohttp access logging is
disabled; application HTTP events contain request ID, method, route template and status,
not query parameters, tokens, bodies or provider error messages. Telegram's failure log
also no longer serializes arbitrary exception text. The Stage 0 spike remains separate
and is never mounted by this bootstrap.

## Authentication and API

Authlib handles code exchange with PKCE S256 and client-secret-basic. `joserfc` verifies
RS256 signatures, issuer, audience/authorized party, expiry, issued-at, subject and nonce.
JWKS is cached for five minutes, with throttled refresh for rotation. State and browser
binding are short-lived, stored durably and consumed once. There is no UserInfo call,
refresh flow, username-based linking or browser-supplied account ID.

Verified `profile.id` must belong to an existing Skye account. `(issuer, sub)` is linked
immutably to that ID; mismatches fail closed. On a database that predates this work,
the legacy `web_sessions` table may have a different schema; the new app deliberately
uses **`web_auth_sessions`** and leaves the old table untouched. `web_identities` and
`oidc_transactions` are additive. Opaque session tokens are hashed in SQLite,
rotated at login and capped at 20 per account. Cookies use `__Host-`, Secure, HttpOnly,
SameSite=Lax and Path=/ without Domain. Idle/absolute expiration is 7/30 days. Bans are
rechecked on every authenticated request; logout and logout-all revoke server records.

| Endpoint | Scope |
| --- | --- |
| GET `/api/v1/auth/start`, `/auth/callback` | Rate-limited OIDC only |
| GET `/api/v1/session` | Current authenticated ID + CSRF token |
| POST `/api/v1/auth/logout`, `/auth/logout/all` | Exact Origin + session CSRF token |
| GET `/api/v1/capabilities` | Truthful read-only capability flags |
| GET `/api/v1/preferences` | Same effective personal model/settings source as Telegram |
| GET `/api/v1/projects`, `/threads` | Owner-scoped private navigation |
| GET `/api/v1/threads/:id`, `/threads/:id/messages` | Owner-scoped thread/allowlisted transcript |
| GET `/api/v1/runs/:id` | Owner-scoped delivery state, 24-hour activity, settled/pending/unknown cost (no provider refs) |

All responses/errors are no-store, vary on cookies/fetch metadata and carry safe errors
with request IDs. Foreign and unknown threads both return 404. History reads are bounded
to 100 messages/page. No group, media download, run execution or event-stream endpoint
is exposed here. Next.js account routes render dynamically and use no-store fetches plus
runtime AJV validation of Python-generated JSON Schema, not unverified TypeScript casts.
They do not cache account responses globally or persist transcripts/drafts in localStorage.
CSRF values remain server-side for Next.js logout actions. Logout revokes in Python before
clearing the Next.js cookie/router cache; the direct API also sends Clear-Site-Data.

## Billing holds and operator reconciliation

Known provider usage is recorded before settlement, but charging is gated on confirmed
delivery. If usage is missing/estimated, or a known cost exceeds the remaining wallet,
the run enters `run_reconciliation`; a delivered run in that state blocks new paid
admission for the payer. It is never silently marked free or charged twice.

```bash
# Read-only inspection; shows only run/payer/funding/reason/cost/provider references
uv run python scripts/reconcile_run.py --database /path/to/skye.db --list

# Stop bot/API/scheduler first. Supply real provider usage evidence; never infer it.
uv run python scripts/reconcile_run.py --database /path/to/skye.db \
  --confirm-stopped --run-id <run> --cost-milli <retail cost> \
  --evidence provider:usage-<id> --model <model> \
  --input-tokens 0 --output-tokens 0
```

`cost-milli` is the retail wallet charge; provider cost is optional. This workflow still
needs an actual-provider exercise. Provider references/usage are not exposed by the API.

## Production cutover record (2026-11-07)

Performed on the owner's server with explicit downtime approval:

1. Built `skye-next:prod` and `skye-web:prod`, then stopped only `skye-next`.
2. Took a fresh SQLite online backup plus media copy inside the data volume, and
   copied it to root-only `/root/skye-next-backups/20261107-live-cutover` (190 MB).
3. Migrated the live volume with the new image. Result: 13 private project/default
   threads, 5 group bindings, 28 allowlisted historical messages, 2 wallets untouched,
   integrity and foreign keys clean. The bot/database were not touched before this
   point; a second migration run on copies imported zero.
4. Replaced only the managed `chat.skye-bot.com` Caddy block. `/auth/callback` and
   `/api/v1/*` go to Python on **127.0.0.1:8090**; other UI routes go to the web
   container on **127.0.0.1:18780**. The Streamlit `/beta` route is unchanged.
   Client-supplied `X-Skye-Internal-Token` is stripped at the proxy.
5. Started `skye` and `web` from compose. Both healthy; `web_started` and polling
   appear in structured logs. Fresh OIDC start uses the registered `/auth/callback`,
   PKCE S256, nonce and a Secure `__Host-skye_login` cookie.

Rollback while retaining compatible data:

```bash
cd /root/skye-next
docker compose stop web skye
# Restore Caddy from the managed backup only if no later edits exist:
#   cp /root/skye-next-backups/20261107-cutover/Caddyfile /etc/caddy/Caddyfile
#   systemctl reload caddy
# If no new post-cutover writes occurred, restore the complete DB/media backup
# to the volume while stopped. Never overwrite newer wallet/transcript data with
# a stale backup; see the migration section.
docker compose up -d skye
```

The old static UI release remains under `/var/www/chat.skye-bot.com/releases`; it is
not served while the new Caddy block is active. The old bot image was replaced by the
rebuild; rebuilding commit `1d8b7e3` is the code-level rollback path.

## Temporary verification cleanup

The live check used an isolated root-owned service and two Caddy routes. After the second
account test, remove them and rotate the OIDC secret in BotFather (the secret was also
typed into chat, so treat it as exposed regardless of file permissions):

```bash
ssh vi
systemctl disable --now skye-oidc-verification
rm -f /etc/systemd/system/skye-oidc-verification.service
systemctl daemon-reload
# Remove only the block between the marked BEGIN/END comments, validate, reload.
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile && systemctl reload caddy
rm -rf /root/skye-web-verification /root/skye-web-rehearsal-20261107
```

The Caddy backup made before the test is `/etc/caddy/Caddyfile.pre-skye-oidc-20261107`
and is readable only by root. Restore it only if no later Caddy edits exist; otherwise
remove the marked block instead. Confirm the normal site still responds and `/api/v1/spike/*`
is absent. Delete local credential copies as well. Never commit an env file.

## Executed evidence

- Python: **586 tests passed**, including migration idempotence, DB/media backup/restore,
  group exclusion/reset, default-only instructions, cutover-bounded backfill, opaque media
  receipts, partial-send receipts, allowlisted/bounded activity, pinned automation firing,
  durable run deduplication, cancellation, delivery-gated and exactly-once settlement,
  known-charge retry, explicit reconciliation, provider references and no-usage holds.
- Auth/API: signed claims, invalid signature/unknown key, missing claims, PKCE, browser
  binding, expiry/replay, decimal-string profile IDs with strict rejection, immutable
  account mapping, hashed sessions, idle/absolute expiry, logout/revocation, CSRF, bans,
  forged Host, run/activity owner isolation and internal-secret/session separation.
- **Live OIDC:** one real existing account passed signature, issuer, audience, nonce,
  profile-ID and existing-account checks through the registered callback. A second
  real account is still required for the Stage 3 two-account gate.
- **Live-data rehearsal:** 13 projects, 5 groups, 28 projected historical messages
  across 13 threads, zero on repeat; all integrity/ownership/session/wallet/media/restore
  checks passed on private copies. Live services and database were not modified.
- Web: **33 foundation browser tests passed** across Chromium/Firefox/WebKit. Axe waits
  for settled overlays; fading text was an audit timing artifact, not a reason to disable
  contrast checks. Python Ruff, strict mypy (50 files), TypeScript, contracts and
  production build are checked separately.
- `scripts/serve_web_test_accounts.py` + `web/scripts/check-auth.mjs`: two synthetic
  accounts through the actual production Next.js build into Python, in all three engines.
  Own transcript/navigation renders, foreign data is absent, read-only pages pass axe,
  and logout revokes access. These tests deliberately inject test cookies over loopback
  HTTP; **they do not verify real OIDC, HTTPS or browser Secure-cookie acceptance**.
- Baseline unused carousel lint failure and npm audit's 13 findings remain disclosed in
  `web/docs/foundation-verification.md`; no force upgrades or rule suppression were used.

The synthetic server creates its own temporary database and tokens; never point it at
real data or expose it publicly. It has no bot/model/payment integration. Stop owned
test services when finished. See `web/README.md` for the repeatable browser commands.
