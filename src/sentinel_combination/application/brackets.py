from __future__ import annotations

from decimal import Decimal

from sentinel_combination.domain.brackets import BracketPlan
from sentinel_combination.domain.enums import Side
from sentinel_combination.domain.instruments import Instrument
from sentinel_combination.domain.orders import OrderIntent, OrderLifecycle


class BracketCoordinator:
    """Compile bracket commands only from confirmed external fills."""

    def compile_for_entry(
        self,
        *,
        plan: BracketPlan,
        instrument: Instrument,
        entry_lifecycle: OrderLifecycle,
    ) -> tuple[OrderIntent, ...]:
        if entry_lifecycle.intent.bracket_id != plan.bracket_id:
            raise ValueError("entry order does not belong to bracket")
        if entry_lifecycle.filled_quantity <= 0:
            raise ValueError("entry has no confirmed fill quantity")
        if entry_lifecycle.average_fill_price is None:
            raise ValueError("entry has no confirmed average fill price")
        return plan.compile_exit_intents(
            instrument=instrument,
            confirmed_entry_quantity=entry_lifecycle.filled_quantity,
            average_entry_price=entry_lifecycle.average_fill_price,
        )

    @staticmethod
    def net_cost_protective_price(
        *,
        side: Side,
        entry_price: Decimal,
        remaining_quantity: Decimal,
        allocated_entry_fees: Decimal,
        estimated_exit_fees: Decimal,
        contract_multiplier: Decimal,
    ) -> Decimal:
        if remaining_quantity <= 0:
            raise ValueError("remaining_quantity must be positive")
        if contract_multiplier <= 0:
            raise ValueError("contract_multiplier must be positive")
        if allocated_entry_fees < 0 or estimated_exit_fees < 0:
            raise ValueError("fees cannot be negative")
        cost_per_price_unit = (
            allocated_entry_fees + estimated_exit_fees
        ) / (remaining_quantity * contract_multiplier)
        return entry_price + (cost_per_price_unit * side.sign)
