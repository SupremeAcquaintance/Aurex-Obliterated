"""Guarded local operator app. This is a private boundary, not user authentication."""

import asyncio
import ipaddress
import re
import sqlite3
from contextlib import asynccontextmanager, closing
from pathlib import Path
from time import monotonic
from uuid import uuid4

from alembic.script import ScriptDirectory
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from starlette.responses import JSONResponse

from aurex.config.settings import Settings, get_settings
from aurex.db import models  # noqa: F401
from aurex.db.base import Base
from aurex.signal_gateway.native_lifecycle import (
    NativeControlRequest,
    NativeLifecycleError,
    NativeSupervisorController,
    unconfigured_status,
)
from aurex.signal_gateway.native_supervision import NativeSupervisorConfig

ROOT = Path(__file__).resolve().parents[3]
CHECK_TIMEOUT_SECONDS = 30
MAX_DATABASE_BYTES = 512 * 1024 * 1024


class PrivateRuntimeError(ValueError):
    pass


def database_path(settings: Settings) -> Path:
    try:
        url = make_url(settings.database_url)
        if url.drivername != "sqlite" or not url.database or url.query:
            raise PrivateRuntimeError("EXISTING_FILE_SQLITE_REQUIRED")
        path = Path(url.database).resolve(strict=True)
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_DATABASE_BYTES:
            raise PrivateRuntimeError("DATABASE_SIZE_INVALID")
        return path
    except (ArgumentError, OSError) as exc:
        raise PrivateRuntimeError("EXISTING_FILE_SQLITE_REQUIRED") from exc


def runtime_check(settings: Settings, port: int) -> dict:
    """Read-only bounded checks; never create, upgrade, seed or reset a database."""
    blockers = []
    actual = []
    expected = sorted(ScriptDirectory(str(ROOT / "infra" / "alembic")).get_heads())
    if type(port) is not int or not 1024 <= port <= 65535:
        blockers.append("PORT_OUT_OF_RANGE")
    if settings.live_trading_enabled or settings.live_execution_adapter != "disabled":
        blockers.append("LIVE_EXECUTION_MUST_BE_DISABLED")
    if settings.environment.strip().lower() in {"prod", "production"}:
        blockers.append("PRODUCTION_ENVIRONMENT_NOT_AUTHORIZED")
    try:
        path = database_path(settings)
        deadline = monotonic() + CHECK_TIMEOUT_SECONDS
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
            db.execute("PRAGMA query_only=ON")
            db.set_progress_handler(lambda: int(monotonic() > deadline), 1000)
            db.execute("BEGIN")
            actual = sorted(row[0] for row in db.execute("SELECT version_num FROM alembic_version"))
            if not expected or actual != expected:
                blockers.append("CURRENT_SCHEMA_REQUIRED")
            if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                blockers.append("DATABASE_INTEGRITY_FAILED")
            if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                blockers.append("DATABASE_FOREIGN_KEYS_FAILED")
            tables = {
                row[0] for row in db.execute("SELECT name FROM sqlite_schema WHERE type='table'")
            }
            if not set(Base.metadata.tables) <= tables:
                blockers.append("REQUIRED_TABLES_MISSING")
            elif any(
                not set(table.columns.keys())
                <= {row[1] for row in db.execute('PRAGMA table_info("' + name + '")')}
                for name, table in Base.metadata.tables.items()
            ):
                blockers.append("REQUIRED_COLUMNS_MISSING")
    except PrivateRuntimeError as exc:
        blockers.append(str(exc))
    except (sqlite3.Error, OSError):
        blockers.append("DATABASE_CHECK_FAILED")
    if not all(
        (ROOT / "apps" / "frontend" / item).is_file()
        for item in (
            "index.html",
            "app.js",
            "dashboard-transport.js",
            "styles.css",
        )
    ):
        blockers.append("DASHBOARD_ASSETS_MISSING")
    return {
        "status": "BLOCKED" if blockers else "PRIVATE_CONFIG_READY",
        "blockers": blockers,
        "database_revisions": actual,
        "expected_revisions": expected,
        "host": "127.0.0.1",
        "port": port,
        "proxy_headers_trusted": False,
        "public_access_authorized": False,
        "management_authentication": False,
        "starts_native_supervisor": False,
        "live_authority": False,
        "operational_acceptance": False,
    }


class LocalOperatorBoundary:
    """Reject remote peers, rebinding hosts and browser cross-origin operations."""

    def __init__(self, app, *, port: int, settings: Settings, instance_id: str):
        self.app = app
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.settings = settings.model_copy(deep=True)
        self.instance_id = instance_id.encode("ascii")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        headers = scope.get("headers", [])
        hosts = [value.decode("latin-1") for key, value in headers if key == b"host"]
        origins = [value.decode("latin-1") for key, value in headers if key == b"origin"]
        values = dict(headers)
        try:
            local = ipaddress.ip_address(scope.get("client", ("", 0))[0]).is_loopback
        except (ValueError, TypeError):
            local = False
        reason = None
        if not local or len(hosts) != 1 or hosts[0] not in self.hosts:
            reason = "LOCAL_HOST_REQUIRED"
        elif len(origins) > 1 or (origins and origins[0] != "http://" + hosts[0]):
            reason = "SAME_ORIGIN_REQUIRED"
        elif values.get(b"sec-fetch-site", b"none") not in {b"same-origin", b"none"}:
            reason = "SAME_ORIGIN_REQUIRED"
        elif values.get(b"x-aurex-instance", self.instance_id) != self.instance_id:
            reason = "RUNTIME_INSTANCE_MISMATCH"
        elif (
            scope["method"] not in {"GET", "HEAD", "OPTIONS"}
            and not origins
            and values.get(b"x-aurex-local-request") != b"1"
        ):
            reason = "LOCAL_REQUEST_HEADER_REQUIRED"
        elif get_settings() != self.settings and (scope["method"], scope["path"]) not in {
            ("GET", "/system/native-supervisor"),
            ("POST", "/system/native-supervisor/stop"),
        }:
            reason = "RUNTIME_SETTINGS_CHANGED"

        async def guarded_send(message):
            if message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": [
                        *[
                            (k, v)
                            for k, v in message.get("headers", [])
                            if k
                            not in {
                                b"cache-control",
                                b"x-frame-options",
                                b"x-content-type-options",
                            }
                        ],
                        (b"cache-control", b"no-store"),
                        (b"x-frame-options", b"DENY"),
                        (b"x-content-type-options", b"nosniff"),
                    ],
                }
            await send(message)

        if reason:
            status = 503 if reason == "RUNTIME_SETTINGS_CHANGED" else 403
            return await JSONResponse({"detail": reason}, status_code=status)(
                scope, receive, guarded_send
            )
        return await self.app(scope, receive, guarded_send)


def create_private_app(
    port: int,
    instance_id: str | None = None,
    *,
    native_config: NativeSupervisorConfig | None = None,
    native_directory: Path | None = None,
):
    # Import only after the launcher has bound and validated process settings.
    from aurex.api.app import create_app
    from aurex.api.dependencies import get_db

    settings = get_settings().model_copy(deep=True)
    instance_id = instance_id or uuid4().hex
    if not re.fullmatch(r"[0-9a-f]{32}", instance_id):
        raise PrivateRuntimeError("RUNTIME_INSTANCE_INVALID")
    report = runtime_check(settings, port)
    if report["blockers"]:
        raise PrivateRuntimeError(",".join(report["blockers"]))
    path = database_path(settings)
    identity = (path.stat().st_dev, path.stat().st_ino)

    def connect():
        # Refuse a replaced/missing path and implicit DB creation, including after restart.
        if (path.stat().st_dev, path.stat().st_ino) != identity:
            raise PrivateRuntimeError("DATABASE_FILE_REPLACED")
        db = sqlite3.connect(
            path.as_uri() + "?mode=rw", uri=True, timeout=5, check_same_thread=False
        )
        db.execute("PRAGMA foreign_keys=ON")
        return db

    engine = create_engine(f"sqlite:///{path.as_posix()}", creator=connect, poolclass=NullPool)
    app = create_app()

    def recheck():
        if get_settings() != settings or runtime_check(settings, port)["blockers"]:
            raise NativeLifecycleError("managed_runtime_preflight_failed")
        if (path.stat().st_dev, path.stat().st_ino) != identity:
            raise NativeLifecycleError("managed_database_identity_changed")

    if (native_config is None) != (native_directory is None):
        raise PrivateRuntimeError("NATIVE_CONFIG_AND_DIRECTORY_REQUIRED")
    controller = (
        None
        if native_config is None
        else NativeSupervisorController(
            path, settings, native_config, native_directory, instance_id, recheck=recheck
        )
    )
    app.state.native_supervisor_controller = controller
    app.state.native_shutdown_clean = True

    def local_db():
        with Session(engine, autoflush=False, expire_on_commit=False) as db:
            yield db

    app.dependency_overrides[get_db] = local_db
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        try:
            fresh = runtime_check(settings, port)
            if fresh["blockers"] or get_settings() != settings:
                raise PrivateRuntimeError("PRIVATE_STARTUP_RECHECK_FAILED")
            with engine.connect() as connection:
                connection.exec_driver_sql("SELECT 1")
            async with original_lifespan(application) as state:
                yield state
        finally:
            try:
                if controller is not None:
                    app.state.native_shutdown_clean = await asyncio.to_thread(controller.close)
            except Exception:
                app.state.native_shutdown_clean = False
                raise
            finally:
                engine.dispose()

    app.router.lifespan_context = lifespan
    app.state.private_instance_id = instance_id
    app.add_middleware(LocalOperatorBoundary, port=port, settings=settings, instance_id=instance_id)

    @app.get("/system/private-runtime", tags=["system"])
    def private_status():
        # This is service preflight/status, not a strategy or supervisor health claim.
        current = runtime_check(settings, port)
        current["instance_id"] = instance_id
        current["native_supervisor_configured"] = controller is not None
        return JSONResponse(current, status_code=200 if not current["blockers"] else 503)

    @app.get("/system/native-supervisor", tags=["system"])
    def native_status():
        return controller.status() if controller is not None else unconfigured_status(instance_id)

    def control(action, request):
        if controller is None:
            raise HTTPException(status_code=409, detail="managed_supervisor_unconfigured")
        try:
            return getattr(controller, action)(request)
        except NativeLifecycleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="managed_control_unavailable") from exc

    @app.post("/system/native-supervisor/start", tags=["system"])
    def native_start(request: NativeControlRequest):
        return control("start", request)

    @app.post("/system/native-supervisor/stop", tags=["system"])
    def native_stop(request: NativeControlRequest):
        return control("stop", request)

    return app
