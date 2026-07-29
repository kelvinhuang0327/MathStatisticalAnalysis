#!/usr/bin/env python3
"""Apply wave-15 attention replay evidence to the BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave15 import (
    ATTENTION_REPLAY_METHOD_ID,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE15_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "c7371b31baae77afec61e9977b55a0d3b682b7034374cb24a8aff47c9a02eb01"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE15_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "5ab41c5df8bce3bed81e817f24837b4914308a905eb9a60c2f02ed4f5094c551"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 39,
    "CLOSED_UNEXECUTABLE": 28,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 150,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 40,
    "CLOSED_UNEXECUTABLE": 28,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 149,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-15 evidence is inconsistent."""


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


def _evidence_row(evidence: dict[str, Any]) -> dict[str, Any]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
    ):
        raise CatalogOverlayError("wave-15 evidence identity changed")
    rows_raw = evidence.get("strategies")
    if not isinstance(rows_raw, list):
        raise CatalogOverlayError(
            "wave-15 evidence must contain one strategy"
        )
    rows = cast(list[object], rows_raw)
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise CatalogOverlayError(
            "wave-15 evidence must contain one strategy"
        )
    row = cast(dict[str, Any], rows[0])
    if (
        row.get("legacy_method_id") != ATTENTION_REPLAY_METHOD_ID
        or row.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD[
            ATTENTION_REPLAY_METHOD_ID
        ]
        or row.get("native_ticket_count") != 1
        or row.get("ok_execution_count") != 2148
    ):
        raise CatalogOverlayError("wave-15 strategy identity changed")
    parity_raw = evidence.get("parity")
    if not isinstance(parity_raw, dict):
        raise CatalogOverlayError("wave-15 parity evidence changed")
    parity = cast(dict[str, Any], parity_raw)
    if (
        parity.get("case_count") != 4
        or parity.get("status") != "PASS"
        or len(cast(list[object], parity.get("support_artifacts", [])))
        != 3
    ):
        raise CatalogOverlayError("wave-15 parity evidence changed")
    return row


def apply_wave15_evidence(
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
        raise CatalogOverlayError("wave-15 evidence file changed")
    evidence_row = _evidence_row(evidence)

    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise CatalogOverlayError("base catalog records changed")
    records = cast(list[object], records_raw)
    if len(records) != 221:
        raise CatalogOverlayError("base catalog records changed")
    record: dict[str, Any] | None = None
    for candidate in records:
        if not isinstance(candidate, dict):
            continue
        typed = cast(dict[str, Any], candidate)
        if typed.get("legacy_method_id") == ATTENTION_REPLAY_METHOD_ID:
            record = typed
            break
    if (
        record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or record.get("source_sha256")
        != evidence_row.get("source_sha256")
    ):
        raise CatalogOverlayError(
            "wave-15 evidence leaves the validated universe"
        )
    record.update(
        {
            "candidate_k_semantics": "NOT_APPLICABLE",
            "combination_count_semantics": (
                "NOT_APPLICABLE_SINGLE_SOURCE_CONFIGURATION"
            ),
            "native_ticket_semantics": (
                "FROZEN_SOURCE_NATIVE_"
                + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE15_METHOD[
                    ATTENTION_REPLAY_METHOD_ID
                ]
            ),
            "reproduction_status": "BACKTESTED",
            "status_reason": (
                "Exact frozen-class output parity passed four causal "
                "history cutoffs with the checkpoint, dataset, and "
                "training helper blob identities pinned. The frozen "
                "forward-pass logits are explicitly discarded before "
                "fixed recency weights select the ticket. 2148 causal "
                "executions completed and one insufficient-history "
                "closure remained explicit. Compact evidence SHA-256 is "
                f"{evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "NOT_APPLICABLE_SINGLE_NATIVE_TICKET"
            ),
            "ticket_order_semantics": (
                "FROZEN_WEIGHTED_FREQUENCY_STABLE_ORDER_BEFORE_"
                "ORDERED_20_CONSTRUCTION"
            ),
            "unranked_reason": "RANKED_BACKTEST_EVIDENCE_AVAILABLE",
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
                "SOURCE_NATIVE_WAVE15_ATTENTION_FIXED_RECENCY_"
                "CAUSAL_BACKTEST"
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
    catalog = apply_wave15_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(catalog) + b"\n")


if __name__ == "__main__":
    main()
