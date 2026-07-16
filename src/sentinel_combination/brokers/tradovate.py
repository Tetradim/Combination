from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

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
    BrokerRejected,
    BrokerSubmitResult,
    BrokerUnknownOutcome,
    BrokerUnsupported,
    MarginEstimate,
    MarketSnapshot,
)


class TradovateBroker(HttpBrokerMixin):
    """Tradovate/NinjaTrader futures adapter using the Tradovate REST API."""

    def __init__(self, name: str, config: BrokerConfig) -> None:
        super().__init__()
        self._name = name
        self.config = config
        self._token: str | None = None
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
            native_trailing_stop=False,
            cancel_replace=True,
            margin_preview=False,
            streaming_order_updates=False,
            reduce_only=False,
            native_bracket=True,
            supports_futures=True,
            asset_classes=(AssetClass.LISTED_FUTURE,),
        )

    def _base_url(self) -> str:
        return str(self.config.settings.get("base_url", "https://live.tradovateapi.com/v1"))

    def connect(self) -> None:
        self._make_http(base_url=self._base_url())
        payload = {
            "name": self.config.secret("username"),
            "password": self.config.secret("password"),
            "appId": str(self.config.settings.get("app_id", "SentinelCombination")),
            "appVersion": str(self.config.settings.get("app_version", "1.0")),
            "cid": int(self.config.secret("cid") or "0"),
            "sec": self.config.secret("secret"),
        }
        response = self._request("POST", "/auth/accesstokenrequest", json=payload)
        data = response.json()
        token = str(data.get("accessToken") or "")
        if not token:
            self._close_http()
            raise BrokerAuthenticationError(str(data.get("errorText") or "Tradovate authentication failed"))
        self._token = token
        assert self._http is not None
        self._http.headers.update({"Authorization": f"Bearer {token}"})

    def disconnect(self) -> None:
        self._token = None
        self._close_http()

    def is_connected(self) -> bool:
        return self._http is not None and bool(self._token)

    def _symbol(self, instrument_id: str) -> str:
        return str((self.config.settings.get("symbols") or {}).get(instrument_id, instrument_id))

    def _instrument_id(self, symbol: str) -> str:
        for instrument_id, configured in (self.config.settings.get("symbols") or {}).items():
            if str(configured) == symbol:
                return str(instrument_id)
        return symbol

    def _account_spec(self) -> str:
        return str(self.config.settings.get("account_spec", self.config.account_id))

    def _order_payload(self, intent: OrderIntent) -> dict[str, Any]:
        order_type = {
            OrderType.MARKET: "Market",
            OrderType.LIMIT: "Limit",
            OrderType.STOP: "Stop",
            OrderType.STOP_LIMIT: "StopLimit",
            OrderType.TRAILING_STOP: "TrailingStop",
        }[intent.order_type]
        payload: dict[str, Any] = {
            "accountSpec": self._account_spec(),
            "accountId": int(intent.account_id),
            "action": "Buy" if intent.side is Side.BUY else "Sell",
            "symbol": self._symbol(intent.instrument_id),
            "orderQty": float(intent.quantity),
            "orderType": order_type,
            "timeInForce": intent.time_in_force,
            "isAutomated": True,
            "customTag50": intent.client_order_id,
        }
        if intent.limit_price is not None:
            payload["price"] = float(intent.limit_price)
        if intent.stop_price is not None:
            payload["stopPrice"] = float(intent.stop_price)
        if intent.reduce_only:
            payload["isLiquidation"] = True
        return payload

    def submit_order(self, intent: OrderIntent) -> BrokerSubmitResult:
        response = self._request("POST", "/order/placeorder", json=self._order_payload(intent), unknown_on_timeout=True)
        data = response.json()
        if data.get("failureReason") or data.get("failureText"):
            raise BrokerRejected(str(data.get("failureText") or data.get("failureReason")))
        order_id = str(data.get("orderId") or data.get("id") or "")
        if not order_id:
            raise BrokerUnknownOutcome("Tradovate accepted the request without an order ID")
        return BrokerSubmitResult(order_id, utc_now())

    def cancel_order(self, *, account_id: str, client_order_id: str, broker_order_id: str) -> None:
        self._request("POST", "/order/cancelorder", json={"orderId": int(broker_order_id)}, unknown_on_timeout=True)

    def replace_order(self, *, lifecycle_client_order_id: str, broker_order_id: str, replacement: OrderIntent) -> BrokerSubmitResult:
        payload = self._order_payload(replacement)
        payload["orderId"] = int(broker_order_id)
        response = self._request("POST", "/order/modifyorder", json=payload, unknown_on_timeout=True)
        data = response.json()
        if data.get("failureReason") or data.get("failureText"):
            raise BrokerRejected(str(data.get("failureText") or data.get("failureReason")))
        return BrokerSubmitResult(str(data.get("orderId") or broker_order_id), utc_now())

    def get_account_snapshot(self, account_id: str) -> AccountSnapshot:
        response = self._request("GET", "/cashBalance/getcashbalancesnapshot", params={"accountId": account_id})
        item = response.json()
        return AccountSnapshot(
            account_id=account_id,
            equity=decimal(item.get("totalCashValue") or item.get("netLiq")),
            available_buying_power=decimal(item.get("availableMargin") or item.get("cashBalance")),
            captured_at=parse_iso(item.get("timestamp") or utc_now()),
            initial_margin_used=decimal(item.get("initialMargin")),
            maintenance_margin_used=decimal(item.get("maintenanceMargin")),
        )

    def get_market_snapshot(self, instrument_id: str) -> MarketSnapshot:
        quotes = self.config.settings.get("quotes") or {}
        item = quotes.get(instrument_id)
        if not isinstance(item, Mapping):
            raise BrokerUnsupported(
                "Tradovate market snapshots require a quote feed mapped in settings.quotes or a separate market-data service"
            )
        bid = decimal(item.get("bid"))
        ask = decimal(item.get("ask"))
        mark = decimal(item.get("mark") or ((bid + ask) / 2 if bid and ask else 0))
        return MarketSnapshot(instrument_id, bid, ask, mark, parse_iso(item.get("captured_at") or utc_now()))

    def get_positions(self, account_id: str) -> Sequence[BrokerPosition]:
        response = self._request("GET", "/position/list")
        result: list[BrokerPosition] = []
        for item in response.json() or []:
            if str(item.get("accountId")) != str(account_id):
                continue
            quantity = decimal(item.get("netPos"))
            if quantity == 0:
                continue
            result.append(BrokerPosition(
                account_id=account_id,
                instrument_id=self._instrument_id(str(item.get("contractId") or item.get("symbol") or "")),
                quantity=quantity,
                average_entry_price=decimal(item.get("netPrice") or item.get("prevPrice")),
                captured_at=parse_iso(item.get("timestamp") or utc_now()),
            ))
        return tuple(result)

    def _snapshot(self, account_id: str, item: Mapping[str, Any]) -> BrokerOrderSnapshot:
        side = Side.BUY if str(item.get("action") or "Buy").lower() == "buy" else Side.SELL
        status = status_from_text(str(item.get("ordStatus") or item.get("status") or "working"))
        return BrokerOrderSnapshot(
            account_id=account_id,
            instrument_id=self._instrument_id(str(item.get("contractId") or item.get("symbol") or "")),
            client_order_id=str(item.get("customTag50") or item.get("orderId") or ""),
            broker_order_id=str(item.get("id") or item.get("orderId") or ""),
            status=status,
            side=side,
            quantity=decimal(item.get("orderQty")),
            filled_quantity=decimal(item.get("cumQty")),
            average_fill_price=decimal(item.get("avgPx")) if item.get("avgPx") is not None else None,
            captured_at=parse_iso(item.get("timestamp") or utc_now()),
            reduce_only=bool(item.get("isLiquidation", False)),
        )

    def get_open_orders(self, account_id: str) -> Sequence[BrokerOrderSnapshot]:
        response = self._request("GET", "/order/list")
        result = []
        for item in response.json() or []:
            if str(item.get("accountId")) != str(account_id):
                continue
            snapshot = self._snapshot(account_id, item)
            if not snapshot.status.terminal:
                result.append(snapshot)
        return tuple(result)

    def get_order(self, *, account_id: str, client_order_id: str, broker_order_id: str | None = None) -> BrokerOrderSnapshot | None:
        response = self._request("GET", "/order/list")
        for item in response.json() or []:
            if str(item.get("accountId")) != str(account_id):
                continue
            snapshot = self._snapshot(account_id, item)
            if broker_order_id and snapshot.broker_order_id == str(broker_order_id):
                return snapshot
            if snapshot.client_order_id == client_order_id:
                return snapshot
        return None

    def estimate_margin(self, intent: OrderIntent) -> MarginEstimate:
        account = self.get_account_snapshot(intent.account_id)
        return MarginEstimate(
            initial_margin=account.initial_margin_used,
            maintenance_margin=account.maintenance_margin_used,
            source="tradovate-account-snapshot",
            captured_at=account.captured_at,
        )

    def poll_order_updates(self, account_id: str) -> Iterable[BrokerOrderUpdate]:
        response = self._request("GET", "/order/list")
        updates: list[BrokerOrderUpdate] = []
        for item in response.json() or []:
            if str(item.get("accountId")) != str(account_id):
                continue
            snapshot = self._snapshot(account_id, item)
            state = (snapshot.status.value, str(snapshot.filled_quantity))
            previous = self._known_states.get(snapshot.broker_order_id)
            if previous == state:
                continue
            self._known_states[snapshot.broker_order_id] = state
            previous_filled = Decimal(previous[1]) if previous else Decimal("0")
            if snapshot.status in {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED}:
                increment = snapshot.filled_quantity - previous_filled
                if increment <= 0:
                    continue
                execution_id = str(item.get("execId") or f"{snapshot.broker_order_id}:{snapshot.filled_quantity}")
                updates.append(BrokerOrderUpdate(
                    source=self.name,
                    external_event_id=f"execution:{execution_id}",
                    account_id=account_id,
                    instrument_id=snapshot.instrument_id,
                    client_order_id=snapshot.client_order_id,
                    broker_order_id=snapshot.broker_order_id,
                    update_type=OrderUpdateType.FILL if snapshot.status is OrderStatus.FILLED else OrderUpdateType.PARTIAL_FILL,
                    occurred_at=snapshot.captured_at,
                    execution_id=execution_id,
                    fill_quantity=increment,
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
            update_type = mapping.get(snapshot.status)
            if update_type is None:
                continue
            digest = hashlib.sha256(f"{snapshot.broker_order_id}:{state}".encode()).hexdigest()[:24]
            updates.append(BrokerOrderUpdate(
                source=self.name,
                external_event_id=f"order:{digest}",
                account_id=account_id,
                instrument_id=snapshot.instrument_id,
                client_order_id=snapshot.client_order_id,
                broker_order_id=snapshot.broker_order_id,
                update_type=update_type,
                occurred_at=snapshot.captured_at,
                reason=str(item.get("text") or item.get("rejectReason") or "") or None,
            ))
        return tuple(updates)
