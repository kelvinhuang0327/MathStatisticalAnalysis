"""Resume the frozen R25 plateau and chase its 48 resolved square-sum-326 owners.

The Owner's resume packet supplies the completed 76-profile square-sum-318
plateau and next cursor. No plateau enumeration, census or cursor solve occurs.
R24 supplies the entire resolved ledger; R16 independently supplies the exact
48-member owner set and its per-histogram certificates. Fresh R13 relaxations
are compared with those committed certificates before any bound is adopted.
Only the surviving family maximum may enter a stronger support model. Stop
at the first strict chase-family drop with the exact successor owner set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from importlib import import_module
from itertools import combinations
from pathlib import Path
from time import monotonic
from typing import Any, cast

from .b649_k20_min_s2_class_dominance_or_descent_r13 import (
    degree_class_open_wedge_relaxation,
    graph_triangle_upper_bound_from_open_wedges,
    profile_family_envelope_from_triangle_bound,
    profile_shadow_obstruction,
)
from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import solver_runtime_preflight
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import canonical_primitive_preflight
from .b649_k20_min_s2_cursor_plateau_closure_r18 import generic_open_wedge_floor
from .b649_k20_min_s2_higher_order_closure_r2 import (
    K20_S1,
    K20_S2,
    k20_min_s2_s4_lower_bound_certificate,
)
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import coarse_profile_envelope
from .b649_k20_min_s2_next_distinct_plateau_r10 import (
    _motif_triangle_bound as motif_triangle_bound,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_next_distinct_plateau_r10 import (
    _support_model as support_model,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_r16_freeze_and_owner_refinement_r17 import (
    complement_route_attempt,
    exact_support_triangle_refutation,
    witness_open_wedge_check,
)
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    bound_from_cap,
    decode_profile,
    profile_id,
)

DegreeProfile = tuple[int, ...]
TASK_ID = "B649_K20_MIN_S2_CURSOR_DYNAMIC_OWNER_CHASE_R25"
TASK_BRANCH = "codex/b649-k20-min-s2-cursor-dynamic-owner-chase-r25"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "809d566e6274d150da4531b2772e07d6218cd044"
BASE_TREE = "9994b471cc814824387dc5effc06dae02e3d9936"
START_FAMILY_BOUND = 313_652_520
INITIAL_CURSOR_PROFILE = decode_profile("66666665432211111111")
CHASE_START_BOUND = 313_651_848
INCUMBENT = 313_239_661
PLATEAU_PROFILE_COUNT = 76
PLATEAU_SQUARE_SUM = 318
PLATEAU_CLASS_BOUND = 313_628_776
NEXT_CURSOR_BOUND = 313_637_848
NEXT_CURSOR_PROFILE = decode_profile("66666665422221111111")
RESOLVED_LEDGER_COUNT = 408
RESOLVED_OWNER_COUNT = 48
RESULT_DIRECTORY = "docs/research/matrix-native-results"
RESULT_FILENAME = "b649-k20-min-s2-cursor-dynamic-owner-chase-r25-result.json"
MODULE_NAME = "lottolab.research.b649_k20_min_s2_cursor_dynamic_owner_chase_r25"
INPUT_FILENAMES = {
    "R24": "b649-k20-min-s2-owner-ledger-reconcile-and-refine-r24-result.json",
    "R16": "b649-k20-min-s2-load-bearing-plateau-descent-r16-result.json",
}
INPUT_SHA256 = {
    "R24": "ca3678b2e7159cc67dab99c9fa3d73e46ffeed7458fcccd36bd5b53f53a39827",
    "R16": "777b7ee0bf85a0daf351f4c41120f29343d91266df8d59432a8b943602f80083",
}
ROUTES = (
    "A_EXACT_SUPPORT_OPEN_WEDGE_REFUTATION",
    "B_COMPLEMENT_TRIANGLE_LOWER_BOUND",
    "C_NONCORE_TRIANGLE_CEILING",
)
NATIVE_SECONDS = {"WITNESS": 60.0, ROUTES[0]: 900.0, ROUTES[1]: 90.0, ROUTES[2]: 60.0}
CHEAP_WALL_SECONDS = 10.0
EXTERNAL_GRACE_SECONDS = 30.0
EXTERNAL_KILL_SECONDS = 5
PROOF_WALL_SECONDS = 1_800.0
SUCCESS_A = "SUCCESS_A_FAMILY_CLOSED"
SUCCESS_B = "SUCCESS_B_ALL_RESOLVED_AT_OR_BELOW_CURSOR"
SUCCESS_C = "SUCCESS_C_STRICT_FAMILY_TIGHTENING_EXACT_REMAINING_OWNERS"
NO_DROP = "NO_CERTIFIED_OWNER_CHASE_FAMILY_DROP"


@dataclass(frozen=True, slots=True)
class State:
    bounds: Mapping[DegreeProfile, int]
    owners: tuple[DegreeProfile, ...]
    histogram_rows: Mapping[DegreeProfile, dict[str, object]]
    above_cursor: tuple[dict[str, object], ...]
    input_hashes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class Outcome:
    status: str
    bounds: Mapping[DegreeProfile, int]
    family_bound: int
    owners: tuple[DegreeProfile, ...]
    cheap_rows: tuple[dict[str, object], ...]
    steps: tuple[dict[str, object], ...]
    attempts: tuple[dict[str, object], ...]
    dispatched: tuple[DegreeProfile, ...]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def result_path() -> Path:
    return repo_root() / RESULT_DIRECTORY / RESULT_FILENAME


def object_row(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise AssertionError("expected certificate object")
    return cast(dict[str, object], raw)


def rows(raw: object) -> list[object]:
    if not isinstance(raw, list):
        raise AssertionError("expected certificate rows")
    return cast(list[object], raw)


def integer(raw: object) -> int:
    if type(raw) is not int:
        raise AssertionError("expected exact integer certificate")
    return raw


def committed_inputs() -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    inputs: dict[str, dict[str, object]] = {}
    hashes: dict[str, str] = {}
    for label, filename in INPUT_FILENAMES.items():
        relative = f"{RESULT_DIRECTORY}/{filename}"
        blob = subprocess.check_output(["git", "show", f"{BASE_HEAD}:{relative}"], cwd=repo_root())
        digest = hashlib.sha256(blob).hexdigest()
        if digest != INPUT_SHA256[label]:
            raise AssertionError(f"pinned {label} certificate identity changed")
        inputs[label] = object_row(json.loads(blob))
        hashes[relative] = digest
    return inputs, hashes


def plateau_certificate() -> dict[str, object]:
    """Recheck the generic algebra; reuse the packet's coverage without exploring it."""

    floor = generic_open_wedge_floor(20, 93, 6, 12)
    cap = graph_triangle_upper_bound_from_open_wedges(
        tuple(6 + d for d in INITIAL_CURSOR_PROFILE), floor
    )
    envelope = profile_family_envelope_from_triangle_bound(
        INITIAL_CURSOR_PROFILE, cap["GRAPH_TRIANGLE_UPPER_BOUND"]
    )
    if (
        sum(d * d for d in INITIAL_CURSOR_PROFILE) != PLATEAU_SQUARE_SUM
        or coarse_profile_envelope(INITIAL_CURSOR_PROFILE).family_upper_bound != START_FAMILY_BOUND
        or floor != 5
        or envelope["FAMILY_UPPER_BOUND"] != PLATEAU_CLASS_BOUND
        or PLATEAU_CLASS_BOUND >= NEXT_CURSOR_BOUND
        or coarse_profile_envelope(NEXT_CURSOR_PROFILE).family_upper_bound != NEXT_CURSOR_BOUND
        or sum(d * d for d in NEXT_CURSOR_PROFILE) != 316
        or profile_shadow_obstruction(NEXT_CURSOR_PROFILE) is not None
    ):
        raise AssertionError("frozen plateau certificate or next cursor changed")
    return {
        "AUTHORITY": "OWNER_AUTHORITATIVE_RESUME_PACKET_COMPLETED_ANALYSIS",
        "PLATEAU_PROFILE_COUNT": PLATEAU_PROFILE_COUNT,
        "PLATEAU_SQUARE_SUM": PLATEAU_SQUARE_SUM,
        "PLATEAU_CLASS_BOUND": PLATEAU_CLASS_BOUND,
        "INITIAL_CURSOR_BOUND": START_FAMILY_BOUND,
        "INITIAL_CURSOR_PROFILE": profile_id(INITIAL_CURSOR_PROFILE),
        "INDIVIDUAL_PLATEAU_SOLVES": 0,
        "PLATEAU_EXPLORATION_RERUN": False,
        "COVERAGE_REUSED_FROM_RESUME_PACKET": True,
        "CERTIFICATE_SCOPE": "ALL_K20_MIN_S2_PROFILES_WITH_SQUARE_SUM_318",
        "GRAPH_PREMISES": {"VERTICES": 20, "EDGES": 93, "MIN_DEGREE": 6, "MAX_DEGREE": 12},
        "GENERIC_OPEN_WEDGE_FLOOR": floor,
        "TRIANGLE_ENVELOPE": cap,
        "PROFILE_ENVELOPE": envelope,
        "NEXT_RANKED_CURSOR": NEXT_CURSOR_BOUND,
        "NEXT_CURSOR_PROFILE": profile_id(NEXT_CURSOR_PROFILE),
        "NEXT_CURSOR_IDENTITY_SOURCE": "LEXICOGRAPHIC_MAXIMUM_SQUARE_SUM_316_COARSE_ENVELOPE",
    }


def family_state(bounds: Mapping[DegreeProfile, int]) -> tuple[int, tuple[DegreeProfile, ...]]:
    if not bounds or INITIAL_CURSOR_PROFILE in bounds or NEXT_CURSOR_PROFILE in bounds:
        raise AssertionError("frozen plateau/cursor must remain outside the individual ledger")
    maximum = max(NEXT_CURSOR_BOUND, PLATEAU_CLASS_BOUND, *bounds.values())
    owners = tuple(sorted((p for p, b in bounds.items() if b == maximum), reverse=True))
    if maximum == NEXT_CURSOR_BOUND:
        owners = (NEXT_CURSOR_PROFILE, *owners)
    return maximum, owners


def above_cursor_rows(bounds: Mapping[DegreeProfile, int]) -> tuple[dict[str, object], ...]:
    return tuple(
        {"PROFILE_ID": profile_id(p), "BOUND": b}
        for p, b in sorted(bounds.items(), key=lambda item: (item[1], item[0]), reverse=True)
        if b > NEXT_CURSOR_BOUND
    )


def assert_no_omitted_above_cursor(
    bounds: Mapping[DegreeProfile, int], listed: tuple[dict[str, object], ...]
) -> None:
    if listed != above_cursor_rows(bounds):
        raise AssertionError("resolved profile above the next cursor omitted, invented or changed")


def reconstruct_state(inputs: Mapping[str, dict[str, object]], hashes: Mapping[str, str]) -> State:
    r24, r16 = inputs["R24"], inputs["R16"]
    if (
        r24.get("TASK_STATUS") != SUCCESS_B
        or r24.get("FAMILY_UPPER_BOUND") != START_FAMILY_BOUND
        or r24.get("NEXT_CURSOR_PROFILE") != profile_id(INITIAL_CURSOR_PROFILE)
        or r24.get("CURSOR_PROFILE_SOLVES") != 0
        or r24.get("NO_CURSOR_WORK_GUARD") != "PASS"
    ):
        raise AssertionError("R24 resume authority changed or cursor was solved")
    bounds: dict[DegreeProfile, int] = {}
    for raw in rows(r24["FINAL_RESOLVED_LEDGER"]):
        row = object_row(raw)
        p = decode_profile(row["PROFILE_ID"])
        if p in bounds:
            raise AssertionError("duplicate resolved profile")
        if sum(d * d for d in p) == PLATEAU_SQUARE_SUM:
            raise AssertionError("frozen new plateau overlaps the prior resolved ledger")
        bounds[p] = integer(row["CURRENT_BOUND"])
    if len(bounds) != RESOLVED_LEDGER_COUNT or max(bounds.values()) != CHASE_START_BOUND:
        raise AssertionError("complete R24 resolved ledger identity changed")
    family, owners = family_state(bounds)
    (raw_class,) = rows(r16["CLASS_CERTIFICATES"])
    cert = object_row(raw_class)
    identities = tuple(decode_profile(p) for p in rows(cert["PROFILE_IDENTITIES"]))
    if (
        family != CHASE_START_BOUND
        or len(owners) != RESOLVED_OWNER_COUNT
        or len(identities) != RESOLVED_OWNER_COUNT
        or len(set(identities)) != len(identities)
        or set(identities) != set(owners)
        or cert.get("COMPLETE_SUFFIX_ENUMERATION") is not True
        or cert.get("SQUARE_SUM") != 326
        or cert.get("CLASS_FAMILY_UPPER_BOUND") != CHASE_START_BOUND
        or cert.get("GRAPH_TRIANGLE_UPPER_BOUND") != 273
    ):
        raise AssertionError("exact 48 resolved owners differ from the complete R16 certificate")
    histograms: dict[DegreeProfile, dict[str, object]] = {}
    for raw in rows(cert["HISTOGRAM_ENVELOPES"]):
        row = object_row(raw)
        p = decode_profile(row["PROFILE"])
        if p in histograms:
            raise AssertionError("duplicate R16 histogram certificate")
        histograms[p] = row
    if histograms.keys() != set(owners):
        raise AssertionError("R16 histogram certificates omit a resolved owner")
    for p in owners:
        if sum(d * d for d in p) != 326 or profile_shadow_obstruction(p) is not None:
            raise AssertionError("owner violates the degree-class structural premises")
    plateau_certificate()
    above = above_cursor_rows(bounds)
    assert_no_omitted_above_cursor(bounds, above)
    return State(bounds, owners, histograms, above, hashes)


def current_state() -> State:
    return reconstruct_state(*committed_inputs())


def assert_solver_scope(profile: DegreeProfile, bounds: Mapping[DegreeProfile, int]) -> None:
    family, owners = family_state(bounds)
    if profile not in bounds or profile in (INITIAL_CURSOR_PROFILE, NEXT_CURSOR_PROFILE):
        raise AssertionError("unresolved cursor/plateau work forbidden")
    if family <= NEXT_CURSOR_BOUND or profile not in owners:
        raise AssertionError("only a current max/tied max resolved owner may be refined")


def cheap_certificate(state: State, profile: DegreeProfile) -> dict[str, object]:
    relaxation = degree_class_open_wedge_relaxation(
        tuple(6 + d for d in profile), wall_limit_seconds=CHEAP_WALL_SECONDS
    )
    prior = state.histogram_rows[profile]
    floor = integer(relaxation["WEIGHTED_OPEN_WEDGE_LOWER_BOUND"])
    cap = graph_triangle_upper_bound_from_open_wedges(tuple(6 + d for d in profile), floor)
    envelope = profile_family_envelope_from_triangle_bound(
        profile, cap["GRAPH_TRIANGLE_UPPER_BOUND"]
    )
    if (
        relaxation["SOLVER_STATUS"] != "OPTIMAL"
        or prior["RELAXATION_STATUS"] != "OPTIMAL"
        or floor != prior["WEIGHTED_OPEN_WEDGE_LOWER_BOUND"]
        or cap != prior["TRIANGLE_ENVELOPE"]
        or envelope != prior["PROFILE_ENVELOPE"]
    ):
        raise AssertionError("fresh R13 optimum differs from the independent committed R16 row")
    return {
        "PROFILE_ID": profile_id(profile),
        "OLD_BOUND": state.bounds[profile],
        "CERTIFIED_OWNER_BOUND": min(state.bounds[profile], envelope["FAMILY_UPPER_BOUND"]),
        "STRICT_REFINEMENT": envelope["FAMILY_UPPER_BOUND"] < state.bounds[profile],
        "R13_RELAXATION": relaxation,
        "TRIANGLE_ENVELOPE": cap,
        "PROFILE_ENVELOPE": envelope,
        "INDEPENDENT_R16_CERTIFICATE_MATCH": "PASS",
    }


def run_chase(
    state: State,
    cheap: Callable[[State, DegreeProfile], dict[str, object]],
    stronger: Callable[[DegreeProfile, Mapping[DegreeProfile, int]], dict[str, object]],
) -> Outcome:
    bounds = dict(state.bounds)
    steps: list[dict[str, object]] = []
    cheap_rows: list[dict[str, object]] = []
    attempts: list[dict[str, object]] = []
    dispatched: list[DegreeProfile] = []

    def adopt(profile: DegreeProfile, bound: int, kind: str) -> None:
        before, old_owners = family_state(bounds)
        old = bounds[profile]
        if bound >= old:
            raise AssertionError("adopted owner refinement must be strict")
        bounds[profile] = bound
        after, new_owners = family_state(bounds)
        steps.append(
            {
                "STEP": len(steps) + 1,
                "PROFILE_ID": profile_id(profile),
                "KIND": kind,
                "OLD_BOUND": old,
                "NEW_BOUND": bound,
                "FAMILY_BOUND_BEFORE": before,
                "FAMILY_BOUND_AFTER": after,
                "OWNER_SET_BEFORE": list(map(profile_id, old_owners)),
                "OWNER_SET_AFTER": list(map(profile_id, new_owners)),
            }
        )

    # Every member remains a tied max until a strict family drop. A drop is
    # terminal even during the cheap phase; no stale-owner dispatch may follow.
    for profile in state.owners:
        assert_solver_scope(profile, bounds)
        proof = cheap(state, profile)
        if proof.get("PROFILE_ID") != profile_id(profile):
            raise AssertionError("cheap certificate profile identity mismatch")
        cheap_rows.append(proof)
        bound = integer(proof["CERTIFIED_OWNER_BOUND"])
        if bound < bounds[profile]:
            adopt(profile, bound, "R13_DEGREE_CLASS_RELAXATION")
        if family_state(bounds)[0] < CHASE_START_BOUND:
            break

    # The live task leaves one owner after the 48 cheap checks. Handle ties by
    # recomputing after each strict refinement, and stop at the first family drop.
    while family_state(bounds)[0] >= CHASE_START_BOUND:
        _, owners = family_state(bounds)
        pending = [p for p in owners if p not in dispatched]
        if not pending:
            break
        profile = pending[0]
        assert_solver_scope(profile, bounds)
        dispatched.append(profile)
        proof = stronger(profile, dict(bounds))
        if proof.get("PROFILE_ID") != profile_id(profile):
            raise AssertionError("strong certificate profile identity mismatch")
        attempts.append(proof)
        bound = proof.get("CERTIFIED_OWNER_BOUND")
        if bound is not None:
            cap = integer(proof["REFINED_TRIANGLE_CAP"])
            if bound_from_cap(profile, cap, 112)[1] != integer(bound):
                raise AssertionError("strong owner bound does not reproduce its triangle cap")
            adopt(profile, integer(bound), str(proof["BOUND_LIMITING_RELAXATION"]))

    family, owners = family_state(bounds)
    status = (
        SUCCESS_A
        if family <= INCUMBENT
        else SUCCESS_B
        if max(bounds.values()) <= NEXT_CURSOR_BOUND
        else SUCCESS_C
        if family < CHASE_START_BOUND
        else NO_DROP
    )
    return Outcome(
        status,
        bounds,
        family,
        owners,
        tuple(cheap_rows),
        tuple(steps),
        tuple(attempts),
        tuple(dispatched),
    )


def committed_cheap_bounds(state: State) -> dict[DegreeProfile, int]:
    """Child guard uses pinned certificates, never reruns the 48 relaxations."""

    return {
        p: min(b, integer(state.histogram_rows[p]["FAMILY_UPPER_BOUND"]))
        if p in state.histogram_rows
        else b
        for p, b in state.bounds.items()
    }


def support_witness(profile: DegreeProfile) -> dict[str, object]:
    cp_model: Any = import_module("ortools.sat.python.cp_model")
    model, triples, doubles, _ = support_model(profile)
    solver: Any = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 649
    status = str(solver.StatusName(solver.Solve(model)))
    if status not in ("OPTIMAL", "FEASIBLE"):
        raise RuntimeError(f"surviving owner realizability witness was not found: {status}")
    ts = tuple(t for t, v in triples.items() if solver.Value(v))
    ds = tuple(d for d, v in doubles.items() if solver.Value(v))
    if len(ts) != 22 or len(ds) != 27:
        raise AssertionError("owner support witness counts changed")
    edges = [tuple(sorted(p)) for t in ts for p in combinations(t, 2)] + list(ds)
    if len(set(edges)) != 93:
        raise AssertionError("owner support witness violates pair linearity")
    for vertex, degree in enumerate(profile):
        if sum(vertex in t for t in ts) != degree or sum(vertex in d for d in ds) != 6 - degree:
            raise AssertionError("owner witness violates a ticket degree")
    started = monotonic()
    check = witness_open_wedge_check(profile, ts, ds, wall_limit_seconds=15.0)
    check["WITNESS_SOURCE"] = "R25_SURVIVING_RESOLVED_OWNER_SUPPORT_MODEL"
    return {
        "STATUS": "PASS",
        "REALIZABILITY_STATUS": status,
        "TRIPLES": list(ts),
        "DOUBLES": list(ds),
        "SOLVER_WALL_TIME_SECONDS": float(solver.WallTime()),
        "OPEN_WEDGE_MODEL_NONVACUITY": check,
        "NONVACUITY_CHECK_WALL_SECONDS": monotonic() - started,
    }


def solver_child(request: Mapping[str, object]) -> dict[str, object]:
    state = current_state()
    profile = decode_profile(request["PROFILE_ID"])
    bounds = {decode_profile(p): integer(b) for p, b in object_row(request["BOUNDS"]).items()}
    assert_solver_scope(profile, bounds)
    if bounds != committed_cheap_bounds(state) or len(family_state(bounds)[1]) != 1:
        raise AssertionError("stronger model requires the exact complete post-cheap ledger")
    route = str(request["ROUTE"])
    if route == "WITNESS":
        proof = support_witness(profile)
    elif route == ROUTES[0]:
        proof = exact_support_triangle_refutation(
            profile, refuted_triangle_count=273, wall_limit_seconds=NATIVE_SECONDS[route]
        )
    elif route in ROUTES[1:]:
        witness = object_row(request["WITNESS"])
        triples = tuple(
            cast(tuple[int, int, int], tuple(map(integer, rows(t))))
            for t in rows(witness["TRIPLES"])
        )
        doubles = tuple(
            cast(tuple[int, int], tuple(map(integer, rows(d)))) for d in rows(witness["DOUBLES"])
        )
        if route == ROUTES[1]:
            proof = complement_route_attempt(profile, triples, doubles)
        else:
            proof = motif_triangle_bound(
                profile, triples, doubles, wall_limit_seconds=NATIVE_SECONDS[route]
            )
            proof["STATUS"] = proof["SOLVER_STATUS"]
            proof["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] = proof[
                "SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND"
            ]
    else:
        raise AssertionError("unknown owner-only route")
    proof.update({"PROFILE_ID": profile_id(profile), "ROUTE": route})
    return proof


def bounded_call(
    profile: DegreeProfile,
    bounds: Mapping[DegreeProfile, int],
    route: str,
    *,
    deadline: float,
    witness: Mapping[str, object] | None = None,
) -> dict[str, object]:
    assert_solver_scope(profile, bounds)
    external = NATIVE_SECONDS[route] + EXTERNAL_GRACE_SECONDS
    if deadline - monotonic() < external + EXTERNAL_KILL_SECONDS:
        return {
            "PROFILE_ID": profile_id(profile),
            "ROUTE": route,
            "STATUS": "NOT_RUN_PROOF_WALL_BUDGET",
        }
    request = {
        "PROFILE_ID": profile_id(profile),
        "BOUNDS": {profile_id(p): b for p, b in bounds.items()},
        "ROUTE": route,
        "WITNESS": witness,
    }
    environment = {
        **os.environ,
        "PYTHONPATH": str(repo_root() / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
    started = monotonic()
    process = subprocess.run(
        [
            "timeout",
            "--signal=TERM",
            f"--kill-after={EXTERNAL_KILL_SECONDS}s",
            f"{external}s",
            sys.executable,
            "-m",
            MODULE_NAME,
            "--solver-request",
            json.dumps(request),
        ],
        cwd=repo_root(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=external + EXTERNAL_KILL_SECONDS + 10,
    )
    if process.returncode in (124, 137):
        proof: dict[str, object] = {
            "PROFILE_ID": profile_id(profile),
            "ROUTE": route,
            "STATUS": "EXTERNAL_HARD_TIMEOUT",
        }
    elif process.returncode != 0:
        raise RuntimeError(f"R25 solver child failed: {process.stderr[-2000:]}")
    else:
        proof = object_row(json.loads(process.stdout))
    proof.update(
        {
            "NATIVE_WALL_LIMIT_SECONDS": NATIVE_SECONDS[route],
            "EXTERNAL_HARD_TIMEOUT_SECONDS": external,
            "EXTERNAL_TIMEOUT_EXIT_CODE": process.returncode,
            "SUBPROCESS_WALL_SECONDS": monotonic() - started,
        }
    )
    return proof


def accepted_cap(proof: Mapping[str, object]) -> int | None:
    route = proof["ROUTE"]
    if route == ROUTES[0]:
        if proof.get("STATUS") != "INFEASIBLE":
            return None
        if (
            proof.get("CERTIFICATE_KIND") != "CP_SAT_INFEASIBLE"
            or proof.get("REFUTED_GRAPH_TRIANGLE_COUNT") != 273
            or proof.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND") != 272
            or proof.get("OPEN_WEDGE_CEILING_REFUTED") != 7
        ):
            raise AssertionError("exact-support refutation certificate identity mismatch")
        return 272
    if route not in ROUTES[1:] or proof.get("STATUS") not in ("OPTIMAL", "FEASIBLE"):
        return None
    cap = proof.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND")
    # These inherited minimization/maximization routes report certified objective
    # bounds for FEASIBLE too; their feasible objective itself is never adopted.
    return integer(cap) if cap is not None and integer(cap) < 273 else None


def refine_owner(
    profile: DegreeProfile, bounds: Mapping[DegreeProfile, int], *, deadline: float
) -> dict[str, object]:
    witness = bounded_call(profile, bounds, "WITNESS", deadline=deadline)
    if witness.get("STATUS") != "PASS":
        raise RuntimeError("surviving owner support/nonvacuity check did not pass")
    proofs: list[dict[str, object]] = []
    for route in ROUTES:
        proof = bounded_call(profile, bounds, route, deadline=deadline, witness=witness)
        proofs.append(proof)
        cap = accepted_cap(proof)
        if cap is not None:
            s3, bound = bound_from_cap(profile, cap, 112)
            return {
                "PROFILE_ID": profile_id(profile),
                "CERTIFIED_OWNER_BOUND": bound,
                "REFINED_TRIANGLE_CAP": cap,
                "REFINED_S3": s3,
                "S4_FLOOR": 112,
                "BOUND_LIMITING_RELAXATION": route,
                "ROUTES": proofs,
                "WITNESS_CHECK": witness,
                "LATER_ROUTES": "NOT_REQUIRED_AFTER_FIRST_CERTIFIED_STRICT_FAMILY_DROP",
            }
    return {
        "PROFILE_ID": profile_id(profile),
        "CERTIFIED_OWNER_BOUND": None,
        "ROUTES": proofs,
        "WITNESS_CHECK": witness,
        "LATER_ROUTES": "NOT_RUN_S4_MOTIF_OR_HIGHER_MULTIPLICITY",
    }


def compute_result() -> dict[str, object]:
    started = monotonic()
    primitives = canonical_primitive_preflight()
    runtime = solver_runtime_preflight()
    state = current_state()
    s4 = k20_min_s2_s4_lower_bound_certificate()
    if (K20_S1, K20_S2, s4.s4_lower_bound) != (372_228_640, 63_838_600, 112):
        raise AssertionError("canonical primitive/S4 authority changed")
    outcome = run_chase(
        state,
        cheap_certificate,
        lambda p, b: refine_owner(p, b, deadline=started + PROOF_WALL_SECONDS),
    )
    calls = [object_row(r) for a in outcome.attempts for r in rows(a["ROUTES"])]
    cheap_times = [
        object_row(r["R13_RELAXATION"])["SOLVER_WALL_TIME_SECONDS"] for r in outcome.cheap_rows
    ]
    solver_seconds = sum(float(cast(float, t)) for t in cheap_times) + sum(
        float(cast(float, r.get("SOLVER_WALL_TIME_SECONDS", 0.0))) for r in calls
    )
    final_above = above_cursor_rows(outcome.bounds)
    assert_no_omitted_above_cursor(outcome.bounds, final_above)
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": outcome.status,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "INPUT_AUTHORITY": "PINNED_R24_R16_GIT_BLOBS_PLUS_OWNER_RESUME_PACKET",
        "COMMITTED_INPUT_SHA256": dict(state.input_hashes),
        "START_FAMILY_BOUND": START_FAMILY_BOUND,
        "OWNER_CHASE_START_FAMILY_BOUND": CHASE_START_BOUND,
        **plateau_certificate(),
        "PLATEAU_CERTIFICATE": plateau_certificate(),
        "NEXT_CURSOR_BOUND": NEXT_CURSOR_BOUND,
        "RESOLVED_OWNER_COUNT": len(state.owners),
        "EXACT_48_RESOLVED_OWNER_SET": list(map(profile_id, state.owners)),
        "EXACT_OWNER_SET_COMPLETENESS": "PASS_R24_MAXIMUM_EQUALS_COMPLETE_R16_SUFFIX",
        "INITIAL_RESOLVED_ABOVE_NEXT_CURSOR": list(state.above_cursor),
        "INITIAL_RESOLVED_ABOVE_NEXT_CURSOR_COUNT": len(state.above_cursor),
        "NON_OWNER_RESOLVED_ABOVE_NEXT_CURSOR_COUNT": len(state.above_cursor) - len(state.owners),
        "NO_OMITTED_RESOLVED_ABOVE_CURSOR": "PASS",
        "CHEAPLY_REFINED_OWNER_COUNT": sum(
            bool(r["STRICT_REFINEMENT"]) for r in outcome.cheap_rows
        ),
        "CHEAP_RELAXATION_COUNT": len(outcome.cheap_rows),
        "CHEAP_CERTIFICATES": list(outcome.cheap_rows),
        "INDEPENDENT_47_OF_48_CHECK": (
            "FRESH_R13_OPTIMA_MATCH_ALL_PINNED_R16_HISTOGRAM_CERTIFICATES"
        ),
        "POST_CHEAP_OWNER_SET": list(
            map(profile_id, family_state(committed_cheap_bounds(state))[1])
        ),
        "REFINEMENT_STEPS": list(outcome.steps),
        "OWNER_ATTEMPTS": list(outcome.attempts),
        "OWNER_TRANSITION_COUNT": sum(
            s["OWNER_SET_BEFORE"] != s["OWNER_SET_AFTER"] for s in outcome.steps
        ),
        "OWNERS_REFINED_COUNT": len({s["PROFILE_ID"] for s in outcome.steps}),
        "STRONGER_OWNER_PROFILES_DISPATCHED": list(map(profile_id, outcome.dispatched)),
        "CURRENT_BOUND_OWNER_SET": list(map(profile_id, outcome.owners)),
        "FAMILY_UPPER_BOUND": outcome.family_bound,
        "MAX_RESOLVED_BOUND": max(outcome.bounds.values()),
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": outcome.family_bound - INCUMBENT,
        "FAMILY_STATUS": "CLOSED"
        if outcome.status == SUCCESS_A
        else "OPEN_STRICTLY_TIGHTENED"
        if outcome.family_bound < START_FAMILY_BOUND
        else "OPEN",
        "OWNER_CHASE_CERTIFIED_FAMILY_DROP": CHASE_START_BOUND - outcome.family_bound,
        "TOTAL_CERTIFIED_FAMILY_DROP": START_FAMILY_BOUND - outcome.family_bound,
        "CURSOR_GENUINELY_LOAD_BEARING": max(outcome.bounds.values()) <= NEXT_CURSOR_BOUND,
        "FINAL_RESOLVED_ABOVE_NEXT_CURSOR": list(final_above),
        "FINAL_RESOLVED_LEDGER": [
            {"PROFILE_ID": profile_id(p), "CURRENT_BOUND": b}
            for p, b in sorted(
                outcome.bounds.items(), key=lambda item: (item[1], item[0]), reverse=True
            )
        ],
        "RESOLVED_LEDGER_COUNT": len(outcome.bounds),
        "RESOLVED_PROFILE_COUNT_INCLUDING_FROZEN_CLASS": len(outcome.bounds)
        + PLATEAU_PROFILE_COUNT,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "CANONICAL_PRIMITIVES": primitives,
        "S4_CERTIFICATE": asdict(s4),
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_STATUS": "OPTIMAL_R13_AND_INFEASIBLE_EXACT_SUPPORT"
        if calls and calls[-1].get("STATUS") == "INFEASIBLE"
        else "SEE_OWNER_ATTEMPTS",
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "R13_PER_HISTOGRAM_SECONDS": CHEAP_WALL_SECONDS,
            **NATIVE_SECONDS,
            "EXTERNAL_GRACE_SECONDS": EXTERNAL_GRACE_SECONDS,
            "EXTERNAL_KILL_AFTER_SECONDS": EXTERNAL_KILL_SECONDS,
            "PROOF_WALL_SECONDS": PROOF_WALL_SECONDS,
            "CP_SAT_SEARCH_WORKERS": 1,
        },
        "SOLVER_ACTUAL_WALL_TIME": solver_seconds,
        "SOLVER_ACTUAL_WALL_TIME_SCOPE": "REPORTED_R13_AND_STRONGER_CERTIFICATE_SOLVER_TIMES",
        "SOLVER_CERTIFIED_BOUND": max(
            (
                integer(a["CERTIFIED_OWNER_BOUND"])
                for a in outcome.attempts
                if a.get("CERTIFIED_OWNER_BOUND") is not None
            ),
            default=None,
        ),
        "SOLVER_CERTIFIED_BOUND_SCOPE": "SURVIVING_RESOLVED_OWNER_ONLY",
        "PROOF_ACTUAL_WALL_SECONDS": monotonic() - started,
        "STOP_RULE": "FIRST_A_OR_B_OR_STRICT_CHASE_FAMILY_DROP_WITH_EXACT_REMAINING_OWNERS",
        "CURSOR_PROFILE_SOLVES": 0,
        "NO_CURSOR_WORK_GUARD": "PASS",
        "INDIVIDUAL_PLATEAU_SOLVES": 0,
        "PLATEAU_RERUN_COUNT": 0,
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        "SOLVER_MODEL_SOURCE_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "RUNTIME_TRANSITION_OCCURRED": "NO",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solver-request")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.solver_request is not None:
        print(json.dumps(solver_child(object_row(json.loads(args.solver_request)))))
        return
    if repo_root() != Path(WORKTREE_PATH):
        raise RuntimeError("module resolved outside the exact retained R25 worktree")
    if args.output is not None:
        if args.output.resolve() != result_path():
            raise ValueError("output must be the exact R25 result path")
        if result_path().exists():
            raise FileExistsError("preserve the existing R25 result; do not rerun the proof")
    result = compute_result()
    if args.output is not None:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "CHEAPLY_REFINED_OWNER_COUNT",
                    "FAMILY_UPPER_BOUND",
                    "CURRENT_BOUND_OWNER_SET",
                    "SOLVER_ACTUAL_WALL_TIME",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
