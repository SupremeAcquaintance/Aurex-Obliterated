from __future__ import annotations

import argparse
import configparser
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_accepted_development_measurement_execution import (  # noqa: E402
    S5AcceptedDevelopmentMeasurementExecutionContractAuditV1,
    S5AcceptedDevelopmentMeasurementExecutionContractV1,
    S5AcceptedDevelopmentMeasurementResultV1,
)
from aurex.backtest_engine.s5_accepted_development_measurement_protocol import (  # noqa: E402
    S5AcceptedDevelopmentMeasurementProtocolAuditV1,
    S5AcceptedDevelopmentMeasurementProtocolV1,
)
from aurex.backtest_engine.s5_accepted_development_measurement_result_audit import (  # noqa: E402
    S5_MEASUREMENT_AUDIT_NEXT,
    S5_MEASUREMENT_AUDIT_REJECT,
    S5AcceptedDevelopmentMeasurementResultAuditV1,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.s5_release_tag_source_remediation import (  # noqa: E402
    S5_RELEASE_REMEDIATION_GATES,
    S5ReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_release_tag_source_remediation_protocol_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_release_tag_source_remediation.py"
)
MEASUREMENT_PROTOCOL_PATH = Path(
    "data/evidence/s5_accepted_development_measurement_protocol_v1.json"
)
MEASUREMENT_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_accepted_development_measurement_protocol_audit_v1.json"
)
MEASUREMENT_EXECUTION_PATH = Path(
    "data/evidence/s5_accepted_development_measurement_execution_contract_v1.json"
)
MEASUREMENT_EXECUTION_AUDIT_PATH = Path(
    "data/evidence/s5_accepted_development_measurement_execution_contract_audit_v1.json"
)
MEASUREMENT_RESULT_PATH = Path(
    "data/evidence/s5_accepted_development_measurement_result_v1.json"
)
MEASUREMENT_ROWS_PATH = Path(
    "data/evidence/s5_accepted_development_monthly_measurements_v1.jsonl"
)
MEASUREMENT_RESULT_AUDIT_PATH = Path(
    "data/evidence/s5_accepted_development_measurement_result_audit_v1.json"
)
HISTORY_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_result_v2.json"
)
HISTORY_RESULT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_result_audit_v2.json"
)
REPOSITORY_CONFIG_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_v1.git/config"
)
REPOSITORY_PACKED_REFS_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_payload_v1.git/packed-refs"
)
SOURCE_PATHS = tuple(
    sorted(
        (
            MEASUREMENT_PROTOCOL_PATH,
            MEASUREMENT_PROTOCOL_AUDIT_PATH,
            MEASUREMENT_EXECUTION_PATH,
            MEASUREMENT_EXECUTION_AUDIT_PATH,
            MEASUREMENT_RESULT_PATH,
            MEASUREMENT_ROWS_PATH,
            MEASUREMENT_RESULT_AUDIT_PATH,
            HISTORY_RESULT_PATH,
            HISTORY_RESULT_AUDIT_PATH,
            REPOSITORY_CONFIG_PATH,
            REPOSITORY_PACKED_REFS_PATH,
        ),
        key=lambda path: path.as_posix(),
    )
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build_hashed[ModelT: BaseModel](
    model: type[ModelT],
    hash_field: str,
    values: dict,
) -> ModelT:
    payload = dict(values)
    payload[hash_field] = "0" * 64
    preliminary = model.model_construct(**payload)
    payload[hash_field] = universe_evidence_hash(
        preliminary.model_dump(mode="json", exclude={hash_field})
    )
    return model.model_validate(payload)


def builder_contract_hash() -> str:
    paths = tuple(
        sorted(
            (MODULE_PATH, Path(__file__).resolve().relative_to(PROJECT_ROOT)),
            key=lambda path: path.as_posix(),
        )
    )
    bindings = tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in paths
    )
    return universe_evidence_hash(
        tuple(item.model_dump(mode="json") for item in bindings)
    )


def source_bindings() -> tuple[S5HistoryBinding, ...]:
    if len(SOURCE_PATHS) != 11 or not all(path.is_file() for path in SOURCE_PATHS):
        raise ValueError("S5 release remediation source set is incomplete")
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in SOURCE_PATHS
    )


def repository_has_no_tags() -> bool:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    with REPOSITORY_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        parser.read_file(handle)
    if parser.get('remote "origin"', "tagOpt", fallback="") != "--no-tags":
        return False
    refs = tuple(
        line.split(" ", maxsplit=1)[1]
        for line in REPOSITORY_PACKED_REFS_PATH.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith(("#", "^"))
    )
    return refs == ("refs/heads/master",)


def load_lineage() -> tuple[
    S5AcceptedDevelopmentMeasurementProtocolV1,
    S5AcceptedDevelopmentMeasurementProtocolAuditV1,
    S5AcceptedDevelopmentMeasurementExecutionContractV1,
    S5AcceptedDevelopmentMeasurementExecutionContractAuditV1,
    S5AcceptedDevelopmentMeasurementResultV1,
    S5AcceptedDevelopmentMeasurementResultAuditV1,
]:
    protocol = S5AcceptedDevelopmentMeasurementProtocolV1.model_validate_json(
        MEASUREMENT_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S5AcceptedDevelopmentMeasurementProtocolAuditV1.model_validate_json(
        MEASUREMENT_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    execution = S5AcceptedDevelopmentMeasurementExecutionContractV1.model_validate_json(
        MEASUREMENT_EXECUTION_PATH.read_text(encoding="utf-8")
    )
    execution_audit = (
        S5AcceptedDevelopmentMeasurementExecutionContractAuditV1.model_validate_json(
            MEASUREMENT_EXECUTION_AUDIT_PATH.read_text(encoding="utf-8")
        )
    )
    result = S5AcceptedDevelopmentMeasurementResultV1.model_validate_json(
        MEASUREMENT_RESULT_PATH.read_text(encoding="utf-8")
    )
    result_audit = S5AcceptedDevelopmentMeasurementResultAuditV1.model_validate_json(
        MEASUREMENT_RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    if (
        protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or execution.protocol_evidence_hash != protocol.protocol_evidence_hash
        or execution_audit.contract_evidence_hash != execution.contract_evidence_hash
        or result.execution_contract_evidence_hash != execution.contract_evidence_hash
        or result_audit.result_evidence_hash != result.result_evidence_hash
        or result_audit.decision != S5_MEASUREMENT_AUDIT_REJECT
        or result_audit.next_authorization != S5_MEASUREMENT_AUDIT_NEXT
        or result_audit.nominal_result_pass_upheld
        or result_audit.release_measurement_fields_valid
        or not repository_has_no_tags()
    ):
        raise ValueError("S5 release remediation predecessor lineage changed")
    return protocol, protocol_audit, execution, execution_audit, result, result_audit


def build_protocol(*, frozen_at: datetime) -> S5ReleaseTagSourceRemediationProtocolV1:
    _, _, _, _, result, result_audit = load_lineage()
    bindings = source_bindings()
    values = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "source_bindings": bindings,
        "source_binding_manifest_evidence_hash": universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in bindings)
        ),
        "rejected_measurement_result_evidence_hash": result.result_evidence_hash,
        "rejection_audit_evidence_hash": result_audit.audit_evidence_hash,
        "original_repository_config_file_sha256": file_sha256(
            REPOSITORY_CONFIG_PATH
        ),
        "original_repository_packed_refs_file_sha256": file_sha256(
            REPOSITORY_PACKED_REFS_PATH
        ),
        "required_gate_ids": S5_RELEASE_REMEDIATION_GATES,
        "limitations": tuple(
            sorted(
                (
                    "The official remote may change after discovery; any drift stops the run.",
                    "Git tag presence does not prove signer identity or signature validity.",
                    "Only stable-name tags reachable from the frozen cutoff are eligible.",
                    "The copied repository is a remediation dataset, not a replacement source.",
                    "The original no-tags repository and rejected measurement remain immutable.",
                    "Tag acquisition can repair missing release metadata but cannot prove edge.",
                    "No BTC value or return may be read during remediation.",
                    "No threshold, strategy rule, candidate, or signal may be created.",
                    "A successful run authorizes only an amended measurement protocol.",
                    "Network availability and remote stability are not guaranteed.",
                    "Production, live trading, and real capital remain prohibited.",
                    "Qualified strategies and real net profit remain zero.",
                )
            )
        ),
    }
    return build_hashed(
        S5ReleaseTagSourceRemediationProtocolV1,
        "protocol_evidence_hash",
        values,
    )


def write_protocol(path: Path, protocol: S5ReleaseTagSourceRemediationProtocolV1) -> None:
    if path.exists():
        raise ValueError(f"S5 release remediation protocol already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5ReleaseTagSourceRemediationProtocolV1.model_validate_json(serialized) != protocol:
        raise ValueError("S5 release remediation protocol did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the S5 release-tag source remediation protocol."
    )
    parser.add_argument("--freeze", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        protocol = build_protocol(frozen_at=datetime.now(UTC))
        protected_paths = (
            Path(protocol.destination_history_dataset_path),
            Path(protocol.transcript_directory),
            Path(protocol.result_path),
        )
        if any(path.exists() for path in protected_paths):
            raise ValueError("S5 release remediation destination already exists")
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "discovery=0 copies=0 fetches=0 network=0 market_values=0 returns=0 "
            "candidates=0 signals=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
