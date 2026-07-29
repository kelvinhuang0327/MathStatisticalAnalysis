#!/usr/bin/env python3
"""Build compact evidence for the wave-44 checkpoint-native backtests."""

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
from lottolab.application.legacy_checkpoint_native_portfolios_wave44 import (
    CAUSAL_ELIGIBILITY_RULE,
    CHECKPOINT_BY_SOURCE_NATIVE_WAVE44_METHOD,
    CHECKPOINT_INTRODUCTION_COMMIT,
    CHECKPOINT_INTRODUCTION_TIME,
    FROZEN_SOURCE_COMMIT,
    IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE44_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE44_METHOD,
    MODEL_CANDIDATE_K,
    MODEL_CONTEXT_DRAW_COUNT,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE44_METHOD,
    SOURCE_NATIVE_WAVE44_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE44_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_checkpoint_native_batch_import_wave44 import (
    MATERIALIZATION_SCHEMA_VERSION,
    NONCAUSAL_TARGET_REASON,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_CHECKPOINT_NATIVE_WAVE44_EVIDENCE_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_CHECKPOINT_NATIVE_WAVE44_PARITY_V1"
)
BASE_CATALOG_SHA256 = (
    "c73ae9a4cb6aa872e839031b17975011b8ea0bb1b241336ab172a775afd3511a"
)
BASE_CATALOG_FILE_SHA256 = (
    "e5c40c227be80624a9134e44e4c6df2dd27157904faca612e3f103d8a663a351"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 80,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 7,
    "OWNER_DECISION_REQUIRED": 69,
}
EXPECTED_PROGRESS = {
    "backtested_count": 83,
    "closed_count": 65,
    "duplicate_alias_count": 7,
    "owner_decision_required_count": 66,
    "reproduced_count": 83,
    "total_strategy_count": 221,
    "uncompleted_count": 66,
}
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_FILE_SHA256 = (
    "e84c070c33cc6d70a186cab34b881d516a45e3826fac365620cfba050b4c5ef5"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "b482ecc6e9db23428d45160ea437ebb749007a140baaa5853426b2f089d6f759"
)
EXPECTED_PARITY_FILE_SHA256 = (
    "19680af17c03f5cb98e72093066fdf99b20d9651d9a8c2561094a7e9e4d272f8"
)
EXPECTED_PARITY_SHA256 = (
    "7e5456e3ebdd852cd21a636532ae3b8cc2989877e9042c46b76d72618a1a042c"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "03a5a6efb7cbe627cfcbd5106df9a93b073c8f89bf1e7d3d20bf714e2ca9d27a"
)
EXPECTED_REPORT_SHA256 = (
    "cd6dbb715da814764520a775738fe167363c9b203ca92caef65252953696e3d0"
)
EXPECTED_TICKET_SEQUENCE_SHA256 = {
    "ai_lab/scripts/benchmark_ai.py": (
        "e51ac6420fea97ff005a6dcc3619f1b07d684b1bab8eba780f2f7871cfbefd91"
    ),
    "ai_lab/scripts/benchmark_ai_zdp.py": (
        "4c2243c6740d52c885112e73906097cdb378b414be403c9a1ca75e8140b02cb7"
    ),
    "ai_lab/scripts/benchmark_v3.py": (
        "c59f017c3cc528605c09be38e56a9ace370b36b5e6446fb80dbbf7b623be9803"
    ),
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "0b86d11fbcf7dd2d89523fac4f6a057e1dbb68b23b605f2290d483fdc1fac70c"
    ),
    "biglotto_execution_audit.csv": (
        "4078d23d91a62be381ee49a8df7fd3e72cffd7d9397bcc057c3dd7f87b4d14fa"
    ),
    "biglotto_full_rankings.csv": (
        "4d75cfb14c7d058486a14aeef1f1c259ce093f0e6be9f762d1e4bfaf1abc9dd3"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "03a5a6efb7cbe627cfcbd5106df9a93b073c8f89bf1e7d3d20bf714e2ca9d27a"
    ),
    "biglotto_official_prize_distributions.csv": (
        "0d98e82c2dbd714b4217d681aa14e8cd0421a41411e9076d8776aa3008235130"
    ),
    "biglotto_strategy_universe.csv": (
        "5b689bdd3ba6b75f87852e024d8997391158a1a945d3956fa95df23dbdd06a80"
    ),
    "biglotto_success_metrics.csv": (
        "9a27300dcdb974f371a57172b2999ba4cbb9c2c7701b2bda654a32eeedac34de"
    ),
    "biglotto_top10.csv": (
        "efaa431d6d509ee5cd1ef2ebc5a520f90bdf2d5d05092e4bf6a7aa8b68e6841c"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-44 evidence inputs violate the frozen contract."""


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
        hashlib.sha256(raw).hexdigest()
        != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts")
        != EXPECTED_BASE_STATUS_COUNTS
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
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS:
            continue
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE44_METHOD[
                cast(str, method_id)
            ]
            or type(row.get("strategy_id")) is not str
        ):
            raise EvidenceBuildError(
                f"wave-44 catalog row changed: {method_id}"
            )
        by_method[cast(str, method_id)] = cast(str, row["strategy_id"])
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS):
        raise EvidenceBuildError("wave-44 catalog method set changed")
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
        or parity.get("eligible_target_count") != 48
        or parity.get("native_ticket_case_count") != 144
        or parity.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or parity.get("ledger_content_sha256")
        != LEDGER_CONTENT_SHA256
        or parity.get("ticket_sequence_sha256_by_method")
        != EXPECTED_TICKET_SEQUENCE_SHA256
        or parity.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
    ):
        raise EvidenceBuildError("wave-44 parity identity changed")
    return parity


def _validate_input(
    path: Path,
    *,
    strategy_id_by_method: dict[str, str],
) -> list[dict[str, object]]:
    document, raw = _read_json(path)
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
        or len(cast(list[object], document.get("executions", [])))
        != 6447
    ):
        raise EvidenceBuildError("wave-44 full input identity changed")
    method_by_strategy_id = {
        strategy_id: method_id
        for method_id, strategy_id in strategy_id_by_method.items()
    }
    statuses: defaultdict[str, Counter[str]] = defaultdict(Counter)
    reasons: defaultdict[str, Counter[str]] = defaultdict(Counter)
    tickets: defaultdict[str, list[list[int]]] = defaultdict(list)
    strategies: dict[str, dict[str, object]] = {}
    for candidate in cast(
        list[object],
        document.get("executions", []),
    ):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-44 execution changed")
        row = cast(dict[str, Any], candidate)
        strategy_id = row.get("strategy_id")
        method_id = method_by_strategy_id.get(cast(str, strategy_id))
        if method_id is None:
            raise EvidenceBuildError("wave-44 strategy identity changed")
        status = cast(str, row.get("status"))
        statuses[method_id][status] += 1
        if status != "OK":
            reason = row.get("reason_code")
            if reason != NONCAUSAL_TARGET_REASON:
                raise EvidenceBuildError(
                    "wave-44 closed reason changed"
                )
            reasons[method_id][cast(str, reason)] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError(
                "wave-44 native generation changed"
            )
        native = cast(dict[str, Any], native_raw)
        native_tickets = cast(
            list[object],
            row.get("native_tickets", []),
        )
        if (
            native.get("legacy_method_id") != method_id
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE44_METHOD[
                method_id
            ]
            or native.get("candidate_k") is not None
            or native.get("source_candidate_k_values") != [49]
            or row.get("candidate_k") != MODEL_CANDIDATE_K
            or native.get("combination_count") is not None
            or row.get("combination_count") is not None
            or native.get("native_ticket_count") != 1
            or row.get("native_ticket_count") != 1
            or native.get("native_duplicate_ticket_count") != 0
            or native.get("model_context_draw_count")
            != MODEL_CONTEXT_DRAW_COUNT
            or native.get("checkpoint_introduction_commit")
            != CHECKPOINT_INTRODUCTION_COMMIT
            or native.get("checkpoint_introduction_time")
            != CHECKPOINT_INTRODUCTION_TIME
            or native.get("causal_eligibility_rule")
            != CAUSAL_ELIGIBILITY_RULE
            or native.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
            or native.get("ledger_file_sha256")
            != LEDGER_FILE_SHA256
            or native.get("ledger_content_sha256")
            != LEDGER_CONTENT_SHA256
            or native.get("local_source_configuration")
            != LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE44_METHOD[
                method_id
            ]
            or native.get("imported_comparators_excluded")
            != list(
                IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE44_METHOD[
                    method_id
                ]
            )
            or len(native_tickets) != 1
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError(
                f"wave-44 native semantics changed: {method_id}"
            )
        ticket = native_tickets[0]
        if not isinstance(ticket, list):
            raise EvidenceBuildError("wave-44 native ticket changed")
        tickets[method_id].append(cast(list[int], ticket))
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS:
        sequence_sha256 = hashlib.sha256(
            json.dumps(
                tickets[method_id],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if (
            statuses[method_id]
            != {"CLOSED_REJECTED": 2101, "OK": 48}
            or reasons[method_id]
            != {NONCAUSAL_TARGET_REASON: 2101}
            or len(tickets[method_id]) != 48
            or sequence_sha256
            != EXPECTED_TICKET_SEQUENCE_SHA256[method_id]
        ):
            raise EvidenceBuildError(
                f"wave-44 execution distribution changed: {method_id}"
            )
        checkpoint_path, checkpoint_sha256, checkpoint_blob_id = (
            CHECKPOINT_BY_SOURCE_NATIVE_WAVE44_METHOD[method_id]
        )
        strategies[method_id] = {
            "candidate_k_distribution": {"49": 48},
            "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
            "checkpoint_blob_id": checkpoint_blob_id,
            "checkpoint_path": checkpoint_path,
            "checkpoint_sha256": checkpoint_sha256,
            "closed_execution_count": 2101,
            "closed_reason_code_distribution": {
                NONCAUSAL_TARGET_REASON: 2101
            },
            "combination_count_distribution": {"null": 48},
            "execution_status_counts": {
                "CLOSED_REJECTED": 2101,
                "OK": 48,
            },
            "imported_comparators_excluded": list(
                IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE44_METHOD[
                    method_id
                ]
            ),
            "legacy_method_id": method_id,
            "local_source_configuration": (
                LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE44_METHOD[
                    method_id
                ]
            ),
            "model_context_draw_count": MODEL_CONTEXT_DRAW_COUNT,
            "native_duplicate_ticket_count_distribution": {"0": 48},
            "native_ticket_count_distribution": {"1": 48},
            "native_ticket_semantics": (
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE44_METHOD[
                    method_id
                ]
            ),
            "ok_execution_count": 48,
            "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
            "source_sha256": (
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE44_METHOD[method_id]
            ),
            "ticket_sequence_sha256": sequence_sha256,
        }
    return [strategies[method_id] for method_id in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS]


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
        raise EvidenceBuildError("wave-44 report identity changed")
    return checksums


def build_evidence(
    *,
    base_catalog_path: Path,
    input_file: Path,
    parity_file: Path,
    report_file: Path,
    report_directory: Path,
) -> dict[str, object]:
    """Validate all wave-44 artifacts and return compact evidence."""

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
        "checkpoint_introduction_commit": (
            CHECKPOINT_INTRODUCTION_COMMIT
        ),
        "checkpoint_introduction_time": CHECKPOINT_INTRODUCTION_TIME,
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
        "source_native_protocol": SOURCE_NATIVE_WAVE44_PROTOCOL,
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
