"""Tests for configuration management."""

from app.config import Settings


def test_default_settings():
    """Settings should load with sensible defaults."""
    s = Settings(OPENAI_API_KEY="test-key")
    assert s.OPENAI_MODEL == "gpt-4o"
    assert s.LOG_LEVEL == "INFO"
    assert s.CHECKPOINTER_BACKEND == "sqlite"
    assert s.PROMPTS_DIR == "prompts"
    assert "sqlite" in s.DATABASE_URL
