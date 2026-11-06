from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_feature_execution import (  # noqa: E402
    S1NfciFeatureExecutionAddendum,
)
from aurex.backtest_engine.s1_nfci_feature_protocol import (  # noqa: E402
    S1NfciFeatureProtocol,
    S1NfciFeatureProtocolAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402
from scripts.run_s1_nfci_features import runner_contract_hash  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s1_nfci_feature_execution_addendum_v1.json")
PROTOCOL_PATH = Path("data/evidence/s1_nfci_feature_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path("data/evidence/s1_nfci_feature_protocol_audit_v1.json")
FEATURE_OUTPUT_PATH = Path(
    "data/evidence/datasets/s1_nfci_development_features_v1.jsonl"
)
RESULT_PATH = Path("data/evidence/s1_nfci_feature_result_v1.json")
SCRIPT_PATH = Path("scripts/freeze_s1_nfci_feature_execution.py")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def build_addendum(*, frozen_at: datetime) -> S1NfciFeatureExecutionAddendum:
    protocol = S1NfciFeatureProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciFeatureProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        protocol.next_authorization
        != "AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_RUNNER_IMPLEMENTATION_ONLY"
        or protocol.authorizes_feature_calculation_now
        or audit.protocol_file_sha256 != file_sha256(PROTOCOL_PATH)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or FEATURE_OUTPUT_PATH.exists()
        or RESULT_PATH.exists()
    ):
        raise ValueError("S1 NFCI feature execution preconditions failed")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "protocol_file_sha256": file_sha256(PROTOCOL_PATH),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_file_sha256": file_sha256(PROTOCOL_AUDIT_PATH),
        "protocol_audit_evidence_hash": audit.audit_evidence_hash,
        "normalization_result_evidence_hash": (
            protocol.normalization_result_evidence_hash
        ),
        "normalization_audit_evidence_hash": (
            protocol.normalization_audit_evidence_hash
        ),
        "normalized_dataset_file_sha256": protocol.normalized_dataset_file_sha256,
        "input_row_manifest_evidence_hash": (
            protocol.input_row_manifest_evidence_hash
        ),
        "runner_contract_hash": runner_contract_hash(),
        "synthetic_test_ids": (
            "EXACT_DECIMAL_LEVEL_AND_LAG_DIFFERENCES",
            "NEGATIVE_ZERO_CANONICALIZED_TO_ZERO",
            "EXACT_FOUR_ROW_WARMUP_AND_277_OUTPUT_ROWS",
            "NORMALIZED_ROW_HASH_TAMPER_REJECTED",
            "SORTED_COMPACT_FEATURE_JSONL_REPRODUCES",
            "NO_FLOAT_BTC_RETURN_SIGNAL_OR_ORDER_FIELDS",
        ),
    }
    provisional = S1NfciFeatureExecutionAddendum.model_construct(
        **payload,
        addendum_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["addendum_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"addendum_evidence_hash"})
    )
    return S1NfciFeatureExecutionAddendum.model_validate(complete)


def write_atomic(path: Path, addendum: S1NfciFeatureExecutionAddendum) -> None:
    if path.exists():
        raise ValueError(f"S1 feature execution exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 feature execution transaction: {temporary}")
    serialized = addendum.model_dump_json(indent=2) + "\n"
    if S1NfciFeatureExecutionAddendum.model_validate_json(serialized) != addendum:
        raise ValueError("S1 feature execution addendum did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze S1 feature execution.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1NfciFeatureExecutionAddendum.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_addendum(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S1 feature execution differs")
        print(f"PASS {stored.addendum_evidence_hash}")
        return 0
    addendum = build_addendum(frozen_at=datetime.now(UTC))
    write_atomic(args.output, addendum)
    print(
        f"FROZEN {args.output} {addendum.addendum_evidence_hash} "
        "normalized_rows_parsed=0 feature_rows=0 btc_values=0 returns=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
