from datetime import datetime, timezone

import pytest

from sentinel_combination.domain.readiness import ReadinessSnapshot


def snapshot(**overrides) -> ReadinessSnapshot:
    values = {
        "broker_connected": True,
        "authenticated": True,
        "account_fresh": True,
        "market_data_fresh": True,
        "positions_reconciled": True,
        "orders_reconciled": True,
        "kill_switch_clear": True,
        "persistence_healthy": True,
        "margin_available": True,
        "instrument_tradeable": True,
        "protective_order_supported": True,
        "activation_authorized": True,
        "evaluated_at": datetime.now(timezone.utc),
        "reasons": (),
    }
    values.update(overrides)
    return ReadinessSnapshot(**values)


def test_every_exposure_readiness_gate_is_required():
    assert snapshot().ready_for_exposure is True

    blocked = snapshot(
        margin_available=False,
        reasons=("margin unavailable",),
    )
    assert blocked.ready_for_exposure is False

    with pytest.raises(
        PermissionError,
        match="margin unavailable",
    ):
        blocked.assert_ready_for_exposure()
