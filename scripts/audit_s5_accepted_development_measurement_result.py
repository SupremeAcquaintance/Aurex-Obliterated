from __future__ import annotations

import argparse
import configparser
import json
import sys
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_accepted_development_measurement_execution import (  # noqa: E402
    S5_MEASUREMENT_PASS,
    S5_MEASUREMENT_RESULT_NEXT,
    S5AcceptedDevelopmentMeasurementExecutionContractAuditV1,
    S5AcceptedDevelopmentMeasurementExecutionContractV1,
    S5AcceptedDevelopmentMeasurementResultV1,
    S5AcceptedDevelopmentMonthlyMeasurementRow,
)
from aurex.backtest_engine.s5_accepted_development_measurement_protocol import (  # noqa: E402
    S5AcceptedDevelopmentMeasurementProtocolAuditV1,
    S5AcceptedDevelopmentMeasurementProtocolV1,
)
from aurex.backtest_engine.s5_accepted_development_measurement_result_audit import (  # noqa: E402
    S5AcceptedDevelopmentMeasurementResultAuditV1,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/s5_accepted_development_measurement_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_accepted_development_measurement_protocol_audit_v1.json"
)
DEFAULT_CONTRACT = Path(
    "data/evidence/s5_accepted_development_measurement_execution_contract_v1.json"
)
DEFAULT_CONTRACT_AUDIT = Path(
    "data/evidence/s5_accepted_development_measurement_execution_contract_audit_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/s5_accepted_development_measurement_result_v1.json"
)
DEFAULT_OUTPUT_ROWS = Path(
    "data/evidence/s5_accepted_development_monthly_measurements_v1.jsonl"
)
DEFAULT_AUDIT = Path(
    "data/evidence/s5_accepted_development_measurement_result_audit_v1.json"
)
REPOSITORY_CONFIG = Path(
    "data/evidence/s5_bitcoin_core_history_payload_v1.git/config"
)
REPOSITORY_PACKED_REFS = Path(
    "data/evidence/s5_bitcoin_core_history_payload_v1.git/packed-refs"
)
AUDIT_MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_accepted_development_measurement_result_audit.py"
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build_hashed[ModelT: BaseModel](
    model: type[ModelT],
    hash_field: str,
    values: dict,
) -> ModelT:
    payload = dict(values)
    payload[hash_field] = "0" * 64
    preliminary = model.model_construct(**payload)
    payload[hash_field] = universe_evidence_hash(
        preliminary.model_dump(mode="json", exclude={hash_field})
    )
    return model.model_validate(payload)


def auditor_contract_bindings() -> tuple[S5HistoryBinding, ...]:
    paths = tuple(
        sorted(
            (
                AUDIT_MODULE_PATH,
                Path(__file__).resolve().relative_to(PROJECT_ROOT),
            ),
            key=lambda path: path.as_posix(),
        )
    )
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in paths
    )


def load_rows(path: Path) -> tuple[S5AcceptedDevelopmentMonthlyMeasurementRow, ...]:
    rows: list[S5AcceptedDevelopmentMonthlyMeasurementRow] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for sequence, line in enumerate(handle, start=1):
            if not line.endswith("\n") or line.endswith("\r\n") or not line.strip():
                raise ValueError("S5 measurement output JSONL framing changed")
            row = S5AcceptedDevelopmentMonthlyMeasurementRow.model_validate(
                json.loads(line)
            )
            if row.sequence != sequence:
                raise ValueError("S5 measurement output sequence changed")
            rows.append(row)
    return tuple(rows)


def verify_month_grid(
    rows: tuple[S5AcceptedDevelopmentMonthlyMeasurementRow, ...],
) -> None:
    if len(rows) != 212 or rows[0].month_start != date(2009, 1, 1):
        raise ValueError("S5 measurement month grid start changed")
    if rows[-1].month_start != date(2026, 8, 1):
        raise ValueError("S5 measurement month grid end changed")
    if any(
        previous.month_end_exclusive != current.month_start
        for previous, current in zip(rows, rows[1:], strict=False)
    ):
        raise ValueError("S5 measurement month grid is not contiguous")


def repository_ref_state() -> tuple[bool, int, int, bool]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    with (PROJECT_ROOT / REPOSITORY_CONFIG).open("r", encoding="utf-8") as handle:
        parser.read_file(handle)
    no_tags = parser.get('remote "origin"', "tagOpt", fallback="") == "--no-tags"
    refs: list[str] = []
    for line in (PROJECT_ROOT / REPOSITORY_PACKED_REFS).read_text(
        encoding="utf-8"
    ).splitlines():
        if not line or line.startswith("#") or line.startswith("^"):
            continue
        parts = line.split(" ", maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 40:
            raise ValueError("S5 packed refs framing changed")
        refs.append(parts[1])
    tag_count = sum(ref.startswith("refs/tags/") for ref in refs)
    branch_refs = tuple(ref for ref in refs if ref.startswith("refs/heads/"))
    return no_tags, tag_count, len(branch_refs), branch_refs == ("refs/heads/master",)


def build_audit(
    *,
    result_path: Path,
    output_rows_path: Path,
    audited_at: datetime,
) -> S5AcceptedDevelopmentMeasurementResultAuditV1:
    protocol = S5AcceptedDevelopmentMeasurementProtocolV1.model_validate_json(
        (PROJECT_ROOT / DEFAULT_PROTOCOL).read_text(encoding="utf-8")
    )
    protocol_audit = S5AcceptedDevelopmentMeasurementProtocolAuditV1.model_validate_json(
        (PROJECT_ROOT / DEFAULT_PROTOCOL_AUDIT).read_text(encoding="utf-8")
    )
    contract = S5AcceptedDevelopmentMeasurementExecutionContractV1.model_validate_json(
        (PROJECT_ROOT / DEFAULT_CONTRACT).read_text(encoding="utf-8")
    )
    contract_audit = (
        S5AcceptedDevelopmentMeasurementExecutionContractAuditV1.model_validate_json(
            (PROJECT_ROOT / DEFAULT_CONTRACT_AUDIT).read_text(encoding="utf-8")
        )
    )
    result = S5AcceptedDevelopmentMeasurementResultV1.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    rows = load_rows(output_rows_path)
    verify_month_grid(rows)
    output_file_hash = file_sha256(output_rows_path)
    output_manifest_hash = universe_evidence_hash(
        tuple(row.model_dump(mode="json") for row in rows)
    )
    if (
        protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.execution_contract_evidence_hash != contract.contract_evidence_hash
        or result.execution_contract_audit_evidence_hash != contract_audit.audit_evidence_hash
        or result.decision != S5_MEASUREMENT_PASS
        or result.next_authorization != S5_MEASUREMENT_RESULT_NEXT
        or result.output_path != output_rows_path.as_posix()
        or result.output_file_sha256 != output_file_hash
        or result.output_byte_count != output_rows_path.stat().st_size
        or result.output_row_count != len(rows)
        or result.output_row_manifest_evidence_hash != output_manifest_hash
        or any(
            row.source_normalization_result_evidence_hash
            != protocol.corrected_normalization_result_evidence_hash
            for row in rows
        )
    ):
        raise ValueError("S5 measurement result or output lineage changed")
    aggregate_counts = {
        "primary": sum(
            row.primary_source_verified_accepted_pull_count for row in rows
        ),
        "all_accepted": sum(row.all_accepted_pull_count for row in rows),
        "canonical": sum(row.canonical_integration_count for row in rows),
        "unresolved": sum(row.unresolved_git_merge_count for row in rows),
        "stable": sum(row.stable_release_tag_count for row in rows),
        "signed_stable": sum(
            row.signed_annotated_stable_release_tag_count for row in rows
        ),
    }
    if aggregate_counts != {
        "primary": result.primary_events_in_complete_months,
        "all_accepted": result.all_accepted_events_in_complete_months,
        "canonical": result.canonical_events_in_complete_months,
        "unresolved": result.unresolved_merges_in_complete_months,
        "stable": 0,
        "signed_stable": 0,
    }:
        raise ValueError("S5 measurement output aggregate accounting changed")
    no_tags, tag_ref_count, branch_ref_count, master_only = repository_ref_state()
    if (
        result.stable_release_tag_inventory_count != 0
        or not no_tags
        or tag_ref_count != 0
        or branch_ref_count != 1
        or not master_only
    ):
        raise ValueError("S5 release-tag source omission was not reproduced")
    auditor_bindings = auditor_contract_bindings()
    values = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
        "execution_contract_evidence_hash": contract.contract_evidence_hash,
        "execution_contract_audit_evidence_hash": contract_audit.audit_evidence_hash,
        "runner_contract_hash": contract.runner_contract_hash,
        "auditor_implementation_bindings": auditor_bindings,
        "auditor_contract_hash": universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in auditor_bindings)
        ),
        "output_file_sha256": output_file_hash,
        "output_row_manifest_evidence_hash": output_manifest_hash,
        "repository_config_file_sha256": file_sha256(PROJECT_ROOT / REPOSITORY_CONFIG),
        "repository_packed_refs_file_sha256": file_sha256(
            PROJECT_ROOT / REPOSITORY_PACKED_REFS
        ),
        "repository_tag_opt_no_tags_observed": no_tags,
        "packed_tag_ref_count": tag_ref_count,
        "packed_branch_ref_count": branch_ref_count,
        "packed_master_only_observed": master_only,
        "limitations": tuple(
            sorted(
                (
                    "The nominal run PASS is rejected because absent release source became zero.",
                    "The 212 output rows and aggregate counts are internally hash-consistent.",
                    "Nonrelease metrics were not independently reconstructed from 57,592 inputs.",
                    "No BTC market value or return was read during this audit.",
                    "No release tag was available in the frozen no-tags repository.",
                    "Release continuity cannot be interpreted or used as a candidate feature.",
                    "A separate bounded source-remediation protocol is required before replay.",
                    "The original result and output remain immutable evidence of the defect.",
                    "Trading authority and real net profit remain zero.",
                )
            )
        ),
    }
    return build_hashed(
        S5AcceptedDevelopmentMeasurementResultAuditV1,
        "audit_evidence_hash",
        values,
    )


def write_audit(
    path: Path,
    audit: S5AcceptedDevelopmentMeasurementResultAuditV1,
) -> None:
    if path.exists():
        raise ValueError(f"S5 measurement result audit already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5AcceptedDevelopmentMeasurementResultAuditV1.model_validate_json(serialized) != audit:
        raise ValueError("S5 measurement result audit did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the frozen S5 accepted-development measurement result."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = S5AcceptedDevelopmentMeasurementResultAuditV1.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                result_path=args.result,
                output_rows_path=args.rows,
                audited_at=stored.audited_at,
            )
            if stored != expected:
                raise ValueError("Stored S5 measurement result audit changed")
            print(f"PASS {stored.audit_evidence_hash}", flush=True)
            return 0
        audit = build_audit(
            result_path=args.result,
            output_rows_path=args.rows,
            audited_at=datetime.now(UTC),
        )
        write_audit(args.output, audit)
        print(
            f"REJECTED {args.output} {audit.audit_evidence_hash} "
            "release_tags=0 tag_opt=no-tags market_values=0 returns=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
