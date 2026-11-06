from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_bigquery_feasibility import (  # noqa: E402
    S2FeasibilityBinding,
    build_hashed,
)
from aurex.backtest_engine.s2_bigquery_feasibility_v3 import (  # noqa: E402
    S2_FEASIBILITY_V3_PASS,
    S2BigQueryFeasibilityAuditV3,
    S2BigQueryFeasibilityResultV3,
)
from aurex.backtest_engine.s2_bigquery_payload import (  # noqa: E402
    S2_PAYLOAD_BLOCK_VALIDATION,
    S2_PAYLOAD_PASS,
    S2BigQueryPayloadProtocol,
    S2BigQueryPayloadProtocolAudit,
    S2BigQueryPayloadResult,
)
from aurex.backtest_engine.s2_bigquery_payload_v2 import (  # noqa: E402
    S2BigQueryPayloadAuditV2,
    S2BigQueryPayloadFailureAuditV1,
    S2BigQueryPayloadProtocolAuditV2,
    S2BigQueryPayloadProtocolV2,
    S2BigQueryPayloadResultV2,
)
from aurex.backtest_engine.s2_development_measurement_protocol import (  # noqa: E402
    S2_MEASUREMENT_GATES,
    S2DevelopmentMeasurementProtocol,
    S2MeasurementDefinition,
)
from aurex.backtest_engine.s2_onchain_settlement_charter import (  # noqa: E402
    S2OnchainSettlementCharter,
    S2OnchainSettlementCharterAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s2_development_measurement_protocol_v1.json")
CHARTER_PATH = Path("data/evidence/s2_onchain_settlement_charter_v1.json")
CHARTER_AUDIT_PATH = Path("data/evidence/s2_onchain_settlement_charter_audit_v1.json")
FEASIBILITY_PROTOCOL_V3_PATH = Path("data/evidence/s2_bigquery_feasibility_protocol_v3.json")
FEASIBILITY_PROTOCOL_AUDIT_V3_PATH = Path(
    "data/evidence/s2_bigquery_feasibility_protocol_audit_v3.json"
)
FEASIBILITY_RESULT_V3_PATH = Path("data/evidence/s2_bigquery_feasibility_result_v3.json")
FEASIBILITY_AUDIT_V3_PATH = Path("data/evidence/s2_bigquery_feasibility_audit_v3.json")
PAYLOAD_PROTOCOL_V1_PATH = Path("data/evidence/s2_bigquery_payload_protocol_v1.json")
PAYLOAD_PROTOCOL_AUDIT_V1_PATH = Path("data/evidence/s2_bigquery_payload_protocol_audit_v1.json")
PAYLOAD_RESULT_V1_PATH = Path("data/evidence/s2_bigquery_payload_result_v1.json")
PAYLOAD_FAILURE_AUDIT_V1_PATH = Path("data/evidence/s2_bigquery_payload_failure_audit_v1.json")
PAYLOAD_PROTOCOL_V2_PATH = Path("data/evidence/s2_bigquery_payload_protocol_v2.json")
PAYLOAD_PROTOCOL_AUDIT_V2_PATH = Path("data/evidence/s2_bigquery_payload_protocol_audit_v2.json")
PAYLOAD_RESULT_V2_PATH = Path("data/evidence/s2_bigquery_payload_result_v2.json")
PAYLOAD_AUDIT_V2_PATH = Path("data/evidence/s2_bigquery_payload_audit_v2.json")
PAYLOAD_PATH = Path("data/evidence/s2_development_weekly_payload_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s2_development_measurement_protocol.py")


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(MODULE_PATH),
            "builder_path": Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix(),
            "builder_sha256": file_sha256(Path(__file__)),
        }
    )


def source_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                CHARTER_PATH,
                CHARTER_AUDIT_PATH,
                FEASIBILITY_PROTOCOL_V3_PATH,
                FEASIBILITY_PROTOCOL_AUDIT_V3_PATH,
                FEASIBILITY_RESULT_V3_PATH,
                FEASIBILITY_AUDIT_V3_PATH,
                PAYLOAD_PROTOCOL_V1_PATH,
                PAYLOAD_PROTOCOL_AUDIT_V1_PATH,
                PAYLOAD_RESULT_V1_PATH,
                PAYLOAD_FAILURE_AUDIT_V1_PATH,
                PAYLOAD_PROTOCOL_V2_PATH,
                PAYLOAD_PROTOCOL_AUDIT_V2_PATH,
                PAYLOAD_RESULT_V2_PATH,
                PAYLOAD_AUDIT_V2_PATH,
                PAYLOAD_PATH,
            ),
            key=lambda item: item.as_posix(),
        )
    )


def load_lineage():
    charter = S2OnchainSettlementCharter.model_validate_json(CHARTER_PATH.read_text())
    charter_audit = S2OnchainSettlementCharterAudit.model_validate_json(
        CHARTER_AUDIT_PATH.read_text()
    )
    feasibility_result = S2BigQueryFeasibilityResultV3.model_validate_json(
        FEASIBILITY_RESULT_V3_PATH.read_text()
    )
    feasibility_audit = S2BigQueryFeasibilityAuditV3.model_validate_json(
        FEASIBILITY_AUDIT_V3_PATH.read_text()
    )
    payload_protocol_v1 = S2BigQueryPayloadProtocol.model_validate_json(
        PAYLOAD_PROTOCOL_V1_PATH.read_text()
    )
    payload_protocol_audit_v1 = S2BigQueryPayloadProtocolAudit.model_validate_json(
        PAYLOAD_PROTOCOL_AUDIT_V1_PATH.read_text()
    )
    payload_result_v1 = S2BigQueryPayloadResult.model_validate_json(
        PAYLOAD_RESULT_V1_PATH.read_text()
    )
    payload_failure_audit_v1 = S2BigQueryPayloadFailureAuditV1.model_validate_json(
        PAYLOAD_FAILURE_AUDIT_V1_PATH.read_text()
    )
    payload_protocol_v2 = S2BigQueryPayloadProtocolV2.model_validate_json(
        PAYLOAD_PROTOCOL_V2_PATH.read_text()
    )
    payload_protocol_audit_v2 = S2BigQueryPayloadProtocolAuditV2.model_validate_json(
        PAYLOAD_PROTOCOL_AUDIT_V2_PATH.read_text()
    )
    payload_result_v2 = S2BigQueryPayloadResultV2.model_validate_json(
        PAYLOAD_RESULT_V2_PATH.read_text()
    )
    payload_audit_v2 = S2BigQueryPayloadAuditV2.model_validate_json(
        PAYLOAD_AUDIT_V2_PATH.read_text()
    )
    if (
        charter.charter_evidence_hash != charter_audit.charter_evidence_hash
        or feasibility_result.decision != S2_FEASIBILITY_V3_PASS
        or feasibility_result.result_evidence_hash != feasibility_audit.result_evidence_hash
        or payload_protocol_v1.protocol_evidence_hash
        != payload_protocol_audit_v1.protocol_evidence_hash
        or payload_result_v1.decision != S2_PAYLOAD_BLOCK_VALIDATION
        or payload_result_v1.result_evidence_hash != payload_failure_audit_v1.result_evidence_hash
        or payload_protocol_v2.prior_payload_result_evidence_hash
        != payload_result_v1.result_evidence_hash
        or payload_protocol_v2.protocol_evidence_hash
        != payload_protocol_audit_v2.protocol_evidence_hash
        or payload_result_v2.decision != S2_PAYLOAD_PASS
        or payload_result_v2.result_evidence_hash != payload_audit_v2.result_evidence_hash
        or payload_result_v2.payload_file_sha256 != file_sha256(PAYLOAD_PATH)
        or payload_result_v2.payload_file_sha256 != payload_audit_v2.payload_file_sha256
        or payload_result_v2.payload_evidence_hash != payload_audit_v2.payload_evidence_hash
        or payload_result_v2.payload_byte_count != PAYLOAD_PATH.stat().st_size
        or payload_result_v2.payload_byte_count != 94_662
        or payload_result_v2.query_result_rows_returned != 280
    ):
        raise ValueError("S2 measurement predecessor lineage did not reconcile")
    return (
        charter,
        payload_protocol_v2,
        payload_protocol_audit_v2,
        payload_result_v2,
        payload_audit_v2,
    )


def measurement_definitions() -> tuple[S2MeasurementDefinition, ...]:
    return (
        S2MeasurementDefinition(
            measurement_id="confirmed_tx_current_4w",
            formula="SUM_CONFIRMED_NON_COINBASE_TX_LAGS_0_TO_3",
            output_type="INTEGER",
            unit="TRANSACTIONS",
            maximum_lag_weeks=3,
        ),
        S2MeasurementDefinition(
            measurement_id="confirmed_tx_prior_4w",
            formula="SUM_CONFIRMED_NON_COINBASE_TX_LAGS_4_TO_7",
            output_type="INTEGER",
            unit="TRANSACTIONS",
            maximum_lag_weeks=7,
        ),
        S2MeasurementDefinition(
            measurement_id="confirmed_fee_sats_current_4w",
            formula="SUM_CONFIRMED_FEE_SATOSHIS_LAGS_0_TO_3",
            output_type="INTEGER",
            unit="SATOSHIS",
            maximum_lag_weeks=3,
        ),
        S2MeasurementDefinition(
            measurement_id="confirmed_fee_sats_prior_4w",
            formula="SUM_CONFIRMED_FEE_SATOSHIS_LAGS_4_TO_7",
            output_type="INTEGER",
            unit="SATOSHIS",
            maximum_lag_weeks=7,
        ),
        S2MeasurementDefinition(
            measurement_id="confirmed_tx_growth_ppm",
            formula=("ROUND_HALF_EVEN_1E6_TIMES_CURRENT_MINUS_PRIOR_DIVIDED_BY_PRIOR_TX"),
            output_type="INTEGER",
            unit="PARTS_PER_MILLION",
            maximum_lag_weeks=7,
        ),
        S2MeasurementDefinition(
            measurement_id="confirmed_fee_growth_ppm",
            formula=("ROUND_HALF_EVEN_1E6_TIMES_CURRENT_MINUS_PRIOR_DIVIDED_BY_PRIOR_FEE"),
            output_type="INTEGER",
            unit="PARTS_PER_MILLION",
            maximum_lag_weeks=7,
        ),
        S2MeasurementDefinition(
            measurement_id="settlement_demand_agreement",
            formula=(
                "BOTH_BROADENING_IF_BOTH_GROWTH_PPM_GT_ZERO_BOTH_CONTRACTING_IF_"
                "BOTH_LT_ZERO_ELSE_FLAT_OR_MIXED"
            ),
            output_type="ENUM",
            unit="CATEGORY",
            maximum_lag_weeks=7,
        ),
    )


def build_protocol(*, frozen_at: datetime) -> S2DevelopmentMeasurementProtocol:
    (
        charter,
        payload_protocol,
        payload_protocol_audit,
        payload_result,
        payload_audit,
    ) = load_lineage()
    paths = source_paths()
    if len(paths) != 15 or not all(path.is_file() for path in paths):
        raise ValueError("S2 measurement source set is incomplete")
    values = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "charter_evidence_hash": charter.charter_evidence_hash,
        "payload_protocol_evidence_hash": payload_protocol.protocol_evidence_hash,
        "payload_protocol_audit_evidence_hash": payload_protocol_audit.audit_evidence_hash,
        "payload_result_evidence_hash": payload_result.result_evidence_hash,
        "payload_result_audit_evidence_hash": payload_audit.audit_evidence_hash,
        "payload_file_sha256": payload_result.payload_file_sha256,
        "payload_evidence_hash": payload_result.payload_evidence_hash,
        "source_bindings": tuple(
            S2FeasibilityBinding(path=path.as_posix(), file_sha256=file_sha256(path))
            for path in paths
        ),
        "measurement_definitions": measurement_definitions(),
        "quality_gates": S2_MEASUREMENT_GATES,
        "limitations": tuple(
            sorted(
                (
                    "All historical target periods remain outcome-aware and nonqualifying.",
                    (
                        "Fee growth can reflect congestion or fee-market conditions rather "
                        "than broader user demand."
                    ),
                    (
                        "Four-week aggregation is an ex-ante measurement choice, not "
                        "evidence of optimality."
                    ),
                    "Measurement construction cannot define a trading rule or strategy candidate.",
                    (
                        "No market price or return may be read while constructing this "
                        "measurement dataset."
                    ),
                    (
                        "Payload acquisition success does not establish predictive value "
                        "or profitability."
                    ),
                    "Prospective validation and future holdout remain sealed.",
                    "The agreement category is descriptive and cannot itself authorize a position.",
                    (
                        "The single future candidate budget forbids outcome-driven model "
                        "or threshold search."
                    ),
                    (
                        "Trading, Testnet strategy orders, production, live authority, "
                        "real capital, and profit remain zero."
                    ),
                )
            )
        ),
    }
    return build_hashed(S2DevelopmentMeasurementProtocol, "protocol_evidence_hash", values)


def write_protocol(path: Path, protocol: S2DevelopmentMeasurementProtocol) -> None:
    if path.exists():
        raise ValueError(f"S2 development measurement protocol exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S2DevelopmentMeasurementProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S2 development measurement protocol did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze S2 development measurement protocol.")
    parser.add_argument("--freeze", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "payload_rows_parsed=0 market_values=0 parameters=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
