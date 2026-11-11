import json
from typing import Any

from tools.readback_summary_metrics import AUDIT_SCHEMA, check_summary_rows


def row(run: int, suffix: str, prefix: int | None, schema: str) -> dict[str, Any]:
    return {
        "id": f"{run}-{suffix}",
        "run_id": str(run),
        "strategy_snapshot_id": str(run),
        "summary_kind": "AUDIT",
        "ticket_count_prefix": prefix,
        "summary_version": 2,
        "denominator_count": 0,
        "successful_count": 0,
        "closed_count": 0,
        "rank_value": None,
        "canonical_summary_json": json.dumps({"schema": schema}),
        "summary_sha256": suffix,
    }


def test_two_audit_kind_rows_per_run_have_distinct_counts():
    rows = [
        item
        for run in range(153)
        for item in (
            row(run, "correction", None, AUDIT_SCHEMA),
            row(run, "result", (2, 3, 5)[run % 3], "result"),
        )
    ]
    report = check_summary_rows(rows, rows)
    assert report["expected"] == {"correction_audit_rows": 153, "other_summary_rows": 153}
    assert report["observed"] == {
        "correction_audit_rows": 153,
        "summary_kind_audit_rows": 306,
        "summary_rows": 306,
    }
    assert report["matched"] == {"correction_audit_rows": 153, "other_summary_rows": 153}
    assert report["conflicts"] == report["incomplete_items"] == []


def test_missing_duplicate_and_wrong_classification_are_reported():
    correction = row(0, "correction", None, AUDIT_SCHEMA)
    result = row(0, "result", 2, "result")
    changed = dict(correction, ticket_count_prefix=2)
    report = check_summary_rows([correction, result], [changed, changed])
    assert report["observed"]["correction_audit_rows"] == 0
    assert report["matched"]["correction_audit_rows"] == 0
    assert len(report["conflicts"]) == 2
    assert report["incomplete_items"] == ["missing summary 0-result"]
