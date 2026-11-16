"""Environment-based application configuration.

All settings are read from environment variables (or a local `.env` file).
Secrets such as API keys live only here, on the server. They are never sent
to the frontend.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Alpha Research API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = Field(
        default=f"sqlite:///{(BACKEND_DIR / 'data' / 'alpha_research.db').as_posix()}"
    )
    # Run Alembic migrations automatically when the API starts.
    auto_migrate: bool = True

    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:3000"

    # Market data integration. "none" means no provider is configured and every
    # market-data endpoint reports that data is unavailable.
    market_data_provider: Literal["none", "tiingo"] = "none"
    market_data_api_key: SecretStr | None = None
    # How many years of daily prices to load the first time a stock is synced.
    price_history_years: int = Field(default=2, ge=1, le=30)

    # SEC EDGAR fundamentals (free, no key). The SEC requires a User-Agent with
    # your name and contact email, e.g. "Jane Doe jane@example.com".
    sec_user_agent: str | None = None

    # AI research integration. "none" means AI report generation is unavailable.
    ai_provider: Literal["none"] = "none"
    ai_api_key: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def _non_empty_database_url(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("DATABASE_URL must not be empty")
        return value

    @model_validator(mode="after")
    def _provider_needs_key(self) -> "Settings":
        key = self.market_data_api_key.get_secret_value().strip() if self.market_data_api_key else ""
        if self.market_data_provider != "none" and not key:
            raise ValueError(
                f"MARKET_DATA_PROVIDER={self.market_data_provider} needs MARKET_DATA_API_KEY to be set"
            )
        return self

    @field_validator("sec_user_agent")
    @classmethod
    def _sec_user_agent_has_contact(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        if "@" not in value:
            raise ValueError(
                'SEC_USER_AGENT must include a contact email, e.g. "Jane Doe jane@example.com"'
            )
        return value.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
