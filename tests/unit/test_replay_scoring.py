"""Domain invariants for immutable Replay prize-scoring contracts."""

from __future__ import annotations

from datetime import date

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    BigLottoPrizeTier,
    BigLottoPrizeTierId,
    NoPrizeResult,
    resolve_big_lotto_prize_tier,
)
from lottolab.domain.replay_scoring import (
    SCORING_SCHEMA_VERSION,
    ReplayScoredPrediction,
    ReplayScoringReason,
    ReplayScoringStatus,
    ReplayTargetOutcome,
    recompute_scored_result_sha256,
)

_SOURCE_ARTIFACT_SHA = "a" * 64
_SOURCE_SNAPSHOT_SHA = "b" * 64
_OUTCOME_SHA = "c" * 64


def _outcome(**overrides: object) -> ReplayTargetOutcome:
    values: dict[str, object] = {
        "lottery_type": LotteryType.BIG_LOTTO,
        "target_draw_number": "100",
        "target_draw_date": date(2026, 1, 1),
        "winning_main_numbers": (1, 2, 3, 4, 5, 6),
        "winning_special_number": 7,
    }
    values.update(overrides)
    return ReplayTargetOutcome.create(**values)  # type: ignore[arg-type]


def _scored_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "scoring_schema_version": SCORING_SCHEMA_VERSION,
        "source_replay_artifact_payload_sha256": _SOURCE_ARTIFACT_SHA,
        "source_replay_snapshot_result_sha256": _SOURCE_SNAPSHOT_SHA,
        "dataset_id": "dataset",
        "dataset_version": "1",
        "lottery_type": LotteryType.BIG_LOTTO,
        "target_draw_number": "100",
        "target_draw_date": date(2026, 1, 1),
        "strategy_id": "strategy",
        "strategy_version": "1.0.0",
        "source_history_status": "OK",
        "source_history_reason_code": None,
        "source_prediction_status": "OK",
        "source_prediction_reason_code": None,
        "scoring_status": ReplayScoringStatus.SCORED,
        "scoring_reason_code": None,
        "predicted_main_numbers": (1, 2, 3, 4, 5, 6),
        "target_outcome_sha256": _OUTCOME_SHA,
        "main_number_hit_count": 6,
        "special_number_hit": False,
        "prize_tier_id": BigLottoPrizeTierId.FIRST,
        "prize_official_label": "頭獎",
        "no_prize_result": None,
    }
    values.update(overrides)
    return values


def test_valid_target_outcome_is_immutable_and_hash_stamped() -> None:
    outcome = _outcome()

    assert outcome.winning_main_numbers == (1, 2, 3, 4, 5, 6)
    assert len(outcome.outcome_sha256) == 64
    with pytest.raises(AttributeError):
        outcome.target_draw_number = "101"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("winning_main_numbers", (1, 2, 3, 4, 5)),
        ("winning_main_numbers", (0, 2, 3, 4, 5, 6)),
        ("winning_main_numbers", (1, 2, 3, 4, 5, 50)),
        ("winning_main_numbers", (1, 2, 3, 4, 5, 5)),
        ("winning_main_numbers", (2, 1, 3, 4, 5, 6)),
        ("winning_special_number", 50),
        ("winning_special_number", 6),
    ),
)
def test_invalid_target_outcome_numbers_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _outcome(**{field: value})


def test_target_outcome_hash_changes_with_main_or_special_number() -> None:
    original = _outcome()
    changed_main = _outcome(winning_main_numbers=(1, 2, 3, 4, 5, 8))
    changed_special = _outcome(winning_special_number=8)

    hashes = {
        original.outcome_sha256,
        changed_main.outcome_sha256,
        changed_special.outcome_sha256,
    }
    assert len(hashes) == 3


@pytest.mark.parametrize(
    "draw_number",
    ("", " 100 ", "\uff13\uff10\uff10", "abc", "1" * 33),
)
def test_target_outcome_rejects_non_normalized_draw_number(draw_number: str) -> None:
    with pytest.raises(ValueError, match="ASCII decimal digits"):
        _outcome(target_draw_number=draw_number)


def test_target_outcome_preserves_leading_zeroes_as_identity() -> None:
    padded = _outcome(target_draw_number="0007")
    plain = _outcome(target_draw_number="7")

    assert padded.target_draw_number == "0007"
    assert padded.outcome_sha256 != plain.outcome_sha256


def test_scored_requires_the_complete_hit_and_prize_field_set() -> None:
    with pytest.raises(ValueError, match="main_number_hit_count"):
        ReplayScoredPrediction.create(**_scored_values(main_number_hit_count=None))
    with pytest.raises(ValueError, match="special_number_hit"):
        ReplayScoredPrediction.create(**_scored_values(special_number_hit=None))
    with pytest.raises(ValueError, match="canonical prize tier"):
        ReplayScoredPrediction.create(
            **_scored_values(prize_tier_id=None, prize_official_label=None)
        )


def test_impossible_scored_signature_cannot_obtain_a_valid_result_hash() -> None:
    record: ReplayScoredPrediction | None = None

    with pytest.raises(ValueError, match="ticket size"):
        record = ReplayScoredPrediction.create(
            **_scored_values(
                main_number_hit_count=6,
                special_number_hit=True,
                prize_tier_id=None,
                prize_official_label=None,
                no_prize_result=NoPrizeResult.NO_PRIZE,
            )
        )

    assert record is None


def test_winning_signature_rejects_no_prize() -> None:
    with pytest.raises(ValueError, match="winning signature cannot carry NO_PRIZE"):
        ReplayScoredPrediction.create(
            **_scored_values(
                main_number_hit_count=6,
                special_number_hit=False,
                prize_tier_id=None,
                prize_official_label=None,
                no_prize_result=NoPrizeResult.NO_PRIZE,
            )
        )


@pytest.mark.parametrize(
    ("prize_tier_id", "prize_official_label"),
    (
        (BigLottoPrizeTierId.SECOND, "頭獎"),
        (BigLottoPrizeTierId.FIRST, "貳獎"),
    ),
)
def test_winning_signature_rejects_wrong_canonical_tier(
    prize_tier_id: BigLottoPrizeTierId,
    prize_official_label: str,
) -> None:
    with pytest.raises(ValueError, match="canonical prize tier"):
        ReplayScoredPrediction.create(
            **_scored_values(
                prize_tier_id=prize_tier_id,
                prize_official_label=prize_official_label,
            )
        )


def test_losing_signature_rejects_winning_tier() -> None:
    with pytest.raises(ValueError, match="cannot carry a winning tier"):
        ReplayScoredPrediction.create(
            **_scored_values(
                main_number_hit_count=1,
                special_number_hit=False,
            )
        )


def test_no_prize_is_scored_and_distinct_from_not_scored() -> None:
    record = ReplayScoredPrediction.create(
        **_scored_values(
            predicted_main_numbers=(1, 8, 9, 10, 11, 12),
            main_number_hit_count=1,
            prize_tier_id=None,
            prize_official_label=None,
            no_prize_result=NoPrizeResult.NO_PRIZE,
        )
    )

    assert record.scoring_status is ReplayScoringStatus.SCORED
    assert record.no_prize_result is NoPrizeResult.NO_PRIZE
    assert record.prize_tier_id is None
    assert record.prize_official_label is None
    assert record.scored_result_sha256 == recompute_scored_result_sha256(record)


@pytest.mark.parametrize(
    "tier",
    BIG_LOTTO_RULE_CONTRACT.prize_rule.tiers,
    ids=lambda tier: tier.tier_id.value,
)
def test_every_canonical_winning_tier_remains_valid(tier: BigLottoPrizeTier) -> None:
    resolution = resolve_big_lotto_prize_tier(tier.main_hits, tier.special_hit)

    assert resolution is tier
    record = ReplayScoredPrediction.create(
        **_scored_values(
            main_number_hit_count=tier.main_hits,
            special_number_hit=tier.special_hit,
            prize_tier_id=tier.tier_id,
            prize_official_label=tier.official_label,
        )
    )

    assert record.prize_tier_id is tier.tier_id
    assert record.prize_official_label == tier.official_label
    assert record.no_prize_result is None
    assert record.scored_result_sha256 == recompute_scored_result_sha256(record)


def test_closed_history_and_prediction_reject_hit_and_tier_fields() -> None:
    history_closed = _scored_values(
        source_history_status="TARGET_NOT_FOUND",
        source_history_reason_code="TARGET_DRAW_NOT_FOUND",
        source_prediction_status=None,
        source_prediction_reason_code=None,
        strategy_version=None,
        predicted_main_numbers=None,
        target_outcome_sha256=None,
        main_number_hit_count=None,
        special_number_hit=None,
        prize_tier_id=None,
        prize_official_label=None,
        no_prize_result=None,
        scoring_status=ReplayScoringStatus.NOT_SCORED_HISTORY_CLOSED,
        scoring_reason_code=ReplayScoringReason.SOURCE_HISTORY_CLOSED,
    )
    ReplayScoredPrediction.create(**history_closed)
    with pytest.raises(ValueError, match="cannot carry hit or prize"):
        ReplayScoredPrediction.create(**(history_closed | {"main_number_hit_count": 0}))

    prediction_closed = _scored_values(
        source_prediction_status="STRATEGY_NOT_FOUND",
        source_prediction_reason_code="UNKNOWN_STRATEGY",
        strategy_version=None,
        predicted_main_numbers=None,
        target_outcome_sha256=None,
        main_number_hit_count=None,
        special_number_hit=None,
        prize_tier_id=None,
        prize_official_label=None,
        no_prize_result=None,
        scoring_status=ReplayScoringStatus.NOT_SCORED_PREDICTION_CLOSED,
        scoring_reason_code=ReplayScoringReason.SOURCE_PREDICTION_CLOSED,
    )
    ReplayScoredPrediction.create(**prediction_closed)
    with pytest.raises(ValueError, match="cannot carry hit or prize"):
        ReplayScoredPrediction.create(**(prediction_closed | {"special_number_hit": False}))


@pytest.mark.parametrize(
    ("status", "reason", "outcome_sha"),
    (
        (
            ReplayScoringStatus.TARGET_OUTCOME_NOT_FOUND,
            ReplayScoringReason.TARGET_OUTCOME_NOT_FOUND,
            None,
        ),
        (
            ReplayScoringStatus.TARGET_IDENTITY_MISMATCH,
            ReplayScoringReason.TARGET_IDENTITY_MISMATCH,
            _OUTCOME_SHA,
        ),
    ),
)
def test_missing_and_mismatched_outcomes_reject_scoring_fields(
    status: ReplayScoringStatus,
    reason: ReplayScoringReason,
    outcome_sha: str | None,
) -> None:
    values = _scored_values(
        scoring_status=status,
        scoring_reason_code=reason,
        target_outcome_sha256=outcome_sha,
        main_number_hit_count=None,
        special_number_hit=None,
        prize_tier_id=None,
        prize_official_label=None,
        no_prize_result=None,
    )
    ReplayScoredPrediction.create(**values)
    with pytest.raises(ValueError, match="cannot carry hit or prize"):
        ReplayScoredPrediction.create(**(values | {"main_number_hit_count": 0}))


def test_scored_result_hash_changes_with_tier_or_hit_signature() -> None:
    first = ReplayScoredPrediction.create(**_scored_values())
    second = ReplayScoredPrediction.create(
        **_scored_values(
            predicted_main_numbers=(1, 2, 3, 4, 5, 7),
            main_number_hit_count=5,
            special_number_hit=True,
            prize_tier_id=BigLottoPrizeTierId.SECOND,
            prize_official_label="貳獎",
        )
    )

    assert first.scored_result_sha256 != second.scored_result_sha256


def test_partially_populated_identities_fail_closed() -> None:
    with pytest.raises(ValueError, match="complete strategy identity"):
        ReplayScoredPrediction.create(**_scored_values(strategy_version=None))
    with pytest.raises(ValueError, match="target_draw_number"):
        ReplayScoredPrediction.create(**_scored_values(target_draw_number=""))
    with pytest.raises(ValueError, match="target_outcome_sha256"):
        ReplayScoredPrediction.create(**_scored_values(target_outcome_sha256="invalid"))
