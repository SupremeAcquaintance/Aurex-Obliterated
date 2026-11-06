# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (
    S5GitHubBulkAcquisitionProtocol,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_pagination import (
    S5_GITHUB_BULK_MONOTONIC_NEXT,
    S5GitHubBulkMonotonicTerminalAmendmentAuditV4,
    S5GitHubBulkMonotonicTerminalAmendmentV4,
    evidence_hash_valid,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts import run_s5_bitcoin_core_github_bulk_acquisition as base
from scripts.audit_s5_bitcoin_core_github_bulk_terminal_drift_failure_v3 import (
    SCRIPT_PATH as DRIFT_AUDITOR_PATH,
    observation_from_failure,
)
from scripts.freeze_s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4 import (
    FAILURE_ARTIFACT_PATH,
    MODULE_PATH,
    PROTOCOL_PATH,
    build_amendment,
    builder_contract_hash,
)
from scripts.run_s1_btc_source_acquisition import file_sha256

DEFAULT_AMENDMENT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_audit_v4.json"
)
SCRIPT_PATH = Path(
    "scripts/audit_s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4.py"
)


def auditor_contract_hash() -> str:
    paths = (MODULE_PATH, DRIFT_AUDITOR_PATH, SCRIPT_PATH)
    return universe_evidence_hash(
        {
            "sources": tuple(
                {"path": path.as_posix(), "file_sha256": file_sha256(PROJECT_ROOT / path)}
                for path in paths
            )
        }
    )


def reverify_candidate_page() -> None:
    protocol = S5GitHubBulkAcquisitionProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    observation = observation_from_failure(
        FAILURE_ARTIFACT_PATH, protocol_hash=protocol.protocol_evidence_hash
    )
    parsed = base.parse_observation(observation=observation, protocol=protocol)
    if not (
        parsed.page == 118
        and parsed.terminal_page == 245
        and parsed.next_page == 119
        and len(parsed.records) == 100
    ):
        raise ValueError("S5 GitHub monotonic-terminal candidate page changed")


def build_audit(
    *, amendment_path: Path, audited_at: datetime
) -> S5GitHubBulkMonotonicTerminalAmendmentAuditV4:
    stored = S5GitHubBulkMonotonicTerminalAmendmentV4.model_validate_json(
        amendment_path.read_text(encoding="utf-8")
    )
    expected = build_amendment(frozen_at=stored.frozen_at)
    reverify_candidate_page()
    if not (
        stored == expected
        and evidence_hash_valid(stored, "amendment_evidence_hash")
        and stored.builder_contract_hash == builder_contract_hash()
        and stored.next_authorization == S5_GITHUB_BULK_MONOTONIC_NEXT
    ):
        raise ValueError("S5 GitHub monotonic-terminal amendment reconstruction changed")
    payload = {
        "audited_at": audited_at,
        "amendment_file_sha256": file_sha256(amendment_path),
        "amendment_evidence_hash": stored.amendment_evidence_hash,
        "terminal_drift_audit_evidence_hash": stored.terminal_drift_audit_evidence_hash,
        "builder_contract_hash": stored.builder_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "next_authorization": S5_GITHUB_BULK_MONOTONIC_NEXT,
    }
    provisional = S5GitHubBulkMonotonicTerminalAmendmentAuditV4.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5GitHubBulkMonotonicTerminalAmendmentAuditV4.model_validate(complete)


def write_atomic(
    path: Path, audit: S5GitHubBulkMonotonicTerminalAmendmentAuditV4
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 GitHub monotonic audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 GitHub monotonic-audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5GitHubBulkMonotonicTerminalAmendmentAuditV4.model_validate_json(serialized) != audit:
        raise ValueError("S5 GitHub monotonic-terminal audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit S5 GitHub monotonic-terminal v4 rule.")
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        audit = build_audit(amendment_path=args.amendment, audited_at=datetime.now(UTC))
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "promote=118 additional_requests=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
