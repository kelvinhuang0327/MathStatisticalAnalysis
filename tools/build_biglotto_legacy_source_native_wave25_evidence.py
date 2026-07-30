#!/usr/bin/env python3
"""Build compact evidence for the wave-25 causal source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave25 import (
    CAG_METHOD_ID,
    CLUSTER_COVER_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE25_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE25_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE25_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE25_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE25_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE25_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE25_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS,
    TME_OPTIMIZER_METHOD_ID,
    ZDP_METHOD_ID,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave25 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE25_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "d2f4d085daa3da16b05b0fc1e6e02b1e8b3ffafcbc91480e7d970c6b6f3c6524"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "238f3d97c6ec218871f103d1385784f3802f74e98466b3e5d50564275e7b6900"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "4d5b0aa0d7d7eb3f8e7ca9622808e8f9ef681662c1d852485f134dba2f9c7d22"
)
EXPECTED_PARITY_SHA256 = (
    "90615f61aec224f72d5214b34c8bb1eec130cce83f3750472527db60729d2282"
)
EXPECTED_REPORT_SHA256 = (
    "0314b8d1e199b52443c7c3909666dbc0953e381b1446a7401a113f68e9521b6d"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "29b033e421fe22b1e1498d93bf58cc1225018952dc3a1f592c76a5b6a7e671fc"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 54,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 125,
}
EXPECTED_PROGRESS = {
    "backtested_count": 58,
    "closed_count": 37,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 121,
    "reproduced_count": 58,
    "total_strategy_count": 221,
    "uncompleted_count": 121,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "6b94df6ce292cc06c2a0679276dca3ce09f4725270d2e202cb244e3dd76e414e"
    ),
    "biglotto_execution_audit.csv": (
        "2bead237bde8316cac44d0181729eed05eb360aeb8c4126998456da2ecc3e20a"
    ),
    "biglotto_full_rankings.csv": (
        "d30ed01cd96d0f214bddec8fa3fb097cfe592cf89bc04172061b46ca41ef0e46"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "29b033e421fe22b1e1498d93bf58cc1225018952dc3a1f592c76a5b6a7e671fc"
    ),
    "biglotto_official_prize_distributions.csv": (
        "6270c5ba801bdcc1c9bc50ddaa00a72b43a34dd0a8d1bf4b7a83d71b0a326c9c"
    ),
    "biglotto_strategy_universe.csv": (
        "24d8598fccde5da53f44164122d3af6f7158303c03acad1755b06208f09a278c"
    ),
    "biglotto_success_metrics.csv": (
        "7127262bccf02cc7819bee7c1bdcdc7a6ea3fefe47636e324971bf03f074bb57"
    ),
    "biglotto_top10.csv": (
        "25022abb2ff6ebb2383a18d445d25167b2b2731ab781fc8cd23023e3326cf8ce"
    ),
}
EXPECTED_STATUS_BY_METHOD = {
    TME_OPTIMIZER_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
    CAG_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
    CLUSTER_COVER_METHOD_ID: {
        "CLOSED_EXECUTION_ERROR": 127,
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2021,
    },
    ZDP_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
}
EXPECTED_CANDIDATE_K_DISTRIBUTIONS = {
    TME_OPTIMIZER_METHOD_ID: {None: 2148},
    CAG_METHOD_ID: {
        13: 1,
        14: 3,
        15: 13,
        16: 19,
        17: 91,
        18: 2021,
    },
    CLUSTER_COVER_METHOD_ID: {18: 2021},
    ZDP_METHOD_ID: {
        13: 1,
        14: 3,
        15: 13,
        16: 19,
        17: 91,
        18: 249,
        19: 511,
        20: 618,
        21: 462,
        22: 155,
        23: 26,
    },
}
EXPECTED_MARKOV_ORDER_DISTRIBUTIONS = {
    TME_OPTIMIZER_METHOD_ID: {1: 49, 2: 100, 3: 1999},
    CAG_METHOD_ID: {1: 49, 2: 100, 3: 1999},
    CLUSTER_COVER_METHOD_ID: {1: 19, 2: 89, 3: 1913},
    ZDP_METHOD_ID: {1: 49, 2: 100, 3: 1999},
}
EXPECTED_KILL_COUNT_DISTRIBUTIONS = {
    TME_OPTIMIZER_METHOD_ID: {0: 2148},
    CAG_METHOD_ID: {0: 29, 5: 2119},
    CLUSTER_COVER_METHOD_ID: {0: 2, 5: 2019},
    ZDP_METHOD_ID: {0: 29, 5: 2119},
}
EXPECTED_DUPLICATE_DISTRIBUTIONS = {
    TME_OPTIMIZER_METHOD_ID: {0: 2148},
    CAG_METHOD_ID: {0: 2134, 1: 12, 2: 2},
    CLUSTER_COVER_METHOD_ID: {0: 2021},
    ZDP_METHOD_ID: {0: 2140, 1: 8},
}


class EvidenceBuildError(ValueError):
    """Wave-25 evidence inputs violate the frozen contract."""


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
    by_method = {
        cast(str, row["legacy_method_id"]): row
        for candidate in records
        if isinstance(candidate, dict)
        for row in [cast(dict[str, Any], candidate)]
        if isinstance(row.get("legacy_method_id"), str)
    }
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS:
        row = by_method.get(method_id, {})
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE25_METHOD[method_id]
        ):
            raise EvidenceBuildError(
                "wave-25 catalog identity changed"
            )


def _method_for_closed_row(row: dict[str, Any]) -> str:
    strategy_id = cast(str, row.get("strategy_id", ""))
    matches = [
        method_id
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS
        if method_id.rsplit("/", 1)[-1].removesuffix(".py")
        in strategy_id
    ]
    if len(matches) != 1:
        raise EvidenceBuildError("closed execution strategy changed")
    return matches[0]


def _validate_input(
    document: dict[str, Any],
    raw: bytes,
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
    status_by_method: dict[str, Counter[str]] = defaultdict(Counter)
    candidates_by_method: dict[
        str, Counter[int | None]
    ] = defaultdict(Counter)
    duplicates_by_method: dict[str, Counter[int]] = defaultdict(Counter)
    orders_by_method: dict[str, Counter[int]] = defaultdict(Counter)
    kill_counts_by_method: dict[str, Counter[int]] = defaultdict(Counter)
    calls_by_method: dict[str, Counter[int]] = defaultdict(Counter)
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        status = row.get("status")
        if status != "OK":
            if status not in (
                "CLOSED_EXECUTION_ERROR",
                "CLOSED_INSUFFICIENT_HISTORY",
            ):
                raise EvidenceBuildError("unexpected execution closure")
            method_id = _method_for_closed_row(row)
            status_by_method[method_id][cast(str, status)] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError("native execution evidence changed")
        native = cast(dict[str, Any], native_raw)
        method_id = native.get("legacy_method_id")
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS:
            raise EvidenceBuildError("native method identity changed")
        typed_method_id = cast(str, method_id)
        expected_ticket_count = (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE25_METHOD[
                typed_method_id
            ]
        )
        expected_combination_count = (
            SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE25_METHOD[
                typed_method_id
            ]
        )
        candidate_pool = cast(
            list[object],
            native.get("candidate_pool", []),
        )
        expected_candidate_k = (
            None
            if typed_method_id == TME_OPTIMIZER_METHOD_ID
            else len(candidate_pool)
        )
        if (
            row.get("candidate_k") != expected_candidate_k
            or row.get("combination_count")
            != expected_combination_count
            or row.get("native_ticket_count") != expected_ticket_count
            or native.get("candidate_k") is not None
            or native.get("candidate_pool_size")
            != expected_candidate_k
            or native.get("combination_count") is not None
            or native.get("source_method_combination_count")
            != expected_combination_count
            or native.get("native_ticket_count")
            != expected_ticket_count
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE25_METHOD[
                typed_method_id
            ]
            or native.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE25_METHOD[
                    typed_method_id
                ]
            )
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE25_METHOD[
                    typed_method_id
                ]
            ]
            or len(cast(list[object], row.get("native_tickets", [])))
            != expected_ticket_count
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError("native execution evidence changed")
        duplicate_count = native.get("native_duplicate_ticket_count")
        markov_order = native.get("markov_order")
        kill_numbers = cast(list[object], native.get("kill_numbers", []))
        statistical_calls = native.get("statistical_call_count")
        if (
            type(duplicate_count) is not int
            or type(markov_order) is not int
            or type(statistical_calls) is not int
        ):
            raise EvidenceBuildError("native diagnostics changed")
        status_by_method[typed_method_id]["OK"] += 1
        candidates_by_method[typed_method_id][
            expected_candidate_k
        ] += 1
        duplicates_by_method[typed_method_id][duplicate_count] += 1
        orders_by_method[typed_method_id][markov_order] += 1
        kill_counts_by_method[typed_method_id][len(kill_numbers)] += 1
        calls_by_method[typed_method_id][statistical_calls] += 1

    rows: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS:
        if (
            dict(sorted(status_by_method[method_id].items()))
            != EXPECTED_STATUS_BY_METHOD[method_id]
            or dict(sorted(candidates_by_method[method_id].items()))
            != EXPECTED_CANDIDATE_K_DISTRIBUTIONS[method_id]
            or dict(sorted(duplicates_by_method[method_id].items()))
            != EXPECTED_DUPLICATE_DISTRIBUTIONS[method_id]
            or dict(sorted(orders_by_method[method_id].items()))
            != EXPECTED_MARKOV_ORDER_DISTRIBUTIONS[method_id]
            or dict(sorted(kill_counts_by_method[method_id].items()))
            != EXPECTED_KILL_COUNT_DISTRIBUTIONS[method_id]
        ):
            raise EvidenceBuildError("execution diagnostics changed")
        expected_calls = 2 if method_id == ZDP_METHOD_ID else 1
        if calls_by_method[method_id] != Counter(
            {expected_calls: EXPECTED_STATUS_BY_METHOD[method_id]["OK"]}
        ):
            raise EvidenceBuildError("statistical call count changed")
        status_counts = EXPECTED_STATUS_BY_METHOD[method_id]
        rows.append(
            {
                "candidate_k_distribution": dict(
                    sorted(candidates_by_method[method_id].items())
                ),
                "closed_execution_count": (
                    2149 - status_counts["OK"]
                ),
                "execution_status_counts": status_counts,
                "kill_count_distribution": dict(
                    sorted(kill_counts_by_method[method_id].items())
                ),
                "legacy_method_id": method_id,
                "markov_order_distribution": dict(
                    sorted(orders_by_method[method_id].items())
                ),
                "native_duplicate_ticket_count_distribution": dict(
                    sorted(duplicates_by_method[method_id].items())
                ),
                "native_ticket_count": (
                    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE25_METHOD[
                        method_id
                    ]
                ),
                "native_ticket_semantics": (
                    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE25_METHOD[
                        method_id
                    ]
                ),
                "ok_execution_count": status_counts["OK"],
                "source_history_order": (
                    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE25_METHOD[
                        method_id
                    ]
                ),
                "source_method_combination_count": (
                    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE25_METHOD[
                        method_id
                    ]
                ),
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE25_METHOD[
                        method_id
                    ]
                ),
                "statistical_call_count_distribution": dict(
                    sorted(calls_by_method[method_id].items())
                ),
            }
        )
    return rows


def _validate_report(
    directory: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    checksums = {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in EXPECTED_REPORT_CHECKSUMS
    }
    if checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("report artifact checksums changed")
    report, report_raw = _read_json(
        directory / "biglotto_multi_ticket_backtest_report.json"
    )
    if (
        hashlib.sha256(report_raw).hexdigest()
        != EXPECTED_REPORT_FILE_SHA256
        or report.get("report_sha256") != EXPECTED_REPORT_SHA256
        or report.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or report.get("input_raw_sha256") != EXPECTED_INPUT_SHA256
        or report.get("input_canonical_sha256")
        != EXPECTED_INPUT_CANONICAL_SHA256
        or report.get("progress") != EXPECTED_PROGRESS
        or report.get("target_draw_count") != 2149
    ):
        raise EvidenceBuildError("report identity changed")
    portfolio = cast(dict[str, Any], report.get("portfolio_contract", {}))
    if (
        portfolio.get("same_ordered_20_portfolio_for_every_prefix")
        is not True
        or portfolio.get("prefix_counts") != [5, 10, 15, 20]
        or portfolio.get("candidate_k_is_ticket_count") is not False
        or portfolio.get("combination_count_is_ticket_count") is not False
    ):
        raise EvidenceBuildError("portfolio contract changed")
    return report, checksums


def build_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    report_directory: Path,
    parity_path: Path,
) -> dict[str, object]:
    _validate_catalog(catalog_path)
    input_document, input_raw = _read_json(input_path)
    strategies = _validate_input(input_document, input_raw)
    report, report_checksums = _validate_report(report_directory)
    parity, parity_raw = _read_json(parity_path)
    parity_cases = cast(list[object], parity.get("cases", []))
    if (
        hashlib.sha256(parity_raw).hexdigest()
        != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("case_count") != 532
        or len(parity_cases) != 532
        or sum(
            1
            for candidate in parity_cases
            if isinstance(candidate, dict)
            and cast(dict[str, object], candidate).get("status")
            == "CLOSED_PARITY"
        )
        != 127
        or parity.get("upstream_unified_parity_evidence_sha256")
        != "8064df37f44f695699e87071a4ffe2cb7a816405862f73d37fa14e038f73edd5"
    ):
        raise EvidenceBuildError("parity evidence changed")
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "database_sha256": EXPECTED_DATABASE_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "input_canonical_sha256": EXPECTED_INPUT_CANONICAL_SHA256,
        "input_sha256": EXPECTED_INPUT_SHA256,
        "materialization_schema_version": MATERIALIZATION_SCHEMA_VERSION,
        "parity": {
            "case_count": parity["case_count"],
            "closed_parity_case_count": 127,
            "parity_sha256": EXPECTED_PARITY_SHA256,
            "source_artifacts": parity["source_artifacts"],
            "status": parity["status"],
            "support_artifacts": parity["support_artifacts"],
            "upstream_unified_parity_evidence_sha256": (
                parity["upstream_unified_parity_evidence_sha256"]
            ),
        },
        "progress": report["progress"],
        "report_artifact_checksums": report_checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "strategies": strategies,
        "target_draw_count": 2149,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--report-directory", required=True, type=Path)
    parser.add_argument("--parity-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    evidence = build_evidence(
        catalog_path=args.catalog,
        input_path=args.input_file,
        report_directory=args.report_directory,
        parity_path=args.parity_file,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
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
