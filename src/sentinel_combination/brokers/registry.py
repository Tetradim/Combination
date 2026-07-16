from __future__ import annotations

from collections.abc import Callable, Mapping

from sentinel_combination.config import BrokerConfig
from sentinel_combination.ports.broker import BrokerPort, BrokerUnsupported

from .catalog import BrokerCompany, get_broker_company, list_broker_companies
from .ccxt_derivatives import CCXTDerivativesBroker, PRESETS
from .ibkr import IBKRBroker
from .tradestation import TradeStationBroker
from .tradovate import TradovateBroker


BrokerFactory = Callable[[str, BrokerConfig], BrokerPort]


class BrokerRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, BrokerFactory] = {}
        self.register("ibkr", IBKRBroker)
        self.register("interactive_brokers", IBKRBroker)
        self.register("tradestation", TradeStationBroker)
        self.register("tradovate", TradovateBroker)
        self.register("ninjatrader", TradovateBroker)
        for adapter in PRESETS:
            self.register(adapter, CCXTDerivativesBroker)

    def register(self, adapter: str, factory: BrokerFactory) -> None:
        key = adapter.strip().lower()
        if not key:
            raise ValueError("adapter is required")
        self._factories[key] = factory

    @property
    def adapters(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

    def build(self, name: str, config: BrokerConfig) -> BrokerPort:
        requested = config.adapter.strip().lower()
        company: BrokerCompany | None = None
        try:
            company = get_broker_company(requested)
        except KeyError:
            try:
                company = get_broker_company(name)
            except KeyError:
                company = None
        adapter = requested
        if company is not None and company.default_adapter:
            adapter = company.default_adapter
        if adapter not in self._factories:
            transport = str(config.settings.get("transport_adapter", "")).strip().lower()
            if transport:
                adapter = transport
        factory = self._factories.get(adapter)
        if factory is None:
            company_name = company.display_name if company else requested
            raise BrokerUnsupported(
                f"{company_name} is in the futures-broker catalog but has no configured transport adapter; "
                f"set settings.transport_adapter to one of: {', '.join(self.adapters)}"
            )
        effective = BrokerConfig(
            adapter=adapter,
            account_id=config.account_id,
            environment=config.environment,
            enabled=config.enabled,
            credentials=config.credentials,
            settings=config.settings,
        )
        return factory(name, effective)

    def companies(self) -> tuple[BrokerCompany, ...]:
        return list_broker_companies()


_DEFAULT_REGISTRY = BrokerRegistry()


def build_broker(name: str, config: BrokerConfig) -> BrokerPort:
    return _DEFAULT_REGISTRY.build(name, config)
