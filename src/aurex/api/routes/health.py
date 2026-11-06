from fastapi import APIRouter

from aurex.config.settings import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "live_trading_enabled": settings.live_trading_enabled,
    }

