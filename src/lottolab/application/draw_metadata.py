"""Research-only sidecar metadata retained from the official Taiwan Lottery API.

This is additive to, and never feeds, the canonical draw-ingestion contract in
``lottolab.application.draw_automation`` (``ProviderDrawRecord`` /
``ProviderFetchResult``). Nothing here changes backend CSV validation, the
canonical draw database, or any strategy semantics; it exists so future
research can read fields the canonical ingestion path currently discards:
``drawNumberAppear``, ``sellAmount``, ``totalAmount``, and the jackpot/rollover
prize-tier fields.

Field names below intentionally avoid inventing meaning the source does not
confirm. ``draw_number_appear`` mirrors the official ``drawNumberAppear`` key
verbatim; it is NOT renamed to a physical-draw-order concept because no
official documentation in this repository confirms that semantic.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from lottolab.domain.draws import LotteryType


class FieldCausalAvailability(StrEnum):
    """When a field's value can be known relative to the draw it describes."""

    PRE_DRAW_DERIVABLE = "PRE_DRAW_DERIVABLE"
    POST_DRAW_ONLY = "POST_DRAW_ONLY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class OfficialDrawMetadataRecord:
    """One draw's research-only metadata, additive to ``ProviderDrawRecord``.

    ``jackpot_prize``/``jackpot_last_prize`` are ``None`` when the lottery
    type's top prize tier has no rollover pool in the source (confirmed for
    ``DAILY_539``, whose ``d539JackpotAssign`` object carries only
    ``winnerCount``/``perPrize``). ``raw_json`` is the complete, untouched
    source row so a field this record does not individually model is never
    lost.
    """

    lottery_type: LotteryType
    draw_number: str
    draw_date: date
    draw_number_appear: tuple[int, ...]
    sell_amount: int | None
    total_amount: int | None
    jackpot_winner_count: int | None
    jackpot_per_prize: int | None
    jackpot_prize: int | None
    jackpot_last_prize: int | None
    source_reference: str
    raw_json: str


#: Causal-availability contract for every modeled field on
#: :class:`OfficialDrawMetadataRecord`, keyed by field name. A field is
#: ``PRE_DRAW_DERIVABLE`` only when its value for draw ``t`` can be computed
#: from draws strictly before ``t`` alone (see
#: :func:`derive_pre_draw_jackpot_rollover`). Every other modeled field is
#: ``POST_DRAW_ONLY``: it is delivered by the official API bundled with draw
#: ``t``'s own result and must never be used as a same-target predictive
#: feature for draw ``t``.
CAUSAL_AVAILABILITY: dict[str, FieldCausalAvailability] = {
    "draw_number_appear": FieldCausalAvailability.POST_DRAW_ONLY,
    "sell_amount": FieldCausalAvailability.POST_DRAW_ONLY,
    "total_amount": FieldCausalAvailability.POST_DRAW_ONLY,
    "jackpot_winner_count": FieldCausalAvailability.POST_DRAW_ONLY,
    "jackpot_per_prize": FieldCausalAvailability.POST_DRAW_ONLY,
    "jackpot_prize": FieldCausalAvailability.POST_DRAW_ONLY,
    "jackpot_last_prize": FieldCausalAvailability.POST_DRAW_ONLY,
    "raw_json": FieldCausalAvailability.POST_DRAW_ONLY,
}

#: The pre-draw rollover state entering a target draw is itself
#: ``PRE_DRAW_DERIVABLE`` even though the ``jackpot_last_prize`` field stored
#: on a draw's own row is ``POST_DRAW_ONLY``: it is a deterministic function
#: of the strictly-prior draw and never depends on the target draw's own row.
#: See :func:`derive_pre_draw_jackpot_rollover`.
PRE_DRAW_ROLLOVER_AVAILABILITY = FieldCausalAvailability.PRE_DRAW_DERIVABLE


def derive_pre_draw_jackpot_rollover(
    *, prior_draw_metadata: OfficialDrawMetadataRecord | None
) -> int | None:
    """Reconstruct the jackpot pool carried into the draw after ``prior_draw_metadata``.

    Uses ONLY the immediately-preceding draw's own jackpot-tier fields; never
    reads a target draw's own row. Returns ``None`` when there is no prior
    draw, or when the lottery type has no rollover jackpot tier (its
    ``jackpot_prize``/``jackpot_last_prize`` are ``None``) -- this function
    never guesses a missing jackpot value.

    Verified against live official API history for ``BIG_LOTTO`` and
    ``POWER_LOTTO``: when the prior draw's jackpot ``winner_count`` is 0, the
    pool carries forward as ``prize + last_prize``; whenever a draw's
    ``winner_count`` is greater than 0, the following draw's carried pool
    resets to 0.
    """

    if prior_draw_metadata is None:
        return None
    winner_count = prior_draw_metadata.jackpot_winner_count
    prize = prior_draw_metadata.jackpot_prize
    last_prize = prior_draw_metadata.jackpot_last_prize
    if winner_count is None or prize is None or last_prize is None:
        return None
    if winner_count > 0:
        return 0
    return prize + last_prize


def find_prior_draw_metadata(
    records: Iterable[OfficialDrawMetadataRecord],
    *,
    lottery_type: LotteryType,
    strictly_before: date,
) -> OfficialDrawMetadataRecord | None:
    """Return the most recent record strictly before ``strictly_before``.

    Only considers records with a matching ``lottery_type`` and a
    ``draw_date`` earlier than ``strictly_before``; a record for the target
    draw itself (or any later draw) is never eligible.
    """

    candidates = [
        record
        for record in records
        if record.lottery_type is lottery_type and record.draw_date < strictly_before
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda record: (record.draw_date, int(record.draw_number)))


def derive_pre_draw_jackpot_rollover_for_target(
    records: Iterable[OfficialDrawMetadataRecord],
    *,
    lottery_type: LotteryType,
    target_draw_date: date,
) -> int | None:
    """Compute the pre-draw jackpot rollover for a target draw date.

    Equivalent to :func:`derive_pre_draw_jackpot_rollover` applied to the
    result of :func:`find_prior_draw_metadata`; ``target_draw_date`` is used
    only as the strictly-before cutoff and the target draw's own row (if any
    exists in ``records``) is never consulted.
    """

    prior = find_prior_draw_metadata(
        records, lottery_type=lottery_type, strictly_before=target_draw_date
    )
    return derive_pre_draw_jackpot_rollover(prior_draw_metadata=prior)


__all__ = [
    "CAUSAL_AVAILABILITY",
    "PRE_DRAW_ROLLOVER_AVAILABILITY",
    "FieldCausalAvailability",
    "OfficialDrawMetadataRecord",
    "derive_pre_draw_jackpot_rollover",
    "derive_pre_draw_jackpot_rollover_for_target",
    "find_prior_draw_metadata",
]
