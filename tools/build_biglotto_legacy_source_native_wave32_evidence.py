#!/usr/bin/env python3
"""Build compact evidence for the wave-32 causal source-native batch."""

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
)
from lottolab.application.legacy_source_native_portfolios_wave32 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE32_METHOD,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE32_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE32_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE32_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE32_METHOD,
    SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE32_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD,
    VARIANT_CONFIGURATIONS,
    VARIANT_HISTORY_METHOD_ID,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave32 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE32_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "e078f1b01daf9d3a24ed1770f0f7b27d41c4e4bcb713cd375c781f02876f09b9"
)
BASE_CATALOG_FILE_SHA256 = (
    "c63b3d4db5a7d8b2d07801bf093505654a855b2f35f19191ab4e40e8f3377b31"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "59ccb1b1b7ea4296598e9bfdac676bcf5d0d3497f94e7c69a3433d7290eb212c"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "91a7fbd0c379e3e25f7e741c44d722404cd364652012a69055a59b9662c52598"
)
EXPECTED_PARITY_SHA256 = (
    "5a777d036d292676a273ae5acfbc999124859ca689ee051a4c0e8391ef793c81"
)
EXPECTED_REPORT_SHA256 = (
    "ed6c4cbf432f900a1d73ec15261cfe4b3bdf81c4fe49eaf124ffea3d823ecf13"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "46ee1124d59879857b8d42877ec379e89b9f596c87a9aeb19716a2717231209b"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 75,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 103,
}
EXPECTED_PROGRESS = {
    "backtested_count": 76,
    "closed_count": 38,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 102,
    "reproduced_count": 76,
    "total_strategy_count": 221,
    "uncompleted_count": 102,
}
EXPECTED_DUPLICATE_DISTRIBUTION = {
    "0": 1799,
    "1": 224,
    "2": 24,
    "3": 34,
    "4": 15,
    "5": 2,
    "6": 31,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "67a963d633e3710cee19f0ca78b88467e7baf0045af7600a8062e3a95331b19e"
    ),
    "biglotto_execution_audit.csv": (
        "a5b3f5100e12d523ebe34bef533293316bd8ca5db7449dcde9da582d5964d7fe"
    ),
    "biglotto_full_rankings.csv": (
        "3602974ad09db26f08c3e89cfa99d440ac67e8a22b7de233ae8f2814eb804622"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "46ee1124d59879857b8d42877ec379e89b9f596c87a9aeb19716a2717231209b"
    ),
    "biglotto_official_prize_distributions.csv": (
        "3df2551f3ea2dee11b66d70654d5aa427e1cdceb0bc11871fb46901f1dc2d255"
    ),
    "biglotto_strategy_universe.csv": (
        "520c750c34ab7fe090449db0838dd23e32e5b665ea26dafb7898addc52af243f"
    ),
    "biglotto_success_metrics.csv": (
        "128e3d6d6fbb37a25f9ac138f4b9c942d73bef2427da3d218f3245d70af0b2e9"
    ),
    "biglotto_top10.csv": (
        "87afe4ede9ce80adb595d59db40bfdd5451121c3bbbf1128fd32074d91e89caa"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-32 evidence inputs violate the frozen contract."""


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


def _validate_catalog(path: Path) -> str:
    catalog, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
    ):
        raise EvidenceBuildError("base catalog identity changed")
    records = cast(list[object], catalog.get("records", []))
    matches: list[dict[str, Any]] = []
    for candidate in records:
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        if row.get("legacy_method_id") == VARIANT_HISTORY_METHOD_ID:
            matches.append(row)
    if len(matches) != 1:
        raise EvidenceBuildError("wave-32 catalog row changed")
    row = matches[0]
    if (
        row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
        or row.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD[
            VARIANT_HISTORY_METHOD_ID
        ]
        or not isinstance(row.get("strategy_id"), str)
    ):
        raise EvidenceBuildError("wave-32 catalog identity changed")
    return cast(str, row["strategy_id"])


def _validate_input(
    document: dict[str, Any],
    raw: bytes,
    *,
    strategy_id: str,
) -> dict[str, object]:
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
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    duplicates: Counter[int] = Counter()
    ok_count = 0
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        if row.get("strategy_id") != strategy_id:
            raise EvidenceBuildError("execution strategy changed")
        status = cast(str, row.get("status"))
        statuses[status] += 1
        if status != "OK":
            reason = row.get("reason_code")
            if not isinstance(reason, str):
                raise EvidenceBuildError("closed reason changed")
            reasons[reason] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError("native execution evidence changed")
        native = cast(dict[str, Any], native_raw)
        statistical_counts_raw = native.get(
            "statistical_candidate_counts"
        )
        if not isinstance(statistical_counts_raw, list):
            raise EvidenceBuildError(
                "statistical candidate metadata changed"
            )
        statistical_counts = cast(list[object], statistical_counts_raw)
        expected_history_counts = [
            min(cast(int, native["history_draw_count"]), window)
            for _method_name, window in VARIANT_CONFIGURATIONS
        ]
        if (
            native.get("legacy_method_id") != VARIANT_HISTORY_METHOD_ID
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD[
                VARIANT_HISTORY_METHOD_ID
            ]
            or native.get("source_history_order")
            != SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE32_METHOD[
                VARIANT_HISTORY_METHOD_ID
            ]
            or native.get("source_history_order_detail")
            != SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE32_METHOD[
                VARIANT_HISTORY_METHOD_ID
            ]
            or native.get("candidate_k") is not None
            or row.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or row.get("combination_count") != 11
            or native.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE32_METHOD[
                    VARIANT_HISTORY_METHOD_ID
                ]
            )
            or native.get("variant_history_draw_counts")
            != expected_history_counts
            or statistical_counts[3:6] != [20, 20, 20]
            or native.get("statistical_fallback_positions") != []
            or native.get("native_ticket_count") != 11
            or row.get("native_ticket_count") != 11
            or len(cast(list[object], row.get("native_tickets", [])))
            != 11
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE32_METHOD[
                    VARIANT_HISTORY_METHOD_ID
                ]
            ]
        ):
            raise EvidenceBuildError("native execution semantics changed")
        duplicate_count = native.get("native_duplicate_ticket_count")
        if type(duplicate_count) is not int:
            raise EvidenceBuildError("native duplicate count changed")
        duplicates[duplicate_count] += 1
        ok_count += 1
    duplicate_distribution = {
        str(key): value for key, value in sorted(duplicates.items())
    }
    if (
        statuses
        != {
            "CLOSED_INSUFFICIENT_HISTORY": 20,
            "OK": 2129,
        }
        or reasons
        != {
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM": 20
        }
        or duplicate_distribution != EXPECTED_DUPLICATE_DISTRIBUTION
    ):
        raise EvidenceBuildError("wave-32 execution distribution changed")
    return {
        "candidate_k_distribution": {"null": ok_count},
        "closed_execution_count": 20,
        "closed_reason_code_distribution": dict(sorted(reasons.items())),
        "execution_status_counts": dict(sorted(statuses.items())),
        "legacy_method_id": VARIANT_HISTORY_METHOD_ID,
        "minimum_history_draws": (
            MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE32_METHOD[
                VARIANT_HISTORY_METHOD_ID
            ]
        ),
        "native_duplicate_ticket_count_distribution": (
            duplicate_distribution
        ),
        "native_ticket_count": (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD[
                VARIANT_HISTORY_METHOD_ID
            ]
        ),
        "native_ticket_semantics": (
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE32_METHOD[
                VARIANT_HISTORY_METHOD_ID
            ]
        ),
        "ok_execution_count": ok_count,
        "random_protocol": (
            "PYTHON_RANDOM_MODULE_SEEDED_WITH_VARIANT_HISTORY_LENGTH_"
            "FOR_STATISTICAL_POSITIONS_4_5_6"
        ),
        "source_history_order": (
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE32_METHOD[
                VARIANT_HISTORY_METHOD_ID
            ]
        ),
        "source_history_order_detail": (
            SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE32_METHOD[
                VARIANT_HISTORY_METHOD_ID
            ]
        ),
        "source_method_combination_count": (
            SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD[
                VARIANT_HISTORY_METHOD_ID
            ]
        ),
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD[
                VARIANT_HISTORY_METHOD_ID
            ]
        ),
        "statistical_fallback_execution_count": 0,
    }


def _validate_parity(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("status") != "PASS"
        or document.get("case_count") != 480
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or not isinstance(
            document.get("frozen_source_behavior_facts"), dict
        )
        or len(cast(list[object], document.get("source_artifacts", [])))
        != 1
        or len(cast(list[object], document.get("support_artifacts", [])))
        != 4
    ):
        raise EvidenceBuildError("parity evidence changed")
    return {
        "case_count": document["case_count"],
        "frozen_source_behavior_facts": document[
            "frozen_source_behavior_facts"
        ],
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


def build_wave32_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate immutable inputs and return compact wave-32 evidence."""

    strategy_id = _validate_catalog(catalog_path)
    input_document, input_raw = _read_json(input_path)
    strategy = _validate_input(
        input_document,
        input_raw,
        strategy_id=strategy_id,
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
        "strategies": [strategy],
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
    evidence = build_wave32_evidence(
        catalog_path=args.catalog,
        input_path=args.input,
        parity_path=args.parity,
        report_path=args.report,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    if args.output.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output": str(args.output),
                "strategy_count": 1,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
