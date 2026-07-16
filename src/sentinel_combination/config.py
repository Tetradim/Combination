from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import yaml

from sentinel_combination.application.risk import RiskLimits
from sentinel_combination.domain.enums import AssetClass
from sentinel_combination.domain.instruments import Instrument


@dataclass(frozen=True)
class BrokerConfig:
    adapter: str
    account_id: str
    environment: str = "live"
    enabled: bool = True
    credentials: Mapping[str, str] = field(default_factory=dict)
    settings: Mapping[str, Any] = field(default_factory=dict)

    def secret(self, name: str, *, required: bool = True) -> str | None:
        env_name = self.credentials.get(name)
        value = os.getenv(env_name, "") if env_name else ""
        if required and not value:
            raise ValueError(
                f"missing credential {name!r}; expected environment variable {env_name!r}"
            )
        return value or None


@dataclass(frozen=True)
class AppConfig:
    database_path: Path
    api_token_env: str
    activation_token_env: str
    brokers: Mapping[str, BrokerConfig]
    instruments: Mapping[str, Instrument]
    risk_limits: RiskLimits
    reconciliation_interval_seconds: float = 15.0
    update_poll_interval_seconds: float = 1.0

    @property
    def api_token(self) -> str:
        value = os.getenv(self.api_token_env, "")
        if not value:
            raise ValueError(f"missing API token in {self.api_token_env}")
        return value

    @property
    def activation_token(self) -> str:
        value = os.getenv(self.activation_token_env, "")
        if not value:
            raise ValueError(
                f"missing live activation token in {self.activation_token_env}"
            )
        return value


def _decimal(payload: Mapping[str, Any], key: str, default: str) -> Decimal:
    return Decimal(str(payload.get(key, default)))


def load_config(path: str | Path) -> AppConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    broker_items: dict[str, BrokerConfig] = {}
    for name, payload in (raw.get("brokers") or {}).items():
        broker_items[name] = BrokerConfig(
            adapter=str(payload["adapter"]),
            account_id=str(payload["account_id"]),
            environment=str(payload.get("environment", "live")),
            enabled=bool(payload.get("enabled", True)),
            credentials=dict(payload.get("credentials") or {}),
            settings=dict(payload.get("settings") or {}),
        )
    instruments: dict[str, Instrument] = {}
    for instrument_id, payload in (raw.get("instruments") or {}).items():
        instruments[instrument_id] = Instrument(
            instrument_id=instrument_id,
            asset_class=AssetClass(str(payload["asset_class"])),
            venue=str(payload["venue"]),
            symbol=str(payload["symbol"]),
            price_increment=_decimal(payload, "price_increment", "0.01"),
            quantity_increment=_decimal(payload, "quantity_increment", "1"),
            minimum_quantity=_decimal(payload, "minimum_quantity", "1"),
            minimum_notional=_decimal(payload, "minimum_notional", "0"),
            contract_multiplier=_decimal(payload, "contract_multiplier", "1"),
            settlement_currency=payload.get("settlement_currency"),
            expiry=payload.get("expiry"),
            first_notice_date=payload.get("first_notice_date"),
            last_trade_date=payload.get("last_trade_date"),
            last_safe_trade_date=payload.get("last_safe_trade_date"),
        )
    limits = raw.get("risk_limits") or {}
    risk_limits = RiskLimits(
        maximum_order_notional=_decimal(limits, "maximum_order_notional", "25000"),
        maximum_position_notional=_decimal(limits, "maximum_position_notional", "100000"),
        maximum_margin_fraction=_decimal(limits, "maximum_margin_fraction", "0.25"),
        maximum_daily_loss=_decimal(limits, "maximum_daily_loss", "1000"),
        maximum_spread_bps=_decimal(limits, "maximum_spread_bps", "25"),
    )
    return AppConfig(
        database_path=Path(raw.get("database_path", "data/combination.sqlite3")),
        api_token_env=str(raw.get("api_token_env", "COMBINATION_API_TOKEN")),
        activation_token_env=str(
            raw.get("activation_token_env", "COMBINATION_ACTIVATION_TOKEN")
        ),
        brokers=broker_items,
        instruments=instruments,
        risk_limits=risk_limits,
        reconciliation_interval_seconds=float(raw.get("reconciliation_interval_seconds", 15)),
        update_poll_interval_seconds=float(raw.get("update_poll_interval_seconds", 1)),
    )
