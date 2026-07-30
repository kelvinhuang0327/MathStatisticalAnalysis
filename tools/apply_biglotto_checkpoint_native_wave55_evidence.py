#!/usr/bin/env python3
"""Apply wave-55 frozen-checkpoint evidence to the full catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_checkpoint_native_portfolios_wave55 import (
    CAUSAL_ELIGIBILITY_RULE,
    CHECKPOINT_INTRODUCTION_COMMIT,
    CHECKPOINT_INTRODUCTION_TIME,
    FROZEN_SOURCE_COMMIT,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE55_METHOD,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE55_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "6599e096044c967623bdf7d58f4fbe0e11515459bd77613cb389754ae72a58a1"
)
BASE_CATALOG_FILE_SHA256 = (
    "023434b64df1af74cde40191474133709eff35401273fe0f29d17b70009642f5"
)
EXPECTED_EVIDENCE_SHA256 = (
    "080e64dc16e80941b1700c1425e6a7527537eca51235e2957aacc01e32e4f4ca"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_CHECKPOINT_NATIVE_WAVE55_EVIDENCE_V1"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_checkpoint_native_wave55_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 121,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 24,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 123,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 22,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-55 evidence is inconsistent."""


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
        or evidence.get("checkpoint_introduction_commit")
        != CHECKPOINT_INTRODUCTION_COMMIT
        or evidence.get("checkpoint_introduction_time")
        != CHECKPOINT_INTRODUCTION_TIME
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256")
        != "63fe6c56873b2d14a92c8a92c13e5d5e6e69fcdb3061e6f7a3286a2942ba1993"
    ):
        raise CatalogOverlayError("wave-55 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-55 strategy evidence changed"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if (
            method_id not in SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS
            or method_id in by_method
        ):
            raise CatalogOverlayError(
                "wave-55 strategy method set changed"
            )
        typed_method_id = cast(str, method_id)
        if (
            row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE55_METHOD[
                typed_method_id
            ]
            or row.get("execution_status_counts")
            != {"CLOSED_REJECTED": 2101, "OK": 48}
            or row.get("ok_execution_count") != 48
            or row.get("closed_execution_count") != 2101
            or row.get("candidate_k_distribution") != {"49": 48}
            or row.get("combination_count_distribution")
            != {"null": 48}
            or row.get("native_ticket_count_distribution")
            != {
                str(
                    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD[
                        typed_method_id
                    ]
                ): 48
            }
            or row.get("native_duplicate_ticket_count_distribution")
            != {"0": 48}
            or row.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
        ):
            raise CatalogOverlayError(
                f"wave-55 strategy evidence changed: {method_id}"
            )
        by_method[typed_method_id] = row
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS):
        raise CatalogOverlayError("wave-55 strategy evidence is incomplete")
    return by_method


def apply_wave55_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay both validated wave-55 BACKTESTED dispositions."""

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
        raise CatalogOverlayError("wave-55 evidence file changed")
    evidence_by_method = _validate_evidence(evidence)

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
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS:
        record = record_by_method.get(method_id)
        evidence_row = evidence_by_method[method_id]
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256")
            != evidence_row.get("source_sha256")
        ):
            raise CatalogOverlayError(
                "wave-55 evidence leaves the validated universe"
            )
        record.update(
            {
                "candidate_k_semantics": (
                    "ORDERED20_INPUT_USES_FULL_49_LEGAL_NUMBER_DOMAIN_"
                    "DISTINCT_FROM_SOURCE_INTERNAL_CANDIDATE_LIMITS_"
                    "NATIVE_TICKET_COUNT_AND_ORDERED_20"
                ),
                "combination_count_semantics": (
                    "NULL_SINGLE_LOCAL_SOURCE_CONFIGURATION_DISTINCT_"
                    "FROM_CANDIDATE_K_NATIVE_TICKET_COUNT_AND_ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE55_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Exact frozen high-level expert portfolio and checkpoint "
                    "execution regenerated all "
                    f"{48 * NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD[method_id]} "
                    "positional tickets across 48 causal targets. The "
                    "checkpoint Git-introduction date is the conservative "
                    "boundary: this method retained 2101 pre-boundary "
                    "CLOSED_REJECTED results. Candidate-K, source-internal "
                    "candidate limits, one local configuration, native ticket "
                    "count, expert position order, duplicates, and ordered-20 "
                    "remain distinct. Compact evidence "
                    f"SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_ALL_FROZEN_EXPERT_POSITIONAL_NATIVE_TICKETS_"
                    "INCLUDING_DUPLICATES_BEFORE_ORDERED_20_DERIVATION"
                ),
                "ticket_order_semantics": (
                    "FROZEN_SOURCE_EXPERT_POSITION_ORDER_BEFORE_ORDERED_20_"
                    "CONSTRUCTION"
                ),
                "unranked_reason": (
                    "RANKED_BACKTEST_EVIDENCE_AVAILABLE_WITH_PARTIAL_"
                    "CAUSAL_CHECKPOINT_COVERAGE"
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
                "SOURCE_NATIVE_WAVE55_ORTHOGONAL_AND_SIX_EXPERT_FROZEN_"
                "CHECKPOINT_PARTIAL_COVERAGE_CAUSAL_BACKTEST"
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
    catalog = apply_wave55_evidence(
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
