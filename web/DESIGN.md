# Skye interface foundation

## Direction

**Achromatic ledger / Open plane**, seed **1660668609**, drawn 2026-11-07 for
workspace + inbox/detail/settings with `--keep palette,type`. No redraws.
Chosen over Editorial greeting because repeated, long-lived conversation work needs
quiet tools, not a welcome dashboard. Preserve the dealt move: neutral chrome, one
near-black primary, brand color almost entirely confined to Skye's actual mark.
The existing mark's gradient is an existing-brand asset exception, not a UI motif.

**Idea:** Skye's one conversation with shared memory becomes a quiet conversation
canvas with an inspectable context edge. Context stays closed until requested.
**Face:** a nearly-white cool ground, Skye's real mark, and the familiar short voice.
**Signature:** Context distinguishes project instructions from personal resources and
eventually available resources from actual per-run use. It is not a decorative sidebar.

## Data and jobs

- Objects: personal projects/instructions, optional-project threads, ordered deliveries,
  run status, account-wide memories/skills/apps/files, model preferences and wallet.
- Real limits: 50 current Telegram projects, 500-character memories, 12,000-character
  project instructions, deployment-bounded media and skill archives. Do not invent totals.
- Account-wide resources are not project-private. Each thread has its own transcript.
- Main job: write and resume a thread; second job: inspect the context behind a reply.
- People use Skye for small questions and prolonged work, on desktop and on a phone.
- Broad library functions get routes; the current work gets a context pane/editor.
- Navigation and open popovers are local view state, not synchronized Telegram selection.
- Preview data is synthetic: “Skye, on the web”, “A quieter week” and four short threads.
  Labels and server environment gates distinguish it from real personal account data.

## Screen questions

| Surface | Question |
| --- | --- |
| Chat | Where did we leave off, and what is Skye doing? |
| Project | Which conversations belong to this work? |
| Memory | What does Skye remember, and where does it apply? |
| Connectors | Which apps can Skye use, and which need attention? |
| Skills | What have I taught Skye? |
| Files | Which materials can I reuse now? |
| Agents | Which specialist, version and permissions are active? |
| Automations | What runs next, where, and at whose cost? |
| Account | What is available, and what did the work cost? |

## Tokens and type

All tokens live in `app/globals.css`, mapped through Tailwind v4 `@theme inline`.
Reuse `base-luma`, Base UI, Hugeicons and the installed Geist faces. No preset reset.
`colors/skye.ase` was decoded and its five RGB swatches match `colors.txt` exactly.

- `background`, `sidebar`, `card`: near-white open plane / subtly different surfaces.
  Dark is neutral lightness steps, not navy. No resting-panel shadows or glass.
- `foreground`: normal reading ink; `muted-foreground`: legible secondary/meta text.
- `primary`: neutral strongest action, not every link or selected nav item.
- `brand`: Skye blue reserved primitive role; `link` and `ring`: accessible derived blues.
- `input`: visible control boundary, distinct from quiet structural `border`.
- `destructive`: negative action/error role only, adjusted after rendered contrast checks.
- Original pale blues cannot carry white small text (2.63:1 / 3.30:1). Do not use them
  for white-label controls. Verify rendered alpha/hover/focus pairs in both appearances.
- Conversation: 16px / 1.6, ≤75-character prose measure. UI 14px, metadata 12px.
  Main headings 16–24px; first-run title uses the kit's 18px role. Unitless leading, regular or medium
  text; tabular numbers for future cost and durations. Mono reserved for code/IDs.
- Keep native zoom. Inputs are 16px below the desktop density breakpoint. Use logical
  properties and `dir="auto"` for messages; never animate words into the transcript.

## Geometry and primitives

At 1440px: 256px navigation + 1184px canvas = 1440. Conversation max 736px, composer
max 800px including equal 32px gutters. Context uses 352px from that canvas only above
1200px; no invisible overlay covers the conversation. At tablet widths navigation folds
before it starves the conversation. Phone: one region, 16–20px gutters, bottom-safe composer.

Prefer installed Sidebar, MessageScroller, Message/Bubble, Field/InputGroup, Trace,
Dialog, Sheet, Tabs, Command, Empty, Skeleton, Spinner and Buttons. Domain compositions
live under `components/workspace`; no alternate custom primitive set. Literal color
values belong only to tokens/brand asset, not component call sites.

Menus pick; dialogs edit one thing; sheets inspect; full routes manage a library.
One modal at a time. Desktop Context is a nonmodal aside; narrower Context is a Base UI
Sheet (bottom on small layouts). Base UI handles trapping, Escape and focus restoration.
No independent focus trap, manual z-index stack or click-only path. Every modal has a Title.

## States, voice, and behavior

- Stage 1 is explicitly disconnected. Send retains the current-page draft and says “Not
  sent”; it never appends a pretend successful message. Feature dialogs explain staging.
- No recording/upload permission prompts, fake Sparks balance or dummy connected apps.
- `/dev/states/{empty,ready,loading,failed,running,long,low-funds}` exists only with
  `NODE_ENV=development`; production responds 404 and renders empty navigation.
- Headers stay during loading. Skeletons hold geometry; progress is not invented.
  Static run fixtures are labeled. Errors explain recovery beside the failed work.
- Preserve keyboard focus on incoming content. Route transitions focus the destination
  title; overlays return to their trigger. The draft textarea remains reachable at zoom.
- Static fixture transcript uses `aria-live=off`. Only the explicit send-status change
  announces; future SSE integration must coordinate MessageScroller's own log defaults.
- Suppress transition/movement under reduced motion, including installed primitives;
  theme switching already suppresses transitions. No app entrance or motion floor.
- Vocabulary: Project, Thread, Memory, Connector, Skill, Agent, Automation, Sparks.
  Sentence case, verb-first actions, calm specific errors. “Oops” and generic blame are out.

## Verification and boundaries

The later Stage 3 integration preserves this composition and adds default-off,
read-only account navigation/text history plus sign-out. It does not enable sending
or resource editors. Current integration evidence and remaining gates are recorded
in the parent repository's `docs/web-cutover.md`; the state fixtures remain disconnected.

Run `npm run contracts:check`, `npm run typecheck`, `npm run build`, and
`npm run test:e2e`. Browser tests cover draft safety, Escape/focus return, command search,
mobile navigation, Context, 320/390/768/1440 widths, reduced motion and axe checks.
Screenshot/contrast/critique evidence belongs in `docs/foundation-verification.md`.
A clean axe report does not substitute for a real screen-reader walkthrough.
No claim of production account integration, real OIDC, or functional resource CRUD.
