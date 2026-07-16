# Experiment Guide

## Ground rules

1. Preserve both source repositories as authoritative upstreams.
2. Pin every experiment to exact Chain, Iron, and Combination commits.
3. Start in shadow mode.
4. Keep synthetic state separate from broker-authoritative state.
5. Never bypass Iron readiness, reconciliation, risk, margin, lifecycle, activation, or operator-confirmation gates.
6. Never present Chain paper fills as exchange or broker fills.
7. Record every translation decision and rejected mapping.
8. Require restart and duplicate-event tests before paper promotion.
9. Require paper reconciliation and cancel/fill race tests before any live-gated trial.

## Experiment 1: Chain bracket intent with Iron lifecycle discipline

**Question:** Can Chain's advanced bracket plan be represented as an Iron-managed order graph?

Shadow outputs should include:

- entry intent;
- protective and profit legs;
- quantity allocation;
- OCA relationships;
- activation state;
- expected broker order family;
- warnings for unsupported staged or synthetic behavior.

Do not submit orders. Compare the plan with Chain's own exchange-plan preview and Iron's lifecycle requirements.

## Experiment 2: Chain signal normalization with Iron readiness and risk

Translate a normalized Chain signal into a neutral `ExperimentEnvelope`, then construct Iron-native instrument, account, market, margin, and activity inputs.

Reject the translation when:

- the crypto symbol cannot map to a listed-futures contract;
- multiplier or tick rules are missing;
- margin is unavailable;
- account or market state is stale;
- positions are unreconciled;
- the contract is past its last safe trade date.

## Experiment 3: Iron instrument math in Chain previews

Use Iron's futures multiplier and tick information in an isolated copy of Chain's preview/backtest calculations.

Acceptance criteria:

- legacy crypto results remain byte-for-byte unchanged;
- futures PnL uses contract multiplier;
- every trigger and fill is tick aligned;
- partial quantities obey contract integer rules;
- replay produces the same final state.

## Experiment 4: Chain operator UI for Iron diagnostics

Expose read-only Iron data in a new Combination-owned UI route or panel:

- readiness;
- reconciliation;
- kill-switch state;
- working orders;
- lifecycle states;
- margin estimates;
- positions and contract dates.

Do not import these views into Chain upstream until the experiment proves useful.

## Experiment 5: Shared event journal

Define a Combination event envelope containing:

- event ID;
- source component;
- source commit;
- account and instrument scope;
- source timestamp and ingestion timestamp;
- event type;
- immutable payload hash;
- parent/causation ID.

Mirror source events without replacing either source persistence store. Test duplicates, out-of-order events, restarts, and partial writes.

## Promotion checklist

A feature may move from shadow to paper only when:

- all source tests pass;
- Combination tests pass;
- old Chain paper histories replay identically;
- Iron duplicate execution IDs remain idempotent;
- position and order invariants hold after restart;
- unsupported mappings fail closed;
- operator output identifies the source of truth.

A paper feature may become live-gated only after a separate design review and an explicit operator-controlled activation path.
