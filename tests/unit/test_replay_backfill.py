from datetime import date, timedelta
from typing import Any

import pytest

from lottolab.application.use_cases.replay_backfill import (
    BackfillSelection,
    canonical_json,
    identity,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"latest": 0},
        {"latest": True},
        {"latest": 2, "all_draws": True},
        {"all_draws": True, "start_date": date(2020, 1, 1)},
        {"start_date": date(2020, 2, 1), "end_date": date(2020, 1, 1)},
    ],
)
def test_reject_invalid_selection(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        BackfillSelection(**kwargs)


def test_selection_preserves_full_history_and_does_not_pad_missing_draws() -> None:
    draws = tuple(
        ReplayDraw(
            LotteryType.BIG_LOTTO,
            str(n),
            date(2020, 1, 1) + timedelta(days=n),
            (1, 2, 3, 4, 5, 6),
            7,
        )
        for n in range(10)
    )
    assert BackfillSelection(latest=3).select(draws) == draws[-3:]
    assert (
        BackfillSelection(start_date=draws[3].draw_date, end_date=draws[5].draw_date).select(draws)
        == draws[3:6]
    )
    assert BackfillSelection(all_draws=True).select(draws) == draws
    with pytest.raises(ValueError, match="only 10 available"):
        BackfillSelection(latest=1500).select(draws)
    with pytest.raises(ValueError, match="no target"):
        BackfillSelection(start_date=date(2030, 1, 1)).select(draws)


def test_hash_uses_json_roundtrip() -> None:
    assert canonical_json({1: (2, 3)}) == canonical_json({"1": [2, 3]})
    assert identity({1: (2, 3)}) == identity({"1": [2, 3]})
