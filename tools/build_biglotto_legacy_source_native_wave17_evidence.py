#!/usr/bin/env python3
"""Build checked evidence for the seventeenth BIG_LOTTO source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave17 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE17_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE17_METHOD,
    SCIENTIFIC_SMART_RANDOM_METHOD_ID,
    SMART_MULTI_BET_METHOD_ID,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE17_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE17_METHOD,
    SOURCE_NATIVE_WAVE17_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE17_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave17 import (
    MATERIALIZATION_SCHEMA_VERSION,
)
from verify_biglotto_legacy_source_native_wave17_parity import (
    FROZEN_SOURCE_COMMIT,
    PARITY_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE17_EVIDENCE_V1"
)
BASE_CATALOG_SHA256 = (
    "4a03137a6d7c2be3b8daa238a1292cbe35f563c800b6654c6c585888a25917dd"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "9f2a80e5ab5d88c5938ed867a1bdafc94da68f0b63b8c8b8d527dd8a947bd06a"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "dfc892957aed8ac7566d74c0c078a3bd214d4254d946d0b4ee58077572fa91dd"
)
EXPECTED_REPORT_SHA256 = (
    "db7c30e2eaa8536ca4ab30e221ab4c3689c6effe070b584849c46a3b0576cb0a"
)
EXPECTED_PARITY_SHA256 = (
    "f4ced21625d1c5f3021ace69920af8ba4df88626925963e4c63a14c958e921de"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 41,
    "CLOSED_UNEXECUTABLE": 30,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 146,
}
EXPECTED_PRE_OVERLAY_PROGRESS = {
    "backtested_count": 43,
    "closed_count": 30,
    "duplicate_alias_count": 4,
    "owner_decision_required_count": 144,
    "reproduced_count": 43,
    "total_strategy_count": 221,
    "uncompleted_count": 144,
}
_NATIVE_TICKET_COUNT = {
    SCIENTIFIC_SMART_RANDOM_METHOD_ID: 7,
    SMART_MULTI_BET_METHOD_ID: 6,
}
_POOL_NAMES = (
    "hot",
    "cold",
    "mid",
    "recent_active",
    "last_draw",
    "comeback",
)


class EvidenceBuildError(ValueError):
    """Wave-17 evidence inputs violate the frozen contract."""


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
    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise EvidenceBuildError("base catalog records are missing")
    found: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], records_raw):
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if (
            type(method_id) is str
            and method_id in SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS
        ):
            found[method_id] = row
    if set(found) != set(SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS) or any(
        row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
        or row.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE17_METHOD[method_id]
        for method_id, row in found.items()
    ):
        raise EvidenceBuildError("wave-17 catalog identities changed")


def _validate_input(
    document: dict[str, Any],
    raw: bytes,
) -> list[dict[str, object]]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_INPUT_SHA256
        or document.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", []))) != 2149
    ):
        raise EvidenceBuildError("full input identity changed")
    executions_raw = document.get("executions")
    if not isinstance(executions_raw, list):
        raise EvidenceBuildError("full input executions are missing")
    if len(cast(list[object], executions_raw)) != 4298:
        raise EvidenceBuildError("full input execution count changed")

    statuses: Counter[str] = Counter()
    per_method: dict[str, Counter[str]] = {
        method_id: Counter()
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS
    }
    pool_values: dict[str, set[int]] = defaultdict(set)
    for candidate in cast(list[object], executions_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        status = row.get("status")
        if type(status) is not str:
            raise EvidenceBuildError("execution status is invalid")
        statuses[status] += 1
        if status != "OK":
            if status != "CLOSED_INSUFFICIENT_HISTORY":
                raise EvidenceBuildError("unexpected execution closure")
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError("native execution evidence changed")
        native = cast(dict[str, Any], native_raw)
        method_id = native.get("legacy_method_id")
        if (
            type(method_id) is not str
            or method_id not in SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS
        ):
            raise EvidenceBuildError("native method identity changed")
        per_method[method_id]["OK"] += 1
        candidate_counts = native.get("source_candidate_ticket_counts")
        expected_candidate_length = (
            0 if method_id == SCIENTIFIC_SMART_RANDOM_METHOD_ID else 6
        )
        if (
            row.get("candidate_k") is not None
            or native.get("candidate_k") is not None
            or row.get("combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE17_METHOD[
                method_id
            ]
            or native.get("combination_count") is not None
            or row.get("native_ticket_count")
            != _NATIVE_TICKET_COUNT[method_id]
            or native.get("native_ticket_count")
            != _NATIVE_TICKET_COUNT[method_id]
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE17_METHOD[method_id]
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE17_METHOD[
                    method_id
                ]
            ]
            or not isinstance(candidate_counts, list)
            or len(cast(list[object], candidate_counts))
            != expected_candidate_length
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError("native execution evidence changed")
        if method_id == SMART_MULTI_BET_METHOD_ID:
            for name, value in zip(
                _POOL_NAMES,
                cast(list[object], candidate_counts),
                strict=True,
            ):
                if type(value) is not int or value < 0:
                    raise EvidenceBuildError(
                        "candidate-pool evidence changed"
                    )
                pool_values[name].add(value)

    if dict(sorted(statuses.items())) != {
        "CLOSED_INSUFFICIENT_HISTORY": 2,
        "OK": 4296,
    } or any(
        counts != {"OK": 2148} for counts in per_method.values()
    ):
        raise EvidenceBuildError("execution status evidence changed")
    return [
        {
            "candidate_k": None,
            "candidate_pool_count_observed_values": (
                {
                    name: sorted(pool_values[name])
                    for name in _POOL_NAMES
                }
                if method_id == SMART_MULTI_BET_METHOD_ID
                else {}
            ),
            "closed_status_counts": {
                "CLOSED_INSUFFICIENT_HISTORY": 1,
            },
            "combination_count": (
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE17_METHOD[
                    method_id
                ]
            ),
            "legacy_method_id": method_id,
            "minimum_history_draws": 1,
            "native_ticket_count": _NATIVE_TICKET_COUNT[method_id],
            "native_ticket_semantics": (
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE17_METHOD[
                    method_id
                ]
            ),
            "ok_execution_count": 2148,
            "source_history_order": (
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE17_METHOD[
                    method_id
                ]
            ),
            "source_sha256": (
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE17_METHOD[method_id]
            ),
        }
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS
    ]


def _validate_report(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_REPORT_FILE_SHA256
        or document.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or document.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or document.get("catalog_sha256") != BASE_CATALOG_SHA256
        or document.get("input_raw_sha256") != EXPECTED_INPUT_SHA256
        or document.get("report_sha256") != EXPECTED_REPORT_SHA256
        or document.get("progress") != EXPECTED_PRE_OVERLAY_PROGRESS
        or document.get("target_draw_count") != 2149
    ):
        raise EvidenceBuildError("full report identity changed")
    return {
        "artifact_sha256": EXPECTED_REPORT_FILE_SHA256,
        "internal_report_sha256": EXPECTED_REPORT_SHA256,
        "progress": EXPECTED_PRE_OVERLAY_PROGRESS,
    }


def _validate_parity(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    source_raw = document.get("source_artifacts")
    support_raw = document.get("support_artifacts")
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or document.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or document.get("source_native_protocol")
        != SOURCE_NATIVE_WAVE17_PROTOCOL
        or document.get("database_sha256")
        != EXPECTED_DATABASE_SHA256
        or document.get("case_count") != 8
        or document.get("status") != "PASS"
        or not isinstance(source_raw, list)
        or len(cast(list[object], source_raw)) != 2
        or not isinstance(support_raw, list)
        or len(cast(list[object], support_raw)) != 2
    ):
        raise EvidenceBuildError("frozen-source parity changed")
    return {
        "artifact_sha256": EXPECTED_PARITY_SHA256,
        "case_count": 8,
        "runtime_dependency_versions": (
            document["runtime_dependency_versions"]
        ),
        "source_artifacts": source_raw,
        "status": "PASS",
        "support_artifacts": support_raw,
    }


def build_evidence(
    *,
    base_catalog_path: Path,
    input_a_path: Path,
    input_b_path: Path,
    report_a_path: Path,
    report_b_path: Path,
    parity_path: Path,
) -> dict[str, object]:
    _validate_catalog(base_catalog_path)
    input_a, input_a_raw = _read_json(input_a_path)
    _input_b, input_b_raw = _read_json(input_b_path)
    if input_a_raw != input_b_raw:
        raise EvidenceBuildError("full input double-run differs")
    strategies = _validate_input(input_a, input_a_raw)
    report_a, report_a_raw = _read_json(report_a_path)
    _report_b, report_b_raw = _read_json(report_b_path)
    if report_a_raw != report_b_raw:
        raise EvidenceBuildError("full report double-run differs")
    report = _validate_report(report_a, report_a_raw)
    parity, parity_raw = _read_json(parity_path)
    parity_summary = _validate_parity(parity, parity_raw)
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "dataset_sha256": EXPECTED_DATABASE_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "full_input": {
            "artifact_sha256": EXPECTED_INPUT_SHA256,
            "execution_count": 4298,
            "status_counts": {
                "CLOSED_INSUFFICIENT_HISTORY": 2,
                "OK": 4296,
            },
            "target_draw_count": 2149,
        },
        "full_report": report,
        "parity": parity_summary,
        "port_protocol": SOURCE_NATIVE_WAVE17_PROTOCOL,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "strategies": strategies,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--input-a", required=True, type=Path)
    parser.add_argument("--input-b", required=True, type=Path)
    parser.add_argument("--report-a", required=True, type=Path)
    parser.add_argument("--report-b", required=True, type=Path)
    parser.add_argument("--parity", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    document = build_evidence(
        base_catalog_path=args.base_catalog,
        input_a_path=args.input_a,
        input_b_path=args.input_b,
        report_a_path=args.report_a,
        report_b_path=args.report_b,
        parity_path=args.parity,
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
