"""Real-SQLite coverage for the Replay -> base-method-evaluation chain.

Seeds the same committed synthetic BIG_LOTTO fixture and task-owned temporary
database that tests/integration/test_replay_research_session_sqlite.py uses,
then drives the whole vertical end to end: ReplayResearchSession produces real
snapshots from a real strategy adapter over a real causal history, those
snapshots plus the fixture's own realized outcomes go through the composition
seam, and the existing evaluator returns the record.

Every outcome here comes from the committed synthetic fixture, never from a
production draw database, so the chain is exercised with no empirical access
of any kind. The database is also snapshotted before and after to prove the
evaluation path stays strictly read-only.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import ReplayPredictionSnapshot
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.interfaces.research.replay_research_session import ReplayResearchSession
from lottolab.research.base_method_evaluation import (
    AVG_MATCH_ID,
    BIG_LOTTO_MATCH_CONTRACT,
    OutputShape,
    ReplayStatus,
    WindowKind,
    evaluate_method,
)
from lottolab.research.replay_method_evaluation import (
    ReplayMethodEvaluationError,
    ReplayTargetOutcome,
    build_method_draw_observations,
    build_single_ticket_identity,
    evaluate_replayed_single_ticket_method,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "replay" / "synthetic_biglotto_causal_history.json"
)

_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"
_DATASET_ID = "SYNTHETIC_BIG_LOTTO_METHOD_EVALUATION_V1A"
_DATASET_VERSION = "1"
_STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"
_METHOD_FAMILY = "SYNTHETIC_REPLAY_EVALUATION_V1A"
_TARGET_DRAW_NUMBERS = tuple(str(1000100 + offset) for offset in range(10))
_TABLES = ("draws", "schema_migrations", "ingestion_runs", "ingestion_items")


def _task_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "method-evaluation-sqlite")}
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
                "synthetic-method-evaluation-sqlite",
            )
        )
        for row in _fixture_rows()
    ]
    document = parse_draw_csv(
        "\n".join((_HEADER, *rows, "")),
        filename="synthetic-method-evaluation-sqlite.csv",
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


def _fixture_row(draw_number: str) -> dict[str, Any]:
    for row in _fixture_rows():
        if row["draw_number"] == draw_number:
            return row
    raise AssertionError(f"fixture has no row for {draw_number}")


def _outcomes_from_fixture() -> tuple[ReplayTargetOutcome, ...]:
    """Realized outcomes taken from the committed synthetic fixture only."""

    return tuple(
        ReplayTargetOutcome(
            draw_number=draw_number,
            draw_date=date.fromisoformat(_fixture_row(draw_number)["draw_date"]),
            main_numbers=tuple(_fixture_row(draw_number)["main_numbers"]),
        )
        for draw_number in _TARGET_DRAW_NUMBERS
    )


def _replayed_snapshots(paths: LocalDataPaths) -> tuple[ReplayPredictionSnapshot, ...]:
    session = ReplayResearchSession(paths=paths)
    result = session.replay_targets(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        target_draw_numbers=_TARGET_DRAW_NUMBERS,
        strategy_ids=(_STRATEGY_ID,),
    )
    return result.snapshots


def test_replay_to_evaluation_chain_produces_a_full_record(tmp_path: Path) -> None:
    """The whole V1A vertical: causal replay -> observation -> evaluation record."""

    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)

    before = _table_snapshot(paths)
    snapshots = _replayed_snapshots(paths)
    record = evaluate_replayed_single_ticket_method(
        snapshots,
        _outcomes_from_fixture(),
        method_family=_METHOD_FAMILY,
        replay_status=ReplayStatus.BASELINE_RECORDED,
    )
    after = _table_snapshot(paths)

    assert after == before, "the evaluation chain must never write to the draw database"
    assert len(snapshots) == len(_TARGET_DRAW_NUMBERS)
    assert all(snapshot.history_status == "OK" for snapshot in snapshots)
    assert all(snapshot.prediction_status == "OK" for snapshot in snapshots)

    assert record.identity.method_id == _STRATEGY_ID
    assert record.identity.method_family == _METHOD_FAMILY
    assert record.identity.output_shape is OutputShape.SINGLE_OUTPUT
    assert record.identity.target_coverage.eligible_draw_count == len(_TARGET_DRAW_NUMBERS)
    assert record.identity.target_coverage.first_draw_id == _TARGET_DRAW_NUMBERS[0]
    assert record.identity.target_coverage.last_draw_id == _TARGET_DRAW_NUMBERS[-1]
    assert set(record.windows) == {
        WindowKind.WINDOW_50,
        WindowKind.WINDOW_300,
        WindowKind.WINDOW_750,
        WindowKind.FULL_HISTORY,
    }


def test_hit_counts_match_an_independent_recomputation(tmp_path: Path) -> None:
    """Recompute every hit count straight from the snapshot and the fixture row."""

    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    snapshots = _replayed_snapshots(paths)

    observations = build_method_draw_observations(snapshots, _outcomes_from_fixture())

    assert len(observations) == len(snapshots)
    for snapshot, observation in zip(snapshots, observations, strict=True):
        assert snapshot.predicted_main_numbers is not None
        drawn = set(_fixture_row(snapshot.target_draw_number)["main_numbers"])
        expected_hits = len(set(snapshot.predicted_main_numbers) & drawn)
        assert observation.draw_id == snapshot.target_draw_number
        assert observation.main_hit_counts == (expected_hits,)
        assert observation.native_ticket_count == observation.distinct_ticket_count == 1


def test_chain_matches_direct_evaluator_invocation(tmp_path: Path) -> None:
    """Composing through the seam equals calling the existing evaluator itself."""

    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    snapshots = _replayed_snapshots(paths)
    outcomes = _outcomes_from_fixture()

    observations = build_method_draw_observations(snapshots, outcomes)
    identity = build_single_ticket_identity(
        snapshots,
        observations,
        method_family=_METHOD_FAMILY,
        replay_status=ReplayStatus.BASELINE_RECORDED,
    )
    expected = evaluate_method(BIG_LOTTO_MATCH_CONTRACT, identity, observations)

    assert (
        evaluate_replayed_single_ticket_method(
            snapshots,
            outcomes,
            method_family=_METHOD_FAMILY,
            replay_status=ReplayStatus.BASELINE_RECORDED,
        )
        == expected
    )


def test_evaluation_is_deterministic_for_identical_snapshots(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    snapshots = _replayed_snapshots(paths)
    outcomes = _outcomes_from_fixture()

    first = evaluate_replayed_single_ticket_method(
        snapshots,
        outcomes,
        method_family=_METHOD_FAMILY,
        replay_status=ReplayStatus.BASELINE_RECORDED,
    )
    second = evaluate_replayed_single_ticket_method(
        snapshots,
        outcomes,
        method_family=_METHOD_FAMILY,
        replay_status=ReplayStatus.BASELINE_RECORDED,
    )

    assert first == second
    assert (
        first.windows[WindowKind.FULL_HISTORY].metrics[AVG_MATCH_ID].random_reference
        == second.windows[WindowKind.FULL_HISTORY].metrics[AVG_MATCH_ID].random_reference
    )


def test_a_missing_outcome_fails_closed_against_real_snapshots(tmp_path: Path) -> None:
    """A dropped outcome must raise, never quietly shrink the evaluated history."""

    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    snapshots = _replayed_snapshots(paths)

    with pytest.raises(ReplayMethodEvaluationError, match="no target outcome was supplied"):
        evaluate_replayed_single_ticket_method(
            snapshots,
            _outcomes_from_fixture()[:-1],
            method_family=_METHOD_FAMILY,
            replay_status=ReplayStatus.BASELINE_RECORDED,
        )
