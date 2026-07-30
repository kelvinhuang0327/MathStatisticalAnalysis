#!/usr/bin/env python3
"""Build compact evidence for the wave-31 causal source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave31 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE31_METHOD,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE31_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE31_METHOD,
    RADICAL_BACKTEST_METHOD_ID,
    RADICAL_PREDICT_METHOD_ID,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE31_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE31_METHOD,
    SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE31_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave31 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE31_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "1b1b66eb3821d48ab0df9e94460fae3dfd69da104fd3532b3ff2bbebd1c56b7e"
)
BASE_CATALOG_FILE_SHA256 = (
    "f9a0b7f07b949d1156deaa9b5a52ed44124df8e4f583901241bd7f6d097d3014"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "eb9636d04e229aea0063886d76160710f73a17c64a86027f318e07e4f777290c"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "3956dd4cb618ac415d0ffe40b1b1512146249b735ceba15bb6ec81d93c354b35"
)
EXPECTED_PARITY_SHA256 = (
    "c93e878890ff14b95a03e01625d782531fd97f9962481b80f0f9f3953ac75917"
)
EXPECTED_REPORT_SHA256 = (
    "2aef79b614b1c5205fe3d6de3958c1463647de0d5d27e2f72cc688d08431a8ce"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "7b6d83ced05460769cc3db9f6094fbf2b57a05ed3569de879bd86499ec4762f0"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 73,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 105,
}
EXPECTED_PROGRESS = {
    "backtested_count": 75,
    "closed_count": 38,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 103,
    "reproduced_count": 75,
    "total_strategy_count": 221,
    "uncompleted_count": 103,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "4ceba25b57eeb7913c8ee95f0d4a5df690f8e12dc1af43ce9a969a9c2b63895f"
    ),
    "biglotto_execution_audit.csv": (
        "71e6e0aba896faf16f67202fbf7baf955822f830bf65fdcfcd90cffe46b1c1fa"
    ),
    "biglotto_full_rankings.csv": (
        "1aa66fd5eb2bd6fabf28f8eb6bed08616efc4fa90e40aeaf45226da3a5fd49d7"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "7b6d83ced05460769cc3db9f6094fbf2b57a05ed3569de879bd86499ec4762f0"
    ),
    "biglotto_official_prize_distributions.csv": (
        "5a409adf454f71afd1e75f104fa368792567670318104fa9a9cb32854ae32fd6"
    ),
    "biglotto_strategy_universe.csv": (
        "f83d73450ddf7e20d2edafe2af647b10f512809cc68809bd9d3d000b35de6014"
    ),
    "biglotto_success_metrics.csv": (
        "3c6073fc7bd72495cf3e21972314193434ccd1c676508cc120005a5d66f3c0ff"
    ),
    "biglotto_top10.csv": (
        "3a53e532af5170b76a206653f7940c02ce1c51cb448eb2bface732923e656786"
    ),
}
EXPECTED_STATUS_BY_METHOD = {
    RADICAL_PREDICT_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "CLOSED_INVALID_OUTPUT": 32,
        "OK": 2116,
    },
    RADICAL_BACKTEST_METHOD_ID: {
        "CLOSED_INSUFFICIENT_HISTORY": 50,
        "CLOSED_INVALID_OUTPUT": 129,
        "OK": 1970,
    },
}
EXPECTED_DUPLICATE_DISTRIBUTION_BY_METHOD = {
    RADICAL_PREDICT_METHOD_ID: {0: 2116},
    RADICAL_BACKTEST_METHOD_ID: {0: 1961, 1: 9},
}


class EvidenceBuildError(ValueError):
    """Wave-31 evidence inputs violate the frozen contract."""


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
    strategy_to_method: dict[str, str] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS:
        row = by_method.get(method_id, {})
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD[method_id]
            or not isinstance(row.get("strategy_id"), str)
        ):
            raise EvidenceBuildError("wave-31 catalog identity changed")
        strategy_to_method[cast(str, row["strategy_id"])] = method_id
    return strategy_to_method


def _string_distribution(counter: Counter[int]) -> dict[str, int]:
    return {
        str(key): count for key, count in sorted(counter.items())
    }


def _validate_input(
    document: dict[str, Any],
    raw: bytes,
    *,
    strategy_to_method: dict[str, str],
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
    if len(executions) != 4298:
        raise EvidenceBuildError("full input execution count changed")
    statuses: dict[str, Counter[str]] = defaultdict(Counter)
    duplicates: dict[str, Counter[int]] = defaultdict(Counter)
    reason_codes: dict[str, Counter[str]] = defaultdict(Counter)
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = strategy_to_method.get(cast(str, row.get("strategy_id")))
        if method_id is None:
            raise EvidenceBuildError("execution strategy changed")
        status = cast(str, row.get("status"))
        statuses[method_id][status] += 1
        if status != "OK":
            reason_code = row.get("reason_code")
            if not isinstance(reason_code, str):
                raise EvidenceBuildError("closed reason changed")
            reason_codes[method_id][reason_code] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError("native execution evidence changed")
        native = cast(dict[str, Any], native_raw)
        duplicate_count = native.get("native_duplicate_ticket_count")
        if (
            native.get("legacy_method_id") != method_id
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD[method_id]
            or native.get("source_history_order")
            != SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE31_METHOD[
                method_id
            ]
            or native.get("source_history_order_detail")
            != SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE31_METHOD[
                method_id
            ]
            or native.get("candidate_k") is not None
            or not isinstance(native.get("candidate_pools"), list)
            or row.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or row.get("combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD[
                method_id
            ]
            or native.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE31_METHOD[
                    method_id
                ]
            )
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE31_METHOD[
                    method_id
                ]
            ]
            or native.get("random_protocol") != "NONE_DETERMINISTIC"
            or native.get("randomness_used") is not False
            or row.get("native_ticket_count")
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD[
                method_id
            ]
            or len(cast(list[object], row.get("native_tickets", [])))
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD[
                method_id
            ]
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
            or type(duplicate_count) is not int
        ):
            raise EvidenceBuildError("native execution evidence changed")
        duplicates[method_id][duplicate_count] += 1
    if (
        {method: dict(value) for method, value in statuses.items()}
        != EXPECTED_STATUS_BY_METHOD
        or any(
            dict(duplicates[method_id])
            != EXPECTED_DUPLICATE_DISTRIBUTION_BY_METHOD[method_id]
            for method_id in SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS
        )
    ):
        raise EvidenceBuildError("execution distributions changed")
    return [
        {
            "candidate_k_distribution": {
                "null": EXPECTED_STATUS_BY_METHOD[method_id]["OK"]
            },
            "closed_execution_count": (
                2149 - EXPECTED_STATUS_BY_METHOD[method_id]["OK"]
            ),
            "closed_reason_code_distribution": dict(
                sorted(reason_codes[method_id].items())
            ),
            "execution_status_counts": dict(
                sorted(statuses[method_id].items())
            ),
            "legacy_method_id": method_id,
            "minimum_history_draws": (
                MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE31_METHOD[method_id]
            ),
            "native_duplicate_ticket_count_distribution": (
                _string_distribution(duplicates[method_id])
            ),
            "native_ticket_count": (
                NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD[
                    method_id
                ]
            ),
            "native_ticket_semantics": (
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE31_METHOD[
                    method_id
                ]
            ),
            "ok_execution_count": EXPECTED_STATUS_BY_METHOD[method_id]["OK"],
            "random_protocol": "NONE_DETERMINISTIC",
            "source_history_order": (
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE31_METHOD[
                    method_id
                ]
            ),
            "source_history_order_detail": (
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE31_METHOD[
                    method_id
                ]
            ),
            "source_method_combination_count": (
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD[
                    method_id
                ]
            ),
            "source_sha256": (
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD[method_id]
            ),
        }
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS
    ]


def _validate_parity(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("status") != "PASS"
        or document.get("case_count") != 130
        or document.get("closed_parity_case_count") != 61
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("database_sha256") != EXPECTED_DATABASE_SHA256
        or not isinstance(
            document.get("frozen_source_behavior_facts"), dict
        )
        or len(cast(list[object], document.get("source_artifacts", [])))
        != 2
        or len(cast(list[object], document.get("support_artifacts", [])))
        != 4
    ):
        raise EvidenceBuildError("parity evidence changed")
    return {
        "case_count": document["case_count"],
        "closed_parity_case_count": document[
            "closed_parity_case_count"
        ],
        "frozen_source_behavior_facts": document[
            "frozen_source_behavior_facts"
        ],
        "parity_instrumentation": document["parity_instrumentation"],
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


def build_wave31_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate immutable inputs and return compact wave-31 evidence."""

    strategy_to_method = _validate_catalog(catalog_path)
    input_document, input_raw = _read_json(input_path)
    strategies = _validate_input(
        input_document,
        input_raw,
        strategy_to_method=strategy_to_method,
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
        "strategies": strategies,
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
    evidence = build_wave31_evidence(
        catalog_path=args.catalog,
        input_path=args.input,
        parity_path=args.parity,
        report_path=args.report,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output": str(args.output),
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
