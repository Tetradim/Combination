from datetime import datetime, timezone
from decimal import Decimal

import pytest

from sentinel_combination.application.order_gateway import OrderGateway
from sentinel_combination.application.risk import (
    RiskContext,
    RiskLimits,
)
from sentinel_combination.domain.enums import (
    AssetClass,
    OrderStatus,
    OrderType,
    Side,
)
from sentinel_combination.domain.instruments import Instrument
from sentinel_combination.domain.orders import OrderIntent
from sentinel_combination.domain.readiness import ReadinessSnapshot
from sentinel_combination.ports.broker import (
    BrokerCapabilities,
    BrokerSubmitResult,
)
from sentinel_combination.storage.sqlite import SQLiteStore


class RecordingBroker:
    name = "recording-test-broker"
    capabilities = BrokerCapabilities(
        durable_stop_orders=True,
        native_oco=True,
        native_trailing_stop=True,
        cancel_replace=True,
        margin_preview=True,
        streaming_order_updates=True,
    )

    def __init__(self) -> None:
        self.submitted = []

    def submit_order(self, intent):
        self.submitted.append(intent)
        return BrokerSubmitResult(
            broker_order_id="broker-order-1",
            accepted_at=datetime.now(timezone.utc),
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


def readiness(**overrides) -> ReadinessSnapshot:
    values = {
        "broker_connected": True,
        "authenticated": True,
        "account_fresh": True,
        "market_data_fresh": True,
        "positions_reconciled": True,
        "orders_reconciled": True,
        "kill_switch_clear": True,
        "persistence_healthy": True,
        "margin_available": True,
        "instrument_tradeable": True,
        "protective_order_supported": True,
        "activation_authorized": True,
        "evaluated_at": datetime.now(timezone.utc),
        "reasons": (),
    }
    values.update(overrides)
    return ReadinessSnapshot(**values)


def test_gateway_blocks_failed_readiness_before_broker_call(
    tmp_path,
):
    store = SQLiteStore(
        tmp_path / "db.sqlite3"
    )
    store.initialize()
    broker = RecordingBroker()
    gateway = OrderGateway(
        store=store,
        broker=broker,
    )
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
    risk_context = RiskContext(
        reference_price=Decimal("100"),
        current_position_quantity=Decimal("0"),
        account_equity=Decimal("100000"),
        available_buying_power=Decimal("100000"),
        initial_margin_required=Decimal("1000"),
        realized_pnl_today=Decimal("0"),
        spread_bps=Decimal("1"),
    )
    limits = RiskLimits(
        maximum_order_notional=Decimal("10000"),
        maximum_position_notional=Decimal("20000"),
        maximum_margin_fraction=Decimal("0.5"),
        maximum_daily_loss=Decimal("5000"),
        maximum_spread_bps=Decimal("20"),
    )

    with pytest.raises(PermissionError):
        gateway.submit(
            intent=intent,
            instrument=instrument(),
            readiness=readiness(
                positions_reconciled=False,
            ),
            risk_context=risk_context,
            risk_limits=limits,
        )

    assert broker.submitted == []

    lifecycle = gateway.submit(
        intent=intent,
        instrument=instrument(),
        readiness=readiness(),
        risk_context=risk_context,
        risk_limits=limits,
    )

    assert lifecycle.status is OrderStatus.SUBMITTED
    assert lifecycle.broker_order_id == "broker-order-1"
    assert broker.submitted == [intent]
