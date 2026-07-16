from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .enums import OrderType, Side
from .events import utc_now
from .instruments import Instrument
from .orders import OrderIntent


def _validate_fraction(name: str, value: Decimal) -> None:
    if value <= 0 or value > 1:
        raise ValueError(f"{name} must be greater than zero and no more than one")


@dataclass(frozen=True)
class ProtectiveStop:
    trigger_price: Decimal

    def __post_init__(self) -> None:
        if self.trigger_price <= 0:
            raise ValueError("protective stop price must be positive")


@dataclass(frozen=True)
class TakeProfitTarget:
    trigger_price: Decimal
    close_fraction: Decimal

    def __post_init__(self) -> None:
        if self.trigger_price <= 0:
            raise ValueError("take-profit price must be positive")
        _validate_fraction("close_fraction", self.close_fraction)


@dataclass(frozen=True)
class TrailingRule:
    close_fraction: Decimal
    distance_pct: Decimal | None = None
    distance_amount: Decimal | None = None
    activation_price: Decimal | None = None
    activate_after_target_index: int | None = None
    ratchet_step: Decimal | None = None

    def __post_init__(self) -> None:
        _validate_fraction("close_fraction", self.close_fraction)
        configured = int(self.distance_pct is not None) + int(self.distance_amount is not None)
        if configured != 1:
            raise ValueError("exactly one trailing distance must be configured")
        if self.distance_pct is not None and self.distance_pct <= 0:
            raise ValueError("distance_pct must be positive")
        if self.distance_amount is not None and self.distance_amount <= 0:
            raise ValueError("distance_amount must be positive")
        if self.activation_price is not None and self.activation_price <= 0:
            raise ValueError("activation_price must be positive")
        if self.activate_after_target_index is not None and self.activate_after_target_index < 0:
            raise ValueError("activate_after_target_index cannot be negative")
        if self.ratchet_step is not None and self.ratchet_step <= 0:
            raise ValueError("ratchet_step must be positive")


@dataclass(frozen=True)
class BracketPlan:
    bracket_id: str
    schema_version: int
    semantics_version: str
    account_id: str
    instrument_id: str
    strategy_id: str
    entry_side: Side
    protective_stop: ProtectiveStop
    take_profit_targets: tuple[TakeProfitTarget, ...] = ()
    trailing_rule: TrailingRule | None = None
    move_to_net_cost_after_target: int | None = None

    def __post_init__(self) -> None:
        for name in ("bracket_id", "semantics_version", "account_id", "instrument_id", "strategy_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} is required")
        if self.schema_version <= 0:
            raise ValueError("schema_version must be positive")
        allocated = sum((target.close_fraction for target in self.take_profit_targets), Decimal("0"))
        if allocated > 1:
            raise ValueError("take-profit allocations cannot exceed the filled entry quantity")
        if self.move_to_net_cost_after_target is not None:
            if self.move_to_net_cost_after_target < 0:
                raise ValueError("move_to_net_cost_after_target cannot be negative")
            if self.move_to_net_cost_after_target >= len(self.take_profit_targets):
                raise ValueError("move_to_net_cost_after_target references a missing target")

    def validate_against_entry(self, entry_price: Decimal) -> None:
        if entry_price <= 0:
            raise ValueError("entry_price must be positive")
        stop = self.protective_stop.trigger_price
        if self.entry_side is Side.BUY:
            if stop >= entry_price:
                raise ValueError("long protective stop must be below entry")
            if any(target.trigger_price <= entry_price for target in self.take_profit_targets):
                raise ValueError("long take-profit targets must be above entry")
            if any(later.trigger_price <= earlier.trigger_price for earlier, later in zip(self.take_profit_targets, self.take_profit_targets[1:])):
                raise ValueError("long take-profit targets must be strictly increasing")
        else:
            if stop <= entry_price:
                raise ValueError("short protective stop must be above entry")
            if any(target.trigger_price >= entry_price for target in self.take_profit_targets):
                raise ValueError("short take-profit targets must be below entry")
            if any(later.trigger_price >= earlier.trigger_price for earlier, later in zip(self.take_profit_targets, self.take_profit_targets[1:])):
                raise ValueError("short take-profit targets must be strictly decreasing")

    def compile_exit_intents(
        self,
        *,
        instrument: Instrument,
        confirmed_entry_quantity: Decimal,
        average_entry_price: Decimal,
    ) -> tuple[OrderIntent, ...]:
        if instrument.instrument_id != self.instrument_id:
            raise ValueError("instrument does not match bracket")
        if confirmed_entry_quantity <= 0:
            raise ValueError("confirmed entry quantity must be positive")
        self.validate_against_entry(average_entry_price)

        exit_side = self.entry_side.opposite
        confirmed = instrument.quantize_quantity_down(confirmed_entry_quantity)
        if confirmed <= 0:
            raise ValueError("confirmed entry quantity rounds to zero")

        intents: list[OrderIntent] = [
            OrderIntent(
                client_order_id=f"{self.bracket_id}:stop",
                account_id=self.account_id,
                instrument_id=self.instrument_id,
                side=exit_side,
                quantity=confirmed,
                order_type=OrderType.STOP,
                stop_price=instrument.quantize_price(self.protective_stop.trigger_price),
                reduce_only=True,
                strategy_id=self.strategy_id,
                bracket_id=self.bracket_id,
                oca_group_id=f"{self.bracket_id}:exits",
                created_at=utc_now(),
            )
        ]

        allocated_quantity = Decimal("0")
        for index, target in enumerate(self.take_profit_targets):
            raw = confirmed * target.close_fraction
            quantity = instrument.quantize_quantity_down(raw)
            if quantity <= 0:
                raise ValueError(f"target {index} quantity rounds to zero")
            allocated_quantity += quantity
            intents.append(
                OrderIntent(
                    client_order_id=f"{self.bracket_id}:tp:{index}",
                    account_id=self.account_id,
                    instrument_id=self.instrument_id,
                    side=exit_side,
                    quantity=quantity,
                    order_type=OrderType.LIMIT,
                    limit_price=instrument.quantize_price(target.trigger_price),
                    reduce_only=True,
                    strategy_id=self.strategy_id,
                    bracket_id=self.bracket_id,
                    parent_order_id=f"{self.bracket_id}:entry",
                    oca_group_id=f"{self.bracket_id}:exits",
                    created_at=utc_now(),
                )
            )
        if allocated_quantity > confirmed:
            raise AssertionError("compiled targets exceed confirmed entry quantity")
        return tuple(intents)
