from __future__ import annotations

from sentinel_combination.application.lifecycle import apply_broker_update
from sentinel_combination.domain.enums import OrderUpdateType
from sentinel_combination.domain.events import EventEnvelope
from sentinel_combination.domain.instruments import Instrument
from sentinel_combination.domain.orders import BrokerOrderUpdate
from sentinel_combination.domain.positions import Position
from sentinel_combination.storage.sqlite import SQLiteStore


class FillProcessor:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def process(
        self,
        update: BrokerOrderUpdate,
        *,
        instrument: Instrument,
    ) -> bool:
        if update.instrument_id != instrument.instrument_id:
            raise ValueError("instrument does not match broker update")

        with self.store.transaction() as transaction:
            if not transaction.claim_external_event(
                source=update.source,
                external_event_id=update.external_event_id,
            ):
                return False

            lifecycle = transaction.get_order(update.client_order_id)
            if lifecycle is None:
                raise LookupError("broker update references an unknown order")

            updated = apply_broker_update(lifecycle, update)
            transaction.save_order(updated)

            if update.update_type in {
                OrderUpdateType.PARTIAL_FILL,
                OrderUpdateType.FILL,
            }:
                assert update.fill_price is not None
                position = transaction.get_position(
                    account_id=update.account_id,
                    instrument_id=update.instrument_id,
                )
                if position is None:
                    position = Position(
                        account_id=update.account_id,
                        instrument_id=update.instrument_id,
                    )

                position = position.apply_fill(
                    side=lifecycle.intent.side,
                    quantity=update.fill_quantity,
                    price=update.fill_price,
                    fee=update.fee,
                    instrument=instrument,
                    at=update.occurred_at,
                )
                transaction.save_position(position)
                transaction.append_event(
                    EventEnvelope.create(
                        event_type="OrderFillApplied",
                        source=update.source,
                        occurred_at=update.occurred_at,
                        account_id=update.account_id,
                        instrument_id=update.instrument_id,
                        order_id=update.client_order_id,
                        bracket_id=lifecycle.intent.bracket_id,
                        payload={
                            "execution_id": update.execution_id,
                            "fill_quantity": str(update.fill_quantity),
                            "fill_price": str(update.fill_price),
                            "fee": str(update.fee),
                            "order_status": updated.status.value,
                            "position_quantity": str(position.quantity),
                            "position_average_entry": str(
                                position.average_entry_price
                            ),
                            "position_realized_pnl": str(
                                position.realized_pnl
                            ),
                        },
                    )
                )
            else:
                transaction.append_event(
                    EventEnvelope.create(
                        event_type="BrokerOrderUpdateApplied",
                        source=update.source,
                        occurred_at=update.occurred_at,
                        account_id=update.account_id,
                        instrument_id=update.instrument_id,
                        order_id=update.client_order_id,
                        bracket_id=lifecycle.intent.bracket_id,
                        payload={
                            "update_type": update.update_type.value,
                            "order_status": updated.status.value,
                            "reason": update.reason,
                        },
                    )
                )

        return True
