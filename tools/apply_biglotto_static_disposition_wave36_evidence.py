#!/usr/bin/env python3
"""Apply wave-36 unbound neural-training closures to the catalog."""

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
    "fca99742869404dd397cdb6cdc2b0755db2d7ff591002e2b30004c7a9e57fab9"
)
BASE_CATALOG_FILE_SHA256 = (
    "d2d15de8a6ee168def33636c9d6a724bc780b4218f24866be7e6ab8f4473a846"
)
EXPECTED_EVIDENCE_SHA256 = (
    "7e88c5242c7f738afaed6c48b7bc74d08b4c7472ac87e8334e7eac66aa14ce7e"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE36_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V8"
REASON_CODE = (
    "UNBOUND_NEURAL_TRAINING_RANDOMNESS_WITHOUT_FROZEN_PRESTATE"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_static_disposition_wave36_evidence_v1.json"
)
CLOSED_METHODS = {
    "lottery_api/models/lstm_attention_predictor.py": (
        "99fa7814c95d7cf0c4c73cf43ad2aaedbc13b024ac77d5d1ead331a84649872c"
    ),
    "lottery_api/models/perball_lstm.py": (
        "cfe6216f73d308963afabedc282d0c2f74c779e3e1220c746090e205280056d8"
    ),
}
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 40,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 98,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 42,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 96,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-36 evidence is inconsistent."""


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
    return cast(dict[str, Any], document), hashlib.sha256(raw).hexdigest()


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
        or evidence.get("review_policy_version")
        != REVIEW_POLICY_VERSION
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
        or evidence.get("base_catalog_file_sha256")
        != BASE_CATALOG_FILE_SHA256
    ):
        raise CatalogOverlayError("wave-36 evidence identity changed")
    rows_raw = evidence.get("dispositions")
    if not isinstance(rows_raw, list):
        raise CatalogOverlayError(
            "wave-36 evidence dispositions must be a list"
        )
    rows = cast(list[object], rows_raw)
    if len(rows) != 2:
        raise CatalogOverlayError(
            "wave-36 evidence must contain two dispositions"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-36 disposition must be an object"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if type(method_id) is not str or method_id not in CLOSED_METHODS:
            raise CatalogOverlayError(
                "wave-36 disposition method changed"
            )
        facts_raw = row.get("decisive_source_facts")
        facts = (
            cast(list[object], facts_raw)
            if isinstance(facts_raw, list)
            else []
        )
        if (
            method_id in by_method
            or row.get("reproduction_status")
            != "CLOSED_UNEXECUTABLE"
            or row.get("reason_code") != REASON_CODE
            or row.get("source_sha256") != CLOSED_METHODS[method_id]
            or type(row.get("source_blob_id")) is not str
            or type(row.get("source_byte_size")) is not int
            or len(facts) != 3
            or type(row.get("status_reason")) is not str
        ):
            raise CatalogOverlayError(
                "wave-36 disposition identity changed"
            )
        by_method[method_id] = row
    if set(by_method) != set(CLOSED_METHODS):
        raise CatalogOverlayError("wave-36 evidence omits a closure")
    return by_method


def apply_wave36_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
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
        raise CatalogOverlayError("wave-36 evidence file changed")
    dispositions = _validate_evidence(evidence)

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

    for method_id, evidence_row in dispositions.items():
        record = record_by_method.get(method_id)
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
                "wave-36 closure leaves the validated universe"
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
                    "NO_REPRODUCIBLE_FROZEN_NATIVE_TICKETS_BECAUSE_"
                    "NEURAL_TRAINING_RANDOM_STATE_WAS_NOT_BOUND_OR_"
                    "SERIALIZED"
                ),
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "status_reason": (
                    f"{evidence_row['status_reason']} Frozen-source "
                    "wave-36 disposition evidence SHA-256 is "
                    f"{evidence_sha256}."
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
                "STATIC_DISPOSITION_WAVE36_UNBOUND_NEURAL_TRAINING_"
                "RANDOMNESS_REVIEW"
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
    catalog = apply_wave36_evidence(
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
