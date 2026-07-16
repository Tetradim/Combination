from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping


class AssetClass(str, Enum):
    CRYPTO = "crypto"
    LISTED_FUTURES = "listed_futures"


class ExperimentMode(str, Enum):
    SHADOW = "shadow"
    PAPER = "paper"
    LIVE_GATED = "live_gated"


@dataclass(frozen=True)
class InstrumentRef:
    instrument_id: str
    asset_class: AssetClass
    venue: str
    symbol: str
    tick_size: Decimal | None = None
    multiplier: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.instrument_id.strip():
            raise ValueError("instrument_id is required")
        if not self.venue.strip():
            raise ValueError("venue is required")
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if self.tick_size is not None and self.tick_size <= 0:
            raise ValueError("tick_size must be positive")
        if self.multiplier is not None and self.multiplier <= 0:
            raise ValueError("multiplier must be positive")


@dataclass(frozen=True)
class ReadinessSnapshot:
    broker_connected: bool = False
    account_fresh: bool = False
    market_data_fresh: bool = False
    reconciled: bool = False
    kill_switch_clear: bool = False
    margin_available: bool = False
    live_activation_present: bool = False
    reasons: tuple[str, ...] = ()

    @property
    def live_ready(self) -> bool:
        return all(
            (
                self.broker_connected,
                self.account_fresh,
                self.market_data_fresh,
                self.reconciled,
                self.kill_switch_clear,
                self.margin_available,
                self.live_activation_present,
            )
        ) and not self.reasons


@dataclass(frozen=True)
class ExperimentEnvelope:
    experiment_id: str
    mode: ExperimentMode
    source_component: str
    target_component: str
    instrument: InstrumentRef
    payload: Mapping[str, Any] = field(default_factory=dict)
    readiness: ReadinessSnapshot | None = None

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id is required")
        if self.source_component not in {"chain", "iron", "combination"}:
            raise ValueError("unsupported source_component")
        if self.target_component not in {"chain", "iron", "combination"}:
            raise ValueError("unsupported target_component")

    @property
    def may_route_live(self) -> bool:
        return (
            self.mode is ExperimentMode.LIVE_GATED
            and self.readiness is not None
            and self.readiness.live_ready
        )
