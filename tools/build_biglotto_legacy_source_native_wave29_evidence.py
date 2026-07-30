#!/usr/bin/env python3
"""Build compact evidence for the wave-29 causal source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave29 import (
    ELITE_CLAIM_VERIFIER_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE29_METHOD,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE29_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE29_METHOD,
    OPTIMIZED_BACKTEST_METHOD_ID,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave29 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE29_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "d35ea79ecccbc89dbe8584b85f7d9f621d075cabda769df94880fd31ad97e079"
)
BASE_CATALOG_FILE_SHA256 = (
    "aa9f313aac761aef4d9dcd542b0e6ee31629107174717d16b95aac9904ffd852"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "76e8b96d8c821c5fd54dcb4158afd983b5349ae88b0f7b27a87590965653401a"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "a46fa574e4ae9f59c41f95f01a7b0c269ce70824aaee2ff282ed67cd45e67afd"
)
EXPECTED_PARITY_SHA256 = (
    "90b87ad2abaafae49e4766f6025febf07bea2c22178947dd0500bb4d9cd3a35d"
)
EXPECTED_REPORT_SHA256 = (
    "721f9c3a72f83846a924ae0d09e0c47017597fd6745a139c69a55bfbe0092e2b"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "d70168d6c0a6f59a20745fbdab555af8a3294d07b57fec9c676ea7ee32d01a72"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 70,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 108,
}
EXPECTED_PROGRESS = {
    "backtested_count": 72,
    "closed_count": 38,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 106,
    "reproduced_count": 72,
    "total_strategy_count": 221,
    "uncompleted_count": 106,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "2ed7416a7bd7497cda7d749810e5d6841e177fc967e4bb247b9f32d9b4b284f9"
    ),
    "biglotto_execution_audit.csv": (
        "6b743c7ea108fd338b5482ea5e38690057c5dd5dec76802e407781fd6ad3ac7a"
    ),
    "biglotto_full_rankings.csv": (
        "52fc51cb32a544f165d20a646e020e412d3415a3f356bdaf1aeb4a27698fdae9"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "d70168d6c0a6f59a20745fbdab555af8a3294d07b57fec9c676ea7ee32d01a72"
    ),
    "biglotto_official_prize_distributions.csv": (
        "1d76926f4b36dd938e6ebfc0b90ae5f5fc569c6aeabf84f0aa00a8476115cef1"
    ),
    "biglotto_strategy_universe.csv": (
        "71010c0190cbfda8198926a251925d94e2912ac9fa1ab473fea1f4f45debfdc8"
    ),
    "biglotto_success_metrics.csv": (
        "0e7390a994846df9d6b92cef8025286e1dc210d131ef13dcbbbe6e692d05b603"
    ),
    "biglotto_top10.csv": (
        "faedf2bf72a73ac69856a744fc90fcc2e22a60f567f63b4195bb150f7e8136e4"
    ),
}
EXPECTED_STATUS_BY_METHOD = {
    method_id: {"CLOSED_INSUFFICIENT_HISTORY": 1, "OK": 2148}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
}
EXPECTED_DUPLICATE_DISTRIBUTION = {
    0: 1515,
    1: 424,
    2: 137,
    3: 31,
    4: 41,
}
EXPECTED_ALL_FAILURE_BEHAVIOR = {
    OPTIMIZED_BACKTEST_METHOD_ID: "UNSEEDED_RANDOM_FALLBACK",
    ELITE_CLAIM_VERIFIER_METHOD_ID: "NO_CONSENSUS_TICKET",
}


class EvidenceBuildError(ValueError):
    """Wave-29 evidence inputs violate the frozen contract."""


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


def _validate_catalog(path: Path) -> dict[str, str]:
    catalog, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
    ):
        raise EvidenceBuildError("base catalog identity changed")
    records = cast(list[object], catalog.get("records", []))
    by_method = {
        cast(str, row["legacy_method_id"]): row
        for candidate in records
        if isinstance(candidate, dict)
        for row in [cast(dict[str, Any], candidate)]
        if isinstance(row.get("legacy_method_id"), str)
    }
    strategy_to_method: dict[str, str] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS:
        row = by_method.get(method_id, {})
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD[method_id]
            or not isinstance(row.get("strategy_id"), str)
        ):
            raise EvidenceBuildError("wave-29 catalog identity changed")
        strategy_to_method[cast(str, row["strategy_id"])] = method_id
    return strategy_to_method


def _string_distribution(counter: Counter[int]) -> dict[str, int]:
    return {
        str(key): count for key, count in sorted(counter.items())
    }


def _validate_input(
    document: dict[str, Any],
    raw: bytes,
    *,
    strategy_to_method: dict[str, str],
) -> list[dict[str, object]]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_INPUT_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest()
        != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", []))) != 2149
    ):
        raise EvidenceBuildError("full input identity changed")
    executions = cast(list[object], document.get("executions", []))
    if len(executions) != 4298:
        raise EvidenceBuildError("full input execution count changed")
    statuses: dict[str, Counter[str]] = defaultdict(Counter)
    duplicates: dict[str, Counter[int]] = defaultdict(Counter)
    reason_codes: dict[str, Counter[str]] = defaultdict(Counter)
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = strategy_to_method.get(cast(str, row.get("strategy_id")))
        if method_id is None:
            raise EvidenceBuildError("execution strategy changed")
        status = cast(str, row.get("status"))
        statuses[method_id][status] += 1
        if status != "OK":
            reason_code = row.get("reason_code")
            if not isinstance(reason_code, str):
                raise EvidenceBuildError("closed reason changed")
            reason_codes[method_id][reason_code] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError("native execution evidence changed")
        native = cast(dict[str, Any], native_raw)
        duplicate_count = native.get("native_duplicate_ticket_count")
        if (
            native.get("legacy_method_id") != method_id
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD[method_id]
            or native.get("source_history_order")
            != SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE29_METHOD[
                method_id
            ]
            or native.get("source_history_order_detail")
            != SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE29_METHOD[
                method_id
            ]
            or native.get("candidate_k") is not None
            or native.get("candidate_pool_size") is not None
            or native.get("candidate_pool") != []
            or row.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or row.get("combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD[
                method_id
            ]
            or native.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE29_METHOD[
                    method_id
                ]
            )
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE29_METHOD[
                    method_id
                ]
            ]
            or native.get("all_base_methods_failed_behavior")
            != EXPECTED_ALL_FAILURE_BEHAVIOR[method_id]
            or row.get("native_ticket_count")
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD[
                method_id
            ]
            or len(cast(list[object], row.get("native_tickets", [])))
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD[
                method_id
            ]
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
            or type(duplicate_count) is not int
        ):
            raise EvidenceBuildError("native execution evidence changed")
        duplicates[method_id][duplicate_count] += 1
    if (
        {method: dict(value) for method, value in statuses.items()}
        != EXPECTED_STATUS_BY_METHOD
        or any(
            dict(duplicates[method_id])
            != EXPECTED_DUPLICATE_DISTRIBUTION
            for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
        )
    ):
        raise EvidenceBuildError("execution distributions changed")
    return [
        {
            "all_base_methods_failed_behavior": (
                EXPECTED_ALL_FAILURE_BEHAVIOR[method_id]
            ),
            "candidate_k_distribution": {"null": 2148},
            "closed_execution_count": 1,
            "closed_reason_code_distribution": dict(
                sorted(reason_codes[method_id].items())
            ),
            "execution_status_counts": dict(
                sorted(statuses[method_id].items())
            ),
            "legacy_method_id": method_id,
            "minimum_history_draws": (
                MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE29_METHOD[method_id]
            ),
            "native_duplicate_ticket_count_distribution": (
                _string_distribution(duplicates[method_id])
            ),
            "native_ticket_count": (
                NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD[
                    method_id
                ]
            ),
            "native_ticket_semantics": (
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE29_METHOD[
                    method_id
                ]
            ),
            "ok_execution_count": 2148,
            "source_history_order": (
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE29_METHOD[
                    method_id
                ]
            ),
            "source_history_order_detail": (
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE29_METHOD[
                    method_id
                ]
            ),
            "source_method_combination_count": (
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD[
                    method_id
                ]
            ),
            "source_sha256": (
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD[method_id]
            ),
        }
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
    ]


def _validate_parity(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    expected_behavior_facts = {
        OPTIMIZED_BACKTEST_METHOD_ID: {
            "all_base_methods_failed_behavior": "UNSEEDED_RANDOM_FALLBACK",
            "random_sample_fallback_call_count": 1,
        },
        ELITE_CLAIM_VERIFIER_METHOD_ID: {
            "all_base_methods_failed_behavior": "NO_CONSENSUS_TICKET",
            "random_sample_fallback_call_count": 0,
        },
    }
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("status") != "PASS"
        or document.get("case_count") != 130
        or document.get("closed_parity_case_count") != 0
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("database_sha256") != EXPECTED_DATABASE_SHA256
        or document.get("frozen_source_behavior_facts")
        != expected_behavior_facts
        or len(cast(list[object], document.get("source_artifacts", [])))
        != 2
        or len(cast(list[object], document.get("support_artifacts", [])))
        != 4
    ):
        raise EvidenceBuildError("parity evidence changed")
    return {
        "case_count": document["case_count"],
        "closed_parity_case_count": document[
            "closed_parity_case_count"
        ],
        "frozen_source_behavior_facts": document[
            "frozen_source_behavior_facts"
        ],
        "parity_instrumentation": document["parity_instrumentation"],
        "parity_sha256": EXPECTED_PARITY_SHA256,
        "source_artifacts": document["source_artifacts"],
        "status": document["status"],
        "support_artifacts": document["support_artifacts"],
    }


def _validate_report(
    document: dict[str, Any],
    raw: bytes,
    *,
    report_directory: Path,
) -> None:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_REPORT_FILE_SHA256
        or document.get("report_sha256") != EXPECTED_REPORT_SHA256
        or document.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or document.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or document.get("input_raw_sha256") != EXPECTED_INPUT_SHA256
        or document.get("input_canonical_sha256")
        != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or document.get("target_draw_count") != 2149
        or document.get("progress") != EXPECTED_PROGRESS
    ):
        raise EvidenceBuildError("pre-overlay report identity changed")
    actual_checksums = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in report_directory.iterdir()
        if path.is_file()
    }
    if actual_checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("pre-overlay report checksums changed")


def build_wave29_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate immutable inputs and return compact wave-29 evidence."""

    strategy_to_method = _validate_catalog(catalog_path)
    input_document, input_raw = _read_json(input_path)
    strategies = _validate_input(
        input_document,
        input_raw,
        strategy_to_method=strategy_to_method,
    )
    parity_document, parity_raw = _read_json(parity_path)
    parity = _validate_parity(parity_document, parity_raw)
    report_document, report_raw = _read_json(report_path)
    _validate_report(
        report_document,
        report_raw,
        report_directory=report_path.parent,
    )
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "dataset_sha256": EXPECTED_DATABASE_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "input_canonical_sha256": EXPECTED_INPUT_CANONICAL_SHA256,
        "input_raw_sha256": EXPECTED_INPUT_SHA256,
        "materialization_schema_version": MATERIALIZATION_SCHEMA_VERSION,
        "parity": parity,
        "report_checksums": EXPECTED_REPORT_CHECKSUMS,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "strategies": strategies,
        "target_draw_count": 2149,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--parity", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = build_wave29_evidence(
        catalog_path=args.catalog,
        input_path=args.input,
        parity_path=args.parity,
        report_path=args.report,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output": str(args.output),
                "strategy_count": len(
                    cast(list[object], evidence["strategies"])
                ),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
