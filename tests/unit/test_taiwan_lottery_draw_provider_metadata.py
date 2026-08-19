"""Acceptance tests for the official-draw research metadata sidecar parsing.

Fixture shapes mirror a live spot-check of the official API (2026-08-16):
BIG_LOTTO uses ``jackpotAssign``/``secondAssign``/...; POWER_LOTTO uses
``super638JackpotAssign``/...; DAILY_539 uses ``d539JackpotAssign`` whose
tier object carries only ``winnerCount``/``perPrize`` -- no
``prize``/``lastPrize`` -- confirmed across 60 sampled rows to have no
rollover jackpot pool. ``period`` defaults to a real-shaped JSON integer
(also spot-checked live); the one row that overrides it with a string
(``test_rows_outside_range_produce_no_metadata_either``) proves the string
form stays compatible too.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from lottolab.application.draw_automation import DrawProviderContractError
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.taiwan_lottery_draw_provider import TaiwanLotteryDrawProvider


def _envelope(result_key: str, rows: list[dict[str, object]]) -> bytes:
    return json.dumps({"rtCode": 0, "rtMsg": "OK", "content": {result_key: rows}}).encode("utf-8")


def _big_lotto_row(
    period: int | str = 115000079,
    iso_date: str = "2026-08-14",
    *,
    draw_number_size: list[object] | None = None,
    draw_number_appear: list[object] | None = None,
    sell_amount: object = 93928200,
    total_amount: object = 130683982,
    jackpot: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "period": period,
        "lotteryDate": iso_date,
        "drawNumberSize": draw_number_size or [5, 12, 25, 33, 34, 35, 27],
        "drawNumberAppear": (
            draw_number_appear if draw_number_appear is not None else [35, 25, 5, 12, 34, 33, 27]
        ),
        "totalAmount": total_amount,
        "sellAmount": sell_amount,
        "jackpotAssign": (
            jackpot
            if jackpot is not None
            else {"prize": 18825389, "lastPrize": 78084190, "winnerCount": 0, "perPrize": 0}
        ),
        "secondAssign": {"prize": 1492256, "lastPrize": 0, "winnerCount": 1, "perPrize": 1492256},
    }


def _power_lotto_row() -> dict[str, object]:
    return {
        "period": 115000065,
        "lotteryDate": "2026-08-13",
        "drawNumberSize": [1, 3, 4, 7, 10, 19, 6],
        "drawNumberAppear": [1, 4, 10, 19, 7, 3, 6],
        "totalAmount": 286438226,
        "sellAmount": 61051500,
        "super638JackpotAssign": {
            "prize": 18022878,
            "lastPrize": 246330673,
            "winnerCount": 0,
            "perPrize": 0,
        },
    }


def _daily_539_row() -> dict[str, object]:
    return {
        "period": 115000198,
        "lotteryDate": "2026-08-15",
        "drawNumberSize": [12, 14, 21, 35, 37],
        "drawNumberAppear": [35, 21, 37, 14, 12],
        "sellAmount": 36512950,
        "totalAmount": 10531900,
        "d539JackpotAssign": {"winnerCount": 0, "perPrize": 8000000},
    }


class _FakeTransport:
    def __init__(self, response: bytes) -> None:
        self._response = response

    def __call__(self, url: str) -> bytes:
        return self._response


def test_fetch_draws_with_metadata_matches_fetch_draws_canonical_half() -> None:
    row = _big_lotto_row()
    transport = _FakeTransport(_envelope("lotto649Res", [row]))
    provider = TaiwanLotteryDrawProvider(transport=transport)

    canonical_only = provider.fetch_draws(
        lottery_type=LotteryType.BIG_LOTTO, date_from=date(2026, 8, 1), date_to=date(2026, 8, 31)
    )
    result, metadata = provider.fetch_draws_with_metadata(
        lottery_type=LotteryType.BIG_LOTTO, date_from=date(2026, 8, 1), date_to=date(2026, 8, 31)
    )

    assert result == canonical_only
    assert result.records[0].main_numbers == (5, 12, 25, 33, 34, 35)
    assert len(metadata) == 1


def test_draw_number_appear_preserved_in_source_order_unsorted() -> None:
    row = _big_lotto_row(draw_number_appear=[35, 25, 5, 12, 34, 33, 27])
    transport = _FakeTransport(_envelope("lotto649Res", [row]))
    provider = TaiwanLotteryDrawProvider(transport=transport)

    _, metadata = provider.fetch_draws_with_metadata(
        lottery_type=LotteryType.BIG_LOTTO, date_from=date(2026, 8, 1), date_to=date(2026, 8, 31)
    )

    assert metadata[0].draw_number_appear == (35, 25, 5, 12, 34, 33, 27)
    assert metadata[0].draw_number_appear != tuple(sorted(metadata[0].draw_number_appear))


def test_big_lotto_jackpot_tier_fields_preserved() -> None:
    row = _big_lotto_row(
        jackpot={"prize": 18825389, "lastPrize": 78084190, "winnerCount": 0, "perPrize": 0}
    )
    transport = _FakeTransport(_envelope("lotto649Res", [row]))
    provider = TaiwanLotteryDrawProvider(transport=transport)

    _, metadata = provider.fetch_draws_with_metadata(
        lottery_type=LotteryType.BIG_LOTTO, date_from=date(2026, 8, 1), date_to=date(2026, 8, 31)
    )
    record = metadata[0]

    assert record.jackpot_prize == 18825389
    assert record.jackpot_last_prize == 78084190
    assert record.jackpot_winner_count == 0
    assert record.jackpot_per_prize == 0
    assert record.sell_amount == 93928200
    assert record.total_amount == 130683982


def test_power_lotto_uses_its_own_jackpot_assign_key() -> None:
    transport = _FakeTransport(_envelope("superLotto638Res", [_power_lotto_row()]))
    provider = TaiwanLotteryDrawProvider(transport=transport)

    _, metadata = provider.fetch_draws_with_metadata(
        lottery_type=LotteryType.POWER_LOTTO,
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31),
    )
    record = metadata[0]

    assert record.jackpot_prize == 18022878
    assert record.jackpot_last_prize == 246330673
    assert record.jackpot_winner_count == 0


def test_daily_539_has_no_rollover_jackpot_pool() -> None:
    transport = _FakeTransport(_envelope("daily539Res", [_daily_539_row()]))
    provider = TaiwanLotteryDrawProvider(transport=transport)

    _, metadata = provider.fetch_draws_with_metadata(
        lottery_type=LotteryType.DAILY_539, date_from=date(2026, 8, 1), date_to=date(2026, 8, 31)
    )
    record = metadata[0]

    assert record.jackpot_prize is None
    assert record.jackpot_last_prize is None
    assert record.jackpot_winner_count == 0
    assert record.jackpot_per_prize == 8000000


def test_raw_json_preserves_fields_not_individually_modeled() -> None:
    row = _big_lotto_row()
    transport = _FakeTransport(_envelope("lotto649Res", [row]))
    provider = TaiwanLotteryDrawProvider(transport=transport)

    _, metadata = provider.fetch_draws_with_metadata(
        lottery_type=LotteryType.BIG_LOTTO, date_from=date(2026, 8, 1), date_to=date(2026, 8, 31)
    )

    decoded = json.loads(metadata[0].raw_json)
    assert decoded["secondAssign"] == row["secondAssign"]
    assert decoded["period"] == row["period"]


def test_missing_draw_number_appear_raises_contract_error() -> None:
    row = _big_lotto_row()
    del row["drawNumberAppear"]
    transport = _FakeTransport(_envelope("lotto649Res", [row]))
    provider = TaiwanLotteryDrawProvider(transport=transport)

    with pytest.raises(DrawProviderContractError):
        provider.fetch_draws_with_metadata(
            lottery_type=LotteryType.BIG_LOTTO,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
        )


def test_wrong_length_draw_number_appear_raises_contract_error() -> None:
    row = _big_lotto_row(draw_number_appear=[35, 25, 5, 12, 34, 33])
    transport = _FakeTransport(_envelope("lotto649Res", [row]))
    provider = TaiwanLotteryDrawProvider(transport=transport)

    with pytest.raises(DrawProviderContractError):
        provider.fetch_draws_with_metadata(
            lottery_type=LotteryType.BIG_LOTTO,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
        )


def test_non_integer_winner_count_raises_contract_error() -> None:
    row = _big_lotto_row(
        jackpot={"prize": 1, "lastPrize": 2, "winnerCount": "zero", "perPrize": 0}
    )
    transport = _FakeTransport(_envelope("lotto649Res", [row]))
    provider = TaiwanLotteryDrawProvider(transport=transport)

    with pytest.raises(DrawProviderContractError):
        provider.fetch_draws_with_metadata(
            lottery_type=LotteryType.BIG_LOTTO,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
        )


def test_missing_jackpot_object_yields_none_fields_without_raising() -> None:
    row = _big_lotto_row()
    del row["jackpotAssign"]
    transport = _FakeTransport(_envelope("lotto649Res", [row]))
    provider = TaiwanLotteryDrawProvider(transport=transport)

    _, metadata = provider.fetch_draws_with_metadata(
        lottery_type=LotteryType.BIG_LOTTO, date_from=date(2026, 8, 1), date_to=date(2026, 8, 31)
    )

    record = metadata[0]
    assert record.jackpot_prize is None
    assert record.jackpot_last_prize is None
    assert record.jackpot_winner_count is None
    assert record.jackpot_per_prize is None


def test_missing_sell_amount_is_none_not_an_error() -> None:
    row = _big_lotto_row()
    del row["sellAmount"]
    transport = _FakeTransport(_envelope("lotto649Res", [row]))
    provider = TaiwanLotteryDrawProvider(transport=transport)

    _, metadata = provider.fetch_draws_with_metadata(
        lottery_type=LotteryType.BIG_LOTTO, date_from=date(2026, 8, 1), date_to=date(2026, 8, 31)
    )

    assert metadata[0].sell_amount is None
    assert metadata[0].total_amount == 130683982


def test_rows_outside_range_produce_no_metadata_either() -> None:
    row = _big_lotto_row(period="115000059", iso_date="2026-06-30")
    transport = _FakeTransport(_envelope("lotto649Res", [row]))
    provider = TaiwanLotteryDrawProvider(transport=transport)

    result, metadata = provider.fetch_draws_with_metadata(
        lottery_type=LotteryType.BIG_LOTTO, date_from=date(2026, 8, 1), date_to=date(2026, 8, 31)
    )

    assert result.records == ()
    assert metadata == ()
