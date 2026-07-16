from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from .enums import Side
from .events import utc_now
from .instruments import Instrument


@dataclass(frozen=True)
class Position:
    account_id: str
    instrument_id: str
    quantity: Decimal = Decimal("0")
    average_entry_price: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    fees_paid: Decimal = Decimal("0")
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.account_id.strip() or not self.instrument_id.strip():
            raise ValueError("account_id and instrument_id are required")
        if self.quantity == 0 and self.average_entry_price != 0:
            raise ValueError("flat position must have zero average entry price")
        if self.quantity != 0 and self.average_entry_price <= 0:
            raise ValueError("open position must have positive average entry price")
        if self.fees_paid < 0:
            raise ValueError("fees_paid cannot be negative")

    def apply_fill(
        self,
        *,
        side: Side,
        quantity: Decimal,
        price: Decimal,
        fee: Decimal,
        instrument: Instrument,
        at: datetime | None = None,
    ) -> "Position":
        if quantity <= 0:
            raise ValueError("fill quantity must be positive")
        if price <= 0:
            raise ValueError("fill price must be positive")
        if fee < 0:
            raise ValueError("fee cannot be negative")

        signed_fill = quantity * side.sign
        current = self.quantity
        new_quantity = current + signed_fill
        realized_delta = Decimal("0")
        average = self.average_entry_price

        if current == 0:
            average = price
        elif current * signed_fill > 0:
            total_abs = abs(current) + abs(signed_fill)
            average = ((abs(current) * average) + (abs(signed_fill) * price)) / total_abs
        else:
            closing_quantity = min(abs(current), abs(signed_fill))
            direction = Decimal("1") if current > 0 else Decimal("-1")
            realized_delta = (
                (price - average)
                * closing_quantity
                * direction
                * instrument.contract_multiplier
            )
            if new_quantity == 0:
                average = Decimal("0")
            elif current * new_quantity < 0:
                average = price

        return replace(
            self,
            quantity=new_quantity,
            average_entry_price=average,
            realized_pnl=self.realized_pnl + realized_delta - fee,
            fees_paid=self.fees_paid + fee,
            updated_at=at or utc_now(),
        )
