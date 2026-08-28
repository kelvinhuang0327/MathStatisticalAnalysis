"""Coverage for the Next-Draw Recommendation evidence artifact (LCJ-1)."""

from __future__ import annotations

import dataclasses
from fractions import Fraction

import pytest

from lottolab.evidence.next_draw_recommendation_evidence import (
    ComputationStatus,
    NextDrawRecommendationEvidenceArtifact,
    RecommendationEvidenceArtifactTamperError,
    RecommendationEvidenceStrategyRecord,
    RecommendationEvidenceWindow,
    StrategyBacktestStatus,
)


def _window(kind: str, *, observed: Fraction, baseline: Fraction) -> RecommendationEvidenceWindow:
    return RecommendationEvidenceWindow(
        window_kind=kind,
        window_status="COMPLETE",
        eligible_draw_count=750,
        observed_value=observed,
        random_reference=baseline,
        delta_vs_random=observed - baseline,
    )


def _artifact() -> NextDrawRecommendationEvidenceArtifact:
    record = RecommendationEvidenceStrategyRecord(
        strategy_id="s1",
        strategy_name="Strategy One",
        native_ticket_count=2,
        status=StrategyBacktestStatus.EVALUATED,
        hit_tier_id="M3_PLUS",
        windows=(_window("WINDOW_750", observed=Fraction(1, 20), baseline=Fraction(1, 27)),),
    )
    return NextDrawRecommendationEvidenceArtifact.build(
        lottery_type="BIG_LOTTO",
        source_draw_db_sha256="a" * 64,
        source_draw_count=2164,
        last_causal_draw_id="115000082",
        replay_depth=800,
        hit_tier_id="M3_PLUS",
        records=(record,),
    )


def test_build_produces_a_verifiable_hash() -> None:
    artifact = _artifact()
    assert len(artifact.artifact_sha256) == 64
    assert artifact.computation_status is ComputationStatus.FRESH_UNREVIEWED


def test_round_trip_through_canonical_dict() -> None:
    artifact = _artifact()
    restored = NextDrawRecommendationEvidenceArtifact.from_canonical_dict(artifact.canonical_dict())
    assert restored == artifact


def test_tampering_is_detected_at_construction_time() -> None:
    # A frozen artifact re-derives and checks its own hash in __post_init__,
    # so even an in-process dataclasses.replace() is caught immediately --
    # there is no way to hold a tampered instance at all.
    artifact = _artifact()
    with pytest.raises(RecommendationEvidenceArtifactTamperError):
        dataclasses.replace(artifact, source_draw_count=artifact.source_draw_count + 1)


def test_tampering_a_serialized_payload_is_detected_on_reload() -> None:
    artifact = _artifact()
    payload = dict(artifact.canonical_dict())
    payload["source_draw_count"] = artifact.source_draw_count + 1
    with pytest.raises(RecommendationEvidenceArtifactTamperError):
        NextDrawRecommendationEvidenceArtifact.from_canonical_dict(payload)


def test_large_portfolio_denominators_survive_round_trip() -> None:
    # comb(49, 6) ** 10-scale denominators exceed the LCJ-1 safe-integer bound
    # as raw JSON integers; they must round-trip exactly as decimal strings.
    huge_denominator = 13_983_816**8
    window = _window(
        "WINDOW_750",
        observed=Fraction(1, 10),
        baseline=Fraction(1, huge_denominator),
    )
    record = RecommendationEvidenceStrategyRecord(
        strategy_id="s-huge",
        strategy_name="Ten Ticket Strategy",
        native_ticket_count=10,
        status=StrategyBacktestStatus.EVALUATED,
        hit_tier_id="M3_PLUS",
        windows=(window,),
    )
    artifact = NextDrawRecommendationEvidenceArtifact.build(
        lottery_type="BIG_LOTTO",
        source_draw_db_sha256="b" * 64,
        source_draw_count=2164,
        last_causal_draw_id="115000082",
        replay_depth=800,
        hit_tier_id="M3_PLUS",
        records=(record,),
    )
    restored = NextDrawRecommendationEvidenceArtifact.from_canonical_dict(artifact.canonical_dict())
    assert restored.records[0].windows[0].random_reference == Fraction(1, huge_denominator)


def test_non_evaluated_record_carries_no_windows() -> None:
    record = RecommendationEvidenceStrategyRecord(
        strategy_id="s2",
        strategy_name="Not Reachable",
        native_ticket_count=3,
        status=StrategyBacktestStatus.NOT_ABC_COMPLIANT,
        hit_tier_id="M3_PLUS",
        windows=(),
    )
    artifact = NextDrawRecommendationEvidenceArtifact.build(
        lottery_type="BIG_LOTTO",
        source_draw_db_sha256="c" * 64,
        source_draw_count=2164,
        last_causal_draw_id="115000082",
        replay_depth=800,
        hit_tier_id="M3_PLUS",
        records=(record,),
    )
    assert artifact.records[0].status is StrategyBacktestStatus.NOT_ABC_COMPLIANT
    assert artifact.records[0].windows == ()
