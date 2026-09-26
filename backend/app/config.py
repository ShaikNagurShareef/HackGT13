"""Runtime settings from environment / backend/.env (keys never leave the server, NFR-11)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_env: str = "development"
    artifacts_dir: Path = BACKEND_DIR.parent / "artifacts" / "current"
    allowed_origins: str = "http://localhost:5173"
    rate_limit_per_minute: int = Field(default=300, ge=1)
    paid_rate_limit_per_minute: int = Field(default=30, ge=1)
    llm_daily_budget: int = Field(default=3000, ge=0)
    geocode_daily_budget: int = Field(default=2500, ge=0)

    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_fallback_model: str = "openai/gpt-oss-20b"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    elevenlabs_api_key: SecretStr | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model: str = "eleven_flash_v2_5"
    tts_daily_budget: int = Field(default=500, ge=0)
    # xAI (Grok): explanations, voice, and Imagine street redesign illustrations; all optional.
    xai_api_key: SecretStr | None = None
    xai_model: str = "grok-4.20-0309-non-reasoning"
    xai_image_model: str = "grok-imagine-image-2.0"
    xai_tts_voice: str = "eve"
    imagine_daily_budget: int = Field(default=40, ge=0)
    imagine_cache_dir: Path = BACKEND_DIR / "cache" / "imagine"  # git-ignored (cache/)
    geoapify_api_key: SecretStr | None = None
    database_url: SecretStr | None = None
    mongodb_uri: SecretStr | None = None
    mongodb_db: str = "pathpulse"

    explain_budget_s: float = 4.0
    groq_budget_s: float = 1.6

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
