from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from sentinel_combination.application.lifecycle import transition
from sentinel_combination.domain.enums import OrderStatus
from sentinel_combination.domain.events import EventEnvelope
from sentinel_combination.ports.broker import BrokerPort
from sentinel_combination.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class ReconciliationResult:
    broker_name: str
    account_id: str
    positions_match: bool
    orders_match: bool
    position_differences: Mapping[str, tuple[Decimal, Decimal]]
    missing_local_orders: tuple[str, ...]
    missing_broker_orders: tuple[str, ...]

    @property
    def reconciled(self) -> bool:
        return self.positions_match and self.orders_match


class ReconciliationService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def reconcile(self, broker: BrokerPort, account_id: str) -> ReconciliationResult:
        broker_positions = {
            item.instrument_id: item.quantity
            for item in broker.get_positions(account_id)
            if item.quantity != 0
        }
        with self.store.transaction() as transaction:
            local_positions = {
                item.instrument_id: item.quantity
                for item in transaction.list_positions(account_id=account_id)
                if item.quantity != 0
            }
            local_orders = transaction.list_orders(
                account_id=account_id,
                broker_name=broker.name,
                include_terminal=False,
            )
        position_differences: dict[str, tuple[Decimal, Decimal]] = {}
        for instrument_id in sorted(set(local_positions) | set(broker_positions)):
            local = local_positions.get(instrument_id, Decimal("0"))
            remote = broker_positions.get(instrument_id, Decimal("0"))
            if local != remote:
                position_differences[instrument_id] = (local, remote)

        broker_orders = {
            item.client_order_id: item for item in broker.get_open_orders(account_id)
        }
        local_by_id = {item.intent.client_order_id: item for item in local_orders}
        missing_local = tuple(sorted(set(broker_orders) - set(local_by_id)))
        missing_broker = tuple(sorted(set(local_by_id) - set(broker_orders)))

        # Resolve only unknown-submission states that the broker can prove.
        with self.store.transaction() as transaction:
            for client_id, lifecycle in local_by_id.items():
                remote = broker_orders.get(client_id)
                if lifecycle.status is not OrderStatus.RECONCILIATION_REQUIRED or remote is None:
                    continue
                if remote.quantity != lifecycle.intent.quantity:
                    continue
                if remote.filled_quantity != lifecycle.filled_quantity:
                    # Missing fills may never be manufactured during reconciliation.
                    continue
                target = remote.status
                if target in {
                    OrderStatus.SUBMITTED,
                    OrderStatus.ACKNOWLEDGED,
                    OrderStatus.WORKING,
                    OrderStatus.PARTIALLY_FILLED,
                    OrderStatus.FILLED,
                    OrderStatus.CANCELED,
                    OrderStatus.REJECTED,
                    OrderStatus.EXPIRED,
                }:
                    updated = transition(
                        lifecycle,
                        target,
                        broker_order_id=remote.broker_order_id,
                    )
                    transaction.save_order(updated, broker_name=broker.name)

        result = ReconciliationResult(
            broker_name=broker.name,
            account_id=account_id,
            positions_match=not position_differences,
            orders_match=not missing_local and not missing_broker,
            position_differences=position_differences,
            missing_local_orders=missing_local,
            missing_broker_orders=missing_broker,
        )
        details = {
            "position_differences": {
                key: {"local": str(value[0]), "broker": str(value[1])}
                for key, value in position_differences.items()
            },
            "missing_local_orders": list(missing_local),
            "missing_broker_orders": list(missing_broker),
        }
        with self.store.transaction() as transaction:
            transaction.save_reconciliation(
                broker_name=broker.name,
                account_id=account_id,
                positions_match=result.positions_match,
                orders_match=result.orders_match,
                details=details,
            )
            transaction.append_event(
                EventEnvelope.create(
                    event_type=(
                        "BrokerReconciled" if result.reconciled else "BrokerReconciliationFailed"
                    ),
                    source=broker.name,
                    account_id=account_id,
                    payload=details,
                )
            )
        return result
