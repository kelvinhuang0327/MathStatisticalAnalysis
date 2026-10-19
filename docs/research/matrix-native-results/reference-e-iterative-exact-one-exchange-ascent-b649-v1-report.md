# STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_R1 — report

Status: COMPLETE — `PHASE10_EXECUTION_GATE: PASS` ｜ 2026-08-27 ｜ B649 (Structure A) only

The deterministic `ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1` procedure independently ascended from each sealed Phase 9 best-neighbor portfolio until its complete exact one-number-exchange neighborhood contained no strictly better portfolio.

Preregistration SHA-256: `593dc33d34190063c5be5817a36bab4bfd3d64a9b98dac2ca1d942d06b567cfd` (frozen before native B649 execution).

Canonical result SHA-256: `099ca254ff9143c00953bde62329b2b8ae298a1f8e2bcfb757ca1c263119aa2c` (303,160 bytes).

## 0. Identity and authority

```text
STUDY_ID:                    STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_V1
TASK_ID:                     STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_R1
REFINEMENT_METHOD_ID:        ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1
OWNER_AUTHORIZATION:         AUTHORIZE_STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_R1
LOTTERY:                     BIG_LOTTO
POOL_SIZE:                   49
DRAW_SIZE:                   6
PRIMARY_EVENT:               M3_PLUS
K_SCOPE:                     [10, 15, 20]
RUNG_COUPLING:               NONE
CANONICAL_BASE_COMMIT:       d024c52895b68191f20564c7d7494782f374ca4a
CANONICAL_BASE_TREE:         df025ea5a9c52a4fe06325c68c97dad4508b964b
PHASE9_AUTHORITY_SHA256:     5c45204d227cc3750b9efe68ec9afeb3d83d6bd72104acbe319897fc94013e00
GLOBAL_OPTIMUM_STATUS:       UNKNOWN
```

All three immutable Phase 9 seed identities were verified before native Phase 10 evaluation:

| $k$ | Verified seed portfolio SHA-256 | Verified exact seed $Q_0$ |
|---:|:---|:---:|
| 10 | `4167482d739c59896ad9d50d23ebad89c1d22e787df8a34ae2b6bfd9206a69d5` | `90995/499422` |
| 15 | `ba6f516af65c31246550827ddcdcff2fcbf3f588be336e6de959a59dc898d1c8` | `464027/1747977` |
| 20 | `a107d9cb5c7e0def7b19ccf2a6d02306b25bc0efe3443ea9899f3a4755429a4a` | `171323/499422` |

## 1. Headline result

All three rungs reached complete certified exact one-exchange local optima. The Phase 9 `k=10` seed was already locally optimal and accepted zero Phase 10 moves. The `k=15` and `k=20` rungs accepted 21 and 27 strict exact improvements, respectively.

| $k$ | Accepted moves | Total iterations including terminal | Terminal exact $Q$ | Delta vs Phase 9 seed | Delta vs Method E | Terminal portfolio SHA-256 | Terminal best-neighbor delta | Certificate |
|---:|---:|---:|:---:|:---:|:---:|:---|:---:|:---|
| 10 | 0 | 1 | `90995/499422` | `0/1` | `40/1747977` | `4167482d739c59896ad9d50d23ebad89c1d22e787df8a34ae2b6bfd9206a69d5` | `0/1` | `TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED` |
| 15 | 21 | 22 | `14090/52969` | `41/75999` | `397/499422` | `8057138edd980413fa52607144d66a90372e68d251654998e3a1767fd3d9ce83` | `0/1` | `TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED` |
| 20 | 27 | 28 | `1200781/3495954` | `760/1747977` | `815/1747977` | `bf561d28d26961043f112ba8ed762ba9535666022c7df6bcefe49b8a21412710` | `-1/13983816` | `TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED` |

Terminal iteration checks:

- `k=10`: 2,580 unique legal neighbors; best exact $Q=90995/499422$; equality rejected.
- `k=15`: 3,870 unique legal neighbors; best exact $Q=14090/52969$; equality rejected.
- `k=20`: 5,160 unique legal neighbors; best exact $Q=1601041/4661272$; exact delta `-1/13983816` rejected.

```text
PHASE10_EXECUTION_GATE: PASS
K10_TERMINAL_CERTIFICATE: PASS
K15_TERMINAL_CERTIFICATE: PASS
K20_TERMINAL_CERTIFICATE: PASS
EVERY_ACCEPTED_MOVE_STRICT: TRUE
GLOBAL_OPTIMUM_STATUS: UNKNOWN
```

## 2. Accepted exact deltas

There were no accepted Phase 10 moves for `k=10`.

Accepted `k=15` moves:

| Iteration | Exact delta |
|---:|:---:|
| 0 | `925/3495954` |
| 1 | `16/1747977` |
| 2 | `40/1747977` |
| 3 | `8/582659` |
| 4 | `8/582659` |
| 5 | `127/13983816` |
| 6 | `8/582659` |
| 7 | `95/6991908` |
| 8 | `9/665896` |
| 9 | `317/13983816` |
| 10 | `125/13983816` |
| 11 | `9/665896` |
| 12 | `3/665896` |
| 13 | `16/1747977` |
| 14 | `83/4661272` |
| 15 | `31/2330636` |
| 16 | `31/2330636` |
| 17 | `125/13983816` |
| 18 | `31/2330636` |
| 19 | `125/6991908` |
| 20 | `155/6991908` |

Accepted `k=20` moves:

| Iteration | Exact delta |
|---:|:---:|
| 0 | `5/158907` |
| 1 | `379/13983816` |
| 2 | `40/1747977` |
| 3 | `505/13983816` |
| 4 | `79/3495954` |
| 5 | `29/1271256` |
| 6 | `29/1271256` |
| 7 | `313/13983816` |
| 8 | `9/665896` |
| 9 | `9/665896` |
| 10 | `9/665896` |
| 11 | `317/13983816` |
| 12 | `3/332948` |
| 13 | `125/13983816` |
| 14 | `17/1271256` |
| 15 | `1/74382` |
| 16 | `59/4661272` |
| 17 | `127/13983816` |
| 18 | `41/4661272` |
| 19 | `61/6991908` |
| 20 | `31/3495954` |
| 21 | `8/1747977` |
| 22 | `31/2330636` |
| 23 | `15/1165318` |
| 24 | `61/4661272` |
| 25 | `17/1271256` |
| 26 | `31/2330636` |

Every listed fraction is strictly greater than zero exactly. Iterations 21 (`k=15`) and 27 (`k=20`) are the separate rejected terminal iterations and are not included above.

## 3. Terminal portfolios

### k=10

```text
[1,2,3,4,5,6]
[1,7,13,19,25,49]
[2,8,14,20,26,49]
[7,8,9,10,11,12]
[13,14,15,16,17,18]
[19,20,21,22,23,24]
[25,26,27,28,29,30]
[31,32,33,34,35,36]
[37,38,39,40,41,42]
[43,44,45,46,47,48]
```

### k=15

```text
[1,2,3,4,5,33]
[2,8,9,29,36,37]
[3,9,15,27,32,42]
[4,26,27,29,34,41]
[5,8,15,26,31,39]
[6,10,16,22,25,28]
[6,12,18,24,30,35]
[7,10,11,12,14,20]
[7,13,19,25,30,49]
[11,17,23,28,35,49]
[13,14,16,17,18,21]
[19,20,21,22,23,24]
[31,32,33,34,36,40]
[37,38,39,40,41,42]
[43,44,45,46,47,48]
```

### k=20

```text
[1,2,3,11,12,18]
[1,7,13,31,37,43]
[1,8,15,23,38,44]
[2,8,14,20,31,47]
[2,9,19,36,43,49]
[3,7,14,23,39,45]
[3,9,15,27,31,46]
[4,10,16,22,28,33]
[4,13,14,15,17,18]
[5,6,22,29,34,49]
[5,16,19,26,32,47]
[6,10,12,24,30,35]
[6,16,21,25,42,48]
[7,8,9,11,17,41]
[11,13,20,23,40,46]
[17,20,21,24,39,44]
[18,41,44,45,46,48]
[25,26,27,28,29,30]
[25,32,33,34,35,36]
[37,38,39,40,41,42]
```

## 4. Exactness and deterministic reproduction

The simultaneous evaluator scanned all 13,983,816 B649 winning draws at every iteration. All-neighbor toy cases matched an independent brute-force exact evaluator. Portfolio ranking and move acceptance used integer covered-draw counts and exact `Fraction` values only.

Two complete executions ran in separate Python processes from the same frozen inputs. The second process overwrote the canonical result, after which its byte count and SHA-256 were compared with the recorded first-process identity.

```text
RUN1_RESULT_SHA256:          099ca254ff9143c00953bde62329b2b8ae298a1f8e2bcfb757ca1c263119aa2c
RUN1_RESULT_BYTES:           303160
RUN2_RESULT_SHA256:          099ca254ff9143c00953bde62329b2b8ae298a1f8e2bcfb757ca1c263119aa2c
RUN2_RESULT_BYTES:           303160
FRESH_PROCESS_BYTE_IDENTITY: PASS
```

Performance measurements were excluded from the scientific JSON:

| Process | k=10 seconds | k=15 seconds | k=20 seconds | Total wall seconds | Peak resident memory |
|:---|---:|---:|---:|---:|---:|
| Run 1 | 29.192076 | 758.228125 | 1200.355595 | 1987.89 | 139,182,080 bytes (132.734 MiB) |
| Run 2 | 27.444861 | 772.482596 | 1203.451688 | 2003.61 | 138,493,952 bytes (132.078 MiB) |

## 5. Claim boundary

This exact finite-state procedure certifies local optimality only within each terminal portfolio's complete legal one-number-exchange neighborhood. It does not establish a global optimum, predictive advantage, prize-value advantage, a cross-structure result, a new research reference, or a runtime strategy.

```text
HISTORICAL_DRAWS = NOT USED
RNG = NONE
MONTE_CARLO = NONE
DB_ACCESS = NO
SECOND_EXCHANGE = NOT RUN
T539_P638 = NOT RUN
REFERENCE_PROMOTION = NOT AUTHORIZED
RUNTIME_PROMOTION = NOT AUTHORIZED
GLOBAL_OPTIMUM_STATUS: UNKNOWN
PUSH = NOT RUN
PR = NOT CREATED
```

## 6. Artifacts

```text
src/lottolab/research/reference_e_iterative_exact_one_exchange_ascent.py
tools/run_strategy_matrix_phase10_b649_iterative_exact_1exchange_local_ascent.py
tests/unit/test_reference_e_iterative_exact_one_exchange_ascent.py
docs/research/matrix-native-results/reference-e-iterative-exact-one-exchange-ascent-b649-v1-preregistration.md
docs/research/matrix-native-results/reference-e-iterative-exact-one-exchange-ascent-b649-v1-result.json
docs/research/matrix-native-results/reference-e-iterative-exact-one-exchange-ascent-b649-v1-report.md
```
