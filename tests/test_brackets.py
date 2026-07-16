from datetime import datetime, timezone
from decimal import Decimal

from sentinel_combination.application.brackets import BracketCoordinator
from sentinel_combination.domain.brackets import (
    BracketPlan,
    ProtectiveStop,
    TakeProfitTarget,
)
from sentinel_combination.domain.enums import (
    AssetClass,
    OrderStatus,
    OrderType,
    Side,
)
from sentinel_combination.domain.instruments import Instrument
from sentinel_combination.domain.orders import (
    OrderIntent,
    OrderLifecycle,
)


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


def test_bracket_exits_use_confirmed_fill_quantity():
    item = instrument()
    plan = BracketPlan(
        bracket_id="b1",
        schema_version=1,
        semantics_version="1.0",
        account_id="a",
        instrument_id=item.instrument_id,
        strategy_id="s",
        entry_side=Side.BUY,
        protective_stop=ProtectiveStop(
            Decimal("95")
        ),
        take_profit_targets=(
            TakeProfitTarget(
                Decimal("104"),
                Decimal("0.5"),
            ),
            TakeProfitTarget(
                Decimal("108"),
                Decimal("0.5"),
            ),
        ),
    )
    entry = OrderLifecycle(
        intent=OrderIntent(
            client_order_id="b1:entry",
            account_id="a",
            instrument_id=item.instrument_id,
            side=Side.BUY,
            quantity=Decimal("2"),
            order_type=OrderType.MARKET,
            strategy_id="s",
            bracket_id="b1",
            created_at=datetime.now(timezone.utc),
        ),
        status=OrderStatus.PARTIALLY_FILLED,
        filled_quantity=Decimal("1.2"),
        average_fill_price=Decimal("100"),
    )

    exits = BracketCoordinator().compile_for_entry(
        plan=plan,
        instrument=item,
        entry_lifecycle=entry,
    )

    assert exits[0].quantity == Decimal("1.2")
    assert exits[0].reduce_only is True
    assert [
        order.quantity
        for order in exits[1:]
    ] == [
        Decimal("0.600"),
        Decimal("0.600"),
    ]
