#!/usr/bin/env python3
"""Apply wave-18 closures and duplicate alias to the BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "6c86158c8ba85234896e2a7ae05f05b083a5cd9716b53d9c130fb95d07c7e336"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE18_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V5"
EXPECTED_EVIDENCE_SHA256 = (
    "818a6874a0c846e2268443283b633a41dafd544c1a1a917d140c2cbfbcb22f4d"
)
CLOSED_REASON_CODE = (
    "COMPARATIVE_IMPORTED_PREDICTOR_AUDIT_WITHOUT_"
    "INDEPENDENT_TARGET_PORTFOLIO"
)
ALIAS_REASON_CODE = (
    "FROZEN_SELECTION_FUNCTION_AST_IDENTICAL_IGNORING_DOCSTRING"
)
ALIAS_BODY_SHA256 = (
    "97ba09dbea86ef96dbc69164ac1cec90170effb71e5bfb549bdd7d3b64a60611"
)
ALIAS_METHOD_ID = "tools/verify_randomness_impact.py"
ALIAS_TARGET_METHOD_ID = "tools/verify_gemini_3bet_claim.py"
ALIAS_TARGET_STRATEGY_ID = (
    "legacy_biglotto__verify_gemini_3bet_claim__05734b9e2afe"
)
CLOSED_METHODS = {
    "tools/audit_raw_experts.py": (
        "771e17bc998ad369432fb42a36793d4e9669485ee8e331b30a0fb0a654974836"
    ),
    "tools/experimental/compare_models.py": (
        "adce89cc4bbcc8654794ab847e0b6f44085b629e7a77a4fe8543081c343f0906"
    ),
}
ALIAS_SOURCE_SHA256 = {
    ALIAS_METHOD_ID: (
        "95c4b24121a543d86a28f804ac12ed81b7371f26ab7eaecf07b7896d4644593f"
    ),
    ALIAS_TARGET_METHOD_ID: (
        "05734b9e2afee57e9bfc3047a4cb3a79c9e4177c7bff38a13ed5a78c732fb978"
    ),
}
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 43,
    "CLOSED_UNEXECUTABLE": 30,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 144,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 43,
    "CLOSED_UNEXECUTABLE": 32,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 141,
}
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class CatalogOverlayError(ValueError):
    """The catalog or wave-18 disposition evidence is inconsistent."""


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


def _validate_digest(value: object, context: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CatalogOverlayError(
            f"{context} must be a lowercase SHA-256"
        )


def _validate_evidence(
    evidence: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or evidence.get("review_policy_version")
        != REVIEW_POLICY_VERSION
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
    ):
        raise CatalogOverlayError("wave-18 evidence identity changed")
    rows_raw = evidence.get("dispositions")
    if (
        not isinstance(rows_raw, list)
        or len(cast(list[object], rows_raw)) != 2
    ):
        raise CatalogOverlayError(
            "wave-18 evidence must contain two dispositions"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], rows_raw):
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-18 disposition must be an object"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        facts_raw = row.get("decisive_source_facts")
        if (
            type(method_id) is not str
            or method_id in by_method
            or method_id not in CLOSED_METHODS
            or row.get("reproduction_status")
            != "CLOSED_UNEXECUTABLE"
            or row.get("reason_code") != CLOSED_REASON_CODE
            or row.get("source_sha256") != CLOSED_METHODS[method_id]
            or type(row.get("source_blob_id")) is not str
            or len(cast(str, row["source_blob_id"])) != 40
            or type(row.get("source_byte_size")) is not int
            or cast(int, row["source_byte_size"]) <= 0
            or type(row.get("status_reason")) is not str
            or not isinstance(facts_raw, list)
            or len(cast(list[object], facts_raw)) < 3
        ):
            raise CatalogOverlayError(
                "wave-18 disposition identity changed"
            )
        _validate_digest(
            row.get("source_sha256"),
            f"{method_id} source",
        )
        by_method[method_id] = row
    if set(by_method) != set(CLOSED_METHODS):
        raise CatalogOverlayError("wave-18 evidence omits a closure")

    aliases_raw = evidence.get("duplicate_aliases")
    if (
        not isinstance(aliases_raw, list)
        or len(cast(list[object], aliases_raw)) != 1
    ):
        raise CatalogOverlayError(
            "wave-18 evidence must contain one duplicate alias"
        )
    alias_raw = cast(list[object], aliases_raw)[0]
    if not isinstance(alias_raw, dict):
        raise CatalogOverlayError("wave-18 alias must be an object")
    alias = cast(dict[str, Any], alias_raw)
    alias_source_raw = alias.get("alias_source")
    target_source_raw = alias.get("target_source")
    if (
        alias.get("alias_legacy_method_id") != ALIAS_METHOD_ID
        or alias.get("target_legacy_method_id")
        != ALIAS_TARGET_METHOD_ID
        or alias.get("target_strategy_id") != ALIAS_TARGET_STRATEGY_ID
        or alias.get("reproduction_status") != "DUPLICATE_ALIAS"
        or alias.get("reason_code") != ALIAS_REASON_CODE
        or alias.get("selection_function_body_sha256")
        != ALIAS_BODY_SHA256
        or not isinstance(alias_source_raw, dict)
        or not isinstance(target_source_raw, dict)
    ):
        raise CatalogOverlayError("wave-18 alias identity changed")
    alias_source = cast(dict[str, Any], alias_source_raw)
    target_source = cast(dict[str, Any], target_source_raw)
    for method_id, source_raw in (
        (ALIAS_METHOD_ID, alias_source),
        (ALIAS_TARGET_METHOD_ID, target_source),
    ):
        source = source_raw
        if (
            source.get("source_sha256")
            != ALIAS_SOURCE_SHA256[method_id]
            or source.get("selection_function_body_sha256")
            != ALIAS_BODY_SHA256
            or type(source.get("source_blob_id")) is not str
            or len(cast(str, source["source_blob_id"])) != 40
            or type(source.get("source_byte_size")) is not int
            or cast(int, source["source_byte_size"]) <= 0
        ):
            raise CatalogOverlayError(
                "wave-18 alias source identity changed"
            )
    return by_method, alias


def apply_wave18_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
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
        raise CatalogOverlayError("wave-18 evidence file changed")
    dispositions, alias = _validate_evidence(evidence)

    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise CatalogOverlayError("base catalog records changed")
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], records_raw):
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
                "wave-18 closure leaves the validated universe"
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
                    "NO_INDEPENDENT_EXECUTABLE_TARGET_DRAW_PORTFOLIO"
                ),
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "status_reason": (
                    f"{evidence_row['status_reason']} Frozen-source "
                    "wave-18 disposition evidence SHA-256 is "
                    f"{evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "ticket_order_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "unranked_reason": (
                    f"CLOSED_UNEXECUTABLE:{CLOSED_REASON_CODE}"
                ),
            }
        )

    alias_record = record_by_method.get(ALIAS_METHOD_ID)
    target_record = record_by_method.get(ALIAS_TARGET_METHOD_ID)
    alias_source = cast(dict[str, Any], alias["alias_source"])
    target_source = cast(dict[str, Any], alias["target_source"])
    if (
        alias_record is None
        or target_record is None
        or alias_record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or target_record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or alias_record.get("strategy_id") == ALIAS_TARGET_STRATEGY_ID
        or target_record.get("strategy_id") != ALIAS_TARGET_STRATEGY_ID
        or alias_record.get("source_sha256")
        != alias_source.get("source_sha256")
        or alias_record.get("source_blob_id")
        != alias_source.get("source_blob_id")
        or target_record.get("source_sha256")
        != target_source.get("source_sha256")
        or target_record.get("source_blob_id")
        != target_source.get("source_blob_id")
    ):
        raise CatalogOverlayError(
            "wave-18 alias leaves the validated universe"
        )
    alias_record.update(
        {
            "candidate_k_semantics": (
                "DUPLICATE_ALIAS_INHERITS_CANONICAL_METHOD_SEMANTICS"
            ),
            "combination_count_semantics": (
                "DUPLICATE_ALIAS_INHERITS_CANONICAL_METHOD_SEMANTICS"
            ),
            "duplicate_alias_target": ALIAS_TARGET_STRATEGY_ID,
            "native_ticket_semantics": (
                "DUPLICATE_ALIAS_NO_INDEPENDENT_NATIVE_PORTFOLIO"
            ),
            "reproduction_status": "DUPLICATE_ALIAS",
            "status_reason": (
                f"{alias['status_reason']} Frozen-source wave-18 "
                f"disposition evidence SHA-256 is {evidence_sha256}."
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

    artifacts_raw = catalog.get("source_artifacts")
    if not isinstance(artifacts_raw, list):
        raise CatalogOverlayError("base source artifacts changed")
    cast(list[object], artifacts_raw).append(
        {
            "artifact_name": evidence_path.name,
            "artifact_sha256": evidence_sha256,
            "evidence_role": (
                "STATIC_DISPOSITION_WAVE18_IMPORTED_PREDICTOR_AUDIT_"
                "AND_FUNCTION_AST_ALIAS_REVIEW"
            ),
        }
    )
    catalog["status_counts"] = EXPECTED_OUTPUT_STATUS_COUNTS
    catalog["catalog_sha256"] = _catalog_hash(catalog)
    return cast(dict[str, object], catalog)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = apply_wave18_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(catalog) + b"\n")


if __name__ == "__main__":
    main()
