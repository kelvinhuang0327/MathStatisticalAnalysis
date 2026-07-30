#!/usr/bin/env python3
"""Build compact evidence for the three wave-60 causal backtests."""

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
from lottolab.application.legacy_seeded_benchmark_native_portfolios_wave60 import (
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    FROZEN_SOURCE_COMMIT,
    IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE60_METHOD,
    INSUFFICIENT_HISTORY_REASON,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD,
    MODEL_CANDIDATE_K,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE60_METHOD,
    PINNED_DATASET_SHA256,
    SOURCE_NATIVE_WAVE60_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_seeded_benchmark_native_batch_import_wave60 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SEEDED_BENCHMARKS_WAVE60_EVIDENCE_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SEEDED_BENCHMARKS_WAVE60_PARITY_V1"
)
BASE_CATALOG_SHA256 = (
    "57897e5073fbeb796ad90df9ad67010d8001c14c775c554b2304c3d6c6e6fd88"
)
BASE_CATALOG_FILE_SHA256 = (
    "5034dea7d5f1e9b42b62a0291237ea103fe93d79617db4564bb735bbf4936138"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 126,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 9,
}
EXPECTED_PROGRESS = {
    "backtested_count": 129,
    "closed_count": 74,
    "duplicate_alias_count": 12,
    "owner_decision_required_count": 6,
    "reproduced_count": 129,
    "total_strategy_count": 221,
    "uncompleted_count": 6,
}
EXPECTED_INPUT_FILE_SHA256 = (
    "e3b66f2626919549c794e5b6ecaee0de48f1426e130a7679018a8ad06d31283a"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "9946c3113bf8031cb28765dee428b153ef5616ef57a96ad17be37e722e7d599c"
)
EXPECTED_PARITY_FILE_SHA256 = (
    "0321d87cec9552b0c0bd6d3dfba7596de320ecb2511de7a94a39dbc063bf4705"
)
EXPECTED_PARITY_SHA256 = (
    "025ca7355f1567eb387576e08c42bf125cea1acf80e44c31008a2139a3ea9777"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "0d14296afd286c8cbe91a3211addbc98deca763600446aa8542aa63f3f7f2693"
)
EXPECTED_REPORT_SHA256 = (
    "0769459ec4aa11c3da4cc1b353eddf65bcc26daf75fc045218775d7fb4b4224b"
)
EXPECTED_SEQUENCE_SHA256 = {
    "tools/hybrid_integration_benchmark.py": (
        "c342dbaf12094249921efa2fbe34886e685fe0aafccee720414afc7445d9720d"
    ),
    "tools/orthogonal_diversification_benchmark.py": (
        "0f1b741177e065364d0a45614154e01160abc89d13704674a3e09c01c42e9985"
    ),
    "tools/zone_split_optimizer.py": (
        "cf959bf7157fc447bc77f8bf37f031c3ba94e5b8fe3e94bf1ca0eb4a2c06f58c"
    ),
}
EXPECTED_DUPLICATE_DISTRIBUTIONS = {
    "tools/hybrid_integration_benchmark.py": {
        "3": 2128,
        "4": 6,
        "5": 8,
        "6": 6,
    },
    "tools/orthogonal_diversification_benchmark.py": {"4": 2148},
    "tools/zone_split_optimizer.py": {"0": 2145, "1": 3},
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "e00c6b94f02478a3a170455fdad4a5f2f864a6afa65483656b11ddba85b4670e"
    ),
    "biglotto_execution_audit.csv": (
        "28f564a200b6539aac22ca400362f5486cdf9896ec9c3ffb9a54db14c64e7247"
    ),
    "biglotto_full_rankings.csv": (
        "3e8243b9572c71400c8da4cc5349901249e0e4dc0c6f48afa46149c31db9418b"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "0d14296afd286c8cbe91a3211addbc98deca763600446aa8542aa63f3f7f2693"
    ),
    "biglotto_official_prize_distributions.csv": (
        "9a04086c77d11cddf796799610d7c99945b64ad44280dffb8ef669869ede8c34"
    ),
    "biglotto_strategy_universe.csv": (
        "cb41b472c39dd70dea394497c96478c1b14d059c6733a9def229f860e3f6c310"
    ),
    "biglotto_success_metrics.csv": (
        "67e77d6f48f500d82880f5895e008df359187bd154dc256472981dda0df49719"
    ),
    "biglotto_top10.csv": (
        "5f43b33a3889f7c819a477c3eff940b18d7a7b9b25c7b845d9ee23855b68725c"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-60 evidence inputs violate the frozen contract."""


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
    by_method: dict[str, str] = {}
    for candidate in cast(list[object], catalog.get("records", [])):
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS:
            continue
        typed_method_id = cast(str, method_id)
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD[
                typed_method_id
            ]
            or type(row.get("strategy_id")) is not str
        ):
            raise EvidenceBuildError(
                f"wave-60 catalog row changed: {method_id}"
            )
        by_method[typed_method_id] = cast(str, row["strategy_id"])
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS):
        raise EvidenceBuildError("wave-60 catalog method set changed")
    return by_method


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    expected_statuses = {
        method_id: {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
            "OK": 2148,
        }
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS
    }
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("native_ticket_case_count") != 139620
        or parity.get("status_counts_by_method") != expected_statuses
        or parity.get("ledger_file_sha256") is not None
        or parity.get("ledger_content_sha256")
        != LEDGER_CONTENT_SHA256
        or parity.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
    ):
        raise EvidenceBuildError("wave-60 parity identity changed")
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
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", []))) != 2149
        or len(executions) != 6447
    ):
        raise EvidenceBuildError("wave-60 full input identity changed")
    method_by_strategy_id = {
        strategy_id: method_id
        for method_id, strategy_id in strategy_id_by_method.items()
    }
    statuses: defaultdict[str, Counter[str]] = defaultdict(Counter)
    reasons: defaultdict[str, Counter[str]] = defaultdict(Counter)
    portfolios: defaultdict[str, list[list[list[int]]]] = defaultdict(
        list
    )
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-60 execution changed")
        row = cast(dict[str, Any], candidate)
        method_id = method_by_strategy_id.get(
            cast(str, row.get("strategy_id"))
        )
        if method_id is None:
            raise EvidenceBuildError("wave-60 strategy identity changed")
        status = cast(str, row.get("status"))
        statuses[method_id][status] += 1
        if status != "OK":
            reasons[method_id][cast(str, row.get("reason_code"))] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError(
                "wave-60 native generation changed"
            )
        native = cast(dict[str, Any], native_raw)
        tickets = cast(list[object], row.get("native_tickets", []))
        native_count = (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD[
                method_id
            ]
        )
        configuration_count = (
            LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD[
                method_id
            ]
        )
        if (
            native.get("legacy_method_id") != method_id
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD[method_id]
            or native.get("causal_protocol") != CAUSAL_PROTOCOL
            or native.get("candidate_k") is not None
            or row.get("candidate_k") != MODEL_CANDIDATE_K
            or native.get("combination_count") is not None
            or row.get("combination_count") != configuration_count
            or native.get("local_configuration_count")
            != configuration_count
            or native.get("native_ticket_count") != native_count
            or row.get("native_ticket_count") != native_count
            or native.get("ledger_file_sha256")
            != LEDGER_FILE_SHA256
            or native.get("ledger_content_sha256")
            != LEDGER_CONTENT_SHA256
            or native.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
            or native.get("imported_comparators_excluded")
            != list(
                IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE60_METHOD[
                    method_id
                ]
            )
            or len(tickets) != native_count
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError(
                f"wave-60 native semantics changed: {method_id}"
            )
        portfolios[method_id].append(
            cast(list[list[int]], tickets)
        )
    strategies: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS:
        if (
            statuses[method_id]
            != {"CLOSED_INSUFFICIENT_HISTORY": 1, "OK": 2148}
            or reasons[method_id]
            != {INSUFFICIENT_HISTORY_REASON: 1}
            or len(portfolios[method_id]) != 2148
        ):
            raise EvidenceBuildError(
                f"wave-60 execution distribution changed: {method_id}"
            )
        sequence_sha256 = hashlib.sha256(
            _canonical_bytes(portfolios[method_id])
        ).hexdigest()
        duplicate_counts = Counter(
            len(portfolio)
            - len({tuple(ticket) for ticket in portfolio})
            for portfolio in portfolios[method_id]
        )
        duplicate_distribution = {
            str(key): value
            for key, value in sorted(duplicate_counts.items())
        }
        if (
            sequence_sha256 != EXPECTED_SEQUENCE_SHA256[method_id]
            or duplicate_distribution
            != EXPECTED_DUPLICATE_DISTRIBUTIONS[method_id]
        ):
            raise EvidenceBuildError(
                f"wave-60 ticket sequence changed: {method_id}"
            )
        strategies.append(
            {
                "candidate_k_distribution": {"49": 2148},
                "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
                "causal_protocol": CAUSAL_PROTOCOL,
                "closed_execution_count": 1,
                "closed_reason_code_distribution": {
                    INSUFFICIENT_HISTORY_REASON: 1
                },
                "combination_count_distribution": {
                    str(
                        LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD[
                            method_id
                        ]
                    ): 2148
                },
                "execution_status_counts": {
                    "CLOSED_INSUFFICIENT_HISTORY": 1,
                    "OK": 2148,
                },
                "imported_comparators_excluded": list(
                    IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE60_METHOD[
                        method_id
                    ]
                ),
                "legacy_method_id": method_id,
                "native_duplicate_ticket_count_distribution": (
                    duplicate_distribution
                ),
                "native_ticket_count_distribution": {
                    str(
                        NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD[
                            method_id
                        ]
                    ): 2148
                },
                "native_ticket_semantics": (
                    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE60_METHOD[
                        method_id
                    ]
                ),
                "ok_execution_count": 2148,
                "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD[
                        method_id
                    ]
                ),
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
        or report.get("dataset_sha256") != PINNED_DATASET_SHA256
        or report.get("target_draw_count") != 2149
        or report.get("progress") != EXPECTED_PROGRESS
        or report.get("input_raw_sha256")
        != EXPECTED_INPUT_FILE_SHA256
        or report.get("input_canonical_sha256")
        != EXPECTED_INPUT_CANONICAL_SHA256
        or report.get("research_disclaimer") != RESEARCH_DISCLAIMER
        or checksums != EXPECTED_REPORT_CHECKSUMS
    ):
        raise EvidenceBuildError("wave-60 report identity changed")
    return checksums


def build_evidence(
    *,
    base_catalog_path: Path,
    input_file: Path,
    parity_file: Path,
    report_file: Path,
    report_directory: Path,
) -> dict[str, object]:
    """Validate every wave-60 artifact and return compact evidence."""

    strategy_ids = _validate_catalog(base_catalog_path)
    parity = _validate_parity(parity_file)
    strategies = _validate_input(
        input_file,
        strategy_id_by_method=strategy_ids,
    )
    checksums = _validate_report(
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
        "dataset_sha256": PINNED_DATASET_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "input_canonical_sha256": EXPECTED_INPUT_CANONICAL_SHA256,
        "input_raw_sha256": EXPECTED_INPUT_FILE_SHA256,
        "ledger_content_sha256": LEDGER_CONTENT_SHA256,
        "ledger_file_sha256": LEDGER_FILE_SHA256,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "materialization_schema_version": MATERIALIZATION_SCHEMA_VERSION,
        "parity": parity,
        "report_checksums": checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_native_protocol": SOURCE_NATIVE_WAVE60_PROTOCOL,
        "strategies": strategies,
        "target_draw_count": 2149,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--parity-file", required=True, type=Path)
    parser.add_argument("--report-file", required=True, type=Path)
    parser.add_argument("--report-directory", required=True, type=Path)
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
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
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
