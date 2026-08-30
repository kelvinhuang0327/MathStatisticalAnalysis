"""Disposable SQLite acceptance for canonical T539/P638 schedule authority."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lottolab.application.schedule_sync import (
    P638_SCHEDULE_GAME_CODE,
    T539_SCHEDULE_GAME_CODE,
    AuthoritativeScheduleVeto,
    CanonicalScheduleAuthorityFetchResult,
    CanonicalScheduleAuthorityGameSyncResult,
    CanonicalScheduleAuthoritySyncResult,
    ScheduleAuthorityApplyStatus,
    ScheduleExceptionKind,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import TargetSourceProvenance
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteCanonicalScheduleAuthorityRepository,
    SQLiteFutureDrawIdentityReader,
)
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    parse_official_t539_p638_schedule,
)


def _paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "canonical-authority")}
    )


def _row(game_code: int, draw_number: str | int | None, draw_date: str) -> dict[str, object]:
    return {
        "drawDate": draw_date,
        "drawTerm": draw_number,
        "gameCode": game_code,
    }


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


def _fetch(
    *rows: object,
    observed_at: datetime = datetime(2099, 1, 1, tzinfo=UTC),
    marker: int = 0,
    active_vetoes: tuple[AuthoritativeScheduleVeto, ...] = (),
) -> CanonicalScheduleAuthorityFetchResult:
    return parse_official_t539_p638_schedule(
        _body(*rows, marker=marker),
        observed_at=observed_at,
        active_vetoes=active_vetoes,
    )


def _game_result(
    result: CanonicalScheduleAuthoritySyncResult,
    lottery_type: LotteryType,
) -> CanonicalScheduleAuthorityGameSyncResult:
    return next(
        item for item in result.game_results if item.lottery_type is lottery_type
    )


def _schedule_snapshot(
    paths: LocalDataPaths,
    lottery_type: LotteryType,
    draw_number: str,
) -> tuple[object, ...]:
    with open_database(paths, read_only=True) as connection:
        row = connection.execute(
            """
            SELECT s.*, f.official_game_code, f.scheduled_local_time,
                   f.source_period_identifier, f.immutable_schedule_hash,
                   f.authority_origin
            FROM draw_schedules AS s
            INNER JOIN draw_schedule_facts AS f ON f.schedule_id = s.id
            WHERE s.lottery_type = ? AND s.draw_number = ?
            """,
            (lottery_type.value, draw_number),
        ).fetchone()
    assert row is not None
    return tuple(row)


def test_complete_authority_persists_both_natural_keys_and_generic_reader_resolves(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    result = SQLiteCanonicalScheduleAuthorityRepository(
        paths
    ).apply_canonical_schedule_authority(
        _fetch(
            _row(T539_SCHEDULE_GAME_CODE, "1001", "20990102"),
            _row(P638_SCHEDULE_GAME_CODE, "1001", "20990103"),
        )
    )

    assert _game_result(result, LotteryType.DAILY_539).inserted_count == 1
    assert _game_result(result, LotteryType.POWER_LOTTO).inserted_count == 1
    reader = SQLiteFutureDrawIdentityReader(paths)
    t539 = reader.find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    )
    p638 = reader.find_earliest_unpopulated_future(
        LotteryType.POWER_LOTTO,
        datetime(2099, 1, 1, tzinfo=UTC),
    )
    assert t539 is not None
    assert p638 is not None
    assert t539.announcement.target.draw_number == "1001"
    assert p638.announcement.target.draw_number == "1001"
    with open_database(paths, read_only=True) as connection:
        facts = connection.execute(
            """
            SELECT s.lottery_type, f.official_game_code,
                   f.source_period_identifier, f.scheduled_local_time,
                   f.authority_origin
            FROM draw_schedules AS s
            INNER JOIN draw_schedule_facts AS f ON f.schedule_id = s.id
            ORDER BY s.lottery_type
            """
        ).fetchall()
        observations = connection.execute(
            """
            SELECT lottery_type, event_kind, disposition
            FROM draw_schedule_authority_evidence ORDER BY lottery_type, id
            """
        ).fetchall()
    assert facts == [
        ("DAILY_539", 5120, "1001", "20:30:00", "OFFICIAL"),
        ("POWER_LOTTO", 5134, "1001", "20:30:00", "OFFICIAL"),
    ]
    assert observations == [
        ("DAILY_539", "OFFICIAL_OBSERVATION", "INSERTED"),
        ("POWER_LOTTO", "OFFICIAL_OBSERVATION", "INSERTED"),
    ]
    with open_database(paths) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE draw_schedule_facts SET official_game_code = 1 WHERE schedule_id = 1"
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM draw_schedule_authority_evidence WHERE id = 1")


def test_incomplete_t539_writes_no_schedule_but_valid_p638_is_isolated(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    result = SQLiteCanonicalScheduleAuthorityRepository(
        paths
    ).apply_canonical_schedule_authority(
        _fetch(
            _row(T539_SCHEDULE_GAME_CODE, None, "20990102"),
            _row(P638_SCHEDULE_GAME_CODE, "2001", "20990103"),
        )
    )

    t539 = _game_result(result, LotteryType.DAILY_539)
    p638 = _game_result(result, LotteryType.POWER_LOTTO)
    assert t539.apply_status is ScheduleAuthorityApplyStatus.NO_AUTHORITY
    assert t539.inserted_count == 0
    assert p638.apply_status is ScheduleAuthorityApplyStatus.ACCEPTED
    assert p638.inserted_count == 1
    assert SQLiteFutureDrawIdentityReader(paths).find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    ) is None


def test_same_fact_reobservation_keeps_schedule_immutable_and_appends_provenance(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)
    first = repository.apply_canonical_schedule_authority(
        _fetch(
            _row(T539_SCHEDULE_GAME_CODE, "3001", "20990102"),
            _row(P638_SCHEDULE_GAME_CODE, "4001", "20990103"),
        )
    )
    original = _schedule_snapshot(paths, LotteryType.DAILY_539, "3001")
    second = repository.apply_canonical_schedule_authority(
        _fetch(
            _row(T539_SCHEDULE_GAME_CODE, "3001", "20990102"),
            _row(P638_SCHEDULE_GAME_CODE, "4001", "20990103"),
            observed_at=datetime(2099, 1, 1, 1, tzinfo=UTC),
            marker=1,
        )
    )

    assert _game_result(first, LotteryType.DAILY_539).inserted_count == 1
    assert _game_result(second, LotteryType.DAILY_539).reobserved_count == 1
    assert _schedule_snapshot(paths, LotteryType.DAILY_539, "3001") == original
    with open_database(paths, read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT source_payload_sha256, source_observed_at, disposition
            FROM draw_schedule_authority_evidence
            WHERE lottery_type = 'DAILY_539' AND draw_number = '3001'
            ORDER BY id
            """
        ).fetchall()
    assert len(rows) == 2
    assert rows[0][0] != rows[1][0]
    assert rows[0][1] != rows[1][1]
    assert [row[2] for row in rows] == ["INSERTED", "REOBSERVED"]


def test_game_local_conflict_blocks_only_affected_target_and_never_overwrites(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)
    repository.apply_canonical_schedule_authority(
        _fetch(
            _row(T539_SCHEDULE_GAME_CODE, "5001", "20990102"),
            _row(P638_SCHEDULE_GAME_CODE, "6001", "20990103"),
        )
    )
    original = _schedule_snapshot(paths, LotteryType.DAILY_539, "5001")

    result = repository.apply_canonical_schedule_authority(
        _fetch(
            _row(T539_SCHEDULE_GAME_CODE, "5001", "20990104"),
            _row(P638_SCHEDULE_GAME_CODE, "6002", "20990104"),
            observed_at=datetime(2099, 1, 1, 1, tzinfo=UTC),
            marker=2,
        )
    )

    assert _game_result(result, LotteryType.DAILY_539).apply_status is (
        ScheduleAuthorityApplyStatus.CONFLICT
    )
    assert _game_result(result, LotteryType.POWER_LOTTO).inserted_count == 1
    assert _schedule_snapshot(paths, LotteryType.DAILY_539, "5001") == original
    reader = SQLiteFutureDrawIdentityReader(paths)
    assert reader.get_scheduled_draw(LotteryType.DAILY_539, "5001") is not None
    assert reader.find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    ) is None
    assert reader.get_scheduled_draw(LotteryType.POWER_LOTTO, "6002") is not None


def test_cancellation_preserves_schedule_but_removes_it_from_runnable_resolution(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)
    repository.apply_canonical_schedule_authority(
        _fetch(
            _row(T539_SCHEDULE_GAME_CODE, "7001", "20990102"),
            _row(P638_SCHEDULE_GAME_CODE, "8001", "20990103"),
        )
    )
    original = _schedule_snapshot(paths, LotteryType.DAILY_539, "7001")
    veto = AuthoritativeScheduleVeto(
        lottery_type=LotteryType.DAILY_539,
        official_game_code=T539_SCHEDULE_GAME_CODE,
        draw_number="7001",
        exception_kind=ScheduleExceptionKind.CANCELLATION,
        source=TargetSourceProvenance(
            source_id="TAIWAN_LOTTERY_OFFICIAL_EXCEPTION_NOTICE",
            source_version="fixture-v1",
            source_locator="https://www.taiwanlottery.com/announcement/7001",
            source_sha256="d" * 64,
            observed_at=datetime(2099, 1, 1, 2, tzinfo=UTC),
        ),
    )
    result = repository.apply_canonical_schedule_authority(
        _fetch(
            _row(T539_SCHEDULE_GAME_CODE, "7001", "20990102"),
            _row(P638_SCHEDULE_GAME_CODE, "8001", "20990103"),
            observed_at=datetime(2099, 1, 1, 2, tzinfo=UTC),
            marker=3,
            active_vetoes=(veto,),
        )
    )

    assert _game_result(result, LotteryType.DAILY_539).apply_status is (
        ScheduleAuthorityApplyStatus.VETOED
    )
    assert _schedule_snapshot(paths, LotteryType.DAILY_539, "7001") == original
    reader = SQLiteFutureDrawIdentityReader(paths)
    assert reader.get_scheduled_draw(LotteryType.DAILY_539, "7001") is not None
    assert reader.find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    ) is None


def test_successful_disappearance_blocks_cached_row_but_later_complete_reobservation_restores(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)
    repository.apply_canonical_schedule_authority(
        _fetch(
            _row(T539_SCHEDULE_GAME_CODE, "9001", "20990102"),
            _row(P638_SCHEDULE_GAME_CODE, "9101", "20990103"),
        )
    )
    reader = SQLiteFutureDrawIdentityReader(paths)
    assert reader.find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    ) is not None

    repository.apply_canonical_schedule_authority(
        _fetch(
            _row(P638_SCHEDULE_GAME_CODE, "9101", "20990103"),
            observed_at=datetime(2099, 1, 1, 1, tzinfo=UTC),
            marker=4,
        )
    )
    assert reader.find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    ) is None

    repository.apply_canonical_schedule_authority(
        _fetch(
            _row(T539_SCHEDULE_GAME_CODE, "9001", "20990102"),
            _row(P638_SCHEDULE_GAME_CODE, "9101", "20990103"),
            observed_at=datetime(2099, 1, 1, 2, tzinfo=UTC),
            marker=5,
        )
    )
    restored = reader.find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    )
    assert restored is not None
    assert restored.announcement.target.draw_number == "9001"


def test_source_unavailable_means_no_write_and_does_not_invalidate_cached_explicit_row(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)
    repository.apply_canonical_schedule_authority(
        _fetch(
            _row(T539_SCHEDULE_GAME_CODE, "9201", "20990102"),
            _row(P638_SCHEDULE_GAME_CODE, "9301", "20990103"),
        )
    )
    reader = SQLiteFutureDrawIdentityReader(paths)
    cached = reader.find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    )

    assert cached is not None
    assert cached.announcement.target.draw_number == "9201"


def test_earliest_future_target_order_is_deterministic_and_numeric(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    SQLiteCanonicalScheduleAuthorityRepository(paths).apply_canonical_schedule_authority(
        _fetch(
            _row(T539_SCHEDULE_GAME_CODE, "10", "20990102"),
            _row(T539_SCHEDULE_GAME_CODE, "2", "20990102"),
            _row(P638_SCHEDULE_GAME_CODE, "1", "20990103"),
        )
    )

    earliest = SQLiteFutureDrawIdentityReader(paths).find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    )
    assert earliest is not None
    assert earliest.announcement.target.draw_number == "2"
