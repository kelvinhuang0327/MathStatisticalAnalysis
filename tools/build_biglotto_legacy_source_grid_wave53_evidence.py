#!/usr/bin/env python3
"""Build compact evidence for the wave-53 source-grid dispositions."""

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
from lottolab.application.legacy_source_grid_native_portfolios_wave53 import (
    CONTEXT_POLICY,
    FROZEN_SOURCE_COMMIT,
    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE53_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE53_METHOD,
    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE53_METHOD,
    PINNED_DATASET_SHA256,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE53_METHOD,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE53_METHOD,
    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE53_METHOD,
    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE53_METHOD,
    SOURCE_NATIVE_WAVE53_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE53_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE53_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import CONSTRUCTOR_IDENTIFIER
from lottolab.infrastructure.legacy_source_grid_native_batch_import_wave53 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_NATIVE_WAVE53_EVIDENCE_V1"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE53_PARITY_V1"
BASE_CATALOG_SHA256 = "92c8c4cf9967950b07f8188f0d7fa2cbc87d595bbc643e66ff2fbfe1edf5a1f8"
BASE_CATALOG_FILE_SHA256 = "2b6e20ee56cb4707aa8a0cbb7a7c296394e4cfd50bd4026910c4eebd3c6e6daf"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 117,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 28,
}
EXPECTED_FINAL_PROGRESS = {
    "backtested_count": 119,
    "closed_count": 65,
    "duplicate_alias_count": 11,
    "owner_decision_required_count": 26,
    "reproduced_count": 119,
    "total_strategy_count": 221,
    "uncompleted_count": 26,
}
EXPECTED_INPUT_FILE_SHA256 = "308b239f549394fa4d17585dafe8cc2f991e2ac3ef0d90fc059b511533d36601"
EXPECTED_INPUT_CANONICAL_SHA256 = "36fe88bc9a89056620dac3dcf205a328969335f3252c952df3e7809f027ae4f5"
EXPECTED_PARITY_FILE_SHA256 = "7415ebf9a5b6663bd5b0ce0b0e6a90b8eafdc82f52263781a344809dc8d015b5"
EXPECTED_PARITY_SHA256 = "6373c2d0979b3b50affec5db407fe57efbe0515ac5cdecf28bfa3a6dbe39620f"
EXPECTED_REPORT_FILE_SHA256 = "81420b851f33bb1555dd6044aa670cca297a6dd08ba1355d3b00368758dd5a16"
EXPECTED_REPORT_SHA256 = "735b4b7c05b7166237283ed5c60cc60c4038e50b16ac005585e95dcd7da0b01e"
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": "b0911cd705a03ce6099863915b3ff1f4eb3589075e1a99b6291ad14724dcc7c8",
    "biglotto_execution_audit.csv": (
        "c9d81d3d8fa72ef39a6b52dc30b2ba85d8c02fbf988230e1e81f7b810df34f0f"
    ),
    "biglotto_full_rankings.csv": (
        "c54b180934cf5e09325945e7b428bcbbfb34ed3cb7a5dbf37599d69475c86f83"
    ),
    "biglotto_multi_ticket_backtest_report.json": EXPECTED_REPORT_FILE_SHA256,
    "biglotto_official_prize_distributions.csv": (
        "ee6982e85413a8b3d5d8c9baf8ac201a934eafe5d03d37aab8a02e053cebdb84"
    ),
    "biglotto_strategy_universe.csv": (
        "a3f372231a965c02f1f676af80265aad5991965d872f34ca5a31ae490199c626"
    ),
    "biglotto_success_metrics.csv": (
        "4437e3ca4756d5bcb87ad5e20f9e1f31bb205003a2137bae22edec50e1d725c5"
    ),
    "biglotto_top10.csv": "b7a12487d00610aa5926ef2e824a32e82d66aee7c9a8cab0ce1f4f5975366f3e",
}
EXPECTED_OK_COUNTS = {
    method_id: 2149 - MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE53_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE53_METHODS
}
EXPECTED_CLOSED_COUNTS = {
    method_id: MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE53_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE53_METHODS
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
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE53_METHODS:
            continue
        typed_method_id = cast(str, method_id)
        if (
            row.get("source_commit") != FROZEN_SOURCE_COMMIT
            or row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE53_METHOD[typed_method_id]
            or not isinstance(row.get("strategy_id"), str)
        ):
            raise EvidenceBuildError(f"wave-53 catalog row changed: {method_id}")
        by_method[typed_method_id] = cast(str, row["strategy_id"])
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE53_METHODS):
        raise EvidenceBuildError("wave-53 catalog method set changed")
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
        or parity.get("native_ticket_case_count") != 34780
        or parity.get("exact_alias_candidates") != []
        or parity.get("cross_wave_exact_alias_candidates") != []
    ):
        raise EvidenceBuildError("wave-53 parity identity changed")


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
        raise EvidenceBuildError("wave-53 full input identity changed")
    provenance = document.get("source_provenance")
    if not isinstance(provenance, dict):
        raise EvidenceBuildError("wave-53 source provenance changed")
    typed_provenance = cast(dict[str, Any], provenance)
    physical_database_sha256 = typed_provenance.get("database_sha256_before")
    if (
        typed_provenance.get("context_policy") != CONTEXT_POLICY
        or typed_provenance.get("source_native_protocol") != SOURCE_NATIVE_WAVE53_PROTOCOL
        or typed_provenance.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or typed_provenance.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or typed_provenance.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or typed_provenance.get("logical_dataset_sha256") != PINNED_DATASET_SHA256
        or typed_provenance.get("logical_history_anchor")
        != "CHECKSUMMED_WAVE53_FULL_PREFIX_CONTEXT_LEDGER"
        or typed_provenance.get("database_sha256_after") != physical_database_sha256
        or type(physical_database_sha256) is not str
        or typed_provenance.get("execution_status_counts")
        != {"CLOSED_INSUFFICIENT_HISTORY": 700, "OK": 3598}
    ):
        raise EvidenceBuildError("wave-53 source provenance identity changed")
    method_by_strategy_id = {
        strategy_id_by_method[method_id]: method_id
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE53_METHODS
    }
    executions = cast(list[object], document["executions"])
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-53 execution row changed")
        row = cast(dict[str, Any], candidate)
        if row.get("strategy_id") not in method_by_strategy_id:
            raise EvidenceBuildError("wave-53 execution leaves the method set")
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
        raise EvidenceBuildError("wave-53 report identity changed")
    actual_checksums = {
        name: hashlib.sha256(path.parent.joinpath(name).read_bytes()).hexdigest()
        for name in EXPECTED_REPORT_CHECKSUMS
    }
    if actual_checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("wave-53 report checksums changed")


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
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE53_METHODS
    }
    by_method: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in executions:
        by_method[method_by_strategy_id[cast(str, row["strategy_id"])]].append(row)
    strategies: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE53_METHODS:
        rows = by_method[method_id]
        ok = [row for row in rows if row.get("status") == "OK"]
        closed = [
            row for row in rows if row.get("status") == "CLOSED_INSUFFICIENT_HISTORY"
        ]
        expected_ok = EXPECTED_OK_COUNTS[method_id]
        expected_closed = EXPECTED_CLOSED_COUNTS[method_id]
        if len(ok) != expected_ok or len(closed) != expected_closed:
            raise EvidenceBuildError(f"wave-53 execution counts changed: {method_id}")
        native_metadata = [
            cast(dict[str, Any], row["native_generation"]) for row in ok
        ]
        if {
            cast(str, metadata.get("random_protocol"))
            for metadata in native_metadata
        } != {RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE53_METHOD[method_id]}:
            raise EvidenceBuildError(f"wave-53 random protocol changed: {method_id}")
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
                    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE53_METHOD[
                        method_id
                    ]
                ),
                "legacy_method_id": method_id,
                "minimum_history_draws": (
                    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE53_METHOD[method_id]
                ),
                "minimum_history_rationale": (
                    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE53_METHOD[
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
                    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE53_METHOD[method_id]
                ),
                "source_candidate_k_values": list(
                    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE53_METHOD[
                        method_id
                    ]
                ),
                "source_configuration_count": (
                    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE53_METHOD[
                        method_id
                    ]
                ),
                "source_configuration_count_distribution": _distribution(
                    [row.get("combination_count") for row in ok]
                ),
                "source_configuration_members": list(
                    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE53_METHOD[
                        method_id
                    ]
                ),
                "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE53_METHOD[method_id]
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
        "source_native_protocol": SOURCE_NATIVE_WAVE53_PROTOCOL,
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
