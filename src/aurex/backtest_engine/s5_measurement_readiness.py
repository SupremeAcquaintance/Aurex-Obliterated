"""Read-only verification of the audited S5 measurement checkpoint."""

import json
from hashlib import sha256
from pathlib import Path

from aurex.backtest_engine.universe import universe_evidence_hash

S5_MEASUREMENT_CHECKPOINT = "S5_MEASUREMENTS_AUDITED_RESEARCH_ONLY"
S5_MEASUREMENT_NEXT = "RECONCILE_PLATFORM_READINESS_AND_EXECUTION_EVIDENCE"
S5_MEASUREMENT_AUDIT_HASH = "37f27c2ddfb81aaad18424aaa6ed9224da5fe086bb4f8490514caba0c796cfd1"


def file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def sealed_record(path: Path) -> dict:
    record = json.loads(path.read_bytes())
    expected = universe_evidence_hash({k: v for k, v in record.items() if k != "evidence_hash"})
    if record["evidence_hash"] != expected:
        raise ValueError("S5 checkpoint evidence hash changed")
    return record


def verify_measurement_checkpoint(root: Path) -> bool:
    try:
        evidence = root / "data/evidence"
        audit = sealed_record(evidence / "s5_amended_measurement_result_audit_v2.json")
        result_path = evidence / "s5_amended_measurement_result_v2.json"
        result = sealed_record(result_path)
        protocol = sealed_record(evidence / "s5_amended_measurement_protocol_v2.json")
        contract = sealed_record(evidence / "s5_amended_measurement_execution_v2.json")
        if (
            audit["evidence_hash"] != S5_MEASUREMENT_AUDIT_HASH
            or audit["result_hash"] != result["evidence_hash"]
            or audit["result_file_hash"] != file_digest(result_path)
            or result["protocol_hash"] != protocol["evidence_hash"]
            or result["contract_hash"] != contract["evidence_hash"]
            or contract["protocol_hash"] != protocol["evidence_hash"]
            or any(value is not False for value in audit["authority"].values())
            or audit["historical_qualification_permitted"] is not False
            or audit["output_hash"] != file_digest(root / protocol["output_path"])
            or audit["tags_hash"] != file_digest(root / protocol["tag_path"])
        ):
            return False
        for record in (
            *protocol["source_bindings"], *contract["implementation_bindings"],
            *result["transcript_bindings"],
        ):
            path = (root / record["path"]).resolve()
            if not path.is_relative_to(root.resolve()) or file_digest(path) != record["sha256"]:
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False
