# AGENTS.md

Operating brief for anyone working in this repository.

## What Skye is

Skye is a personal AI agent that lives in Telegram. You message her like a
person — a short line, a voice note, a photo, a document — and she keeps the
context and gets the task done. She is free to start and paid beyond her
limits, and the whole thing is self-hostable: one bot, one SQLite database,
one process.

## What makes her different

Two ideas carry the product:

- **Personality.** Skye has a stable voice: calm, short, warm, grounded, and
  female. She is not a neutral assistant behind a form. Identity and tone are
  part of the product, not decoration, and live in `BASE_PROMPT.md`.
- **All-in-one.** There is no suite of apps to stitch together. Chat, voice,
  pictures, documents, web search, code, skills, memories, automations, and
  third-party connectors are all the same agent in the same conversation. One
  place, one memory, one relationship.

## Files and pictures

Anything a user sends — a photo, a document, an album — is kept per scope in
`MediaLibrary` (`library.py`), on disk beside the database and independent of
the optional Docker sandbox. Pictures become `image-<n>.<ext>`; documents keep
their (sanitized) name. Every later turn can reuse them: `edit_image` takes
saved names in `files`, `list_files` discovers them, and sandbox workspaces are
seeded with the same names under `/work`. Finished pictures are stored back and
delivered automatically. The image tools never guess a source: they edit the
photo attached to the current message or the exact saved names the model passes.
A scope keeps only its newest files — 20 in a group, 50 in a private chat — and
drops older ones, so a busy group never hoards everyone's media; idle-TTL and
byte caps apply too. A conversation that predates the library is imported once
on its next turn.

## Stack

- Python 3.14, managed with `uv`, `src/` layout, fully typed (`mypy --strict`).
- Telegram through `aiogram`; Telegram Stars for payments.
- Models through Chat Completions against any OpenAI-compatible base URL — no
  per-provider adapters.
- SQLite + WAL through `aiosqlite`: one process, one writer, no ORM, no queue.
- Config from the environment only (`pydantic-settings`); no YAML, no per-user
  keys.
- Structured JSON logs through `structlog`.
- Pictures and speech on the OpenAI-compatible endpoints, or directly on fal.ai.
- Optional integrations: Exa for web search, a per-scope Docker sandbox for
  code, and Composio for hosted app connectors.

## Language

Documentation, commit messages, issues, and code comments are written in
English. Conversations with the agent may happen in any language.

## Economy

Skye runs on **Sparks** (✦), an in-app currency users top up with Telegram
Stars. There is no subscription.

- Every request is metered. Model tokens and generated pictures are priced
  through `pricing.py`, a provider-agnostic catalog keyed by model id. When the
  provider reports the real cost of a request, that value wins and is converted
  at `SKYE_SPARKS_PER_RUB`; otherwise the catalog is the fallback. Switching
  providers is a catalog change, not a code change.
- A wallet per user is an append-only ledger (`wallet_ledger`): top-ups, spends
  with their token and image breakdown and the provider cost, bonuses, refunds.
- A small free daily and monthly token allowance stays for everyone and is spent
  before the wallet; `/account` shows what is left and every request reports
  whether it came out of the allowance or the wallet. Past the allowance, runs
  are paid from the wallet.
- Every chat is open by default: a group needs no allowlist and each person pays
  for their own requests. An **allow** entry grants free, uncharged use to a
  person or a whole group; a **ban** still blocks one. Any member can volunteer
  as the chat **sponsor** and cover every request from their own wallet.
- Connector tool calls are bridged locally and billed at a flat rate
  (`SKYE_CONNECTOR_CALL_RUB`). Chat Completions cannot run provider-hosted MCP
  tools, so each Composio or custom MCP endpoint is connected in-process and its
  tools are exposed to the model as ordinary functions.
- Spending is shown under a reply by default; each scope can hide it.

## Observability

Logs are structured JSON on stdout, one object per line, and Dozzle is the only
viewer. `configure_logging` routes `structlog` and standard-library logs from
dependencies (aiogram, httpx, openai) through `structlog.stdlib.ProcessorFormatter`,
so application events, user messages, assistant replies, tool calls, turns,
billing, and model calls (`model_call` from `ModelCallTransport`) all land in the
same stream with a `level` and `kind` field. `merge_contextvars` tags every line
inside a run with `run_id`, `chat_id`, `user_id`, and `thread_id`.

Nothing is mirrored to SQLite: prompts and responses are never stored, so message
text stays out of the logs — events carry only metadata such as length, tokens,
duration, and cost. Dozzle detects the JSON automatically, colour-codes levels,
groups tracebacks, and can query the fields with its built-in SQL engine
(`SELECT * FROM logs WHERE kind = 'turn'`, `WHERE level = 'error'`).

Run it with the logs profile:

```bash
docker compose --profile logs up -d dozzle   # http://<host>:8080
```

Dozzle needs `docker.sock`, which is root-equivalent on the host, so it is never
exposed without authentication: `DOZZLE_AUTH_PROVIDER=simple` reads
`dozzle/users.yml` (copy `dozzle/users.yml.example` and generate the hash with
`docker run -it --rm amir20/dozzle generate`). The compose service filters to the
Skye container through the `com.skye.logs` label and Docker caps its json-file
logs at 10 MB × 5.

## Tooling

```bash
uv sync
uv run ruff check .
uv run mypy
uv run pytest
```

Line length 100. Ruff selects `E`, `F`, `I`, `UP`, `B`, `SIM`.
