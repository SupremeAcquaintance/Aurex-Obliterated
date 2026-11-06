import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import select

from aurex.backtest_engine.candidate_protocols import (
    JAM_REVERSAL_SPOT_V1_DATASET_ID,
    JAM_REVERSAL_SPOT_V1_PINE_SHA256,
    jam_reversal_spot_v1_preregistration,
)
from aurex.backtest_engine.reference_replay import ReferenceReplayEvidenceLab
from aurex.backtest_engine.reference_validation import (
    ReferenceReplayValidationLab,
    reference_validation_record_response,
)
from aurex.backtest_engine.schemas import (
    ReferenceReplayRequest,
    ReferenceReplayValidationRequest,
)
from aurex.backtest_engine.service import (
    build_backtest_protocol_hash,
    build_backtest_protocol_snapshot,
    strategy_source_evidence,
)
from aurex.db.models import (
    BacktestProtocol,
    BacktestReferenceReplayRun,
    BacktestReferenceReplayValidation,
)
from aurex.db.session import SessionLocal

ARTIFACT_PATH = Path(
    "data/evidence/jam_reversal_spot_v1_1.0.1_historical_decision.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen Jam Reversal Spot v1.0.1 historical decision once, "
            "then record and audit its immutable validation."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify the frozen protocol and request without loading return outcomes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = datetime.now(UTC)
    try:
        campaign = frozen_campaign()
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "status": "DRY_RUN_READY",
                        "mutates_ledger": False,
                        **campaign_snapshot(campaign),
                    },
                    indent=2,
                    default=str,
                )
            )
            return 0
        result = execute_campaign(campaign, started_at=started_at)
    except (LookupError, RuntimeError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, indent=2))
        return 1

    print(json.dumps(result, indent=2, default=str))
    return 0


def frozen_campaign() -> dict:
    package = jam_reversal_spot_v1_preregistration()
    source = strategy_source_evidence("jam_reversal_spot_v1", "1.0.1")
    if not source.get("ready"):
        raise RuntimeError(
            "jam_reversal_spot_source_evidence_blocked:"
            + ",".join(str(reason) for reason in source.get("reasons") or [])
        )
    if source.get("pine_source_sha256") != JAM_REVERSAL_SPOT_V1_PINE_SHA256:
        raise RuntimeError("jam_reversal_spot_pine_source_hash_drift")

    expected_snapshot = build_backtest_protocol_snapshot(package.protocol)
    expected_hash = build_backtest_protocol_hash(expected_snapshot)
    with SessionLocal() as session:
        protocol = session.execute(
            select(BacktestProtocol).where(
                BacktestProtocol.protocol_hash == expected_hash
            )
        ).scalar_one_or_none()
        if protocol is None:
            raise LookupError(
                f"authoritative_jam_protocol_missing:{expected_hash}"
            )
        recorded_source = protocol.protocol_snapshot.get(
            "strategy_source_evidence"
        ) or {}
        if (
            recorded_source.get("pine_source_sha256")
            != source.get("pine_source_sha256")
        ):
            raise RuntimeError("jam_reversal_spot_protocol_source_drift")

    request = ReferenceReplayRequest(
        dataset_id=JAM_REVERSAL_SPOT_V1_DATASET_ID,
        strategy="jam_reversal_spot_v1",
        strategy_version="1.0.1",
        parameters=dict(package.protocol.parameters),
        tick_size="0.01",
        point_value="1",
        minimum_contract="0.00001",
        commission_percent="0.10",
        slippage_ticks=2,
        intrabar_policy="stop_first",
    )
    return {
        "protocol_id": protocol.id,
        "protocol_hash": protocol.protocol_hash,
        "protocol_registered_at": protocol.registered_at,
        "walk_forward_plan_hash": package.walk_forward_plan_hash,
        "request": request,
        "request_hash": canonical_hash(request.model_dump(mode="json")),
        "pine_source_sha256": source["pine_source_sha256"],
    }


def campaign_snapshot(campaign: dict) -> dict:
    return {
        "strategy": "jam_reversal_spot_v1",
        "strategy_version": "1.0.1",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "direction": "LONG_ONLY",
        "protocol_id": campaign["protocol_id"],
        "protocol_hash": campaign["protocol_hash"],
        "protocol_registered_at": campaign["protocol_registered_at"],
        "walk_forward_plan_hash": campaign["walk_forward_plan_hash"],
        "request_hash": campaign["request_hash"],
        "request": campaign["request"].model_dump(mode="json"),
        "pine_source_sha256": campaign["pine_source_sha256"],
    }


def execute_campaign(campaign: dict, *, started_at: datetime) -> dict:
    request = campaign["request"]
    with SessionLocal() as session:
        unrelated = session.execute(
            select(BacktestReferenceReplayRun).where(
                BacktestReferenceReplayRun.strategy
                == "jam_reversal_spot_v1",
                BacktestReferenceReplayRun.strategy_version == "1.0.1",
                BacktestReferenceReplayRun.dataset_id
                != JAM_REVERSAL_SPOT_V1_DATASET_ID,
            )
        ).scalars().first()
        if unrelated is not None:
            raise RuntimeError(
                f"unexpected_candidate_outcome_exists:{unrelated.id}"
            )
        replay, replay_reused = ReferenceReplayEvidenceLab(session).record(
            request
        )
        replay_id = replay.id
        replay_receipt = {
            "record_id": replay.id,
            "record_evidence_hash": replay.record_evidence_hash,
            "engine_evidence_hash": replay.engine_evidence_hash,
            "reused_existing": replay_reused,
        }
        session.commit()

    validation_request = ReferenceReplayValidationRequest(
        reference_replay_run_id=replay_id,
        protocol_id=campaign["protocol_id"],
    )
    with SessionLocal() as session:
        preflight = ReferenceReplayValidationLab(session).preflight(
            validation_request
        )
        if preflight.status == "BLOCKED":
            raise RuntimeError(
                "jam_validation_binding_blocked:"
                + ",".join(preflight.reasons)
            )
        validation, validation_reused = ReferenceReplayValidationLab(
            session
        ).record(validation_request)
        validation_id = validation.id
        session.commit()

    with SessionLocal() as session:
        replay = session.get(BacktestReferenceReplayRun, replay_id)
        validation = session.get(
            BacktestReferenceReplayValidation,
            validation_id,
        )
        if replay is None:
            raise RuntimeError(f"jam_replay_commit_missing:{replay_id}")
        if validation is None:
            raise RuntimeError(
                f"jam_validation_commit_missing:{validation_id}"
            )
        replay_audit = ReferenceReplayEvidenceLab(session).audit(
            replay
        ).model_dump(mode="json")
        validation_response = reference_validation_record_response(
            validation,
            reused_existing=validation_reused,
        ).model_dump(mode="json")
        validation_audit = ReferenceReplayValidationLab(session).audit(
            validation
        ).model_dump(mode="json")

    if replay_audit["status"] != "PASS":
        raise RuntimeError("jam_replay_audit_failed")
    if validation_audit["status"] != "PASS":
        raise RuntimeError("jam_validation_audit_failed")

    decision = (
        "ADVANCE_TO_TRADINGVIEW_PARITY"
        if validation_response["status"] == "PASSED"
        else "REJECT_CURRENT_VERSION"
    )
    completed_at = datetime.now(UTC)
    artifact_payload = {
        "artifact_schema_version": (
            "aurex-jam-reversal-spot-historical-decision-v1"
        ),
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        **campaign_snapshot(campaign),
        "replay": replay_receipt,
        "validation": validation_response,
        "replay_audit": replay_audit,
        "validation_audit": validation_audit,
        "decision": decision,
        "paper_authorized": False,
        "production_authorized": False,
    }
    artifact_hash = canonical_hash(artifact_payload)
    artifact = {
        **artifact_payload,
        "artifact_evidence_hash": artifact_hash,
    }
    write_artifact(artifact)
    return {
        "status": (
            "COMPLETE_PASSED"
            if validation_response["status"] == "PASSED"
            else "COMPLETE_REJECTED"
        ),
        "decision": decision,
        "artifact_path": str(ARTIFACT_PATH),
        "artifact_evidence_hash": artifact_hash,
        "replay": replay_receipt,
        "validation": {
            "id": validation_response["id"],
            "status": validation_response["status"],
            "statistical_acceptance_passed": validation_response[
                "statistical_acceptance_passed"
            ],
            "acceptance_reasons": validation_response[
                "acceptance_reasons"
            ],
        },
        "replay_audit_status": replay_audit["status"],
        "validation_audit_status": validation_audit["status"],
        "paper_authorized": False,
        "production_authorized": False,
    }


def canonical_hash(payload: object) -> str:
    return sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()


def write_artifact(payload: dict) -> None:
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = ARTIFACT_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(ARTIFACT_PATH)


if __name__ == "__main__":
    raise SystemExit(main())
