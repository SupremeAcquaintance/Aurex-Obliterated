import secrets
from hashlib import sha256
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.config.settings import Settings, get_settings
from aurex.signal_gateway.schemas import SignalResponse, TradingViewSignalPayload
from aurex.signal_gateway.service import SignalIntakeService, WebhookDeliveryContext
from aurex.signal_gateway.tradingview_delivery import (
    has_forwarding_headers,
    tradingview_origin_status,
    tradingview_source_network_snapshot,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
DbSession = Annotated[Session, Depends(get_db)]
WebhookSecret = Annotated[str | None, Header(alias="X-Aurex-Webhook-Secret")]
WebhookQuerySecret = Annotated[str | None, Query(alias="secret")]


@router.post(
    "/tradingview",
    response_model=SignalResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_tradingview_webhook(
    payload: TradingViewSignalPayload,
    db: DbSession,
    http_response: Response,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    webhook_secret: WebhookSecret = None,
    webhook_query_secret: WebhookQuerySecret = None,
) -> SignalResponse | JSONResponse:
    if not valid_webhook_secret(settings.webhook_secret, webhook_secret, webhook_query_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )

    if has_forwarding_headers(request.headers):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forwarded requests cannot establish direct TradingView origin",
        )

    raw_body = await request.body()
    source_networks = tradingview_source_network_snapshot(
        settings.tradingview_webhook_source_networks
    )
    delivery_context = WebhookDeliveryContext(
        authentication_status="SHARED_SECRET_VALIDATED",
        authentication_transport=authentication_transport(
            webhook_secret,
            webhook_query_secret,
        ),
        request_method=request.method,
        request_path=request.url.path,
        content_type=request.headers.get("content-type"),
        body_sha256=sha256(raw_body).hexdigest(),
        body_size_bytes=len(raw_body),
        remote_ip=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
        origin_status=tradingview_origin_status(
            request.client.host if request.client is not None else None,
            source_networks,
        ),
        source_network_configuration_status=source_networks.configuration_status,
        source_networks=source_networks.networks,
        source_networks_sha256=source_networks.networks_sha256,
        source_networks_authority_url=source_networks.authority_url,
    )
    result = SignalIntakeService(db, settings).ingest_tradingview(
        payload,
        delivery_context=delivery_context,
    )
    signal_response = SignalResponse.model_validate(result.signal)
    headers = delivery_headers(result, settings.webhook_processing_budget_ms)

    if result.is_duplicate:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=jsonable_encoder(signal_response),
            headers=headers,
        )

    for name, value in headers.items():
        http_response.headers[name] = value
    return signal_response


def valid_webhook_secret(
    expected_secret: str,
    header_secret: str | None,
    query_secret: str | None,
) -> bool:
    candidates = [
        candidate
        for candidate in (header_secret, query_secret)
        if candidate is not None and candidate != ""
    ]
    return bool(candidates) and all(
        secrets.compare_digest(candidate.encode("utf-8"), expected_secret.encode("utf-8"))
        for candidate in candidates
    )


def authentication_transport(header_secret: str | None, query_secret: str | None) -> str:
    if header_secret and query_secret:
        return "header_and_query"
    if header_secret:
        return "header"
    if query_secret:
        return "query"
    return "none"


def delivery_headers(result, processing_budget_ms: int) -> dict[str, str]:
    return {
        "Cache-Control": "no-store",
        "X-Aurex-Signal-Id": result.signal.id,
        "X-Aurex-Idempotency-Key": result.signal.idempotency_key,
        "X-Aurex-Processing-Ms": format(result.processing_duration_ms, "f"),
        "X-Aurex-Processing-Budget-Ms": str(processing_budget_ms),
        "X-Aurex-Processing-Budget-Status": (
            "within" if result.within_processing_budget else "exceeded"
        ),
    }
