from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from tests.fixtures.historical.prefix_analytics_builder import build_run_import

from lottolab.application.historical_prefix_queries import (
    HistoricalPrefixQueryContractError,
    HistoricalPrefixStrategyKey,
)
from lottolab.application.use_cases.query_historical_prefix_analytics import (
    GetHistoricalPrefixBestRankings,
)
from lottolab.domain.historical_prefix_analytics import analyze_historical_prefixes


@pytest.mark.parametrize(
    ("strategy_id", "strategy_version", "replicate"),
    [
        ("", "v1", 1),
        (" strategy", "v1", 1),
        ("strategy ", "v1", 1),
        ("strategy", "", 1),
        ("strategy", " v1", 1),
        ("strategy", "v1 ", 1),
        ("strategy", "v1", 0),
        ("strategy", "v1", -1),
        ("strategy", "v1", True),
    ],
)
def test_strategy_key_rejects_noncanonical_or_incomplete_identity(
    strategy_id: Any,
    strategy_version: Any,
    replicate: Any,
) -> None:
    with pytest.raises(HistoricalPrefixQueryContractError):
        HistoricalPrefixStrategyKey(strategy_id, strategy_version, replicate)


def test_strategy_key_has_no_default_version_or_replicate() -> None:
    with pytest.raises(TypeError):
        HistoricalPrefixStrategyKey("strategy")  # type: ignore[call-arg]


def test_query_models_are_frozen_slotted_values() -> None:
    key = HistoricalPrefixStrategyKey("strategy", "v1", 1)
    assert not hasattr(key, "__dict__")
    with pytest.raises(FrozenInstanceError):
        key.replicate = 2  # type: ignore[misc]


def test_metadata_preserves_source_identity_without_time_or_path_fields() -> None:
    result = analyze_historical_prefixes(build_run_import())
    first = GetHistoricalPrefixBestRankings().execute(result)
    second = GetHistoricalPrefixBestRankings().execute(result)

    assert first == second
    assert first.metadata.result_schema_version == result.result_schema_version
    assert first.metadata.source_import_identity_sha256 == result.source_import_identity_sha256
    assert first.metadata.source_manifest_sha256 == result.source_manifest_sha256
    assert first.metadata.source_artifact_sha256 == result.source_artifact_sha256
    assert first.metadata.dataset_identity == result.dataset_identity
    assert first.metadata.dataset_sha256 == result.dataset_sha256
    assert first.metadata.lottery_type == result.lottery_type.value
    assert first.metadata.ranking_policy_id == result.ranking_policy_id
    assert first.metadata.historical_only_disclaimer_id == result.historical_only_disclaimer_id
    assert not any("time" in name or "path" in name for name in first.metadata.__slots__)
