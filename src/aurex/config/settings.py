from decimal import Decimal
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Aurex"
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = Field(default="sqlite:///./data/aurex.db")
    live_trading_enabled: bool = False
    live_execution_adapter: str = "disabled"
    webhook_secret: str = "local-dev-secret"
    tradingview_webhook_source_networks: str = (
        "52.89.214.238/32,34.212.75.30/32,54.218.53.128/32,52.32.178.7/32"
    )
    duplicate_cooldown_minutes: int = Field(default=30, ge=0, le=1440)
    webhook_processing_budget_ms: int = Field(default=2500, ge=100, le=3000)
    paper_commission_bps: Decimal = Field(default=Decimal("10"), ge=0, le=1000)
    paper_half_spread_bps: Decimal = Field(default=Decimal("2.5"), ge=0, le=1000)
    paper_market_impact_bps: Decimal = Field(default=Decimal("2.5"), ge=0, le=1000)
    paper_latency_ms: int = Field(default=500, ge=0, le=60_000)

    model_config = SettingsConfigDict(
        env_prefix="AUREX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_webhook_secret(self) -> "Settings":
        if self.environment.strip().lower() not in {"prod", "production"}:
            return self

        secret = self.webhook_secret
        if secret != secret.strip() or secret == "local-dev-secret" or len(secret) < 32:
            raise ValueError(
                "Production AUREX_WEBHOOK_SECRET must be at least 32 characters, "
                "must not use the local default, and must not have surrounding whitespace"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
