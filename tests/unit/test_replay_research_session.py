"""Pure validation-level unit coverage for ReplayResearchSession.

Real-database parity and cache-reuse behavior live in
tests/integration/test_replay_research_session_sqlite.py. Every case here
raises before any filesystem I/O happens -- SQLiteDrawDataRepository and
SQLiteDrawHistoryReader only ever store the ``paths`` value they are given
(see their constructors); a session built with an explicit, never-opened
``paths`` is enough to exercise pure input validation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lottolab.infrastructure.persistence.draw_schema import DATA_DIRECTORY_ENV, LocalDataPaths
from lottolab.interfaces.research.replay_research_session import (
    MOST_RECENT_TARGET_PAGE_SIZE_LIMIT,
    ReplayResearchSession,
    ResearchReplayError,
)


def test_construction_fails_closed_when_the_local_database_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_DIRECTORY_ENV, str(tmp_path / "no-database-here"))

    with pytest.raises(ResearchReplayError, match="local draw database is unavailable"):
        ReplayResearchSession()


def test_replay_targets_rejects_empty_target_draw_numbers(tmp_path: Path) -> None:
    session = _unopened_session(tmp_path)

    with pytest.raises(ValueError, match="target_draw_numbers must not be empty"):
        session.replay_targets(
            dataset_id="d",
            dataset_version="1",
            target_draw_numbers=(),
            strategy_ids=("some_strategy",),
        )


def test_replay_targets_rejects_empty_strategy_ids(tmp_path: Path) -> None:
    session = _unopened_session(tmp_path)

    with pytest.raises(ValueError, match="strategy_ids must not be empty"):
        session.replay_targets(
            dataset_id="d",
            dataset_version="1",
            target_draw_numbers=("1000000",),
            strategy_ids=(),
        )


def test_replay_portfolio_targets_rejects_empty_target_draw_numbers(tmp_path: Path) -> None:
    session = _unopened_session(tmp_path)

    with pytest.raises(ValueError, match="target_draw_numbers must not be empty"):
        session.replay_portfolio_targets(
            dataset_id="d",
            dataset_version="1",
            target_draw_numbers=(),
            strategy_ids=("some_strategy",),
        )


def test_replay_portfolio_targets_rejects_empty_strategy_ids(tmp_path: Path) -> None:
    session = _unopened_session(tmp_path)

    with pytest.raises(ValueError, match="strategy_ids must not be empty"):
        session.replay_portfolio_targets(
            dataset_id="d",
            dataset_version="1",
            target_draw_numbers=("1000000",),
            strategy_ids=(),
        )


@pytest.mark.parametrize("count", [0, -1, -100])
def test_most_recent_target_draw_numbers_rejects_non_positive_count(
    tmp_path: Path, count: int
) -> None:
    session = _unopened_session(tmp_path)

    with pytest.raises(ValueError, match="count must be a positive integer"):
        session.most_recent_target_draw_numbers(count)


def test_most_recent_target_draw_numbers_rejects_count_above_the_page_limit(
    tmp_path: Path,
) -> None:
    session = _unopened_session(tmp_path)

    with pytest.raises(ValueError, match="must not exceed"):
        session.most_recent_target_draw_numbers(MOST_RECENT_TARGET_PAGE_SIZE_LIMIT + 1)


def _unopened_session(tmp_path: Path) -> ReplayResearchSession:
    """A session over a database path that is never actually opened.

    Construction and every validation error under test here happen before
    any SQLite connection is made, so the path need not exist.
    """

    paths = LocalDataPaths(
        data_directory=tmp_path,
        database=tmp_path / "never-opened.db",
    )
    return ReplayResearchSession(paths=paths)
