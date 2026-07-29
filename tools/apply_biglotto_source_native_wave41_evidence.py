#!/usr/bin/env python3
"""Apply wave-41 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave41 import (
    FROZEN_NETWORKX_SEMANTICS,
    GRAPH_METHOD_ID,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE41_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE41_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE41_METHOD,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "ed095e2bd580075b42f6be5239bbb2bbf7cf7552e551aee96b9ab8a7c7dba88f"
)
BASE_CATALOG_FILE_SHA256 = (
    "a1041e8fac30b9680a3b36adbf4a0b65063e2e3c7ea8482eb1bb7f08283dc332"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE41_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "03afecea6e2288ca34258d8299a557bcff20dc1aa3a268962b4aa652c58f859f"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_source_native_wave41_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 79,
    "CLOSED_UNEXECUTABLE": 64,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 73,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 80,
    "CLOSED_UNEXECUTABLE": 64,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 72,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-41 evidence is inconsistent."""


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
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CatalogOverlayError(f"{path}: invalid JSON") from exc
    if not isinstance(document, dict):
        raise CatalogOverlayError(f"{path}: top level must be an object")
    return (
        cast(dict[str, Any], document),
        hashlib.sha256(raw).hexdigest(),
    )


def _catalog_hash(document: dict[str, Any]) -> str:
    reduced = {
        key: value
        for key, value in document.items()
        if key != "catalog_sha256"
    }
    return hashlib.sha256(_canonical_bytes(reduced)).hexdigest()


def _validate_evidence(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
        or evidence.get("base_catalog_file_sha256")
        != BASE_CATALOG_FILE_SHA256
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256")
        != "460d3514f0a5928787e0f14ae7fc353dc18ac35e7e99a93300ec254e2e56d055"
    ):
        raise CatalogOverlayError("wave-41 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise CatalogOverlayError(
            "wave-41 evidence must contain one strategy"
        )
    row = cast(dict[str, Any], rows[0])
    if (
        row.get("legacy_method_id") != GRAPH_METHOD_ID
        or row.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE41_METHOD[
            GRAPH_METHOD_ID
        ]
        or row.get("native_ticket_count_upper_bound")
        != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD[
            GRAPH_METHOD_ID
        ]
        or row.get("native_ticket_count_distribution") != {"2": 2099}
        or row.get("native_duplicate_ticket_count_distribution")
        != {"0": 2099}
        or row.get("source_method_combination_count")
        != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD[
            GRAPH_METHOD_ID
        ]
        or row.get("source_method_combination_members")
        != list(
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE41_METHOD[
                GRAPH_METHOD_ID
            ]
        )
        or row.get("closed_execution_count") != 50
        or row.get("ok_execution_count") != 2099
        or row.get("candidate_k_distribution") != {"null": 2099}
        or row.get("random_protocol")
        != "NONE_DETERMINISTIC_NATIVE_SELECTION"
        or row.get("frozen_networkx_semantics")
        != FROZEN_NETWORKX_SEMANTICS
        or row.get("graph_edge_count_minimum") != 156
        or row.get("graph_edge_count_maximum") != 942
        or row.get("graph_edge_count_sequence_sha256")
        != "51bb935dd96d992abf0e58b704d1ca35e79847806d78a903ce4f210270c392c6"
    ):
        raise CatalogOverlayError("wave-41 strategy identity changed")
    parity = cast(dict[str, Any], evidence.get("parity", {}))
    if (
        parity.get("case_count") != 65
        or parity.get("status") != "PASS"
        or parity.get("parity_sha256")
        != "bbe310f97a66eb4f2b7163e14f2ef373721a4cd807f277f628b0744a79e11863"
        or parity.get("networkx_reference_version") != "3.2.1"
        or len(cast(list[object], parity.get("source_artifacts", [])))
        != 1
        or len(cast(list[object], parity.get("support_artifacts", [])))
        != 4
        or not isinstance(
            parity.get("frozen_source_behavior_facts"), dict
        )
    ):
        raise CatalogOverlayError("wave-41 parity evidence changed")
    return row


def apply_wave41_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay the validated wave-41 BACKTESTED disposition."""

    catalog, raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        raw_catalog_sha256 != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION
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
        raise CatalogOverlayError("wave-41 evidence file changed")
    evidence_row = _validate_evidence(evidence)

    records = cast(list[object], catalog.get("records", []))
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in records:
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
    record = record_by_method.get(GRAPH_METHOD_ID)
    if (
        record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or record.get("source_sha256")
        != evidence_row.get("source_sha256")
    ):
        raise CatalogOverlayError(
            "wave-41 evidence leaves the validated universe"
        )
    record.update(
        {
            "candidate_k_semantics": (
                "NULL_NO_COMBINATORIAL_CANDIDATE_K"
            ),
            "combination_count_semantics": (
                "FROZEN_TWO_SOURCE_METHOD_CONFIGURATIONS_DISTINCT_"
                "FROM_NATIVE_TICKETS_AND_ORDERED_20"
            ),
            "native_ticket_semantics": (
                "FROZEN_SOURCE_NATIVE_"
                + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE41_METHOD[
                    GRAPH_METHOD_ID
                ]
            ),
            "reproduction_status": "BACKTESTED",
            "status_reason": (
                "Frozen source parity covered 65 causal histories "
                "against NetworkX 3.2.1 weighted-betweenness behavior "
                "and preserved graph-centrality then unified-deviation "
                "source order. 2099 causal executions completed and 50 "
                "minimum-history closures remained explicit. Compact "
                f"evidence SHA-256 is {evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "PRESERVE_FROZEN_NATIVE_POSITIONS_AND_ANY_EXACT_"
                "DUPLICATES"
            ),
            "ticket_order_semantics": (
                "GRAPH_CENTRALITY_TICKET_THEN_UNIFIED_DEVIATION_"
                "BASELINE_TICKET_BEFORE_ORDERED_20"
            ),
            "unranked_reason": "RANKED_BACKTEST_EVIDENCE_AVAILABLE",
        }
    )

    source_artifacts = cast(
        list[object],
        catalog.get("source_artifacts", []),
    )
    source_artifacts.append(
        {
            "artifact_name": EVIDENCE_ARTIFACT_NAME,
            "artifact_sha256": evidence_sha256,
            "evidence_role": (
                "SOURCE_NATIVE_WAVE41_GRAPH_CENTRALITY_CAUSAL_BACKTEST"
            ),
        }
    )
    status_counts = Counter(
        cast(str, cast(dict[str, Any], item)["reproduction_status"])
        for item in records
    )
    if dict(status_counts) != EXPECTED_OUTPUT_STATUS_COUNTS:
        raise CatalogOverlayError("output status counts changed")
    catalog["status_counts"] = dict(EXPECTED_OUTPUT_STATUS_COUNTS)
    catalog["catalog_sha256"] = _catalog_hash(catalog)
    return cast(dict[str, object], catalog)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    catalog = apply_wave41_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    payload = _canonical_bytes(catalog) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "catalog_sha256": catalog["catalog_sha256"],
                "output_file": str(args.output_file),
                "physical_file_sha256": hashlib.sha256(payload).hexdigest(),
                "status_counts": catalog["status_counts"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
