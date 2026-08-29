# Strategy Matrix causal rolling selector pilot R1

This pilot compares a strictly pre-target rolling strategy selector with a strategy frozen at the first eligible target. It is historical evidence only.

## Metric and causal contract

- Primary metric: official-any-prize rate per distinct target draw.
- Windows: SHORT=50, MEDIUM=300, LONG=750 prior completed comparable targets.
- Each cell uses one fixed candidate universe and the intersection of complete targets.
- Rolling and frozen outcomes are evaluated on identical targets.

## Rolling versus frozen results

| Lottery | Tickets | Window | Status | Targets | Candidates | Rolling | Frozen | Delta | Relative delta | Switches | Frozen strategy |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| B649 | 2 | 50 | EXCLUDED | 0 | 19 | — | — | — | — | 0 | — |
| B649 | 2 | 300 | EXCLUDED | 0 | 19 | — | — | — | — | 0 | — |
| B649 | 2 | 750 | EXCLUDED | 0 | 19 | — | — | — | — | 0 | — |
| B649 | 3 | 50 | COMPLETE | 654 | 19 | 21/218 | 59/654 | 2/327 | 4/59 | 69 | legacy_biglotto__test_mwsc__ba37643d6a3b |
| B649 | 3 | 300 | COMPLETE | 404 | 19 | 6/101 | 31/404 | -7/404 | -7/31 | 28 | legacy_biglotto__test_dcb__c3299c25ca59 |
| B649 | 3 | 750 | EXCLUDED | 0 | 19 | — | — | — | — | 0 | — |
| P638 | 1 | 50 | COMPLETE | 847 | 22 | 96/847 | 101/847 | -5/847 | -5/101 | 115 | power_c07_borda_ensemble_1bet |
| P638 | 1 | 300 | COMPLETE | 597 | 22 | 65/597 | 65/597 | 0/1 | 0/1 | 21 | power_c07_borda_ensemble_1bet |
| P638 | 1 | 750 | COMPLETE | 147 | 22 | 4/49 | 1/21 | 5/147 | 5/7 | 4 | power_c07_borda_ensemble_1bet |
| P638 | 2 | 50 | COMPLETE | 1783 | 21 | 312/1783 | 321/1783 | -9/1783 | -3/107 | 241 | power_biglotto_p0_echo_2bet |
| P638 | 2 | 300 | COMPLETE | 1533 | 21 | 284/1533 | 277/1533 | 1/219 | 7/277 | 69 | power_biglotto_p0_echo_2bet |
| P638 | 2 | 750 | COMPLETE | 1083 | 21 | 68/361 | 59/361 | 9/361 | 9/59 | 34 | power_momentum_2bet |
| P638 | 3 | 50 | COMPLETE | 1833 | 14 | 138/611 | 388/1833 | 2/141 | 13/194 | 196 | power_biglotto_random_zone_split_3bet |
| P638 | 3 | 300 | COMPLETE | 1583 | 14 | 338/1583 | 359/1583 | -21/1583 | -21/359 | 72 | midfreq_fourier_mk_3bet |
| P638 | 3 | 750 | COMPLETE | 1133 | 14 | 256/1133 | 22/103 | 14/1133 | 7/121 | 11 | power_biglotto_exhaustive_audit_3bet |
| P638 | 4 | 50 | COMPLETE | 1832 | 3 | 459/1832 | 221/916 | 17/1832 | 1/26 | 114 | power_apriori_ext_4bet |
| P638 | 4 | 300 | COMPLETE | 1582 | 3 | 403/1582 | 207/791 | -11/1582 | -11/414 | 41 | pp3_freqort_4bet |
| P638 | 4 | 750 | COMPLETE | 1132 | 3 | 153/566 | 77/283 | -1/566 | -1/154 | 4 | pp3_freqort_4bet |
| P638 | 5 | 50 | COMPLETE | 1853 | 3 | 488/1853 | 497/1853 | -9/1853 | -9/497 | 79 | power_orthogonal_5bet |
| P638 | 5 | 300 | COMPLETE | 1603 | 3 | 423/1603 | 433/1603 | -10/1603 | -10/433 | 55 | power_orthogonal_5bet |
| P638 | 5 | 750 | COMPLETE | 1153 | 3 | 312/1153 | 322/1153 | -10/1153 | -5/161 | 12 | power_orthogonal_5bet |
| P638 | 7 | 50 | COMPLETE | 1783 | 3 | 573/1783 | 539/1783 | 34/1783 | 34/539 | 92 | power_biglotto_gemini_phase2_7bet |
| P638 | 7 | 300 | COMPLETE | 1533 | 3 | 509/1533 | 520/1533 | -11/1533 | -11/520 | 32 | power_biglotto_elite_7bet |
| P638 | 7 | 750 | COMPLETE | 1083 | 3 | 370/1083 | 370/1083 | 0/1 | 0/1 | 0 | power_biglotto_elite_7bet |
| P638 | 10 | 50 | COMPLETE | 1853 | 1 | 590/1853 | 590/1853 | 0/1 | 0/1 | 0 | power_biglotto_backtest_10bet |
| P638 | 10 | 300 | COMPLETE | 1603 | 1 | 520/1603 | 520/1603 | 0/1 | 0/1 | 0 | power_biglotto_backtest_10bet |
| P638 | 10 | 750 | COMPLETE | 1153 | 1 | 380/1153 | 380/1153 | 0/1 | 0/1 | 0 | power_biglotto_backtest_10bet |
| P638 | 11 | 50 | COMPLETE | 1853 | 1 | 709/1853 | 709/1853 | 0/1 | 0/1 | 0 | power_biglotto_variant_history_11bet |
| P638 | 11 | 300 | COMPLETE | 1603 | 1 | 611/1603 | 611/1603 | 0/1 | 0/1 | 0 | power_biglotto_variant_history_11bet |
| P638 | 11 | 750 | COMPLETE | 1153 | 1 | 435/1153 | 435/1153 | 0/1 | 0/1 | 0 | power_biglotto_variant_history_11bet |
| P638 | 12 | 50 | COMPLETE | 1853 | 1 | 733/1853 | 733/1853 | 0/1 | 0/1 | 0 | power_biglotto_core_satellite_12bet |
| P638 | 12 | 300 | COMPLETE | 1603 | 1 | 640/1603 | 640/1603 | 0/1 | 0/1 | 0 | power_biglotto_core_satellite_12bet |
| P638 | 12 | 750 | COMPLETE | 1153 | 1 | 466/1153 | 466/1153 | 0/1 | 0/1 | 0 | power_biglotto_core_satellite_12bet |
| P638 | 25 | 50 | COMPLETE | 1853 | 1 | 840/1853 | 840/1853 | 0/1 | 0/1 | 0 | power_biglotto_auto_optimizer_alpha_25bet |
| P638 | 25 | 300 | COMPLETE | 1603 | 1 | 743/1603 | 743/1603 | 0/1 | 0/1 | 0 | power_biglotto_auto_optimizer_alpha_25bet |
| P638 | 25 | 750 | COMPLETE | 1153 | 1 | 544/1153 | 544/1153 | 0/1 | 0/1 | 0 | power_biglotto_auto_optimizer_alpha_25bet |
| T539 | 1 | 50 | COMPLETE | 5680 | 25 | 123/1136 | 65/568 | -7/1136 | -7/130 | 887 | 539_3bet_orthogonal |
| T539 | 1 | 300 | COMPLETE | 5430 | 25 | 113/905 | 593/5430 | 17/1086 | 85/593 | 259 | t539_biglotto_short_window_deviation_1bet |
| T539 | 1 | 750 | COMPLETE | 4980 | 25 | 39/332 | 9/83 | 3/332 | 1/12 | 174 | t539_biglotto_short_window_deviation_1bet |
| T539 | 2 | 50 | COMPLETE | 5780 | 13 | 63/289 | 669/2890 | -39/2890 | -13/223 | 829 | t539_biglotto_two_bet_elite_2bet |
| T539 | 2 | 300 | COMPLETE | 5530 | 13 | 626/2765 | 1189/5530 | 9/790 | 63/1189 | 287 | t539_biglotto_two_bet_optimizer_v2_2bet |
| T539 | 2 | 750 | COMPLETE | 5080 | 13 | 233/1016 | 291/1270 | 1/5080 | 1/1164 | 126 | t539_biglotto_two_bet_elite_2bet |
| T539 | 3 | 50 | COMPLETE | 5780 | 13 | 365/1156 | 5/17 | 25/1156 | 5/68 | 889 | t539_biglotto_zdp_3bet |
| T539 | 3 | 300 | COMPLETE | 5530 | 13 | 1811/5530 | 909/2765 | -1/790 | -7/1818 | 262 | t539_biglotto_exhaustive_audit_3bet |
| T539 | 3 | 750 | COMPLETE | 5080 | 13 | 429/1270 | 167/508 | 23/2540 | 23/835 | 118 | t539_biglotto_exhaustive_audit_3bet |
| T539 | 4 | 50 | COMPLETE | 5879 | 1 | 2268/5879 | 2268/5879 | 0/1 | 0/1 | 0 | t539_biglotto_tme_optimizer_4bet |
| T539 | 4 | 300 | COMPLETE | 5629 | 1 | 2162/5629 | 2162/5629 | 0/1 | 0/1 | 0 | t539_biglotto_tme_optimizer_4bet |
| T539 | 4 | 750 | COMPLETE | 5179 | 1 | 1976/5179 | 1976/5179 | 0/1 | 0/1 | 0 | t539_biglotto_tme_optimizer_4bet |
| T539 | 5 | 50 | COMPLETE | 5780 | 3 | 3007/5780 | 253/578 | 477/5780 | 477/2530 | 193 | t539_biglotto_five_me_5bet |
| T539 | 5 | 300 | COMPLETE | 5530 | 3 | 1473/2765 | 295/553 | -2/2765 | -2/1475 | 2 | daily539_f4cold_5bet |
| T539 | 5 | 750 | COMPLETE | 5080 | 3 | 68/127 | 68/127 | 0/1 | 0/1 | 0 | daily539_f4cold_5bet |
| T539 | 7 | 50 | COMPLETE | 5780 | 3 | 1543/2890 | 160/289 | -57/2890 | -57/1600 | 280 | t539_biglotto_gemini_phase2_7bet |
| T539 | 7 | 300 | COMPLETE | 5530 | 3 | 3047/5530 | 1527/2765 | -1/790 | -7/3054 | 10 | t539_biglotto_gemini_phase2_7bet |
| T539 | 7 | 750 | COMPLETE | 5080 | 3 | 1403/2540 | 1403/2540 | 0/1 | 0/1 | 0 | t539_biglotto_gemini_phase2_7bet |
| T539 | 10 | 50 | COMPLETE | 5879 | 1 | 3239/5879 | 3239/5879 | 0/1 | 0/1 | 0 | t539_biglotto_backtest_10bet |
| T539 | 10 | 300 | COMPLETE | 5629 | 1 | 3101/5629 | 3101/5629 | 0/1 | 0/1 | 0 | t539_biglotto_backtest_10bet |
| T539 | 10 | 750 | COMPLETE | 5179 | 1 | 2845/5179 | 2845/5179 | 0/1 | 0/1 | 0 | t539_biglotto_backtest_10bet |
| T539 | 11 | 50 | COMPLETE | 5860 | 1 | 3857/5860 | 3857/5860 | 0/1 | 0/1 | 0 | t539_biglotto_variant_history_11bet |
| T539 | 11 | 300 | COMPLETE | 5610 | 1 | 1229/1870 | 1229/1870 | 0/1 | 0/1 | 0 | t539_biglotto_variant_history_11bet |
| T539 | 11 | 750 | COMPLETE | 5160 | 1 | 225/344 | 225/344 | 0/1 | 0/1 | 0 | t539_biglotto_variant_history_11bet |
| T539 | 12 | 50 | COMPLETE | 5879 | 1 | 3848/5879 | 3848/5879 | 0/1 | 0/1 | 0 | t539_biglotto_core_satellite_12bet |
| T539 | 12 | 300 | COMPLETE | 5629 | 1 | 3693/5629 | 3693/5629 | 0/1 | 0/1 | 0 | t539_biglotto_core_satellite_12bet |
| T539 | 12 | 750 | COMPLETE | 5179 | 1 | 3397/5179 | 3397/5179 | 0/1 | 0/1 | 0 | t539_biglotto_core_satellite_12bet |
| T539 | 25 | 50 | COMPLETE | 5879 | 1 | 4502/5879 | 4502/5879 | 0/1 | 0/1 | 0 | t539_biglotto_auto_optimizer_alpha_25bet |
| T539 | 25 | 300 | COMPLETE | 5629 | 1 | 4344/5629 | 4344/5629 | 0/1 | 0/1 | 0 | t539_biglotto_auto_optimizer_alpha_25bet |
| T539 | 25 | 750 | COMPLETE | 5179 | 1 | 3979/5179 | 3979/5179 | 0/1 | 0/1 | 0 | t539_biglotto_auto_optimizer_alpha_25bet |

## Cell coverage and selection details

### B649:K2

- Candidates: 19
- Comparable targets: 0 of 750
- Coverage-excluded/missing targets: 750
- Coverage exclusion reasons: `{"EXECUTION_FAILURE": 750}`
- SHORT: conclusion=INCONCLUSIVE_CANONICAL_COVERAGE_INSUFFICIENT; first=None; last=None; switches=0; selection_frequency=`{}`
- MEDIUM: conclusion=INCONCLUSIVE_CANONICAL_COVERAGE_INSUFFICIENT; first=None; last=None; switches=0; selection_frequency=`{}`
- LONG: conclusion=INCONCLUSIVE_CANONICAL_COVERAGE_INSUFFICIENT; first=None; last=None; switches=0; selection_frequency=`{}`

### B649:K3

- Candidates: 19
- Comparable targets: 704 of 750
- Coverage-excluded/missing targets: 46
- Coverage exclusion reasons: `{"EXECUTION_FAILURE": 46}`
- SHORT: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=109000077; last=115000081; switches=69; selection_frequency=`{"legacy_biglotto__backtest_sum_constraint__acb3b118300d": 91, "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2": 118, "legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5": 29, "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d": 1, "legacy_biglotto__core_satellite__611284461323": 20, "legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504": 41, "legacy_biglotto__test_asm__d39a233a4c75": 18, "legacy_biglotto__test_cag__7ca5343dfedd": 23, "legacy_biglotto__test_ces__78d17c530ab8": 42, "legacy_biglotto__test_cluster_cover__5b43959e7c55": 66, "legacy_biglotto__test_dcb__c3299c25ca59": 66, "legacy_biglotto__test_dms__b63442289bd5": 14, "legacy_biglotto__test_mwsc__ba37643d6a3b": 71, "legacy_biglotto__test_tme__f3bb5106dfe3": 21, "legacy_biglotto__test_zdp__e80cc7e95453": 33}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=111000114; last=115000081; switches=28; selection_frequency=`{"legacy_biglotto__backtest_sum_constraint__acb3b118300d": 18, "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2": 175, "legacy_biglotto__core_satellite__611284461323": 78, "legacy_biglotto__test_cluster_cover__5b43959e7c55": 33, "legacy_biglotto__test_dcb__c3299c25ca59": 100}`
- LONG: conclusion=INCONCLUSIVE_CANONICAL_COVERAGE_INSUFFICIENT; first=None; last=None; switches=0; selection_frequency=`{}`

### P638:K1

- Candidates: 22
- Comparable targets: 897 of 1933
- Coverage-excluded/missing targets: 1036
- Coverage exclusion reasons: `{"EXCLUDED_INSUFFICIENT_HISTORY": 500, "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE": 721}`
- SHORT: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=102000067; last=115000061; switches=115; selection_frequency=`{"power_biglotto_attention_replay_1bet": 37, "power_biglotto_cold_hunter_1bet": 62, "power_biglotto_dms_1bet": 70, "power_biglotto_dynamic_frequency_1bet": 22, "power_biglotto_gap_pressure_1bet": 12, "power_biglotto_graph_predictor_1bet": 14, "power_biglotto_moderate_rank_1bet": 178, "power_biglotto_optimized_ensemble_1bet": 54, "power_biglotto_pure_cold_1bet": 19, "power_biglotto_rebound_aware_1bet": 22, "power_biglotto_short_window_deviation_1bet": 55, "power_biglotto_zone_momentum_1bet": 56, "power_c01_recency_decay_1bet": 17, "power_c03_pair_centrality_1bet": 34, "power_c04_zone_balanced_1bet": 11, "power_c05_dispersion_match_1bet": 22, "power_c06_regime_cusum_1bet": 65, "power_c07_borda_ensemble_1bet": 97}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=106000081; last=115000061; switches=21; selection_frequency=`{"power_biglotto_attention_replay_1bet": 17, "power_biglotto_dms_1bet": 28, "power_biglotto_moderate_rank_1bet": 52, "power_biglotto_pure_cold_1bet": 6, "power_c03_pair_centrality_1bet": 18, "power_c04_zone_balanced_1bet": 144, "power_c06_regime_cusum_1bet": 68, "power_c07_borda_ensemble_1bet": 264}`
- LONG: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=113000079; last=115000061; switches=4; selection_frequency=`{"power_biglotto_moderate_rank_1bet": 72, "power_c03_pair_centrality_1bet": 33, "power_c07_borda_ensemble_1bet": 42}`

### P638:K2

- Candidates: 21
- Comparable targets: 1833 of 1933
- Coverage-excluded/missing targets: 100
- Coverage exclusion reasons: `{"EXCLUDED_INSUFFICIENT_HISTORY": 100}`
- SHORT: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=98000053; last=115000061; switches=241; selection_frequency=`{"cold_complement_2bet": 69, "fourier30_markov30_2bet": 33, "lag_reversion_2bet": 112, "midfreq_fourier_2bet": 58, "power_apriori_2bet": 143, "power_biglotto_deviation_2bet": 61, "power_biglotto_dm_dms_2bet": 6, "power_biglotto_echo_2bet": 81, "power_biglotto_enhanced_dual_2bet": 77, "power_biglotto_gemini_v1_2bet": 53, "power_biglotto_p0_echo_2bet": 110, "power_biglotto_smart_2bet": 8, "power_biglotto_two_bet_elite_2bet": 78, "power_biglotto_two_bet_final_2bet": 4, "power_biglotto_two_bet_optimizer_2bet": 52, "power_biglotto_two_bet_optimizer_v2_2bet": 143, "power_fourier_gap_rebound_2bet": 146, "power_fourier_rhythm_2bet": 135, "power_lead_lag_2bet": 132, "power_momentum_2bet": 153, "zonal_entropy_2bet": 129}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=100000094; last=115000061; switches=69; selection_frequency=`{"cold_complement_2bet": 21, "lag_reversion_2bet": 87, "power_apriori_2bet": 104, "power_biglotto_echo_2bet": 152, "power_biglotto_p0_echo_2bet": 45, "power_biglotto_two_bet_elite_2bet": 91, "power_biglotto_two_bet_optimizer_v2_2bet": 26, "power_fourier_gap_rebound_2bet": 435, "power_fourier_rhythm_2bet": 290, "power_lead_lag_2bet": 56, "power_momentum_2bet": 70, "zonal_entropy_2bet": 156}`
- LONG: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=105000022; last=115000061; switches=34; selection_frequency=`{"power_biglotto_two_bet_optimizer_v2_2bet": 18, "power_fourier_gap_rebound_2bet": 662, "power_fourier_rhythm_2bet": 193, "power_momentum_2bet": 110, "zonal_entropy_2bet": 100}`

### P638:K3

- Candidates: 14
- Comparable targets: 1883 of 1933
- Coverage-excluded/missing targets: 50
- Coverage exclusion reasons: `{"EXCLUDED_INSUFFICIENT_HISTORY": 50}`
- SHORT: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=98000003; last=115000061; switches=196; selection_frequency=`{"fourier_rhythm_3bet": 112, "midfreq_fourier_mk_3bet": 293, "power_biglotto_asm_3bet": 100, "power_biglotto_cag_3bet": 15, "power_biglotto_diversified_ensemble_v6_3bet": 199, "power_biglotto_dms_3bet": 7, "power_biglotto_exhaustive_audit_3bet": 258, "power_biglotto_mwsc_3bet": 43, "power_biglotto_random_core_satellite_3bet": 82, "power_biglotto_random_zone_split_3bet": 179, "power_biglotto_tme_3bet": 177, "power_biglotto_zdp_3bet": 68, "power_biglotto_zone_split_3bet": 201, "power_precision_3bet": 99}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=100000044; last=115000061; switches=72; selection_frequency=`{"fourier_rhythm_3bet": 17, "midfreq_fourier_mk_3bet": 597, "power_biglotto_diversified_ensemble_v6_3bet": 87, "power_biglotto_exhaustive_audit_3bet": 120, "power_biglotto_random_zone_split_3bet": 248, "power_biglotto_tme_3bet": 14, "power_biglotto_zone_split_3bet": 279, "power_precision_3bet": 221}`
- LONG: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=104000077; last=115000061; switches=11; selection_frequency=`{"midfreq_fourier_mk_3bet": 503, "power_biglotto_exhaustive_audit_3bet": 55, "power_biglotto_random_zone_split_3bet": 184, "power_biglotto_zone_split_3bet": 385, "power_precision_3bet": 6}`

### P638:K4

- Candidates: 3
- Comparable targets: 1882 of 1933
- Coverage-excluded/missing targets: 51
- Coverage exclusion reasons: `{"EXCLUDED_INSUFFICIENT_HISTORY": 50, "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE": 1}`
- SHORT: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=98000004; last=115000061; switches=114; selection_frequency=`{"power_apriori_ext_4bet": 521, "power_biglotto_tme_optimizer_4bet": 391, "pp3_freqort_4bet": 920}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=100000045; last=115000061; switches=41; selection_frequency=`{"power_apriori_ext_4bet": 255, "power_biglotto_tme_optimizer_4bet": 65, "pp3_freqort_4bet": 1262}`
- LONG: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=104000078; last=115000061; switches=4; selection_frequency=`{"power_apriori_ext_4bet": 76, "pp3_freqort_4bet": 1056}`

### P638:K5

- Candidates: 3
- Comparable targets: 1903 of 1933
- Coverage-excluded/missing targets: 30
- Coverage exclusion reasons: `{"EXCLUDED_INSUFFICIENT_HISTORY": 30}`
- SHORT: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000081; last=115000061; switches=79; selection_frequency=`{"power_biglotto_five_me_5bet": 844, "power_biglotto_zone_balance_5bet": 48, "power_orthogonal_5bet": 961}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=100000024; last=115000061; switches=55; selection_frequency=`{"power_biglotto_five_me_5bet": 688, "power_orthogonal_5bet": 915}`
- LONG: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=104000057; last=115000061; switches=12; selection_frequency=`{"power_biglotto_five_me_5bet": 286, "power_orthogonal_5bet": 867}`

### P638:K7

- Candidates: 3
- Comparable targets: 1833 of 1933
- Coverage-excluded/missing targets: 100
- Coverage exclusion reasons: `{"EXCLUDED_INSUFFICIENT_HISTORY": 100}`
- SHORT: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=98000053; last=115000061; switches=92; selection_frequency=`{"power_biglotto_elite_7bet": 1170, "power_biglotto_gemini_phase2_7bet": 613}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=100000094; last=115000061; switches=32; selection_frequency=`{"power_biglotto_elite_7bet": 1389, "power_biglotto_gemini_phase2_7bet": 144}`
- LONG: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=105000022; last=115000061; switches=0; selection_frequency=`{"power_biglotto_elite_7bet": 1083}`

### P638:K10

- Candidates: 1
- Comparable targets: 1903 of 1933
- Coverage-excluded/missing targets: 30
- Coverage exclusion reasons: `{"EXCLUDED_INSUFFICIENT_HISTORY": 30}`
- SHORT: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000081; last=115000061; switches=0; selection_frequency=`{"power_biglotto_backtest_10bet": 1853}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=100000024; last=115000061; switches=0; selection_frequency=`{"power_biglotto_backtest_10bet": 1603}`
- LONG: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=104000057; last=115000061; switches=0; selection_frequency=`{"power_biglotto_backtest_10bet": 1153}`

### P638:K11

- Candidates: 1
- Comparable targets: 1903 of 1933
- Coverage-excluded/missing targets: 30
- Coverage exclusion reasons: `{"EXCLUDED_INSUFFICIENT_HISTORY": 30}`
- SHORT: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000081; last=115000061; switches=0; selection_frequency=`{"power_biglotto_variant_history_11bet": 1853}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=100000024; last=115000061; switches=0; selection_frequency=`{"power_biglotto_variant_history_11bet": 1603}`
- LONG: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=104000057; last=115000061; switches=0; selection_frequency=`{"power_biglotto_variant_history_11bet": 1153}`

### P638:K12

- Candidates: 1
- Comparable targets: 1903 of 1933
- Coverage-excluded/missing targets: 30
- Coverage exclusion reasons: `{"EXCLUDED_INSUFFICIENT_HISTORY": 30}`
- SHORT: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000081; last=115000061; switches=0; selection_frequency=`{"power_biglotto_core_satellite_12bet": 1853}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=100000024; last=115000061; switches=0; selection_frequency=`{"power_biglotto_core_satellite_12bet": 1603}`
- LONG: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=104000057; last=115000061; switches=0; selection_frequency=`{"power_biglotto_core_satellite_12bet": 1153}`

### P638:K25

- Candidates: 1
- Comparable targets: 1903 of 1933
- Coverage-excluded/missing targets: 30
- Coverage exclusion reasons: `{"EXCLUDED_INSUFFICIENT_HISTORY": 30}`
- SHORT: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000081; last=115000061; switches=0; selection_frequency=`{"power_biglotto_auto_optimizer_alpha_25bet": 1853}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=100000024; last=115000061; switches=0; selection_frequency=`{"power_biglotto_auto_optimizer_alpha_25bet": 1603}`
- LONG: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=104000057; last=115000061; switches=0; selection_frequency=`{"power_biglotto_auto_optimizer_alpha_25bet": 1153}`

### T539:K1

- Candidates: 25
- Comparable targets: 5730 of 5930
- Coverage-excluded/missing targets: 200
- Coverage exclusion reasons: `{"FIXED_UNIVERSE_PRE_ELIGIBILITY_MINIMUM_HISTORY": 200}`
- SHORT: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=96000251; last=115000186; switches=887; selection_frequency=`{"539_3bet_orthogonal": 354, "acb_markov_midfreq": 494, "daily539_f4cold": 482, "daily539_markov_cold": 358, "p0b_539_3bet_f_cold_fmid": 54, "t539_biglotto_attention_replay_1bet": 339, "t539_biglotto_cold_hunter_1bet": 333, "t539_biglotto_dms_1bet": 443, "t539_biglotto_dynamic_frequency_1bet": 292, "t539_biglotto_gap_pressure_1bet": 234, "t539_biglotto_graph_predictor_1bet": 270, "t539_biglotto_hot_cooccurrence_1bet": 281, "t539_biglotto_moderate_rank_1bet": 344, "t539_biglotto_optimized_ensemble_1bet": 354, "t539_biglotto_pure_cold_1bet": 193, "t539_biglotto_rebound_aware_1bet": 209, "t539_biglotto_short_window_deviation_1bet": 295, "t539_biglotto_zone_momentum_1bet": 218, "zone_gap_3bet_539": 133}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000240; last=115000186; switches=259; selection_frequency=`{"539_3bet_orthogonal": 341, "acb_markov_midfreq": 253, "daily539_f4cold": 203, "daily539_markov_cold": 73, "p0b_539_3bet_f_cold_fmid": 450, "t539_biglotto_attention_replay_1bet": 179, "t539_biglotto_cold_hunter_1bet": 562, "t539_biglotto_dms_1bet": 691, "t539_biglotto_dynamic_frequency_1bet": 146, "t539_biglotto_graph_predictor_1bet": 185, "t539_biglotto_hot_cooccurrence_1bet": 298, "t539_biglotto_moderate_rank_1bet": 123, "t539_biglotto_optimized_ensemble_1bet": 618, "t539_biglotto_pure_cold_1bet": 289, "t539_biglotto_rebound_aware_1bet": 110, "t539_biglotto_short_window_deviation_1bet": 468, "t539_biglotto_zone_momentum_1bet": 368, "zone_gap_3bet_539": 73}`
- LONG: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=99000167; last=115000186; switches=174; selection_frequency=`{"539_3bet_orthogonal": 245, "acb_markov_midfreq": 539, "daily539_f4cold": 184, "daily539_markov_cold": 40, "p0b_539_3bet_f_cold_fmid": 520, "t539_biglotto_attention_replay_1bet": 144, "t539_biglotto_cold_hunter_1bet": 585, "t539_biglotto_dms_1bet": 870, "t539_biglotto_dynamic_frequency_1bet": 89, "t539_biglotto_gap_pressure_1bet": 35, "t539_biglotto_graph_predictor_1bet": 5, "t539_biglotto_hot_cooccurrence_1bet": 296, "t539_biglotto_moderate_rank_1bet": 51, "t539_biglotto_optimized_ensemble_1bet": 479, "t539_biglotto_pure_cold_1bet": 576, "t539_biglotto_rebound_aware_1bet": 78, "t539_biglotto_short_window_deviation_1bet": 84, "t539_biglotto_zone_momentum_1bet": 109, "zone_gap_3bet_539": 51}`

### T539:K2

- Candidates: 13
- Comparable targets: 5830 of 5930
- Coverage-excluded/missing targets: 100
- Coverage exclusion reasons: `{"FIXED_UNIVERSE_PRE_ELIGIBILITY_MINIMUM_HISTORY": 100}`
- SHORT: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=96000151; last=115000186; switches=829; selection_frequency=`{"midfreq_acb_2bet": 1049, "midfreq_fourier_2bet": 342, "t539_biglotto_deviation_2bet": 519, "t539_biglotto_dm_dms_2bet": 495, "t539_biglotto_echo_2bet": 660, "t539_biglotto_enhanced_dual_2bet": 521, "t539_biglotto_gemini_v1_2bet": 295, "t539_biglotto_p0_echo_2bet": 341, "t539_biglotto_smart_2bet": 415, "t539_biglotto_two_bet_elite_2bet": 623, "t539_biglotto_two_bet_final_2bet": 152, "t539_biglotto_two_bet_optimizer_2bet": 45, "t539_biglotto_two_bet_optimizer_v2_2bet": 323}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000140; last=115000186; switches=287; selection_frequency=`{"midfreq_acb_2bet": 1304, "midfreq_fourier_2bet": 151, "t539_biglotto_deviation_2bet": 826, "t539_biglotto_dm_dms_2bet": 218, "t539_biglotto_echo_2bet": 768, "t539_biglotto_enhanced_dual_2bet": 193, "t539_biglotto_p0_echo_2bet": 203, "t539_biglotto_smart_2bet": 504, "t539_biglotto_two_bet_elite_2bet": 1128, "t539_biglotto_two_bet_optimizer_2bet": 11, "t539_biglotto_two_bet_optimizer_v2_2bet": 224}`
- LONG: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=99000067; last=115000186; switches=126; selection_frequency=`{"midfreq_acb_2bet": 1509, "midfreq_fourier_2bet": 4, "t539_biglotto_deviation_2bet": 869, "t539_biglotto_echo_2bet": 899, "t539_biglotto_enhanced_dual_2bet": 86, "t539_biglotto_p0_echo_2bet": 114, "t539_biglotto_smart_2bet": 191, "t539_biglotto_two_bet_elite_2bet": 1408}`

### T539:K3

- Candidates: 13
- Comparable targets: 5830 of 5930
- Coverage-excluded/missing targets: 100
- Coverage exclusion reasons: `{"FIXED_UNIVERSE_PRE_ELIGIBILITY_MINIMUM_HISTORY": 100}`
- SHORT: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=96000151; last=115000186; switches=889; selection_frequency=`{"acb_markov_midfreq_3bet": 906, "daily539_f4cold_3bet": 1155, "t539_biglotto_asm_3bet": 123, "t539_biglotto_cag_3bet": 121, "t539_biglotto_diversified_ensemble_v6_3bet": 488, "t539_biglotto_dms_3bet": 272, "t539_biglotto_exhaustive_audit_3bet": 717, "t539_biglotto_mwsc_3bet": 345, "t539_biglotto_random_core_satellite_3bet": 54, "t539_biglotto_random_zone_split_3bet": 647, "t539_biglotto_tme_3bet": 314, "t539_biglotto_zdp_3bet": 167, "t539_biglotto_zone_split_3bet": 471}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000140; last=115000186; switches=262; selection_frequency=`{"acb_markov_midfreq_3bet": 1126, "daily539_f4cold_3bet": 1344, "t539_biglotto_diversified_ensemble_v6_3bet": 382, "t539_biglotto_dms_3bet": 16, "t539_biglotto_exhaustive_audit_3bet": 891, "t539_biglotto_mwsc_3bet": 149, "t539_biglotto_random_zone_split_3bet": 601, "t539_biglotto_tme_3bet": 87, "t539_biglotto_zdp_3bet": 8, "t539_biglotto_zone_split_3bet": 926}`
- LONG: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=99000067; last=115000186; switches=118; selection_frequency=`{"acb_markov_midfreq_3bet": 709, "daily539_f4cold_3bet": 1991, "t539_biglotto_diversified_ensemble_v6_3bet": 142, "t539_biglotto_exhaustive_audit_3bet": 664, "t539_biglotto_random_zone_split_3bet": 441, "t539_biglotto_tme_3bet": 5, "t539_biglotto_zone_split_3bet": 1128}`

### T539:K4

- Candidates: 1
- Comparable targets: 5929 of 5930
- Coverage-excluded/missing targets: 1
- Coverage exclusion reasons: `{"FIXED_UNIVERSE_PRE_ELIGIBILITY_MINIMUM_HISTORY": 1}`
- SHORT: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=96000052; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_tme_optimizer_4bet": 5879}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000041; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_tme_optimizer_4bet": 5629}`
- LONG: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=98000229; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_tme_optimizer_4bet": 5179}`

### T539:K5

- Candidates: 3
- Comparable targets: 5830 of 5930
- Coverage-excluded/missing targets: 100
- Coverage exclusion reasons: `{"FIXED_UNIVERSE_PRE_ELIGIBILITY_MINIMUM_HISTORY": 100}`
- SHORT: conclusion=ROLLING_HISTORICALLY_EXCEEDED_PAIRED_CAUSAL_FROZEN_BASELINE; first=96000151; last=115000186; switches=193; selection_frequency=`{"daily539_f4cold_5bet": 4656, "t539_biglotto_five_me_5bet": 1124}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000140; last=115000186; switches=2; selection_frequency=`{"daily539_f4cold_5bet": 5486, "t539_biglotto_five_me_5bet": 44}`
- LONG: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=99000067; last=115000186; switches=0; selection_frequency=`{"daily539_f4cold_5bet": 5080}`

### T539:K7

- Candidates: 3
- Comparable targets: 5830 of 5930
- Coverage-excluded/missing targets: 100
- Coverage exclusion reasons: `{"FIXED_UNIVERSE_PRE_ELIGIBILITY_MINIMUM_HISTORY": 100}`
- SHORT: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=96000151; last=115000186; switches=280; selection_frequency=`{"t539_biglotto_elite_7bet": 1152, "t539_biglotto_gemini_phase2_7bet": 4620, "t539_biglotto_high_prize_trend_7bet": 8}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_UNDERPERFORMED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000140; last=115000186; switches=10; selection_frequency=`{"t539_biglotto_elite_7bet": 73, "t539_biglotto_gemini_phase2_7bet": 5457}`
- LONG: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=99000067; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_gemini_phase2_7bet": 5080}`

### T539:K10

- Candidates: 1
- Comparable targets: 5929 of 5930
- Coverage-excluded/missing targets: 1
- Coverage exclusion reasons: `{"FIXED_UNIVERSE_PRE_ELIGIBILITY_MINIMUM_HISTORY": 1}`
- SHORT: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=96000052; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_backtest_10bet": 5879}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000041; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_backtest_10bet": 5629}`
- LONG: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=98000229; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_backtest_10bet": 5179}`

### T539:K11

- Candidates: 1
- Comparable targets: 5910 of 5930
- Coverage-excluded/missing targets: 20
- Coverage exclusion reasons: `{"FIXED_UNIVERSE_PRE_ELIGIBILITY_MINIMUM_HISTORY": 20}`
- SHORT: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=96000071; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_variant_history_11bet": 5860}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000060; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_variant_history_11bet": 5610}`
- LONG: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=98000248; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_variant_history_11bet": 5160}`

### T539:K12

- Candidates: 1
- Comparable targets: 5929 of 5930
- Coverage-excluded/missing targets: 1
- Coverage exclusion reasons: `{"FIXED_UNIVERSE_PRE_ELIGIBILITY_MINIMUM_HISTORY": 1}`
- SHORT: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=96000052; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_core_satellite_12bet": 5879}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000041; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_core_satellite_12bet": 5629}`
- LONG: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=98000229; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_core_satellite_12bet": 5179}`

### T539:K25

- Candidates: 1
- Comparable targets: 5929 of 5930
- Coverage-excluded/missing targets: 1
- Coverage exclusion reasons: `{"FIXED_UNIVERSE_PRE_ELIGIBILITY_MINIMUM_HISTORY": 1}`
- SHORT: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=96000052; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_auto_optimizer_alpha_25bet": 5879}`
- MEDIUM: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=97000041; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_auto_optimizer_alpha_25bet": 5629}`
- LONG: conclusion=ROLLING_HISTORICALLY_MATCHED_PAIRED_CAUSAL_FROZEN_BASELINE; first=98000229; last=115000186; switches=0; selection_frequency=`{"t539_biglotto_auto_optimizer_alpha_25bet": 5179}`

## Scientific limitations

- Historical outperformance, equality, or underperformance does not prove future predictive advantage.
- No profitability, production-readiness, promotion, p-value, or significance claim is made.
- B649 K2 is excluded because every authority target contains at least one strategy execution failure; its strategy universe cannot be compared without changing membership.
- A window is inconclusive whenever the fixed comparable series cannot provide W prior targets plus a current evaluation target.

## Explicit boundaries

```text
PHASE12_DEPENDENCY = NONE
PHASE12_PATHS_CHANGED = NONE
P638_ZONE2 = NOT RUN
SECOND_EXCHANGE = NOT RUN
REFERENCE_PROMOTION = NOT AUTHORIZED
RUNTIME_PROMOTION = NOT AUTHORIZED
PREDICTIVE_ADVANTAGE = NOT CLAIMED
PROFITABILITY = NOT CLAIMED
```
