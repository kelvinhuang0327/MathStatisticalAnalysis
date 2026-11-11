"""Reusable summary-only readback check for continuation-v2 rows.

This is independent of the historical, pinned full readback verifier; callers
must explicitly integrate it into a future readback. It does not open a DB.
"""

import json
from collections.abc import Iterable, Mapping
from typing import Any, cast

AUDIT_SCHEMA = "research-store-v5-continuation-v2-audit"
SUMMARY_FIELDS = (
    "run_id",
    "strategy_snapshot_id",
    "summary_kind",
    "ticket_count_prefix",
    "summary_version",
    "denominator_count",
    "successful_count",
    "closed_count",
    "rank_value",
    "canonical_summary_json",
    "summary_sha256",
)


def is_correction_audit(row: Mapping[str, Any]) -> bool:
    """Apply the historical verifier's correction classification predicate."""
    if row.get("summary_kind") != "AUDIT" or row.get("ticket_count_prefix") is not None:
        return False
    try:
        document = json.loads(row["canonical_summary_json"])
    except (KeyError, TypeError, ValueError):
        return False
    if not isinstance(document, dict):
        return False
    typed_document = cast(dict[str, Any], document)
    return typed_document.get("schema") == AUDIT_SCHEMA


def check_summary_rows(
    expected_rows: Iterable[Mapping[str, Any]], actual_rows: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Compare IDs and verifier fields; report distinct classification denominators."""
    conflicts: list[str] = []
    incomplete: list[str] = []

    def index(rows: Iterable[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            identity = str(row.get("id"))
            if identity in result:
                conflicts.append(f"duplicate {label} summary identity {identity}")
            else:
                result[identity] = row
        return result

    expected = index(expected_rows, "expected")
    actual = index(actual_rows, "actual")
    expected_correction = sum(is_correction_audit(row) for row in expected.values())
    matched_correction = matched_result = 0
    for identity, wanted in expected.items():
        found = actual.get(identity)
        if found is None:
            incomplete.append(f"missing summary {identity}")
            continue
        if any(
            field not in wanted
            or field not in found
            or json.dumps(wanted[field], sort_keys=True) != json.dumps(found[field], sort_keys=True)
            for field in SUMMARY_FIELDS
        ):
            conflicts.append(f"summary content mismatch {identity}")
        elif is_correction_audit(wanted):
            matched_correction += 1
        else:
            matched_result += 1
    for identity in sorted(actual.keys() - expected.keys()):
        conflicts.append(f"unexpected summary identity {identity}")

    return {
        "expected": {
            "correction_audit_rows": expected_correction,
            "other_summary_rows": len(expected) - expected_correction,
        },
        "observed": {
            "correction_audit_rows": sum(is_correction_audit(row) for row in actual.values()),
            "summary_kind_audit_rows": sum(
                row.get("summary_kind") == "AUDIT" for row in actual.values()
            ),
            "summary_rows": len(actual),
        },
        "matched": {
            "correction_audit_rows": matched_correction,
            "other_summary_rows": matched_result,
        },
        "conflicts": conflicts,
        "incomplete_items": incomplete,
    }
