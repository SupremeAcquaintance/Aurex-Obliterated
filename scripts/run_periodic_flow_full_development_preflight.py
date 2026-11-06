from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_full_development_preflight import (  # noqa: E402
    PeriodicFlowAcquisitionPreflightResult,
    PeriodicFlowReusePreflightEvidence,
    audit_preflight_result,
    build_preflight_result,
)
from aurex.backtest_engine.periodic_flow_full_development_runner import (  # noqa: E402
    source_contract_hash,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_EVIDENCE_ROOT,
    DEFAULT_EXECUTION_CONTRACT,
    DEFAULT_EXECUTION_CONTRACT_AUDIT,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    LoadedContext,
    file_sha256,
    load_context,
    marker_state,
    select_zip_member,
    verify_reuse_archive,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_full_development_preflight_result_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_full_development_preflight.py"
)
SCRIPT_PATH = Path("scripts/run_periodic_flow_full_development_preflight.py")


def builder_contract_hash() -> str:
    return source_contract_hash(PROJECT_ROOT, (MODULE_PATH, SCRIPT_PATH))


def authoritative_reuse_evidence(
    *,
    context: LoadedContext,
    evidence_root: Path,
    emit_progress: bool,
) -> tuple[PeriodicFlowReusePreflightEvidence, ...]:
    targets = [
        target
        for target in context.protocol.targets
        if target.reuse_candidate_path is not None
    ]
    evidence = []
    for index, target in enumerate(targets, start=1):
        path = verify_reuse_archive(evidence_root=evidence_root, target=target)
        with zipfile.ZipFile(path) as archive:
            (
                _,
                compressed_total,
                uncompressed_total,
                _,
                _,
                _,
                _,
            ) = select_zip_member(
                archive,
                target=target,
                protocol=context.protocol,
            )
            member_names = tuple(
                sorted(member.filename for member in archive.infolist() if not member.is_dir())
            )
        evidence.append(
            PeriodicFlowReusePreflightEvidence(
                month=target.month,
                product=target.product,
                family=target.family,
                local_path=path.resolve().relative_to(evidence_root.resolve()).as_posix(),
                archive_bytes=path.stat().st_size,
                archive_sha256=target.published_archive_sha256,
                published_sha256=target.published_archive_sha256,
                zip_member_names=member_names,
                zip_compressed_bytes_total=compressed_total,
                zip_uncompressed_bytes_total=uncompressed_total,
                member_policy=target.member_policy,
            )
        )
        if emit_progress:
            print(
                f"REUSE {index}/37 {target.month} {target.product} PASS",
                flush=True,
            )
    return tuple(evidence)


def authoritative_result(
    *,
    args: argparse.Namespace,
    generated_at: datetime,
    free_disk_bytes: int,
    emit_progress: bool,
) -> PeriodicFlowAcquisitionPreflightResult:
    context = load_context(args)
    state = marker_state(args.acquisition_root)
    if state.request_count or state.response_count or state.payload_bytes_received:
        raise ValueError("Q1 preflight result requires a zero-request acquisition root")
    reuse_evidence = authoritative_reuse_evidence(
        context=context,
        evidence_root=args.evidence_root,
        emit_progress=emit_progress,
    )
    return build_preflight_result(
        generated_at=generated_at,
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        execution_contract_file_sha256=file_sha256(args.execution_contract),
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        runner_source_hash=context.contract.runner_source_hash,
        preflight_builder_contract_hash=builder_contract_hash(),
        reuse_evidence=reuse_evidence,
        reuse_candidate_bytes=sum(item.archive_bytes for item in reuse_evidence),
        free_disk_bytes=free_disk_bytes,
        limitations=(
            "The disk observation is point-in-time and must be repeated before acquisition.",
            "All 37 reuse candidates passed checksum and ZIP-policy preflight only.",
            "Full row-level structural parsing still occurs during the acquisition run.",
            "No missing archive was requested and no payload byte was received.",
            "The 100 GB ceiling is conservative and is not an expected transfer size.",
            "The 20 GB post-acquisition reserve is a hard capital-preservation-style gate.",
            "Prices, quantities, features, parameters, returns, and outcomes remained sealed.",
            "No candidate, Pine, paper, Testnet strategy order, or live authority exists.",
            "The blocked result is operational evidence, not a source-quality failure.",
            "Real net profit remains zero.",
        ),
    )


def write_result(path: Path, result: PeriodicFlowAcquisitionPreflightResult) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 preflight result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 preflight result transaction: {temporary}")
    serialized = result.model_dump_json(indent=2) + "\n"
    if PeriodicFlowAcquisitionPreflightResult.model_validate_json(serialized) != result:
        raise ValueError("Q1 preflight result did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record or check the Q1 acquisition preflight evidence."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument(
        "--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT
    )
    parser.add_argument(
        "--execution-contract-audit",
        type=Path,
        default=DEFAULT_EXECUTION_CONTRACT_AUDIT,
    )
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument(
        "--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowAcquisitionPreflightResult.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_result(
                args=args,
                generated_at=stored.generated_at,
                free_disk_bytes=stored.free_disk_bytes,
                emit_progress=False,
            )
            if stored != expected or not audit_preflight_result(stored):
                raise ValueError("Stored Q1 preflight result changed")
            print(
                f"PASS {args.output} {stored.result_evidence_hash} "
                f"decision={stored.decision} requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        free = shutil.disk_usage(args.acquisition_root.parent.resolve()).free
        result = authoritative_result(
            args=args,
            generated_at=datetime.now(UTC),
            free_disk_bytes=free,
            emit_progress=True,
        )
        write_result(args.output, result)
        print(
            f"WROTE {args.output} {result.result_evidence_hash} "
            f"decision={result.decision} shortfall="
            f"{result.additional_free_disk_bytes_required} requests=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

