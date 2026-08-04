"""Application orchestration for legacy single- and multi-file draw imports."""

from __future__ import annotations

from collections.abc import Callable

from lottolab.application.ports import BatchDrawImportParser, BatchDrawImportRepository
from lottolab.domain.batch_imports import (
    BatchDrawImportCommit,
    BatchDrawImportPreview,
    ImportFilePayload,
)

BATCH_PARSER_VERSION = "lottolab-legacy-draw-batch-v1"


class BatchImportDigestMismatchError(ValueError):
    """The commit payload is not the previewed batch."""


class InvalidBatchDrawImportError(ValueError):
    """The batch contains no safely importable draw rows."""

    def __init__(self, preview: BatchDrawImportPreview) -> None:
        super().__init__("batch contains no safely importable draw rows")
        self.preview = preview


class PreviewBatchDrawImport:
    def __init__(self, parser: BatchDrawImportParser) -> None:
        self._parser = parser

    def execute(self, payloads: tuple[ImportFilePayload, ...]) -> BatchDrawImportPreview:
        return self._parser(payloads)


class CommitBatchDrawImport:
    def __init__(
        self,
        parser: BatchDrawImportParser,
        repository_factory: Callable[[], BatchDrawImportRepository],
    ) -> None:
        self._parser = parser
        self._repository_factory = repository_factory

    def execute(
        self,
        *,
        payloads: tuple[ImportFilePayload, ...],
        expected_manifest_sha256: str,
        parser_version: str,
    ) -> BatchDrawImportCommit:
        if parser_version != BATCH_PARSER_VERSION:
            raise BatchImportDigestMismatchError("batch parser version is not current")
        preview = self._parser(payloads)
        if preview.manifest_sha256 != expected_manifest_sha256:
            raise BatchImportDigestMismatchError("batch content does not match the preview digest")
        if not preview.is_valid:
            raise InvalidBatchDrawImportError(preview)
        return self._repository_factory().apply_valid_batch_import(preview)


__all__ = [
    "BATCH_PARSER_VERSION",
    "BatchImportDigestMismatchError",
    "CommitBatchDrawImport",
    "InvalidBatchDrawImportError",
    "PreviewBatchDrawImport",
]
