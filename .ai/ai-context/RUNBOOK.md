# Runbook

Status: bootstrap R1 · 2026-07-20 · fixed base `origin/main` 8d5af3c86544d7bceb1cf444422e5162759da661

## Toolchain requirements

- Python 3.13, pinned via `.python-version`; dependencies managed with `uv` (`uv.lock` is committed). `[Confirmed]`
- Node 20 for the frontend (`frontend/package-lock.json` is committed). `[Confirmed]` ([.github/workflows/ci.yml](../../.github/workflows/ci.yml))

## Canonical backend commands

```bash
uv sync                        # install deps (Python version pinned via .python-version)
uv run pytest                  # unit / contract / architecture tests
uv run ruff check .            # lint
uv run pyright                 # type check (strict)
uv run uvicorn --factory lottolab.interfaces.api.app:create_app --reload   # API :8000
```

`[Confirmed]` ([README.md](../../README.md))

## Canonical frontend commands

```bash
cd frontend && npm install && npm run dev
```

`[Confirmed]` (README.md)

## CI-equivalent commands

From [.github/workflows/ci.yml](../../.github/workflows/ci.yml):

```bash
# backend job
uv sync --frozen
uv run ruff check .
uv run pyright
uv run pytest

# frontend job (cwd: frontend/)
npm ci
npm run api:check
npm run typecheck
npm test
npm run build
```

`[Confirmed]`

## Local runtime controller

```bash
uv sync --frozen
cd frontend && npm ci && cd ..

uv run --no-sync lottolab local start    # API 127.0.0.1:8000 + Vite 127.0.0.1:5173
uv run --no-sync lottolab local status   # verifies state, PID identity, process group, listener
uv run --no-sync lottolab local smoke    # health, frontend, direct/proxied Strategy Catalog
uv run --no-sync lottolab local stop     # stops only the controller-owned process group
```

`[Confirmed]` (README.md)

Rules, all `[Confirmed]` from README.md:

- The controller stores its owner-only lock/state/log under the user's system temp
  directory. It never reads the DB, never depends on LotteryNew, never accepts an
  alternate port, and never kills a foreign port owner.
- Fixed ports **8000** and **5173** are a deliberate safety constraint, not an
  oversight.
- Supported today on POSIX/macOS only; Windows is not supported.
- On a clean stop, active state is removed, but task-owned diagnostic logs remain in
  the owner-only runtime directory outside the repo.
- The controller only uses an already-locked Python/frontend environment — **it never
  bootstraps or installs dependencies itself.**
- Same-OS-user race/tamper immunity is explicitly out of the supported threat model;
  stronger isolation requires OS sandboxing or privilege separation, which is out of
  current scope.

## SQLite / data-directory rules

- The local DB always lives **outside the Git worktree**. Default location can be
  overridden with an absolute, owner-only path:
  `LOTTOLAB_DATA_DIR=/absolute/owner-only/path uv run --no-sync lottolab local start`
- A history read with no existing DB returns a deterministic empty result — it creates
  no directory, DB, or migration. Only the first valid commit creates the version-1
  schema.
- User DBs, SQLite sidecar files, uploads, and runtime artifacts never enter Git.
- Tests and task lifecycles must point `LOTTOLAB_DATA_DIR` at a freshly created
  temp directory outside the repo, and remove only the path that task itself created,
  after verification.

`[Confirmed]` (README.md)

**DB open/query/write requires explicit task authorization.** No command in this
runbook grants standing authority to open, query, or write the database; that
authorization is scoped per task.

## LotteryNew boundary

LotteryNew is read-only from this repo, without exception — see
[PROJECT_PROFILE.md](PROJECT_PROFILE.md#relationship-to-lotterynew). No command in
this runbook reads from or writes to LotteryNew.

## Reproducibility gates

An interpreter or numerical-dependency upgrade is a separate, gated PR that must
regenerate and re-pin **all** golden digests in the same PR. Lesson recorded in
ADR-0003: LotteryNew previously broke every existing digest after a Python 3.12
switch to Neumaier summation changed floating-point results. A PR that casually
upgrades a dependency alongside unrelated work is rejected outright. `[Confirmed]`
([ADR-0003](../../docs/decisions/ADR-0003-language-and-toolchain.md))

## B649 evidence-first (backtest / ranking / strategy selection)

Entry point: `uv run --no-sync python tools/b649_evidence_status.py --latest-draw <期號>`
(bounded discovery; JSON per ticket count). README's generated block
(`<!-- BEGIN GENERATED B649 EVIDENCE STATUS -->`) is refreshed with `--write-readme` and
verified by `--check-readme` and `tests/unit/test_b649_evidence_status.py`.

- **EXISTING_EVIDENCE_FIRST** — before any backtest/ranking recomputation: read the README
  index, follow its locators, run the discovery tool, and report the existing result first.
- **README_IS_INDEX_NOT_AUTHORITY** — README is navigation only; it can never prove
  `NO_BACKTEST` / missing K. Absence requires the tool's bounded lookup to return `ABSENT`.
- **STALE_IS_NOT_ABSENT** — old-cutoff evidence is `AVAILABLE_STALE`, never `ABSENT`.
- **REPORT_BEFORE_REFRESH** — for stale evidence report historical ranking, cutoff, missing
  draws, coverage/strategy count and freshness limits before computing anything.
- **DELTA_REFRESH_BEFORE_FULL_RERUN** — extend with the missing draws whenever valid.
- **OWNER_REFRESH_DECISION** — when the historical ranking is still valid evidence, surface
  it and let the Owner decide whether to refresh; never silently replace it.
- **FULL_RERUN_JUSTIFICATION** — a full rerun names one reason: `INCOMPATIBLE_SCHEMA`,
  `INVALID_EXISTING_EVIDENCE`, `NON_INCREMENTAL_ALGORITHM`, `OWNER_REQUESTED_FULL_RERUN`
  or `OTHER_EXPLICIT_TECHNICAL_REASON`. "README did not show it" is not a reason.
- When both exist, report historical rank, refreshed rank, rank change, stability and
  sample/coverage difference (`compare_rankings`); do not pick a strategy just because it
  wins a small refresh window. Prefer long-history + recent-delta + rank stability +
  coverage. Sealed-geometry K20 portfolios are outcome-independent and are never tuned on
  historical outcomes.

## Branch / worktree safety

- Never force-push, force-delete a branch, or force-reset a worktree without explicit,
  scoped authorization for that specific action.
- Never run a broad cleanup (`git clean`, `git reset --hard`, or equivalent) without
  explicit authority for that exact operation.
- Before any operation that could discard uncommitted work, check status first and
  preserve anything found rather than discarding it.
- The canonical primary checkout's dirty/untracked inventory is protected: do not
  stage, modify, or otherwise process paths outside an explicitly authorized allowlist.

`[Inferred]` from this bootstrap task's own operating constraints; not yet formalized
as a standing repository policy document.

## Deployment, registry, publication

Deployment process, artifact registry, publication steps, and external-notification
procedures are **`[Unknown]`** — no committed source in this repository documents them
as of this bootstrap.
