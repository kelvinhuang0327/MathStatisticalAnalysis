"""Read model and query for the canonical structural Matrix projection.

Scope is fixed at V1: the exact-combinatorial ``EXPECTED_MAX_MAIN_MATCHES_V1``
metric over the native uniform winning space, for exactly three lotteries,
the 14 canonical imported-optimizer Matrix methods, and five ticket counts.
This is a distinct authority family from historical success-rate or ranking
evidence and never claims either.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum, StrEnum

_SHA256 = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_DECIMAL = re.compile(r"^(?:0|[1-9][0-9]*)$", flags=re.ASCII)

SCHEMA_ID = "lottolab.strategy_matrix.structural"
SCHEMA_VERSION = "1.0.0"
SCOPE = "NATIVE_UNIFORM_WINNING_SPACE"
AUTHORITY_KIND = "CANONICAL_PACKAGED_MATRIX"
METRIC_ID = "EXPECTED_MAX_MAIN_MATCHES_V1"
METRIC_DEFINITION = "E[max_t |t intersection D|]"
METRIC_UNIT = "MAIN_MATCHES"
METRIC_DRAW_DISTRIBUTION = "LEGAL_UNIFORM_MAIN_DRAW"
METRIC_EXACTNESS = "EXACT_COMBINATORIAL_EXPECTATION"


class StructuralLottery(StrEnum):
    BIG_LOTTO = "BIG_LOTTO"
    DAILY_539 = "DAILY_539"
    POWER_LOTTO_ZONE1 = "POWER_LOTTO_ZONE1"


class StructuralCaseId(StrEnum):
    NATIVE_BIG_LOTTO = "NATIVE_BIG_LOTTO"
    NATIVE_DAILY_539 = "NATIVE_DAILY_539"
    NATIVE_POWER_LOTTO_ZONE1 = "NATIVE_POWER_LOTTO_ZONE1"


STRUCTURAL_CASE_ID_BY_LOTTERY: Mapping[StructuralLottery, StructuralCaseId] = {
    StructuralLottery.BIG_LOTTO: StructuralCaseId.NATIVE_BIG_LOTTO,
    StructuralLottery.DAILY_539: StructuralCaseId.NATIVE_DAILY_539,
    StructuralLottery.POWER_LOTTO_ZONE1: StructuralCaseId.NATIVE_POWER_LOTTO_ZONE1,
}
STRUCTURAL_LOTTERY_BY_CASE_ID: Mapping[StructuralCaseId, StructuralLottery] = {
    case_id: lottery for lottery, case_id in STRUCTURAL_CASE_ID_BY_LOTTERY.items()
}


class StructuralTicketCount(IntEnum):
    TWO = 2
    THREE = 3
    FIVE = 5
    TEN = 10
    TWENTY = 20


STRUCTURAL_TICKET_COUNTS: tuple[StructuralTicketCount, ...] = (
    StructuralTicketCount.TWO,
    StructuralTicketCount.THREE,
    StructuralTicketCount.FIVE,
    StructuralTicketCount.TEN,
    StructuralTicketCount.TWENTY,
)


class StructuralMethodId(StrEnum):
    """The exact 14 canonical Matrix methods from the pinned research ledger's
    ``imported_optimizer_matrix.methods[*].strategy_id``."""

    CYCLIC_SIDON_SHIFT_V1 = "CYCLIC_SIDON_SHIFT_V1"
    GREEDY_MIN_OVERLAP_V1 = "GREEDY_MIN_OVERLAP_V1"
    GREEDY_MINMAX_THEN_SUM_OVERLAP_V1 = "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1"
    GREEDY_MINMAX_SUM_THEN_REUSE_DISPERSION_V1 = "GREEDY_MINMAX_SUM_THEN_REUSE_DISPERSION_V1"
    CANDIDATE_LOW_OVERLAP_V1 = "CANDIDATE_LOW_OVERLAP_V1"
    RESTART_GREEDY_SWAP_COVERAGE_SEARCH_V1 = "RESTART_GREEDY_SWAP_COVERAGE_SEARCH_V1"
    REFERENCE_E_BEST_1EXCHANGE_EXACT_COVERAGE_V1 = "REFERENCE_E_BEST_1EXCHANGE_EXACT_COVERAGE_V1"
    ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1 = "ITERATIVE_EXACT_1EXCHANGE_REFINEMENT_V1"
    B649_CANDIDATE_SET_LOW_OVERLAP_V1 = "B649_CANDIDATE_SET_LOW_OVERLAP_V1"
    B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1 = "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1"
    B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1 = "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1"
    HARD_DIV_PAIRWISE_OVERLAP_R1 = "HARD_DIV_PAIRWISE_OVERLAP_R1"
    HARD_DIV_PAIRWISE_OVERLAP_R2 = "HARD_DIV_PAIRWISE_OVERLAP_R2"
    ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1 = "ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1"


STRUCTURAL_METHOD_IDS: tuple[StructuralMethodId, ...] = tuple(StructuralMethodId)
assert len(STRUCTURAL_METHOD_IDS) == 14

K20_EXACT_ASCENT_METHOD_ID = StructuralMethodId.ITERATIVE_EXACT_1EXCHANGE_EXPECTED_MAX_V1


class StructuralSourceStatus(StrEnum):
    MEASURED = "MEASURED"
    REUSED_VERIFIED = "REUSED_VERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_RUN = "NOT_RUN"


class StructuralMeasurementStatus(StrEnum):
    MEASURED = "MEASURED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNAVAILABLE = "UNAVAILABLE"


class StrategyMatrixStructuralContractError(ValueError):
    """A structural Matrix read-model value violates its closed contract."""


@dataclass(frozen=True, slots=True)
class StructuralMatrixValue:
    numerator: str
    denominator: str

    def __post_init__(self) -> None:
        if not _DECIMAL.fullmatch(self.numerator):
            raise StrategyMatrixStructuralContractError(
                "value numerator must be a decimal integer string"
            )
        if not _DECIMAL.fullmatch(self.denominator) or self.denominator == "0":
            raise StrategyMatrixStructuralContractError(
                "value denominator must be a positive decimal integer string"
            )


@dataclass(frozen=True, slots=True)
class SourceReference:
    repository_path: str
    file_sha256: str

    def __post_init__(self) -> None:
        if not self.repository_path:
            raise StrategyMatrixStructuralContractError("source reference path must be non-empty")
        if not _SHA256.fullmatch(self.file_sha256):
            raise StrategyMatrixStructuralContractError("source reference sha256 is malformed")


@dataclass(frozen=True, slots=True)
class StructuralMatrixAuthoritySources:
    metric_surface: SourceReference
    matrix: SourceReference
    ledger: SourceReference


@dataclass(frozen=True, slots=True)
class StructuralMatrixAuthority:
    kind: str
    source_head: str
    source_tree: str
    sources: StructuralMatrixAuthoritySources

    def __post_init__(self) -> None:
        if self.kind != AUTHORITY_KIND:
            raise StrategyMatrixStructuralContractError(
                "authority kind is not CANONICAL_PACKAGED_MATRIX"
            )
        if not re.fullmatch(r"[0-9a-f]{40}", self.source_head):
            raise StrategyMatrixStructuralContractError(
                "authority source_head is not a full Git SHA-1"
            )
        if not re.fullmatch(r"[0-9a-f]{40}", self.source_tree):
            raise StrategyMatrixStructuralContractError(
                "authority source_tree is not a full Git SHA-1"
            )


@dataclass(frozen=True, slots=True)
class StructuralMatrixMetric:
    metric_id: str
    definition: str
    unit: str
    draw_distribution: str
    exactness: str


@dataclass(frozen=True, slots=True)
class StructuralMatrixClaimBoundary:
    historical_outcomes_used: bool
    historical_success_rate_claimed: bool
    ranking_score_claimed: bool
    global_optimum_claimed: bool
    cross_lottery_normalization: str


_VALID_STATUS_PAIRS: frozenset[tuple[StructuralSourceStatus, StructuralMeasurementStatus]] = (
    frozenset(
        {
            (StructuralSourceStatus.MEASURED, StructuralMeasurementStatus.MEASURED),
            (StructuralSourceStatus.REUSED_VERIFIED, StructuralMeasurementStatus.MEASURED),
            (StructuralSourceStatus.REUSED_VERIFIED, StructuralMeasurementStatus.UNAVAILABLE),
            (StructuralSourceStatus.NOT_APPLICABLE, StructuralMeasurementStatus.NOT_APPLICABLE),
            (StructuralSourceStatus.NOT_RUN, StructuralMeasurementStatus.UNAVAILABLE),
        }
    )
)


@dataclass(frozen=True, slots=True)
class StructuralMatrixCell:
    row_id: str
    case_id: StructuralCaseId
    lottery: StructuralLottery
    method_id: StructuralMethodId
    ticket_count: StructuralTicketCount
    method_objective: str
    source_status: StructuralSourceStatus
    measurement_status: StructuralMeasurementStatus
    value: StructuralMatrixValue | None
    portfolio_sha256: str | None
    unavailable_reason: str | None
    local_optimum_status: str | None

    def __post_init__(self) -> None:
        if not self.row_id:
            raise StrategyMatrixStructuralContractError("cell row_id must be non-empty")
        if STRUCTURAL_LOTTERY_BY_CASE_ID[self.case_id] is not self.lottery:
            raise StrategyMatrixStructuralContractError(
                "cell case_id and lottery do not correspond"
            )
        if not self.method_objective:
            raise StrategyMatrixStructuralContractError("cell method_objective must be non-empty")
        if (self.source_status, self.measurement_status) not in _VALID_STATUS_PAIRS:
            raise StrategyMatrixStructuralContractError(
                f"cell {self.row_id} has an invalid source/measurement status pair: "
                f"{self.source_status}/{self.measurement_status}"
            )
        if self.measurement_status is StructuralMeasurementStatus.MEASURED:
            if self.value is None:
                raise StrategyMatrixStructuralContractError(
                    f"cell {self.row_id} is MEASURED without a value"
                )
            if self.portfolio_sha256 is None or not _SHA256.fullmatch(self.portfolio_sha256):
                raise StrategyMatrixStructuralContractError(
                    f"cell {self.row_id} is MEASURED without a valid portfolio_sha256"
                )
            if self.unavailable_reason is not None:
                raise StrategyMatrixStructuralContractError(
                    f"cell {self.row_id} is MEASURED but carries an unavailable_reason"
                )
        else:
            if self.value is not None:
                raise StrategyMatrixStructuralContractError(
                    f"cell {self.row_id} is unmeasured but carries a value"
                )
            if self.portfolio_sha256 is not None:
                raise StrategyMatrixStructuralContractError(
                    f"cell {self.row_id} is unmeasured but carries a portfolio_sha256"
                )
            if not self.unavailable_reason:
                raise StrategyMatrixStructuralContractError(
                    f"cell {self.row_id} is unmeasured without an unavailable_reason"
                )
            if self.local_optimum_status is not None:
                raise StrategyMatrixStructuralContractError(
                    f"cell {self.row_id} is unmeasured but carries a local_optimum_status"
                )


@dataclass(frozen=True, slots=True)
class StrategyMatrixStructuralDataset:
    schema_id: str
    schema_version: str
    projection_sha256: str
    authority: StructuralMatrixAuthority
    scope: str
    supported_ticket_counts: tuple[int, ...]
    metric: StructuralMatrixMetric
    claim_boundary: StructuralMatrixClaimBoundary
    cells: tuple[StructuralMatrixCell, ...]

    def __post_init__(self) -> None:
        if self.schema_id != SCHEMA_ID:
            raise StrategyMatrixStructuralContractError(
                "dataset schema_id does not match the pinned contract"
            )
        if self.schema_version != SCHEMA_VERSION:
            raise StrategyMatrixStructuralContractError(
                "dataset schema_version does not match the pinned contract"
            )
        if not _SHA256.fullmatch(self.projection_sha256):
            raise StrategyMatrixStructuralContractError("dataset projection_sha256 is malformed")
        if self.scope != SCOPE:
            raise StrategyMatrixStructuralContractError(
                "dataset scope does not match the pinned contract"
            )
        if self.supported_ticket_counts != tuple(int(count) for count in STRUCTURAL_TICKET_COUNTS):
            raise StrategyMatrixStructuralContractError(
                "dataset supported_ticket_counts does not match V1"
            )
        row_ids = [cell.row_id for cell in self.cells]
        if len(set(row_ids)) != len(row_ids):
            raise StrategyMatrixStructuralContractError("dataset contains a duplicate cell row_id")


PINNED_SOURCE_HEAD = "c6b03e2b6eb7219a35d619607897cc6969e95fce"
PINNED_SOURCE_TREE = "0b0b6079e37257273ef41fe333b3c98fa11f1864"

PINNED_METRIC_SURFACE = SourceReference(
    repository_path="docs/research/matrix-native-results/expected-max-main-matches-v1-result.json",
    file_sha256="2672c958d009cf7e3c09f54d30c1c536c92165ade54af85ce5cfb38a9f977c85",
)
PINNED_MATRIX = SourceReference(
    repository_path="docs/research/matrix-native-results/imported-optimizer-integration-r1-result.json",
    file_sha256="ca94489292a666e4521698d7b21314c7faca6e0881c82deb093bd21b344d88a0",
)
PINNED_LEDGER = SourceReference(
    repository_path="docs/research/cross_lottery_research_ledger_r1.json",
    file_sha256="2b8e70c1f5cae670b9f8b01373906b8ed545dd04e87e51a020abeb90e20fe63a",
)
PINNED_AUTHORITY_SOURCES = StructuralMatrixAuthoritySources(
    metric_surface=PINNED_METRIC_SURFACE,
    matrix=PINNED_MATRIX,
    ledger=PINNED_LEDGER,
)
PINNED_AUTHORITY = StructuralMatrixAuthority(
    kind=AUTHORITY_KIND,
    source_head=PINNED_SOURCE_HEAD,
    source_tree=PINNED_SOURCE_TREE,
    sources=PINNED_AUTHORITY_SOURCES,
)
PINNED_CLAIM_BOUNDARY = StructuralMatrixClaimBoundary(
    historical_outcomes_used=False,
    historical_success_rate_claimed=False,
    ranking_score_claimed=False,
    global_optimum_claimed=False,
    cross_lottery_normalization="NOT_PERFORMED",
)
PINNED_METRIC = StructuralMatrixMetric(
    metric_id=METRIC_ID,
    definition=METRIC_DEFINITION,
    unit=METRIC_UNIT,
    draw_distribution=METRIC_DRAW_DISTRIBUTION,
    exactness=METRIC_EXACTNESS,
)

STRUCTURAL_LOTTERY_DRAW_SIZE: Mapping[StructuralLottery, int] = {
    StructuralLottery.BIG_LOTTO: 6,
    StructuralLottery.DAILY_539: 5,
    StructuralLottery.POWER_LOTTO_ZONE1: 6,
}

K20_EXACT_ASCENT_LOTTERY = StructuralLottery.BIG_LOTTO
K20_EXACT_ASCENT_TICKET_COUNT = StructuralTicketCount.TWENTY
K20_EXACT_ASCENT_VALUE = StructuralMatrixValue(numerator="8249099", denominator="3495954")

EXPECTED_CELL_COUNT = (
    len(StructuralLottery) * len(STRUCTURAL_METHOD_IDS) * len(STRUCTURAL_TICKET_COUNTS)
)
assert EXPECTED_CELL_COUNT == 210


@dataclass(frozen=True, slots=True)
class StrategyMatrixStructuralQuery:
    lottery: StructuralLottery | None = None
    method_id: StructuralMethodId | None = None
    ticket_count: StructuralTicketCount | None = None


def query_strategy_matrix_structural(
    dataset: StrategyMatrixStructuralDataset, query: StrategyMatrixStructuralQuery
) -> StrategyMatrixStructuralDataset:
    """Filter a dataset's cells; ``projection_sha256`` always identifies the complete snapshot."""

    def matches(cell: StructuralMatrixCell) -> bool:
        return (
            (query.lottery is None or cell.lottery is query.lottery)
            and (query.method_id is None or cell.method_id is query.method_id)
            and (query.ticket_count is None or cell.ticket_count is query.ticket_count)
        )

    filtered = tuple(cell for cell in dataset.cells if matches(cell))
    return StrategyMatrixStructuralDataset(
        schema_id=dataset.schema_id,
        schema_version=dataset.schema_version,
        projection_sha256=dataset.projection_sha256,
        authority=dataset.authority,
        scope=dataset.scope,
        supported_ticket_counts=dataset.supported_ticket_counts,
        metric=dataset.metric,
        claim_boundary=dataset.claim_boundary,
        cells=filtered,
    )
