# MATRIX_PHASE8_METHOD_F_REUSE_DISPERSION_TIEBREAK_B649_V1 — locked preregistration

Status: LOCKED before any Candidate F B649-scale coverage inspection ｜
2026-08-18 ｜ B649 (Structure A) only

`TASK_ID: MATRIX_PHASE8_METHOD_F_DISCOVERY_R1`, Owner authorization
`AUTHORIZE_MATRIX_PHASE8_METHOD_F_DISCOVERY_R1`. There is no separate prior
design-phase commit for this task: the Owner's task packet in this
conversation is the design authority, verified against canonical
`origin/main` `9141649ceaad5d5261443606cdd681b93a8c5549`.

```text
PREREGISTRATION_LOCKED: YES
HASH_METHOD: LCJ-1 canonical bytes (lottolab.evidence.canonical_json), SHA-256
PREREGISTRATION_HASH_SHA256:  32f673d601feadd54d8019a0942358ce1aaf0ef7cda6e7423a5bf9bf85824263
LOCK_SCOPE: THIS_EXACT_CANDIDATE_F_VARIANT_ONLY
B649_CANDIDATE_F_COVERAGE: NOT_YET_RUN_AT_LOCK_TIME
REFERENCE_E_RERUN: FORBIDDEN
T539_EXECUTION: NOT_RUN
P638_EXECUTION: NOT_RUN
PARAMETER_RESCUE: FORBIDDEN
POST_RESULT_TUNING: FORBIDDEN
```

## 0. Identity

```text
STUDY_ID:                STRATEGY_MATRIX_PHASE8_METHOD_F_REUSE_DISPERSION_TIEBREAK_V1
TASK_ID:                 MATRIX_PHASE8_METHOD_F_DISCOVERY_R1
REFERENCE_E_CONSTRUCTOR_ID: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
CANDIDATE_F_CONSTRUCTOR_ID: GREEDY_MINMAX_SUM_THEN_REUSE_DISPERSION_V1
HYPOTHESIS_FAMILY_ID:    REUSE_DISPERSION_TIEBREAK
SOURCE_TYPE:             STRATEGY_MATRIX_NATIVE
EVIDENCE_TYPE:           EXACT_COMBINATORIAL
CANONICAL_INPUT_COMMIT:  9141649ceaad5d5261443606cdd681b93a8c5549
CANONICAL_INPUT_TREE:    26f7dbb950cf7290f98ee08d436ad214582fb285
GLOBAL_OPTIMUM_STATUS:   UNKNOWN
```

## 1. Research question

Reference E already minimizes, in order, incremental max pairwise overlap
and then incremental sum of pairwise overlaps -- exactly the sealed `S2`
mechanism -- breaking any remaining tie by arbitrary lexicographic scan
order. Does inserting a *specific* geometric tiebreak among tickets
Reference E already considers tied -- prefer the one leaving per-number
reuse least concentrated -- change exact B649 `M3+` coverage? This is a
new mechanism layered strictly on top of Reference E's own two
coordinates, not a parameter rescue of E and not a reopening of the
Phase-6 decision to keep `S3` out of the constructor's scored objective:
Candidate F's reuse coordinates can never override `(max, sum)`, so it
cannot trade away Reference E's sealed mechanism to chase reuse
dispersion.

## 2. Frozen scope

```text
STRUCTURE:          STRUCTURE_A_B649 only. No Structure B (T539) / Structure C
                     (P638 Zone-1) replication in this task.
LOTTERY:             BIG_LOTTO  pool=49, draw=6
K_LADDER:            [10, 15, 20]
PRIMARY_EVENT:       M3_PLUS (minimum_matches=3)
SECONDARY_EVENTS:    NOT_RUN
MONTE_CARLO:         NONE
HISTORICAL_DRAWS:    NOT_USED
LEARNED_PARAMETERS:  NONE
WEIGHTS:             NONE
RANDOMNESS:          NONE
RESTARTS:            NONE
POST_RESULT_TUNING:  FORBIDDEN
```

## 3. Frozen comparators

```text
REFERENCE_E = greedy_minmax_then_sum_overlap_constructor
              .greedy_minmax_then_sum_overlap_portfolio(49, 6, k)
              -- NOT rerun. Sealed Q_E(k) copied verbatim from
              docs/research/matrix-native-results/
              constructor-frontier-next-generation-v1-result.json
              (blob 70148c6c59baea1087126bf95a009eb4d291149c), whose own
              locked preregistration hash is
              ea014c2204e1fa77041329fc60d172502589bbc02c7922c63e78120e582080c1.
              Reference E's source file
              (src/lottolab/research/greedy_minmax_then_sum_overlap_constructor.py)
              is confirmed unchanged at blob
              b141a3c881252135b581123761db820108e2f046.

CANDIDATE_F = GREEDY_MINMAX_SUM_THEN_REUSE_DISPERSION_V1, generated fresh
              in this task.

RANDOM (Q_RANDOM) = exact_coverage_baseline.exact_random_portfolio_coverage
              (49, 6, 3, k) -- closed-form exact Fraction, no portfolio,
              no simulation.
```

Sealed exact `M3+` fractions for Reference E (copied, not recomputed):

| k  | Q_E (sealed)      |
|---:|:------------------|
| 10 | 212295/1165318    |
| 15 | 927161/3495954    |
| 20 | 17379/50666       |

Sealed Reference E geometry (copied, not recomputed) at the same k, under
the sealed `max_pairwise_overlap <= 1` regime (so `sum_pairwise_overlap`
equals the pair-intersection-one count):

| k  | max_pairwise_overlap (E) | sum_pairwise_overlap (E) | duplicate_count (E) |
|---:|:------------------------:|:------------------------:|:---------------------:|
| 10 | 1                         | 11                        | 0                      |
| 15 | 1                         | 43                        | 0                      |
| 20 | 1                         | 93                        | 0                      |

## 4. Frozen constructor: Candidate F

```text
CANDIDATE_F_CONSTRUCTOR_ID: GREEDY_MINMAX_SUM_THEN_REUSE_DISPERSION_V1
ENTRY_POINT:
  lottolab.research.greedy_minmax_sum_then_reuse_dispersion_constructor
    .greedy_minmax_sum_then_reuse_dispersion_portfolio(pool_size, draw_size, ticket_count)
```

### 4.1 Constructor rule

For each unused legal ticket, minimize lexicographically:

1. incremental max pairwise overlap against the portfolio so far
2. incremental sum of pairwise overlaps against the portfolio so far
3. resulting peak per-number reuse if the candidate were appended
4. resulting `SUM_i C(reuse_i, 3)` over the whole pool if the candidate
   were appended
5. candidate lexicographic order

Coordinates 1-2 and 5 are exactly Reference E's own key. Coordinates 3-4
are new and can only ever discriminate among tickets already tied on
Reference E's own `(max, sum)` -- they can never make a worse `(max,
sum)` win. Ticket 0 is the lexicographically first `draw_size`-subset,
identical to Reference E's, because every candidate ties trivially on all
four non-final coordinates against an empty portfolio.

### 4.2 What Candidate F is not

No weight, no random restart, no historical draw, no outcome label, no
learned parameter, no post-result coefficient. It does not score `S3`
directly and does not reopen the Phase-6 decision to exclude `S3` from
the constructor objective -- the reuse coordinates are a tiebreak *within*
Reference E's own equivalence classes, never an independent scored
objective that could outrank `(max, sum)`.

## 5. Frozen metrics

For every `k` in `{10, 15, 20}`, report exactly:

```text
Q_F, Q_E (copied), Q_RANDOM (closed-form)
DELTA_F_VS_E = Q_F - Q_E
DELTA_F_VS_RANDOM = Q_F - Q_RANDOM
```

Geometry, exact, for Candidate F's own portfolio at each `k`:

```text
max_pairwise_overlap, sum_pairwise_overlap, peak_reuse,
SUM_C_REUSE_3, reuse_histogram, unique_count, duplicate_count
```

`reuse_histogram` is the multiset of per-number reuse counts expressed as
`{reuse_count: number_of_pool_numbers_with_that_count}`. All arithmetic is
exact (`fractions.Fraction` / Python arbitrary-precision `int`); no Monte
Carlo, no floating-point coverage value.

## 6. Advance gate

`METHOD_F_ADVANCE_GATE` passes iff all hold:

```text
1. Q_F(k) >= Q_E(k)                for every k in {10, 15, 20}
2. Q_F(20) > Q_E(20)
3. duplicate_count(k) == 0          for every k in {10, 15, 20}
4. GEOMETRY_NOT_WORSE(k)            for every k in {10, 15, 20}, where
   GEOMETRY_NOT_WORSE(k) means:
     Candidate F's max_pairwise_overlap(k) <= sealed E max_pairwise_overlap(k)
     AND
     Candidate F's sum_pairwise_overlap(k) <= sealed E sum_pairwise_overlap(k)
   (clause 1 claims Q_F(k) >= Q_E(k), i.e. non-inferiority, at all three
   rungs, so "where superiority is claimed" is read as this full ladder)
5. REPRODUCIBILITY: a second, independent, fresh-process invocation of
   greedy_minmax_sum_then_reuse_dispersion_portfolio(49, 6, 20) returns a
   byte-identical tuple (and therefore an identical portfolio SHA-256) to
   the first invocation.
```

Pass classification: `METHOD_F_STRUCTURE_A_ADVANCE`,
`CROSS_STRUCTURE_REPLICATION_ELIGIBLE: YES`.

Fail classification: `DO_NOT_ADVANCE_THIS_EXACT_METHOD_F_VARIANT`,
`CROSS_STRUCTURE_REPLICATION_ELIGIBLE: NO`. Failure closes only this exact
variant; it does not retire reuse-dispersion tiebreak research generally,
and it must not be tuned or rescued.

## 7. Claim boundary

```text
ALLOWED: exact deterministic B649 combinatorial coverage/geometry
         comparison of Candidate F against Reference E and against the
         exact random baseline.
NOT_ESTABLISHED: predictive advantage, profit/economic value, universal
         portability, global optimum, untested structures (T539/P638),
         runtime suitability.
GLOBAL_OPTIMUM_STATUS: UNKNOWN
RUNTIME_PROMOTION: NOT_AUTHORIZED
```

## 8. No-rescue

The locked constructor key (all five coordinates and their order), the
k-ladder, the primary event, the sealed Reference E comparator values, and
the advance gate must not change after any native `Q_F` is seen. Reference
E may not be rerun. T539/P638 may not start in this task regardless of the
gate outcome (cross-structure replication, if eligible, is a separate
future task). A failed gate closes this exact Candidate F variant only and
must not be tuned or rescued.
