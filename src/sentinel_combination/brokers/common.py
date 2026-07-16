from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from sentinel_combination.domain.enums import OrderStatus, OrderType, OrderUpdateType, Side
from sentinel_combination.domain.orders import BrokerOrderUpdate, OrderIntent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def decimal(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def status_from_text(value: str) -> OrderStatus:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    mapping = {
        "new": OrderStatus.WORKING,
        "open": OrderStatus.WORKING,
        "working": OrderStatus.WORKING,
        "accepted": OrderStatus.ACKNOWLEDGED,
        "acknowledged": OrderStatus.ACKNOWLEDGED,
        "submitted": OrderStatus.SUBMITTED,
        "partially_filled": OrderStatus.PARTIALLY_FILLED,
        "partial_fill": OrderStatus.PARTIALLY_FILLED,
        "partiallyfilled": OrderStatus.PARTIALLY_FILLED,
        "filled": OrderStatus.FILLED,
        "done": OrderStatus.FILLED,
        "canceled": OrderStatus.CANCELED,
        "cancelled": OrderStatus.CANCELED,
        "rejected": OrderStatus.REJECTED,
        "expired": OrderStatus.EXPIRED,
        "inactive": OrderStatus.REJECTED,
        "pending_cancel": OrderStatus.PENDING_CANCEL,
    }
    return mapping.get(normalized, OrderStatus.RECONCILIATION_REQUIRED)


def update_type_for_status(status: OrderStatus) -> OrderUpdateType:
    mapping = {
        OrderStatus.ACKNOWLEDGED: OrderUpdateType.ACKNOWLEDGED,
        OrderStatus.SUBMITTED: OrderUpdateType.ACKNOWLEDGED,
        OrderStatus.WORKING: OrderUpdateType.WORKING,
        OrderStatus.PARTIALLY_FILLED: OrderUpdateType.PARTIAL_FILL,
        OrderStatus.FILLED: OrderUpdateType.FILL,
        OrderStatus.CANCELED: OrderUpdateType.CANCELED,
        OrderStatus.REJECTED: OrderUpdateType.REJECTED,
        OrderStatus.EXPIRED: OrderUpdateType.EXPIRED,
    }
    if status not in mapping:
        raise ValueError(f"no broker update type for status {status.value}")
    return mapping[status]


def ccxt_order_type(intent: OrderIntent) -> str:
    return {
        OrderType.MARKET: "market",
        OrderType.LIMIT: "limit",
        OrderType.STOP: "market",
        OrderType.STOP_LIMIT: "limit",
        OrderType.TRAILING_STOP: "market",
    }[intent.order_type]


def parse_iso(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000
        return datetime.fromtimestamp(number, tz=timezone.utc)
    text = str(value or "")
    if not text:
        return utc_now()
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
