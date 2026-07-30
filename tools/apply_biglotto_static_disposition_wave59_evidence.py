#!/usr/bin/env python3
"""Apply wave-59 no-target-portfolio closure evidence."""

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
    "4d4211355dc84791616a6f68f29dce3bbd293fa829426d8ed519618eb0fbf369"
)
BASE_CATALOG_FILE_SHA256 = (
    "33c4a9f1be363fab2e566b3931c58a2990ee52abf4199f0b8d4fe5076d020199"
)
EXPECTED_EVIDENCE_SHA256 = (
    "c57853e4d6a0daad65ed9852072ac3037210715f5ce2fc5786baa57b821e084e"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE59_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V13"
REASON_CODE = (
    "OUTCOME_RANKING_SEARCH_HAS_NO_SOURCE_DEFINED_TARGET_PORTFOLIO_"
    "APPLICATION"
)
METHOD_ID = "ai_lab/scripts/automl_strategy_optimizer.py"
SOURCE_SHA256 = (
    "ad4b69c62db34be8d545987f1268c77b9401f132dee9c2852fc849bd03882d90"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_static_disposition_wave59_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 126,
    "CLOSED_UNEXECUTABLE": 73,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 10,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 126,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 9,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-59 evidence is inconsistent."""


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


def _validate_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    rows = cast(list[object], evidence.get("dispositions", []))
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
        or len(rows) != 1
        or not isinstance(rows[0], dict)
    ):
        raise CatalogOverlayError("wave-59 evidence identity changed")
    row = cast(dict[str, Any], rows[0])
    facts = cast(list[object], row.get("decisive_source_facts", []))
    if (
        row.get("legacy_method_id") != METHOD_ID
        or row.get("reproduction_status") != "CLOSED_UNEXECUTABLE"
        or row.get("reason_code") != REASON_CODE
        or row.get("source_sha256") != SOURCE_SHA256
        or type(row.get("source_blob_id")) is not str
        or type(row.get("source_byte_size")) is not int
        or len(facts) != 3
        or type(row.get("status_reason")) is not str
    ):
        raise CatalogOverlayError("wave-59 disposition changed")
    return row


def apply_wave59_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Close the frozen retrospective search without inventing tickets."""

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
        raise CatalogOverlayError("wave-59 evidence file changed")
    disposition = _validate_evidence(evidence)

    records = cast(list[object], catalog.get("records", []))
    record: dict[str, Any] | None = None
    for candidate in records:
        if not isinstance(candidate, dict):
            continue
        typed_candidate = cast(dict[str, Any], candidate)
        if typed_candidate.get("legacy_method_id") == METHOD_ID:
            record = typed_candidate
            break
    if (
        record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or record.get("source_sha256")
        != disposition.get("source_sha256")
        or record.get("source_blob_id")
        != disposition.get("source_blob_id")
        or record.get("source_byte_size")
        != disposition.get("source_byte_size")
    ):
        raise CatalogOverlayError(
            "wave-59 closure leaves the validated universe"
        )
    record.update(
        {
            "candidate_k_semantics": (
                "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
            ),
            "combination_count_semantics": (
                "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
            ),
            "native_ticket_semantics": (
                "NO_SOURCE_DEFINED_TARGET_PORTFOLIO_AFTER_"
                "RETROSPECTIVE_CONFIGURATION_RANKING"
            ),
            "reproduction_status": "CLOSED_UNEXECUTABLE",
            "status_reason": (
                f"{disposition['status_reason']} Frozen-source wave-59 "
                f"disposition evidence SHA-256 is {evidence_sha256}."
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
                "STATIC_DISPOSITION_WAVE59_RETROSPECTIVE_SEARCH_NO_"
                "TARGET_PORTFOLIO_APPLICATION_REVIEW"
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
    catalog = apply_wave59_evidence(
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
