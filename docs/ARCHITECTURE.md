# Sentinel Combination Architecture

Sentinel Combination is an independent live-only backend.

```text
Signal or strategy intent
        ↓
Canonical validation
        ↓
Readiness gateway
        ↓
Instrument, account, margin, and portfolio risk
        ↓
Order gateway
        ↓
Broker or exchange adapter
        ↓
Acknowledgements, fills, rejects, cancels, expirations
        ↓
Idempotent lifecycle processor
        ↓
Position ledger and bracket coordinator
        ↓
Reconciliation and operator state
```

## Source of truth

- The venue is authoritative for orders and positions.
- Confirmed fills are authoritative for position changes.
- The local event journal is authoritative for what Combination processed.
- Reconciliation resolves differences. The system does not guess.

## Execution path

There is one runtime execution path: a connected broker or exchange account. Broker-provided sandbox credentials use the same path.

## Package boundaries

- `domain`: immutable financial and lifecycle concepts.
- `application`: use cases and state transitions.
- `ports`: broker and external service contracts.
- `storage`: durable implementations.
- `adapters`: certified venue integrations added later.
- `api`: authenticated operator interface added later.
- `discord`: authenticated alert and command surface added later.

## Safety rule

No signal, UI request, bracket trigger, or strategy decision directly changes a position. Only a confirmed broker/exchange fill processed atomically by the lifecycle pipeline changes the position ledger.
