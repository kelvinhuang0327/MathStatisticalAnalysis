#!/usr/bin/env python3
"""Apply wave-56 direct/transitive stochastic closures."""

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
    "1103e1ec10b1af374ef48c649dd32a3e9b72fb46f38d39c2921aaedd179bbf81"
)
BASE_CATALOG_FILE_SHA256 = (
    "f89e763a8d25a094ac2f0876b38cd37bd6e50a384306d985afd709ff43c95f71"
)
EXPECTED_EVIDENCE_SHA256 = (
    "c9a9d9420e29e718ceec5bfe309869ed9a6b3f3e76c78c1b04d381e85089edbf"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE56_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V12"
REASON_CODE = (
    "UNBOUND_DIRECT_OR_TRANSITIVE_STOCHASTIC_NATIVE_SELECTION_WITHOUT_"
    "FROZEN_PRESTATE"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_static_disposition_wave56_evidence_v1.json"
)
CLOSED_METHODS = {
    "lottery_api/models/advanced_strategies.py": (
        "91c682887cd000fac721e85b77c6a3692aeb90a08981bbc39184ee33997666af"
    ),
    "lottery_api/models/big_lotto_dual_bet_optimizer.py": (
        "4f4e30404e4380c5d25439e2f02605de5cbbd1f9a0ead21822c5aa676062e0c5"
    ),
    "lottery_api/models/selective_ensemble.py": (
        "423bd30a0a94b5c14599f490a5f882116c4e88d3fbe9afa53a8d63c58b751bf2"
    ),
    "lottery_api/models/unified_predictor.py": (
        "32d0112c95ce33306002b2f4e13e2c768ff7612c0eb8750cd453cba73575e004"
    ),
    "tools/auto_optimizer_v2.py": (
        "d3238f515f54b6422a4851cbb9f867bc1536abde55acb4aaa69712fc7a6a508a"
    ),
    "tools/backtest/big_lotto_2025_tournament.py": (
        "bd7616eaae0945290e6e686c449a0637d6e04ec1ec0e972e2f96e763c9733dfd"
    ),
    "tools/predict_114000118.py": (
        "42c5b74e1ea7957ebaeb5151b89e15531694b2189e1ccf6477d19a8a4ff144ba"
    ),
    "tools/verify_cluster_size.py": (
        "fdb1cdbd08b6d548f7615ce4df992b992c8a00a5c103f8cecf9d0f37add8ff0d"
    ),
}
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 123,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 22,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 123,
    "CLOSED_UNEXECUTABLE": 73,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 14,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-56 evidence is inconsistent."""


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
        raise CatalogOverlayError("wave-56 evidence identity changed")
    rows_raw = evidence.get("dispositions")
    if not isinstance(rows_raw, list):
        raise CatalogOverlayError(
            "wave-56 evidence dispositions must be a list"
        )
    rows = cast(list[object], rows_raw)
    if len(rows) != len(CLOSED_METHODS):
        raise CatalogOverlayError(
            "wave-56 evidence disposition count changed"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-56 disposition must be an object"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if type(method_id) is not str or method_id not in CLOSED_METHODS:
            raise CatalogOverlayError(
                "wave-56 disposition method changed"
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
                "wave-56 disposition identity changed"
            )
        by_method[method_id] = row
    if set(by_method) != set(CLOSED_METHODS):
        raise CatalogOverlayError("wave-56 evidence omits a closure")
    return by_method


def apply_wave56_evidence(
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
        raise CatalogOverlayError("wave-56 evidence file changed")
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
                "wave-56 closure leaves the validated universe"
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
                    "wave-56 disposition evidence SHA-256 is "
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
                "STATIC_DISPOSITION_WAVE56_DIRECT_AND_TRANSITIVE_"
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
    catalog = apply_wave56_evidence(
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
