"""Closed-outcome tests for the injected GenerateLiveZoneSplitBets use case."""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from lottolab.application.use_cases.generate_live_zone_split_bets import (
    GenerateLiveZoneSplitBets,
    GenerateLiveZoneSplitBetsInput,
    GenerateLiveZoneSplitBetsReason,
    GenerateLiveZoneSplitBetsResult,
    GenerateLiveZoneSplitBetsStatus,
    build_production_generate_live_zone_split_bets,
)
from lottolab.domain.strategies import LifecycleStatus
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.live.biglotto_zone_split import (
    LiveZoneSplitResult,
    MalformedSamplerOutput,
)

_POOL_SIZE = 49


def _result(
    *,
    bets: tuple[tuple[int, ...], ...] = ((1, 2, 3, 4, 5, 6),),
    coverage_rate: float | None = None,
    total_unique_numbers: int | None = None,
    method: str = "fixture-method",
    philosophy: str = "fixture-philosophy",
) -> LiveZoneSplitResult:
    all_numbers = {number for bet in bets for number in bet}
    if total_unique_numbers is None:
        total_unique_numbers = len(all_numbers)
    if coverage_rate is None:
        coverage_rate = round(len(all_numbers) / _POOL_SIZE, 4)
    return LiveZoneSplitResult(
        bets=bets,
        coverage_rate=coverage_rate,
        total_unique_numbers=total_unique_numbers,
        method=method,
        philosophy=philosophy,
    )


def _spy(outcome: object):
    calls: list[int] = []

    def generator(num_bets: int) -> LiveZoneSplitResult:
        calls.append(num_bets)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome  # type: ignore[return-value]

    return generator, calls


# --- 1. valid generator maps every field exactly ---------------------------


def test_execute_maps_valid_generator_output_to_ok_result() -> None:
    bets = ((1, 2, 3, 4, 5, 6), (10, 11, 12, 13, 14, 15), (20, 21, 22, 23, 24, 25))
    core_result = _result(bets=bets, method="m", philosophy="p")
    generator, calls = _spy(core_result)
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=3))

    assert calls == [3]
    assert result.status is GenerateLiveZoneSplitBetsStatus.OK
    assert result.bets == bets
    assert result.coverage_rate == core_result.coverage_rate
    assert result.total_unique_numbers == core_result.total_unique_numbers
    assert result.method == "m"
    assert result.philosophy == "p"
    assert result.reason_code is None


# --- 2. production builder returns structurally valid results --------------


@pytest.mark.parametrize("num_bets", [1, 3, 10])
def test_production_builder_returns_structurally_valid_results(num_bets: int) -> None:
    use_case = build_production_generate_live_zone_split_bets()

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=num_bets))

    assert result.status is GenerateLiveZoneSplitBetsStatus.OK
    assert result.reason_code is None
    assert result.bets is not None
    assert len(result.bets) == num_bets
    seen: set[int] = set()
    for bet in result.bets:
        assert len(bet) == 6
        assert len(set(bet)) == 6
        assert all(1 <= number <= 49 for number in bet)
        seen.update(bet)
    assert result.total_unique_numbers == len(seen)
    assert result.coverage_rate == round(len(seen) / _POOL_SIZE, 4)
    assert result.method
    assert result.philosophy


# --- 4. invalid inputs fail closed and never call the generator ------------


@pytest.mark.parametrize(
    "num_bets",
    [0, 11, -1, True, False, 3.0, "3"],
    ids=["zero", "above-max", "negative", "bool-true", "bool-false", "float", "string"],
)
def test_execute_rejects_invalid_num_bets_without_calling_generator(num_bets: object) -> None:
    generator, calls = _spy(_result())
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=num_bets))  # type: ignore[arg-type]

    assert calls == []
    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_REQUEST
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.INVALID_NUM_BETS
    assert result.bets is None


# --- 5. MalformedSamplerOutput maps to INVALID_OUTPUT/MALFORMED_OUTPUT -----


def test_execute_maps_malformed_sampler_output_to_invalid_output() -> None:
    generator, _ = _spy(MalformedSamplerOutput("bad sampler output"))
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=3))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT
    assert result.bets is None


# --- 6. unexpected exceptions map to EXECUTION_ERROR/EXECUTION_ERROR -------


def test_execute_maps_unexpected_exception_to_execution_error() -> None:
    generator, _ = _spy(RuntimeError("boom"))
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=3))

    assert result.status is GenerateLiveZoneSplitBetsStatus.EXECUTION_ERROR
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.EXECUTION_ERROR
    assert result.bets is None


# --- 7. wrong return type maps to INVALID_OUTPUT ----------------------------


def test_execute_rejects_wrong_generator_return_type() -> None:
    generator, _ = _spy({"not": "a LiveZoneSplitResult"})
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=3))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT


# --- 8. wrong bet count maps to INVALID_OUTPUT ------------------------------


def test_execute_rejects_wrong_bet_count() -> None:
    core_result = _result(bets=((1, 2, 3, 4, 5, 6),))
    generator, _ = _spy(core_result)
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=3))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT


# --- 9. invalid element type, duplicates, wrong count, out-of-range --------


@pytest.mark.parametrize(
    "bad_bets",
    [
        (("1", 2, 3, 4, 5, 6),),
        ((1, 1, 2, 3, 4, 5),),
        ((1, 2, 3, 4, 5),),
        ((1, 2, 3, 4, 5, 6, 7),),
        ((0, 2, 3, 4, 5, 6),),
        ((1, 2, 3, 4, 5, 50),),
        ([1, 2, 3, 4, 5, 6],),
        ((True, 2, 3, 4, 5, 6),),
    ],
    ids=[
        "wrong-element-type",
        "duplicate",
        "too-short",
        "too-long",
        "below-range",
        "above-range",
        "list-not-tuple",
        "bool-not-exact-int",
    ],
)
def test_execute_rejects_malformed_bet_contents(bad_bets: object) -> None:
    core_result = _result(bets=bad_bets)  # type: ignore[arg-type]
    generator, _ = _spy(core_result)
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=1))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT


# --- 10. inconsistent total_unique_numbers maps to INVALID_OUTPUT ----------


def test_execute_rejects_inconsistent_total_unique_numbers() -> None:
    core_result = _result(bets=((1, 2, 3, 4, 5, 6),), total_unique_numbers=99)
    generator, _ = _spy(core_result)
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=1))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT


# --- 11. inconsistent coverage_rate maps to INVALID_OUTPUT ------------------


def test_execute_rejects_inconsistent_coverage_rate() -> None:
    core_result = _result(bets=((1, 2, 3, 4, 5, 6),), coverage_rate=0.9999)
    generator, _ = _spy(core_result)
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=1))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT


# --- 12. empty method or philosophy maps to INVALID_OUTPUT -----------------


@pytest.mark.parametrize(
    "method,philosophy",
    [("", "p"), ("m", "")],
    ids=["empty-method", "empty-philosophy"],
)
def test_execute_rejects_empty_method_or_philosophy(method: str, philosophy: str) -> None:
    core_result = _result(method=method, philosophy=philosophy)
    generator, _ = _spy(core_result)
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=1))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT


# --- 13. result-model OK/failure invariants are mutation-sensitive ---------

_VALID_PAYLOAD: dict[str, object] = {
    "bets": ((1, 2, 3, 4, 5, 6),),
    "coverage_rate": 0.1224,
    "total_unique_numbers": 6,
    "method": "m",
    "philosophy": "p",
}


@pytest.mark.parametrize("missing_field", sorted(_VALID_PAYLOAD))
def test_ok_result_requires_every_payload_field(missing_field: str) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload[missing_field] = None
    with pytest.raises(ValueError):
        GenerateLiveZoneSplitBetsResult(
            status=GenerateLiveZoneSplitBetsStatus.OK,
            reason_code=None,
            **payload,  # type: ignore[arg-type]
        )


def test_ok_result_rejects_reason_code() -> None:
    with pytest.raises(ValueError):
        GenerateLiveZoneSplitBetsResult(
            status=GenerateLiveZoneSplitBetsStatus.OK,
            reason_code=GenerateLiveZoneSplitBetsReason.EXECUTION_ERROR,
            **_VALID_PAYLOAD,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("present_field", sorted(_VALID_PAYLOAD))
def test_failure_result_rejects_any_payload_field(present_field: str) -> None:
    payload: dict[str, object] = {key: None for key in _VALID_PAYLOAD}
    payload[present_field] = _VALID_PAYLOAD[present_field]
    with pytest.raises(ValueError):
        GenerateLiveZoneSplitBetsResult(
            status=GenerateLiveZoneSplitBetsStatus.INVALID_REQUEST,
            reason_code=GenerateLiveZoneSplitBetsReason.INVALID_NUM_BETS,
            **payload,  # type: ignore[arg-type]
        )


def test_failure_result_requires_reason_code() -> None:
    with pytest.raises(ValueError):
        GenerateLiveZoneSplitBetsResult(
            status=GenerateLiveZoneSplitBetsStatus.INVALID_REQUEST,
            reason_code=None,
            bets=None,
            coverage_rate=None,
            total_unique_numbers=None,
            method=None,
            philosophy=None,
        )


def test_result_invariants_allow_valid_direct_construction() -> None:
    ok = GenerateLiveZoneSplitBetsResult(
        status=GenerateLiveZoneSplitBetsStatus.OK,
        reason_code=None,
        **_VALID_PAYLOAD,  # type: ignore[arg-type]
    )
    failure = GenerateLiveZoneSplitBetsResult(
        status=GenerateLiveZoneSplitBetsStatus.INVALID_REQUEST,
        reason_code=GenerateLiveZoneSplitBetsReason.INVALID_NUM_BETS,
        bets=None,
        coverage_rate=None,
        total_unique_numbers=None,
        method=None,
        philosophy=None,
    )

    assert ok.bets == _VALID_PAYLOAD["bets"]
    assert ok.reason_code is None
    assert failure.bets is None
    assert failure.reason_code is GenerateLiveZoneSplitBetsReason.INVALID_NUM_BETS


def test_input_and_result_models_are_frozen() -> None:
    request = GenerateLiveZoneSplitBetsInput(num_bets=1)
    result = GenerateLiveZoneSplitBetsResult(
        status=GenerateLiveZoneSplitBetsStatus.OK,
        reason_code=None,
        **_VALID_PAYLOAD,  # type: ignore[arg-type]
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        request.num_bets = 2  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.bets = None  # type: ignore[misc]


# --- 14. input/execute surfaces expose no forbidden fields ------------------


def test_input_and_execute_surfaces_expose_no_forbidden_fields() -> None:
    forbidden = {"history", "seed", "strategy_id", "lottery_type", "sampler"}

    input_fields = {field.name for field in dataclasses.fields(GenerateLiveZoneSplitBetsInput)}
    assert input_fields == {"num_bets"}
    assert input_fields.isdisjoint(forbidden)

    execute_params = set(inspect.signature(GenerateLiveZoneSplitBets.execute).parameters) - {
        "self"
    }
    assert execute_params == {"request"}


# --- 16. production catalog retains exact ONLINE IDs in append order -------


def test_production_catalog_has_exact_online_strategies_in_append_order() -> None:
    online = production_catalog().list(lifecycle_status=LifecycleStatus.ONLINE)
    assert [descriptor.strategy_id for descriptor in online] == [
        "biglotto_social_wisdom_anti_popularity",
        "biglotto_zone_split_3bet_bet1",
        "biglotto_zone_split_3bet_bet2",
        "biglotto_zone_split_3bet_bet3",
        "biglotto_deviation_2bet",
        "biglotto_deviation_2bet_bet2",
        "biglotto_p0_2bet_bet1",
        "biglotto_p0_2bet_bet2",
        "legacy_biglotto__graph_predictor__cd70713a5709",
        "legacy_biglotto__backtest_must_hit__909c91fd2fd0",
        "legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac",
        "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee",
        "legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4",
        "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e",
        "legacy_biglotto__core_satellite__2e82891003b3",
        "legacy_biglotto__auto_discovery_biglotto__06bcb164db84",
        "legacy_biglotto__biglotto_2bet_final__7eaedb330a07",
        "legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876",
        "legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3",
        "legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5",
        "legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad",
        "legacy_biglotto__optimized_ensemble__e05e0fde22d7",
        "legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511",
        "legacy_biglotto__predict_biglotto_6bets_cluster__1fd9e8a7ae2a",
        "legacy_biglotto__predict_biglotto_7bets_cluster__8f55b5d94669",
        "legacy_biglotto__predict_biglotto_echo_2bet__59c20b25b1fa",
        "legacy_biglotto__predict_biglotto_elite7__eb46a9856446",
        "legacy_biglotto__research_variant_history__149648f9fffc",
        "legacy_biglotto__auto_optimizer_alpha__7eaa9572e384",
        "legacy_biglotto__backtest_10bet_biglotto__054e85b088be",
        "legacy_biglotto__test_tme__f3bb5106dfe3",
        "legacy_biglotto__verify_gemini_2bet_claim__d5ca233aa776",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
        "legacy_biglotto__predict_big_lotto_smart_2bet__7acdaab1bd0a",
        "legacy_biglotto__verify_gemini_phase2_claim__6407a8f39519",
        "legacy_biglotto__attention_replay_predictor__a811e2eb8215",
        "legacy_biglotto__predict_biglotto_115000002_zone_balance__8febca575f5d",
        "legacy_biglotto__test_ces__78d17c530ab8",
        "legacy_biglotto__test_dms__b63442289bd5",
        "legacy_biglotto__test_greedy_optimizer__82df7f878ece",
        "legacy_biglotto__test_mwsc__ba37643d6a3b",
        "legacy_biglotto__test_cag__7ca5343dfedd",
        "legacy_biglotto__test_cluster_cover__5b43959e7c55",
        "legacy_biglotto__test_zdp__e80cc7e95453",
        "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01",
        "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d",
        "legacy_biglotto__backtest_strategy_1__41ed79a6de62",
        "legacy_biglotto__core_satellite__611284461323",
        "legacy_biglotto__zone_split__b6144f9d479f",
        "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2",
        "legacy_biglotto__social_wisdom_predictor__a00829b5d875",
        "legacy_biglotto__negative_selection_biglotto__98f860c52cc2",
        "legacy_biglotto__quick_ml_predict__8b7ba0b52e2d",
        "legacy_biglotto__test_asm__d39a233a4c75",
        "legacy_biglotto__test_dcb__c3299c25ca59",
        "legacy_biglotto__test_4bet_dcb__3c7e3e661ad8",
        "legacy_biglotto__test_ecp__c9d5ac6decdd",
        "legacy_biglotto__test_pce__9c0cf22b4217",
        "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8",
        "legacy_biglotto__cold_hunter_predict__9e89f2b41add",
        "legacy_biglotto__short_window_deviation_predict__9e89f2b41add",
        "legacy_biglotto__rebound_aware_predict__9e89f2b41add",
        "legacy_biglotto__zone_momentum_predict__9e89f2b41add",
        "legacy_biglotto__pure_cold_predict__9e89f2b41add",
        "legacy_biglotto__moderate_rank_predict__9e89f2b41add",
        "legacy_biglotto__gap_pressure_scorer__5e862ef27ee6",
        "legacy_biglotto__test_dm_dms_biglotto__bad71858012d",
        "legacy_biglotto__test_dms_biglotto__10e39919c3a1",
        "b649_new_horizon_minimax_disagreement_r1",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b",
        "legacy_biglotto__minimal_dual_bet_strategy__3c9657df7ff4",
        "power_c01_recency_decay_1bet",
        "power_c02_gap_overdue_1bet",
        "power_c03_pair_centrality_1bet",
        "power_c04_zone_balanced_1bet",
        "power_c05_dispersion_match_1bet",
        "power_c06_regime_cusum_1bet",
        "power_c07_borda_ensemble_1bet",
        "acb_markov_midfreq_3bet",
        "legacy_biglotto__backtest_apriori__2abb53765703",
        "legacy_biglotto__covering_strategy_research__214ecc206fc9",
        "legacy_biglotto__evolution_engine__3df019c31ce4",
        "legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504",
        "legacy_biglotto__backtest_sum_constraint__acb3b118300d",
        "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae",
        "legacy_biglotto__verify_markov_vs_triple_2bet__2094ee4bc361",
        "legacy_biglotto__backtest_biglotto_coldpool_15__2a80423e3cf5",
        "zonal_entropy_2bet",
        "power_apriori_2bet",
        "power_lead_lag_2bet",
        "acb_single_539",
        "biglotto_wave2_neighbor_ad_cooccurrence_anti_pairs",
        "biglotto_wave2_neighbor_ad_cooccurrence_conditional",
        "biglotto_wave2_neighbor_ad_cooccurrence_top_pairs",
        "biglotto_wave2_neighbor_ad_cooccurrence_transition_pairs",
        "biglotto_wave2_neighbor_ad_cooccurrence_triplet",
        "biglotto_wave2_neighbor_ad_graph_bridge_bet",
        "biglotto_wave2_neighbor_ad_graph_centrality_bet",
        "biglotto_wave2_neighbor_ad_graph_pagerank_bet",
        "biglotto_wave2_sum_range_ad_structural_sum_regression",
        "biglotto_wave2_social_ad_negative_consensus_remove",
        "legacy_biglotto__concentrated_pool_predictor__a03b90705749",
        "legacy_biglotto__constraint_filter_predictor__3a85b3995002",
        "legacy_biglotto__predict_biglotto_apriori__cda690ae84c2",
        "legacy_biglotto__smart_multi_bet__613c62c1f192",
        "legacy_biglotto__anti_consensus_strategy__a454ddd26cef",
        "legacy_biglotto__cooccurrence_graph__25fa2e473092",
        "legacy_biglotto__backtest_radical_strategy__e54cc0812bc6",
        "legacy_biglotto__power_fourier_rhythm__cb75e72e4c94",
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_biglotto__predict_biglotto_quad_strike__e202e664208f",
        "legacy_biglotto__frontend_markov_strategy__2fc1cafea55c",
        "legacy_biglotto__orthogonal_2bet_optimizer__aa51b0e5e4a4",
        "legacy_biglotto__frontend_trend_strategy__a5f4554c80ef",
        "legacy_biglotto__frontend_bayesian_strategy__baa3045817fb",
        "legacy_biglotto__biglotto_2bet_hedging__07a3aa455074",
    ]
