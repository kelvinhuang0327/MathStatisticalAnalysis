# STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_R1 — report

Status: COMPLETE — `PHASE9_ADVANCE_GATE: PASS` ｜ 2026-08-27 ｜ B649 (Structure A) only

Exhaustively determines whether sealed Method E (`GREEDY_MINMAX_THEN_SUM_OVERLAP_V1`)
possesses any strictly better exact one-number-exchange neighbor at B649 $k \in \{10, 15, 20\}$.

Preregistration SHA-256: `68b25e8e2c7ee82d2f6c035003a3d21f67c649b00c465345e5d85423b377eb8d` (locked before native execution).

## 0. Identity

```text
STUDY_ID:                     STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_V1
TASK_ID:                      STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_R1
OWNER_AUTHORIZATION:          AUTHORIZE_STRATEGY_MATRIX_PHASE9_REFERENCE_E_EXACT_1EXCHANGE_DISCOVERY_R1
REFERENCE_CONSTRUCTOR_ID:     GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
CANDIDATE_ID:                 REFERENCE_E_BEST_1EXCHANGE_EXACT_COVERAGE_V1
LOTTERY:                      BIG_LOTTO (pool=49, draw=6)
PRIMARY_EVENT:                M3_PLUS (minimum_matches=3)
EXPOSURE_LADDER:              [10, 15, 20]
CANONICAL_BASE_COMMIT:        79948c6ba3b7195b85e11c690c50b70bf185b1d2
CANONICAL_BASE_TREE:          5e5c0c94550c0444ddb1e7ebd994c4223c48ca5a
GLOBAL_OPTIMUM_STATUS:        UNKNOWN
```

## 1. Headline finding

Reference E is **not a local optimum** under 1-number exchanges at any of the tested exposure rungs ($k=10, 15, 20$).

At all three rungs ($k=10, 15, 20$), exhaustive enumeration of all legal single-number-exchange neighbors reveals strictly better portfolios under exact combinatorial $M3+$ coverage:
- At $k=10$: Exactly 2,580 unique legal neighbors were evaluated. The maximum-coverage neighbor strictly improves over Reference E by $\Delta = +40/1747977 \approx +2.288 \times 10^{-5}$.
- At $k=15$: Exactly 3,870 unique legal neighbors were evaluated. The maximum-coverage neighbor strictly improves over Reference E by $\Delta = +19/74382 \approx +2.554 \times 10^{-4}$.
- At $k=20$: Exactly 5,160 unique legal neighbors were evaluated. The maximum-coverage neighbor strictly improves over Reference E by $\Delta = +5/158907 \approx +3.146 \times 10^{-5}$.

Because $\Delta > 0$ at all tested rungs, every rung is classified as `ONE_EXCHANGE_IMPROVEMENT_FOUND` and the overall advance gate passes: `PHASE9_ADVANCE_GATE: PASS`.

## 2. Exact primary coverages

| $k$ | Unique Neighbors | $Q_E$ (sealed) | $Q_{\text{best}}$ (exact) | $\Delta$ vs Reference E | $\Delta$ (approx float) | Classification | Best Neighbor Portfolio SHA-256 |
|---:|:---:|:---|:---|:---:|:---:|:---|:---|
| 10 | 2,580 | 212295/1165318 | 90995/499422 | +40/1747977 | +0.00002288 | `ONE_EXCHANGE_IMPROVEMENT_FOUND` | `4167482d739c59896ad9d50d23ebad89c1d22e787df8a34ae2b6bfd9206a69d5` |
| 15 | 3,870 | 927161/3495954 | 464027/1747977 | +19/74382 | +0.00025544 | `ONE_EXCHANGE_IMPROVEMENT_FOUND` | `ba6f516af65c31246550827ddcdcff2fcbf3f588be336e6de959a59dc898d1c8` |
| 20 | 5,160 | 17379/50666 | 171323/499422 | +5/158907 | +0.00003146 | `ONE_EXCHANGE_IMPROVEMENT_FOUND` | `a107d9cb5c7e0def7b19ccf2a6d02306b25bc0efe3443ea9899f3a4755429a4a` |

Approximate floats (presentation only):

| $k$ | $Q_E$ (float) | $Q_{\text{best}}$ (float) | $\Delta$ vs Reference E |
|---:|:---:|:---:|:---:|
| 10 | 0.18217774 | 0.18220062 | +0.00002288 |
| 15 | 0.26520973 | 0.26546516 | +0.00025544 |
| 20 | 0.34301109 | 0.34304256 | +0.00003146 |

## 3. Phase 9 advance gate

```text
PHASE9_ADVANCE_GATE:     PASS
ALL_TESTED_K_DELTA_GT_0: TRUE
GLOBAL_OPTIMUM_STATUS:   UNKNOWN
```

- Clause 1: `k=10 delta > 0`: TRUE (+40/1747977)
- Clause 2: `k=15 delta > 0`: TRUE (+19/74382)
- Clause 3: `k=20 delta > 0`: TRUE (+5/158907)
- Overall Gate: PASS (requires at least one tested $k$ with $\Delta > 0$).

## 4. Method E verification

Before evaluating any 1-exchange neighbor, Method E (`GREEDY_MINMAX_THEN_SUM_OVERLAP_V1`) was deterministically regenerated and verified against the sealed Phase-7 authority:
- 20-ticket portfolio SHA-256: `ac2198cf057b10ac8bd05e53519e5901999fe0b6beb4c35abb59c92a60ff60ff` (MATCH)
- Sealed $Q_E(10)$: `212295/1165318` (MATCH)
- Sealed $Q_E(15)$: `927161/3495954` (MATCH)
- Sealed $Q_E(20)$: `17379/50666` (MATCH)

## 5. Claim boundary

This study establishes exact deterministic combinatorial 1-number-exchange neighborhood evaluation for sealed Method E at B649 $k \in \{10, 15, 20\}$.
It proves that Method E is not a local optimum under 1-number exchange perturbations.
It does not establish a global optimum, predictive advantage, prize value advantage, or runtime promotion.

```text
HISTORICAL_DRAWS:       NOT_USED
RNG:                    NONE
MONTE_CARLO:            NONE
DB_ACCESS:              NO
T539_EXECUTION:         NOT_RUN
P638_EXECUTION:         NOT_RUN
PARAMETER_RESCUE_RUN:   NO
SECOND_EXCHANGE:        FORBIDDEN / NOT_PERFORMED
GLOBAL_OPTIMUM_STATUS:  UNKNOWN
RUNTIME_PROMOTION:      NOT_AUTHORIZED
PUSH:                   NOT_RUN
PR:                     NOT_CREATED
```

## 6. Artifacts

```text
src/lottolab/research/reference_e_exact_one_exchange_refinement.py
tools/run_strategy_matrix_phase9_reference_e_exact_one_exchange_discovery.py
tests/unit/test_reference_e_exact_one_exchange_refinement.py
docs/research/matrix-native-results/reference-e-exact-one-exchange-b649-v1-preregistration.md
docs/research/matrix-native-results/reference-e-exact-one-exchange-b649-v1-result.json
docs/research/matrix-native-results/reference-e-exact-one-exchange-b649-v1-report.md
```
