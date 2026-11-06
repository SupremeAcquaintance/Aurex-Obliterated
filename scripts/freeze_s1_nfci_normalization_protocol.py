from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_full_execution import (  # noqa: E402
    S1NfciFullAcquisitionAudit,
    S1NfciFullAcquisitionResult,
)
from aurex.backtest_engine.s1_nfci_normalization import (  # noqa: E402
    S1_NFCI_NORMALIZATION_GATES,
    S1NfciNormalizationProtocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

DEFAULT_OUTPUT = Path("data/evidence/s1_nfci_normalization_protocol_v1.json")
ACQUISITION_RESULT_PATH = Path(
    "data/evidence/s1_nfci_full_acquisition_result_v1.json"
)
ACQUISITION_AUDIT_PATH = Path(
    "data/evidence/s1_nfci_full_acquisition_audit_v1.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/s1_nfci_normalization.py")
SCRIPT_PATH = Path("scripts/freeze_s1_nfci_normalization_protocol.py")


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "script_path": SCRIPT_PATH.as_posix(),
            "script_sha256": file_sha256(PROJECT_ROOT / SCRIPT_PATH),
        }
    )


def input_manifest(result: S1NfciFullAcquisitionResult) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "sequence": target.sequence,
            "target_id": target.target_id,
            "vintage_date": target.vintage_date.isoformat(),
            "expected_value_column": target.summary.csv_header[1],
            "raw_path": target.raw_path,
            "raw_file_sha256": target.raw_file_sha256,
            "raw_file_bytes": target.raw_file_bytes,
            "row_count": target.summary.row_count,
            "last_observation_date": (
                None
                if target.summary.last_observation_date is None
                else target.summary.last_observation_date.isoformat()
            ),
            "release_lag_days": target.summary.release_lag_days,
        }
        for target in result.target_evidence
    )


def build_protocol(*, frozen_at: datetime) -> S1NfciNormalizationProtocol:
    result = S1NfciFullAcquisitionResult.model_validate_json(
        ACQUISITION_RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciFullAcquisitionAudit.model_validate_json(
        ACQUISITION_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        result.decision != "PASS_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION"
        or result.next_authorization
        != "AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_PROTOCOL_ONLY"
        or result.complete_target_count != 281
        or result.failed_target_count != 0
        or audit.result_file_sha256 != file_sha256(ACQUISITION_RESULT_PATH)
        or audit.result_evidence_hash != result.result_evidence_hash
        or audit.checkpoint_evidence_hash != result.checkpoint_evidence_hash
        or audit.runner_contract_hash != result.runner_contract_hash
    ):
        raise ValueError("S1 acquisition does not authorize normalization protocol")
    manifest = input_manifest(result)
    if len(manifest) != 281:
        raise ValueError("S1 normalization input manifest is not complete")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "acquisition_result_file_sha256": file_sha256(ACQUISITION_RESULT_PATH),
        "acquisition_result_evidence_hash": result.result_evidence_hash,
        "acquisition_audit_file_sha256": file_sha256(ACQUISITION_AUDIT_PATH),
        "acquisition_audit_evidence_hash": audit.audit_evidence_hash,
        "acquisition_checkpoint_evidence_hash": result.checkpoint_evidence_hash,
        "acquisition_runner_contract_hash": result.runner_contract_hash,
        "acquisition_decision": result.decision,
        "acquisition_next_authorization": result.next_authorization,
        "input_manifest_evidence_hash": universe_evidence_hash(manifest),
        "quality_gates": S1_NFCI_NORMALIZATION_GATES,
    }
    provisional = S1NfciNormalizationProtocol.model_construct(
        **payload,
        protocol_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S1NfciNormalizationProtocol.model_validate(complete)


def write_atomic(path: Path, protocol: S1NfciNormalizationProtocol) -> None:
    if path.exists():
        raise ValueError(f"S1 normalization protocol exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 normalization protocol transaction: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S1NfciNormalizationProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("S1 normalization protocol did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or check S1 normalization.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1NfciNormalizationProtocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if stored != build_protocol(frozen_at=stored.frozen_at):
            raise SystemExit("Stored S1 normalization protocol differs")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    write_atomic(args.output, protocol)
    print(
        f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
        "vintages=281 raw_value_rows_read=0 btc_values=0 returns=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
