# Canonical threads and authenticated web reads

Implementation date: 2026-11-07. This extends the Stage 0–1 foundation; it does not
enable a deployment. **Both new runtime flags default to false.** No live database,
bot service, payment, provider account or public ingress was changed during development.

## Status and release gates

Stage 2's canonical storage, offline migration, thread selection and shared admission/
settlement core are implemented. Stage 3's feature-gated authentication and owner-scoped
read API are implemented, along with Next.js read-only account views.

Do not mark the combined production exit gates passed:

- The real Telegram OIDC round-trip, nonce/profile claims and two real existing accounts
  still require registered HTTPS origins and operator credentials. Synthetic accounts
  and signed-token tests cannot establish those facts.
- Old runtime history is preserved, **not backfilled into the visible transcript**.
  No raw assistant history is exposed as a shortcut. Old fallback/media delivery needs
  evidence unavailable in legacy rows. The read-only UI discloses this limit.
- Newly confirmed Telegram text bubbles (including fallback text after successful
  delivery) have canonical receipts. Voice/image/file transcript references and durable
  activity projection remain open. Existing Telegram media/library behavior is unchanged.
- Cancellation/provider failure can leave unknown cost because the runtime cannot always
  return final usage. A cost exceeding the remaining wallet rolls back settlement and
  stays unknown for reconciliation; it is not silently reported as paid or free. There
  is no reservation/partial-charge reconciliation workflow yet. Do not enable paid web
  sending on this basis.
- Production ingress/TLS behavior, operational restore on the actual deployment and
  real-account acceptance remain operator/release work. Web send, streams, uploads and
  resource CRUD are not exposed by this stage.

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
SHA-256 checksums and the explicit no-backfill status. Migration is additive and
repeat-safe, preserves legacy lookups, and checks SQLite integrity. An ambiguous mapping
aborts the data transaction; any preceding schema additions remain safely retryable.

Verify counts, owners, original session references, project instructions, wallet totals,
media and integrity on the copy. Repeat migration and check zero new imports. Tests also
restore the legacy backup into a **different** database and verify content/wallet totals.
That fixture rehearsal is not a rehearsal on the operator's actual data.

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
`https://your-registered-host.example/api/v1/auth/callback` exactly in BotFather.
Preserve the public Host at ingress, strip client-supplied `X-Skye-Internal-Token`, and
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
immutably to that ID; mismatches fail closed. Opaque session tokens are hashed in SQLite,
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

All responses/errors are no-store, vary on cookies/fetch metadata and carry safe errors
with request IDs. Foreign and unknown threads both return 404. History reads are bounded
to 100 messages/page. No group, media download, run execution or event-stream endpoint
is exposed here. Next.js account routes render dynamically and use no-store fetches plus
runtime AJV validation of Python-generated JSON Schema, not unverified TypeScript casts.
They do not cache account responses globally or persist transcripts/drafts in localStorage.
CSRF values remain server-side for Next.js logout actions. Logout revokes in Python before
clearing the Next.js cookie/router cache; the direct API also sends Clear-Site-Data.

## Executed evidence

- Python: **568 tests passed**, including migration idempotence, DB/media backup/restore,
  group exclusion/reset, default-only instructions, retained project history, pinned
  automation firing, durable run deduplication, payer serialization, exactly-once wallet/
  allowance settlement, cancellation and interrupted runs.
- Auth/API: signed claims, invalid signature/unknown key, missing claims, PKCE, browser
  binding, expiry/replay, immutable account mapping, hashed sessions, idle/absolute expiry,
  logout/revocation, CSRF, bans, forged Host and internal-secret/session separation.
- Web: **33 foundation browser tests passed** across Chromium/Firefox/WebKit. Axe waits
  for settled overlays; fading text was an audit timing artifact, not a reason to disable
  contrast checks. Python Ruff, strict mypy, TypeScript, contracts and production build
  are checked separately.
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
