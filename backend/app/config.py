from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    database_path: str = "data/support_agent.db"
    frontend_origin: str = "http://localhost:5173"
    top_k: int = 5
    min_retrieval_score: float = 0.35
    max_history_messages: int = 10
    auth_secret: str = "portfolio-demo-secret-change-me"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
