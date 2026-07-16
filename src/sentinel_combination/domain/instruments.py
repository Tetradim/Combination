from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from .enums import AssetClass


def _require_positive(name: str, value: Decimal) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    asset_class: AssetClass
    venue: str
    symbol: str
    price_increment: Decimal
    quantity_increment: Decimal
    minimum_quantity: Decimal
    minimum_notional: Decimal
    contract_multiplier: Decimal = Decimal("1")
    settlement_currency: str | None = None
    expiry: str | None = None
    first_notice_date: str | None = None
    last_trade_date: str | None = None
    last_safe_trade_date: str | None = None

    def __post_init__(self) -> None:
        for name in ("instrument_id", "venue", "symbol"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} is required")
        _require_positive("price_increment", self.price_increment)
        _require_positive("quantity_increment", self.quantity_increment)
        _require_positive("minimum_quantity", self.minimum_quantity)
        _require_positive("contract_multiplier", self.contract_multiplier)
        if self.minimum_notional < 0:
            raise ValueError("minimum_notional cannot be negative")

    def quantize_price(self, value: Decimal) -> Decimal:
        steps = (value / self.price_increment).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return steps * self.price_increment

    def quantize_quantity_down(self, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("quantity cannot be negative")
        steps = (value / self.quantity_increment).quantize(Decimal("1"), rounding=ROUND_DOWN)
        return steps * self.quantity_increment

    def notional(self, *, price: Decimal, quantity: Decimal) -> Decimal:
        return abs(price * quantity * self.contract_multiplier)

    def validate_order_values(self, *, quantity: Decimal, reference_price: Decimal) -> None:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.quantize_quantity_down(quantity) != quantity:
            raise ValueError("quantity is not aligned to instrument increment")
        if quantity < self.minimum_quantity:
            raise ValueError("quantity is below minimum_quantity")
        if reference_price <= 0:
            raise ValueError("reference_price must be positive")
        if self.quantize_price(reference_price) != reference_price:
            raise ValueError("price is not aligned to instrument increment")
        if self.notional(price=reference_price, quantity=quantity) < self.minimum_notional:
            raise ValueError("order notional is below minimum_notional")
