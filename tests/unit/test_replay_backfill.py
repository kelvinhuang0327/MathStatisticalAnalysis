from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from lottolab.application.use_cases.replay_backfill import (
    BackfillSelection,
    canonical_json,
    identity,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw
from lottolab.infrastructure.persistence.replay_backfill_store import (
    SQLiteBackfillStore,
    identity as persisted_identity,
)


def _summary_for_statuses(
    tmp_path: Path,
    statuses: tuple[str, ...],
    *,
    expected_cells: int | None = None,
) -> dict[str, Any]:
    run_id = "summary-test-run"
    store = SQLiteBackfillStore(tmp_path / "replay-summary.sqlite")
    store.prepare(
        {
            "run_id": run_id,
            "lottery_type": "BIG_LOTTO",
            "dataset_identity": "summary-test-dataset",
            "expected_cells": (
                expected_cells if expected_cells is not None else len(statuses)
            ),
        }
    )
    for index, status in enumerate(statuses):
        result: dict[str, Any] = {
            "cell_identity": f"summary-test-cell-{index}",
            "lottery_type": "BIG_LOTTO",
            "strategy_id": "summary-test-strategy",
            "strategy_version": "v1",
            "execution_version": "unit-test",
            "dataset_identity": "summary-test-dataset",
            "target_draw_id": f"summary-test-draw-{index}",
            "target_draw_date": "2026-01-01",
            "execution_status": status,
            "source_history_provenance_status": "UNKNOWN",
        }
        result["result_identity"] = persisted_identity(result)
        store.save(run_id, result)
    return store.summary(run_id)


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"latest": 0},
        {"latest": True},
        {"latest": 2, "all_draws": True},
        {"all_draws": True, "start_date": date(2020, 1, 1)},
        {"start_date": date(2020, 2, 1), "end_date": date(2020, 1, 1)},
    ],
)
def test_reject_invalid_selection(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        BackfillSelection(**kwargs)


def test_selection_preserves_full_history_and_does_not_pad_missing_draws() -> None:
    draws = tuple(
        ReplayDraw(
            LotteryType.BIG_LOTTO,
            str(n),
            date(2020, 1, 1) + timedelta(days=n),
            (1, 2, 3, 4, 5, 6),
            7,
        )
        for n in range(10)
    )
    assert BackfillSelection(latest=3).select(draws) == draws[-3:]
    assert (
        BackfillSelection(start_date=draws[3].draw_date, end_date=draws[5].draw_date).select(draws)
        == draws[3:6]
    )
    assert BackfillSelection(all_draws=True).select(draws) == draws
    with pytest.raises(ValueError, match="only 10 available"):
        BackfillSelection(latest=1500).select(draws)
    with pytest.raises(ValueError, match="no target"):
        BackfillSelection(start_date=date(2030, 1, 1)).select(draws)


def test_hash_uses_json_roundtrip() -> None:
    assert canonical_json({1: (2, 3)}) == canonical_json({"1": [2, 3]})
    assert identity({1: (2, 3)}) == identity({"1": [2, 3]})


def test_summary_all_complete_cells_is_completed(tmp_path: Path) -> None:
    summary = _summary_for_statuses(tmp_path, ("COMPLETE", "COMPLETE"))

    assert summary["status"] == "COMPLETED"
    assert summary["expected_cells"] == 2
    assert summary["processed_cells"] == 2
    assert summary["pending_cells"] == 0
    assert summary["valid_result_cells"] == 2
    assert summary["failed_cells"] == 0
    assert summary["missing_history_cells"] == 0
    assert summary["status_counts"] == {"COMPLETE": 2}


def test_summary_complete_and_not_eligible_cells_is_finished_with_gaps(
    tmp_path: Path,
) -> None:
    summary = _summary_for_statuses(
        tmp_path, ("COMPLETE", "COMPLETE", "NOT_ELIGIBLE")
    )

    assert summary["status"] == "FINISHED_WITH_GAPS"
    assert summary["expected_cells"] == 3
    assert summary["processed_cells"] == 3
    assert summary["pending_cells"] == 0
    assert summary["valid_result_cells"] == 2
    assert summary["failed_cells"] == 0
    assert summary["missing_history_cells"] == 1
    assert summary["status_counts"] == {"COMPLETE": 2, "NOT_ELIGIBLE": 1}


@pytest.mark.parametrize(
    ("statuses", "expected_cells", "expected_status", "status_counts"),
    [
        (
            ("COMPLETE", "FAILED"),
            2,
            "FINISHED_WITH_GAPS",
            {"COMPLETE": 1, "FAILED": 1},
        ),
        (("COMPLETE",), 2, "IN_PROGRESS", {"COMPLETE": 1}),
    ],
    ids=("failed", "pending"),
)
def test_summary_distinguishes_failed_or_pending_cells_from_valid_gaps(
    tmp_path: Path,
    statuses: tuple[str, ...],
    expected_cells: int,
    expected_status: str,
    status_counts: dict[str, int],
) -> None:
    summary = _summary_for_statuses(tmp_path, statuses, expected_cells=expected_cells)

    assert summary["status"] == expected_status
    assert summary["expected_cells"] == expected_cells
    assert summary["processed_cells"] == len(statuses)
    assert summary["pending_cells"] == expected_cells - len(statuses)
    assert summary["valid_result_cells"] == statuses.count("COMPLETE")
    assert summary["failed_cells"] == statuses.count("FAILED")
    assert summary["missing_history_cells"] == statuses.count("NOT_ELIGIBLE")
    assert summary["status_counts"] == status_counts
    assert not (
        summary["status"] == "FINISHED_WITH_GAPS"
        and summary["processed_cells"] == summary["expected_cells"]
        and summary["failed_cells"] == 0
        and summary["pending_cells"] == 0
        and set(summary["status_counts"]) <= {"COMPLETE", "NOT_ELIGIBLE"}
        and sum(summary["status_counts"].values()) == summary["expected_cells"]
    )
