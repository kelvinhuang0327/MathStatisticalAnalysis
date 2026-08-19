# STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_DESIGN_R1 — experiment design

## 1. What sealed evidence could and could not resolve

The sealed `STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1` study
(origin/main commit `4d15e2f`) already contains the exact, per-cell `N_c`
multiplicity spectrum, `S_j` collision moments, and signed higher-order terms
`T_j` for all 15 nontrivial (lottery, k) cells. That fully resolves the
**existence and magnitude** question (is the residual zero or not, how big)
directly by inspection — no new lottery-scale computation was needed for
that part, and none was run.

It does **not** resolve **why** — the sealed schema (design-r1.md Section 6)
freezes only the *pairwise* ticket-intersection histogram
(`ticket_pair_intersection_histogram: {r: pair_count}`) and does not persist
any triple-wise quantity (no `|t_i ∩ t_j ∩ t_l|`), and the real B649/T539/
P638 Zone-1 portfolios themselves were never stored in the sealed JSON
(design-r1.md Section 11: "portfolios were not stored in the sealed result
JSONs"). So the sealed evidence alone cannot show *which* structural fact
about a ticket triple flips `S3` from zero to nonzero.

## 2. The bounded experiment (designed and executed in this task)

**Question:** given two tickets pairs with the *same* pairwise intersection
size `r`, does the *identity* of the shared numbers (all three pairs sharing
one common number — "hub" — versus three pairs sharing three mutually
distinct numbers — "triangle") change whether a triple-order collision (a
single winning combination hitting all three tickets at threshold `m`) is
possible?

**Scope, sized to stay trivially exact and bounded (packet Section 8):**

- Toy pools only, sized just large enough to fit each construction (11-18
  numbers), never the real 49/39/38-number pools.
- `k=3` tickets per case (the minimum nontrivial triple), not a full k=20
  ladder.
- Draw sizes fixed at the two *real* structural ratios under study —
  `draw_size=6, minimum_matches=3` (matches B649 and P638 Zone-1 exactly)
  and `draw_size=5, minimum_matches=3` (matches T539 exactly) — rather than
  the sealed unit test's toy `draw_size=3, minimum_matches=2`, so the result
  transfers directly to the real question instead of needing a further
  analogy argument.
- Full winning-space enumeration per case: `C(18,5)=8568` combinations at
  the largest, milliseconds of runtime, no Monte Carlo.
- No B649/T539/P638 constructor, portfolio, or real winning space touched.
  No sealed artifact read, written, or re-derived beyond citing its schema.

**Six cases run** (`reproduce_analysis.py::run_synthetic_confirmation`):

| label | pool | draw | m | max r | triple ∩ | deficit | threshold (3m-d) | bound met | S3 |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| D6M3_HUB_r1 | 16 | 6 | 3 | 1 | 1 | 2 | 3 | False | 0 |
| D6M3_TRIANGLE_r1 | 15 | 6 | 3 | 1 | 0 | 3 | 3 | True | 64 |
| D5M3_HUB_r1 | 13 | 5 | 3 | 1 | 1 | 2 | 4 | False | 0 |
| D5M3_TRIANGLE_r1 | 12 | 5 | 3 | 1 | 0 | 3 | 4 | False | 0 |
| D5M3_HUB_r2 | 11 | 5 | 3 | 2 | 2 | 4 | 4 | True | 27 |
| D5M3_TRIANGLE_r2 | 18 | 5 | 3 | 2 | 0 | 4 | 4 | True | 3 |

"deficit" is `sum(pairwise overlaps) − |triple intersection|`; "bound met"
is `deficit >= 3m−d`, the necessary condition derived in `report.md` Section
4. All six cases match the prediction exactly (`bound_met == (S3 > 0)` in
every row; the script asserts this and does not silently continue on a
mismatch).

**Result:** classification **A vs. B resolved as B** (packet Section 7) —
the deficit statistic (pairwise overlaps minus triple intersection) is a
necessary and, in all six tested cases, exactly-tight predictor of whether a
triple collision is *possible*; it is not tested here as a predictor of
*magnitude* beyond existence. At the exact B649/P638 ratio (`d=6,m=3`), hub
and triangle structures at the *same* `r=1` diverge (0 vs. 64); at the exact
T539 ratio (`d=5,m=3`), `r=1` is insufficient for either structure, so the
hub/triangle distinction is moot there — confirming T539's zero-residual
finding is a structural ceiling, not a lucky construction choice.

## 3. What remains open (not run, would need separate authorization)

The synthetic experiment shows the *mechanism class* is real at the correct
ratios. It does **not** show that the real, sealed B649/P638 Sidon and
Arm-B portfolios actually use hub-vs-triangle sharing in the proportions
that would fully account for the observed magnitude gap (e.g. `S3=6528`
for Sidon vs. `320` for Arm-B at `BIG_LOTTO k=10`). The real
`unique_number_coverage` field is consistent with triangle-type sharing at
`k=3` for both BIG_LOTTO and DAILY_539 Sidon (see `report.md` Section 6.3),
but that is an indirect, k=3-only check — it does not decompose the k=10..20
cells where multiple overlapping pairs coexist.

**If the Owner wants exact quantitative attribution** of the Sidon-vs-Arm-B
magnitude gap (not required for the primary classification, which is
already fully resolved): a follow-up task would regenerate the real
Arm-B and Sidon `k=20` portfolios once each per lottery through the
existing, unmodified canonical constructors (`greedy_min_overlap_portfolio`,
`sidon_shift_portfolio` family) and compute the triple-intersection size for
every ticket triple in each portfolio (`C(20,3)=1140` triples per lottery
per arm — cheap once the portfolio exists). The expensive part is
regenerating Arm-B itself: the sealed runtime log records approximately
774s (B649), 30s (T539), and 159s (P638 Zone-1), about 16 minutes total,
because the greedy constructor is what is expensive, not the triple-count.
No new winning-space enumeration is needed for this follow-up (it only
needs the ticket lists, not a re-scan of `C(49,6)` combinations), so it
would be materially cheaper than the original mechanism study, but it is
still expensive enough, and touches the canonical constructors closely
enough, that this task does not execute it unauthorized. `NEW_EXPERIMENT_REQUIRED: NO` in
the final report reflects that the *primary* classification does not need
this follow-up; this section exists so the option is visible if the Owner
wants the secondary magnitude question closed too.

## 4. Explicitly out of scope, per packet boundaries

Not designed and not run: anything touching P638 Zone-2, Arm-C, historical
draw data, Cohort V2 outcomes, or any change to a sealed Phase-5 artifact.
No production strategy, DB, or constructor code was modified.
