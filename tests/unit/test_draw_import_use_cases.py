"""Application gating tests for previewed CSV commit requests."""

from __future__ import annotations

import hashlib
from typing import cast

import pytest

from lottolab.application.draw_data import (
    DigestMismatchError,
    ImportCommitResult,
    InvalidDrawImportError,
    ParserVersionMismatchError,
)
from lottolab.application.ports import DrawDataRepository
from lottolab.application.use_cases.draw_imports import CommitDrawImport
from lottolab.domain.ingestion import DrawCsvParseResult
from lottolab.infrastructure.imports.csv_draws import PARSER_VERSION, parse_draw_csv

HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers"
VALID = HEADER + "\nBIG_LOTTO,1,2026-07-16,1|3|9|17|24|49,7\n"


class FakeImportRepository:
    def __init__(self) -> None:
        self.received: DrawCsvParseResult | None = None

    def apply_valid_import(self, result: DrawCsvParseResult) -> ImportCommitResult:
        self.received = result
        raise AssertionError("the fake does not commit")


def digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_digest_mismatch_stops_before_parse_and_repository_factory() -> None:
    parser_called = False
    factory_called = False

    def parser(content: str | bytes, *, filename: str = "") -> DrawCsvParseResult:
        del content, filename
        nonlocal parser_called
        parser_called = True
        raise AssertionError("digest mismatch must stop before parsing")

    def factory() -> DrawDataRepository:
        nonlocal factory_called
        factory_called = True
        return cast(DrawDataRepository, FakeImportRepository())

    use_case = CommitDrawImport(parser, PARSER_VERSION, factory)
    with pytest.raises(DigestMismatchError):
        use_case.execute(
            filename="synthetic.csv",
            csv_text=VALID,
            expected_sha256="0" * 64,
            parser_version=PARSER_VERSION,
        )

    assert parser_called is False
    assert factory_called is False


def test_parser_version_mismatch_stops_before_parse_and_repository_factory() -> None:
    def parser(content: str | bytes, *, filename: str = "") -> DrawCsvParseResult:
        del content, filename
        raise AssertionError("stale parser version must stop before parsing")

    def factory() -> DrawDataRepository:
        raise AssertionError("stale parser version must stop before persistence")

    use_case = CommitDrawImport(parser, PARSER_VERSION, factory)
    with pytest.raises(ParserVersionMismatchError):
        use_case.execute(
            filename="synthetic.csv",
            csv_text=VALID,
            expected_sha256=digest(VALID),
            parser_version="stale",
        )


def test_invalid_document_with_normalized_rows_never_reaches_repository() -> None:
    duplicate = VALID + "BIG_LOTTO,1,2026-07-16,1|3|9|17|24|49,7\n"
    parsed = parse_draw_csv(duplicate)
    assert not parsed.is_valid
    assert len(parsed.normalized_rows) == 2

    def factory() -> DrawDataRepository:
        raise AssertionError("invalid parse result must not reach persistence")

    use_case = CommitDrawImport(parse_draw_csv, PARSER_VERSION, factory)
    with pytest.raises(InvalidDrawImportError) as captured:
        use_case.execute(
            filename="synthetic.csv",
            csv_text=duplicate,
            expected_sha256=digest(duplicate),
            parser_version=PARSER_VERSION,
        )

    assert captured.value.result is not None
