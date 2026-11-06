import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from aurex.signal_gateway import tradingview_relay as relay

NOW = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)
KEY = hashlib.sha256(b"synthetic-test-signing-key-only").hexdigest()
BODY = b'{"fixture":"synthetic only, not a real TradingView alert"}'


def timestamp(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def campaign(**kwargs):
    return relay.RelayCampaign.model_validate({
        "campaign_id": "synthetic-campaign-0001",
        "worker_hostname": "aurex-fixture.test.workers.dev",
        "starts_at": timestamp(NOW - timedelta(minutes=5)),
        "expires_at": timestamp(NOW + timedelta(minutes=5)),
        "source_reviewed_at": timestamp(NOW - timedelta(hours=1)),
        "expected_body_sha256": hashlib.sha256(BODY).hexdigest(),
        **kwargs,
    })


def receipt(**kwargs):
    c = campaign()
    return {
        "schema_version": relay.SCHEMA, "campaign_id": c.campaign_id,
        "worker_hostname": c.worker_hostname, "received_at": timestamp(NOW),
        "expires_at": c.expires_at, "source_reviewed_at": c.source_reviewed_at,
        "source_ip": "52.89.214.238", "cf_ray": "0123456789abcdef-JNB",
        "method": "POST", "path": "/webhooks/tradingview",
        "evidence_kind": "CLOUDFLARE_EDGE_RELAY_NOT_DIRECT_PEER",
        "body_sha256": hashlib.sha256(BODY).hexdigest(),
        "body_b64": base64.b64encode(BODY).decode(), **kwargs,
    }


def sign(payload, *, key=KEY):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    encoded = base64.b64encode(raw)
    return json.dumps({
        "payload_b64": encoded.decode(),
        "signature_hex": hmac.new(bytes.fromhex(key), relay.DOMAIN + encoded,
                                   hashlib.sha256).hexdigest(),
    }).encode()


def test_synthetic_receipt_verifies_exact_bytes_without_claiming_direct_origin():
    verified, body = relay.verify_receipt(sign(receipt()), campaign(), KEY, now=NOW)
    assert body == BODY
    assert verified.evidence_kind == "CLOUDFLARE_EDGE_RELAY_NOT_DIRECT_PEER"
    assert KEY not in verified.model_dump_json()


@pytest.mark.parametrize(("changes", "code"), [
    ({"campaign_id": "different-campaign-0001"}, "CAMPAIGN_MISMATCH"),
    ({"worker_hostname": "different.test.workers.dev"}, "CAMPAIGN_MISMATCH"),
    ({"expires_at": timestamp(NOW)}, "CAMPAIGN_MISMATCH"),
    ({"source_ip": "127.0.0.1"}, "SOURCE_IP_NOT_ALLOWED"),
    ({"source_ip": "52.89.214.238, 127.0.0.1"}, "SOURCE_IP_NOT_ALLOWED"),
    ({"body_sha256": "0" * 64}, "BODY_HASH_MISMATCH"),
    ({"body_b64": "e30="}, "BODY_HASH_MISMATCH"),
    ({"body_b64": "**notbase64"}, "INVALID_BASE64"),
    ({"body_b64": ""}, "BODY_SIZE_INVALID"),
    ({"received_at": timestamp(NOW - timedelta(hours=1))}, "RECEIPT_OUTSIDE_CAMPAIGN"),
    ({"received_at": timestamp(NOW + timedelta(minutes=1))}, "RECEIPT_NOT_FRESH"),
    ({"received_at": "2026-09-27T10:00:00"}, "INVALID_UTC_TIMESTAMP"),
    ({"method": "GET"}, "INVALID_RECEIPT"),
    ({"cf_ray": "spoof"}, "INVALID_RECEIPT"),
    ({"unrecognized": True}, "INVALID_RECEIPT"),
    ({"evidence_kind": "DIRECT_PEER"}, "INVALID_RECEIPT"),
])
def test_authenticated_but_invalid_receipt_is_rejected(changes, code):
    with pytest.raises(relay.RelayVerificationError, match=code):
        relay.verify_receipt(sign(receipt(**changes)), campaign(), KEY, now=NOW)


def test_stale_receipt_is_rejected():
    with pytest.raises(relay.RelayVerificationError, match="RECEIPT_NOT_FRESH"):
        relay.verify_receipt(sign(receipt()), campaign(), KEY, now=NOW + timedelta(minutes=16))


def test_forged_hmac_is_rejected():
    other = hashlib.sha256(b"another-synthetic-key").hexdigest()
    with pytest.raises(relay.RelayVerificationError, match="SIGNATURE_MISMATCH"):
        relay.verify_receipt(sign(receipt(), key=other), campaign(), KEY, now=NOW)


@pytest.mark.parametrize("raw", [
    b"[]", b"null", b"not json", b'{"payload_b64":"x","payload_b64":"y"}',
    b'{"payload_b64":{},"signature_hex":[]}', b'{"unexpected":"field"}',
    b"x" * (relay.MAX_RESPONSE_BYTES + 1),
])
def test_malformed_envelope_does_not_leak_values(raw):
    with pytest.raises(relay.RelayVerificationError):
        relay.verify_receipt(raw, campaign(), KEY, now=NOW)


def test_duplicate_signed_json_keys_rejected():
    raw = json.dumps(receipt()).encode().replace(
        b'"method": "POST"', b'"method": "GET", "method": "POST"',
    )
    with pytest.raises(relay.RelayVerificationError, match="INVALID_RECEIPT"):
        relay.verify_receipt(sign(raw), campaign(), KEY, now=NOW)


@pytest.mark.parametrize("change", [
    {"worker_hostname": "localhost"}, {"worker_hostname": "name.workers.dev.evil.example"},
    {"worker_hostname": "name.test.workers.dev/path"},
    {"starts_at": timestamp(NOW + timedelta(hours=1))},
    {"expires_at": timestamp(NOW + timedelta(hours=2))},
    {"source_reviewed_at": timestamp(NOW - timedelta(days=2))},
    {"source_reviewed_at": timestamp(NOW)}, {"campaign_id": "short"},
])
def test_invalid_campaign_rejected(change):
    with pytest.raises(ValueError):
        campaign(**change)


def transport(monkeypatch, handler):
    real_client = httpx.Client

    def client(**kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(relay.httpx, "Client", client)


def test_collection_authenticates_without_query_secrets(monkeypatch):
    def handler(request):
        assert str(request.url) == f"https://{campaign().worker_hostname}/receipt"
        assert request.headers["authorization"] == f"Bearer {KEY}"
        return httpx.Response(200, json=json.loads(sign(receipt())))

    transport(monkeypatch, handler)
    assert relay.verify_receipt(relay.fetch_receipt(campaign(), KEY), campaign(), KEY, now=NOW)


@pytest.mark.parametrize("status", [301, 302, 307, 401, 403, 429, 500])
def test_collection_never_follows_redirects_or_accepts_error_responses(monkeypatch, status):
    transport(monkeypatch, lambda _: httpx.Response(status, headers={"location": "https://evil.example"}))
    with pytest.raises(relay.RelayVerificationError, match="RECEIVER_REQUEST_REJECTED"):
        relay.fetch_receipt(campaign(), KEY)


def test_collection_pending_is_not_success(monkeypatch):
    transport(monkeypatch, lambda _: httpx.Response(404))
    assert relay.fetch_receipt(campaign(), KEY) is None


def test_collection_bounds_actual_response_bytes(monkeypatch):
    transport(
        monkeypatch,
        lambda _: httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b"x" * (relay.MAX_RESPONSE_BYTES + 1),
        ),
    )
    with pytest.raises(relay.RelayVerificationError, match="RECEIPT_TOO_LARGE"):
        relay.fetch_receipt(campaign(), KEY)
