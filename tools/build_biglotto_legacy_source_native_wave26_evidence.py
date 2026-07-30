#!/usr/bin/env python3
"""Build compact evidence for the wave-26 causal source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave26 import (
    CES_METHOD_ID,
    DMS_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE26_METHOD,
    GREEDY_METHOD_ID,
    MWSC_METHOD_ID,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE26_METHOD,
    PCE_METHOD_ID,
    SMH_CLOSED_METHOD_ID,
    SMH_CLOSED_REASON_CODE,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE26_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE26_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave26 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE26_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "ae4b21d03d6c4c56b29d6ae53292d2f85671fa8ab07fdf36e867f2fb62162957"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "664c1bf977c187cf6c0985a1cea5fdba38ffaf2f5db46ece8c57d21859855e33"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "5e72818df89ce68179e53c28d1a2cc6e04035778418bc7ab4c8fadc6313fb324"
)
EXPECTED_PARITY_SHA256 = (
    "4f5e8a7007f9e1e09332d9c95dfdc0e9a4df1e14948fb842b6397b8978083329"
)
EXPECTED_REPORT_SHA256 = (
    "5b6e44e5ea9ee47c588345af81beb1612bd263d5a957537de9c7f5518e49fa99"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "39d280e55df201b3295a18bc8bb78142191b2b3863c168901441380628ecb5cd"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 58,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 121,
}
EXPECTED_PROGRESS = {
    "backtested_count": 63,
    "closed_count": 37,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 116,
    "reproduced_count": 63,
    "total_strategy_count": 221,
    "uncompleted_count": 116,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "7cc538f5a9febf92ecd82b756932418679f9cb12ffe2d1b6876ca6e7f48ad2b1"
    ),
    "biglotto_execution_audit.csv": (
        "2746f981ed80928b8d010abdf4556bc7473c7f797b05f08db0a1fdebe2341a35"
    ),
    "biglotto_full_rankings.csv": (
        "d57754c460c0ba020677ca690fe7b5d52abefb0596c5348672409af1588e02d5"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "39d280e55df201b3295a18bc8bb78142191b2b3863c168901441380628ecb5cd"
    ),
    "biglotto_official_prize_distributions.csv": (
        "b3e08be7c10000403a81b1e57a52b3374ba9732d8717d6fc78d216ee0e3f5bc8"
    ),
    "biglotto_strategy_universe.csv": (
        "3e59b65c9d9a986c9f6d5e22f8284ae6941846f3c27f53113153f21f92556623"
    ),
    "biglotto_success_metrics.csv": (
        "1f7a3549e8fd8a12db162568286eb81cfa11188c69c04fb3e08350448d5233b2"
    ),
    "biglotto_top10.csv": (
        "e973b86e988267702d502bfcdf83d2a1868d2f7bfdd76b0f72a6195e976bf61c"
    ),
}
EXPECTED_STATUS_BY_METHOD = {
    CES_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
    DMS_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 20,
        "OK": 2129,
    },
    GREEDY_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
    MWSC_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
    PCE_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    },
}
EXPECTED_CANDIDATE_K_DISTRIBUTIONS = {
    CES_METHOD_ID: {
        15: 3,
        16: 3,
        17: 8,
        18: 10,
        19: 17,
        20: 2107,
    },
    DMS_METHOD_ID: {None: 2129},
    GREEDY_METHOD_ID: {
        13: 1,
        14: 3,
        15: 13,
        16: 19,
        17: 91,
        18: 2021,
    },
    MWSC_METHOD_ID: {
        14: 1,
        15: 3,
        16: 3,
        17: 2,
        18: 2139,
    },
    PCE_METHOD_ID: {None: 2148},
}
EXPECTED_KILL_COUNT_DISTRIBUTIONS = {
    CES_METHOD_ID: {0: 29, 5: 2119},
    DMS_METHOD_ID: {0: 2129},
    GREEDY_METHOD_ID: {0: 29, 5: 2119},
    MWSC_METHOD_ID: {0: 29, 5: 2119},
    PCE_METHOD_ID: {0: 29, 5: 2119},
}
EXPECTED_DUPLICATE_DISTRIBUTIONS = {
    CES_METHOD_ID: {0: 2148},
    DMS_METHOD_ID: {0: 2122, 1: 6, 2: 1},
    GREEDY_METHOD_ID: {0: 2148},
    MWSC_METHOD_ID: {0: 2148},
    PCE_METHOD_ID: {0: 2148},
}
EXPECTED_STATISTICAL_CALL_DISTRIBUTIONS = {
    CES_METHOD_ID: {1: 2148},
    DMS_METHOD_ID: {20: 1363, 21: 766},
    GREEDY_METHOD_ID: {1: 2148},
    MWSC_METHOD_ID: {4: 2148},
    PCE_METHOD_ID: {1: 2148},
}


class EvidenceBuildError(ValueError):
    """Wave-26 evidence inputs violate the frozen contract."""


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
    for method_id in (
        *SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS,
        SMH_CLOSED_METHOD_ID,
    ):
        row = by_method.get(method_id, {})
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[method_id]
        ):
            raise EvidenceBuildError(
                "wave-26 catalog identity changed"
            )


def _method_for_closed_row(row: dict[str, Any]) -> str:
    strategy_id = cast(str, row.get("strategy_id", ""))
    matches = [
        method_id
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS
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
    if len(executions) != 10745:
        raise EvidenceBuildError("full input execution count changed")
    status_by_method: dict[str, Counter[str]] = defaultdict(Counter)
    candidates_by_method: dict[
        str, Counter[int | None]
    ] = defaultdict(Counter)
    duplicates_by_method: dict[str, Counter[int]] = defaultdict(Counter)
    kill_counts_by_method: dict[str, Counter[int]] = defaultdict(Counter)
    calls_by_method: dict[str, Counter[int]] = defaultdict(Counter)
    selected_by_method: dict[
        str, Counter[tuple[str, ...]]
    ] = defaultdict(Counter)
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        status = row.get("status")
        if status != "OK":
            if status != "CLOSED_INSUFFICIENT_HISTORY":
                raise EvidenceBuildError("unexpected execution closure")
            method_id = _method_for_closed_row(row)
            status_by_method[method_id][cast(str, status)] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError("native execution evidence changed")
        native = cast(dict[str, Any], native_raw)
        method_id = native.get("legacy_method_id")
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS:
            raise EvidenceBuildError("native method identity changed")
        typed_method_id = cast(str, method_id)
        expected_ticket_count = (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD[
                typed_method_id
            ]
        )
        expected_combination_count = (
            SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD[
                typed_method_id
            ]
        )
        candidate_pool = cast(
            list[object],
            native.get("candidate_pool", []),
        )
        expected_candidate_k = native.get("candidate_pool_size")
        if (
            expected_candidate_k is not None
            and (
                type(expected_candidate_k) is not int
                or expected_candidate_k != len(candidate_pool)
            )
        ) or (
            expected_candidate_k is None and candidate_pool
        ):
            raise EvidenceBuildError("candidate pool evidence changed")
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
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[
                typed_method_id
            ]
            or native.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE26_METHOD[
                    typed_method_id
                ]
            )
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE26_METHOD[
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
        kill_numbers = cast(list[object], native.get("kill_numbers", []))
        statistical_calls = native.get("statistical_call_count")
        selected_methods = native.get("selected_methods")
        if (
            type(duplicate_count) is not int
            or type(statistical_calls) is not int
            or not isinstance(selected_methods, list)
        ):
            raise EvidenceBuildError("native diagnostics changed")
        typed_selected_methods = cast(list[object], selected_methods)
        if any(
            not isinstance(item, str)
            for item in typed_selected_methods
        ):
            raise EvidenceBuildError("native diagnostics changed")
        status_by_method[typed_method_id]["OK"] += 1
        candidates_by_method[typed_method_id][
            expected_candidate_k
        ] += 1
        duplicates_by_method[typed_method_id][duplicate_count] += 1
        kill_counts_by_method[typed_method_id][len(kill_numbers)] += 1
        calls_by_method[typed_method_id][statistical_calls] += 1
        selected_by_method[typed_method_id][
            tuple(cast(list[str], typed_selected_methods))
        ] += 1

    rows: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS:
        if (
            dict(sorted(status_by_method[method_id].items()))
            != EXPECTED_STATUS_BY_METHOD[method_id]
            or dict(sorted(candidates_by_method[method_id].items()))
            != EXPECTED_CANDIDATE_K_DISTRIBUTIONS[method_id]
            or dict(sorted(duplicates_by_method[method_id].items()))
            != EXPECTED_DUPLICATE_DISTRIBUTIONS[method_id]
            or dict(sorted(kill_counts_by_method[method_id].items()))
            != EXPECTED_KILL_COUNT_DISTRIBUTIONS[method_id]
            or dict(sorted(calls_by_method[method_id].items()))
            != EXPECTED_STATISTICAL_CALL_DISTRIBUTIONS[method_id]
        ):
            raise EvidenceBuildError("execution diagnostics changed")
        selected_distribution = [
            {
                "count": count,
                "methods": list(methods),
            }
            for methods, count in sorted(
                selected_by_method[method_id].items()
            )
        ]
        if (
            method_id == DMS_METHOD_ID
            and (
                sum(
                    cast(int, row["count"])
                    for row in selected_distribution
                )
                != EXPECTED_STATUS_BY_METHOD[method_id]["OK"]
                or any(
                    len(cast(list[object], row["methods"])) != 3
                    for row in selected_distribution
                )
            )
        ) or (
            method_id != DMS_METHOD_ID
            and selected_distribution
            != [
                {
                    "count": EXPECTED_STATUS_BY_METHOD[method_id]["OK"],
                    "methods": [],
                }
            ]
        ):
            raise EvidenceBuildError("selected-method evidence changed")
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
                "native_duplicate_ticket_count_distribution": dict(
                    sorted(duplicates_by_method[method_id].items())
                ),
                "native_ticket_count": (
                    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD[
                        method_id
                    ]
                ),
                "native_ticket_semantics": (
                    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE26_METHOD[
                        method_id
                    ]
                ),
                "ok_execution_count": status_counts["OK"],
                "source_history_order": (
                    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE26_METHOD[
                        method_id
                    ]
                ),
                "source_method_combination_count": (
                    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD[
                        method_id
                    ]
                ),
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[
                        method_id
                    ]
                ),
                "selected_method_sequence_count": len(
                    selected_distribution
                ),
                "selected_method_sequence_distribution_sha256": (
                    hashlib.sha256(
                        _canonical_bytes(selected_distribution)
                    ).hexdigest()
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
    static_dispositions = cast(
        list[object], parity.get("static_dispositions", [])
    )
    if (
        hashlib.sha256(parity_raw).hexdigest()
        != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("case_count") != 165
        or len(parity_cases) != 165
        or sum(
            1
            for candidate in parity_cases
            if isinstance(candidate, dict)
            and cast(dict[str, object], candidate).get("status")
            == "CLOSED_PARITY"
        )
        != 19
        or static_dispositions
        != [
            {
                "legacy_method_id": SMH_CLOSED_METHOD_ID,
                "random_sample_call_count": 2,
                "random_state_binding_calls": [],
                "reason_code": SMH_CLOSED_REASON_CODE,
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[
                        SMH_CLOSED_METHOD_ID
                    ]
                ),
                "status": "CLOSED_UNEXECUTABLE",
            }
        ]
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
            "closed_parity_case_count": 19,
            "parity_sha256": EXPECTED_PARITY_SHA256,
            "source_artifacts": parity["source_artifacts"],
            "static_dispositions": static_dispositions,
            "status": parity["status"],
            "support_artifacts": parity["support_artifacts"],
        },
        "progress": report["progress"],
        "report_artifact_checksums": report_checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "static_dispositions": static_dispositions,
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
                "static_disposition_count": len(
                    cast(
                        list[object],
                        evidence["static_dispositions"],
                    )
                ),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
