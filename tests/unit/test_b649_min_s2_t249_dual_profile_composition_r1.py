"""Independent exact composition checks and fail-closed certificate mutations."""

from __future__ import annotations

import copy
import json
import os
import re
import runpy
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from fractions import Fraction
from functools import lru_cache, wraps
from inspect import Parameter, Signature, signature
from math import comb
from pathlib import Path
from typing import Any, cast

import pytest
from _pytest.fixtures import FixtureRequest

from lottolab.research import b649_min_s2_t249_dual_profile_composition_r1 as c

_ISOLATED_CHILD_ENV = "B649_T249_ISOLATED_CHILD"
_TEMP_ROOT_ENV = "B649_T249_TEST_TEMP_ROOT"
_PRELOAD_ENV = "B649_T249_PRELOAD_PARENT_RESEARCH"
_REVERSE_ENV = "B649_T249_REVERSE_ORDER"
_REPORT_PATH_ENV = "B649_T249_CHILD_REPORT_PATH"
_TEST_PATH = "tests/unit/test_b649_min_s2_t249_dual_profile_composition_r1.py"
_RUNNER_PATH = "scripts/research/b649_historical_source_closure_isolated_runner_r1.py"
_CHILD_TIMEOUT_SECONDS = 300

EXPECTED_ORIGINAL_NODE_IDS = (
    f"{_TEST_PATH}::test_sealed_result_reproduces",
    f"{_TEST_PATH}::test_immutable_inputs_and_judged_sibling_identities",
    f"{_TEST_PATH}::test_exact_integer_full_t_domain",
    f"{_TEST_PATH}::test_exactly_one_row_and_all_4646_others",
    f"{_TEST_PATH}::test_entire_cursor_identity_bounds_and_coverage",
    f"{_TEST_PATH}::test_family_all_rows_all_cursor_ties_and_remaining_profiles",
    f"{_TEST_PATH}::test_all_caveats_status_snapshots_and_no_bonferroni",
    f"{_TEST_PATH}::test_theorem_execution_forbidden",
    f"{_TEST_PATH}::test_wrong_donor_profile_fails_closed[66665555555331000000]",
    f"{_TEST_PATH}::test_wrong_donor_profile_fails_closed[00000000000000000000]",
    f"{_TEST_PATH}::test_mutated_certificate_fails_closed[bound]",
    f"{_TEST_PATH}::test_mutated_certificate_fails_closed[cap]",
    f"{_TEST_PATH}::test_mutated_certificate_fails_closed[first_term]",
    f"{_TEST_PATH}::test_mutated_certificate_fails_closed[last_term]",
    f"{_TEST_PATH}::test_mutated_certificate_fails_closed[rounding]",
    f"{_TEST_PATH}::test_mutated_certificate_fails_closed[bonferroni]",
    f"{_TEST_PATH}::test_composition_mutations_fail_closed[profile]",
    f"{_TEST_PATH}::test_composition_mutations_fail_closed[bound]",
    f"{_TEST_PATH}::test_composition_mutations_fail_closed[float]",
    f"{_TEST_PATH}::test_composition_mutations_fail_closed[cursor_bound]",
    f"{_TEST_PATH}::test_composition_mutations_fail_closed[cursor_id]",
    f"{_TEST_PATH}::test_composition_mutations_fail_closed[cursor_partition]",
    f"{_TEST_PATH}::test_composition_mutations_fail_closed[other_row]",
    f"{_TEST_PATH}::test_source_hash_and_missing_donor_fail_closed",
    f"{_TEST_PATH}::test_missing_snapshot_fails_closed",
    f"{_TEST_PATH}::test_duplicate_missing_rows_and_duplicate_json_fail_closed",
    f"{_TEST_PATH}::test_forged_expected_cursor_fails_closed",
)


def _private_directory(path: Path) -> None:
    path.mkdir(mode=0o700)
    path.chmod(0o700)
    assert stat.S_IMODE(path.stat().st_mode) == 0o700


@lru_cache(maxsize=1)
def _task_temp_root() -> Path:
    configured = os.environ.get(_TEMP_ROOT_ENV)
    if configured is None:
        root = Path(tempfile.mkdtemp(prefix="t249-test-", dir=tempfile.gettempdir()))
        root.chmod(0o700)
    else:
        root = Path(configured).resolve()
    assert root.is_dir(), f"task temp root is missing: {root}"
    assert root != c.ROOT and not root.is_relative_to(c.ROOT), (
        f"task temp root must be outside the worktree: {root}"
    )
    assert stat.S_IMODE(root.stat().st_mode) == 0o700, (
        f"task temp root must have mode 0700: {root}"
    )
    app_data = root / "app-data"
    if not app_data.exists():
        _private_directory(app_data)
    assert stat.S_IMODE(app_data.stat().st_mode) == 0o700, (
        f"app-data directory must have mode 0700: {app_data}"
    )
    return root


@lru_cache(maxsize=1)
def _historical_runner() -> dict[str, object]:
    return runpy.run_path(str(c.ROOT / _RUNNER_PATH))


def _sealed_source_paths() -> set[str]:
    load_inventory = cast(
        Callable[[Path], dict[str, str]],
        _historical_runner()["load_sealed_source_inventory"],
    )
    return set(load_inventory(c.ROOT))


def research_source_paths() -> set[str]:
    loaded: set[str] = set()
    for name, module in sys.modules.copy().items():
        if name.startswith("lottolab.research.") and name != c.__name__:
            source = getattr(module, "__file__", None)
            assert source is not None, f"research module without source: {name}"
            path = Path(str(source)).resolve()
            assert path.is_relative_to(c.ROOT), f"research module outside worktree: {path}"
            loaded.add(path.relative_to(c.ROOT).as_posix())
    return loaded


def _output_text(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def _run_bounded_subprocess(
    command: Sequence[str], cwd: Path, env: dict[str, str], timeout_seconds: float
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            cwd=cwd,
            env=env,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = _output_text(exc.stdout), _output_text(exc.stderr)
        raise AssertionError(
            f"child process timed out after {timeout_seconds:g}s\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        ) from exc


def _assert_child_success(
    result: subprocess.CompletedProcess[str],
    expected_nodeid: str | None = None,
    allowed_stderr: Sequence[str] = (),
) -> None:
    details = f"exit={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert result.returncode == 0, f"isolated child failed\n{details}"
    if result.stderr:
        stderr_lines = tuple(result.stderr.splitlines())
        assert stderr_lines == tuple(allowed_stderr), (
            f"isolated child wrote unexpected stderr\n{details}"
        )
        print("T249_CHILD_STDERR_CAPTURED=" + json.dumps(stderr_lines))
    if expected_nodeid is not None:
        passed = any(
            expected_nodeid in line and re.search(r"\bPASSED\b", line)
            for line in result.stdout.splitlines()
        )
        assert passed, (
            f"isolated child did not report this node as passed: {expected_nodeid}\n{details}"
        )


_isolated_suite_outcomes_cache: dict[str, str] | None = None
_isolated_suite_failure: str | None = None


def _isolated_suite_outcomes() -> dict[str, str]:
    global _isolated_suite_outcomes_cache, _isolated_suite_failure
    if _isolated_suite_failure is not None:
        raise AssertionError(_isolated_suite_failure)
    if _isolated_suite_outcomes_cache is not None:
        return _isolated_suite_outcomes_cache

    root = c.ROOT.resolve()
    task_root = _task_temp_root()
    child_root = Path(tempfile.mkdtemp(prefix="t249-child-", dir=task_root))
    child_root.chmod(0o700)
    app_data = child_root / "app-data"
    child_tmp = child_root / "tmp"
    _private_directory(app_data)
    _private_directory(child_tmp)
    basetemp = child_root / "pytest"
    assert "b649" not in str(basetemp).casefold(), f"unsafe pytest basetemp: {basetemp}"
    report_path = child_root / "node-results.json"

    env = os.environ.copy()
    env[_ISOLATED_CHILD_ENV] = "1"
    env[_TEMP_ROOT_ENV] = str(task_root)
    env[_REPORT_PATH_ENV] = str(report_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TMPDIR"] = str(child_tmp)
    env["XDG_CACHE_HOME"] = str(app_data)
    env["XDG_DATA_HOME"] = str(app_data)
    pythonpath_parts = (str(root / "src"), str(root / "tests/unit"), env.get("PYTHONPATH", ""))
    env["PYTHONPATH"] = os.pathsep.join(part for part in pythonpath_parts if part)
    env.pop(_PRELOAD_ENV, None)

    driver = cast(str, _historical_runner()["_ISOLATED_PYTEST_DRIVER"])
    command = [
        sys.executable,
        "-c",
        driver,
        _TEST_PATH,
        "-p",
        "no:cacheprovider",
        "-p",
        "test_b649_t249_collection_isolation_r1",
        f"--basetemp={basetemp}",
        "-vv",
        "--tb=short",
        "-s",
    ]
    if os.environ.get(_REVERSE_ENV) == "1":
        env[_REVERSE_ENV] = "1"
    else:
        env.pop(_REVERSE_ENV, None)

    try:
        result = _run_bounded_subprocess(command, root, env, _CHILD_TIMEOUT_SECONDS)
        _assert_child_success(
            result,
            allowed_stderr=("fatal: git cat-file: could not get object info",),
        )
        runner = _historical_runner()
        extract = cast(Callable[[str], Any], runner["extract_runtime_loaded_helpers"])
        runtime = extract(result.stdout)
        assert runtime["pytest_exit_code"] == result.returncode
        modules_value = runtime["modules"]
        assert isinstance(modules_value, list), (
            f"child Research module report is malformed: {modules_value}"
        )
        modules = cast(list[object], modules_value)
        actual_paths: set[str] = set()
        for entry in modules:
            assert isinstance(entry, dict), f"child Research module entry is malformed: {entry}"
            module_record = cast(dict[str, object], entry)
            assert module_record.get("inside_worktree") is True, (
                f"Research module resolved outside worktree: {module_record}"
            )
            module_path = module_record.get("path")
            assert isinstance(module_path, str), (
                f"child Research path is malformed: {module_record}"
            )
            actual_paths.add(module_path)
        assert actual_paths == _sealed_source_paths() | {c.SOURCE}, (
            f"child Research module set differs: actual={sorted(actual_paths)}"
        )
        assert report_path.is_file(), f"child pytest report is missing: {report_path}"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        expected_nodeids = list(EXPECTED_ORIGINAL_NODE_IDS)
        if os.environ.get(_REVERSE_ENV) == "1":
            expected_nodeids.reverse()
        assert report["collected_node_ids"] == expected_nodeids, (
            "isolated child collected different original node IDs or order: "
            f"{report['collected_node_ids']}"
        )
        assert set(report["outcomes"]) == set(EXPECTED_ORIGINAL_NODE_IDS), (
            "isolated child did not report every original node ID"
        )
        assert not report["solver_modules"], (
            f"solver was unexpectedly loaded: {report['solver_modules']}"
        )
        outcome_records = report["outcomes"]
        assert all(isinstance(record, dict) for record in outcome_records.values()), (
            f"isolated child reported malformed outcomes: {outcome_records}"
        )
        assert all(record.get("wasxfail") is None for record in outcome_records.values()), (
            f"isolated child unexpectedly xfailed tests: {outcome_records}"
        )
        outcomes = {
            nodeid: str(result_data["outcome"])
            for nodeid, result_data in outcome_records.items()
        }
        assert all(outcome == "passed" for outcome in outcomes.values()), (
            f"isolated child test outcomes were not all PASS: {outcomes}"
        )
    except AssertionError as exc:
        _isolated_suite_failure = str(exc)
        raise

    _isolated_suite_outcomes_cache = outcomes
    return outcomes


def _isolated_original_test(
    *parameter_names: str,
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    def decorate(function: Callable[..., object]) -> Callable[..., object]:
        original_parameters = tuple(signature(function).parameters)
        assert set(parameter_names).issubset(original_parameters)
        wrapper_parameters = [Parameter("request", Parameter.POSITIONAL_OR_KEYWORD)]
        wrapper_parameters.extend(
            Parameter(name, Parameter.POSITIONAL_OR_KEYWORD) for name in parameter_names
        )

        @wraps(function)
        def isolated_test(*args: object, **kwargs: object) -> object:
            request_value = kwargs.get("request", args[0] if args else None)
            assert isinstance(request_value, FixtureRequest)
            request = request_value
            if os.environ.get(_ISOLATED_CHILD_ENV) == "1":
                original_arguments: dict[str, object] = {}
                for name in original_parameters:
                    if name in parameter_names:
                        original_arguments[name] = kwargs[name]
                    else:
                        original_arguments[name] = request.getfixturevalue(name)
                return function(**original_arguments)

            request_node = cast(Any, request).node
            nodeid = str(request_node.nodeid)
            outcome = _isolated_suite_outcomes().get(nodeid)
            assert outcome == "passed", (
                f"isolated child did not PASS original node {nodeid}: {outcome}"
            )
            return None

        cast(Any, isolated_test).__signature__ = Signature(wrapper_parameters)
        return cast(Callable[..., object], isolated_test)

    return decorate


@pytest.fixture(scope="module")
def inputs() -> c.Inputs:
    return c.load_inputs()


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return c.compute_result()


@_isolated_original_test()
def test_sealed_result_reproduces(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.render(result)
    assert result["IMPLEMENTATION_SHA256"] == c.sha((c.ROOT / c.SOURCE).read_bytes())


@_isolated_original_test()
def test_immutable_inputs_and_judged_sibling_identities(inputs: c.Inputs) -> None:
    base, donor, pins = inputs
    assert pins["BASE_HEAD"] == c.BASE_HEAD and pins["BASE_TREE"] == c.BASE_TREE
    assert pins["DONOR_HEAD"] == c.DONOR_HEAD and pins["DONOR_TREE"] == c.DONOR_TREE
    assert c.git("merge-base", c.BASE_HEAD, c.DONOR_HEAD).decode().strip() == base["BASE_HEAD"]
    assert donor["BASE_HEAD"] == base["BASE_HEAD"]
    with pytest.raises(subprocess.CalledProcessError) as rejected:
        c.git("merge-base", "--is-ancestor", c.DONOR_HEAD, c.BASE_HEAD)
    assert rejected.value.returncode == 1


@_isolated_original_test()
def test_exact_integer_full_t_domain(inputs: c.Inputs, result: dict[str, object]) -> None:
    donor = inputs[1]
    d = tuple(map(int, c.string(donor["TARGET_PROFILE"])))
    degrees = tuple(6 + x for x in d)
    w = sum(x * (x - 1) // 2 for x in degrees)
    triples = sum(x * (x - 1) * (x - 2) // 6 for x in degrees)
    contained_cap = sum(x * (g - 2) for x, g in zip(d, degrees, strict=True)) // 3
    theorem = c.obj(donor["THEOREM"])
    model = c.obj(donor["SUPPORT_MODEL"])
    expected: list[list[int]] = []
    for t in range(c.integer(model["T_MIN"]), c.integer(theorem["T_CAP"]) + 1):
        k4 = max(0, -(-(triples - (max(degrees) - 2) * (w - 3 * t)) // 4))
        contained = min(k4, contained_cap)
        s4 = max(112, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        rational = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        bound = -(-rational.numerator // rational.denominator)
        assert Fraction(bound - 1) < rational <= bound
        expected.append([t, bound, k4, contained, s4, s3])
    assert c.obj(result["ROUTE_B"])["ALL_T_TERMS"] == expected
    assert expected == c.obj(donor["ROUTE_B"])["ALL_T_TERMS"]
    assert len(expected) == c.integer(theorem["T_CAP"]) - c.integer(model["T_MIN"]) + 1
    assert max(t[1] for t in expected) == donor["PROFILE_BOUND"]
    assert w == sum(comb(g, 2) for g in degrees)


@_isolated_original_test()
def test_exactly_one_row_and_all_4646_others(inputs: c.Inputs, result: dict[str, object]) -> None:
    before = c.obj(inputs[0]["RESOLVED_ROW_BOUNDS"])
    after = c.obj(result["RESOLVED_ROW_BOUNDS"])
    assert len(before) == len(after) == 4647 and set(before) == set(after)
    assert [p for p in before if before[p] != after[p]] == [c.TARGET]
    untouched_before = {p: v for p, v in before.items() if p != c.TARGET}
    untouched_after = {p: v for p, v in after.items() if p != c.TARGET}
    assert len(untouched_before) == 4646 and untouched_before == untouched_after
    assert result["INHERITED_TWO_PROFILE_ROW_UPDATES_VERBATIM"] == inputs[0]["ROW_UPDATES"]
    for p in c.inherited.TARGETS:
        assert before[p] == after[p] == c.obj(c.obj(inputs[0]["ROW_UPDATES"])[p])["AFTER_BOUND"]


@_isolated_original_test()
def test_entire_cursor_identity_bounds_and_coverage(
    inputs: c.Inputs, result: dict[str, object]
) -> None:
    cursor = c.obj(result["CURSOR"])
    assert cursor == inputs[0]["CURSOR"] == c.obj(inputs[1]["BASE_AUTHORITY"])["CURSOR"]
    assert c.sha(c.render(cursor)) == c.CURSOR_SHA
    ids = c.items(cursor["PROFILE_IDS"])
    assert len(ids) == len(set(c.string(p) for p in ids)) == cursor["PROFILE_COUNT"] == 197
    assert set(ids) == set(c.obj(cursor["COARSE_BOUND_PROJECTION"]))
    assert not set(ids).intersection(c.obj(result["RESOLVED_ROW_BOUNDS"]))


@_isolated_original_test()
def test_family_all_rows_all_cursor_ties_and_remaining_profiles(result: dict[str, object]) -> None:
    ledger = c.obj(result["RESOLVED_ROW_BOUNDS"])
    cursor = c.obj(result["CURSOR"])
    all_bounds = {**ledger, **c.obj(cursor["COARSE_BOUND_PROJECTION"])}
    assert len(all_bounds) == 4647 + c.integer(cursor["PROFILE_COUNT"])
    ranked = sorted((c.integer(b), p) for p, b in all_bounds.items())
    maximum = ranked[-1][0]
    owners = sorted(p for b, p in ranked if b == maximum)
    assert result["FAMILY_BOUND_AFTER"] == maximum
    assert result["FAMILY_OWNER_IDS"] == owners
    incumbent = c.integer(result["INCUMBENT"])
    assert result["GAP_TO_INCUMBENT"] == maximum - incumbent
    assert result["EXACT_FAMILY_DELTA"] == c.integer(result["FAMILY_BOUND_BEFORE"]) - maximum
    assert result["STILL_OPEN_PROFILE_COUNT"] == sum(b > incumbent for b, _ in ranked)
    assert result["RESOLVED_OPEN_PROFILE_IDS"] == sorted(
        p for p, b in ledger.items() if c.integer(b) > incumbent
    )
    assert c.family(
        {"row1": maximum, "row2": maximum}, {"COARSE_BOUND_PROJECTION": {"cursor1": maximum}}
    ) == (maximum, ["cursor1", "row1", "row2"])


@_isolated_original_test()
def test_all_caveats_status_snapshots_and_no_bonferroni(
    inputs: c.Inputs, result: dict[str, object]
) -> None:
    original, donor, _ = inputs
    snapshots = c.obj(result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"])
    for k, v in original.items():
        if k.startswith("INHERITED_") or k in (
            "ATTAINABILITY",
            "FULL_METADATA_DIGEST_AFTER",
            "LEDGER_VIEW",
        ):
            assert snapshots[k] == v
    assert result["INHERITED_TWO_PROFILE_THEOREMS_VERBATIM"] == original["THEOREMS"]
    assert result["DONOR_THEOREM_VERBATIM"] == donor["THEOREM"]
    status = c.obj(result["DONOR_STATUS_SNAPSHOTS_VERBATIM"])
    assert status["TASK_STATUS"] == donor["TASK_STATUS"]
    assert status["HISTORICAL_R2"] == donor["HISTORICAL_R2"]
    assert status["SCENARIO_2_STATUS"] == "PROJECTED_ONLY"
    assert result["CERTIFICATES_ADOPTED"] == {**c.inherited.CAPS, c.TARGET: c.CAP}
    assert result["BONFERRONI_5_ADOPTED"] == "NO"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"


@_isolated_original_test()
def test_theorem_execution_forbidden(
    monkeypatch: pytest.MonkeyPatch, result: dict[str, object]
) -> None:
    def forbidden() -> dict[str, object]:
        pytest.fail("theorem must not be re-executed")

    monkeypatch.setattr(c.inherited, "theorem_a", forbidden)
    monkeypatch.setattr(c.inherited, "theorem_b", forbidden)
    assert c.compute_result() == result


@_isolated_original_test("pid")
@pytest.mark.parametrize("pid", [c.inherited.PROFILE_A, "0" * 20])
def test_wrong_donor_profile_fails_closed(inputs: c.Inputs, pid: str) -> None:
    donor = copy.deepcopy(inputs[1])
    donor["TARGET_PROFILE"] = pid
    with pytest.raises(AssertionError, match="wrong donor profile"):
        c.validate_donor(donor)


@_isolated_original_test("mutation")
@pytest.mark.parametrize(
    "mutation", ["bound", "cap", "first_term", "last_term", "rounding", "bonferroni"]
)
def test_mutated_certificate_fails_closed(inputs: c.Inputs, mutation: str) -> None:
    donor = copy.deepcopy(inputs[1])
    if mutation == "bound":
        donor["PROFILE_BOUND"] = c.integer(donor["PROFILE_BOUND"]) + 1
    elif mutation == "cap":
        c.obj(donor["THEOREM"])["T_CAP"] = c.CAP - 1
    elif mutation in ("first_term", "last_term"):
        c.items(c.obj(donor["ROUTE_B"])["ALL_T_TERMS"]).pop(0 if mutation == "first_term" else -1)
    elif mutation == "rounding":
        row = c.items(c.items(c.obj(donor["ROUTE_B"])["ALL_T_TERMS"])[-1])
        row[1] = c.integer(row[1]) - 1
    else:
        c.obj(donor["HISTORICAL_R2"])["BONFERRONI_5_USED"] = "YES"
    with pytest.raises(AssertionError, match=r"scope|bound/domain|unadopted"):
        c.validate_donor(donor)


@_isolated_original_test("mutation")
@pytest.mark.parametrize(
    "mutation",
    ["profile", "bound", "float", "cursor_bound", "cursor_id", "cursor_partition", "other_row"],
)
def test_composition_mutations_fail_closed(inputs: c.Inputs, mutation: str) -> None:
    base, donor, _ = inputs
    bounds = {p: c.integer(v) for p, v in c.obj(base["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = copy.deepcopy(c.obj(base["CURSOR"]))
    pid, bound = c.TARGET, c.integer(donor["PROFILE_BOUND"])
    if mutation == "profile":
        pid = c.inherited.PROFILE_B
    elif mutation == "bound":
        bound += 1
    elif mutation == "float":
        c.obj(c.obj(donor := copy.deepcopy(donor))["ROW_UPDATE"])["AFTER"] = {
            "cap": 249,
            "bound": float(bound),
            "s4_base": 112,
        }
    elif mutation == "cursor_bound":
        cursor["BOUND"] = c.integer(cursor["BOUND"]) - 1
    elif mutation == "cursor_id":
        c.items(cursor["PROFILE_IDS"])[0] = "0" * 20
    elif mutation == "cursor_partition":
        c.obj(c.obj(cursor["PARTITION"])["UNRESOLVED_FRONTIER_UNDER_W785_CURSOR"])["COUNT"] = 196
    else:
        bounds[c.inherited.PROFILE_A] += 1
    with pytest.raises(AssertionError, match=r"wrong update|bound/domain|cursor|projection"):
        c.compose(bounds, cursor, c.obj(base["CURSOR"]), donor, pid, bound)


@_isolated_original_test()
def test_source_hash_and_missing_donor_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(AssertionError, match="source-hash"):
        c.blob(c.BASE_HEAD, c.BASE_RESULT, "0" * 64)
    with pytest.raises(AssertionError, match="source-hash"):
        c.local_blob(f"{c.SOURCES}/donor-result.json", "0" * 64)
    monkeypatch.setattr(c, "DONOR_HEAD", "0" * 40)
    with pytest.raises(subprocess.CalledProcessError):
        c.load_inputs()


@_isolated_original_test()
def test_missing_snapshot_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(c, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        c.local_blob(f"{c.SOURCES}/donor-result.json", c.DONOR_RESULT_SHA)


@_isolated_original_test()
def test_duplicate_missing_rows_and_duplicate_json_fail_closed(inputs: c.Inputs) -> None:
    rows = [(p, c.integer(v)) for p, v in c.obj(inputs[0]["RESOLVED_ROW_BOUNDS"]).items()]
    for bad in [rows[:-1], [rows[0], *rows[:-1]]]:
        with pytest.raises(AssertionError, match="row count"):
            c.validate_rows(bad)
    with pytest.raises(AssertionError, match="duplicate JSON"):
        c.decode(b'{"PROFILE_BOUND":1,"PROFILE_BOUND":2}')


@_isolated_original_test()
def test_forged_expected_cursor_fails_closed(inputs: c.Inputs) -> None:
    cursor = copy.deepcopy(c.obj(inputs[0]["CURSOR"]))
    cursor["BOUND"] = c.integer(cursor["BOUND"]) - 1
    with pytest.raises(AssertionError, match="expected cursor source-hash"):
        c.validate_cursor(cursor, cursor)
