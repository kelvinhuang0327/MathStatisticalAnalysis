# STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_ITERATIVE_EXACT_1EXCHANGE_REPLICATION_V1 — locked preregistration

Status: LOCKED before native Phase-11 execution ｜ 2026-08-28 ｜ T539 and P638 Zone-1 only

`TASK_ID: STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_ITERATIVE_EXACT_1EXCHANGE_REPLICATION_R1`  
Owner authorization: `AUTHORIZE_STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_ITERATIVE_EXACT_1EXCHANGE_REPLICATION_R1`.

This task replicates the already-canonical Phase-10 deterministic iterative
exact one-number-exchange ascent on the two already-supported non-B649 native
structures. The Phase-7 Method-E result files are immutable authorities for
the seed constructor identity, exact Q values, and k=20 portfolio identity.

```text
PREREGISTRATION_LOCKED: YES
HASH_METHOD: SHA-256 of this exact frozen Markdown document
LOCK_SCOPE: THIS_EXACT_PHASE11_T539_P638_ZONE1_REPLICATION_ONLY
NATIVE_PHASE11_EXECUTION: NOT_YET_RUN_AT_LOCK_TIME
CANONICAL_METHOD_IMPLEMENTATION: src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py
PHASE7_RESEAL: FORBIDDEN
RUNG_COUPLING: NONE
CROSS_STRUCTURE_STATE_SHARING: NONE
ITERATION_CAP: NONE
RESTARTS: NONE
CANDIDATE_SAMPLING: NONE
RNG: NONE
MONTE_CARLO: NONE
SECOND_EXCHANGE: FORBIDDEN
PLATEAU_MOVES: FORBIDDEN
POST_RESULT_BUDGET_CHANGE: FORBIDDEN
P638_ZONE2: NOT_RUN
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

## 0. Identity

```text
STUDY_ID:                    STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_ITERATIVE_EXACT_1EXCHANGE_REPLICATION_V1
TASK_ID:                     STRATEGY_MATRIX_PHASE11_T539_P638_ZONE1_ITERATIVE_EXACT_1EXCHANGE_REPLICATION_R1
REFINEMENT_METHOD_ID:        ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1
CANONICAL_BASE_COMMIT:       1de7bf0d51160802115aa7ade416e5e717a00461
CANONICAL_BASE_TREE:         895696e5c2ab87b7ebe1c294a2a32edcdefefe43
K_SCOPE:                     [10, 15, 20]
PRIMARY_EVENT_MIN_MATCHES:   3
```

## 1. Frozen native authorities

### DAILY_539

```text
STRUCTURE_ID: DAILY_539
LOTTERY_TYPE: DAILY_539
POOL_SIZE: 39
DRAW_SIZE: 5
PRIMARY_EVENT: M3_PLUS
SEED_CONSTRUCTOR: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
PHASE7_AUTHORITY: docs/research/matrix-native-results/constructor-frontier-next-generation-t539-v1-result.json
PHASE7_AUTHORITY_SHA256: 5e8a52d5e841b9c7e0f29711ded55e717421cc0334c272bd94ac2ee84ebe9474
REQUIRED_PHASE7_STUDY_ID: STRATEGY_MATRIX_PHASE7_T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1
REQUIRED_PHASE7_STATUS: T539_NEXT_GEN_CONSTRUCTOR_REPLICATION_SUPPORTED
REQUIRED_METHOD_E_PORTFOLIO_SHA256_K20: 81830474195db8ae460367b71ecea271a390aaa432c5af4bd78fc18c65c09b60
Q_METHOD_E_K10: 2734/27417
Q_METHOD_E_K15: 9475/63973
Q_METHOD_E_K20: 152/777
```

### POWER_LOTTO Zone-1

```text
STRUCTURE_ID: POWER_LOTTO_ZONE1
LOTTERY_TYPE: POWER_LOTTO
ZONE: zone1
POOL_SIZE: 38
DRAW_SIZE: 6
PRIMARY_EVENT: ZONE1_M3_PLUS
SEED_CONSTRUCTOR: GREEDY_MINMAX_THEN_SUM_OVERLAP_V1
PHASE7_AUTHORITY: docs/research/matrix-native-results/constructor-frontier-next-generation-p638-zone1-v1-result.json
PHASE7_AUTHORITY_SHA256: 77e6df9e8baa8202c886d6b30808b5c78993bfda13b4eab7710ae60f5ea139ed
REQUIRED_PHASE7_STUDY_ID: STRATEGY_MATRIX_PHASE7_P638_ZONE1_NEXT_GEN_CONSTRUCTOR_REPLICATION_V1
REQUIRED_PHASE7_STATUS: P638_NEXT_GEN_CONSTRUCTOR_REPLICATION_SUPPORTED
REQUIRED_METHOD_E_PORTFOLIO_SHA256_K20: 59182264db6be95ab51dff64f0548f1a5f1163ca33e8b4a646fe02db383d8d85
Q_METHOD_E_K10: 52270/145299
Q_METHOD_E_K15: 126653/250971
Q_METHOD_E_K20: 578195/920227
P638_ZONE2: NOT_RUN
```

The full k=20 Method-E portfolio is regenerated from the frozen native
constructor mapping and its lexicographic prefixes are used for k=10 and
k=15. Each prefix is independently hash-checked and its exact primary-event
Q is independently checked by the Phase-10 ascent evaluator before the
corresponding rung is accepted as a seed.

## 2. Frozen refinement semantics

For every structure and every k independently, let `P0` be the regenerated
sealed Method-E portfolio prefix. At each iteration:

1. Enumerate every unique legal exact one-number-exchange neighbor.
2. Canonicalize each ticket ascending and the complete portfolio
   lexicographically; reject duplicate tickets and de-duplicate equivalent
   complete portfolios.
3. Evaluate exact primary-event coverage for every unique neighbor.
4. Select maximum exact coverage, breaking exact ties by the lexicographically
   smallest complete portfolio.
5. Accept only when `Q_best > Q_current` exactly.
6. After an accepted move, repeat the same complete procedure.
7. Stop when the complete exact neighborhood has no strictly better neighbor.

No plateau move, iteration cap, restart, candidate sampling, RNG, Monte Carlo
estimate, second exchange, cross-k coupling, cross-structure state sharing,
or result-dependent search-budget change is allowed. The implementation is
the canonical `ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1` module named above;
the Phase-11 runner must not fork or redefine it.

## 3. Required terminal certificate

Each of the six rungs records the structure id, k, seed Method-E portfolio
SHA-256, seed exact Q, every iteration index, input portfolio SHA-256, exact
input Q, unique legal neighbor count, best-neighbor portfolio SHA-256, exact
best-neighbor Q, exact delta, accepted move, move count, terminal portfolio,
terminal portfolio SHA-256, terminal exact Q, exact terminal delta versus
Method E, and the classification
`TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED`.

The terminal iteration must have `accepted_move = false` and
`best_neighbor_Q <= terminal_Q` exactly. Zero accepted moves is a valid
scientific result and is not a failure condition.

## 4. Completion and claim boundary

```text
PHASE11_EXECUTION_GATE: PASS iff all six terminal certificates PASS
GLOBAL_OPTIMUM_STATUS: UNKNOWN
HISTORICAL_DRAWS: NOT_USED
DB_ACCESS: NO
P638_ZONE2: NOT_RUN
REFERENCE_PROMOTION: NOT_AUTHORIZED
RUNTIME_PROMOTION: NOT_AUTHORIZED
PUSH: NOT_RUN
PR: NOT_CREATED
```

The result certifies local optimality only within each terminal portfolio's
complete legal one-number-exchange neighborhood. It does not establish a
global optimum, predictive advantage, prize/economic value, a runtime
strategy, or any P638 Zone-2 result.
