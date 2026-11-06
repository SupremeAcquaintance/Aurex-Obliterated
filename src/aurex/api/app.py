from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from aurex.api.routes.analyst import router as analyst_router
from aurex.api.routes.backtests import router as backtests_router
from aurex.api.routes.broker import router as broker_router
from aurex.api.routes.health import router as health_router
from aurex.api.routes.journal import router as journal_router
from aurex.api.routes.live import router as live_router
from aurex.api.routes.market import router as market_router
from aurex.api.routes.operator_profile import router as operator_profile_router
from aurex.api.routes.paper import router as paper_router
from aurex.api.routes.performance import router as performance_router
from aurex.api.routes.prediction_market import router as prediction_market_router
from aurex.api.routes.risk import router as risk_router
from aurex.api.routes.sandbox_profile import router as sandbox_profile_router
from aurex.api.routes.signals import router as signals_router
from aurex.api.routes.strategies import router as strategies_router
from aurex.api.routes.system import router as system_router
from aurex.api.routes.trades import router as trades_router
from aurex.api.routes.webhooks import router as webhooks_router
from aurex.config.settings import get_settings
from aurex.observability.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(health_router)
    app.include_router(webhooks_router)
    app.include_router(signals_router)
    app.include_router(risk_router)
    app.include_router(trades_router)
    app.include_router(paper_router)
    app.include_router(performance_router)
    app.include_router(prediction_market_router)
    app.include_router(strategies_router)
    app.include_router(analyst_router)
    app.include_router(broker_router)
    app.include_router(live_router)
    app.include_router(backtests_router)
    app.include_router(system_router)
    app.include_router(market_router)
    app.include_router(journal_router)
    app.include_router(operator_profile_router)
    app.include_router(sandbox_profile_router)

    frontend_dir = Path(__file__).resolve().parents[3] / "apps" / "frontend"
    if frontend_dir.exists():
        app.mount(
            "/dashboard/assets",
            StaticFiles(directory=frontend_dir),
            name="dashboard-assets",
        )

        @app.get("/dashboard", include_in_schema=False)
        def dashboard() -> FileResponse:
            return FileResponse(frontend_dir / "index.html")

    return app
