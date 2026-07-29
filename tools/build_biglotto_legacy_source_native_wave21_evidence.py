#!/usr/bin/env python3
"""Build checked evidence for the twenty-first source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave21 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE21_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE21_METHOD,
    POST_SELECTION_FILTER_METHOD_ID,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE21_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE21_METHOD,
    SOURCE_NATIVE_WAVE21_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE21_METHOD,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave21 import (
    MATERIALIZATION_SCHEMA_VERSION,
)
from verify_biglotto_legacy_source_native_wave21_parity import (
    FROZEN_SOURCE_COMMIT,
    PARITY_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE21_EVIDENCE_V1"
)
BASE_CATALOG_SHA256 = (
    "41dbed7938e716dad58bfea74fe6d2b3cf471dba030aba111314438bfb7d2d0e"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "fa3a2909fa5eba3712d625de318805dd5295228d186b9cd9920d5b906d7bf62a"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "48c829a22e917f718b97795ffe27abcd825f810bfa50cdba0a2f58a79b127ef8"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "0fae98881bc71fa015b6199cd626bb798318df2c9e00a0cecf99afb3505a38db"
)
EXPECTED_REPORT_SHA256 = (
    "58fd85c567cc65d406a2e9da39524a66250d7d67baf73021f0fbe2df90f615d0"
)
EXPECTED_PARITY_SHA256 = (
    "a8b41f349dadc54dd38f9e61a96bc46c97ade90fad14013ba9aa787aba80e00c"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 44,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 135,
}
EXPECTED_PROGRESS = {
    "backtested_count": 45,
    "closed_count": 37,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 134,
    "reproduced_count": 45,
    "total_strategy_count": 221,
    "uncompleted_count": 134,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "d602364d87f3d2b90d2a60f5a25b48e0aacf217cccbad06094cdd26ae18bd02a"
    ),
    "biglotto_execution_audit.csv": (
        "b2b33f38d849f6a91ce81cda2db0896fcf65c120c5230d1124d927b4c18c5563"
    ),
    "biglotto_full_rankings.csv": (
        "f9f3e74b4ac90e76178d7170d94eb5b95532a29821c6ea161625566de1496e6c"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "0fae98881bc71fa015b6199cd626bb798318df2c9e00a0cecf99afb3505a38db"
    ),
    "biglotto_official_prize_distributions.csv": (
        "0f88611eeb8eecb4e6be9321c998ee8265eab9ab314349483571d98d83f1d2a9"
    ),
    "biglotto_strategy_universe.csv": (
        "cc2586d69e4087cf13019392b6d3b81f89f0ff463e9fc81a8b7832c914375ca8"
    ),
    "biglotto_success_metrics.csv": (
        "da67a4d00a2a3fac067714ac4437be1cad8de53381e103b39fdf57fbc00021b7"
    ),
    "biglotto_top10.csv": (
        "d4b2875d18688f5a928d3f07b54ba7bd1076f9a38de06ac95c3271c027bf1ef6"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-21 evidence inputs violate the frozen contract."""


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


def _validate_catalog(path: Path) -> None:
    catalog, _raw = _read_json(path)
    if (
        catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
    ):
        raise EvidenceBuildError("base catalog identity changed")
    records = cast(list[object], catalog.get("records", []))
    found: list[dict[str, Any]] = []
    for candidate in records:
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        if row.get("legacy_method_id") == POST_SELECTION_FILTER_METHOD_ID:
            found.append(row)
    if (
        len(found) != 1
        or found[0].get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or found[0].get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE21_METHOD[
            POST_SELECTION_FILTER_METHOD_ID
        ]
    ):
        raise EvidenceBuildError("wave-21 catalog identity changed")


def _validate_input(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_INPUT_SHA256
        or document.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", []))) != 2149
    ):
        raise EvidenceBuildError("full input identity changed")
    executions = cast(list[object], document.get("executions", []))
    if len(executions) != 2149:
        raise EvidenceBuildError("full input execution count changed")

    statuses: Counter[str] = Counter()
    duplicates: Counter[int] = Counter()
    retries: Counter[bool] = Counter()
    fallbacks: Counter[bool] = Counter()
    danger_lengths: Counter[int] = Counter()
    frequency_candidate_counts: list[int] = []
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        status = row.get("status")
        if type(status) is not str:
            raise EvidenceBuildError("execution status is invalid")
        statuses[status] += 1
        if status != "OK":
            if status != "CLOSED_INSUFFICIENT_HISTORY":
                raise EvidenceBuildError("unexpected execution closure")
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError("native execution evidence changed")
        native = cast(dict[str, Any], native_raw)
        candidates = cast(
            list[object],
            native.get("source_candidate_ticket_counts", []),
        )
        if (
            row.get("candidate_k") is not None
            or row.get("combination_count") != 2
            or row.get("native_ticket_count") != 2
            or native.get("legacy_method_id")
            != POST_SELECTION_FILTER_METHOD_ID
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE21_METHOD[
                POST_SELECTION_FILTER_METHOD_ID
            ]
            or native.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or native.get("native_ticket_count") != 2
            or len(candidates) != 2
            or candidates[1] != 49
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE21_METHOD[
                    POST_SELECTION_FILTER_METHOD_ID
                ]
            ]
            or len(cast(list[object], row.get("native_tickets", [])))
            != 2
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError("native execution evidence changed")
        duplicate_count = native.get("native_duplicate_ticket_count")
        retry_used = native.get("zone_retry_used")
        fallback_used = native.get("zone_fallback_used")
        danger_numbers = cast(
            list[object],
            native.get("danger_numbers", []),
        )
        frequency_count = candidates[0]
        if (
            type(duplicate_count) is not int
            or type(retry_used) is not bool
            or type(fallback_used) is not bool
            or type(frequency_count) is not int
        ):
            raise EvidenceBuildError("native branch evidence changed")
        duplicates[duplicate_count] += 1
        retries[retry_used] += 1
        fallbacks[fallback_used] += 1
        danger_lengths[len(danger_numbers)] += 1
        frequency_candidate_counts.append(frequency_count)

    if (
        statuses
        != {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
            "OK": 2148,
        }
        or duplicates != {0: 2136, 1: 12}
        or retries != {False: 2089, True: 59}
        or fallbacks != {False: 2148}
        or danger_lengths != {0: 1936, 1: 207, 2: 5}
        or min(frequency_candidate_counts) != 6
        or max(frequency_candidate_counts) != 49
    ):
        raise EvidenceBuildError("execution branch evidence changed")
    return {
        "candidate_k": None,
        "closed_status_counts": {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
        },
        "combination_count": 2,
        "combination_members": list(
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE21_METHOD[
                POST_SELECTION_FILTER_METHOD_ID
            ]
        ),
        "danger_number_count_distribution": {
            str(key): value
            for key, value in sorted(danger_lengths.items())
        },
        "frequency_candidate_count_range": [
            min(frequency_candidate_counts),
            max(frequency_candidate_counts),
        ],
        "legacy_method_id": POST_SELECTION_FILTER_METHOD_ID,
        "minimum_history_draws": 1,
        "native_duplicate_ticket_count_distribution": {
            str(key): value
            for key, value in sorted(duplicates.items())
        },
        "native_ticket_count": 2,
        "native_ticket_semantics": (
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE21_METHOD[
                POST_SELECTION_FILTER_METHOD_ID
            ]
        ),
        "ok_execution_count": 2148,
        "random_protocol": "NONE_DETERMINISTIC",
        "source_history_order": (
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE21_METHOD[
                POST_SELECTION_FILTER_METHOD_ID
            ]
        ),
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE21_METHOD[
                POST_SELECTION_FILTER_METHOD_ID
            ]
        ),
        "zone_fallback_count": fallbacks[True],
        "zone_retry_count": retries[True],
    }


def _validate_report(path: Path) -> dict[str, str]:
    report_path = path / "biglotto_multi_ticket_backtest_report.json"
    report, raw = _read_json(report_path)
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_REPORT_FILE_SHA256
        or report.get("report_sha256") != EXPECTED_REPORT_SHA256
        or report.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or report.get("input_raw_sha256") != EXPECTED_INPUT_SHA256
        or report.get("input_canonical_sha256")
        != EXPECTED_INPUT_CANONICAL_SHA256
        or report.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or report.get("target_draw_count") != 2149
        or report.get("progress") != EXPECTED_PROGRESS
    ):
        raise EvidenceBuildError("report identity changed")
    audit = cast(list[object], report.get("execution_audit", []))
    statuses = Counter(
        cast(dict[str, Any], row).get("status")
        for row in audit
        if isinstance(row, dict)
    )
    if statuses != {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    }:
        raise EvidenceBuildError("report execution coverage changed")
    checksums = {
        artifact.name: hashlib.sha256(artifact.read_bytes()).hexdigest()
        for artifact in sorted(path.iterdir(), key=lambda item: item.name)
        if artifact.is_file()
    }
    if checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("report checksums changed")
    return checksums


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or parity.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or parity.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or parity.get("case_count") != 6
        or parity.get("status") != "PASS"
        or parity.get("database_sha256")
        != EXPECTED_DATABASE_SHA256
    ):
        raise EvidenceBuildError("parity evidence changed")
    cases = cast(list[object], parity.get("cases", []))
    retry_branch_found = False
    for candidate in cases:
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        if (
            row.get("zone_retry_used") is True
            and row.get("danger_numbers") == [1]
        ):
            retry_branch_found = True
    if not retry_branch_found:
        raise EvidenceBuildError("parity retry branch is missing")
    return parity


def build_evidence(
    *,
    catalog: Path,
    input_a: Path,
    input_b: Path,
    report_a: Path,
    report_b: Path,
    parity: Path,
) -> dict[str, object]:
    _validate_catalog(catalog)
    input_document_a, input_raw_a = _read_json(input_a)
    input_document_b, input_raw_b = _read_json(input_b)
    strategy = _validate_input(input_document_a, input_raw_a)
    if input_raw_a != input_raw_b:
        raise EvidenceBuildError("repeat input is not byte-identical")
    _validate_input(input_document_b, input_raw_b)
    checksums_a = _validate_report(report_a)
    checksums_b = _validate_report(report_b)
    if checksums_a != checksums_b:
        raise EvidenceBuildError(
            "repeat report directory is not byte-identical"
        )
    parity_document = _validate_parity(parity)
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "candidate_k_semantics": (
            "NOT_APPLICABLE_NO_DECLARED_PRE_TICKET_CANDIDATE_K"
        ),
        "combination_count_semantics": (
            "TWO_SOURCE_SELECTION_BRANCHES_DISTINCT_FROM_TWO_"
            "POSITIONAL_NATIVE_TICKETS"
        ),
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "input_canonical_sha256": EXPECTED_INPUT_CANONICAL_SHA256,
        "input_raw_sha256": EXPECTED_INPUT_SHA256,
        "output_checksums": checksums_a,
        "parity": parity_document,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "reproducibility": {
            "input_byte_identical": True,
            "repeat_input_raw_sha256": EXPECTED_INPUT_SHA256,
            "repeat_report_file_sha256": (
                EXPECTED_REPORT_FILE_SHA256
            ),
            "report_directory_byte_identical": True,
        },
        "source_database_sha256_after": EXPECTED_DATABASE_SHA256,
        "source_database_sha256_before": EXPECTED_DATABASE_SHA256,
        "source_native_protocol": SOURCE_NATIVE_WAVE21_PROTOCOL,
        "strategies": [strategy],
        "target_draw_count": 2149,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--input-a", required=True, type=Path)
    parser.add_argument("--input-b", required=True, type=Path)
    parser.add_argument("--report-a", required=True, type=Path)
    parser.add_argument("--report-b", required=True, type=Path)
    parser.add_argument("--parity", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    evidence = build_evidence(
        catalog=args.catalog,
        input_a=args.input_a,
        input_b=args.input_b,
        report_a=args.report_a,
        report_b=args.report_b,
        parity=args.parity,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
                "status": "PASS",
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
