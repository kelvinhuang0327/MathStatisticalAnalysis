"""Run the real T539/P638 four-window null benchmark into its task root."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from lottolab.application.multiwindow_success_windows import (
    MultiWindowAnalysis,
    MultiWindowSuccessResultsUnavailableError,
    WindowResult,
    WindowStatus,
    analyze_multiwindow_success_windows,
)
from lottolab.infrastructure.persistence.multiwindow_success_windows_repositories import (
    SQLiteMultiWindowSuccessSourceReader,
)

sys.set_int_max_str_digits(0)

EXPECTED_STRATEGIES = {"DAILY_539": 62, "POWER_LOTTO": 70}
OUTPUT_FILENAME = "multiwindow_summary.json"


def _top_descriptive_lifts(analysis: MultiWindowAnalysis) -> dict[str, list[dict[str, object]]]:
    complete = [
        row
        for row in analysis.rows
        if row.lift_vs_null is not None and row.observed_minus_null_rate is not None
    ]

    def lift_fraction(row: WindowResult):
        assert row.lift_vs_null is not None
        return row.lift_vs_null.as_fraction()

    ordered = sorted(
        complete,
        key=lift_fraction,
    )

    def render(rows: Iterable[WindowResult]) -> list[dict[str, object]]:
        values: list[dict[str, object]] = []
        for row in rows:
            assert row.lift_vs_null is not None
            assert row.observed_minus_null_rate is not None
            values.append(
                {
                    "strategy_id": row.strategy_id,
                    "strategy_version": row.strategy_version,
                    "window_kind": row.window_kind.value,
                    "lift_vs_null": row.lift_vs_null.canonical_dict(),
                    "observed_minus_null_rate": row.observed_minus_null_rate.canonical_dict(),
                }
            )
        return values

    return {"lowest": render(ordered[:5]), "highest": render(reversed(ordered[-5:]))}


def _acceptance_summary(analysis: MultiWindowAnalysis) -> dict[str, object]:
    expected_strategy_count = EXPECTED_STRATEGIES[analysis.lottery_type]
    expected_family_size = expected_strategy_count * 4
    status_counts = Counter(row.status.value for row in analysis.rows)
    if analysis.strategy_count != expected_strategy_count:
        raise RuntimeError(
            f"{analysis.lottery_type} strategy count changed: "
            f"expected {expected_strategy_count}, got {analysis.strategy_count}"
        )
    if analysis.family_size != expected_family_size:
        raise RuntimeError(
            f"{analysis.lottery_type} family size changed: "
            f"expected {expected_family_size}, got {analysis.family_size}"
        )
    if any(row.status is WindowStatus.NO_ELIGIBLE_TARGETS for row in analysis.rows):
        raise RuntimeError(f"{analysis.lottery_type} has a window with no eligible targets")
    return {
        "lottery_type": analysis.lottery_type,
        "run_id": analysis.run_id,
        "strategy_count": analysis.strategy_count,
        "family_size": analysis.family_size,
        "draw_count": analysis.draw_count,
        "row_count": len(analysis.rows),
        "status_counts": dict(sorted(status_counts.items())),
        "complete_row_count": sum(
            1 for row in analysis.rows if row.status is WindowStatus.COMPLETE
        ),
        "null_contract": analysis.null_contract.canonical_dict(),
        "top_descriptive_lifts": _top_descriptive_lifts(analysis),
    }


def _load_analysis(database: Path, lottery_type: str, run_id: str) -> MultiWindowAnalysis:
    source = SQLiteMultiWindowSuccessSourceReader(database, lottery_type).load_source(run_id)
    if source is None:
        raise MultiWindowSuccessResultsUnavailableError(
            f"{lottery_type} run was not found: {run_id}"
        )
    return analyze_multiwindow_success_windows(source)


def build_summary(
    *,
    t539_database: Path,
    t539_run_id: str,
    p638_database: Path,
    p638_run_id: str,
) -> dict[str, object]:
    t539 = _load_analysis(t539_database, "DAILY_539", t539_run_id)
    p638 = _load_analysis(p638_database, "POWER_LOTTO", p638_run_id)
    return {
        "contract": "T539_P638_MULTIWINDOW_NULL_BENCHMARK_BACKEND_R1",
        "event": "OFFICIAL_ANY_PRIZE_TARGET_SUCCESS",
        "evidence_status": "DESCRIPTIVE_ONLY",
        "research_only": True,
        "promotion_allowed": False,
        "sampling_policy": "UNIFORM_IID_LEGAL_TICKETS_WITH_REPLACEMENT",
        "acceptance": {
            "t539": _acceptance_summary(t539),
            "p638": _acceptance_summary(p638),
        },
        "analyses": {
            "t539": t539.canonical_dict(),
            "p638": p638.canonical_dict(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t539-db", type=Path, required=True)
    parser.add_argument("--t539-run-id", required=True)
    parser.add_argument("--p638-db", type=Path, required=True)
    parser.add_argument("--p638-run-id", required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    args = parser.parse_args()
    summary = build_summary(
        t539_database=args.t539_db,
        t539_run_id=args.t539_run_id,
        p638_database=args.p638_db,
        p638_run_id=args.p638_run_id,
    )
    runtime_root = args.runtime_root.resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    output = runtime_root / OUTPUT_FILENAME
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
