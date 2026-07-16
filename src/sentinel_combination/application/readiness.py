from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sentinel_combination.domain.events import utc_now
from sentinel_combination.domain.orders import OrderIntent
from sentinel_combination.domain.readiness import ReadinessSnapshot
from sentinel_combination.ports.broker import BrokerPort
from sentinel_combination.storage.sqlite import SQLiteStore


def require_exposure_readiness(intent: OrderIntent, readiness: ReadinessSnapshot) -> None:
    if intent.reduce_only:
        if not readiness.broker_connected or not readiness.authenticated:
            raise PermissionError(
                "risk-reducing order requires an authenticated broker connection"
            )
        if not readiness.persistence_healthy:
            raise PermissionError(
                "risk-reducing order blocked because persistence is unhealthy"
            )
        if not readiness.positions_reconciled:
            raise PermissionError(
                "risk-reducing order blocked because positions are not reconciled"
            )
        return
    readiness.assert_ready_for_exposure()


def evaluate_readiness(
    *,
    store: SQLiteStore,
    broker: BrokerPort,
    account_id: str,
    instrument_id: str,
    activation_authorized: bool,
    order_stream_healthy: bool,
    maximum_account_age_seconds: float = 15,
    maximum_market_age_seconds: float = 5,
) -> ReadinessSnapshot:
    now = utc_now()
    reasons: list[str] = []
    connected = broker.is_connected()
    authenticated = False
    account_fresh = False
    market_fresh = False
    margin_available = False
    instrument_tradeable = False
    if connected:
        try:
            account = broker.get_account_snapshot(account_id)
            authenticated = True
            account_fresh = now - account.captured_at <= timedelta(
                seconds=maximum_account_age_seconds
            )
            if not account_fresh:
                reasons.append("account snapshot is stale")
        except Exception as exc:
            reasons.append(f"account unavailable: {exc}")
        try:
            market = broker.get_market_snapshot(instrument_id)
            market_fresh = now - market.captured_at <= timedelta(
                seconds=maximum_market_age_seconds
            )
            instrument_tradeable = market.bid > 0 and market.ask > 0 and market.ask >= market.bid
            if not market_fresh:
                reasons.append("market snapshot is stale")
            if not instrument_tradeable:
                reasons.append("instrument market is not tradeable")
        except Exception as exc:
            reasons.append(f"market unavailable: {exc}")
        # Margin availability is checked for the concrete order before submission;
        # here it means the adapter exposes a valid margin path.
        margin_available = broker.capabilities.margin_preview
    reconciliation = None
    with store.transaction() as transaction:
        level, _, _ = transaction.get_kill_switch()
        reconciliation = transaction.get_reconciliation(broker.name, account_id)
    positions_reconciled = bool(reconciliation and reconciliation["positions_match"])
    orders_reconciled = bool(reconciliation and reconciliation["orders_match"])
    if not positions_reconciled:
        reasons.append("positions are not reconciled")
    if not orders_reconciled:
        reasons.append("orders are not reconciled")
    kill_switch_clear = level.value == "clear"
    if not kill_switch_clear:
        reasons.append(f"kill switch is {level.value}")
    persistence_healthy = store.healthcheck() and store.verify_audit_chain()
    if not persistence_healthy:
        reasons.append("persistence or audit chain is unhealthy")
    protective_supported = broker.capabilities.durable_stop_orders
    if not protective_supported:
        reasons.append("durable protective orders are not supported")
    if not activation_authorized:
        reasons.append("activation authorization is absent")
    if not order_stream_healthy:
        reasons.append("order update stream is unhealthy")
    return ReadinessSnapshot(
        broker_connected=connected,
        authenticated=authenticated,
        account_fresh=account_fresh,
        market_data_fresh=market_fresh,
        positions_reconciled=positions_reconciled,
        orders_reconciled=orders_reconciled,
        kill_switch_clear=kill_switch_clear,
        persistence_healthy=persistence_healthy,
        margin_available=margin_available,
        instrument_tradeable=instrument_tradeable,
        protective_order_supported=protective_supported,
        activation_authorized=activation_authorized,
        evaluated_at=now,
        order_stream_healthy=order_stream_healthy,
        reasons=tuple(reasons),
    )
