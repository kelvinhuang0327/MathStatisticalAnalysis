#!/usr/bin/env python3
"""Build compact evidence for the wave-47 source-grid dispositions."""

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
from lottolab.application.legacy_source_grid_native_portfolios_wave47 import (
    CONTEXT_POLICY,
    FROZEN_SOURCE_COMMIT,
    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE47_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE47_METHOD,
    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE47_METHOD,
    MODEL_CANDIDATE_K,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD,
    PINNED_DATASET_SHA256,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE47_METHOD,
    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD,
    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE47_METHOD,
    SOURCE_NATIVE_WAVE47_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE47_METHOD,
    STABILITY_ALIAS_METHOD_ID,
    STABILITY_ALIAS_TARGET_METHOD_ID,
    SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_grid_native_batch_import_wave47 import (
    CLOSED_REASON,
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_NATIVE_WAVE47_EVIDENCE_V1"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE47_PARITY_V1"
BASE_CATALOG_SHA256 = "6d744b689e99702c0b2bc5693dbdd091b6aeea881a45c13eb8a90c44aa85089a"
BASE_CATALOG_FILE_SHA256 = "2e175399ff7df9eb80102791522d47d616104992710288d51548d4548633d8a0"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 99,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 9,
    "OWNER_DECISION_REQUIRED": 48,
}
EXPECTED_PRE_OVERLAY_PROGRESS = {
    "backtested_count": 106,
    "closed_count": 65,
    "duplicate_alias_count": 9,
    "owner_decision_required_count": 41,
    "reproduced_count": 106,
    "total_strategy_count": 221,
    "uncompleted_count": 41,
}
EXPECTED_FINAL_PROGRESS = {
    "backtested_count": 106,
    "closed_count": 65,
    "duplicate_alias_count": 10,
    "owner_decision_required_count": 40,
    "reproduced_count": 106,
    "total_strategy_count": 221,
    "uncompleted_count": 40,
}
EXPECTED_INPUT_FILE_SHA256 = "ebfce877aeba18a19a249baf59c08aa74c81b4088585e8d21ae1980cffe21dd9"
EXPECTED_INPUT_CANONICAL_SHA256 = "cc238cd9c932da052bba5e9dd88afdee4d904097580f215dee729f31a1a3f955"
EXPECTED_PARITY_FILE_SHA256 = "d51236920b51a298db3c55181d48b99959cd98c680b5e12838c3f33de44fc497"
EXPECTED_PARITY_SHA256 = "cfc7de53d6bffcbb4070a255c4c5b777590f87e1feff4d1e1ae149c3e52d5983"
EXPECTED_REPORT_FILE_SHA256 = "45632e7d0d1208032b2c5ee95d21936259e6ce2b0591c358a0643566cb451175"
EXPECTED_REPORT_SHA256 = "1a46057c48f86f9f1e5186583fcdcee547551af76ce809eccfeca84a06320971"
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": ("fb271a125e6398e18a632d4cf9b6e3c1faa4bae880cfb92d3177d42ffc096780"),
    "biglotto_execution_audit.csv": (
        "6ee2e1ae7ef022bc2c6f138e7b34d98efbdf5d866738eea8d0609be1eda92435"
    ),
    "biglotto_full_rankings.csv": (
        "ad5d063989847a79f5ebc8a87ee4593183006697abd67b560e28724ce98c5dba"
    ),
    "biglotto_multi_ticket_backtest_report.json": (EXPECTED_REPORT_FILE_SHA256),
    "biglotto_official_prize_distributions.csv": (
        "efa4f35b70703d84f02f12b80912e48413de1b01de60d3fa45bc54c2be7eff78"
    ),
    "biglotto_strategy_universe.csv": (
        "0415c127d486d227b9b6ebaada6ac9a15031763a4971d6f7f57d977256c85015"
    ),
    "biglotto_success_metrics.csv": (
        "e9566dba27b7268b5b7cc12e66280c4c56faada83727d4408079443b0f68f198"
    ),
    "biglotto_top10.csv": ("be48984b37675c1c803d17cb64bda1739d669b4912889789807012d95650d1f6"),
}
EXPECTED_OK_COUNTS = {
    method_id: 2149 - MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
}
EXPECTED_CLOSED_COUNTS = {
    method_id: MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
}


class EvidenceBuildError(ValueError):
    """Wave-47 evidence inputs violate the frozen contract."""


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
        *SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS,
        STABILITY_ALIAS_METHOD_ID,
        STABILITY_ALIAS_TARGET_METHOD_ID,
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
        if (
            row.get("source_commit") != FROZEN_SOURCE_COMMIT
            or type(row.get("strategy_id")) is not str
        ):
            raise EvidenceBuildError(f"wave-47 catalog row changed: {method_id}")
        if typed_method_id == STABILITY_ALIAS_TARGET_METHOD_ID:
            if row.get("reproduction_status") != "BACKTESTED":
                raise EvidenceBuildError("wave-47 canonical alias target changed")
        elif (
            row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE47_METHOD[typed_method_id]
        ):
            raise EvidenceBuildError(f"wave-47 catalog row changed: {method_id}")
        by_method[typed_method_id] = cast(str, row["strategy_id"])
    if set(by_method) != relevant:
        raise EvidenceBuildError("wave-47 catalog method set changed")
    return by_method


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    expected_cross_alias = [
        {
            "left_method_id": STABILITY_ALIAS_METHOD_ID,
            "output_mismatch_count": 0,
            "overlapping_causal_output_case_count": 1649,
            "right_method_id": STABILITY_ALIAS_TARGET_METHOD_ID,
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
        or parity.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or parity.get("native_ticket_case_count") != 59480
        or parity.get("exact_alias_candidates") != []
        or parity.get("cross_wave_exact_alias_candidates") != expected_cross_alias
    ):
        raise EvidenceBuildError("wave-47 parity identity changed")
    return parity


def _validate_input(
    path: Path,
    *,
    strategy_id_by_method: dict[str, str],
) -> tuple[list[dict[str, object]], str]:
    document, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_INPUT_FILE_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest() != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("dataset_version") != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", []))) != 2149
        or len(cast(list[object], document.get("executions", []))) != 15043
    ):
        raise EvidenceBuildError("wave-47 full input identity changed")
    provenance = document.get("source_provenance")
    if not isinstance(provenance, dict):
        raise EvidenceBuildError("wave-47 source provenance changed")
    typed_provenance = cast(dict[str, Any], provenance)
    physical_database_sha256 = typed_provenance.get("database_sha256_before")
    if (
        typed_provenance.get("context_policy") != CONTEXT_POLICY
        or typed_provenance.get("source_native_protocol") != SOURCE_NATIVE_WAVE47_PROTOCOL
        or typed_provenance.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or typed_provenance.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or typed_provenance.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or typed_provenance.get("logical_dataset_sha256") != PINNED_DATASET_SHA256
        or typed_provenance.get("logical_history_anchor")
        != "CHECKSUMMED_WAVE47_FULL_PREFIX_CONTEXT_LEDGER"
        or typed_provenance.get("database_sha256_after") != physical_database_sha256
        or type(physical_database_sha256) is not str
        or typed_provenance.get("execution_status_counts")
        != {"CLOSED_INSUFFICIENT_HISTORY": 3296, "OK": 11747}
    ):
        raise EvidenceBuildError("wave-47 source provenance identity changed")
    method_by_strategy_id = {
        strategy_id: method_id
        for method_id, strategy_id in strategy_id_by_method.items()
        if method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
    }
    rows_by_method: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in cast(list[object], document.get("executions", [])):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-47 execution changed")
        row = cast(dict[str, Any], candidate)
        method_id = method_by_strategy_id.get(cast(str, row.get("strategy_id")))
        if method_id is None:
            raise EvidenceBuildError("wave-47 execution strategy identity changed")
        rows_by_method[method_id].append(row)
    strategies: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS:
        rows = rows_by_method[method_id]
        expected_ok = EXPECTED_OK_COUNTS[method_id]
        expected_closed = EXPECTED_CLOSED_COUNTS[method_id]
        status_counts = Counter(cast(str, row.get("status")) for row in rows)
        if status_counts != {
            "OK": expected_ok,
            "CLOSED_INSUFFICIENT_HISTORY": expected_closed,
        }:
            raise EvidenceBuildError(f"wave-47 status counts changed: {method_id}")
        ok = [row for row in rows if row.get("status") == "OK"]
        closed = [row for row in rows if row.get("status") == "CLOSED_INSUFFICIENT_HISTORY"]
        native_generation = [
            cast(dict[str, Any], row.get("native_generation"))
            for row in ok
            if isinstance(row.get("native_generation"), dict)
        ]
        native_count = NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
        configuration_count = SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
        if (
            len(native_generation) != len(ok)
            or any(row.get("reason_code") != CLOSED_REASON for row in closed)
            or any(
                row.get("candidate_k") != MODEL_CANDIDATE_K
                or row.get("combination_count") != configuration_count
                or row.get("portfolio_ticket_count") != 20
                or row.get("portfolio_derivation") != CONSTRUCTOR_IDENTIFIER
                or len(cast(list[object], row.get("native_tickets", []))) != native_count
                or len(cast(list[object], row.get("ordered_portfolio", []))) != 20
                for row in ok
            )
            or any(
                generation.get("candidate_k") is not None
                or generation.get("combination_count") is not None
                or generation.get("source_method_combination_count") != configuration_count
                or generation.get("source_candidate_k_values") != [49]
                or generation.get("ledger_file_sha256") != LEDGER_FILE_SHA256
                or generation.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
                or generation.get("source_minimum_history_rationale")
                != MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
                for generation in native_generation
            )
        ):
            raise EvidenceBuildError(f"wave-47 execution semantics changed: {method_id}")
        strategies.append(
            {
                "candidate_k_distribution": _distribution([row.get("candidate_k") for row in ok]),
                "closed_execution_count": len(closed),
                "execution_status_counts": dict(sorted(status_counts.items())),
                "intra_ticket_order_semantics": (
                    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
                ),
                "legacy_method_id": method_id,
                "minimum_history_draws": (
                    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
                ),
                "minimum_history_rationale": (
                    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
                ),
                "native_duplicate_ticket_count_distribution": (
                    _distribution(
                        [
                            generation.get("native_duplicate_ticket_count")
                            for generation in native_generation
                        ]
                    )
                ),
                "native_ticket_count_distribution": _distribution(
                    [row.get("native_ticket_count") for row in ok]
                ),
                "ok_execution_count": len(ok),
                "source_candidate_k_values": list(
                    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
                ),
                "source_configuration_count": configuration_count,
                "source_configuration_count_distribution": (
                    _distribution([row.get("combination_count") for row in ok])
                ),
                "source_configuration_members": list(
                    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
                ),
                "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
                "source_sha256": (SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]),
                "strategy_id": strategy_id_by_method[method_id],
            }
        )
    return strategies, physical_database_sha256


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
        or report.get("dataset_sha256") != PINNED_DATASET_SHA256
        or report.get("target_draw_count") != 2149
        or report.get("progress") != EXPECTED_PRE_OVERLAY_PROGRESS
        or report.get("research_disclaimer") != RESEARCH_DISCLAIMER
    ):
        raise EvidenceBuildError("wave-47 report identity changed")
    metrics = cast(list[dict[str, Any]], report.get("metrics", []))
    prizes = cast(
        list[dict[str, Any]],
        report.get("official_prize_distributions", []),
    )
    rankings = cast(list[object], report.get("rankings", []))
    if (
        len(metrics) != 896
        or len(prizes) != 112
        or len(rankings) != 28288
        or Counter(cast(str, row.get("strategy_id")) for row in metrics)
        != Counter({strategy_id: 128 for strategy_id in strategy_ids})
        or Counter(cast(str, row.get("strategy_id")) for row in prizes)
        != Counter({strategy_id: 16 for strategy_id in strategy_ids})
        or {cast(int, row.get("prefix_count")) for row in metrics} != {5, 10, 15, 20}
        or {cast(str, row.get("window")) for row in metrics}
        != {"FULL", "RECENT_750", "RECENT_300", "RECENT_50"}
        or len({cast(str, row.get("criterion")) for row in metrics}) != 8
        or any(
            row.get("exact_random_baseline_probability") is None
            or row.get("random_baseline_rate_difference") is None
            for row in metrics
        )
    ):
        raise EvidenceBuildError("wave-47 metric, prize, or ranking coverage changed")
    checksums = {
        file_path.name: hashlib.sha256(file_path.read_bytes()).hexdigest()
        for file_path in path.parent.iterdir()
        if file_path.is_file()
    }
    if checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("wave-47 report checksums changed")
    return report, checksums


def build_evidence(
    *,
    base_catalog_path: Path,
    parity_path: Path,
    input_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate all artifacts and return the compact wave-47 proof."""

    strategy_id_by_method = _validate_catalog(base_catalog_path)
    parity = _validate_parity(parity_path)
    strategies, physical_database_sha256 = _validate_input(
        input_path,
        strategy_id_by_method=strategy_id_by_method,
    )
    report, report_checksums = _validate_report(
        report_path,
        strategy_ids={
            strategy_id_by_method[method_id] for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
        },
    )
    document: dict[str, object] = {
        "alias_disposition": {
            "alias_method_id": STABILITY_ALIAS_METHOD_ID,
            "alias_source_sha256": (
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE47_METHOD[STABILITY_ALIAS_METHOD_ID]
            ),
            "alias_strategy_id": strategy_id_by_method[STABILITY_ALIAS_METHOD_ID],
            "canonical_method_id": STABILITY_ALIAS_TARGET_METHOD_ID,
            "canonical_strategy_id": strategy_id_by_method[STABILITY_ALIAS_TARGET_METHOD_ID],
            "output_mismatch_count": 0,
            "overlapping_causal_output_case_count": 1649,
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
        "parity_sha256": parity["parity_sha256"],
        "physical_regeneration_database_sha256": (physical_database_sha256),
        "report_checksums": report_checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": report["report_sha256"],
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_native_protocol": SOURCE_NATIVE_WAVE47_PROTOCOL,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "strategies": strategies,
        "target_draw_count": 2149,
    }
    document["evidence_sha256"] = hashlib.sha256(_canonical_bytes(document)).hexdigest()
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
                "strategy_disposition_count": 8,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
