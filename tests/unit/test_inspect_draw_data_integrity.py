"""Unit tests for the InspectDrawDataIntegrity use case, against a fake reader."""

from __future__ import annotations

from pathlib import Path

import pytest

from lottolab.application.use_cases.inspect_draw_data_integrity import (
    DrawDataIntegrityReader,
    InspectDrawDataIntegrity,
    InspectDrawDataIntegrityRequest,
)
from lottolab.domain.draw_data_integrity import (
    DrawDataIntegrityReport,
    DrawDataIntegrityStatus,
)

_ABSENT_REPORT = DrawDataIntegrityReport(
    status=DrawDataIntegrityStatus.ABSENT,
    schema_version=None,
    table_counts=(),
    lottery_summaries=(),
    findings=(),
)


class _FakeReader:
    def __init__(
        self,
        report: DrawDataIntegrityReport | None = None,
        error: Exception | None = None,
    ) -> None:
        self._report = report
        self._error = error
        self.received_database: Path | None = None

    def inspect(self, database: Path) -> DrawDataIntegrityReport:
        self.received_database = database
        if self._error is not None:
            raise self._error
        assert self._report is not None
        return self._report


class _BrokenSchemaError(RuntimeError):
    pass


def test_fake_reader_satisfies_the_reader_protocol() -> None:
    reader = _FakeReader(report=_ABSENT_REPORT)
    assert isinstance(reader, DrawDataIntegrityReader)


def test_execute_delegates_the_exact_requested_path_to_the_reader() -> None:
    reader = _FakeReader(report=_ABSENT_REPORT)
    use_case = InspectDrawDataIntegrity(reader)
    database = Path("/private/tmp/lottolab-p337-draw-data-integrity-r1/full/example/lottolab.db")

    use_case.execute(InspectDrawDataIntegrityRequest(database=database))

    assert reader.received_database == database


def test_execute_forwards_an_absent_result_unchanged() -> None:
    reader = _FakeReader(report=_ABSENT_REPORT)
    use_case = InspectDrawDataIntegrity(reader)

    result = use_case.execute(
        InspectDrawDataIntegrityRequest(database=Path("/nonexistent/lottolab.db"))
    )

    assert result is _ABSENT_REPORT
    assert result.status is DrawDataIntegrityStatus.ABSENT


def test_execute_propagates_a_reader_exception_unchanged() -> None:
    reader = _FakeReader(error=_BrokenSchemaError("cannot open the local draw database safely"))
    use_case = InspectDrawDataIntegrity(reader)

    with pytest.raises(_BrokenSchemaError, match="cannot open"):
        use_case.execute(InspectDrawDataIntegrityRequest(database=Path("/bad/lottolab.db")))


def test_request_holds_the_exact_path_it_was_given() -> None:
    database = Path("/private/tmp/lottolab-p337-draw-data-integrity-r1/full/example/lottolab.db")
    request = InspectDrawDataIntegrityRequest(database=database)
    assert request.database == database
