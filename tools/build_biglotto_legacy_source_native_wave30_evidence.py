#!/usr/bin/env python3
"""Build compact evidence for the wave-30 causal source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave30 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE30_METHOD,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE30_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE30_METHOD,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE30_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE30_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE30_METHOD,
    SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE30_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE30_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE30_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave30 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE30_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "dca1c838cc8d9003e51ff84d66d68248e44fe48f9b7fbde1ee77ba9d093f0c3f"
)
BASE_CATALOG_FILE_SHA256 = (
    "72275a74a5459e7f5fd27c8d1185e54d988abaf257e872bb0e47c256eb24ec70"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "01cc1c8e17c8ea4af8d2592df93b826968ea1de470092131c462deefae187f5c"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "e2f4e84e27c1effd6ee19d9a6c810a08d1921ab056959c725a0deb55ce14795c"
)
EXPECTED_PARITY_SHA256 = (
    "77d5a4e74c9eb381cc049994111199ee2cb6ffebc7c3ee3af6a0e720ca01e2e4"
)
EXPECTED_REPORT_SHA256 = (
    "fb5499b38e138eb9cda76aaf872aa513340057ed49217ca1dd3fd9dd3358ca7b"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "bc3782d0c56a704ca7c24f9e0636ddaf14a649a18422d14894d61df53060b7cb"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 72,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 106,
}
EXPECTED_PROGRESS = {
    "backtested_count": 73,
    "closed_count": 38,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 105,
    "reproduced_count": 73,
    "total_strategy_count": 221,
    "uncompleted_count": 105,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "808196e39cd1692f7d34110107d840a65560cd7a87006462ff73674d4c51603f"
    ),
    "biglotto_execution_audit.csv": (
        "a53f6c73531eabc0d9121ca7882e66dbecbc3bc8adfad4d9ed776feda4c57731"
    ),
    "biglotto_full_rankings.csv": (
        "5efaf6fef809dacea303099f756ac6f825b90ce32c34148ba57c370dd99da3cb"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "bc3782d0c56a704ca7c24f9e0636ddaf14a649a18422d14894d61df53060b7cb"
    ),
    "biglotto_official_prize_distributions.csv": (
        "51a98c3e06b314fc54981c90fa60ef5f755a8cf4e67e0185e4e041c773bb99e9"
    ),
    "biglotto_strategy_universe.csv": (
        "0fd0fcf4828a83f9b7989ffd2cff895577cfba2819b70d3e0b12e8826e48ff67"
    ),
    "biglotto_success_metrics.csv": (
        "6c1fa4450a032b30612e8ba96388b5dab3990acea6cdf610cd9fbae92365bcd2"
    ),
    "biglotto_top10.csv": (
        "68298e915eb571d8589adb213a725ebd8614a21a407f0f499ee857d21cece0fe"
    ),
}
EXPECTED_STATUS_BY_METHOD = {
    method_id: {"CLOSED_INSUFFICIENT_HISTORY": 1, "OK": 2148}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE30_METHODS
}
EXPECTED_DUPLICATE_DISTRIBUTION = {
    0: 1219,
    1: 769,
    2: 134,
    3: 11,
    4: 11,
    5: 2,
    6: 2,
}


class EvidenceBuildError(ValueError):
    """Wave-30 evidence inputs violate the frozen contract."""


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
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE30_METHODS:
        row = by_method.get(method_id, {})
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE30_METHOD[method_id]
            or not isinstance(row.get("strategy_id"), str)
        ):
            raise EvidenceBuildError("wave-30 catalog identity changed")
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
    if len(executions) != 2149:
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
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE30_METHOD[method_id]
            or native.get("source_history_order")
            != SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE30_METHOD[
                method_id
            ]
            or native.get("source_history_order_detail")
            != SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE30_METHOD[
                method_id
            ]
            or native.get("candidate_k") is not None
            or native.get("candidate_pool_size") is not None
            or native.get("candidate_pool") != []
            or row.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or row.get("combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD[
                method_id
            ]
            or native.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE30_METHOD[
                    method_id
                ]
            )
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE30_METHOD[
                    method_id
                ]
            ]
            or native.get("random_protocol")
            != RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE30_METHOD[method_id]
            or native.get("randomness_used") is not True
            or native.get("numpy_version_pin") != "numpy==1.26.2"
            or native.get("numpy_scalar_exp_reproduction")
            != "SCALAR_NUMPY_EXP_REPRODUCED_WITH_IEEE754_MATH_EXP"
            or native.get("source_engine_method_count") != 7
            or native.get("source_ewma_variant_count") != 3
            or native.get("source_ewma_lambdas")
            != ["0.03", "0.10", "0.15"]
            or row.get("native_ticket_count")
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD[
                method_id
            ]
            or len(cast(list[object], row.get("native_tickets", [])))
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD[
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
            != EXPECTED_DUPLICATE_DISTRIBUTION
            for method_id in SUPPORTED_SOURCE_NATIVE_WAVE30_METHODS
        )
    ):
        raise EvidenceBuildError("execution distributions changed")
    return [
        {
            "candidate_k_distribution": {"null": 2148},
            "closed_execution_count": 1,
            "closed_reason_code_distribution": dict(
                sorted(reason_codes[method_id].items())
            ),
            "execution_status_counts": dict(
                sorted(statuses[method_id].items())
            ),
            "legacy_method_id": method_id,
            "minimum_history_draws": (
                MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE30_METHOD[method_id]
            ),
            "native_duplicate_ticket_count_distribution": (
                _string_distribution(duplicates[method_id])
            ),
            "native_ticket_count": (
                NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD[
                    method_id
                ]
            ),
            "native_ticket_semantics": (
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE30_METHOD[
                    method_id
                ]
            ),
            "ok_execution_count": 2148,
            "numpy_scalar_exp_reproduction": (
                "SCALAR_NUMPY_EXP_REPRODUCED_WITH_IEEE754_MATH_EXP"
            ),
            "numpy_version_pin": "numpy==1.26.2",
            "random_protocol": (
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE30_METHOD[method_id]
            ),
            "source_history_order": (
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE30_METHOD[
                    method_id
                ]
            ),
            "source_history_order_detail": (
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE30_METHOD[
                    method_id
                ]
            ),
            "source_method_combination_count": (
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD[
                    method_id
                ]
            ),
            "source_sha256": (
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE30_METHOD[method_id]
            ),
        }
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE30_METHODS
    ]


def _validate_parity(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("status") != "PASS"
        or document.get("case_count") != 65
        or document.get("closed_parity_case_count") != 0
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("database_sha256") != EXPECTED_DATABASE_SHA256
        or document.get("frozen_numpy_version_pin") != "numpy==1.26.2"
        or document.get("numpy_scalar_exp_instrumentation_facts")
        != {
            "removed_local_numpy_import_count": 1,
            "scalar_numpy_exp_call_site_count": 1,
        }
        or len(cast(list[object], document.get("source_artifacts", [])))
        != 1
        or len(cast(list[object], document.get("support_artifacts", [])))
        != 5
    ):
        raise EvidenceBuildError("parity evidence changed")
    return {
        "case_count": document["case_count"],
        "closed_parity_case_count": document[
            "closed_parity_case_count"
        ],
        "frozen_numpy_version_pin": document[
            "frozen_numpy_version_pin"
        ],
        "numpy_scalar_exp_instrumentation_facts": document[
            "numpy_scalar_exp_instrumentation_facts"
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


def build_wave30_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate immutable inputs and return compact wave-30 evidence."""

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
    evidence = build_wave30_evidence(
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
