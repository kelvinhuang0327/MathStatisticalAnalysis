#!/usr/bin/env python3
"""Build compact evidence for the wave-46 source-grid dispositions."""

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
from lottolab.application.legacy_source_grid_native_portfolios_wave46 import (
    CONTEXT_POLICY,
    FROZEN_SOURCE_COMMIT,
    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE46_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE46_METHOD,
    MODEL_CANDIDATE_K,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD,
    OPTIMAL_MATRIX_METHOD_ID,
    PREDICTABILITY_ALIAS_METHOD_ID,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE46_METHOD,
    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD,
    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE46_METHOD,
    SOURCE_NATIVE_WAVE46_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_grid_native_batch_import_wave46 import (
    CLOSED_REASON,
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_NATIVE_WAVE46_EVIDENCE_V1"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE46_PARITY_V1"
BASE_CATALOG_SHA256 = "a13329f3bbe134d6825f7c14d9476b98e9ae4864588cc5f83ac94be17264a2c3"
BASE_CATALOG_FILE_SHA256 = "d6c7a0dbbd6430f5d8c74c1d9b93de0ae2cc1bc81806936c0b5156ea52b84bf2"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 87,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 8,
    "OWNER_DECISION_REQUIRED": 61,
}
EXPECTED_PROGRESS = {
    "backtested_count": 99,
    "closed_count": 65,
    "duplicate_alias_count": 9,
    "owner_decision_required_count": 48,
    "reproduced_count": 99,
    "total_strategy_count": 221,
    "uncompleted_count": 48,
}
EXPECTED_DATABASE_SHA256 = "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
EXPECTED_INPUT_FILE_SHA256 = "cc9232c049d57689b4d63cbb8f57db13e5a2b72b77833f9e7a007b363956ad26"
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "00f3f0b628971b2a0b9ce24816dcb686619aa868354183bcd868f523eed5954e"
)
EXPECTED_PARITY_FILE_SHA256 = "436afe0a07f8cbfeef54dc61ace3a8a47b5766f9ab44c8dc77bd01f700532928"
EXPECTED_PARITY_SHA256 = "a2aead3767df485be996ad99616024776fba760643f722630a17d94479f0e33e"
EXPECTED_REPORT_FILE_SHA256 = "3809474d978486d832e4f02b4e4f5ea1d0c371e07ec43f3038782e82b1bcac43"
EXPECTED_REPORT_SHA256 = "80351893fb4f3cfc1a83d48bbf91edf341fe409ed32d1e09dad007dbc0b4e383"
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": "be69373bff1ac7df69911cc6c47b3f0dde3a8342f4cc3b3a505cb16b410cd591",
    "biglotto_execution_audit.csv": (
        "419b100ed30aac9d83512c9ae37197c38a17903503e14ae595c5823b065f318f"
    ),
    "biglotto_full_rankings.csv": (
        "a80e33cf8ffa30a753df374ea767cd353dbadd935c075805d01736bd95e55730"
    ),
    "biglotto_multi_ticket_backtest_report.json": EXPECTED_REPORT_FILE_SHA256,
    "biglotto_official_prize_distributions.csv": (
        "73f4703af1a0741af07d729b9aa560b6c23e7a2ff714e75f57407b7199e7474a"
    ),
    "biglotto_strategy_universe.csv": (
        "125046860c11854a30069fcfe8ef638ac4adbea1cde348760b6e361b33b2165b"
    ),
    "biglotto_success_metrics.csv": (
        "5f3444fea430a4070106192213c04163ef28950e0ccfd5de88e8c9b9979760e0"
    ),
    "biglotto_top10.csv": "209d2b0fa262eeba5a6e1229d966782c2acd3f2839e45cb8ac36bb3b56e52bc6",
}
EXPECTED_OK_COUNTS = {
    method_id: 2149 - minimum
    for method_id, minimum in MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE46_METHOD.items()
    if method_id in SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS
}
EXPECTED_CLOSED_COUNTS = {
    method_id: minimum
    for method_id, minimum in MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE46_METHOD.items()
    if method_id in SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS
}
EXPECTED_CANONICALIZATION_COUNTS = {
    method_id: 5920 if method_id == "tools/backtest_sum_constraint.py" else 0
    for method_id in SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD
}


class EvidenceBuildError(ValueError):
    """Wave-46 evidence inputs violate the frozen contract."""


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
    relevant = {
        *SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS,
        PREDICTABILITY_ALIAS_METHOD_ID,
    }
    for candidate in cast(list[object], catalog.get("records", [])):
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id not in relevant:
            continue
        typed_method_id = cast(str, method_id)
        if (
            row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD[typed_method_id]
            or type(row.get("strategy_id")) is not str
        ):
            raise EvidenceBuildError(f"wave-46 catalog row changed: {method_id}")
        by_method[typed_method_id] = cast(str, row["strategy_id"])
    if set(by_method) != relevant:
        raise EvidenceBuildError("wave-46 catalog method set changed")
    return by_method


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version") != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or parity.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or parity.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or parity.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or parity.get("intra_ticket_canonicalization_count_by_method")
        != EXPECTED_CANONICALIZATION_COUNTS
        or parity.get("exact_alias_candidates")
        != [
            {
                "left_method_id": OPTIMAL_MATRIX_METHOD_ID,
                "output_mismatch_count": 0,
                "overlapping_causal_output_case_count": 1949,
                "right_method_id": PREDICTABILITY_ALIAS_METHOD_ID,
            }
        ]
    ):
        raise EvidenceBuildError("wave-46 parity identity changed")
    return parity


def _distribution(values: list[object]) -> dict[str, int]:
    counts = Counter(
        "null"
        if value is None
        else str(value).lower()
        if isinstance(value, bool)
        else str(value)
        for value in values
    )
    return dict(sorted(counts.items()))


def _validate_input(
    path: Path,
    *,
    strategy_id_by_method: dict[str, str],
) -> list[dict[str, Any]]:
    document, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_INPUT_FILE_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest()
        != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or document.get("dataset_version") != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", []))) != 2149
        or len(cast(list[object], document.get("executions", []))) != 25788
    ):
        raise EvidenceBuildError("wave-46 full input identity changed")
    provenance = document.get("source_provenance")
    if not isinstance(provenance, dict):
        raise EvidenceBuildError("wave-46 source provenance changed")
    typed_provenance = cast(dict[str, Any], provenance)
    if (
        typed_provenance.get("context_policy") != CONTEXT_POLICY
        or typed_provenance.get("source_native_protocol")
        != SOURCE_NATIVE_WAVE46_PROTOCOL
        or typed_provenance.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
        or typed_provenance.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or typed_provenance.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or typed_provenance.get("execution_status_counts")
        != {"CLOSED_INSUFFICIENT_HISTORY": 2701, "OK": 23087}
    ):
        raise EvidenceBuildError("wave-46 source provenance identity changed")
    method_by_strategy_id = {
        strategy_id: method_id
        for method_id, strategy_id in strategy_id_by_method.items()
        if method_id in SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS
    }
    rows_by_method: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in cast(list[object], document.get("executions", [])):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-46 execution changed")
        row = cast(dict[str, Any], candidate)
        method_id = method_by_strategy_id.get(cast(str, row.get("strategy_id")))
        if method_id is None:
            raise EvidenceBuildError("wave-46 execution strategy identity changed")
        rows_by_method[method_id].append(row)
    strategies: list[dict[str, Any]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS:
        rows = rows_by_method[method_id]
        expected_ok = EXPECTED_OK_COUNTS[method_id]
        expected_closed = EXPECTED_CLOSED_COUNTS[method_id]
        status_counts = Counter(cast(str, row.get("status")) for row in rows)
        if status_counts != {
            "OK": expected_ok,
            "CLOSED_INSUFFICIENT_HISTORY": expected_closed,
        }:
            raise EvidenceBuildError(f"wave-46 status counts changed: {method_id}")
        ok = [row for row in rows if row.get("status") == "OK"]
        closed = [
            row
            for row in rows
            if row.get("status") == "CLOSED_INSUFFICIENT_HISTORY"
        ]
        if any(row.get("reason_code") != CLOSED_REASON for row in closed):
            raise EvidenceBuildError(f"wave-46 closure changed: {method_id}")
        native_generation = [
            cast(dict[str, Any], row.get("native_generation"))
            for row in ok
            if isinstance(row.get("native_generation"), dict)
        ]
        expected_native_count = (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]
        )
        expected_configuration_count = (
            SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]
        )
        if (
            len(native_generation) != len(ok)
            or any(row.get("candidate_k") != MODEL_CANDIDATE_K for row in ok)
            or any(
                row.get("combination_count") != expected_configuration_count
                or row.get("portfolio_ticket_count") != 20
                or row.get("portfolio_derivation") != CONSTRUCTOR_IDENTIFIER
                or len(cast(list[object], row.get("native_tickets"))) != expected_native_count
                or len(cast(list[object], row.get("ordered_portfolio"))) != 20
                for row in ok
            )
            or any(
                generation.get("candidate_k") is not None
                or generation.get("combination_count") is not None
                or generation.get("source_method_combination_count")
                != expected_configuration_count
                or generation.get("source_candidate_k_values")
                != list(
                    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE46_METHOD[
                        method_id
                    ]
                )
                or generation.get("ledger_file_sha256") != LEDGER_FILE_SHA256
                or generation.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
                for generation in native_generation
            )
        ):
            raise EvidenceBuildError(f"wave-46 execution semantics changed: {method_id}")
        strategies.append(
            {
                "candidate_k_distribution": _distribution(
                    [row.get("candidate_k") for row in ok]
                ),
                "closed_execution_count": len(closed),
                "execution_status_counts": dict(sorted(status_counts.items())),
                "intra_ticket_order_semantics": (
                    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE46_METHOD[
                        method_id
                    ]
                ),
                "legacy_method_id": method_id,
                "minimum_history_draws": (
                    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]
                ),
                "native_duplicate_ticket_count_distribution": _distribution(
                    [
                        generation.get("native_duplicate_ticket_count")
                        for generation in native_generation
                    ]
                ),
                "native_ticket_count_distribution": _distribution(
                    [row.get("native_ticket_count") for row in ok]
                ),
                "ok_execution_count": len(ok),
                "source_candidate_k_values": list(
                    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE46_METHOD[
                        method_id
                    ]
                ),
                "source_configuration_count": expected_configuration_count,
                "source_configuration_count_distribution": _distribution(
                    [row.get("combination_count") for row in ok]
                ),
                "source_configuration_members": list(
                    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE46_METHOD[
                        method_id
                    ]
                ),
                "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]
                ),
                "strategy_id": strategy_id_by_method[method_id],
            }
        )
    return strategies


def _validate_report(
    path: Path,
    *,
    strategy_ids: set[str],
) -> tuple[dict[str, Any], dict[str, str]]:
    report, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_REPORT_FILE_SHA256
        or report.get("report_sha256") != EXPECTED_REPORT_SHA256
        or report.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version") != BACKTEST_POLICY_VERSION
        or report.get("input_raw_sha256") != EXPECTED_INPUT_FILE_SHA256
        or report.get("input_canonical_sha256") != EXPECTED_INPUT_CANONICAL_SHA256
        or report.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or report.get("target_draw_count") != 2149
        or report.get("progress")
        != {
            "backtested_count": 99,
            "closed_count": 65,
            "duplicate_alias_count": 8,
            "owner_decision_required_count": 49,
            "reproduced_count": 99,
            "total_strategy_count": 221,
            "uncompleted_count": 49,
        }
        or report.get("research_disclaimer") != RESEARCH_DISCLAIMER
    ):
        raise EvidenceBuildError("wave-46 report identity changed")
    metrics = cast(list[dict[str, Any]], report.get("metrics", []))
    prizes = cast(
        list[dict[str, Any]],
        report.get("official_prize_distributions", []),
    )
    rankings = cast(list[object], report.get("rankings", []))
    if (
        len(metrics) != 1536
        or len(prizes) != 192
        or len(rankings) != 28288
        or Counter(cast(str, row.get("strategy_id")) for row in metrics)
        != Counter({strategy_id: 128 for strategy_id in strategy_ids})
        or Counter(cast(str, row.get("strategy_id")) for row in prizes)
        != Counter({strategy_id: 16 for strategy_id in strategy_ids})
        or {cast(int, row.get("prefix_count")) for row in metrics}
        != {5, 10, 15, 20}
        or {cast(str, row.get("window")) for row in metrics}
        != {"FULL", "RECENT_750", "RECENT_300", "RECENT_50"}
        or len({cast(str, row.get("criterion")) for row in metrics}) != 8
        or any(
            row.get("exact_random_baseline_probability") is None
            or row.get("random_baseline_rate_difference") is None
            for row in metrics
        )
    ):
        raise EvidenceBuildError(
            "wave-46 metric, prize, or ranking coverage changed"
        )
    checksums = {
        file_path.name: hashlib.sha256(file_path.read_bytes()).hexdigest()
        for file_path in path.parent.iterdir()
        if file_path.is_file()
    }
    if checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("wave-46 report checksums changed")
    return report, checksums


def build_evidence(
    *,
    base_catalog_path: Path,
    parity_path: Path,
    input_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate all artifacts and return the compact wave-46 proof."""

    strategy_id_by_method = _validate_catalog(base_catalog_path)
    parity = _validate_parity(parity_path)
    strategies = _validate_input(
        input_path,
        strategy_id_by_method=strategy_id_by_method,
    )
    report, report_checksums = _validate_report(
        report_path,
        strategy_ids={
            strategy_id_by_method[method_id]
            for method_id in SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS
        },
    )
    document: dict[str, object] = {
        "alias_disposition": {
            "alias_method_id": PREDICTABILITY_ALIAS_METHOD_ID,
            "alias_source_sha256": (
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD[
                    PREDICTABILITY_ALIAS_METHOD_ID
                ]
            ),
            "alias_strategy_id": strategy_id_by_method[
                PREDICTABILITY_ALIAS_METHOD_ID
            ],
            "canonical_method_id": OPTIMAL_MATRIX_METHOD_ID,
            "canonical_strategy_id": strategy_id_by_method[
                OPTIMAL_MATRIX_METHOD_ID
            ],
            "output_mismatch_count": 0,
            "overlapping_causal_output_case_count": 1949,
            "status": "DUPLICATE_ALIAS",
        },
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "context_policy": CONTEXT_POLICY,
        "dataset_sha256": EXPECTED_DATABASE_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "final_progress": EXPECTED_PROGRESS,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "input_canonical_sha256": EXPECTED_INPUT_CANONICAL_SHA256,
        "input_file_sha256": EXPECTED_INPUT_FILE_SHA256,
        "ledger_content_sha256": LEDGER_CONTENT_SHA256,
        "ledger_file_sha256": LEDGER_FILE_SHA256,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "parity_file_sha256": EXPECTED_PARITY_FILE_SHA256,
        "parity_sha256": parity["parity_sha256"],
        "report_checksums": report_checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": report["report_sha256"],
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_native_protocol": SOURCE_NATIVE_WAVE46_PROTOCOL,
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
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--parity", required=True, type=Path)
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--report-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output_file}")
    document = build_evidence(
        base_catalog_path=args.base_catalog,
        parity_path=args.parity,
        input_path=args.input_file,
        report_path=args.report_file,
    )
    payload = _canonical_bytes(document) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": document["evidence_sha256"],
                "output_file": str(args.output_file),
                "physical_file_sha256": hashlib.sha256(payload).hexdigest(),
                "strategy_disposition_count": 13,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
