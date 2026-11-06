from datetime import datetime

from pydantic import BaseModel, ConfigDict

from aurex.domain.enums import SystemEventSeverity


class SystemEventResponse(BaseModel):
    id: str
    severity: SystemEventSeverity
    category: str
    message: str
    metadata_json: dict
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)

