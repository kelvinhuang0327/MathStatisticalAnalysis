"""Build and replay the exact 34-event continuation of the pinned B649 R2 ledger."""

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

TASK_ID = "B649_W832_32R2_DUAL_EVENT_34_EXACT_R1"
ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = "src/lottolab/research/b649_w832_32r2_dual_34_exact_r1.py"
TEST_PATH = "tests/unit/test_b649_w832_32r2_dual_34_exact_r1.py"
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-w832-32r2-dual-34-exact-r1-result.json"
)
COMMITTED_PATHS = tuple(sorted((SOURCE_PATH, TEST_PATH, RESULT_PATH)))
PRESERVED_R1_PATHS = (
    "docs/research/matrix-native-results/"
    "b649-w832-z6-t256-32-event-from31-r1-result.json",
    "src/lottolab/research/b649_w832_z6_t256_32_event_from31_r1.py",
    "tests/unit/test_b649_w832_z6_t256_32_event_from31_r1.py",
)

BASE_HEAD = "3cece5b6d5ac61bb0637adc8d755d2af7a760cbb"
BASE_TREE = "d93a6c833db8e1461d2693505d3dfc34c8832363"
BASE_PARENT_HEAD = "88a37370e6db035d6155190723de8cea646e76b7"
BASE_PARENT_TREE = "4fede8e927eab43d58b906ce80e7eea10300b4a0"
BASE_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-w832-z6-t256-32-event-from31-r2-result.json"
)
BASE_RESULT_SHA256 = "ba226e0a1808468f6ad1f58bb3bc411109276896cbe81cbc5b719b61a72715a3"
BASE_SOURCE_PATH = "src/lottolab/research/b649_w832_z6_t256_32_event_from31_r2.py"
BASE_SOURCE_SHA256 = "7d71ccf1263f84a97fdfe484e83f8fe46ca146138e86c8960c764fe0e1797975"
BASE_TEST_PATH = "tests/unit/test_b649_w832_z6_t256_32_event_from31_r2.py"
BASE_TEST_SHA256 = "262537133d430b20b2d5dfc4b9eb7a97d93797ae2be551c0cc1041d4f5fa8095"
BASE_FULL_DIGEST = "5667e54776b5fade56831c76228bf65fd926aed9d66048b459450eb31ec4de7f"
BASE_BOUNDS_DIGEST = "3b8ee21e9c6d96712bf7310434b0de3158f665ca54cee2d53f0841b62e3e6d67"

DONOR_BASE_HEAD = "88a37370e6db035d6155190723de8cea646e76b7"
DONOR_SOURCE_SHA256 = "4ca05fd20ba3a336a0652cc5a37ae33b4ab126e78b2e15da10b6a58856eff326"
DONOR_RESULT_SHA256 = "2a581072b4ee4e0c1fa3d1878362d6c270527ed4b027c827022f14e90b54b39e"
MATH_TASK_ID = "B649_NEXT_TWO_FRONTIER_FRESH_MATH_JUDGE_R1"
MATH_VERDICT_CLAIM = "VERIFIED_WITH_CAVEATS"
MATH_PROOF_SCOPE_CLAIM = "TWO_FULL_PROFILES"
MATH_EVIDENCE_KIND = "TRANSCRIPT_ONLY"
MATH_TRANSCRIPT_LOCATOR = "UNKNOWN"
MATH_PROVENANCE_STATUS = "INHERITED_REPORT_ONLY"

EXPECTED_ROWS = 4_647
EXPECTED_EVENTS_BEFORE = 32
EXPECTED_EVENTS_AFTER = 34
EXPECTED_CLASS_COUNT = 197
EXPECTED_CLASS_BOUND = 313_258_872
EXPECTED_CLASS_ID_SET_SHA256 = "1fd8ef4779e3967b75cbeaa2ca65de9afc2551d27ae7e98daa1e3f700fc24e8b"
EXPECTED_FAMILY_BEFORE = 313_391_740
EXPECTED_FAMILY_AFTER = 313_391_636
EXPECTED_FAMILY_GAIN = 104
EXPECTED_MAX_OWNER = "66665555555321100000"
EXPECTED_NEXT_DISTINCT_BOUND = 313_391_560
EXPECTED_NEXT_DISTINCT_OWNER = "65555555555432100000"
EXPECTED_BOUNDS_DIGEST = "850eda553999f1dd0a92ff14df01c4ba3ee33e0d37a823c11dff1092918bd872"

MATH_PROVENANCE: dict[str, str] = {
    "TASK_ID": MATH_TASK_ID,
    "VERDICT_CLAIM": MATH_VERDICT_CLAIM,
    "PROOF_SCOPE_CLAIM": MATH_PROOF_SCOPE_CLAIM,
    "EVIDENCE_KIND": MATH_EVIDENCE_KIND,
    "ACTUAL_TRANSCRIPT_LOCATOR": MATH_TRANSCRIPT_LOCATOR,
    "STATUS": MATH_PROVENANCE_STATUS,
    "FRESH_CERTIFICATION": "NOT_PERFORMED",
}
BANNED_LINEAGE = re.compile(
    r"(?:\b(?:35|36|37|38)[-_ ]*event\b|\bB649[_-][A-Z0-9_-]*(?:35|36|37|38)[_-]EVENT\b)",
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
    distribution: dict[str, int]
    w: int
    u: int
    g_max: int
    a_max: int
    catalog_source: str
    configurations: int
    config_set_sha256: str
    argmax_term: tuple[int, ...]


PROFILE_A = ProfileSpec(
    event_id="T256_66655555555331100000",
    profile_id="66655555555331100000",
    old_cap=265,
    new_cap=256,
    old_bound=313_391_740,
    new_bound=313_311_276,
    s4_base=112,
    distribution={"6": 3, "5": 8, "3": 2, "1": 2, "0": 5},
    w=827,
    u=2318,
    g_max=12,
    a_max=197,
    catalog_source=(
        "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:"
        "NB_CERTIFICATES[1206]"
    ),
    configurations=1150,
    config_set_sha256="e7fa2321c2fcdaec777e993d9ee8af683e10f4157da32e39095be11c1ed112de",
    argmax_term=(256, 313_311_276, 432, 197, 247_821, 5_062_848),
)
PROFILE_B = ProfileSpec(
    event_id="T258_66655555555411110000",
    profile_id="66655555555411110000",
    old_cap=265,
    new_cap=258,
    old_bound=313_391_740,
    new_bound=313_328_812,
    s4_base=112,
    distribution={"6": 3, "5": 8, "4": 1, "1": 4, "0": 4},
    w=827,
    u=2320,
    g_max=12,
    a_max=197,
    catalog_source=(
        "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:"
        "NB_CERTIFICATES[1204]"
    ),
    configurations=757,
    config_set_sha256="784b8b4f2d2e75b8923c7f0558ca182cd79217a1c65bf608d86c36bb09a35635",
    argmax_term=(258, 313_328_812, 448, 197, 258_685, 5_086_592),
)
PROFILE_SPECS = (PROFILE_A, PROFILE_B)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run_git(*args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], check=True, capture_output=True
    ).stdout


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
    return (
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def validate_base_identity(head: str, tree: str, result_sha256: str) -> None:
    require((head, tree) == (BASE_HEAD, BASE_TREE), "BASE_HEAD_TREE_MISMATCH")
    require(result_sha256 == BASE_RESULT_SHA256, "BASE_RESULT_SHA256_MISMATCH")


def validate_candidate_parent(head: str, parents: Sequence[str]) -> None:
    require(
        list(parents) == [head, BASE_HEAD],
        "CANDIDATE_MUST_BE_DIRECT_CHILD_OF_PINNED_BASE",
    )


def validate_committed_paths(paths: Sequence[str]) -> None:
    require(list(paths) == list(COMMITTED_PATHS), "COMMITTED_PATH_SET_MISMATCH")


def committed_tree_entries(head: str, paths: Sequence[str]) -> list[tuple[list[str], str]]:
    entries = run_git("ls-tree", head, "--", *paths).decode("utf-8").splitlines()
    parsed: list[tuple[list[str], str]] = []
    for line in entries:
        if "\t" not in line:
            continue
        metadata, path = line.split("\t", maxsplit=1)
        parsed.append((metadata.split(), path))
    return parsed


def validate_candidate_tree_entries(
    parsed: Sequence[tuple[Sequence[str], str]], paths: Sequence[str]
) -> None:
    require(
        len(parsed) == len(paths)
        and {path for _metadata, path in parsed} == set(paths)
        and all(
            list(metadata[:2]) == ["100644", "blob"]
            for metadata, _path in parsed
        ),
        "COMMITTED_TREE_ENTRIES_MISMATCH",
    )


def verify_candidate_ancestry() -> str:
    """Accept the fixed Base or its one exact three-path candidate child."""
    head = git_text("rev-parse", "HEAD")
    if head == BASE_HEAD:
        require(
            git_text("rev-parse", "HEAD^{tree}") == BASE_TREE,
            "BASE_TREE_MISMATCH",
        )
        return head

    parents = git_text("rev-list", "--parents", "-n", "1", head).split()
    validate_candidate_parent(head, parents)
    paths = run_git(
        "diff-tree", "--no-commit-id", "--name-only", "-r", head
    ).decode("utf-8").splitlines()
    validate_committed_paths(paths)
    validate_candidate_tree_entries(committed_tree_entries(head, paths), paths)
    dirty_candidate_paths = set(validate_worktree_scope()).intersection(paths)
    for path in paths:
        current = (ROOT / path).read_bytes()
        committed = run_git("show", f"{head}:{path}")
        require(
            current == committed or path in dirty_candidate_paths,
            f"COMMITTED_CANDIDATE_BYTES_MISMATCH:{path}",
        )
    return head


def validate_worktree_scope() -> list[str]:
    allowed = set(COMMITTED_PATHS) | set(PRESERVED_R1_PATHS)
    output = run_git("status", "--short", "--untracked-files=all").decode(
        "utf-8"
    ).rstrip("\n")
    observed: list[str] = []
    for line in output.splitlines():
        require(len(line) >= 4, "WORKTREE_STATUS_LINE_INVALID")
        path = line[3:]
        require(path in allowed, f"OUT_OF_SCOPE_WORKTREE_PATH:{path}")
        observed.append(path)
    return sorted(observed)


def verify_source_closure(
    module_files: Mapping[str, str] | None = None,
) -> int:
    """Allow only Base-committed LottoLab modules plus this candidate source."""
    if module_files is None:
        loaded = tuple(
            (name, getattr(module, "__file__", None), module)
            for name, module in tuple(sys.modules.items())
        )
    else:
        loaded = tuple(
            (name, file_name, None) for name, file_name in module_files.items()
        )

    root = ROOT.resolve()
    own_source = (ROOT / SOURCE_PATH).resolve()
    verified_base_modules = 0
    for module_name, file_name, module in loaded:
        if module_name != "lottolab" and not module_name.startswith("lottolab."):
            continue
        if file_name is None:
            namespace_paths = getattr(module, "__path__", None)
            expected_namespace = root / "src/lottolab/research"
            resolved_paths = (
                tuple(Path(path).resolve() for path in namespace_paths)
                if namespace_paths is not None
                else ()
            )
            require(
                module_name == "lottolab.research"
                and resolved_paths == (expected_namespace,),
                f"SOURCE_CLOSURE_NAMESPACE_PATH_MISMATCH:{module_name}",
            )
            continue

        require(
            type(file_name) is str,
            f"SOURCE_CLOSURE_MODULE_FILE_MISSING:{module_name}",
        )
        path = Path(cast(str, file_name)).resolve()
        if path == own_source:
            require(path.is_file(), "CANDIDATE_SOURCE_MISSING")
            continue
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(
                f"SOURCE_CLOSURE_MODULE_OUTSIDE_WORKTREE:{module_name}"
            ) from exc
        require(relative.endswith(".py"), f"SOURCE_CLOSURE_MODULE_NOT_PYTHON:{relative}")
        try:
            committed = run_git("show", f"{BASE_HEAD}:{relative}")
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"UNCOMMITTED_IMPORT_MODULE:{relative}") from exc
        require(
            path.is_file() and path.read_bytes() == committed,
            f"BASE_MODULE_BYTES_MISMATCH:{relative}",
        )
        verified_base_modules += 1

    require(
        Path(base_r2.__file__).resolve() == root / BASE_SOURCE_PATH,
        "R2_MODULE_IMPORT_PATH_MISMATCH",
    )
    return verified_base_modules


def validate_r2_commit_identity() -> tuple[dict[str, Any], bytes]:
    require(git_text("rev-parse", BASE_HEAD) == BASE_HEAD, "R2_HEAD_UNAVAILABLE")
    require(
        git_text("rev-parse", f"{BASE_HEAD}^{{tree}}") == BASE_TREE,
        "R2_TREE_MISMATCH",
    )
    require(
        git_text("rev-parse", f"{BASE_PARENT_HEAD}^{{tree}}") == BASE_PARENT_TREE,
        "R2_PARENT_TREE_MISMATCH",
    )
    parents = git_text("rev-list", "--parents", "-n", "1", BASE_HEAD).split()
    require(
        parents == [BASE_HEAD, BASE_PARENT_HEAD],
        "R2_PARENT_IDENTITY_MISMATCH",
    )
    r2_paths = list(base_r2.COMMITTED_PATHS)
    actual_paths = run_git(
        "diff-tree", "--no-commit-id", "--name-only", "-r", BASE_HEAD
    ).decode("utf-8").splitlines()
    require(actual_paths == r2_paths, "R2_COMMITTED_PATH_SET_MISMATCH")
    validate_candidate_tree_entries(
        committed_tree_entries(BASE_HEAD, actual_paths), actual_paths
    )

    for path in r2_paths:
        committed = run_git("show", f"{BASE_HEAD}:{path}")
        require((ROOT / path).read_bytes() == committed, f"R2_BLOB_BYTES_MISMATCH:{path}")

    source_sha = sha256((ROOT / BASE_SOURCE_PATH).read_bytes())
    test_sha = sha256((ROOT / BASE_TEST_PATH).read_bytes())
    result_raw = run_git("show", f"{BASE_HEAD}:{BASE_RESULT_PATH}")
    result_sha = sha256(result_raw)
    validate_base_identity(BASE_HEAD, BASE_TREE, result_sha)
    require(source_sha == BASE_SOURCE_SHA256, "R2_SOURCE_SHA256_MISMATCH")
    require(test_sha == BASE_TEST_SHA256, "R2_TEST_SHA256_MISMATCH")
    require(
        (ROOT / BASE_RESULT_PATH).read_bytes() == result_raw,
        "R2_RESULT_WORKTREE_BYTES_MISMATCH",
    )
    base_result = json_object(result_raw, "R2_RESULT_INVALID_JSON")
    require(
        base_result.get("TASK_ID") == base_r2.TASK_ID
        and base_result.get("SOURCE_SHA256") == BASE_SOURCE_SHA256
        and base_result.get("TEST_SHA256") == BASE_TEST_SHA256
        and base_result.get("ROWS_AFTER") == EXPECTED_ROWS
        and base_result.get("EVENTS_AFTER") == EXPECTED_EVENTS_BEFORE
        and base_result.get("FULL_DIGEST") == BASE_FULL_DIGEST
        and base_result.get("BOUNDS_DIGEST") == BASE_BOUNDS_DIGEST,
        "R2_RESULT_IDENTITY_OR_TOTALS_MISMATCH",
    )
    base_identity = cast(dict[str, Any], base_result.get("BASE"))
    require(
        base_identity.get("HEAD") == BASE_PARENT_HEAD
        and base_identity.get("TREE") == BASE_PARENT_TREE
        and base_identity.get("RESULT_SHA256") == base_r2.BASE_RESULT_SHA256
        and base_identity.get("ROWS") == EXPECTED_ROWS
        and base_identity.get("EVENTS") == 31
        and base_identity.get("FULL_DIGEST") == base_r2.BASE_FULL_DIGEST
        and base_identity.get("BOUNDS_DIGEST") == base_r2.BASE_BOUNDS_DIGEST,
        "R2_PARENT_RESULT_IDENTITY_MISMATCH",
    )
    return base_result, result_raw


def validate_event_history(
    history: Sequence[Mapping[str, Any]], expected_count: int
) -> None:
    event_ids: list[str] = []
    for event in history:
        event_id = event.get("EVENT_ID")
        require(type(event_id) is str and bool(event_id), "EVENT_ID_MISSING")
        event_ids.append(cast(str, event_id))
    require(len(event_ids) == len(set(event_ids)), "DUPLICATE_EVENT_ID")
    require(
        len(history) == expected_count,
        f"EVENT_COUNT_MISMATCH:EXPECTED_{expected_count}",
    )


def apply_event_history(
    initial_rows: Mapping[str, Row],
    history: Sequence[Mapping[str, Any]],
) -> dict[str, Row]:
    rows = dict(initial_rows)
    seen: set[str] = set()
    for event in history:
        event_id = event.get("EVENT_ID")
        profile_id = event.get("PROFILE_ID")
        if type(event_id) is not str or not event_id:
            raise ValueError("EVENT_ID_MISSING")
        event_id_text = event_id
        require(event_id_text not in seen, f"DUPLICATE_EVENT_ID:{event_id_text}")
        seen.add(event_id_text)
        if type(profile_id) is not str or profile_id not in rows:
            raise ValueError("EVENT_PROFILE_ID_INVALID")
        profile_id_text = profile_id
        row = rows[profile_id_text]
        before = (
            event.get("BOUND_BEFORE"),
            event.get("CAP_BEFORE"),
            event.get("S4_BASE_BEFORE"),
            event.get("SOURCE_BEFORE"),
        )
        actual = (row.bound, row.cap, row.s4_base, row.source)
        require(
            actual == before,
            f"EVENT_BEFORE_STATE_MISMATCH:{event_id_text}",
        )
        after_bound = event.get("BOUND_AFTER")
        after_cap = event.get("CAP_AFTER")
        after_s4 = event.get("S4_BASE_AFTER")
        after_source = event.get("SOURCE_AFTER")
        require(
            type(after_bound) is int
            and type(after_cap) is int
            and type(after_s4) is int
            and type(after_source) is str,
            f"EVENT_AFTER_STATE_INVALID:{event_id_text}",
        )
        rows[profile_id_text] = replace(
            row,
            bound=cast(int, after_bound),
            cap=cast(int, after_cap),
            s4_base=cast(int, after_s4),
            source=cast(str, after_source),
        )
    return rows


def load_and_replay_r2_base() -> tuple[
    dict[str, Any], dict[str, Row], dict[str, Row], bytes, list[dict[str, Any]]
]:
    verify_source_closure()
    verify_candidate_ancestry()
    validate_worktree_scope()
    base_result, base_raw = validate_r2_commit_identity()

    frozen_result, frozen_identity = base_r2.LEDGER_ENGINE.verify_frozen_source(ROOT)
    base_r2.validate_frozen_identity(frozen_identity)
    frozen_rows = base_r2.LEDGER_ENGINE.load_frozen_seven_row_ledger(frozen_result)
    require(len(frozen_rows) == EXPECTED_ROWS, "FROZEN_ROW_COUNT_MISMATCH")

    history_value = base_result.get("EVENT_HISTORY")
    require(type(history_value) is list, "R2_EVENT_HISTORY_MISSING")
    history = cast(list[dict[str, Any]], history_value)
    validate_event_history(history, EXPECTED_EVENTS_BEFORE)
    require(
        base_result.get("EVENTS_BEFORE") == 31
        and history[-1].get("EVENT_ID") == base_r2.EVENT_ID,
        "R2_EVENT_PREFIX_IDENTITY_MISMATCH",
    )
    require(
        not {
            spec.event_id for spec in PROFILE_SPECS
        }.intersection({cast(str, event["EVENT_ID"]) for event in history}),
        "DUAL_EVENT_ALREADY_PRESENT_IN_R2_PREFIX",
    )

    base_rows = apply_event_history(frozen_rows, history)
    require(
        len(base_rows) == EXPECTED_ROWS
        and base_result.get("ROWS_BEFORE") == EXPECTED_ROWS
        and base_result.get("ROWS_AFTER") == EXPECTED_ROWS,
        "R2_REPLAY_ROW_COUNT_MISMATCH",
    )
    full_digest = base_r2.ROW_ENGINE.full_digest(base_rows)
    bounds_digest = base_r2.ROW_ENGINE.bounds_digest(base_rows)
    require(
        (full_digest, bounds_digest)
        == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST)
        == (
            base_result.get("FULL_DIGEST"),
            base_result.get("BOUNDS_DIGEST"),
        ),
        "R2_FULL_OR_BOUNDS_DIGEST_REPLAY_MISMATCH",
    )
    return base_result, frozen_rows, base_rows, base_raw, history


def validate_profile_id(profile_id: str, spec: ProfileSpec) -> None:
    require(profile_id == spec.profile_id, "TARGET_PROFILE_ID_MISMATCH")


def profile_data(profile_id: str) -> tuple[tuple[int, ...], dict[str, int]]:
    profile = cast(tuple[int, ...], base_r2.SPLIT_ENGINE.profile_values(profile_id))
    distribution = {
        str(degree): count
        for degree, count in sorted(Counter(profile).items(), reverse=True)
    }
    return profile, distribution


def validate_distribution(
    distribution: Mapping[str, int], spec: ProfileSpec
) -> None:
    require(dict(distribution) == spec.distribution, "TARGET_DEGREE_DISTRIBUTION_MISMATCH")


def profile_parameters(profile: Sequence[int]) -> dict[str, int]:
    degrees = [6 + degree for degree in profile]
    return {
        "W": sum(comb(degree, 2) for degree in degrees),
        "U": sum(comb(degree, 3) for degree in degrees),
        "G_MAX": max(degrees),
        "A_MAX": sum(
            degree * (g - 2) for degree, g in zip(profile, degrees, strict=True)
        )
        // 3,
    }


def validate_wua(parameters: Mapping[str, int], spec: ProfileSpec) -> None:
    require(parameters.get("W") == spec.w, "TARGET_W_MISMATCH")
    require(parameters.get("U") == spec.u, "TARGET_U_MISMATCH")
    require(parameters.get("G_MAX") == spec.g_max, "TARGET_G_MAX_MISMATCH")
    require(parameters.get("A_MAX") == spec.a_max, "TARGET_A_MAX_MISMATCH")


def validate_old_row(row: Row, spec: ProfileSpec) -> None:
    require(
        (row.bound, row.cap, row.s4_base, row.source)
        == (
            spec.old_bound,
            spec.old_cap,
            spec.s4_base,
            spec.catalog_source,
        ),
        f"TARGET_OLD_ROW_IDENTITY_MISMATCH:{spec.profile_id}",
    )


def validate_cap_bound(spec: ProfileSpec, cap: int, bound: int) -> None:
    if cap == spec.old_cap:
        expected_bound = spec.old_bound
    elif cap == spec.new_cap:
        expected_bound = spec.new_bound
    else:
        raise ValueError("UNSUPPORTED_TARGET_CAP")
    require(bound == expected_bound, "TARGET_CAP_BOUND_MISMATCH")


def row_source_after(spec: ProfileSpec) -> str:
    return (
        f"catalog:{spec.catalog_source};PROFILE_ID={spec.profile_id};"
        f"OLD_CAP={spec.old_cap};NEW_CAP={spec.new_cap};"
        f"OLD_BOUND={spec.old_bound};NEW_BOUND={spec.new_bound};"
        f"SCIENCE_JUDGE_TASK_ID={MATH_TASK_ID};"
        f"SCIENCE_JUDGE_EVIDENCE_KIND={MATH_EVIDENCE_KIND};"
        f"PROOF_SCOPE={MATH_PROOF_SCOPE_CLAIM}"
    )


def validate_row_source(source: str, spec: ProfileSpec) -> None:
    require(not BANNED_LINEAGE.search(source), "CROSS_LINEAGE_SOURCE_CONTAMINATION")
    require(source == row_source_after(spec), "ROW_SOURCE_BINDING_MISMATCH")


def floor_four_sevenths(s4: int) -> int:
    require(type(s4) is int and s4 >= 0, "S4_MUST_BE_NONNEGATIVE_INTEGER")
    return (4 * s4) // 7


def route_certificate(
    spec: ProfileSpec, profile: Sequence[int], cap: int
) -> dict[str, Any]:
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
        left != right
        for left, right in zip(normalized_r32, normalized_split, strict=False)
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
        k4_numerator = parameters["U"] - (
            parameters["G_MAX"] - 2
        ) * (parameters["W"] - 3 * t)
        k4_expected = max(0, -((-k4_numerator) // 4))
        contained_expected = min(k4_expected, parameters["A_MAX"])
        s4_expected = max(
            spec.s4_base,
            448 * contained_expected
            + 679 * (k4_expected - contained_expected),
        )
        s3_expected = (
            2_800 * parameters["W"]
            + 11_872 * (t - 22)
            - 30_800
        )
        bound_floor = 308_390_040 + s3_expected - floor_four_sevenths(s4_expected)
        bound_exact = Fraction(308_390_040 + s3_expected) - Fraction(
            4 * s4_expected, 7
        )
        bound_ceiling = -((-bound_exact.numerator) // bound_exact.denominator)
        require(
            (k4, contained, s4, s3)
            == (k4_expected, contained_expected, s4_expected, s3_expected),
            f"ROUTE_B_INTEGER_RECOUNT_MISMATCH:T={t}",
        )
        require(
            bound == bound_floor == bound_ceiling
            and 0 <= bound - bound_exact < 1,
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


def validate_class_identity(
    class_info: Mapping[str, Any],
    before_rows: Mapping[str, Row],
    after_rows: Mapping[str, Row],
) -> tuple[dict[str, Any], int]:
    ids_value = class_info.get("PROFILE_IDS")
    require(type(ids_value) is list, "CLASS_PROFILE_IDS_MISSING")
    ids = cast(list[str], ids_value)
    require(
        len(ids) == EXPECTED_CLASS_COUNT
        and len(set(ids)) == EXPECTED_CLASS_COUNT
        and ids == sorted(ids, reverse=True),
        "CLASS_PROFILE_ID_SET_MISMATCH",
    )
    id_digest = sha256(json.dumps(ids).encode("utf-8"))
    require(
        id_digest == EXPECTED_CLASS_ID_SET_SHA256
        and class_info.get("COUNT") == EXPECTED_CLASS_COUNT
        and class_info.get("ID_SET_SHA256") == EXPECTED_CLASS_ID_SET_SHA256,
        "CLASS_IDENTITY_MISMATCH",
    )
    require(
        not set(ids).intersection(before_rows)
        and not set(ids).intersection(after_rows),
        "CLASS_PROFILE_IDS_MUST_REMAIN_OUTSIDE_RESOLVED_ROW_LEDGER",
    )
    class_before = class_info.get("BOUND_BEFORE")
    class_after = class_info.get("BOUND_AFTER")
    class_mutations = class_info.get("RESOLVED_ROW_EVENTS")
    require(
        class_before == EXPECTED_CLASS_BOUND
        and class_after == EXPECTED_CLASS_BOUND
        and class_info.get("BOUND_DELTA") == 0
        and class_mutations == 0,
        "CLASS_BOUND_OR_MUTATION_MISMATCH",
    )
    copied = cast(dict[str, Any], json.loads(json.dumps(dict(class_info))))
    return copied, cast(int, class_mutations)


def family_summary(rows: Mapping[str, Row], class_bound: int) -> dict[str, Any]:
    return base_r2.family_summary(rows, class_bound)


def validate_family_gain(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> int:
    before_bound = before.get("FAMILY_BOUND")
    after_bound = after.get("FAMILY_BOUND")
    require(
        before_bound == EXPECTED_FAMILY_BEFORE
        and after_bound == EXPECTED_FAMILY_AFTER
        and before_bound - after_bound == EXPECTED_FAMILY_GAIN,
        "FAMILY_GAIN_MISMATCH",
    )
    require(
        after.get("MAX_RESOLVED_BOUND") == EXPECTED_FAMILY_AFTER
        and after.get("MAX_RESOLVED_OWNERS") == [EXPECTED_MAX_OWNER]
        and after.get("NEXT_DISTINCT_BOUND") == EXPECTED_NEXT_DISTINCT_BOUND
        and after.get("NEXT_DISTINCT_OWNERS") == [EXPECTED_NEXT_DISTINCT_OWNER],
        "FAMILY_MAX_OR_NEXT_DISTINCT_MISMATCH",
    )
    return cast(int, before_bound) - cast(int, after_bound)


def validate_math_provenance(provenance: Mapping[str, Any]) -> None:
    require(
        provenance.get("TASK_ID") == MATH_TASK_ID
        and provenance.get("VERDICT_CLAIM") == MATH_VERDICT_CLAIM
        and provenance.get("PROOF_SCOPE_CLAIM") == MATH_PROOF_SCOPE_CLAIM
        and provenance.get("EVIDENCE_KIND") == "TRANSCRIPT_ONLY"
        and provenance.get("ACTUAL_TRANSCRIPT_LOCATOR") == "UNKNOWN"
        and provenance.get("STATUS") == "INHERITED_REPORT_ONLY"
        and provenance.get("FRESH_CERTIFICATION") == "NOT_PERFORMED",
        "MATH_PROVENANCE_NOT_INHERITED_REPORT_ONLY",
    )


def validate_ledger_partition(
    before_rows: Mapping[str, Row], after_rows: Mapping[str, Row]
) -> set[str]:
    require(set(before_rows) == set(after_rows), "ROW_ID_SET_CHANGED")
    changed = {
        profile_id
        for profile_id in before_rows
        if before_rows[profile_id] != after_rows[profile_id]
    }
    expected = {spec.profile_id for spec in PROFILE_SPECS}
    require(changed == expected, "ROW_MUTATION_SET_MISMATCH")
    return changed


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
    base_result: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    full_history: Sequence[Mapping[str, Any]],
    before_rows: Mapping[str, Row],
    after_rows: Mapping[str, Row],
    profile_info: Sequence[Mapping[str, Any]],
    class_info: Mapping[str, Any],
    family_before: Mapping[str, Any],
    family_after: Mapping[str, Any],
    provenance: Mapping[str, Any],
    encoded_result: bytes,
) -> dict[str, str]:
    spec = PROFILE_A
    old_row = before_rows[spec.profile_id]
    route = cast(dict[str, Any], profile_info[0]["ROUTE_B"])
    parameters = cast(
        dict[str, int],
        cast(dict[str, Any], route["OLD"])["PROFILE_PARAMETERS"],
    )
    unrelated = dict(after_rows)
    unrelated_id = next(
        profile_id for profile_id in unrelated if profile_id not in {
            item.profile_id for item in PROFILE_SPECS
        }
    )
    unrelated[unrelated_id] = replace(
        unrelated[unrelated_id],
        bound=unrelated[unrelated_id].bound + 1,
    )
    wrong_class = dict(class_info)
    wrong_class["ID_SET_SHA256"] = "0" * 64
    wrong_family_after = dict(family_after)
    wrong_family_after["FAMILY_BOUND"] = EXPECTED_FAMILY_AFTER - 1
    wrong_provenance = dict(provenance)
    wrong_provenance["STATUS"] = "FRESHLY_CERTIFIED"
    wrong_event = dict(full_history[-1])
    wrong_event["BOUND_BEFORE"] = cast(int, wrong_event["BOUND_BEFORE"]) + 1

    return {
        "WRONG_BASE_HEAD_TREE": expect_rejected(
            lambda: validate_base_identity("0" * 40, BASE_TREE, BASE_RESULT_SHA256)
        ),
        "WRONG_BASE_RESULT_SHA": expect_rejected(
            lambda: validate_base_identity(BASE_HEAD, BASE_TREE, "0" * 64)
        ),
        "WRONG_TARGET_PROFILE": expect_rejected(
            lambda: validate_profile_id("0" * 20, spec)
        ),
        "WRONG_ORIGINAL_CAP": expect_rejected(
            lambda: validate_old_row(replace(old_row, cap=264), spec)
        ),
        "WRONG_ORIGINAL_BOUND": expect_rejected(
            lambda: validate_old_row(replace(old_row, bound=old_row.bound + 1), spec)
        ),
        "WRONG_NEW_CAP": expect_rejected(
            lambda: validate_cap_bound(spec, spec.new_cap - 1, spec.new_bound)
        ),
        "WRONG_NEW_BOUND": expect_rejected(
            lambda: validate_cap_bound(spec, spec.new_cap, spec.new_bound + 1)
        ),
        "WRONG_W": expect_rejected(
            lambda: validate_wua({**parameters, "W": parameters["W"] + 1}, spec)
        ),
        "WRONG_U": expect_rejected(
            lambda: validate_wua({**parameters, "U": parameters["U"] + 1}, spec)
        ),
        "WRONG_A_MAX": expect_rejected(
            lambda: validate_wua(
                {**parameters, "A_MAX": parameters["A_MAX"] + 1}, spec
            )
        ),
        "MISSING_EVENT": expect_rejected(
            lambda: validate_event_history(full_history[:-1], EXPECTED_EVENTS_AFTER)
        ),
        "DUPLICATE_EVENT": expect_rejected(
            lambda: validate_event_history(
                [*full_history, full_history[-1]], EXPECTED_EVENTS_AFTER
            )
        ),
        "WRONG_BEFORE_STATE": expect_rejected(
            lambda: apply_event_history(
                before_rows, [*full_history[-2:-1], wrong_event]
            )
        ),
        "UNRELATED_ROW_MUTATION": expect_rejected(
            lambda: validate_ledger_partition(before_rows, unrelated)
        ),
        "WRONG_FAMILY_GAIN": expect_rejected(
            lambda: validate_family_gain(family_before, wrong_family_after)
        ),
        "WRONG_CLASS": expect_rejected(
            lambda: validate_class_identity(wrong_class, before_rows, after_rows)
        ),
        "CROSS_LINEAGE_IMPORT": expect_rejected(
            lambda: verify_source_closure(
                {
                    "lottolab.foreign_candidate": str(
                        ROOT
                        / "src/lottolab/research/foreign_untracked_candidate.py"
                    )
                }
            )
        ),
        "WRONG_PARENT": expect_rejected(
            lambda: validate_candidate_parent("f" * 40, ["f" * 40, "0" * 40])
        ),
        "WRONG_PATH_SET": expect_rejected(
            lambda: validate_committed_paths([*COMMITTED_PATHS, "src/foreign.py"])
        ),
        "WRONG_POSTCOMMIT_GUARD": expect_rejected(
            lambda: validate_result_bytes(encoded_result + b"x", encoded_result)
        ),
        "FALSE_FRESH_MATH_CERTIFICATION": expect_rejected(
            lambda: validate_math_provenance(wrong_provenance)
        ),
        "WRONG_R2_PREFIX": expect_rejected(
            lambda: require(
                list(history) == list(full_history[: len(history) - 1]),
                "R2_EVENT_PREFIX_PARITY_MISMATCH",
            )
        ),
        "WRONG_BASE_ROWS": expect_rejected(
            lambda: require(
                base_result.get("ROWS_AFTER") == EXPECTED_ROWS - 1,
                "R2_REPLAY_ROW_COUNT_MISMATCH",
            )
        ),
    }


def validate_profile_old_state(
    spec: ProfileSpec, old_row: Row, profile: Sequence[int]
) -> dict[str, int]:
    validate_old_row(old_row, spec)
    validate_profile_id(spec.profile_id, spec)
    distribution = {
        str(degree): count
        for degree, count in sorted(Counter(profile).items(), reverse=True)
    }
    validate_distribution(distribution, spec)
    require(
        len(profile) == 20
        and sum(profile) == 66
        and sum(degree * degree for degree in profile) == 328,
        f"TARGET_PROFILE_MOMENTS_MISMATCH:{spec.profile_id}",
    )
    return distribution


def build_candidate() -> tuple[dict[str, Any], dict[str, Row], dict[str, Row]]:
    closure_count = verify_source_closure()
    verify_candidate_ancestry()
    validate_worktree_scope()
    base_result, frozen_rows, base_rows, base_raw, base_history = (
        load_and_replay_r2_base()
    )
    class_base_value = cast(dict[str, Any], base_result.get("CLASS"))
    class_info, _base_class_mutations = validate_class_identity(
        class_base_value, base_rows, base_rows
    )
    class_bound = cast(int, class_info["BOUND_AFTER"])
    family_before = family_summary(base_rows, class_bound)
    require(
        family_before.get("FAMILY_BOUND") == EXPECTED_FAMILY_BEFORE,
        "FAMILY_BEFORE_MISMATCH",
    )

    current_rows = dict(base_rows)
    new_events: list[dict[str, Any]] = []
    profile_results: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    current_frontier = family_before

    for spec in PROFILE_SPECS:
        profile, _ignored_distribution = profile_data(spec.profile_id)
        old_row = current_rows[spec.profile_id]
        distribution = validate_profile_old_state(spec, old_row, profile)
        parameters = profile_parameters(profile)
        validate_wua(parameters, spec)
        old_route = route_certificate(spec, profile, spec.old_cap)
        new_route = route_certificate(spec, profile, spec.new_cap)
        old_terms = cast(list[list[int]], old_route["TERMS"])
        new_terms = cast(list[list[int]], new_route["TERMS"])
        require(
            new_terms == old_terms[: len(new_terms)],
            f"ROUTE_B_PREFIX_MISMATCH:{spec.profile_id}",
        )

        updated_row = replace(
            old_row,
            bound=spec.new_bound,
            cap=spec.new_cap,
            source=row_source_after(spec),
        )
        validate_cap_bound(spec, updated_row.cap, updated_row.bound)
        validate_row_source(updated_row.source, spec)
        current_rows[spec.profile_id] = updated_row

        event = base_r2.base31.base.nine.event_from_update(
            spec.event_id, spec.profile_id, old_row, updated_row
        )
        event["PROOF_SCOPE_CLAIM"] = MATH_PROOF_SCOPE_CLAIM
        event["MATH_PROVENANCE_STATUS"] = MATH_PROVENANCE_STATUS
        event["CATALOG_SOURCE"] = spec.catalog_source
        event["CONFIGURATIONS"] = spec.configurations
        event["CONFIG_SET_SHA256"] = spec.config_set_sha256
        event["ARGMAX_TERM"] = list(spec.argmax_term)
        event["ROUTE_B"] = {
            "OLD_TERM_COUNT": old_route["TERM_COUNT"],
            "NEW_TERM_COUNT": new_route["TERM_COUNT"],
            "OLD_ARGMAX": old_route["ARGMAX_TERM"],
            "NEW_ARGMAX": new_route["ARGMAX_TERM"],
            "W": parameters["W"],
            "U": parameters["U"],
            "A_MAX": parameters["A_MAX"],
            "S4_BASE": spec.s4_base,
            "INTEGER_RECOUNT": "PASS",
            "FRACTION_RECOUNT": "PASS",
            "R32_CROSSCHECK": "PASS",
            "TERM_MISMATCH_COUNT": (
                cast(int, old_route["TERM_MISMATCH_COUNT"])
                + cast(int, new_route["TERM_MISMATCH_COUNT"])
            ),
        }
        new_events.append(event)

        frontier_after_event = family_summary(current_rows, class_bound)
        transitions.append(
            {
                "EVENT_ID": spec.event_id,
                "FAMILY_BOUND_BEFORE": current_frontier["FAMILY_BOUND"],
                "FAMILY_BOUND_AFTER": frontier_after_event["FAMILY_BOUND"],
                "MAX_RESOLVED_OWNERS_AFTER": frontier_after_event[
                    "MAX_RESOLVED_OWNERS"
                ],
                "NEXT_DISTINCT_BOUND_AFTER": frontier_after_event[
                    "NEXT_DISTINCT_BOUND"
                ],
                "NEXT_DISTINCT_OWNERS_AFTER": frontier_after_event[
                    "NEXT_DISTINCT_OWNERS"
                ],
            }
        )
        current_frontier = frontier_after_event
        profile_results.append(
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
                "NEW_ROW_SOURCE": updated_row.source,
                "SUPPORT_VALIDATION": "NOT_RUN_NO_ROW_REALIZATION",
                "SUPPORT_SIGNATURE": None,
                "ROUTE_B": {"OLD": old_route, "NEW": new_route},
                "CATALOG_SOURCE_KIND": "VIRTUAL_LOCATOR_PRESERVED_AS_PROVENANCE",
                "CATALOG_SOURCE": spec.catalog_source,
                "CONFIGURATIONS": spec.configurations,
                "CONFIG_SET_SHA256": spec.config_set_sha256,
            }
        )

    events = [*base_history, *new_events]
    validate_event_history(events, EXPECTED_EVENTS_AFTER)
    require(
        events[:EXPECTED_EVENTS_BEFORE] == base_history,
        "EVENT_PREFIX_PARITY_FAILED",
    )
    require(
        [event["EVENT_ID"] for event in new_events]
        == [spec.event_id for spec in PROFILE_SPECS],
        "ADDED_EVENT_ID_ORDER_MISMATCH",
    )

    after_rows = current_rows
    replayed_after_rows = apply_event_history(frozen_rows, events)
    require(replayed_after_rows == after_rows, "FULL_34_EVENT_REPLAY_MISMATCH")
    changed_ids = validate_ledger_partition(base_rows, after_rows)
    require(
        len(changed_ids) == 2
        and len(base_rows) - len(changed_ids) == 4_645,
        "CHANGED_ROW_TOTAL_MISMATCH",
    )

    full_before = base_r2.ROW_ENGINE.full_digest(base_rows)
    bounds_before = base_r2.ROW_ENGINE.bounds_digest(base_rows)
    full_after = base_r2.ROW_ENGINE.full_digest(after_rows)
    bounds_after = base_r2.ROW_ENGINE.bounds_digest(after_rows)
    require(
        (full_before, bounds_before) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "R2_BASE_DIGEST_CHANGED",
    )
    require(
        bounds_after == EXPECTED_BOUNDS_DIGEST,
        "EXPECTED_34_EVENT_BOUNDS_DIGEST_MISMATCH",
    )

    class_info, class_mutations = validate_class_identity(
        class_info, base_rows, after_rows
    )
    family_after = family_summary(after_rows, class_bound)
    family_gain = validate_family_gain(family_before, family_after)
    require(
        family_gain == EXPECTED_FAMILY_GAIN,
        "EXPECTED_FAMILY_GAIN_MISMATCH",
    )

    validate_math_provenance(MATH_PROVENANCE)
    event_prefix_digest = sha256(serialize_result({"EVENT_HISTORY": base_history}))
    candidate_prefix_digest = sha256(
        serialize_result({"EVENT_HISTORY": events[:EXPECTED_EVENTS_BEFORE]})
    )
    require(
        event_prefix_digest == candidate_prefix_digest,
        "EVENT_PREFIX_DIGEST_MISMATCH",
    )

    source_file = ROOT / SOURCE_PATH
    test_file = ROOT / TEST_PATH
    require(source_file.is_file() and not source_file.is_symlink(), "CANDIDATE_SOURCE_MISSING")
    require(test_file.is_file() and not test_file.is_symlink(), "CANDIDATE_TEST_MISSING")
    source_sha256 = sha256(source_file.read_bytes())
    test_sha256 = sha256(test_file.read_bytes())

    encoded_placeholder = b""
    negative = negative_case_results(
        base_result,
        base_history,
        events,
        base_rows,
        after_rows,
        profile_results,
        class_info,
        family_before,
        family_after,
        MATH_PROVENANCE,
        encoded_placeholder,
    )
    placeholder_replay_guard = negative["WRONG_POSTCOMMIT_GUARD"]
    require(
        placeholder_replay_guard
        == "REJECTED: ValueError: CANDIDATE_RESULT_REPLAY_MISMATCH",
        "POSTCOMMIT_GUARD_NEGATIVE_CONTROL_MISMATCH",
    )

    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_COMMIT_COMPATIBLE_34_EVENT_CANDIDATE_REPLAYED",
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
        "POSTCOMMIT_REPLAY_POLICY": (
            "RUN_CANDIDATE_CHECK_AND_FOCUSED_TESTS_AFTER_COMMIT"
        ),
        "SOURCE_CLOSURE_POLICY": (
            "PINNED_R2_BASE_PYTHON_MODULES_PLUS_THIS_CANDIDATE_SOURCE"
        ),
        "SOURCE_CLOSURE": {
            "STATUS": "PASS",
            "VERIFIED_BASE_MODULE_COUNT": closure_count,
            "EXTERNAL_UNCOMMITTED_IMPORTS": 0,
        },
        "SOURCE_MUTATIONS_OUTSIDE_SCOPE": 0,
        "OUT_OF_SCOPE_WORKTREE_PATHS": [],
        "BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "PARENT": BASE_PARENT_HEAD,
            "PARENT_TREE": BASE_PARENT_TREE,
            "RESULT_PATH": BASE_RESULT_PATH,
            "RESULT_SHA256": sha256(base_raw),
            "SOURCE_PATH": BASE_SOURCE_PATH,
            "SOURCE_SHA256": BASE_SOURCE_SHA256,
            "TEST_PATH": BASE_TEST_PATH,
            "TEST_SHA256": BASE_TEST_SHA256,
            "ROWS": len(base_rows),
            "EVENTS": len(base_history),
            "FULL_DIGEST": full_before,
            "BOUNDS_DIGEST": bounds_before,
            "EVENT_HISTORY_SHA256": event_prefix_digest,
        },
        "FROZEN": {
            "HEAD": base_r2.FROZEN_HEAD,
            "TREE": base_r2.FROZEN_TREE,
            "RESULT_SHA256": base_r2.FROZEN_RESULT_SHA256,
        },
        "ROWS_BEFORE": len(base_rows),
        "ROWS_AFTER": len(after_rows),
        "EVENTS_BEFORE": len(base_history),
        "EVENTS_AFTER": len(events),
        "ADDED_EVENTS": len(new_events),
        "EVENT_PREFIX_PARITY": "EXACT",
        "EVENT_PREFIX_SHA256": candidate_prefix_digest,
        "CHANGED_ROWS": len(changed_ids),
        "UNCHANGED_ROWS": len(base_rows) - len(changed_ids),
        "BEFORE_STATE_MISMATCH": 0,
        "UNRELATED_ROW_MUTATION": 0,
        "PROFILES": profile_results,
        "EVENT_TRANSITIONS": transitions,
        "CLASS": class_info,
        "CLASS_VALIDATION_SCOPE": (
            "PINNED_197_PROFILE_ID_SET_AND_BOUND_REVALIDATED;"
            "CLASS_IDS_ARE_OUTSIDE_THE_RESOLVED_4647_ROW_LEDGER"
        ),
        "CLASS_COUNT": EXPECTED_CLASS_COUNT,
        "CLASS_BOUND": class_bound,
        "CLASS_ID_SET_SHA256": EXPECTED_CLASS_ID_SET_SHA256,
        "CLASS_MUTATIONS": class_mutations,
        "FAMILY_BEFORE": family_before["FAMILY_BOUND"],
        "FAMILY_AFTER": family_after["FAMILY_BOUND"],
        "FAMILY_GAIN": family_gain,
        "MAX_OWNER": family_after["MAX_RESOLVED_OWNERS"][0],
        "MAX_RESOLVED_BOUND": family_after["MAX_RESOLVED_BOUND"],
        "MAX_RESOLVED_OWNERS": family_after["MAX_RESOLVED_OWNERS"],
        "NEXT_DISTINCT_BOUND": family_after["NEXT_DISTINCT_BOUND"],
        "NEXT_DISTINCT_OWNER": family_after["NEXT_DISTINCT_OWNERS"][0],
        "NEXT_DISTINCT_OWNERS": family_after["NEXT_DISTINCT_OWNERS"],
        "FULL_DIGEST": full_after,
        "BOUNDS_DIGEST": bounds_after,
        "MATH_PROVENANCE_STATUS": MATH_PROVENANCE_STATUS,
        "MATH_PROVENANCE": MATH_PROVENANCE,
        "EVENT_SOURCE_EVIDENCE": {
            "DONOR_BASE_HEAD": DONOR_BASE_HEAD,
            "DONOR_SOURCE_SHA256": DONOR_SOURCE_SHA256,
            "DONOR_RESULT_SHA256": DONOR_RESULT_SHA256,
            "DONOR_USED_AS_RUNTIME_IMPORT": False,
            "VIRTUAL_CATALOG_LOCATORS_TREATED_AS_ARRAYS": False,
        },
        "NEGATIVE_CASE_RESULTS": negative,
        "EVENT_HISTORY": events,
        "SOURCE_SHA256": source_sha256,
        "TEST_SHA256": test_sha256,
        "PUSH": "NOT_RUN",
        "PR": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
        "FORMAL_FAMILY_AUTHORITY_ADOPTION": "NOT_ACCEPTED",
    }
    encoded_result = serialize_result(result)
    result["NEGATIVE_CASE_RESULTS"] = negative_case_results(
        base_result,
        base_history,
        events,
        base_rows,
        after_rows,
        profile_results,
        class_info,
        family_before,
        family_after,
        MATH_PROVENANCE,
        encoded_result,
    )
    require(
        all(
            value.startswith("REJECTED:")
            for value in result["NEGATIVE_CASE_RESULTS"].values()
        ),
        "REQUIRED_NEGATIVE_CONTROL_ACCEPTED",
    )
    require(
        serialize_result(result) == encoded_result,
        "NEGATIVE_CONTROL_RESULT_SERIALIZATION_CHANGED",
    )
    return result, base_rows, after_rows


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
                "FAMILY_BEFORE": result["FAMILY_BEFORE"],
                "FAMILY_AFTER": result["FAMILY_AFTER"],
                "FAMILY_GAIN": result["FAMILY_GAIN"],
                "FULL_DIGEST": result["FULL_DIGEST"],
                "BOUNDS_DIGEST": result["BOUNDS_DIGEST"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
