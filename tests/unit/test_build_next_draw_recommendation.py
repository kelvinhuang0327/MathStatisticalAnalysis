"""Use-case coverage for composing one Next-Draw Recommendation bucket (P1)."""

from __future__ import annotations

from fractions import Fraction

from lottolab.application.use_cases.build_next_draw_recommendation import (
    BuildNextDrawRecommendationBucket,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_recommendation import (
    BucketAvailabilityStatus,
    RecommendationExclusionReason,
)
from lottolab.domain.strategies import LifecycleStatus, ResponseShape, StrategyDescriptor
from lottolab.evidence.next_draw_recommendation_evidence import (
    NextDrawRecommendationEvidenceArtifact,
    RecommendationEvidenceStrategyRecord,
    RecommendationEvidenceWindow,
    StrategyBacktestStatus,
)
from lottolab.strategies.catalog import StrategyCatalog


def _descriptor(strategy_id: str, *, native_ticket_count: int = 2) -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id=strategy_id,
        strategy_name=strategy_id,
        version="v1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path="lottolab.strategies.adapters.fake:FakeAdapter",
        native_ticket_count=native_ticket_count,
        response_shape=ResponseShape.PORTFOLIO,
    )


def _window(observed: Fraction, baseline: Fraction) -> RecommendationEvidenceWindow:
    return RecommendationEvidenceWindow(
        window_kind="WINDOW_750",
        window_status="COMPLETE",
        eligible_draw_count=750,
        observed_value=observed,
        random_reference=baseline,
        delta_vs_random=observed - baseline,
    )


def _evidence(records: tuple[RecommendationEvidenceStrategyRecord, ...]) -> NextDrawRecommendationEvidenceArtifact:
    return NextDrawRecommendationEvidenceArtifact.build(
        lottery_type="BIG_LOTTO",
        source_draw_db_sha256="a" * 64,
        source_draw_count=2164,
        last_causal_draw_id="115000082",
        replay_depth=800,
        hit_tier_id="M3_PLUS",
        records=records,
    )


def test_strategy_with_no_evidence_record_is_excluded_as_evidence_unavailable() -> None:
    catalog = StrategyCatalog([_descriptor("s1")])
    evidence = _evidence(())
    view = BuildNextDrawRecommendationBucket(catalog=catalog, evidence=evidence).execute(
        lottery_type=LotteryType.BIG_LOTTO, native_ticket_count=2
    )
    assert view.availability is BucketAvailabilityStatus.LIMITED_POOL
    assert view.total_candidate_count == 1
    assert len(view.ranked) == 0
    assert len(view.excluded) == 1
    assert view.excluded[0].reason is RecommendationExclusionReason.EVIDENCE_UNAVAILABLE


def test_strategy_with_unreachable_backtest_status_is_excluded() -> None:
    catalog = StrategyCatalog([_descriptor("s1")])
    record = RecommendationEvidenceStrategyRecord(
        strategy_id="s1",
        strategy_name="s1",
        native_ticket_count=2,
        status=StrategyBacktestStatus.DRIVER_ERROR,
        hit_tier_id="M3_PLUS",
        windows=(),
    )
    view = BuildNextDrawRecommendationBucket(catalog=catalog, evidence=_evidence((record,))).execute(
        lottery_type=LotteryType.BIG_LOTTO, native_ticket_count=2
    )
    assert len(view.excluded) == 1
    assert view.excluded[0].reason is RecommendationExclusionReason.EXECUTION_UNREACHABLE


def test_evaluated_strategies_are_ranked_by_the_domain_rule() -> None:
    catalog = StrategyCatalog([_descriptor("winner"), _descriptor("loser")])
    winner = RecommendationEvidenceStrategyRecord(
        strategy_id="winner", strategy_name="Winner", native_ticket_count=2,
        status=StrategyBacktestStatus.EVALUATED, hit_tier_id="M3_PLUS",
        windows=(_window(Fraction(2, 10), Fraction(1, 12)),),
    )
    loser = RecommendationEvidenceStrategyRecord(
        strategy_id="loser", strategy_name="Loser", native_ticket_count=2,
        status=StrategyBacktestStatus.EVALUATED, hit_tier_id="M3_PLUS",
        windows=(_window(Fraction(1, 10), Fraction(1, 12)),),
    )
    view = BuildNextDrawRecommendationBucket(
        catalog=catalog, evidence=_evidence((winner, loser))
    ).execute(lottery_type=LotteryType.BIG_LOTTO, native_ticket_count=2)
    assert view.availability is BucketAvailabilityStatus.LIMITED_POOL
    assert [c.strategy_id for c in view.ranked] == ["winner", "loser"]
    assert view.ranked[0].rank == 1
    assert view.ranked[0].windows[0].delta_vs_random == Fraction(2, 10) - Fraction(1, 12)


def test_wrong_lottery_type_or_ticket_count_never_enters_the_bucket() -> None:
    catalog = StrategyCatalog([
        _descriptor("wrong_count", native_ticket_count=3),
        _descriptor("right_count", native_ticket_count=2),
    ])
    right = RecommendationEvidenceStrategyRecord(
        strategy_id="right_count", strategy_name="Right", native_ticket_count=2,
        status=StrategyBacktestStatus.EVALUATED, hit_tier_id="M3_PLUS",
        windows=(_window(Fraction(1, 10), Fraction(1, 12)),),
    )
    view = BuildNextDrawRecommendationBucket(catalog=catalog, evidence=_evidence((right,))).execute(
        lottery_type=LotteryType.BIG_LOTTO, native_ticket_count=2
    )
    assert view.total_candidate_count == 1
    assert [c.strategy_id for c in view.ranked] == ["right_count"]


def test_unavailable_bucket_has_no_candidates_at_all() -> None:
    catalog = StrategyCatalog([_descriptor("only_2bet", native_ticket_count=2)])
    view = BuildNextDrawRecommendationBucket(catalog=catalog, evidence=_evidence(())).execute(
        lottery_type=LotteryType.BIG_LOTTO, native_ticket_count=20
    )
    assert view.availability is BucketAvailabilityStatus.UNAVAILABLE
    assert view.total_candidate_count == 0
