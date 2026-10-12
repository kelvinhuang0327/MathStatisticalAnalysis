"""Close the K20 min-S2 cursor class, then chase the actual family maximum (R28).

Authority is the sealed R26 crossover result at ec95e55c, pinned by SHA-256.
Its INFEASIBLE proofs are replayed without solving onto R26's own replayed
start, which reproduces the complete 408-row ledger. The R25 square-sum-318
class aggregate is expanded to its exact members by ranked lookup, with no
solve. The incomplete R27 worktree based on 809d566e is never read.

Phase 1 freezes the complete coarse plateau at the unresolved cursor. Phase 2
applies the R18/R23 induced-P3 class certificate (open-wedge floor 5, lifted by
the wedge congruence) to the whole plateau with zero individual solves. Any
member the class bound leaves at the cursor bound remains a residual owner for
Phase 3. Phase 4 recomputes the family maximum after every certified change
and works only on its current owners:

* an unresolved cursor: freeze its plateau and apply the class certificate;
* resolved owners, including class-envelope members: R26's closed-form
  full-ticket lemma, else the exact-support open-wedge refutation. A signature
  group is tried as one union first, then one member at a time. Each target is
  the Success-B depth first, then the shallowest cap that leaves the owner set,
  then bisection between them.

Only INFEASIBLE certifies a cap. FEASIBLE, UNKNOWN and timeouts never change a
bound, every target cap is strictly below the current certificate cap, and a
failed target is never repeated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from importlib import import_module
from itertools import combinations
from pathlib import Path
from time import monotonic, time
from typing import Any, cast

from . import b649_k20_min_s2_six_owner_batch_refinement_r26 as batch
from . import b649_k20_min_s2_six_owner_cursor_crossover_r26 as r26
from .b649_k20_min_s2_class_dominance_or_descent_r13 import (
    graph_triangle_upper_bound_from_open_wedges,
    profile_family_envelope_from_triangle_bound,
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import solver_runtime_preflight
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import canonical_primitive_preflight
from .b649_k20_min_s2_cursor_plateau_closure_r18 import generic_open_wedge_floor
from .b649_k20_min_s2_dangerous_core_realizability_r5 import K20_REUSED_S4_LOWER_BOUND
from .b649_k20_min_s2_higher_order_closure_r2 import (
    K20_S1,
    K20_S2,
    k20_min_s2_s4_lower_bound_certificate,
)
from .b649_k20_min_s2_load_bearing_plateau_descent_r16 import (
    PlateauFrontier,
    freeze_current_plateau,
)
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import coarse_profile_envelope
from .b649_k20_min_s2_next_distinct_plateau_r10 import SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_DOUBLE_SUPPORT_COUNT,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
)
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    bound_from_cap,
    decode_profile,
    profile_id,
    support_witness,
)
from .b649_k20_min_s2_successive_class_dominance_r14 import lookup_ranked_frontier

DegreeProfile = tuple[int, ...]
Pair = tuple[int, int]
Triple = tuple[int, int, int]
Solve = tuple[tuple[DegreeProfile, ...], int]
Prover = Callable[[Sequence[Solve], float, Collection[DegreeProfile]], list[dict[str, object]]]

TASK_ID = "B649_K20_MIN_S2_CURRENT_CURSOR_CLASS_OWNER_CHASE_R28"
TASK_BRANCH = "codex/b649-k20-min-s2-current-cursor-class-owner-chase-r28"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "ec95e55cb9a22bcd5da2178cd929e69f93be48b6"
BASE_TREE = "9a94f77f8ac09fe383b602a8001c080722214e77"
R26_RESULT = r26.RESULT_FILENAME
R26_RESULT_SHA256 = "3a809bff908adf1d015a79281589f3a4426d0f2615f5489cfa1576ab33ca8fc9"
R25_RESULT = batch.R25_FILENAME
STALE_R27_BASE_HEAD = "809d566e6274d150da4531b2772e07d6218cd044"
STALE_R27_MARKERS = (
    "min_s2_current_cursor_dynamic_closure_r27",
    "min-s2-current-cursor-dynamic-closure-r27",
)
START_BOUND = 313_637_848
START_CURSOR = decode_profile("66666665422221111111")
START_MAX_RESOLVED = 313_637_736
START_LEDGER_COUNT = 408
INCUMBENT = 313_239_661
SUCCESS_B_DROP = 25_000
SUCCESS_B_TARGET = START_BOUND - SUCCESS_B_DROP
FROZEN_SQUARE_SUM = 318
FROZEN_COUNT = 76
FROZEN_COARSE_BOUND = 313_652_520
FROZEN_BOUND = 313_628_776
FROZEN_CAP = 272
EXPECTED_PLATEAU_COUNT = 74
EXPECTED_NEXT_CURSOR = decode_profile("66666665332221111111")
EXPECTED_NEXT_BOUND = 313_635_048
EXPECTED_CLASS_BOUND = 313_625_976
EDGE_COUNT = 3 * K20_TRIPLE_SUPPORT_COUNT + K20_DOUBLE_SUPPORT_COUNT
RESULT_DIRECTORY = batch.RESULT_DIRECTORY
RESULT_FILENAME = "b649-k20-min-s2-current-cursor-class-owner-chase-r28-result.json"
MODULE_NAME = "lottolab.research.b649_k20_min_s2_current_cursor_class_owner_chase_r28"
CP_SAT_WORKERS = 8
PROOF_WALL_SECONDS = 3_600.0
UNION_SECONDS = 10.0
MEMBER_SECONDS = 60.0
RETRY_SECONDS = 240.0
CHECK_SECONDS = 30.0
PLATEAU_LOOKUP_SECONDS = 120.0
EXTERNAL_GRACE_SECONDS = 15.0
EXTERNAL_KILL_SECONDS = 5
ROUTE_A = r26.ROUTE_A
ROUTE_D = r26.ROUTE_D
KIND_A = r26.KIND_A
ROUTE_CLASS = "R18_INDUCED_P3_INJECTION_AND_WEDGE_CONGRUENCE"
ROUTE_RESIDUAL = "COARSE_RANKED_ENVELOPE_RESIDUAL"
CURSOR_OWNER = "UNRESOLVED_CURSOR_PLATEAU"
CLASS_OWNER = "CLASS_ENVELOPE_RESOLVED_PROFILE"
RESOLVED_OWNER = "RESOLVED_PROFILE"
SUCCESS_A = "SUCCESS_A_FAMILY_CLOSED"
SUCCESS_B = "SUCCESS_B_CERTIFIED_FAMILY_DROP_AT_LEAST_25000"
SUCCESS_C = "SUCCESS_C_BUDGET_END_EXACT_OWNER_AND_FRONTIER"
STOPPED = "STOPPED_CURRENT_OWNER_NOT_TIGHTENED_BY_ROUTES"

object_row = batch.object_row
rows = batch.rows
integer = batch.integer
signature = r26.signature


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def git_blob(relative: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{BASE_HEAD}:{relative}"], cwd=repo_root())


def assert_not_stale_r27(head: str, names: Iterable[str]) -> None:
    """Reject the superseded R27 base and any R27 file as an input."""

    if head == STALE_R27_BASE_HEAD or head != BASE_HEAD:
        raise AssertionError("stale R27 authority rejected; only ec95e55c is authority")
    if any(marker in name for name in names for marker in STALE_R27_MARKERS):
        raise AssertionError("stale R27 scratch file offered as authority")


def stale_r27_guard() -> dict[str, object]:
    listing = subprocess.check_output(
        [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            BASE_HEAD,
            "src/lottolab/research",
            RESULT_DIRECTORY,
        ],
        cwd=repo_root(),
        text=True,
    ).split()
    assert_not_stale_r27(BASE_HEAD, listing)
    assert_not_stale_r27(BASE_HEAD, (R26_RESULT, R25_RESULT))
    return {
        "STATUS": "PASS",
        "REJECTED_BASE_HEAD": STALE_R27_BASE_HEAD,
        "R27_FILES_AT_BASE_HEAD": 0,
        "R27_SCRATCH_ADOPTED": False,
    }


def r26_authority() -> tuple[dict[str, object], str]:
    blob = git_blob(f"{RESULT_DIRECTORY}/{R26_RESULT}")
    digest = hashlib.sha256(blob).hexdigest()
    if digest != R26_RESULT_SHA256:
        raise AssertionError("ec95e55 R26 authority fingerprint changed")
    result = object_row(json.loads(blob))
    expected: dict[str, object] = {
        "TASK_STATUS": r26.SUCCESS_B,
        "FAMILY_UPPER_BOUND": START_BOUND,
        "MAX_RESOLVED_BOUND": START_MAX_RESOLVED,
        "NEXT_CURSOR_BOUND": START_BOUND,
        "NEXT_CURSOR_PROFILE": profile_id(START_CURSOR),
        "CURRENT_BOUND_OWNER_SET": [profile_id(START_CURSOR)],
        "REMAINING_RESOLVED_ABOVE_CURSOR_COUNT": 0,
        "RESOLVED_LEDGER_COUNT": START_LEDGER_COUNT,
        "CURSOR_PROFILE_SOLVES": 0,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": START_BOUND - INCUMBENT,
        "CURSOR_GENUINELY_LOAD_BEARING": True,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError(f"ec95e55 R26 authority mismatch: {key}")
    return result, digest


def replay_authority(
    result: Mapping[str, object],
) -> tuple[dict[DegreeProfile, int], dict[DegreeProfile, Certificate]]:
    """Replay every sealed R26 crossover proof onto R26's own start, no solving."""

    start = r26.start_state()
    bounds = dict(start.bounds)
    catalog = dict(start.certificates)
    for index, raw in enumerate(rows(result["GROUP_ATTEMPTS"])):
        attempt = object_row(raw)
        if attempt.get("STATUS") != "INFEASIBLE":
            continue
        profiles = tuple(decode_profile(p) for p in rows(attempt["PROFILE_IDS"]))
        cap = integer(attempt["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
        if r26.accepted_cap(attempt, profiles, cap) != cap:
            raise AssertionError("sealed R26 proof identity mismatch")
        for p in profiles:
            cert = catalog[p]
            s3, bound = bound_from_cap(p, cap, integer(cert.s4))
            if bound >= bounds[p] or bound > START_BOUND:
                raise AssertionError("sealed R26 proof does not reproduce its crossing")
            bounds[p] = bound
            catalog[p] = replace(
                cert,
                bound=bound,
                s3=s3,
                triangle_cap=cap,
                source_result=R26_RESULT,
                source_row=f"GROUP_ATTEMPTS[{index}]",
                relaxation=str(attempt["ROUTE"]),
            )
    sealed = {
        decode_profile(row["PROFILE_ID"]): integer(row["CURRENT_BOUND"])
        for row in map(object_row, rows(result["FINAL_RESOLVED_LEDGER"]))
    }
    if (
        sealed != bounds
        or len(bounds) != START_LEDGER_COUNT
        or START_CURSOR in bounds
        or max(bounds.values()) != START_MAX_RESOLVED
        or any(catalog[p].bound != b for p, b in bounds.items())
    ):
        raise AssertionError("R26 replay does not reproduce its sealed 408-row ledger")
    return bounds, catalog


def profile_s4_floor(profile: DegreeProfile) -> int:
    """The R13 profile S4 floor: 112, or the seven-inactive-ticket floor."""

    return max(
        K20_REUSED_S4_LOWER_BOUND,
        SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND if profile.count(0) == 7 else 0,
    )


def frozen_class(bounds: Collection[DegreeProfile]) -> dict[DegreeProfile, Certificate]:
    """Expand the R25 square-sum-318 aggregate to its members by lookup only."""

    blob = git_blob(f"{RESULT_DIRECTORY}/{R25_RESULT}")
    if hashlib.sha256(blob).hexdigest() != batch.R25_SHA256:
        raise AssertionError("pinned R25 class authority changed")
    r25 = object_row(json.loads(blob))
    envelope = object_row(r25["PROFILE_ENVELOPE"])
    if (
        r25.get("PLATEAU_PROFILE_COUNT") != FROZEN_COUNT
        or r25.get("PLATEAU_SQUARE_SUM") != FROZEN_SQUARE_SUM
        or r25.get("PLATEAU_CLASS_BOUND") != FROZEN_BOUND
        or r25.get("INITIAL_CURSOR_BOUND") != FROZEN_COARSE_BOUND
        or r25.get("CERTIFICATE_SCOPE") != "ALL_K20_MIN_S2_PROFILES_WITH_SQUARE_SUM_318"
        or r25.get("NEXT_CURSOR_PROFILE") != profile_id(START_CURSOR)
        or envelope.get("GRAPH_TRIANGLE_UPPER_BOUND") != FROZEN_CAP
        or envelope.get("S4_LOWER_BOUND") != K20_REUSED_S4_LOWER_BOUND
        or envelope.get("FAMILY_UPPER_BOUND") != FROZEN_BOUND
    ):
        raise AssertionError("R25 square-sum-318 class certificate changed")
    frontier = lookup_ranked_frontier(
        start_profile=None,
        start_square_sum=FROZEN_SQUARE_SUM,
        profile_limit=FROZEN_COUNT + 1,
        deadline=monotonic() + PLATEAU_LOOKUP_SECONDS,
        prior_profiles=bounds,
    )
    members = frontier.profiles[:FROZEN_COUNT]
    if (
        len(frontier.profiles) != FROZEN_COUNT + 1
        or frontier.profiles[FROZEN_COUNT] != START_CURSOR
        or any(sum(d * d for d in p) != FROZEN_SQUARE_SUM for p in members)
        or any(e.family_upper_bound != FROZEN_COARSE_BOUND for e in frontier.envelopes[:-1])
    ):
        raise AssertionError("R25 class membership does not end at the current cursor")
    catalog: dict[DegreeProfile, Certificate] = {}
    for p in members:
        s3, bound = bound_from_cap(p, FROZEN_CAP, profile_s4_floor(p))
        motif = profile_family_envelope_from_triangle_bound(p, FROZEN_CAP)
        if bound != FROZEN_BOUND or motif["FAMILY_UPPER_BOUND"] != bound:
            raise AssertionError("R25 class member does not reproduce the class bound")
        catalog[p] = Certificate(
            p,
            bound,
            R25_RESULT,
            "PLATEAU_CERTIFICATE",
            "CLASS_ENVELOPE_ONLY",
            s3,
            profile_s4_floor(p),
            FROZEN_CAP,
            ROUTE_CLASS,
        )
    return catalog


@dataclass
class Chase:
    """Complete family: resolved ledger, expanded classes and one unresolved cursor."""

    bounds: dict[DegreeProfile, int]
    catalog: dict[DegreeProfile, Certificate]
    cursor: DegreeProfile | None
    cursor_bound: int | None
    deadline: float
    attempts: list[dict[str, object]] = field(default_factory=lambda: [])
    steps: list[dict[str, object]] = field(default_factory=lambda: [])
    plateaus: list[dict[str, object]] = field(default_factory=lambda: [])
    sequence: list[dict[str, object]] = field(default_factory=lambda: [])
    nonvacuity: list[dict[str, object]] = field(default_factory=lambda: [])
    failed: dict[Solve, str] = field(default_factory=lambda: {})
    dispatched: list[DegreeProfile] = field(default_factory=lambda: [])
    checked: set[tuple[object, ...]] = field(default_factory=lambda: set())


def family_state(chase: Chase) -> tuple[int, tuple[DegreeProfile, ...]]:
    """Recompute the complete family maximum and its exact owners."""

    if chase.cursor is not None and (chase.cursor in chase.bounds or chase.cursor_bound is None):
        raise AssertionError("the unresolved cursor must stay outside the resolved ledger")
    if set(chase.bounds) != set(chase.catalog) or any(
        chase.catalog[p].bound != b for p, b in chase.bounds.items()
    ):
        raise AssertionError("certificate catalog and family ledger diverged")
    terms = list(chase.bounds.values())
    if chase.cursor_bound is not None:
        terms.append(chase.cursor_bound)
    family = max(terms)
    owners = tuple(sorted((p for p, b in chase.bounds.items() if b == family), reverse=True))
    if chase.cursor is not None and chase.cursor_bound == family:
        owners = (chase.cursor, *owners)
    return family, owners


def owner_type(chase: Chase, profile: DegreeProfile) -> str:
    if profile == chase.cursor:
        return CURSOR_OWNER
    if chase.catalog[profile].realizability == "CLASS_ENVELOPE_ONLY":
        return CLASS_OWNER
    return RESOLVED_OWNER


def record_owner(chase: Chase) -> None:
    family, owners = family_state(chase)
    entry: dict[str, object] = {
        "FAMILY_BOUND": family,
        "OWNER_TYPES": sorted({owner_type(chase, p) for p in owners}),
        "OWNER_COUNT": len(owners),
        "OWNER_IDS": list(map(profile_id, owners)),
    }
    if not chase.sequence or {k: chase.sequence[-1][k] for k in ("FAMILY_BOUND", "OWNER_IDS")} != {
        k: entry[k] for k in ("FAMILY_BOUND", "OWNER_IDS")
    }:
        chase.sequence.append(entry)


def assert_owner_scope(chase: Chase, profiles: Sequence[DegreeProfile]) -> None:
    """Only current family-max resolved owners may enter any solver model."""

    _, owners = family_state(chase)
    if (
        not profiles
        or len(set(profiles)) != len(profiles)
        or any(p not in chase.bounds or p not in owners or p == chase.cursor for p in profiles)
    ):
        raise AssertionError("only current family-max resolved owners may enter a model")


def certify_cursor_plateau(chase: Chase) -> dict[str, object]:
    """Phase 1 and 2 on the current cursor: exact plateau, generic class bound."""

    family, owners = family_state(chase)
    cursor, active = chase.cursor, chase.cursor_bound
    if cursor is None or active is None or active != family or owners[0] != cursor:
        raise AssertionError("only an unresolved cursor that owns the family max is certified")
    plateau: PlateauFrontier = freeze_current_plateau(
        cursor=cursor,
        active_bound=active,
        prior_profiles=chase.bounds,
        deadline=min(chase.deadline, monotonic() + PLATEAU_LOOKUP_SECONDS),
    )
    members = plateau.profiles
    if (
        not members
        or members[0] != cursor
        or len(set(members)) != len(members)
        or any(p in chase.bounds for p in members)
        or any(coarse_profile_envelope(p).family_upper_bound != active for p in members)
        or (plateau.next_bound is not None and plateau.next_bound >= active)
    ):
        raise AssertionError("plateau membership is incomplete or exceeds the active bound")
    floor = generic_open_wedge_floor(
        K20_TICKET_COUNT, EDGE_COUNT, K20_TICKET_CAPACITY, 2 * K20_TICKET_CAPACITY
    )
    envelope = graph_triangle_upper_bound_from_open_wedges(
        tuple(K20_TICKET_CAPACITY + d for d in cursor), floor
    )
    cap = envelope["GRAPH_TRIANGLE_UPPER_BOUND"]
    index = len(chase.plateaus)
    certified: list[DegreeProfile] = []
    residual: list[DegreeProfile] = []
    class_bounds: list[int] = []
    for p in members:
        if (
            graph_triangle_upper_bound_from_open_wedges(
                tuple(K20_TICKET_CAPACITY + d for d in p), floor
            )
            != envelope
        ):
            raise AssertionError("plateau members do not share the class wedge envelope")
        s4 = profile_s4_floor(p)
        s3, bound = bound_from_cap(p, cap, s4)
        if bound < active:
            if profile_family_envelope_from_triangle_bound(p, cap)["FAMILY_UPPER_BOUND"] != bound:
                raise AssertionError("class bound does not reproduce the R13 motif envelope")
            certified.append(p)
        else:
            residual.append(p)
        class_bounds.append(min(bound, active))
        chase.bounds[p] = min(bound, active)
        chase.catalog[p] = Certificate(
            p,
            min(bound, active),
            RESULT_FILENAME,
            f"PLATEAU_CERTIFICATES[{index}]",
            "CLASS_ENVELOPE_ONLY",
            s3,
            s4,
            cap,
            ROUTE_CLASS if bound < active else ROUTE_RESIDUAL,
        )
    chase.cursor, chase.cursor_bound = plateau.next_profile, plateau.next_bound
    after, new_owners = family_state(chase)
    wedges = overlap_wedge_count(cursor)
    row: dict[str, object] = {
        "PLATEAU_INDEX": index,
        "CURSOR_PROFILE": profile_id(cursor),
        "ACTIVE_COARSE_BOUND": active,
        "SQUARE_SUMS": sorted({sum(d * d for d in p) for p in members}),
        "PLATEAU_PROFILE_COUNT": len(members),
        "PLATEAU_PROFILE_IDS": list(map(profile_id, members)),
        "CLASS_CERTIFICATE_KIND": ROUTE_CLASS,
        "INDUCED_P3_OPEN_WEDGE_LOWER_BOUND": floor,
        **envelope,
        "GRAPH_PLUS_COMPLEMENT_TRIANGLE_IDENTITY_CONSTANT": 1140 - 18 * EDGE_COUNT + wedges,
        "NONCORE_TRIANGLE_UPPER_BOUND": cap - K20_TRIPLE_SUPPORT_COUNT,
        "CLASS_FAMILY_UPPER_BOUND": max(class_bounds),
        "CERTIFIED_MEMBER_COUNT": len(certified),
        "RESIDUAL_MEMBER_COUNT": len(residual),
        "RESIDUAL_MEMBER_IDS": list(map(profile_id, residual)),
        "CLASS_DOMINANCE": "COMPLETE" if not residual else "PARTIAL_RESIDUALS_TO_PHASE_3",
        "INDIVIDUAL_SOLVES": 0,
        "NEXT_CURSOR_PROFILE": None
        if plateau.next_profile is None
        else profile_id(plateau.next_profile),
        "NEXT_CURSOR_BOUND": plateau.next_bound,
        "LOOKUP_PROFILE_COUNT": plateau.lookup_profile_count,
        "COMPLETE_PROFILES_EXAMINED": plateau.complete_profiles_examined,
        "SQUARE_SUM_CLASSES_EXAMINED": plateau.square_sum_classes_examined,
        "FAMILY_BOUND_BEFORE": family,
        "FAMILY_BOUND_AFTER": after,
        "OWNER_SET_AFTER": list(map(profile_id, new_owners)),
    }
    chase.plateaus.append(row)
    chase.steps.append(
        {
            "KIND": "CURSOR_PLATEAU_CLASS_CERTIFICATE",
            "PLATEAU_INDEX": index,
            "FAMILY_BOUND_BEFORE": family,
            "FAMILY_BOUND_AFTER": after,
            "OWNER_SET_AFTER": list(map(profile_id, new_owners)),
        }
    )
    return row


def support_union_model(
    profiles: Sequence[DegreeProfile], ceiling: int
) -> tuple[Any, dict[Triple, Any], dict[Pair, Any], list[Any], list[Any]]:
    """R26's exact union support model, without R26's no-cursor scope guard.

    The constraints are identical to ``batch.union_support_model``; R28 may
    model the cursor plateau because it owns the family maximum.
    """

    if not profiles or ceiling < 0:
        raise AssertionError("invalid group model")
    profiles = tuple(decode_profile(list(p)) for p in profiles)
    if len({overlap_wedge_count(p) for p in profiles}) != 1:
        raise AssertionError("group lacks a shared wedge identity")
    cp_model: Any = import_module("ortools.sat.python.cp_model")
    model: Any = cp_model.CpModel()
    degrees = [
        model.NewIntVar(min(p[v] for p in profiles), max(p[v] for p in profiles), f"d{v}")
        for v in range(20)
    ]
    model.AddAllowedAssignments(degrees, profiles)
    active = [v for v in range(20) if any(p[v] for p in profiles)]
    triples = {t: model.NewBoolVar(f"t{t}") for t in combinations(active, 3)}
    doubles = {p: model.NewBoolVar(f"b{p}") for p in combinations(range(20), 2)}
    by_pair: dict[Pair, list[Any]] = {p: [] for p in doubles}
    for t, variable in triples.items():
        for pair in combinations(t, 2):
            by_pair[pair].append(variable)
    for v, degree in enumerate(degrees):
        model.Add(sum(x for t, x in triples.items() if v in t) == degree)
        model.Add(sum(x for p, x in doubles.items() if v in p) == 6 - degree)
    model.Add(sum(triples.values()) == 22)
    model.Add(sum(doubles.values()) == 27)
    edges: dict[Pair, Any] = {}
    for p, double in doubles.items():
        model.Add(sum(by_pair[p]) + double <= 1)
        edges[p] = model.NewBoolVar(f"e{p}")
        model.Add(edges[p] == sum(by_pair[p]) + double)
    indicators: list[Any] = []
    by_ends: dict[Pair, list[Any]] = {p: [] for p in doubles}
    for center in range(20):
        for a, b in combinations((v for v in range(20) if v != center), 2):
            x = model.NewBoolVar(f"o{center}_{a}_{b}")
            model.Add(
                x
                >= edges[(min(center, a), max(center, a))]
                + edges[(min(center, b), max(center, b))]
                - edges[(a, b)]
                - 1
            )
            indicators.append(x)
            by_ends[(a, b)].append(x)
    for (a, b), edge in edges.items():
        model.Add(sum(by_ends[(a, b)]) >= degrees[a] + degrees[b] - 6).OnlyEnforceIf(edge.Not())
    model.Add(sum(indicators) <= ceiling)
    return model, triples, doubles, degrees, indicators


def solve_group(
    profiles: Sequence[DegreeProfile], cap: int, seconds: float, workers: int
) -> dict[str, object]:
    wedge = overlap_wedge_count(profiles[0])
    ceiling = wedge - 3 * (cap + 1)
    model, _, _, _, indicators = support_union_model(profiles, ceiling)
    solver = r26.configured_solver(seconds, workers)
    status = str(solver.StatusName(solver.Solve(model)))
    return {
        "ROUTE": ROUTE_A,
        "STATUS": status,
        "CERTIFICATE_KIND": KIND_A if status == "INFEASIBLE" else "NOT_CERTIFIED",
        "PROFILE_IDS": list(map(profile_id, profiles)),
        "WEDGE_COUNT": wedge,
        "REFUTED_GRAPH_TRIANGLE_COUNT": cap + 1,
        "OPEN_WEDGE_CEILING_REFUTED": ceiling,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": cap if status == "INFEASIBLE" else None,
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": ceiling + 1 if status == "INFEASIBLE" else None,
        "OPEN_WEDGE_INDICATOR_COUNT": len(indicators),
        "CP_SAT_SEARCH_WORKERS": workers,
        "SOLVER_WALL_TIME_SECONDS": float(solver.WallTime()),
        "SOLVER_CONFIGURED_WALL_LIMIT": seconds,
    }


def witness_nonvacuity(cert: Certificate) -> dict[str, object]:
    """The proof configuration must realize, and pin exactly, a committed witness."""

    triples, doubles = support_witness(cert)
    edges = {tuple(sorted(p)) for t in triples for p in combinations(t, 2)} | set(doubles)
    triangles = sum(all(p in edges for p in combinations(t, 2)) for t in combinations(range(20), 3))
    count = overlap_wedge_count(cert.profile) - 3 * triangles
    statuses: dict[str, str] = {}
    for label, ceiling, fixed in (
        ("UNFIXED_AT_WITNESS_COUNT", count, False),
        ("FIXED_AT_WITNESS_COUNT", count, True),
        ("FIXED_ONE_BELOW", count - 1, True),
    ):
        model, tv, dv, degrees, _ = support_union_model((cert.profile,), ceiling)
        if fixed:
            for v, d in zip(degrees, cert.profile, strict=True):
                model.Add(v == d)
            for t, v in tv.items():
                model.Add(v == int(t in triples))
            for p, v in dv.items():
                model.Add(v == int(p in doubles))
        solver = r26.configured_solver(CHECK_SECONDS, CP_SAT_WORKERS)
        statuses[label] = str(solver.StatusName(solver.Solve(model)))
    if (
        statuses["UNFIXED_AT_WITNESS_COUNT"] not in ("OPTIMAL", "FEASIBLE")
        or statuses["FIXED_AT_WITNESS_COUNT"] != "OPTIMAL"
        or statuses["FIXED_ONE_BELOW"] != "INFEASIBLE"
    ):
        raise AssertionError("proof configuration fails committed witness nonvacuity")
    return {
        "STATUS": "PASS",
        "PROFILE_ID": profile_id(cert.profile),
        "WITNESS_OPEN_WEDGES": count,
        "STATUSES": statuses,
        "CP_SAT_SEARCH_WORKERS": CP_SAT_WORKERS,
    }


def batch_child(request: Mapping[str, object]) -> None:
    """Solve a list of owner refutations, one JSON line per completed solve."""

    owners = {decode_profile(p) for p in rows(request["OWNERS"])}
    seconds = float(cast(float, request["SECONDS"]))
    deadline = float(cast(float, request["DEADLINE_UNIX"]))
    for raw in rows(request["SOLVES"]):
        solve = object_row(raw)
        profiles = tuple(decode_profile(p) for p in rows(solve["PROFILES"]))
        if not profiles or not set(profiles) <= owners:
            raise AssertionError("child received a profile outside the current owner set")
        remaining = deadline - time() - 1.0
        if remaining <= 0:
            proof: dict[str, object] = {
                "STATUS": "PROOF_BUDGET_EXHAUSTED",
                "PROFILE_IDS": list(map(profile_id, profiles)),
            }
        else:
            proof = solve_group(
                profiles, integer(solve["CAP"]), min(seconds, remaining), CP_SAT_WORKERS
            )
        print(json.dumps(proof), flush=True)


def bounded_batch(
    solves: Sequence[Solve], seconds: float, owners: Collection[DegreeProfile], deadline: float
) -> list[dict[str, object]]:
    """Run solves in one child under native limits and one external hard timeout."""

    remaining = deadline - monotonic() - EXTERNAL_GRACE_SECONDS - 1.0
    if remaining <= 0:
        return [
            {"STATUS": "PROOF_BUDGET_EXHAUSTED", "PROFILE_IDS": list(map(profile_id, s[0]))}
            for s in solves
        ]
    external = min(len(solves) * (seconds + 5.0), remaining) + EXTERNAL_GRACE_SECONDS
    request = {
        "SOLVES": [{"PROFILES": list(map(profile_id, s[0])), "CAP": s[1]} for s in solves],
        "SECONDS": seconds,
        "DEADLINE_UNIX": time() + min(len(solves) * (seconds + 5.0), remaining),
        "OWNERS": list(map(profile_id, owners)),
    }
    env = {
        **os.environ,
        "PYTHONPATH": str(repo_root() / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
    started = monotonic()
    completed = subprocess.run(
        [
            "timeout",
            "--signal=TERM",
            f"--kill-after={EXTERNAL_KILL_SECONDS}s",
            f"{external}s",
            sys.executable,
            "-m",
            MODULE_NAME,
            "--batch-child",
            json.dumps(request),
        ],
        cwd=repo_root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    lines: list[dict[str, object]] = []
    for line in completed.stdout.splitlines():
        try:
            lines.append(object_row(json.loads(line)))
        except (json.JSONDecodeError, AssertionError):
            break
    proofs: list[dict[str, object]] = []
    for index, solve in enumerate(solves):
        proof: dict[str, object]
        if index < len(lines) and lines[index].get("PROFILE_IDS") == list(
            map(profile_id, solve[0])
        ):
            proof = lines[index]
        else:
            proof = {
                "STATUS": "EXTERNAL_TIMEOUT"
                if completed.returncode in (124, 137)
                else "CHILD_FAILURE",
                "PROFILE_IDS": list(map(profile_id, solve[0])),
                "ERROR": completed.stderr[-2000:],
            }
        proof.update(
            {
                "EXTERNAL_HARD_TIMEOUT_SECONDS": external,
                "EXTERNAL_TIMEOUT_EXIT_CODE": completed.returncode,
                "BATCH_SIZE": len(solves),
                "BATCH_SUBPROCESS_WALL_SECONDS": monotonic() - started,
            }
        )
        proofs.append(proof)
    return proofs


def competing_bound(chase: Chase, members: Collection[DegreeProfile]) -> int:
    """The largest family term outside ``members``, the cursor included."""

    others = [b for p, b in chase.bounds.items() if p not in members]
    if chase.cursor_bound is not None:
        others.append(chase.cursor_bound)
    return max(others, default=0)


def cap_bound(cert: Certificate, cap: int) -> int:
    return bound_from_cap(cert.profile, cap, integer(cert.s4))[1]


def target_caps(cert: Certificate, competitor: int) -> tuple[int, int]:
    """Success-B depth, and the shallowest cap that leaves the owner set."""

    cap = integer(cert.triangle_cap)
    goal = max(competitor, SUCCESS_B_TARGET)
    shallow = cap - 1
    while shallow > K20_TRIPLE_SUPPORT_COUNT and (
        cap_bound(cert, shallow) > goal or cap_bound(cert, shallow) >= cert.bound
    ):
        shallow -= 1
    deep = shallow
    while deep > K20_TRIPLE_SUPPORT_COUNT and cap_bound(cert, deep) > SUCCESS_B_TARGET:
        deep -= 1
    return deep, shallow


def dispatch(
    chase: Chase,
    solves: Sequence[Solve],
    seconds: float,
    prove: Prover,
    stage: str,
) -> list[dict[str, object]]:
    """Lemma first, then the solver; every solve must target a current owner."""

    out: dict[int, dict[str, object]] = {}
    pending: list[int] = []
    for index, (profiles, cap) in enumerate(solves):
        assert_owner_scope(chase, profiles)
        if (profiles, cap) in chase.failed:
            raise AssertionError("a failed target is never repeated")
        if any(cap >= integer(chase.catalog[p].triangle_cap) for p in profiles):
            raise AssertionError("no committed or weaker cap is ever re-proved")
        lemma = r26.lemma_proof(profiles, cap)
        if lemma is not None:
            out[index] = lemma
        else:
            pending.append(index)
    if pending:
        _, owners = family_state(chase)
        proofs = prove([solves[i] for i in pending], seconds, owners)
        if len(proofs) != len(pending):
            raise AssertionError("prover returned the wrong number of proofs")
        for index, proof in zip(pending, proofs, strict=True):
            out[index] = proof
            chase.dispatched.extend(p for p in solves[index][0] if p not in chase.dispatched)
    results: list[dict[str, object]] = []
    for index, (profiles, cap) in enumerate(solves):
        cert = chase.catalog[profiles[0]]
        proof = out[index]
        chase.attempts.append(
            {
                "STAGE": stage,
                "GROUP_SIZE": len(profiles),
                "CURRENT_BOUND": cert.bound,
                "CURRENT_TRIANGLE_CAP": cert.triangle_cap,
                "TARGET_TRIANGLE_CAP": cap,
                "TARGET_BOUND": cap_bound(cert, cap),
                "SUCCESS_B_TARGET": SUCCESS_B_TARGET,
                **proof,
            }
        )
        results.append(proof)
    return results


def apply_proof(chase: Chase, solve: Solve, proof: Mapping[str, object]) -> bool:
    """Adopt one INFEASIBLE certificate and recompute the complete family max."""

    profiles, cap = solve
    if r26.accepted_cap(proof, profiles, cap) is None:
        chase.failed[solve] = str(proof.get("STATUS"))
        return False
    assert_owner_scope(chase, profiles)
    before, _ = family_state(chase)
    index = next(
        i
        for i in range(len(chase.attempts) - 1, -1, -1)
        if chase.attempts[i].get("PROFILE_IDS") == list(map(profile_id, profiles))
        and chase.attempts[i].get("TARGET_TRIANGLE_CAP") == cap
    )
    for p in profiles:
        cert = chase.catalog[p]
        s3, bound = bound_from_cap(p, cap, integer(cert.s4))
        if cap >= integer(cert.triangle_cap) or bound >= chase.bounds[p]:
            raise AssertionError("certificate does not tighten its profile")
        chase.bounds[p] = bound
        chase.catalog[p] = replace(
            cert,
            bound=bound,
            s3=s3,
            triangle_cap=cap,
            source_result=RESULT_FILENAME,
            source_row=f"ATTEMPTS[{index}]",
            relaxation=str(proof["ROUTE"]),
        )
    after, owners = family_state(chase)
    chase.steps.append(
        {
            "KIND": "OWNER_REFUTATION",
            "ATTEMPT_INDEX": index,
            "PROFILE_IDS": list(map(profile_id, profiles)),
            "ROUTE": proof["ROUTE"],
            "TRIANGLE_CAP": cap,
            "NEW_BOUND": chase.bounds[profiles[0]],
            "FAMILY_BOUND_BEFORE": before,
            "FAMILY_BOUND_AFTER": after,
            "FAMILY_MAX_CHANGED": after < before,
            "OWNER_SET_AFTER": list(map(profile_id, owners)),
        }
    )
    record_owner(chase)
    return True


def refine_group(
    chase: Chase,
    group: Sequence[Certificate],
    prove: Prover,
    check: Callable[[Certificate], dict[str, object]],
) -> list[DegreeProfile]:
    """Union first, then members: Success-B depth, then bisection to the exit cap.

    Returns the members left untightened.
    """

    members = tuple(c.profile for c in group)
    assert_owner_scope(chase, members)
    key = tuple(signature(group[0]))
    if key not in chase.checked:
        chase.checked.add(key)
        witness = next((c for c in group if c.witness_row is not None), None)
        if witness is not None:
            chase.nonvacuity.append(check(witness))
    deep, _ = target_caps(group[0], competing_bound(chase, members))
    if len(members) > 1 and (members, deep) not in chase.failed:
        solve = (members, deep)
        if apply_proof(chase, solve, dispatch(chase, [solve], UNION_SECONDS, prove, "UNION")[0]):
            return []
    pending = list(members)
    exit_caps = {
        p: target_caps(chase.catalog[p], competing_bound(chase, pending))[1] for p in pending
    }
    low = {p: deep - 1 for p in pending}
    high = {p: exit_caps[p] + 1 for p in pending}
    proofs_held: dict[DegreeProfile, dict[str, object]] = {}
    stage = "MEMBER_DEEP"
    while monotonic() < chase.deadline - EXTERNAL_GRACE_SECONDS - 1:
        probes: list[Solve] = []
        for p in pending:
            while low[p] + 1 < high[p]:
                probe = deep if low[p] < deep else (low[p] + high[p]) // 2
                if ((p,), probe) in chase.failed:
                    low[p] = probe
                    continue
                probes.append(((p,), probe))
                break
        if not probes:
            break
        results = dispatch(chase, probes, MEMBER_SECONDS, prove, stage)
        stage = "MEMBER_BISECTION"
        for solve, proof in zip(probes, results, strict=True):
            (p,), cap = solve
            if r26.accepted_cap(proof, (p,), cap) is not None:
                high[p] = cap
                proofs_held[p] = proof
            else:
                chase.failed[solve] = str(proof.get("STATUS"))
                low[p] = cap
    for p in pending:
        retry = ((p,), exit_caps[p])
        if (
            p in proofs_held
            or chase.failed.get(retry) not in ("UNKNOWN", "EXTERNAL_TIMEOUT")
            or monotonic() >= chase.deadline - EXTERNAL_GRACE_SECONDS - RETRY_SECONDS
        ):
            continue
        del chase.failed[retry]
        proof = dispatch(chase, [retry], RETRY_SECONDS, prove, "MEMBER_RETRY")[0]
        if r26.accepted_cap(proof, (p,), exit_caps[p]) is not None:
            high[p] = exit_caps[p]
            proofs_held[p] = proof
        else:
            chase.failed[retry] = str(proof.get("STATUS"))
    for p in sorted(proofs_held, reverse=True):
        apply_proof(chase, ((p,), high[p]), proofs_held[p])
    return [p for p in pending if p not in proofs_held]


def run_chase(
    chase: Chase, prove: Prover, check: Callable[[Certificate], dict[str, object]]
) -> tuple[str, tuple[DegreeProfile, ...]]:
    """Phase 4: work only on the current family maximum until A, B or C."""

    while True:
        record_owner(chase)
        family, owners = family_state(chase)
        if family <= INCUMBENT:
            return SUCCESS_A, ()
        if START_BOUND - family >= SUCCESS_B_DROP:
            return SUCCESS_B, ()
        if monotonic() >= chase.deadline - EXTERNAL_GRACE_SECONDS - 1:
            return SUCCESS_C, ()
        if chase.cursor is not None and owners[0] == chase.cursor:
            certify_cursor_plateau(chase)
            continue
        stuck: list[DegreeProfile] = []
        for group in r26.signature_groups(chase.catalog[p] for p in owners):
            stuck = refine_group(chase, group, prove, check)
            if stuck:
                break
        if stuck:
            return (
                SUCCESS_C
                if monotonic() >= chase.deadline - EXTERNAL_GRACE_SECONDS - RETRY_SECONDS
                else STOPPED
            ), tuple(stuck)


def start_chase(deadline: float) -> tuple[Chase, dict[str, object], dict[str, str]]:
    """Authority replay, frozen class expansion and the Phase 1 assertions."""

    result, digest = r26_authority()
    bounds, catalog = replay_authority(result)
    frozen = frozen_class(bounds)
    if set(frozen) & set(bounds):
        raise AssertionError("frozen class overlaps the resolved ledger")
    bounds.update({p: c.bound for p, c in frozen.items()})
    catalog.update(frozen)
    chase = Chase(bounds, catalog, START_CURSOR, START_BOUND, deadline)
    family, owners = family_state(chase)
    above = [p for p, b in bounds.items() if b > START_BOUND]
    if (
        family != START_BOUND
        or owners != (START_CURSOR,)
        or above
        or max(b for p, b in bounds.items() if p not in frozen) != START_MAX_RESOLVED
    ):
        raise AssertionError("current cursor is not the unique load-bearing owner")
    assertions: dict[str, object] = {
        "CURSOR_IS_UNIQUE_START_OWNER": True,
        "RESOLVED_ABOVE_CURSOR_COUNT": len(above),
        "MAX_RESOLVED_BOUND": START_MAX_RESOLVED,
        "MAX_RESOLVED_GAP_TO_CURSOR": START_BOUND - START_MAX_RESOLVED,
        "FROZEN_R25_CLASS_MEMBERS_EXPANDED": len(frozen),
        "FROZEN_R25_CLASS_BOUND": FROZEN_BOUND,
        "COMPLETE_FAMILY_TERM_COUNT": len(bounds) + 1,
    }
    hashes = {
        f"{RESULT_DIRECTORY}/{R26_RESULT}": digest,
        f"{RESULT_DIRECTORY}/{R25_RESULT}": batch.R25_SHA256,
    }
    return chase, assertions, hashes


def model_identity() -> dict[str, object]:
    """R28's cursor-capable model equals R26's model on a non-cursor profile."""

    probe = decode_profile("66665555554440000000")
    ours: Any = support_union_model((probe,), 30)[0]
    theirs: Any = batch.union_support_model((probe,), 30)[0]
    digests = [hashlib.sha256(str(m.Proto()).encode()).hexdigest() for m in (ours, theirs)]
    if digests[0] != digests[1]:
        raise AssertionError("R28 support model diverged from the committed R26 model")
    return {
        "STATUS": "PASS",
        "PROBE_PROFILE": profile_id(probe),
        "CEILING": 30,
        "MODEL_PROTO_TEXT_SHA256": digests[0],
    }


def owner_rows(chase: Chase, owners: Sequence[DegreeProfile]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for p in owners:
        if p == chase.cursor:
            out.append(
                {
                    "PROFILE_ID": profile_id(p),
                    "OWNER_TYPE": CURSOR_OWNER,
                    "CURRENT_BOUND": chase.cursor_bound,
                    "BOUND_SOURCE": "R8_COARSE_PROFILE_ENVELOPE",
                }
            )
        else:
            out.append(
                {"OWNER_TYPE": owner_type(chase, p), **batch.certificate_row(chase.catalog[p])}
            )
    return out


def compute_result(
    prove: Prover | None = None,
    check: Callable[[Certificate], dict[str, object]] = witness_nonvacuity,
    proof_wall_seconds: float = PROOF_WALL_SECONDS,
) -> dict[str, object]:
    if not 0 < proof_wall_seconds <= PROOF_WALL_SECONDS:
        raise ValueError("proof wall limit must be in (0, 3600]")
    started_epoch = time()
    started = monotonic()
    deadline = started + proof_wall_seconds
    primitives = canonical_primitive_preflight()
    runtime = solver_runtime_preflight()
    s4 = k20_min_s2_s4_lower_bound_certificate()
    if (K20_S1, K20_S2, s4.s4_lower_bound) != (372_228_640, 63_838_600, 112):
        raise AssertionError("canonical primitive/S4 preflight changed")
    if coarse_profile_envelope(START_CURSOR).family_upper_bound != START_BOUND:
        raise AssertionError("cursor coarse arithmetic changed")
    stale = stale_r27_guard()
    identity = model_identity()
    chase, assertions, hashes = start_chase(deadline)
    record_owner(chase)
    plateau = certify_cursor_plateau(chase)
    if (
        plateau["PLATEAU_PROFILE_COUNT"] != EXPECTED_PLATEAU_COUNT
        or plateau["CLASS_FAMILY_UPPER_BOUND"] != EXPECTED_CLASS_BOUND
        or plateau["RESIDUAL_MEMBER_COUNT"] != 0
        or plateau["NEXT_CURSOR_PROFILE"] != profile_id(EXPECTED_NEXT_CURSOR)
        or plateau["NEXT_CURSOR_BOUND"] != EXPECTED_NEXT_BOUND
        or plateau["SQUARE_SUMS"] != [316]
    ):
        raise AssertionError("current plateau membership or class certificate changed")

    def solver(
        solves: Sequence[Solve], seconds: float, owners: Collection[DegreeProfile]
    ) -> list[dict[str, object]]:
        print(
            f"{len(solves)} solve(s) at {[s[1] for s in solves][:3]} "
            f"family {family_state(chase)[0]}",
            file=sys.stderr,
            flush=True,
        )
        return bounded_batch(solves, seconds, owners, deadline)

    status, stuck = run_chase(chase, prove or solver, check)
    family, owners = family_state(chase)
    unions = [a for a in chase.attempts if a.get("STAGE") == "UNION"]
    statuses = Counter(str(a.get("STATUS")) for a in chase.attempts)
    final_types = sorted({owner_type(chase, p) for p in owners})
    result: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_STATUS": status,
        "INPUT_AUTHORITY": "EC95E55C_R26_SEALED_RESULT_REPLAYED_PLUS_PINNED_R25_CLASS",
        "AUTHORITY_FINGERPRINT": {
            "R26_RESULT_SHA256": R26_RESULT_SHA256,
            "R26_REPLAY_REPRODUCES_SEALED_LEDGER": True,
            "R26_LEDGER_COUNT": START_LEDGER_COUNT,
        },
        "COMMITTED_INPUT_SHA256": hashes,
        "STALE_R27_GUARD": stale,
        "MODEL_IDENTITY": identity,
        "START_BOUND": START_BOUND,
        "START_CURSOR_PROFILE": profile_id(START_CURSOR),
        "PHASE1_ASSERTIONS": assertions,
        "PLATEAU_PROFILE_COUNT": plateau["PLATEAU_PROFILE_COUNT"],
        "CURRENT_PLATEAU": plateau["PLATEAU_PROFILE_IDS"],
        "PHASE2_CLASS_CERTIFICATE": plateau,
        "PHASE3_PROFILE_FALLBACK": "NOT_REQUIRED_CLASS_DOMINANCE_COMPLETE",
        "PLATEAUS_PROCESSED": len(chase.plateaus),
        "PLATEAU_CERTIFICATES": chase.plateaus,
        "CLASSES_CERTIFIED": sum(r["CLASS_DOMINANCE"] == "COMPLETE" for r in chase.plateaus)
        + sum(a.get("STATUS") == "INFEASIBLE" for a in unions),
        "UNION_CLASS_ATTEMPTS": len(unions),
        "PROFILES_PROCESSED": len(chase.dispatched),
        "PROFILES_PROCESSED_SCOPE": "DISTINCT_PROFILES_SENT_TO_A_SOLVER_MODEL",
        "OWNER_CLASS_SEQUENCE": chase.sequence,
        "OWNER_TRANSITION_COUNT": len(chase.sequence) - 1,
        "GROUP_ATTEMPTS": chase.attempts,
        "REFINEMENT_STEPS": chase.steps,
        "WITNESS_NONVACUITY": chase.nonvacuity,
        "FAMILY_UPPER_BOUND": family,
        "FINAL_BOUND_OWNER_TYPE": final_types[0] if len(final_types) == 1 else final_types,
        "FINAL_BOUND_OWNER_IDS": list(map(profile_id, owners)),
        "FINAL_BOUND_OWNERS": owner_rows(chase, owners),
        "UNTIGHTENED_OWNER_IDS": list(map(profile_id, stuck)),
        "MAX_RESOLVED_BOUND": max(chase.bounds.values()),
        "NEXT_ACTIVE_BOUND": chase.cursor_bound,
        "NEXT_ACTIVE_PROFILE": None if chase.cursor is None else profile_id(chase.cursor),
        "NEXT_COMPETING_BOUND": competing_bound(chase, owners),
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family - INCUMBENT,
        "CERTIFIED_FAMILY_DROP": START_BOUND - family,
        "SUCCESS_B_TARGET": SUCCESS_B_TARGET,
        "FAMILY_STATUS": "CLOSED"
        if status == SUCCESS_A
        else "OPEN_STRICTLY_TIGHTENED"
        if family < START_BOUND
        else "OPEN",
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "CANONICAL_PRIMITIVES": primitives,
        "S4_CERTIFIED_FLOOR": s4.s4_lower_bound,
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_STATUS": dict(sorted(statuses.items())),
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "UNION_NATIVE_SECONDS": UNION_SECONDS,
            "MEMBER_NATIVE_SECONDS": MEMBER_SECONDS,
            "RETRY_NATIVE_SECONDS": RETRY_SECONDS,
            "CHECK_NATIVE_SECONDS": CHECK_SECONDS,
            "EXTERNAL_GRACE_SECONDS": EXTERNAL_GRACE_SECONDS,
            "EXTERNAL_KILL_AFTER_SECONDS": EXTERNAL_KILL_SECONDS,
            "PROOF_WALL_SECONDS": proof_wall_seconds,
            "CP_SAT_SEARCH_WORKERS": CP_SAT_WORKERS,
        },
        "SOLVER_ACTUAL_WALL_TIME": sum(
            float(cast(float, a.get("SOLVER_WALL_TIME_SECONDS") or 0.0)) for a in chase.attempts
        ),
        "SOLVER_CERTIFIED_BOUND": family,
        "SOLVER_CERTIFIED_BOUND_SCOPE": "COMPLETE_FAMILY_LEDGER_PLUS_UNRESOLVED_CURSOR",
        "FINAL_RESOLVED_LEDGER": [
            {"PROFILE_ID": profile_id(p), "CURRENT_BOUND": b}
            for p, b in sorted(
                chase.bounds.items(), key=lambda item: (item[1], item[0]), reverse=True
            )
        ],
        "RESOLVED_LEDGER_COUNT": len(chase.bounds),
        "R26_PROOF_RERUN_COUNT": 0,
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        "WORK_BELOW_CURRENT_FAMILY_MAX_STARTED": False,
        "NO_OLD_WORK_GUARD": "PASS",
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "JUDGE_MODE": "NOT_APPLICABLE",
        "JUDGE_DISPATCH": "SUPPRESSED",
        "PROOF_STARTED_UNIX_TIME": started_epoch,
        "PROOF_ACTUAL_WALL_SECONDS": monotonic() - started,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-child")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.batch_child:
        batch_child(object_row(json.loads(args.batch_child)))
        return
    target = repo_root() / RESULT_DIRECTORY / RESULT_FILENAME
    output = args.output or target
    if output.resolve() != target.resolve() or output.exists():
        raise AssertionError("only a new exact R28 result output is authorized")
    result = compute_result()
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "FAMILY_UPPER_BOUND",
                    "FINAL_BOUND_OWNER_TYPE",
                    "NEXT_ACTIVE_PROFILE",
                    "PROOF_ACTUAL_WALL_SECONDS",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
