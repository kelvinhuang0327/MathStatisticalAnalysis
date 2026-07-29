#!/usr/bin/env python3
"""Build compact evidence for the wave-27 causal source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave27 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE27_METHOD,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE27_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE27_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE27_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE27_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE27_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave27 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE27_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "97b459b3835353c9a3f9cea24183c488a7c50f3a4168c62f8574f8a0484650bd"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "3a0b8fb891f3cc23ef977886a4405a04b8fb0a7f217189a54d9747bdd60085e0"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "6ececab4cfa6aa98269925a9adff7e0caa3a30fbbf0f791c5657897114c385a4"
)
EXPECTED_PARITY_SHA256 = (
    "47103efd10d1aeed29e026a105ebcedf555222e395d1a8407114c53e8ea387cb"
)
EXPECTED_REPORT_SHA256 = (
    "e78e21b102ac9eee286e26799e7679db9cd55b19b56c9218b7ed0566443486a3"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "ce297fa9364a458aa7df36d8aba792fd7765d7fd0800333837940e28fb2b82ad"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 63,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 115,
}
EXPECTED_PROGRESS = {
    "backtested_count": 67,
    "closed_count": 38,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 111,
    "reproduced_count": 67,
    "total_strategy_count": 221,
    "uncompleted_count": 111,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "e1b644c00c1d794abb39aba8e19dff12952a9ebe3ac003b4cd1fbc900b762b80"
    ),
    "biglotto_execution_audit.csv": (
        "3c6b064fb5a9a532f5658ee221c6d97ce782e47126cabd2e11bfca8bed68d1ba"
    ),
    "biglotto_full_rankings.csv": (
        "7f1f9ba5decaf877278b14b3da913b6412020aba839f1fdc233924ef98d00015"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "ce297fa9364a458aa7df36d8aba792fd7765d7fd0800333837940e28fb2b82ad"
    ),
    "biglotto_official_prize_distributions.csv": (
        "fe2b4ce450c85640d8a334704e88a1cadf4fcdc53231aa9e47abda9f30c3d7b3"
    ),
    "biglotto_strategy_universe.csv": (
        "573b7a1804544c9210c58e4abd28dc2f333ed6903da7152d665876db06909a8c"
    ),
    "biglotto_success_metrics.csv": (
        "aebb53bd00316340c86bfbb690ee97286ee647694acb5599a86153fff27560d2"
    ),
    "biglotto_top10.csv": (
        "80548ccbad835f963591752d642046cf05f0a1daf733ce8ba4ed45249d70d90b"
    ),
}
EXPECTED_STATUS_BY_METHOD = {
    "lottery_api/models/biglotto_2bet_optimizer.py": {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
    "lottery_api/models/biglotto_2bet_optimizer_v2.py": {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
    "tools/verify_gemini_2bet_claim.py": {
        "CLOSED_INSUFFICIENT_HISTORY": 50,
        "OK": 2099,
    },
    "tools/verify_gemini_3bet_claim.py": {
        "CLOSED_EXECUTION_ERROR": 11,
        "CLOSED_INSUFFICIENT_HISTORY": 50,
        "OK": 2088,
    },
}
EXPECTED_CANDIDATE_K_DISTRIBUTIONS = {
    "lottery_api/models/biglotto_2bet_optimizer.py": {12: 2148},
    "lottery_api/models/biglotto_2bet_optimizer_v2.py": {
        15: 1,
        16: 4,
        17: 6,
        18: 2137,
    },
    "tools/verify_gemini_2bet_claim.py": {12: 2099},
    "tools/verify_gemini_3bet_claim.py": {
        14: 59,
        15: 260,
        16: 661,
        17: 793,
        18: 315,
    },
}
EXPECTED_DUPLICATE_DISTRIBUTIONS = {
    method_id: {0: sum(statuses.get("OK", 0) for statuses in [status])}
    for method_id, status in EXPECTED_STATUS_BY_METHOD.items()
}


class EvidenceBuildError(ValueError):
    """Wave-27 evidence inputs violate the frozen contract."""


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


def _validate_catalog(
    path: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    catalog, _raw = _read_json(path)
    if (
        catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
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
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS:
        row = by_method.get(method_id, {})
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE27_METHOD[method_id]
            or not isinstance(row.get("strategy_id"), str)
        ):
            raise EvidenceBuildError("wave-27 catalog identity changed")
        strategy_to_method[cast(str, row["strategy_id"])] = method_id
    return by_method, strategy_to_method


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
    if len(executions) != 8596:
        raise EvidenceBuildError("full input execution count changed")
    statuses: dict[str, Counter[str]] = defaultdict(Counter)
    candidates: dict[str, Counter[int]] = defaultdict(Counter)
    duplicates: dict[str, Counter[int]] = defaultdict(Counter)
    reason_codes: dict[str, Counter[str]] = defaultdict(Counter)
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        strategy_id = row.get("strategy_id")
        method_id = strategy_to_method.get(cast(str, strategy_id))
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
        pool = cast(list[object], native.get("candidate_pool", []))
        candidate_k = native.get("candidate_pool_size")
        duplicate_count = native.get("native_duplicate_ticket_count")
        if (
            native.get("legacy_method_id") != method_id
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE27_METHOD[method_id]
            or native.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or type(candidate_k) is not int
            or candidate_k != len(pool)
            or row.get("candidate_k") != candidate_k
            or row.get("combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD[
                method_id
            ]
            or row.get("native_ticket_count")
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD[
                method_id
            ]
            or native.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE27_METHOD[
                    method_id
                ]
            )
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE27_METHOD[
                    method_id
                ]
            ]
            or native.get("minimum_history_draws")
            != MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE27_METHOD[method_id]
            or type(duplicate_count) is not int
            or len(cast(list[object], row.get("native_tickets", [])))
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD[
                method_id
            ]
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError("native execution evidence changed")
        candidates[method_id][candidate_k] += 1
        duplicates[method_id][duplicate_count] += 1
    if (
        {method: dict(value) for method, value in statuses.items()}
        != EXPECTED_STATUS_BY_METHOD
        or {method: dict(value) for method, value in candidates.items()}
        != EXPECTED_CANDIDATE_K_DISTRIBUTIONS
        or {method: dict(value) for method, value in duplicates.items()}
        != EXPECTED_DUPLICATE_DISTRIBUTIONS
    ):
        raise EvidenceBuildError("execution distributions changed")
    return [
        {
            "candidate_k_distribution": {
                str(key): count
                for key, count in sorted(candidates[method_id].items())
            },
            "closed_execution_count": (
                2149 - statuses[method_id]["OK"]
            ),
            "closed_reason_code_distribution": dict(
                sorted(reason_codes[method_id].items())
            ),
            "execution_status_counts": dict(
                sorted(statuses[method_id].items())
            ),
            "legacy_method_id": method_id,
            "minimum_history_draws": (
                MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE27_METHOD[method_id]
            ),
            "native_duplicate_ticket_count_distribution": {
                str(key): count
                for key, count in sorted(duplicates[method_id].items())
            },
            "native_ticket_count": (
                NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD[
                    method_id
                ]
            ),
            "native_ticket_semantics": (
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE27_METHOD[
                    method_id
                ]
            ),
            "ok_execution_count": statuses[method_id]["OK"],
            "source_history_order": (
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE27_METHOD[
                    method_id
                ]
            ),
            "source_method_combination_count": (
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD[
                    method_id
                ]
            ),
            "source_sha256": (
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE27_METHOD[method_id]
            ),
        }
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS
    ]


def _validate_parity(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("status") != "PASS"
        or document.get("case_count") != 292
        or document.get("closed_parity_case_count") != 109
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("database_sha256") != EXPECTED_DATABASE_SHA256
        or len(cast(list[object], document.get("source_artifacts", [])))
        != 4
        or len(cast(list[object], document.get("support_artifacts", [])))
        != 4
    ):
        raise EvidenceBuildError("parity evidence changed")
    return {
        "case_count": document["case_count"],
        "closed_parity_case_count": document[
            "closed_parity_case_count"
        ],
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


def build_wave27_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate immutable inputs and return compact wave-27 evidence."""

    _records, strategy_to_method = _validate_catalog(catalog_path)
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
    evidence = build_wave27_evidence(
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
