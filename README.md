![Skye Marketing Banner](./assets/banner.png)

# Meet `Skye`

- [Website](https://skye-bot.com)
- [Docs](https://docs.skye-bot.com)

## Features

### Write as Usual

Skye lives where your conversations, work, and everyday life already happen. There’s no extra app to learn — just write to her the way you would write to a person. Short, by voice, with a photo or a document: she will pick up the context and help you finish the task.

---

### Talk in Text and Voice

Ask questions, think out loud, or send a voice note. Skye will get to the point — and go deeper when you need it. She also works in groups and can help run channels.

---

### Work with Photos and Documents

Create and edit images by saying what you want. Skye can describe a picture, read and compare documents, explain a spreadsheet, and summarize a text.

---

### Search the Web

Ask about something that changed this week and she looks it up, then answers with the sources linked. YouTube transcripts work too — hand her a link and ask for the point of it.

---

### Files and Code

Some tasks need running, not talking. Skye has a private workspace where she writes files, runs commands, and hands back the finished document, script, or archive.

---

### Remember

Tell her once — your timezone, how you like a summary, what you are working on — and she keeps it. Memories stay private to you or shared with the group, and you can see and delete them any time.

---

### Skills, Apps, and Agents

Skye learns jobs the way you would teach a person. Upload a skill for something she should know how to do, connect an app you already use, or build a custom agent with its own instructions and hand it the task.

---

### Automations

Some things should happen without you asking. Give her a schedule or a webhook and she runs the task in that chat on her own — a morning brief, a recurring check, whatever you keep repeating.

---

### Free to Start

There is no subscription. `/account` shows your free daily and monthly allowance; past it, runs are paid from Sparks — an in-app credit you top up with Telegram Stars. Every request tells you what it cost, and each chat can hide the tally.

---

## Run It Yourself

Skye is self-hostable: one bot, one SQLite database, one process. No queue, no external services, no per-user keys.

```bash
git clone https://github.com/overwaven/skye-next
cd skye-next
cp .env.example .env   # fill in the required values below
docker compose up -d --build
```

Only two variables are required: `TELEGRAM_BOT_TOKEN` from [@BotFather](https://t.me/BotFather), and `SKYE_OWNER_IDS` — the comma-separated Telegram user ids allowed to administer the bot. Add one model key on top: `SKYE_PROVIDER_API_KEY` with any OpenAI-compatible `SKYE_PROVIDER_BASE_URL`, or `OPENAI_API_KEY`, or `OPENROUTER_API_KEY`.

Everything else is optional and turns a capability on:

| Variable | Capability |
|---|---|
| `SKYE_EXA_API_KEY` | Web search and page reading |
| `SKYE_FAL_KEY` | Pictures and speech, separate from the chat provider |
| `COMPOSIO_API_KEY` | Hosted app connectors |
| `SKYE_SANDBOX_ENABLED=true` | The private code workspace |
| `SKYE_AUDIO_PROVIDER=local` | Voice notes and replies on the host with Whisper large-v3-turbo and Supertonic 3 |
| `SKYE_TOOL_STRICT=false` | A provider that rejects strict tool schemas (for example Beget) |
| `SKYE_WEB_ORIGIN` | Public origin for webhook automation URLs |

The database and every picture and file a user sends live on the `skye-data` volume. There is no inbound port — she uses long polling. Logs are structured JSON on stdout, so `docker compose logs -f` is enough, or start the Dozzle viewer for SQL over the event fields:

```bash
cp dozzle/users.yml.example dozzle/users.yml   # generate the hash first, see AGENTS.md
docker compose --profile logs up -d dozzle     # http://<host>:8080
```

To work on the code itself, skip Docker: `uv sync`, then `uv run skye`.

One caution before you enable the sandbox: the compose file mounts `/var/run/docker.sock` so the bot can spawn one container per command, and that is root-equivalent on the host. It is off by default, and so is sandbox network egress.
