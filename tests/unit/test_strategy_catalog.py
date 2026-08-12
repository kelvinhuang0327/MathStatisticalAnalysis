"""Invariant tests — these replace legacy exact-count/blob-pin assertions.

Adding a strategy must NEVER require editing these tests.
"""

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import (
    LifecycleStatus,
    ResponseShape,
    StrategyDescriptor,
)
from lottolab.strategies.adapters import (
    BigLottoDeviation2BetBet2Adapter,
    BigLottoP02BetBet1Adapter,
    BigLottoP02BetBet2Adapter,
    BigLottoZoneSplit3BetBet2Adapter,
    BigLottoZoneSplit3BetBet3Adapter,
)
from lottolab.strategies.adapters.biglotto_horizon_minimax import (
    BigLottoHorizonMinimaxDisagreementAdapter,
)
from lottolab.strategies.catalog import (
    DuplicateStrategyIdError,
    StrategyCatalog,
    UnknownStrategyError,
    production_catalog,
)
from lottolab.strategies.executable_registry import ExecutableRegistry, NotExecutableError


def make_descriptor(
    strategy_id: str,
    *,
    status: LifecycleStatus,
    executable: bool,
    adapter_path: str | None = None,
    min_history: int = 1,
) -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id=strategy_id,
        strategy_name=strategy_id,
        version="v0.1",
        lottery_types=(LotteryType.DAILY_539,),
        lifecycle_status=status,
        executable=executable,
        adapter_path=adapter_path,
        min_history=min_history,
    )


def test_duplicate_ids_rejected() -> None:
    first = make_descriptor("dup", status=LifecycleStatus.OBSERVATION, executable=False)
    with pytest.raises(DuplicateStrategyIdError):
        StrategyCatalog([first, first])


def test_only_online_may_be_executable() -> None:
    with pytest.raises(ValueError, match="iff lifecycle_status is ONLINE"):
        make_descriptor(
            "obs", status=LifecycleStatus.OBSERVATION, executable=True, adapter_path="x:y"
        )


def test_executable_requires_adapter_path() -> None:
    with pytest.raises(ValueError, match="requires adapter_path"):
        make_descriptor("online", status=LifecycleStatus.ONLINE, executable=True)


def test_online_status_requires_executable_descriptor() -> None:
    with pytest.raises(ValueError, match="iff lifecycle_status is ONLINE"):
        make_descriptor("online", status=LifecycleStatus.ONLINE, executable=False)


def test_non_executable_rejects_adapter_path() -> None:
    with pytest.raises(ValueError, match="cannot declare adapter_path"):
        make_descriptor(
            "obs",
            status=LifecycleStatus.OBSERVATION,
            executable=False,
            adapter_path="x:y",
        )


@pytest.mark.parametrize(
    ("strategy_id", "min_history", "message"),
    [("", 1, "strategy_id"), ("valid", 0, "min_history")],
)
def test_descriptor_rejects_invalid_identity_or_history(
    strategy_id: str, min_history: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        make_descriptor(
            strategy_id,
            status=LifecycleStatus.OBSERVATION,
            executable=False,
            min_history=min_history,
        )


def test_registry_never_loads_non_executable() -> None:
    catalog = StrategyCatalog(
        [make_descriptor("obs", status=LifecycleStatus.OBSERVATION, executable=False)]
    )
    registry = ExecutableRegistry(catalog)
    assert registry.executable_ids() == frozenset()
    with pytest.raises(NotExecutableError):
        registry.load_adapter("obs")


def test_list_filters_by_status_and_type() -> None:
    catalog = StrategyCatalog(
        [
            make_descriptor("obs", status=LifecycleStatus.OBSERVATION, executable=False),
            make_descriptor("retired", status=LifecycleStatus.RETIRED, executable=False),
        ]
    )
    listed = catalog.list(lifecycle_status=LifecycleStatus.OBSERVATION)
    assert [d.strategy_id for d in listed] == ["obs"]
    assert len(catalog.list(lottery_type=LotteryType.DAILY_539)) == 2


def test_list_order_deterministically_preserves_descriptor_declaration() -> None:
    catalog = StrategyCatalog(
        [
            make_descriptor("zeta", status=LifecycleStatus.RETIRED, executable=False),
            make_descriptor("alpha", status=LifecycleStatus.OBSERVATION, executable=False),
        ]
    )
    assert [descriptor.strategy_id for descriptor in catalog.list()] == ["zeta", "alpha"]
    assert [descriptor.strategy_id for descriptor in catalog] == ["zeta", "alpha"]


def test_unknown_strategy_behavior_is_explicit() -> None:
    catalog = StrategyCatalog(())
    registry = ExecutableRegistry(catalog)
    with pytest.raises(UnknownStrategyError, match="missing"):
        catalog.get("missing")
    with pytest.raises(UnknownStrategyError, match="missing"):
        registry.load_adapter("missing")


def test_production_catalog_invariants() -> None:
    """Holds for any future content: ids unique (by construction), and every
    executable descriptor must be loadable metadata-wise."""
    catalog = production_catalog()
    executable_ids = ExecutableRegistry(catalog).executable_ids()
    catalog_ids = {descriptor.strategy_id for descriptor in catalog}
    observation_ids = {
        descriptor.strategy_id
        for descriptor in catalog
        if descriptor.lifecycle_status is LifecycleStatus.OBSERVATION
    }

    assert executable_ids <= catalog_ids
    assert executable_ids.isdisjoint(observation_ids)
    for descriptor in catalog:
        assert descriptor.provenance
        assert descriptor.executable is (descriptor.lifecycle_status is LifecycleStatus.ONLINE)
        if descriptor.executable:
            assert descriptor.adapter_path, descriptor.strategy_id
        else:
            assert descriptor.adapter_path is None


def test_catalog_preserves_approved_strategy_append_order() -> None:
    catalog = production_catalog()
    ids = [descriptor.strategy_id for descriptor in catalog]
    assert ids == [
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
    ]
    online_ids = {
        descriptor.strategy_id
        for descriptor in catalog
        if descriptor.lifecycle_status is LifecycleStatus.ONLINE
    }
    assert online_ids == set(ids)
    assert ExecutableRegistry(catalog).executable_ids() == frozenset(ids)


def test_horizon_minimax_descriptor_and_adapter_identity_match_exactly() -> None:
    descriptor = production_catalog().get(
        BigLottoHorizonMinimaxDisagreementAdapter.strategy_id
    )
    assert (
        descriptor.strategy_id,
        descriptor.strategy_name,
        descriptor.version,
        descriptor.lottery_types,
        descriptor.min_history,
        descriptor.lifecycle_status,
        descriptor.executable,
        descriptor.adapter_path,
        descriptor.response_shape,
        descriptor.native_ticket_count,
    ) == (
        BigLottoHorizonMinimaxDisagreementAdapter.strategy_id,
        BigLottoHorizonMinimaxDisagreementAdapter.strategy_name,
        BigLottoHorizonMinimaxDisagreementAdapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        BigLottoHorizonMinimaxDisagreementAdapter.min_history,
        LifecycleStatus.ONLINE,
        True,
        "lottolab.strategies.adapters.biglotto_horizon_minimax:"
        "BigLottoHorizonMinimaxDisagreementAdapter",
        ResponseShape.PORTFOLIO,
        2,
    )


def test_zone_split_bet2_descriptor_and_adapter_identity_match_exactly() -> None:
    descriptor = production_catalog().get(BigLottoZoneSplit3BetBet2Adapter.strategy_id)
    assert (
        descriptor.strategy_id,
        descriptor.strategy_name,
        descriptor.version,
        descriptor.lottery_types,
        descriptor.min_history,
        descriptor.lifecycle_status,
        descriptor.executable,
        descriptor.adapter_path,
    ) == (
        BigLottoZoneSplit3BetBet2Adapter.strategy_id,
        BigLottoZoneSplit3BetBet2Adapter.strategy_name,
        BigLottoZoneSplit3BetBet2Adapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        BigLottoZoneSplit3BetBet2Adapter.min_history,
        LifecycleStatus.ONLINE,
        True,
        "lottolab.strategies.adapters.biglotto_selected:BigLottoZoneSplit3BetBet2Adapter",
    )
    assert descriptor.provenance == (
        "legacy_commit:24617fe3bb7ec087acf121f302bffd638ccfa179",
        "legacy_source:lottery_api/models/p541d_r2_biglotto_selected_adapters.py",
        "legacy_test:tests/test_p541d_r2_biglotto_selected_adapters.py",
        "migration_task:MATHSTATISTICALANALYSIS_BIGLOTTO_ZONE_SPLIT_3BET_BET2_LOCAL_IMPLEMENTATION_R1",
    )


def test_deviation_bet2_descriptor_registry_and_provenance_match_exactly() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(BigLottoDeviation2BetBet2Adapter.strategy_id)
    assert (
        descriptor.strategy_id,
        descriptor.strategy_name,
        descriptor.version,
        descriptor.lottery_types,
        descriptor.min_history,
        descriptor.lifecycle_status,
        descriptor.executable,
        descriptor.adapter_path,
    ) == (
        BigLottoDeviation2BetBet2Adapter.strategy_id,
        BigLottoDeviation2BetBet2Adapter.strategy_name,
        BigLottoDeviation2BetBet2Adapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        BigLottoDeviation2BetBet2Adapter.min_history,
        LifecycleStatus.ONLINE,
        True,
        "lottolab.strategies.adapters.biglotto_selected:"
        "BigLottoDeviation2BetBet2Adapter",
    )
    assert descriptor.provenance == (
        "legacy_commit:520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f",
        "legacy_source:tools/predict_biglotto_deviation_2bet.py",
        "legacy_symbol:deviation_complement_2bet",
        "target_producer:_deviation_complement_2bet",
        "output_index:1",
        "evidence_status:HISTORICAL_RESEARCH_ONLY",
        "current_significance:NOT_ESTABLISHED",
        "migration_task:"
        "MATHSTATISTICALANALYSIS_BIGLOTTO_DEVIATION_2BET_BET2_IMPLEMENT_AND_PUBLISH_R1",
    )
    assert (
        ExecutableRegistry(catalog).load_adapter(descriptor.strategy_id)
        is BigLottoDeviation2BetBet2Adapter
    )


def test_zone_split_bet3_descriptor_and_adapter_identity_match_exactly() -> None:
    descriptor = production_catalog().get(BigLottoZoneSplit3BetBet3Adapter.strategy_id)
    assert (
        descriptor.strategy_id,
        descriptor.strategy_name,
        descriptor.version,
        descriptor.lottery_types,
        descriptor.min_history,
        descriptor.lifecycle_status,
        descriptor.executable,
        descriptor.adapter_path,
    ) == (
        BigLottoZoneSplit3BetBet3Adapter.strategy_id,
        BigLottoZoneSplit3BetBet3Adapter.strategy_name,
        BigLottoZoneSplit3BetBet3Adapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        BigLottoZoneSplit3BetBet3Adapter.min_history,
        LifecycleStatus.ONLINE,
        True,
        "lottolab.strategies.adapters.biglotto_selected:BigLottoZoneSplit3BetBet3Adapter",
    )
    assert descriptor.provenance == (
        "legacy_commit:24617fe3bb7ec087acf121f302bffd638ccfa179",
        "legacy_source:lottery_api/models/p541d_r2_biglotto_selected_adapters.py",
        "legacy_test:tests/test_p541d_r2_biglotto_selected_adapters.py",
        "legacy_symbol:_zone_split_bets",
        "legacy_contract:P541D_R2",
        "evidence_status:HISTORICAL_RESEARCH_ONLY",
        "current_significance:NOT_ESTABLISHED",
        "migration_task:"
        "MATHSTATISTICALANALYSIS_BIGLOTTO_ZONE_SPLIT_3BET_BET3_IMPLEMENT_AND_PUBLISH_R1",
    )


def test_p0_bet1_descriptor_and_adapter_identity_match_exactly() -> None:
    descriptor = production_catalog().get(BigLottoP02BetBet1Adapter.strategy_id)
    assert (
        descriptor.strategy_id,
        descriptor.strategy_name,
        descriptor.version,
        descriptor.lottery_types,
        descriptor.min_history,
        descriptor.lifecycle_status,
        descriptor.executable,
        descriptor.adapter_path,
    ) == (
        BigLottoP02BetBet1Adapter.strategy_id,
        BigLottoP02BetBet1Adapter.strategy_name,
        BigLottoP02BetBet1Adapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        BigLottoP02BetBet1Adapter.min_history,
        LifecycleStatus.ONLINE,
        True,
        "lottolab.strategies.adapters.biglotto_selected:BigLottoP02BetBet1Adapter",
    )
    assert "evidence_status:HISTORICAL_RESEARCH_ONLY" in descriptor.provenance
    assert "current_significance:NOT_ESTABLISHED" in descriptor.provenance


def test_p0_bet2_descriptor_and_adapter_identity_match_exactly() -> None:
    descriptor = production_catalog().get(BigLottoP02BetBet2Adapter.strategy_id)
    assert (
        descriptor.strategy_id,
        descriptor.strategy_name,
        descriptor.version,
        descriptor.lottery_types,
        descriptor.min_history,
        descriptor.lifecycle_status,
        descriptor.executable,
        descriptor.adapter_path,
    ) == (
        BigLottoP02BetBet2Adapter.strategy_id,
        BigLottoP02BetBet2Adapter.strategy_name,
        BigLottoP02BetBet2Adapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        BigLottoP02BetBet2Adapter.min_history,
        LifecycleStatus.ONLINE,
        True,
        "lottolab.strategies.adapters.biglotto_selected:BigLottoP02BetBet2Adapter",
    )
    assert descriptor.provenance == (
        "legacy_commit:44a9067b73cc38fcd517673f5187e98080997aef",
        "legacy_source:tools/quick_predict.py",
        "legacy_source:recovered_strategies/biglotto/historical_adapters.py",
        "evidence_status:HISTORICAL_RESEARCH_ONLY",
        "current_significance:NOT_ESTABLISHED",
        "migration_task:MATHSTATISTICALANALYSIS_BIGLOTTO_P0_2BET_BET2_ADAPTER_MIGRATION_R1",
    )
