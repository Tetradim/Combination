# Sentinel Combination / Sentinel Archive Validation Report

Generated: `2026-07-17T00:48:03.843387+00:00`

## Scope and interpretation

This campaign uses Sentinel Archive as an external deterministic replay harness. It does not place broker orders and it does not certify real-money profitability. The one-month profitability matrix is a normalized spot-style experiment using Archive's account model; it does not apply listed-futures contract multipliers, exchange margin, funding, queue position, or broker fills.

## Deterministic automation scenarios

Passed **6/6** scenarios.

| Scenario | Result | Expected evidence | Observed actions |
|---|---:|---|---|
| take_profit_exit | PASS | take_profit_sell | take_profit_sell, buy |
| regular_stop_exit | PASS | regular_stop_sell | regular_stop_sell, buy |
| trailing_stop_activation_and_exit | PASS | trailing_stop_sell | trailing_stop_sell, trailing_stop, buy |
| tightened_trailing_stop_exit | PASS | trailing_stop_sell | trailing_stop_sell, tighten_trailing_stop, trailing_stop, buy |
| partial_fill_and_idempotency | PASS |  |  |
| emergency_exit | PASS |  | emergency_exit, buy |

## Historical data

| Symbol | Provider | Bars | First | Last |
|---|---|---:|---|---|
| ES=F | Yahoo Finance via yfinance | 473 | 2026-06-17T00:00:00+00:00 | 2026-07-17T00:00:00+00:00 |
| NQ=F | Yahoo Finance via yfinance | 473 | 2026-06-17T00:00:00+00:00 | 2026-07-17T00:00:00+00:00 |
| CL=F | Yahoo Finance via yfinance | 473 | 2026-06-17T00:00:00+00:00 | 2026-07-17T00:00:00+00:00 |
| GC=F | Yahoo Finance via yfinance | 473 | 2026-06-17T00:00:00+00:00 | 2026-07-17T00:00:00+00:00 |
| BTC-USD | Yahoo Finance via yfinance | 719 | 2026-06-17T00:00:00+00:00 | 2026-07-17T00:00:00+00:00 |
| ETH-USD | Yahoo Finance via yfinance | 719 | 2026-06-17T00:00:00+00:00 | 2026-07-17T00:00:00+00:00 |

## Best normalized one-month matrix results

| Rank | Symbol | Stop % | Target % | Trail % | Slip bps | Commission | Return % | Trades | Win % | Max DD % | Exits |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | CL=F | 0.50 | 1.00 | 0.50 | 0.0 | 0.00 | 2.3013 | 170 | 49.41 | 0.4132 | {"trailing_stop_sell": 170} |
| 2 | CL=F | 0.50 | 2.00 | 0.50 | 0.0 | 0.00 | 2.3013 | 170 | 49.41 | 0.4132 | {"trailing_stop_sell": 170} |
| 3 | CL=F | 0.50 | 4.00 | 0.50 | 0.0 | 0.00 | 2.3013 | 170 | 49.41 | 0.4132 | {"trailing_stop_sell": 170} |
| 4 | CL=F | 1.00 | 1.00 | 0.50 | 0.0 | 0.00 | 2.3013 | 170 | 49.41 | 0.4132 | {"trailing_stop_sell": 170} |
| 5 | CL=F | 1.00 | 2.00 | 0.50 | 0.0 | 0.00 | 2.3013 | 170 | 49.41 | 0.4132 | {"trailing_stop_sell": 170} |
| 6 | CL=F | 1.00 | 4.00 | 0.50 | 0.0 | 0.00 | 2.3013 | 170 | 49.41 | 0.4132 | {"trailing_stop_sell": 170} |
| 7 | CL=F | 2.00 | 1.00 | 0.50 | 0.0 | 0.00 | 2.3013 | 170 | 49.41 | 0.4132 | {"trailing_stop_sell": 170} |
| 8 | CL=F | 2.00 | 2.00 | 0.50 | 0.0 | 0.00 | 2.3013 | 170 | 49.41 | 0.4132 | {"trailing_stop_sell": 170} |
| 9 | CL=F | 2.00 | 4.00 | 0.50 | 0.0 | 0.00 | 2.3013 | 170 | 49.41 | 0.4132 | {"trailing_stop_sell": 170} |
| 10 | CL=F | 0.50 | 1.00 | 0.50 | 0.0 | 2.50 | 1.4513 | 170 | 49.41 | 0.6031 | {"trailing_stop_sell": 170} |
| 11 | CL=F | 0.50 | 2.00 | 0.50 | 0.0 | 2.50 | 1.4513 | 170 | 49.41 | 0.6031 | {"trailing_stop_sell": 170} |
| 12 | CL=F | 0.50 | 4.00 | 0.50 | 0.0 | 2.50 | 1.4513 | 170 | 49.41 | 0.6031 | {"trailing_stop_sell": 170} |
| 13 | CL=F | 1.00 | 1.00 | 0.50 | 0.0 | 2.50 | 1.4513 | 170 | 49.41 | 0.6031 | {"trailing_stop_sell": 170} |
| 14 | CL=F | 1.00 | 2.00 | 0.50 | 0.0 | 2.50 | 1.4513 | 170 | 49.41 | 0.6031 | {"trailing_stop_sell": 170} |
| 15 | CL=F | 1.00 | 4.00 | 0.50 | 0.0 | 2.50 | 1.4513 | 170 | 49.41 | 0.6031 | {"trailing_stop_sell": 170} |
| 16 | CL=F | 2.00 | 1.00 | 0.50 | 0.0 | 2.50 | 1.4513 | 170 | 49.41 | 0.6031 | {"trailing_stop_sell": 170} |
| 17 | CL=F | 2.00 | 2.00 | 0.50 | 0.0 | 2.50 | 1.4513 | 170 | 49.41 | 0.6031 | {"trailing_stop_sell": 170} |
| 18 | CL=F | 2.00 | 4.00 | 0.50 | 0.0 | 2.50 | 1.4513 | 170 | 49.41 | 0.6031 | {"trailing_stop_sell": 170} |
| 19 | CL=F | 1.00 | 1.00 | 0.50 | 5.0 | 0.00 | 0.6432 | 170 | 41.18 | 0.8581 | {"trailing_stop_sell": 170} |
| 20 | CL=F | 1.00 | 2.00 | 0.50 | 5.0 | 0.00 | 0.6432 | 170 | 41.18 | 0.8581 | {"trailing_stop_sell": 170} |
| 21 | CL=F | 1.00 | 4.00 | 0.50 | 5.0 | 0.00 | 0.6432 | 170 | 41.18 | 0.8581 | {"trailing_stop_sell": 170} |
| 22 | CL=F | 2.00 | 1.00 | 0.50 | 5.0 | 0.00 | 0.6432 | 170 | 41.18 | 0.8581 | {"trailing_stop_sell": 170} |
| 23 | CL=F | 2.00 | 2.00 | 0.50 | 5.0 | 0.00 | 0.6432 | 170 | 41.18 | 0.8581 | {"trailing_stop_sell": 170} |
| 24 | CL=F | 2.00 | 4.00 | 0.50 | 5.0 | 0.00 | 0.6432 | 170 | 41.18 | 0.8581 | {"trailing_stop_sell": 170} |
| 25 | CL=F | 0.50 | 1.00 | 0.50 | 5.0 | 0.00 | 0.6241 | 170 | 40.59 | 0.8771 | {"regular_stop_sell": 1, "trailing_stop_sell": 169} |

## Acquisition and reproduction

- Historical bars were requested at runtime through `yfinance` with `period=1mo` and `interval=1h`.
- Synthetic scenarios use explicit OHLC bars stored in the campaign script so target, stop, trailing activation, tightening, duplicate handoff, partial-fill, and emergency-exit behavior are reproducible.
- The market strategy is deliberately transparent: 8-bar/24-bar moving-average entry and exit, with Archive stop, target, and trailing policies applied on subsequent bars.
- All raw market rows, scenario records, parameter results, trade logs, and equity curves are included in the workflow artifact.

## Known limitations discovered by design inspection

1. Archive evaluates trailing stop before regular stop and take profit inside each OHLC bar; when multiple thresholds are crossed in one bar, this priority is an assumption rather than known tick ordering.
2. Archive is long-only and uses spot-style cash accounting. Its profitability values cannot be treated as futures-contract P&L.
3. Public Yahoo data may be delayed, adjusted, incomplete, or use a continuous/front-month representation that differs from the exact contract a broker would route.
4. No brokerage order acknowledgement, partial broker fill, cancellation, margin preview, or reconciliation is exercised by this campaign.
5. Optimizing parameters on the same month used for evaluation is in-sample and creates selection bias. The ranked table is diagnostic, not evidence of a durable edge.
