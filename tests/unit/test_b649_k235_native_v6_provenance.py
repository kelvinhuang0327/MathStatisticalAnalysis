"""Unit tests for B649 K235 native prediction Producer v6 provenance output.

Covers AC01 through AC14:
- AC01: Upper adapter SHA256 matches expected adoption receipt.
- AC02: Opt-in provenance; default preserves existing Producer contract.
- AC03: Native fidelity: 3 K5 strategies, 15 tickets, positions 1..5.
- AC04: Complete causal history snapshot, draw count, and SHA binding.
- AC05: Source runtime provenance: git commit/tree, loaded code SHA.
- AC06: Strategy RNG semantics: deterministic vs seeded stochastic.
- AC07: Schedule authority and target binding required from named input.
- AC08: Generation timestamps from actual generation event; LOCAL_ONLY.
- AC09: Complete synthesized output validated through adapt_native_input.
- AC10: Missing required provenance fields explicitly rejected.
- AC11: Replay identity repeatability and no collision on varied scope.
- AC12: Existing Producer regression unaffected.
- AC13: No formal DB, Replay DB, or scheduler mutation.
- AC14: Deliverable contract and CLI options verified.
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from typing import Any

import pytest
from tools.b649_k235_predict import (
    NATIVE_INPUT_SCHEMA,
    PREDICTION_SCHEMA_VERSION,
    REPO_ROOT,
    Draw,
    _load_causal_draws,
    _resolve_seed_metadata,
    build_v6_provenance_output,
    main,
    produce_v6_native_prediction,
    run_prediction,
)

from lottolab.application.use_cases.generate_bet import (
    instantiate_portfolio_adapter,
)
from lottolab.domain.b649_next_undrawn_forecast import (
    OBJECTIVE,
    RANKING_POLICY_VERSION,
    digest,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.research_live_forecast import (
    NATIVE_STREAM,
    NATIVE_STREAM_VERSION,
    LiveForecastInput,
    sha256,
)
from lottolab.infrastructure import pre_outcome_target_operational as authority_module
from lottolab.infrastructure.b649_v6_native_input_adapter_candidate import (
    adapt_native_input,
)
from lottolab.infrastructure.imports.csv_draws import normalized_draw_record_hash
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    initialize_schema,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

ADAPTER_ADOPTED_SHA256 = "14750c16c1f46c69e719a975909af4bcc8a7caee23634a3a0377d40610e86893"
PRODUCER_OBSERVED_SHA256 = "87929fd644d30a5c9daa4abbc0ec07207ea1bae7927fc4e774e542bc9008d730"


def _create_synthetic_prediction_env(tmp_path: Path) -> tuple[Path, Path]:
    """Create a self-contained SQLite database and rank_history.json for testing."""
    data_directory = tmp_path / "canonical_draw_data"
    db_path = data_directory / "lottolab.db"
    initialize_schema(LocalDataPaths(data_directory, db_path))
    base_date = datetime.date(2025, 1, 1)
    with sqlite3.connect(db_path) as conn:
        offsets = [0, 7, 14, 21, 28, 35]
        rows = []
        for i in range(505):
            dnum = str(114999593 + i)
            ddate = (base_date + datetime.timedelta(days=i)).isoformat()
            nums = sorted([((i + off) % 49) + 1 for off in offsets])
            sp = [((i + 42) % 49) + 1]
            rows.append((dnum, ddate, nums, sp))
        rows.extend(
            [
                ("115000098", "2026-10-16", [1, 2, 3, 4, 5, 6], [7]),
                ("115000099", "2026-10-23", [2, 3, 4, 5, 6, 7], [8]),
            ]
        )
        conn.execute(
            "INSERT INTO ingestion_runs "
            "(id, operation_type, status, lottery_type, source_filename, source_sha256, "
            "parser_version, total_count, inserted_count, skipped_count, conflict_count, "
            "failed_count, first_draw_number, last_draw_number, started_at, completed_at, "
            "error_summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "synthetic-history",
                "SYNTHETIC",
                "SUCCESS",
                "BIG_LOTTO",
                "synthetic.csv",
                "a" * 64,
                "test",
                len(rows),
                len(rows),
                0,
                0,
                0,
                rows[0][0],
                rows[-1][0],
                "2026-11-25T00:00:00Z",
                "2026-11-25T00:00:01Z",
                None,
            ),
        )
        conn.executemany(
            "INSERT INTO draws "
            "(lottery_type, draw_number, draw_date, main_numbers_json, special_numbers_json, "
            "normalized_record_hash, source_name, source_reference, ingestion_run_id, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "BIG_LOTTO",
                    number,
                    draw_date,
                    json.dumps(main),
                    json.dumps(special),
                    normalized_draw_record_hash(
                        lottery_type=LotteryType.BIG_LOTTO,
                        draw_number=number,
                        draw_date_value=datetime.date.fromisoformat(draw_date),
                        main_numbers=tuple(main),
                        special_numbers=tuple(special),
                    ),
                    "synthetic",
                    None,
                    "synthetic-history",
                    "2026-11-25T00:00:00Z",
                    "2026-11-25T00:00:00Z",
                )
                for number, draw_date, main, special in rows
            ],
        )

    # Use the 3 canonical production K5 strategies
    catalog = production_catalog()
    descriptors = tuple(catalog.list(lottery_type=LotteryType.BIG_LOTTO))
    dmap = {d.strategy_id: d for d in descriptors}

    k5_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]

    rank_history: dict[str, Any] = {
        "hist": {"115000096": {"2": [], "3": [], "5": []}},
        "ids": {},
    }

    # Add mock candidates for K2 and K3 to satisfy pipeline
    k2_candidates = [d for d in descriptors if d.native_ticket_count == 2][:3]
    k3_candidates = [d for d in descriptors if d.native_ticket_count == 3][:3]

    for rank, d in enumerate(k2_candidates, start=1):
        rank_history["hist"]["115000096"]["2"].append([rank, d.strategy_id])
        rank_history["ids"][d.strategy_id] = [rank, d.strategy_name]

    for rank, d in enumerate(k3_candidates, start=1):
        rank_history["hist"]["115000096"]["3"].append([rank, d.strategy_id])
        rank_history["ids"][d.strategy_id] = [rank, d.strategy_name]

    for rank, sid in enumerate(k5_ids, start=1):
        d = dmap[sid]
        rank_history["hist"]["115000096"]["5"].append([rank, sid])
        rank_history["ids"][sid] = [rank, d.strategy_name]

    rank_history_path = tmp_path / "synthetic_rank_history.json"
    rank_history_path.write_text(json.dumps(rank_history), encoding="utf-8")
    return db_path, rank_history_path


def _make_schedule_binding() -> dict[str, Any]:
    return {
        "schedule_authority_sha256": "a" * 64,
        "target_draw_number": "115000098",
        "scheduled_at": "2026-10-16T20:30:00+08:00",
        "target_draw_date": "2026-10-16",
        "timezone": "Asia/Taipei",
    }


def _make_ranking_evidence(
    strategy_ids: list[str],
    draw_numbers: list[str],
) -> dict[str, Any]:
    observations = []
    for sid in sorted(strategy_ids):
        for dnum in draw_numbers:
            observations.append(
                {
                    "strategy_id": sid,
                    "strategy_version": "v0.1",
                    "native_k": 5,
                    "draw_number": dnum,
                    "draw_date": "2026-10-14",
                    "causal_history_sha256": "0" * 64,
                    "generation_config_sha256": "1" * 64,
                    "status": "EVALUATED",
                    "producer_fingerprint": "p" * 64,
                    "tickets": [[1, 2, 3, 4, 5, 6]],
                }
            )
    observations.sort(key=lambda r: (str(r["strategy_id"]), str(r["draw_number"])))
    return {
        "history_cutoff_draw": max(draw_numbers, key=int),
        "objective": OBJECTIVE,
        "ranking_policy_version": RANKING_POLICY_VERSION,
        "evaluation_window": "FULL",
        "observations": observations,
        "evidence_payload_sha256": digest(observations),
    }


def test_ac01_source_sha_alignment() -> None:
    """AC01: Verify upstream Adapter SHA matches adoption receipt."""
    adapter_rel = "src/lottolab/infrastructure/b649_v6_native_input_adapter_candidate.py"
    adapter_file = REPO_ROOT / adapter_rel
    assert adapter_file.exists(), f"Adapter file not found at {adapter_file}"
    actual_adapter_sha = hashlib.sha256(adapter_file.read_bytes()).hexdigest()
    assert actual_adapter_sha == ADAPTER_ADOPTED_SHA256, (
        f"Adapter SHA256 mismatch: {actual_adapter_sha} != {ADAPTER_ADOPTED_SHA256}"
    )

    producer_file = REPO_ROOT / "tools/b649_k235_predict.py"
    assert producer_file.exists()


def test_ac02_opt_in_preservation(tmp_path: Path) -> None:
    """AC02: Provenance output is opt-in; default run_prediction retains existing contract."""
    db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path)
    out_dir = tmp_path / "default_run"

    doc = run_prediction(
        db_path=db_path,
        rank_history_path=rank_history_path,
        cutoff_draw="115000097",
        target_draw="115000098",
        output_dir=out_dir,
        overwrite=True,
        emit_v6_provenance=False,
    )

    assert doc["schema_version"] == PREDICTION_SCHEMA_VERSION
    assert "v6_provenance" not in doc
    assert "native_result" not in doc
    assert "provenance" not in doc
    assert (out_dir / "predictions_115000098.json").exists()
    assert (out_dir / "tickets_115000098.txt").exists()
    assert not (out_dir / "v6_native_prediction_115000098.json").exists()


def test_ac03_native_fidelity_15_tickets_no_dedup(tmp_path: Path) -> None:
    """AC03: 3 K5 strategies produce 15 tickets; ticket positions 1..5 preserved; no dedup."""
    db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path)
    k5_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]
    sched = _make_schedule_binding()
    rank_ev = _make_ranking_evidence(k5_ids, ["115000095", "115000096", "115000097"])

    bundle = produce_v6_native_prediction(
        db_path=db_path,
        rank_history_path=rank_history_path,
        cutoff_draw="115000097",
        target_draw="115000098",
        schedule_binding=sched,
        ranking_evidence=rank_ev,
        output_dir=tmp_path / "v6_fidelity",
        overwrite=True,
    )

    native = bundle["native_result"]
    assert native["schema_version"] == NATIVE_INPUT_SCHEMA
    assert native["strategy_count_expected"] == 3
    assert native["strategy_count_generated"] == 3
    assert native["ticket_count_expected"] == 15
    assert native["ticket_count_generated"] == 15
    assert len(native["strategies"]) == 3

    total_tickets = 0
    all_tickets = []
    for s_idx, strat in enumerate(native["strategies"], start=1):
        assert strat["rank"] == s_idx
        assert strat["native_k"] == 5
        tickets = strat["tickets"]
        assert len(tickets) == 5
        for t_idx, t in enumerate(tickets, start=1):
            assert t["position"] == t_idx
            assert len(t["emitted_main_numbers"]) == 6
            assert len(set(t["emitted_main_numbers"])) == 6
            assert all(1 <= n <= 49 for n in t["emitted_main_numbers"])
            assert t["legal_main_numbers"] == t["emitted_main_numbers"]
            assert t["predicted_special_number"] is None
            total_tickets += 1
            all_tickets.append(t["emitted_main_numbers"])

    assert total_tickets == 15

    effective = bundle["provenance"]["effective_parameters"]
    effective_by_id = {row["strategy_id"]: row for row in effective["strategies"]}
    assert effective["sha256"] == digest({"strategies": effective["strategies"]})
    registry = ExecutableRegistry(production_catalog())
    for strategy_id in k5_ids:
        adapter_class = registry.load_adapter(strategy_id)
        assert effective_by_id[strategy_id]["adapter_class"] == (
            f"{adapter_class.__module__}:{adapter_class.__qualname__}"
        )


def test_ac04_causal_history_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC04: v6 history and canonical row hashes come from one cutoff-bounded snapshot."""
    db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path)
    k5_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]
    sched = _make_schedule_binding()
    rank_ev = _make_ranking_evidence(k5_ids, ["115000095", "115000096", "115000097"])

    statements: list[str] = []
    original_open = authority_module.open_database

    @contextmanager
    def traced_open(paths: LocalDataPaths, *, read_only: bool = False) -> Iterator[sqlite3.Connection]:
        with original_open(paths, read_only=read_only) as connection:
            connection.set_trace_callback(statements.append)
            yield connection

    monkeypatch.setattr(authority_module, "open_database", traced_open)
    bundle = produce_v6_native_prediction(
        db_path=db_path,
        rank_history_path=rank_history_path,
        cutoff_draw="115000097",
        target_draw="115000098",
        schedule_binding=sched,
        ranking_evidence=rank_ev,
    )

    prov = bundle["provenance"]
    hist = prov["history_snapshot"]
    target = prov["target"]

    draws = hist["draws"]
    assert len(draws) == 505
    assert target["history_draw_count"] == 505
    assert target["data_cutoff"] == "115000097"
    assert target["target_draw_number"] == "115000098"

    expected_sha = digest(draws)
    assert hist["sha256"] == expected_sha
    assert target["causal_history_sha256"] == expected_sha
    assert hist["reference"] == f"research-live-history:sha256:{expected_sha}"
    assert "history_fingerprint_sha256" in hist
    verified = hist["verified_canonical"]
    assert verified["authority"].endswith("open_verified_snapshot")
    assert verified["schema_version"] == "LOTTOLAB_PRE_OUTCOME_CAUSAL_HISTORY_V1"
    assert verified["target"]["draw_number"] == "115000098"
    assert verified["history_ref"]["draw_count"] == 505
    assert verified["history_ref"]["last_draw_number"] == "115000097"
    assert len(verified["normalized_records"]) == 505
    assert verified["normalized_records"][-1]["normalized_record_hash"]
    assert {"115000098", "115000099"}.isdisjoint(
        {row["draw_number"] for row in verified["normalized_records"]}
    )
    assert verified["history_ref"]["history_sha256"] != hist["sha256"]

    history_select = next(
        statement for statement in statements if "SELECT draw_number, draw_date" in statement
    )
    assert "draw_date < '2026-10-16'" in history_select
    assert "ltrim(draw_number, '0') <= '115000097'" in history_select

    replay = produce_v6_native_prediction(
        db_path=db_path,
        rank_history_path=rank_history_path,
        cutoff_draw="115000097",
        target_draw="115000098",
        schedule_binding=sched,
        ranking_evidence=rank_ev,
    )
    assert [row["tickets"] for row in bundle["native_result"]["strategies"]] == [
        row["tickets"] for row in replay["native_result"]["strategies"]
    ]
    assert (
        bundle["provenance"]["history_snapshot"]["verified_canonical"]
        == replay["provenance"]["history_snapshot"]["verified_canonical"]
    )


def test_native_v6_rejects_cutoff_mismatch_and_tampered_canonical_record(
    tmp_path: Path,
) -> None:
    db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path)
    k5_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]
    schedule = _make_schedule_binding()
    ranking = _make_ranking_evidence(k5_ids, ["115000095", "115000096", "115000097"])
    mismatch_output = tmp_path / "cutoff-mismatch-output"
    wrong_cutoff = dict(ranking, history_cutoff_draw="115000096")
    with pytest.raises(ValueError, match="ranking evidence cutoff does not match"):
        produce_v6_native_prediction(
            db_path=db_path,
            rank_history_path=rank_history_path,
            cutoff_draw="115000097",
            target_draw="115000098",
            schedule_binding=schedule,
            ranking_evidence=wrong_cutoff,
            output_dir=mismatch_output,
        )
    assert not mismatch_output.exists()

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE draws SET main_numbers_json = ? "
            "WHERE lottery_type = 'BIG_LOTTO' AND draw_number = '115000097'",
            ("[1,2,3,4,5,49]",),
        )
    tampered_output = tmp_path / "tampered-output"
    with pytest.raises(authority_module.CausalHistoryAuthorityError, match="does not match"):
        produce_v6_native_prediction(
            db_path=db_path,
            rank_history_path=rank_history_path,
            cutoff_draw="115000097",
            target_draw="115000098",
            schedule_binding=schedule,
            ranking_evidence=ranking,
            output_dir=tampered_output,
        )
    assert not tampered_output.exists()


@pytest.mark.parametrize("missing", ["schema", "normalized_record_hash"])
def test_native_v6_rejects_missing_canonical_schema_or_hash_without_artifact(
    missing: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_directory = tmp_path / f"missing-{missing}"
    db_directory.mkdir()
    db_path = db_directory / "lottolab.db"
    with sqlite3.connect(db_path) as connection:
        if missing == "normalized_record_hash":
            connection.execute("CREATE TABLE schema_migrations (version INTEGER)")
            connection.execute("INSERT INTO schema_migrations VALUES (4)")
        connection.execute(
            "CREATE TABLE draws (lottery_type TEXT, draw_number TEXT, draw_date TEXT, "
            "main_numbers_json TEXT, special_numbers_json TEXT, special_numbers TEXT)"
        )
        connection.execute(
            "INSERT INTO draws VALUES ('BIG_LOTTO','115000097','2026-05-20',"
            "'[1,2,3,4,5,6]','[7]','[7]')"
        )

    @contextmanager
    def raw_read_only_open(
        _paths: LocalDataPaths, *, read_only: bool = False
    ) -> Iterator[sqlite3.Connection]:
        assert read_only
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
        try:
            yield connection
        finally:
            connection.close()

    monkeypatch.setattr(authority_module, "open_database", raw_read_only_open)
    ranking_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]
    _db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path / "rank-inputs")
    ranking = _make_ranking_evidence(ranking_ids, ["115000095", "115000096", "115000097"])
    output = tmp_path / f"missing-{missing}-output"
    with pytest.raises(authority_module.CausalHistoryAuthorityError):
        produce_v6_native_prediction(
            db_path=db_path,
            rank_history_path=rank_history_path,
            cutoff_draw="115000097",
            target_draw="115000098",
            schedule_binding=_make_schedule_binding(),
            ranking_evidence=ranking,
            output_dir=output,
        )
    assert not output.exists()


def test_ac05_source_runtime_provenance(tmp_path: Path) -> None:
    """AC05: Source execution and runtime manifest have verifiable git and loaded code hashes."""
    db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path)
    k5_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]
    sched = _make_schedule_binding()
    rank_ev = _make_ranking_evidence(k5_ids, ["115000095", "115000096", "115000097"])

    producer_path = REPO_ROOT / "tools/b649_k235_predict.py"
    base_commit = os.environ.get("NATIVE_CANDIDATE_BASE_COMMIT")
    base_tree = os.environ.get("NATIVE_CANDIDATE_BASE_TREE")
    source_execution_override = None
    if base_commit and base_tree:
        source_execution_override = {
            "repository": str(REPO_ROOT),
            "commit": base_commit,
            "tree": base_tree,
            "loaded_code_sha256": hashlib.sha256(producer_path.read_bytes()).hexdigest(),
            "pre_draw_proof_status": "LOCAL_ONLY",
        }
    bundle = produce_v6_native_prediction(
        db_path=db_path,
        rank_history_path=rank_history_path,
        cutoff_draw="115000097",
        target_draw="115000098",
        schedule_binding=sched,
        ranking_evidence=rank_ev,
        source_execution_override=source_execution_override,
    )

    prov = bundle["provenance"]
    src_exec = prov["source_execution"]
    assert str(REPO_ROOT) in src_exec["repository"]
    assert len(src_exec["commit"]) >= 7
    assert len(src_exec["tree"]) >= 7
    expected_loaded_sha = hashlib.sha256(producer_path.read_bytes()).hexdigest()
    assert src_exec["loaded_code_sha256"] == expected_loaded_sha

    runtime = prov["runtime_manifest"]
    assert "python" in runtime
    assert runtime["python"]["version"].startswith("3.13")
    assert runtime["sha256"] == digest({k: v for k, v in runtime.items() if k != "sha256"})


def test_ac06_strategy_rng_semantics(tmp_path: Path) -> None:
    """AC06: Deterministic vs seeded stochastic RNG semantics are correctly distinguished."""
    db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path)
    k5_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]
    sched = _make_schedule_binding()
    rank_ev = _make_ranking_evidence(k5_ids, ["115000095", "115000096", "115000097"])

    bundle = produce_v6_native_prediction(
        db_path=db_path,
        rank_history_path=rank_history_path,
        cutoff_draw="115000097",
        target_draw="115000098",
        schedule_binding=sched,
        ranking_evidence=rank_ev,
    )

    prov = bundle["provenance"]
    seeds = prov["seeds"]

    configs_by_id = {c["strategy_id"]: c for c in prov["generation_configs"]}

    cfg_ortho = configs_by_id["legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e"]
    assert cfg_ortho["rng_semantics"]["behavior"] == "DETERMINISTIC"
    assert cfg_ortho["rng_semantics"]["seed"] is None
    assert cfg_ortho["strategy_id"] not in seeds

    cfg_markov = configs_by_id["legacy_composite__quick_predict_5bet_ts3_markov_freqort"]
    assert cfg_markov["rng_semantics"]["behavior"] == "DETERMINISTIC"
    assert cfg_markov["rng_semantics"]["seed"] is None
    assert cfg_markov["strategy_id"] not in seeds

    cfg_5me = configs_by_id["legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd"]
    assert cfg_5me["rng_semantics"]["behavior"] == "SEEDED_STOCHASTIC"
    assert cfg_5me["rng_semantics"]["seed"] == 505
    assert seeds[cfg_5me["strategy_id"]] == 505


def test_ac07_schedule_binding_required(tmp_path: Path) -> None:
    """AC07: Schedule authority and binding must be provided from named input; cannot be guessed."""
    db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path)
    k5_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]
    rank_ev = _make_ranking_evidence(k5_ids, ["115000095", "115000096", "115000097"])

    # Missing schedule_binding raises ValueError
    with pytest.raises(ValueError, match="schedule binding is required"):
        produce_v6_native_prediction(
            db_path=db_path,
            rank_history_path=rank_history_path,
            cutoff_draw="115000097",
            target_draw="115000098",
            schedule_binding=None,  # type: ignore[arg-type]
            ranking_evidence=rank_ev,
        )

    # Missing scheduled_at raises ValueError
    with pytest.raises(ValueError, match="schedule binding missing required field: scheduled_at"):
        produce_v6_native_prediction(
            db_path=db_path,
            rank_history_path=rank_history_path,
            cutoff_draw="115000097",
            target_draw="115000098",
            schedule_binding={
                "schedule_authority_sha256": "a" * 64,
                "target_draw_number": "115000098",
                "target_draw_date": "2026-10-16",
            },
            ranking_evidence=rank_ev,
        )


def test_ac08_generation_timestamps(tmp_path: Path) -> None:
    """AC08: Generation timestamps are captured at generation time; proof status is LOCAL_ONLY."""
    db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path)
    k5_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]
    sched = _make_schedule_binding()
    rank_ev = _make_ranking_evidence(k5_ids, ["115000095", "115000096", "115000097"])

    bundle = produce_v6_native_prediction(
        db_path=db_path,
        rank_history_path=rank_history_path,
        cutoff_draw="115000097",
        target_draw="115000098",
        schedule_binding=sched,
        ranking_evidence=rank_ev,
    )

    prov = bundle["provenance"]
    assert prov.get("generation_started_at")
    assert prov.get("generation_finished_at")
    assert bundle["native_result"]["pre_draw_proof_status"] == "LOCAL_ONLY"
    assert "issued_at" not in prov
    assert "committed_at" not in prov


def test_ac09_v6_validation_with_formal_adapter(tmp_path: Path) -> None:
    """AC09: Complete Producer v6 output passes adapt_native_input and validate()."""
    db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path)
    k5_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]
    sched = _make_schedule_binding()
    rank_ev = _make_ranking_evidence(k5_ids, ["115000095", "115000096", "115000097"])

    bundle = produce_v6_native_prediction(
        db_path=db_path,
        rank_history_path=rank_history_path,
        cutoff_draw="115000097",
        target_draw="115000098",
        schedule_binding=sched,
        ranking_evidence=rank_ev,
    )

    # Pass directly into formal adapter
    forecast = adapt_native_input(bundle["native_result"], bundle["provenance"])

    assert isinstance(forecast, LiveForecastInput)
    assert forecast.provenance_class == "NATIVE_GENERATED"
    assert forecast.forecast_stream_id == NATIVE_STREAM
    assert forecast.forecast_stream_version == NATIVE_STREAM_VERSION
    assert forecast.request_id.startswith("native-input:")
    assert len(forecast.request_sha256) == 64
    assert len(forecast.payload_bytes) > 0

    # Also test via run_prediction(emit_v6_provenance=True)
    out_dir = tmp_path / "v6_run"
    doc = run_prediction(
        db_path=db_path,
        rank_history_path=rank_history_path,
        cutoff_draw="115000097",
        target_draw="115000098",
        output_dir=out_dir,
        overwrite=True,
        emit_v6_provenance=True,
        schedule_binding=sched,
        ranking_evidence=rank_ev,
    )

    forecast2 = adapt_native_input(doc["native_result"], doc["provenance"])
    assert isinstance(forecast2, LiveForecastInput)
    assert (out_dir / "v6_native_prediction_115000098.json").exists()


def test_ac10_invalid_inputs_rejected(tmp_path: Path) -> None:
    """AC10: Missing source tree, history SHA, schedule, RNG, version, timestamps rejected."""
    draws = [
        Draw("115000096", datetime.date(2026, 10, 12), (1, 2, 3, 4, 5, 6), 7),
        Draw("115000097", datetime.date(2026, 10, 14), (2, 3, 4, 5, 6, 7), 8),
    ]
    catalog = production_catalog()
    dmap = {d.strategy_id: d for d in catalog.list(lottery_type=LotteryType.BIG_LOTTO)}

    k5_entries = [
        {
            "rank": 1,
            "strategy_id": "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
            "strategy_version": "v0.1",
            "native_ticket_count": 5,
            "tickets": [
                {"emitted_main_numbers": [i, i + 1, i + 2, i + 3, i + 4, i + 5]}
                for i in range(1, 6)
            ],
            "determinism_seed": {"behavior": "DETERMINISTIC", "seed": None},
        },
        {
            "rank": 2,
            "strategy_id": "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
            "strategy_version": "v0.1",
            "native_ticket_count": 5,
            "tickets": [
                {"emitted_main_numbers": [i, i + 1, i + 2, i + 3, i + 4, i + 5]}
                for i in range(1, 6)
            ],
            "determinism_seed": {"behavior": "DETERMINISTIC", "seed": None},
        },
        {
            "rank": 3,
            "strategy_id": "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
            "strategy_version": "v0.1",
            "native_ticket_count": 5,
            "tickets": [
                {"emitted_main_numbers": [i, i + 1, i + 2, i + 3, i + 4, i + 5]}
                for i in range(1, 6)
            ],
            "determinism_seed": {"behavior": "SEEDED_STOCHASTIC", "seed": 2},
        },
    ]

    sched = _make_schedule_binding()
    sids = [e["strategy_id"] for e in k5_entries]
    rank_ev = _make_ranking_evidence(sids, ["115000096", "115000097"])

    base_args: dict[str, Any] = {
        "target_draw": "115000098",
        "cutoff_draw": "115000097",
        "draws": draws,
        "k5_entries": k5_entries,
        "descriptors_map": dmap,
        "schedule_binding": sched,
        "ranking_evidence": rank_ev,
        "generation_started_at": "2026-10-16T10:00:00Z",
        "generation_finished_at": "2026-10-16T10:00:01Z",
    }

    # 1. Missing source tree
    with pytest.raises(ValueError, match="source execution missing required field: tree"):
        bad_args = copy.deepcopy(base_args)
        bad_args["source_execution_override"] = {
            "repository": str(REPO_ROOT),
            "commit": "1" * 40,
            "tree": "",
            "loaded_code_sha256": "2" * 64,
        }
        build_v6_provenance_output(**bad_args)

    # 2. Missing schedule binding
    with pytest.raises(ValueError, match="schedule binding is required"):
        bad_args = copy.deepcopy(base_args)
        bad_args["schedule_binding"] = None
        build_v6_provenance_output(**bad_args)

    # 3. Missing generation timestamps
    with pytest.raises(ValueError, match="generation_started_at timestamp is required"):
        bad_args = copy.deepcopy(base_args)
        bad_args["generation_started_at"] = ""
        build_v6_provenance_output(**bad_args)

    # 4. Missing RNG identity
    with pytest.raises(ValueError, match="RNG identity is required"):
        bad_args = copy.deepcopy(base_args)
        bad_args["k5_entries"][0]["determinism_seed"] = {}
        build_v6_provenance_output(**bad_args)

    # 5. Missing strategy version
    with pytest.raises(ValueError, match="strategy version is required"):
        bad_args = copy.deepcopy(base_args)
        bad_args["k5_entries"][0]["strategy_version"] = ""
        build_v6_provenance_output(**bad_args)

    # 6. UNKNOWN proof status
    with pytest.raises(ValueError, match="pre_draw_proof_status cannot be empty or UNKNOWN"):
        bad_args = copy.deepcopy(base_args)
        bad_args["pre_draw_proof_status"] = "UNKNOWN"
        build_v6_provenance_output(**bad_args)


def test_ac11_replay_identity_repeat_and_no_collision(tmp_path: Path) -> None:
    """AC11: Same fixed inputs produce identical tickets and request_id; varying differs."""
    db_path, _ = _create_synthetic_prediction_env(tmp_path)
    k5_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]
    sched = _make_schedule_binding()
    rank_ev = _make_ranking_evidence(k5_ids, ["115000095", "115000096", "115000097"])

    fixed_started = "2026-10-16T10:00:00.000000Z"
    fixed_finished = "2026-10-16T10:00:01.000000Z"

    draws, causal_history = _load_causal_draws(db_path, "115000097", "115000098")
    catalog = production_catalog()
    dmap = {d.strategy_id: d for d in catalog.list(lottery_type=LotteryType.BIG_LOTTO)}

    k5_entries = []
    registry = ExecutableRegistry(catalog)
    for rank, sid in enumerate(k5_ids, start=1):
        adapter_cls = registry.load_adapter(sid)
        impl = instantiate_portfolio_adapter(sid, adapter_cls)
        bets = impl.get_bets_with_emission(causal_history, LotteryType.BIG_LOTTO)
        k5_entries.append(
            {
                "rank": rank,
                "strategy_id": sid,
                "strategy_version": dmap[sid].version,
                "native_ticket_count": 5,
                "tickets": [{"emitted_main_numbers": list(b.emitted_main_numbers)} for b in bets],
                "determinism_seed": _resolve_seed_metadata(dmap[sid], causal_history),
            }
        )

    # Run 1
    bundle1 = build_v6_provenance_output(
        target_draw="115000098",
        cutoff_draw="115000097",
        draws=draws,
        k5_entries=k5_entries,
        descriptors_map=dmap,
        schedule_binding=sched,
        ranking_evidence=rank_ev,
        generation_started_at=fixed_started,
        generation_finished_at=fixed_finished,
    )
    f1 = adapt_native_input(bundle1["native_result"], bundle1["provenance"])

    # Run 2 with identical inputs
    bundle2 = build_v6_provenance_output(
        target_draw="115000098",
        cutoff_draw="115000097",
        draws=draws,
        k5_entries=k5_entries,
        descriptors_map=dmap,
        schedule_binding=sched,
        ranking_evidence=rank_ev,
        generation_started_at=fixed_started,
        generation_finished_at=fixed_finished,
    )
    f2 = adapt_native_input(bundle2["native_result"], bundle2["provenance"])

    assert f1.request_id == f2.request_id
    assert f1.request_sha256 == f2.request_sha256
    assert sha256(f1.payload_bytes) == sha256(f2.payload_bytes)

    # Vary target scope (target_draw 115000098 -> 115000099)
    sched_diff = copy.deepcopy(sched)
    sched_diff["target_draw_date"] = "2026-10-18"
    bundle_diff = build_v6_provenance_output(
        target_draw="115000099",
        cutoff_draw="115000097",
        draws=draws,
        k5_entries=k5_entries,
        descriptors_map=dmap,
        schedule_binding=sched_diff,
        ranking_evidence=rank_ev,
        generation_started_at=fixed_started,
        generation_finished_at=fixed_finished,
    )
    f_diff = adapt_native_input(bundle_diff["native_result"], bundle_diff["provenance"])

    assert f_diff.request_id != f1.request_id
    assert sha256(f_diff.payload_bytes) != sha256(f1.payload_bytes)


def test_ac12_existing_producer_regression(tmp_path: Path) -> None:
    """AC12: Baseline prediction quality components across K2, K3, K5 execute cleanly."""
    db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path)
    out_dir = tmp_path / "regression_check"

    doc = run_prediction(
        db_path=db_path,
        rank_history_path=rank_history_path,
        cutoff_draw="115000097",
        target_draw="115000098",
        output_dir=out_dir,
        overwrite=True,
    )

    valid_statuses = ("COMPLETE", "PARTIAL_QUALIFIED", "NO_QUALIFIED_PREDICTIONS")
    assert doc["overall_pipeline_status"] in valid_statuses
    assert doc["causal_history_length"] == 505
    assert "k2" in doc and "k3" in doc and "k5" in doc


def test_ac13_formal_db_and_scheduler_unmutated(tmp_path: Path) -> None:
    """AC13: Verify no database mutation or scheduler connection occurs."""
    db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path)
    sha_before = hashlib.sha256(db_path.read_bytes()).hexdigest()

    sched = _make_schedule_binding()
    k5_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]
    rank_ev = _make_ranking_evidence(k5_ids, ["115000095", "115000096", "115000097"])

    produce_v6_native_prediction(
        db_path=db_path,
        rank_history_path=rank_history_path,
        cutoff_draw="115000097",
        target_draw="115000098",
        schedule_binding=sched,
        ranking_evidence=rank_ev,
        output_dir=tmp_path / "read_only_check",
    )

    sha_after = hashlib.sha256(db_path.read_bytes()).hexdigest()
    assert sha_before == sha_after, "SQLite DB was unexpectedly modified during read-only operation"


def test_ac14_cli_opt_in_v6_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC14: CLI options --emit-v6-provenance with JSON schedule/ranking execute cleanly."""
    db_path, rank_history_path = _create_synthetic_prediction_env(tmp_path)
    k5_ids = [
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
    ]
    sched = _make_schedule_binding()
    rank_ev = _make_ranking_evidence(k5_ids, ["115000095", "115000096", "115000097"])

    sched_file = tmp_path / "sched.json"
    sched_file.write_text(json.dumps(sched), encoding="utf-8")

    rank_file = tmp_path / "rank_ev.json"
    rank_file.write_text(json.dumps(rank_ev), encoding="utf-8")

    out_dir = tmp_path / "cli_v6_out"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "b649_k235_predict.py",
            "--db-path",
            str(db_path),
            "--rank-history-path",
            str(rank_history_path),
            "--cutoff-draw",
            "115000097",
            "--target-draw",
            "115000098",
            "--output-dir",
            str(out_dir),
            "--emit-v6-provenance",
            "--schedule-binding-json",
            str(sched_file),
            "--ranking-evidence-json",
            str(rank_file),
            "--overwrite",
        ],
    )

    main()

    v6_file = out_dir / "v6_native_prediction_115000098.json"
    assert v6_file.exists(), f"Expected v6 output file at {v6_file}"
    data = json.loads(v6_file.read_text(encoding="utf-8"))
    assert "native_result" in data
    assert "provenance" in data
    forecast = adapt_native_input(data["native_result"], data["provenance"])
    assert isinstance(forecast, LiveForecastInput)
