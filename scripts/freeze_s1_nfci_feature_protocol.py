from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_feature_protocol import (  # noqa: E402
    S1_NFCI_FEATURE_GATES,
    S1NfciFeatureDefinition,
    S1NfciFeatureProtocol,
)
from aurex.backtest_engine.s1_nfci_normalization_execution import (  # noqa: E402
    S1NfciNormalizationResult,
    S1NfciNormalizationResultAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s1_nfci_feature_protocol_v1.json")
NORMALIZATION_RESULT_PATH = Path(
    "data/evidence/s1_nfci_normalization_result_v1.json"
)
NORMALIZATION_AUDIT_PATH = Path(
    "data/evidence/s1_nfci_normalization_result_audit_v1.json"
)
NORMALIZED_DATASET_PATH = Path(
    "data/evidence/datasets/s1_nfci_development_normalized_v1.jsonl"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s1_nfci_feature_protocol.py")
SCRIPT_PATH = Path("scripts/freeze_s1_nfci_feature_protocol.py")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def build_protocol(*, frozen_at: datetime) -> S1NfciFeatureProtocol:
    result = S1NfciNormalizationResult.model_validate_json(
        NORMALIZATION_RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciNormalizationResultAudit.model_validate_json(
        NORMALIZATION_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        result.decision != "PASS_S1_NFCI_DEVELOPMENT_NORMALIZATION"
        or result.next_authorization
        != "AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_PROTOCOL_ONLY"
        or audit.result_file_sha256 != file_sha256(NORMALIZATION_RESULT_PATH)
        or audit.result_evidence_hash != result.result_evidence_hash
        or audit.dataset_file_sha256 != result.dataset_file_sha256
        or file_sha256(NORMALIZED_DATASET_PATH) != result.dataset_file_sha256
        or NORMALIZED_DATASET_PATH.stat().st_size != result.dataset_bytes
    ):
        raise ValueError("S1 normalization does not authorize the feature protocol")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "normalization_result_file_sha256": file_sha256(
            NORMALIZATION_RESULT_PATH
        ),
        "normalization_result_evidence_hash": result.result_evidence_hash,
        "normalization_audit_file_sha256": file_sha256(NORMALIZATION_AUDIT_PATH),
        "normalization_audit_evidence_hash": audit.audit_evidence_hash,
        "normalized_dataset_file_sha256": result.dataset_file_sha256,
        "input_row_manifest_evidence_hash": universe_evidence_hash(
            result.row_evidence_hashes
        ),
        "normalization_decision": result.decision,
        "normalization_next_authorization": result.next_authorization,
        "feature_definitions": (
            S1NfciFeatureDefinition(
                feature_id="nfci_level",
                formula="CURRENT_NFCI_SOURCE_DECIMAL",
                required_lag_vintages=0,
            ),
            S1NfciFeatureDefinition(
                feature_id="nfci_change_1v",
                formula="CURRENT_NFCI_MINUS_LAG_1_VINTAGE_NFCI",
                required_lag_vintages=1,
            ),
            S1NfciFeatureDefinition(
                feature_id="nfci_change_4v",
                formula="CURRENT_NFCI_MINUS_LAG_4_VINTAGE_NFCI",
                required_lag_vintages=4,
            ),
        ),
        "quality_gates": S1_NFCI_FEATURE_GATES,
    }
    provisional = S1NfciFeatureProtocol.model_construct(
        **payload,
        protocol_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S1NfciFeatureProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S1NfciFeatureProtocol) -> None:
    if path.exists():
        raise ValueError(f"S1 feature protocol exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 feature protocol transaction: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S1NfciFeatureProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S1 feature protocol did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or check S1 features.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1NfciFeatureProtocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_protocol(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S1 feature protocol differs")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    write_atomic(args.output, protocol)
    print(
        f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
        "features=3 candidates=0 normalized_value_rows_parsed=0 btc_values=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
