# Selector lineage diversity attribution R1

## Outcome

The two frozen lineage authorities merge to 135 canonical Strategy IDs (131 base-resolved plus 4 Wave26 supplements).
The selector contains 134 unique selected Strategy IDs; 109 are absent from that canonical lineage authority. Those experiments fail closed as LINEAGE_SOURCE_INCONSISTENT; no name-based or semantic alias inference is used.

## Frozen source identities

| Authority | Commit | Tree | SHA-256 | Bytes | Path |
|---|---|---|---|---:|---|
| base_lineage | b78eda6a2c9858413c6d1a4cb182ac1083fe9454 | 2656632e9681e075151a6687414a02a84440bfa3 | f2f7d1fd5e08083124aaeb43dfe889f96012f6020b9daafae49f6368f832bfad | 389466 | docs/research/matrix-native-results/strategy-matrix-static-lineage-redundancy-map-r1-result.json |
| rolling_decomposition | cc9bd1088a9f871618725d0910874283e0318459 | 7d05638845dc553fa20d793ceba8ce1aceff71ee | 92ffb4d5678d403322791de1e3cb133d3bdb91c9c911142f67f4f3f4ee8979c9 | 112094 | docs/research/matrix-native-results/rolling-selector-stability-decomposition-r1-result.json |
| rolling_selector | abc367bd6d8b59d01ecc4d79e56c787bbc03cd20 | bf430efd66b7ce1ac38ee04fb0052e8c55cc972c | 04df0bfdffcf4ecc05d4f2ac3f58cfa1fa301061c5f1c30e549ddc3b5b174157 | 235086 | docs/research/matrix-native-results/strategy-matrix-causal-rolling-selector-pilot-r1-result.json |
| wave26_supplement | 139b3aae0ec52ef947796ee7db68cd38a9bf9f5c | 8467da3725fb323d21fc647b7d6d02ea953a68a6 | 193b9301640e5561cb495903ce0d6710c47886b72b5f603542505a82f9218db3 | 28165 | docs/research/matrix-native-results/wave26-dynamic-binding-resolution-r1-result.json |

## Lineage merge

- Base result rows: 135
- Base resolved rows retained: 131
- Base unresolved rows replaced read-only: 4
- Wave26 supplemental rows: 4
- Combined canonical IDs: 135
- Complete 135-ID coverage: True

## Experiment counts by diversity class and historical sign

| Diversity class | POSITIVE | ZERO | NEGATIVE | INCONCLUSIVE | Total |
|---|---:|---:|---:|---:|---:|
| NO_SWITCH | 0 | 0 | 0 | 4 | 4 |
| PARAMETER_SIBLING_DIVERSITY_ONLY | 0 | 0 | 0 | 0 | 0 |
| DISTINCT_BINDING_DIVERSITY | 1 | 0 | 1 | 0 | 2 |
| MIXED_DIVERSITY | 0 | 0 | 0 | 0 | 0 |
| LINEAGE_SOURCE_INCONSISTENT | 14 | 31 | 15 | 0 | 60 |

## Per-experiment attribution

| Cell | Window | Sign | Raw switches | Class | Unique strategies | Unique bindings | Unique callables |
|---|---:|---|---:|---|---:|---:|---:|
| B649:K2 | W50 | INCONCLUSIVE | 0 | NO_SWITCH | 0 | 0 | 0 |
| B649:K2 | W300 | INCONCLUSIVE | 0 | NO_SWITCH | 0 | 0 | 0 |
| B649:K2 | W750 | INCONCLUSIVE | 0 | NO_SWITCH | 0 | 0 | 0 |
| B649:K3 | W50 | POSITIVE | 69 | DISTINCT_BINDING_DIVERSITY | 15 | 15 | 15 |
| B649:K3 | W300 | NEGATIVE | 28 | DISTINCT_BINDING_DIVERSITY | 5 | 5 | 5 |
| B649:K3 | W750 | INCONCLUSIVE | 0 | NO_SWITCH | 0 | 0 | 0 |
| P638:K1 | W50 | NEGATIVE | 115 | LINEAGE_SOURCE_INCONSISTENT | 18 | — | — |
| P638:K1 | W300 | ZERO | 21 | LINEAGE_SOURCE_INCONSISTENT | 8 | — | — |
| P638:K1 | W750 | POSITIVE | 4 | LINEAGE_SOURCE_INCONSISTENT | 3 | — | — |
| P638:K2 | W50 | NEGATIVE | 241 | LINEAGE_SOURCE_INCONSISTENT | 21 | — | — |
| P638:K2 | W300 | POSITIVE | 69 | LINEAGE_SOURCE_INCONSISTENT | 12 | — | — |
| P638:K2 | W750 | POSITIVE | 34 | LINEAGE_SOURCE_INCONSISTENT | 5 | — | — |
| P638:K3 | W50 | POSITIVE | 196 | LINEAGE_SOURCE_INCONSISTENT | 14 | — | — |
| P638:K3 | W300 | NEGATIVE | 72 | LINEAGE_SOURCE_INCONSISTENT | 8 | — | — |
| P638:K3 | W750 | POSITIVE | 11 | LINEAGE_SOURCE_INCONSISTENT | 5 | — | — |
| P638:K4 | W50 | POSITIVE | 114 | LINEAGE_SOURCE_INCONSISTENT | 3 | — | — |
| P638:K4 | W300 | NEGATIVE | 41 | LINEAGE_SOURCE_INCONSISTENT | 3 | — | — |
| P638:K4 | W750 | NEGATIVE | 4 | LINEAGE_SOURCE_INCONSISTENT | 2 | — | — |
| P638:K5 | W50 | NEGATIVE | 79 | LINEAGE_SOURCE_INCONSISTENT | 3 | — | — |
| P638:K5 | W300 | NEGATIVE | 55 | LINEAGE_SOURCE_INCONSISTENT | 2 | — | — |
| P638:K5 | W750 | NEGATIVE | 12 | LINEAGE_SOURCE_INCONSISTENT | 2 | — | — |
| P638:K7 | W50 | POSITIVE | 92 | LINEAGE_SOURCE_INCONSISTENT | 2 | — | — |
| P638:K7 | W300 | NEGATIVE | 32 | LINEAGE_SOURCE_INCONSISTENT | 2 | — | — |
| P638:K7 | W750 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| P638:K10 | W50 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| P638:K10 | W300 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| P638:K10 | W750 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| P638:K11 | W50 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| P638:K11 | W300 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| P638:K11 | W750 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| P638:K12 | W50 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| P638:K12 | W300 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| P638:K12 | W750 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| P638:K25 | W50 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| P638:K25 | W300 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| P638:K25 | W750 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K1 | W50 | NEGATIVE | 887 | LINEAGE_SOURCE_INCONSISTENT | 19 | — | — |
| T539:K1 | W300 | POSITIVE | 259 | LINEAGE_SOURCE_INCONSISTENT | 18 | — | — |
| T539:K1 | W750 | POSITIVE | 174 | LINEAGE_SOURCE_INCONSISTENT | 19 | — | — |
| T539:K2 | W50 | NEGATIVE | 829 | LINEAGE_SOURCE_INCONSISTENT | 13 | — | — |
| T539:K2 | W300 | POSITIVE | 287 | LINEAGE_SOURCE_INCONSISTENT | 11 | — | — |
| T539:K2 | W750 | POSITIVE | 126 | LINEAGE_SOURCE_INCONSISTENT | 8 | — | — |
| T539:K3 | W50 | POSITIVE | 889 | LINEAGE_SOURCE_INCONSISTENT | 13 | — | — |
| T539:K3 | W300 | NEGATIVE | 262 | LINEAGE_SOURCE_INCONSISTENT | 10 | — | — |
| T539:K3 | W750 | POSITIVE | 118 | LINEAGE_SOURCE_INCONSISTENT | 7 | — | — |
| T539:K4 | W50 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K4 | W300 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K4 | W750 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K5 | W50 | POSITIVE | 193 | LINEAGE_SOURCE_INCONSISTENT | 2 | — | — |
| T539:K5 | W300 | NEGATIVE | 2 | LINEAGE_SOURCE_INCONSISTENT | 2 | — | — |
| T539:K5 | W750 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K7 | W50 | NEGATIVE | 280 | LINEAGE_SOURCE_INCONSISTENT | 3 | — | — |
| T539:K7 | W300 | NEGATIVE | 10 | LINEAGE_SOURCE_INCONSISTENT | 2 | — | — |
| T539:K7 | W750 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K10 | W50 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K10 | W300 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K10 | W750 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K11 | W50 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K11 | W300 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K11 | W750 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K12 | W50 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K12 | W300 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K12 | W750 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K25 | W50 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K25 | W300 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |
| T539:K25 | W750 | ZERO | 0 | LINEAGE_SOURCE_INCONSISTENT | 1 | — | — |

## Required answers

1. Switching-active exact DISTINCT_BINDING_DIVERSITY: POSITIVE=1, NEGATIVE=1, ZERO=0.

2. Switching-active PARAMETER_SIBLING_DIVERSITY_ONLY: 0.

3. Five repeated-positive candidates:

| Cell | Window | Sign | Switches | Diversity class |
|---|---:|---|---:|---|
| P638:K2 | W50 | NEGATIVE | 241 | LINEAGE_SOURCE_INCONSISTENT |
| P638:K2 | W300 | POSITIVE | 69 | LINEAGE_SOURCE_INCONSISTENT |
| P638:K2 | W750 | POSITIVE | 34 | LINEAGE_SOURCE_INCONSISTENT |
| P638:K3 | W50 | POSITIVE | 196 | LINEAGE_SOURCE_INCONSISTENT |
| P638:K3 | W300 | NEGATIVE | 72 | LINEAGE_SOURCE_INCONSISTENT |
| P638:K3 | W750 | POSITIVE | 11 | LINEAGE_SOURCE_INCONSISTENT |
| T539:K1 | W50 | NEGATIVE | 887 | LINEAGE_SOURCE_INCONSISTENT |
| T539:K1 | W300 | POSITIVE | 259 | LINEAGE_SOURCE_INCONSISTENT |
| T539:K1 | W750 | POSITIVE | 174 | LINEAGE_SOURCE_INCONSISTENT |
| T539:K2 | W50 | NEGATIVE | 829 | LINEAGE_SOURCE_INCONSISTENT |
| T539:K2 | W300 | POSITIVE | 287 | LINEAGE_SOURCE_INCONSISTENT |
| T539:K2 | W750 | POSITIVE | 126 | LINEAGE_SOURCE_INCONSISTENT |
| T539:K3 | W50 | POSITIVE | 889 | LINEAGE_SOURCE_INCONSISTENT |
| T539:K3 | W300 | NEGATIVE | 262 | LINEAGE_SOURCE_INCONSISTENT |
| T539:K3 | W750 | POSITIVE | 118 | LINEAGE_SOURCE_INCONSISTENT |

4. P638 C01-C07 bridge family: NOT_ATTRIBUTABLE_FROM_FREQUENCY_ONLY: C01-C07 are seven distinct bindings in one frozen callable family, but the sealed result exposes selection frequencies and a trace hash, not transition order. Exact switches cannot be assigned to this family without inventing transitions.

| Window | Sign | Raw switches | Bridge selections | Total selections | Share |
|---|---|---:|---:|---:|---:|
| W50 | NEGATIVE | 115 | 246 | 847 | 0.290437 |
| W300 | ZERO | 21 | 494 | 597 | 0.827471 |
| W750 | POSITIVE | 4 | 75 | 147 | 0.510204 |

5. Positive historical deltas after separation: classifiable experiments containing distinct-binding diversity=True; classifiable experiments without distinct-binding diversity=False; LINEAGE_SOURCE_INCONSISTENT positives=14.

6. Wave26 involvement: 4 of 4 appear in a selector universe and 3 of 4 are selected.

| Wave26 Strategy ID | In universe | Selected | Combined class |
|---|---|---|---|
| legacy_biglotto__test_ces__78d17c530ab8 | True | True | DISTINCT_BINDING |
| legacy_biglotto__test_dms__b63442289bd5 | True | True | DISTINCT_BINDING |
| legacy_biglotto__test_greedy_optimizer__82df7f878ece | True | False | DISTINCT_BINDING |
| legacy_biglotto__test_mwsc__ba37643d6a3b | True | True | DISTINCT_BINDING |

## Interpretation and runtime boundary

The report is descriptive. Selection frequency does not expose transition order, so it cannot assign a switch count to a particular family. Missing selector-to-canonical lineage IDs are reported as source inconsistency rather than inferred.

    NEW_HISTORICAL_REPLAY = NOT RUN
    DB_ACCESS = NO
    NEW_SELECTOR = NOT IMPLEMENTED
    SEMANTIC_EQUIVALENCE = NOT CLAIMED
    PREDICTIVE_ADVANTAGE = NOT ESTABLISHED
    PROFITABILITY = NOT ESTABLISHED
