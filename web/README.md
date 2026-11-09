# Skye web interface

Next.js 16.4.4 / React 19 / Tailwind v4 / Base UI shadcn (`base-luma`) / Hugeicons.
`npm run dev` starts the real web UI and an isolated Python preview backend together.
It requires Node, `uv`, and the parent Python checkout. No production credentials are needed.

```bash
npm ci
npm run dev
```

Open <http://localhost:3000/chat> (or the port printed by Next.js).

The preview uses the same API, SQLite stores, media library, SSE and turn lifecycle as
production. It starts with projects, conversations, image attachments, documents, an
audio file and a completed tool trace. You can create/edit projects with the icon picker,
rename/move/archive/delete threads, upload/attach/preview files, send messages, stop a run,
retry a failure, record audio, switch themes, navigate Library, and sign out/back in.
Type **demo error** in a message to exercise the failed-run UI. Replies, transcription,
tool work and spending are simulated; no model, Telegram, external connector or paid
service is called. Library resource editors retain the production UI's current limits.

Demo changes persist across restarts in ignored `web/.dev-data/`, completely separate
from production. Stop with Ctrl+C; both preview processes shut down. The dev API bridge
and automatic demo identity are disabled outside `NODE_ENV=development`. Next binds to
localhost only. For a phone, use browser device emulation; this is not a public server.

`npm run dev:states` runs the older disconnected state gallery (also used by browser E2E):

- `/chat/a-place-to-think`: sample conversation and responsive Context inspector.
- `/projects/skye-web`: sample thread list and local-only instructions editor.
- `/dev/states/ready`: navigation for empty/loading/failure/running/long/low-funds fixtures.
- `/library/memory` (and connectors/skills/files/agents/automations): routable library framing.
- `/settings/general`: working local light/dark/system preference.

Development samples are labeled. All fixture state routes return 404 in
production. With account integration disabled, production navigation is empty and login
is visibly unavailable. The isolated OIDC lab is **not** wired to the UI.

## Opt-in account reads

See `../docs/web-cutover.md` for the default-off Python migration/auth flags, matching
Next.js environment, HTTPS ingress and remaining release gates. Real-provider Telegram
OIDC verification is still blocked on operator setup; do not enable a public deployment
based on the synthetic tests. Never use `NEXT_PUBLIC_*` for internal URLs or secrets.

When explicitly configured, the UI validates Python-generated response schemas on the
server, reads owner-scoped navigation/history, and supports sign-out and revoke-all.
Old history is preserved but not backfilled; voice/media transcript parts are not yet
shown. Resource editors still disclose that they do not persist changes.

To repeat the **synthetic, loopback-only** production-rendering checks:

```bash
# Root terminal 1: temporary DB, no real bot/models/accounts
uv run python scripts/serve_web_test_accounts.py --output "$TMPDIR/skye-auth-check.json"

# web/ terminal 2, after npm run build; this token is for fixtures ONLY
SKYE_WEB_ENABLED=true SKYE_WEB_ORIGIN=https://localhost:3004 \
SKYE_WEB_API_ORIGIN=http://127.0.0.1:8092 \
SKYE_WEB_INTERNAL_TOKEN=fixture-internal-token-not-for-production-123456789 \
npm run start -- --hostname localhost --port 3004

# web/ terminal 3
node scripts/check-auth.mjs "$TMPDIR/skye-auth-check.json"
```

The script tests two owners, foreign-thread exclusion, axe and logout in three engines.
It injects synthetic cookie headers over HTTP and does not prove TLS cookie acceptance
or real OIDC. Stop both owned test servers afterward; the Python fixture removes its
temporary database and token file on graceful shutdown.

## Checks

```bash
npm run contracts:check  # requires the Python checkout in .. and uv
npm run typecheck
npm run build
npx playwright install chromium firefox webkit
npm run test:e2e
```

`npm run lint` currently also checks unused installed primitives; see the verification
report for the pre-existing carousel rule failure. It has not been silenced or rewritten
as unrelated work. New/changed foundation files are linted separately.

`npm run contracts` regenerates `lib/contracts.generated.ts` and `lib/contracts.schema.json` from the authoritative
`../src/skye/web_contracts.py` schema. Do not hand-edit generated domain types.
`DESIGN.md` defines UI conventions; `docs/foundation-verification.md` records measured
checks and limits. `../docs/web-foundation.md` documents Stage 0 decisions, migration,
retention and the executable OIDC/SSE lab.

The web client is part of this repository and its source is tracked alongside the Python
code, so one clone and one deploy produce both containers. `npm run contracts` keeps the
generated web types in sync with `../src/skye/web_contracts.py`.
