from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER_PATH = (
    REPO_ROOT
    / ".task-data/B649_K20_DESTROY5_GLOBAL_POOL_STRATIFIED_1024_R1/run1/driver.py"
)
DRIVER_MODULE_NAME = "_b649_k20_destroy5_campaign_driver_for_test"
DRIVER_SPEC = importlib.util.spec_from_file_location(DRIVER_MODULE_NAME, DRIVER_PATH)
assert DRIVER_SPEC is not None and DRIVER_SPEC.loader is not None
DRIVER = importlib.util.module_from_spec(DRIVER_SPEC)
sys.modules[DRIVER_MODULE_NAME] = DRIVER
DRIVER_SPEC.loader.exec_module(DRIVER)


def _frozen_start_doc() -> dict[str, Any]:
    return {
        "START_COUNT": DRIVER.EXPECTED_START_COUNT,
        "START_SHA256": DRIVER.EXPECTED_START_SHA256,
    }


def _newer_incumbent(semantics: Any) -> Any:
    return semantics.IncumbentAuthority(
        count=313_263_889,
        sha256="a" * 64,
        artifact_locator="git:" + "b" * 40 + ":docs/research/newer-result.json",
        source_commit="b" * 40,
    )


def test_runner_persists_authority_and_records_both_thresholds(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    journal_path = tmp_path / "set-results.jsonl"
    frozen_start_doc = _frozen_start_doc()
    semantics, state, authority = DRIVER.prepare_run_authority(
        state_path, REPO_ROOT, frozen_start_doc, {"FILES": {}}
    )

    assert DRIVER.EXPECTED_START_COUNT == 313_239_661
    assert semantics.FROZEN_START_COUNT == 313_239_661
    assert state["START_COUNT"] == 313_239_661
    assert state["CURRENT_VERIFIED_INCUMBENT_COUNT"] == 313_263_888
    assert state["CURRENT_VERIFIED_INCUMBENT_SHA256"] == (
        "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
    )
    assert state["CURRENT_INCUMBENT_AUTHORITY_LOCATOR"] == (
        "git:032ce592c3efd0ac4b5b82a813d157224419c794:"
        "docs/research/matrix-native-results/"
        "b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
    )
    assert authority.count == 313_263_888
    assert state["MANIFEST_FILE_SHA256"] == DRIVER.FROZEN_MANIFEST_FILE_SHA256
    assert not any("INCUMBENT" in key for key in frozen_start_doc)

    candidates = (
        (313_239_661, 0, -24_227, "NO", "NO"),
        (313_239_662, 1, -24_226, "YES", "NO"),
        (313_263_888, 24_227, 0, "YES", "NO"),
        (313_263_889, 24_228, 1, "YES", "YES"),
    )
    for index, (count, *_classification) in enumerate(candidates, start=1):
        row = {
            "SET_INDEX": index,
            "BEST_COUNT": count,
            "BEST_DELTA": count - DRIVER.EXPECTED_START_COUNT,
        }
        DRIVER.record_set_result(row, journal_path, authority, semantics)

    recorded = [json.loads(line) for line in journal_path.read_text().splitlines()]
    assert len(recorded) == len(candidates)
    for row, (count, frozen_delta, incumbent_delta, local_gain, global_gain) in zip(
        recorded, candidates, strict=True
    ):
        assert row["BEST_COUNT"] == count
        assert row["CURRENT_VERIFIED_INCUMBENT_COUNT"] == 313_263_888
        assert row["DELTA_FROM_FROZEN_START"] == frozen_delta
        assert row["DELTA_FROM_CURRENT_VERIFIED_INCUMBENT"] == incumbent_delta
        assert row["LOCAL_GAIN_VS_FROZEN_START"] == local_gain
        assert row["GLOBAL_STRICT_GAIN"] == global_gain

    local_only = DRIVER.terminal_result_fields(313_263_888, authority, semantics)
    assert local_only["LOCAL_GAIN_VS_FROZEN_START"] == "YES"
    assert local_only["GLOBAL_STRICT_GAIN"] == "NO"
    assert local_only["STRICT_GAIN"] is False
    global_gain = DRIVER.terminal_result_fields(313_263_889, authority, semantics)
    assert global_gain["GLOBAL_STRICT_GAIN"] == "YES"
    assert global_gain["STRICT_GAIN"] is True


def test_resume_reuses_persisted_launch_authority(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    frozen_start_doc = _frozen_start_doc()
    semantics, first_state, first_authority = DRIVER.prepare_run_authority(
        state_path, REPO_ROOT, frozen_start_doc, {"FILES": {}}
    )
    resolver_calls: list[bool] = []

    def newer_resolver() -> Any:
        resolver_calls.append(True)
        return _newer_incumbent(semantics)

    resumed_semantics, resumed_state, resumed_authority = (
        DRIVER.prepare_run_authority(
            state_path,
            REPO_ROOT,
            frozen_start_doc,
            {"FILES": {}},
            incumbent_resolver=newer_resolver,
        )
    )

    assert resolver_calls == []
    assert resumed_semantics is semantics
    assert resumed_state["CURRENT_VERIFIED_INCUMBENT_COUNT"] == 313_263_888
    assert resumed_state["CURRENT_VERIFIED_INCUMBENT_SHA256"] == (
        first_state["CURRENT_VERIFIED_INCUMBENT_SHA256"]
    )
    assert resumed_state["CURRENT_INCUMBENT_AUTHORITY_LOCATOR"] == (
        first_state["CURRENT_INCUMBENT_AUTHORITY_LOCATOR"]
    )
    assert resumed_authority == first_authority


def test_missing_authority_with_existing_run_artifacts_fails_closed(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    (tmp_path / "set-results.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(
        RuntimeError, match="run artifacts exist without persisted incumbent authority"
    ):
        DRIVER.prepare_run_authority(
            state_path, REPO_ROOT, _frozen_start_doc(), {"FILES": {}}
        )

    assert not state_path.exists()
