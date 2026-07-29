#!/usr/bin/env python3
"""Apply wave-22 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave22 import (
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE22_METHOD,
    SMART_2BET_METHOD_ID,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE22_METHOD,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "87b00e843eca65f043e2313199ce5d984e4b433f974848da97b47cfcc64be1f2"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE22_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "76aa41b01d62df0aa78bf354eb1a40ffdf0fae9ffd576e527576d9ca9294ab04"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 45,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 134,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 46,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 133,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-22 evidence is inconsistent."""


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
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256")
        != "056df37a2a17b2b45a7f194a9b54977308e7366fe7ddbcab55b6ae4b43c0a808"
    ):
        raise CatalogOverlayError("wave-21 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise CatalogOverlayError(
            "wave-21 evidence must contain one strategy"
        )
    strategy = cast(dict[str, Any], rows[0])
    if (
        strategy.get("legacy_method_id")
        != SMART_2BET_METHOD_ID
        or strategy.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE22_METHOD[
            SMART_2BET_METHOD_ID
        ]
        or strategy.get("native_ticket_count") != 2
        or strategy.get("combination_count") != 2
        or strategy.get("candidate_k") is not None
        or strategy.get("native_duplicate_ticket_count_distribution")
        != {"0": 2148}
        or strategy.get("frequency_candidate_count_range") != [6, 49]
        or strategy.get("ok_execution_count") != 2148
    ):
        raise CatalogOverlayError("wave-21 strategy identity changed")
    parity = cast(dict[str, Any], evidence.get("parity", {}))
    if (
        parity.get("case_count") != 6
        or parity.get("status") != "PASS"
        or not isinstance(parity.get("source_artifact"), dict)
        or not isinstance(parity.get("support_artifacts"), list)
    ):
        raise CatalogOverlayError("wave-21 parity evidence changed")
    return strategy


def apply_wave22_evidence(
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
        raise CatalogOverlayError("wave-21 evidence file changed")
    strategy = _validate_evidence(evidence)

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

    record = record_by_method.get(SMART_2BET_METHOD_ID)
    if (
        record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or record.get("source_sha256")
        != strategy.get("source_sha256")
    ):
        raise CatalogOverlayError(
            "wave-21 evidence leaves the validated universe"
        )
    record.update(
        {
            "candidate_k_semantics": (
                "NOT_APPLICABLE_NO_DECLARED_PRE_TICKET_CANDIDATE_K"
            ),
            "combination_count_semantics": (
                "TWO_FROZEN_PREDICTOR_CONFIGURATIONS_DISTINCT_FROM_"
                "TWO_"
                "POSITIONAL_NATIVE_TICKETS"
            ),
            "native_ticket_semantics": (
                "FROZEN_SOURCE_NATIVE_"
                + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE22_METHOD[
                    SMART_2BET_METHOD_ID
                ]
            ),
            "reproduction_status": "BACKTESTED",
            "status_reason": (
                "Exact frozen-method selection parity passed six pinned "
                "causal history cutoffs with UnifiedPredictionEngine, "
                "rules, configuration loader, and prediction configuration "
                "identities pinned. The conservative True-Frequency-50 "
                "ticket and aggressive full-history Deviation ticket remain "
                "positional. 2148 causal executions completed and one "
                "insufficient-history closure remained explicit. Compact "
                "evidence SHA-256 is "
                f"{evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "PRESERVE_BOTH_POSITIONAL_TICKETS_IF_TRUE_FREQUENCY_"
                "AND_DEVIATION_EMIT_THE_SAME_TICKET"
            ),
            "ticket_order_semantics": (
                "FROZEN_CONSERVATIVE_TRUE_FREQUENCY_50_THEN_"
                "AGGRESSIVE_FULL_HISTORY_DEVIATION_ORDER_BEFORE_"
                "ORDERED_20_CONSTRUCTION"
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
            "artifact_name": evidence_path.name,
            "artifact_sha256": evidence_sha256,
            "evidence_role": (
                "SOURCE_NATIVE_WAVE22_SMART_TWO_BET_CAUSAL_"
                "BACKTEST"
            ),
        }
    )
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
    catalog = apply_wave22_evidence(
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
