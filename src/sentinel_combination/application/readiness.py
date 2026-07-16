from __future__ import annotations

from sentinel_combination.domain.orders import OrderIntent
from sentinel_combination.domain.readiness import ReadinessSnapshot


def require_exposure_readiness(
    intent: OrderIntent,
    readiness: ReadinessSnapshot,
) -> None:
    if intent.reduce_only:
        if not readiness.broker_connected or not readiness.authenticated:
            raise PermissionError(
                "risk-reducing order requires an authenticated broker connection"
            )
        if not readiness.persistence_healthy:
            raise PermissionError(
                "risk-reducing order blocked because persistence is unhealthy"
            )
        return
    readiness.assert_ready_for_exposure()
