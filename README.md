# Next Step Bot

Telegram bot that helps with overwhelm by recommending **one** small action at a time. Add tasks freely, break them down with AI when you need help (via local [Ollama](https://ollama.com)), and work through steps with simple buttons.

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) with a small model:
  ```powershell
  ollama pull phi3:mini
  ```
- Telegram bot token from [@BotFather](https://t.me/BotFather)

## Setup

```powershell
cd path\to\next-step-bot
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set `BOT_TOKEN` from BotFather. Never commit `.env`.

## Run

1. Open **Ollama** (tray icon visible).
2. Start the bot:

```powershell
.\.venv\Scripts\python.exe -m bot
```

Or double-click `run.bat`.

3. Message your bot in Telegram (`/start`).

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome and menu |
| `/add <task>` | Add a task (no breakdown yet) |
| `/list` | Your tasks — tap one to break down or continue |
| `/breakdown` | Same as picking a task from `/list` |
| `/done` | Pick which main task you finished |
| `/clear` | Show delete confirmation message |
| `/confirmclear` | Delete all tasks |
| `/help` | Usage reminder |

Plain text (without `/`) also adds a task.

**Buttons:** My tasks, Add task (when empty). While working: Next, Too big, Skip, My tasks

## Environment variables

See `.env.example`:

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | Telegram bot token |
| `DATABASE_URL` | No | SQLite path (default is fine) |
| `OLLAMA_BASE_URL` | No | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | No | Default `phi3:mini` |
| `OLLAMA_TIMEOUT_SECONDS` | No | AI request timeout |
| `MAX_BREAKDOWNS_PER_DAY` | No | Per-user daily AI cap |

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

## Deploy later (optional)

MVP uses **long-polling** on your PC. For 24/7 use from your phone without your PC:

- Deploy the bot to a VPS (Railway, Fly.io, etc.)
- Run Ollama on the same server, or switch to a cloud LLM API
- Switch from polling to a **webhook** in `bot/__main__.py`

## Notes

- Bot + Ollama must run on the same machine (your PC for MVP).
- Keep the terminal open while using the bot.
- `.env` and `data/` are gitignored.
