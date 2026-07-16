from sentinel_combination.capabilities import CAPABILITIES, list_capabilities


def test_capability_ids_are_unique():
    identifiers = [capability.capability_id for capability in CAPABILITIES]
    assert len(identifiers) == len(set(identifiers))


def test_iron_inventory_contains_critical_execution_features():
    identifiers = {capability.capability_id for capability in list_capabilities("iron")}
    required = {
        "iron.safety.kill_switch",
        "iron.safety.cancel_sweep",
        "iron.readiness.trading",
        "iron.reconciliation.positions",
        "iron.ledger.fill_idempotency",
        "iron.planning.reversal_phases",
        "iron.margin.estimates",
        "iron.orders.submission",
        "iron.orders.cancellation",
        "iron.orders.stream_updates",
        "iron.safety.emergency_flatten",
        "iron.audit.immutable_jsonl",
    }
    assert required <= identifiers


def test_both_sources_and_combination_are_represented():
    owners = {capability.owner for capability in CAPABILITIES}
    assert owners == {"chain", "iron", "combination"}
