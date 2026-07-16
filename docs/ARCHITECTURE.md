# Combination Architecture

## Purpose

Combination is an integration laboratory, not a replacement for Sentinel Chain or Sentinel Iron. The original repositories remain the authoritative upstreams and can continue to evolve independently.

The superproject pins each upstream at an exact commit and adds only the smallest practical cross-project surface:

- source provenance and lock verification;
- a unified operator CLI;
- subprocess-isolated component launchers;
- neutral experiment contracts;
- a capability registry;
- integration tests and experiment documentation.

## Repository boundaries

### Sentinel Chain component

`components/sentinel-chain` remains responsible for:

- crypto signal normalization and intake;
- paper-first execution;
- risk sizing and signal risk checks;
- synthetic bracket state and amendments;
- staged targets and partial exits;
- trailing, break-even, and profit-lock behavior;
- paper position and PnL accounting;
- previews and backtests;
- FastAPI and operator UI workflows;
- crypto exchange capability previews.

Combination does not duplicate or monkey-patch those modules.

### Sentinel Iron component

`components/sentinel-iron` remains responsible for:

- listed-futures instrument definitions;
- broker ports and provider adapters;
- account, position, quote, and historical-data boundaries;
- order readiness, risk, submission, cancellation, and updates;
- broker-authoritative fill and lifecycle handling;
- processed-fill idempotency;
- internal/broker reconciliation;
- margin estimates and approved schedules;
- kill switch and emergency flattening;
- portfolio targets and phased rebalances;
- continuous futures, trend, carry, and composite calculations;
- immutable audit history.

Combination never bypasses Iron's readiness, margin, risk, reconciliation, activation, or operator-confirmation gates.

### Combination facade

`src/sentinel_combination` owns only integration concerns:

- locating and validating pinned components;
- exposing a combined capability inventory;
- launching a source component in an isolated subprocess;
- defining asset-class-neutral experiment envelopes;
- preventing an experiment from being described as live-ready unless all readiness fields are explicitly true.

The facade deliberately does not submit an order itself.

## Process isolation

Chain and Iron are launched in subprocesses with component-specific `PYTHONPATH` values. This is intentional:

1. Package globals and persistence configuration cannot leak accidentally.
2. A dependency upgrade in one component is easier to diagnose.
3. Crashes remain attributable to one component.
4. The facade cannot silently replace source classes at runtime.

A future in-process bridge should be introduced only for a small, stable protocol and only after replay and lifecycle invariants are defined.

## Source pinning

Three pieces must agree:

1. the gitlink SHA stored in the parent repository;
2. `combination.lock.json`;
3. `ComponentPin.commit` in `sentinel_combination.components`.

`combination doctor --strict` verifies the checked-out submodule HEADs against the expected pins.

## Integration direction

The safest sequence is:

1. **Observe:** run Chain and Iron independently and compare events.
2. **Shadow:** translate one component's intent into a non-executing envelope for the other.
3. **Paper:** let the target component apply its own native checks and paper behavior.
4. **Reconcile:** prove restart, duplicate-event, partial-fill, cancel, and reversal behavior.
5. **Live-gated:** permit only explicit operator-approved experiments that retain every source safety gate.

No step should replace broker or exchange truth with a synthetic assumption.
