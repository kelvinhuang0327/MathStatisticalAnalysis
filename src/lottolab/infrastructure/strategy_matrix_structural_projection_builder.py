"""Offline materializer for the packaged structural Matrix projection.

Reads only the three pinned canonical research JSON inputs (explicit paths;
no discovery), verifies their SHA-256 identity, projects the exact 210-cell
V1 grid, and returns the canonical packaged artifact bytes. Build/development
tooling only: never invoked by request-time application code, and never
invokes the research runner, optimizer, evaluator, historical replay,
ranking, or a database.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from lottolab.application.strategy_matrix_structural import (
    PINNED_AUTHORITY,
    PINNED_CLAIM_BOUNDARY,
    PINNED_LEDGER,
    PINNED_MATRIX,
    PINNED_METRIC,
    PINNED_METRIC_SURFACE,
    SCHEMA_ID,
    SCHEMA_VERSION,
    SCOPE,
    STRUCTURAL_CASE_ID_BY_LOTTERY,
    STRUCTURAL_METHOD_IDS,
    STRUCTURAL_TICKET_COUNTS,
    StructuralCaseId,
    StructuralLottery,
    StructuralMethodId,
    StructuralTicketCount,
)
from lottolab.infrastructure.strategy_matrix_structural_reader import parse_structural_projection

_EXPECTED_MAX_OBJECTIVE = "EXPECTED_MAX_MAIN_MATCHES_V1"


class StrategyMatrixStructuralBuildError(RuntimeError):
    """The offline structural Matrix materializer could not build a valid projection."""


def build_strategy_matrix_structural_projection_bytes(
    *,
    metric_surface_path: Path,
    matrix_path: Path,
    ledger_path: Path,
) -> bytes:
    metric_surface = _json_object(
        _read_and_verify(metric_surface_path, PINNED_METRIC_SURFACE.file_sha256, "metric surface"),
        "metric surface",
    )
    matrix = _json_object(
        _read_and_verify(matrix_path, PINNED_MATRIX.file_sha256, "matrix"),
        "matrix",
    )
    ledger = _json_object(
        _read_and_verify(ledger_path, PINNED_LEDGER.file_sha256, "ledger"),
        "ledger",
    )

    method_objectives = _method_objectives_from_ledger(ledger)
    evaluated_by_id, unavailable_by_id = _index_metric_surface(metric_surface)
    matrix_rows_by_id = _index_matrix_rows(matrix)

    cells: list[dict[str, object]] = []
    for lottery in StructuralLottery:
        case_id = STRUCTURAL_CASE_ID_BY_LOTTERY[lottery]
        for method_id in STRUCTURAL_METHOD_IDS:
            for ticket_count in STRUCTURAL_TICKET_COUNTS:
                row_id = f"{case_id.value}|{method_id.value}|default|k{int(ticket_count)}|m3"
                cells.append(
                    _build_cell(
                        row_id=row_id,
                        case_id=case_id,
                        lottery=lottery,
                        method_id=method_id,
                        ticket_count=ticket_count,
                        method_objective=method_objectives[method_id],
                        evaluated_by_id=evaluated_by_id,
                        unavailable_by_id=unavailable_by_id,
                        matrix_rows_by_id=matrix_rows_by_id,
                    )
                )

    document: dict[str, object] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "authority": {
            "kind": PINNED_AUTHORITY.kind,
            "source_head": PINNED_AUTHORITY.source_head,
            "source_tree": PINNED_AUTHORITY.source_tree,
            "sources": {
                "metric_surface": {
                    "repository_path": PINNED_METRIC_SURFACE.repository_path,
                    "file_sha256": PINNED_METRIC_SURFACE.file_sha256,
                },
                "matrix": {
                    "repository_path": PINNED_MATRIX.repository_path,
                    "file_sha256": PINNED_MATRIX.file_sha256,
                },
                "ledger": {
                    "repository_path": PINNED_LEDGER.repository_path,
                    "file_sha256": PINNED_LEDGER.file_sha256,
                },
            },
        },
        "scope": SCOPE,
        "supported_ticket_counts": [int(count) for count in STRUCTURAL_TICKET_COUNTS],
        "metric": {
            "metric_id": PINNED_METRIC.metric_id,
            "definition": PINNED_METRIC.definition,
            "unit": PINNED_METRIC.unit,
            "draw_distribution": PINNED_METRIC.draw_distribution,
            "exactness": PINNED_METRIC.exactness,
        },
        "claim_boundary": {
            "historical_outcomes_used": PINNED_CLAIM_BOUNDARY.historical_outcomes_used,
            "historical_success_rate_claimed": (
                PINNED_CLAIM_BOUNDARY.historical_success_rate_claimed
            ),
            "ranking_score_claimed": PINNED_CLAIM_BOUNDARY.ranking_score_claimed,
            "global_optimum_claimed": PINNED_CLAIM_BOUNDARY.global_optimum_claimed,
            "cross_lottery_normalization": PINNED_CLAIM_BOUNDARY.cross_lottery_normalization,
        },
        "cells": cells,
    }
    canonical = _canonical_json(document)
    document["projection_sha256"] = hashlib.sha256(canonical).hexdigest()
    payload = _canonical_json(document) + b"\n"

    try:
        parse_structural_projection(payload)
    except Exception as exc:
        raise StrategyMatrixStructuralBuildError(
            f"materialized projection failed reader self-validation: {exc}"
        ) from exc
    return payload


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def _read_and_verify(path: Path, expected_sha256: str, label: str) -> bytes:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise StrategyMatrixStructuralBuildError(
            f"cannot read the pinned {label} source: {exc}"
        ) from exc
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise StrategyMatrixStructuralBuildError(
            f"the pinned {label} source checksum does not match "
            f"(expected {expected_sha256}, got {actual})"
        )
    return raw


def _json_object(raw: bytes, label: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StrategyMatrixStructuralBuildError(
            f"the pinned {label} source is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise StrategyMatrixStructuralBuildError(f"the pinned {label} source must be a JSON object")
    return cast(dict[str, object], parsed)


def _method_objectives_from_ledger(ledger: dict[str, object]) -> dict[StructuralMethodId, str]:
    matrix_block = ledger.get("imported_optimizer_matrix")
    if not isinstance(matrix_block, dict):
        raise StrategyMatrixStructuralBuildError("ledger is missing imported_optimizer_matrix")
    methods_value = cast(dict[str, object], matrix_block).get("methods")
    if not isinstance(methods_value, list):
        raise StrategyMatrixStructuralBuildError(
            "ledger imported_optimizer_matrix.methods must be a list"
        )
    methods = cast(list[object], methods_value)
    if len(methods) != len(STRUCTURAL_METHOD_IDS):
        raise StrategyMatrixStructuralBuildError(
            f"ledger imported_optimizer_matrix.methods must contain exactly "
            f"{len(STRUCTURAL_METHOD_IDS)} entries"
        )
    objectives: dict[StructuralMethodId, str] = {}
    for entry in methods:
        if not isinstance(entry, dict):
            raise StrategyMatrixStructuralBuildError("ledger method entry must be an object")
        record = cast(dict[str, object], entry)
        strategy_id = record.get("strategy_id")
        objective = record.get("objective")
        if not isinstance(strategy_id, str) or not isinstance(objective, str) or not objective:
            raise StrategyMatrixStructuralBuildError(
                "ledger method entry is missing a strategy_id or objective"
            )
        try:
            method_id = StructuralMethodId(strategy_id)
        except ValueError as exc:
            raise StrategyMatrixStructuralBuildError(
                f"ledger method {strategy_id!r} is not one of the canonical 14 methods"
            ) from exc
        if method_id in objectives:
            raise StrategyMatrixStructuralBuildError(f"ledger method {strategy_id!r} is duplicated")
        objectives[method_id] = objective
    if set(objectives) != set(STRUCTURAL_METHOD_IDS):
        raise StrategyMatrixStructuralBuildError(
            "ledger method universe does not match the canonical 14 methods"
        )
    return objectives


def _index_by_row_id(items: list[object], label: str) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise StrategyMatrixStructuralBuildError(f"{label} entry must be an object")
        record = cast(dict[str, object], item)
        row_id = record.get("row_id")
        if not isinstance(row_id, str) or not row_id:
            raise StrategyMatrixStructuralBuildError(f"{label} entry is missing row_id")
        if row_id in indexed:
            raise StrategyMatrixStructuralBuildError(f"{label} has a duplicate row_id {row_id!r}")
        indexed[row_id] = record
    return indexed


def _index_metric_surface(
    metric_surface: dict[str, object],
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    evaluated = metric_surface.get("evaluated_cells")
    unavailable = metric_surface.get("unavailable_cells")
    if not isinstance(evaluated, list) or not isinstance(unavailable, list):
        raise StrategyMatrixStructuralBuildError(
            "metric surface evaluated_cells/unavailable_cells must be lists"
        )
    evaluated_by_id = _index_by_row_id(
        cast(list[object], evaluated), "metric surface evaluated_cells"
    )
    unavailable_by_id = _index_by_row_id(
        cast(list[object], unavailable), "metric surface unavailable_cells"
    )
    overlap = set(evaluated_by_id) & set(unavailable_by_id)
    if overlap:
        raise StrategyMatrixStructuralBuildError(
            "metric surface has a row_id present in both evaluated and unavailable cells"
        )
    return evaluated_by_id, unavailable_by_id


def _index_matrix_rows(matrix: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = matrix.get("rows")
    if not isinstance(rows, list):
        raise StrategyMatrixStructuralBuildError("matrix rows must be a list")
    return _index_by_row_id(cast(list[object], rows), "matrix rows")


def _build_cell(
    *,
    row_id: str,
    case_id: StructuralCaseId,
    lottery: StructuralLottery,
    method_id: StructuralMethodId,
    ticket_count: StructuralTicketCount,
    method_objective: str,
    evaluated_by_id: dict[str, dict[str, object]],
    unavailable_by_id: dict[str, dict[str, object]],
    matrix_rows_by_id: dict[str, dict[str, object]],
) -> dict[str, object]:
    evaluated = evaluated_by_id.get(row_id)
    unavailable = unavailable_by_id.get(row_id)
    if evaluated is not None and unavailable is not None:
        raise StrategyMatrixStructuralBuildError(
            f"row {row_id} is present in both evaluated and unavailable cells"
        )
    if evaluated is None and unavailable is None:
        raise StrategyMatrixStructuralBuildError(f"row {row_id} is missing from the metric surface")

    matrix_row = matrix_rows_by_id.get(row_id)
    if matrix_row is None:
        raise StrategyMatrixStructuralBuildError(f"row {row_id} is missing from the matrix rows")

    value_object: dict[str, object] | None
    portfolio_sha256_value: str | None
    unavailable_reason: str | None

    if evaluated is not None:
        source_status = evaluated.get("status")
        if source_status not in ("MEASURED", "REUSED_VERIFIED"):
            raise StrategyMatrixStructuralBuildError(
                f"row {row_id} evaluated status {source_status!r} is unexpected"
            )
        value_field = evaluated.get("expected_max_main_matches_v1")
        if not isinstance(value_field, dict):
            raise StrategyMatrixStructuralBuildError(
                f"row {row_id} is missing expected_max_main_matches_v1"
            )
        numerator = cast(dict[str, object], value_field).get("numerator")
        denominator = cast(dict[str, object], value_field).get("denominator")
        if (
            isinstance(numerator, bool)
            or not isinstance(numerator, int)
            or isinstance(denominator, bool)
            or not isinstance(denominator, int)
            or numerator < 0
            or denominator <= 0
        ):
            raise StrategyMatrixStructuralBuildError(
                f"row {row_id} expected_max_main_matches_v1 is malformed"
            )
        portfolio_sha256 = evaluated.get("portfolio_sha256")
        if not isinstance(portfolio_sha256, str) or not portfolio_sha256:
            raise StrategyMatrixStructuralBuildError(f"row {row_id} is missing portfolio_sha256")
        measurement_status = "MEASURED"
        value_object = {"numerator": str(numerator), "denominator": str(denominator)}
        portfolio_sha256_value = portfolio_sha256
        unavailable_reason = None
    else:
        assert unavailable is not None
        source_status = unavailable.get("status")
        if source_status not in ("NOT_APPLICABLE", "REUSED_VERIFIED"):
            raise StrategyMatrixStructuralBuildError(
                f"row {row_id} unavailable status {source_status!r} is unexpected"
            )
        reason = unavailable.get("reason")
        if not isinstance(reason, str) or not reason:
            raise StrategyMatrixStructuralBuildError(
                f"row {row_id} is missing an unavailable reason"
            )
        measurement_status = (
            "NOT_APPLICABLE" if source_status == "NOT_APPLICABLE" else "UNAVAILABLE"
        )
        value_object = None
        portfolio_sha256_value = None
        unavailable_reason = reason

    local_optimum_status: str | None = None
    if method_objective == _EXPECTED_MAX_OBJECTIVE and measurement_status == "MEASURED":
        raw_local_optimum_status = matrix_row.get("local_optimum_status")
        if not isinstance(raw_local_optimum_status, str) or not raw_local_optimum_status:
            raise StrategyMatrixStructuralBuildError(
                f"row {row_id} is missing a local_optimum_status"
            )
        local_optimum_status = raw_local_optimum_status

    return {
        "row_id": row_id,
        "case_id": case_id.value,
        "lottery": lottery.value,
        "method_id": method_id.value,
        "ticket_count": int(ticket_count),
        "method_objective": method_objective,
        "source_status": source_status,
        "measurement_status": measurement_status,
        "value": value_object,
        "portfolio_sha256": portfolio_sha256_value,
        "unavailable_reason": unavailable_reason,
        "local_optimum_status": local_optimum_status,
    }
