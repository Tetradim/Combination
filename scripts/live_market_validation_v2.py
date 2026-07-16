from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def choose_market(markets: dict[str, dict[str, Any]]) -> tuple[str | None, dict[str, Any] | None]:
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for symbol, market in markets.items():
        if market.get("active") is False:
            continue
        if not (market.get("swap") or market.get("future")):
            continue
        base = str(market.get("base", "")).upper()
        if base != "BTC":
            continue
        quote = str(market.get("quote", "")).upper()
        settle = str(market.get("settle", "")).upper()
        score = {"USDT": 0, "USD": 1, "USDC": 2}.get(quote, 10)
        if market.get("swap"):
            score -= 2
        if settle in {"USDT", "USD", "USDC"}:
            score -= 1
        candidates.append((score, symbol, market))
    if not candidates:
        return None, None
    _, symbol, market = min(candidates, key=lambda item: (item[0], item[1]))
    return symbol, market


def fetch_book(exchange: Any, symbol: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    if not exchange.has.get("fetchOrderBook"):
        return None, [{"method": "fetch_order_book", "status": "unsupported"}]
    for limit in (5, 20, 100, None):
        try:
            started = time.perf_counter()
            if limit is None:
                book = exchange.fetch_order_book(symbol)
            else:
                book = exchange.fetch_order_book(symbol, limit)
            attempts.append(
                {
                    "method": "fetch_order_book",
                    "limit": limit,
                    "status": "success",
                    "duration_seconds": round(time.perf_counter() - started, 4),
                }
            )
            return book, attempts
        except Exception as exc:
            attempts.append(
                {
                    "method": "fetch_order_book",
                    "limit": limit,
                    "status": "failure",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return None, attempts


def fetch_ticker_or_fallback(exchange: Any, symbol: str, book: dict[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    ticker: dict[str, Any] = {}
    if exchange.has.get("fetchTicker"):
        try:
            started = time.perf_counter()
            ticker = exchange.fetch_ticker(symbol)
            attempts.append(
                {
                    "method": "fetch_ticker",
                    "status": "success",
                    "duration_seconds": round(time.perf_counter() - started, 4),
                }
            )
            return ticker, attempts
        except Exception as exc:
            attempts.append(
                {
                    "method": "fetch_ticker",
                    "status": "failure",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    else:
        attempts.append({"method": "fetch_ticker", "status": "unsupported"})

    bids = (book or {}).get("bids") or []
    asks = (book or {}).get("asks") or []
    bid = bids[0][0] if bids else None
    ask = asks[0][0] if asks else None
    last = None
    if bid is not None and ask is not None:
        last = (float(bid) + float(ask)) / 2.0
    ticker = {
        "bid": bid,
        "ask": ask,
        "last": last,
        "timestamp": (book or {}).get("timestamp"),
        "source": "order_book_fallback",
    }
    return ticker, attempts


def validate_exchange(ccxt: Any, company: str, ids: list[str], options: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "company": company,
        "candidate_ccxt_ids": ids,
        "started_at": now_iso(),
    }
    exchange_id = next((item for item in ids if hasattr(ccxt, item)), None)
    if exchange_id is None:
        row.update(
            {
                "status": "ccxt_class_missing",
                "available_candidate_ids": [],
            }
        )
        return row

    row["exchange_id"] = exchange_id
    exchange = None
    started = time.perf_counter()
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class(
            {
                "enableRateLimit": True,
                "timeout": 30000,
                **options,
            }
        )
        row["capabilities"] = {
            key: bool(exchange.has.get(key))
            for key in (
                "fetchMarkets",
                "fetchTicker",
                "fetchOrderBook",
                "fetchFundingRate",
                "fetchTrades",
                "fetchOHLCV",
                "createOrder",
                "cancelOrder",
                "fetchOpenOrders",
                "fetchPositions",
            )
        }
        markets = exchange.load_markets()
        row["market_count"] = len(markets)
        symbol, market = choose_market(markets)
        row["selected_symbol"] = symbol
        if symbol is None or market is None:
            raise RuntimeError("No active BTC futures or swap market found")
        row["selected_market"] = {
            key: market.get(key)
            for key in (
                "id",
                "symbol",
                "base",
                "quote",
                "settle",
                "swap",
                "future",
                "linear",
                "inverse",
                "active",
                "contractSize",
                "expiry",
                "precision",
                "limits",
            )
        }

        book, book_attempts = fetch_book(exchange, symbol)
        ticker, ticker_attempts = fetch_ticker_or_fallback(exchange, symbol, book)
        row["attempts"] = book_attempts + ticker_attempts
        bids = (book or {}).get("bids") or []
        asks = (book or {}).get("asks") or []
        bid = ticker.get("bid") if ticker.get("bid") is not None else (bids[0][0] if bids else None)
        ask = ticker.get("ask") if ticker.get("ask") is not None else (asks[0][0] if asks else None)
        last = ticker.get("last")
        if last is None and bid is not None and ask is not None:
            last = (float(bid) + float(ask)) / 2.0
        row.update(
            {
                "status": "reachable",
                "bid": bid,
                "ask": ask,
                "last": last,
                "ticker_timestamp": ticker.get("timestamp"),
                "order_book_timestamp": (book or {}).get("timestamp"),
                "bid_levels": len(bids),
                "ask_levels": len(asks),
                "spread_valid": bid is None or ask is None or float(bid) <= float(ask),
                "positive_reference_price": last is None or float(last) > 0,
                "ticker_source": ticker.get("source", "fetch_ticker"),
            }
        )

        if exchange.has.get("fetchFundingRate"):
            try:
                funding = exchange.fetch_funding_rate(symbol)
                row["funding"] = {
                    "funding_rate": funding.get("fundingRate"),
                    "timestamp": funding.get("timestamp"),
                    "next_funding_timestamp": funding.get("nextFundingTimestamp"),
                }
            except Exception as exc:
                row["funding_error"] = f"{type(exc).__name__}: {exc}"

        if book is None and not any(item.get("status") == "success" for item in ticker_attempts):
            row["status"] = "markets_loaded_but_no_price_method_succeeded"
    except Exception as exc:
        row["status"] = "blocked_or_failed"
        row["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        row["duration_seconds"] = round(time.perf_counter() - started, 4)
        if exchange is not None:
            try:
                exchange.close()
            except Exception:
                pass
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="live-market-v2")
    args = parser.parse_args()

    import ccxt

    specs: list[tuple[str, list[str], dict[str, Any]]] = [
        ("Binance Futures", ["binanceusdm"], {"options": {"defaultType": "future"}}),
        ("Bybit", ["bybit"], {"options": {"defaultType": "swap"}}),
        ("OKX", ["okx"], {"options": {"defaultType": "swap"}}),
        ("Bitget", ["bitget"], {"options": {"defaultType": "swap"}}),
        ("KuCoin Futures", ["kucoinfutures"], {}),
        ("Kraken Futures", ["krakenfutures"], {}),
        ("Deribit", ["deribit"], {}),
        ("BitMEX", ["bitmex"], {}),
        ("Gate.io Futures", ["gate", "gateio"], {"options": {"defaultType": "swap"}}),
        ("Hyperliquid", ["hyperliquid"], {}),
        ("Coinbase International", ["coinbaseinternational"], {}),
        ("Crypto.com Exchange", ["cryptocom"], {"options": {"defaultType": "swap"}}),
        ("MEXC", ["mexc"], {"options": {"defaultType": "swap"}}),
        ("HTX", ["htx", "huobi"], {"options": {"defaultType": "swap"}}),
        ("Phemex", ["phemex"], {}),
        ("WOO X", ["woo"], {}),
        ("BingX", ["bingx"], {"options": {"defaultType": "swap"}}),
        ("dYdX", ["dydx"], {}),
    ]

    results = [validate_exchange(ccxt, company, ids, options) for company, ids, options in specs]
    reached = sum(1 for row in results if row.get("status") == "reachable")
    payload = {
        "generated_at": now_iso(),
        "ccxt_version": getattr(ccxt, "__version__", None),
        "policy": "Unauthenticated read-only public market data only. No order, cancellation, account, position, or credential call was executed.",
        "company_count": len(results),
        "reachable_count": reached,
        "results": results,
    }
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "live-market-results-v2.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    lines = [
        "# Public derivatives market validation v2",
        "",
        f"Generated: `{payload['generated_at']}`",
        f"CCXT version: `{payload['ccxt_version']}`",
        f"Reached: **{reached}/{len(results)}** companies",
        "",
        "| Company | CCXT ID | Status | Symbol | Bid | Ask | Last/source |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for row in results:
        source = row.get("ticker_source", "")
        last = row.get("last")
        lines.append(
            "| {company} | {exchange_id} | {status} | {symbol} | {bid} | {ask} | {last} {source} |".format(
                company=row.get("company", ""),
                exchange_id=row.get("exchange_id", ""),
                status=row.get("status", ""),
                symbol=row.get("selected_symbol", ""),
                bid=row.get("bid", ""),
                ask=row.get("ask", ""),
                last=last if last is not None else "",
                source=f"({source})" if source else "",
            )
        )
    lines.extend(
        [
            "",
            "This validates only public data discovery and normalization. It does not validate authenticated order lifecycle behavior.",
        ]
    )
    (output_dir / "LIVE_MARKET_REPORT_V2.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
