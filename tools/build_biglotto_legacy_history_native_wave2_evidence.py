"""Build compact evidence for the second four-method history-native wave."""

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
from lottolab.application.legacy_history_native_portfolios_wave2 import (
    ANTI_CONSENSUS_METHOD_ID,
    CANDIDATE_K_BY_HISTORY_NATIVE_WAVE2_METHOD,
    CONCENTRATED_POOL_METHOD_ID,
    CONSTRAINT_FILTER_METHOD_ID,
    COOCCURRENCE_GRAPH_METHOD_ID,
    DEFAULT_HISTORY_NATIVE_WAVE2_USER_SEED,
    HISTORY_NATIVE_WAVE2_PROTOCOL,
    MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE2_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE2_METHOD,
    RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE2_METHOD,
    SOURCE_HISTORY_ORDER_BY_HISTORY_NATIVE_WAVE2_METHOD,
    SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE2_METHOD,
    SUPPORTED_HISTORY_NATIVE_WAVE2_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_history_native_batch_import_wave2 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_HISTORY_NATIVE_WAVE2_EVIDENCE_V1"
)
EXPECTED_TARGET_COUNT = 2149
EXPECTED_STATUS_COUNTS_BY_METHOD = {
    ANTI_CONSENSUS_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
    CONSTRAINT_FILTER_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
    COOCCURRENCE_GRAPH_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 100,
        "OK": 2049,
    },
    CONCENTRATED_POOL_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
}
EXPECTED_FIXED_NATIVE_TICKET_COUNTS = {
    ANTI_CONSENSUS_METHOD_ID: 6,
    CONSTRAINT_FILTER_METHOD_ID: 2,
    CONCENTRATED_POOL_METHOD_ID: 2,
}


class EvidenceBuildError(ValueError):
    """The wave-2 materialization/report pair violates its frozen contract."""


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
            or hashlib.sha256(candidate.read_bytes()).hexdigest() != digest
        ):
            raise EvidenceBuildError(f"checksum mismatch: {filename}")
        rows[filename] = digest
    rows["SHA256SUMS"] = hashlib.sha256(
        checksum_path.read_bytes()
    ).hexdigest()
    return dict(sorted(rows.items()))


def _valid_native_count(method_id: str, count: object) -> bool:
    if type(count) is not int:
        return False
    if method_id == COOCCURRENCE_GRAPH_METHOD_ID:
        return 1 <= count <= 4
    return count == EXPECTED_FIXED_NATIVE_TICKET_COUNTS[method_id]


def build_evidence(
    *,
    input_file: Path,
    report_directory: Path,
) -> dict[str, object]:
    document, raw_input = _read_json(input_file)
    report_path = (
        report_directory / "biglotto_multi_ticket_backtest_report.json"
    )
    report, raw_report = _read_json(report_path)
    output_checksums = _read_checksums(report_directory)
    input_sha256 = hashlib.sha256(raw_input).hexdigest()
    targets_raw = document.get("targets")
    if not isinstance(targets_raw, list):
        raise EvidenceBuildError("input targets are missing")
    if (
        document.get("schema_version") != INPUT_SCHEMA_VERSION
        or document.get("dataset_version") != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], targets_raw)) != EXPECTED_TARGET_COUNT
        or report.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version") != BACKTEST_POLICY_VERSION
        or report.get("input_raw_sha256") != input_sha256
        or report.get("target_draw_count") != EXPECTED_TARGET_COUNT
    ):
        raise EvidenceBuildError("input/report identity contract changed")
    if report.get("progress") != {
        "backtested_count": 12,
        "closed_count": 6,
        "duplicate_alias_count": 3,
        "owner_decision_required_count": 200,
        "reproduced_count": 12,
        "total_strategy_count": 221,
        "uncompleted_count": 200,
    }:
        raise EvidenceBuildError("report progress does not prove wave 2")

    provenance_raw = document.get("source_provenance")
    if not isinstance(provenance_raw, dict):
        raise EvidenceBuildError("source provenance is missing")
    provenance = cast(dict[str, Any], provenance_raw)
    if (
        provenance.get("constructor") != CONSTRUCTOR_IDENTIFIER
        or provenance.get("history_native_protocol")
        != HISTORY_NATIVE_WAVE2_PROTOCOL
        or provenance.get("user_seed")
        != DEFAULT_HISTORY_NATIVE_WAVE2_USER_SEED
        or provenance.get("database_sha256_before")
        != provenance.get("database_sha256_after")
        or provenance.get("frozen_sources")
        != SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE2_METHOD
        or provenance.get("minimum_history_draws")
        != MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE2_METHOD
        or provenance.get("native_ticket_semantics")
        != NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE2_METHOD
        or provenance.get("candidate_k")
        != CANDIDATE_K_BY_HISTORY_NATIVE_WAVE2_METHOD
        or provenance.get("random_protocols")
        != RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE2_METHOD
        or provenance.get("source_history_order")
        != SOURCE_HISTORY_ORDER_BY_HISTORY_NATIVE_WAVE2_METHOD
        or provenance.get("execution_status_counts_by_method")
        != EXPECTED_STATUS_COUNTS_BY_METHOD
    ):
        raise EvidenceBuildError("source provenance contract changed")

    universe_raw = report.get("universe")
    if not isinstance(universe_raw, list):
        raise EvidenceBuildError("report universe is missing")
    catalog_by_method: dict[str, tuple[str, str]] = {}
    for candidate in cast(list[object], universe_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("report universe row is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id in SUPPORTED_HISTORY_NATIVE_WAVE2_METHODS:
            catalog_by_method[cast(str, method_id)] = (
                cast(str, row["strategy_id"]),
                cast(str, row["strategy_version"]),
            )
    if set(catalog_by_method) != set(
        SUPPORTED_HISTORY_NATIVE_WAVE2_METHODS
    ):
        raise EvidenceBuildError("wave-2 methods leave the 221 universe")
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
        strategy_id = cast(str, row.get("strategy_id"))
        method_id = method_by_strategy.get(strategy_id)
        if method_id is None:
            raise EvidenceBuildError("execution strategy is outside wave 2")
        status = cast(str, row.get("status"))
        status_counts[method_id][status] += 1
        if status == "OK":
            native_count = row.get("native_ticket_count")
            if (
                not _valid_native_count(method_id, native_count)
                or row.get("portfolio_ticket_count") != 20
                or row.get("portfolio_derivation")
                != CONSTRUCTOR_IDENTIFIER
                or row.get("candidate_k")
                != CANDIDATE_K_BY_HISTORY_NATIVE_WAVE2_METHOD[method_id]
                or row.get("combination_count") is not None
            ):
                raise EvidenceBuildError(
                    "successful execution semantics changed"
                )
            native_tickets = row.get("native_tickets")
            if not isinstance(native_tickets, list):
                raise EvidenceBuildError(
                    "native duplicate semantics changed"
                )
            typed_native_tickets = cast(list[object], native_tickets)
            if method_id == COOCCURRENCE_GRAPH_METHOD_ID and len(
                {
                    tuple(cast(list[int], ticket))
                    for ticket in typed_native_tickets
                }
            ) != native_count:
                raise EvidenceBuildError(
                    "native duplicate semantics changed"
                )
            native_generation = row.get("native_generation")
            if not isinstance(native_generation, dict):
                raise EvidenceBuildError(
                    "native generation provenance changed"
                )
            generation = cast(dict[str, object], native_generation)
            if (
                generation.get("protocol")
                != HISTORY_NATIVE_WAVE2_PROTOCOL
                or generation.get("legacy_method_id") != method_id
                or generation.get("source_sha256")
                != SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE2_METHOD[method_id]
                or generation.get("history_cutoff_draw_number")
                != row.get("history_cutoff_draw_number")
                or generation.get("random_protocol")
                != RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE2_METHOD[method_id]
                or generation.get("source_history_order")
                != SOURCE_HISTORY_ORDER_BY_HISTORY_NATIVE_WAVE2_METHOD[
                    method_id
                ]
                or generation.get("candidate_k") is not None
                or generation.get("combination_count") is not None
            ):
                raise EvidenceBuildError(
                    "native generation provenance changed"
                )
            target = cast(str, row["target_draw_number"])
            successful_targets[method_id].append(target)
            native_counts[method_id].add(cast(int, native_count))
            if method_id not in first_success_fixtures:
                first_success_fixtures[method_id] = {
                    "candidate_k": row.get("candidate_k"),
                    "history_draw_count": generation["history_draw_count"],
                    "seed_digest": generation["seed_digest"],
                    "target_draw_number": target,
                    "tickets": typed_native_tickets,
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
        for method_id in SUPPORTED_HISTORY_NATIVE_WAVE2_METHODS
    }
    if normalized_status_counts != EXPECTED_STATUS_COUNTS_BY_METHOD:
        raise EvidenceBuildError("execution counts changed")

    strategies: list[dict[str, object]] = []
    for method_id in SUPPORTED_HISTORY_NATIVE_WAVE2_METHODS:
        strategy_id, strategy_version = catalog_by_method[method_id]
        targets = successful_targets[method_id]
        strategies.append(
            {
                "candidate_k": (
                    CANDIDATE_K_BY_HISTORY_NATIVE_WAVE2_METHOD[method_id]
                ),
                "catalog_strategy_id": strategy_id,
                "closed_status_counts": {
                    status: count
                    for status, count in normalized_status_counts[
                        method_id
                    ].items()
                    if status != "OK"
                },
                "first_successful_target_draw": targets[0],
                "last_successful_target_draw": targets[-1],
                "legacy_method_id": method_id,
                "minimum_history_draws": (
                    MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE2_METHOD[
                        method_id
                    ]
                ),
                "native_ticket_count_values": sorted(
                    native_counts[method_id]
                ),
                "native_ticket_semantics": (
                    NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE2_METHOD[
                        method_id
                    ]
                ),
                "random_protocol": (
                    RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE2_METHOD[method_id]
                ),
                "source_history_order": (
                    SOURCE_HISTORY_ORDER_BY_HISTORY_NATIVE_WAVE2_METHOD[
                        method_id
                    ]
                ),
                "source_sha256": (
                    SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE2_METHOD[method_id]
                ),
                "strategy_version": strategy_version,
                "successful_execution_count": len(targets),
            }
        )

    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "catalog_sha256_before_status_overlay": report["catalog_sha256"],
        "candidate_k_semantics": (
            "EXECUTION_LEVEL_ONLY_DISTINCT_FROM_NATIVE_TICKET_COUNT"
        ),
        "combination_count_semantics": "NOT_APPLICABLE_ALL_WAVE2_METHODS",
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "dataset_sha256": document["dataset_sha256"],
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "first_success_fixtures": first_success_fixtures,
        "history_native_protocol": HISTORY_NATIVE_WAVE2_PROTOCOL,
        "input_canonical_sha256": report["input_canonical_sha256"],
        "input_raw_sha256": input_sha256,
        "output_checksums": output_checksums,
        "report_file_sha256": hashlib.sha256(raw_report).hexdigest(),
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": report["report_sha256"],
        "source_database_sha256_after": provenance[
            "database_sha256_after"
        ],
        "source_database_sha256_before": provenance[
            "database_sha256_before"
        ],
        "source_read_mode": provenance["source_read_mode"],
        "strategies": strategies,
        "supplemented_low_max_draw_count": provenance[
            "replay_truth_supplemented_draw_count"
        ],
        "target_draw_count": EXPECTED_TARGET_COUNT,
        "user_seed": DEFAULT_HISTORY_NATIVE_WAVE2_USER_SEED,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--report-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = build_evidence(
        input_file=args.input_file,
        report_directory=args.report_directory,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_bytes(evidence) + b"\n")


if __name__ == "__main__":
    main()
