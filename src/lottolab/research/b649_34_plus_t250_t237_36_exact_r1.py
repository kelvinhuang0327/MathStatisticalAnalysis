"""Build and replay the exact 36-event continuation of the pinned 34-event B649 ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import Any, cast

from . import b649_w832_z6_t256_32_event_from31_r2 as base_r2

TASK_ID = "B649_34_PLUS_T250_T237_36_EXACT_R1"
ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = "src/lottolab/research/b649_34_plus_t250_t237_36_exact_r1.py"
TEST_PATH = "tests/unit/test_b649_34_plus_t250_t237_36_exact_r1.py"
RESULT_PATH = "docs/research/matrix-native-results/b649-34-plus-t250-t237-36-exact-r1-result.json"
COMMITTED_PATHS = tuple(sorted((SOURCE_PATH, TEST_PATH, RESULT_PATH)))
BASE_HEAD = "3506bb31fd55ac46df2d3c9b7337c3a8e9ea8059"
BASE_TREE = "8517cbdbd95af4aa213d464eecb28284842d8556"
BASE_PARENT_HEAD = "3cece5b6d5ac61bb0637adc8d755d2af7a760cbb"
BASE_PARENT_TREE = "d93a6c833db8e1461d2693505d3dfc34c8832363"
BASE_RESULT_PATH = "docs/research/matrix-native-results/b649-w832-32r2-dual-34-exact-r1-result.json"
BASE_RESULT_SHA256 = "bb38f7dd6c97aaad5be22a5eef193064a72686d41c1a7bd4e306c3c51432f04c"
BASE_SOURCE_PATH = "src/lottolab/research/b649_w832_32r2_dual_34_exact_r1.py"
BASE_SOURCE_SHA256 = "67a1beb2282c1cc54772d3f1da898ae94742ff7ffe4939e951327a326fe782ea"
BASE_TEST_PATH = "tests/unit/test_b649_w832_32r2_dual_34_exact_r1.py"
BASE_TEST_SHA256 = "177d3d04fa9673d7d64b5b45db499b62ce30f051ec2fca4498a5b7e8a824d74f"
BASE_FULL_DIGEST = "991075890542833637382bc46f5afc0da3e39c3106bcb8d16f3a3effb5fb86ca"
BASE_BOUNDS_DIGEST = "850eda553999f1dd0a92ff14df01c4ba3ee33e0d37a823c11dff1092918bd872"
PARENT_COMMITTED_PATHS = tuple(sorted((BASE_SOURCE_PATH, BASE_TEST_PATH, BASE_RESULT_PATH)))
R2_HEAD = "3cece5b6d5ac61bb0637adc8d755d2af7a760cbb"
R2_TREE = "d93a6c833db8e1461d2693505d3dfc34c8832363"
R2_PARENT_HEAD = "88a37370e6db035d6155190723de8cea646e76b7"
R2_RESULT_SHA256 = "ba226e0a1808468f6ad1f58bb3bc411109276896cbe81cbc5b719b61a72715a3"
R2_SOURCE_SHA256 = "7d71ccf1263f84a97fdfe484e83f8fe46ca146138e86c8960c764fe0e1797975"
R2_TEST_SHA256 = "262537133d430b20b2d5dfc4b9eb7a97d93797ae2be551c0cc1041d4f5fa8095"
R2_FULL_DIGEST = "5667e54776b5fade56831c76228bf65fd926aed9d66048b459450eb31ec4de7f"
R2_BOUNDS_DIGEST = "3b8ee21e9c6d96712bf7310434b0de3158f665ca54cee2d53f0841b62e3e6d67"
R2_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-w832-z6-t256-32-event-from31-r2-result.json"
)
R2_SOURCE_PATH = "src/lottolab/research/b649_w832_z6_t256_32_event_from31_r2.py"
R2_TEST_PATH = "tests/unit/test_b649_w832_z6_t256_32_event_from31_r2.py"
COMMON_BASE_HEAD = "88a37370e6db035d6155190723de8cea646e76b7"
COMMON_BASE_TREE = "4fede8e927eab43d58b906ce80e7eea10300b4a0"
COMMON_BASE_RESULT_SHA256 = "802cb12eb1b737450c707d55386382e90689a3ff1574b84aa0a7365bb975497d"
COMMON_BASE_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-triple-t262-31-event-family-integration-r1-result.json"
)
T250_COMMIT = "2f95ab23f2e29d7119ce02b6e8b4fafd566d707a"
T250_TREE = "b2de0849e9010d08a3766126ff19257d76e6747d"
T250_PARENT = COMMON_BASE_HEAD
T250_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-next-owner-t250-32-event-from31-r1-result.json"
)
T250_RESULT_SHA256 = "b46bc2d5dd5575c9f82365ee39134bdf55c55d8a8c92a7861f92d2eb61b0f419"
T250_EVENT_ID = "T250_66665555555321100000"
T250_PROFILE_ID = "66665555555321100000"
EXPECTED_ROWS = 4_647
EXPECTED_EVENTS_BEFORE = 34
EXPECTED_EVENTS_MIDDLE = 35
EXPECTED_EVENTS_AFTER = 36
EXPECTED_CLASS_COUNT = 197
EXPECTED_CLASS_BOUND = 313_258_872
EXPECTED_CLASS_ID_SET_SHA256 = "1fd8ef4779e3967b75cbeaa2ca65de9afc2551d27ae7e98daa1e3f700fc24e8b"
EXPECTED_FAMILY_34 = 313_391_636
EXPECTED_FAMILY_35 = 313_391_560
EXPECTED_FAMILY_36 = 313_391_172
EXPECTED_GAIN_34_TO_35 = 76
EXPECTED_GAIN_35_TO_36 = 388
EXPECTED_GAIN_34_TO_36 = 464
EXPECTED_GAIN_31_TO_36 = 568
EXPECTED_MAX_OWNER = "65555555555511111000"
EXPECTED_NEXT_DISTINCT_BOUND = 313_390_396
EXPECTED_NEXT_DISTINCT_OWNER = "55555555555443000000"
EXPECTED_BOUNDS_DIGEST = "2f22be18f8555ad413d786adfe019aeeeb60084b392d584f12e1c50b8f598649"
MATH_PROVENANCE_STATUS = "INHERITED_REPORT_ONLY"
BANNED_LINEAGE = re.compile(
    r"(?:\b(?:37|38|39|40)[-_ ]*event\b|\bB649[_-][A-Z0-9_-]*(?:37|38|39|40)[_-]EVENT\b)",
    re.IGNORECASE,
)
Row = base_r2.Row


@dataclass(frozen=True)
class ProfileSpec:
    event_id: str
    profile_id: str
    old_cap: int
    new_cap: int
    old_bound: int
    new_bound: int
    s4_base: int
    source_before: str | None
    source_after: str
    distribution: dict[str, int]
    w: int
    u: int
    g_max: int
    a_max: int
    sum_squares: int
    argmax_term: tuple[int, ...]
    science_task_id: str
    science_verdict: str
    proof_scope: str
    evidence_kind: str
    session_id: str
    session_name: str
    session_uuid: str
    cap_attainment: str
    route_b_old_terms: int
    route_b_new_terms: int
    route_b_term_mismatch: int


PROFILE_T250 = ProfileSpec(
    event_id=T250_EVENT_ID,
    profile_id=T250_PROFILE_ID,
    old_cap=264,
    new_cap=250,
    old_bound=313_391_636,
    new_bound=313_266_168,
    s4_base=112,
    source_before="b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[874]",
    source_after=(
        "OWNER_TRANSCRIPT_ONLY|TASK_ID=B649_NEXT_OWNER_666655555553211_T250_FRESH_MATH_JUDGE_R1"
        "|SESSION_ID=01a152c5-acb6-7553-ab32-95d042abd243|VERDICT=VERIFIED_WITH_CAVEATS"
        "|PROOF_SCOPE=FULL_PROFILE|EXACT_MAX_T=250|NEW_BOUND=313266168|ROUTE_B_TERMS=472|TERM_MISMATCH=0"
    ),
    distribution={"6": 4, "5": 7, "3": 1, "2": 1, "1": 2, "0": 5},
    w=830,
    u=2345,
    g_max=12,
    a_max=199,
    sum_squares=334,
    argmax_term=(250, 313_266_168, 387, 199, 216_804, 5_000_016),
    science_task_id="B649_NEXT_OWNER_666655555553211_T250_FRESH_MATH_JUDGE_R1",
    science_verdict="VERIFIED_WITH_CAVEATS",
    proof_scope="FULL_PROFILE",
    evidence_kind="TRANSCRIPT_ONLY",
    session_id="01a152c5-acb6-7553-ab32-95d042abd243",
    session_name="UNKNOWN",
    session_uuid="01a152c5-acb6-7553-ab32-95d042abd243",
    cap_attainment="EXACT_MAX_T_250_REPORTED",
    route_b_old_terms=243,
    route_b_new_terms=229,
    route_b_term_mismatch=0,
)
PROFILE_T237 = ProfileSpec(
    event_id="T237_65555555555432100000",
    profile_id="65555555555432100000",
    old_cap=267,
    new_cap=237,
    old_bound=313_391_560,
    new_bound=313_122_700,
    s4_base=112,
    source_before=None,
    source_after=(
        "OWNER_TRANSCRIPT_ONLY|TASK_ID=B649_NEXT_DISTINCT_OWNER_655555555554321_T237_FRESH_MATH_JUDGE_R1"
        "|SESSION_NAME=/root/t237_fresh_judge|SESSION_UUID=UNKNOWN|VERDICT=VERIFIED_WITH_CAVEATS"
        "|PROOF_SCOPE=FULL_PROFILE|EVIDENCE_KIND=TRANSCRIPT_ONLY|CAP_ATTAINMENT=NOT_PROVEN"
        "|ROUTE_B_OLD_TERMS=246|ROUTE_B_NEW_TERMS=216|TERM_MISMATCH=0"
    ),
    distribution={"6": 1, "5": 10, "4": 1, "3": 1, "2": 1, "1": 1, "0": 5},
    w=821,
    u=2265,
    g_max=12,
    a_max=193,
    sum_squares=316,
    argmax_term=(237, 313_122_700, 292, 193, 153_685, 4_820_480),
    science_task_id="B649_NEXT_DISTINCT_OWNER_655555555554321_T237_FRESH_MATH_JUDGE_R1",
    science_verdict="VERIFIED_WITH_CAVEATS",
    proof_scope="FULL_PROFILE",
    evidence_kind="TRANSCRIPT_ONLY",
    session_id="UNKNOWN",
    session_name="/root/t237_fresh_judge",
    session_uuid="UNKNOWN",
    cap_attainment="NOT_PROVEN",
    route_b_old_terms=246,
    route_b_new_terms=216,
    route_b_term_mismatch=0,
)
PROFILE_SPECS = (PROFILE_T250, PROFILE_T237)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run_git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True).stdout


def git_text(*args: str) -> str:
    return run_git(*args).decode("utf-8").strip()


def json_object(raw: bytes, message: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(message) from exc
    require(type(value) is dict, message)
    return cast(dict[str, Any], value)


def serialize_result(result: Mapping[str, Any]) -> bytes:
    return (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def validate_base_identity(head: str, tree: str, result_sha256: str) -> None:
    require((head, tree) == (BASE_HEAD, BASE_TREE), "BASE_HEAD_TREE_MISMATCH")
    require(result_sha256 == BASE_RESULT_SHA256, "BASE_RESULT_SHA256_MISMATCH")


def validate_parent_identity(head: str, tree: str, result_sha256: str) -> None:
    require((head, tree) == (BASE_HEAD, BASE_TREE), "PARENT_HEAD_TREE_MISMATCH")
    require(result_sha256 == BASE_RESULT_SHA256, "PARENT_RESULT_SHA256_MISMATCH")


def validate_candidate_parent(head: str, parents: Sequence[str]) -> None:
    require(list(parents) == [head, BASE_HEAD], "CANDIDATE_MUST_BE_DIRECT_CHILD_OF_PINNED_BASE")


def validate_committed_paths(paths: Sequence[str]) -> None:
    require(list(paths) == list(COMMITTED_PATHS), "COMMITTED_PATH_SET_MISMATCH")


def committed_tree_entries(head: str, paths: Sequence[str]) -> list[tuple[list[str], str]]:
    lines = run_git("ls-tree", head, "--", *paths).decode("utf-8").splitlines()
    parsed: list[tuple[list[str], str]] = []
    for line in lines:
        if "\t" in line:
            metadata, path = line.split("\t", maxsplit=1)
            parsed.append((metadata.split(), path))
    return parsed


def validate_candidate_tree_entries(
    parsed: Sequence[tuple[Sequence[str], str]], paths: Sequence[str]
) -> None:
    require(
        len(parsed) == len(paths)
        and {path for _metadata, path in parsed} == set(paths)
        and all(list(metadata[:2]) == ["100644", "blob"] for metadata, _path in parsed),
        "COMMITTED_TREE_ENTRIES_MISMATCH",
    )


def verify_candidate_ancestry() -> str:
    head = git_text("rev-parse", "HEAD")
    if head == BASE_HEAD:
        require(git_text("rev-parse", "HEAD^{tree}") == BASE_TREE, "BASE_TREE_MISMATCH")
        return head
    parents = git_text("rev-list", "--parents", "-n", "1", head).split()
    validate_candidate_parent(head, parents)
    paths = (
        run_git("diff-tree", "--no-commit-id", "--name-only", "-r", head)
        .decode("utf-8")
        .splitlines()
    )
    validate_committed_paths(paths)
    validate_candidate_tree_entries(committed_tree_entries(head, paths), paths)
    dirty = set(validate_worktree_scope()).intersection(paths)
    for path in paths:
        require(
            (ROOT / path).read_bytes() == run_git("show", f"{head}:{path}") or path in dirty,
            f"COMMITTED_CANDIDATE_BYTES_MISMATCH:{path}",
        )
    return head


def validate_worktree_scope(status_output: str | None = None) -> list[str]:
    output = (
        run_git("status", "--porcelain=v1", "--untracked-files=all").decode("utf-8").rstrip("\n")
        if status_output is None
        else status_output.rstrip("\n")
    )
    allowed = set(COMMITTED_PATHS)
    observed: list[str] = []
    for line in output.splitlines():
        require(len(line) >= 4, "WORKTREE_STATUS_LINE_INVALID")
        path = line[3:]
        require(path in allowed, f"OUT_OF_SCOPE_WORKTREE_PATH:{path}")
        observed.append(path)
    return sorted(observed)


def verify_source_closure(module_files: Mapping[str, str] | None = None) -> int:
    """Allow only fixed-parent committed LottoLab modules plus this candidate."""
    loaded = (
        tuple(
            (name, getattr(module, "__file__", None), module)
            for name, module in tuple(sys.modules.items())
        )
        if module_files is None
        else tuple((name, path, None) for name, path in module_files.items())
    )
    root = ROOT.resolve()
    own_source = (ROOT / SOURCE_PATH).resolve()
    count = 0
    for name, file_name, module in loaded:
        if name != "lottolab" and not name.startswith("lottolab."):
            continue
        if file_name is None:
            namespace = getattr(module, "__path__", None)
            expected = root / "src/lottolab/research"
            paths = (
                tuple(Path(path).resolve() for path in namespace) if namespace is not None else ()
            )
            require(
                name == "lottolab.research" and paths == (expected,),
                f"SOURCE_CLOSURE_NAMESPACE_PATH_MISMATCH:{name}",
            )
            continue
        require(type(file_name) is str, f"SOURCE_CLOSURE_MODULE_FILE_MISSING:{name}")
        path = Path(cast(str, file_name)).resolve()
        if path == own_source:
            require(path.is_file(), "CANDIDATE_SOURCE_MISSING")
            continue
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"SOURCE_CLOSURE_MODULE_OUTSIDE_WORKTREE:{name}") from exc
        require(relative.endswith(".py"), f"SOURCE_CLOSURE_MODULE_NOT_PYTHON:{relative}")
        try:
            committed = run_git("show", f"{BASE_HEAD}:{relative}")
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"UNCOMMITTED_IMPORT_MODULE:{relative}") from exc
        require(
            path.is_file() and path.read_bytes() == committed,
            f"BASE_MODULE_BYTES_MISMATCH:{relative}",
        )
        count += 1
    require(
        Path(base_r2.__file__).resolve() == root / R2_SOURCE_PATH, "R2_MODULE_IMPORT_PATH_MISMATCH"
    )
    return count


def validate_parent_commit_identity() -> tuple[
    dict[str, Any], bytes, list[dict[str, Any]], dict[str, Any]
]:
    require(git_text("rev-parse", BASE_HEAD) == BASE_HEAD, "PARENT_HEAD_UNAVAILABLE")
    require(git_text("rev-parse", f"{BASE_HEAD}^{{tree}}") == BASE_TREE, "PARENT_TREE_MISMATCH")
    parent_line = git_text("rev-list", "--parents", "-n", "1", BASE_HEAD).split()
    require(parent_line == [BASE_HEAD, BASE_PARENT_HEAD], "PARENT_PARENT_IDENTITY_MISMATCH")
    require(
        git_text("rev-parse", f"{BASE_PARENT_HEAD}^{{tree}}") == BASE_PARENT_TREE,
        "PARENT_PARENT_TREE_MISMATCH",
    )
    paths = (
        run_git("diff-tree", "--no-commit-id", "--name-only", "-r", BASE_HEAD)
        .decode("utf-8")
        .splitlines()
    )
    require(paths == list(PARENT_COMMITTED_PATHS), "PARENT_COMMITTED_PATH_SET_MISMATCH")
    validate_candidate_tree_entries(committed_tree_entries(BASE_HEAD, paths), paths)
    for path in PARENT_COMMITTED_PATHS:
        require(
            (ROOT / path).read_bytes() == run_git("show", f"{BASE_HEAD}:{path}"),
            f"PARENT_BLOB_BYTES_MISMATCH:{path}",
        )
    source_sha = sha256(run_git("show", f"{BASE_HEAD}:{BASE_SOURCE_PATH}"))
    test_sha = sha256(run_git("show", f"{BASE_HEAD}:{BASE_TEST_PATH}"))
    raw = run_git("show", f"{BASE_HEAD}:{BASE_RESULT_PATH}")
    validate_parent_identity(BASE_HEAD, BASE_TREE, sha256(raw))
    require(source_sha == BASE_SOURCE_SHA256, "PARENT_SOURCE_SHA256_MISMATCH")
    require(test_sha == BASE_TEST_SHA256, "PARENT_TEST_SHA256_MISMATCH")
    result = json_object(raw, "PARENT_RESULT_INVALID_JSON")
    require(
        result.get("TASK_ID") == "B649_W832_32R2_DUAL_EVENT_34_EXACT_R1"
        and result.get("SOURCE_SHA256") == BASE_SOURCE_SHA256
        and result.get("TEST_SHA256") == BASE_TEST_SHA256
        and result.get("ROWS_AFTER") == EXPECTED_ROWS
        and result.get("EVENTS_AFTER") == EXPECTED_EVENTS_BEFORE
        and result.get("FULL_DIGEST") == BASE_FULL_DIGEST
        and result.get("BOUNDS_DIGEST") == BASE_BOUNDS_DIGEST,
        "PARENT_RESULT_IDENTITY_OR_TOTALS_MISMATCH",
    )
    r2_base = cast(dict[str, Any], result.get("BASE"))
    require(
        r2_base.get("HEAD") == R2_HEAD
        and r2_base.get("TREE") == R2_TREE
        and r2_base.get("PARENT") == R2_PARENT_HEAD
        and r2_base.get("PARENT_TREE") == COMMON_BASE_TREE
        and r2_base.get("RESULT_PATH") == R2_RESULT_PATH
        and r2_base.get("RESULT_SHA256") == R2_RESULT_SHA256
        and r2_base.get("SOURCE_PATH") == R2_SOURCE_PATH
        and r2_base.get("SOURCE_SHA256") == R2_SOURCE_SHA256
        and r2_base.get("TEST_PATH") == R2_TEST_PATH
        and r2_base.get("TEST_SHA256") == R2_TEST_SHA256
        and r2_base.get("ROWS") == EXPECTED_ROWS
        and r2_base.get("EVENTS") == 32
        and r2_base.get("FULL_DIGEST") == R2_FULL_DIGEST
        and r2_base.get("BOUNDS_DIGEST") == R2_BOUNDS_DIGEST,
        "PARENT_R2_BASE_IDENTITY_MISMATCH",
    )
    r2_raw = run_git("show", f"{R2_HEAD}:{R2_RESULT_PATH}")
    require(sha256(r2_raw) == R2_RESULT_SHA256, "R2_RESULT_SHA256_MISMATCH")
    require(
        sha256(run_git("show", f"{R2_HEAD}:{R2_SOURCE_PATH}")) == R2_SOURCE_SHA256
        and sha256(run_git("show", f"{R2_HEAD}:{R2_TEST_PATH}")) == R2_TEST_SHA256,
        "R2_SOURCE_OR_TEST_SHA256_MISMATCH",
    )
    r2_result = json_object(r2_raw, "R2_RESULT_INVALID_JSON")
    require(git_text("rev-parse", f"{R2_HEAD}^{{tree}}") == R2_TREE, "R2_TREE_MISMATCH")
    require(
        git_text("rev-parse", f"{R2_HEAD}^") == COMMON_BASE_HEAD, "R2_COMMON_BASE_PARENT_MISMATCH"
    )
    r2_base = cast(dict[str, Any], r2_result.get("BASE"))
    require(
        r2_base.get("HEAD") == COMMON_BASE_HEAD
        and r2_base.get("TREE") == COMMON_BASE_TREE
        and r2_base.get("RESULT_SHA256") == COMMON_BASE_RESULT_SHA256,
        "R2_COMMON_BASE_IDENTITY_MISMATCH",
    )
    r2_history = r2_result.get("EVENT_HISTORY")
    history_value = result.get("EVENT_HISTORY")
    require(type(r2_history) is list and len(r2_history) == 32, "R2_EVENT_HISTORY_MISSING")
    require(type(history_value) is list, "PARENT_EVENT_HISTORY_MISSING")
    history = cast(list[dict[str, Any]], history_value)
    validate_event_history(history, EXPECTED_EVENTS_BEFORE)
    require(history[:32] == r2_history, "PARENT_R2_PREFIX_PARITY_MISMATCH")
    return result, raw, history, r2_result


def validate_common_base() -> bytes:
    require(
        git_text("rev-parse", f"{COMMON_BASE_HEAD}^{{tree}}") == COMMON_BASE_TREE,
        "COMMON_31_TREE_MISMATCH",
    )
    raw = run_git("show", f"{COMMON_BASE_HEAD}:{COMMON_BASE_RESULT_PATH}")
    require(sha256(raw) == COMMON_BASE_RESULT_SHA256, "COMMON_31_RESULT_SHA256_MISMATCH")
    common = json_object(raw, "COMMON_31_RESULT_INVALID_JSON")
    require(
        common.get("ROWS_AFTER") == EXPECTED_ROWS and common.get("EVENTS_AFTER") == 31,
        "COMMON_31_RESULT_TOTALS_MISMATCH",
    )
    return raw


def validate_t250_identity(
    parent_history: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    require(git_text("rev-parse", T250_COMMIT) == T250_COMMIT, "T250_COMMIT_UNAVAILABLE")
    require(git_text("rev-parse", f"{T250_COMMIT}^{{tree}}") == T250_TREE, "T250_TREE_MISMATCH")
    require(git_text("rev-parse", f"{T250_COMMIT}^") == T250_PARENT, "T250_PARENT_MISMATCH")
    require(
        git_text("rev-parse", f"{T250_PARENT}^{{tree}}") == COMMON_BASE_TREE,
        "T250_COMMON_BASE_TREE_MISMATCH",
    )
    validate_common_base()
    raw = run_git("show", f"{T250_COMMIT}:{T250_RESULT_PATH}")
    require(sha256(raw) == T250_RESULT_SHA256, "T250_RESULT_SHA256_MISMATCH")
    donor = json_object(raw, "T250_RESULT_INVALID_JSON")
    require(
        donor.get("TASK_ID") == "B649_NEXT_OWNER_T250_32_EVENT_FROM31_FAMILY_INTEGRATION_R1"
        and donor.get("ROWS_AFTER") == EXPECTED_ROWS
        and donor.get("EVENTS_BEFORE") == 31
        and donor.get("EVENTS_AFTER") == 32
        and donor.get("NEW_EVENT_COUNT") == 1
        and donor.get("NEW_EVENT_ID") == T250_EVENT_ID,
        "T250_RESULT_IDENTITY_OR_TOTALS_MISMATCH",
    )
    base = cast(dict[str, Any], donor.get("BASE"))
    require(
        base.get("HEAD") == COMMON_BASE_HEAD
        and base.get("TREE") == COMMON_BASE_TREE
        and base.get("RESULT_SHA256") == COMMON_BASE_RESULT_SHA256
        and base.get("RESULT_PATH") == COMMON_BASE_RESULT_PATH
        and base.get("ROWS") == EXPECTED_ROWS
        and base.get("EVENTS") == 31,
        "T250_COMMON_BASE_IDENTITY_MISMATCH",
    )
    source_path = donor.get("SOURCE_PATH")
    test_path = donor.get("TEST_PATH")
    require(type(source_path) is str and type(test_path) is str, "T250_SOURCE_PATH_MISSING")
    source_path = cast(str, source_path)
    test_path = cast(str, test_path)
    require(
        sha256(run_git("show", f"{T250_COMMIT}:{source_path}")) == donor.get("SOURCE_SHA256")
        and sha256(run_git("show", f"{T250_COMMIT}:{test_path}")) == donor.get("TEST_SHA256"),
        "T250_SOURCE_OR_TEST_SHA256_MISMATCH",
    )
    donor_paths = (
        run_git("diff-tree", "--no-commit-id", "--name-only", "-r", T250_COMMIT)
        .decode("utf-8")
        .splitlines()
    )
    require(
        donor_paths == sorted((source_path, test_path, T250_RESULT_PATH)),
        "T250_COMMITTED_PATH_SET_MISMATCH",
    )
    validate_candidate_tree_entries(committed_tree_entries(T250_COMMIT, donor_paths), donor_paths)
    donor_history_value = donor.get("EVENT_HISTORY")
    require(type(donor_history_value) is list, "T250_EVENT_HISTORY_MISSING")
    donor_history = cast(list[dict[str, Any]], donor_history_value)
    validate_event_history(donor_history, 32)
    require(donor_history[:31] == list(parent_history[:31]), "COMMON_31_EVENT_PREFIX_MISMATCH")
    event = donor_history[-1]
    validate_t250_event(event)
    validate_science_provenance(event, PROFILE_T250)
    science = cast(dict[str, Any], donor.get("SCIENCE_PROVENANCE"))
    require(
        science.get("TASK_ID") == PROFILE_T250.science_task_id
        and science.get("VERDICT") == PROFILE_T250.science_verdict
        and science.get("PROOF_SCOPE") == PROFILE_T250.proof_scope
        and science.get("EVIDENCE_KIND") == PROFILE_T250.evidence_kind
        and science.get("SESSION_ID") == PROFILE_T250.session_id
        and science.get("EXACT_MAX_T") == 250
        and science.get("NEW_BOUND") == PROFILE_T250.new_bound
        and science.get("ROUTE_B_TERMS")
        == PROFILE_T250.route_b_old_terms + PROFILE_T250.route_b_new_terms
        and science.get("TERM_MISMATCH") == 0,
        "T250_SCIENCE_PROVENANCE_MISMATCH",
    )
    return donor, event


def validate_t250_event(event: Mapping[str, Any]) -> None:
    require(event.get("EVENT_ID") == T250_EVENT_ID, "T250_EVENT_ID_MISMATCH")
    require(event.get("PROFILE_ID") == T250_PROFILE_ID, "T250_EVENT_PROFILE_MISMATCH")
    require(
        (
            event.get("BOUND_BEFORE"),
            event.get("CAP_BEFORE"),
            event.get("BOUND_AFTER"),
            event.get("CAP_AFTER"),
        )
        == (313_391_636, 264, 313_266_168, 250),
        "T250_EVENT_TRANSITION_MISMATCH",
    )
    require(
        event.get("S4_BASE_BEFORE") == event.get("S4_BASE_AFTER") == 112
        and event.get("SOURCE_BEFORE") == PROFILE_T250.source_before
        and event.get("SOURCE_AFTER") == PROFILE_T250.source_after,
        "T250_EVENT_SOURCE_OR_S4_MISMATCH",
    )


def validate_event_history(history: Sequence[Mapping[str, Any]], expected_count: int) -> None:
    event_ids: list[str] = []
    for event in history:
        event_id = event.get("EVENT_ID")
        require(type(event_id) is str and bool(event_id), "EVENT_ID_MISSING")
        event_ids.append(cast(str, event_id))
    require(len(event_ids) == len(set(event_ids)), "DUPLICATE_EVENT_ID")
    require(len(history) == expected_count, f"EVENT_COUNT_MISMATCH:EXPECTED_{expected_count}")


def apply_event_history(
    initial_rows: Mapping[str, Row], history: Sequence[Mapping[str, Any]]
) -> dict[str, Row]:
    rows = dict(initial_rows)
    seen: set[str] = set()
    for event in history:
        event_id = event.get("EVENT_ID")
        profile_id = event.get("PROFILE_ID")
        if type(event_id) is not str or not event_id:
            raise ValueError("EVENT_ID_MISSING")
        require(event_id not in seen, f"DUPLICATE_EVENT_ID:{event_id}")
        seen.add(event_id)
        if type(profile_id) is not str or profile_id not in rows:
            raise ValueError("EVENT_PROFILE_ID_INVALID")
        row = rows[profile_id]
        before = (
            event.get("BOUND_BEFORE"),
            event.get("CAP_BEFORE"),
            event.get("S4_BASE_BEFORE"),
            event.get("SOURCE_BEFORE"),
        )
        require(
            (row.bound, row.cap, row.s4_base, row.source) == before,
            f"EVENT_BEFORE_STATE_MISMATCH:{event_id}",
        )
        after_bound, after_cap, after_s4, after_source = (
            event.get("BOUND_AFTER"),
            event.get("CAP_AFTER"),
            event.get("S4_BASE_AFTER"),
            event.get("SOURCE_AFTER"),
        )
        require(
            type(after_bound) is int
            and type(after_cap) is int
            and type(after_s4) is int
            and type(after_source) is str,
            f"EVENT_AFTER_STATE_INVALID:{event_id}",
        )
        rows[profile_id] = replace(
            row, bound=after_bound, cap=after_cap, s4_base=after_s4, source=after_source
        )
    return rows


def load_and_replay_parent_base() -> tuple[
    dict[str, Any], dict[str, Row], dict[str, Row], bytes, list[dict[str, Any]]
]:
    verify_source_closure()
    verify_candidate_ancestry()
    validate_worktree_scope()
    result, raw, history, _r2_result = validate_parent_commit_identity()
    frozen_result, identity = base_r2.LEDGER_ENGINE.verify_frozen_source(ROOT)
    base_r2.validate_frozen_identity(identity)
    frozen_rows = base_r2.LEDGER_ENGINE.load_frozen_seven_row_ledger(frozen_result)
    require(len(frozen_rows) == EXPECTED_ROWS, "FROZEN_ROW_COUNT_MISMATCH")
    rows = apply_event_history(frozen_rows, history)
    require(len(rows) == EXPECTED_ROWS, "PARENT_REPLAY_ROW_COUNT_MISMATCH")
    full = base_r2.ROW_ENGINE.full_digest(rows)
    bounds = base_r2.ROW_ENGINE.bounds_digest(rows)
    require(
        (full, bounds) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST)
        and (result.get("FULL_DIGEST"), result.get("BOUNDS_DIGEST"))
        == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "PARENT_FULL_OR_BOUNDS_DIGEST_REPLAY_MISMATCH",
    )
    _class_info, _mutations = validate_class_identity(
        cast(dict[str, Any], result["CLASS"]), rows, rows
    )
    family = family_summary(rows, EXPECTED_CLASS_BOUND)
    require(
        family.get("FAMILY_BOUND") == EXPECTED_FAMILY_34
        and result.get("FAMILY_AFTER") == EXPECTED_FAMILY_34,
        "PARENT_FAMILY_REPLAY_MISMATCH",
    )
    return result, frozen_rows, rows, raw, history


def validate_profile_id(profile_id: str, spec: ProfileSpec) -> None:
    require(profile_id == spec.profile_id, "TARGET_PROFILE_ID_MISMATCH")


def profile_data(profile_id: str) -> tuple[tuple[int, ...], dict[str, int]]:
    profile = cast(tuple[int, ...], base_r2.SPLIT_ENGINE.profile_values(profile_id))
    distribution = {
        str(degree): count for degree, count in sorted(Counter(profile).items(), reverse=True)
    }
    return profile, distribution


def validate_distribution(distribution: Mapping[str, int], spec: ProfileSpec) -> None:
    require(dict(distribution) == spec.distribution, "TARGET_DEGREE_DISTRIBUTION_MISMATCH")


def profile_parameters(profile: Sequence[int]) -> dict[str, int]:
    degrees = [6 + degree for degree in profile]
    return {
        "W": sum(comb(degree, 2) for degree in degrees),
        "U": sum(comb(degree, 3) for degree in degrees),
        "G_MAX": max(degrees),
        "A_MAX": sum(degree * (g - 2) for degree, g in zip(profile, degrees, strict=True)) // 3,
    }


def validate_wua(parameters: Mapping[str, int], spec: ProfileSpec) -> None:
    require(parameters.get("W") == spec.w, "TARGET_W_MISMATCH")
    require(parameters.get("U") == spec.u, "TARGET_U_MISMATCH")
    require(parameters.get("G_MAX") == spec.g_max, "TARGET_G_MAX_MISMATCH")
    require(parameters.get("A_MAX") == spec.a_max, "TARGET_A_MAX_MISMATCH")


def validate_old_row(row: Row, spec: ProfileSpec) -> None:
    require(
        (row.bound, row.cap, row.s4_base) == (spec.old_bound, spec.old_cap, spec.s4_base),
        f"TARGET_OLD_ROW_IDENTITY_MISMATCH:{spec.profile_id}",
    )
    require(type(row.source) is str, f"TARGET_OLD_ROW_SOURCE_INVALID:{spec.profile_id}")
    if spec.source_before is not None:
        require(
            row.source == spec.source_before, f"TARGET_OLD_ROW_SOURCE_MISMATCH:{spec.profile_id}"
        )


def validate_cap_bound(spec: ProfileSpec, cap: int, bound: int) -> None:
    if cap == spec.old_cap:
        expected = spec.old_bound
    elif cap == spec.new_cap:
        expected = spec.new_bound
    else:
        raise ValueError("UNSUPPORTED_TARGET_CAP")
    require(bound == expected, "TARGET_CAP_BOUND_MISMATCH")


def row_source_after(spec: ProfileSpec) -> str:
    return spec.source_after


def validate_row_source(source: str, spec: ProfileSpec) -> None:
    require(not BANNED_LINEAGE.search(source), "CROSS_LINEAGE_SOURCE_CONTAMINATION")
    require(source == row_source_after(spec), "ROW_SOURCE_BINDING_MISMATCH")


def floor_four_sevenths(s4: int) -> int:
    require(type(s4) is int and s4 >= 0, "S4_MUST_BE_NONNEGATIVE_INTEGER")
    return (4 * s4) // 7


def route_certificate(spec: ProfileSpec, profile: Sequence[int], cap: int) -> dict[str, Any]:
    require(
        cap in (spec.old_cap, spec.new_cap),
        "UNSUPPORTED_ROUTE_B_CAP",
    )
    route = base_r2.LEDGER_ENGINE.route_b_envelope(spec.profile_id, cap)
    r32_terms = base_r2.R32_ENGINE.route_b_envelope(profile, cap, spec.s4_base)
    split_terms = base_r2.SPLIT_ENGINE.route_b_terms(profile, cap, spec.s4_base)
    normalized_r32 = [list(term) for term in r32_terms]
    normalized_split = [list(term) for term in split_terms]
    terms = cast(list[list[int]], route.get("TERMS"))
    mismatch_count = sum(
        left != right for left, right in zip(normalized_r32, normalized_split, strict=False)
    ) + abs(len(normalized_r32) - len(normalized_split))
    require(mismatch_count == 0, "R32_SPLIT_TERM_MISMATCH")
    require(
        terms == normalized_r32 == normalized_split,
        "ROUTE_B_TERMS_DIFFER_FROM_R32_AND_SPLIT",
    )

    parameters = profile_parameters(profile)
    validate_wua(parameters, spec)
    for term in terms:
        t, bound, k4, contained, s4, s3 = term
        k4_numerator = parameters["U"] - (parameters["G_MAX"] - 2) * (parameters["W"] - 3 * t)
        k4_expected = max(0, -((-k4_numerator) // 4))
        contained_expected = min(k4_expected, parameters["A_MAX"])
        s4_expected = max(
            spec.s4_base,
            448 * contained_expected + 679 * (k4_expected - contained_expected),
        )
        s3_expected = 2_800 * parameters["W"] + 11_872 * (t - 22) - 30_800
        bound_floor = 308_390_040 + s3_expected - floor_four_sevenths(s4_expected)
        bound_exact = Fraction(308_390_040 + s3_expected) - Fraction(4 * s4_expected, 7)
        bound_ceiling = -((-bound_exact.numerator) // bound_exact.denominator)
        require(
            (k4, contained, s4, s3) == (k4_expected, contained_expected, s4_expected, s3_expected),
            f"ROUTE_B_INTEGER_RECOUNT_MISMATCH:T={t}",
        )
        require(
            bound == bound_floor == bound_ceiling and 0 <= bound - bound_exact < 1,
            f"ROUTE_B_FRACTION_RECOUNT_MISMATCH:T={t}",
        )

    expected_bound = spec.old_bound if cap == spec.old_cap else spec.new_bound
    validate_cap_bound(spec, cap, cast(int, route.get("BOUND")))
    argmax = cast(list[int], route.get("ARGMAX_TERM"))
    require(
        cast(int, route.get("BOUND")) == expected_bound
        and cast(int, route.get("TERM_COUNT")) == cap - 21 == len(terms)
        and [term[0] for term in terms] == list(range(22, cap + 1))
        and argmax[0] == cap
        and argmax[1] == expected_bound,
        "ROUTE_B_CAP_DOMAIN_OR_BOUND_MISMATCH",
    )
    if cap == spec.new_cap:
        require(argmax == list(spec.argmax_term), "ROUTE_B_ARGMAX_MISMATCH")

    return {
        "CAP": cap,
        "DOMAIN": [22, cap],
        "TERM_COUNT": len(terms),
        "BOUND": expected_bound,
        "ARGMAX_TERM": argmax,
        "TERMS": terms,
        "PROFILE_PARAMETERS": {
            **parameters,
            "S4_BASE": spec.s4_base,
        },
        "INTEGER_RECOUNT": "PASS",
        "FRACTION_RECOUNT": "PASS",
        "R32_CROSSCHECK": "PASS",
        "TERM_MISMATCH_COUNT": mismatch_count,
    }


def validate_science_provenance(event: Mapping[str, Any], spec: ProfileSpec) -> None:
    require(
        event.get("PROOF_SCOPE") == spec.proof_scope
        and event.get("PROOF_EVIDENCE_KIND") == spec.evidence_kind,
        "SCIENCE_PROVENANCE_MISSING_OR_MISMATCHED",
    )
    donor = event.get("DONOR")
    require(type(donor) is dict, "SCIENCE_PROVENANCE_MISSING_OR_MISMATCHED")
    evidence = cast(dict[str, Any], donor)
    if spec is PROFILE_T250:
        expected = {
            "TASK_ID": spec.science_task_id,
            "SESSION_ID": spec.session_id,
            "VERDICT": spec.science_verdict,
            "PROOF_SCOPE": spec.proof_scope,
            "EVIDENCE_KIND": spec.evidence_kind,
            "EXACT_MAX_T": 250,
            "NEW_BOUND": spec.new_bound,
            "ROUTE_B_TERMS": spec.route_b_old_terms + spec.route_b_new_terms,
            "TERM_MISMATCH": spec.route_b_term_mismatch,
        }
    else:
        expected = {
            "TASK_ID": spec.science_task_id,
            "SESSION_NAME": spec.session_name,
            "SESSION_UUID": spec.session_uuid,
            "VERDICT": spec.science_verdict,
            "PROOF_SCOPE": spec.proof_scope,
            "EVIDENCE_KIND": spec.evidence_kind,
            "CAP_ATTAINMENT": spec.cap_attainment,
            "ROUTE_B_OLD_TERMS": spec.route_b_old_terms,
            "ROUTE_B_NEW_TERMS": spec.route_b_new_terms,
            "ROUTE_B_TERM_MISMATCH": spec.route_b_term_mismatch,
        }
    require(
        all(evidence.get(key) == value for key, value in expected.items()),
        "SCIENCE_PROVENANCE_MISSING_OR_MISMATCHED",
    )
    if spec is PROFILE_T237:
        require(
            event.get("MATH_PROVENANCE_STATUS") == MATH_PROVENANCE_STATUS,
            "SCIENCE_PROVENANCE_MISSING_OR_MISMATCHED",
        )


def validate_class_identity(
    class_info: Mapping[str, Any], before_rows: Mapping[str, Row], after_rows: Mapping[str, Row]
) -> tuple[dict[str, Any], int]:
    value = class_info.get("PROFILE_IDS")
    require(type(value) is list, "CLASS_PROFILE_IDS_MISSING")
    ids = cast(list[str], value)
    require(
        len(ids) == EXPECTED_CLASS_COUNT
        and len(set(ids)) == EXPECTED_CLASS_COUNT
        and ids == sorted(ids, reverse=True),
        "CLASS_PROFILE_ID_SET_MISMATCH",
    )
    digest = sha256(json.dumps(ids).encode("utf-8"))
    require(
        digest == EXPECTED_CLASS_ID_SET_SHA256
        and class_info.get("COUNT") == EXPECTED_CLASS_COUNT
        and class_info.get("ID_SET_SHA256") == EXPECTED_CLASS_ID_SET_SHA256,
        "CLASS_IDENTITY_MISMATCH",
    )
    require(
        not set(ids).intersection(before_rows) and not set(ids).intersection(after_rows),
        "CLASS_PROFILE_IDS_MUST_REMAIN_OUTSIDE_RESOLVED_ROW_LEDGER",
    )
    mutations = class_info.get("RESOLVED_ROW_EVENTS")
    require(
        class_info.get("BOUND_BEFORE") == EXPECTED_CLASS_BOUND
        and class_info.get("BOUND_AFTER") == EXPECTED_CLASS_BOUND
        and class_info.get("BOUND_DELTA") == 0
        and mutations == 0,
        "CLASS_BOUND_OR_MUTATION_MISMATCH",
    )
    return cast(dict[str, Any], json.loads(json.dumps(dict(class_info)))), cast(int, mutations)


def family_summary(rows: Mapping[str, Row], class_bound: int) -> dict[str, Any]:
    return base_r2.family_summary(rows, class_bound)


def validate_family_gain(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    expected_before: int,
    expected_after: int,
    expected_gain: int,
) -> int:
    old = before.get("FAMILY_BOUND")
    new = after.get("FAMILY_BOUND")
    require(
        type(old) is int
        and type(new) is int
        and old == expected_before
        and new == expected_after
        and old - new == expected_gain,
        "FAMILY_GAIN_MISMATCH",
    )
    return cast(int, old) - cast(int, new)


def validate_final_frontier(family: Mapping[str, Any]) -> None:
    require(
        family.get("FAMILY_BOUND") == EXPECTED_FAMILY_36
        and family.get("MAX_RESOLVED_BOUND") == EXPECTED_FAMILY_36
        and family.get("MAX_RESOLVED_OWNERS") == [EXPECTED_MAX_OWNER]
        and family.get("NEXT_DISTINCT_BOUND") == EXPECTED_NEXT_DISTINCT_BOUND
        and family.get("NEXT_DISTINCT_OWNERS") == [EXPECTED_NEXT_DISTINCT_OWNER],
        "FAMILY_MAX_OR_NEXT_DISTINCT_MISMATCH",
    )


def validate_ledger_partition(
    before_rows: Mapping[str, Row], after_rows: Mapping[str, Row]
) -> set[str]:
    require(set(before_rows) == set(after_rows), "ROW_ID_SET_CHANGED")
    changed = {pid for pid in before_rows if before_rows[pid] != after_rows[pid]}
    require(changed == {spec.profile_id for spec in PROFILE_SPECS}, "ROW_MUTATION_SET_MISMATCH")
    return changed


def validate_route_bound(spec: ProfileSpec, cap: int, route: Mapping[str, Any]) -> None:
    bound = route.get("BOUND")
    require(type(bound) is int, "R32_ROUTE_BOUND_MISSING")
    validate_cap_bound(spec, cap, cast(int, bound))


def validate_event_profile(event: Mapping[str, Any], expected_profile_id: str) -> None:
    require(event.get("PROFILE_ID") == expected_profile_id, "TARGET_PROFILE_ID_MISMATCH")


def validate_event_prefix(
    parent_history: Sequence[Mapping[str, Any]], history: Sequence[Mapping[str, Any]]
) -> None:
    require(list(history[: len(parent_history)]) == list(parent_history), "EVENT_PREFIX_MUTATION")


def validate_result_bytes(actual: bytes, expected: bytes) -> None:
    require(actual == expected, "CANDIDATE_RESULT_REPLAY_MISMATCH")


def expect_rejected(action: Callable[[], object]) -> str:
    try:
        action()
    except (
        ValueError,
        AssertionError,
        KeyError,
        IndexError,
        TypeError,
    ) as exc:
        return f"REJECTED: {type(exc).__name__}: {exc}"
    raise AssertionError("negative control was unexpectedly accepted")


def negative_case_results(
    parent_history: Sequence[Mapping[str, Any]],
    history: Sequence[Mapping[str, Any]],
    before_rows: Mapping[str, Row],
    middle_rows: Mapping[str, Row],
    after_rows: Mapping[str, Row],
    profiles: Sequence[Mapping[str, Any]],
    class_info: Mapping[str, Any],
    family_before: Mapping[str, Any],
    family_after: Mapping[str, Any],
    encoded_result: bytes,
) -> dict[str, str]:
    t250_event = cast(dict[str, Any], history[-2])
    t237_event = cast(dict[str, Any], history[-1])
    t250_row = before_rows[PROFILE_T250.profile_id]
    t237_row = middle_rows[PROFILE_T237.profile_id]
    route = cast(dict[str, Any], cast(dict[str, Any], profiles[0]["ROUTE_B"])["NEW"])
    unrelated = dict(after_rows)
    unrelated_id = next(
        pid for pid in unrelated if pid not in {spec.profile_id for spec in PROFILE_SPECS}
    )
    unrelated[unrelated_id] = replace(
        unrelated[unrelated_id], bound=unrelated[unrelated_id].bound + 1
    )
    wrong_class = dict(class_info)
    wrong_class["ID_SET_SHA256"] = "0" * 64
    wrong_family = dict(family_after)
    wrong_family["FAMILY_BOUND"] = EXPECTED_FAMILY_36 - 1
    wrong_before = dict(t237_event)
    wrong_before["BOUND_BEFORE"] = cast(int, wrong_before["BOUND_BEFORE"]) + 1
    missing_science = dict(t237_event)
    missing_science.pop("DONOR", None)
    changed_prefix = [dict(event) for event in history]
    changed_prefix[0]["EVENT_ID"] = "MUTATED_PREFIX_EVENT"
    wrong_tree_entry = [(["100644", "blob", "0" * 40], SOURCE_PATH)]
    return {
        "WRONG_PARENT_HEAD_TREE": expect_rejected(
            lambda: validate_parent_identity("0" * 40, BASE_TREE, BASE_RESULT_SHA256)
        ),
        "WRONG_PARENT_COMMIT_PARENT": expect_rejected(
            lambda: validate_candidate_parent("f" * 40, ["f" * 40, "0" * 40])
        ),
        "WRONG_COMMITTED_PATH_SET": expect_rejected(
            lambda: validate_committed_paths([*COMMITTED_PATHS, "src/foreign.py"])
        ),
        "WRONG_COMMITTED_TREE_ENTRIES": expect_rejected(
            lambda: validate_candidate_tree_entries(wrong_tree_entry, COMMITTED_PATHS)
        ),
        "WRONG_SOURCE_CLOSURE": expect_rejected(
            lambda: verify_source_closure(
                {
                    "lottolab.foreign_candidate": str(
                        ROOT / "src/lottolab/research/foreign_untracked_candidate.py"
                    )
                }
            )
        ),
        "WRONG_T250_PROFILE": expect_rejected(lambda: validate_event_profile(t250_event, "0" * 20)),
        "WRONG_T237_PROFILE": expect_rejected(lambda: validate_event_profile(t237_event, "0" * 20)),
        "WRONG_T250_OLD_CAP": expect_rejected(
            lambda: validate_old_row(replace(t250_row, cap=t250_row.cap - 1), PROFILE_T250)
        ),
        "WRONG_T237_OLD_BOUND": expect_rejected(
            lambda: validate_old_row(replace(t237_row, bound=t237_row.bound + 1), PROFILE_T237)
        ),
        "WRONG_BEFORE_STATE": expect_rejected(
            lambda: apply_event_history(middle_rows, [wrong_before])
        ),
        "UNSUPPORTED_CAP": expect_rejected(
            lambda: validate_cap_bound(
                PROFILE_T237, PROFILE_T237.new_cap - 1, PROFILE_T237.new_bound
            )
        ),
        "WRONG_R32_BOUND": expect_rejected(
            lambda: validate_route_bound(
                PROFILE_T250,
                PROFILE_T250.new_cap,
                {**route, "BOUND": cast(int, route["BOUND"]) + 1},
            )
        ),
        "MISSING_EVENT": expect_rejected(
            lambda: validate_event_history(history[:-1], EXPECTED_EVENTS_AFTER)
        ),
        "DUPLICATE_EVENT": expect_rejected(
            lambda: validate_event_history([*history, history[-1]], EXPECTED_EVENTS_AFTER)
        ),
        "EVENT_PREFIX_MUTATION": expect_rejected(
            lambda: validate_event_prefix(parent_history, changed_prefix)
        ),
        "UNRELATED_ROW_MUTATION": expect_rejected(
            lambda: validate_ledger_partition(before_rows, unrelated)
        ),
        "WRONG_CLASS_IDENTITY": expect_rejected(
            lambda: validate_class_identity(wrong_class, before_rows, after_rows)
        ),
        "INCORRECT_FAMILY_GAIN": expect_rejected(
            lambda: validate_family_gain(
                family_before,
                wrong_family,
                EXPECTED_FAMILY_34,
                EXPECTED_FAMILY_36,
                EXPECTED_GAIN_34_TO_36,
            )
        ),
        "MISSING_SCIENCE_PROVENANCE": expect_rejected(
            lambda: validate_science_provenance(missing_science, PROFILE_T237)
        ),
        "CROSS_LINEAGE_UNCOMMITTED_IMPORT": expect_rejected(
            lambda: verify_source_closure(
                {"lottolab.cross_lineage": str(ROOT / "src/lottolab/research/uncommitted.py")}
            )
        ),
        "UNEXPECTED_DIRTY_PATH": expect_rejected(
            lambda: validate_worktree_scope("?? src/unapproved.py\n")
        ),
        "PRE_POSTCOMMIT_CANONICAL_BYTE_DRIFT": expect_rejected(
            lambda: validate_result_bytes(encoded_result + b"x", encoded_result)
        ),
    }


def validate_profile_old_state(
    spec: ProfileSpec, old_row: Row, profile: Sequence[int]
) -> dict[str, int]:
    validate_old_row(old_row, spec)
    validate_profile_id(spec.profile_id, spec)
    distribution = {
        str(degree): count for degree, count in sorted(Counter(profile).items(), reverse=True)
    }
    require(distribution == spec.distribution, "TARGET_DEGREE_DISTRIBUTION_MISMATCH")
    require(
        len(profile) == 20
        and sum(profile) == 66
        and sum(value * value for value in profile) == spec.sum_squares,
        f"TARGET_PROFILE_MOMENTS_MISMATCH:{spec.profile_id}",
    )
    return distribution


def build_candidate() -> tuple[dict[str, Any], dict[str, Row], dict[str, Row]]:
    parent_result, frozen_rows, base_rows, parent_raw, parent_history = (
        load_and_replay_parent_base()
    )
    donor_result, t250_event = validate_t250_identity(parent_history)
    class_info, class_mutations = validate_class_identity(
        cast(dict[str, Any], parent_result["CLASS"]), base_rows, base_rows
    )
    class_bound = cast(int, class_info["BOUND_AFTER"])
    family_34 = family_summary(base_rows, class_bound)
    require(family_34.get("FAMILY_BOUND") == EXPECTED_FAMILY_34, "FAMILY_34_REPLAY_MISMATCH")

    current_rows = dict(base_rows)
    middle_rows: dict[str, Row] | None = None
    profiles: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = list(parent_history)
    current_frontier = family_34

    for index, spec in enumerate(PROFILE_SPECS):
        profile, _ = profile_data(spec.profile_id)
        old_row = current_rows[spec.profile_id]
        distribution = validate_profile_old_state(spec, old_row, profile)
        parameters = profile_parameters(profile)
        validate_wua(parameters, spec)
        old_route = route_certificate(spec, profile, spec.old_cap)
        new_route = route_certificate(spec, profile, spec.new_cap)
        old_terms = cast(list[list[int]], old_route["TERMS"])
        new_terms = cast(list[list[int]], new_route["TERMS"])
        require(
            new_terms == old_terms[: len(new_terms)], f"ROUTE_B_PREFIX_MISMATCH:{spec.profile_id}"
        )
        require(
            old_route["TERM_COUNT"] == spec.route_b_old_terms
            and new_route["TERM_COUNT"] == spec.route_b_new_terms
            and old_route["TERM_MISMATCH_COUNT"]
            == new_route["TERM_MISMATCH_COUNT"]
            == spec.route_b_term_mismatch,
            f"ROUTE_B_TERM_TOTAL_MISMATCH:{spec.profile_id}",
        )
        updated = replace(
            old_row, bound=spec.new_bound, cap=spec.new_cap, source=row_source_after(spec)
        )
        validate_cap_bound(spec, updated.cap, updated.bound)
        validate_row_source(updated.source, spec)
        current_rows[spec.profile_id] = updated

        if index == 0:
            event = json.loads(json.dumps(t250_event))
            validate_t250_event(event)
        else:
            event = base_r2.base31.base.nine.event_from_update(
                spec.event_id, spec.profile_id, old_row, updated
            )
            event["PROOF_SCOPE"] = spec.proof_scope
            event["PROOF_EVIDENCE_KIND"] = spec.evidence_kind
            event["MATH_PROVENANCE_STATUS"] = MATH_PROVENANCE_STATUS
            event["DONOR"] = {
                "TASK_ID": spec.science_task_id,
                "SESSION_NAME": spec.session_name,
                "SESSION_UUID": spec.session_uuid,
                "VERDICT": spec.science_verdict,
                "PROOF_SCOPE": spec.proof_scope,
                "EVIDENCE_KIND": spec.evidence_kind,
                "CAP_ATTAINMENT": spec.cap_attainment,
                "ROUTE_B_OLD_TERMS": spec.route_b_old_terms,
                "ROUTE_B_NEW_TERMS": spec.route_b_new_terms,
                "ROUTE_B_TERM_MISMATCH": spec.route_b_term_mismatch,
                "W": spec.w,
                "U": spec.u,
                "G_MAX": spec.g_max,
                "A_MAX": spec.a_max,
                "S4_BASE": spec.s4_base,
            }
            event["ROUTE_B"] = {
                "OLD_TERM_COUNT": old_route["TERM_COUNT"],
                "NEW_TERM_COUNT": new_route["TERM_COUNT"],
                "OLD_ARGMAX": old_route["ARGMAX_TERM"],
                "NEW_ARGMAX": new_route["ARGMAX_TERM"],
                "W": parameters["W"],
                "U": parameters["U"],
                "G_MAX": parameters["G_MAX"],
                "A_MAX": parameters["A_MAX"],
                "S4_BASE": spec.s4_base,
                "INTEGER_RECOUNT": "PASS",
                "FRACTION_RECOUNT": "PASS",
                "R32_CROSSCHECK": "PASS",
                "TERM_MISMATCH_COUNT": 0,
            }
        validate_event_profile(event, spec.profile_id)
        validate_science_provenance(event, spec)
        require(
            (
                event.get("BOUND_BEFORE"),
                event.get("CAP_BEFORE"),
                event.get("S4_BASE_BEFORE"),
                event.get("SOURCE_BEFORE"),
            )
            == (old_row.bound, old_row.cap, old_row.s4_base, old_row.source)
            and (
                event.get("BOUND_AFTER"),
                event.get("CAP_AFTER"),
                event.get("S4_BASE_AFTER"),
                event.get("SOURCE_AFTER"),
            )
            == (updated.bound, updated.cap, updated.s4_base, updated.source),
            f"EVENT_BEFORE_OR_AFTER_STATE_MISMATCH:{spec.event_id}",
        )
        events.append(event)

        after_frontier = family_summary(current_rows, class_bound)
        expected_after = EXPECTED_FAMILY_35 if index == 0 else EXPECTED_FAMILY_36
        expected_gain = EXPECTED_GAIN_34_TO_35 if index == 0 else EXPECTED_GAIN_35_TO_36
        gain = validate_family_gain(
            current_frontier,
            after_frontier,
            cast(int, current_frontier["FAMILY_BOUND"]),
            expected_after,
            expected_gain,
        )
        transitions.append(
            {
                "EVENT_ID": spec.event_id,
                "FAMILY_BOUND_BEFORE": current_frontier["FAMILY_BOUND"],
                "FAMILY_BOUND_AFTER": after_frontier["FAMILY_BOUND"],
                "FAMILY_GAIN": gain,
                "MAX_RESOLVED_OWNERS_AFTER": after_frontier["MAX_RESOLVED_OWNERS"],
                "NEXT_DISTINCT_BOUND_AFTER": after_frontier["NEXT_DISTINCT_BOUND"],
                "NEXT_DISTINCT_OWNERS_AFTER": after_frontier["NEXT_DISTINCT_OWNERS"],
            }
        )
        current_frontier = after_frontier
        if index == 0:
            middle_rows = dict(current_rows)
        profiles.append(
            {
                "EVENT_ID": spec.event_id,
                "PROFILE_ID": spec.profile_id,
                "DEGREE_DISTRIBUTION": distribution,
                "W": parameters["W"],
                "U": parameters["U"],
                "G_MAX": parameters["G_MAX"],
                "A_MAX": parameters["A_MAX"],
                "S4_BASE": spec.s4_base,
                "OLD_CAP": spec.old_cap,
                "NEW_CAP": spec.new_cap,
                "OLD_BOUND": spec.old_bound,
                "NEW_BOUND": spec.new_bound,
                "OWNER_BOUND_DELTA": spec.old_bound - spec.new_bound,
                "OLD_ROW_SOURCE": old_row.source,
                "NEW_ROW_SOURCE": updated.source,
                "CAP_ATTAINMENT": spec.cap_attainment,
                "ROUTE_B": {"OLD": old_route, "NEW": new_route},
                "SCIENCE_PROVENANCE": cast(dict[str, Any], event["DONOR"]),
            }
        )

    require(middle_rows is not None, "MISSING_35_EVENT_STATE")
    middle_state = cast(dict[str, Row], middle_rows)
    validate_event_history(events, EXPECTED_EVENTS_AFTER)
    validate_event_prefix(parent_history, events)
    require(events[:EXPECTED_EVENTS_BEFORE] == parent_history, "EVENT_PREFIX_PARITY_FAILED")
    require(
        [event["EVENT_ID"] for event in events[EXPECTED_EVENTS_BEFORE:]]
        == [spec.event_id for spec in PROFILE_SPECS],
        "ADDED_EVENT_ID_ORDER_MISMATCH",
    )
    replayed_after = apply_event_history(frozen_rows, events)
    require(replayed_after == current_rows, "FULL_36_EVENT_REPLAY_MISMATCH")
    replayed_middle = apply_event_history(frozen_rows, events[:EXPECTED_EVENTS_MIDDLE])
    require(replayed_middle == middle_rows, "FULL_35_EVENT_REPLAY_MISMATCH")
    changed = validate_ledger_partition(base_rows, current_rows)
    require(
        len(changed) == 2 and len(base_rows) - len(changed) == 4_645, "CHANGED_ROW_TOTAL_MISMATCH"
    )

    full_before = base_r2.ROW_ENGINE.full_digest(base_rows)
    bounds_before = base_r2.ROW_ENGINE.bounds_digest(base_rows)
    full_after = base_r2.ROW_ENGINE.full_digest(current_rows)
    bounds_after = base_r2.ROW_ENGINE.bounds_digest(current_rows)
    require(
        (full_before, bounds_before) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "PARENT_BASE_DIGEST_CHANGED",
    )
    require(bounds_after == EXPECTED_BOUNDS_DIGEST, "EXPECTED_36_EVENT_BOUNDS_DIGEST_MISMATCH")
    class_info, class_mutations = validate_class_identity(class_info, base_rows, current_rows)
    family_36 = family_summary(current_rows, class_bound)
    gain_34_to_36 = validate_family_gain(
        family_34, family_36, EXPECTED_FAMILY_34, EXPECTED_FAMILY_36, EXPECTED_GAIN_34_TO_36
    )
    validate_final_frontier(family_36)

    prefix_sha = sha256(serialize_result({"EVENT_HISTORY": parent_history}))
    candidate_prefix_sha = sha256(
        serialize_result({"EVENT_HISTORY": events[:EXPECTED_EVENTS_BEFORE]})
    )
    require(prefix_sha == candidate_prefix_sha, "EVENT_PREFIX_DIGEST_MISMATCH")
    source_file = ROOT / SOURCE_PATH
    test_file = ROOT / TEST_PATH
    require(source_file.is_file() and not source_file.is_symlink(), "CANDIDATE_SOURCE_MISSING")
    require(test_file.is_file() and not test_file.is_symlink(), "CANDIDATE_TEST_MISSING")
    source_sha = sha256(source_file.read_bytes())
    test_sha = sha256(test_file.read_bytes())

    negative_args = (
        parent_history,
        events,
        base_rows,
        middle_state,
        current_rows,
        profiles,
        class_info,
        family_34,
        family_36,
    )
    negative = negative_case_results(*negative_args, b"")
    donor_event_sha = sha256(serialize_result({"EVENT": t250_event}))
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_COMMIT_COMPATIBLE_36_EVENT_CANDIDATE_REPLAYED",
        "IMPLEMENTATION_DEPTH": "NORMAL",
        "DEPTH_SOURCE": "PLANNER_SUPPLIED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "ENGINEERING_JUDGE_STATUS": "SELF_CHECK_ONLY",
        "FORMAL_FAMILY_AUTHORITY": "NOT_ACCEPTED",
        "COMMIT_MODEL": {
            "PARENT": BASE_HEAD,
            "EXPECTED_PATHS": list(COMMITTED_PATHS),
            "MAX_LOCAL_COMMITS": 1,
            "FINAL_HEAD_EMBEDDED": False,
            "FINAL_TREE_EMBEDDED": False,
        },
        "POSTCOMMIT_REPLAY_POLICY": "REPLAY_CANDIDATE_AND_FOCUSED_TESTS_FROM_FINAL_COMMIT",
        "SOURCE_CLOSURE_POLICY": "FIXED_PARENT_COMMITTED_PYTHON_MODULES_PLUS_THIS_CANDIDATE_SOURCE",
        "SOURCE_CLOSURE": {
            "STATUS": "PASS",
            "EXTERNAL_UNCOMMITTED_IMPORTS": 0,
            "T250_DONOR_USED_AS_RUNTIME_IMPORT": False,
        },
        "SOURCE_MUTATIONS_OUTSIDE_SCOPE": 0,
        "OUT_OF_SCOPE_WORKTREE_PATHS": [],
        "BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "PARENT": BASE_PARENT_HEAD,
            "PARENT_TREE": BASE_PARENT_TREE,
            "RESULT_PATH": BASE_RESULT_PATH,
            "RESULT_SHA256": sha256(parent_raw),
            "SOURCE_PATH": BASE_SOURCE_PATH,
            "SOURCE_SHA256": BASE_SOURCE_SHA256,
            "TEST_PATH": BASE_TEST_PATH,
            "TEST_SHA256": BASE_TEST_SHA256,
            "ROWS": len(base_rows),
            "EVENTS": len(parent_history),
            "FULL_DIGEST": full_before,
            "BOUNDS_DIGEST": bounds_before,
            "EVENT_HISTORY_SHA256": prefix_sha,
        },
        "FROZEN": {
            "HEAD": base_r2.FROZEN_HEAD,
            "TREE": base_r2.FROZEN_TREE,
            "RESULT_SHA256": base_r2.FROZEN_RESULT_SHA256,
        },
        "ROWS_BEFORE": len(base_rows),
        "ROWS_AFTER": len(current_rows),
        "EVENTS_BEFORE": len(parent_history),
        "EVENTS_MIDDLE": EXPECTED_EVENTS_MIDDLE,
        "EVENTS_AFTER": len(events),
        "ADDED_EVENTS": len(events) - len(parent_history),
        "EVENT_PREFIX_PARITY": "EXACT",
        "EVENT_PREFIX_SHA256": candidate_prefix_sha,
        "DUPLICATE_EVENTS": 0,
        "CHANGED_ROWS": len(changed),
        "CHANGED_ROW_IDS": sorted(changed),
        "UNCHANGED_ROWS": len(base_rows) - len(changed),
        "BEFORE_STATE_MISMATCHES": 0,
        "UNRELATED_ROW_MUTATIONS": 0,
        "PROFILES": profiles,
        "EVENT_TRANSITIONS": transitions,
        "CLASS": class_info,
        "CLASS_VALIDATION_SCOPE": "197_PROFILE_ID_SET_AND_BOUND_REVALIDATED;NO_CLASS_MUTATIONS",
        "CLASS_COUNT": EXPECTED_CLASS_COUNT,
        "CLASS_BOUND": class_bound,
        "CLASS_ID_SET_SHA256": EXPECTED_CLASS_ID_SET_SHA256,
        "CLASS_MUTATIONS": class_mutations,
        "FAMILY_34": family_34["FAMILY_BOUND"],
        "FAMILY_35": transitions[0]["FAMILY_BOUND_AFTER"],
        "FAMILY_36": family_36["FAMILY_BOUND"],
        "FAMILY_BEFORE": family_34["FAMILY_BOUND"],
        "FAMILY_AFTER": family_36["FAMILY_BOUND"],
        "FAMILY_GAIN_34_TO_35": transitions[0]["FAMILY_GAIN"],
        "FAMILY_GAIN_35_TO_36": transitions[1]["FAMILY_GAIN"],
        "FAMILY_GAIN_34_TO_36": gain_34_to_36,
        "FAMILY_GAIN_31_TO_36": EXPECTED_GAIN_31_TO_36,
        "MAX_OWNER": family_36["MAX_RESOLVED_OWNERS"][0],
        "MAX_RESOLVED_BOUND": family_36["MAX_RESOLVED_BOUND"],
        "MAXIMIZING_OWNERS": family_36["MAX_RESOLVED_OWNERS"],
        "NEXT_DISTINCT_BOUND": family_36["NEXT_DISTINCT_BOUND"],
        "NEXT_DISTINCT_OWNER": family_36["NEXT_DISTINCT_OWNERS"][0],
        "NEXT_DISTINCT_OWNERS": family_36["NEXT_DISTINCT_OWNERS"],
        "FULL_DIGEST": full_after,
        "BOUNDS_DIGEST": bounds_after,
        "MATH_PROVENANCE_STATUS": MATH_PROVENANCE_STATUS,
        "MATH_PROVENANCE": {
            "T250": cast(dict[str, Any], donor_result["SCIENCE_PROVENANCE"]),
            "T237": cast(dict[str, Any], events[-1]["DONOR"]),
        },
        "EVENT_SOURCE_EVIDENCE": {
            "COMMON_BASE_HEAD": COMMON_BASE_HEAD,
            "COMMON_BASE_TREE": COMMON_BASE_TREE,
            "COMMON_BASE_RESULT_SHA256": COMMON_BASE_RESULT_SHA256,
            "T250_COMMIT": T250_COMMIT,
            "T250_TREE": T250_TREE,
            "T250_PARENT": T250_PARENT,
            "T250_RESULT_SHA256": T250_RESULT_SHA256,
            "T250_INCREMENT_EVENT_ID": T250_EVENT_ID,
            "T250_INCREMENT_EVENT_SHA256": donor_event_sha,
            "T250_DONOR_USED_AS_RUNTIME_IMPORT": False,
            "DONOR_FULL_HISTORY_CONCATENATED": False,
            "COMMON_31_EVENT_PREFIX_PARITY": "EXACT",
        },
        "NEGATIVE_CASE_RESULTS": negative,
        "EVENT_HISTORY": events,
        "SOURCE_SHA256": source_sha,
        "TEST_SHA256": test_sha,
        "PUSH": "NOT_RUN",
        "PR": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
        "FORMAL_FAMILY_AUTHORITY_ADOPTION": "NOT_ACCEPTED",
    }
    encoded = serialize_result(result)
    result["NEGATIVE_CASE_RESULTS"] = negative_case_results(*negative_args, encoded)
    require(
        all(value.startswith("REJECTED:") for value in result["NEGATIVE_CASE_RESULTS"].values()),
        "REQUIRED_NEGATIVE_CONTROL_ACCEPTED",
    )
    require(serialize_result(result) == encoded, "NEGATIVE_CONTROL_RESULT_SERIALIZATION_CHANGED")
    return result, base_rows, current_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="create the result if absent")
    mode.add_argument("--check", action="store_true", help="replay and compare the saved result")
    args = parser.parse_args()

    result, _before, _after = build_candidate()
    encoded = serialize_result(result)
    output_path = ROOT / RESULT_PATH
    if args.write:
        try:
            with output_path.open("xb") as output:
                output.write(encoded)
            outcome = "CREATED"
        except FileExistsError:
            validate_result_bytes(output_path.read_bytes(), encoded)
            outcome = "ALREADY_MATCHES"
        print(f"RESULT_WRITE: {outcome}")
    else:
        require(output_path.is_file(), "CANDIDATE_RESULT_MISSING")
        validate_result_bytes(output_path.read_bytes(), encoded)
        print("CANDIDATE_REPLAY: PASS")

    print(
        json.dumps(
            {
                "ROWS": result["ROWS_AFTER"],
                "EVENTS": result["EVENTS_AFTER"],
                "CHANGED_ROWS": result["CHANGED_ROWS"],
                "FAMILY_34": result["FAMILY_34"],
                "FAMILY_35": result["FAMILY_35"],
                "FAMILY_36": result["FAMILY_36"],
                "FAMILY_GAIN_34_TO_36": result["FAMILY_GAIN_34_TO_36"],
                "FULL_DIGEST": result["FULL_DIGEST"],
                "BOUNDS_DIGEST": result["BOUNDS_DIGEST"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
