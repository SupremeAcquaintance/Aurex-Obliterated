import argparse
import json

from aurex.backtest_engine.failure_analysis import analyze_reference_replay_failure
from aurex.backtest_engine.reference_replay import ReferenceReplayEvidenceLab
from aurex.db.models import BacktestReferenceReplayRun
from aurex.db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic development-only failure reports."
    )
    parser.add_argument("replay_ids", nargs="+", help="Immutable reference replay IDs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reports: list[dict[str, object]] = []
    with SessionLocal() as session:
        lab = ReferenceReplayEvidenceLab(session)
        for replay_id in args.replay_ids:
            replay = session.get(BacktestReferenceReplayRun, replay_id)
            if replay is None:
                raise SystemExit(f"Reference replay not found: {replay_id}")
            audit = lab.audit(replay)
            if audit.status != "PASS":
                raise SystemExit(
                    f"Reference replay audit blocked for {replay_id}: {audit.reasons}"
                )
            reports.append(analyze_reference_replay_failure(replay))
    print(json.dumps(reports, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
