#!/usr/bin/env python3
"""Apply wave-58 enhanced-dual and seeded-v6 evidence to the catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_dual_seeded_native_portfolios_wave58 import (
    CAUSAL_ELIGIBILITY_RULE,
    ENHANCED_DUAL_METHOD_ID,
    FROZEN_SOURCE_COMMIT,
    MINIMUM_HISTORY_DRAWS_BY_SOURCE_NATIVE_WAVE58_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE58_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE58_METHOD,
    SEEDED_V6_METHOD_ID,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE58_METHOD,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE58_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "6316066d537d3966d25549f7a8d220db13a5b5b506345f779dcfdb7e75c7f476"
)
BASE_CATALOG_FILE_SHA256 = (
    "b2ae5e48fa59f6619b853d6bdf3d4a2e5a05f5aa840e139950b2539cdc9686f7"
)
EXPECTED_EVIDENCE_SHA256 = (
    "7db702bf9754c1a2d037130b9a11ce7b52e14121097e048d6c09cf505832ad35"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_DUAL_SEEDED_WAVE58_EVIDENCE_V1"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_dual_seeded_wave58_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 124,
    "CLOSED_UNEXECUTABLE": 73,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 12,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 126,
    "CLOSED_UNEXECUTABLE": 73,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 10,
}
EXPECTED_REPORT_SHA256 = (
    "9d797d7300cebba69af48389ac792bf23520b043dad39b63c5469f3c05509f04"
)
EXPECTED_EXECUTION_COUNTS = {
    ENHANCED_DUAL_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 100,
        "OK": 2049,
    },
    SEEDED_V6_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
}
EXPECTED_DUPLICATE_DISTRIBUTIONS = {
    ENHANCED_DUAL_METHOD_ID: {"0": 2048, "1": 1},
    SEEDED_V6_METHOD_ID: {"0": 2148},
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-58 evidence is inconsistent."""


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
        raise CatalogOverlayError(
            f"{path}: top level must be an object"
        )
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
) -> dict[str, dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
        or evidence.get("base_catalog_file_sha256")
        != BASE_CATALOG_FILE_SHA256
        or evidence.get("causal_eligibility_rule")
        != CAUSAL_ELIGIBILITY_RULE
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256") != EXPECTED_REPORT_SHA256
    ):
        raise CatalogOverlayError("wave-58 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-58 strategy evidence changed"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if not isinstance(method_id, str):
            raise CatalogOverlayError(
                "wave-58 method identity changed"
            )
        by_method[method_id] = row
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS):
        raise CatalogOverlayError("wave-58 method set changed")
    for method_id, strategy in by_method.items():
        minimum = (
            MINIMUM_HISTORY_DRAWS_BY_SOURCE_NATIVE_WAVE58_METHOD[
                method_id
            ]
        )
        ok_count = 2149 - minimum
        native_count = (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE58_METHOD[
                method_id
            ]
        )
        if (
            strategy.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE58_METHOD[method_id]
            or strategy.get("execution_status_counts")
            != EXPECTED_EXECUTION_COUNTS[method_id]
            or strategy.get("ok_execution_count") != ok_count
            or strategy.get("closed_execution_count") != minimum
            or strategy.get("candidate_k_distribution")
            != {"49": ok_count}
            or strategy.get("combination_count_distribution")
            != {"null": ok_count}
            or strategy.get("native_ticket_count_distribution")
            != {str(native_count): ok_count}
            or strategy.get(
                "native_duplicate_ticket_count_distribution"
            )
            != EXPECTED_DUPLICATE_DISTRIBUTIONS[method_id]
            or strategy.get("source_candidate_k_values")
            != list(
                SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    method_id
                ]
            )
            or strategy.get("native_ticket_semantics")
            != NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE58_METHOD[
                method_id
            ]
            or strategy.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
        ):
            raise CatalogOverlayError(
                f"wave-58 strategy evidence changed: {method_id}"
            )
    return by_method


def _candidate_k_semantics(method_id: str) -> str:
    source_values = "_".join(
        str(value)
        for value in (
            SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE58_METHOD[
                method_id
            ]
        )
    )
    return (
        "ORDERED20_INPUT_USES_FULL_49_LEGAL_NUMBER_DOMAIN_DISTINCT_"
        f"FROM_SOURCE_CANDIDATE_K_VALUES_{source_values}_NATIVE_"
        "TICKET_COUNT_LOCAL_CONFIGURATION_COUNT_AND_ORDERED_20"
    )


def apply_wave58_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay two independently BACKTESTED source-native methods."""

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
        raise CatalogOverlayError("wave-58 evidence file changed")
    strategy_evidence = _validate_evidence(evidence)

    records = cast(list[object], catalog.get("records", []))
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in records:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError("base catalog record is invalid")
        record = cast(dict[str, Any], candidate)
        method_id = record.get("legacy_method_id")
        if isinstance(method_id, str):
            record_by_method[method_id] = record
    if len(record_by_method) != 221:
        raise CatalogOverlayError("base catalog records changed")

    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS:
        record = record_by_method.get(method_id)
        evidence_row = strategy_evidence[method_id]
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256")
            != evidence_row.get("source_sha256")
        ):
            raise CatalogOverlayError(
                "wave-58 evidence leaves the validated universe"
            )
        minimum = (
            MINIMUM_HISTORY_DRAWS_BY_SOURCE_NATIVE_WAVE58_METHOD[
                method_id
            ]
        )
        ok_count = 2149 - minimum
        native_count = (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE58_METHOD[
                method_id
            ]
        )
        random_note = (
            "source reset Python and NumPy RNG seeds to 42 at each "
            "target and the frozen-runtime ledger preserves each output"
            if method_id == SEEDED_V6_METHOD_ID
            else "the source selection path is deterministic"
        )
        duplicate_distribution = evidence_row[
            "native_duplicate_ticket_count_distribution"
        ]
        record.update(
            {
                "candidate_k_semantics": _candidate_k_semantics(
                    method_id
                ),
                "combination_count_semantics": (
                    "NULL_SINGLE_LOCAL_SOURCE_CONFIGURATION_DISTINCT_"
                    "FROM_SOURCE_CANDIDATE_K_NATIVE_TICKET_COUNT_AND_"
                    "ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE58_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "The frozen public source entrypoint regenerated "
                    f"{native_count} positional native tickets for "
                    f"{ok_count} of 2149 targets using only each target's "
                    "strictly earlier history prefix; "
                    f"{minimum} leading targets are explicitly closed for "
                    "insufficient source history. "
                    f"Randomness disposition: {random_note}. Candidate-K, "
                    "native ticket count, local configuration count, "
                    "combination count, and ordered-20 remain distinct. "
                    f"Compact evidence SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "FROZEN_SOURCE_NATIVE_DUPLICATES_PRESERVED_BEFORE_"
                    "ORDERED_20_DERIVATION_DISTRIBUTION_"
                    + "_".join(
                        f"{key}:{value}"
                        for key, value in cast(
                            dict[str, int],
                            duplicate_distribution,
                        ).items()
                    )
                ),
                "ticket_order_semantics": (
                    "FROZEN_SOURCE_POSITIONAL_TICKET_ORDER_PRESERVED_"
                    "BEFORE_ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": (
                    "RANKED_BACKTEST_EVIDENCE_AVAILABLE"
                ),
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
                "SOURCE_NATIVE_WAVE58_ENHANCED_DUAL_AND_SEEDED_V6_"
                "FULL_PREFIX_CAUSAL_BACKTEST_PROOF"
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
    catalog = apply_wave58_evidence(
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
                "physical_file_sha256": hashlib.sha256(
                    payload
                ).hexdigest(),
                "status_counts": catalog["status_counts"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
