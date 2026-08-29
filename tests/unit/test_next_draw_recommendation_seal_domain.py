"""Unit contracts for the immutable Next-Draw Recommendation seal shape."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_recommendation import NATIVE_TICKET_COUNT_BUCKETS
from lottolab.domain.next_draw_recommendation_seal import (
    NextDrawRecommendationLifecycleState,
    NextDrawRecommendationSeal,
    NextDrawRecommendationSealContractError,
    NextDrawRecommendationSealTamperError,
    SealedRecommendationBucket,
    SealedStrategyTickets,
    TicketSealStatus,
)
from lottolab.domain.prospective_observer import ObservationTarget

TARGET = ObservationTarget(
    lottery_type=LotteryType.BIG_LOTTO, draw_number="115000090", draw_date=date(2099, 9, 1)
)
SCHEDULED_AT = datetime(2099, 9, 1, 8, 30, tzinfo=UTC)
SEALED_AT = datetime(2099, 8, 30, 10, 0, tzinfo=UTC)
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _sealed_ticket(rank: int = 1, strategy_id: str = "s1") -> SealedStrategyTickets:
    return SealedStrategyTickets(
        rank=rank,
        strategy_id=strategy_id,
        strategy_name="Strategy One",
        status=TicketSealStatus.OK,
        tickets=((1, 2, 3, 4, 5, 6),),
        detail="",
    )


def _buckets(*, with_ticket: bool = True) -> tuple[SealedRecommendationBucket, ...]:
    return tuple(
        SealedRecommendationBucket(
            native_ticket_count=count,
            availability="AVAILABLE",
            total_candidate_count=1,
            ranked_strategy_ids=("s1",),
            ranking_projection_sha256=SHA_C,
            sealed_tickets=(_sealed_ticket(),) if with_ticket else (),
        )
        for count in NATIVE_TICKET_COUNT_BUCKETS
    )


def _seal(**overrides: object) -> NextDrawRecommendationSeal:
    kwargs: dict[str, object] = {
        "target": TARGET,
        "target_scheduled_at": SCHEDULED_AT,
        "sealed_at": SEALED_AT,
        "target_registration_digest": SHA_A,
        "evidence_artifact_sha256": SHA_B,
        "causal_history_sha256": SHA_C,
        "causal_history_draw_count": 1889,
        "buckets": _buckets(),
    }
    kwargs.update(overrides)
    return NextDrawRecommendationSeal.create(**kwargs)  # type: ignore[arg-type]


def test_seal_round_trips_through_canonical_dict() -> None:
    seal = _seal()
    restored = NextDrawRecommendationSeal.from_canonical_dict(seal.canonical_dict())
    assert restored == seal
    assert restored.seal_digest == seal.seal_digest


def test_seal_self_verifies_and_rejects_tampered_content() -> None:
    seal = _seal()
    tampered = dict(seal.canonical_dict())
    tampered["causal_history_draw_count"] = seal.causal_history_draw_count + 1
    with pytest.raises(NextDrawRecommendationSealTamperError):
        NextDrawRecommendationSeal.from_canonical_dict(tampered)


def test_seal_rejects_a_hand_edited_digest_that_matches_nothing() -> None:
    seal = _seal()
    tampered = dict(seal.canonical_dict())
    tampered["seal_digest"] = "0" * 64
    with pytest.raises(NextDrawRecommendationSealTamperError):
        NextDrawRecommendationSeal.from_canonical_dict(tampered)


def test_seal_requires_sealing_strictly_before_the_scheduled_time() -> None:
    with pytest.raises(NextDrawRecommendationSealContractError):
        _seal(sealed_at=SCHEDULED_AT)
    with pytest.raises(NextDrawRecommendationSealContractError):
        _seal(sealed_at=datetime(2099, 9, 1, 9, 0, tzinfo=UTC))


def test_seal_requires_every_supported_bucket_exactly_once_in_order() -> None:
    with pytest.raises(NextDrawRecommendationSealContractError):
        _seal(buckets=_buckets()[:-1])

    reordered = tuple(reversed(_buckets()))
    with pytest.raises(NextDrawRecommendationSealContractError):
        _seal(buckets=reordered)


def test_seal_requires_ranking_policy_id_to_match_the_frozen_policy() -> None:
    seal = _seal()
    tampered = dict(seal.canonical_dict())
    tampered["ranking_policy_id"] = "SOME_OTHER_POLICY"
    with pytest.raises(NextDrawRecommendationSealContractError):
        NextDrawRecommendationSeal.from_canonical_dict(tampered)


def test_bucket_rejects_sealed_tickets_outside_the_ranked_prefix() -> None:
    with pytest.raises(NextDrawRecommendationSealContractError):
        SealedRecommendationBucket(
            native_ticket_count=1,
            availability="AVAILABLE",
            total_candidate_count=2,
            ranked_strategy_ids=("s1", "s2"),
            ranking_projection_sha256=SHA_C,
            sealed_tickets=(_sealed_ticket(rank=1, strategy_id="s2"),),
        )


def test_bucket_rejects_non_contiguous_sealed_ticket_ranks() -> None:
    with pytest.raises(NextDrawRecommendationSealContractError):
        SealedRecommendationBucket(
            native_ticket_count=1,
            availability="AVAILABLE",
            total_candidate_count=2,
            ranked_strategy_ids=("s1", "s2"),
            ranking_projection_sha256=SHA_C,
            sealed_tickets=(_sealed_ticket(rank=2, strategy_id="s1"),),
        )


def test_sealed_strategy_tickets_status_and_ticket_presence_must_agree() -> None:
    with pytest.raises(NextDrawRecommendationSealContractError):
        SealedStrategyTickets(
            rank=1,
            strategy_id="s1",
            strategy_name="Strategy One",
            status=TicketSealStatus.OK,
            tickets=(),
            detail="",
        )
    with pytest.raises(NextDrawRecommendationSealContractError):
        SealedStrategyTickets(
            rank=1,
            strategy_id="s1",
            strategy_name="Strategy One",
            status=TicketSealStatus.DECLINED,
            tickets=((1, 2, 3),),
            detail="",
        )


def test_matches_frozen_inputs_ignores_sealed_at_and_generated_buckets() -> None:
    seal = _seal()
    # A later attempt with a different sealed_at and different bucket content
    # (as a non-reproducible strategy legitimately could produce) must still
    # be recognized as the same frozen prediction event.
    other = _seal(
        sealed_at=datetime(2099, 8, 30, 11, 0, tzinfo=UTC), buckets=_buckets(with_ticket=False)
    )
    assert seal.seal_digest != other.seal_digest
    assert seal.matches_frozen_inputs(
        target=other.target,
        target_scheduled_at=other.target_scheduled_at,
        target_registration_digest=other.target_registration_digest,
        evidence_artifact_sha256=other.evidence_artifact_sha256,
        causal_history_sha256=other.causal_history_sha256,
        causal_history_draw_count=other.causal_history_draw_count,
    )


def test_matches_frozen_inputs_rejects_a_different_evidence_hash() -> None:
    seal = _seal()
    assert not seal.matches_frozen_inputs(
        target=seal.target,
        target_scheduled_at=seal.target_scheduled_at,
        target_registration_digest=seal.target_registration_digest,
        evidence_artifact_sha256="f" * 64,
        causal_history_sha256=seal.causal_history_sha256,
        causal_history_draw_count=seal.causal_history_draw_count,
    )


def test_bucket_lookup_helper_finds_the_exact_native_ticket_count() -> None:
    seal = _seal()
    found = seal.bucket(5)
    assert found is not None
    assert found.native_ticket_count == 5
    assert seal.bucket(4) is None


def test_lifecycle_state_enum_names_are_exact() -> None:
    assert {member.value for member in NextDrawRecommendationLifecycleState} == {
        "WAITING_FOR_ELIGIBLE_TARGET",
        "TARGET_AVAILABLE",
        "PREDICTIONS_SEALED",
        "OUTCOME_AVAILABLE",
    }
