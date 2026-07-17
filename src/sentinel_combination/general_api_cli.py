from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .archive_general_api import ArchiveGeneralApiClient, GeneralApiConfigStore, GeneralApiDefaults


def run(command: str | None, config_file: str, args: Any) -> int:
    store = GeneralApiConfigStore(
        Path(config_file),
        GeneralApiDefaults(
            bot_id="sentinel-combination",
            display_name="Sentinel Combination",
            roles=("trader",),
        ),
    )
    client = ArchiveGeneralApiClient(store)
    try:
        if command == "show":
            payload: Any = {"settings": store.public(store.load()), "contract": "archive.general.v1"}
        elif command == "configure":
            patch: dict[str, Any] = {}
            for key in (
                "base_url",
                "run_id",
                "participant_id",
                "api_token",
                "timeout_seconds",
                "starting_cash",
                "commission_per_order",
                "slippage_bps",
            ):
                value = getattr(args, key, None)
                if value is not None:
                    patch[key] = value
            if getattr(args, "enabled", None) is not None:
                patch["enabled"] = args.enabled
            if getattr(args, "symbols", None) is not None:
                patch["subscribed_symbols"] = args.symbols.split(",")
            payload = {"settings": store.public(store.save(patch))}
        elif command == "test":
            payload = client.test_connection()
        elif command == "register":
            payload = client.register()
        elif command == "account":
            payload = client.account()
        else:
            print("Choose one of: show, configure, test, register, account", file=sys.stderr)
            return 2
    except Exception as exc:
        print(f"General API error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
