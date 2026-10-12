# B649 branch3 proof authority consolidation

The current authority for K20 successors is
[`b649-branch3-k20-proof-authority-consolidation-r1.json`](matrix-native-results/b649-branch3-k20-proof-authority-consolidation-r1.json).
Its [`source manifest`](matrix-native-results/b649-branch3-k20-proof-authority-consolidation-r1-sources.json)
records each source worktree, verified HEAD/tree, every pre-copy SHA256,
the imported Python dependency graph, and reused files already present on main.
The source files and verified hashes are the handoff authority; source commit
objects do not need to exist in a successor repository.

Remote `origin/main` and the local tracking ref both resolved to
`0b2822fc544d504367e79397de493a020506c0a7` before the task worktree was created.
The base tree is `d9b85c7bd5fae756804d7fb9c9c7bde8411c0e29`.
The task branch is `codex/b649-branch3-k20-proof-authority-consolidation-r1`.

| Proof family | Current upper bound | Remaining gap | Status |
|---|---:|---:|---|
| K10 global optimum | 176345645 | 0 | PROVEN |
| K20 minimum-S2, frozen R2 | 313916056 | 676395 | OPEN |
| K20 outside minimum-S2, pair overlap <=1 | 311435293 | Below incumbent | CLOSED |
| K20 Family C, exactly one overlap-2 pair | 311499152 | Below incumbent | CLOSED |
| K20 Family A, maximum overlap >=3 | 357241548 | 44001887 | OPEN |
| K20 Family B, multiple overlap-2 pairs | 357794343 | 44554682 | OPEN |

The K20 incumbent remains `313239661`. Taking the maximum of the current
five K20 family bounds gives the global certified upper bound `357794343`
and the remaining gap `44554682`. Family B's open residual is three or more
overlap-2 pairs with overlap mass at least 94.

Twenty files were copied byte for byte: seven proof modules, seven focused
test files, and six load-bearing result records. The K10 rational-dual verifier
imports the prior profile-42/3/4 module. Family B imports the preceding heavy-pair
module for its exact triple table; that same module supplies Family C's wedge
certificate. These dependencies contain historical solver entry points, which
are retained as part of the imported modules. The focused checks never call
them. The unimported mass>=13 exploratory proof and standalone exploratory
CP-SAT/mass-census files are excluded.

The minimum-S2 R2 source commit contains only its module and focused test.
Its frozen S1/S2/S3 terms, S4 floor, fourth-order credit, bound, and gap are
preserved in the consolidated JSON. Existing source records remain unchanged;
their earlier UNKNOWN statuses and older A/B bounds describe their original
scopes. Use the consolidated record's explicit authority selections for the
current scientific state.

Validation is limited to the eight focused suites listed in the consolidated
JSON. First run `uv sync --frozen --extra research`, then:

```sh
uv run --no-sync pytest -q \
  tests/unit/test_b649_k10_nonlinear_p4_p14_higher_order_bound_r1.py \
  tests/unit/test_b649_k10_profile_42_3_4_exact_closure_r1.py \
  tests/unit/test_b649_k20_outside_min_s2_global_penalty_bound_r1.py \
  tests/unit/test_b649_k20_min_s2_higher_order_closure_r2.py \
  tests/unit/test_b649_k20_heavy_pair_r3plus_global_bound_r3.py \
  tests/unit/test_b649_k20_heavy_pair_defect_global_bound_r2.py \
  tests/unit/test_b649_k20_multi_r2_defect_global_bound_r3.py \
  tests/unit/test_b649_branch3_k20_proof_authority_consolidation_r1.py
```

Ruff lint and strict Pyright are scoped to the fifteen changed Python files.
The separate optional formatter check flags 13 imported source files, which
remain byte-for-byte aligned with their recorded source hashes.
The integration suite checks hashes against native files, selects each current
source record, checks the frozen minimum-S2 terms, and verifies bound/gap
aggregation. Bounded toy counts and local certificate checks in the existing
suites are validation only. Three controlled local mutations confirmed that
the hash, Family B bound, and global bound checks fail when their protected
values are wrong; each mutation was restored and the focused suites were
re-run. No research enumeration, certificate regeneration, portfolio search,
CP-SAT run, full suite, or Judge is part of this task.

The task worktree and branch are retained. Delivery is one local commit in the
canonical repository's shared object database. Push, PR, merge, and production
mutation are outside this task.
