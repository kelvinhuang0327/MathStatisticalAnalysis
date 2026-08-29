# Rolling selector stability decomposition R1

This is descriptive attribution of one already-completed historical experiment. It does not rerun a strategy, alter the selector, optimize a window, or make a future-performance claim.

## Sealed source and accounting

- Source path: `docs/research/matrix-native-results/strategy-matrix-causal-rolling-selector-pilot-r1-result.json`
- Source HEAD: `abc367bd6d8b59d01ecc4d79e56c787bbc03cd20`
- Source tree: `bf430efd66b7ce1ac38ee04fb0052e8c55cc972c`
- Source SHA-256: `04df0bfdffcf4ecc05d4f2ac3f58cfa1fa301061c5f1c30e549ddc3b5b174157`
- Cells accounted for: 22
- Experiments accounted for: 66
- Available experiments: 62
- Sign classification uses the exact numerator/denominator only; `decimal_12` is not used.

## Definitions

- POSITIVE/ZERO/NEGATIVE follow the sign of the exact rolling-minus-frozen rational delta.
- INCONCLUSIVE means the source window is unavailable; no sign is inferred.
- Repeated positive means POSITIVE in at least two available windows.
- Sign reversal means an available-window pair contains one POSITIVE and one NEGATIVE.
- A material selected-strategy change means the exact dominant strategy identity set changes across available windows. No magnitude threshold is used.

## Complete experiment decomposition

| Cell | K | Window | Class | Available | Exact delta | Switches | Switch group | ZERO with switches=0 | Frozen strategy | Dominant rolling strategy (count) |
|---|---:|---|---|---|---:|---:|---|---|---|---|
| B649:K2 | 2 | W50 | INCONCLUSIVE | NO | — | 0 | INCONCLUSIVE | N/A | — | — |
| B649:K2 | 2 | W300 | INCONCLUSIVE | NO | — | 0 | INCONCLUSIVE | N/A | — | — |
| B649:K2 | 2 | W750 | INCONCLUSIVE | NO | — | 0 | INCONCLUSIVE | N/A | — | — |
| B649:K3 | 3 | W50 | POSITIVE | YES | 2/327 | 69 | SWITCHING_ACTIVE | N/A | legacy_biglotto__test_mwsc__ba37643d6a3b | legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2 (118) |
| B649:K3 | 3 | W300 | NEGATIVE | YES | -7/404 | 28 | SWITCHING_ACTIVE | N/A | legacy_biglotto__test_dcb__c3299c25ca59 | legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2 (175) |
| B649:K3 | 3 | W750 | INCONCLUSIVE | NO | — | 0 | INCONCLUSIVE | N/A | — | — |
| P638:K1 | 1 | W50 | NEGATIVE | YES | -5/847 | 115 | SWITCHING_ACTIVE | N/A | power_c07_borda_ensemble_1bet | power_biglotto_moderate_rank_1bet (178) |
| P638:K1 | 1 | W300 | ZERO | YES | 0/1 | 21 | SWITCHING_ACTIVE | NO | power_c07_borda_ensemble_1bet | power_c07_borda_ensemble_1bet (264) |
| P638:K1 | 1 | W750 | POSITIVE | YES | 5/147 | 4 | SWITCHING_ACTIVE | N/A | power_c07_borda_ensemble_1bet | power_biglotto_moderate_rank_1bet (72) |
| P638:K2 | 2 | W50 | NEGATIVE | YES | -9/1783 | 241 | SWITCHING_ACTIVE | N/A | power_biglotto_p0_echo_2bet | power_momentum_2bet (153) |
| P638:K2 | 2 | W300 | POSITIVE | YES | 1/219 | 69 | SWITCHING_ACTIVE | N/A | power_biglotto_p0_echo_2bet | power_fourier_gap_rebound_2bet (435) |
| P638:K2 | 2 | W750 | POSITIVE | YES | 9/361 | 34 | SWITCHING_ACTIVE | N/A | power_momentum_2bet | power_fourier_gap_rebound_2bet (662) |
| P638:K3 | 3 | W50 | POSITIVE | YES | 2/141 | 196 | SWITCHING_ACTIVE | N/A | power_biglotto_random_zone_split_3bet | midfreq_fourier_mk_3bet (293) |
| P638:K3 | 3 | W300 | NEGATIVE | YES | -21/1583 | 72 | SWITCHING_ACTIVE | N/A | midfreq_fourier_mk_3bet | midfreq_fourier_mk_3bet (597) |
| P638:K3 | 3 | W750 | POSITIVE | YES | 14/1133 | 11 | SWITCHING_ACTIVE | N/A | power_biglotto_exhaustive_audit_3bet | midfreq_fourier_mk_3bet (503) |
| P638:K4 | 4 | W50 | POSITIVE | YES | 17/1832 | 114 | SWITCHING_ACTIVE | N/A | power_apriori_ext_4bet | pp3_freqort_4bet (920) |
| P638:K4 | 4 | W300 | NEGATIVE | YES | -11/1582 | 41 | SWITCHING_ACTIVE | N/A | pp3_freqort_4bet | pp3_freqort_4bet (1262) |
| P638:K4 | 4 | W750 | NEGATIVE | YES | -1/566 | 4 | SWITCHING_ACTIVE | N/A | pp3_freqort_4bet | pp3_freqort_4bet (1056) |
| P638:K5 | 5 | W50 | NEGATIVE | YES | -9/1853 | 79 | SWITCHING_ACTIVE | N/A | power_orthogonal_5bet | power_orthogonal_5bet (961) |
| P638:K5 | 5 | W300 | NEGATIVE | YES | -10/1603 | 55 | SWITCHING_ACTIVE | N/A | power_orthogonal_5bet | power_orthogonal_5bet (915) |
| P638:K5 | 5 | W750 | NEGATIVE | YES | -10/1153 | 12 | SWITCHING_ACTIVE | N/A | power_orthogonal_5bet | power_orthogonal_5bet (867) |
| P638:K7 | 7 | W50 | POSITIVE | YES | 34/1783 | 92 | SWITCHING_ACTIVE | N/A | power_biglotto_gemini_phase2_7bet | power_biglotto_elite_7bet (1170) |
| P638:K7 | 7 | W300 | NEGATIVE | YES | -11/1533 | 32 | SWITCHING_ACTIVE | N/A | power_biglotto_elite_7bet | power_biglotto_elite_7bet (1389) |
| P638:K7 | 7 | W750 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_elite_7bet | power_biglotto_elite_7bet (1083) |
| P638:K10 | 10 | W50 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_backtest_10bet | power_biglotto_backtest_10bet (1853) |
| P638:K10 | 10 | W300 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_backtest_10bet | power_biglotto_backtest_10bet (1603) |
| P638:K10 | 10 | W750 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_backtest_10bet | power_biglotto_backtest_10bet (1153) |
| P638:K11 | 11 | W50 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_variant_history_11bet | power_biglotto_variant_history_11bet (1853) |
| P638:K11 | 11 | W300 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_variant_history_11bet | power_biglotto_variant_history_11bet (1603) |
| P638:K11 | 11 | W750 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_variant_history_11bet | power_biglotto_variant_history_11bet (1153) |
| P638:K12 | 12 | W50 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_core_satellite_12bet | power_biglotto_core_satellite_12bet (1853) |
| P638:K12 | 12 | W300 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_core_satellite_12bet | power_biglotto_core_satellite_12bet (1603) |
| P638:K12 | 12 | W750 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_core_satellite_12bet | power_biglotto_core_satellite_12bet (1153) |
| P638:K25 | 25 | W50 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_auto_optimizer_alpha_25bet | power_biglotto_auto_optimizer_alpha_25bet (1853) |
| P638:K25 | 25 | W300 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_auto_optimizer_alpha_25bet | power_biglotto_auto_optimizer_alpha_25bet (1603) |
| P638:K25 | 25 | W750 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | power_biglotto_auto_optimizer_alpha_25bet | power_biglotto_auto_optimizer_alpha_25bet (1153) |
| T539:K1 | 1 | W50 | NEGATIVE | YES | -7/1136 | 887 | SWITCHING_ACTIVE | N/A | 539_3bet_orthogonal | acb_markov_midfreq (494) |
| T539:K1 | 1 | W300 | POSITIVE | YES | 17/1086 | 259 | SWITCHING_ACTIVE | N/A | t539_biglotto_short_window_deviation_1bet | t539_biglotto_dms_1bet (691) |
| T539:K1 | 1 | W750 | POSITIVE | YES | 3/332 | 174 | SWITCHING_ACTIVE | N/A | t539_biglotto_short_window_deviation_1bet | t539_biglotto_dms_1bet (870) |
| T539:K2 | 2 | W50 | NEGATIVE | YES | -39/2890 | 829 | SWITCHING_ACTIVE | N/A | t539_biglotto_two_bet_elite_2bet | midfreq_acb_2bet (1049) |
| T539:K2 | 2 | W300 | POSITIVE | YES | 9/790 | 287 | SWITCHING_ACTIVE | N/A | t539_biglotto_two_bet_optimizer_v2_2bet | midfreq_acb_2bet (1304) |
| T539:K2 | 2 | W750 | POSITIVE | YES | 1/5080 | 126 | SWITCHING_ACTIVE | N/A | t539_biglotto_two_bet_elite_2bet | midfreq_acb_2bet (1509) |
| T539:K3 | 3 | W50 | POSITIVE | YES | 25/1156 | 889 | SWITCHING_ACTIVE | N/A | t539_biglotto_zdp_3bet | daily539_f4cold_3bet (1155) |
| T539:K3 | 3 | W300 | NEGATIVE | YES | -1/790 | 262 | SWITCHING_ACTIVE | N/A | t539_biglotto_exhaustive_audit_3bet | daily539_f4cold_3bet (1344) |
| T539:K3 | 3 | W750 | POSITIVE | YES | 23/2540 | 118 | SWITCHING_ACTIVE | N/A | t539_biglotto_exhaustive_audit_3bet | daily539_f4cold_3bet (1991) |
| T539:K4 | 4 | W50 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_tme_optimizer_4bet | t539_biglotto_tme_optimizer_4bet (5879) |
| T539:K4 | 4 | W300 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_tme_optimizer_4bet | t539_biglotto_tme_optimizer_4bet (5629) |
| T539:K4 | 4 | W750 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_tme_optimizer_4bet | t539_biglotto_tme_optimizer_4bet (5179) |
| T539:K5 | 5 | W50 | POSITIVE | YES | 477/5780 | 193 | SWITCHING_ACTIVE | N/A | t539_biglotto_five_me_5bet | daily539_f4cold_5bet (4656) |
| T539:K5 | 5 | W300 | NEGATIVE | YES | -2/2765 | 2 | SWITCHING_ACTIVE | N/A | daily539_f4cold_5bet | daily539_f4cold_5bet (5486) |
| T539:K5 | 5 | W750 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | daily539_f4cold_5bet | daily539_f4cold_5bet (5080) |
| T539:K7 | 7 | W50 | NEGATIVE | YES | -57/2890 | 280 | SWITCHING_ACTIVE | N/A | t539_biglotto_gemini_phase2_7bet | t539_biglotto_gemini_phase2_7bet (4620) |
| T539:K7 | 7 | W300 | NEGATIVE | YES | -1/790 | 10 | SWITCHING_ACTIVE | N/A | t539_biglotto_gemini_phase2_7bet | t539_biglotto_gemini_phase2_7bet (5457) |
| T539:K7 | 7 | W750 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_gemini_phase2_7bet | t539_biglotto_gemini_phase2_7bet (5080) |
| T539:K10 | 10 | W50 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_backtest_10bet | t539_biglotto_backtest_10bet (5879) |
| T539:K10 | 10 | W300 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_backtest_10bet | t539_biglotto_backtest_10bet (5629) |
| T539:K10 | 10 | W750 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_backtest_10bet | t539_biglotto_backtest_10bet (5179) |
| T539:K11 | 11 | W50 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_variant_history_11bet | t539_biglotto_variant_history_11bet (5860) |
| T539:K11 | 11 | W300 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_variant_history_11bet | t539_biglotto_variant_history_11bet (5610) |
| T539:K11 | 11 | W750 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_variant_history_11bet | t539_biglotto_variant_history_11bet (5160) |
| T539:K12 | 12 | W50 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_core_satellite_12bet | t539_biglotto_core_satellite_12bet (5879) |
| T539:K12 | 12 | W300 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_core_satellite_12bet | t539_biglotto_core_satellite_12bet (5629) |
| T539:K12 | 12 | W750 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_core_satellite_12bet | t539_biglotto_core_satellite_12bet (5179) |
| T539:K25 | 25 | W50 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_auto_optimizer_alpha_25bet | t539_biglotto_auto_optimizer_alpha_25bet (5879) |
| T539:K25 | 25 | W300 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_auto_optimizer_alpha_25bet | t539_biglotto_auto_optimizer_alpha_25bet (5629) |
| T539:K25 | 25 | W750 | ZERO | YES | 0/1 | 0 | ZERO_SWITCH | YES | t539_biglotto_auto_optimizer_alpha_25bet | t539_biglotto_auto_optimizer_alpha_25bet (5179) |

## Cross-window cell patterns

| Cell | Available | W50 / W300 / W750 | Repeated positive | Reversal | Switch-active windows | Dominant identity change |
|---|---:|---|---|---|---:|---|
| B649:K2 | 0 | W50=INCONCLUSIVE / W300=INCONCLUSIVE / W750=INCONCLUSIVE | NO | NO | 0 | INCONCLUSIVE_FEWER_THAN_TWO_AVAILABLE_WINDOWS |
| B649:K3 | 2 | W50=POSITIVE / W300=NEGATIVE / W750=INCONCLUSIVE | NO | YES | 2 | NO_DOMINANT_IDENTITY_STABLE |
| P638:K1 | 3 | W50=NEGATIVE / W300=ZERO / W750=POSITIVE | NO | YES | 3 | YES_DOMINANT_IDENTITY_CHANGED |
| P638:K2 | 3 | W50=NEGATIVE / W300=POSITIVE / W750=POSITIVE | YES | YES | 3 | YES_DOMINANT_IDENTITY_CHANGED |
| P638:K3 | 3 | W50=POSITIVE / W300=NEGATIVE / W750=POSITIVE | YES | YES | 3 | NO_DOMINANT_IDENTITY_STABLE |
| P638:K4 | 3 | W50=POSITIVE / W300=NEGATIVE / W750=NEGATIVE | NO | YES | 3 | NO_DOMINANT_IDENTITY_STABLE |
| P638:K5 | 3 | W50=NEGATIVE / W300=NEGATIVE / W750=NEGATIVE | NO | NO | 3 | NO_DOMINANT_IDENTITY_STABLE |
| P638:K7 | 3 | W50=POSITIVE / W300=NEGATIVE / W750=ZERO | NO | YES | 2 | NO_DOMINANT_IDENTITY_STABLE |
| P638:K10 | 3 | W50=ZERO / W300=ZERO / W750=ZERO | NO | NO | 0 | NO_DOMINANT_IDENTITY_STABLE |
| P638:K11 | 3 | W50=ZERO / W300=ZERO / W750=ZERO | NO | NO | 0 | NO_DOMINANT_IDENTITY_STABLE |
| P638:K12 | 3 | W50=ZERO / W300=ZERO / W750=ZERO | NO | NO | 0 | NO_DOMINANT_IDENTITY_STABLE |
| P638:K25 | 3 | W50=ZERO / W300=ZERO / W750=ZERO | NO | NO | 0 | NO_DOMINANT_IDENTITY_STABLE |
| T539:K1 | 3 | W50=NEGATIVE / W300=POSITIVE / W750=POSITIVE | YES | YES | 3 | YES_DOMINANT_IDENTITY_CHANGED |
| T539:K2 | 3 | W50=NEGATIVE / W300=POSITIVE / W750=POSITIVE | YES | YES | 3 | NO_DOMINANT_IDENTITY_STABLE |
| T539:K3 | 3 | W50=POSITIVE / W300=NEGATIVE / W750=POSITIVE | YES | YES | 3 | NO_DOMINANT_IDENTITY_STABLE |
| T539:K4 | 3 | W50=ZERO / W300=ZERO / W750=ZERO | NO | NO | 0 | NO_DOMINANT_IDENTITY_STABLE |
| T539:K5 | 3 | W50=POSITIVE / W300=NEGATIVE / W750=ZERO | NO | YES | 2 | NO_DOMINANT_IDENTITY_STABLE |
| T539:K7 | 3 | W50=NEGATIVE / W300=NEGATIVE / W750=ZERO | NO | NO | 2 | NO_DOMINANT_IDENTITY_STABLE |
| T539:K10 | 3 | W50=ZERO / W300=ZERO / W750=ZERO | NO | NO | 0 | NO_DOMINANT_IDENTITY_STABLE |
| T539:K11 | 3 | W50=ZERO / W300=ZERO / W750=ZERO | NO | NO | 0 | NO_DOMINANT_IDENTITY_STABLE |
| T539:K12 | 3 | W50=ZERO / W300=ZERO / W750=ZERO | NO | NO | 0 | NO_DOMINANT_IDENTITY_STABLE |
| T539:K25 | 3 | W50=ZERO / W300=ZERO / W750=ZERO | NO | NO | 0 | NO_DOMINANT_IDENTITY_STABLE |

## Descriptive aggregates

### By lottery

| Lottery | Cells | Experiments | Available | Sign counts | Active / zero-switch / inconclusive |
|---|---:|---:|---:|---|---|
| B649 | 2 | 6 | 2 | POSITIVE=1, ZERO=0, NEGATIVE=1, INCONCLUSIVE=4 | 2 / 0 / 4 |
| P638 | 10 | 30 | 30 | POSITIVE=7, ZERO=14, NEGATIVE=9, INCONCLUSIVE=0 | 17 / 13 / 0 |
| T539 | 10 | 30 | 30 | POSITIVE=7, ZERO=17, NEGATIVE=6, INCONCLUSIVE=0 | 13 / 17 / 0 |

### By K

| K | Cells | Experiments | Available | Sign counts | Maximum switches |
|---:|---:|---:|---:|---|---:|
| 1 | 2 | 6 | 6 | POSITIVE=3, ZERO=1, NEGATIVE=2, INCONCLUSIVE=0 | 887 |
| 2 | 3 | 9 | 6 | POSITIVE=4, ZERO=0, NEGATIVE=2, INCONCLUSIVE=3 | 829 |
| 3 | 3 | 9 | 8 | POSITIVE=5, ZERO=0, NEGATIVE=3, INCONCLUSIVE=1 | 889 |
| 4 | 2 | 6 | 6 | POSITIVE=1, ZERO=3, NEGATIVE=2, INCONCLUSIVE=0 | 114 |
| 5 | 2 | 6 | 6 | POSITIVE=1, ZERO=1, NEGATIVE=4, INCONCLUSIVE=0 | 193 |
| 7 | 2 | 6 | 6 | POSITIVE=1, ZERO=2, NEGATIVE=3, INCONCLUSIVE=0 | 280 |
| 10 | 2 | 6 | 6 | POSITIVE=0, ZERO=6, NEGATIVE=0, INCONCLUSIVE=0 | 0 |
| 11 | 2 | 6 | 6 | POSITIVE=0, ZERO=6, NEGATIVE=0, INCONCLUSIVE=0 | 0 |
| 12 | 2 | 6 | 6 | POSITIVE=0, ZERO=6, NEGATIVE=0, INCONCLUSIVE=0 | 0 |
| 25 | 2 | 6 | 6 | POSITIVE=0, ZERO=6, NEGATIVE=0, INCONCLUSIVE=0 | 0 |

### By window

| Window | Experiments | Available | Sign counts | Maximum switches |
|---:|---:|---:|---|---:|
| W50 | 22 | 21 | POSITIVE=6, ZERO=9, NEGATIVE=6, INCONCLUSIVE=1 | 889 |
| W300 | 22 | 21 | POSITIVE=3, ZERO=10, NEGATIVE=8, INCONCLUSIVE=1 | 287 |
| W750 | 22 | 20 | POSITIVE=6, ZERO=12, NEGATIVE=2, INCONCLUSIVE=2 | 174 |

### By switch activity

| Group | Experiments | Available | Sign counts |
|---|---:|---:|---|
| SWITCHING_ACTIVE | 32 | 32 | POSITIVE=15, ZERO=1, NEGATIVE=16, INCONCLUSIVE=0 |
| ZERO_SWITCH | 30 | 30 | POSITIVE=0, ZERO=30, NEGATIVE=0, INCONCLUSIVE=0 |
| INCONCLUSIVE | 4 | 0 | POSITIVE=0, ZERO=0, NEGATIVE=0, INCONCLUSIVE=4 |

### By cell switching profile

| Cell profile | Cells | Available experiments | Sign counts | Repeated-positive cells | Reversal cells |
|---|---:|---:|---|---:|---:|
| SWITCHING_ACTIVE_IN_AT_LEAST_ONE_AVAILABLE_WINDOW | 12 | 35 | POSITIVE=15, ZERO=4, NEGATIVE=16, INCONCLUSIVE=1 | 5 | 10 |
| ZERO_SWITCH_ACROSS_ALL_AVAILABLE_WINDOWS | 9 | 27 | POSITIVE=0, ZERO=27, NEGATIVE=0, INCONCLUSIVE=0 | 0 | 0 |
| NO_AVAILABLE_WINDOWS | 1 | 0 | POSITIVE=0, ZERO=0, NEGATIVE=0, INCONCLUSIVE=3 | 0 | 0 |

Cell profiles: switching-active in at least one available window=12; zero-switch across all available windows=9; no available windows=1.

## Required diagnostic answers

1. **ZERO experiments with switch_count=0.** 30 of 31 ZERO experiments are zero-switch matches; 1 ZERO experiment is switching-active.

2. **Switching-active experiments only.** 32 total: POSITIVE=15, NEGATIVE=16, ZERO=1.

3. **Positive in at least two available windows.** P638:K2, P638:K3, T539:K1, T539:K2, T539:K3.

4. **Sign reversals.** B649:K3, P638:K1, P638:K2, P638:K3, P638:K4, P638:K7, T539:K1, T539:K2, T539:K3, T539:K5.

5. **K concentration.** K1-K3 contain 12 of 15 positive experiments. Full counts: K1=3, K2=4, K3=5, K4=1, K5=1, K7=1, K10=0, K11=0, K12=0, K25=0.

6. **Largest switching frequencies.** MIXED_AMONG_THREE_LARGEST_EXPERIMENTS. The three largest observed experiments are T539:K3 W50=889 (POSITIVE), T539:K1 W50=887 (NEGATIVE), T539:K2 W50=829 (NEGATIVE). The global maximum is 889.

7. **Descriptive candidates for a separately preregistered experiment.** P638:K2, P638:K3, T539:K1, T539:K2, T539:K3. These are identified only because positive signs repeat in at least two available, switching-active windows. This is not a promotion rule, and no future selector is defined here.

## Interpretation boundary

Every repeat-positive candidate also retains its full cross-window sign pattern above; a repeated historical sign is not evidence of future predictive advantage.

```text
NEW_HISTORICAL_REPLAY = NOT RUN
DB_ACCESS = NO
NEW_SELECTOR = NOT IMPLEMENTED
PHASE12_DEPENDENCY = NONE
PREDICTIVE_ADVANTAGE = NOT ESTABLISHED
PROFITABILITY = NOT ESTABLISHED
COMPOSITE_SCORE = NOT CREATED
PROMOTION_THRESHOLD = NOT CREATED
STATISTICAL_SIGNIFICANCE = NOT CLAIMED
```
