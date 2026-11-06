from dataclasses import dataclass
from typing import Protocol

from aurex.config.settings import Settings
from aurex.db.models import BrokerConnection, LiveDeploymentPlan
from aurex.domain.enums import ReadinessStatus


class LiveExecutionAdapter(Protocol):
    name: str
    implemented: bool
    supports_live_order_submission: bool

    def readiness_reasons(
        self,
        *,
        settings: Settings,
        plan: LiveDeploymentPlan,
        connection: BrokerConnection | None,
    ) -> list[str]:
        """Return concrete reasons why this adapter cannot submit first-live orders."""


@dataclass(frozen=True)
class LiveExecutionAdapterAudit:
    name: str
    implemented: bool
    supports_live_order_submission: bool
    status: ReadinessStatus
    reasons: list[str]
    evidence_snapshot: dict[str, object]


class DisabledLiveExecutionAdapter:
    name = "disabled"
    implemented = False
    supports_live_order_submission = False

    def readiness_reasons(
        self,
        *,
        settings: Settings,
        plan: LiveDeploymentPlan,
        connection: BrokerConnection | None,
    ) -> list[str]:
        return ["live_execution_adapter_not_implemented"]


class UnregisteredLiveExecutionAdapter:
    implemented = False
    supports_live_order_submission = False

    def __init__(self, name: str) -> None:
        self.name = name

    def readiness_reasons(
        self,
        *,
        settings: Settings,
        plan: LiveDeploymentPlan,
        connection: BrokerConnection | None,
    ) -> list[str]:
        return [
            "live_execution_adapter_not_implemented",
            "live_execution_adapter_not_registered",
        ]


def configured_live_execution_adapter(settings: Settings) -> LiveExecutionAdapter:
    configured = settings.live_execution_adapter.strip().lower()
    if configured == "disabled":
        return DisabledLiveExecutionAdapter()
    return UnregisteredLiveExecutionAdapter(configured or "disabled")


def live_execution_adapter_audit(
    *,
    settings: Settings,
    plan: LiveDeploymentPlan,
    connection: BrokerConnection | None,
) -> LiveExecutionAdapterAudit:
    adapter = configured_live_execution_adapter(settings)
    reasons = adapter.readiness_reasons(
        settings=settings,
        plan=plan,
        connection=connection,
    )
    status = (
        ReadinessStatus.PASS
        if adapter.implemented and adapter.supports_live_order_submission and not reasons
        else ReadinessStatus.BLOCKED
    )
    evidence_snapshot = {
        "configured_adapter": settings.live_execution_adapter,
        "adapter": adapter.name,
        "implemented": adapter.implemented,
        "supports_live_order_submission": adapter.supports_live_order_submission,
        "live_trading_enabled": settings.live_trading_enabled,
        "broker_connection_id": plan.broker_connection_id,
        "connection_environment": connection.environment.value if connection else None,
        "connection_status": connection.status.value if connection else None,
        "connection_live_trading_enabled": (
            connection.live_trading_enabled if connection else None
        ),
        "reasons": reasons,
    }
    return LiveExecutionAdapterAudit(
        name=adapter.name,
        implemented=adapter.implemented,
        supports_live_order_submission=adapter.supports_live_order_submission,
        status=status,
        reasons=reasons,
        evidence_snapshot=evidence_snapshot,
    )
