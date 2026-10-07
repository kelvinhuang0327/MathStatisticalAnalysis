"""Bind the protected 2048 Destroy5 driver to persisted dual-threshold results.

This adapter changes only execution authority and result serialization hooks.
The frozen scientific driver and its search inputs remain untouched.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


TASK_ID = "B649_K20_V7_DESTROY5_GLOBAL_POOL_2048_R1"
EXPECTED_START_COUNT = 313_239_661
EXPECTED_START_SHA256 = (
    "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
)
RESULT_SEMANTICS_RELATIVE_PATH = Path(
    "src/lottolab/research/b649_k20_destroy5_result_semantics.py"
)
RUN_ARTIFACTS_WITHOUT_AUTHORITY = (
    "set-results.jsonl",
    "canonical-recounts.jsonl",
    "result.json",
)
_BINDING_ATTRIBUTE = "_b649_destroy5_execution_authority_binding"

_LAUNCH_AUTHORITY_FIELDS = (
    "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_COUNT",
    "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_SHA256",
    "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_ARTIFACT_LOCATOR",
    "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_SOURCE_COMMIT",
)
_COMPAT_AUTHORITY_FIELDS = (
    "CURRENT_VERIFIED_INCUMBENT_COUNT",
    "CURRENT_VERIFIED_INCUMBENT_SHA256",
    "CURRENT_INCUMBENT_AUTHORITY_LOCATOR",
    "CURRENT_VERIFIED_INCUMBENT_SOURCE_COMMIT",
)


def _load_result_semantics(repo_root: Path) -> ModuleType:
    path = repo_root / RESULT_SEMANTICS_RELATIVE_PATH
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Destroy5 dual-threshold result semantics are unavailable")
    module_name = "_b649_k20_destroy5_result_semantics_for_execution_authority"
    semantics = __import__("sys").modules.get(module_name)
    if semantics is None:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Destroy5 result semantics module cannot be loaded")
        semantics = importlib.util.module_from_spec(spec)
        __import__("sys").modules[module_name] = semantics
        spec.loader.exec_module(semantics)
    if Path(semantics.__file__).resolve() != path.resolve():
        raise RuntimeError("Destroy5 result semantics import escaped the repository")
    if semantics.FROZEN_START_COUNT != EXPECTED_START_COUNT:
        raise RuntimeError("Destroy5 result semantics disagrees with frozen START")
    return semantics


def _state_authority_fields(authority: Any, semantics: ModuleType) -> dict[str, Any]:
    fields = semantics.execution_authority_fields(authority)
    return {
        **fields,
        "CURRENT_VERIFIED_INCUMBENT_COUNT": authority.count,
        "CURRENT_VERIFIED_INCUMBENT_SHA256": authority.sha256,
        "CURRENT_INCUMBENT_AUTHORITY_LOCATOR": authority.artifact_locator,
        "CURRENT_VERIFIED_INCUMBENT_SOURCE_COMMIT": authority.source_commit,
    }


def _authority_from_state(
    state: dict[str, Any], semantics: ModuleType
) -> Any | None:
    launch_present = [key in state for key in _LAUNCH_AUTHORITY_FIELDS]
    compat_present = [key in state for key in _COMPAT_AUTHORITY_FIELDS]
    if any(launch_present) and not all(launch_present):
        raise RuntimeError("persisted launch-time incumbent authority is partial")
    if any(compat_present) and not all(compat_present):
        raise RuntimeError("persisted incumbent authority compatibility fields are partial")
    if not any(launch_present) and not any(compat_present):
        return None

    if all(launch_present):
        authority = semantics.IncumbentAuthority(
            count=state[_LAUNCH_AUTHORITY_FIELDS[0]],
            sha256=state[_LAUNCH_AUTHORITY_FIELDS[1]],
            artifact_locator=state[_LAUNCH_AUTHORITY_FIELDS[2]],
            source_commit=state[_LAUNCH_AUTHORITY_FIELDS[3]],
        )
    else:
        authority = semantics.IncumbentAuthority(
            count=state[_COMPAT_AUTHORITY_FIELDS[0]],
            sha256=state[_COMPAT_AUTHORITY_FIELDS[1]],
            artifact_locator=state[_COMPAT_AUTHORITY_FIELDS[2]],
            source_commit=state[_COMPAT_AUTHORITY_FIELDS[3]],
        )

    expected = _state_authority_fields(authority, semantics)
    keys_to_validate = list(_LAUNCH_AUTHORITY_FIELDS if all(launch_present) else ())
    keys_to_validate += list(_COMPAT_AUTHORITY_FIELDS if all(compat_present) else ())
    if any(state.get(key) != expected[key] for key in keys_to_validate):
        raise RuntimeError("resume incumbent authority is invalid or inconsistent")
    return authority


def classify_set_result(
    row: dict[str, Any], authority: Any, semantics: ModuleType
) -> dict[str, Any]:
    fields = semantics.classify_candidate(int(row["BEST_COUNT"]), authority)
    if row.get("BEST_DELTA") != fields["DELTA_FROM_FROZEN_START"]:
        raise RuntimeError("set BEST_DELTA differs from frozen START classification")
    if (
        "CURRENT_VERIFIED_INCUMBENT_COUNT" in row
        and row["CURRENT_VERIFIED_INCUMBENT_COUNT"] != authority.count
    ):
        raise RuntimeError("set result uses a different launch-time incumbent")
    for key, value in fields.items():
        if key in row and row[key] != value:
            raise RuntimeError(f"set result classification mismatch at {key}")
    row.update(fields)
    row["CURRENT_VERIFIED_INCUMBENT_COUNT"] = authority.count
    return row


def seal_terminal_result(
    result: dict[str, Any], authority: Any, semantics: ModuleType
) -> dict[str, Any]:
    best_count = int(result["BEST_COUNT"])
    if int(result.get("BEST_CANONICAL_RECOUNT", -1)) != best_count:
        raise RuntimeError("terminal result lacks a matching canonical best recount")
    fields = semantics.classify_candidate(best_count, authority)
    if result.get("BEST_DELTA") != fields["DELTA_FROM_FROZEN_START"]:
        raise RuntimeError("terminal BEST_DELTA differs from frozen START classification")
    for key, value in fields.items():
        if key in result and result[key] != value:
            raise RuntimeError(f"terminal result classification mismatch at {key}")

    sets_completed = int(result["SETS_COMPLETED"])
    sample_count = int(result["DESTROY_SET_COUNT_EXPECTED"])
    if sets_completed != sample_count:
        raise RuntimeError("terminal result does not seal a complete frozen sample")
    scientific_result = semantics.terminal_scientific_result(
        best_canonically_verified_count=best_count,
        launch_time_incumbent=authority,
        sets_completed=sets_completed,
        sample_count=sample_count,
    )
    if scientific_result is None:
        raise RuntimeError("terminal scientific result is unresolved")

    result.update(_state_authority_fields(authority, semantics))
    result.update(fields)
    result["STRICT_GAIN"] = fields["GLOBAL_STRICT_GAIN"] == "YES"
    result["SCIENTIFIC_RESULT"] = scientific_result
    return result


def bind_driver(
    driver: ModuleType,
    repo_root: Path,
    run_root: Path,
    *,
    incumbent_resolver: Callable[[], Any] | None = None,
    _test_only_allow_synthetic_run_root: bool = False,
) -> dict[str, Any]:
    """Bind one exact 2048 driver module to authority and classification hooks."""

    repo = Path(repo_root).resolve()
    run = Path(run_root).resolve()
    expected_run = repo / ".task-data" / TASK_ID / str(driver.EXECUTION_ID)
    expected_driver = expected_run / "driver.py"
    if driver.TASK_ID != TASK_ID:
        raise RuntimeError("execution-authority binding targets a different task")
    if int(driver.START_COUNT) != EXPECTED_START_COUNT:
        raise RuntimeError("execution-authority binding targets a different START count")
    if driver.START_SHA256 != EXPECTED_START_SHA256:
        raise RuntimeError("execution-authority binding targets a different START SHA256")
    if not _test_only_allow_synthetic_run_root and run != expected_run:
        raise RuntimeError("execution-authority binding targets a different run root")
    if _test_only_allow_synthetic_run_root and run == expected_run:
        raise RuntimeError("synthetic run-root override must use an isolated test directory")
    if Path(driver.__file__).resolve() != expected_driver:
        raise RuntimeError("execution-authority binding targets a different driver file")

    existing = getattr(driver, _BINDING_ATTRIBUTE, None)
    if existing is not None:
        if existing["repo_root"] == repo and existing["run_root"] == run:
            return existing
        raise RuntimeError("driver module is already bound to another logical run")

    semantics = _load_result_semantics(repo)
    original_initialize_state = driver.initialize_state
    original_apply_set_row = driver.apply_set_row
    original_summarize_set_row = driver.summarize_set_row
    original_canonical_json = driver.canonical_json
    authority_box: dict[str, Any] = {"value": None}
    resolver = incumbent_resolver or semantics.resolve_launch_time_incumbent

    def current_authority() -> Any:
        authority = authority_box["value"]
        if authority is None:
            raise RuntimeError("run authority must be persisted before result classification")
        return authority

    def resolve_for_state(state_path: Path) -> Any:
        if state_path.is_symlink():
            raise RuntimeError("run state must be a regular file")
        if state_path.exists():
            if not state_path.is_file():
                raise RuntimeError("run state must be a regular file")
            loaded = json.loads(state_path.read_text(encoding="utf-8"))
            persisted = _authority_from_state(loaded, semantics)
            if persisted is not None:
                if authority_box["value"] is not None and authority_box["value"] != persisted:
                    raise RuntimeError("run authority changed within one logical run")
                authority_box["value"] = persisted
                return persisted
            if any((run / name).exists() for name in RUN_ARTIFACTS_WITHOUT_AUTHORITY):
                raise RuntimeError("run artifacts exist without persisted incumbent authority")
        elif any((run / name).exists() for name in RUN_ARTIFACTS_WITHOUT_AUTHORITY):
            raise RuntimeError("run artifacts exist without persisted incumbent authority")

        if authority_box["value"] is not None:
            return authority_box["value"]
        authority = resolver()
        semantics.execution_authority_fields(authority)
        authority_box["value"] = authority
        return authority

    def canonical_json_with_authority(value: Any) -> bytes:
        if isinstance(value, dict) and value.get("TASK_ID") == TASK_ID:
            if "SCHEMA_VERSION" in value and "EXECUTION_ID" in value:
                authority = current_authority()
                expected = _state_authority_fields(authority, semantics)
                persisted = _authority_from_state(value, semantics)
                if persisted is not None and persisted != authority:
                    raise RuntimeError("run state authority changed before persistence")
                value.update(expected)
            elif (
                value.get("TASK_STATUS") == "COMPLETE"
                and "BEST_CANONICAL_RECOUNT" in value
                and "DESTROY_SET_COUNT_EXPECTED" in value
            ):
                seal_terminal_result(value, current_authority(), semantics)
            elif "SET_INDEX" in value and "BEST_COUNT" in value:
                classify_set_result(value, current_authority(), semantics)
        return original_canonical_json(value)

    def initialize_state_with_authority(
        state_path: Path, repo_root_arg: Path, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        target = Path(state_path).resolve()
        if target != run / "state.json":
            raise RuntimeError("run authority may be persisted only in this logical run state")
        authority = resolve_for_state(Path(state_path))
        state = original_initialize_state(state_path, repo_root_arg, inputs)
        persisted = _authority_from_state(state, semantics)
        if persisted is not None and persisted != authority:
            raise RuntimeError("resumed run authority differs from its persisted incumbent")
        if persisted is None:
            state.update(_state_authority_fields(authority, semantics))
            driver.atomic_write(state_path, original_canonical_json(state))
        return state

    def apply_set_row_with_authority(
        aggregate: dict[str, Any], row: dict[str, Any], *args: Any, **kwargs: Any
    ) -> Any:
        classify_set_result(row, current_authority(), semantics)
        return original_apply_set_row(aggregate, row, *args, **kwargs)

    def summarize_set_row_with_authority(row: dict[str, Any]) -> dict[str, Any]:
        summary = original_summarize_set_row(row)
        classify_set_result(summary, current_authority(), semantics)
        return summary

    driver.canonical_json = canonical_json_with_authority
    driver.initialize_state = initialize_state_with_authority
    driver.apply_set_row = apply_set_row_with_authority
    driver.summarize_set_row = summarize_set_row_with_authority
    binding = {
        "repo_root": repo,
        "run_root": run,
        "semantics": semantics,
        "authority": lambda: authority_box["value"],
    }
    setattr(driver, _BINDING_ATTRIBUTE, binding)
    return binding
