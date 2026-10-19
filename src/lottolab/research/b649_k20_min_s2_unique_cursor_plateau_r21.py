"""Resolve the complete load-bearing square-sum-322 cursor class (R21).

Only R20's final committed ledger is consumed; its 14 old owners are never
re-solved. The 57 unresolved profiles have 824 overlap wedges. R18's induced
P3 injection gives five open wedges, hence at most 273 triangles and class
bound 313,646,248. This includes every exact 22-triple/27-double realization
and every S3 maximizer, so individual support or higher-order solving is
unnecessary. The family then stops at R20's two resolved owners, 313,656,776.

R14's complete class relaxation is an external-timeout-wrapped verification
oracle, run before the class is applied. Its incumbent objectives are never
used as lower bounds. No proof work is dispatched after an old owner returns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from math import comb
from pathlib import Path
from time import monotonic
from typing import cast

from .b649_k20_min_s2_class_dominance_or_descent_r13 import (
    CLASS_RELAXATION_WALL_LIMIT_SECONDS,
    graph_triangle_upper_bound_from_open_wedges,
    profile_family_envelope_from_triangle_bound,
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import solver_runtime_preflight
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import canonical_primitive_preflight
from .b649_k20_min_s2_cursor_plateau_closure_r18 import (
    assert_plateau_only_scope,
    clique_partition_edge_totals,
    generic_open_wedge_floor,
    recompute_family_bound,
)
from .b649_k20_min_s2_load_bearing_plateau_descent_r16 import (
    PlateauFrontier,
    freeze_current_plateau,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_DOUBLE_SUPPORT_COUNT,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_INCIDENCE_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
)
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    decode_profile,
    profile_id,
)
from .b649_k20_min_s2_successive_class_dominance_r14 import certify_square_sum_class

DegreeProfile = tuple[int, ...]
TASK_ID = "B649_K20_MIN_S2_UNIQUE_CURSOR_PLATEAU_R21"
TASK_BRANCH = "codex/b649-k20-min-s2-unique-cursor-plateau-r21"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "6869271550f53725b523edb69ae68bfec66c4232"
BASE_TREE = "158e66436a76ca27bc55d15b5e95d47f647c4628"
START_BOUND = 313_658_120
INCUMBENT = 313_239_661
CURSOR_PROFILE: DegreeProfile = tuple(map(int, "66666665442111111111"))
SQUARE_SUM = 322
EXPECTED_PLATEAU_COUNT = 57
EXPECTED_RESOLVED_COUNT = 282
EXPECTED_RESOLVED_MAX = 313_656_776
EXPECTED_RESOLVED_OWNERS = ("66665555555411100000", "66655555555521000000")
EXPECTED_NEXT_PROFILE: DegreeProfile = tuple(map(int, "66666665433111111111"))
EXPECTED_NEXT_BOUND = 313_655_320
EXPECTED_CLASS_BOUND = 313_646_248
MAX_PLATEAUS = 3
MAX_NEW_PROFILE_SOLVES = 64
PROOF_WALL_SECONDS = 3_600.0
CLASS_ORACLE_NATIVE_SECONDS = 600.0
CLASS_ORACLE_EXTERNAL_SECONDS = 620.0
RESULT_DIRECTORY = "docs/research/matrix-native-results"
R20_FILENAME = "b649-k20-min-s2-resolved-above-cursor-owner-chase-r20-result.json"
R20_SHA256 = "47afe9b8e5643f0123fcccfcf678689755106056e7b9b68a3431b837706113aa"
RESULT_FILENAME = "b649-k20-min-s2-unique-cursor-plateau-r21-result.json"
MODULE_NAME = "lottolab.research.b649_k20_min_s2_unique_cursor_plateau_r21"
SUCCESS_C = "SUCCESS_C_CURRENT_PLATEAU_RESOLVED_EXACT_PREVIOUSLY_RESOLVED_OWNER"


@dataclass(frozen=True, slots=True)
class CurrentState:
    bounds: Mapping[DegreeProfile, int]
    sources: Mapping[DegreeProfile, str]
    old_owners: frozenset[DegreeProfile]
    input_sha256: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def result_path() -> Path:
    return repo_root() / RESULT_DIRECTORY / RESULT_FILENAME


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AssertionError("expected a certificate object")
    return cast(dict[str, object], value)


def _rows(value: object) -> list[object]:
    if not isinstance(value, list):
        raise AssertionError("expected a certificate row list")
    return cast(list[object], value)


def _integer(value: object) -> int:
    if type(value) is not int:
        raise AssertionError("expected an exact integer bound")
    return value


def committed_r20_result() -> tuple[dict[str, object], str]:
    """Read one pinned result, without reconstructing any previous ledger."""

    relative = f"{RESULT_DIRECTORY}/{R20_FILENAME}"
    blob = subprocess.check_output(["git", "show", f"{BASE_HEAD}:{relative}"], cwd=repo_root())
    digest = hashlib.sha256(blob).hexdigest()
    if digest != R20_SHA256:
        raise AssertionError("the pinned R20 result identity changed")
    return _object(json.loads(blob)), digest


def validate_current_state(result: Mapping[str, object], digest: str) -> CurrentState:
    expected: dict[str, object] = {
        "TASK_STATUS": "SUCCESS_B_ALL_RESOLVED_AT_OR_BELOW_CURSOR",
        "FAMILY_UPPER_BOUND": START_BOUND,
        "CURSOR_BOUND": START_BOUND,
        "CURSOR_PROFILE": profile_id(CURSOR_PROFILE),
        "CURRENT_BOUND_OWNER_SET": [profile_id(CURSOR_PROFILE)],
        "RESOLVED_LEDGER_COUNT": EXPECTED_RESOLVED_COUNT,
        "REMAINING_RESOLVED_ABOVE_CURSOR_COUNT": 0,
        "REMAINING_RESOLVED_ABOVE_CURSOR_PROFILES": [],
        "INCUMBENT": INCUMBENT,
        "CURSOR_GENUINELY_LOAD_BEARING": True,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError(f"R20 unique-cursor authority mismatch: {key}")
    bounds: dict[DegreeProfile, int] = {}
    sources: dict[DegreeProfile, str] = {}
    for index, raw in enumerate(_rows(result["FINAL_RESOLVED_LEDGER"])):
        row = _object(raw)
        profile = decode_profile(row["PROFILE_ID"])
        if profile in bounds:
            raise AssertionError("duplicate committed resolved profile")
        bounds[profile] = _integer(row["CURRENT_BOUND"])
        sources[profile] = f"R20.FINAL_RESOLVED_LEDGER[{index}]"
    if len(bounds) != EXPECTED_RESOLVED_COUNT or CURSOR_PROFILE in bounds:
        raise AssertionError("the complete resolved identity set or unresolved cursor changed")
    if any(bound > START_BOUND for bound in bounds.values()):
        raise AssertionError("a resolved profile exceeds the current cursor")
    maximum = max(bounds.values())
    owners = tuple(sorted((profile_id(p) for p, b in bounds.items() if b == maximum), reverse=True))
    if max(bounds.values()) != EXPECTED_RESOLVED_MAX or owners != EXPECTED_RESOLVED_OWNERS:
        raise AssertionError("the committed resolved maximum or owner set changed")
    old_rows = _rows(result["RESOLVED_ABOVE_CURSOR_PROFILES"])
    old_owners = frozenset(decode_profile(raw) for raw in old_rows)
    if len(old_owners) != len(old_rows) or len(old_owners) != 14 or not old_owners <= bounds.keys():
        raise AssertionError("R20's 14 old-owner guard identities changed")
    return CurrentState(bounds, sources, old_owners, digest)


def current_state() -> CurrentState:
    result, digest = committed_r20_result()
    return validate_current_state(result, digest)


def assert_class_scope(state: CurrentState, plateau: PlateauFrontier) -> None:
    assert_plateau_only_scope(
        plateau.profiles,
        prior=state.bounds,
        plateau=plateau.profiles,
        active_bound=START_BOUND,
    )
    if set(plateau.profiles) & state.old_owners:
        raise AssertionError("old owner re-run requested")
    if plateau.bound != START_BOUND or max(state.bounds.values()) >= START_BOUND:
        raise AssertionError("class work is not at the actual starting family maximum")


def freeze_plateau(state: CurrentState, *, deadline: float) -> PlateauFrontier:
    plateau = freeze_current_plateau(
        cursor=CURSOR_PROFILE,
        active_bound=START_BOUND,
        prior_profiles=state.bounds,
        deadline=deadline,
    )
    if (
        len(plateau.profiles) != EXPECTED_PLATEAU_COUNT
        or plateau.profiles[0] != CURSOR_PROFILE
        or plateau.next_profile != EXPECTED_NEXT_PROFILE
        or plateau.next_bound != EXPECTED_NEXT_BOUND
        or any(sum(d * d for d in p) != SQUARE_SUM for p in plateau.profiles)
    ):
        raise AssertionError("complete current plateau membership or exact successor changed")
    assert_class_scope(state, plateau)
    return plateau


def certify_plateau_class(plateau: PlateauFrontier) -> dict[str, object]:
    profiles = plateau.profiles
    if len(profiles) != EXPECTED_PLATEAU_COUNT or len(set(profiles)) != len(profiles):
        raise AssertionError("class certificate requires the complete unique 57-profile plateau")
    for profile in profiles:
        decode_profile(list(profile))
        if sum(d * d for d in profile) != SQUARE_SUM:
            raise AssertionError("class member has the wrong degree square sum")
    edge_count = 3 * K20_TRIPLE_SUPPORT_COUNT + K20_DOUBLE_SUPPORT_COUNT
    low, high = K20_TICKET_CAPACITY, 2 * K20_TICKET_CAPACITY
    floor = generic_open_wedge_floor(K20_TICKET_COUNT, edge_count, low, high)
    envelopes = [
        graph_triangle_upper_bound_from_open_wedges(tuple(6 + d for d in p), floor)
        for p in profiles
    ]
    if any(envelope != envelopes[0] for envelope in envelopes):
        raise AssertionError("class members do not share their wedge and triangle envelope")
    triangle_cap = envelopes[0]["GRAPH_TRIANGLE_UPPER_BOUND"]
    motifs = [profile_family_envelope_from_triangle_bound(p, triangle_cap) for p in profiles]
    class_bound = max(row["FAMILY_UPPER_BOUND"] for row in motifs)
    if plateau.next_bound is None or class_bound >= plateau.next_bound:
        raise AssertionError("generic class dominance is insufficient below the next competitor")
    if class_bound != EXPECTED_CLASS_BOUND:
        raise AssertionError("the analytic class bound changed")
    wedges = overlap_wedge_count(profiles[0])
    triangle_identity = comb(20, 3) - 18 * edge_count + wedges
    return {
        "CLASS_CERTIFICATE_KIND": "R18_INDUCED_P3_INJECTION_AND_WEDGE_CONGRUENCE",
        "SQUARE_SUM": SQUARE_SUM,
        "PROFILE_COUNT": len(profiles),
        "PROFILE_IDENTITIES": list(map(profile_id, profiles)),
        "OVERLAP_GRAPH_VERTEX_COUNT": K20_TICKET_COUNT,
        "OVERLAP_GRAPH_EDGE_COUNT": edge_count,
        "OVERLAP_GRAPH_DEGREE_INTERVAL": [low, high],
        "CLIQUE_PARTITION_EDGE_TOTALS": [
            {"COMPONENT_SIZES": list(sizes), "EDGE_COUNT": edges}
            for sizes, edges in clique_partition_edge_totals(20, low, high)
        ],
        "INDUCED_P3_OPEN_WEDGE_LOWER_BOUND": floor,
        **envelopes[0],
        "GRAPH_PLUS_COMPLEMENT_TRIANGLE_IDENTITY_CONSTANT": triangle_identity,
        "COMPLEMENT_TRIANGLE_LOWER_BOUND": triangle_identity - triangle_cap,
        "NONCORE_TRIANGLE_UPPER_BOUND": triangle_cap - K20_TRIPLE_SUPPORT_COUNT,
        "SHARED_VERTEX_SUPPORT_PAIR_COUNT": (SQUARE_SUM - K20_TRIPLE_INCIDENCE_COUNT) // 2,
        "LOOSE_THREE_CYCLE_UPPER_BOUND": triangle_cap - K20_TRIPLE_SUPPORT_COUNT,
        "PASCH_LIKE_FOUR_SUPPORT_UPPER_BOUND": (triangle_cap - K20_TRIPLE_SUPPORT_COUNT) // 4,
        "TRIPLE_SUPPORT_COUNT": K20_TRIPLE_SUPPORT_COUNT,
        "RESIDUAL_DOUBLE_SUPPORT_COUNT": K20_DOUBLE_SUPPORT_COUNT,
        "REALIZATION_SCOPE": "ALL_EXACT_SUPPORT_REALIZATIONS_AND_RELAXATION_SUPERSETS",
        "S4_FLOOR_SCOPE": "ALL_REALIZATIONS_INCLUDING_S3_MAXIMIZERS",
        "S3_UPPER_BOUND": max(row["S3_UPPER_BOUND"] for row in motifs),
        "S4_LOWER_BOUND": min(row["S4_LOWER_BOUND"] for row in motifs),
        "FOURTH_ORDER_CREDIT": min(row["FOURTH_ORDER_CREDIT"] for row in motifs),
        "CLASS_FAMILY_UPPER_BOUND": class_bound,
        "RANKED_COARSE_CLASS_BOUND": plateau.bound,
        "NEXT_DISTINCT_COARSE_BOUND": plateau.next_bound,
        "COMPLETE_PLATEAU_COVERAGE": True,
        "CERTIFICATION_STATUS": "CERTIFIED_BELOW_NEXT_COMPETING_FAMILY_BOUND",
        "PER_PROFILE_SOLVER_WORK_NEEDED": False,
        "HIGHER_ORDER_MULTIPLICITY_LOAD_BEARING": False,
    }


def class_oracle_child(*, wall_seconds: float) -> dict[str, object]:
    if not 0 < wall_seconds <= CLASS_ORACLE_NATIVE_SECONDS:
        raise ValueError("invalid bounded class oracle wall limit")
    started = monotonic()
    deadline = started + wall_seconds
    state = current_state()
    plateau = freeze_plateau(state, deadline=deadline)
    assert_class_scope(state, plateau)
    certificate = certify_square_sum_class(
        square_sum=SQUARE_SUM,
        upper_profile=CURSOR_PROFILE,
        prior_profiles=state.bounds,
        deadline=deadline,
    )
    return {
        "CLASS_CERTIFICATE": certificate,
        "PROOF_ACTUAL_WALL_SECONDS": monotonic() - started,
    }


def run_class_oracle(
    state: CurrentState, plateau: PlateauFrontier, *, deadline: float
) -> dict[str, object]:
    assert_class_scope(state, plateau)
    remaining = deadline - monotonic()
    external_seconds = min(CLASS_ORACLE_EXTERNAL_SECONDS, remaining - 5.0)
    native_seconds = min(CLASS_ORACLE_NATIVE_SECONDS, external_seconds - 20.0)
    if native_seconds <= 0:
        raise RuntimeError("insufficient remaining proof wall budget for the class oracle")
    environment = {
        **os.environ,
        "PYTHONPATH": str(repo_root() / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
    command = [
        "timeout",
        "--signal=TERM",
        "--kill-after=5s",
        f"{external_seconds}s",
        sys.executable,
        "-m",
        MODULE_NAME,
        "--class-oracle-wall-seconds",
        str(native_seconds),
    ]
    started = monotonic()
    completed = subprocess.run(
        command, cwd=repo_root(), env=environment, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"class oracle failed/was externally timed out: {completed.returncode}; "
            f"{completed.stderr[-1000:]}"
        )
    proof = _object(json.loads(completed.stdout))
    proof["EXTERNAL_TIMEOUT_SECONDS"] = external_seconds
    proof["NATIVE_CLASS_DEADLINE_SECONDS"] = native_seconds
    proof["ACTUAL_WRAPPED_RUN_SECONDS"] = monotonic() - started
    proof["EXTERNAL_TIMEOUT_EXIT_CODE"] = completed.returncode
    return proof


def validate_class_oracle(
    proof: Mapping[str, object], plateau: PlateauFrontier, analytic_bound: int
) -> dict[str, object]:
    certificate = _object(proof["CLASS_CERTIFICATE"])
    if (
        certificate.get("SQUARE_SUM") != SQUARE_SUM
        or certificate.get("COMPLETE_SUFFIX_ENUMERATION") is not True
    ):
        raise AssertionError("class oracle did not certify the complete square-sum class")
    identities: list[DegreeProfile] = []
    rows: list[dict[str, object]] = []
    for raw in _rows(certificate["HISTOGRAM_ENVELOPES"]):
        row = _object(raw)
        profile = decode_profile(row["PROFILE"])
        status, source = row.get("RELAXATION_STATUS"), row.get("LOWER_BOUND_SOURCE")
        if (status, source) not in {
            ("OPTIMAL", "OPTIMAL_OBJECTIVE_VALUE"),
            ("FEASIBLE", "BEST_OBJECTIVE_BOUND_FLOOR"),
        }:
            raise AssertionError("class oracle requires an optimal or certified best bound")
        floor = _integer(row["WEIGHTED_OPEN_WEDGE_LOWER_BOUND"])
        triangle = graph_triangle_upper_bound_from_open_wedges(tuple(6 + d for d in profile), floor)
        envelope = profile_family_envelope_from_triangle_bound(
            profile, triangle["GRAPH_TRIANGLE_UPPER_BOUND"]
        )
        wall = row["SOLVER_WALL_TIME_SECONDS"]
        if not isinstance(wall, (int, float)) or wall < 0:
            raise AssertionError("class oracle omitted its observed solver wall time")
        if row["FAMILY_UPPER_BOUND"] != envelope["FAMILY_UPPER_BOUND"]:
            raise AssertionError("class oracle row's family bound does not reproduce")
        identities.append(profile)
        rows.append(
            {
                "PROFILE_ID": profile_id(profile),
                "STATUS": status,
                "LOWER_BOUND_SOURCE": source,
                "OPEN_WEDGE_LOWER_BOUND": floor,
                "GRAPH_TRIANGLE_UPPER_BOUND": triangle["GRAPH_TRIANGLE_UPPER_BOUND"],
                "FAMILY_UPPER_BOUND": envelope["FAMILY_UPPER_BOUND"],
                "SOLVER_SECONDS": float(wall),
            }
        )
    if len(identities) != len(set(identities)) or set(identities) != set(plateau.profiles):
        raise AssertionError("class oracle membership is incomplete, duplicated or outside plateau")
    declared = tuple(decode_profile(raw) for raw in _rows(certificate["PROFILE_IDENTITIES"]))
    if declared != plateau.profiles:
        raise AssertionError("class oracle's complete ranked identity set changed")
    family_bound = max(_integer(row["FAMILY_UPPER_BOUND"]) for row in rows)
    triangle_bound = max(_integer(row["GRAPH_TRIANGLE_UPPER_BOUND"]) for row in rows)
    if (
        certificate["CLASS_FAMILY_UPPER_BOUND"] != family_bound
        or certificate["GRAPH_TRIANGLE_UPPER_BOUND"] != triangle_bound
        or family_bound > analytic_bound
    ):
        raise AssertionError("class envelope oracle does not verify the analytic class bound")
    return {
        "STATUS": "PASS",
        "MACHINERY": "R14.certify_square_sum_class / R13.degree_class_open_wedge_relaxation",
        "COMPLETE_PLATEAU_COVERAGE": True,
        "HISTOGRAM_COUNT": len(rows),
        "HISTOGRAM_ROWS": rows,
        "CLASS_FAMILY_UPPER_BOUND": family_bound,
        "GRAPH_TRIANGLE_UPPER_BOUND": triangle_bound,
        "ORACLE_USED_TO_SET_CLOSURE_BOUND": False,
        "ACTUAL_WRAPPED_RUN_SECONDS": proof.get("ACTUAL_WRAPPED_RUN_SECONDS"),
        "EXTERNAL_TIMEOUT_EXIT_CODE": proof.get("EXTERNAL_TIMEOUT_EXIT_CODE"),
        "SOLVER_WALL_SECONDS": sum(cast(float, row["SOLVER_SECONDS"]) for row in rows),
    }


def compute_result(*, proof_wall_seconds: float = PROOF_WALL_SECONDS) -> dict[str, object]:
    if not 0 < proof_wall_seconds <= PROOF_WALL_SECONDS:
        raise ValueError("proof wall limit must be positive and at most 3600 seconds")
    started = monotonic()
    deadline = started + proof_wall_seconds
    primitives = canonical_primitive_preflight()
    runtime = solver_runtime_preflight()
    state = current_state()
    plateau = freeze_plateau(state, deadline=deadline)
    certificate = certify_plateau_class(plateau)
    class_bound = _integer(certificate["CLASS_FAMILY_UPPER_BOUND"])
    proof = run_class_oracle(state, plateau, deadline=deadline)
    oracle = validate_class_oracle(proof, plateau, class_bound)
    if plateau.next_profile is None or plateau.next_bound is None:
        raise AssertionError("missing exact next competing cursor")
    family, owners = recompute_family_bound(
        state.bounds,
        class_profiles=plateau.profiles,
        class_bound=class_bound,
        next_profile=plateau.next_profile,
        next_bound=plateau.next_bound,
    )
    if (
        family != EXPECTED_RESOLVED_MAX
        or tuple(map(profile_id, owners)) != EXPECTED_RESOLVED_OWNERS
    ):
        raise AssertionError("the exact final resolved owner set changed")
    # Terminal proof boundary: only reporting occurs after an old owner returns.
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_STATUS": SUCCESS_C,
        "INPUT_AUTHORITY": "ONE_IMMUTABLE_BASE_HEAD_R20_FINAL_LEDGER_GIT_BLOB",
        "COMMITTED_INPUT_SHA256": {f"{RESULT_DIRECTORY}/{R20_FILENAME}": state.input_sha256},
        "PRIOR_OWNER_LEDGER_REBUILT": False,
        "RESOLVED_LEDGER_COUNT_REUSED": len(state.bounds),
        "MAX_RESOLVED_PROFILE_BOUND_AT_START": max(state.bounds.values()),
        "RESOLVED_ABOVE_CURSOR_COUNT_AT_START": 0,
        "UNIQUE_CURSOR_ASSERTION": "PASS",
        "START_CURRENT_BOUND_OWNER": profile_id(CURSOR_PROFILE),
        "START_BOUND": START_BOUND,
        "CURRENT_LOAD_BEARING_PLATEAU": list(map(profile_id, plateau.profiles)),
        "CURRENT_PLATEAU_PROFILE_COUNT": len(plateau.profiles),
        "CURRENT_PLATEAU_COMPLETELY_RESOLVED": True,
        "PLATEAU_COUNT_PROCESSED": 1,
        "PROFILE_COUNT_PROCESSED": 0,
        "CLASSES_ANALYZED": 1,
        "CLASSES_CERTIFIED": 1,
        "PROFILES_ELIMINATED_BY_CLASS_BOUND": len(plateau.profiles),
        "CLASS_CERTIFICATES": [certificate],
        "ANALYTIC_CLASS_CERTIFIED_BOUND": class_bound,
        "CLASS_ENVELOPE_ORACLE": oracle,
        "PLATEAU_LOOKUP": {
            "LOOKUP_PROFILE_COUNT": plateau.lookup_profile_count,
            "COMPLETE_PROFILES_EXAMINED": plateau.complete_profiles_examined,
            "SQUARE_SUM_CLASSES_EXAMINED": plateau.square_sum_classes_examined,
            "COMPLETE_CURRENT_PLATEAU": True,
        },
        "END_BOUND": family,
        "FAMILY_UPPER_BOUND": family,
        "CURRENT_BOUND_OWNER": profile_id(owners[0]),
        "CURRENT_BOUND_OWNER_SET": list(map(profile_id, owners)),
        "CURRENT_BOUND_OWNER_SOURCES": {profile_id(p): state.sources[p] for p in owners},
        "CURRENT_BOUND_OWNER_ROLE": "PREVIOUSLY_RESOLVED_PROFILE",
        "NEXT_ACTIVE_BOUND": plateau.next_bound,
        "NEXT_ACTIVE_PROFILE": profile_id(plateau.next_profile),
        "NEXT_ACTIVE_PROFILE_ROLE": "UNRESOLVED_RANKED_PREFIX",
        "NEXT_ACTIVE_CURSOR_IS_LOAD_BEARING": False,
        "NEXT_COMPETING_FAMILY_BOUND": max(max(state.bounds.values()), plateau.next_bound),
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family - INCUMBENT,
        "FAMILY_STATUS": "OPEN_STRICTLY_TIGHTENED",
        "CERTIFIED_FAMILY_DROP": START_BOUND - family,
        "PACKET_SUCCESS_A_SATISFIED": family <= INCUMBENT,
        "PACKET_SUCCESS_B_SATISFIED": START_BOUND - family >= 25_000,
        "PACKET_SUCCESS_C_SATISFIED": True,
        "STOP_REASON": "PREVIOUSLY_RESOLVED_PROFILE_BECAME_OWNER",
        "CANONICAL_PRIMITIVES": primitives,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_STATUS": "OPTIMAL_CLASS_ENVELOPE_ORACLE"
        if all(_object(row)["STATUS"] == "OPTIMAL" for row in _rows(oracle["HISTOGRAM_ROWS"]))
        else "CERTIFIED_BEST_BOUND_CLASS_ENVELOPE_ORACLE",
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "PER_HISTOGRAM_NATIVE_SECONDS": CLASS_RELAXATION_WALL_LIMIT_SECONDS,
            "CLASS_ORACLE_NATIVE_DEADLINE_SECONDS": proof["NATIVE_CLASS_DEADLINE_SECONDS"],
            "CLASS_ORACLE_EXTERNAL_TIMEOUT_SECONDS": proof["EXTERNAL_TIMEOUT_SECONDS"],
            "EXTERNAL_KILL_AFTER_SECONDS": 5,
            "PROOF_WALL_SECONDS": proof_wall_seconds,
            "CP_SAT_SEARCH_WORKERS": 1,
            "MAX_SUCCESSIVE_PLATEAUS": MAX_PLATEAUS,
            "MAX_NEW_PROFILE_SOLVES": MAX_NEW_PROFILE_SOLVES,
        },
        "SOLVER_ACTUAL_WALL_TIME": oracle["SOLVER_WALL_SECONDS"],
        "PROOF_ACTUAL_WALL_SECONDS": monotonic() - started,
        "SOLVER_CERTIFIED_BOUND": oracle["CLASS_FAMILY_UPPER_BOUND"],
        "SOLVER_CERTIFIED_BOUND_SCOPE": "CURRENT_PLATEAU_CLASS_ONLY",
        "EXACT_SUPPORT_PROFILE_SOLVES": 0,
        "SOLVER_PROFILES_SENT": [],
        "PRIOR_PROFILE_RERUN_COUNT": 0,
        "NO_OLD_OWNER_RERUN_GUARD": "PASS",
        "WORK_AFTER_RESOLVED_OWNER_RETURNED": False,
        "WORK_BELOW_CURRENT_FAMILY_MAX_STARTED": False,
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class-oracle-wall-seconds", type=float)
    parser.add_argument("--proof-wall-seconds", type=float, default=PROOF_WALL_SECONDS)
    arguments = parser.parse_args()
    if arguments.class_oracle_wall_seconds is not None:
        print(json.dumps(class_oracle_child(wall_seconds=arguments.class_oracle_wall_seconds)))
        return
    result = compute_result(proof_wall_seconds=arguments.proof_wall_seconds)
    result_path().write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "TASK_STATUS",
                    "CURRENT_PLATEAU_PROFILE_COUNT",
                    "FAMILY_UPPER_BOUND",
                    "CURRENT_BOUND_OWNER_SET",
                    "NEXT_ACTIVE_PROFILE",
                    "SOLVER_ACTUAL_WALL_TIME",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
