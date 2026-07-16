from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

import httpx

from sentinel_combination.brokers.common import decimal, parse_iso, status_from_text, utc_now
from sentinel_combination.brokers.http_base import HttpBrokerMixin
from sentinel_combination.config import BrokerConfig
from sentinel_combination.domain.enums import AssetClass, OrderStatus, OrderType, OrderUpdateType, Side
from sentinel_combination.domain.orders import BrokerOrderUpdate, OrderIntent
from sentinel_combination.ports.broker import (
    AccountSnapshot,
    BrokerAuthenticationError,
    BrokerCapabilities,
    BrokerOrderSnapshot,
    BrokerPosition,
    BrokerSubmitResult,
    BrokerUnknownOutcome,
    MarginEstimate,
    MarketSnapshot,
)


class TradeStationBroker(HttpBrokerMixin):
    LIVE_BASE = "https://api.tradestation.com/v3"
    SIM_BASE = "https://sim-api.tradestation.com/v3"
    TOKEN_URL = "https://signin.tradestation.com/oauth/token"

    def __init__(self, name: str, config: BrokerConfig) -> None:
        super().__init__()
        self._name = name
        self.config = config
        self._access_token: str | None = None
        self._token_expires_at = datetime.min.replace(tzinfo=timezone.utc)
        self._known_states: dict[str, tuple[str, str]] = {}

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
            native_oco=False,
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

    def _refresh(self) -> None:
        client_id = self.config.secret("client_id")
        client_secret = self.config.secret("client_secret")
        refresh_token = self.config.secret("refresh_token")
        try:
            response = httpx.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                },
                timeout=15,
            )
            response.raise_for_status()
        except Exception as exc:
            raise BrokerAuthenticationError(str(exc)) from exc
        data = response.json()
        self._access_token = str(data["access_token"])
        self._token_expires_at = utc_now() + timedelta(
            seconds=max(30, int(data.get("expires_in", 1200)) - 30)
        )
        if self._http is not None:
            self._http.headers["Authorization"] = f"Bearer {self._access_token}"

    def _ensure_token(self) -> None:
        if not self._access_token or utc_now() >= self._token_expires_at:
            self._refresh()

    def _request(self, *args: Any, **kwargs: Any) -> httpx.Response:
        self._ensure_token()
        return super()._request(*args, **kwargs)

    def connect(self) -> None:
        self._refresh()
        base = self.LIVE_BASE if self.environment == "live" else self.SIM_BASE
        self._make_http(
            base_url=base,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        self.get_account_snapshot(self.config.account_id)

    def disconnect(self) -> None:
        self._close_http()
        self._access_token = None

    def is_connected(self) -> bool:
        return self._http is not None and bool(self._access_token)

    def _symbol(self, instrument_id: str) -> str:
        return str((self.config.settings.get("symbols") or {}).get(instrument_id, instrument_id))

    def _instrument_id(self, symbol: str) -> str:
        for instrument_id, item in (self.config.settings.get("symbols") or {}).items():
            if item == symbol:
                return str(instrument_id)
        return symbol

    def _order_payload(self, intent: OrderIntent) -> dict[str, Any]:
        trade_action = {
            (Side.BUY, False): "BUY",
            (Side.SELL, False): "SELLSHORT" if intent.metadata.get("opening_short") == "true" else "SELL",
            (Side.BUY, True): "BUYTOCOVER",
            (Side.SELL, True): "SELL",
        }[(intent.side, intent.reduce_only)]
        order_type = {
            OrderType.MARKET: "Market",
            OrderType.LIMIT: "Limit",
            OrderType.STOP: "StopMarket",
            OrderType.STOP_LIMIT: "StopLimit",
            OrderType.TRAILING_STOP: "TrailingStop",
        }[intent.order_type]
        payload: dict[str, Any] = {
            "AccountID": intent.account_id,
            "Symbol": self._symbol(intent.instrument_id),
            "Quantity": str(intent.quantity),
            "OrderType": order_type,
            "TradeAction": trade_action,
            "TimeInForce": {"Duration": intent.time_in_force},
            "Route": str(self.config.settings.get("route", "Intelligent")),
            "ClientOrderID": intent.client_order_id,
        }
        if intent.limit_price is not None:
            payload["LimitPrice"] = str(intent.limit_price)
        if intent.stop_price is not None:
            payload["StopPrice"] = str(intent.stop_price)
        if intent.order_type is OrderType.TRAILING_STOP:
            payload["AdvancedOptions"] = {
                "TrailingStop": {
                    "Amount": str(intent.metadata.get("trailing_amount", "")),
                    "Percent": str(intent.metadata.get("trailing_percent", "")),
                }
            }
        return payload

    @staticmethod
    def _extract_order_id(payload: Mapping[str, Any]) -> str:
        orders = payload.get("Orders") or payload.get("orders") or []
        if orders:
            return str(orders[0].get("OrderID") or orders[0].get("orderId") or "")
        return str(payload.get("OrderID") or payload.get("orderId") or "")

    def submit_order(self, intent: OrderIntent) -> BrokerSubmitResult:
        response = self._request(
            "POST",
            "/orderexecution/orders",
            json=self._order_payload(intent),
            unknown_on_timeout=True,
        )
        order_id = self._extract_order_id(response.json())
        if not order_id:
            raise BrokerUnknownOutcome("TradeStation accepted request without OrderID")
        return BrokerSubmitResult(order_id, utc_now())

    def cancel_order(self, *, account_id: str, client_order_id: str, broker_order_id: str) -> None:
        self._request(
            "DELETE",
            f"/orderexecution/orders/{broker_order_id}",
            unknown_on_timeout=True,
        )

    def replace_order(self, *, lifecycle_client_order_id: str, broker_order_id: str, replacement: OrderIntent) -> BrokerSubmitResult:
        response = self._request(
            "PUT",
            f"/orderexecution/orders/{broker_order_id}",
            json=self._order_payload(replacement),
            unknown_on_timeout=True,
        )
        order_id = self._extract_order_id(response.json()) or broker_order_id
        return BrokerSubmitResult(order_id, utc_now())

    def get_account_snapshot(self, account_id: str) -> AccountSnapshot:
        response = self._request("GET", f"/brokerage/accounts/{account_id}/balances")
        items = response.json().get("Balances") or []
        if not items:
            raise BrokerAuthenticationError(f"TradeStation account {account_id} not found")
        item = items[0]
        return AccountSnapshot(
            account_id=account_id,
            equity=decimal(item.get("Equity")),
            available_buying_power=decimal(item.get("BuyingPower")),
            captured_at=utc_now(),
            currency=str(item.get("Currency") or "USD"),
            initial_margin_used=decimal(item.get("InitialMargin")),
            maintenance_margin_used=decimal(item.get("MaintenanceMargin")),
        )

    def get_market_snapshot(self, instrument_id: str) -> MarketSnapshot:
        response = self._request("GET", f"/marketdata/quotes/{self._symbol(instrument_id)}")
        quotes = response.json().get("Quotes") or []
        if not quotes:
            raise BrokerAuthenticationError(f"no TradeStation quote for {instrument_id}")
        item = quotes[0]
        bid, ask = decimal(item.get("Bid")), decimal(item.get("Ask"))
        mark = decimal(item.get("Last") or ((bid + ask) / 2 if bid and ask else 0))
        return MarketSnapshot(instrument_id, bid, ask, mark, parse_iso(item.get("TradeTime") or utc_now()))

    def get_positions(self, account_id: str) -> Sequence[BrokerPosition]:
        response = self._request("GET", f"/brokerage/accounts/{account_id}/positions")
        result = []
        for item in response.json().get("Positions") or []:
            quantity = decimal(item.get("Quantity"))
            if str(item.get("LongShort") or "Long").lower() == "short":
                quantity = -abs(quantity)
            if quantity == 0:
                continue
            result.append(BrokerPosition(
                account_id=account_id,
                instrument_id=self._instrument_id(str(item.get("Symbol"))),
                quantity=quantity,
                average_entry_price=decimal(item.get("AveragePrice")),
                captured_at=utc_now(),
            ))
        return tuple(result)

    def _snapshot(self, account_id: str, item: Mapping[str, Any]) -> BrokerOrderSnapshot:
        action = str(item.get("TradeAction") or "BUY").upper()
        return BrokerOrderSnapshot(
            account_id=account_id,
            instrument_id=self._instrument_id(str(item.get("Symbol"))),
            client_order_id=str(item.get("ClientOrderID") or item.get("OrderID")),
            broker_order_id=str(item.get("OrderID")),
            status=status_from_text(str(item.get("StatusDescription") or item.get("Status") or "working")),
            side=Side.BUY if action.startswith("BUY") else Side.SELL,
            quantity=decimal(item.get("Quantity")),
            filled_quantity=decimal(item.get("FilledQuantity")),
            average_fill_price=decimal(item.get("FilledPrice")) if item.get("FilledPrice") else None,
            captured_at=parse_iso(item.get("OpenedDateTime") or utc_now()),
            reduce_only=action in {"SELL", "BUYTOCOVER"},
        )

    def get_open_orders(self, account_id: str) -> Sequence[BrokerOrderSnapshot]:
        response = self._request("GET", f"/brokerage/accounts/{account_id}/orders")
        result = []
        for item in response.json().get("Orders") or []:
            snapshot = self._snapshot(account_id, item)
            if not snapshot.status.terminal:
                result.append(snapshot)
        return tuple(result)

    def get_order(self, *, account_id: str, client_order_id: str, broker_order_id: str | None = None) -> BrokerOrderSnapshot | None:
        if broker_order_id:
            response = self._request("GET", f"/brokerage/accounts/{account_id}/orders/{broker_order_id}")
            items = response.json().get("Orders") or []
        else:
            response = self._request("GET", f"/brokerage/accounts/{account_id}/orders")
            items = response.json().get("Orders") or []
        for item in items:
            snapshot = self._snapshot(account_id, item)
            if broker_order_id and snapshot.broker_order_id == broker_order_id:
                return snapshot
            if snapshot.client_order_id == client_order_id:
                return snapshot
        return None

    def estimate_margin(self, intent: OrderIntent) -> MarginEstimate:
        response = self._request(
            "POST",
            "/orderexecution/orderconfirm",
            json=self._order_payload(intent),
        )
        confirmations = response.json().get("Confirmations") or []
        item = confirmations[0] if confirmations else response.json()
        initial = decimal(item.get("InitialMargin") or item.get("EstimatedCost"))
        maintenance = decimal(item.get("MaintenanceMargin") or initial)
        return MarginEstimate(abs(initial), abs(maintenance), "tradestation-confirm", utc_now())

    def poll_order_updates(self, account_id: str) -> Iterable[BrokerOrderUpdate]:
        response = self._request("GET", f"/brokerage/accounts/{account_id}/orders")
        updates: list[BrokerOrderUpdate] = []
        for item in response.json().get("Orders") or []:
            snapshot = self._snapshot(account_id, item)
            state = (snapshot.status.value, str(snapshot.filled_quantity))
            if self._known_states.get(snapshot.broker_order_id) == state:
                continue
            self._known_states[snapshot.broker_order_id] = state
            status = snapshot.status
            if status in {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED}:
                previous_filled = Decimal("0")
                execution_id = str(item.get("ExecutionID") or f"{snapshot.broker_order_id}:{snapshot.filled_quantity}")
                fill_quantity = snapshot.filled_quantity - previous_filled
                if fill_quantity <= 0:
                    continue
                update_type = OrderUpdateType.FILL if status is OrderStatus.FILLED else OrderUpdateType.PARTIAL_FILL
                updates.append(BrokerOrderUpdate(
                    source=self.name,
                    external_event_id=f"execution:{execution_id}",
                    account_id=account_id,
                    instrument_id=snapshot.instrument_id,
                    client_order_id=snapshot.client_order_id,
                    broker_order_id=snapshot.broker_order_id,
                    update_type=update_type,
                    occurred_at=snapshot.captured_at,
                    execution_id=execution_id,
                    fill_quantity=fill_quantity,
                    fill_price=snapshot.average_fill_price or Decimal("0"),
                    cumulative_filled_quantity=snapshot.filled_quantity,
                ))
                continue
            mapping = {
                OrderStatus.SUBMITTED: OrderUpdateType.ACKNOWLEDGED,
                OrderStatus.ACKNOWLEDGED: OrderUpdateType.ACKNOWLEDGED,
                OrderStatus.WORKING: OrderUpdateType.WORKING,
                OrderStatus.CANCELED: OrderUpdateType.CANCELED,
                OrderStatus.REJECTED: OrderUpdateType.REJECTED,
                OrderStatus.EXPIRED: OrderUpdateType.EXPIRED,
            }
            if status not in mapping:
                continue
            digest = hashlib.sha256(f"{snapshot.broker_order_id}:{state}".encode()).hexdigest()[:24]
            updates.append(BrokerOrderUpdate(
                source=self.name,
                external_event_id=f"order:{digest}",
                account_id=account_id,
                instrument_id=snapshot.instrument_id,
                client_order_id=snapshot.client_order_id,
                broker_order_id=snapshot.broker_order_id,
                update_type=mapping[status],
                occurred_at=snapshot.captured_at,
                reason=str(item.get("RejectReason") or "") or None,
            ))
        return tuple(updates)
