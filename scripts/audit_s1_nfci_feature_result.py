from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_feature_execution import (  # noqa: E402
    S1NfciFeatureResult,
    S1NfciFeatureResultAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402
from scripts.run_s1_nfci_features import (  # noqa: E402
    DEFAULT_OUTPUT,
    DEFAULT_RESULT,
    NORMALIZED_DATASET_PATH,
    build_feature_rows,
    build_result,
    load_lineage,
    parse_normalized_rows,
    runner_contract_hash,
    serialize_feature_rows,
)

DEFAULT_AUDIT = Path("data/evidence/s1_nfci_feature_result_audit_v1.json")
AUDITOR_PATH = Path("scripts/audit_s1_nfci_feature_result.py")


def build_audit(
    *,
    result_path: Path,
    feature_dataset_path: Path,
    audited_at: datetime,
) -> S1NfciFeatureResultAudit:
    stored = S1NfciFeatureResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    (
        protocol,
        protocol_audit,
        addendum,
        _execution_audit,
        normalization_result,
        normalization_audit,
    ) = load_lineage()
    normalized_bytes = NORMALIZED_DATASET_PATH.read_bytes()
    normalized_rows = parse_normalized_rows(
        normalized_bytes,
        expected_row_hashes=normalization_result.row_evidence_hashes,
    )
    feature_rows = build_feature_rows(
        normalized_rows,
        source_row_hashes=normalization_result.row_evidence_hashes,
    )
    reconstructed_dataset = serialize_feature_rows(feature_rows)
    if feature_dataset_path.read_bytes() != reconstructed_dataset:
        raise ValueError("S1 NFCI feature dataset differs from reconstruction")
    expected = build_result(
        completed_at=stored.completed_at,
        feature_rows=feature_rows,
        feature_dataset=reconstructed_dataset,
        protocol=protocol,
        protocol_audit=protocol_audit,
        addendum=addendum,
        normalization_result=normalization_result,
        normalization_audit=normalization_audit,
    )
    if stored != expected or stored.runner_contract_hash != runner_contract_hash():
        raise ValueError("S1 NFCI feature result differs from reconstruction")
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": stored.result_evidence_hash,
        "feature_dataset_file_sha256": sha256(reconstructed_dataset).hexdigest(),
        "runner_contract_hash": stored.runner_contract_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
        "input_row_manifest_evidence_hash": universe_evidence_hash(
            normalization_result.row_evidence_hashes
        ),
        "feature_row_manifest_evidence_hash": universe_evidence_hash(
            tuple(row.model_dump(mode="json") for row in feature_rows)
        ),
    }
    provisional = S1NfciFeatureResultAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S1NfciFeatureResultAudit.model_validate(complete)


def write_atomic(path: Path, audit: S1NfciFeatureResultAudit) -> None:
    if path.exists():
        raise ValueError(f"S1 feature result audit exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 feature result audit: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S1NfciFeatureResultAudit.model_validate_json(serialized) != audit:
        raise ValueError("S1 feature result audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S1 NFCI feature result.")
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
        stored = S1NfciFeatureResultAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(
            result_path=args.result,
            feature_dataset_path=args.dataset,
            audited_at=stored.audited_at,
        )
        if stored != expected:
            raise SystemExit("Stored S1 feature result audit differs")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    audit = build_audit(
        result_path=args.result,
        feature_dataset_path=args.dataset,
        audited_at=datetime.now(UTC),
    )
    write_atomic(args.output, audit)
    print(f"AUDITED {args.output} {audit.audit_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
