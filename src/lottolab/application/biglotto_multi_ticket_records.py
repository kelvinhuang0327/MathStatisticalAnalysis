"""Read-only application contract for pinned B649 multi-ticket history."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lottolab.domain.biglotto_full_strategy_catalog import ReproductionStatus

B649_RESEARCH_DISCLAIMER_ZH_TW = (
    "歷史成功率、排名與隨機基準差異僅供描述性研究，"  # noqa: RUF001
    "不構成未來預測、推薦、上線決策或中獎保證。"
)
B649_PREFIX_COUNTS = (5, 10, 15, 20)

B649_METRICS_UNAVAILABLE_STRATEGY_IDS = frozenset(
    {
        # replay_batch_exact2: pinned replay reproduction over a narrow,
        # non-causal-ordered draw window (1,500 / 1,550 executions each,
        # not the full 2,149-draw causal history every other BACKTESTED
        # strategy uses), so rolling 5/10/15/20-window metrics cannot be
        # computed under the same methodology. Owner-approved exception;
        # never regenerate, never expand this set.
        "legacy_biglotto__backtest_biglotto_5bet_ts3markov__25760472baa0",
        "legacy_biglotto__predict_biglotto_triple_strike__236fe529c01f",
    }
)
B649_METRICS_UNAVAILABLE_REASON = "FROZEN_PREDICTION_OUTPUT_AND_PRODUCER_UNAVAILABLE"
B649_AUTHORITY_MODE_HISTORICAL_SEALED = "HISTORICAL_SEALED_EVIDENCE_V1"
B649_AUTHORITY_MODE_FRESH_REPRODUCTION = "FRESH_CURRENT_CATALOG_REPRODUCTION_V1"


class B649HistoryWindow(StrEnum):
    FULL = "FULL"
    RECENT_750 = "RECENT_750"
    RECENT_300 = "RECENT_300"
    RECENT_50 = "RECENT_50"


class B649SuccessCriterion(StrEnum):
    M3_PLUS = "M3_PLUS"
    M4_PLUS = "M4_PLUS"
    M5_PLUS = "M5_PLUS"
    M6 = "M6"
    M2_PLUS_SPECIAL = "M2_PLUS_SPECIAL"
    M3_PLUS_SPECIAL = "M3_PLUS_SPECIAL"
    M4_PLUS_SPECIAL = "M4_PLUS_SPECIAL"
    M5_PLUS_SPECIAL = "M5_PLUS_SPECIAL"


B649_HISTORY_WINDOWS = tuple(B649HistoryWindow)
B649_SUCCESS_CRITERIA = tuple(B649SuccessCriterion)
B649_REPRODUCTION_STATUSES = (
    ReproductionStatus.BACKTESTED,
    ReproductionStatus.CLOSED_UNEXECUTABLE,
    ReproductionStatus.DUPLICATE_ALIAS,
)


@dataclass(frozen=True, slots=True)
class B649OfficialPrizeCounts:
    first: int
    second: int
    third: int
    fourth: int
    fifth: int
    sixth: int
    seventh: int
    general: int


@dataclass(frozen=True, slots=True)
class B649MultiTicketRecord:
    strategy_id: str
    strategy_version: str
    legacy_method_id: str
    source_path: str
    method_family: str
    reproduction_status: ReproductionStatus
    duplicate_alias_target: str | None
    prefix_count: int
    window: B649HistoryWindow
    criterion: B649SuccessCriterion
    rank: int | None
    official_rank: int | None
    official_any_prize_count: int | None
    official_any_prize_rate: str | None
    official_random_baseline_probability: str | None
    official_random_baseline_delta: str | None
    unranked_reason: str | None
    success_count: int | None
    effective_backtest_draw_count: int | None
    successful_execution_count: int | None
    historical_success_rate: str | None
    random_baseline_success_rate: str | None
    random_baseline_rate_difference: str | None
    coverage: str | None
    window_available_draws: int | None
    window_requested_draws: int | None
    window_complete: bool | None
    official_prize_counts: B649OfficialPrizeCounts | None
    no_prize_count: int | None
    report_sha256: str | None
    report_file_sha256: str | None
    catalog_sha256: str
    authority_mode: str | None
    metrics_unavailable_reason: str | None


@dataclass(frozen=True, slots=True)
class B649MultiTicketRecordDataset:
    records: tuple[B649MultiTicketRecord, ...]
    catalog_sha256: str
    projection_sha256: str
    source_report_count: int
    metrics_available_strategy_count: int
    metrics_unavailable_strategy_count: int


@dataclass(frozen=True, slots=True)
class B649MultiTicketRecordQuery:
    prefix_count: int
    window: B649HistoryWindow
    criterion: B649SuccessCriterion
    q: str | None = None
    method_family: str | None = None
    reproduction_status: ReproductionStatus | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class B649MultiTicketRecordPage:
    items: tuple[B649MultiTicketRecord, ...]
    total: int
    limit: int
    offset: int


def query_b649_multi_ticket_records(
    dataset: B649MultiTicketRecordDataset,
    query: B649MultiTicketRecordQuery,
) -> B649MultiTicketRecordPage:
    """Filter one already-validated immutable projection without ranking it."""

    if query.prefix_count not in B649_PREFIX_COUNTS:
        raise ValueError("prefix_count is outside the closed set")

    search = query.q.casefold() if query.q is not None else None
    selected = [
        row
        for row in dataset.records
        if row.prefix_count == query.prefix_count
        and row.window is query.window
        and row.criterion is query.criterion
        and (
            search is None
            or search in row.strategy_id.casefold()
            or search in row.legacy_method_id.casefold()
            or search in row.source_path.casefold()
        )
        and (query.method_family is None or row.method_family == query.method_family)
        and (
            query.reproduction_status is None
            or row.reproduction_status is query.reproduction_status
        )
    ]
    selected.sort(key=lambda row: row.strategy_id)
    return B649MultiTicketRecordPage(
        items=tuple(selected[query.offset : query.offset + query.limit]),
        total=len(selected),
        limit=query.limit,
        offset=query.offset,
    )


B649_EXACT_NATIVE_TICKET_COUNTS = (2, 3)


@dataclass(frozen=True, slots=True)
class B649ExactNativeRecord:
    strategy_id: str
    strategy_version: str
    legacy_method_id: str
    source_path: str
    method_family: str
    reproduction_status: ReproductionStatus
    duplicate_alias_target: str | None
    ticket_count: int
    window: B649HistoryWindow
    criterion: str
    metric_status: str
    rankable: bool
    unavailable_reason: str | None
    metrics_unavailable_reason: str | None
    unranked_reason: str | None
    official_any_prize_count: int | None
    official_any_prize_rate: str | None
    official_random_baseline_probability: str | None
    official_random_baseline_delta: str | None
    coverage: str | None
    official_prize_counts: B649OfficialPrizeCounts | None
    no_prize_count: int | None
    available_observation_count: int | None
    effective_backtest_draw_count: int | None
    successful_observation_count: int | None
    ticket_position_count: int | None
    observed_distinct_ticket_count: int | None
    observed_duplicate_ticket_count: int | None
    native_ticket_count_classification: str | None
    native_ticket_count_distribution: dict[str, int] | None
    execution_status_counts: dict[str, int] | None
    window_available_draws: int | None
    window_requested_draws: int | None
    window_complete: bool | None
    authority_mode: str | None
    input_canonical_sha256: str | None
    input_raw_sha256: str | None
    catalog_sha256: str
    official_rank: None = None


@dataclass(frozen=True, slots=True)
class B649ExactNativeRecordDataset:
    records: tuple[B649ExactNativeRecord, ...]
    catalog_sha256: str
    projection_sha256: str
    available_strategy_count_by_exact_ticket_count: dict[str, int]


@dataclass(frozen=True, slots=True)
class B649ExactNativeRecordQuery:
    ticket_count: int
    window: B649HistoryWindow
    q: str | None = None
    method_family: str | None = None
    reproduction_status: ReproductionStatus | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class B649ExactNativeRecordPage:
    items: tuple[B649ExactNativeRecord, ...]
    total: int
    limit: int
    offset: int


def query_b649_exact_native_records(
    dataset: B649ExactNativeRecordDataset,
    query: B649ExactNativeRecordQuery,
) -> B649ExactNativeRecordPage:
    """Filter exact-native projection without ranking it; order by strategy_id ASC."""

    if query.ticket_count not in B649_EXACT_NATIVE_TICKET_COUNTS:
        raise ValueError("ticket_count is outside the exact-native closed set (2, 3)")

    search = query.q.casefold() if query.q is not None else None
    selected = [
        row
        for row in dataset.records
        if row.ticket_count == query.ticket_count
        and row.window is query.window
        and (
            search is None
            or search in row.strategy_id.casefold()
            or search in row.legacy_method_id.casefold()
            or search in row.source_path.casefold()
        )
        and (query.method_family is None or row.method_family == query.method_family)
        and (
            query.reproduction_status is None
            or row.reproduction_status is query.reproduction_status
        )
    ]
    selected.sort(key=lambda row: row.strategy_id)
    return B649ExactNativeRecordPage(
        items=tuple(selected[query.offset : query.offset + query.limit]),
        total=len(selected),
        limit=query.limit,
        offset=query.offset,
    )


__all__ = [
    "B649_AUTHORITY_MODE_FRESH_REPRODUCTION",
    "B649_AUTHORITY_MODE_HISTORICAL_SEALED",
    "B649_EXACT_NATIVE_TICKET_COUNTS",
    "B649_HISTORY_WINDOWS",
    "B649_METRICS_UNAVAILABLE_REASON",
    "B649_METRICS_UNAVAILABLE_STRATEGY_IDS",
    "B649_PREFIX_COUNTS",
    "B649_REPRODUCTION_STATUSES",
    "B649_RESEARCH_DISCLAIMER_ZH_TW",
    "B649_SUCCESS_CRITERIA",
    "B649ExactNativeRecord",
    "B649ExactNativeRecordDataset",
    "B649ExactNativeRecordPage",
    "B649ExactNativeRecordQuery",
    "B649HistoryWindow",
    "B649MultiTicketRecord",
    "B649MultiTicketRecordDataset",
    "B649MultiTicketRecordPage",
    "B649MultiTicketRecordQuery",
    "B649OfficialPrizeCounts",
    "B649SuccessCriterion",
    "query_b649_exact_native_records",
    "query_b649_multi_ticket_records",
]
