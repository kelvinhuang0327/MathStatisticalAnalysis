#!/usr/bin/env python3
"""Apply wave-46 source-grid evidence to the full strategy catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_grid_native_portfolios_wave46 import (
    FROZEN_SOURCE_COMMIT,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE46_METHOD,
    OPTIMAL_MATRIX_METHOD_ID,
    PREDICTABILITY_ALIAS_METHOD_ID,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE46_METHOD,
    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = "a13329f3bbe134d6825f7c14d9476b98e9ae4864588cc5f83ac94be17264a2c3"
BASE_CATALOG_FILE_SHA256 = "d6c7a0dbbd6430f5d8c74c1d9b93de0ae2cc1bc81806936c0b5156ea52b84bf2"
EXPECTED_EVIDENCE_SHA256 = "a81d0c1b2a4f9ed343d547dbaeff5b83ca77bb453bcf7ecb843779ff7414f9ac"
EXPECTED_EVIDENCE_FILE_SHA256 = (
    "2b5704b3ef48b9c88cdd85bb6915e0caa4b7b635181d5d7afda5dacfe16f5a45"
)
EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_NATIVE_WAVE46_EVIDENCE_V1"
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_source_grid_native_wave46_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 87,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 8,
    "OWNER_DECISION_REQUIRED": 61,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 99,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 9,
    "OWNER_DECISION_REQUIRED": 48,
}
EXPECTED_OK_COUNTS = {
    "ai_lab/automl_biglotto/portfolio_optimizer.py": 1949,
    "tools/backtest_big_lotto_orthogonal_5bet.py": 1649,
    "tools/backtest_biglotto_6bet.py": 1949,
    "tools/backtest_biglotto_6bet_ewma.py": 1949,
    "tools/backtest_biglotto_coldpool_15.py": 1849,
    "tools/backtest_biglotto_markov_4bet.py": 1999,
    "tools/backtest_biglotto_triple_strike_v2.py": 1649,
    "tools/backtest_markov_repeat_exception.py": 1999,
    "tools/backtest_structural_group.py": 1999,
    "tools/backtest_sum_constraint.py": 1999,
    "tools/optimal_2bet_3bet_matrix.py": 1949,
    "tools/predict_biglotto_quad_strike.py": 2148,
}
EXPECTED_CLOSED_COUNTS = {
    method_id: 2149 - count for method_id, count in EXPECTED_OK_COUNTS.items()
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-46 evidence is inconsistent."""


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
    return cast(dict[str, Any], parsed), hashlib.sha256(raw).hexdigest()


def _catalog_hash(document: dict[str, Any]) -> str:
    reduced = {
        key: value for key, value in document.items() if key != "catalog_sha256"
    }
    return hashlib.sha256(_canonical_bytes(reduced)).hexdigest()


def _validate_evidence(
    evidence: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version") != EVIDENCE_SCHEMA_VERSION
        or evidence.get("evidence_sha256") != EXPECTED_EVIDENCE_SHA256
        or evidence.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256") != BASE_CATALOG_SHA256
        or evidence.get("base_catalog_file_sha256")
        != BASE_CATALOG_FILE_SHA256
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256")
        != "80351893fb4f3cfc1a83d48bbf91edf341fe409ed32d1e09dad007dbc0b4e383"
        or evidence.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or evidence.get("final_progress")
        != {
            "backtested_count": 99,
            "closed_count": 65,
            "duplicate_alias_count": 9,
            "owner_decision_required_count": 48,
            "reproduced_count": 99,
            "total_strategy_count": 221,
            "uncompleted_count": 48,
        }
    ):
        raise CatalogOverlayError("wave-46 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError("wave-46 strategy evidence changed")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if (
            method_id not in SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS
            or method_id in by_method
        ):
            raise CatalogOverlayError("wave-46 strategy method set changed")
        typed_method_id = cast(str, method_id)
        expected_ok = EXPECTED_OK_COUNTS[typed_method_id]
        expected_native_count = (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD[typed_method_id]
        )
        expected_configuration_count = (
            SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD[
                typed_method_id
            ]
        )
        if (
            row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD[typed_method_id]
            or row.get("ok_execution_count") != expected_ok
            or row.get("closed_execution_count")
            != EXPECTED_CLOSED_COUNTS[typed_method_id]
            or row.get("candidate_k_distribution") != {"49": expected_ok}
            or row.get("native_ticket_count_distribution")
            != {str(expected_native_count): expected_ok}
            or row.get("source_configuration_count")
            != expected_configuration_count
            or row.get("source_configuration_count_distribution")
            != {str(expected_configuration_count): expected_ok}
            or row.get("source_candidate_k_values")
            != list(
                SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE46_METHOD[
                    typed_method_id
                ]
            )
            or row.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        ):
            raise CatalogOverlayError(
                f"wave-46 strategy evidence changed: {method_id}"
            )
        by_method[typed_method_id] = row
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS):
        raise CatalogOverlayError("wave-46 strategy evidence is incomplete")
    alias = evidence.get("alias_disposition")
    if not isinstance(alias, dict):
        raise CatalogOverlayError("wave-46 alias evidence changed")
    typed_alias = cast(dict[str, Any], alias)
    if (
        typed_alias.get("alias_method_id") != PREDICTABILITY_ALIAS_METHOD_ID
        or typed_alias.get("canonical_method_id") != OPTIMAL_MATRIX_METHOD_ID
        or typed_alias.get("overlapping_causal_output_case_count") != 1949
        or typed_alias.get("output_mismatch_count") != 0
        or typed_alias.get("status") != "DUPLICATE_ALIAS"
    ):
        raise CatalogOverlayError("wave-46 alias proof changed")
    return by_method, typed_alias


def apply_wave46_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay twelve BACKTESTED rows and one DUPLICATE_ALIAS row."""

    catalog, raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_file_sha256 = _read_json(evidence_path)
    if (
        raw_catalog_sha256 != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION
        or catalog.get("catalog_policy_version") != CATALOG_POLICY_VERSION
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or _catalog_hash(catalog) != BASE_CATALOG_SHA256
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or evidence_file_sha256 != EXPECTED_EVIDENCE_FILE_SHA256
    ):
        raise CatalogOverlayError("base catalog or evidence changed")
    evidence_by_method, alias_evidence = _validate_evidence(evidence)
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
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS:
        record = record_by_method.get(method_id)
        evidence_row = evidence_by_method[method_id]
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256") != evidence_row.get("source_sha256")
        ):
            raise CatalogOverlayError(
                "wave-46 evidence leaves the validated universe"
            )
        configuration_count = (
            SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD[
                method_id
            ]
        )
        candidate_values = (
            SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]
        )
        candidate_values_label = "_".join(map(str, candidate_values))
        record.update(
            {
                "candidate_k_semantics": (
                    "ORDERED20_INPUT_USES_FULL_49_LEGAL_NUMBER_DOMAIN_WHILE_"
                    "FROZEN_SOURCE_INTERNAL_CANDIDATE_K_VALUES_ARE_"
                    f"{candidate_values_label}_"
                    "DISTINCT_FROM_NATIVE_TICKET_COUNT_SOURCE_CONFIGURATION_"
                    "COUNT_AND_ORDERED_20"
                ),
                "combination_count_semantics": (
                    f"FROZEN_SOURCE_LOCAL_CONFIGURATION_COUNT_{configuration_count}_"
                    "DISTINCT_FROM_CANDIDATE_K_NATIVE_TICKET_COUNT_AND_ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE46_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Exact frozen CPython/NumPy/SciPy execution was captured "
                    "in a checksummed full-prefix causal ledger. This method "
                    f"completed {EXPECTED_OK_COUNTS[method_id]} causal "
                    f"executions and retained {EXPECTED_CLOSED_COUNTS[method_id]} "
                    "explicit insufficient-history closures. Candidate-K, "
                    f"{configuration_count} source configuration(s), "
                    f"{NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]} "
                    "native positional ticket(s), duplicates, and ordered-20 "
                    "remain separate. Compact evidence SHA-256 is "
                    f"{EXPECTED_EVIDENCE_SHA256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_ALL_FROZEN_POSITIONAL_NATIVE_TICKETS_"
                    "INCLUDING_CROSS_CONFIGURATION_DUPLICATES_BEFORE_"
                    "CHECKSUMMED_ORDERED_20_DERIVATION"
                ),
                "ticket_order_semantics": (
                    "FROZEN_SOURCE_CONFIGURATION_THEN_POSITIONAL_BET_"
                    "ORDER_BEFORE_ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": "RANKED_BACKTEST_EVIDENCE_AVAILABLE",
            }
        )
    alias_record = record_by_method.get(PREDICTABILITY_ALIAS_METHOD_ID)
    canonical_record = record_by_method.get(OPTIMAL_MATRIX_METHOD_ID)
    if (
        alias_record is None
        or canonical_record is None
        or alias_record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or alias_record.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD[
            PREDICTABILITY_ALIAS_METHOD_ID
        ]
        or alias_evidence.get("alias_strategy_id")
        != alias_record.get("strategy_id")
        or alias_evidence.get("canonical_strategy_id")
        != canonical_record.get("strategy_id")
    ):
        raise CatalogOverlayError(
            "wave-46 duplicate alias leaves the validated universe"
        )
    alias_record.update(
        {
            "candidate_k_semantics": (
                "DUPLICATE_ALIAS_INHERITS_CANONICAL_METHOD_SEMANTICS"
            ),
            "combination_count_semantics": (
                "DUPLICATE_ALIAS_INHERITS_CANONICAL_METHOD_SEMANTICS"
            ),
            "duplicate_alias_target": canonical_record["strategy_id"],
            "native_ticket_semantics": (
                "DUPLICATE_ALIAS_NO_INDEPENDENT_NATIVE_PORTFOLIO"
            ),
            "reproduction_status": "DUPLICATE_ALIAS",
            "status_reason": (
                "The embedded five-ticket label portfolio matched "
                "optimal_2bet_3bet_matrix.py at all 1,949 overlapping causal "
                "cutoffs with zero positional ticket mismatches. Ranking this "
                "wrapper independently would double count the same selection "
                "method. Compact evidence SHA-256 is "
                f"{EXPECTED_EVIDENCE_SHA256}."
            ),
            "ticket_duplicate_semantics": (
                "INHERITED_FROM_DUPLICATE_ALIAS_TARGET"
            ),
            "ticket_order_semantics": "INHERITED_FROM_DUPLICATE_ALIAS_TARGET",
            "unranked_reason": "DUPLICATE_ALIAS",
        }
    )
    source_artifacts = cast(list[object], catalog.get("source_artifacts", []))
    source_artifacts.append(
        {
            "artifact_name": EVIDENCE_ARTIFACT_NAME,
            "artifact_sha256": EXPECTED_EVIDENCE_SHA256,
            "evidence_role": (
                "SOURCE_NATIVE_WAVE46_CONFIGURATION_GRID_CAUSAL_BACKTEST_"
                "AND_PREDICTABILITY_PORTFOLIO_ALIAS_PROOF"
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
        raise SystemExit(f"refusing to overwrite existing output: {args.output_file}")
    catalog = apply_wave46_evidence(
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
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
