from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = (
    REPO_ROOT
    / ".task-data/B649_K20_V7_DESTROY5_GLOBAL_POOL_2048_R1/run1"
)
LAUNCHER_PATH = RUN_ROOT / "continuation8_launcher.py"
DRIVER_PATH = RUN_ROOT / "driver.py"


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _inputs() -> dict[str, Any]:
    return {
        "start_doc": {
            "START_SOURCE_COMMIT": "c" * 40,
            "START_SOURCE_FILE_SHA256": "d" * 64,
        },
        "source_sha256": {},
        "verification_sha256": "e" * 64,
    }


def _synthetic_driver(name: str) -> Any:
    driver = _load_module(DRIVER_PATH, name)
    # The runner hook is real; these stubs keep the integration case free of
    # scoring, destroy-set execution, recounts, launcher gates, and sealing I/O.
    driver.apply_set_row = lambda *_args, **_kwargs: None
    driver.summarize_set_row = lambda row: {
        "SET_INDEX": row["SET_INDEX"],
        "BEST_COUNT": row["BEST_COUNT"],
        "BEST_DELTA": row["BEST_DELTA"],
    }
    return driver


def _bind(driver: Any, run_root: Path, **kwargs: Any) -> tuple[Any, dict[str, str]]:
    launcher = _load_module(LAUNCHER_PATH, f"_b649_2048_launcher_{id(driver)}")
    return launcher.bind_execution_authority(
        driver,
        REPO_ROOT,
        run_root,
        _test_only_allow_synthetic_run_root=True,
        **kwargs,
    )


def test_continuation8_binds_persistence_classification_resume_and_terminal_seal(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run1"
    run_root.mkdir()
    state_path = run_root / "state.json"
    driver = _synthetic_driver("_b649_2048_execution_driver_first")
    binding, source_hashes = _bind(driver, run_root)

    assert driver.TASK_ID == "B649_K20_V7_DESTROY5_GLOBAL_POOL_2048_R1"
    assert driver.START_COUNT == 313_239_661
    assert driver.START_SHA256 == (
        "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
    )
    assert set(source_hashes) == {
        "src/lottolab/research/b649_k20_destroy5_result_semantics.py",
        "src/lottolab/research/b649_k20_destroy5_execution_authority.py",
    }

    state = driver.initialize_state(state_path, REPO_ROOT, _inputs())
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["START_COUNT"] == 313_239_661
    assert persisted["LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_COUNT"] == 313_263_888
    assert persisted["LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_SHA256"] == (
        "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
    )
    assert persisted["LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_ARTIFACT_LOCATOR"] == (
        "git:032ce592c3efd0ac4b5b82a813d157224419c794:"
        "docs/research/matrix-native-results/"
        "b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
    )
    assert not any("INCUMBENT" in key for key in _inputs()["start_doc"])
    assert binding["authority"]().count == 313_263_888

    expected = (
        (313_239_661, 0, -24_227, "NO", "NO"),
        (313_239_662, 1, -24_226, "YES", "NO"),
        (313_263_888, 24_227, 0, "YES", "NO"),
        (313_263_889, 24_228, 1, "YES", "YES"),
    )
    for index, (count, frozen_delta, incumbent_delta, local_gain, global_gain) in enumerate(
        expected, start=1
    ):
        row = {
            "SET_INDEX": index,
            "BEST_COUNT": count,
            "BEST_DELTA": count - 313_239_661,
        }
        driver.apply_set_row({}, row, (), "", None, None, None)
        serialized = json.loads(driver.canonical_json(row))
        assert serialized["CURRENT_VERIFIED_INCUMBENT_COUNT"] == 313_263_888
        assert serialized["DELTA_FROM_FROZEN_START"] == frozen_delta
        assert serialized["DELTA_FROM_CURRENT_VERIFIED_INCUMBENT"] == incumbent_delta
        assert serialized["LOCAL_GAIN_VS_FROZEN_START"] == local_gain
        assert serialized["GLOBAL_STRICT_GAIN"] == global_gain
        summary = driver.summarize_set_row(row)
        assert summary["GLOBAL_STRICT_GAIN"] == global_gain

    for best_count, expected_global, expected_result in (
        (313_263_888, "NO", "NO_GLOBAL_IMPROVEMENT_IN_V7_DESTROY5_2048_CAMPAIGN"),
        (313_263_889, "YES", "IMPROVED_VS_CURRENT_VERIFIED_INCUMBENT"),
    ):
        terminal = {
            "TASK_ID": driver.TASK_ID,
            "TASK_STATUS": "COMPLETE",
            "SCIENTIFIC_RESULT": "IMPROVED",
            "BEST_COUNT": best_count,
            "BEST_DELTA": best_count - 313_239_661,
            "BEST_CANONICAL_RECOUNT": best_count,
            "SETS_COMPLETED": 2048,
            "DESTROY_SET_COUNT_EXPECTED": 2048,
        }
        sealed = json.loads(driver.canonical_json(terminal))
        assert sealed["DELTA_FROM_FROZEN_START"] == best_count - 313_239_661
        assert sealed["DELTA_FROM_CURRENT_VERIFIED_INCUMBENT"] == best_count - 313_263_888
        assert sealed["LOCAL_GAIN_VS_FROZEN_START"] == "YES"
        assert sealed["GLOBAL_STRICT_GAIN"] == expected_global
        assert sealed["STRICT_GAIN"] is (expected_global == "YES")
        assert sealed["SCIENTIFIC_RESULT"] == expected_result

    resolver_calls: list[bool] = []
    semantics = binding["semantics"]
    newer_authority = semantics.IncumbentAuthority(
        count=313_263_889,
        sha256="a" * 64,
        artifact_locator="git:" + "b" * 40 + ":docs/research/newer-result.json",
        source_commit="b" * 40,
    )

    def newer_resolver() -> Any:
        resolver_calls.append(True)
        return newer_authority

    resumed_driver = _synthetic_driver("_b649_2048_execution_driver_resume")
    resumed_binding, _ = _bind(
        resumed_driver,
        run_root,
        incumbent_resolver=newer_resolver,
    )
    resumed_state = resumed_driver.initialize_state(
        state_path, REPO_ROOT, _inputs()
    )
    assert resolver_calls == []
    assert resumed_binding["authority"]() == binding["authority"]()
    assert resumed_state["LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_COUNT"] == 313_263_888
    assert json.loads(state_path.read_text(encoding="utf-8"))[
        "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_COUNT"
    ] == 313_263_888
