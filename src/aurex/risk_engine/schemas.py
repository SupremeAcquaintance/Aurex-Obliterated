from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class RiskStatusResponse(BaseModel):
    account_id: str
    account_name: str
    account_mode: str
    currency: str
    current_equity: Decimal
    risk_profile_id: str
    risk_profile_name: str
    risk_per_trade: Decimal
    max_daily_loss: Decimal
    max_weekly_loss: Decimal
    max_open_positions: int
    minimum_reward_risk: Decimal
    max_signal_age_seconds: int
    kill_switch_enabled: bool
    open_positions: int
    daily_realized_pl: Decimal
    weekly_realized_pl: Decimal

    model_config = ConfigDict(from_attributes=True)


class KillSwitchResponse(BaseModel):
    risk_profile_id: str
    kill_switch_enabled: bool

