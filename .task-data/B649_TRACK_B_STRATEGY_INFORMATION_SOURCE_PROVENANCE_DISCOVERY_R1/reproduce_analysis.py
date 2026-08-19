#!/usr/bin/env python3
"""Reproduce the B649 production-strategy information-source consolidation."""

from __future__ import annotations

import csv
import hashlib
import io
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

OUTPUT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = OUTPUT_ROOT.parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from lottolab.domain.draws import LotteryType  # noqa: E402
from lottolab.strategies.catalog import production_catalog  # noqa: E402

GOAL_ID = "B649_TRACK_B_STRATEGY_INFORMATION_SOURCE_PROVENANCE_DISCOVERY_R1"
EXPECTED_STRATEGY_COUNT = 69
EXPECTED_ADAPTER_FILE_COUNT = 17

AVAILABLE = "TECHNICALLY_AVAILABLE"
RISK = "TECHNICALLY_AVAILABLE_WITH_NATIVE_CLOSURE_RISK"
DEAD = "TECHNICALLY_UNAVAILABLE / DEAD_PRODUCTION_PATH"

SOURCE_TAXONOMY = (
    "frequency",
    "gap_recency",
    "hot_cold",
    "deviation",
    "markov_sequence",
    "trend",
    "zone_range",
    "cooccurrence",
    "pair_triple_structure",
    "historical_feedback",
    "social_anti_popularity",
    "symbolic_temporal",
    "other_outcome_blind_randomness",
)

ABSENT_SOURCE_TAXONOMY = (
    "cross_lottery_lagged_context",
    "calendar_schedule_context",
    "draw_order_position",
    "realized_player_popularity",
    "jackpot_sales_market_state",
    "equipment_ballset_regime",
)

SOURCE_FAMILY = {
    "frequency": "historical_number_occurrence",
    "gap_recency": "historical_number_occurrence_timing",
    "hot_cold": "historical_number_occurrence_rank",
    "deviation": "historical_number_occurrence_residual",
    "markov_sequence": "historical_temporal_sequence",
    "trend": "historical_number_occurrence_time_weighting",
    "zone_range": "within_draw_range_geometry_or_zone_counts",
    "cooccurrence": "historical_cross_number_relationships",
    "pair_triple_structure": "historical_within_draw_structure",
    "historical_feedback": "historical_method_hit_feedback",
    "social_anti_popularity": "social_behavior_prior",
    "symbolic_temporal": "historical_state_or_regime_sequence",
    "other_outcome_blind_randomness": "outcome_blind_randomness",
    "cross_lottery_lagged_context": "external_lottery_history",
    "calendar_schedule_context": "preknown_calendar_and_cadence",
    "draw_order_position": "raw_physical_draw_sequence",
    "realized_player_popularity": "observed_crowd_choice_proxy",
    "jackpot_sales_market_state": "preknown_market_and_rollover_state",
    "equipment_ballset_regime": "physical_draw_regime_metadata",
}

CLASSIFICATIONS: dict[str, dict[str, Any]] = {}


def add(
    strategy_ids: str | tuple[str, ...],
    *,
    sources: tuple[str, ...],
    transforms: tuple[str, ...],
    construction: tuple[str, ...],
    dependencies: tuple[str, ...],
    independent_families: tuple[str, ...],
    notes: str,
    multi_source: bool = False,
    availability: str = AVAILABLE,
) -> None:
    ids = (strategy_ids,) if isinstance(strategy_ids, str) else strategy_ids
    unknown = set(sources) - set(SOURCE_TAXONOMY)
    if unknown:
        raise AssertionError(f"unknown source categories: {sorted(unknown)}")
    for strategy_id in ids:
        if strategy_id in CLASSIFICATIONS:
            raise AssertionError(f"duplicate classification: {strategy_id}")
        CLASSIFICATIONS[strategy_id] = {
            "actual_information_sources_consumed": ";".join(sources),
            "independent_information_source_families": ";".join(
                independent_families
            ),
            "model_transformation_type": ";".join(transforms),
            "portfolio_construction_behavior": ";".join(construction),
            "shared_engine_library_dependencies": ";".join(dependencies),
            "multi_source_internal_ensemble": "YES" if multi_source else "NO",
            "technical_availability_status": availability,
            "notes_caveats": notes,
        }


add(
    "biglotto_social_wisdom_anti_popularity",
    sources=("social_anti_popularity", "frequency"),
    transforms=("fixed_social_prior", "weighted_score_blend"),
    construction=("ranked_single_ticket",),
    dependencies=("biglotto_selected._unpopular_scores", "biglotto_selected._historical_frequency"),
    independent_families=("social_behavior_prior", "historical_number_occurrence"),
    notes="Distinct anti-popularity prior (1-31 penalized; 32-49 favored) blended 65/35 with trailing-50 frequency.",
    multi_source=True,
)
add(
    (
        "biglotto_zone_split_3bet_bet1",
        "biglotto_zone_split_3bet_bet2",
        "biglotto_zone_split_3bet_bet3",
    ),
    sources=("zone_range", "other_outcome_blind_randomness"),
    transforms=("history_identity_hash_seed", "fixed_zone_geometry"),
    construction=("position_specific_ticket_from_three_overlapping_zone_pools",),
    dependencies=("biglotto_selected._zone_split_bets",),
    independent_families=("outcome_blind_structural_prior",),
    notes="Three catalog IDs expose positional outputs of one seeded zone sampler; history content supplies reproducibility, not a learned predictive feature.",
)
add(
    ("biglotto_deviation_2bet", "biglotto_deviation_2bet_bet2"),
    sources=("frequency", "deviation", "hot_cold"),
    transforms=("expected_frequency_residual", "threshold_ranking"),
    construction=("position_specific_hot_or_cold_complement_ticket",),
    dependencies=("biglotto_selected._deviation_complement_2bet",),
    independent_families=("historical_number_occurrence",),
    notes="Two IDs expose the hot and cold positions of the same trailing-window deviation calculation.",
)
add(
    ("biglotto_p0_2bet_bet1", "biglotto_p0_2bet_bet2"),
    sources=("frequency", "deviation", "hot_cold", "gap_recency"),
    transforms=("lag2_echo_boost", "expected_frequency_residual"),
    construction=("position_specific_hot_echo_or_disjoint_cold_ticket",),
    dependencies=("biglotto_selected._p0_hot_echo_2bets",),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence"),
    notes="Two IDs expose positions of one Hot+Echo / Cold pair; they are not independent source families.",
)
add(
    "legacy_biglotto__graph_predictor__cd70713a5709",
    sources=("cooccurrence", "pair_triple_structure"),
    transforms=("weighted_graph", "pagerank", "greedy_clique"),
    construction=("ranked_single_ticket",),
    dependencies=("biglotto_wave1_graph_helpers",),
    independent_families=("historical_cross_number_relationships",),
    notes="Genuinely relationship-based rather than a frequency-window alias.",
)
add(
    "legacy_biglotto__backtest_must_hit__909c91fd2fd0",
    sources=("frequency", "hot_cold"),
    transforms=("trailing50_top_rank",),
    construction=("ranked_single_ticket",),
    dependencies=("collections.Counter",),
    independent_families=("historical_number_occurrence",),
    notes="Top six most frequent numbers in the last 50 draws.",
)
add(
    "legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac",
    sources=("frequency", "historical_feedback"),
    transforms=("self_tuned_window_selection",),
    construction=("ranked_single_ticket",),
    dependencies=("biglotto_wave1_dynamic_frequency_helpers",),
    independent_families=("historical_number_occurrence", "historical_method_hit_feedback"),
    notes="Selects among five frequency windows using historical feedback; still one occurrence-count source family.",
    multi_source=True,
)
add(
    "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee",
    sources=("frequency", "hot_cold", "cooccurrence", "pair_triple_structure"),
    transforms=("hot_filter", "cooccurrence_weighting"),
    construction=("ranked_single_ticket",),
    dependencies=("biglotto_wave1_cooccurrence_helpers",),
    independent_families=("historical_number_occurrence", "historical_cross_number_relationships"),
    notes="Combines marginal hotness with pair co-occurrence rules.",
    multi_source=True,
)
add(
    "legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4",
    sources=("frequency", "hot_cold", "gap_recency", "markov_sequence"),
    transforms=("continuous_temperature", "adaptive_echo_weight"),
    construction=("five_ticket_2bet_plus_3bet_portfolio",),
    dependencies=("biglotto_wave1_echo_helpers",),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence"),
    notes="Adaptive echo variants are transformations of the same occurrence/lag history.",
    multi_source=True,
)
add(
    "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e",
    sources=("frequency", "trend"),
    transforms=("exponential_decay", "lambda_sweep"),
    construction=("one_ticket_per_lambda_seven_ticket_portfolio",),
    dependencies=("biglotto_wave2._high_prize_trend_predict",),
    independent_families=("historical_number_occurrence",),
    notes="Seven lambda settings are model variants, not seven information sources.",
)
add(
    "legacy_biglotto__core_satellite__2e82891003b3",
    sources=("frequency", "hot_cold", "deviation"),
    transforms=("four_frequency_pool_rankings",),
    construction=("core_satellite", "diversification", "twelve_ticket_portfolio"),
    dependencies=("biglotto_wave2_core_satellite_helpers",),
    independent_families=("historical_number_occurrence",),
    notes="Four pool modes share one frequency table; construction drives most catalog differentiation.",
    multi_source=True,
)
add(
    "legacy_biglotto__auto_discovery_biglotto__06bcb164db84",
    sources=(
        "frequency", "gap_recency", "hot_cold", "deviation", "markov_sequence",
        "trend", "zone_range", "cooccurrence", "pair_triple_structure", "symbolic_temporal",
    ),
    transforms=("conditional_entropy", "mutual_information", "ema", "graph_rank", "negative_exclusion", "multi_window_grid"),
    construction=("one_strategy_id", "multi_source_internal_ensemble", "fifty_four_native_tickets"),
    dependencies=("biglotto_wave2_auto_discovery_30_function_family",),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_cross_number_relationships", "historical_within_draw_structure"),
    notes="One strategy ID, 30 internal scoring functions, 54 method/window tickets; never count these as 30 production strategies.",
    multi_source=True,
    availability=RISK,
)
add(
    (
        "legacy_biglotto__biglotto_2bet_final__7eaedb330a07",
        "legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876",
    ),
    sources=("frequency", "deviation", "markov_sequence", "pair_triple_structure"),
    transforms=("statistical_transform", "weighted_method_vote"),
    construction=("overlapping_top_pool_two_ticket_portfolio", "portfolio_optimization"),
    dependencies=("unified_prediction_engine_family", "biglotto_wave3_shared_helpers"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Different pool/slice rules wrap the same deviation/Markov/statistical feeder family.",
    multi_source=True,
)
add(
    "legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3",
    sources=("frequency", "deviation", "markov_sequence", "pair_triple_structure"),
    transforms=("statistical_transform", "bayesian_transform", "weighted_method_vote"),
    construction=("overlapping_top_pool_two_ticket_portfolio", "portfolio_optimization"),
    dependencies=("unified_prediction_engine_family", "biglotto_wave3_shared_helpers"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Adds Bayesian/frequency transforms but no new raw information beyond causal number history.",
    multi_source=True,
)
add(
    "legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5",
    sources=("frequency", "deviation", "markov_sequence", "pair_triple_structure", "hot_cold", "gap_recency"),
    transforms=("statistical_transform", "weighted_method_vote", "negative_exclusion"),
    construction=("three_overlapping_top18_slices", "portfolio_optimization"),
    dependencies=("unified_prediction_engine_family", "negative_selector_family"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Base N-bet optimizer reused by later CAG/DCB/ASM/ECP wrappers.",
    multi_source=True,
)
add(
    "legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad",
    sources=("frequency", "deviation", "markov_sequence", "hot_cold", "pair_triple_structure"),
    transforms=("statistical_transform", "method_separation"),
    construction=("one_ticket_per_method_four_ticket_portfolio",),
    dependencies=("unified_prediction_engine_family",),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Four tickets expose four transforms of the same historical draw stream.",
    multi_source=True,
)
add(
    "legacy_biglotto__optimized_ensemble__e05e0fde22d7",
    sources=("frequency", "trend", "gap_recency", "symbolic_temporal"),
    transforms=("momentum", "entropy", "lag_reversion", "roi_weighted_ensemble"),
    construction=("ranked_single_ticket",),
    dependencies=("biglotto_wave4_optimized_ensemble_helpers",),
    independent_families=("historical_number_occurrence", "historical_state_or_regime_sequence"),
    notes="Distinct transform stack, but all inputs remain the same historical number stream.",
    multi_source=True,
)
add(
    "legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511",
    sources=("frequency", "deviation", "markov_sequence", "zone_range", "hot_cold", "gap_recency", "pair_triple_structure"),
    transforms=("statistical_transform", "weighted_method_vote", "negative_exclusion"),
    construction=("disjoint_top20_slices", "portfolio_optimization"),
    dependencies=("unified_prediction_engine_family", "negative_selector_family"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="A five-engine wrapper plus kill filtering; mostly shared-engine lineage.",
    multi_source=True,
)
add(
    (
        "legacy_biglotto__predict_biglotto_6bets_cluster__1fd9e8a7ae2a",
        "legacy_biglotto__predict_biglotto_7bets_cluster__8f55b5d94669",
    ),
    sources=("cooccurrence", "pair_triple_structure"),
    transforms=("cluster_pivot", "anchor_expansion"),
    construction=("multi_anchor_diversified_cluster_portfolio",),
    dependencies=("biglotto_wave5_cluster_helpers",),
    independent_families=("historical_cross_number_relationships",),
    notes="Six- and seven-ticket IDs share one Cluster-Pivot producer; ticket count is the main difference.",
    availability=RISK,
)
add(
    "legacy_biglotto__predict_biglotto_echo_2bet__59c20b25b1fa",
    sources=("frequency", "hot_cold", "gap_recency", "markov_sequence"),
    transforms=("temperature_score", "fixed_echo_weight"),
    construction=("hot_then_disjoint_cold_two_ticket_portfolio",),
    dependencies=("biglotto_wave1_echo_helpers", "biglotto_wave5_echo_wrapper"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence"),
    notes="A fixed-weight sibling of the adaptive echo family.",
    multi_source=True,
)
add(
    "legacy_biglotto__predict_biglotto_elite7__eb46a9856446",
    sources=("frequency", "deviation", "markov_sequence", "pair_triple_structure"),
    transforms=("statistical_transform", "multi_window_sweep", "consensus_ensemble"),
    construction=("six_method_window_tickets_plus_consensus",),
    dependencies=("unified_prediction_engine_family", "biglotto_wave5_wrapper"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Six Unified method/window variants plus one consensus ticket.",
    multi_source=True,
    availability=RISK,
)
add(
    "legacy_biglotto__research_variant_history__149648f9fffc",
    sources=("frequency", "deviation", "markov_sequence", "zone_range", "pair_triple_structure"),
    transforms=("statistical_transform", "multi_window_sweep"),
    construction=("eleven_method_window_variant_portfolio",),
    dependencies=("unified_prediction_engine_family", "biglotto_wave5_wrapper"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Eleven transforms/windows; no independent external information source.",
    multi_source=True,
)
add(
    "legacy_biglotto__auto_optimizer_alpha__7eaa9572e384",
    sources=("frequency", "deviation", "trend", "zone_range"),
    transforms=("bayesian_transform", "five_method_five_window_grid"),
    construction=("twenty_five_method_window_ticket_portfolio",),
    dependencies=("unified_prediction_engine_family",),
    independent_families=("historical_number_occurrence", "historical_number_occurrence_time_weighting"),
    notes="Twenty-five tickets are a method/window grid over four occurrence-derived dimensions.",
    multi_source=True,
)
add(
    "legacy_biglotto__backtest_10bet_biglotto__054e85b088be",
    sources=("frequency", "deviation", "markov_sequence", "trend", "hot_cold", "pair_triple_structure"),
    transforms=("statistical_transform", "bayesian_transform", "ewma"),
    construction=("seven_unified_tickets_plus_three_ewma_tickets",),
    dependencies=("unified_prediction_engine_family",),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Ten tickets remain transformations of the same causal draw history.",
    multi_source=True,
)
add(
    "legacy_biglotto__test_tme__f3bb5106dfe3",
    sources=("frequency", "deviation", "markov_sequence", "pair_triple_structure"),
    transforms=("statistical_transform", "method_separation"),
    construction=("three_independent_method_tickets",),
    dependencies=("unified_prediction_engine_family",),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Statistical/deviation/Markov positions from the shared engine family.",
    multi_source=True,
)
add(
    "legacy_biglotto__verify_gemini_2bet_claim__d5ca233aa776",
    sources=("frequency", "deviation", "markov_sequence", "pair_triple_structure"),
    transforms=("statistical_transform", "weighted_method_vote"),
    construction=("overlapping_top12_two_ticket_slices",),
    dependencies=("unified_prediction_engine_family",),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Another N-bet wrapper over deviation/Markov/statistical outputs.",
    multi_source=True,
)
add(
    "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    sources=("frequency", "deviation", "markov_sequence", "hot_cold", "trend", "pair_triple_structure"),
    transforms=("statistical_transform", "method_separation"),
    construction=("five_independent_method_tickets",),
    dependencies=("unified_prediction_engine_family",),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Five methods, one shared historical input family.",
    multi_source=True,
)
add(
    "legacy_biglotto__predict_big_lotto_smart_2bet__7acdaab1bd0a",
    sources=("frequency", "deviation"),
    transforms=("true_frequency_rank", "deviation_transform"),
    construction=("conservative_plus_aggressive_two_ticket_portfolio",),
    dependencies=("unified_prediction_engine_family", "biglotto_wave7_true_frequency"),
    independent_families=("historical_number_occurrence",),
    notes="Two transforms of occurrence counts, not two independent information sources.",
)
add(
    "legacy_biglotto__verify_gemini_phase2_claim__6407a8f39519",
    sources=("frequency", "gap_recency", "deviation", "markov_sequence", "trend", "hot_cold"),
    transforms=("statistical_transform", "bayesian_transform", "seven_method_variant"),
    construction=("one_ticket_per_method_seven_ticket_portfolio",),
    dependencies=("local_gemini_reimplementation_of_unified_family",),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence"),
    notes="Local claim-verifier variants mirror the Unified family without adding external information.",
    multi_source=True,
)
add(
    "legacy_biglotto__attention_replay_predictor__a811e2eb8215",
    sources=("frequency", "trend"),
    transforms=("fifteen_draw_recency_weighting",),
    construction=("ranked_single_ticket",),
    dependencies=("biglotto_wave7_attention_weights",),
    independent_families=("historical_number_occurrence",),
    notes="A recency-weighted frequency transform.",
)
add(
    "legacy_biglotto__predict_biglotto_115000002_zone_balance__8febca575f5d",
    sources=("frequency", "zone_range", "trend"),
    transforms=("dynamic_frequency_ranked_zones", "multi_window_sweep"),
    construction=("main500_plus_four_comparison_tickets",),
    dependencies=("unified_prediction_engine_family", "biglotto_wave7_zone_balance_variant"),
    independent_families=("historical_number_occurrence", "historical_within_draw_structure"),
    notes="Five windows of one dynamic zone/frequency method.",
)
add(
    "legacy_biglotto__test_ces__78d17c530ab8",
    sources=("frequency", "deviation", "markov_sequence", "hot_cold", "pair_triple_structure"),
    transforms=("statistical_transform", "weighted_method_vote", "negative_exclusion", "constraint_scoring"),
    construction=("three_low_overlap_constrained_top20_combinations", "diversification"),
    dependencies=("wave26_frozen_unified_core_indirect", "negative_selector_family"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Wave 8 adapter delegates to the Wave 26 frozen Unified authority.",
    multi_source=True,
    availability=RISK,
)
add(
    "legacy_biglotto__test_dms__b63442289bd5",
    sources=("frequency", "deviation", "markov_sequence", "trend", "zone_range", "hot_cold", "pair_triple_structure", "historical_feedback"),
    transforms=("statistical_transform", "bayesian_transform", "rolling_method_audit"),
    construction=("top_three_historically_selected_method_tickets",),
    dependencies=("wave26_frozen_unified_core_indirect",),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure", "historical_method_hit_feedback"),
    notes="Method selection is distinct feedback, but all candidate methods consume the shared causal draw stream.",
    multi_source=True,
)
add(
    "legacy_biglotto__test_greedy_optimizer__82df7f878ece",
    sources=("frequency", "deviation", "markov_sequence", "pair_triple_structure", "cooccurrence"),
    transforms=("statistical_transform", "weighted_method_vote", "negative_exclusion", "greedy_constraint_score"),
    construction=("three_diversity_greedy_top18_combinations", "diversification"),
    dependencies=("wave26_frozen_unified_core_indirect", "negative_selector_family"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure", "historical_cross_number_relationships"),
    notes="Co-occurrence influences ticket construction after a shared-engine top-18 pool.",
    multi_source=True,
    availability=RISK,
)
add(
    "legacy_biglotto__test_mwsc__ba37643d6a3b",
    sources=("frequency", "deviation", "markov_sequence", "pair_triple_structure"),
    transforms=("statistical_transform", "multi_window_consensus", "negative_exclusion"),
    construction=("three_overlapping_consensus_top18_slices",),
    dependencies=("wave26_frozen_unified_core_indirect", "negative_selector_family"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Four windows multiply transforms, not source independence.",
    multi_source=True,
)
add(
    "legacy_biglotto__test_cag__7ca5343dfedd",
    sources=("frequency", "deviation", "markov_sequence", "hot_cold", "gap_recency", "cooccurrence", "pair_triple_structure"),
    transforms=("statistical_transform", "weighted_method_vote", "negative_exclusion", "cooccurrence_anchor_rank"),
    construction=("three_anchor_grouped_tickets",),
    dependencies=("unified_prediction_engine_family", "negative_selector_family", "biglotto_wave9_cooccurrence"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_cross_number_relationships", "historical_within_draw_structure"),
    notes="Adds relationship-based construction to the same base top-18 engine pool.",
    multi_source=True,
)
add(
    "legacy_biglotto__test_cluster_cover__5b43959e7c55",
    sources=("frequency", "deviation", "markov_sequence", "hot_cold", "gap_recency", "cooccurrence", "pair_triple_structure"),
    transforms=("statistical_transform", "weighted_method_vote", "negative_exclusion", "cooccurrence_cluster_fill"),
    construction=("three_round_robin_cluster_cover_tickets", "diversification"),
    dependencies=("unified_prediction_engine_family", "negative_selector_family", "biglotto_wave9_cooccurrence"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_cross_number_relationships", "historical_within_draw_structure"),
    notes="Cluster construction differs, but its candidate pool is the base shared-engine optimizer.",
    multi_source=True,
)
add(
    "legacy_biglotto__test_zdp__e80cc7e95453",
    sources=("frequency", "deviation", "markov_sequence", "hot_cold", "gap_recency", "zone_range", "pair_triple_structure"),
    transforms=("statistical_transform", "weighted_method_vote", "negative_exclusion", "zonal_density_protection"),
    construction=("three_heavy_zone_configurations", "seeded_fallback"),
    dependencies=("unified_prediction_engine_family", "negative_selector_family"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Zone allocation is a construction layer over a shared-engine candidate pool.",
    multi_source=True,
)
add(
    "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01",
    sources=("frequency", "zone_range", "hot_cold", "gap_recency"),
    transforms=("bayesian_transform", "negative_exclusion"),
    construction=("zone_balance_plus_bayesian_two_ticket_portfolio",),
    dependencies=("unified_prediction_engine_family", "negative_selector_family"),
    independent_families=("historical_number_occurrence", "historical_within_draw_structure"),
    notes="Two engine outputs share one negative-selection filter.",
    multi_source=True,
)
add(
    "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d",
    sources=("frequency", "hot_cold", "cooccurrence", "pair_triple_structure", "symbolic_temporal"),
    transforms=("bayesian_transform", "graph_centrality", "entropy_validation", "regime_detection"),
    construction=("consensus_synergy_disruptor_three_ticket_portfolio", "diversification"),
    dependencies=("unified_prediction_engine_family", "biglotto_graph_family", "feature_analyzer_family"),
    independent_families=("historical_number_occurrence", "historical_cross_number_relationships", "historical_within_draw_structure", "historical_state_or_regime_sequence"),
    notes="One of the broader nontrivial ensembles, though all inputs remain historical draw outcomes.",
    multi_source=True,
)
add(
    "legacy_biglotto__backtest_strategy_1__41ed79a6de62",
    sources=("frequency", "hot_cold", "gap_recency", "zone_range"),
    transforms=("danger_filter", "zone_balance_retry"),
    construction=("frequency_plus_zone_two_ticket_portfolio",),
    dependencies=("unified_prediction_engine_family", "negative_selector_family"),
    independent_families=("historical_number_occurrence", "historical_within_draw_structure"),
    notes="Post-selection filtering changes construction, not the underlying occurrence data.",
    multi_source=True,
)
add(
    "legacy_biglotto__core_satellite__611284461323",
    sources=("other_outcome_blind_randomness",),
    transforms=("causal_identity_seed", "random_shuffle"),
    construction=("shared_core_disjoint_satellite_three_ticket_portfolio",),
    dependencies=("biglotto_wave11_random_native_helpers",),
    independent_families=("outcome_blind_randomness",),
    notes="Never reads historical number content; this is construction diversity, not predictive information.",
)
add(
    "legacy_biglotto__zone_split__b6144f9d479f",
    sources=("zone_range", "other_outcome_blind_randomness"),
    transforms=("causal_identity_seed", "fixed_zone_geometry"),
    construction=("random_native_three_zone_ticket_portfolio",),
    dependencies=("biglotto_wave11_random_native_helpers",),
    independent_families=("outcome_blind_structural_prior",),
    notes="Never reads historical number content; zones constrain a seeded random portfolio.",
)
add(
    "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2",
    sources=("frequency", "hot_cold"),
    transforms=("trailing50_rank",),
    construction=("sampled_hot_cold_orthogonal_three_ticket_portfolio", "diversification"),
    dependencies=("biglotto_wave11_history_native_helpers",),
    independent_families=("historical_number_occurrence",),
    notes="Random sampling occurs after hot/cold pools are defined; it is construction, not a new signal.",
)
add(
    "legacy_biglotto__social_wisdom_predictor__a00829b5d875",
    sources=("social_anti_popularity", "frequency"),
    transforms=("fixed_social_prior", "weighted_score_blend", "seeded_gaussian_perturbation"),
    construction=("eight_ticket_weight_noise_sweep",),
    dependencies=("biglotto_wave12_social_wisdom_helpers",),
    independent_families=("social_behavior_prior", "historical_number_occurrence"),
    notes="Genuinely distinct social prior; related to, but not identical with, the selected deterministic Social Wisdom ID.",
    multi_source=True,
)
add(
    "legacy_biglotto__negative_selection_biglotto__98f860c52cc2",
    sources=("frequency", "hot_cold", "gap_recency", "zone_range", "cooccurrence", "pair_triple_structure"),
    transforms=("negative_exclusion", "weighted_sampling", "structural_filter"),
    construction=("nominal_eight_ticket_diversity_portfolio", "cooccurrence_cluster_tail"),
    dependencies=("biglotto_wave12_negative_selection_helpers",),
    independent_families=("historical_number_occurrence", "historical_cross_number_relationships", "historical_within_draw_structure"),
    notes="Despite its name, this is frequency/hot-cold exclusion, not Social Wisdom; native dedup can shorten output.",
    multi_source=True,
    availability=RISK,
)
add(
    "legacy_biglotto__quick_ml_predict__8b7ba0b52e2d",
    sources=("frequency", "gap_recency", "hot_cold", "zone_range", "pair_triple_structure", "symbolic_temporal"),
    transforms=("handcrafted_score_ensemble", "pattern_matching", "hybrid_rank"),
    construction=("two_ticket_advanced_plus_hybrid_portfolio",),
    dependencies=("biglotto_wave12_quick_ml_helpers",),
    independent_families=("historical_number_occurrence", "historical_within_draw_structure", "historical_state_or_regime_sequence"),
    notes="Frozen pattern-slice IndexError triggers for every history length >=5; catalog min_history=1 does not make the realistic path executable.",
    multi_source=True,
    availability=DEAD,
)
add(
    "legacy_biglotto__test_asm__d39a233a4c75",
    sources=("frequency", "deviation", "markov_sequence", "hot_cold", "gap_recency", "pair_triple_structure"),
    transforms=("statistical_transform", "weighted_method_vote", "negative_exclusion"),
    construction=("three_fixed_index_maps_from_top18", "portfolio_optimization"),
    dependencies=("unified_prediction_engine_family", "negative_selector_family"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="An alternate slicing wrapper around the base three-bet optimizer pool.",
    multi_source=True,
    availability=RISK,
)
add(
    (
        "legacy_biglotto__test_dcb__c3299c25ca59",
        "legacy_biglotto__test_4bet_dcb__3c7e3e661ad8",
    ),
    sources=("frequency", "deviation", "markov_sequence", "hot_cold", "gap_recency", "cooccurrence", "pair_triple_structure"),
    transforms=("statistical_transform", "weighted_method_vote", "negative_exclusion", "correlation_boost"),
    construction=("three_or_four_overlapping_slices_from_same_boosted_top18", "portfolio_optimization"),
    dependencies=("unified_prediction_engine_family", "negative_selector_family", "biglotto_wave13_dcb_helpers"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_cross_number_relationships", "historical_within_draw_structure"),
    notes="DCB and 4-Bet DCB share one boosted candidate pool; only slice coverage differs.",
    multi_source=True,
    availability=RISK,
)
add(
    "legacy_biglotto__test_ecp__c9d5ac6decdd",
    sources=("frequency", "deviation", "markov_sequence", "hot_cold", "gap_recency", "pair_triple_structure"),
    transforms=("statistical_transform", "fifty_weight_consensus", "negative_exclusion"),
    construction=("three_overlapping_top18_slices",),
    dependencies=("unified_prediction_engine_family", "negative_selector_family"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Fifty repeated deterministic statistical calls collapse to one heavily weighted transform.",
    multi_source=True,
)
add(
    "legacy_biglotto__test_pce__9c0cf22b4217",
    sources=("frequency", "deviation", "markov_sequence", "trend", "zone_range", "hot_cold", "gap_recency", "pair_triple_structure"),
    transforms=("statistical_transform", "bayesian_transform", "pairwise_consensus", "negative_exclusion"),
    construction=("up_to_three_greedy_pair_vote_tickets",),
    dependencies=("unified_prediction_engine_family", "negative_selector_family"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure"),
    notes="Consensus construction spans seven shared-engine methods; fewer than three legal bets closes the adapter.",
    multi_source=True,
    availability=RISK,
)
add(
    "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8",
    sources=("frequency", "deviation", "markov_sequence", "trend", "hot_cold", "pair_triple_structure", "historical_feedback", "zone_range"),
    transforms=("statistical_transform", "rolling_method_audit", "zonal_density_protection"),
    construction=("audit_selected_single_ticket",),
    dependencies=("unified_prediction_engine_family",),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure", "historical_method_hit_feedback"),
    notes="DMS selects one shared-engine method from trailing hit feedback, then applies ZDP.",
    multi_source=True,
)
add(
    "legacy_biglotto__cold_hunter_predict__9e89f2b41add",
    sources=("gap_recency", "hot_cold"),
    transforms=("gap_bucket_rank",),
    construction=("three_hot_one_warm_two_cold_single_ticket",),
    dependencies=("biglotto_batch15_cold_hunter_family",),
    independent_families=("historical_number_occurrence_timing",),
    notes="One of six catalog IDs sharing the same cold_hunter_predictor source hash.",
)
add(
    "legacy_biglotto__short_window_deviation_predict__9e89f2b41add",
    sources=("frequency", "deviation", "gap_recency"),
    transforms=("seventy_five_twenty_five_deviation_gap_blend",),
    construction=("ranked_single_ticket",),
    dependencies=("biglotto_batch15_cold_hunter_family",),
    independent_families=("historical_number_occurrence",),
    notes="Short-window variation of the shared cold-hunter donor family.",
)
add(
    "legacy_biglotto__rebound_aware_predict__9e89f2b41add",
    sources=("gap_recency", "hot_cold", "zone_range", "symbolic_temporal"),
    transforms=("large_small_rebound_regime", "gap_bucket_rank"),
    construction=("regime_dependent_four_two_or_three_three_split",),
    dependencies=("biglotto_batch15_cold_hunter_family",),
    independent_families=("historical_number_occurrence_timing", "historical_state_or_regime_sequence"),
    notes="Uses a short streak state plus the same hot/warm/cold gap buckets.",
    multi_source=True,
)
add(
    "legacy_biglotto__zone_momentum_predict__9e89f2b41add",
    sources=("frequency", "gap_recency", "trend", "zone_range"),
    transforms=("short_vs_long_zone_momentum",),
    construction=("momentum_tilted_zone_quota_single_ticket",),
    dependencies=("biglotto_batch15_cold_hunter_family",),
    independent_families=("historical_number_occurrence", "historical_within_draw_structure"),
    notes="Can close if the donor's zone quotas do not emit six numbers.",
    multi_source=True,
    availability=RISK,
)
add(
    "legacy_biglotto__pure_cold_predict__9e89f2b41add",
    sources=("gap_recency", "hot_cold"),
    transforms=("descending_current_gap_rank",),
    construction=("ranked_single_ticket",),
    dependencies=("biglotto_batch15_cold_hunter_family",),
    independent_families=("historical_number_occurrence_timing",),
    notes="Pure gap rank; naming does not create an independent source.",
)
add(
    "legacy_biglotto__moderate_rank_predict__9e89f2b41add",
    sources=("gap_recency", "hot_cold"),
    transforms=("moderate_gap_rank", "previous_draw_exclusion"),
    construction=("ranked_single_ticket",),
    dependencies=("biglotto_batch15_cold_hunter_family",),
    independent_families=("historical_number_occurrence_timing",),
    notes="Skips both the previous draw and the five hottest candidates.",
)
add(
    "legacy_biglotto__gap_pressure_scorer__5e862ef27ee6",
    sources=("gap_recency",),
    transforms=("sigmoid_current_gap_over_historical_interval",),
    construction=("ranked_single_ticket",),
    dependencies=("biglotto_batch15_gap_pressure_family",),
    independent_families=("historical_number_occurrence_timing",),
    notes="A distinct gap normalization, but not a new raw data source.",
)
add(
    "legacy_biglotto__test_dm_dms_biglotto__bad71858012d",
    sources=("frequency", "deviation", "markov_sequence", "trend", "hot_cold", "pair_triple_structure", "historical_feedback"),
    transforms=("statistical_transform", "rolling_hit_audit"),
    construction=("top_two_audited_method_tickets",),
    dependencies=("unified_prediction_engine_family", "biglotto_batch15_dms_helpers"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure", "historical_method_hit_feedback"),
    notes="Top two methods by trailing audit; candidate signals remain shared-engine transforms.",
    multi_source=True,
)
add(
    "legacy_biglotto__test_dms_biglotto__10e39919c3a1",
    sources=("frequency", "deviation", "markov_sequence", "trend", "hot_cold", "pair_triple_structure", "historical_feedback"),
    transforms=("statistical_transform", "rolling_hit_audit"),
    construction=("single_audit_selected_method_ticket",),
    dependencies=("unified_prediction_engine_family", "biglotto_batch15_dms_helpers"),
    independent_families=("historical_number_occurrence", "historical_temporal_sequence", "historical_within_draw_structure", "historical_method_hit_feedback"),
    notes="Single-ticket sibling of DM-DMS with a different audit gate/window.",
    multi_source=True,
)
add(
    "b649_new_horizon_minimax_disagreement_r1",
    sources=("frequency", "deviation", "trend", "symbolic_temporal"),
    transforms=("multi_horizon_zscore", "ordinal_minimax", "horizon_disagreement"),
    construction=("consensus_plus_disagreement_two_ticket_barbell", "diversification"),
    dependencies=("sealed_b649_horizon_minimax_research_producer",),
    independent_families=("historical_number_occurrence", "historical_state_or_regime_sequence"),
    notes="Newest production strategy; historical research only and no predictive advantage claimed.",
    multi_source=True,
)


ROW_FIELDS = (
    "strategy_id",
    "adapter_file",
    "adapter_class",
    "catalog_wave_provenance_identity",
    "catalog_provenance",
    "response_shape",
    "native_ticket_count",
    "min_history",
    "actual_information_sources_consumed",
    "independent_information_source_families",
    "model_transformation_type",
    "portfolio_construction_behavior",
    "shared_engine_library_dependencies",
    "multi_source_internal_ensemble",
    "technical_availability_status",
    "frequency_gap_deviation_lineage",
    "notes_caveats",
)


def split_tokens(value: str) -> tuple[str, ...]:
    return tuple(item for item in value.split(";") if item)


def saturation(count: int) -> str:
    if count >= 20:
        return "HEAVILY_SATURATED"
    if count >= 6:
        return "MODERATELY_REPRESENTED"
    if count >= 1:
        return "SPARSELY_REPRESENTED"
    return "ABSENT"


def catalog_rows() -> list[dict[str, Any]]:
    descriptors = production_catalog().list(lottery_type=LotteryType.BIG_LOTTO)
    if len(descriptors) != EXPECTED_STRATEGY_COUNT:
        raise AssertionError(
            f"expected {EXPECTED_STRATEGY_COUNT} B649 strategies, got {len(descriptors)}"
        )
    catalog_ids = {descriptor.strategy_id for descriptor in descriptors}
    if catalog_ids != set(CLASSIFICATIONS):
        raise AssertionError(
            "classification/catalog mismatch: "
            f"missing={sorted(catalog_ids - set(CLASSIFICATIONS))}, "
            f"extra={sorted(set(CLASSIFICATIONS) - catalog_ids)}"
        )

    dominant = {
        "frequency", "gap_recency", "hot_cold", "deviation",
        "markov_sequence", "trend", "zone_range",
    }
    rows: list[dict[str, Any]] = []
    for descriptor in descriptors:
        if descriptor.adapter_path is None:
            raise AssertionError(f"missing adapter path: {descriptor.strategy_id}")
        module_name, adapter_class = descriptor.adapter_path.split(":", 1)
        adapter_path = SRC_ROOT.joinpath(*module_name.split(".")).with_suffix(".py")
        if not adapter_path.is_file():
            raise AssertionError(f"adapter file not found: {adapter_path}")
        identity_tokens = tuple(
            token
            for token in descriptor.provenance
            if token.startswith(("migration_task:", "research_task:", "legacy_task:"))
        )
        classification = CLASSIFICATIONS[descriptor.strategy_id]
        sources = set(split_tokens(classification["actual_information_sources_consumed"]))
        lineage = (
            bool(sources & dominant)
            and len(sources & dominant) * 2 >= len(sources)
            and "social_anti_popularity" not in sources
            and "other_outcome_blind_randomness" not in sources
        )
        rows.append(
            {
                "strategy_id": descriptor.strategy_id,
                "adapter_file": str(adapter_path.relative_to(REPO_ROOT)),
                "adapter_class": adapter_class,
                "catalog_wave_provenance_identity": ";".join(identity_tokens),
                "catalog_provenance": ";".join(descriptor.provenance),
                "response_shape": descriptor.response_shape.value,
                "native_ticket_count": descriptor.native_ticket_count,
                "min_history": descriptor.min_history,
                **classification,
                "frequency_gap_deviation_lineage": "YES" if lineage else "NO",
            }
        )
    if len({row["adapter_file"] for row in rows}) != EXPECTED_ADAPTER_FILE_COUNT:
        raise AssertionError("adapter-file count drifted from 17")
    return rows


def csv_text(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
    return stream.getvalue()


def source_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = {source: [] for source in SOURCE_TAXONOMY}
    for row in rows:
        for source in split_tokens(row["actual_information_sources_consumed"]):
            counts[source] += 1
            if len(examples[source]) < 5:
                examples[source].append(row["strategy_id"])
    summaries: list[dict[str, Any]] = []
    for source in (*SOURCE_TAXONOMY, *ABSENT_SOURCE_TAXONOMY):
        count = counts[source]
        summaries.append(
            {
                "information_source": source,
                "independent_information_family": SOURCE_FAMILY[source],
                "strategy_count": count,
                "share_of_69": f"{count / EXPECTED_STRATEGY_COUNT:.6f}",
                "saturation_class": saturation(count),
                "example_strategy_ids": ";".join(examples.get(source, [])),
                "interpretation": (
                    "No production B649 strategy consumes this source."
                    if count == 0
                    else "Counts IDs consuming the dimension; it does not imply source independence."
                ),
            }
        )
    return summaries


def performance_summaries(
    rows: list[dict[str, Any]], summaries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for summary in summaries:
        source = summary["information_source"]
        members = [
            row
            for row in rows
            if source in split_tokens(row["actual_information_sources_consumed"])
        ]
        risk_count = sum(row["technical_availability_status"] == RISK for row in members)
        dead = [row["strategy_id"] for row in members if row["technical_availability_status"] == DEAD]
        available_count = sum(row["technical_availability_status"] == AVAILABLE for row in members)
        count = int(summary["strategy_count"])
        redundancy = (
            "HIGH" if count >= 20 else "MEDIUM" if count >= 6 else "LOW" if count else "NONE"
        )
        output.append(
            {
                "information_source": source,
                "strategy_count": count,
                "technical_available_count": available_count,
                "native_closure_risk_count": risk_count,
                "dead_path_count": len(dead),
                "known_failure_strategy_ids": ";".join(dead),
                "redundancy_association": redundancy,
                "historical_performance_association": "SOURCE_UNAVAILABLE",
                "performance_evidence_note": (
                    "Referenced 2,148-execution hit/prize summary was not resolved. "
                    "Local source-native JSON proves execution/reproduction only; "
                    "the local snapshot DB covers 11 legacy B649 IDs and only one "
                    "exact current catalog ID, so it is not a comparable 69-strategy source summary."
                ),
            }
        )
    return output


CANDIDATES = (
    {
        "rank": 1,
        "candidate_source": "cross_lottery_lagged_context",
        "why_distinct": "Uses only completed T539/P638/B649 outcomes available before the target; none of the 69 adapters consumes another lottery's history.",
        "pre_target_availability": "STRICT: lag all foreign-game rows to timestamps before the target cutoff.",
        "technical_obtainability": "HIGH: repository already models all three lottery types and historical draws.",
        "estimated_test_cost": "LOW_TO_MEDIUM",
        "temporal_transferability": "MEDIUM; validate by rolling origin and lottery-specific normalization.",
        "cross_lottery_relevance": "B649,T539,P638",
        "main_risk": "Spurious calendar correlation and unequal draw schedules; preregister lag and null controls.",
        "first_test": "Add date-aligned lagged foreign frequency/entropy/regime features to a simple locked baseline.",
    },
    {
        "rank": 2,
        "candidate_source": "calendar_schedule_context",
        "why_distinct": "CausalDrawRow carries date, but production adapters use it only for validation/seed/order guards, not as a predictive feature.",
        "pre_target_availability": "STRICT: weekday, draw interval, holiday proximity, month and schedule regime are known in advance.",
        "technical_obtainability": "HIGH: no new outcome feed required; holiday tables are small and versionable.",
        "estimated_test_cost": "LOW",
        "temporal_transferability": "MEDIUM; use coarse preregistered bins and regime-aware validation.",
        "cross_lottery_relevance": "B649,T539,P638",
        "main_risk": "Multiple-testing and seasonality overfit; prefer a few predeclared features.",
        "first_test": "Evaluate calendar features alone, then conditional interactions with the locked frequency baseline.",
    },
    {
        "rank": 3,
        "candidate_source": "draw_order_position",
        "why_distinct": "Adapters receive canonical sorted number tuples, so physical draw order/ball position is discarded before every strategy runs.",
        "pre_target_availability": "STRICT for training rows; target features must use only prior ordered draws.",
        "technical_obtainability": "MEDIUM: requires a separately verified ordered-results archive and immutable ingestion contract.",
        "estimated_test_cost": "MEDIUM",
        "temporal_transferability": "MEDIUM_TO_LOW unless stable across equipment regimes.",
        "cross_lottery_relevance": "B649,T539,P638 where ordered results are source-verifiable",
        "main_risk": "Published display order may be sorted rather than physical order; provenance must fail closed.",
        "first_test": "Audit source semantics first, then test position-transition features against permutation nulls.",
    },
    {
        "rank": 4,
        "candidate_source": "realized_player_popularity_and_market_state",
        "why_distinct": "Current Social Wisdom uses a static birthday-number prior; no strategy uses observed winner counts, prize splits, jackpot rollover or sales state.",
        "pre_target_availability": "STRICT when using only prior published winner/payout/sales rows and the announced pre-draw jackpot.",
        "technical_obtainability": "MEDIUM: needs a versioned official prize-market archive joined by draw ID/date.",
        "estimated_test_cost": "MEDIUM",
        "temporal_transferability": "MEDIUM for payout optimization, LOW for ball-outcome prediction.",
        "cross_lottery_relevance": "B649,T539,P638 with lottery-specific payout normalization",
        "main_risk": "This may improve expected prize sharing, not winning-number probability; keep objectives separate.",
        "first_test": "Model historical split risk as a construction objective without altering the locked draw-probability model.",
    },
    {
        "rank": 5,
        "candidate_source": "equipment_ballset_regime",
        "why_distinct": "No strategy or CausalDrawRow field represents machine, ball set, venue or maintenance regime.",
        "pre_target_availability": "CONDITIONAL: only metadata published before each target may be used.",
        "technical_obtainability": "LOW_TO_MEDIUM: first prove an auditable source and stable identifiers.",
        "estimated_test_cost": "MEDIUM_TO_HIGH",
        "temporal_transferability": "LOW_TO_MEDIUM; strongest value may be changepoint stratification.",
        "cross_lottery_relevance": "Method transfers to B649,T539,P638; equipment identities do not.",
        "main_risk": "Sparse regimes, missing metadata and post-target leakage.",
        "first_test": "Run a metadata availability audit before any predictive experiment.",
    },
)


def fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(REPO_ROOT)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def report_text(
    rows: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> str:
    adapter_files = sorted({REPO_ROOT / row["adapter_file"] for row in rows})
    direct_unified = sum(
        "legacy_source:lottery_api/models/unified_predictor.py"
        in row["catalog_provenance"].split(";")
        for row in rows
    )
    indirect_or_variant = sum(
        any(
            marker in row["shared_engine_library_dependencies"]
            for marker in (
                "wave26_frozen_unified_core_indirect",
                "local_gemini_reimplementation_of_unified_family",
            )
        )
        for row in rows
    )
    lineage_count = sum(row["frequency_gap_deviation_lineage"] == "YES" for row in rows)
    multi_count = sum(row["multi_source_internal_ensemble"] == "YES" for row in rows)
    by_saturation: dict[str, list[str]] = {
        "HEAVILY_SATURATED": [],
        "MODERATELY_REPRESENTED": [],
        "SPARSELY_REPRESENTED": [],
        "ABSENT": [],
    }
    for item in summaries:
        by_saturation[item["saturation_class"]].append(
            f"{item['information_source']} ({item['strategy_count']})"
        )
    transforms = Counter(
        token
        for row in rows
        for token in split_tokens(row["model_transformation_type"])
    )
    constructions = Counter(
        token
        for row in rows
        for token in split_tokens(row["portfolio_construction_behavior"])
    )
    dead_ids = [row["strategy_id"] for row in rows if row["technical_availability_status"] == DEAD]
    risk_ids = [row["strategy_id"] for row in rows if row["technical_availability_status"] == RISK]

    def joined(items: list[str]) -> str:
        return ", ".join(items) if items else "none"

    top_transforms = ", ".join(f"{name} ({count})" for name, count in transforms.most_common(8))
    top_constructions = ", ".join(
        f"{name} ({count})" for name, count in constructions.most_common(8)
    )
    return f"""# B649 strategy information-source provenance consolidation

GOAL_ID: {GOAL_ID}

STATUS: COMPLETE

## Scope and evidence

- Production strategies: **{len(rows)}**
- Adapter files: **{len(adapter_files)}**
- Catalog source: `src/lottolab/strategies/catalog.py`
- Adapter aggregate SHA-256: `{fingerprint(adapter_files)}`
- Catalog SHA-256: `{hashlib.sha256((REPO_ROOT / 'src/lottolab/strategies/catalog.py').read_bytes()).hexdigest()}`
- Taxonomy rule: source/feature dimensions, model transforms, and ticket construction are separate columns. Counts are strategy-ID incidence counts and may overlap; they are not independent-source counts.
- Saturation thresholds: `HEAVILY_SATURATED >=20`, `MODERATELY_REPRESENTED 6-19`, `SPARSELY_REPRESENTED 1-5`, `ABSENT 0`.

Data quality: 69 unique catalog IDs matched 69 classifications and 17 adapter files. No duplicate strategy row exists. The referenced row-level predecessor artifacts were absent and the existing task directory was empty, so consolidation used the live catalog, adapter/module contracts, shared-helper dependency chain, and the continuation's grounded findings. No new 69-strategy replay was run.

## Main finding

The catalog is highly saturated in transformations of the same historical draw stream, not in independent predictive information. **{lineage_count}/69** IDs meet the deterministic “frequency/gap/deviation lineage” rule (at least half their labeled dimensions are occurrence, gap, hot/cold, deviation, Markov, trend, or zone derivatives, excluding Social Wisdom and outcome-blind random paths).

The catalog directly pins **{direct_unified}** IDs to `unified_predictor.py`; another **{indirect_or_variant}** IDs use the same family indirectly (four Wave-8 frozen-core consumers) or as a local Gemini variant. Therefore `UNIFIED_ENGINE_STRATEGY_COUNT` is **{direct_unified} direct / {direct_unified + indirect_or_variant} lineage-inclusive**. Strategy IDs are not independent evidence units.

AutoDiscovery is represented correctly as `ONE_STRATEGY_ID / MULTI_SOURCE_INTERNAL_ENSEMBLE`: 30 internal scoring functions produce 54 native method/window tickets. Across the full table, **{multi_count}** IDs are flagged as multi-source/internal ensembles under the explicit row-level definition.

## Saturation

- HEAVILY_SATURATED: {joined(by_saturation['HEAVILY_SATURATED'])}
- MODERATELY_REPRESENTED: {joined(by_saturation['MODERATELY_REPRESENTED'])}
- SPARSELY_REPRESENTED: {joined(by_saturation['SPARSELY_REPRESENTED'])}
- ABSENT: {joined(by_saturation['ABSENT'])}

Dominant raw/derived dimensions are frequency and its deviation/hot-cold/trend relatives, followed by Markov/structural/zone transforms. Social anti-popularity is genuinely distinct but sparse. Outcome-blind random-native paths add construction diversity, not predictive information.

## Redundancy clusters

- Unified family: {direct_unified} catalog-pinned IDs; {direct_unified + indirect_or_variant} including indirect/variant consumers.
- Selected positional aliases: three Zone Split IDs, two Deviation IDs, and two P0 Hot+Echo/Cold IDs expose positions from shared producers.
- N-bet optimizer family: 2-bet, 3-bet, Gemini, CAG, Cluster-Cover, ZDP, ASM, DCB, ECP and PCE mostly alter weighting, exclusion and slicing over shared feeder methods.
- Cluster-Pivot: six- and seven-ticket IDs share one co-occurrence producer.
- Batch-15 cold-hunter family: six IDs share source hash `9e89f2b41add...` and differentiate gap/rank transforms.
- Social Wisdom is not NegativeSelection: Social Wisdom consumes a behavioral anti-popularity prior; NegativeSelection consumes frequency/hot-cold/gap/co-occurrence history.

## Transform and construction concentration

- Most common transforms: {top_transforms}
- Most common constructions: {top_constructions}

## Technical availability

- TECHNICALLY_UNAVAILABLE / DEAD_PRODUCTION_PATH: {joined(dead_ids)}
- TECHNICALLY_AVAILABLE_WITH_NATIVE_CLOSURE_RISK: {joined(risk_ids)}

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
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .task-data/{GOAL_ID}/reproduce_analysis.py --check
```

The script validates the exact catalog set/count, adapter-file count, taxonomy membership, and byte-for-byte output determinism.
"""


def rendered_outputs() -> dict[str, str]:
    rows = catalog_rows()
    summaries = source_summaries(rows)
    performance = performance_summaries(rows, summaries)
    return {
        "strategy_information_sources.csv": csv_text(rows, ROW_FIELDS),
        "information_source_summary.csv": csv_text(
            summaries,
            (
                "information_source",
                "independent_information_family",
                "strategy_count",
                "share_of_69",
                "saturation_class",
                "example_strategy_ids",
                "interpretation",
            ),
        ),
        "source_performance_summary.csv": csv_text(
            performance,
            (
                "information_source",
                "strategy_count",
                "technical_available_count",
                "native_closure_risk_count",
                "dead_path_count",
                "known_failure_strategy_ids",
                "redundancy_association",
                "historical_performance_association",
                "performance_evidence_note",
            ),
        ),
        "missing_information_candidates.csv": csv_text(
            list(CANDIDATES),
            (
                "rank",
                "candidate_source",
                "why_distinct",
                "pre_target_availability",
                "technical_obtainability",
                "estimated_test_cost",
                "temporal_transferability",
                "cross_lottery_relevance",
                "main_risk",
                "first_test",
            ),
        ),
        "report.md": report_text(rows, summaries),
    }


def main() -> int:
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] != "--check"):
        print("usage: reproduce_analysis.py [--check]", file=sys.stderr)
        return 2
    outputs = rendered_outputs()
    if len(sys.argv) == 2:
        mismatches = [
            name
            for name, content in outputs.items()
            if not (OUTPUT_ROOT / name).is_file()
            or (OUTPUT_ROOT / name).read_text(encoding="utf-8") != content
        ]
        if mismatches:
            print("CHECK_FAIL " + " ".join(mismatches), file=sys.stderr)
            return 1
        print(
            "CHECK_PASS strategies=69 adapter_files=17 outputs=5 "
            "performance_association=SOURCE_UNAVAILABLE"
        )
        return 0
    for name, content in outputs.items():
        (OUTPUT_ROOT / name).write_text(content, encoding="utf-8", newline="")
    print("WROTE strategies=69 adapter_files=17 outputs=5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
