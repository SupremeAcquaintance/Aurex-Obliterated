from __future__ import annotations

import argparse
import json
import shutil
import socket
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_acquisition import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionProtocol,
    PeriodicFlowSuccessorAcquisitionProtocolAudit,
)
from aurex.backtest_engine.periodic_flow_successor_acquisition import (  # noqa: E402
    audit_hash as audit_protocol_hash,
)
from aurex.backtest_engine.periodic_flow_successor_runner import (  # noqa: E402
    PeriodicFlowExcludedMonthEvidence,
)
from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v4 import (  # noqa: E402
    PeriodicFlowSuccessorTerminalAuditV4,
    audit_successor_terminal_audit_v4,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v4 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV4,
    PeriodicFlowSuccessorCheckpointV4,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v5 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV5,
    PeriodicFlowSuccessorCheckpointV5,
    PeriodicFlowSuccessorExecutionContractAuditV5,
    PeriodicFlowSuccessorExecutionContractV5,
    PeriodicFlowSuccessorTransportAmendmentAuditV5,
    PeriodicFlowSuccessorTransportAmendmentV5,
    audit_hash,
    build_acquisition_result_v5,
    build_checkpoint_v5,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    AcquisitionFailure,
    LoadedContext,
    _write_json_transactional,
    file_sha256,
    inspect_archive,
    pair_month,
    select_zip_member,
    source_contract_hash,
    verify_reuse_archive,
)
from scripts.run_periodic_flow_successor_acquisition import (  # noqa: E402
    result_limitations,
)
from scripts.run_periodic_flow_successor_acquisition_v3 import (  # noqa: E402
    INHERITED_MODULE_PATH,
    INHERITED_SCRIPT_PATH,
    V2_MODULE_PATH,
    V2_SCRIPT_PATH,
    ProtocolTransportAdapterV3,
    ensure_network_archive_v3,
    marker_state_v3,
)
from scripts.run_periodic_flow_successor_acquisition_v4 import (  # noqa: E402
    V3_MODULE_PATH,
    V3_SCRIPT_PATH,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_audit_v1.json"
)
DEFAULT_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v5.json"
)
DEFAULT_AMENDMENT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_audit_v5.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v5.json"
)
DEFAULT_EXECUTION_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v5.json"
)
DEFAULT_V4_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v4.json"
)
DEFAULT_V4_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v4.json"
)
DEFAULT_V4_TERMINAL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v4.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_ACQUISITION_ROOT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_v5"
)
DEFAULT_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v5.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v5.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/periodic_flow_successor_transport_v5.py")
SCRIPT_PATH = Path("scripts/run_periodic_flow_successor_acquisition_v5.py")
V4_MODULE_PATH = Path("src/aurex/backtest_engine/periodic_flow_successor_transport_v4.py")
V4_SCRIPT_PATH = Path("scripts/run_periodic_flow_successor_acquisition_v4.py")


class ProtocolTransportAdapterV5(ProtocolTransportAdapterV3):
    @property
    def bootstrap_target_key(self) -> str:
        return "V5_CHECKPOINT_ONLY_NO_BOOTSTRAP"


def current_runner_source_hash_v5() -> str:
    return source_contract_hash(
        PROJECT_ROOT,
        (
            MODULE_PATH,
            SCRIPT_PATH,
            V4_MODULE_PATH,
            V4_SCRIPT_PATH,
            V3_MODULE_PATH,
            V3_SCRIPT_PATH,
            V2_MODULE_PATH,
            V2_SCRIPT_PATH,
            INHERITED_MODULE_PATH,
            INHERITED_SCRIPT_PATH,
        ),
    )


def load_context(args: argparse.Namespace) -> LoadedContext:
    protocol = PeriodicFlowSuccessorAcquisitionProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = PeriodicFlowSuccessorAcquisitionProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    amendment = PeriodicFlowSuccessorTransportAmendmentV5.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    amendment_audit = PeriodicFlowSuccessorTransportAmendmentAuditV5.model_validate_json(
        args.amendment_audit.read_text(encoding="utf-8")
    )
    contract = PeriodicFlowSuccessorExecutionContractV5.model_validate_json(
        args.execution_contract.read_text(encoding="utf-8")
    )
    contract_audit = PeriodicFlowSuccessorExecutionContractAuditV5.model_validate_json(
        args.execution_contract_audit.read_text(encoding="utf-8")
    )
    runner_hash = current_runner_source_hash_v5()
    if (
        not audit_protocol_hash(protocol, "protocol_evidence_hash")
        or not audit_protocol_hash(protocol_audit, "audit_evidence_hash")
        or not audit_hash(amendment, "amendment_evidence_hash")
        or not audit_hash(amendment_audit, "audit_evidence_hash")
        or not audit_hash(contract, "contract_evidence_hash")
        or not audit_hash(contract_audit, "audit_evidence_hash")
        or protocol_audit.protocol_file_sha256 != file_sha256(args.protocol)
        or amendment.parent_protocol_file_sha256 != file_sha256(args.protocol)
        or amendment.parent_protocol_evidence_hash != protocol.protocol_evidence_hash
        or amendment_audit.amendment_file_sha256 != file_sha256(args.amendment)
        or contract.amendment_file_sha256 != file_sha256(args.amendment)
        or contract.amendment_audit_file_sha256 != file_sha256(args.amendment_audit)
        or contract.runner_source_hash != runner_hash
        or contract_audit.contract_file_sha256 != file_sha256(args.execution_contract)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.runner_source_hash != runner_hash
    ):
        raise ValueError("Q1 successor v5 acquisition authority or source changed")
    return LoadedContext(  # type: ignore[arg-type]
        protocol=ProtocolTransportAdapterV5(protocol, amendment),
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
    )


def _seed(args: argparse.Namespace, context: LoadedContext):
    checkpoint = PeriodicFlowSuccessorCheckpointV4.model_validate_json(
        args.v4_checkpoint.read_text(encoding="utf-8")
    )
    terminal_audit = PeriodicFlowSuccessorTerminalAuditV4.model_validate_json(
        args.v4_terminal_audit.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResultV4.model_validate_json(
        args.v4_result.read_text(encoding="utf-8")
    )
    if (
        file_sha256(args.v4_checkpoint)
        != context.contract.seed_v4_checkpoint_file_sha256
        or checkpoint.checkpoint_evidence_hash
        != context.contract.seed_v4_checkpoint_evidence_hash
        or file_sha256(args.v4_result) != context.contract.seed_v4_result_file_sha256
        or result.result_evidence_hash != context.contract.seed_v4_result_evidence_hash
        or file_sha256(args.v4_terminal_audit)
        != context.contract.seed_v4_terminal_audit_file_sha256
        or terminal_audit.audit_evidence_hash
        != context.contract.seed_v4_terminal_audit_evidence_hash
        or not audit_successor_terminal_audit_v4(terminal_audit)
        or len(checkpoint.archive_evidence) != context.contract.seed_archive_count
        or len(checkpoint.paired_month_evidence)
        != context.contract.seed_paired_month_count
        or len(checkpoint.excluded_month_evidence)
        != context.contract.seed_excluded_month_count
    ):
        raise ValueError("Q1 successor v5 seed lineage changed")
    return checkpoint


def _verify_evidence(evidence_root: Path, evidence) -> Path:
    path = (evidence_root / evidence.local_path).resolve()
    if (
        not path.is_relative_to(evidence_root.resolve())
        or not path.is_file()
        or path.stat().st_size != evidence.archive_bytes
        or file_sha256(path) != evidence.archive_sha256
    ):
        raise ValueError(f"Q1 successor v5 archive changed: {evidence.key}")
    return path


def _build_checkpoint(args, context, archives, pairs, exclusions):
    state = marker_state_v3(args.acquisition_root)
    return build_checkpoint_v5(
        updated_at=datetime.now(UTC),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        runner_source_hash=context.contract.runner_source_hash,
        archive_evidence=tuple(archives),
        paired_month_evidence=tuple(pairs),
        excluded_month_evidence=tuple(exclusions),
        request_marker_count=state.request_count,
        response_marker_count=state.response_count,
        request_marker_manifest_hash=state.manifest_hash,
        cumulative_payload_bytes_received=state.payload_bytes_received,
        total_new_archive_bytes=sum(item.new_archive_bytes for item in archives),
        total_member_uncompressed_bytes=sum(
            item.zip_uncompressed_bytes_total for item in archives
        ),
    )


def load_checkpoint(args, context):
    if not args.checkpoint.exists():
        seed = _seed(args, context)
        return _build_checkpoint(
            args,
            context,
            seed.archive_evidence,
            seed.paired_month_evidence,
            seed.excluded_month_evidence,
        )
    checkpoint = PeriodicFlowSuccessorCheckpointV5.model_validate_json(
        args.checkpoint.read_text(encoding="utf-8")
    )
    state = marker_state_v3(args.acquisition_root)
    if (
        checkpoint.execution_contract_evidence_hash
        != context.contract.contract_evidence_hash
        or checkpoint.runner_source_hash != context.contract.runner_source_hash
        or checkpoint.request_marker_count != state.request_count
        or checkpoint.response_marker_count != state.response_count
        or checkpoint.request_marker_manifest_hash != state.manifest_hash
        or checkpoint.cumulative_payload_bytes_received != state.payload_bytes_received
    ):
        raise ValueError("Q1 successor v5 checkpoint lineage changed")
    return checkpoint


def write_checkpoint(args, context, archives, pairs, exclusions):
    checkpoint = _build_checkpoint(args, context, archives, pairs, exclusions)
    if checkpoint.request_marker_count != checkpoint.response_marker_count:
        raise ValueError("Q1 successor v5 checkpoint refused unmatched markers")
    _write_json_transactional(
        args.checkpoint, checkpoint.model_dump(mode="json"), overwrite=True
    )
    return checkpoint


def _wait_for_dns(context: LoadedContext) -> None:
    last_error = None
    for attempt in range(1, context.protocol.maximum_dns_checks_per_network_target + 1):
        try:
            if socket.getaddrinfo("data.binance.vision", 443):
                return
        except OSError as exc:
            last_error = exc
        if attempt < context.protocol.maximum_dns_checks_per_network_target:
            time.sleep(context.protocol.dns_retry_delays_seconds[attempt - 1])
    raise AcquisitionFailure(f"Q1 successor v5 DNS preflight unresolved: {last_error}")


def preflight(args, context):
    if args.result.exists():
        raise ValueError("A terminal Q1 successor v5 result already exists")
    seed = _seed(args, context)
    for evidence in seed.archive_evidence:
        _verify_evidence(args.evidence_root, evidence)
    reused = [item for item in context.protocol.targets if item.reuse_candidate_path]
    for target in reused:
        path = verify_reuse_archive(evidence_root=args.evidence_root, target=target)
        with zipfile.ZipFile(path) as archive:
            select_zip_member(archive, target=target, protocol=context.protocol)
    _wait_for_dns(context)
    free = shutil.disk_usage(args.acquisition_root.parent.resolve()).free
    result = {
        "status": "PASS"
        if free >= context.contract.required_free_disk_bytes_before_acquisition
        else "BLOCKED_INSUFFICIENT_FREE_DISK",
        "seed_archives_verified": len(seed.archive_evidence),
        "seed_pairs_verified": len(seed.paired_month_evidence),
        "seed_exclusions_verified": len(seed.excluded_month_evidence),
        "free_disk_bytes": free,
        "required_free_disk_bytes": (
            context.contract.required_free_disk_bytes_before_acquisition
        ),
        "network_requests_made": marker_state_v3(args.acquisition_root).request_count,
        "outcomes_accessed": 0,
        "orders_submitted": 0,
    }
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    if result["status"] != "PASS":
        raise AcquisitionFailure("Q1 successor v5 disk requirement failed")
    return result


def _inspect(args, context, target):
    try:
        if target.reuse_candidate_path is not None:
            path = verify_reuse_archive(evidence_root=args.evidence_root, target=target)
            mode, attempts = "REUSED_LOCAL", 0
        else:
            _wait_for_dns(context)
            path, attempts = ensure_network_archive_v3(
                root=args.acquisition_root, target=target, context=context
            )
            mode = "NETWORK_ACQUIRED"
        return inspect_archive(
            target=target,
            archive_path=path,
            evidence_root=args.evidence_root,
            protocol=context.protocol,
            source_mode=mode,
            get_attempt_count=attempts,
        )
    except AcquisitionFailure:
        raise
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise AcquisitionFailure(
            f"Q1 successor v5 archive integrity failed for {target.key}: {exc}"
        ) from exc


def _rebuild(args, context, evidence):
    target = next(item for item in context.protocol.targets if item.key == evidence.key)
    path = _verify_evidence(args.evidence_root, evidence)
    rebuilt = inspect_archive(
        target=target,
        archive_path=path,
        evidence_root=args.evidence_root,
        protocol=context.protocol,
        source_mode=evidence.source_mode,
        get_attempt_count=evidence.payload_get_attempt_count,
    )
    if rebuilt.evidence != evidence:
        raise ValueError(f"Q1 successor v5 seed evidence changed: {evidence.key}")
    return rebuilt


def _counts(pairs):
    years = {str(year): 0 for year in range(2020, 2024)}
    quarters = set()
    for pair in pairs:
        year, month = pair.month.split("-")
        years[year] += 1
        quarters.add((year, (int(month) - 1) // 3 + 1))
    return years, len(quarters)


def write_result(args, context, checkpoint, failed_key=None, failure=None):
    years, quarters = _counts(checkpoint.paired_month_evidence)
    result = build_acquisition_result_v5(
        generated_at=datetime.now(UTC),
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        execution_contract_file_sha256=file_sha256(args.execution_contract),
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        runner_source_hash=context.contract.runner_source_hash,
        checkpoint_file_sha256=file_sha256(args.checkpoint),
        checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        inspected_archive_count=len(checkpoint.archive_evidence),
        qualified_paired_month_count=len(checkpoint.paired_month_evidence),
        excluded_month_count=len(checkpoint.excluded_month_evidence),
        completed_month_count=(
            len(checkpoint.paired_month_evidence)
            + len(checkpoint.excluded_month_evidence)
        ),
        qualified_months_by_year=years,
        qualified_quarter_count=quarters,
        request_marker_count=checkpoint.request_marker_count,
        cumulative_payload_bytes_received=checkpoint.cumulative_payload_bytes_received,
        total_new_archive_bytes=checkpoint.total_new_archive_bytes,
        hard_failure_target_key=failed_key,
        hard_failure_reason=failure,
        limitations=result_limitations(),
    )
    _write_json_transactional(args.result, result.model_dump(mode="json"), overwrite=False)
    return result


def run(args, context):
    preflight(args, context)
    checkpoint = load_checkpoint(args, context)
    if not args.checkpoint.exists():
        checkpoint = write_checkpoint(
            args,
            context,
            checkpoint.archive_evidence,
            checkpoint.paired_month_evidence,
            checkpoint.excluded_month_evidence,
        )
    archives = list(checkpoint.archive_evidence)
    pairs = list(checkpoint.paired_month_evidence)
    exclusions = list(checkpoint.excluded_month_evidence)
    by_key = {item.key: item for item in archives}
    completed = {item.month for item in pairs} | {item.month for item in exclusions}
    targets = {item.key: item for item in context.protocol.targets}
    active = "PRE_ACQUISITION"
    try:
        for month in sorted({item.month for item in context.protocol.targets}):
            if month in completed:
                continue
            inspections = {}
            for target in (targets[(month, "SPOT")], targets[(month, "USD_M_PERPETUAL")]):
                active = f"{month}|{target.product}"
                inspection = (
                    _rebuild(args, context, by_key[target.key])
                    if target.key in by_key
                    else _inspect(args, context, target)
                )
                if target.key not in by_key:
                    archives.append(inspection.evidence)
                    by_key[target.key] = inspection.evidence
                    checkpoint = write_checkpoint(args, context, archives, pairs, exclusions)
                    print(
                        f"ARCHIVE {len(archives)}/74 {month} {target.product} "
                        f"{'PASS' if inspection.evidence.archive_pass else 'EXCLUDE'} "
                        f"rows={inspection.evidence.row_count}",
                        flush=True,
                    )
                inspections[target.product] = inspection
                if not inspection.evidence.archive_pass:
                    exclusions.append(
                        PeriodicFlowExcludedMonthEvidence(
                            month=month,
                            failed_stage=(
                                "SPOT_ARCHIVE"
                                if target.product == "SPOT"
                                else "USDM_ARCHIVE"
                            ),
                            failed_product=target.product,
                            reason_codes=inspection.evidence.reason_codes,
                            archive_sha256=inspection.evidence.archive_sha256,
                            source_mode=inspection.evidence.source_mode,
                        )
                    )
                    completed.add(month)
                    checkpoint = write_checkpoint(args, context, archives, pairs, exclusions)
                    print(f"MONTH {month} EXCLUDED", flush=True)
                    break
            if month in completed:
                continue
            pair = pair_month(month, inspections["SPOT"], inspections["USD_M_PERPETUAL"])
            if pair.paired_clock_pass:
                pairs.append(pair)
                print(f"PAIRED {len(pairs)}/37 {month} PASS", flush=True)
            else:
                exclusions.append(
                    PeriodicFlowExcludedMonthEvidence(
                        month=month,
                        failed_stage="PAIRED_CLOCK",
                        failed_product="PAIRED",
                        reason_codes=pair.reason_codes,
                    )
                )
            completed.add(month)
            checkpoint = write_checkpoint(args, context, archives, pairs, exclusions)
        return write_result(args, context, checkpoint)
    except AcquisitionFailure as exc:
        checkpoint = write_checkpoint(args, context, archives, pairs, exclusions)
        return write_result(args, context, checkpoint, active, str(exc))


def parse_args():
    parser = argparse.ArgumentParser(description="Run Q1 successor v5 acquisition.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--run", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument("--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT)
    parser.add_argument(
        "--execution-contract-audit", type=Path, default=DEFAULT_EXECUTION_CONTRACT_AUDIT
    )
    parser.add_argument("--v4-checkpoint", type=Path, default=DEFAULT_V4_CHECKPOINT)
    parser.add_argument("--v4-result", type=Path, default=DEFAULT_V4_RESULT)
    parser.add_argument("--v4-terminal-audit", type=Path, default=DEFAULT_V4_TERMINAL_AUDIT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        context = load_context(args)
        if args.preflight:
            preflight(args, context)
        elif args.check:
            checkpoint = load_checkpoint(args, context)
            result = (
                PeriodicFlowSuccessorAcquisitionResultV5.model_validate_json(
                    args.result.read_text(encoding="utf-8")
                )
                if args.result.exists()
                else None
            )
            print(
                json.dumps(
                    {
                        "archives": len(checkpoint.archive_evidence),
                        "pairs": len(checkpoint.paired_month_evidence),
                        "excluded": len(checkpoint.excluded_month_evidence),
                        "requests": checkpoint.request_marker_count,
                        "terminal": None if result is None else result.decision,
                    },
                    indent=2,
                )
            )
        else:
            result = run(args, context)
            print(
                f"RESULT {result.decision} archives={result.inspected_archive_count} "
                f"paired={result.qualified_paired_month_count} "
                f"excluded={result.excluded_month_count} requests={result.request_marker_count}",
                flush=True,
            )
            if result.decision != (
                "PERMIT_Q1_SUCCESSOR_PAIRED_DEVELOPMENT_MEASUREMENT_PROTOCOL"
            ):
                return 1
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
