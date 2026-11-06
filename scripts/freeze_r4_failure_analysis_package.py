import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_r4_failure_analysis import (
    R4_FAILURE_SOURCE_FILES,
    R4FailureAnalysisPackage,
    audit_r4_failure_analysis_package,
    build_r4_failure_analysis_package,
)
from aurex.backtest_engine.research_r4_failure_protocol import (
    R4FailureAnalysisProtocol,
    audit_r4_failure_analysis_protocol,
)
from aurex.backtest_engine.research_r4_result import (
    R4ValidationResultLedger,
    audit_r4_validation_result_ledger,
)
from aurex.backtest_engine.research_r4_run_package import (
    R4RunPackage,
    audit_r4_run_package,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from aurex.backtest_engine.validation_bundle import ValidationDatasetBundle

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_PROTOCOL = (
    DEFAULT_EVIDENCE_ROOT / "r4_failure_analysis_protocol_v1.json"
)
DEFAULT_VALIDATION_BUNDLE = (
    DEFAULT_EVIDENCE_ROOT / "validation_2025_4h_bundle_v1.json"
)
DEFAULT_RUN_PACKAGE = (
    DEFAULT_EVIDENCE_ROOT / "r4_path_quality_run_package_v1.json"
)
DEFAULT_LEDGER = DEFAULT_EVIDENCE_ROOT / "r4_path_quality_result_v1.json"
DEFAULT_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "r4_failure_analysis_package_v1.json"
)
DEFAULT_RESULT = DEFAULT_EVIDENCE_ROOT / "r4_failure_analysis_result_v1.json"


def source_file_hashes(project_root: Path) -> dict[str, str]:
    return {
        relative_path: hashlib.sha256(
            (project_root / relative_path).read_bytes()
        ).hexdigest()
        for relative_path in R4_FAILURE_SOURCE_FILES
    }


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_r4_failure_analysis_package.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_r4_failure_analysis.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_r4_failure_runner.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def load_analysis_inputs(args):
    protocol = R4FailureAnalysisProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    validation_bundle = ValidationDatasetBundle.model_validate_json(
        args.validation_bundle.read_text(encoding="utf-8")
    )
    run_package = R4RunPackage.model_validate_json(
        args.run_package.read_text(encoding="utf-8")
    )
    ledger = R4ValidationResultLedger.model_validate_json(
        args.ledger.read_text(encoding="utf-8")
    )
    if not audit_r4_failure_analysis_protocol(protocol):
        raise ValueError("R4 failure protocol failed its hash audit")
    if not audit_r4_run_package(run_package):
        raise ValueError("R4 run package failed its hash audit")
    if not audit_r4_validation_result_ledger(ledger):
        raise ValueError("R4 result ledger failed its hash audit")
    if (
        protocol.validation_dataset_bundle_evidence_hash
        != validation_bundle.bundle_evidence_hash
        or protocol.run_package_evidence_hash
        != run_package.package_evidence_hash
        or protocol.result_ledger_evidence_hash != ledger.ledger_evidence_hash
        or ledger.validation_dataset_bundle_evidence_hash
        != validation_bundle.bundle_evidence_hash
        or ledger.run_package_evidence_hash != run_package.package_evidence_hash
    ):
        raise ValueError("R4 failure-analysis package inputs changed lineage")
    receipt_hashes = {
        receipt.run_id: receipt.result_evidence_hash
        for receipt in ledger.replay_receipts
    }
    if receipt_hashes != protocol.replay_result_evidence_hashes:
        raise ValueError("R4 failure protocol no longer matches replay receipts")
    return protocol, validation_bundle, run_package, ledger


def authoritative_package(
    *,
    frozen_at: datetime,
    protocol: R4FailureAnalysisProtocol,
    validation_bundle: ValidationDatasetBundle,
    run_package: R4RunPackage,
    ledger: R4ValidationResultLedger,
) -> R4FailureAnalysisPackage:
    project_root = Path(__file__).resolve().parents[1]
    return build_r4_failure_analysis_package(
        frozen_at=frozen_at,
        failure_protocol_evidence_hash=protocol.protocol_evidence_hash,
        validation_dataset_bundle_evidence_hash=(
            validation_bundle.bundle_evidence_hash
        ),
        run_package_evidence_hash=run_package.package_evidence_hash,
        result_ledger_evidence_hash=ledger.ledger_evidence_hash,
        replay_result_evidence_hashes=protocol.replay_result_evidence_hashes,
        source_file_sha256=source_file_hashes(project_root),
        preexisting_analysis_artifacts=[],
        builder_contract_hash=builder_contract_hash(),
    )


def write_package(path: Path, package: R4FailureAnalysisPackage) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = package.model_dump_json(indent=2) + "\n"
    if R4FailureAnalysisPackage.model_validate_json(serialized) != package:
        raise ValueError("R4 failure-analysis package JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> R4FailureAnalysisPackage:
    if args.output.exists():
        raise ValueError("Frozen R4 failure-analysis package exists; use --check")
    if args.result.exists():
        raise ValueError("R4 failure-analysis result predates package freeze")
    inputs = load_analysis_inputs(args)
    package = authoritative_package(
        frozen_at=datetime.now(UTC),
        protocol=inputs[0],
        validation_bundle=inputs[1],
        run_package=inputs[2],
        ledger=inputs[3],
    )
    write_package(args.output, package)
    stored = R4FailureAnalysisPackage.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if stored != package or not audit_r4_failure_analysis_package(stored):
        raise ValueError("R4 failure-analysis package failed reload verification")
    print(
        f"WROTE {args.output} {stored.package_evidence_hash} "
        f"sources={len(stored.source_file_sha256)}",
        flush=True,
    )
    return stored


def run_check(args) -> R4FailureAnalysisPackage:
    inputs = load_analysis_inputs(args)
    stored = R4FailureAnalysisPackage.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_package(
        frozen_at=stored.frozen_at,
        protocol=inputs[0],
        validation_bundle=inputs[1],
        run_package=inputs[2],
        ledger=inputs[3],
    )
    if stored != expected or not audit_r4_failure_analysis_package(stored):
        raise ValueError("Stored R4 failure package differs from rebuild")
    print(
        "PASS "
        f"r4_failure_package={stored.package_evidence_hash} "
        f"sources={len(stored.source_file_sha256)}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the R4 failure-analysis source package."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--validation-bundle", type=Path, default=DEFAULT_VALIDATION_BUNDLE
    )
    parser.add_argument("--run-package", type=Path, default=DEFAULT_RUN_PACKAGE)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.freeze:
            run_freeze(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
