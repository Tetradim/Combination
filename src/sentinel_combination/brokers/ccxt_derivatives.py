from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

from sentinel_combination.brokers.common import (
    ccxt_order_type,
    decimal,
    status_from_text,
    utc_now,
)
from sentinel_combination.config import BrokerConfig
from sentinel_combination.domain.enums import (
    AssetClass,
    OrderStatus,
    OrderType,
    OrderUpdateType,
    Side,
)
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


@dataclass(frozen=True)
class CCXTDerivativePreset:
    adapter: str
    exchange_id: str
    sandbox_supported: bool
    default_type: str
    display_name: str


PRESETS: dict[str, CCXTDerivativePreset] = {
    "binance_usdm": CCXTDerivativePreset("binance_usdm", "binanceusdm", True, "future", "Binance USD-M Futures"),
    "binance_coinm": CCXTDerivativePreset("binance_coinm", "binancecoinm", True, "delivery", "Binance COIN-M Futures"),
    "bybit": CCXTDerivativePreset("bybit", "bybit", True, "swap", "Bybit Derivatives"),
    "okx": CCXTDerivativePreset("okx", "okx", True, "swap", "OKX Derivatives"),
    "bitget": CCXTDerivativePreset("bitget", "bitget", True, "swap", "Bitget Derivatives"),
    "kucoin_futures": CCXTDerivativePreset("kucoin_futures", "kucoinfutures", True, "swap", "KuCoin Futures"),
    "kraken_futures": CCXTDerivativePreset("kraken_futures", "krakenfutures", True, "future", "Kraken Futures"),
    "deribit": CCXTDerivativePreset("deribit", "deribit", True, "future", "Deribit"),
    "bitmex": CCXTDerivativePreset("bitmex", "bitmex", True, "swap", "BitMEX"),
    "gateio_futures": CCXTDerivativePreset("gateio_futures", "gateio", False, "swap", "Gate.io Futures"),
    "hyperliquid": CCXTDerivativePreset("hyperliquid", "hyperliquid", True, "swap", "Hyperliquid"),
    "coinbase_international": CCXTDerivativePreset("coinbase_international", "coinbaseinternational", False, "swap", "Coinbase International Exchange"),
    "cryptocom": CCXTDerivativePreset("cryptocom", "cryptocom", False, "swap", "Crypto.com Exchange"),
    "mexc": CCXTDerivativePreset("mexc", "mexc", False, "swap", "MEXC"),
    "htx": CCXTDerivativePreset("htx", "htx", False, "swap", "HTX"),
    "phemex": CCXTDerivativePreset("phemex", "phemex", False, "swap", "Phemex"),
    "woo": CCXTDerivativePreset("woo", "woo", False, "swap", "WOO X"),
    "bingx": CCXTDerivativePreset("bingx", "bingx", False, "swap", "BingX"),
    "dydx": CCXTDerivativePreset("dydx", "dydx", False, "swap", "dYdX"),
}


class CCXTDerivativesBroker:
    """Broker-authoritative adapter for derivatives exchanges supported by CCXT.

    CCXT is used only as a transport/unification library. Every state change still
    comes from the exchange's order, trade, position, and balance responses.
    """

    def __init__(self, name: str, config: BrokerConfig) -> None:
        if config.adapter not in PRESETS:
            raise ValueError(f"unknown CCXT derivatives adapter {config.adapter!r}")
        self._name = name
        self.config = config
        self.preset = PRESETS[config.adapter]
        self._exchange: Any | None = None
        self._last_trade_ms: int | None = None
        self._known_trade_ids: set[str] = set()
        self._known_order_states: dict[str, tuple[str, str]] = {}

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
            cancel_replace=False,
            margin_preview=True,
            streaming_order_updates=False,
            reduce_only=True,
            native_bracket=False,
            supports_crypto_derivatives=True,
            broker_managed_test_environment=self.preset.sandbox_supported,
            asset_classes=(AssetClass.CRYPTO_PERPETUAL,),
        )

    def _symbol(self, instrument_id: str) -> str:
        mapping = self.config.settings.get("symbols") or {}
        return str(mapping.get(instrument_id, instrument_id))

    def _instrument_id(self, symbol: str) -> str:
        mapping = self.config.settings.get("symbols") or {}
        for instrument_id, configured_symbol in mapping.items():
            if configured_symbol == symbol:
                return str(instrument_id)
        return symbol

    def connect(self) -> None:
        try:
            import ccxt  # type: ignore
        except ImportError as exc:
            raise BrokerUnsupported(
                "CCXT adapter requires the 'crypto-derivatives' extra"
            ) from exc
        exchange_class = getattr(ccxt, self.preset.exchange_id, None)
        if exchange_class is None:
            raise BrokerUnsupported(
                f"installed CCXT does not provide {self.preset.exchange_id}"
            )
        params: dict[str, Any] = {
            "apiKey": self.config.secret("api_key"),
            "secret": self.config.secret("api_secret"),
            "enableRateLimit": True,
            "timeout": int(self.config.settings.get("timeout_ms", 15000)),
            "options": {
                "defaultType": self.config.settings.get(
                    "default_type", self.preset.default_type
                )
            },
        }
        password = self.config.secret("passphrase", required=False)
        if password:
            params["password"] = password
        uid = self.config.secret("uid", required=False)
        if uid:
            params["uid"] = uid
        if self.config.adapter == "okx" and self.environment != "live":
            params["headers"] = {"x-simulated-trading": "1"}
        self._exchange = exchange_class(params)
        if self.environment != "live":
            if not self.preset.sandbox_supported:
                raise BrokerUnsupported(
                    f"{self.preset.display_name} has no configured broker-managed test environment"
                )
            try:
                self._exchange.set_sandbox_mode(True)
            except Exception as exc:
                raise BrokerUnsupported(
                    f"unable to activate sandbox for {self.preset.display_name}: {exc}"
                ) from exc
        try:
            self._exchange.load_markets()
            self._exchange.fetch_balance()
        except Exception as exc:
            self._exchange = None
            raise BrokerAuthenticationError(str(exc)) from exc

    def disconnect(self) -> None:
        exchange = self._exchange
        self._exchange = None
        if exchange is not None:
            close = getattr(exchange, "close", None)
            if callable(close):
                close()

    def is_connected(self) -> bool:
        return self._exchange is not None

    def _require_exchange(self) -> Any:
        if self._exchange is None:
            raise BrokerAuthenticationError(f"{self.name} is not connected")
        return self._exchange

    def submit_order(self, intent: OrderIntent) -> BrokerSubmitResult:
        exchange = self._require_exchange()
        symbol = self._symbol(intent.instrument_id)
        params: dict[str, Any] = {
            "clientOrderId": intent.client_order_id,
        }
        if intent.reduce_only:
            params["reduceOnly"] = True
        if intent.oca_group_id:
            params["ocaGroup"] = intent.oca_group_id
        if intent.order_type in {OrderType.STOP, OrderType.STOP_LIMIT}:
            params["stopPrice"] = float(intent.stop_price or Decimal("0"))
            params["triggerPrice"] = float(intent.stop_price or Decimal("0"))
        if intent.order_type is OrderType.TRAILING_STOP:
            trail = intent.metadata.get("trailing_percent") if hasattr(intent, "metadata") else None
            if trail is not None:
                params["trailingPercent"] = float(trail)
        try:
            order = exchange.create_order(
                symbol,
                ccxt_order_type(intent),
                intent.side.value,
                float(intent.quantity),
                float(intent.limit_price) if intent.limit_price is not None else None,
                params,
            )
        except Exception as exc:
            name = exc.__class__.__name__.lower()
            if "timeout" in name or "network" in name or "unavailable" in name:
                raise BrokerUnknownOutcome(str(exc)) from exc
            raise BrokerRejected(str(exc)) from exc
        order_id = str(order.get("id") or "")
        if not order_id:
            raise BrokerUnknownOutcome("exchange accepted request without an order ID")
        return BrokerSubmitResult(order_id, utc_now())

    def cancel_order(
        self,
        *,
        account_id: str,
        client_order_id: str,
        broker_order_id: str,
    ) -> None:
        exchange = self._require_exchange()
        try:
            exchange.cancel_order(
                broker_order_id,
                None,
                {"clientOrderId": client_order_id},
            )
        except Exception as exc:
            raise BrokerUnknownOutcome(str(exc)) from exc

    def replace_order(
        self,
        *,
        lifecycle_client_order_id: str,
        broker_order_id: str,
        replacement: OrderIntent,
    ) -> BrokerSubmitResult:
        exchange = self._require_exchange()
        edit = getattr(exchange, "edit_order", None)
        if not callable(edit) or not exchange.has.get("editOrder"):
            raise BrokerUnsupported(f"{self.name} does not expose atomic replace")
        params: dict[str, Any] = {"clientOrderId": replacement.client_order_id}
        if replacement.reduce_only:
            params["reduceOnly"] = True
        if replacement.stop_price is not None:
            params["stopPrice"] = float(replacement.stop_price)
            params["triggerPrice"] = float(replacement.stop_price)
        try:
            order = edit(
                broker_order_id,
                self._symbol(replacement.instrument_id),
                ccxt_order_type(replacement),
                replacement.side.value,
                float(replacement.quantity),
                float(replacement.limit_price)
                if replacement.limit_price is not None
                else None,
                params,
            )
        except Exception as exc:
            raise BrokerUnknownOutcome(str(exc)) from exc
        return BrokerSubmitResult(str(order["id"]), utc_now())

    def get_account_snapshot(self, account_id: str) -> AccountSnapshot:
        balance = self._require_exchange().fetch_balance()
        total = balance.get("total") or {}
        free = balance.get("free") or {}
        currency = str(self.config.settings.get("settlement_currency", "USDT"))
        equity = decimal(total.get(currency) or balance.get("info", {}).get("equity"))
        buying_power = decimal(free.get(currency) or balance.get("info", {}).get("availableBalance"))
        return AccountSnapshot(
            account_id=account_id,
            equity=equity,
            available_buying_power=buying_power,
            captured_at=utc_now(),
            currency=currency,
        )

    def get_market_snapshot(self, instrument_id: str) -> MarketSnapshot:
        ticker = self._require_exchange().fetch_ticker(self._symbol(instrument_id))
        bid = decimal(ticker.get("bid"))
        ask = decimal(ticker.get("ask"))
        mark = decimal(
            ticker.get("mark")
            or ticker.get("last")
            or ((bid + ask) / Decimal("2") if bid and ask else None)
        )
        return MarketSnapshot(instrument_id, bid, ask, mark, utc_now())

    def get_positions(self, account_id: str) -> Sequence[BrokerPosition]:
        exchange = self._require_exchange()
        raw = exchange.fetch_positions()
        result: list[BrokerPosition] = []
        for item in raw:
            contracts = decimal(item.get("contracts"))
            if contracts == 0:
                continue
            side = str(item.get("side") or "long").lower()
            quantity = contracts if side == "long" else -contracts
            result.append(
                BrokerPosition(
                    account_id=account_id,
                    instrument_id=self._instrument_id(str(item.get("symbol"))),
                    quantity=quantity,
                    average_entry_price=decimal(item.get("entryPrice")),
                    captured_at=utc_now(),
                )
            )
        return tuple(result)

    def _snapshot(self, account_id: str, item: Mapping[str, Any]) -> BrokerOrderSnapshot:
        status = status_from_text(str(item.get("status") or "open"))
        side = Side(str(item.get("side") or "buy").lower())
        amount = decimal(item.get("amount"))
        filled = decimal(item.get("filled"))
        client_id = str(
            item.get("clientOrderId")
            or (item.get("info") or {}).get("clientOrderId")
            or (item.get("info") or {}).get("orderLinkId")
            or item.get("id")
        )
        return BrokerOrderSnapshot(
            account_id=account_id,
            instrument_id=self._instrument_id(str(item.get("symbol"))),
            client_order_id=client_id,
            broker_order_id=str(item.get("id")),
            status=status,
            side=side,
            quantity=amount,
            filled_quantity=filled,
            average_fill_price=decimal(item.get("average")) if item.get("average") else None,
            captured_at=utc_now(),
            reduce_only=bool((item.get("info") or {}).get("reduceOnly", False)),
        )

    def get_open_orders(self, account_id: str) -> Sequence[BrokerOrderSnapshot]:
        items = self._require_exchange().fetch_open_orders()
        return tuple(self._snapshot(account_id, item) for item in items)

    def get_order(
        self,
        *,
        account_id: str,
        client_order_id: str,
        broker_order_id: str | None = None,
    ) -> BrokerOrderSnapshot | None:
        exchange = self._require_exchange()
        try:
            if broker_order_id:
                item = exchange.fetch_order(broker_order_id)
                return self._snapshot(account_id, item)
            for item in exchange.fetch_orders():
                snapshot = self._snapshot(account_id, item)
                if snapshot.client_order_id == client_order_id:
                    return snapshot
        except Exception:
            return None
        return None

    def estimate_margin(self, intent: OrderIntent) -> MarginEstimate:
        market = self.get_market_snapshot(intent.instrument_id)
        leverage = decimal(self.config.settings.get("leverage", "1"))
        if leverage <= 0:
            raise ValueError("configured leverage must be positive")
        multiplier = decimal(self.config.settings.get("contract_multiplier", "1"))
        notional = market.mark * intent.quantity * multiplier
        initial = abs(notional) / leverage
        maintenance_rate = decimal(
            self.config.settings.get("maintenance_margin_rate", "0.005")
        )
        maintenance = abs(notional) * maintenance_rate
        return MarginEstimate(initial, maintenance, f"{self.name}:exchange-config", utc_now())

    def poll_order_updates(self, account_id: str) -> Iterable[BrokerOrderUpdate]:
        exchange = self._require_exchange()
        now_ms = int(utc_now().timestamp() * 1000)
        since = self._last_trade_ms or max(0, now_ms - 60_000)
        updates: list[BrokerOrderUpdate] = []
        if exchange.has.get("fetchMyTrades"):
            try:
                trades = exchange.fetch_my_trades(since=since)
            except Exception:
                trades = []
            for trade in trades:
                trade_id = str(trade.get("id") or "")
                if not trade_id or trade_id in self._known_trade_ids:
                    continue
                self._known_trade_ids.add(trade_id)
                timestamp = int(trade.get("timestamp") or now_ms)
                self._last_trade_ms = max(self._last_trade_ms or 0, timestamp + 1)
                info = trade.get("info") or {}
                client_id = str(
                    trade.get("clientOrderId")
                    or info.get("clientOrderId")
                    or info.get("orderLinkId")
                    or trade.get("order")
                )
                updates.append(
                    BrokerOrderUpdate(
                        source=self.name,
                        external_event_id=f"trade:{trade_id}",
                        account_id=account_id,
                        instrument_id=self._instrument_id(str(trade.get("symbol"))),
                        client_order_id=client_id,
                        broker_order_id=str(trade.get("order") or ""),
                        update_type=OrderUpdateType.PARTIAL_FILL,
                        occurred_at=datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc),
                        execution_id=trade_id,
                        fill_quantity=decimal(trade.get("amount")),
                        fill_price=decimal(trade.get("price")),
                        fee=decimal((trade.get("fee") or {}).get("cost")),
                    )
                )
        try:
            order_items = list(exchange.fetch_open_orders())
            if exchange.has.get("fetchClosedOrders"):
                order_items += list(exchange.fetch_closed_orders(since=since))
        except Exception:
            order_items = []
        for item in order_items:
            snapshot = self._snapshot(account_id, item)
            state = (snapshot.status.value, str(snapshot.filled_quantity))
            key = snapshot.broker_order_id
            if self._known_order_states.get(key) == state:
                continue
            self._known_order_states[key] = state
            if snapshot.status in {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED}:
                # Fill quantities are emitted from trades to preserve execution-ID idempotency.
                continue
            try:
                update_type = {
                    OrderStatus.ACKNOWLEDGED: OrderUpdateType.ACKNOWLEDGED,
                    OrderStatus.SUBMITTED: OrderUpdateType.ACKNOWLEDGED,
                    OrderStatus.WORKING: OrderUpdateType.WORKING,
                    OrderStatus.CANCELED: OrderUpdateType.CANCELED,
                    OrderStatus.REJECTED: OrderUpdateType.REJECTED,
                    OrderStatus.EXPIRED: OrderUpdateType.EXPIRED,
                }[snapshot.status]
            except KeyError:
                continue
            digest = hashlib.sha256(
                f"{key}:{state[0]}:{state[1]}".encode("utf-8")
            ).hexdigest()[:24]
            updates.append(
                BrokerOrderUpdate(
                    source=self.name,
                    external_event_id=f"order:{digest}",
                    account_id=account_id,
                    instrument_id=snapshot.instrument_id,
                    client_order_id=snapshot.client_order_id,
                    broker_order_id=snapshot.broker_order_id,
                    update_type=update_type,
                    occurred_at=snapshot.captured_at,
                    reason=(item.get("info") or {}).get("rejectReason"),
                )
            )
        return tuple(updates)
