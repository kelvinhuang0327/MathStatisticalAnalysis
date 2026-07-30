#!/usr/bin/env python3
"""Build checked evidence for the twenty-second source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave22 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE22_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE22_METHOD,
    SMART_2BET_METHOD_ID,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE22_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE22_METHOD,
    SOURCE_NATIVE_WAVE22_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE22_METHOD,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave22 import (
    MATERIALIZATION_SCHEMA_VERSION,
)
from verify_biglotto_legacy_source_native_wave22_parity import (
    FROZEN_SOURCE_COMMIT,
    PARITY_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE22_EVIDENCE_V1"
)
BASE_CATALOG_SHA256 = (
    "87b00e843eca65f043e2313199ce5d984e4b433f974848da97b47cfcc64be1f2"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "35bac6eaaccac9d21c8aac87bad5cce93973129b5e6cf85773db07216b2b4bc0"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "69fb92434b65041fd193c2d80b4029998bfd0f594d3a9d873dcb08863cff76fa"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "d023ad3f9a22a8acb3828cdb1b74829382479e0c9a6a783b5c74b608ef83297f"
)
EXPECTED_REPORT_SHA256 = (
    "056df37a2a17b2b45a7f194a9b54977308e7366fe7ddbcab55b6ae4b43c0a808"
)
EXPECTED_PARITY_SHA256 = (
    "3eb74b3101a239e2f01f2b79e55bd0fb9b3f5d3c6a66db567bae1cd6d2ca8f87"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 45,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 134,
}
EXPECTED_PROGRESS = {
    "backtested_count": 46,
    "closed_count": 37,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 133,
    "reproduced_count": 46,
    "total_strategy_count": 221,
    "uncompleted_count": 133,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "4fdb23ae07fcd6f476a0226f48ce6ca8b7a934c608d998b5301236c92327f3f7"
    ),
    "biglotto_execution_audit.csv": (
        "f6153ce2f5b8e8526f368dad86b8ebf5202a40262c67619e5c3399ab9770c07b"
    ),
    "biglotto_full_rankings.csv": (
        "c969349d4fc10904e7da82c395e083544638afb2c577d629c7a8fa155602eeb5"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "d023ad3f9a22a8acb3828cdb1b74829382479e0c9a6a783b5c74b608ef83297f"
    ),
    "biglotto_official_prize_distributions.csv": (
        "0c506059b16d83de38218bd7b3aef02366076d40f1860bdcd304537d906ae064"
    ),
    "biglotto_strategy_universe.csv": (
        "7729f025a0fa1a0015c93f4104c99489ccca2b1e832107d237079e7df499a073"
    ),
    "biglotto_success_metrics.csv": (
        "ef719c1e3ca49bbe94f5872c5af3cacc605900ec0550e53fb2a1b58cc069dbe3"
    ),
    "biglotto_top10.csv": (
        "e3c6fedddf48e1ff873819dcf162756bb1daea7368a52466a8bfda4039c74ef0"
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
        if row.get("legacy_method_id") == SMART_2BET_METHOD_ID:
            found.append(row)
    if (
        len(found) != 1
        or found[0].get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or found[0].get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE22_METHOD[
            SMART_2BET_METHOD_ID
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
            != SMART_2BET_METHOD_ID
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE22_METHOD[
                SMART_2BET_METHOD_ID
            ]
            or native.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or native.get("native_ticket_count") != 2
            or len(candidates) != 2
            or candidates[1] != 49
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE22_METHOD[
                    SMART_2BET_METHOD_ID
                ]
            ]
            or len(cast(list[object], row.get("native_tickets", [])))
            != 2
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError("native execution evidence changed")
        duplicate_count = native.get("native_duplicate_ticket_count")
        frequency_count = candidates[0]
        if (
            type(duplicate_count) is not int
            or type(frequency_count) is not int
        ):
            raise EvidenceBuildError(
                "native configuration evidence changed"
            )
        duplicates[duplicate_count] += 1
        frequency_candidate_counts.append(frequency_count)

    if (
        statuses
        != {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
            "OK": 2148,
        }
        or duplicates != {0: 2148}
        or min(frequency_candidate_counts) != 6
        or max(frequency_candidate_counts) != 49
    ):
        raise EvidenceBuildError(
            "execution configuration evidence changed"
        )
    return {
        "candidate_k": None,
        "closed_status_counts": {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
        },
        "combination_count": 2,
        "combination_members": list(
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE22_METHOD[
                SMART_2BET_METHOD_ID
            ]
        ),
        "frequency_candidate_count_range": [
            min(frequency_candidate_counts),
            max(frequency_candidate_counts),
        ],
        "legacy_method_id": SMART_2BET_METHOD_ID,
        "minimum_history_draws": 1,
        "native_duplicate_ticket_count_distribution": {
            str(key): value
            for key, value in sorted(duplicates.items())
        },
        "native_ticket_count": 2,
        "native_ticket_semantics": (
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE22_METHOD[
                SMART_2BET_METHOD_ID
            ]
        ),
        "ok_execution_count": 2148,
        "random_protocol": "NONE_DETERMINISTIC",
        "source_history_order": (
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE22_METHOD[
                SMART_2BET_METHOD_ID
            ]
        ),
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE22_METHOD[
                SMART_2BET_METHOD_ID
            ]
        ),
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
            "TWO_SOURCE_PREDICTOR_CONFIGURATIONS_DISTINCT_FROM_TWO_"
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
        "source_native_protocol": SOURCE_NATIVE_WAVE22_PROTOCOL,
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
