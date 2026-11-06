import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from aurex.config.settings import get_settings
from aurex.db.session import SessionLocal
from aurex.signal_gateway.schemas import TradingViewVerificationResponse
from aurex.signal_gateway.service import tradingview_signal_verification
from aurex.signal_gateway.tradingview_delivery import (
    TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS,
    TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL,
)
from aurex.signal_gateway.tradingview_external_proof import (
    EXPECTED_STRATEGY,
    EXPECTED_SYMBOL,
    EXTERNAL_PROOF_ATTESTATION,
    TradingViewExternalDeliveryProof,
    TradingViewExternalProofOperatorInput,
    audit_tradingview_external_delivery_proof,
    build_alert_log_artifact_evidence,
    build_tradingview_external_delivery_proof,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/tradingview_external_delivery_proof_v1.json"
)


def template_payload() -> dict:
    return {
        "schema_version": (
            "aurex-tradingview-external-proof-operator-input-v1"
        ),
        "operator_identifier": "NON_SECRET_OPERATOR_ALIAS",
        "attested_at": "YYYY-MM-DDTHH:MM:SS+00:00",
        "attestation_statement": EXTERNAL_PROOF_ATTESTATION,
        "source_network_authority_checked_at": (
            "YYYY-MM-DDTHH:MM:SS+00:00"
        ),
        "source_network_authority_url": (
            TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL
        ),
        "source_networks_observed": list(
            TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS
        ),
        "expected_signal_id": (
            "EXACT_SIGNAL_ID_RETURNED_BY_AUREX_AFTER_THE_GENUINE_ALERT"
        ),
        "alert_log_claim": {
            "alert_name": "AUREX_EXTERNAL_DELIVERY_PROOF_V1",
            "alert_fired_at": "YYYY-MM-DDTHH:MM:SS+00:00",
            "delivery_status": "DELIVERED",
            "webhook_status_text": (
                "EXACT_NON_SECRET_STATUS_SHOWN_IN_TRADINGVIEW_ALERT_LOG"
            ),
        },
        "credentials_stored_or_embedded": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight, freeze, or audit one TradingView external-delivery "
            "safe-rejection proof without authorizing trading."
        )
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--template", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--freeze", action="store_true")
    modes.add_argument("--check", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--alert-log", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def read_operator_input(path: Path) -> TradingViewExternalProofOperatorInput:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read operator input: {exc}") from exc
    return TradingViewExternalProofOperatorInput.model_validate(payload)


def durable_write_new(path: Path, payload: str) -> None:
    if path.exists():
        raise ValueError(f"refusing to overwrite immutable proof: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def require_paths(args: argparse.Namespace) -> None:
    if args.alert_log is None:
        raise ValueError("--alert-log is required for this mode")
    if not args.check and args.input is None:
        raise ValueError("--input is required for preflight or freeze")


def current_database_verification() -> TradingViewVerificationResponse:
    with SessionLocal() as session:
        return tradingview_signal_verification(
            session,
            get_settings(),
            strategy=EXPECTED_STRATEGY,
            symbol=EXPECTED_SYMBOL,
        )


def run() -> int:
    args = parse_args()
    if args.template:
        print(json.dumps(template_payload(), indent=2))
        return 0

    require_paths(args)
    alert_log_artifact = build_alert_log_artifact_evidence(args.alert_log)
    verification = current_database_verification()

    if args.check:
        proof = TradingViewExternalDeliveryProof.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        audit_tradingview_external_delivery_proof(
            proof,
            verification,
            alert_log_artifact,
        )
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "proof_id": proof.proof_id,
                    "decision": proof.decision,
                    "evidence_hash": proof.evidence_hash,
                },
                indent=2,
            )
        )
        return 0

    operator_input = read_operator_input(args.input)
    proof = build_tradingview_external_delivery_proof(
        operator_input,
        verification,
        alert_log_artifact,
    )
    rendered = proof.model_dump_json(indent=2) + "\n"
    if args.preflight:
        print(rendered, end="")
        return 0 if proof.status == "PASS" else 2
    if proof.status != "PASS":
        print(rendered, end="")
        raise ValueError("refusing to freeze a failed external-delivery proof")
    durable_write_new(args.output, rendered)
    print(
        json.dumps(
            {
                "status": "FROZEN",
                "output": str(args.output),
                "proof_id": proof.proof_id,
                "decision": proof.decision,
                "evidence_hash": proof.evidence_hash,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (OSError, ValidationError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
