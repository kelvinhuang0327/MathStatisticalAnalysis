#!/usr/bin/env python3
"""Apply wave-39 direct/transitive stochastic closures."""

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
    "660d35418eedb2c7daab0911fd4ade3aa33cd0ccbf479c78ac2a0366afa212a9"
)
BASE_CATALOG_FILE_SHA256 = (
    "0cde129c724bdf0048ad295a198c902d2e1f6e668321becbc998ab18b86c7cfa"
)
EXPECTED_EVIDENCE_SHA256 = (
    "b508a1e9a6f3096be48fe181d5e3cb4253cfb07d1d4889de3db1ca8c9adab974"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE39_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V11"
REASON_CODE = (
    "UNBOUND_OR_TRANSITIVE_STOCHASTIC_NATIVE_SELECTION_WITHOUT_"
    "FROZEN_PRESTATE"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_static_disposition_wave39_evidence_v1.json"
)
CLOSED_METHODS = {
    "lottery_api/models/auto_optimizer.py": (
        "7328cf15d87447754c22db959a0a3bd7d5acd458ea29c865043b01575f58d636"
    ),
    "lottery_api/models/meta_learning.py": (
        "93da5e6fe3354a0242023054397cb39d07f3e87a031dda18efd82bdf27a25c1f"
    ),
    "lottery_api/models/optimized_predictor.py": (
        "ea587dc9d257b2b7d295d5e7e345db2760ffb251da276fcadfa928fa4ca890df"
    ),
    "lottery_api/models/ultra_optimized_predictor.py": (
        "67e02f62b826d3dc40ae77369a143f66ec9d1e884d42e68586e6e8ebd60eac63"
    ),
    "tools/backtest_phase1_comparison.py": (
        "c9400489aee3671f5428423621ffe1a8b4b571a9c5e0da217ebf328f4e4a3db3"
    ),
    "tools/find_best_test_periods.py": (
        "f3174bd643473fb45c2a4b154ed4fefdeec83bfe1efa35555879cd31adc825b8"
    ),
    "tools/generate_final_predictions.py": (
        "5add2d975c50bea9c8fe63162b703ee84ba9b06697a261b423ae8b5dfc5808fc"
    ),
    "tools/generate_v7_predictions.py": (
        "e941ef56d900a8accf32b0e9d329cc6612dc6aaf435a0155c486ccaeede7a53d"
    ),
    "tools/predict_big_lotto_115000003.py": (
        "794d6ebebe47743d1dfe5236c4760a383f3078d74c3a55e3648979f1f0e07cef"
    ),
    "tools/predict_biglotto_7bets_optimized.py": (
        "eda0e6bd148adae77c8592f59a99e05698dcd9acc521973c2deb20d3d3a79a83"
    ),
}
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 54,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 84,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 64,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 74,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-39 evidence is inconsistent."""


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
        raise CatalogOverlayError("wave-39 evidence identity changed")
    rows_raw = evidence.get("dispositions")
    if not isinstance(rows_raw, list):
        raise CatalogOverlayError(
            "wave-39 evidence dispositions must be a list"
        )
    rows = cast(list[object], rows_raw)
    if len(rows) != len(CLOSED_METHODS):
        raise CatalogOverlayError(
            "wave-39 evidence disposition count changed"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-39 disposition must be an object"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if type(method_id) is not str or method_id not in CLOSED_METHODS:
            raise CatalogOverlayError(
                "wave-39 disposition method changed"
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
                "wave-39 disposition identity changed"
            )
        by_method[method_id] = row
    if set(by_method) != set(CLOSED_METHODS):
        raise CatalogOverlayError("wave-39 evidence omits a closure")
    return by_method


def apply_wave39_evidence(
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
        raise CatalogOverlayError("wave-39 evidence file changed")
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
                "wave-39 closure leaves the validated universe"
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
                    "DIRECT_OR_TRANSITIVE_STOCHASTIC_PRESTATE_WAS_NOT_"
                    "BOUND_OR_SERIALIZED"
                ),
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "status_reason": (
                    f"{evidence_row['status_reason']} Frozen-source "
                    "wave-39 disposition evidence SHA-256 is "
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
                "STATIC_DISPOSITION_WAVE39_DIRECT_AND_TRANSITIVE_"
                "STOCHASTIC_NATIVE_SELECTION_REVIEW"
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
    catalog = apply_wave39_evidence(
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
