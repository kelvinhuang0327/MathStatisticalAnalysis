"""Validate a saved ReplayBackfill.execute summary against an isolated stage's plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _count(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def validate_summary(
    summary: object, *, expected_cells: int, expected_not_eligible: int = 0
) -> None:
    """Raise ValueError unless the saved counts match the declared terminal outcome."""
    total = _count("expected_cells argument", expected_cells)
    gaps = _count("expected_not_eligible argument", expected_not_eligible)
    if gaps > total:
        raise ValueError("expected_not_eligible exceeds expected_cells")
    if not isinstance(summary, dict):
        raise ValueError("summary must be a JSON object")

    status = "FINISHED_WITH_GAPS" if gaps else "COMPLETED"
    if summary.get("status") != status:
        raise ValueError(f"status must be {status} for the declared counts")

    counts = summary.get("status_counts")
    if not isinstance(counts, dict):
        raise ValueError("status_counts must be a JSON object")
    expected_counts = {"COMPLETE": total - gaps, "NOT_ELIGIBLE": gaps, "FAILED": 0, "PENDING": 0}
    if counts.keys() - expected_counts.keys():
        raise ValueError("status_counts contains an unknown cell status")
    for key, expected in expected_counts.items():
        if _count(f"status_counts.{key}", counts.get(key, 0)) != expected:
            raise ValueError(f"status_counts.{key} must equal {expected}")

    for key, expected in {
        "expected_cells": total,
        "processed_cells": total,
        "valid_result_cells": total - gaps,
        "missing_history_cells": gaps,
        "failed_cells": 0,
        "failed_count": 0,
        "pending_cells": 0,
    }.items():
        if _count(key, summary.get(key)) != expected:
            raise ValueError(f"{key} must equal {expected}")

    new = _count("newly_calculated_count", summary.get("newly_calculated_count"))
    skipped = _count("existing_skipped_count", summary.get("existing_skipped_count"))
    if new + skipped != total:
        raise ValueError(f"newly_calculated_count + existing_skipped_count must equal {total}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path, help="Path to the saved run summary JSON")
    parser.add_argument("--expected-cells", type=int, required=True, help="Planned total cells")
    parser.add_argument(
        "--expected-not-eligible",
        type=int,
        default=0,
        help="Exact number of NOT_ELIGIBLE cells permitted by the plan (default: 0)",
    )
    args = parser.parse_args()
    try:
        summary = json.loads(args.summary.read_text(encoding="utf-8"))
        validate_summary(
            summary,
            expected_cells=args.expected_cells,
            expected_not_eligible=args.expected_not_eligible,
        )
    except (OSError, ValueError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"VALID {summary['status']}: {args.expected_cells} cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
