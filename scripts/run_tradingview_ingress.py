"""Check or serve a webhook-only direct-TLS listener. Never opens a tunnel."""

import argparse
import json
import os
import sqlite3
import ssl
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from aurex.api.webhook_ingress import (
    create_webhook_ingress,
    ingress_configuration_blockers,
)
from aurex.config.settings import Settings


def database_schema_check(settings: Settings) -> bool:
    """Check the supported local campaign DB without creating or modifying it."""
    try:
        url = make_url(settings.database_url)
        if url.get_backend_name() != "sqlite" or not url.database or url.query:
            return False
        path = Path(url.database).resolve()
        if not path.is_file():
            return False
        migrations = Path(__file__).resolve().parents[1] / "infra" / "alembic"
        expected = set(ScriptDirectory(str(migrations)).get_heads())
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
            rows = connection.execute("select version_num from alembic_version")
            actual = {row[0] for row in rows}
        return bool(expected) and actual == expected
    except (OSError, sqlite3.Error, ArgumentError, ValueError):
        return False


def deployment_check(settings: Settings, certfile: str | None, keyfile: str | None) -> dict:
    blockers = ingress_configuration_blockers(settings)
    schema_verified = database_schema_check(settings)
    if not schema_verified:
        blockers.append("CURRENT_LOCAL_SQLITE_MIGRATION_REQUIRED")
    tls_loaded = False
    if not certfile or not keyfile:
        blockers.append("TLS_CERTIFICATE_AND_PRIVATE_KEY_REQUIRED")
    else:
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(certfile, keyfile, password="")
            tls_loaded = True
        except (OSError, ssl.SSLError, ValueError):
            blockers.append("TLS_CERTIFICATE_OR_KEY_UNUSABLE")
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "status": "LOCAL_CONFIG_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "tls_key_pair_loadable": tls_loaded,
        "proxy_headers_trusted": False,
        "access_logging_enabled": False,
        "scope": "RETIRED_CANDIDATE_SAFE_REJECTION_ONLY",
        "public_reachability_verified": False,
        "certificate_hostname_and_public_trust_verified": False,
        "external_delivery_proven": False,
        "database_schema_verified": schema_verified,
        "credentials_in_report": False,
        "live_authority": False,
        "remaining_external_requirements": [
            "Approved direct IPv4 HTTPS hostname and publicly trusted certificate on port 443",
            "Fresh no-write signal preflight on the deployment database",
            "Official sender list rechecked within 24 hours before the alert",
            "TradingView 2FA, webhook access, and authority to create one alert",
            "Genuine alert log and matching receipt independently reconciled",
        ],
    }


def server_config(settings: Settings, certfile: str, keyfile: str, host: str) -> uvicorn.Config:
    return uvicorn.Config(
        create_webhook_ingress(settings),
        host=host,
        port=443,
        proxy_headers=False,
        forwarded_allow_ips="",
        access_log=False,
        ssl_certfile=certfile,
        ssl_keyfile=keyfile,
        ssl_keyfile_password="",
        ssl_ciphers="ECDHE+AESGCM:ECDHE+CHACHA20",
        workers=1,
        timeout_keep_alive=2,
        limit_concurrency=8,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--serve", action="store_true")
    parser.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    parser.add_argument("--output", type=Path, help="New credential-free preflight report")
    args = parser.parse_args()
    try:
        settings = Settings()
    except ValidationError:
        print(json.dumps({"status": "BLOCKED", "blockers": ["INVALID_SETTINGS"]}))
        return 2
    certfile = os.environ.get("AUREX_INGRESS_TLS_CERTFILE")
    keyfile = os.environ.get("AUREX_INGRESS_TLS_KEYFILE")
    report = deployment_check(settings, certfile, keyfile)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(rendered)
    print(rendered, end="")
    if report["blockers"]:
        return 2
    if args.serve:
        uvicorn.Server(server_config(settings, certfile, keyfile, args.host)).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
