#!/usr/bin/env python3
"""Build compact evidence for the wave-33 causal source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave33 import (
    FEASIBILITY_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE33_METHOD,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE33_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE33_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE33_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE33_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE33_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE33_METHOD,
    SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE33_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE33_METHOD,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave33 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE33_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "0316f019dea91815a451d1a71481d79e910b5760c842d2223e808acf8cc2337d"
)
BASE_CATALOG_FILE_SHA256 = (
    "4cb3f616e07db272162b880b6eb4472bd2050378847bff4070f88449afacd49f"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "ea97a6d3086fad923ae9da5f2cf1c93313b27037fc9cd44575a3a1bea21a2a8b"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "6f8606c98077ed86d8fe0bd0fc10267cc9e087c60e581f2b938230a42b7f7094"
)
EXPECTED_PARITY_SHA256 = (
    "c6dbbf82db8a8e39de2b544f53b8ef5d4bd169a52c39efb4cb099c7ce429a339"
)
EXPECTED_REPORT_SHA256 = (
    "905054f4977f083cc6cc279e341a4dc2a875baa4c281fc2b1710c80458b61f3c"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "0e07096c70f12a3ef3ff9f755c85b56654ba85b0ce74924d3bcd2fece1177b88"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 76,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 102,
}
EXPECTED_PROGRESS = {
    "backtested_count": 77,
    "closed_count": 38,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 101,
    "reproduced_count": 77,
    "total_strategy_count": 221,
    "uncompleted_count": 101,
}
EXPECTED_DUPLICATE_DISTRIBUTION = {
    "2": 1028,
    "3": 266,
    "4": 854,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "a3419cc257ec4f3000f37ff6e9ced791202a2f5342bfc5b7a7684aa8a7a18704"
    ),
    "biglotto_execution_audit.csv": (
        "d7dc2b5237a5f9395407290124be5ecd85417077b70f7acf61158945b3b64ebf"
    ),
    "biglotto_full_rankings.csv": (
        "42cd5d92c9a65d475f1dc4897da4ecae656082915eb9f61c97753bcd4c80e6c6"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "0e07096c70f12a3ef3ff9f755c85b56654ba85b0ce74924d3bcd2fece1177b88"
    ),
    "biglotto_official_prize_distributions.csv": (
        "eedc64b485043d64259848d0b4b221c20085bc3ae10055756458d721795859d6"
    ),
    "biglotto_strategy_universe.csv": (
        "67e9f02bfded06219f52518479d904c77ce4dae5668ce8a41e21026b925e5b03"
    ),
    "biglotto_success_metrics.csv": (
        "ec894d56bcfda92e15276d727ecfb2fcdf76851b8251bdc8231e6ee8a3f08d2c"
    ),
    "biglotto_top10.csv": (
        "4f027629ec57ca7d3fd90185053aff5de93a600e06a671ed6516d47b1b1e8965"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-33 evidence inputs violate the frozen contract."""


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
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvidenceBuildError(f"{path.name}: invalid JSON") from exc
    if not isinstance(document, dict):
        raise EvidenceBuildError(
            f"{path.name}: top level must be an object"
        )
    return cast(dict[str, Any], document), raw


def _validate_catalog(path: Path) -> str:
    catalog, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
    ):
        raise EvidenceBuildError("base catalog identity changed")
    matches: list[dict[str, Any]] = []
    for candidate in cast(list[object], catalog.get("records", [])):
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        if row.get("legacy_method_id") == FEASIBILITY_METHOD_ID:
            matches.append(row)
    if len(matches) != 1:
        raise EvidenceBuildError("wave-33 catalog row changed")
    row = matches[0]
    if (
        row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
        or row.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE33_METHOD[
            FEASIBILITY_METHOD_ID
        ]
        or not isinstance(row.get("strategy_id"), str)
    ):
        raise EvidenceBuildError("wave-33 catalog identity changed")
    return cast(str, row["strategy_id"])


def _validate_input(
    document: dict[str, Any],
    raw: bytes,
    *,
    strategy_id: str,
) -> dict[str, object]:
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
    if len(executions) != 2149:
        raise EvidenceBuildError("full input execution count changed")
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    duplicates: Counter[int] = Counter()
    ok_count = 0
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        if row.get("strategy_id") != strategy_id:
            raise EvidenceBuildError("execution strategy changed")
        status = cast(str, row.get("status"))
        statuses[status] += 1
        if status != "OK":
            reason = row.get("reason_code")
            if not isinstance(reason, str):
                raise EvidenceBuildError("closed reason changed")
            reasons[reason] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError("native execution evidence changed")
        native = cast(dict[str, Any], native_raw)
        pools_raw = native.get("candidate_pools")
        if not isinstance(pools_raw, list):
            raise EvidenceBuildError("Top-12 candidate pool changed")
        pools = cast(list[object], pools_raw)
        if len(pools) != 1 or not isinstance(pools[0], list):
            raise EvidenceBuildError("Top-12 candidate pool changed")
        pool = cast(list[object], pools[0])
        if len(pool) != 12:
            raise EvidenceBuildError("Top-12 candidate pool changed")
        if (
            native.get("legacy_method_id") != FEASIBILITY_METHOD_ID
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE33_METHOD[
                FEASIBILITY_METHOD_ID
            ]
            or native.get("source_history_order")
            != SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE33_METHOD[
                FEASIBILITY_METHOD_ID
            ]
            or native.get("source_history_order_detail")
            != SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE33_METHOD[
                FEASIBILITY_METHOD_ID
            ]
            or native.get("candidate_k") is not None
            or row.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or row.get("combination_count") != 6
            or native.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE33_METHOD[
                    FEASIBILITY_METHOD_ID
                ]
            )
            or native.get("statistical_candidate_count") != 20
            or native.get("statistical_fallback_used") is not False
            or native.get("native_ticket_count") != 8
            or row.get("native_ticket_count") != 8
            or len(cast(list[object], row.get("native_tickets", [])))
            != 8
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE33_METHOD[
                    FEASIBILITY_METHOD_ID
                ]
            ]
        ):
            raise EvidenceBuildError("native execution semantics changed")
        duplicate_count = native.get("native_duplicate_ticket_count")
        if type(duplicate_count) is not int:
            raise EvidenceBuildError("native duplicate count changed")
        duplicates[duplicate_count] += 1
        ok_count += 1
    duplicate_distribution = {
        str(key): value for key, value in sorted(duplicates.items())
    }
    if (
        statuses != {"CLOSED_INSUFFICIENT_HISTORY": 1, "OK": 2148}
        or reasons
        != {"AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM": 1}
        or duplicate_distribution != EXPECTED_DUPLICATE_DISTRIBUTION
    ):
        raise EvidenceBuildError("wave-33 execution distribution changed")
    return {
        "candidate_k_distribution": {"null": ok_count},
        "candidate_pool_size_distribution": {"12": ok_count},
        "closed_execution_count": 1,
        "closed_reason_code_distribution": dict(sorted(reasons.items())),
        "execution_status_counts": dict(sorted(statuses.items())),
        "legacy_method_id": FEASIBILITY_METHOD_ID,
        "minimum_history_draws": (
            MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE33_METHOD[
                FEASIBILITY_METHOD_ID
            ]
        ),
        "native_duplicate_ticket_count_distribution": (
            duplicate_distribution
        ),
        "native_ticket_count": (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE33_METHOD[
                FEASIBILITY_METHOD_ID
            ]
        ),
        "native_ticket_semantics": (
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE33_METHOD[
                FEASIBILITY_METHOD_ID
            ]
        ),
        "ok_execution_count": ok_count,
        "random_protocol": (
            "WRAPPER_RANDOM_AND_NUMPY_SEED_42_BEFORE_EACH_BENCHMARK_"
            "WITH_STATISTICAL_RANDOM_RESEEDED_BY_HISTORY_LENGTH"
        ),
        "source_history_order": (
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE33_METHOD[
                FEASIBILITY_METHOD_ID
            ]
        ),
        "source_history_order_detail": (
            SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE33_METHOD[
                FEASIBILITY_METHOD_ID
            ]
        ),
        "source_method_combination_count": (
            SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE33_METHOD[
                FEASIBILITY_METHOD_ID
            ]
        ),
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE33_METHOD[
                FEASIBILITY_METHOD_ID
            ]
        ),
        "statistical_fallback_execution_count": 0,
    }


def _validate_parity(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("status") != "PASS"
        or document.get("case_count") != 65
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or not isinstance(
            document.get("frozen_source_behavior_facts"), dict
        )
        or len(cast(list[object], document.get("source_artifacts", [])))
        != 1
        or len(cast(list[object], document.get("support_artifacts", [])))
        != 4
    ):
        raise EvidenceBuildError("parity evidence changed")
    return {
        "case_count": document["case_count"],
        "frozen_source_behavior_facts": document[
            "frozen_source_behavior_facts"
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


def build_wave33_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate immutable inputs and return compact wave-33 evidence."""

    strategy_id = _validate_catalog(catalog_path)
    input_document, input_raw = _read_json(input_path)
    strategy = _validate_input(
        input_document,
        input_raw,
        strategy_id=strategy_id,
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
        "strategies": [strategy],
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
    evidence = build_wave33_evidence(
        catalog_path=args.catalog,
        input_path=args.input,
        parity_path=args.parity,
        report_path=args.report,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    if args.output.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output": str(args.output),
                "strategy_count": 1,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
