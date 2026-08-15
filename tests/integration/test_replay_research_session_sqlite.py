"""Real-SQLite parity coverage for ReplayResearchSession.

Mirrors tests/integration/test_replay_historical_predictions_sqlite.py's own
fixture-seeding pattern (same committed synthetic fixture, same task-owned
temp database), but exercises the new research composition root instead of
hand-wiring BuildCausalHistory/GenerateOneBet/StrategyCatalog directly. The
load-bearing claim under test: ReplayResearchSession.replay_targets() must
return exactly what the pre-existing, directly-composed
ReplayHistoricalPredictions returns for the same request -- with or without
a warm cache -- since PR #127's cache contract is "identical results, fewer
recomputations," never "different results."
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.application.use_cases.build_causal_history import BuildCausalHistory
from lottolab.application.use_cases.generate_bet import build_production_generate_one_bet
from lottolab.application.use_cases.replay_historical_predictions import (
    ReplayHistoricalPredictions,
    ReplayHistoricalPredictionsInput,
    ReplayResearchCache,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.evidence.replay_artifact import causal_history_sha256
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.replay_history_reader import SQLiteDrawHistoryReader
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.interfaces.research.replay_research_session import (
    ReplayResearchSession,
    ResearchReplayError,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "replay" / "synthetic_biglotto_causal_history.json"
)

_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"
_DATASET_ID = "SYNTHETIC_BIG_LOTTO_RESEARCH_SESSION_R1"
_DATASET_VERSION = "1"
_TARGET_DRAW_NUMBERS = ("1000104", "1000105", "1000106")
_STRATEGY_IDS = (
    "biglotto_social_wisdom_anti_popularity",
    "biglotto_zone_split_3bet_bet1",
    "biglotto_deviation_2bet",
)
_TABLES = ("draws", "schema_migrations", "ingestion_runs", "ingestion_items")


def _task_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "research-session-sqlite")}
    )


def _fixture_rows() -> list[dict[str, Any]]:
    fixture: dict[str, Any] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return cast("list[dict[str, Any]]", fixture["history_rows"])


def _seed_canonical_draws(paths: LocalDataPaths) -> None:
    rows = [
        ",".join(
            (
                LotteryType.BIG_LOTTO.value,
                row["draw_number"],
                row["draw_date"],
                "|".join(str(number) for number in row["main_numbers"]),
                str(row["special_number"]),
                "synthetic-research-session-sqlite",
            )
        )
        for row in _fixture_rows()
    ]
    document = parse_draw_csv(
        "\n".join((_HEADER, *rows, "")),
        filename="synthetic-research-session-sqlite.csv",
    )
    assert document.is_valid, document.errors

    result = SQLiteDrawDataRepository(paths).apply_valid_import(document)

    assert result.inserted_count == len(rows) == 110
    assert result.skipped_count == result.conflict_count == result.failed_count == 0


def _table_snapshot(paths: LocalDataPaths) -> dict[str, tuple[tuple[object, ...], ...]]:
    with open_database(paths, read_only=True) as connection:
        return {
            table: tuple(
                tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
            )
            for table in _TABLES
        }


def _draw_date_for(draw_number: str) -> date:
    for row in _fixture_rows():
        if row["draw_number"] == draw_number:
            return date.fromisoformat(row["draw_date"])
    raise AssertionError(f"fixture has no row for {draw_number}")


def _directly_composed_snapshots(
    paths: LocalDataPaths,
    *,
    target_draw_numbers: tuple[str, ...] = _TARGET_DRAW_NUMBERS,
    strategy_ids: tuple[str, ...] = _STRATEGY_IDS,
    maximum_history_draws: int | None = None,
    minimum_history_draws: int | None = None,
) -> tuple[Any, ...]:
    """The pre-existing composition path, wired with no cache -- the parity baseline."""

    replay = ReplayHistoricalPredictions(
        BuildCausalHistory(lambda: SQLiteDrawHistoryReader(paths)),
        build_production_generate_one_bet(),
        production_catalog(),
    )
    targets = tuple(
        ReplayTarget(draw_number=number, draw_date=_draw_date_for(number))
        for number in target_draw_numbers
    )
    result = replay.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id=_DATASET_ID,
            dataset_version=_DATASET_VERSION,
            targets=targets,
            strategy_ids=strategy_ids,
            maximum_history_draws=maximum_history_draws,
            minimum_history_draws=minimum_history_draws,
        )
    )
    return result.snapshots


def test_replay_targets_matches_the_directly_composed_replay_use_case(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    expected = _directly_composed_snapshots(paths)

    before = _table_snapshot(paths)
    session = ReplayResearchSession(paths=paths)
    result = session.replay_targets(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        target_draw_numbers=_TARGET_DRAW_NUMBERS,
        strategy_ids=_STRATEGY_IDS,
    )
    after = _table_snapshot(paths)

    assert after == before, "replay_targets must never write to the draw database"
    assert result.snapshots == expected
    assert len(result.snapshots) == len(_TARGET_DRAW_NUMBERS) * len(_STRATEGY_IDS)
    for snapshot in result.snapshots:
        assert snapshot.predicted_main_numbers is not None
        assert len(snapshot.predicted_main_numbers) == 6


def test_replay_targets_reuses_cache_across_repeated_calls_and_stays_deterministic(
    tmp_path: Path,
) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    session = ReplayResearchSession(paths=paths)

    first = session.replay_targets(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        target_draw_numbers=_TARGET_DRAW_NUMBERS,
        strategy_ids=_STRATEGY_IDS,
    )
    pair_count = len(_TARGET_DRAW_NUMBERS) * len(_STRATEGY_IDS)
    assert session.cache_stats.misses == pair_count
    assert session.cache_stats.hits == 0

    second = session.replay_targets(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        target_draw_numbers=_TARGET_DRAW_NUMBERS,
        strategy_ids=_STRATEGY_IDS,
    )
    assert session.cache_stats.misses == pair_count
    assert session.cache_stats.hits == pair_count
    assert second.snapshots == first.snapshots


def test_replay_targets_applies_history_cutoff_bounds_identically_to_direct_composition(
    tmp_path: Path,
) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    expected = _directly_composed_snapshots(
        paths, maximum_history_draws=20, minimum_history_draws=5
    )

    session = ReplayResearchSession(paths=paths)
    result = session.replay_targets(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        target_draw_numbers=_TARGET_DRAW_NUMBERS,
        strategy_ids=_STRATEGY_IDS,
        maximum_history_draws=20,
        minimum_history_draws=5,
    )

    assert result.snapshots == expected
    for snapshot in result.snapshots:
        assert snapshot.causal_history_count == 20


def test_replay_targets_unknown_strategy_id_is_a_closed_result_not_an_exception(
    tmp_path: Path,
) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    session = ReplayResearchSession(paths=paths)

    result = session.replay_targets(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        target_draw_numbers=_TARGET_DRAW_NUMBERS[:1],
        strategy_ids=("totally_unknown_strategy_id",),
    )

    assert len(result.snapshots) == 1
    snapshot = result.snapshots[0]
    assert snapshot.history_status == "OK"
    assert snapshot.prediction_status == "STRATEGY_UNAVAILABLE"
    assert snapshot.predicted_main_numbers is None


def test_replay_targets_missing_target_draw_raises_research_replay_error(
    tmp_path: Path,
) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    session = ReplayResearchSession(paths=paths)

    with pytest.raises(ResearchReplayError, match="absent-draw"):
        session.replay_targets(
            dataset_id=_DATASET_ID,
            dataset_version=_DATASET_VERSION,
            target_draw_numbers=("absent-draw",),
            strategy_ids=_STRATEGY_IDS[:1],
        )


def test_most_recent_target_draw_numbers_returns_oldest_first(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    session = ReplayResearchSession(paths=paths)

    assert session.most_recent_target_draw_numbers(3) == ("1000107", "1000108", "1000109")


def test_sessions_do_not_share_a_cache_unless_one_is_explicitly_passed(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    pair_count = len(_TARGET_DRAW_NUMBERS) * len(_STRATEGY_IDS)

    independent_a = ReplayResearchSession(paths=paths)
    independent_a.replay_targets(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        target_draw_numbers=_TARGET_DRAW_NUMBERS,
        strategy_ids=_STRATEGY_IDS,
    )
    independent_b = ReplayResearchSession(paths=paths)
    independent_b.replay_targets(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        target_draw_numbers=_TARGET_DRAW_NUMBERS,
        strategy_ids=_STRATEGY_IDS,
    )
    assert independent_b.cache_stats.hits == 0  # no shared cache -> both sessions start cold

    shared_cache = ReplayResearchCache()
    shared_first = ReplayResearchSession(paths=paths, cache=shared_cache)
    shared_first.replay_targets(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        target_draw_numbers=_TARGET_DRAW_NUMBERS,
        strategy_ids=_STRATEGY_IDS,
    )
    shared_second = ReplayResearchSession(paths=paths, cache=shared_cache)
    shared_second.replay_targets(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        target_draw_numbers=_TARGET_DRAW_NUMBERS,
        strategy_ids=_STRATEGY_IDS,
    )
    assert shared_second.cache_stats.hits == pair_count  # explicit shared cache -> second is warm


def _seed_native_draws(
    paths: LocalDataPaths,
    *,
    lottery_type: LotteryType,
    rows: list[tuple[str, str, tuple[int, ...], int | None]],
) -> None:
    csv_rows = [
        ",".join(
            (
                lottery_type.value,
                draw_number,
                draw_date,
                "|".join(str(number) for number in main_numbers),
                "" if special_number is None else str(special_number),
                f"synthetic-{lottery_type.value.lower()}-research-session",
            )
        )
        for draw_number, draw_date, main_numbers, special_number in rows
    ]
    document = parse_draw_csv(
        "\n".join((_HEADER, *csv_rows, "")),
        filename=f"synthetic-{lottery_type.value.lower()}.csv",
    )
    assert document.is_valid, document.errors
    result = SQLiteDrawDataRepository(paths).apply_valid_import(document)
    assert result.inserted_count == len(rows)
    assert result.skipped_count == result.conflict_count == result.failed_count == 0


def test_replay_targets_supports_daily_539_native_five_number_causal_history(
    tmp_path: Path,
) -> None:
    """DAILY_539 (5/39, no special number) must resolve end to end through the session."""

    paths = _task_paths(tmp_path)
    _seed_native_draws(
        paths,
        lottery_type=LotteryType.DAILY_539,
        rows=[
            ("1", "2026-02-01", (1, 2, 3, 4, 5), None),
            ("2", "2026-02-02", (6, 7, 8, 9, 10), None),
            ("3", "2026-02-03", (11, 12, 13, 14, 15), None),
        ],
    )
    session = ReplayResearchSession(lottery_type=LotteryType.DAILY_539, paths=paths)

    result = session.replay_targets(
        dataset_id="SYNTHETIC_DAILY_539_RESEARCH_SESSION_R1",
        dataset_version="1",
        target_draw_numbers=("3",),
        strategy_ids=_STRATEGY_IDS[:1],
    )

    assert len(result.snapshots) == 1
    snapshot = result.snapshots[0]
    # Target/history lottery identity is preserved end to end.
    assert snapshot.lottery_type is LotteryType.DAILY_539
    assert snapshot.target_draw_number == "3"
    assert snapshot.target_draw_date == date(2026, 2, 3)
    # Five-number DAILY_539 rows are accepted -- the six-number BIG_LOTTO
    # contract is not silently applied -- and the causal cutoff stops
    # strictly before the target (draws "1" and "2" only, never "3").
    assert snapshot.history_status == "OK"
    assert snapshot.causal_history_count == 2
    assert snapshot.cutoff_draw_number == "2"
    assert snapshot.cutoff_draw_date == date(2026, 2, 2)
    reader = SQLiteDrawHistoryReader(paths)
    expected_history = reader.read_causal_history(LotteryType.DAILY_539, "3")
    assert len(expected_history) == 2
    assert all(row.lottery_type is LotteryType.DAILY_539 for row in expected_history)
    assert all(len(row.main_numbers) == 5 for row in expected_history)
    assert all(row.special_number is None for row in expected_history)
    assert snapshot.causal_history_sha256 == causal_history_sha256(expected_history)
    # No strategy in the production catalog currently supports DAILY_539; the
    # causal-history read still succeeds and resolves as a closed result.
    assert snapshot.prediction_status == "STRATEGY_UNAVAILABLE"


def test_replay_targets_supports_power_lotto_native_zone_split_causal_history(
    tmp_path: Path,
) -> None:
    """POWER_LOTTO (6/38 main zone + 1/8 special zone) must resolve end to end."""

    paths = _task_paths(tmp_path)
    _seed_native_draws(
        paths,
        lottery_type=LotteryType.POWER_LOTTO,
        rows=[
            ("1", "2026-02-01", (1, 2, 3, 4, 5, 6), 8),
            ("2", "2026-02-02", (7, 8, 9, 10, 11, 12), 3),
            ("3", "2026-02-03", (13, 14, 15, 16, 17, 18), 1),
        ],
    )
    session = ReplayResearchSession(lottery_type=LotteryType.POWER_LOTTO, paths=paths)

    result = session.replay_targets(
        dataset_id="SYNTHETIC_POWER_LOTTO_RESEARCH_SESSION_R1",
        dataset_version="1",
        target_draw_numbers=("3",),
        strategy_ids=_STRATEGY_IDS[:1],
    )

    assert len(result.snapshots) == 1
    snapshot = result.snapshots[0]
    # Target/history lottery identity is preserved end to end.
    assert snapshot.lottery_type is LotteryType.POWER_LOTTO
    assert snapshot.target_draw_number == "3"
    assert snapshot.target_draw_date == date(2026, 2, 3)
    # The causal cutoff stops strictly before the target (draws "1" and "2"
    # only, never "3").
    assert snapshot.history_status == "OK"
    assert snapshot.causal_history_count == 2
    assert snapshot.cutoff_draw_number == "2"
    assert snapshot.cutoff_draw_date == date(2026, 2, 2)
    reader = SQLiteDrawHistoryReader(paths)
    expected_history = reader.read_causal_history(LotteryType.POWER_LOTTO, "3")
    assert len(expected_history) == 2
    # Native zone semantics are preserved, not flattened into a fake
    # single-zone BIG_LOTTO row: zone1 (6 main numbers, 1..38) stays distinct
    # from zone2 (the 1..8 special number) on every causal history row.
    assert all(row.lottery_type is LotteryType.POWER_LOTTO for row in expected_history)
    assert all(len(row.main_numbers) == 6 for row in expected_history)
    assert all(max(row.main_numbers) <= 38 for row in expected_history)
    assert all(
        row.special_number is not None and 1 <= row.special_number <= 8 for row in expected_history
    )
    assert [row.special_number for row in expected_history] == [8, 3]
    assert snapshot.causal_history_sha256 == causal_history_sha256(expected_history)
    # No strategy in the production catalog currently supports POWER_LOTTO; the
    # causal-history read (main zone + special zone both preserved) still
    # succeeds and resolves as a closed result.
    assert snapshot.prediction_status == "STRATEGY_UNAVAILABLE"
