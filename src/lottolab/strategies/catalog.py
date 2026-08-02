"""Read-only strategy catalog: metadata lookup without importing adapters."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape, StrategyDescriptor


class DuplicateStrategyIdError(ValueError):
    pass


class UnknownStrategyError(KeyError):
    pass


class StrategyCatalog:
    def __init__(self, descriptors: Iterable[StrategyDescriptor]) -> None:
        self._by_id: dict[str, StrategyDescriptor] = {}
        for descriptor in descriptors:
            if descriptor.strategy_id in self._by_id:
                raise DuplicateStrategyIdError(descriptor.strategy_id)
            self._by_id[descriptor.strategy_id] = descriptor

    def __iter__(self) -> Iterator[StrategyDescriptor]:
        return iter(self.list())

    def __len__(self) -> int:
        return len(self._by_id)

    def get(self, strategy_id: str) -> StrategyDescriptor:
        try:
            return self._by_id[strategy_id]
        except KeyError as exc:
            raise UnknownStrategyError(strategy_id) from exc

    def list(
        self,
        *,
        lottery_type: LotteryType | None = None,
        lifecycle_status: LifecycleStatus | None = None,
    ) -> tuple[StrategyDescriptor, ...]:
        """Return matches in the descriptor declaration order pinned by provenance."""
        return tuple(
            descriptor
            for descriptor in self._by_id.values()
            if (lottery_type is None or lottery_type in descriptor.lottery_types)
            and (lifecycle_status is None or descriptor.lifecycle_status is lifecycle_status)
        )


_PRODUCTION_DESCRIPTORS = (
    StrategyDescriptor(
        strategy_id="biglotto_social_wisdom_anti_popularity",
        strategy_name="大樂透 Social Wisdom Anti-Popularity",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_selected:"
            "BigLottoSocialWisdomAntiPopularityAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f",
            "legacy_source:lottery_api/models/replay_strategy_registry.py",
            "legacy_task:P541F_R2",
            "legacy_pr:690",
            "migration_task:P600B_R2",
            "migration_task:P602B",
        ),
    ),
    StrategyDescriptor(
        strategy_id="biglotto_zone_split_3bet_bet1",
        strategy_name="大樂透 Zone Split 3注（Replay Bet 1）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_selected:BigLottoZoneSplit3BetBet1Adapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f",
            "legacy_source:lottery_api/models/replay_strategy_registry.py",
            "legacy_task:P541F_R2",
            "legacy_pr:690",
            "migration_task:P600B_R2",
            "migration_task:P602B",
        ),
    ),
    StrategyDescriptor(
        strategy_id="biglotto_zone_split_3bet_bet2",
        strategy_name="大樂透 Zone Split 3注（Replay Bet 2）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_selected:BigLottoZoneSplit3BetBet2Adapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:24617fe3bb7ec087acf121f302bffd638ccfa179",
            "legacy_source:lottery_api/models/p541d_r2_biglotto_selected_adapters.py",
            "legacy_test:tests/test_p541d_r2_biglotto_selected_adapters.py",
            "migration_task:MATHSTATISTICALANALYSIS_BIGLOTTO_ZONE_SPLIT_3BET_BET2_LOCAL_IMPLEMENTATION_R1",
        ),
    ),
    StrategyDescriptor(
        strategy_id="biglotto_zone_split_3bet_bet3",
        strategy_name="大樂透 Zone Split 3注（Replay Bet 3）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_selected:BigLottoZoneSplit3BetBet3Adapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:24617fe3bb7ec087acf121f302bffd638ccfa179",
            "legacy_source:lottery_api/models/p541d_r2_biglotto_selected_adapters.py",
            "legacy_test:tests/test_p541d_r2_biglotto_selected_adapters.py",
            "legacy_symbol:_zone_split_bets",
            "legacy_contract:P541D_R2",
            "evidence_status:HISTORICAL_RESEARCH_ONLY",
            "current_significance:NOT_ESTABLISHED",
            "migration_task:"
            "MATHSTATISTICALANALYSIS_BIGLOTTO_ZONE_SPLIT_3BET_BET3_IMPLEMENT_AND_PUBLISH_R1",
        ),
    ),
    StrategyDescriptor(
        strategy_id="biglotto_deviation_2bet",
        strategy_name="大樂透 Deviation 2注",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_selected:BigLottoDeviation2BetAdapter"
        ),
        min_history=100,
        provenance=(
            "legacy_commit:520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f",
            "legacy_source:lottery_api/models/replay_strategy_registry.py",
            "legacy_source:tools/predict_biglotto_deviation_2bet.py",
            "migration_task:P603A",
        ),
    ),
    StrategyDescriptor(
        strategy_id="biglotto_deviation_2bet_bet2",
        strategy_name="大樂透 Deviation 2注（Cold Bet 2）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_selected:"
            "BigLottoDeviation2BetBet2Adapter"
        ),
        min_history=100,
        provenance=(
            "legacy_commit:520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f",
            "legacy_source:tools/predict_biglotto_deviation_2bet.py",
            "legacy_symbol:deviation_complement_2bet",
            "target_producer:_deviation_complement_2bet",
            "output_index:1",
            "evidence_status:HISTORICAL_RESEARCH_ONLY",
            "current_significance:NOT_ESTABLISHED",
            "migration_task:"
            "MATHSTATISTICALANALYSIS_BIGLOTTO_DEVIATION_2BET_BET2_IMPLEMENT_AND_PUBLISH_R1",
        ),
    ),
    StrategyDescriptor(
        strategy_id="biglotto_p0_2bet_bet1",
        strategy_name="大樂透 P0 2注（Hot+Echo Bet 1）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_selected:BigLottoP02BetBet1Adapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:44a9067b73cc38fcd517673f5187e98080997aef",
            "legacy_source:tools/quick_predict.py",
            "legacy_source:recovered_strategies/biglotto/historical_adapters.py",
            "evidence_status:HISTORICAL_RESEARCH_ONLY",
            "current_significance:NOT_ESTABLISHED",
            "migration_task:MATHSTATISTICALANALYSIS_BIGLOTTO_P0_2BET_BET1_ADAPTER_MIGRATION_R1",
        ),
    ),
    StrategyDescriptor(
        strategy_id="biglotto_p0_2bet_bet2",
        strategy_name="大樂透 P0 2注（Cold Bet 2）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_selected:BigLottoP02BetBet2Adapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:44a9067b73cc38fcd517673f5187e98080997aef",
            "legacy_source:tools/quick_predict.py",
            "legacy_source:recovered_strategies/biglotto/historical_adapters.py",
            "evidence_status:HISTORICAL_RESEARCH_ONLY",
            "current_significance:NOT_ESTABLISHED",
            "migration_task:MATHSTATISTICALANALYSIS_BIGLOTTO_P0_2BET_BET2_ADAPTER_MIGRATION_R1",
        ),
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__graph_predictor__cd70713a5709",
        strategy_name="大樂透 Co-occurrence Graph (PageRank + Clique)",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave1:BigLottoGraphPredictorAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:ai_lab/scripts/graph_predictor.py",
            "full_strategy_catalog_id:legacy_biglotto__graph_predictor__cd70713a5709",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE1_R1",
        ),
        response_shape=ResponseShape.SINGLE_TICKET,
        native_ticket_count=1,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__backtest_must_hit__909c91fd2fd0",
        strategy_name="大樂透 Must-Hit Top6（近50期最頻繁）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave1:BigLottoMustHitTop6Adapter"
        ),
        min_history=50,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/backtest_must_hit.py",
            "legacy_symbol:predict_must_hit",
            "full_strategy_catalog_id:legacy_biglotto__backtest_must_hit__909c91fd2fd0",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE1_R1",
        ),
        response_shape=ResponseShape.SINGLE_TICKET,
        native_ticket_count=1,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac",
        strategy_name="大樂透 Dynamic Frequency（自動選窗）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave1:BigLottoDynamicFrequencyAdapter"
        ),
        min_history=200,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/dynamic_frequency_predictor.py",
            "full_strategy_catalog_id:"
            "legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE1_R1",
        ),
        response_shape=ResponseShape.SINGLE_TICKET,
        native_ticket_count=1,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee",
        strategy_name="大樂透 Hot Co-occurrence Analyzer",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave1:BigLottoHotCooccurrenceAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/hot_cooccurrence_analyzer.py",
            "legacy_symbol:analyze_and_recommend",
            "full_strategy_catalog_id:"
            "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE1_R1",
        ),
        response_shape=ResponseShape.SINGLE_TICKET,
        native_ticket_count=1,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4",
        strategy_name="大樂透 Echo-Aware Phase 2（自適應權重，2注+3注）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave1:BigLottoEchoPhase2Adapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/predict_biglotto_echo_phase2.py",
            "legacy_source:tools/predict_biglotto_echo_2bet.py",
            "legacy_source:tools/predict_biglotto_echo_3bet.py",
            "legacy_symbol:phase2_echo_2bet",
            "legacy_symbol:phase2_echo_3bet",
            "full_strategy_catalog_id:"
            "legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE1_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=5,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__high_prize_trend_optimizer__0fc72409150e",
        strategy_name="大樂透 High Prize Trend（7組Lambda衰減）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave2:BigLottoHighPrizeTrendAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:ai_lab/scripts/high_prize_trend_optimizer.py",
            "legacy_symbol:HighPrizeTrendOptimizer.predict",
            "full_strategy_catalog_id:"
            "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE2_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=7,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__core_satellite__2e82891003b3",
        strategy_name="大樂透 Core-Satellite（4模式x3注）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave2:BigLottoCoreSatelliteAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:lottery_api/engine/core_satellite.py",
            "legacy_symbol:CoreSatelliteGenerator.generate_from_history",
            "full_strategy_catalog_id:legacy_biglotto__core_satellite__2e82891003b3",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE2_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=12,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__auto_discovery_biglotto__06bcb164db84",
        strategy_name="大樂透 Auto-Discovery（6維度x54組態）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave2:BigLottoAutoDiscoveryAdapter"
        ),
        min_history=50,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/auto_discovery_biglotto.py",
            "legacy_symbol:build_methods",
            "full_strategy_catalog_id:"
            "legacy_biglotto__auto_discovery_biglotto__06bcb164db84",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE2_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=54,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__biglotto_2bet_final__7eaedb330a07",
        strategy_name="大樂透 雙注優化 V3 最終版（Top15+大號加強）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=("lottolab.strategies.adapters.biglotto_wave3:BigLottoTwoBetFinalAdapter"),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:lottery_api/models/biglotto_2bet_final.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_symbol:BigLotto2BetOptimizerV3.predict_2bets_final",
            "full_strategy_catalog_id:legacy_biglotto__biglotto_2bet_final__7eaedb330a07",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE3_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=2,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876",
        strategy_name="大樂透 雙注覆蓋優化",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave3:BigLottoTwoBetOptimizerAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:lottery_api/models/biglotto_2bet_optimizer.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_symbol:BigLotto2BetOptimizer.predict_2bets",
            "full_strategy_catalog_id:legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE3_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=2,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3",
        strategy_name="大樂透 雙注覆蓋優化 V2",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave3:BigLottoTwoBetOptimizerV2Adapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:lottery_api/models/biglotto_2bet_optimizer_v2.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_symbol:BigLotto2BetOptimizerV2.predict_2bets_optimized",
            "full_strategy_catalog_id:legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE3_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=2,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5",
        strategy_name="大樂透三注智能組合預測器",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave4:BigLottoThreeBetOptimizerAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:lottery_api/models/biglotto_3bet_optimizer.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_source:tools/negative_selector.py",
            "legacy_symbol:BigLotto3BetOptimizer.predict_3bets_diversified",
            "full_strategy_catalog_id:legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE4_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=3,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad",
        strategy_name="大樂透 TME 4注智能組合預測器",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=("lottolab.strategies.adapters.biglotto_wave4:BigLottoTMEOptimizerAdapter"),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:lottery_api/models/biglotto_tme_optimizer.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_symbol:BigLottoTMEOptimizer.predict_4bets",
            "full_strategy_catalog_id:legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE4_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=4,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__optimized_ensemble__e05e0fde22d7",
        strategy_name="ROI 優化集成預測器",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave4:BigLottoOptimizedEnsembleAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:lottery_api/models/optimized_ensemble.py",
            "legacy_symbol:OptimizedEnsemblePredictor.predict",
            "full_strategy_catalog_id:legacy_biglotto__optimized_ensemble__e05e0fde22d7",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE4_R1",
        ),
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511",
        strategy_name="大樂透兩注精選預測器",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave4:BigLottoTwoBetElitePredictorAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/predict_biglotto_115000007_2bets.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_source:tools/negative_selector.py",
            "legacy_symbol:BigLotto2BetOptimizer.predict_2bets",
            "full_strategy_catalog_id:"
            "legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE4_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=2,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__predict_biglotto_6bets_cluster__1fd9e8a7ae2a",
        strategy_name="大樂透 Cluster Pivot 6注",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=("lottolab.strategies.adapters.biglotto_wave5:BigLottoSixBetClusterAdapter"),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/predict_biglotto_6bets_cluster.py",
            "legacy_source_sha256:1fd9e8a7ae2ae9f19b97cb68cde009bce3962d8344a24f9bf07e15cc803abde3",
            "legacy_symbol:BigLottoClusterPivotPredictor.generate_bets",
            "full_strategy_catalog_id:"
            "legacy_biglotto__predict_biglotto_6bets_cluster__1fd9e8a7ae2a",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE5_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=6,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__predict_biglotto_7bets_cluster__8f55b5d94669",
        strategy_name="大樂透 Cluster Pivot 7注",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=("lottolab.strategies.adapters.biglotto_wave5:BigLottoSevenBetClusterAdapter"),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/predict_biglotto_7bets_cluster.py",
            "legacy_source_sha256:8f55b5d94669543524eef58d65598213097357925a8f982c84ae7614fa85a735",
            "legacy_symbol:BigLottoClusterPivotPredictor.generate_bets",
            "full_strategy_catalog_id:"
            "legacy_biglotto__predict_biglotto_7bets_cluster__8f55b5d94669",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE5_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=7,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__predict_biglotto_echo_2bet__59c20b25b1fa",
        strategy_name="大樂透 Echo-Aware 偏差互補 2注",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=("lottolab.strategies.adapters.biglotto_wave5:BigLottoEchoTwoBetAdapter"),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/predict_biglotto_echo_2bet.py",
            "legacy_source_sha256:59c20b25b1fa59ef9edad2a6a6c031321bfbafea7752351c692ab5cfa2fa6620",
            "legacy_symbol:echo_aware_deviation_2bet",
            "full_strategy_catalog_id:legacy_biglotto__predict_biglotto_echo_2bet__59c20b25b1fa",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE5_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=2,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__predict_biglotto_elite7__eb46a9856446",
        strategy_name="大樂透 Elite-7 優化預測",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=("lottolab.strategies.adapters.biglotto_wave5:BigLottoEliteSevenAdapter"),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/predict_biglotto_elite7.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_source_sha256:eb46a985644626a796640ef0fd9913c340f4c9780a694824029f5083ed1b833a",
            "legacy_symbol:predict_7bet_optimized",
            "full_strategy_catalog_id:legacy_biglotto__predict_biglotto_elite7__eb46a9856446",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE5_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=7,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__research_variant_history__149648f9fffc",
        strategy_name="大樂透歷史窗口 11 變體研究組合",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=("lottolab.strategies.adapters.biglotto_wave5:BigLottoVariantHistoryAdapter"),
        min_history=20,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/research_variant_history.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_source_sha256:149648f9fffcd0e6e9b5f89c2ab58ce5c1171ad75a5b7ed9f336469e710e8d68",
            "legacy_symbol:analyze_variants",
            "full_strategy_catalog_id:legacy_biglotto__research_variant_history__149648f9fffc",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE5_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=11,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__auto_optimizer_alpha__7eaa9572e384",
        strategy_name="大樂透 Auto Optimizer Alpha（5方法×5窗口）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave6:"
            "BigLottoAutoOptimizerAlphaAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/auto_optimizer_alpha.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_source_sha256:"
            "7eaa9572e3848fdf8fbcb66dbade25f653bf25a7fe7c4be95b6e9d2f8df1d61d",
            "legacy_symbol:AutoOptimizer.generate_strategy_space",
            "full_strategy_catalog_id:"
            "legacy_biglotto__auto_optimizer_alpha__7eaa9572e384",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE6_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=25,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__backtest_10bet_biglotto__054e85b088be",
        strategy_name="大樂透 10注 Unified＋EWMA 回測組合",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave6:"
            "BigLottoTenBetBacktestAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/backtest_10bet_biglotto.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_source_sha256:"
            "054e85b088bec0827318b2442255dee961fa3e9ca8b08b87cc2d5b4cfcb669f2",
            "legacy_symbol:main",
            "full_strategy_catalog_id:"
            "legacy_biglotto__backtest_10bet_biglotto__054e85b088be",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE6_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=10,
    ),
    StrategyDescriptor(
        strategy_id="legacy_biglotto__test_tme__f3bb5106dfe3",
        strategy_name="大樂透 TME 三方法獨立組合",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave6:"
            "BigLottoTmeThreeAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/test_tme.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_source_sha256:"
            "f3bb5106dfe3f255bc84317169fb5fbafa653a97c2977b66cb12a49eab07891c",
            "legacy_symbol:TMEOptimizer.predict_3bets_tme",
            "full_strategy_catalog_id:legacy_biglotto__test_tme__f3bb5106dfe3",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE6_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=3,
    ),
    StrategyDescriptor(
        strategy_id=(
            "legacy_biglotto__verify_gemini_2bet_claim__d5ca233aa776"
        ),
        strategy_name="大樂透 Gemini V1 雙注驗證組合",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave6:"
            "BigLottoGeminiTwoBetVerifierAdapter"
        ),
        min_history=50,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/verify_gemini_2bet_claim.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_source_sha256:"
            "d5ca233aa776d257c12b0f07e6d68205c5126b05759c39cf00e8ce8314062df3",
            "legacy_symbol:generate_2bet_v1",
            "full_strategy_catalog_id:"
            "legacy_biglotto__verify_gemini_2bet_claim__d5ca233aa776",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE6_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=2,
    ),
    StrategyDescriptor(
        strategy_id=(
            "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd"
        ),
        strategy_name="大樂透 5ME 五方法獨立組合",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave7:"
            "BigLottoFiveMeAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/predict_5me_115000004.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_source_sha256:"
            "8a1c06ce1bddb2ab605ad00e95503d1f6bea35b102ad5c39559eb1cf4c5e5782",
            "legacy_symbol:main",
            "full_strategy_catalog_id:"
            "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE7_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=5,
    ),
    StrategyDescriptor(
        strategy_id=(
            "legacy_biglotto__predict_big_lotto_smart_2bet__7acdaab1bd0a"
        ),
        strategy_name="大樂透 Smart 2-Bet 頻率偏差互補組合",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave7:"
            "BigLottoSmartTwoBetAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/predict_big_lotto_smart_2bet.py",
            "legacy_source:lottery_api/models/unified_predictor.py",
            "legacy_source_sha256:"
            "7acdaab1bd0afea2dd270e225335c25ccdb26594ce788902f2752b5e41801ede",
            "legacy_symbol:main",
            "full_strategy_catalog_id:"
            "legacy_biglotto__predict_big_lotto_smart_2bet__7acdaab1bd0a",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE7_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=2,
    ),
    StrategyDescriptor(
        strategy_id=(
            "legacy_biglotto__verify_gemini_phase2_claim__6407a8f39519"
        ),
        strategy_name="大樂透 Gemini Phase 2 七方法驗證組合",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_wave7:"
            "BigLottoGeminiPhaseTwoVerifierAdapter"
        ),
        min_history=100,
        provenance=(
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
            "legacy_source:tools/verify_gemini_phase2_claim.py",
            "legacy_source_sha256:"
            "6407a8f3951913fcd2de6b98046305defd377739e67d7f37b53884f81964b480",
            "legacy_symbol:generate_7_bets",
            "full_strategy_catalog_id:"
            "legacy_biglotto__verify_gemini_phase2_claim__6407a8f39519",
            "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE7_R1",
        ),
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=7,
    ),
)


def production_catalog() -> StrategyCatalog:
    """Return metadata in the pinned legacy descriptor declaration order."""
    return StrategyCatalog(_PRODUCTION_DESCRIPTORS)
