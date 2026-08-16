# STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1 — locked preregistration

Status: LOCKED before any native winning-space enumeration ｜ 2026-08-16 ｜
Strategy Matrix Phase 5, cross-lottery low-overlap geometry mechanism

`TASK_ID: STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_LOCK_EXECUTE_R1`,
Owner authorization
`AUTHORIZE_STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_LOCK_EXECUTE_R1`.
Locks and executes the design frozen in
`docs/research/strategy-matrix-phase5-low-overlap-geometry-mechanism-design-r1.md`
and `docs/research/low-overlap-geometry-mechanism-v1-execution-plan-schema.md`
(commit `1fb81414747864d31f91c6567ff81fe1ed50eb02`), which used the exact same
two-step design-then-lock-and-execute pattern the B649 frontier, T539, and
P638 Zone-1 cells already used. Three native lottery structures, two arms
(Sidon, Arm-B) each — Arm-C and P638 Zone-2 are explicitly `OUT_OF_SCOPE`
and have no counterpart in this task.

```text
PREREGISTRATION_LOCKED: YES
HASH_METHOD: LCJ-1 canonical bytes (lottolab.evidence.canonical_json), SHA-256
PREREGISTRATION_HASH_SHA256: 8400019909b7361ad65e172449588802498fdf5d424d37a87adc030f7cde34be
REAL_B649/T539/P638_MECHANISM_DECOMPOSITION: NOT_YET_RUN_AT_LOCK_TIME
```

## 0. Identity

```text
STUDY_ID:              STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1
HYPOTHESIS_FAMILY_ID:  DIVERSIFICATION
SOURCE_TYPE:           STRATEGY_MATRIX_NATIVE_MECHANISM
EVIDENCE_TYPE:         EXACT_COMBINATORIAL
DESIGN_COMMIT:         1fb81414747864d31f91c6567ff81fe1ed50eb02
CANONICAL_INPUT_COMMIT: 52b8353c932589c3f3ea8ff61fe7982c667cbbb0
CANONICAL_INPUT_TREE:   69e81767f701ea4f29f86bb0af34262191950c70
STARTING_CLASSIFICATION:
  NON_SIDON_LOW_OVERLAP_SUPPORTED_ACROSS_3_NATIVE_LOTTERY_STRUCTURES
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

## 1. Research question and disclosed prior observation

For each native lottery structure and each fixed exposure rung, does the
Arm-B advantage over Sidon arise from lower hit-event redundancy, and is
that reduction principally pairwise or dependent on higher-order hit
multiplicity?

The positive Arm-B-minus-Sidon coverage direction is already sealed across
all three structures and is not a new outcome-blind hypothesis. The
synthesis already observed a `k=5` peak in its field named
`REL_GAIN_OVER_SIDON`. Canonical code inspection (design doc §2) resolved
that field as `GAIN_OVER_RANDOM_RATIO_TO_SIDON = (Q_B-Q_R)/(Q_S-Q_R)`, not
`(Q_B-Q_S)/Q_S`. The peak is treated only as a known descriptive
motivation for mechanism tracing; it is not presented as a fresh discovery.

## 2. Frozen lottery, exposure, and event scope

```text
BIG_LOTTO:           pool=49, draw/ticket=6, event=M3_PLUS
DAILY_539:           pool=39, draw/ticket=5, event=M3_PLUS
POWER_LOTTO_ZONE1:   pool=38, draw/ticket=6, event=ZONE1_M3_PLUS
K_LADDER:            [1, 3, 5, 10, 15, 20]
PRIMARY_EVENT:       minimum_matches=3 only
SECONDARY_EVENTS:    NOT_RUN_BY_DEFAULT; cannot change primary decision
MONTE_CARLO:         NONE
HISTORICAL_DRAWS:    NOT_USED
P638_ZONE2:          OUT_OF_SCOPE
ARM_C:               OUT_OF_SCOPE
```

`k=1` is an identity/sanity boundary and is excluded from replicated
`k>1` decision predicates.

## 3. Frozen arms and input authority

Each lottery has exactly two fixed, deterministic, nested-prefix arms:

```text
ARM_S: canonical cyclic Sidon-shift portfolio
ARM_B: canonical deterministic greedy minimum-overlap portfolio
```

At execution, the maximum `k=20` portfolio is generated once per arm and
all smaller portfolios are exact prefixes (`portfolio_k == portfolio_20[:k]`,
never rebuilt independently). No copied algorithm, new tie-break, offset,
seed, random search, optimizer, or post-result adjustment.

```text
B649:        cyclic_sidon_shift.sidon_shift_portfolio,
             greedy_min_overlap_constructor.greedy_min_overlap_portfolio(49, 6, k)
T539:        cyclic_sidon_shift_t539.sidon_shift_portfolio,
             greedy_min_overlap_constructor_t539.greedy_min_overlap_portfolio_t539
P638 Zone1:  cyclic_sidon_shift_p638.sidon_shift_portfolio,
             greedy_min_overlap_constructor_p638_zone1.greedy_min_overlap_portfolio_p638_zone1
```

Sidon base sets (0-indexed, verified unchanged at execution time):

```text
B649:       (0, 1, 3, 7, 12, 20)
T539:       (0, 1, 3, 7, 12)
P638 Zone1: (0, 1, 3, 7, 17, 30)
```

The untracked duplicate `cyclic_sidon_shift_p638_zone1.py` flagged by a
prior report is not a canonical input and must not be read or imported.
B649's schema indirection is intentional and preserved: there is no
standalone sealed B649 Arm-B result; both arms are read from the existing
`DIVERSIFICATION_CONSTRUCTOR_FRONTIER_B649_V1` frontier artifact (keys
`q.a.3` = Sidon, `q.b.3` = Arm-B), without inspecting Arm C beyond the
file-level identity checks needed to load that artifact.

The canonical `origin/main` commit/tree, exact sealed input Git blobs, and
this locked preregistration hash must all be re-verified before the first
native constructor call. Any mismatch stops execution
(`STOP_LOW_OVERLAP_MECHANISM_INPUT_DRIFT`).

## 4. Frozen metric semantics

For exact coverage probabilities `Q_B`, `Q_S`, and random-expected `Q_R`:

```text
RELATIVE_LIFT_VS_RANDOM = (Q_B-Q_R)/Q_R
RELATIVE_COVERAGE_DELTA_VS_SIDON = (Q_B-Q_S)/Q_S
GAIN_OVER_RANDOM_RATIO_TO_SIDON = (Q_B-Q_R)/(Q_S-Q_R)
  only when Q_S-Q_R > 0; at k=1 -> NOT_APPLICABLE_K1
```

The sealed label `REL_GAIN_OVER_SIDON` maps only to
`GAIN_OVER_RANDOM_RATIO_TO_SIDON`. These three quantities remain distinct
and contextual; none replaces the primary integer mechanism endpoints. No
semantic change is permitted after this lock.

## 5. Frozen winner-multiplicity quantities

For a portfolio of `k` tickets and every winning combination `w`:

```text
c(w) = number of portfolio tickets hitting w at M3+
N_c  = count{w:c(w)=c}, c=0,...,k
K    = sum_{r=3..d} C(d,r)C(n-d,d-r)
I    = sum_w c(w) = sum_c c*N_c = k*K
COVERED    = sum_{c>=1}N_c
REDUNDANCY = sum_{c>=2}(c-1)N_c = I-COVERED
S_j        = sum_w C(c(w),j), j=1,...,k
COVERED    = S1-S2+S3-S4+...
```

All `N_c`, `S_j`, coverage, and redundancy values are exact integers. `Q`
is the reduced fraction `COVERED/C(n,d)`.

Delta direction is always Arm-B minus Sidon:

```text
DELTA_X = X_B-X_S
DELTA_COVERED = -DELTA_S2+DELTA_S3-DELTA_S4+...
DELTA_REDUNDANCY = -DELTA_COVERED
```

Because incidence is fixed (`S1_B=S1_S`), the redundancy direction is
algebraically equivalent to the already-sealed coverage direction once
exact `Q` is reproduced. It is a required mechanism restatement, not an
independent replication claim; `S2` and the higher-order terms provide the
new discrimination.

## 6. Frozen geometry and the independent S2 check

For each arm and `k`, record the complete ticket-pair intersection
histogram, max and exact mean pairwise overlap, legacy sparse overlap
profile, per-number reuse vector, unique-number coverage, exact population
variance plus presentation standard deviation of reuse, and duplicate count.

For pair intersection cardinality `r`, compute

```text
H_m(n,d,r) = sum C(r,a)C(d-r,b)C(d-r,c)C(n-2d+r,e)
```

over `a+b+c+e=d`, `a+b>=m`, and `a+c>=m`. If `h_r` is the ticket-pair
histogram, require

```text
S2_GEOMETRY = sum_r h_r H_m(n,d,r) = sum_w C(c(w),2) = S2_MULTIPLICITY
```

exactly at every cell. Duplicate count must be zero and the reuse vector
must sum to `k*d`.

## 7. Primary endpoints and signed decomposition

Persist `N_c`, `I`, `COVERED`, `REDUNDANCY`, full `S_j`, all geometry
fields, and all Arm-B-minus-Sidon deltas for every lottery and `k`.

```text
P   = PAIRWISE_COMPONENT = -DELTA_S2
T_j = (-1)^(j+1)DELTA_S_j for j>=3
H   = HIGHER_ORDER_RESIDUAL = sum_{j>=3}T_j
DELTA_COVERED = P+H
```

Also compute the cancellation-aware

```text
PAIRWISE_ABSOLUTE_CONTRIBUTION_SHARE = |P|/(|P|+sum_{j>=3}|T_j|)
```

or `NOT_APPLICABLE_ZERO_CHANGE` when the denominator is zero.

Per cell, assign exactly one descriptor:

```text
PAIRWISE_COLLISION_EXACTLY_SUFFICIENT
  iff P=DELTA_COVERED and every T_j=0

PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL
  iff P>0, share>1/2, and some T_j!=0

HIGHER_ORDER_MULTIPLICITY_PRIMARY_OR_PAIRWISE_OPPOSING
  otherwise
```

Every signed `T_j` is always reported. Any nonzero term is a material
combinatorial contribution; counts, probability points, residual, and
absolute contribution share disclose its size without an economic claim.

## 8. Frozen cross-lottery classifications

```text
REDUNDANCY_REDUCTION_REPLICATED
  iff REDUNDANCY_B < REDUNDANCY_S for every k>1 across all 3 structures.

REDUNDANCY_REDUCTION_NOT_UNIVERSAL
  otherwise; enumerate failures/equalities.

PAIRWISE_COLLISION_REDUCTION_REPLICATED
  iff S2_B < S2_S for every k>1 across all 3 structures.

PAIRWISE_COLLISION_NOT_UNIVERSALLY_EXPLANATORY
  otherwise; enumerate failures/equalities.

GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

Pairwise reduction and exact pairwise sufficiency are separate claims. A
positive replicated pairwise direction cannot suppress higher-order terms.
No all-pass classification is required.

## 9. Exact computation and failure gates

One lexicographic streaming pass per lottery evaluates both arms and all
ladder prefixes. It stores only multiplicity counters, not winners. All
derived quantities come from `N_c`; `S2` is recomputed independently from
pair geometry.

Before classification, exact reconstructed `Q_B` and `Q_S` must equal the
sealed source fractions at every cell (B649 from
`diversification-constructor-frontier-b649-v1-result.json` keys `q.a.3` /
`q.b.3`; T539 Sidon from `diversification-coverage-t539-v1-result.json`
key `q_sidon.3`, T539 Arm-B from
`greedy-min-overlap-constructor-t539-v1-result.json` key `q.b.3`; P638
Zone1 analogously from `diversification-coverage-p638-zone1-v1-result.json`
key `q_sidon.3` and `greedy-min-overlap-constructor-p638-zone1-v1-result.json`
key `q.b.3`). Execution stops without a result classification on any of:

- source commit/tree/blob or matrix-ID mismatch;
- preregistration hash mismatch;
- invalid/non-prefix/duplicate portfolio;
- `sum N_c != C(n,d)`;
- `I != k*K` or `REDUNDANCY != I-COVERED`;
- inclusion-exclusion mismatch;
- geometry-vs-multiplicity `S2` mismatch;
- reconstructed sealed-Q mismatch;
- invalid metric denominator.

No fallback, tolerance, float comparison, Monte Carlo rescue, or omitted
cell is permitted.

## 10. Computational feasibility

The exact winning-space total is `13,983,816 + 575,757 + 2,760,681 =
17,320,254` combinations. A two-arm, 20-ticket streaming pass has at most
`692,810,160` ticket-mask intersection checks and constant-size streaming
state. Existing sealed Arm-B constructor timings total about 16.1 minutes
serially (774.5s B649, 30.0s T539, 159.0s P638 Zone1), and generation is
expected to dominate. This is a bounded exact study; no sampling is
needed. Runtime is measured and reported but does not affect any
scientific classification.

## 11. Scope and no-rescue commitment

Arms, contract, k ladder, endpoints, evaluation method, comparator, and
classification/replication rules are locked by this file before any real
native-scale value is computed. No new constructor, no different event
threshold, no k-ladder change, no classification-rule change, no secondary
event promoted to primary, once results are visible. Secondary events,
Arm-C, Zone2, prediction, prize value, profit, and global optimization
cannot rescue or reinterpret the primary result. Any change required after
this point stops with `STOP_LOW_OVERLAP_MECHANISM_POST_LOCK_CHANGE_REQUIRED`
instead of being made silently.

```text
PREDICTIVE_ADVANTAGE:   NOT_TESTED
PRIZE_VALUE_ADVANTAGE:  NOT_TESTED
ECONOMIC_OPTIMALITY:    NOT_TESTED
GLOBAL_OPTIMUM_STATUS:  UNKNOWN
P638_ZONE2:             OUT_OF_SCOPE
ARM_C:                  OUT_OF_SCOPE
```

## 12. Preregistration hash

Computed over the LCJ-1 canonical JSON of every locked parameter above
(study/task identity, canonical input commit/tree, exposure ladder,
primary event, per-lottery pool/draw sizes, Sidon base sets, per-arm
constructor identities, sealed source matrix IDs/paths/blob SHA-1s and
their own preregistration hashes, metric-semantics formula strings) by
`tools/hash_preregistration_low_overlap_geometry_mechanism_v1.py`,
recorded in
`low-overlap-geometry-mechanism-v1-preregistration-hash.json`:

```text
preregistration_hash_sha256 = 8400019909b7361ad65e172449588802498fdf5d424d37a87adc030f7cde34be
```

`run_low_overlap_geometry_mechanism_v1.py` re-verifies this hash before
running and refuses to proceed on a mismatch.

```text
PREREGISTRATION_LOCKED: YES
LOCK_BLOCKERS: NONE
REAL_MECHANISM_DECOMPOSITION: NOT_YET_RUN_AT_LOCK_TIME
```
