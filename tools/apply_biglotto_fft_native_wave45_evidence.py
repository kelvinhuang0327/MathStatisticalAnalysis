#!/usr/bin/env python3
"""Apply wave-45 FFT-native evidence to the full strategy catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_fft_native_portfolios_wave45 import (
    FROZEN_SOURCE_COMMIT,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE45_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE45_METHOD,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE45_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS,
    TRIPLE_ALIAS_METHOD_ID,
    TRIPLE_ORIGINAL_METHOD_ID,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = "b18e432eac7be977fe81e9d4fd1bc71830fcffde20a48579572ddde55de77f4e"
BASE_CATALOG_FILE_SHA256 = "ed43a5e50f66d2d00d8d8dbaf1a69447c6cf70dee8b2c9b38e643bd3f0c28c38"
EXPECTED_EVIDENCE_SHA256 = "611c1a940505ecb9e5e1f079e31b0ca2e42948c8dad40a68610ead8060abb06c"
EXPECTED_EVIDENCE_FILE_SHA256 = "8aa8bae620c4afbee5f42d3dce055856087231c8f8005372beba6726cb3aa91a"
EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_FFT_NATIVE_WAVE45_EVIDENCE_V1"
EVIDENCE_ARTIFACT_NAME = "biglotto_legacy_fft_native_wave45_evidence_v1.json"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 83,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 7,
    "OWNER_DECISION_REQUIRED": 66,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 87,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 8,
    "OWNER_DECISION_REQUIRED": 61,
}
EXPECTED_OK_COUNTS = {
    "tools/backtest_big_lotto_3bet.py": 1649,
    "tools/backtest_biglotto_triple_strike_original.py": 1649,
    "tools/backtest_fcf_vs_ts3.py": 1999,
    "tools/verify_markov_vs_triple_2bet.py": 1648,
}
EXPECTED_CLOSED_COUNTS = {
    "tools/backtest_big_lotto_3bet.py": 500,
    "tools/backtest_biglotto_triple_strike_original.py": 500,
    "tools/backtest_fcf_vs_ts3.py": 150,
    "tools/verify_markov_vs_triple_2bet.py": 501,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-45 evidence is inconsistent."""


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
    reduced = {key: value for key, value in document.items() if key != "catalog_sha256"}
    return hashlib.sha256(_canonical_bytes(reduced)).hexdigest()


def _validate_evidence(
    evidence: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version") != EVIDENCE_SCHEMA_VERSION
        or evidence.get("evidence_sha256") != EXPECTED_EVIDENCE_SHA256
        or evidence.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or evidence.get("base_catalog_sha256") != BASE_CATALOG_SHA256
        or evidence.get("base_catalog_file_sha256") != BASE_CATALOG_FILE_SHA256
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256")
        != "8ec3c9b7631ba03837313775e00ed5b96df462bd1d377d230291acc8b4687e0a"
        or evidence.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or evidence.get("final_progress")
        != {
            "backtested_count": 87,
            "closed_count": 65,
            "duplicate_alias_count": 8,
            "owner_decision_required_count": 61,
            "reproduced_count": 87,
            "total_strategy_count": 221,
            "uncompleted_count": 61,
        }
    ):
        raise CatalogOverlayError("wave-45 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError("wave-45 strategy evidence changed")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS or method_id in by_method:
            raise CatalogOverlayError("wave-45 strategy method set changed")
        typed_method_id = cast(str, method_id)
        expected_combination = SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE45_METHOD[
            typed_method_id
        ]
        if (
            row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE45_METHOD[typed_method_id]
            or row.get("ok_execution_count") != EXPECTED_OK_COUNTS[typed_method_id]
            or row.get("closed_execution_count") != EXPECTED_CLOSED_COUNTS[typed_method_id]
            or row.get("candidate_k_distribution") != {"49": EXPECTED_OK_COUNTS[typed_method_id]}
            or row.get("native_ticket_count_distribution")
            != {
                str(
                    {
                        "tools/backtest_big_lotto_3bet.py": 3,
                        "tools/backtest_biglotto_triple_strike_original.py": 3,
                        "tools/backtest_fcf_vs_ts3.py": 6,
                        "tools/verify_markov_vs_triple_2bet.py": 4,
                    }[typed_method_id]
                ): EXPECTED_OK_COUNTS[typed_method_id]
            }
            or row.get("combination_count_distribution")
            != {
                (
                    "null" if expected_combination is None else str(expected_combination)
                ): EXPECTED_OK_COUNTS[typed_method_id]
            }
            or row.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        ):
            raise CatalogOverlayError(f"wave-45 strategy evidence changed: {method_id}")
        by_method[typed_method_id] = row
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS):
        raise CatalogOverlayError("wave-45 strategy evidence is incomplete")
    alias = evidence.get("alias_disposition")
    if not isinstance(alias, dict):
        raise CatalogOverlayError("wave-45 alias evidence changed")
    typed_alias = cast(dict[str, Any], alias)
    if (
        typed_alias.get("alias_method_id") != TRIPLE_ALIAS_METHOD_ID
        or typed_alias.get("canonical_method_id") != TRIPLE_ORIGINAL_METHOD_ID
        or typed_alias.get("overlapping_causal_output_case_count") != 1648
        or typed_alias.get("output_mismatch_count") != 0
        or typed_alias.get("status") != "DUPLICATE_ALIAS"
    ):
        raise CatalogOverlayError("wave-45 alias proof changed")
    return by_method, typed_alias


def apply_wave45_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay four BACKTESTED rows and one DUPLICATE_ALIAS row."""

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
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS:
        record = record_by_method.get(method_id)
        evidence_row = evidence_by_method[method_id]
        if (
            record is None
            or record.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256") != evidence_row.get("source_sha256")
        ):
            raise CatalogOverlayError("wave-45 evidence leaves the validated universe")
        combination_count = SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id]
        record.update(
            {
                "candidate_k_semantics": (
                    "FROZEN_SOURCE_49_LEGAL_NUMBER_SELECTION_DOMAIN_"
                    "DISTINCT_FROM_NATIVE_TICKET_COUNT_SOURCE_"
                    "CONFIGURATION_COUNT_AND_ORDERED_20"
                ),
                "combination_count_semantics": (
                    "NOT_APPLICABLE_SINGLE_SOURCE_CONFIGURATION"
                    if combination_count is None
                    else (
                        "FROZEN_SOURCE_LOCAL_CONFIGURATION_COUNT_2_"
                        "DISTINCT_FROM_CANDIDATE_K_NATIVE_TICKET_COUNT_"
                        "AND_ORDERED_20"
                    )
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Exact frozen CPython/NumPy/SciPy execution was "
                    "captured in a checksummed causal ledger. This method "
                    f"completed {EXPECTED_OK_COUNTS[method_id]} causal "
                    "executions and retained "
                    f"{EXPECTED_CLOSED_COUNTS[method_id]} explicit "
                    "insufficient-history closures. Candidate-K, source "
                    "configuration count, native tickets, positional "
                    "duplicates, and ordered-20 remain separate. Compact "
                    f"evidence SHA-256 is {EXPECTED_EVIDENCE_SHA256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_ALL_FROZEN_POSITIONAL_NATIVE_TICKETS_"
                    "INCLUDING_CROSS_CONFIGURATION_DUPLICATES"
                ),
                "ticket_order_semantics": (
                    "FROZEN_SOURCE_CONFIGURATION_THEN_POSITIONAL_BET_"
                    "ORDER_BEFORE_ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": ("RANKED_BACKTEST_EVIDENCE_AVAILABLE"),
            }
        )
    alias_record = record_by_method.get(TRIPLE_ALIAS_METHOD_ID)
    canonical_record = record_by_method.get(TRIPLE_ORIGINAL_METHOD_ID)
    if (
        alias_record is None
        or canonical_record is None
        or alias_record.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
        or alias_record.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE45_METHOD[TRIPLE_ALIAS_METHOD_ID]
        or alias_evidence.get("alias_strategy_id") != alias_record.get("strategy_id")
        or alias_evidence.get("canonical_strategy_id") != canonical_record.get("strategy_id")
    ):
        raise CatalogOverlayError("wave-45 duplicate alias leaves the validated universe")
    alias_record.update(
        {
            "candidate_k_semantics": ("DUPLICATE_ALIAS_INHERITS_CANONICAL_METHOD_SEMANTICS"),
            "combination_count_semantics": ("DUPLICATE_ALIAS_INHERITS_CANONICAL_METHOD_SEMANTICS"),
            "duplicate_alias_target": canonical_record["strategy_id"],
            "native_ticket_semantics": ("DUPLICATE_ALIAS_NO_INDEPENDENT_NATIVE_PORTFOLIO"),
            "reproduction_status": "DUPLICATE_ALIAS",
            "status_reason": (
                "The source-local Triple Strike selection output matched "
                "the original Triple Strike method at all 1,648 overlapping "
                "causal cutoffs with zero mismatches. The imported Apriori "
                "comparator already has separate catalog rows, so ranking "
                "this wrapper independently would double count the same "
                "local three-ticket selection method. Compact evidence "
                f"SHA-256 is {EXPECTED_EVIDENCE_SHA256}."
            ),
            "ticket_duplicate_semantics": ("INHERITED_FROM_DUPLICATE_ALIAS_TARGET"),
            "ticket_order_semantics": ("INHERITED_FROM_DUPLICATE_ALIAS_TARGET"),
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
            "artifact_sha256": EXPECTED_EVIDENCE_SHA256,
            "evidence_role": (
                "SOURCE_NATIVE_WAVE45_FFT_CAUSAL_BACKTEST_AND_TRIPLE_STRIKE_ALIAS_PROOF"
            ),
        }
    )
    status_counts = Counter(
        cast(str, cast(dict[str, Any], item)["reproduction_status"]) for item in records
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
    catalog = apply_wave45_evidence(
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
