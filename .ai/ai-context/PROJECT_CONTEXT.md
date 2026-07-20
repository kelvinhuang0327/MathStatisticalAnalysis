# Project Context

Status: bootstrap R1 · 2026-07-20 · fixed base `origin/main` 8d5af3c86544d7bceb1cf444422e5162759da661

## Layering and dependency direction

```text
Frontend (Vue 3 + TS)
   │  versioned API contract (contracts/openapi.json → generated TS types)
Interfaces (FastAPI routes / CLI)          ← thin shell, composition root
   │
Application (use cases / ports / DTO)
   │
Domain (draws / strategies / lifecycle)    ← pure model, zero external deps
   ▲
Infrastructure (persistence / snapshot / scheduler)  ← implements ports
```

`[Confirmed]` ([docs/architecture/system.md](../../docs/architecture/system.md))

Dependency-direction rules, enforced by `tests/architecture`:

- `domain` imports no other lottolab layer.
- `strategies` imports only `domain`; **the catalog never imports adapter implementations**.
- `application` imports neither `interfaces` nor `infrastructure` (inverted via ports).
- `infrastructure` never imports `interfaces`.
- Production code never imports research/outputs/artifacts-class directories.

**Architecture enforcement test:**
[tests/architecture/test_dependency_rules.py](../../tests/architecture/test_dependency_rules.py)
— a violation is a CI failure. `[Confirmed]`

## Strategy descriptor and lifecycle invariants

1. Each strategy has exactly one `StrategyDescriptor` — the single source of metadata truth.
2. `executable=True ⟺ lifecycle_status=ONLINE`, and an `ONLINE` descriptor always has an `adapter_path`.
3. `OBSERVATION` / `REJECTED` / `RETIRED` descriptors never enter the `ExecutableRegistry` — **no stubs**.
4. Adding a strategy means adding one descriptor entry; it does not change the central
   list or existing tests (invariant tests replace exact-count assertions).

`[Confirmed]` (docs/architecture/system.md)

## Canonical documentation entry point

[docs/README.md](../../docs/README.md) is the **single canonical entry point** for all
new-system documentation (ADR-0002). Any new document must be added to its routing
table or it counts as scattered/orphaned. This `.ai/` layer is itself registered there
per that rule.

## Migration ledger — no duplication

Per-capability migration state lives only in
[docs/migration/migration-ledger.yaml](../../docs/migration/migration-ledger.yaml).
This file does not duplicate that ledger; it only points to it. Read the ledger
directly for current phase/PR/parity-evidence per capability.

### Replay status

`lottery.replay.read_models` is currently `phase: INVENTORIED` in the migration ledger
(no PR, no parity evidence — "only catalog/lifecycle metadata is in the P600B pilot").
`[Confirmed]` (docs/migration/migration-ledger.yaml)

**Replay implementation and parity evidence are not yet complete.** This bootstrap does
not change that status and does not constitute or claim any Replay validation.
`[Inferred]` After this bootstrap is reviewed and merged, the next safe planning step is
a separate read-only Replay architecture-fit review based on the then-current `main`
branch. This is a planning recommendation, not an existing repository milestone.

## Reproducibility

Interpreter or numerical-dependency upgrades are a gated PR that must regenerate and
re-pin all golden digests (ADR-0003) — see [RUNBOOK.md](RUNBOOK.md) for the operational
rule.
