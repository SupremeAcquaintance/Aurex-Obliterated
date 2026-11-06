from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import ValidationError

from aurex.backtest_engine.operator_profile_workflow import (
    DEFAULT_OUTPUT_PATH,
    DEFAULT_REVIEW_PATH,
    OperatorProfilePreflightResponse,
    OperatorProfileStatusResponse,
    OperatorProfileTemplateResponse,
    build_operator_profile_preflight,
    operator_profile_status,
    operator_profile_template_response,
)
from aurex.backtest_engine.research_operator_access_profile import (
    OperatorAccessCapitalDataInput,
)

router = APIRouter(prefix="/operator-profile", tags=["operator-profile"])
MAX_OPERATOR_PROFILE_REQUEST_BYTES = 65_536
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
    response_model=OperatorProfileStatusResponse,
)
def get_operator_profile_status(response: Response) -> OperatorProfileStatusResponse:
    response.headers.update(NO_STORE_HEADERS)
    return operator_profile_status(OUTPUT_PATH)


@router.get(
    "/template",
    response_model=OperatorProfileTemplateResponse,
)
def get_operator_profile_template(
    response: Response,
) -> OperatorProfileTemplateResponse:
    response.headers.update(NO_STORE_HEADERS)
    return operator_profile_template_response()


@router.post(
    "/preflight",
    response_model=OperatorProfilePreflightResponse,
)
async def preflight_operator_profile(
    request: Request,
    response: Response,
) -> OperatorProfilePreflightResponse:
    body = await request.body()
    if len(body) > MAX_OPERATOR_PROFILE_REQUEST_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Operator profile input exceeds the 64 KiB limit",
            headers=NO_STORE_HEADERS,
        )
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operator profile input must be one valid JSON object",
            headers=NO_STORE_HEADERS,
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operator profile input must be one JSON object",
            headers=NO_STORE_HEADERS,
        )
    try:
        operator_input = OperatorAccessCapitalDataInput.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Operator profile input failed validation",
                "errors": sanitized_validation_errors(exc),
            },
            headers=NO_STORE_HEADERS,
        ) from exc
    try:
        result = build_operator_profile_preflight(
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
