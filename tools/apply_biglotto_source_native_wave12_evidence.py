#!/usr/bin/env python3
"""Apply the twelfth source-native evidence wave to a validated catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave12 import (
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE12_METHOD,
    MODERATE_SELECTION_METHOD_ID,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE12_METHOD,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE12_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE12_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE12_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE12_METHOD,
    SOURCE_NATIVE_WAVE12_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "73484188012e8ee558ac1e60dba0445bc922102b5187f04fc0d3e561926d0f0e"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE12_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 36,
    "CLOSED_UNEXECUTABLE": 25,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 156,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 37,
    "CLOSED_UNEXECUTABLE": 25,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 155,
}
EXPECTED_NATIVE_DUPLICATE_COUNTS = [
    331,
    333,
    335,
    336,
    337,
    338,
    339,
    340,
    341,
    342,
    343,
    344,
    345,
    346,
    347,
    348,
    349,
    350,
    351,
    352,
    353,
    354,
    355,
    356,
    357,
    358,
]
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class CatalogOverlayError(ValueError):
    """The base catalog or wave-12 evidence violates the overlay contract."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CatalogOverlayError(f"{path}: invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise CatalogOverlayError(f"{path}: top level must be an object")
    return (
        cast(dict[str, Any], parsed),
        hashlib.sha256(raw).hexdigest(),
    )


def _catalog_hash(document: dict[str, Any]) -> str:
    reduced = {
        key: value
        for key, value in document.items()
        if key != "catalog_sha256"
    }
    return hashlib.sha256(_canonical_bytes(reduced)).hexdigest()


def _validate_digest(value: object, context: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CatalogOverlayError(
            f"{context} must be a lowercase SHA-256"
        )


def _validate_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("source_native_protocol")
        != SOURCE_NATIVE_WAVE12_PROTOCOL
        or evidence.get("constructor")
        != "strategy_preserving_20_ticket/v1"
        or evidence.get("backtest_policy_version")
        != "BIG_LOTTO_CAUSAL_ORDERED_20_PREFIX_5_10_15_20_V1"
        or evidence.get("target_draw_count") != 2149
        or evidence.get("catalog_sha256_before_status_overlay")
        != BASE_CATALOG_SHA256
        or evidence.get("source_database_sha256_before")
        != evidence.get("source_database_sha256_after")
        or evidence.get("candidate_k_semantics")
        != "NOT_APPLICABLE_GRID_PARAMETERS_ARE_CONFIGURATIONS"
        or evidence.get("combination_count_semantics")
        != "FROZEN_PARAMETER_GRID_CONFIGURATION_COUNT"
    ):
        raise CatalogOverlayError("wave-12 evidence identity changed")
    for key in (
        "input_raw_sha256",
        "input_canonical_sha256",
        "report_file_sha256",
        "report_sha256",
        "source_database_sha256_before",
    ):
        _validate_digest(evidence.get(key), f"evidence {key}")
    reproducibility_raw = evidence.get("reproducibility")
    parity_raw = evidence.get("frozen_source_parity")
    if (
        not isinstance(reproducibility_raw, dict)
        or not isinstance(parity_raw, dict)
    ):
        raise CatalogOverlayError(
            "wave-12 reproducibility/parity evidence changed"
        )
    reproducibility = cast(dict[str, Any], reproducibility_raw)
    parity = cast(dict[str, Any], parity_raw)
    if (
        reproducibility.get("input_byte_identical") is not True
        or reproducibility.get("report_directory_byte_identical")
        is not True
        or reproducibility.get("repeat_input_raw_sha256")
        != evidence.get("input_raw_sha256")
        or reproducibility.get("repeat_report_file_sha256")
        != evidence.get("report_file_sha256")
        or parity.get("status") != "PASS"
        or parity.get("case_count") != 3
        or parity.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
    ):
        raise CatalogOverlayError(
            "wave-12 reproducibility/parity evidence changed"
        )
    _validate_digest(
        parity.get("artifact_sha256"),
        "frozen-source parity artifact",
    )
    rows_raw = evidence.get("strategies")
    if not isinstance(rows_raw, list):
        raise CatalogOverlayError(
            "wave-12 evidence must contain one strategy"
        )
    rows = cast(list[object], rows_raw)
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise CatalogOverlayError(
            "wave-12 evidence must contain one strategy"
        )
    row = cast(dict[str, Any], rows[0])
    if (
        row.get("legacy_method_id") != MODERATE_SELECTION_METHOD_ID
        or row.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD[
            MODERATE_SELECTION_METHOD_ID
        ]
        or row.get("successful_execution_count") != 2099
        or row.get("closed_status_counts")
        != {"CLOSED_INSUFFICIENT_HISTORY": 50}
        or row.get("minimum_history_draws")
        != MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE12_METHOD[
            MODERATE_SELECTION_METHOD_ID
        ]
        or row.get("native_ticket_count_values") != [360]
        or row.get("native_duplicate_ticket_count_values")
        != EXPECTED_NATIVE_DUPLICATE_COUNTS
        or row.get("native_ticket_semantics")
        != NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE12_METHOD[
            MODERATE_SELECTION_METHOD_ID
        ]
        or row.get("random_protocol")
        != RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE12_METHOD[
            MODERATE_SELECTION_METHOD_ID
        ]
        or row.get("source_history_order")
        != SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE12_METHOD[
            MODERATE_SELECTION_METHOD_ID
        ]
        or row.get("combination_count")
        != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE12_METHOD[
            MODERATE_SELECTION_METHOD_ID
        ]
        or row.get("combination_members")
        != list(
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE12_METHOD[
                MODERATE_SELECTION_METHOD_ID
            ]
        )
        or row.get("candidate_k") is not None
        or row.get("source_result_selection")
        != (
            "ALL_180_FIXED_CONFIGURATIONS_RETAINED_NO_TARGET_"
            "OUTCOME_GRID_WINNER_SELECTION"
        )
    ):
        raise CatalogOverlayError("wave-12 strategy evidence changed")
    return row


def apply_wave12_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    catalog, _raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        catalog.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION
        or catalog.get("catalog_policy_version")
        != CATALOG_POLICY_VERSION
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or _catalog_hash(catalog) != BASE_CATALOG_SHA256
        or catalog.get("status_counts")
        != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
    ):
        raise CatalogOverlayError("base catalog identity changed")
    _validate_digest(evidence_sha256, "evidence file digest")
    evidence_row = _validate_evidence(evidence)

    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise CatalogOverlayError("base catalog records changed")
    records = cast(list[object], records_raw)
    if len(records) != 221:
        raise CatalogOverlayError("base catalog records changed")
    record: dict[str, Any] | None = None
    for candidate in records:
        if not isinstance(candidate, dict):
            continue
        typed_candidate = cast(dict[str, Any], candidate)
        if (
            typed_candidate.get("legacy_method_id")
            == MODERATE_SELECTION_METHOD_ID
        ):
            record = typed_candidate
            break
    if (
        record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD[
            MODERATE_SELECTION_METHOD_ID
        ]
        or record.get("strategy_id")
        != evidence_row.get("strategy_id")
        or record.get("strategy_version")
        != evidence_row.get("strategy_version")
    ):
        raise CatalogOverlayError(
            "wave-12 evidence leaves the validated base universe"
        )
    record.update(
        {
            "candidate_k_semantics": (
                "NOT_APPLICABLE_FROZEN_GRID_PARAMETERS_ARE_"
                "CONFIGURATIONS_NOT_CANDIDATE_POOLS"
            ),
            "combination_count_semantics": (
                "FROZEN_SOURCE_180_PARAMETER_CONFIGURATIONS_"
                "DISTINCT_FROM_360_POSITIONAL_NATIVE_TICKETS"
            ),
            "native_ticket_semantics": (
                "FROZEN_SOURCE_NATIVE_"
                + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE12_METHOD[
                    MODERATE_SELECTION_METHOD_ID
                ]
            ),
            "reproduction_status": "BACKTESTED",
            "status_reason": (
                "Exact frozen-commit function parity passed 3 cases "
                "covering all 180 configurations and 360 positional "
                "tickets; 2099 causal executions completed and 50 "
                "insufficient-history closures remained explicit. No "
                "target outcome selected a grid winner. Compact evidence "
                f"SHA-256 is {evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "PRESERVE_NATIVE_POSITIONAL_DUPLICATES_ACROSS_"
                "FROZEN_GRID_CONFIGURATIONS"
            ),
            "ticket_order_semantics": (
                "FROZEN_PENALTY_HOT_RANK_COLD_GAP_AND_BET_LOOP_"
                "ORDER_BEFORE_ORDERED_20_CONSTRUCTION"
            ),
            "unranked_reason": (
                "RANKED_BACKTEST_EVIDENCE_AVAILABLE"
            ),
        }
    )

    artifacts_raw = catalog.get("source_artifacts")
    if not isinstance(artifacts_raw, list):
        raise CatalogOverlayError("base source artifacts changed")
    cast(list[object], artifacts_raw).append(
        {
            "artifact_name": evidence_path.name,
            "artifact_sha256": evidence_sha256,
            "evidence_role": (
                "SOURCE_NATIVE_WAVE12_BATCH_CAUSAL_BACKTEST"
            ),
        }
    )
    catalog["status_counts"] = EXPECTED_OUTPUT_STATUS_COUNTS
    catalog["catalog_sha256"] = _catalog_hash(catalog)
    return cast(dict[str, object], catalog)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = apply_wave12_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(catalog) + b"\n")


if __name__ == "__main__":
    main()
