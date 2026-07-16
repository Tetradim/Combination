from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Sequence

from sentinel_combination.brokers.common import decimal, status_from_text, utc_now
from sentinel_combination.config import BrokerConfig
from sentinel_combination.domain.enums import AssetClass, OrderStatus, OrderType, OrderUpdateType, Side
from sentinel_combination.domain.orders import BrokerOrderUpdate, OrderIntent
from sentinel_combination.ports.broker import (
    AccountSnapshot,
    BrokerAuthenticationError,
    BrokerCapabilities,
    BrokerOrderSnapshot,
    BrokerPosition,
    BrokerRejected,
    BrokerSubmitResult,
    BrokerUnknownOutcome,
    BrokerUnsupported,
    MarginEstimate,
    MarketSnapshot,
)


class IBKRBroker:
    def __init__(self, name: str, config: BrokerConfig) -> None:
        self._name = name
        self.config = config
        self._ib: Any | None = None
        self._contracts: dict[str, Any] = {}
        self._execution_ids: set[str] = set()
        self._order_states: dict[int, tuple[str, str]] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def environment(self) -> str:
        return self.config.environment

    @property
    def capabilities(self) -> BrokerCapabilities:
        return BrokerCapabilities(
            durable_stop_orders=True,
            native_oco=True,
            native_trailing_stop=True,
            cancel_replace=True,
            margin_preview=True,
            streaming_order_updates=True,
            reduce_only=False,
            native_bracket=True,
            supports_futures=True,
            broker_managed_test_environment=True,
            asset_classes=(AssetClass.LISTED_FUTURE,),
        )

    def connect(self) -> None:
        try:
            from ib_async import IB
        except ImportError as exc:
            raise BrokerUnsupported("IBKR requires the 'ibkr' optional dependency") from exc
        ib = IB()
        try:
            ib.connect(
                host=str(self.config.settings.get("host", "127.0.0.1")),
                port=int(self.config.settings.get("port", 7497)),
                clientId=int(self.config.settings.get("client_id", 73)),
                timeout=float(self.config.settings.get("timeout_seconds", 8)),
                readonly=False,
                account=self.config.account_id,
            )
        except Exception as exc:
            raise BrokerAuthenticationError(str(exc)) from exc
        self._ib = ib
        for instrument_id in (self.config.settings.get("contracts") or {}):
            self._contract(instrument_id)

    def disconnect(self) -> None:
        if self._ib is not None:
            self._ib.disconnect()
        self._ib = None
        self._contracts.clear()

    def is_connected(self) -> bool:
        return bool(self._ib is not None and self._ib.isConnected())

    def _require(self) -> Any:
        if not self.is_connected():
            raise BrokerAuthenticationError("IBKR TWS/IB Gateway is not connected")
        return self._ib

    def _contract(self, instrument_id: str) -> Any:
        if instrument_id in self._contracts:
            return self._contracts[instrument_id]
        try:
            from ib_async import Future
        except ImportError as exc:
            raise BrokerUnsupported("IBKR requires ib_async") from exc
        mapping = (self.config.settings.get("contracts") or {}).get(instrument_id)
        if not mapping:
            raise ValueError(f"missing IBKR contract mapping for {instrument_id}")
        contract = Future(
            symbol=str(mapping["symbol"]),
            lastTradeDateOrContractMonth=str(mapping.get("expiry", "")),
            exchange=str(mapping.get("exchange", "CME")),
            localSymbol=str(mapping.get("local_symbol", "")),
            multiplier=str(mapping.get("multiplier", "")),
            currency=str(mapping.get("currency", "USD")),
        )
        qualified = self._require().qualifyContracts(contract)
        if not qualified:
            raise BrokerRejected(f"IBKR could not qualify {instrument_id}")
        self._contracts[instrument_id] = qualified[0]
        return qualified[0]

    def _order(self, intent: OrderIntent, *, what_if: bool = False) -> Any:
        try:
            from ib_async import LimitOrder, MarketOrder, Order, StopOrder
        except ImportError as exc:
            raise BrokerUnsupported("IBKR requires ib_async") from exc
        action = "BUY" if intent.side is Side.BUY else "SELL"
        qty = float(intent.quantity)
        if intent.order_type is OrderType.MARKET:
            order = MarketOrder(action, qty)
        elif intent.order_type is OrderType.LIMIT:
            order = LimitOrder(action, qty, float(intent.limit_price))
        elif intent.order_type is OrderType.STOP:
            order = StopOrder(action, qty, float(intent.stop_price))
        elif intent.order_type is OrderType.STOP_LIMIT:
            order = Order(
                action=action,
                totalQuantity=qty,
                orderType="STP LMT",
                auxPrice=float(intent.stop_price),
                lmtPrice=float(intent.limit_price),
            )
        elif intent.order_type is OrderType.TRAILING_STOP:
            trail_pct = float((intent.metadata or {}).get("trailing_percent", 1))
            order = Order(
                action=action,
                totalQuantity=qty,
                orderType="TRAIL",
                trailingPercent=trail_pct,
            )
        else:
            raise BrokerUnsupported(f"unsupported IBKR order type {intent.order_type.value}")
        order.orderRef = intent.client_order_id
        order.account = intent.account_id
        order.tif = intent.time_in_force
        order.transmit = True
        order.whatIf = what_if
        if intent.oca_group_id:
            order.ocaGroup = intent.oca_group_id
            order.ocaType = 1
        return order

    def submit_order(self, intent: OrderIntent) -> BrokerSubmitResult:
        try:
            trade = self._require().placeOrder(
                self._contract(intent.instrument_id), self._order(intent)
            )
            self._require().sleep(float(self.config.settings.get("ack_wait_seconds", 0.25)))
        except Exception as exc:
            raise BrokerUnknownOutcome(str(exc)) from exc
        order_id = str(getattr(trade.order, "orderId", ""))
        if not order_id or order_id == "0":
            raise BrokerUnknownOutcome("IBKR did not assign an order ID")
        status = str(getattr(trade.orderStatus, "status", ""))
        if status.lower() == "inactive":
            raise BrokerRejected("IBKR marked the order inactive")
        return BrokerSubmitResult(order_id, utc_now())

    def _trade_by_order_id(self, broker_order_id: str) -> Any | None:
        for trade in self._require().trades():
            if str(getattr(trade.order, "orderId", "")) == str(broker_order_id):
                return trade
        return None

    def cancel_order(self, *, account_id: str, client_order_id: str, broker_order_id: str) -> None:
        trade = self._trade_by_order_id(broker_order_id)
        if trade is None:
            raise BrokerUnknownOutcome(f"IBKR order {broker_order_id} not found")
        self._require().cancelOrder(trade.order)

    def replace_order(self, *, lifecycle_client_order_id: str, broker_order_id: str, replacement: OrderIntent) -> BrokerSubmitResult:
        trade = self._trade_by_order_id(broker_order_id)
        if trade is None:
            raise BrokerUnknownOutcome(f"IBKR order {broker_order_id} not found")
        replacement_order = self._order(replacement)
        replacement_order.orderId = int(broker_order_id)
        try:
            updated = self._require().placeOrder(
                self._contract(replacement.instrument_id), replacement_order
            )
        except Exception as exc:
            raise BrokerUnknownOutcome(str(exc)) from exc
        return BrokerSubmitResult(str(updated.order.orderId), utc_now())

    def get_account_snapshot(self, account_id: str) -> AccountSnapshot:
        values = self._require().accountSummary(account_id)
        data = {(item.tag, item.currency): item.value for item in values}
        def value(tag: str) -> Decimal:
            return decimal(data.get((tag, "USD")) or next((v for (t, _), v in data.items() if t == tag), 0))
        return AccountSnapshot(
            account_id=account_id,
            equity=value("NetLiquidation"),
            available_buying_power=value("AvailableFunds"),
            captured_at=utc_now(),
            currency="USD",
            initial_margin_used=value("InitMarginReq"),
            maintenance_margin_used=value("MaintMarginReq"),
        )

    def get_market_snapshot(self, instrument_id: str) -> MarketSnapshot:
        ticker = self._require().reqTickers(self._contract(instrument_id))[0]
        bid = decimal(getattr(ticker, "bid", None))
        ask = decimal(getattr(ticker, "ask", None))
        market_price = getattr(ticker, "marketPrice", lambda: None)()
        mark = decimal(market_price or getattr(ticker, "last", None) or ((bid + ask) / 2 if bid and ask else None))
        return MarketSnapshot(instrument_id, bid, ask, mark, utc_now())

    def _instrument_for_contract(self, contract: Any) -> str:
        con_id = getattr(contract, "conId", None)
        for instrument_id, configured in self._contracts.items():
            if getattr(configured, "conId", None) == con_id:
                return instrument_id
        return str(getattr(contract, "localSymbol", None) or getattr(contract, "symbol", ""))

    def get_positions(self, account_id: str) -> Sequence[BrokerPosition]:
        result = []
        for item in self._require().reqPositions():
            if item.account != account_id or decimal(item.position) == 0:
                continue
            result.append(BrokerPosition(
                account_id=account_id,
                instrument_id=self._instrument_for_contract(item.contract),
                quantity=decimal(item.position),
                average_entry_price=decimal(item.avgCost) / decimal(getattr(item.contract, "multiplier", 1), "1"),
                captured_at=utc_now(),
            ))
        return tuple(result)

    def _snapshot_trade(self, account_id: str, trade: Any) -> BrokerOrderSnapshot:
        order = trade.order
        status = trade.orderStatus
        action = str(getattr(order, "action", "BUY")).upper()
        average = decimal(getattr(status, "avgFillPrice", None))
        return BrokerOrderSnapshot(
            account_id=account_id,
            instrument_id=self._instrument_for_contract(trade.contract),
            client_order_id=str(getattr(order, "orderRef", "") or getattr(order, "orderId", "")),
            broker_order_id=str(getattr(order, "orderId", "")),
            status=status_from_text(str(getattr(status, "status", ""))),
            side=Side.BUY if action == "BUY" else Side.SELL,
            quantity=decimal(getattr(order, "totalQuantity", 0)),
            filled_quantity=decimal(getattr(status, "filled", 0)),
            average_fill_price=average if average > 0 else None,
            captured_at=utc_now(),
            reduce_only=False,
        )

    def get_open_orders(self, account_id: str) -> Sequence[BrokerOrderSnapshot]:
        return tuple(self._snapshot_trade(account_id, t) for t in self._require().openTrades() if not getattr(t.order, "account", "") or t.order.account == account_id)

    def get_order(self, *, account_id: str, client_order_id: str, broker_order_id: str | None = None) -> BrokerOrderSnapshot | None:
        for trade in self._require().trades():
            snapshot = self._snapshot_trade(account_id, trade)
            if broker_order_id and snapshot.broker_order_id == str(broker_order_id):
                return snapshot
            if snapshot.client_order_id == client_order_id:
                return snapshot
        return None

    def estimate_margin(self, intent: OrderIntent) -> MarginEstimate:
        state = self._require().whatIfOrder(self._contract(intent.instrument_id), self._order(intent, what_if=True))
        initial = decimal(getattr(state, "initMarginChange", 0))
        maintenance = decimal(getattr(state, "maintMarginChange", 0))
        return MarginEstimate(abs(initial), abs(maintenance), "ibkr-what-if", utc_now())

    def poll_order_updates(self, account_id: str) -> Iterable[BrokerOrderUpdate]:
        updates: list[BrokerOrderUpdate] = []
        for fill in self._require().fills():
            execution = fill.execution
            exec_id = str(getattr(execution, "execId", ""))
            if not exec_id or exec_id in self._execution_ids:
                continue
            self._execution_ids.add(exec_id)
            order_id = str(getattr(execution, "orderId", ""))
            trade = self._trade_by_order_id(order_id)
            client_id = str(getattr(trade.order, "orderRef", "") if trade else order_id)
            quantity = decimal(getattr(execution, "shares", 0))
            price = decimal(getattr(execution, "price", 0))
            commission = decimal(getattr(getattr(fill, "commissionReport", None), "commission", 0))
            updates.append(BrokerOrderUpdate(
                source=self.name,
                external_event_id=f"execution:{exec_id}",
                account_id=account_id,
                instrument_id=self._instrument_for_contract(fill.contract),
                client_order_id=client_id,
                broker_order_id=order_id,
                update_type=OrderUpdateType.PARTIAL_FILL,
                occurred_at=getattr(fill, "time", utc_now()),
                execution_id=exec_id,
                fill_quantity=quantity,
                fill_price=price,
                fee=commission,
            ))
        for trade in self._require().trades():
            snapshot = self._snapshot_trade(account_id, trade)
            key = int(snapshot.broker_order_id or 0)
            state = (snapshot.status.value, str(snapshot.filled_quantity))
            if self._order_states.get(key) == state:
                continue
            self._order_states[key] = state
            if snapshot.status in {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED}:
                continue
            mapping = {
                OrderStatus.SUBMITTED: OrderUpdateType.ACKNOWLEDGED,
                OrderStatus.ACKNOWLEDGED: OrderUpdateType.ACKNOWLEDGED,
                OrderStatus.WORKING: OrderUpdateType.WORKING,
                OrderStatus.CANCELED: OrderUpdateType.CANCELED,
                OrderStatus.REJECTED: OrderUpdateType.REJECTED,
                OrderStatus.EXPIRED: OrderUpdateType.EXPIRED,
            }
            if snapshot.status not in mapping:
                continue
            digest = hashlib.sha256(f"{key}:{state}".encode()).hexdigest()[:24]
            updates.append(BrokerOrderUpdate(
                source=self.name,
                external_event_id=f"order:{digest}",
                account_id=account_id,
                instrument_id=snapshot.instrument_id,
                client_order_id=snapshot.client_order_id,
                broker_order_id=snapshot.broker_order_id,
                update_type=mapping[snapshot.status],
                occurred_at=utc_now(),
            ))
        return tuple(updates)
