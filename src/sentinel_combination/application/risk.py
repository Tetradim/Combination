from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sentinel_combination.domain.instruments import Instrument
from sentinel_combination.domain.orders import OrderIntent


@dataclass(frozen=True)
class RiskLimits:
    maximum_order_notional: Decimal
    maximum_position_notional: Decimal
    maximum_margin_fraction: Decimal
    maximum_daily_loss: Decimal
    maximum_spread_bps: Decimal

    def __post_init__(self) -> None:
        if self.maximum_order_notional <= 0:
            raise ValueError("maximum_order_notional must be positive")
        if self.maximum_position_notional <= 0:
            raise ValueError("maximum_position_notional must be positive")
        if self.maximum_margin_fraction <= 0 or self.maximum_margin_fraction > 1:
            raise ValueError("maximum_margin_fraction must be in (0, 1]")
        if self.maximum_daily_loss <= 0:
            raise ValueError("maximum_daily_loss must be positive")
        if self.maximum_spread_bps < 0:
            raise ValueError("maximum_spread_bps cannot be negative")


@dataclass(frozen=True)
class RiskContext:
    reference_price: Decimal
    current_position_quantity: Decimal
    account_equity: Decimal
    available_buying_power: Decimal
    initial_margin_required: Decimal
    realized_pnl_today: Decimal
    spread_bps: Decimal


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: tuple[str, ...]
    order_notional: Decimal
    projected_position_notional: Decimal


def evaluate_order_risk(
    *,
    intent: OrderIntent,
    instrument: Instrument,
    context: RiskContext,
    limits: RiskLimits,
) -> RiskDecision:
    instrument.validate_order_values(
        quantity=intent.quantity,
        reference_price=context.reference_price,
    )
    order_notional = instrument.notional(
        price=context.reference_price,
        quantity=intent.quantity,
    )
    projected_quantity = context.current_position_quantity + (intent.quantity * intent.side.sign)
    projected_position_notional = instrument.notional(
        price=context.reference_price,
        quantity=projected_quantity,
    )
    reasons: list[str] = []

    if not intent.reduce_only and order_notional > limits.maximum_order_notional:
        reasons.append("order notional exceeds limit")
    if not intent.reduce_only and projected_position_notional > limits.maximum_position_notional:
        reasons.append("projected position notional exceeds limit")
    if context.realized_pnl_today <= -limits.maximum_daily_loss:
        reasons.append("daily loss limit reached")
    if context.spread_bps > limits.maximum_spread_bps:
        reasons.append("spread exceeds limit")
    if not intent.reduce_only:
        if context.initial_margin_required < 0:
            reasons.append("margin estimate is invalid")
        elif context.initial_margin_required > context.available_buying_power:
            reasons.append("insufficient buying power")
        elif context.account_equity <= 0:
            reasons.append("account equity is unavailable")
        elif context.initial_margin_required / context.account_equity > limits.maximum_margin_fraction:
            reasons.append("margin fraction exceeds limit")

    return RiskDecision(
        approved=not reasons,
        reasons=tuple(reasons),
        order_notional=order_notional,
        projected_position_notional=projected_position_notional,
    )
