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
status or provide PR/parity evidence for this capability. `[Confirmed]`
`[Inferred]` The next safe planning step is a separate read-only Replay
architecture-fit review against current `main`. This is a planning
recommendation, not an existing repository milestone.

### BIG_LOTTO pilot and candidate status — 2026-10-14

- `[Confirmed]` [PR #373](https://github.com/kelvinhuang0327/MathStatisticalAnalysis/pull/373)
  merged at `2026-10-13T04:44:57Z` (merge commit
  `a895e02f0f3a71c29c33bee6612a73ff0bd9fac8`); [PR #375](https://github.com/kelvinhuang0327/MathStatisticalAnalysis/pull/375)
  merged at `2026-10-13T07:10:39Z` (merge commit
  `61bad6d9ed4bdb6977d076d6b7fa28ac7b05f82a`).
  At that earlier observation, both local `origin/main` refs and the observed remote
  `main` pointed to the latter commit.
- `[Confirmed]` [PR #379](https://github.com/kelvinhuang0327/MathStatisticalAnalysis/pull/379)
  merged at `2026-10-14T09:47:50Z` as `b16cd98dc30c2459701c53024c8bf9b2328da925`
  (tree `d09c71985187a3151eb1641804bc592da9a635ba`). CI run `38532436278`
  passed its backend and frontend jobs. On 2026-10-15, the r2 candidate run of tool
  commit `b74d02ad1383b21b863c6272966d8a36f481ee29` completed once on CPython
  3.9.6 / NumPy 1.26.2 / SciPy 1.12.0 (runner and recorder exit `0`); the receipt
  was accepted and candidate fields `MATCH`. Output manifest
  `biglotto-final-receipt-r2-20261015-output.manifest.json` (SHA-256
  `8efca11b4959707d5fad184af1038d6dc51c07bc7dfbffa01b7dd6e0991ffd1e`)
  binds `receipt.jsonl` (SHA-256 `f8615e2ff27886193f6e496f5f96fc3cfb0850fe7c07e393f5560799364d870c`).
  Evidence root: `/Users/kelvin/Documents/ChatGPT/ReplayEvidence/`. The original
  source identity remains unestablished (`false`); historical parity is `UNKNOWN`.
- `[Confirmed]` The local single candidate result for `BIG_LOTTO` draw
  `102000010` (`2013/02/01`) is `MATCH`: predicted numbers
  `[4, 8, 30, 33, 37, 44]`, special `null`, using 635 candidate history rows
  through draw `102000009` (`2013/01/29`).
  Source: `.task-data/biglotto-candidate-reproduction-r1/RESULT.json`
  (SHA-256 `0bab72d54cad11ce8bd1e26338f1e0badfbcf94c1fb2cf07396483c9f5880708`);
  `candidate_history.json` SHA-256
  `89086d0130ef8dee2ba84edf07af6299433ce4b73f6c7e8d917b2b96d837f7ee`.
- `MATCH` confirms agreement under this candidate history and existing candidate
  implementation only. The original capture's actual execution source, complete
  ordered history, dataset/snapshot, runtime, and loaded-module identity remain
  `UNKNOWN`. Original-input reproduction and original
  parity are not confirmed; the result records
  `original_reproduction_claimed: false` and `original_source_identity_established: false`.

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
