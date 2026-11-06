import argparse
import hashlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.binance_vision import (
    download_binance_vision_archives,
    prepare_binance_vision_dataset,
    write_prepared_dataset,
)
from aurex.backtest_engine.development_bundle import (
    DatasetRole,
    DevelopmentDatasetBundle,
    DevelopmentDatasetEntry,
    audit_development_dataset_bundle,
    build_development_dataset_bundle,
    build_development_dataset_entry,
)
from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    audit_market_universe_manifest,
    universe_evidence_hash,
)

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_UNIVERSE_MANIFEST = DEFAULT_EVIDENCE_ROOT / "market_universe_manifest_v1.json"
DEFAULT_BUNDLE_OUTPUT = DEFAULT_EVIDENCE_ROOT / "development_4h_dataset_bundle_v1.json"
BUNDLE_DIRECTORY = "development_4h_bundle_v1"


def load_universe_manifest(path: Path) -> MarketUniverseManifest:
    manifest = MarketUniverseManifest.model_validate_json(path.read_text(encoding="utf-8"))
    audit = audit_market_universe_manifest(manifest)
    if audit["status"] != "PASS":
        raise ValueError(f"Market universe manifest audit failed: {audit['reasons']}")
    if manifest.status != "READY":
        raise ValueError("Market universe manifest is not ready")
    return manifest


def development_partition(manifest: MarketUniverseManifest):
    matches = [partition for partition in manifest.partitions if partition.name == "DEVELOPMENT"]
    if len(matches) != 1 or matches[0].end is None:
        raise ValueError("Frozen universe must contain one bounded development partition")
    return matches[0]


def expected_universe_roles(
    manifest: MarketUniverseManifest,
) -> dict[str, DatasetRole]:
    roles = {
        assessment.evidence.symbol: assessment.role
        for assessment in manifest.assessments
        if assessment.role in {"DECISION_CANDIDATE", "DEVELOPMENT_ONLY"}
    }
    if len(roles) != (
        manifest.summary.decision_market_count
        + manifest.summary.development_only_market_count
    ):
        raise ValueError("Frozen universe included-role summary is inconsistent")
    return dict(sorted(roles.items()))


def prepare_symbol_entry(
    *,
    evidence_root: Path,
    manifest: MarketUniverseManifest,
    symbol: str,
    role: DatasetRole,
) -> DevelopmentDatasetEntry:
    partition = development_partition(manifest)
    archive_relative = f"{BUNDLE_DIRECTORY}/archives/{symbol}"
    csv_relative = f"{BUNDLE_DIRECTORY}/datasets/{symbol}.csv"
    source_manifest_relative = (
        f"{BUNDLE_DIRECTORY}/datasets/{symbol}.manifest.json"
    )
    archive_directory = evidence_root / archive_relative
    csv_path = evidence_root / csv_relative
    source_manifest_path = evidence_root / source_manifest_relative
    archive_directory.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    archives = download_binance_vision_archives(
        destination=archive_directory,
        symbol=symbol,
        timeframe=manifest.rule.timeframe,
        data_start=partition.start,
        data_end=partition.end,
        base_uri=manifest.rule.archive_base_uri,
    )
    prepared = prepare_binance_vision_dataset(
        archive_paths=archives,
        symbol=symbol,
        timeframe=manifest.rule.timeframe,
        data_start=partition.start,
        data_end=partition.end,
        base_uri=manifest.rule.archive_base_uri,
    )
    write_prepared_dataset(
        prepared,
        csv_path=csv_path,
        manifest_path=source_manifest_path,
    )
    return build_development_dataset_entry(
        evidence_root=evidence_root,
        symbol=symbol,
        universe_role=role,
        partition_start=partition.start,
        partition_end=partition.end,
        archive_directory_relative_path=archive_relative,
        csv_relative_path=csv_relative,
        source_manifest_relative_path=source_manifest_relative,
    )


def build_bundle(
    *,
    generated_at: datetime,
    evidence_root: Path,
    manifest: MarketUniverseManifest,
    entries: list[DevelopmentDatasetEntry],
) -> DevelopmentDatasetBundle:
    partition = development_partition(manifest)
    return build_development_dataset_bundle(
        generated_at=generated_at,
        universe_manifest_evidence_hash=manifest.manifest_evidence_hash,
        contamination_ledger_hash=manifest.rule.contamination_ledger_hash,
        builder_contract_hash=builder_contract_hash(),
        partition_start=partition.start,
        partition_end=partition.end,
        expected_roles=expected_universe_roles(manifest),
        entries=entries,
        limitations=[
            (
                "This bundle contains only the frozen development partition; it does "
                "not contain validation, holdout, or forward candles."
            ),
            (
                "OHLCV integrity and continuity do not establish a profitable strategy "
                "or authorize paper, sandbox, or live execution."
            ),
            (
                "Binance Vision source archives describe one venue and do not establish "
                "future liquidity, spreads, slippage, or market availability."
            ),
            (
                "Strategy outcomes were not calculated or inspected while acquiring and "
                "freezing this dataset bundle."
            ),
        ],
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    contract_paths = [
        project_root / "scripts" / "build_development_dataset_bundle.py",
        project_root / "src" / "aurex" / "backtest_engine" / "binance_vision.py",
        project_root / "src" / "aurex" / "backtest_engine" / "development_bundle.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in contract_paths
            }
        }
    )


def write_bundle(path: Path, bundle: DevelopmentDatasetBundle) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_acquire(args) -> DevelopmentDatasetBundle:
    if args.bundle_output.exists():
        raise ValueError(
            "The frozen development dataset bundle already exists; use --check instead "
            "of overwriting evidence"
        )
    manifest = load_universe_manifest(args.universe_manifest)
    roles = expected_universe_roles(manifest)
    entries: list[DevelopmentDatasetEntry] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                prepare_symbol_entry,
                evidence_root=args.evidence_root,
                manifest=manifest,
                symbol=symbol,
                role=role,
            ): symbol
            for symbol, role in roles.items()
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            symbol = futures[future]
            try:
                entries.append(future.result())
            except Exception as exc:
                raise RuntimeError(
                    f"Development dataset acquisition failed for {symbol}"
                ) from exc
            if completed % 5 == 0 or completed == len(futures):
                print(
                    f"Development datasets prepared: {completed}/{len(futures)}",
                    flush=True,
                )
    bundle = build_bundle(
        generated_at=datetime.now(UTC),
        evidence_root=args.evidence_root,
        manifest=manifest,
        entries=entries,
    )
    write_bundle(args.bundle_output, bundle)
    print(f"WROTE {args.bundle_output} {bundle.bundle_evidence_hash}", flush=True)
    return run_check(args)


def run_check(args) -> DevelopmentDatasetBundle:
    manifest = load_universe_manifest(args.universe_manifest)
    bundle = DevelopmentDatasetBundle.model_validate_json(
        args.bundle_output.read_text(encoding="utf-8")
    )
    if bundle.universe_manifest_evidence_hash != manifest.manifest_evidence_hash:
        raise ValueError("Development bundle is bound to a different universe manifest")
    if bundle.contamination_ledger_hash != manifest.rule.contamination_ledger_hash:
        raise ValueError("Development bundle contamination binding does not match universe")
    audit = audit_development_dataset_bundle(
        bundle,
        evidence_root=args.evidence_root,
        expected_roles=expected_universe_roles(manifest),
        current_builder_contract_hash=builder_contract_hash(),
    )
    if audit["status"] != "PASS":
        raise ValueError(f"Development dataset bundle audit failed: {audit['reasons']}")
    if bundle.status != "READY":
        raise ValueError(
            "Development dataset bundle is evidence-valid but blocked for symbols: "
            f"{bundle.summary.blocked_symbols}"
        )
    print(
        "PASS "
        f"bundle={bundle.bundle_evidence_hash} "
        f"datasets={bundle.summary.dataset_count} "
        f"rows={bundle.summary.total_rows} "
        f"blocked={bundle.summary.blocked_dataset_count}",
        flush=True,
    )
    return bundle


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Acquire or offline-verify Aurex's frozen 4h development dataset bundle."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--acquire", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument(
        "--universe-manifest",
        type=Path,
        default=DEFAULT_UNIVERSE_MANIFEST,
    )
    parser.add_argument("--bundle-output", type=Path, default=DEFAULT_BUNDLE_OUTPUT)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.workers <= 12:
        parser.error("--workers must be between 1 and 12")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.acquire:
            run_acquire(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
