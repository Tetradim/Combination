# Sentinel Combination — Live-Only Unified Backend Build Plan

**Status:** authoritative development plan  
**Repository:** `Tetradim/Combination`  
**Implementation branch:** `build/live-only-unified-core`  
**Execution policy:** one broker/exchange-connected path only

## 1. Purpose and product identity

Sentinel Combination is a new third trading system derived from the strongest parts of Sentinel Chain and Sentinel Iron. It is not a launcher, facade, submodule collection, compatibility shell, or process coordinator around the two source bots.

The finished system will be one independently evolving backend with one canonical domain model, one immutable event journal, one broker/exchange order lifecycle, one fill-authoritative position ledger, one readiness gateway, one reconciliation system, one margin and risk gateway, one bracket coordinator, one instrument catalog, one API and operator interface, one Discord alert and command surface, and one adapter contract for every venue.

Sentinel Chain and Sentinel Iron remain independent source projects. Combination selectively ports, rewrites, and reconciles their strongest concepts without requiring either source repository at runtime.

## 2. Live-only execution policy

Combination will contain no deployable internal fake exchange, synthetic fill engine, separate paper execution engine, shadow order router, demonstration trading backend, or hypothetical runtime order mode.

The only supported runtime execution path is:

1. connect through a brokerage or exchange adapter;
2. authenticate a specific account;
3. retrieve authoritative account, position, working-order, market, and margin state;
4. complete readiness and reconciliation;
5. evaluate instrument, strategy, account, margin, portfolio, and operational risk;
6. submit an API order to the connected account;
7. consume authoritative acknowledgements, fills, rejections, cancellations, expirations, and replacements;
8. update the durable lifecycle and position ledger from those external facts;
9. reconcile local state against the venue continuously and after restart.

A broker-provided sandbox, test account, or paper account is permitted only because it uses the broker's real API, real lifecycle messages, and real account state. Combination does not contain a second implementation for those accounts. The same adapter, database, order gateway, lifecycle processor, bracket coordinator, and reconciliation path are used for sandboxed and funded credentials.

Unit and integration tests may use isolated test doubles to verify state transitions and failure behavior. Those doubles are not deployable adapters and do not create a runtime trading mode.

## 3. Non-negotiable hierarchy

The architecture follows this hierarchy:

1. broker or exchange truth;
2. durable order lifecycle and execution-ID idempotency;
3. fill-authoritative position accounting;
4. readiness, reconciliation, margin, and operational safety;
5. bracket and strategy intelligence;
6. signals, Discord, API, and operator UI.

No signal, strategy, bracket trigger, scheduled action, API request, or UI command may directly change a position. Only a confirmed fill may change the position ledger.

No submitted order may be displayed or persisted as filled before a broker/exchange fill update is processed. No cancel request may be treated as a canceled order before authoritative confirmation. No unknown submission outcome may be guessed as rejected or retried automatically; it enters `reconciliation_required`.

## 4. Features selected from Sentinel Chain

### Signal intake and normalization

Keep JSON webhooks, TradingView-style alerts, flexible text parsing, Discord commands, aliases for symbols/sides/stops/targets/trailing rules, and signal idempotency.

Change the boundary so flexible aliases end at source-specific parsers. Every accepted message becomes a strict canonical command. No loose dictionary reaches risk, lifecycle, or an adapter, and no webhook can bypass readiness or account risk.

### Versioned bracket plans

Keep fixed protection, staged TP1/TP2/runner targets, partial close fractions, partial trailing reductions, activation-gated trailing, target-gated trailing, ratchet steps, break-even, net-cost break-even, profit locks, target-specific post-fill actions, time/session exits, OCA relationships, long/short symmetry, tighten-only protection, and farther-only target amendments.

Split bracket intent and state. `BracketPlan` is immutable, schema-versioned, and semantics-versioned. `BracketState` tracks management progress. The position ledger owns economic exposure; the lifecycle owns order truth. Exit quantities are calculated from confirmed entry fills, never requested quantity.

Leave behind the internal paper exchange, synthetic fills as truth, immediate live netting, mark-count holding periods, candle-path execution, direct lot mutation, assumed cancellation, and exits created for unfilled entry quantity.

### Advanced trade management

Retain staged profit-taking, runner management, delayed trailing, stepped ratchets, post-target protection, residual exposure checks, and bracket coverage diagnostics.

Every open position must have durable venue-resident catastrophic protection whenever the route supports it. Application-managed trailing may supplement protection but should not be the only protection if a network or process failure would leave exposure unmanaged.

### Operator experience

Use Chain's operator-centered approach later, expanded with account/market freshness, reconciliation, kill switch, margin, liquidation distance, lifecycle timelines, pending cancel, bracket graph, native-versus-application protection, adapter heartbeat, database health, and unresolved incidents.

## 5. Features selected from Sentinel Iron

### Order lifecycle

Use the authoritative states: planned, risk approved, submitting, submitted, acknowledged, working, partially filled, pending cancel, canceled, filled, rejected, expired, and reconciliation required.

Add parent-child relationships, bracket IDs, OCA group IDs, replacement chains, broker ID consistency, adapter sequence tracking, unknown outcome handling, and invariants after every update.

### Execution-ID idempotency

Every external event receives a durable uniqueness key `(source, external_event_id)`. Every fill also requires a broker/exchange execution ID. Duplicates do not change lifecycle, position, fees, P&L, bracket state, or downstream commands. The database enforces uniqueness.

### Position ledger

Keep signed fill quantities, weighted average additions, reductions without average reset, side flips, fees, realized P&L, and reconciliation. Extend with strategy/bracket attribution, funding/borrow cost, margin allocation, and external/manual position classification.

The invariant is: authoritative account position equals internal managed lots plus classified external exposure. Unattributed exposure blocks new trading until reconciled.

### Readiness

Exposure-increasing orders require connected and authenticated adapters, fresh account and market state, reconciled positions and orders, clear kill switch, healthy persistence and event journal, available margin, tradeable instruments, durable protection support, explicit account/strategy/instrument authorization, and activation authorization.

Risk-reducing actions may remain available during selected degraded conditions, but they still require authenticated connectivity and durable persistence.

### Reconciliation

Include venue/internal positions, working orders, broker ID mapping, bracket children, cancel/replace chains, sequence gaps, external/manual orders, startup checks, unknown submission recovery, and reconnect checks.

### Kill switch and emergency controls

Use three levels: pause entries, cancel working, and flatten-and-halt. Flatten-and-halt blocks commands, snapshots venue state, cancels obsolete non-protective orders, submits reduce-only flatten orders, waits for fills, cancels obsolete protection, reconciles, and remains halted until operator clearance. Submitted flatten orders do not prove the account is flat.

### Instruments and margin

Generalize Iron's tick, multiplier, settlement, exchange, expiry, first-notice, last-trade, and last-safe-trade rules into one model for crypto spot, crypto perpetuals, and listed futures. Add quantity increment, minimum quantity/notional, settlement currency, margin mode, funding interval, and liquidation information.

Keep authoritative initial/maintenance margin and buying-power checks. For crypto derivatives add isolated/cross mode, position/order margin, margin ratio, liquidation price/distance, and timestamped calculation source. Never invent a default maintenance margin or liquidation model.

### Reversals and targets

Use confirmed flatten-then-open phases for reversals. Cancel obsolete exits, flatten reduce-only, wait for fills, reconcile flat, refresh state, rerun readiness/risk/margin, then open the new side and protect actual fills.

Support both `TradeIntent` and `PositionTarget` as strategy outputs, with both flowing through the same lifecycle and risk system.

## 6. Features deliberately excluded

Combination excludes Chain's internal paper exchange, any simulated fill runtime, any shadow router, candle-path order execution, mark-count exits, separate fake-money accounting, futures-only assumptions in generic services, JSON files as the principal funded database, automatic retry after unknown outcome, unverified adapters described as ready, invented margin defaults, silent repair, strategy logic in adapters, and Discord as a source of truth.

## 7. Canonical domain model

Core entities are Account, Instrument, StrategyIntent, TradeIntent, PositionTarget, BracketPlan, BracketState, OrderIntent, OrderLifecycle, BrokerOrderUpdate, Fill, Position, StrategyLot, MarginSnapshot, ReadinessSnapshot, RiskDecision, and EventEnvelope.

Plan describes intention; lifecycle describes order truth; position describes economic exposure; bracket state describes management progress; the event journal describes immutable history.

## 8. Atomic processing

Processing an external update is one database transaction: claim event ID, verify identity, load lifecycle, validate transition, update fills and average price, update position and fees, update bracket state, persist state, append events, and commit. If any step fails, none of the mutations commit.

## 9. Risk layers

Signal validity covers canonical scope, bracket coherence, directional validity, and schema versions. Strategy risk covers trade risk, stop width, reward/risk, allocation, drawdown, losses, and holding restrictions. Instrument/order risk covers precision, minimums, spread, collar, rate, IDs, and reduce-only validity. Account/margin risk covers equity, buying power, initial/maintenance margin, liquidation distance, margin mode, open-order margin, and daily loss. Portfolio risk covers gross/net exposure, concentration, correlation, aggregate stop risk, and stress loss. Operational risk covers database health, heartbeats, sequence gaps, clock drift, stale data, rejects, cancel failures, unresolved reconciliation, and unknown states. The strictest rejection wins.

## 10. Bracket coordinator

The complete coordinator will support actual-fill exit sizing, durable catastrophic stops, staged targets, partial target fills, partial trailing, activation gates, ratchet steps, target-specific actions, net-cost break-even, profit locks, tighten-only cancel/replace, OCA, residual checks, native order mapping, and application-managed state where native behavior is insufficient. Broker-native OCO is preferred only after adapter semantics are proven; capability flags alone are not certification.

## 11. Storage

Initial deployment uses SQLite in WAL mode with full synchronous durability for one process. Initial tables cover metadata, immutable events, processed external events, lifecycle records, positions, and kill switch. Planned tables add bracket plans/state, strategy lots, margin snapshots, readiness, reconciliation incidents, operator commands, and adapter checkpoints.

PostgreSQL is required before multiple active processes, remote workers, high availability, replicated failover, or high event throughput. Domain and application services remain storage-independent.

## 12. Adapter certification

An adapter is not funded-certified until it passes connection/authentication, account/market snapshots, positions, working orders, margin, submit/reject, acknowledgment, working, partial/full fill, cancellation, cancel/fill races, async reject, expiry, restart recovery, execution-ID deduplication, broker ID consistency, position/order reconciliation, unknown outcome recovery, and emergency flatten.

The first targets should be one crypto derivatives venue and one listed-futures broker. Other adapters remain disabled until separately certified.

## 13. API, Discord, and UI

Add these after lifecycle, persistence, reconciliation, and risk are stable. Every state change requires authentication, authorization, account/strategy scope, idempotency key, durable command event, dangerous-action confirmation, and complete audit data. Discord is an alert/command surface, never authoritative storage.

## 14. Testing policy

The application exposes no fake exchange or simulated runtime. Tests may use non-deployable test doubles for lifecycle transitions, terminal immutability, duplicates, partial fills, cancel races, side flips, fees, actual-fill bracket sizing, readiness, margin rejection, unknown outcomes, rollback, restart, reconciliation, and emergency sequencing. Real adapters also receive contract tests against the broker's own sandbox/test account through the same production adapter path.

## 15. Delivery phases

1. **Independent live core:** remove submodule runtime; implement instruments, orders, lifecycle, brackets, readiness, risk, events, positions, SQLite, idempotency, broker port, and gateway.
2. **Reconciliation and emergency safety:** account/market freshness, position/order reconciliation, unknown-outcome recovery, kill switch, cancel sweep, emergency flatten, sequence checkpoints.
3. **Complete bracket coordination:** persistence, staged state, trailing, partial-fill resizing, native OCO, replace chains, post-fill actions, net-cost protection, coverage diagnostics.
4. **First adapters:** one crypto derivatives adapter and one futures broker, including streaming, margin, market data, and certification.
5. **Strategy ingress and portfolio:** JSON/TradingView, strict text, Discord, trade intents, position targets, strategy and portfolio risk.
6. **Operator system:** FastAPI, authentication, UI, lifecycle/bracket visualization, incidents, audit export, and runbooks.
7. **Restricted funded activation:** restart/fault verification, adapter certification, allowlists, capital/order/loss limits, emergency verification, explicit activation.

## 16. Definition of complete

Combination is ready for restricted funded deployment only when it runs without Chain or Iron; no deployable fake execution exists; every position mutation comes from a confirmed fill; duplicate events cannot mutate twice; unknown outcomes force reconciliation; restarts reconstruct equivalent state; partial fills/cancel races work; bracket protection uses confirmed quantity; exposure has verified durable protection; readiness/reconciliation/margin/risk cannot be bypassed; kill switch and emergency flatten pass adapter tests; at least one adapter is certified; activation is scoped and reversible; the database/journal are recoverable; and account, strategy, instrument, and capital limits are explicitly authorized.

This plan prioritizes external truth, recoverability, and controlled failure over demonstrations, fake-money features, convenience modes, or optimistic automation.
