from decimal import Decimal

from sentinel_combination.domain.enums import AssetClass, Side
from sentinel_combination.domain.instruments import Instrument
from sentinel_combination.domain.positions import Position


def instrument() -> Instrument:
    return Instrument(
        instrument_id="BTC-PERP",
        asset_class=AssetClass.CRYPTO_PERPETUAL,
        venue="VENUE",
        symbol="BTCUSDT",
        price_increment=Decimal("0.1"),
        quantity_increment=Decimal("0.001"),
        minimum_quantity=Decimal("0.001"),
        minimum_notional=Decimal("1"),
    )


def test_position_ledger_handles_reduction_and_side_flip():
    item = instrument()
    position = Position(
        account_id="a",
        instrument_id=item.instrument_id,
    )

    position = position.apply_fill(
        side=Side.BUY,
        quantity=Decimal("2"),
        price=Decimal("100"),
        fee=Decimal("1"),
        instrument=item,
    )
    assert position.quantity == Decimal("2")
    assert position.realized_pnl == Decimal("-1")

    position = position.apply_fill(
        side=Side.SELL,
        quantity=Decimal("3"),
        price=Decimal("110"),
        fee=Decimal("1"),
        instrument=item,
    )
    assert position.quantity == Decimal("-1")
    assert position.average_entry_price == Decimal("110")
    assert position.realized_pnl == Decimal("18")
    assert position.fees_paid == Decimal("2")
