from datetime import datetime, timezone
from decimal import Decimal

from sentinel_combination.application.fills import FillProcessor
from sentinel_combination.application.lifecycle import transition
from sentinel_combination.domain.enums import (
    AssetClass,
    OrderStatus,
    OrderType,
    OrderUpdateType,
    Side,
)
from sentinel_combination.domain.instruments import Instrument
from sentinel_combination.domain.orders import (
    BrokerOrderUpdate,
    OrderIntent,
    OrderLifecycle,
)
from sentinel_combination.storage.sqlite import SQLiteStore


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


def test_execution_idempotency_prevents_double_mutation(
    tmp_path,
):
    store = SQLiteStore(
        tmp_path / "state.sqlite3"
    )
    store.initialize()

    intent = OrderIntent(
        client_order_id="o1",
        account_id="a1",
        instrument_id="BTC-PERP",
        side=Side.BUY,
        quantity=Decimal("1"),
        order_type=OrderType.MARKET,
        strategy_id="s1",
        created_at=datetime.now(timezone.utc),
    )
    lifecycle = OrderLifecycle(intent=intent)
    lifecycle = transition(
        lifecycle,
        OrderStatus.RISK_APPROVED,
    )
    lifecycle = transition(
        lifecycle,
        OrderStatus.SUBMITTING,
    )
    lifecycle = transition(
        lifecycle,
        OrderStatus.SUBMITTED,
        broker_order_id="bo1",
    )

    with store.transaction() as transaction:
        transaction.save_order(lifecycle)

    update = BrokerOrderUpdate(
        source="broker",
        external_event_id="execution:1",
        account_id="a1",
        instrument_id="BTC-PERP",
        client_order_id="o1",
        update_type=OrderUpdateType.FILL,
        occurred_at=datetime.now(timezone.utc),
        broker_order_id="bo1",
        execution_id="execution-1",
        fill_quantity=Decimal("1"),
        fill_price=Decimal("100"),
        fee=Decimal("0.1"),
    )

    processor = FillProcessor(store)
    assert processor.process(
        update,
        instrument=instrument(),
    ) is True
    assert processor.process(
        update,
        instrument=instrument(),
    ) is False

    duplicate_execution = BrokerOrderUpdate(
        source="broker",
        external_event_id="execution:1:replayed",
        account_id="a1",
        instrument_id="BTC-PERP",
        client_order_id="o1",
        update_type=OrderUpdateType.FILL,
        occurred_at=datetime.now(timezone.utc),
        broker_order_id="bo1",
        execution_id="execution-1",
        fill_quantity=Decimal("1"),
        fill_price=Decimal("100"),
        fee=Decimal("0.1"),
    )
    assert processor.process(
        duplicate_execution,
        instrument=instrument(),
    ) is False

    with store.transaction() as transaction:
        position = transaction.get_position(
            account_id="a1",
            instrument_id="BTC-PERP",
        )
        order = transaction.get_order("o1")

    assert position is not None
    assert order is not None
    assert position.quantity == Decimal("1")
    assert position.realized_pnl == Decimal("-0.1")
    assert order.status is OrderStatus.FILLED
