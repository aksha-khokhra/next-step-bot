# Next Step Bot

Telegram bot that breaks overwhelming tasks into small steps and recommends **one** action at a time. Uses [Ollama](https://ollama.com) locally (free) for AI breakdown.

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) running with `phi3:mini`:
  ```powershell
  ollama pull phi3:mini
  ```
- Telegram bot token from [@BotFather](https://t.me/BotFather)

## Setup

```powershell
cd "c:\Users\khokh\OneDrive\Documents\My Projects\next-step-bot"
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

No need to run `Activate.ps1` (often blocked on Windows).

Edit `.env` and set `BOT_TOKEN=...` from BotFather.

## Run

1. Ensure Ollama is running (open the Ollama app or it starts in the tray).
2. Start the bot:

```powershell
.\.venv\Scripts\python.exe -m bot
```

Or double-click `run.bat`, or run `.\run.bat` in the terminal.

3. Open your bot in Telegram on your phone or desktop and send `/start`.

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome |
| `/add <task>` | Add goal and AI-break into steps |
| `/next` | One recommended next step |
| `/list` | Up to 5 pending goals |
| `/help` | Usage reminder |

You can also send plain text (without `/`) to add a task.

## Notes

- The bot must run on a PC with Ollama while you use it from Telegram on your phone.
- Keep your PC awake and the bot process running for replies.
- `.env` and `data/` are gitignored — do not commit your token.
