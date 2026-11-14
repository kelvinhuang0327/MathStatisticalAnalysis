import hashlib
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lottolab.application.local_runtime import LocalRuntimeError
from lottolab.application.use_cases.replay_backfill import (
    BackfillSelection,
    ReplayBackfill,
    canonical_json,
    identity,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayBehavior, ReplayDraw, ReplayStrategy
from lottolab.interfaces.cli import replay_backfill as replay_backfill_cli


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"latest": 0},
        {"latest": True},
        {"latest": 2, "all_draws": True},
        {"all_draws": True, "start_date": date(2020, 1, 1)},
        {"start_date": date(2020, 2, 1), "end_date": date(2020, 1, 1)},
    ],
)
def test_reject_invalid_selection(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        BackfillSelection(**kwargs)


def test_selection_preserves_full_history_and_does_not_pad_missing_draws() -> None:
    draws = tuple(
        ReplayDraw(
            LotteryType.BIG_LOTTO,
            str(n),
            date(2020, 1, 1) + timedelta(days=n),
            (1, 2, 3, 4, 5, 6),
            7,
        )
        for n in range(10)
    )
    assert BackfillSelection(latest=3).select(draws) == draws[-3:]
    assert (
        BackfillSelection(start_date=draws[3].draw_date, end_date=draws[5].draw_date).select(draws)
        == draws[3:6]
    )
    assert BackfillSelection(all_draws=True).select(draws) == draws
    with pytest.raises(ValueError, match="only 10 available"):
        BackfillSelection(latest=1500).select(draws)
    with pytest.raises(ValueError, match="no target"):
        BackfillSelection(start_date=date(2030, 1, 1)).select(draws)


def test_hash_uses_json_roundtrip() -> None:
    assert canonical_json({1: (2, 3)}) == canonical_json({"1": [2, 3]})
    assert identity({1: (2, 3)}) == identity({"1": [2, 3]})


@pytest.mark.parametrize(
    ("application_revision", "revision_status"),
    [("a" * 40, "AVAILABLE"), (None, "UNKNOWN")],
    ids=("known-revision", "unavailable-revision"),
)
def test_manifest_records_implementation_provenance_separately(
    application_revision: str | None,
    revision_status: str,
) -> None:
    strategy = ReplayStrategy(
        "fixture_strategy",
        "Fixture strategy",
        "v2",
        ReplayBehavior.DETERMINISTIC,
        1,
        0,
        fingerprint="fixture-fingerprint",
    )
    source_sha256 = "b" * 64
    worker = ReplayBackfill(
        adapter=SimpleNamespace(lottery_type=LotteryType.BIG_LOTTO),
        strategies=(strategy,),
        draws=(ReplayDraw(LotteryType.BIG_LOTTO, "100", date(2020, 1, 1), (1,)),),
        source_identity="fixture-source",
        store=object(),
        execution_version="execution-hash",
        strategy_sources={
            "fixture_strategy": {
                "source_module": "lottolab.strategies.fixture",
                "source_path": "lottolab/strategies/fixture.py",
                "source_sha256": source_sha256,
                "source_history_provenance": {"status": "UNKNOWN"},
            }
        },
        application_revision=application_revision,
    )

    manifest = worker.manifest(BackfillSelection(all_draws=True))
    provenance = manifest["implementation_provenance"]
    revision = provenance["application_revision"]
    assert revision["status"] == revision_status
    assert revision["commit"] == application_revision
    assert revision["provider"] == "git-rev-parse"
    assert provenance["execution_version"] == "execution-hash"
    assert provenance["strategies"] == [
        {
            "strategy_id": "fixture_strategy",
            "strategy_version": "v2",
            "source_status": "AVAILABLE",
            "source_module": "lottolab.strategies.fixture",
            "source_path": "lottolab/strategies/fixture.py",
            "file_sha256": source_sha256,
        }
    ]
    assert "source_history_provenance" not in provenance
    assert manifest["strategy_sources"]["fixture_strategy"]["source_history_provenance"] == {
        "status": "UNKNOWN"
    }


def test_application_revision_uses_loaded_checkout_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_revision = "c" * 40
    expected_repository = Path(replay_backfill_cli.__file__).resolve().parents[4]

    def revision_reader(repository: Path) -> str:
        assert repository == expected_repository
        return expected_revision

    monkeypatch.setattr(replay_backfill_cli, "_read_git_revision", revision_reader)

    assert replay_backfill_cli.application_revision() == expected_revision


def test_application_revision_is_unavailable_without_git_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_reader(_repository: Path) -> str:
        raise LocalRuntimeError("Git metadata unavailable")

    monkeypatch.setattr(replay_backfill_cli, "_read_git_revision", unavailable_reader)

    assert replay_backfill_cli.application_revision() is None


def test_biglotto_inventory_records_source_module_path_and_hash() -> None:
    bindings, accounts = replay_backfill_cli.native_strategy_inventory(LotteryType.BIG_LOTTO)
    assert bindings

    strategy = bindings[0].strategy
    source = accounts[strategy.strategy_id]
    source_path = (
        Path(replay_backfill_cli.__file__).resolve().parents[3] / source["source_path"]
    )
    assert source["source_module"].startswith("lottolab.")
    assert source_path.is_file()
    assert source["source_sha256"] == hashlib.sha256(source_path.read_bytes()).hexdigest()
