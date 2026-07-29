#!/usr/bin/env python3
"""Build checked evidence for the twelfth BIG_LOTTO source-native batch."""

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
)
from lottolab.application.legacy_source_native_portfolios_wave12 import (
    DEFAULT_SOURCE_NATIVE_WAVE12_USER_SEED,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE12_METHOD,
    MODERATE_SELECTION_METHOD_ID,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE12_METHOD,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE12_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE12_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE12_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE12_METHOD,
    SOURCE_NATIVE_WAVE12_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave12 import (
    MATERIALIZATION_SCHEMA_VERSION,
)
from verify_biglotto_legacy_source_native_wave12_parity import (
    FROZEN_SOURCE_COMMIT,
    PARITY_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE12_EVIDENCE_V1"
)
EXPECTED_CATALOG_SHA256 = (
    "73484188012e8ee558ac1e60dba0445bc922102b5187f04fc0d3e561926d0f0e"
)
EXPECTED_TARGET_COUNT = 2149
EXPECTED_STATUS_COUNTS = {
    "CLOSED_INSUFFICIENT_HISTORY": 50,
    "OK": 2099,
}
EXPECTED_NATIVE_DUPLICATE_COUNTS = [
    331,
    333,
    335,
    336,
    337,
    338,
    339,
    340,
    341,
    342,
    343,
    344,
    345,
    346,
    347,
    348,
    349,
    350,
    351,
    352,
    353,
    354,
    355,
    356,
    357,
    358,
]
EXPECTED_REPORT_PROGRESS = {
    "backtested_count": 37,
    "closed_count": 25,
    "duplicate_alias_count": 4,
    "owner_decision_required_count": 155,
    "reproduced_count": 37,
    "total_strategy_count": 221,
    "uncompleted_count": 155,
}


class EvidenceBuildError(ValueError):
    """Wave-12 evidence inputs violate the frozen contract."""


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


def _directory_checksums(directory: Path) -> dict[str, str]:
    output = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(
            candidate
            for candidate in directory.iterdir()
            if candidate.is_file()
        )
    }
    if not output:
        raise EvidenceBuildError("report directory is empty")
    return output


def _parity_summary(
    parity: dict[str, Any],
    raw: bytes,
    database_sha256: object,
) -> dict[str, object]:
    cases_raw = parity.get("cases")
    if (
        parity.get("parity_schema_version") != PARITY_SCHEMA_VERSION
        or parity.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or parity.get("port_protocol") != SOURCE_NATIVE_WAVE12_PROTOCOL
        or parity.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD
        or parity.get("database_sha256") != database_sha256
        or parity.get("status") != "PASS"
        or parity.get("case_count") != 3
        or not isinstance(cases_raw, list)
        or len(cast(list[object], cases_raw)) != 3
    ):
        raise EvidenceBuildError("frozen-source parity identity changed")
    for candidate in cast(list[object], cases_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("parity case is invalid")
        row = cast(dict[str, Any], candidate)
        ticket_sha256 = row.get("ticket_sha256")
        if (
            row.get("legacy_method_id")
            != MODERATE_SELECTION_METHOD_ID
            or type(row.get("history_draw_count")) is not int
            or row.get("native_ticket_count") != 360
            or type(ticket_sha256) is not str
            or len(ticket_sha256) != 64
        ):
            raise EvidenceBuildError("parity case changed")
    return {
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "case_count": 3,
        "execution_mode": parity["execution_mode"],
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "status": "PASS",
    }


def _strategy_row(
    document: dict[str, Any],
) -> dict[str, object]:
    executions_raw = document.get("executions")
    if not isinstance(executions_raw, list):
        raise EvidenceBuildError("input executions are missing")
    statuses: Counter[str] = Counter()
    native_counts: set[int] = set()
    duplicate_counts: set[int] = set()
    strategy_ids: set[str] = set()
    strategy_versions: set[str] = set()
    for candidate in cast(list[object], executions_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("input execution is invalid")
        row = cast(dict[str, Any], candidate)
        status = row.get("status")
        strategy_id = row.get("strategy_id")
        strategy_version = row.get("strategy_version")
        if (
            type(status) is not str
            or type(strategy_id) is not str
            or type(strategy_version) is not str
        ):
            raise EvidenceBuildError("execution identity changed")
        statuses[status] += 1
        strategy_ids.add(strategy_id)
        strategy_versions.add(strategy_version)
        if status != "OK":
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError(
                "successful native generation is missing"
            )
        native = cast(dict[str, Any], native_raw)
        ticket_counts = native.get("source_candidate_ticket_counts")
        if (
            native.get("legacy_method_id")
            != MODERATE_SELECTION_METHOD_ID
            or row.get("native_ticket_count") != 360
            or native.get("native_ticket_count") != 360
            or type(native.get("native_duplicate_ticket_count"))
            is not int
            or not isinstance(ticket_counts, list)
            or ticket_counts != [2] * 180
            or native.get("source_combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE12_METHOD[
                    MODERATE_SELECTION_METHOD_ID
                ]
            )
        ):
            raise EvidenceBuildError("native metadata changed")
        native_counts.add(cast(int, row["native_ticket_count"]))
        duplicate_counts.add(
            cast(int, native["native_duplicate_ticket_count"])
        )
    if (
        dict(sorted(statuses.items())) != EXPECTED_STATUS_COUNTS
        or native_counts != {360}
        or sorted(duplicate_counts)
        != EXPECTED_NATIVE_DUPLICATE_COUNTS
        or len(strategy_ids) != 1
        or len(strategy_versions) != 1
    ):
        raise EvidenceBuildError("execution evidence changed")
    return {
        "candidate_k": None,
        "closed_status_counts": {
            "CLOSED_INSUFFICIENT_HISTORY": 50,
        },
        "combination_count": (
            SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE12_METHOD[
                MODERATE_SELECTION_METHOD_ID
            ]
        ),
        "combination_members": list(
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE12_METHOD[
                MODERATE_SELECTION_METHOD_ID
            ]
        ),
        "legacy_method_id": MODERATE_SELECTION_METHOD_ID,
        "minimum_history_draws": (
            MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE12_METHOD[
                MODERATE_SELECTION_METHOD_ID
            ]
        ),
        "native_duplicate_ticket_count_values": sorted(
            duplicate_counts
        ),
        "native_ticket_count_values": [360],
        "native_ticket_semantics": (
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE12_METHOD[
                MODERATE_SELECTION_METHOD_ID
            ]
        ),
        "random_protocol": (
            RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE12_METHOD[
                MODERATE_SELECTION_METHOD_ID
            ]
        ),
        "source_history_order": (
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE12_METHOD[
                MODERATE_SELECTION_METHOD_ID
            ]
        ),
        "source_result_selection": (
            "ALL_180_FIXED_CONFIGURATIONS_RETAINED_NO_TARGET_"
            "OUTCOME_GRID_WINNER_SELECTION"
        ),
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD[
                MODERATE_SELECTION_METHOD_ID
            ]
        ),
        "strategy_id": next(iter(strategy_ids)),
        "strategy_version": next(iter(strategy_versions)),
        "successful_execution_count": 2099,
    }


def build_evidence(
    *,
    input_file: Path,
    repeat_input_file: Path,
    report_directory: Path,
    repeat_report_directory: Path,
    parity_file: Path,
) -> dict[str, object]:
    document, raw_input = _read_json(input_file)
    repeat_document, raw_repeat = _read_json(repeat_input_file)
    if raw_input != raw_repeat or document != repeat_document:
        raise EvidenceBuildError(
            "repeat materialization is not byte-identical"
        )
    report_path = (
        report_directory / "biglotto_multi_ticket_backtest_report.json"
    )
    repeat_report_path = (
        repeat_report_directory
        / "biglotto_multi_ticket_backtest_report.json"
    )
    report, raw_report = _read_json(report_path)
    repeat_report, raw_repeat_report = _read_json(repeat_report_path)
    checksums = _directory_checksums(report_directory)
    repeat_checksums = _directory_checksums(repeat_report_directory)
    if (
        raw_report != raw_repeat_report
        or report != repeat_report
        or checksums != repeat_checksums
    ):
        raise EvidenceBuildError(
            "repeat report directory is not byte-identical"
        )
    targets = document.get("targets")
    executions = document.get("executions")
    if (
        document.get("dataset_version") != MATERIALIZATION_SCHEMA_VERSION
        or not isinstance(targets, list)
        or len(cast(list[object], targets)) != EXPECTED_TARGET_COUNT
        or not isinstance(executions, list)
        or len(cast(list[object], executions)) != 2149
        or report.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or report.get("catalog_sha256") != EXPECTED_CATALOG_SHA256
        or report.get("progress") != EXPECTED_REPORT_PROGRESS
        or report.get("target_draw_count") != EXPECTED_TARGET_COUNT
    ):
        raise EvidenceBuildError("input/report contract changed")
    expected_lengths = {
        "execution_audit": 2149,
        "metrics": 128,
        "official_prize_distributions": 16,
        "rankings": 28288,
        "top_10": 128,
        "universe": 221,
    }
    if any(
        not isinstance(report.get(key), list)
        or len(cast(list[object], report[key])) != expected
        for key, expected in expected_lengths.items()
    ):
        raise EvidenceBuildError("report collection lengths changed")
    provenance_raw = document.get("source_provenance")
    if not isinstance(provenance_raw, dict):
        raise EvidenceBuildError("source provenance is missing")
    provenance = cast(dict[str, Any], provenance_raw)
    if (
        provenance.get("constructor") != CONSTRUCTOR_IDENTIFIER
        or provenance.get("source_native_protocol")
        != SOURCE_NATIVE_WAVE12_PROTOCOL
        or provenance.get("user_seed")
        != DEFAULT_SOURCE_NATIVE_WAVE12_USER_SEED
        or provenance.get("database_sha256_before")
        != provenance.get("database_sha256_after")
        or provenance.get("frozen_sources")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD
        or provenance.get("execution_status_counts_by_method")
        != {
            MODERATE_SELECTION_METHOD_ID: EXPECTED_STATUS_COUNTS
        }
        or provenance.get("source_result_selection")
        != (
            "NO_TARGET_OUTCOME_GRID_WINNER_SELECTION; ALL_180_"
            "FIXED_CONFIGURATIONS_RETAINED_IN_SOURCE_ORDER"
        )
    ):
        raise EvidenceBuildError("source provenance changed")
    parity, raw_parity = _read_json(parity_file)
    input_sha256 = hashlib.sha256(raw_input).hexdigest()
    report_file_sha256 = hashlib.sha256(raw_report).hexdigest()
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "candidate_k_semantics": (
            "NOT_APPLICABLE_GRID_PARAMETERS_ARE_CONFIGURATIONS"
        ),
        "catalog_sha256_before_status_overlay": EXPECTED_CATALOG_SHA256,
        "combination_count_semantics": (
            "FROZEN_PARAMETER_GRID_CONFIGURATION_COUNT"
        ),
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_parity": _parity_summary(
            parity,
            raw_parity,
            provenance.get("database_sha256_before"),
        ),
        "input_canonical_sha256": hashlib.sha256(
            _canonical_bytes(document)
        ).hexdigest(),
        "input_raw_sha256": input_sha256,
        "output_checksums": checksums,
        "report_file_sha256": report_file_sha256,
        "report_sha256": report["report_sha256"],
        "reproducibility": {
            "input_byte_identical": True,
            "repeat_input_raw_sha256": input_sha256,
            "repeat_report_file_sha256": report_file_sha256,
            "report_directory_byte_identical": True,
        },
        "source_database_sha256_after": provenance[
            "database_sha256_after"
        ],
        "source_database_sha256_before": provenance[
            "database_sha256_before"
        ],
        "source_native_protocol": SOURCE_NATIVE_WAVE12_PROTOCOL,
        "strategies": [_strategy_row(document)],
        "target_draw_count": EXPECTED_TARGET_COUNT,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--repeat-input-file", required=True, type=Path)
    parser.add_argument("--report-directory", required=True, type=Path)
    parser.add_argument(
        "--repeat-report-directory",
        required=True,
        type=Path,
    )
    parser.add_argument("--parity-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    document = build_evidence(
        input_file=args.input_file,
        repeat_input_file=args.repeat_input_file,
        report_directory=args.report_directory,
        repeat_report_directory=args.repeat_report_directory,
        parity_file=args.parity_file,
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
