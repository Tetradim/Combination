# Feature Matrix

The complete implementations are included through pinned submodules. “Available” means the source feature is present and can be exercised through its native package. “Unified” means Combination currently exposes a cross-project facade for it.

## Summary

| Capability family | Chain | Iron | Combination status |
|---|---:|---:|---|
| Crypto webhook/text/Discord signal intake | Available | — | Chain-native |
| Synthetic staged bracket management | Available | — | Chain-native |
| Trailing, break-even, profit-lock, time exits | Available | — | Chain-native |
| Scenario previews and bracket backtests | Available | — | Chain-native |
| Browser operator UI | Available | — | Chain-native launcher |
| Listed-futures instrument and expiry model | — | Available | Iron-native |
| Broker ports and adapter boundaries | Preview-only crypto discovery | Available | Iron-native |
| Readiness, activation, and reconciliation gates | Partial/paper workflow | Available | Iron-native |
| Broker fill and lifecycle truth | — | Available | Iron-native |
| Margin previews and approved schedules | — | Available | Iron-native |
| Portfolio targets and phased rebalances | — | Available | Iron-native |
| Kill switch, cancel sweep, emergency flatten | Workflow halt | Available | Iron-native |
| Shared capability inventory | — | — | Unified |
| Pin validation and unified launcher | — | — | Unified |
| Cross-asset experiment envelope | — | — | Scaffolded |
| Autonomous cross-bot live routing | — | — | Intentionally absent |

## Sentinel Chain capabilities present

- TradingView/custom JSON webhooks.
- Strict and flexible text alert parsing.
- Discord-style command integration.
- Alias-rich symbol, side, bracket, target, trailing, and close-size normalization.
- Restart-safe signal idempotency.
- Quote, base, risk-amount, and equity-percent sizing.
- Stop requirement and maximum stop-width checks.
- First-target and total staged reward/risk checks.
- Order, symbol, portfolio notional, and aggregate open-risk controls.
- Volatility, leverage, slippage, allowed venue, blocked symbol, daily loss, and consecutive-loss checks.
- Approval queues and audit persistence.
- Paper long/short lots and reversal netting.
- Fixed stop loss and single or staged take profit.
- Partial take-profit and partial trailing reductions.
- Percentage and fixed-distance trailing stops.
- Activation-gated and take-profit-gated trailing stops.
- Minimum trailing ratchet steps.
- Price-triggered and post-target break-even.
- Post-target profit locks.
- Mark-count time exits.
- OCA-style group and sibling cancellation tracking.
- Tighten-only stop/trailing amendments and farther-only target amendments.
- Manual bracket reduction, close-at-mark, close-at-protective-trigger, and exit cancellation.
- Bracket coverage, exit ladder, OCA, trigger distance, and decision-support diagnostics.
- Non-mutating mark, multi-mark, candle-path, and trailing-ratchet previews.
- Mark and OHLC backtests with adverse/favorable sequencing.
- MFE, MAE, fee, slippage, funding, drawdown, runup, win rate, and profit-factor reporting.
- Bitunix futures kline retrieval.
- CCXT venue discovery and non-executing order-plan classification.
- FastAPI service and browser operator interface.

## Sentinel Iron capabilities present

### Safety and readiness

- Persistent kill switch with mandatory operator reason.
- Kill-switch cancel sweep for known working and partially filled orders.
- Paper/live broker environment validation.
- Exact live activation-token requirement before broker handoff.
- Broker connectivity, account, and position retrieval.
- Trading-readiness checks for connection, account freshness, and reconciliation.
- Fail-closed behavior when kill-switch state, readiness, or margin information is unavailable.
- Operator-confirmed emergency flatten path separated from strategy entry.

### Market data and futures domain

- Normalized quote snapshots and instrument mismatch rejection.
- Historical daily-bar retrieval, validation, sorting, and duplicate rejection.
- Deterministic historical-bar persistence.
- Futures instrument catalog with multiplier, tick size, settlement, exchange, contract month, first notice, last trade, and last safe trade date.
- Delivery-date-aware flat targets.
- Back-adjusted continuous series with overlap validation.

### Risk and margin

- Kill-switch and reconciliation checks.
- Stale account and market-data checks.
- Instrument and quote validation.
- Crossed/two-sided quote and spread checks.
- Order-rate, position, and notional limits.
- Initial/maintenance margin and buying-power checks.
- Daily-loss and last-safe-trade-date checks.
- Duplicate client-order-ID checks.
- Tick-size and price-collar checks.
- Broker/API margin estimate service.
- Expiring operator-supplied margin schedules.
- Validated margin-schedule persistence.
- IBKR what-if margin preview.
- TradeStation v3 confirmation margin preview.
- NinjaTrader and Optimus fail-closed margin boundaries when verified previews are unavailable.

### Orders, fills, and lifecycle

- Audited risk-first order submission.
- Explicit synchronous broker-rejection lifecycle.
- Persistent accepted-order activity.
- Duplicate client-order-ID protection and order-rate inputs.
- Persistent latest lifecycle state.
- Validated pending-cancel transitions and broker cancel requests.
- Acknowledgement, incremental fill, cumulative fill, cancellation, and asynchronous-reject updates.
- Broker order-ID and instrument consistency checks.
- Fill-driven signed position ledger.
- Weighted-average additions, reductions without average reset, and side-flip handling.
- Processed execution-ID idempotency across restarts.
- Internal-versus-broker position reconciliation.
- Append-only JSONL audit events.

### Portfolio and strategy infrastructure

- Current-position-to-target order planning.
- Batch target planning with duplicate/missing input rejection.
- Risk-reducing orders before exposure-increasing orders.
- Separate flatten/open phases for reversals.
- Persisted rebalance phase coordination.
- Phase submission requiring a complete risk context for every order.
- Per-order rebalance risk-context construction.
- Volatility-scaled target contracts.
- Per-instrument sizing limits and portfolio gross-risk cap.
- Volatility-normalized multi-lookback trend signal.
- Weighted trend/carry composite signal.

### Broker boundaries

- Interactive Brokers.
- TradeStation.
- NinjaTrader.
- Optimus.

## Combination-native features

- Exact commit pins for both complete repositories.
- Unified `combination` CLI.
- Submodule and import health checks.
- Source pin report.
- Machine-readable capability registry.
- Subprocess-isolated Chain and Iron delegation.
- Neutral crypto/listed-futures instrument references.
- Shadow, paper, and live-gated experiment modes.
- Explicit readiness snapshot that cannot report live readiness with a missing gate.
- Root and component test orchestration.

## Not yet unified

The following are intentionally not connected automatically:

- Chain signal directly to Iron broker submission.
- Chain synthetic exit directly to an Iron cancel/replace request.
- Iron broker fill directly into Chain's paper lot ledger.
- One shared database for both packages.
- One shared kill switch that mutates both source stores.
- Autonomous live cross-bot execution.

Those connections require explicit protocol design, lifecycle mapping, replay fixtures, and operator acceptance criteria.
