"""Use case: query canonical strategy metadata without data-path or DB access.

Text search is a Unicode-casefolded substring match over strategy ID and display
name. All supplied filters are combined with AND semantics, and matching items
retain descriptor declaration order.
"""

from __future__ import annotations

from lottolab.application.dto import (
    StrategyOverviewCapabilities,
    StrategyOverviewItem,
    StrategyOverviewResponse,
    StrategyOverviewSummary,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.strategies.catalog import StrategyCatalog

MAX_STRATEGY_SEARCH_LENGTH = 100


class QueryStrategyOverview:
    def __init__(self, catalog: StrategyCatalog) -> None:
        self._catalog = catalog

    def execute(
        self,
        *,
        q: str | None = None,
        lottery_type: LotteryType | None = None,
        lifecycle_status: LifecycleStatus | None = None,
        executable: bool | None = None,
    ) -> StrategyOverviewResponse:
        normalized_query = self._normalize_query(q)
        candidates = self._catalog.list(
            lottery_type=lottery_type,
            lifecycle_status=lifecycle_status,
        )
        matches = tuple(
            descriptor
            for descriptor in candidates
            if self._matches_text(descriptor, normalized_query)
            and (executable is None or descriptor.executable is executable)
        )

        lifecycle_counts = {status: 0 for status in LifecycleStatus}
        lottery_type_counts = {kind: 0 for kind in LotteryType}
        executable_count = 0
        for descriptor in matches:
            lifecycle_counts[descriptor.lifecycle_status] += 1
            executable_count += int(descriptor.executable)
            for kind in descriptor.lottery_types:
                lottery_type_counts[kind] += 1

        return StrategyOverviewResponse(
            items=tuple(StrategyOverviewItem.from_descriptor(item) for item in matches),
            summary=StrategyOverviewSummary(
                total=len(matches),
                executable_count=executable_count,
                metadata_only_count=len(matches) - executable_count,
                lifecycle_counts=lifecycle_counts,
                lottery_type_counts=lottery_type_counts,
            ),
            capabilities=StrategyOverviewCapabilities(
                evaluation_metrics_available=False,
                d3_status_available=False,
                best_strategy_ranking_available=False,
                unavailable_reason_codes=(
                    "NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE",
                ),
            ),
        )

    @staticmethod
    def _normalize_query(query: str | None) -> str | None:
        if query is None:
            return None
        trimmed = query.strip()
        if not trimmed:
            raise ValueError("q must not be blank")
        if len(trimmed) > MAX_STRATEGY_SEARCH_LENGTH:
            raise ValueError(
                f"q must contain at most {MAX_STRATEGY_SEARCH_LENGTH} characters"
            )
        return trimmed.casefold()

    @staticmethod
    def _matches_text(
        descriptor: StrategyDescriptor,
        normalized_query: str | None,
    ) -> bool:
        if normalized_query is None:
            return True
        return (
            normalized_query in descriptor.strategy_id.casefold()
            or normalized_query in descriptor.strategy_name.casefold()
        )
