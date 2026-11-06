import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_v3_discovery_charter import (
    V3MechanismDiscoveryCharter,
    audit_v3_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_v3_p02_aggtrades_census import (
    V3P02AggTradesCensusContract,
    V3P02AggTradesCensusResult,
    audit_v3_p02_census_contract,
    audit_v3_p02_census_result,
)
from aurex.backtest_engine.research_v3_p02_payload_pilot import (
    V3_P02_FULL_COHORT_SYMBOLS,
    V3_P02_SAMPLE_KEYS,
    V3P02PayloadPilotProtocol,
    V3P02PayloadTarget,
    audit_v3_p02_payload_pilot_protocol,
    build_v3_p02_payload_pilot_protocol,
)
from aurex.backtest_engine.research_v3_proposal_register import (
    V3MechanismProposalRegister,
    audit_v3_mechanism_proposal_register,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHARTER = Path(
    "data/evidence/v3_mechanism_discovery_charter_v1.json"
)
DEFAULT_REGISTER = Path(
    "data/evidence/v3_mechanism_proposal_register_v1.json"
)
DEFAULT_CENSUS_CONTRACT = Path(
    "data/evidence/v3_p02_aggtrades_census_contract_v1.json"
)
DEFAULT_CENSUS_RESULT = Path(
    "data/evidence/v3_p02_aggtrades_census_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_p02_payload_pilot_protocol_v1.json"
)


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_v3_p02_payload_pilot_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_payload_pilot.py",
        ]
    )


def charter_builder_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_v3_discovery_charter.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_discovery_charter.py",
        ]
    )


def register_builder_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_v3_proposal_register.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_proposal_register.py",
        ]
    )


def census_builder_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_v3_p02_aggtrades_census_contract.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_aggtrades_census.py",
        ]
    )


def census_runner_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v3_p02_aggtrades_census.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_aggtrades_census.py",
        ]
    )


def load_inputs(
    args,
) -> tuple[
    V3MechanismDiscoveryCharter,
    V3MechanismProposalRegister,
    V3P02AggTradesCensusContract,
    V3P02AggTradesCensusResult,
]:
    charter = V3MechanismDiscoveryCharter.model_validate_json(
        args.charter.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_discovery_charter(charter)
        or charter.builder_contract_hash != charter_builder_hash()
    ):
        raise ValueError("V3 discovery charter audit failed")

    register = V3MechanismProposalRegister.model_validate_json(
        args.register.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_proposal_register(register)
        or register.builder_contract_hash != register_builder_hash()
        or register.discovery_charter_evidence_hash
        != charter.charter_evidence_hash
    ):
        raise ValueError("V3 proposal register audit failed")

    contract = V3P02AggTradesCensusContract.model_validate_json(
        args.census_contract.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p02_census_contract(contract)
        or contract.builder_contract_hash != census_builder_hash()
        or contract.discovery_charter_evidence_hash
        != charter.charter_evidence_hash
        or contract.proposal_register_evidence_hash
        != register.register_evidence_hash
    ):
        raise ValueError("V3P02 census contract audit failed")

    result = V3P02AggTradesCensusResult.model_validate_json(
        args.census_result.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p02_census_result(result)
        or result.contract_evidence_hash != contract.contract_evidence_hash
        or result.target_manifest_hash != contract.target_manifest_hash
        or result.runner_contract_hash != census_runner_hash()
        or result.summary.present_count != 744
        or result.summary.complete_symbol_count != 31
        or not result.authorizes_separate_pilot_protocol
        or result.archive_payload_requests_made != 0
        or result.market_numeric_values_inspected
        or result.return_metrics_calculated
    ):
        raise ValueError("V3P02 census result audit failed")
    return charter, register, contract, result


def payload_targets(
    result: V3P02AggTradesCensusResult,
) -> list[V3P02PayloadTarget]:
    targets = []
    for record in result.records:
        if record.availability != "PRESENT" or record.checksum_sha256 is None:
            raise ValueError(
                f"V3P02 payload target lacks a checksum: {record.key}"
            )
        targets.append(
            V3P02PayloadTarget(
                symbol=record.symbol,
                month=record.month,
                archive_url=record.archive_url,
                checksum_sha256=record.checksum_sha256,
                sample_payload=record.key in V3_P02_SAMPLE_KEYS,
                full_cohort=record.symbol in V3_P02_FULL_COHORT_SYMBOLS,
            )
        )
    return targets


def authoritative_protocol(
    *,
    frozen_at: datetime,
    charter: V3MechanismDiscoveryCharter,
    register: V3MechanismProposalRegister,
    census_contract: V3P02AggTradesCensusContract,
    census_result: V3P02AggTradesCensusResult,
) -> V3P02PayloadPilotProtocol:
    return build_v3_p02_payload_pilot_protocol(
        frozen_at=frozen_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        proposal_register_evidence_hash=register.register_evidence_hash,
        census_contract_evidence_hash=census_contract.contract_evidence_hash,
        census_result_evidence_hash=census_result.result_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        targets=payload_targets(census_result),
        limitations=[
            (
                "The pilot may inspect archive identity, compressed size, ZIP/CSV "
                "structure, aggregate-trade IDs, and timestamps only."
            ),
            (
                "Price, quantity, maker side, signals, trades, PnL, and returns are "
                "forbidden and are not needed for this feasibility decision."
            ),
            (
                "The 744 HEAD requests estimate storage from source metadata; they "
                "do not prove future availability or uncompressed storage needs."
            ),
            (
                "Only three deterministic archives may be downloaded, checksum "
                "verified, retained, and structurally inspected."
            ),
            (
                "Minute coverage and aggregate-trade ID continuity are source "
                "quality checks, not evidence of predictive edge."
            ),
            (
                "The deterministic ten-symbol cohort is a future acquisition scope, "
                "not a selected strategy universe or profitable portfolio."
            ),
            (
                "A passing pilot permits only a separately frozen ten-symbol full "
                "payload protocol and grants no candidate, validation, holdout, "
                "forward, Pine, paper, sandbox, live, or capital permission."
            ),
        ],
    )


def write_protocol(
    path: Path,
    protocol: V3P02PayloadPilotProtocol,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if V3P02PayloadPilotProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("V3P02 payload pilot protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V3P02PayloadPilotProtocol:
    if args.output.exists():
        raise ValueError("Frozen V3P02 payload protocol exists; use --check")
    charter, register, census_contract, census_result = load_inputs(args)
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        charter=charter,
        register=register,
        census_contract=census_contract,
        census_result=census_result,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        f"heads={len(protocol.targets)} samples={len(protocol.sample_keys)}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V3P02PayloadPilotProtocol:
    charter, register, census_contract, census_result = load_inputs(args)
    protocol = V3P02PayloadPilotProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        charter=charter,
        register=register,
        census_contract=census_contract,
        census_result=census_result,
    )
    if protocol != expected:
        raise ValueError("V3P02 payload pilot protocol is not reproducible")
    if not audit_v3_p02_payload_pilot_protocol(protocol):
        raise ValueError("V3P02 payload pilot protocol hash audit failed")
    print(
        "PASS "
        f"v3p02_payload_protocol={protocol.protocol_evidence_hash} "
        f"heads={len(protocol.targets)} samples={len(protocol.sample_keys)} "
        f"columns={protocol.expected_column_count} "
        f"returns={protocol.return_calculation_permitted}",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the no-return V3P02 aggregate-trade payload pilot."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument(
        "--census-contract",
        type=Path,
        default=DEFAULT_CENSUS_CONTRACT,
    )
    parser.add_argument(
        "--census-result",
        type=Path,
        default=DEFAULT_CENSUS_RESULT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
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
