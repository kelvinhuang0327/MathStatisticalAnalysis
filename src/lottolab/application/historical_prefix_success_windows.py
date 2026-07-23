"""Immutable read models for persisted Historical Prefix success windows.

The source models are the narrow typed boundary returned by infrastructure.
The result models are deterministic application-owned projections over the
merged strategy-success evaluator.  Nothing here imports FastAPI, Pydantic,
SQLite, or filesystem APIs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_results import HistoricalLotteryType
from lottolab.domain.strategy_success_evaluation import (
    WindowEvaluationStatus,
    WindowKind,
)
from lottolab.domain.strategy_success_measurement import (
    EvidenceStatus,
    MeasurementMode,
    WindowRole,
)

SUPPORTED_PREFIX_COUNTS = (1, 2, 3, 4, 5, 10, 15, 20)
DEFAULT_PAGE_LIMIT = 50
DEFAULT_PAGE_OFFSET = 0
MIN_PAGE_LIMIT = 1
MAX_PAGE_LIMIT = 200

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class HistoricalPrefixSuccessWindowsError(RuntimeError):
    """Base class for sanitized application failures in this vertical."""


class HistoricalPrefixSuccessWindowsContractError(HistoricalPrefixSuccessWindowsError):
    """Caller input or a supplied typed source violates the closed contract."""


class HistoricalPrefixSuccessWindowsUnavailableError(HistoricalPrefixSuccessWindowsError):
    """Persisted source state could not be reconstructed or evaluated safely."""


class HistoricalPrefixSuccessImportNotFoundError(HistoricalPrefixSuccessWindowsError):
    """The exact COMPLETED import identity does not exist."""


class HistoricalPrefixSuccessStrategyNotFoundError(HistoricalPrefixSuccessWindowsError):
    """The exact strategy descriptor does not exist in the selected import."""


class HistoricalPrefixSuccessCriterion(StrEnum):
    M3_PLUS = "M3_PLUS"
    M4_PLUS = "M4_PLUS"
    M5_PLUS = "M5_PLUS"
    M6 = "M6"
    M2_PLUS_SPECIAL = "M2_PLUS_SPECIAL"
    M3_PLUS_SPECIAL = "M3_PLUS_SPECIAL"
    M4_PLUS_SPECIAL = "M4_PLUS_SPECIAL"
    M5_PLUS_SPECIAL = "M5_PLUS_SPECIAL"


class HistoricalPrefixSuccessEvaluationStatus(StrEnum):
    EVALUATED = "EVALUATED"
    NO_OBSERVATIONS = "NO_OBSERVATIONS"


def _require_canonical_text(value: str, name: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise HistoricalPrefixSuccessWindowsContractError(
            f"{name} must be a non-empty canonical string"
        )


def _require_optional_canonical_text(value: str | None, name: str) -> None:
    if value is not None:
        _require_canonical_text(value, name)


def _require_sha256(value: str, name: str) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise HistoricalPrefixSuccessWindowsContractError(
            f"{name} must be an exact lowercase SHA-256"
        )


@dataclass(frozen=True, slots=True)
class HistoricalPrefixSuccessWindowSourceMetadata:
    run_id: str
    contract_version: str
    import_identity_sha256: str
    source_kind: str
    source_repository: str
    source_commit_oid: str
    source_artifact_sha256: str
    dataset_identity: str
    dataset_sha256: str
    lottery_type: HistoricalLotteryType

    def __post_init__(self) -> None:
        for name in (
            "run_id",
            "contract_version",
            "source_kind",
            "source_repository",
            "source_commit_oid",
            "dataset_identity",
        ):
            _require_canonical_text(getattr(self, name), name)
        for name in (
            "import_identity_sha256",
            "source_artifact_sha256",
            "dataset_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        if self.lottery_type is not HistoricalLotteryType.BIG_LOTTO:
            raise HistoricalPrefixSuccessWindowsContractError(
                "lottery_type must be exactly BIG_LOTTO"
            )


@dataclass(frozen=True, slots=True)
class HistoricalPrefixSuccessStrategyIdentity:
    strategy_id: str
    effective_strategy_id: str
    strategy_version: str
    replicate: int
    identity_kind: str
    governance_status: str
    alias_of_strategy_id: str | None
    equivalence_group: str | None
    nested_prefix_supported: bool
    descriptor_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "strategy_id",
            "effective_strategy_id",
            "strategy_version",
            "identity_kind",
            "governance_status",
        ):
            _require_canonical_text(getattr(self, name), name)
        _require_optional_canonical_text(self.alias_of_strategy_id, "alias_of_strategy_id")
        _require_optional_canonical_text(self.equivalence_group, "equivalence_group")
        if type(self.replicate) is not int or self.replicate < 1:
            raise HistoricalPrefixSuccessWindowsContractError(
                "replicate must be an integer >= 1"
            )
        if type(self.nested_prefix_supported) is not bool:
            raise HistoricalPrefixSuccessWindowsContractError(
                "nested_prefix_supported must be a boolean"
            )
        _require_sha256(self.descriptor_sha256, "descriptor_sha256")


@dataclass(frozen=True, slots=True)
class HistoricalPrefixSuccessDrawIdentity:
    draw_number: int
    draw_date: str
    draw_sha256: str

    def __post_init__(self) -> None:
        if type(self.draw_number) is not int or self.draw_number < 0:
            raise HistoricalPrefixSuccessWindowsContractError(
                "draw_number must be a non-negative integer"
            )
        _require_canonical_text(self.draw_date, "draw_date")
        _require_sha256(self.draw_sha256, "draw_sha256")


@dataclass(frozen=True, slots=True)
class HistoricalPrefixSuccessTicketOutcome:
    portfolio_position: int
    main_hit_count: int
    special_hit: bool
    ticket_sha256: str

    def __post_init__(self) -> None:
        if type(self.portfolio_position) is not int or self.portfolio_position < 1:
            raise HistoricalPrefixSuccessWindowsContractError(
                "portfolio_position must be a positive integer"
            )
        if type(self.main_hit_count) is not int or not 0 <= self.main_hit_count <= 6:
            raise HistoricalPrefixSuccessWindowsContractError(
                "main_hit_count must be an integer between 0 and 6"
            )
        if type(self.special_hit) is not bool:
            raise HistoricalPrefixSuccessWindowsContractError(
                "special_hit must be a boolean"
            )
        if self.main_hit_count + int(self.special_hit) > 6:
            raise HistoricalPrefixSuccessWindowsContractError(
                "ticket hit signature exceeds the six-number selection"
            )
        _require_sha256(self.ticket_sha256, "ticket_sha256")


@dataclass(frozen=True, slots=True)
class HistoricalPrefixSuccessSourceObservation:
    target: HistoricalPrefixSuccessDrawIdentity
    cutoff: HistoricalPrefixSuccessDrawIdentity
    constructor_identifier: str
    portfolio_sha256: str
    tickets: tuple[HistoricalPrefixSuccessTicketOutcome, ...]

    def __post_init__(self) -> None:
        if type(self.target) is not HistoricalPrefixSuccessDrawIdentity:
            raise HistoricalPrefixSuccessWindowsContractError("target identity is malformed")
        if type(self.cutoff) is not HistoricalPrefixSuccessDrawIdentity:
            raise HistoricalPrefixSuccessWindowsContractError("cutoff identity is malformed")
        _require_canonical_text(self.constructor_identifier, "constructor_identifier")
        _require_sha256(self.portfolio_sha256, "portfolio_sha256")
        if type(self.tickets) is not tuple or len(self.tickets) != 20:
            raise HistoricalPrefixSuccessWindowsContractError(
                "every source observation must carry exactly 20 tickets"
            )
        if any(
            type(ticket) is not HistoricalPrefixSuccessTicketOutcome
            for ticket in self.tickets
        ):
            raise HistoricalPrefixSuccessWindowsContractError(
                "source observation contains a malformed ticket"
            )
        if tuple(ticket.portfolio_position for ticket in self.tickets) != tuple(
            range(1, 21)
        ):
            raise HistoricalPrefixSuccessWindowsContractError(
                "ticket tuple order must match positions 1..20"
            )


@dataclass(frozen=True, slots=True)
class HistoricalPrefixSuccessSourceStrategy:
    identity: HistoricalPrefixSuccessStrategyIdentity
    observations: tuple[HistoricalPrefixSuccessSourceObservation, ...]

    def __post_init__(self) -> None:
        if type(self.identity) is not HistoricalPrefixSuccessStrategyIdentity:
            raise HistoricalPrefixSuccessWindowsContractError("strategy identity is malformed")
        if type(self.observations) is not tuple or any(
            type(item) is not HistoricalPrefixSuccessSourceObservation
            for item in self.observations
        ):
            raise HistoricalPrefixSuccessWindowsContractError(
                "strategy observations must be an immutable typed tuple"
            )


@dataclass(frozen=True, slots=True)
class HistoricalPrefixSuccessWindowSource:
    metadata: HistoricalPrefixSuccessWindowSourceMetadata
    strategies: tuple[HistoricalPrefixSuccessSourceStrategy, ...]

    def __post_init__(self) -> None:
        if type(self.metadata) is not HistoricalPrefixSuccessWindowSourceMetadata:
            raise HistoricalPrefixSuccessWindowsContractError("source metadata is malformed")
        if type(self.strategies) is not tuple or any(
            type(item) is not HistoricalPrefixSuccessSourceStrategy for item in self.strategies
        ):
            raise HistoricalPrefixSuccessWindowsContractError(
                "source strategies must be an immutable typed tuple"
            )
        keys = tuple(
            (
                item.identity.strategy_id,
                item.identity.strategy_version,
                item.identity.replicate,
            )
            for item in self.strategies
        )
        if len(keys) != len(set(keys)):
            raise HistoricalPrefixSuccessWindowsContractError(
                "source contains duplicate exact strategy descriptors"
            )


@dataclass(frozen=True, slots=True)
class HistoricalPrefixSuccessCriterionIdentity:
    criterion: HistoricalPrefixSuccessCriterion
    minimum_main_hits: int
    require_special_hit: bool
    measurement_mode: MeasurementMode


@dataclass(frozen=True, slots=True)
class HistoricalPrefixSuccessSelectionIdentity:
    lottery: LotteryType
    strategy_id: str
    strategy_version: str
    replicate: int
    ticket_count: int
    max_bet_index: int


@dataclass(frozen=True, slots=True)
class HistoricalPrefixExactSuccessRate:
    numerator: int
    denominator: int
    available: bool


@dataclass(frozen=True, slots=True)
class HistoricalPrefixSuccessWindowSummary:
    window_kind: WindowKind
    window_role: WindowRole
    requested_draw_count: int | None
    source_draw_count: int
    eligible_draw_count: int
    excluded_draw_count: int
    success_count: int
    failure_count: int
    success_rate: HistoricalPrefixExactSuccessRate
    first_target: HistoricalPrefixSuccessDrawIdentity
    last_target: HistoricalPrefixSuccessDrawIdentity
    first_cutoff: HistoricalPrefixSuccessDrawIdentity
    last_cutoff: HistoricalPrefixSuccessDrawIdentity
    nested_windows_independent: bool
    evaluation_status: WindowEvaluationStatus
    evidence_status: EvidenceStatus


@dataclass(frozen=True, slots=True)
class HistoricalPrefixStrategySuccessWindowResult:
    strategy: HistoricalPrefixSuccessStrategyIdentity
    criterion: HistoricalPrefixSuccessCriterionIdentity
    prefix_count: int
    selection: HistoricalPrefixSuccessSelectionIdentity
    status: HistoricalPrefixSuccessEvaluationStatus
    source_observation_count: int
    windows: tuple[HistoricalPrefixSuccessWindowSummary, ...]


@dataclass(frozen=True, slots=True)
class HistoricalPrefixStrategySuccessWindowPage:
    metadata: HistoricalPrefixSuccessWindowSourceMetadata
    criterion: HistoricalPrefixSuccessCriterionIdentity
    prefix_count: int
    total_count: int
    limit: int
    offset: int
    items: tuple[HistoricalPrefixStrategySuccessWindowResult, ...]


__all__ = [
    "DEFAULT_PAGE_LIMIT",
    "DEFAULT_PAGE_OFFSET",
    "MAX_PAGE_LIMIT",
    "MIN_PAGE_LIMIT",
    "SUPPORTED_PREFIX_COUNTS",
    "HistoricalPrefixExactSuccessRate",
    "HistoricalPrefixStrategySuccessWindowPage",
    "HistoricalPrefixStrategySuccessWindowResult",
    "HistoricalPrefixSuccessCriterion",
    "HistoricalPrefixSuccessCriterionIdentity",
    "HistoricalPrefixSuccessDrawIdentity",
    "HistoricalPrefixSuccessEvaluationStatus",
    "HistoricalPrefixSuccessImportNotFoundError",
    "HistoricalPrefixSuccessSelectionIdentity",
    "HistoricalPrefixSuccessSourceObservation",
    "HistoricalPrefixSuccessSourceStrategy",
    "HistoricalPrefixSuccessStrategyIdentity",
    "HistoricalPrefixSuccessStrategyNotFoundError",
    "HistoricalPrefixSuccessTicketOutcome",
    "HistoricalPrefixSuccessWindowSource",
    "HistoricalPrefixSuccessWindowSourceMetadata",
    "HistoricalPrefixSuccessWindowSummary",
    "HistoricalPrefixSuccessWindowsContractError",
    "HistoricalPrefixSuccessWindowsError",
    "HistoricalPrefixSuccessWindowsUnavailableError",
]
