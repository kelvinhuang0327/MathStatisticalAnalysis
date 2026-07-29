"""Build compact evidence for the Core-Satellite and Zone Split batch."""

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
from lottolab.application.legacy_random_native_portfolios import (
    CORE_SATELLITE_METHOD_ID,
    CORE_SATELLITE_SOURCE_SHA256,
    DEFAULT_USER_SEED,
    RANDOM_NATIVE_PROTOCOL,
    SUPPORTED_RANDOM_NATIVE_METHODS,
    ZONE_SPLIT_METHOD_ID,
    ZONE_SPLIT_SOURCE_SHA256,
    LegacyRandomNativeRequest,
    generate_legacy_random_native_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_random_batch_import import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_RANDOM_NATIVE_EVIDENCE_V1"
EXPECTED_TARGET_COUNT = 2149
EXPECTED_SUCCESS_COUNT_PER_STRATEGY = 2148
EXPECTED_CLOSED_COUNT_PER_STRATEGY = 1
_SOURCE_SHA256_BY_METHOD = {
    CORE_SATELLITE_METHOD_ID: CORE_SATELLITE_SOURCE_SHA256,
    ZONE_SPLIT_METHOD_ID: ZONE_SPLIT_SOURCE_SHA256,
}


class EvidenceBuildError(ValueError):
    """The materialization/report pair violates the frozen batch contract."""


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
    rows["SHA256SUMS"] = hashlib.sha256(checksum_path.read_bytes()).hexdigest()
    return dict(sorted(rows.items()))


def build_evidence(
    *,
    input_file: Path,
    report_directory: Path,
) -> dict[str, object]:
    document, raw_input = _read_json(input_file)
    report_path = report_directory / "biglotto_multi_ticket_backtest_report.json"
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
        "backtested_count": 4,
        "closed_count": 0,
        "duplicate_alias_count": 3,
        "owner_decision_required_count": 214,
        "reproduced_count": 4,
        "total_strategy_count": 221,
        "uncompleted_count": 214,
    }:
        raise EvidenceBuildError("report progress does not prove this batch")
    provenance_raw = document.get("source_provenance")
    if not isinstance(provenance_raw, dict):
        raise EvidenceBuildError("source provenance is missing")
    provenance = cast(dict[str, Any], provenance_raw)
    if (
        provenance.get("constructor") != CONSTRUCTOR_IDENTIFIER
        or provenance.get("random_native_protocol") != RANDOM_NATIVE_PROTOCOL
        or provenance.get("user_seed") != DEFAULT_USER_SEED
        or provenance.get("database_sha256_before")
        != provenance.get("database_sha256_after")
        or provenance.get("frozen_sources") != _SOURCE_SHA256_BY_METHOD
    ):
        raise EvidenceBuildError("source provenance contract changed")

    executions_raw = document.get("executions")
    if not isinstance(executions_raw, list):
        raise EvidenceBuildError("executions are missing")
    executions = cast(list[object], executions_raw)
    catalog_by_method: dict[str, tuple[str, str]] = {}
    universe_raw = report.get("universe")
    if not isinstance(universe_raw, list):
        raise EvidenceBuildError("report universe is missing")
    for candidate in cast(list[object], universe_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("report universe row is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id in SUPPORTED_RANDOM_NATIVE_METHODS:
            catalog_by_method[cast(str, method_id)] = (
                cast(str, row["strategy_id"]),
                cast(str, row["strategy_version"]),
            )
    if set(catalog_by_method) != set(SUPPORTED_RANDOM_NATIVE_METHODS):
        raise EvidenceBuildError("random-native methods leave the 221 universe")
    method_by_strategy = {
        strategy_id: method_id
        for method_id, (strategy_id, _version) in catalog_by_method.items()
    }
    success_counts: Counter[str] = Counter()
    closed_counts: Counter[str] = Counter()
    successful_targets: dict[str, list[str]] = defaultdict(list)
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("execution row is invalid")
        row = cast(dict[str, Any], candidate)
        strategy_id = cast(str, row.get("strategy_id"))
        method_id = method_by_strategy.get(strategy_id)
        if method_id is None:
            raise EvidenceBuildError("execution strategy is outside the batch")
        if row.get("status") == "OK":
            if (
                row.get("native_ticket_count") != 3
                or row.get("portfolio_ticket_count") != 20
                or row.get("portfolio_derivation") != CONSTRUCTOR_IDENTIFIER
            ):
                raise EvidenceBuildError("successful execution semantics changed")
            native_generation = row.get("native_generation")
            if not isinstance(native_generation, dict):
                raise EvidenceBuildError("native generation provenance changed")
            typed_generation = cast(dict[str, object], native_generation)
            if (
                typed_generation.get("protocol") != RANDOM_NATIVE_PROTOCOL
                or typed_generation.get("legacy_method_id") != method_id
                or typed_generation.get("source_sha256")
                != _SOURCE_SHA256_BY_METHOD[method_id]
            ):
                raise EvidenceBuildError("native generation provenance changed")
            success_counts[method_id] += 1
            successful_targets[method_id].append(
                cast(str, row["target_draw_number"])
            )
        elif (
            row.get("status") == "CLOSED_INSUFFICIENT_HISTORY"
            and row.get("reason_code") == "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF"
        ):
            closed_counts[method_id] += 1
        else:
            raise EvidenceBuildError("execution status leaves the closed contract")
    if any(
        success_counts[method_id] != EXPECTED_SUCCESS_COUNT_PER_STRATEGY
        or closed_counts[method_id] != EXPECTED_CLOSED_COUNT_PER_STRATEGY
        for method_id in SUPPORTED_RANDOM_NATIVE_METHODS
    ):
        raise EvidenceBuildError("execution counts changed")

    parity_target = "115000056"
    parity_fixtures: dict[str, object] = {}
    strategy_rows: list[dict[str, object]] = []
    for method_id in SUPPORTED_RANDOM_NATIVE_METHODS:
        strategy_id, strategy_version = catalog_by_method[method_id]
        parity = generate_legacy_random_native_portfolio(
            LegacyRandomNativeRequest(
                legacy_method_id=method_id,
                target_draw_number=parity_target,
            )
        )
        parity_fixtures[method_id] = {
            "seed_digest": parity.metadata.seed_digest,
            "target_draw_number": parity_target,
            "tickets": [list(ticket) for ticket in parity.tickets],
        }
        targets = successful_targets[method_id]
        strategy_rows.append(
            {
                "catalog_strategy_id": strategy_id,
                "closed_execution_count": closed_counts[method_id],
                "first_successful_target_draw": targets[0],
                "last_successful_target_draw": targets[-1],
                "legacy_method_id": method_id,
                "native_ticket_count": 3,
                "source_sha256": _SOURCE_SHA256_BY_METHOD[method_id],
                "strategy_version": strategy_version,
                "successful_execution_count": success_counts[method_id],
            }
        )

    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "catalog_sha256_before_status_overlay": report["catalog_sha256"],
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "dataset_sha256": document["dataset_sha256"],
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "input_canonical_sha256": report["input_canonical_sha256"],
        "input_raw_sha256": input_sha256,
        "output_checksums": output_checksums,
        "parity_fixtures": parity_fixtures,
        "random_native_protocol": RANDOM_NATIVE_PROTOCOL,
        "report_file_sha256": hashlib.sha256(raw_report).hexdigest(),
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": report["report_sha256"],
        "source_database_sha256_after": provenance["database_sha256_after"],
        "source_database_sha256_before": provenance["database_sha256_before"],
        "source_read_mode": provenance["source_read_mode"],
        "strategies": strategy_rows,
        "supplemented_low_max_draw_count": provenance[
            "replay_truth_supplemented_draw_count"
        ],
        "target_draw_count": EXPECTED_TARGET_COUNT,
        "user_seed": DEFAULT_USER_SEED,
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
