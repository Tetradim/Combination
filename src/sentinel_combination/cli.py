from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .brokers.catalog import FuturesProduct, get_broker_company, list_broker_companies
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
