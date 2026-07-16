from __future__ import annotations

from enum import Enum


class AssetClass(str, Enum):
    CRYPTO_SPOT = "crypto_spot"
    CRYPTO_PERPETUAL = "crypto_perpetual"
    LISTED_FUTURE = "listed_future"


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"

    @property
    def sign(self) -> int:
        return 1 if self is Side.BUY else -1

    @property
    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(str, Enum):
    PLANNED = "planned"
    RISK_APPROVED = "risk_approved"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    WORKING = "working"
    PARTIALLY_FILLED = "partially_filled"
    PENDING_CANCEL = "pending_cancel"
    CANCELED = "canceled"
    FILLED = "filled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    RECONCILIATION_REQUIRED = "reconciliation_required"

    @property
    def terminal(self) -> bool:
        return self in {
            OrderStatus.CANCELED,
            OrderStatus.FILLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }


class OrderUpdateType(str, Enum):
    ACKNOWLEDGED = "acknowledged"
    WORKING = "working"
    PARTIAL_FILL = "partial_fill"
    FILL = "fill"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class BracketLegKind(str, Enum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIME_EXIT = "time_exit"


class KillSwitchLevel(str, Enum):
    CLEAR = "clear"
    PAUSE_ENTRIES = "pause_entries"
    CANCEL_WORKING = "cancel_working"
    FLATTEN_AND_HALT = "flatten_and_halt"
