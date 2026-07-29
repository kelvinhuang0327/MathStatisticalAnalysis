#!/usr/bin/env python3
"""Apply wave-57 HPSB backtest and exact-alias evidence to the catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_hpsb_native_portfolios_wave57 import (
    CAUSAL_ELIGIBILITY_RULE,
    ENSEMBLE_ALIAS_METHOD_ID,
    FROZEN_SOURCE_COMMIT,
    HPSB_METHOD_ID,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE57_METHOD,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE57_METHOD,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "46f4a8aab26f63db2db1c1299e90bd9e516d10f53fdfcb35251d18259a47278b"
)
BASE_CATALOG_FILE_SHA256 = (
    "524cbf255ee3d791691ce6f946b554ff2e2b941c5815967e6f874a7c7f3ea465"
)
EXPECTED_EVIDENCE_SHA256 = (
    "235947a7035aa43396125ba3340d48872dd81a60a3f367a1908da98dbf4b0512"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_HPSB_NATIVE_WAVE57_EVIDENCE_V1"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_hpsb_native_wave57_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 123,
    "CLOSED_UNEXECUTABLE": 73,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 14,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 124,
    "CLOSED_UNEXECUTABLE": 73,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 12,
}
EXPECTED_REPORT_SHA256 = (
    "a419af476eb6bb3cc8205b40c42c1a5602cd7af6c5b92e49557abeccebbd323d"
)


class CatalogOverlayError(ValueError):
    """The catalog or wave-57 evidence is inconsistent."""


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
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_alias = {
        "alias_method_id": ENSEMBLE_ALIAS_METHOD_ID,
        "canonical_method_id": HPSB_METHOD_ID,
        "exact_match_count": 2149,
        "reason_code": (
            "EXACT_ALL_TARGET_DEFAULT_ENTRYPOINT_ALIAS_TO_HPSB_V2"
        ),
        "target_count": 2149,
    }
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
        or evidence.get("alias_disposition") != expected_alias
    ):
        raise CatalogOverlayError("wave-57 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise CatalogOverlayError(
            "wave-57 canonical strategy evidence changed"
        )
    strategy = cast(dict[str, Any], rows[0])
    if (
        strategy.get("legacy_method_id") != HPSB_METHOD_ID
        or strategy.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE57_METHOD[HPSB_METHOD_ID]
        or strategy.get("execution_status_counts")
        != {"CLOSED_INSUFFICIENT_HISTORY": 1, "OK": 2148}
        or strategy.get("ok_execution_count") != 2148
        or strategy.get("closed_execution_count") != 1
        or strategy.get("candidate_k_distribution") != {"49": 2148}
        or strategy.get("combination_count_distribution")
        != {"null": 2148}
        or strategy.get("native_ticket_count_distribution")
        != {"1": 2148}
        or strategy.get("native_duplicate_ticket_count_distribution")
        != {"0": 2148}
        or strategy.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
    ):
        raise CatalogOverlayError(
            "wave-57 HPSB strategy evidence changed"
        )
    return strategy, cast(dict[str, Any], expected_alias)


def apply_wave57_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay one BACKTESTED method and one exact duplicate alias."""

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
        raise CatalogOverlayError("wave-57 evidence file changed")
    strategy_evidence, alias_evidence = _validate_evidence(evidence)

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
    hpsb_record = record_by_method.get(HPSB_METHOD_ID)
    alias_record = record_by_method.get(ENSEMBLE_ALIAS_METHOD_ID)
    if (
        hpsb_record is None
        or alias_record is None
        or hpsb_record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or alias_record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or hpsb_record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or alias_record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or hpsb_record.get("source_sha256")
        != strategy_evidence.get("source_sha256")
        or alias_record.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE57_METHOD[
            ENSEMBLE_ALIAS_METHOD_ID
        ]
    ):
        raise CatalogOverlayError(
            "wave-57 evidence leaves the validated universe"
        )
    canonical_strategy_id = cast(str, hpsb_record["strategy_id"])
    hpsb_record.update(
        {
            "candidate_k_semantics": (
                "ORDERED20_INPUT_USES_FULL_49_LEGAL_NUMBER_DOMAIN_"
                "DISTINCT_FROM_SOURCE_CANDIDATE_K_NATIVE_TICKET_COUNT_"
                "LOCAL_CONFIGURATION_COUNT_AND_ORDERED_20"
            ),
            "combination_count_semantics": (
                "NULL_SINGLE_LOCAL_SOURCE_CONFIGURATION_DISTINCT_FROM_"
                "CANDIDATE_K_NATIVE_TICKET_COUNT_AND_ORDERED_20"
            ),
            "native_ticket_semantics": (
                "FROZEN_SOURCE_NATIVE_"
                + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE57_METHOD[
                    HPSB_METHOD_ID
                ]
            ),
            "reproduction_status": "BACKTESTED",
            "status_reason": (
                "The frozen public predict_hpsb_v2 entrypoint regenerated "
                "one positional native ticket for all 2149 targets from "
                "their full strictly earlier history prefixes. Ordered-20 "
                "backtesting retained 2148 OK executions and one first-draw "
                "CLOSED_INSUFFICIENT_HISTORY result because the evaluator "
                "requires a prior cutoff identity. Candidate-K, one native "
                "ticket, one local configuration, combination count, and "
                "ordered-20 remain distinct. Compact evidence SHA-256 is "
                f"{evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "FROZEN_SINGLE_NATIVE_TICKET_HAS_ZERO_NATIVE_DUPLICATES_"
                "BEFORE_ORDERED_20_DERIVATION"
            ),
            "ticket_order_semantics": (
                "FROZEN_SOURCE_SINGLE_POSITION_BEFORE_ORDERED_20_"
                "CONSTRUCTION"
            ),
            "unranked_reason": "RANKED_BACKTEST_EVIDENCE_AVAILABLE",
        }
    )
    if (
        alias_evidence["canonical_method_id"] != HPSB_METHOD_ID
        or alias_evidence["alias_method_id"] != ENSEMBLE_ALIAS_METHOD_ID
    ):
        raise CatalogOverlayError("wave-57 alias target changed")
    alias_record.update(
        {
            "candidate_k_semantics": (
                "DUPLICATE_ALIAS_INHERITS_CANONICAL_METHOD_SEMANTICS"
            ),
            "combination_count_semantics": (
                "DUPLICATE_ALIAS_INHERITS_CANONICAL_METHOD_SEMANTICS"
            ),
            "duplicate_alias_target": canonical_strategy_id,
            "native_ticket_semantics": (
                "DUPLICATE_ALIAS_NO_INDEPENDENT_NATIVE_PORTFOLIO"
            ),
            "reproduction_status": "DUPLICATE_ALIAS",
            "status_reason": (
                "Frozen-runtime execution of the default public "
                "predict_ensemble entrypoint matched predict_hpsb_v2 "
                "exactly for 2149 of 2149 causal targets. The local "
                "patch_ai_adapter function is not invoked by that "
                "entrypoint or module main; the unsupported "
                "transformer_v3_raw adapter request therefore forces AI "
                "weight to zero and leaves the same HPSB-DMS ticket. An "
                "independent ranking row would double count the canonical "
                "HPSB strategy. Compact evidence SHA-256 is "
                f"{evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "INHERITED_FROM_DUPLICATE_ALIAS_TARGET"
            ),
            "ticket_order_semantics": (
                "INHERITED_FROM_DUPLICATE_ALIAS_TARGET"
            ),
            "unranked_reason": "DUPLICATE_ALIAS",
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
                "SOURCE_NATIVE_WAVE57_HPSB_V2_FULL_PREFIX_CAUSAL_"
                "BACKTEST_AND_ENSEMBLE_EXACT_ALIAS_PROOF"
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
    catalog = apply_wave57_evidence(
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
