"""SQLite integration tests for the exact Historical Prefix source reader.

Every database is pytest-owned under the task's external ``--basetemp``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from tests.fixtures.historical.builder import (
    CUTOFF_DRAW_NUMBER,
    CUTOFF_MAIN_NUMBERS,
    CUTOFF_SPECIAL_NUMBERS,
    REAL_STRATEGY_IDS,
    TARGET_DRAW_NUMBER,
    TARGET_MAIN_NUMBERS,
    build_baseline_envelope,
    build_draw_snapshot,
    build_envelope,
    build_portfolio,
    build_strategy_descriptor,
    build_tickets,
    envelope_bytes,
)

from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessWindowsUnavailableError,
)
from lottolab.domain.historical_results import HistoricalRunImport, HistoricalRunStatus
from lottolab.infrastructure.persistence.historical_prefix_success_window_reader import (
    SQLiteHistoricalPrefixSuccessWindowSourceReader,
)
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultRepository,
)
from lottolab.normalization.historical_import import (
    verify_and_normalize_historical_import,
)


def _success_window_envelope() -> dict[str, Any]:
    baseline = build_baseline_envelope()
    target_special = (49,)
    draws = [
        build_draw_snapshot(
            draw_number=CUTOFF_DRAW_NUMBER,
            draw_date="2026-01-01",
            main_numbers=CUTOFF_MAIN_NUMBERS,
            special_numbers=CUTOFF_SPECIAL_NUMBERS,
        ),
        build_draw_snapshot(
            draw_number=TARGET_DRAW_NUMBER,
            draw_date="2026-01-10",
            main_numbers=TARGET_MAIN_NUMBERS,
            special_numbers=target_special,
        ),
    ]
    portfolios = [
        build_portfolio(
            strategy_id=str(descriptor["strategy_id"]),
            strategy_version=str(descriptor["strategy_version"]),
            replicate=int(descriptor["replicate"]),
            tickets=build_tickets(
                target_main=TARGET_MAIN_NUMBERS,
                target_special=target_special,
            ),
        )
        for descriptor in baseline["strategy_descriptors"]
    ]
    return build_envelope(
        strategy_descriptors=baseline["strategy_descriptors"],
        draw_snapshots=draws,
        portfolios=portfolios,
    )


def _normalized(envelope: dict[str, Any] | None = None) -> HistoricalRunImport:
    result = verify_and_normalize_historical_import(
        envelope_bytes(_success_window_envelope() if envelope is None else envelope)
    )
    assert result.normalized_import is not None
    return result.normalized_import


def _persist(database: Path, run_import: HistoricalRunImport | None = None) -> HistoricalRunImport:
    normalized = _normalized() if run_import is None else run_import
    result = SQLiteHistoricalResultRepository(database).commit_import(normalized)
    assert result.status is HistoricalRunStatus.COMPLETED
    return normalized


def _database_inventory(database: Path) -> tuple[str, tuple[tuple[str, int], ...], bytes]:
    with sqlite3.connect(f"file:{database.as_uri().removeprefix('file:')}?mode=ro", uri=True) as db:
        schema = "\n".join(
            str(row[0])
            for row in db.execute(
                "SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL ORDER BY type, name"
            )
        )
        counts = tuple(
            (table, int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]))
            for table in (
                "historical_result_run",
                "historical_strategy_snapshot",
                "historical_draw_snapshot",
                "historical_portfolio",
                "historical_ticket",
                "historical_count_summary",
            )
        )
    return schema, counts, database.read_bytes()


def test_exact_completed_import_reconstructs_source_order_aliases_replicates_and_tickets(
    tmp_path: Path,
) -> None:
    database = tmp_path / "historical.db"
    run_import = _persist(database)

    source = SQLiteHistoricalPrefixSuccessWindowSourceReader(database).load_source(
        run_import.import_identity_sha256
    )

    assert source is not None
    assert source.metadata.import_identity_sha256 == run_import.import_identity_sha256
    assert source.metadata.source_artifact_sha256 == run_import.source.source_artifact_sha256
    assert source.metadata.dataset_identity == run_import.dataset.dataset_identity
    assert [item.identity.strategy_id for item in source.strategies] == [
        item.strategy_id for item in run_import.strategy_descriptors
    ]
    assert [item.identity.replicate for item in source.strategies[2:4]] == [1, 2]
    alias = source.strategies[-1]
    assert alias.identity.strategy_id == "SYNTHETIC_ALIAS_B"
    assert alias.identity.effective_strategy_id == "SYNTHETIC_ALIAS_B"
    assert alias.identity.alias_of_strategy_id == "SYNTHETIC_BASE_A"
    assert len(alias.observations) == 1
    assert [ticket.portfolio_position for ticket in alias.observations[0].tickets] == list(
        range(1, 21)
    )
    expected = next(
        portfolio
        for portfolio in run_import.portfolios
        if portfolio.strategy_id == alias.identity.strategy_id
    )
    assert [
        (ticket.main_hit_count, ticket.special_hit)
        for ticket in alias.observations[0].tickets
    ] == [(ticket.main_hit_count, ticket.special_hit) for ticket in expected.tickets]


def test_absent_database_and_absent_or_non_completed_exact_run_are_not_found(
    tmp_path: Path,
) -> None:
    absent_database = tmp_path / "absent.db"
    assert (
        SQLiteHistoricalPrefixSuccessWindowSourceReader(absent_database).load_source("a" * 64)
        is None
    )
    assert not absent_database.exists()

    database = tmp_path / "failed.db"
    run_import = _normalized()
    tampered = dataclasses.replace(
        run_import,
        draw_snapshots=(*run_import.draw_snapshots, run_import.draw_snapshots[0]),
    )
    failed = SQLiteHistoricalResultRepository(database).commit_import(tampered)
    assert failed.status is HistoricalRunStatus.FAILED
    assert (
        SQLiteHistoricalPrefixSuccessWindowSourceReader(database).load_source(
            run_import.import_identity_sha256
        )
        is None
    )
    assert (
        SQLiteHistoricalPrefixSuccessWindowSourceReader(database).load_source("f" * 64)
        is None
    )


def test_read_is_byte_schema_row_and_sidecar_invariant(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    run_import = _persist(database)
    before = _database_inventory(database)
    before_digest = hashlib.sha256(before[2]).hexdigest()

    first = SQLiteHistoricalPrefixSuccessWindowSourceReader(database).load_source(
        run_import.import_identity_sha256
    )
    second = SQLiteHistoricalPrefixSuccessWindowSourceReader(database).load_source(
        run_import.import_identity_sha256
    )

    after = _database_inventory(database)
    assert first == second
    assert after[:2] == before[:2]
    assert hashlib.sha256(after[2]).hexdigest() == before_digest
    assert after[2] == before[2]
    assert not list(tmp_path.glob("historical.db-*"))
    assert not list(tmp_path.glob("historical.db-journal"))


def test_unverifiable_manifest_digest_cannot_escape_the_read_boundary(
    tmp_path: Path,
) -> None:
    database = tmp_path / "historical.db"
    run_import = _persist(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE historical_result_run SET manifest_sha256 = ?",
            ("f" * 64,),
        )
        connection.commit()

    source = SQLiteHistoricalPrefixSuccessWindowSourceReader(database).load_source(
        run_import.import_identity_sha256
    )

    assert source is not None
    assert not hasattr(source.metadata, "manifest_sha256")
    assert source.metadata.import_identity_sha256 == run_import.import_identity_sha256
    assert source.metadata.source_artifact_sha256 == run_import.source.source_artifact_sha256


@pytest.mark.parametrize(
    "selector",
    ["A" * 64, f"{'a' * 64} ", f" {'a' * 64}", "abc", "a" * 63],
)
def test_malformed_selector_fails_before_database_open(tmp_path: Path, selector: str) -> None:
    database = tmp_path / "historical.db"
    _persist(database)
    before = database.read_bytes()

    with pytest.raises(HistoricalPrefixSuccessWindowsUnavailableError):
        SQLiteHistoricalPrefixSuccessWindowSourceReader(database).load_source(selector)

    assert database.read_bytes() == before


def test_zero_portfolio_descriptor_remains_visible_in_declaration_order(tmp_path: Path) -> None:
    descriptors = [
        build_strategy_descriptor(strategy_id="SYNTHETIC_ZERO"),
        build_strategy_descriptor(strategy_id=REAL_STRATEGY_IDS[0], identity_kind="REAL"),
    ]
    draws = [
        build_draw_snapshot(
            draw_number=CUTOFF_DRAW_NUMBER,
            draw_date="2026-01-01",
            main_numbers=CUTOFF_MAIN_NUMBERS,
            special_numbers=CUTOFF_SPECIAL_NUMBERS,
        ),
        build_draw_snapshot(
            draw_number=TARGET_DRAW_NUMBER,
            draw_date="2026-01-10",
            main_numbers=TARGET_MAIN_NUMBERS,
            special_numbers=(49,),
        ),
    ]
    envelope = build_envelope(
        strategy_descriptors=descriptors,
        draw_snapshots=draws,
        portfolios=[
            build_portfolio(
                strategy_id=REAL_STRATEGY_IDS[0],
                tickets=build_tickets(
                    target_main=TARGET_MAIN_NUMBERS,
                    target_special=(49,),
                ),
            )
        ],
    )
    database = tmp_path / "historical.db"
    run_import = _persist(database, _normalized(envelope))

    source = SQLiteHistoricalPrefixSuccessWindowSourceReader(database).load_source(
        run_import.import_identity_sha256
    )

    assert source is not None
    assert [item.identity.strategy_id for item in source.strategies] == [
        "SYNTHETIC_ZERO",
        REAL_STRATEGY_IDS[0],
    ]
    assert source.strategies[0].observations == ()


@pytest.mark.parametrize(
    ("sql", "parameters"),
    [
        (
            "UPDATE historical_ticket SET main_hit_count = main_hit_count + 1 WHERE id = 1",
            (),
        ),
        (
            "UPDATE historical_strategy_snapshot SET effective_strategy_id = ? WHERE rowid = 1",
            ("tampered-effective-id",),
        ),
        (
            "UPDATE historical_portfolio SET prefix10_sha256 = ? WHERE rowid = 1",
            ("f" * 64,),
        ),
    ],
)
def test_tampered_persisted_content_fails_closed(
    tmp_path: Path,
    sql: str,
    parameters: tuple[object, ...],
) -> None:
    database = tmp_path / "historical.db"
    run_import = _persist(database)
    with sqlite3.connect(database) as connection:
        connection.execute(sql, parameters)
        connection.commit()

    with pytest.raises(HistoricalPrefixSuccessWindowsUnavailableError):
        SQLiteHistoricalPrefixSuccessWindowSourceReader(database).load_source(
            run_import.import_identity_sha256
        )


def test_corrupt_storage_fails_closed_without_raw_sqlite_exception(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    database.write_bytes(b"not-a-sqlite-database")

    with pytest.raises(
        HistoricalPrefixSuccessWindowsUnavailableError,
        match="historical success-window source is unavailable",
    ):
        SQLiteHistoricalPrefixSuccessWindowSourceReader(database).load_source("a" * 64)
