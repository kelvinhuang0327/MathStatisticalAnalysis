"""Fixture-only acceptance for the official BIG_LOTTO schedule authority contract."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from lottolab.application.schedule_sync import (
    BIG_LOTTO_SCHEDULE_GAME_CODE,
    OfficialScheduleContractError,
    ScheduleAuthorityStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    OfficialHttpsClient,
    TaiwanLotteryBigLottoCanonicalScheduleAuthorityProvider,
    parse_official_biglotto_schedule_authority,
)

OBSERVED_AT = datetime(2099, 1, 1, tzinfo=UTC)


def _body(*rows: object, marker: int = 0) -> bytes:
    return json.dumps(
        {
            "content": {"nextDrawDateList": list(rows)},
            "fixtureMarker": marker,
            "rtCode": 0,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _row(*, game_code: object, draw_date: object, draw_term: object) -> dict[str, object]:
    return {
        "drawDate": draw_date,
        "drawTerm": draw_term,
        "gameCode": game_code,
    }


def _biglotto_game(body: bytes):
    result = parse_official_biglotto_schedule_authority(
        body,
        observed_at=OBSERVED_AT,
    )
    assert len(result.games) == 1
    game = result.games[0]
    assert game.lottery_type is LotteryType.BIG_LOTTO
    assert game.official_game_code == BIG_LOTTO_SCHEDULE_GAME_CODE
    return result, game


def test_biglotto_provider_uses_5118_and_preserves_explicit_eight_field_identity() -> None:
    body = _body(
        _row(game_code=BIG_LOTTO_SCHEDULE_GAME_CODE, draw_date="20990102", draw_term="115000087"),
        _row(game_code=5120, draw_date="20990102", draw_term="539-ignored"),
    )
    result, game = _biglotto_game(body)

    assert game.status is ScheduleAuthorityStatus.COMPLETE
    assert len(game.schedules) == 1
    fact = game.schedules[0]
    assert fact.announcement.target.lottery_type is LotteryType.BIG_LOTTO
    assert fact.announcement.target.draw_number == "115000087"
    assert fact.announcement.target.draw_date.isoformat() == "2099-01-02"
    assert fact.announcement.scheduled_at.isoformat() == "2099-01-02T12:30:00+00:00"
    assert fact.announcement.schedule_timezone == "Asia/Taipei"
    assert fact.official_game_code == 5118
    assert fact.scheduled_local_time.isoformat() == "20:30:00"
    assert fact.source_period_identifier == "115000087"
    assert set(fact.immutable_dict()) == {
        "draw_date",
        "draw_number",
        "lottery_type",
        "official_game_code",
        "schedule_timezone",
        "scheduled_at",
        "scheduled_local_time",
        "source_period_identifier",
    }
    assert result.source_payload_sha256 == fact.announcement.source.source_payload_sha256


def test_biglotto_provider_path_calls_official_https_client_and_returns_one_game() -> None:
    body = _body(
        _row(game_code=BIG_LOTTO_SCHEDULE_GAME_CODE, draw_date="20990102", draw_term=115000087)
    )
    provider = TaiwanLotteryBigLottoCanonicalScheduleAuthorityProvider(
        https_client=OfficialHttpsClient(
            transport=lambda _request, _context, _timeout, _limit: body
        )
    )

    result = provider.fetch_authority(observed_at=OBSERVED_AT)

    assert len(result.games) == 1
    assert result.games[0].status is ScheduleAuthorityStatus.COMPLETE
    assert result.games[0].schedules[0].source_period_identifier == "115000087"


def test_biglotto_missing_draw_term_has_no_fact_and_wrong_game_code_is_not_coerced() -> None:
    result, game = _biglotto_game(
        _body(
            _row(game_code=BIG_LOTTO_SCHEDULE_GAME_CODE, draw_date="20990102", draw_term=None),
            _row(game_code="5118", draw_date="20990103", draw_term="115000088"),
        )
    )

    assert result.games[0] is game
    assert game.status is ScheduleAuthorityStatus.INCOMPLETE_AUTHORITY
    assert game.schedules == ()


def test_biglotto_conflicting_natural_key_is_fail_closed() -> None:
    _, game = _biglotto_game(
        _body(
            _row(
                game_code=BIG_LOTTO_SCHEDULE_GAME_CODE,
                draw_date="20990102",
                draw_term="115000087",
            ),
            _row(
                game_code=BIG_LOTTO_SCHEDULE_GAME_CODE,
                draw_date="20990103",
                draw_term="115000087",
            ),
        )
    )

    assert game.status is ScheduleAuthorityStatus.SOURCE_CONFLICT
    assert game.schedules == ()


def test_duplicate_json_member_is_rejected_before_schedule_interpretation() -> None:
    body = (
        b'{"content":{"nextDrawDateList":[]},"content":{"nextDrawDateList":[]},'
        b'"rtCode":0}'
    )

    with pytest.raises(OfficialScheduleContractError, match="duplicate JSON members"):
        parse_official_biglotto_schedule_authority(body, observed_at=OBSERVED_AT)
