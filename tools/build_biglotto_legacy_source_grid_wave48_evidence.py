#!/usr/bin/env python3
"""Build compact evidence for the wave-48 source-grid dispositions."""

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
from lottolab.application.legacy_source_grid_native_portfolios_wave48 import (
    CONTEXT_POLICY,
    FROZEN_SOURCE_COMMIT,
    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE48_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE48_METHOD,
    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE48_METHOD,
    OPTIMIZE_5BET_ALIAS_METHOD_ID,
    OPTIMIZE_5BET_ALIAS_TARGET_METHOD_ID,
    PINNED_DATASET_SHA256,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE48_METHOD,
    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE48_METHOD,
    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE48_METHOD,
    SOURCE_NATIVE_WAVE48_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE48_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import CONSTRUCTOR_IDENTIFIER
from lottolab.infrastructure.legacy_source_grid_native_batch_import_wave48 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_NATIVE_WAVE48_EVIDENCE_V1"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE48_PARITY_V1"
BASE_CATALOG_SHA256 = "ec260faa8b40d9cf8435ee2b6c460be1ec5ba500ac27968923fce26b869c1bfe"
BASE_CATALOG_FILE_SHA256 = "d09eb4876f0dbaa47c8d8fc83e9e5fcd9926ab3a4d14f3cd632a402410d43f4d"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 106,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 10,
    "OWNER_DECISION_REQUIRED": 40,
}
EXPECTED_PRE_OVERLAY_PROGRESS = {
    "backtested_count": 108,
    "closed_count": 65,
    "duplicate_alias_count": 10,
    "owner_decision_required_count": 38,
    "reproduced_count": 108,
    "total_strategy_count": 221,
    "uncompleted_count": 38,
}
EXPECTED_FINAL_PROGRESS = {
    "backtested_count": 108,
    "closed_count": 65,
    "duplicate_alias_count": 11,
    "owner_decision_required_count": 37,
    "reproduced_count": 108,
    "total_strategy_count": 221,
    "uncompleted_count": 37,
}
EXPECTED_INPUT_FILE_SHA256 = "d991dcea0d23e772a8771244223a5fdc207e3a4f97bf5d75d71b0bbb314cc799"
EXPECTED_INPUT_CANONICAL_SHA256 = "0de7e1613b0c58f3bcec4299c50494a770a631bf6e29270449fe7d2d14c80af3"
EXPECTED_PARITY_FILE_SHA256 = "14363930c208c58bca911e44f55ad023db663cd845bc35c536d399377c217259"
EXPECTED_PARITY_SHA256 = "b38d648411c2e354d5bbbecd8b8e79f0235b15ccc9b97df1c1d364bcc8efad87"
EXPECTED_REPORT_FILE_SHA256 = "c30e5e9ca5f913f96e4074097aecf21ea51db0ff65d1aa65c2b4856b002a1914"
EXPECTED_REPORT_SHA256 = "d8538162672b1048719fdef97c6700f8dd380f58695e534a4424985ad961495a"
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": "e5a49e0440ec2a1b9f88a01ed9eaf88a96b958bb0f4fbd47a3a0228428c225c0",
    "biglotto_execution_audit.csv": (
        "c5596ad238f2e7d04ee730f8057863c59863a94ae5793fb2809b9f375946f566"
    ),
    "biglotto_full_rankings.csv": (
        "66f275098653cb923813475494e06b244a7395d69b1e5616dbb802ac2aff129e"
    ),
    "biglotto_multi_ticket_backtest_report.json": EXPECTED_REPORT_FILE_SHA256,
    "biglotto_official_prize_distributions.csv": (
        "914890af81d372c0eb72cd00c0e1be6f82251f880aa1ef9093f232a8086247e6"
    ),
    "biglotto_strategy_universe.csv": (
        "6a90cf3e2ca5f41f1cdc6183aedce9f59ab65202975fa63502870fd80aad2330"
    ),
    "biglotto_success_metrics.csv": (
        "36cd47085124c0de8205bdcd82a8621c5fc6b53606886a0962dc3d948c19573b"
    ),
    "biglotto_top10.csv": "a2552b65633a777461e657c3d120c457a30881723c3e3239604cd9cfc481f601",
}
EXPECTED_OK_COUNTS = {
    method_id: 2149 - MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS
}
EXPECTED_CLOSED_COUNTS = {
    method_id: MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS
}


class EvidenceBuildError(ValueError):
    """Wave-48 evidence inputs violate the frozen contract."""


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
    relevant = {
        *SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS,
        OPTIMIZE_5BET_ALIAS_METHOD_ID,
        OPTIMIZE_5BET_ALIAS_TARGET_METHOD_ID,
    }
    by_method: dict[str, str] = {}
    for candidate in cast(list[object], catalog.get("records", [])):
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id not in relevant:
            continue
        typed_method_id = cast(str, method_id)
        if row.get("source_commit") != FROZEN_SOURCE_COMMIT or not isinstance(
            row.get("strategy_id"),
            str,
        ):
            raise EvidenceBuildError(f"wave-48 catalog row changed: {method_id}")
        if typed_method_id == OPTIMIZE_5BET_ALIAS_TARGET_METHOD_ID:
            if row.get("reproduction_status") != "BACKTESTED":
                raise EvidenceBuildError("wave-48 canonical alias target changed")
        elif (
            row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE48_METHOD[typed_method_id]
        ):
            raise EvidenceBuildError(f"wave-48 catalog row changed: {method_id}")
        by_method[typed_method_id] = cast(str, row["strategy_id"])
    if set(by_method) != relevant:
        raise EvidenceBuildError("wave-48 catalog method set changed")
    return by_method


def _validate_parity(path: Path) -> None:
    parity, raw = _read_json(path)
    expected_alias = [
        {
            "left_method_id": OPTIMIZE_5BET_ALIAS_METHOD_ID,
            "output_mismatch_count": 0,
            "overlapping_causal_output_case_count": 1500,
            "right_method_id": OPTIMIZE_5BET_ALIAS_TARGET_METHOD_ID,
        }
    ]
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version") != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("dataset_sha256") != PINNED_DATASET_SHA256
        or parity.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or parity.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or parity.get("native_ticket_case_count") != 80394
        or parity.get("exact_alias_candidates") != []
        or parity.get("cross_wave_exact_alias_candidates") != expected_alias
    ):
        raise EvidenceBuildError("wave-48 parity identity changed")


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
        or len(cast(list[object], document.get("executions", []))) != 4298
    ):
        raise EvidenceBuildError("wave-48 full input identity changed")
    provenance = document.get("source_provenance")
    if not isinstance(provenance, dict):
        raise EvidenceBuildError("wave-48 source provenance changed")
    typed_provenance = cast(dict[str, Any], provenance)
    physical_database_sha256 = typed_provenance.get("database_sha256_before")
    if (
        typed_provenance.get("context_policy") != CONTEXT_POLICY
        or typed_provenance.get("source_native_protocol") != SOURCE_NATIVE_WAVE48_PROTOCOL
        or typed_provenance.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or typed_provenance.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or typed_provenance.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or typed_provenance.get("logical_dataset_sha256") != PINNED_DATASET_SHA256
        or typed_provenance.get("logical_history_anchor")
        != "CHECKSUMMED_WAVE48_FULL_PREFIX_CONTEXT_LEDGER"
        or typed_provenance.get("database_sha256_after") != physical_database_sha256
        or type(physical_database_sha256) is not str
        or typed_provenance.get("execution_status_counts")
        != {"CLOSED_INSUFFICIENT_HISTORY": 1149, "OK": 3149}
    ):
        raise EvidenceBuildError("wave-48 source provenance identity changed")
    method_by_strategy_id = {
        strategy_id_by_method[method_id]: method_id
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS
    }
    executions = cast(list[object], document["executions"])
    by_method: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-48 execution row changed")
        row = cast(dict[str, Any], candidate)
        method_id = method_by_strategy_id.get(cast(str, row.get("strategy_id")))
        if method_id is None:
            raise EvidenceBuildError("wave-48 execution leaves the method set")
        by_method[method_id].append(row)
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS):
        raise EvidenceBuildError("wave-48 execution method set changed")
    return (
        [cast(dict[str, Any], row) for row in executions],
        physical_database_sha256,
    )


def _validate_report(path: Path, report_directory: Path) -> None:
    report, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_REPORT_FILE_SHA256
        or report.get("report_sha256") != EXPECTED_REPORT_SHA256
        or report.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version") != BACKTEST_POLICY_VERSION
        or report.get("research_disclaimer") != RESEARCH_DISCLAIMER
        or report.get("progress") != EXPECTED_PRE_OVERLAY_PROGRESS
        or report.get("input_raw_sha256") != EXPECTED_INPUT_FILE_SHA256
        or report.get("input_canonical_sha256") != EXPECTED_INPUT_CANONICAL_SHA256
        or len(cast(list[object], report.get("metrics", []))) != 256
        or len(cast(list[object], report.get("official_prize_distributions", []))) != 32
        or len(cast(list[object], report.get("rankings", []))) != 28288
    ):
        raise EvidenceBuildError("wave-48 report identity changed")
    actual_checksums = {
        name: hashlib.sha256(report_directory.joinpath(name).read_bytes()).hexdigest()
        for name in EXPECTED_REPORT_CHECKSUMS
    }
    if actual_checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("wave-48 report checksums changed")


def build_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Return compact, checksummed evidence for two backtests and one alias."""

    strategy_id_by_method = _validate_catalog(catalog_path)
    _validate_parity(parity_path)
    executions, physical_database_sha256 = _validate_input(
        input_path,
        strategy_id_by_method=strategy_id_by_method,
    )
    _validate_report(report_path, report_path.parent)
    method_by_strategy_id = {
        strategy_id_by_method[method_id]: method_id
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS
    }
    by_method: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in executions:
        by_method[method_by_strategy_id[cast(str, row["strategy_id"])]].append(row)
    strategies: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE48_METHODS:
        rows = by_method[method_id]
        ok = [row for row in rows if row.get("status") == "OK"]
        closed = [
            row for row in rows if row.get("status") == "CLOSED_INSUFFICIENT_HISTORY"
        ]
        expected_ok = EXPECTED_OK_COUNTS[method_id]
        expected_closed = EXPECTED_CLOSED_COUNTS[method_id]
        if len(ok) != expected_ok or len(closed) != expected_closed:
            raise EvidenceBuildError(f"wave-48 execution counts changed: {method_id}")
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
                    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id]
                ),
                "legacy_method_id": method_id,
                "minimum_history_draws": (
                    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id]
                ),
                "minimum_history_rationale": (
                    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id]
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
                    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id]
                ),
                "source_configuration_count": (
                    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id]
                ),
                "source_configuration_count_distribution": _distribution(
                    [row.get("combination_count") for row in ok]
                ),
                "source_configuration_members": list(
                    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id]
                ),
                "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
                "source_sha256": SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE48_METHOD[method_id],
                "strategy_id": strategy_id_by_method[method_id],
            }
        )
    document: dict[str, object] = {
        "alias_disposition": {
            "alias_method_id": OPTIMIZE_5BET_ALIAS_METHOD_ID,
            "alias_source_sha256": SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE48_METHOD[
                OPTIMIZE_5BET_ALIAS_METHOD_ID
            ],
            "alias_strategy_id": strategy_id_by_method[OPTIMIZE_5BET_ALIAS_METHOD_ID],
            "canonical_method_id": OPTIMIZE_5BET_ALIAS_TARGET_METHOD_ID,
            "canonical_strategy_id": strategy_id_by_method[
                OPTIMIZE_5BET_ALIAS_TARGET_METHOD_ID
            ],
            "output_mismatch_count": 0,
            "overlapping_causal_output_case_count": 1500,
            "status": "DUPLICATE_ALIAS",
        },
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
        "source_native_protocol": SOURCE_NATIVE_WAVE48_PROTOCOL,
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
