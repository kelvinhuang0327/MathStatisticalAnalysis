# Seven-member eleven-event Hunter certificate

Task: `B649_K20_R3_STATE_13169800_SEVEN_MEMBER_11EVENT_HUNTER_R1`.
Route: `STANDARD`, `SELF_CHECK_ONLY`. This is a local research certificate.

The immutable input is commit `7ee823ca367076b483f93f1cc8c4d6da89aaa3e2`,
tree `f0f6d5f1e0ee8617c7630863f9099c25d5753ecb`, and
`b649-k20-r3-next-two-layers-shared-hunter-certificate-r1-result.json`
with SHA256 `cbc291d98438e515f9b53f58dd6174bdb9eba88c123842bdd5f63a8aedd173e7`.
The final result is
`b649-k20-r3-state-13169800-seven-member-11event-hunter-r1-result.json`,
SHA256 `62989e8481d07290a6f63e9affb5fdc32dee4c799a1921c8d124dd6a2323930c`.

## Complete coverage and sealed remainder

The R24 region for `state:s2-13169800-s3-789320` has 989 compressed members
representing 1,072 vectors. Its identity is
`c183f8d2f93d3a695fcae3e2d2d280d40ffb1de3527eb43e61ce5321569dcde1`.
Every raw member is rebuilt with the existing single-vector R7 constructor;
all existing carried certificate bounds and R24 replacements replay the ledger.
The source's entire maximizing set is exactly
`[0,11][1,a][4,6-a][20,1]`, for `a = 0,...,6`, omitting zero counts.
Exact-loss R17 recovery confirms seven members and seven distinct vectors.

All 982 other members, representing 1,065 vectors, keep their sealed bounds.
Their ordered `(counts, vector_count, raw_bound, final_bound)` digest is
`9492d611e99e79ffc5b9a6d4f4dcecc05b77b1ad250c3d50c7509a3fdafad01e`.
The new result includes the full 989-member ledger, not only the corrected subset.
All 34 pinned upstream inputs are rehashed before every public build/replay,
including when cached authority readers are warm.

## Exact residual events and Hunter floor

Use `R_i = E_i \\ (E_A union E_B)`. Each of the seven vectors has eleven
type-0 tickets, each with six labels entirely outside the two anchors. Hence
the subset has 66 incidences on 40 labels. For label frequencies `d_x`,
`Q = sum_x C(d_x,2) = sum_{i<j} |T_i intersect T_j|`.
Since `C(d,2) >= d-1`, `Q >= 66-40 = 26`. The balanced allocation of fourteen
frequencies 1 and twenty-six frequencies 2 attains this incidence-only floor.

The existing integer region counter independently recounts the four type-0
residual pair rows, then checks equality with R8 and the sealed residual-pair
counter. It counts official outcomes through their seven-to-one mapping to
seven-element sets, using binomial region allocations, without enumerating
the full official outcome space. The exact overlap floors are:

| Pair overlap | Exact residual intersection floor |
|---|---:|
| 0 | 107,800 |
| 1 | 574,000 |
| 2 | 1,691,620 |
| 3 | 3,451,651 |

Let `G_k` contain pairs with ticket overlap at least `k`, with `e_k` edges.
The R3 family overlap ceiling is 3, so `e1 + e2 + e3 = Q`.
For any simple graph of forest rank `r`, its edge count is at most
`C(r+1,2)`: merging components of ranks `a,b` increases the capacity by `ab`.
Thus its rank is at least `rho(e) = min{r: C(r+1,2) >= e}`.
A tree chosen by descending overlap contains a spanning forest of every
nested `G_k`. Hunter's inequality then gives the correction floor

`10*phi(0) + sum_{k=1..3} (phi(k)-phi(k-1))*rho(e_k)`.

Partitioning by the highest nonempty threshold proves:

| Case | Lower bound on e1 | Rank floors | Hunter floor |
|---|---:|---|---:|
| e2 = e3 = 0 | 26 | (7,0,0) | 4,341,400 |
| e2 > 0, e3 = 0 | 13 | (5,1,0) | 4,526,620 |
| e3 > 0 | 9 | (4,1,1) | 5,820,451 |

The minimum is 4,341,400. The exact integer relaxation checks all 30,216
feasible threshold triples and agrees, with minimizing edge counts `(26,0,0)`.
An independent test relaxes over ranks and obtains the same floor.
Each vector has a concrete R8-valid eighteen-ticket support witness, verified
cell demands, pair overlaps, collision mass, rank inequalities and tree costs.
Its eleven-event subset tree extends to all eighteen residual events by
nonnegative edges. This is a universal lower-bound argument; the witnesses
demonstrate validity without replacing the universal proof.

## Single replacement and complete R3 maximum

The seven source members carry the existing R6/forest correction 4,018,000
and no additional R14 credit, as established by the complete carried-bound
replay and `final_bound == raw_bound`. Replace the applied correction once
with `max(R6, forest, existing R14, eleven-event Hunter) = 4,341,400`.
Corrections are never summed. A compressed member uses its weakest represented
vector. No new R14 certificate is credited by this task.

| Recomputed term | Value |
|---|---:|
| Starting complete R3 UB | 355,628,469 |
| Seven-member maximum after replacement | 355,305,069 |
| Preserved remainder maximum | 355,597,508 |
| Complete target State maximum | 355,597,508 |
| Preserved classified maximum | 355,468,904 |
| Preserved unclassified Tail bound | 354,039,277 |
| Complete R3 UB after all 23 State terms | 355,597,508 |
| Incumbent | 313,263,888 |
| Remaining gap | 42,333,620 |

The final owner remains `state:s2-13169800-s3-789320`. All other 22 State terms,
the classified aggregate and Tail are preserved exactly. Output numbers are
derived from pinned sources and exact arithmetic; expected values occur only
in assertions and this report.

## Reproduction and verification

From the task worktree, with its source on `PYTHONPATH` and Python 3.13:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m lottolab.research.b649_k20_r3_state_13169800_seven_member_11event_hunter_r1 --write
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m lottolab.research.b649_k20_r3_state_13169800_seven_member_11event_hunter_r1 --verify
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/unit/test_b649_k20_r3_state_13169800_seven_member_11event_hunter_r1.py
python -m ruff check --no-cache src/lottolab/research/b649_k20_r3_state_13169800_seven_member_11event_hunter_r1.py tests/unit/test_b649_k20_r3_state_13169800_seven_member_11event_hunter_r1.py
python -m pyright --project .task-data/pyrightconfig.json
git diff --check
```

The scoped Pyright configuration uses `typeCheckingMode: strict`,
`pythonVersion: 3.13`, and exactly the new source and test files. Runtime
dependencies come from the existing Python 3.13.8 environment; imports use
this task's `src`. Tests cover completeness, exact residual identity, pair
floors, collision mass, Hunter ranks, max-only replacement, preserved remainder,
the complete Family maximum, witness validity and immutable-source tampering.
The forbidden-entrypoint test also clears authority caches before replay.

No R7 census, R25, CP-SAT, heavy solver or full outcome enumeration runs.
No Fiber, production, other-worktree source, push, PR or merge is changed.
The specified worktree and branch were absent at preflight and were created
at the exact immutable base under the existing task identity. One local
commit is the authorized final disposition; the worktree is retained.

## Observed check evidence

Focused pytest: 61 passed. Scoped Ruff: all checks passed. Strict Python 3.13
Pyright: exactly two files analyzed, zero errors, zero warnings. Stored-result
replay and final pytest are repeated after the mutant processes exit.

Nine non-equivalent implementation mutants are killed by the named focused
checks. Each mutant is compiled only into a disposable subprocess's module
memory; no candidate or upstream source file is rewritten. The source SHA256
before and after the final mutation run is
`ac9a5236dc79c31382348b76414b3008dde86f9c228a5d48314eeac055f51965`.

| Implementation mutant | Observed rejection |
|---|---|
| Eleven events changed to ten | Exact cohort coverage fails |
| Pair floors increased by one | Floor exceeds an exact residual row |
| Collision mass decreased by one | Independent frequency sum disagrees |
| Threshold rank floor decreased by one | Exact integer Hunter relaxation disagrees |
| Largest threshold case used instead of minimum | Exact integer Hunter relaxation disagrees |
| Correction max replaced with sum | Single-replacement arithmetic assertion fails |
| Preserved remainder bound decreased by one | Preservation guard fails |
| Family recomputed using only the seven members | Complete 23-State maximum assertion fails |
| Immutable fingerprint guard removed | Source tampering no longer raises |

The final mutation report and per-mutant logs are retained in `.task-data`.
The earlier mutation attempt is retained separately as superseded: extending
the carried-source fingerprint set during that attempt invalidated its
source-stability assertion, and one expected error-display string had the
operands reversed. All nine mutants were rerun against the stable final source.
An initial Pyright invocation ignored absolute include paths and is not
counted as a pass; the corrected relative-path configuration analyzes both
files. Strict type-alias/index diagnostics and a Ruff regex-string diagnostic
were repaired before the passing final checks. No type rule was suppressed.
