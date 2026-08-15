# STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_DESIGN_R1 — design

Status: DESIGN COMPLETE — OWNER REVIEW REQUIRED ｜ 2026-08-15 ｜ no native
mechanism decomposition executed

```text
PREREGISTRATION_STATUS: DRAFT_NOT_LOCKED
REAL_B649_MECHANISM_DECOMPOSITION: NOT_RUN
REAL_T539_MECHANISM_DECOMPOSITION: NOT_RUN
REAL_P638_ZONE1_MECHANISM_DECOMPOSITION: NOT_RUN
NEW_MATRIX_SCIENTIFIC_CELL: NONE
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

This document designs the next Matrix-native combinatorial mechanism study.
It does not predict draws, measure profit, choose numbers, rerun a sealed
cell, or create a result.  The future question is why the deterministic,
algebra-free greedy minimum-overlap Arm-B covers more of the `M3+` winning
space than the Sidon reference in all three native lottery structures.

## 0. Identity and authority

```text
TASK_ID:              STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_DESIGN_R1
FUTURE_STUDY_ID:      STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1
HYPOTHESIS_FAMILY_ID: DIVERSIFICATION
SOURCE_TYPE_NOW:       STRATEGY_MATRIX_DESIGN
FUTURE_EVIDENCE_TYPE: EXACT_COMBINATORIAL
CANONICAL_STARTING_CLASSIFICATION:
  NON_SIDON_LOW_OVERLAP_SUPPORTED_ACROSS_3_NATIVE_LOTTERY_STRUCTURES
```

The design was derived from canonical `origin/main` commit
`52b8353c932589c3f3ea8ff61fe7982c667cbbb0`, tree
`69e81767f701ea4f29f86bb0af34262191950c70`.  The dirty, diverged local
`main` checkout was not used as scientific authority.  No `AGENTS.md` or
`AGENTS.override.md` applies in that canonical tree.

Owner authorization is design-only.  One later task may lock and execute
only after separate authorization.  Push, PR, merge, Arm-C replication,
P638 Zone2, historical draws, repair of sealed artifacts, and production or
prospective actions remain outside this task.

## 1. Sealed inputs read, not modified or re-executed

| Structure | Arm-B / Sidon authority | Canonical Git blob(s) |
|---|---|---|
| B649 | `diversification-constructor-frontier-b649-v1-{result.json,report.md}`; Arm A is Sidon, Arm B is `GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1` embedded in the four-arm cell | result `169df1649ff0b8247ef5c779e8104079ae574cf4`; report `60289b021f7859f0b92ccf42f38add16b9a31158` |
| T539 Arm-B | `greedy-min-overlap-constructor-t539-v1-{result.json,report.md}` | result `346544f3a644a3083ef9863bd7f35a345a50f531`; report `c542920fc8bc900dcdb8e148cde772d22b80a731` |
| T539 Sidon | `diversification-coverage-t539-v1-{result.json,report.md}` | result `013f4fbc1de6d62966b4c09e6f4bca5f5ae8a032`; report `30e92c82033c67cabc92f2ac17131c328106d739` |
| P638 Zone1 Arm-B | `greedy-min-overlap-constructor-p638-zone1-v1-{result.json,report.md}` | result `7665d8bd84bf0c5d9a9004afb29e61ff8d421ff5`; report `958a1a71b7169df352dd6a71ec196d63df7a90aa` |
| P638 Zone1 Sidon | `diversification-coverage-p638-zone1-v1-{result.json,report.md}` | result `f75ce278096d120ab368a058dba0f6262e9e8041`; report `ca7754640ecd41f70351330382106e28bcd4fa53` |
| Phase-5 synthesis | generator, result, and report for `strategy-matrix-phase5-non-sidon-low-overlap-cross-lottery-synthesis-v1` | generator `5d0ad0728486ee0030510158e9262d1dc3ee6763`; result `d9e5d86582e71ba86f8e48d091f31eaf824bf224`; report `2720632e56c56245a0ca18566aafda26d9d8b533` |

The source cells' sealed preregistration SHA-256 values are, respectively:
`02b3bc90256b94864eb35e1caf940bec79f83f0315671281a49b3c0cb05b9e71`
(B649 frontier),
`cb786aac3fc04ea2f1c302b37120831a2296869e94e7d397260d5745420ff8bd`
(T539 Arm-B),
`dd926b0ea045cb57be4e1cd10bc16e3d524e3b6acae5b34a805ed01f437e334e`
(T539 Sidon),
`e535caa323c1bb5ef027e5d8c5efa8b12fa83f59f83312ad1d9250d1e039f58b`
(P638 Zone1 Arm-B), and
`53e18558d07821460772a49f8358da3f2290b888dbde21c4497a0525c73cc992`
(P638 Zone1 Sidon).

The B649 schema indirection is intentional and preserved: there is no
standalone sealed B649 Arm-B result.  The future executor must read Arm A
and Arm B from the existing frontier artifact and must not inspect Arm C
beyond the file-level identity checks needed to load that artifact.

The canonical constructor entry points are immutable inputs:

- B649: `cyclic_sidon_shift.sidon_shift_portfolio` and
  `greedy_min_overlap_constructor.greedy_min_overlap_portfolio(49, 6, k)`.
- T539: `cyclic_sidon_shift_t539.sidon_shift_portfolio` and
  `greedy_min_overlap_constructor_t539.greedy_min_overlap_portfolio_t539`.
- P638 Zone1: `cyclic_sidon_shift_p638.sidon_shift_portfolio` and
  `greedy_min_overlap_constructor_p638_zone1.greedy_min_overlap_portfolio_p638_zone1`.

The untracked duplicate `cyclic_sidon_shift_p638_zone1.py` mentioned by a
prior report is not a canonical input and must not be read or imported.

## 2. Metric-semantics gate — resolved from canonical synthesis code

The formulas were verified directly in
`tools/generate_strategy_matrix_phase5_non_sidon_low_overlap_synthesis.py`,
not inferred from the report label.  In `analyze_cell`, the generator
re-derives `delta_random_b = Q_B-Q_R`, `delta_sidon = Q_B-Q_S`, and
`delta_random_sidon = Q_S-Q_R`, then computes the two existing relative
series.

The future study freezes three distinct names:

```text
RELATIVE_LIFT_VS_RANDOM = (Q_B - Q_R) / Q_R

RELATIVE_COVERAGE_DELTA_VS_SIDON = (Q_B - Q_S) / Q_S

GAIN_OVER_RANDOM_RATIO_TO_SIDON = (Q_B - Q_R) / (Q_S - Q_R)
                                      only when Q_S - Q_R > 0
```

Semantic mapping of the sealed report is exact:

```text
sealed REL_LIFT_RANDOM     -> RELATIVE_LIFT_VS_RANDOM
sealed REL_GAIN_OVER_SIDON -> GAIN_OVER_RANDOM_RATIO_TO_SIDON
sealed DELTA_SIDON         -> Q_B - Q_S (an absolute probability delta)
```

`REL_GAIN_OVER_SIDON` does **not** mean
`RELATIVE_COVERAGE_DELTA_VS_SIDON`.  Sealed artifacts remain unchanged;
the new unambiguous name is used only in this design and any future cell.
At `k=1`, `Q_B=Q_S=Q_R`, so
`GAIN_OVER_RANDOM_RATIO_TO_SIDON` is exact `0/0` and must be serialized as
`NOT_APPLICABLE_K1`.

The already-observed cross-lottery `k=5` peak belongs specifically to
`GAIN_OVER_RANDOM_RATIO_TO_SIDON`.  It is a disclosed starting observation,
not a newly discovered or outcome-blind endpoint.  The mechanism study may
describe which exact collision terms co-vary with that known shape, but it
must not relabel the peak as belonging to either of the other two metrics.

## 3. Research question and frozen scope

For each fixed lottery structure, `k`, and primary `M3+` event, is Arm-B's
coverage advantage over Sidon explained by reduced duplicate hit incidence
across winning combinations?  More specifically:

1. Is total redundancy smaller for Arm-B at every `k>1` in all three
   structures?
2. Is the pairwise collision moment `S2` smaller for Arm-B at every `k>1`
   in all three structures?
3. After the exact pairwise term is removed, do signed higher-order
   collision moments make a nonzero or dominant contribution?

```text
LOTTERIES:    B649, T539, P638 Zone1
K_LADDER:     {1, 3, 5, 10, 15, 20}
PRIMARY:      M3+ only
SECONDARY:    NOT_RUN_BY_DEFAULT
ENUMERATION:  exact combinations only
MONTE_CARLO:  NONE
DRAW_HISTORY: NOT_USED
P638_ZONE2:   OUT_OF_SCOPE
ARM_C:        OUT_OF_SCOPE
```

`M4+`, `M5+`, and `M6` are not needed for the primary mechanism decision.
Their already-known structural behavior does not authorize expanding this
cell.  A lock amendment may add them only as clearly secondary diagnostics;
they can never change the primary classification.

## 4. Winner-level mechanism identities

Fix a lottery with pool size `n`, draw/ticket size `d`, threshold `m=3`,
portfolio `T={t_1,...,t_k}`, and complete winning space
`W=C([n],d)`.  Define the ticket hit event

```text
E_i = {w in W : |w intersection t_i| >= m}
c(w) = count{i : w in E_i}
N_c  = count{w : c(w)=c}, for c=0,...,k
```

Pool symmetry makes every ticket's event size identical:

```text
K_M3+ = sum_{r=3..d} C(d,r) C(n-d,d-r)
I     = sum_w c(w) = sum_c c*N_c = k*K_M3+
```

Therefore coverage can differ only through repeated incidence:

```text
COVERED    = sum_{c>=1} N_c
REDUNDANCY = sum_{c>=2} (c-1)N_c
           = I - COVERED
Q          = COVERED / C(n,d)
```

The binomial collision moments are

```text
S_j = sum_w C(c(w),j), j=1,...,k
S_1 = I
COVERED = S_1 - S_2 + S_3 - S_4 + ... + (-1)^(k+1)S_k
```

All quantities are nonnegative integers until the final exact `Fraction`
conversion for `Q`.  No floating-point value is load-bearing.

For every Arm-B/Sidon comparison, delta direction is frozen as

```text
DELTA_X = X_B - X_S
```

Because `S1_B=S1_S`,

```text
DELTA_COVERED = -DELTA_S2 + DELTA_S3 - DELTA_S4 + ...
DELTA_REDUNDANCY = -DELTA_COVERED
```

This is the primary mechanism decomposition.  A positive
`DELTA_COVERED` is exactly equivalent to a negative `DELTA_REDUNDANCY`.
Consequently, if the future exact-Q cross-check reproduces the already
sealed `Q_B>Q_S` direction, `REDUNDANCY_REDUCTION_REPLICATED` is an
algebraic restatement of that sealed coverage result, not independent new
evidence.  The genuinely discriminating outputs are `S2`, the signed
higher-order terms, and their geometry link.

## 5. Exact geometry-to-S2 link

For two `d`-number tickets with intersection cardinality `r`, partition the
pool into shared, left-only, right-only, and outside-union regions of sizes

```text
r, d-r, d-r, n-2d+r.
```

Let `a,b,c,e` be the winning draw's counts from those four regions.  The
number of winning combinations that hit both tickets at threshold `m` is

```text
H_m(n,d,r) = sum C(r,a) C(d-r,b) C(d-r,c) C(n-2d+r,e)
```

over exactly the tuples satisfying

```text
a+b+c+e=d, a+b>=m, a+c>=m,
0<=a<=r, 0<=b,c<=d-r, 0<=e<=n-2d+r.
```

If `h_r` is the number of unordered ticket pairs whose ticket
intersection has size `r`, then the geometry route gives

```text
S2_GEOMETRY = sum_r h_r * H_m(n,d,r).
```

The winner-multiplicity route independently gives

```text
S2_MULTIPLICITY = sum_w C(c(w),2).
```

Every future `(lottery, arm, k)` cell must assert exact integer equality:

```text
S2_GEOMETRY == S2_MULTIPLICITY
```

This check is stronger than correlating mean overlap with coverage.  It
proves precisely how the full ticket-pair intersection histogram induces
the pairwise hit-event collision count.  It does not assume that `S2` alone
determines the union; the toy counterexample in §12 proves that it need not.

## 6. Frozen geometry quantities

For both Arm-B and Sidon at every `k`, record:

- `ticket_pair_intersection_histogram`: complete integer counts `h_r` for
  `r=0,...,d`; zero bins may be omitted only in the serialized sparse map.
- `max_pairwise_overlap = max r` over ticket pairs, or `0` at `k=1`.
- `mean_pairwise_overlap = sum_r r*h_r / C(k,2)` as an exact fraction, or
  `0/1` at `k=1`.
- `overlap_profile`: the legacy sparse count-map representation of the same
  histogram; it must equal the histogram after zero bins are removed.
- `per_number_reuse_vector = (u_1,...,u_n)`, where `u_x` is the number of
  portfolio tickets containing number `x`; it must sum to `k*d`.
- `unique_number_coverage = count{x:u_x>0}`.
- `reuse_dispersion`: population standard deviation
  `sqrt((1/n) sum_x (u_x-kd/n)^2)`.  Persist the population variance as an
  exact fraction; any square-root float is presentation-only.
- `duplicate_count = k - count(distinct tickets)`; must be zero or execution
  stops before classification.

The pair histogram and overlap profile are intentionally linked rather than
silently treated as two unrelated metrics.  The reuse vector is the source
for both unique coverage and reuse dispersion.

## 7. Primary endpoints

For each of the 15 nontrivial cells (`3 lotteries * 5 k values >1`), plus
the `k=1` sanity boundary, persist:

1. Full `N_c` for each arm, including `N_0` and explicit zero bins through
   `c=k`.
2. `K_M3+`, `I`, `COVERED`, `REDUNDANCY`, and exact `Q` for each arm.
3. Full `S_j`, `j=1,...,k`, including explicit zero high-order terms.
4. `DELTA_COVERED`, `DELTA_REDUNDANCY`, and every `DELTA_S_j`.
5. `PAIRWISE_COMPONENT = -DELTA_S2`.
6. Each signed higher-order term
   `T_j = (-1)^(j+1) DELTA_S_j`, `j>=3`.
7. `HIGHER_ORDER_RESIDUAL = sum_{j>=3} T_j`.
8. All frozen geometry fields and the exact `S2` geometry cross-check.

The three normalized coverage metrics from §2 are contextual secondary
outputs.  They must be computed from exact `Q` values and may not replace
the count-scale mechanism endpoints.

## 8. Pairwise versus higher-order interpretation

The additive decomposition is frozen as

```text
P = PAIRWISE_COMPONENT = -DELTA_S2
T_j = (-1)^(j+1) DELTA_S_j, j>=3
H = HIGHER_ORDER_RESIDUAL = sum T_j
DELTA_COVERED = P + H
```

To prevent cancellation among higher-order terms from being hidden, also
report

```text
PAIRWISE_ABSOLUTE_CONTRIBUTION_SHARE =
  |P| / (|P| + sum_{j>=3}|T_j|)
```

when the denominator is positive; otherwise report `NOT_APPLICABLE_ZERO_CHANGE`.
The phrase “pairwise is primary” has the exact threshold `share > 1/2` and
also requires `P>0`, so it cannot be assigned merely because a signed ratio
is large after cancellation.

Per cell, report one mechanism descriptor:

```text
PAIRWISE_COLLISION_EXACTLY_SUFFICIENT
  if P == DELTA_COVERED and every T_j == 0

PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL
  if P > 0, share > 1/2, and at least one T_j != 0

HIGHER_ORDER_MULTIPLICITY_PRIMARY_OR_PAIRWISE_OPPOSING
  otherwise
```

“Material higher-order” is combinatorial, not economic: any nonzero exact
`T_j` changes at least one winning-combination incidence and is reported.
Its practical size remains visible in counts, probability points, the signed
residual, and the cancellation-aware contribution share.  This avoids an
unstated percentage threshold and does not erase a small exact contribution.

The descriptor is per cell; an aggregate may be `MIXED_BY_LOTTERY_OR_K`.
The mandatory replicated classifications below remain separate, so no
all-pass narrative is forced.

## 9. Frozen decision outputs

```text
REDUNDANCY_REDUCTION_REPLICATED
  iff REDUNDANCY_B < REDUNDANCY_S for every k>1 in all three structures.

REDUNDANCY_REDUCTION_NOT_UNIVERSAL
  otherwise; list every failing/equal cell.

PAIRWISE_COLLISION_REDUCTION_REPLICATED
  iff S2_B < S2_S for every k>1 in all three structures.

PAIRWISE_COLLISION_NOT_UNIVERSALLY_EXPLANATORY
  otherwise; list every failing/equal cell.

GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

Always report every signed higher-order term separately, even when pairwise
reduction replicates.  `PAIRWISE_COLLISION_REDUCTION_REPLICATED` means the
pairwise direction is universal; it does not by itself claim exact or total
mechanistic sufficiency.

At `k=1`, both portfolios contain one event: `N_c`, coverage, and redundancy
must agree; `S_j=0` for `j>=2`; the cell is a sanity check and is excluded
from the replicated decision predicates.

## 10. Deterministic future execution

The normative plan and serialized field schema are in
`low-overlap-geometry-mechanism-v1-execution-plan-schema.md`.  In summary:

1. Pin a clean future canonical `origin/main`, verify all input IDs and
   locked preregistration hash, and stop on drift.
2. Build each Arm-B maximum `k=20` portfolio exactly once through the
   existing canonical constructor; build each Sidon `k=20` portfolio once;
   obtain ladder portfolios by prefix slices only.
3. Hash the ordered portfolios and assert ticket validity, prefix nesting,
   and zero duplicates.
4. Stream every winning combination in lexicographic order.  For both arms,
   compute all 20 hit indicators once and increment `N_c` for each ladder
   prefix.  Do not store the winning combinations.
5. Derive all identities from `N_c`; independently derive `S2` from ticket
   pair geometry.
6. Assert reconstructed `Q_B` and `Q_S` equal the already-sealed exact
   fractions at every `(lottery,k)` before applying any new classification.
7. Serialize exact integers/fractions with sorted keys, then render a report.

Any identity mismatch, sealed-Q mismatch, duplicate ticket, wrong input ID,
or denominator-gate failure stops execution with no scientific classification.

## 11. Computational feasibility

The complete winning-space population is

```text
B649:        C(49,6) = 13,983,816
T539:        C(39,5) =    575,757
P638 Zone1: C(38,6) =  2,760,681
TOTAL:                  17,320,254 winning combinations
```

A straightforward two-arm, 20-ticket streaming pass performs at most
`17,320,254 * 40 = 692,810,160` bit-intersection/`bit_count` checks, while
retaining only small count arrays.  The sealed T539 and P638 Arm-B runs
already measured two-arm winning-space enumeration at 2.98 s and 16.69 s,
respectively, although the future multiplicity pass must scan all tickets
and therefore must not claim those timings as its own benchmark.

Regenerating the immutable Arm-B portfolios is expected to dominate serial
runtime because portfolios were not stored in the sealed result JSONs.  The
sealed measured constructor times were approximately 774.5 s (B649), 30.0 s
(T539), and 159.0 s (P638 Zone1), totaling about 16.1 minutes before the new
enumeration.  This remains practical as one bounded exact run; no Monte Carlo
shortcut is justified.

Memory is streaming and bounded: for each arm/lattice prefix, `N_c` needs
only `k+1` integers.  Across the six ladder rungs that is 60 counters per
arm per lottery, plus ticket masks, geometry, and derived moments.  No
winner list, historical database, or per-winner record is retained.

## 12. Toy/synthetic formula verification in this design

`tests/unit/test_low_overlap_geometry_mechanism.py` exercises only a
7-number toy pool with 3-number tickets and threshold 2.  It verifies:

- all three relative metrics are exact and numerically distinct;
- the gain-over-random ratio rejects a nonpositive Sidon-vs-random
  denominator;
- `H_m(n,d,r)` matches direct winner enumeration for `r=0,1,2,3`;
- reuse vector, exact mean overlap, exact population variance, unique
  coverage, and duplicate count semantics;
- `I=k*K`, `REDUNDANCY=I-COVERED`, all `S_j`, and inclusion-exclusion;
- `S2_GEOMETRY == S2_MULTIPLICITY` exactly;
- two synthetic portfolios can have the identical pair histogram
  `{r=1: 3}` and identical `S2=12`, yet different `S3` (`0` vs `1`) and
  different coverage (`27` vs `28`).

That last fixture is the design's explicit guard against assuming answer A.
No B649, T539, or P638 constructor, portfolio, or winning space is invoked
by the tests.

## 13. Remaining pre-lock issues

```text
SCIENTIFIC_DEFINITION_GAPS: NONE IDENTIFIED
INPUT_MAPPING_GAPS:        NONE IDENTIFIED
METRIC_SEMANTICS_GAPS:     NONE IDENTIFIED
COMPUTATIONAL_BLOCKER:     NONE IDENTIFIED
OWNER_REVIEW:              REQUIRED
LOCK_AUTHORIZATION:        REQUIRED AND NOT GRANTED
EXECUTION_AUTHORIZATION:   REQUIRED AND NOT GRANTED
```

At lock time, the Owner must approve the draft byte-for-byte (or require a
new draft), authorize its hash, and authorize creation of the execution
script/result/report/attempt ledger.  Secondary thresholds remain excluded
by default; adding them is a scope amendment, not an unresolved ambiguity.

## 14. Artifacts created by this design task

```text
docs/research/strategy-matrix-phase5-low-overlap-geometry-mechanism-design-r1.md
docs/research/low-overlap-geometry-mechanism-v1-preregistration-draft.md
docs/research/low-overlap-geometry-mechanism-v1-execution-plan-schema.md
src/lottolab/research/low_overlap_geometry_mechanism.py
tests/unit/test_low_overlap_geometry_mechanism.py
```

No hash, locked preregistration, execution tool, result JSON, result report,
attempt ledger, Matrix scientific cell, or historical-data artifact is
created.

## 15. No-rescue and claim boundary

The future execution may not add a constructor, change the delta direction,
drop a failing `k`, change the `M3+` threshold, reinterpret
`REL_GAIN_OVER_SIDON`, suppress a signed higher-order term, or use a
secondary event to rescue the primary classification after results are
visible.  A changed design requires a new draft and Owner review before any
native enumeration.

```text
PREDICTIVE_ADVANTAGE:   NOT_TESTED
PRIZE_VALUE_ADVANTAGE:  NOT_TESTED
ECONOMIC_OPTIMALITY:    NOT_TESTED
GLOBAL_OPTIMUM_STATUS:  UNKNOWN
P638_ZONE2:             OUT_OF_SCOPE
ARM_C:                  OUT_OF_SCOPE
REAL_MECHANISM_RESULTS: NOT_RUN
```

```text
FINAL_CLASSIFICATION:
LOW_OVERLAP_GEOMETRY_MECHANISM_DESIGN_READY_FOR_OWNER_REVIEW
```
