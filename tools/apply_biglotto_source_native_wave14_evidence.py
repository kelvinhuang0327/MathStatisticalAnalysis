#!/usr/bin/env python3
"""Apply mixed wave-14 evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave14 import (
    CANDIDATE_K_BY_SOURCE_NATIVE_WAVE14_METHOD,
    GRAPH_PREDICTOR_METHOD_ID,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE14_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE14_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "9dc3608286ed37fbf98798958c2c392f80a9508784c69d46d7bb0f61a62fa4ad"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE14_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "07caf36d15c42a8b34445e854bb6bb77a37035a18165861cc23513b2b192ff8a"
)
SPECIAL_METHOD_ID = "tools/biglotto_special_v4.py"
SPECIAL_SOURCE_SHA256 = (
    "00256ce82d7cd515550e71274f4cf6d3a546c2660d2640650099533db202c7a7"
)
SPECIAL_REASON_CODE = (
    "SPECIAL_NUMBER_RANKING_WITHOUT_MAIN_NUMBER_TICKET_CONSTRUCTION"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 37,
    "CLOSED_UNEXECUTABLE": 27,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 153,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 39,
    "CLOSED_UNEXECUTABLE": 28,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 150,
}
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class CatalogOverlayError(ValueError):
    """The catalog or wave-14 evidence is inconsistent."""


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


def _validate_evidence(
    evidence: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
    ):
        raise CatalogOverlayError("wave-14 evidence identity changed")
    strategies_raw = evidence.get("strategies")
    if not isinstance(strategies_raw, list):
        raise CatalogOverlayError(
            "wave-14 evidence must contain two strategies"
        )
    strategies: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], strategies_raw):
        if not isinstance(candidate, dict):
            raise CatalogOverlayError("wave-14 strategy is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if (
            type(method_id) is not str
            or method_id in strategies
            or method_id
            not in SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD[method_id]
            or row.get("candidate_k")
            != CANDIDATE_K_BY_SOURCE_NATIVE_WAVE14_METHOD[method_id]
            or row.get("combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE14_METHOD[
                method_id
            ]
            or type(row.get("ok_execution_count")) is not int
            or cast(int, row["ok_execution_count"]) <= 0
        ):
            raise CatalogOverlayError(
                "wave-14 strategy identity changed"
            )
        strategies[method_id] = row
    if set(strategies) != set(
        SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD
    ):
        raise CatalogOverlayError("wave-14 evidence omits a strategy")

    dispositions_raw = evidence.get("static_dispositions")
    if not isinstance(dispositions_raw, list):
        raise CatalogOverlayError(
            "wave-14 evidence must contain one static disposition"
        )
    dispositions = cast(list[object], dispositions_raw)
    if len(dispositions) != 1 or not isinstance(dispositions[0], dict):
        raise CatalogOverlayError(
            "wave-14 evidence must contain one static disposition"
        )
    disposition = cast(dict[str, Any], dispositions[0])
    facts_raw = disposition.get("decisive_source_facts")
    if (
        disposition.get("legacy_method_id") != SPECIAL_METHOD_ID
        or disposition.get("source_sha256") != SPECIAL_SOURCE_SHA256
        or disposition.get("reproduction_status")
        != "CLOSED_UNEXECUTABLE"
        or disposition.get("reason_code") != SPECIAL_REASON_CODE
        or type(disposition.get("source_blob_id")) is not str
        or len(cast(str, disposition["source_blob_id"])) != 40
        or type(disposition.get("source_byte_size")) is not int
        or cast(int, disposition["source_byte_size"]) <= 0
        or type(disposition.get("status_reason")) is not str
        or not isinstance(facts_raw, list)
        or len(cast(list[object], facts_raw)) < 3
    ):
        raise CatalogOverlayError(
            "wave-14 static disposition changed"
        )
    return strategies, disposition


def apply_wave14_evidence(
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
        or catalog.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
    ):
        raise CatalogOverlayError("base catalog identity changed")
    if evidence_sha256 != EXPECTED_EVIDENCE_SHA256:
        raise CatalogOverlayError("wave-14 evidence file changed")
    _validate_digest(evidence_sha256, "evidence file digest")
    strategies, disposition = _validate_evidence(evidence)

    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise CatalogOverlayError("base catalog records changed")
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], records_raw):
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "base catalog record is invalid"
            )
        record = cast(dict[str, Any], candidate)
        method_id = record.get("legacy_method_id")
        if isinstance(method_id, str):
            record_by_method[method_id] = record
    if len(record_by_method) != 221:
        raise CatalogOverlayError("base catalog records changed")

    for method_id, evidence_row in strategies.items():
        record = record_by_method.get(method_id)
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256")
            != evidence_row.get("source_sha256")
        ):
            raise CatalogOverlayError(
                "wave-14 evidence leaves the validated universe"
            )
        is_graph = method_id == GRAPH_PREDICTOR_METHOD_ID
        record.update(
            {
                "candidate_k_semantics": (
                    "PAGERANK_TOP15_INTERMEDIATE_POOL_DISTINCT_FROM_"
                    "ONE_NATIVE_TICKET"
                    if is_graph
                    else "NOT_APPLICABLE_FULL_49_NUMBER_RANKING"
                ),
                "combination_count_semantics": (
                    "NOT_APPLICABLE_SINGLE_SOURCE_CONFIGURATION"
                    if is_graph
                    else "SEVEN_FIXED_BIG_LOTTO_LAMBDA_CONFIGURATIONS_"
                    "DISTINCT_FROM_SEVEN_POSITIONAL_NATIVE_TICKETS"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE14_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Exact frozen-class parity passed three causal "
                    "history cutoffs; "
                    f"{evidence_row['ok_execution_count']} executions "
                    "completed with insufficient-history closures "
                    "preserved. No target outcome selected a "
                    "configuration. Compact evidence SHA-256 is "
                    f"{evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_NATIVE_POSITIONAL_DUPLICATES_ACROSS_"
                    "LAMBDA_CONFIGURATIONS"
                    if not is_graph
                    else "NOT_APPLICABLE_SINGLE_NATIVE_TICKET"
                ),
                "ticket_order_semantics": (
                    "FROZEN_PAGERANK_THEN_GREEDY_CLIQUE_ORDER_BEFORE_"
                    "ORDERED_20_CONSTRUCTION"
                    if is_graph
                    else "FROZEN_BIG_LOTTO_LAMBDA_DECLARATION_ORDER_"
                    "BEFORE_ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": (
                    "RANKED_BACKTEST_EVIDENCE_AVAILABLE"
                ),
            }
        )

    special_record = record_by_method.get(SPECIAL_METHOD_ID)
    if (
        special_record is None
        or special_record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or special_record.get("source_sha256")
        != disposition.get("source_sha256")
        or special_record.get("source_blob_id")
        != disposition.get("source_blob_id")
        or special_record.get("source_byte_size")
        != disposition.get("source_byte_size")
    ):
        raise CatalogOverlayError(
            "wave-14 disposition leaves the validated universe"
        )
    special_record.update(
        {
            "candidate_k_semantics": (
                "TOP4_SPECIAL_NUMBER_CANDIDATES_NOT_MAIN_TICKETS"
            ),
            "combination_count_semantics": (
                "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
            ),
            "native_ticket_semantics": (
                "NO_EXECUTABLE_BIG_LOTTO_MAIN_NUMBER_TICKETS"
            ),
            "reproduction_status": "CLOSED_UNEXECUTABLE",
            "status_reason": (
                f"{disposition['status_reason']} Frozen-source wave-14 "
                f"evidence SHA-256 is {evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
            ),
            "ticket_order_semantics": (
                "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
            ),
            "unranked_reason": (
                f"CLOSED_UNEXECUTABLE:{SPECIAL_REASON_CODE}"
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
                "SOURCE_NATIVE_WAVE14_CAUSAL_BACKTEST_AND_SPECIAL_"
                "POSITION_DISPOSITION"
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
    catalog = apply_wave14_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(catalog) + b"\n")


if __name__ == "__main__":
    main()
