#!/usr/bin/env python3
"""Build compact evidence for both wave-62 diversified backtests."""

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
    RESEARCH_DISCLAIMER,
)
from lottolab.application.legacy_diversified_native_portfolios_wave62 import (
    BACKTEST_METHOD_ID,
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    ENSEMBLE_METHOD_ID,
    FROZEN_SOURCE_COMMIT,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    MODEL_CANDIDATE_K,
    NATIVE_TICKET_ORDER_BY_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_METHOD,
    RANDOM_PROTOCOL_BY_METHOD,
    SOURCE_CANDIDATE_K_VALUES_BY_METHOD,
    SOURCE_CLOSED_RESULT_HORIZONS_BY_METHOD,
    SOURCE_NATIVE_WAVE62_PROTOCOL,
    SOURCE_RANDOM_BASELINE_EXCLUDED_BY_METHOD,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_METHOD,
    SUPPORTED_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_diversified_native_batch_import_wave62 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_DIVERSIFIED_WAVE62_EVIDENCE_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_DIVERSIFIED_WAVE62_PARITY_V1"
)
BASE_CATALOG_SHA256 = (
    "9d80f7e5e6e996b825f19cf8c209f7148576429785a72daa9462134549a8661c"
)
BASE_CATALOG_FILE_SHA256 = (
    "b216eebf3cad8fc47bc75c908f7035a9697cc9165d872f9fae1d9f9ca42b83bd"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 130,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 5,
}
EXPECTED_PROGRESS = {
    "backtested_count": 132,
    "closed_count": 74,
    "duplicate_alias_count": 12,
    "owner_decision_required_count": 3,
    "reproduced_count": 132,
    "total_strategy_count": 221,
    "uncompleted_count": 3,
}
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_FILE_SHA256 = (
    "6a200ea7a0b8fe9c6b558a4489ba376238fb8ffd29639a2060653700bf09ff63"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "4ccbccd2bd8f33bfcdeda4fa0833afe3904980df60ddefd4b6e062c37b5dcd19"
)
EXPECTED_PARITY_FILE_SHA256 = (
    "6eca2bba9558892160858d0bfdc96051f1529f1607da5fb5b16390b1b5007938"
)
EXPECTED_PARITY_SHA256 = (
    "633e517f7fa33e14206d526b31a16a4a2a496a94a42166b9ec5baf8c80543709"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "89f4af7d63901748e8e0c7994a2914e812bad7c3b58792efc5834f2a83d2da98"
)
EXPECTED_REPORT_SHA256 = (
    "5e48902cd79eae2498989aae7729b7d6cfafeee949393f1a57c3b7761050612b"
)
EXPECTED_ALL_SEQUENCE_SHA256 = {
    ENSEMBLE_METHOD_ID: (
        "e24e53c0688b27e6c2d6b632912a46d79ca5366dce3b7ace393b5fe4870c75c6"
    ),
    BACKTEST_METHOD_ID: (
        "795f2e6e18aec6fda93bc39852c4d3a0c9257074b35548171a1972ff2a867c3c"
    ),
}
EXPECTED_OK_SEQUENCE_SHA256 = {
    ENSEMBLE_METHOD_ID: (
        "06fd6f9bc0cdac34c20859d0cd27e9c1b5f8e60c3f031e86c1bdb93b3ae2ccf5"
    ),
    BACKTEST_METHOD_ID: (
        "30301ba74b86a0c2d98311181702e84b3a81e8e87849b43ca379fd802c3d0e8d"
    ),
}
EXPECTED_EXECUTION_COUNTS = {
    ENSEMBLE_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 50,
        "OK": 2099,
    },
    BACKTEST_METHOD_ID: {
        "CLOSED_REJECTED": 1649,
        "OK": 500,
    },
}
EXPECTED_CLOSED_REASONS = {
    ENSEMBLE_METHOD_ID: {
        "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM": 50,
    },
    BACKTEST_METHOD_ID: {
        "TARGET_OUTSIDE_FROZEN_SOURCE_MAIN_HORIZONS_150_AND_500": 1649,
    },
}
EXPECTED_NATIVE_COUNT_DISTRIBUTIONS = {
    ENSEMBLE_METHOD_ID: {"3": 2099},
    BACKTEST_METHOD_ID: {"3": 350, "6": 150},
}
EXPECTED_CONFIGURATION_DISTRIBUTIONS = {
    ENSEMBLE_METHOD_ID: {"1": 2099},
    BACKTEST_METHOD_ID: {"1": 350, "2": 150},
}
EXPECTED_DUPLICATE_DISTRIBUTIONS = {
    ENSEMBLE_METHOD_ID: {"0": 2099},
    BACKTEST_METHOD_ID: {
        "0": 350,
        "1": 139,
        "2": 10,
        "3": 1,
    },
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "e64c49d9a075fc9822972ad1a804850e8d8fddc015bd7843c1251220936c0447"
    ),
    "biglotto_execution_audit.csv": (
        "b38b9711d6fd8092cd280d1819b431351500738209dd9ef48568b0780bea3777"
    ),
    "biglotto_full_rankings.csv": (
        "3443d8a8a54a21dfc28f53d1e32b0504378f4deaebbf6d92a98d184bba3b0d13"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "89f4af7d63901748e8e0c7994a2914e812bad7c3b58792efc5834f2a83d2da98"
    ),
    "biglotto_official_prize_distributions.csv": (
        "508b0e4991701524f192960f0333b2de8ca64918bf1252662b67b3ed2d196289"
    ),
    "biglotto_strategy_universe.csv": (
        "c305c3c0fceee79a91580d2f0868848005f312291cde1455c268d86b1708c4c6"
    ),
    "biglotto_success_metrics.csv": (
        "65b35d5ddd8e179ec1bce14aeca729f2885d7e32193646130a8e2b0f05250d59"
    ),
    "biglotto_top10.csv": (
        "08139c30820e6da0f1f1552fae8769dff96560a5134f6b26f709f0410a079f2b"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-62 evidence inputs violate the frozen contract."""


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
        or catalog.get("full_universe_complete") is not False
    ):
        raise EvidenceBuildError("base catalog identity changed")
    records = cast(list[object], catalog.get("records", []))
    by_method: dict[str, str] = {}
    for candidate in records:
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id not in SUPPORTED_METHODS:
            continue
        typed_method_id = cast(str, method_id)
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_METHOD[typed_method_id]
            or type(row.get("strategy_id")) is not str
        ):
            raise EvidenceBuildError(
                f"wave-62 catalog row changed: {method_id}"
            )
        by_method[typed_method_id] = cast(str, row["strategy_id"])
    if set(by_method) != set(SUPPORTED_METHODS):
        raise EvidenceBuildError("wave-62 catalog method set changed")
    return by_method


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("native_ticket_case_count") != 8247
        or parity.get("status_counts_by_method")
        != EXPECTED_EXECUTION_COUNTS
        or parity.get("native_ticket_count_distribution_by_method")
        != EXPECTED_NATIVE_COUNT_DISTRIBUTIONS
        or parity.get(
            "native_duplicate_ticket_count_distribution_by_method"
        )
        != EXPECTED_DUPLICATE_DISTRIBUTIONS
        or parity.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or parity.get("ledger_content_sha256")
        != LEDGER_CONTENT_SHA256
        or parity.get("ticket_sequence_sha256_by_method")
        != EXPECTED_ALL_SEQUENCE_SHA256
        or parity.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
    ):
        raise EvidenceBuildError("wave-62 parity identity changed")
    return parity


def _validate_input(
    path: Path,
    *,
    strategy_id_by_method: dict[str, str],
) -> list[dict[str, object]]:
    document, raw = _read_json(path)
    executions = cast(list[object], document.get("executions", []))
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_INPUT_FILE_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest()
        != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256")
        != EXPECTED_DATABASE_SHA256
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", [])))
        != 2149
        or len(executions) != 4298
    ):
        raise EvidenceBuildError("wave-62 full input identity changed")
    method_by_strategy_id = {
        strategy_id: method_id
        for method_id, strategy_id in strategy_id_by_method.items()
    }
    statuses: defaultdict[str, Counter[str]] = defaultdict(Counter)
    reasons: defaultdict[str, Counter[str]] = defaultdict(Counter)
    portfolios: defaultdict[str, list[list[list[int]]]] = defaultdict(
        list
    )
    configuration_counts: defaultdict[str, Counter[int]] = defaultdict(
        Counter
    )
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-62 execution changed")
        row = cast(dict[str, Any], candidate)
        method_id = method_by_strategy_id.get(
            cast(str, row.get("strategy_id"))
        )
        if method_id is None:
            raise EvidenceBuildError("wave-62 strategy identity changed")
        status = cast(str, row.get("status"))
        statuses[method_id][status] += 1
        if status != "OK":
            reasons[method_id][
                cast(str, row.get("reason_code"))
            ] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError(
                "wave-62 native generation changed"
            )
        native = cast(dict[str, Any], native_raw)
        native_tickets = cast(
            list[object],
            row.get("native_tickets", []),
        )
        config_count = native.get("local_configuration_count")
        if (
            type(config_count) is not int
            or config_count not in {1, 2}
        ):
            raise EvidenceBuildError(
                "wave-62 configuration count changed"
            )
        expected_native_count = 3 * config_count
        if (
            native.get("legacy_method_id") != method_id
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_METHOD[method_id]
            or native.get("candidate_k") is not None
            or native.get("source_candidate_k_values")
            != list(SOURCE_CANDIDATE_K_VALUES_BY_METHOD[method_id])
            or row.get("candidate_k") != MODEL_CANDIDATE_K
            or native.get("combination_count") is not None
            or row.get("combination_count") != config_count
            or native.get("native_ticket_count")
            != expected_native_count
            or row.get("native_ticket_count")
            != expected_native_count
            or native.get("causal_eligibility_rule")
            != CAUSAL_ELIGIBILITY_RULE
            or native.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
            or native.get("random_protocol")
            != RANDOM_PROTOCOL_BY_METHOD[method_id]
            or native.get("randomness_used") is not True
            or native.get("ledger_file_sha256")
            != LEDGER_FILE_SHA256
            or native.get("ledger_content_sha256")
            != LEDGER_CONTENT_SHA256
            or native.get("native_ticket_count_semantics")
            != NATIVE_TICKET_SEMANTICS_BY_METHOD[method_id]
            or native.get("native_ticket_order")
            != NATIVE_TICKET_ORDER_BY_METHOD[method_id]
            or native.get("source_closed_result_horizons")
            != list(
                SOURCE_CLOSED_RESULT_HORIZONS_BY_METHOD[method_id]
            )
            or native.get("source_random_baseline_excluded")
            is not SOURCE_RANDOM_BASELINE_EXCLUDED_BY_METHOD[method_id]
            or len(native_tickets) != expected_native_count
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError(
                f"wave-62 native semantics changed: {method_id}"
            )
        portfolios[method_id].append(
            cast(list[list[int]], native_tickets)
        )
        configuration_counts[method_id][config_count] += 1
    strategies: list[dict[str, object]] = []
    for method_id in SUPPORTED_METHODS:
        sequence_sha256 = hashlib.sha256(
            _canonical_bytes(portfolios[method_id])
        ).hexdigest()
        native_counts = Counter(
            len(portfolio) for portfolio in portfolios[method_id]
        )
        duplicate_counts = Counter(
            len(portfolio)
            - len({tuple(ticket) for ticket in portfolio})
            for portfolio in portfolios[method_id]
        )
        if (
            dict(statuses[method_id])
            != EXPECTED_EXECUTION_COUNTS[method_id]
            or dict(reasons[method_id])
            != EXPECTED_CLOSED_REASONS[method_id]
            or {
                str(key): value
                for key, value in sorted(native_counts.items())
            }
            != EXPECTED_NATIVE_COUNT_DISTRIBUTIONS[method_id]
            or {
                str(key): value
                for key, value in sorted(
                    configuration_counts[method_id].items()
                )
            }
            != EXPECTED_CONFIGURATION_DISTRIBUTIONS[method_id]
            or {
                str(key): value
                for key, value in sorted(duplicate_counts.items())
            }
            != EXPECTED_DUPLICATE_DISTRIBUTIONS[method_id]
            or sequence_sha256
            != EXPECTED_OK_SEQUENCE_SHA256[method_id]
        ):
            raise EvidenceBuildError(
                f"wave-62 execution distribution changed: {method_id}"
            )
        ok_count = statuses[method_id]["OK"]
        closed_count = 2149 - ok_count
        strategies.append(
            {
                "candidate_k_distribution": {"49": ok_count},
                "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
                "causal_protocol": CAUSAL_PROTOCOL,
                "closed_execution_count": closed_count,
                "closed_reason_code_distribution": dict(
                    EXPECTED_CLOSED_REASONS[method_id]
                ),
                "combination_count_distribution": dict(
                    EXPECTED_CONFIGURATION_DISTRIBUTIONS[method_id]
                ),
                "execution_status_counts": dict(
                    EXPECTED_EXECUTION_COUNTS[method_id]
                ),
                "legacy_method_id": method_id,
                "native_duplicate_ticket_count_distribution": dict(
                    EXPECTED_DUPLICATE_DISTRIBUTIONS[method_id]
                ),
                "native_ticket_count_distribution": dict(
                    EXPECTED_NATIVE_COUNT_DISTRIBUTIONS[method_id]
                ),
                "native_ticket_order": (
                    NATIVE_TICKET_ORDER_BY_METHOD[method_id]
                ),
                "native_ticket_semantics": (
                    NATIVE_TICKET_SEMANTICS_BY_METHOD[method_id]
                ),
                "ok_execution_count": ok_count,
                "random_protocol": RANDOM_PROTOCOL_BY_METHOD[method_id],
                "randomness_reproduction": (
                    "SOURCE_RUNTIME_LEDGER_EXACT_TICKET_REPLAY"
                ),
                "source_candidate_k_values": list(
                    SOURCE_CANDIDATE_K_VALUES_BY_METHOD[method_id]
                ),
                "source_closed_result_horizons": list(
                    SOURCE_CLOSED_RESULT_HORIZONS_BY_METHOD[method_id]
                ),
                "source_random_baseline_excluded": (
                    SOURCE_RANDOM_BASELINE_EXCLUDED_BY_METHOD[
                        method_id
                    ]
                ),
                "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
                "source_sha256": SOURCE_SHA256_BY_METHOD[method_id],
                "ticket_sequence_sha256": sequence_sha256,
            }
        )
    return strategies


def _validate_report(
    *,
    report_file: Path,
    report_directory: Path,
) -> dict[str, str]:
    report, raw = _read_json(report_file)
    checksums = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in report_directory.iterdir()
        if path.is_file()
    }
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_REPORT_FILE_SHA256
        or report.get("report_schema_version")
        != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or report.get("report_sha256") != EXPECTED_REPORT_SHA256
        or report.get("catalog_sha256") != BASE_CATALOG_SHA256
        or report.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or report.get("target_draw_count") != 2149
        or report.get("progress") != EXPECTED_PROGRESS
        or report.get("input_raw_sha256")
        != EXPECTED_INPUT_FILE_SHA256
        or report.get("input_canonical_sha256")
        != EXPECTED_INPUT_CANONICAL_SHA256
        or report.get("research_disclaimer") != RESEARCH_DISCLAIMER
        or checksums != EXPECTED_REPORT_CHECKSUMS
    ):
        raise EvidenceBuildError("wave-62 report identity changed")
    return checksums


def build_evidence(
    *,
    base_catalog_path: Path,
    input_file: Path,
    parity_file: Path,
    report_file: Path,
    report_directory: Path,
) -> dict[str, object]:
    """Validate every wave-62 artifact and return compact evidence."""

    strategy_id_by_method = _validate_catalog(base_catalog_path)
    parity = _validate_parity(parity_file)
    strategies = _validate_input(
        input_file,
        strategy_id_by_method=strategy_id_by_method,
    )
    report_checksums = _validate_report(
        report_file=report_file,
        report_directory=report_directory,
    )
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "causal_protocol": CAUSAL_PROTOCOL,
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "dataset_sha256": EXPECTED_DATABASE_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "input_canonical_sha256": EXPECTED_INPUT_CANONICAL_SHA256,
        "input_raw_sha256": EXPECTED_INPUT_FILE_SHA256,
        "ledger_content_sha256": LEDGER_CONTENT_SHA256,
        "ledger_file_sha256": LEDGER_FILE_SHA256,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "materialization_schema_version": (
            MATERIALIZATION_SCHEMA_VERSION
        ),
        "parity": {
            "parity_file_sha256": EXPECTED_PARITY_FILE_SHA256,
            "parity_schema_version": PARITY_SCHEMA_VERSION,
            "parity_sha256": EXPECTED_PARITY_SHA256,
            "source_artifacts": parity["source_artifacts"],
            "support_artifacts": parity["support_artifacts"],
        },
        "report_checksums": report_checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_native_protocol": SOURCE_NATIVE_WAVE62_PROTOCOL,
        "strategies": strategies,
        "target_draw_count": 2149,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--parity-file", required=True, type=Path)
    parser.add_argument("--report-file", required=True, type=Path)
    parser.add_argument(
        "--report-directory",
        required=True,
        type=Path,
    )
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    document = build_evidence(
        base_catalog_path=args.base_catalog,
        input_file=args.input_file,
        parity_file=args.parity_file,
        report_file=args.report_file,
        report_directory=args.report_directory,
    )
    payload = _canonical_bytes(document) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(
                    payload
                ).hexdigest(),
                "output_file": str(args.output_file),
                "strategy_count": len(
                    cast(list[object], document["strategies"])
                ),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
