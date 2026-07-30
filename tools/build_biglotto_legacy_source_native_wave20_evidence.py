#!/usr/bin/env python3
"""Build checked evidence for the twentieth BIG_LOTTO source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave20 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE20_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE20_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE20_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE20_METHOD,
    SOURCE_NATIVE_WAVE20_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE20_METHOD,
    ZONE_BALANCE_500_METHOD_ID,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave20 import (
    MATERIALIZATION_SCHEMA_VERSION,
)
from verify_biglotto_legacy_source_native_wave20_parity import (
    FROZEN_SOURCE_COMMIT,
    PARITY_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE20_EVIDENCE_V1"
)
BASE_CATALOG_SHA256 = (
    "9d5bbcc15bc584b3bbda51bf38ad49a5e0e93b7f30ff38bfc88d82a67d9c8261"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "b0eb82554a5f42283544935cdfe2f5857f6012385e790e052f01eb50862eb695"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "34283b286fae8c98a56efc1fa752237313eb74a2d416634814298ecd8698a5a3"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "663bbb5ae988825986ded3bfc4db7e568bcacd2b4834354810d8a0f2e6416d69"
)
EXPECTED_REPORT_SHA256 = (
    "5da4175b54fc75ee0b484a549acfef7eeb52b4381e08a80a812f38db9200e143"
)
EXPECTED_PARITY_SHA256 = (
    "7d8bf265c3bdc7229966f637a60b10c363afda57c4f2d2cab70b0641430f2365"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 43,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 136,
}
EXPECTED_PRE_OVERLAY_PROGRESS = {
    "backtested_count": 44,
    "closed_count": 37,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 135,
    "reproduced_count": 44,
    "total_strategy_count": 221,
    "uncompleted_count": 135,
}


class EvidenceBuildError(ValueError):
    """Wave-20 evidence inputs violate the frozen contract."""


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
    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise EvidenceBuildError("base catalog records are missing")
    found: list[dict[str, Any]] = []
    for candidate in cast(list[object], records_raw):
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        if row.get("legacy_method_id") == ZONE_BALANCE_500_METHOD_ID:
            found.append(row)
    if (
        len(found) != 1
        or found[0].get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or found[0].get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE20_METHOD[
            ZONE_BALANCE_500_METHOD_ID
        ]
    ):
        raise EvidenceBuildError("wave-20 catalog identity changed")


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
    executions_raw = document.get("executions")
    if not isinstance(executions_raw, list):
        raise EvidenceBuildError("full input executions are missing")
    executions = cast(list[object], executions_raw)
    if len(executions) != 2149:
        raise EvidenceBuildError("full input execution count changed")

    statuses: Counter[str] = Counter()
    duplicate_counts: set[int] = set()
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
        duplicate_count = native.get("native_duplicate_ticket_count")
        if (
            row.get("candidate_k") is not None
            or row.get("combination_count") != 4
            or row.get("native_ticket_count") != 5
            or native.get("legacy_method_id")
            != ZONE_BALANCE_500_METHOD_ID
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE20_METHOD[
                ZONE_BALANCE_500_METHOD_ID
            ]
            or native.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or native.get("native_ticket_count") != 5
            or native.get("source_candidate_ticket_counts")
            != [1, 1, 1, 1]
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE20_METHOD[
                    ZONE_BALANCE_500_METHOD_ID
                ]
            ]
            or type(duplicate_count) is not int
            or not 1 <= duplicate_count <= 4
            or len(cast(list[object], row.get("native_tickets", [])))
            != 5
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError("native execution evidence changed")
        native_tickets = cast(
            list[object],
            row["native_tickets"],
        )
        if native_tickets[0] != native_tickets[4]:
            raise EvidenceBuildError(
                "frozen repeated 500-window ticket was not preserved"
            )
        duplicate_counts.add(duplicate_count)

    if dict(sorted(statuses.items())) != {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    } or duplicate_counts != {1, 2, 3, 4}:
        raise EvidenceBuildError("execution status evidence changed")
    return {
        "candidate_k": None,
        "closed_status_counts": {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
        },
        "combination_count": 4,
        "combination_members": list(
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE20_METHOD[
                ZONE_BALANCE_500_METHOD_ID
            ]
        ),
        "legacy_method_id": ZONE_BALANCE_500_METHOD_ID,
        "minimum_history_draws": 1,
        "native_duplicate_ticket_count_values": sorted(
            duplicate_counts
        ),
        "native_ticket_count": 5,
        "native_ticket_semantics": (
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE20_METHOD[
                ZONE_BALANCE_500_METHOD_ID
            ]
        ),
        "ok_execution_count": 2148,
        "random_protocol": "NONE_DETERMINISTIC",
        "source_history_order": (
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE20_METHOD[
                ZONE_BALANCE_500_METHOD_ID
            ]
        ),
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE20_METHOD[
                ZONE_BALANCE_500_METHOD_ID
            ]
        ),
    }


def _validate_report(
    path: Path,
    *,
    expected_input_sha256: str,
) -> tuple[dict[str, str], str]:
    report_path = path / "biglotto_multi_ticket_backtest_report.json"
    report, raw = _read_json(report_path)
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_REPORT_FILE_SHA256
        or report.get("report_sha256") != EXPECTED_REPORT_SHA256
        or report.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or report.get("input_raw_sha256")
        != expected_input_sha256
        or report.get("input_canonical_sha256")
        != EXPECTED_INPUT_CANONICAL_SHA256
        or report.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or report.get("target_draw_count") != 2149
        or report.get("progress") != EXPECTED_PRE_OVERLAY_PROGRESS
        or report.get("portfolio_contract")
        != {
            "candidate_k_is_ticket_count": False,
            "combination_count_is_ticket_count": False,
            "prefix_counts": [5, 10, 15, 20],
            "same_ordered_20_portfolio_for_every_prefix": True,
        }
    ):
        raise EvidenceBuildError("report identity changed")
    audit_raw = report.get("execution_audit")
    if not isinstance(audit_raw, list):
        raise EvidenceBuildError("report audit is missing")
    statuses = Counter(
        cast(dict[str, Any], row).get("status")
        for row in cast(list[object], audit_raw)
        if isinstance(row, dict)
    )
    if statuses != {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    }:
        raise EvidenceBuildError("report execution coverage changed")

    checksums: dict[str, str] = {}
    for artifact in sorted(path.iterdir(), key=lambda item: item.name):
        if artifact.is_file():
            checksums[artifact.name] = hashlib.sha256(
                artifact.read_bytes()
            ).hexdigest()
    if (
        checksums.get("biglotto_multi_ticket_backtest_report.json")
        != EXPECTED_REPORT_FILE_SHA256
        or checksums.get("SHA256SUMS")
        != "bbbcd1c710da505142edfd81bb266502c004373cc64c6349ce771633f1ebac5d"
    ):
        raise EvidenceBuildError("report checksums changed")
    return checksums, cast(str, report["report_sha256"])


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or parity.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or parity.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or parity.get("case_count") != 4
        or parity.get("status") != "PASS"
        or parity.get("database_sha256")
        != EXPECTED_DATABASE_SHA256
    ):
        raise EvidenceBuildError("parity evidence changed")
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
    checksums_a, report_sha_a = _validate_report(
        report_a,
        expected_input_sha256=EXPECTED_INPUT_SHA256,
    )
    checksums_b, report_sha_b = _validate_report(
        report_b,
        expected_input_sha256=EXPECTED_INPUT_SHA256,
    )
    if checksums_a != checksums_b or report_sha_a != report_sha_b:
        raise EvidenceBuildError(
            "repeat report directory is not byte-identical"
        )
    parity_document = _validate_parity(parity)
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "candidate_k_semantics": (
            "NOT_APPLICABLE_NO_PRE_TICKET_CANDIDATE_K"
        ),
        "combination_count_semantics": (
            "FOUR_WINDOW_CONFIGURATIONS_DISTINCT_FROM_FIVE_"
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
        "source_native_protocol": SOURCE_NATIVE_WAVE20_PROTOCOL,
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
