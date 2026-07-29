#!/usr/bin/env python3
"""Build compact evidence for the wave-64 frozen XGBoost replay."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.biglotto_multi_ticket_backtest import (
    BACKTEST_POLICY_VERSION,
    REPORT_SCHEMA_VERSION,
    RESEARCH_DISCLAIMER,
)
from lottolab.application.legacy_xgboost_native_portfolios_wave64 import (
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    CLOSED_REASON,
    DETERMINISM_PROTOCOL,
    FROZEN_SOURCE_COMMIT,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    METHOD_ID,
    NATIVE_TICKET_ORDER,
    NATIVE_TICKET_SEMANTICS,
    PINNED_DATASET_SHA256,
    PROBABILITY_SEQUENCE_SHA256,
    SOURCE_NATIVE_WAVE64_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256,
    TICKET_SEQUENCE_SHA256,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_xgboost_native_batch_import_wave64 import (
    HISTORY_INPUT_CANONICAL_SHA256,
    HISTORY_INPUT_FILE_SHA256,
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_XGBOOST_WAVE64_EVIDENCE_V1"
)
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_XGBOOST_WAVE64_PARITY_V1"
BASE_CATALOG_SHA256 = (
    "518c00da6a791551a74766b1356686e16cef88a087e00e1fdc839dce8e18e8a4"
)
BASE_CATALOG_FILE_SHA256 = (
    "c9f632d1306af42748a5f11493fb19c8bafcddecd3810676ad4178d9133c68ab"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 133,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 2,
}
EXPECTED_PROGRESS = {
    "backtested_count": 134,
    "closed_count": 74,
    "duplicate_alias_count": 12,
    "owner_decision_required_count": 1,
    "reproduced_count": 134,
    "total_strategy_count": 221,
    "uncompleted_count": 1,
}
EXPECTED_INPUT_FILE_SHA256 = (
    "25ba060686325f72ba6a89d9528243f499e378f494cf055a52c2992943628480"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "477d8597fe76104bcd7abcece88a258a51d04b4de801d7afaba133d6e1da038a"
)
EXPECTED_PARITY_FILE_SHA256 = (
    "5778462fd4b4d1034e66c3e9e4b10ef8e2bcadf053ad2c096a0bdfc322114927"
)
EXPECTED_PARITY_SHA256 = (
    "ed47a272603b1f4701f1615bf2c613161230dcb0aef8ea0720c11666db3de857"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "6167700a8a44e0d7f9e2596e093c53ac97c278bd1ab20e7d0682b49dd91e3279"
)
EXPECTED_REPORT_SHA256 = (
    "505c0dc63d081dcd10a9aa530b20af4319000a4d16d22613e73ef6c7e448542f"
)
EXPECTED_OK_SEQUENCE_SHA256 = (
    "e4247f625f1d3a3747eea07a6ff8bc2d3a529ceeebf20094330d715e6d4b4cce"
)
EXPECTED_ORDERED20_SEQUENCE_SHA256 = (
    "80fb952d7d57f59b72d13214fb1693d5d0d12c59c0da5c397e8d70584768616e"
)
EXPECTED_OK_ORDERED20_SEQUENCE_SHA256 = (
    "d16a206db636c2934b0ee938a76ada54140be72769cc5c56a4ab2d9ae5698d95"
)
EXPECTED_EXECUTION_COUNTS = {
    "CLOSED_INSUFFICIENT_HISTORY": 15,
    "OK": 2134,
}
EXPECTED_CLOSED_REASONS = {CLOSED_REASON: 15}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "7142e0dcf0ab7ea156f7fb4d0ef1525e34eac6f2ab86f4031e32d79b130153ce"
    ),
    "biglotto_execution_audit.csv": (
        "b8e62cb78f1cf66dd45ba7ffffef0223d8387738d2fadb71688c08ae13caad43"
    ),
    "biglotto_full_rankings.csv": (
        "d647426484b23c156f473372ecf280018ca4948b5efd469806da719bd0931695"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "6167700a8a44e0d7f9e2596e093c53ac97c278bd1ab20e7d0682b49dd91e3279"
    ),
    "biglotto_official_prize_distributions.csv": (
        "dbd63d730d8cea98a68bc83951724a8bf2282c7112983a8457bf2601d98bb4bb"
    ),
    "biglotto_strategy_universe.csv": (
        "d84cedff7b999d2cb45a34c5faa31294f61755b3480f119fd30e21302a4fa056"
    ),
    "biglotto_success_metrics.csv": (
        "3351ee2c865c793bfbfa1e830aef59fe4032f3eecb15fcfdbd3caeb6638ea437"
    ),
    "biglotto_top10.csv": (
        "b4e670a6604b9384b52d6aa6d8c53f6b6badd67678e73bebf4e3ff7a22b5657c"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-64 evidence inputs violate the frozen contract."""


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
        raise EvidenceBuildError(
            f"{path.name}: top level must be an object"
        )
    return cast(dict[str, Any], parsed), raw


def _validate_catalog(path: Path) -> str:
    catalog, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
    ):
        raise EvidenceBuildError("base catalog identity changed")
    for candidate in cast(list[object], catalog.get("records", [])):
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        if row.get("legacy_method_id") != METHOD_ID:
            continue
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256") != SOURCE_SHA256
            or type(row.get("strategy_id")) is not str
        ):
            break
        return cast(str, row["strategy_id"])
    raise EvidenceBuildError("wave-64 catalog row changed")


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("status_counts") != EXPECTED_EXECUTION_COUNTS
        or parity.get("native_ticket_case_count") != 2134
        or parity.get("native_ticket_count_distribution")
        != {"1": 2134}
        or parity.get("ticket_sequence_sha256")
        != TICKET_SEQUENCE_SHA256
        or parity.get("probability_sequence_sha256")
        != PROBABILITY_SEQUENCE_SHA256
        or parity.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or parity.get("ledger_content_sha256")
        != LEDGER_CONTENT_SHA256
        or parity.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
        or parity.get("thread_count_parity")
        != {
            "omp_thread_counts": [1, 8],
            "status": "PASS",
            "target_indices": [15, 50, 100, 999, 2148],
        }
    ):
        raise EvidenceBuildError("wave-64 parity identity changed")
    return parity


def _validate_input(
    path: Path,
    *,
    strategy_id: str,
) -> dict[str, object]:
    document, raw = _read_json(path)
    executions = cast(list[object], document.get("executions", []))
    provenance = cast(
        dict[str, Any],
        document.get("source_provenance", {}),
    )
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_INPUT_FILE_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest()
        != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", [])))
        != 2149
        or len(executions) != 2149
        or provenance.get("execution_status_counts")
        != EXPECTED_EXECUTION_COUNTS
        or provenance.get("native_ticket_count_distribution")
        != {"1": 2134}
        or provenance.get("combination_count_distribution")
        != {"1": 2134}
        or provenance.get(
            "native_duplicate_ticket_count_distribution"
        )
        != {"0": 2134}
        or provenance.get("history_input_file_sha256")
        != HISTORY_INPUT_FILE_SHA256
        or provenance.get("history_input_canonical_sha256")
        != HISTORY_INPUT_CANONICAL_SHA256
    ):
        raise EvidenceBuildError("wave-64 full input identity changed")
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    ok_native: list[list[list[int]]] = []
    all_native: list[list[list[int]] | None] = []
    ok_ordered: list[list[list[int]]] = []
    all_ordered: list[list[list[int]] | None] = []
    all_probabilities: list[list[float] | None] = []
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-64 execution changed")
        row = cast(dict[str, Any], candidate)
        if row.get("strategy_id") != strategy_id:
            raise EvidenceBuildError("wave-64 strategy identity changed")
        status = cast(str, row.get("status"))
        statuses[status] += 1
        if status != "OK":
            reason = cast(str, row.get("reason_code"))
            reasons[reason] += 1
            all_native.append(None)
            all_ordered.append(None)
            all_probabilities.append(None)
            if any(
                key in row
                for key in (
                    "native_tickets",
                    "ordered_portfolio",
                    "portfolio_ticket_count",
                )
            ):
                raise EvidenceBuildError(
                    "wave-64 closed row carries tickets"
                )
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError(
                "wave-64 native generation changed"
            )
        native = cast(dict[str, Any], native_raw)
        tickets = cast(list[list[int]], row.get("native_tickets", []))
        ordered = cast(
            list[list[int]],
            row.get("ordered_portfolio", []),
        )
        selected = cast(
            list[float],
            native.get("selected_probabilities", []),
        )
        ledger_index = native.get("ledger_target_index")
        if (
            native.get("legacy_method_id") != METHOD_ID
            or native.get("source_sha256") != SOURCE_SHA256
            or native.get("causal_protocol") != CAUSAL_PROTOCOL
            or native.get("candidate_k") is not None
            or native.get("source_candidate_k_values") != [49]
            or row.get("candidate_k") != 49
            or native.get("combination_count") is not None
            or native.get("local_configuration_count") != 1
            or row.get("combination_count") != 1
            or native.get("native_ticket_count") != 1
            or row.get("native_ticket_count") != 1
            or len(tickets) != 1
            or len(selected) != 6
            or row.get("portfolio_ticket_count") != 20
            or len(ordered) != 20
            or native.get("native_ticket_count_semantics")
            != NATIVE_TICKET_SEMANTICS
            or native.get("native_ticket_order")
            != NATIVE_TICKET_ORDER
            or native.get("determinism_protocol")
            != DETERMINISM_PROTOCOL
            or native.get("source_random_state_explicit") is not False
            or native.get("repeatability_parity_passed") is not True
            or native.get("thread_count_parity_passed") is not True
            or native.get("causal_eligibility_rule")
            != CAUSAL_ELIGIBILITY_RULE
            or native.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
            or native.get("ledger_file_sha256")
            != LEDGER_FILE_SHA256
            or native.get("ledger_content_sha256")
            != LEDGER_CONTENT_SHA256
            or type(ledger_index) is not int
            or ledger_index < 15
            or native.get("source_history_input_draw_count")
            != min(ledger_index, 1000)
        ):
            raise EvidenceBuildError("wave-64 native semantics changed")
        ok_native.append(tickets)
        all_native.append(tickets)
        ok_ordered.append(ordered)
        all_ordered.append(ordered)
        all_probabilities.append(selected)
    if (
        dict(statuses) != EXPECTED_EXECUTION_COUNTS
        or dict(reasons) != EXPECTED_CLOSED_REASONS
        or hashlib.sha256(_canonical_bytes(all_native)).hexdigest()
        != TICKET_SEQUENCE_SHA256
        or hashlib.sha256(_canonical_bytes(ok_native)).hexdigest()
        != EXPECTED_OK_SEQUENCE_SHA256
        or hashlib.sha256(_canonical_bytes(all_ordered)).hexdigest()
        != EXPECTED_ORDERED20_SEQUENCE_SHA256
        or hashlib.sha256(_canonical_bytes(ok_ordered)).hexdigest()
        != EXPECTED_OK_ORDERED20_SEQUENCE_SHA256
        or hashlib.sha256(
            _canonical_bytes(all_probabilities)
        ).hexdigest()
        != PROBABILITY_SEQUENCE_SHA256
    ):
        raise EvidenceBuildError("wave-64 execution distribution changed")
    return {
        "candidate_k_distribution": {"49": 2134},
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "causal_protocol": CAUSAL_PROTOCOL,
        "closed_execution_count": 15,
        "closed_reason_code_distribution": EXPECTED_CLOSED_REASONS,
        "combination_count_distribution": {"1": 2134},
        "determinism_protocol": DETERMINISM_PROTOCOL,
        "execution_status_counts": EXPECTED_EXECUTION_COUNTS,
        "legacy_method_id": METHOD_ID,
        "model_estimators_per_label": 50,
        "model_label_count": 49,
        "model_max_depth": 3,
        "native_duplicate_ticket_count_distribution": {"0": 2134},
        "native_ticket_count_distribution": {"1": 2134},
        "native_ticket_order": NATIVE_TICKET_ORDER,
        "native_ticket_semantics": NATIVE_TICKET_SEMANTICS,
        "ok_execution_count": 2134,
        "ordered20_sequence_sha256": (
            EXPECTED_ORDERED20_SEQUENCE_SHA256
        ),
        "probability_sequence_sha256": PROBABILITY_SEQUENCE_SHA256,
        "source_candidate_k_values": [49],
        "source_history_input_upper_bound": 1000,
        "source_random_state_explicit": False,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256": SOURCE_SHA256,
        "target_stable_model_retraining": True,
        "thread_count_parity_passed": True,
        "ticket_sequence_sha256": TICKET_SEQUENCE_SHA256,
    }


def _validate_report(
    *,
    report_file: Path,
    report_directory: Path,
    strategy_id: str,
) -> dict[str, str]:
    report, raw = _read_json(report_file)
    checksums = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in report_directory.iterdir()
        if path.is_file()
    }
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_REPORT_FILE_SHA256
        or report.get("report_schema_version")
        != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or report.get("report_sha256") != EXPECTED_REPORT_SHA256
        or report.get("catalog_sha256") != BASE_CATALOG_SHA256
        or report.get("dataset_sha256") != PINNED_DATASET_SHA256
        or report.get("target_draw_count") != 2149
        or report.get("progress") != EXPECTED_PROGRESS
        or report.get("input_raw_sha256")
        != EXPECTED_INPUT_FILE_SHA256
        or report.get("input_canonical_sha256")
        != EXPECTED_INPUT_CANONICAL_SHA256
        or report.get("research_disclaimer") != RESEARCH_DISCLAIMER
        or checksums != EXPECTED_REPORT_CHECKSUMS
        or len(cast(list[object], report.get("universe", []))) != 221
        or len(cast(list[object], report.get("rankings", []))) != 28288
        or len(cast(list[object], report.get("top_10", []))) != 128
        or len(
            cast(
                list[object],
                report.get("official_prize_distributions", []),
            )
        )
        != 16
    ):
        raise EvidenceBuildError("wave-64 report identity changed")
    metrics = cast(list[dict[str, Any]], report.get("metrics", []))
    if (
        len(metrics) != 128
        or {row.get("strategy_id") for row in metrics}
        != {strategy_id}
        or {row.get("prefix_count") for row in metrics}
        != {5, 10, 15, 20}
        or {row.get("window") for row in metrics}
        != {"FULL", "RECENT_750", "RECENT_300", "RECENT_50"}
        or len({row.get("criterion") for row in metrics}) != 8
        or not all(row.get("rankable") is True for row in metrics)
        or not all(
            isinstance(row.get("exact_random_baseline_probability"), dict)
            and isinstance(row.get("random_baseline_rate_difference"), dict)
            for row in metrics
        )
    ):
        raise EvidenceBuildError("wave-64 report coverage changed")
    rankings = cast(list[dict[str, Any]], report.get("rankings", []))
    if (
        sum(row.get("strategy_id") == strategy_id for row in rankings)
        != 128
        or any(
            row.get("strategy_id") != strategy_id
            and not row.get("unranked_reason")
            for row in rankings
        )
    ):
        raise EvidenceBuildError(
            "wave-64 complete-universe ranking changed"
        )
    return checksums


def build_evidence(
    *,
    base_catalog_path: Path,
    input_file: Path,
    parity_file: Path,
    report_file: Path,
    report_directory: Path,
) -> dict[str, object]:
    """Validate every wave-64 artifact and return compact evidence."""

    strategy_id = _validate_catalog(base_catalog_path)
    parity = _validate_parity(parity_file)
    strategy = _validate_input(
        input_file,
        strategy_id=strategy_id,
    )
    checksums = _validate_report(
        report_file=report_file,
        report_directory=report_directory,
        strategy_id=strategy_id,
    )
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "causal_protocol": CAUSAL_PROTOCOL,
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "input_canonical_sha256": EXPECTED_INPUT_CANONICAL_SHA256,
        "input_raw_sha256": EXPECTED_INPUT_FILE_SHA256,
        "ledger_content_sha256": LEDGER_CONTENT_SHA256,
        "ledger_file_sha256": LEDGER_FILE_SHA256,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "materialization_schema_version": (
            MATERIALIZATION_SCHEMA_VERSION
        ),
        "parity": parity,
        "report_checksums": checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_native_protocol": SOURCE_NATIVE_WAVE64_PROTOCOL,
        "strategies": [strategy],
        "target_draw_count": 2149,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--parity-file", required=True, type=Path)
    parser.add_argument("--report-file", required=True, type=Path)
    parser.add_argument("--report-directory", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    document = build_evidence(
        base_catalog_path=args.base_catalog,
        input_file=args.input_file,
        parity_file=args.parity_file,
        report_file=args.report_file,
        report_directory=args.report_directory,
    )
    payload = _canonical_bytes(document) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
                "strategy_count": 1,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
