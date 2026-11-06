import argparse
import hashlib
import json
import sys
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.binance_vision import (
    MAX_ARCHIVE_DOWNLOAD_BYTES,
    MAX_CHECKSUM_DOWNLOAD_BYTES,
    atomic_write,
    fetch_url_bytes,
    file_sha256,
    local_archive_is_verified,
    parse_checksum_file,
    prepare_binance_vision_dataset,
)
from aurex.backtest_engine.research_r4_protocol import (
    R4_DECISION_SYMBOLS,
    R4_REQUIRED_MONTHS,
    R4CandidateProtocol,
    audit_r4_candidate_protocol,
)
from aurex.backtest_engine.universe import (
    MarketUniverseManifest,
    audit_market_universe_manifest,
    universe_evidence_hash,
)
from aurex.backtest_engine.validation_bundle import (
    ValidationArchiveRequest,
    ValidationDatasetBundle,
    ValidationDatasetEntry,
    audit_validation_dataset_bundle,
    build_validation_dataset_bundle,
    build_validation_dataset_entry,
)

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_UNIVERSE = DEFAULT_EVIDENCE_ROOT / "market_universe_manifest_v1.json"
DEFAULT_R4_PROTOCOL = DEFAULT_EVIDENCE_ROOT / "r4_path_quality_candidate_v1.json"
DEFAULT_OUTPUT = DEFAULT_EVIDENCE_ROOT / "validation_2025_4h_bundle_v1.json"
BUNDLE_DIRECTORY = "validation_2025_4h_bundle_v1"
ARCHIVE_BASE_URI = "https://data.binance.vision/data/spot/monthly/klines"


def load_inputs(args) -> tuple[MarketUniverseManifest, R4CandidateProtocol]:
    universe = MarketUniverseManifest.model_validate_json(
        args.universe.read_text(encoding="utf-8")
    )
    protocol = R4CandidateProtocol.model_validate_json(
        args.r4_protocol.read_text(encoding="utf-8")
    )
    if audit_market_universe_manifest(universe)["status"] != "PASS":
        raise ValueError("Validation bundle universe audit failed")
    if not audit_r4_candidate_protocol(protocol):
        raise ValueError("Validation bundle R4 candidate audit failed")
    if protocol.universe_manifest_evidence_hash != universe.manifest_evidence_hash:
        raise ValueError("Validation bundle candidate/universe binding changed")
    if tuple(protocol.decision_symbols) != R4_DECISION_SYMBOLS:
        raise ValueError("Validation bundle candidate universe changed")
    return universe, protocol


def acquire_archive_request(
    *,
    evidence_root: Path,
    archive_directory: Path,
    symbol: str,
    month: str,
) -> ValidationArchiveRequest:
    archive_name = f"{symbol}-4h-{month}.zip"
    archive_uri = f"{ARCHIVE_BASE_URI}/{symbol}/4h/{archive_name}"
    checksum_uri = f"{archive_uri}.CHECKSUM"
    archive_path = archive_directory / archive_name
    checksum_path = Path(f"{archive_path}.CHECKSUM")
    observed_at = datetime.now(UTC)
    if not local_archive_is_verified(archive_path, checksum_path):
        try:
            checksum_bytes = fetch_url_bytes(
                checksum_uri,
                MAX_CHECKSUM_DOWNLOAD_BYTES,
            )
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            if archive_path.exists() or checksum_path.exists():
                raise ValueError(
                    f"Unavailable archive conflicts with local files: {archive_name}"
                ) from exc
            return ValidationArchiveRequest(
                month=month,
                archive_name=archive_name,
                archive_uri=archive_uri,
                checksum_uri=checksum_uri,
                observed_at=observed_at,
                status="UNAVAILABLE_404",
            )
        archive_bytes = fetch_url_bytes(
            archive_uri,
            MAX_ARCHIVE_DOWNLOAD_BYTES,
        )
        atomic_write(checksum_path, checksum_bytes)
        atomic_write(archive_path, archive_bytes)
        if not local_archive_is_verified(archive_path, checksum_path):
            raise ValueError(f"Validation checksum mismatch for {archive_name}")
    archive_relative = archive_path.relative_to(evidence_root).as_posix()
    checksum_relative = checksum_path.relative_to(evidence_root).as_posix()
    expected = parse_checksum_file(checksum_path, archive_name)
    return ValidationArchiveRequest(
        month=month,
        archive_name=archive_name,
        archive_uri=archive_uri,
        checksum_uri=checksum_uri,
        observed_at=observed_at,
        status="CHECKSUM_VERIFIED",
        archive_relative_path=archive_relative,
        checksum_relative_path=checksum_relative,
        archive_sha256=file_sha256(archive_path),
        checksum_file_sha256=file_sha256(checksum_path),
        expected_archive_sha256=expected,
        archive_size_bytes=archive_path.stat().st_size,
    )


def prepare_symbol_entry(
    *,
    evidence_root: Path,
    symbol: str,
) -> ValidationDatasetEntry:
    archive_relative = f"{BUNDLE_DIRECTORY}/archives/{symbol}"
    csv_relative = f"{BUNDLE_DIRECTORY}/datasets/{symbol}.csv"
    manifest_relative = f"{BUNDLE_DIRECTORY}/datasets/{symbol}.manifest.json"
    archive_directory = evidence_root / archive_relative
    csv_path = evidence_root / csv_relative
    manifest_path = evidence_root / manifest_relative
    archive_directory.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    requests = [
        acquire_archive_request(
            evidence_root=evidence_root,
            archive_directory=archive_directory,
            symbol=symbol,
            month=month,
        )
        for month in R4_REQUIRED_MONTHS
    ]
    archive_paths = [
        evidence_root / (request.archive_relative_path or "")
        for request in requests
        if request.status == "CHECKSUM_VERIFIED"
    ]
    prepared = prepare_binance_vision_dataset(
        archive_paths=archive_paths,
        symbol=symbol,
        timeframe="4h",
        data_start=datetime(2025, 1, 1, tzinfo=UTC),
        data_end=datetime(2026, 1, 1, tzinfo=UTC),
        base_uri=ARCHIVE_BASE_URI,
    )
    manifest = {
        **prepared.manifest,
        "validation_archive_requests": [
            request.model_dump(mode="json") for request in requests
        ],
        "strategy_outcome_fields_inspected": [],
    }
    csv_temporary = csv_path.with_name(f"{csv_path.name}.part")
    manifest_temporary = manifest_path.with_name(f"{manifest_path.name}.part")
    csv_temporary.write_text(prepared.csv_text, encoding="utf-8", newline="")
    manifest_temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )
    csv_temporary.replace(csv_path)
    manifest_temporary.replace(manifest_path)
    return build_validation_dataset_entry(
        evidence_root=evidence_root,
        symbol=symbol,
        partition_start=datetime(2025, 1, 1, tzinfo=UTC),
        partition_end=datetime(2026, 1, 1, tzinfo=UTC),
        archive_directory_relative_path=archive_relative,
        csv_relative_path=csv_relative,
        source_manifest_relative_path=manifest_relative,
    )


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "build_validation_dataset_bundle.py",
        project_root / "src" / "aurex" / "backtest_engine" / "binance_vision.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "validation_bundle.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def authoritative_bundle(
    *,
    generated_at: datetime,
    universe: MarketUniverseManifest,
    protocol: R4CandidateProtocol,
    entries: list[ValidationDatasetEntry],
) -> ValidationDatasetBundle:
    return build_validation_dataset_bundle(
        generated_at=generated_at,
        r4_candidate_protocol_evidence_hash=protocol.protocol_evidence_hash,
        universe_manifest_evidence_hash=universe.manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=(
            protocol.development_dataset_bundle_evidence_hash
        ),
        contamination_ledger_hash=protocol.contamination_ledger_hash,
        builder_contract_hash=builder_contract_hash(),
        entries=entries,
        limitations=[
            (
                "This bundle contains only the frozen 2025 validation partition and "
                "does not contain 2026 holdout or forward candles."
            ),
            (
                "An HTTP 404 receipt records observed source unavailability but cannot "
                "prove why Binance stopped publishing an archive."
            ),
            (
                "A contiguous terminal missing suffix is retained as market "
                "termination; internal, leading, or resumed gaps block validation."
            ),
            (
                "OHLCV acquisition and integrity checks calculate no strategy signal, "
                "trade, return, gate, or verdict."
            ),
            (
                "Historical Binance Vision data do not establish future liquidity, "
                "spread, slippage, execution quality, or profitability."
            ),
        ],
    )


def write_bundle(path: Path, bundle: ValidationDatasetBundle) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = bundle.model_dump_json(indent=2) + "\n"
    if ValidationDatasetBundle.model_validate_json(serialized) != bundle:
        raise ValueError("Validation bundle JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_acquire(args) -> ValidationDatasetBundle:
    if args.output.exists():
        raise ValueError("Frozen validation bundle exists; use --check")
    universe, protocol = load_inputs(args)
    entries: list[ValidationDatasetEntry] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                prepare_symbol_entry,
                evidence_root=args.evidence_root,
                symbol=symbol,
            ): symbol
            for symbol in protocol.decision_symbols
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            symbol = futures[future]
            try:
                entries.append(future.result())
            except Exception as exc:
                raise RuntimeError(
                    f"Validation dataset acquisition failed for {symbol}"
                ) from exc
            if completed % 5 == 0 or completed == len(futures):
                print(
                    f"Validation datasets prepared: {completed}/{len(futures)}",
                    flush=True,
                )
    bundle = authoritative_bundle(
        generated_at=datetime.now(UTC),
        universe=universe,
        protocol=protocol,
        entries=entries,
    )
    write_bundle(args.output, bundle)
    print(
        f"WROTE {args.output} {bundle.bundle_evidence_hash} "
        f"status={bundle.status}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> ValidationDatasetBundle:
    universe, protocol = load_inputs(args)
    bundle = ValidationDatasetBundle.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if (
        bundle.r4_candidate_protocol_evidence_hash
        != protocol.protocol_evidence_hash
        or bundle.universe_manifest_evidence_hash
        != universe.manifest_evidence_hash
    ):
        raise ValueError("Validation bundle parent binding changed")
    audit = audit_validation_dataset_bundle(
        bundle,
        evidence_root=args.evidence_root,
        current_builder_contract_hash=builder_contract_hash(),
    )
    if audit["status"] != "PASS":
        raise ValueError(f"Validation bundle audit failed: {audit['reasons']}")
    print(
        "PASS "
        f"validation_bundle={bundle.bundle_evidence_hash} "
        f"status={bundle.status} "
        f"datasets={bundle.summary.dataset_count} "
        f"rows={bundle.summary.total_rows} "
        f"terminal={bundle.summary.terminal_unavailable_count} "
        f"blocked={bundle.summary.blocked_dataset_count}",
        flush=True,
    )
    return bundle


def parse_args():
    parser = argparse.ArgumentParser(
        description="Acquire or verify the frozen 2025 R4 validation dataset bundle."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--acquire", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--r4-protocol", type=Path, default=DEFAULT_R4_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
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
