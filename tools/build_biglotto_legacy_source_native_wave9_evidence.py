#!/usr/bin/env python3
"""Build checked evidence for the ninth BIG_LOTTO source-native batch."""

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
)
from lottolab.application.legacy_source_native_portfolios_wave9 import (
    CANDIDATE_K_BY_SOURCE_NATIVE_WAVE9_METHOD,
    DEFAULT_SOURCE_NATIVE_WAVE9_USER_SEED,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE9_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE9_METHOD,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE9_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE9_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE9_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE9_METHOD,
    SOURCE_NATIVE_WAVE9_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE9_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave9 import (
    MATERIALIZATION_SCHEMA_VERSION,
)
from verify_biglotto_legacy_source_native_wave9_parity import (
    FROZEN_SOURCE_COMMIT,
    PARITY_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE9_EVIDENCE_V1"
)
EXPECTED_CATALOG_SHA256 = (
    "5c07216f86f1e9de44f324f6210fbbc1518bc6b6308847e198df37c4f191a492"
)
EXPECTED_TARGET_COUNT = 2149
EXPECTED_STATUS_COUNTS_BY_METHOD = {
    "tools/backtest_cluster_pivot_biglotto.py": {
        "CLOSED_INSUFFICIENT_HISTORY": 50,
        "OK": 2099,
    },
    "tools/research_true_orthogonal.py": {
        "CLOSED_INSUFFICIENT_HISTORY": 100,
        "OK": 2049,
    },
    "tools/backtest_p0p1_upgrade.py": {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
}
EXPECTED_NATIVE_COUNT_VALUES = {
    "tools/backtest_cluster_pivot_biglotto.py": [17, 19],
    "tools/research_true_orthogonal.py": [17, 18, 19, 20, 21],
    "tools/backtest_p0p1_upgrade.py": [10],
}
EXPECTED_SOURCE_CANDIDATE_K_VALUES = {
    "tools/backtest_cluster_pivot_biglotto.py": [],
    "tools/research_true_orthogonal.py": [],
    "tools/backtest_p0p1_upgrade.py": [
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        24,
    ],
}
EXPECTED_REPORT_PROGRESS = {
    "backtested_count": 34,
    "closed_count": 21,
    "duplicate_alias_count": 4,
    "owner_decision_required_count": 162,
    "reproduced_count": 34,
    "total_strategy_count": 221,
    "uncompleted_count": 162,
}


class EvidenceBuildError(ValueError):
    """Wave-9 evidence inputs violate the frozen contract."""


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
    output: dict[str, str] = {}
    for path in sorted(
        candidate for candidate in directory.iterdir() if candidate.is_file()
    ):
        output[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not output:
        raise EvidenceBuildError("report directory is empty")
    return output


def _validate_parity(
    parity: dict[str, Any],
    raw: bytes,
    database_sha256: object,
) -> dict[str, object]:
    cases_raw = parity.get("cases")
    if (
        parity.get("parity_schema_version") != PARITY_SCHEMA_VERSION
        or parity.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or parity.get("port_protocol") != SOURCE_NATIVE_WAVE9_PROTOCOL
        or parity.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD
        or parity.get("database_sha256") != database_sha256
        or parity.get("status") != "PASS"
        or parity.get("case_count") != 9
        or not isinstance(cases_raw, list)
        or len(cast(list[object], cases_raw)) != 9
    ):
        raise EvidenceBuildError("frozen-source parity identity changed")
    method_counts: Counter[str] = Counter()
    for candidate in cast(list[object], cases_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("parity case is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if (
            method_id not in SUPPORTED_SOURCE_NATIVE_WAVE9_METHODS
            or type(row.get("history_draw_count")) is not int
            or type(row.get("native_ticket_count")) is not int
            or type(row.get("ticket_sha256")) is not str
            or len(cast(str, row["ticket_sha256"])) != 64
        ):
            raise EvidenceBuildError("parity case changed")
        method_counts[cast(str, method_id)] += 1
    if method_counts != Counter(
        {
            method_id: 3
            for method_id in SUPPORTED_SOURCE_NATIVE_WAVE9_METHODS
        }
    ):
        raise EvidenceBuildError("parity method coverage changed")
    return {
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "case_count": 9,
        "execution_mode": parity["execution_mode"],
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "status": "PASS",
    }


def _strategy_rows(
    document: dict[str, Any],
) -> list[dict[str, object]]:
    executions_raw = document.get("executions")
    if not isinstance(executions_raw, list):
        raise EvidenceBuildError("input executions are missing")
    status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    native_counts: dict[str, set[int]] = defaultdict(set)
    duplicate_counts: dict[str, set[int]] = defaultdict(set)
    source_candidate_k_values: dict[str, set[int]] = defaultdict(set)
    strategy_identity: dict[str, tuple[str, str]] = {}
    for candidate in cast(list[object], executions_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("input execution is invalid")
        row = cast(dict[str, Any], candidate)
        strategy_id = row.get("strategy_id")
        strategy_version = row.get("strategy_version")
        status = row.get("status")
        if (
            type(strategy_id) is not str
            or type(strategy_version) is not str
            or type(status) is not str
        ):
            raise EvidenceBuildError("execution identity changed")
        native_raw = row.get("native_generation")
        if status == "OK":
            if not isinstance(native_raw, dict):
                raise EvidenceBuildError(
                    "successful native generation is missing"
                )
            native = cast(dict[str, Any], native_raw)
            method_id = native.get("legacy_method_id")
            if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE9_METHODS:
                raise EvidenceBuildError("unexpected successful method")
            method = cast(str, method_id)
            strategy_identity[method] = (strategy_id, strategy_version)
            status_counts[method]["OK"] += 1
            native_count = row.get("native_ticket_count")
            duplicate_count = native.get(
                "native_duplicate_ticket_count"
            )
            candidate_values = native.get(
                "source_candidate_k_values"
            )
            if (
                type(native_count) is not int
                or type(duplicate_count) is not int
                or not isinstance(candidate_values, list)
            ):
                raise EvidenceBuildError("native metadata changed")
            typed_candidate_values = cast(
                list[object],
                candidate_values,
            )
            if any(
                type(value) is not int
                for value in typed_candidate_values
            ):
                raise EvidenceBuildError("source Candidate-K changed")
            native_counts[method].add(native_count)
            duplicate_counts[method].add(duplicate_count)
            source_candidate_k_values[method].update(
                cast(list[int], typed_candidate_values)
            )
            continue
        method = next(
            (
                method_id
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE9_METHODS
                if strategy_id.endswith(
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD[
                        method_id
                    ][:12]
                )
            ),
            None,
        )
        if method is None:
            raise EvidenceBuildError("closed strategy identity changed")
        strategy_identity[method] = (strategy_id, strategy_version)
        status_counts[method][status] += 1

    actual_status = {
        method_id: dict(sorted(status_counts[method_id].items()))
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE9_METHODS
    }
    if actual_status != EXPECTED_STATUS_COUNTS_BY_METHOD:
        raise EvidenceBuildError("execution status counts changed")
    rows: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE9_METHODS:
        strategy_id, strategy_version = strategy_identity[method_id]
        closed = {
            status: count
            for status, count in actual_status[method_id].items()
            if status != "OK"
        }
        rows.append(
            {
                "candidate_k": (
                    CANDIDATE_K_BY_SOURCE_NATIVE_WAVE9_METHOD[
                        method_id
                    ]
                ),
                "closed_status_counts": closed,
                "combination_count": (
                    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE9_METHOD[
                        method_id
                    ]
                ),
                "combination_members": list(
                    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE9_METHOD[
                        method_id
                    ]
                ),
                "legacy_method_id": method_id,
                "minimum_history_draws": (
                    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE9_METHOD[
                        method_id
                    ]
                ),
                "native_duplicate_ticket_count_values": sorted(
                    duplicate_counts[method_id]
                ),
                "native_ticket_count_values": sorted(
                    native_counts[method_id]
                ),
                "native_ticket_semantics": (
                    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE9_METHOD[
                        method_id
                    ]
                ),
                "random_protocol": (
                    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE9_METHOD[
                        method_id
                    ]
                ),
                "source_candidate_k_values": sorted(
                    source_candidate_k_values[method_id]
                ),
                "source_history_order": (
                    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE9_METHOD[
                        method_id
                    ]
                ),
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD[
                        method_id
                    ]
                ),
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                "successful_execution_count": actual_status[method_id][
                    "OK"
                ],
            }
        )
    if {
        cast(str, row["legacy_method_id"]): row[
            "native_ticket_count_values"
        ]
        for row in rows
    } != EXPECTED_NATIVE_COUNT_VALUES:
        raise EvidenceBuildError("native ticket counts changed")
    if {
        cast(str, row["legacy_method_id"]): row[
            "source_candidate_k_values"
        ]
        for row in rows
    } != EXPECTED_SOURCE_CANDIDATE_K_VALUES:
        raise EvidenceBuildError("source Candidate-K values changed")
    return rows


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
        or len(cast(list[object], executions)) != 6447
        or report.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or report.get("catalog_sha256") != EXPECTED_CATALOG_SHA256
        or report.get("progress") != EXPECTED_REPORT_PROGRESS
        or report.get("target_draw_count") != EXPECTED_TARGET_COUNT
    ):
        raise EvidenceBuildError("input/report contract changed")
    expected_lengths = {
        "execution_audit": 6447,
        "metrics": 384,
        "official_prize_distributions": 48,
        "rankings": 28288,
        "top_10": 384,
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
        != SOURCE_NATIVE_WAVE9_PROTOCOL
        or provenance.get("user_seed")
        != DEFAULT_SOURCE_NATIVE_WAVE9_USER_SEED
        or provenance.get("database_sha256_before")
        != provenance.get("database_sha256_after")
        or provenance.get("frozen_sources")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD
        or provenance.get("execution_status_counts_by_method")
        != EXPECTED_STATUS_COUNTS_BY_METHOD
        or provenance.get("candidate_k_semantics")
        != (
            "TOP_LEVEL_NOT_APPLICABLE; PER_CONFIGURATION_VALUES_"
            "RETAINED_IN_NATIVE_GENERATION_METADATA"
        )
    ):
        raise EvidenceBuildError("source provenance changed")
    parity, raw_parity = _read_json(parity_file)
    parity_summary = _validate_parity(
        parity,
        raw_parity,
        provenance.get("database_sha256_before"),
    )
    input_sha256 = hashlib.sha256(raw_input).hexdigest()
    report_file_sha256 = hashlib.sha256(raw_report).hexdigest()
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "candidate_k_semantics": (
            "PER_CONFIGURATION_CANDIDATE_POOL_SIZE_DISTINCT_FROM_NATIVE_"
            "TICKET_AND_SOURCE_CONFIGURATION_COUNTS"
        ),
        "catalog_sha256_before_status_overlay": EXPECTED_CATALOG_SHA256,
        "combination_count_semantics": (
            "SOURCE_ENTRYPOINT_METHOD_OR_PARAMETER_CONFIGURATION_COUNT"
        ),
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_parity": parity_summary,
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
        "source_native_protocol": SOURCE_NATIVE_WAVE9_PROTOCOL,
        "strategies": _strategy_rows(document),
        "target_draw_count": EXPECTED_TARGET_COUNT,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--repeat-input-file", required=True, type=Path)
    parser.add_argument("--report-directory", required=True, type=Path)
    parser.add_argument(
        "--repeat-report-directory", required=True, type=Path
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
                "strategy_count": len(
                    cast(list[object], document["strategies"])
                ),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
