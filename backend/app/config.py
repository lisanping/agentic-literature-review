"""Configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── OpenAI ──
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # ── Database ──
    DATABASE_URL: str = "sqlite+aiosqlite:///data/app.db"

    # ── Vector database ──
    CHROMA_PATH: str = "/data/chroma"

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Semantic Scholar ──
    S2_API_KEY: str = ""

    # ── Logging ──
    LOG_LEVEL: str = "INFO"

    # ── LangGraph Checkpointer ──
    CHECKPOINTER_BACKEND: str = "sqlite"
    CHECKPOINT_DB_URL: str = "sqlite:///data/checkpoints.db"

    # ── LLM Routing ──
    LLM_ROUTING_CONFIG: str = ""

    # ── Prompt templates ──
    PROMPTS_DIR: str = "prompts"

    # ── Authentication ──
    AUTH_REQUIRED: bool = False  # False = backward-compatible, no auth enforced
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_COST_FACTOR: int = 12
    FIRST_ADMIN_EMAIL: str = ""  # Auto-create admin on first startup
    FIRST_ADMIN_PASSWORD: str = ""


settings = Settings()
