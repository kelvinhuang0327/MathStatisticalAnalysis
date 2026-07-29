#!/usr/bin/env python3
"""Build compact evidence for the wave-40 causal source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave40 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE40_METHOD,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE40_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE40_METHOD,
    PORTFOLIO_METHOD_ID,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE40_METHOD,
    SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE40_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE40_METHOD,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave40 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE40_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "9970c56da9efc613fb9d2b033bb613dc6d6124a9227458183b303b2a369c6141"
)
BASE_CATALOG_FILE_SHA256 = (
    "f013536b311d93ee2af19f9d6041701aebc3f4fd930e073b79e301147968ad0e"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "5ae1dfd4ce5e2f96c2f0a9be48f75d5fa8195a3d066f5fee7031580a787dbc82"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "da07e6a3d12d4e9b097fdc718fb9400f5461a51e1c1ada405a08d60b1b8b6957"
)
EXPECTED_PARITY_SHA256 = (
    "30b4e3852fa1a64d2f2e433f9b1234754e80b11eb03edcbbe7efdec4d086e0ce"
)
EXPECTED_REPORT_SHA256 = (
    "1103cc021d3cae176f3c070d6e1099ff51d8463d90aa6f0cd5bdeae36bf0b8e7"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "61c8fb4d6cf88d9d542ab10e2eb0f1910e02f924629b6bedae6c792ca4a53f4f"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 64,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 74,
}
EXPECTED_PROGRESS = {
    "backtested_count": 79,
    "closed_count": 64,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 73,
    "reproduced_count": 79,
    "total_strategy_count": 221,
    "uncompleted_count": 73,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "9bdaa0f639b709e8d7635315120fe9c93eb7178d3ceab957eac31edd181ec33f"
    ),
    "biglotto_execution_audit.csv": (
        "a10e25e403a251714a56b193d46442c7200110fa99df38b99ceb8bc49a92643d"
    ),
    "biglotto_full_rankings.csv": (
        "1bbe2c18ee9c19d26aa8fb13c4f9cd862eaec88fd60de3b5970d23405d9f48b8"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "61c8fb4d6cf88d9d542ab10e2eb0f1910e02f924629b6bedae6c792ca4a53f4f"
    ),
    "biglotto_official_prize_distributions.csv": (
        "8270313ffe69b697049fcf460aecc5ad041710fdfda86ba44f217afa29089278"
    ),
    "biglotto_strategy_universe.csv": (
        "d8c9fa3b797d1961b1d16d1c61ddca4e4d5d923fed89a8a5838bc20ef0bfc6eb"
    ),
    "biglotto_success_metrics.csv": (
        "c5ab50be7ea0fecf0f1816c0a3dd00fbadff00affa4aeb3e40bb3e13073f3370"
    ),
    "biglotto_top10.csv": (
        "84ab1b0cb6b8b8161df523f844ae8819cfa2237a07c416c652cb5affe8f2cc1f"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-40 evidence inputs violate the frozen contract."""


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
        typed_candidate = cast(dict[str, Any], candidate)
        if typed_candidate.get("legacy_method_id") == PORTFOLIO_METHOD_ID:
            matches.append(typed_candidate)
    if len(matches) != 1:
        raise EvidenceBuildError("wave-40 catalog row changed")
    row = matches[0]
    if (
        row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
        or row.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE40_METHOD[
            PORTFOLIO_METHOD_ID
        ]
        or not isinstance(row.get("strategy_id"), str)
    ):
        raise EvidenceBuildError("wave-40 catalog identity changed")
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
    native_counts: Counter[int] = Counter()
    duplicates: Counter[int] = Counter()
    decisions: Counter[str] = Counter()
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
        if (
            native.get("legacy_method_id") != PORTFOLIO_METHOD_ID
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE40_METHOD[
                PORTFOLIO_METHOD_ID
            ]
            or native.get("source_history_order")
            != SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE40_METHOD[
                PORTFOLIO_METHOD_ID
            ]
            or native.get("source_history_order_detail")
            != SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE40_METHOD[
                PORTFOLIO_METHOD_ID
            ]
            or native.get("candidate_k") is not None
            or row.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or row.get("combination_count") != 3
            or native.get("source_method_combination_count") != 3
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE40_METHOD[
                    PORTFOLIO_METHOD_ID
                ]
            ]
            or native.get("randomness_used") is not False
        ):
            raise EvidenceBuildError("native execution semantics changed")
        native_count = row.get("native_ticket_count")
        duplicate_count = native.get("native_duplicate_ticket_count")
        decision_values = native.get(
            "source_duplicate_suppression_results"
        )
        typed_decisions = (
            cast(list[object], decision_values)
            if isinstance(decision_values, list)
            else []
        )
        if (
            type(native_count) is not int
            or type(duplicate_count) is not int
            or not isinstance(decision_values, list)
            or any(not isinstance(value, str) for value in typed_decisions)
            or len(cast(list[object], row.get("native_tickets", [])))
            != native_count
        ):
            raise EvidenceBuildError("native count evidence changed")
        native_counts[native_count] += 1
        duplicates[duplicate_count] += 1
        decisions[
            "+".join(cast(list[str], typed_decisions))
        ] += 1
        ok_count += 1
    if (
        statuses
        != {"CLOSED_INSUFFICIENT_HISTORY": 100, "OK": 2049}
        or reasons
        != {"AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM": 100}
        or native_counts != {4: 2049}
        or duplicates != {0: 2049}
        or decisions
        != {
            "AUXILIARY_DUPLICATE_SUPPRESSED+"
            "WINDOW50_FILL_APPENDED": 2049
        }
    ):
        raise EvidenceBuildError("wave-40 execution distribution changed")
    return {
        "candidate_k_distribution": {"null": ok_count},
        "closed_execution_count": 100,
        "closed_reason_code_distribution": dict(sorted(reasons.items())),
        "execution_status_counts": dict(sorted(statuses.items())),
        "legacy_method_id": PORTFOLIO_METHOD_ID,
        "minimum_history_draws": (
            MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE40_METHOD[
                PORTFOLIO_METHOD_ID
            ]
        ),
        "native_duplicate_ticket_count_distribution": {
            str(key): value for key, value in sorted(duplicates.items())
        },
        "native_ticket_count_distribution": {
            str(key): value for key, value in sorted(native_counts.items())
        },
        "native_ticket_count_upper_bound": (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD[
                PORTFOLIO_METHOD_ID
            ]
        ),
        "native_ticket_semantics": (
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE40_METHOD[
                PORTFOLIO_METHOD_ID
            ]
        ),
        "ok_execution_count": ok_count,
        "random_protocol": "NONE_DETERMINISTIC_NATIVE_SELECTION",
        "source_duplicate_suppression_distribution": dict(
            sorted(decisions.items())
        ),
        "source_history_order": (
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE40_METHOD[
                PORTFOLIO_METHOD_ID
            ]
        ),
        "source_history_order_detail": (
            SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE40_METHOD[
                PORTFOLIO_METHOD_ID
            ]
        ),
        "source_method_combination_count": (
            SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE40_METHOD[
                PORTFOLIO_METHOD_ID
            ]
        ),
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE40_METHOD[
                PORTFOLIO_METHOD_ID
            ]
        ),
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
        != 1
    ):
        raise EvidenceBuildError("parity evidence changed")
    return {
        "case_count": document["case_count"],
        "frozen_source_behavior_facts": document[
            "frozen_source_behavior_facts"
        ],
        "parity_file_sha256": EXPECTED_PARITY_SHA256,
        "parity_sha256": document["parity_sha256"],
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


def build_wave40_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate immutable inputs and return compact wave-40 evidence."""

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
    evidence = build_wave40_evidence(
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
