"""Cross every resolved K20 min-S2 bound below the unresolved cursor (R26).

The Owner directed this task to build on the sibling six-owner R26 commit
ddac9036. Its sealed result is pinned by SHA-256 and replayed proof by proof
onto the frozen 408-row R25 ledger. The replay reconstructs the six owner
certificates at cap 269 and the one newly exposed owner that it left open.
From there the complete resolved ledger is chased in descending order. Each
tied owner set is split by identical structural signature. Every group first
gets one shared certificate on the exact union of its members' support models,
and only then individual models. A profile enters a model only while it is a
current maximum above the cursor. The cursor is never solved.

Two refutation routes are accepted:

D. A closed-form lemma. Suppose exactly 13 tickets carry triple supports. A
   degree-6 ticket has 12 distinct triple neighbours, so it is adjacent to all
   12 others. Every non-adjacent pair inside the 13-set is therefore an open
   wedge at each degree-6 ticket, and
   O >= #deg6 * (C(13,2) - 66 - floor(sum(6-d)/2)).
A. The exact-support open-wedge refutation, run with a parallel CP-SAT
   portfolio. Only INFEASIBLE is accepted. Before any proof, the same
   configuration must return a feasible status at every committed witness's
   open-wedge count.

A certificate is accepted only if it moves its group to or below the cursor.
A certificate that cannot change the family maximum is rejected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from importlib import import_module
from itertools import combinations
from math import comb
from pathlib import Path
from time import monotonic, time
from typing import Any, cast

from . import b649_k20_min_s2_six_owner_batch_refinement_r26 as batch
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import solver_runtime_preflight
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import canonical_primitive_preflight
from .b649_k20_min_s2_higher_order_closure_r2 import (
    K20_S1,
    K20_S2,
    k20_min_s2_s4_lower_bound_certificate,
)
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import coarse_profile_envelope
from .b649_k20_min_s2_realizable_core_class_bound_r4 import overlap_wedge_count
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    bound_from_cap,
    decode_profile,
    profile_id,
    support_witness,
)

DegreeProfile = tuple[int, ...]
Signature = tuple[int, int, int, int, int, int, int, int, int, int, int, str, str]
Prover = Callable[[Sequence[Certificate], Mapping[DegreeProfile, int], int], dict[str, object]]

TASK_ID = "B649_K20_MIN_S2_SIX_OWNER_CURSOR_CROSSOVER_R26"
TASK_BRANCH = "codex/b649-k20-min-s2-six-owner-cursor-crossover-r26"
PACKET_BASE_HEAD = "a990c5f0bc20c3f6dd56e92c6aedc75ca9dcac50"
PACKET_BASE_TREE = "0efc56f9dc73963309efa3d89fa3f4d80f620d83"
BASE_HEAD = "ddac9036d84de311cdbbc26c22ec5df8ef48c095"
BASE_TREE = "78e55eadc10a86c5acd323797732da6e5475918b"
BASE_DISPOSITION = "OWNER_DIRECTED_REBASE_ONTO_SIBLING_R26_DDAC9036"
SIBLING_RESULT_SHA256 = "a4cd324e242c2dc50b70fc428e16338d06cd820412ffaa6b6e1f26f7b46f5278"
SIBLING_FAMILY_BOUND = 313_649_608
SIBLING_OWNER = decode_profile("66665555554440000000")
SIX_REFINED_CAP = 269
SIX_REFINED_BOUND = 313_626_760
TRIANGLE_UNIT = 11_872
REQUIRED_DROP_TO_CURSOR = batch.START_FAMILY_BOUND - batch.NEXT_CURSOR_BOUND
OWNER_IDS = batch.OWNER_IDS
OWNERS = batch.OWNERS
NEXT_CURSOR_BOUND = batch.NEXT_CURSOR_BOUND
NEXT_CURSOR_PROFILE = batch.NEXT_CURSOR_PROFILE
START_FAMILY_BOUND = batch.START_FAMILY_BOUND
INCUMBENT = batch.INCUMBENT
RESULT_DIRECTORY = batch.RESULT_DIRECTORY
RESULT_FILENAME = "b649-k20-min-s2-six-owner-cursor-crossover-r26-result.json"
MODULE_NAME = "lottolab.research.b649_k20_min_s2_six_owner_cursor_crossover_r26"
CP_SAT_WORKERS = 8
PROOF_WALL_SECONDS = 3_600.0
NATIVE_GROUP_SECONDS = 120.0
NATIVE_INDIVIDUAL_SECONDS = 60.0
NATIVE_CHECK_SECONDS = 30.0
EXTERNAL_GRACE_SECONDS = 15.0
EXTERNAL_KILL_SECONDS = 5
ROUTE_A = "A_EXACT_SUPPORT_UNION_OPEN_WEDGE_REFUTATION"
ROUTE_D = "D_FULL_TICKET_OPEN_WEDGE_LEMMA"
KIND_A = "CP_SAT_INFEASIBLE"
KIND_D = "CLOSED_FORM_OPEN_WEDGE_LOWER_BOUND"
SUCCESS_A = batch.SUCCESS_A
SUCCESS_B = batch.SUCCESS_B
SUCCESS_C = batch.SUCCESS_C
NO_DROP = batch.NO_DROP
SIGNATURE_FIELDS = (
    "N",
    "TRIPLES",
    "DOUBLES",
    "EDGES",
    "DEGREE_SQUARE_SUM",
    "WEDGES",
    "TRIANGLE_CAP",
    "NONCORE_TRIANGLE_CAP",
    "S3",
    "S4_FLOOR",
    "CURRENT_BOUND",
    "SUPPORT_REALIZATION_CLASS",
    "BOUND_LIMITING_RELAXATION",
)

object_row = batch.object_row
rows = batch.rows
integer = batch.integer
family_state = batch.family_state
assert_solver_scope = batch.assert_solver_scope
certificate_row = batch.certificate_row
target_cap = batch.target_cap


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def sibling_result() -> tuple[dict[str, object], str]:
    relative = f"{RESULT_DIRECTORY}/{batch.RESULT_FILENAME}"
    blob = subprocess.check_output(["git", "show", f"{BASE_HEAD}:{relative}"], cwd=repo_root())
    digest = hashlib.sha256(blob).hexdigest()
    if digest != SIBLING_RESULT_SHA256:
        raise AssertionError("pinned sibling R26 identity changed")
    return object_row(json.loads(blob)), digest


def replay_sibling(base: batch.State, sibling: Mapping[str, object], digest: str) -> batch.State:
    """Apply every sibling INFEASIBLE proof in order, re-checking its identity."""

    if (
        sibling.get("BASE_HEAD") != PACKET_BASE_HEAD
        or sibling.get("TASK_STATUS") != SUCCESS_C
        or sibling.get("FAMILY_UPPER_BOUND") != SIBLING_FAMILY_BOUND
        or sibling.get("NO_CURSOR_WORK_GUARD") != "PASS"
        or sibling.get("CURSOR_PROFILE_SOLVES") != 0
    ):
        raise AssertionError("sibling R26 authority or guard changed")
    if family_state(base.bounds) != (START_FAMILY_BOUND, OWNERS):
        raise AssertionError("R25 six-owner start changed")
    bounds = dict(base.bounds)
    catalog = dict(base.certificates)
    for index, raw in enumerate(rows(sibling["GROUP_ATTEMPTS"])):
        attempt = object_row(raw)
        profiles = tuple(decode_profile(p) for p in rows(attempt["PROFILE_IDS"]))
        assert_solver_scope(profiles, bounds)
        if attempt.get("STATUS") != "INFEASIBLE":
            continue
        cap = integer(attempt["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
        if batch.accepted_cap(attempt, profiles, cap) != cap:
            raise AssertionError("sibling proof identity mismatch")
        for p in profiles:
            cert = catalog[p]
            s3, bound = bound_from_cap(p, cap, integer(cert.s4))
            if bound >= bounds[p] or bound > NEXT_CURSOR_BOUND:
                raise AssertionError("sibling proof does not cross the cursor")
            bounds[p] = bound
            catalog[p] = replace(
                cert,
                bound=bound,
                s3=s3,
                triangle_cap=cap,
                source_result=batch.RESULT_FILENAME,
                source_row=f"GROUP_ATTEMPTS[{index}]",
                relaxation=ROUTE_A,
            )
    sealed = {
        decode_profile(row["PROFILE_ID"]): integer(row["CURRENT_BOUND"])
        for row in map(object_row, rows(sibling["FINAL_RESOLVED_LEDGER"]))
    }
    if (
        sealed != bounds
        or len(bounds) != 408
        or family_state(bounds) != (SIBLING_FAMILY_BOUND, (SIBLING_OWNER,))
        or any(bounds[p] != SIX_REFINED_BOUND for p in OWNERS)
        or any(catalog[p].triangle_cap != SIX_REFINED_CAP for p in OWNERS)
    ):
        raise AssertionError("sibling replay does not reproduce its sealed ledger")
    return batch.State(bounds, catalog, {**base.input_hashes, batch.RESULT_FILENAME: digest})


def start_state() -> batch.State:
    sibling, digest = sibling_result()
    return replay_sibling(batch.current_state(), sibling, digest)


def signature(cert: Certificate) -> Signature:
    """Packet grouping fields: structure, caps, S3, S4, realization, relaxation."""

    n, triples, doubles, edges, squares, wedges, cap, s3, s4, bound = batch.signature(cert)
    return (
        n,
        triples,
        doubles,
        edges,
        squares,
        wedges,
        cap,
        cap - 22,
        s3,
        s4,
        bound,
        cert.realizability,
        cert.relaxation,
    )


def signature_groups(certificates: Iterable[Certificate]) -> tuple[tuple[Certificate, ...], ...]:
    groups: dict[Signature, list[Certificate]] = defaultdict(list)
    for cert in certificates:
        groups[signature(cert)].append(cert)
    return tuple(tuple(group) for _, group in sorted(groups.items(), key=lambda item: item[0]))


def group_row(group: Sequence[Certificate]) -> dict[str, object]:
    return {
        "SIGNATURE": list(signature(group[0])),
        "SIGNATURE_FIELDS": list(SIGNATURE_FIELDS),
        "PROFILE_IDS": [profile_id(c.profile) for c in group],
        "MEMBER_COUNT": len(group),
        "COVERAGE": "EXACT_ALLOWED_ASSIGNMENT_UNION_OF_LISTED_HISTOGRAMS",
    }


def crossing_bound(cert: Certificate, cap: int) -> tuple[int, int]:
    """Reject any certified cap that leaves its profile above the cursor."""

    s3, bound = bound_from_cap(cert.profile, cap, integer(cert.s4))
    if bound > NEXT_CURSOR_BOUND:
        raise AssertionError("insufficient certificate cannot cross the cursor")
    if bound >= cert.bound:
        raise AssertionError("certificate does not tighten its profile")
    return s3, bound


def full_ticket_open_wedge_floor(profile: DegreeProfile) -> int | None:
    """Route D: open wedges forced at degree-6 tickets when 13 carry triples."""

    support = [d for d in profile if d]
    full = sum(d == 6 for d in profile)
    if len(support) != 13 or full == 0:
        return None
    nonadjacent = comb(13, 2) - 3 * 22 - sum(6 - d for d in support) // 2
    return full * max(nonadjacent, 0)


def lemma_proof(profiles: Sequence[DegreeProfile], cap: int) -> dict[str, object] | None:
    wedge = overlap_wedge_count(profiles[0])
    ceiling = wedge - 3 * (cap + 1)
    floors = [full_ticket_open_wedge_floor(p) for p in profiles]
    if any(f is None or f <= ceiling for f in floors):
        return None
    lower = min(f for f in floors if f is not None)
    return {
        "ROUTE": ROUTE_D,
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": KIND_D,
        "PROFILE_IDS": list(map(profile_id, profiles)),
        "WEDGE_COUNT": wedge,
        "REFUTED_GRAPH_TRIANGLE_COUNT": cap + 1,
        "OPEN_WEDGE_CEILING_REFUTED": ceiling,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": cap,
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": lower,
        "LEMMA_ROWS": [
            {
                "PROFILE_ID": profile_id(p),
                "TRIPLE_SUPPORT_TICKETS": 13,
                "DEGREE_SIX_TICKETS": sum(d == 6 for d in p),
                "DOUBLE_ENDPOINTS_INSIDE_SUPPORT": sum(6 - d for d in p if d),
                "NONADJACENT_SUPPORT_PAIR_FLOOR": comb(13, 2)
                - 66
                - sum(6 - d for d in p if d) // 2,
                "OPEN_WEDGE_FLOOR": full_ticket_open_wedge_floor(p),
            }
            for p in profiles
        ],
        "SOLVER_WALL_TIME_SECONDS": 0.0,
    }


def accepted_cap(
    proof: Mapping[str, object], profiles: Sequence[DegreeProfile], cap: int
) -> int | None:
    if proof.get("STATUS") != "INFEASIBLE":
        return None
    route = (proof.get("ROUTE"), proof.get("CERTIFICATE_KIND"))
    if (
        route not in ((ROUTE_A, KIND_A), (ROUTE_D, KIND_D))
        or proof.get("PROFILE_IDS") != list(map(profile_id, profiles))
        or proof.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND") != cap
        or proof.get("REFUTED_GRAPH_TRIANGLE_COUNT") != cap + 1
        or proof.get("OPEN_WEDGE_CEILING_REFUTED")
        != overlap_wedge_count(profiles[0]) - 3 * (cap + 1)
    ):
        raise AssertionError("refutation certificate identity mismatch")
    if route[0] == ROUTE_D and lemma_proof(profiles, cap) is None:
        raise AssertionError("closed-form lemma does not refute the ceiling")
    return cap


def configured_solver(seconds: float, workers: int) -> Any:
    cp_model: Any = import_module("ortools.sat.python.cp_model")
    solver: Any = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = 649
    return solver


def witness_open_wedges(cert: Certificate) -> int:
    triples, doubles = support_witness(cert)
    edges = {tuple(sorted(p)) for t in triples for p in combinations(t, 2)} | set(doubles)
    triangles = sum(all(p in edges for p in combinations(t, 2)) for t in combinations(range(20), 3))
    return overlap_wedge_count(cert.profile) - 3 * triangles


def proof_config_nonvacuity(certificates: Iterable[Certificate]) -> dict[str, object]:
    """The proof configuration must find each committed witness open-wedge count."""

    checks: list[dict[str, object]] = []
    for cert in certificates:
        if cert.witness_row is None:
            continue
        ceiling = witness_open_wedges(cert)
        model, *_ = batch.union_support_model((cert.profile,), ceiling)
        solver = configured_solver(NATIVE_CHECK_SECONDS, CP_SAT_WORKERS)
        status = str(solver.StatusName(solver.Solve(model)))
        if status not in ("OPTIMAL", "FEASIBLE"):
            raise AssertionError("proof configuration cannot realize a committed witness")
        checks.append(
            {
                "PROFILE_ID": profile_id(cert.profile),
                "UNFIXED_CEILING_AT_WITNESS_OPEN_WEDGES": ceiling,
                "STATUS": status,
                "SOLVER_WALL_TIME_SECONDS": float(solver.WallTime()),
            }
        )
    if not checks:
        raise AssertionError("no committed witness exercises the proof configuration")
    return {"STATUS": "PASS", "CP_SAT_SEARCH_WORKERS": CP_SAT_WORKERS, "CHECKS": checks}


def solve_group(
    profiles: Sequence[DegreeProfile], cap: int, seconds: float, workers: int
) -> dict[str, object]:
    wedge = overlap_wedge_count(profiles[0])
    ceiling = wedge - 3 * (cap + 1)
    model, _, _, _, indicators = batch.union_support_model(profiles, ceiling)
    solver = configured_solver(seconds, workers)
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


def bounded_group(
    group: Sequence[Certificate], bounds: Mapping[DegreeProfile, int], cap: int, deadline: float
) -> dict[str, object]:
    """Run one route-A proof in a child under an external hard timeout."""

    profiles = tuple(c.profile for c in group)
    assert_solver_scope(profiles, bounds)
    native = NATIVE_GROUP_SECONDS if len(group) > 1 else NATIVE_INDIVIDUAL_SECONDS
    seconds = min(native, deadline - monotonic() - EXTERNAL_GRACE_SECONDS - 1)
    if seconds <= 0:
        return {"STATUS": "PROOF_BUDGET_EXHAUSTED", "PROFILE_IDS": list(map(profile_id, profiles))}
    request = {
        "PROFILES": list(map(profile_id, profiles)),
        "CAP": cap,
        "SECONDS": seconds,
        "WORKERS": CP_SAT_WORKERS,
        "BOUNDS": {profile_id(p): b for p, b in bounds.items()},
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
    result = subprocess.run(
        [
            "timeout",
            "--signal=TERM",
            f"--kill-after={EXTERNAL_KILL_SECONDS}s",
            f"{seconds + EXTERNAL_GRACE_SECONDS}s",
            sys.executable,
            "-m",
            MODULE_NAME,
            "--group-child",
            json.dumps(request),
        ],
        cwd=repo_root(),
        env=env,
        capture_output=True,
        text=True,
        timeout=seconds + EXTERNAL_GRACE_SECONDS + EXTERNAL_KILL_SECONDS + 5,
    )
    proof: dict[str, object] = (
        object_row(json.loads(result.stdout))
        if result.returncode == 0
        else {
            "STATUS": "EXTERNAL_TIMEOUT" if result.returncode in (124, 137) else "CHILD_FAILURE",
            "PROFILE_IDS": list(map(profile_id, profiles)),
            "ERROR": result.stderr[-2000:],
        }
    )
    proof.update(
        {
            "EXTERNAL_HARD_TIMEOUT_SECONDS": seconds + EXTERNAL_GRACE_SECONDS,
            "EXTERNAL_TIMEOUT_EXIT_CODE": result.returncode,
            "SUBPROCESS_WALL_SECONDS": monotonic() - started,
        }
    )
    return proof


def run_chase(state: batch.State, prove: Prover) -> dict[str, object]:
    """Descend the complete resolved ledger until nothing exceeds the cursor."""

    bounds = dict(state.bounds)
    catalog = dict(state.certificates)
    attempts: list[dict[str, object]] = []
    steps: list[dict[str, object]] = []
    exposed: list[DegreeProfile] = []
    start_above = sorted(
        (p for p, b in bounds.items() if b > NEXT_CURSOR_BOUND),
        key=lambda p: (bounds[p], p),
        reverse=True,
    )

    def attempt(group: Sequence[Certificate]) -> bool:
        before, _ = family_state(bounds)
        profiles = tuple(c.profile for c in group)
        assert_solver_scope(profiles, bounds)
        cap = target_cap(group[0])
        proof = prove(group, dict(bounds), cap)
        attempts.append(
            {
                "OWNER_CERTIFICATES": [certificate_row(c) for c in group],
                "GROUP_SIGNATURE": list(signature(group[0])),
                "REQUIRED_DROP_TO_CURSOR": group[0].bound - NEXT_CURSOR_BOUND,
                "TRIANGLES_REQUIRED": integer(group[0].triangle_cap) - cap,
                "TARGET_TRIANGLE_CAP": cap,
                **proof,
            }
        )
        if accepted_cap(proof, profiles, cap) is None:
            return False
        for cert in group:
            s3, bound = crossing_bound(cert, cap)
            bounds[cert.profile] = bound
            catalog[cert.profile] = replace(
                cert,
                bound=bound,
                s3=s3,
                triangle_cap=cap,
                source_result=RESULT_FILENAME,
                source_row=f"GROUP_ATTEMPTS[{len(attempts) - 1}]",
                relaxation=str(proof["ROUTE"]),
            )
        after, owners = family_state(bounds)
        steps.append(
            {
                "GROUP_PROFILE_IDS": list(map(profile_id, profiles)),
                "ROUTE": proof["ROUTE"],
                "TRIANGLE_CAP": cap,
                "NEW_BOUND": bounds[profiles[0]],
                "FAMILY_BOUND_BEFORE": before,
                "FAMILY_BOUND_AFTER": after,
                "FAMILY_MAX_CHANGED": after < before,
                "MAX_RESOLVED_BOUND": max(bounds.values()),
                "RESOLVED_ABOVE_CURSOR_AFTER": sum(b > NEXT_CURSOR_BOUND for b in bounds.values()),
                "OWNER_SET_AFTER": list(map(profile_id, owners)),
                "COMPLETE_LEDGER_ROW_COUNT": len(bounds),
            }
        )
        return True

    while family_state(bounds)[0] > NEXT_CURSOR_BOUND:
        _, owners = family_state(bounds)
        exposed.extend(p for p in owners if p not in exposed)
        progress = False
        for group in signature_groups(catalog[p] for p in owners):
            if attempt(group):
                progress = True
                continue
            if len(group) == 1 or attempts[-1].get("STATUS") == "PROOF_BUDGET_EXHAUSTED":
                continue
            for cert in group:
                if attempt((cert,)):
                    progress = True
                elif attempts[-1].get("STATUS") == "PROOF_BUDGET_EXHAUSTED":
                    break
        if not progress:
            break
    family, owners = family_state(bounds)
    remaining = sorted(
        (p for p, b in bounds.items() if b > NEXT_CURSOR_BOUND),
        key=lambda p: (bounds[p], p),
        reverse=True,
    )
    status = (
        SUCCESS_A
        if family <= INCUMBENT
        else SUCCESS_B
        if not remaining
        else SUCCESS_C
        if family < SIBLING_FAMILY_BOUND
        else NO_DROP
    )
    return {
        "TASK_STATUS": status,
        "CHASE_START_FAMILY_BOUND": SIBLING_FAMILY_BOUND,
        "CHASE_START_RESOLVED_ABOVE_CURSOR_COUNT": len(start_above),
        "CHASE_START_STRUCTURAL_GROUPS": [
            group_row(g) for g in signature_groups(state.certificates[p] for p in start_above)
        ],
        "FAMILY_UPPER_BOUND": family,
        "MAX_RESOLVED_BOUND": max(bounds.values()),
        "CURRENT_BOUND_OWNER_SET": list(map(profile_id, owners)),
        "CURRENT_BOUND_OWNER_CERTIFICATES": [
            certificate_row(catalog[p]) for p in owners if p in catalog
        ],
        "GROUP_ATTEMPTS": attempts,
        "GROUP_REFINEMENT_STEPS": steps,
        "CHASE_EXPOSED_OWNER_PROFILES": list(map(profile_id, exposed)),
        "REMAINING_RESOLVED_ABOVE_CURSOR_COUNT": len(remaining),
        "REMAINING_RESOLVED_ABOVE_CURSOR": [
            {"PROFILE_ID": profile_id(p), "CURRENT_BOUND": bounds[p]} for p in remaining
        ],
        "REFINED_OWNER_BOUNDS": {profile_id(p): bounds[p] for p in OWNERS},
        "REFINED_CHASE_BOUNDS": {profile_id(p): bounds[p] for p in start_above},
        "FINAL_RESOLVED_LEDGER": [
            {"PROFILE_ID": profile_id(p), "CURRENT_BOUND": b}
            for p, b in sorted(bounds.items(), key=lambda item: (item[1], item[0]), reverse=True)
        ],
    }


def six_owner_reconstruction(r25: batch.State, start: batch.State) -> list[dict[str, object]]:
    rows_out: list[dict[str, object]] = []
    for p in OWNERS:
        before = r25.certificates[p]
        after = start.certificates[p]
        one = bound_from_cap(p, integer(before.triangle_cap) - 1, integer(before.s4))[1]
        two = bound_from_cap(p, integer(before.triangle_cap) - 2, integer(before.s4))[1]
        rows_out.append(
            {
                "PROFILE_ID": profile_id(p),
                "START_CERTIFICATE": certificate_row(before),
                "START_BOUND": before.bound,
                "REQUIRED_DROP_TO_CURSOR": before.bound - NEXT_CURSOR_BOUND,
                "TRIANGLE_UNIT": before.bound - one,
                "ONE_TRIANGLE_BOUND": one,
                "ONE_TRIANGLE_VERDICT": "REJECTED_ABOVE_CURSOR"
                if one > NEXT_CURSOR_BOUND
                else "SUFFICIENT",
                "TWO_TRIANGLE_BOUND": two,
                "TWO_TRIANGLE_VERDICT": "SUFFICIENT" if two <= NEXT_CURSOR_BOUND else "REJECTED",
                "TARGET_TRIANGLE_CAP": target_cap(before),
                "REFINED_CERTIFICATE": certificate_row(after),
            }
        )
    return rows_out


def minimal_s4_credit(cert: Certificate, missing: int) -> int:
    """Smallest S4-floor increase whose 4/7 credit covers ``missing`` outcomes."""

    s4 = integer(cert.s4)
    credit = 0
    while (4 * (s4 + credit)) // 7 - (4 * s4) // 7 < missing:
        credit += 1
    return credit


def certificate_form_evaluation(r25: batch.State) -> dict[str, object]:
    cert = r25.certificates[OWNERS[0]]
    one = bound_from_cap(cert.profile, integer(cert.triangle_cap) - 1, integer(cert.s4))[1]
    missing = one - NEXT_CURSOR_BOUND
    return {
        "REQUIRED_DROP_TO_CURSOR": REQUIRED_DROP_TO_CURSOR,
        "ONE_TRIANGLE_DROP": TRIANGLE_UNIT,
        "ONE_TRIANGLE_SHORTFALL": missing,
        "A_TWO_TRIANGLE_EQUIVALENT_TIGHTENING": "SELECTED_SMALLEST_RIGOROUS_PROOF",
        "B_ONE_TRIANGLE_PLUS_S4_CREDIT": {
            "STATUS": "NOT_SELECTED_NO_CERTIFIED_PROFILE_S4_CREDIT",
            "MINIMUM_S4_FLOOR_INCREASE_REQUIRED": minimal_s4_credit(cert, missing),
        },
        "C_ONE_TRIANGLE_PLUS_HIGHER_ORDER_CORRECTION": "NOT_REQUIRED_A_CERTIFIED",
        "D_DIRECT_OPEN_WEDGE_LOWER_BOUND": "NOT_APPLICABLE_NEEDS_EXACTLY_13_TRIPLE_SUPPORT_TICKETS"
        if all(full_ticket_open_wedge_floor(p) is None for p in OWNERS)
        else "APPLICABLE",
    }


def six_owner_reproduction(r25: batch.State) -> dict[str, object]:
    """Re-prove the six cap-269 refutations, group first; no ledger effect."""

    groups = signature_groups(r25.certificates[p] for p in OWNERS)
    proofs: list[dict[str, object]] = []
    for group in groups:
        profiles = tuple(c.profile for c in group)
        proof = solve_group(profiles, SIX_REFINED_CAP, NATIVE_CHECK_SECONDS, CP_SAT_WORKERS)
        proofs.append(proof)
        if proof["STATUS"] == "INFEASIBLE" or len(group) == 1:
            continue
        for p in profiles:
            proofs.append(solve_group((p,), SIX_REFINED_CAP, NATIVE_CHECK_SECONDS, CP_SAT_WORKERS))
    covered = {
        p
        for proof in proofs
        if proof["STATUS"] == "INFEASIBLE"
        for p in map(decode_profile, rows(proof["PROFILE_IDS"]))
    }
    return {
        "STATUS": "PASS" if covered == set(OWNERS) else "INCOMPLETE",
        "EFFECT": "VERIFICATION_ONLY_NO_LEDGER_EFFECT",
        "GROUP_COUNT": len(groups),
        "GROUPS": [group_row(g) for g in groups],
        "PROOFS": proofs,
    }


def compute_result() -> dict[str, object]:
    started_epoch = time()
    started = monotonic()
    primitives = canonical_primitive_preflight()
    runtime = solver_runtime_preflight()
    s4 = k20_min_s2_s4_lower_bound_certificate()
    if (K20_S1, K20_S2, s4.s4_lower_bound) != (372_228_640, 63_838_600, 112):
        raise AssertionError("canonical primitive/S4 preflight changed")
    if coarse_profile_envelope(NEXT_CURSOR_PROFILE).family_upper_bound != NEXT_CURSOR_BOUND:
        raise AssertionError("frozen cursor arithmetic changed")
    if REQUIRED_DROP_TO_CURSOR != 12_656:
        raise AssertionError("required drop arithmetic changed")
    r25 = batch.current_state()
    state = start_state()
    above = [p for p, b in state.bounds.items() if b > NEXT_CURSOR_BOUND]
    print(f"Chase start: {len(above)} resolved above cursor", file=sys.stderr, flush=True)
    config_check = proof_config_nonvacuity(
        [state.certificates[p] for p in (*OWNERS, *sorted(above, reverse=True))]
    )
    witness_checks = [
        batch.witness_model_check(group)
        for group in signature_groups(state.certificates[p] for p in above)
        if any(c.witness_row is not None for c in group)
    ]
    reproduction = six_owner_reproduction(r25)
    if reproduction["STATUS"] != "PASS":
        raise AssertionError("six-owner cap-269 reproduction failed")
    deadline = started + PROOF_WALL_SECONDS

    def prove(
        group: Sequence[Certificate], bounds: Mapping[DegreeProfile, int], cap: int
    ) -> dict[str, object]:
        profiles = tuple(c.profile for c in group)
        lemma = lemma_proof(profiles, cap)
        if lemma is not None:
            return lemma
        print(
            f"Proving {len(group)} at {group[0].bound}: cap {cap}",
            file=sys.stderr,
            flush=True,
        )
        proof = bounded_group(group, bounds, cap, deadline)
        print(f"Group status {proof['STATUS']}", file=sys.stderr, flush=True)
        return proof

    outcome = run_chase(state, prove)
    attempts = [object_row(a) for a in rows(outcome["GROUP_ATTEMPTS"])]
    six_groups = signature_groups(r25.certificates[p] for p in OWNERS)
    exposed = [*start_sibling_exposed(), *rows(outcome["CHASE_EXPOSED_OWNER_PROFILES"])]
    newly_exposed = list(dict.fromkeys(str(p) for p in exposed if p not in OWNER_IDS))
    family = integer(outcome["FAMILY_UPPER_BOUND"])
    result: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "PACKET_BASE_HEAD": PACKET_BASE_HEAD,
        "PACKET_BASE_TREE": PACKET_BASE_TREE,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_DISPOSITION": BASE_DISPOSITION,
        "SIBLING_RESULT": batch.RESULT_FILENAME,
        "SIBLING_RESULT_SHA256": SIBLING_RESULT_SHA256,
        "START_FAMILY_BOUND": START_FAMILY_BOUND,
        "REQUIRED_DROP_TO_CURSOR": REQUIRED_DROP_TO_CURSOR,
        "TRIANGLE_UNIT": TRIANGLE_UNIT,
        "START_OWNER_COUNT": len(OWNERS),
        "OWNER_PROFILES": list(OWNER_IDS),
        "START_OWNER_BOUNDS": {profile_id(p): r25.bounds[p] for p in OWNERS},
        "OWNER_SIGNATURE_GROUP_COUNT": len(six_groups),
        "OWNER_SIGNATURE_GROUPS": [group_row(g) for g in six_groups],
        "SIX_OWNER_RECONSTRUCTION": six_owner_reconstruction(r25, state),
        "CERTIFICATE_FORM_EVALUATION": certificate_form_evaluation(r25),
        "SIX_OWNER_REPRODUCTION": reproduction,
        "PROOF_CONFIG_NONVACUITY": config_check,
        "UNION_WITNESS_NONVACUITY": witness_checks,
        "NEXT_CURSOR_BOUND": NEXT_CURSOR_BOUND,
        "NEXT_CURSOR_PROFILE": profile_id(NEXT_CURSOR_PROFILE),
        "CANONICAL_PRIMITIVE_STATUS": "PASS",
        "CANONICAL_PRIMITIVES": primitives,
        "S4_CERTIFIED_FLOOR": s4.s4_lower_bound,
        "COMMITTED_INPUT_SHA256": dict(state.input_hashes),
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "NATIVE_GROUP_SECONDS": NATIVE_GROUP_SECONDS,
            "NATIVE_INDIVIDUAL_SECONDS": NATIVE_INDIVIDUAL_SECONDS,
            "NATIVE_CHECK_SECONDS": NATIVE_CHECK_SECONDS,
            "EXTERNAL_GRACE_SECONDS": EXTERNAL_GRACE_SECONDS,
            "EXTERNAL_KILL_AFTER_SECONDS": EXTERNAL_KILL_SECONDS,
            "PROOF_WALL_SECONDS": PROOF_WALL_SECONDS,
            "CP_SAT_SEARCH_WORKERS": CP_SAT_WORKERS,
        },
        "SOLVER_STATUS": [a["STATUS"] for a in attempts],
        "SOLVER_ACTUAL_WALL_TIME": sum(
            float(cast(float, a.get("SOLVER_WALL_TIME_SECONDS", 0.0))) for a in attempts
        ),
        "ROUTE_COUNTS": {
            route: sum(a.get("ROUTE") == route and a["STATUS"] == "INFEASIBLE" for a in attempts)
            for route in (ROUTE_A, ROUTE_D)
        },
        "NEWLY_EXPOSED_RESOLVED_OWNER_COUNT": len(newly_exposed),
        "NEWLY_EXPOSED_RESOLVED_OWNER_PROFILES": newly_exposed,
        "RESOLVED_LEDGER_COUNT": 408,
        "CURSOR_PROFILE_SOLVES": 0,
        "PLATEAU_RERUN_COUNT": 0,
        "NO_CURSOR_WORK_GUARD": "PASS",
        "INCUMBENT": INCUMBENT,
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "JUDGE_MODE": "NOT_APPLICABLE",
        "JUDGE_DISPATCH": "SUPPRESSED",
        **outcome,
    }
    result["SOLVER_CERTIFIED_BOUND"] = family
    result["SOLVER_CERTIFIED_BOUND_SCOPE"] = "COMPLETE_FAMILY_LEDGER_PLUS_UNRESOLVED_CURSOR"
    result["REMAINING_GAP"] = family - INCUMBENT
    result["CURSOR_GENUINELY_LOAD_BEARING"] = (
        family == NEXT_CURSOR_BOUND and outcome["REMAINING_RESOLVED_ABOVE_CURSOR_COUNT"] == 0
    )
    result["FAMILY_STATUS"] = (
        "CLOSED"
        if outcome["TASK_STATUS"] == SUCCESS_A
        else "OPEN_CURSOR_LOAD_BEARING"
        if result["CURSOR_GENUINELY_LOAD_BEARING"]
        else "OPEN_STRICTLY_TIGHTENED"
        if outcome["TASK_STATUS"] == SUCCESS_C
        else "OPEN"
    )
    result["PROOF_STARTED_UNIX_TIME"] = started_epoch
    result["PROOF_ACTUAL_WALL_SECONDS"] = monotonic() - started
    return result


def start_sibling_exposed() -> list[object]:
    sibling, _ = sibling_result()
    return rows(sibling["NEWLY_EXPOSED_RESOLVED_OWNER_PROFILES"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group-child")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.group_child:
        request = object_row(json.loads(args.group_child))
        profiles = tuple(decode_profile(p) for p in rows(request["PROFILES"]))
        bounds = {decode_profile(p): integer(b) for p, b in object_row(request["BOUNDS"]).items()}
        baseline = start_state()
        if bounds.keys() != baseline.bounds.keys() or any(
            b > baseline.bounds[p] for p, b in bounds.items()
        ):
            raise AssertionError("child requires complete monotone resolved ledger")
        assert_solver_scope(profiles, bounds)
        print(
            json.dumps(
                solve_group(
                    profiles,
                    integer(request["CAP"]),
                    float(cast(float, request["SECONDS"])),
                    integer(request["WORKERS"]),
                )
            )
        )
        return
    output = args.output or repo_root() / RESULT_DIRECTORY / RESULT_FILENAME
    if (
        output.resolve() != (repo_root() / RESULT_DIRECTORY / RESULT_FILENAME).resolve()
        or output.exists()
    ):
        raise AssertionError("only a new exact R26 crossover result output is authorized")
    result = compute_result()
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "FAMILY_UPPER_BOUND",
                    "MAX_RESOLVED_BOUND",
                    "REMAINING_RESOLVED_ABOVE_CURSOR_COUNT",
                    "CURRENT_BOUND_OWNER_SET",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
