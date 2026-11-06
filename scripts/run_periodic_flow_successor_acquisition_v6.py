from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sys
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from itertools import chain
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
from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v5 import (  # noqa: E402
    PeriodicFlowSuccessorTerminalAuditV5,
    audit_successor_terminal_audit_v5,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v5 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV5,
    PeriodicFlowSuccessorCheckpointV5,
)
from aurex.backtest_engine.periodic_flow_successor_validator_v6 import (  # noqa: E402
    PeriodicFlowArchiveEvidenceV6,
    PeriodicFlowSuccessorAcquisitionResultV6,
    PeriodicFlowSuccessorCheckpointV6,
    PeriodicFlowSuccessorExecutionContractAuditV6,
    PeriodicFlowSuccessorExecutionContractV6,
    PeriodicFlowSuccessorValidatorAmendmentAuditV6,
    PeriodicFlowSuccessorValidatorAmendmentV6,
    audit_hash,
    build_acquisition_result_v6,
    build_checkpoint_v6,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    RAW_HEADER_ALIASES,
    SPOT_HEADER_ALIASES,
    AcquisitionFailure,
    ArchiveInspection,
    LoadedContext,
    _write_json_transactional,
    evidence_reason_codes,
    file_sha256,
    month_bounds_ms,
    normalized_header,
    pair_month,
    parse_bool,
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
from scripts.run_periodic_flow_successor_acquisition_v5 import (  # noqa: E402
    V4_MODULE_PATH,
    V4_SCRIPT_PATH,
    _wait_for_dns,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_audit_v1.json"
)
DEFAULT_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_validator_amendment_v6.json"
)
DEFAULT_AMENDMENT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_validator_amendment_audit_v6.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v6.json"
)
DEFAULT_EXECUTION_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v6.json"
)
DEFAULT_V5_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v5.json"
)
DEFAULT_V5_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v5.json"
)
DEFAULT_V5_TERMINAL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v5.json"
)
DEFAULT_V5_TRANSPORT_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v5.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_ACQUISITION_ROOT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_v6"
)
DEFAULT_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v6.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v6.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_successor_validator_v6.py"
)
SCRIPT_PATH = Path("scripts/run_periodic_flow_successor_acquisition_v6.py")
V5_MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_successor_transport_v5.py"
)
V5_SCRIPT_PATH = Path("scripts/run_periodic_flow_successor_acquisition_v5.py")


class ProtocolTransportAdapterV6(ProtocolTransportAdapterV3):
    def __init__(self, protocol, amendment, transport):
        super().__init__(protocol, transport)
        self._validator_amendment = amendment

    @property
    def bootstrap_target_key(self) -> str:
        return "V6_CHECKPOINT_ONLY_NO_BOOTSTRAP"

    @property
    def amendment_evidence_hash(self) -> str:
        return self._validator_amendment.amendment_evidence_hash

    @property
    def request_marker_schema(self) -> str:
        return "aurex-q1-periodic-flow-successor-http-request-v6"

    @property
    def response_marker_schema(self) -> str:
        return "aurex-q1-periodic-flow-successor-http-response-v6"

    def __getattr__(self, name: str):
        try:
            return getattr(self._validator_amendment, name)
        except AttributeError:
            return super().__getattr__(name)


def current_runner_source_hash_v6() -> str:
    return source_contract_hash(
        PROJECT_ROOT,
        (
            MODULE_PATH,
            SCRIPT_PATH,
            V5_MODULE_PATH,
            V5_SCRIPT_PATH,
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
    amendment = PeriodicFlowSuccessorValidatorAmendmentV6.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    amendment_audit = PeriodicFlowSuccessorValidatorAmendmentAuditV6.model_validate_json(
        args.amendment_audit.read_text(encoding="utf-8")
    )
    contract = PeriodicFlowSuccessorExecutionContractV6.model_validate_json(
        args.execution_contract.read_text(encoding="utf-8")
    )
    contract_audit = PeriodicFlowSuccessorExecutionContractAuditV6.model_validate_json(
        args.execution_contract_audit.read_text(encoding="utf-8")
    )
    terminal = PeriodicFlowSuccessorTerminalAuditV5.model_validate_json(
        args.v5_terminal_audit.read_text(encoding="utf-8")
    )
    transport = __import__(
        "aurex.backtest_engine.periodic_flow_successor_transport_v5",
        fromlist=["PeriodicFlowSuccessorTransportAmendmentV5"],
    ).PeriodicFlowSuccessorTransportAmendmentV5.model_validate_json(
        args.v5_transport_amendment.read_text(encoding="utf-8")
    )
    runner_hash = current_runner_source_hash_v6()
    if (
        not audit_protocol_hash(protocol, "protocol_evidence_hash")
        or not audit_protocol_hash(protocol_audit, "audit_evidence_hash")
        or not audit_hash(amendment, "amendment_evidence_hash")
        or not audit_hash(amendment_audit, "audit_evidence_hash")
        or not audit_hash(contract, "contract_evidence_hash")
        or not audit_hash(contract_audit, "audit_evidence_hash")
        or not audit_successor_terminal_audit_v5(terminal)
        or protocol_audit.protocol_file_sha256 != file_sha256(args.protocol)
        or amendment.parent_protocol_file_sha256 != file_sha256(args.protocol)
        or amendment.parent_v5_amendment_file_sha256
        != file_sha256(args.v5_transport_amendment)
        or amendment.parent_v5_amendment_evidence_hash
        != transport.amendment_evidence_hash
        or amendment_audit.amendment_file_sha256 != file_sha256(args.amendment)
        or contract.amendment_file_sha256 != file_sha256(args.amendment)
        or contract.amendment_audit_file_sha256 != file_sha256(args.amendment_audit)
        or contract.runner_source_hash != runner_hash
        or contract_audit.contract_file_sha256 != file_sha256(args.execution_contract)
        or contract_audit.runner_source_hash != runner_hash
    ):
        raise ValueError("Q1 successor v6 acquisition authority or source changed")
    return LoadedContext(  # type: ignore[arg-type]
        protocol=ProtocolTransportAdapterV6(protocol, amendment, transport),
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
    )


def _seed(args, context):
    checkpoint = PeriodicFlowSuccessorCheckpointV5.model_validate_json(
        args.v5_checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResultV5.model_validate_json(
        args.v5_result.read_text(encoding="utf-8")
    )
    terminal = PeriodicFlowSuccessorTerminalAuditV5.model_validate_json(
        args.v5_terminal_audit.read_text(encoding="utf-8")
    )
    if (
        file_sha256(args.v5_checkpoint)
        != context.contract.seed_v5_checkpoint_file_sha256
        or checkpoint.checkpoint_evidence_hash
        != context.contract.seed_v5_checkpoint_evidence_hash
        or file_sha256(args.v5_result) != context.contract.seed_v5_result_file_sha256
        or result.result_evidence_hash != context.contract.seed_v5_result_evidence_hash
        or file_sha256(args.v5_terminal_audit)
        != context.contract.seed_v5_terminal_audit_file_sha256
        or terminal.audit_evidence_hash
        != context.contract.seed_v5_terminal_audit_evidence_hash
        or len(checkpoint.archive_evidence) != context.contract.seed_archive_count
        or len(checkpoint.paired_month_evidence)
        != context.contract.seed_paired_month_count
        or len(checkpoint.excluded_month_evidence)
        != context.contract.seed_excluded_month_count
    ):
        raise ValueError("Q1 successor v6 seed lineage changed")
    return checkpoint


def _verify_evidence(evidence_root: Path, evidence) -> Path:
    path = (evidence_root / evidence.local_path).resolve()
    if (
        not path.is_relative_to(evidence_root.resolve())
        or not path.is_file()
        or path.stat().st_size != evidence.archive_bytes
        or file_sha256(path) != evidence.archive_sha256
    ):
        raise ValueError(f"Q1 successor v6 archive changed: {evidence.key}")
    return path


def inspect_archive_v6(
    *, target, archive_path, evidence_root, protocol, source_mode, get_attempt_count
):
    archive_hash = file_sha256(archive_path)
    if archive_hash != target.published_archive_sha256:
        raise ValueError(f"Q1 archive checksum changed during inspection: {target.key}")
    start_ms, end_ms, expected_minutes = month_bounds_ms(target.month)
    row_count = 0
    min_timestamp = max_timestamp = previous_timestamp = None
    min_primary = max_primary = previous_primary = None
    non_increasing = duplicates = forward_gap_count = skipped_count = max_skip = 0
    min_raw = max_raw = previous_last_raw = None
    raw_range_gaps = raw_range_non_increasing = timestamp_regressions = 0
    makers: set[bool] = set()
    minutes: set[int] = set()
    header_present = False
    with zipfile.ZipFile(archive_path) as archive:
        (
            member,
            compressed_total,
            uncompressed_total,
            duplicate_name,
            canonical_hash,
            duplicate_hash,
            duplicate_identical,
        ) = select_zip_member(archive, target=target, protocol=protocol)
        with archive.open(member) as binary:
            reader = csv.reader(io.TextIOWrapper(binary, encoding="utf-8", newline=""))
            try:
                first_row = next(reader)
            except StopIteration as exc:
                raise ValueError("Q1 structural CSV is empty") from exc
            if len(first_row) != len(target.expected_columns):
                raise ValueError("Q1 structural CSV column count changed")
            try:
                int(first_row[0])
            except ValueError:
                header_present = True
                aliases = SPOT_HEADER_ALIASES if target.product == "SPOT" else RAW_HEADER_ALIASES
                if normalized_header(first_row, aliases) != target.expected_columns:
                    raise ValueError("Q1 structural CSV header changed") from None
                rows = reader
            else:
                rows = chain((first_row,), reader)
            for row in rows:
                if len(row) != len(target.expected_columns):
                    raise ValueError("Q1 structural CSV column count changed")
                try:
                    primary_id = int(row[0])
                    if target.product == "SPOT":
                        first_raw, last_raw = int(row[3]), int(row[4])
                        timestamp, maker = int(row[5]), parse_bool(row[6])
                        if first_raw > last_raw:
                            raise ValueError("Q1 Spot raw trade range is reversed")
                    else:
                        first_raw = last_raw = None
                        timestamp, maker = int(row[4]), parse_bool(row[5])
                except ValueError as exc:
                    raise ValueError(
                        "Q1 structural ID, timestamp, or maker value is invalid"
                    ) from exc
                if not start_ms <= timestamp < end_ms:
                    raise ValueError("Q1 structural timestamp is outside the frozen month")
                if previous_primary is not None:
                    if primary_id <= previous_primary:
                        non_increasing += 1
                        duplicates += primary_id == previous_primary
                    elif primary_id > previous_primary + 1:
                        forward_gap_count += 1
                        skipped = primary_id - previous_primary - 1
                        skipped_count += skipped
                        max_skip = max(max_skip, skipped)
                if previous_timestamp is not None and timestamp < previous_timestamp:
                    timestamp_regressions += 1
                if target.product == "SPOT":
                    if previous_last_raw is not None:
                        raw_range_non_increasing += first_raw <= previous_last_raw
                        raw_range_gaps += first_raw > previous_last_raw + 1
                    min_raw = first_raw if min_raw is None else min(min_raw, first_raw)
                    max_raw = last_raw if max_raw is None else max(max_raw, last_raw)
                    previous_last_raw = last_raw
                min_primary = primary_id if min_primary is None else min(min_primary, primary_id)
                max_primary = primary_id if max_primary is None else max(max_primary, primary_id)
                min_timestamp = (
                    timestamp if min_timestamp is None else min(min_timestamp, timestamp)
                )
                max_timestamp = (
                    timestamp if max_timestamp is None else max(max_timestamp, timestamp)
                )
                previous_primary, previous_timestamp = primary_id, timestamp
                makers.add(maker)
                minutes.add((timestamp - start_ms) // 60_000)
                row_count += 1
    if not row_count or None in (min_timestamp, max_timestamp, min_primary, max_primary):
        raise ValueError("Q1 structural CSV has no rows")
    ordered_minutes = sorted(minutes)
    maximum_event_gap = max(
        (b - a for a, b in zip(ordered_minutes, ordered_minutes[1:], strict=False)),
        default=0,
    )
    unordered_usdm = target.product == "USD_M_PERPETUAL" and non_increasing > 0
    if target.product == "SPOT" or unordered_usdm:
        forward_gap_model = skipped_count_model = max_skip_model = 0
        skipped_fraction_model = Decimal(0)
    else:
        forward_gap_model, skipped_count_model, max_skip_model = (
            forward_gap_count,
            skipped_count,
            max_skip,
        )
        span = max_primary - min_primary + 1
        skipped_fraction_model = Decimal(skipped_count) / Decimal(span)
    coverage = Decimal(len(minutes)) / Decimal(expected_minutes)
    maker_tuple = tuple(sorted(makers))
    reasons = evidence_reason_codes(
        product=target.product,
        row_count=row_count,
        coverage=coverage,
        maximum_event_gap_minutes=maximum_event_gap,
        non_increasing=non_increasing,
        duplicates=duplicates,
        forward_gaps=forward_gap_model,
        skipped_fraction=skipped_fraction_model,
        max_skip=max_skip_model,
        raw_range_gaps=raw_range_gaps if target.product == "SPOT" else None,
        raw_range_non_increasing=(
            raw_range_non_increasing if target.product == "SPOT" else None
        ),
        timestamp_regressions=timestamp_regressions,
        makers=maker_tuple,
    )
    evidence = PeriodicFlowArchiveEvidenceV6(
        month=target.month,
        product=target.product,
        family=target.family,
        source_mode=source_mode,
        archive_url=target.archive_url,
        local_path=archive_path.resolve().relative_to(evidence_root.resolve()).as_posix(),
        archive_bytes=archive_path.stat().st_size,
        archive_sha256=archive_hash,
        zip_member_count=2 if duplicate_name is not None else 1,
        selected_member_name=member.filename,
        zip_compressed_bytes_total=compressed_total,
        zip_uncompressed_bytes_total=uncompressed_total,
        selected_member_uncompressed_bytes=member.file_size,
        duplicate_member_name=duplicate_name,
        canonical_member_sha256=canonical_hash,
        duplicate_member_sha256=duplicate_hash,
        duplicate_member_byte_identical=duplicate_identical,
        column_count=len(target.expected_columns),
        header_present=header_present,
        row_count=row_count,
        first_timestamp_ms=min_timestamp,
        last_timestamp_ms=max_timestamp,
        unique_minute_count=len(minutes),
        expected_minute_count=expected_minutes,
        minute_coverage_fraction=coverage,
        maximum_event_gap_minutes=maximum_event_gap,
        first_primary_id=min_primary,
        last_primary_id=max_primary,
        primary_id_non_increasing_count=non_increasing,
        primary_id_duplicate_count=duplicates,
        primary_id_forward_gap_count=forward_gap_model,
        primary_id_skipped_count=skipped_count_model,
        primary_id_skipped_fraction=skipped_fraction_model,
        maximum_single_primary_id_skip_count=max_skip_model,
        first_raw_trade_id=min_raw if target.product == "SPOT" else None,
        last_raw_trade_id=max_raw if target.product == "SPOT" else None,
        raw_range_gap_count=raw_range_gaps if target.product == "SPOT" else None,
        raw_range_non_increasing_count=(
            raw_range_non_increasing if target.product == "SPOT" else None
        ),
        timestamp_regression_count=timestamp_regressions,
        buyer_maker_values_observed=maker_tuple,
        payload_get_attempt_count=get_attempt_count,
        new_archive_bytes=(
            archive_path.stat().st_size if source_mode == "NETWORK_ACQUIRED" else 0
        ),
        archive_pass=not reasons,
        reason_codes=reasons,
        parsed_numeric_fields=(
            ("aggregate_trade_id", "first_trade_id", "last_trade_id", "timestamp")
            if target.product == "SPOT"
            else ("timestamp", "trade_id")
        ),
    )
    return ArchiveInspection(evidence=evidence, minute_indexes=frozenset(minutes))


def _build_checkpoint(args, context, archives, pairs, exclusions):
    state = marker_state_v3(args.acquisition_root)
    return build_checkpoint_v6(
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
    checkpoint = PeriodicFlowSuccessorCheckpointV6.model_validate_json(
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
        raise ValueError("Q1 successor v6 checkpoint lineage changed")
    return checkpoint


def write_checkpoint(args, context, archives, pairs, exclusions):
    checkpoint = _build_checkpoint(args, context, archives, pairs, exclusions)
    if checkpoint.request_marker_count != checkpoint.response_marker_count:
        raise ValueError("Q1 successor v6 checkpoint refused unmatched markers")
    _write_json_transactional(
        args.checkpoint, checkpoint.model_dump(mode="json"), overwrite=True
    )
    return checkpoint


def preflight(args, context):
    if args.result.exists():
        raise ValueError("A terminal Q1 successor v6 result already exists")
    seed = _seed(args, context)
    for evidence in seed.archive_evidence:
        _verify_evidence(args.evidence_root, evidence)
    terminal = (PROJECT_ROOT / context.protocol.terminal_archive_path).resolve()
    if (
        not terminal.is_file()
        or terminal.stat().st_size != context.protocol.terminal_archive_bytes
        or file_sha256(terminal) != context.protocol.terminal_archive_sha256
    ):
        raise ValueError("Q1 successor v6 terminal archive changed")
    reused = [item for item in context.protocol.targets if item.reuse_candidate_path]
    for target in reused:
        path = verify_reuse_archive(evidence_root=args.evidence_root, target=target)
        with zipfile.ZipFile(path) as archive:
            select_zip_member(archive, target=target, protocol=context.protocol)
    _wait_for_dns(context)
    free = shutil.disk_usage(args.acquisition_root.parent.resolve()).free
    result = {
        "status": (
            "PASS"
            if free >= context.contract.required_free_disk_bytes_before_acquisition
            else "BLOCKED_INSUFFICIENT_FREE_DISK"
        ),
        "seed_archives_verified": len(seed.archive_evidence),
        "seed_pairs_verified": len(seed.paired_month_evidence),
        "seed_exclusions_verified": len(seed.excluded_month_evidence),
        "terminal_archive_verified": True,
        "free_disk_bytes": free,
        "required_free_disk_bytes": context.contract.required_free_disk_bytes_before_acquisition,
        "network_requests_made": marker_state_v3(args.acquisition_root).request_count,
        "outcomes_accessed": 0,
        "orders_submitted": 0,
    }
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    if result["status"] != "PASS":
        raise AcquisitionFailure("Q1 successor v6 disk requirement failed")
    return result


def _inspect(args, context, target):
    try:
        terminal_key = ("2023-01", "USD_M_PERPETUAL")
        if target.key == terminal_key:
            path = (PROJECT_ROOT / context.protocol.terminal_archive_path).resolve()
            mode, attempts = "REUSED_LOCAL", 0
        elif target.reuse_candidate_path is not None:
            path = verify_reuse_archive(evidence_root=args.evidence_root, target=target)
            mode, attempts = "REUSED_LOCAL", 0
        else:
            _wait_for_dns(context)
            path, attempts = ensure_network_archive_v3(
                root=args.acquisition_root, target=target, context=context
            )
            mode = "NETWORK_ACQUIRED"
        return inspect_archive_v6(
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
            f"Q1 successor v6 archive integrity failed for {target.key}: {exc}"
        ) from exc


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
    result = build_acquisition_result_v6(
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
            for target in (
                targets[(month, "SPOT")],
                targets[(month, "USD_M_PERPETUAL")],
            ):
                active = f"{month}|{target.product}"
                if target.key in by_key:
                    inspection = ArchiveInspection(
                        evidence=by_key[target.key], minute_indexes=frozenset()
                    )
                    inspections[target.product] = inspection
                    if not inspection.evidence.archive_pass:
                        raise ValueError(
                            "Q1 successor v6 incomplete month seeded a failed archive"
                        )
                    continue
                inspection = _inspect(args, context, target)
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
    except (AcquisitionFailure, ValueError) as exc:
        checkpoint = write_checkpoint(args, context, archives, pairs, exclusions)
        return write_result(args, context, checkpoint, active, str(exc))


def parse_args():
    parser = argparse.ArgumentParser(description="Run Q1 successor v6 acquisition.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--run", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument(
        "--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT
    )
    parser.add_argument(
        "--execution-contract-audit",
        type=Path,
        default=DEFAULT_EXECUTION_CONTRACT_AUDIT,
    )
    parser.add_argument("--v5-checkpoint", type=Path, default=DEFAULT_V5_CHECKPOINT)
    parser.add_argument("--v5-result", type=Path, default=DEFAULT_V5_RESULT)
    parser.add_argument(
        "--v5-terminal-audit", type=Path, default=DEFAULT_V5_TERMINAL_AUDIT
    )
    parser.add_argument(
        "--v5-transport-amendment",
        type=Path,
        default=DEFAULT_V5_TRANSPORT_AMENDMENT,
    )
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
                PeriodicFlowSuccessorAcquisitionResultV6.model_validate_json(
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
