import json
import os
import ssl
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import ValidationError

from aurex.signal_gateway import native_market_data as market
from aurex.signal_gateway.native_bars import NativeIndicatorParameters, prepare_native_closed_bar
from scripts.check_native_public_data import main

NOW = datetime(2026, 10, 6, 12, 0, 5, tzinfo=UTC)
BOUNDARY = NOW.replace(second=0)


def encoded(payload):
    return json.dumps(payload, separators=(",", ":")).encode()


def rows(url):
    query = parse_qs(urlsplit(url).query)
    start = int(query["startTime"][0])
    return [
        [
            start + i * 900000,
            "100.00000000",
            "101",
            "99",
            "100",
            "1.50000000",
            start + (i + 1) * 900000 - 1,
            "150",
            4,
            "1",
            "100",
            "0",
        ]
        for i in range(int(query["limit"][0]))
    ]


def fixture_client(transform=None, **kwargs):
    calls = []

    def fetch(url):
        calls.append(url)
        payload = {"serverTime": market.milliseconds(NOW)} if url == market.TIME_URL else rows(url)
        response = market.PublicResponse(200, encoded(payload))
        return transform(url, response) if transform else response

    options = {"transport": fetch, "now": lambda: NOW, "monotonic": lambda: 0.0}
    options.update(kwargs)
    return market.PublicCandleClient(**options), calls


@pytest.mark.parametrize("count", [1, 17, 900, 1000, 1001, 4096])
def test_bounded_pagination_retains_raw_bytes_and_reconstructs_exact_closed_candles(count):
    client, calls = fixture_client()
    evidence = client.acquire(count=count)
    bars = market.verify_public_evidence(evidence)
    assert len(calls) == 1 + (count + 999) // 1000
    assert evidence.transport == "injected"
    assert evidence.execution_authority is evidence.forward_qualifying is False
    assert bars[0].timestamp == BOUNDARY - market.STEP * count
    assert bars[-1].timestamp == BOUNDARY - market.STEP
    assert evidence.candles_sha256 == market.history_hash(list(bars))
    for page in evidence.pages:
        assert page.body.encode() == encoded(rows(page.url))
        assert page.body_sha256 == sha256(page.body.encode()).hexdigest()
    if count >= 900:
        frame = prepare_native_closed_bar(
            list(bars), now=NOW, feed_id=evidence.feed_id, parameters=NativeIndicatorParameters()
        )
        assert frame.status == "READY"
        # Acquisition does not silently upgrade the processor's provenance claim.
        assert frame.source_origin_verified is frame.execution_authority is False


def test_requested_historical_interval_is_exact_and_not_forward_permission():
    client, _ = fixture_client()
    start = BOUNDARY - timedelta(days=10)
    evidence = client.acquire(count=23, first_open=start)
    bars = market.verify_public_evidence(evidence)
    assert bars[0].timestamp == start
    assert bars[-1].timestamp == start + 22 * market.STEP
    with pytest.raises(market.NativeBarError, match="stale"):
        prepare_native_closed_bar(list(bars), now=NOW, feed_id=evidence.feed_id)


@pytest.mark.parametrize("count", [0, -1, 4097, True, 1.0, "17"])
def test_invalid_count_has_no_network_request(count):
    client, calls = fixture_client()
    with pytest.raises(market.PublicDataError, match="window_size"):
        client.acquire(count=count)
    assert calls == []


@pytest.mark.parametrize(
    "start", [NOW, BOUNDARY.replace(tzinfo=None), BOUNDARY + timedelta(microseconds=1)]
)
def test_invalid_start_has_no_network_request(start):
    client, calls = fixture_client()
    with pytest.raises(market.NativeBarError):
        client.acquire(count=1, first_open=start)
    assert calls == []


def test_current_forming_candle_rejects_before_candle_request():
    client, calls = fixture_client()
    with pytest.raises(market.PublicDataError, match="not_closed"):
        client.acquire(count=1, first_open=BOUNDARY)
    assert calls == [market.TIME_URL]


@pytest.mark.parametrize("seconds", [0, 1, 2, 3])
def test_recent_close_has_explicit_two_second_finality_delay(seconds):
    observed = BOUNDARY + timedelta(seconds=seconds)

    def transform(url, response):
        return (
            replace(response, body=encoded({"serverTime": market.milliseconds(observed)}))
            if url == market.TIME_URL
            else response
        )

    client, _ = fixture_client(transform, now=lambda: observed)
    bars = market.verify_public_evidence(client.acquire(count=1))
    assert bars[0].timestamp == BOUNDARY - market.STEP * (2 if seconds < 2 else 1)


@pytest.mark.parametrize("shift", [-3, 3, 900])
def test_server_clock_skew_never_fetches_candles(shift):
    def transform(url, response):
        return replace(
            response, body=encoded({"serverTime": market.milliseconds(NOW) + shift * 1000})
        )

    client, calls = fixture_client(transform)
    with pytest.raises(market.PublicDataError, match="clock_skew"):
        client.acquire()
    assert calls == [market.TIME_URL]


@pytest.mark.parametrize(
    "payload",
    [
        {"serverTime": True},
        {"serverTime": "123"},
        {"serverTime": -1},
        {"serverTime": 10**16},
        {"serverTime": 1, "extra": 2},
        [],
    ],
)
def test_malformed_server_time_rejects(payload):
    client, _ = fixture_client(lambda url, response: replace(response, body=encoded(payload)))
    with pytest.raises(market.PublicDataError, match="server_time_invalid"):
        client.acquire()


@pytest.mark.parametrize("status", [301, 302, 403, 418, 429, 451, 500, 503])
def test_http_rejection_is_sanitized_and_not_retried(status):
    client, calls = fixture_client(
        lambda url, response: market.PublicResponse(
            status, b"secret error body must not be reflected", retry_after="120"
        )
    )
    with pytest.raises(market.PublicDataError) as caught:
        client.acquire()
    assert str(caught.value) == "public_http_rejected"
    assert caught.value.status == status
    assert caught.value.retry_after == 120
    assert len(calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"body": b""},
        {"body": b"x" * (market.MAX_RESPONSE_BYTES + 1)},
        {"body": b"\xff"},
        {"body": b"not-json"},
        {"body": b'{"serverTime":NaN}'},
        {"body": b'{"serverTime":1,"serverTime":2}'},
        {"content_type": "text/html"},
        {"content_encoding": "gzip"},
    ],
)
def test_bad_http_payload_is_not_accepted(change):
    client, _ = fixture_client(lambda url, response: replace(response, **change))
    with pytest.raises(market.PublicDataError):
        client.acquire()


@pytest.mark.parametrize(
    "kind",
    [
        "empty",
        "extra",
        "reversed",
        "duplicate",
        "gap",
        "short_row",
        "long_row",
        "float_open_time",
        "microsecond_time",
        "wrong_close",
        "bool_trades",
        "negative_trades",
        "price_number",
        "price_nan",
        "price_precision",
        "price_negative",
        "price_zero",
        "geometry",
        "volume_negative",
        "taker_volume",
        "quote_volume",
        "ignore",
    ],
)
def test_malformed_or_discontinuous_candles_fail_without_sorting_or_filling(kind):
    def transform(url, response):
        if url == market.TIME_URL:
            return response
        data = rows(url)
        match kind:
            case "empty":
                data = []
            case "extra":
                data.append(data[-1])
            case "reversed":
                data.reverse()
            case "duplicate":
                data[1] = data[0]
            case "gap":
                data[1][0] += 900000
            case "short_row":
                data[0].pop()
            case "long_row":
                data[0].append("0")
            case "float_open_time":
                data[0][0] = float(data[0][0])
            case "microsecond_time":
                data[0][0] *= 1000
            case "wrong_close":
                data[0][6] += 1
            case "bool_trades":
                data[0][8] = True
            case "negative_trades":
                data[0][8] = -1
            case "price_number":
                data[0][1] = 100.0
            case "price_nan":
                data[0][1] = "NaN"
            case "price_precision":
                data[0][1] = "100.000000001"
            case "price_negative":
                data[0][1] = "-1"
            case "price_zero":
                data[0][1] = "0"
            case "geometry":
                data[0][2] = "1"
            case "volume_negative":
                data[0][5] = "-1"
            case "taker_volume":
                data[0][9] = "2"
            case "quote_volume":
                data[0][10] = "151"
            case "ignore":
                data[0][11] = 0
        return replace(response, body=encoded(data))

    client, _ = fixture_client(transform)
    with pytest.raises((market.PublicDataError, ValidationError)):
        client.acquire(count=2)


def test_missing_page_at_pagination_boundary_never_yields_partial_success():
    def transform(url, response):
        if "limit=1" in url and "limit=1000" not in url:
            return replace(response, body=b"[]")
        return response

    client, calls = fixture_client(transform)
    with pytest.raises(market.PublicDataError, match="count_mismatch"):
        client.acquire(count=1001)
    assert len(calls) == 3


@pytest.mark.parametrize("elapsed", [-1.0, 11.0])
def test_monotonic_request_deadline(elapsed):
    times = iter([0.0, 0.0, elapsed])
    client, _ = fixture_client(monotonic=lambda: next(times))
    with pytest.raises(market.PublicDataError, match="deadline"):
        client.acquire()


@pytest.mark.parametrize("delta", [-1, 2, 11])
def test_wall_clock_jump_rejected(delta):
    times = iter([NOW, NOW + timedelta(seconds=delta)])
    client, _ = fixture_client(now=lambda: next(times))
    with pytest.raises(market.PublicDataError, match="clock_changed"):
        client.acquire()


@pytest.mark.parametrize(
    "kind",
    [
        "body",
        "url",
        "history",
        "scope",
        "time",
        "page_order",
        "missing_page",
        "extra_page",
        "rehash_gap",
        "rehash_geometry",
    ],
)
def test_offline_reconstruction_rejects_changed_artifact(kind):
    client, _ = fixture_client()
    original = client.acquire(count=1001)
    payload = original.model_dump(mode="json")
    page = payload["pages"][0]
    match kind:
        case "body":
            page["body"] += " "
        case "url":
            page["url"] = page["url"].replace("BTCUSDT", "ETHUSDT")
        case "history":
            payload["candles_sha256"] = "0" * 64
        case "scope":
            payload["symbol"] = "ETHUSDT"
        case "time":
            page["received_at"] = (NOW + timedelta(seconds=20)).isoformat()
        case "page_order":
            payload["pages"].reverse()
        case "missing_page":
            payload["pages"].pop()
        case "extra_page":
            payload["pages"].append(page)
        case "rehash_gap" | "rehash_geometry":
            raw = json.loads(page["body"])
            raw[0][0 if kind == "rehash_gap" else 2] = 0 if kind == "rehash_gap" else "1"
            page["body"] = encoded(raw).decode()
            page["body_sha256"] = sha256(page["body"].encode()).hexdigest()
    with pytest.raises((market.PublicDataError, ValidationError)):
        market.verify_public_evidence(market.PublicCandleEvidence.model_validate(payload))


def test_write_read_roundtrip_no_overwrite_and_crash_truncation(tmp_path):
    client, _ = fixture_client()
    evidence = client.acquire(count=17)
    path = tmp_path / "source.json"
    digest = market.write_public_evidence(evidence, path)
    assert digest == sha256(path.read_bytes()).hexdigest()
    assert market.read_public_evidence(path) == evidence
    with pytest.raises(FileExistsError):
        market.write_public_evidence(evidence, path)
    original = path.read_bytes()
    path.write_bytes(original[: len(original) // 2])
    with pytest.raises(market.PublicDataError):
        market.read_public_evidence(path)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.binance.com/api/v3/time",
        "http://data-api.binance.vision/api/v3/time",
        market.PUBLIC_ORIGIN + "/api/v3/order",
        market.TIME_URL + "?signature=secret",
        market.TIME_URL + "#fragment",
        market.TIME_URL.replace("https://", "https://user:pass@"),
        market.TIME_URL.replace(".vision", ".vision.evil.test"),
    ],
)
def test_transport_whitelist_rejects_before_opening_connection(monkeypatch, url):
    def forbidden(*args, **kwargs):
        raise AssertionError("network must not be used")

    monkeypatch.setattr(market.http.client, "HTTPSConnection", forbidden)
    with pytest.raises(market.PublicDataError):
        market.fetch_public(url)


def test_fixed_tls_transport_has_no_credentials_redirect_or_proxy(monkeypatch):
    seen = {}

    class Response:
        status = 302

        def __init__(self):
            self.data = b"{}"

        def read1(self, size):
            value, self.data = self.data[:size], self.data[size:]
            return value

        def getheader(self, name, default=None):
            return {"Content-Type": "application/json", "Location": "https://evil.test"}.get(
                name, default
            )

    class Connection:
        def __init__(self, host, **kwargs):
            seen.update(host=host, **kwargs)

        def request(self, method, target, headers):
            seen.update(method=method, target=target, headers=headers)

        def getresponse(self):
            return Response()

        def close(self):
            seen["closed"] = True

    monkeypatch.setattr(market.http.client, "HTTPSConnection", Connection)
    monkeypatch.setenv("HTTPS_PROXY", "https://user:secret@proxy.invalid")
    response = market.fetch_public(market.TIME_URL)
    assert response.status == 302
    assert seen["host"] == "data-api.binance.vision"
    assert seen["context"].verify_mode == ssl.CERT_REQUIRED
    assert seen["context"].check_hostname
    assert seen["method"] == "GET" and seen["target"] == "/api/v3/time"
    assert set(seen["headers"]) == {"Accept", "Accept-Encoding", "User-Agent"}
    assert seen["closed"]


def test_cli_can_acquire_and_verify_without_database_or_network_on_replay(
    tmp_path, monkeypatch, capsys
):
    client, calls = fixture_client()
    monkeypatch.setattr("scripts.check_native_public_data.PublicCandleClient", lambda: client)
    path = tmp_path / "evidence.json"
    assert main(["--output", str(path), "--count", "17"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "PASS" and result["transport"] == "injected"
    assert result["database_opened"] is result["execution_authority"] is False
    assert main(["--verify", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "offline_reconstruction"
    assert len(calls) == 2
    assert main(["--output", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "output_already_exists"
    assert len(calls) == 2


def test_cli_sanitizes_failure_and_writes_no_success_artifact(tmp_path, monkeypatch, capsys):
    client, _ = fixture_client(
        lambda url, response: market.PublicResponse(429, b"private", retry_after="60")
    )
    monkeypatch.setattr("scripts.check_native_public_data.PublicCandleClient", lambda: client)
    path = tmp_path / "evidence.json"
    assert main(["--output", str(path)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "BLOCKED"
    assert result["http_status"] == 429 and result["retry_after_seconds"] == 60
    assert "private" not in str(result)
    assert not path.exists()


def test_clock_failure_exposes_raw_public_clock_diagnostic_not_candle_success(
    tmp_path, monkeypatch, capsys
):
    client, calls = fixture_client(
        lambda url, response: replace(
            response, body=encoded({"serverTime": market.milliseconds(NOW) + 8000})
        )
    )
    monkeypatch.setattr("scripts.check_native_public_data.PublicCandleClient", lambda: client)
    path = tmp_path / "not-created.json"
    assert main(["--output", str(path)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "BLOCKED" and result["reason"] == "public_server_clock_skew"
    exchange = result["clock_observation"]
    assert exchange["url"] == market.TIME_URL
    assert sha256(exchange["body"].encode()).hexdigest() == exchange["body_sha256"]
    assert result["clock_tolerance_seconds"] == 2
    assert calls == [market.TIME_URL] and not path.exists()


def test_window_overflow_rejects_before_network():
    client, calls = fixture_client()
    with pytest.raises(market.PublicDataError, match="time_out_of_range"):
        client.acquire(count=2, first_open=datetime(9999, 12, 31, 23, 45, tzinfo=UTC))
    assert not calls


@pytest.mark.parametrize("backward", [True, False])
def test_inter_request_clock_jump_stops_before_next_page(backward):
    page_time = NOW + timedelta(seconds=-1 if backward else 91)
    times = iter([NOW, NOW, page_time, page_time])
    client, calls = fixture_client(now=lambda: next(times))
    with pytest.raises(market.PublicDataError, match="sequence_invalid|deadline"):
        client.acquire(count=1001)
    assert len(calls) == 2


def test_total_monotonic_deadline_is_checked_after_last_page():
    times = iter([0, 0, 0, 0, 0, 0, 91])
    client, _ = fixture_client(monotonic=lambda: next(times))
    with pytest.raises(market.PublicDataError, match="batch_deadline"):
        client.acquire(count=1)


def test_retained_surrogate_body_is_rejected():
    client, _ = fixture_client()
    evidence = client.acquire(count=1).model_dump(mode="json")
    evidence["pages"][0]["body"] = "\ud800"
    with pytest.raises((market.PublicDataError, ValidationError)):
        market.verify_public_evidence(market.PublicCandleEvidence.model_validate(evidence))


def test_fresh_process_can_verify_with_broken_db_settings_and_no_network(tmp_path):
    client, _ = fixture_client()
    path = tmp_path / "source.json"
    market.write_public_evidence(client.acquire(count=17), path)
    root = Path(__file__).resolve().parents[2]
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "import socket,sys; "
            "socket.create_connection=lambda *a,**k: "
            "(_ for _ in ()).throw(AssertionError('network')); "
            "from scripts.check_native_public_data import main; "
            "raise SystemExit(main(['--verify',sys.argv[1]]))",
            str(path),
        ],
        cwd=root,
        env={**os.environ, "AUREX_DATABASE_URL": "invalid-driver:///forbidden"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result["status"] == "PASS"
    assert result["database_opened"] is result["execution_authority"] is False


@pytest.mark.parametrize("failure", ["timeout", "oversize", "read_error"])
def test_transport_failure_bounds_close_connection_and_sanitize_errors(monkeypatch, failure):
    seen = []

    class Response:
        status = 200

        def read1(self, size):
            if failure == "oversize":
                return b"x" * size
            raise OSError("private transport detail")

    class Connection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            if failure == "timeout":
                raise TimeoutError("private transport detail")

        def getresponse(self):
            return Response()

        def close(self):
            seen.append("closed")

    monkeypatch.setattr(market.http.client, "HTTPSConnection", Connection)
    with pytest.raises(market.PublicDataError) as caught:
        market.fetch_public(market.TIME_URL)
    assert "private" not in str(caught.value)
    assert seen == ["closed"]


def test_disk_full_never_reports_success_and_partial_file_fails_replay(
    tmp_path, monkeypatch, capsys
):
    client, _ = fixture_client()
    monkeypatch.setattr("scripts.check_native_public_data.PublicCandleClient", lambda: client)

    def fail_sync(handle):
        raise OSError("disk failure")

    monkeypatch.setattr(market.os, "fsync", fail_sync)
    path = tmp_path / "unacknowledged.json"
    assert main(["--output", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"
    # A whole write may precede fsync failure; offline data is not forward evidence.
    assert market.read_public_evidence(path).forward_qualifying is False


@pytest.mark.parametrize("kind", ["empty", "oversize", "invalid_utf8"])
def test_readback_bounds_and_encoding(tmp_path, kind):
    body = {
        "empty": b"",
        "oversize": b"x" * (market.MAX_ARTIFACT_BYTES + 1),
        "invalid_utf8": b"\xff",
    }[kind]
    path = tmp_path / "invalid.json"
    path.write_bytes(body)
    with pytest.raises(market.PublicDataError):
        market.read_public_evidence(path)
