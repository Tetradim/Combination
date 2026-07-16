from datetime import datetime, timezone
from decimal import Decimal

from sentinel_combination.application.risk import (
    RiskContext,
    RiskLimits,
    evaluate_order_risk,
)
from sentinel_combination.domain.enums import AssetClass, OrderType, Side
from sentinel_combination.domain.instruments import Instrument
from sentinel_combination.domain.orders import OrderIntent


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


def limits() -> RiskLimits:
    return RiskLimits(
        maximum_order_notional=Decimal("100000"),
        maximum_position_notional=Decimal("100000"),
        maximum_margin_fraction=Decimal("0.5"),
        maximum_daily_loss=Decimal("5000"),
        maximum_spread_bps=Decimal("20"),
    )


def test_reduce_only_cannot_increase_or_reverse_exposure():
    intent = OrderIntent(
        client_order_id="reduce-1",
        account_id="a1",
        instrument_id="BTC-PERP",
        side=Side.SELL,
        quantity=Decimal("2"),
        order_type=OrderType.MARKET,
        strategy_id="s1",
        reduce_only=True,
        created_at=datetime.now(timezone.utc),
    )
    context = RiskContext(
        reference_price=Decimal("100"),
        current_position_quantity=Decimal("1"),
        account_equity=Decimal("100000"),
        available_buying_power=Decimal("100000"),
        initial_margin_required=Decimal("0"),
        realized_pnl_today=Decimal("0"),
        spread_bps=Decimal("1"),
    )

    decision = evaluate_order_risk(
        intent=intent,
        instrument=instrument(),
        context=context,
        limits=limits(),
    )
    assert decision.approved is False
    assert "reduce-only order exceeds the open position" in decision.reasons
