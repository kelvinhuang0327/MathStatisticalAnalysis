#!/usr/bin/env python3
"""Apply wave-62 diversified evidence to the full catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_diversified_native_portfolios_wave62 import (
    BACKTEST_METHOD_ID,
    CAUSAL_ELIGIBILITY_RULE,
    ENSEMBLE_METHOD_ID,
    FROZEN_SOURCE_COMMIT,
    NATIVE_TICKET_ORDER_BY_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_METHOD,
    SOURCE_CANDIDATE_K_VALUES_BY_METHOD,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_METHOD,
    SUPPORTED_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "9d80f7e5e6e996b825f19cf8c209f7148576429785a72daa9462134549a8661c"
)
BASE_CATALOG_FILE_SHA256 = (
    "b216eebf3cad8fc47bc75c908f7035a9697cc9165d872f9fae1d9f9ca42b83bd"
)
EXPECTED_EVIDENCE_SHA256 = (
    "7441a0e0007e8d4e53f9e2e05ccc350d20518411b847b6c36ffd07ec4cbbfd3d"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_DIVERSIFIED_WAVE62_EVIDENCE_V1"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_diversified_wave62_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 130,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 5,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 132,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 3,
}
EXPECTED_REPORT_SHA256 = (
    "5e48902cd79eae2498989aae7729b7d6cfafeee949393f1a57c3b7761050612b"
)
EXPECTED_EXECUTION_COUNTS = {
    ENSEMBLE_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 50,
        "OK": 2099,
    },
    BACKTEST_METHOD_ID: {
        "CLOSED_REJECTED": 1649,
        "OK": 500,
    },
}
EXPECTED_NATIVE_COUNT_DISTRIBUTIONS = {
    ENSEMBLE_METHOD_ID: {"3": 2099},
    BACKTEST_METHOD_ID: {"3": 350, "6": 150},
}
EXPECTED_CONFIGURATION_DISTRIBUTIONS = {
    ENSEMBLE_METHOD_ID: {"1": 2099},
    BACKTEST_METHOD_ID: {"1": 350, "2": 150},
}
EXPECTED_DUPLICATE_DISTRIBUTIONS = {
    ENSEMBLE_METHOD_ID: {"0": 2099},
    BACKTEST_METHOD_ID: {
        "0": 350,
        "1": 139,
        "2": 10,
        "3": 1,
    },
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-62 evidence is inconsistent."""


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
        raise CatalogOverlayError("wave-62 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-62 strategy evidence changed"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if not isinstance(method_id, str):
            raise CatalogOverlayError(
                "wave-62 method identity changed"
            )
        by_method[method_id] = row
    if set(by_method) != set(SUPPORTED_METHODS):
        raise CatalogOverlayError("wave-62 method set changed")
    for method_id, strategy in by_method.items():
        if (
            strategy.get("source_sha256")
            != SOURCE_SHA256_BY_METHOD[method_id]
            or strategy.get("execution_status_counts")
            != EXPECTED_EXECUTION_COUNTS[method_id]
            or strategy.get("ok_execution_count")
            != EXPECTED_EXECUTION_COUNTS[method_id]["OK"]
            or strategy.get("closed_execution_count")
            != (
                2149
                - EXPECTED_EXECUTION_COUNTS[method_id]["OK"]
            )
            or strategy.get("candidate_k_distribution")
            != {
                "49": EXPECTED_EXECUTION_COUNTS[method_id]["OK"]
            }
            or strategy.get("combination_count_distribution")
            != EXPECTED_CONFIGURATION_DISTRIBUTIONS[method_id]
            or strategy.get("native_ticket_count_distribution")
            != EXPECTED_NATIVE_COUNT_DISTRIBUTIONS[method_id]
            or strategy.get(
                "native_duplicate_ticket_count_distribution"
            )
            != EXPECTED_DUPLICATE_DISTRIBUTIONS[method_id]
            or strategy.get("source_candidate_k_values")
            != list(SOURCE_CANDIDATE_K_VALUES_BY_METHOD[method_id])
            or strategy.get("native_ticket_semantics")
            != NATIVE_TICKET_SEMANTICS_BY_METHOD[method_id]
            or strategy.get("native_ticket_order")
            != NATIVE_TICKET_ORDER_BY_METHOD[method_id]
            or strategy.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
        ):
            raise CatalogOverlayError(
                f"wave-62 strategy evidence changed: {method_id}"
            )
    return by_method


def _candidate_k_semantics(method_id: str) -> str:
    source_values = "_".join(
        str(value)
        for value in SOURCE_CANDIDATE_K_VALUES_BY_METHOD[method_id]
    )
    return (
        "ORDERED20_INPUT_USES_FULL_49_LEGAL_NUMBER_DOMAIN_DISTINCT_"
        f"FROM_SOURCE_CANDIDATE_K_VALUES_{source_values}_NATIVE_"
        "TICKET_COUNT_CONFIGURATION_COUNT_AND_ORDERED_20"
    )


def _status_reason(
    *,
    method_id: str,
    evidence_sha256: str,
) -> str:
    if method_id == ENSEMBLE_METHOD_ID:
        return (
            "Frozen DiversifiedEnsemble.predict_3bets regenerated three "
            "positional native tickets for 2099 of 2149 targets using "
            "only each target's strictly earlier prefix; the first 50 "
            "targets are CLOSED_INSUFFICIENT_HISTORY by the frozen "
            "clustering minimum. Python and NumPy seeds reset to 42 at "
            "each target, and the ledger preserves the exact output "
            "sequence. Candidate-K, source pools, native ticket count, "
            "configuration count, and ordered-20 remain distinct. "
            f"Compact evidence SHA-256 is {evidence_sha256}."
        )
    return (
        "Frozen run_comprehensive_audit regenerated its DIVERSIFIED "
        "configuration for the declared 150 then 500 horizons: 350 "
        "targets retain one three-ticket block and the overlapping last "
        "150 retain two blocks in source horizon order for six positions; "
        "1649 targets outside both horizons are CLOSED_REJECTED. Python "
        "and NumPy seeds reset to 123 at each diversified horizon start. "
        "The source-declared random comparator is excluded from this "
        "method's native strategy portfolio. Candidate-K, native ticket "
        "count, configuration count, and ordered-20 remain distinct. "
        f"Compact evidence SHA-256 is {evidence_sha256}."
    )


def apply_wave62_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay two independently BACKTESTED diversified methods."""

    catalog, raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        raw_catalog_sha256 != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_schema_version")
        != CATALOG_SCHEMA_VERSION
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
        raise CatalogOverlayError("wave-62 evidence file changed")
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

    for method_id in SUPPORTED_METHODS:
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
                "wave-62 evidence leaves the validated universe"
            )
        duplicate_distribution = cast(
            dict[str, int],
            evidence_row[
                "native_duplicate_ticket_count_distribution"
            ],
        )
        record.update(
            {
                "candidate_k_semantics": _candidate_k_semantics(
                    method_id
                ),
                "combination_count_semantics": (
                    "EXECUTED_SOURCE_CONFIGURATION_BLOCK_COUNT_"
                    "DISTINCT_FROM_SOURCE_CANDIDATE_K_NATIVE_TICKET_"
                    "COUNT_AND_ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_METHOD[method_id]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": _status_reason(
                    method_id=method_id,
                    evidence_sha256=evidence_sha256,
                ),
                "ticket_duplicate_semantics": (
                    "FROZEN_SOURCE_NATIVE_DUPLICATES_PRESERVED_BEFORE_"
                    "ORDERED_20_DERIVATION_DISTRIBUTION_"
                    + "_".join(
                        f"{key}:{value}"
                        for key, value in duplicate_distribution.items()
                    )
                ),
                "ticket_order_semantics": (
                    NATIVE_TICKET_ORDER_BY_METHOD[method_id]
                    + "_BEFORE_ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": (
                    "RANKED_BACKTEST_EVIDENCE_AVAILABLE_PARTIAL_COVERAGE"
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
                "SOURCE_NATIVE_WAVE62_DIVERSIFIED_ENSEMBLE_AND_"
                "HORIZON_WRAPPER_CAUSAL_BACKTEST_PROOF"
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
    catalog = apply_wave62_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    payload = _canonical_bytes(catalog) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "catalog_sha256": cast(
                    dict[str, Any],
                    catalog,
                )["catalog_sha256"],
                "output_file": str(args.output_file),
                "physical_file_sha256": hashlib.sha256(
                    payload
                ).hexdigest(),
                "status_counts": catalog["status_counts"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
