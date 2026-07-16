#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHAIN = ROOT / "components" / "sentinel-chain"
IRON = ROOT / "components" / "sentinel-iron"


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def editable_spec(path: Path, extras: list[str]) -> str:
    suffix = f"[{','.join(extras)}]" if extras else ""
    return f"{path}{suffix}"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Bootstrap the Combination superproject.")
    result.add_argument("--dev", action="store_true", help="Install pytest and both component development extras.")
    result.add_argument("--exchange", action="store_true", help="Install Sentinel Chain's optional CCXT exchange extra.")
    result.add_argument("--ibkr", action="store_true", help="Install Sentinel Iron's optional IBKR extra.")
    result.add_argument("--no-submodules", action="store_true", help="Skip git submodule initialization.")
    result.add_argument("--no-pip-upgrade", action="store_true", help="Do not upgrade pip before installation.")
    result.add_argument("--python", default=sys.executable, help="Python interpreter used for installation.")
    return result


def main() -> int:
    args = parser().parse_args()
    python = args.python

    if not args.no_submodules:
        run(["git", "submodule", "update", "--init", "--recursive"])

    missing = [str(path) for path in (CHAIN, IRON) if not (path / "pyproject.toml").is_file()]
    if missing:
        raise SystemExit(
            "Component submodules are not initialized: "
            + ", ".join(missing)
            + ". Run git submodule update --init --recursive."
        )

    if not args.no_pip_upgrade:
        run([python, "-m", "pip", "install", "--upgrade", "pip"])

    root_extras = ["dev"] if args.dev else []
    chain_extras: list[str] = []
    iron_extras: list[str] = []
    if args.dev:
        chain_extras.append("dev")
        iron_extras.append("dev")
    if args.exchange:
        chain_extras.append("exchange")
    if args.ibkr:
        iron_extras.append("ibkr")

    for spec in (
        editable_spec(ROOT, root_extras),
        editable_spec(CHAIN, chain_extras),
        editable_spec(IRON, iron_extras),
    ):
        run([python, "-m", "pip", "install", "-e", spec])

    run([python, "-m", "sentinel_combination", "doctor", "--strict"])
    print("Combination bootstrap complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
