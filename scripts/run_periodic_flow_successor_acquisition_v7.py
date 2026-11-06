from __future__ import annotations

import argparse
import json
import shutil
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
from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v6 import (  # noqa: E402
    PeriodicFlowSuccessorTerminalAuditV6,
    audit_successor_terminal_audit_v6,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v5 import (  # noqa: E402
    PeriodicFlowSuccessorTransportAmendmentV5,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v7 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV7,
    PeriodicFlowSuccessorCheckpointV7,
    PeriodicFlowSuccessorExecutionContractAuditV7,
    PeriodicFlowSuccessorExecutionContractV7,
    PeriodicFlowSuccessorTransportAmendmentAuditV7,
    PeriodicFlowSuccessorTransportAmendmentV7,
    audit_hash,
    build_acquisition_result_v7,
    build_checkpoint_v7,
)
from aurex.backtest_engine.periodic_flow_successor_validator_v6 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV6,
    PeriodicFlowSuccessorCheckpointV6,
    PeriodicFlowSuccessorValidatorAmendmentV6,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    AcquisitionFailure,
    ArchiveInspection,
    LoadedContext,
    _write_json_transactional,
    file_sha256,
    pair_month,
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
from scripts.run_periodic_flow_successor_acquisition_v6 import (  # noqa: E402
    MODULE_PATH as V6_MODULE_PATH,
)
from scripts.run_periodic_flow_successor_acquisition_v6 import (  # noqa: E402
    SCRIPT_PATH as V6_SCRIPT_PATH,
)
from scripts.run_periodic_flow_successor_acquisition_v6 import (  # noqa: E402
    V5_MODULE_PATH,
    V5_SCRIPT_PATH,
    ProtocolTransportAdapterV6,
    inspect_archive_v6,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_protocol_audit_v1.json"
)
DEFAULT_VALIDATOR_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_validator_amendment_v6.json"
)
DEFAULT_INHERITED_TRANSPORT_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v5.json"
)
DEFAULT_AMENDMENT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_v7.json"
)
DEFAULT_AMENDMENT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_transport_amendment_audit_v7.json"
)
DEFAULT_EXECUTION_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_v7.json"
)
DEFAULT_EXECUTION_CONTRACT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_execution_contract_audit_v7.json"
)
DEFAULT_V6_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v6.json"
)
DEFAULT_V6_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v6.json"
)
DEFAULT_V6_TERMINAL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v6.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_ACQUISITION_ROOT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_v7"
)
DEFAULT_CHECKPOINT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_checkpoint_v7.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_result_v7.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_successor_transport_v7.py"
)
SCRIPT_PATH = Path("scripts/run_periodic_flow_successor_acquisition_v7.py")


class ProtocolTransportAdapterV7(ProtocolTransportAdapterV6):
    def __init__(self, protocol, validator, inherited_transport, transport):
        super().__init__(protocol, validator, inherited_transport)
        self._v7_transport_amendment = transport

    @property
    def amendment_evidence_hash(self) -> str:
        return self._v7_transport_amendment.amendment_evidence_hash

    @property
    def request_marker_schema(self) -> str:
        return self._v7_transport_amendment.request_marker_schema

    @property
    def response_marker_schema(self) -> str:
        return self._v7_transport_amendment.response_marker_schema

    @property
    def maximum_new_archive_bytes_total(self) -> int:
        return self._v7_transport_amendment.maximum_remaining_payload_bytes

    def __getattr__(self, name: str):
        try:
            return getattr(self._v7_transport_amendment, name)
        except AttributeError:
            return super().__getattr__(name)


def current_runner_source_hash_v7() -> str:
    return source_contract_hash(
        PROJECT_ROOT,
        (
            MODULE_PATH,
            SCRIPT_PATH,
            V6_MODULE_PATH,
            V6_SCRIPT_PATH,
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
    validator = PeriodicFlowSuccessorValidatorAmendmentV6.model_validate_json(
        args.validator_amendment.read_text(encoding="utf-8")
    )
    inherited_transport = PeriodicFlowSuccessorTransportAmendmentV5.model_validate_json(
        args.inherited_transport_amendment.read_text(encoding="utf-8")
    )
    amendment = PeriodicFlowSuccessorTransportAmendmentV7.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    amendment_audit = PeriodicFlowSuccessorTransportAmendmentAuditV7.model_validate_json(
        args.amendment_audit.read_text(encoding="utf-8")
    )
    contract = PeriodicFlowSuccessorExecutionContractV7.model_validate_json(
        args.execution_contract.read_text(encoding="utf-8")
    )
    contract_audit = PeriodicFlowSuccessorExecutionContractAuditV7.model_validate_json(
        args.execution_contract_audit.read_text(encoding="utf-8")
    )
    terminal = PeriodicFlowSuccessorTerminalAuditV6.model_validate_json(
        args.v6_terminal_audit.read_text(encoding="utf-8")
    )
    runner_hash = current_runner_source_hash_v7()
    if (
        not audit_protocol_hash(protocol, "protocol_evidence_hash")
        or not audit_protocol_hash(protocol_audit, "audit_evidence_hash")
        or not audit_hash(amendment, "amendment_evidence_hash")
        or not audit_hash(amendment_audit, "audit_evidence_hash")
        or not audit_hash(contract, "contract_evidence_hash")
        or not audit_hash(contract_audit, "audit_evidence_hash")
        or not audit_successor_terminal_audit_v6(terminal)
        or protocol_audit.protocol_file_sha256 != file_sha256(args.protocol)
        or amendment.parent_protocol_file_sha256 != file_sha256(args.protocol)
        or amendment.parent_v6_validator_amendment_file_sha256
        != file_sha256(args.validator_amendment)
        or amendment.parent_v6_validator_amendment_evidence_hash
        != validator.amendment_evidence_hash
        or amendment_audit.amendment_file_sha256 != file_sha256(args.amendment)
        or contract.amendment_file_sha256 != file_sha256(args.amendment)
        or contract.amendment_audit_file_sha256 != file_sha256(args.amendment_audit)
        or contract.runner_source_hash != runner_hash
        or contract_audit.contract_file_sha256 != file_sha256(args.execution_contract)
        or contract_audit.runner_source_hash != runner_hash
    ):
        raise ValueError("Q1 successor v7 acquisition authority or source changed")
    return LoadedContext(  # type: ignore[arg-type]
        protocol=ProtocolTransportAdapterV7(
            protocol, validator, inherited_transport, amendment
        ),
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
    )


def _seed(args, context):
    checkpoint = PeriodicFlowSuccessorCheckpointV6.model_validate_json(
        args.v6_checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResultV6.model_validate_json(
        args.v6_result.read_text(encoding="utf-8")
    )
    terminal = PeriodicFlowSuccessorTerminalAuditV6.model_validate_json(
        args.v6_terminal_audit.read_text(encoding="utf-8")
    )
    if (
        file_sha256(args.v6_checkpoint)
        != context.contract.seed_v6_checkpoint_file_sha256
        or checkpoint.checkpoint_evidence_hash
        != context.contract.seed_v6_checkpoint_evidence_hash
        or file_sha256(args.v6_result) != context.contract.seed_v6_result_file_sha256
        or result.result_evidence_hash != context.contract.seed_v6_result_evidence_hash
        or file_sha256(args.v6_terminal_audit)
        != context.contract.seed_v6_terminal_audit_file_sha256
        or terminal.audit_evidence_hash
        != context.contract.seed_v6_terminal_audit_evidence_hash
        or len(checkpoint.archive_evidence) != context.contract.seed_archive_count
        or len(checkpoint.paired_month_evidence)
        != context.contract.seed_paired_month_count
        or len(checkpoint.excluded_month_evidence)
        != context.contract.seed_excluded_month_count
        or checkpoint.total_new_archive_bytes
        != context.contract.seed_total_new_archive_bytes
    ):
        raise ValueError("Q1 successor v7 seed lineage changed")
    return checkpoint


def _verify_evidence(evidence_root: Path, evidence) -> Path:
    path = (evidence_root / evidence.local_path).resolve()
    if (
        not path.is_relative_to(evidence_root.resolve())
        or not path.is_file()
        or path.stat().st_size != evidence.archive_bytes
        or file_sha256(path) != evidence.archive_sha256
    ):
        raise ValueError(f"Q1 successor v7 archive changed: {evidence.key}")
    return path


def _build_checkpoint(args, context, archives, pairs, exclusions):
    state = marker_state_v3(args.acquisition_root)
    return build_checkpoint_v7(
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
    checkpoint = PeriodicFlowSuccessorCheckpointV7.model_validate_json(
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
        raise ValueError("Q1 successor v7 checkpoint lineage changed")
    return checkpoint


def write_checkpoint(args, context, archives, pairs, exclusions):
    checkpoint = _build_checkpoint(args, context, archives, pairs, exclusions)
    if checkpoint.request_marker_count != checkpoint.response_marker_count:
        raise ValueError("Q1 successor v7 checkpoint refused unmatched markers")
    _write_json_transactional(
        args.checkpoint, checkpoint.model_dump(mode="json"), overwrite=True
    )
    return checkpoint


def preflight(args, context):
    if args.result.exists():
        raise ValueError("A terminal Q1 successor v7 result already exists")
    seed = _seed(args, context)
    for evidence in seed.archive_evidence:
        _verify_evidence(args.evidence_root, evidence)
    if tuple(args.acquisition_root.rglob("*.part")):
        raise ValueError("Q1 successor v7 root contains an unbound partial")
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
        "seed_total_new_archive_bytes": seed.total_new_archive_bytes,
        "maximum_remaining_payload_bytes": (
            context.contract.maximum_remaining_payload_bytes
        ),
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
        raise AcquisitionFailure("Q1 successor v7 disk requirement failed")
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
            f"Q1 successor v7 archive integrity failed for {target.key}: {exc}"
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
    result = build_acquisition_result_v7(
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
                            "Q1 successor v7 incomplete month seeded a failed archive"
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
    parser = argparse.ArgumentParser(description="Run Q1 successor v7 acquisition.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--run", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument(
        "--validator-amendment", type=Path, default=DEFAULT_VALIDATOR_AMENDMENT
    )
    parser.add_argument(
        "--inherited-transport-amendment",
        type=Path,
        default=DEFAULT_INHERITED_TRANSPORT_AMENDMENT,
    )
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
    parser.add_argument("--v6-checkpoint", type=Path, default=DEFAULT_V6_CHECKPOINT)
    parser.add_argument("--v6-result", type=Path, default=DEFAULT_V6_RESULT)
    parser.add_argument(
        "--v6-terminal-audit", type=Path, default=DEFAULT_V6_TERMINAL_AUDIT
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
                PeriodicFlowSuccessorAcquisitionResultV7.model_validate_json(
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
