# Nasir AI Assistant

Telegram AI assistant with the original button menu preserved and real API-backed features.

## Included
- 💬 Chat with OpenAI Responses API
- 📝 Writing: rewrite, summarize, translate, correction, generation
- 🖼️ Image generation with GPT Image
- 🖼️ Image analysis/vision
- 🖼️ Image editing from a Telegram photo + caption
- 🎙️ Voice/audio transcription
- 🔊 Text-to-speech
- 🎬 Video generation with Sora 2
- ✨ Animation mode using the video generator
- 📁 PDF/DOCX/TXT/CSV/XLSX ingestion + AI summary
- 🌐 Current web search through OpenAI web search tool
- 🧠 Per-user memory and explicit learning statements
- 👑 Owner-only button remains available
- ⚙️ Settings/account screens remain available
- 🚂 Railway-ready

## Railway Variables
Required:
- `BOT_TOKEN` = your BotFather token
- `OWNER_ID` = your Telegram numeric ID
- `OPENAI_API_KEY` = your OpenAI API key

Recommended/default model variables are already listed in `.env.example` and have safe defaults in `config.py`.

For video generation, your OpenAI project must have access to the selected Sora model. Video jobs are asynchronous and the bot polls until completion.

## Run
```bash
pip install -r requirements.txt
python main.py
```

Railway start command: `python main.py`

Do not put API keys inside source files or GitHub. Store them only in Railway Variables.
