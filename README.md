# Combination

Combination is an experimental integration laboratory for **Sentinel Chain** and **Sentinel Iron**.

It keeps both source projects independent while pinning their complete implementations into one reproducible superproject:

- `components/sentinel-chain` — the full Sentinel Chain crypto automation, synthetic bracket, paper execution, backtesting, API, and operator UI implementation.
- `components/sentinel-iron` — the full Sentinel Iron listed-futures domain, broker lifecycle, reconciliation, margin, risk, portfolio targeting, audit, and emergency-control implementation.
- `src/sentinel_combination` — a thin integration facade, launcher, capability inventory, and experiment boundary.

The original repositories remain unchanged and can continue to diverge. Combination pins exact source commits so experiments are reproducible and upgrades are explicit.

## Safety boundary

Combination does **not** automatically enable autonomous live trading. Sentinel Chain retains its paper-first behavior. Sentinel Iron retains its live activation, readiness, reconciliation, risk, margin, broker, lifecycle, audit, kill-switch, and operator-confirmation gates.

## Clone

```bash
git clone --recurse-submodules https://github.com/Tetradim/Combination.git
cd Combination
python scripts/bootstrap.py --dev
```

For an existing clone:

```bash
git submodule update --init --recursive
python scripts/bootstrap.py --dev
```

Windows PowerShell:

```powershell
.\scripts\bootstrap.ps1 -Dev
```

## Unified CLI

```bash
combination doctor --strict
combination capabilities
combination pins
combination chain --host 127.0.0.1 --port 8004
combination iron -- --help
combination test-all
```

The facade delegates to the original packages rather than duplicating their domain logic. This keeps experimental glue removable and makes it clear whether a behavior originates in Chain, Iron, or Combination.

## Architecture

```text
Combination
├── components/
│   ├── sentinel-chain/   # pinned full upstream repository
│   └── sentinel-iron/    # pinned full upstream repository
├── src/sentinel_combination/
│   ├── capabilities.py   # feature/provenance registry
│   ├── components.py     # pin and path definitions
│   ├── contracts.py      # neutral cross-bot experiment contracts
│   ├── runtime.py        # subprocess isolation and delegation
│   └── cli.py            # unified operator entry point
├── docs/
│   ├── ARCHITECTURE.md
│   ├── FEATURE_MATRIX.md
│   └── EXPERIMENTS.md
└── scripts/
    ├── bootstrap.py
    └── bootstrap.ps1
```

## Why submodules

Git submodules are intentional here:

1. Every source feature is present at an exact commit.
2. Chain and Iron can evolve independently.
3. Combination can test upgrades one source at a time.
4. Provenance remains obvious during debugging.
5. Integration code cannot silently rewrite either bot.

See `combination.lock.json` for the pinned repositories and commits, and `docs/FEATURE_MATRIX.md` for the capability inventory.
