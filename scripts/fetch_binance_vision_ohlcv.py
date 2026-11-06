import argparse
from datetime import datetime
from pathlib import Path

from aurex.backtest_engine.binance_vision import (
    DEFAULT_BINANCE_VISION_KLINE_URI,
    download_binance_vision_archives,
    prepare_binance_vision_dataset,
    write_prepared_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Download, checksum-verify, and normalize Binance Vision monthly klines "
            "for Aurex."
        )
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--data-start", required=True, type=datetime.fromisoformat)
    parser.add_argument("--data-end", required=True, type=datetime.fromisoformat)
    parser.add_argument("--download-dir", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    parser.add_argument("--base-uri", default=DEFAULT_BINANCE_VISION_KLINE_URI)
    args = parser.parse_args()

    archives = download_binance_vision_archives(
        destination=args.download_dir,
        symbol=args.symbol,
        timeframe=args.timeframe,
        data_start=args.data_start,
        data_end=args.data_end,
        base_uri=args.base_uri,
    )
    prepared = prepare_binance_vision_dataset(
        archive_paths=archives,
        symbol=args.symbol,
        timeframe=args.timeframe,
        data_start=args.data_start,
        data_end=args.data_end,
        base_uri=args.base_uri,
    )
    write_prepared_dataset(
        prepared,
        csv_path=args.output_csv,
        manifest_path=args.output_manifest,
    )
    units = ", ".join(prepared.manifest["transformation"]["timestamp_units"])
    print(
        f"Prepared {prepared.manifest['row_count']} rows from {len(archives)} archives; "
        f"timestamp units {units}; CSV SHA-256 "
        f"{prepared.manifest['canonical_csv_sha256']}"
    )


if __name__ == "__main__":
    main()
