import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.research_v3_p01_coverage_result import (
    V3_P01_SYNC_FAMILIES,
    V3P01MonthCoverageEvidence,
)
from aurex.backtest_engine.research_v3_proposal_register import (
    V3MechanismProposalRegister,
)
from scripts.run_v3_p01_timestamp_coverage import (
    ArchiveTimestampSource,
    CoverageTask,
    inspect_task,
    load_inputs,
    maximum_gap_minutes,
    render_tasks,
)


class Args:
    charter = Path("data/evidence/v3_mechanism_discovery_charter_v1.json")
    register = Path("data/evidence/v3_mechanism_proposal_register_v1.json")
    p01_protocol = Path("data/evidence/v2_p01_primary_protocol_v1.json")
    p01_result = Path(
        "data/evidence/v2_p01_full_acquisition_result_v1.json"
    )
    evidence_root = Path("data/evidence")


def coverage_contract():
    register = V3MechanismProposalRegister.model_validate_json(
        Args.register.read_text(encoding="utf-8")
    )
    return register.proposals[0].coverage_contract


def write_timestamp_zip(path: Path, timestamps: list[int]) -> None:
    rows = b"".join(
        f"{timestamp},not-a-price,still-not-a-price\n".encode()
        for timestamp in timestamps
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{path.stem}.csv", rows)


def test_maximum_gap_includes_internal_and_boundary_minutes() -> None:
    assert maximum_gap_minutes(
        timestamps={0, 120_000},
        start_ms=0,
        end_ms=240_000,
    ) == 1
    assert maximum_gap_minutes(
        timestamps=set(),
        start_ms=0,
        end_ms=240_000,
    ) == 4


def test_timestamp_inspection_never_parses_market_numeric_fields(
    tmp_path: Path,
) -> None:
    timestamps = [1672531200000, 1672531260000]
    sources = []
    for family_id in V3_P01_SYNC_FAMILIES:
        path = tmp_path / f"{family_id}.zip"
        write_timestamp_zip(path, timestamps)
        sources.append(
            ArchiveTimestampSource(
                family_id=family_id,
                path=path,
                archive_sha256=file_sha256(path),
                row_count=2,
            )
        )
    evidence = inspect_task(
        task=CoverageTask(
            symbol="AAVEUSDT",
            month="2023-01",
            sources=tuple(sources),
        ),
        contract=coverage_contract(),
    )

    assert evidence.synchronized_minute_count == 2
    assert evidence.numeric_market_fields_inspected == []
    assert evidence.month_coverage_pass is False
    assert evidence.reason_codes == [
        "MAXIMUM_GAP_EXCEEDS_LIMIT",
        "MONTH_COVERAGE_BELOW_FLOOR",
    ]


def test_month_evidence_refuses_reason_tampering(tmp_path: Path) -> None:
    timestamps = [1672531200000]
    sources = []
    for family_id in V3_P01_SYNC_FAMILIES:
        path = tmp_path / f"{family_id}.zip"
        write_timestamp_zip(path, timestamps)
        sources.append(
            ArchiveTimestampSource(
                family_id=family_id,
                path=path,
                archive_sha256=file_sha256(path),
                row_count=1,
            )
        )
    evidence = inspect_task(
        task=CoverageTask(
            symbol="AAVEUSDT",
            month="2023-01",
            sources=tuple(sources),
        ),
        contract=coverage_contract(),
    )
    payload = evidence.model_dump()
    payload["month_coverage_pass"] = True

    with pytest.raises(ValidationError, match="decision does not reconcile"):
        V3P01MonthCoverageEvidence.model_validate(payload)


def test_v3p01_runner_renders_exact_744_task_matrix() -> None:
    _, _, _, p01_result = load_inputs(Args())

    tasks = render_tasks(
        evidence_root=Args.evidence_root,
        p01_result=p01_result,
    )

    assert len(tasks) == 744
    assert len({(task.symbol, task.month) for task in tasks}) == 744
    assert all(len(task.sources) == 4 for task in tasks)


def test_v3p01_coverage_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_v3_p01_timestamp_coverage.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
