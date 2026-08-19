# B649 strategy information-source provenance consolidation

GOAL_ID: B649_TRACK_B_STRATEGY_INFORMATION_SOURCE_PROVENANCE_DISCOVERY_R1

STATUS: COMPLETE

## Scope and evidence

- Production strategies: **69**
- Adapter files: **17**
- Catalog source: `src/lottolab/strategies/catalog.py`
- Adapter aggregate SHA-256: `f7cb22626a5fcad6bbeff7a394b6e02ccdbe83dfb403ae1ec3072e986e6a1960`
- Catalog SHA-256: `b2a74d1e8b920acfa679d471f01d50527eafda5dcedd370105ab1aeb33c00ca6`
- Taxonomy rule: source/feature dimensions, model transforms, and ticket construction are separate columns. Counts are strategy-ID incidence counts and may overlap; they are not independent-source counts.
- Saturation thresholds: `HEAVILY_SATURATED >=20`, `MODERATELY_REPRESENTED 6-19`, `SPARSELY_REPRESENTED 1-5`, `ABSENT 0`.

Data quality: 69 unique catalog IDs matched 69 classifications and 17 adapter files. No duplicate strategy row exists. The referenced row-level predecessor artifacts were absent and the existing task directory was empty, so consolidation used the live catalog, adapter/module contracts, shared-helper dependency chain, and the continuation's grounded findings. No new 69-strategy replay was run.

## Main finding

The catalog is highly saturated in transformations of the same historical draw stream, not in independent predictive information. **58/69** IDs meet the deterministic “frequency/gap/deviation lineage” rule (at least half their labeled dimensions are occurrence, gap, hot/cold, deviation, Markov, trend, or zone derivatives, excluding Social Wisdom and outcome-blind random paths).

The catalog directly pins **29** IDs to `unified_predictor.py`; another **5** IDs use the same family indirectly (four Wave-8 frozen-core consumers) or as a local Gemini variant. Therefore `UNIFIED_ENGINE_STRATEGY_COUNT` is **29 direct / 34 lineage-inclusive**. Strategy IDs are not independent evidence units.

AutoDiscovery is represented correctly as `ONE_STRATEGY_ID / MULTI_SOURCE_INTERNAL_ENSEMBLE`: 30 internal scoring functions produce 54 native method/window tickets. Across the full table, **46** IDs are flagged as multi-source/internal ensembles under the explicit row-level definition.

## Saturation

- HEAVILY_SATURATED: frequency (56), gap_recency (28), hot_cold (39), deviation (38), markov_sequence (31), pair_triple_structure (35)
- MODERATELY_REPRESENTED: trend (16), zone_range (19), cooccurrence (12), symbolic_temporal (6)
- SPARSELY_REPRESENTED: historical_feedback (5), social_anti_popularity (2), other_outcome_blind_randomness (5)
- ABSENT: cross_lottery_lagged_context (0), calendar_schedule_context (0), draw_order_position (0), realized_player_popularity (0), jackpot_sales_market_state (0), equipment_ballset_regime (0)

Dominant raw/derived dimensions are frequency and its deviation/hot-cold/trend relatives, followed by Markov/structural/zone transforms. Social anti-popularity is genuinely distinct but sparse. Outcome-blind random-native paths add construction diversity, not predictive information.

## Redundancy clusters

- Unified family: 29 catalog-pinned IDs; 34 including indirect/variant consumers.
- Selected positional aliases: three Zone Split IDs, two Deviation IDs, and two P0 Hot+Echo/Cold IDs expose positions from shared producers.
- N-bet optimizer family: 2-bet, 3-bet, Gemini, CAG, Cluster-Cover, ZDP, ASM, DCB, ECP and PCE mostly alter weighting, exclusion and slicing over shared feeder methods.
- Cluster-Pivot: six- and seven-ticket IDs share one co-occurrence producer.
- Batch-15 cold-hunter family: six IDs share source hash `9e89f2b41add...` and differentiate gap/rank transforms.
- Social Wisdom is not NegativeSelection: Social Wisdom consumes a behavioral anti-popularity prior; NegativeSelection consumes frequency/hot-cold/gap/co-occurrence history.

## Transform and construction concentration

- Most common transforms: statistical_transform (28), negative_exclusion (16), weighted_method_vote (14), bayesian_transform (8), fixed_zone_geometry (4), expected_frequency_residual (4), history_identity_hash_seed (3), method_separation (3)
- Most common constructions: ranked_single_ticket (11), portfolio_optimization (8), diversification (7), position_specific_ticket_from_three_overlapping_zone_pools (3), overlapping_top_pool_two_ticket_portfolio (3), position_specific_hot_or_cold_complement_ticket (2), position_specific_hot_echo_or_disjoint_cold_ticket (2), three_overlapping_top18_slices (2)

## Technical availability

- TECHNICALLY_UNAVAILABLE / DEAD_PRODUCTION_PATH: legacy_biglotto__quick_ml_predict__8b7ba0b52e2d
- TECHNICALLY_AVAILABLE_WITH_NATIVE_CLOSURE_RISK: legacy_biglotto__auto_discovery_biglotto__06bcb164db84, legacy_biglotto__predict_biglotto_6bets_cluster__1fd9e8a7ae2a, legacy_biglotto__predict_biglotto_7bets_cluster__8f55b5d94669, legacy_biglotto__predict_biglotto_elite7__eb46a9856446, legacy_biglotto__test_ces__78d17c530ab8, legacy_biglotto__test_greedy_optimizer__82df7f878ece, legacy_biglotto__negative_selection_biglotto__98f860c52cc2, legacy_biglotto__test_asm__d39a233a4c75, legacy_biglotto__test_dcb__c3299c25ca59, legacy_biglotto__test_4bet_dcb__3c7e3e661ad8, legacy_biglotto__test_pce__9c0cf22b4217, legacy_biglotto__zone_momentum_predict__9e89f2b41add

QuickML is dead for realistic production history because the frozen pattern slice raises for every history length >=5. This task records the defect and does not fix it.

## Performance association

PERFORMANCE_ASSOCIATION: SOURCE_UNAVAILABLE

The referenced 2,148-execution hit/prize summary could not be resolved. Local source-native JSON evidence establishes execution/reproduction and closure counts but not the required hit/prize performance values. A read-only local snapshot contained 24,140 B649 replay rows across 11 legacy IDs; only `biglotto_deviation_2bet` exactly matches the current 69-ID catalog, and its 1,570 rows are not the referenced 2,148-execution population. Using that partial snapshot for source-level ranking would create an identity and coverage bias, so no best-source or causal claim is made.

SOURCES_ASSOCIATED_WITH_BEST_EXISTING_STRATEGIES: SOURCE_UNAVAILABLE

SOURCES_ASSOCIATED_WITH_HIGH_REDUNDANCY: frequency, deviation, hot_cold, markov_sequence, trend, zone_range, pair_triple_structure

## Top new information candidates

1. **Cross-lottery lagged context** — cheap, strictly laggable, and applicable to B649/T539/P638; guard against schedule-induced spurious correlation.
2. **Calendar/schedule context** — dates already exist but are not modeled as features; use a small preregistered set.
3. **Verified physical draw order/position** — currently destroyed by sorted-number canonicalization; first prove source semantics.
4. **Realized crowd popularity plus jackpot/sales state** — distinct from the static Social Wisdom prior; evaluate as payout/split-risk information, not ball causation.
5. **Equipment/ball-set regime metadata** — genuinely absent but higher-cost and leakage-prone; start with an availability audit.

These candidates are ranked for information novelty, strict pre-target availability, technical cost, temporal transferability, and cross-lottery reuse. They are hypotheses, not evidence of predictive advantage. No candidate was implemented or selected as the next official Frontier direction.

NEW_INFORMATION_SEARCH_SPACE: MEDIUM

The transformation space over historical number occurrence is crowded; the remaining information-source space is meaningful but requires careful provenance and leakage controls.

## Reproduction

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .task-data/B649_TRACK_B_STRATEGY_INFORMATION_SOURCE_PROVENANCE_DISCOVERY_R1/reproduce_analysis.py --check
```

The script validates the exact catalog set/count, adapter-file count, taxonomy membership, and byte-for-byte output determinism.
