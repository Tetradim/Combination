from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReadinessSnapshot:
    broker_connected: bool
    authenticated: bool
    account_fresh: bool
    market_data_fresh: bool
    positions_reconciled: bool
    orders_reconciled: bool
    kill_switch_clear: bool
    persistence_healthy: bool
    margin_available: bool
    instrument_tradeable: bool
    protective_order_supported: bool
    activation_authorized: bool
    evaluated_at: datetime
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.evaluated_at.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")

    @property
    def ready_for_exposure(self) -> bool:
        return all(
            (
                self.broker_connected,
                self.authenticated,
                self.account_fresh,
                self.market_data_fresh,
                self.positions_reconciled,
                self.orders_reconciled,
                self.kill_switch_clear,
                self.persistence_healthy,
                self.margin_available,
                self.instrument_tradeable,
                self.protective_order_supported,
                self.activation_authorized,
            )
        ) and not self.reasons

    def assert_ready_for_exposure(self) -> None:
        if not self.ready_for_exposure:
            detail = ", ".join(self.reasons) if self.reasons else "one or more readiness gates failed"
            raise PermissionError(f"new exposure is blocked: {detail}")
