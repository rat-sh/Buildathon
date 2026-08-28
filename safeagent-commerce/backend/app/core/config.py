"""
core/config.py — Application settings via Pydantic Settings v2
===============================================================
All config is loaded from environment variables (or .env file).
Pydantic v2 validates and type-coerces all values at startup.
If a required value is missing, the app refuses to start — fail fast.
"""

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration.
    All values must come from environment variables or .env file.
    Sensitive values (API keys, secrets) are never logged.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars — don't crash on extras
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_ENV: str = Field(default="development")
    APP_SECRET_KEY: str = Field(default="dev-secret-change-in-production-minimum-32-chars")
    DEBUG: bool = Field(default=True)

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./safeagent.db"
    )

    # ── Razorpay — TEST MODE ONLY ─────────────────────────────────────────────
    # These must be TEST keys (rzp_test_*). Production keys are never used here.
    RAZORPAY_KEY_ID: str = Field(default="rzp_test_placeholder")
    RAZORPAY_KEY_SECRET: str = Field(default="placeholder_secret")
    RAZORPAY_WEBHOOK_SECRET: str = Field(default="placeholder_webhook_secret")

    # ── LLM ───────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(default="")
    GROQ_API_KEY: str = Field(default="")
    LLM_MODEL: str = Field(default="gpt-4o-mini")

    # ── AI Buyer Auth ─────────────────────────────────────────────────────────
    AI_BUYER_API_KEY: str = Field(default="test-ai-buyer-key")

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:8000", "http://localhost:3000"]
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """Allow CORS_ORIGINS as space-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split() if origin.strip()]
        return v

    @field_validator("RAZORPAY_KEY_ID")
    @classmethod
    def validate_razorpay_key(cls, v: str) -> str:
        """
        Enforce that we ONLY use test keys in this buildathon.
        This validator blocks production keys from being used accidentally.
        """
        if v and not v.startswith("rzp_test_") and v != "rzp_test_placeholder":
            raise ValueError(
                "SAFETY: Only Razorpay TEST keys (rzp_test_*) are allowed. "
                "Never use production keys in this project."
            )
        return v

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


# ── Singleton — import this everywhere ───────────────────────────────────────
# Usage: from app.core.config import settings
settings = Settings()
