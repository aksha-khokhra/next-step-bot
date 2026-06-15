from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str
    database_url: str = f"sqlite+aiosqlite:///{(ROOT_DIR / 'data' / 'bot.db').as_posix()}"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_timeout_seconds: float = 180.0
    ollama_model: str = "phi3:mini"
    max_breakdowns_per_day: int = 20


settings = Settings()
