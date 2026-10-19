# B649 Track D Post-2023 Consensus Alignment Mechanism R1

TASK_ID: `B649_TRACK_D_POST2023_CONSENSUS_ALIGNMENT_MECHANISM_AND_NEXT_DIRECTION_R1`  
STATUS: PASS  
MODE: CONTINUATION_HANDOFF / DEVELOPMENT_MECHANISM_DISCOVERY  
DATE: 2026-08-14

`B_EH04_INTERIM_DATA_USED: NO`  
`COHORT_V2_PROSPECTIVE_DATA_USED: NO`  
`REPO_MUTATION: NONE`  
`DB_MUTATION: NONE`

## 1. Current phenomenon

The recovered 1,417-target table reproduces the period dependence exactly:

| Cohort | Targets | Static-consensus M2+ | Rate |
|---|---:|---:|---:|
| Full development | 1,417 | 231 | **16.30%** |
| Earlier search period | 1,117 | 164 | **14.68%** |
| PRE_2023 | 996 | 137 | **13.76%** |
| POST_2023 | 421 | 94 | **22.33%** |
| POST_2023 held-out subset | 300 | 67 | **22.33%** |

[Confirmed] Data quality is internally clean for the present question: 1,417 unique targets and dates, strict date ordering, no null F1/F2/M2 values, and zero mismatches in era labels, ticket width/range, F1 derivation, ticket/outcome hit counts, or M2 labels.

The effect direction in the continuation wording needed correction: static consensus does **not** become more concentrated in 1–12 after 2023. Its mean selected slots in 1–12 falls from 3.300 to 2.810.

## 2. F1/F2 definitions

### F1 — `top6_slots_in_1_12`

Count of the six frozen static-consensus ticket numbers that lie in the inclusive band 1–12. Static consensus uses the same 22 complete strategy streams at every target, equal weights, rank-linear contributions over each strategy's six ordered candidates, and deterministic `(-score, number)` ordering.

```text
FEATURE: top6_slots_in_1_12
USES_TARGET_OUTCOME: NO
STRICT_PRIOR_AVAILABLE: YES
DERIVATION: count(n in frozen consensus ticket_t where 1 <= n <= 12)
```

The count was independently recomputed from every stored ticket: 0/1,417 mismatches.

### F2 — `top6_mean_gap`

For each selected number, order the authoritative draw index by ascending numeric `draw_number`, find the most recent strictly-prior main-number occurrence, and take the inclusive row distance from that occurrence to target `t`. F2 is the arithmetic mean of those six distances. The target outcome is inserted only after its feature is computed.

```text
FEATURE: top6_mean_gap
USES_TARGET_OUTCOME: NO
STRICT_PRIOR_AVAILABLE: YES
DERIVATION: mean_t(current_prior_row_index - last_prior_main_occurrence_index[n])
```

Independent reconstruction matched all 1,417 stored values within CSV rounding (maximum absolute difference `0.0003334`). This definition is strict-prior but sensitive to the historical corpus's number-support semantics; Section 9 addresses that separately.

## 3. Era-shift result

The prior scratch command was not recoverable. The reported result was independently reproduced from the retained table with a fully specified family-wise test.

Multiplicity family: the 21 outcome-free consensus-state columns `n_supported_numbers`, `top1_score`, `top1_support`, `top6_mean_support`, `rank6_score`, `rank7_score`, `rank6_minus_rank7_margin`, `rank6_support`, `rank7_support`, `rank6_rank7_tied`, `top6_family_breadth_mean`, `top6_distinct_families`, `score_entropy_norm`, `support_concentration_hhi`, `top6_score_mass_fraction`, `minority_support_mass`, `strategy_disagreement`, `family_disagreement`, `top6_slots_in_43_49`, `top6_slots_in_1_12`, and `top6_mean_gap`.

Correction: 2,000 deterministic era-label permutations preserving group sizes 996/421; statistic = maximum absolute Welch `t` over all 21 columns; seed = `B649_TRACK_D_POST2023_ERA_SCREEN_R1|2000|max_abs_welch_t|21`. The largest null max-|t| was 4.519; its 95th/99th percentiles were 3.033/3.453.

| Feature | PRE distribution | POST distribution | POST−PRE | Hedges g | Welch t (df) | Raw p | Max-t FWER p |
|---|---|---|---:|---:|---:|---:|---:|
| F1 slots in 1–12 | mean 3.300; median 3; IQR 3–4 | mean 2.810; median 3; IQR 2–4 | **−0.490** | −0.438 | −7.608 (807.6) | `7.77e-14` | **0.00049975** |
| F2 mean gap | mean 10.071; median 9.167; IQR 6.833–11.500 | mean 8.219; median 8.000; IQR 6.000–10.500 | **−1.853** | −0.326 | −7.262 (1392.1) | `6.34e-13` | **0.00049975** |

For both features, 0/2,000 permuted family maxima reached the observed statistic, so the finite-simulation value is `(0+1)/(2000+1) = 0.00049975`, reported as `p=0.0005`; it is not a literal zero probability.

The already documented sparse high-band feature `top6_slots_in_43_49` also clears this era-screen threshold. F1/F2 therefore describe a broader ticket-composition state, not two isolated predictors.

## 4. Sharp break versus drift

### Chronological summaries

| Year | n | F1 mean | F1 median | F2 mean | F2 median | M2+ |
|---|---:|---:|---:|---:|---:|---:|
| 2014 | 108 | 2.963 | 3 | 16.171 | 9.750 | 16.67% |
| 2015 | 109 | 3.780 | 4 | 8.823 | 8.833 | 15.60% |
| 2016 | 111 | 2.991 | 3 | 9.952 | 10.000 | 10.81% |
| 2017 | 108 | 2.630 | 3 | 10.122 | 10.250 | 15.74% |
| 2018 | 108 | 4.074 | 4 | 8.580 | 8.333 | 14.81% |
| 2019 | 112 | 3.527 | 3.5 | 9.435 | 9.250 | 12.50% |
| 2020 | 112 | 3.393 | 3 | 8.308 | 8.084 | 13.39% |
| 2021 | 114 | 3.509 | 4 | 9.588 | 9.500 | 10.53% |
| 2022 | 114 | 2.842 | 3 | 9.809 | 9.833 | 14.04% |
| 2023 | 116 | 3.190 | 3 | 8.206 | 8.000 | 21.55% |
| 2024 | 118 | 2.373 | 2 | 8.524 | 8.167 | 25.42% |
| 2025 | 118 | 2.788 | 3 | 8.155 | 8.084 | 22.03% |
| 2026 partial | 69 | 2.957 | 3 | 7.826 | 7.000 | 18.84% |

The last 100 pre-2023 targets have F1/F2 means 2.850/9.482; the first 100 post-2023 targets have 3.390/8.602. F1 therefore initially moves **up**, opposite its full-era mean difference. Causal trailing-100 F1 then falls to 2.55 by end-2024 and remains near 2.8; F2 settles near 8.

### Lightweight searched breakpoint check

Year-start boundaries 2015–2025 were searched with at least 100 observations per side. This is exploratory; no searched-boundary p-value is treated as preregistered.

| Criterion | Best | Next | Fixed 2023 rank |
|---|---|---|---:|
| F1 absolute Welch t | 2022 (`|t|=9.02`) | 2024 (`8.74`) | 3rd (`7.61`) |
| F2 absolute Welch t | 2023 (`7.26`) | 2024 (`6.40`) | 1st |
| Joint standardized two-segment SSE gain | 2015 (2014 high-gap outlier) | 2022, then 2024 | 4th |

Model comparison agrees that the two features do not share one clean 2023 mechanism. For F1, a fixed-step model fits better than a linear trend, but the best searched boundary is 2022 and the immediate 2023 move reverses sign. For F2, linear drift has lower BIC (4894.5) than a fixed 2023 step (4935.7); adding a 2023 step to trend does not improve BIC.

```text
F1_BREAK_DESCRIPTION: MULTIPLE_LEVEL_CHANGES; NO UNIQUE 2023 BREAK
F2_BREAK_DESCRIPTION: GRADUAL_DRIFT WITH A LOWER POST-2023 LEVEL
BREAK_PATTERN: NO_CLEAR_BREAK
```

## 5. Strict-prior availability

[Confirmed] Every one of the 31,174 emissions used by static consensus has a stored `history_cutoff < target_draw`. Each target has exactly one shared cutoff, the same 22 complete strategy identities, and one frozen emission per identity. F1 is computed only from that frozen ticket. F2 is computed from the history state before the target row is incorporated.

```text
STRICT_PRIOR_FEATURES: PASS
TARGET_OUTCOME_USED_BY_F1: NO
TARGET_OUTCOME_USED_BY_F2: NO
```

Strict-prior availability establishes deployability of the measurements, not predictive validity.

## 6. Joint era-state analysis

A two-variable logistic description using standardized F1/F2 separates the eras strongly:

| Metric | Result |
|---|---:|
| Apparent AUC | **0.650** |
| LR statistic, 2 df | 97.07 |
| LR p | `8.33e-22` |
| POST odds ratio per +1 SD F1 | 0.650 |
| POST odds ratio per +1 SD F2 | 0.566 |

Using fixed bins—F1 `0–2 / 3 / 4–6`, F2 full-sample tertiles `<=7.333 / 7.333–10.333 / >10.333`—the POST share is:

| F1 \ F2 | Low gap | Mid gap | High gap |
|---|---:|---:|---:|
| Low F1 (0–2) | 52.8% | 40.5% | 33.3% |
| Mid F1 (3) | 33.8% | 28.1% | 19.4% |
| High F1 (4–6) | 24.1% | 21.4% | 20.8% |

```text
JOINT_ERA_STATE_SIGNAL: STRONG
```

This is regime description. Calendar date itself already reveals era, so era classification is not a useful prediction product.

## 7. Joint target-success analysis

### Model comparison

| Development analysis | AUC | Proper-loss/result |
|---|---:|---|
| Continuous F1+F2, unadjusted | 0.565 | LR p 0.015; partly era-mediated |
| Era only | 0.566 | Brier 0.13491 |
| Era + continuous F1+F2 | 0.595 | +0.029 AUC; incremental LR p 0.031 |
| PRE-only continuous F1+F2 | 0.552 | LR p 0.114 |
| POST-only continuous F1+F2 | 0.571 | LR p 0.158 |
| Strict-forward continuous model, 2017–2026 | 0.541 | Brier/log loss slightly worse than rolling-rate baseline |

F2 has no monotone target relationship: low/mid/high-gap M2+ rates are 15.20% / 17.63% / 16.13%.

The fixed, non-optimized F1-low state (`F1 <= 2`) is the only target-level clue worth retaining:

| Cohort | F1 low | Other F1 | Difference |
|---|---:|---:|---:|
| PRE_2023 | 42/227 = 18.50% | 95/769 = 12.35% | +6.15 pp |
| POST_2023 | 45/172 = 26.16% | 49/249 = 19.68% | +6.48 pp |
| All | 87/399 = 21.80% | 144/1,018 = 14.15% | +7.65 pp |

Era-adjusted F1-low odds ratio is 1.54 (development LR p 0.0059); it is positive in 9/13 individual years. However, POST-only evidence is uncertain (OR 1.45, p 0.118), several years reverse direction, and discovery occurred on fully exposed development data. A strict-forward categorical F1/F2 model reaches only AUC 0.536 versus 0.524 for the rolling-rate baseline, with tiny Brier/log-loss improvements (0.14034 vs 0.14083; 0.45501 vs 0.45586).

### Fixed 3x3 conditional table

Each cell is `n; M2+ rate; difference from 16.30% overall`.

| F1 \ F2 | Low gap (`<=7.333`) | Mid gap | High gap (`>10.333`) |
|---|---|---|---|
| Low F1 (0–2) | 159; 20.13%; +3.82 pp | 111; 24.32%; +8.02 pp | 129; 21.71%; +5.40 pp |
| Mid F1 (3) | 154; 11.04%; −5.26 pp | 167; 16.17%; −0.13 pp | 144; 14.58%; −1.72 pp |
| High F1 (4–6) | 174; 14.37%; −1.93 pp | 187; 14.97%; −1.33 pp | 192; 13.54%; −2.76 pp |

The low-F1 lift appears across all F2 bins; F2 adds no stable ordering. This is hypothesis generation, not a validated trust/fallback gate.

```text
JOINT_TARGET_M2_SIGNAL: WEAK
F1_LOW_STATE: RETAIN_FOR_FUTURE_LOCKED_VALIDATION
F2_TARGET_GATE: NOT_SUPPORTED
```

## 8. Strategy/pipeline composition check

The sealed matrix contains 23 identities, of which the same 22 complete streams are used at every target. Across those 22:

- strategy identity and family headcount are constant;
- every strategy has exactly one version across successful emissions;
- artifact/emission schema is always 1.0.0;
- the source snapshot and replay code authority are pinned once;
- every target has one strict-prior cutoff shared across all 22 streams.

No strategy availability, identity, family-mix, implementation-version, schema, or consensus-composition boundary coincides with 2023.

Emission behavior does change under the fixed composition:

| All 22 strategy emissions | PRE | POST | Delta |
|---|---:|---:|---:|
| Mean slots in 1–12 per emitted ticket | 1.624 | 1.479 | −0.145 |
| Mean emitted-ticket gap | 10.370 | 8.795 | −1.575 |

Fifteen of 22 strategies reduce low-band emission and 21/22 reduce emitted-ticket gap. The largest low-band reductions are the dynamic-frequency stream (−0.923 slot) and graph predictor (−0.564); the largest gap reductions occur in P0/deviation bet-2, short-window deviation, and pure-cold streams (about −4.95 to −5.49 draws). These are associations with evolving input history, not causal attributions.

```text
STRATEGY_SIDE_BREAK: PARTIAL
  # broad emission behavior changes, but no common sharp 2023 breakpoint
PIPELINE_OR_VERSION_BREAK: NOT_FOUND
PIPELINE_OR_STRATEGY_COMPOSITION_EXPLANATION: POSSIBLE VIA INPUT-DRIVEN EMISSION BEHAVIOR; COMPOSITION ITSELF NOT FOUND
```

## 9. Format-contamination check

The authoritative 3,149-row history contains 1,314 incompatible pre-2014 rows. Recomputing the *measurement* while leaving the frozen consensus tickets unchanged gives:

| Gap history | PRE mean | POST mean | Delta | Raw p |
|---|---:|---:|---:|---:|
| Stored mixed-history F2 | 10.071 | 8.219 | −1.853 | `6.34e-13` |
| Valid 6-of-49 rows only (1,835 rows) | 9.284 | 8.219 | −1.065 | `1.52e-08` |
| 2014+ target-only history (n=1,393 usable) | 9.312 | 8.219 | −1.093 | `6.94e-09` |

Removing incompatible rows attenuates about 42.5% of the raw mean difference, but the F2 shift remains. The incompatible-history share declines smoothly from 75.87% at the first target to 48.17% at the first 2023 target and 41.74% at the end; its correlations with F1/F2 are +0.135/+0.249. That dilution is a plausible contributor to gradual strategy behavior, not a complete explanation.

All 1,417 target outcomes themselves lie in the homogeneous 2014–2026 6-of-49 era. F1 still reflects tickets emitted by strategies that consumed the mixed upstream history; determining the causal effect on F1 requires cleaned-history re-emission and cannot be inferred from relabeling stored tickets.

```text
DOES_THE_F1_F2_BREAK_PERSIST_WITHIN_HOMOGENEOUS_MODERN_6_OF_49_HISTORY: YES FOR THE OBSERVED TARGET TABLE AND CLEANED GAP MEASUREMENT
FORMAT_CONTAMINATION_EXPLAINS_F1_F2: PARTIAL
```

## 10. Predictive versus structural interpretation

`STRUCTURAL_INTERPRETATION:` F1/F2 are strong descriptors of how a fixed 22-stream consensus system responds to an evolving historical input corpus. Their evolution is distributed across strategies and is not explained by a catalog, code-version, schema, or stream-composition switch.

`PREDICTIVE_INTERPRETATION:` F1-low is a weak, development-only confidence-state clue; F2 does not add a stable target ordering. The pair does not yet justify a production gate, fallback selector, or Top-6 reranker. Era separation is much stronger than target discrimination.

The correct label is therefore **STRUCTURAL / REGIME DESCRIPTOR WITH ONE WEAK F1 TARGET HYPOTHESIS**, not a validated predictive gate.

## 11. Top mechanism candidates

1. **Mixed-history dilution under fixed strategy code — supported as a contributor.** The incompatible share falls continuously while most streams reduce gap and low-band emission. Clean-gap sensitivity proves it is only partial.
2. **Strategy-specific response to evolving valid history — supported behavior, unresolved cause.** Frequency/graph streams dominate low-band change; deviation/hot-cold/P0 streams dominate gap change despite constant identities and versions.
3. **A genuine post-2023 ticket/outcome alignment state — unresolved.** The M2+ step remains much sharper than F1/F2's non-common chronology. F1/F2 therefore do not explain the outcome anomaly; genuinely new temporal information is still needed.

## 12. Next research direction

| Option | Evidence-based decision |
|---|---|
| F1/F2 consensus-confidence model | Retain F1-low for later locked validation; do not dispatch now because discrimination and forward proper-loss gain are weak and all current outcomes are exposed. |
| Strategy-composition model | Do not select: composition, versions, schemas, and identities are constant. |
| Homogeneous-history rebuild | High-value data-integrity/mechanism follow-up before any cleaned-consensus claim, but it does not replace the next new-information experiment because the clean-gap shift persists. |
| EH04 / new temporal information | **Select:** information-orthogonal to static consensus and capable of explaining or falsifying target-level temporal signal directly. |

```text
NEXT_RESEARCH_DIRECTION: EXTERNAL_FRONTIER_HYPOTHESIS — EH04_CONTEXT_TREE_WEIGHTED_SYMBOLIC_RESIDUAL_FORECASTER
WHY_THIS_DIRECTION: F1/F2 mostly explain structural era state and only weakly explain target M2; EH04 remains the best bounded test of genuinely new predictive information.
NEXT_TASK_TRACK: B
```

This preserves the pre-interim Track D selection. If EH04 is already active, continue it without a parallel F1/F2 task; no EH04 report, ticket results, interim metrics, development leaderboard, or locked configuration was read here.

## 13. Minimal next-task handoff

`NEXT_B_TASK_ID:` `B649_TRACK_B_EH04_CONTEXT_TREE_WEIGHTED_SYMBOLIC_RESIDUAL_FORECASTER_DISCOVERY_R1`

`TITLE:` EH04 Context-Tree-Weighted Symbolic Residual Forecaster Discovery

`RESEARCH_QUESTION:` Does variable-order, strict-prior symbolic temporal context add per-number predictive information beyond IID, simple frequency, fixed-order Markov controls, and frozen static consensus?

`WHY_NOW:` Same-surface F1/F2 state explains era far better than target success; EH04 tests a genuinely different information source. F1-low remains a frozen secondary hypothesis for later disjoint validation, not a tuning input.

`DISCOVERY_MODE:` YES

`INPUTS:` Strict-prior per-number appearance/gap/rank symbol streams with historical-format validity made explicit; frozen static consensus only as comparator or one bounded blend arm. If an EH04 configuration is already locked, do not alter it from this report.

`SEARCH_SPACE:` Bounded symbol family, fold-local bins, maximum CTW depth, minimum context support, one simple calibration option, candidate K, standalone CTW, and one bounded consensus blend. No F1/F2 threshold zoo, residual reranker, portfolio geometry, or post-evaluation rescue.

`DEVELOPMENT_VALIDATION:` Nested expanding-window prequential development evaluation; select inside inner chronological folds, evaluate information gain on non-overlapping outer folds, then lock before any genuinely disjoint future outcomes are read.

`PRIMARY_BASELINE:` STATIC_CONSENSUS; information baselines IID/uniform, trailing frequency, and fixed-order Markov depths 1–3.

`SUCCESS_METRIC:` Stable outer-fold log-loss/code-length improvement over every simple temporal control, followed by a locked one-ticket M2+ improvement over contemporaneous static consensus. For a future 300-target disjoint evaluation, require at least +6 M2+ targets and positive delta in at least 4/6 blocks.

`STOP_OR_PIVOT:` Stop if EH04 fails the proper-loss controls, fails chronological stability, fails locked M2+ transfer, or needs unbounded/post-evaluation tuning. Do not rescue it with exposed outcomes.

`EXPECTED_OUTPUT:` One compact discovery report, one locked configuration, inner/outer prequential summaries, per-target scores and one legal ticket per arm, proper-loss/calibration and M1+/M2+/M3+/M4+ block results, leakage/equal-budget checks, and one bounded decision.

## 14. Validation and boundaries

```text
ERA_P_0_0005_INDEPENDENT_REPRODUCTION: PASS
FEATURE_DEFINITIONS_DOCUMENTED: PASS
RAW_AND_CORRECTED_TESTS_DISTINGUISHED: PASS
BREAKPOINT_VS_DRIFT_CLASSIFICATION: PASS
ERA_AND_TARGET_ANALYSES_SEPARATED: PASS
STRICT_PRIOR_CHECK: PASS
FORMAT_CONTAMINATION_CHECK: PASS
PIPELINE_STRATEGY_CHECK: PASS
EXACTLY_ONE_NEXT_DIRECTION: PASS
B_EH04_INTERIM_DATA_USED: NO
COHORT_V2_PROSPECTIVE_DATA_USED: NO
REPO_MUTATION: NONE
DB_MUTATION: NONE
```

Limitations: all 1,417 outcomes are exposed development data; apparent p-values are descriptive after discovery; the breakpoint scan was searched; no cleaned strategy re-emission or prospective validation was run; causality remains unresolved.

INTENT: code/data describe F1/F2 as strong era separators but do not establish a causal target gate; the check/task expects separate era-versus-M2 mechanism evidence and one next direction; the opened continuation packet says only meaningful strict-prior target signal may justify an F1/F2 consensus-state model, otherwise new temporal information retains priority.

END
