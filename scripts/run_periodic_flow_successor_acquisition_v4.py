from __future__ import annotations

import argparse
import json
import shutil
import socket
import sys
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
from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v3 import (  # noqa: E402
    PeriodicFlowSuccessorTerminalAuditV3,
    audit_successor_terminal_audit_v3,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v3 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV3,
    PeriodicFlowSuccessorCheckpointV3,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v4 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV4,
    PeriodicFlowSuccessorCheckpointV4,
    PeriodicFlowSuccessorExecutionContractAuditV4,
    PeriodicFlowSuccessorExecutionContractV4,
    PeriodicFlowSuccessorTransportAmendmentAuditV4,
    PeriodicFlowSuccessorTransportAmendmentV4,
    audit_hash,
    build_acquisition_result_v4,
    build_checkpoint_v4,
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
    target_archive_path,
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

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_audit_v1.json"
)
DEFAULT_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v4.json"
)
DEFAULT_AMENDMENT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_audit_v4.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v4.json"
)
DEFAULT_EXECUTION_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v4.json"
)
DEFAULT_V3_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v3.json"
)
DEFAULT_V3_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v3.json"
)
DEFAULT_V3_TERMINAL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v3.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_ACQUISITION_ROOT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_v4"
)
DEFAULT_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v4.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v4.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/periodic_flow_successor_transport_v4.py")
SCRIPT_PATH = Path("scripts/run_periodic_flow_successor_acquisition_v4.py")
V3_MODULE_PATH = Path("src/aurex/backtest_engine/periodic_flow_successor_transport_v3.py")
V3_SCRIPT_PATH = Path("scripts/run_periodic_flow_successor_acquisition_v3.py")
BOOTSTRAP_MARKER_NAME = "BTCUSDT-trades-2020-08.zip.bootstrap.json"


class ProtocolTransportAdapterV4(ProtocolTransportAdapterV3):
    def __init__(
        self,
        protocol: PeriodicFlowSuccessorAcquisitionProtocol,
        amendment: PeriodicFlowSuccessorTransportAmendmentV4,
    ):
        super().__init__(protocol, amendment)  # type: ignore[arg-type]
        self.continuation_bootstrap_target_key = amendment.bootstrap_target_key

    @property
    def bootstrap_target_key(self) -> str:
        # V4 copies and verifies its bootstrap before entering inherited transport.
        return "V4_BOOTSTRAP_ALREADY_MANAGED"


def current_runner_source_hash_v4() -> str:
    return source_contract_hash(
        PROJECT_ROOT,
        (
            MODULE_PATH,
            SCRIPT_PATH,
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
    amendment = PeriodicFlowSuccessorTransportAmendmentV4.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    amendment_audit = PeriodicFlowSuccessorTransportAmendmentAuditV4.model_validate_json(
        args.amendment_audit.read_text(encoding="utf-8")
    )
    contract = PeriodicFlowSuccessorExecutionContractV4.model_validate_json(
        args.execution_contract.read_text(encoding="utf-8")
    )
    contract_audit = PeriodicFlowSuccessorExecutionContractAuditV4.model_validate_json(
        args.execution_contract_audit.read_text(encoding="utf-8")
    )
    runner_hash = current_runner_source_hash_v4()
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
        or amendment_audit.amendment_evidence_hash != amendment.amendment_evidence_hash
        or contract.amendment_file_sha256 != file_sha256(args.amendment)
        or contract.amendment_evidence_hash != amendment.amendment_evidence_hash
        or contract.amendment_audit_file_sha256 != file_sha256(args.amendment_audit)
        or contract.amendment_audit_evidence_hash != amendment_audit.audit_evidence_hash
        or contract.runner_source_hash != runner_hash
        or contract_audit.contract_file_sha256 != file_sha256(args.execution_contract)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.runner_source_hash != runner_hash
    ):
        raise ValueError("Q1 successor v4 acquisition authority or source changed")
    adapter = ProtocolTransportAdapterV4(protocol, amendment)
    return LoadedContext(  # type: ignore[arg-type]
        protocol=adapter,
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
    )


def _load_seed(args: argparse.Namespace, context: LoadedContext):
    checkpoint = PeriodicFlowSuccessorCheckpointV3.model_validate_json(
        args.v3_checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResultV3.model_validate_json(
        args.v3_result.read_text(encoding="utf-8")
    )
    terminal_audit = PeriodicFlowSuccessorTerminalAuditV3.model_validate_json(
        args.v3_terminal_audit.read_text(encoding="utf-8")
    )
    contract = context.contract
    if (
        file_sha256(args.v3_checkpoint) != contract.seed_v3_checkpoint_file_sha256
        or checkpoint.checkpoint_evidence_hash
        != contract.seed_v3_checkpoint_evidence_hash
        or file_sha256(args.v3_result) != contract.seed_v3_result_file_sha256
        or result.result_evidence_hash != contract.seed_v3_result_evidence_hash
        or file_sha256(args.v3_terminal_audit)
        != contract.seed_v3_terminal_audit_file_sha256
        or terminal_audit.audit_evidence_hash
        != contract.seed_v3_terminal_audit_evidence_hash
        or not audit_successor_terminal_audit_v3(terminal_audit)
        or len(checkpoint.archive_evidence) != contract.seed_archive_count
        or len(checkpoint.paired_month_evidence) != contract.seed_paired_month_count
        or len(checkpoint.excluded_month_evidence)
        != contract.seed_excluded_month_count
    ):
        raise ValueError("Q1 successor v4 seed lineage changed")
    return checkpoint, terminal_audit


def _verify_archive_evidence(*, evidence_root: Path, evidence) -> Path:
    path = (evidence_root / evidence.local_path).resolve()
    if (
        not path.is_relative_to(evidence_root.resolve())
        or not path.is_file()
        or path.stat().st_size != evidence.archive_bytes
        or file_sha256(path) != evidence.archive_sha256
    ):
        raise ValueError(f"Q1 successor v4 seed archive changed: {evidence.key}")
    return path


def verify_checkpoint_archives_v4(
    *, checkpoint: PeriodicFlowSuccessorCheckpointV4, evidence_root: Path
) -> None:
    for evidence in checkpoint.archive_evidence:
        _verify_archive_evidence(evidence_root=evidence_root, evidence=evidence)


def _seed_checkpoint(
    args: argparse.Namespace, context: LoadedContext
) -> PeriodicFlowSuccessorCheckpointV4:
    seed, _ = _load_seed(args, context)
    state = marker_state_v3(args.acquisition_root)
    return build_checkpoint_v4(
        updated_at=datetime.now(UTC),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        runner_source_hash=context.contract.runner_source_hash,
        archive_evidence=seed.archive_evidence,
        paired_month_evidence=seed.paired_month_evidence,
        excluded_month_evidence=seed.excluded_month_evidence,
        request_marker_count=state.request_count,
        response_marker_count=state.response_count,
        request_marker_manifest_hash=state.manifest_hash,
        cumulative_payload_bytes_received=state.payload_bytes_received,
        total_new_archive_bytes=sum(item.new_archive_bytes for item in seed.archive_evidence),
        total_member_uncompressed_bytes=sum(
            item.zip_uncompressed_bytes_total for item in seed.archive_evidence
        ),
    )


def load_checkpoint_v4(
    *, args: argparse.Namespace, context: LoadedContext
) -> PeriodicFlowSuccessorCheckpointV4:
    if not args.checkpoint.exists():
        return _seed_checkpoint(args, context)
    checkpoint = PeriodicFlowSuccessorCheckpointV4.model_validate_json(
        args.checkpoint.read_text(encoding="utf-8")
    )
    state = marker_state_v3(args.acquisition_root)
    if (
        checkpoint.protocol_evidence_hash != context.protocol.protocol_evidence_hash
        or checkpoint.execution_contract_evidence_hash
        != context.contract.contract_evidence_hash
        or checkpoint.runner_source_hash != context.contract.runner_source_hash
        or checkpoint.request_marker_count != state.request_count
        or checkpoint.response_marker_count != state.response_count
        or checkpoint.request_marker_manifest_hash != state.manifest_hash
        or checkpoint.cumulative_payload_bytes_received != state.payload_bytes_received
    ):
        raise ValueError("Q1 successor v4 checkpoint lineage changed")
    return checkpoint


def write_checkpoint_v4(
    *, args: argparse.Namespace, context: LoadedContext, archives, pairs, exclusions
) -> PeriodicFlowSuccessorCheckpointV4:
    state = marker_state_v3(args.acquisition_root)
    if state.request_count != state.response_count:
        raise ValueError("Q1 successor v4 checkpoint refused unmatched markers")
    checkpoint = build_checkpoint_v4(
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
    _write_json_transactional(
        args.checkpoint, checkpoint.model_dump(mode="json"), overwrite=True
    )
    return checkpoint


def _bootstrap_marker_path(root: Path, target) -> Path:
    return target_archive_path(root, target).with_name(BOOTSTRAP_MARKER_NAME)


def ensure_bootstrap_partial_v4(
    *, args: argparse.Namespace, target, context: LoadedContext
) -> Path:
    actual_key = f"{target.month}|{target.product}"
    if actual_key != context.protocol.continuation_bootstrap_target_key:
        raise ValueError("Q1 successor v4 bootstrap target changed")
    source = (PROJECT_ROOT / context.protocol.bootstrap_partial_path).resolve()
    destination = target_archive_path(args.acquisition_root, target)
    partial = destination.with_name(f"{destination.name}.part")
    marker = _bootstrap_marker_path(args.acquisition_root, target)
    if marker.exists():
        payload = json.loads(marker.read_text(encoding="utf-8"))
        valid_partial = (
            partial.is_file()
            and partial.stat().st_size >= context.protocol.bootstrap_partial_bytes
        )
        valid_archive = (
            destination.is_file()
            and destination.stat().st_size
            == context.protocol.bootstrap_expected_total_bytes
            and file_sha256(destination) == target.published_archive_sha256
        )
        if (
            payload.get("schema_version")
            != "aurex-q1-periodic-flow-successor-partial-bootstrap-v4"
            or payload.get("transport_amendment_evidence_hash")
            != context.protocol.amendment_evidence_hash
            or payload.get("execution_contract_evidence_hash")
            != context.contract.contract_evidence_hash
            or payload.get("source_file_sha256")
            != context.protocol.bootstrap_partial_file_sha256
            or payload.get("source_bytes") != context.protocol.bootstrap_partial_bytes
            or not (valid_partial or valid_archive)
        ):
            raise ValueError("Q1 successor v4 bootstrap marker changed")
        return partial if valid_partial else destination
    if tuple(destination.parent.glob(f"{destination.name}.get.*.request.json")):
        raise ValueError("Q1 successor v4 requests exist without bootstrap evidence")
    if (
        not source.is_file()
        or source.stat().st_size != context.protocol.bootstrap_partial_bytes
        or file_sha256(source) != context.protocol.bootstrap_partial_file_sha256
    ):
        raise ValueError("Q1 successor v4 bootstrap source changed")
    destination.parent.mkdir(parents=True, exist_ok=True)
    transaction = partial.with_name(f"{partial.name}.bootstrap.part")
    if not partial.exists():
        if transaction.exists():
            transaction.unlink()
        shutil.copyfile(source, transaction)
        if (
            transaction.stat().st_size != context.protocol.bootstrap_partial_bytes
            or file_sha256(transaction)
            != context.protocol.bootstrap_partial_file_sha256
        ):
            raise ValueError("Q1 successor v4 bootstrap copy failed")
        transaction.replace(partial)
    elif (
        partial.stat().st_size != context.protocol.bootstrap_partial_bytes
        or file_sha256(partial) != context.protocol.bootstrap_partial_file_sha256
    ):
        raise ValueError("Q1 successor v4 unmarked bootstrap partial changed")
    _write_json_transactional(
        marker,
        {
            "schema_version": (
                "aurex-q1-periodic-flow-successor-partial-bootstrap-v4"
            ),
            "transport_amendment_evidence_hash": (
                context.protocol.amendment_evidence_hash
            ),
            "execution_contract_evidence_hash": (
                context.contract.contract_evidence_hash
            ),
            "target_key": actual_key,
            "source_path": context.protocol.bootstrap_partial_path,
            "source_file_sha256": context.protocol.bootstrap_partial_file_sha256,
            "source_bytes": context.protocol.bootstrap_partial_bytes,
            "expected_total_bytes": context.protocol.bootstrap_expected_total_bytes,
            "copied_at": datetime.now(UTC).isoformat(),
        },
        overwrite=False,
    )
    return partial


def preflight(args: argparse.Namespace, context: LoadedContext) -> dict:
    if args.result.exists():
        raise ValueError("A terminal Q1 successor v4 result already exists")
    seed, terminal_audit = _load_seed(args, context)
    for evidence in seed.archive_evidence:
        _verify_archive_evidence(evidence_root=args.evidence_root, evidence=evidence)
    reused = [item for item in context.protocol.targets if item.reuse_candidate_path]
    reused_bytes = 0
    for target in reused:
        path = verify_reuse_archive(evidence_root=args.evidence_root, target=target)
        reused_bytes += path.stat().st_size
        with zipfile.ZipFile(path) as archive:
            select_zip_member(archive, target=target, protocol=context.protocol)
    source = (PROJECT_ROOT / context.protocol.bootstrap_partial_path).resolve()
    if (
        not source.is_file()
        or source.stat().st_size != context.protocol.bootstrap_partial_bytes
        or file_sha256(source) != terminal_audit.partial_archive_file_sha256
    ):
        raise ValueError("Q1 successor v4 preflight bootstrap changed")
    dns_addresses = sorted(
        {
            item[4][0]
            for item in socket.getaddrinfo("data.binance.vision", 443)
            if item[4]
        }
    )
    if not dns_addresses:
        raise AcquisitionFailure("Q1 successor v4 DNS preflight failed")
    state = marker_state_v3(args.acquisition_root)
    free = shutil.disk_usage(args.acquisition_root.parent.resolve()).free
    required = context.contract.required_free_disk_bytes_before_acquisition
    result = {
        "status": "PASS" if free >= required else "BLOCKED_INSUFFICIENT_FREE_DISK",
        "protocol_evidence_hash": context.protocol.protocol_evidence_hash,
        "transport_amendment_evidence_hash": context.protocol.amendment_evidence_hash,
        "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
        "runner_source_hash": context.contract.runner_source_hash,
        "seed_archives_verified": len(seed.archive_evidence),
        "seed_paired_months_verified": len(seed.paired_month_evidence),
        "seed_excluded_months_verified": len(seed.excluded_month_evidence),
        "reuse_candidates_verified": len(reused),
        "reuse_candidate_bytes": reused_bytes,
        "bootstrap_partial_bytes_verified": source.stat().st_size,
        "dns_address_count": len(dns_addresses),
        "free_disk_bytes": free,
        "required_free_disk_bytes_before_acquisition": required,
        "network_requests_made": state.request_count,
        "outcomes_accessed": 0,
        "orders_submitted": 0,
    }
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    if result["status"] != "PASS":
        raise AcquisitionFailure("Q1 successor v4 preflight disk requirement failed")
    return result


def _rebuild_inspection(*, args: argparse.Namespace, context, evidence):
    target = next(item for item in context.protocol.targets if item.key == evidence.key)
    path = _verify_archive_evidence(evidence_root=args.evidence_root, evidence=evidence)
    rebuilt = inspect_archive(
        target=target,
        archive_path=path,
        evidence_root=args.evidence_root,
        protocol=context.protocol,
        source_mode=evidence.source_mode,
        get_attempt_count=evidence.payload_get_attempt_count,
    )
    if rebuilt.evidence != evidence:
        raise ValueError(f"Q1 successor v4 seed evidence changed: {evidence.key}")
    return rebuilt


def _inspect_target(*, args: argparse.Namespace, context, target):
    try:
        if target.reuse_candidate_path is not None:
            path = verify_reuse_archive(evidence_root=args.evidence_root, target=target)
            source_mode = "REUSED_LOCAL"
            attempts = 0
        else:
            if (
                f"{target.month}|{target.product}"
                == context.protocol.continuation_bootstrap_target_key
            ):
                ensure_bootstrap_partial_v4(args=args, target=target, context=context)
            path, attempts = ensure_network_archive_v3(
                root=args.acquisition_root, target=target, context=context
            )
            source_mode = "NETWORK_ACQUIRED"
        return inspect_archive(
            target=target,
            archive_path=path,
            evidence_root=args.evidence_root,
            protocol=context.protocol,
            source_mode=source_mode,
            get_attempt_count=attempts,
        )
    except AcquisitionFailure:
        raise
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise AcquisitionFailure(
            f"Q1 successor v4 archive integrity failed for {target.key}: {exc}"
        ) from exc


def _qualification_counts(pairs: list) -> tuple[dict[str, int], int]:
    by_year = {str(year): 0 for year in range(2020, 2024)}
    quarters: set[tuple[str, int]] = set()
    for pair in pairs:
        year, month = pair.month.split("-")
        by_year[year] += 1
        quarters.add((year, (int(month) - 1) // 3 + 1))
    return by_year, len(quarters)


def write_result_v4(
    *, args, context, checkpoint, hard_failure_target_key, hard_failure_reason
) -> PeriodicFlowSuccessorAcquisitionResultV4:
    by_year, quarter_count = _qualification_counts(list(checkpoint.paired_month_evidence))
    result = build_acquisition_result_v4(
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
        qualified_months_by_year=by_year,
        qualified_quarter_count=quarter_count,
        request_marker_count=checkpoint.request_marker_count,
        cumulative_payload_bytes_received=checkpoint.cumulative_payload_bytes_received,
        total_new_archive_bytes=checkpoint.total_new_archive_bytes,
        hard_failure_target_key=hard_failure_target_key,
        hard_failure_reason=hard_failure_reason,
        limitations=result_limitations(),
    )
    _write_json_transactional(args.result, result.model_dump(mode="json"), overwrite=False)
    return result


def run_acquisition_v4(args: argparse.Namespace, context: LoadedContext):
    preflight(args, context)
    checkpoint = load_checkpoint_v4(args=args, context=context)
    if not args.checkpoint.exists():
        checkpoint = write_checkpoint_v4(
            args=args,
            context=context,
            archives=list(checkpoint.archive_evidence),
            pairs=list(checkpoint.paired_month_evidence),
            exclusions=list(checkpoint.excluded_month_evidence),
        )
    verify_checkpoint_archives_v4(
        checkpoint=checkpoint, evidence_root=args.evidence_root
    )
    archives = list(checkpoint.archive_evidence)
    pairs = list(checkpoint.paired_month_evidence)
    exclusions = list(checkpoint.excluded_month_evidence)
    archive_by_key = {item.key: item for item in archives}
    completed_months = {item.month for item in pairs} | {item.month for item in exclusions}
    target_by_key = {item.key: item for item in context.protocol.targets}
    months = sorted({item.month for item in context.protocol.targets})
    active_key = "PRE_ACQUISITION"
    try:
        for month in months:
            if month in completed_months:
                continue
            inspections = {}
            for target in (
                target_by_key[(month, "SPOT")],
                target_by_key[(month, "USD_M_PERPETUAL")],
            ):
                active_key = f"{target.month}|{target.product}"
                if target.key in archive_by_key:
                    inspection = _rebuild_inspection(
                        args=args, context=context, evidence=archive_by_key[target.key]
                    )
                else:
                    inspection = _inspect_target(
                        args=args, context=context, target=target
                    )
                    archives.append(inspection.evidence)
                    archive_by_key[target.key] = inspection.evidence
                    checkpoint = write_checkpoint_v4(
                        args=args,
                        context=context,
                        archives=archives,
                        pairs=pairs,
                        exclusions=exclusions,
                    )
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
                    completed_months.add(month)
                    checkpoint = write_checkpoint_v4(
                        args=args,
                        context=context,
                        archives=archives,
                        pairs=pairs,
                        exclusions=exclusions,
                    )
                    print(f"MONTH {month} EXCLUDED", flush=True)
                    break
            if month in completed_months:
                continue
            pair = pair_month(
                month, inspections["SPOT"], inspections["USD_M_PERPETUAL"]
            )
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
                print(f"MONTH {month} EXCLUDED stage=PAIRED_CLOCK", flush=True)
            completed_months.add(month)
            checkpoint = write_checkpoint_v4(
                args=args,
                context=context,
                archives=archives,
                pairs=pairs,
                exclusions=exclusions,
            )
        return write_result_v4(
            args=args,
            context=context,
            checkpoint=checkpoint,
            hard_failure_target_key=None,
            hard_failure_reason=None,
        )
    except AcquisitionFailure as exc:
        checkpoint = write_checkpoint_v4(
            args=args,
            context=context,
            archives=archives,
            pairs=pairs,
            exclusions=exclusions,
        )
        return write_result_v4(
            args=args,
            context=context,
            checkpoint=checkpoint,
            hard_failure_target_key=active_key,
            hard_failure_reason=str(exc),
        )


def check_state_v4(args: argparse.Namespace, context: LoadedContext) -> dict:
    checkpoint = load_checkpoint_v4(args=args, context=context)
    verify_checkpoint_archives_v4(
        checkpoint=checkpoint, evidence_root=args.evidence_root
    )
    result = None
    if args.result.exists():
        result = PeriodicFlowSuccessorAcquisitionResultV4.model_validate_json(
            args.result.read_text(encoding="utf-8")
        )
        if (
            result.checkpoint_file_sha256 != file_sha256(args.checkpoint)
            or result.checkpoint_evidence_hash != checkpoint.checkpoint_evidence_hash
            or result.runner_source_hash != context.contract.runner_source_hash
        ):
            raise ValueError("Q1 successor v4 terminal result changed")
    summary = {
        "status": "PASS",
        "inspected_archives": len(checkpoint.archive_evidence),
        "qualified_paired_months": len(checkpoint.paired_month_evidence),
        "excluded_months": len(checkpoint.excluded_month_evidence),
        "request_markers": checkpoint.request_marker_count,
        "payload_bytes_received": checkpoint.cumulative_payload_bytes_received,
        "terminal_result": None if result is None else result.decision,
        "outcomes_accessed": 0,
        "orders_submitted": 0,
    }
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight, run, or check the Q1 successor v4 acquisition."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--run", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument(
        "--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT
    )
    parser.add_argument(
        "--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT
    )
    parser.add_argument(
        "--execution-contract-audit",
        type=Path,
        default=DEFAULT_EXECUTION_CONTRACT_AUDIT,
    )
    parser.add_argument("--v3-checkpoint", type=Path, default=DEFAULT_V3_CHECKPOINT)
    parser.add_argument("--v3-result", type=Path, default=DEFAULT_V3_RESULT)
    parser.add_argument(
        "--v3-terminal-audit", type=Path, default=DEFAULT_V3_TERMINAL_AUDIT
    )
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument(
        "--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT
    )
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
            check_state_v4(args, context)
        else:
            result = run_acquisition_v4(args, context)
            print(
                f"RESULT {result.decision} archives={result.inspected_archive_count} "
                f"paired={result.qualified_paired_month_count} "
                f"excluded={result.excluded_month_count} "
                f"requests={result.request_marker_count}",
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
