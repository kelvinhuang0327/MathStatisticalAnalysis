"""BLHQ R1: commit one already-validated historical import."""

from __future__ import annotations

from lottolab.application.ports import HistoricalResultRepository
from lottolab.domain.historical_results import HistoricalImportCommitResult, HistoricalRunImport


class ImportHistoricalResults:
    """Thin composition of a validated import and its repository port.

    Never parses raw bytes: the only accepted input is a
    :class:`HistoricalRunImport` that normalization has already verified.
    """

    def __init__(self, repository: HistoricalResultRepository) -> None:
        self._repository = repository

    def __call__(self, run_import: HistoricalRunImport) -> HistoricalImportCommitResult:
        if type(run_import) is not HistoricalRunImport:
            raise TypeError(
                "ImportHistoricalResults accepts only a validated HistoricalRunImport"
            )
        return self._repository.commit_import(run_import)
