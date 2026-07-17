from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .brokers.catalog import FuturesProduct, get_broker_company, list_broker_companies
from .general_api_cli import run as run_general_api
from .storage.sqlite import SQLiteStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="combination",
        description=(
            "Live-only broker-authoritative "
            "Sentinel Combination backend."
        ),
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "version",
        help="Show the package version.",
    )

    init_db = subparsers.add_parser(
        "init-db",
        help="Initialize the durable local database.",
    )
    init_db.add_argument(
        "--path",
        required=True,
    )

    doctor = subparsers.add_parser(
        "doctor",
        help=(
            "Check the local durable store. "
            "Broker readiness is adapter-specific."
        ),
    )
    doctor.add_argument(
        "--path",
        required=True,
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
    )

    brokers = subparsers.add_parser(
        "brokers",
        help="List futures brokerages and crypto-futures companies in the catalog.",
    )
    brokers.add_argument(
        "--product",
        choices=("all", "listed_futures", "crypto_futures"),
        default="all",
    )
    brokers.add_argument("--json", action="store_true", dest="as_json")

    broker_info = subparsers.add_parser(
        "broker-info",
        help="Show one futures brokerage catalog entry.",
    )
    broker_info.add_argument("broker")
    broker_info.add_argument("--json", action="store_true", dest="as_json")

    general_api = subparsers.add_parser(
        "general-api",
        help="Configure Sentinel Archive's General API replay-broker connection.",
    )
    general_api.add_argument("--config-file", default="data/general_api.json")
    general_api_subparsers = general_api.add_subparsers(dest="general_api_command")
    general_api_subparsers.add_parser("show", help="Show redacted General API settings.")
    configure = general_api_subparsers.add_parser("configure", help="Update General API settings.")
    enabled = configure.add_mutually_exclusive_group()
    enabled.add_argument("--enable", action="store_true", dest="enabled")
    enabled.add_argument("--disable", action="store_false", dest="enabled")
    configure.set_defaults(enabled=None)
    configure.add_argument("--base-url")
    configure.add_argument("--run-id")
    configure.add_argument("--participant-id")
    configure.add_argument("--symbols", help="Comma-separated equity- and crypto-futures symbols.")
    configure.add_argument("--api-token", help="Archive participant token; stored in a mode-0600 file.")
    configure.add_argument("--timeout-seconds", type=float)
    configure.add_argument("--starting-cash", type=float)
    configure.add_argument("--commission-per-order", type=float)
    configure.add_argument("--slippage-bps", type=float)
    general_api_subparsers.add_parser("test", help="Test Archive reachability and authentication.")
    general_api_subparsers.add_parser("register", help="Register Combination with the replay run.")
    general_api_subparsers.add_parser("account", help="Read Combination's simulated account.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "version":
        print(__version__)
        return 0

    if args.command == "init-db":
        store = SQLiteStore(Path(args.path))
        store.initialize()
        print(f"initialized: {store.path}")
        return 0

    if args.command == "brokers":
        product = None if args.product == "all" else FuturesProduct(args.product)
        companies = list_broker_companies(product=product)
        payload = [
            {
                "broker_id": item.broker_id,
                "display_name": item.display_name,
                "products": [product.value for product in item.products],
                "default_adapter": item.default_adapter,
                "aliases": list(item.aliases),
            }
            for item in companies
        ]
        if args.as_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for item in payload:
                adapter = item["default_adapter"] or "configure transport_adapter"
                print(f"{item['broker_id']}: {item['display_name']} [{', '.join(item['products'])}] adapter={adapter}")
        return 0

    if args.command == "broker-info":
        company = get_broker_company(args.broker)
        payload = {
            "broker_id": company.broker_id,
            "display_name": company.display_name,
            "products": [product.value for product in company.products],
            "default_adapter": company.default_adapter,
            "aliases": list(company.aliases),
        }
        if args.as_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for key, value in payload.items():
                print(f"{key}: {value}")
        return 0

    if args.command == "general-api":
        return run_general_api(args.general_api_command, args.config_file, args)

    if args.command == "doctor":
        store = SQLiteStore(Path(args.path))
        healthy = store.healthcheck()
        payload = {
            "database_path": str(store.path),
            "database_healthy": healthy,
            "runtime_execution_paths": [
                "broker_or_exchange_account"
            ],
            "internal_fake_execution": False,
        }
        if args.as_json:
            print(
                json.dumps(
                    payload,
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            for key, value in payload.items():
                print(f"{key}: {value}")
        return 0 if healthy else 1

    raise AssertionError(
        f"unhandled command: {args.command}"
    )
