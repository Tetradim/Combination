# Sentinel Combination Comprehensive Validation Report

**Generated:** 2026-07-17

## Executive judgment

**The current repository passes its existing code-level tests, repeated-state tests, database integrity checks, Sentinel Archive compatibility checks, and most public crypto-derivatives market-data checks. It is not certified for funded trading.**

The strongest engineering evidence is repeatability across Python 3.11–3.13, randomized test ordering, 30 database restart cycles, 100 import cycles, two normal CI runs, two historical replay workflow runs, and read-only market discovery from 15 of 18 crypto-derivatives companies.

The strongest negative finding is coverage depth: the current Combination repository contains only **12 unique automated tests**. Repeating those tests many times is useful for determinism, but it does not substitute for broker-specific tests of authentication, order acknowledgement, rejection, partial fills, cancellation, margin, reconciliation, disconnect recovery, or emergency flattening.

The Sentinel Archive one-month matrix also did **not** demonstrate a robust trading edge. Across 648 settings, 89 were positive and 559 were negative in Archive's normalized spot-style model. These are harness and strategy diagnostics, not futures-contract profitability results.

## Exact provenance

- Main commit exercised by exhaustive and public validation: `ba08534b42ff16409fb0fc7a0b753a1bb1a3db54`
- Validation-only PR head: `a45f0d6524448bb32e6d26effc4c762d04a50c5b`
- Synthetic PR merge commit exercised by the historical workflow: `45e350fd44024965f2ef8f367bc06d6bc605c2ca`
- Sentinel Archive commit: `44aa4337cfb15aeb562a874b8dbc3fa799149f18`
- Validation PR: `#4` — draft, validation-only, never merged

Workflow runs:

- Standard CI initial: `29545599860`
- Archive historical initial: `29545599861`
- Standard CI repeat: `29545734396`
- Archive historical repeat: `29545734425`
- Expanded public derivatives: `29545734415`
- Exhaustive validation: `29545734461`

## How the evidence was acquired

1. GitHub Actions used clean Ubuntu runners and installed the repository's complete declared broker dependency surface.
2. Source and tests were compiled and executed on Python 3.11, 3.12, and 3.13.
3. The complete Combination suite was rerun under five randomized orders and hash seeds per Python version and twenty additional stress seeds.
4. Thirty independent SQLite databases were initialized and diagnosed twice to test repeatable startup and restart behavior.
5. The package and broker catalog were imported one hundred times.
6. Sentinel Archive was checked out independently, its 98-test suite was run, its FastAPI application was imported, and replay and data contracts were exercised.
7. Historical hourly data was acquired at runtime through Yahoo Finance and yfinance for ES, NQ, CL, GC, BTC, and ETH.
8. Archive evaluated 108 stop, target, trailing, slippage, and commission combinations per symbol, yielding 648 cases.
9. Public derivatives checks used unauthenticated CCXT market discovery, ticker, order-book, and funding endpoints only.
10. No credential, account, position, order-submission, or cancellation method was invoked in public-data workflows.

## Combination code-level results

| Check | Result |
|---|---:|
| Unique Combination tests | 12 |
| Python versions | 3.11, 3.12, 3.13 |
| Exhaustive full-suite runs | 38 |
| Test invocations in exhaustive workflow | 456 |
| Normal CI runs | 2 passed |
| Historical-workflow Combination runs | 2 passed |
| Randomized stress suite failures | 0 / 20 |
| Database failures | 0 / 30 |
| Import failures | 0 / 100 |
| Dependency consistency | `pip check` passed |

### Current unique test inventory

| File | Tests |
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

Notably absent from the current automated inventory are direct tests for authenticated broker sessions, adapter order submission, broker cancellation, live partial fills, margin responses, reconciliation against an account, disconnect recovery, emergency flattening, and listed-futures entitlement behavior.

## Persistence results

- Thirty database init, doctor, and restart cycles passed.
- `PRAGMA integrity_check` returned `ok` on inspected evidence databases.
- Journal mode was `wal`.
- Synchronous mode was `2` (`FULL`).
- Ten application tables were present: brackets, events, kill switch, metadata, orders, positions, processed executions, processed external events, reconciliations, and SQLite sequence.
- A separately opened inspection connection reported `foreign_keys=0`. SQLite foreign-key enforcement is connection-local, so this remains an explicit source-code and runtime audit item rather than a proven schema failure.

## Broker catalog and adapter registry

- Cataloged companies: **44**
- Listed-futures companies: **26**
- Crypto-futures companies: **18**
- Registered executable factory keys: **24**
- Duplicate broker IDs: **0**
- Blank broker IDs: **0**

Many listed-futures catalog entries do not yet have a direct transport factory. Being present in the catalog is not equivalent to having a tested executable broker integration.

## Sentinel Archive deterministic scenarios

Passed **6/6** scenarios:

- take-profit exit;
- regular-stop exit;
- trailing-stop activation and exit;
- tightened trailing-stop exit;
- partial-fill and idempotency handling;
- emergency exit.

These scenarios run in Sentinel Archive's external replay and simulation environment. They do not add a paper engine to Combination and do not prove live broker behavior.

## One-month historical matrix

Hourly data window: 2026-06-17 through 2026-07-17.

| Symbol | Bars | Cases | Positive | Mean return % | Median return % | Min % | Max % |
|---|---:|---:|---:|---:|---:|---:|---:|
| BTC-USD | 719 | 108 | 13 | -1.4987 | -1.3592 | -3.9468 | 0.4147 |
| CL=F | 473 | 108 | 30 | -0.3456 | -0.5798 | -2.4955 | 2.3013 |
| ES=F | 473 | 108 | 11 | -0.2044 | -0.1589 | -0.5974 | 0.1055 |
| ETH-USD | 719 | 108 | 9 | -1.8350 | -1.6432 | -4.3352 | 0.0626 |
| GC=F | 473 | 108 | 0 | -0.9471 | -0.8952 | -2.0802 | -0.1192 |
| NQ=F | 473 | 108 | 26 | -0.3139 | -0.3449 | -0.9984 | 0.3340 |

Overall: **89 positive / 648 cases (13.73%)**; mean `-0.8574%`, median `-0.6348%`, range `-4.3352%` to `2.3013%`.

### Cost sensitivity

| Slippage bps | Commission | Positive / cases | Mean return % | Median return % | Max % |
|---:|---:|---:|---:|---:|---:|
| 0.0 | 0.00 | 44 / 162 | -0.2669 | -0.2714 | 2.3013 |
| 0.0 | 2.50 | 22 / 162 | -0.6703 | -0.5898 | 1.4513 |
| 5.0 | 0.00 | 18 / 162 | -1.0433 | -0.7618 | 0.6432 |
| 5.0 | 2.50 | 5 / 162 | -1.4493 | -0.9832 | 0.0831 |

Under the most expensive tested assumption, 5 bps slippage plus a $2.50 commission, only 5 of 162 settings were positive. The best per-symbol results under that assumption were:

| Symbol | Best return % | Stop | Target | Trail | Trades | Max DD % |
|---|---:|---:|---:|---:|---:|---:|
| NQ=F | 0.0831 | 1.0 | 4.0 | 2.0 | 12 | 0.3661 |
| BTC-USD | -0.0789 | 2.0 | 4.0 | 2.0 | 26 | 0.8097 |
| ES=F | -0.1474 | 2.0 | 2.0 | 2.0 | 11 | 0.2574 |
| CL=F | -0.2068 | 1.0 | 1.0 | 0.5 | 170 | 1.1614 |
| GC=F | -0.3150 | 2.0 | 4.0 | 2.0 | 10 | 0.4391 |
| ETH-USD | -1.0779 | 2.0 | 2.0 | 2.0 | 48 | 1.3940 |

### Historical-test interpretation

- The campaign used an 8-bar and 24-bar moving-average signal and Archive's long-only spot-style accounting.
- It did not apply listed-futures multipliers, margin, funding, queue position, broker fills, or exact contract rolls.
- Archive evaluates threshold priority from OHLC bars; simultaneous intrabar trigger ordering is assumed rather than observed.
- Parameter selection and evaluation used the same month, producing in-sample selection bias.
- The matrix is evidence about replay behavior and cost sensitivity, not proof that Combination has a profitable strategy.

## Public crypto-derivatives market data

CCXT `4.5.66` reached **15/18** cataloged crypto-derivatives companies.

Reached:

- OKX
- Bitget
- KuCoin Futures
- Kraken Futures
- Deribit
- BitMEX
- Gate.io Futures
- Hyperliquid
- Coinbase International Exchange
- Crypto.com Exchange
- MEXC
- HTX
- Phemex
- BingX
- dYdX

Blocked from the GitHub runner:

- Binance Futures — HTTP 451 regional restriction;
- Bybit — CloudFront HTTP 403 regional restriction;
- WOO X — HTTP 403.

For every reached venue, the runner obtained a positive BTC derivative reference price. Where both bid and ask were available, spread ordering was valid. Market metadata, contract size, precision, limits, funding data where supported, timestamps, and order-book depth were recorded in the JSON artifact.

These results show public market-data accessibility and normalization. They do not show successful authenticated adapter behavior.

## Readiness classification

| Area | Classification |
|---|---|
| Installation, compilation, imports | PASS |
| Existing core unit tests | PASS WITH LIMITED UNIQUE COVERAGE |
| Randomized repetition | PASS |
| Database initialization and restart | PASS |
| Broker catalog and factory registry | PASS |
| Sentinel Archive external replay compatibility | PASS |
| Historical replay matrix | PASS AS DIAGNOSTIC; NO ROBUST EDGE SHOWN |
| Public crypto-derivatives market data | PARTIAL PASS — 15 OF 18 |
| Listed-futures entitled live data | NOT TESTED |
| Authenticated order submission | NOT TESTED |
| Broker cancellation and partial fills | NOT TESTED |
| Broker margin and reconciliation | NOT TESTED |
| Disconnect and restart with working orders | NOT TESTED |
| Emergency flatten against a brokerage account | NOT TESTED |
| Funded trading | NOT CERTIFIED |

## Final judgment

Combination is stable under the tests it currently has and is suitable for the next stage of credentialed broker integration testing. It should not control unrestricted funded capital yet.

Before market use, each intended broker adapter needs recorded evidence for authentication, contract discovery, entitled market data, order acceptance, controlled rejection, partial fill, duplicate execution handling, cancellation, cancel and fill races, margin, position and order reconciliation, restart recovery, protective-order persistence, and emergency flattening.

## Raw evidence and checksums

- Historical Archive artifact digest: `sha256:76ef741df8105e9572b4771213354971d5813ef4d12bcd80974803bb55803755`
- Expanded public market artifact digest: `sha256:6ff755ebedeb2e3a7c3312a1474f125e1d909a9f0cd9980cd8a2458fe041d0b3`
- Exhaustive Archive and live artifact digest: `sha256:9dd9cc25f0f2c5b0981f1f6a3255f6126feca397300e4c0aa799762ad6995f3b`
- Stress artifact digest: `sha256:91df2d66740e2dbb1a9651bcfa0bb2436addb18309235c0e79e55406b297d8df`
- Python 3.11 artifact digest: `sha256:4f72992b1eab637e81c8476f3613801448252077b3e68dbda41a45b6c2a9b357`
- Python 3.12 artifact digest: `sha256:b650f7d436268747cf23c9d66ed1c6fe76dee6b8ef83aa31ba47a11a0b156a0b`
- Python 3.13 artifact digest: `sha256:1b1db7a277707d381669a629aa0a156d73b959abcc9542bd4ced807b8fedaf7f`
