# Project Context

Status: Replay evidence as of 2026-10-14 · merged base `b16cd98dc30c2459701c53024c8bf9b2328da925`

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

`lottery.replay.read_models` remains `phase: INVENTORIED` in the migration ledger;
its `pr` and `parity_evidence` fields are both `null`, and the ledger says the
P600B pilot includes only catalog/lifecycle metadata. `[Confirmed]`
(docs/migration/migration-ledger.yaml)

Replay execution, history, scoring, API, and UI components already exist in the
repository (for example, `src/lottolab/application/use_cases/replay_historical_predictions.py`,
`src/lottolab/domain/replay_history.py`, `src/lottolab/domain/replay_scoring.py`,
`src/lottolab/interfaces/api/replay_execution.py`, and
`frontend/src/features/replay-history/ReplayHistoryPage.vue`). `[Confirmed]`
This code inventory is separate from the migration/parity status of the
`lottery.replay.read_models` capability.

The bootstrap is merged into `origin/main`; it does not change that ledger
status. `[Confirmed]`

### Separate BIG_LOTTO captured-record pilot

The single-record BIG_LOTTO capture-conversion pilot ([PR #373](https://github.com/kelvinhuang0327/MathStatisticalAnalysis/pull/373)) merged on 2026-10-13 at `a895e02f0f3a71c29c33bee6612a73ff0bd9fac8`. It converted one captured record through the canonical snapshot and scoring artifacts, then checked the target GET response against eight mapped fields: ordinal, target draw number/date, strategy ID, predicted main numbers, source prediction status, main-number hit count, and special-number hit. `[Confirmed]` (data/manifests/biglotto-single-endpoint-pilot-r1.json)

The original dataset/version, identity of the original 635 history rows, capture-time strategy/runtime identity, and original legacy HTTP response remain unknown or unverified; prediction regeneration was not run. `[Confirmed]` (data/manifests/biglotto-single-endpoint-pilot-r1.json)

`[Confirmed]` As of 2026-10-14, old r7 evidence records exit 0, `accepted: true`, and candidate `MATCH` for commit `560503e9e0ab897c603205151368b10d33af94c4` / tree `bf43fa58a2bb2b5c9c0d337b6a0c7e90e3c42a41`; this applies only to those old tool bytes.

`[Confirmed]` [PR #379](https://github.com/kelvinhuang0327/MathStatisticalAnalysis/pull/379) merged at 2026-10-14T09:47:50Z into commit `b16cd98dc30c2459701c53024c8bf9b2328da925` / tree `d09c71985187a3151eb1641804bc592da9a635ba`. [CI run 38532436278](https://github.com/kelvinhuang0327/MathStatisticalAnalysis/actions/runs/38532436278) succeeded for backend and frontend. On 2026-10-15, the r2 candidate run of tool commit `b74d02ad1383b21b863c6272966d8a36f481ee29` completed once on CPython 3.9.6 / NumPy 1.26.2 / SciPy 1.12.0 (runner and recorder exit `0`); the receipt was accepted and candidate fields `MATCH`. Evidence root `/Users/kelvin/Documents/ChatGPT/ReplayEvidence/`: output manifest `biglotto-final-receipt-r2-20261015-output.manifest.json` SHA-256 `8efca11b4959707d5fad184af1038d6dc51c07bc7dfbffa01b7dd6e0991ffd1e`, binding `receipt.jsonl` SHA-256 `f8615e2ff27886193f6e496f5f96fc3cfb0850fe7c07e393f5560799364d870c`. This is candidate-only evidence; `original_source_identity_established: false` and historical parity is `UNKNOWN`.

`[Unknown]` Original execution source, complete ordered history, dataset/snapshot, runtime, and loaded-module identity remain `UNKNOWN`; the original legacy HTTP response remains unverified. Historical parity is incomplete; CTO progress remains 5/6 (83.3%). Resolving those identities and historical parity remains outstanding.

This pilot does not change `lottery.replay.read_models`: its migration-ledger phase remains `INVENTORIED`, with no PR or parity-evidence entry. `[Confirmed]` (docs/migration/migration-ledger.yaml)

### BIG_LOTTO bounded source-check closeout — 2026-10-16

`[Confirmed]` This round of bounded source checks is closed: no material sufficient
to establish the original P14B execution identity was found in the checked sources.
This does not prove that such evidence is absent everywhere. Original P14B historical
parity remains `UNKNOWN` and cannot be verified from the available evidence. Static DB
path resolution describes defaults and overrides only; the actual historical DB path
remains unproven.

The r2 candidate receipt was accepted and candidate output fields are `MATCH`, with
`candidate_only=true`, `original_source_identity_established=false`, and
`historical_reproduction_proven=false`. CTO technical completion remains **5/6 (83.3%)**;
the outstanding milestone is original P14B historical parity evidence.

Reopening requires mutually linked evidence from the same execution: original program
version and worktree state; full command/argv, host, cwd, runtime and dependencies;
the corresponding DB/snapshot or complete ordered inputs with digest; and original
outputs/logs/execution identifiers that link back to that execution.

Evidence:
- `/Users/kelvin/Documents/ChatGPT/ReplayEvidence/biglotto-final-receipt-r2-20261015-output/result.json`
- `/Users/kelvin/Documents/ChatGPT/ReplayEvidence/p14b-adjacent-records-r1/artifact/evidence.json`
  (manifest: `/Users/kelvin/Documents/ChatGPT/ReplayEvidence/p14b-adjacent-records-r1/manifest.json`).
- `/Users/kelvin/Documents/ChatGPT/ReplayEvidence/p14b-path-resolution-r1/artifact/evidence.json`
  (manifest: `/Users/kelvin/Documents/ChatGPT/ReplayEvidence/p14b-path-resolution-r1/manifest.json`).

## Reproducibility

Interpreter or numerical-dependency upgrades are a gated PR that must regenerate and
re-pin all golden digests (ADR-0003) — see [RUNBOOK.md](RUNBOOK.md) for the operational
rule.
