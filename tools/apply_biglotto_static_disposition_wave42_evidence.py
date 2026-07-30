#!/usr/bin/env python3
"""Apply wave-42 duplicate aliases to the BIG_LOTTO catalog."""

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
    "2296f709d572f62dd4a77033cd8a5d7e5ac62cc57c7c718d4e20392636998b3a"
)
BASE_CATALOG_FILE_SHA256 = (
    "bc95d77aa4c6b4e68e511f80224111ba7cb685017932256b2367e124ca1699cd"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE42_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V6"
REASON_CODE = "PASS_THROUGH_WRAPPER_WITHOUT_INDEPENDENT_SELECTION_LOGIC"
EXPECTED_EVIDENCE_SHA256 = (
    "1ed8c1145ccf6ae10e82085e8a19fb069888f8cd3a1e66054a0a9844b180d9f1"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_static_disposition_wave42_evidence_v1.json"
)
TARGET_METHOD_ID = "lottery_api/models/advanced_strategies.py"
TARGET_STRATEGY_ID = (
    "legacy_biglotto__advanced_strategies__91c682887cd0"
)
TARGET_SOURCE_SHA256 = (
    "91c682887cd000fac721e85b77c6a3692aeb90a08981bbc39184ee33997666af"
)
ALIAS_SPECS = {
    "tools/final_draw_v11.py": {
        "source_sha256": (
            "9b2b5dcb8a0bca65a108a15ad57e698cbc5522ee580a6ed8384ce59f5885981e"
        ),
        "target_symbol": "anomaly_cluster_v11_predict",
        "target_symbol_ast_sha256": (
            "71ea70e26d813833d44c72b00c7f8eccc2da34d9db9b5b8f5d0d9227cb8c7731"
        ),
    },
    "tools/predict_v9_anomaly_cluster.py": {
        "source_sha256": (
            "e44a6f1f3466b3a332a45a0f3462291a906807105f7f2eaa890d0288dbc417a1"
        ),
        "target_symbol": "anomaly_cluster_predict",
        "target_symbol_ast_sha256": (
            "64e34a215f9e0fa0cdd2a8e3c8dc16f378697f2a37214e9b77f2c908a7e7a857"
        ),
    },
}
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 80,
    "CLOSED_UNEXECUTABLE": 64,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 72,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 80,
    "CLOSED_UNEXECUTABLE": 64,
    "DUPLICATE_ALIAS": 7,
    "OWNER_DECISION_REQUIRED": 70,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-42 evidence is inconsistent."""


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
) -> dict[str, dict[str, Any]]:
    target_raw = evidence.get("target_source")
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
        or not isinstance(target_raw, dict)
    ):
        raise CatalogOverlayError("wave-42 evidence identity changed")
    target = cast(dict[str, Any], target_raw)
    if (
        target.get("legacy_method_id") != TARGET_METHOD_ID
        or target.get("strategy_id") != TARGET_STRATEGY_ID
        or target.get("source_sha256") != TARGET_SOURCE_SHA256
    ):
        raise CatalogOverlayError("wave-42 alias target changed")
    rows = cast(list[object], evidence.get("duplicate_aliases", []))
    if len(rows) != 2:
        raise CatalogOverlayError(
            "wave-42 evidence must contain two aliases"
        )
    aliases: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-42 alias must be an object"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("alias_legacy_method_id")
        if not isinstance(method_id, str):
            raise CatalogOverlayError("wave-42 alias identity changed")
        spec = ALIAS_SPECS.get(method_id)
        facts = cast(
            list[object],
            row.get("decisive_source_facts", []),
        )
        if (
            spec is None
            or method_id in aliases
            or row.get("reproduction_status") != "DUPLICATE_ALIAS"
            or row.get("reason_code") != REASON_CODE
            or row.get("target_legacy_method_id")
            != TARGET_METHOD_ID
            or row.get("target_strategy_id") != TARGET_STRATEGY_ID
            or row.get("alias_source_sha256")
            != spec["source_sha256"]
            or row.get("target_symbol") != spec["target_symbol"]
            or row.get("target_symbol_ast_sha256")
            != spec["target_symbol_ast_sha256"]
            or len(facts) != 3
            or any(not isinstance(fact, str) for fact in facts)
        ):
            raise CatalogOverlayError("wave-42 alias identity changed")
        aliases[method_id] = row
    if set(aliases) != set(ALIAS_SPECS):
        raise CatalogOverlayError("wave-42 evidence omits an alias")
    return aliases


def apply_wave42_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay both validated wave-42 duplicate aliases."""

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
        raise CatalogOverlayError("wave-42 evidence file changed")
    aliases = _validate_evidence(evidence)

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
    target = by_method.get(TARGET_METHOD_ID)
    if (
        target is None
        or target.get("strategy_id") != TARGET_STRATEGY_ID
        or target.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or target.get("source_sha256") != TARGET_SOURCE_SHA256
    ):
        raise CatalogOverlayError("wave-42 alias target changed")

    for method_id, evidence_row in aliases.items():
        record = by_method.get(method_id)
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256")
            != evidence_row.get("alias_source_sha256")
            or record.get("source_blob_id")
            != evidence_row.get("alias_source_blob_id")
            or record.get("source_byte_size")
            != evidence_row.get("alias_source_byte_size")
        ):
            raise CatalogOverlayError(
                "wave-42 alias leaves the validated universe"
            )
        symbol = cast(str, evidence_row["target_symbol"])
        record.update(
            {
                "candidate_k_semantics": (
                    "DUPLICATE_ALIAS_INHERITS_CANONICAL_METHOD_SEMANTICS"
                ),
                "combination_count_semantics": (
                    "DUPLICATE_ALIAS_INHERITS_CANONICAL_METHOD_SEMANTICS"
                ),
                "duplicate_alias_target": TARGET_STRATEGY_ID,
                "native_ticket_semantics": (
                    "DUPLICATE_ALIAS_NO_INDEPENDENT_NATIVE_PORTFOLIO"
                ),
                "reproduction_status": "DUPLICATE_ALIAS",
                "status_reason": (
                    "Frozen AST review proves this wrapper obtains its "
                    f"BIG_LOTTO tickets from AdvancedStrategies.{symbol} "
                    "and only formats the returned portfolio. An "
                    "independent ranking row would double count the "
                    "canonical source method. Frozen-source wave-42 "
                    f"evidence SHA-256 is {evidence_sha256}."
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
                "STATIC_DISPOSITION_WAVE42_ADVANCED_STRATEGIES_"
                "PASS_THROUGH_ALIAS_REVIEW"
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
    catalog = apply_wave42_evidence(
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
