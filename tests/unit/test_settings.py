import pytest
from pydantic import ValidationError

from aurex.config.settings import Settings


def test_production_rejects_default_webhook_secret() -> None:
    with pytest.raises(ValidationError, match="Production AUREX_WEBHOOK_SECRET"):
        Settings(environment="production", webhook_secret="local-dev-secret")


def test_production_accepts_strong_webhook_secret() -> None:
    settings = Settings(
        environment="production",
        webhook_secret="aurex-production-webhook-secret-32-plus",
    )

    assert settings.webhook_secret == "aurex-production-webhook-secret-32-plus"
    assert settings.webhook_processing_budget_ms == 2500
