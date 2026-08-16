# STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1 -- report

Status: SEALED | exact combinatorial S3 triple-geometry mechanism, real B649/T539/P638 Zone-1 sealed portfolios | native execution complete

No historical draw is read. No Monte Carlo estimate is used. No winning-space enumeration is performed -- `S3_MULTIPLICITY` is reused read-only from the already-sealed Phase-5 result. Predictive advantage, prize-value advantage, economic optimality, P638 Zone-2, Arm-C, and `J4_GEOMETRY` are all out of scope for this study (see S8 for the full claim boundary).
## 1. S3_GEOMETRY vs sealed S3_MULTIPLICITY (the core new identity)

| Lottery | k | Arm | S3_GEOMETRY | S3_MULTIPLICITY | Identity |
|---|---:|---|---:|---:|---|
| BIG_LOTTO | 3 | ARM_B | 0 | 0 | PASS |
| BIG_LOTTO | 3 | SIDON | 64 | 64 | PASS |
| BIG_LOTTO | 5 | ARM_B | 0 | 0 | PASS |
| BIG_LOTTO | 5 | SIDON | 512 | 512 | PASS |
| BIG_LOTTO | 10 | ARM_B | 320 | 320 | PASS |
| BIG_LOTTO | 10 | SIDON | 6528 | 6528 | PASS |
| BIG_LOTTO | 15 | ARM_B | 7040 | 7040 | PASS |
| BIG_LOTTO | 15 | SIDON | 20288 | 20288 | PASS |
| BIG_LOTTO | 20 | ARM_B | 19584 | 19584 | PASS |
| BIG_LOTTO | 20 | SIDON | 38400 | 38400 | PASS |
| DAILY_539 | 3 | ARM_B | 0 | 0 | PASS |
| DAILY_539 | 3 | SIDON | 0 | 0 | PASS |
| DAILY_539 | 5 | ARM_B | 0 | 0 | PASS |
| DAILY_539 | 5 | SIDON | 0 | 0 | PASS |
| DAILY_539 | 10 | ARM_B | 0 | 0 | PASS |
| DAILY_539 | 10 | SIDON | 0 | 0 | PASS |
| DAILY_539 | 15 | ARM_B | 0 | 0 | PASS |
| DAILY_539 | 15 | SIDON | 0 | 0 | PASS |
| DAILY_539 | 20 | ARM_B | 0 | 0 | PASS |
| DAILY_539 | 20 | SIDON | 0 | 0 | PASS |
| POWER_LOTTO_zone1 | 3 | ARM_B | 0 | 0 | PASS |
| POWER_LOTTO_zone1 | 3 | SIDON | 64 | 64 | PASS |
| POWER_LOTTO_zone1 | 5 | ARM_B | 0 | 0 | PASS |
| POWER_LOTTO_zone1 | 5 | SIDON | 512 | 512 | PASS |
| POWER_LOTTO_zone1 | 10 | ARM_B | 1920 | 1920 | PASS |
| POWER_LOTTO_zone1 | 10 | SIDON | 3968 | 3968 | PASS |
| POWER_LOTTO_zone1 | 15 | ARM_B | 12288 | 12288 | PASS |
| POWER_LOTTO_zone1 | 15 | SIDON | 15680 | 15680 | PASS |
| POWER_LOTTO_zone1 | 20 | ARM_B | 34240 | 34240 | PASS |
| POWER_LOTTO_zone1 | 20 | SIDON | 38016 | 38016 | PASS |

Every row above passed; a single failure would have raised before this result file could ever be written (no partial result is ever persisted).

## 2. Ticket-triple intersection histogram (canonical shape `r_min,r_mid,r_max,s`)

- `BIG_LOTTO` k=3 `ARM_B` (1 triples): 0,0,0,0:1
- `BIG_LOTTO` k=3 `SIDON` (1 triples): 1,1,1,0:1
- `BIG_LOTTO` k=5 `ARM_B` (10 triples): 0,0,0,0:10
- `BIG_LOTTO` k=5 `SIDON` (10 triples): 1,1,1,0:8, 1,1,1,1:2
- `BIG_LOTTO` k=10 `ARM_B` (120 triples): 0,0,0,0:58, 0,1,1,0:30, 0,0,1,0:26, 1,1,1,0:5, 1,1,1,1:1
- `BIG_LOTTO` k=10 `SIDON` (120 triples): 1,1,1,0:102, 1,1,1,1:18
- `BIG_LOTTO` k=15 `ARM_B` (455 triples): 0,0,1,0:124, 0,1,1,0:116, 1,1,1,0:110, 0,0,0,0:65, 1,1,1,1:40
- `BIG_LOTTO` k=15 `SIDON` (455 triples): 1,1,1,0:317, 0,1,1,0:74, 1,1,1,1:62, 0,0,1,0:2
- `BIG_LOTTO` k=20 `ARM_B` (1140 triples): 0,1,1,0:404, 1,1,1,0:306, 0,0,1,0:260, 1,1,1,1:94, 0,0,0,0:76
- `BIG_LOTTO` k=20 `SIDON` (1140 triples): 1,1,1,0:600, 0,1,1,0:342, 1,1,1,1:126, 0,0,1,0:72
- `DAILY_539` k=3 `ARM_B` (1 triples): 0,0,0,0:1
- `DAILY_539` k=3 `SIDON` (1 triples): 1,1,1,0:1
- `DAILY_539` k=5 `ARM_B` (10 triples): 0,0,0,0:10
- `DAILY_539` k=5 `SIDON` (10 triples): 1,1,1,0:8, 1,1,1,1:2
- `DAILY_539` k=10 `ARM_B` (120 triples): 0,0,0,0:38, 0,0,1,0:36, 0,1,1,0:30, 1,1,1,0:12, 1,1,1,1:4
- `DAILY_539` k=10 `SIDON` (120 triples): 1,1,1,0:86, 1,1,1,1:18, 0,1,1,0:16
- `DAILY_539` k=15 `ARM_B` (455 triples): 0,1,1,0:145, 0,0,1,0:131, 1,1,1,0:64, 1,1,1,1:60, 0,0,0,0:55
- `DAILY_539` k=15 `SIDON` (455 triples): 1,1,1,0:224, 0,1,1,0:147, 1,1,1,1:60, 0,0,1,0:24
- `DAILY_539` k=20 `ARM_B` (1140 triples): 0,1,1,0:396, 0,0,1,0:354, 1,1,1,0:209, 1,1,1,1:111, 0,0,0,0:70
- `DAILY_539` k=20 `SIDON` (1140 triples): 0,1,1,0:420, 1,1,1,0:374, 0,0,1,0:228, 1,1,1,1:110, 0,0,0,0:8
- `POWER_LOTTO_zone1` k=3 `ARM_B` (1 triples): 0,0,0,0:1
- `POWER_LOTTO_zone1` k=3 `SIDON` (1 triples): 1,1,1,0:1
- `POWER_LOTTO_zone1` k=5 `ARM_B` (10 triples): 0,0,0,0:10
- `POWER_LOTTO_zone1` k=5 `SIDON` (10 triples): 1,1,1,0:8, 1,1,1,1:2
- `POWER_LOTTO_zone1` k=10 `ARM_B` (120 triples): 0,1,1,0:60, 1,1,1,0:30, 0,0,0,0:20, 1,1,1,1:10
- `POWER_LOTTO_zone1` k=10 `SIDON` (120 triples): 1,1,1,0:62, 0,1,1,0:40, 1,1,1,1:18
- `POWER_LOTTO_zone1` k=15 `ARM_B` (455 triples): 1,1,1,0:192, 0,1,1,0:180, 1,1,1,1:53, 0,0,0,0:20, 0,0,1,0:10
- `POWER_LOTTO_zone1` k=15 `SIDON` (455 triples): 1,1,1,0:245, 0,1,1,0:147, 1,1,1,1:52, 0,0,1,0:11
- `POWER_LOTTO_zone1` k=20 `ARM_B` (1140 triples): 1,1,1,0:535, 0,1,1,0:408, 1,1,1,1:115, 0,0,1,0:60, 0,0,0,0:22
- `POWER_LOTTO_zone1` k=20 `SIDON` (1140 triples): 1,1,1,0:594, 0,1,1,0:376, 1,1,1,1:124, 0,0,1,0:46

## 3. Saturated-triple count by k (the H2 endpoint) vs sealed residual magnitude

| Lottery | k | Arm | Saturated triples | Total triples | Sealed T3 | Sealed H | Sealed \|H\|/\|DELTA_COVERED\| |
|---|---:|---|---:|---:|---:|---:|---|
| BIG_LOTTO | 3 | ARM_B | 0 | 1 | -64 | -64 | -16/2759 |
| BIG_LOTTO | 3 | SIDON | 1 | 1 | -64 | -64 | -16/2759 |
| BIG_LOTTO | 5 | ARM_B | 0 | 10 | -512 | -511 | -511/36489 |
| BIG_LOTTO | 5 | SIDON | 8 | 10 | -512 | -511 | -511/36489 |
| BIG_LOTTO | 10 | ARM_B | 5 | 120 | -6208 | -6115 | -1223/22457 |
| BIG_LOTTO | 10 | SIDON | 102 | 120 | -6208 | -6115 | -1223/22457 |
| BIG_LOTTO | 15 | ARM_B | 110 | 455 | -13248 | -12888 | -3222/31003 |
| BIG_LOTTO | 15 | SIDON | 317 | 455 | -13248 | -12888 | -3222/31003 |
| BIG_LOTTO | 20 | ARM_B | 306 | 1140 | -18816 | -18223 | -18223/118677 |
| BIG_LOTTO | 20 | SIDON | 600 | 1140 | -18816 | -18223 | -18223/118677 |
| DAILY_539 | 3 | ARM_B | 0 | 1 | 0 | 0 | 0/1 |
| DAILY_539 | 3 | SIDON | 0 | 1 | 0 | 0 | 0/1 |
| DAILY_539 | 5 | ARM_B | 0 | 10 | 0 | 0 | 0/1 |
| DAILY_539 | 5 | SIDON | 0 | 10 | 0 | 0 | 0/1 |
| DAILY_539 | 10 | ARM_B | 0 | 120 | 0 | 0 | 0/1 |
| DAILY_539 | 10 | SIDON | 0 | 120 | 0 | 0 | 0/1 |
| DAILY_539 | 15 | ARM_B | 0 | 455 | 0 | 0 | 0/1 |
| DAILY_539 | 15 | SIDON | 0 | 455 | 0 | 0 | 0/1 |
| DAILY_539 | 20 | ARM_B | 0 | 1140 | 0 | 0 | 0/1 |
| DAILY_539 | 20 | SIDON | 0 | 1140 | 0 | 0 | 0/1 |
| POWER_LOTTO_zone1 | 3 | ARM_B | 0 | 1 | -64 | -64 | -8/967 |
| POWER_LOTTO_zone1 | 3 | SIDON | 1 | 1 | -64 | -64 | -8/967 |
| POWER_LOTTO_zone1 | 5 | ARM_B | 0 | 10 | -512 | -511 | -511/25489 |
| POWER_LOTTO_zone1 | 5 | SIDON | 8 | 10 | -512 | -511 | -511/25489 |
| POWER_LOTTO_zone1 | 10 | ARM_B | 30 | 120 | -2048 | -2031 | -2031/23969 |
| POWER_LOTTO_zone1 | 10 | SIDON | 62 | 120 | -2048 | -2031 | -2031/23969 |
| POWER_LOTTO_zone1 | 15 | ARM_B | 192 | 455 | -3392 | -3305 | -661/2979 |
| POWER_LOTTO_zone1 | 15 | SIDON | 245 | 455 | -3392 | -3305 | -661/2979 |
| POWER_LOTTO_zone1 | 20 | ARM_B | 535 | 1140 | -3776 | -3681 | -3681/14519 |
| POWER_LOTTO_zone1 | 20 | SIDON | 594 | 1140 | -3776 | -3681 | -3681/14519 |

`residual_to_net_gain_ratio = H / DELTA_COVERED` is read from the sealed Phase-5 result unchanged (both terms already exact and sealed); it is reported once per `(lottery, k)` cell, not per arm, since `DELTA_COVERED` is itself an Arm-B-minus-Sidon comparison quantity.

## 4. Necessary Mass Bound Lemma prediction vs the sealed zero/nonzero pattern

| Lottery | k | Arm | mass_bound_prediction_correct | S3_MULTIPLICITY==0 | Sealed max_pairwise_overlap |
|---|---:|---|---|---|---:|
| BIG_LOTTO | 3 | ARM_B | PASS | True | 0 |
| BIG_LOTTO | 3 | SIDON | PASS | False | 1 |
| BIG_LOTTO | 5 | ARM_B | PASS | True | 0 |
| BIG_LOTTO | 5 | SIDON | PASS | False | 1 |
| BIG_LOTTO | 10 | ARM_B | PASS | False | 1 |
| BIG_LOTTO | 10 | SIDON | PASS | False | 1 |
| BIG_LOTTO | 15 | ARM_B | PASS | False | 1 |
| BIG_LOTTO | 15 | SIDON | PASS | False | 1 |
| BIG_LOTTO | 20 | ARM_B | PASS | False | 1 |
| BIG_LOTTO | 20 | SIDON | PASS | False | 1 |
| DAILY_539 | 3 | ARM_B | PASS | True | 0 |
| DAILY_539 | 3 | SIDON | PASS | True | 1 |
| DAILY_539 | 5 | ARM_B | PASS | True | 0 |
| DAILY_539 | 5 | SIDON | PASS | True | 1 |
| DAILY_539 | 10 | ARM_B | PASS | True | 1 |
| DAILY_539 | 10 | SIDON | PASS | True | 1 |
| DAILY_539 | 15 | ARM_B | PASS | True | 1 |
| DAILY_539 | 15 | SIDON | PASS | True | 1 |
| DAILY_539 | 20 | ARM_B | PASS | True | 1 |
| DAILY_539 | 20 | SIDON | PASS | True | 1 |
| POWER_LOTTO_zone1 | 3 | ARM_B | PASS | True | 0 |
| POWER_LOTTO_zone1 | 3 | SIDON | PASS | False | 1 |
| POWER_LOTTO_zone1 | 5 | ARM_B | PASS | True | 0 |
| POWER_LOTTO_zone1 | 5 | SIDON | PASS | False | 1 |
| POWER_LOTTO_zone1 | 10 | ARM_B | PASS | False | 1 |
| POWER_LOTTO_zone1 | 10 | SIDON | PASS | False | 1 |
| POWER_LOTTO_zone1 | 15 | ARM_B | PASS | False | 1 |
| POWER_LOTTO_zone1 | 15 | SIDON | PASS | False | 1 |
| POWER_LOTTO_zone1 | 20 | ARM_B | PASS | False | 1 |
| POWER_LOTTO_zone1 | 20 | SIDON | PASS | False | 1 |

## 5. Sealed higher-order terms and mechanism descriptor (context only, read-only)

| Lottery | k | Sealed T3 | Sealed T4 | Sealed T5 | Sealed H | Sealed DELTA_COVERED | Sealed mechanism descriptor |
|---|---:|---:|---:|---:|---:|---:|---|
| BIG_LOTTO | 3 | -64 | 0 | 0 | -64 | 11036 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| BIG_LOTTO | 5 | -512 | 1 | 0 | -511 | 36489 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| BIG_LOTTO | 10 | -6208 | 93 | 0 | -6115 | 112285 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| BIG_LOTTO | 15 | -13248 | 360 | 0 | -12888 | 124012 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| BIG_LOTTO | 20 | -18816 | 593 | 0 | -18223 | 118677 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| DAILY_539 | 3 | 0 | 0 | 0 | 0 | 108 | PAIRWISE_COLLISION_EXACTLY_SUFFICIENT |
| DAILY_539 | 5 | 0 | 0 | 0 | 0 | 360 | PAIRWISE_COLLISION_EXACTLY_SUFFICIENT |
| DAILY_539 | 10 | 0 | 0 | 0 | 0 | 900 | PAIRWISE_COLLISION_EXACTLY_SUFFICIENT |
| DAILY_539 | 15 | 0 | 0 | 0 | 0 | 1044 | PAIRWISE_COLLISION_EXACTLY_SUFFICIENT |
| DAILY_539 | 20 | 0 | 0 | 0 | 0 | 828 | PAIRWISE_COLLISION_EXACTLY_SUFFICIENT |
| POWER_LOTTO_zone1 | 3 | -64 | 0 | 0 | -64 | 7736 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| POWER_LOTTO_zone1 | 5 | -512 | 1 | 0 | -511 | 25489 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| POWER_LOTTO_zone1 | 10 | -2048 | 17 | 0 | -2031 | 23969 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| POWER_LOTTO_zone1 | 15 | -3392 | 87 | 0 | -3305 | 14895 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| POWER_LOTTO_zone1 | 20 | -3776 | 95 | 0 | -3681 | 14519 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |

`J4_GEOMETRY` (whether `S4_GEOMETRY == S4_MULTIPLICITY` holds the same way `S3` does) is `OUT_OF_SCOPE` for this lock -- `T4`/`T5` above are copied read-only from the sealed Phase-5 result for context, never recomputed or geometrically explained by this study.

## 6. Portfolio hash verification (licenses reusing sealed S3_MULTIPLICITY)

| Lottery | Arm | Regenerated SHA-256 matches sealed |
|---|---|---|
| BIG_LOTTO | ARM_B | PASS |
| BIG_LOTTO | SIDON | PASS |
| DAILY_539 | ARM_B | PASS |
| DAILY_539 | SIDON | PASS |
| POWER_LOTTO_zone1 | ARM_B | PASS |
| POWER_LOTTO_zone1 | SIDON | PASS |

## 7. Classifications

```text
S3_GEOMETRY_IDENTITY_STATUS: S3_GEOMETRY_IDENTITY_REPLICATED
  failing_cells: NONE
MASS_BOUND_PREDICTION_STATUS: MASS_BOUND_PREDICTS_ZERO_SPLIT
  exception_cells: NONE
GLOBAL_OPTIMUM_STATUS: UNKNOWN
FINAL_CLASSIFICATION: S3_GEOMETRY_IDENTITY_REPLICATED__MASS_BOUND_PREDICTS_ZERO_SPLIT
```

## 8. Claim boundary (unchanged from lock)

This study supports exact combinatorial `S3` triple-geometry mechanism claims only.

```text
predictive_advantage:   NOT_TESTED
prize_value_advantage:  NOT_TESTED
economic_optimality:    NOT_TESTED
global_optimum_status:  UNKNOWN
p638_zone2:             NOT_RUN
arm_c:                  NOT_RUN
j4_geometry:            NOT_RUN
monte_carlo:            False
historical_draws_read:  False
native_winning_space_enumeration: False
```

## 9. Runtime, memory, and exact input provenance

```text
repository: kelvinhuang0327/MathStatisticalAnalysis
canonical_input_commit: 81104798a9f265de400c1a8bc476e109b14e1a4a
canonical_input_tree:   a82dc823bab4d396ac63a8856d507b43d393047d
locked_preregistration_path:   docs/research/matrix-native-results/higher-order-residual-mechanism-v1-preregistration.md
locked_preregistration_sha256: 354d96bcee4c9e4efb59e3e88f18c686fdfb23ed00be5dae2c0ea0d133e550a6
sealed_phase5_result_path: docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-result.json
sealed_phase5_result_blob: dc17f0b39c9baf81f8c85162d5db554e7ca2797a
sealed_phase5_preregistration_sha256: 8400019909b7361ad65e172449588802498fdf5d424d37a87adc030f7cde34be
```

Input Git blobs (frozen at lock time, re-verified byte-identical during Phase 0):

| Path | Git blob SHA-1 |
|---|---|
| `docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-preregistration-hash.json` | `c26e61a62dbebcfa44881d5a23f044a0ed52e04f` |
| `docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-preregistration.md` | `17b1ae14523bcd63f48d226a3134a2c5531ee654` |
| `docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-report.md` | `0243589b14068ea6a3f32d8af37e4db9b7569065` |
| `docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-result.json` | `dc17f0b39c9baf81f8c85162d5db554e7ca2797a` |
| `src/lottolab/research/cyclic_sidon_shift.py` | `d07efb5c71a0b25bb00ba3823e208c57aabb306e` |
| `src/lottolab/research/cyclic_sidon_shift_p638.py` | `736d0c7e8efc79f68e989921be3e5e0742617e97` |
| `src/lottolab/research/cyclic_sidon_shift_t539.py` | `f6b95bed2e0d51ed81781efd096d4f87d88606a1` |
| `src/lottolab/research/greedy_min_overlap_constructor.py` | `5511f67d981f7f8a1c33183c966d76ee50249d7d` |
| `src/lottolab/research/greedy_min_overlap_constructor_p638_zone1.py` | `622898a9f0a9f4c72af456a21af83c0fc63c7d45` |
| `src/lottolab/research/greedy_min_overlap_constructor_t539.py` | `372542aa0c164d3548a6aaa91dd56b28821d0eaa` |
| `src/lottolab/research/higher_order_residual_mechanism.py` | `2bc6eb7857ba373b723ac9e4d6c4dc89080e464c` |
| `src/lottolab/research/low_overlap_geometry_mechanism.py` | `20b6e0d70b17ef4e34c4d3d6f89196685c5bd22c` |

```text
BIG_LOTTO portfolio generation: SIDON=0.000s ARM_B=765.237s
DAILY_539 portfolio generation: SIDON=0.000s ARM_B=30.202s
POWER_LOTTO_zone1 portfolio generation: SIDON=0.000s ARM_B=151.248s
BIG_LOTTO triple-geometry computation: 0.007s
DAILY_539 triple-geometry computation: 0.006s
POWER_LOTTO_zone1 triple-geometry computation: 0.008s
total: 946.713s
peak_memory_bytes: 22167552
```
