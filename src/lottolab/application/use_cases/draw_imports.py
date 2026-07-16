"""DB-free preview and validation-gated transactional commit use cases."""

from __future__ import annotations

import hashlib

from lottolab.application.draw_data import (
    DigestMismatchError,
    ImportCommitResult,
    InvalidDrawImportError,
    ParserVersionMismatchError,
)
from lottolab.application.ports import DrawCsvParser, DrawDataRepositoryFactory
from lottolab.domain.ingestion import DrawCsvParseResult


class PreviewDrawImport:
    def __init__(self, parser: DrawCsvParser, parser_version: str) -> None:
        self._parser = parser
        self._parser_version = parser_version

    def execute(
        self,
        *,
        filename: str,
        csv_text: str,
        declared_parser_version: str | None,
    ) -> DrawCsvParseResult:
        if (
            declared_parser_version is not None
            and declared_parser_version != self._parser_version
        ):
            raise ParserVersionMismatchError("The declared parser version is not current")
        return self._parser(csv_text, filename=filename)


class CommitDrawImport:
    def __init__(
        self,
        parser: DrawCsvParser,
        parser_version: str,
        repository_factory: DrawDataRepositoryFactory,
    ) -> None:
        self._parser = parser
        self._parser_version = parser_version
        self._repository_factory = repository_factory

    def execute(
        self,
        *,
        filename: str,
        csv_text: str,
        expected_sha256: str,
        parser_version: str,
    ) -> ImportCommitResult:
        actual_sha256 = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
        if actual_sha256 != expected_sha256:
            raise DigestMismatchError("CSV content does not match the preview digest")
        if parser_version != self._parser_version:
            raise ParserVersionMismatchError("The parser version is not current")

        parsed = self._parser(csv_text, filename=filename)
        if not parsed.is_valid:
            raise InvalidDrawImportError(parsed)

        repository = self._repository_factory()
        return repository.apply_valid_import(parsed)
