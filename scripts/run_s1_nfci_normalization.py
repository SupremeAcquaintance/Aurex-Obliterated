from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
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
    S1NfciNormalizationProtocolAudit,
)
from aurex.backtest_engine.s1_nfci_normalization_execution import (  # noqa: E402
    S1NfciNormalizationExecutionAddendum,
    S1NfciNormalizationExecutionAudit,
    S1NfciNormalizationResult,
    S1NfciNormalizedRow,
)
from aurex.backtest_engine.s1_source_feasibility import S1SourceGate  # noqa: E402
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402

PROTOCOL_PATH = Path("data/evidence/s1_nfci_normalization_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s1_nfci_normalization_protocol_audit_v1.json"
)
EXECUTION_ADDENDUM_PATH = Path(
    "data/evidence/s1_nfci_normalization_execution_addendum_v1.json"
)
EXECUTION_AUDIT_PATH = Path(
    "data/evidence/s1_nfci_normalization_execution_audit_v1.json"
)
ACQUISITION_RESULT_PATH = Path(
    "data/evidence/s1_nfci_full_acquisition_result_v1.json"
)
ACQUISITION_AUDIT_PATH = Path(
    "data/evidence/s1_nfci_full_acquisition_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/datasets/s1_nfci_development_normalized_v1.jsonl"
)
DEFAULT_RESULT = Path("data/evidence/s1_nfci_normalization_result_v1.json")
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s1_nfci_normalization_execution.py"
)
RUNNER_PATH = Path("scripts/run_s1_nfci_normalization.py")


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "module_path": MODULE_PATH.as_posix(),
            "module_sha256": file_sha256(PROJECT_ROOT / MODULE_PATH),
            "runner_path": RUNNER_PATH.as_posix(),
            "runner_sha256": file_sha256(PROJECT_ROOT / RUNNER_PATH),
        }
    )


def select_latest_nfci(
    csv_text: str,
    *,
    expected_value_column: str,
    vintage_date: date,
) -> tuple[date, str, int]:
    reader = csv.reader(io.StringIO(csv_text, newline=""))
    try:
        header = tuple(next(reader))
    except StopIteration as error:
        raise ValueError("NFCI source CSV is empty") from error
    expected_header = ("observation_date", expected_value_column)
    if header != expected_header:
        raise ValueError(f"NFCI source header changed: {header!r}")

    previous_date: date | None = None
    selected_date: date | None = None
    selected_value: str | None = None
    row_count = 0
    for raw_row in reader:
        if len(raw_row) != 2:
            raise ValueError("NFCI source row width changed")
        observation_text, value_text = raw_row
        try:
            observation_date = date.fromisoformat(observation_text)
        except ValueError as error:
            raise ValueError("NFCI observation date is invalid") from error
        if previous_date is not None and observation_date <= previous_date:
            raise ValueError("NFCI observation dates are not strictly increasing")
        if observation_date > vintage_date:
            raise ValueError("NFCI source contains a post-vintage observation")
        if value_text != value_text.strip():
            raise ValueError("NFCI value has surrounding whitespace")
        try:
            parsed = Decimal(value_text)
        except InvalidOperation as error:
            raise ValueError("NFCI value is not a decimal") from error
        if not parsed.is_finite():
            raise ValueError("NFCI value is not finite")
        previous_date = observation_date
        selected_date = observation_date
        selected_value = value_text
        row_count += 1

    if selected_date is None or selected_value is None:
        raise ValueError("NFCI source contains no observation rows")
    return selected_date, selected_value, row_count


def serialize_rows(rows: tuple[S1NfciNormalizedRow, ...]) -> bytes:
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
    S1NfciNormalizationProtocol,
    S1NfciNormalizationProtocolAudit,
    S1NfciNormalizationExecutionAddendum,
    S1NfciNormalizationExecutionAudit,
    S1NfciFullAcquisitionResult,
    S1NfciFullAcquisitionAudit,
]:
    protocol = S1NfciNormalizationProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S1NfciNormalizationProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    addendum = S1NfciNormalizationExecutionAddendum.model_validate_json(
        EXECUTION_ADDENDUM_PATH.read_text(encoding="utf-8")
    )
    execution_audit = S1NfciNormalizationExecutionAudit.model_validate_json(
        EXECUTION_AUDIT_PATH.read_text(encoding="utf-8")
    )
    acquisition_result = S1NfciFullAcquisitionResult.model_validate_json(
        ACQUISITION_RESULT_PATH.read_text(encoding="utf-8")
    )
    acquisition_audit = S1NfciFullAcquisitionAudit.model_validate_json(
        ACQUISITION_AUDIT_PATH.read_text(encoding="utf-8")
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
        or addendum.acquisition_result_evidence_hash
        != acquisition_result.result_evidence_hash
        or addendum.acquisition_audit_evidence_hash
        != acquisition_audit.audit_evidence_hash
        or acquisition_audit.result_file_sha256
        != file_sha256(ACQUISITION_RESULT_PATH)
        or acquisition_audit.result_evidence_hash
        != acquisition_result.result_evidence_hash
    ):
        raise ValueError("S1 NFCI normalization lineage changed")
    return (
        protocol,
        protocol_audit,
        addendum,
        execution_audit,
        acquisition_result,
        acquisition_audit,
    )


def build_rows(
    acquisition_result: S1NfciFullAcquisitionResult,
    acquisition_audit: S1NfciFullAcquisitionAudit,
) -> tuple[tuple[S1NfciNormalizedRow, ...], int, tuple[dict[str, object], ...]]:
    rows: list[S1NfciNormalizedRow] = []
    raw_manifest: list[dict[str, object]] = []
    aggregate_raw_bytes = 0
    targets = tuple(sorted(acquisition_result.target_evidence, key=lambda item: item.sequence))
    if tuple(target.sequence for target in targets) != tuple(range(1, 282)):
        raise ValueError("S1 NFCI normalization target sequence changed")

    for target in targets:
        if (
            target.outcome != "COMPLETE"
            or target.raw_path is None
            or target.raw_file_sha256 is None
            or target.summary is None
        ):
            raise ValueError(f"Incomplete S1 NFCI target: {target.target_id}")
        raw_path = Path(target.raw_path)
        raw_bytes = raw_path.read_bytes()
        raw_hash = sha256(raw_bytes).hexdigest()
        if (
            raw_hash != target.raw_file_sha256
            or acquisition_audit.raw_file_sha256.get(target.target_id) != raw_hash
            or len(raw_bytes) != target.raw_file_bytes
        ):
            raise ValueError(f"S1 NFCI raw identity changed: {target.target_id}")
        expected_column = f"NFCI_{target.vintage_date:%Y%m%d}"
        if target.summary.csv_header != ("observation_date", expected_column):
            raise ValueError(f"S1 NFCI summary header changed: {target.target_id}")
        try:
            csv_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"S1 NFCI source is not UTF-8: {target.target_id}") from error
        selected_date, selected_value, row_count = select_latest_nfci(
            csv_text,
            expected_value_column=expected_column,
            vintage_date=target.vintage_date,
        )
        release_lag_days = (target.vintage_date - selected_date).days
        if (
            row_count != target.summary.row_count
            or selected_date != target.summary.last_observation_date
            or release_lag_days != target.summary.release_lag_days
            or not 0 <= release_lag_days <= 21
        ):
            raise ValueError(f"S1 NFCI selected row changed: {target.target_id}")
        rows.append(
            S1NfciNormalizedRow(
                sequence=target.sequence,
                target_id=target.target_id,
                source_vintage_date=target.vintage_date,
                selected_observation_date=selected_date,
                release_lag_days=release_lag_days,
                nfci_value_source_text=selected_value,
                source_raw_path=target.raw_path,
                source_raw_sha256=raw_hash,
            )
        )
        raw_manifest.append(
            {
                "sequence": target.sequence,
                "target_id": target.target_id,
                "raw_path": target.raw_path,
                "raw_file_sha256": raw_hash,
                "raw_file_bytes": len(raw_bytes),
            }
        )
        aggregate_raw_bytes += len(raw_bytes)
    return tuple(rows), aggregate_raw_bytes, tuple(raw_manifest)


def build_result(
    *,
    completed_at: datetime,
    rows: tuple[S1NfciNormalizedRow, ...],
    dataset_bytes: bytes,
    aggregate_raw_bytes: int,
    protocol: S1NfciNormalizationProtocol,
    protocol_audit: S1NfciNormalizationProtocolAudit,
    addendum: S1NfciNormalizationExecutionAddendum,
    acquisition_result: S1NfciFullAcquisitionResult,
    acquisition_audit: S1NfciFullAcquisitionAudit,
) -> S1NfciNormalizationResult:
    row_hashes = tuple(
        universe_evidence_hash(row.model_dump(mode="json")) for row in rows
    )
    gates = tuple(
        S1SourceGate(
            gate_id=gate_id,
            status="PASS",
            reason="Normalized evidence satisfies the frozen causal condition.",
        )
        for gate_id in S1_NFCI_NORMALIZATION_GATES
    )
    payload = {
        "completed_at": completed_at,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
        "execution_addendum_file_sha256": file_sha256(EXECUTION_ADDENDUM_PATH),
        "execution_addendum_evidence_hash": addendum.addendum_evidence_hash,
        "runner_contract_hash": addendum.runner_contract_hash,
        "acquisition_result_evidence_hash": acquisition_result.result_evidence_hash,
        "acquisition_audit_evidence_hash": acquisition_audit.audit_evidence_hash,
        "input_manifest_evidence_hash": protocol.input_manifest_evidence_hash,
        "dataset_file_sha256": sha256(dataset_bytes).hexdigest(),
        "dataset_bytes": len(dataset_bytes),
        "row_evidence_hashes": row_hashes,
        "minimum_release_lag_days": min(row.release_lag_days for row in rows),
        "maximum_release_lag_days": max(row.release_lag_days for row in rows),
        "aggregate_raw_bytes_rehashed": aggregate_raw_bytes,
        "gates": gates,
    }
    provisional = S1NfciNormalizationResult.model_construct(
        **payload,
        result_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return S1NfciNormalizationResult.model_validate(complete)


def write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 NFCI normalization transaction: {temporary}")
    temporary.write_bytes(payload)
    temporary.replace(path)


def write_result_atomic(path: Path, result: S1NfciNormalizationResult) -> None:
    serialized = result.model_dump_json(indent=2) + "\n"
    if S1NfciNormalizationResult.model_validate_json(serialized) != result:
        raise ValueError("S1 NFCI normalization result did not round-trip")
    write_bytes_atomic(path, serialized.encode("utf-8"))


def execute(*, output_path: Path, result_path: Path, check_only: bool) -> S1NfciNormalizationResult:
    (
        protocol,
        protocol_audit,
        addendum,
        _execution_audit,
        acquisition_result,
        acquisition_audit,
    ) = load_lineage()
    if (
        output_path.as_posix() != protocol.output_path
        or result_path.as_posix() != addendum.result_path
    ):
        raise ValueError("S1 NFCI normalization output path changed")
    rows, aggregate_raw_bytes, _raw_manifest = build_rows(
        acquisition_result,
        acquisition_audit,
    )
    dataset_bytes = serialize_rows(rows)
    if output_path.exists():
        if output_path.read_bytes() != dataset_bytes:
            raise ValueError("Stored S1 NFCI normalized dataset differs")
    elif check_only:
        raise ValueError("S1 NFCI normalized dataset does not exist")
    else:
        write_bytes_atomic(output_path, dataset_bytes)

    if result_path.exists():
        stored = S1NfciNormalizationResult.model_validate_json(
            result_path.read_text(encoding="utf-8")
        )
        expected = build_result(
            completed_at=stored.completed_at,
            rows=rows,
            dataset_bytes=dataset_bytes,
            aggregate_raw_bytes=aggregate_raw_bytes,
            protocol=protocol,
            protocol_audit=protocol_audit,
            addendum=addendum,
            acquisition_result=acquisition_result,
            acquisition_audit=acquisition_audit,
        )
        if stored != expected:
            raise ValueError("Stored S1 NFCI normalization result differs")
        return stored
    if check_only:
        raise ValueError("S1 NFCI normalization result does not exist")
    result = build_result(
        completed_at=datetime.now(UTC),
        rows=rows,
        dataset_bytes=dataset_bytes,
        aggregate_raw_bytes=aggregate_raw_bytes,
        protocol=protocol,
        protocol_audit=protocol_audit,
        addendum=addendum,
        acquisition_result=acquisition_result,
        acquisition_audit=acquisition_audit,
    )
    write_result_atomic(result_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or check S1 NFCI normalization.")
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
        f"PASS {result.result_evidence_hash} rows={result.row_count} "
        f"dataset_bytes={result.dataset_bytes} btc_values=0 returns=0 orders=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
