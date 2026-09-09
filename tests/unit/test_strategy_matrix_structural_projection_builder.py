"""Unit tests for the offline structural Matrix projection materializer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

import lottolab.infrastructure.strategy_matrix_structural_projection_builder as builder_module
from lottolab.application.strategy_matrix_structural import (
    PINNED_LEDGER,
    PINNED_MATRIX,
    PINNED_METRIC_SURFACE,
    SourceReference,
    StructuralMeasurementStatus,
    StructuralSourceStatus,
)
from lottolab.infrastructure.strategy_matrix_structural_projection_builder import (
    StrategyMatrixStructuralBuildError,
    build_strategy_matrix_structural_projection_bytes,
)
from lottolab.infrastructure.strategy_matrix_structural_reader import (
    PROJECTION_RESOURCE_NAME,
    parse_structural_projection,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_METRIC_SURFACE_PATH = _REPO_ROOT / PINNED_METRIC_SURFACE.repository_path
_MATRIX_PATH = _REPO_ROOT / PINNED_MATRIX.repository_path
_LEDGER_PATH = _REPO_ROOT / PINNED_LEDGER.repository_path
_PACKAGED_ARTIFACT_PATH = (
    _REPO_ROOT / "src" / "lottolab" / "strategies" / "data" / PROJECTION_RESOURCE_NAME
)


def _write_json(directory: Path, name: str, document: dict[str, Any]) -> Path:
    path = directory / name
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def test_builds_a_valid_projection_from_the_real_pinned_sources() -> None:
    payload = build_strategy_matrix_structural_projection_bytes(
        metric_surface_path=_METRIC_SURFACE_PATH,
        matrix_path=_MATRIX_PATH,
        ledger_path=_LEDGER_PATH,
    )
    dataset = parse_structural_projection(payload)
    assert len(dataset.cells) == 210


def test_not_run_unavailable_status_builds_as_unavailable() -> None:
    payload = build_strategy_matrix_structural_projection_bytes(
        metric_surface_path=_METRIC_SURFACE_PATH,
        matrix_path=_MATRIX_PATH,
        ledger_path=_LEDGER_PATH,
    )
    dataset = parse_structural_projection(payload)
    cell = next(
        cell
        for cell in dataset.cells
        if cell.row_id
        == "NATIVE_DAILY_539|ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1|default|k3|m3"
    )
    assert cell.source_status is StructuralSourceStatus.NOT_RUN
    assert cell.measurement_status is StructuralMeasurementStatus.UNAVAILABLE
    assert cell.value is None
    assert cell.unavailable_reason


def test_rebuilding_from_the_real_pinned_sources_matches_the_committed_artifact() -> None:
    payload = build_strategy_matrix_structural_projection_bytes(
        metric_surface_path=_METRIC_SURFACE_PATH,
        matrix_path=_MATRIX_PATH,
        ledger_path=_LEDGER_PATH,
    )
    committed = _PACKAGED_ARTIFACT_PATH.read_bytes()
    assert payload == committed


def test_metric_surface_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    tampered = json.loads(_METRIC_SURFACE_PATH.read_text(encoding="utf-8"))
    tampered["evaluated_cell_count"] = tampered["evaluated_cell_count"]  # no-op read
    tampered["task_id"] = "TAMPERED"
    tampered_path = _write_json(tmp_path, "metric_surface.json", tampered)

    with pytest.raises(StrategyMatrixStructuralBuildError, match="checksum"):
        build_strategy_matrix_structural_projection_bytes(
            metric_surface_path=tampered_path,
            matrix_path=_MATRIX_PATH,
            ledger_path=_LEDGER_PATH,
        )


def test_matrix_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    tampered = json.loads(_MATRIX_PATH.read_text(encoding="utf-8"))
    tampered["task_id"] = "TAMPERED"
    tampered_path = _write_json(tmp_path, "matrix.json", tampered)

    with pytest.raises(StrategyMatrixStructuralBuildError, match="checksum"):
        build_strategy_matrix_structural_projection_bytes(
            metric_surface_path=_METRIC_SURFACE_PATH,
            matrix_path=tampered_path,
            ledger_path=_LEDGER_PATH,
        )


def test_ledger_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    tampered = json.loads(_LEDGER_PATH.read_text(encoding="utf-8"))
    tampered["ledger_id"] = "TAMPERED"
    tampered_path = _write_json(tmp_path, "ledger.json", tampered)

    with pytest.raises(StrategyMatrixStructuralBuildError, match="checksum"):
        build_strategy_matrix_structural_projection_bytes(
            metric_surface_path=_METRIC_SURFACE_PATH,
            matrix_path=_MATRIX_PATH,
            ledger_path=tampered_path,
        )


def test_missing_source_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(StrategyMatrixStructuralBuildError, match="cannot read"):
        build_strategy_matrix_structural_projection_bytes(
            metric_surface_path=tmp_path / "does-not-exist.json",
            matrix_path=_MATRIX_PATH,
            ledger_path=_LEDGER_PATH,
        )


def test_ledger_missing_a_canonical_method_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = json.loads(_LEDGER_PATH.read_text(encoding="utf-8"))
    methods = cast(list[dict[str, Any]], ledger["imported_optimizer_matrix"]["methods"])
    ledger["imported_optimizer_matrix"]["methods"] = methods[:-1]
    tampered_path = _write_json(tmp_path, "ledger.json", ledger)

    # Re-pin the expected ledger checksum to this tampered copy's own hash so
    # the checksum gate passes and the method-universe validation is the one
    # under test, not the (already separately tested) checksum gate.
    tampered_sha256 = hashlib.sha256(tampered_path.read_bytes()).hexdigest()
    monkeypatch.setattr(
        builder_module,
        "PINNED_LEDGER",
        SourceReference(repository_path=PINNED_LEDGER.repository_path, file_sha256=tampered_sha256),
    )

    with pytest.raises(StrategyMatrixStructuralBuildError, match="exactly 14 entries"):
        build_strategy_matrix_structural_projection_bytes(
            metric_surface_path=_METRIC_SURFACE_PATH,
            matrix_path=_MATRIX_PATH,
            ledger_path=tampered_path,
        )


def test_ledger_with_an_unrecognized_method_id_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = json.loads(_LEDGER_PATH.read_text(encoding="utf-8"))
    methods = cast(list[dict[str, Any]], ledger["imported_optimizer_matrix"]["methods"])
    methods[0]["strategy_id"] = "NOT_A_CANONICAL_METHOD_ID"
    tampered_path = _write_json(tmp_path, "ledger.json", ledger)
    tampered_sha256 = hashlib.sha256(tampered_path.read_bytes()).hexdigest()
    monkeypatch.setattr(
        builder_module,
        "PINNED_LEDGER",
        SourceReference(repository_path=PINNED_LEDGER.repository_path, file_sha256=tampered_sha256),
    )

    with pytest.raises(
        StrategyMatrixStructuralBuildError, match="not one of the canonical 14 methods"
    ):
        build_strategy_matrix_structural_projection_bytes(
            metric_surface_path=_METRIC_SURFACE_PATH,
            matrix_path=_MATRIX_PATH,
            ledger_path=tampered_path,
        )


def test_missing_matrix_row_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    matrix = json.loads(_MATRIX_PATH.read_text(encoding="utf-8"))
    rows = cast(list[dict[str, Any]], matrix["rows"])
    matrix["rows"] = [
        row
        for row in rows
        if row.get("row_id")
        != "NATIVE_BIG_LOTTO|ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1|default|k20|m3"
    ]
    tampered_path = _write_json(tmp_path, "matrix.json", matrix)
    tampered_sha256 = hashlib.sha256(tampered_path.read_bytes()).hexdigest()
    monkeypatch.setattr(
        builder_module,
        "PINNED_MATRIX",
        SourceReference(repository_path=PINNED_MATRIX.repository_path, file_sha256=tampered_sha256),
    )

    with pytest.raises(StrategyMatrixStructuralBuildError, match="missing from the matrix rows"):
        build_strategy_matrix_structural_projection_bytes(
            metric_surface_path=_METRIC_SURFACE_PATH,
            matrix_path=tampered_path,
            ledger_path=_LEDGER_PATH,
        )


def test_missing_metric_surface_row_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metric_surface = json.loads(_METRIC_SURFACE_PATH.read_text(encoding="utf-8"))
    target_row_id = "NATIVE_BIG_LOTTO|ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1|default|k20|m3"
    metric_surface["evaluated_cells"] = [
        row
        for row in cast(list[dict[str, Any]], metric_surface["evaluated_cells"])
        if row.get("row_id") != target_row_id
    ]
    metric_surface["unavailable_cells"] = [
        row
        for row in cast(list[dict[str, Any]], metric_surface["unavailable_cells"])
        if row.get("row_id") != target_row_id
    ]
    tampered_path = _write_json(tmp_path, "metric_surface.json", metric_surface)
    tampered_sha256 = hashlib.sha256(tampered_path.read_bytes()).hexdigest()
    monkeypatch.setattr(
        builder_module,
        "PINNED_METRIC_SURFACE",
        SourceReference(
            repository_path=PINNED_METRIC_SURFACE.repository_path, file_sha256=tampered_sha256
        ),
    )

    with pytest.raises(StrategyMatrixStructuralBuildError, match="missing from the metric surface"):
        build_strategy_matrix_structural_projection_bytes(
            metric_surface_path=tampered_path,
            matrix_path=_MATRIX_PATH,
            ledger_path=_LEDGER_PATH,
        )


def test_output_path_is_never_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "strategy_matrix_structural_v1.json"
    output.write_bytes(b"pre-existing")
    payload = build_strategy_matrix_structural_projection_bytes(
        metric_surface_path=_METRIC_SURFACE_PATH,
        matrix_path=_MATRIX_PATH,
        ledger_path=_LEDGER_PATH,
    )
    with pytest.raises(FileExistsError), output.open("xb") as handle:
        handle.write(payload)
    assert output.read_bytes() == b"pre-existing"
