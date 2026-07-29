#!/usr/bin/env python3
"""Apply wave-64 XGBoost evidence to the full 221-strategy catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_xgboost_native_portfolios_wave64 import (
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    DETERMINISM_PROTOCOL,
    FROZEN_SOURCE_COMMIT,
    METHOD_ID,
    NATIVE_TICKET_ORDER,
    NATIVE_TICKET_SEMANTICS,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256,
    TICKET_SEQUENCE_SHA256,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "518c00da6a791551a74766b1356686e16cef88a087e00e1fdc839dce8e18e8a4"
)
BASE_CATALOG_FILE_SHA256 = (
    "c9f632d1306af42748a5f11493fb19c8bafcddecd3810676ad4178d9133c68ab"
)
EXPECTED_EVIDENCE_SHA256 = (
    "2173aa5a4c354c8d8d11c0459e3017dcc4baaca770dc6fc623df683c0b191741"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_XGBOOST_WAVE64_EVIDENCE_V1"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_xgboost_wave64_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 133,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 2,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 134,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 1,
}
EXPECTED_REPORT_SHA256 = (
    "505c0dc63d081dcd10a9aa530b20af4319000a4d16d22613e73ef6c7e448542f"
)


class CatalogOverlayError(ValueError):
    """The catalog or wave-64 evidence is inconsistent."""


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
        raise CatalogOverlayError("wave-64 evidence identity changed")
    strategy = cast(dict[str, Any], rows[0])
    if (
        strategy.get("legacy_method_id") != METHOD_ID
        or strategy.get("source_sha256") != SOURCE_SHA256
        or strategy.get("execution_status_counts")
        != {
            "CLOSED_INSUFFICIENT_HISTORY": 15,
            "OK": 2134,
        }
        or strategy.get("ok_execution_count") != 2134
        or strategy.get("closed_execution_count") != 15
        or strategy.get("candidate_k_distribution")
        != {"49": 2134}
        or strategy.get("combination_count_distribution")
        != {"1": 2134}
        or strategy.get("native_ticket_count_distribution")
        != {"1": 2134}
        or strategy.get(
            "native_duplicate_ticket_count_distribution"
        )
        != {"0": 2134}
        or strategy.get("native_ticket_semantics")
        != NATIVE_TICKET_SEMANTICS
        or strategy.get("native_ticket_order")
        != NATIVE_TICKET_ORDER
        or strategy.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
        or strategy.get("determinism_protocol")
        != DETERMINISM_PROTOCOL
        or strategy.get("source_random_state_explicit") is not False
        or strategy.get("target_stable_model_retraining") is not True
        or strategy.get("thread_count_parity_passed") is not True
        or strategy.get("ticket_sequence_sha256")
        != TICKET_SEQUENCE_SHA256
    ):
        raise CatalogOverlayError("wave-64 strategy evidence changed")
    return strategy


def apply_wave64_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay the wave-64 frozen XGBoost causal backtest."""

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
        raise CatalogOverlayError("wave-64 evidence file changed")
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
            "wave-64 evidence leaves the validated universe"
        )
    record.update(
        {
            "candidate_k_semantics": (
                "FROZEN_MODEL_RANKS_49_MULTI_OUTPUT_LABEL_"
                "PROBABILITIES_DISTINCT_FROM_ONE_NATIVE_TICKET_ONE_"
                "SOURCE_CONFIGURATION_AND_ORDERED_20"
            ),
            "combination_count_semantics": (
                "ONE_SOURCE_MODEL_CONFIGURATION_DISTINCT_FROM_"
                "CANDIDATE_K_NATIVE_TICKET_COUNT_AND_ORDERED_20"
            ),
            "native_ticket_semantics": NATIVE_TICKET_SEMANTICS,
            "reproduction_status": "BACKTESTED",
            "status_reason": (
                "Exact frozen XGBoostPredictor.predict output was "
                "reproduced under CPython 3.9.6, NumPy 1.26.2, "
                "pandas 2.1.3, scikit-learn 1.3.2, and XGBoost "
                "2.0.2 for every causal target. Each target sees only "
                "strictly earlier history and the source itself caps "
                "training at the most recent 1000 draws. Fifteen "
                "targets retain the source-defined insufficient-"
                "training closure; 2134 targets preserve one native "
                "top-six probability-ranked ticket. Although the "
                "source omits random_state, it uses full row and "
                "column sampling; exact repeat and OpenMP 1-versus-8 "
                "ticket/probability parity passed at five cutoffs. "
                "The 49 model labels, one source configuration, one "
                "native ticket, and one ordered-20 portfolio remain "
                "separate. Compact evidence SHA-256 is "
                f"{evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "NOT_APPLICABLE_SINGLE_NATIVE_TICKET_ALL_2134_"
                "EXECUTIONS_HAVE_ZERO_NATIVE_DUPLICATES"
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
                "SOURCE_NATIVE_WAVE64_FROZEN_XGBOOST_FULL_PREFIX_"
                "CAUSAL_BACKTEST_PROOF"
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
    catalog = apply_wave64_evidence(
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
