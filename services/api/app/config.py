from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://haggle:haggle@localhost:5432/haggle"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:3000"]

    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5-5"

    # Used by the Channel3 price check. Empty means the feature is off, not broken.
    channel3_api_key: str = ""
    channel3_base_url: str = "https://api.trychannel3.com"

    # Public-demo guards. Per-IP match starts per hour, and a daily cap on Claude matches for the whole
    # server (0 turns Claude off entirely; each Claude match spends real API credit).
    rate_limits_enabled: bool = True
    matches_per_hour_per_ip: int = 30
    llm_matches_per_day: int = 25
    market_checks_per_hour_per_ip: int = 60
    rate_limit_prefix: str = "haggle"

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_env: Literal["sandbox"] = "sandbox"
    # PayPal records the buyer's approval only when it can send them back to a page we serve.
    frontend_url: str = "http://localhost:3000"

    @field_validator("database_url")
    @classmethod
    def use_the_async_driver(cls, url: str) -> str:
        """Hosts hand out plain postgres:// URLs, but the API talks to Postgres through asyncpg."""
        for plain in ("postgres://", "postgresql://"):
            if url.startswith(plain):
                return "postgresql+asyncpg://" + url[len(plain) :]
        return url

    @property
    def allowed_origins(self) -> list[str]:
        """The frontend's own address is always allowed, so one FRONTEND_URL is enough when hosted."""
        origins = [*self.cors_origins, self.frontend_url.rstrip("/")]
        return list(dict.fromkeys(origins))


PAYPAL_SANDBOX_URL = "https://api-m.sandbox.paypal.com"

settings = Settings()
