from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal

from .enums import OrderStatus, OrderType, OrderUpdateType, Side
from .events import utc_now


@dataclass(frozen=True)
class OrderIntent:
    client_order_id: str
    account_id: str
    instrument_id: str
    side: Side
    quantity: Decimal
    order_type: OrderType
    strategy_id: str
    created_at: datetime
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    reduce_only: bool = False
    bracket_id: str | None = None
    parent_order_id: str | None = None
    oca_group_id: str | None = None
    time_in_force: str = "GTC"
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("client_order_id", "account_id", "instrument_id", "strategy_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} is required")
        if not self.time_in_force.strip():
            raise ValueError("time_in_force is required")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.order_type in {OrderType.LIMIT, OrderType.STOP_LIMIT} and self.limit_price is None:
            raise ValueError("limit_price is required for limit orders")
        if self.order_type in {OrderType.STOP, OrderType.STOP_LIMIT} and self.stop_price is None:
            raise ValueError("stop_price is required for stop orders")
        if self.limit_price is not None and self.limit_price <= 0:
            raise ValueError("limit_price must be positive")
        if self.stop_price is not None and self.stop_price <= 0:
            raise ValueError("stop_price must be positive")


@dataclass(frozen=True)
class OrderLifecycle:
    intent: OrderIntent
    status: OrderStatus = OrderStatus.PLANNED
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Decimal | None = None
    broker_order_id: str | None = None
    reject_reason: str | None = None
    last_update_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.filled_quantity < 0:
            raise ValueError("filled_quantity cannot be negative")
        if self.filled_quantity > self.intent.quantity:
            raise ValueError("filled_quantity cannot exceed requested quantity")
        if self.filled_quantity > 0 and self.average_fill_price is None:
            raise ValueError("average_fill_price is required after a fill")
        if self.average_fill_price is not None and self.average_fill_price <= 0:
            raise ValueError("average_fill_price must be positive")

    @property
    def remaining_quantity(self) -> Decimal:
        return self.intent.quantity - self.filled_quantity

    def with_status(
        self,
        status: OrderStatus,
        *,
        broker_order_id: str | None = None,
        reject_reason: str | None = None,
        at: datetime | None = None,
    ) -> "OrderLifecycle":
        return replace(
            self,
            status=status,
            broker_order_id=broker_order_id if broker_order_id is not None else self.broker_order_id,
            reject_reason=reject_reason,
            last_update_at=at or utc_now(),
        )


@dataclass(frozen=True)
class BrokerOrderUpdate:
    source: str
    external_event_id: str
    account_id: str
    instrument_id: str
    client_order_id: str
    update_type: OrderUpdateType
    occurred_at: datetime
    broker_order_id: str | None = None
    execution_id: str | None = None
    fill_quantity: Decimal = Decimal("0")
    fill_price: Decimal | None = None
    cumulative_filled_quantity: Decimal | None = None
    fee: Decimal = Decimal("0")
    reason: str | None = None

    def __post_init__(self) -> None:
        for name in ("source", "external_event_id", "account_id", "instrument_id", "client_order_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} is required")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.fill_quantity < 0:
            raise ValueError("fill_quantity cannot be negative")
        if self.fee < 0:
            raise ValueError("fee cannot be negative")
        is_fill = self.update_type in {OrderUpdateType.PARTIAL_FILL, OrderUpdateType.FILL}
        if is_fill:
            if not self.execution_id or not self.execution_id.strip():
                raise ValueError("execution_id is required for fill updates")
            if self.fill_quantity <= 0:
                raise ValueError("fill_quantity must be positive for fill updates")
            if self.fill_price is None or self.fill_price <= 0:
                raise ValueError("fill_price must be positive for fill updates")
        elif self.fill_quantity != 0 or self.fill_price is not None or self.execution_id is not None:
            raise ValueError("fill fields are only valid for fill updates")
