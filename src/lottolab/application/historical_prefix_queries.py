"""Immutable application read models for historical-prefix analytics queries.

The models deliberately retain the frozen domain candidates, summaries, and
per-draw metrics.  They add only query metadata, slicing, and pagination; no
ranking or metric is recomputed here.
"""

from __future__ import annotations

from dataclasses import dataclass

from lottolab.domain.historical_prefix_analytics import (
    HistoricalPerDrawPrefixMetrics,
    HistoricalPrefixRankingCandidate,
    HistoricalPrefixRankingStatus,
    HistoricalStrategyPrefixSummary,
)

DEFAULT_TOP_K = 5
MIN_TOP_K = 1
MAX_TOP_K = 100
DEFAULT_PAGE_LIMIT = 50
MIN_PAGE_LIMIT = 1
MAX_PAGE_LIMIT = 200
DEFAULT_PAGE_OFFSET = 0
OVERVIEW_PREFIX_COUNTS = (10, 15, 20)


class HistoricalPrefixQueryContractError(ValueError):
    """A caller parameter or supplied analytics result violates the query contract."""


@dataclass(frozen=True, slots=True)
class HistoricalPrefixQueryMetadata:
    result_schema_version: str
    source_import_identity_sha256: str
    source_manifest_sha256: str
    source_artifact_sha256: str
    dataset_identity: str
    dataset_sha256: str
    lottery_type: str
    ranking_policy_id: str
    historical_only_disclaimer_id: str


@dataclass(frozen=True, slots=True)
class HistoricalPrefixStrategyKey:
    strategy_id: str
    strategy_version: str
    replicate: int

    def __post_init__(self) -> None:
        for field_name, value in (
            ("strategy_id", self.strategy_id),
            ("strategy_version", self.strategy_version),
        ):
            if type(value) is not str or not value or value != value.strip():
                raise HistoricalPrefixQueryContractError(
                    f"{field_name} must be a non-empty canonical string"
                )
        if type(self.replicate) is not int or self.replicate < 1:
            raise HistoricalPrefixQueryContractError("replicate must be an integer >= 1")


@dataclass(frozen=True, slots=True)
class HistoricalPrefixRankingGroupSlice:
    prefix_count: int
    status: HistoricalPrefixRankingStatus
    total_candidate_count: int
    requested_top_k: int
    candidates: tuple[HistoricalPrefixRankingCandidate, ...]


HistoricalPrefixBestRankingGroup = HistoricalPrefixRankingGroupSlice


@dataclass(frozen=True, slots=True)
class HistoricalPrefixBestRankings:
    metadata: HistoricalPrefixQueryMetadata
    top_k: int
    groups: tuple[HistoricalPrefixRankingGroupSlice, ...]


@dataclass(frozen=True, slots=True)
class HistoricalPrefixStrategyOverview:
    metadata: HistoricalPrefixQueryMetadata
    prefix_count: int
    summaries: tuple[HistoricalStrategyPrefixSummary, ...]
    total_count: int


@dataclass(frozen=True, slots=True)
class HistoricalPrefixReplayPage:
    metadata: HistoricalPrefixQueryMetadata
    strategy: HistoricalPrefixStrategyKey
    prefix_count: int
    items: tuple[HistoricalPerDrawPrefixMetrics, ...]
    total_count: int
    limit: int
    offset: int


__all__ = [
    "DEFAULT_PAGE_LIMIT",
    "DEFAULT_PAGE_OFFSET",
    "DEFAULT_TOP_K",
    "MAX_PAGE_LIMIT",
    "MAX_TOP_K",
    "MIN_PAGE_LIMIT",
    "MIN_TOP_K",
    "OVERVIEW_PREFIX_COUNTS",
    "HistoricalPrefixBestRankingGroup",
    "HistoricalPrefixBestRankings",
    "HistoricalPrefixQueryContractError",
    "HistoricalPrefixQueryMetadata",
    "HistoricalPrefixRankingGroupSlice",
    "HistoricalPrefixReplayPage",
    "HistoricalPrefixStrategyKey",
    "HistoricalPrefixStrategyOverview",
]
