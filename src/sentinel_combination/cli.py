from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Sequence

from .capabilities import capability_dicts, list_capabilities, owners
from .components import COMPONENTS, doctor_report, load_lock
from .runtime import run_chain, run_iron, run_tests, verify_import


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="combination",
        description="Experimental integration facade for Sentinel Chain and Sentinel Iron.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Validate source pins, submodules, and imports.")
    doctor.add_argument("--strict", action="store_true", help="Return nonzero unless every pin and import is healthy.")
    doctor.add_argument("--json", action="store_true", dest="as_json")

    capabilities = subparsers.add_parser("capabilities", help="List imported and integration capabilities.")
    capabilities.add_argument("--owner", choices=("all", *owners()), default="all")
    capabilities.add_argument("--json", action="store_true", dest="as_json")

    pins = subparsers.add_parser("pins", help="Show the reproducible source lock.")
    pins.add_argument("--json", action="store_true", dest="as_json")

    chain = subparsers.add_parser("chain", help="Launch the pinned Sentinel Chain API/UI.")
    chain.add_argument("--host", default="127.0.0.1")
    chain.add_argument("--port", type=int, default=8004)
    chain.add_argument("--reload", action="store_true")
    chain.add_argument("extra", nargs=argparse.REMAINDER)

    iron = subparsers.add_parser("iron", help="Delegate to the pinned Sentinel Iron CLI.")
    iron.add_argument("args", nargs=argparse.REMAINDER)

    tests = subparsers.add_parser("test-all", help="Run Combination, Chain, and Iron test suites in order.")
    tests.add_argument(
        "--only",
        choices=("combination", "chain", "iron"),
        action="append",
        help="Limit testing to one or more components.",
    )
    return parser


def _doctor(*, strict: bool, as_json: bool) -> int:
    report = doctor_report()
    imports: dict[str, dict[str, object]] = {}
    for key, component in COMPONENTS.items():
        healthy, detail = verify_import(component)
        imports[key] = {"healthy": healthy, "detail": detail}
    report["imports"] = imports
    report["healthy"] = bool(report["healthy"]) and all(item["healthy"] for item in imports.values())
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"project: {report['project_root']}")
        for key, status in report["components"].items():
            import_status = imports[key]
            print(
                f"{key}: initialized={status['initialized']} pin_matches={status['pin_matches']} "
                f"import={import_status['healthy']} head={status['current_head'] or '-'}"
            )
            if not import_status["healthy"]:
                print(f"  import detail: {import_status['detail']}")
        print(f"healthy: {report['healthy']}")
    return 1 if strict and not report["healthy"] else 0


def _capabilities(*, owner: str, as_json: bool) -> int:
    selected = list_capabilities(owner)
    if as_json:
        print(json.dumps(capability_dicts(owner), indent=2, sort_keys=True))
        return 0
    counts = Counter(capability.category for capability in selected)
    print(f"capabilities: {len(selected)}")
    print("categories: " + ", ".join(f"{name}={count}" for name, count in sorted(counts.items())))
    for capability in selected:
        print(
            f"[{capability.owner}] {capability.capability_id} "
            f"({capability.maturity})\n  {capability.summary}\n  source: {capability.provenance}"
        )
    return 0


def _pins(*, as_json: bool) -> int:
    lock = load_lock()
    if as_json:
        print(json.dumps(lock, indent=2, sort_keys=True))
        return 0
    for name, payload in lock["components"].items():
        print(f"{name}: {payload['commit']}\n  {payload['repository']}\n  {payload['path']}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "doctor":
        return _doctor(strict=args.strict, as_json=args.as_json)
    if args.command == "capabilities":
        return _capabilities(owner=args.owner, as_json=args.as_json)
    if args.command == "pins":
        return _pins(as_json=args.as_json)
    if args.command == "chain":
        return run_chain(host=args.host, port=args.port, reload=args.reload, extra_args=args.extra)
    if args.command == "iron":
        return run_iron(args.args)
    if args.command == "test-all":
        return run_tests(args.only or ("combination", "chain", "iron"))
    raise AssertionError(f"unhandled command: {args.command}")
