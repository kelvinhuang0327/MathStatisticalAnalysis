"""Thin application entry point for pure historical-prefix analytics."""

from __future__ import annotations

from collections.abc import Iterable

from lottolab.domain.historical_prefix_analytics import (
    SUPPORTED_PREFIX_COUNTS,
    HistoricalPrefixAnalyticsResult,
    analyze_historical_prefixes,
)
from lottolab.domain.historical_results import HistoricalRunImport


class AnalyzeHistoricalPrefixes:
    """Analyze one already-validated import without repositories or runtime state."""

    def execute(
        self,
        run_import: HistoricalRunImport,
        *,
        prefix_counts: Iterable[int] = SUPPORTED_PREFIX_COUNTS,
    ) -> HistoricalPrefixAnalyticsResult:
        return analyze_historical_prefixes(run_import, prefix_counts=prefix_counts)


__all__ = ["AnalyzeHistoricalPrefixes"]
