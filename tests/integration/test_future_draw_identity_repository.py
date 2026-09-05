"""Disposable-DB acceptance for canonical future draw identities."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lottolab.application.draw_data import RepositoryUnavailableError
from lottolab.application.future_draw_identity import (
    FutureDrawIdentityConflictError,
    FutureDrawIdentityNotFutureError,
    FutureDrawIdentityUnavailableError,
    ManualFutureDrawIdentitySupplementResult,
    OwnerCertifiedFutureDrawIdentityInput,
    ScheduledDrawOutcomeState,
)
from lottolab.application.schedule_sync import (
    CanonicalScheduleSyncConflictError,
    OfficialScheduleFetchResult,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionItemDisposition, IngestionRunStatus
from lottolab.domain.pre_outcome_target import TargetAnnouncement
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    CONTEXT_MIGRATION_CHECKSUM,
    CONTEXT_MIGRATION_NAME,
    CONTEXT_MIGRATION_STATEMENTS,
    CONTEXT_SCHEMA_VERSION,
    DATA_DIRECTORY_ENV,
    MIGRATION_CHECKSUM,
    MIGRATION_NAME,
    MIGRATION_STATEMENTS,
    LocalDataPaths,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteFutureDrawIdentityReader,
    SQLiteManualFutureDrawIdentitySupplementRepository,
    SQLiteOfficialScheduleSyncRepository,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.infrastructure.pre_outcome_target_operational import (
    OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
    parse_owner_certified_future_draw_identity_input,
    select_owner_certified_future_draw_identity,
)
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    SCHEDULE_URL,
    parse_official_b649_schedule,
)

_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"


def _paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "canonical-test-data")}
    )


def _v2_paths(tmp_path: Path) -> LocalDataPaths:
    paths = _paths(tmp_path)
    paths.data_directory.mkdir(mode=0o700, parents=True)
    paths.data_directory.chmod(0o700)
    descriptor = os.open(paths.database, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    paths.database.chmod(0o600)
    with sqlite3.connect(paths.database) as connection:
        for statement in MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, checksum, applied_at)
            VALUES (1, ?, ?, '2099-01-01T00:00:00Z')
            """,
            (MIGRATION_NAME, MIGRATION_CHECKSUM),
        )
        for statement in CONTEXT_MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO schema_migrations (version, name, checksum, applied_at)
            VALUES (?, ?, ?, '2099-01-01T00:00:01Z')
            """,
            (CONTEXT_SCHEMA_VERSION, CONTEXT_MIGRATION_NAME, CONTEXT_MIGRATION_CHECKSUM),
        )
    return paths


def _manual_input(
    *,
    draw_number: str,
    draw_date: str,
    scheduled_at: str,
    variant: str = "canonical",
) -> tuple[OwnerCertifiedFutureDrawIdentityInput, TargetAnnouncement]:
    document = {
        "announcements": [
            {
                "schedule_timezone": "Asia/Taipei",
                "scheduled_at": scheduled_at,
                "source": {
                    "observed_at": "2099-01-01T00:00:00Z",
                    "source_id": "TAIWAN_LOTTERY_OFFICIAL_SCHEDULE",
                    "source_locator": (
                        "https://www.taiwanlottery.com/schedule/"
                        f"{draw_number}?variant={variant}"
                    ),
                    "source_payload_sha256": hashlib.sha256(variant.encode()).hexdigest(),
                    "source_version": "taiwan-lottery-official-schedule-v1",
                },
                "target": {
                    "draw_date": draw_date,
                    "draw_number": draw_number,
                    "lottery_type": "BIG_LOTTO",
                },
            }
        ],
        "schema_version": OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
    }
    encoded = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    parsed = parse_owner_certified_future_draw_identity_input(
        encoded,
        source_filename=f"synthetic-{draw_number}-{variant}.json",
    )
    selected = select_owner_certified_future_draw_identity(
        parsed,
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=draw_number,
    )
    return parsed, selected


def _commit_schedule(
    repository: SQLiteManualFutureDrawIdentitySupplementRepository,
    *,
    draw_number: str,
    draw_date: str,
    scheduled_at: str,
    variant: str = "canonical",
) -> ManualFutureDrawIdentitySupplementResult:
    parsed, selected = _manual_input(
        draw_number=draw_number,
        draw_date=draw_date,
        scheduled_at=scheduled_at,
        variant=variant,
    )
    return repository.apply_owner_certified_supplement(
        parsed,
        selected,
        parsed.input_sha256,
    )


def _insert_completed_draw(
    paths: LocalDataPaths,
    *,
    draw_number: str,
    draw_date: str,
) -> None:
    parsed = parse_draw_csv(
        "\n".join(
            (
                _HEADER,
                (
                    f"BIG_LOTTO,{draw_number},{draw_date},"
                    "1|3|9|17|24|49,7,synthetic-completed"
                ),
                "",
            )
        ),
        filename=f"completed-{draw_number}.csv",
    )
    assert parsed.is_valid, parsed.errors
    result = SQLiteDrawDataRepository(paths).apply_valid_import(parsed)
    assert result.status is IngestionRunStatus.SUCCESS
    assert result.inserted_count == 1


def _schedule_row(paths: LocalDataPaths, draw_number: str) -> tuple[object, ...]:
    with open_database(paths, read_only=True) as connection:
        row = connection.execute(
            "SELECT * FROM draw_schedules WHERE lottery_type = ? AND draw_number = ?",
            (LotteryType.BIG_LOTTO.value, draw_number),
        ).fetchone()
    assert row is not None
    return tuple(row)


def _official_schedule_body(*rows: tuple[str, str]) -> bytes:
    return json.dumps(
        {
            "content": {
                "nextDrawDateList": [
                    {
                        "drawDate": draw_date,
                        "drawTerm": draw_number,
                        "gameCode": 5118,
                    }
                    for draw_number, draw_date in rows
                ]
            },
            "rtCode": 0,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _official_fetch(
    body: bytes,
    *,
    observed_at: datetime = datetime(2099, 1, 1, tzinfo=UTC),
    source_url: str = SCHEDULE_URL,
) -> OfficialScheduleFetchResult:
    announcements = parse_official_b649_schedule(
        body,
        observed_at=observed_at,
        source_url=source_url,
    )
    return OfficialScheduleFetchResult(
        provider_id="TAIWAN_LOTTERY_OFFICIAL_SCHEDULE",
        provider_version="taiwan-lottery-official-schedule-v1",
        source_url=source_url,
        source_payload_sha256=hashlib.sha256(body).hexdigest(),
        observed_at=observed_at,
        announcements=announcements,
    )


def test_official_schedule_sync_inserts_explicit_identities_and_audits_batch(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    body = _official_schedule_body(
        ("209900101", "20990102"),
        ("209900102", "20990103"),
    )

    result = SQLiteOfficialScheduleSyncRepository(paths).apply_official_schedule_sync(
        _official_fetch(body)
    )

    assert result.status is IngestionRunStatus.SUCCESS
    assert result.target_draw_numbers == ("209900101", "209900102")
    assert result.total_count == 2
    assert result.inserted_count == 2
    assert result.skipped_count == 0
    assert result.conflict_count == 0
    reader = SQLiteFutureDrawIdentityReader(paths)
    for draw_number in result.target_draw_numbers:
        record = reader.get_scheduled_draw(LotteryType.BIG_LOTTO, draw_number)
        assert record is not None
        assert record.outcome_state is ScheduledDrawOutcomeState.NOT_POPULATED
    with open_database(paths, read_only=True) as connection:
        audit = connection.execute(
            """
            SELECT r.operation_type, r.status, r.total_count, r.inserted_count,
                   c.trigger, c.provider, c.fetched_count
            FROM ingestion_runs AS r
            INNER JOIN ingestion_run_context AS c ON c.ingestion_run_id = r.id
            WHERE r.id = ?
            """,
            (result.run_id,),
        ).fetchone()
        items = connection.execute(
            """
            SELECT disposition, draw_number
            FROM ingestion_items
            WHERE ingestion_run_id = ?
            ORDER BY source_row_number
            """,
            (result.run_id,),
        ).fetchall()
    assert audit == (
        "OFFICIAL_SCHEDULE_SYNC",
        "SUCCESS",
        2,
        2,
        "OFFICIAL_SCHEDULE_SYNC",
        "TAIWAN_LOTTERY_OFFICIAL_SCHEDULE",
        2,
    )
    assert items == [("INSERTED", "209900101"), ("INSERTED", "209900102")]


def test_official_schedule_sync_repeat_is_exact_audited_no_op_even_at_later_observation(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    body = _official_schedule_body(("209900110", "20990102"))
    repository = SQLiteOfficialScheduleSyncRepository(paths)
    first = repository.apply_official_schedule_sync(_official_fetch(body))
    original = _schedule_row(paths, "209900110")

    second = repository.apply_official_schedule_sync(
        _official_fetch(body, observed_at=datetime(2099, 1, 1, 1, tzinfo=UTC))
    )

    assert second.status is IngestionRunStatus.SUCCESS
    assert second.inserted_count == 0
    assert second.skipped_count == 1
    assert second.exact_duplicate_count == 1
    assert second.completed_count == 0
    assert _schedule_row(paths, "209900110") == original
    with open_database(paths, read_only=True) as connection:
        runs = connection.execute(
            """
            SELECT status, inserted_count, skipped_count
            FROM ingestion_runs
            WHERE operation_type = 'OFFICIAL_SCHEDULE_SYNC'
            ORDER BY started_at, id
            """
        ).fetchall()
    assert runs == [("SUCCESS", 1, 0), ("SUCCESS", 0, 1)]
    assert first.run_id != second.run_id


def test_official_schedule_sync_same_identity_different_envelope_is_audited_no_op(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    first_body = _official_schedule_body(("209900110", "20990102"))
    repository = SQLiteOfficialScheduleSyncRepository(paths)
    first = repository.apply_official_schedule_sync(_official_fetch(first_body))
    original = _schedule_row(paths, "209900110")

    second_body = _official_schedule_body(
        ("209900110", "20990102"),
        ("209900111", "20990106"),
    )
    assert hashlib.sha256(first_body).hexdigest() != hashlib.sha256(second_body).hexdigest()

    second = repository.apply_official_schedule_sync(
        _official_fetch(second_body, observed_at=datetime(2099, 1, 1, 1, tzinfo=UTC))
    )

    assert second.status is IngestionRunStatus.SUCCESS
    assert second.total_count == 2
    assert second.inserted_count == 1
    assert second.skipped_count == 1
    assert second.exact_duplicate_count == 1
    assert second.conflict_count == 0
    assert _schedule_row(paths, "209900110") == original

    with open_database(paths, read_only=True) as connection:
        rows = connection.execute(
            "SELECT draw_number FROM draw_schedules ORDER BY draw_number"
        ).fetchall()
        assert rows == [("209900110",), ("209900111",)]
        runs = connection.execute(
            """
            SELECT id, source_sha256, inserted_count, skipped_count, conflict_count
            FROM ingestion_runs
            WHERE operation_type = 'OFFICIAL_SCHEDULE_SYNC'
            ORDER BY started_at, id
            """
        ).fetchall()
        items = connection.execute(
            """
            SELECT draw_number, disposition
            FROM ingestion_items
            WHERE ingestion_run_id = ?
            ORDER BY source_row_number
            """,
            (second.run_id,),
        ).fetchall()
    assert runs == [
        (first.run_id, hashlib.sha256(first_body).hexdigest(), 1, 0, 0),
        (second.run_id, hashlib.sha256(second_body).hexdigest(), 1, 1, 0),
    ]
    assert items == [("209900110", "SKIPPED_DUPLICATE"), ("209900111", "INSERTED")]


def test_official_schedule_sync_source_identity_mutation_conflicts(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteOfficialScheduleSyncRepository(paths)
    body = _official_schedule_body(("209900125", "20990102"))
    first_url = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/NextDrawDate"
    second_url = "https://www.taiwanlottery.com/TLCAPIWeB/Lottery/NextDrawDate"
    repository.apply_official_schedule_sync(_official_fetch(body, source_url=first_url))
    original = _schedule_row(paths, "209900125")

    conflicting = _official_fetch(body, source_url=second_url)
    with pytest.raises(CanonicalScheduleSyncConflictError) as raised:
        repository.apply_official_schedule_sync(conflicting)

    assert raised.value.result.status is IngestionRunStatus.FAILED
    assert raised.value.result.conflict_count == 1
    assert raised.value.result.failed_count == 0
    assert _schedule_row(paths, "209900125") == original
    with open_database(paths, read_only=True) as connection:
        audit = connection.execute(
            """
            SELECT status, inserted_count, skipped_count, conflict_count, failed_count
            FROM ingestion_runs
            WHERE id = ?
            """,
            (raised.value.result.run_id,),
        ).fetchone()
        item = connection.execute(
            """
            SELECT disposition
            FROM ingestion_items
            WHERE ingestion_run_id = ?
            """,
            (raised.value.result.run_id,),
        ).fetchone()
    assert audit == ("FAILED", 0, 0, 1, 0)
    assert item == ("CONFLICT",)


def test_official_schedule_sync_conflict_is_audited_without_mutating_schedule(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteOfficialScheduleSyncRepository(paths)
    first_body = _official_schedule_body(("209900120", "20990102"))
    repository.apply_official_schedule_sync(_official_fetch(first_body))
    original = _schedule_row(paths, "209900120")

    conflicting = _official_fetch(_official_schedule_body(("209900120", "20990103")))
    with pytest.raises(CanonicalScheduleSyncConflictError) as raised:
        repository.apply_official_schedule_sync(conflicting)

    assert raised.value.result.status is IngestionRunStatus.FAILED
    assert raised.value.result.conflict_count == 1
    assert raised.value.result.failed_count == 0
    assert _schedule_row(paths, "209900120") == original
    with open_database(paths, read_only=True) as connection:
        audit = connection.execute(
            """
            SELECT status, inserted_count, skipped_count, conflict_count, failed_count
            FROM ingestion_runs
            WHERE id = ?
            """,
            (raised.value.result.run_id,),
        ).fetchone()
        item = connection.execute(
            """
            SELECT disposition
            FROM ingestion_items
            WHERE ingestion_run_id = ?
            """,
            (raised.value.result.run_id,),
        ).fetchone()
    assert audit == ("FAILED", 0, 0, 1, 0)
    assert item == ("CONFLICT",)


def test_official_schedule_sync_batch_conflict_has_no_partial_schedule_writes(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteOfficialScheduleSyncRepository(paths)
    repository.apply_official_schedule_sync(
        _official_fetch(_official_schedule_body(("209900130", "20990102")))
    )
    original = _schedule_row(paths, "209900130")

    conflicting_batch = _official_fetch(
        _official_schedule_body(
            ("209900130", "20990103"),
            ("209900131", "20990104"),
        )
    )
    with pytest.raises(CanonicalScheduleSyncConflictError) as raised:
        repository.apply_official_schedule_sync(conflicting_batch)

    assert raised.value.result.total_count == 2
    assert raised.value.result.conflict_count == 1
    assert raised.value.result.failed_count == 1
    assert _schedule_row(paths, "209900130") == original
    with open_database(paths, read_only=True) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM draw_schedules WHERE draw_number = '209900131'"
        ).fetchone() == (0,)
        items = connection.execute(
            """
            SELECT draw_number, disposition
            FROM ingestion_items
            WHERE ingestion_run_id = ?
            ORDER BY source_row_number
            """,
            (raised.value.result.run_id,),
        ).fetchall()
    assert items == [("209900130", "CONFLICT"), ("209900131", "FAILED")]


def test_official_schedule_sync_does_not_reintroduce_completed_draw_as_unresolved(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _insert_completed_draw(paths, draw_number="209900140", draw_date="2099-01-02")

    result = SQLiteOfficialScheduleSyncRepository(paths).apply_official_schedule_sync(
        _official_fetch(_official_schedule_body(("209900140", "20990102")))
    )

    assert result.status is IngestionRunStatus.SUCCESS
    assert result.inserted_count == 0
    assert result.skipped_count == 1
    assert result.exact_duplicate_count == 0
    assert result.completed_count == 1
    with open_database(paths, read_only=True) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM draw_schedules WHERE draw_number = '209900140'"
        ).fetchone() == (0,)


def test_due_reader_prioritizes_due_identity_and_rolls_to_future_after_outcome(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    writer = SQLiteManualFutureDrawIdentitySupplementRepository(paths)
    reader = SQLiteFutureDrawIdentityReader(paths)
    _commit_schedule(
        writer,
        draw_number="209900150",
        draw_date="2099-01-02",
        scheduled_at="2099-01-02T12:30:00Z",
    )
    _commit_schedule(
        writer,
        draw_number="209900151",
        draw_date="2099-01-03",
        scheduled_at="2099-01-03T12:30:00Z",
    )
    deadline = datetime(2099, 1, 2, 12, 30, tzinfo=UTC)

    due = reader.find_earliest_unpopulated_due(LotteryType.BIG_LOTTO, deadline)
    future = reader.find_earliest_unpopulated_future(
        LotteryType.BIG_LOTTO,
        datetime(2099, 1, 2, 12, 31, tzinfo=UTC),
    )
    assert due is not None
    assert due.announcement.target.draw_number == "209900150"
    assert future is not None
    assert future.announcement.target.draw_number == "209900151"

    _insert_completed_draw(paths, draw_number="209900150", draw_date="2099-01-02")

    assert reader.find_earliest_unpopulated_due(LotteryType.BIG_LOTTO, deadline) is None
    rolled = reader.find_earliest_unpopulated_future(
        LotteryType.BIG_LOTTO,
        datetime(2099, 1, 2, 12, 31, tzinfo=UTC),
    )
    assert rolled is not None
    assert rolled.announcement.target.draw_number == "209900151"


def test_future_schedule_has_no_outcome_and_state_is_derived_from_completed_draw(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    writer = SQLiteManualFutureDrawIdentitySupplementRepository(paths)
    reader = SQLiteFutureDrawIdentityReader(paths)
    parsed, selected = _manual_input(
        draw_number="209900001",
        draw_date="2099-01-02",
        scheduled_at="2099-01-02T12:30:00Z",
    )
    before_preview = (
        hashlib.sha256(paths.database.read_bytes()).hexdigest(),
        paths.database.stat().st_size,
        paths.database.stat().st_mtime_ns,
    )

    preview = writer.preview_owner_certified_supplement(
        parsed,
        selected,
        parsed.input_sha256,
    )

    after_preview = (
        hashlib.sha256(paths.database.read_bytes()).hexdigest(),
        paths.database.stat().st_size,
        paths.database.stat().st_mtime_ns,
    )
    assert preview.zero_write is True
    assert preview.disposition is IngestionItemDisposition.INSERTED
    assert after_preview == before_preview

    committed = writer.apply_owner_certified_supplement(
        parsed,
        selected,
        parsed.input_sha256,
    )
    schedule_before_outcome = _schedule_row(paths, "209900001")
    record = reader.get_scheduled_draw(LotteryType.BIG_LOTTO, "209900001")

    assert committed.disposition is IngestionItemDisposition.INSERTED
    assert record is not None
    assert record.outcome_state is ScheduledDrawOutcomeState.NOT_POPULATED
    assert record.outcome_draw_internal_id is None
    assert reader.find_earliest_unpopulated_future(
        LotteryType.BIG_LOTTO,
        datetime(2099, 1, 1, tzinfo=UTC),
    ) == record
    with open_database(paths, read_only=True) as connection:
        columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_xinfo(draw_schedules)")
        }
    assert columns.isdisjoint(
        {
            "main_numbers",
            "main_numbers_json",
            "special_numbers",
            "special_numbers_json",
            "winning_numbers",
            "outcome_state",
            "outcome_hash",
            "prize_result",
        }
    )

    _insert_completed_draw(
        paths,
        draw_number="209900001",
        draw_date="2099-01-02",
    )
    populated = reader.get_scheduled_draw(LotteryType.BIG_LOTTO, "209900001")

    assert populated is not None
    assert populated.outcome_state is ScheduledDrawOutcomeState.POPULATED
    assert populated.outcome_draw_internal_id is not None
    assert _schedule_row(paths, "209900001") == schedule_before_outcome
    assert reader.find_earliest_unpopulated_future(
        LotteryType.BIG_LOTTO,
        datetime(2099, 1, 1, tzinfo=UTC),
    ) is None
    completed = SQLiteDrawDataRepository(paths).get_draw(
        LotteryType.BIG_LOTTO,
        "209900001",
    )
    assert completed is not None
    assert completed.main_numbers == (1, 3, 9, 17, 24, 49)
    assert completed.special_numbers == (7,)
    with open_database(paths) as connection:
        connection.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.IntegrityError, match="date conflicts"):
            connection.execute(
                """
                UPDATE draws SET draw_date = '2099-01-03'
                WHERE lottery_type = 'BIG_LOTTO' AND draw_number = '209900001'
                """
            )
        connection.rollback()
        connection.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.IntegrityError, match="date conflicts"):
            connection.execute(
                """
                UPDATE draws SET draw_number = '209900099'
                WHERE lottery_type = 'BIG_LOTTO' AND draw_number = '209900001'
                """
            )
        connection.rollback()
    unchanged_completed = SQLiteDrawDataRepository(paths).get_draw(
        LotteryType.BIG_LOTTO,
        "209900001",
    )
    assert unchanged_completed is not None
    assert unchanged_completed.draw_number == "209900001"
    assert unchanged_completed.draw_date.isoformat() == "2099-01-02"


def test_earliest_future_order_is_numeric_and_excludes_populated_rows(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    writer = SQLiteManualFutureDrawIdentitySupplementRepository(paths)
    reader = SQLiteFutureDrawIdentityReader(paths)
    _commit_schedule(
        writer,
        draw_number="10",
        draw_date="2099-01-02",
        scheduled_at="2099-01-02T12:30:00Z",
    )
    _commit_schedule(
        writer,
        draw_number="2",
        draw_date="2099-01-02",
        scheduled_at="2099-01-02T12:30:00Z",
    )
    _commit_schedule(
        writer,
        draw_number="11",
        draw_date="2099-01-03",
        scheduled_at="2099-01-03T12:30:00Z",
    )

    earliest = reader.find_earliest_unpopulated_future(
        LotteryType.BIG_LOTTO,
        datetime(2099, 1, 1, tzinfo=UTC),
    )
    assert earliest is not None
    assert earliest.announcement.target.draw_number == "2"

    _insert_completed_draw(paths, draw_number="2", draw_date="2099-01-02")
    next_record = reader.find_earliest_unpopulated_future(
        LotteryType.BIG_LOTTO,
        datetime(2099, 1, 1, tzinfo=UTC),
    )
    assert next_record is not None
    assert next_record.announcement.target.draw_number == "10"
    after_cutoff = reader.find_earliest_unpopulated_future(
        LotteryType.BIG_LOTTO,
        datetime(2099, 1, 2, 12, 30, tzinfo=UTC),
    )
    assert after_cutoff is not None
    assert after_cutoff.announcement.target.draw_number == "11"


def test_exact_duplicate_is_audited_no_op_and_conflict_cannot_mutate_schedule(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    writer = SQLiteManualFutureDrawIdentitySupplementRepository(paths)
    first = _commit_schedule(
        writer,
        draw_number="209900010",
        draw_date="2099-01-02",
        scheduled_at="2099-01-02T12:30:00Z",
    )
    original = _schedule_row(paths, "209900010")

    duplicate = _commit_schedule(
        writer,
        draw_number="209900010",
        draw_date="2099-01-02",
        scheduled_at="2099-01-02T12:30:00Z",
    )

    assert duplicate.run_id != first.run_id
    assert duplicate.disposition is IngestionItemDisposition.SKIPPED_DUPLICATE
    assert duplicate.inserted_count == 0
    assert duplicate.skipped_count == 1
    assert _schedule_row(paths, "209900010") == original

    conflict_input, conflict_target = _manual_input(
        draw_number="209900010",
        draw_date="2099-01-03",
        scheduled_at="2099-01-03T12:30:00Z",
        variant="conflicting-immutable-material",
    )
    with pytest.raises(FutureDrawIdentityConflictError) as raised:
        writer.apply_owner_certified_supplement(
            conflict_input,
            conflict_target,
            conflict_input.input_sha256,
        )

    assert raised.value.result.status is IngestionRunStatus.FAILED
    assert raised.value.result.disposition is IngestionItemDisposition.CONFLICT
    assert raised.value.result.conflict_count == 1
    assert _schedule_row(paths, "209900010") == original
    with open_database(paths, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM draw_schedules").fetchone() == (1,)
        audits = connection.execute(
            """
            SELECT r.status, r.inserted_count, r.skipped_count, r.conflict_count,
                   c.trigger, i.disposition, i.normalized_record_hash
            FROM ingestion_runs AS r
            INNER JOIN ingestion_run_context AS c ON c.ingestion_run_id = r.id
            INNER JOIN ingestion_items AS i ON i.ingestion_run_id = r.id
            WHERE r.operation_type = 'MANUAL_FUTURE_IDENTITY_SUPPLEMENT'
            ORDER BY r.started_at, r.id
            """
        ).fetchall()
    assert len(audits) == 3
    assert {str(row[4]) for row in audits} == {"MANUAL_FUTURE_IDENTITY_SUPPLEMENT"}
    assert {str(row[5]) for row in audits} == {
        "INSERTED",
        "SKIPPED_DUPLICATE",
        "CONFLICT",
    }
    assert all(len(str(row[6])) == 64 for row in audits)


def test_schedule_after_outcome_and_mismatching_outcome_are_rejected_atomically(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    writer = SQLiteManualFutureDrawIdentitySupplementRepository(paths)
    _insert_completed_draw(paths, draw_number="209900020", draw_date="2099-01-02")
    completed_input, completed_target = _manual_input(
        draw_number="209900020",
        draw_date="2099-01-02",
        scheduled_at="2099-01-02T12:30:00Z",
    )
    with pytest.raises(FutureDrawIdentityNotFutureError):
        writer.preview_owner_certified_supplement(
            completed_input,
            completed_target,
            completed_input.input_sha256,
        )
    with pytest.raises(FutureDrawIdentityNotFutureError):
        writer.apply_owner_certified_supplement(
            completed_input,
            completed_target,
            completed_input.input_sha256,
        )
    with open_database(paths, read_only=True) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM draw_schedules WHERE draw_number = '209900020'"
        ).fetchone() == (0,)
    completed = SQLiteDrawDataRepository(paths).get_draw(
        LotteryType.BIG_LOTTO,
        "209900020",
    )
    assert completed is not None
    with open_database(paths) as connection:
        connection.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.IntegrityError, match="completed draw already exists"):
            connection.execute(
                """
                INSERT INTO draw_schedules (
                    lottery_type, draw_number, draw_date, scheduled_at,
                    schedule_timezone, source_id, source_version, source_locator,
                    source_payload_sha256, source_observed_at,
                    normalized_announcement_hash, ingestion_run_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "BIG_LOTTO",
                    "209900020",
                    "2099-01-02",
                    "2099-01-02T12:30:00.000000Z",
                    "Asia/Taipei",
                    completed_target.source.source_id,
                    completed_target.source.source_version,
                    completed_target.source.source_locator,
                    completed_target.source.source_payload_sha256,
                    "2099-01-01T00:00:00.000000Z",
                    "c" * 64,
                    completed.ingestion_run_id,
                    "2099-01-01T01:00:00.000000Z",
                ),
            )
        connection.rollback()

    scheduled = _commit_schedule(
        writer,
        draw_number="209900021",
        draw_date="2099-01-02",
        scheduled_at="2099-01-02T12:30:00Z",
    )
    with open_database(paths, read_only=True) as connection:
        before_runs = int(
            connection.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0]
        )
    with pytest.raises(RepositoryUnavailableError):
        _insert_completed_draw(
            paths,
            draw_number="209900021",
            draw_date="2099-01-03",
        )
    with open_database(paths, read_only=True) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM draws WHERE draw_number = '209900021'"
        ).fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone() == (
            before_runs,
        )
        context = connection.execute(
            "SELECT trigger, fetched_count FROM ingestion_run_context WHERE ingestion_run_id = ?",
            (scheduled.run_id,),
        ).fetchone()
    assert context == ("MANUAL_FUTURE_IDENTITY_SUPPLEMENT", 1)

    _insert_completed_draw(paths, draw_number="209900021", draw_date="2099-01-02")
    populated = SQLiteFutureDrawIdentityReader(paths).get_scheduled_draw(
        LotteryType.BIG_LOTTO,
        "209900021",
    )
    assert populated is not None
    assert populated.outcome_state is ScheduledDrawOutcomeState.POPULATED


def test_manual_preview_rejects_valid_v2_without_migrating_or_writing(tmp_path: Path) -> None:
    paths = _v2_paths(tmp_path)
    writer = SQLiteManualFutureDrawIdentitySupplementRepository(paths)
    parsed, selected = _manual_input(
        draw_number="209900030",
        draw_date="2099-01-02",
        scheduled_at="2099-01-02T12:30:00Z",
    )
    before = (
        hashlib.sha256(paths.database.read_bytes()).hexdigest(),
        paths.database.stat().st_size,
        paths.database.stat().st_mtime_ns,
    )

    with pytest.raises(FutureDrawIdentityUnavailableError):
        writer.preview_owner_certified_supplement(
            parsed,
            selected,
            parsed.input_sha256,
        )

    after = (
        hashlib.sha256(paths.database.read_bytes()).hexdigest(),
        paths.database.stat().st_size,
        paths.database.stat().st_mtime_ns,
    )
    assert after == before
    with sqlite3.connect(f"file:{paths.database}?mode=ro", uri=True) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_schema WHERE name = 'draw_schedules'"
        ).fetchone() is None
        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone() == (
            CONTEXT_SCHEMA_VERSION,
        )
