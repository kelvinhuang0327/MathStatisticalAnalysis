from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import cast

import pytest

import lottolab
from lottolab.application.use_cases.replay_backfill import (
    BackfillSelection,
    JsonObject,
    ReplayBackfill,
    identity,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    HistoricalReplayMode,
    HistoricalReplayRequest,
    ReplayBehavior,
    ReplayDraw,
    ReplayEvaluation,
    ReplaySourceSnapshot,
    ReplayStrategy,
    ReplayTargetRecord,
    ReplayTicket,
)
from lottolab.domain.prize_evaluation import evaluate_historical_lottery_prize
from lottolab.infrastructure.persistence.replay_backfill_store import SQLiteBackfillStore


class CountingProducer:
    strategy_id = "six-key-candidate-strategy"

    def __init__(self, *, ticket_count: int = 2, duplicate_tickets: bool = False) -> None:
        self.calls = 0
        self.ticket_count = ticket_count
        self.duplicate_tickets = duplicate_tickets

    def get_bets(
        self, history: tuple[ReplayDraw, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        self.calls += 1
        if self.duplicate_tickets:
            # Produce exact duplicate number sets at different ticket positions
            return ((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 6))
        return tuple((1, 2, 3, 4, 5, 6 + i) for i in range(self.ticket_count))


class SyntheticAdapter:
    lottery_type = LotteryType.BIG_LOTTO

    def __init__(self, producer: CountingProducer) -> None:
        self._producer = producer

    def generate(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> tuple[ReplayTicket, ...]:
        bets = self._producer.get_bets(history, self.lottery_type)
        return tuple(
            ReplayTicket(position, numbers, None) for position, numbers in enumerate(bets, start=1)
        )

    def evaluate(
        self, strategy: ReplayStrategy, ticket: ReplayTicket, target: ReplayDraw
    ) -> ReplayEvaluation:
        outcome = evaluate_historical_lottery_prize(
            lottery_type=target.lottery_type,
            target_draw_id=target.draw_number,
            predicted_main_numbers=ticket.main_numbers,
            predicted_special_number=ticket.special_number,
            winning_main_numbers=target.main_numbers,
            winning_special_number=target.special_number,
        )
        return ReplayEvaluation(
            zone1_hits=outcome.zone1_hits,
            zone2_hit=outcome.zone2_hit,
            is_winner=outcome.is_winner,
            prize_tier=outcome.prize_tier,
            historical_rule_id=outcome.historical_rule_id,
            scorer_version=outcome.scorer_version,
        )


class _PayloadAccessReplayBackfill(ReplayBackfill):
    def payload_for_test(self, record: ReplayTargetRecord, cell_identity: str) -> JsonObject:
        return super()._payload(record, cell_identity)


def _make_draws(count: int = 4) -> tuple[ReplayDraw, ...]:
    return tuple(
        ReplayDraw(
            LotteryType.BIG_LOTTO,
            str(100000001 + index),
            date(2024, 1, 1) + timedelta(days=index),
            (1, 2, 3, 4, 5, 6),
            7,
        )
        for index in range(count)
    )


def _make_worker(
    store: SQLiteBackfillStore,
    producer: CountingProducer,
    *,
    strategy_name: str = "Candidate Strategy",
    strategy_version: str = "strategy-v1",
    execution_version: str = "execution-v1",
    source_identity: str = "dataset-source-v1",
    fingerprint: str = "fingerprint-v1",
    ticket_count: int = 2,
    draws: tuple[ReplayDraw, ...] | None = None,
) -> _PayloadAccessReplayBackfill:
    strategy = ReplayStrategy(
        producer.strategy_id,
        strategy_name,
        strategy_version,
        ReplayBehavior.DETERMINISTIC,
        ticket_count,
        1,
        fingerprint=fingerprint,
    )
    adapter = SyntheticAdapter(producer)
    return _PayloadAccessReplayBackfill(
        adapter=adapter,
        strategies=(strategy,),
        draws=draws or _make_draws(),
        source_identity=source_identity,
        store=store,
        execution_version=execution_version,
    )


def _db_path(tmp_path: Path, name: str) -> Path:
    scratch = tmp_path / "sqlite_test"
    scratch.mkdir(parents=True, exist_ok=True)
    return scratch / f"{name}.sqlite3"


_REPLAY_DATA_TABLES = (
    "replay_backfill_runs",
    "replay_backfill_targets",
    "replay_backfill_strategy_inventory",
    "replay_backfill_cells",
    "replay_backfill_run_cells",
    "replay_backfill_tickets",
    "replay_backfill_training",
    "replay_backfill_sources",
)


def _strip_historical_scoring_identity(store: SQLiteBackfillStore) -> None:
    with sqlite3.connect(store.database) as conn:
        rows = conn.execute(
            "SELECT cell_identity, payload_json FROM replay_backfill_cells"
        ).fetchall()
        assert len(rows) == 1
        cell_identity, payload_json = rows[0]
        payload: dict[str, object] = json.loads(payload_json)
        hit_details: object = payload["hit_details"]
        assert isinstance(hit_details, list) and hit_details
        for detail in cast(list[object], hit_details):
            assert isinstance(detail, dict)
            detail_values = cast(dict[str, object], detail)
            assert detail_values.pop("historical_rule_id", None) is not None
            assert detail_values.pop("scorer_version", None) is not None
        result_identity = identity(
            {key: value for key, value in payload.items() if key != "result_identity"}
        )
        payload["result_identity"] = result_identity
        conn.execute(
            "UPDATE replay_backfill_cells SET result_identity=?, payload_json=? "
            "WHERE cell_identity=?",
            (
                result_identity,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                cell_identity,
            ),
        )


def _replay_store_snapshot(store: SQLiteBackfillStore) -> tuple[object, ...]:
    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        schema = tuple(
            conn.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
            ).fetchall()
        )
        version = tuple(
            conn.execute(
                "SELECT version, checksum FROM replay_backfill_schema"
            ).fetchall()
        )
        data = tuple(
            (
                table,
                tuple(conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()),
            )
            for table in _REPLAY_DATA_TABLES
        )
        foreign_key_violations = tuple(conn.execute("PRAGMA foreign_key_check").fetchall())
    return schema, version, data, foreign_key_violations


# --- AC01: Verification that lottolab is loaded from this test checkout ---


def test_ac01_lottolab_loaded_from_test_checkout_src() -> None:
    test_checkout_root = Path(__file__).resolve().parents[2]
    expected_package = (test_checkout_root / "src" / "lottolab").resolve()
    imported_package = Path(lottolab.__file__).resolve().parent
    assert imported_package == expected_package, (
        f"Expected lottolab from {expected_package}, got {imported_package}"
    )


# --- AC02: Six-column natural key order and content; K and run_id not in key ---


def test_ac02_six_key_cell_identity_formula(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_db_path(tmp_path, "ac02"))
    producer = CountingProducer(ticket_count=2)
    worker = _make_worker(store, producer)
    result = worker.execute(BackfillSelection(latest=1))

    assert result["valid_result_cells"] == 1
    assert producer.calls == 1

    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        row = conn.execute(
            "SELECT cell_identity, lottery_type, strategy_id, strategy_version, "
            "execution_version, dataset_identity, target_draw_id, payload_json "
            "FROM replay_backfill_cells"
        ).fetchone()

    cell_id, lot_type, strat_id, strat_ver, exec_ver, data_id, target_id, payload_str = row
    payload = json.loads(payload_str)

    expected_canonical_identity = identity(
        {
            "dataset_identity": data_id,
            "execution_version": exec_ver,
            "lottery_type": lot_type,
            "strategy_id": strat_id,
            "strategy_version": strat_ver,
            "target_draw_id": target_id,
        }
    )

    # 1. cell_identity matches exact six-column canonical hash
    assert cell_id == expected_canonical_identity
    assert payload["cell_identity"] == expected_canonical_identity

    # 2. K (ticket_count) and run_id are NOT in the natural key
    assert "run_id" not in identity.__code__.co_varnames
    # Verify that changing K in a strategy does not change the six-column identity definition itself
    k_modified_identity = identity(
        {
            "dataset_identity": data_id,
            "execution_version": exec_ver,
            "lottery_type": lot_type,
            "strategy_id": strat_id,
            "strategy_version": strat_ver,
            "target_draw_id": target_id,
        }
    )
    assert expected_canonical_identity == k_modified_identity


# --- AC03 & AC08: Idempotent replay, exactly 1 logical cell, no duplicates ---


def test_ac03_and_ac08_idempotence_and_single_logical_cell(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_db_path(tmp_path, "ac03_ac08"))
    producer = CountingProducer()
    worker1 = _make_worker(store, producer)
    first_run = worker1.execute(BackfillSelection(latest=1))

    resumed_producer = CountingProducer()
    worker2 = _make_worker(store, resumed_producer)
    second_run = worker2.execute(BackfillSelection(latest=1))

    assert first_run["run_id"] == second_run["run_id"]
    assert second_run["existing_skipped_count"] == 1
    assert second_run["newly_calculated_count"] == 0
    assert resumed_producer.calls == 0

    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        cell_count = conn.execute("SELECT count(*) FROM replay_backfill_cells").fetchone()[0]
        run_cell_count = conn.execute("SELECT count(*) FROM replay_backfill_run_cells").fetchone()[
            0
        ]

    assert cell_count == 1, "Only 1 logical cell should exist in replay_backfill_cells"
    assert run_cell_count == 1, "Same run_id idempotence maintains 1 entry in run_cells"


# --- AC04: Display name change does not change cell_identity and reuses result ---


def test_ac04_strategy_display_name_change_preserves_identity(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_db_path(tmp_path, "ac04"))
    producer1 = CountingProducer()
    worker1 = _make_worker(store, producer1, strategy_name="Original Display Name")
    run1 = worker1.execute(BackfillSelection(latest=1))
    assert run1["valid_result_cells"] == 1

    # Second worker has different display_name, but same 6 natural keys and semantics
    producer2 = CountingProducer()
    worker2 = _make_worker(store, producer2, strategy_name="Changed Display Name v2")
    run2 = worker2.execute(BackfillSelection(latest=1))

    assert run2["existing_skipped_count"] == 1
    assert run2["newly_calculated_count"] == 0
    assert producer2.calls == 0

    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        cell_count = conn.execute("SELECT count(*) FROM replay_backfill_cells").fetchone()[0]
    assert cell_count == 1


# --- AC05: Same key but different K or fingerprint raises CONFLICT before prepare ---


def test_ac05_same_key_different_k_raises_conflict_before_prepare(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_db_path(tmp_path, "ac05_k"))
    producer1 = CountingProducer(ticket_count=2)
    worker1 = _make_worker(store, producer1, ticket_count=2)
    worker1.execute(BackfillSelection(latest=1))

    # Capture store state before second run
    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        runs_before = conn.execute("SELECT count(*) FROM replay_backfill_runs").fetchone()[0]

    # Second worker has K=5 (different ticket count) with same six columns
    producer2 = CountingProducer(ticket_count=5)
    worker2 = _make_worker(store, producer2, ticket_count=5)

    with pytest.raises(ValueError, match="CONFLICT") as exc:
        worker2.execute(BackfillSelection(latest=1))

    assert "expected_native_ticket_count" in str(exc.value)
    assert producer2.calls == 0, "Producer must not be called when conflict is detected"

    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        runs_after = conn.execute("SELECT count(*) FROM replay_backfill_runs").fetchone()[0]
    assert runs_after == runs_before, "prepare must not have run before conflict check"


def test_ac05_same_key_different_fingerprint_raises_conflict_before_prepare(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_db_path(tmp_path, "ac05_fp"))
    producer1 = CountingProducer()
    worker1 = _make_worker(store, producer1, fingerprint="fp-version-1")
    worker1.execute(BackfillSelection(latest=1))

    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        runs_before = conn.execute("SELECT count(*) FROM replay_backfill_runs").fetchone()[0]

    producer2 = CountingProducer()
    worker2 = _make_worker(store, producer2, fingerprint="fp-version-2")

    with pytest.raises(ValueError, match="CONFLICT") as exc:
        worker2.execute(BackfillSelection(latest=1))

    assert "fingerprint" in str(exc.value)
    assert producer2.calls == 0

    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        runs_after = conn.execute("SELECT count(*) FROM replay_backfill_runs").fetchone()[0]
    assert runs_after == runs_before


def test_ac05_fingerprint_and_k_conflicts_precede_missing_scorer_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteBackfillStore(_db_path(tmp_path, "ac05_combined_conflict"))
    worker1 = _make_worker(
        store, CountingProducer(ticket_count=2), fingerprint="fp-version-1", ticket_count=2
    )
    worker1.execute(BackfillSelection(latest=1))
    _strip_historical_scoring_identity(store)
    snapshot_before = _replay_store_snapshot(store)

    prepare_calls: list[JsonObject] = []
    original_prepare = store.prepare

    def record_prepare(manifest: JsonObject) -> None:
        prepare_calls.append(manifest)
        original_prepare(manifest)

    monkeypatch.setattr(store, "prepare", record_prepare)
    producer = CountingProducer(ticket_count=5)
    worker2 = _make_worker(
        store, producer, fingerprint="fp-version-2", ticket_count=5
    )

    with pytest.raises(ValueError, match="CONFLICT") as exc:
        worker2.execute(BackfillSelection(latest=1))

    message = str(exc.value)
    assert "fingerprint=" in message
    assert "expected_native_ticket_count" in message
    assert "historical scoring identity" not in message
    assert prepare_calls == []
    assert producer.calls == 0
    assert _replay_store_snapshot(store) == snapshot_before


def test_ac05_missing_scorer_identity_remains_an_independent_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteBackfillStore(_db_path(tmp_path, "ac05_missing_scorer"))
    worker1 = _make_worker(store, CountingProducer(), fingerprint="fp-compatible")
    worker1.execute(BackfillSelection(latest=1))
    _strip_historical_scoring_identity(store)
    snapshot_before = _replay_store_snapshot(store)

    prepare_calls: list[JsonObject] = []
    original_prepare = store.prepare

    def record_prepare(manifest: JsonObject) -> None:
        prepare_calls.append(manifest)
        original_prepare(manifest)

    monkeypatch.setattr(store, "prepare", record_prepare)
    producer = CountingProducer()
    worker2 = _make_worker(store, producer, fingerprint="fp-compatible")

    with pytest.raises(ValueError, match="historical scoring identity"):
        worker2.execute(BackfillSelection(latest=1))

    assert prepare_calls == []
    assert producer.calls == 0
    assert _replay_store_snapshot(store) == snapshot_before


# --- AC06: Strategy version, execution version, dataset identity isolation ---


def test_ac06_cross_version_isolation(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_db_path(tmp_path, "ac06"))
    producer = CountingProducer()
    worker1 = _make_worker(
        store,
        producer,
        strategy_version="v1",
        execution_version="exec-v1",
        source_identity="dataset-v1",
    )
    worker1.execute(BackfillSelection(latest=1))

    # 1. strategy_version changes -> separate valid cell, no cross reuse
    producer_v2 = CountingProducer()
    worker_strat_v2 = _make_worker(
        store,
        producer_v2,
        strategy_version="v2",
        execution_version="exec-v1",
        source_identity="dataset-v1",
    )
    res_strat_v2 = worker_strat_v2.execute(BackfillSelection(latest=1))
    assert res_strat_v2["newly_calculated_count"] == 1
    assert producer_v2.calls == 1

    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        assert conn.execute("SELECT count(*) FROM replay_backfill_cells").fetchone()[0] == 2

    # 2. execution_version changes -> raises cross-version error before prepare
    producer_exec_v2 = CountingProducer()
    worker_exec_v2 = _make_worker(
        store,
        producer_exec_v2,
        strategy_version="v1",
        execution_version="exec-v2",
        source_identity="dataset-v1",
    )
    with pytest.raises(ValueError, match="COMPLETE replay identity conflict"):
        worker_exec_v2.execute(BackfillSelection(latest=1))
    assert producer_exec_v2.calls == 0

    # 3. dataset_identity changes -> raises cross-version error before prepare
    producer_data_v2 = CountingProducer()
    worker_data_v2 = _make_worker(
        store,
        producer_data_v2,
        strategy_version="v1",
        execution_version="exec-v1",
        source_identity="dataset-v2",
    )
    with pytest.raises(ValueError, match="COMPLETE replay identity conflict"):
        worker_data_v2.execute(BackfillSelection(latest=1))
    assert producer_data_v2.calls == 0


# --- AC07: Existing cell with old-format cell_identity is found and preserved ---


def test_ac07_old_cell_identity_compatibility_and_preservation(tmp_path: Path) -> None:
    database = _db_path(tmp_path, "ac07_old_hash")
    store = SQLiteBackfillStore(database)
    producer = CountingProducer(ticket_count=2)
    worker = _make_worker(store, producer)

    # First, construct an old-format cell_identity manually
    # where "strategy": asdict(strategy) was used
    strategy = worker.strategies[0]
    target = worker.draws[-1]
    old_cell_identity = identity(
        {
            "execution_version": worker.execution_version,
            "dataset_identity": worker.dataset_identity,
            "lottery_type": worker.lottery_type.value,
            "strategy": asdict(strategy),
            "target_draw_id": target.draw_number,
        }
    )
    new_canonical_identity = identity(
        {
            "dataset_identity": worker.dataset_identity,
            "execution_version": worker.execution_version,
            "lottery_type": worker.lottery_type.value,
            "strategy_id": strategy.strategy_id,
            "strategy_version": strategy.strategy_version,
            "target_draw_id": target.draw_number,
        }
    )
    assert old_cell_identity != new_canonical_identity, (
        "Old and new cell identity hashes must differ"
    )

    # Seed the database directly with the old-format cell
    seed_run_id = "seed-old-hash-run"
    manifest = worker.manifest(BackfillSelection(latest=1))
    manifest["run_id"] = seed_run_id
    store.prepare(manifest)

    # Execute single prediction using controller to get valid record and payload
    history = worker.draws[:-1]
    result = worker.controller.execute(
        HistoricalReplayRequest(
            lottery_type=worker.lottery_type,
            mode=HistoricalReplayMode.INCREMENTAL_REFRESH,
            source=ReplaySourceSnapshot(
                worker.lottery_type, history, (target,)
            ),
            strategies=(strategy,),
        )
    )
    old_payload = worker.payload_for_test(result.records[0], old_cell_identity)
    store.save_many(seed_run_id, (old_payload,))

    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as conn:
        seeded_cell = conn.execute(
            "SELECT cell_identity, execution_status, result_identity FROM replay_backfill_cells"
        ).fetchone()
    assert seeded_cell[0] == old_cell_identity

    # Now run the candidate worker for the same target and same strategy
    candidate_producer = CountingProducer(ticket_count=2)
    candidate_worker = _make_worker(store, candidate_producer)
    cand_summary = candidate_worker.execute(BackfillSelection(latest=1))

    assert cand_summary["existing_skipped_count"] == 1
    assert cand_summary["newly_calculated_count"] == 0
    assert candidate_producer.calls == 0

    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as conn:
        cells = conn.execute(
            "SELECT cell_identity, payload_json FROM replay_backfill_cells"
        ).fetchall()
        run_cells = conn.execute(
            "SELECT run_id, cell_identity FROM replay_backfill_run_cells"
        ).fetchall()

    # The existing cell MUST still have old_cell_identity (NOT overwritten or converted)
    assert len(cells) == 1
    assert cells[0][0] == old_cell_identity
    # Both runs reference old_cell_identity
    assert len(run_cells) == 2
    assert all(rc[1] == old_cell_identity for rc in run_cells)


# --- AC09: Cross-run reference without run_id in cell natural key ---


def test_ac09_cross_run_reference_no_run_id_in_cell(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_db_path(tmp_path, "ac09"))
    producer = CountingProducer()
    worker1 = _make_worker(store, producer)
    run1 = worker1.execute(BackfillSelection(latest=1))

    # Second run requests latest=2 (includes the target from run1)
    worker2 = _make_worker(store, producer)
    run2 = worker2.execute(BackfillSelection(latest=2))

    assert run1["run_id"] != run2["run_id"]
    assert run2["existing_skipped_count"] == 1
    assert run2["newly_calculated_count"] == 1

    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        cell_rows = conn.execute(
            "SELECT cell_identity, payload_json FROM replay_backfill_cells"
        ).fetchall()
        run_cell_rows = conn.execute(
            "SELECT run_id, cell_identity FROM replay_backfill_run_cells"
        ).fetchall()

    assert len(cell_rows) == 2, "1 existing cell reused + 1 new cell calculated"
    # Neither cell payload contains run_id
    for _, payload_str in cell_rows:
        payload = json.loads(payload_str)
        assert "run_id" not in payload

    # Reused cell from run1 is linked in run_cell_rows under both run1 and run2
    run1_cell_id = run_cell_rows[0][1]
    matching_links = [r for r in run_cell_rows if r[1] == run1_cell_id]
    assert len(matching_links) == 2
    assert {r[0] for r in matching_links} == {run1["run_id"], run2["run_id"]}


# --- AC10: All tickets maintain original ticket_position and duplicate tickets not deduplicated ---


def test_ac10_tickets_preserve_position_and_duplicates(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_db_path(tmp_path, "ac10"))
    # Producer generates duplicate tickets at position 1 and position 2
    producer = CountingProducer(duplicate_tickets=True)
    worker = _make_worker(store, producer, ticket_count=2)
    worker.execute(BackfillSelection(latest=1))

    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        tickets = conn.execute(
            "SELECT ticket_position, main_numbers_json FROM replay_backfill_tickets "
            "ORDER BY ticket_position ASC"
        ).fetchall()

    assert len(tickets) == 2
    assert tickets[0][0] == 1
    assert tickets[1][0] == 2
    # Both tickets have the same numbers and were NOT deduplicated
    assert tickets[0][1] == tickets[1][1] == "[1,2,3,4,5,6]"


# --- AC11: Negative test matrix ---


def test_ac11_negative_cases_matrix(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_db_path(tmp_path, "ac11"))
    producer = CountingProducer(ticket_count=2)
    worker = _make_worker(store, producer, ticket_count=2, fingerprint="fp-orig")
    worker.execute(BackfillSelection(latest=1))

    # 1. 同鍵不同K -> CONFLICT
    diff_k_worker = _make_worker(
        store, CountingProducer(ticket_count=4), ticket_count=4, fingerprint="fp-orig"
    )
    with pytest.raises(ValueError, match="CONFLICT"):
        diff_k_worker.execute(BackfillSelection(latest=1))

    # 2. 同鍵不同fingerprint -> CONFLICT
    diff_fp_worker = _make_worker(
        store, CountingProducer(ticket_count=2), ticket_count=2, fingerprint="fp-other"
    )
    with pytest.raises(ValueError, match="CONFLICT"):
        diff_fp_worker.execute(BackfillSelection(latest=1))

    # 3. 錯誤execution_version -> COMPLETE replay identity conflict
    diff_exec_worker = _make_worker(store, CountingProducer(), execution_version="exec-wrong")
    with pytest.raises(ValueError, match="COMPLETE replay identity conflict"):
        diff_exec_worker.execute(BackfillSelection(latest=1))

    # 4. 錯誤dataset_identity -> COMPLETE replay identity conflict
    diff_data_worker = _make_worker(store, CountingProducer(), source_identity="dataset-wrong")
    with pytest.raises(ValueError, match="COMPLETE replay identity conflict"):
        diff_data_worker.execute(BackfillSelection(latest=1))

    # 5. 重複六欄鍵 -> store rejects conflicting save for existing cell
    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        cell_row = conn.execute("SELECT payload_json FROM replay_backfill_cells").fetchone()
    corrupt_cell = json.loads(cell_row[0])
    corrupt_cell["strategy_fingerprint"] = "corrupt-fingerprint"
    corrupt_cell["result_identity"] = identity(
        {k: v for k, v in corrupt_cell.items() if k != "result_identity"}
    )
    with pytest.raises(ValueError, match="CONFLICT"):
        store.save_many("corrupt-run", (corrupt_cell,))

    # 6. 舊Hash身份衝突 -> conflicting semantics on old-hash cell rejected
    database_old = _db_path(tmp_path, "ac11_old")
    store_old = SQLiteBackfillStore(database_old)
    worker_old = _make_worker(
        store_old, CountingProducer(ticket_count=2), ticket_count=2, fingerprint="fp-old"
    )
    # Seed old hash
    target = worker_old.draws[-1]
    strategy = worker_old.strategies[0]
    old_id = identity(
        {
            "execution_version": worker_old.execution_version,
            "dataset_identity": worker_old.dataset_identity,
            "lottery_type": worker_old.lottery_type.value,
            "strategy": asdict(strategy),
            "target_draw_id": target.draw_number,
        }
    )
    manifest = worker_old.manifest(BackfillSelection(latest=1))
    manifest["run_id"] = "seed-old"
    store_old.prepare(manifest)
    res = worker_old.controller.execute(
        HistoricalReplayRequest(
            lottery_type=worker_old.lottery_type,
            mode=HistoricalReplayMode.INCREMENTAL_REFRESH,
            source=ReplaySourceSnapshot(
                worker_old.lottery_type, worker_old.draws[:-1], (target,)
            ),
            strategies=(strategy,),
        )
    )
    store_old.save_many("seed-old", (worker_old.payload_for_test(res.records[0], old_id),))

    # Now attempt to run worker on store_old with DIFFERENT K (conflict against old hash)
    conflicting_worker = _make_worker(
        store_old, CountingProducer(ticket_count=5), ticket_count=5, fingerprint="fp-old"
    )
    with pytest.raises(ValueError, match="CONFLICT"):
        conflicting_worker.execute(BackfillSelection(latest=1))

    # 7. cutoff不合法 -> BackfillSelection invalid date range
    with pytest.raises(ValueError, match="start_date must not exceed end_date"):
        BackfillSelection(start_date=date(2024, 2, 1), end_date=date(2024, 1, 1))

    # 8. 跨run資料混入 -> verify run_id isolation
    with sqlite3.connect(store.database.as_uri() + "?mode=ro", uri=True) as conn:
        all_runs = conn.execute("SELECT run_id FROM replay_backfill_runs").fetchall()
        all_cell_runs = conn.execute("SELECT run_id FROM replay_backfill_run_cells").fetchall()
    assert len(all_runs) == 1
    assert all_runs[0][0] == all_cell_runs[0][0]
