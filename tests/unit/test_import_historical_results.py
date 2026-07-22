"""Unit tests for the ImportHistoricalResults application use case (BLHQ R1)."""

from __future__ import annotations

import pytest
from tests.fixtures.historical.builder import build_baseline_envelope, envelope_bytes

from lottolab.application.use_cases.import_historical_results import ImportHistoricalResults
from lottolab.domain.historical_results import (
    HistoricalImportCommitResult,
    HistoricalRunImport,
    HistoricalRunStatus,
)
from lottolab.normalization.historical_import import verify_and_normalize_historical_import


class _StubRepository:
    def __init__(self) -> None:
        self.received: HistoricalRunImport | None = None

    def commit_import(self, run_import: HistoricalRunImport) -> HistoricalImportCommitResult:
        self.received = run_import
        return HistoricalImportCommitResult(
            run_id="stub-run",
            status=HistoricalRunStatus.COMPLETED,
            import_identity_sha256=run_import.import_identity_sha256,
            manifest_sha256=run_import.manifest_sha256,
            is_idempotent_replay=False,
            completed_at="2026-07-20T00:00:00.000000Z",
            error_code=None,
            error_summary=None,
        )


def _normalized_import() -> HistoricalRunImport:
    envelope = build_baseline_envelope()
    result = verify_and_normalize_historical_import(envelope_bytes(envelope))
    assert result.normalized_import is not None
    return result.normalized_import


def test_use_case_delegates_a_validated_import_to_the_repository() -> None:
    repository = _StubRepository()
    use_case = ImportHistoricalResults(repository)
    run_import = _normalized_import()

    result = use_case(run_import)

    assert repository.received is run_import
    assert result.status is HistoricalRunStatus.COMPLETED
    assert result.import_identity_sha256 == run_import.import_identity_sha256


def test_use_case_rejects_anything_that_is_not_a_normalized_run_import() -> None:
    repository = _StubRepository()
    use_case = ImportHistoricalResults(repository)

    with pytest.raises(TypeError):
        use_case({"not": "a domain object"})  # type: ignore[arg-type]

    assert repository.received is None
