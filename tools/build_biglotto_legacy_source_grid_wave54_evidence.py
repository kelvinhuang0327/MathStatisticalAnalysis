#!/usr/bin/env python3
"""Build compact evidence for the wave-54 source-grid dispositions."""

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
from lottolab.application.legacy_source_grid_native_portfolios_wave54 import (
    CONTEXT_POLICY,
    FROZEN_SOURCE_COMMIT,
    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE54_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE54_METHOD,
    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE54_METHOD,
    PINNED_DATASET_SHA256,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE54_METHOD,
    RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE54_METHOD,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE54_METHOD,
    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE54_METHOD,
    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE54_METHOD,
    SOURCE_NATIVE_WAVE54_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE54_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import CONSTRUCTOR_IDENTIFIER
from lottolab.infrastructure.legacy_source_grid_native_batch_import_wave54 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_NATIVE_WAVE54_EVIDENCE_V1"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE54_PARITY_V1"
BASE_CATALOG_SHA256 = "f7203b3a3951f56f09d8f635998697d8903aa3d345854626e9ac44be7916a1aa"
BASE_CATALOG_FILE_SHA256 = "6c2f6f1addcf3545aad655957331c79edceba0695009c8db861bdb0479862224"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 119,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 26,
}
EXPECTED_FINAL_PROGRESS = {
    "backtested_count": 121,
    "closed_count": 65,
    "duplicate_alias_count": 11,
    "owner_decision_required_count": 24,
    "reproduced_count": 121,
    "total_strategy_count": 221,
    "uncompleted_count": 24,
}
EXPECTED_INPUT_FILE_SHA256 = "41024ab48c9cd71f969b3ef5d4359cd9b249fd91d3e842ea346146a997fa30d3"
EXPECTED_INPUT_CANONICAL_SHA256 = "d62c108821e05b69446b960b478c53e98b1871353680a151cfd4523883a8c7a3"
EXPECTED_PARITY_FILE_SHA256 = "7e6aadbd00a2116a801b999d49aa0c3d06c538a19cb5ba0901c659b296be64fc"
EXPECTED_PARITY_SHA256 = "50ef49fb13189c7c776a22e08057d8439ab362540549d146720b18afab310fa6"
EXPECTED_REPORT_FILE_SHA256 = "e1f0a19fccb48aaa439419862f210d853e0c10a21b5d2d70c1dcf890745631eb"
EXPECTED_REPORT_SHA256 = "a8508a240024bc0faff6f343233449577a8abe606acca5d3199c71e00366bf15"
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": "eff7932e2304e68c6522105ff7b9fe199a5548bd3db42916e80be0b01f919954",
    "biglotto_execution_audit.csv": (
        "5dc69545955fdf548ee1133687b76a2b8c86f381046a1c83c5631b4305187c47"
    ),
    "biglotto_full_rankings.csv": (
        "fadaf6a103e10c3ad380c46fccfdbfb0ed0c6a1b8fb56f2f285711f53bf9cbe6"
    ),
    "biglotto_multi_ticket_backtest_report.json": EXPECTED_REPORT_FILE_SHA256,
    "biglotto_official_prize_distributions.csv": (
        "c5755ea62cd0aab0b2276c0fd32f39b8d6588f676dbf7c83af7705ec8f906f0b"
    ),
    "biglotto_strategy_universe.csv": (
        "8cf551381df99dbfd030162844cabe228e6a8ded28a811266594601bd77948f3"
    ),
    "biglotto_success_metrics.csv": (
        "ba4d9ac4f71b77b18e99aa43144df0f581a1a2c5c148d484500b1e049941f6ea"
    ),
    "biglotto_top10.csv": "8d72789185b2035f68e5fea7693475d190127d4368b4a98d72aaf1ada8abd153",
}
EXPECTED_OK_COUNTS = {
    method_id: 2149 - MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE54_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS
}
EXPECTED_CLOSED_COUNTS = {
    method_id: MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE54_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS
}


class EvidenceBuildError(ValueError):
    """Wave-54 evidence inputs violate the frozen contract."""


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
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS:
            continue
        typed_method_id = cast(str, method_id)
        if (
            row.get("source_commit") != FROZEN_SOURCE_COMMIT
            or row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE54_METHOD[typed_method_id]
            or not isinstance(row.get("strategy_id"), str)
        ):
            raise EvidenceBuildError(f"wave-54 catalog row changed: {method_id}")
        by_method[typed_method_id] = cast(str, row["strategy_id"])
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS):
        raise EvidenceBuildError("wave-54 catalog method set changed")
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
        or parity.get("native_ticket_case_count") != 8196
        or parity.get("exact_alias_candidates") != []
        or parity.get("cross_wave_exact_alias_candidates") != []
    ):
        raise EvidenceBuildError("wave-54 parity identity changed")


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
        raise EvidenceBuildError("wave-54 full input identity changed")
    provenance = document.get("source_provenance")
    if not isinstance(provenance, dict):
        raise EvidenceBuildError("wave-54 source provenance changed")
    typed_provenance = cast(dict[str, Any], provenance)
    physical_database_sha256 = typed_provenance.get("database_sha256_before")
    if (
        typed_provenance.get("context_policy") != CONTEXT_POLICY
        or typed_provenance.get("source_native_protocol") != SOURCE_NATIVE_WAVE54_PROTOCOL
        or typed_provenance.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or typed_provenance.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or typed_provenance.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or typed_provenance.get("logical_dataset_sha256") != PINNED_DATASET_SHA256
        or typed_provenance.get("logical_history_anchor")
        != "CHECKSUMMED_WAVE54_FULL_PREFIX_CONTEXT_LEDGER"
        or typed_provenance.get("database_sha256_after") != physical_database_sha256
        or type(physical_database_sha256) is not str
        or typed_provenance.get("execution_status_counts")
        != {"CLOSED_INSUFFICIENT_HISTORY": 200, "OK": 4098}
    ):
        raise EvidenceBuildError("wave-54 source provenance identity changed")
    method_by_strategy_id = {
        strategy_id_by_method[method_id]: method_id
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS
    }
    executions = cast(list[object], document["executions"])
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-54 execution row changed")
        row = cast(dict[str, Any], candidate)
        if row.get("strategy_id") not in method_by_strategy_id:
            raise EvidenceBuildError("wave-54 execution leaves the method set")
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
        raise EvidenceBuildError("wave-54 report identity changed")
    actual_checksums = {
        name: hashlib.sha256(path.parent.joinpath(name).read_bytes()).hexdigest()
        for name in EXPECTED_REPORT_CHECKSUMS
    }
    if actual_checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("wave-54 report checksums changed")


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
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS
    }
    by_method: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in executions:
        by_method[method_by_strategy_id[cast(str, row["strategy_id"])]].append(row)
    strategies: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE54_METHODS:
        rows = by_method[method_id]
        ok = [row for row in rows if row.get("status") == "OK"]
        closed = [
            row for row in rows if row.get("status") == "CLOSED_INSUFFICIENT_HISTORY"
        ]
        expected_ok = EXPECTED_OK_COUNTS[method_id]
        expected_closed = EXPECTED_CLOSED_COUNTS[method_id]
        if len(ok) != expected_ok or len(closed) != expected_closed:
            raise EvidenceBuildError(f"wave-54 execution counts changed: {method_id}")
        native_metadata = [
            cast(dict[str, Any], row["native_generation"]) for row in ok
        ]
        if (
            {
                cast(str, metadata.get("random_protocol"))
                for metadata in native_metadata
            }
            != {RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE54_METHOD[method_id]}
            or {
                metadata.get("randomness_used") for metadata in native_metadata
            }
            != {RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE54_METHOD[method_id]}
            or {
                metadata.get("randomness_reproduction")
                for metadata in native_metadata
            }
            != {"EXACT_FROZEN_RUNTIME_LEDGER"}
        ):
            raise EvidenceBuildError(f"wave-54 random protocol changed: {method_id}")
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
                    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE54_METHOD[
                        method_id
                    ]
                ),
                "legacy_method_id": method_id,
                "minimum_history_draws": (
                    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE54_METHOD[method_id]
                ),
                "minimum_history_rationale": (
                    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE54_METHOD[
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
                    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE54_METHOD[method_id]
                ),
                "randomness_reproduction": "EXACT_FROZEN_RUNTIME_LEDGER",
                "randomness_used": (
                    RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE54_METHOD[method_id]
                ),
                "source_candidate_k_values": list(
                    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE54_METHOD[
                        method_id
                    ]
                ),
                "source_configuration_count": (
                    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE54_METHOD[
                        method_id
                    ]
                ),
                "source_configuration_count_distribution": _distribution(
                    [row.get("combination_count") for row in ok]
                ),
                "source_configuration_members": list(
                    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE54_METHOD[
                        method_id
                    ]
                ),
                "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE54_METHOD[method_id]
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
        "source_native_protocol": SOURCE_NATIVE_WAVE54_PROTOCOL,
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
