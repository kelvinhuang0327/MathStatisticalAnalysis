"""Local composition tests for exact B649 sealed-authority paths."""

from __future__ import annotations

from pathlib import Path

from lottolab.infrastructure.b649_analytics_artifact_reader import (
    SealedB649AnalyticsArtifactReader,
)
from lottolab.interfaces.api.local_app import (
    B649_DEFAULT_TASK_DATA_ROOT,
    B649_TASK_DATA_ROOT_ENV,
    local_b649_analytics_composition,
)


def test_local_composition_uses_the_pinned_root_without_discovery() -> None:
    composition = local_b649_analytics_composition({})

    assert composition.task_data_root == B649_DEFAULT_TASK_DATA_ROOT
    assert isinstance(
        composition.b649_analytics_artifact_reader(),
        SealedB649AnalyticsArtifactReader,
    )


def test_local_composition_accepts_one_exact_server_side_override() -> None:
    root = Path("/owner/exact/task-data")
    composition = local_b649_analytics_composition({B649_TASK_DATA_ROOT_ENV: str(root)})

    assert composition.task_data_root == root
