#!/usr/bin/env python3
"""Build compact evidence for the wave-57 HPSB causal backtest and alias."""

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
    RESEARCH_DISCLAIMER,
)
from lottolab.application.legacy_hpsb_native_portfolios_wave57 import (
    CAUSAL_ELIGIBILITY_RULE,
    ENSEMBLE_ALIAS_METHOD_ID,
    FROZEN_SOURCE_COMMIT,
    HPSB_METHOD_ID,
    IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE57_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE57_METHOD,
    MODEL_CANDIDATE_K,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE57_METHOD,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE57_METHOD,
    RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE57_METHOD,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE57_METHOD,
    SOURCE_NATIVE_WAVE57_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE57_METHOD,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_hpsb_native_batch_import_wave57 import (
    MATERIALIZATION_SCHEMA_VERSION,
    NO_CAUSAL_CUTOFF_REASON,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_HPSB_NATIVE_WAVE57_EVIDENCE_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_HPSB_NATIVE_WAVE57_PARITY_V1"
)
BASE_CATALOG_SHA256 = (
    "46f4a8aab26f63db2db1c1299e90bd9e516d10f53fdfcb35251d18259a47278b"
)
BASE_CATALOG_FILE_SHA256 = (
    "524cbf255ee3d791691ce6f946b554ff2e2b941c5815967e6f874a7c7f3ea465"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 123,
    "CLOSED_UNEXECUTABLE": 73,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 14,
}
EXPECTED_PROGRESS = {
    "backtested_count": 124,
    "closed_count": 73,
    "duplicate_alias_count": 11,
    "owner_decision_required_count": 13,
    "reproduced_count": 124,
    "total_strategy_count": 221,
    "uncompleted_count": 13,
}
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_FILE_SHA256 = (
    "caa29d5e1e9c68df790197321c1b98a3421b9ddebb056323d0d221ab38ea6384"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "10a44c3ac64306432d02604b74bbfd1ef9c7d07cf58f937cec148cb782eae8b8"
)
EXPECTED_PARITY_FILE_SHA256 = (
    "01b263e415318cb13ba78eb866b009be1544bffa63fe52e43d0367db45fa0c9a"
)
EXPECTED_PARITY_SHA256 = (
    "aba837bdf2680da52ab28ab095532ace02c14f29b63eba6c2fa094f912cb72ec"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "428f03b71362606c1102b9cd80c4f6888f96e83f039924e1978c4bc1a77d7a9d"
)
EXPECTED_REPORT_SHA256 = (
    "a419af476eb6bb3cc8205b40c42c1a5602cd7af6c5b92e49557abeccebbd323d"
)
EXPECTED_ALL_TARGET_TICKET_SEQUENCE_SHA256 = (
    "0133cd250129a5f24aa273ef5a28d1320e4e9837c64833f6faf4c7733c2e1320"
)
EXPECTED_OK_TICKET_SEQUENCE_SHA256 = (
    "1b3acdf5a173d266dbf245da228c3b447e797cc0a6bc2a90dabdbab6abf307fe"
)
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "7ff1137fa556e77a2894e7bd2671a6c5f2f47432c53f32cf3ea3444d191b1df8"
    ),
    "biglotto_execution_audit.csv": (
        "df766d11536b2b3423c6dd2a269e8967e9fbaebd75c318dc6cfcc7ad67126809"
    ),
    "biglotto_full_rankings.csv": (
        "fd6656a840b8e315ce240bf96b581be5d81a2ca238c1d1d24cd7eef0e72a029c"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "428f03b71362606c1102b9cd80c4f6888f96e83f039924e1978c4bc1a77d7a9d"
    ),
    "biglotto_official_prize_distributions.csv": (
        "19cf929a85b624742097fff4bbe7581ab4569c3cbbdd20bf008552916a794d13"
    ),
    "biglotto_strategy_universe.csv": (
        "244922aa26c64abc457d208bc44ec65782d6d510784a8333fdf01d93ea88b1fd"
    ),
    "biglotto_success_metrics.csv": (
        "3b9b4e16721de59d84ae90ab0f49be2f51ed0a3db45339b4c1b2e620fa723ac4"
    ),
    "biglotto_top10.csv": (
        "5cd0cfd1482e999d8ac2c025ed173905476cebed2f7975807c2e7df7b48fbff8"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-57 evidence inputs violate the frozen contract."""


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
    expected_methods = {HPSB_METHOD_ID, ENSEMBLE_ALIAS_METHOD_ID}
    records = cast(list[object], catalog.get("records", []))
    by_method: dict[str, str] = {}
    for candidate in records:
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id not in expected_methods:
            continue
        typed_method_id = cast(str, method_id)
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE57_METHOD[
                typed_method_id
            ]
            or type(row.get("strategy_id")) is not str
        ):
            raise EvidenceBuildError(
                f"wave-57 catalog row changed: {method_id}"
            )
        by_method[typed_method_id] = cast(str, row["strategy_id"])
    if set(by_method) != expected_methods:
        raise EvidenceBuildError("wave-57 catalog method set changed")
    return by_method


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    expected_sequences = {
        HPSB_METHOD_ID: EXPECTED_ALL_TARGET_TICKET_SEQUENCE_SHA256,
        ENSEMBLE_ALIAS_METHOD_ID: (
            EXPECTED_ALL_TARGET_TICKET_SEQUENCE_SHA256
        ),
    }
    expected_alias = {
        "alias_method_id": ENSEMBLE_ALIAS_METHOD_ID,
        "canonical_method_id": HPSB_METHOD_ID,
        "exact_match_count": 2149,
        "reason_code": (
            "EXACT_ALL_TARGET_DEFAULT_ENTRYPOINT_ALIAS_TO_HPSB_V2"
        ),
        "target_count": 2149,
    }
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("eligible_target_count") != 2149
        or parity.get("native_ticket_case_count") != 2149
        or parity.get("audited_native_ticket_case_count") != 4298
        or parity.get("first_target_history_draw_count") != 0
        or parity.get("alias_disposition") != expected_alias
        or parity.get("cross_wave_exact_alias_candidates") != []
        or parity.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or parity.get("ledger_content_sha256")
        != LEDGER_CONTENT_SHA256
        or parity.get("ticket_sequence_sha256_by_method")
        != expected_sequences
        or parity.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
    ):
        raise EvidenceBuildError("wave-57 parity identity changed")
    return parity


def _validate_input(
    path: Path,
    *,
    strategy_id_by_method: dict[str, str],
) -> dict[str, object]:
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
        or len(executions) != 2149
    ):
        raise EvidenceBuildError("wave-57 full input identity changed")
    canonical_strategy_id = strategy_id_by_method[HPSB_METHOD_ID]
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    portfolios: list[list[list[int]]] = []
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-57 execution changed")
        row = cast(dict[str, Any], candidate)
        if row.get("strategy_id") != canonical_strategy_id:
            raise EvidenceBuildError("wave-57 strategy identity changed")
        status = cast(str, row.get("status"))
        statuses[status] += 1
        if status != "OK":
            reason = cast(str, row.get("reason_code"))
            reasons[reason] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError(
                "wave-57 native generation changed"
            )
        native = cast(dict[str, Any], native_raw)
        native_tickets = cast(
            list[object],
            row.get("native_tickets", []),
        )
        if (
            native.get("legacy_method_id") != HPSB_METHOD_ID
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE57_METHOD[
                HPSB_METHOD_ID
            ]
            or native.get("candidate_k") is not None
            or native.get("source_candidate_k_values")
            != list(
                SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE57_METHOD[
                    HPSB_METHOD_ID
                ]
            )
            or row.get("candidate_k") != MODEL_CANDIDATE_K
            or native.get("combination_count") is not None
            or row.get("combination_count") is not None
            or native.get("native_ticket_count") != 1
            or row.get("native_ticket_count") != 1
            or native.get("native_duplicate_ticket_count") != 0
            or native.get("causal_eligibility_rule")
            != CAUSAL_ELIGIBILITY_RULE
            or native.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
            or native.get("random_protocol")
            != RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE57_METHOD[
                HPSB_METHOD_ID
            ]
            or native.get("randomness_used")
            is not RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE57_METHOD[
                HPSB_METHOD_ID
            ]
            or native.get("ledger_file_sha256")
            != LEDGER_FILE_SHA256
            or native.get("ledger_content_sha256")
            != LEDGER_CONTENT_SHA256
            or native.get("local_source_configuration")
            != LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE57_METHOD[
                HPSB_METHOD_ID
            ]
            or native.get("imported_comparators_excluded")
            != list(
                IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE57_METHOD[
                    HPSB_METHOD_ID
                ]
            )
            or len(native_tickets) != 1
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError(
                "wave-57 native semantics changed"
            )
        portfolios.append(cast(list[list[int]], native_tickets))
    sequence_sha256 = hashlib.sha256(
        _canonical_bytes(portfolios)
    ).hexdigest()
    if (
        statuses
        != {"CLOSED_INSUFFICIENT_HISTORY": 1, "OK": 2148}
        or reasons != {NO_CAUSAL_CUTOFF_REASON: 1}
        or len(portfolios) != 2148
        or sequence_sha256 != EXPECTED_OK_TICKET_SEQUENCE_SHA256
    ):
        raise EvidenceBuildError(
            "wave-57 execution distribution changed"
        )
    return {
        "candidate_k_distribution": {"49": 2148},
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "closed_execution_count": 1,
        "closed_reason_code_distribution": {
            NO_CAUSAL_CUTOFF_REASON: 1
        },
        "combination_count_distribution": {"null": 2148},
        "execution_status_counts": {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
            "OK": 2148,
        },
        "imported_comparators_excluded": list(
            IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE57_METHOD[
                HPSB_METHOD_ID
            ]
        ),
        "legacy_method_id": HPSB_METHOD_ID,
        "local_source_configuration": (
            LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE57_METHOD[
                HPSB_METHOD_ID
            ]
        ),
        "native_duplicate_ticket_count_distribution": {"0": 2148},
        "native_ticket_count_distribution": {"1": 2148},
        "native_ticket_semantics": (
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE57_METHOD[
                HPSB_METHOD_ID
            ]
        ),
        "ok_execution_count": 2148,
        "random_protocol": (
            RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE57_METHOD[HPSB_METHOD_ID]
        ),
        "randomness_reproduction": (
            "SOURCE_RUNTIME_LEDGER_EXACT_TICKET_REPLAY"
        ),
        "randomness_used": (
            RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE57_METHOD[HPSB_METHOD_ID]
        ),
        "source_candidate_k_values": list(
            SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE57_METHOD[
                HPSB_METHOD_ID
            ]
        ),
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE57_METHOD[HPSB_METHOD_ID]
        ),
        "ticket_sequence_sha256": sequence_sha256,
    }


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
        raise EvidenceBuildError("wave-57 report identity changed")
    return checksums


def build_evidence(
    *,
    base_catalog_path: Path,
    input_file: Path,
    parity_file: Path,
    report_file: Path,
    report_directory: Path,
) -> dict[str, object]:
    """Validate every wave-57 artifact and return compact evidence."""

    strategy_id_by_method = _validate_catalog(base_catalog_path)
    parity = _validate_parity(parity_file)
    strategy = _validate_input(
        input_file,
        strategy_id_by_method=strategy_id_by_method,
    )
    report_checksums = _validate_report(
        report_file=report_file,
        report_directory=report_directory,
    )
    return {
        "alias_disposition": parity["alias_disposition"],
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
        "source_native_protocol": SOURCE_NATIVE_WAVE57_PROTOCOL,
        "strategies": [strategy],
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
