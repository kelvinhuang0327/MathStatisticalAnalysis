#!/usr/bin/env python3
"""Build compact evidence for the wave-49 source-grid dispositions."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, cast

from lottolab.application.biglotto_multi_ticket_backtest import (
    BACKTEST_POLICY_VERSION,
    REPORT_SCHEMA_VERSION,
    RESEARCH_DISCLAIMER,
)
from lottolab.application.legacy_source_grid_native_portfolios_wave49 import (
    CONTEXT_POLICY,
    FROZEN_SOURCE_COMMIT,
    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE49_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE49_METHOD,
    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE49_METHOD,
    PINNED_DATASET_SHA256,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE49_METHOD,
    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE49_METHOD,
    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE49_METHOD,
    SOURCE_NATIVE_WAVE49_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE49_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import CONSTRUCTOR_IDENTIFIER
from lottolab.infrastructure.legacy_source_grid_native_batch_import_wave49 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_NATIVE_WAVE49_EVIDENCE_V1"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE49_PARITY_V1"
BASE_CATALOG_SHA256 = "b4fdd1ce3e5edf21592b83cc0473f140a1360dbd6dea9aef2a3b90c91dd3ba4f"
BASE_CATALOG_FILE_SHA256 = "7a6038a751cd8ac3d0e39c40acfe2b3042ef3d1e4aa0525f0f5cc9cacfaec730"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 108,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 37,
}
EXPECTED_FINAL_PROGRESS = {
    "backtested_count": 111,
    "closed_count": 65,
    "duplicate_alias_count": 11,
    "owner_decision_required_count": 34,
    "reproduced_count": 111,
    "total_strategy_count": 221,
    "uncompleted_count": 34,
}
EXPECTED_INPUT_FILE_SHA256 = "94e1ff9e043d6ac39a581df843dda0dbdb5ea433e03ecc62d354b1a24cb036c7"
EXPECTED_INPUT_CANONICAL_SHA256 = "3cf636a9b60c28ce9efb5a5a8c795850e52533d276b8a3a2bbdbf130f7269b18"
EXPECTED_PARITY_FILE_SHA256 = "8ce9f0ea7c7f4dd1b5eb2d1683ee348c2c2b4fa122ebc5421d3c15070320a8c3"
EXPECTED_PARITY_SHA256 = "f9575eb59ced463f17102ce2914edbd9857c76f0d5aa234f7743a3de28b506bb"
EXPECTED_REPORT_FILE_SHA256 = "7fcccf90df28ab34c3e0f88133fd3c71946e79a8138ee02649e6112da991c530"
EXPECTED_REPORT_SHA256 = "f7db309e7fc254bb1ab1e156f727843685fee499e69744e821841620bc44a8d7"
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": "b6fefe6e4b5f9f0856524478670113bc6dffa7ddce1eefea1d672f2f0624a1a4",
    "biglotto_execution_audit.csv": (
        "95e5e0d028458d02f4a3dc36053300bd00b794aed7040a329352de536e87630a"
    ),
    "biglotto_full_rankings.csv": (
        "93a88f38e7b64d3126285a21c362567271fae0fbffa2ab1d6d196b516220bba6"
    ),
    "biglotto_multi_ticket_backtest_report.json": EXPECTED_REPORT_FILE_SHA256,
    "biglotto_official_prize_distributions.csv": (
        "c9a4f4742fc341f0b7d7e4b836f1fb42df7cf90a61e8ab72d6b272df96fc9941"
    ),
    "biglotto_strategy_universe.csv": (
        "c1bb4772dd31b9fadfc5ac447845815222e6e7444b4254bf21e024de05d3866e"
    ),
    "biglotto_success_metrics.csv": (
        "14080a485532c90ddc9cfd96a3f8dbf6fd2394d122e50a490115df9962b18174"
    ),
    "biglotto_top10.csv": "3fa0bea5b35d97229d96074e722d70ed6637542b436110d7bdef3eaadb6eddf8",
}
EXPECTED_OK_COUNTS = {
    method_id: 2149 - MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS
}
EXPECTED_CLOSED_COUNTS = {
    method_id: MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS
}


class EvidenceBuildError(ValueError):
    """Wave-49 evidence inputs violate the frozen contract."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvidenceBuildError(f"{path.name}: invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise EvidenceBuildError(f"{path.name}: top level must be an object")
    return cast(dict[str, Any], parsed), raw


def _distribution(values: list[object]) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                "null"
                if value is None
                else str(value).lower()
                if isinstance(value, bool)
                else str(value)
                for value in values
            ).items()
        )
    )


def _validate_catalog(path: Path) -> dict[str, str]:
    catalog, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
    ):
        raise EvidenceBuildError("base catalog identity changed")
    by_method: dict[str, str] = {}
    for candidate in cast(list[object], catalog.get("records", [])):
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS:
            continue
        typed_method_id = cast(str, method_id)
        if (
            row.get("source_commit") != FROZEN_SOURCE_COMMIT
            or row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE49_METHOD[typed_method_id]
            or not isinstance(row.get("strategy_id"), str)
        ):
            raise EvidenceBuildError(f"wave-49 catalog row changed: {method_id}")
        by_method[typed_method_id] = cast(str, row["strategy_id"])
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS):
        raise EvidenceBuildError("wave-49 catalog method set changed")
    return by_method


def _validate_parity(path: Path) -> None:
    parity, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version") != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("dataset_sha256") != PINNED_DATASET_SHA256
        or parity.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or parity.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or parity.get("native_ticket_case_count") != 105298
        or parity.get("exact_alias_candidates") != []
        or parity.get("cross_wave_exact_alias_candidates") != []
    ):
        raise EvidenceBuildError("wave-49 parity identity changed")


def _validate_input(
    path: Path,
    *,
    strategy_id_by_method: dict[str, str],
) -> tuple[list[dict[str, Any]], str]:
    document, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_INPUT_FILE_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest()
        != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("dataset_version") != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", []))) != 2149
        or len(cast(list[object], document.get("executions", []))) != 6447
    ):
        raise EvidenceBuildError("wave-49 full input identity changed")
    provenance = document.get("source_provenance")
    if not isinstance(provenance, dict):
        raise EvidenceBuildError("wave-49 source provenance changed")
    typed_provenance = cast(dict[str, Any], provenance)
    physical_database_sha256 = typed_provenance.get("database_sha256_before")
    if (
        typed_provenance.get("context_policy") != CONTEXT_POLICY
        or typed_provenance.get("source_native_protocol") != SOURCE_NATIVE_WAVE49_PROTOCOL
        or typed_provenance.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or typed_provenance.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or typed_provenance.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or typed_provenance.get("logical_dataset_sha256") != PINNED_DATASET_SHA256
        or typed_provenance.get("logical_history_anchor")
        != "CHECKSUMMED_WAVE49_FULL_PREFIX_CONTEXT_LEDGER"
        or typed_provenance.get("database_sha256_after") != physical_database_sha256
        or type(physical_database_sha256) is not str
        or typed_provenance.get("execution_status_counts")
        != {"CLOSED_INSUFFICIENT_HISTORY": 1798, "OK": 4649}
    ):
        raise EvidenceBuildError("wave-49 source provenance identity changed")
    method_by_strategy_id = {
        strategy_id_by_method[method_id]: method_id
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS
    }
    executions = cast(list[object], document["executions"])
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-49 execution row changed")
        row = cast(dict[str, Any], candidate)
        if row.get("strategy_id") not in method_by_strategy_id:
            raise EvidenceBuildError("wave-49 execution leaves the method set")
    return (
        [cast(dict[str, Any], row) for row in executions],
        physical_database_sha256,
    )


def _validate_report(path: Path) -> None:
    report, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_REPORT_FILE_SHA256
        or report.get("report_sha256") != EXPECTED_REPORT_SHA256
        or report.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version") != BACKTEST_POLICY_VERSION
        or report.get("research_disclaimer") != RESEARCH_DISCLAIMER
        or report.get("progress") != EXPECTED_FINAL_PROGRESS
        or report.get("input_raw_sha256") != EXPECTED_INPUT_FILE_SHA256
        or report.get("input_canonical_sha256") != EXPECTED_INPUT_CANONICAL_SHA256
        or len(cast(list[object], report.get("metrics", []))) != 384
        or len(cast(list[object], report.get("official_prize_distributions", []))) != 48
        or len(cast(list[object], report.get("rankings", []))) != 28288
    ):
        raise EvidenceBuildError("wave-49 report identity changed")
    actual_checksums = {
        name: hashlib.sha256(path.parent.joinpath(name).read_bytes()).hexdigest()
        for name in EXPECTED_REPORT_CHECKSUMS
    }
    if actual_checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("wave-49 report checksums changed")


def build_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Return compact, checksummed evidence for three backtested rows."""

    strategy_id_by_method = _validate_catalog(catalog_path)
    _validate_parity(parity_path)
    executions, physical_database_sha256 = _validate_input(
        input_path,
        strategy_id_by_method=strategy_id_by_method,
    )
    _validate_report(report_path)
    method_by_strategy_id = {
        strategy_id_by_method[method_id]: method_id
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS
    }
    by_method: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in executions:
        by_method[method_by_strategy_id[cast(str, row["strategy_id"])]].append(row)
    strategies: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS:
        rows = by_method[method_id]
        ok = [row for row in rows if row.get("status") == "OK"]
        closed = [
            row for row in rows if row.get("status") == "CLOSED_INSUFFICIENT_HISTORY"
        ]
        expected_ok = EXPECTED_OK_COUNTS[method_id]
        expected_closed = EXPECTED_CLOSED_COUNTS[method_id]
        if len(ok) != expected_ok or len(closed) != expected_closed:
            raise EvidenceBuildError(f"wave-49 execution counts changed: {method_id}")
        native_metadata = [
            cast(dict[str, Any], row["native_generation"]) for row in ok
        ]
        strategies.append(
            {
                "candidate_k_distribution": _distribution(
                    [row.get("candidate_k") for row in ok]
                ),
                "closed_execution_count": len(closed),
                "execution_status_counts": {
                    "CLOSED_INSUFFICIENT_HISTORY": len(closed),
                    "OK": len(ok),
                },
                "intra_ticket_order_semantics": (
                    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
                ),
                "legacy_method_id": method_id,
                "minimum_history_draws": (
                    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
                ),
                "minimum_history_rationale": (
                    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
                ),
                "native_duplicate_ticket_count_distribution": _distribution(
                    [
                        metadata.get("native_duplicate_ticket_count")
                        for metadata in native_metadata
                    ]
                ),
                "native_ticket_count_distribution": _distribution(
                    [row.get("native_ticket_count") for row in ok]
                ),
                "ok_execution_count": len(ok),
                "source_candidate_k_values": list(
                    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
                ),
                "source_configuration_count": (
                    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
                ),
                "source_configuration_count_distribution": _distribution(
                    [row.get("combination_count") for row in ok]
                ),
                "source_configuration_members": list(
                    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
                ),
                "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
                "source_sha256": SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id],
                "strategy_id": strategy_id_by_method[method_id],
            }
        )
    document: dict[str, object] = {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "context_policy": CONTEXT_POLICY,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "final_progress": EXPECTED_FINAL_PROGRESS,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "input_canonical_sha256": EXPECTED_INPUT_CANONICAL_SHA256,
        "input_file_sha256": EXPECTED_INPUT_FILE_SHA256,
        "ledger_content_sha256": LEDGER_CONTENT_SHA256,
        "ledger_file_sha256": LEDGER_FILE_SHA256,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "parity_file_sha256": EXPECTED_PARITY_FILE_SHA256,
        "parity_sha256": EXPECTED_PARITY_SHA256,
        "physical_regeneration_database_sha256": physical_database_sha256,
        "report_checksums": EXPECTED_REPORT_CHECKSUMS,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_native_protocol": SOURCE_NATIVE_WAVE49_PROTOCOL,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "strategies": strategies,
        "target_draw_count": 2149,
    }
    document["evidence_sha256"] = hashlib.sha256(_canonical_bytes(document)).hexdigest()
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--parity", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output_file}")
    evidence = build_evidence(
        catalog_path=args.catalog,
        input_path=args.input,
        parity_path=args.parity,
        report_path=args.report,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_file_sha256": hashlib.sha256(payload).hexdigest(),
                "evidence_sha256": evidence["evidence_sha256"],
                "final_progress": evidence["final_progress"],
                "strategy_count": len(cast(list[object], evidence["strategies"])),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
