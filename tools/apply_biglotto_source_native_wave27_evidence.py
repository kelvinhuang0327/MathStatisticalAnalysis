#!/usr/bin/env python3
"""Apply wave-27 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave27 import (
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE27_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE27_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "97b459b3835353c9a3f9cea24183c488a7c50f3a4168c62f8574f8a0484650bd"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE27_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "848f5dcba142c1e98163e2194191e4bcaf872f51577eec266240843323c17675"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_source_native_wave27_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 63,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 115,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 67,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 111,
}
EXPECTED_OK_COUNTS = {
    "lottery_api/models/biglotto_2bet_optimizer.py": 2148,
    "lottery_api/models/biglotto_2bet_optimizer_v2.py": 2148,
    "tools/verify_gemini_2bet_claim.py": 2099,
    "tools/verify_gemini_3bet_claim.py": 2088,
}
EXPECTED_CLOSED_COUNTS = {
    method_id: 2149 - ok_count
    for method_id, ok_count in EXPECTED_OK_COUNTS.items()
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-27 evidence is inconsistent."""


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
) -> dict[str, dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256")
        != "e78e21b102ac9eee286e26799e7679db9cd55b19b56c9218b7ed0566443486a3"
    ):
        raise CatalogOverlayError("wave-27 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    if len(rows) != 4:
        raise CatalogOverlayError(
            "wave-27 evidence must contain four strategies"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-27 strategy evidence is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if not isinstance(method_id, str):
            raise CatalogOverlayError(
                "wave-27 strategy method is invalid"
            )
        by_method[method_id] = row
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS:
        row = by_method.get(method_id)
        if (
            row is None
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE27_METHOD[
                method_id
            ]
            or row.get("native_ticket_count")
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD[
                method_id
            ]
            or row.get("source_method_combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD[
                method_id
            ]
            or row.get("closed_execution_count")
            != EXPECTED_CLOSED_COUNTS[method_id]
            or row.get("ok_execution_count")
            != EXPECTED_OK_COUNTS[method_id]
            or not isinstance(row.get("candidate_k_distribution"), dict)
            or not isinstance(
                row.get("native_duplicate_ticket_count_distribution"),
                dict,
            )
            or not isinstance(
                row.get("closed_reason_code_distribution"),
                dict,
            )
        ):
            raise CatalogOverlayError(
                "wave-27 strategy identity changed"
            )
    parity = cast(dict[str, Any], evidence.get("parity", {}))
    if (
        parity.get("case_count") != 292
        or parity.get("closed_parity_case_count") != 109
        or parity.get("status") != "PASS"
        or not isinstance(parity.get("source_artifacts"), list)
        or not isinstance(parity.get("support_artifacts"), list)
    ):
        raise CatalogOverlayError("wave-27 parity evidence changed")
    return by_method


def apply_wave27_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay four validated BACKTESTED dispositions."""

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
        raise CatalogOverlayError("wave-27 evidence file changed")
    evidence_by_method = _validate_evidence(evidence)

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

    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS:
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
                "wave-27 evidence leaves the validated universe"
            )
        ok_count = EXPECTED_OK_COUNTS[method_id]
        closed_count = EXPECTED_CLOSED_COUNTS[method_id]
        closed_reasons = cast(
            dict[str, int],
            evidence_row["closed_reason_code_distribution"],
        )
        record.update(
            {
                "candidate_k_semantics": (
                    "EXECUTION_SPECIFIC_FROZEN_RANKED_CANDIDATE_POOL_"
                    "LENGTH_DISTINCT_FROM_NATIVE_TICKET_COUNT"
                ),
                "combination_count_semantics": (
                    "FROZEN_SOURCE_PREDICTOR_COMPONENT_COUNT_DISTINCT_"
                    "FROM_CANDIDATE_K_NATIVE_TICKETS_AND_ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE27_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Frozen high-level AST parity covered 292 cases "
                    "including 109 matching closed-result cases, "
                    "preserving weighted Counter insertion ties, source "
                    "slice positions, verifier minimum-history guards, "
                    "native ticket order, and candidate-pool closures. "
                    f"{ok_count} causal executions completed and "
                    f"{closed_count} source closures remained explicit "
                    f"as {dict(sorted(closed_reasons.items()))}. Compact "
                    f"evidence SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_ALL_FROZEN_POSITIONAL_TICKETS_INCLUDING_"
                    "ANY_SOURCE_DUPLICATES"
                ),
                "ticket_order_semantics": (
                    "FROZEN_SOURCE_ENTRYPOINT_POSITIONAL_ORDER_BEFORE_"
                    "ORDERED_20_CONSTRUCTION"
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
                "SOURCE_NATIVE_WAVE27_WEIGHTED_TWO_AND_THREE_BET_"
                "CAUSAL_BACKTEST"
            ),
        }
    )
    status_counts = Counter(
        cast(str, cast(dict[str, Any], record)["reproduction_status"])
        for record in records
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
    catalog = apply_wave27_evidence(
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
