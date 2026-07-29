#!/usr/bin/env python3
"""Build checked evidence for the twenty-third source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave23 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE23_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE23_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE23_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE23_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE23_METHOD,
    SOURCE_NATIVE_WAVE23_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE23_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE23_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave23 import (
    MATERIALIZATION_SCHEMA_VERSION,
)
from verify_biglotto_legacy_source_native_wave23_parity import (
    FROZEN_SOURCE_COMMIT,
    PARITY_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE23_EVIDENCE_V1"
)
BASE_CATALOG_SHA256 = (
    "a9049b4dfe6167731f256fae70e6d3fa4af09ecd48147b3a2a859d1501236838"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "fcfc8cf2a826d56867b032023d92cc9e8973365d71e2b3e2017efd4dc2e79753"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "2bf7da6168f93f60bb5af8e89046f9a8587da1419d7dcc867586f148189ae8a1"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "241d04165d98c314f73e9ea1eb095c874bae87fdd40c144dc1abbb5e1a50fd4d"
)
EXPECTED_REPORT_SHA256 = (
    "51f21c411eeaa0b796e6c1bc7e6e3e7660294afbca105fac8d1288f56923ce3a"
)
EXPECTED_PARITY_SHA256 = (
    "8064df37f44f695699e87071a4ffe2cb7a816405862f73d37fa14e038f73edd5"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 46,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 133,
}
EXPECTED_PROGRESS = {
    "backtested_count": 48,
    "closed_count": 37,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 131,
    "reproduced_count": 48,
    "total_strategy_count": 221,
    "uncompleted_count": 131,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "06e4152dadf886ed79630f193117f3f76bab606a9151a5cf4591bf6d835feb25"
    ),
    "biglotto_execution_audit.csv": (
        "00fef1fb8b2b51b057dfe2ce7cd622429ab10a5b57dfcb8b142f3c0ce1a568c1"
    ),
    "biglotto_full_rankings.csv": (
        "af0ad2261137a0624439d973f822179d8d9bf15c8a2ba7641759fbe43d205540"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "241d04165d98c314f73e9ea1eb095c874bae87fdd40c144dc1abbb5e1a50fd4d"
    ),
    "biglotto_official_prize_distributions.csv": (
        "3a4e6ba77be9f693138f715b483d48428b9cc0bf68600f45f16ccb1e34ad5062"
    ),
    "biglotto_strategy_universe.csv": (
        "7d7131a4578ae0f09802eb6821a8dc73508a8cb9e9db5a097a2f6c9c8ac0a75b"
    ),
    "biglotto_success_metrics.csv": (
        "c7e91f32feb8cb90857ea0fdf1c9c84da92aabfb590f16e68e7b8ac62d4648ee"
    ),
    "biglotto_top10.csv": (
        "2ea2f5713f022cd0a75a49e7627f509df33e2e40b8d8ba3945e9d6dd07a3a106"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-23 evidence inputs violate the frozen contract."""


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
    records = cast(list[object], catalog.get("records", []))
    by_method = {
        cast(str, row["legacy_method_id"]): row
        for candidate in records
        if isinstance(candidate, dict)
        for row in [cast(dict[str, Any], candidate)]
        if isinstance(row.get("legacy_method_id"), str)
    }
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE23_METHODS:
        row = by_method.get(method_id, {})
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE23_METHOD[method_id]
        ):
            raise EvidenceBuildError(
                "wave-23 catalog identity changed"
            )


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
    executions = cast(list[object], document.get("executions", []))
    if len(executions) != 4298:
        raise EvidenceBuildError("full input execution count changed")
    status_by_method: dict[str, Counter[str]] = defaultdict(Counter)
    duplicates_by_method: dict[str, Counter[int]] = defaultdict(Counter)
    orders_by_method: dict[str, Counter[int]] = defaultdict(Counter)
    candidates_by_method: dict[str, Counter[int]] = defaultdict(Counter)
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        status = row.get("status")
        if status != "OK":
            if status != "CLOSED_INSUFFICIENT_HISTORY":
                raise EvidenceBuildError("unexpected execution closure")
            strategy_id = cast(str, row.get("strategy_id", ""))
            method_id = next(
                (
                    item
                    for item in SUPPORTED_SOURCE_NATIVE_WAVE23_METHODS
                    if item.rsplit("/", 1)[-1].removesuffix(".py")
                    in strategy_id
                ),
                None,
            )
            if method_id is None:
                raise EvidenceBuildError(
                    "closed execution strategy changed"
                )
            status_by_method[method_id][cast(str, status)] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError("native execution evidence changed")
        native = cast(dict[str, Any], native_raw)
        method_id = native.get("legacy_method_id")
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE23_METHODS:
            raise EvidenceBuildError("native method identity changed")
        typed_method_id = cast(str, method_id)
        expected_count = (
            SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE23_METHOD[
                typed_method_id
            ]
        )
        if (
            row.get("candidate_k") is not None
            or row.get("combination_count") != expected_count
            or row.get("native_ticket_count") != expected_count
            or native.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or native.get("native_ticket_count") != expected_count
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE23_METHOD[
                typed_method_id
            ]
            or native.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE23_METHOD[
                    typed_method_id
                ]
            )
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE23_METHOD[
                    typed_method_id
                ]
            ]
            or len(cast(list[object], row.get("native_tickets", [])))
            != expected_count
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError("native execution evidence changed")
        duplicate_count = native.get("native_duplicate_ticket_count")
        markov_order = native.get("markov_order")
        source_counts = cast(
            list[object],
            native.get("source_candidate_ticket_counts", []),
        )
        if (
            type(duplicate_count) is not int
            or type(markov_order) is not int
            or len(source_counts) != expected_count
            or type(source_counts[0]) is not int
        ):
            raise EvidenceBuildError("native diagnostics changed")
        status_by_method[typed_method_id]["OK"] += 1
        duplicates_by_method[typed_method_id][duplicate_count] += 1
        orders_by_method[typed_method_id][markov_order] += 1
        candidates_by_method[typed_method_id][source_counts[0]] += 1
    rows: list[dict[str, object]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE23_METHODS:
        if status_by_method[method_id] != Counter(
            {"OK": 2148, "CLOSED_INSUFFICIENT_HISTORY": 1}
        ):
            raise EvidenceBuildError("execution coverage changed")
        rows.append(
            {
                "candidate_k": None,
                "closed_execution_count": 1,
                "combination_count": (
                    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE23_METHOD[
                        method_id
                    ]
                ),
                "legacy_method_id": method_id,
                "markov_order_distribution": dict(
                    sorted(orders_by_method[method_id].items())
                ),
                "native_duplicate_ticket_count_distribution": dict(
                    sorted(duplicates_by_method[method_id].items())
                ),
                "native_ticket_count": (
                    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE23_METHOD[
                        method_id
                    ]
                ),
                "native_ticket_semantics": (
                    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE23_METHOD[
                        method_id
                    ]
                ),
                "ok_execution_count": 2148,
                "source_history_order": (
                    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE23_METHOD[
                        method_id
                    ]
                ),
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE23_METHOD[
                        method_id
                    ]
                ),
                "statistical_candidate_count_distribution": dict(
                    sorted(candidates_by_method[method_id].items())
                ),
            }
        )
    return rows


def _validate_report(
    directory: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    checksums = {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in EXPECTED_REPORT_CHECKSUMS
    }
    if checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("report artifact checksums changed")
    report, raw = _read_json(
        directory / "biglotto_multi_ticket_backtest_report.json"
    )
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_REPORT_FILE_SHA256
        or report.get("report_sha256") != EXPECTED_REPORT_SHA256
        or report.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or report.get("catalog_sha256") != BASE_CATALOG_SHA256
        or report.get("input_raw_sha256") != EXPECTED_INPUT_SHA256
        or report.get("input_canonical_sha256")
        != EXPECTED_INPUT_CANONICAL_SHA256
        or report.get("progress") != EXPECTED_PROGRESS
        or report.get("target_draw_count") != 2149
    ):
        raise EvidenceBuildError("backtest report identity changed")
    return report, checksums


def _validate_parity(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or document.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or document.get("database_sha256")
        != EXPECTED_DATABASE_SHA256
        or document.get("port_protocol")
        != SOURCE_NATIVE_WAVE23_PROTOCOL
        or document.get("status") != "PASS"
        or document.get("case_count") != 12
    ):
        raise EvidenceBuildError("parity evidence identity changed")
    return {
        "case_count": 12,
        "parity_sha256": EXPECTED_PARITY_SHA256,
        "source_artifacts": document.get("source_artifacts"),
        "status": "PASS",
        "support_artifact": document.get("support_artifact"),
    }


def build_evidence(
    *,
    base_catalog: Path,
    input_file: Path,
    report_directory: Path,
    parity_file: Path,
) -> dict[str, object]:
    _validate_catalog(base_catalog)
    input_document, input_raw = _read_json(input_file)
    strategies = _validate_input(input_document, input_raw)
    _report, report_checksums = _validate_report(report_directory)
    parity_document, parity_raw = _read_json(parity_file)
    parity = _validate_parity(parity_document, parity_raw)
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "database_sha256": EXPECTED_DATABASE_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "input_canonical_sha256": EXPECTED_INPUT_CANONICAL_SHA256,
        "input_sha256": EXPECTED_INPUT_SHA256,
        "materialization_schema_version": (
            MATERIALIZATION_SCHEMA_VERSION
        ),
        "parity": parity,
        "progress": dict(EXPECTED_PROGRESS),
        "report_artifact_checksums": report_checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "strategies": strategies,
        "target_draw_count": 2149,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--report-directory", required=True, type=Path)
    parser.add_argument("--parity-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    evidence = build_evidence(
        base_catalog=args.base_catalog,
        input_file=args.input_file,
        report_directory=args.report_directory,
        parity_file=args.parity_file,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
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
