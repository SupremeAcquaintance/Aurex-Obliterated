from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_successor_event_outcome_protocol import (  # noqa: E402
    JAM_EVENT_OUTCOME_DECISION,
    JAM_EVENT_OUTCOME_NEXT_AUTHORIZATION,
    JamSuccessorEventOutcomeProtocol,
    JamSuccessorEventOutcomeProtocolAudit,
    audit_jam_successor_event_outcome_audit,
    audit_jam_successor_event_outcome_protocol,
)
from aurex.backtest_engine.jam_successor_event_prevalence import (  # noqa: E402
    JamSuccessorDevelopmentEventPrevalenceProtocol,
    audit_jam_successor_prevalence_protocol,
    build_jam_successor_prevalence_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PARENT_PROTOCOL = Path(
    "data/evidence/jam_successor_event_outcome_protocol_v1.json"
)
DEFAULT_PARENT_AUDIT = Path(
    "data/evidence/jam_successor_event_outcome_protocol_audit_v1.json"
)
DEFAULT_FEATURE_ROWS = Path(
    "data/evidence/jam_successor_development_feature_rows_v1.parquet"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_successor_development_event_prevalence_protocol_v1.json"
)

EXPECTED_PARENT_PROTOCOL_FILE_SHA256 = (
    "6eaf28df7810a9ebb93a048ded432c27d9d7791fdca6210d84d752e89a1f5081"
)
EXPECTED_PARENT_PROTOCOL_EVIDENCE_HASH = (
    "33323ff5864c9dfdeed1b5ddd5dc237ac5a7b7d23d1a1ac484abf75e02ded8db"
)
EXPECTED_PARENT_AUDIT_FILE_SHA256 = (
    "24f292d0441dcaf2128530b51d84cfd535f960430bb8df01c7641c64c75e0281"
)
EXPECTED_PARENT_AUDIT_EVIDENCE_HASH = (
    "b2236b02b9e3bbbf495bf66f9d862f446a29ae4bf3a9422d495bd8f0501f80e4"
)
EXPECTED_FEATURE_ROWS_FILE_SHA256 = (
    "fbb6ee42fca63ea6fe38db093c6c5c5484d2c6997d658d616f09f6fd4c2a0dfa"
)
EXPECTED_FEATURE_ROWS_SCHEMA_HASH = (
    "15995c028cfb437bea77990389eee4e036f9493b106270476ad1ce07cfcc037b"
)
EXPECTED_FEATURE_ROWS_BYTES = 129_887_758


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
            / "freeze_jam_successor_event_prevalence_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_successor_event_prevalence.py",
        ]
    )


def load_inputs(
    *,
    parent_protocol_path: Path,
    parent_audit_path: Path,
    feature_rows_path: Path,
) -> tuple[
    JamSuccessorEventOutcomeProtocol,
    JamSuccessorEventOutcomeProtocolAudit,
]:
    parent = JamSuccessorEventOutcomeProtocol.model_validate_json(
        parent_protocol_path.read_text(encoding="utf-8")
    )
    parent_audit = JamSuccessorEventOutcomeProtocolAudit.model_validate_json(
        parent_audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_successor_event_outcome_protocol(parent)
        or not audit_jam_successor_event_outcome_audit(parent_audit)
        or file_sha256(parent_protocol_path)
        != EXPECTED_PARENT_PROTOCOL_FILE_SHA256
        or parent.protocol_evidence_hash
        != EXPECTED_PARENT_PROTOCOL_EVIDENCE_HASH
        or file_sha256(parent_audit_path) != EXPECTED_PARENT_AUDIT_FILE_SHA256
        or parent_audit.audit_evidence_hash
        != EXPECTED_PARENT_AUDIT_EVIDENCE_HASH
        or parent_audit.protocol_evidence_hash != parent.protocol_evidence_hash
        or file_sha256(feature_rows_path) != EXPECTED_FEATURE_ROWS_FILE_SHA256
        or feature_rows_path.stat().st_size != EXPECTED_FEATURE_ROWS_BYTES
        or parent.feature_rows_file_sha256 != EXPECTED_FEATURE_ROWS_FILE_SHA256
        or parent.feature_rows_schema_hash != EXPECTED_FEATURE_ROWS_SCHEMA_HASH
        or parent.feature_rows_bytes != EXPECTED_FEATURE_ROWS_BYTES
        or parent.decision != JAM_EVENT_OUTCOME_DECISION
        or parent.next_required_authorization
        != JAM_EVENT_OUTCOME_NEXT_AUTHORIZATION
        or parent.event_flags_calculated
        or parent.accepted_events_calculated
        or parent.future_labels_calculated
        or parent.return_metrics_calculated
        or parent.strategy_executions
    ):
        raise ValueError("Jam prevalence parent lineage changed")
    return parent, parent_audit


def authoritative_protocol(
    *,
    frozen_at: datetime,
    inputs: tuple,
    parent_protocol_path: Path,
    parent_audit_path: Path,
    feature_rows_path: Path,
) -> JamSuccessorDevelopmentEventPrevalenceProtocol:
    parent = inputs[0]
    parent_audit = inputs[1]
    return build_jam_successor_prevalence_protocol(
        frozen_at=frozen_at,
        parent_event_protocol_path=parent_protocol_path.as_posix(),
        parent_event_protocol_file_sha256=file_sha256(parent_protocol_path),
        parent_event_protocol_evidence_hash=parent.protocol_evidence_hash,
        parent_event_audit_path=parent_audit_path.as_posix(),
        parent_event_audit_file_sha256=file_sha256(parent_audit_path),
        parent_event_audit_evidence_hash=parent_audit.audit_evidence_hash,
        feature_rows_path=feature_rows_path.as_posix(),
        feature_rows_file_sha256=parent.feature_rows_file_sha256,
        feature_rows_schema_hash=parent.feature_rows_schema_hash,
        feature_rows_bytes=parent.feature_rows_bytes,
        event_conditions=parent.event_definition.conditions,
        builder_contract_hash=builder_contract_hash(),
        limitations=[
            (
                "This protocol permits only event-predicate evaluation on the "
                "frozen 2019-2020 causal feature rows."
            ),
            (
                "All five conditions and all seven prevalence gates are inherited "
                "unchanged from the frozen parent protocol."
            ),
            (
                "Every raw event is retained in a deterministic ledger with "
                "accepted or suppressed status."
            ),
            (
                "Suppression is chronological across the complete development "
                "partition and does not reset by month or year."
            ),
            (
                "Accepted events must be separated by at least sixty complete "
                "minutes."
            ),
            (
                "Only counts, rates, calendar buckets, concentration, and gate "
                "decisions may be calculated."
            ),
            (
                "No aggregate-trade row, future price, future label, return, path, "
                "or matched-control outcome may be opened."
            ),
            (
                "The sealed 2021 validation and 2022 holdout partitions remain "
                "closed."
            ),
            (
                "A failed prevalence gate retires the event definition; thresholds "
                "cannot be relaxed or replaced."
            ),
            (
                "A passing prevalence result grants no outcome, strategy, signal, "
                "paper, Testnet-order, production, or live authority."
            ),
            (
                "Outcome calculation requires the separately recorded next "
                "authorization and the unchanged protocol lineage."
            ),
            (
                "Exact Pine parity remains unavailable because the event depends "
                "on aggregate-trade aggressor identity."
            ),
            (
                "This stage produces no economic evidence and real net profit "
                "remains zero."
            ),
        ],
    )


def write_protocol(
    path: Path,
    protocol: JamSuccessorDevelopmentEventPrevalenceProtocol,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if (
        JamSuccessorDevelopmentEventPrevalenceProtocol.model_validate_json(
            serialized
        )
        != protocol
    ):
        raise ValueError("Jam prevalence protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def input_args(args) -> tuple:
    return load_inputs(
        parent_protocol_path=args.parent_protocol,
        parent_audit_path=args.parent_audit,
        feature_rows_path=args.feature_rows,
    )


def run_freeze(args) -> JamSuccessorDevelopmentEventPrevalenceProtocol:
    if args.output.exists():
        raise ValueError("Jam prevalence protocol exists; use --check")
    inputs = input_args(args)
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        inputs=inputs,
        parent_protocol_path=args.parent_protocol,
        parent_audit_path=args.parent_audit,
        feature_rows_path=args.feature_rows,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        "events=0 labels=0 returns=0 validation=False holdout=False",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> JamSuccessorDevelopmentEventPrevalenceProtocol:
    inputs = input_args(args)
    protocol = JamSuccessorDevelopmentEventPrevalenceProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        inputs=inputs,
        parent_protocol_path=args.parent_protocol,
        parent_audit_path=args.parent_audit,
        feature_rows_path=args.feature_rows,
    )
    if protocol != expected or not audit_jam_successor_prevalence_protocol(
        protocol
    ):
        raise ValueError("Jam prevalence protocol is not reproducible")
    print(
        "PASS "
        f"jam_prevalence_protocol={protocol.protocol_evidence_hash} "
        f"conditions={len(protocol.event_conditions)} "
        f"gates={len(protocol.prevalence_gates)} "
        "events=0 labels=0 returns=0",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze the Jam successor 2019-2020 development event-prevalence "
            "protocol without calculating an event, label, or return."
        )
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--parent-protocol",
        type=Path,
        default=DEFAULT_PARENT_PROTOCOL,
    )
    parser.add_argument(
        "--parent-audit",
        type=Path,
        default=DEFAULT_PARENT_AUDIT,
    )
    parser.add_argument(
        "--feature-rows",
        type=Path,
        default=DEFAULT_FEATURE_ROWS,
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
