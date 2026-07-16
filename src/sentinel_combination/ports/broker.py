from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol, Sequence

from sentinel_combination.domain.orders import OrderIntent


class BrokerError(RuntimeError):
    pass


class BrokerRejected(BrokerError):
    def __init__(self, reason: str, *, code: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code


class BrokerUnknownOutcome(BrokerError):
    pass


@dataclass(frozen=True)
class BrokerCapabilities:
    durable_stop_orders: bool
    native_oco: bool
    native_trailing_stop: bool
    cancel_replace: bool
    margin_preview: bool
    streaming_order_updates: bool


@dataclass(frozen=True)
class AccountSnapshot:
    account_id: str
    equity: Decimal
    available_buying_power: Decimal
    captured_at: datetime


@dataclass(frozen=True)
class MarketSnapshot:
    instrument_id: str
    bid: Decimal
    ask: Decimal
    mark: Decimal
    captured_at: datetime


@dataclass(frozen=True)
class MarginEstimate:
    initial_margin: Decimal
    maintenance_margin: Decimal
    source: str
    captured_at: datetime


@dataclass(frozen=True)
class BrokerSubmitResult:
    broker_order_id: str
    accepted_at: datetime


class BrokerPort(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def capabilities(self) -> BrokerCapabilities: ...

    def connect(self) -> None: ...

    def submit_order(self, intent: OrderIntent) -> BrokerSubmitResult: ...

    def cancel_order(
        self,
        *,
        account_id: str,
        client_order_id: str,
        broker_order_id: str,
    ) -> None: ...

    def get_account_snapshot(self, account_id: str) -> AccountSnapshot: ...

    def get_market_snapshot(self, instrument_id: str) -> MarketSnapshot: ...

    def get_positions(self, account_id: str) -> Sequence[object]: ...

    def get_open_orders(self, account_id: str) -> Sequence[object]: ...

    def estimate_margin(self, intent: OrderIntent) -> MarginEstimate: ...
