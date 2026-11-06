from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_normalization import (  # noqa: E402
    S1NfciNormalizationProtocol,
    S1NfciNormalizationProtocolAudit,
)
from aurex.backtest_engine.s1_nfci_normalization_execution import (  # noqa: E402
    S1NfciNormalizationExecutionAddendum,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402
from scripts.run_s1_nfci_normalization import runner_contract_hash  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s1_nfci_normalization_execution_addendum_v1.json"
)
PROTOCOL_PATH = Path("data/evidence/s1_nfci_normalization_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s1_nfci_normalization_protocol_audit_v1.json"
)
NORMALIZED_OUTPUT_PATH = Path(
    "data/evidence/datasets/s1_nfci_development_normalized_v1.jsonl"
)
RESULT_PATH = Path("data/evidence/s1_nfci_normalization_result_v1.json")
SCRIPT_PATH = Path("scripts/freeze_s1_nfci_normalization_execution.py")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def build_addendum(*, frozen_at: datetime) -> S1NfciNormalizationExecutionAddendum:
    protocol = S1NfciNormalizationProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciNormalizationProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        protocol.next_authorization
        != "AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_RUNNER_IMPLEMENTATION_ONLY"
        or protocol.authorizes_value_transformation_now
        or audit.protocol_file_sha256 != file_sha256(PROTOCOL_PATH)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or NORMALIZED_OUTPUT_PATH.exists()
        or RESULT_PATH.exists()
    ):
        raise ValueError("S1 NFCI normalization execution preconditions failed")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "protocol_file_sha256": file_sha256(PROTOCOL_PATH),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_file_sha256": file_sha256(PROTOCOL_AUDIT_PATH),
        "protocol_audit_evidence_hash": audit.audit_evidence_hash,
        "acquisition_result_evidence_hash": (
            protocol.acquisition_result_evidence_hash
        ),
        "acquisition_audit_evidence_hash": protocol.acquisition_audit_evidence_hash,
        "input_manifest_evidence_hash": protocol.input_manifest_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "synthetic_test_ids": (
            "LATEST_VALID_DECIMAL_SELECTED_WITHOUT_ROUNDING",
            "DUPLICATE_OR_NON_INCREASING_DATE_REJECTED",
            "POST_VINTAGE_OBSERVATION_REJECTED",
            "MISSING_NONFINITE_OR_WHITESPACE_VALUE_REJECTED",
            "SORTED_COMPACT_JSONL_SERIALIZATION_REPRODUCES",
            "ZERO_DERIVED_FEATURE_BTC_RETURN_AND_ORDER_FIELDS",
        ),
    }
    provisional = S1NfciNormalizationExecutionAddendum.model_construct(
        **payload,
        addendum_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["addendum_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"addendum_evidence_hash"})
    )
    return S1NfciNormalizationExecutionAddendum.model_validate(complete)


def write_atomic(path: Path, addendum: S1NfciNormalizationExecutionAddendum) -> None:
    if path.exists():
        raise ValueError(f"S1 normalization execution exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 normalization execution transaction: {temporary}")
    serialized = addendum.model_dump_json(indent=2) + "\n"
    if S1NfciNormalizationExecutionAddendum.model_validate_json(serialized) != addendum:
        raise ValueError("S1 normalization execution addendum did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze S1 normalization execution.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1NfciNormalizationExecutionAddendum.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_addendum(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S1 normalization execution differs")
        print(f"PASS {stored.addendum_evidence_hash}")
        return 0
    addendum = build_addendum(frozen_at=datetime.now(UTC))
    write_atomic(args.output, addendum)
    print(
        f"FROZEN {args.output} {addendum.addendum_evidence_hash} "
        "raw_value_rows_read=0 btc_values=0 returns=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
