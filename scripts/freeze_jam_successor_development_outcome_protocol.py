from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_archive_quality_remediation import (  # noqa: E402
    JamArchiveQualityResult,
    audit_jam_archive_quality_result,
)
from aurex.backtest_engine.jam_successor_development_outcome import (  # noqa: E402
    JamSuccessorDevelopmentOutcomeExecutionProtocol,
    audit_jam_successor_outcome_protocol,
    build_jam_successor_outcome_protocol,
)
from aurex.backtest_engine.jam_successor_distribution_protocol import (  # noqa: E402
    JamSuccessorDevelopmentDistributionProtocol,
    audit_jam_successor_distribution_protocol,
)
from aurex.backtest_engine.jam_successor_distribution_result import (  # noqa: E402
    JamSuccessorDevelopmentDistributionResult,
    audit_jam_successor_distribution_result,
)
from aurex.backtest_engine.jam_successor_event_outcome_protocol import (  # noqa: E402
    JAM_EVENT_PREVALENCE_PASS_NEXT_AUTHORIZATION,
    JamSuccessorEventOutcomeProtocol,
    audit_jam_successor_event_outcome_protocol,
)
from aurex.backtest_engine.jam_successor_event_prevalence import (  # noqa: E402
    JAM_PREVALENCE_NEXT_AUTHORIZATION,
    JAM_PREVALENCE_PASS_DECISION,
    JamDevelopmentEventLedgerRecord,
    JamSuccessorDevelopmentEventPrevalenceAudit,
    JamSuccessorDevelopmentEventPrevalenceProtocol,
    JamSuccessorDevelopmentEventPrevalenceResult,
    audit_jam_successor_prevalence_audit,
    audit_jam_successor_prevalence_protocol,
    audit_jam_successor_prevalence_result,
    validate_event_ledger,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_jam_successor_distribution_protocol import (  # noqa: E402
    development_quarantine,
)

DEFAULT_PARENT_EVENT_PROTOCOL = Path(
    "data/evidence/jam_successor_event_outcome_protocol_v1.json"
)
DEFAULT_PREVALENCE_PROTOCOL = Path(
    "data/evidence/jam_successor_development_event_prevalence_protocol_v1.json"
)
DEFAULT_PREVALENCE_RESULT = Path(
    "data/evidence/jam_successor_development_event_prevalence_result_v1.json"
)
DEFAULT_PREVALENCE_AUDIT = Path(
    "data/evidence/jam_successor_development_event_prevalence_audit_v1.json"
)
DEFAULT_EVENT_LEDGER = Path(
    "data/evidence/jam_successor_development_event_ledger_v1.jsonl"
)
DEFAULT_FEATURE_ROWS = Path(
    "data/evidence/jam_successor_development_feature_rows_v1.parquet"
)
DEFAULT_DISTRIBUTION_PROTOCOL = Path(
    "data/evidence/jam_successor_development_distribution_protocol_v1.json"
)
DEFAULT_DISTRIBUTION_RESULT = Path(
    "data/evidence/jam_successor_development_distribution_result_v1.json"
)
DEFAULT_QUALITY_RESULT = Path(
    "data/evidence/jam_archive_quality_remediation_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_successor_development_outcome_execution_protocol_v1.json"
)

EXPECTED_PARENT_EVENT_PROTOCOL_FILE_SHA256 = (
    "6eaf28df7810a9ebb93a048ded432c27d9d7791fdca6210d84d752e89a1f5081"
)
EXPECTED_PARENT_EVENT_PROTOCOL_EVIDENCE_HASH = (
    "33323ff5864c9dfdeed1b5ddd5dc237ac5a7b7d23d1a1ac484abf75e02ded8db"
)
EXPECTED_PREVALENCE_PROTOCOL_FILE_SHA256 = (
    "336c6e516f4def171cc4fd29a5f82ecfde5971f7883593fd3064a4eee7871119"
)
EXPECTED_PREVALENCE_PROTOCOL_EVIDENCE_HASH = (
    "e43339f5186b5702c6db0d316b236415c5bb02f0bc2cb18d9188f5122adbe0cd"
)
EXPECTED_PREVALENCE_RESULT_FILE_SHA256 = (
    "1bd0d659f7f582899ed7a61928e77bd92383dc8d22e3d5b79f9e178dde1a41d4"
)
EXPECTED_PREVALENCE_RESULT_EVIDENCE_HASH = (
    "444fe28b86c6283181f3e99cfe55258fd4e9136cbca1c92b978cbdfae9ea77ea"
)
EXPECTED_PREVALENCE_AUDIT_FILE_SHA256 = (
    "c93ea38a6418b12e06c26650133457b8926cb0bfb49000168199cb70927c1d77"
)
EXPECTED_PREVALENCE_AUDIT_EVIDENCE_HASH = (
    "414e9affc9e138a38a25c7a3d3432f0672217c9ff3e8707b73147200ea5f544d"
)
EXPECTED_EVENT_LEDGER_FILE_SHA256 = (
    "b6fe0c49bbbb8b61ac268b4716d2a50ab5fa08479ccbf254ef532b15a3b7d909"
)
EXPECTED_FEATURE_ROWS_FILE_SHA256 = (
    "fbb6ee42fca63ea6fe38db093c6c5c5484d2c6997d658d616f09f6fd4c2a0dfa"
)
EXPECTED_FEATURE_ROWS_SCHEMA_HASH = (
    "15995c028cfb437bea77990389eee4e036f9493b106270476ad1ce07cfcc037b"
)
EXPECTED_DISTRIBUTION_PROTOCOL_FILE_SHA256 = (
    "f56eff43ca8868786b55b047041ce3d453ec5cb60ac3754ba1c76dfea03cc6d1"
)
EXPECTED_DISTRIBUTION_PROTOCOL_EVIDENCE_HASH = (
    "8451a456171524092390ce3ef9536032d3d6e3dea1eee4eedc8e70cd014b8551"
)
EXPECTED_DISTRIBUTION_RESULT_FILE_SHA256 = (
    "be5e863b6a12b8d37646a6899cab3ee1b4808d429dac6ceaf53a693926ff8cc8"
)
EXPECTED_DISTRIBUTION_RESULT_EVIDENCE_HASH = (
    "d79092c225bb5cd4ecda603a45f1114f6e7f669c1413e3e36057cdcac72b9eef"
)
EXPECTED_QUALITY_RESULT_FILE_SHA256 = (
    "db1d1321598e07ba24d30aacd8b41cc28af0db186ccf4de7789a5bb2f7b18097"
)
EXPECTED_QUALITY_RESULT_EVIDENCE_HASH = (
    "02a3b8fef4e44995ebc1c0150044f1506e1f805d6c565f86d54bacc227f4f00c"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path)
                for path in paths
            }
        }
    )


def builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_jam_successor_development_outcome_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_successor_development_outcome.py",
        ]
    )


def load_event_ledger(
    path: Path,
) -> list[JamDevelopmentEventLedgerRecord]:
    return [
        JamDevelopmentEventLedgerRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def load_inputs(args) -> tuple:
    parent = JamSuccessorEventOutcomeProtocol.model_validate_json(
        args.parent_event_protocol.read_text(encoding="utf-8")
    )
    prevalence_protocol = (
        JamSuccessorDevelopmentEventPrevalenceProtocol.model_validate_json(
            args.prevalence_protocol.read_text(encoding="utf-8")
        )
    )
    prevalence_result = (
        JamSuccessorDevelopmentEventPrevalenceResult.model_validate_json(
            args.prevalence_result.read_text(encoding="utf-8")
        )
    )
    prevalence_audit = (
        JamSuccessorDevelopmentEventPrevalenceAudit.model_validate_json(
            args.prevalence_audit.read_text(encoding="utf-8")
        )
    )
    distribution_protocol = (
        JamSuccessorDevelopmentDistributionProtocol.model_validate_json(
            args.distribution_protocol.read_text(encoding="utf-8")
        )
    )
    distribution_result = (
        JamSuccessorDevelopmentDistributionResult.model_validate_json(
            args.distribution_result.read_text(encoding="utf-8")
        )
    )
    quality_result = JamArchiveQualityResult.model_validate_json(
        args.quality_result.read_text(encoding="utf-8")
    )
    ledger = load_event_ledger(args.event_ledger)
    validate_event_ledger(
        ledger,
        conditions=parent.event_definition.conditions,
    )
    quarantine = development_quarantine(quality_result)
    if (
        not audit_jam_successor_event_outcome_protocol(parent)
        or not audit_jam_successor_prevalence_protocol(prevalence_protocol)
        or not audit_jam_successor_prevalence_result(prevalence_result)
        or not audit_jam_successor_prevalence_audit(prevalence_audit)
        or not audit_jam_successor_distribution_protocol(distribution_protocol)
        or not audit_jam_successor_distribution_result(distribution_result)
        or not audit_jam_archive_quality_result(quality_result)
        or file_sha256(args.parent_event_protocol)
        != EXPECTED_PARENT_EVENT_PROTOCOL_FILE_SHA256
        or parent.protocol_evidence_hash
        != EXPECTED_PARENT_EVENT_PROTOCOL_EVIDENCE_HASH
        or file_sha256(args.prevalence_protocol)
        != EXPECTED_PREVALENCE_PROTOCOL_FILE_SHA256
        or prevalence_protocol.protocol_evidence_hash
        != EXPECTED_PREVALENCE_PROTOCOL_EVIDENCE_HASH
        or file_sha256(args.prevalence_result)
        != EXPECTED_PREVALENCE_RESULT_FILE_SHA256
        or prevalence_result.result_evidence_hash
        != EXPECTED_PREVALENCE_RESULT_EVIDENCE_HASH
        or file_sha256(args.prevalence_audit)
        != EXPECTED_PREVALENCE_AUDIT_FILE_SHA256
        or prevalence_audit.audit_evidence_hash
        != EXPECTED_PREVALENCE_AUDIT_EVIDENCE_HASH
        or file_sha256(args.event_ledger)
        != EXPECTED_EVENT_LEDGER_FILE_SHA256
        or file_sha256(args.feature_rows)
        != EXPECTED_FEATURE_ROWS_FILE_SHA256
        or file_sha256(args.distribution_protocol)
        != EXPECTED_DISTRIBUTION_PROTOCOL_FILE_SHA256
        or distribution_protocol.protocol_evidence_hash
        != EXPECTED_DISTRIBUTION_PROTOCOL_EVIDENCE_HASH
        or file_sha256(args.distribution_result)
        != EXPECTED_DISTRIBUTION_RESULT_FILE_SHA256
        or distribution_result.result_evidence_hash
        != EXPECTED_DISTRIBUTION_RESULT_EVIDENCE_HASH
        or file_sha256(args.quality_result)
        != EXPECTED_QUALITY_RESULT_FILE_SHA256
        or quality_result.result_evidence_hash
        != EXPECTED_QUALITY_RESULT_EVIDENCE_HASH
        or prevalence_result.decision != JAM_PREVALENCE_PASS_DECISION
        or prevalence_result.next_required_authorization
        != JAM_PREVALENCE_NEXT_AUTHORIZATION
        or parent.prevalence_pass_next_authorization
        != JAM_EVENT_PREVALENCE_PASS_NEXT_AUTHORIZATION
        or prevalence_result.raw_event_count != len(ledger)
        or prevalence_result.accepted_event_count
        != sum(item.accepted for item in ledger)
        or prevalence_result.event_ledger_file_sha256
        != EXPECTED_EVENT_LEDGER_FILE_SHA256
        or prevalence_result.feature_rows_file_sha256
        != EXPECTED_FEATURE_ROWS_FILE_SHA256
        or distribution_result.feature_rows_schema_hash
        != EXPECTED_FEATURE_ROWS_SCHEMA_HASH
        or prevalence_result.sealed_market_periods_opened
        or prevalence_result.future_price_rows_accessed
        or prevalence_result.future_labels_calculated
        or prevalence_result.return_metrics_calculated
        or len(quarantine) != 3_063
        or universe_evidence_hash({"minutes": quarantine})
        != distribution_protocol.development_quarantine_manifest_hash
    ):
        raise ValueError("Jam development outcome parent lineage changed")
    return (
        parent,
        prevalence_protocol,
        prevalence_result,
        prevalence_audit,
        distribution_protocol,
        distribution_result,
        quality_result,
        ledger,
        quarantine,
    )


def authoritative_protocol(
    *,
    frozen_at: datetime,
    inputs: tuple,
    args,
) -> JamSuccessorDevelopmentOutcomeExecutionProtocol:
    parent = inputs[0]
    prevalence_protocol = inputs[1]
    prevalence_result = inputs[2]
    prevalence_audit = inputs[3]
    distribution_protocol = inputs[4]
    distribution_result = inputs[5]
    quality_result = inputs[6]
    activity_metric = next(
        item
        for item in distribution_result.feature_distributions
        if item.feature_id == "baseline_sell_quote_median_120m"
    )
    return build_jam_successor_outcome_protocol(
        frozen_at=frozen_at,
        parent_event_protocol_path=args.parent_event_protocol.as_posix(),
        parent_event_protocol_file_sha256=file_sha256(
            args.parent_event_protocol
        ),
        parent_event_protocol_evidence_hash=parent.protocol_evidence_hash,
        prevalence_protocol_path=args.prevalence_protocol.as_posix(),
        prevalence_protocol_file_sha256=file_sha256(args.prevalence_protocol),
        prevalence_protocol_evidence_hash=(
            prevalence_protocol.protocol_evidence_hash
        ),
        prevalence_result_path=args.prevalence_result.as_posix(),
        prevalence_result_file_sha256=file_sha256(args.prevalence_result),
        prevalence_result_evidence_hash=prevalence_result.result_evidence_hash,
        prevalence_audit_path=args.prevalence_audit.as_posix(),
        prevalence_audit_file_sha256=file_sha256(args.prevalence_audit),
        prevalence_audit_evidence_hash=prevalence_audit.audit_evidence_hash,
        event_ledger_path=args.event_ledger.as_posix(),
        event_ledger_file_sha256=file_sha256(args.event_ledger),
        feature_rows_path=args.feature_rows.as_posix(),
        feature_rows_file_sha256=prevalence_result.feature_rows_file_sha256,
        feature_rows_schema_hash=prevalence_result.feature_rows_schema_hash,
        distribution_protocol_path=args.distribution_protocol.as_posix(),
        distribution_protocol_file_sha256=file_sha256(
            args.distribution_protocol
        ),
        distribution_protocol_evidence_hash=(
            distribution_protocol.protocol_evidence_hash
        ),
        distribution_result_path=args.distribution_result.as_posix(),
        distribution_result_file_sha256=file_sha256(args.distribution_result),
        distribution_result_evidence_hash=distribution_result.result_evidence_hash,
        quality_result_path=args.quality_result.as_posix(),
        quality_result_file_sha256=file_sha256(args.quality_result),
        quality_result_evidence_hash=quality_result.result_evidence_hash,
        development_quarantine_manifest_hash=(
            distribution_protocol.development_quarantine_manifest_hash
        ),
        archive_targets=distribution_protocol.archive_targets,
        archive_target_manifest_hash=(
            distribution_protocol.archive_target_manifest_hash
        ),
        activity_q25=activity_metric.quantiles["0.25"],
        activity_q50=activity_metric.quantiles["0.5"],
        activity_q75=activity_metric.quantiles["0.75"],
        builder_contract_hash=builder_contract_hash(),
        limitations=[
            (
                "This protocol is frozen after development event prevalence but "
                "before any post-event aggregate-trade price is opened."
            ),
            (
                "Only the 991 accepted 2019-2020 events and deterministic matched "
                "controls may receive outcomes."
            ),
            (
                "Raw event thresholds, direction, suppression, horizons, costs, "
                "controls, inference, and gates cannot change."
            ),
            (
                "Controls use causal features and timestamps only; no future "
                "price or outcome may affect matching."
            ),
            (
                "All raw event minutes are excluded from control eligibility."
            ),
            (
                "Control candidates must be at least 1,440 minutes from every "
                "accepted event; exactly 1,440 minutes is permitted."
            ),
            (
                "Selected controls are unique and separated from each other by "
                "at least 60 minutes."
            ),
            (
                "A complete non-quarantined aggregate-trade minute path is "
                "required independently for each horizon."
            ),
            (
                "Unavailable diagnostics cannot disqualify or rescue an available "
                "primary outcome."
            ),
            (
                "No minute or price may be synthesized, forward-filled, or "
                "replaced by a kline value."
            ),
            (
                "Per-subject returns are rounded once to 18 decimal places before "
                "all aggregate metrics."
            ),
            (
                "The primary profit factor uses gross positive return divided by "
                "absolute gross negative return."
            ),
            (
                "Matched excess is the event base-cost return minus its selected "
                "control base-cost return at 30 minutes."
            ),
            (
                "Month concentration uses each month's sum of absolute individual "
                "event returns divided by the total absolute individual returns."
            ),
            (
                "Bootstrap month draws are deterministic SHA-256 counter draws "
                "and the lower bound is the 500th sorted replicate without "
                "interpolation."
            ),
            (
                "All eleven development gates are conjunctive and unwaivable."
            ),
            (
                "A failed development decision retires this event definition; no "
                "threshold or diagnostic rescue is permitted."
            ),
            (
                "A passing development decision still requires separate explicit "
                "authorization before opening sealed 2021 validation."
            ),
            (
                "The 2021 validation and 2022 holdout archives remain sealed."
            ),
            (
                "This stage creates no strategy, signal, candidate, paper "
                "eligibility, Testnet strategy order, production, or live "
                "authority."
            ),
            (
                "Exact Pine parity remains unavailable because the event depends "
                "on aggregate-trade aggressor identity."
            ),
            (
                "Real capital remains disabled and historical development returns "
                "are not real profit."
            ),
        ],
    )


def write_protocol(
    path: Path,
    protocol: JamSuccessorDevelopmentOutcomeExecutionProtocol,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if (
        JamSuccessorDevelopmentOutcomeExecutionProtocol.model_validate_json(
            serialized
        )
        != protocol
    ):
        raise ValueError("Jam outcome execution protocol did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def run_freeze(args) -> JamSuccessorDevelopmentOutcomeExecutionProtocol:
    if args.output.exists():
        raise ValueError("Jam outcome execution protocol exists; use --check")
    inputs = load_inputs(args)
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        inputs=inputs,
        args=args,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        "market_values=0 labels=0 returns=0 validation=False holdout=False",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> JamSuccessorDevelopmentOutcomeExecutionProtocol:
    inputs = load_inputs(args)
    protocol = JamSuccessorDevelopmentOutcomeExecutionProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        inputs=inputs,
        args=args,
    )
    if protocol != expected or not audit_jam_successor_outcome_protocol(protocol):
        raise ValueError("Jam outcome execution protocol is not reproducible")
    print(
        "PASS "
        f"jam_outcome_protocol={protocol.protocol_evidence_hash} "
        "events=991 horizons=15,30,60 gates=11 "
        "market_values=0 labels=0 returns=0",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze exact Jam successor development outcome execution and "
            "inference semantics before opening a post-event price."
        )
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--parent-event-protocol",
        type=Path,
        default=DEFAULT_PARENT_EVENT_PROTOCOL,
    )
    parser.add_argument(
        "--prevalence-protocol",
        type=Path,
        default=DEFAULT_PREVALENCE_PROTOCOL,
    )
    parser.add_argument(
        "--prevalence-result",
        type=Path,
        default=DEFAULT_PREVALENCE_RESULT,
    )
    parser.add_argument(
        "--prevalence-audit",
        type=Path,
        default=DEFAULT_PREVALENCE_AUDIT,
    )
    parser.add_argument(
        "--event-ledger",
        type=Path,
        default=DEFAULT_EVENT_LEDGER,
    )
    parser.add_argument(
        "--feature-rows",
        type=Path,
        default=DEFAULT_FEATURE_ROWS,
    )
    parser.add_argument(
        "--distribution-protocol",
        type=Path,
        default=DEFAULT_DISTRIBUTION_PROTOCOL,
    )
    parser.add_argument(
        "--distribution-result",
        type=Path,
        default=DEFAULT_DISTRIBUTION_RESULT,
    )
    parser.add_argument(
        "--quality-result",
        type=Path,
        default=DEFAULT_QUALITY_RESULT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            run_check(args)
        else:
            run_freeze(args)
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
