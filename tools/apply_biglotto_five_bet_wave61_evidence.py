#!/usr/bin/env python3
"""Apply wave-61 five-bet closed-result evidence to the catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_five_bet_native_portfolios_wave61 import (
    CAUSAL_PROTOCOL,
    FROZEN_SOURCE_COMMIT,
    METHOD_ID,
    NATIVE_TICKET_SEMANTICS,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "d3d3aaa7b8b0b8b6dff39ea900440944812cdb5118f90c20a9dd02c733be77f9"
)
BASE_CATALOG_FILE_SHA256 = (
    "21e229c8994b292dc7be08922c15113094d3f19e8d675282ca388a6d23ceeb44"
)
EXPECTED_EVIDENCE_SHA256 = (
    "75df66d094c926c4e58f2872599fcaca780508ed0061452d957d20e6c2b53560"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_FIVE_BET_WAVE61_EVIDENCE_V1"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_five_bet_wave61_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 129,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 6,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 130,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 5,
}
EXPECTED_REPORT_SHA256 = (
    "ea0950f3f9f46ecbf29f12c54e95540a4641f76565d82ae1d940b081ad830181"
)
EXPECTED_DUPLICATE_DISTRIBUTION = {
    "2": 20,
    "3": 19,
    "4": 5,
    "5": 5,
    "11": 39,
    "12": 66,
    "13": 19,
    "14": 12,
    "15": 1,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-61 evidence is inconsistent."""


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
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256") != EXPECTED_REPORT_SHA256
        or len(rows) != 1
        or not isinstance(rows[0], dict)
    ):
        raise CatalogOverlayError("wave-61 evidence identity changed")
    strategy = cast(dict[str, Any], rows[0])
    if (
        strategy.get("legacy_method_id") != METHOD_ID
        or strategy.get("source_sha256") != SOURCE_SHA256
        or strategy.get("execution_status_counts")
        != {
            "CLOSED_EXECUTION_ERROR": 14,
            "CLOSED_REJECTED": 1949,
            "OK": 186,
        }
        or strategy.get("ok_execution_count") != 186
        or strategy.get("closed_execution_count") != 1963
        or strategy.get("candidate_k_distribution")
        != {"49": 186}
        or strategy.get("combination_count_distribution")
        != {"3": 49, "5": 137}
        or strategy.get("native_ticket_count_distribution")
        != {"15": 49, "25": 137}
        or strategy.get(
            "native_duplicate_ticket_count_distribution"
        )
        != EXPECTED_DUPLICATE_DISTRIBUTION
        or strategy.get("native_ticket_semantics")
        != NATIVE_TICKET_SEMANTICS
        or strategy.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
    ):
        raise CatalogOverlayError(
            "wave-61 strategy evidence changed"
        )
    return strategy


def apply_wave61_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay the partial-coverage five-bet causal backtest."""

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
        raise CatalogOverlayError("wave-61 evidence file changed")
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
            "wave-61 evidence leaves the validated universe"
        )
    record.update(
        {
            "candidate_k_semantics": (
                "ORDERED20_INPUT_USES_FULL_49_LEGAL_NUMBER_DOMAIN_"
                "DISTINCT_FROM_SOURCE_CANDIDATE_POOLS_18_20_NATIVE_"
                "TICKET_COUNT_CONFIGURATION_COUNT_AND_ORDERED_20"
            ),
            "combination_count_semantics": (
                "EXECUTED_SOURCE_MAIN_CONFIGURATION_COUNT_3_OR_5_"
                "DISTINCT_FROM_CANDIDATE_K_NATIVE_TICKET_COUNT_AND_"
                "ORDERED_20"
            ),
            "native_ticket_semantics": (
                "FROZEN_SOURCE_NATIVE_" + NATIVE_TICKET_SEMANTICS
            ),
            "reproduction_status": "BACKTESTED",
            "status_reason": (
                "Frozen source main runs horizons 150 and 200 in a "
                "declared five-call order. The exact closed-result replay "
                "retains 186 legal causal portfolios: 49 with 15 native "
                "positions and 137 with 25; 1949 targets outside those "
                "horizons are CLOSED_REJECTED and 14 source outputs with "
                "illegal ticket positions are CLOSED_EXECUTION_ERROR. "
                "All legal executions use only strict earlier prefixes, "
                "preserve source seed-42 run boundaries and duplicates, "
                "and derive one ordered-20 portfolio before all four "
                f"prefix tests. Compact evidence SHA-256 is {evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "FROZEN_SOURCE_NATIVE_DUPLICATES_PRESERVED_BEFORE_"
                "ORDERED_20_DERIVATION_VARIABLE_DISTRIBUTION_IN_EVIDENCE"
            ),
            "ticket_order_semantics": (
                "SOURCE_MAIN_CONFIGURATION_CALL_ORDER_THEN_BET_"
                "POSITION_BEFORE_ORDERED_20_CONSTRUCTION"
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
                "SOURCE_NATIVE_WAVE61_FIVE_BET_CLOSED_RESULT_HORIZON_"
                "CAUSAL_BACKTEST_AND_INVALID_OUTPUT_CLOSURE_PROOF"
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
    catalog = apply_wave61_evidence(
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
