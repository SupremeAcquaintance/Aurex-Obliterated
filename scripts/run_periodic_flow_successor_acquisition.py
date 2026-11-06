from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_full_development_runner import (  # noqa: E402
    PeriodicFlowAcquisitionResult as V1AcquisitionResult,
)
from aurex.backtest_engine.periodic_flow_full_development_runner import (  # noqa: E402
    PeriodicFlowExecutionContract as V1ExecutionContract,
)
from aurex.backtest_engine.periodic_flow_successor_acquisition import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionProtocol,
    PeriodicFlowSuccessorAcquisitionProtocolAudit,
)
from aurex.backtest_engine.periodic_flow_successor_acquisition import (  # noqa: E402
    audit_hash as audit_protocol_hash,
)
from aurex.backtest_engine.periodic_flow_successor_runner import (  # noqa: E402
    PeriodicFlowExcludedMonthEvidence,
    PeriodicFlowSuccessorAcquisitionResult,
    PeriodicFlowSuccessorCheckpoint,
    PeriodicFlowSuccessorExecutionContractAuditV2,
    PeriodicFlowSuccessorExecutionContractV2,
    audit_hash,
    build_acquisition_result,
    build_checkpoint,
)
from scripts.freeze_periodic_flow_successor_acquisition_protocol import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    AcquisitionFailure,
    LoadedContext,
    NoRedirectHandler,
    _write_json_transactional,
    file_sha256,
    inspect_archive,
    marker_path,
    marker_state,
    pair_month,
    reconcile_target_markers,
    resolved_archive_path,
    select_zip_member,
    source_contract_hash,
    target_archive_path,
    verify_reuse_archive,
    write_request_marker,
    write_response_marker,
)

DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_audit_v1.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v2.json"
)
DEFAULT_EXECUTION_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v2.json"
)
DEFAULT_V1_EXECUTION_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_full_development_execution_contract_v1.json"
)
DEFAULT_V1_RESULT = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_result_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_ACQUISITION_ROOT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_v2"
)
DEFAULT_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v2.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v2.json"
)
MODULE_PATH = Path("src/aurex/backtest_engine/periodic_flow_successor_runner.py")
SCRIPT_PATH = Path("scripts/run_periodic_flow_successor_acquisition.py")
INHERITED_MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_full_development_runner.py"
)
INHERITED_SCRIPT_PATH = Path(
    "scripts/run_periodic_flow_full_development_acquisition.py"
)


class ProtocolTransportAdapter:
    def __init__(self, protocol: PeriodicFlowSuccessorAcquisitionProtocol):
        self._protocol = protocol
        self.maximum_archive_bytes_each = protocol.maximum_archive_bytes
        self.maximum_member_uncompressed_bytes_each = (
            protocol.maximum_member_uncompressed_bytes
        )
        self.maximum_attempts_per_network_target = 3
        self.maximum_payload_get_attempts = 144
        self.retry_backoff_seconds = (5, 20)
        self.request_timeout_seconds = 300

    def __getattr__(self, name: str):
        return getattr(self._protocol, name)


def _set_idle_socket_timeout(response, seconds: int) -> None:
    raw = getattr(getattr(response, "fp", None), "raw", None)
    socket = getattr(raw, "_sock", None)
    if socket is not None:
        socket.settimeout(seconds)


def ensure_network_archive_v2(
    *, root: Path, target, context: LoadedContext
) -> tuple[Path, int]:
    attempts = reconcile_target_markers(root=root, target=target, context=context)
    destination = target_archive_path(root, target)
    if destination.exists():
        if file_sha256(destination) != target.published_archive_sha256 or attempts == 0:
            raise AcquisitionFailure("Existing Q1 successor archive identity changed")
        latest = json.loads(
            marker_path(root, target, attempts, "response").read_text(encoding="utf-8")
        )
        if latest["outcome"] not in {
            "PASS",
            "RECOVERED_VERIFIED_ARCHIVE_AFTER_INTERRUPTION",
        }:
            raise AcquisitionFailure("Existing Q1 successor archive lacks success evidence")
        return destination, attempts
    if attempts >= context.protocol.maximum_attempts_per_network_target:
        raise AcquisitionFailure(f"Request budget exhausted for {target.key}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(NoRedirectHandler())
    last_error: Exception | None = None
    for attempt in range(
        attempts + 1,
        context.protocol.maximum_attempts_per_network_target + 1,
    ):
        state = marker_state(root)
        if state.request_count >= context.protocol.maximum_payload_get_attempts:
            raise AcquisitionFailure("Global Q1 successor request budget exhausted")
        free = shutil.disk_usage(root.parent.resolve()).free
        if free < (
            context.protocol.maximum_archive_bytes_each
            + context.protocol.minimum_free_disk_bytes_after_acquisition
        ):
            raise AcquisitionFailure("Insufficient disk for a successor archive attempt")
        if (
            state.payload_bytes_received + context.protocol.maximum_archive_bytes_each
            > context.protocol.maximum_new_archive_bytes_total
        ):
            raise AcquisitionFailure("Successor payload budget cannot admit another attempt")
        part = destination.with_name(f"{destination.name}.part")
        if part.exists():
            raise AcquisitionFailure(f"Stale successor partial archive exists: {part}")
        write_request_marker(
            root=root,
            target=target,
            context=context,
            attempt=attempt,
        )
        received = 0
        status: int | None = None
        final_url = target.archive_url
        declared_length: int | None = None
        content_encoding = "identity"
        started = time.monotonic()
        try:
            request = urllib.request.Request(
                target.archive_url,
                headers={
                    "Accept": context.contract.request_accept,
                    "Accept-Encoding": context.contract.request_accept_encoding,
                    "User-Agent": context.contract.request_user_agent,
                },
                method="GET",
            )
            with opener.open(
                request,
                timeout=context.contract.request_timeout_seconds,
            ) as response:
                status = response.getcode()
                final_url = response.geturl()
                content_encoding = response.headers.get(
                    "Content-Encoding", "identity"
                ).lower()
                if status != 200 or final_url != target.archive_url:
                    raise AcquisitionFailure("Q1 successor HTTP response identity changed")
                if content_encoding not in {"", "identity"}:
                    raise AcquisitionFailure("Q1 successor content encoding changed")
                declared = response.headers.get("Content-Length")
                if declared is not None:
                    declared_length = int(declared)
                    if not 0 < declared_length <= context.protocol.maximum_archive_bytes_each:
                        raise AcquisitionFailure(
                            "Q1 successor Content-Length exceeds the frozen limit"
                        )
                _set_idle_socket_timeout(
                    response, context.contract.idle_read_timeout_seconds
                )
                digest = hashlib.sha256()
                with part.open("xb") as output:
                    while True:
                        if (
                            time.monotonic() - started
                            > context.contract.total_archive_deadline_seconds
                        ):
                            raise TimeoutError("Q1 successor total archive deadline exceeded")
                        chunk = response.read1(context.contract.stream_chunk_bytes)
                        if not chunk:
                            break
                        received += len(chunk)
                        if received > context.protocol.maximum_archive_bytes_each:
                            raise AcquisitionFailure(
                                "Q1 successor archive exceeded the per-file byte limit"
                            )
                        if (
                            state.payload_bytes_received + received
                            > context.protocol.maximum_new_archive_bytes_total
                        ):
                            raise AcquisitionFailure(
                                "Q1 successor cumulative bytes exceeded the limit"
                            )
                        digest.update(chunk)
                        output.write(chunk)
                if declared_length is not None and received != declared_length:
                    raise TimeoutError(
                        "Q1 successor payload size differs from Content-Length"
                    )
                if digest.hexdigest() != target.published_archive_sha256:
                    raise AcquisitionFailure(
                        "Q1 successor downloaded archive checksum mismatch"
                    )
            part.replace(destination)
            write_response_marker(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=status,
                final_url=final_url,
                content_length=declared_length,
                content_encoding=content_encoding or "identity",
                bytes_received=received,
                outcome="PASS",
            )
            return destination, attempt
        except urllib.error.HTTPError as exc:
            last_error = exc
            if part.exists():
                part.unlink()
            transient = exc.code in context.contract.transient_http_statuses
            write_response_marker(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=exc.code,
                final_url=exc.geturl() or target.archive_url,
                content_length=None,
                content_encoding="identity",
                bytes_received=received,
                outcome="TRANSIENT" if transient else "HTTP_FAIL",
            )
            if not transient:
                raise AcquisitionFailure(
                    f"Q1 successor HTTP {exc.code} for {target.key}"
                ) from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_error = exc
            if part.exists():
                part.unlink()
            write_response_marker(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=status,
                final_url=final_url,
                content_length=declared_length,
                content_encoding=content_encoding or "identity",
                bytes_received=received,
                outcome="TRANSIENT",
            )
        except AcquisitionFailure:
            if part.exists():
                part.unlink()
            write_response_marker(
                root=root,
                target=target,
                context=context,
                attempt=attempt,
                status=status,
                final_url=final_url,
                content_length=declared_length,
                content_encoding=content_encoding or "identity",
                bytes_received=received,
                outcome="INTEGRITY_FAIL",
            )
            raise
        if attempt < context.protocol.maximum_attempts_per_network_target:
            time.sleep(context.protocol.retry_backoff_seconds[attempt - 1])
    raise AcquisitionFailure(
        f"Q1 successor payload unresolved for {target.key}"
    ) from last_error


def current_runner_source_hash() -> str:
    return source_contract_hash(
        PROJECT_ROOT,
        (MODULE_PATH, SCRIPT_PATH, INHERITED_MODULE_PATH, INHERITED_SCRIPT_PATH),
    )


def load_context(args: argparse.Namespace) -> LoadedContext:
    protocol = PeriodicFlowSuccessorAcquisitionProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = PeriodicFlowSuccessorAcquisitionProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    contract = PeriodicFlowSuccessorExecutionContractV2.model_validate_json(
        args.execution_contract.read_text(encoding="utf-8")
    )
    contract_audit = PeriodicFlowSuccessorExecutionContractAuditV2.model_validate_json(
        args.execution_contract_audit.read_text(encoding="utf-8")
    )
    v1_contract = V1ExecutionContract.model_validate_json(
        args.v1_execution_contract.read_text(encoding="utf-8")
    )
    v1_result = V1AcquisitionResult.model_validate_json(
        args.v1_result.read_text(encoding="utf-8")
    )
    runner_hash = current_runner_source_hash()
    if (
        not audit_protocol_hash(protocol, "protocol_evidence_hash")
        or not audit_protocol_hash(protocol_audit, "audit_evidence_hash")
        or protocol_audit.protocol_file_sha256 != file_sha256(args.protocol)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or not audit_hash(contract, "contract_evidence_hash")
        or contract.parent_protocol_file_sha256 != file_sha256(args.protocol)
        or contract.parent_protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.parent_protocol_audit_file_sha256 != file_sha256(args.protocol_audit)
        or contract.parent_protocol_audit_evidence_hash
        != protocol_audit.audit_evidence_hash
        or contract.inherited_v1_execution_contract_evidence_hash
        != v1_contract.contract_evidence_hash
        or contract.inherited_v1_runner_source_hash != v1_contract.runner_source_hash
        or contract.runner_source_hash != runner_hash
        or not audit_hash(contract_audit, "audit_evidence_hash")
        or contract_audit.contract_file_sha256 != file_sha256(args.execution_contract)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or contract_audit.runner_source_hash != runner_hash
        or v1_result.runner_source_hash != v1_contract.runner_source_hash
    ):
        raise ValueError("Q1 successor acquisition authority or source changed")
    return LoadedContext(  # type: ignore[arg-type]
        protocol=ProtocolTransportAdapter(protocol),
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
    )


def empty_checkpoint(context: LoadedContext) -> PeriodicFlowSuccessorCheckpoint:
    return build_checkpoint(
        updated_at=datetime.now(UTC),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        runner_source_hash=context.contract.runner_source_hash,
        archive_evidence=(),
        paired_month_evidence=(),
        excluded_month_evidence=(),
        request_marker_count=0,
        response_marker_count=0,
        request_marker_manifest_hash=marker_state(DEFAULT_ACQUISITION_ROOT).manifest_hash,
        cumulative_payload_bytes_received=0,
        total_new_archive_bytes=0,
        total_member_uncompressed_bytes=0,
    )


def load_checkpoint(
    *, path: Path, context: LoadedContext, acquisition_root: Path
) -> PeriodicFlowSuccessorCheckpoint:
    if not path.exists():
        state = marker_state(acquisition_root)
        if state.request_count or state.response_count:
            raise ValueError("Q1 successor markers exist without a checkpoint")
        return build_checkpoint(
            updated_at=datetime.now(UTC),
            protocol_evidence_hash=context.protocol.protocol_evidence_hash,
            execution_contract_evidence_hash=context.contract.contract_evidence_hash,
            runner_source_hash=context.contract.runner_source_hash,
            archive_evidence=(),
            paired_month_evidence=(),
            excluded_month_evidence=(),
            request_marker_count=0,
            response_marker_count=0,
            request_marker_manifest_hash=state.manifest_hash,
            cumulative_payload_bytes_received=0,
            total_new_archive_bytes=0,
            total_member_uncompressed_bytes=0,
        )
    checkpoint = PeriodicFlowSuccessorCheckpoint.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    state = marker_state(acquisition_root)
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
        raise ValueError("Q1 successor checkpoint lineage or marker state changed")
    return checkpoint


def write_checkpoint(
    *,
    path: Path,
    context: LoadedContext,
    acquisition_root: Path,
    archives: list,
    pairs: list,
    exclusions: list,
) -> PeriodicFlowSuccessorCheckpoint:
    state = marker_state(acquisition_root)
    if state.request_count != state.response_count:
        raise ValueError("Q1 successor checkpoint refused unmatched HTTP markers")
    checkpoint = build_checkpoint(
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
    _write_json_transactional(path, checkpoint.model_dump(mode="json"), overwrite=True)
    return checkpoint


def verify_checkpoint_archives(
    *, checkpoint: PeriodicFlowSuccessorCheckpoint, evidence_root: Path
) -> None:
    for evidence in checkpoint.archive_evidence:
        path = (evidence_root / evidence.local_path).resolve()
        if (
            not path.is_relative_to(evidence_root.resolve())
            or not path.is_file()
            or path.stat().st_size != evidence.archive_bytes
            or file_sha256(path) != evidence.archive_sha256
        ):
            raise ValueError(f"Q1 successor checkpoint archive changed: {evidence.key}")


def preflight(args: argparse.Namespace, context: LoadedContext) -> dict:
    if args.result.exists():
        raise ValueError("A terminal Q1 successor acquisition result already exists")
    if list(args.acquisition_root.rglob("*.part")):
        raise ValueError("Unaccounted Q1 successor partial files exist")
    reused = [item for item in context.protocol.targets if item.reuse_candidate_path]
    reused_bytes = 0
    for index, target in enumerate(reused, start=1):
        path = verify_reuse_archive(evidence_root=args.evidence_root, target=target)
        reused_bytes += path.stat().st_size
        with zipfile.ZipFile(path) as archive:
            select_zip_member(archive, target=target, protocol=context.protocol)
        print(
            f"PREFLIGHT_REUSE {index}/26 {target.month} {target.product} PASS",
            flush=True,
        )
    free = shutil.disk_usage(args.acquisition_root.parent.resolve()).free
    required = context.contract.required_free_disk_bytes_before_acquisition
    state = marker_state(args.acquisition_root)
    result = {
        "status": "PASS" if free >= required else "BLOCKED_INSUFFICIENT_FREE_DISK",
        "protocol_evidence_hash": context.protocol.protocol_evidence_hash,
        "execution_contract_evidence_hash": context.contract.contract_evidence_hash,
        "runner_source_hash": context.contract.runner_source_hash,
        "reuse_candidates_verified": len(reused),
        "reuse_candidate_bytes": reused_bytes,
        "maximum_network_targets": context.protocol.maximum_network_target_count,
        "free_disk_bytes": free,
        "required_free_disk_bytes_before_acquisition": required,
        "additional_free_disk_bytes_required": max(0, required - free),
        "network_requests_made": state.request_count,
        "price_or_quantity_values_parsed": [],
        "outcomes_accessed": 0,
        "orders_submitted": 0,
    }
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    if result["status"] != "PASS":
        raise AcquisitionFailure("Q1 successor preflight disk requirement failed")
    return result


def result_limitations() -> tuple[str, ...]:
    return (
        "A pass covers structurally qualified paired development months only.",
        "Acquisition does not establish a market mechanism or edge.",
        "Buyer-maker flags are source fields, not trading signals.",
        "Failed source months remain excluded whole without synthesis.",
        "No price, quantity, quote quantity, feature, parameter, or return was parsed.",
        "No strategy candidate, Pine implementation, signal, or trade was created.",
        "Validation, holdout, and forward outcomes remained sealed.",
        "Paper and Testnet strategy-order authority remain false.",
        "Production, live, real-capital authority, and profit remain false.",
        "A pass permits only a separately frozen no-outcome measurement protocol.",
    )


def qualification_counts(pairs: list) -> tuple[dict[str, int], int]:
    by_year = {str(year): 0 for year in range(2020, 2024)}
    quarters: set[tuple[str, int]] = set()
    for pair in pairs:
        year, month = pair.month.split("-")
        by_year[year] += 1
        quarters.add((year, (int(month) - 1) // 3 + 1))
    return by_year, len(quarters)


def write_result(
    *,
    args: argparse.Namespace,
    context: LoadedContext,
    checkpoint: PeriodicFlowSuccessorCheckpoint,
    hard_failure_target_key: str | None,
    hard_failure_reason: str | None,
) -> PeriodicFlowSuccessorAcquisitionResult:
    by_year, quarter_count = qualification_counts(list(checkpoint.paired_month_evidence))
    result = build_acquisition_result(
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


def inspect_target(
    *, args: argparse.Namespace, context: LoadedContext, target
):
    try:
        if target.reuse_candidate_path is not None:
            path = verify_reuse_archive(evidence_root=args.evidence_root, target=target)
            source_mode = "REUSED_LOCAL"
            attempts = 0
        else:
            path, attempts = ensure_network_archive_v2(
                root=args.acquisition_root,
                target=target,
                context=context,
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
            f"Q1 successor archive integrity failed for {target.key}: {exc}"
        ) from exc


def rebuild_inspection(*, args: argparse.Namespace, context: LoadedContext, evidence):
    target = next(item for item in context.protocol.targets if item.key == evidence.key)
    path = resolved_archive_path(
        evidence_root=args.evidence_root,
        acquisition_root=args.acquisition_root,
        target=target,
    )
    rebuilt = inspect_archive(
        target=target,
        archive_path=path,
        evidence_root=args.evidence_root,
        protocol=context.protocol,
        source_mode=evidence.source_mode,
        get_attempt_count=evidence.payload_get_attempt_count,
    )
    if rebuilt.evidence != evidence:
        raise ValueError(f"Q1 successor archive evidence changed: {evidence.key}")
    return rebuilt


def run_acquisition(
    args: argparse.Namespace, context: LoadedContext
) -> PeriodicFlowSuccessorAcquisitionResult:
    preflight(args, context)
    checkpoint = load_checkpoint(
        path=args.checkpoint,
        context=context,
        acquisition_root=args.acquisition_root,
    )
    if not args.checkpoint.exists():
        checkpoint = write_checkpoint(
            path=args.checkpoint,
            context=context,
            acquisition_root=args.acquisition_root,
            archives=[],
            pairs=[],
            exclusions=[],
        )
    verify_checkpoint_archives(checkpoint=checkpoint, evidence_root=args.evidence_root)
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
            spot_target = target_by_key[(month, "SPOT")]
            raw_target = target_by_key[(month, "USD_M_PERPETUAL")]
            for target in (spot_target, raw_target):
                active_key = f"{target.month}|{target.product}"
                if target.key in archive_by_key:
                    inspection = rebuild_inspection(
                        args=args,
                        context=context,
                        evidence=archive_by_key[target.key],
                    )
                else:
                    inspection = inspect_target(args=args, context=context, target=target)
                    archives.append(inspection.evidence)
                    archive_by_key[target.key] = inspection.evidence
                    checkpoint = write_checkpoint(
                        path=args.checkpoint,
                        context=context,
                        acquisition_root=args.acquisition_root,
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
                    checkpoint = write_checkpoint(
                        path=args.checkpoint,
                        context=context,
                        acquisition_root=args.acquisition_root,
                        archives=archives,
                        pairs=pairs,
                        exclusions=exclusions,
                    )
                    print(
                        f"MONTH {month} EXCLUDED stage={exclusions[-1].failed_stage} "
                        f"reasons={exclusions[-1].reason_codes}",
                        flush=True,
                    )
                    break
            if month in completed_months:
                continue
            pair = pair_month(month, inspections["SPOT"], inspections["USD_M_PERPETUAL"])
            if pair.paired_clock_pass:
                pairs.append(pair)
                print(
                    f"PAIRED {len(pairs)}/37 {month} PASS "
                    f"coverage={pair.paired_minute_coverage_fraction}",
                    flush=True,
                )
            else:
                exclusions.append(
                    PeriodicFlowExcludedMonthEvidence(
                        month=month,
                        failed_stage="PAIRED_CLOCK",
                        failed_product="PAIRED",
                        reason_codes=pair.reason_codes,
                    )
                )
                print(
                    f"MONTH {month} EXCLUDED stage=PAIRED_CLOCK "
                    f"reasons={pair.reason_codes}",
                    flush=True,
                )
            completed_months.add(month)
            checkpoint = write_checkpoint(
                path=args.checkpoint,
                context=context,
                acquisition_root=args.acquisition_root,
                archives=archives,
                pairs=pairs,
                exclusions=exclusions,
            )
        return write_result(
            args=args,
            context=context,
            checkpoint=checkpoint,
            hard_failure_target_key=None,
            hard_failure_reason=None,
        )
    except AcquisitionFailure as exc:
        checkpoint = write_checkpoint(
            path=args.checkpoint,
            context=context,
            acquisition_root=args.acquisition_root,
            archives=archives,
            pairs=pairs,
            exclusions=exclusions,
        )
        return write_result(
            args=args,
            context=context,
            checkpoint=checkpoint,
            hard_failure_target_key=active_key,
            hard_failure_reason=str(exc),
        )


def check_state(args: argparse.Namespace, context: LoadedContext) -> dict:
    checkpoint = load_checkpoint(
        path=args.checkpoint,
        context=context,
        acquisition_root=args.acquisition_root,
    )
    verify_checkpoint_archives(checkpoint=checkpoint, evidence_root=args.evidence_root)
    result = None
    if args.result.exists():
        result = PeriodicFlowSuccessorAcquisitionResult.model_validate_json(
            args.result.read_text(encoding="utf-8")
        )
        if (
            result.checkpoint_file_sha256 != file_sha256(args.checkpoint)
            or result.checkpoint_evidence_hash != checkpoint.checkpoint_evidence_hash
            or result.runner_source_hash != context.contract.runner_source_hash
        ):
            raise ValueError("Q1 successor terminal result changed")
    summary = {
        "status": "PASS",
        "inspected_archives": len(checkpoint.archive_evidence),
        "qualified_paired_months": len(checkpoint.paired_month_evidence),
        "excluded_months": len(checkpoint.excluded_month_evidence),
        "request_markers": checkpoint.request_marker_count,
        "terminal_result": None if result is None else result.decision,
        "outcomes_accessed": 0,
        "orders_submitted": 0,
    }
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight, run, or check the Q1 successor paired acquisition."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--run", action="store_true")
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
    parser.add_argument(
        "--v1-execution-contract", type=Path, default=DEFAULT_V1_EXECUTION_CONTRACT
    )
    parser.add_argument("--v1-result", type=Path, default=DEFAULT_V1_RESULT)
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
            check_state(args, context)
        else:
            result = run_acquisition(args, context)
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
