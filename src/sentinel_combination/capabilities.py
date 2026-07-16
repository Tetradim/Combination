from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class Capability:
    capability_id: str
    owner: str
    category: str
    maturity: str
    summary: str
    provenance: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


_ROWS = (
    # Sentinel Chain: strategy, bracket, simulation, and operator surface.
    ("chain.signal.normalization", "chain", "signal", "operational", "JSON, TradingView, text, Discord-style, alias-rich crypto signal normalization.", "sentinel_chain.signals / text_signals"),
    ("chain.signal.idempotency", "chain", "signal", "operational", "Restart-safe duplicate signal rejection.", "Sentinel Chain persistence"),
    ("chain.risk.pretrade", "chain", "risk", "operational", "Stop, reward/risk, target-count, notional, concentration, volatility, leverage, slippage, loss, and aggregate open-risk controls.", "sentinel_chain.risk"),
    ("chain.sizing.fixed_fraction", "chain", "risk", "operational", "Risk amount or equity-percent sizing from stop distance.", "sentinel_chain.risk"),
    ("chain.bracket.synthetic", "chain", "bracket", "operational", "Long/short synthetic stop, staged targets, OCA grouping, and partial close management.", "sentinel_chain.execution / brackets"),
    ("chain.bracket.trailing", "chain", "bracket", "operational", "Percent or amount trailing, activation gates, delayed activation, stepped ratchets, and partial trailing exits.", "sentinel_chain.execution"),
    ("chain.bracket.protection", "chain", "bracket", "operational", "Break-even, post-target break-even, profit locks, and tighten-only amendments.", "sentinel_chain.execution"),
    ("chain.bracket.time_exit", "chain", "bracket", "operational", "Paper mark-count time exits.", "sentinel_chain.execution"),
    ("chain.execution.paper", "chain", "execution", "operational", "Paper lots, reversal netting, fee/slippage accounting, PnL, and restart replay.", "sentinel_chain.execution"),
    ("chain.preview.scenario", "chain", "research", "operational", "Non-mutating mark, path, candle, trailing-ratchet, ladder, coverage, and OCA diagnostics.", "Sentinel Chain API"),
    ("chain.backtest.bracket", "chain", "research", "operational", "Mark/OHLC bracket backtests with MFE/MAE, fees, slippage, funding, drawdown, and performance metrics.", "Sentinel Chain backtests"),
    ("chain.market.bitunix", "chain", "market_data", "operational", "Bitunix futures kline adapter.", "Sentinel Chain market data"),
    ("chain.exchange.discovery", "chain", "exchange", "preview_only", "CCXT venue discovery, capability inspection, and non-executing bracket plan classification.", "sentinel_chain.exchanges"),
    ("chain.operator.api_ui", "chain", "operator", "operational", "FastAPI endpoints and browser operator UI for signals, risk, approvals, positions, brackets, audit, and exports.", "sentinel_chain.app / static"),
    ("chain.discord.client", "chain", "operator", "operational", "Minimal Discord slash-command client.", "Sentinel Chain Discord integration"),

    # Sentinel Iron: execution, futures domain, broker truth, and portfolio infrastructure.
    ("iron.safety.kill_switch", "iron", "safety", "operational", "Persistent operator kill switch with required reason and immutable audit events.", "sentinel_iron.application.kill_switch"),
    ("iron.safety.cancel_sweep", "iron", "safety", "operational", "Kill-switch enforcement sweep cancels known working and partially filled broker orders.", "sentinel_iron.application.kill_switch_enforcement"),
    ("iron.broker.connection", "iron", "broker", "operational", "Paper/live broker connection, account and position retrieval, and audited failures.", "sentinel_iron.application.broker_connection"),
    ("iron.readiness.trading", "iron", "safety", "operational", "Blocks disconnected, stale-account, missing-account, and unreconciled trading.", "sentinel_iron.application.trading_readiness"),
    ("iron.market.snapshot", "iron", "market_data", "operational", "Validated live quote snapshots with instrument mismatch rejection and audit.", "sentinel_iron.application.market_data"),
    ("iron.market.history", "iron", "market_data", "operational", "Validated inclusive historical daily bars with duplicate and range rejection.", "sentinel_iron.application.market_data"),
    ("iron.market.history_store", "iron", "storage", "operational", "Deterministic JSON historical bar cache.", "sentinel_iron.storage.historical_bars"),
    ("iron.gateway.live_activation", "iron", "safety", "operational", "Exact activation-token gate before any live broker handoff.", "sentinel_iron.application.order_gateway"),
    ("iron.gateway.readiness", "iron", "execution", "operational", "Fail-closed order gateway checks kill switch and readiness before risk or submission.", "sentinel_iron.application.order_gateway"),
    ("iron.reconciliation.positions", "iron", "reconciliation", "operational", "Internal-versus-broker position reconciliation blocks readiness on differences.", "sentinel_iron.application.reconciliation"),
    ("iron.ledger.positions", "iron", "accounting", "operational", "Fill-driven signed position accounting, weighted averages, reductions, and reversals.", "sentinel_iron.application.position_ledger"),
    ("iron.ledger.fill_idempotency", "iron", "accounting", "operational", "Broker execution IDs prevent duplicate fill mutation across restarts.", "sentinel_iron.storage.processed_fills"),
    ("iron.orders.activity", "iron", "lifecycle", "operational", "Accepted-order activity, original side/quantity, duplicate client-ID prevention, and rate inputs.", "sentinel_iron.application.order_activity"),
    ("iron.orders.activity_store", "iron", "storage", "operational", "Restart-safe JSONL accepted-order activity.", "sentinel_iron.storage.order_activity"),
    ("iron.orders.lifecycle_store", "iron", "storage", "operational", "Restart-safe latest broker order lifecycle state.", "sentinel_iron.storage.order_lifecycles"),
    ("iron.planning.targets", "iron", "planning", "operational", "Current-to-target order planning with risk-reducing orders first.", "sentinel_iron.application.order_planning"),
    ("iron.planning.reversal_phases", "iron", "planning", "operational", "Long/short reversals split into fill-confirmed flatten and open phases.", "sentinel_iron.application.order_planning"),
    ("iron.portfolio.strategy_targets", "iron", "portfolio", "operational", "Trend, carry, and composite signals become volatility-sized, gross-risk-capped contract targets.", "sentinel_iron.application.strategy_targets"),
    ("iron.futures.expiry_guard", "iron", "futures", "operational", "Contracts past last-safe-trade date are forced to flat targets.", "sentinel_iron.application.strategy_targets"),
    ("iron.futures.continuous", "iron", "futures", "operational", "Back-adjusted continuous histories reject missing roll overlap.", "sentinel_iron.market.continuous"),
    ("iron.rebalance.coordinator", "iron", "execution", "operational", "Persisted phased rebalance coordinator waits for fills and blocks after cancel/reject.", "sentinel_iron.application.rebalance_execution"),
    ("iron.rebalance.submission", "iron", "execution", "operational", "Risk-context-required phase submission stops after the first gateway rejection.", "sentinel_iron.application.rebalance_phase_submission"),
    ("iron.rebalance.risk_context", "iron", "risk", "operational", "Builds validated per-order risk contexts for rebalance intents.", "sentinel_iron.application.rebalance_risk_context"),
    ("iron.margin.estimates", "iron", "margin", "operational", "Broker/API-derived initial and maintenance margin estimates; never invents fallback values.", "sentinel_iron.application.margin_estimates"),
    ("iron.margin.schedules", "iron", "margin", "operational", "Approved expiring FCM/exchange margin schedules for routes without previews.", "sentinel_iron.application.margin_schedules"),
    ("iron.margin.schedule_store", "iron", "storage", "operational", "Validated JSON margin schedule persistence.", "sentinel_iron.storage.margin_schedules"),
    ("iron.instruments.catalog", "iron", "futures", "operational", "Multiplier, tick, settlement, exchange, month, notice, last-trade, and last-safe dates.", "sentinel_iron.storage.instruments"),
    ("iron.adapter.ibkr", "iron", "broker", "boundary", "IBKR broker adapter and what-if margin preview.", "Sentinel Iron IBKR adapter"),
    ("iron.adapter.tradestation", "iron", "broker", "boundary", "TradeStation v3 order confirmation and margin preview.", "Sentinel Iron TradeStation adapter"),
    ("iron.adapter.ninjatrader", "iron", "broker", "boundary", "NinjaTrader adapter boundary with fail-closed margin preview behavior.", "Sentinel Iron NinjaTrader adapter"),
    ("iron.adapter.optimus", "iron", "broker", "boundary", "Optimus route boundary with fail-closed margin preview behavior.", "Sentinel Iron Optimus adapter"),
    ("iron.orders.submission", "iron", "execution", "operational", "Audited risk-first broker submission with persisted working/rejected lifecycle.", "sentinel_iron.application.order_submission"),
    ("iron.orders.sync_rejection", "iron", "execution", "operational", "Synchronous broker rejects become explicit rejected lifecycle states.", "sentinel_iron.ports.broker"),
    ("iron.orders.cancellation", "iron", "execution", "operational", "Validated pending-cancel transition, broker cancel request, persistence, and audit.", "sentinel_iron.application.order_cancellation"),
    ("iron.safety.emergency_flatten", "iron", "safety", "operator_confirmed", "Broker-authoritative emergency flatten separate from strategy entry.", "sentinel_iron.application.position_flattening"),
    ("iron.orders.stream_updates", "iron", "lifecycle", "operational", "Acknowledgement, fill, cancellation, and async reject processing with broker-ID validation.", "sentinel_iron.application.order_updates"),
    ("iron.audit.immutable_jsonl", "iron", "audit", "operational", "Append-only JSONL audit snapshots.", "sentinel_iron.storage.audit"),
    ("iron.risk.pretrade", "iron", "risk", "operational", "Kill switch, reconciliation, freshness, quote, spread, rate, position, notional, margin, PnL, date, duplicate-ID, tick, and collar checks.", "sentinel_iron.application.risk_check"),
    ("iron.strategy.trend", "iron", "strategy", "research_ready", "Volatility-normalized multi-lookback futures trend signal.", "sentinel_iron.strategies.trend_following"),
    ("iron.strategy.composite", "iron", "strategy", "research_ready", "Weighted trend/carry composite signals.", "sentinel_iron.strategies.composite"),

    # Combination integration features.
    ("combination.sources.pinned", "combination", "provenance", "operational", "Exact source commits pinned as complete submodules.", "combination.lock.json"),
    ("combination.runtime.isolated", "combination", "runtime", "operational", "Chain and Iron execute in subprocesses with explicit source paths.", "sentinel_combination.runtime"),
    ("combination.contracts.neutral", "combination", "integration", "scaffold", "Asset-class-neutral experiment envelopes and readiness snapshots.", "sentinel_combination.contracts"),
    ("combination.live.fail_closed", "combination", "safety", "operational", "The facade never bypasses source live-trading gates.", "sentinel_combination.runtime"),
)


CAPABILITIES: tuple[Capability, ...] = tuple(Capability(*row) for row in _ROWS)


def list_capabilities(owner: str | None = None) -> tuple[Capability, ...]:
    if owner in (None, "all"):
        return CAPABILITIES
    return tuple(capability for capability in CAPABILITIES if capability.owner == owner)


def capability_dicts(owner: str | None = None) -> list[dict[str, str]]:
    return [capability.to_dict() for capability in list_capabilities(owner)]


def owners() -> tuple[str, ...]:
    return tuple(sorted({capability.owner for capability in CAPABILITIES}))


def categories(capabilities: Iterable[Capability] | None = None) -> tuple[str, ...]:
    selected = capabilities or CAPABILITIES
    return tuple(sorted({capability.category for capability in selected}))
