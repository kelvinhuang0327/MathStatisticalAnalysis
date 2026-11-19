import pytest
from tools.validate_replay_stage_summary import validate_summary


def summary(gaps: int = 0) -> dict:
    complete = 30_562 - gaps
    return {
        "status": "FINISHED_WITH_GAPS" if gaps else "COMPLETED",
        "expected_cells": 30_562,
        "processed_cells": 30_562,
        "valid_result_cells": complete,
        "missing_history_cells": gaps,
        "failed_cells": 0,
        "failed_count": 0,
        "pending_cells": 0,
        "status_counts": {"COMPLETE": complete, **({"NOT_ELIGIBLE": gaps} if gaps else {})},
        "existing_skipped_count": 0,
        "newly_calculated_count": 30_562,
    }


def test_completed():
    validate_summary(summary(), expected_cells=30_562)


def test_finished_with_declared_gaps():
    validate_summary(summary(12_922), expected_cells=30_562, expected_not_eligible=12_922)


def test_gaps_require_permission():
    with pytest.raises(ValueError, match="status"):
        validate_summary(summary(12_922), expected_cells=30_562)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "UNKNOWN"),
        ("status", "FINISHED_WITH_GAPS"),
        ("expected_cells", 30_561),
        ("processed_cells", 30_561),
        ("newly_calculated_count", 30_561),
        ("valid_result_cells", 30_561),
        ("missing_history_cells", 1),
        ("failed_cells", 1),
        ("failed_count", 1),
        ("pending_cells", 1),
        ("failed_count", False),
        ("pending_cells", None),
    ],
)
def test_inconsistent_summary(field, value):
    with pytest.raises(ValueError, match=field):
        validate_summary({**summary(), field: value}, expected_cells=30_562)


@pytest.mark.parametrize(
    "counts",
    [
        {"COMPLETE": 30_561},
        {"COMPLETE": 30_563},
        {"COMPLETE": 30_562, "FAILED": 1},
        {"COMPLETE": 30_562, "PENDING": 1},
        {"COMPLETE": 30_562, "OTHER": 1},
        {"COMPLETE": 30_562, "NOT_ELIGIBLE": 1},
        {"COMPLETE": "30562"},
    ],
)
def test_invalid_status_counts(counts):
    with pytest.raises(ValueError, match="status_counts"):
        validate_summary({**summary(), "status_counts": counts}, expected_cells=30_562)


def test_wrong_gap_count_with_same_total():
    with pytest.raises(ValueError, match="status_counts"):
        validate_summary(summary(12_921), expected_cells=30_562, expected_not_eligible=12_922)
