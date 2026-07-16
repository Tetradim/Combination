from sentinel_combination.brokers.catalog import (
    FuturesProduct,
    get_broker_company,
    list_broker_companies,
)
from sentinel_combination.brokers.registry import BrokerRegistry


def test_catalog_contains_major_listed_futures_brokerages():
    identifiers = {item.broker_id for item in list_broker_companies(product=FuturesProduct.LISTED_FUTURES)}
    assert {
        "interactive_brokers",
        "tradestation",
        "tradovate",
        "ninjatrader",
        "optimus_futures",
        "amp_futures",
        "edgeclear",
        "ironbeam",
        "tastytrade",
        "charles_schwab",
        "etrade",
        "webull",
        "robinhood",
        "plus500_futures",
        "stonex",
        "rjo_futures",
        "cannon_trading",
        "phillip_capital",
        "dorman_trading",
        "wedbush_futures",
        "marex",
        "adm_investor_services",
        "advantage_futures",
        "straits_financial",
    } <= identifiers


def test_catalog_contains_crypto_futures_companies():
    identifiers = {item.broker_id for item in list_broker_companies(product=FuturesProduct.CRYPTO_FUTURES)}
    assert {
        "binance_futures",
        "bybit",
        "okx",
        "bitget",
        "kucoin_futures",
        "kraken_futures",
        "deribit",
        "bitmex",
        "gateio_futures",
        "hyperliquid",
        "coinbase_international",
        "crypto_com_exchange",
        "mexc",
        "htx",
        "phemex",
        "woo_x",
        "bingx",
        "dydx",
    } <= identifiers


def test_aliases_and_registry_resolve():
    assert get_broker_company("IBKR").broker_id == "interactive_brokers"
    assert get_broker_company("thinkorswim").broker_id == "charles_schwab"
    adapters = set(BrokerRegistry().adapters)
    assert {"ibkr", "tradestation", "tradovate", "ninjatrader", "bybit", "okx"} <= adapters
