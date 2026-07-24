"""Closed descriptive random-baseline evidence for research qualification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from lottolab.application.historical_success_qualification import (
    HistoricalSuccessQualificationIdentity,
)
from lottolab.application.historical_success_random_baseline import (
    RANDOM_BASELINE_POLICY_VERSION,
    HistoricalSuccessRandomBaselineReadiness,
    HistoricalSuccessRandomBaselineResult,
)
from lottolab.domain.strategy_success_evaluation import WindowKind
from lottolab.domain.strategy_success_measurement import DEFAULT_WINDOW_POLICY_VERSION

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class HistoricalSuccessQualificationRandomBaselineContractError(ValueError):
    """Aggregate random-baseline evidence violates the closed R1 contract."""


class HistoricalSuccessQualificationRandomRole(StrEnum):
    REFERENCE_ONLY = "REFERENCE_ONLY"
    PRIMARY_DESCRIPTIVE_COMPARISON = "PRIMARY_DESCRIPTIVE_COMPARISON"
    CONFIRMATION_DESCRIPTIVE_COMPARISON = "CONFIRMATION_DESCRIPTIVE_COMPARISON"
    AUDIT_ONLY_NON_BLOCKING = "AUDIT_ONLY_NON_BLOCKING"


class HistoricalSuccessQualificationRandomAvailabilityStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    ALL_NOT_READY = "ALL_NOT_READY"


QUALIFICATION_RANDOM_WINDOW_ROLES = (
    (WindowKind.FULL_HISTORY, HistoricalSuccessQualificationRandomRole.REFERENCE_ONLY),
    (
        WindowKind.LONG,
        HistoricalSuccessQualificationRandomRole.PRIMARY_DESCRIPTIVE_COMPARISON,
    ),
    (
        WindowKind.MEDIUM,
        HistoricalSuccessQualificationRandomRole.CONFIRMATION_DESCRIPTIVE_COMPARISON,
    ),
    (
        WindowKind.SHORT,
        HistoricalSuccessQualificationRandomRole.AUDIT_ONLY_NON_BLOCKING,
    ),
)

_MULTIPLE_TESTING_WARNING = (
    "This response evaluated {evaluated_cell_count} import × window cells. Each READY "  # noqa: RUF001
    "upper_tail_probability is a raw, unadjusted exact descriptive value. No multiplicity "
    "adjustment, threshold, pooled probability, combined decision, or random-advantage "
    "inference is authorized."
)


def render_multiple_testing_warning(evaluated_cell_count: int) -> str:
    if type(evaluated_cell_count) is not int or evaluated_cell_count < 1:
        raise HistoricalSuccessQualificationRandomBaselineContractError(
            "evaluated_cell_count must be a positive integer"
        )
    return _MULTIPLE_TESTING_WARNING.format(evaluated_cell_count=evaluated_cell_count)


@dataclass(frozen=True, slots=True)
class HistoricalSuccessQualificationRandomBaselineAvailability:
    availability_status: HistoricalSuccessQualificationRandomAvailabilityStatus
    evaluated_cell_count: int
    ready_cell_count: int
    raw_upper_tail_probability_count: int
    multiple_testing_warning: str

    def __post_init__(self) -> None:
        for name in (
            "evaluated_cell_count",
            "ready_cell_count",
            "raw_upper_tail_probability_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise HistoricalSuccessQualificationRandomBaselineContractError(
                    f"{name} must be a non-negative integer"
                )
        if self.evaluated_cell_count < 1:
            raise HistoricalSuccessQualificationRandomBaselineContractError(
                "evaluated_cell_count must be positive"
            )
        if not (
            self.raw_upper_tail_probability_count
            == self.ready_cell_count
            <= self.evaluated_cell_count
        ):
            raise HistoricalSuccessQualificationRandomBaselineContractError(
                "availability counts are contradictory"
            )
        expected_status = (
            HistoricalSuccessQualificationRandomAvailabilityStatus.COMPLETE
            if self.ready_cell_count == self.evaluated_cell_count
            else HistoricalSuccessQualificationRandomAvailabilityStatus.PARTIAL
            if self.ready_cell_count > 0
            else HistoricalSuccessQualificationRandomAvailabilityStatus.ALL_NOT_READY
        )
        if self.availability_status is not expected_status:
            raise HistoricalSuccessQualificationRandomBaselineContractError(
                "availability status contradicts READY counts"
            )
        if self.multiple_testing_warning != render_multiple_testing_warning(
            self.evaluated_cell_count
        ):
            raise HistoricalSuccessQualificationRandomBaselineContractError(
                "multiple-testing warning is not the exact R1 wording"
            )


@dataclass(frozen=True, slots=True)
class HistoricalSuccessQualificationRandomBaselineCell:
    import_index: int
    window_index: int
    qualification_random_role: HistoricalSuccessQualificationRandomRole
    baseline: HistoricalSuccessRandomBaselineResult

    def __post_init__(self) -> None:
        if type(self.import_index) is not int or self.import_index < 0:
            raise HistoricalSuccessQualificationRandomBaselineContractError(
                "import_index must be a non-negative integer"
            )
        if type(self.window_index) is not int or not 0 <= self.window_index < len(
            QUALIFICATION_RANDOM_WINDOW_ROLES
        ):
            raise HistoricalSuccessQualificationRandomBaselineContractError(
                "window_index is outside the closed four-window order"
            )
        if type(self.baseline) is not HistoricalSuccessRandomBaselineResult:
            raise HistoricalSuccessQualificationRandomBaselineContractError(
                "baseline must be a typed random-baseline result"
            )
        expected_window, expected_role = QUALIFICATION_RANDOM_WINDOW_ROLES[self.window_index]
        if (
            self.qualification_random_role is not expected_role
            or self.baseline.cell.window_kind is not expected_window
        ):
            raise HistoricalSuccessQualificationRandomBaselineContractError(
                "window index, role, and baseline window must agree"
            )


@dataclass(frozen=True, slots=True)
class HistoricalSuccessQualificationRandomBaselineEvidence:
    qualification_identity: HistoricalSuccessQualificationIdentity
    ordered_import_identity_sha256s: tuple[str, ...]
    availability_summary: HistoricalSuccessQualificationRandomBaselineAvailability
    ordered_cells: tuple[HistoricalSuccessQualificationRandomBaselineCell, ...]

    def __post_init__(self) -> None:
        if type(self.qualification_identity) is not HistoricalSuccessQualificationIdentity:
            raise HistoricalSuccessQualificationRandomBaselineContractError(
                "qualification_identity is malformed"
            )
        if (
            type(self.ordered_import_identity_sha256s) is not tuple
            or not 2 <= len(self.ordered_import_identity_sha256s) <= 4
            or len(set(self.ordered_import_identity_sha256s))
            != len(self.ordered_import_identity_sha256s)
            or any(
                type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None
                for value in self.ordered_import_identity_sha256s
            )
        ):
            raise HistoricalSuccessQualificationRandomBaselineContractError(
                "ordered import identities must contain two to four distinct SHA-256 values"
            )
        expected_indexes = tuple(
            (import_index, window_index)
            for import_index in range(len(self.ordered_import_identity_sha256s))
            for window_index in range(len(QUALIFICATION_RANDOM_WINDOW_ROLES))
        )
        if (
            tuple((cell.import_index, cell.window_index) for cell in self.ordered_cells)
            != expected_indexes
        ):
            raise HistoricalSuccessQualificationRandomBaselineContractError(
                "cells must preserve caller import order then the four-window order"
            )
        source_hashes: dict[int, tuple[str, str]] = {}
        for cell in self.ordered_cells:
            baseline_identity = cell.baseline.cell
            expected_import_identity = self.ordered_import_identity_sha256s[cell.import_index]
            if (
                baseline_identity.import_identity_sha256 != expected_import_identity
                or baseline_identity.strategy_id != self.qualification_identity.strategy_id
                or baseline_identity.strategy_version
                != self.qualification_identity.strategy_version
                or baseline_identity.replicate != self.qualification_identity.replicate
                or baseline_identity.prefix_count != self.qualification_identity.prefix_count
                or baseline_identity.criterion.value != self.qualification_identity.criterion
                or baseline_identity.policy_version != RANDOM_BASELINE_POLICY_VERSION
                or baseline_identity.window_policy_version != DEFAULT_WINDOW_POLICY_VERSION
            ):
                raise HistoricalSuccessQualificationRandomBaselineContractError(
                    "baseline identity does not match the aggregate qualification identity"
                )
            hashes = (
                baseline_identity.dataset_sha256,
                baseline_identity.source_artifact_sha256,
            )
            prior_hashes = source_hashes.setdefault(cell.import_index, hashes)
            if prior_hashes != hashes:
                raise HistoricalSuccessQualificationRandomBaselineContractError(
                    "source hashes must stay fixed across one import's windows"
                )
        ready_count = sum(
            cell.baseline.readiness is HistoricalSuccessRandomBaselineReadiness.READY
            for cell in self.ordered_cells
        )
        if self.availability_summary != _availability_summary(
            evaluated_cell_count=len(self.ordered_cells),
            ready_cell_count=ready_count,
        ):
            raise HistoricalSuccessQualificationRandomBaselineContractError(
                "availability summary contradicts the ordered cells"
            )


def _availability_summary(
    *,
    evaluated_cell_count: int,
    ready_cell_count: int,
) -> HistoricalSuccessQualificationRandomBaselineAvailability:
    status = (
        HistoricalSuccessQualificationRandomAvailabilityStatus.COMPLETE
        if ready_cell_count == evaluated_cell_count
        else HistoricalSuccessQualificationRandomAvailabilityStatus.PARTIAL
        if ready_cell_count > 0
        else HistoricalSuccessQualificationRandomAvailabilityStatus.ALL_NOT_READY
    )
    return HistoricalSuccessQualificationRandomBaselineAvailability(
        availability_status=status,
        evaluated_cell_count=evaluated_cell_count,
        ready_cell_count=ready_cell_count,
        raw_upper_tail_probability_count=ready_cell_count,
        multiple_testing_warning=render_multiple_testing_warning(evaluated_cell_count),
    )


def aggregate_historical_success_qualification_random_baseline_evidence(
    *,
    qualification_identity: HistoricalSuccessQualificationIdentity,
    ordered_import_identity_sha256s: tuple[str, ...],
    ordered_baselines: tuple[HistoricalSuccessRandomBaselineResult, ...],
) -> HistoricalSuccessQualificationRandomBaselineEvidence:
    expected_count = len(ordered_import_identity_sha256s) * len(QUALIFICATION_RANDOM_WINDOW_ROLES)
    if len(ordered_baselines) != expected_count:
        raise HistoricalSuccessQualificationRandomBaselineContractError(
            "aggregate requires exactly four baseline cells per import"
        )
    cells = tuple(
        HistoricalSuccessQualificationRandomBaselineCell(
            import_index=index // len(QUALIFICATION_RANDOM_WINDOW_ROLES),
            window_index=index % len(QUALIFICATION_RANDOM_WINDOW_ROLES),
            qualification_random_role=QUALIFICATION_RANDOM_WINDOW_ROLES[
                index % len(QUALIFICATION_RANDOM_WINDOW_ROLES)
            ][1],
            baseline=baseline,
        )
        for index, baseline in enumerate(ordered_baselines)
    )
    ready_count = sum(
        baseline.readiness is HistoricalSuccessRandomBaselineReadiness.READY
        for baseline in ordered_baselines
    )
    return HistoricalSuccessQualificationRandomBaselineEvidence(
        qualification_identity=qualification_identity,
        ordered_import_identity_sha256s=ordered_import_identity_sha256s,
        availability_summary=_availability_summary(
            evaluated_cell_count=len(cells),
            ready_cell_count=ready_count,
        ),
        ordered_cells=cells,
    )


__all__ = [
    "QUALIFICATION_RANDOM_WINDOW_ROLES",
    "HistoricalSuccessQualificationRandomAvailabilityStatus",
    "HistoricalSuccessQualificationRandomBaselineAvailability",
    "HistoricalSuccessQualificationRandomBaselineCell",
    "HistoricalSuccessQualificationRandomBaselineContractError",
    "HistoricalSuccessQualificationRandomBaselineEvidence",
    "HistoricalSuccessQualificationRandomRole",
    "aggregate_historical_success_qualification_random_baseline_evidence",
    "render_multiple_testing_warning",
]
