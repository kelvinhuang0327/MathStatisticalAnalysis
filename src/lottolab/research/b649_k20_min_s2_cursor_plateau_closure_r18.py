"""Close the complete square-sum-324 K20 minimum-S2 plateau (R18).

One induced-P3 argument suffices for every realizable profile in the plateau.
The overlap graph has degrees 6+a_i, 93 edges, and 825 wedges. A graph with
these degrees cannot be a disjoint union of cliques: its only possible clique
component sizes are (7,13), (8,12), (9,11), and (10,10), with respectively
99, 94, 91, and 90 edges. Thus some x-y-z is an induced P3.

For each other neighbor w of y, either w is adjacent to both endpoints (so
x-w-z is an open wedge), or w misses an endpoint (so endpoint-y-w is one).
These distinct wedges, together with x-y-z, give at least deg(y)-1 >= 5 open
wedges. Since 825-3*T is a multiple of three, there are at least six. Hence
T <= 273 and the entire class bound is 313,649,048, below the next cursor.
This certificate applies to all realizations, including S3 maximizers; no
individual support, motif, or S4 optimization is necessary.

The R17 owner bound is reused unchanged. All prior resolved profiles and all
profiles below the current maximum are excluded from new solver work.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from math import comb
from pathlib import Path
from time import monotonic
from typing import cast

from .b649_k20_min_s2_class_dominance_or_descent_r13 import (
    CLASS_RELAXATION_WALL_LIMIT_SECONDS,
    assert_no_prior_profile_rerun,
    graph_triangle_upper_bound_from_open_wedges,
    profile_family_envelope_from_triangle_bound,
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import solver_runtime_preflight
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import canonical_primitive_preflight
from .b649_k20_min_s2_load_bearing_plateau_descent_r16 import (
    PlateauFrontier,
    freeze_current_plateau,
    profile_identity,
)
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import coarse_profile_envelope
from .b649_k20_min_s2_r16_freeze_and_owner_refinement_r17 import (
    EXPECTED_NEXT_CURSOR_PROFILE,
    EXPECTED_OWNER_PROFILE,
    post_r16_bound_ledger,
)
from .b649_k20_min_s2_r16_freeze_and_owner_refinement_r17 import (
    RESULT_FILENAME as R17_RESULT_FILENAME,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_DOUBLE_SUPPORT_COUNT,
    K20_INCUMBENT,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_INCIDENCE_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
)

DegreeProfile = tuple[int, ...]
TASK_ID = "B649_K20_MIN_S2_CURSOR_PLATEAU_CLOSURE_R18"
TASK_BRANCH = "codex/b649-k20-min-s2-cursor-plateau-closure-r18"
BASE_HEAD = "5505538fb9d55f9741593bf3e4c410bbf79308f3"
BASE_TREE = "36367eceaa6008a65cb6d87109b70b312e9bdc27"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
RESULT_FILENAME = "b649-k20-min-s2-cursor-plateau-closure-r18-result.json"
START_BOUND = 313_672_792
INCUMBENT = K20_INCUMBENT
PRIOR_OWNER_REFINED_BOUND = 313_662_376
EXPECTED_PRIOR_MAX = 313_671_448
EXPECTED_PLATEAU_COUNT = 55
SQUARE_SUM = 324
MAX_PLATEAUS = 3
MAX_NEW_PROFILE_SOLVES = 64
MAX_PROOF_WALL_SECONDS = 3_600.0
EXTERNAL_CLASS_ORACLE_TIMEOUT_SECONDS = 620
CLASS_ORACLE_NATIVE_DEADLINE_SECONDS = 600.0
EXPECTED_NEXT_PROFILE: DegreeProfile = tuple(int(d) for d in "66666665442111111111")
EXPECTED_NEXT_BOUND = 313_658_120
EXPECTED_BOUND_OWNERS = (
    "66666555554411100000",
    "66665555555421000000",
)


@dataclass(frozen=True, slots=True)
class CurrentState:
    bounds: Mapping[DegreeProfile, int]
    sources: Mapping[DegreeProfile, str]
    cursor: DegreeProfile
    cursor_bound: int


def result_path(filename: str = RESULT_FILENAME) -> Path:
    return Path(__file__).resolve().parents[3] / "docs/research/matrix-native-results" / filename


def _read_object(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected a JSON object at {path}")
    return cast(dict[str, object], value)


def current_state() -> CurrentState:
    """Reconstruct the complete 227-profile ledger and apply R17's override."""

    bounds, sources = post_r16_bound_ledger()
    prior = _read_object(result_path(R17_RESULT_FILENAME))
    expected: dict[str, object] = {
        "TASK_STATUS": "SUCCESS_B_OWNER_ELIMINATED_CURSOR_LOAD_BEARING",
        "CURRENT_OWNER_PROFILE": profile_identity(EXPECTED_OWNER_PROFILE),
        "OWNER_REFINED_BOUND": PRIOR_OWNER_REFINED_BOUND,
        "NEXT_CURSOR_PROFILE": profile_identity(EXPECTED_NEXT_CURSOR_PROFILE),
        "NEXT_CURSOR_BOUND": START_BOUND,
        "FAMILY_UPPER_BOUND": START_BOUND,
        "CURRENT_BOUND_OWNER": profile_identity(EXPECTED_NEXT_CURSOR_PROFILE),
        "INCUMBENT": INCUMBENT,
    }
    for key, value in expected.items():
        if prior.get(key) != value:
            raise AssertionError(f"R17 authority mismatch: {key}")
    if len(bounds) != 227 or EXPECTED_OWNER_PROFILE not in bounds:
        raise AssertionError("the complete prior no-rerun ledger is missing")
    bounds[EXPECTED_OWNER_PROFILE] = PRIOR_OWNER_REFINED_BOUND
    sources[EXPECTED_OWNER_PROFILE] = "R17.OWNER_REFINED_BOUND"
    if max(bounds.values()) != EXPECTED_PRIOR_MAX:
        raise AssertionError("post-R17 resolved maximum changed")
    if EXPECTED_NEXT_CURSOR_PROFILE in bounds:
        raise AssertionError("R17 cursor was already resolved")
    return CurrentState(bounds, sources, EXPECTED_NEXT_CURSOR_PROFILE, START_BOUND)


def assert_plateau_only_scope(
    requested: Collection[DegreeProfile],
    *,
    prior: Collection[DegreeProfile],
    plateau: Collection[DegreeProfile],
    active_bound: int,
) -> None:
    """Guard class and individual work against prior owners and lower ranks."""

    assert_no_prior_profile_rerun(prior, requested)
    if len(requested) != len(set(requested)):
        raise AssertionError("duplicate new profile request")
    if not set(requested) <= set(plateau):
        raise AssertionError("only frozen current-plateau profiles are allowed")
    if any(coarse_profile_envelope(p).family_upper_bound != active_bound for p in requested):
        raise AssertionError("new work must be at the current family maximum")


def freeze_plateau(state: CurrentState, *, deadline: float) -> PlateauFrontier:
    plateau = freeze_current_plateau(
        cursor=state.cursor,
        active_bound=state.cursor_bound,
        prior_profiles=state.bounds,
        deadline=deadline,
    )
    if (
        len(plateau.profiles) != EXPECTED_PLATEAU_COUNT
        or plateau.profiles[0] != EXPECTED_NEXT_CURSOR_PROFILE
        or plateau.next_profile != EXPECTED_NEXT_PROFILE
        or plateau.next_bound != EXPECTED_NEXT_BOUND
        or any(sum(d * d for d in p) != SQUARE_SUM for p in plateau.profiles)
    ):
        raise AssertionError("current plateau membership or exact successor changed")
    assert_plateau_only_scope(
        plateau.profiles,
        prior=state.bounds,
        plateau=plateau.profiles,
        active_bound=state.cursor_bound,
    )
    return plateau


def clique_partition_edge_totals(
    vertex_count: int, minimum_degree: int, maximum_degree: int
) -> tuple[tuple[tuple[int, ...], int], ...]:
    """Enumerate component sizes, not degree profiles or portfolio candidates."""

    if not 0 <= minimum_degree <= maximum_degree < vertex_count:
        raise ValueError("invalid graph degree interval")
    rows: list[tuple[tuple[int, ...], int]] = []

    def visit(remaining: int, sizes: tuple[int, ...], minimum_size: int) -> None:
        if remaining == 0:
            rows.append((sizes, sum(comb(size, 2) for size in sizes)))
            return
        for size in range(minimum_size, min(maximum_degree + 1, remaining) + 1):
            visit(remaining - size, (*sizes, size), size)

    visit(vertex_count, (), minimum_degree + 1)
    return tuple(rows)


def generic_open_wedge_floor(
    vertex_count: int, edge_count: int, minimum_degree: int, maximum_degree: int
) -> int:
    """Use the induced-P3 injection only when clique partitions are excluded."""

    partitions = clique_partition_edge_totals(vertex_count, minimum_degree, maximum_degree)
    if any(edges == edge_count for _, edges in partitions):
        return 0
    return max(0, minimum_degree - 1)


def certify_plateau_class(plateau: PlateauFrontier) -> dict[str, object]:
    profiles = plateau.profiles
    if len(profiles) != EXPECTED_PLATEAU_COUNT or any(
        len(p) != K20_TICKET_COUNT
        or tuple(sorted(p, reverse=True)) != p
        or any(type(d) is not int or not 0 <= d <= K20_TICKET_CAPACITY for d in p)
        or sum(p) != K20_TRIPLE_INCIDENCE_COUNT
        or sum(d * d for d in p) != SQUARE_SUM
        for p in profiles
    ):
        raise AssertionError("class certificate requires complete square-sum-324 profiles")
    if len(profiles) != len(set(profiles)):
        raise AssertionError("class membership contains duplicate profiles")
    edge_count = 3 * K20_TRIPLE_SUPPORT_COUNT + K20_DOUBLE_SUPPORT_COUNT
    minimum_degree, maximum_degree = K20_TICKET_CAPACITY, 2 * K20_TICKET_CAPACITY
    floor = generic_open_wedge_floor(K20_TICKET_COUNT, edge_count, minimum_degree, maximum_degree)
    envelopes = [
        graph_triangle_upper_bound_from_open_wedges(
            tuple(K20_TICKET_CAPACITY + d for d in p), floor
        )
        for p in profiles
    ]
    if any(envelope != envelopes[0] for envelope in envelopes):
        raise AssertionError("a square-sum class must share its wedge/triangle envelope")
    triangle_bound = envelopes[0]["GRAPH_TRIANGLE_UPPER_BOUND"]
    motif_bounds = [
        profile_family_envelope_from_triangle_bound(p, triangle_bound) for p in profiles
    ]
    class_bound = max(row["FAMILY_UPPER_BOUND"] for row in motif_bounds)
    if plateau.next_bound is None or class_bound >= plateau.next_bound:
        raise AssertionError("generic certificate does not close the plateau below its successor")
    wedges = overlap_wedge_count(profiles[0])
    complement_identity = comb(K20_TICKET_COUNT, 3) - (K20_TICKET_COUNT - 2) * edge_count + wedges
    return {
        "CLASS_CERTIFICATE_KIND": "ONE_INDUCED_P3_INJECTION_AND_WEDGE_CONGRUENCE",
        "SQUARE_SUM": SQUARE_SUM,
        "PROFILE_COUNT": len(profiles),
        "PROFILE_IDENTITIES": [profile_identity(p) for p in profiles],
        "VERTEX_COUNT": K20_TICKET_COUNT,
        "OVERLAP_GRAPH_EDGE_COUNT": edge_count,
        "OVERLAP_GRAPH_DEGREE_INTERVAL": [minimum_degree, maximum_degree],
        "CLIQUE_PARTITION_EDGE_TOTALS": [
            {"COMPONENT_SIZES": list(sizes), "EDGE_COUNT": edges}
            for sizes, edges in clique_partition_edge_totals(
                K20_TICKET_COUNT, minimum_degree, maximum_degree
            )
        ],
        "INDUCED_P3_OPEN_WEDGE_LOWER_BOUND": floor,
        **envelopes[0],
        "GRAPH_PLUS_COMPLEMENT_TRIANGLE_IDENTITY_CONSTANT": complement_identity,
        "COMPLEMENT_TRIANGLE_LOWER_BOUND": complement_identity - triangle_bound,
        "SHARED_VERTEX_SUPPORT_PAIR_COUNT": (SQUARE_SUM - K20_TRIPLE_INCIDENCE_COUNT) // 2,
        "LOOSE_THREE_CYCLE_UPPER_BOUND": triangle_bound - K20_TRIPLE_SUPPORT_COUNT,
        "PASCH_LIKE_FOUR_SUPPORT_UPPER_BOUND": (triangle_bound - K20_TRIPLE_SUPPORT_COUNT) // 4,
        "TRIPLE_SUPPORT_COUNT": K20_TRIPLE_SUPPORT_COUNT,
        "RESIDUAL_DOUBLE_SUPPORT_COUNT": K20_DOUBLE_SUPPORT_COUNT,
        "S4_FLOOR_SCOPE": "ALL_REALIZATIONS_INCLUDING_S3_MAXIMIZERS",
        "S3_UPPER_BOUND": max(row["S3_UPPER_BOUND"] for row in motif_bounds),
        "S4_LOWER_BOUND": min(row["S4_LOWER_BOUND"] for row in motif_bounds),
        "FOURTH_ORDER_CREDIT": min(row["FOURTH_ORDER_CREDIT"] for row in motif_bounds),
        "CLASS_FAMILY_UPPER_BOUND": class_bound,
        "RANKED_COARSE_CLASS_BOUND": plateau.bound,
        "COMPLETE_PLATEAU_COVERAGE": True,
        "CERTIFICATION_STATUS": "CERTIFIED_BELOW_NEXT_DISTINCT_CURSOR",
        "PER_PROFILE_SOLVER_WORK_NEEDED": False,
    }


def recompute_family_bound(
    prior_bounds: Mapping[DegreeProfile, int],
    *,
    class_profiles: Sequence[DegreeProfile],
    class_bound: int,
    next_profile: DegreeProfile,
    next_bound: int,
) -> tuple[int, tuple[DegreeProfile, ...]]:
    """Include every certified envelope; never confuse the cursor with max."""

    assert_no_prior_profile_rerun(prior_bounds, class_profiles)
    if next_profile in prior_bounds or next_profile in class_profiles:
        raise AssertionError("the exact next cursor is already resolved")
    if coarse_profile_envelope(next_profile).family_upper_bound != next_bound:
        raise AssertionError("the next cursor bound does not match its identity")
    ledger = dict(prior_bounds)
    ledger.update(dict.fromkeys(class_profiles, class_bound))
    ledger[next_profile] = next_bound
    family_bound = max(ledger.values())
    owners = tuple(
        sorted((p for p, bound in ledger.items() if bound == family_bound), reverse=True)
    )
    return family_bound, owners


def compute_result(*, proof_wall_seconds: float = MAX_PROOF_WALL_SECONDS) -> dict[str, object]:
    if not 0 < proof_wall_seconds <= MAX_PROOF_WALL_SECONDS:
        raise ValueError("proof wall limit must be in (0, 3600]")
    started = monotonic()
    primitives = canonical_primitive_preflight()
    runtime = solver_runtime_preflight()
    state = current_state()
    plateau = freeze_plateau(state, deadline=started + proof_wall_seconds)
    certificate = certify_plateau_class(plateau)
    class_bound = cast(int, certificate["CLASS_FAMILY_UPPER_BOUND"])
    if plateau.next_profile is None or plateau.next_bound is None:
        raise AssertionError("the packet-pinned next cursor is missing")
    family_bound, owners = recompute_family_bound(
        state.bounds,
        class_profiles=plateau.profiles,
        class_bound=class_bound,
        next_profile=plateau.next_profile,
        next_bound=plateau.next_bound,
    )
    if tuple(profile_identity(p) for p in owners) != EXPECTED_BOUND_OWNERS:
        raise AssertionError("the exact new family-bound owners changed")
    load_bearing_cursor = owners[0]
    success_c = (
        class_bound < plateau.next_bound
        and state.bounds[load_bearing_cursor] == family_bound
        and load_bearing_cursor != state.cursor
    )
    if not success_c:
        raise AssertionError("the closed plateau lacks an exact new load-bearing cursor")
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_STATUS": "SUCCESS_C_PLATEAU_RESOLVED_EXACT_LOAD_BEARING_CURSOR",
        "STOP_REASON": "CURRENT_PLATEAU_RESOLVED_EXACT_NEW_FAMILY_MAX_CURSOR",
        "START_BOUND": START_BOUND,
        "PLATEAU_COUNT_PROCESSED": 1,
        "CURRENT_PLATEAU_PROFILE_COUNT": len(plateau.profiles),
        "CURRENT_LOAD_BEARING_PLATEAU": [profile_identity(p) for p in plateau.profiles],
        "PROFILE_COUNT_PROCESSED": 0,
        "CLASSES_ANALYZED": 1,
        "CLASSES_CERTIFIED": 1,
        "PROFILES_ELIMINATED_BY_CLASS_BOUND": len(plateau.profiles),
        "CLASS_CERTIFICATES": [certificate],
        "NEXT_ACTIVE_BOUND": plateau.next_bound,
        "NEXT_ACTIVE_PROFILE": profile_identity(plateau.next_profile),
        "NEXT_ACTIVE_PROFILE_ROLE": "UNRESOLVED_RANKED_PREFIX",
        "NEXT_ACTIVE_CURSOR_IS_LOAD_BEARING": family_bound == plateau.next_bound,
        "NEW_LOAD_BEARING_CURSOR_BOUND": state.bounds[load_bearing_cursor],
        "NEW_LOAD_BEARING_CURSOR_PROFILE": profile_identity(load_bearing_cursor),
        "NEW_LOAD_BEARING_CURSOR_SOURCE": state.sources[load_bearing_cursor],
        "NEW_LOAD_BEARING_CURSOR_TIED_PROFILES": [profile_identity(p) for p in owners],
        "CURRENT_PLATEAU_COMPLETELY_RESOLVED": True,
        "PACKET_SUCCESS_A_SATISFIED": family_bound <= INCUMBENT,
        "PACKET_SUCCESS_B_SATISFIED": START_BOUND - family_bound >= 50_000,
        "PACKET_SUCCESS_C_SATISFIED": success_c,
        "SUCCESS_C_CURSOR_DEFINITION": "PROFILE_CARRYING_RECOMPUTED_FAMILY_MAX",
        "FAMILY_UPPER_BOUND": family_bound,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family_bound - INCUMBENT,
        "CERTIFIED_FAMILY_DROP": START_BOUND - family_bound,
        "FAMILY_STATUS": "OPEN_STRICTLY_TIGHTENED_PRIOR_OWNERS_LOAD_BEARING",
        "CURRENT_BOUND_OWNER": profile_identity(owners[0]),
        "CURRENT_BOUND_OWNERS": [profile_identity(p) for p in owners],
        "CURRENT_BOUND_OWNER_KIND": "PRIOR_RESOLVED_PROFILE_TIE",
        "CURRENT_BOUND_OWNER_SOURCES": {profile_identity(p): state.sources[p] for p in owners},
        "PRIOR_RESOLVED_PROFILE_COUNT": len(state.bounds),
        "PRIOR_RESOLVED_OWNER": profile_identity(EXPECTED_OWNER_PROFILE),
        "PRIOR_RESOLVED_OWNER_REUSED_BOUND": state.bounds[EXPECTED_OWNER_PROFILE],
        "PRIOR_PROFILE_RERUN_COUNT": 0,
        "SOLVER_PROFILES_SENT": [],
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "CANONICAL_PRIMITIVES": primitives,
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_STATUS": "NOT_NEEDED_ANALYTIC_CLASS_CERTIFICATE",
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "PROOF_TASK_BUDGET_SECONDS": MAX_PROOF_WALL_SECONDS,
            "ANALYTIC_REPLAY_DEADLINE_SECONDS": proof_wall_seconds,
            "CLASS_ORACLE_NATIVE_SECONDS_PER_HISTOGRAM": CLASS_RELAXATION_WALL_LIMIT_SECONDS,
            "CLASS_ORACLE_NATIVE_DEADLINE_SECONDS": CLASS_ORACLE_NATIVE_DEADLINE_SECONDS,
            "EXTERNAL_CLASS_ORACLE_TIMEOUT_SECONDS": EXTERNAL_CLASS_ORACLE_TIMEOUT_SECONDS,
            "CP_SAT_SEARCH_WORKERS": 1,
            "MAX_PLATEAUS": MAX_PLATEAUS,
            "MAX_NEW_PROFILE_SOLVES": MAX_NEW_PROFILE_SOLVES,
        },
        "SOLVER_ACTUAL_WALL_TIME": 0.0,
        "SOLVER_CERTIFIED_BOUND": None,
        "ANALYTIC_CLASS_CERTIFIED_BOUND": class_bound,
        "ANALYTIC_RESULT_WALL_SECONDS": monotonic() - started,
        "RANK_LOOKUP": {
            "COMPLETE_PROFILES_EXAMINED": plateau.complete_profiles_examined,
            "SQUARE_SUM_CLASSES_EXAMINED": plateau.square_sum_classes_examined,
            "LOOKUP_PROFILE_COUNT": plateau.lookup_profile_count,
        },
        "PER_PROFILE_SUPPORT_MOTIF_S4_SOLVES": "NOT_NEEDED_CLASS_CERTIFICATE_SUFFICIENT",
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        "WORK_BELOW_CURRENT_FAMILY_MAX_STARTED": False,
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def attach_class_oracle(result: dict[str, object], proof: dict[str, object]) -> None:
    """Account for the observed R14 relaxation without using it for closure.

    Every row must cover exactly one frozen profile and reproduce its envelope.
    FEASIBLE rows carry only the best-objective bound; they never contribute an
    incumbent objective as a lower bound. The analytic certificate sets the
    production research result regardless of the oracle's stronger envelope.
    """

    raw_certificate = proof.get("CLASS_CERTIFICATE")
    if not isinstance(raw_certificate, dict):
        raise AssertionError("the oracle proof lacks its class certificate")
    certificate = cast(dict[str, object], raw_certificate)
    if (
        certificate.get("SQUARE_SUM") != SQUARE_SUM
        or certificate.get("COMPLETE_SUFFIX_ENUMERATION") is not True
    ):
        raise AssertionError("the oracle did not cover the complete active class")
    raw_rows = certificate.get("HISTOGRAM_ENVELOPES")
    if not isinstance(raw_rows, list):
        raise AssertionError("the oracle proof lacks histogram rows")
    identities: list[str] = []
    compact_rows: list[str] = []
    family_bounds: list[int] = []
    triangle_bounds: list[int] = []
    solver_wall = 0.0
    for raw_row in cast(list[object], raw_rows):
        if not isinstance(raw_row, dict):
            raise AssertionError("an oracle row is malformed")
        row = cast(dict[str, object], raw_row)
        raw_profile = row.get("PROFILE")
        if not isinstance(raw_profile, list):
            raise AssertionError("an oracle profile is malformed")
        if any(type(d) is not int for d in cast(list[object], raw_profile)):
            raise AssertionError("an oracle profile is malformed")
        profile = tuple(cast(list[int], raw_profile))
        identity = profile_identity(profile)
        status = row.get("RELAXATION_STATUS")
        source = row.get("LOWER_BOUND_SOURCE")
        if (status, source) not in {
            ("OPTIMAL", "OPTIMAL_OBJECTIVE_VALUE"),
            ("FEASIBLE", "BEST_OBJECTIVE_BOUND_FLOOR"),
        }:
            raise AssertionError("the oracle row is not an optimal or certified best bound")
        lower_bound = row.get("WEIGHTED_OPEN_WEDGE_LOWER_BOUND")
        wall = row.get("SOLVER_WALL_TIME_SECONDS")
        if type(lower_bound) is not int or lower_bound < 0 or not isinstance(wall, (int, float)):
            raise AssertionError("an oracle row lacks a certified lower bound or wall time")
        triangle = graph_triangle_upper_bound_from_open_wedges(
            tuple(K20_TICKET_CAPACITY + degree for degree in profile), lower_bound
        )["GRAPH_TRIANGLE_UPPER_BOUND"]
        envelope = profile_family_envelope_from_triangle_bound(profile, triangle)
        bound = envelope["FAMILY_UPPER_BOUND"]
        if row.get("FAMILY_UPPER_BOUND") != bound:
            raise AssertionError("the oracle row's family bound is inconsistent")
        identities.append(identity)
        family_bounds.append(bound)
        triangle_bounds.append(triangle)
        solver_wall += float(wall)
        compact_rows.append(f"{identity}|{status}|{wall}|{lower_bound}|{triangle}|{bound}")
    if (
        len(identities) != EXPECTED_PLATEAU_COUNT
        or len(set(identities)) != len(identities)
        or set(identities) != set(cast(list[str], result["CURRENT_LOAD_BEARING_PLATEAU"]))
    ):
        raise AssertionError("the class-envelope oracle membership is incomplete or duplicated")
    certified_bound = max(family_bounds)
    if (
        certificate.get("CLASS_FAMILY_UPPER_BOUND") != certified_bound
        or certificate.get("GRAPH_TRIANGLE_UPPER_BOUND") != max(triangle_bounds)
        or certified_bound > cast(int, result["ANALYTIC_CLASS_CERTIFIED_BOUND"])
    ):
        raise AssertionError("the oracle contradicts its summary or the analytic envelope")
    result["CLASS_ENVELOPE_ORACLE"] = {
        "STATUS": "PASS",
        "MACHINERY": "R14.certify_square_sum_class / R13.degree_class_open_wedge_relaxation",
        "COMPLETE_PLATEAU_COVERAGE": True,
        "HISTOGRAM_COUNT": len(identities),
        "ROW_ENCODING": (
            "profile|status|solver_seconds|open_wedge_floor|triangle_ceiling|family_bound"
        ),
        "HISTOGRAM_ROWS": compact_rows,
        "CLASS_FAMILY_UPPER_BOUND": certified_bound,
        "GRAPH_TRIANGLE_UPPER_BOUND": max(triangle_bounds),
        "ORACLE_USED_TO_SET_CLOSURE_BOUND": False,
        "ACTUAL_WRAPPED_RUN_SECONDS": proof.get("PROOF_ACTUAL_WALL_SECONDS"),
    }
    result["SOLVER_STATUS"] = (
        "OPTIMAL_CLASS_ENVELOPE_ORACLE"
        if all("|OPTIMAL|" in row for row in compact_rows)
        else "CERTIFIED_BEST_BOUND_CLASS_ENVELOPE_ORACLE"
    )
    result["SOLVER_ACTUAL_WALL_TIME"] = solver_wall
    result["SOLVER_CERTIFIED_BOUND"] = certified_bound


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-wall-seconds", type=float, default=MAX_PROOF_WALL_SECONDS)
    parser.add_argument("--class-oracle-proof", type=Path)
    arguments = parser.parse_args()
    result = compute_result(proof_wall_seconds=arguments.proof_wall_seconds)
    if arguments.class_oracle_proof is not None:
        attach_class_oracle(result, _read_object(arguments.class_oracle_proof))
    result_path().write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "TASK_STATUS",
                    "FAMILY_UPPER_BOUND",
                    "CURRENT_BOUND_OWNERS",
                    "NEXT_ACTIVE_PROFILE",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
