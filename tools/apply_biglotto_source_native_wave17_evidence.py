#!/usr/bin/env python3
"""Apply wave-17 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave17 import (
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE17_METHOD,
    SCIENTIFIC_SMART_RANDOM_METHOD_ID,
    SMART_MULTI_BET_METHOD_ID,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE17_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "4a03137a6d7c2be3b8daa238a1292cbe35f563c800b6654c6c585888a25917dd"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE17_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "2362665d0e019c118c71ee468281b90046e9e61b5f5d24b60f106def9340bb91"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 41,
    "CLOSED_UNEXECUTABLE": 30,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 146,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 43,
    "CLOSED_UNEXECUTABLE": 30,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 144,
}
_NATIVE_TICKET_COUNT = {
    SCIENTIFIC_SMART_RANDOM_METHOD_ID: 7,
    SMART_MULTI_BET_METHOD_ID: 6,
}
_COMBINATION_COUNT = {
    SCIENTIFIC_SMART_RANDOM_METHOD_ID: 1,
    SMART_MULTI_BET_METHOD_ID: 6,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-17 evidence is inconsistent."""


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
    ):
        raise CatalogOverlayError("wave-17 evidence identity changed")
    rows_raw = evidence.get("strategies")
    if not isinstance(rows_raw, list):
        raise CatalogOverlayError(
            "wave-17 evidence must contain two strategies"
        )
    strategies: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], rows_raw):
        if not isinstance(candidate, dict):
            raise CatalogOverlayError("wave-17 strategy is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if (
            type(method_id) is not str
            or method_id in strategies
            or method_id not in SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE17_METHOD[method_id]
            or row.get("native_ticket_count")
            != _NATIVE_TICKET_COUNT[method_id]
            or row.get("combination_count")
            != _COMBINATION_COUNT[method_id]
            or row.get("candidate_k") is not None
            or row.get("ok_execution_count") != 2148
        ):
            raise CatalogOverlayError("wave-17 strategy identity changed")
        strategies[method_id] = row
    if set(strategies) != set(SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS):
        raise CatalogOverlayError("wave-17 evidence omits a strategy")

    parity_raw = evidence.get("parity")
    if not isinstance(parity_raw, dict):
        raise CatalogOverlayError("wave-17 parity evidence changed")
    parity = cast(dict[str, Any], parity_raw)
    if (
        parity.get("case_count") != 8
        or parity.get("status") != "PASS"
        or len(cast(list[object], parity.get("source_artifacts", [])))
        != 2
        or len(cast(list[object], parity.get("support_artifacts", [])))
        != 2
    ):
        raise CatalogOverlayError("wave-17 parity evidence changed")
    return strategies


def apply_wave17_evidence(
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
        raise CatalogOverlayError("wave-17 evidence file changed")
    strategies = _validate_evidence(evidence)

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

    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS:
        record = record_by_method.get(method_id)
        strategy = strategies[method_id]
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256")
            != strategy.get("source_sha256")
        ):
            raise CatalogOverlayError(
                "wave-17 evidence leaves the validated universe"
            )
        if method_id == SCIENTIFIC_SMART_RANDOM_METHOD_ID:
            candidate_semantics = (
                "NOT_APPLICABLE_NO_PRE_TICKET_CANDIDATE_K"
            )
            combination_semantics = (
                "FROZEN_SOURCE_CONFIGURATION_COUNT_1_DISTINCT_FROM_"
                "SEVEN_NATIVE_TICKETS"
            )
            order_semantics = (
                "FROZEN_STABLE_EV_SCORE_DESCENDING_NATIVE_ORDER_"
                "BEFORE_ORDERED_20_CONSTRUCTION"
            )
            status_detail = (
                "seven normative/diverse smart-random tickets"
            )
        else:
            candidate_semantics = (
                "NOT_APPLICABLE_NO_PRE_TICKET_CANDIDATE_K; "
                "FROZEN_CATEGORY_POOL_SIZES_RECORDED_SEPARATELY"
            )
            combination_semantics = (
                "SIX_DECLARED_COMPLEMENTARY_STRATEGY_BRANCHES_"
                "DISTINCT_FROM_SIX_NATIVE_TICKETS"
            )
            order_semantics = (
                "FROZEN_SOURCE_STRATEGY_DECLARATION_ORDER_BEFORE_"
                "ORDERED_20_CONSTRUCTION"
            )
            status_detail = (
                "six complementary candidate-pool strategy tickets"
            )
        record.update(
            {
                "candidate_k_semantics": candidate_semantics,
                "combination_count_semantics": combination_semantics,
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE17_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Exact frozen-class parity passed four causal "
                    f"cutoffs for {status_detail}. The unpreserved "
                    "module-global random state was replaced by a "
                    "target-stable CPython MT19937 seed with seed "
                    "evidence recorded per execution. 2148 causal "
                    "executions completed and one insufficient-history "
                    "closure remained explicit. Compact evidence "
                    f"SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_EXACT_NATIVE_POSITIONAL_DUPLICATES"
                ),
                "ticket_order_semantics": order_semantics,
                "unranked_reason": (
                    "RANKED_BACKTEST_EVIDENCE_AVAILABLE"
                ),
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
                "SOURCE_NATIVE_WAVE17_TARGET_STABLE_RANDOM_AND_"
                "SMART_MULTI_CAUSAL_BACKTEST"
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
    catalog = apply_wave17_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(catalog) + b"\n")


if __name__ == "__main__":
    main()
