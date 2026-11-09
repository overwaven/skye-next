# Foundation verification

Date: 2026-11-07. Scope: PLAN.md Stages 0–1 only.

This is the foundation snapshot, recorded before its local commits. Subsequent gated
Stage 2–3 implementation, current checks and open gates are in the parent repository's
`docs/web-cutover.md`; commit/account-integration statements below describe this snapshot.
The Python test count here is historical: low-signal unit tests were later removed by
policy, and `npm run test:e2e` now always writes `playwright-report/` and
`test-results/results.json`.

## Outcome

Stage 1's disconnected interface foundation is complete. Stage 0's local contracts,
decision records and transport lab pass; its real Telegram OIDC gate remains open.
This is not a working account client or a production-readiness certification.

## Executed checks

| Check | Result |
| --- | --- |
| Python `uv run pytest -q` | 538 passed |
| Python `uv run mypy` | No issues in 44 source files |
| Python `uv run ruff check .` | Passed |
| `npm run contracts:check` | Generated TypeScript matches Python schema |
| `npm run typecheck` | Passed |
| `npm run build` | Passed |
| `npm run test:e2e` | 39 passed: 13 scenarios in Chromium, Firefox and WebKit |
| Targeted ESLint on foundation app/compositions/hooks/lib/scripts/tests/config | Passed |
| `npm run postinstall` | Base UI 1.9.0 patch applied successfully |
| Next.js → Python SSE probe | First heartbeat 0.003s; Last-Event-ID=2 replayed only 3/4 |
| `node scripts/check-production.mjs` | Fixture routes 404; sample navigation and lab rewrite absent |
| Design inspector: chat, project, Memory | Each 0 FAIL / 0 WARN at 1440, 768 and 390px |
| Eight additional foundation captures | No captured console errors or horizontal overflow |

The browser suite checks draft preservation and explicit “Not sent” feedback, command
search, Context at 320/390/768/1440px, all state/library routes, mobile navigation,
Escape and editor focus return, dark appearance, reduced motion and 200% text resize.
Its axe checks include open resource editors and Context. Automated WebKit is not a
real VoiceOver session. A physical-device/screen-reader walkthrough remains release work.
The console assertion excludes only Firefox's known axe-injection microtask diagnostic.

## Six-domain foundation review

| Domain | Coverage and outcome | Remaining boundary |
| --- | --- | --- |
| Accessibility | Named controls, field labels, modal titles, Escape/focus return, visible focus, centralized send announcement and axe checks | No claim of exhaustive WCAG conformance or assistive-technology certification |
| Layout | Screenshots at desktop/tablet/phone; 320px and 200% text tests; Context aside becomes a sheet | Production-length translated/account data still needs review |
| Writing | Clear preview labels, shared-resource explanation, local-only editor disclosure, actionable unavailable-feature feedback | Real API errors and account/billing copy await integration |
| Typography | Retained Geist, 16px conversation text, restrained headings, mobile inputs and readable prose measure | Rich Markdown, code and real attachment typography are later slices |
| Color | ASE swatches decoded and matched to colors.txt; light/dark semantic roles, stronger control boundaries and focus outlines; rendered axe checks | No published exhaustive contrast matrix for every installed unused primitive |
| UI polish | One icon family, quiet surfaces, contextual overlays, reduced-motion overrides, hydrated/settled screenshot capture | Live stream/reconnect and actual-use provenance cannot be judged from fixtures |

Modern Web Guidance accessibility advice informed centralized announcements and focus
behavior. Modal behavior is delegated to Base UI, not an application-built focus trap.

## Visual critique

Direction: **Achromatic ledger / Open plane**, seed **1660668609**, retaining palette
and typography. The existing Skye mark is the only gradient exception.

All 18 chat/project/Memory inspector screenshots were opened and reviewed, plus the
eight foundation captures. Evidence is local under `.taste-skill/inspect/`:

- `{chat,project,memory}/{desktop,tablet,mobile}-{fold,page-01}.jpg` and `report.json`.
- `foundation/`: empty desktop, desktop/mobile Context, desktop project, mobile Memory,
  320px error, dark chat and mobile settings captures.

Subjective scores (not automated grades): hierarchy **4/5**, restraint **4/5**,
responsive composition **4/5**, distinctive identity **3/5**. The shell keeps the
conversation primary, avoids a card maze, and reveals shared context on demand.
Its deliberate neutrality also limits distinctiveness; the mark and Context edge carry
most identity. Empty library routes remain sparse because inventing account data would
be worse. Context's enabled-versus-used distinction needs real run evidence before it
can deliver its full value. This is a coherent foundation, not an award-level claim.

## Issues fixed during verification

1. SSE compression buffered the initial heartbeat through Next.js. The lab now sends
   `Cache-Control: no-store, no-transform`; the real rewrite probe verifies early delivery.
2. WebKit exposed Base UI 1.9.0 VoiceOver focus guards as unnamed buttons. The small
   CJS/ESM patch in `patches/@base-ui+react+1.9.0.patch` adds “Continue in popup” only
   when the library exposes the button role. It preserves library trapping/navigation.
   `patch-package --error-on-fail` makes installation fail rather than silently lose it.
   Reassess/remove the patch on a dependency upgrade; no upstream fix is claimed.
3. Input boundaries, narrow-screen input type size and error recovery spacing were
   adjusted after rendered checks. Reduced motion covers installed primitive transitions.
4. Screenshot capture originally hid carets before hydration, causing measurement-induced
   React mismatches. It now waits for hydration and settled sheets and leaves carets alone;
   the subsequent eight captures report no console errors.

## Open gates and known limits

- **Stage 0 blocker:** no operator OIDC credentials/registered origin were available.
  Signed-token tests prove local verification, not Telegram's actual `id`/`sub` claims,
  nonce round-trip or existing-account match. Follow the root repository's
  `docs/web-foundation.md` (relative to this file: `../../docs/web-foundation.md`).
- **Existing lint failure:** full `npm run lint` still reports
  `components/ui/carousel.tsx:99`, `react-hooks/set-state-in-effect`, in an unused,
  pre-existing primitive. It was not silenced or rewritten as unrelated work.
- **Dependency audit:** npm reported 13 vulnerabilities (2 low, 11 moderate), largely
  tooling/transitive. No force upgrade was performed; assess before release.
- No production migration, restore rehearsal, live account read, model call, payment,
  deployment or bot restart was performed. The lab cannot authenticate the real bot DB.
- Sending, uploading, recording, resource persistence, account balances and Telegram sync
  are unavailable, explicitly disclosed. Fixture thread/project/state routes are dev-only.
- Safe history projection is synthetic and conservative; receipt-backed fallback/media
  backfill, ownership enforcement and production retention belong to later stages.
- Actual production ingress buffering, security/load testing, real-data UI review and
  broader release audits remain later-stage gates. Passing the foundation checks
  does not clear those unimplemented systems.

Both repositories retain uncommitted changes, including pre-existing work. No commit or
push was made; the parent does not automatically track the separate nested web repository.

## Stage 4–5 update (2026-11-07)

Sending, SSE, thread management, uploads and voice transcription are now implemented; see
the parent repository's `docs/web-stage45.md`. Additional evidence:

- `uv run python scripts/verify_web_stage45.py` — 10 API steps through the real aiohttp
  app, stores, TurnService and media library; artifact `docs/web-stage45-e2e.json`.
- `node scripts/verify-stage45-ui.mjs` — connected local browser run through Caddy, Next
  and the API with a deterministic runtime: text send, live tool step, run details, image
  upload and delivery, rename and draft reload; artifact `test-results/stage45-connected.json`.
- The pre-existing carousel lint failure is fixed with a scoped comment; `npm run lint`
  now passes. The dependency audit counts remain disclosed.

The connected voice UI was not browser-automated: headless Chromium's fake audio device
hangs on `getUserMedia` in this environment. The transcription endpoint, media storage and
review path are covered by the API proof, and the recording UI is typechecked and built.
