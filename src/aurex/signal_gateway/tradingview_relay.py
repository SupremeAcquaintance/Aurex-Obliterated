"""Verify bounded edge receipts without claiming direct origin or executing a signal."""

import base64
import binascii
import hashlib
import hmac
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.signal_gateway.tradingview_delivery import TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS

SCHEMA = "aurex-tradingview-relay-receipt-v1"
DOMAIN = b"aurex-tradingview-relay-v1\n"
MAX_BODY_BYTES = 16 * 1024
MAX_RESPONSE_BYTES = 40 * 1024
SENDER_IPS = {value.split("/")[0] for value in TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS}


class RelayVerificationError(ValueError):
    """Only fixed, credential-free codes may cross the CLI boundary."""


def strict_json(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise RelayVerificationError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    try:
        result = json.loads(raw, object_pairs_hook=pairs)
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise RelayVerificationError("INVALID_JSON") from exc


def utc_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
        if parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z") != value:
            raise ValueError
        return parsed
    except ValueError as exc:
        raise RelayVerificationError("INVALID_UTC_TIMESTAMP") from exc


def require_key(value: str) -> bytes:
    if not re.fullmatch(r"[0-9a-f]{64}", value) or len(set(value)) < 8:
        raise RelayVerificationError("DEDICATED_256_BIT_KEY_REQUIRED")
    return bytes.fromhex(value)


class RelayCampaign(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["aurex-tradingview-relay-campaign-v1"] = (
        "aurex-tradingview-relay-campaign-v1"
    )
    campaign_id: str = Field(pattern=r"^[a-z0-9-]{16,64}$")
    worker_hostname: str = Field(pattern=r"^[a-z0-9-]+\.[a-z0-9-]+\.workers\.dev$")
    starts_at: str
    expires_at: str
    source_reviewed_at: str
    expected_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("starts_at", "expires_at", "source_reviewed_at")
    @classmethod
    def timestamp(cls, value: str) -> str:
        utc_timestamp(value)
        return value

    @model_validator(mode="after")
    def window(self):
        start, end, review = map(utc_timestamp, (
            self.starts_at, self.expires_at, self.source_reviewed_at,
        ))
        if not timedelta(0) < end - start <= timedelta(hours=1):
            raise ValueError("CAMPAIGN_WINDOW_INVALID")
        if review > start or end - review > timedelta(hours=24):
            raise ValueError("SOURCE_REVIEW_NOT_CURRENT")
        return self


class RelayReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["aurex-tradingview-relay-receipt-v1"]
    campaign_id: str
    worker_hostname: str
    received_at: str
    expires_at: str
    source_reviewed_at: str
    source_ip: str
    cf_ray: str = Field(pattern=r"^[0-9a-f]{16}-[A-Z]{3}$")
    method: Literal["POST"]
    path: Literal["/webhooks/tradingview"]
    evidence_kind: Literal["CLOUDFLARE_EDGE_RELAY_NOT_DIRECT_PEER"]
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_b64: str = Field(max_length=22000)


def _base64(value: str) -> bytes:
    try:
        raw = base64.b64decode(value, validate=True)
        if base64.b64encode(raw).decode("ascii") != value:
            raise ValueError
        return raw
    except (ValueError, binascii.Error) as exc:
        raise RelayVerificationError("INVALID_BASE64") from exc


def verify_receipt(
    raw: bytes, campaign: RelayCampaign, signing_key: str, *, now: datetime,
) -> tuple[RelayReceipt, bytes]:
    if now.tzinfo is None:
        raise RelayVerificationError("VERIFICATION_TIME_REQUIRES_TIMEZONE")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RelayVerificationError("RECEIPT_TOO_LARGE")
    envelope = strict_json(raw)
    if set(envelope) != {"payload_b64", "signature_hex"}:
        raise RelayVerificationError("INVALID_ENVELOPE")
    payload_b64, signature = envelope["payload_b64"], envelope["signature_hex"]
    if not isinstance(payload_b64, str) or not isinstance(signature, str):
        raise RelayVerificationError("INVALID_ENVELOPE")
    if not re.fullmatch(r"[0-9a-f]{64}", signature):
        raise RelayVerificationError("INVALID_SIGNATURE")
    try:
        signed = DOMAIN + payload_b64.encode("ascii")
    except UnicodeError as exc:
        raise RelayVerificationError("INVALID_BASE64") from exc
    expected = hmac.new(require_key(signing_key), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise RelayVerificationError("SIGNATURE_MISMATCH")
    try:
        receipt = RelayReceipt.model_validate(strict_json(_base64(payload_b64)))
    except ValueError as exc:
        raise RelayVerificationError("INVALID_RECEIPT") from exc
    if any(getattr(receipt, key) != getattr(campaign, key) for key in (
        "campaign_id", "worker_hostname", "expires_at", "source_reviewed_at",
    )):
        raise RelayVerificationError("CAMPAIGN_MISMATCH")
    received = utc_timestamp(receipt.received_at)
    if not utc_timestamp(campaign.starts_at) <= received <= utc_timestamp(campaign.expires_at):
        raise RelayVerificationError("RECEIPT_OUTSIDE_CAMPAIGN")
    age = now.astimezone(UTC) - received
    if age < timedelta(seconds=-30) or age > timedelta(minutes=15):
        raise RelayVerificationError("RECEIPT_NOT_FRESH")
    if receipt.source_ip not in SENDER_IPS:
        raise RelayVerificationError("SOURCE_IP_NOT_ALLOWED")
    body = _base64(receipt.body_b64)
    if not 0 < len(body) <= MAX_BODY_BYTES:
        raise RelayVerificationError("BODY_SIZE_INVALID")
    digest = hashlib.sha256(body).hexdigest()
    if digest != receipt.body_sha256 or digest != campaign.expected_body_sha256:
        raise RelayVerificationError("BODY_HASH_MISMATCH")
    return receipt, body


def fetch_receipt(campaign: RelayCampaign, read_secret: str) -> bytes | None:
    require_key(read_secret)
    try:
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", f"https://{campaign.worker_hostname}/receipt",
                               headers={"Authorization": f"Bearer {read_secret}"}) as response:
                if response.status_code == 404:
                    return None
                if response.status_code != 200:
                    raise RelayVerificationError("RECEIVER_REQUEST_REJECTED")
                if response.headers.get("content-type", "").split(";", 1)[0] != "application/json":
                    raise RelayVerificationError("RECEIVER_CONTENT_TYPE_INVALID")
                raw = bytearray()
                for chunk in response.iter_bytes(chunk_size=4096):
                    raw.extend(chunk)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise RelayVerificationError("RECEIPT_TOO_LARGE")
                return bytes(raw)
    except httpx.HTTPError as exc:
        raise RelayVerificationError("RECEIVER_TRANSPORT_FAILED") from exc
