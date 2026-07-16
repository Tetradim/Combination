# Sentinel Combination — Live-Only Unified Backend Build Plan

**Status:** authoritative development plan  
**Repository:** `Tetradim/Combination`  
**Implementation branch:** `build/live-only-unified-core`  
**Execution policy:** one broker/exchange-connected path only

## 1. Purpose and product identity

Sentinel Combination is a new third trading system derived from the strongest parts of Sentinel Chain and Sentinel Iron. It is not a launcher, facade, submodule collection, compatibility shell, or process coordinator around the two source bots.

The finished system will be one independently evolving backend with:

- one canonical domain model;
- one immutable event journal;
- one broker/exchange order lifecycle;
- one fill-authoritative position ledger;
- one readiness gateway;
- one reconciliation system;
- one margin and risk gateway;
- one bracket coordinator;
- one instrument catalog;
- one API and operator interface;
- one Discord alert and command surface;
- one adapter contract for every venue.

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

1. **Broker or exchange truth**
2. **Durable order lifecycle and execution-ID idempotency**
3. **Fill-authoritative position accounting**
4. **Readiness, reconciliation, margin, and operational safety**
5. **Bracket and strategy intelligence**
6. **Signals, Discord, API, and operator UI**

No signal, strategy, bracket trigger, scheduled action, API request, or UI command may directly change a position. Only a confirmed fill may change the position ledger.

No submitted order may be displayed or persisted as filled before a broker/exchange fill update is processed.

No cancel request may be treated as a canceled order before authoritative confirmation.

No unknown submission outcome may be guessed as rejected or retried automatically. It enters `reconciliation_required`.

## 4. Features selected from Sentinel Chain

### 4.1 Signal intake and normalization

Keep and adapt:

- JSON webhook intake;
- TradingView-style alerts;
- flexible text parsing;
- Discord-originated commands;
- aliases for symbols, sides, stops, targets, trailing rules, quantities, and strategy identifiers;
- signal fingerprints and idempotency keys.

Change:

- flexible aliases exist only in source-specific ingress parsers;
- every accepted message becomes a strict canonical command;
- no loosely structured dictionary reaches risk, lifecycle, or adapters;
- external source terminology never dictates venue-specific order behavior;
- all timestamps, IDs, quantities, and prices are normalized before the application layer.

Leave behind:

- aliases scattered through the backend;
- free-form internal order states;
- treating a webhook as authorization to bypass readiness or account risk;
- treating missing fields as harmless defaults when real exposure is possible.

### 4.2 Versioned bracket plans

Keep and promote:

- fixed protective stops;
- absolute and percentage-derived protective prices;
- staged TP1, TP2, and runner targets;
- per-target close fractions;
- partial trailing reductions;
- percentage and fixed-amount trailing distances;
- activation-gated trailing;
- trailing activated after a target fills;
- minimum ratchet steps;
- price-triggered break-even;
- post-target break-even;
- profit locks;
- target-specific post-fill actions;
- time or session exit intent;
- OCA relationships;
- long and short symmetry;
- tighten-only protective amendments;
- farther-into-profit target amendments.

Change:

The bracket becomes two separate structures:

- `BracketPlan`: immutable strategy intent, schema-versioned and semantics-versioned;
- `BracketState`: mutable management progress driven by fills and broker acknowledgements.

A bracket does not own the economic position. The position ledger does.

A bracket does not declare an order filled. The lifecycle does.

Every exit quantity is calculated from confirmed entry fills, not requested entry quantity.

Every bracket command flows through the normal readiness/risk/order lifecycle path. Reduce-only orders receive a narrower readiness policy, but they still require an authenticated connection and healthy persistence.

Leave behind:

- a mutable signal object doubling as execution state;
- synthetic triggers being treated as executions;
- direct lot quantity mutation;
- cancellation being assumed successful;
- exit orders created for unfilled entry quantity;
- runtime candle-path execution;
- mark-count holding periods.

### 4.3 Advanced trade management

Keep and adapt:

- staged profit-taking;
- partial runner management;
- delayed trailing activation;
- stepped ratchets;
- post-target protection changes;
- net-cost break-even;
- profit locking;
- protective priority;
- residual exposure checks;
- bracket coverage diagnostics.

New safety rule:

Every open position must have durable venue-resident catastrophic protection whenever the adapter and venue support it. Application-managed trailing or staged exits may supplement that order, but they should not be the only protection if an application or network failure could leave the account exposed.

A route that cannot provide durable protection for a strategy requiring unattended synthetic supervision is not certified for unattended funded use.

### 4.4 Operator experience

Use Chain's operator-centered approach as the visual foundation, later expanded with:

- connection and authentication status;
- account freshness;
- market freshness;
- position reconciliation;
- working-order reconciliation;
- kill-switch state;
- margin and buying power;
- maintenance margin;
- liquidation distance;
- lifecycle timelines;
- partial-fill progress;
- pending cancel status;
- bracket graph;
- native versus application-managed protection;
- adapter heartbeat;
- database health;
- last processed external sequence;
- unresolved reconciliation incidents.

Leave behind:

- optimistic UI status;
- state-changing UI actions without durable command events;
- generic "connected" badges that ignore stale account or order state.

## 5. Features selected from Sentinel Iron

### 5.1 Order lifecycle

Keep as the authoritative core:

- planned;
- risk approved;
- submitting;
- submitted;
- acknowledged;
- working;
- partially filled;
- pending cancel;
- canceled;
- filled;
- rejected;
- expired;
- reconciliation required.

Strengthen with:

- parent-child order relationships;
- bracket IDs;
- OCA group IDs;
- replacement chains;
- broker order ID consistency;
- adapter sequence tracking;
- explicit unknown-outcome state;
- lifecycle invariants enforced after every update.

### 5.2 Execution-ID idempotency

Keep and generalize.

Every external event receives a durable uniqueness key:

`(source, external_event_id)`

Every fill also requires a broker/exchange execution ID.

A duplicate event:

- is recorded as observed if diagnostics require it;
- does not change lifecycle;
- does not change position;
- does not change fees or P&L;
- does not advance bracket state;
- does not generate downstream orders.

The database enforces uniqueness. In-memory checks are not sufficient.

### 5.3 Fill-authoritative position ledger

Keep:

- signed fill quantities;
- weighted average additions;
- reductions without resetting average entry;
- side-flip handling;
- fees;
- realized P&L;
- broker/exchange reconciliation.

Extend with:

- strategy and bracket attribution;
- gross and net P&L;
- funding and borrow cost;
- margin allocation;
- external/manual position classification;
- account-level and strategy-level exposure views.

The invariant is:

`authoritative account position == internal managed lots + classified external exposure`

Unattributed exposure enters reconciliation and cannot be silently assigned to a strategy.

### 5.4 Readiness gating

Keep and expand.

Exposure-increasing orders require:

- adapter connected;
- authenticated;
- account snapshot fresh;
- market snapshot fresh;
- positions reconciled;
- working orders reconciled;
- kill switch clear;
- database healthy;
- event journal healthy;
- margin available;
- instrument tradeable;
- durable protection capability available;
- account authorized;
- strategy authorized;
- instrument authorized;
- explicit activation token or equivalent authorization.

Risk-reducing actions may remain available during selected degraded conditions, but they still require authenticated connectivity and durable local state.

### 5.5 Reconciliation

Keep:

- internal versus venue positions;
- quantity mismatches;
- venue positions missing locally;
- internal positions missing at venue.

Add:

- working-order reconciliation;
- broker-order-ID mapping;
- bracket child-order reconciliation;
- cancel/replace chain reconciliation;
- execution sequence gaps;
- external/manual order classification;
- startup reconciliation before new exposure;
- forced reconciliation after unknown submission outcome;
- forced reconciliation after stream reconnect.

### 5.6 Kill switch and emergency controls

Keep the persistent operator kill switch and cancel sweep.

Use three levels:

#### Pause entries

- block new exposure;
- continue managing current protective orders.

#### Cancel working

- block entries;
- cancel exposure-increasing orders;
- cancel profit orders according to policy;
- preserve catastrophic protection unless flattening is underway.

#### Flatten and halt

1. block new commands;
2. snapshot venue state;
3. cancel obsolete non-protective orders;
4. submit reduce-only flatten orders;
5. wait for confirmed fills;
6. cancel obsolete protective orders;
7. reconcile orders and positions;
8. remain halted until explicit operator clearance.

The system may not declare an account flat based on submitted flatten orders alone.

### 5.7 Instrument and futures rules

Keep:

- tick size;
- contract multiplier;
- settlement;
- exchange;
- contract month;
- first notice;
- last trade;
- last safe trade.

Generalize into one instrument model for:

- crypto spot;
- crypto perpetuals;
- listed futures.

Add:

- quantity increment;
- minimum quantity;
- minimum notional;
- settlement currency;
- margin mode;
- funding interval;
- expiry;
- inverse-contract metadata when later implemented.

No generic service may assume quantity is always integer, always freely divisible, or that notional is always simply price multiplied by quantity without a contract multiplier.

### 5.8 Margin

Keep:

- broker/API-derived initial margin;
- maintenance margin;
- buying-power checks;
- expiring operator-supplied schedules only when an authoritative preview is unavailable;
- fail-closed behavior for missing or stale margin.

Extend for crypto derivatives:

- isolated versus cross margin;
- position margin;
- order margin;
- account margin ratio;
- estimated liquidation price;
- liquidation distance;
- strategy margin allocation;
- calculation source and timestamp.

Combination must never invent a default maintenance margin or liquidation model.

### 5.9 Phase-based reversals

Use as the only funded execution behavior:

1. cancel obsolete exits;
2. submit reduce-only flatten order;
3. wait for confirmed fills;
4. reconcile flat state;
5. refresh account, market, and margin snapshots;
6. re-run readiness and risk;
7. submit the new direction;
8. create protection from actual fills.

No immediate in-memory netting is used as funded execution truth.

### 5.10 Portfolio targets

Keep as an optional strategy output type.

Combination supports:

- `TradeIntent`: a defined entry with bracket management;
- `PositionTarget`: move an account/instrument toward a target quantity.

Both produce canonical order intents and flow through the same lifecycle, risk, margin, and reconciliation systems.

Trend, carry, or other specific strategies remain plugins, not execution-core dependencies.

## 6. Features deliberately excluded

The new bot excludes:

- Chain's internal paper exchange;
- any simulated fill engine;
- any runtime shadow router;
- hypothetical price-path execution;
- candle-path order execution;
- mark-count exits;
- separate fake-money accounting;
- Iron's futures-only assumptions in generic services;
- multiple JSON files as the principal funded database;
- automatic retry after an unknown submission outcome;
- unverified adapters presented as funded-ready;
- invented margin defaults;
- silent state repair;
- strategy logic embedded in broker adapters;
- Discord as a source of truth.

Historical market analytics may be added for strategy research, but they do not become an alternate order execution engine inside this backend.

## 7. Canonical domain model

Core entities:

- `Account`
- `Instrument`
- `StrategyIntent`
- `TradeIntent`
- `PositionTarget`
- `BracketPlan`
- `BracketState`
- `OrderIntent`
- `OrderLifecycle`
- `BrokerOrderUpdate`
- `Fill`
- `Position`
- `StrategyLot`
- `MarginSnapshot`
- `ReadinessSnapshot`
- `RiskDecision`
- `EventEnvelope`

Critical separation:

- plan describes intention;
- lifecycle describes order truth;
- position describes economic exposure;
- bracket state describes management progress;
- event journal describes immutable history.

## 8. Atomic event processing

Processing a fill is one database transaction:

1. claim the external event ID;
2. verify source/account/instrument/order identity;
3. load lifecycle;
4. validate transition;
5. update fill quantity and average fill price;
6. update position and fees;
7. update strategy lot and bracket progress;
8. persist all new state;
9. append derived events;
10. commit.

If any step fails, none of the mutations commit.

## 9. Risk layers

### Signal validity

- strict side and instrument;
- coherent target allocations;
- directionally valid stops and targets;
- valid schema and semantics versions;
- required strategy and account scope.

### Strategy risk

- per-trade risk;
- stop width;
- reward/risk;
- strategy allocation;
- strategy daily loss;
- strategy drawdown;
- consecutive loss policy;
- holding/session restrictions.

### Instrument and order risk

- tick alignment;
- quantity increment;
- minimum quantity;
- minimum notional;
- spread;
- price collar;
- order rate;
- duplicate client order ID;
- reduce-only validity.

### Account and margin risk

- equity;
- buying power;
- initial margin;
- maintenance margin;
- margin fraction;
- liquidation distance;
- isolated/cross mode;
- open-order margin;
- account daily loss.

### Portfolio risk

- gross exposure;
- net exposure;
- instrument concentration;
- venue concentration;
- strategy concentration;
- correlated exposure;
- aggregate stop risk;
- stress loss.

### Operational risk

- database health;
- adapter heartbeat;
- stream sequence gaps;
- clock drift;
- stale data;
- repeated rejection;
- cancellation failure;
- unresolved reconciliation;
- unknown order state.

The strictest applicable rejection wins.

## 10. Bracket coordinator behavior

The complete coordinator will support:

- actual-fill-based exit sizing;
- durable catastrophic stop;
- staged targets;
- partial target fills;
- partial trailing reductions;
- activation gates;
- ratchet steps;
- target-specific actions;
- net-cost break-even;
- profit locks;
- tighten-only cancel/replace;
- OCA relationships;
- residual exposure checks;
- native order mapping;
- application-managed state where native behavior is insufficient.

Broker-native OCO or attached orders are preferred only after the adapter proves their semantics. Capability flags alone do not constitute certification.

## 11. Storage

### Initial implementation

SQLite in WAL mode with full synchronous durability for a single-process deployment.

Initial tables:

- metadata;
- immutable events;
- processed external events;
- order lifecycles;
- positions;
- kill switch.

Planned tables:

- bracket plans;
- bracket state;
- strategy lots;
- margin snapshots;
- readiness results;
- reconciliation incidents;
- operator commands;
- adapter checkpoints.

### Production expansion

PostgreSQL is required before:

- multiple active application processes;
- remote workers;
- high availability;
- replicated failover;
- high event throughput.

The domain and application layers remain independent of the database implementation.

## 12. Adapter contract and certification

An adapter is not funded-trading certified until it passes:

- connection and authentication;
- account snapshot;
- market snapshot;
- positions;
- working orders;
- margin preview or approved authoritative source;
- submit;
- synchronous rejection;
- acknowledgement;
- working status;
- partial fill;
- full fill;
- cancellation;
- cancel/fill race;
- asynchronous rejection;
- expiry;
- restart recovery;
- execution-ID deduplication;
- broker order-ID consistency;
- position reconciliation;
- working-order reconciliation;
- unknown submission outcome recovery;
- emergency flatten.

The first targets should be one crypto derivatives venue and one listed-futures broker. Other adapters remain disabled until separately certified.

## 13. API, Discord, and operator UI

These are added after lifecycle, persistence, reconciliation, and risk are stable.

Every state-changing request requires:

- authentication;
- authorization;
- account scope;
- strategy scope;
- idempotency key;
- durable command event;
- explicit confirmation for dangerous actions;
- complete audit information.

The UI will show external truth and local processing truth separately where they have not yet reconciled.

Discord will provide alerts and permissioned commands. It will not hold authoritative state.

## 14. Testing policy

The application exposes no fake exchange or simulation runtime.

The test suite still uses isolated, non-deployable test doubles to verify:

- lifecycle transitions;
- terminal-state immutability;
- duplicate execution IDs;
- partial fills;
- cancel/fill races;
- side flips;
- fee accounting;
- actual-fill-based bracket quantities;
- readiness blocks;
- margin rejection;
- unknown outcome;
- database rollback;
- restart state;
- reconciliation incidents;
- emergency sequencing.

Every real adapter also receives contract tests against the broker's available sandbox or test account using the same adapter path intended for funded credentials.

## 15. Delivery phases

### Phase 1 — independent live core

- replace the submodule runtime;
- create an independent package;
- establish provenance;
- implement instruments;
- implement order intents and lifecycle;
- implement bracket plans;
- implement readiness;
- implement risk;
- implement immutable events;
- implement position accounting;
- implement SQLite durability;
- implement execution-ID idempotency;
- implement broker port;
- implement order gateway.

### Phase 2 — reconciliation and emergency safety

- account and market freshness;
- position reconciliation;
- working-order reconciliation;
- unknown-outcome recovery;
- kill-switch levels;
- cancel service;
- cancel sweep;
- emergency flatten coordinator;
- adapter sequence checkpoints.

### Phase 3 — complete bracket coordination

- bracket persistence;
- staged target state;
- trailing state;
- partial-fill resizing;
- native OCO mapping;
- cancel/replace chains;
- post-fill actions;
- net-cost protection;
- coverage diagnostics.

### Phase 4 — first real adapters

- one crypto derivatives adapter;
- one listed-futures broker;
- streaming updates;
- margin integration;
- market data;
- adapter certification.

### Phase 5 — strategy ingress and portfolio control

- JSON and TradingView-style ingress;
- strict text normalization;
- Discord commands and alerts;
- trade intents;
- position targets;
- strategy risk;
- portfolio risk.

### Phase 6 — operator system

- FastAPI;
- authentication and authorization;
- operator UI;
- lifecycle and bracket visualizations;
- incident and reconciliation controls;
- audit export;
- operational runbooks.

### Phase 7 — restricted funded activation

- restart and recovery verification;
- network and timeout fault injection;
- adapter certification;
- account, strategy, instrument, and capital allowlists;
- maximum order and daily loss limits;
- kill switch and emergency procedure verification;
- explicit operator activation.

## 16. Definition of complete

Combination is ready for restricted funded deployment only when:

1. it runs without Sentinel Chain or Sentinel Iron;
2. no deployable fake execution mode exists;
3. every position mutation comes from a confirmed external fill;
4. duplicate events cannot mutate state twice;
5. unknown outcomes force reconciliation;
6. restart reconstructs equivalent state;
7. partial fills and cancel races are handled;
8. bracket protection uses confirmed fill quantity;
9. open exposure has verified durable protection;
10. readiness, reconciliation, margin, and risk cannot be bypassed;
11. kill switch and emergency flatten pass adapter-level tests;
12. at least one adapter passes the complete certification contract;
13. operator activation is explicit, scoped, and reversible;
14. the database and event journal are healthy and recoverable;
15. connected account, strategy, instrument, and capital limits are explicitly authorized.

This plan deliberately prioritizes external truth, recoverability, and controlled failure over demonstrations, fake-money features, convenience modes, or optimistic automation.
