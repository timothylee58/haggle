from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://haggle:haggle@localhost:5432/haggle"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:3000"]

    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5-5"

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_env: Literal["sandbox"] = "sandbox"
    # PayPal records the buyer's approval only when it can send them back to a page we serve.
    frontend_url: str = "http://localhost:3000"


PAYPAL_SANDBOX_URL = "https://api-m.sandbox.paypal.com"

settings = Settings()
