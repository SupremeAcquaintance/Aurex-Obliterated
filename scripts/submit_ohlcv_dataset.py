import argparse
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit a prepared OHLCV dataset to Aurex preflight or import."
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:8919")
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--continuity",
        choices=(
            "continuous_24_7",
            "continuous_24_7_with_documented_outages",
            "session_based",
        ),
        default="continuous_24_7",
    )
    parser.add_argument(
        "--documented-gaps-json",
        type=Path,
        help="JSON array of exact missing-candle windows and supporting source references.",
    )
    parser.add_argument("--import-dataset", action="store_true")
    args = parser.parse_args()

    csv_text = args.csv.read_text(encoding="utf-8")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    canonical_hash = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    if canonical_hash != manifest.get("canonical_csv_sha256"):
        raise ValueError("Prepared CSV SHA-256 does not match its source manifest")
    documented_gaps = []
    if args.documented_gaps_json is not None:
        documented_gaps = json.loads(args.documented_gaps_json.read_text(encoding="utf-8"))
        if not isinstance(documented_gaps, list):
            raise ValueError("Documented gaps JSON must contain an array")

    payload = {
        "symbol": manifest["symbol"],
        "timeframe": manifest["timeframe"],
        "source": manifest["source"],
        "source_reference": manifest["source_reference"],
        "csv_timezone": "UTC",
        "continuity": args.continuity,
        "documented_gaps": documented_gaps,
        "source_artifacts": manifest["source_artifacts"],
        "transformation": manifest["transformation"],
        "csv_text": csv_text,
    }
    path = (
        "/backtests/ohlcv/import-csv"
        if args.import_dataset
        else "/backtests/ohlcv/preflight-csv"
    )
    request = urllib.request.Request(
        f"{args.api_url.rstrip('/')}{path}",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Aurex returned HTTP {exc.code}: {detail}") from exc

    summary_keys = (
        "id",
        "status",
        "symbol",
        "timeframe",
        "valid_rows",
        "rejected_rows",
        "row_count",
        "data_start",
        "data_end",
        "missing_interval_count",
        "documented_gap_count",
        "undocumented_gap_count",
        "source_artifacts_verified",
        "canonical_csv_sha256",
        "source_artifact_bundle_hash",
        "evidence_hash",
        "reused_existing",
    )
    print(json.dumps({key: result.get(key) for key in summary_keys if key in result}, indent=2))


if __name__ == "__main__":
    main()
