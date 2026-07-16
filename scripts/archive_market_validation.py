from __future__ import annotations

import argparse
import csv
import importlib
import json
import math
import os
import platform
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass
class Trade:
    symbol: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    quantity: float
    exit_reason: str
    pnl: float


@dataclass
class RunResult:
    symbol: str
    stop_pct: float
    target_pct: float
    trail_pct: float
    slippage_bps: float
    commission: float
    bars: int
    first_timestamp: str
    last_timestamp: str
    ending_equity: float
    return_pct: float
    trades: int
    wins: int
    losses: int
    win_rate_pct: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    max_drawdown_pct: float
    exit_counts: dict[str, int]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def handoff(symbol: str, action: str, key: str, *, quantity: float | None = None, trailing: float | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract_version": "edge.pulse.handoff.v1",
        "symbol": symbol,
        "action": action,
        "confidence": 1.0,
        "reason": "archive_validation_campaign",
        "mode": "paper",
        "orb_session": "market_open",
        "idempotency_key": key,
        "source": "sentinel_edge",
        "created_at": time.time(),
        "metadata": {},
    }
    if quantity is not None:
        payload["metadata"]["quantity"] = quantity
    if trailing is not None:
        payload["trailing_percent"] = trailing
    return payload


def make_bar(MarketBar: Any, timestamp: str, symbol: str, open_: float, high: float, low: float, close: float, volume: float = 1.0) -> Any:
    return MarketBar(timestamp=timestamp, symbol=symbol, open=open_, high=high, low=low, close=close, volume=volume, source="validation_synthetic")


def scenario_tests(SentinelArchive: Any, SimulationConfig: Any, MarketBar: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def execute(name: str, config: Any, bars: list[Any], actions: list[tuple[int, dict[str, Any]]], expected_action: str | None) -> None:
        engine = SentinelArchive(config)
        session = engine.import_bars(name, bars, source="validation_synthetic")
        engine.start_replay(session.session_id)
        actions_by_step: dict[int, list[dict[str, Any]]] = {}
        for step_index, payload in actions:
            actions_by_step.setdefault(step_index, []).append(payload)
        snapshots: list[dict[str, Any]] = []
        step_index = 0
        while engine.replay.active:
            engine.step()
            for payload in actions_by_step.get(step_index, []):
                response = engine.process_handoff(payload)
                snapshots.append({"step": step_index, "payload": payload, "response": response})
            step_index += 1
        decision_actions = [item.get("action") for item in engine.decisions]
        passed = expected_action is None or expected_action in decision_actions
        results.append(
            {
                "name": name,
                "passed": passed,
                "expected_action": expected_action,
                "decision_actions": decision_actions,
                "ending_equity": engine.account.total_equity,
                "open_positions": engine.account.open_positions,
                "handoffs": snapshots,
                "event_log": list(reversed(engine.event_log)),
            }
        )

    base = "2026-01-02T14:30:00+00:00"
    execute(
        "take_profit_exit",
        SimulationConfig(starting_cash=100000, default_quantity=10, max_allocation_pct=100, take_profit_percent=5, regular_stop_percent=0),
        [
            make_bar(MarketBar, base, "TEST", 100, 100, 100, 100),
            make_bar(MarketBar, "2026-01-02T14:31:00+00:00", "TEST", 100, 106, 99.5, 105),
        ],
        [(0, handoff("TEST", "buy", "tp-buy", quantity=10))],
        "take_profit_sell",
    )
    execute(
        "regular_stop_exit",
        SimulationConfig(starting_cash=100000, default_quantity=10, max_allocation_pct=100, take_profit_percent=0, regular_stop_percent=3),
        [
            make_bar(MarketBar, base, "TEST", 100, 100, 100, 100),
            make_bar(MarketBar, "2026-01-02T14:31:00+00:00", "TEST", 100, 101, 96, 97),
        ],
        [(0, handoff("TEST", "buy", "stop-buy", quantity=10))],
        "regular_stop_sell",
    )
    execute(
        "trailing_stop_activation_and_exit",
        SimulationConfig(starting_cash=100000, default_quantity=10, max_allocation_pct=100, take_profit_percent=0, regular_stop_percent=0, default_trailing_percent=2),
        [
            make_bar(MarketBar, base, "TEST", 100, 100, 100, 100),
            make_bar(MarketBar, "2026-01-02T14:31:00+00:00", "TEST", 100, 110, 109, 109.5),
            make_bar(MarketBar, "2026-01-02T14:32:00+00:00", "TEST", 109.5, 110, 107, 108),
        ],
        [
            (0, handoff("TEST", "buy", "trail-buy", quantity=10)),
            (0, handoff("TEST", "trailing_stop", "trail-enable", trailing=2)),
        ],
        "trailing_stop_sell",
    )
    execute(
        "tightened_trailing_stop_exit",
        SimulationConfig(starting_cash=100000, default_quantity=10, max_allocation_pct=100, take_profit_percent=0, regular_stop_percent=0, default_trailing_percent=5),
        [
            make_bar(MarketBar, base, "TEST", 100, 100, 100, 100),
            make_bar(MarketBar, "2026-01-02T14:31:00+00:00", "TEST", 100, 108, 107, 107.5),
            make_bar(MarketBar, "2026-01-02T14:32:00+00:00", "TEST", 107.5, 108, 105, 106),
        ],
        [
            (0, handoff("TEST", "buy", "tight-buy", quantity=10)),
            (0, handoff("TEST", "trailing_stop", "tight-enable", trailing=5)),
            (1, handoff("TEST", "tighten_trailing_stop", "tight-update", trailing=2)),
        ],
        "trailing_stop_sell",
    )

    engine = SentinelArchive(SimulationConfig(starting_cash=100000, default_quantity=10, max_allocation_pct=100, fill_ratio=0.5))
    bars = [make_bar(MarketBar, base, "TEST", 100, 100, 100, 100)]
    session = engine.import_bars("partial_fill_and_idempotency", bars, source="validation_synthetic")
    engine.start_replay(session.session_id)
    engine.step()
    first = engine.process_handoff(handoff("TEST", "buy", "duplicate-key", quantity=10))
    duplicate = engine.process_handoff(handoff("TEST", "buy", "duplicate-key", quantity=10))
    qty = engine.account.positions["TEST"].quantity
    results.append(
        {
            "name": "partial_fill_and_idempotency",
            "passed": first.get("accepted") is True and duplicate.get("reason") == "duplicate" and math.isclose(qty, 5.0),
            "expected_quantity": 5.0,
            "actual_quantity": qty,
            "first_response": first,
            "duplicate_response": duplicate,
        }
    )

    engine = SentinelArchive(SimulationConfig(starting_cash=100000, default_quantity=10, max_allocation_pct=100))
    session = engine.import_bars("emergency_exit", bars, source="validation_synthetic")
    engine.start_replay(session.session_id)
    engine.step()
    engine.process_handoff(handoff("TEST", "buy", "emergency-buy", quantity=10))
    response = engine.process_handoff(handoff("GLOBAL", "emergency_exit", "emergency-exit"))
    results.append(
        {
            "name": "emergency_exit",
            "passed": response.get("accepted") is True and engine.account.open_positions == 0,
            "response": response,
            "open_positions": engine.account.open_positions,
            "decision_actions": [item.get("action") for item in engine.decisions],
        }
    )
    return results


def download_history(symbol: str, period: str = "1mo", interval: str = "1h") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import pandas as pd
    import yfinance as yf

    frame = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False, threads=False)
    if frame is None or frame.empty:
        raise RuntimeError(f"no historical rows returned for {symbol}")
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [str(item[0]) for item in frame.columns]
    frame = frame.dropna(subset=["Open", "High", "Low", "Close"])
    rows: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        timestamp = index.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)
        rows.append(
            {
                "timestamp": timestamp.isoformat(),
                "symbol": symbol,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row.get("Volume", 0.0) or 0.0),
                "source": "yfinance_public_historical",
            }
        )
    metadata = {
        "provider": "Yahoo Finance via yfinance",
        "requested_period": period,
        "requested_interval": interval,
        "rows": len(rows),
        "first_timestamp": rows[0]["timestamp"],
        "last_timestamp": rows[-1]["timestamp"],
        "downloaded_at": utc_now(),
    }
    return rows, metadata


def sma(values: list[float], size: int) -> float | None:
    if len(values) < size:
        return None
    return sum(values[-size:]) / size


def collect_new_decisions(engine: Any, seen: set[tuple[Any, ...]], output: list[dict[str, Any]], replay_timestamp: str | None) -> None:
    for item in reversed(engine.decisions):
        signature = (item.get("action"), item.get("symbol"), item.get("fill_price"), item.get("quantity"), item.get("timestamp"))
        if signature in seen:
            continue
        seen.add(signature)
        output.append({**item, "replay_timestamp": replay_timestamp})


def pair_trades(decisions: list[dict[str, Any]]) -> list[Trade]:
    open_entries: dict[str, list[dict[str, Any]]] = {}
    trades: list[Trade] = []
    for item in decisions:
        symbol = str(item.get("symbol"))
        action = str(item.get("action"))
        if action == "buy":
            open_entries.setdefault(symbol, []).append(item)
            continue
        if action in {"sell", "regular_stop_sell", "take_profit_sell", "trailing_stop_sell", "stop_all", "emergency_exit"}:
            entries = open_entries.get(symbol) or []
            if not entries:
                continue
            entry = entries.pop(0)
            entry_price = float(entry.get("fill_price") or entry.get("price") or 0.0)
            exit_price = float(item.get("fill_price") or item.get("price") or 0.0)
            quantity = float(item.get("quantity") or entry.get("quantity") or 0.0)
            trades.append(
                Trade(
                    symbol=symbol,
                    entry_time=str(entry.get("replay_timestamp") or entry.get("timestamp")),
                    exit_time=str(item.get("replay_timestamp") or item.get("timestamp")),
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=quantity,
                    exit_reason=action,
                    pnl=(exit_price - entry_price) * quantity,
                )
            )
    return trades


def max_drawdown(values: list[float]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            worst = min(worst, (value - peak) / peak * 100.0)
    return abs(worst)


def run_market_case(
    SentinelArchive: Any,
    SimulationConfig: Any,
    MarketBar: Any,
    symbol: str,
    raw_rows: list[dict[str, Any]],
    *,
    stop_pct: float,
    target_pct: float,
    trail_pct: float,
    slippage_bps: float,
    commission: float,
) -> tuple[RunResult, list[dict[str, Any]], list[float]]:
    first_price = raw_rows[0]["close"]
    quantity = max(0.000001, 10000.0 / first_price)
    config = SimulationConfig(
        starting_cash=100000.0,
        default_quantity=quantity,
        max_allocation_pct=100.0,
        fill_ratio=1.0,
        slippage_bps=slippage_bps,
        commission_per_order=commission,
        regular_stop_percent=stop_pct,
        take_profit_percent=target_pct,
        default_trailing_percent=trail_pct,
        reject_below_confidence=0.0,
    )
    engine = SentinelArchive(config)
    bars = [MarketBar(**row) for row in raw_rows]
    session = engine.import_bars(f"one-month-{symbol}", bars, source="yfinance_public_historical")
    engine.start_replay(session.session_id)
    closes: list[float] = []
    decisions: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    equity_curve: list[float] = [engine.account.total_equity]
    signal_counter = 0
    while engine.replay.active:
        engine.step()
        index = max(0, engine.replay.index - 1)
        close = raw_rows[index]["close"]
        closes.append(close)
        fast = sma(closes, 8)
        slow = sma(closes, 24)
        position = engine.account.positions.get(symbol)
        if fast is not None and slow is not None:
            if position is None and fast > slow:
                signal_counter += 1
                engine.process_handoff(handoff(symbol, "buy", f"{symbol}-buy-{signal_counter}", quantity=quantity))
                if symbol in engine.account.positions:
                    signal_counter += 1
                    engine.process_handoff(handoff(symbol, "trailing_stop", f"{symbol}-trail-{signal_counter}", trailing=trail_pct))
            elif position is not None and fast < slow:
                signal_counter += 1
                engine.process_handoff(handoff(symbol, "sell", f"{symbol}-sell-{signal_counter}"))
        collect_new_decisions(engine, seen, decisions, engine.replay.current_timestamp)
        equity_curve.append(engine.account.total_equity)
    if symbol in engine.account.positions:
        signal_counter += 1
        engine.process_handoff(handoff(symbol, "sell", f"{symbol}-final-{signal_counter}"))
        collect_new_decisions(engine, seen, decisions, engine.replay.current_timestamp)
        equity_curve.append(engine.account.total_equity)
    trades = pair_trades(decisions)
    wins = sum(1 for trade in trades if trade.pnl > 0)
    losses = sum(1 for trade in trades if trade.pnl <= 0)
    gross_profit = sum(trade.pnl for trade in trades if trade.pnl > 0)
    gross_loss = abs(sum(trade.pnl for trade in trades if trade.pnl < 0))
    exit_counts: dict[str, int] = {}
    for trade in trades:
        exit_counts[trade.exit_reason] = exit_counts.get(trade.exit_reason, 0) + 1
    result = RunResult(
        symbol=symbol,
        stop_pct=stop_pct,
        target_pct=target_pct,
        trail_pct=trail_pct,
        slippage_bps=slippage_bps,
        commission=commission,
        bars=len(raw_rows),
        first_timestamp=raw_rows[0]["timestamp"],
        last_timestamp=raw_rows[-1]["timestamp"],
        ending_equity=engine.account.total_equity,
        return_pct=(engine.account.total_equity / 100000.0 - 1.0) * 100.0,
        trades=len(trades),
        wins=wins,
        losses=losses,
        win_rate_pct=(wins / len(trades) * 100.0) if trades else 0.0,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=(gross_profit / gross_loss) if gross_loss else (None if not gross_profit else float("inf")),
        max_drawdown_pct=max_drawdown(equity_curve),
        exit_counts=exit_counts,
    )
    return result, [asdict(item) for item in trades], equity_curve


def write_markdown(
    path: Path,
    metadata: dict[str, Any],
    scenarios: list[dict[str, Any]],
    market_results: list[RunResult],
    data_metadata: dict[str, Any],
    failures: list[dict[str, Any]],
) -> None:
    passed = sum(1 for item in scenarios if item.get("passed"))
    ranked = sorted(market_results, key=lambda item: item.return_pct, reverse=True)
    lines = [
        "# Sentinel Combination / Sentinel Archive Validation Report",
        "",
        f"Generated: `{metadata['generated_at']}`",
        "",
        "## Scope and interpretation",
        "",
        "This campaign uses Sentinel Archive as an external deterministic replay harness. It does not place broker orders and it does not certify real-money profitability. The one-month profitability matrix is a normalized spot-style experiment using Archive's account model; it does not apply listed-futures contract multipliers, exchange margin, funding, queue position, or broker fills.",
        "",
        "## Deterministic automation scenarios",
        "",
        f"Passed **{passed}/{len(scenarios)}** scenarios.",
        "",
        "| Scenario | Result | Expected evidence | Observed actions |",
        "|---|---:|---|---|",
    ]
    for item in scenarios:
        lines.append(f"| {item['name']} | {'PASS' if item.get('passed') else 'FAIL'} | {item.get('expected_action', '')} | {', '.join(item.get('decision_actions', []))} |")
    lines.extend(["", "## Historical data", "", "| Symbol | Provider | Bars | First | Last |", "|---|---|---:|---|---|"])
    for symbol, info in data_metadata.items():
        lines.append(f"| {symbol} | {info['provider']} | {info['rows']} | {info['first_timestamp']} | {info['last_timestamp']} |")
    if failures:
        lines.extend(["", "### Data or execution failures", ""])
        for failure in failures:
            lines.append(f"- `{failure.get('symbol', failure.get('stage', 'unknown'))}`: {failure['error']}")
    lines.extend(["", "## Best normalized one-month matrix results", "", "| Rank | Symbol | Stop % | Target % | Trail % | Slip bps | Commission | Return % | Trades | Win % | Max DD % | Exits |", "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"])
    for index, item in enumerate(ranked[:25], start=1):
        lines.append(
            f"| {index} | {item.symbol} | {item.stop_pct:.2f} | {item.target_pct:.2f} | {item.trail_pct:.2f} | {item.slippage_bps:.1f} | {item.commission:.2f} | {item.return_pct:.4f} | {item.trades} | {item.win_rate_pct:.2f} | {item.max_drawdown_pct:.4f} | {json.dumps(item.exit_counts, sort_keys=True)} |"
        )
    lines.extend(
        [
            "",
            "## Acquisition and reproduction",
            "",
            "- Historical bars were requested at runtime through `yfinance` with `period=1mo` and `interval=1h`.",
            "- Synthetic scenarios use explicit OHLC bars stored in the campaign script so target, stop, trailing activation, tightening, duplicate handoff, partial-fill, and emergency-exit behavior are reproducible.",
            "- The market strategy is deliberately transparent: 8-bar/24-bar moving-average entry and exit, with Archive stop, target, and trailing policies applied on subsequent bars.",
            "- All raw market rows, scenario records, parameter results, trade logs, and equity curves are included in the workflow artifact.",
            "",
            "## Known limitations discovered by design inspection",
            "",
            "1. Archive evaluates trailing stop before regular stop and take profit inside each OHLC bar; when multiple thresholds are crossed in one bar, this priority is an assumption rather than known tick ordering.",
            "2. Archive is long-only and uses spot-style cash accounting. Its profitability values cannot be treated as futures-contract P&L.",
            "3. Public Yahoo data may be delayed, adjusted, incomplete, or use a continuous/front-month representation that differs from the exact contract a broker would route.",
            "4. No brokerage order acknowledgement, partial broker fill, cancellation, margin preview, or reconciliation is exercised by this campaign.",
            "5. Optimizing parameters on the same month used for evaluation is in-sample and creates selection bias. The ranked table is diagnostic, not evidence of a durable edge.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-path", required=True)
    parser.add_argument("--output-dir", default="validation-output")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = Path(args.archive_path).resolve()
    sys.path.insert(0, str(archive_path))
    core = importlib.import_module("sentinel_archive.core")
    models = importlib.import_module("sentinel_archive.models")
    SentinelArchive = core.SentinelArchive
    SimulationConfig = models.SimulationConfig
    MarketBar = models.MarketBar

    metadata = {
        "generated_at": utc_now(),
        "python": sys.version,
        "platform": platform.platform(),
        "combination_sha": os.getenv("COMBINATION_SHA"),
        "archive_sha": os.getenv("ARCHIVE_SHA"),
        "campaign": "archive_market_validation_v1",
    }
    scenarios = scenario_tests(SentinelArchive, SimulationConfig, MarketBar)
    (output_dir / "scenario_results.json").write_text(json.dumps(scenarios, indent=2, default=str), encoding="utf-8")

    symbols = ["ES=F", "NQ=F", "CL=F", "GC=F", "BTC-USD", "ETH-USD"]
    data_metadata: dict[str, Any] = {}
    raw_data: dict[str, list[dict[str, Any]]] = {}
    failures: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            rows, info = download_history(symbol)
            raw_data[symbol] = rows
            data_metadata[symbol] = info
            with (output_dir / f"market_{symbol.replace('=', '_').replace('-', '_')}.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        except Exception as exc:
            failures.append({"stage": "download", "symbol": symbol, "error": repr(exc)})

    market_results: list[RunResult] = []
    best_trade_logs: dict[str, Any] = {}
    best_equity_curves: dict[str, Any] = {}
    settings = [
        (stop, target, trail, slippage, commission)
        for stop in (0.5, 1.0, 2.0)
        for target in (1.0, 2.0, 4.0)
        for trail in (0.5, 1.0, 2.0)
        for slippage in (0.0, 5.0)
        for commission in (0.0, 2.5)
    ]
    for symbol, rows in raw_data.items():
        symbol_runs: list[tuple[RunResult, list[dict[str, Any]], list[float]]] = []
        for stop, target, trail, slippage, commission in settings:
            try:
                symbol_runs.append(
                    run_market_case(
                        SentinelArchive,
                        SimulationConfig,
                        MarketBar,
                        symbol,
                        rows,
                        stop_pct=stop,
                        target_pct=target,
                        trail_pct=trail,
                        slippage_bps=slippage,
                        commission=commission,
                    )
                )
            except Exception as exc:
                failures.append({"stage": "market_case", "symbol": symbol, "settings": [stop, target, trail, slippage, commission], "error": repr(exc)})
        market_results.extend(item[0] for item in symbol_runs)
        if symbol_runs:
            best = max(symbol_runs, key=lambda item: item[0].return_pct)
            best_trade_logs[symbol] = {"settings": asdict(best[0]), "trades": best[1]}
            best_equity_curves[symbol] = {"settings": asdict(best[0]), "equity": best[2]}

    with (output_dir / "market_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        if market_results:
            fieldnames = list(asdict(market_results[0]))
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in market_results:
                row = asdict(item)
                row["exit_counts"] = json.dumps(row["exit_counts"], sort_keys=True)
                writer.writerow(row)
    (output_dir / "best_trade_logs.json").write_text(json.dumps(best_trade_logs, indent=2, default=str), encoding="utf-8")
    (output_dir / "best_equity_curves.json").write_text(json.dumps(best_equity_curves, indent=2, default=str), encoding="utf-8")
    (output_dir / "run_metadata.json").write_text(json.dumps({**metadata, "data": data_metadata, "failures": failures, "settings_count": len(settings)}, indent=2), encoding="utf-8")
    write_markdown(output_dir / "VALIDATION_REPORT.md", metadata, scenarios, market_results, data_metadata, failures)

    scenario_failures = [item for item in scenarios if not item.get("passed")]
    if scenario_failures:
        print(json.dumps({"scenario_failures": scenario_failures}, indent=2))
        return 2
    if not market_results:
        print(json.dumps({"error": "no historical market cases completed", "failures": failures}, indent=2))
        return 3
    print(json.dumps({"scenarios": len(scenarios), "scenario_passed": len(scenarios), "market_runs": len(market_results), "symbols": sorted(data_metadata), "failures": len(failures)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
