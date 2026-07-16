from decimal import Decimal

import pytest

from sentinel_combination.contracts import (
    AssetClass,
    ExperimentEnvelope,
    ExperimentMode,
    InstrumentRef,
    ReadinessSnapshot,
)


def instrument() -> InstrumentRef:
    return InstrumentRef(
        instrument_id="CME:ES:2026-09",
        asset_class=AssetClass.LISTED_FUTURES,
        venue="CME",
        symbol="ESU6",
        tick_size=Decimal("0.25"),
        multiplier=Decimal("50"),
    )


def test_live_mode_requires_every_readiness_gate():
    not_ready = ExperimentEnvelope(
        experiment_id="shadow-live-check",
        mode=ExperimentMode.LIVE_GATED,
        source_component="chain",
        target_component="iron",
        instrument=instrument(),
        readiness=ReadinessSnapshot(
            broker_connected=True,
            account_fresh=True,
            market_data_fresh=True,
            reconciled=True,
            kill_switch_clear=True,
            margin_available=False,
            live_activation_present=True,
        ),
    )
    assert not_ready.may_route_live is False

    ready = ExperimentEnvelope(
        experiment_id="fully-gated-check",
        mode=ExperimentMode.LIVE_GATED,
        source_component="chain",
        target_component="iron",
        instrument=instrument(),
        readiness=ReadinessSnapshot(
            broker_connected=True,
            account_fresh=True,
            market_data_fresh=True,
            reconciled=True,
            kill_switch_clear=True,
            margin_available=True,
            live_activation_present=True,
        ),
    )
    assert ready.may_route_live is True


def test_shadow_and_paper_modes_never_report_live_routing():
    for mode in (ExperimentMode.SHADOW, ExperimentMode.PAPER):
        envelope = ExperimentEnvelope(
            experiment_id=f"mode-{mode.value}",
            mode=mode,
            source_component="chain",
            target_component="iron",
            instrument=instrument(),
            readiness=ReadinessSnapshot(
                broker_connected=True,
                account_fresh=True,
                market_data_fresh=True,
                reconciled=True,
                kill_switch_clear=True,
                margin_available=True,
                live_activation_present=True,
            ),
        )
        assert envelope.may_route_live is False


def test_instrument_rejects_nonpositive_tick_size():
    with pytest.raises(ValueError, match="tick_size"):
        InstrumentRef(
            instrument_id="bad",
            asset_class=AssetClass.LISTED_FUTURES,
            venue="CME",
            symbol="ES",
            tick_size=Decimal("0"),
        )
