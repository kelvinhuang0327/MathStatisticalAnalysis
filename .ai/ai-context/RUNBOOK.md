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

## Post-merge status maintenance

- After merging a PR, the merger (person or agent) checks status text the PR may have made
  stale, such as conditional wording like "after X is merged" in
  `.ai/ai-context/PROJECT_CONTEXT.md`. If the condition now holds, rewrite it as current
  status with the date and source commit; a plan whose condition is still unmet may stay
  conditional.
- `.ai/ai-memory/MEMORY_LOG.md` is append-only: add a new dated entry citing current
  evidence, only when the task authorizes memory writes. Never edit older entries.
- List anything not checked in the handoff. A merge does not update other branches or
  worktrees; they get the fix only after updating onto the new `main`.

- Keep merged PR status separate from candidate and original-source claims. As of
  `2026-10-13`, PR #373/#375 are merged; the local single `BIG_LOTTO` candidate
  result is `MATCH`. That proves agreement under the candidate history and
  existing candidate implementation only. The original capture's dataset/version,
  history identity, and strategy version remain `UNKNOWN`; original-input
  reproduction and original parity are not confirmed.
- When explicitly authorized to synchronize local `.ai/` status, update only the
  named paragraphs/files, record each worktree's HEAD/status and complete file
  SHA-256 before/after, preserve existing dirty content, and verify old memory-log
  prefix bytes. This local documentation maintenance does not update Git refs or
  establish execution, publication, or parity evidence.

`[Inferred]` from the 2026-10-12 Replay status follow-up; not yet a standing repository
policy document.

## Deployment, registry, publication

Deployment process, artifact registry, publication steps, and external-notification
procedures are **`[Unknown]`** — no committed source in this repository documents them
as of this bootstrap.

## One-off evidence retention

`[Inferred]` Project workflow recommendation; not an established repository policy.

- Save one-off execution artifacts with `--output-directory` to a persistent path
  outside the version-controlled source tree that the owner can continue to access.
- Keep DB and scratch data under the existing temporary-directory rules; execution
  artifacts and runtime data must not enter Git.
- In the handoff, list the artifact root, full manifest SHA-256, commit/tree,
  runtime/source identity, and receipt/result SHA-256 values.
- Explicitly list missing files and do not claim archival is complete while required
  evidence is missing.
