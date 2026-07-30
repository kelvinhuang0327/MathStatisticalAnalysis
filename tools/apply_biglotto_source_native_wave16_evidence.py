#!/usr/bin/env python3
"""Apply mixed wave-16 evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave16 import (
    CLOSED_SOURCE_NATIVE_WAVE16_METHODS,
    HOT_COOCCURRENCE_METHOD_ID,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE16_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "2924248b76d3ecbf43e237b6a29a002a7e2320baeeeed09f8f8e7ccbac1d8eff"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE16_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "c2e4bfe2b2aa36ec9624d7077a466c5990f00172bde3fee4dc11f3ebd512fb00"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 40,
    "CLOSED_UNEXECUTABLE": 28,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 149,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 41,
    "CLOSED_UNEXECUTABLE": 30,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 146,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-16 evidence is inconsistent."""


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
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
    ):
        raise CatalogOverlayError("wave-16 evidence identity changed")

    rows_raw = evidence.get("strategies")
    if not isinstance(rows_raw, list):
        raise CatalogOverlayError(
            "wave-16 evidence must contain one strategy"
        )
    rows = cast(list[object], rows_raw)
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise CatalogOverlayError(
            "wave-16 evidence must contain one strategy"
        )
    strategy = cast(dict[str, Any], rows[0])
    if (
        strategy.get("legacy_method_id")
        != HOT_COOCCURRENCE_METHOD_ID
        or strategy.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD[
            HOT_COOCCURRENCE_METHOD_ID
        ]
        or strategy.get("native_ticket_count") != 1
        or strategy.get("combination_count") != 1
        or strategy.get("candidate_k_observed_values")
        != [6, 11, 16, 19, 20]
        or strategy.get("ok_execution_count") != 2148
    ):
        raise CatalogOverlayError("wave-16 strategy identity changed")

    parity_raw = evidence.get("parity")
    if not isinstance(parity_raw, dict):
        raise CatalogOverlayError("wave-16 parity evidence changed")
    parity = cast(dict[str, Any], parity_raw)
    if (
        parity.get("case_count") != 4
        or parity.get("status") != "PASS"
        or len(cast(list[object], parity.get("support_artifacts", [])))
        != 1
    ):
        raise CatalogOverlayError("wave-16 parity evidence changed")

    dispositions_raw = evidence.get("closed_dispositions")
    if not isinstance(dispositions_raw, list):
        raise CatalogOverlayError(
            "wave-16 evidence must contain two closed dispositions"
        )
    dispositions: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], dispositions_raw):
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-16 closed disposition is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        facts_raw = row.get("decisive_source_facts")
        if (
            type(method_id) is not str
            or method_id in dispositions
            or method_id not in CLOSED_SOURCE_NATIVE_WAVE16_METHODS
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD[method_id]
            or row.get("reproduction_status")
            != "CLOSED_UNEXECUTABLE"
            or type(row.get("reason_code")) is not str
            or type(row.get("status_reason")) is not str
            or not isinstance(facts_raw, list)
            or len(cast(list[object], facts_raw)) < 3
        ):
            raise CatalogOverlayError(
                "wave-16 closed disposition changed"
            )
        dispositions[method_id] = row
    if set(dispositions) != set(CLOSED_SOURCE_NATIVE_WAVE16_METHODS):
        raise CatalogOverlayError(
            "wave-16 evidence omits a closed disposition"
        )
    return strategy, dispositions


def apply_wave16_evidence(
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
        raise CatalogOverlayError("wave-16 evidence file changed")
    strategy, dispositions = _validate_evidence(evidence)

    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise CatalogOverlayError("base catalog records changed")
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], records_raw):
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

    method_id = HOT_COOCCURRENCE_METHOD_ID
    record = record_by_method.get(method_id)
    if (
        record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or record.get("source_sha256")
        != strategy.get("source_sha256")
    ):
        raise CatalogOverlayError(
            "wave-16 evidence leaves the validated universe"
        )
    record.update(
        {
            "candidate_k_semantics": (
                "FROZEN_DYNAMIC_TOP20_HOT_FREQUENCY_POOL_SIZE_"
                "DISTINCT_FROM_ONE_NATIVE_TICKET"
            ),
            "combination_count_semantics": (
                "FROZEN_SOURCE_CONFIGURATION_COUNT_1_DISTINCT_FROM_"
                "NATIVE_TICKET_COUNT"
            ),
            "native_ticket_semantics": (
                "FROZEN_SOURCE_NATIVE_"
                + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE16_METHOD[
                    method_id
                ]
            ),
            "reproduction_status": "BACKTESTED",
            "status_reason": (
                "Exact frozen-class parity passed four causal history "
                "cutoffs with the dependency manifest identity pinned. "
                "2148 causal executions completed and one "
                "insufficient-history closure remained explicit. "
                "Candidate-K was observed as 6, 11, 16, 19, or 20 and "
                "remained distinct from one native ticket and one "
                "source configuration. Compact evidence SHA-256 is "
                f"{evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "NOT_APPLICABLE_SINGLE_NATIVE_TICKET"
            ),
            "ticket_order_semantics": (
                "FROZEN_SINGLE_NATIVE_TICKET_ORDER_BEFORE_ORDERED_20_"
                "CONSTRUCTION"
            ),
            "unranked_reason": "RANKED_BACKTEST_EVIDENCE_AVAILABLE",
        }
    )

    for closed_method_id, disposition in dispositions.items():
        closed_record = record_by_method.get(closed_method_id)
        if (
            closed_record is None
            or closed_record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or closed_record.get("source_commit")
            != FROZEN_SOURCE_COMMIT
            or closed_record.get("source_sha256")
            != disposition.get("source_sha256")
        ):
            raise CatalogOverlayError(
                "wave-16 disposition leaves the validated universe"
            )
        reason_code = cast(str, disposition["reason_code"])
        closed_record.update(
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
                    f"{disposition['status_reason']} Frozen-source "
                    f"wave-16 evidence SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "ticket_order_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "unranked_reason": (
                    f"CLOSED_UNEXECUTABLE:{reason_code}"
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
                "SOURCE_NATIVE_WAVE16_HOT_COOCCURRENCE_CAUSAL_"
                "BACKTEST_AND_EXISTING_PORTFOLIO_AUDIT_DISPOSITIONS"
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
    catalog = apply_wave16_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(catalog) + b"\n")


if __name__ == "__main__":
    main()
