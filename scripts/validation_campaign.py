from __future__ import annotations

import argparse
import csv
import dataclasses
import importlib
import json
import os
import pkgutil
import platform
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_json(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {k: safe_json(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe_json(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def run_command(args: list[str], timeout: int = 120) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=os.environ.copy(),
        )
        return {
            "command": args,
            "returncode": completed.returncode,
            "duration_seconds": round(time.perf_counter() - started, 4),
            "stdout": completed.stdout[-20000:],
            "stderr": completed.stderr[-20000:],
        }
    except Exception as exc:  # pragma: no cover - evidence collection
        return {
            "command": args,
            "returncode": None,
            "duration_seconds": round(time.perf_counter() - started, 4),
            "error": f"{type(exc).__name__}: {exc}",
        }


def inspect_modules() -> dict[str, Any]:
    import sentinel_combination

    successes: list[str] = []
    failures: list[dict[str, str]] = []
    prefix = sentinel_combination.__name__ + "."
    for module in pkgutil.walk_packages(sentinel_combination.__path__, prefix):
        try:
            importlib.import_module(module.name)
            successes.append(module.name)
        except Exception as exc:
            failures.append(
                {
                    "module": module.name,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return {
        "package_file": str(Path(sentinel_combination.__file__).resolve()),
        "imported_count": len(successes),
        "imported_modules": successes,
        "failures": failures,
    }


def inspect_catalog() -> dict[str, Any]:
    from sentinel_combination.brokers.catalog import list_broker_companies
    from sentinel_combination.brokers.registry import BrokerRegistry

    companies = list(list_broker_companies())
    company_rows: list[dict[str, Any]] = []
    broker_ids: list[str] = []
    for company in companies:
        row = safe_json(company)
        if not isinstance(row, dict):
            row = {"repr": repr(company)}
        broker_id = str(row.get("broker_id", getattr(company, "broker_id", "")))
        broker_ids.append(broker_id)
        company_rows.append(row)

    registry = BrokerRegistry()
    adapters = getattr(registry, "adapters", {})
    adapter_keys = sorted(adapters.keys()) if isinstance(adapters, dict) else []
    duplicates = sorted({item for item in broker_ids if broker_ids.count(item) > 1})
    blanks = [index for index, item in enumerate(broker_ids) if not item]
    return {
        "company_count": len(companies),
        "companies": company_rows,
        "broker_ids": sorted(broker_ids),
        "duplicate_broker_ids": duplicates,
        "blank_broker_id_indexes": blanks,
        "registered_adapter_keys": adapter_keys,
    }


def inspect_cli_and_database(output_dir: Path) -> dict[str, Any]:
    commands = [
        ["combination", "--help"],
        ["combination", "brokers"],
        ["combination", "brokers", "--product", "listed_futures"],
        ["combination", "brokers", "--product", "crypto_futures"],
    ]
    results = [run_command(command) for command in commands]

    catalog = inspect_catalog()
    for broker_id in catalog["broker_ids"]:
        results.append(run_command(["combination", "broker-info", broker_id]))

    database_path = output_dir / "validation.sqlite3"
    results.append(run_command(["combination", "init-db", "--path", str(database_path)]))
    results.append(run_command(["combination", "doctor", "--path", str(database_path)]))

    sqlite_result: dict[str, Any] = {"exists": database_path.exists()}
    if database_path.exists():
        connection = sqlite3.connect(database_path)
        try:
            sqlite_result.update(
                {
                    "integrity_check": connection.execute("PRAGMA integrity_check").fetchone()[0],
                    "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
                    "synchronous": connection.execute("PRAGMA synchronous").fetchone()[0],
                    "foreign_keys": connection.execute("PRAGMA foreign_keys").fetchone()[0],
                    "table_count": connection.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                    ).fetchone()[0],
                }
            )
        finally:
            connection.close()
    return {"commands": results, "sqlite": sqlite_result}


def create_archive_scenarios(output_dir: Path) -> dict[str, Any]:
    scenario_dir = output_dir / "archive_scenarios"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    scenarios: dict[str, list[tuple[str, str, float, float, float, float, float]]] = {
        "steady_up": [
            (f"2026-07-16T14:{minute:02d}:00Z", "BTC-PERP", 100 + minute, 102 + minute, 99 + minute, 101 + minute, 1000 + minute)
            for minute in range(10)
        ],
        "steady_down": [
            (f"2026-07-16T15:{minute:02d}:00Z", "ESU6", 5000 - minute, 5001 - minute, 4997 - minute, 4998 - minute, 500 + minute)
            for minute in range(10)
        ],
        "gap_and_recovery": [
            ("2026-07-16T16:00:00Z", "ETH-PERP", 3000, 3010, 2990, 3005, 800),
            ("2026-07-16T16:01:00Z", "ETH-PERP", 2850, 2900, 2800, 2875, 5000),
            ("2026-07-16T16:02:00Z", "ETH-PERP", 2875, 2960, 2860, 2940, 3200),
        ],
        "same_timestamp_multi_symbol": [
            ("2026-07-16T17:00:00Z", "BTC-PERP", 60000, 60100, 59900, 60050, 100),
            ("2026-07-16T17:00:00Z", "ETH-PERP", 3200, 3220, 3180, 3210, 200),
            ("2026-07-16T17:01:00Z", "BTC-PERP", 60050, 60200, 60000, 60150, 120),
            ("2026-07-16T17:01:00Z", "ETH-PERP", 3210, 3235, 3200, 3225, 210),
        ],
        "out_of_order_input": [
            ("2026-07-16T18:02:00Z", "NQU6", 22010, 22020, 21990, 22000, 50),
            ("2026-07-16T18:00:00Z", "NQU6", 22000, 22015, 21995, 22010, 40),
            ("2026-07-16T18:01:00Z", "NQU6", 22010, 22030, 22000, 22020, 45),
        ],
        "extreme_range": [
            ("2026-07-16T19:00:00Z", "BTC-PERP", 60000, 66000, 48000, 51000, 25000),
            ("2026-07-16T19:01:00Z", "BTC-PERP", 51000, 57000, 50000, 56000, 18000),
        ],
    }

    summaries: list[dict[str, Any]] = []
    header = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
    for name, rows in scenarios.items():
        path = scenario_dir / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        sorted_rows = sorted(rows, key=lambda row: (row[0], row[1]))
        groups: dict[str, int] = {}
        invalid_ohlc = 0
        for timestamp, _, open_price, high, low, close, _ in sorted_rows:
            groups[timestamp] = groups.get(timestamp, 0) + 1
            if high < max(open_price, close) or low > min(open_price, close) or low > high:
                invalid_ohlc += 1
        summaries.append(
            {
                "scenario": name,
                "path": str(path),
                "row_count": len(rows),
                "timestamp_group_count": len(groups),
                "max_same_timestamp_group": max(groups.values()),
                "input_was_sorted": rows == sorted_rows,
                "invalid_ohlc_rows": invalid_ohlc,
            }
        )
    return {"schema": header, "scenarios": summaries}


def inspect_archive(archive_path: Path, output_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(archive_path.resolve()),
        "exists": archive_path.exists(),
        "generated_scenarios": create_archive_scenarios(output_dir),
    }
    if not archive_path.exists():
        return result

    candidate_files = sorted(
        path for path in archive_path.rglob("*") if path.is_file() and path.suffix.lower() in {".csv", ".jsonl"}
    )
    inspected: list[dict[str, Any]] = []
    for path in candidate_files[:100]:
        item: dict[str, Any] = {
            "path": str(path.relative_to(archive_path)),
            "size": path.stat().st_size,
        }
        try:
            if path.suffix.lower() == ".csv":
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.reader(handle)
                    header = next(reader, [])
                    rows = sum(1 for _ in reader)
                item.update({"header": header, "row_count": rows})
            else:
                with path.open("r", encoding="utf-8") as handle:
                    rows = sum(1 for line in handle if line.strip())
                item["row_count"] = rows
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
        inspected.append(item)
    result["recorded_data_files"] = inspected

    sys.path.insert(0, str(archive_path.resolve()))
    try:
        module = importlib.import_module("sentinel_archive.main")
        app = getattr(module, "app", None)
        result["main_imported"] = True
        if app is not None:
            routes = sorted(
                {
                    getattr(route, "path", "")
                    for route in getattr(app, "routes", [])
                    if getattr(route, "path", "")
                }
            )
            result["api_routes"] = routes
            try:
                from fastapi.testclient import TestClient

                with TestClient(app) as client:
                    response = client.get("/api/health")
                result["health"] = {
                    "status_code": response.status_code,
                    "body": response.text[:5000],
                }
            except Exception as exc:
                result["health_error"] = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        result["main_imported"] = False
        result["import_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            sys.path.remove(str(archive_path.resolve()))
        except ValueError:
            pass
    return result


def choose_derivative_market(markets: dict[str, dict[str, Any]]) -> str | None:
    candidates: list[tuple[int, str]] = []
    for symbol, market in markets.items():
        if market.get("active") is False:
            continue
        if not (market.get("swap") or market.get("future")):
            continue
        if str(market.get("base", "")).upper() != "BTC":
            continue
        quote = str(market.get("quote", "")).upper()
        score = {"USDT": 0, "USD": 1, "USDC": 2}.get(quote, 10)
        if market.get("swap"):
            score -= 1
        candidates.append((score, symbol))
    return min(candidates)[1] if candidates else None


def inspect_live_markets() -> dict[str, Any]:
    import ccxt

    exchange_specs: list[tuple[str, dict[str, Any]]] = [
        ("binanceusdm", {"options": {"defaultType": "future"}}),
        ("bybit", {"options": {"defaultType": "swap"}}),
        ("okx", {"options": {"defaultType": "swap"}}),
        ("bitget", {"options": {"defaultType": "swap"}}),
        ("kucoinfutures", {}),
        ("krakenfutures", {}),
        ("deribit", {}),
        ("bitmex", {}),
        ("gateio", {"options": {"defaultType": "swap"}}),
        ("mexc", {"options": {"defaultType": "swap"}}),
        ("htx", {"options": {"defaultType": "swap"}}),
        ("phemex", {}),
        ("woo", {}),
        ("bingx", {"options": {"defaultType": "swap"}}),
        ("dydx", {}),
    ]
    rows: list[dict[str, Any]] = []
    for exchange_id, options in exchange_specs:
        row: dict[str, Any] = {"exchange": exchange_id, "started_at": utc_now()}
        started = time.perf_counter()
        try:
            exchange_class = getattr(ccxt, exchange_id)
            exchange = exchange_class(
                {
                    "enableRateLimit": True,
                    "timeout": 20000,
                    **options,
                }
            )
            markets = exchange.load_markets()
            symbol = choose_derivative_market(markets)
            row["market_count"] = len(markets)
            row["selected_symbol"] = symbol
            if not symbol:
                raise RuntimeError("No active BTC derivative market found")
            ticker = exchange.fetch_ticker(symbol)
            order_book = exchange.fetch_order_book(symbol, 5)
            bid = ticker.get("bid")
            ask = ticker.get("ask")
            last = ticker.get("last")
            row.update(
                {
                    "status": "reachable",
                    "bid": bid,
                    "ask": ask,
                    "last": last,
                    "ticker_timestamp": ticker.get("timestamp"),
                    "order_book_timestamp": order_book.get("timestamp"),
                    "bid_levels": len(order_book.get("bids") or []),
                    "ask_levels": len(order_book.get("asks") or []),
                    "spread_valid": bid is None or ask is None or bid <= ask,
                    "positive_last": last is None or last > 0,
                }
            )
            if exchange.has.get("fetchFundingRate"):
                try:
                    funding = exchange.fetch_funding_rate(symbol)
                    row["funding_rate"] = funding.get("fundingRate")
                    row["funding_timestamp"] = funding.get("timestamp")
                except Exception as exc:
                    row["funding_error"] = f"{type(exc).__name__}: {exc}"
            try:
                exchange.close()
            except Exception:
                pass
        except Exception as exc:
            row["status"] = "unreachable_or_unsupported"
            row["error"] = f"{type(exc).__name__}: {exc}"
        row["duration_seconds"] = round(time.perf_counter() - started, 4)
        rows.append(row)
    return {
        "policy": "Public read-only market-data calls only. No credentials and no order methods.",
        "results": rows,
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Sentinel Combination Validation Campaign",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Python: `{report['environment']['python']}`",
        f"Platform: `{report['environment']['platform']}`",
        "",
        "## Acquisition method",
        "",
        "- Combination package and tests were run from the checked-out repository commit.",
        "- Broker catalog and CLI results were obtained by importing and invoking the installed package.",
        "- SQLite findings were read directly with SQLite PRAGMA statements after `init-db` and `doctor`.",
        "- Sentinel Archive findings came from a checked-out Archive repository, its FastAPI app, and recorded data files.",
        "- Live market findings used unauthenticated CCXT ticker/order-book/funding endpoints only; no order endpoint was called.",
        "",
        "## Summary",
        "",
    ]
    modules = report.get("modules", {})
    catalog = report.get("catalog", {})
    cli = report.get("cli_and_database", {})
    lines.extend(
        [
            f"- Imported Combination modules: **{modules.get('imported_count', 0)}**",
            f"- Import failures: **{len(modules.get('failures', []))}**",
            f"- Broker companies cataloged: **{catalog.get('company_count', 0)}**",
            f"- Registered direct adapter keys: **{len(catalog.get('registered_adapter_keys', []))}**",
            f"- SQLite integrity: **{cli.get('sqlite', {}).get('integrity_check', 'not run')}**",
        ]
    )
    if "archive" in report:
        archive = report["archive"]
        lines.append(f"- Sentinel Archive imported: **{archive.get('main_imported', False)}**")
        lines.append(f"- Sentinel Archive data files inspected: **{len(archive.get('recorded_data_files', []))}**")
    if "live_markets" in report:
        market_rows = report["live_markets"].get("results", [])
        reached = sum(1 for row in market_rows if row.get("status") == "reachable")
        lines.append(f"- Public derivatives venues reached: **{reached}/{len(market_rows)}**")
    lines.extend(["", "## Critical observations", ""])
    critical: list[str] = []
    if modules.get("failures"):
        critical.append("One or more package modules failed to import.")
    if catalog.get("duplicate_broker_ids"):
        critical.append("Duplicate broker identifiers were found.")
    if catalog.get("blank_broker_id_indexes"):
        critical.append("Blank broker identifiers were found.")
    if cli.get("sqlite", {}).get("integrity_check") not in {None, "ok"}:
        critical.append("SQLite integrity check did not return `ok`.")
    failed_commands = [
        item for item in cli.get("commands", []) if item.get("returncode") not in {0}
    ]
    if failed_commands:
        critical.append(f"{len(failed_commands)} CLI/database commands returned non-zero status.")
    if not critical:
        critical.append("No critical failure was detected by this runner.")
    lines.extend(f"- {item}" for item in critical)
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "Passing this campaign does not certify funded trading. Authenticated order submission, cancellation, fills, margin, position reconciliation, disconnect recovery, and emergency flattening must be tested separately for each broker account and adapter.",
            "",
            "Detailed command output and structured evidence are stored in `validation-results.json` and the workflow logs.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="validation-results")
    parser.add_argument("--live-market", action="store_true")
    parser.add_argument("--archive-path")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "generated_at": utc_now(),
        "environment": {
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cwd": str(Path.cwd()),
            "github_sha": os.getenv("GITHUB_SHA"),
            "github_run_id": os.getenv("GITHUB_RUN_ID"),
        },
    }

    for name, function in (
        ("modules", inspect_modules),
        ("catalog", inspect_catalog),
        ("cli_and_database", lambda: inspect_cli_and_database(output_dir)),
    ):
        try:
            report[name] = function()
        except Exception as exc:
            report[name] = {"fatal_error": f"{type(exc).__name__}: {exc}"}

    if args.archive_path:
        try:
            report["archive"] = inspect_archive(Path(args.archive_path), output_dir)
        except Exception as exc:
            report["archive"] = {"fatal_error": f"{type(exc).__name__}: {exc}"}
    else:
        report["archive_scenarios"] = create_archive_scenarios(output_dir)

    if args.live_market:
        try:
            report["live_markets"] = inspect_live_markets()
        except Exception as exc:
            report["live_markets"] = {"fatal_error": f"{type(exc).__name__}: {exc}"}

    json_path = output_dir / "validation-results.json"
    markdown_path = output_dir / "VALIDATION_REPORT.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(build_markdown(report), encoding="utf-8")
    print(markdown_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
