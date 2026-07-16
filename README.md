# Sentinel Combination

Sentinel Combination is a new, independently evolving trading backend derived from the strongest ideas in Sentinel Chain and Sentinel Iron.

It is **not** a wrapper around the two source bots. It is a single backend with:

- Chain-derived signal normalization and advanced bracket intent;
- Iron-derived broker-authoritative order lifecycle, fill idempotency, readiness, reconciliation, margin discipline, and emergency controls;
- one canonical instrument model for crypto spot, crypto perpetuals, and listed futures;
- one durable event journal and position ledger;
- one execution path for every connected brokerage or exchange account.

## Execution policy

Combination contains no deployable fake exchange, internal paper engine, simulated fill mode, or shadow-routing mode.


## Current build status

The `build/live-only-unified-core` branch begins the independent backend. The first slice contains:

- canonical instruments and precision rules;
- versioned bracket plans;
- explicit order lifecycle states;
- broker/exchange adapter protocols;
- readiness gates;
- pre-trade risk decisions;
- execution-ID idempotency;
- fill-authoritative position accounting;
- durable SQLite transactions and event journal;
- an order gateway that cannot bypass readiness or risk.

No broker adapter is certified yet. Until an adapter passes the required lifecycle, reconciliation, margin, and failure-contract tests, the code must not be represented as ready for unrestricted funded trading.

## Install

```bash
python -m pip install -e ".[dev]"
combination init-db --path data/combination.sqlite3
combination doctor --path data/combination.sqlite3
python -m pytest
```

## Design records

- `docs/LIVE_ONLY_BUILD_PLAN.md`
- `docs/ARCHITECTURE.md`
- `docs/PROVENANCE.md`

## Futures broker catalog

Combination includes a first-class catalog for listed-futures brokerages and crypto-futures companies.

```bash
combination brokers
combination brokers --product listed_futures
combination brokers --product crypto_futures
combination broker-info interactive_brokers
```

Direct adapters are included for Interactive Brokers, TradeStation, Tradovate/NinjaTrader, and supported crypto-derivatives venues through CCXT. Other catalog companies can be associated with a configured transport adapter through `settings.transport_adapter`.
