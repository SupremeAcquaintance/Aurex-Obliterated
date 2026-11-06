from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.risk_engine.schemas import KillSwitchResponse, RiskStatusResponse
from aurex.risk_engine.service import RiskEngine

router = APIRouter(prefix="/risk", tags=["risk"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/status", response_model=RiskStatusResponse)
def get_risk_status(db: DbSession) -> dict[str, object]:
    status = RiskEngine(db).risk_status()
    db.commit()
    return status


@router.post("/kill-switch", response_model=KillSwitchResponse)
def enable_kill_switch(db: DbSession) -> KillSwitchResponse:
    risk_profile = RiskEngine(db).set_kill_switch(True)
    db.commit()
    return KillSwitchResponse(
        risk_profile_id=risk_profile.id,
        kill_switch_enabled=risk_profile.kill_switch_enabled,
    )


@router.post("/kill-switch/reset", response_model=KillSwitchResponse)
def reset_kill_switch(db: DbSession) -> KillSwitchResponse:
    risk_profile = RiskEngine(db).set_kill_switch(False)
    db.commit()
    return KillSwitchResponse(
        risk_profile_id=risk_profile.id,
        kill_switch_enabled=risk_profile.kill_switch_enabled,
    )

