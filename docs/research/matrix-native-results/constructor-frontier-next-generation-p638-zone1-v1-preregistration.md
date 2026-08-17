# STRATEGY_MATRIX_PHASE7_P638_ZONE1_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1 — locked preregistration

Status: LOCKED before any native P638 Zone1 candidate coverage inspection ｜ 2026-08-17 ｜
P638 Zone1 only

`TASK_ID: STRATEGY_MATRIX_PHASE7_P638_ZONE1_NEXT_GEN_CONSTRUCTOR_REPLICATION_R1`,
Owner authorization
`AUTHORIZE_MATRIX_PHASE7_P638_ZONE1_NEXT_GEN_CONSTRUCTOR_REPLICATION_R1`.
Locks the already-canonical Phase-7 constructor
`GREEDY_MINMAX_THEN_SUM_OVERLAP_V1` against current `origin/main`
`8d5e83219834266c4a60927297ba21a61a2379f4` for a P638 Zone1-only replication.

```text
PREREGISTRATION_LOCKED: YES
HASH_METHOD: LCJ-1 canonical bytes (lottolab.evidence.canonical_json), SHA-256
PREREGISTRATION_HASH_SHA256:  e4299741623632702e6548e6f3c505d37c01099c2b2f5561b56cf2695782b202
LOCK_SCOPE: THIS_EXACT_P638_ZONE1_REPLICATION_ONLY
REAL_P638_CANDIDATE_COVERAGE: NOT_YET_RUN_AT_LOCK_TIME
B649_RERUN: FORBIDDEN
T539_RERUN: FORBIDDEN
ARM_C_RERUN: FORBIDDEN
P638_ZONE2: OUT_OF_SCOPE
PARAMETER_RESCUE: FORBIDDEN
```

## 0. Identity

```text
STUDY_ID:               STRATEGY_MATRIX_PHASE7_P638_ZONE1_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1
PROPOSED_CONSTRUCTOR_ID: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
HYPOTHESIS_FAMILY_ID:   DIVERSIFICATION
SOURCE_TYPE:            STRATEGY_MATRIX_NATIVE
EVIDENCE_TYPE:          EXACT_COMBINATORIAL
CANONICAL_INPUT_COMMIT: 8d5e83219834266c4a60927297ba21a61a2379f4
CANONICAL_INPUT_TREE:   3eef6b026100ce8550442a10c92750bce1852b04
GLOBAL_OPTIMUM_STATUS:  UNKNOWN
```

## 1. Research question

Does the unchanged generic constructor
`GREEDY_MINMAX_THEN_SUM_OVERLAP_V1`, evaluated at native P638 Zone1
`(pool_size=38, draw_size=6)`, beat exact random and greedy Arm-B on
P638 `ZONE1_M3_PLUS` under the locked five-clause replication gate?

## 2. Frozen scope

```text
LOTTERY:            POWER_LOTTO  pool=38, draw=6, zone=zone1
K_LADDER:           [1, 3, 5, 10, 15, 20]
PRIMARY_EVENT:      ZONE1_M3_PLUS (minimum_matches=3)
SECONDARY_EVENTS:   NOT_RUN
MONTE_CARLO:        NONE
HISTORICAL_DRAWS:   NOT_USED
B649:               SEALED AUTHORITY ONLY (NOT RERUN)
T539:               SEALED AUTHORITY ONLY (NOT RERUN)
ARM_C:              NOT_RUN (no P638 frontier exists)
P638_ZONE2:         OUT_OF_SCOPE
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
ENTRY:     greedy_minmax_then_sum_overlap_portfolio(38, 6, k)
```

## 4. Frozen comparators

```text
A = cyclic_sidon_shift_p638.sidon_shift_portfolio
    sealed diversification-coverage-p638-zone1-v1-result.json
    hash 53e18558d07821460772a49f8358da3f2290b888dbde21c4497a0525c73cc992
    blob f75ce278096d120ab368a058dba0f6262e9e8041
B = greedy_min_overlap_portfolio(38, 6, k)
    sealed greedy-min-overlap-constructor-p638-zone1-v1-result.json
    hash e535caa323c1bb5ef027e5d8c5efa8b12fa83f59f83312ad1d9250d1e039f58b
    blob 7665d8bd84bf0c5d9a9004afb29e61ff8d421ff5
D = exact_random_portfolio_coverage(38, 6, 3, k)
E = GREEDY_MINMAX_THEN_SUM_OVERLAP_V1 at native (38, 6)
```

## 5. Frozen replication gate

PASS only if ALL:

1. Q_E > Q_D every k>1
2. Q_E >= Q_B every k>1
3. Q_E > Q_B at k={10,15,20}
4. duplicate count = 0
5. where E claims coverage superiority, lex (max,sum) does not worsen vs Arm-B

If ALL PASS: `P638_NEXT_GEN_CONSTRUCTOR_REPLICATION_SUPPORTED`
and `CROSS_LOTTERY_STATUS: NEXT_GEN_CONSTRUCTOR_SUPPORTED_IN_3_NATIVE_STRUCTURES`.

Otherwise: `DO_NOT_ADVANCE_THIS_EXACT_P638_REPLICATION`.
A P638 failure does not invalidate sealed B649/T539 results.
