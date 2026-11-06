from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_successor_distribution_protocol import (  # noqa: E402
    JamSuccessorDevelopmentDistributionProtocol,
)
from aurex.backtest_engine.jam_successor_distribution_result import (  # noqa: E402
    JamSuccessorDevelopmentDistributionAudit,
    JamSuccessorDevelopmentDistributionResult,
    audit_jam_successor_distribution_audit,
    audit_jam_successor_distribution_result,
    build_jam_successor_distribution_audit,
)
from scripts.freeze_jam_successor_distribution_protocol import (  # noqa: E402
    DEFAULT_FEATURE_AUDIT,
    DEFAULT_FEATURE_PROTOCOL,
    DEFAULT_FEATURE_SPECIFICATION,
    DEFAULT_FULL_AUDIT,
    DEFAULT_FULL_PROTOCOL,
    DEFAULT_FULL_RESULT,
    DEFAULT_QUALITY_RESULT,
    file_sha256,
)
from scripts.run_jam_successor_development_distribution import (  # noqa: E402
    DEFAULT_EVIDENCE_ROOT,
    DEFAULT_FEATURE_ROWS,
    DEFAULT_OUTPUT,
    DEFAULT_PROTOCOL,
    run_distribution,
)

DEFAULT_AUDIT_OUTPUT = Path("data/evidence/jam_successor_development_distribution_audit_v1.json")
DEFAULT_TEMP_ROOT = Path(".tmp/jam_successor_development_distribution_independent_audit")


def _validated_temp_root(path: Path) -> Path:
    resolved = path.resolve()
    allowed = (PROJECT_ROOT / ".tmp").resolve()
    if not resolved.is_relative_to(allowed):
        raise ValueError("Jam distribution audit temp root must remain under .tmp")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)
    return resolved


def _write_audit(
    path: Path,
    audit: JamSuccessorDevelopmentDistributionAudit,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if JamSuccessorDevelopmentDistributionAudit.model_validate_json(serialized) != audit:
        raise ValueError("Jam distribution audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional audit exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_audit(args) -> JamSuccessorDevelopmentDistributionAudit:
    if args.output.exists():
        raise ValueError(f"Jam distribution audit already exists: {args.output}")
    protocol = JamSuccessorDevelopmentDistributionProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    result = JamSuccessorDevelopmentDistributionResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_successor_distribution_result(result)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or not args.feature_rows.is_file()
        or file_sha256(args.feature_rows) != result.feature_rows_file_sha256
    ):
        raise ValueError("Jam canonical distribution evidence changed")
    audit_root = _validated_temp_root(args.temp_root)
    reconstructed_feature_rows = audit_root / "feature_rows.parquet"
    reconstructed_result_path = audit_root / "result.json"
    runner_temp = audit_root / "runner"
    generated_at = (
        result.generated_at.astimezone(UTC)
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )
    runner_args = SimpleNamespace(
        protocol=args.protocol,
        feature_protocol=args.feature_protocol,
        feature_specification=args.feature_specification,
        feature_audit=args.feature_audit,
        full_protocol=args.full_protocol,
        full_result=args.full_result,
        full_audit=args.full_audit,
        quality_result=args.quality_result,
        evidence_root=args.evidence_root,
        feature_rows=reconstructed_feature_rows,
        output=reconstructed_result_path,
        temp_root=runner_temp,
        generated_at=generated_at,
    )
    try:
        reconstructed = run_distribution(runner_args)
        reconstructed_result_file_hash = file_sha256(reconstructed_result_path)
        canonical_result_file_hash = file_sha256(args.result)
        if (
            reconstructed != result
            or reconstructed.result_evidence_hash != result.result_evidence_hash
            or reconstructed_result_file_hash != canonical_result_file_hash
            or file_sha256(reconstructed_feature_rows) != result.feature_rows_file_sha256
            or reconstructed.feature_rows_schema_hash != result.feature_rows_schema_hash
        ):
            raise ValueError("Jam independent distribution reconstruction changed")
        audit = build_jam_successor_distribution_audit(
            audited_at=datetime.now(UTC),
            protocol_path=args.protocol.as_posix(),
            protocol_file_sha256=file_sha256(args.protocol),
            protocol_evidence_hash=protocol.protocol_evidence_hash,
            result_path=args.result.as_posix(),
            result_file_sha256=canonical_result_file_hash,
            result_evidence_hash=result.result_evidence_hash,
            feature_rows_path=args.feature_rows.as_posix(),
            feature_rows_file_sha256=result.feature_rows_file_sha256,
            feature_rows_schema_hash=result.feature_rows_schema_hash,
            decision=result.decision,
        )
        if not audit_jam_successor_distribution_audit(audit):
            raise ValueError("Jam distribution audit failed internal audit")
        _write_audit(args.output, audit)
    finally:
        if audit_root.exists():
            shutil.rmtree(audit_root)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"result={audit.result_evidence_hash} "
        "reconstructed_archives=24 reconstructed_rows=1052640 "
        "validation=False holdout=False returns=False",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Independently reconstruct and audit the frozen 2019-2020 Jam "
            "successor feature-distribution evidence."
        )
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--feature-rows",
        type=Path,
        default=DEFAULT_FEATURE_ROWS,
    )
    parser.add_argument(
        "--feature-protocol",
        type=Path,
        default=DEFAULT_FEATURE_PROTOCOL,
    )
    parser.add_argument(
        "--feature-specification",
        type=Path,
        default=DEFAULT_FEATURE_SPECIFICATION,
    )
    parser.add_argument(
        "--feature-audit",
        type=Path,
        default=DEFAULT_FEATURE_AUDIT,
    )
    parser.add_argument(
        "--full-protocol",
        type=Path,
        default=DEFAULT_FULL_PROTOCOL,
    )
    parser.add_argument(
        "--full-result",
        type=Path,
        default=DEFAULT_FULL_RESULT,
    )
    parser.add_argument(
        "--full-audit",
        type=Path,
        default=DEFAULT_FULL_AUDIT,
    )
    parser.add_argument(
        "--quality-result",
        type=Path,
        default=DEFAULT_QUALITY_RESULT,
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--temp-root", type=Path, default=DEFAULT_TEMP_ROOT)
    return parser.parse_args()


def main() -> int:
    try:
        run_audit(parse_args())
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
