# Stage 6 — personal resources

## Failure inventory (before implementation)

- A foreign memory/skill/custom connector ID must not read, alter or delete data.
- Missing CSRF, origin, session or a revoked session must reject mutations.
- Editing memory must preserve its ID, enforce 500 characters and reject stale revisions.
- Turning memory off must affect the next runtime turn, not delete stored facts.
- Skill preview must not install anything; installation must revalidate the exact bytes.
- Archives must reject traversal, links, duplicate paths, encryption and expansion bombs
  before allocation; duplicate names must not replace an installed skill.
- Connector status must come from the provider, never from browser return parameters.
- Provider outage must not turn a stale connection into a verified connected state.
- MCP must deny private/link-local/metadata IPs, DNS rebinding and redirects at connection
  time; tests must never invoke a third-party tool with side effects.
- Credentials must not appear in responses, events or logs. Web credential editing must
  require configured encryption; existing unencrypted deployments remain readable.
- Telegram and web must use the same rows and invalidate resource views without re-login.
- Resource availability is not evidence of use. Only safe recorded run activity is evidence.
- Failed saves, uploads and disconnects must preserve input and expose a retry path.

## Design

Retain Achromatic ledger / Open plane, seed 1660668609; no redraw or preset change.
Memory answers what Skye remembers and where it applies; Connectors answers which apps
are available or need attention; Skills answers what has been taught. Lists lead, editors
are dialogs, substantial details have stable routes. The context edge distinguishes
personal availability from confirmed tool activity. No invented resource counts or usage.

## Security and operations

MCP transport resolves every request and pins it to a checked public IP while retaining
the original TLS hostname; redirects, local/metadata/CGNAT addresses and URL credentials
are rejected. Tests list tool schemas only, without executing tools. Public HTTPS on port
443 is required; no operator-private-network exception is provided. Changing a server URL
requires explicitly replacing or removing any saved credentials so secrets cannot be sent
silently to the new destination.

Credential editing in web requires `SKYE_CONNECTOR_ENCRYPTION_KEY`, a Fernet key held
outside the database. Generate it once, back up it separately and securely with the DB,
then restart; existing plaintext custom headers are migrated transactionally. Previous
DB backups and WAL may contain plaintext: protect them as sensitive. Changing or losing
the key without first decrypting/re-encrypting a verified offline copy will stop startup;
do not silently rotate it. No key means web accepts only connector configurations with no
new credentials; existing Telegram plaintext records remain readable. This does not
encrypt Composio's own session cache or the whole database.

Composio callback identity verification is **off by default**. The project operator must
first configure `https://chat.skye-bot.com/connector-verify` as its project-wide callback
identity verifier in Composio, confirm query-string logging is disabled across ingress,
and verify the effect on Telegram's existing connection workflow. Only after both channels
are compatible may `SKYE_COMPOSIO_VERIFIER_ENABLED=true` be set. The web exchanges the
single-use session URI against the authenticated user's server-side `tg:<id>` and confirms
the returned toolkit is active; browser return parameters never establish success. Until
that operator gate is complete, connecting/reconnecting an app from web remains disabled;
existing connected apps and safe disconnect still work.

Automated local API evidence is in `docs/web-stage6-e2e.json`. Connected browser tests
use a local synthetic database, not real credentials. The one-account production deploy
and the Memory/Connectors/Skills browser flows are verified. Live real-provider connector
use/revocation, cross-channel acceptance and a second real account remain unverified; the
implementation checklist is complete while that exit gate is not fully signed off.

## Local visual review

The app inspector ran on the three library routes at 1440, 768 and 390 CSS pixels with
the existing user-selected project emoji allowed. All screenshots were opened. It reports
zero failures; each sparse test account yields a `hero-void` warning because the true
resource list is small. Do not manufacture entries to fill that space. The 320px browser
run also checks row action containment, navigation and no horizontal page overflow.
The memory action row was stacked on phones after it squeezed long text; filtered
categories now show their readable label and MCP setup does not stretch to page width.
The one screen question for each resource is answered by its list; scope is explicit;
neither connector availability nor a saved memory is represented as evidence of use.

## Deployment, 2026-11-10

The isolated Stage 6 snapshot was folded back into the single source checkout at
`/root/skye-next`; no second copy of the application remains on the server. The Python
and web containers run from that checkout, Telegram polling and the web listener start,
the public login returns 200, and resource access remains owner-scoped. The production
schema includes thread pins/previews and persisted tool activity details.

Composio callback verification is enabled with the project-wide verifier at
`https://chat.skye-bot.com/connector-verify`. Web credential editing remains disabled until
`SKYE_CONNECTOR_ENCRYPTION_KEY` is configured and backed up as described above. The
VkusVill custom MCP remains disabled because `https://mcp.vkusvill.ru/mcp` hangs.

Post-deployment SQLite `quick_check` passed and both containers reported running without
restarts. Anonymous resource access returns 401; authenticated live UI was verified with
the owner's account.

Local verification: 426 Python regressions and 78 browser checks across Chromium, Firefox
and WebKit, including chat selection/layout stability, tool evidence, Memory/Skills/
Connectors CRUD, project deletion and English/Russian locale persistence. The connected
browser checks use an isolated local database under `web/test-results/`; they are not live
provider or second-account verification.
