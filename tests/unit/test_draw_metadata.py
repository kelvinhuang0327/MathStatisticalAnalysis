"""Unit coverage for the official-draw metadata contract and rollover derivation.

The rollover arithmetic verified here (``prize + last_prize`` carries
forward when the prior draw's jackpot ``winner_count`` is 0; the pool resets
to 0 the draw after any ``winner_count > 0``) was reproduced against live
official API history for BIG_LOTTO (2 rows) and POWER_LOTTO (100 rows, 5
winner events, 94 no-winner chain checks, all consistent).
"""

from __future__ import annotations

from datetime import date

from lottolab.application.draw_metadata import (
    CAUSAL_AVAILABILITY,
    FieldCausalAvailability,
    OfficialDrawMetadataRecord,
    derive_pre_draw_jackpot_rollover,
    derive_pre_draw_jackpot_rollover_for_target,
    find_prior_draw_metadata,
)
from lottolab.domain.draws import LotteryType


def _record(
    *,
    lottery_type: LotteryType = LotteryType.BIG_LOTTO,
    draw_number: str,
    draw_date: date,
    jackpot_prize: int | None = None,
    jackpot_last_prize: int | None = None,
    jackpot_winner_count: int | None = None,
) -> OfficialDrawMetadataRecord:
    return OfficialDrawMetadataRecord(
        lottery_type=lottery_type,
        draw_number=draw_number,
        draw_date=draw_date,
        draw_number_appear=(1, 2, 3, 4, 5, 6, 7),
        sell_amount=None,
        total_amount=None,
        jackpot_winner_count=jackpot_winner_count,
        jackpot_per_prize=None,
        jackpot_prize=jackpot_prize,
        jackpot_last_prize=jackpot_last_prize,
        source_reference="test",
        raw_json="{}",
    )


def test_no_winner_rollover_carries_prize_plus_last_prize_forward() -> None:
    prior = _record(
        draw_number="115000078",
        draw_date=date(2026, 8, 11),
        jackpot_prize=16397730,
        jackpot_last_prize=61686460,
        jackpot_winner_count=0,
    )

    rollover = derive_pre_draw_jackpot_rollover(prior_draw_metadata=prior)

    assert rollover == 16397730 + 61686460 == 78084190


def test_winner_resets_next_draw_rollover_to_zero() -> None:
    prior = _record(
        draw_number="115000017",
        draw_date=date(2026, 2, 16),
        jackpot_prize=67955440,
        jackpot_last_prize=42036926,
        jackpot_winner_count=1,
    )

    rollover = derive_pre_draw_jackpot_rollover(prior_draw_metadata=prior)

    assert rollover == 0


def test_no_prior_draw_yields_unknown_rollover() -> None:
    assert derive_pre_draw_jackpot_rollover(prior_draw_metadata=None) is None


def test_lottery_type_without_rollover_pool_yields_unknown_not_guessed() -> None:
    prior = _record(
        draw_number="115000198",
        draw_date=date(2026, 8, 15),
        jackpot_prize=None,
        jackpot_last_prize=None,
        jackpot_winner_count=0,
    )

    assert derive_pre_draw_jackpot_rollover(prior_draw_metadata=prior) is None


def test_find_prior_draw_metadata_excludes_same_and_later_dates() -> None:
    earlier = _record(draw_number="1", draw_date=date(2026, 1, 1))
    same_date_as_target = _record(draw_number="2", draw_date=date(2026, 1, 5))
    later = _record(draw_number="3", draw_date=date(2026, 1, 10))

    prior = find_prior_draw_metadata(
        [earlier, same_date_as_target, later],
        lottery_type=LotteryType.BIG_LOTTO,
        strictly_before=date(2026, 1, 5),
    )

    assert prior is earlier


def test_find_prior_draw_metadata_returns_most_recent_eligible() -> None:
    older = _record(draw_number="1", draw_date=date(2026, 1, 1))
    closer = _record(draw_number="2", draw_date=date(2026, 1, 3))

    prior = find_prior_draw_metadata(
        [older, closer],
        lottery_type=LotteryType.BIG_LOTTO,
        strictly_before=date(2026, 1, 5),
    )

    assert prior is closer


def test_find_prior_draw_metadata_filters_by_lottery_type() -> None:
    wrong_type = _record(
        lottery_type=LotteryType.POWER_LOTTO, draw_number="1", draw_date=date(2026, 1, 1)
    )

    prior = find_prior_draw_metadata(
        [wrong_type],
        lottery_type=LotteryType.BIG_LOTTO,
        strictly_before=date(2026, 1, 5),
    )

    assert prior is None


def test_derive_for_target_uses_only_strictly_prior_draws_never_target_row() -> None:
    prior = _record(
        draw_number="115000078",
        draw_date=date(2026, 8, 11),
        jackpot_prize=16397730,
        jackpot_last_prize=61686460,
        jackpot_winner_count=0,
    )
    target_row_present_but_must_be_ignored = _record(
        draw_number="115000079",
        draw_date=date(2026, 8, 14),
        jackpot_prize=999,
        jackpot_last_prize=999,
        jackpot_winner_count=1,
    )

    rollover = derive_pre_draw_jackpot_rollover_for_target(
        [prior, target_row_present_but_must_be_ignored],
        lottery_type=LotteryType.BIG_LOTTO,
        target_draw_date=date(2026, 8, 14),
    )

    assert rollover == 78084190


def test_post_draw_only_fields_are_never_marked_pre_draw_derivable() -> None:
    for field, availability in CAUSAL_AVAILABILITY.items():
        assert availability is FieldCausalAvailability.POST_DRAW_ONLY, field
