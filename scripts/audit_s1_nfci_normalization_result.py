from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_normalization_execution import (  # noqa: E402
    S1NfciNormalizationResult,
    S1NfciNormalizationResultAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402
from scripts.run_s1_nfci_normalization import (  # noqa: E402
    DEFAULT_OUTPUT,
    DEFAULT_RESULT,
    build_result,
    build_rows,
    load_lineage,
    runner_contract_hash,
    serialize_rows,
)

DEFAULT_AUDIT = Path("data/evidence/s1_nfci_normalization_result_audit_v1.json")
AUDITOR_PATH = Path("scripts/audit_s1_nfci_normalization_result.py")


def build_audit(
    *,
    result_path: Path,
    dataset_path: Path,
    audited_at: datetime,
) -> S1NfciNormalizationResultAudit:
    stored = S1NfciNormalizationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    (
        protocol,
        protocol_audit,
        addendum,
        _execution_audit,
        acquisition_result,
        acquisition_audit,
    ) = load_lineage()
    rows, aggregate_raw_bytes, raw_manifest = build_rows(
        acquisition_result,
        acquisition_audit,
    )
    reconstructed_dataset = serialize_rows(rows)
    if dataset_path.read_bytes() != reconstructed_dataset:
        raise ValueError("S1 NFCI normalized dataset differs from reconstruction")
    expected = build_result(
        completed_at=stored.completed_at,
        rows=rows,
        dataset_bytes=reconstructed_dataset,
        aggregate_raw_bytes=aggregate_raw_bytes,
        protocol=protocol,
        protocol_audit=protocol_audit,
        addendum=addendum,
        acquisition_result=acquisition_result,
        acquisition_audit=acquisition_audit,
    )
    if stored != expected or stored.runner_contract_hash != runner_contract_hash():
        raise ValueError("S1 NFCI normalization result differs from reconstruction")
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": stored.result_evidence_hash,
        "dataset_file_sha256": sha256(reconstructed_dataset).hexdigest(),
        "runner_contract_hash": stored.runner_contract_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
        "raw_manifest_evidence_hash": universe_evidence_hash(raw_manifest),
        "aggregate_raw_bytes": aggregate_raw_bytes,
        "row_manifest_evidence_hash": universe_evidence_hash(
            tuple(row.model_dump(mode="json") for row in rows)
        ),
    }
    provisional = S1NfciNormalizationResultAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S1NfciNormalizationResultAudit.model_validate(complete)


def write_atomic(path: Path, audit: S1NfciNormalizationResultAudit) -> None:
    if path.exists():
        raise ValueError(f"S1 normalization result audit exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 normalization result audit: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S1NfciNormalizationResultAudit.model_validate_json(serialized) != audit:
        raise ValueError("S1 normalization result audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S1 normalization result.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--audit", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1NfciNormalizationResultAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(
            result_path=args.result,
            dataset_path=args.dataset,
            audited_at=stored.audited_at,
        )
        if stored != expected:
            raise SystemExit("Stored S1 normalization result audit differs")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    audit = build_audit(
        result_path=args.result,
        dataset_path=args.dataset,
        audited_at=datetime.now(UTC),
    )
    write_atomic(args.output, audit)
    print(f"AUDITED {args.output} {audit.audit_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
