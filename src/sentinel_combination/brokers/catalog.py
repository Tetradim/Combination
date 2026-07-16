from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FuturesProduct(str, Enum):
    LISTED_FUTURES = "listed_futures"
    CRYPTO_FUTURES = "crypto_futures"


@dataclass(frozen=True)
class BrokerCompany:
    broker_id: str
    display_name: str
    products: tuple[FuturesProduct, ...]
    default_adapter: str | None = None
    aliases: tuple[str, ...] = ()

    def matches(self, value: str) -> bool:
        needle = value.strip().lower().replace(" ", "_").replace("-", "_")
        candidates = {
            self.broker_id,
            self.display_name.lower().replace(" ", "_").replace("-", "_"),
            *(alias.lower().replace(" ", "_").replace("-", "_") for alias in self.aliases),
        }
        return needle in candidates


BROKER_COMPANIES: tuple[BrokerCompany, ...] = (
    BrokerCompany("interactive_brokers", "Interactive Brokers", (FuturesProduct.LISTED_FUTURES,), "ibkr", ("ibkr", "ib")),
    BrokerCompany("tradestation", "TradeStation", (FuturesProduct.LISTED_FUTURES,), "tradestation"),
    BrokerCompany("tradovate", "Tradovate", (FuturesProduct.LISTED_FUTURES,), "tradovate"),
    BrokerCompany("ninjatrader", "NinjaTrader", (FuturesProduct.LISTED_FUTURES,), "tradovate", ("ninja_trader",)),
    BrokerCompany("optimus_futures", "Optimus Futures", (FuturesProduct.LISTED_FUTURES,), aliases=("optimus",)),
    BrokerCompany("amp_futures", "AMP Futures", (FuturesProduct.LISTED_FUTURES,), aliases=("amp",)),
    BrokerCompany("edgeclear", "EdgeClear", (FuturesProduct.LISTED_FUTURES,), aliases=("edge_clear",)),
    BrokerCompany("ironbeam", "Ironbeam", (FuturesProduct.LISTED_FUTURES,)),
    BrokerCompany("tastytrade", "tastytrade", (FuturesProduct.LISTED_FUTURES,), aliases=("tasty",)),
    BrokerCompany("charles_schwab", "Charles Schwab", (FuturesProduct.LISTED_FUTURES,), aliases=("schwab", "thinkorswim")),
    BrokerCompany("etrade", "E*TRADE from Morgan Stanley", (FuturesProduct.LISTED_FUTURES,), aliases=("e_trade", "morgan_stanley_etrade")),
    BrokerCompany("webull", "Webull", (FuturesProduct.LISTED_FUTURES,)),
    BrokerCompany("robinhood", "Robinhood", (FuturesProduct.LISTED_FUTURES,)),
    BrokerCompany("plus500_futures", "Plus500 Futures", (FuturesProduct.LISTED_FUTURES,), aliases=("plus500",)),
    BrokerCompany("stonex", "StoneX", (FuturesProduct.LISTED_FUTURES,), aliases=("stonex_futures", "daniels_trading")),
    BrokerCompany("rjo_futures", "RJO Futures", (FuturesProduct.LISTED_FUTURES,), aliases=("rjo",)),
    BrokerCompany("cannon_trading", "Cannon Trading", (FuturesProduct.LISTED_FUTURES,), aliases=("cannon",)),
    BrokerCompany("phillip_capital", "Phillip Capital", (FuturesProduct.LISTED_FUTURES,), aliases=("phillipcapital",)),
    BrokerCompany("dorman_trading", "Dorman Trading", (FuturesProduct.LISTED_FUTURES,), aliases=("dorman",)),
    BrokerCompany("wedbush_futures", "Wedbush Futures", (FuturesProduct.LISTED_FUTURES,), aliases=("wedbush",)),
    BrokerCompany("marex", "Marex", (FuturesProduct.LISTED_FUTURES,)),
    BrokerCompany("adm_investor_services", "ADM Investor Services", (FuturesProduct.LISTED_FUTURES,), aliases=("admis",)),
    BrokerCompany("advantage_futures", "Advantage Futures", (FuturesProduct.LISTED_FUTURES,), aliases=("advantage",)),
    BrokerCompany("straits_financial", "Straits Financial", (FuturesProduct.LISTED_FUTURES,), aliases=("straits",)),
    BrokerCompany("discount_trading", "Discount Trading", (FuturesProduct.LISTED_FUTURES,)),
    BrokerCompany("stage_5_trading", "Stage 5 Trading", (FuturesProduct.LISTED_FUTURES,), aliases=("stage5",)),
    BrokerCompany("binance_futures", "Binance Futures", (FuturesProduct.CRYPTO_FUTURES,), "binance_usdm", ("binance", "binance_usdm", "binance_coinm")),
    BrokerCompany("bybit", "Bybit", (FuturesProduct.CRYPTO_FUTURES,), "bybit"),
    BrokerCompany("okx", "OKX", (FuturesProduct.CRYPTO_FUTURES,), "okx"),
    BrokerCompany("bitget", "Bitget", (FuturesProduct.CRYPTO_FUTURES,), "bitget"),
    BrokerCompany("kucoin_futures", "KuCoin Futures", (FuturesProduct.CRYPTO_FUTURES,), "kucoin_futures", ("kucoin",)),
    BrokerCompany("kraken_futures", "Kraken Futures", (FuturesProduct.CRYPTO_FUTURES,), "kraken_futures", ("kraken",)),
    BrokerCompany("deribit", "Deribit", (FuturesProduct.CRYPTO_FUTURES,), "deribit"),
    BrokerCompany("bitmex", "BitMEX", (FuturesProduct.CRYPTO_FUTURES,), "bitmex"),
    BrokerCompany("gateio_futures", "Gate.io Futures", (FuturesProduct.CRYPTO_FUTURES,), "gateio_futures", ("gateio", "gate_io")),
    BrokerCompany("hyperliquid", "Hyperliquid", (FuturesProduct.CRYPTO_FUTURES,), "hyperliquid"),
    BrokerCompany("coinbase_international", "Coinbase International Exchange", (FuturesProduct.CRYPTO_FUTURES,), "coinbase_international", ("coinbaseinternational",)),
    BrokerCompany("crypto_com_exchange", "Crypto.com Exchange", (FuturesProduct.CRYPTO_FUTURES,), "cryptocom", ("crypto_com",)),
    BrokerCompany("mexc", "MEXC", (FuturesProduct.CRYPTO_FUTURES,), "mexc"),
    BrokerCompany("htx", "HTX", (FuturesProduct.CRYPTO_FUTURES,), "htx", ("huobi",)),
    BrokerCompany("phemex", "Phemex", (FuturesProduct.CRYPTO_FUTURES,), "phemex"),
    BrokerCompany("woo_x", "WOO X", (FuturesProduct.CRYPTO_FUTURES,), "woo", ("woo",)),
    BrokerCompany("bingx", "BingX", (FuturesProduct.CRYPTO_FUTURES,), "bingx"),
    BrokerCompany("dydx", "dYdX", (FuturesProduct.CRYPTO_FUTURES,), "dydx"),
)


def list_broker_companies(*, product: FuturesProduct | None = None) -> tuple[BrokerCompany, ...]:
    if product is None:
        return BROKER_COMPANIES
    return tuple(company for company in BROKER_COMPANIES if product in company.products)


def get_broker_company(value: str) -> BrokerCompany:
    for company in BROKER_COMPANIES:
        if company.matches(value):
            return company
    raise KeyError(f"unknown futures brokerage {value!r}")
