from __future__ import annotations

import pytest
from tests.fixtures.historical.prefix_analytics_builder import build_run_import

from lottolab.application.use_cases.analyze_historical_prefixes import AnalyzeHistoricalPrefixes
from lottolab.domain.historical_prefix_analytics import (
    HistoricalPrefixAnalyticsInputError,
    analyze_historical_prefixes,
)


def test_use_case_is_a_thin_deterministic_domain_delegation() -> None:
    run_import = build_run_import()
    assert AnalyzeHistoricalPrefixes().execute(run_import) == analyze_historical_prefixes(
        run_import
    )


def test_use_case_preserves_typed_domain_input_errors() -> None:
    with pytest.raises(HistoricalPrefixAnalyticsInputError):
        AnalyzeHistoricalPrefixes().execute(build_run_import(), prefix_counts=(6,))
