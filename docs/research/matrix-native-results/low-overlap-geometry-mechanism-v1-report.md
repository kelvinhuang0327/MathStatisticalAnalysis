# STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1 -- report

Status: SEALED | exact combinatorial mechanism decomposition, real B649/T539/P638 Zone-1 winning-space scale | native execution complete

No historical draw is read. No Monte Carlo estimate is used. Predictive advantage, prize-value advantage, economic optimality, P638 Zone-2, and Arm-C are all out of scope for this study (see S8 for the full claim boundary).
## 1. Metric semantics (sealed-label correction)

| Name | Formula |
|---|---|
| `RELATIVE_LIFT_VS_RANDOM` | `(Q_B-Q_R)/Q_R` |
| `RELATIVE_COVERAGE_DELTA_VS_SIDON` | `(Q_B-Q_S)/Q_S` |
| `GAIN_OVER_RANDOM_RATIO_TO_SIDON` | `(Q_B-Q_R)/(Q_S-Q_R)` |

The sealed report label `REL_GAIN_OVER_SIDON` maps only to `GAIN_OVER_RANDOM_RATIO_TO_SIDON` -- **not** to `RELATIVE_COVERAGE_DELTA_VS_SIDON`. This mapping is unchanged from the locked preregistration.

## 2. Per lottery/k coverage, redundancy, and S2 comparison

| Lottery | k | Q_ARM_B | Q_SIDON | REDUNDANCY_B | REDUNDANCY_S | S2_B | S2_S |
|---|---:|---|---|---:|---:|---:|---:|
| BIG_LOTTO | 1 | 4654/249711 | 4654/249711 | 0 | 0 | 0 | 0 |
| BIG_LOTTO | 3 | 32528/582659 | 27487/499422 | 1200 | 12236 | 1200 | 12300 |
| BIG_LOTTO | 5 | 54130/582659 | 18299/202664 | 4000 | 40489 | 4000 | 41000 |
| BIG_LOTTO | 10 | 211705/1165318 | 2428175/13983816 | 65780 | 178065 | 66100 | 184500 |
| BIG_LOTTO | 15 | 86785/332948 | 5351/21252 | 264390 | 388402 | 271400 | 408300 |
| BIG_LOTTO | 20 | 142111/423752 | 108833/332948 | 522817 | 641494 | 542200 | 679100 |
| DAILY_539 | 1 | 1927/191919 | 1927/191919 | 0 | 0 | 0 | 0 |
| DAILY_539 | 3 | 1927/63973 | 1915/63973 | 0 | 108 | 0 | 108 |
| DAILY_539 | 5 | 9635/191919 | 9515/191919 | 0 | 360 | 0 | 360 |
| DAILY_539 | 10 | 2722/27417 | 18754/191919 | 648 | 1548 | 648 | 1548 |
| DAILY_539 | 15 | 9391/63973 | 1325/9139 | 2196 | 3240 | 2196 | 3240 |
| DAILY_539 | 20 | 37136/191919 | 1940/10101 | 4212 | 5040 | 4212 | 5040 |
| POWER_LOTTO_zone1 | 1 | 35611/920227 | 35611/920227 | 0 | 0 | 0 | 0 |
| POWER_LOTTO_zone1 | 3 | 106433/920227 | 44509/394383 | 1200 | 8936 | 1200 | 9000 |
| POWER_LOTTO_zone1 | 5 | 530165/2760681 | 504676/2760681 | 4000 | 29489 | 4000 | 30000 |
| POWER_LOTTO_zone1 | 10 | 324750/920227 | 950281/2760681 | 94080 | 118049 | 96000 | 122000 |
| POWER_LOTTO_zone1 | 15 | 64365/131461 | 445590/920227 | 250830 | 265725 | 263000 | 281200 |
| POWER_LOTTO_zone1 | 20 | 1686068/2760681 | 1369/2261 | 450592 | 465111 | 484200 | 502400 |

## 3. Full signed decomposition (Arm-B minus Sidon)

| Lottery | k | DELTA_COVERED | -DELTA_S2 (P) | +DELTA_S3 | -DELTA_S4 | +DELTA_S5 (higher j alternate sign) | H (higher-order residual) |
|---|---:|---:|---:|---:|---:|---:|---:|
| BIG_LOTTO | 1 | 0 | 0 | n/a | n/a | n/a | 0 |
| BIG_LOTTO | 3 | 11036 | 11100 | -64 | n/a | n/a | -64 |
| BIG_LOTTO | 5 | 36489 | 37000 | -512 | 1 | 0 | -511 |
| BIG_LOTTO | 10 | 112285 | 118400 | -6208 | 93 | 0 | -6115 |
| BIG_LOTTO | 15 | 124012 | 136900 | -13248 | 360 | 0 | -12888 |
| BIG_LOTTO | 20 | 118677 | 136900 | -18816 | 593 | 0 | -18223 |
| DAILY_539 | 1 | 0 | 0 | n/a | n/a | n/a | 0 |
| DAILY_539 | 3 | 108 | 108 | 0 | n/a | n/a | 0 |
| DAILY_539 | 5 | 360 | 360 | 0 | 0 | 0 | 0 |
| DAILY_539 | 10 | 900 | 900 | 0 | 0 | 0 | 0 |
| DAILY_539 | 15 | 1044 | 1044 | 0 | 0 | 0 | 0 |
| DAILY_539 | 20 | 828 | 828 | 0 | 0 | 0 | 0 |
| POWER_LOTTO_zone1 | 1 | 0 | 0 | n/a | n/a | n/a | 0 |
| POWER_LOTTO_zone1 | 3 | 7736 | 7800 | -64 | n/a | n/a | -64 |
| POWER_LOTTO_zone1 | 5 | 25489 | 26000 | -512 | 1 | 0 | -511 |
| POWER_LOTTO_zone1 | 10 | 23969 | 26000 | -2048 | 17 | 0 | -2031 |
| POWER_LOTTO_zone1 | 15 | 14895 | 18200 | -3392 | 87 | 0 | -3305 |
| POWER_LOTTO_zone1 | 20 | 14519 | 18200 | -3776 | 95 | 0 | -3681 |

Every signed `T_j` for `j` up to `k` is persisted in the machine-readable result's `comparison.higher_order_signed_terms`; only `j in {3,4,5}` are tabulated above for readability. `n/a` marks a `j` that exceeds that cell's own `k` (no such term exists, not a suppressed one).

## 4. Pairwise contribution share and per-cell mechanism descriptor

| Lottery | k | \|P\|/(\|P\|+sum\|T_j\|) | Mechanism descriptor |
|---|---:|---|---|
| BIG_LOTTO | 1 | NOT_APPLICABLE_K1 | NOT_APPLICABLE_K1 |
| BIG_LOTTO | 3 | 2775/2791 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| BIG_LOTTO | 5 | 37000/37513 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| BIG_LOTTO | 10 | 118400/124701 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| BIG_LOTTO | 15 | 34225/37627 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| BIG_LOTTO | 20 | 136900/156309 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| DAILY_539 | 1 | NOT_APPLICABLE_K1 | NOT_APPLICABLE_K1 |
| DAILY_539 | 3 | 1/1 | PAIRWISE_COLLISION_EXACTLY_SUFFICIENT |
| DAILY_539 | 5 | 1/1 | PAIRWISE_COLLISION_EXACTLY_SUFFICIENT |
| DAILY_539 | 10 | 1/1 | PAIRWISE_COLLISION_EXACTLY_SUFFICIENT |
| DAILY_539 | 15 | 1/1 | PAIRWISE_COLLISION_EXACTLY_SUFFICIENT |
| DAILY_539 | 20 | 1/1 | PAIRWISE_COLLISION_EXACTLY_SUFFICIENT |
| POWER_LOTTO_zone1 | 1 | NOT_APPLICABLE_K1 | NOT_APPLICABLE_K1 |
| POWER_LOTTO_zone1 | 3 | 975/983 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| POWER_LOTTO_zone1 | 5 | 26000/26513 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| POWER_LOTTO_zone1 | 10 | 5200/5613 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| POWER_LOTTO_zone1 | 15 | 2600/3097 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |
| POWER_LOTTO_zone1 | 20 | 2600/3153 | PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL |

## 5. Geometry (both arms)

| Lottery | k | Arm | Max overlap | Mean overlap | Unique numbers | Reuse dispersion (float) | Duplicates |
|---|---:|---|---:|---|---:|---:|---:|
| BIG_LOTTO | 1 | ARM_B | 0 | 0/1 | 6 | 0.327804 | 0 |
| BIG_LOTTO | 1 | SIDON | 0 | 0/1 | 6 | 0.327804 | 0 |
| BIG_LOTTO | 3 | ARM_B | 0 | 0/1 | 18 | 0.482082 | 0 |
| BIG_LOTTO | 3 | SIDON | 1 | 1/1 | 15 | 0.595695 | 0 |
| BIG_LOTTO | 5 | ARM_B | 0 | 0/1 | 30 | 0.487238 | 0 |
| BIG_LOTTO | 5 | SIDON | 1 | 1/1 | 22 | 0.803470 | 0 |
| BIG_LOTTO | 10 | ARM_B | 1 | 13/45 | 48 | 0.505694 | 0 |
| BIG_LOTTO | 10 | SIDON | 1 | 1/1 | 30 | 1.249740 | 0 |
| BIG_LOTTO | 15 | ARM_B | 1 | 62/105 | 48 | 0.996871 | 0 |
| BIG_LOTTO | 15 | SIDON | 1 | 33/35 | 35 | 1.582390 | 0 |
| BIG_LOTTO | 20 | ARM_B | 1 | 63/95 | 48 | 1.262670 | 0 |
| BIG_LOTTO | 20 | SIDON | 1 | 163/190 | 40 | 1.761970 | 0 |
| DAILY_539 | 1 | ARM_B | 0 | 0/1 | 5 | 0.334318 | 0 |
| DAILY_539 | 1 | SIDON | 0 | 0/1 | 5 | 0.334318 | 0 |
| DAILY_539 | 3 | ARM_B | 0 | 0/1 | 15 | 0.486504 | 0 |
| DAILY_539 | 3 | SIDON | 1 | 1/1 | 12 | 0.624926 | 0 |
| DAILY_539 | 5 | ARM_B | 0 | 0/1 | 25 | 0.479700 | 0 |
| DAILY_539 | 5 | SIDON | 1 | 1/1 | 17 | 0.861935 | 0 |
| DAILY_539 | 10 | ARM_B | 1 | 2/5 | 35 | 0.749315 | 0 |
| DAILY_539 | 10 | SIDON | 1 | 43/45 | 22 | 1.357764 | 0 |
| DAILY_539 | 15 | ARM_B | 1 | 61/105 | 39 | 1.163210 | 0 |
| DAILY_539 | 15 | SIDON | 1 | 6/7 | 27 | 1.685300 | 0 |
| DAILY_539 | 20 | ARM_B | 1 | 117/190 | 39 | 1.410489 | 0 |
| DAILY_539 | 20 | SIDON | 1 | 14/19 | 32 | 1.780159 | 0 |
| POWER_LOTTO_zone1 | 1 | ARM_B | 0 | 0/1 | 6 | 0.364642 | 0 |
| POWER_LOTTO_zone1 | 1 | SIDON | 0 | 0/1 | 6 | 0.364642 | 0 |
| POWER_LOTTO_zone1 | 3 | ARM_B | 0 | 0/1 | 18 | 0.499307 | 0 |
| POWER_LOTTO_zone1 | 3 | SIDON | 1 | 1/1 | 15 | 0.638124 | 0 |
| POWER_LOTTO_zone1 | 5 | ARM_B | 0 | 0/1 | 30 | 0.407682 | 0 |
| POWER_LOTTO_zone1 | 5 | SIDON | 1 | 1/1 | 22 | 0.832178 | 0 |
| POWER_LOTTO_zone1 | 10 | ARM_B | 1 | 2/3 | 36 | 0.815365 | 0 |
| POWER_LOTTO_zone1 | 10 | SIDON | 1 | 8/9 | 35 | 1.091392 | 0 |
| POWER_LOTTO_zone1 | 15 | ARM_B | 1 | 17/21 | 37 | 1.110264 | 0 |
| POWER_LOTTO_zone1 | 15 | SIDON | 1 | 92/105 | 38 | 1.265349 | 0 |
| POWER_LOTTO_zone1 | 20 | ARM_B | 1 | 157/190 | 38 | 1.203642 | 0 |
| POWER_LOTTO_zone1 | 20 | SIDON | 1 | 82/95 | 38 | 1.348026 | 0 |

## 6. Exact identity/check table

Every cell below passed every check; a single failure would have raised before this result file could ever be written (no partial result is ever persisted).

| Lottery | k | n_c_sums_to_winning_space | fixed_incidence_identity | redundancy_identity | inclusion_exclusion_identity | s2_geometry_identity | reuse_vector_identity | zero_duplicates | q_arm_b_matches_sealed | q_sidon_matches_sealed |
|---|---:|---|---|---|---|---|---|---|---|---|
| BIG_LOTTO | 1 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| BIG_LOTTO | 3 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| BIG_LOTTO | 5 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| BIG_LOTTO | 10 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| BIG_LOTTO | 15 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| BIG_LOTTO | 20 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| DAILY_539 | 1 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| DAILY_539 | 3 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| DAILY_539 | 5 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| DAILY_539 | 10 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| DAILY_539 | 15 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| DAILY_539 | 20 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| POWER_LOTTO_zone1 | 1 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| POWER_LOTTO_zone1 | 3 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| POWER_LOTTO_zone1 | 5 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| POWER_LOTTO_zone1 | 10 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| POWER_LOTTO_zone1 | 15 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| POWER_LOTTO_zone1 | 20 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

## 7. Replicated classifications

```text
REDUNDANCY_REDUCTION_STATUS: REDUNDANCY_REDUCTION_REPLICATED
  failing_or_equal_cells: NONE
PAIRWISE_COLLISION_STATUS: PAIRWISE_COLLISION_REDUCTION_REPLICATED
  failing_or_equal_cells: NONE
MECHANISM_DESCRIPTOR_COUNTS (k>1 cells only): {'PAIRWISE_COLLISION_EXACTLY_SUFFICIENT': 5, 'PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL': 10}
AGGREGATE_MECHANISM_DESCRIPTOR: MIXED_BY_LOTTERY_OR_K
GLOBAL_OPTIMUM_STATUS: UNKNOWN
FINAL_CLASSIFICATION: REDUNDANCY_REDUCTION_REPLICATED__PAIRWISE_COLLISION_REDUCTION_REPLICATED__AGGREGATE_DESCRIPTOR_MIXED_BY_LOTTERY_OR_K
```

## 8. Claim boundary (unchanged from lock)

This study supports exact combinatorial mechanism claims only.

```text
predictive_advantage:   NOT_TESTED
prize_value_advantage:  NOT_TESTED
economic_optimality:    NOT_TESTED
global_optimum_status:  UNKNOWN
p638_zone2:             NOT_RUN
arm_c:                  NOT_RUN
monte_carlo:            False
historical_draws_read:  False
```

## 9. Runtime, memory, and exact input provenance

```text
repository: kelvinhuang0327/MathStatisticalAnalysis
canonical_input_commit: 52b8353c932589c3f3ea8ff61fe7982c667cbbb0
canonical_input_tree:   69e81767f701ea4f29f86bb0af34262191950c70
locked_preregistration_path:   docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-preregistration.md
locked_preregistration_sha256: 8400019909b7361ad65e172449588802498fdf5d424d37a87adc030f7cde34be
```

Input Git blobs (frozen at lock time, re-verified byte-identical during Phase 0):

| Path | Git blob SHA-1 |
|---|---|
| `docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-report.md` | `60289b021f7859f0b92ccf42f38add16b9a31158` |
| `docs/research/matrix-native-results/diversification-constructor-frontier-b649-v1-result.json` | `169df1649ff0b8247ef5c779e8104079ae574cf4` |
| `docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-report.md` | `ca7754640ecd41f70351330382106e28bcd4fa53` |
| `docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-result.json` | `f75ce278096d120ab368a058dba0f6262e9e8041` |
| `docs/research/matrix-native-results/diversification-coverage-t539-v1-report.md` | `30e92c82033c67cabc92f2ac17131c328106d739` |
| `docs/research/matrix-native-results/diversification-coverage-t539-v1-result.json` | `013f4fbc1de6d62966b4c09e6f4bca5f5ae8a032` |
| `docs/research/matrix-native-results/greedy-min-overlap-constructor-p638-zone1-v1-report.md` | `958a1a71b7169df352dd6a71ec196d63df7a90aa` |
| `docs/research/matrix-native-results/greedy-min-overlap-constructor-p638-zone1-v1-result.json` | `7665d8bd84bf0c5d9a9004afb29e61ff8d421ff5` |
| `docs/research/matrix-native-results/greedy-min-overlap-constructor-t539-v1-report.md` | `c542920fc8bc900dcdb8e148cde772d22b80a731` |
| `docs/research/matrix-native-results/greedy-min-overlap-constructor-t539-v1-result.json` | `346544f3a644a3083ef9863bd7f35a345a50f531` |
| `docs/research/matrix-native-results/strategy-matrix-phase5-non-sidon-low-overlap-cross-lottery-synthesis-v1-report.md` | `2720632e56c56245a0ca18566aafda26d9d8b533` |
| `docs/research/matrix-native-results/strategy-matrix-phase5-non-sidon-low-overlap-cross-lottery-synthesis-v1-result.json` | `d9e5d86582e71ba86f8e48d091f31eaf824bf224` |
| `tools/generate_strategy_matrix_phase5_non_sidon_low_overlap_synthesis.py` | `5d0ad0728486ee0030510158e9262d1dc3ee6763` |

```text
BIG_LOTTO portfolio generation: SIDON=0.000s ARM_B=774.020s
DAILY_539 portfolio generation: SIDON=0.000s ARM_B=30.652s
POWER_LOTTO_zone1 portfolio generation: SIDON=0.000s ARM_B=154.229s
BIG_LOTTO winning-space enumeration: 35.774s
DAILY_539 winning-space enumeration: 1.471s
POWER_LOTTO_zone1 winning-space enumeration: 7.157s
derivation_and_validation: 0.006s
total: 1003.321s
peak_memory_bytes: 24788992
```
