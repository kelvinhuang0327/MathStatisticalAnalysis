"""Closed-universe and reproducible-export tests for BIG_LOTTO research."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lottolab.domain.biglotto_full_strategy_catalog import (
    EXPECTED_FIRST_BATCH_COUNT,
    EXPECTED_TOTAL_STRATEGY_COUNT,
    FullStrategyCatalogError,
    ReplayBatchMappingStatus,
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.interfaces.cli.full_strategy_research import (
    CATALOG_CSV_FILENAME,
    CATALOG_JSON_FILENAME,
    CHECKSUM_FILENAME,
    PROGRESS_JSON_FILENAME,
    FullStrategyResearchCliError,
    export_full_strategy_research_catalog,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def test_catalog_contains_every_audited_method_with_closed_status() -> None:
    catalog = load_full_strategy_catalog()

    assert len(catalog.records) == EXPECTED_TOTAL_STRATEGY_COUNT == 221
    assert len({record.strategy_id for record in catalog.records}) == 221
    assert len({record.legacy_method_id for record in catalog.records}) == 221
    assert all(type(record.reproduction_status) is ReproductionStatus for record in catalog.records)
    assert catalog.full_universe_complete is True
    assert catalog.progress.canonical_dict() == {
        "backtested_count": 135,
        "closed_count": 74,
        "duplicate_alias_count": 12,
        "owner_decision_required_count": 0,
        "reproduced_count": 135,
        "total_strategy_count": 221,
        "uncompleted_count": 0,
    }


def test_catalog_preserves_frozen_source_and_unreproduced_semantics() -> None:
    catalog = load_full_strategy_catalog()

    assert catalog.frozen_source_commit == "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
    assert all(record.source_commit == catalog.frozen_source_commit for record in catalog.records)
    assert all(len(record.source_sha256) == 64 for record in catalog.records)
    pending = tuple(
        record
        for record in catalog.records
        if record.reproduction_status is ReproductionStatus.OWNER_DECISION_REQUIRED
    )
    assert len(pending) == 0
    assert all(record.native_ticket_semantics == "NOT_YET_REPRODUCED" for record in pending)
    assert all(record.ticket_order_semantics == "NOT_YET_REPRODUCED" for record in pending)
    assert all(record.ticket_duplicate_semantics == "NOT_YET_REPRODUCED" for record in pending)
    assert all(record.candidate_k_semantics == "NOT_YET_REPRODUCED" for record in pending)
    assert all(record.combination_count_semantics == "NOT_YET_REPRODUCED" for record in pending)
    backtested = tuple(
        record
        for record in catalog.records
        if record.reproduction_status is ReproductionStatus.BACKTESTED
    )
    assert len(backtested) == 135
    assert {record.native_ticket_semantics for record in backtested} == {
        "EXACT_REPLAY_BACKED_SOURCE_NATIVE_3_TICKETS",
        "EXACT_REPLAY_BACKED_SOURCE_NATIVE_4_TICKETS",
        "FROZEN_FACTORY_RANDOM_NATIVE_3_TICKETS_WITH_VERSIONED_SEED",
        "FROZEN_HISTORY_NATIVE_SOURCE_1_TICKETS",
        "FROZEN_HISTORY_NATIVE_SOURCE_2_TICKETS",
        "FROZEN_HISTORY_NATIVE_SOURCE_3_TICKETS",
        "FROZEN_HISTORY_NATIVE_SOURCE_8_TICKETS",
        "FROZEN_HISTORY_NATIVE_SOURCE_EXACTLY_2",
        "FROZEN_HISTORY_NATIVE_SOURCE_EXACTLY_6",
        "FROZEN_HISTORY_NATIVE_SOURCE_EXACTLY_8_DIVERSITY_ORDERED_TICKETS",
        "FROZEN_HISTORY_NATIVE_SOURCE_BASE_4_THEN_ENHANCED_UP_TO_4_SOURCE_ORDER_TICKETS",
        "FROZEN_HISTORY_NATIVE_SOURCE_FIVE_SOURCE_CONFIGURATIONS_FLATTENED_TO_8_POSITIONAL_TICKETS",
        "FROZEN_HISTORY_NATIVE_SOURCE_FOUR_DOCUMENTED_HISTORY_MODES_X_3_SOURCE_ORDER_TICKETS",
        "FROZEN_HISTORY_NATIVE_SOURCE_HOT_ECHO_THEN_DISJOINT_COLD_ECHO_2_TICKETS",
        "FROZEN_HISTORY_NATIVE_SOURCE_SINGLE_MODE_1_THEN_TWO_BET_MODE_2_SOURCE_ORDER_TICKETS",
        "FROZEN_HISTORY_NATIVE_SOURCE_SOURCE_ORDER_UP_TO_4_UNIQUE",
        "FROZEN_SOURCE_NATIVE_EIGHT_SOURCE_PARAMETER_GRID_CONFIGURATIONS_IN_DECLARATION_ORDER",
        "FROZEN_SOURCE_NATIVE_GENERATE_RANDOM_5_BETS_SOURCE_CALL_ORDER",
        "FROZEN_SOURCE_NATIVE_PHASE2_2BET_THEN_PHASE2_3BET_SOURCE_ORDER_5_POSITIONAL_TICKETS",
        "FROZEN_SOURCE_NATIVE_RANDOM_BASELINE_3_BETS_SOURCE_CALL_ORDER",
        "FROZEN_SOURCE_NATIVE_DEFAULT_6_CLUSTER_TICKETS_THEN_1_SKEW_DEFENSE_TICKET",
        "FROZEN_SOURCE_NATIVE_SOURCE_CONFIGURATIONS_1_2_3_7_FLATTENED_TO_13_POSITIONAL_TICKETS",
        "FROZEN_SOURCE_NATIVE_UP_TO_6_CLUSTER_CENTER_TICKETS_IN_SOURCE_LOOP_ORDER",
        "FROZEN_SOURCE_NATIVE_UP_TO_7_CLUSTER_CENTER_TICKETS_IN_SOURCE_LOOP_ORDER",
        "FROZEN_SOURCE_NATIVE_UP_TO_7_DISTINCT_ANTECEDENT_RULE_TICKETS_IN_SOURCE_ORDER",
        "FROZEN_SOURCE_NATIVE_7_METHOD_TICKETS_IN_FROZEN_GENERATE_7_BETS_ORDER",
        "FROZEN_SOURCE_NATIVE_1_TICKET_FROM_BEST_OF_5_FROZEN_FREQUENCY_WINDOWS",
        "FROZEN_SOURCE_NATIVE_1_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_8_SOURCE_CONFIGURATIONS_FLATTENED_IN_DECLARATION_AND_BET_ORDER",
        "FROZEN_SOURCE_NATIVE_1_COMPLEMENT_TICKET_FOR_2_FROZEN_PURCHASED_TICKETS",
        "FROZEN_SOURCE_NATIVE_7_SOURCE_CONFIGURATIONS_FLATTENED_IN_DECLARATION_AND_BET_ORDER",
        "FROZEN_SOURCE_NATIVE_9_SOURCE_CONFIGURATIONS_FLATTENED_IN_DECLARATION_AND_BET_ORDER",
        "FROZEN_SOURCE_NATIVE_4_SOURCE_CONFIGURATIONS_AT_DEFAULT_SEED_42_FLATTENED_TO_10_POSITIONS",
        "FROZEN_SOURCE_NATIVE_26_BIG_LOTTO_SOURCE_STRATEGY_CONFIGURATIONS_FLATTENED_TO_65_POSITIONAL_TICKETS_WITH_REPEATS",
        "FROZEN_SOURCE_NATIVE_TOP6_CONFIGURATION_AS_ONE_LEGAL_TICKET_WITH_TOP10_AND_TOP15_RETAINED_AS_CANDIDATE_POOLS",
        "FROZEN_SOURCE_NATIVE_180_FROZEN_GRID_CONFIGURATIONS_X_2_POSITIONAL_TICKETS_FLATTENED_TO_360_WITH_REPEATS",
        "FROZEN_SOURCE_NATIVE_ONE_PAGERANK_TOP15_GREEDY_CLIQUE_TICKET",
        "FROZEN_SOURCE_NATIVE_SEVEN_BIG_LOTTO_LAMBDA_CONFIGURATIONS_FLATTENED_IN_SOURCE_ORDER",
        "FROZEN_SOURCE_NATIVE_ONE_FIXED_15_DRAW_RECENCY_WEIGHTED_FREQUENCY_TICKET",
        "FROZEN_SOURCE_NATIVE_ONE_TOP20_HOT_POOL_WITH_NORMALIZED_100_DRAW_COOCCURRENCE_TICKET",
        "FROZEN_SOURCE_NATIVE_SEVEN_NORMATIVE_DIVERSE_SMART_RANDOM_TICKETS_EV_SORTED",
        "FROZEN_SOURCE_NATIVE_SIX_COMPLEMENTARY_POOL_STRATEGY_TICKETS_IN_DECLARATION_ORDER",
        "FROZEN_SOURCE_NATIVE_FIVE_POSITIONAL_ZONE_BALANCE_OUTPUTS_MAIN_500_THEN_COMPARISON_100_200_300_500_INCLUDING_REPEATED_500",
        "FROZEN_SOURCE_NATIVE_TWO_POSITIONAL_POST_SELECTION_TICKETS_FREQUENCY_50_DANGER_FILTER_THEN_ZONE_BALANCE_500_OR_510",
        "FROZEN_SOURCE_NATIVE_TWO_POSITIONAL_SMART_TICKETS_TRUE_FREQUENCY_50_CONSERVATIVE_THEN_FULL_HISTORY_DEVIATION_AGGRESSIVE",
        "FROZEN_SOURCE_NATIVE_FIVE_POSITIONAL_UNIFIED_ENGINE_TICKETS_STATISTICAL_DEVIATION_MARKOV_HOT_COLD_THEN_TREND",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_UNIFIED_ENGINE_TICKETS_STATISTICAL_DEVIATION_THEN_MARKOV",
        "FROZEN_SOURCE_NATIVE_TWO_POSITIONAL_TICKETS_FROM_TOP15_WEIGHTED_POOL_WITH_SECOND_TICKET_LARGE_NUMBER_PRIORITY",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_OVERLAPPING_SLICES_0_6_4_10_8_14_FROM_TOP18",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_ANCHOR_SECONDARY_INDEX_MAPPINGS_FROM_BASE_TOP18",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_OVERLAPPING_SLICES_FROM_CORRELATION_BOOSTED_TOP18",
        "FROZEN_SOURCE_NATIVE_FOUR_POSITIONAL_OVERLAPPING_SLICES_0_6_4_10_8_14_12_18_FROM_CORRELATION_BOOSTED_TOP18",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_OVERLAPPING_SLICES_FROM_FIFTY_SAMPLE_ELITE_CONSENSUS_TOP18",
        "FROZEN_SOURCE_NATIVE_FOUR_POSITIONAL_INDEPENDENT_UNIFIED_TICKETS_STATISTICAL_DEVIATION_MARKOV_THEN_HOT_COLD",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_TOP3_ANCHOR_COOCCURRENCE_GROUP_TICKETS_FROM_BASE_TOP18",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_ROUND_ROBIN_DISJOINT_COOCCURRENCE_CLUSTER_TICKETS_FROM_BASE_TOP18",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_LOW_MID_HIGH_HEAVY_ZONE_TICKETS_FROM_WEIGHTED_TOP30_POOL",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_SCORE_SORTED_CONSTRAINED_TOP20_COMBINATIONS",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_RECENT_AUDIT_SELECTED_UNIFIED_METHOD_TICKETS",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_DIVERSITY_GREEDY_TOP18_COMBINATIONS",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_SLICES_FROM_MULTI_WINDOW_CONSENSUS_TOP18",
        "FROZEN_SOURCE_NATIVE_UP_TO_THREE_POSITIONAL_PAIRWISE_CONSENSUS_GREEDY_TICKETS",
        "FROZEN_SOURCE_NATIVE_TWO_POSITIONAL_TOP12_WEIGHTED_CANDIDATE_SLICES_0_6_AND_3_9",
        "FROZEN_SOURCE_NATIVE_TWO_POSITIONAL_TOP18_WEIGHTED_CANDIDATE_SLICES_0_6_AND_4_10",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_TOP18_WEIGHTED_CANDIDATE_SLICES_0_6_4_10_8_14",
        "FROZEN_SOURCE_NATIVE_TWO_POSITIONAL_DISJOINT_SLICES_0_6_AND_6_12_FROM_WEIGHTED_TOP20",
        "FROZEN_SOURCE_NATIVE_UP_TO_SEVEN_POSITIONAL_OVERLAPPING_SLICES_FROM_WEIGHTED_TOP30",
        "FROZEN_SOURCE_NATIVE_SIX_POSITIONAL_WINDOWED_UNIFIED_TICKETS_THEN_ONE_CONSENSUS_TICKET",
        "FROZEN_SOURCE_NATIVE_SIX_RECENT_WINDOW_UNIFIED_TICKETS_THEN_ONE_UNWEIGHTED_CONSENSUS_TICKET",
        "FROZEN_SOURCE_NATIVE_SEVEN_UNIFIED_METHOD_TICKETS_THEN_THREE_SCALAR_EWMA_TREND_VARIANTS",
        "FROZEN_SOURCE_NATIVE_ONE_GAP_01_19_WEIGHTED_TICKET_WITH_LOW_SUM_SHIFT",
        "FROZEN_SOURCE_NATIVE_TWO_POSITIONAL_GAP_TICKETS_EXCLUDING_01_19_THEN_20_29",
        "FROZEN_SOURCE_NATIVE_ELEVEN_POSITIONAL_UNIFIED_PREDICTOR_WINDOW_VARIANTS",
        "FROZEN_SOURCE_NATIVE_SIX_BENCHMARK_CONFIGURATIONS_FLATTENED_TO_EIGHT_POSITIONAL_TICKETS",
        "FROZEN_SOURCE_NATIVE_TWENTY_FIVE_POSITIONAL_UNIFIED_PREDICTOR_WINDOW_CONFIGURATIONS",
        "FROZEN_SOURCE_NATIVE_THREE_CLUSTER_PIVOT_CORE_TICKETS_THEN_NONDUPLICATE_TOP_HYBRID_TICKET_THEN_AT_MOST_ONE_NONDUPLICATE_WINDOW50_FILL_TICKET_TRUNCATED_TO_FOUR",
        "FROZEN_SOURCE_NATIVE_GRAPH_CENTRALITY_TICKET_THEN_UNIFIED_DEVIATION_BASELINE_TICKET",
        "FROZEN_SOURCE_NATIVE_ONE_FROZEN_CHECKPOINT_TRANSFORMER_TOP6_TICKET",
        "FROZEN_SOURCE_NATIVE_ONE_FROZEN_CHECKPOINT_TRANSFORMER_TOP6_ZONE_CAPPED_TICKET",
        "FROZEN_SOURCE_NATIVE_ONE_FROZEN_CHECKPOINT_U_HPE_V3_TOP6_ZONE_CAPPED_TICKET",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_EXPERT_TICKETS_STRUCTURAL_AI_HPSB_DMS_THEN_HYBRID_BALANCE",
        "FROZEN_SOURCE_NATIVE_SIX_POSITIONAL_EXPERT_TICKETS_STRUCTURAL_AI_HPSB_DMS_COOCCURRENCE_GRAPH_HYBRID_BALANCE_GAP_RECOVERY_THEN_TAIL",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_TICKETS_FOURIER_RANK_BLOCKS_THEN_LAG2_ECHO_PLUS_COLD",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_TICKETS_FOURIER_COLD_THEN_TAIL_BALANCE",
        "FROZEN_SOURCE_NATIVE_SIX_POSITIONAL_TICKETS_TS3_POSITIONS_1_TO_3_THEN_FCF_POSITIONS_4_TO_6",
        "FROZEN_SOURCE_NATIVE_FOUR_POSITIONAL_TICKETS_MARKOV_POSITIONS_1_TO_2_THEN_TRIPLE_STRIKE_POSITIONS_3_TO_4",
        "FROZEN_SOURCE_NATIVE_3_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_2_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_4_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_5_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_6_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_10_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_11_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_14_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_17_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_24_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_27_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_39_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_40_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_42_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_54_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_12_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER",
        "FROZEN_SOURCE_NATIVE_ONE_POSITIONAL_HPSB_V2_DYNAMIC_METHOD_SELECTION_TICKET",
        "FROZEN_SOURCE_NATIVE_TWO_POSITIONAL_TICKETS_ZONE_BALANCE_W500_THEN_BAYESIAN_W300_WITH_NEGATIVE_EXCLUSION",
        "FROZEN_SOURCE_NATIVE_THREE_POSITIONAL_TICKETS_CONSENSUS_GRAPH_SYNERGY_THEN_TAIL_DISRUPTOR",
        "FROZEN_SOURCE_NATIVE_TWELVE_POSITIONAL_TICKETS_FOUR_LOCAL_HYBRID_STRATEGIES_X_THREE_BETS_IN_DECLARATION_ORDER",
        "FROZEN_SOURCE_NATIVE_THIRTY_FIVE_POSITIONAL_TICKETS_SEVEN_ORTHOGONAL_STRATEGIES_X_TWO_THEN_THREE_BETS_IN_DECLARATION_ORDER",
        "FROZEN_SOURCE_NATIVE_EIGHTEEN_POSITIONAL_TICKETS_SIX_ZONE_VARIANTS_X_THREE_BETS_IN_DECLARATION_ORDER",
        "FROZEN_SOURCE_NATIVE_SOURCE_MAIN_CALL_ORDER_5ME_P150_4P1_P150_5ME_P200_4P1_P200_DENSE_P200_WITH_15_OR_25_POSITIONAL_TICKETS",
        "FROZEN_SOURCE_NATIVE_SOURCE_DEFAULT_SEED42_THREE_POSITIONAL_TICKETS_CONSENSUS_PRIME_GNN_STRUCTURAL_FLUX_THEN_ENTROPY_OUTLIER",
        "FROZEN_SOURCE_NATIVE_SOURCE_MAIN_DIVERSIFIED_H150_THEN_H500_THREE_BET_BLOCKS_FLATTENED_TO_3_OR_6_POSITIONAL_TICKETS",
        "FROZEN_SOURCE_NATIVE_SOURCE_BIG_LOTTO_NUM_BETS_2_THEN_3_EACH_FIVE_LOCAL_METHODS_IN_DECLARATION_ORDER_FLATTENED_TO_25_POSITIONAL_TICKETS",
        "FROZEN_SOURCE_NATIVE_ONE_TOP6_TICKET_FROM_49_MULTI_OUTPUT_BINARY_XGBOOST_PROBABILITIES",
        "FROZEN_SOURCE_REPORT_1_LEADERBOARD_NUMBERS_WITH_ONE_TO_TEN_NATIVE_TICKET_POSITIONS",
    }
    random_native = tuple(
        record
        for record in backtested
        if record.native_ticket_semantics
        == "FROZEN_FACTORY_RANDOM_NATIVE_3_TICKETS_WITH_VERSIONED_SEED"
    )
    assert {record.source_path for record in random_native} == {
        "lottery_api/models/core_satellite.py",
        "lottery_api/models/zone_split.py",
    }
    assert all(
        record.ticket_order_semantics == "FROZEN_FACTORY_BET_ORDER_BEFORE_ORDERED_20_CONSTRUCTION"
        for record in random_native
    )
    assert all(
        record.ticket_duplicate_semantics == "PRESERVE_NATIVE_POSITIONAL_DUPLICATES"
        for record in random_native
    )
    assert {evidence_role for _, _, evidence_role in catalog.source_artifacts} >= {
        "HISTORY_NATIVE_BATCH_CAUSAL_BACKTEST",
        "HISTORY_NATIVE_WAVE2_BATCH_CAUSAL_BACKTEST",
        "HISTORY_NATIVE_WAVE3_BATCH_CAUSAL_BACKTEST",
        "HISTORY_NATIVE_WAVE5_BATCH_CAUSAL_BACKTEST",
        "RANDOM_NATIVE_BATCH_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE6_BATCH_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE7_BATCH_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE8_BATCH_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE9_BATCH_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE11_BATCH_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE12_BATCH_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE17_TARGET_STABLE_RANDOM_AND_SMART_MULTI_CAUSAL_BACKTEST",
        "STATIC_DISPOSITION_WAVE18_IMPORTED_PREDICTOR_AUDIT_AND_FUNCTION_AST_ALIAS_REVIEW",
        "STATIC_DISPOSITION_WAVE19_NON_BIGLOTTO_AND_IMPORTED_PREDICTOR_HARNESS_REVIEW",
        "STATIC_CLOSED_DISPOSITION_REVIEW",
        "STATIC_DISPOSITION_WAVE4_REVIEW",
        "STATIC_DISPOSITION_WAVE10_HTTP_RESPONSE_REVIEW",
        "STATIC_DISPOSITION_WAVE13_EXCLUSION_POOL_REVIEW",
        "SOURCE_NATIVE_WAVE14_CAUSAL_BACKTEST_AND_SPECIAL_POSITION_DISPOSITION",
        "SOURCE_NATIVE_WAVE15_ATTENTION_FIXED_RECENCY_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE16_HOT_COOCCURRENCE_CAUSAL_BACKTEST_AND_EXISTING_PORTFOLIO_AUDIT_DISPOSITIONS",
        "SOURCE_NATIVE_WAVE20_ZONE_BALANCE_WINDOWS_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE21_POST_SELECTION_FILTER_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE22_SMART_TWO_BET_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE23_5ME_TME_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE24_WEIGHTED_CANDIDATE_POOL_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE25_TME_COOCCURRENCE_ZONAL_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE26_CONSTRAINT_DYNAMIC_CONSENSUS_CAUSAL_BACKTEST_AND_UNSEEDED_RNG_DISPOSITION",
        "SOURCE_NATIVE_WAVE27_WEIGHTED_TWO_AND_THREE_BET_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE28_WEIGHTED_AND_ELITE7_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE29_ROLLING_ELITE7_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE30_TEN_BET_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE31_RADICAL_GAP_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE32_VARIANT_WINDOWS_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE33_FEASIBILITY_CONFIGS_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE34_AUTO_OPTIMIZER_GRID_CAUSAL_BACKTEST",
        "STATIC_DISPOSITION_WAVE35_FROZEN_MODEL_CHECKPOINT_COMPATIBILITY_REVIEW",
        "STATIC_DISPOSITION_WAVE36_UNBOUND_NEURAL_TRAINING_RANDOMNESS_REVIEW",
        "STATIC_DISPOSITION_WAVE37_UNBOUND_TICKET_GENERATION_RANDOMNESS_REVIEW",
        "STATIC_DISPOSITION_WAVE38_UNBOUND_STOCHASTIC_NATIVE_SELECTION_REVIEW",
        "STATIC_DISPOSITION_WAVE39_DIRECT_AND_TRANSITIVE_STOCHASTIC_NATIVE_SELECTION_REVIEW",
        "SOURCE_NATIVE_WAVE40_CLUSTER_3_PLUS_1_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE41_GRAPH_CENTRALITY_CAUSAL_BACKTEST",
        "STATIC_DISPOSITION_WAVE42_ADVANCED_STRATEGIES_PASS_THROUGH_ALIAS_REVIEW",
        "STATIC_DISPOSITION_WAVE43_CANDIDATE_ONLY_NO_LEGAL_TICKET_REVIEW",
        "SOURCE_NATIVE_WAVE44_FROZEN_CHECKPOINT_PARTIAL_COVERAGE_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE45_FFT_CAUSAL_BACKTEST_AND_TRIPLE_STRIKE_ALIAS_PROOF",
        "SOURCE_NATIVE_WAVE46_CONFIGURATION_GRID_CAUSAL_BACKTEST_AND_PREDICTABILITY_PORTFOLIO_ALIAS_PROOF",
        "SOURCE_NATIVE_WAVE47_FULL_PREFIX_CAUSAL_BACKTEST_AND_STABILITY_PORTFOLIO_ALIAS_PROOF",
        "SOURCE_NATIVE_WAVE48_ENHANCEMENT_AND_DIRECTION_GRID_CAUSAL_BACKTEST_AND_STANDARD_TS3_ALIAS_PROOF",
        "SOURCE_NATIVE_WAVE49_AUTO_DISCOVERY_SIGNAL_GRID_AND_FOURIER_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE50_COVERING_AND_EXHAUSTIVE_FEATURE_SWEEP_CAUSAL_BACKTEST",
        "SOURCE_NATIVE_WAVE51_CLUSTER_AND_DEVIATION_EXTREME_SEEDED_CAUSAL_BACKTEST",
        "STATIC_DISPOSITION_WAVE56_DIRECT_AND_TRANSITIVE_STOCHASTIC_NATIVE_SELECTION_REVIEW",
        "SOURCE_NATIVE_WAVE57_HPSB_V2_FULL_PREFIX_CAUSAL_BACKTEST_AND_ENSEMBLE_EXACT_ALIAS_PROOF",
        "SOURCE_NATIVE_WAVE58_ENHANCED_DUAL_AND_SEEDED_V6_FULL_PREFIX_CAUSAL_BACKTEST_PROOF",
        "STATIC_DISPOSITION_WAVE59_RETROSPECTIVE_SEARCH_NO_TARGET_PORTFOLIO_APPLICATION_REVIEW",
        "SOURCE_NATIVE_WAVE60_HYBRID_ORTHOGONAL_AND_ZONE_SEEDED_BENCHMARK_FULL_PREFIX_CAUSAL_BACKTEST_PROOF",
        "SOURCE_NATIVE_WAVE61_FIVE_BET_CLOSED_RESULT_HORIZON_CAUSAL_BACKTEST_AND_INVALID_OUTPUT_CLOSURE_PROOF",
        "SOURCE_NATIVE_WAVE62_DIVERSIFIED_ENSEMBLE_AND_HORIZON_WRAPPER_CAUSAL_BACKTEST_PROOF",
        "SOURCE_NATIVE_WAVE63_ADVANCED_LOCAL_METHODS_TARGET_STABLE_CAUSAL_BACKTEST_PROOF",
        "SOURCE_NATIVE_WAVE65_EVOLUTION_ENGINE_FULL_PREFIX_CAUSAL_BACKTEST_PROOF",
    }
    closed = tuple(
        record
        for record in catalog.records
        if record.reproduction_status is ReproductionStatus.CLOSED_UNEXECUTABLE
    )
    assert {record.legacy_method_id for record in closed} == {
        "lottery_api/models/autogluon_model.py",
        "lottery_api/models/advanced_bayesian_analyzer.py",
        "lottery_api/models/bayesian_ensemble.py",
        "lottery_api/models/big_lotto_optimizer.py",
        "lottery_api/models/p47_wave4_powerlotto_adapters.py",
        "lottery_api/engine/predraw_ledger.py",
        "ai_lab/automl_biglotto/report.py",
        "analysis/p540a_full_replay_regeneration_readiness.py",
        "analysis/p540b_daily539_incremental_replay_generation.py",
        "analyze_proximity_115000019.py",
        "null_hypothesis_115000019.py",
        "tools/analyze_draw_115000019.py",
        "tools/eval_traits_115000021.py",
        "tools/predict_superlotto_best.py",
        "ai_lab/scripts/train_critic.py",
        "tools/analyze_biglotto_special.py",
        "tools/arbitrage_analysis.py",
        "tools/generate_realistic_data.py",
        "tools/negative_selector.py",
        "tools/negative_selector_optimized.py",
        "tools/advanced_prediction_engine.py",
        "tools/analyze_theoretical_vs_actual.py",
        "lottery_api/tools/backtest_6_bets.py",
        "lottery_api/tools/backtest_8_bets_2025.py",
        "lottery_api/tools/backtest_8_bets_2025_v2.py",
        "lottery_api/tools/rolling_backtest_2025.py",
        "tools/backtest_must_not_hit.py",
        "tools/backtest_p1_dynamic.py",
        "tools/biglotto_special_v4.py",
        "analysis/p270b_outcome_blind_portfolio_geometry_power_audit.py",
        "tools/p282b_big649_deduplicated_portfolio_replay.py",
        "tools/audit_raw_experts.py",
        "tools/experimental/compare_models.py",
        "tools/backtest_39lotto_comprehensive.py",
        "tools/backtest_ml_comprehensive_2025_biglotto.py",
        "tools/testing/test-all-optimizations.py",
        "tools/testing/test-optimization-b.py",
        "tools/testing/test-optimization-simple.py",
        "tools/test_smh.py",
        "ai_lab/scripts/benchmark_hybrid.py",
        "ai_lab/scripts/benchmark_rl.py",
        "lottery_api/models/lstm_attention_predictor.py",
        "lottery_api/models/perball_lstm.py",
        "lottery_api/engine/multi_bet_optimizer.py",
        "tools/coverage_strategy_research.py",
        "tools/covering_research.py",
        "lottery_api/models/dynamic_ensemble_predictor.py",
        "lottery_api/models/enhanced_predictor.py",
        "lottery_api/models/mcts_portfolio_optimizer.py",
        "lottery_api/models/transformer_model.py",
        "lottery_api/models/multi_bet_optimizer.py",
        "tools/backtest/benchmark_dual_bet.py",
        "tools/benchmark_new_strategies.py",
        "tools/predict_biglotto_6bets_optimized.py",
        "tools/strategy_leaderboard.py",
        "lottery_api/models/auto_optimizer.py",
        "lottery_api/models/meta_learning.py",
        "lottery_api/models/optimized_predictor.py",
        "lottery_api/models/ultra_optimized_predictor.py",
        "tools/backtest_phase1_comparison.py",
        "tools/find_best_test_periods.py",
        "tools/generate_final_predictions.py",
        "tools/generate_v7_predictions.py",
        "tools/predict_big_lotto_115000003.py",
        "tools/predict_biglotto_7bets_optimized.py",
        "lottery_api/models/advanced_strategies.py",
        "lottery_api/models/big_lotto_dual_bet_optimizer.py",
        "lottery_api/models/selective_ensemble.py",
        "lottery_api/models/unified_predictor.py",
        "tools/auto_optimizer_v2.py",
        "tools/backtest/big_lotto_2025_tournament.py",
        "tools/predict_114000118.py",
        "tools/verify_cluster_size.py",
        "ai_lab/scripts/automl_strategy_optimizer.py",
    }
    assert {record.native_ticket_semantics for record in closed} == {
        "NO_EXECUTABLE_BIG_LOTTO_MAIN_NUMBER_TICKETS",
        "NO_EXECUTABLE_BIG_LOTTO_NATIVE_TICKETS",
        "NO_EXECUTABLE_BIG_LOTTO_NATIVE_TICKETS_DUE_FROZEN_MODEL_ARTIFACT_INCOMPATIBILITY",
        "NO_INDEPENDENT_EXECUTABLE_BIG_LOTTO_TARGET_PORTFOLIO",
        "NO_INDEPENDENT_EXECUTABLE_TARGET_DRAW_PORTFOLIO",
        "NO_SOURCE_DEFINED_LEGAL_SIX_NUMBER_TICKET",
        "NO_REPRODUCIBLE_FROZEN_NATIVE_TICKETS_BECAUSE_MODULE_GLOBAL_RANDOM_STATE_WAS_NOT_BOUND_OR_SERIALIZED",
        "NO_REPRODUCIBLE_FROZEN_NATIVE_TICKETS_BECAUSE_NEURAL_TRAINING_RANDOM_STATE_WAS_NOT_BOUND_OR_SERIALIZED",
        "NO_REPRODUCIBLE_FROZEN_NATIVE_TICKETS_BECAUSE_TICKET_GENERATION_RANDOM_STATE_WAS_NOT_BOUND_OR_SERIALIZED",
        "NO_REPRODUCIBLE_FROZEN_NATIVE_TICKETS_BECAUSE_STOCHASTIC_SELECTION_PRESTATE_WAS_NOT_BOUND_OR_SERIALIZED",
        "NO_REPRODUCIBLE_FROZEN_NATIVE_TICKETS_BECAUSE_DIRECT_OR_TRANSITIVE_STOCHASTIC_PRESTATE_WAS_NOT_BOUND_OR_SERIALIZED",
        "NO_SOURCE_DEFINED_TARGET_PORTFOLIO_AFTER_RETROSPECTIVE_CONFIGURATION_RANKING",
    }
    assert all(record.unranked_reason.startswith("CLOSED_UNEXECUTABLE:") for record in closed)


def test_first_replay_batch_is_explicitly_not_the_full_universe() -> None:
    catalog = load_full_strategy_catalog()

    assert len(catalog.first_batch_strategy_ids) == EXPECTED_FIRST_BATCH_COUNT == 11
    assert len(set(catalog.first_batch_strategy_ids)) == 11
    assert "biglotto_deviation_2bet" in catalog.first_batch_strategy_ids
    assert catalog.full_universe_complete is True
    assert catalog.progress.total_strategy_count != len(catalog.first_batch_strategy_ids)
    exact = tuple(
        mapping
        for mapping in catalog.first_batch_mappings
        if mapping.mapping_status is ReplayBatchMappingStatus.EXACT_SOURCE_SYMBOL_MATCH
    )
    unresolved = tuple(
        mapping
        for mapping in catalog.first_batch_mappings
        if mapping.mapping_status is ReplayBatchMappingStatus.OWNER_DECISION_REQUIRED
    )
    assert len(exact) == 2
    assert len(unresolved) == 9
    assert {mapping.registry_strategy_id for mapping in exact} == {
        "biglotto_triple_strike",
        "biglotto_ts3_markov_4bet_w30",
    }
    assert all(mapping.catalog_strategy_id for mapping in exact)
    assert all(mapping.catalog_strategy_id is None for mapping in unresolved)


def test_duplicate_aliases_keep_explicit_target_and_unranked_reason() -> None:
    aliases = tuple(
        record
        for record in load_full_strategy_catalog().records
        if record.reproduction_status is ReproductionStatus.DUPLICATE_ALIAS
    )

    assert len(aliases) == 12
    assert all(record.duplicate_alias_target for record in aliases)
    assert {record.unranked_reason for record in aliases} == {"DUPLICATE_ALIAS"}
    backup = next(
        record
        for record in aliases
        if record.legacy_method_id == "tools/biglotto_diversified_ensemble_v6_backup.py"
    )
    assert backup.duplicate_alias_target == (
        "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d"
    )
    assert backup.native_ticket_semantics == (
        "EXACT_FROZEN_SOURCE_BLOB_DUPLICATE_OF_CANONICAL_METHOD"
    )
    randomness_alias = next(
        record
        for record in aliases
        if record.legacy_method_id == "tools/verify_randomness_impact.py"
    )
    assert randomness_alias.duplicate_alias_target == (
        "legacy_biglotto__verify_gemini_3bet_claim__05734b9e2afe"
    )
    assert randomness_alias.native_ticket_semantics == (
        "DUPLICATE_ALIAS_NO_INDEPENDENT_NATIVE_PORTFOLIO"
    )
    pass_through_aliases = {
        record.legacy_method_id: record
        for record in aliases
        if record.legacy_method_id
        in {
            "tools/final_draw_v11.py",
            "tools/predict_v9_anomaly_cluster.py",
        }
    }
    assert set(pass_through_aliases) == {
        "tools/final_draw_v11.py",
        "tools/predict_v9_anomaly_cluster.py",
    }
    assert {record.duplicate_alias_target for record in pass_through_aliases.values()} == {
        "legacy_biglotto__advanced_strategies__91c682887cd0"
    }
    triple_alias = next(
        record
        for record in aliases
        if record.legacy_method_id == "tools/verify_biglotto_3bet_comparison.py"
    )
    assert triple_alias.duplicate_alias_target == (
        "legacy_biglotto__backtest_biglotto_triple_strike_original__4a8297a758b9"
    )
    predictability_alias = next(
        record for record in aliases if record.legacy_method_id == "tools/predictability_engine.py"
    )
    assert predictability_alias.duplicate_alias_target == (
        "legacy_biglotto__optimal_2bet_3bet_matrix__6e5aec296145"
    )
    ensemble_alias = next(
        record
        for record in aliases
        if record.legacy_method_id
        == "lottery_api/models/ensemble_predictor.py"
    )
    assert ensemble_alias.duplicate_alias_target == (
        "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8"
    )


def _parse_checksums(raw: bytes) -> dict[str, str]:
    return {
        filename: digest
        for line in raw.decode("ascii").splitlines()
        for digest, filename in (line.split("  ", maxsplit=1),)
    }


def test_export_is_deterministic_and_checksums_every_data_file(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_summary = json.loads(export_full_strategy_research_catalog(first))
    second_summary = json.loads(export_full_strategy_research_catalog(second))

    assert first_summary["output_directory"] == str(first)
    assert second_summary["output_directory"] == str(second)
    for filename in (
        CATALOG_JSON_FILENAME,
        CATALOG_CSV_FILENAME,
        PROGRESS_JSON_FILENAME,
        CHECKSUM_FILENAME,
    ):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()

    checksums = _parse_checksums((first / CHECKSUM_FILENAME).read_bytes())
    assert set(checksums) == {
        CATALOG_JSON_FILENAME,
        CATALOG_CSV_FILENAME,
        PROGRESS_JSON_FILENAME,
    }
    for filename, expected in checksums.items():
        assert hashlib.sha256((first / filename).read_bytes()).hexdigest() == expected

    progress = json.loads((first / PROGRESS_JSON_FILENAME).read_bytes())
    assert progress["full_universe_complete"] is True
    assert progress["first_batch_is_full_universe"] is False
    assert progress["first_batch_exact_mapping_count"] == 2
    assert progress["first_batch_owner_decision_required_mapping_count"] == 9
    assert progress["progress"]["total_strategy_count"] == 221
    assert progress["progress"]["uncompleted_count"] == 0
    assert "do not guarantee future prizes" in progress["research_disclaimer"]


def test_export_refuses_to_overwrite_any_existing_output(tmp_path: Path) -> None:
    export_full_strategy_research_catalog(tmp_path)
    original = (tmp_path / CATALOG_JSON_FILENAME).read_bytes()

    with pytest.raises(FullStrategyResearchCliError, match="refusing to overwrite"):
        export_full_strategy_research_catalog(tmp_path)

    assert (tmp_path / CATALOG_JSON_FILENAME).read_bytes() == original


def test_catalog_command_is_registered_and_reports_honest_progress(
    tmp_path: Path,
) -> None:
    help_result = runner.invoke(app, ["--help"])
    result = runner.invoke(
        app,
        [
            "export-biglotto-strategy-universe",
            "--output-directory",
            str(tmp_path),
        ],
    )

    assert help_result.exit_code == 0
    assert "export-biglotto-strategy-universe" in help_result.stdout
    assert result.exit_code == 0
    summary = json.loads(result.stdout)
    assert summary["total_strategy_count"] == 221
    assert summary["backtested_count"] == 135
    assert summary["closed_count"] == 74
    assert summary["uncompleted_count"] == 0


def test_unknown_full_universe_strategy_id_fails_explicitly() -> None:
    with pytest.raises(FullStrategyCatalogError, match="unknown full-universe"):
        load_full_strategy_catalog().get("missing")
