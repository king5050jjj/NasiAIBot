# Architecture

All Python modules are kept in one directory for easy GitHub mobile upload.

- `main.py` starts the Telegram bot.
- `bot.py` contains Telegram handlers and preserves the original button menu.
- `ai.py` is the real OpenAI provider for chat, vision, images, audio, TTS and video.
- `web.py` uses the OpenAI Responses API web-search tool.
- `memory.py` stores user memories.
- `files.py` extracts supported document text.
- `db.py` provides SQLite/PostgreSQL-ready persistence.

Secrets are environment variables only.
