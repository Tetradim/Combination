from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Callable, Iterable, Protocol, Sequence

from sentinel_combination.domain.enums import AssetClass, OrderStatus, Side
from sentinel_combination.domain.orders import BrokerOrderUpdate, OrderIntent


class BrokerError(RuntimeError):
    """Base class for an adapter-level failure."""


class BrokerAuthenticationError(BrokerError):
    pass


class BrokerRejected(BrokerError):
    def __init__(self, reason: str, *, code: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code


class BrokerUnknownOutcome(BrokerError):
    """The broker may have accepted an order but the result is unknown."""


class BrokerUnsupported(BrokerError):
    pass


@dataclass(frozen=True)
class BrokerCapabilities:
    durable_stop_orders: bool
    native_oco: bool
    native_trailing_stop: bool
    cancel_replace: bool
    margin_preview: bool
    streaming_order_updates: bool
    reduce_only: bool = True
    native_bracket: bool = False
    supports_futures: bool = False
    supports_crypto_derivatives: bool = False
    broker_managed_test_environment: bool = False
    asset_classes: tuple[AssetClass, ...] = ()


@dataclass(frozen=True)
class AccountSnapshot:
    account_id: str
    equity: Decimal
    available_buying_power: Decimal
    captured_at: datetime
    currency: str = "USD"
    initial_margin_used: Decimal = Decimal("0")
    maintenance_margin_used: Decimal = Decimal("0")


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


@dataclass(frozen=True)
class BrokerPosition:
    account_id: str
    instrument_id: str
    quantity: Decimal
    average_entry_price: Decimal
    captured_at: datetime


@dataclass(frozen=True)
class BrokerOrderSnapshot:
    account_id: str
    instrument_id: str
    client_order_id: str
    broker_order_id: str
    status: OrderStatus
    side: Side
    quantity: Decimal
    filled_quantity: Decimal
    average_fill_price: Decimal | None
    captured_at: datetime
    reduce_only: bool = False


OrderUpdateHandler = Callable[[BrokerOrderUpdate], None]


class BrokerPort(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def environment(self) -> str: ...

    @property
    def capabilities(self) -> BrokerCapabilities: ...

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def is_connected(self) -> bool: ...

    def submit_order(self, intent: OrderIntent) -> BrokerSubmitResult: ...

    def cancel_order(
        self,
        *,
        account_id: str,
        client_order_id: str,
        broker_order_id: str,
    ) -> None: ...

    def replace_order(
        self,
        *,
        lifecycle_client_order_id: str,
        broker_order_id: str,
        replacement: OrderIntent,
    ) -> BrokerSubmitResult: ...

    def get_account_snapshot(self, account_id: str) -> AccountSnapshot: ...

    def get_market_snapshot(self, instrument_id: str) -> MarketSnapshot: ...

    def get_positions(self, account_id: str) -> Sequence[BrokerPosition]: ...

    def get_open_orders(self, account_id: str) -> Sequence[BrokerOrderSnapshot]: ...

    def get_order(
        self,
        *,
        account_id: str,
        client_order_id: str,
        broker_order_id: str | None = None,
    ) -> BrokerOrderSnapshot | None: ...

    def estimate_margin(self, intent: OrderIntent) -> MarginEstimate: ...

    def poll_order_updates(self, account_id: str) -> Iterable[BrokerOrderUpdate]: ...
