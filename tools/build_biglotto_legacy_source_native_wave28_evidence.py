#!/usr/bin/env python3
"""Build compact evidence for the wave-28 causal source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave28 import (
    DECLARED_NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE28_METHOD,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE28_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE28_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE28_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE28_METHOD,
    SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE28_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE28_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave28 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE28_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "39c5335761c4dbf9e655d2c5aa003617d076386ded36b4172b307889e50aaf5e"
)
BASE_CATALOG_FILE_SHA256 = (
    "d8b28cc828c3656b9640db2fd134e3ede82f5f30b5c49e9be454ca09f0ce9ed9"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "34b103708c95c848364849950ba8710280a82fa7046c737615da9b05ef76caf8"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "4f67768f44cd1f0df013deb610f26800edc5e0415232e56e4c3bee2b73edbd18"
)
EXPECTED_PARITY_SHA256 = (
    "0444356d9c419d62ffbce789a0f3d4079fbab5a3ffd9103b0769cfd9ff4b9003"
)
EXPECTED_REPORT_SHA256 = (
    "f4b3da9356ed502c649d4f2f32352b78f5d16fcc5cdaac8d8f52321ff2926682"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "0ed37127e16e3bb5e0ec22fe5f63952aafcddaeefca79eec2b55158404dcb188"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 67,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 111,
}
EXPECTED_PROGRESS = {
    "backtested_count": 70,
    "closed_count": 38,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 108,
    "reproduced_count": 70,
    "total_strategy_count": 221,
    "uncompleted_count": 108,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "51c96c429a243b4c5a61526adf90528acc29290a752000cf4fe4361f70369ac5"
    ),
    "biglotto_execution_audit.csv": (
        "bce4948570241ca4d162a768b21294a231a9ff4414072db7fc8e0dc0f7fbe6a2"
    ),
    "biglotto_full_rankings.csv": (
        "605dd601868fbc4952f4ff138fbfe7a56d5f94000271a7acca2e4a1a66978fc3"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "0ed37127e16e3bb5e0ec22fe5f63952aafcddaeefca79eec2b55158404dcb188"
    ),
    "biglotto_official_prize_distributions.csv": (
        "07a15040a9a852317598b200bd76a1a1261dba627ccf7052a3d1ea934fa116ff"
    ),
    "biglotto_strategy_universe.csv": (
        "ae489e912b112555e18d5b1fa154d1fdc1ae66dd33c0172f91bcf41d7c9a85f2"
    ),
    "biglotto_success_metrics.csv": (
        "39a41b1ad64df0e12d6c2d5326b65a5c5f414c3e732b57a0ce2d551ec9198298"
    ),
    "biglotto_top10.csv": (
        "bb877eac3794de96df71932ab1a3abc1ef0b01736e70318d3c2b111dd1422b0a"
    ),
}
EXPECTED_STATUS_BY_METHOD = {
    method_id: {"CLOSED_INSUFFICIENT_HISTORY": 1, "OK": 2148}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS
}
EXPECTED_CANDIDATE_K_DISTRIBUTIONS = {
    "tools/predict_biglotto_115000007_2bets.py": {
        15: 2,
        16: 3,
        17: 3,
        18: 10,
        19: 8,
        20: 2122,
    },
    "tools/predict_biglotto_7bets.py": {
        15: 2,
        16: 3,
        17: 3,
        18: 10,
        19: 8,
        20: 6,
        21: 9,
        22: 21,
        23: 87,
        24: 169,
        25: 391,
        26: 480,
        27: 472,
        28: 292,
        29: 147,
        30: 48,
    },
    "tools/predict_biglotto_elite7.py": {None: 2148},
}
EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTIONS = {
    "tools/predict_biglotto_115000007_2bets.py": {2: 2148},
    "tools/predict_biglotto_7bets.py": {
        4: 8,
        5: 24,
        6: 677,
        7: 1439,
    },
    "tools/predict_biglotto_elite7.py": {7: 2148},
}
EXPECTED_DUPLICATE_DISTRIBUTIONS = {
    "tools/predict_biglotto_115000007_2bets.py": {0: 2148},
    "tools/predict_biglotto_7bets.py": {0: 2148},
    "tools/predict_biglotto_elite7.py": {
        0: 2048,
        2: 46,
        3: 26,
        4: 28,
    },
}
EXPECTED_KILL_COUNT_DISTRIBUTIONS = {
    "tools/predict_biglotto_115000007_2bets.py": {0: 29, 5: 2119},
    "tools/predict_biglotto_7bets.py": {0: 29, 5: 2119},
    "tools/predict_biglotto_elite7.py": {0: 2148},
}


class EvidenceBuildError(ValueError):
    """Wave-28 evidence inputs violate the frozen contract."""


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
) -> dict[str, str]:
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
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS:
        row = by_method.get(method_id, {})
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE28_METHOD[method_id]
            or not isinstance(row.get("strategy_id"), str)
        ):
            raise EvidenceBuildError("wave-28 catalog identity changed")
        strategy_to_method[cast(str, row["strategy_id"])] = method_id
    return strategy_to_method


def _string_distribution(
    counter: Counter[int | None],
) -> dict[str, int]:
    return {
        "null" if key is None else str(key): count
        for key, count in sorted(
            counter.items(),
            key=lambda item: (
                item[0] is None,
                -1 if item[0] is None else item[0],
            ),
        )
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
    if len(executions) != 6447:
        raise EvidenceBuildError("full input execution count changed")
    statuses: dict[str, Counter[str]] = defaultdict(Counter)
    candidates: dict[str, Counter[int | None]] = defaultdict(Counter)
    ticket_counts: dict[str, Counter[int | None]] = defaultdict(Counter)
    duplicates: dict[str, Counter[int | None]] = defaultdict(Counter)
    kill_counts: dict[str, Counter[int | None]] = defaultdict(Counter)
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
        pool = cast(list[object], native.get("candidate_pool", []))
        candidate_k = native.get("candidate_pool_size")
        ticket_count = native.get("native_ticket_count")
        duplicate_count = native.get("native_duplicate_ticket_count")
        kill_numbers = native.get("kill_numbers")
        expected_candidate_k = len(pool) if pool else None
        if (
            native.get("legacy_method_id") != method_id
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE28_METHOD[method_id]
            or native.get("source_history_order")
            != SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE28_METHOD[
                method_id
            ]
            or native.get("source_history_order_detail")
            != SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE28_METHOD[
                method_id
            ]
            or native.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or candidate_k != expected_candidate_k
            or row.get("candidate_k") != candidate_k
            or row.get("combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD[
                method_id
            ]
            or native.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE28_METHOD[
                    method_id
                ]
            )
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE28_METHOD[
                    method_id
                ]
            ]
            or type(ticket_count) is not int
            or type(duplicate_count) is not int
            or not isinstance(kill_numbers, list)
            or len(cast(list[object], row.get("native_tickets", [])))
            != ticket_count
            or row.get("native_ticket_count") != ticket_count
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError("native execution evidence changed")
        candidates[method_id][cast(int | None, candidate_k)] += 1
        ticket_counts[method_id][ticket_count] += 1
        duplicates[method_id][duplicate_count] += 1
        kill_counts[method_id][len(cast(list[object], kill_numbers))] += 1
    if (
        {method: dict(value) for method, value in statuses.items()}
        != EXPECTED_STATUS_BY_METHOD
        or {method: dict(value) for method, value in candidates.items()}
        != EXPECTED_CANDIDATE_K_DISTRIBUTIONS
        or {method: dict(value) for method, value in ticket_counts.items()}
        != EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTIONS
        or {method: dict(value) for method, value in duplicates.items()}
        != EXPECTED_DUPLICATE_DISTRIBUTIONS
        or {method: dict(value) for method, value in kill_counts.items()}
        != EXPECTED_KILL_COUNT_DISTRIBUTIONS
    ):
        raise EvidenceBuildError("execution distributions changed")
    return [
        {
            "candidate_k_distribution": _string_distribution(
                candidates[method_id]
            ),
            "closed_execution_count": 1,
            "closed_reason_code_distribution": dict(
                sorted(reason_codes[method_id].items())
            ),
            "declared_native_ticket_count": (
                DECLARED_NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD[
                    method_id
                ]
            ),
            "execution_status_counts": dict(
                sorted(statuses[method_id].items())
            ),
            "kill_number_count_distribution": _string_distribution(
                kill_counts[method_id]
            ),
            "legacy_method_id": method_id,
            "minimum_history_draws": (
                MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE28_METHOD[method_id]
            ),
            "native_duplicate_ticket_count_distribution": (
                _string_distribution(duplicates[method_id])
            ),
            "native_ticket_count_distribution": _string_distribution(
                ticket_counts[method_id]
            ),
            "native_ticket_semantics": (
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE28_METHOD[
                    method_id
                ]
            ),
            "ok_execution_count": 2148,
            "source_history_order": (
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE28_METHOD[
                    method_id
                ]
            ),
            "source_history_order_detail": (
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE28_METHOD[
                    method_id
                ]
            ),
            "source_method_combination_count": (
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD[
                    method_id
                ]
            ),
            "source_sha256": (
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE28_METHOD[method_id]
            ),
        }
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS
    ]


def _validate_parity(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("status") != "PASS"
        or document.get("case_count") != 210
        or document.get("closed_parity_case_count") != 0
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("database_sha256") != EXPECTED_DATABASE_SHA256
        or len(cast(list[object], document.get("source_artifacts", [])))
        != 3
        or len(cast(list[object], document.get("support_artifacts", [])))
        != 5
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


def build_wave28_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate immutable inputs and return compact wave-28 evidence."""

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
    evidence = build_wave28_evidence(
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
