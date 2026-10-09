# B649 K20 Fiber T=270 structural exact closure (R1) — preserved artifact

Task: `B649_K20_FIBER_INCUMBENT_T270_STRUCTURAL_EXACT_CLOSURE_R1`

## Scientific result (from `result.json`, frozen)

- Cell: profile `55555555555511111100`, T=270 (22 triple labels, 27 pair labels, 20 tickets of size 6, pool 1..49).
- `TASK_STATUS`: `PROVED_NO_STRICT_GAIN_WITHIN_DEFINED_PROFILE_T270_CELL`
- `EXACT_CELL_MAX`: 313263888 (equals `ADMISSIBLE_CELL_UPPER_BOUND` and the K20 incumbent count)
- `STRICT_GAIN`: NO
- Structure: the cell is forced to `G = K12 ⊔ (K8 − e)`; 5 isomorphism classes (CYCLIC/orbit0, NONCYCLIC/orbit0, /orbit2, /orbit3, /orbit6). Max attained by NONCYCLIC/orbit0 and NONCYCLIC/orbit3.
- `UNPROVED_ITEMS`: empty in the result.
- Scope limit: `GLOBAL_MIN_S2_FAMILY_STATUS` = `NOT_CLOSED_BY_THIS_TASK`. This artifact does not close the global min-S2 family.

## Frozen files

`result.json`, `t270_structural_closure.py`, `test_t270_structural_closure.py` are byte-identical copies of the source task root
`.task-data/B649_K20_FIBER_INCUMBENT_T270_STRUCTURAL_EXACT_CLOSURE_R1/` (gitignored there, not modified).
Hashes are in `SHA256SUMS`; `shasum -a 256 -c SHA256SUMS` verifies them.

- `result.json` = `cd136425601d69c4cf1f437ea11a2c2bd25ff9d295e2cc2f670092aeb20176b8` (matches the expected result hash)
- `t270_structural_closure.py` = `45ee56d3…fce07` (matches the result's `DEPENDENCY_SHA256.SCRIPT`)
- `test_t270_structural_closure.py` = `4ac139d0…a2894` (no hash for this file is recorded in `result.json`)

## Layout and path constraint

The script computes `REPO_ROOT = TASK_ROOT.parents[1]`, so the archive directory must sit exactly two levels below the repo root. That is why it lives at `research-archive/<TASK_ID>/`, and the bytes stay unchanged.

## Seal-time checks (no enumeration, no CP-SAT, no re-search)

1. Result SHA matches the expected value.
2. Script SHA matches `DEPENDENCY_SHA256.SCRIPT` in the result.
3. Authority blobs verified from git objects: baseline `3d5d3f8f…` @ `75d2b23a`; evaluator `92dcb836…` @ `75d2b23a` and @ current `origin/main`; generator `852c210b…` and old family result `0d948aa4…` @ `82e88ada`.
4. The 26-row table matches the old family result (`82e88ada`, `CANDIDATE_COUNTS`). Rows are keyed by (portfolio SHA256, deleted point): 26 unique keys on both sides. Every member's count and STS class equals its old row. The one portfolio hash that appears twice is `c0657150…` under two different deleted points, which the keying handles. Max over the 26 rows = 313263888.
5. The 5 classes: 5 entries, fresh recount equals the old table for each, max = 313263888 = `EXACT_CELL_MAX`.

## Focused portable run (this seal)

Run from `research-archive/<TASK_ID>/` under `ulimit -t 90` and `nice -n 15`, with `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`:

- `t270_structural_closure.py --help` runs (the module imports with no side effects).
- `REPO_ROOT` resolves to the repo root of the worktree, and `result.json` is found.
- `pytest -k phase1_arithmetic test_t270_structural_closure.py`: 1 passed, 3 deselected (about 0.3 CPU-seconds).

Not run in this seal, on purpose:
- The three fixture-based tests. They re-run the STS(13) classification and the family recount, which are out of scope for a preservation seal.

## Portability blocker (not fixed; bytes unchanged)

`load_authority()` and `import_generator()` read the old generator and old family result through a hardcoded path:

`SOURCE_WORKTREE = /Users/kelvin/.codex/worktrees/b649-k20-overlap-block-repartition-12-8-exhaustive-r1/MathStatisticalAnalysis`

- That path is machine-local. The generator `src/lottolab/research/b649_k20_overlap_block_repartition_12_8_exhaustive_r1.py` is absent from `origin/main` and exists only at commit `82e88ada`.
- So the fixture-based tests and a full `main()` run need that old worktree on disk. Otherwise `git -C <missing dir>` fails.
- The fix would change the script bytes or add a compatibility wrapper. Neither was done here, per the task rules.

## Repo-level change accompanying this archive

`pyproject.toml` `[tool.ruff] extend-exclude` now includes `"research-archive"`, alongside the existing `.task-data`. Without it, `uv run ruff check .` (CI) flags two frozen-file findings: SIM300 in `t270_structural_closure.py` and I001 in the test file. Those findings are left unfixed because fixing them would change the frozen bytes.

## Not included

`.fable/` metadata, caches, Fiber checkpoints and locks, and `.task-data/` contents are not part of this commit.
