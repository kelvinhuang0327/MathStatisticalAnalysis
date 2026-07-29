#!/usr/bin/env python3
"""Build checked evidence for the mixed fourteenth BIG_LOTTO batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.biglotto_multi_ticket_backtest import (
    BACKTEST_POLICY_VERSION,
    REPORT_SCHEMA_VERSION,
)
from lottolab.application.legacy_source_native_portfolios_wave14 import (
    CANDIDATE_K_BY_SOURCE_NATIVE_WAVE14_METHOD,
    GRAPH_PREDICTOR_METHOD_ID,
    HIGH_PRIZE_TREND_METHOD_ID,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE14_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE14_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE14_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE14_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE14_METHOD,
    SOURCE_NATIVE_WAVE14_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave14 import (
    MATERIALIZATION_SCHEMA_VERSION,
)
from verify_biglotto_legacy_source_native_wave14_parity import (
    FROZEN_SOURCE_COMMIT,
    PARITY_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE14_EVIDENCE_V1"
)
BASE_CATALOG_SHA256 = (
    "9dc3608286ed37fbf98798958c2c392f80a9508784c69d46d7bb0f61a62fa4ad"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "ae51abaac3277dc952f52b55bd5312322ce37950f950d07b18a89645c137e176"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "0feef92cae652dcd2a4be887ecd9f364e6e3db199bde56cd78450e8c29ffa959"
)
EXPECTED_REPORT_SHA256 = (
    "354c14c5c22dab34edb6d4d20acbbde7319cf5eb1aa9f79d7c222f42e5c18b0a"
)
EXPECTED_PARITY_SHA256 = (
    "834ecc1341387943eb6ce126488eca359ca3b9f1ad0e4a4e4db205c17889eaa8"
)
SPECIAL_METHOD_ID = "tools/biglotto_special_v4.py"
SPECIAL_SOURCE_SHA256 = (
    "00256ce82d7cd515550e71274f4cf6d3a546c2660d2640650099533db202c7a7"
)
SPECIAL_REASON_CODE = (
    "SPECIAL_NUMBER_RANKING_WITHOUT_MAIN_NUMBER_TICKET_CONSTRUCTION"
)
EXPECTED_PRE_OVERLAY_PROGRESS = {
    "backtested_count": 39,
    "closed_count": 27,
    "duplicate_alias_count": 4,
    "owner_decision_required_count": 151,
    "reproduced_count": 39,
    "total_strategy_count": 221,
    "uncompleted_count": 151,
}


class EvidenceBuildError(ValueError):
    """Wave-14 evidence inputs violate the frozen contract."""


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


def _git(frozen_root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(frozen_root), *arguments),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise EvidenceBuildError("frozen Git query failed")
    return completed.stdout


def _validate_catalog(
    catalog_path: Path,
) -> dict[str, dict[str, Any]]:
    catalog, _raw = _read_json(catalog_path)
    if (
        catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts")
        != {
            "BACKTESTED": 37,
            "CLOSED_UNEXECUTABLE": 27,
            "DUPLICATE_ALIAS": 4,
            "OWNER_DECISION_REQUIRED": 153,
        }
    ):
        raise EvidenceBuildError("base catalog identity changed")
    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise EvidenceBuildError("base catalog records are missing")
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], records_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("catalog record is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if isinstance(method_id, str):
            record_by_method[method_id] = row
    expected_methods = {
        GRAPH_PREDICTOR_METHOD_ID,
        HIGH_PRIZE_TREND_METHOD_ID,
        SPECIAL_METHOD_ID,
    }
    for method_id in expected_methods:
        row = record_by_method.get(method_id)
        expected_sha = (
            SPECIAL_SOURCE_SHA256
            if method_id == SPECIAL_METHOD_ID
            else SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD[
                method_id
            ]
        )
        if (
            row is None
            or row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256") != expected_sha
        ):
            raise EvidenceBuildError(
                f"catalog method identity changed: {method_id}"
            )
    return record_by_method


def _validate_input(
    document: dict[str, Any],
    raw: bytes,
) -> list[dict[str, object]]:
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
    rows_by_method: dict[str, list[dict[str, Any]]] = {
        GRAPH_PREDICTOR_METHOD_ID: [],
        HIGH_PRIZE_TREND_METHOD_ID: [],
    }
    for candidate in cast(list[object], executions_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        native = row.get("native_generation")
        method_id = (
            cast(dict[str, Any], native).get("legacy_method_id")
            if isinstance(native, dict)
            else None
        )
        if method_id is None:
            strategy_id = row.get("strategy_id")
            if strategy_id == (
                "legacy_biglotto__graph_predictor__cd70713a5709"
            ):
                method_id = GRAPH_PREDICTOR_METHOD_ID
            elif strategy_id == (
                "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e"
            ):
                method_id = HIGH_PRIZE_TREND_METHOD_ID
        if method_id not in rows_by_method:
            raise EvidenceBuildError("unexpected strategy in full input")
        rows_by_method[cast(str, method_id)].append(row)

    expected_statuses = {
        GRAPH_PREDICTOR_METHOD_ID: {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
            "OK": 2148,
        },
        HIGH_PRIZE_TREND_METHOD_ID: {
            "CLOSED_INSUFFICIENT_HISTORY": 100,
            "OK": 2049,
        },
    }
    summaries: list[dict[str, object]] = []
    for method_id, rows in rows_by_method.items():
        statuses = Counter(cast(str, row["status"]) for row in rows)
        if dict(sorted(statuses.items())) != expected_statuses[method_id]:
            raise EvidenceBuildError("execution status evidence changed")
        successful = [row for row in rows if row["status"] == "OK"]
        expected_native_count = (
            1 if method_id == GRAPH_PREDICTOR_METHOD_ID else 7
        )
        duplicate_values: set[int] = set()
        for row in successful:
            native = cast(dict[str, Any], row["native_generation"])
            if (
                row.get("native_ticket_count")
                != expected_native_count
                or native.get("candidate_k") is not None
                or native.get("combination_count") is not None
                or len(cast(list[object], row["ordered_portfolio"]))
                != 20
            ):
                raise EvidenceBuildError("native ticket evidence changed")
            duplicate_values.add(
                cast(int, native["native_duplicate_ticket_count"])
            )
        expected_duplicates = (
            {0}
            if method_id == GRAPH_PREDICTOR_METHOD_ID
            else {0, 1, 2, 3, 4, 5}
        )
        if duplicate_values != expected_duplicates:
            raise EvidenceBuildError("duplicate evidence changed")
        summaries.append(
            {
                "candidate_k": (
                    CANDIDATE_K_BY_SOURCE_NATIVE_WAVE14_METHOD[
                        method_id
                    ]
                ),
                "closed_status_counts": {
                    "CLOSED_INSUFFICIENT_HISTORY": (
                        MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE14_METHOD[
                            method_id
                        ]
                    )
                },
                "combination_count": (
                    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE14_METHOD[
                        method_id
                    ]
                ),
                "combination_members": list(
                    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE14_METHOD[
                        method_id
                    ]
                ),
                "legacy_method_id": method_id,
                "minimum_history_draws": (
                    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE14_METHOD[
                        method_id
                    ]
                ),
                "native_duplicate_ticket_count_values": sorted(
                    duplicate_values
                ),
                "native_ticket_count": expected_native_count,
                "native_ticket_semantics": (
                    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE14_METHOD[
                        method_id
                    ]
                ),
                "ok_execution_count": len(successful),
                "source_history_order": (
                    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE14_METHOD[
                        method_id
                    ]
                ),
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD[
                        method_id
                    ]
                ),
            }
        )
    return summaries


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
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or document.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or document.get("port_protocol")
        != SOURCE_NATIVE_WAVE14_PROTOCOL
        or document.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD
        or document.get("database_sha256")
        != EXPECTED_DATABASE_SHA256
        or document.get("case_count") != 6
        or document.get("status") != "PASS"
    ):
        raise EvidenceBuildError("frozen-source parity changed")
    return {
        "artifact_sha256": EXPECTED_PARITY_SHA256,
        "case_count": 6,
        "execution_mode": document["execution_mode"],
        "status": "PASS",
    }


def _special_disposition(
    *,
    frozen_root: Path,
    record: dict[str, Any],
) -> dict[str, object]:
    raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{SPECIAL_METHOD_ID}",
    )
    if hashlib.sha256(raw).hexdigest() != SPECIAL_SOURCE_SHA256:
        raise EvidenceBuildError("special source SHA changed")
    text = raw.decode("utf-8")
    required = (
        "special_sequence = [d['special'] for d in h_slice]",
        "return sorted_indices[:n].tolist()",
        "pred_top_4 = BigLottoSpecialPredictorV4(h_prev).predict_top_n(n=4)",
        "target = history[idx]['special']",
    )
    if any(fragment not in text for fragment in required):
        raise EvidenceBuildError("special source semantics changed")
    blob_id = (
        _git(
            frozen_root,
            "rev-parse",
            f"{FROZEN_SOURCE_COMMIT}:{SPECIAL_METHOD_ID}",
        )
        .decode("ascii")
        .strip()
    )
    if (
        record.get("source_blob_id") != blob_id
        or record.get("source_byte_size") != len(raw)
    ):
        raise EvidenceBuildError("special source blob identity changed")
    return {
        "decisive_source_facts": [
            "The source models only the seventh special-number position.",
            "Its native output is a top-four ranking of individual special "
            "numbers, not one or more six-main-number tickets.",
            "The backtest checks whether the known special number appears "
            "in that top-four list and never constructs a main portfolio.",
        ],
        "legacy_method_id": SPECIAL_METHOD_ID,
        "reason_code": SPECIAL_REASON_CODE,
        "reproduction_status": "CLOSED_UNEXECUTABLE",
        "source_blob_id": blob_id,
        "source_byte_size": len(raw),
        "source_sha256": SPECIAL_SOURCE_SHA256,
        "status_reason": (
            "The frozen method ranks candidates for the special-number "
            "position only. Converting four single-number candidates into "
            "six-main-number tickets would invent absent selection logic."
        ),
    }


def build_evidence(
    *,
    frozen_root: Path,
    base_catalog_path: Path,
    input_a_path: Path,
    input_b_path: Path,
    report_a_path: Path,
    report_b_path: Path,
    parity_path: Path,
) -> dict[str, object]:
    record_by_method = _validate_catalog(base_catalog_path)
    input_a, input_a_raw = _read_json(input_a_path)
    _input_b, input_b_raw = _read_json(input_b_path)
    if input_a_raw != input_b_raw:
        raise EvidenceBuildError("full input double-run differs")
    strategy_rows = _validate_input(input_a, input_a_raw)
    report_a, report_a_raw = _read_json(report_a_path)
    _report_b, report_b_raw = _read_json(report_b_path)
    if report_a_raw != report_b_raw:
        raise EvidenceBuildError("full report double-run differs")
    report_summary = _validate_report(report_a, report_a_raw)
    parity, parity_raw = _read_json(parity_path)
    parity_summary = _validate_parity(parity, parity_raw)
    special = _special_disposition(
        frozen_root=frozen_root,
        record=record_by_method[SPECIAL_METHOD_ID],
    )
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
                "CLOSED_INSUFFICIENT_HISTORY": 101,
                "OK": 4197,
            },
            "target_draw_count": 2149,
        },
        "full_report": report_summary,
        "parity": parity_summary,
        "port_protocol": SOURCE_NATIVE_WAVE14_PROTOCOL,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "static_dispositions": [special],
        "strategies": strategy_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
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
        frozen_root=args.frozen_root,
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
                "static_disposition_count": 1,
                "strategy_count": 2,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
