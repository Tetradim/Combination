from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from sentinel_combination.domain.enums import OrderStatus, OrderUpdateType
from sentinel_combination.domain.orders import BrokerOrderUpdate, OrderLifecycle


_ALLOWED: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PLANNED: {OrderStatus.RISK_APPROVED, OrderStatus.REJECTED},
    OrderStatus.RISK_APPROVED: {OrderStatus.SUBMITTING, OrderStatus.REJECTED},
    OrderStatus.SUBMITTING: {
        OrderStatus.SUBMITTED,
        OrderStatus.REJECTED,
        OrderStatus.RECONCILIATION_REQUIRED,
    },
    OrderStatus.SUBMITTED: {
        OrderStatus.ACKNOWLEDGED,
        OrderStatus.WORKING,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.PENDING_CANCEL,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
        OrderStatus.RECONCILIATION_REQUIRED,
    },
    OrderStatus.ACKNOWLEDGED: {
        OrderStatus.WORKING,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.PENDING_CANCEL,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
        OrderStatus.RECONCILIATION_REQUIRED,
    },
    OrderStatus.WORKING: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.PENDING_CANCEL,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
        OrderStatus.RECONCILIATION_REQUIRED,
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.PENDING_CANCEL,
        OrderStatus.CANCELED,
        OrderStatus.EXPIRED,
        OrderStatus.RECONCILIATION_REQUIRED,
    },
    OrderStatus.PENDING_CANCEL: {
        OrderStatus.PENDING_CANCEL,
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.RECONCILIATION_REQUIRED,
    },
    OrderStatus.RECONCILIATION_REQUIRED: {
        OrderStatus.SUBMITTED,
        OrderStatus.ACKNOWLEDGED,
        OrderStatus.WORKING,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    },
    OrderStatus.CANCELED: set(),
    OrderStatus.FILLED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.EXPIRED: set(),
}


def transition(
    lifecycle: OrderLifecycle,
    target: OrderStatus,
    *,
    broker_order_id: str | None = None,
    reject_reason: str | None = None,
) -> OrderLifecycle:
    if target == lifecycle.status:
        return lifecycle
    if target not in _ALLOWED[lifecycle.status]:
        raise ValueError(
            f"invalid order transition: {lifecycle.status.value} -> {target.value}"
        )
    return lifecycle.with_status(
        target,
        broker_order_id=broker_order_id,
        reject_reason=reject_reason,
    )


def request_cancel(lifecycle: OrderLifecycle) -> OrderLifecycle:
    if lifecycle.status not in {
        OrderStatus.SUBMITTED,
        OrderStatus.ACKNOWLEDGED,
        OrderStatus.WORKING,
        OrderStatus.PARTIALLY_FILLED,
    }:
        raise ValueError(
            f"order cannot enter pending cancel from {lifecycle.status.value}"
        )
    if not lifecycle.broker_order_id:
        raise ValueError("broker_order_id is required before cancellation")
    return transition(lifecycle, OrderStatus.PENDING_CANCEL)


def _validate_update_identity(
    lifecycle: OrderLifecycle,
    update: BrokerOrderUpdate,
) -> None:
    if update.account_id != lifecycle.intent.account_id:
        raise ValueError("broker update account mismatch")
    if update.instrument_id != lifecycle.intent.instrument_id:
        raise ValueError("broker update instrument mismatch")
    if update.client_order_id != lifecycle.intent.client_order_id:
        raise ValueError("broker update client order mismatch")
    if lifecycle.broker_order_id and update.broker_order_id:
        if lifecycle.broker_order_id != update.broker_order_id:
            raise ValueError("broker update order ID mismatch")


def apply_broker_update(
    lifecycle: OrderLifecycle,
    update: BrokerOrderUpdate,
) -> OrderLifecycle:
    _validate_update_identity(lifecycle, update)
    broker_order_id = update.broker_order_id or lifecycle.broker_order_id

    if update.update_type is OrderUpdateType.ACKNOWLEDGED:
        return transition(
            lifecycle,
            OrderStatus.ACKNOWLEDGED,
            broker_order_id=broker_order_id,
        )
    if update.update_type is OrderUpdateType.WORKING:
        return transition(
            lifecycle,
            OrderStatus.WORKING,
            broker_order_id=broker_order_id,
        )
    if update.update_type in {
        OrderUpdateType.PARTIAL_FILL,
        OrderUpdateType.FILL,
    }:
        assert update.fill_price is not None
        new_filled = lifecycle.filled_quantity + update.fill_quantity
        if update.cumulative_filled_quantity is not None:
            if update.cumulative_filled_quantity < lifecycle.filled_quantity:
                raise ValueError("cumulative fill quantity cannot decrease")
            if update.cumulative_filled_quantity != new_filled:
                raise ValueError(
                    "incremental and cumulative fill quantities disagree"
                )
        if new_filled > lifecycle.intent.quantity:
            raise ValueError("fill exceeds requested order quantity")
        previous_notional = (
            lifecycle.filled_quantity
            * (lifecycle.average_fill_price or Decimal("0"))
        )
        updated_average = (
            previous_notional + update.fill_quantity * update.fill_price
        ) / new_filled
        if new_filled == lifecycle.intent.quantity:
            target = OrderStatus.FILLED
        elif lifecycle.status is OrderStatus.PENDING_CANCEL:
            target = OrderStatus.PENDING_CANCEL
        else:
            target = OrderStatus.PARTIALLY_FILLED
        if target != lifecycle.status:
            updated = transition(
                lifecycle,
                target,
                broker_order_id=broker_order_id,
            )
        else:
            updated = lifecycle.with_status(
                target,
                broker_order_id=broker_order_id,
            )
        return replace(
            updated,
            filled_quantity=new_filled,
            average_fill_price=updated_average,
            last_update_at=update.occurred_at,
        )
    if update.update_type is OrderUpdateType.CANCELED:
        return transition(
            lifecycle,
            OrderStatus.CANCELED,
            broker_order_id=broker_order_id,
        )
    if update.update_type is OrderUpdateType.REJECTED:
        return transition(
            lifecycle,
            OrderStatus.REJECTED,
            broker_order_id=broker_order_id,
            reject_reason=update.reason or "broker rejected order",
        )
    if update.update_type is OrderUpdateType.EXPIRED:
        return transition(
            lifecycle,
            OrderStatus.EXPIRED,
            broker_order_id=broker_order_id,
        )
    raise AssertionError(f"unsupported update type: {update.update_type}")
