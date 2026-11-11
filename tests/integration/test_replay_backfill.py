from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import lottolab.infrastructure.persistence.project_database_paths as project_database_paths
from lottolab.application.historical_replay_adapters import (
    BigLottoReplayAdapter,
    ReplayStrategyBinding,
)
from lottolab.application.use_cases.replay_backfill import (
    BackfillSelection,
    ReplayBackfill,
    identity,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    ReplayBehavior,
    ReplayDraw,
    ReplayStrategy,
    ReplayTicket,
)
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import resolve_local_data_paths
from lottolab.infrastructure.persistence.project_database_paths import (
    canonical_project_root,
    project_database_environment,
)
from lottolab.infrastructure.persistence.replay_backfill_store import (
    SCHEMA_CHECKSUM,
    SCHEMA_SQL,
    SCHEMA_VERSION,
    SQLiteBackfillStore,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.interfaces.api.replay_backfill import create_app, create_replay_backfill_router
from lottolab.interfaces.cli import replay_backfill as replay_backfill_cli
from lottolab.interfaces.cli.main import app
from lottolab.interfaces.cli.replay_backfill import (
    build_adapter,
    main,
    native_strategy_inventory,
)
from lottolab.strategies.adapters.base import CausalDrawRow


class Producer:
    strategy_id = "two-tickets"
    fail = False
    calls = 0

    def get_bets(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("intentional isolated strategy failure")
        return ((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 7))


@pytest.fixture(autouse=True)
def isolate_project_database_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Keep CLI registry resolution inside a disposable fake canonical project."""
    project_root = tmp_path / "canonical-project"
    database_directory = project_root / "data" / "databases"
    database_directory.mkdir(parents=True)
    (project_root / ".task-data" / "_scratch").mkdir(parents=True)
    (project_root / ".gitignore").write_text("/.task-data/_scratch/\n", encoding="utf-8")
    subprocess.run(
        ["git", "init", "--quiet", str(project_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    fake_database = database_directory / "replay-backfill.sqlite3"
    _create_empty_backfill_database(fake_database)
    (database_directory / "database-locations.json").write_text(
        json.dumps(
            {
                "version": 1,
                "read_databases": {
                    "LOTTOLAB_REPLAY_BACKFILL_DB": "replay-backfill.sqlite3"
                },
                "writable_databases": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(project_database_paths, "PROJECT_ROOT", project_root)
    assert canonical_project_root() == project_root


@pytest.fixture
def test_only_external_database_root(tmp_path: Path) -> Path:
    """Give CLI test injection a named root without depending on pytest's temp name."""
    root = (
        tmp_path
        / "canonical-project"
        / ".task-data"
        / "_scratch"
        / "msa-pytest.replay-backfill"
    )
    root.mkdir()
    return root


def worker(
    tmp_path: Path,
    *,
    producer: Producer | None = None,
    draws: tuple[ReplayDraw, ...] | None = None,
    store: SQLiteBackfillStore | None = None,
    source_history_provenance_status: str = "UNKNOWN",
) -> tuple[ReplayBackfill, Producer, SQLiteBackfillStore]:
    producer = producer or Producer()
    strategy = ReplayStrategy(
        producer.strategy_id,
        "two-tickets",
        "v1",
        ReplayBehavior.DETERMINISTIC,
        2,
        2,
        fingerprint="source-v1",
    )
    adapter = BigLottoReplayAdapter((ReplayStrategyBinding(strategy, producer),))
    draws = draws or tuple(
        ReplayDraw(
            LotteryType.BIG_LOTTO,
            str(100000001 + n),
            date(2020, 1, 1) + timedelta(days=n),
            (1, 2, 3, 4, 5, 6),
            7,
        )
        for n in range(12)
    )
    store = store or SQLiteBackfillStore(tmp_path / "replay.sqlite3")
    return (
        ReplayBackfill(
            adapter=adapter,
            strategies=(strategy,),
            draws=draws,
            source_identity="synthetic-fixture-v1",
            store=store,
            execution_version="test-source-v1",
            source_history_provenance_status=source_history_provenance_status,
        ),
        producer,
        store,
    )


def _test_database_path(tmp_path: Path, filename: str) -> Path:
    project_root = next(
        parent for parent in Path(__file__).resolve().parents if (parent / ".git").exists()
    )
    project_database_paths.PROJECT_ROOT = project_root
    scratch = (
        project_root
        / ".task-data"
        / "_scratch"
        / "replay-hit-position-producer-fix-r1"
        / "pytest-databases"
    )
    scratch = scratch / tmp_path.parent.name
    scratch.mkdir(parents=True, exist_ok=True)
    return scratch / f"{tmp_path.name}-{filename}"


def test_resume_after_interruption_and_idempotence(tmp_path: Path) -> None:
    engine, producer, store = worker(
        tmp_path, store=SQLiteBackfillStore(_test_database_path(tmp_path, "resume.sqlite3"))
    )
    selection = BackfillSelection(latest=8)

    def interrupt(summary: dict[str, Any]) -> None:
        raise KeyboardInterrupt("simulate worker loss after durable commit")

    with pytest.raises(KeyboardInterrupt):
        engine.execute(selection, batch_size=3, progress=interrupt)
    run_id = engine.manifest(selection)["run_id"]
    assert store.summary(run_id)["valid_result_cells"] == 3
    before = store.query()["items"]
    resumed, _, _ = worker(tmp_path, producer=producer, store=store)
    result = resumed.execute(selection, batch_size=2)
    assert result["valid_result_cells"] == 8
    assert result["pending_cells"] == 0
    assert result["existing_skipped_count"] == 3
    assert result["newly_calculated_count"] == 5
    assert result["failed_count"] == 0
    assert producer.calls == 8
    assert store.query(limit=3)["items"] == before
    completed_payloads = json.loads(json.dumps(store.query()["items"]))
    repeated = resumed.execute(selection)
    assert repeated["existing_skipped_count"] == 8
    assert repeated["newly_calculated_count"] == 0
    assert producer.calls == 8
    assert store.query()["total_count"] == 8
    assert json.loads(json.dumps(store.query()["items"])) == completed_payloads


def test_skip_completed_cells_by_six_column_key_across_runs(tmp_path: Path) -> None:
    engine, producer, store = worker(tmp_path)
    first = engine.execute(BackfillSelection(latest=3))
    resumed, _, _ = worker(tmp_path, producer=producer, store=store)

    second = resumed.execute(BackfillSelection(latest=5))

    assert first["run_id"] != second["run_id"]
    assert second["existing_skipped_count"] == 3
    assert second["newly_calculated_count"] == 2
    assert second["valid_result_cells"] == 5
    assert producer.calls == 5
    assert store.query(run_id=second["run_id"])["total_count"] == 5


def test_batch_partition_parity_and_all_native_tickets(tmp_path: Path) -> None:
    a, _, store_a = worker(
        tmp_path, store=SQLiteBackfillStore(_test_database_path(tmp_path, "a.sqlite3"))
    )
    b, _, store_b = worker(
        tmp_path, store=SQLiteBackfillStore(_test_database_path(tmp_path, "b.sqlite3"))
    )
    a.execute(BackfillSelection(latest=8), batch_size=1, max_cells=4)
    a.execute(BackfillSelection(latest=8), batch_size=1)
    b.execute(BackfillSelection(latest=8), batch_size=8)
    assert store_a.query()["items"] == store_b.query()["items"]
    row = store_a.query(limit=1)["items"][0]
    assert len(row["predicted_tickets"]) == len(row["hit_details"]) == 2
    assert [ticket["ticket_position"] for ticket in row["predicted_tickets"]] == [1, 2]
    assert [hit["ticket_position"] for hit in row["hit_details"]] == [1, 2]
    assert [h["zone1_hits"] for h in row["hit_details"]] == [6, 5]
    assert [h["zone2_hit"] for h in row["hit_details"]] == [False, True]
    assert row["prize_results"] == ["FIRST", "SECOND"]
    assert row["combination_success"] is True


def test_complete_hit_positions_survive_store_and_http_projection(tmp_path: Path) -> None:
    engine, _, store = worker(
        tmp_path, store=SQLiteBackfillStore(_test_database_path(tmp_path, "http.sqlite3"))
    )
    summary = engine.execute(BackfillSelection(latest=1))
    run_id = str(summary["run_id"])
    read_only_store = SQLiteBackfillStore(store.database, read_only=True)
    stored_rows = read_only_store.query(run_id=run_id)["items"]
    assert len(stored_rows) == 1
    payload = cast(dict[str, Any], stored_rows[0])
    payload_without_identity = {
        key: value for key, value in payload.items() if key != "result_identity"
    }
    assert payload["result_identity"] == identity(payload_without_identity)
    assert payload["execution_status"] == "COMPLETE"
    assert [ticket["ticket_position"] for ticket in payload["predicted_tickets"]] == [1, 2]
    assert [hit["ticket_position"] for hit in payload["hit_details"]] == [1, 2]
    assert [
        {
            field: hit[field]
            for field in ("zone1_hits", "zone2_hit", "is_winner", "prize_tier")
        }
        for hit in payload["hit_details"]
    ] == [
        {"zone1_hits": 6, "zone2_hit": False, "is_winner": True, "prize_tier": "FIRST"},
        {"zone1_hits": 5, "zone2_hit": True, "is_winner": True, "prize_tier": "SECOND"},
    ]

    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as connection:
        child_rows = connection.execute(
            "SELECT ticket_position,main_numbers_json,special_numbers_json,"
            "main_hit_count,special_hit,prize_tier "
            "FROM replay_backfill_tickets WHERE cell_identity=? ORDER BY ticket_position",
            (payload["cell_identity"],),
        ).fetchall()
    for ticket, hit, child in zip(
        payload["predicted_tickets"], payload["hit_details"], child_rows, strict=True
    ):
        assert child[0] == ticket["ticket_position"] == hit["ticket_position"]
        assert json.loads(child[1]) == ticket["main_numbers"]
        assert json.loads(child[2]) == (
            [] if ticket["special_number"] is None else [ticket["special_number"]]
        )
        assert child[3:] == (
            hit["zone1_hits"],
            int(hit["zone2_hit"]),
            hit["prize_tier"],
        )

    app = FastAPI()
    app.include_router(create_replay_backfill_router(read_only_store))
    client = cast(httpx.Client, TestClient(app))
    root = "/api/v1/replay-backfill"
    results = client.get(root + "/results", params={"run_id": run_id})
    assert results.status_code == 200
    result_payload = results.json()["items"][0]
    assert result_payload["cell_identity"] == payload["cell_identity"]
    assert result_payload["result_identity"] == payload["result_identity"]
    run = client.get(root + "/runs/" + run_id)
    assert run.status_code == 200
    assert run.json()["valid_result_cells"] == 1
    predictions = client.get(
        root + "/predictions",
        params={
            "lottery_type": "BIG_LOTTO",
            "run_id": run_id,
            "strategy_id": "two-tickets",
            "period": "ALL",
        },
    )
    assert predictions.status_code == 200
    public_item = predictions.json()["items"][0]
    assert public_item["identity_status"] == "VERIFIED"
    assert public_item["evaluation_status"] == "EVALUATED"
    public_tickets = public_item["predicted_tickets"]
    assert [ticket["ticket_position"] for ticket in public_tickets] == [1, 2]
    assert [ticket["main_hit_count"] for ticket in public_tickets] == [6, 5]
    assert [ticket["special_hit"] for ticket in public_tickets] == [False, True]
    assert [ticket["prize_tier"] for ticket in public_tickets] == ["FIRST", "SECOND"]
    assert client.get(root + "/runs/missing").status_code == 404
    assert client.get(root + "/results", params={"limit": 201}).status_code == 422


def test_source_history_provenance_status_is_stored(tmp_path: Path) -> None:
    engine, _, store = worker(tmp_path, source_history_provenance_status="VERIFIED")
    selection = BackfillSelection(latest=1)
    summary = engine.execute(selection)

    read_only_store = SQLiteBackfillStore(store.database, read_only=True)
    rows = read_only_store.query(run_id=str(summary["run_id"]))["items"]
    assert len(rows) == 1
    assert rows[0]["source_history_provenance_status"] == "VERIFIED"
    assert engine.manifest(selection)["source_history_provenance_status"] == "VERIFIED"


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "invalid"])
def test_predictions_api_rejects_malformed_hit_positions(
    tmp_path: Path, mutation: str
) -> None:
    engine, _, store = worker(
        tmp_path, store=SQLiteBackfillStore(_test_database_path(tmp_path, "negative.sqlite3"))
    )
    summary = engine.execute(BackfillSelection(latest=1))
    run_id = str(summary["run_id"])
    payload = cast(dict[str, Any], store.query(run_id=run_id)["items"][0])
    hits = cast(list[dict[str, Any]], payload["hit_details"])
    if mutation == "missing":
        hits[0].pop("ticket_position")
    elif mutation == "duplicate":
        hits[1]["ticket_position"] = hits[0]["ticket_position"]
    else:
        hits[0]["ticket_position"] = 0
    payload_without_identity = {
        key: value for key, value in payload.items() if key != "result_identity"
    }
    payload["result_identity"] = identity(payload_without_identity)
    with sqlite3.connect(store.database) as connection:
        connection.execute(
            "UPDATE replay_backfill_cells SET result_identity=?,payload_json=? "
            "WHERE cell_identity=?",
            (
                payload["result_identity"],
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                payload["cell_identity"],
            ),
        )

    app = FastAPI()
    app.include_router(
        create_replay_backfill_router(SQLiteBackfillStore(store.database, read_only=True))
    )
    client = cast(httpx.Client, TestClient(app))
    response = client.get(
        "/api/v1/replay-backfill/predictions",
        params={"lottery_type": "BIG_LOTTO", "run_id": run_id, "period": "ALL"},
    )
    assert response.status_code == 200
    public_item = response.json()["items"][0]
    assert public_item["identity_status"] == "UNTRUSTED"
    assert public_item["evaluation_status"] == "UNTRUSTED"


def test_failure_isolation_retry_and_warmup_are_not_success(tmp_path: Path) -> None:
    engine, producer, store = worker(
        tmp_path, store=SQLiteBackfillStore(_test_database_path(tmp_path, "failure.sqlite3"))
    )
    producer.fail = True
    result = engine.execute(BackfillSelection(all_draws=True))
    assert result["failed_cells"] == 10
    assert result["missing_history_cells"] == 2
    assert result["valid_result_cells"] == 0
    failed_app = FastAPI()
    failed_app.include_router(
        create_replay_backfill_router(SQLiteBackfillStore(store.database, read_only=True))
    )
    failed_predictions = cast(httpx.Client, TestClient(failed_app)).get(
        "/api/v1/replay-backfill/predictions",
        params={
            "lottery_type": "BIG_LOTTO",
            "run_id": result["run_id"],
            "period": "ALL",
        },
    )
    assert failed_predictions.status_code == 200
    for item in failed_predictions.json()["items"]:
        if item["prediction_status"] != "COMPLETE":
            assert item["evaluation_status"] != "EVALUATED"
    producer.fail = False
    result = engine.execute(BackfillSelection(all_draws=True), retry_failed=True)
    assert result["valid_result_cells"] == 10
    assert result["missing_history_cells"] == 2
    assert result["coverage_percent"] < 100
    assert store.query()["total_count"] == 12


def test_generation_cannot_see_target_or_future_outcomes(tmp_path: Path) -> None:
    engine, _, store = worker(tmp_path)
    binding = engine.strategies[0]
    seen: list[str] = []

    class SpyAdapter(BigLottoReplayAdapter):
        def generate(
            self, strategy: ReplayStrategy, history: tuple[ReplayDraw, ...], target: ReplayDraw
        ) -> tuple[ReplayTicket, ...]:
            assert all(row.sort_key < target.sort_key for row in history)
            assert target.main_numbers == (0,)
            assert target.special_number is None
            seen.append(target.draw_number)
            return super().generate(strategy, history, target)

    adapter = SpyAdapter((ReplayStrategyBinding(binding, Producer()),))
    engine = ReplayBackfill(
        adapter=adapter,
        strategies=(binding,),
        draws=engine.draws,
        source_identity="fixture",
        store=store,
        execution_version="v1",
    )
    engine.execute(BackfillSelection(latest=3))
    assert seen == [d.draw_number for d in engine.draws[-3:]]


def test_production_strategy_predictions_ignore_changed_future_outcomes(tmp_path: Path) -> None:
    bindings, _ = native_strategy_inventory(LotteryType.BIG_LOTTO)
    binding = next(
        b for b in bindings if b.strategy.strategy_id == "biglotto_social_wisdom_anti_popularity"
    )
    base, _, _ = worker(tmp_path)
    mutated = (
        *base.draws[:-1],
        replace(base.draws[-1], main_numbers=(11, 12, 13, 14, 15, 16), special_number=17),
    )
    outputs: list[list[Any]] = []
    for n, draws in enumerate((base.draws, mutated)):
        store = SQLiteBackfillStore(tmp_path / f"future-{n}.sqlite3")
        engine = ReplayBackfill(
            adapter=build_adapter(LotteryType.BIG_LOTTO, (binding,)),
            strategies=(binding.strategy,),
            draws=draws,
            source_identity="same-fixture",
            store=store,
            execution_version="v1",
        )
        engine.execute(BackfillSelection(latest=2))
        outputs.append([r["predicted_tickets"] for r in store.query()["items"]])
    assert outputs[0] == outputs[1]


def test_query_api_filters_pagination_status_and_read_only(tmp_path: Path) -> None:
    engine, _, store = worker(tmp_path)
    result = engine.execute(BackfillSelection(all_draws=True))
    app = FastAPI()
    app.include_router(
        create_replay_backfill_router(SQLiteBackfillStore(store.database, read_only=True))
    )
    client = cast(httpx.Client, TestClient(app))
    path = "/api/v1/replay-backfill"
    response = client.get(
        path + "/results",
        params={
            "lottery_type": "BIG_LOTTO",
            "strategy_id": "two-tickets",
            "start_date": "2020-01-03",
            "end_date": "2020-01-08",
            "limit": 2,
            "offset": 1,
            "execution_status": "COMPLETE",
        },
    )
    assert response.status_code == 200
    assert response.json()["total_count"] == 6
    assert len(response.json()["items"]) == 2
    target = response.json()["items"][0]["target_draw_id"]
    assert (
        client.get(path + "/results", params={"target_draw_id": target}).json()["total_count"] == 1
    )
    assert client.get(path + "/results", params={"limit": 201}).status_code == 422
    assert (
        client.get(path + "/results?start_date=2021-01-01&end_date=2020-01-01").status_code == 422
    )
    assert client.get(path + "/runs/" + result["run_id"]).json()["valid_result_cells"] == 10
    assert client.get(path + "/runs/missing").status_code == 404
    assert client.post(path + "/results").status_code == 405
    assert (
        client.get(path + "/results", params={"strategy_id": "' OR 1=1 --"}).json()["items"] == []
    )


def test_predictions_api_pins_requested_run_across_newer_runs(tmp_path: Path) -> None:
    engine, _, store = worker(
        tmp_path, store=SQLiteBackfillStore(_test_database_path(tmp_path, "predictions.sqlite3"))
    )
    selection = BackfillSelection(all_draws=True)
    original = engine.execute(selection)
    # A newer target-window run reuses existing COMPLETE cells instead of
    # recomputing the same logical work under a different execution identity.
    newer = engine.execute(BackfillSelection(latest=5))
    assert newer["existing_skipped_count"] == 5
    assert newer["newly_calculated_count"] == 0
    assert original["run_id"] != newer["run_id"]

    app = FastAPI()
    app.include_router(
        create_replay_backfill_router(SQLiteBackfillStore(store.database, read_only=True))
    )
    client = cast(httpx.Client, TestClient(app))
    root = "/api/v1/replay-backfill/predictions"
    params = {
        "lottery_type": "BIG_LOTTO",
        "strategy_id": "two-tickets",
        "period": "ALL",
        "limit": 5,
        "run_id": original["run_id"],
    }

    first = client.get(root, params=params)
    assert first.status_code == 200
    assert first.json()["run_id"] == original["run_id"]
    assert first.json()["total_count"] == len(engine.draws)
    assert len(first.json()["items"]) == 5
    assert first.json()["next_cursor"]

    second = client.get(root, params={**params, "cursor": first.json()["next_cursor"]})
    assert second.status_code == 200
    assert second.json()["run_id"] == original["run_id"]
    assert second.json()["items"][0]["target_draw_number"] != first.json()["items"][-1][
        "target_draw_number"
    ]

    latest = client.get(
        root,
        params={key: value for key, value in params.items() if key not in {"run_id", "cursor"}},
    )
    assert latest.status_code == 200
    assert latest.json()["run_id"] == newer["run_id"]

    wrong_lottery = client.get(
        root,
        params={**params, "lottery_type": "DAILY_539"},
    )
    assert wrong_lottery.status_code == 422
    missing_run = client.get(root, params={**params, "run_id": "missing"})
    assert missing_run.status_code == 404


def test_contract_api_uses_bounded_stable_pages_and_recomputed_coverage(tmp_path: Path) -> None:
    engine, _, store = worker(tmp_path)
    engine.execute(BackfillSelection(all_draws=True))
    app = FastAPI()
    app.include_router(
        create_replay_backfill_router(SQLiteBackfillStore(store.database, read_only=True))
    )
    client = cast(httpx.Client, TestClient(app))
    root = "/api/v1/replay-backfill"

    first = client.get(root + "/strategies", params={"lottery_type": "BIG_LOTTO", "limit": 5})
    assert first.status_code == 200
    strategy_payload = first.json()
    assert len(strategy_payload["items"]) == 5
    assert strategy_payload["total_count"] > 5
    second = client.get(
        root + "/strategies",
        params={"lottery_type": "BIG_LOTTO", "limit": 5, "cursor": strategy_payload["next_cursor"]},
    )
    assert second.status_code == 200
    assert not {
        (item["strategy_id"], item["strategy_version"]) for item in strategy_payload["items"]
    }.intersection(
        (item["strategy_id"], item["strategy_version"]) for item in second.json()["items"]
    )

    response = client.get(
        root + "/predictions",
        params={"lottery_type": "BIG_LOTTO", "period": "ALL", "limit": 3},
    )
    assert response.status_code == 200
    prediction_payload = response.json()
    collected = list(prediction_payload["items"])
    while prediction_payload["next_cursor"] is not None:
        page = client.get(
            root + "/predictions",
            params={
                "lottery_type": "BIG_LOTTO",
                "period": "ALL",
                "limit": 3,
                "cursor": prediction_payload["next_cursor"],
            },
        )
        prediction_payload = page.json()
        collected.extend(prediction_payload["items"])
    assert len(collected) == prediction_payload["total_count"] == 12
    assert len({item["target_draw_number"] for item in collected}) == 12
    assert collected[-1]["predicted_tickets"][0]["ticket_position"] == 1
    assert collected[-1]["actual_main_numbers"] == list(engine.draws[-1].main_numbers)
    assert collected[-1]["training"]["training_status"] == "NOT_TRAINABLE"

    coverage = client.get(root + "/coverage", params={"lottery_type": "BIG_LOTTO"})
    assert coverage.status_code == 200
    assert coverage.json()["expected_cell_count"] == 12
    assert coverage.json()["completed_cell_count"] == 10
    assert coverage.json()["closed_cell_count"] == 2
    assert coverage.json()["missing_strategy_ids"] == ["two-tickets"]


def test_missing_database_is_not_created_by_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.sqlite3"
    monkeypatch.setenv("LOTTOLAB_REPLAY_BACKFILL_DB", str(missing))
    app = create_app()
    app.openapi()
    assert not missing.exists()
    response = cast(httpx.Client, TestClient(app)).get("/api/v1/replay-backfill/results")
    assert response.status_code == 503
    assert str(missing) not in response.text
    assert not missing.exists()


def test_existing_foreign_schema_and_completed_overwrite_rejected(tmp_path: Path) -> None:
    foreign = tmp_path / "foreign.sqlite3"
    with sqlite3.connect(foreign) as connection:
        connection.execute("CREATE TABLE draws(id INTEGER)")
    engine, _, _ = worker(tmp_path, store=SQLiteBackfillStore(foreign))
    with pytest.raises(ValueError, match="standalone"):
        engine.execute(BackfillSelection(latest=2))
    with sqlite3.connect(foreign) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall() == [("draws",)]
    engine, _, store = worker(tmp_path)
    result = engine.execute(BackfillSelection(latest=2))
    row = store.query(limit=1)["items"][0]
    corrupt = {**row, "error_reason": "changed"}
    corrupt["result_identity"] = identity(
        {k: v for k, v in corrupt.items() if k != "result_identity"}
    )
    with pytest.raises(ValueError, match="CONFLICT"):
        store.save(result["run_id"], corrupt)
    assert store.query(limit=1)["items"][0] == row


def test_legacy_backfill_schema_migrates_without_losing_cells(tmp_path: Path) -> None:
    database = tmp_path / "legacy-replay.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE replay_backfill_schema (
                version INTEGER PRIMARY KEY CHECK(version = 1), checksum TEXT NOT NULL
            );
            CREATE TABLE replay_backfill_runs (
                run_id TEXT PRIMARY KEY, manifest_json TEXT NOT NULL,
                expected_cells INTEGER NOT NULL CHECK(expected_cells > 0),
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            );
            CREATE TABLE replay_backfill_cells (
                cell_identity TEXT PRIMARY KEY,
                lottery_type TEXT NOT NULL, strategy_id TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                execution_version TEXT NOT NULL, dataset_identity TEXT NOT NULL,
                target_draw_id TEXT NOT NULL, target_draw_date TEXT NOT NULL,
                execution_status TEXT NOT NULL CHECK(execution_status IN
                    ('COMPLETE','FAILED','NOT_ELIGIBLE','TYPED_CLOSURE','MISSING','PARTIAL')),
                result_identity TEXT NOT NULL, payload_json TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 1 CHECK(attempts > 0),
                UNIQUE(lottery_type,strategy_id,strategy_version,execution_version,dataset_identity,target_draw_id)
            );
            CREATE TABLE replay_backfill_run_cells (
                run_id TEXT NOT NULL REFERENCES replay_backfill_runs(run_id),
                cell_identity TEXT NOT NULL REFERENCES replay_backfill_cells(cell_identity),
                PRIMARY KEY(run_id,cell_identity)
            );
            CREATE INDEX replay_backfill_filter ON replay_backfill_cells
                (lottery_type,strategy_id,target_draw_date,target_draw_id);
            CREATE INDEX replay_backfill_status ON replay_backfill_cells(execution_status);
            """
        )
        connection.execute(
            "INSERT INTO replay_backfill_schema VALUES(1,?)",
            ("87659eafeb6be707bf711e0951cf9695bfce30748ddc218213c5cb799f33f16c",),
        )
        connection.execute(
            "INSERT INTO replay_backfill_runs(run_id,manifest_json,expected_cells) VALUES(?,?,?)",
            ("old-run", "{}", 1),
        )
        connection.execute(
            "INSERT INTO replay_backfill_cells VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "old-cell",
                "BIG_LOTTO",
                "approved-strategy",
                "v1",
                "old-execution",
                "old-dataset",
                "100000001",
                "2020-01-01",
                "COMPLETE",
                "old-result",
                "{}",
                1,
            ),
        )
        connection.execute(
            "INSERT INTO replay_backfill_run_cells VALUES(?,?)", ("old-run", "old-cell")
        )

    SQLiteBackfillStore(database).prepare(
        {
            "run_id": "new-run",
            "expected_cells": 1,
            "lottery_type": "BIG_LOTTO",
            "dataset_identity": "new-dataset",
            "strategies": [],
            "targets": [],
        }
    )

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version,checksum FROM replay_backfill_schema"
        ).fetchone() == (SCHEMA_VERSION, SCHEMA_CHECKSUM)
        assert connection.execute(
            "SELECT cell_identity,strategy_id,strategy_version,target_draw_id,attempts "
            "FROM replay_backfill_cells"
        ).fetchall() == [("old-cell", "approved-strategy", "v1", "100000001", 1)]
        assert connection.execute(
            "SELECT run_id,cell_identity FROM replay_backfill_run_cells"
        ).fetchall() == [("old-run", "old-cell")]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("lottery", list(LotteryType))
def test_inventory_accounts_for_native_and_current_catalog(lottery: LotteryType) -> None:
    bindings, accounts = native_strategy_inventory(lottery)
    assert bindings
    assert not [a for a in accounts.values() if a["status"] == "BLOCKED"]
    assert {b.strategy.strategy_id for b in bindings} == {
        sid for sid, account in accounts.items() if account["status"] == "EXECUTABLE"
    }
    for binding in bindings:
        assert binding.strategy.native_ticket_count > 0


def test_inventory_maps_the_existing_quickml_successor() -> None:
    bindings, accounts = native_strategy_inventory(LotteryType.BIG_LOTTO)
    quickml_id = "research_biglotto__quick_ml_corrected_successor_v1"
    binding = next(binding for binding in bindings if binding.strategy.strategy_id == quickml_id)
    assert binding.strategy.strategy_version == "v1"
    assert accounts[quickml_id]["status"] == "EXECUTABLE"

    from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory

    item = next(
        item
        for item in load_replay_strategy_inventory().items
        if item.lottery_type is LotteryType.BIG_LOTTO and item.strategy_id == quickml_id
    )
    assert item.backfill_runnable


def test_cli_default_target_respects_writable_registry(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse_unregistered_target(database: Path) -> None:
        raise PermissionError("target is not registered in writable_databases")

    monkeypatch.setattr(
        replay_backfill_cli, "require_project_database_write_ready", refuse_unregistered_target
    )
    assert main(["--lottery-type", "BIG_LOTTO", "--latest", "1500", "--all-strategies"]) == 1
    assert "writable_databases" in capsys.readouterr().err
    assert main(["--schema"]) == 0
    assert "UNIQUE" in capsys.readouterr().out


def test_cli_full_source_worker_storage_chain(
    tmp_path: Path,
    test_only_external_database_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = resolve_local_data_paths(environ={"LOTTOLAB_DATA_DIR": str(tmp_path / "draw-source")})
    document = parse_draw_csv(
        "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source\n"
        + "\n".join(
            f"BIG_LOTTO,{100000001 + n},2020-01-{n + 1:02d},1|2|3|4|5|6,7,synthetic"
            for n in range(12)
        )
        + "\n",
        filename="synthetic.csv",
    )
    assert document.is_valid
    SQLiteDrawDataRepository(paths).apply_valid_import(document)
    source_digest = hashlib.sha256(paths.database.read_bytes()).hexdigest()
    output = test_only_external_database_root / "cli-results.sqlite3"
    args = [
        "--lottery-type",
        "BIG_LOTTO",
        "--source-database",
        str(paths.database),
        "--database",
        str(output),
        "--strategy-id",
        "biglotto_social_wisdom_anti_popularity",
        "--latest",
        "5",
        "--batch-size",
        "2",
    ]
    assert main(
        [*args, "--max-cells", "2"],
        test_only_external_database_root=test_only_external_database_root,
    ) == 2
    partial_output = capsys.readouterr()
    assert json.loads(partial_output.out)["valid_result_cells"] == 2
    assert main(args, test_only_external_database_root=test_only_external_database_root) == 0
    completed_output = capsys.readouterr()
    completed = json.loads(completed_output.out)
    assert completed["valid_result_cells"] == 5
    assert completed["newly_calculated_count"] == 3
    assert "已存在跳過 2、新算 3、失敗 0" in completed_output.err
    assert SQLiteBackfillStore(output, read_only=True).query()["total_count"] == 5
    assert hashlib.sha256(paths.database.read_bytes()).hexdigest() == source_digest


def test_resume_empty_initialization_and_reject_unsafe_paths(tmp_path: Path) -> None:
    empty = tmp_path / "empty.sqlite3"
    empty.touch(mode=0o600)
    engine, _, _ = worker(tmp_path, store=SQLiteBackfillStore(empty))
    assert engine.execute(BackfillSelection(latest=2))["valid_result_cells"] == 2
    linked = tmp_path / "linked.sqlite3"
    linked.symlink_to(empty)
    engine, _, _ = worker(tmp_path, store=SQLiteBackfillStore(linked))
    with pytest.raises(ValueError, match="symlinks"):
        engine.execute(BackfillSelection(latest=2))
    engine, _, _ = worker(tmp_path, store=SQLiteBackfillStore(Path("relative.sqlite3")))
    with pytest.raises(ValueError, match="absolute"):
        engine.execute(BackfillSelection(latest=2))


def test_registry_default_and_allowed_explicit_backfill_targets(
    test_only_external_database_root: Path,
) -> None:
    registered = Path(project_database_environment({})["LOTTOLAB_REPLAY_BACKFILL_DB"])
    assert registered == (
        project_database_paths.PROJECT_ROOT / "data" / "databases" / "replay-backfill.sqlite3"
    )
    assert replay_backfill_cli.resolve_output_database(None) == registered
    assert replay_backfill_cli.resolve_output_database(registered) == registered
    scratch = (
        canonical_project_root()
        / ".task-data"
        / "_scratch"
        / "replay-backfill-stage"
        / "stage.sqlite3"
    )
    assert replay_backfill_cli.resolve_output_database(scratch) == scratch
    test_database = test_only_external_database_root / "pytest-only.sqlite3"
    assert (
        replay_backfill_cli.resolve_output_database(
            test_database,
            test_only_external_database_root=test_only_external_database_root,
        )
        == test_database
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        "data/databases/legacy/old.sqlite3",
        "data/databases/backups/backup.sqlite3",
        "data/databases/imported/import.sqlite3",
        "data/replay/reference/reference.sqlite3",
        "data/replay/active/active.sqlite3",
        ".task-data/receipt.sqlite3",
    ],
)
def test_rejects_protected_project_targets(relative_path: str) -> None:
    target = canonical_project_root() / relative_path
    with pytest.raises(ValueError):
        replay_backfill_cli.resolve_output_database(target)


def test_rejects_library_and_project_external_targets(tmp_path: Path) -> None:
    library_target = (
        Path.home() / "Library" / "Application Support" / "LottoLab" / "backfill.sqlite3"
    )
    with pytest.raises(ValueError):
        replay_backfill_cli.resolve_output_database(library_target)
    with pytest.raises(ValueError):
        replay_backfill_cli.resolve_output_database(tmp_path / "outside.sqlite3")


def test_normal_cli_call_rejects_external_database_and_hides_test_injection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            [
                "--lottery-type",
                "BIG_LOTTO",
                "--database",
                str(tmp_path / "outside.sqlite3"),
                "--strategy-id",
                "biglotto_social_wisdom_anti_popularity",
                "--latest",
                "1",
            ]
        )
        == 1
    )
    assert "explicit database must be" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["--help"])
    help_text = capsys.readouterr().out
    assert "LOTTOLAB_REPLAY_BACKFILL_DB" in help_text
    assert "test_only_external_database_root" not in help_text


def test_main_cli_registers_replay_backfill_command() -> None:
    result = CliRunner().invoke(app, ["replay-backfill", "--schema"])
    assert result.exit_code == 0, result.output
    assert "UNIQUE" in result.output


def _create_empty_backfill_database(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO replay_backfill_schema(version,checksum) VALUES(?,?)",
            (SCHEMA_VERSION, SCHEMA_CHECKSUM),
        )


def _replay_table_counts(database: Path) -> dict[str, int]:
    tables = (
        "replay_backfill_runs",
        "replay_backfill_targets",
        "replay_backfill_strategy_inventory",
        "replay_backfill_sources",
        "replay_backfill_cells",
        "replay_backfill_run_cells",
        "replay_backfill_tickets",
        "replay_backfill_training",
    )
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        return {
            table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in tables
        }


def test_import_stage_merges_read_only_and_duplicate_import_is_idempotent(
    test_only_external_database_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = test_only_external_database_root / "stage.sqlite3"
    engine, _, _ = worker(test_only_external_database_root, store=SQLiteBackfillStore(source))
    engine.execute(BackfillSelection(latest=3))
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    target = test_only_external_database_root / "target.sqlite3"
    _create_empty_backfill_database(target)

    args = ["import-stage", "--source", str(source), "--database", str(target)]
    assert main(
        args, test_only_external_database_root=test_only_external_database_root
    ) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["schema_version"] == SCHEMA_VERSION
    assert first["added_rows"]["replay_backfill_runs"] == 1
    assert first["added_rows"]["replay_backfill_cells"] == 3
    assert first["target_after_rows"]["replay_backfill_tickets"] > 0
    assert first["source_rows"] == first["target_after_rows"]
    counts_after_first = _replay_table_counts(target)

    assert main(
        args, test_only_external_database_root=test_only_external_database_root
    ) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["added_total"] == 0
    assert second["skipped_total"] > 0
    assert second["target_before_rows"] == second["target_after_rows"]
    assert _replay_table_counts(target) == counts_after_first
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash


def test_import_stage_rejects_schema_version_mismatch_before_writing(
    test_only_external_database_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = test_only_external_database_root / "wrong-version.sqlite3"
    _create_empty_backfill_database(source)
    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "UPDATE replay_backfill_schema SET version=?", (SCHEMA_VERSION - 1,)
        )
    target = test_only_external_database_root / "target.sqlite3"
    _create_empty_backfill_database(target)

    assert (
        main(
            ["import-stage", "--source", str(source), "--database", str(target)],
            test_only_external_database_root=test_only_external_database_root,
        )
        == 1
    )
    assert "schema version or checksum" in capsys.readouterr().err
    assert _replay_table_counts(target) == {key: 0 for key in _replay_table_counts(target)}

_IMPORT_STAGE_TABLES_FOR_CONFLICT_TESTS = (
    "replay_backfill_runs",
    "replay_backfill_targets",
    "replay_backfill_strategy_inventory",
    "replay_backfill_sources",
    "replay_backfill_cells",
    "replay_backfill_run_cells",
    "replay_backfill_tickets",
    "replay_backfill_training",
)


def _make_test_only_stage_and_target(test_only_root: Path) -> tuple[Path, Path]:
    source = test_only_root / "stage-test-only.sqlite3"
    engine, _, _ = worker(test_only_root, store=SQLiteBackfillStore(source))
    engine.execute(BackfillSelection(latest=3))
    with sqlite3.connect(source) as connection:
        run_row = connection.execute(
            "SELECT run_id,manifest_json FROM replay_backfill_runs"
        ).fetchone()
        assert run_row is not None
        manifest = json.loads(str(run_row[1]))
        manifest["synthetic_scope"] = "TEST_ONLY"
        connection.execute(
            "UPDATE replay_backfill_runs SET manifest_json=? WHERE run_id=?",
            (json.dumps(manifest, sort_keys=True, separators=(",", ":")), run_row[0]),
        )
    target = test_only_root / "target-test-only.sqlite3"
    target.write_bytes(source.read_bytes())
    return source, target


def _import_stage_snapshot(database: Path) -> dict[str, tuple[tuple[Any, ...], ...]]:
    with sqlite3.connect(database) as connection:
        return {
            table: tuple(
                tuple(row)
                for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')
            )
            for table in _IMPORT_STAGE_TABLES_FOR_CONFLICT_TESTS
        }


def _give_stage_a_new_test_run_id(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        run_row = connection.execute(
            "SELECT run_id,manifest_json FROM replay_backfill_runs"
        ).fetchone()
        assert run_row is not None
        old_run_id = str(run_row[0])
        new_run_id = f"TEST_ONLY_SECOND_RUN:{old_run_id}"
        manifest = json.loads(str(run_row[1]))
        manifest["synthetic_run"] = "TEST_ONLY_SECOND_RUN"
        connection.execute(
            "UPDATE replay_backfill_runs SET run_id=?,manifest_json=? WHERE run_id=?",
            (
                new_run_id,
                json.dumps(manifest, sort_keys=True, separators=(",", ":")),
                old_run_id,
            ),
        )
        for table in (
            "replay_backfill_targets",
            "replay_backfill_strategy_inventory",
            "replay_backfill_sources",
            "replay_backfill_run_cells",
        ):
            connection.execute(
                f'UPDATE "{table}" SET run_id=? WHERE run_id=?',
                (new_run_id, old_run_id),
            )


def _mutate_stage_cell_for_test_conflict(database: Path, field: str) -> None:
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT cell_identity,result_identity,execution_status,payload_json "
            "FROM replay_backfill_cells ORDER BY cell_identity LIMIT 1"
        ).fetchone()
        assert row is not None
        cell_identity = str(row[0])
        if field == "result_identity":
            connection.execute(
                "UPDATE replay_backfill_cells SET result_identity=? WHERE cell_identity=?",
                ("TEST_ONLY_DIFFERENT_RESULT_IDENTITY", cell_identity),
            )
        elif field == "payload_json":
            payload = json.loads(str(row[3]))
            payload["synthetic_conflict"] = "TEST_ONLY_DIFFERENT_PAYLOAD"
            connection.execute(
                "UPDATE replay_backfill_cells SET payload_json=? WHERE cell_identity=?",
                (json.dumps(payload, sort_keys=True, separators=(",", ":")), cell_identity),
            )
        elif field == "execution_status":
            status = "FAILED" if str(row[2]) != "FAILED" else "COMPLETE"
            connection.execute(
                "UPDATE replay_backfill_cells SET execution_status=? WHERE cell_identity=?",
                (status, cell_identity),
            )
        else:
            raise AssertionError(f"unsupported synthetic conflict field: {field}")


def _ensure_test_only_training_row(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT cell_identity FROM replay_backfill_cells ORDER BY cell_identity LIMIT 1"
        ).fetchone()
        assert row is not None
        cell_identity = str(row[0])
        connection.execute(
            "INSERT OR IGNORE INTO replay_backfill_training "
            "(cell_identity,training_status,model_version,training_cutoff,training_artifact_id,"
            "input_source_hash,trainer_identity,training_artifact_hash) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (cell_identity, "TEST_ONLY", None, None, None, None, None, None),
        )


def test_import_stage_reuses_matching_result_with_remapped_cell_identity_and_is_idempotent(
    test_only_external_database_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, target = _make_test_only_stage_and_target(test_only_external_database_root)
    with sqlite3.connect(target) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        row = connection.execute(
            "SELECT cell_identity FROM replay_backfill_cells ORDER BY cell_identity LIMIT 1"
        ).fetchone()
        assert row is not None
        source_identity = str(row[0])
        target_identity = f"TEST_ONLY_TARGET_IDENTITY:{source_identity}"
        connection.execute(
            "UPDATE replay_backfill_cells SET cell_identity=? WHERE cell_identity=?",
            (target_identity, source_identity),
        )
        for table in (
            "replay_backfill_run_cells",
            "replay_backfill_tickets",
            "replay_backfill_training",
        ):
            connection.execute(
                f'UPDATE "{table}" SET cell_identity=? WHERE cell_identity=?',
                (target_identity, source_identity),
            )
    before = _import_stage_snapshot(target)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    args = ["import-stage", "--source", str(source), "--database", str(target)]

    assert main(
        args,
        test_only_external_database_root=test_only_external_database_root,
    ) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["added_total"] == 0
    assert first["target_before_rows"] == first["target_after_rows"]
    assert _import_stage_snapshot(target) == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT 1 FROM replay_backfill_run_cells WHERE cell_identity=?",
            (target_identity,),
        ).fetchone() is not None
        assert connection.execute(
            "SELECT 1 FROM replay_backfill_cells WHERE cell_identity=?",
            (source_identity,),
        ).fetchone() is None

    assert main(
        args,
        test_only_external_database_root=test_only_external_database_root,
    ) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["added_total"] == 0
    assert second["target_before_rows"] == second["target_after_rows"]
    assert _import_stage_snapshot(target) == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash


@pytest.mark.parametrize("field", ["result_identity", "payload_json", "execution_status"])
def test_import_stage_rejects_cell_result_conflicts_and_rolls_back_new_run(
    test_only_external_database_root: Path,
    capsys: pytest.CaptureFixture[str],
    field: str,
) -> None:
    source, target = _make_test_only_stage_and_target(test_only_external_database_root)
    _give_stage_a_new_test_run_id(source)
    _mutate_stage_cell_for_test_conflict(source, field)
    before = _import_stage_snapshot(target)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    args = ["import-stage", "--source", str(source), "--database", str(target)]

    assert main(
        args,
        test_only_external_database_root=test_only_external_database_root,
    ) == 1
    assert "stage cell conflicts with an existing natural key" in capsys.readouterr().err
    assert _import_stage_snapshot(target) == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT 1 FROM replay_backfill_runs WHERE run_id LIKE 'TEST_ONLY_SECOND_RUN:%'"
        ).fetchone() is None
        assert connection.execute(
            "SELECT 1 FROM replay_backfill_run_cells WHERE run_id LIKE 'TEST_ONLY_SECOND_RUN:%'"
        ).fetchone() is None


@pytest.mark.parametrize("table", ["replay_backfill_tickets", "replay_backfill_training"])
def test_import_stage_rejects_conflicting_child_rows_and_rolls_back(
    test_only_external_database_root: Path,
    capsys: pytest.CaptureFixture[str],
    table: str,
) -> None:
    source, target = _make_test_only_stage_and_target(test_only_external_database_root)
    _give_stage_a_new_test_run_id(source)
    if table == "replay_backfill_training":
        _ensure_test_only_training_row(source)
        _ensure_test_only_training_row(target)
    with sqlite3.connect(target) as connection:
        if table == "replay_backfill_tickets":
            connection.execute(
                "UPDATE replay_backfill_tickets SET prize_tier='TEST_ONLY_CHILD_CONFLICT' "
                "WHERE rowid=(SELECT rowid FROM replay_backfill_tickets ORDER BY rowid LIMIT 1)"
            )
        else:
            connection.execute(
                "UPDATE replay_backfill_training SET training_artifact_hash=? "
                "WHERE rowid=(SELECT rowid FROM replay_backfill_training ORDER BY rowid LIMIT 1)",
                ("TEST_ONLY_CHILD_CONFLICT",),
            )
    before = _import_stage_snapshot(target)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    args = ["import-stage", "--source", str(source), "--database", str(target)]

    assert main(
        args,
        test_only_external_database_root=test_only_external_database_root,
    ) == 1
    assert f"stage row conflicts with an existing identity: {table}" in capsys.readouterr().err
    assert _import_stage_snapshot(target) == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    with sqlite3.connect(target) as connection:
        assert connection.execute(
            "SELECT 1 FROM replay_backfill_runs WHERE run_id LIKE 'TEST_ONLY_SECOND_RUN:%'"
        ).fetchone() is None
        assert connection.execute(
            "SELECT 1 FROM replay_backfill_run_cells WHERE run_id LIKE 'TEST_ONLY_SECOND_RUN:%'"
        ).fetchone() is None


def test_import_stage_rejects_conflicting_manifest_and_rolls_back(
    test_only_external_database_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, target = _make_test_only_stage_and_target(test_only_external_database_root)
    with sqlite3.connect(target) as connection:
        connection.execute(
            "UPDATE replay_backfill_runs SET manifest_json=?",
            (json.dumps({"synthetic_scope": "TEST_ONLY_TARGET_CONFLICT"}),),
        )
    before = _import_stage_snapshot(target)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    args = ["import-stage", "--source", str(source), "--database", str(target)]

    assert main(
        args,
        test_only_external_database_root=test_only_external_database_root,
    ) == 1
    assert "stage run ID conflicts with an existing target manifest" in capsys.readouterr().err
    assert _import_stage_snapshot(target) == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
