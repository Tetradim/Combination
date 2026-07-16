from datetime import datetime, timezone
from decimal import Decimal

import pytest

from sentinel_combination.application.lifecycle import (
    apply_broker_update,
    request_cancel,
    transition,
)
from sentinel_combination.domain.enums import (
    OrderStatus,
    OrderType,
    OrderUpdateType,
    Side,
)
from sentinel_combination.domain.orders import (
    BrokerOrderUpdate,
    OrderIntent,
    OrderLifecycle,
)


def intent() -> OrderIntent:
    return OrderIntent(
        client_order_id="order-1",
        account_id="account-1",
        instrument_id="BTC-PERP",
        side=Side.BUY,
        quantity=Decimal("2"),
        order_type=OrderType.MARKET,
        strategy_id="strategy-1",
        created_at=datetime.now(timezone.utc),
    )


def update(
    kind,
    *,
    event_id,
    quantity="0",
    price=None,
    execution_id=None,
):
    return BrokerOrderUpdate(
        source="broker",
        external_event_id=event_id,
        account_id="account-1",
        instrument_id="BTC-PERP",
        client_order_id="order-1",
        update_type=kind,
        occurred_at=datetime.now(timezone.utc),
        broker_order_id="broker-1",
        execution_id=execution_id,
        fill_quantity=Decimal(quantity),
        fill_price=(
            Decimal(price)
            if price is not None
            else None
        ),
    )


def test_partial_fill_can_arrive_while_cancel_is_pending():
    lifecycle = OrderLifecycle(intent=intent())
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
        broker_order_id="broker-1",
    )
    lifecycle = transition(
        lifecycle,
        OrderStatus.WORKING,
    )
    lifecycle = request_cancel(lifecycle)

    lifecycle = apply_broker_update(
        lifecycle,
        update(
            OrderUpdateType.PARTIAL_FILL,
            event_id="event-1",
            quantity="1",
            price="100",
            execution_id="fill-1",
        ),
    )
    assert lifecycle.status is OrderStatus.PENDING_CANCEL
    assert lifecycle.filled_quantity == Decimal("1")

    lifecycle = apply_broker_update(
        lifecycle,
        update(
            OrderUpdateType.FILL,
            event_id="event-2",
            quantity="1",
            price="102",
            execution_id="fill-2",
        ),
    )
    assert lifecycle.status is OrderStatus.FILLED
    assert lifecycle.average_fill_price == Decimal("101")


def test_terminal_order_cannot_reopen():
    lifecycle = OrderLifecycle(intent=intent())
    lifecycle = transition(
        lifecycle,
        OrderStatus.REJECTED,
        reject_reason="no",
    )

    with pytest.raises(
        ValueError,
        match="invalid order transition",
    ):
        transition(
            lifecycle,
            OrderStatus.SUBMITTED,
        )
