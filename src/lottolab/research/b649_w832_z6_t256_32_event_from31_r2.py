"""Replay the pinned 31-event B649 ledger and apply the judged T256 bound."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, replace
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import Any, cast

from . import b649_triple_t262_31_event_family_integration_r1 as base31

TASK_ID = "B649_W832_Z6_T256_32_EVENT_EXACT_TREE_R2"
ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = "src/lottolab/research/b649_w832_z6_t256_32_event_from31_r2.py"
TEST_PATH = "tests/unit/test_b649_w832_z6_t256_32_event_from31_r2.py"
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-w832-z6-t256-32-event-from31-r2-result.json"
)
COMMITTED_PATHS = tuple(sorted((SOURCE_PATH, TEST_PATH, RESULT_PATH)))
BASE_MODULE_PATH = (
    "src/lottolab/research/b649_triple_t262_31_event_family_integration_r1.py"
)

BASE_HEAD = "88a37370e6db035d6155190723de8cea646e76b7"
BASE_TREE = "4fede8e927eab43d58b906ce80e7eea10300b4a0"
BASE_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-triple-t262-31-event-family-integration-r1-result.json"
)
BASE_RESULT_SHA256 = "802cb12eb1b737450c707d55386382e90689a3ff1574b84aa0a7365bb975497d"
BASE_FULL_DIGEST = "a92e08b279b0fb80098f10d461dd3399e86712b6ffe14968851fa175d0356091"
BASE_BOUNDS_DIGEST = "f153977eb639f329bad84743498f475e1091cc883e2ae927445bf0a9f348170e"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"

PROFILE_ID = "66666555544431000000"
OLD_CAP = 263
NEW_CAP = 256
OLD_BOUND = 313_388_988
NEW_BOUND = 313_326_448
OWNER_DELTA = 62_540
S4_BASE = 112
W_EXPECTED = 832
U_EXPECTED = 2_359
G_MAX_EXPECTED = 12
A_MAX_EXPECTED = 200
EXPECTED_DISTRIBUTION = {"6": 5, "5": 4, "4": 3, "3": 1, "1": 1, "0": 6}
EXPECTED_OLD_ARGMAX = [263, 313_388_988, 483, 200, 281_757, 5_159_952]
EXPECTED_NEW_ARGMAX = [256, 313_326_448, 430, 200, 245_770, 5_076_848]
EXPECTED_CLASS_COUNT = 197
EXPECTED_CLASS_BOUND = 313_258_872
EXPECTED_CLASS_ID_SET_SHA256 = "1fd8ef4779e3967b75cbeaa2ca65de9afc2551d27ae7e98daa1e3f700fc24e8b"
EXPECTED_FAMILY_BOUND = 313_391_740
EXPECTED_MAX_OWNERS = ["66655555555331100000", "66655555555411110000"]
EXPECTED_NEXT_BOUND = 313_391_636
EXPECTED_NEXT_OWNERS = ["66665555555321100000"]

MATH_TASK_ID = "B649_W832_Z6_T258_T256_FRESH_MATH_JUDGE_R1"
SCIENCE_VERDICT = "VERIFIED_WITH_CAVEATS"
PROOF_SCOPE = "FULL_PROFILE"
EVIDENCE_KIND = "TRANSCRIPT_ONLY"
JUDGE_SESSION_1 = "01a14d96-d115-77e3-9ae0-13f254b3f9dd"
JUDGE_SESSION_2 = "7fe2a838-2c06-44a3-a23e-be91c47381ee"
JUDGE_SESSION_2_CONTINUATION = "56b7cb51-5961-4c9c-9f61-9a2314abcf8e"
JUDGE_REPORT_SHA256 = "NOT_APPLICABLE"

ROW_SOURCE_BEFORE = (
    "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[521]"
)
ROW_SOURCE_AFTER = (
    "local:b649-w832-z6-t256-32-event-from31-r2-result.json"
    "#PROFILE=66666555544431000000;PROOF_SCOPE=FULL_PROFILE"
    ";JUDGE_VERDICT=VERIFIED_WITH_CAVEATS;EVIDENCE_KIND=TRANSCRIPT_ONLY"
    ";JUDGE_SESSION_1=01a14d96-d115-77e3-9ae0-13f254b3f9dd"
    ";JUDGE_SESSION_2=7fe2a838-2c06-44a3-a23e-be91c47381ee"
)
EVENT_ID = "T256_66666555544431000000"

LEDGER_ENGINE = base31.base.twenty_seven.four
ROW_ENGINE = LEDGER_ENGINE.seven.two
SPLIT_ENGINE = LEDGER_ENGINE.seven.three.split
R32_ENGINE = LEDGER_ENGINE.seven.three.r32
R5_ENGINE = LEDGER_ENGINE.seven.three.r5
Row = base31.Row


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


def verify_base_identity(head: str, tree: str, result_sha256: str) -> None:
    require((head, tree) == (BASE_HEAD, BASE_TREE), "BASE_HEAD_TREE_MISMATCH")
    require(result_sha256 == BASE_RESULT_SHA256, "BASE_RESULT_SHA256_MISMATCH")


def verify_candidate_ancestry() -> str:
    """Accept Base or one exact-scope child without pinning its future SHA."""
    head = git_text("rev-parse", "HEAD")
    if head == BASE_HEAD:
        require(git_text("rev-parse", "HEAD^{tree}") == BASE_TREE, "BASE_TREE_MISMATCH")
        return head
    parents = git_text("rev-list", "--parents", "-n", "1", head).split()
    validate_candidate_parent(head, parents)
    committed_paths = run_git(
        "diff-tree", "--no-commit-id", "--name-only", "-r", head
    ).decode("utf-8").splitlines()
    validate_committed_paths(committed_paths)
    tree_entries = run_git("ls-tree", head, "--", *COMMITTED_PATHS).decode(
        "utf-8"
    ).splitlines()
    parsed_entries = [
        (metadata.split(), path)
        for line in tree_entries
        if "\t" in line
        for metadata, path in (line.split("\t", maxsplit=1),)
    ]
    require(
        len(parsed_entries) == len(COMMITTED_PATHS)
        and {path for _metadata, path in parsed_entries} == set(COMMITTED_PATHS)
        and all(
            metadata[:2] == ["100644", "blob"]
            for metadata, _path in parsed_entries
        ),
        "COMMITTED_R2_TREE_ENTRIES_MISMATCH",
    )
    for path in COMMITTED_PATHS:
        current = (ROOT / path).read_bytes()
        committed = run_git("show", f"{head}:{path}")
        require(current == committed, f"COMMITTED_CANDIDATE_BYTES_MISMATCH:{path}")
    return head


def verify_source_closure(module_files: Mapping[str, str] | None = None) -> int:
    """Require every loaded LottoLab module to be Base-tracked or this R2 source."""
    if module_files is None:
        loaded = tuple(
            (name, getattr(module, "__file__", None), module)
            for name, module in tuple(sys.modules.items())
        )
    else:
        loaded = tuple((name, file_name, None) for name, file_name in module_files.items())
    root = ROOT.resolve()
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
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(
                f"SOURCE_CLOSURE_MODULE_OUTSIDE_WORKTREE:{module_name}"
            ) from exc
        require(relative.endswith(".py"), f"SOURCE_CLOSURE_MODULE_NOT_PYTHON:{relative}")
        if relative == SOURCE_PATH:
            require(path.is_file(), f"R2_SOURCE_MISSING:{relative}")
            continue
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
        Path(base31.__file__).resolve() == root / BASE_MODULE_PATH,
        "BASE_MODULE_IMPORT_PATH_MISMATCH",
    )
    return verified_base_modules


def validate_frozen_identity(identity: Mapping[str, Any]) -> None:
    require(
        (
            identity.get("HEAD"),
            identity.get("TREE"),
            identity.get("RESULT_SHA256"),
        )
        == (FROZEN_HEAD, FROZEN_TREE, FROZEN_RESULT_SHA256),
        "FROZEN_LEDGER_IDENTITY_MISMATCH",
    )


def apply_event_history(
    initial_rows: Mapping[str, Row], history: Sequence[Mapping[str, Any]]
) -> dict[str, Row]:
    require(len(history) == 31, "EXPECTED_31_BASE_EVENTS")
    rows = dict(initial_rows)
    seen: set[str] = set()
    for event in history:
        event_id = event.get("EVENT_ID")
        profile_id = event.get("PROFILE_ID")
        require(type(event_id) is str and bool(event_id), "EVENT_ID_MISSING")
        event_id_text = cast(str, event_id)
        require(event_id_text not in seen, f"DUPLICATE_EVENT_ID:{event_id_text}")
        seen.add(event_id_text)
        require(
            type(profile_id) is str and bool(profile_id) and profile_id in rows,
            "EVENT_PROFILE_ID_INVALID",
        )
        profile_id_text = cast(str, profile_id)
        row = rows[profile_id_text]
        before = (
            event.get("BOUND_BEFORE"),
            event.get("CAP_BEFORE"),
            event.get("S4_BASE_BEFORE"),
            event.get("SOURCE_BEFORE"),
        )
        actual = (row.bound, row.cap, row.s4_base, row.source)
        require(actual == before, f"EVENT_BEFORE_STATE_MISMATCH:{event_id_text}")
        bound_after = event.get("BOUND_AFTER")
        cap_after = event.get("CAP_AFTER")
        s4_after = event.get("S4_BASE_AFTER")
        source_after = event.get("SOURCE_AFTER")
        require(
            type(bound_after) is int
            and type(cap_after) is int
            and type(s4_after) is int
            and type(source_after) is str,
            f"EVENT_AFTER_STATE_INVALID:{event_id_text}",
        )
        rows[profile_id_text] = replace(
            row,
            bound=cast(int, bound_after),
            cap=cast(int, cap_after),
            s4_base=cast(int, s4_after),
            source=cast(str, source_after),
        )
    return rows


def validate_base_history(
    base_result: Mapping[str, Any], rows: Mapping[str, Row]
) -> list[dict[str, Any]]:
    history_value = base_result.get("EVENT_HISTORY")
    require(type(history_value) is list, "BASE_EVENT_HISTORY_MISSING")
    history = cast(list[dict[str, Any]], history_value)
    require(
        base_result.get("TASK_ID") == base31.TASK_ID
        and base_result.get("ROWS_AFTER") == 4_647
        and base_result.get("EVENTS_AFTER") == 31
        and len(history) == 31,
        "BASE_RESULT_ROWS_OR_EVENTS_MISMATCH",
    )
    full = ROW_ENGINE.full_digest(rows)
    bounds = ROW_ENGINE.bounds_digest(rows)
    require(
        (full, bounds)
        == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST)
        == (base_result.get("FULL_DIGEST"), base_result.get("BOUNDS_DIGEST")),
        "BASE_FULL_OR_BOUNDS_DIGEST_REPLAY_MISMATCH",
    )
    return history


def load_and_replay_base() -> tuple[dict[str, Any], dict[str, Row], bytes]:
    verify_source_closure()
    verify_candidate_ancestry()
    require(git_text("rev-parse", BASE_HEAD) == BASE_HEAD, "BASE_HEAD_UNAVAILABLE")
    require(git_text("rev-parse", f"{BASE_HEAD}^{{tree}}") == BASE_TREE, "BASE_TREE_MISMATCH")
    frozen_result, frozen_identity = LEDGER_ENGINE.verify_frozen_source(ROOT)
    validate_frozen_identity(frozen_identity)
    frozen_rows = LEDGER_ENGINE.load_frozen_seven_row_ledger(frozen_result)
    require(len(frozen_rows) == 4_647, "FROZEN_LOADER_ROW_COUNT_MISMATCH")

    raw = run_git("show", f"{BASE_HEAD}:{BASE_RESULT_PATH}")
    digest = sha256(raw)
    verify_base_identity(BASE_HEAD, BASE_TREE, digest)
    require((ROOT / BASE_RESULT_PATH).read_bytes() == raw, "WORKING_BASE_RESULT_BYTES_MISMATCH")
    base_result = json_object(raw, "BASE_RESULT_INVALID_JSON")
    history_value = base_result.get("EVENT_HISTORY")
    require(type(history_value) is list, "BASE_EVENT_HISTORY_MISSING")
    history = cast(list[dict[str, Any]], history_value)
    base_rows = apply_event_history(frozen_rows, history)
    validate_base_history(base_result, base_rows)
    return base_result, base_rows, raw


def profile_data(profile_id: str) -> tuple[tuple[int, ...], dict[str, int]]:
    profile = cast(tuple[int, ...], SPLIT_ENGINE.profile_values(profile_id))
    distribution = {
        str(degree): count
        for degree, count in sorted(Counter(profile).items(), reverse=True)
    }
    return profile, distribution


def validate_profile_id(profile_id: str) -> None:
    require(profile_id == PROFILE_ID, "TARGET_PROFILE_ID_MISMATCH")


def validate_distribution(distribution: Mapping[str, int]) -> None:
    require(dict(distribution) == EXPECTED_DISTRIBUTION, "TARGET_DEGREE_DISTRIBUTION_MISMATCH")


def validate_wua(w: int, u: int, a_max: int, g_max: int) -> None:
    require(w == W_EXPECTED, "TARGET_W_MISMATCH")
    require(u == U_EXPECTED, "TARGET_U_MISMATCH")
    require(a_max == A_MAX_EXPECTED, "TARGET_A_MAX_MISMATCH")
    require(g_max == G_MAX_EXPECTED, "TARGET_G_MAX_MISMATCH")


def validate_old_row(row: Row) -> None:
    require(
        (row.bound, row.cap, row.s4_base, row.source)
        == (OLD_BOUND, OLD_CAP, S4_BASE, ROW_SOURCE_BEFORE),
        "TARGET_OLD_ROW_IDENTITY_MISMATCH",
    )


def validate_route_binding(
    cap: int, bound: int, argmax_term: Sequence[int], expected_cap: int, expected_bound: int
) -> None:
    require(cap == expected_cap, "ROUTE_B_CAP_MISMATCH")
    require(bound == expected_bound, "ROUTE_B_BOUND_MISMATCH")
    expected_argmax = EXPECTED_OLD_ARGMAX if expected_cap == OLD_CAP else EXPECTED_NEW_ARGMAX
    require(list(argmax_term) == expected_argmax, "ROUTE_B_ARGMAX_MISMATCH")


def floor_four_sevenths(s4: int) -> int:
    require(type(s4) is int and s4 >= 0, "S4_MUST_BE_NONNEGATIVE_INTEGER")
    return (4 * s4) // 7


def validate_s4_rounding_mode(s4: int, mode: str) -> None:
    value = Fraction(4 * s4, 7)
    floor_value = value.numerator // value.denominator
    ceiling_value = -((-value.numerator) // value.denominator)
    require(floor_value != ceiling_value, "S4_ROUNDING_PROBE_NOT_DISCRIMINATING")
    require(mode == "FLOOR", "S4_ROUNDING_MODE_MUST_USE_FLOOR")


def route_certificate(profile_id: str, profile: Sequence[int], cap: int) -> dict[str, Any]:
    route = LEDGER_ENGINE.route_b_envelope(profile_id, cap)
    r32_terms = R32_ENGINE.route_b_envelope(profile, cap, S4_BASE)
    split_terms = SPLIT_ENGINE.route_b_terms(profile, cap, S4_BASE)
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
        "FROZEN_ROUTE_B_TERMS_DIFFER_FROM_R32_AND_SPLIT",
    )

    degrees = [6 + degree for degree in profile]
    w = sum(comb(degree, 2) for degree in degrees)
    u = sum(comb(degree, 3) for degree in degrees)
    g_max = max(degrees)
    a_numerator = sum(
        degree * (g - 2) for degree, g in zip(profile, degrees, strict=True)
    )
    a_max = a_numerator // 3
    validate_wua(w, u, a_max, g_max)
    integer_recount = True
    fraction_recount = True
    for term in terms:
        t, bound, k4, contained, s4, s3 = term
        k4_numerator = u - (g_max - 2) * (w - 3 * t)
        k4_expected = max(0, -((-k4_numerator) // 4))
        contained_expected = min(k4_expected, a_max)
        s4_expected = max(
            S4_BASE, 448 * contained_expected + 679 * (k4_expected - contained_expected)
        )
        s3_expected = 2_800 * w + 11_872 * (t - 22) - 30_800
        bound_floor = 308_390_040 + s3_expected - floor_four_sevenths(s4_expected)
        bound_exact = Fraction(308_390_040 + s3_expected) - Fraction(4 * s4_expected, 7)
        bound_ceiling = -((-bound_exact.numerator) // bound_exact.denominator)
        require(
            (k4, contained, s4, s3) == (
                k4_expected,
                contained_expected,
                s4_expected,
                s3_expected,
            ),
            f"ROUTE_B_INTEGER_RECOUNT_MISMATCH:T={t}",
        )
        require(
            bound == bound_floor == bound_ceiling and 0 <= bound - bound_exact < 1,
            f"ROUTE_B_FRACTION_RECOUNT_MISMATCH:T={t}",
        )
    require(
        route.get("TERM_COUNT") == cap - 21 == len(terms)
        and [term[0] for term in terms] == list(range(22, cap + 1)),
        "ROUTE_B_TERM_DOMAIN_MISMATCH",
    )
    argmax = cast(list[int], route.get("ARGMAX_TERM"))
    bound = cast(int, route.get("BOUND"))
    validate_route_binding(cap, bound, argmax, cap, OLD_BOUND if cap == OLD_CAP else NEW_BOUND)
    return {
        "CAP": cap,
        "DOMAIN": [22, cap],
        "TERM_COUNT": len(terms),
        "BOUND": bound,
        "ARGMAX_TERM": argmax,
        "TERMS": terms,
        "INTEGER_RECOUNT": "PASS" if integer_recount else "FAIL",
        "FRACTION_RECOUNT": "PASS" if fraction_recount else "FAIL",
        "R32_CROSSCHECK": "PASS",
        "TERM_MISMATCH_COUNT": mismatch_count,
        "PROFILE_PARAMETERS": {"W": w, "U": u, "G_MAX": g_max, "A_MAX": a_max, "S4_BASE": S4_BASE},
    }


def math_binding() -> dict[str, Any]:
    return {
        "TASK_ID": MATH_TASK_ID,
        "PROFILE_ID": PROFILE_ID,
        "PROOF_SCOPE": PROOF_SCOPE,
        "STRONGEST_PROVED_CAP": NEW_CAP,
        "VERDICT": SCIENCE_VERDICT,
        "EVIDENCE_KIND": EVIDENCE_KIND,
        "JUDGE_SESSION_1": JUDGE_SESSION_1,
        "JUDGE_SESSION_2": JUDGE_SESSION_2,
        "JUDGE_SESSION_2_CONTINUATION": JUDGE_SESSION_2_CONTINUATION,
        "SESSION_2_CONTINUATION_IS_SAME_JUDGE": True,
        "JUDGE_REPORT_SHA256": JUDGE_REPORT_SHA256,
        "JUDGE_REPORT_SHA256_STATUS": "UNKNOWN",
        "TRANSCRIPT_CONTENT_SHA256": "UNKNOWN",
        "CAP_ATTAINMENT": "UNKNOWN",
        "GLOBAL_OPTIMALITY": "NOT_CLAIMED",
    }


def validate_math_binding(binding: Mapping[str, Any]) -> None:
    require(
        binding.get("TASK_ID") == MATH_TASK_ID
        and binding.get("PROFILE_ID") == PROFILE_ID
        and binding.get("PROOF_SCOPE") == PROOF_SCOPE
        and binding.get("STRONGEST_PROVED_CAP") == NEW_CAP
        and binding.get("VERDICT") == SCIENCE_VERDICT
        and binding.get("EVIDENCE_KIND") == EVIDENCE_KIND
        and binding.get("JUDGE_SESSION_1") == JUDGE_SESSION_1
        and binding.get("JUDGE_SESSION_2") == JUDGE_SESSION_2
        and binding.get("JUDGE_SESSION_2_CONTINUATION") == JUDGE_SESSION_2_CONTINUATION
        and binding.get("SESSION_2_CONTINUATION_IS_SAME_JUDGE") is True
        and binding.get("JUDGE_REPORT_SHA256") == JUDGE_REPORT_SHA256
        and binding.get("JUDGE_REPORT_SHA256_STATUS") == "UNKNOWN",
        "SCIENCE_JUDGE_PROVENANCE_MISSING_OR_MISMATCHED",
    )


def validate_event_history(history: Sequence[Mapping[str, Any]], expected_count: int) -> None:
    event_ids: list[str] = []
    for event in history:
        event_id = event.get("EVENT_ID")
        require(type(event_id) is str and bool(event_id), "EVENT_ID_MISSING")
        event_ids.append(cast(str, event_id))
    require(len(event_ids) == len(set(event_ids)), "DUPLICATE_EVENT_ID")
    require(len(history) == expected_count, f"EVENT_COUNT_MISMATCH:EXPECTED_{expected_count}")


def validate_ledger_partition(
    before_rows: Mapping[str, Row], after_rows: Mapping[str, Row]
) -> None:
    require(set(before_rows) == set(after_rows), "ROW_ID_SET_CHANGED")
    changed = {profile for profile in before_rows if before_rows[profile] != after_rows[profile]}
    require(changed == {PROFILE_ID}, "UNRELATED_ROW_MUTATION")


def validate_class_identity(class_info: Mapping[str, Any]) -> None:
    ids = class_info.get("PROFILE_IDS")
    require(
        class_info.get("COUNT") == EXPECTED_CLASS_COUNT
        and class_info.get("BOUND_AFTER") == EXPECTED_CLASS_BOUND
        and class_info.get("BOUND_BEFORE") == EXPECTED_CLASS_BOUND
        and class_info.get("BOUND_DELTA") == 0
        and class_info.get("ID_SET_SHA256") == EXPECTED_CLASS_ID_SET_SHA256
        and type(ids) is list
        and len(cast(list[Any], ids)) == EXPECTED_CLASS_COUNT
        and len(set(cast(list[Any], ids))) == EXPECTED_CLASS_COUNT,
        "CLASS_IDENTITY_MISMATCH",
    )


def validate_family_gain(before: Mapping[str, Any], after: Mapping[str, Any]) -> None:
    before_bound = before.get("FAMILY_BOUND")
    after_bound = after.get("FAMILY_BOUND")
    require(
        before_bound == EXPECTED_FAMILY_BOUND
        and after_bound == EXPECTED_FAMILY_BOUND
        and before_bound - after_bound == 0,
        "FAMILY_GAIN_MISMATCH",
    )


_BANNED_LINEAGE = re.compile(
    r"(?:\b(?:34|35|36|37|38)[-_ ]*event\b|\bB649[_-][A-Z0-9_-]*(?:34|35|36|37|38)[_-]EVENT\b)",
    re.IGNORECASE,
)


def validate_row_source(source: str) -> None:
    require(not _BANNED_LINEAGE.search(source), "CROSS_LINEAGE_SOURCE_CONTAMINATION")
    require(source == ROW_SOURCE_AFTER, "ROW_SOURCE_BINDING_MISMATCH")


def validate_old_row_cap(row: Row, expected_cap: int) -> None:
    require(row.cap == expected_cap == OLD_CAP, "TARGET_OLD_CAP_MISMATCH")


def validate_new_bound(cap: int, bound: int) -> None:
    require(cap == NEW_CAP, "UNSUPPORTED_T_CAP")
    require(bound == NEW_BOUND, "T256_ROUTE_B_BOUND_MISMATCH")


def validate_candidate_parent(head: str, parents: Sequence[str]) -> None:
    require(
        list(parents) == [head, BASE_HEAD],
        "CANDIDATE_MUST_BE_DIRECT_CHILD_OF_PINNED_BASE",
    )


def validate_committed_paths(paths: Sequence[str]) -> None:
    require(
        list(paths) == list(COMMITTED_PATHS),
        "COMMITTED_PATH_SET_MISMATCH",
    )


def expect_rejected(action: Callable[[], object]) -> str:
    try:
        action()
    except (ValueError, AssertionError, KeyError, IndexError, TypeError) as exc:
        return f"REJECTED: {type(exc).__name__}: {exc}"
    raise AssertionError("negative control was unexpectedly accepted")


def negative_case_results(
    base_result: Mapping[str, Any],
    base_history: Sequence[Mapping[str, Any]],
    full_history: Sequence[Mapping[str, Any]],
    before_rows: Mapping[str, Row],
    after_rows: Mapping[str, Row],
    old_row: Row,
    new_row: Row,
    profile_distribution: Mapping[str, int],
    profile_parameters: Mapping[str, int],
    class_info: Mapping[str, Any],
    family_before: Mapping[str, Any],
    family_after: Mapping[str, Any],
    binding: Mapping[str, Any],
) -> dict[str, str]:
    unrelated = dict(after_rows)
    unrelated_id = next(profile for profile in unrelated if profile != PROFILE_ID)
    unrelated[unrelated_id] = replace(
        unrelated[unrelated_id], bound=unrelated[unrelated_id].bound + 1
    )
    missing_provenance = dict(binding)
    missing_provenance.pop("JUDGE_SESSION_1", None)
    params = dict(profile_parameters)
    rounding_probe = Fraction(4, 7)
    floor_value = rounding_probe.numerator // rounding_probe.denominator
    ceiling_value = -((-rounding_probe.numerator) // rounding_probe.denominator)
    require(floor_value != ceiling_value, "S4_ROUNDING_NEGATIVE_CONTROL_NOT_DISCRIMINATING")
    return {
        "WRONG_BASE_HEAD_TREE": expect_rejected(
            lambda: verify_base_identity("0" * 40, BASE_TREE, BASE_RESULT_SHA256)
        ),
        "WRONG_BASE_RESULT_SHA": expect_rejected(
            lambda: verify_base_identity(BASE_HEAD, BASE_TREE, "0" * 64)
        ),
        "WRONG_TARGET_PROFILE": expect_rejected(lambda: validate_profile_id("0" * 20)),
        "WRONG_ORIGINAL_CAP": expect_rejected(
            lambda: validate_old_row_cap(replace(old_row, cap=264), OLD_CAP)
        ),
        "WRONG_DEGREE_DISTRIBUTION": expect_rejected(
            lambda: validate_distribution({"6": 5, "5": 5})
        ),
        "WRONG_W": expect_rejected(
            lambda: validate_wua(params["W"] + 1, params["U"], params["A_MAX"], params["G_MAX"])
        ),
        "WRONG_U": expect_rejected(
            lambda: validate_wua(params["W"], params["U"] + 1, params["A_MAX"], params["G_MAX"])
        ),
        "WRONG_A_MAX": expect_rejected(
            lambda: validate_wua(params["W"], params["U"], params["A_MAX"] + 1, params["G_MAX"])
        ),
        "UNSUPPORTED_T_CAP_255": expect_rejected(lambda: validate_new_bound(255, NEW_BOUND)),
        "WRONG_T256_BOUND": expect_rejected(lambda: validate_new_bound(NEW_CAP, NEW_BOUND + 1)),
        "MISSING_EVENT": expect_rejected(lambda: validate_event_history(base_history, 32)),
        "DUPLICATE_EVENT": expect_rejected(
            lambda: validate_event_history([*full_history, full_history[-1]], 32)
        ),
        "UNRELATED_ROW_MUTATION": expect_rejected(
            lambda: validate_ledger_partition(before_rows, unrelated)
        ),
        "WRONG_CLASS_IDENTITY": expect_rejected(
            lambda: validate_class_identity({**class_info, "ID_SET_SHA256": "0" * 64})
        ),
        "WRONG_FAMILY_GAIN": expect_rejected(
            lambda: validate_family_gain(
                family_before,
                {**family_after, "FAMILY_BOUND": EXPECTED_FAMILY_BOUND - 1},
            )
        ),
        "CROSS_LINEAGE_34_38_SOURCE": expect_rejected(
            lambda: validate_row_source(
                ROW_SOURCE_AFTER + ";source=35-event-candidate/result.json"
            )
        ),
        "MISSING_SCIENCE_JUDGE_PROVENANCE": expect_rejected(
            lambda: validate_math_binding(missing_provenance)
        ),
        "S4_ROUNDING_CEILING_MUTATION": expect_rejected(
            lambda: validate_s4_rounding_mode(1, "CEILING")
        ),
        "WRONG_CANDIDATE_PARENT": expect_rejected(
            lambda: validate_candidate_parent("f" * 40, ["f" * 40, "0" * 40])
        ),
        "WRONG_COMMITTED_PATH_SET": expect_rejected(
            lambda: validate_committed_paths([*COMMITTED_PATHS, "src/foreign.py"])
        ),
        "WRONG_SOURCE_CLOSURE": expect_rejected(
            lambda: verify_source_closure(
                {
                    "lottolab.uncommitted_candidate": str(
                        ROOT / "src/lottolab/research/foreign_untracked_candidate.py"
                    )
                }
            )
        ),
    }


def family_summary(rows: Mapping[str, Row], class_bound: int) -> dict[str, Any]:
    return base31.family_summary(rows, class_bound)


def build_candidate() -> tuple[dict[str, Any], dict[str, Row], dict[str, Row]]:
    base_result, base_rows, base_raw = load_and_replay_base()
    history = cast(list[dict[str, Any]], base_result["EVENT_HISTORY"])
    validate_event_history(history, 31)
    require(
        PROFILE_ID not in {event["PROFILE_ID"] for event in history},
        "TARGET_PROFILE_ALREADY_UPDATED_IN_31_EVENT_PREFIX",
    )

    old_row = base_rows[PROFILE_ID]
    validate_old_row(old_row)
    profile, distribution = profile_data(PROFILE_ID)
    validate_profile_id(PROFILE_ID)
    validate_distribution(distribution)
    require(len(profile) == 20 and sum(profile) == 66 and sum(d * d for d in profile) == 338,
            "TARGET_PROFILE_MOMENTS_MISMATCH")
    require(old_row.realization is not None, "TARGET_SUPPORT_REALIZATION_MISSING")
    triples, pairs = old_row.realization
    support_signature = R5_ENGINE.validate_k20_support_realization(triples, pairs, profile)
    support_summary = asdict(support_signature)

    old_route = route_certificate(PROFILE_ID, profile, OLD_CAP)
    new_route = route_certificate(PROFILE_ID, profile, NEW_CAP)
    validate_new_bound(NEW_CAP, cast(int, new_route["BOUND"]))
    old_terms = cast(list[list[int]], old_route["TERMS"])
    new_terms = cast(list[list[int]], new_route["TERMS"])
    require(
        new_terms == old_terms[: len(new_terms)]
        and len(old_terms) == 242
        and len(new_terms) == 235,
        "ROUTE_B_PREFIX_OR_TERM_COUNT_MISMATCH",
    )
    mismatch_count = cast(int, old_route["TERM_MISMATCH_COUNT"]) + cast(
        int, new_route["TERM_MISMATCH_COUNT"]
    )
    require(mismatch_count == 0, "ROUTE_B_TERM_MISMATCH_COUNT_NONZERO")

    binding = math_binding()
    validate_math_binding(binding)
    validate_row_source(ROW_SOURCE_AFTER)
    new_row = replace(old_row, bound=NEW_BOUND, cap=NEW_CAP, source=ROW_SOURCE_AFTER)
    after_rows = dict(base_rows)
    after_rows[PROFILE_ID] = new_row
    validate_ledger_partition(base_rows, after_rows)
    changed = {profile for profile in base_rows if base_rows[profile] != after_rows[profile]}
    require(len(changed) == 1, "CHANGED_ROW_COUNT_MISMATCH")

    event = base31.base.nine.event_from_update(EVENT_ID, PROFILE_ID, old_row, new_row)
    event["SCIENCE_JUDGE"] = binding
    event["ROUTE_B"] = {
        "OLD_TERM_COUNT": old_route["TERM_COUNT"],
        "NEW_TERM_COUNT": new_route["TERM_COUNT"],
        "OLD_ARGMAX": old_route["ARGMAX_TERM"],
        "NEW_ARGMAX": new_route["ARGMAX_TERM"],
        "INTEGER_RECOUNT": "PASS",
        "FRACTION_RECOUNT": "PASS",
        "R32_CROSSCHECK": "PASS",
        "TERM_MISMATCH_COUNT": mismatch_count,
    }
    events = [*history, event]
    validate_event_history(events, 32)
    require(events[:31] == history, "EVENT_PREFIX_PARITY_FAILED")

    full_before = ROW_ENGINE.full_digest(base_rows)
    bounds_before = ROW_ENGINE.bounds_digest(base_rows)
    full_after = ROW_ENGINE.full_digest(after_rows)
    bounds_after = ROW_ENGINE.bounds_digest(after_rows)
    require(
        (full_before, bounds_before) == (BASE_FULL_DIGEST, BASE_BOUNDS_DIGEST),
        "BASE_DIGESTS_CHANGED_DURING_UPDATE",
    )
    require(full_after != full_before and bounds_after != bounds_before,
            "UPDATED_ROW_DID_NOT_CHANGE_CANONICAL_DIGESTS")

    class_info = json.loads(json.dumps(base_result["CLASS"]))
    validate_class_identity(class_info)
    class_bound = cast(int, class_info["BOUND_AFTER"])
    family_before = family_summary(base_rows, class_bound)
    family_after = family_summary(after_rows, class_bound)
    validate_family_gain(family_before, family_after)
    require(
        family_after["MAX_RESOLVED_BOUND"] == EXPECTED_FAMILY_BOUND
        and family_after["MAX_RESOLVED_OWNERS"] == EXPECTED_MAX_OWNERS
        and family_after["NEXT_DISTINCT_BOUND"] == EXPECTED_NEXT_BOUND
        and family_after["NEXT_DISTINCT_OWNERS"] == EXPECTED_NEXT_OWNERS,
        "FULL_FAMILY_RECOUNT_MISMATCH",
    )

    profile_parameters = cast(dict[str, int], old_route["PROFILE_PARAMETERS"])
    negative = negative_case_results(
        base_result,
        history,
        events,
        base_rows,
        after_rows,
        old_row,
        new_row,
        distribution,
        profile_parameters,
        class_info,
        family_before,
        family_after,
        binding,
    )
    require(
        len(negative) == 21
        and all(value.startswith("REJECTED:") for value in negative.values()),
        "REQUIRED_NEGATIVE_CONTROL_ACCEPTED",
    )

    source_sha256 = sha256((ROOT / SOURCE_PATH).read_bytes())
    test_sha256 = sha256((ROOT / TEST_PATH).read_bytes())
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "LOCAL_COMMIT_COMPATIBLE_32_EVENT_R2_CANDIDATE_REPLAYED",
        "IMPLEMENTATION_DEPTH": "NORMAL",
        "DEPTH_SOURCE": "PLANNER_SUPPLIED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "NEW_ENGINEERING_JUDGE": "SELF_CHECK_ONLY",
        "FORMAL_FAMILY_AUTHORITY": "NOT_ACCEPTED",
        "COMMIT_MODEL": {
            "PARENT": BASE_HEAD,
            "EXPECTED_PATHS": list(COMMITTED_PATHS),
            "MAX_LOCAL_COMMITS": 1,
            "FINAL_HEAD_EMBEDDED": False,
            "FINAL_TREE_EMBEDDED": False,
        },
        "POSTCOMMIT_REPLAY_POLICY": "RUN_CANDIDATE_CHECK_AND_FOCUSED_TESTS_AFTER_COMMIT",
        "FINAL_GIT_IDENTITY_POLICY": "RECORD_ACTUAL_HEAD_TREE_AND_PARENT_EXTERNALLY",
        "SOURCE_CLOSURE_POLICY": "PINNED_BASE_PYTHON_MODULES_PLUS_R2_SOURCE_TEST_AND_RESULT",
        "EXTERNAL_UNCOMMITTED_IMPORTS": 0,
        "BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "RESULT_PATH": BASE_RESULT_PATH,
            "RESULT_SHA256": sha256(base_raw),
            "ROWS": len(base_rows),
            "EVENTS": len(history),
            "FULL_DIGEST": full_before,
            "BOUNDS_DIGEST": bounds_before,
        },
        "FROZEN": {
            "HEAD": FROZEN_HEAD,
            "TREE": FROZEN_TREE,
            "RESULT_SHA256": FROZEN_RESULT_SHA256,
        },
        "ROWS_BEFORE": len(base_rows),
        "ROWS_AFTER": len(after_rows),
        "EVENTS_BEFORE": len(history),
        "EVENTS_AFTER": len(events),
        "CHANGED_ROWS": len(changed),
        "UNCHANGED_ROWS": len(base_rows) - len(changed),
        "EVENT_PREFIX_PARITY": "EXACT",
        "UNRELATED_ROW_MUTATION": 0,
        "TARGET_PROFILE": {
            "PROFILE_ID": PROFILE_ID,
            "DEGREE_DISTRIBUTION": distribution,
            "K_COUNT": sum(1 for degree in profile if degree > 0),
            "Z_COUNT": profile.count(0),
            "SUM_D": sum(profile),
            "SUM_D_SQUARED": sum(degree * degree for degree in profile),
            "OLD_CAP": OLD_CAP,
            "NEW_CAP": NEW_CAP,
            "OLD_BOUND": OLD_BOUND,
            "NEW_BOUND": NEW_BOUND,
            "OWNER_DELTA": OWNER_DELTA,
            "OLD_ROW_SOURCE": ROW_SOURCE_BEFORE,
            "NEW_ROW_SOURCE": ROW_SOURCE_AFTER,
            "SUPPORT_VALIDATION": "R5_PASS",
            "SUPPORT_SIGNATURE": support_summary,
        },
        "MATH_BINDING": binding,
        "ROUTE_B": {
            "OLD": old_route,
            "NEW": new_route,
            "OLD_TERMS": len(old_terms),
            "NEW_TERMS": len(new_terms),
            "OLD_ARGMAX": old_route["ARGMAX_TERM"],
            "NEW_ARGMAX": new_route["ARGMAX_TERM"],
            "INTEGER_RECOUNT": "PASS",
            "FRACTION_RECOUNT": "PASS",
            "R32_CROSSCHECK": "PASS",
            "TERM_MISMATCH_COUNT": mismatch_count,
            "S4_ROUNDING_NEGATIVE_CONTROL": {
                "PROBE_S4": 1,
                "FOUR_S4_OVER_SEVEN": "4/7",
                "FLOOR": 0,
                "CEILING": 1,
                "MUTATED_CEILING": negative["S4_ROUNDING_CEILING_MUTATION"],
            },
        },
        "CLASS": class_info,
        "CLASS_COUNT": class_info["COUNT"],
        "CLASS_BOUND": class_info["BOUND_AFTER"],
        "CLASS_ID_SET_SHA256": class_info["ID_SET_SHA256"],
        "CLASS_MUTATIONS": 0,
        "FAMILY_BEFORE": family_before["FAMILY_BOUND"],
        "FAMILY_AFTER": family_after["FAMILY_BOUND"],
        "FAMILY_GAIN": family_before["FAMILY_BOUND"] - family_after["FAMILY_BOUND"],
        "MAX_RESOLVED_BOUND": family_after["MAX_RESOLVED_BOUND"],
        "MAX_RESOLVED_OWNERS": family_after["MAX_RESOLVED_OWNERS"],
        "NEXT_DISTINCT_BOUND": family_after["NEXT_DISTINCT_BOUND"],
        "NEXT_DISTINCT_OWNERS": family_after["NEXT_DISTINCT_OWNERS"],
        "FULL_DIGEST": full_after,
        "BOUNDS_DIGEST": bounds_after,
        "AUTHORITY_GATES": {
            "BASE_HEAD_TREE": "MATCH",
            "BASE_RESULT_SHA256": "MATCH",
            "BASE_FULL_DIGEST_REPLAY": "MATCH",
            "BASE_BOUNDS_DIGEST_REPLAY": "MATCH",
            "FROZEN_HEAD_TREE": "MATCH",
            "FROZEN_RESULT_SHA256": "MATCH",
            "MATH_JUDGE_BINDING": "TRANSCRIPT_ONLY",
            "CLASS_COUNT": "MATCH",
            "CLASS_ID_SET": "EXACT_MATCH",
            "CLASS_BOUND": "MATCH",
            "CLASS_MUTATIONS": 0,
        },
        "NEGATIVE_CASE_RESULTS": negative,
        "EVENT_HISTORY": events,
        "SOURCE_SHA256": source_sha256,
        "TEST_SHA256": test_sha256,
    }
    return result, base_rows, after_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="create the result file if absent")
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
            require(output_path.read_bytes() == encoded, "REFUSING_TO_OVERWRITE_DIFFERENT_RESULT")
            outcome = "ALREADY_MATCHES"
        print(f"RESULT_WRITE: {outcome}")
    else:
        require(output_path.is_file(), "CANDIDATE_RESULT_MISSING")
        require(output_path.read_bytes() == encoded, "CANDIDATE_RESULT_REPLAY_MISMATCH")
        print("CANDIDATE_REPLAY: PASS")
    print(
        json.dumps(
            {
                "ROWS": result["ROWS_AFTER"],
                "EVENTS": result["EVENTS_AFTER"],
                "CHANGED_ROWS": result["CHANGED_ROWS"],
                "FAMILY_BEFORE": result["FAMILY_BEFORE"],
                "FAMILY_AFTER": result["FAMILY_AFTER"],
                "FULL_DIGEST": result["FULL_DIGEST"],
                "BOUNDS_DIGEST": result["BOUNDS_DIGEST"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
