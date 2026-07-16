from decimal import Decimal

import pytest

from sentinel_combination.domain.enums import AssetClass
from sentinel_combination.domain.instruments import Instrument


def instrument() -> Instrument:
    return Instrument(
        instrument_id="CME:ES:2026-09",
        asset_class=AssetClass.LISTED_FUTURE,
        venue="CME",
        symbol="ESU6",
        price_increment=Decimal("0.25"),
        quantity_increment=Decimal("1"),
        minimum_quantity=Decimal("1"),
        minimum_notional=Decimal("1"),
        contract_multiplier=Decimal("50"),
    )


def test_instrument_enforces_tick_and_quantity_rules():
    item = instrument()
    assert item.quantize_price(
        Decimal("6000.13")
    ) == Decimal("6000.25")
    assert item.quantize_quantity_down(
        Decimal("2.9")
    ) == Decimal("2")

    with pytest.raises(
        ValueError,
        match="quantity is not aligned",
    ):
        item.validate_order_values(
            quantity=Decimal("1.5"),
            reference_price=Decimal("6000.25"),
        )
