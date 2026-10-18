"""Unit tests for B649 K2/K3/K5 predict CLI and pipeline (AC1, AC2, AC3, AC4, AC7)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest
from tools.b649_k235_predict import (
    REPO_ROOT,
    load_causal_draws,
    main,
    run_prediction,
)

from lottolab.strategies.adapters.biglotto_horizon_minimax import (
    BigLottoHorizonMinimaxDisagreementAdapter,
)
from lottolab.strategies.catalog import production_catalog


def test_ac1_ac2_runtime_independence_and_blocking_legacy_worktrees(
    tmp_path: Path,
) -> None:
    """AC1 and AC2:
    - Verifies that running prediction executes cleanly without importing ANY Python
      modules from:
        - B649_K2_K3_EXACT_NATIVE_FULL_REPLAY_R1
        - B649_K235_DISJOINT_LOCAL_IMPLEMENTATION_R1
        - any .task-data Python scripts
    - Uses an active sys.meta_path import blocker that raises ImportError if any module
      from these forbidden legacy paths is imported.
    - Confirms execution completes successfully (status: COMPLETE, all 9 candidates generated).
    - Inspects sys.modules to verify that every loaded lottolab / tool module origin is inside
      TARGET_WORKTREE, and 0 modules are from the forbidden paths.
    """
    forbidden_prefixes = (
        "B649_K2_K3_EXACT_NATIVE_FULL_REPLAY_R1",
        "B649_K235_DISJOINT_LOCAL_IMPLEMENTATION_R1",
        ".task-data",
    )

    class ForbiddenPathBlocker:
        def find_spec(
            self, fullname: str, path: Any = None, target: Any = None
        ) -> None:
            if path is not None:
                for p in path:
                    for forbidden in forbidden_prefixes:
                        if forbidden in str(p):
                            raise ImportError(
                                f"AC1/AC2 Violation: import of {fullname} "
                                f"from forbidden path: {p}"
                            )
            return None

    # Verify blocker itself triggers if forbidden path is queried
    blocker_test = ForbiddenPathBlocker()
    with pytest.raises(ImportError, match="AC1/AC2 Violation"):
        blocker_test.find_spec(
            "dummy_module",
            path=["/some/path/B649_K2_K3_EXACT_NATIVE_FULL_REPLAY_R1/tools"],
        )

    # Install blocker on sys.meta_path
    blocker = ForbiddenPathBlocker()
    sys.meta_path.insert(0, blocker)
    try:
        out_dir = tmp_path / "ac1_ac2_test"
        doc = run_prediction(
            cutoff_draw="115000097",
            target_draw="115000098",
            output_dir=out_dir,
            overwrite=True,
        )
        assert doc["overall_pipeline_status"] == "COMPLETE"
        assert doc["all_k_available"] is True
        assert doc["causal_history_length"] == 2179

        # Audit all loaded modules in sys.modules
        repo_root_str = str(REPO_ROOT.resolve())
        forbidden_hits: list[str] = []
        lottolab_modules: list[str] = []

        for mod_name, mod in list(sys.modules.items()):
            mod_file = getattr(mod, "__file__", None)
            if mod_file is not None:
                mod_file_str = str(Path(mod_file).resolve())
                for forbidden in forbidden_prefixes:
                    if forbidden in mod_file_str:
                        forbidden_hits.append(f"{mod_name}: {mod_file_str}")
                if mod_name.startswith("lottolab.") or mod_name == "lottolab":
                    lottolab_modules.append(mod_name)
                    assert mod_file_str.startswith(repo_root_str), (
                        f"Module {mod_name} ({mod_file_str}) not from REPO_ROOT ({repo_root_str})"
                    )

        assert forbidden_hits == [], (
            f"Found modules loaded from forbidden paths: {forbidden_hits}"
        )
        assert len(lottolab_modules) > 0, "Expected lottolab modules to be loaded"

    finally:
        if blocker in sys.meta_path:
            sys.meta_path.remove(blocker)


def test_ac1_existing_output_conflict_rejection_and_idempotence(
    tmp_path: Path,
) -> None:
    """AC1:
    - Conflicting existing file without overwrite raises FileExistsError and preserves content.
    - Explicit overwrite=True overwrites.
    - Identical existing files without overwrite succeed idempotently and preserve content.
    """
    out_dir = tmp_path / "ac1_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_file = out_dir / "predictions_115000098.json"
    txt_file = out_dir / "tickets_115000098.txt"

    # 1. Create conflicting existing file
    conflicting_json = '{"conflicting_data": true}\n'
    json_file.write_text(conflicting_json, encoding="utf-8")

    with pytest.raises(FileExistsError) as excinfo:
        run_prediction(
            cutoff_draw="115000097",
            target_draw="115000098",
            output_dir=out_dir,
            overwrite=False,
        )
    assert "already exists with conflicting" in str(excinfo.value)
    # File content must remain completely preserved and uncorrupted
    assert json_file.read_text(encoding="utf-8") == conflicting_json

    # 2. Overwrite=True succeeds
    doc = run_prediction(
        cutoff_draw="115000097",
        target_draw="115000098",
        output_dir=out_dir,
        overwrite=True,
    )
    assert doc["overall_pipeline_status"] == "COMPLETE"
    assert json_file.exists()
    assert txt_file.exists()
    written_json_bytes = json_file.read_bytes()
    written_txt_bytes = txt_file.read_bytes()

    # 3. Idempotent rerun without overwrite succeeds and preserves exact bytes
    doc_idempotent = run_prediction(
        cutoff_draw="115000097",
        target_draw="115000098",
        output_dir=out_dir,
        overwrite=False,
    )
    assert doc_idempotent["overall_pipeline_status"] == "COMPLETE"
    assert json_file.read_bytes() == written_json_bytes
    assert txt_file.read_bytes() == written_txt_bytes


def test_ac2_runtime_and_catalog_version_integrity() -> None:
    """AC2:
    Horizon __file__ is located in TARGET_WORKTREE.
    Adapter and catalog descriptor are both v0.2.
    Binding is valid.
    Other strategies in catalog remain unchanged.
    """
    import lottolab.strategies.adapters.biglotto_horizon_minimax as hm

    assert Path(hm.__file__).resolve() == (
        REPO_ROOT / "src/lottolab/strategies/adapters/biglotto_horizon_minimax.py"
    ).resolve()

    assert BigLottoHorizonMinimaxDisagreementAdapter.strategy_version == "v0.2"

    catalog = production_catalog()
    descriptor = catalog.get("b649_new_horizon_minimax_disagreement_r1")
    assert descriptor.version == "v0.2"

    # Other strategies remain unchanged (e.g. v0.1)
    minimal_dual = catalog.get(
        "legacy_biglotto__minimal_dual_bet_strategy__3c9657df7ff4"
    )
    assert minimal_dual.version == "v0.1"


def test_ac2_causal_cutoff_and_future_data_exclusion(tmp_path: Path) -> None:
    """AC2:
    Validate cutoff < target.
    Validate with synthetic DB containing cutoff, target, and future draws:
    - History only contains draws <= cutoff.
    - Target and future draws are strictly excluded.
    - Erroneous cutoff/target fails without producing predictions.
    """
    synth_db = tmp_path / "synthetic_lottolab.db"
    with sqlite3.connect(synth_db) as conn:
        conn.execute(
            "CREATE TABLE draws ("
            "draw_number TEXT PRIMARY KEY, "
            "draw_date TEXT, "
            "main_numbers_json TEXT, "
            "special_numbers_json TEXT, "
            "lottery_type TEXT"
            ");"
        )
        sample_draws = [
            ("115000095", "2026-10-10", "[1, 2, 3, 4, 5, 6]", "[7]", "BIG_LOTTO"),
            ("115000096", "2026-10-12", "[2, 3, 4, 5, 6, 7]", "[8]", "BIG_LOTTO"),
            ("115000097", "2026-10-14", "[3, 4, 5, 6, 7, 8]", "[9]", "BIG_LOTTO"),  # cutoff
            ("115000098", "2026-10-16", "[4, 5, 6, 7, 8, 9]", "[10]", "BIG_LOTTO"),  # target
            ("115000099", "2026-10-18", "[5, 6, 7, 8, 9, 10]", "[11]", "BIG_LOTTO"),  # future
            ("115000100", "2026-10-20", "[6, 7, 8, 9, 10, 11]", "[12]", "BIG_LOTTO"),  # future
        ]
        conn.executemany(
            "INSERT INTO draws VALUES (?, ?, ?, ?, ?);",
            sample_draws,
        )

    # 1. Valid cutoff < target against DB containing target & future
    draws, causal_history = load_causal_draws(
        synth_db,
        cutoff_draw="115000097",
        target_draw="115000098",
    )
    assert len(draws) == 3
    assert len(causal_history) == 3
    assert draws[-1].draw_number == "115000097"
    loaded_numbers = [int(d.draw_number) for d in draws]
    assert loaded_numbers == [115000095, 115000096, 115000097]
    # Verify target and future draws are strictly excluded
    assert 115000098 not in loaded_numbers
    assert 115000099 not in loaded_numbers
    assert 115000100 not in loaded_numbers

    # 2. Negative test: cutoff == target
    with pytest.raises(ValueError, match="must be strictly less than target"):
        load_causal_draws(
            synth_db,
            cutoff_draw="115000098",
            target_draw="115000098",
        )

    # 3. Negative test: cutoff > target
    with pytest.raises(ValueError, match="must be strictly less than target"):
        load_causal_draws(
            synth_db,
            cutoff_draw="115000099",
            target_draw="115000098",
        )

    # 4. Negative test: cutoff draw not present in DB
    with pytest.raises(
        RuntimeError, match="Causal history does not end at cutoff"
    ):
        load_causal_draws(
            synth_db,
            cutoff_draw="115000105",
            target_draw="115000106",
        )


def test_ac3_no_qualified_candidates_and_partial_availability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3:
    - When a K category has no qualified candidates, it is marked unavailable.
    - When some K are available, overall result does not claim all three K are available.
    - When all K have no qualified candidates, pipeline status is NO_QUALIFIED_PREDICTIONS.
    - No ticket padding, number alteration, or hiding rejected tickets in accepted entries.
    """
    valid_k2_entry = {
        "rank": 1,
        "strategy_id": "mock_k2_strat",
        "display_name": "Mock K2 Strat",
        "strategy_version": "v1.0",
        "status": "OK",
        "tickets": [
            {"emitted_main_numbers": [1, 2, 3, 4, 5, 6]},
            {"emitted_main_numbers": [7, 8, 9, 10, 11, 12]},
        ],
    }
    # Overlapping K3 entry that will be rejected by output quality (cross ticket overlap)
    overlapping_k3_entry = {
        "rank": 1,
        "strategy_id": "mock_k3_overlap",
        "display_name": "Mock K3 Overlap",
        "strategy_version": "v1.0",
        "status": "OK",
        "tickets": [
            {"emitted_main_numbers": [1, 2, 3, 4, 5, 6]},
            {"emitted_main_numbers": [1, 2, 3, 4, 5, 6]},
            {"emitted_main_numbers": [7, 8, 9, 10, 11, 12]},
        ],
    }
    valid_k5_entry = {
        "rank": 1,
        "strategy_id": "mock_k5_strat",
        "display_name": "Mock K5 Strat",
        "strategy_version": "v1.0",
        "status": "OK",
        "tickets": [
            {"emitted_main_numbers": [1, 2, 3, 4, 5, 6]},
            {"emitted_main_numbers": [7, 8, 9, 10, 11, 12]},
            {"emitted_main_numbers": [13, 14, 15, 16, 17, 18]},
            {"emitted_main_numbers": [19, 20, 21, 22, 23, 24]},
            {"emitted_main_numbers": [25, 26, 27, 28, 29, 30]},
        ],
    }

    # Scenario 1: Partial availability (K2 and K5 valid, K3 all rejected)
    partial_override = {
        "k2": {"entries": [valid_k2_entry]},
        "k3": {"entries": [overlapping_k3_entry]},
        "k5": {"entries": [valid_k5_entry]},
    }
    out1 = tmp_path / "partial"
    doc_partial = run_prediction(
        output_dir=out1,
        raw_predictions_override=partial_override,
    )
    assert doc_partial["overall_pipeline_status"] == "PARTIAL_QUALIFIED"
    assert doc_partial["all_k_available"] is False
    assert doc_partial["has_any_qualified_prediction"] is True
    assert doc_partial["available_k_categories"] == ["K2", "K5"]
    assert doc_partial["unavailable_k_categories"] == ["K3"]

    assert doc_partial["k2"]["is_available"] is True
    assert doc_partial["k2"]["availability_status"] == "AVAILABLE"

    assert doc_partial["k3"]["is_available"] is False
    assert doc_partial["k3"]["availability_status"] == "UNAVAILABLE"
    assert doc_partial["k3"]["has_qualified_candidates"] is False
    assert doc_partial["k3"]["fair_draw_exact_coverage_fraction"] is None
    assert len(doc_partial["k3"]["accepted_entries"]) == 0
    assert len(doc_partial["k3"]["rejected_entries"]) == 1

    assert doc_partial["k5"]["is_available"] is True
    assert doc_partial["k5"]["availability_status"] == "AVAILABLE"

    # Scenario 2: All categories rejected (none available)
    none_override = {
        "k2": {"entries": [overlapping_k3_entry]},  # Wrong count & overlap
        "k3": {"entries": [overlapping_k3_entry]},
        "k5": {"entries": [overlapping_k3_entry]},
    }
    out2 = tmp_path / "none_avail"
    doc_none = run_prediction(
        output_dir=out2,
        raw_predictions_override=none_override,
    )
    assert doc_none["overall_pipeline_status"] == "NO_QUALIFIED_PREDICTIONS"
    assert doc_none["all_k_available"] is False
    assert doc_none["has_any_qualified_prediction"] is False
    assert doc_none["available_k_categories"] == []
    assert doc_none["unavailable_k_categories"] == ["K2", "K3", "K5"]
    for k_key in ("k2", "k3", "k5"):
        assert doc_none[k_key]["is_available"] is False
        assert doc_none[k_key]["availability_status"] == "UNAVAILABLE"
        assert len(doc_none[k_key]["accepted_entries"]) == 0

    def _mock_run_prediction(**kwargs: Any) -> dict[str, Any]:
        return doc_none

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "b649_k235_predict.py",
            "--output-dir",
            str(tmp_path / "cli_test"),
        ],
    )
    monkeypatch.setattr(
        "tools.b649_k235_predict.run_prediction",
        _mock_run_prediction,
    )
    with pytest.raises(SystemExit) as exc_exit:
        main()
    assert exc_exit.value.code == 2


def test_ac4_draw_098_end_to_end_and_exact_coverage(tmp_path: Path) -> None:
    """AC4 (No regression):
    Run end-to-end for draw 115000098:
    - Input cutoff 115000097, 2179 draws.
    - Generates 9 candidates across K2, K3, K5.
    - Quality evaluation yields:
        K2: accept rank 1, 2; reject rank 3
        K3: accept rank 1, 3; reject rank 2
        K5: accept rank 1, 2; reject rank 3
      Total: 6 accepted, 3 rejected.
    - Horizon 098 tickets match the regression golden:
        08 15 20 26 29 35
        03 04 06 07 14 22
    - Exact coverage fractions:
        K2 = 5302152 / 85900584
        K3 = 7930128 / 85900584
        K5 = 13139880 / 85900584
      Rejected candidates do not receive these values.
    - all_k_available is True, pipeline status is COMPLETE.
    """
    doc = run_prediction(
        cutoff_draw="115000097",
        target_draw="115000098",
        output_dir=tmp_path,
        overwrite=True,
    )

    assert doc["overall_pipeline_status"] == "COMPLETE"
    assert doc["all_k_available"] is True
    assert doc["has_any_qualified_prediction"] is True
    assert doc["available_k_categories"] == ["K2", "K3", "K5"]
    assert doc["unavailable_k_categories"] == []
    assert doc["causal_history_length"] == 2179
    assert doc["target_draw_number"] == "115000098"
    assert doc["prediction_cutoff_draw_number"] == "115000097"
    assert doc["actual_imported_horizon_version"] == "v0.2"

    # K2 assertions
    k2 = doc["k2"]
    assert k2["is_available"] is True
    assert k2["availability_status"] == "AVAILABLE"
    assert k2["accepted_strategy_count"] == 2
    assert k2["rejected_strategy_count"] == 1
    assert [e["rank"] for e in k2["accepted_entries"]] == [1, 2]
    assert [e["rank"] for e in k2["rejected_entries"]] == [3]
    assert k2["fair_draw_exact_coverage_fraction"] == "5302152/85900584"
    for e in k2["accepted_entries"]:
        assert e["exact_coverage_fraction"] == "5302152/85900584"
    for e in k2["rejected_entries"]:
        assert e["exact_coverage_fraction"] is None

    # Verify Horizon tickets
    horizon_entry = k2["accepted_entries"][0]
    assert (
        horizon_entry["strategy_id"]
        == "b649_new_horizon_minimax_disagreement_r1"
    )
    assert horizon_entry["strategy_version"] == "v0.2"
    horizon_tickets = [
        t["emitted_main_numbers"] for t in horizon_entry["tickets"]
    ]
    assert horizon_tickets == [
        [8, 15, 20, 26, 29, 35],
        [3, 4, 6, 7, 14, 22],
    ]

    # K3 assertions
    k3 = doc["k3"]
    assert k3["is_available"] is True
    assert k3["availability_status"] == "AVAILABLE"
    assert k3["accepted_strategy_count"] == 2
    assert k3["rejected_strategy_count"] == 1
    assert [e["rank"] for e in k3["accepted_entries"]] == [1, 3]
    assert [e["rank"] for e in k3["rejected_entries"]] == [2]
    assert k3["fair_draw_exact_coverage_fraction"] == "7930128/85900584"
    for e in k3["accepted_entries"]:
        assert e["exact_coverage_fraction"] == "7930128/85900584"
    for e in k3["rejected_entries"]:
        assert e["exact_coverage_fraction"] is None

    # K5 assertions
    k5 = doc["k5"]
    assert k5["is_available"] is True
    assert k5["availability_status"] == "AVAILABLE"
    assert k5["accepted_strategy_count"] == 2
    assert k5["rejected_strategy_count"] == 1
    assert [e["rank"] for e in k5["accepted_entries"]] == [1, 2]
    assert [e["rank"] for e in k5["rejected_entries"]] == [3]
    assert k5["fair_draw_exact_coverage_fraction"] == "13139880/85900584"
    for e in k5["accepted_entries"]:
        assert e["exact_coverage_fraction"] == "13139880/85900584"
    for e in k5["rejected_entries"]:
        assert e["exact_coverage_fraction"] is None

    assert doc["accepted_counts_by_k"] == {"k2": 2, "k3": 2, "k5": 2}
    assert doc["rejected_counts_by_k"] == {"k2": 1, "k3": 1, "k5": 1}

    # Verify generated files exist
    json_file = tmp_path / "predictions_115000098.json"
    txt_file = tmp_path / "tickets_115000098.txt"
    assert json_file.exists()
    assert txt_file.exists()


def test_ac7_reproducibility(tmp_path: Path) -> None:
    """AC7:
    Two executions with the same input produce identical JSON and ticket text bytes.
    """
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    run_prediction(
        cutoff_draw="115000097",
        target_draw="115000098",
        output_dir=out1,
    )
    run_prediction(
        cutoff_draw="115000097",
        target_draw="115000098",
        output_dir=out2,
    )

    json1 = (out1 / "predictions_115000098.json").read_bytes()
    json2 = (out2 / "predictions_115000098.json").read_bytes()
    assert json1 == json2

    txt1 = (out1 / "tickets_115000098.txt").read_bytes()
    txt2 = (out2 / "tickets_115000098.txt").read_bytes()
    assert txt1 == txt2
