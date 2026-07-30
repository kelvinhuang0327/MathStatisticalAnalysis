"""Build compact evidence for the sixth source-native BIG_LOTTO wave."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, cast

from lottolab.application.biglotto_multi_ticket_backtest import (
    BACKTEST_POLICY_VERSION,
    INPUT_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
)
from lottolab.application.legacy_source_native_portfolios_wave6 import (
    COMPARE_RANDOM_METHOD_ID,
    DEFAULT_SOURCE_NATIVE_WAVE6_USER_SEED,
    ECHO_PHASE2_METHOD_ID,
    HOT_STOP_REBOUND_METHOD_ID,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE6_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE6_METHOD,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE6_METHOD,
    SBP_RANDOM_METHOD_ID,
    SOURCE_CANDIDATE_TICKET_COUNTS_BY_SOURCE_NATIVE_WAVE6_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE6_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE6_METHOD,
    SOURCE_NATIVE_WAVE6_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave6 import (
    MATERIALIZATION_SCHEMA_VERSION,
)
from verify_biglotto_legacy_source_native_wave6_parity import (
    DEPENDENCY_SOURCES,
    FROZEN_SOURCE_COMMIT,
    HISTORY_COUNTS_BY_METHOD,
    PARITY_SCHEMA_VERSION,
    SOURCE_BLOB_BY_METHOD,
    SOURCE_BYTE_SIZE_BY_METHOD,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE6_EVIDENCE_V1"
)
EXPECTED_CATALOG_SHA256 = (
    "5f1fb42728423a9bfc3cfd2a3f5af0ea6e97f62d599a5bec7c8692ad4a1e5cd3"
)
EXPECTED_TARGET_COUNT = 2149
EXPECTED_STATUS_COUNTS_BY_METHOD = {
    ECHO_PHASE2_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
    HOT_STOP_REBOUND_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 200,
        "OK": 1949,
    },
    COMPARE_RANDOM_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
    SBP_RANDOM_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
}
EXPECTED_NATIVE_COUNT_VALUES = {
    ECHO_PHASE2_METHOD_ID: [5],
    HOT_STOP_REBOUND_METHOD_ID: [8],
    COMPARE_RANDOM_METHOD_ID: [5],
    SBP_RANDOM_METHOD_ID: [3],
}
EXPECTED_RANDOMNESS_USED = {
    ECHO_PHASE2_METHOD_ID: False,
    HOT_STOP_REBOUND_METHOD_ID: False,
    COMPARE_RANDOM_METHOD_ID: True,
    SBP_RANDOM_METHOD_ID: True,
}
EXPECTED_REPORT_PROGRESS = {
    "backtested_count": 22,
    "closed_count": 21,
    "duplicate_alias_count": 4,
    "owner_decision_required_count": 174,
    "reproduced_count": 22,
    "total_strategy_count": 221,
    "uncompleted_count": 174,
}


class EvidenceBuildError(ValueError):
    """The wave-6 evidence inputs violate the frozen contract."""


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


def _read_checksums(report_directory: Path) -> dict[str, str]:
    checksum_path = report_directory / "SHA256SUMS"
    rows: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        try:
            digest, filename = line.split("  ", maxsplit=1)
        except ValueError as exc:
            raise EvidenceBuildError("SHA256SUMS is malformed") from exc
        candidate = report_directory / filename
        if (
            len(digest) != 64
            or not candidate.is_file()
            or hashlib.sha256(candidate.read_bytes()).hexdigest()
            != digest
        ):
            raise EvidenceBuildError(f"checksum mismatch: {filename}")
        rows[filename] = digest
    rows["SHA256SUMS"] = hashlib.sha256(
        checksum_path.read_bytes()
    ).hexdigest()
    return dict(sorted(rows.items()))


def _validate_parity(
    *,
    parity: dict[str, Any],
    raw_parity: bytes,
    dataset_sha256: object,
) -> dict[str, object]:
    if (
        parity.get("parity_schema_version") != PARITY_SCHEMA_VERSION
        or parity.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or parity.get("parity_case_count") != 12
        or parity.get("database_sha256_before") != dataset_sha256
        or parity.get("database_sha256_after") != dataset_sha256
        or parity.get("random_parity_semantics")
        != (
            "EXACT_FROZEN_RANDOM_SAMPLE_CALL_ORDER_UNDER_INJECTED_"
            "VERSIONED_TARGET_STABLE_SEED_NOT_ORIGINAL_STATE_RECOVERY"
        )
    ):
        raise EvidenceBuildError("frozen-source parity identity changed")
    sources_raw = parity.get("sources")
    if not isinstance(sources_raw, list):
        raise EvidenceBuildError("frozen-source parity sources are missing")
    sources_by_method: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], sources_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError(
                "frozen-source parity source row is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if type(method_id) is not str or method_id in sources_by_method:
            raise EvidenceBuildError(
                "frozen-source parity source identity is invalid"
            )
        sources_by_method[method_id] = row
    expected_source_ids = {
        *SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS,
        *DEPENDENCY_SOURCES,
    }
    if set(sources_by_method) != expected_source_ids:
        raise EvidenceBuildError("frozen-source parity omits a source")
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS:
        row = sources_by_method[method_id]
        if (
            row.get("source_role") != "PRIMARY_METHOD"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD[method_id]
            or row.get("source_blob_id")
            != SOURCE_BLOB_BY_METHOD[method_id]
            or row.get("source_byte_size")
            != SOURCE_BYTE_SIZE_BY_METHOD[method_id]
        ):
            raise EvidenceBuildError(
                "frozen-source parity primary identity changed"
            )
    for method_id, facts in DEPENDENCY_SOURCES.items():
        row = sources_by_method[method_id]
        if (
            row.get("source_role") != "FROZEN_IMPORTED_DEPENDENCY"
            or row.get("source_sha256") != facts["source_sha256"]
            or row.get("source_blob_id") != facts["source_blob_id"]
            or row.get("source_byte_size") != facts["source_byte_size"]
        ):
            raise EvidenceBuildError(
                "frozen-source parity dependency identity changed"
            )
    cases_raw = parity.get("parity_cases")
    if not isinstance(cases_raw, list):
        raise EvidenceBuildError("frozen-source parity cases are missing")
    observed_counts: dict[str, list[int]] = defaultdict(list)
    for candidate in cast(list[object], cases_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError(
                "frozen-source parity case is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        history_count = row.get("history_draw_count")
        if (
            method_id not in SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS
            or type(history_count) is not int
            or row.get("status") != "PASS"
            or row.get("randomness_used")
            is not EXPECTED_RANDOMNESS_USED[cast(str, method_id)]
            or type(row.get("native_ticket_count")) is not int
            or type(row.get("native_duplicate_ticket_count")) is not int
            or type(row.get("ordered_tickets_sha256")) is not str
            or len(cast(str, row["ordered_tickets_sha256"])) != 64
        ):
            raise EvidenceBuildError(
                "frozen-source parity result changed"
            )
        observed_counts[cast(str, method_id)].append(history_count)
    if {
        method_id: tuple(counts)
        for method_id, counts in observed_counts.items()
    } != HISTORY_COUNTS_BY_METHOD:
        raise EvidenceBuildError(
            "frozen-source parity history cutoffs changed"
        )
    return {
        "artifact_sha256": hashlib.sha256(raw_parity).hexdigest(),
        "case_count": 12,
        "execution_mode": parity["source_execution_mode"],
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "random_parity_semantics": parity[
            "random_parity_semantics"
        ],
        "status": "PASS",
    }


def _validate_report_contract(
    *,
    document: dict[str, Any],
    raw_input: bytes,
    report: dict[str, Any],
) -> None:
    targets_raw = document.get("targets")
    if not isinstance(targets_raw, list):
        raise EvidenceBuildError("input targets are missing")
    if (
        document.get("schema_version") != INPUT_SCHEMA_VERSION
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], targets_raw))
        != EXPECTED_TARGET_COUNT
        or report.get("report_schema_version")
        != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or report.get("input_raw_sha256")
        != hashlib.sha256(raw_input).hexdigest()
        or report.get("target_draw_count") != EXPECTED_TARGET_COUNT
        or report.get("catalog_sha256") != EXPECTED_CATALOG_SHA256
        or report.get("progress") != EXPECTED_REPORT_PROGRESS
        or len(cast(list[object], report.get("metrics", []))) != 512
        or len(
            cast(
                list[object],
                report.get("official_prize_distributions", []),
            )
        )
        != 64
        or len(cast(list[object], report.get("rankings", [])))
        != 28288
        or len(cast(list[object], report.get("top_10", []))) != 512
    ):
        raise EvidenceBuildError("input/report contract changed")


def _validate_provenance(
    provenance: dict[str, Any],
) -> None:
    expected_none_candidate = {
        method_id: None
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS
    }
    expected_oldest_first = {
        method_id: "OLDEST_FIRST"
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS
    }
    expected_combination_members = {
        method_id: list(members)
        for method_id, members in (
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE6_METHOD.items()
        )
    }
    expected_candidate_counts = {
        method_id: list(counts)
        for method_id, counts in (
            SOURCE_CANDIDATE_TICKET_COUNTS_BY_SOURCE_NATIVE_WAVE6_METHOD.items()
        )
    }
    if (
        provenance.get("constructor") != CONSTRUCTOR_IDENTIFIER
        or provenance.get("source_native_protocol")
        != SOURCE_NATIVE_WAVE6_PROTOCOL
        or provenance.get("user_seed")
        != DEFAULT_SOURCE_NATIVE_WAVE6_USER_SEED
        or provenance.get("database_sha256_before")
        != provenance.get("database_sha256_after")
        or provenance.get("frozen_sources")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD
        or provenance.get("minimum_history_draws")
        != MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE6_METHOD
        or provenance.get("native_ticket_semantics")
        != NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE6_METHOD
        or provenance.get("candidate_k") != expected_none_candidate
        or provenance.get("combination_count")
        != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE6_METHOD
        or provenance.get("combination_members")
        != expected_combination_members
        or provenance.get("random_protocols")
        != RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE6_METHOD
        or provenance.get("source_candidate_ticket_counts")
        != expected_candidate_counts
        or provenance.get("source_history_order")
        != expected_oldest_first
        or provenance.get("execution_status_counts_by_method")
        != EXPECTED_STATUS_COUNTS_BY_METHOD
    ):
        raise EvidenceBuildError("source provenance contract changed")


def build_evidence(
    *,
    input_file: Path,
    repeat_input_file: Path,
    report_directory: Path,
    repeat_report_directory: Path,
    parity_file: Path,
) -> dict[str, object]:
    document, raw_input = _read_json(input_file)
    repeat_document, raw_repeat_input = _read_json(repeat_input_file)
    if raw_repeat_input != raw_input or repeat_document != document:
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
    output_checksums = _read_checksums(report_directory)
    repeat_checksums = _read_checksums(repeat_report_directory)
    if (
        raw_repeat_report != raw_report
        or repeat_report != report
        or repeat_checksums != output_checksums
    ):
        raise EvidenceBuildError(
            "repeat backtest outputs are not byte-identical"
        )
    _validate_report_contract(
        document=document,
        raw_input=raw_input,
        report=report,
    )
    provenance_raw = document.get("source_provenance")
    if not isinstance(provenance_raw, dict):
        raise EvidenceBuildError("source provenance is missing")
    provenance = cast(dict[str, Any], provenance_raw)
    _validate_provenance(provenance)
    parity, raw_parity = _read_json(parity_file)
    parity_summary = _validate_parity(
        parity=parity,
        raw_parity=raw_parity,
        dataset_sha256=document.get("dataset_sha256"),
    )

    universe_raw = report.get("universe")
    if not isinstance(universe_raw, list):
        raise EvidenceBuildError("report universe is missing")
    catalog_by_method: dict[str, tuple[str, str]] = {}
    for candidate in cast(list[object], universe_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("report universe row is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id in SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS:
            catalog_by_method[cast(str, method_id)] = (
                cast(str, row["strategy_id"]),
                cast(str, row["strategy_version"]),
            )
    if set(catalog_by_method) != set(
        SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS
    ):
        raise EvidenceBuildError("wave-6 methods leave the 221 universe")
    method_by_strategy = {
        strategy_id: method_id
        for method_id, (strategy_id, _version) in catalog_by_method.items()
    }

    executions_raw = document.get("executions")
    if not isinstance(executions_raw, list):
        raise EvidenceBuildError("executions are missing")
    status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    successful_targets: dict[str, list[str]] = defaultdict(list)
    native_counts: dict[str, set[int]] = defaultdict(set)
    first_success_fixtures: dict[str, object] = {}
    for candidate in cast(list[object], executions_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("execution row is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = method_by_strategy.get(
            cast(str, row.get("strategy_id"))
        )
        if method_id is None:
            raise EvidenceBuildError(
                "execution strategy is outside wave 6"
            )
        status = cast(str, row.get("status"))
        status_counts[method_id][status] += 1
        if status == "OK":
            native_count = row.get("native_ticket_count")
            if (
                type(native_count) is not int
                or row.get("portfolio_ticket_count") != 20
                or row.get("portfolio_derivation")
                != CONSTRUCTOR_IDENTIFIER
                or row.get("candidate_k") is not None
                or row.get("combination_count")
                != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE6_METHOD[
                    method_id
                ]
            ):
                raise EvidenceBuildError(
                    "successful execution semantics changed"
                )
            generation_raw = row.get("native_generation")
            if not isinstance(generation_raw, dict):
                raise EvidenceBuildError(
                    "native generation provenance changed"
                )
            generation = cast(dict[str, object], generation_raw)
            if (
                generation.get("protocol")
                != SOURCE_NATIVE_WAVE6_PROTOCOL
                or generation.get("legacy_method_id") != method_id
                or generation.get("source_sha256")
                != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD[
                    method_id
                ]
                or generation.get("history_cutoff_draw_number")
                != row.get("history_cutoff_draw_number")
                or generation.get("random_protocol")
                != RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE6_METHOD[
                    method_id
                ]
                or generation.get("randomness_used")
                is not EXPECTED_RANDOMNESS_USED[method_id]
                or generation.get("source_history_order")
                != "OLDEST_FIRST"
                or generation.get("candidate_k") is not None
                or generation.get("combination_count") is not None
                or generation.get("source_combination_members")
                != list(
                    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE6_METHOD[
                        method_id
                    ]
                )
                or generation.get("source_candidate_ticket_counts")
                != list(
                    SOURCE_CANDIDATE_TICKET_COUNTS_BY_SOURCE_NATIVE_WAVE6_METHOD[
                        method_id
                    ]
                )
            ):
                raise EvidenceBuildError(
                    "native generation provenance changed"
                )
            target = cast(str, row["target_draw_number"])
            successful_targets[method_id].append(target)
            native_counts[method_id].add(native_count)
            if method_id not in first_success_fixtures:
                first_success_fixtures[method_id] = {
                    "combination_count": row.get("combination_count"),
                    "history_draw_count": generation[
                        "history_draw_count"
                    ],
                    "seed_digest": generation["seed_digest"],
                    "target_draw_number": target,
                    "tickets": row["native_tickets"],
                }
        elif status == "CLOSED_INSUFFICIENT_HISTORY":
            if (
                row.get("reason_code")
                != "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
            ):
                raise EvidenceBuildError(
                    "unexpected insufficient-history semantics"
                )
        else:
            raise EvidenceBuildError(
                "execution status leaves the closed contract"
            )
    normalized_status_counts = {
        method_id: dict(sorted(status_counts[method_id].items()))
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS
    }
    if normalized_status_counts != EXPECTED_STATUS_COUNTS_BY_METHOD:
        raise EvidenceBuildError("execution counts changed")
    normalized_native_counts = {
        method_id: sorted(native_counts[method_id])
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS
    }
    if normalized_native_counts != EXPECTED_NATIVE_COUNT_VALUES:
        raise EvidenceBuildError("native ticket counts changed")

    strategies: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS:
        strategy_id, strategy_version = catalog_by_method[method_id]
        targets = successful_targets[method_id]
        minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE6_METHOD[
            method_id
        ]
        strategies.append(
            {
                "candidate_k": None,
                "catalog_strategy_id": strategy_id,
                "closed_status_counts": {
                    "CLOSED_INSUFFICIENT_HISTORY": minimum
                },
                "combination_count": (
                    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE6_METHOD[
                        method_id
                    ]
                ),
                "combination_members": list(
                    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE6_METHOD[
                        method_id
                    ]
                ),
                "first_successful_target_draw": targets[0],
                "last_successful_target_draw": targets[-1],
                "legacy_method_id": method_id,
                "minimum_history_draws": minimum,
                "native_ticket_count_values": (
                    normalized_native_counts[method_id]
                ),
                "native_ticket_semantics": (
                    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE6_METHOD[
                        method_id
                    ]
                ),
                "random_protocol": (
                    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE6_METHOD[
                        method_id
                    ]
                ),
                "source_candidate_ticket_counts": list(
                    SOURCE_CANDIDATE_TICKET_COUNTS_BY_SOURCE_NATIVE_WAVE6_METHOD[
                        method_id
                    ]
                ),
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD[
                        method_id
                    ]
                ),
                "strategy_version": strategy_version,
                "successful_execution_count": len(targets),
            }
        )

    input_sha256 = hashlib.sha256(raw_input).hexdigest()
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "catalog_sha256_before_status_overlay": report[
            "catalog_sha256"
        ],
        "candidate_k_semantics": (
            "NOT_APPLICABLE_NO_SINGLE_TOP_K_CANDIDATE_CONTRACT"
        ),
        "combination_count_semantics": (
            "EXECUTION_LEVEL_SOURCE_ENTRYPOINT_OR_PARAMETER_GRID_COUNT"
        ),
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "dataset_sha256": document["dataset_sha256"],
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "first_success_fixtures": first_success_fixtures,
        "frozen_source_parity": parity_summary,
        "input_canonical_sha256": report["input_canonical_sha256"],
        "input_raw_sha256": input_sha256,
        "output_checksums": output_checksums,
        "report_file_sha256": hashlib.sha256(raw_report).hexdigest(),
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": report["report_sha256"],
        "reproducibility": {
            "input_byte_identical": True,
            "report_directory_byte_identical": True,
            "repeat_input_raw_sha256": hashlib.sha256(
                raw_repeat_input
            ).hexdigest(),
            "repeat_report_file_sha256": hashlib.sha256(
                raw_repeat_report
            ).hexdigest(),
        },
        "source_database_sha256_after": provenance[
            "database_sha256_after"
        ],
        "source_database_sha256_before": provenance[
            "database_sha256_before"
        ],
        "source_native_protocol": SOURCE_NATIVE_WAVE6_PROTOCOL,
        "source_read_mode": provenance["source_read_mode"],
        "strategies": strategies,
        "supplemented_low_max_draw_count": provenance[
            "replay_truth_supplemented_draw_count"
        ],
        "target_draw_count": EXPECTED_TARGET_COUNT,
        "user_seed": DEFAULT_SOURCE_NATIVE_WAVE6_USER_SEED,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument(
        "--repeat-input-file",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--report-directory",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--repeat-report-directory",
        type=Path,
        required=True,
    )
    parser.add_argument("--parity-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = build_evidence(
        input_file=args.input_file,
        repeat_input_file=args.repeat_input_file,
        report_directory=args.report_directory,
        repeat_report_directory=args.repeat_report_directory,
        parity_file=args.parity_file,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(evidence) + b"\n")


if __name__ == "__main__":
    main()
