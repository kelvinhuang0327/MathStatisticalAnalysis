#!/usr/bin/env python3
"""Build checked evidence for the fifteenth BIG_LOTTO source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave15 import (
    ATTENTION_REPLAY_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE15_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE15_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE15_METHOD,
    SOURCE_NATIVE_WAVE15_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave15 import (
    MATERIALIZATION_SCHEMA_VERSION,
)
from verify_biglotto_legacy_source_native_wave15_parity import (
    FROZEN_SOURCE_COMMIT,
    PARITY_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE15_EVIDENCE_V1"
)
BASE_CATALOG_SHA256 = (
    "c7371b31baae77afec61e9977b55a0d3b682b7034374cb24a8aff47c9a02eb01"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "d8fe5c0ec3753a8b7a64bb5bbae0eedf6ec299c0bd2ac8a5e3f22db81c951b3e"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "099271a1703c047ed3168a8983e03255f6986455cca0b6d61e5af0e2c504e4fc"
)
EXPECTED_REPORT_SHA256 = (
    "9a23dedaf9ac1087c404a126fe002ed59937a06beb6ec8eedcab720d0e8aeeb2"
)
EXPECTED_PARITY_SHA256 = (
    "27af91133a4bcceb84c2f71c40003418569ab8c7f53eb387de5566bae165612e"
)
EXPECTED_PRE_OVERLAY_PROGRESS = {
    "backtested_count": 40,
    "closed_count": 28,
    "duplicate_alias_count": 4,
    "owner_decision_required_count": 149,
    "reproduced_count": 40,
    "total_strategy_count": 221,
    "uncompleted_count": 149,
}


class EvidenceBuildError(ValueError):
    """Wave-15 evidence inputs violate the frozen contract."""


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


def _validate_catalog(path: Path) -> dict[str, Any]:
    catalog, _raw = _read_json(path)
    if (
        catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts")
        != {
            "BACKTESTED": 39,
            "CLOSED_UNEXECUTABLE": 28,
            "DUPLICATE_ALIAS": 4,
            "OWNER_DECISION_REQUIRED": 150,
        }
    ):
        raise EvidenceBuildError("base catalog identity changed")
    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise EvidenceBuildError("base catalog records are missing")
    for candidate in cast(list[object], records_raw):
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        if row.get("legacy_method_id") == ATTENTION_REPLAY_METHOD_ID:
            if (
                row.get("reproduction_status")
                != "OWNER_DECISION_REQUIRED"
                or row.get("source_sha256")
                != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD[
                    ATTENTION_REPLAY_METHOD_ID
                ]
            ):
                break
            return row
    raise EvidenceBuildError("attention catalog identity changed")


def _validate_input(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_INPUT_SHA256
        or document.get("dataset_sha256")
        != EXPECTED_DATABASE_SHA256
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", [])))
        != 2149
    ):
        raise EvidenceBuildError("full input identity changed")
    executions_raw = document.get("executions")
    if not isinstance(executions_raw, list):
        raise EvidenceBuildError("full input executions are missing")
    statuses: Counter[str] = Counter()
    for candidate in cast(list[object], executions_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        status = row.get("status")
        if type(status) is not str:
            raise EvidenceBuildError("execution status is invalid")
        statuses[status] += 1
        if status != "OK":
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError("native execution evidence changed")
        native = cast(dict[str, Any], native_raw)
        if (
            native.get("legacy_method_id") != ATTENTION_REPLAY_METHOD_ID
            or row.get("native_ticket_count") != 1
            or native.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE15_METHOD[
                    ATTENTION_REPLAY_METHOD_ID
                ]
            ]
            or len(cast(list[object], row["ordered_portfolio"]))
            != 20
        ):
            raise EvidenceBuildError("native execution evidence changed")
    if dict(sorted(statuses.items())) != {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    }:
        raise EvidenceBuildError("execution status evidence changed")
    return {
        "closed_status_counts": {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
        },
        "legacy_method_id": ATTENTION_REPLAY_METHOD_ID,
        "minimum_history_draws": 1,
        "native_ticket_count": 1,
        "native_ticket_semantics": (
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE15_METHOD[
                ATTENTION_REPLAY_METHOD_ID
            ]
        ),
        "ok_execution_count": 2148,
        "source_history_order": (
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE15_METHOD[
                ATTENTION_REPLAY_METHOD_ID
            ]
        ),
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD[
                ATTENTION_REPLAY_METHOD_ID
            ]
        ),
    }


def _validate_report(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_REPORT_FILE_SHA256
        or document.get("report_schema_version")
        != REPORT_SCHEMA_VERSION
        or document.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or document.get("catalog_sha256") != BASE_CATALOG_SHA256
        or document.get("input_raw_sha256")
        != EXPECTED_INPUT_SHA256
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
    support_raw = document.get("support_artifacts")
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or document.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or document.get("port_protocol")
        != SOURCE_NATIVE_WAVE15_PROTOCOL
        or document.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD
        or document.get("database_sha256")
        != EXPECTED_DATABASE_SHA256
        or document.get("case_count") != 4
        or document.get("status") != "PASS"
        or not isinstance(support_raw, list)
        or len(cast(list[object], support_raw)) != 3
    ):
        raise EvidenceBuildError("frozen-source parity changed")
    return {
        "artifact_sha256": EXPECTED_PARITY_SHA256,
        "case_count": 4,
        "execution_mode": document["execution_mode"],
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
    strategy = _validate_input(input_a, input_a_raw)
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
            "execution_count": 2149,
            "status_counts": {
                "CLOSED_INSUFFICIENT_HISTORY": 1,
                "OK": 2148,
            },
            "target_draw_count": 2149,
        },
        "full_report": report,
        "parity": parity_summary,
        "port_protocol": SOURCE_NATIVE_WAVE15_PROTOCOL,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "strategies": [strategy],
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
                "strategy_count": 1,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
