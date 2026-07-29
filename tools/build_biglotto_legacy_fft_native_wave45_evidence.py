#!/usr/bin/env python3
"""Build compact evidence for the wave-45 FFT-native dispositions."""

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
from lottolab.application.legacy_fft_native_portfolios_wave45 import (
    FROZEN_SOURCE_COMMIT,
    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE45_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE45_METHOD,
    MODEL_CANDIDATE_K,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE45_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE45_METHOD,
    SOURCE_NATIVE_WAVE45_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE45_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS,
    TRIPLE_ALIAS_METHOD_ID,
    TRIPLE_ORIGINAL_METHOD_ID,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_fft_native_batch_import_wave45 import (
    CLOSED_REASON,
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_FFT_NATIVE_WAVE45_EVIDENCE_V1"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_FFT_NATIVE_WAVE45_PARITY_V1"
BASE_CATALOG_SHA256 = "b18e432eac7be977fe81e9d4fd1bc71830fcffde20a48579572ddde55de77f4e"
BASE_CATALOG_FILE_SHA256 = "ed43a5e50f66d2d00d8d8dbaf1a69447c6cf70dee8b2c9b38e643bd3f0c28c38"
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 83,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 7,
    "OWNER_DECISION_REQUIRED": 66,
}
EXPECTED_PROGRESS = {
    "backtested_count": 87,
    "closed_count": 65,
    "duplicate_alias_count": 8,
    "owner_decision_required_count": 61,
    "reproduced_count": 87,
    "total_strategy_count": 221,
    "uncompleted_count": 61,
}
EXPECTED_DATABASE_SHA256 = "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
EXPECTED_INPUT_FILE_SHA256 = "e1279cd05dfbdb7e7d8a9e1b6667f2099a54543dd71b7881435550bf25ef51c4"
EXPECTED_INPUT_CANONICAL_SHA256 = "72c10326fd66073ed40cf5d77a115a7c2aafe2a73cac3e70442a3b7edae92907"
EXPECTED_PARITY_FILE_SHA256 = "2a1b0c033e2e94f03b52cc988a89f7005d06a3f83522f9c3147aa0531991e6bf"
EXPECTED_PARITY_SHA256 = "ff1f8fdbc1b5adee1b396d5ae4fd25ce15ef4a286e6f7fbd372a0ab44f549d1b"
EXPECTED_REPORT_FILE_SHA256 = "35fbeb737f6ef4f53c0019a48364c1175f5a3234f54e4c3ba473eb97ff970c6e"
EXPECTED_REPORT_SHA256 = "8ec3c9b7631ba03837313775e00ed5b96df462bd1d377d230291acc8b4687e0a"
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": ("ee9579e6ef1f645b56107a82de673393e4f53ee8a3cf081b2320ded385e3c094"),
    "biglotto_execution_audit.csv": (
        "2e99ed5800c773a143754fbabd1ab2868fc77ff75a6605320ee8e9aba31d821d"
    ),
    "biglotto_full_rankings.csv": (
        "3e062b474331c810b2f4dac9911370279778ed8db3a49a2e7001c517deeff395"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "35fbeb737f6ef4f53c0019a48364c1175f5a3234f54e4c3ba473eb97ff970c6e"
    ),
    "biglotto_official_prize_distributions.csv": (
        "38a8f45adea327e751f66117bad81005c1adc22047da1ada59173bbd3b46b2e2"
    ),
    "biglotto_strategy_universe.csv": (
        "8a1e980660e736ab3b908b9f0a89ca24b39ae2a12be152ad3c4838d84b0fda82"
    ),
    "biglotto_success_metrics.csv": (
        "23845a73e62b4653ab1b283313b1f96b362dc13188855c18e28792b3c5069d12"
    ),
    "biglotto_top10.csv": ("6171b07011cb18d958d42469c85dbf04d4a13bb2c63154cfcc208286846bb723"),
}
EXPECTED_OK_COUNTS = {
    "tools/backtest_big_lotto_3bet.py": 1649,
    "tools/backtest_biglotto_triple_strike_original.py": 1649,
    "tools/backtest_fcf_vs_ts3.py": 1999,
    "tools/verify_markov_vs_triple_2bet.py": 1648,
}
EXPECTED_CLOSED_COUNTS = {
    "tools/backtest_big_lotto_3bet.py": 500,
    "tools/backtest_biglotto_triple_strike_original.py": 500,
    "tools/backtest_fcf_vs_ts3.py": 150,
    "tools/verify_markov_vs_triple_2bet.py": 501,
}


class EvidenceBuildError(ValueError):
    """Wave-45 evidence inputs violate the frozen contract."""


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
        raise EvidenceBuildError(f"{path.name}: top level must be an object")
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
    relevant = {
        *SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS,
        TRIPLE_ALIAS_METHOD_ID,
    }
    for candidate in cast(list[object], catalog.get("records", [])):
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id not in relevant:
            continue
        typed_method_id = cast(str, method_id)
        if (
            row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE45_METHOD[typed_method_id]
            or type(row.get("strategy_id")) is not str
        ):
            raise EvidenceBuildError(f"wave-45 catalog row changed: {method_id}")
        by_method[typed_method_id] = cast(str, row["strategy_id"])
    if set(by_method) != relevant:
        raise EvidenceBuildError("wave-45 catalog method set changed")
    return by_method


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version") != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or parity.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or parity.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or parity.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or parity.get("alias_source_method") != TRIPLE_ALIAS_METHOD_ID
        or parity.get("alias_target_method") != TRIPLE_ORIGINAL_METHOD_ID
        or parity.get("alias_case_count") != 1648
        or parity.get("alias_mismatch_count") != 0
        or parity.get("intra_ticket_canonicalization_count_by_method")
        != {
            "tools/backtest_big_lotto_3bet.py": 0,
            "tools/backtest_biglotto_triple_strike_original.py": 0,
            "tools/backtest_fcf_vs_ts3.py": 0,
            "tools/verify_biglotto_3bet_comparison.py": 0,
            "tools/verify_markov_vs_triple_2bet.py": 3181,
        }
    ):
        raise EvidenceBuildError("wave-45 parity identity changed")
    return parity


def _distribution(values: list[object]) -> dict[str, int]:
    counts = Counter(
        "null" if value is None else (str(value).lower() if isinstance(value, bool) else str(value))
        for value in values
    )
    return dict(sorted(counts.items()))


def _validate_input(
    path: Path,
    *,
    strategy_id_by_method: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    document, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_INPUT_FILE_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest() != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or document.get("dataset_version") != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", []))) != 2149
        or len(cast(list[object], document.get("executions", []))) != 8596
    ):
        raise EvidenceBuildError("wave-45 full input identity changed")
    method_by_strategy_id = {
        strategy_id: method_id
        for method_id, strategy_id in strategy_id_by_method.items()
        if method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS
    }
    rows_by_method: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in cast(
        list[object],
        document.get("executions", []),
    ):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-45 execution changed")
        row = cast(dict[str, Any], candidate)
        method_id = method_by_strategy_id.get(cast(str, row.get("strategy_id")))
        if method_id is None:
            raise EvidenceBuildError("wave-45 execution strategy identity changed")
        rows_by_method[method_id].append(row)
    strategies: list[dict[str, Any]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS:
        rows = rows_by_method[method_id]
        status_counts = Counter(cast(str, row.get("status")) for row in rows)
        if status_counts != {
            "OK": EXPECTED_OK_COUNTS[method_id],
            "CLOSED_INSUFFICIENT_HISTORY": (EXPECTED_CLOSED_COUNTS[method_id]),
        }:
            raise EvidenceBuildError(f"wave-45 status counts changed: {method_id}")
        ok = [row for row in rows if row.get("status") == "OK"]
        closed = [row for row in rows if row.get("status") == "CLOSED_INSUFFICIENT_HISTORY"]
        if any(row.get("reason_code") != CLOSED_REASON for row in closed):
            raise EvidenceBuildError(f"wave-45 closure changed: {method_id}")
        native_generation = [
            cast(dict[str, Any], row.get("native_generation"))
            for row in ok
            if isinstance(row.get("native_generation"), dict)
        ]
        if (
            len(native_generation) != len(ok)
            or any(row.get("candidate_k") != MODEL_CANDIDATE_K for row in ok)
            or any(
                row.get("portfolio_ticket_count") != 20
                or row.get("portfolio_derivation") != CONSTRUCTOR_IDENTIFIER
                for row in ok
            )
            or any(
                generation.get("candidate_k") is not None
                or generation.get("combination_count") is not None
                or generation.get("ledger_file_sha256") != LEDGER_FILE_SHA256
                or generation.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
                for generation in native_generation
            )
        ):
            raise EvidenceBuildError(f"wave-45 execution semantics changed: {method_id}")
        strategies.append(
            {
                "candidate_k_distribution": _distribution([row.get("candidate_k") for row in ok]),
                "closed_execution_count": len(closed),
                "combination_count_distribution": _distribution(
                    [row.get("combination_count") for row in ok]
                ),
                "execution_status_counts": dict(sorted(status_counts.items())),
                "intra_ticket_order_semantics": (
                    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id]
                ),
                "legacy_method_id": method_id,
                "minimum_history_draws": (
                    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id]
                ),
                "native_duplicate_ticket_count_distribution": (
                    _distribution(
                        [
                            generation.get("native_duplicate_ticket_count")
                            for generation in native_generation
                        ]
                    )
                ),
                "native_ticket_count_distribution": _distribution(
                    [row.get("native_ticket_count") for row in ok]
                ),
                "ok_execution_count": len(ok),
                "source_combination_count": (
                    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id]
                ),
                "source_combination_members": list(
                    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id]
                ),
                "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
                "source_sha256": (SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id]),
                "strategy_id": strategy_id_by_method[method_id],
            }
        )
    return strategies, document


def _validate_report(
    path: Path,
    *,
    strategy_ids: set[str],
) -> tuple[dict[str, Any], dict[str, str]]:
    report, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_REPORT_FILE_SHA256
        or report.get("report_sha256") != EXPECTED_REPORT_SHA256
        or report.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version") != BACKTEST_POLICY_VERSION
        or report.get("input_raw_sha256") != EXPECTED_INPUT_FILE_SHA256
        or report.get("input_canonical_sha256") != EXPECTED_INPUT_CANONICAL_SHA256
        or report.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or report.get("target_draw_count") != 2149
        or report.get("progress")
        != {
            "backtested_count": 87,
            "closed_count": 65,
            "duplicate_alias_count": 7,
            "owner_decision_required_count": 62,
            "reproduced_count": 87,
            "total_strategy_count": 221,
            "uncompleted_count": 62,
        }
        or report.get("research_disclaimer") != RESEARCH_DISCLAIMER
    ):
        raise EvidenceBuildError("wave-45 report identity changed")
    metrics = cast(list[dict[str, Any]], report.get("metrics", []))
    prizes = cast(
        list[dict[str, Any]],
        report.get("official_prize_distributions", []),
    )
    rankings = cast(list[object], report.get("rankings", []))
    if (
        len(metrics) != 512
        or len(prizes) != 64
        or len(rankings) != 28288
        or Counter(cast(str, row.get("strategy_id")) for row in metrics)
        != Counter({strategy_id: 128 for strategy_id in strategy_ids})
        or Counter(cast(str, row.get("strategy_id")) for row in prizes)
        != Counter({strategy_id: 16 for strategy_id in strategy_ids})
        or {cast(int, row.get("prefix_count")) for row in metrics} != {5, 10, 15, 20}
        or {cast(str, row.get("window")) for row in metrics}
        != {"FULL", "RECENT_750", "RECENT_300", "RECENT_50"}
        or len({cast(str, row.get("criterion")) for row in metrics}) != 8
        or any(
            row.get("exact_random_baseline_probability") is None
            or row.get("random_baseline_rate_difference") is None
            for row in metrics
        )
    ):
        raise EvidenceBuildError("wave-45 metric, prize, or ranking coverage changed")
    report_directory = path.parent
    checksums = {
        file_path.name: hashlib.sha256(file_path.read_bytes()).hexdigest()
        for file_path in report_directory.iterdir()
        if file_path.is_file()
    }
    if checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("wave-45 report checksums changed")
    return report, checksums


def build_evidence(
    *,
    base_catalog_path: Path,
    parity_path: Path,
    input_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate all artifacts and return the compact wave-45 proof."""

    strategy_id_by_method = _validate_catalog(base_catalog_path)
    parity = _validate_parity(parity_path)
    strategies, _input = _validate_input(
        input_path,
        strategy_id_by_method=strategy_id_by_method,
    )
    report, report_checksums = _validate_report(
        report_path,
        strategy_ids={
            strategy_id_by_method[method_id] for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS
        },
    )
    document: dict[str, object] = {
        "alias_disposition": {
            "alias_method_id": TRIPLE_ALIAS_METHOD_ID,
            "alias_source_sha256": (
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE45_METHOD[TRIPLE_ALIAS_METHOD_ID]
            ),
            "alias_strategy_id": strategy_id_by_method[TRIPLE_ALIAS_METHOD_ID],
            "canonical_method_id": TRIPLE_ORIGINAL_METHOD_ID,
            "canonical_strategy_id": strategy_id_by_method[TRIPLE_ORIGINAL_METHOD_ID],
            "overlapping_causal_output_case_count": 1648,
            "output_mismatch_count": 0,
            "status": "DUPLICATE_ALIAS",
        },
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "dataset_sha256": EXPECTED_DATABASE_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "final_progress": EXPECTED_PROGRESS,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "input_canonical_sha256": EXPECTED_INPUT_CANONICAL_SHA256,
        "input_file_sha256": EXPECTED_INPUT_FILE_SHA256,
        "ledger_content_sha256": LEDGER_CONTENT_SHA256,
        "ledger_file_sha256": LEDGER_FILE_SHA256,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "parity_file_sha256": EXPECTED_PARITY_FILE_SHA256,
        "parity_sha256": parity["parity_sha256"],
        "report_checksums": report_checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": report["report_sha256"],
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_native_protocol": SOURCE_NATIVE_WAVE45_PROTOCOL,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "strategies": strategies,
        "target_draw_count": 2149,
    }
    document["evidence_sha256"] = hashlib.sha256(_canonical_bytes(document)).hexdigest()
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--parity", required=True, type=Path)
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--report-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output_file}")
    document = build_evidence(
        base_catalog_path=args.base_catalog,
        parity_path=args.parity,
        input_path=args.input_file,
        report_path=args.report_file,
    )
    payload = _canonical_bytes(document) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": document["evidence_sha256"],
                "output_file": str(args.output_file),
                "physical_file_sha256": hashlib.sha256(payload).hexdigest(),
                "strategy_disposition_count": 5,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
