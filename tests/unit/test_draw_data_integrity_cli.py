"""Unit tests for the draw-data integrity CLI adapter and root registration.

Adapter behavior remains isolated on a test-local Typer app, while focused
root-app tests prove discovery, required-option handling, and direct dispatch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import lottolab.interfaces.cli.draw_data_integrity as cli_module
from lottolab.domain.draw_data_integrity import (
    DrawDataIntegrityFinding,
    DrawDataIntegrityFindingCode,
    DrawDataIntegrityReport,
    DrawDataIntegrityStatus,
    DrawDataLotterySummary,
    DrawDataTableCount,
)
from lottolab.infrastructure.persistence.draw_schema import LocalDataError, SchemaMigrationError
from lottolab.interfaces.cli.main import app as root_app

runner = CliRunner()

test_app = typer.Typer()
test_app.command("inspect-draw-data-integrity")(cli_module.draw_data_integrity_command)

_ABSENT_REPORT = DrawDataIntegrityReport(
    status=DrawDataIntegrityStatus.ABSENT,
    schema_version=None,
    table_counts=(),
    lottery_summaries=(),
    findings=(),
)

_ALL_ZERO_FINDINGS = tuple(
    DrawDataIntegrityFinding(code=code, count=0) for code in DrawDataIntegrityFindingCode
)

_HEALTHY_REPORT = DrawDataIntegrityReport(
    status=DrawDataIntegrityStatus.HEALTHY,
    schema_version=1,
    table_counts=(
        DrawDataTableCount(table_name="draws", row_count=2),
        DrawDataTableCount(table_name="ingestion_runs", row_count=1),
        DrawDataTableCount(table_name="ingestion_items", row_count=0),
    ),
    lottery_summaries=(
        DrawDataLotterySummary(
            lottery_type="BIG_LOTTO",
            draw_count=2,
            first_draw_number="0001",
            first_draw_date="2026-01-01",
            last_draw_number="0002",
            last_draw_date="2026-01-08",
        ),
    ),
    findings=_ALL_ZERO_FINDINGS,
)

_UNHEALTHY_REPORT = DrawDataIntegrityReport(
    status=DrawDataIntegrityStatus.UNHEALTHY,
    schema_version=1,
    table_counts=(
        DrawDataTableCount(table_name="draws", row_count=1),
        DrawDataTableCount(table_name="ingestion_runs", row_count=1),
        DrawDataTableCount(table_name="ingestion_items", row_count=0),
    ),
    lottery_summaries=(
        DrawDataLotterySummary(
            lottery_type="BIG_LOTTO",
            draw_count=1,
            first_draw_number="0001",
            first_draw_date="2026-01-01",
            last_draw_number="0001",
            last_draw_date="2026-01-01",
        ),
    ),
    findings=tuple(
        DrawDataIntegrityFinding(
            code=code,
            count=1 if code is DrawDataIntegrityFindingCode.FOREIGN_KEY_VIOLATION else 0,
        )
        for code in DrawDataIntegrityFindingCode
    ),
)


class _FakeReader:
    """Records every ``inspect`` call and returns one fixed report or error."""

    def __init__(
        self,
        report: DrawDataIntegrityReport | None = None,
        error: Exception | None = None,
    ) -> None:
        self._report = report
        self._error = error
        self.calls: list[Path] = []

    def inspect(self, database: Path) -> DrawDataIntegrityReport:
        self.calls.append(database)
        if self._error is not None:
            raise self._error
        assert self._report is not None
        return self._report


def _patch_reader(monkeypatch: pytest.MonkeyPatch, reader: _FakeReader) -> None:
    monkeypatch.setattr(cli_module, "SQLiteDrawDataIntegrityReader", lambda: reader)


def test_database_option_is_forwarded_verbatim_to_the_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = _FakeReader(report=_ABSENT_REPORT)
    _patch_reader(monkeypatch, reader)
    database = Path("/private/tmp/p338a-fixture/lottolab.db")

    result = runner.invoke(
        test_app, ["--database", str(database)]
    )

    assert result.exit_code == 1
    assert reader.calls == [database]


def test_inspection_runs_exactly_once_per_invocation(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = _FakeReader(report=_HEALTHY_REPORT)
    _patch_reader(monkeypatch, reader)

    result = runner.invoke(
        test_app,
        ["--database", "/private/tmp/p338a-fixture/lottolab.db"],
    )

    assert result.exit_code == 0
    assert len(reader.calls) == 1


def test_healthy_report_exits_zero_with_full_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_reader(monkeypatch, _FakeReader(report=_HEALTHY_REPORT))

    result = runner.invoke(
        test_app,
        ["--database", "/private/tmp/p338a-fixture/lottolab.db"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "HEALTHY"
    assert payload["schema_version"] == 1
    assert result.stderr == ""


def test_absent_report_exits_one_with_full_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_reader(monkeypatch, _FakeReader(report=_ABSENT_REPORT))

    result = runner.invoke(
        test_app,
        ["--database", "/private/tmp/p338a-fixture/lottolab.db"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload == {
        "status": "ABSENT",
        "schema_version": None,
        "table_counts": [],
        "lottery_summaries": [],
        "findings": [],
    }
    assert result.stderr == ""


def test_unhealthy_report_exits_one_with_full_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_reader(monkeypatch, _FakeReader(report=_UNHEALTHY_REPORT))

    result = runner.invoke(
        test_app,
        ["--database", "/private/tmp/p338a-fixture/lottolab.db"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "UNHEALTHY"
    findings_by_code = {entry["code"]: entry["count"] for entry in payload["findings"]}
    assert findings_by_code["FOREIGN_KEY_VIOLATION"] == 1
    assert result.stderr == ""


def test_json_key_and_array_ordering_is_fixed() -> None:
    rendered = cli_module.render_draw_data_integrity_report(_HEALTHY_REPORT)

    expected = (
        '{"findings":[{"code":"SQLITE_QUICK_CHECK_FAILED","count":0},'
        '{"code":"FOREIGN_KEY_VIOLATION","count":0},'
        '{"code":"DUPLICATE_DRAW_IDENTITY","count":0},'
        '{"code":"INVALID_DRAW_NUMBER","count":0},'
        '{"code":"INVALID_NORMALIZED_RECORD_HASH","count":0},'
        '{"code":"INVALID_NUMBERS_JSON","count":0}],'
        '"lottery_summaries":[{"draw_count":2,"first_draw_date":"2026-01-01",'
        '"first_draw_number":"0001","last_draw_date":"2026-01-08",'
        '"last_draw_number":"0002","lottery_type":"BIG_LOTTO"}],'
        '"schema_version":1,'
        '"status":"HEALTHY",'
        '"table_counts":[{"row_count":2,"table_name":"draws"},'
        '{"row_count":1,"table_name":"ingestion_runs"},'
        '{"row_count":0,"table_name":"ingestion_items"}]}'
    )
    assert rendered == expected
    assert json.loads(rendered) == json.loads(expected)


def test_repeated_rendering_of_the_same_report_is_byte_identical() -> None:
    first = cli_module.render_draw_data_integrity_report(_HEALTHY_REPORT)
    second = cli_module.render_draw_data_integrity_report(_HEALTHY_REPORT)
    assert first == second


def test_local_data_error_fails_closed_with_its_sanitized_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_reader(
        monkeypatch,
        _FakeReader(error=LocalDataError("local data path cannot contain symlinks")),
    )

    result = runner.invoke(
        test_app,
        ["--database", "/private/tmp/p338a-fixture/lottolab.db"],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "inspect-draw-data-integrity error: local data path cannot contain symlinks\n"
    )
    assert "Traceback" not in result.stderr


def test_schema_migration_error_fails_closed_with_its_sanitized_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_reader(
        monkeypatch,
        _FakeReader(error=SchemaMigrationError("database exists without a schema migration")),
    )

    result = runner.invoke(
        test_app,
        ["--database", "/private/tmp/p338a-fixture/lottolab.db"],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "inspect-draw-data-integrity error: database exists without a schema migration\n"
    )


def test_unexpected_error_fails_closed_and_leaks_no_internal_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_path = "/private/tmp/p338a-fixture/lottolab.db"
    _patch_reader(
        monkeypatch,
        _FakeReader(error=RuntimeError(f"disk I/O error reading {secret_path}")),
    )

    result = runner.invoke(
        test_app,
        ["--database", secret_path],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "inspect-draw-data-integrity error: inspection failed safely\n"
    assert secret_path not in result.stderr
    assert "Traceback" not in result.stderr


def test_output_never_contains_the_supplied_database_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_path = "/private/tmp/p338a-fixture/very-secret-directory/lottolab.db"
    _patch_reader(monkeypatch, _FakeReader(report=_HEALTHY_REPORT))

    result = runner.invoke(
        test_app,
        ["--database", secret_path],
    )

    assert secret_path not in result.stdout
    assert secret_path not in result.stderr
    assert "very-secret-directory" not in result.stdout
    assert "very-secret-directory" not in result.stderr


def test_missing_database_file_is_not_rejected_by_typer_argument_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``exists=True``: a nonexistent path must reach the use case, not fail in Typer."""

    reader = _FakeReader(report=_ABSENT_REPORT)
    _patch_reader(monkeypatch, reader)
    missing = Path("/private/tmp/p338a-fixture/definitely-does-not-exist/lottolab.db")

    result = runner.invoke(
        test_app, ["--database", str(missing)]
    )

    assert "Usage:" not in result.stderr
    assert reader.calls == [missing]


def test_missing_required_option_fails_with_empty_stdout() -> None:
    result = runner.invoke(test_app, [])

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Traceback" not in result.stderr


def test_root_help_lists_the_command_exactly_once_without_adapter_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def record_execution(database: Path) -> DrawDataIntegrityReport:
        calls.append(database)
        return _HEALTHY_REPORT

    monkeypatch.setattr(cli_module, "inspect_draw_data_integrity_report", record_execution)

    result = runner.invoke(root_app, ["--help"])

    assert result.exit_code == 0
    assert result.stdout.count("inspect-draw-data-integrity") == 1
    assert calls == []


def test_root_command_help_marks_database_required_without_adapter_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def record_execution(database: Path) -> DrawDataIntegrityReport:
        calls.append(database)
        return _HEALTHY_REPORT

    monkeypatch.setattr(cli_module, "inspect_draw_data_integrity_report", record_execution)

    result = runner.invoke(root_app, ["inspect-draw-data-integrity", "--help"])

    assert result.exit_code == 0
    assert "--database" in result.stdout
    assert "required" in result.stdout.casefold()
    assert calls == []


def test_missing_root_database_option_fails_before_adapter_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def record_execution(database: Path) -> DrawDataIntegrityReport:
        calls.append(database)
        return _HEALTHY_REPORT

    monkeypatch.setattr(cli_module, "inspect_draw_data_integrity_report", record_execution)

    result = runner.invoke(root_app, ["inspect-draw-data-integrity"])

    assert result.exit_code != 0
    assert "--database" in result.stderr
    assert calls == []


def test_root_dispatch_reaches_the_existing_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def record_execution(database: Path) -> DrawDataIntegrityReport:
        calls.append(database)
        return _HEALTHY_REPORT

    monkeypatch.setattr(cli_module, "inspect_draw_data_integrity_report", record_execution)
    database = Path("/private/tmp/p338b-fixture/lottolab.db")

    result = runner.invoke(
        root_app,
        ["inspect-draw-data-integrity", "--database", str(database)],
    )

    assert result.exit_code == 0
    assert calls == [database]
    assert json.loads(result.stdout)["status"] == "HEALTHY"
