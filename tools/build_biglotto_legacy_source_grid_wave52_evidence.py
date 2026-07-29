#!/usr/bin/env python3
"""Build compact evidence for the wave-52 source-grid dispositions."""

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
from lottolab.application.legacy_source_grid_native_portfolios_wave52 import (
    CONTEXT_POLICY,
    FROZEN_SOURCE_COMMIT,
    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE52_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE52_METHOD,
    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE52_METHOD,
    PINNED_DATASET_SHA256,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE52_METHOD,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE52_METHOD,
    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE52_METHOD,
    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE52_METHOD,
    SOURCE_NATIVE_WAVE52_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE52_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE52_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import CONSTRUCTOR_IDENTIFIER
from lottolab.infrastructure.legacy_source_grid_native_batch_import_wave52 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_NATIVE_WAVE52_EVIDENCE_V1"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE52_PARITY_V1"
BASE_CATALOG_SHA256 = "49ec499f5471538c4255867af513a53e2a67c0c8013938f541cc971a1a7765cd"
BASE_CATALOG_FILE_SHA256 = "e1af7ebf25acd41061bd786cf398b99d3a8d1892807b11e903ef97659eeb1d02"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 115,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 30,
}
EXPECTED_FINAL_PROGRESS = {
    "backtested_count": 117,
    "closed_count": 65,
    "duplicate_alias_count": 11,
    "owner_decision_required_count": 28,
    "reproduced_count": 117,
    "total_strategy_count": 221,
    "uncompleted_count": 28,
}
EXPECTED_INPUT_FILE_SHA256 = "b066de5361d538288de3d37a2c4410c26c329c2c5132ccf1e3d7a798e5168d40"
EXPECTED_INPUT_CANONICAL_SHA256 = "b3edb1fa8cc6c1a7adc1de106567813caa2c4d48528c4d36cee322abdb24f509"
EXPECTED_PARITY_FILE_SHA256 = "a59c8bbc8baa0f73a5a94d709cdf3dcc0b8e2e3bd42588f425f8a6b7014e3f3b"
EXPECTED_PARITY_SHA256 = "892179f9803344e671b4be4b3b2ea9f1dd5cb3bb27dd9061390b95a2fe176d43"
EXPECTED_REPORT_FILE_SHA256 = "e93a2f1e440d0336494cfea23a1a9aa2593384d16122cac333373fb3b398d61b"
EXPECTED_REPORT_SHA256 = "0f1ea5c43ab75ddf4c6604c3e0a21e13db885d0ef38e16c3afb8445f9b9facaa"
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": "9b2e98aa518abf0c4a9b863e5c4ebf27ed3e5d7b3ef26a4180c3cdaf916d4146",
    "biglotto_execution_audit.csv": (
        "3b15a49182ce849cfbc6f583265d4364bd4c6b7bf2d8ecb6a145a91e5029ddc3"
    ),
    "biglotto_full_rankings.csv": (
        "f96ca35327d3abe6bc0911559fc3d6f765578553e3e5c1eb6a10728c9877e6bf"
    ),
    "biglotto_multi_ticket_backtest_report.json": EXPECTED_REPORT_FILE_SHA256,
    "biglotto_official_prize_distributions.csv": (
        "16e1ece0e93a4b3f75327410666125747d36749d377b69b1a9610d0d1ed11fd4"
    ),
    "biglotto_strategy_universe.csv": (
        "662dd44d0d769ed8d121ef46041102ce61a304188ff3ee3230b98c0bb12dcf11"
    ),
    "biglotto_success_metrics.csv": (
        "5a674d13dd283416b404128e90c271dbfdfb65208126f681c1d968569193b449"
    ),
    "biglotto_top10.csv": "a043599a003da327d924f21242fefe2c5c2e4bf31387553dec019588314c056b",
}
EXPECTED_OK_COUNTS = {
    method_id: 2149 - MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE52_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE52_METHODS
}
EXPECTED_CLOSED_COUNTS = {
    method_id: MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE52_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE52_METHODS
}


class EvidenceBuildError(ValueError):
    """Wave-52 evidence inputs violate the frozen contract."""


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
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE52_METHODS:
            continue
        typed_method_id = cast(str, method_id)
        if (
            row.get("source_commit") != FROZEN_SOURCE_COMMIT
            or row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE52_METHOD[typed_method_id]
            or not isinstance(row.get("strategy_id"), str)
        ):
            raise EvidenceBuildError(f"wave-52 catalog row changed: {method_id}")
        by_method[typed_method_id] = cast(str, row["strategy_id"])
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE52_METHODS):
        raise EvidenceBuildError("wave-52 catalog method set changed")
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
        or parity.get("native_ticket_case_count") != 3952
        or parity.get("exact_alias_candidates") != []
        or parity.get("cross_wave_exact_alias_candidates") != []
    ):
        raise EvidenceBuildError("wave-52 parity identity changed")


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
        raise EvidenceBuildError("wave-52 full input identity changed")
    provenance = document.get("source_provenance")
    if not isinstance(provenance, dict):
        raise EvidenceBuildError("wave-52 source provenance changed")
    typed_provenance = cast(dict[str, Any], provenance)
    physical_database_sha256 = typed_provenance.get("database_sha256_before")
    if (
        typed_provenance.get("context_policy") != CONTEXT_POLICY
        or typed_provenance.get("source_native_protocol") != SOURCE_NATIVE_WAVE52_PROTOCOL
        or typed_provenance.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or typed_provenance.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or typed_provenance.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or typed_provenance.get("logical_dataset_sha256") != PINNED_DATASET_SHA256
        or typed_provenance.get("logical_history_anchor")
        != "CHECKSUMMED_WAVE52_FULL_PREFIX_CONTEXT_LEDGER"
        or typed_provenance.get("database_sha256_after") != physical_database_sha256
        or type(physical_database_sha256) is not str
        or typed_provenance.get("execution_status_counts")
        != {"CLOSED_INSUFFICIENT_HISTORY": 2331, "OK": 1967}
    ):
        raise EvidenceBuildError("wave-52 source provenance identity changed")
    method_by_strategy_id = {
        strategy_id_by_method[method_id]: method_id
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE52_METHODS
    }
    executions = cast(list[object], document["executions"])
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-52 execution row changed")
        row = cast(dict[str, Any], candidate)
        if row.get("strategy_id") not in method_by_strategy_id:
            raise EvidenceBuildError("wave-52 execution leaves the method set")
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
        or len(cast(list[object], report.get("metrics", []))) != 256
        or len(cast(list[object], report.get("official_prize_distributions", []))) != 32
        or len(cast(list[object], report.get("rankings", []))) != 28288
    ):
        raise EvidenceBuildError("wave-52 report identity changed")
    actual_checksums = {
        name: hashlib.sha256(path.parent.joinpath(name).read_bytes()).hexdigest()
        for name in EXPECTED_REPORT_CHECKSUMS
    }
    if actual_checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("wave-52 report checksums changed")


def build_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Return compact, checksummed evidence for two backtested rows."""

    strategy_id_by_method = _validate_catalog(catalog_path)
    _validate_parity(parity_path)
    executions, physical_database_sha256 = _validate_input(
        input_path,
        strategy_id_by_method=strategy_id_by_method,
    )
    _validate_report(report_path)
    method_by_strategy_id = {
        strategy_id_by_method[method_id]: method_id
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE52_METHODS
    }
    by_method: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in executions:
        by_method[method_by_strategy_id[cast(str, row["strategy_id"])]].append(row)
    strategies: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE52_METHODS:
        rows = by_method[method_id]
        ok = [row for row in rows if row.get("status") == "OK"]
        closed = [
            row for row in rows if row.get("status") == "CLOSED_INSUFFICIENT_HISTORY"
        ]
        expected_ok = EXPECTED_OK_COUNTS[method_id]
        expected_closed = EXPECTED_CLOSED_COUNTS[method_id]
        if len(ok) != expected_ok or len(closed) != expected_closed:
            raise EvidenceBuildError(f"wave-52 execution counts changed: {method_id}")
        native_metadata = [
            cast(dict[str, Any], row["native_generation"]) for row in ok
        ]
        if {
            cast(str, metadata.get("random_protocol"))
            for metadata in native_metadata
        } != {RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE52_METHOD[method_id]}:
            raise EvidenceBuildError(f"wave-52 random protocol changed: {method_id}")
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
                    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE52_METHOD[
                        method_id
                    ]
                ),
                "legacy_method_id": method_id,
                "minimum_history_draws": (
                    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE52_METHOD[method_id]
                ),
                "minimum_history_rationale": (
                    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE52_METHOD[
                        method_id
                    ]
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
                "random_protocol": (
                    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE52_METHOD[method_id]
                ),
                "source_candidate_k_values": list(
                    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE52_METHOD[
                        method_id
                    ]
                ),
                "source_configuration_count": (
                    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE52_METHOD[
                        method_id
                    ]
                ),
                "source_configuration_count_distribution": _distribution(
                    [row.get("combination_count") for row in ok]
                ),
                "source_configuration_members": list(
                    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE52_METHOD[
                        method_id
                    ]
                ),
                "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE52_METHOD[method_id]
                ),
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
        "source_native_protocol": SOURCE_NATIVE_WAVE52_PROTOCOL,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "strategies": strategies,
        "target_draw_count": 2149,
    }
    document["evidence_sha256"] = hashlib.sha256(
        _canonical_bytes(document)
    ).hexdigest()
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
