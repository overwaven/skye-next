# Stage 4–5: web chat, uploads and voice

Implementation date: 2026-11-07. This adds the first writable web vertical slice on top
of the canonical store and read-only API. Python remains the only database writer,
scheduler, billing authority and agent executor.

## Chat

`POST /api/v1/threads/{thread_id}/messages` accepts a client request id, text and opaque
file ids. It appends the canonical user message inside the shared `TurnService`
admission, returns `202` after the run is durable, and continues in the background. A
repeat request id returns the original run instead of executing again. Busy, quota,
validation and archived-thread failures map to safe API errors.

The web adapter uses the same `AgentRuntime`, conversation session and `TurnService` as
Telegram. `send_message` deliveries are appended as confirmed assistant messages; the
fallback reply is appended only when no visible message or media was delivered. Delivery
is marked complete before settlement, and settlement remains once per run.

`GET /api/v1/threads/{id}/events` is a snapshot-first SSE stream. A connect writes the
current thread, latest 50 messages, active/latest run, labelled activity and cursor, then
streams durable events from the per-user `web_events` index. Heartbeats keep ingress
alive. Reconnect starts from a new snapshot, so a dropped connection cannot silently skip
a run or a committed reply. Events cover:

- `message.created` for web, Telegram and automation appends;
- `run.changed` with state, delivery state and settlement state;
- `run.activity` with a curated label, category and status only — never arguments,
  tool output, reasoning or private assistant prose;
- `resource.changed` for thread/project/memory changes plus account-wide invalidation.

`MessageScroller` uses `autoScroll` and anchored items for real deliveries. History pages
use `before=<sequence>&limit=50`. Markdown is rendered without raw HTML or remote images;
code blocks use the shadcn CodeBlock. Server and model citation tokens are sanitized
before storage.

Thread creation, rename and archive use `POST /threads` and `PATCH /threads/{id}`.
Moving a thread to a custom project or no project uses the same endpoint. Drafts are
stored per thread in local storage and cleared only after the server accepts a send.
Telegram's `/threads` picker reads the same canonical rows, so a web-created thread is
available in Telegram without another migration. The shell revalidates server components
when the browser regains focus, covering memory, skills, connectors and preferences
changed from Telegram; memory tool calls also publish an immediate event.

## Uploads and media

`POST /api/v1/media` accepts bounded authenticated bytes with a name and declared type.
The bytes are stored in the existing per-scope `MediaLibrary`; the API returns an opaque
id, never a filesystem path. `GET /api/v1/media` lists web uploads and Telegram-saved
library files. `GET /api/v1/media/{id}` resolves both a message part id and an upload id,
checks ownership, and serves:

- safe raster images inline with `nosniff`, a sandbox CSP and `same-origin` policy;
- every other type as an attachment with a sanitized filename;
- missing or evicted bytes as an honest 404, rendered as expired in the UI.

HTML, SVG, script and XHTML uploads are rejected. The media picker supports progress,
cancel, retry, duplicate-name handling and removal. Generated pictures and files are
saved back to the library and appended to the assistant turn, so they render and remain
reusable like any other file. A Telegram photo already saved in the library is listed
and can be attached to a web turn; the model can edit it through the existing saved-file
rules.

## Voice

The browser records with `MediaRecorder`, shows a timer, detects webm/mp4 support and
posts the bounded bytes to `POST /api/v1/audio/transcribe`. The endpoint reuses
`AudioService`, stores the recording as media, limits requests to 25 MB and ten per
minute per account, and returns an editable transcript with the media record. The person
can play the recording, edit the text, discard it or attach it; the transcript is sent as
request context and the audio remains an attachment. Microphone denial, unsupported
formats and upload failures keep the draft and show a recovery message.

Transcription is **not separately charged** in this release. This is an explicit bounded
policy (25 MB, ten per minute) until a price is added to `pricing.py`; it does not bypass
model settlement for the resulting turn.

## Schema and security

Schema version 3 is additive: `run_activity.label/tool_id`, `canonical_runs.failure`,
`web_events` and `web_uploads`. A v2 database rolls forward in place on startup; the
offline migration also installs v3. Old rows are not rewritten and no legacy table is
dropped.

Every write still requires the session cookie, same Origin and the CSRF header. Uploads
and SSE remain on the same origin through Caddy; the internal Next server keeps its
separate internal token. No provider errors, request bodies, tool arguments or file paths
are logged.

## Verification

- `uv run pytest -q`: 422 passed.
- `uv run python scripts/verify_web_stage45.py`: 10 API steps passed, including snapshot
  SSE, ordered message events, labelled activity, upload/download, a file-bearing turn,
  transcription, rename, stop and archive rejection. Artifact:
  `docs/web-stage45-e2e.json`.
- `npm run test:e2e`: 39 browser checks across Chromium, Firefox and WebKit in fixture
  mode, with HTML/JSON artifacts.
- `node scripts/verify-stage45-ui.mjs`: connected local run through Caddy, Next and the
  real API (fake provider) covering text send, live tool step, run details, image upload
  and delivery, rename and draft reload. Artifact:
  `web/test-results/stage45-connected.json`.
- Live provider check through the deployed API on 2026-11-07: a new thread completed a
  real `hi` turn with two committed messages, `delivery_state=complete`, no failure and
  no wallet charge (complimentary). The verification thread was archived. Three earlier
  failed holds caused by the input-envelope bug were settled explicitly at zero usage
  with operator evidence `stage45-input-shape-fix`.

## Known limits

- Only one real Telegram account is available; the strict two-account isolation gate is
  still unmet and is not claimed.
- The connected browser proof uses a deterministic runtime on the operator machine. A
  live free-provider turn completed through the deployed API, but live browser acceptance
  still needs the account owner to send from the UI.
- Telegram file bytes that were never saved in the shared media library remain
  unavailable for download; the UI says so instead of guessing.
- Memory/skills/connectors/preferences do not have web editors yet (Stage 6). Changes
  made in Telegram revalidate on focus; thread/project and memory tool changes also push
  events immediately.
- Generated video and audio artifacts are not supported as web playback beyond attached
  files and their stored MIME type.

## Interface refinement (2026-11-07)

Threads can now be deleted completely from the list menu; the delete is transactional,
refuses active runs and automation targets, and rebinds a project to a replacement thread
when the deleted row was its selected or initial thread. Thread menus live on sidebar and
project rows, not inside the open thread.

Projects carry the same emoji as Telegram and can be created from the sidebar or the new
thread selector. Moving a thread is a submenu, not a dialog. The project selector creates
a project in place and selects it.

Attachments use the shadcn `Attachment` primitives in the composer and transcript, with a
thumbnail, full preview, download and remove actions. The picker has grid/list layouts,
search, type filters, a three-dot action menu per item, click-to-attach, upload progress
and cancellation.

Tool activity is rendered in the transcript as a collapsible icon list (`1 tool`, `N
tools`) and remains available after the run completes; the separate run-details dialog was
removed. Consecutive assistant messages from one run show the “Skye” label once. Route
changes and tab panels animate, with reduced-motion respected.
Thread tool activity is loaded per run: the latest run streams live, and earlier runs in
the visible history are fetched from the owner-scoped run endpoint so their collapsible
tool blocks remain in place after reload (within the 24-hour activity retention window).
