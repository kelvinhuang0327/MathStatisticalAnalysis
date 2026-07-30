#!/usr/bin/env python3
"""Build compact evidence for both wave-58 causal backtests."""

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
from lottolab.application.legacy_dual_seeded_native_portfolios_wave58 import (
    CAUSAL_ELIGIBILITY_RULE,
    ENHANCED_DUAL_METHOD_ID,
    FROZEN_SOURCE_COMMIT,
    IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE58_METHOD,
    INSUFFICIENT_HISTORY_REASON,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE58_METHOD,
    MINIMUM_HISTORY_DRAWS_BY_SOURCE_NATIVE_WAVE58_METHOD,
    MODEL_CANDIDATE_K,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE58_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE58_METHOD,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE58_METHOD,
    RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE58_METHOD,
    SEEDED_V6_METHOD_ID,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE58_METHOD,
    SOURCE_NATIVE_WAVE58_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE58_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_dual_seeded_native_batch_import_wave58 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_DUAL_SEEDED_WAVE58_EVIDENCE_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_DUAL_SEEDED_WAVE58_PARITY_V1"
)
BASE_CATALOG_SHA256 = (
    "6316066d537d3966d25549f7a8d220db13a5b5b506345f779dcfdb7e75c7f476"
)
BASE_CATALOG_FILE_SHA256 = (
    "b2ae5e48fa59f6619b853d6bdf3d4a2e5a05f5aa840e139950b2539cdc9686f7"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 124,
    "CLOSED_UNEXECUTABLE": 73,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 12,
}
EXPECTED_PROGRESS = {
    "backtested_count": 126,
    "closed_count": 73,
    "duplicate_alias_count": 12,
    "owner_decision_required_count": 10,
    "reproduced_count": 126,
    "total_strategy_count": 221,
    "uncompleted_count": 10,
}
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_FILE_SHA256 = (
    "68d841d826fe7904bcd9cd0498234ed4f42e8883390d4b1bd06241c37b03f9a7"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "93bf5662d66ed7bd7a9add2e87d59e7b3cc4df05349905c8db419aa1cba26b29"
)
EXPECTED_PARITY_FILE_SHA256 = (
    "653afe296021e296f495e2b131bc3a55bf5b76010f76b7b8c3a82f3e1f4c39af"
)
EXPECTED_PARITY_SHA256 = (
    "5243a1537b7f109a9cc784c12cf1621f2f2f109055c837ca8e9f41611890440e"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "8c4a71e41a6de16d3fbea7f79a2ecfafdbaeadf7344f4af277e1f1ca0e1d0a99"
)
EXPECTED_REPORT_SHA256 = (
    "9d797d7300cebba69af48389ac792bf23520b043dad39b63c5469f3c05509f04"
)
EXPECTED_ALL_SEQUENCE_SHA256 = {
    ENHANCED_DUAL_METHOD_ID: (
        "2e13908ce4c9e0bd573dd616211cc08a31d8680d2893263b69a9b0df25a412ca"
    ),
    SEEDED_V6_METHOD_ID: (
        "7c1bcabd88497d3ce9517028d5ff9629c6d3e0b9599b3fc354230367af794814"
    ),
}
EXPECTED_OK_SEQUENCE_SHA256 = {
    ENHANCED_DUAL_METHOD_ID: (
        "202affe6cb1b949469bc3d14cad63653f66a9badad05a0bcc2f1d76dfef7b19b"
    ),
    SEEDED_V6_METHOD_ID: (
        "e78dd91dd381562789ac0903fa030ac53082d7c39c063cdc3cd8b23f1ecc395e"
    ),
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "ec1d4d90a7aa425b976ed53322b025980ac89ff17e442a3f2677d3cd504b3f35"
    ),
    "biglotto_execution_audit.csv": (
        "69dde8091b9a9a4a5a17a99d8dda82fdd176ae456da5037e24fd98c4016b9586"
    ),
    "biglotto_full_rankings.csv": (
        "834aaa7283b20ac48890a84184fca5730a2f731de00486542b032a7c90ed0c8c"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "8c4a71e41a6de16d3fbea7f79a2ecfafdbaeadf7344f4af277e1f1ca0e1d0a99"
    ),
    "biglotto_official_prize_distributions.csv": (
        "1442286baaff2d5dfcc768ae2e90ae0067450b0a346a1e1a880264334ad058e1"
    ),
    "biglotto_strategy_universe.csv": (
        "03cb0205c7717b14d66693cbd85ba6f42b0dc8dc1bae5f74a2c4596f1ed6f448"
    ),
    "biglotto_success_metrics.csv": (
        "baea867f0c8f1429aeb9fc05647056e9281127ed85c14b1358f66c53e0f30696"
    ),
    "biglotto_top10.csv": (
        "1d578317289301979ab3661b4b5ac7cfd61b6c6323bbac328f73184100cd9eda"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-58 evidence inputs violate the frozen contract."""


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
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS:
            continue
        typed_method_id = cast(str, method_id)
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE58_METHOD[
                typed_method_id
            ]
            or type(row.get("strategy_id")) is not str
        ):
            raise EvidenceBuildError(
                f"wave-58 catalog row changed: {method_id}"
            )
        by_method[typed_method_id] = cast(str, row["strategy_id"])
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS):
        raise EvidenceBuildError("wave-58 catalog method set changed")
    return by_method


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    expected_statuses = {
        method_id: {
            "CLOSED_INSUFFICIENT_HISTORY": (
                MINIMUM_HISTORY_DRAWS_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    method_id
                ]
            ),
            "OK": (
                2149
                - MINIMUM_HISTORY_DRAWS_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    method_id
                ]
            ),
        }
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS
    }
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("native_ticket_case_count") != 10542
        or parity.get("status_counts_by_method")
        != expected_statuses
        or parity.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or parity.get("ledger_content_sha256")
        != LEDGER_CONTENT_SHA256
        or parity.get("ticket_sequence_sha256_by_method")
        != EXPECTED_ALL_SEQUENCE_SHA256
        or parity.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
    ):
        raise EvidenceBuildError("wave-58 parity identity changed")
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
        or len(cast(list[object], document.get("targets", []))) != 2149
        or len(executions) != 4298
    ):
        raise EvidenceBuildError("wave-58 full input identity changed")
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
            raise EvidenceBuildError("wave-58 execution changed")
        row = cast(dict[str, Any], candidate)
        method_id = method_by_strategy_id.get(
            cast(str, row.get("strategy_id"))
        )
        if method_id is None:
            raise EvidenceBuildError("wave-58 strategy identity changed")
        status = cast(str, row.get("status"))
        statuses[method_id][status] += 1
        if status != "OK":
            reason = cast(str, row.get("reason_code"))
            reasons[method_id][reason] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError(
                "wave-58 native generation changed"
            )
        native = cast(dict[str, Any], native_raw)
        native_tickets = cast(
            list[object],
            row.get("native_tickets", []),
        )
        expected_native_count = (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE58_METHOD[method_id]
        )
        if (
            native.get("legacy_method_id") != method_id
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE58_METHOD[method_id]
            or native.get("candidate_k") is not None
            or native.get("source_candidate_k_values")
            != list(
                SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    method_id
                ]
            )
            or row.get("candidate_k") != MODEL_CANDIDATE_K
            or native.get("combination_count") is not None
            or row.get("combination_count") is not None
            or native.get("native_ticket_count")
            != expected_native_count
            or row.get("native_ticket_count")
            != expected_native_count
            or native.get("causal_eligibility_rule")
            != CAUSAL_ELIGIBILITY_RULE
            or native.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
            or native.get("random_protocol")
            != RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE58_METHOD[method_id]
            or native.get("randomness_used")
            is not RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE58_METHOD[
                method_id
            ]
            or native.get("ledger_file_sha256")
            != LEDGER_FILE_SHA256
            or native.get("ledger_content_sha256")
            != LEDGER_CONTENT_SHA256
            or native.get("local_source_configuration")
            != LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE58_METHOD[
                method_id
            ]
            or native.get("imported_comparators_excluded")
            != list(
                IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    method_id
                ]
            )
            or len(native_tickets) != expected_native_count
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError(
                f"wave-58 native semantics changed: {method_id}"
            )
        portfolios[method_id].append(
            cast(list[list[int]], native_tickets)
        )
    strategies: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS:
        minimum = (
            MINIMUM_HISTORY_DRAWS_BY_SOURCE_NATIVE_WAVE58_METHOD[
                method_id
            ]
        )
        ok_count = 2149 - minimum
        sequence_sha256 = hashlib.sha256(
            _canonical_bytes(portfolios[method_id])
        ).hexdigest()
        if (
            statuses[method_id]
            != {
                "CLOSED_INSUFFICIENT_HISTORY": minimum,
                "OK": ok_count,
            }
            or reasons[method_id]
            != {INSUFFICIENT_HISTORY_REASON: minimum}
            or len(portfolios[method_id]) != ok_count
            or sequence_sha256
            != EXPECTED_OK_SEQUENCE_SHA256[method_id]
        ):
            raise EvidenceBuildError(
                f"wave-58 execution distribution changed: {method_id}"
            )
        native_count = (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE58_METHOD[method_id]
        )
        duplicate_counts = Counter(
            len(portfolio)
            - len({tuple(ticket) for ticket in portfolio})
            for portfolio in portfolios[method_id]
        )
        strategies.append(
            {
                "candidate_k_distribution": {"49": ok_count},
                "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
                "closed_execution_count": minimum,
                "closed_reason_code_distribution": {
                    INSUFFICIENT_HISTORY_REASON: minimum
                },
                "combination_count_distribution": {"null": ok_count},
                "execution_status_counts": {
                    "CLOSED_INSUFFICIENT_HISTORY": minimum,
                    "OK": ok_count,
                },
                "imported_comparators_excluded": list(
                    IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE58_METHOD[
                        method_id
                    ]
                ),
                "legacy_method_id": method_id,
                "local_source_configuration": (
                    LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE58_METHOD[
                        method_id
                    ]
                ),
                "minimum_history_draws": minimum,
                "native_duplicate_ticket_count_distribution": {
                    str(key): value
                    for key, value in sorted(duplicate_counts.items())
                },
                "native_ticket_count_distribution": {
                    str(native_count): ok_count
                },
                "native_ticket_semantics": (
                    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE58_METHOD[
                        method_id
                    ]
                ),
                "ok_execution_count": ok_count,
                "random_protocol": (
                    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE58_METHOD[
                        method_id
                    ]
                ),
                "randomness_reproduction": (
                    "SOURCE_RUNTIME_LEDGER_EXACT_TICKET_REPLAY"
                ),
                "randomness_used": (
                    RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE58_METHOD[
                        method_id
                    ]
                ),
                "source_candidate_k_values": list(
                    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE58_METHOD[
                        method_id
                    ]
                ),
                "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE58_METHOD[
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
        raise EvidenceBuildError("wave-58 report identity changed")
    return checksums


def build_evidence(
    *,
    base_catalog_path: Path,
    input_file: Path,
    parity_file: Path,
    report_file: Path,
    report_directory: Path,
) -> dict[str, object]:
    """Validate every wave-58 artifact and return compact evidence."""

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
        "parity": parity,
        "report_checksums": report_checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_native_protocol": SOURCE_NATIVE_WAVE58_PROTOCOL,
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
