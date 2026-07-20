# Project Profile

Status: bootstrap R1 · 2026-07-20 · fixed base `origin/main` 8d5af3c86544d7bceb1cf444422e5162759da661

## Identity

**LottoLab** — a lottery statistical-analysis system, the next-generation rebuild of the
frozen legacy repo `LotteryNew`, migrated capability by capability. `[Confirmed]`
([README.md](../../README.md), [ADR-0004](../../docs/decisions/ADR-0004-project-name-and-scope.md))

Python package / CLI command: `lottolab`. Scope is lottery-only by charter (ADR-0004):
`DAILY_539`, `BIG_LOTTO`, `POWER_LOTTO`; other domains (stock, betting-pool, ...) get
their own separate project, never this repo. `[Confirmed]`

Currently *implemented* end-to-end functionality (Strategy Overview, local Draw Data
ingestion) supports **`BIG_LOTTO` only** — 6 unique main numbers (1–49) plus exactly one
required, non-overlapping special number (1–49). The other two lottery types are in
scope per ADR-0004 but not yet built out. `[Confirmed]` ([README.md](../../README.md))

## Owner / contact

Owner and sole decision-maker on ADRs to date: **Kelvin** (`kelvin@webcomm.com.tw`, per
`pyproject.toml` `[project.authors]`). `[Confirmed]`

## Relationship to LotteryNew

- LotteryNew is a **frozen, read-only reference implementation**. This repo never writes
  to it — not one line. `[Confirmed]` ([README.md](../../README.md) §軌道紀律,
  [ADR-0001](../../docs/decisions/ADR-0001-new-repo-location.md))
- Reason: LotteryNew has had three live-writer-collision incidents; the new track never
  risks a repeat. `[Confirmed]` (ADR-0001)
- Migration is strangler-fig style: migrate a capability → verify parity against
  hash-pinned golden/snapshot exports → retire the legacy side. Data enters only through
  `tools/import_snapshot.py`'s manifest validation; new-system tests read exported
  golden files only and never import legacy code. `[Confirmed]` (ADR-0001,
  [docs/architecture/system.md](../../docs/architecture/system.md))
- **No-write boundary is explicit and absolute**: nothing in this repo's tooling opens,
  queries, or modifies LotteryNew. `[Confirmed]`

## Stack

| Layer | Choice | Source |
|---|---|---|
| Backend language | Python 3.13 (pinned) + uv (lockfile) | [ADR-0003](../../docs/decisions/ADR-0003-language-and-toolchain.md) |
| Web framework | FastAPI + Pydantic v2 (OpenAPI is the contract source for frontend types) | ADR-0003 |
| Frontend | TypeScript + Vite + Vue 3 | ADR-0003 |
| Storage | SQLite, single canonical path enforced at the repository layer | ADR-0003 |
| Quality gates | ruff + pyright (strict) + pytest (layered) | ADR-0003 |

ML-heavy dependencies (tensorflow, autogluon, prophet, ...) are deliberately **not** in
the core; current strategies need only numpy/pandas/scipy-class dependencies.
`[Confirmed]` (ADR-0003)

## Authoritative sources

- [README.md](../../README.md) — quick start, runtime controller, current feature notes
- [docs/README.md](../../docs/README.md) — canonical documentation entry point (ADR-0002)
- [docs/architecture/system.md](../../docs/architecture/system.md) — layering and dependency rules
- [docs/decisions/](../../docs/decisions/) — ADR-0001 through ADR-0004
- [docs/migration/migration-ledger.yaml](../../docs/migration/migration-ledger.yaml) — per-capability migration state
- [docs/capabilities/catalog.yaml](../../docs/capabilities/catalog.yaml) — capability inventory

## Explicitly not claimed

Production readiness, deployment status, a registry/publication process, and support
for lottery types beyond `BIG_LOTTO` in the shipped feature set are **not** established
by any committed source as of this bootstrap. Treat as `[Unknown]` unless a future
source states otherwise.
