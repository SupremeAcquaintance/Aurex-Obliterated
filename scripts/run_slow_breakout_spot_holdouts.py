import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import select

from aurex.backtest_engine.candidate_decisions import (
    evaluate_slow_breakout_spot_cross_market,
)
from aurex.backtest_engine.candidate_protocols import (
    SLOW_BREAKOUT_SPOT_V1_DATASET_IDS,
    SLOW_BREAKOUT_SPOT_V1_EXECUTION_SPECS,
    slow_breakout_spot_v1_preregistrations,
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
    "data/evidence/slow_breakout_spot_v1_1.0.0_cross_market_decision.json"
)
EXECUTION_SPEC_SOURCE = (
    "https://data-api.binance.vision/api/v3/exchangeInfo"
)
EXECUTION_SPEC_RETRIEVED_AT = "2026-07-22T11:46:00Z"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen ETHUSDT and SOLUSDT slow-breakout holdouts as one "
            "audited decision."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify frozen protocols and requests without loading candles or outcomes.",
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


def frozen_campaign() -> list[dict]:
    source = strategy_source_evidence("slow_breakout_spot_v1", "1.0.0")
    if not source.get("ready"):
        raise RuntimeError(
            "slow_breakout_source_evidence_blocked:"
            + ",".join(str(reason) for reason in source.get("reasons") or [])
        )
    campaign: list[dict] = []
    with SessionLocal() as session:
        for package in slow_breakout_spot_v1_preregistrations():
            symbol = package.protocol.symbols[0]
            expected_snapshot = build_backtest_protocol_snapshot(package.protocol)
            expected_hash = build_backtest_protocol_hash(expected_snapshot)
            protocol = session.execute(
                select(BacktestProtocol).where(
                    BacktestProtocol.protocol_hash == expected_hash
                )
            ).scalar_one_or_none()
            if protocol is None:
                raise LookupError(f"authoritative_protocol_missing:{symbol}:{expected_hash}")
            recorded_source = protocol.protocol_snapshot.get(
                "strategy_source_evidence"
            ) or {}
            if recorded_source.get("pine_source_sha256") != source.get(
                "pine_source_sha256"
            ):
                raise RuntimeError(f"protocol_source_drift:{symbol}")
            execution_spec = SLOW_BREAKOUT_SPOT_V1_EXECUTION_SPECS[symbol]
            request = ReferenceReplayRequest(
                dataset_id=SLOW_BREAKOUT_SPOT_V1_DATASET_IDS[symbol],
                strategy="slow_breakout_spot_v1",
                strategy_version="1.0.0",
                parameters=dict(package.protocol.parameters),
                tick_size=execution_spec["tick_size"],
                point_value=execution_spec["point_value"],
                minimum_contract=execution_spec["minimum_contract"],
                commission_percent="0.05",
                slippage_ticks=2,
                intrabar_policy="stop_first",
            )
            campaign.append(
                {
                    "symbol": symbol,
                    "protocol_id": protocol.id,
                    "protocol_hash": protocol.protocol_hash,
                    "protocol_registered_at": protocol.registered_at,
                    "walk_forward_plan_hash": package.walk_forward_plan_hash,
                    "request": request,
                    "request_hash": canonical_hash(request.model_dump(mode="json")),
                    "pine_source_sha256": source["pine_source_sha256"],
                }
            )
    return campaign


def campaign_snapshot(campaign: list[dict]) -> dict:
    return {
        "strategy": "slow_breakout_spot_v1",
        "strategy_version": "1.0.0",
        "execution_spec_source": EXECUTION_SPEC_SOURCE,
        "execution_spec_retrieved_at": EXECUTION_SPEC_RETRIEVED_AT,
        "holdouts": [
            {
                "symbol": item["symbol"],
                "protocol_id": item["protocol_id"],
                "protocol_hash": item["protocol_hash"],
                "protocol_registered_at": item["protocol_registered_at"],
                "walk_forward_plan_hash": item["walk_forward_plan_hash"],
                "request_hash": item["request_hash"],
                "request": item["request"].model_dump(mode="json"),
                "pine_source_sha256": item["pine_source_sha256"],
            }
            for item in campaign
        ],
    }


def execute_campaign(campaign: list[dict], *, started_at: datetime) -> dict:
    expected_dataset_ids = {
        item["request"].dataset_id for item in campaign
    }
    with SessionLocal() as session:
        unexpected = session.execute(
            select(BacktestReferenceReplayRun).where(
                BacktestReferenceReplayRun.strategy == "slow_breakout_spot_v1",
                BacktestReferenceReplayRun.strategy_version == "1.0.0",
                BacktestReferenceReplayRun.dataset_id.not_in(expected_dataset_ids),
            )
        ).scalars().first()
        if unexpected is not None:
            raise RuntimeError(f"unexpected_candidate_outcome_exists:{unexpected.id}")

        replay_receipts: list[dict] = []
        for item in campaign:
            record, reused = ReferenceReplayEvidenceLab(session).record(item["request"])
            replay_receipts.append(
                {
                    "symbol": item["symbol"],
                    "record_id": record.id,
                    "record_evidence_hash": record.record_evidence_hash,
                    "engine_evidence_hash": record.engine_evidence_hash,
                    "reused_existing": reused,
                }
            )
        session.commit()

    validation_requests = [
        ReferenceReplayValidationRequest(
            reference_replay_run_id=receipt["record_id"],
            protocol_id=item["protocol_id"],
        )
        for item, receipt in zip(campaign, replay_receipts, strict=True)
    ]
    with SessionLocal() as session:
        validation_preflights = [
            ReferenceReplayValidationLab(session).preflight(request)
            for request in validation_requests
        ]
        for response in validation_preflights:
            if response.status == "BLOCKED":
                raise RuntimeError(
                    f"validation_binding_blocked:{response.symbol}:"
                    + ",".join(response.reasons)
                )
        for request in validation_requests:
            ReferenceReplayValidationLab(session).record(request)
        session.commit()

    replay_audits = []
    validation_audits = []
    persisted_validations = []
    with SessionLocal() as session:
        for receipt in replay_receipts:
            replay = session.get(BacktestReferenceReplayRun, receipt["record_id"])
            if replay is None:
                raise RuntimeError(f"replay_commit_missing:{receipt['record_id']}")
            replay_audits.append(
                ReferenceReplayEvidenceLab(session).audit(replay).model_dump(mode="json")
            )
        for request in validation_requests:
            validation = session.execute(
                select(BacktestReferenceReplayValidation).where(
                    BacktestReferenceReplayValidation.reference_replay_run_id
                    == request.reference_replay_run_id,
                    BacktestReferenceReplayValidation.protocol_id
                    == request.protocol_id,
                )
            ).scalar_one_or_none()
            if validation is None:
                raise RuntimeError(
                    f"validation_commit_missing:{request.reference_replay_run_id}"
                )
            persisted_validations.append(
                reference_validation_record_response(validation).model_dump(mode="json")
            )
            validation_audits.append(
                ReferenceReplayValidationLab(session).audit(validation).model_dump(
                    mode="json"
                )
            )

    if any(audit["status"] != "PASS" for audit in replay_audits):
        raise RuntimeError("replay_audit_failed")
    if any(audit["status"] != "PASS" for audit in validation_audits):
        raise RuntimeError("validation_audit_failed")
    decision = evaluate_slow_breakout_spot_cross_market(persisted_validations)
    completed_at = datetime.now(UTC)
    artifact_payload = {
        "artifact_schema_version": "aurex-holdout-campaign-artifact-v1",
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        **campaign_snapshot(campaign),
        "replays": replay_receipts,
        "validations": persisted_validations,
        "replay_audits": replay_audits,
        "validation_audits": validation_audits,
        "cross_market_decision": decision,
    }
    artifact_hash = canonical_hash(artifact_payload)
    artifact = {**artifact_payload, "artifact_evidence_hash": artifact_hash}
    write_artifact(artifact)
    return {
        "status": (
            "COMPLETE_ACCEPTED"
            if decision["status"] == "ACCEPT"
            else "COMPLETE_REJECTED"
        ),
        "artifact_path": str(ARTIFACT_PATH),
        "artifact_evidence_hash": artifact_hash,
        "cross_market_decision": decision,
        "replays": replay_receipts,
        "validation_audits": [
            {
                "reference_replay_validation_id": audit[
                    "reference_replay_validation_id"
                ],
                "status": audit["status"],
            }
            for audit in validation_audits
        ],
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
