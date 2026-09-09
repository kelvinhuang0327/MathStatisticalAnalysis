"""Unit tests for the packaged structural Matrix projection reader."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

import pytest

import lottolab.infrastructure.strategy_matrix_structural_reader as reader_module
from lottolab.application.strategy_matrix_structural import (
    EXPECTED_CELL_COUNT,
    StructuralLottery,
    StructuralMeasurementStatus,
    StructuralMethodId,
    StructuralTicketCount,
)
from lottolab.infrastructure.strategy_matrix_structural_reader import (
    PROJECTION_RESOURCE_NAME,
    PackagedStrategyMatrixStructuralReader,
    StrategyMatrixStructuralProjectionError,
    parse_structural_projection,
)

_RESOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "lottolab" / "strategies" / "data"


def _load_valid_document() -> dict[str, Any]:
    raw = (_RESOURCE_ROOT / PROJECTION_RESOURCE_NAME).read_bytes()
    return cast(dict[str, Any], json.loads(raw))


def _reseal(document: dict[str, Any]) -> bytes:
    sealed = dict(document)
    canonical = json.dumps(
        {key: value for key, value in sealed.items() if key != "projection_sha256"},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    sealed["projection_sha256"] = hashlib.sha256(canonical).hexdigest()
    return (
        json.dumps(sealed, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        + b"\n"
    )


def test_reads_the_real_committed_artifact() -> None:
    dataset = PackagedStrategyMatrixStructuralReader().read()
    assert len(dataset.cells) == EXPECTED_CELL_COUNT == 210

    k20 = next(
        cell
        for cell in dataset.cells
        if cell.lottery is StructuralLottery.BIG_LOTTO
        and cell.method_id is StructuralMethodId.ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1
        and cell.ticket_count is StructuralTicketCount.TWENTY
    )
    assert k20.measurement_status is StructuralMeasurementStatus.MEASURED
    assert k20.value is not None
    assert (k20.value.numerator, k20.value.denominator) == ("8249099", "3495954")
    assert k20.local_optimum_status == "COMPLETE_RADIUS_1_LOCAL_OPTIMUM"


def test_status_partition_matches_the_frozen_v1_grid() -> None:
    dataset = PackagedStrategyMatrixStructuralReader().read()
    counts = Counter((cell.lottery, cell.measurement_status) for cell in dataset.cells)

    assert counts[(StructuralLottery.BIG_LOTTO, StructuralMeasurementStatus.MEASURED)] == 46
    assert counts[(StructuralLottery.BIG_LOTTO, StructuralMeasurementStatus.NOT_APPLICABLE)] == 6
    assert counts[(StructuralLottery.BIG_LOTTO, StructuralMeasurementStatus.UNAVAILABLE)] == 18
    assert counts[(StructuralLottery.DAILY_539, StructuralMeasurementStatus.MEASURED)] == 29
    assert counts[(StructuralLottery.DAILY_539, StructuralMeasurementStatus.NOT_APPLICABLE)] == 25
    assert counts[(StructuralLottery.DAILY_539, StructuralMeasurementStatus.UNAVAILABLE)] == 16
    assert counts[(StructuralLottery.POWER_LOTTO_ZONE1, StructuralMeasurementStatus.MEASURED)] == 28
    assert (
        counts[(StructuralLottery.POWER_LOTTO_ZONE1, StructuralMeasurementStatus.NOT_APPLICABLE)]
        == 30
    )
    assert (
        counts[(StructuralLottery.POWER_LOTTO_ZONE1, StructuralMeasurementStatus.UNAVAILABLE)] == 12
    )


def test_no_measured_cell_is_silently_zero_and_absent() -> None:
    # Real V1 data happens to contain no zero-valued measured cell; assert that
    # explicitly so the separate synthetic zero-round-trip test below is the
    # thing actually proving "zero must not become null", not an accident.
    dataset = PackagedStrategyMatrixStructuralReader().read()
    zero_valued = [
        cell for cell in dataset.cells if cell.value is not None and cell.value.numerator == "0"
    ]
    assert zero_valued == []


def test_synthetic_zero_value_round_trips_as_measured_not_null() -> None:
    document = _load_valid_document()
    cells = cast(list[dict[str, Any]], document["cells"])
    target = next(cell for cell in cells if cell["measurement_status"] == "MEASURED")
    target["value"] = {"numerator": "0", "denominator": target["value"]["denominator"]}
    document["cells"] = [target if cell["row_id"] == target["row_id"] else cell for cell in cells]

    dataset = parse_structural_projection(_reseal(document))
    patched = next(cell for cell in dataset.cells if cell.row_id == target["row_id"])
    assert patched.measurement_status is StructuralMeasurementStatus.MEASURED
    assert patched.value is not None
    assert patched.value.numerator == "0"


def test_packaged_resource_missing_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    original_read_bytes = Path.read_bytes

    def fail(path: Path) -> bytes:
        if path.name == PROJECTION_RESOURCE_NAME:
            raise FileNotFoundError(path)
        return original_read_bytes(path)

    reader_module._read_packaged_projection.cache_clear()  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(Path, "read_bytes", fail)
    try:
        with pytest.raises(StrategyMatrixStructuralProjectionError):
            PackagedStrategyMatrixStructuralReader().read()
    finally:
        reader_module._read_packaged_projection.cache_clear()  # pyright: ignore[reportPrivateUsage]


def test_packaged_resource_invalid_json_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    original_read_bytes = Path.read_bytes

    def bad(path: Path) -> bytes:
        if path.name == PROJECTION_RESOURCE_NAME:
            return b"{not valid json"
        return original_read_bytes(path)

    reader_module._read_packaged_projection.cache_clear()  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(Path, "read_bytes", bad)
    try:
        with pytest.raises(StrategyMatrixStructuralProjectionError):
            PackagedStrategyMatrixStructuralReader().read()
    finally:
        reader_module._read_packaged_projection.cache_clear()  # pyright: ignore[reportPrivateUsage]


def test_checksum_mismatch_is_rejected() -> None:
    document = _load_valid_document()
    document["projection_sha256"] = "0" * 64
    raw = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    with pytest.raises(StrategyMatrixStructuralProjectionError, match="checksum"):
        parse_structural_projection(raw)


def test_schema_id_mismatch_is_rejected() -> None:
    document = _load_valid_document()
    document["schema_id"] = "wrong.schema.id"
    with pytest.raises(StrategyMatrixStructuralProjectionError, match="schema_id"):
        parse_structural_projection(_reseal(document))


def test_schema_version_mismatch_is_rejected() -> None:
    document = _load_valid_document()
    document["schema_version"] = "9.9.9"
    with pytest.raises(StrategyMatrixStructuralProjectionError, match="schema_version"):
        parse_structural_projection(_reseal(document))


def test_authority_identity_mismatch_is_rejected() -> None:
    document = _load_valid_document()
    document["authority"]["source_head"] = "a" * 40
    with pytest.raises(StrategyMatrixStructuralProjectionError, match="authority"):
        parse_structural_projection(_reseal(document))


def test_authority_source_sha256_mismatch_is_rejected() -> None:
    document = _load_valid_document()
    document["authority"]["sources"]["ledger"]["file_sha256"] = "0" * 64
    with pytest.raises(StrategyMatrixStructuralProjectionError, match="authority"):
        parse_structural_projection(_reseal(document))


def test_missing_cell_is_rejected() -> None:
    document = _load_valid_document()
    document["cells"] = document["cells"][:-1]
    with pytest.raises(StrategyMatrixStructuralProjectionError, match="210 cells"):
        parse_structural_projection(_reseal(document))


def test_duplicate_row_id_is_rejected() -> None:
    document = _load_valid_document()
    cells = cast(list[dict[str, Any]], document["cells"])
    first, second = copy.deepcopy(cells[0]), cells[1]
    # Corrupt the second cell's row_id to collide with the first while keeping
    # its own distinct identity fields, so the grid-identity set stays
    # complete and only the row_id uniqueness check can catch it.
    second["row_id"] = first["row_id"]
    with pytest.raises(StrategyMatrixStructuralProjectionError, match="duplicate"):
        parse_structural_projection(_reseal(document))


def test_malformed_rational_numerator_is_rejected() -> None:
    document = _load_valid_document()
    cells = cast(list[dict[str, Any]], document["cells"])
    target = next(cell for cell in cells if cell["measurement_status"] == "MEASURED")
    target["value"] = {"numerator": "01", "denominator": target["value"]["denominator"]}
    with pytest.raises(StrategyMatrixStructuralProjectionError, match="numerator"):
        parse_structural_projection(_reseal(document))


def test_unreduced_fraction_is_rejected() -> None:
    document = _load_valid_document()
    cells = cast(list[dict[str, Any]], document["cells"])
    target = next(cell for cell in cells if cell["measurement_status"] == "MEASURED")
    numerator = int(target["value"]["numerator"])
    denominator = int(target["value"]["denominator"])
    target["value"] = {"numerator": str(numerator * 2), "denominator": str(denominator * 2)}
    with pytest.raises(StrategyMatrixStructuralProjectionError, match="reduced"):
        parse_structural_projection(_reseal(document))


def test_zero_denominator_is_rejected() -> None:
    document = _load_valid_document()
    cells = cast(list[dict[str, Any]], document["cells"])
    target = next(cell for cell in cells if cell["measurement_status"] == "MEASURED")
    target["value"] = {"numerator": target["value"]["numerator"], "denominator": "0"}
    with pytest.raises(StrategyMatrixStructuralProjectionError, match="denominator"):
        parse_structural_projection(_reseal(document))


def test_k20_exact_ascent_value_tampering_is_rejected() -> None:
    document = _load_valid_document()
    cells = cast(list[dict[str, Any]], document["cells"])
    target = next(
        cell
        for cell in cells
        if cell["row_id"]
        == "NATIVE_BIG_LOTTO|ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1|default|k20|m3"
    )
    target["value"] = {"numerator": "1", "denominator": target["value"]["denominator"]}
    with pytest.raises(StrategyMatrixStructuralProjectionError, match="K20"):
        parse_structural_projection(_reseal(document))


def test_measured_cell_outside_draw_size_range_is_rejected() -> None:
    document = _load_valid_document()
    cells = cast(list[dict[str, Any]], document["cells"])
    target = next(
        cell
        for cell in cells
        if cell["lottery"] == "BIG_LOTTO" and cell["measurement_status"] == "MEASURED"
    )
    denominator = int(target["value"]["denominator"])
    target["value"] = {"numerator": str(denominator * 7 + 1), "denominator": str(denominator)}
    with pytest.raises(StrategyMatrixStructuralProjectionError, match="range"):
        parse_structural_projection(_reseal(document))


def test_unavailable_cell_without_reason_is_rejected() -> None:
    document = _load_valid_document()
    cells = cast(list[dict[str, Any]], document["cells"])
    target = next(cell for cell in cells if cell["measurement_status"] == "NOT_APPLICABLE")
    target["unavailable_reason"] = None
    with pytest.raises(StrategyMatrixStructuralProjectionError):
        parse_structural_projection(_reseal(document))


def test_extra_top_level_key_is_rejected() -> None:
    document = _load_valid_document()
    document["unexpected_extra_field"] = "surprise"
    with pytest.raises(StrategyMatrixStructuralProjectionError):
        parse_structural_projection(_reseal(document))
