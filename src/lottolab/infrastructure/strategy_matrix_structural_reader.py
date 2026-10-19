"""Fixed-resource reader for the immutable structural Matrix projection.

Reads only the one checksum-pinned packaged artifact via
``importlib.resources``; never discovers reports at runtime and never
dereferences ``docs/research`` (or any repository-root path) from the
running application.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from enum import StrEnum
from functools import lru_cache
from importlib.resources import files
from math import gcd
from typing import cast

from lottolab.application.strategy_matrix_structural import (
    EXPECTED_CELL_COUNT,
    K20_EXACT_ASCENT_LOTTERY,
    K20_EXACT_ASCENT_METHOD_ID,
    K20_EXACT_ASCENT_TICKET_COUNT,
    K20_EXACT_ASCENT_VALUE,
    PINNED_AUTHORITY,
    PINNED_CLAIM_BOUNDARY,
    PINNED_METRIC,
    SCHEMA_ID,
    SCHEMA_VERSION,
    SCOPE,
    STRUCTURAL_LOTTERY_DRAW_SIZE,
    STRUCTURAL_METHOD_IDS,
    STRUCTURAL_TICKET_COUNTS,
    SourceReference,
    StrategyMatrixStructuralContractError,
    StrategyMatrixStructuralDataset,
    StructuralCaseId,
    StructuralLottery,
    StructuralMatrixAuthority,
    StructuralMatrixAuthoritySources,
    StructuralMatrixCell,
    StructuralMatrixClaimBoundary,
    StructuralMatrixMetric,
    StructuralMatrixValue,
    StructuralMeasurementStatus,
    StructuralMethodId,
    StructuralSourceStatus,
    StructuralTicketCount,
)

PROJECTION_RESOURCE_NAME = "strategy_matrix_structural_v1.json"
_SHA256 = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA1 = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_DECIMAL = re.compile(r"^(?:0|[1-9][0-9]*)$", flags=re.ASCII)

_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_id",
        "schema_version",
        "projection_sha256",
        "authority",
        "scope",
        "supported_ticket_counts",
        "metric",
        "claim_boundary",
        "cells",
    }
)
_AUTHORITY_KEYS = frozenset({"kind", "source_head", "source_tree", "sources"})
_SOURCES_KEYS = frozenset({"metric_surface", "matrix", "ledger"})
_SOURCE_REFERENCE_KEYS = frozenset({"repository_path", "file_sha256"})
_METRIC_KEYS = frozenset({"metric_id", "definition", "unit", "draw_distribution", "exactness"})
_CLAIM_BOUNDARY_KEYS = frozenset(
    {
        "historical_outcomes_used",
        "historical_success_rate_claimed",
        "ranking_score_claimed",
        "global_optimum_claimed",
        "cross_lottery_normalization",
    }
)
_CELL_KEYS = frozenset(
    {
        "row_id",
        "case_id",
        "lottery",
        "method_id",
        "ticket_count",
        "method_objective",
        "source_status",
        "measurement_status",
        "value",
        "portfolio_sha256",
        "unavailable_reason",
        "local_optimum_status",
    }
)
_VALUE_KEYS = frozenset({"numerator", "denominator"})


class StrategyMatrixStructuralProjectionError(RuntimeError):
    """The fixed packaged structural Matrix projection is absent or violates its closed contract."""


class PackagedStrategyMatrixStructuralReader:
    """Read only the exact named resource; never discover reports at runtime."""

    def read(self) -> StrategyMatrixStructuralDataset:
        return _read_packaged_projection()


@lru_cache(maxsize=1)
def _read_packaged_projection() -> StrategyMatrixStructuralDataset:
    resource = files("lottolab.strategies.data").joinpath(PROJECTION_RESOURCE_NAME)
    try:
        raw = resource.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise StrategyMatrixStructuralProjectionError(
            "the pinned structural Matrix projection is unavailable"
        ) from exc
    return parse_structural_projection(raw)


def parse_structural_projection(raw: bytes) -> StrategyMatrixStructuralDataset:
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StrategyMatrixStructuralProjectionError(
            "the pinned structural Matrix projection is invalid JSON"
        ) from exc

    try:
        document = _mapping(parsed, "projection")
        _exact_keys(document, _TOP_LEVEL_KEYS, "projection")

        if document["schema_id"] != SCHEMA_ID:
            raise StrategyMatrixStructuralProjectionError("the projection schema_id does not match")
        if document["schema_version"] != SCHEMA_VERSION:
            raise StrategyMatrixStructuralProjectionError(
                "the projection schema_version does not match"
            )
        if document["scope"] != SCOPE:
            raise StrategyMatrixStructuralProjectionError("the projection scope does not match")

        projection_sha256 = _sha256(document["projection_sha256"], "projection_sha256")
        _verify_digest(document, projection_sha256)

        authority = _parse_authority(document["authority"])
        if authority != PINNED_AUTHORITY:
            raise StrategyMatrixStructuralProjectionError(
                "the projection authority identity does not match the pinned source authority"
            )

        supported_ticket_counts = _parse_supported_ticket_counts(
            document["supported_ticket_counts"]
        )

        metric = _parse_metric(document["metric"])
        if metric != PINNED_METRIC:
            raise StrategyMatrixStructuralProjectionError(
                "the projection metric definition does not match V1"
            )

        claim_boundary = _parse_claim_boundary(document["claim_boundary"])
        if claim_boundary != PINNED_CLAIM_BOUNDARY:
            raise StrategyMatrixStructuralProjectionError(
                "the projection claim boundary does not match V1"
            )

        cells = _parse_cells(document["cells"])

        dataset = StrategyMatrixStructuralDataset(
            schema_id=SCHEMA_ID,
            schema_version=SCHEMA_VERSION,
            projection_sha256=projection_sha256,
            authority=authority,
            scope=SCOPE,
            supported_ticket_counts=supported_ticket_counts,
            metric=metric,
            claim_boundary=claim_boundary,
            cells=cells,
        )
    except StrategyMatrixStructuralContractError as exc:
        raise StrategyMatrixStructuralProjectionError(str(exc)) from exc

    _verify_k20_exact_ascent_cell(dataset)
    return dataset


def _verify_digest(document: Mapping[str, object], projection_sha256: str) -> None:
    canonical = json.dumps(
        {key: value for key, value in document.items() if key != "projection_sha256"},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != projection_sha256:
        raise StrategyMatrixStructuralProjectionError(
            "the projection checksum does not match its contents"
        )


def _parse_authority(value: object) -> StructuralMatrixAuthority:
    record = _mapping(value, "authority")
    _exact_keys(record, _AUTHORITY_KEYS, "authority")
    sources_record = _mapping(record["sources"], "authority.sources")
    _exact_keys(sources_record, _SOURCES_KEYS, "authority.sources")
    return StructuralMatrixAuthority(
        kind=_required_string(record, "kind"),
        source_head=_git_sha1(record["source_head"], "authority.source_head"),
        source_tree=_git_sha1(record["source_tree"], "authority.source_tree"),
        sources=StructuralMatrixAuthoritySources(
            metric_surface=_parse_source_reference(
                sources_record["metric_surface"], "metric_surface"
            ),
            matrix=_parse_source_reference(sources_record["matrix"], "matrix"),
            ledger=_parse_source_reference(sources_record["ledger"], "ledger"),
        ),
    )


def _parse_source_reference(value: object, label: str) -> SourceReference:
    record = _mapping(value, f"authority.sources.{label}")
    _exact_keys(record, _SOURCE_REFERENCE_KEYS, f"authority.sources.{label}")
    return SourceReference(
        repository_path=_required_string(record, "repository_path"),
        file_sha256=_sha256(record["file_sha256"], f"authority.sources.{label}.file_sha256"),
    )


def _parse_supported_ticket_counts(value: object) -> tuple[int, ...]:
    expected = tuple(int(count) for count in STRUCTURAL_TICKET_COUNTS)
    if not isinstance(value, list):
        raise StrategyMatrixStructuralProjectionError(
            "the projection supported_ticket_counts does not match V1"
        )
    actual: list[int] = []
    for item in cast(list[object], value):
        if isinstance(item, bool) or not isinstance(item, int):
            raise StrategyMatrixStructuralProjectionError(
                "the projection supported_ticket_counts does not match V1"
            )
        actual.append(item)
    if tuple(actual) != expected:
        raise StrategyMatrixStructuralProjectionError(
            "the projection supported_ticket_counts does not match V1"
        )
    return expected


def _parse_metric(value: object) -> StructuralMatrixMetric:
    record = _mapping(value, "metric")
    _exact_keys(record, _METRIC_KEYS, "metric")
    return StructuralMatrixMetric(
        metric_id=_required_string(record, "metric_id"),
        definition=_required_string(record, "definition"),
        unit=_required_string(record, "unit"),
        draw_distribution=_required_string(record, "draw_distribution"),
        exactness=_required_string(record, "exactness"),
    )


def _parse_claim_boundary(value: object) -> StructuralMatrixClaimBoundary:
    record = _mapping(value, "claim_boundary")
    _exact_keys(record, _CLAIM_BOUNDARY_KEYS, "claim_boundary")
    return StructuralMatrixClaimBoundary(
        historical_outcomes_used=_required_bool(record, "historical_outcomes_used"),
        historical_success_rate_claimed=_required_bool(record, "historical_success_rate_claimed"),
        ranking_score_claimed=_required_bool(record, "ranking_score_claimed"),
        global_optimum_claimed=_required_bool(record, "global_optimum_claimed"),
        cross_lottery_normalization=_required_string(record, "cross_lottery_normalization"),
    )


def _parse_cells(value: object) -> tuple[StructuralMatrixCell, ...]:
    if not isinstance(value, list):
        raise StrategyMatrixStructuralProjectionError("projection cells must be a list")
    raw_cells = cast(list[object], value)
    if len(raw_cells) != EXPECTED_CELL_COUNT:
        raise StrategyMatrixStructuralProjectionError(
            f"projection must contain exactly {EXPECTED_CELL_COUNT} cells"
        )

    cells = tuple(_parse_cell(item) for item in raw_cells)

    expected_identities = {
        (lottery, method_id, ticket_count)
        for lottery in StructuralLottery
        for method_id in STRUCTURAL_METHOD_IDS
        for ticket_count in STRUCTURAL_TICKET_COUNTS
    }
    actual_identities = {(cell.lottery, cell.method_id, cell.ticket_count) for cell in cells}
    if actual_identities != expected_identities:
        missing = expected_identities - actual_identities
        extra = actual_identities - expected_identities
        raise StrategyMatrixStructuralProjectionError(
            f"projection grid is incomplete (missing={len(missing)}, extra={len(extra)})"
        )
    if len({cell.row_id for cell in cells}) != len(cells):
        raise StrategyMatrixStructuralProjectionError("projection contains a duplicate cell row_id")

    for cell in cells:
        if cell.measurement_status is StructuralMeasurementStatus.MEASURED:
            assert cell.value is not None
            draw_size = STRUCTURAL_LOTTERY_DRAW_SIZE[cell.lottery]
            numerator = int(cell.value.numerator)
            denominator = int(cell.value.denominator)
            if not (0 <= numerator <= draw_size * denominator):
                raise StrategyMatrixStructuralProjectionError(
                    f"cell {cell.row_id} value is outside the applicable main-draw-size range"
                )

    return cells


def _parse_cell(value: object) -> StructuralMatrixCell:
    record = _mapping(value, "cell")
    _exact_keys(record, _CELL_KEYS, "cell")

    row_id = _required_string(record, "row_id")
    case_id = _enum_member(record, "case_id", StructuralCaseId, row_id)
    lottery = _enum_member(record, "lottery", StructuralLottery, row_id)
    method_id = _enum_member(record, "method_id", StructuralMethodId, row_id)
    ticket_count = _ticket_count(record, row_id)
    method_objective = _required_string(record, "method_objective")
    source_status = _enum_member(record, "source_status", StructuralSourceStatus, row_id)
    measurement_status = _enum_member(
        record, "measurement_status", StructuralMeasurementStatus, row_id
    )
    value_field = _parse_value(record["value"], row_id)
    portfolio_sha256 = _optional_sha256(record["portfolio_sha256"], row_id)
    unavailable_reason = _optional_string(
        record["unavailable_reason"], "unavailable_reason", row_id
    )
    local_optimum_status = _optional_string(
        record["local_optimum_status"], "local_optimum_status", row_id
    )

    try:
        return StructuralMatrixCell(
            row_id=row_id,
            case_id=case_id,
            lottery=lottery,
            method_id=method_id,
            ticket_count=ticket_count,
            method_objective=method_objective,
            source_status=source_status,
            measurement_status=measurement_status,
            value=value_field,
            portfolio_sha256=portfolio_sha256,
            unavailable_reason=unavailable_reason,
            local_optimum_status=local_optimum_status,
        )
    except StrategyMatrixStructuralContractError as exc:
        raise StrategyMatrixStructuralProjectionError(str(exc)) from exc


def _verify_k20_exact_ascent_cell(dataset: StrategyMatrixStructuralDataset) -> None:
    for cell in dataset.cells:
        if (
            cell.lottery is K20_EXACT_ASCENT_LOTTERY
            and cell.method_id is K20_EXACT_ASCENT_METHOD_ID
            and cell.ticket_count is K20_EXACT_ASCENT_TICKET_COUNT
        ):
            if (
                cell.measurement_status is not StructuralMeasurementStatus.MEASURED
                or cell.value != K20_EXACT_ASCENT_VALUE
            ):
                raise StrategyMatrixStructuralProjectionError(
                    "the pinned K20 exact-ascent cell does not match its required value"
                )
            return
    raise StrategyMatrixStructuralProjectionError("the pinned K20 exact-ascent cell is missing")


def _parse_value(value: object, row_id: str) -> StructuralMatrixValue | None:
    if value is None:
        return None
    record = _mapping(value, f"cell {row_id}.value")
    _exact_keys(record, _VALUE_KEYS, f"cell {row_id}.value")
    numerator = record["numerator"]
    denominator = record["denominator"]
    if not isinstance(numerator, str) or not _DECIMAL.fullmatch(numerator):
        raise StrategyMatrixStructuralProjectionError(f"cell {row_id} value numerator is malformed")
    if (
        not isinstance(denominator, str)
        or not _DECIMAL.fullmatch(denominator)
        or denominator == "0"
    ):
        raise StrategyMatrixStructuralProjectionError(
            f"cell {row_id} value denominator is malformed"
        )
    if numerator != "0" and gcd(int(numerator), int(denominator)) != 1:
        raise StrategyMatrixStructuralProjectionError(f"cell {row_id} value is not reduced")
    return StructuralMatrixValue(numerator=numerator, denominator=denominator)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise StrategyMatrixStructuralProjectionError(f"{label} must be a string-keyed object")
    record = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in record):
        raise StrategyMatrixStructuralProjectionError(f"{label} must be a string-keyed object")
    return cast(Mapping[str, object], record)


def _exact_keys(record: Mapping[str, object], keys: AbstractSet[str], label: str) -> None:
    actual = set(record)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise StrategyMatrixStructuralProjectionError(
            f"{label} keys are invalid (missing={missing!r}, extra={extra!r})"
        )


def _required_string(record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise StrategyMatrixStructuralProjectionError(f"{key} must be a non-empty string")
    return value


def _required_bool(record: Mapping[str, object], key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise StrategyMatrixStructuralProjectionError(f"{key} must be a boolean")
    return value


def _optional_string(value: object, key: str, row_id: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise StrategyMatrixStructuralProjectionError(
            f"cell {row_id} {key} must be null or a non-empty string"
        )
    return value


def _optional_sha256(value: object, row_id: str) -> str | None:
    if value is None:
        return None
    return _sha256(value, f"cell {row_id}.portfolio_sha256")


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise StrategyMatrixStructuralProjectionError(
            f"{label} must be a lowercase 64-character SHA-256"
        )
    return value


def _git_sha1(value: object, label: str) -> str:
    if not isinstance(value, str) or not _GIT_SHA1.fullmatch(value):
        raise StrategyMatrixStructuralProjectionError(
            f"{label} must be a full 40-character Git SHA-1"
        )
    return value


def _ticket_count(record: Mapping[str, object], row_id: str) -> StructuralTicketCount:
    value = record.get("ticket_count")
    if isinstance(value, bool) or not isinstance(value, int):
        raise StrategyMatrixStructuralProjectionError(
            f"cell {row_id} ticket_count must be an integer"
        )
    try:
        return StructuralTicketCount(value)
    except ValueError as exc:
        raise StrategyMatrixStructuralProjectionError(
            f"cell {row_id} ticket_count {value} is not a supported ticket count"
        ) from exc


def _enum_member[EnumT: StrEnum](
    record: Mapping[str, object], key: str, enum_type: type[EnumT], row_id: str
) -> EnumT:
    value = record.get(key)
    if not isinstance(value, str):
        raise StrategyMatrixStructuralProjectionError(f"cell {row_id} {key} must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise StrategyMatrixStructuralProjectionError(
            f"cell {row_id} {key} {value!r} is not a recognized value"
        ) from exc
