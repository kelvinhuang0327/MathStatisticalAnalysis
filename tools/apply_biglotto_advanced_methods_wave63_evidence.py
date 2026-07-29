#!/usr/bin/env python3
"""Apply wave-63 advanced-method evidence to the full catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_advanced_methods_native_portfolios_wave63 import (
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    FROZEN_SOURCE_COMMIT,
    METHOD_ID,
    NATIVE_TICKET_ORDER,
    NATIVE_TICKET_SEMANTICS,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "093eca2714e5f3c35e0b03eaf359cca4c8570c7d4b2f0a092b06eacfc3629063"
)
BASE_CATALOG_FILE_SHA256 = (
    "0e8a8ab19084a112a354b754d98fe91386d2fafa4617db352fa8305af8f84ae4"
)
EXPECTED_EVIDENCE_SHA256 = (
    "c9d0a3ae6e5678f1aca771dc88b1cc03b11756ce66c129a5198713bf594e0057"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_ADVANCED_METHODS_WAVE63_EVIDENCE_V1"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_advanced_methods_wave63_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 132,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 3,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 133,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 2,
}
EXPECTED_REPORT_SHA256 = (
    "8fb4ab606e88cf9c1dc74f8ceaf6a476e76aa978925ed85ceb8e8b16a9df45c7"
)
EXPECTED_DUPLICATE_DISTRIBUTION = {
    "20": 2133,
    "21": 8,
    "22": 6,
    "23": 1,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-63 evidence is inconsistent."""


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
    rows = cast(list[object], evidence.get("strategies", []))
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
        or evidence.get("base_catalog_file_sha256")
        != BASE_CATALOG_FILE_SHA256
        or evidence.get("causal_protocol") != CAUSAL_PROTOCOL
        or evidence.get("causal_eligibility_rule")
        != CAUSAL_ELIGIBILITY_RULE
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256") != EXPECTED_REPORT_SHA256
        or len(rows) != 1
        or not isinstance(rows[0], dict)
    ):
        raise CatalogOverlayError("wave-63 evidence identity changed")
    strategy = cast(dict[str, Any], rows[0])
    if (
        strategy.get("legacy_method_id") != METHOD_ID
        or strategy.get("source_sha256") != SOURCE_SHA256
        or strategy.get("execution_status_counts")
        != {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
            "OK": 2148,
        }
        or strategy.get("ok_execution_count") != 2148
        or strategy.get("closed_execution_count") != 1
        or strategy.get("candidate_k_distribution")
        != {"49": 2148}
        or strategy.get("combination_count_distribution")
        != {"10": 2148}
        or strategy.get("native_ticket_count_distribution")
        != {"25": 2148}
        or strategy.get(
            "native_duplicate_ticket_count_distribution"
        )
        != EXPECTED_DUPLICATE_DISTRIBUTION
        or strategy.get("native_ticket_semantics")
        != NATIVE_TICKET_SEMANTICS
        or strategy.get("native_ticket_order")
        != NATIVE_TICKET_ORDER
        or strategy.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
        or strategy.get("source_random_baseline_excluded")
        is not True
        or strategy.get(
            "source_main_reverse_chronological_state_reuse_excluded"
        )
        is not True
        or strategy.get("target_stable_reinstantiation") is not True
    ):
        raise CatalogOverlayError(
            "wave-63 strategy evidence changed"
        )
    return strategy


def apply_wave63_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay the wave-63 advanced local-method causal backtest."""

    catalog, raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        raw_catalog_sha256 != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_schema_version")
        != CATALOG_SCHEMA_VERSION
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
        raise CatalogOverlayError("wave-63 evidence file changed")
    strategy = _validate_evidence(evidence)

    records = cast(list[object], catalog.get("records", []))
    record: dict[str, Any] | None = None
    for candidate in records:
        if not isinstance(candidate, dict):
            continue
        typed = cast(dict[str, Any], candidate)
        if typed.get("legacy_method_id") == METHOD_ID:
            record = typed
            break
    if (
        record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or record.get("source_sha256")
        != strategy.get("source_sha256")
    ):
        raise CatalogOverlayError(
            "wave-63 evidence leaves the validated universe"
        )
    record.update(
        {
            "candidate_k_semantics": (
                "ORDERED20_INPUT_USES_FULL_49_LEGAL_NUMBER_DOMAIN_"
                "DISTINCT_FROM_SOURCE_CANDIDATE_K_49_LOCAL_"
                "CONFIGURATION_COUNT_10_NATIVE_TICKET_COUNT_25_AND_"
                "ORDERED_20"
            ),
            "combination_count_semantics": (
                "EXECUTED_SOURCE_METHOD_X_BET_COUNT_CONFIGURATION_"
                "COUNT_10_DISTINCT_FROM_CANDIDATE_K_NATIVE_TICKET_"
                "COUNT_AND_ORDERED_20"
            ),
            "native_ticket_semantics": (
                "FROZEN_SOURCE_NATIVE_" + NATIVE_TICKET_SEMANTICS
            ),
            "reproduction_status": "BACKTESTED",
            "status_reason": (
                "Frozen advanced_methods_benchmark local selectors "
                "reproduced 2148 causal targets from only strictly "
                "earlier history, capped at the source recent-1000 "
                "boundary. Each target reinstantiates the five local "
                "selectors, resets Python and NumPy seed 42, then "
                "preserves the source num_bets=2 method-order block "
                "before the num_bets=3 block as 25 positional tickets. "
                "The source random comparator and noncausal reverse-"
                "chronological mutable-state reuse are excluded by the "
                "frozen causal adapter. The first target is explicitly "
                "CLOSED_INSUFFICIENT_HISTORY. Candidate-K, ten source "
                "configuration blocks, 25 native positions, and the "
                "single ordered-20 portfolio remain distinct. "
                f"Compact evidence SHA-256 is {evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "FROZEN_SOURCE_NATIVE_DUPLICATES_PRESERVED_BEFORE_"
                "ORDERED_20_DERIVATION_DISTRIBUTION_20:2133_21:8_"
                "22:6_23:1"
            ),
            "ticket_order_semantics": (
                NATIVE_TICKET_ORDER
                + "_BEFORE_ORDERED_20_CONSTRUCTION"
            ),
            "unranked_reason": (
                "RANKED_BACKTEST_EVIDENCE_AVAILABLE_PARTIAL_COVERAGE"
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
                "SOURCE_NATIVE_WAVE63_ADVANCED_LOCAL_METHODS_TARGET_"
                "STABLE_CAUSAL_BACKTEST_PROOF"
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
    catalog = apply_wave63_evidence(
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
