"""Disposable-DB acceptance for the BIG_LOTTO canonical schedule authority."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lottolab.application.future_draw_identity import FutureDrawIdentityUnavailableError
from lottolab.application.schedule_sync import (
    BIG_LOTTO_SCHEDULE_GAME_CODE,
    AuthoritativeScheduleVeto,
    CanonicalScheduleAuthorityFetchResult,
    ScheduleAuthorityApplyStatus,
    ScheduleAuthorityStatus,
    ScheduleExceptionKind,
    SynchronizeCanonicalScheduleAuthority,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import TargetSourceProvenance
from lottolab.infrastructure.persistence import (
    future_draw_identity_repository as repository_module,
)
from lottolab.infrastructure.persistence.draw_schema import (
    CONTEXT_MIGRATION_CHECKSUM,
    CONTEXT_MIGRATION_NAME,
    CONTEXT_MIGRATION_STATEMENTS,
    DATA_DIRECTORY_ENV,
    DRAW_SCHEDULE_MIGRATION_CHECKSUM,
    DRAW_SCHEDULE_MIGRATION_NAME,
    DRAW_SCHEDULE_MIGRATION_STATEMENTS,
    MIGRATION_CHECKSUM,
    MIGRATION_NAME,
    MIGRATION_STATEMENTS,
    LocalDataPaths,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteCanonicalScheduleAuthorityRepository,
    SQLiteFutureDrawIdentityReader,
    SQLiteOfficialScheduleSyncRepository,
)
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    OfficialHttpsClient,
    TaiwanLotteryBigLottoCanonicalScheduleAuthorityProvider,
    TaiwanLotteryScheduleProvider,
    parse_official_biglotto_schedule_authority,
)
from lottolab.interfaces.cli import b649_canonical_schedule_authority_sync as cli_module
from lottolab.interfaces.cli.main import app

OBSERVED_AT = datetime(2099, 1, 1, tzinfo=UTC)
LATER_OBSERVED_AT = datetime(2099, 1, 1, 2, tzinfo=UTC)
COMMIT_AT = datetime(2099, 1, 1, 1, tzinfo=UTC)


def _paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "b649-canonical-data")}
    )


def _row(*, draw_number: object, draw_date: str) -> dict[str, object]:
    return {
        "drawDate": draw_date,
        "drawTerm": draw_number,
        "gameCode": BIG_LOTTO_SCHEDULE_GAME_CODE,
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
    body: bytes,
    *,
    observed_at: datetime = OBSERVED_AT,
) -> CanonicalScheduleAuthorityFetchResult:
    return parse_official_biglotto_schedule_authority(body, observed_at=observed_at)


def _repository(
    paths: LocalDataPaths,
    *,
    clock: Callable[[], datetime] = lambda: COMMIT_AT,
) -> SQLiteCanonicalScheduleAuthorityRepository:
    return SQLiteCanonicalScheduleAuthorityRepository(
        paths,
        initialize=False,
        clock=clock,
    )


def _schedule_rows(paths: LocalDataPaths) -> list[tuple[object, ...]]:
    with open_database(paths, read_only=True) as connection:
        return [tuple(row) for row in connection.execute("SELECT * FROM draw_schedules")]


def _fact_rows(paths: LocalDataPaths) -> list[tuple[object, ...]]:
    with open_database(paths, read_only=True) as connection:
        return [tuple(row) for row in connection.execute("SELECT * FROM draw_schedule_facts")]


def test_provider_use_case_and_repository_persist_official_b649_fact_before_outcome(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    body = _body(_row(draw_number="115000087", draw_date="20990102"))
    provider = TaiwanLotteryBigLottoCanonicalScheduleAuthorityProvider(
        https_client=OfficialHttpsClient(
            transport=lambda _request, _context, _timeout, _limit: body
        )
    )

    result = SynchronizeCanonicalScheduleAuthority(
        provider,
        _repository(paths),
    ).execute(observed_at=OBSERVED_AT)

    game = result.game_results[0]
    assert game.lottery_type is LotteryType.BIG_LOTTO
    assert game.official_game_code == 5118
    assert game.authority_status is ScheduleAuthorityStatus.COMPLETE
    assert game.apply_status is ScheduleAuthorityApplyStatus.ACCEPTED
    assert game.inserted_count == 1
    assert game.target_draw_numbers == ("115000087",)
    assert len(game.immutable_schedule_hashes) == 1

    with open_database(paths, read_only=True) as connection:
        schedule = connection.execute(
            "SELECT lottery_type, draw_number, draw_date, scheduled_at, schedule_timezone, "
            "source_id, source_version, source_locator, source_payload_sha256, "
            "source_observed_at, normalized_announcement_hash, ingestion_run_id, created_at "
            "FROM draw_schedules"
        ).fetchone()
        fact = connection.execute(
            "SELECT schedule_id, official_game_code, scheduled_local_time, "
            "source_period_identifier, immutable_schedule_hash, authority_origin "
            "FROM draw_schedule_facts"
        ).fetchone()
        audit = connection.execute(
            "SELECT r.operation_type, r.status, r.source_sha256, r.parser_version, "
            "c.provider, c.provider_version, i.disposition "
            "FROM ingestion_runs AS r "
            "JOIN ingestion_run_context AS c ON c.ingestion_run_id = r.id "
            "JOIN ingestion_items AS i ON i.ingestion_run_id = r.id"
        ).fetchone()
        outcome_count = connection.execute("SELECT COUNT(*) FROM draws").fetchone()[0]

    assert schedule is not None
    assert fact is not None
    assert schedule[:8] == (
        "BIG_LOTTO",
        "115000087",
        "2099-01-02",
        "2099-01-02T12:30:00.000000Z",
        "Asia/Taipei",
        "TAIWAN_LOTTERY_OFFICIAL_SCHEDULE",
        "taiwan-lottery-official-schedule-v1",
        "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/NextDrawDate",
    )
    assert fact[0] == 1
    assert fact[1:] == (
        5118,
        "20:30:00",
        "115000087",
        game.immutable_schedule_hashes[0],
        "OFFICIAL",
    )
    assert audit == (
        "OFFICIAL_SCHEDULE_SYNC",
        "SUCCESS",
        result.source_payload_sha256,
        "lottolab-t539-p638-official-schedule-json-v1",
        "TAIWAN_LOTTERY_OFFICIAL_SCHEDULE",
        "taiwan-lottery-official-schedule-v1",
        "INSERTED",
    )
    assert outcome_count == 0
    assert len({schedule[8], schedule[10], fact[4]}) == 3

    ordinary = SQLiteFutureDrawIdentityReader(paths).get_scheduled_draw(
        LotteryType.BIG_LOTTO,
        "115000087",
    )
    strict = SQLiteFutureDrawIdentityReader(paths, require_active_authority=True)
    assert ordinary is not None
    assert ordinary.immutable_schedule_sha256 == game.immutable_schedule_hashes[0]
    assert strict.get_scheduled_draw(LotteryType.BIG_LOTTO, "115000087") == ordinary
    assert strict.find_earliest_unpopulated_future(
        LotteryType.BIG_LOTTO,
        OBSERVED_AT,
    ) == ordinary


def test_canonical_fact_upgrades_existing_ordinary_b649_announcement_without_row_mutation(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    body = _body(_row(draw_number="115000087", draw_date="20990102"), marker=1)
    ordinary_provider = TaiwanLotteryScheduleProvider(
        https_client=OfficialHttpsClient(
            transport=lambda _request, _context, _timeout, _limit: body
        )
    )
    ordinary = ordinary_provider.fetch_schedule(observed_at=OBSERVED_AT)
    SQLiteOfficialScheduleSyncRepository(paths).apply_official_schedule_sync(ordinary)
    before = _schedule_rows(paths)

    canonical_body = _body(_row(draw_number="115000087", draw_date="20990102"), marker=2)
    result = _repository(paths).apply_canonical_schedule_authority(_fetch(canonical_body))

    after = _schedule_rows(paths)
    assert after == before
    assert result.game_results[0].inserted_count == 1
    assert _fact_rows(paths)[0][1:] == (
        5118,
        "20:30:00",
        "115000087",
        result.game_results[0].immutable_schedule_hashes[0],
        "OFFICIAL",
    )
    with open_database(paths, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM draws").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM draw_schedule_authority_evidence "
            "WHERE event_kind = 'OFFICIAL_OBSERVATION' AND disposition = 'INSERTED'"
        ).fetchone()[0] == 1


def test_exact_b649_reobservation_keeps_fact_and_schedule_immutable_but_appends_evidence(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    repository = _repository(paths)
    first = repository.apply_canonical_schedule_authority(
        _fetch(_body(_row(draw_number="115000087", draw_date="20990102"), marker=1))
    )
    schedule_before = _schedule_rows(paths)
    fact_before = _fact_rows(paths)

    second = repository.apply_canonical_schedule_authority(
        _fetch(
            _body(_row(draw_number="115000087", draw_date="20990102"), marker=2),
            observed_at=LATER_OBSERVED_AT,
        )
    )

    assert first.game_results[0].inserted_count == 1
    assert second.game_results[0].reobserved_count == 1
    assert _schedule_rows(paths) == schedule_before
    assert _fact_rows(paths) == fact_before
    with open_database(paths, read_only=True) as connection:
        evidence = connection.execute(
            "SELECT disposition, source_payload_sha256, source_observed_at, "
            "immutable_schedule_hash FROM draw_schedule_authority_evidence "
            "ORDER BY id"
        ).fetchall()
    assert [row[0] for row in evidence] == ["INSERTED", "REOBSERVED"]
    assert evidence[0][1] != evidence[1][1]
    assert evidence[0][2] != evidence[1][2]
    assert evidence[0][3] == evidence[1][3] == fact_before[0][4]


def test_typed_b649_cancellation_remains_blocking_after_normal_reobservation(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    repository = _repository(paths)
    repository.apply_canonical_schedule_authority(
        _fetch(_body(_row(draw_number="115000087", draw_date="20990102")))
    )
    veto = AuthoritativeScheduleVeto(
        lottery_type=LotteryType.BIG_LOTTO,
        official_game_code=BIG_LOTTO_SCHEDULE_GAME_CODE,
        draw_number="115000087",
        exception_kind=ScheduleExceptionKind.CANCELLATION,
        source=TargetSourceProvenance(
            source_id="TAIWAN_LOTTERY_OFFICIAL_EXCEPTION_NOTICE",
            source_version="fixture-v1",
            source_locator="https://www.taiwanlottery.com/announcement/115000087",
            source_sha256="a" * 64,
            observed_at=LATER_OBSERVED_AT,
        ),
    )
    veto_result = repository.apply_canonical_schedule_authority(
        parse_official_biglotto_schedule_authority(
            _body(_row(draw_number="115000087", draw_date="20990102"), marker=2),
            observed_at=LATER_OBSERVED_AT,
            active_vetoes=(veto,),
        )
    )

    assert veto_result.game_results[0].apply_status is ScheduleAuthorityApplyStatus.VETOED
    normal_reobservation = repository.apply_canonical_schedule_authority(
        _fetch(
            _body(_row(draw_number="115000087", draw_date="20990102"), marker=3),
            observed_at=datetime(2099, 1, 1, 3, tzinfo=UTC),
        )
    )

    assert normal_reobservation.game_results[0].apply_status is ScheduleAuthorityApplyStatus.VETOED
    assert SQLiteFutureDrawIdentityReader(paths).get_scheduled_draw(
        LotteryType.BIG_LOTTO,
        "115000087",
    ) is not None
    assert SQLiteFutureDrawIdentityReader(
        paths,
        require_active_authority=True,
    ).get_scheduled_draw(LotteryType.BIG_LOTTO, "115000087") is None
    with open_database(paths, read_only=True) as connection:
        events = connection.execute(
            "SELECT event_kind, disposition FROM draw_schedule_authority_evidence "
            "ORDER BY id"
        ).fetchall()
    assert events == [
        ("OFFICIAL_OBSERVATION", "INSERTED"),
        ("CANCELLATION", "VETOED"),
        ("OFFICIAL_OBSERVATION", "VETOED"),
    ]


def test_runtime_deadline_recheck_rejects_valid_observation_without_fact(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    observed_at = datetime(2099, 1, 2, 12, 29, 59, tzinfo=UTC)
    at_deadline = datetime(2099, 1, 2, 12, 30, tzinfo=UTC)
    result = SQLiteCanonicalScheduleAuthorityRepository(
        paths,
        initialize=False,
        clock=lambda: at_deadline,
    ).apply_canonical_schedule_authority(
        _fetch(
            _body(_row(draw_number="115000087", draw_date="20990102")),
            observed_at=observed_at,
        )
    )

    game = result.game_results[0]
    assert game.authority_status is ScheduleAuthorityStatus.OBSERVATION_DEADLINE_EXPIRED
    assert game.apply_status is ScheduleAuthorityApplyStatus.NO_AUTHORITY
    assert _schedule_rows(paths) == []
    assert _fact_rows(paths) == []
    with open_database(paths, read_only=True) as connection:
        evidence = connection.execute(
            "SELECT event_kind, disposition, detail_code FROM "
            "draw_schedule_authority_evidence"
        ).fetchone()
        item = connection.execute("SELECT disposition FROM ingestion_items").fetchone()
    assert evidence == (
        "OFFICIAL_OBSERVATION",
        "REJECTED_DEADLINE",
        "OBSERVATION_DEADLINE_EXPIRED",
    )
    assert item == ("FAILED",)


def test_canonical_write_rolls_back_audit_evidence_and_fact_on_sql_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)

    def fail(*_args: object, **_kwargs: object) -> int:
        raise sqlite3.IntegrityError("injected fact failure")

    monkeypatch.setattr(repository_module, "_insert_canonical_schedule_fact", fail)

    with pytest.raises(FutureDrawIdentityUnavailableError):
        _repository(paths).apply_canonical_schedule_authority(
            _fetch(_body(_row(draw_number="115000087", draw_date="20990102")))
        )

    with open_database(paths, read_only=True) as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "ingestion_runs",
                "ingestion_run_context",
                "ingestion_items",
                "draw_schedules",
                "draw_schedule_facts",
                "draw_schedule_authority_evidence",
            )
        }
    assert counts == {
        "ingestion_runs": 0,
        "ingestion_run_context": 0,
        "ingestion_items": 0,
        "draw_schedules": 0,
        "draw_schedule_facts": 0,
        "draw_schedule_authority_evidence": 0,
    }


def _v3_paths(tmp_path: Path) -> LocalDataPaths:
    paths = _paths(tmp_path)
    paths.data_directory.mkdir(mode=0o700, parents=True)
    paths.database.touch(mode=0o600)
    with sqlite3.connect(paths.database) as connection:
        for statement in MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations VALUES (1, ?, ?, '2099-01-01T00:00:00Z')",
            (MIGRATION_NAME, MIGRATION_CHECKSUM),
        )
        for statement in CONTEXT_MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations VALUES (2, ?, ?, '2099-01-01T00:00:01Z')",
            (CONTEXT_MIGRATION_NAME, CONTEXT_MIGRATION_CHECKSUM),
        )
        for statement in DRAW_SCHEDULE_MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations VALUES (3, ?, ?, '2099-01-01T00:00:02Z')",
            (DRAW_SCHEDULE_MIGRATION_NAME, DRAW_SCHEDULE_MIGRATION_CHECKSUM),
        )
    return paths


def test_b649_cli_emits_bounded_receipt_and_does_not_accept_backdate_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    body = _body(_row(draw_number="115000087", draw_date="20990102"))
    provider = TaiwanLotteryBigLottoCanonicalScheduleAuthorityProvider(
        https_client=OfficialHttpsClient(
            transport=lambda _request, _context, _timeout, _limit: body
        )
    )
    monkeypatch.setattr(
        cli_module,
        "TaiwanLotteryBigLottoCanonicalScheduleAuthorityProvider",
        lambda: provider,
    )

    result = CliRunner().invoke(
        app,
        ["b649-canonical-schedule-authority-sync"],
        env={DATA_DIRECTORY_ENV: str(paths.data_directory)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["command"] == "b649-canonical-schedule-authority-sync"
    assert payload["disposition"] == "INSERTED"
    assert payload["status"] == "ACCEPTED"
    assert payload["lottery_type"] == "BIG_LOTTO"
    assert payload["official_game_code"] == 5118
    assert payload["target_draw_numbers"] == ["115000087"]
    assert len(payload["immutable_schedule_hashes"]) == 1

    no_backdate = CliRunner().invoke(
        app,
        [
            "b649-canonical-schedule-authority-sync",
            "--observed-at",
            "2099-01-01T00:00:00Z",
        ],
        env={DATA_DIRECTORY_ENV: str(paths.data_directory)},
    )
    assert no_backdate.exit_code != 0


def test_b649_cli_validates_current_schema_read_only_and_does_not_migrate_v3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _v3_paths(tmp_path)
    body = _body(_row(draw_number="115000087", draw_date="20990102"))
    provider = TaiwanLotteryBigLottoCanonicalScheduleAuthorityProvider(
        https_client=OfficialHttpsClient(
            transport=lambda _request, _context, _timeout, _limit: body
        )
    )
    monkeypatch.setattr(
        cli_module,
        "TaiwanLotteryBigLottoCanonicalScheduleAuthorityProvider",
        lambda: provider,
    )
    before = paths.database.read_bytes()

    result = CliRunner().invoke(
        app,
        ["b649-canonical-schedule-authority-sync"],
        env={DATA_DIRECTORY_ENV: str(paths.data_directory)},
    )

    assert result.exit_code == 1
    assert "CANONICAL_DATA_AUTHORITY_UNAVAILABLE" in result.stderr
    assert paths.database.read_bytes() == before
    with sqlite3.connect(paths.database) as connection:
        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone() == (3,)
