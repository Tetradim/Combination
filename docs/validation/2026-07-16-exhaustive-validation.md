# Sentinel Combination Exhaustive Validation Report

**Generated:** 2026-07-16T14:32:00Z

## Executive judgment

**Combination passed the code-level, persistence, replay-compatibility, and public crypto-derivatives market-data tests performed in this campaign. It is suitable for continued authenticated broker integration testing. It is not certified for funded trading.**

The strongest positive result is repeatability: the existing Combination suite completed successfully across Python 3.11, 3.12, and 3.13, under randomized execution orders and repeated database/restart cycles. Sentinel Archive also completed its own test suite and exposed a healthy replay API. Public read-only market data was obtained from 16 of the 18 cataloged crypto-derivatives companies.

The strongest limitation is test depth: Combination currently has only **12 unique automated tests**. Repetition increases confidence in determinism and environment compatibility, but it does not replace broader tests for broker lifecycle, authentication, order rejection, partial fills, margin, reconciliation, disconnect recovery, or emergency flattening.

## Exact code and evidence provenance

- Combination commit exercised: `16a1064f47609abc1a88811b04cbc1127deb9536`
- Sentinel Archive commit exercised: `44aa4337cfb15aeb562a874b8dbc3fa799149f18`
- Exhaustive workflow run: `29506041031`
- Expanded public-market workflow run: `29506668493`
- CCXT version used for expanded public-market checks: `4.5.65`

## How the evidence was acquired

1. GitHub Actions checked out the exact Combination `main` commit and installed `.[dev,all-brokers]` in clean Ubuntu runners.
2. The package was installed and compiled separately on Python 3.11, 3.12, and 3.13.
3. Pytest collected the repository's tests, ran the standard suite, and then reran the entire suite with multiple randomized test orders and `PYTHONHASHSEED` values.
4. A separate stress job repeated the full suite 20 additional times, initialized and diagnosed 30 independent SQLite databases, and imported the package/catalog 100 times.
5. CLI commands enumerated every broker company and queried `broker-info` for every catalog entry. SQLite evidence came from `PRAGMA integrity_check`, `journal_mode`, `synchronous`, and schema-table inspection.
6. Sentinel Archive was checked out at its recorded commit, its own test suite was executed, its FastAPI application was imported, and `/api/health` was called through FastAPI's in-process test client.
7. Six deterministic Archive-compatible OHLCV scenarios were generated and validated: trends in both directions, a gap/recovery, same-timestamp multi-symbol data, out-of-order input, and an extreme-range event.
8. Live-market checks used public, unauthenticated CCXT endpoints only: market discovery, ticker, order book, and funding-rate methods where supported. No credentials, account calls, order methods, or cancellation methods were used.
9. Every workflow uploaded raw logs, JUnit XML, JSON results, database files, generated CSV scenarios, dependency lists, commit SHAs, and checksums.

## Test volume

| Measurement | Result |
|---|---:|
| Unique Combination tests | 12 |
| Complete Combination suite runs | 38 |
| Repeated Combination test invocations | 456 |
| Sentinel Archive unique tests | 98 |
| Total test invocations including Archive | 554 |
| Python versions | 3 |
| Database init/doctor cycles | 30 |
| Database failures | 0 |
| Repeated import cycles | 100 |
| Import failures | 0 |
| CLI invocations across Python versions | 150 |

## Combination test inventory

| Test file | Unique tests |
|---|---:|
| `test_brackets.py` | 1 |
| `test_broker_catalog.py` | 3 |
| `test_fill_processor.py` | 1 |
| `test_instruments.py` | 1 |
| `test_lifecycle.py` | 2 |
| `test_order_gateway.py` | 1 |
| `test_positions.py` | 1 |
| `test_readiness.py` | 1 |
| `test_risk.py` | 1 |

### Python compatibility

| Python | Standard suite | Five randomized suites | Module imports | CLI failures | SQLite integrity |
|---|---|---|---:|---:|---|
| 3.11 | 12/12 passed | 5/5 passed | 32 | 0 | ok |
| 3.12 | 12/12 passed | 5/5 passed | 32 | 0 | ok |
| 3.13 | 12/12 passed | 5/5 passed | 32 | 0 | ok |

### Persistence findings

- Thirty independent database initialization/restart cycles completed without failure.
- Every inspected database returned `integrity_check = ok`.
- The database used WAL journaling and FULL synchronous durability (`synchronous = 2`).
- Ten application tables were present in each new validation database.
- The evidence reader observed `foreign_keys = 0` on its own newly opened SQLite inspection connection. This PRAGMA is connection-local; the result does not prove whether application-managed connections enable it, so foreign-key enforcement remains a specific follow-up audit item.

## Broker catalog and executable factory registry

- Cataloged companies: **44**
- Listed-futures companies: **26**
- Crypto-futures companies: **18**
- Registered executable adapter factory keys: **24**
- Duplicate broker IDs: **0**
- Blank broker IDs: **0**

Registered factory keys:

```text
binance_coinm
binance_usdm
bingx
bitget
bitmex
bybit
coinbase_international
cryptocom
deribit
dydx
gateio_futures
htx
hyperliquid
ibkr
interactive_brokers
kraken_futures
kucoin_futures
mexc
ninjatrader
okx
phemex
tradestation
tradovate
woo
```

The first campaign incorrectly displayed zero registered adapters because the evidence collector expected a dictionary while `BrokerRegistry.adapters` returns a tuple. The second workflow directly read the tuple and recorded 24 factory keys. This was a test-harness defect, not a registry defect.

## Sentinel Archive results

- Archive tests: **98 passed**
- Archive API routes discovered: **82**
- `/api/health`: **HTTP 200**
- Health mode: **simulation**
- Health execution setting: **none**
- Recorded CSV/JSONL files found in the checked-out repository: **1**
- Recorded event-bus rows inspected: **15**

### Generated Archive-compatible scenarios

| Scenario | Rows | Timestamp groups | Max same-time group | Input sorted | Invalid OHLC rows |
|---|---:|---:|---:|---|---:|
| steady_up | 10 | 10 | 1 | True | 0 |
| steady_down | 10 | 10 | 1 | True | 0 |
| gap_and_recovery | 3 | 3 | 1 | True | 0 |
| same_timestamp_multi_symbol | 4 | 2 | 2 | True | 0 |
| out_of_order_input | 3 | 3 | 1 | False | 0 |
| extreme_range | 2 | 2 | 1 | True | 0 |

Archive was used as an external replay/data-evidence system. Its simulated account and fill engine were not imported into Combination and did not create Combination positions or fills.

## Public live crypto-derivatives market data

- Initial pass: **9/15** venues reached.
- Corrected expanded pass: **16/18** companies reached.
- The four initial method/identifier failures—KuCoin Futures, Gate.io, WOO X, and dYdX—were corrected in the second harness and then reached successfully.
- Binance Futures and Bybit remained blocked by the GitHub runner's geographic network location, not by a local parsing failure.

| Company | Result | CCXT ID | Selected market | Price result |
|---|---|---|---|---|
| Binance Futures | blocked by region | `binanceusdm` | — | HTTP 451 |
| Bybit | blocked by region | `bybit` | — | CloudFront HTTP 403 |
| OKX | reachable | `okx` | `BTC/USDT:USDT` | valid bid/ask/last |
| Bitget | reachable | `bitget` | `BTC/USDT:USDT` | valid bid/ask/last |
| KuCoin Futures | reachable | `kucoinfutures` | `BTC/USDT:USDT` | valid bid/ask/last |
| Kraken Futures | reachable | `krakenfutures` | `BTC/USD:USD` | valid bid/ask/last |
| Deribit | reachable | `deribit` | `BTC/USD:BTC` | valid bid/ask/last |
| BitMEX | reachable | `bitmex` | `BTC/USDT:USDT` | valid bid/ask/last |
| Gate.io Futures | reachable | `gate` | `BTC/USDT:USDT` | valid bid/ask/last |
| Hyperliquid | reachable | `hyperliquid` | `BTC/USDC:USDC` | valid bid/ask/derived reference |
| Coinbase International | reachable | `coinbaseinternational` | `BTC/USDC:USDC` | valid bid/ask/derived reference |
| Crypto.com Exchange | reachable | `cryptocom` | `BTC/USD:USD` | valid bid/ask/last |
| MEXC | reachable | `mexc` | `BTC/USDT:USDT` | valid bid/ask/last |
| HTX | reachable | `htx` | `BTC/USDT:USDT` | valid bid/ask/last |
| Phemex | reachable | `phemex` | `BTC/USDT:USDT` | valid bid/ask/last |
| WOO X | reachable | `woo` | `BTC/USDT:USDT` | order-book-derived reference |
| BingX | reachable | `bingx` | `BTC/USDT:USDT` | valid bid/ask/last |
| dYdX | reachable | `dydx` | `BTC/USDC:USDC` | order-book-derived reference |

For all 16 reached companies, a positive BTC derivative reference price was obtained. Where bid and ask were present, the observed spread ordering was valid. The test also recorded contract metadata, CCXT capability maps, market counts, funding data where supported, selected symbols, timestamps, order-book depth, and per-call failures.

## Scenario/result classification

| Area | Classification |
|---|---|
| Installation and imports | **PASS** |
| Existing unit tests | **PASS WITH LIMITED UNIQUE COVERAGE** |
| Randomized order repetition | **PASS** |
| Database initialization and health | **PASS** |
| Broker catalog and factory registration | **PASS** |
| Sentinel Archive compatibility | **PASS** |
| Public crypto derivatives market data | **PARTIAL PASS — 16 OF 18** |
| Listed-futures live market data | **NOT TESTED — REQUIRES BROKER DATA CONNECTION** |
| Authenticated order submission | **NOT TESTED** |
| Cancel/replace and partial fills at broker | **NOT TESTED** |
| Broker margin and position reconciliation | **NOT TESTED** |
| Funded market readiness | **NOT CERTIFIED** |

## What this campaign did not test

- Authenticated brokerage login and session renewal
- Real order acceptance and broker order-ID assignment
- Cancellation acknowledgement and cancel/fill races at a live broker
- Partial fills and execution-ID replay from a live broker
- Broker-calculated margin, maintenance margin, and liquidation data
- Position and working-order reconciliation against an account
- Connection loss and restart recovery with live working orders
- Emergency flatten against an authenticated account
- Listed-futures market data through an entitled broker connection
- Funded trading and unrestricted live capital

## Readiness conclusion

### Supported conclusion

Combination is installable, deterministic under the current tests, persistent across repeated clean database cycles, compatible with Sentinel Archive as an external evidence/replay system, and capable of consuming public live data from most cataloged crypto-derivatives venues.

### Unsupported conclusion

The evidence does **not** establish that Combination can safely control a brokerage account in production. No authenticated order was submitted; no real broker acknowledgement, cancellation, fill, partial fill, margin response, position reconciliation, disconnect recovery, or emergency flatten was observed.

### Current deployment judgment

**Do not use unrestricted funded capital.** The next valid certification stage is credentialed broker-specific lifecycle testing with strict account permissions and capital limits. Each adapter needs its own recorded evidence for authentication, market-data entitlement, order acceptance, rejection, partial fill, cancellation, reconciliation, restart, and emergency controls.
