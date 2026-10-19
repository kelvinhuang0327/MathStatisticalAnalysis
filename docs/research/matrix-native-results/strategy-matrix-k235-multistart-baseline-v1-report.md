# STRATEGY_MATRIX_K235_MULTISTART_BASELINE_V1 — result

Status: COMPLETE — `MULTISTART_EXECUTION_GATE: PASS` ｜ 2026-08-31 ｜
BIG_LOTTO, DAILY_539, and POWER_LOTTO_ZONE1 at k=2, 3, and 5

`INTENT: code does deterministic orchestration over four frozen constructor starts for k=2/3/5; the check/task expects every start to run unchanged exact best-improvement ascent to a certified local terminal; the opened canonical implementation says strict exact improvements only, complete legal one-exchange neighborhoods, and lexicographic tie-breaking.`

Thirty-six independent exact best-improvement ascents were run: four frozen
starts in each of nine supported lottery/cardinality cells. Every start reached
an exact one-exchange local optimum, every terminal was retained, and every
cell yielded four canonical terminal portfolios.

No result is a global-optimum claim. k=10 and k=20 remain Phase13-owned and
were not evaluated. POWER_LOTTO Zone-2 remains out of scope and was not run.

## Identity and frozen scope

```text
STUDY_ID:                    STRATEGY_MATRIX_K235_MULTISTART_BASELINE_V1
TASK_ID:                     STRATEGY_MATRIX_K235_MULTISTART_BASELINE_R1
OWNER_AUTHORIZATION:         AUTHORIZE_STRATEGY_MATRIX_K235_MULTISTART_BASELINE_R1
CANONICAL_BASE_COMMIT:       07a5c3479123c03fd91b6f1ae2402046b5f16c2a
CANONICAL_BASE_TREE:         cff549183e67ad49f12afb5076a11b1f8b712dde
REQUESTED_K_SCOPE:           [2, 3, 5]
SUPPORTED_K_SCOPE:           [2, 3, 5]
START_COUNT_PER_CELL:        4
START_MANIFEST_SHA256:       107cb53080b45569c761a81ecd6c5924236f4376e69596c115baac41bb60acfc
PREREGISTRATION_SHA256:      3a842c8b4a16a6427216b187317dba5edc49638b8cd39f9ea5a3b70b351b4a98
GLOBAL_OPTIMUM_STATUS:       UNKNOWN
```

The four frozen start identities, in order, were:

```text
CYCLIC_SIDON_SHIFT_OFFSET0_V1
CYCLIC_SIDON_SHIFT_OFFSET1_V1
CYCLIC_SIDON_SHIFT_OFFSET2_V1
CYCLIC_SIDON_SHIFT_OFFSET3_V1
```

Each is a contiguous window of the existing lottery-native cyclic-Sidon
constructor. Offsets 0 and 1 are the deterministic starts used by Phase12;
offsets 2 and 3 provide the two additional predeclared starts needed for
these cells, which have no Phase10/11 prior terminal comparator. No random
numbers, sampled starts, hidden restarts, or result-dependent start changes
were used.

## Required cell results

| LOTTERY | K | START_COUNT | UNIQUE_TERMINAL_COUNT | BEST_START_ID | BEST_TERMINAL_PORTFOLIO | BEST_EXACT_Q | LOCAL_OPTIMUM_STATUS | GLOBAL_OPTIMUM_STATUS |
|---|---:|---:|---:|---|---|---|---|---|
| BIG_LOTTO | 2 | 4 | 4 | `CYCLIC_SIDON_SHIFT_OFFSET0_V1` | `[[1,2,4,8,13,21],[3,5,6,9,14,22]]` | `21702/582659` | `EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM` | `UNKNOWN` |
| BIG_LOTTO | 3 | 4 | 4 | `CYCLIC_SIDON_SHIFT_OFFSET1_V1` | `[[1,2,3,9,14,22],[4,6,10,12,15,23],[5,7,8,11,16,24]]` | `32528/582659` | `EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM` | `UNKNOWN` |
| BIG_LOTTO | 5 | 4 | 4 | `CYCLIC_SIDON_SHIFT_OFFSET1_V1` | `[[1,2,3,9,14,22],[4,5,7,11,16,24],[6,10,15,23,27,30],[8,12,17,19,20,25],[13,18,21,26,28,29]]` | `54130/582659` | `EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM` | `UNKNOWN` |
| DAILY_539 | 2 | 4 | 4 | `CYCLIC_SIDON_SHIFT_OFFSET0_V1` | `[[1,2,4,8,13],[3,5,6,9,14]]` | `3854/191919` | `EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM` | `UNKNOWN` |
| DAILY_539 | 3 | 4 | 4 | `CYCLIC_SIDON_SHIFT_OFFSET1_V1` | `[[1,2,3,9,14],[4,6,10,12,15],[5,7,8,11,16]]` | `1927/63973` | `EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM` | `UNKNOWN` |
| DAILY_539 | 5 | 4 | 4 | `CYCLIC_SIDON_SHIFT_OFFSET1_V1` | `[[1,2,3,9,14],[4,6,10,15,25],[5,7,11,16,24],[8,12,17,22,23],[13,18,19,20,21]]` | `9635/191919` | `EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM` | `UNKNOWN` |
| POWER_LOTTO_ZONE1 | 2 | 4 | 4 | `CYCLIC_SIDON_SHIFT_OFFSET0_V1` | `[[1,2,4,8,18,31],[3,5,6,9,19,32]]` | `213266/2760681` | `EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM` | `UNKNOWN` |
| POWER_LOTTO_ZONE1 | 3 | 4 | 4 | `CYCLIC_SIDON_SHIFT_OFFSET1_V1` | `[[1,2,3,9,19,32],[4,6,10,12,20,33],[5,7,8,11,21,34]]` | `106433/920227` | `EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM` | `UNKNOWN` |
| POWER_LOTTO_ZONE1 | 5 | 4 | 4 | `CYCLIC_SIDON_SHIFT_OFFSET1_V1` | `[[1,2,3,9,19,32],[4,5,7,11,21,34],[6,10,17,20,25,33],[8,12,14,15,22,35],[13,16,18,23,24,36]]` | `530165/2760681` | `EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM` | `UNKNOWN` |

## All retained start results

The canonical JSON retains every full ascent trace, terminal portfolio, and
terminal exact Q. The compact summary below records the terminal Q and number
of strict accepted moves for each frozen start.

| LOTTERY | K | OFFSET0 | OFFSET1 | OFFSET2 | OFFSET3 |
|---|---:|---|---|---|---|
| BIG_LOTTO | 2 | `21702/582659` · 1 | `21702/582659` · 1 | `21702/582659` · 1 | `21702/582659` · 1 |
| BIG_LOTTO | 3 | `32528/582659` · 3 | `32528/582659` · 3 | `32528/582659` · 3 | `32528/582659` · 3 |
| BIG_LOTTO | 5 | `54130/582659` · 8 | `54130/582659` · 8 | `54130/582659` · 8 | `54130/582659` · 8 |
| DAILY_539 | 2 | `3854/191919` · 1 | `3854/191919` · 1 | `3854/191919` · 1 | `3854/191919` · 1 |
| DAILY_539 | 3 | `1927/63973` · 3 | `1927/63973` · 3 | `1927/63973` · 3 | `1927/63973` · 3 |
| DAILY_539 | 5 | `9635/191919` · 8 | `9635/191919` · 8 | `9635/191919` · 8 | `9635/191919` · 8 |
| POWER_LOTTO_ZONE1 | 2 | `213266/2760681` · 1 | `213266/2760681` · 1 | `213266/2760681` · 1 | `213266/2760681` · 1 |
| POWER_LOTTO_ZONE1 | 3 | `106433/920227` · 3 | `106433/920227` · 3 | `106433/920227` · 3 | `106433/920227` · 3 |
| POWER_LOTTO_ZONE1 | 5 | `530165/2760681` · 8 | `530165/2760681` · 8 | `530165/2760681` · 8 | `530165/2760681` · 8 |

Each cell has four distinct canonical terminal portfolios despite tied exact
terminal Q values. The best start ID is selected by exact Q, then canonical
terminal portfolio, then start ID; this is only the existing deterministic
reporting tie-break.

## Exact method and claim boundary

```text
OBJECTIVE_ID:                EXACT_PORTFOLIO_M3_PLUS_COVERAGE
REFINEMENT_METHOD_ID:        ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1
CANONICAL_METHOD_PATH:       src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py
CANONICAL_METHOD_SHA256:     01e634924797355d4f19487a7abfaeed8910bc3b0c5ee8a6d95ebe617a368577
NEIGHBORHOOD:                COMPLETE_LEGAL_EXACT_ONE_NUMBER_EXCHANGE
TIE_BREAK:                   LEXICOGRAPHIC_COMPLETE_PORTFOLIO
```

Every accepted move had a strictly positive exact `Q` delta. Every final
iteration rejected movement because its best legal neighbor had `Q` no larger
than the terminal. The exact Q semantics and ascent core were not modified.

```text
RANDOM_DERIVED_STARTS:        NONE
SAMPLING:                     NONE
MONTE_CARLO:                  NONE
SECOND_EXCHANGE:              NOT_RUN
GLOBAL_OPTIMUM_STATUS:        UNKNOWN
PREDICTIVE_OR_ECONOMIC_CLAIM: NOT_CLAIMED
PRODUCTION_MUTATION:          NOT_AUTHORIZED
```

## Reproducibility and verification

Canonical result JSON:

```text
RESULT_PATH:                  docs/research/matrix-native-results/strategy-matrix-k235-multistart-baseline-v1-result.json
RESULT_SHA256_RUN1:           d1e04f50d33fbb5bdd01180ab2fefb0afd99fae7e6f1bf07dee8cfe84000a297
RESULT_SHA256_RUN2:           d1e04f50d33fbb5bdd01180ab2fefb0afd99fae7e6f1bf07dee8cfe84000a297
RESULT_BYTES:                 599619
FRESH_PROCESS_BYTE_IDENTITY:  PASS
```

Observed verification outcomes:

```text
OBJECTIVE_FREEZE_TESTS:       PASS (3 passed, 1 deselected)
FOCUSED_TESTS:                PASS (4 passed)
RUFF:                         PASS
PYRIGHT:                      PASS (0 errors, 0 warnings, 0 informations)
ALL_FROZEN_STARTS_EVALUATED:  PASS (36/36)
ALL_TERMINALS_CERTIFIED:      PASS (36/36)
SOURCE_IDENTITY_CHECKS:       PASS
EXACT_ASCENT_CORE_DIFF:       EMPTY
PHASE13_FILES_TOUCHED:        NO
RADIUS2_CHANGES:              NO
```

The full machine-readable evidence is in
`strategy-matrix-k235-multistart-baseline-v1-result.json`; the objective-free
start materialization is in
`strategy-matrix-k235-multistart-baseline-v1-starts.json`.
