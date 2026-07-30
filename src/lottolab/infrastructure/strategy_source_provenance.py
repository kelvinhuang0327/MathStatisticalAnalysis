"""Exact native adapter-source and runner-commit provenance."""

from __future__ import annotations

import hashlib
import inspect
import json
import platform
import subprocess
import sys
from pathlib import Path

from lottolab.application.research_backtest_runner import (
    RESEARCH_BACKTEST_RUNNER_VERSION,
    ResearchBacktestProvenanceError,
    StrategySourceIdentity,
)


def resolve_repository_source_commit_oid(repository_root: Path) -> str:
    """Return HEAD only when it exactly identifies every current source byte."""

    try:
        status = subprocess.run(
            ["git", "-C", str(repository_root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ResearchBacktestProvenanceError(
            "repository identity could not be resolved"
        ) from exc
    if status.stdout:
        raise ResearchBacktestProvenanceError(
            "repository must be clean so source_commit_oid identifies runner bytes"
        )
    try:
        result = subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ResearchBacktestProvenanceError(
            "repository identity could not be resolved"
        ) from exc
    return result.stdout.strip()


class PythonStrategySourceIdentityResolver:
    """Hash the exact module bytes for the adapter selected by the registry."""

    def __init__(self, repository_root: Path) -> None:
        self._repository_root = repository_root.resolve(strict=True)

    def resolve(
        self,
        *,
        strategy_id: str,
        loaded_adapter: type[object],
    ) -> StrategySourceIdentity:
        source_name = inspect.getsourcefile(loaded_adapter)
        if source_name is None:
            raise ResearchBacktestProvenanceError(
                f"native source identity is unavailable for strategy {strategy_id}"
            )
        source_path = Path(source_name).resolve(strict=True)
        try:
            source_path.relative_to(self._repository_root)
        except ValueError as exc:
            raise ResearchBacktestProvenanceError(
                f"native source for strategy {strategy_id} is outside the repository"
            ) from exc
        try:
            source_bytes = source_path.read_bytes()
        except OSError as exc:
            raise ResearchBacktestProvenanceError(
                f"native source bytes are unavailable for strategy {strategy_id}"
            ) from exc
        fingerprint = json.dumps(
            {
                "implementation": platform.python_implementation(),
                "python_cache_tag": sys.implementation.cache_tag,
                "python_version": platform.python_version(),
                "runner_version": RESEARCH_BACKTEST_RUNNER_VERSION,
                "schema_version": "LOTTOLAB_PYTHON_RUNTIME_FINGERPRINT_V1",
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return StrategySourceIdentity(
            strategy_source_sha256=hashlib.sha256(source_bytes).hexdigest(),
            runtime_fingerprint=fingerprint,
        )


__all__ = [
    "PythonStrategySourceIdentityResolver",
    "resolve_repository_source_commit_oid",
]
