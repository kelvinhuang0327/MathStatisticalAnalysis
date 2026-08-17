# STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_V1 — locked preregistration

Status: LOCKED before any native candidate coverage inspection ｜ 2026-08-17 ｜
B649 only

`TASK_ID: STRATEGY_MATRIX_PHASE7_B649_NEXT_GEN_CONSTRUCTOR_LOCK_EXECUTE_R1`,
Owner authorization
`AUTHORIZE_MATRIX_PHASE7_B649_NEXT_GEN_CONSTRUCTOR_LOCK_EXECUTE_R1`.
Locks the exact constructor variant designed in
`docs/research/strategy-matrix-phase7-constructor-frontier-next-generation-design-r1.md`
(commit `b7e9f31d069227d25323c51d912a1a38a5bf07dc`) against canonical
`origin/main` `3b3f953bf9857b85094e9f26c6ef5301ba3561e5`.

```text
PREREGISTRATION_LOCKED: YES
HASH_METHOD: LCJ-1 canonical bytes (lottolab.evidence.canonical_json), SHA-256
PREREGISTRATION_HASH_SHA256:  ea014c2204e1fa77041329fc60d172502589bbc02c7922c63e78120e582080c1
LOCK_SCOPE: THIS_EXACT_CONSTRUCTOR_VARIANT_ONLY
REAL_B649_CANDIDATE_COVERAGE: NOT_YET_RUN_AT_LOCK_TIME
ARM_C_RERUN: FORBIDDEN
T539_EXECUTION: NOT_RUN
P638_EXECUTION: NOT_RUN
PARAMETER_RESCUE: FORBIDDEN
```

## 0. Identity

```text
STUDY_ID:               STRATEGY_MATRIX_PHASE7_CONSTRUCTOR_FRONTIER_NEXT_GENERATION_V1
PROPOSED_CONSTRUCTOR_ID: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
HYPOTHESIS_FAMILY_ID:   DIVERSIFICATION
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
EVIDENCE_TYPE:          EXACT_COMBINATORIAL
DESIGN_SOURCE_COMMIT:   b7e9f31d069227d25323c51d912a1a38a5bf07dc
CANONICAL_INPUT_COMMIT: 3b3f953bf9857b85094e9f26c6ef5301ba3561e5
CANONICAL_INPUT_TREE:   6774dcade3c662d0ab3b757710e9e0aafcc3900b
GLOBAL_OPTIMUM_STATUS:  UNKNOWN
```

## 1. Research question

Does `GREEDY_MINMAX_THEN_SUM_OVERLAP_V1` beat exact random and greedy
Arm-B on B649 `M3+`, and capture at least one quarter of the sealed
Arm-C-minus-Arm-B gap at `k=20`, without rerunning Arm-C?

## 2. Frozen scope

```text
LOTTERY:            BIG_LOTTO  pool=49, draw=6
K_LADDER:           [1, 3, 5, 10, 15, 20]
PRIMARY_EVENT:      M3_PLUS (minimum_matches=3)
SECONDARY_EVENTS:   NOT_RUN
MONTE_CARLO:        NONE
HISTORICAL_DRAWS:   NOT_USED
T539 / P638:        NOT_RUN
ARM_C:              SEALED REFERENCE ONLY
```

## 3. Frozen constructor

```text
RULE:      unused legal ticket minimizing (max_overlap, sum_overlap, ticket)
TIE_BREAK: max, then sum, then lexicographic ticket
WEIGHTS:   none
RANDOM:    none
HISTORY:   none
STOPPING:  exactly ticket_count tickets
PREFIX:    portfolio(k) == portfolio(20)[:k]
ENTRY:     greedy_minmax_then_sum_overlap_portfolio(49, 6, k)
```

## 4. Frozen comparators

```text
A = cyclic_sidon_shift.sidon_shift_portfolio
B = greedy_min_overlap_constructor.greedy_min_overlap_portfolio(49, 6, k)
E = GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
D = exact_coverage_baseline.exact_random_portfolio_coverage
C = sealed q.c.3 from
    diversification-constructor-frontier-b649-v1-result.json
    blob 169df1649ff0b8247ef5c779e8104079ae574cf4
```

Sealed exact `M3+` fractions (copied into the hashed lock, aligned with
the ladder) are the identity checks for A, B, D and the only permitted
Arm-C values.

## 5. Frozen metrics and advance gate

```text
FRONTIER_CAPTURE_RATIO_E(k) = (Q_E-Q_D)/(Q_C-Q_D)   if Q_C > Q_D
B_TO_C_GAP_CAPTURE(k)       = (Q_E-Q_B)/(Q_C-Q_B)   if Q_C > Q_B
MATERIAL: B_TO_C_GAP_CAPTURE(20) >= 1/4
```

`B649_ADVANCE_GATE` passes iff all hold:

1. `Q_E > Q_D` for every `k > 1`
2. `Q_E >= Q_B` for every `k > 1`
3. `Q_E > Q_B` at `k in {10, 15, 20}`
4. `B_TO_C_GAP_CAPTURE(20) >= 1/4`
5. `duplicate_tickets == 0` at every ladder `k`

Pass classification: `B649_NEXT_GEN_CONSTRUCTOR_ADVANCE` and
`CROSS_LOTTERY_REPLICATION_ELIGIBLE: YES`.

Fail classification: `DO_NOT_ADVANCE_THIS_EXACT_VARIANT`.  Failure does
not retire geometry-aware constructor research generally.

## 6. Claim boundary

```text
ALLOWED: exact deterministic B649 combinatorial coverage/frontier evidence
NOT_PROVEN: global optimum, predictive advantage, profitability,
            prize/economic value, cross-lottery replication
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

## 7. No-rescue

The locked constructor key, ladder, event, sealed Arm-C values,
materiality constant `1/4`, and advance gate must not change after any
native `Q_E` is seen.  Arm-C may not be rerun.  T539/P638 may not start
in this task.
