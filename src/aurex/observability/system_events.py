from datetime import datetime

from sqlalchemy.orm import Session

from aurex.db.base import utc_now
from aurex.db.models import SystemEvent
from aurex.domain.enums import SystemEventSeverity


class SystemEventRecorder:
    def __init__(self, session: Session) -> None:
        self.session = session

    def info(
        self,
        category: str,
        message: str,
        metadata: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> SystemEvent:
        return self.record(
            severity=SystemEventSeverity.INFO,
            category=category,
            message=message,
            metadata=metadata,
            occurred_at=occurred_at,
        )

    def warning(
        self,
        category: str,
        message: str,
        metadata: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> SystemEvent:
        return self.record(
            severity=SystemEventSeverity.WARNING,
            category=category,
            message=message,
            metadata=metadata,
            occurred_at=occurred_at,
        )

    def record(
        self,
        severity: SystemEventSeverity,
        category: str,
        message: str,
        metadata: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> SystemEvent:
        event = SystemEvent(
            severity=severity,
            category=category,
            message=message,
            metadata_json=metadata or {},
            occurred_at=occurred_at or utc_now(),
        )
        self.session.add(event)
        return event

