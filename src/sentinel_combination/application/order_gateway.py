from __future__ import annotations

from sentinel_combination.application.lifecycle import transition
from sentinel_combination.application.readiness import require_exposure_readiness
from sentinel_combination.application.risk import (
    RiskContext,
    RiskLimits,
    evaluate_order_risk,
)
from sentinel_combination.domain.enums import OrderStatus
from sentinel_combination.domain.events import EventEnvelope
from sentinel_combination.domain.instruments import Instrument
from sentinel_combination.domain.orders import OrderIntent, OrderLifecycle
from sentinel_combination.domain.readiness import ReadinessSnapshot
from sentinel_combination.ports.broker import (
    BrokerPort,
    BrokerRejected,
    BrokerUnknownOutcome,
)
from sentinel_combination.storage.sqlite import SQLiteStore


class OrderGateway:
    def __init__(
        self,
        *,
        store: SQLiteStore,
        broker: BrokerPort,
    ) -> None:
        self.store = store
        self.broker = broker

    def submit(
        self,
        *,
        intent: OrderIntent,
        instrument: Instrument,
        readiness: ReadinessSnapshot,
        risk_context: RiskContext,
        risk_limits: RiskLimits,
    ) -> OrderLifecycle:
        if intent.instrument_id != instrument.instrument_id:
            raise ValueError("order intent and instrument do not match")

        require_exposure_readiness(intent, readiness)

        with self.store.transaction() as transaction:
            if transaction.get_order(intent.client_order_id) is not None:
                raise ValueError("client_order_id has already been used")

        decision = evaluate_order_risk(
            intent=intent,
            instrument=instrument,
            context=risk_context,
            limits=risk_limits,
        )
        lifecycle = OrderLifecycle(intent=intent)

        if not decision.approved:
            lifecycle = transition(
                lifecycle,
                OrderStatus.REJECTED,
                reject_reason="; ".join(decision.reasons),
            )
            with self.store.transaction() as transaction:
                transaction.save_order(lifecycle)
                transaction.append_event(
                    EventEnvelope.create(
                        event_type="OrderRiskRejected",
                        source="combination",
                        account_id=intent.account_id,
                        instrument_id=intent.instrument_id,
                        order_id=intent.client_order_id,
                        bracket_id=intent.bracket_id,
                        payload={
                            "reasons": list(decision.reasons),
                            "order_notional": str(
                                decision.order_notional
                            ),
                            "projected_position_notional": str(
                                decision.projected_position_notional
                            ),
                        },
                    )
                )
            return lifecycle

        lifecycle = transition(
            lifecycle,
            OrderStatus.RISK_APPROVED,
        )
        lifecycle = transition(
            lifecycle,
            OrderStatus.SUBMITTING,
        )

        with self.store.transaction() as transaction:
            existing = transaction.get_order(intent.client_order_id)
            if existing is not None:
                raise ValueError(
                    "client_order_id has already been used"
                )
            transaction.save_order(lifecycle)
            transaction.append_event(
                EventEnvelope.create(
                    event_type="OrderSubmissionStarted",
                    source="combination",
                    account_id=intent.account_id,
                    instrument_id=intent.instrument_id,
                    order_id=intent.client_order_id,
                    bracket_id=intent.bracket_id,
                    payload={
                        "side": intent.side.value,
                        "quantity": str(intent.quantity),
                        "order_type": intent.order_type.value,
                        "reduce_only": intent.reduce_only,
                    },
                )
            )

        try:
            result = self.broker.submit_order(intent)
        except BrokerRejected as exc:
            lifecycle = transition(
                lifecycle,
                OrderStatus.REJECTED,
                reject_reason=exc.reason,
            )
            event_type = "BrokerSubmissionRejected"
        except BrokerUnknownOutcome as exc:
            lifecycle = transition(
                lifecycle,
                OrderStatus.RECONCILIATION_REQUIRED,
                reject_reason=str(exc),
            )
            event_type = "BrokerSubmissionOutcomeUnknown"
        else:
            lifecycle = transition(
                lifecycle,
                OrderStatus.SUBMITTED,
                broker_order_id=result.broker_order_id,
            )
            event_type = "OrderSubmitted"

        with self.store.transaction() as transaction:
            transaction.save_order(lifecycle)
            transaction.append_event(
                EventEnvelope.create(
                    event_type=event_type,
                    source=self.broker.name,
                    account_id=intent.account_id,
                    instrument_id=intent.instrument_id,
                    order_id=intent.client_order_id,
                    bracket_id=intent.bracket_id,
                    payload={
                        "status": lifecycle.status.value,
                        "broker_order_id": lifecycle.broker_order_id,
                        "reason": lifecycle.reject_reason,
                    },
                )
            )

        return lifecycle
