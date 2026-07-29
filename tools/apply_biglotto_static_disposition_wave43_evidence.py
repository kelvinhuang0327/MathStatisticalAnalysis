#!/usr/bin/env python3
"""Apply wave-43 candidate-only closure to the BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "792ed501402cf371412515e7364a566bb1e8635fbc8eee74a1c2baf4aca8c468"
)
BASE_CATALOG_FILE_SHA256 = (
    "41c9f7b2d711b1c9f7105d204575d053a40799dee0d31a2e7bfc94809ce8898f"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE43_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V7"
REASON_CODE = (
    "VARIABLE_LENGTH_CANDIDATE_RECOMMENDATIONS_WITHOUT_"
    "SOURCE_DEFINED_LEGAL_TICKET"
)
METHOD_ID = "lottery_api/models/advanced_bayesian_analyzer.py"
SOURCE_SHA256 = (
    "8ad90229f37ae952679a66b8f6e3f43202b80210e3308eb1cdeecb7595f593fc"
)
EXPECTED_EVIDENCE_SHA256 = (
    "7982e99da15ef4518d029b01a4ad3675dca6255d8a659186e564bcc630dce465"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_static_disposition_wave43_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 80,
    "CLOSED_UNEXECUTABLE": 64,
    "DUPLICATE_ALIAS": 7,
    "OWNER_DECISION_REQUIRED": 70,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 80,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 7,
    "OWNER_DECISION_REQUIRED": 69,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-43 evidence is inconsistent."""


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
        or evidence.get("review_policy_version")
        != REVIEW_POLICY_VERSION
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
        or evidence.get("base_catalog_file_sha256")
        != BASE_CATALOG_FILE_SHA256
    ):
        raise CatalogOverlayError("wave-43 evidence identity changed")
    rows = cast(list[object], evidence.get("dispositions", []))
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise CatalogOverlayError(
            "wave-43 evidence must contain one disposition"
        )
    row = cast(dict[str, Any], rows[0])
    facts = cast(list[object], row.get("decisive_source_facts", []))
    method_hashes = row.get("method_ast_sha256")
    if (
        row.get("legacy_method_id") != METHOD_ID
        or row.get("source_sha256") != SOURCE_SHA256
        or row.get("source_blob_id")
        != "cd71d74f5cb450e648803cc7a7c607391bfa3c34"
        or row.get("source_byte_size") != 14269
        or row.get("reproduction_status")
        != "CLOSED_UNEXECUTABLE"
        or row.get("reason_code") != REASON_CODE
        or row.get("candidate_k_semantics")
        != "UP_TO_TEN_HOT_OR_COLD_RECOMMENDATION_CANDIDATES"
        or len(facts) != 4
        or any(not isinstance(fact, str) for fact in facts)
        or not isinstance(method_hashes, dict)
        or set(cast(dict[object, object], method_hashes))
        != {
            "analyze_number_bias",
            "analyze_odd_even_bias",
            "detect_state_regime",
            "recommend_strategy",
        }
    ):
        raise CatalogOverlayError(
            "wave-43 disposition identity changed"
        )
    return row


def apply_wave43_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay the validated wave-43 CLOSED disposition."""

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
        raise CatalogOverlayError("wave-43 evidence file changed")
    evidence_row = _validate_evidence(evidence)

    records = cast(list[object], catalog.get("records", []))
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in records:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "base catalog record is invalid"
            )
        record = cast(dict[str, Any], candidate)
        method_id = record.get("legacy_method_id")
        if isinstance(method_id, str):
            by_method[method_id] = record
    if len(by_method) != 221:
        raise CatalogOverlayError("base catalog records changed")
    record = by_method.get(METHOD_ID)
    if (
        record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or record.get("source_sha256")
        != evidence_row.get("source_sha256")
        or record.get("source_blob_id")
        != evidence_row.get("source_blob_id")
        or record.get("source_byte_size")
        != evidence_row.get("source_byte_size")
    ):
        raise CatalogOverlayError(
            "wave-43 closure leaves the validated universe"
        )
    record.update(
        {
            "candidate_k_semantics": (
                "UP_TO_TEN_HOT_OR_COLD_RECOMMENDATION_CANDIDATES_"
                "NOT_A_NATIVE_TICKET"
            ),
            "combination_count_semantics": (
                "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
            ),
            "native_ticket_semantics": (
                "NO_SOURCE_DEFINED_LEGAL_SIX_NUMBER_TICKET"
            ),
            "reproduction_status": "CLOSED_UNEXECUTABLE",
            "status_reason": (
                f"{evidence_row['status_reason']} Taking the first six "
                "would invent a new method and conflate Candidate-K with "
                "ticket count. Frozen-source wave-43 disposition evidence "
                f"SHA-256 is {evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
            ),
            "ticket_order_semantics": (
                "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
            ),
            "unranked_reason": (
                f"CLOSED_UNEXECUTABLE:{REASON_CODE}"
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
                "STATIC_DISPOSITION_WAVE43_CANDIDATE_ONLY_"
                "NO_LEGAL_TICKET_REVIEW"
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
    catalog = apply_wave43_evidence(
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
