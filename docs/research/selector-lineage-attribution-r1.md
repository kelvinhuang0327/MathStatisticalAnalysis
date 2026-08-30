# Selector lineage attribution R1

## Result

This is a descriptive attribution of sealed historical selector outcomes. The source deltas are unchanged. No replay, database access, strategy execution, new selector, optimization, p-value, promotion rule, or predictive claim is part of this result.

The sealed selector artifact contains selection frequencies, total adjacent-ID switch counts, and a trace SHA-256, but not the ordered transition endpoints. A switch total is therefore resolved only when every possible pair in the selected Strategy-ID support has one uniform exact lineage class. All other switches are reported as `UNRESOLVED_LINEAGE`.

## Exact source identities

- Rolling decomposition: `cc9bd1088a9f871618725d0910874283e0318459` / tree `7d05638845dc553fa20d793ceba8ce1aceff71ee` / SHA-256 `92ffb4d5678d403322791de1e3cb133d3bdb91c9c911142f67f4f3f4ee8979c9` / `docs/research/matrix-native-results/rolling-selector-stability-decomposition-r1-result.json`
- Selector pilot supporting locator: `abc367bd6d8b59d01ecc4d79e56c787bbc03cd20` / tree `bf430efd66b7ce1ac38ee04fb0052e8c55cc972c` / SHA-256 `04df0bfdffcf4ecc05d4f2ac3f58cfa1fa301061c5f1c30e549ddc3b5b174157` / `docs/research/matrix-native-results/strategy-matrix-causal-rolling-selector-pilot-r1-result.json`
- Static lineage: `b78eda6a2c9858413c6d1a4cb182ac1083fe9454` / tree `2656632e9681e075151a6687414a02a84440bfa3` / SHA-256 `f2f7d1fd5e08083124aaeb43dfe889f96012f6020b9daafae49f6368f832bfad` / `docs/research/matrix-native-results/strategy-matrix-static-lineage-redundancy-map-r1-result.json`

## Overall transition attribution

| Experiments | Total switches | Lineage-resolved | Same binding | Same callable / different binding | Distinct binding | Unresolved | Dominant family |
|---:|---:|---:|---:|---:|---:|---:|---|
| 66 | 5605 | 28 | 0 | 0 | 28 | 5577 | UNRESOLVED_LINEAGE |

## Positive / zero / negative breakdown

| Sign | Experiments | Switching experiments | Total switches | Resolved | Same binding | Same callable / different binding | Distinct binding | Unresolved |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| POSITIVE | 15 | 15 | 2635 | 0 | 0 | 0 | 0 | 2635 |
| ZERO | 31 | 1 | 21 | 0 | 0 | 0 | 0 | 21 |
| NEGATIVE | 16 | 16 | 2949 | 28 | 0 | 0 | 28 | 2921 |
| INCONCLUSIVE | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Every lottery / K / window experiment

| Cell | Window | Sign | Source delta | Switches | Resolved | Same binding | Same callable / different binding | Distinct | Unresolved | Distinct share | Dominant family |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| B649:K2 | W50 | INCONCLUSIVE | — | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| B649:K2 | W300 | INCONCLUSIVE | — | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| B649:K2 | W750 | INCONCLUSIVE | — | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| B649:K3 | W50 | POSITIVE | 2/327 | 69 | 0 | 0 | 0 | 0 | 69 | — | UNRESOLVED_LINEAGE |
| B649:K3 | W300 | NEGATIVE | -7/404 | 28 | 28 | 0 | 0 | 28 | 0 | 1/1 | DISTINCT_BINDING |
| B649:K3 | W750 | INCONCLUSIVE | — | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K1 | W50 | NEGATIVE | -5/847 | 115 | 0 | 0 | 0 | 0 | 115 | — | UNRESOLVED_LINEAGE |
| P638:K1 | W300 | ZERO | 0/1 | 21 | 0 | 0 | 0 | 0 | 21 | — | UNRESOLVED_LINEAGE |
| P638:K1 | W750 | POSITIVE | 5/147 | 4 | 0 | 0 | 0 | 0 | 4 | — | UNRESOLVED_LINEAGE |
| P638:K2 | W50 | NEGATIVE | -9/1783 | 241 | 0 | 0 | 0 | 0 | 241 | — | UNRESOLVED_LINEAGE |
| P638:K2 | W300 | POSITIVE | 1/219 | 69 | 0 | 0 | 0 | 0 | 69 | — | UNRESOLVED_LINEAGE |
| P638:K2 | W750 | POSITIVE | 9/361 | 34 | 0 | 0 | 0 | 0 | 34 | — | UNRESOLVED_LINEAGE |
| P638:K3 | W50 | POSITIVE | 2/141 | 196 | 0 | 0 | 0 | 0 | 196 | — | UNRESOLVED_LINEAGE |
| P638:K3 | W300 | NEGATIVE | -21/1583 | 72 | 0 | 0 | 0 | 0 | 72 | — | UNRESOLVED_LINEAGE |
| P638:K3 | W750 | POSITIVE | 14/1133 | 11 | 0 | 0 | 0 | 0 | 11 | — | UNRESOLVED_LINEAGE |
| P638:K4 | W50 | POSITIVE | 17/1832 | 114 | 0 | 0 | 0 | 0 | 114 | — | UNRESOLVED_LINEAGE |
| P638:K4 | W300 | NEGATIVE | -11/1582 | 41 | 0 | 0 | 0 | 0 | 41 | — | UNRESOLVED_LINEAGE |
| P638:K4 | W750 | NEGATIVE | -1/566 | 4 | 0 | 0 | 0 | 0 | 4 | — | UNRESOLVED_LINEAGE |
| P638:K5 | W50 | NEGATIVE | -9/1853 | 79 | 0 | 0 | 0 | 0 | 79 | — | UNRESOLVED_LINEAGE |
| P638:K5 | W300 | NEGATIVE | -10/1603 | 55 | 0 | 0 | 0 | 0 | 55 | — | UNRESOLVED_LINEAGE |
| P638:K5 | W750 | NEGATIVE | -10/1153 | 12 | 0 | 0 | 0 | 0 | 12 | — | UNRESOLVED_LINEAGE |
| P638:K7 | W50 | POSITIVE | 34/1783 | 92 | 0 | 0 | 0 | 0 | 92 | — | UNRESOLVED_LINEAGE |
| P638:K7 | W300 | NEGATIVE | -11/1533 | 32 | 0 | 0 | 0 | 0 | 32 | — | UNRESOLVED_LINEAGE |
| P638:K7 | W750 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K10 | W50 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K10 | W300 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K10 | W750 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K11 | W50 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K11 | W300 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K11 | W750 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K12 | W50 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K12 | W300 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K12 | W750 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K25 | W50 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K25 | W300 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| P638:K25 | W750 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K1 | W50 | NEGATIVE | -7/1136 | 887 | 0 | 0 | 0 | 0 | 887 | — | UNRESOLVED_LINEAGE |
| T539:K1 | W300 | POSITIVE | 17/1086 | 259 | 0 | 0 | 0 | 0 | 259 | — | UNRESOLVED_LINEAGE |
| T539:K1 | W750 | POSITIVE | 3/332 | 174 | 0 | 0 | 0 | 0 | 174 | — | UNRESOLVED_LINEAGE |
| T539:K2 | W50 | NEGATIVE | -39/2890 | 829 | 0 | 0 | 0 | 0 | 829 | — | UNRESOLVED_LINEAGE |
| T539:K2 | W300 | POSITIVE | 9/790 | 287 | 0 | 0 | 0 | 0 | 287 | — | UNRESOLVED_LINEAGE |
| T539:K2 | W750 | POSITIVE | 1/5080 | 126 | 0 | 0 | 0 | 0 | 126 | — | UNRESOLVED_LINEAGE |
| T539:K3 | W50 | POSITIVE | 25/1156 | 889 | 0 | 0 | 0 | 0 | 889 | — | UNRESOLVED_LINEAGE |
| T539:K3 | W300 | NEGATIVE | -1/790 | 262 | 0 | 0 | 0 | 0 | 262 | — | UNRESOLVED_LINEAGE |
| T539:K3 | W750 | POSITIVE | 23/2540 | 118 | 0 | 0 | 0 | 0 | 118 | — | UNRESOLVED_LINEAGE |
| T539:K4 | W50 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K4 | W300 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K4 | W750 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K5 | W50 | POSITIVE | 477/5780 | 193 | 0 | 0 | 0 | 0 | 193 | — | UNRESOLVED_LINEAGE |
| T539:K5 | W300 | NEGATIVE | -2/2765 | 2 | 0 | 0 | 0 | 0 | 2 | — | UNRESOLVED_LINEAGE |
| T539:K5 | W750 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K7 | W50 | NEGATIVE | -57/2890 | 280 | 0 | 0 | 0 | 0 | 280 | — | UNRESOLVED_LINEAGE |
| T539:K7 | W300 | NEGATIVE | -1/790 | 10 | 0 | 0 | 0 | 0 | 10 | — | UNRESOLVED_LINEAGE |
| T539:K7 | W750 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K10 | W50 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K10 | W300 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K10 | W750 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K11 | W50 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K11 | W300 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K11 | W750 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K12 | W50 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K12 | W300 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K12 | W750 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K25 | W50 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K25 | W300 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |
| T539:K25 | W750 | ZERO | 0/1 | 0 | 0 | 0 | 0 | 0 | 0 | — | NO_SWITCH |

## Five repeated-positive candidate cells

| Cell | Positive windows | Total switches | Resolved | Same binding | Same callable / different binding | Distinct | Unresolved | Dominant family |
|---|---|---:|---:|---:|---:|---:|---:|---|
| P638:K2 | W300, W750 | 344 | 0 | 0 | 0 | 0 | 344 | UNRESOLVED_LINEAGE |
| P638:K3 | W50, W750 | 279 | 0 | 0 | 0 | 0 | 279 | UNRESOLVED_LINEAGE |
| T539:K1 | W300, W750 | 1320 | 0 | 0 | 0 | 0 | 1320 | UNRESOLVED_LINEAGE |
| T539:K2 | W300, W750 | 1242 | 0 | 0 | 0 | 0 | 1242 | UNRESOLVED_LINEAGE |
| T539:K3 | W50, W750 | 1269 | 0 | 0 | 0 | 0 | 1269 | UNRESOLVED_LINEAGE |

## P638 C01-C07 bridge family

All `7` C01-C07 Strategy IDs exact-join. Every sibling pair is `SAME_CALLABLE_DIFFERENT_BINDING`. Two or more sibling identities were selected in `3` of `3` P638 K1 windows, accounting for `815` selection instances. The actual sibling-transition count is unresolved because endpoints were not embedded; C-to-C switches must not be described as distinct-binding cross-method diversity.

| Window | Selected siblings | Sibling selections | All selections | Total switches | Actual sibling transitions |
|---|---|---:|---:|---:|---|
| W50 | `power_c01_recency_decay_1bet`, `power_c03_pair_centrality_1bet`, `power_c04_zone_balanced_1bet`, `power_c05_dispersion_match_1bet`, `power_c06_regime_cusum_1bet`, `power_c07_borda_ensemble_1bet` | 246 | 847 | 115 | UNRESOLVED (hash-only trace) |
| W300 | `power_c03_pair_centrality_1bet`, `power_c04_zone_balanced_1bet`, `power_c06_regime_cusum_1bet`, `power_c07_borda_ensemble_1bet` | 494 | 597 | 21 | UNRESOLVED (hash-only trace) |
| W750 | `power_c03_pair_centrality_1bet`, `power_c07_borda_ensemble_1bet` | 75 | 147 | 4 | UNRESOLVED (hash-only trace) |

## ZERO / no-switch structural capability

There are `9` cells that are ZERO with no switches in every window. `9` are structurally incapable of dynamic diversity because their candidate universe contains one Strategy ID.

| Cell | Candidate Strategy-ID count | Structural capability |
|---|---:|---|
| P638:K10 | 1 | STRUCTURALLY_INCAPABLE_SINGLE_CANDIDATE |
| P638:K11 | 1 | STRUCTURALLY_INCAPABLE_SINGLE_CANDIDATE |
| P638:K12 | 1 | STRUCTURALLY_INCAPABLE_SINGLE_CANDIDATE |
| P638:K25 | 1 | STRUCTURALLY_INCAPABLE_SINGLE_CANDIDATE |
| T539:K10 | 1 | STRUCTURALLY_INCAPABLE_SINGLE_CANDIDATE |
| T539:K11 | 1 | STRUCTURALLY_INCAPABLE_SINGLE_CANDIDATE |
| T539:K12 | 1 | STRUCTURALLY_INCAPABLE_SINGLE_CANDIDATE |
| T539:K25 | 1 | STRUCTURALLY_INCAPABLE_SINGLE_CANDIDATE |
| T539:K4 | 1 | STRUCTURALLY_INCAPABLE_SINGLE_CANDIDATE |

## Required descriptive questions

1. **Are positive experiments concentrated in transitions between DISTINCT_BINDING identities?**

   `NOT_ESTABLISHED` — No positive switch is lineage-resolved by the available sealed endpoint evidence, so concentration in DISTINCT_BINDING is not established.

2. **Do negative experiments show a different transition composition?**

   `MOSTLY_UNRESOLVED_WITH_ONE_DISTINCT_BINDING_EXPERIMENT` — Only B649:K3:W300 is fully attributable and its 28 switches are DISTINCT_BINDING; the remaining negative composition is unresolved, so a robust sign-composition contrast is not available.

3. **Among the five repeated-positive candidate cells, what lineage classes actually account for their switches?**

   `ALL_RECORDED_SWITCHES_UNRESOLVED_LINEAGE` — All 4,454 switches across the repeated-positive candidate cells remain UNRESOLVED_LINEAGE; none is attributable to same-binding, same-callable/different-binding, or distinct-binding transitions from the available endpoint evidence.

4. **Are P638 C01-C07 sibling transitions common, and are they mistaken for cross-method diversity?**

   `SIBLING_SELECTION_COMMON_TRANSITION_COUNT_INCONCLUSIVE` — Sibling identities are co-selected in every P638 K1 window, but the sealed trace has no endpoints, so transition frequency is not known. Any observed C01-C07 pair switch is SAME_CALLABLE_DIFFERENT_BINDING, not distinct-binding cross-method diversity.

5. **Are any ZERO/no-switch cells structurally incapable of dynamic diversity?**

   `YES` — All 9 of 9 cells that are ZERO with no switches in every window have a single-candidate universe and are structurally incapable of dynamic diversity. 3 additional ZERO/no-switch experiments occur in cells with multiple candidates and are not structurally incapable.

6. **Does any apparent advantage disappear when same-callable parameter switches are separated from genuinely distinct bindings?**

   `LINEAGE_SPECIFIC_ADVANTAGE_NOT_ESTABLISHED` — The source positive deltas do not disappear and remain unchanged, but none can be attributed to same-callable or distinct-binding switches from the available endpoint evidence. No lineage-specific advantage is established.

## Explicit unresolved rows

| Experiment | Sign | Switches | Missing exact IDs | Source-unresolved IDs | Reasons |
|---|---|---:|---|---|---|
| B649:K3:W50 | POSITIVE | 69 | — | `legacy_biglotto__test_ces__78d17c530ab8`, `legacy_biglotto__test_dms__b63442289bd5`, `legacy_biglotto__test_mwsc__ba37643d6a3b` | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, SOURCE_LINEAGE_UNRESOLVED, MIXED_POSSIBLE_LINEAGE_CLASSES_WITHOUT_ENDPOINTS |
| P638:K1:W50 | NEGATIVE | 115 | `power_biglotto_attention_replay_1bet`, `power_biglotto_cold_hunter_1bet`, `power_biglotto_dms_1bet`, `power_biglotto_dynamic_frequency_1bet`, `power_biglotto_gap_pressure_1bet`, `power_biglotto_graph_predictor_1bet`, `power_biglotto_moderate_rank_1bet`, `power_biglotto_optimized_ensemble_1bet`, `power_biglotto_pure_cold_1bet`, `power_biglotto_rebound_aware_1bet`, `power_biglotto_short_window_deviation_1bet`, `power_biglotto_zone_momentum_1bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, MIXED_POSSIBLE_LINEAGE_CLASSES_WITHOUT_ENDPOINTS |
| P638:K1:W300 | ZERO | 21 | `power_biglotto_attention_replay_1bet`, `power_biglotto_dms_1bet`, `power_biglotto_moderate_rank_1bet`, `power_biglotto_pure_cold_1bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, MIXED_POSSIBLE_LINEAGE_CLASSES_WITHOUT_ENDPOINTS |
| P638:K1:W750 | POSITIVE | 4 | `power_biglotto_moderate_rank_1bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, MIXED_POSSIBLE_LINEAGE_CLASSES_WITHOUT_ENDPOINTS |
| P638:K2:W50 | NEGATIVE | 241 | `cold_complement_2bet`, `fourier30_markov30_2bet`, `lag_reversion_2bet`, `midfreq_fourier_2bet`, `power_biglotto_deviation_2bet`, `power_biglotto_dm_dms_2bet`, `power_biglotto_echo_2bet`, `power_biglotto_enhanced_dual_2bet`, `power_biglotto_gemini_v1_2bet`, `power_biglotto_p0_echo_2bet`, `power_biglotto_smart_2bet`, `power_biglotto_two_bet_elite_2bet`, `power_biglotto_two_bet_final_2bet`, `power_biglotto_two_bet_optimizer_2bet`, `power_biglotto_two_bet_optimizer_v2_2bet`, `power_fourier_gap_rebound_2bet`, `power_fourier_rhythm_2bet`, `power_momentum_2bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, MIXED_POSSIBLE_LINEAGE_CLASSES_WITHOUT_ENDPOINTS |
| P638:K2:W300 | POSITIVE | 69 | `cold_complement_2bet`, `lag_reversion_2bet`, `power_biglotto_echo_2bet`, `power_biglotto_p0_echo_2bet`, `power_biglotto_two_bet_elite_2bet`, `power_biglotto_two_bet_optimizer_v2_2bet`, `power_fourier_gap_rebound_2bet`, `power_fourier_rhythm_2bet`, `power_momentum_2bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, MIXED_POSSIBLE_LINEAGE_CLASSES_WITHOUT_ENDPOINTS |
| P638:K2:W750 | POSITIVE | 34 | `power_biglotto_two_bet_optimizer_v2_2bet`, `power_fourier_gap_rebound_2bet`, `power_fourier_rhythm_2bet`, `power_momentum_2bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| P638:K3:W50 | POSITIVE | 196 | `fourier_rhythm_3bet`, `midfreq_fourier_mk_3bet`, `power_biglotto_asm_3bet`, `power_biglotto_cag_3bet`, `power_biglotto_diversified_ensemble_v6_3bet`, `power_biglotto_dms_3bet`, `power_biglotto_exhaustive_audit_3bet`, `power_biglotto_mwsc_3bet`, `power_biglotto_random_core_satellite_3bet`, `power_biglotto_random_zone_split_3bet`, `power_biglotto_tme_3bet`, `power_biglotto_zdp_3bet`, `power_biglotto_zone_split_3bet`, `power_precision_3bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| P638:K3:W300 | NEGATIVE | 72 | `fourier_rhythm_3bet`, `midfreq_fourier_mk_3bet`, `power_biglotto_diversified_ensemble_v6_3bet`, `power_biglotto_exhaustive_audit_3bet`, `power_biglotto_random_zone_split_3bet`, `power_biglotto_tme_3bet`, `power_biglotto_zone_split_3bet`, `power_precision_3bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| P638:K3:W750 | POSITIVE | 11 | `midfreq_fourier_mk_3bet`, `power_biglotto_exhaustive_audit_3bet`, `power_biglotto_random_zone_split_3bet`, `power_biglotto_zone_split_3bet`, `power_precision_3bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| P638:K4:W50 | POSITIVE | 114 | `power_apriori_ext_4bet`, `power_biglotto_tme_optimizer_4bet`, `pp3_freqort_4bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| P638:K4:W300 | NEGATIVE | 41 | `power_apriori_ext_4bet`, `power_biglotto_tme_optimizer_4bet`, `pp3_freqort_4bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| P638:K4:W750 | NEGATIVE | 4 | `power_apriori_ext_4bet`, `pp3_freqort_4bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| P638:K5:W50 | NEGATIVE | 79 | `power_biglotto_five_me_5bet`, `power_biglotto_zone_balance_5bet`, `power_orthogonal_5bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| P638:K5:W300 | NEGATIVE | 55 | `power_biglotto_five_me_5bet`, `power_orthogonal_5bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| P638:K5:W750 | NEGATIVE | 12 | `power_biglotto_five_me_5bet`, `power_orthogonal_5bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| P638:K7:W50 | POSITIVE | 92 | `power_biglotto_elite_7bet`, `power_biglotto_gemini_phase2_7bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| P638:K7:W300 | NEGATIVE | 32 | `power_biglotto_elite_7bet`, `power_biglotto_gemini_phase2_7bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K1:W50 | NEGATIVE | 887 | `539_3bet_orthogonal`, `acb_markov_midfreq`, `daily539_f4cold`, `daily539_markov_cold`, `p0b_539_3bet_f_cold_fmid`, `t539_biglotto_attention_replay_1bet`, `t539_biglotto_cold_hunter_1bet`, `t539_biglotto_dms_1bet`, `t539_biglotto_dynamic_frequency_1bet`, `t539_biglotto_gap_pressure_1bet`, `t539_biglotto_graph_predictor_1bet`, `t539_biglotto_hot_cooccurrence_1bet`, `t539_biglotto_moderate_rank_1bet`, `t539_biglotto_optimized_ensemble_1bet`, `t539_biglotto_pure_cold_1bet`, `t539_biglotto_rebound_aware_1bet`, `t539_biglotto_short_window_deviation_1bet`, `t539_biglotto_zone_momentum_1bet`, `zone_gap_3bet_539` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K1:W300 | POSITIVE | 259 | `539_3bet_orthogonal`, `acb_markov_midfreq`, `daily539_f4cold`, `daily539_markov_cold`, `p0b_539_3bet_f_cold_fmid`, `t539_biglotto_attention_replay_1bet`, `t539_biglotto_cold_hunter_1bet`, `t539_biglotto_dms_1bet`, `t539_biglotto_dynamic_frequency_1bet`, `t539_biglotto_graph_predictor_1bet`, `t539_biglotto_hot_cooccurrence_1bet`, `t539_biglotto_moderate_rank_1bet`, `t539_biglotto_optimized_ensemble_1bet`, `t539_biglotto_pure_cold_1bet`, `t539_biglotto_rebound_aware_1bet`, `t539_biglotto_short_window_deviation_1bet`, `t539_biglotto_zone_momentum_1bet`, `zone_gap_3bet_539` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K1:W750 | POSITIVE | 174 | `539_3bet_orthogonal`, `acb_markov_midfreq`, `daily539_f4cold`, `daily539_markov_cold`, `p0b_539_3bet_f_cold_fmid`, `t539_biglotto_attention_replay_1bet`, `t539_biglotto_cold_hunter_1bet`, `t539_biglotto_dms_1bet`, `t539_biglotto_dynamic_frequency_1bet`, `t539_biglotto_gap_pressure_1bet`, `t539_biglotto_graph_predictor_1bet`, `t539_biglotto_hot_cooccurrence_1bet`, `t539_biglotto_moderate_rank_1bet`, `t539_biglotto_optimized_ensemble_1bet`, `t539_biglotto_pure_cold_1bet`, `t539_biglotto_rebound_aware_1bet`, `t539_biglotto_short_window_deviation_1bet`, `t539_biglotto_zone_momentum_1bet`, `zone_gap_3bet_539` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K2:W50 | NEGATIVE | 829 | `midfreq_acb_2bet`, `midfreq_fourier_2bet`, `t539_biglotto_deviation_2bet`, `t539_biglotto_dm_dms_2bet`, `t539_biglotto_echo_2bet`, `t539_biglotto_enhanced_dual_2bet`, `t539_biglotto_gemini_v1_2bet`, `t539_biglotto_p0_echo_2bet`, `t539_biglotto_smart_2bet`, `t539_biglotto_two_bet_elite_2bet`, `t539_biglotto_two_bet_final_2bet`, `t539_biglotto_two_bet_optimizer_2bet`, `t539_biglotto_two_bet_optimizer_v2_2bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K2:W300 | POSITIVE | 287 | `midfreq_acb_2bet`, `midfreq_fourier_2bet`, `t539_biglotto_deviation_2bet`, `t539_biglotto_dm_dms_2bet`, `t539_biglotto_echo_2bet`, `t539_biglotto_enhanced_dual_2bet`, `t539_biglotto_p0_echo_2bet`, `t539_biglotto_smart_2bet`, `t539_biglotto_two_bet_elite_2bet`, `t539_biglotto_two_bet_optimizer_2bet`, `t539_biglotto_two_bet_optimizer_v2_2bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K2:W750 | POSITIVE | 126 | `midfreq_acb_2bet`, `midfreq_fourier_2bet`, `t539_biglotto_deviation_2bet`, `t539_biglotto_echo_2bet`, `t539_biglotto_enhanced_dual_2bet`, `t539_biglotto_p0_echo_2bet`, `t539_biglotto_smart_2bet`, `t539_biglotto_two_bet_elite_2bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K3:W50 | POSITIVE | 889 | `daily539_f4cold_3bet`, `t539_biglotto_asm_3bet`, `t539_biglotto_cag_3bet`, `t539_biglotto_diversified_ensemble_v6_3bet`, `t539_biglotto_dms_3bet`, `t539_biglotto_exhaustive_audit_3bet`, `t539_biglotto_mwsc_3bet`, `t539_biglotto_random_core_satellite_3bet`, `t539_biglotto_random_zone_split_3bet`, `t539_biglotto_tme_3bet`, `t539_biglotto_zdp_3bet`, `t539_biglotto_zone_split_3bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K3:W300 | NEGATIVE | 262 | `daily539_f4cold_3bet`, `t539_biglotto_diversified_ensemble_v6_3bet`, `t539_biglotto_dms_3bet`, `t539_biglotto_exhaustive_audit_3bet`, `t539_biglotto_mwsc_3bet`, `t539_biglotto_random_zone_split_3bet`, `t539_biglotto_tme_3bet`, `t539_biglotto_zdp_3bet`, `t539_biglotto_zone_split_3bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K3:W750 | POSITIVE | 118 | `daily539_f4cold_3bet`, `t539_biglotto_diversified_ensemble_v6_3bet`, `t539_biglotto_exhaustive_audit_3bet`, `t539_biglotto_random_zone_split_3bet`, `t539_biglotto_tme_3bet`, `t539_biglotto_zone_split_3bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K5:W50 | POSITIVE | 193 | `daily539_f4cold_5bet`, `t539_biglotto_five_me_5bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K5:W300 | NEGATIVE | 2 | `daily539_f4cold_5bet`, `t539_biglotto_five_me_5bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K7:W50 | NEGATIVE | 280 | `t539_biglotto_elite_7bet`, `t539_biglotto_gemini_phase2_7bet`, `t539_biglotto_high_prize_trend_7bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |
| T539:K7:W300 | NEGATIVE | 10 | `t539_biglotto_elite_7bet`, `t539_biglotto_gemini_phase2_7bet` | — | ORDERED_SELECTION_TRACE_ENDPOINTS_NOT_EMBEDDED, MISSING_EXACT_STRATEGY_ID_JOIN, NO_RESOLVABLE_PAIRWISE_LINEAGE_CLASS |

## Boundaries

- `NEW_HISTORICAL_REPLAY = NOT RUN`
- `DB_ACCESS = NO`
- `NEW_SELECTOR = NOT IMPLEMENTED`
- `PREDICTIVE_ADVANTAGE = NOT ESTABLISHED`
- No p-values, significance claim, promotion threshold, profitability claim, Phase 12 use, P638 Zone-2 use, or 2-exchange work.
