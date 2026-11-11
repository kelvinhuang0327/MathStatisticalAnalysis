"""Temporal, variable-cardinality and normal-entry replay regression checks."""

# The replay tests below intentionally exercise private replay-generation hooks.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Protocol, cast

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottolab.application.historical_replay_adapters import (
    BigLottoReplayAdapter,
    binding_from_implementation,
)
from lottolab.application.seeded_single_replay import SEED_CONTRACT
from lottolab.application.use_cases.historical_replay_controller import HistoricalReplayController
from lottolab.application.use_cases.replay_backfill import (
    BackfillSelection,
    ReplayBackfill,
    _OutcomeBlindAdapter,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayBehavior, ReplayDraw
from lottolab.infrastructure.persistence.replay_backfill_store import (
    JsonObject,
    SQLiteBackfillStore,
)
from lottolab.interfaces.api.replay_backfill import _prediction_item, create_replay_backfill_router
from lottolab.interfaces.cli import replay_backfill as replay_cli
from lottolab.interfaces.cli.replay_backfill import build_adapter, native_strategy_inventory
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_batch16 import _EvoStrategy
from lottolab.strategies.adapters.biglotto_evolution_causal import (
    SEED_CONTRACT as EVOLUTION_SEED_CONTRACT,
)
from lottolab.strategies.adapters.biglotto_evolution_causal import BigLottoCausalEvolutionAdapter


class JsonTestClient(Protocol):
    def get(self, url: str, **kwargs: object) -> httpx.Response: ...


def _history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            str(100000001 + i),
            (date(2020, 1, 1) + timedelta(days=i)).isoformat(),
            (1, 2, 3, 4, 5, 6),
        )
        for i in range(n)
    )


class _Candidate(_EvoStrategy):
    def __init__(self, name: str, *, fail_at: int | None = None) -> None:
        self.name = name
        self.params = {"name": name}
        self.category = "test"
        self.seen: list[int] = []
        self.fail_at = fail_at

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        self.seen.append(len(draws))
        if len(draws) == self.fail_at:
            raise ValueError("unknown result")
        return [1, 2, 3, 4, 5, 6][:n_select]


def test_development_and_holdout_are_disjoint_and_rolling(monkeypatch: pytest.MonkeyPatch) -> None:
    history = _history(551)
    good, bad = _Candidate("good"), _Candidate("bad", fail_at=503)
    seen_development: list[tuple[CausalDrawRow, ...]] = []

    def fit(_self: object, development: tuple[CausalDrawRow, ...]) -> tuple[_EvoStrategy, ...]:
        seen_development.append(development)
        return (good, bad)

    monkeypatch.setattr(BigLottoCausalEvolutionAdapter, "_fit_candidates", fit)
    adapter = BigLottoCausalEvolutionAdapter()
    tickets = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    assert seen_development == [history[:501]]
    assert good.seen == [*range(501, 551), 551]
    assert bad.seen == [501, 502, 503]
    assert tickets == ((1, 2, 3, 4, 5, 6),)


def test_general_entry_has_versioned_seeded_bindings_and_replays() -> None:
    bindings, accounts = native_strategy_inventory(LotteryType.BIG_LOTTO)
    seeded = [b for b in bindings if b.strategy.behavior is ReplayBehavior.SEEDED_STOCHASTIC]
    relevant = [b for b in seeded if b.strategy.strategy_version.endswith("+seeded-replay-v1")]
    assert len(relevant) == 10
    assert all(b.strategy.seed_contract == SEED_CONTRACT for b in relevant)
    assert all(
        accounts[b.strategy.strategy_id]["behavior"] == "SEEDED_STOCHASTIC" for b in relevant
    )
    evolution = next(
        b for b in bindings if b.strategy.strategy_id == BigLottoCausalEvolutionAdapter.strategy_id
    )
    assert evolution.strategy.strategy_version == "v0.5"
    assert evolution.strategy.behavior is ReplayBehavior.SEEDED_STOCHASTIC
    assert evolution.strategy.seed_contract == EVOLUTION_SEED_CONTRACT
    assert set(accounts[evolution.strategy.strategy_id]["dependency_sha256"]) == {
        "lottolab.strategies.adapters.biglotto_batch16",
        "lottolab.strategies.adapters.biglotto_evolution_causal",
        "lottolab.strategies.adapters.biglotto_evolution_strict",
        "lottolab.strategies.adapters.biglotto_evolution_bounded",
        "lottolab.strategies.adapters.base",
    }
    binding = next(b for b in relevant if "ml_features" in b.strategy.strategy_id)
    rows = _history(35)
    draws = tuple(
        ReplayDraw(LotteryType.BIG_LOTTO, r.draw, date.fromisoformat(r.date), r.numbers, 7)
        for r in rows
    )
    controller = HistoricalReplayController(
        _OutcomeBlindAdapter(build_adapter(LotteryType.BIG_LOTTO, (binding,)))
    )
    first = controller._generate_cell(binding.strategy, draws[-1], draws[:-1])
    second = controller._generate_cell(binding.strategy, draws[-1], draws[:-1])
    assert first.status.value == second.status.value == "COMPLETE"
    assert first.tickets == second.tickets


def test_general_backfill_worker_runs_seeded_strategy_without_database() -> None:
    class MemoryStore:
        def __init__(self) -> None:
            self.rows: dict[str, JsonObject] = {}
            self.manifest: JsonObject = {}

        def prepare(self, manifest: JsonObject) -> None:
            self.manifest = manifest

        def lookup_many(self, ids: tuple[str, ...]) -> dict[str, JsonObject]:
            return {key: self.rows[key] for key in ids if key in self.rows}

        def lookup(self, cell_identity: str) -> JsonObject | None:
            return self.rows.get(cell_identity)

        def lookup_many_by_unique_keys(
            self, _keys: tuple[tuple[str, str, str, str, str, str], ...]
        ) -> dict[tuple[str, str, str, str, str, str], JsonObject]:
            return {}

        def lookup_complete_by_logical_keys(
            self, _keys: tuple[tuple[str, str, str, str], ...]
        ) -> dict[tuple[str, str, str, str], tuple[JsonObject, ...]]:
            return {}

        def save_many(self, _run_id: str, results: tuple[JsonObject, ...]) -> None:
            self.rows.update({row["cell_identity"]: row for row in results})

        def save(self, _run_id: str, result: JsonObject, *, attempted: bool = True) -> None:
            self.rows[str(result["cell_identity"])] = result

        def summary(self, _run_id: str) -> JsonObject:
            return {"valid_result_cells": len(self.rows), "pending_cells": 0}

    bindings, accounts = native_strategy_inventory(LotteryType.BIG_LOTTO)
    binding = next(b for b in bindings if "frontend_ml_features" in b.strategy.strategy_id)
    rows = _history(35)
    draws = tuple(
        ReplayDraw(LotteryType.BIG_LOTTO, r.draw, date.fromisoformat(r.date), r.numbers, 7)
        for r in rows
    )
    first_store = MemoryStore()
    second_store = MemoryStore()

    def run(store: MemoryStore, batch_size: int) -> None:
        worker = ReplayBackfill(
            adapter=build_adapter(LotteryType.BIG_LOTTO, (binding,)),
            strategies=(binding.strategy,),
            draws=draws,
            source_identity="synthetic",
            store=store,  # type: ignore[arg-type]
            execution_version="test",
            strategy_sources={binding.strategy.strategy_id: accounts[binding.strategy.strategy_id]},
        )
        assert (
            worker.execute(BackfillSelection(latest=4), batch_size=batch_size)["valid_result_cells"]
            == 4
        )

    run(first_store, 1)
    run(second_store, 4)
    assert first_store.rows == second_store.rows
    assert first_store.manifest["strategies"][0]["seed_contract"] == SEED_CONTRACT
    assert all(
        row["strategy_version"].endswith("+seeded-replay-v1") for row in first_store.rows.values()
    )


def test_normal_cli_executes_seeded_strategy_without_database(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class MemoryStore:
        def __init__(self, _path: object) -> None:
            self.rows: dict[str, JsonObject] = {}
            self.manifest: JsonObject = {}
            stores.append(self)

        def prepare(self, manifest: JsonObject) -> None:
            self.manifest = manifest

        def lookup_many(self, ids: tuple[str, ...]) -> dict[str, JsonObject]:
            return {key: self.rows[key] for key in ids if key in self.rows}

        def lookup(self, cell_identity: str) -> JsonObject | None:
            return self.rows.get(cell_identity)

        def lookup_many_by_unique_keys(
            self, _keys: tuple[tuple[str, str, str, str, str, str], ...]
        ) -> dict[tuple[str, str, str, str, str, str], JsonObject]:
            return {}

        def lookup_complete_by_logical_keys(
            self, _keys: tuple[tuple[str, str, str, str], ...]
        ) -> dict[tuple[str, str, str, str], tuple[JsonObject, ...]]:
            return {}

        def save_many(self, _run_id: str, results: tuple[JsonObject, ...]) -> None:
            self.rows.update({row["cell_identity"]: row for row in results})

        def save(self, _run_id: str, result: JsonObject, *, attempted: bool = True) -> None:
            self.rows[str(result["cell_identity"])] = result

        def summary(self, _run_id: str) -> JsonObject:
            return {"status": "COMPLETED", "valid_result_cells": len(self.rows)}

    stores: list[MemoryStore] = []
    rows = _history(35)
    draws = tuple(
        ReplayDraw(LotteryType.BIG_LOTTO, r.draw, date.fromisoformat(r.date), r.numbers, 7)
        for r in rows
    )
    monkeypatch.setattr(replay_cli, "SQLiteBackfillStore", MemoryStore)
    def validate_database_path(path: Path) -> Path:
        return path

    def source_database_hash(_path: Path) -> str:
        return "source-hash"

    def load_draw_snapshot(*_args: object) -> tuple[ReplayDraw, ...]:
        return draws

    monkeypatch.setattr(replay_cli, "validate_database_path", validate_database_path)
    monkeypatch.setattr(replay_cli, "source_database_hash", source_database_hash)
    monkeypatch.setattr(replay_cli, "load_draw_snapshot", load_draw_snapshot)
    monkeypatch.setattr(replay_cli, "execution_source_identity", lambda: "test-source")
    strategy_id = "legacy_biglotto__frontend_ml_features__3a4324bc2aa9"
    test_database_root = Path(replay_cli.tempfile.gettempdir()) / "msa-pytest.seeded-cli"
    rc = replay_cli.main(
        [
            "--lottery-type",
            "BIG_LOTTO",
            "--source-database",
            "/not-read/source",
            "--database",
            str(test_database_root / "replay.sqlite"),
            "--strategy-id",
            strategy_id,
            "--latest",
            "3",
        ],
        test_only_external_database_root=test_database_root,
    )
    assert rc == 0 and len(stores) == 1 and len(stores[0].rows) == 3
    assert all(
        row["strategy_version"].endswith("+seeded-replay-v1") for row in stores[0].rows.values()
    )
    assert '"status":"COMPLETED"' in capsys.readouterr().out


def test_general_readonly_api_lists_seeded_and_unseeded_versions() -> None:
    class ReadOnlyStore:
        def stored_strategy_inventory(self, _lottery: str) -> list[object]:
            return []

    app = FastAPI()
    app.include_router(create_replay_backfill_router(ReadOnlyStore()))  # type: ignore[arg-type]
    strategy_id = "legacy_biglotto__frontend_ml_features__3a4324bc2aa9"
    response = cast(JsonTestClient, TestClient(app)).get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": strategy_id},
    )
    assert response.status_code == 200
    versions = {item["strategy_version"]: item for item in response.json()["items"]}
    assert versions["v0.1"]["executable"] is False
    assert versions["v0.1+seeded-replay-v1"]["executable"] is True


def test_dynamic_count_is_cached_and_training_cutoff_recorded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    candidate = _Candidate("candidate")
    fits: list[int] = []

    def fit(_self: object, development: tuple[CausalDrawRow, ...]) -> tuple[_EvoStrategy, ...]:
        fits.append(len(development))
        return (candidate,)

    monkeypatch.setattr(BigLottoCausalEvolutionAdapter, "_fit_candidates", fit)
    rows = _history(552)
    draws = tuple(
        ReplayDraw(LotteryType.BIG_LOTTO, r.draw, date.fromisoformat(r.date), r.numbers, 7)
        for r in rows
    )
    impl = BigLottoCausalEvolutionAdapter()
    binding = binding_from_implementation(impl)
    adapter = BigLottoReplayAdapter((binding,))
    controller = HistoricalReplayController(_OutcomeBlindAdapter(adapter))
    record = controller._generate_cell(binding.strategy, draws[-1], draws[:-1])
    assert record.status.value == "COMPLETE" and len(record.tickets) == 1
    assert fits == [501]
    worker = ReplayBackfill(
        adapter=adapter,
        strategies=(binding.strategy,),
        draws=draws,
        source_identity="synthetic",
        store=SQLiteBackfillStore(tmp_path / "replay.sqlite"),
        execution_version="test",
        strategy_sources={
            binding.strategy.strategy_id: {
                "training_status": "CAUSAL_FIT_PER_TARGET",
                "training_holdout_size": 50,
            }
        },
    )
    payload = worker._payload(record, "test-cell")
    assert payload["training"]["training_cutoff_draw_id"] == draws[500].draw_number
    assert payload["training"]["validation_first_draw_id"] == draws[501].draw_number
    assert payload["training"]["validation_last_draw_id"] == draws[550].draw_number
    assert payload["training"]["validation_draw_count"] == 50
    public_training = _prediction_item(payload, payload, None)["training"]
    assert public_training["training_cutoff_draw_id"] == draws[500].draw_number
    assert public_training["validation_first_draw_id"] == draws[501].draw_number
    assert public_training["validation_last_draw_id"] == draws[550].draw_number
