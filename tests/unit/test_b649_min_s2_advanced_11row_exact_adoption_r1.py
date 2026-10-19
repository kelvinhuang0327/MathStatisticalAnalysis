"""Exact Advanced-row adoption: identities, independent mathematics, negative cases."""

from __future__ import annotations

import hashlib
import os
import random
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from copy import deepcopy
from fractions import Fraction
from functools import wraps
from itertools import combinations
from math import ceil, comb
from pathlib import Path
from typing import NamedTuple, cast
from xml.etree import ElementTree

import pytest

from lottolab.research import b649_min_s2_advanced_11row_exact_adoption_r1 as v

HISTORICAL_PARENT = "69d2d3fe2696623d75e876e5cd96085297da821c"
HISTORICAL_CHILD = "b280d90be0c35b8c5b1ca7798a394332194f8887"
HISTORICAL_PARENT_TREE = "3fdfa51d658df73afadf6f16eaef145373a529ca"
HISTORICAL_CHILD_TREE = "7d94024cebbce0c05d80902256ccae137fcbc279"
HISTORICAL_TEST = "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py"
HISTORICAL_TEST_BLOB = "c21a91cff3538ee39e51f3c9a05669983cccea00"
HISTORICAL_TEST_SHA256 = "653dc78f718ee509fd9849d2c095f98f60411fdd972615fa50ddcbe971e197e8"
HISTORICAL_SOURCE = "src/lottolab/research/b649_min_s2_advanced_11row_exact_adoption_r1.py"
HISTORICAL_SOURCE_BLOB = "b5bcbdf4f9c515a8b46190e6452f7f2ede32d211"
HISTORICAL_SOURCE_SHA256 = "fcf67c2b2023463d5e26448d82905a4e57b7bed7227a7d2ceee77044b9580bf3"
CANDIDATE_BASE = "f48cc3043af4760a7d439c7029071803414f2260"
CANDIDATE_BASE_TREE = "04a9ccbfefd4620b7d2fb7601e8424518308786e"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_CHILD_CONTEXT_ENV = "ADV11_HISTORICAL_CHILD_CONTEXT"

T264_PROFILES = {"66665555555421000000": 308560, "66666555554411100000": 309183}
WEAKER = [
    "65555555555541000000",
    "66555555554442000000",
    "66555555555431100000",
    "66655555555421100000",
]
A, B = "66655555555431000000", "66665555544441000000"


class ChildRun(NamedTuple):
    exit_code: int
    outcomes: dict[str, str]
    details: dict[str, str]
    stdout: str
    stderr: str
    error: str | None
    evidence_dir: str | None


_child_run: ChildRun | None = None
_HISTORICAL_TEST_NAMES: set[str] = set()
_execution_context_cache: str | None = None


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=False,
        text=True,
    )


def _git_text(root: Path, *args: str) -> str:
    result = _git(root, *args)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _execution_context() -> str:
    global _execution_context_cache
    if _execution_context_cache is None:
        if os.environ.get(HISTORICAL_CHILD_CONTEXT_ENV) == "1":
            _verify_historical_checkout(PROJECT_ROOT)
            _execution_context_cache = "historical-child"
        else:
            _execution_context_cache = "candidate-runner"
    return _execution_context_cache


def _child_report(run: ChildRun, test_name: str) -> str:
    status = run.outcomes.get(test_name, "missing")
    detail = run.details.get(test_name, run.error or "no child test result was recorded")
    return (
        f"Historical Child {HISTORICAL_CHILD} test {test_name} returned {status}; "
        f"child_exit_code={run.exit_code}; evidence_dir={run.evidence_dir}\n"
        f"child detail:\n{detail}\nchild stderr:\n{run.stderr}"
    )


def _assert_child_passed(run: ChildRun, test_name: str) -> None:
    if (
        run.error is not None
        or run.exit_code != 0
        or run.outcomes.get(test_name) != "passed"
    ):
        raise AssertionError(_child_report(run, test_name))


def _private_directory(path: Path) -> None:
    path.mkdir(mode=0o700)
    path.chmod(0o700)


def _verify_historical_child_identity(head: str, tree: str, parents: list[str]) -> None:
    if (head, tree, parents) != (
        HISTORICAL_CHILD,
        HISTORICAL_CHILD_TREE,
        [HISTORICAL_CHILD, HISTORICAL_PARENT],
    ):
        raise RuntimeError(f"wrong historical Child identity: {head} {tree} {parents}")


def _verify_historical_checkout(root: Path) -> None:
    parent_tree = _git_text(root, "rev-parse", f"{HISTORICAL_PARENT}^{{tree}}")
    if parent_tree != HISTORICAL_PARENT_TREE:
        raise RuntimeError(f"wrong historical Parent tree: {parent_tree}")
    head = _git_text(root, "rev-parse", "HEAD")
    tree = _git_text(root, "rev-parse", "HEAD^{tree}")
    parents = _git_text(root, "rev-list", "--parents", "-n", "1", head).split()
    _verify_historical_child_identity(head, tree, parents)
    if _git_text(root, "rev-parse", "--is-shallow-repository") != "false":
        raise RuntimeError("historical Child checkout is shallow")
    objects = _git(root, "rev-list", "--objects", "--missing=print", HISTORICAL_CHILD)
    missing = [line for line in objects.stdout.splitlines() if line.startswith("?")]
    if objects.returncode or missing:
        raise RuntimeError(f"historical Child object graph is incomplete: {missing[:5]}")
    for path, blob, digest in (
        (HISTORICAL_TEST, HISTORICAL_TEST_BLOB, HISTORICAL_TEST_SHA256),
        (HISTORICAL_SOURCE, HISTORICAL_SOURCE_BLOB, HISTORICAL_SOURCE_SHA256),
    ):
        entry = _git_text(root, "ls-tree", HISTORICAL_CHILD, "--", path)
        if entry != f"100644 blob {blob}\t{path}":
            raise RuntimeError(f"historical source blob identity mismatch: {path}: {entry}")
        raw = subprocess.run(
            ["git", "-C", str(root), "show", f"{HISTORICAL_CHILD}:{path}"],
            capture_output=True,
            check=False,
        )
        if raw.returncode or hashlib.sha256(raw.stdout).hexdigest() != digest:
            raise RuntimeError(f"historical source SHA256 mismatch: {path}")


def _historical_case_results(xml_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    xml_root = ElementTree.parse(xml_path).getroot()
    outcomes: dict[str, str] = {}
    details: dict[str, str] = {}
    for case in xml_root.iter("testcase"):
        name = case.attrib.get("name", "")
        if not name:
            continue
        outcome = "passed"
        for tag in ("error", "failure", "skipped"):
            node = case.find(tag)
            if node is not None:
                outcome = "failed" if tag == "failure" else tag
                details[name] = node.attrib.get("message", "") + "\n" + (node.text or "")
                break
        outcomes[name] = outcome
    return outcomes, details


def _run_historical_child(expected_names: set[str]) -> ChildRun:
    runtime_root = Path(tempfile.mkdtemp(prefix="adv11-child-")).resolve()
    runtime_root.chmod(0o700)
    if runtime_root.is_relative_to(PROJECT_ROOT.resolve()):
        shutil.rmtree(runtime_root)
        raise RuntimeError("historical Child runtime directory is inside the repository")
    if "b649" in str(runtime_root).casefold():
        shutil.rmtree(runtime_root)
        raise RuntimeError("historical Child runtime path contains a forbidden B649 segment")
    data_dir, temp_dir, cache_dir, bytecode_dir = (
        runtime_root / name for name in ("app-data", "tmp", "cache", "bytecode")
    )
    for directory in (data_dir, temp_dir, cache_dir, bytecode_dir):
        _private_directory(directory)
    checkout = runtime_root / "historical-child"
    xml_path = runtime_root / "pytest-results.xml"
    stdout = ""
    stderr = ""
    exit_code = -1
    error: str | None = None
    outcomes: dict[str, str] = {}
    details: dict[str, str] = {}
    added = False

    add = _git(
        PROJECT_ROOT,
        "worktree",
        "add",
        "--detach",
        "--quiet",
        str(checkout),
        HISTORICAL_CHILD,
    )
    if add.returncode:
        error = f"git worktree add failed ({add.returncode}): {add.stderr.strip()}"
        stderr = add.stderr
    else:
        added = True
        try:
            _verify_historical_checkout(checkout)
            if sys.version_info[:2] != (3, 13):
                raise RuntimeError(f"expected Python 3.13, got {sys.version.split()[0]}")
            env = os.environ.copy()
            env.update(
                {
                    "LOTTOLAB_DATA_DIR": str(data_dir),
                    "TMPDIR": str(temp_dir),
                    "TMP": str(temp_dir),
                    "TEMP": str(temp_dir),
                    "XDG_CACHE_HOME": str(cache_dir),
                    "PYTHONPYCACHEPREFIX": str(bytecode_dir),
                    "PYTHONPATH": str(checkout / "src"),
                    HISTORICAL_CHILD_CONTEXT_ENV: "1",
                }
            )
            env.pop("PYTEST_ADDOPTS", None)
            env.pop("PYTEST_CURRENT_TEST", None)
            command = [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "--tb=short",
                "-q",
                f"--basetemp={runtime_root / 'pytest-basetemp'}",
                f"--junitxml={xml_path}",
                HISTORICAL_TEST,
            ]
            child = subprocess.run(
                command,
                cwd=checkout,
                capture_output=True,
                check=False,
                env=env,
                text=True,
            )
            exit_code, stdout, stderr = child.returncode, child.stdout, child.stderr
            if not xml_path.is_file():
                error = "historical pytest did not produce its result XML"
            else:
                outcomes, details = _historical_case_results(xml_path)
                missing = sorted(expected_names - outcomes.keys())
                if missing:
                    error = f"Candidate collected IDs missing from historical Child: {missing}"
                elif child.returncode:
                    error = f"historical pytest exited {child.returncode}"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

    if added:
        status = _git(checkout, "status", "--porcelain=v1", "--untracked-files=all")
        if status.returncode or status.stdout.strip():
            error = error or f"historical Child worktree is not clean: {status.stdout.strip()}"
        else:
            remove = _git(PROJECT_ROOT, "worktree", "remove", str(checkout))
            if remove.returncode:
                error = error or f"historical Child cleanup failed: {remove.stderr.strip()}"
            else:
                added = False

    (runtime_root / "child.stdout.txt").write_text(stdout, encoding="utf-8")
    (runtime_root / "child.stderr.txt").write_text(stderr, encoding="utf-8")
    (runtime_root / "child.exit-code.txt").write_text(f"{exit_code}\n", encoding="utf-8")
    failed = (
        error is not None
        or exit_code != 0
        or any(outcome in {"failed", "error"} for outcome in outcomes.values())
    )
    evidence_dir: str | None = str(runtime_root) if failed or added else None
    if not failed and not added:
        shutil.rmtree(runtime_root)
    return ChildRun(exit_code, outcomes, details, stdout, stderr, error, evidence_dir)


@pytest.fixture(scope="session", autouse=True)
def _run_historical_child_session(request: pytest.FixtureRequest) -> None:  # pyright: ignore[reportUnusedFunction]
    global _child_run
    if _execution_context() != "candidate-runner":
        return
    expected_names = {
        item.name
        for item in request.session.items
        if Path(str(item.path)).resolve() == Path(__file__).resolve()
        and item.name.partition("[")[0] in _HISTORICAL_TEST_NAMES
    }
    _child_run = _run_historical_child(expected_names)


@pytest.fixture(autouse=True)  # pyright: ignore[reportUnusedFunction]
def _mirror_historical_child_status() -> None:  # pyright: ignore[reportUnusedFunction]
    current = os.environ.get("PYTEST_CURRENT_TEST", "").partition(" (")[0]
    test_name = current.rsplit("::", 1)[-1]
    if (
        _execution_context() != "candidate-runner"
        or test_name.partition("[")[0] not in _HISTORICAL_TEST_NAMES
    ):
        return
    if _child_run is None:
        raise RuntimeError("historical Child pytest was not executed")
    if _child_run.error is not None or _child_run.exit_code != 0:
        raise RuntimeError(_child_report(_child_run, test_name))
    outcome = _child_run.outcomes.get(test_name)
    if outcome == "error":
        raise RuntimeError(_child_report(_child_run, test_name))
    if outcome == "skipped":
        pytest.skip(_child_report(_child_run, test_name))
    if outcome is None:
        raise RuntimeError(_child_report(_child_run, test_name))


@pytest.fixture(scope="module")
def result() -> v.Document:
    if _execution_context() == "candidate-runner":
        return cast(v.Document, {})
    value = v.compute_result()
    assert (v.ROOT / v.RESULT).read_bytes() == v.render(value)
    return value


def certificates(result: v.Document) -> dict[str, v.Document]:
    return {p: v.obj(c) for p, c in v.obj(result["ROW_CERTIFICATES"]).items()}


def test_identities_judges_and_original_dispositions(result: v.Document) -> None:
    ids = v.obj(result["IDENTITIES"])
    assert [v.obj(ids[c.role])["HEAD"] for c in v.COMMITS] == [c.head for c in v.COMMITS]
    assert v.obj(ids["BASE_69D2"])["RESULT_SHA256"] == (
        "bad130a8b2ca045ba61884c969bae7d40d9b372f9d2a460e98163998f88aead1"
    )
    assert v.obj(result["BASE_JUDGE"])["VERDICT"] == "VERIFIED_WITH_CAVEATS"
    assert v.obj(result["PROTECTED_JUDGE"])["VERDICT"] == "VERIFIED_WITH_CAVEATS"
    docs = v.inputs()
    dispositions = v.obj(result["DONOR_DISPOSITIONS"])
    for commit in v.DONORS:
        record = v.obj(dispositions[commit.role])
        assert record["FRESH_JUDGE_ACCEPTANCE_CLAIMED_BY_THIS_TASK"] == "NO"
        assert record["DISPOSITION_UPGRADED"] is False
        verbatim = v.obj(record["VERBATIM"])
        assert verbatim == {k: docs[commit.role][k] for k in verbatim}
        assert verbatim["PROJECTION_STATUS"] == "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION"
        lines = cast(list[str], record["COMMIT_MESSAGE_REVIEW_LINES"])
        assert bool(lines) == (commit.role == "STEP_1")
    assert result["HISTORICAL_R15"] == "NOT_VERIFIED"
    assert result["LEGAL_ATTAINMENT"] == result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["HEAVY_SOLVER_STARTED"] == result["REMOTE_WRITE"] == "NO"


def test_protected_judge_report_observation() -> None:
    report = v.PROTECTED_JUDGE_REPORT
    common = v.git("rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()
    path = Path(common).parent / str(report["LOCATOR"])
    if not path.is_file():
        pytest.skip("per-worktree Judge report not present on this host")
    raw = path.read_bytes()
    assert v.sha(raw) == report["SHA256_OBSERVED_AT_SEAL"]
    assert raw.decode().splitlines()[0] == "VERIFIED_WITH_CAVEATS"
    assert f"JUDGED_TREE: {v.PROTECTED.tree}" in raw.decode()


def test_incorrect_source_sha_or_tree_rejected() -> None:
    c = v.DONORS[2]
    assert v.sha(v.checked_blob(c.head, c.tree, c.source, c.source_sha)) == c.source_sha
    with pytest.raises(ValueError, match="source SHA256 mismatch"):
        v.checked_blob(c.head, c.tree, c.source, "0" * 64)
    with pytest.raises(ValueError, match="tree identity"):
        v.checked_blob(c.head, v.BASE.tree, c.source, c.source_sha)
    with pytest.raises(ValueError, match="parent identity"):
        v.commit_document(c._replace(parent=v.BASE.head))


def test_selection_is_derived_and_weaker_values_rejected(result: v.Document) -> None:
    strict = cast(list[str], result["STRICT_IMPROVEMENT_PROFILE_IDS"])
    assert result["STRICT_IMPROVEMENT_COUNT"] == len(strict) == len(set(strict)) == 11
    assert result["DIFFERING_ROWS_VS_BASE"] == 15
    rejected = [v.obj(r) for r in v.items(result["WEAKER_CANDIDATES_REJECTED"])]
    assert [r["PROFILE_ID"] for r in rejected] == WEAKER
    for row in rejected:
        assert v.integer(row["DONOR_BOUND"]) > v.integer(row["BASE_BOUND"])
        s2 = v.obj(result["RESOLVED_ROW_BOUNDS"])[cast(str, row["PROFILE_ID"])]
        assert s2 == row["BASE_BOUND"] == row["PROTECTED_BOUND"]
    base_rows, _ = v.base_ledger(v.inputs())
    advanced = dict(v.advanced_chain(v.inputs())[-1][1])
    advanced[strict[0]] = base_rows[strict[0]] + 1
    advanced[WEAKER[0]] = base_rows[WEAKER[0]]
    mutated, weaker = v.select_candidates(base_rows, advanced)
    assert strict[0] not in mutated and strict[0] in weaker and WEAKER[0] not in weaker
    assert all(advanced[p] < base_rows[p] for p in mutated)


def test_actual_sources_and_nonregression_vs_641173(result: v.Document) -> None:
    certs = certificates(result)
    assert certs[A]["ADOPTED_BOUND"] == 313195248 and certs[A]["APPLIED_T_CAP"] == 242
    assert certs[B]["ADOPTED_BOUND"] == 313186092 and certs[B]["APPLIED_T_CAP"] == 241
    assert certs[B]["DONOR_BOUND"] == 313195248 and "rejected as weaker" in str(
        certs[B]["ACTUAL_SOURCE"]
    )
    s3 = v.obj(result["S3_NONREGRESSION_COMPARISON"])
    assert s3["PASS"] is True and s3["REGRESSED_ROWS_VS_S1"] == []
    assert len(v.items(s3["STRENGTHENED_ROWS_VS_S1"])) == 9 and s3["EQUAL_ROWS_VS_S1"] == 4638
    assert s3["PROTECTED_CERTIFIED_ROWS"] == {
        A: {"S1": 313195248, "S2": 313195248},
        B: {"S1": 313186092, "S2": 313186092},
    }
    steps = {p: str(c["DONOR_STEP"]) for p, c in certs.items()}
    assert (
        sorted(steps.values()) == ["STEP_2"] * 2 + ["STEP_3"] * 3 + ["STEP_4"] * 3 + ["STEP_5"] * 3
    )


def test_relaxation_domains_recounted_against_donor_evidence(result: v.Document) -> None:
    states = v.obj(result["RELAXATION_RETAINED_STATES"])
    assert states["TOTAL"] == 6044 and len(v.obj(states["BY_PROFILE"])) == 6
    docs = v.inputs()
    for role, remainder in (("STEP_3", False), ("STEP_4", True)):
        for pid in cast(list[str], docs[role]["PROFILE_ORDER"]):
            donor = v.obj(v.obj(v.obj(docs[role]["PROFILES"])[pid])["RELAXATION"])
            mine = v.relaxation(pid, remainder)
            assert v.render(mine) == v.render(donor)
            records = cast(list[v.Document], mine.get("ALL_RETAINED_STATES", []))
            assert all(v.integer(s["UPPER"]) <= v.integer(mine["CAP"]) for s in records)
    caps = {p: c["PROFILE_RELAXATION_CAP"] for p, c in certificates(result).items()}
    assert [caps[p] for p in cast(list[str], docs["STEP_3"]["PROFILE_ORDER"])] == [250, 222, 218]
    assert [caps[p] for p in cast(list[str], docs["STEP_4"]["PROFILE_ORDER"])] == [260, 227, 259]
    # The z=6 graphical zero census and the z=5 census have their known sizes.
    assert (len(v.zero_lists(6)), len(v.zero_lists(5))) == (102, 31)


def test_analytic_step5_certificate() -> None:
    for pid in cast(list[str], v.inputs()["STEP_5"]["PROFILE_ORDER"]):
        cert = v.analytic_certificate(pid)
        assert cert["CONSTANT"] == 170 and cert["CAP"] == 262
        totals = [
            v.integer(v.obj(c)["TOTAL"])
            for c in v.obj(cert["SIGMA_ENDPOINT_CONTRIBUTIONS"]).values()
        ]
        assert sum(totals) == 92
        assert v.analytic_box_maximum(pid) <= 262
        for d, upper in ((6, 0), (5, 1), (4, 2), (3, 3), (2, 4), (1, 5)):
            assert max(s * (4 - d + s) for s in range(upper + 1)) == [0, 0, 4, 12, 24, 40][6 - d]


def test_local_weights_and_bonferroni_closed_forms() -> None:
    w = v.local_weights()
    one = 7 * sum(comb(6, j) * comb(43, 7 - j) for j in range(3, 7))
    assert w["S1"] == 20 * one == 372228640
    assert (w["K4_PAIR"], w["K4_WITH_TRIPLE"], w["SPARSE_TRIPLES"]) == (679, 448, [0, 0])
    assert all(
        q - comb(q, 2) + comb(q, 3) - Fraction(4 * comb(q, 4), 7) >= (q > 0) for q in range(8)
    )
    assert 8 - comb(8, 2) + comb(8, 3) - Fraction(4 * comb(8, 4), 7) < 1


def test_every_load_bearing_envelope_and_rounding(result: v.Document) -> None:
    total = 0
    for pid, cert in certificates(result).items():
        cap = v.integer(cert["APPLIED_T_CAP"])
        terms = v.envelope(pid, cap, {})
        v.validate_terms(pid, cap, {}, cert["NEW_TERMS"])
        assert v.as_lists(terms) == cert["NEW_TERMS"]
        assert cert["FULL_PROFILE_BOUND"] == max(t[1] for t in terms)
        adopted = v.integer(cert["ADOPTED_BOUND"])
        assert adopted <= v.integer(cert["PROTECTED_BOUND"])
        assert adopted < v.integer(cert["BASE_BOUND"])
        for t, bound, _, _, s4, s3 in terms:
            exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
            assert bound == ceil(exact) and 22 <= t <= cap
        total += len(terms)
    assert total == result["LOAD_BEARING_NEW_TERM_COUNT"] == 2534


def test_t264_only_floors_and_universal_cap_separation(result: v.Document) -> None:
    certs = certificates(result)
    for pid, floor in T264_PROFILES.items():
        old = v.obj(certs[pid]["OLD"])
        assert old["OLD_UNIVERSAL_T_CAP"] == 264
        assert old["OLD_T264_ONLY_S4_FLOORS"] == {"264": floor}
        assert old["OLD_EFFECTIVE_ARGMAX_T_COMPARISON_ONLY"] == [263]
        assert old["EFFECTIVE_ARGMAX_IS_A_UNIVERSAL_CAP"] is False
        assert v.obj(certs[pid]["VALID_S4_SCOPE"])["NEW_T_SPECIFIC_FLOORS"] == {}
        old_terms = cast(list[list[int]], old["OLD_TERMS"])
        assert [t[4] for t in old_terms if t[4] == floor] == [floor] and old_terms[-1][0] == 264
        assert all(t[4] != floor for t in cast(list[list[int]], certs[pid]["NEW_TERMS"]))
    assert v.obj(certs["66665555555421000000"]["OLD"])["OLD_FULL_PROFILE_BOUND"] == 313392308
    assert certs["66665555555421000000"]["DONOR_OLD_EFFECTIVE_CAP_COMPARISON_ONLY"] == 263


def test_negative_cap_swap_scope_leakage_and_rounding(result: v.Document) -> None:
    certs = certificates(result)
    pid = "66665555555421000000"
    sealed = certs[pid]["NEW_TERMS"]
    with pytest.raises(ValueError, match="universal/effective cap swap"):
        v.validate_old_cap(pid, 263)
    v.validate_old_cap(pid, 264)
    with pytest.raises(ValueError, match="incomplete T terms"):
        v.validate_terms(pid, 259, {}, sealed)
    other = "66666555554411100000"
    with pytest.raises(ValueError, match="incomplete T terms"):
        v.validate_terms(other, 250, {}, sealed)
    for special in ({264: 308560}, {250: 308560}, {249: 112}):
        with pytest.raises(ValueError, match="S4 floor scope leakage"):
            v.validate_terms(pid, 250, special, sealed)
    with pytest.raises(ValueError, match="S4 floor scope leakage"):
        v.validate_s4_scope(other, 264, {264: 308560})
    assert v.envelope(pid, 250, {250: 308560}) != v.envelope(pid, 250, {})
    off_by_one = deepcopy(cast(list[list[int]], sealed))
    off_by_one[-1][1] -= 1
    with pytest.raises(ValueError, match="incomplete T terms"):
        v.validate_terms(pid, 250, {}, off_by_one)
    with pytest.raises(ValueError, match="incomplete T terms"):
        v.validate_terms(pid, 250, {}, cast(list[list[int]], sealed)[:-1])


def test_negative_wrong_profile() -> None:
    with pytest.raises(ValueError, match="certificate degree profile mismatch"):
        v.validate_facts("66665555555421000000", v.facts("66665555555331000000"))
    with pytest.raises(ValueError, match="wrong exact degree profile"):
        v.degrees("56665555555421000000")
    claimed = dict(v.facts("65555555555531100000"))
    claimed["W"] = 825
    with pytest.raises(ValueError, match="certificate degree facts mismatch"):
        v.validate_facts("65555555555531100000", claimed)


def test_negative_ledger_mutations(result: v.Document) -> None:
    base_rows, cursor = v.base_ledger(v.inputs())
    certified = {p: v.integer(c["ADOPTED_BOUND"]) for p, c in certificates(result).items()}
    rows, updates = sorted(base_rows.items()), sorted(certified.items())
    assert v.apply_adoption(rows, cursor, updates, certified) == v.ledger(
        result["RESOLVED_ROW_BOUNDS"]
    )
    with pytest.raises(ValueError, match="duplicate or missing ledger row"):
        v.apply_adoption([*rows, rows[0]], cursor, updates, certified)
    with pytest.raises(ValueError, match="duplicate or missing ledger row"):
        v.apply_adoption(rows[1:], cursor, updates, certified)
    mutated = deepcopy(cursor)
    projection = v.obj(mutated["COARSE_BOUND_PROJECTION"])
    projection[next(iter(projection))] = 1
    with pytest.raises(ValueError, match="cursor mutation"):
        v.apply_adoption(rows, mutated, updates, certified)
    with pytest.raises(ValueError, match="duplicate row update"):
        v.apply_adoption(rows, cursor, [*updates, updates[0]], certified)
    with pytest.raises(ValueError, match="wrong or missing adopted profile"):
        v.apply_adoption(rows, cursor, updates[1:], certified)
    with pytest.raises(ValueError, match="wrong or missing adopted profile"):
        v.apply_adoption(rows, cursor, [*updates, (WEAKER[0], 313186584)], certified)
    weaker = [(p, b + 9156 if p == B else b) for p, b in updates]
    with pytest.raises(ValueError, match="differs from the certified bound"):
        v.apply_adoption(rows, cursor, weaker, certified)
    with pytest.raises(ValueError, match="weaker donor value"):
        v.apply_adoption(rows, cursor, [(WEAKER[0], 313186584)], {WEAKER[0]: 313186584})


def test_family_replay(result: v.Document) -> None:
    s0, s1, s2 = (v.obj(result[k]) for k in ("S0_69D2", "S1_641173", "S2_69D2_PLUS_STRONGER_ROWS"))
    assert (s0["FAMILY_BOUND"], s1["FAMILY_BOUND"], s2["FAMILY_BOUND"]) == (
        313392412,
        313392308,
        313391784,
    )
    assert s2["OWNER_COUNT"] == s2["OWNER_CURSOR_COUNT"] == 39 and s2["OWNER_W"] == [784]
    assert s2["RESOLVED_MAXIMUM"] == 313391740 and s2["GAP_TO_INCUMBENT"] == 127896
    assert (result["FAMILY_DELTA_VS_69D2"], result["FAMILY_DELTA_VS_641173"]) == (628, 524)
    assert (result["ROWS_UPDATED"], result["OTHER_ROWS_UNCHANGED"]) == (11, 4636)
    base_rows, cursor = v.base_ledger(v.inputs())
    assert result["CURSOR"] == cursor and result["CURSOR_BOUNDS_CHANGED"] == 0
    assert result["CURSOR_PROFILES"] == 197
    after = v.ledger(result["RESOLVED_ROW_BOUNDS"])
    changed = sorted(p for p in after if after[p] != base_rows[p])
    assert changed == result["STRICT_IMPROVEMENT_PROFILE_IDS"]
    owners = cast(list[str], s2["OWNER_IDS"])
    assert set(owners) <= set(cast(list[str], cursor["PROFILE_IDS"]))
    bounds = v.ledger(cursor["COARSE_BOUND_PROJECTION"])
    opened = sum(b > v.INCUMBENT for b in (*after.values(), *bounds.values()))
    assert s2["STILL_OPEN_PROFILE_COUNT"] == opened


# ------------------------------------------------- realizations of retained states


def realize(pid: str, state: v.Document) -> list[set[int]]:
    """A simple graph with the profile's degrees and the state's crossing degrees."""

    d = v.degrees(pid)
    k = sum(x > 0 for x in d)
    sigma = [
        s
        for _, part in cast(list[list[object]], state["SIGMA_BY_D"])
        for s in cast(list[int], part)
    ]
    zeta = cast(list[int], state["ZETA"])
    adj = [set[int]() for _ in d]

    def connect(a: int, b: int) -> None:
        assert a != b and b not in adj[a]
        adj[a].add(b)
        adj[b].add(a)

    left = dict(enumerate(sigma))
    right = {k + i: z for i, z in enumerate(zeta)}
    while any(left.values()):
        x = max(left, key=lambda i: (left[i], -i))
        for u in sorted(right, key=lambda j: (-right[j], j))[: left[x]]:
            assert right[u] > 0
            connect(x, u)
            right[u] -= 1
        left[x] = 0
    for shore, need in (
        (range(k), [6 + d[x] - sigma[x] for x in range(k)]),
        (range(k, 20), [6 - z for z in zeta]),
    ):
        remaining = dict(zip(shore, need, strict=True))
        while any(remaining.values()):
            x = max(remaining, key=lambda i: (remaining[i], -i))
            take, remaining[x] = remaining[x], 0
            for y in sorted(
                (j for j in remaining if remaining[j]), key=lambda j: (-remaining[j], j)
            )[:take]:
                connect(x, y)
                remaining[y] -= 1
    assert [len(a) for a in adj] == [6 + x for x in d]
    return adj


def triangles(adj: list[set[int]], vertices: list[int]) -> int:
    return sum(b in adj[a] and c in adj[a] and c in adj[b] for a, b, c in combinations(vertices, 3))


def swap(adj: list[set[int]], d: tuple[int, ...], rng: random.Random) -> None:
    edges = [(a, b) for a in range(20) for b in adj[a] if a < b]
    (a, b), (c, e) = rng.sample(edges, 2)
    if rng.random() < 0.5:
        c, e = e, c
    if len({a, b, c, e}) < 4 or c in adj[a] or e in adj[b]:
        return
    trial = [set(x) for x in adj]
    for x, y in ((a, b), (c, e)):
        trial[x].discard(y)
        trial[y].discard(x)
    for x, y in ((a, c), (b, e)):
        trial[x].add(y)
        trial[y].add(x)
    k = sum(x > 0 for x in d)
    if all(len(trial[x] & set(range(k, 20))) <= min(20 - k, 6 - d[x]) for x in range(k)):
        adj[:] = trial


@pytest.mark.parametrize("role", ["STEP_3", "STEP_4"])
def test_split_identity_bounds_and_coverage_on_realizations(role: str) -> None:
    rng = random.Random(649)
    for pid in cast(list[str], v.inputs()[role]["PROFILE_ORDER"]):
        d = v.degrees(pid)
        f = v.facts(pid)
        k, z = v.integer(f["K"]), v.integer(f["Z"])
        domain = v.relaxation(pid, True)
        retained = {
            (str(s["SIGMA_BY_D"]), str(s["ZETA"])): v.integer(s["UPPER"])
            for s in cast(list[v.Document], domain["ALL_RETAINED_STATES"])
        }
        seeds = cast(list[v.Document], domain["ALL_RETAINED_STATES"])
        for seed in (*cast(list[v.Document], domain["ALL_ARGMAX"]), *rng.sample(seeds, 2)):
            adj = realize(pid, seed)
            for _ in range(25):
                swap(adj, d, rng)
                core, zero = list(range(k)), list(range(k, 20))
                sigma = [len(adj[x] & set(zero)) for x in core]
                zeta = [len(adj[u] & set(core)) for u in zero]
                parts: list[list[object]] = []
                start = 0
                for x, n, _ in v.classes(pid):
                    parts.append([x, sorted(sigma[start : start + n])])
                    start += n
                key = (str(parts), str(sorted(zeta)))
                assert key in retained
                h = [set(range(20)) - adj[i] - {i} for i in range(20)]
                m = [len(h[x] & set(core)) for x in core]
                nn = [len(h[u] & set(zero)) for u in zero]
                t_g, t_h = triangles(adj, list(range(20))), triangles(h, list(range(20)))
                assert t_g + t_h == f["GOODMAN"]
                c_z = sum(
                    len(adj[x] & adj[y] & set(zero)) for x, y in combinations(core, 2) if y in h[x]
                )
                c_k = sum(
                    len(adj[u] & adj[w] & set(core)) for u, w in combinations(zero, 2) if w in h[u]
                )
                t_m, t_n = triangles(h, core), triangles(h, zero)
                r = sum(sigma)
                raw = (
                    v.integer(f["GOODMAN"])
                    - 3 * z * (k - 11)
                    - 10 * r
                    + sum(s * a for s, a in zip(sigma, m, strict=True))
                    + sum(q * a for q, a in zip(zeta, nn, strict=True))
                )
                assert t_g == raw - (t_m + t_n + c_z + c_k)
                assert (
                    t_m >= v.triangle_floors(tuple(m))[1] and t_n >= v.triangle_floors(tuple(nn))[1]
                )
                assert c_k >= sum(v.induced_edge_floor(nn, s) for s in sigma)
                assert c_z >= sum(v.induced_edge_floor(m, q) for q in zeta)
                assert t_g <= retained[key] <= v.integer(domain["CAP"])


def test_remainder_lower_bounds_on_random_graphs() -> None:
    rng = random.Random(784)
    for _ in range(300):
        n = rng.randint(4, 15)
        p = rng.random()
        adj = [set[int]() for _ in range(n)]
        for a, b in combinations(range(n), 2):
            if rng.random() < p:
                adj[a].add(b)
                adj[b].add(a)
        degrees = tuple(len(x) for x in adj)
        square, best = v.triangle_floors(degrees)
        assert square <= best <= triangles(adj, list(range(n)))
        subset = rng.sample(range(n), rng.randint(0, n))
        inside = sum(b in adj[a] for a, b in combinations(subset, 2))
        assert inside >= v.induced_edge_floor(list(degrees), len(subset))


def _mirror_historical_test(function: Callable[..., object]) -> Callable[..., object]:
    @wraps(function)
    def wrapped(*args: object, **kwargs: object) -> object:
        if _execution_context() != "candidate-runner":
            return function(*args, **kwargs)
        if _child_run is None:
            raise AssertionError("historical Child pytest was not executed")
        current = os.environ.get("PYTEST_CURRENT_TEST", "").partition(" (")[0]
        test_name = current.rsplit("::", 1)[-1]
        _assert_child_passed(_child_run, test_name)
        return None

    return wrapped


for _test_name, _test_function in tuple(globals().items()):
    if _test_name.startswith("test_") and callable(_test_function):
        _HISTORICAL_TEST_NAMES.add(_test_name)
        globals()[_test_name] = _mirror_historical_test(_test_function)


def test_candidate_is_not_accepted_as_historical_child() -> None:
    assert _child_run is not None
    assert _child_run.exit_code == 0
    assert len(_child_run.outcomes) == 17
    assert all(outcome == "passed" for outcome in _child_run.outcomes.values())
    assert _execution_context() == "candidate-runner"
    with pytest.raises(RuntimeError, match="wrong historical Child identity"):
        _verify_historical_child_identity(
            HISTORICAL_CHILD,
            HISTORICAL_CHILD_TREE,
            [HISTORICAL_CHILD, CANDIDATE_BASE],
        )
    with pytest.raises(RuntimeError, match="wrong historical Child identity"):
        _verify_historical_checkout(PROJECT_ROOT)
    with pytest.raises(ValueError, match="candidate is not Base or its single local child"):
        v.verify_candidate()
    donor = v.DONORS[2]
    with pytest.raises(ValueError, match="source SHA256 mismatch"):
        v.commit_document(donor._replace(result_sha="0" * 64))


def test_nonzero_child_result_preserves_failure_and_stderr() -> None:
    failed = ChildRun(
        exit_code=17,
        outcomes={"test_sentinel": "failed"},
        details={"test_sentinel": "sentinel assertion failed"},
        stdout="sentinel stdout",
        stderr="sentinel stderr",
        error=None,
        evidence_dir="/task-owned-temp/historical-child",
    )
    with pytest.raises(AssertionError, match="child_exit_code=17") as exc_info:
        _assert_child_passed(failed, "test_sentinel")
    assert "sentinel stderr" in str(exc_info.value)

    nonzero_with_passed_case = ChildRun(
        exit_code=23,
        outcomes={"test_sentinel": "passed"},
        details={},
        stdout="sentinel stdout",
        stderr="sentinel stderr",
        error=None,
        evidence_dir="/task-owned-temp/historical-child",
    )
    with pytest.raises(AssertionError, match="child_exit_code=23"):
        _assert_child_passed(nonzero_with_passed_case, "test_sentinel")
