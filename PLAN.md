# Skye Web Chat — Implementation Plan

Status: Stage 1 complete; Stage 2 implementation and Stage 3 authenticated read-only path
are complete behind default-off flags, with one live OIDC account and a server-copy
migration/restore rehearsal passed. The second real account, actual cutover and live
runtime exercise keep the Stage 0/3 exit gates open. Stages 4–10 are not implemented.
Research and verification date: 2026-11-07. Evidence: `docs/web-cutover.md`.

## 1. Outcome and product boundaries

Build a first-class Next.js chat client for the **same Skye account, agent, history,
wallet, memories, connectors, and skills** used in Telegram. A thread is an independent
conversation and belongs to zero or one project. A project organizes multiple threads
and provides shared instructions; it is not itself a conversation.

**Feeling:** minimal, uncluttered, thoughtful, unique. Breadth comes from progressive
disclosure, not from showing every capability at once. The conversation remains the
main workspace. No dashboard of vanity metrics, permanent inspector, nested card maze,
marketing hero, gradients, glass, or decorative animation.

### Release scope

- Core: Telegram OIDC, synchronized private conversations, multiple threads per project,
  unassigned threads, text chat, visible run activity, cancellation/recovery, files,
  images, voice, Memory, Connectors, Skills, models/preferences, and Sparks/account.
- Comprehensive personal release: custom agents, scheduled and webhook automations,
  search, export/deletion, session management, accessible mobile behavior, operations.
- Preserve Telegram group/topic functionality throughout. Do **not** expose group
  transcripts or group resources merely because a person can log in with Telegram.
  A group web workspace is a separately gated follow-up requiring live membership,
  administrator authorization, revocation, sponsor rules, and group privacy design.
- Telegram Stars stays the payment rail. No new subscription or pretend web checkout.
- Not in the initial release: collaborative project membership, public chat sharing,
  autonomous offline sends, a new model runtime, or a second memory/connector store.

### Decisions proposed here

1. Extend the existing Python process with an authenticated HTTP API and SSE. Keep it
   the only database writer, scheduler, billing authority, and agent executor.
2. Run the existing Next.js app as the optional second service. One HTTPS origin routes
   `/api/v1/*` to Python and UI routes to Next.js. No browser-to-provider calls.
3. Sync canonical application records, not duplicate Telegram messages. A web reply is
   immediately available in Telegram's corresponding thread, but does not unsolicitedly
   send a new Telegram notification unless the user opts in.
4. Preserve personal resources as account-wide by default. A project is an organizational
   and instruction boundary, **not a new security boundary**. Clearly label shared memory,
   files, skills, and connector access. Strict project isolation is a later explicit policy.
5. Build real vertical slices before broad management screens; never ship a decorative
   prototype as a working client.

## 2. Repository reconnaissance and implications

| Evidence | Current implementation | Consequence |
| --- | --- | --- |
| `web/package.json:14`, `web/components.json:3` | Next.js 16.4.4, React 19.3.1, Tailwind v4, `base-luma`, Base UI, Hugeicons, `@/` aliases, npm lockfile | Keep this stack, preset, icon family, and installed components. No reinitialization. |
| `web/app/globals.css:50`, `web/app/layout.tsx:7` | Semantic OKLCH tokens, light/dark blocks, Geist and Geist Mono | Adjust tokens slightly, retain fonts; mono only for code/IDs. |
| `src/skye/db.py:80`, `src/skye/db.py:106` | Group/topic conversation keys; each private Telegram project has one session reference | Introduce transport-neutral threads and migrate existing session references without copying or flattening sessions. |
| `src/skye/telegram_projects.py:120`, `:241` | Built-in Skye project, active project selection, session naming | Adapt Telegram selection to project + thread; preserve existing conversations and familiar defaults. |
| `src/skye/sessions.py:11`, `src/skye/db.py:96` | Durable agent history in SQLite, bounded replay | Agent history exists, but is not a safe UI transcript API. Add a sanitized visible-message representation. |
| `BASE_PROMPT.md:11`, `src/skye/runtime.py:184`, `:818` | Only delivery tools are user-visible; assistant text is private, and `on_text` is currently ignored | Do not stream raw model text or chain of thought. Drive transcript from explicit deliveries and safe activity events. |
| `src/skye/runtime.py:778`, `:819` | Runtime accepts session/run overrides and callbacks, but transport is hardcoded to Telegram | Reuse runtime; add explicit transport-neutral context and callbacks rather than simulate Telegram messages. |
| `src/skye/telegram.py:1587`, `:2050` | Admission, payer, quota, settlement, retries, and delivery are orchestrated in Telegram handlers | Extract a shared turn service before exposing paid web runs. |
| `src/skye/models.py:18`, `src/skye/memory.py:19` | Memory scope is user or chat; category `project` is not project isolation | Do not label a category as a private project memory store. |
| `src/skye/connectors.py:480`, `src/skye/skills.py:60` | Reusable connector services and `.md`/`.zip` skill validation, mixed with Telegram panels | Separate services from panel imports where needed; expose the same underlying records. |
| `src/skye/library.py:64` | Media is user/chat scoped, with count, idle TTL, and byte limits | Thread attachment links must survive metadata-wise when bytes expire; no permanent-file promise. |
| `src/skye/automations.py:240`, `src/skye/telegram.py:1559` | Schedules exist; private runs resolve the active project when firing | Bind automations to an explicit canonical thread, never whichever project happens to be active later. |
| `src/skye/automations.py:159`, `src/skye/app.py:308` | Webhook URL construction exists; inspected bootstrap has no HTTP listener | Implement and secure webhook ingress; do not assume URLs already receive traffic. |
| `src/skye/app.py:107`, `:323` | One Python bootstrap owns database, runtime, polling, scheduler, janitors | Add HTTP lifecycle here. Do not start another polling/scheduling process from Next.js. |

Conventions consulted: root `AGENTS.md`, `BASE_PROMPT.md`, `README.md`,
`web/AGENTS.md`, `web/CLAUDE.md`, `web/components.json`, and installed Next.js guides
for authentication, route handlers, Server/Client Components, and Proxy.
No project `DESIGN.md`, `CONTRIBUTING.md`, or `CODING_STANDARDS.md` was found in recon.

Worktree caution: `web/` is itself a Git repository and is currently untracked by the
outer repository. Its package files and many installed primitives already contain
user work. Stage 0 must decide how web is tracked/deployed; do not delete `.git`,
overwrite components, reset changes, or silently convert it into a submodule.

Documentation discrepancy: root `AGENTS.md` says prompts/responses are never stored,
while `agent_messages.message_data` and `DatabaseSession` persist runtime history.
Clarify that metadata-only **logs** differ from conversation storage. Define retention
and user disclosure before adding a canonical transcript or replayable event journal.

## 3. Identity: real Telegram OIDC

Confirmed against Telegram's official documentation **and live discovery document**:

| Setting | Value / decision |
| --- | --- |
| Discovery | `https://oauth.telegram.org/.well-known/openid-configuration` |
| Issuer | `https://oauth.telegram.org` |
| Authorization | `https://oauth.telegram.org/auth` |
| Token | `https://oauth.telegram.org/token` |
| JWKS | `https://oauth.telegram.org/.well-known/jwks.json` |
| Flow | Authorization Code + PKCE **S256**; server-side exchange |
| Client authentication | Prefer `client_secret_basic` |
| Scopes | `openid profile`; request `telegram:bot_access` separately only for optional bot messaging |
| Not requested | Phone number or TON wallet; unnecessary for Skye |
| Token algorithm | Pin configured RS256 initially; never accept token-selected arbitrary algorithms |
| UserInfo | Not provided; consume verified ID-token claims, skip UserInfo fetch |
| Refresh | Discovery currently lists only `authorization_code`; do not invent refresh-token support |

### Flow and account linking

1. Register exact production/staging callback URLs and allowed origins under the bot's
   **Login Widget** settings in BotFather. Client ID/secret are login credentials,
   distinct from the bot API token. Verify allowed local development URLs with BotFather;
   use a registered HTTPS development origin if necessary.
2. Python owns OIDC initiation, short-lived single-use state/PKCE transactions, callback,
   identity mapping, and opaque application sessions. Use a maintained OIDC library
   (evaluate Authlib in the first spike); do not hand-roll signature/JOSE validation.
3. Generate state, nonce, and verifier server-side. Bind them to the initiating browser,
   expire them, consume them once, and allow only validated same-origin return paths.
   Confirm nonce round-trip for the code flow in the spike; never silently omit validation
   of a nonce that was sent. PKCE, state, and code single-use checks remain mandatory.
4. Validate signature, exact issuer, audience/client ID, expiration, issued-at, and nonce
   when applicable, using bounded clock skew and cached/rotating JWKS.
5. Persist OIDC identity by `(issuer, sub)`. **Do not cast `sub` to the Telegram user ID.**
   Telegram's example explicitly has different `sub` and `id` values. Require the verified
   `profile.id` claim to link the existing numeric Telegram user account. Never link by
   username, display name, avatar, or a browser-supplied ID. Missing/ambiguous claims fail
   safely without exposing an existing account. Confirm the actual claim set in staging.
6. Use an opaque random session cookie: `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`,
   no Domain; production `__Host-` name. Store only its hash server-side. Rotate on login,
   enforce idle/absolute expiry, support revocation and “Sign out all devices”.
7. All mutations require origin/CSRF protection and authorization; OIDC state is not API
   CSRF protection. Recheck authorization on SSE, media, search, export, and every object.
8. Default to full-page redirect login: fewer popup failures and no third-party widget
   script dependency. If a popup option is added, follow Telegram's COOP warning:
   `same-origin` breaks SDK communication; evaluate `same-origin-allow-popups` narrowly.

UX: one “Continue with Telegram” action, explanation that the same account is used,
pending redirect feedback, cancellation/expired-login recovery, wrong-account sign-out,
and a clear “Open Skye in Telegram” fallback. Login alone is not proof of group membership
or permission to DM; bot delivery requires the appropriate consent/start flow.

## 4. Shared domain model and synchronization contract

### Canonical objects

| Object | Proposed responsibility |
| --- | --- |
| Account / identity / session | Existing Telegram numeric user ID remains the resource owner; OIDC identity and browser sessions attach to it. |
| Project | Owner, name, preserved optional emoji, instructions, revision, timestamps, archive state. No direct session field after migration. |
| Thread | Opaque ID, owner, nullable project ID, title, stable runtime session reference, revision, archive/pin state, timestamps. |
| Channel binding | Maps Telegram private-chat selection or group/topic identity to a canonical thread; maps deliveries to Telegram message IDs. |
| Visible message + parts | Stable ID, thread, sequence, role, run ID, origin, reply target, content parts, delivery state, timestamps. Multiple Skye bubbles per run are valid. |
| Run | Thread, requester/payer, input message, model/settings snapshot, lifecycle, usage, cost, error/recovery metadata, idempotency key. |
| Event / change cursor | Ordered, authorized replay/invalidation events; bounded retention and explicit cursor-expired recovery. |
| Attachment reference | Owner/scope, opaque file ID, saved library name, MIME, size, origin, availability/expiry; no client-provided filesystem paths. |
| Resource policy | Effective personal/project selections, inheritance explanation, future isolation hooks. Distinguish enabled from actually used. |

Keep `DatabaseSession` as runtime replay storage. Do not send `agent_messages` JSON,
raw prompts, arbitrary tool arguments/results, secrets, or private assistant monologue
to the browser. Visible messages are a separate application projection with an explicit
allowlist. Keep logs metadata-only. Define what transcript/event content is retained,
for how long, and how clear/delete/export apply before persistence changes ship.

### Migration rules

- Versioned, transactional, repeat-safe migrations; back up SQLite **and media** first.
- Every existing custom Telegram project becomes a project with one initial thread,
  retaining its exact session reference and instructions. No new model run for migration.
- The built-in Skye conversation becomes an unassigned default thread. Preserve its
  legacy ID mapping and built-in instructions as an explicit default-conversation policy;
  do not accidentally make those instructions apply to every independent thread.
- Migrate legacy `conversations(user_id, 0)` once, handling the existing lazy migration
  and empty/uninitialized projects. Report counts and unresolved records.
- Group/topic sessions retain their exact bindings and scopes; they are not imported
  into personal web navigation.
- Backfill only provably visible historical deliveries, user input, and safely resolvable
  attachments. Use delivery-tool records where available; do not relabel all assistant
  items as messages. Dedupe fallback deliveries, and mark unavailable history/media honestly.
  Telegram does not provide a generic API to download all past bot chat history.
- Store per-project Telegram active-thread selection; changing the browser's route does
  **not** silently redirect the next Telegram message. Offer explicit “Continue in Telegram”
  and a thread picker in Telegram. Include project/thread names in its confirmation.
- Keep web drafts and view state separate from synchronized account preferences. Do not
  synchronize scroll position, currently open popovers, or web navigation into Telegram.

### Invariants and conflict behavior

- Every read/write joins to the authenticated owner. Random IDs are not authorization.
- A thread has one ordered transcript and one active run across both transports. Lock
  by canonical thread, not by browser tab or Telegram chat; protect global provider limits.
- Serialize wallet admission/settlement per payer, including runs in different threads.
  Use reservation or an equivalent transactional admission rule to prevent concurrent
  free-allowance/wallet overspend; reconcile actual provider cost once per run.
- Mutating request IDs are scoped to account + operation. A repeated send returns the
  existing message/run, not another charge or side effect. Disable automatic blind replay.
- Revision-based updates return a recoverable conflict for concurrent instruction/name
  edits. Show local draft and current server version; do not silently overwrite either.
- Moving a thread changes future project instructions; it does not erase prior context
  or copy history. Explain that retained history can contain old project information.
  Block moves during a run; snapshot effective instructions/settings when accepting a run.
- Archive is reversible. Deleting a project defaults to retaining its threads as
  unassigned; explicitly confirm any separate permanent transcript deletion. Implement
  the same semantics in Telegram. Deleting memory does not delete facts from old messages;
  explain how to clear the relevant history as well.
- Automations have a stable target thread and destination policy. Archive/delete must
  resolve attached automations explicitly; never retarget them to another project.
- Private resources remain personal across projects unless the UI explicitly says
  otherwise. New per-thread tool allowlists require runtime enforcement, not cosmetic switches.

## 5. Backend, API, and live transport

### Deployment shape

```text
Browser ── HTTPS, same origin ── ingress
                                ├─ UI routes ── Next.js web/
                                └─ /api/v1/* ─ Python HTTP server
                                                ├─ auth / authorization
Telegram polling ────────────────────────────────├─ shared turn service
Scheduler / authenticated webhook ingress ──────├─ agent runtime + integrations
                                                └─ existing SQLite + media
```

Use `aiohttp`, already installed, for Python HTTP lifecycle unless Stage 0 finds a
concrete blocker. No FastAPI/ORM/Redis/Celery migration. The ingress is external or an
optional Compose service. The existing bot-only command and deployment keep working
when web is disabled. Bind Python privately behind ingress; do not expose its port
without authentication, TLS termination, request limits, and trusted-proxy configuration.

Next.js Server Components fetch initial authenticated data directly from the internal
Python origin, forwarding only the needed session credentials. Python validates them;
never trust a forwarded `user_id` header. Never put the private upstream or secrets in
`NEXT_PUBLIC_*`. Use Client Components for composer, live updates, and overlays, not
the entire app. Next.js `proxy.ts` may help redirects but is not an authorization layer.
Authenticated responses are private/no-store; exclude them from shared/CDN/route caches.
Read the installed version's docs before implementing async request APIs and caching.

### Shared turn service

Extract admission, access/ban checks, moderation, effective context, quota/wallet,
runtime invocation, usage settlement, cancellation, error mapping, and delivery into
transport-neutral services. Telegram and HTTP adapters call those services. Preserve
complimentary access and sponsor behavior for Telegram groups. Web private requests
pay from their authenticated owner's same allowance/wallet.

Introduce a channel-neutral run context rather than manufacturing aiogram `Message`
objects or fake Telegram topic IDs. Update tool descriptions and reply targets for the
current channel. `send_message`, `send_voice`, images, and generated files commit
canonical visible parts, then adapters handle delivery. Delivery retries never re-run
the model. Keep fallback semantics for runs without an explicit final delivery.

Initially show complete `send_message` bubbles as they arrive alongside live tool status.
Only add text deltas if an explicit, safe delivery-stream boundary is introduced. The
current raw assistant stream must remain private; a typing animation is not a reason
to expose it. Do not implement a second inference path in Next.js or require AI SDK.

### Proposed API families

Specify request/response/error schemas and generate TypeScript from Python-owned
Pydantic/JSON Schema contracts; choose a small generator in Stage 0. Commit generated
types and test drift. Avoid handwritten duplicate domain definitions.

| Family | Operations |
| --- | --- |
| `/auth/telegram/*`, `/session`, `/sessions` | Start/callback, current account, logout/revoke sessions |
| `/capabilities`, `/preferences`, `/models` | Configured availability, limits, defaults, effective settings |
| `/projects`, `/threads` | Owner-scoped CRUD, archive, move, pin, revisions, Telegram continuation |
| `/threads/:id/messages`, `/runs/:id` | Cursor-paged transcript, idempotent send, run snapshot, cancel, explicit retry |
| `/events` | One authenticated account SSE stream: active-run events and resource invalidations |
| `/files`, `/files/:id/content` | Bounded multipart upload, attach existing, authorized download/preview/delete |
| `/audio/*` | Transcription/speech through existing audio services and metering policy |
| `/memories`, `/skills`, `/connectors` | Same personal resource records, search/CRUD and validated actions |
| `/agents`, `/automations` | Existing domain operations, explicit destinations, versions and run history |
| `/account`, `/account/ledger`, `/billing/*` | Allowance, wallet, costs, top-up handoff/status |
| `/search`, `/exports`, `/privacy/*` | Scoped search, bounded export, clear/delete operations |

Errors have stable codes, safe text, field errors, retriable flag, and request/run ID.
Include distinctions for unauthenticated, forbidden/not found, conflict/busy, quota,
unconfigured capability, provider throttle/unavailable, moderation, upload limits,
context limit, interrupted run, and expired media. Never return internal tracebacks.

### SSE and run durability

- Use HTTP commands + SSE rather than WebSockets initially: no real-time voice duplex
  or collaboration requirement. One stream per tab/account avoids per-thread connection
  multiplication; optional cross-tab sharing only after profiling.
- Events carry schema version, unique cursor, thread/run/object IDs, sequence, type, and
  sanitized payload. Types include run accepted/started/activity/delivery/completed/
  failed/cancelled/interrupted, usage settled, and resource changed/deleted.
- Persist accepted input/run state before acknowledging. Reconnect with Last-Event-ID
  or an explicit cursor; deduplicate IDs. Cursor expiry triggers snapshot resync.
  Order snapshot and event subscription so no changes fall between them.
- Keep small transient deltas coalesced in memory; persist final visible messages and
  bounded safe replay events, not every token or raw provider event indefinitely.
- Heartbeats, bounded subscriber buffers, slow-client disconnect/resync, proxy buffering
  disabled, and explicit idle timeouts. Check session validity/revocation on long-lived
  streams and stop on logout/expiry. No tokens in SSE query strings.
- Leaving a page or losing the connection does not cancel a server-accepted run. Stop is
  an explicit idempotent command. Reopening shows the persisted state.
- Restart marks unfinished in-process work interrupted and reconciles known usage.
  Never auto-resume paid/tool-side-effect runs. Explain when external side effects may
  already have happened; a retry is a new deliberate attempt, not guaranteed rollback.
- Record actual usage on errors/cancellation where available. If final cost is unknown,
  show pending/unknown, not free. Test reconciliation and duplicate callbacks.

## 6. Information architecture and spatial interaction

### Design concept

**On this screen, Skye's one conversation with shared memory becomes a quiet conversation
canvas with an inspectable context edge.** The distinctive element is not ornament:
“Context” explains which project instructions and personal resources are available,
and safe run evidence shows what was actually used. Never imply an enabled connector
was called or an available memory was injected when the backend cannot confirm it.

This is an **app screen**, not a landing page. Use the design-taste app-screen workflow:
inventory actual data/jobs, write each screen's one question, deal an app direction with
`--keep palette,type`, choose and record the style/seed, then inspect actual screens.
Dealing and visual critique are Stage 1 deliverables, not claimed as completed here.
Do not apply the marketing-page picture or animation floors to a chat client.

### Shell

- **Leading sidebar:** Skye mark/name, New thread, Search; Projects and recent/pinned
  threads; a compact Library destination for Memory, Connectors, Skills, Agents, Files,
  Automations. Account/settings at the foot. Progressive lists, not all items forever.
- **Center:** compact project/thread breadcrumb and title, optional status, conversation,
  composer. Preserve multiple short Skye replies. Assistant text can use a quiet/ghost
  Bubble variant; user messages use a subtle neutral surface, not giant colored pills.
- **Context edge:** closed by default. A labeled trigger opens a nonmodal secondary pane
  on wide screens, a Sheet/Drawer on narrower screens. Show effective project instructions,
  memory policy, resource availability, attached files, and run details as relevant.
  Do not trap focus in a nonmodal desktop pane.
- **Project view:** thread list first, instructions summary, recent files, New thread.
  Avoid a grid of identical feature cards. “No project” is an explicit move/select choice,
  not a synthetic project the user cannot understand or delete.
- **Library views:** routable master/detail lists for substantial management. A dialog
  is an editor, not the only way to navigate a full management application.
- **Account:** shared allowance, Sparks balance, ledger, top-up and active sessions.
  No subscription language. Counts and money come from the same authoritative snapshot.

Candidate routes: `/login`, `/chat`, `/chat/[threadId]`, `/projects/[projectId]`,
`/library/{memory,connectors,skills,agents,files,automations}`, and
`/settings/{general,account,privacy,sessions}`. Preserve deep links and browser back.
Use URLs for selected objects and shareable-in-account filters, not for secrets or
message text. Drafts are keyed by account/thread; do not put sensitive drafts in URLs.

### Screen questions

| Screen | First question / primary action |
| --- | --- |
| Chat | “Where did we leave off, and what is Skye doing?” / Send |
| Project | “Which conversation belongs to this work?” / New thread |
| Memory | “What does Skye remember, and where does it apply?” / Add memory |
| Connectors | “Which apps can Skye use, and which need attention?” / Connect app |
| Skills | “What have I taught Skye?” / Upload skill |
| Files | “Which files can I use now?” / Upload file |
| Agents | “Which specialist is active, with which permissions/version?” / Select or create |
| Automations | “What will run next, where, and at whose cost?” / Create automation |
| Account | “What is available, and what did my requests cost?” / Top up |

### Overlay hierarchy: depth with restraint

| Surface | Job and guardrail |
| --- | --- |
| DropdownMenu / ContextMenu | Thread actions; context menu always has a visible kebab equivalent. |
| Popover / Combobox / Command | Project/model/agent selection, file attachment picker, global search. |
| Tooltip / HoverCard | Short optional explanation or source preview; never the sole path to essential information. |
| Dialog | Create/rename project, edit memory, upload skill review, connector configuration. |
| Sheet | Context, file details/preview, tool evidence, project instructions without losing chat. |
| Drawer | Thumb-friendly mobile picker/preview; same content/behavior as desktop, not another navigation tree. |
| AlertDialog | Irreversible deletion, reset, revoke, or consequential external action confirmation. |
| Toast | Short success/undo; persistent actionable error also stays by its failed field/message. |

Normally one modal at a time; a confirmation may be its one child. Close the picker/menu
before opening an editor. Base UI owns layering, Escape, focus containment/restoration,
and portals; no manual overlay z-index ladder. Every dialog/sheet/drawer has its Title.
Long overlays scroll internally with overscroll containment and visible footer actions.
On mobile, Back/Escape returns one layer, with draft/selection/scroll preserved.

### Responsive composition

- Wide: roughly 240–272px sidebar, fluid conversation, optional 320–384px context pane.
  Keep prose around 60–75 characters; let code, images, and previews use more canvas.
- Tablet: fold navigation when content no longer fits; context overlays rather than
  squeezing a third column. Offer keyboard-accessible resize only if it improves work.
- Phone: one region at a time; nav Sheet, conversation, full-width detail route or Drawer.
  16–20px margins, 44px touch targets, visible Back and context actions.
- Test 1440, 768, 390 **and 320 CSS px**, 200% text zoom and 400% browser reflow;
  physical devices for virtual keyboard, safe areas, recording, and viewport changes.
  Use dynamic viewport units and min-size constraints; never hide Send behind the keyboard.
- Support long titles, long URLs, large code blocks, tables, multilingual text and bidi
  messages. Logical layout properties, `dir="auto"` where appropriate, no CSS visual
  reordering that breaks the reading order. Wide tables scroll inside their own region.

## 7. shadcn-first composition and theme

The installed kit already contains the following primitives. Reuse and inspect them;
do not re-add them or replace them with hand-built lookalikes.

| Use | Installed components |
| --- | --- |
| Shell/navigation | Sidebar, Breadcrumb, Collapsible, Command, Kbd, Resizable (only if needed) |
| Conversation | MessageScroller + its provider/viewport/items/button, Message, Bubble, Attachment, Marker, Trace |
| Rich responses | CodeBlock, Table, Accordion, AspectRatio, Carousel only for genuine galleries |
| Composer | Field, InputGroup, InputGroupTextarea, InputGroupAddon, Button, Tooltip, Attachment |
| Forms | FieldGroup/Field, Input/Textarea, Select/Combobox, Switch, Checkbox, RadioGroup, ToggleGroup |
| Editors/details | Dialog, Sheet, Drawer, Tabs, ScrollArea, Item, Card with full composition where warranted |
| Feedback | Alert, Empty, Skeleton, Spinner, Progress, Badge, Base UI Toast |
| Actions/confirmations | DropdownMenu, ContextMenu, Popover, AlertDialog, ButtonGroup |
| Scheduling | Calendar/date-picker composition, timezone Combobox, native time input where sufficient |
| Ledger/lists | Table, Pagination, Checkbox for meaningful bulk actions; Chart only for real useful usage history |
| Optional structured input | Questionnaire for backend-supported clarification/approval, not a fictitious agent capability |

Do not use every component simply because it is installed. InputOTP, NavigationMenu,
Menubar, sliders, charts, and carousels are unnecessary until a real task calls for them.
Installed does not mean eagerly bundled: import used components directly, lazy-load
heavy previews/code highlighting/management editors, and measure bundle growth.

Custom code should mostly be domain compositions and data adapters: AppShell,
ThreadNavigation, Conversation, Composer, ContextPanel, and resource list/editor
features. These are not new primitive libraries. Necessary custom adapters include
safe Markdown rendering, API/events, recording, and attachment presentation.
`MessageScroller` owns follow/anchoring/jump-to-latest; do not write a parallel scroll hook.
Use Trace/TraceLine for safe tool activity, Attachment for media, Marker for system notes.

Implementation rules: Base UI `render`, not Radix `asChild`; Hugeicons objects;
`@/components/ui/*` imports; `cn()` for conditions; flex/grid `gap`, not `space-*`;
semantic colors, no scattered raw hues or manual `dark:` colors. Component variants own
appearance, call-site classes own layout. Forms use proper groups/labels/validation;
select/menu items stay inside their Group. Use Base UI `toast`, not Sonner.
Run `npx shadcn@latest docs <component>` and fetch the returned docs before changes;
some chat doc links were missing from CLI discovery despite official pages existing.
Inspect local source and official documentation rather than guessing the API.

### Skye tokens

Source palette from `web/colors/colors.txt`: `#4EA8DE`, `#5390D9`, `#5E60CE`,
`#6930C3`, `#7400B8`. Treat `skye.ase` as the companion swatch asset; validate it
against the text palette in Stage 1 (the binary file was not decoded during planning).

- Keep `base-luma`, existing radius/density, Geist, and neutral surfaces. Adjust tokens in
  **`web/app/globals.css` only**, using its existing OKLCH / `@theme inline` system.
- Choose one principal brand role from Skye blue; retain the purple family for the brand
  mark or one deliberate primary role if needed, not five simultaneous accent categories.
  No mandatory font change or wholesale preset application.
- Map primary/foreground, ring, links, selection, sidebar roles, muted text, borders,
  destructive and actual status roles for light/dark. shadcn `accent` is an interactive
  surface role, not a reason to saturate every hover background.
- Preserve brand colors despite design-taste's generic violet/indigo ban: this is an
  explicit existing-brand exception. Record any inspector `--allow` narrowly for the
  retained brand asset/hue, not as a blanket contrast or accessibility exemption.
- Measured WCAG contrast for **solid swatches**, not rendered UI:

  | Swatch | White text | Black text |
  | --- | --- | --- |
  | `#4EA8DE` | 2.63:1 | 7.98:1 |
  | `#5390D9` | 3.30:1 | 6.36:1 |
  | `#5E60CE` | 5.20:1 | 4.04:1 |
  | `#6930C3` | 7.47:1 | 2.81:1 |
  | `#7400B8` | 8.63:1 | 2.43:1 |

  Thus white small text on the two original blues is not acceptable. Use dark text on
  those fills or derive a darker blue for a white-label primary. Measure actual rendered
  pairs, alpha composition, focus states, and both themes before approving tokens.
- Body/control text ≥4.5:1; large text ≥3:1 where applicable; essential boundaries and
  focus ≥3:1. Color never carries status alone. No danger styling for neutral disconnect
  navigation or ordinary project selection.
- Chat body 16px with unitless 1.5–1.6 leading, UI usually 14px, meta 12–13px. Mobile
  inputs stay 16px without blocking browser zoom. Use tabular figures for cost/timers.
- App motion is feedback only: no entrance choreography, typewriter text, shimmer
  requirement, or animated row hovers. Honor reduced motion in installed primitives too;
  audit rather than assuming upstream defaults conform. Suppress theme-switch transitions.

## 8. Feature completeness and honest behavior

| Area | Required experience / backend work |
| --- | --- |
| Threads | Create, rename, pin, archive/unarchive, delete with consequence, paged history, optional project, move, search, drafts and stable URLs. One active run per thread; other threads remain usable. |
| Projects | Multiple threads, instructions editor, explicit default/new-thread behavior, effective-context summary, no orphaned automations on deletion. Preserve legacy names/emoji as user data; don't add decorative emoji throughout UI. |
| Chat input/output | Multiline text, paste, Enter/Shift+Enter preference, IME composition safety, quoted reply, copy, safe Markdown, lists/tables/code, source links, multiple assistant deliveries, explicit failed-send retry. |
| Run activity | Truthful “Working”, “Searching the web”, “Creating an image”, “Waiting for Gmail”, Stop, elapsed time, safe completed/error evidence. No fake percentages or fabricated tool progress. |
| Images/files | Upload/paste/drop with real file-input alternative, attachment picker, remove before send, image edits against exact saved files, previews/downloads, generated artifacts, availability and expiry. Never guess source images. |
| Voice | Feature-detected recording, permission/HTTPS errors, cancel/stop, duration/size limits, preview/transcript before sending, upload fallback, generated speech with transcript and accessible playback. No autoplay. Reuse Python speech services. |
| Web/code | Linked citations and accessible source details; safe tool status and generated-file results. No exposed Docker terminal, raw secrets, unrestricted executable HTML, or private reasoning. |
| Memory | Search/categories, add/edit/delete, memory-enabled preference and explicit scope, confirmation/undo as appropriate. Preserve 500-character service limit. Editing and project-only memory require explicit service extensions. |
| Connectors | Search catalog, connected/pending/reconnect/unavailable states, provider consent redirect and return, server-verified connection outcome, disconnect, custom MCP URL + masked credential replacement, effective access explanation. |
| Skills | Upload SKILL.md or zip, reuse archive validation/limits, inspect description/files/instructions before install, download/remove, duplicate-name resolution. Enable/disable and version replacement need new backend support if offered. |
| Agents | Browse installed/owned, create/edit instructions, capabilities/model, active selection, version/install semantics, visibility/share links only with explicit consent and permissions. |
| Automations | Create/edit/pause/delete, timezone and next run in words, stable target thread, manual test with cost warning, last-run outcome, offline completion, webhook secret reveal/copy/rotate behind authorization. |
| Models/preferences | Server capability catalog, text/image choices, supported reasoning controls, clear unavailable selection/fallback behavior, shared account defaults; thread overrides only after runtime honors them. |
| Account/Sparks | Same daily/monthly free allowance and reset times, wallet and ledger, per-run breakdown, provider-cost precedence, connector flat costs, display preference. No mocked subscription tiers. |
| Payments | Select a real package and hand off to Telegram Stars invoice/bot flow. Return stays “Payment pending” until the backend sees authoritative payment; poll/events update wallet. Browser success query parameters never credit funds. |
| Search/export/privacy | Search only authorized visible transcript/resources, jump to message, clear filters, explicit content retention, bounded authenticated export, deletion/cancellation policy and device revocation. No public share-by-default. |

Useful additions beyond direct parity: keyboard command search, unread completion markers,
explicit context provenance, connection freshness, draft recovery, reconnect-safe runs,
and per-thread cost/run details. Defer message branching/regenerate/edit-history until
their context and billing semantics exist; never overwrite history or silently repeat
connector side effects. “Catch up” can reuse Skye's existing workflow, targets a named
thread, and is metered like a normal run rather than background-generated on every visit.

## 9. State, feedback, and accessibility contract

Every feature ships its initial, empty, loading, populated, stale, unavailable,
unauthorized, validation-error, server-error, and mutation-pending states where applicable.
Skeletons preserve geometry; refresh keeps existing content. Spinner + text for unknown
work; determinate Progress only when real bytes/steps are measurable. Do not leave an
indefinite spinner after timeout or announce every token/loading tick to screen readers.

| Situation | User sees / can do |
| --- | --- |
| First visit | “Start a thread” in the conversation frame; no fake history or invented suggestions presented as personal knowledge. |
| Sending | Pending message identified as sending; acknowledge persisted acceptance before “Sent”. Duplicate submission guarded server-side. |
| Already running | “Skye is still working in this thread.” Open run or Stop; preserve draft, do not silently queue a paid request. |
| Offline/reconnecting | Keep history/draft; “Connection lost. Reconnecting…” and retry. Never show cached data as freshly synchronized. Do not auto-send later. |
| Run ongoing in background | Status in thread navigation; return to its actual run snapshot, not a reset spinner. |
| Provider/tool failure | Explain the failed operation and a next action beside it; distinguish final failure from successful fallback. Detailed safe run ID available. |
| Interrupted/restart | Preserve delivered parts; “This run was interrupted. Review what completed before trying again.” No automatic side-effect replay. |
| Stop | “Stopping…” then confirmed “Stopped”; explain external actions may already have completed, and show actual/pending usage. |
| Quota/low funds | Allowance/wallet explanation, real reset time or Top up; retain unsent text/files. |
| Connector revoked | “Reconnect Gmail to continue.” Direct action; don't imply a retry alone restores permission. |
| File missing/evicted | “This file is no longer available. Upload it again.” Preserve filename/reference and past messages. |
| Save conflict | Show newer server data and keep local edits; choose review/reapply, never silent last-write-wins. |
| Session expired | Re-authenticate without leaking another account's data; draft recovery is account-bound and optional. |
| Delete/reset | Object and consequences named, confirmation for irreversible work, undo for reversible archive/move. |

Accessibility acceptance:

- WCAG 2.2 AA; native semantics via shadcn/Base UI, visible keyboard focus, named icon
  actions, complete keyboard paths, skip-to-conversation/composer, meaningful landmarks.
- Route changes update title and focus appropriately; incoming messages never steal
  composer focus. Restoring older messages preserves viewport anchor.
- Coordinate MessageScroller's built-in announcements with one centralized status/error
  announcer. Do not double-announce each Trace and stream delta. Announce meaningful
  transitions/completed replies; urgent alerts only for urgent failures.
- Labels are not placeholders. Field errors use `data-invalid`, `aria-invalid`, and
  described error text; focus the first invalid field on submit.
- Menus/popovers have keyboard behavior; modal focus returns to the trigger; nonmodal
  context remains navigable. Hover-only actions have focus/touch equivalents.
- Truncation always has an accessible full-value path; essential errors do not live in
  expiring toasts. Informative image alternatives and audio transcripts are available.
- Reduced motion, forced colors, text-spacing overrides, 320px reflow and zoom are tested.
  Drag/drop/reorder always has a simple button/menu alternative.
- Copy uses Skye's calm, short, warm voice, sentence case, verb-first actions, and one
  vocabulary: Project, Thread, Memory, Connector, Skill, Agent, Automation, Sparks.
  No “Oops”, generic “Something went wrong”, blame, fake certainty, or recovery-free errors.
- Locale-ready whole messages and `Intl` dates/numbers from the start; keep English UI
  copy initially if needed, but support multilingual conversation and bidi content.

## 10. Security, privacy, operations, and performance

- Test cross-account IDOR on every route and event/media subscription, including cursors,
  deleted resources, payment status, export jobs, and guessed attachment IDs.
- Same-origin cookie authentication; origin/CSRF enforcement, strict allowed hosts and
  proxy trust, bounded request/upload sizes, rate limits for login/send/upload/search.
- Reuse access/ban/moderation and provider concurrency rules across channels. Do not
  accidentally give logged-in web users owner/admin privileges.
- Sanitize Markdown with raw HTML disabled, safe link protocols, safe highlighting,
  escaped code and no executable generated content in the application origin. Untrusted
  SVG/HTML downloads as attachments or serve previews from a sandboxed isolated origin.
  Prevent path traversal, content sniffing, archive bombs, and unsafe MIME previews.
- MCP setup needs SSRF defenses: deny private/link-local/metadata destinations by default,
  validate DNS and redirects, guard rebinding, and only permit private network targets
  through explicit self-host operator configuration. Mask secrets; never include headers,
  provider tokens, webhook authorization, or connector raw output in events or logs.
- Existing connector headers are persisted in SQLite. Decide encryption at rest using
  an environment-held key and migration/rotation policy before broad web credential editing;
  never claim secrets are encrypted without implementing it. Protect database/backups too.
- CSP and security headers verified against OIDC, media previews, and Next.js behavior;
  no insecure broad wildcard added just to make a provider popup work.
- Separate “capability disabled by this deployment” from “your authorization expired”.
  `/capabilities` exposes availability and limits without secrets; unavailable features
  have an explanation, not dead controls.
- Metadata-only structured logs with transport/account/thread/run/request correlation;
  redact URL queries, auth codes, cookies, exception text containing message/tool content.
  Record timing/errors/cost metrics, not conversation text. Dozzle stays authenticated.
- Page histories and search with stable cursors; indexes for owner/project/updated time,
  thread sequence, run state, and search. Bound replay and exports. Add full-text indexing
  only for visible authorized content; delete its entries with content.
- Lazy-load heavy management/preview/highlighting code, use existing MessageScroller
  content visibility, and introduce virtualization only after profiling and accessibility
  tests. Avoid a blanket custom virtualizer that breaks find/selection/reading order.
- Initial budgets: p75 LCP ≤2.5s, INP ≤200ms, CLS ≤0.1 on representative mobile; measure
  application send acknowledgement separately from provider latency. Load-test stream
  subscribers, concurrent payer requests, long histories, media and slow clients.
- Graceful shutdown rejects new runs, resolves/marks active work consistently, and closes
  HTTP, scheduler, polling, database and streams. Restart never creates a second scheduler.
- Health/readiness distinguish Python, SQLite, Next.js, provider configuration, and
  temporary upstream failure. Do not publish sensitive diagnostics to anonymous clients.

## 11. Phased implementation and acceptance gates

Every stage includes schema/API tests and UI states for what it introduces. UI work
does not defer accessibility and error handling to the final stage.

### Stage 0 — Lock contracts and prove the risky edges

Dependencies: none. Deliver a small executable spike plus decision records, not production UI.

- [x] Decide nested `web/` repository ownership/tracking without discarding user work.
- [x] Agree private-first scope, transcript retention, default Skye mapping, project deletion,
      shared-resource semantics, Telegram notification/routing behavior, and automation targets.
- [x] Fixture representative legacy sessions: tool-delivered bubbles, fallback reply, voice,
      images/files, empty project, old private conversation, group topic, cancelled run.
- [ ] Validate BotFather setup and real OIDC code flow, `id`/`sub`, nonce behavior, no UserInfo,
      session strategy and chosen Python OIDC library. Obtain credentials outside source control.
- [x] Prove Next.js + Python same-origin ingress and a nonbuffered SSE heartbeat/reconnect.
- [x] Choose typed contract generation and small test dependencies; document new dependencies.
- [x] Record API/error/event shapes, migration map and rollback/backup procedure.

Evidence: `docs/web-foundation.md`, Python contracts/projection tests and isolated lab.
The Next.js rewrite probe measured a 0.003s heartbeat and replayed only events 3/4.
Authlib + joserfc signed-token/PKCE/state tests pass, but no live-provider login was run.
The unchecked OIDC item requires operator credentials and a registered origin; Stage 0's
existing-account exit gate is therefore **not passed**. No production auth is installed.

**Exit:** existing-account login links correctly; sample history has a safe visible projection;
SSE survives the intended ingress; unresolved identity/privacy questions block later stages.

### Stage 1 — Design foundation and shadcn shell

Dependencies: Stage 0 scope decisions; can use fixtures while shared backend work proceeds.

- [x] Inventory real data/jobs; deal and record app style/seed with retained palette/type.
- [x] Make a compact `web/DESIGN.md`: token roles, density/type, shell, context edge,
      overlay rules, screen questions, copy vocabulary and state fixtures.
- [x] Verify ASE palette; implement slight token adjustments in existing globals, both themes.
- [x] Build reusable shell/navigation, chat framing/composer, context panel, project view and
      routable library framing from installed primitives. No backend claims from fixture data.
- [x] Create developer-only state previews for empty, loading, failed, running, long content,
      low funds and narrow layouts; prevent fixtures/debug routes appearing in production.
- [x] Inspect screenshots at 1440/768/390 plus 320px/zoom, keyboard/focus and reduced motion.

Evidence: `web/DESIGN.md` and `web/docs/foundation-verification.md`. Browser suite:
33 passed across Chromium/Firefox/WebKit; production build and fixture gates pass.
Python regression suite: 538 passed. Baseline carousel lint failure and npm audit findings
remain disclosed. This stage is a disconnected shell, not working chat/resource CRUD.

**Exit:** recognizable Skye shell, uncluttered default chat, complete navigation and overlay
focus behavior, measured accessible tokens. No fake working chat or invented usage figures.

### Stage 2 — Canonical threads, migration, and shared turn orchestration

Dependencies: Stage 0 contracts.

- [x] Add versioned schema for threads/projects/bindings/visible transcript/runs and revisions.
- [x] Migrate existing sessions repeat-safely; validate ownership, counts, instructions, files,
      defaults and group/topic behavior. Preserve backups and legacy lookup during cutover.
- [x] Extract shared turn/admission/settlement services; use canonical run keys and transport.
- [x] Implement per-payer concurrency safety, run-id-based idempotent billing, cancellation,
      delivery receipts, interrupted-run state and safe activity/visible-message projection.
- [x] Adapt Telegram projects, thread selection, reset/delete/stop/retry and automation routing
      to shared services. Explicitly decide command semantics where a project now has many threads.
- [x] Keep metadata-only logs; document actual storage and retention consistently.

Implemented/tested: per-payer/thread serialization, durable deduplication, delivery-gated
atomic run-ID settlement, cancellation/interruption, text/voice/image/document receipts,
24-hour allowlisted activity, default-only instructions, `/threads`, group exclusion/reset,
retained project history and pinned private automation firing. Historical backfill is
cutover-bounded and conservative, with per-thread coverage. Unknown or unaffordable cost
is held for explicit operator reconciliation rather than charged or marked free.
**Not yet exercised end-to-end with the live bot under the flags.** Migration was
rehearsed on server-side copies only; the actual cutover requires downtime and a fresh backup.

**Exit:** Telegram behavior passes regression tests; one project can hold independent threads;
both adapters can invoke one shared service without duplicate execution or charges.

### Stage 3 — Production authentication and owner-scoped API

Dependencies: Stage 2 ownership model; incorporate Stage 0 OIDC spike.

- [x] Integrate Python HTTP startup/shutdown into existing bootstrap behind a feature flag.
- [x] Implement OIDC login/callback, hashed opaque sessions, CSRF, revocation and rate limits.
- [x] Add authenticated capability/preferences/project/thread/history endpoints and generated TS.
- [x] Add Next.js login/protected routes, server-fetch adapter, safe errors and no-store behavior.
- [x] Test wrong claims, replay, stale state, bad callbacks, missing profile ID, unknown key,
      account mismatch, expired/revoked session and cross-user requests.

Evidence: 586 Python tests, 33 foundation browser tests, plus synthetic two-account
Next.js → Python read-only rendering/axe/logout checks in all three browser engines.
**One real existing Telegram account passed live OIDC** signature, issuer, audience,
nonce, canonical decimal-string `id` and existing-account checks through the registered
`/auth/callback`. A second real account is still required for the production exit.
Live-data migration/restore passed on private server copies (13 projects, 5 groups,
28 projected messages, zero repeat imports), not on the running database. Web
sending/streams remain absent; the temporary OIDC lab must be removed.

**Exit:** two real accounts remain isolated across UI, API, caches, media placeholders and
streams; existing Telegram resources appear under the correct web account.

### Stage 4 — Text chat vertical slice and cross-channel synchronization

Dependencies: Stages 1–3. This is the first restricted internal alpha, not the full release.

- [ ] Send text idempotently, accept background run, commit multiple visible replies,
      safe activity and settlement; implement snapshot + replay SSE and resource invalidation.
- [ ] Bind MessageScroller to cursor history and real deliveries; safe Markdown/code/citations.
- [ ] Add New thread, titles, project/unassigned selection, move/archive, drafts and keyboard send.
- [ ] Implement explicit Telegram continuation/thread selection and bidirectional updates.
- [ ] Add Stop, failed-send retry, run details, offline/reconnect, busy, moderation, context-limit,
      provider-error and interrupted states. Do not expose private raw assistant output.
- [ ] Revalidate changed memory/skills/connectors/preferences in web after Telegram mutations,
      including model-tool mutations; publish events at the shared service/repository boundary.

**Exit scenario:** start a named thread on web, continue that exact thread in Telegram,
return to web and see the same ordered replies and cost; simultaneous tabs do not double-send;
disconnect/reload does not lose an accepted run or charge twice.

### Stage 5 — Files, images, voice, and safe artifacts

Dependencies: Stage 4.

- [ ] Authenticated bounded uploads, opaque attachment IDs, file metadata/references and
      library picker using existing MediaLibrary and image/tool source rules.
- [ ] Previews/downloads, generated-image/file deliveries and citations; isolate unsafe content.
- [ ] Recording with permission/format detection, transcription review and playback/transcripts;
      server audio endpoints reuse services and explicit metering policy.
- [ ] Handle file limits/eviction/expiry, upload cancellation/retry, duplicate names,
      unsupported media, microphone denial and slow networks without losing drafts.

**Exit:** a Telegram photo can be selected/edited on web and the result reused in the
same account; a web document/voice message works in the shared thread; expired bytes
are represented honestly. No scope leaks or unsafe in-origin previews.

### Stage 6 — Memory, Connectors, and Skills parity

Dependencies: Stage 4 API/events; Stage 5 uploads for Skills. Required for core release.

- [ ] Memory list/search/category/editor, enabled preference, scope explanation and deletion.
- [ ] Connector catalog/detail, consent redirect/return verification, pending/reconnect,
      custom MCP setup/test, masked credentials and safe disconnect.
- [ ] Skill upload/validation/preview/install/download/remove; add version/enable semantics
      only with matching backend implementation and clear source-of-truth rules.
- [ ] Context panel shows effective resources and safe actual-use evidence.
- [ ] Resource changes from web are visible/usable in Telegram and vice versa without re-login.

**Exit:** configure each resource in one channel, use it in the other; revoke a connector
and receive a correct recovery action, reject malicious archives/SSRF targets, and verify
personal/project scope labels match runtime behavior.

### Stage 7 — Agents, automations, models, and account completeness

Dependencies: Stages 4–6.

- [ ] Custom agent CRUD/install/version/visibility/capability/active-agent flows.
- [ ] Automation editor with timezone/next-run preview, stable thread/delivery target,
      pause/test/delete, outcomes, authenticated webhook ingress and secret rotation.
- [ ] Model/image model/reasoning preferences reflect real backend capabilities and defaults;
      expose catalog naming consistent with Skye's documented Sun Engine identity policy.
- [ ] Wallet/allowance/reset timestamps/ledger, per-run usage and costs, Stars top-up handoff,
      pending/success/failure and payment reconciliation. Keep payment validation in Python.
- [ ] Bounded private search, export, privacy/session settings and documented retention.

**Exit:** a schedule fires into its configured thread while another project is active,
result appears in web while offline, metering matches Telegram, Stars payment credits once,
and export/deletion touch only the authenticated user's authorized data.

### Stage 8 — Hardening and six-domain interface gate

Dependencies: Stages 1–7. Run incremental checks earlier too.

- [ ] Backend/contract/frontend/integration/E2E suites; migrations and restored-backup rehearsals.
- [ ] Security tests for sessions, CSRF, IDOR, replay, XSS, uploads, SSRF, event authorization,
      secret redaction, payment tampering, rate limits and revoked long-lived connections.
- [ ] Slow network, provider outage, duplicate Telegram update/send/payment, cancellation races,
      concurrent payer requests, cursor gaps, scheduler restart and disk-full behavior.
- [ ] Measure p75 performance, stream/backpressure limits, query plans and realistic long histories.
- [ ] Run design-taste app lint/inspector on representative real-data routes, open **every**
      screenshot, record app critique, fix top three issues, re-inspect final state.
- [ ] Complete better-interface review in order: Accessibility → Layout → Writing → Typography
      → Colors → UI. Inspect empty/loading/error/narrow states; cite file:line and runtime evidence.
- [ ] Produce one ranked report using the skill's `review-format.md`: scope/coverage, ≤15
      consolidated root causes, verification and Block/Approve. Never mark unseen domains Clear.
- [ ] No HIGH remains: unnamed/unfocusable controls, ignored reduced motion, clipping at
      320px/200%, insufficient contrast, color-only meaning, inaccessible truncation,
      recovery-free errors, or unsafe destructive actions block release.

**Exit:** no unresolved security/data/billing blocker or HIGH interface finding; all critical
flows tested with keyboard and representative screen readers, not just automated scores.

### Stage 9 — Optional web deployment, staged rollout, and documentation

Dependencies: Stage 8.

- [ ] Compose profile for Next.js/ingress; Python remains one process/writer. Reproducible
      npm/uv builds, health checks, environment examples and CI in the correct repository.
- [ ] Document OIDC BotFather URLs/credentials, TLS, internal origins, SSE buffering/timeouts,
      storage/backup/restore, session/secret rotation and capability configuration.
- [ ] Private operator alpha → invited users → opt-in release → general availability.
      Gate web access without restricting existing Telegram users.
- [ ] Observe login errors, failed/duplicate runs, settlement discrepancies, reconnect loops,
      delivery failures and accessibility feedback without collecting message bodies.
- [ ] Rollback runbook: disable web ingress/feature, retain canonical data and compatible
      Telegram adapter. After new writes, roll back code compatibly; never restore an old
      database and discard new conversations/payments as a routine rollback.
- [ ] Update README/product docs and storage/logging claims. Publish known limitations and
      support/payment/privacy paths; keep bot-only self-host instructions valid.

**Exit:** a fresh self-host install and an existing bot upgrade both work; backup restore
and web-disabled fallback are rehearsed, no duplicate polling/scheduler exists.

### Delivery milestones and dependency order

```text
Stage 0 ──┬─ Stage 1 ─────────────────┐
          └─ Stage 2 → Stage 3 ───────┴→ Stage 4 → Stage 5 → Stage 6
                                                               ↓
                                                    Stage 7 → Stage 8 → Stage 9
```

- Internal text alpha: Stage 4. Not advertised as full feature parity.
- Core personal beta: Stages 5–6 plus working account/paid admission and relevant Stage 8
  checks. If account UI is unfinished, do not open paid web use publicly.
- Comprehensive personal release: Stages 7–9 complete.
- Group web workspaces, strict project-isolated resources, and message branching are
  separate follow-ups, not hidden dependencies of personal parity.

## 12. Verification plan and research record

### Commands for implementation gates

```bash
# Repository root
uv run ruff check .
uv run mypy
uv run pytest

# web/ (existing scripts)
npm run lint
npm run typecheck
npm run build

# Add browser/interaction tooling deliberately during Stage 0/1:
# Playwright + axe; frontend behavior tests for event reducer/composer/resource forms.
# Use local skill paths resolved in the implementation environment:
node <design-taste-frontend>/scripts/lint.mjs --app web/app web/components
node <design-taste-frontend>/scripts/inspect.mjs --app <local-authenticated-route>
```

The browser runner must establish a test session on a local, non-production test account;
never paste real session cookies or personal transcripts into screenshot artifacts.
Run at least Chromium, Firefox, WebKit automated flows; manually test VoiceOver/Safari,
NVDA with a supported desktop browser, touch/mobile keyboard, recording and permission UI.
Target current and previous major evergreen browser versions; feature-detect recording
formats and non-Baseline enhancements, with plain upload/native-control fallbacks.

### Required end-to-end scenarios

1. Existing account OIDC login restores projects, memories, skills, connectors and wallet;
   new account is genuinely empty; another account cannot read any of them.
2. Several threads in one project and unassigned threads stay context-independent;
   Telegram continuation targets the selected thread, not the browser's last route.
3. Simultaneous Telegram/web sends and parallel threads preserve run ordering and payer
   admission. Duplicate HTTP/update/SSE/payment delivery produces no duplicate spend.
4. Network loss after acceptance, refresh, session expiry and process restart each have
   a truthful recoverable state, without replaying a connector action or leaking thoughts.
5. Photo/document/skill/voice round-trips and expired media behavior across channels.
6. Memory/skill changes and connector revocation immediately affect the same runtime;
   no misleading project-only scope or visual-only tool permissions.
7. Schedule/webhook targets the right thread, obeys access/quota rules, survives UI being
   closed, and leaves visible run/usage evidence with no credential exposure.
8. Stars payment pending/confirmed/refunded flow, per-run costs and free allowance
   reconcile; return from Telegram alone does not assert payment success.
9. All key flows complete keyboard-only, at narrow width/zoom, with long and bidi text;
   screen-reader announcements remain useful during chat activity and overlays.
10. Archive/move/delete/export and session revocation have correct retention, confirmation,
    authorization, event invalidation and recovery semantics.

### Research completed for this plan

- Read existing backend/frontend source and conventions listed above, including installed
  Next.js documentation. Ran `npx shadcn@latest info --json` in `web/`: confirmed installed
  Base UI `base-luma`, Hugeicons, aliases, preset and component inventory.
- Ran shadcn docs discovery for chat/shell/overlay primitives; fetched official Trace,
  Sidebar and Dialog docs. CLI lacked links for several chat primitives; local source
  confirms MessageScroller uses `@shadcn/react/message-scroller`.
- Fetched Telegram login documentation and live discovery; actual BotFather credentials,
  real-account callback claims, nonce round-trip and login were **not tested**.
- Read all six better-* owning skill briefs and design-taste app-screen guidance.
  These inform implementation acceptance, **not an approval of unbuilt screens**.
- Searched Modern Web Guidance for streaming announcements and retrieved/read its
  accessibility guide. Plan uses restrained announcements: “Debounce frequently-changing
  regions” and “Don't add live-region updates to inert DOM”. No frontend implementation
  or browser verification was performed.
- Computed swatch contrast using WCAG sRGB linearization/luminance against solid white
  and black. These are not claims about current or future rendered component contrast.
- Checked Git status in both repositories to identify existing user work; did not alter it.
- **Not run:** application test suites, build, live UI preview, inspector, screenshots,
  keyboard/screen-reader audits, integration/security/load tests. Only this plan is added.

### External references

- Telegram Login/OIDC: <https://core.telegram.org/bots/telegram-login>
- Live discovery: <https://oauth.telegram.org/.well-known/openid-configuration>
- JWKS: <https://oauth.telegram.org/.well-known/jwks.json>
- shadcn Trace: <https://ui.shadcn.com/docs/components/base/trace>
- shadcn Sidebar: <https://ui.shadcn.com/docs/components/base/sidebar>
- shadcn Dialog: <https://ui.shadcn.com/docs/components/base/dialog>
- Installed-version Next.js guidance:
  `web/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`,
  `15-route-handlers.md`, `16-proxy.md`, and
  `web/node_modules/next/dist/docs/01-app/02-guides/authentication.md`.

## 13. Decisions to confirm before implementation

These are gates with proposed defaults, not reasons to delay writing the plan:

1. **Repository:** keep `web/` separate with an explicit deployment reference, or incorporate
   it into the parent repository through a user-approved migration. Preserve its history/work.
2. **Privacy:** approve transcript/event persistence, retention/expiry and migration disclosure;
   current documentation and code disagree. No silent expansion of content retention.
3. **Scope:** private-account release first; group web access separately authorized later.
4. **Resources:** shared personal Memory/Connectors/Skills/files, project instructions per
   thread; no claim that a project isolates the account's personal resources.
5. **Telegram routing:** browser navigation is local; explicit continuation changes the bot's
   selected thread. Optional notifications, not mirrored duplicate messages by default.
6. **Destruction:** project deletion retains threads unless a separate permanent delete is
   explicitly selected; archive is reversible; automation destinations never silently move.
7. **Billing/runtime:** no paid web launch before shared admission, settlement and account UI;
   no raw-model text streaming that violates Skye's delivery-only voice contract.

Next gates: finish **Stage 0 real-provider OIDC verification** with operator credentials
and a registered origin; close Stage 2's remaining receipt/activity/reconciliation work
and rehearse the actual cutover. Stage 3's read-only path is opt-in, not deployed. Do not
treat synthetic isolation tests as real login or enable Stage 4 paid web sending yet.
