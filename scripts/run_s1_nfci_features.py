from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_feature_execution import (  # noqa: E402
    S1NfciFeatureExecutionAddendum,
    S1NfciFeatureExecutionAudit,
    S1NfciFeatureResult,
    S1NfciFeatureRow,
)
from aurex.backtest_engine.s1_nfci_feature_protocol import (  # noqa: E402
    S1_NFCI_FEATURE_GATES,
    S1NfciFeatureProtocol,
    S1NfciFeatureProtocolAudit,
)
from aurex.backtest_engine.s1_nfci_normalization_execution import (  # noqa: E402
    S1NfciNormalizationResult,
    S1NfciNormalizationResultAudit,
    S1NfciNormalizedRow,
)
from aurex.backtest_engine.s1_source_feasibility import S1SourceGate  # noqa: E402
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

PROTOCOL_PATH = Path("data/evidence/s1_nfci_feature_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path("data/evidence/s1_nfci_feature_protocol_audit_v1.json")
EXECUTION_ADDENDUM_PATH = Path(
    "data/evidence/s1_nfci_feature_execution_addendum_v1.json"
)
EXECUTION_AUDIT_PATH = Path(
    "data/evidence/s1_nfci_feature_execution_audit_v1.json"
)
NORMALIZATION_RESULT_PATH = Path(
    "data/evidence/s1_nfci_normalization_result_v1.json"
)
NORMALIZATION_AUDIT_PATH = Path(
    "data/evidence/s1_nfci_normalization_result_audit_v1.json"
)
NORMALIZED_DATASET_PATH = Path(
    "data/evidence/datasets/s1_nfci_development_normalized_v1.jsonl"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/datasets/s1_nfci_development_features_v1.jsonl"
)
DEFAULT_RESULT = Path("data/evidence/s1_nfci_feature_result_v1.json")
MODULE_PATH = Path("src/aurex/backtest_engine/s1_nfci_feature_execution.py")
RUNNER_PATH = Path("scripts/run_s1_nfci_features.py")


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "runner_path": RUNNER_PATH.as_posix(),
            "runner_sha256": file_sha256(PROJECT_ROOT / RUNNER_PATH),
        }
    )


def decimal_to_fixed(value: Decimal) -> str:
    return "0" if value == 0 else format(value, "f")


def parse_normalized_rows(
    payload: bytes,
    *,
    expected_row_hashes: tuple[str, ...],
) -> tuple[S1NfciNormalizedRow, ...]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("S1 normalized dataset is not UTF-8") from error
    if not text.endswith("\n"):
        raise ValueError("S1 normalized dataset lacks its final newline")
    raw_lines = text.splitlines()
    if len(raw_lines) != 281 or len(expected_row_hashes) != 281:
        raise ValueError("S1 normalized input row count changed")
    rows: list[S1NfciNormalizedRow] = []
    for index, line in enumerate(raw_lines):
        if not line:
            raise ValueError("S1 normalized dataset contains a blank row")
        try:
            raw_row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError("S1 normalized dataset contains invalid JSON") from error
        row = S1NfciNormalizedRow.model_validate(raw_row)
        row_hash = universe_evidence_hash(row.model_dump(mode="json"))
        if row_hash != expected_row_hashes[index] or row.sequence != index + 1:
            raise ValueError("S1 normalized row lineage changed")
        rows.append(row)
    return tuple(rows)


def build_feature_rows(
    rows: tuple[S1NfciNormalizedRow, ...],
    *,
    source_row_hashes: tuple[str, ...],
) -> tuple[S1NfciFeatureRow, ...]:
    if len(rows) != 281 or len(source_row_hashes) != 281:
        raise ValueError("S1 feature input count changed")
    output: list[S1NfciFeatureRow] = []
    values = tuple(Decimal(row.nfci_value_source_text) for row in rows)
    for index in range(4, len(rows)):
        source = rows[index]
        output.append(
            S1NfciFeatureRow(
                sequence=source.sequence,
                target_id=source.target_id,
                source_vintage_date=source.source_vintage_date,
                selected_observation_date=source.selected_observation_date,
                release_lag_days=source.release_lag_days,
                source_normalized_row_sha256=source_row_hashes[index],
                nfci_level=source.nfci_value_source_text,
                nfci_change_1v=decimal_to_fixed(values[index] - values[index - 1]),
                nfci_change_4v=decimal_to_fixed(values[index] - values[index - 4]),
            )
        )
    if len(output) != 277:
        raise ValueError("S1 feature warmup row count changed")
    return tuple(output)


def serialize_feature_rows(rows: tuple[S1NfciFeatureRow, ...]) -> bytes:
    lines = (
        json.dumps(
            row.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        for row in rows
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def load_lineage() -> tuple[
    S1NfciFeatureProtocol,
    S1NfciFeatureProtocolAudit,
    S1NfciFeatureExecutionAddendum,
    S1NfciFeatureExecutionAudit,
    S1NfciNormalizationResult,
    S1NfciNormalizationResultAudit,
]:
    protocol = S1NfciFeatureProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S1NfciFeatureProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    addendum = S1NfciFeatureExecutionAddendum.model_validate_json(
        EXECUTION_ADDENDUM_PATH.read_text(encoding="utf-8")
    )
    execution_audit = S1NfciFeatureExecutionAudit.model_validate_json(
        EXECUTION_AUDIT_PATH.read_text(encoding="utf-8")
    )
    normalization_result = S1NfciNormalizationResult.model_validate_json(
        NORMALIZATION_RESULT_PATH.read_text(encoding="utf-8")
    )
    normalization_audit = S1NfciNormalizationResultAudit.model_validate_json(
        NORMALIZATION_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        protocol_audit.protocol_file_sha256 != file_sha256(PROTOCOL_PATH)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or addendum.protocol_file_sha256 != file_sha256(PROTOCOL_PATH)
        or addendum.protocol_evidence_hash != protocol.protocol_evidence_hash
        or addendum.protocol_audit_file_sha256 != file_sha256(PROTOCOL_AUDIT_PATH)
        or addendum.protocol_audit_evidence_hash
        != protocol_audit.audit_evidence_hash
        or addendum.runner_contract_hash != runner_contract_hash()
        or execution_audit.addendum_file_sha256
        != file_sha256(EXECUTION_ADDENDUM_PATH)
        or execution_audit.addendum_evidence_hash != addendum.addendum_evidence_hash
        or execution_audit.runner_contract_hash != addendum.runner_contract_hash
        or addendum.normalization_result_evidence_hash
        != normalization_result.result_evidence_hash
        or addendum.normalization_audit_evidence_hash
        != normalization_audit.audit_evidence_hash
        or normalization_audit.result_file_sha256
        != file_sha256(NORMALIZATION_RESULT_PATH)
        or normalization_audit.result_evidence_hash
        != normalization_result.result_evidence_hash
        or file_sha256(NORMALIZED_DATASET_PATH)
        != normalization_result.dataset_file_sha256
    ):
        raise ValueError("S1 NFCI feature lineage changed")
    return (
        protocol,
        protocol_audit,
        addendum,
        execution_audit,
        normalization_result,
        normalization_audit,
    )


def build_result(
    *,
    completed_at: datetime,
    feature_rows: tuple[S1NfciFeatureRow, ...],
    feature_dataset: bytes,
    protocol: S1NfciFeatureProtocol,
    protocol_audit: S1NfciFeatureProtocolAudit,
    addendum: S1NfciFeatureExecutionAddendum,
    normalization_result: S1NfciNormalizationResult,
    normalization_audit: S1NfciNormalizationResultAudit,
) -> S1NfciFeatureResult:
    row_hashes = tuple(
        universe_evidence_hash(row.model_dump(mode="json")) for row in feature_rows
    )
    gates = tuple(
        S1SourceGate(
            gate_id=gate_id,
            status="PASS",
            reason="Feature evidence satisfies the frozen macro-only condition.",
        )
        for gate_id in S1_NFCI_FEATURE_GATES
    )
    payload = {
        "completed_at": completed_at,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
        "execution_addendum_file_sha256": file_sha256(EXECUTION_ADDENDUM_PATH),
        "execution_addendum_evidence_hash": addendum.addendum_evidence_hash,
        "runner_contract_hash": addendum.runner_contract_hash,
        "normalization_result_evidence_hash": normalization_result.result_evidence_hash,
        "normalization_audit_evidence_hash": normalization_audit.audit_evidence_hash,
        "normalized_dataset_file_sha256": normalization_result.dataset_file_sha256,
        "input_row_manifest_evidence_hash": (
            protocol.input_row_manifest_evidence_hash
        ),
        "feature_dataset_file_sha256": sha256(feature_dataset).hexdigest(),
        "feature_dataset_bytes": len(feature_dataset),
        "row_evidence_hashes": row_hashes,
        "gates": gates,
    }
    provisional = S1NfciFeatureResult.model_construct(
        **payload,
        result_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S1NfciFeatureResult.model_validate(complete)


def write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 NFCI feature transaction: {temporary}")
    temporary.write_bytes(payload)
    temporary.replace(path)


def write_result_atomic(path: Path, result: S1NfciFeatureResult) -> None:
    serialized = result.model_dump_json(indent=2) + "\n"
    if S1NfciFeatureResult.model_validate_json(serialized) != result:
        raise ValueError("S1 NFCI feature result did not round-trip")
    write_bytes_atomic(path, serialized.encode("utf-8"))


def execute(*, output_path: Path, result_path: Path, check_only: bool) -> S1NfciFeatureResult:
    (
        protocol,
        protocol_audit,
        addendum,
        _execution_audit,
        normalization_result,
        normalization_audit,
    ) = load_lineage()
    if (
        output_path.as_posix() != protocol.output_path
        or result_path.as_posix() != addendum.result_path
    ):
        raise ValueError("S1 NFCI feature output path changed")
    normalized_bytes = NORMALIZED_DATASET_PATH.read_bytes()
    if sha256(normalized_bytes).hexdigest() != normalization_result.dataset_file_sha256:
        raise ValueError("S1 normalized dataset hash changed")
    normalized_rows = parse_normalized_rows(
        normalized_bytes,
        expected_row_hashes=normalization_result.row_evidence_hashes,
    )
    feature_rows = build_feature_rows(
        normalized_rows,
        source_row_hashes=normalization_result.row_evidence_hashes,
    )
    feature_dataset = serialize_feature_rows(feature_rows)
    if output_path.exists():
        if output_path.read_bytes() != feature_dataset:
            raise ValueError("Stored S1 NFCI feature dataset differs")
    elif check_only:
        raise ValueError("S1 NFCI feature dataset does not exist")
    else:
        write_bytes_atomic(output_path, feature_dataset)

    if result_path.exists():
        stored = S1NfciFeatureResult.model_validate_json(
            result_path.read_text(encoding="utf-8")
        )
        expected = build_result(
            completed_at=stored.completed_at,
            feature_rows=feature_rows,
            feature_dataset=feature_dataset,
            protocol=protocol,
            protocol_audit=protocol_audit,
            addendum=addendum,
            normalization_result=normalization_result,
            normalization_audit=normalization_audit,
        )
        if stored != expected:
            raise ValueError("Stored S1 NFCI feature result differs")
        return stored
    if check_only:
        raise ValueError("S1 NFCI feature result does not exist")
    result = build_result(
        completed_at=datetime.now(UTC),
        feature_rows=feature_rows,
        feature_dataset=feature_dataset,
        protocol=protocol,
        protocol_audit=protocol_audit,
        addendum=addendum,
        normalization_result=normalization_result,
        normalization_audit=normalization_audit,
    )
    write_result_atomic(result_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or check S1 NFCI features.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = execute(
        output_path=args.output,
        result_path=args.result,
        check_only=args.check,
    )
    print(
        f"PASS {result.result_evidence_hash} rows={result.feature_row_count} "
        f"dataset_bytes={result.feature_dataset_bytes} btc_values=0 returns=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
