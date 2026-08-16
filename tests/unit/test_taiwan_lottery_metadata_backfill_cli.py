"""Unit coverage for the operator-triggered official-draw metadata backfill CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import lottolab.interfaces.cli.taiwan_lottery_metadata_backfill as backfill_cli
from lottolab.infrastructure.taiwan_lottery_draw_provider import TaiwanLotteryDrawProvider
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def _envelope(result_key: str, rows: list[dict[str, object]]) -> bytes:
    return json.dumps({"rtCode": 0, "rtMsg": "OK", "content": {result_key: rows}}).encode("utf-8")


def _row() -> dict[str, object]:
    return {
        "period": 115000079,
        "lotteryDate": "2026-08-14",
        "drawNumberSize": [5, 12, 25, 33, 34, 35, 27],
        "drawNumberAppear": [35, 25, 5, 12, 34, 33, 27],
        "totalAmount": 130683982,
        "sellAmount": 93928200,
        "jackpotAssign": {
            "prize": 18825389,
            "lastPrize": 78084190,
            "winnerCount": 0,
            "perPrize": 0,
        },
    }


def _fake_provider_factory(response: bytes):
    def _factory() -> TaiwanLotteryDrawProvider:
        return TaiwanLotteryDrawProvider(transport=lambda _url: response)

    return _factory


def test_command_is_registered() -> None:
    result = runner.invoke(app, ["backfill-taiwan-lottery-metadata", "--help"])

    assert result.exit_code == 0
    assert "--lottery-type" in result.output
    assert "--date-from" in result.output
    assert "--date-to" in result.output
    assert "--output" in result.output


def test_fetches_and_appends_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "metadata.jsonl"
    monkeypatch.setattr(
        backfill_cli,
        "TaiwanLotteryDrawProvider",
        _fake_provider_factory(_envelope("lotto649Res", [_row()])),
    )

    result = runner.invoke(
        app,
        [
            "backfill-taiwan-lottery-metadata",
            "--lottery-type",
            "BIG_LOTTO",
            "--date-from",
            "2026-08-01",
            "--date-to",
            "2026-08-31",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["fetched_count"] == 1
    assert payload["written_count"] == 1
    assert output.exists()
    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    written = json.loads(lines[0])
    assert written["draw_number"] == "115000079"
    assert written["jackpot_last_prize"] == 78084190


def test_rejects_an_invalid_date_range(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "metadata.jsonl"
    monkeypatch.setattr(
        backfill_cli,
        "TaiwanLotteryDrawProvider",
        _fake_provider_factory(_envelope("lotto649Res", [])),
    )

    result = runner.invoke(
        app,
        [
            "backfill-taiwan-lottery-metadata",
            "--lottery-type",
            "BIG_LOTTO",
            "--date-from",
            "2026-08-31",
            "--date-to",
            "2026-08-01",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert not output.exists()
