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

## Tooling

```bash
uv sync
uv run ruff check .
uv run mypy
uv run pytest
```

Line length 100. Ruff selects `E`, `F`, `I`, `UP`, `B`, `SIM`.
