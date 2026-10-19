"""Fixture-only acceptance for independent T539/P638 official schedule authority."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from lottolab.application.schedule_sync import (
    P638_SCHEDULE_GAME_CODE,
    T539_SCHEDULE_GAME_CODE,
    AuthoritativeScheduleVeto,
    CanonicalScheduleAuthorityFetchResult,
    OfficialGameScheduleAuthority,
    OfficialScheduleProviderError,
    ScheduleAuthorityStatus,
    ScheduleExceptionKind,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import TargetSourceProvenance
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    SCHEDULE_URL,
    parse_official_t539_p638_schedule,
)

OBSERVED_AT = datetime(2099, 1, 1, tzinfo=UTC)


def _body(*rows: object) -> bytes:
    return json.dumps(
        {"content": {"nextDrawDateList": list(rows)}, "rtCode": 0},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _row(*, game_code: int, draw_date: object, draw_term: object) -> dict[str, object]:
    return {
        "drawDate": draw_date,
        "drawTerm": draw_term,
        "gameCode": game_code,
    }


def _game(
    result: CanonicalScheduleAuthorityFetchResult,
    lottery_type: LotteryType,
) -> OfficialGameScheduleAuthority:
    return next(game for game in result.games if game.lottery_type is lottery_type)


def test_complete_rows_authorize_both_games_with_frozen_identity_and_time() -> None:
    result = parse_official_t539_p638_schedule(
        _body(
            _row(game_code=T539_SCHEDULE_GAME_CODE, draw_date="20990102", draw_term=1234),
            _row(
                game_code=P638_SCHEDULE_GAME_CODE,
                draw_date="20990103",
                draw_term="2234",
            ),
        ),
        observed_at=OBSERVED_AT,
    )

    t539 = _game(result, LotteryType.DAILY_539)
    p638 = _game(result, LotteryType.POWER_LOTTO)
    assert t539.status is ScheduleAuthorityStatus.COMPLETE
    assert p638.status is ScheduleAuthorityStatus.COMPLETE
    assert t539.schedules[0].announcement.target.draw_number == "1234"
    assert t539.schedules[0].source_period_identifier == "1234"
    assert t539.schedules[0].official_game_code == T539_SCHEDULE_GAME_CODE
    assert t539.schedules[0].scheduled_local_time.isoformat() == "20:30:00"
    assert t539.schedules[0].announcement.scheduled_at.isoformat() == (
        "2099-01-02T12:30:00+00:00"
    )
    assert p638.schedules[0].announcement.target.draw_number == "2234"
    assert p638.schedules[0].official_game_code == P638_SCHEDULE_GAME_CODE
    assert len(t539.schedules[0].immutable_schedule_sha256) == 64


def test_t539_null_draw_term_is_incomplete_while_p638_remains_complete() -> None:
    result = parse_official_t539_p638_schedule(
        _body(
            _row(
                game_code=T539_SCHEDULE_GAME_CODE,
                draw_date="20990102",
                draw_term=None,
            ),
            _row(
                game_code=P638_SCHEDULE_GAME_CODE,
                draw_date="20990103",
                draw_term="2234",
            ),
        ),
        observed_at=OBSERVED_AT,
    )

    t539 = _game(result, LotteryType.DAILY_539)
    p638 = _game(result, LotteryType.POWER_LOTTO)
    assert t539.status is ScheduleAuthorityStatus.INCOMPLETE_AUTHORITY
    assert t539.schedules == ()
    assert t539.evidence_draw_dates[0].isoformat() == "2099-01-02"
    assert p638.status is ScheduleAuthorityStatus.COMPLETE


@pytest.mark.parametrize("draw_date", ["2099/01/02", "2099-01-02", "20990230"])
def test_bad_t539_date_is_game_local_and_never_relaxes_strict_yyyymmdd(
    draw_date: str,
) -> None:
    result = parse_official_t539_p638_schedule(
        _body(
            _row(
                game_code=T539_SCHEDULE_GAME_CODE,
                draw_date=draw_date,
                draw_term="1234",
            ),
            _row(
                game_code=P638_SCHEDULE_GAME_CODE,
                draw_date="20990103",
                draw_term="2234",
            ),
        ),
        observed_at=OBSERVED_AT,
    )

    assert _game(result, LotteryType.DAILY_539).status is (
        ScheduleAuthorityStatus.SOURCE_CONFLICT
    )
    assert _game(result, LotteryType.POWER_LOTTO).status is ScheduleAuthorityStatus.COMPLETE


@pytest.mark.parametrize(
    "draw_term",
    ["", "abc", "1.0", "+1", "-1", -1, 1.5, True, "12A"],
)
def test_bad_draw_term_is_rejected_without_arithmetic_or_cross_game_failure(
    draw_term: object,
) -> None:
    result = parse_official_t539_p638_schedule(
        _body(
            _row(
                game_code=T539_SCHEDULE_GAME_CODE,
                draw_date="20990102",
                draw_term=draw_term,
            ),
            _row(
                game_code=P638_SCHEDULE_GAME_CODE,
                draw_date="20990103",
                draw_term="2234",
            ),
        ),
        observed_at=OBSERVED_AT,
    )

    assert _game(result, LotteryType.DAILY_539).status is (
        ScheduleAuthorityStatus.SOURCE_CONFLICT
    )
    assert _game(result, LotteryType.DAILY_539).schedules == ()
    assert _game(result, LotteryType.POWER_LOTTO).status is ScheduleAuthorityStatus.COMPLETE


def test_observation_deadline_is_strict() -> None:
    body = _body(
        _row(game_code=T539_SCHEDULE_GAME_CODE, draw_date="20990102", draw_term="1234")
    )
    before = parse_official_t539_p638_schedule(
        body,
        observed_at=datetime(2099, 1, 2, 12, 29, 59, tzinfo=UTC),
    )
    at_deadline = parse_official_t539_p638_schedule(
        body,
        observed_at=datetime(2099, 1, 2, 12, 30, tzinfo=UTC),
    )

    assert _game(before, LotteryType.DAILY_539).status is ScheduleAuthorityStatus.COMPLETE
    assert _game(at_deadline, LotteryType.DAILY_539).status is (
        ScheduleAuthorityStatus.OBSERVATION_DEADLINE_EXPIRED
    )


def test_typed_exception_veto_blocks_ordinary_acceptance_without_notice_text_parsing() -> None:
    veto = AuthoritativeScheduleVeto(
        lottery_type=LotteryType.POWER_LOTTO,
        official_game_code=P638_SCHEDULE_GAME_CODE,
        draw_number="2234",
        exception_kind=ScheduleExceptionKind.CANCELLATION,
        source=TargetSourceProvenance(
            source_id="TAIWAN_LOTTERY_OFFICIAL_EXCEPTION_NOTICE",
            source_version="fixture-v1",
            source_locator="https://www.taiwanlottery.com/announcement/2234",
            source_sha256="b" * 64,
            observed_at=OBSERVED_AT,
        ),
    )
    result = parse_official_t539_p638_schedule(
        _body(
            _row(
                game_code=T539_SCHEDULE_GAME_CODE,
                draw_date="20990102",
                draw_term="1234",
            ),
            _row(
                game_code=P638_SCHEDULE_GAME_CODE,
                draw_date="20990103",
                draw_term="2234",
            ),
        ),
        observed_at=OBSERVED_AT,
        active_vetoes=(veto,),
    )

    assert _game(result, LotteryType.DAILY_539).status is ScheduleAuthorityStatus.COMPLETE
    p638 = _game(result, LotteryType.POWER_LOTTO)
    assert p638.status is ScheduleAuthorityStatus.AUTHORITATIVE_VETO
    assert p638.schedules == ()
    assert p638.vetoes == (veto,)


def test_typed_exception_veto_is_retained_when_current_game_row_is_absent() -> None:
    veto = AuthoritativeScheduleVeto(
        lottery_type=LotteryType.DAILY_539,
        official_game_code=T539_SCHEDULE_GAME_CODE,
        draw_number="1234",
        exception_kind=ScheduleExceptionKind.CANCELLATION,
        source=TargetSourceProvenance(
            source_id="TAIWAN_LOTTERY_OFFICIAL_EXCEPTION_NOTICE",
            source_version="fixture-v1",
            source_locator="https://www.taiwanlottery.com/announcement/1234",
            source_sha256="c" * 64,
            observed_at=OBSERVED_AT,
        ),
    )
    result = parse_official_t539_p638_schedule(
        _body(
            _row(
                game_code=P638_SCHEDULE_GAME_CODE,
                draw_date="20990103",
                draw_term="2234",
            )
        ),
        observed_at=OBSERVED_AT,
        active_vetoes=(veto,),
    )

    t539 = _game(result, LotteryType.DAILY_539)
    assert t539.status is ScheduleAuthorityStatus.AUTHORITATIVE_VETO
    assert t539.schedules == ()
    assert t539.vetoes == (veto,)
    assert _game(result, LotteryType.POWER_LOTTO).status is ScheduleAuthorityStatus.COMPLETE


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b"[]",
        b'{"rtCode":0,"content":{}}',
        _body("not-an-object-row"),
    ],
)
def test_malformed_shared_envelope_blocks_both_games(body: bytes) -> None:
    with pytest.raises(OfficialScheduleProviderError):
        parse_official_t539_p638_schedule(body, observed_at=OBSERVED_AT)


def test_payload_provenance_is_exact_and_no_result_source_is_consulted() -> None:
    body = _body(
        _row(game_code=T539_SCHEDULE_GAME_CODE, draw_date="20990102", draw_term="1234"),
        _row(game_code=5118, draw_date="20990102", draw_term="9999"),
    )
    result = parse_official_t539_p638_schedule(body, observed_at=OBSERVED_AT)
    t539 = _game(result, LotteryType.DAILY_539)

    assert result.source_url == SCHEDULE_URL
    assert t539.schedules[0].announcement.target.draw_number == "1234"
    assert all(
        fact.announcement.target.draw_number != "9999"
        for game in result.games
        for fact in game.schedules
    )
