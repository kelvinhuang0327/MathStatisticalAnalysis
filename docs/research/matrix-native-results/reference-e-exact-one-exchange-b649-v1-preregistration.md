# MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_B649_V1 — locked preregistration

Status: LOCKED before any native B649 1-exchange execution ｜ 2026-08-27 ｜ B649 (Structure A) only

`TASK_ID: STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_R1`, Owner authorization `AUTHORIZE_STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_R1`. Verified against canonical `origin/main` @ `79948c6ba3b7195b85e11c690c50b70bf185b1d2` (tree `5e5c0c94550c0444ddb1e7ebd994c4223c48ca5a`).

```text
PREREGISTRATION_LOCKED: YES
HASH_METHOD: SHA-256 of frozen preregistration markdown document
LOCK_SCOPE: THIS_EXACT_ONE_EXCHANGE_NEIGHBORHOOD_STUDY_ONLY
NATIVE_B649_ONE_EXCHANGE_EXECUTION: NOT_YET_RUN_AT_LOCK_TIME
REFERENCE_E_CONSTRUCTOR: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
CANDIDATE_SEARCH: REFERENCE_E_BEST_1EXCHANGE_EXACT_COVERAGE_V1
T539_EXECUTION: NOT_RUN
P638_EXECUTION: NOT_RUN
PARAMETER_RESCUE: FORBIDDEN
SECOND_EXCHANGE: FORBIDDEN
POST_RESULT_TUNING: FORBIDDEN
```

## 0. Identity

```text
STUDY_ID:                     STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_V1
TASK_ID:                      STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_R1
REFERENCE_E_CONSTRUCTOR_ID:   GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
CANDIDATE_ID:                 REFERENCE_E_BEST_1EXCHANGE_EXACT_COVERAGE_V1
HYPOTHESIS_FAMILY_ID:         EXACT_LOCAL_NEIGHBORHOOD_REFINEMENT
SOURCE_TYPE:                  STRATEGY_MATRIX_NATIVE
EVIDENCE_TYPE:                EXACT_COMBINATORIAL
CANONICAL_BASE_COMMIT:        79948c6ba3b7195b85e11c690c50b70bf185b1d2
CANONICAL_BASE_TREE:          5e5c0c94550c0444ddb1e7ebd994c4223c48ca5a
GLOBAL_OPTIMUM_STATUS:        UNKNOWN
```

## 1. Research question

Method E (`GREEDY_MINMAX_THEN_SUM_OVERLAP_V1`) was designated as the default research reference constructor in Phase 7. Does the sealed Method E portfolio possess any strictly better exact one-number-exchange neighbor at B649 `k in {10, 15, 20}`?

This study exhaustively enumerates the complete 1-number-exchange neighborhood of Reference E at each tested rung `k`, evaluates exact combinatorial `M3+` coverage across all unique legal neighbors, and determines whether Reference E is a local optimum under 1-number exchanges or if an exact 1-exchange improvement exists.

## 2. Frozen scope

```text
STRUCTURE:          STRUCTURE_A_B649 only. No Structure B (T539) or Structure C (P638) execution.
LOTTERY:            BIG_LOTTO (pool=49, draw=6)
K_LADDER:           [10, 15, 20]
PRIMARY_EVENT:      M3_PLUS (minimum_matches=3)
SECONDARY_EVENTS:   NOT_RUN
MONTE_CARLO:        NONE
HISTORICAL_DRAWS:   NOT_USED
LEARNED_PARAMETERS: NONE
WEIGHTS:            NONE
RANDOMNESS:         NONE
RESTARTS:           NONE
SECOND_EXCHANGE:    FORBIDDEN
POST_RESULT_TUNING: FORBIDDEN
```

## 3. Reference Method E baseline authority

Method E is deterministically regenerated and verified against the sealed Phase-7 authority (`docs/research/matrix-native-results/constructor-frontier-next-generation-v1-result.json`):

- 20-ticket portfolio SHA-256: `ac2198cf057b10ac8bd05e53519e5901999fe0b6beb4c35abb59c92a60ff60ff`
- Exact sealed `M3+` fractions:
  - `Q_E(10) = 212295/1165318`
  - `Q_E(15) = 927161/3495954`
  - `Q_E(20) = 17379/50666`

## 4. One-exchange neighborhood specification

For each `k` in `{10, 15, 20}`:
1. Reference portfolio `P_E(k)` is the length-`k` prefix of Method E.
2. Neighborhood enumeration:
   - For each slot `i` in `0..k-1`:
     - Remove exactly one number `r` from ticket `P_E[i]`.
     - Add exactly one number `a` from `1..49` not in `P_E[i]`.
     - Sort the mutated ticket ascending.
     - Reject duplicate tickets (if mutated ticket is already in `P_E`).
     - Form neighbor portfolio `P' = tuple(sorted(P_E[:i] + (mutated,) + P_E[i+1:]))`.
   - De-duplicate equivalent resulting portfolios.
3. Exact coverage evaluation:
   - Evaluate exact `M3+` coverage `Q(P')` for every unique neighbor using `lottolab.research.exact_coverage_fast_evaluator.coverage_with_base`.
4. Selection:
   - Select neighbor `P*` achieving maximum `Q(P')`.
   - Break exact coverage ties by choosing the lexicographically smallest complete portfolio `P*`.
   - Record exact `delta_vs_reference_e = Q(P*) - Q_E(k)`.

## 5. Classification and advance gate

Per-k classification:
- `ONE_EXCHANGE_IMPROVEMENT_FOUND` if `delta_vs_reference_e > 0`
- `REFERENCE_E_ONE_EXCHANGE_LOCAL_OPTIMUM` if `delta_vs_reference_e <= 0`

Overall advance gate:
- `PHASE9_ADVANCE_GATE = PASS` iff at least one tested `k` has exact `delta_vs_reference_e > 0`.
- `GLOBAL_OPTIMUM_STATUS = UNKNOWN` in all outcomes.

## 6. Reproducibility and claim boundary

- Rerun in a fresh process and require byte-identical result.
- `HISTORICAL_DRAWS: NOT_USED`
- `RNG: NONE`
- `MONTE_CARLO: NONE`
- `DB_ACCESS: NO`
- `RUNTIME_PROMOTION: NOT_AUTHORIZED`
- `GLOBAL_OPTIMUM_STATUS: UNKNOWN`
