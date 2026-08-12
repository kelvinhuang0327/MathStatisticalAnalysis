"""Read-only contracts for sealed B649 Strategy-K and combination evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

B649_CANDIDATE_COVERAGE_DISCLAIMER = (
    "歷史候選覆蓋率與精確隨機基準僅描述封存歷史關係；"  # noqa: RUF001
    "不是官方獎項機率、合法彩券中獎率、未來成功率、預測優勢、推薦或保證。"
)
B649_COMBINATION_DISCLAIMER = (
    "組合排序只重現相同代理、成員數、歷史區間與成功標準下的封存歷史 Top 20；"  # noqa: RUF001
    "不重算上游研究、不代表未來優勢，也不是投注建議。"  # noqa: RUF001
)
B649_HISTORICAL_RANKING_LABEL = "Historical best under current filters"
B649_DETERMINISTIC_ORDER_LABEL = "Deterministic strategy ID order"
B649_SEALED_COMBINATION_ORDER_LABEL = "Sealed historical rank under current filters"


class B649StrategyKCriterion(StrEnum):
    M1_PLUS = "M1_PLUS"
    M2_PLUS = "M2_PLUS"
    M3_PLUS = "M3_PLUS"
    M4_PLUS = "M4_PLUS"
    M5_PLUS = "M5_PLUS"
    M6_PLUS = "M6_PLUS"
    SPECIAL_HIT = "SPECIAL_HIT"
    M2_PLUS_SPECIAL = "M2_PLUS_SPECIAL"
    M3_PLUS_SPECIAL = "M3_PLUS_SPECIAL"
    M4_PLUS_SPECIAL = "M4_PLUS_SPECIAL"
    M5_PLUS_SPECIAL = "M5_PLUS_SPECIAL"
    M6_PLUS_SPECIAL = "M6_PLUS_SPECIAL"


class B649CombinationCriterion(StrEnum):
    M1_PLUS = "M1_PLUS"
    M2_PLUS = "M2_PLUS"
    M3_PLUS = "M3_PLUS"
    M4_PLUS = "M4_PLUS"
    M5_PLUS = "M5_PLUS"
    M6 = "M6"
    SPECIAL_HIT = "SPECIAL_HIT"
    M1_PLUS_SPECIAL = "M1_PLUS_SPECIAL"
    M2_PLUS_SPECIAL = "M2_PLUS_SPECIAL"
    M3_PLUS_SPECIAL = "M3_PLUS_SPECIAL"
    M4_PLUS_SPECIAL = "M4_PLUS_SPECIAL"
    M5_PLUS_SPECIAL = "M5_PLUS_SPECIAL"


class B649StrategyKWindowKind(StrEnum):
    FULL_HISTORY = "FULL_HISTORY"
    LONG = "LONG"
    MEDIUM = "MEDIUM"
    SHORT = "SHORT"


class B649CombinationWindow(StrEnum):
    FULL = "FULL"
    LONG_750 = "LONG_750"
    MID_300 = "MID_300"
    SHORT_50 = "SHORT_50"


class B649WindowRole(StrEnum):
    PRIMARY_EVIDENCE = "PRIMARY_EVIDENCE"
    STABILITY_CONFIRMATION = "STABILITY_CONFIRMATION"
    DEGRADATION_VETO = "DEGRADATION_VETO"
    REFERENCE_ONLY = "REFERENCE_ONLY"


class B649StrategyAvailability(StrEnum):
    MATRIX_AVAILABLE = "MATRIX_AVAILABLE"
    PORTFOLIO_ORDER_AGGREGATION_NOT_DEFINED = "PORTFOLIO_ORDER_AGGREGATION_NOT_DEFINED"


class B649StrategyKSort(StrEnum):
    STRATEGY_ID_ASC = "STRATEGY_ID_ASC"
    OBSERVED_RATE_DESC = "OBSERVED_RATE_DESC"
    OBSERVED_MINUS_BASELINE_DESC = "OBSERVED_MINUS_BASELINE_DESC"


class B649CombinationProxyMode(StrEnum):
    A = "A"
    C = "C"


class B649CombinationSort(StrEnum):
    SEALED_RANK_ASC = "SEALED_RANK_ASC"
    COMBINATION_ID_ASC = "COMBINATION_ID_ASC"


@dataclass(frozen=True, slots=True)
class B649WindowOption:
    window_kind: str
    window_role: B649WindowRole
    requested_draw_count: int | None
    default_emphasis: bool


@dataclass(frozen=True, slots=True)
class B649StrategyAvailabilityRecord:
    strategy_id: str
    strategy_version: str
    availability: B649StrategyAvailability
    availability_reason: str
    response_shape: str
    native_ticket_count: int


@dataclass(frozen=True, slots=True)
class B649EffectiveUniqueKCount:
    effective_unique_k: int
    observation_count: int


@dataclass(frozen=True, slots=True)
class B649StrategyKRecord:
    strategy_id: str
    strategy_version: str
    requested_k: int
    effective_unique_k_counts: tuple[B649EffectiveUniqueKCount, ...]
    criterion: B649StrategyKCriterion
    window_kind: B649StrategyKWindowKind
    window_role: B649WindowRole
    requested_draw_count: int | None
    source_observation_count: int
    eligible_observation_count: int
    excluded_observation_count: int
    success_numerator: int
    success_denominator: int
    random_baseline_numerator: int
    random_baseline_denominator: int
    observed_minus_baseline: str
    first_target_draw: str
    last_target_draw: str
    evaluation_status: str
    measurement_mode: str
    window_policy_version: str
    nested_windows_independent: bool


@dataclass(frozen=True, slots=True)
class B649StrategyKSummary:
    authority_task_tree: str
    authority_full_output_tree: str
    matrix_row_count: int
    supported_k_values: tuple[int, ...]
    supported_criteria: tuple[B649StrategyKCriterion, ...]
    windows: tuple[B649WindowOption, ...]
    strategies: tuple[B649StrategyAvailabilityRecord, ...]
    current_executable_strategy_count: int
    matrix_available_strategy_count: int
    matrix_unavailable_strategy_count: int
    historical_accounted_identity_count: int
    measurement_mode: str
    window_policy_version: str
    duplicate_handling_policy: str
    nested_windows_independent: bool
    predictive_advantage_claimed: bool
    research_disclaimer: str = B649_CANDIDATE_COVERAGE_DISCLAIMER


@dataclass(frozen=True, slots=True)
class B649StrategyKDataset:
    summary: B649StrategyKSummary
    records: tuple[B649StrategyKRecord, ...]


@dataclass(frozen=True, slots=True)
class B649StrategyKQuery:
    requested_k: int
    window_kind: B649StrategyKWindowKind
    criterion: B649StrategyKCriterion
    q: str | None = None
    sort: B649StrategyKSort = B649StrategyKSort.STRATEGY_ID_ASC
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class B649StrategyKPage:
    items: tuple[B649StrategyKRecord, ...]
    total: int
    limit: int
    offset: int
    requested_k: int
    window_kind: B649StrategyKWindowKind
    window_role: B649WindowRole
    criterion: B649StrategyKCriterion
    sort: B649StrategyKSort
    ranking_label: str
    measurement_mode: str
    research_disclaimer: str = B649_CANDIDATE_COVERAGE_DISCLAIMER


@dataclass(frozen=True, slots=True)
class B649CombinationProxyOption:
    proxy_mode: B649CombinationProxyMode
    proxy_label: str


@dataclass(frozen=True, slots=True)
class B649CombinationRecord:
    proxy_mode: B649CombinationProxyMode
    proxy_label: str
    member_count: int
    member_strategy_ids: tuple[str, ...]
    combination_id: str
    evaluation_window: B649CombinationWindow
    criterion: B649CombinationCriterion
    sealed_rank: int
    eligible_draws: int
    success_numerator: int
    success_denominator: int
    observed_rate: str
    exact_random_baseline_numerator: int
    exact_random_baseline_denominator: int
    random_baseline_rate: str
    descriptive_delta: str
    evaluation_status: str
    evaluation_reason: str
    long_delta_sign: str | None
    mid_delta_sign: str | None
    short_delta_sign: str | None
    positive_window_count: int
    minimum_delta: str | None
    delta_range: str | None
    cross_window_stable_positive: bool
    historical_search_only: bool
    predictive_advantage_claimed: bool
    prospective_validation_required: bool
    candidate_disposition: str


@dataclass(frozen=True, slots=True)
class B649CombinationSummary:
    authority_task_tree: str
    sealed_top_candidate_count: int
    proxy_modes: tuple[B649CombinationProxyOption, ...]
    member_counts: tuple[int, ...]
    windows: tuple[B649WindowOption, ...]
    supported_criteria: tuple[B649CombinationCriterion, ...]
    source_scope: str
    full_projection_sent_to_browser: bool
    predictive_advantage_claimed: bool
    research_disclaimer: str = B649_COMBINATION_DISCLAIMER


@dataclass(frozen=True, slots=True)
class B649CombinationDataset:
    summary: B649CombinationSummary
    records: tuple[B649CombinationRecord, ...]


@dataclass(frozen=True, slots=True)
class B649CombinationQuery:
    proxy_mode: B649CombinationProxyMode
    member_count: int
    window: B649CombinationWindow
    criterion: B649CombinationCriterion
    member_search: str | None = None
    sort: B649CombinationSort = B649CombinationSort.SEALED_RANK_ASC
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class B649CombinationPage:
    items: tuple[B649CombinationRecord, ...]
    total: int
    limit: int
    offset: int
    proxy_mode: B649CombinationProxyMode
    member_count: int
    window: B649CombinationWindow
    window_role: B649WindowRole
    criterion: B649CombinationCriterion
    sort: B649CombinationSort
    ranking_label: str
    source_scope: str
    research_disclaimer: str = B649_COMBINATION_DISCLAIMER


@dataclass(frozen=True, slots=True)
class B649EvidenceStatus:
    observer_task_tree: str
    historical_evidence_status: str
    pre_freeze_date_unseen_holdout_count: int
    post_freeze_date_prospective_count: int
    observation_count: int
    observation_start_draw: str
    latest_observed_draw: str | None
    checkpoints: tuple[int, ...]
    checkpoints_reached: tuple[int, ...]
    primary_outcome: str
    c_forward_status: str
    c_forward_reason: str
    holdout_used_to_rerank_historical_results: bool
    predictive_advantage_claimed: bool


class B649AnalyticsAuthorityError(RuntimeError):
    """A sealed B649 authority is absent or violates its pinned contract."""


def query_b649_strategy_k(
    dataset: B649StrategyKDataset,
    query: B649StrategyKQuery,
) -> B649StrategyKPage:
    """Query one comparable Strategy-K cell set without changing its evidence."""

    summary = dataset.summary
    if query.requested_k not in summary.supported_k_values:
        raise ValueError("requested_k is outside the sealed authority range")
    if query.criterion not in summary.supported_criteria:
        raise ValueError("criterion is outside the sealed authority contract")
    window = next(
        (item for item in summary.windows if item.window_kind == query.window_kind.value),
        None,
    )
    if window is None:
        raise ValueError("window_kind is outside the sealed authority contract")

    search = query.q.casefold() if query.q is not None else None
    selected = [
        row
        for row in dataset.records
        if row.requested_k == query.requested_k
        and row.window_kind is query.window_kind
        and row.criterion is query.criterion
        and (search is None or search in row.strategy_id.casefold())
    ]
    if query.sort is B649StrategyKSort.STRATEGY_ID_ASC:
        selected.sort(key=lambda row: (row.strategy_id, row.strategy_version))
        ranking_label = B649_DETERMINISTIC_ORDER_LABEL
    elif query.sort is B649StrategyKSort.OBSERVED_RATE_DESC:
        selected.sort(
            key=lambda row: (
                -Fraction(row.success_numerator, row.success_denominator),
                row.strategy_id,
                row.strategy_version,
            )
        )
        ranking_label = B649_HISTORICAL_RANKING_LABEL
    else:
        selected.sort(
            key=lambda row: (
                -(
                    Fraction(row.success_numerator, row.success_denominator)
                    - Fraction(
                        row.random_baseline_numerator,
                        row.random_baseline_denominator,
                    )
                ),
                row.strategy_id,
                row.strategy_version,
            )
        )
        ranking_label = B649_HISTORICAL_RANKING_LABEL

    return B649StrategyKPage(
        items=tuple(selected[query.offset : query.offset + query.limit]),
        total=len(selected),
        limit=query.limit,
        offset=query.offset,
        requested_k=query.requested_k,
        window_kind=query.window_kind,
        window_role=window.window_role,
        criterion=query.criterion,
        sort=query.sort,
        ranking_label=ranking_label,
        measurement_mode=summary.measurement_mode,
    )


def query_b649_combinations(
    dataset: B649CombinationDataset,
    query: B649CombinationQuery,
) -> B649CombinationPage:
    """Page a sealed Top-20 pool; never recompute or rerank its research."""

    summary = dataset.summary
    if query.member_count not in summary.member_counts:
        raise ValueError("member_count is outside the sealed pair/triple scope")
    if query.criterion not in summary.supported_criteria:
        raise ValueError("criterion is outside the sealed authority contract")
    window = next(
        (item for item in summary.windows if item.window_kind == query.window.value),
        None,
    )
    if window is None:
        raise ValueError("window is outside the sealed authority contract")

    search = query.member_search.casefold() if query.member_search is not None else None
    selected = [
        row
        for row in dataset.records
        if row.proxy_mode is query.proxy_mode
        and row.member_count == query.member_count
        and row.evaluation_window is query.window
        and row.criterion is query.criterion
        and (
            search is None or any(search in member.casefold() for member in row.member_strategy_ids)
        )
    ]
    if query.sort is B649CombinationSort.SEALED_RANK_ASC:
        selected.sort(key=lambda row: (row.sealed_rank, row.combination_id))
        ranking_label = B649_SEALED_COMBINATION_ORDER_LABEL
    else:
        selected.sort(key=lambda row: (row.combination_id, row.sealed_rank))
        ranking_label = "Deterministic combination ID order"

    return B649CombinationPage(
        items=tuple(selected[query.offset : query.offset + query.limit]),
        total=len(selected),
        limit=query.limit,
        offset=query.offset,
        proxy_mode=query.proxy_mode,
        member_count=query.member_count,
        window=query.window,
        window_role=window.window_role,
        criterion=query.criterion,
        sort=query.sort,
        ranking_label=ranking_label,
        source_scope=summary.source_scope,
    )
