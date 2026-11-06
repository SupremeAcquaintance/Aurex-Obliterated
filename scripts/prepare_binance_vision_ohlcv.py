import argparse
from datetime import datetime
from pathlib import Path

from aurex.backtest_engine.binance_vision import (
    prepare_binance_vision_dataset,
    write_prepared_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify and normalize Binance Vision kline archives for Aurex."
    )
    parser.add_argument("--archive", action="append", required=True, type=Path)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--data-start", required=True, type=datetime.fromisoformat)
    parser.add_argument("--data-end", required=True, type=datetime.fromisoformat)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    args = parser.parse_args()

    prepared = prepare_binance_vision_dataset(
        archive_paths=args.archive,
        symbol=args.symbol,
        timeframe=args.timeframe,
        data_start=args.data_start,
        data_end=args.data_end,
    )
    write_prepared_dataset(
        prepared,
        csv_path=args.output_csv,
        manifest_path=args.output_manifest,
    )
    print(
        f"Prepared {prepared.manifest['row_count']} rows; "
        f"CSV SHA-256 {prepared.manifest['canonical_csv_sha256']}"
    )


if __name__ == "__main__":
    main()
