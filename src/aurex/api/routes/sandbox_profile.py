from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import ValidationError

from aurex.backtest_engine.research_sandbox_capability_profile import (
    BinanceSpotTestnetSandboxInput,
)
from aurex.backtest_engine.sandbox_profile_workflow import (
    DEFAULT_OUTPUT_PATH,
    DEFAULT_REVIEW_PATH,
    SandboxProfilePreflightResponse,
    SandboxProfileStatusResponse,
    SandboxProfileTemplateResponse,
    build_sandbox_profile_preflight,
    sandbox_profile_status,
    sandbox_profile_template_response,
)

router = APIRouter(prefix="/sandbox-profile", tags=["sandbox-profile"])
MAX_SANDBOX_PROFILE_REQUEST_BYTES = 65_536
NO_STORE_HEADERS = {"Cache-Control": "no-store"}
REVIEW_PATH = DEFAULT_REVIEW_PATH
OUTPUT_PATH = DEFAULT_OUTPUT_PATH


def sanitized_validation_errors(
    error: ValidationError,
) -> list[dict[str, Any]]:
    return [
        {
            "field": ".".join(str(part) for part in item["loc"]),
            "message": item["msg"],
            "type": item["type"],
        }
        for item in error.errors()
    ]


@router.get(
    "/status",
    response_model=SandboxProfileStatusResponse,
)
def get_sandbox_profile_status(response: Response) -> SandboxProfileStatusResponse:
    response.headers.update(NO_STORE_HEADERS)
    return sandbox_profile_status(OUTPUT_PATH)


@router.get(
    "/template",
    response_model=SandboxProfileTemplateResponse,
)
def get_sandbox_profile_template(
    response: Response,
) -> SandboxProfileTemplateResponse:
    response.headers.update(NO_STORE_HEADERS)
    return sandbox_profile_template_response()


@router.post(
    "/preflight",
    response_model=SandboxProfilePreflightResponse,
)
async def preflight_sandbox_profile(
    request: Request,
    response: Response,
) -> SandboxProfilePreflightResponse:
    body = await request.body()
    if len(body) > MAX_SANDBOX_PROFILE_REQUEST_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Sandbox profile input exceeds the 64 KiB limit",
            headers=NO_STORE_HEADERS,
        )
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sandbox profile input must be one valid JSON object",
            headers=NO_STORE_HEADERS,
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sandbox profile input must be one JSON object",
            headers=NO_STORE_HEADERS,
        )
    try:
        operator_input = BinanceSpotTestnetSandboxInput.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Sandbox profile input failed validation",
                "errors": sanitized_validation_errors(exc),
            },
            headers=NO_STORE_HEADERS,
        ) from exc
    try:
        result = build_sandbox_profile_preflight(
            operator_input,
            review_path=REVIEW_PATH,
            output_path=OUTPUT_PATH,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
            headers=NO_STORE_HEADERS,
        ) from exc
    response.headers.update(NO_STORE_HEADERS)
    return result
