"""GET-only query use case for the isolated Next-Draw P4 authority."""

from __future__ import annotations

import re
from datetime import date

from lottolab.application.ports import NextDrawP4AttributionReaderFactory
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_outcome_attribution import (
    NextDrawOutcomeAttribution,
    NextDrawOutcomeAttributionPage,
)

_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)


class NextDrawP4AttributionNotFoundError(LookupError):
    """No persisted P4 artifact matches the exact target key."""


class QueryNextDrawP4Attribution:
    """Create one read-only repository per request and return stored artifacts only."""

    def __init__(self, reader_factory: NextDrawP4AttributionReaderFactory) -> None:
        self._reader_factory = reader_factory

    def get_exact(
        self,
        *,
        lottery_type: LotteryType,
        target_draw_number: str,
        target_draw_date: date,
    ) -> NextDrawOutcomeAttribution:
        _validate_target(lottery_type, target_draw_number, target_draw_date)
        artifact = self._reader_factory().get_attribution(
            lottery_type,
            target_draw_number,
            target_draw_date,
        )
        if artifact is None:
            raise NextDrawP4AttributionNotFoundError(target_draw_number)
        return artifact

    def history(
        self,
        *,
        lottery_type: LotteryType | None,
        page: int,
        page_size: int,
    ) -> NextDrawOutcomeAttributionPage:
        if lottery_type is not None and lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("P4 history supports BIG_LOTTO only")
        if type(page) is not int or page < 1:
            raise ValueError("page must be a positive integer")
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        return self._reader_factory().list_attributions(
            lottery_type=lottery_type,
            page=page,
            page_size=page_size,
        )


def _validate_target(
    lottery_type: LotteryType,
    target_draw_number: str,
    target_draw_date: date,
) -> None:
    if lottery_type is not LotteryType.BIG_LOTTO:
        raise ValueError("P4 target supports BIG_LOTTO only")
    if type(target_draw_number) is not str or _DRAW_NUMBER.fullmatch(target_draw_number) is None:
        raise ValueError("target_draw_number is invalid")
    if type(target_draw_date) is not date:
        raise ValueError("target_draw_date is invalid")


__all__ = [
    "NextDrawP4AttributionNotFoundError",
    "QueryNextDrawP4Attribution",
]
