import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    owner_id: int = int(os.getenv("OWNER_ID", "0") or 0)
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./assistant.db")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "")
    image_model: str = os.getenv("OPENAI_IMAGE_MODEL", "")
    transcription_model: str = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "")
    tts_model: str = os.getenv("OPENAI_TTS_MODEL", "")
    web_search_api_key: str = os.getenv("WEB_SEARCH_API_KEY", "")
    image_provider_key: str = os.getenv("IMAGE_PROVIDER_API_KEY", "")
    video_provider_key: str = os.getenv("VIDEO_PROVIDER_API_KEY", "")
    animation_provider_key: str = os.getenv("ANIMATION_PROVIDER_API_KEY", "")
    video_model: str = os.getenv("OPENAI_VIDEO_MODEL", "sora-2")
    free_video_space: str = os.getenv("FREE_VIDEO_SPACE", "Lightricks/ltx-video-distilled")
    free_video_seconds: str = os.getenv("FREE_VIDEO_SECONDS", "2")
    video_seconds: str = os.getenv("OPENAI_VIDEO_SECONDS", "4")
    video_size: str = os.getenv("OPENAI_VIDEO_SIZE", "720x1280")
    video_poll_seconds: int = int(os.getenv("VIDEO_POLL_SECONDS", "10"))
    video_poll_attempts: int = int(os.getenv("VIDEO_POLL_ATTEMPTS", "60"))
    max_memory_items: int = int(os.getenv("MAX_MEMORY_ITEMS", "1000"))
    max_file_mb: int = int(os.getenv("MAX_FILE_MB", "25"))

settings = Settings()
