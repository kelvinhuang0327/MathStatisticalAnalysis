# K20 R3 complete tail band to frozen state (R21)

The exact proof reaches Success A. R3 decreases from **356501945** to
**356378218**, owned solely by `state:s2-13169800-s3-789320`. The 23 R20 state
terms remain unchanged. The proof stops at that crossover.

## Authority and scope

- Base head: `ef5c56e64cbd9fd3e07d49b8658ecd3f71a105cd`.
- Base tree: `f5bf9f75a9457e6167d65da5752119687c0088d1`.
- Branch: `codex/b649-k20-r3-classified-tail-band-to-state-r21`.
- Exact retained worktree:
  `/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/B649_K20_R3_CLASSIFIED_TAIL_BAND_TO_STATE_R21`.
- The R20 source/result and their transitive certificate chain are fingerprinted.
  Previously classified terms are carried from committed records, without
  rebuilding a classified-vector census or enumerating prior tail levels.
- Four new task files comprise the implementation, focused tests, result, and
  this note. Runtime verification uses `.task-data` in the task worktree, with
  bytecode and pytest/Ruff caches disabled. The main checkout is untouched.

## Minimum owner correction

Only `tail-vector:L6742484:0x6,1x11,6x1` is recovered and refined. Its original
R6 pair/triple and forest envelope has correction `1804199`, giving
`365048628 - 6742484 - 1804199 = 356501945`. Its recovered support witness
passes the independent R8 validator.

The first existing rational moment certificate is sufficient:

```text
pair minimum sum       = 16167340
outside incidence      = 94
outside pair mass floor= 68
outside slope          = 422618
residual S2 floor      = 16167340 + 422618 * 68 = 44905364
correction             = ceil(44905364 / 9) = 4989485
certified vector bound = 365048628 - 6742484 - 4989485 = 353316659
dispatch target        = 356501796
```

The rational multiplicity inequality is checked exactly for every bin from
0 through 18. Exact four-event pair tables verify the outside slope. The
first certificate naturally goes below state; no further correction is
dispatched after the vector loses ownership. No solver, stronger correction
stage, or additional inherited vector recovery is needed.

## Complete attained tail band

The independently checked integer crossover is
`365048628 - 356378218 = 8670410`; the preceding integer loss would still give
`356378219`. Enumeration starts exactly at `8546832` and processes **580**
attained levels, ending at `8670354`. The next attained loss is **8670564**,
giving the remaining unclassified tail bound **356378064**.

All **6741** new vectors have independently validated support witnesses.
Their existing R6 correction stack already puts them below state: the
maximum new vector bound is **354720384**. No new vector needs the optional
four-ticket correction or becomes a load-bearing classified owner.

The maximum remaining classified term is **356056456**, with inherited ID
`carried-r12-other-levels`. This ID denotes the pinned aggregate certificate
for other R12 levels, rather than a newly recovered individual vector. It is
carried unchanged and is already below state.

```text
R3 = max(356378218, 356378064, 356056456) = 356378218
R3 drop = 123727
R4 reference = 350545749
Incumbent = 313239661
Remaining gap = 43138557
```

Both owner-set transitions are retained: classified vector to unclassified
tail, then tail to state. No transition-count or drop-target stopping rule
is used. No state is refined after Success A.

## Verification

- Canonical primitives: PASS (`18611432`, `18611432`, `372228640`).
- Exact proof: PASS, 292.070262 seconds, one CPU-bound process, no solver.
- Final-source focused pytest and guarded full replay: PASS, **18 tests** in
  200.75 seconds. Every certificate/result field matches, except elapsed time.
- Ruff check: PASS. Formatting: PASS.
- Scoped strict Pyright: PASS, 0 errors, 0 warnings, 0 informations.
- Falsifiability: temporarily removing the prior-level guard causes the
  expected forbidden-enumerator failure; restoring it passes the same test.
  This mutation exists only in the test process and is not committed.

The guarded replay blocks prior-level census functions, generic frontier
census, state refinement, and solver dispatch. It checks every newly enumerated
interval is at or above the R20 cursor and below the state crossover, and
compares every result field except elapsed time. It validates all support
witnesses again and checks owner-only dispatch, complete owner switching,
immutable state terms, and the stop at Success A.

## Attempt accounting

1. Phase 0 and primitive preflight passed before implementation. The exact
   authorized worktree/branch were created from the pinned base; no existing
   checkout was reset or adopted.
2. Initial exact proof completed successfully and wrote the new result file.
3. Development Ruff findings (pairwise iteration, formatting, line length,
   and a nested guard) were repaired in task-owned source/tests.
4. First scoped Pyright invocation used mutually exclusive `--pythonpath`
   and `--venvpath`; it was rejected without running type analysis. The
   corrected invocation exposed an annotation through a tuple-assigned module
   alias. Importing the concrete certificate type fixed all diagnostics.
5. The first isolated focused guard run passed 16 tests. A premature full
   pytest run passed the same 16 tests and reported 2 fixture errors because
   the proof result had not yet been written. No certificate failure occurred.
6. The deliberate falsifiability run failed for the expected reason, then
   restored and passed. Final focused replay passed all 18 tests after the
   result became available, superseding the premature fixture errors.

No process was terminated, no external publication occurred, no new portfolio
search was started, and no production runtime or data was mutated. Exactly
one local task commit contains these four task files after the final
verification gate; the worktree is retained.
