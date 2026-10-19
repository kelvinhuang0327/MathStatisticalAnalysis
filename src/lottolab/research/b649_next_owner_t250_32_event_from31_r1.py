"""Integrate one owner-provided T250 proof into the fixed 31-event B649 ledger."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from . import b649_existing_four_owner_local_authority_r1 as four
from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32
from . import b649_nine_event_eight_profile_local_authority_r1 as nine
from . import b649_sixteen_event_frozen_lineage_local_authority_r1 as sixteen
from . import b649_triple_t262_31_event_family_integration_r1 as lineage

TASK_ID = "B649_NEXT_OWNER_T250_32_EVENT_FROM31_FAMILY_INTEGRATION_R1"
ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = (
    "src/lottolab/research/"
    "b649_next_owner_t250_32_event_from31_r1.py"
)
TEST_PATH = "tests/unit/test_b649_next_owner_t250_32_event_from31_r1.py"
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-next-owner-t250-32-event-from31-r1-result.json"
)
TARGET_PATHS = tuple(sorted((SOURCE_PATH, TEST_PATH, RESULT_PATH)))

BASE_HEAD = "88a37370e6db035d6155190723de8cea646e76b7"
BASE_TREE = "4fede8e927eab43d58b906ce80e7eea10300b4a0"
BASE_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-triple-t262-31-event-family-integration-r1-result.json"
)
BASE_RESULT_SHA256 = "802cb12eb1b737450c707d55386382e90689a3ff1574b84aa0a7365bb975497d"
BASE_ROWS = 4_647
BASE_EVENTS = 31
BASE_FULL_DIGEST = "a92e08b279b0fb80098f10d461dd3399e86712b6ffe14968851fa175d0356091"
BASE_BOUNDS_DIGEST = "f153977eb639f329bad84743498f475e1091cc883e2ae927445bf0a9f348170e"

PROFILE_ID = "66665555555321100000"
OLD_CAP = 264
NEW_CAP = 250
OLD_BOUND = 313_391_636
NEW_BOUND = 313_266_168
ROW_DELTA = 125_468
S4_BASE = 112
EVENT_ID = "T250_66665555555321100000"
CLASS_COUNT = 197
CLASS_BOUND = 313_258_872
CLASS_ID_SET_SHA256 = "1fd8ef4779e3967b75cbeaa2ca65de9afc2551d27ae7e98daa1e3f700fc24e8b"
EXPECTED_FAMILY_BOUND = 313_391_740
EXPECTED_MAXIMIZING_OWNERS = [
    "66655555555331100000",
    "66655555555411110000",
]
EXPECTED_OLD_ROUTE_TERMS = 243
EXPECTED_NEW_ROUTE_TERMS = 229
EXPECTED_OLD_ARGMAX = [264, 313_391_636, 492, 199, 288_099, 5_166_224]
EXPECTED_NEW_ARGMAX = [250, 313_266_168, 387, 199, 216_804, 5_000_016]
EXPECTED_STRUCTURE = {"W": 830, "U": 2_345, "TOP": 12, "A_MAX": 199}

SCIENCE_PROVENANCE: dict[str, Any] = {
    "TASK_ID": "B649_NEXT_OWNER_666655555553211_T250_FRESH_MATH_JUDGE_R1",
    "SESSION_ID": "01a152c5-acb6-7553-ab32-95d042abd243",
    "VERDICT": "VERIFIED_WITH_CAVEATS",
    "PROOF_SCOPE": "FULL_PROFILE",
    "EVIDENCE_KIND": "TRANSCRIPT_ONLY",
    "EXACT_MAX_T": 250,
    "NEW_BOUND": NEW_BOUND,
    "ROUTE_B_TERMS": 472,
    "TERM_MISMATCH": 0,
}
SCIENCE_ROW_SOURCE = (
    "OWNER_TRANSCRIPT_ONLY"
    "|TASK_ID=B649_NEXT_OWNER_666655555553211_T250_FRESH_MATH_JUDGE_R1"
    "|SESSION_ID=01a152c5-acb6-7553-ab32-95d042abd243"
    "|VERDICT=VERIFIED_WITH_CAVEATS|PROOF_SCOPE=FULL_PROFILE"
    "|EXACT_MAX_T=250|NEW_BOUND=313266168|ROUTE_B_TERMS=472"
    "|TERM_MISMATCH=0"
)

EXPECTED_DIRECT_IMPORTS = frozenset(
    {
        "b649_existing_four_owner_local_authority_r1",
        "b649_k20_min_s2_route_b_current_owner_refinement_r32",
        "b649_nine_event_eight_profile_local_authority_r1",
        "b649_sixteen_event_frozen_lineage_local_authority_r1",
        "b649_triple_t262_31_event_family_integration_r1",
    }
)
FORBIDDEN_CROSS_LINEAGE = (
    "b649_next_triple_resolved_frontier_math_r1",
    "B649_NEXT_TRIPLE_RESOLVED_FRONTIER_MATH_R1",
)

Row = four.Row


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def serialize_result(result: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def validate_base_identity(head: str, tree: str, result_sha256: str) -> None:
    require(head == BASE_HEAD, "fixed Base HEAD mismatch")
    require(tree == BASE_TREE, "fixed Base TREE mismatch")
    require(
        result_sha256 == BASE_RESULT_SHA256,
        "fixed Base result SHA256 mismatch",
    )


def validate_profile_id(profile_id: str) -> None:
    require(profile_id == PROFILE_ID, "wrong target Profile")


def validate_supported_cap(cap: int) -> None:
    require(cap in {OLD_CAP, NEW_CAP}, f"unsupported cap: {cap}")


def validate_transition(old: Row, new: Row, profile_id: str) -> None:
    validate_profile_id(profile_id)
    require(
        (old.cap, old.bound) == (OLD_CAP, OLD_BOUND),
        "old cap/bound does not match the fixed 31-event row",
    )
    validate_supported_cap(new.cap)
    require(
        (new.cap, new.bound, new.s4_base)
        == (NEW_CAP, NEW_BOUND, S4_BASE),
        "new cap/bound/S4 base mismatch",
    )
    require(
        old.bound - new.bound == ROW_DELTA,
        "row delta mismatch",
    )
    require(
        new.source == SCIENCE_ROW_SOURCE,
        "new row is missing the exact Owner-supplied science provenance",
    )


def validate_science_provenance(value: Mapping[str, Any]) -> None:
    for key, expected in SCIENCE_PROVENANCE.items():
        require(value.get(key) == expected, f"science provenance mismatch: {key}")
    require(
        "REPORT_PATH" not in value and "REPORT_SHA256" not in value,
        "transcript-only evidence cannot claim a local Judge report",
    )


def validate_structure(
    actual: Mapping[str, int], expected: Mapping[str, int] = EXPECTED_STRUCTURE
) -> None:
    for key, expected_value in expected.items():
        require(
            actual.get(key) == expected_value,
            f"R32 structural value mismatch: {key}",
        )


def route_summary(profile: tuple[int, ...], cap: int, s4_base: int) -> dict[str, Any]:
    validate_supported_cap(cap)
    terms = r32.route_b_envelope(profile, cap, s4_base)
    require(bool(terms), "R32 returned no Route-B terms")
    bound = max(term[1] for term in terms)
    max_t = max(term[0] for term in terms if term[1] == bound)
    argmax = next(term for term in terms if term[0] == max_t)
    wedges, choose3, top = r32.k4_premises(profile)
    structure = {
        "W": wedges,
        "U": choose3,
        "TOP": top,
        "A_MAX": r32.contained_triple_k4_cap(profile),
    }
    return {
        "TERM_COUNT": len(terms),
        "BOUND": bound,
        "ARGMAX": list(argmax),
        "STRUCTURE": structure,
    }


def validate_route_summary(
    actual: Mapping[str, Any],
    *,
    expected_terms: int,
    expected_bound: int,
    expected_argmax: Sequence[int],
) -> None:
    require(
        actual.get("TERM_COUNT") == expected_terms,
        "R32 Route-B term count mismatch",
    )
    require(actual.get("BOUND") == expected_bound, "R32 Route-B bound mismatch")
    require(
        actual.get("ARGMAX") == list(expected_argmax),
        "R32 Route-B argmax mismatch",
    )
    structure = actual.get("STRUCTURE")
    require(isinstance(structure, Mapping), "R32 structural values are missing")
    validate_structure(cast(Mapping[str, int], structure))


def validate_event_append(
    before: Sequence[Mapping[str, Any]],
    after: Sequence[Mapping[str, Any]],
    expected_event_id: str,
) -> None:
    sixteen.verify_unique_events(after)
    require(len(before) == BASE_EVENTS, "31-event prefix is missing or malformed")
    require(
        len(after) == BASE_EVENTS + 1,
        "candidate must append exactly one event",
    )
    require(list(after[:BASE_EVENTS]) == list(before), "event prefix parity mismatch")
    appended = list(after[BASE_EVENTS:])
    require(
        len(appended) == 1 and appended[0].get("EVENT_ID") == expected_event_id,
        "candidate appended the wrong event",
    )


def validate_changed_paths(paths: Sequence[str]) -> None:
    require(
        tuple(sorted(paths)) == TARGET_PATHS,
        "committed paths must be exactly the three authorized new files",
    )


def validate_commit_identity(
    parent_ids: Sequence[str], committed_paths: Sequence[str]
) -> None:
    require(
        list(parent_ids) == [BASE_HEAD],
        "candidate commit parent must be the fixed Base HEAD",
    )
    validate_changed_paths(committed_paths)


def validate_dirty_paths(paths: Sequence[str], allowed_paths: Sequence[str]) -> None:
    require(
        tuple(sorted(paths)) == tuple(sorted(allowed_paths)),
        "unexpected dirty path or missing authorized artifact",
    )


def validate_class_state(
    before_rows: Mapping[str, Row],
    after_rows: Mapping[str, Row],
    profile_ids: Sequence[str],
    id_set_sha256: str,
    class_authority: Mapping[str, Any],
) -> dict[str, Any]:
    require(len(profile_ids) == CLASS_COUNT, "Class count mismatch")
    require(
        len(set(profile_ids)) == CLASS_COUNT,
        "Class contains duplicate Profile IDs",
    )
    require(
        sha256(json.dumps(list(profile_ids)).encode("utf-8"))
        == CLASS_ID_SET_SHA256,
        "Class Profile ID set digest mismatch",
    )
    require(
        id_set_sha256 == CLASS_ID_SET_SHA256,
        "Class authority ID set digest mismatch",
    )
    cursor_id = lineage.CLASS_CURSOR_ID
    require(
        profile_ids.count(cursor_id) == 1,
        "Class must contain its one synthetic cursor Profile",
    )
    require(
        PROFILE_ID not in profile_ids,
        "target row overlaps the unchanged Class",
    )
    represented_ids = [profile_id for profile_id in profile_ids if profile_id in before_rows]
    require(
        all(profile_id in after_rows for profile_id in represented_ids),
        "represented Class Profile disappeared from the candidate ledger",
    )
    require(
        all(before_rows[profile_id] == after_rows[profile_id] for profile_id in represented_ids),
        "Class row mutation detected",
    )
    bound_before = class_authority.get("BOUND_BEFORE")
    bound_after = class_authority.get("BOUND_AFTER")
    bound_delta = class_authority.get("BOUND_DELTA")
    resolved_row_events = class_authority.get("RESOLVED_ROW_EVENTS")
    require(
        (bound_before, bound_after, bound_delta, resolved_row_events)
        == (CLASS_BOUND, CLASS_BOUND, 0, 0),
        "Class bound mismatch",
    )
    return {
        "COUNT": CLASS_COUNT,
        "BOUND_BEFORE": bound_before,
        "BOUND_AFTER": bound_after,
        "BOUND_DELTA": bound_delta,
        "ID_SET_SHA256": CLASS_ID_SET_SHA256,
        "RESOLVED_ROW_EVENTS": resolved_row_events,
        "CLASS_MUTATIONS": 0,
    }


def validate_family_state(
    actual: Mapping[str, Any],
    expected_bound: int,
    expected_owners: Sequence[str],
) -> None:
    require(
        actual.get("FAMILY_BOUND") == expected_bound,
        "Family bound mismatch",
    )
    require(
        actual.get("MAXIMIZING_OWNERS") == list(expected_owners),
        "Family maximizing owners mismatch",
    )


def source_direct_imports(source_text: str) -> list[str]:
    tree = ast.parse(source_text)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
            names.extend(alias.name for alias in node.names)
    return names


def validate_direct_imports(names: Sequence[str]) -> None:
    supplied = frozenset(names)
    unexpected = sorted(supplied - EXPECTED_DIRECT_IMPORTS)
    missing = sorted(EXPECTED_DIRECT_IMPORTS - supplied)
    require(
        not unexpected,
        f"cross-lineage or unpinned direct import: {', '.join(unexpected)}",
    )
    require(not missing, f"required native imports are missing: {', '.join(missing)}")


def source_closure(root: Path) -> list[dict[str, str]]:
    closure: dict[str, str] = {}
    research_root = (root / "src/lottolab/research").resolve()
    for module_name, module in sorted(sys.modules.items()):
        if not module_name.startswith("lottolab.research."):
            continue
        if any(token in module_name for token in FORBIDDEN_CROSS_LINEAGE):
            raise ValueError(f"cross-lineage module loaded: {module_name}")
        filename = getattr(module, "__file__", None)
        if not isinstance(filename, str) or not filename.endswith(".py"):
            continue
        path = Path(filename).resolve()
        if not path.is_relative_to(research_root):
            continue
        relative = path.relative_to(root).as_posix()
        if relative == SOURCE_PATH:
            continue
        base_bytes = four.committed_blob(root, BASE_HEAD, relative)
        require(
            path.read_bytes() == base_bytes,
            f"imported source differs from fixed Base: {relative}",
        )
        closure[relative] = sha256(base_bytes)

    direct_modules: tuple[ModuleType, ...] = (
        four,
        r32,
        nine,
        sixteen,
        lineage,
    )
    required_paths = {
        Path(module.__file__).resolve().relative_to(root).as_posix()
        for module in direct_modules
    }
    require(
        required_paths.issubset(closure),
        "native source closure omits a direct dependency",
    )
    return [
        {"PATH": path, "SHA256": closure[path]}
        for path in sorted(closure)
    ]


def git_text(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def current_dirty_paths(root: Path) -> list[str]:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "core.fsmonitor=false",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    paths: list[str] = []
    for line in completed.stdout.splitlines():
        require(len(line) >= 4, "malformed Git porcelain status")
        paths.append(line[3:])
    return sorted(paths)


def verify_current_worktree() -> None:
    root = ROOT.resolve()
    require(
        Path(git_text(root, "rev-parse", "--show-toplevel")).resolve() == root,
        "wrong repository/worktree root",
    )
    require(
        git_text(root, "branch", "--show-current")
        == "codex/b649-next-owner-t250-32-event-from31-r1",
        "wrong candidate branch",
    )
    head = git_text(root, "rev-parse", "HEAD")
    tree = git_text(root, "rev-parse", "HEAD^{tree}")
    status_paths = current_dirty_paths(root)

    if head == BASE_HEAD:
        require(tree == BASE_TREE, "wrong Base tree before commit")
        validate_dirty_paths(status_paths, TARGET_PATHS)
        return

    parent_line = git_text(root, "rev-list", "--parents", "-n", "1", "HEAD")
    parent_fields = parent_line.split()
    require(parent_fields[0] == head, "malformed candidate parent record")
    committed_paths = git_text(
        root, "diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", "HEAD"
    ).splitlines()
    validate_commit_identity(parent_fields[1:], committed_paths)
    validate_dirty_paths(status_paths, [])


def load_and_replay_base() -> tuple[dict[str, Any], dict[str, Row]]:
    four.verify_commit(ROOT, BASE_HEAD, BASE_TREE)
    base_raw = four.committed_blob(ROOT, BASE_HEAD, BASE_RESULT_PATH)
    validate_base_identity(
        BASE_HEAD,
        BASE_TREE,
        sha256(base_raw),
    )
    base_result = four.json_object(base_raw, "fixed Base result is not valid JSON")
    require(
        base_result.get("TASK_ID") == lineage.TASK_ID,
        "fixed Base result task identity mismatch",
    )
    require(
        (
            base_result.get("ROWS_BEFORE"),
            base_result.get("ROWS_AFTER"),
            base_result.get("EVENTS_BEFORE"),
            base_result.get("EVENTS_AFTER"),
        )
        == (BASE_ROWS, BASE_ROWS, 28, BASE_EVENTS),
        "fixed Base row/event counts mismatch",
    )
    history_value = base_result.get("EVENT_HISTORY")
    require(
        isinstance(history_value, list),
        "fixed Base event history is incomplete",
    )
    history = cast(list[dict[str, Any]], history_value)
    require(
        len(history) == BASE_EVENTS,
        "fixed Base event history is incomplete",
    )
    sixteen.verify_unique_events(history)

    four.verify_commit(ROOT, four.FROZEN_HEAD, four.FROZEN_TREE)
    frozen_raw = four.committed_blob(
        ROOT, four.FROZEN_HEAD, four.FROZEN_RESULT_PATH
    )
    require(
        sha256(frozen_raw) == four.FROZEN_RESULT_SHA256,
        "native frozen ledger result SHA256 mismatch",
    )
    frozen = four.json_object(frozen_raw, "native frozen ledger result is invalid JSON")
    frozen_rows = four.load_frozen_seven_row_ledger(frozen)
    require(len(frozen_rows) == BASE_ROWS, "native frozen loader row count mismatch")

    replayed = dict(frozen_rows)
    for event in history:
        profile_id = event.get("PROFILE_ID")
        if not isinstance(profile_id, str) or profile_id not in replayed:
            raise ValueError("event references an unknown Profile")
        old = replayed[profile_id]
        before = (
            event.get("BOUND_BEFORE"),
            event.get("CAP_BEFORE"),
            event.get("S4_BASE_BEFORE"),
            event.get("SOURCE_BEFORE"),
        )
        require(
            before == (old.bound, old.cap, old.s4_base, old.source),
            f"event before-state mismatch: {event.get('EVENT_ID')}",
        )
        bound_after = event.get("BOUND_AFTER")
        cap_after = event.get("CAP_AFTER")
        s4_base_after = event.get("S4_BASE_AFTER")
        source_after = event.get("SOURCE_AFTER")
        require(
            type(bound_after) is int
            and type(cap_after) is int
            and type(s4_base_after) is int
            and isinstance(source_after, str),
            "event after-state has an invalid schema",
        )
        replayed[profile_id] = replace(
            old,
            bound=bound_after,
            cap=cap_after,
            s4_base=s4_base_after,
            source=source_after,
        )

    prior_changed = base_result.get("CHANGED_PROFILE_IDS_FROM_FROZEN")
    require(isinstance(prior_changed, list), "fixed Base changed-Profile ledger is missing")
    sixteen.verify_ledger_partition(
        frozen_rows,
        replayed,
        set(cast(list[str], prior_changed)),
    )
    full_digest = four.seven.two.full_digest(replayed)
    bounds_digest = four.seven.two.bounds_digest(replayed)
    require(len(replayed) == BASE_ROWS, "fixed Base replay row count mismatch")
    require(
        (full_digest, bounds_digest)
        == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "fixed Base full/bounds digest replay mismatch",
    )
    require(
        (base_result.get("FULL_DIGEST"), base_result.get("BOUNDS_DIGEST"))
        == (full_digest, bounds_digest),
        "fixed Base result digest fields mismatch",
    )
    return base_result, replayed


def expect_rejected(action: Callable[[], object]) -> str:
    try:
        action()
    except (AssertionError, IndexError, KeyError, TypeError, ValueError) as exc:
        return f"REJECTED: {type(exc).__name__}: {exc}"
    raise AssertionError("negative control was unexpectedly accepted")


def negative_control_results(
    base_result: Mapping[str, Any],
    before_rows: Mapping[str, Row],
    after_rows: Mapping[str, Row],
    event_history_before: Sequence[Mapping[str, Any]],
    event_history_after: Sequence[Mapping[str, Any]],
    structure: Mapping[str, int],
    class_record: Mapping[str, Any],
    family_record: Mapping[str, Any],
    new_row: Row,
) -> dict[str, str]:
    event_id = event_history_after[-1].get("EVENT_ID")
    unrelated_id = next(
        profile_id for profile_id in sorted(after_rows) if profile_id != PROFILE_ID
    )
    unrelated_rows = dict(after_rows)
    unrelated_rows[unrelated_id] = replace(
        unrelated_rows[unrelated_id],
        bound=unrelated_rows[unrelated_id].bound + 1,
    )
    class_ids = cast(list[str], class_record["PROFILE_IDS"])
    family_owners = cast(list[str], family_record["MAXIMIZING_OWNERS"])
    wrong_structure = dict(structure)
    wrong_structure["W"] += 1
    wrong_u = dict(structure)
    wrong_u["U"] += 1
    wrong_a_max = dict(structure)
    wrong_a_max["A_MAX"] += 1
    history = cast(list[dict[str, Any]], base_result["EVENT_HISTORY"])

    return {
        "WRONG_BASE_HEAD": expect_rejected(
            lambda: validate_base_identity("0" * 40, BASE_TREE, BASE_RESULT_SHA256)
        ),
        "WRONG_BASE_TREE": expect_rejected(
            lambda: validate_base_identity(BASE_HEAD, "0" * 40, BASE_RESULT_SHA256)
        ),
        "WRONG_BASE_RESULT_SHA": expect_rejected(
            lambda: validate_base_identity(BASE_HEAD, BASE_TREE, "0" * 64)
        ),
        "WRONG_PROFILE": expect_rejected(
            lambda: validate_profile_id("0" * len(PROFILE_ID))
        ),
        "WRONG_OLD_CAP": expect_rejected(
            lambda: validate_transition(
                replace(before_rows[PROFILE_ID], cap=OLD_CAP - 1),
                new_row,
                PROFILE_ID,
            )
        ),
        "UNSUPPORTED_CAP_249": expect_rejected(lambda: validate_supported_cap(249)),
        "WRONG_NEW_BOUND": expect_rejected(
            lambda: validate_transition(
                before_rows[PROFILE_ID],
                replace(new_row, bound=NEW_BOUND + 1),
                PROFILE_ID,
            )
        ),
        "WRONG_W": expect_rejected(
            lambda: validate_structure(wrong_structure)
        ),
        "WRONG_U": expect_rejected(lambda: validate_structure(wrong_u)),
        "WRONG_A_MAX": expect_rejected(lambda: validate_structure(wrong_a_max)),
        "MISSING_EVENT": expect_rejected(
            lambda: validate_event_append(history, history, cast(str, event_id))
        ),
        "DUPLICATE_EVENT": expect_rejected(
            lambda: validate_event_append(
                history,
                [*event_history_after, event_history_after[-1]],
                cast(str, event_id),
            )
        ),
        "UNRELATED_ROW_MUTATION": expect_rejected(
            lambda: sixteen.verify_ledger_partition(
                before_rows, unrelated_rows, {PROFILE_ID}
            )
        ),
        "WRONG_CLASS": expect_rejected(
            lambda: validate_class_state(
                before_rows,
                after_rows,
                class_ids,
                "0" * 64,
                class_record,
            )
        ),
        "WRONG_FAMILY": expect_rejected(
            lambda: validate_family_state(
                {**family_record, "FAMILY_BOUND": EXPECTED_FAMILY_BOUND + 1},
                EXPECTED_FAMILY_BOUND,
                family_owners,
            )
        ),
        "MISSING_JUDGE_PROVENANCE": expect_rejected(
            lambda: validate_science_provenance({})
        ),
        "CROSS_LINEAGE_IMPORT": expect_rejected(
            lambda: validate_direct_imports(
                [*sorted(EXPECTED_DIRECT_IMPORTS), FORBIDDEN_CROSS_LINEAGE[0]]
            )
        ),
        "WRONG_PARENT": expect_rejected(
            lambda: validate_commit_identity(["0" * 40], TARGET_PATHS)
        ),
        "WRONG_COMMITTED_PATHS": expect_rejected(
            lambda: validate_commit_identity(
                [BASE_HEAD],
                [SOURCE_PATH, TEST_PATH, "docs/research/not-authorized.json"],
            )
        ),
        "UNEXPECTED_DIRTY_PATH": expect_rejected(
            lambda: validate_dirty_paths(
                [*TARGET_PATHS[:2], "src/lottolab/unrelated.py"],
                TARGET_PATHS,
            )
        ),
    }


def build_candidate() -> tuple[dict[str, Any], dict[str, Row], dict[str, Row]]:
    source_text = Path(__file__).read_text(encoding="utf-8")
    validate_direct_imports(source_direct_imports(source_text))
    validate_science_provenance(SCIENCE_PROVENANCE)

    base_result, before_rows = load_and_replay_base()
    validate_profile_id(PROFILE_ID)
    old_row = before_rows[PROFILE_ID]
    profile = r32.decode_profile(PROFILE_ID)
    require(r32.profile_id(profile) == PROFILE_ID, "R32 Profile decoding mismatch")

    old_route = route_summary(profile, old_row.cap, old_row.s4_base)
    validate_route_summary(
        old_route,
        expected_terms=EXPECTED_OLD_ROUTE_TERMS,
        expected_bound=OLD_BOUND,
        expected_argmax=EXPECTED_OLD_ARGMAX,
    )
    validate_structure(cast(Mapping[str, int], old_route["STRUCTURE"]))

    new_route = route_summary(profile, NEW_CAP, old_row.s4_base)
    validate_route_summary(
        new_route,
        expected_terms=EXPECTED_NEW_ROUTE_TERMS,
        expected_bound=NEW_BOUND,
        expected_argmax=EXPECTED_NEW_ARGMAX,
    )
    validate_structure(cast(Mapping[str, int], new_route["STRUCTURE"]))

    new_row = replace(
        old_row,
        bound=NEW_BOUND,
        cap=NEW_CAP,
        source=SCIENCE_ROW_SOURCE,
    )
    validate_transition(old_row, new_row, PROFILE_ID)

    after_rows = dict(before_rows)
    after_rows[PROFILE_ID] = new_row
    changed = sixteen.verify_ledger_partition(
        before_rows, after_rows, {PROFILE_ID}
    )
    require(changed == {PROFILE_ID}, "target row change partition mismatch")
    changed_rows = len(changed)
    unchanged_rows = len(before_rows) - changed_rows
    require(
        (changed_rows, unchanged_rows) == (1, BASE_ROWS - 1),
        "single-row update count mismatch",
    )

    base_history = cast(list[dict[str, Any]], base_result["EVENT_HISTORY"])
    event = nine.event_from_update(EVENT_ID, PROFILE_ID, old_row, new_row)
    event["DONOR"] = dict(SCIENCE_PROVENANCE)
    event["PROOF_SCOPE"] = "FULL_PROFILE"
    event["PROOF_EVIDENCE_KIND"] = "TRANSCRIPT_ONLY"
    history_after = [*base_history, event]
    validate_event_append(base_history, history_after, EVENT_ID)

    family_before = lineage.family_summary(before_rows, CLASS_BOUND)
    family_after = lineage.family_summary(after_rows, CLASS_BOUND)
    base_owners = cast(list[str], base_result["MAX_RESOLVED_OWNERS"])
    validate_family_state(
        family_before, EXPECTED_FAMILY_BOUND, base_owners
    )
    validate_family_state(
        family_after, EXPECTED_FAMILY_BOUND, base_owners
    )
    family_gain = int(family_before["FAMILY_BOUND"]) - int(
        family_after["FAMILY_BOUND"]
    )
    require(family_gain == 0, "Family gain must be computed from the full Family frontier")

    class_before = cast(dict[str, Any], base_result["CLASS"])
    class_profile_ids = cast(list[str], class_before["PROFILE_IDS"])
    class_record = validate_class_state(
        before_rows,
        after_rows,
        class_profile_ids,
        cast(str, class_before["ID_SET_SHA256"]),
        class_before,
    )

    full_digest = four.seven.two.full_digest(after_rows)
    bounds_digest = four.seven.two.bounds_digest(after_rows)
    require(full_digest != BASE_FULL_DIGEST, "updated full digest did not change")
    require(bounds_digest != BASE_BOUNDS_DIGEST, "updated bounds digest did not change")

    structure = cast(dict[str, int], new_route["STRUCTURE"])
    negative = negative_control_results(
        base_result,
        before_rows,
        after_rows,
        base_history,
        history_after,
        structure,
        class_before,
        family_after,
        new_row,
    )
    require(
        all(value.startswith("REJECTED: ") for value in negative.values()),
        "a required negative control was accepted",
    )

    closure = source_closure(ROOT)
    source_sha256 = sha256((ROOT / SOURCE_PATH).read_bytes())
    test_sha256 = sha256((ROOT / TEST_PATH).read_bytes())
    row_delta = old_row.bound - new_row.bound
    require(row_delta == ROW_DELTA, "target row delta mismatch")
    term_mismatches = int(
        new_route["BOUND"] != SCIENCE_PROVENANCE["NEW_BOUND"]
        or new_route["ARGMAX"] != EXPECTED_NEW_ARGMAX
    )
    require(term_mismatches == 0, "R32 terms differ from Owner-provided exact proof")

    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_32_EVENT_FAMILY_CANDIDATE",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FORMAL_FAMILY_AUTHORITY": "NOT_ACCEPTED",
        "BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "RESULT_PATH": BASE_RESULT_PATH,
            "RESULT_SHA256": BASE_RESULT_SHA256,
            "ROWS": BASE_ROWS,
            "EVENTS": BASE_EVENTS,
            "FULL_DIGEST": BASE_FULL_DIGEST,
            "BOUNDS_DIGEST": BASE_BOUNDS_DIGEST,
        },
        "ROWS_BEFORE": len(before_rows),
        "ROWS_AFTER": len(after_rows),
        "EVENTS_BEFORE": len(base_history),
        "EVENTS_AFTER": len(history_after),
        "EVENT_PREFIX_PARITY": "EXACT",
        "NEW_EVENT_ID": EVENT_ID,
        "NEW_EVENT_COUNT": 1,
        "DUPLICATE_EVENTS": 0,
        "EVENT_HISTORY": history_after,
        "PROFILE": {
            "PROFILE_ID": PROFILE_ID,
            "OLD_CAP": old_row.cap,
            "NEW_CAP": new_row.cap,
            "OLD_BOUND": old_row.bound,
            "NEW_BOUND": new_row.bound,
            "ROW_DELTA": row_delta,
            "CHANGED_ROWS": changed_rows,
            "UNCHANGED_ROWS": unchanged_rows,
            "OLD_SOURCE": old_row.source,
            "NEW_SOURCE": new_row.source,
            "BEFORE_STATE_MISMATCH": 0,
        },
        "ROUTE_B": {
            "OLD_TERMS": old_route["TERM_COUNT"],
            "NEW_TERMS": new_route["TERM_COUNT"],
            "OLD_BOUND": old_route["BOUND"],
            "NEW_BOUND": new_route["BOUND"],
            "OLD_ARGMAX": old_route["ARGMAX"],
            "NEW_ARGMAX": new_route["ARGMAX"],
            "TERM_MISMATCH_COUNT": term_mismatches,
            "STRUCTURE": structure,
        },
        "SCIENCE_PROVENANCE": dict(SCIENCE_PROVENANCE),
        "CLASS": {
            **class_record,
            "PROFILE_IDS": class_profile_ids,
        },
        "FAMILY_BEFORE": family_before["FAMILY_BOUND"],
        "FAMILY_AFTER": family_after["FAMILY_BOUND"],
        "FAMILY_GAIN": family_gain,
        "ALL_MAXIMIZING_OWNERS": family_after["MAXIMIZING_OWNERS"],
        "NEXT_DISTINCT_BOUND": family_after["NEXT_DISTINCT_BOUND"],
        "NEXT_DISTINCT_OWNERS": family_after["NEXT_DISTINCT_OWNERS"],
        "FAMILY_FRONTIER_BEFORE": family_before,
        "FAMILY_FRONTIER_AFTER": family_after,
        "FULL_DIGEST": full_digest,
        "BOUNDS_DIGEST": bounds_digest,
        "NEGATIVE_CONTROL_RESULTS": negative,
        "SOURCE_CLOSURE_STATUS": "PASS",
        "SOURCE_CLOSURE": closure,
        "SOURCE_PATH": SOURCE_PATH,
        "SOURCE_SHA256": source_sha256,
        "TEST_PATH": TEST_PATH,
        "TEST_SHA256": test_sha256,
        "RESULT_PATH": RESULT_PATH,
        "PUBLICATION": {
            "PUSH": "NOT_RUN",
            "PR": "NOT_RUN",
            "MERGE": "NOT_RUN",
        },
    }
    validate_event_append(
        base_history,
        cast(list[Mapping[str, Any]], result["EVENT_HISTORY"]),
        EVENT_ID,
    )
    serialized = serialize_result(result)
    require(
        json.loads(serialized.decode("utf-8")) == result,
        "canonical result serialization is not round-trip stable",
    )
    return result, before_rows, after_rows


def validate_output_file(root: Path, expected: bytes) -> None:
    output_path = root / RESULT_PATH
    require(output_path.is_file(), "canonical result file is missing")
    require(
        output_path.read_bytes() == expected,
        "canonical result bytes do not match the native replay",
    )


def validate_current_worktree() -> None:
    verify_current_worktree()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="replay the fixed Base and verify the saved canonical result",
    )
    args = parser.parse_args()
    result, _before_rows, _after_rows = build_candidate()
    encoded = serialize_result(result)
    output_path = ROOT / RESULT_PATH

    if args.check:
        validate_output_file(ROOT, encoded)
        validate_current_worktree()
        print(
            "PASS: fixed Base replay, canonical bytes, event lineage, "
            "and Git path guard"
        )
        return

    if output_path.exists():
        previous = four.json_object(
            output_path.read_bytes(), "existing result artifact is invalid JSON"
        )
        require(
            previous.get("TASK_ID") == TASK_ID,
            "refusing to overwrite a result artifact owned by another task",
        )
        if output_path.read_bytes() != encoded:
            output_path.write_bytes(encoded)
    else:
        output_path.write_bytes(encoded)
    validate_output_file(ROOT, encoded)
    validate_current_worktree()
    print(f"WROTE: {RESULT_PATH} sha256={sha256(encoded)}")


if __name__ == "__main__":
    main()
