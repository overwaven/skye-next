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
- A small free daily and monthly token allowance stays for everyone; past it,
  runs are paid from the wallet.
- Top-up packages are code-owned (`sparks.py`); bigger packages carry a better
  rate and are one-time Telegram Stars payments.
- In groups each person pays for their own requests. Any member can volunteer as
  the chat **sponsor** and cover every request from their own wallet.
- Connector tool calls are bridged locally and billed at a flat rate
  (`SKYE_CONNECTOR_CALL_RUB`). Chat Completions cannot run provider-hosted MCP
  tools, so each Composio or custom MCP endpoint is connected in-process and its
  tools are exposed to the model as ordinary functions.
- Spending is shown under a reply by default; each scope can hide it.

## Tooling

```bash
uv sync
uv run ruff check .
uv run mypy
uv run pytest
```

Line length 100. Ruff selects `E`, `F`, `I`, `UP`, `B`, `SIM`.
