"""Refine R21's two resolved owners, stopping when its untouched cursor carries.

Consume the complete committed R20 ledger and R21 class certificate without
re-solving either. Reconstruct only the two owner certificates from R12/R20.
One graph-triangle decrement is sufficient; prefer an exact-support refutation
and stop dispatching as soon as the full ledger maximum reaches the cursor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from time import monotonic
from typing import cast

from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import solver_runtime_preflight
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import canonical_primitive_preflight
from .b649_k20_min_s2_higher_order_closure_r2 import (
    K20_S1,
    K20_S2,
    k20_min_s2_s4_lower_bound_certificate,
)
from .b649_k20_min_s2_next_distinct_plateau_r10 import (
    _motif_triangle_bound as motif_triangle_bound,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_r16_freeze_and_owner_refinement_r17 import (
    complement_route_attempt,
    exact_support_triangle_refutation,
    witness_open_wedge_check,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import overlap_wedge_count
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    bound_from_cap,
    decode_profile,
    profile_id,
    support_witness,
)

DegreeProfile = tuple[int, ...]
TASK_ID = "B649_K20_MIN_S2_RESOLVED_OWNER_PAIR_REFINEMENT_R22"
TASK_BRANCH = "codex/b649-k20-min-s2-resolved-owner-pair-refinement-r22"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "3e4d1a96891d74aba29b35052cee17ba57735b8f"
BASE_TREE = "ded8639944bcfc12c0d2a7b9341b27917577d2a0"
START_BOUND = 313_656_776
INCUMBENT = 313_239_661
CURSOR_BOUND = 313_655_320
CURSOR_PROFILE: DegreeProfile = tuple(map(int, "66666665433111111111"))
OWNER_IDS = ("66665555555411100000", "66655555555521000000")
OWNER_PROFILES = tuple(tuple(map(int, identity)) for identity in OWNER_IDS)
EXPECTED_RESOLVED_COUNT = 339
PLATEAU_BOUND = 313_646_248
MAX_OWNER_PROFILES = 8
PROOF_WALL_SECONDS = 3_600.0
NATIVE_REFUTATION_SECONDS = 60.0
MAX_NATIVE_REFUTATION_SECONDS = 600.0
NATIVE_COMPLEMENT_SECONDS = 90.0
NATIVE_WITNESS_SECONDS = 30.0
EXTERNAL_GRACE_SECONDS = 30.0
RESULT_DIRECTORY = "docs/research/matrix-native-results"
RESULT_FILENAME = "b649-k20-min-s2-resolved-owner-pair-refinement-r22-result.json"
MODULE_NAME = "lottolab.research.b649_k20_min_s2_resolved_owner_pair_refinement_r22"
INPUT_FILENAMES = {
    "R12": "b649-k20-min-s2-continued-multi-plateau-descent-r12-result.json",
    "R20": "b649-k20-min-s2-resolved-above-cursor-owner-chase-r20-result.json",
    "R21": "b649-k20-min-s2-unique-cursor-plateau-r21-result.json",
}
INPUT_SHA256 = {
    "R12": "e36cf3010e077923a7c27efa83e3b9dc157b3e34e5458708eb70ce40998f77f0",
    "R20": "47afe9b8e5643f0123fcccfcf678689755106056e7b9b68a3431b837706113aa",
    "R21": "7d3ffa7b063701a33f00b55f3e203c249c1691187b081341f563b9c72a9548be",
}
ROUTES = (
    "A_EXACT_SUPPORT_OPEN_WEDGE_REFUTATION",
    "B_COMPLEMENT_TRIANGLE_LOWER_BOUND",
    "C_EXACT_NONCORE_TRIANGLE_CEILING",
)
SUCCESS_A = "SUCCESS_A_FAMILY_CLOSED"
SUCCESS_B = "SUCCESS_B_ALL_RESOLVED_AT_OR_BELOW_CURSOR"
SUCCESS_C = "SUCCESS_C_STRICT_FAMILY_TIGHTENING_EXACT_REMAINING_OWNERS"


@dataclass(frozen=True, slots=True)
class CurrentState:
    bounds: Mapping[DegreeProfile, int]
    owners: Mapping[DegreeProfile, Certificate]
    lineage: tuple[dict[str, object], ...]
    input_hashes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class Outcome:
    status: str
    bounds: Mapping[DegreeProfile, int]
    family_bound: int
    owners: tuple[DegreeProfile, ...]
    attempts: tuple[dict[str, object], ...]
    steps: tuple[dict[str, object], ...]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def result_path() -> Path:
    return repo_root() / RESULT_DIRECTORY / RESULT_FILENAME


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AssertionError("expected certificate object")
    return cast(dict[str, object], value)


def _rows(value: object) -> list[object]:
    if not isinstance(value, list):
        raise AssertionError("expected certificate rows")
    return cast(list[object], value)


def _integer(value: object) -> int:
    if type(value) is not int:
        raise AssertionError("expected exact integer certificate")
    return value


def committed_inputs() -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    results: dict[str, dict[str, object]] = {}
    hashes: dict[str, str] = {}
    for label, filename in INPUT_FILENAMES.items():
        relative = f"{RESULT_DIRECTORY}/{filename}"
        blob = subprocess.check_output(["git", "show", f"{BASE_HEAD}:{relative}"], cwd=repo_root())
        digest = hashlib.sha256(blob).hexdigest()
        if digest != INPUT_SHA256[label]:
            raise AssertionError(f"committed {label} identity changed")
        results[label] = _object(json.loads(blob))
        hashes[relative] = digest
    return results, hashes


def family_state(bounds: Mapping[DegreeProfile, int]) -> tuple[int, tuple[DegreeProfile, ...]]:
    if not bounds or CURSOR_PROFILE in bounds:
        raise AssertionError("cursor must remain unresolved outside the complete ledger")
    maximum = max(CURSOR_BOUND, *bounds.values())
    owners = tuple(sorted((p for p, b in bounds.items() if b == maximum), reverse=True))
    if maximum == CURSOR_BOUND:
        owners = (CURSOR_PROFILE, *owners)
    return maximum, owners


def assert_exact_owner_pair(bounds: Mapping[DegreeProfile, int]) -> None:
    if len(bounds) != EXPECTED_RESOLVED_COUNT:
        raise AssertionError("complete resolved ledger count changed")
    if family_state(bounds) != (START_BOUND, OWNER_PROFILES):
        raise AssertionError("exact two-owner family maximum changed")
    above = {p for p, bound in bounds.items() if bound > CURSOR_BOUND}
    if above != set(OWNER_PROFILES):
        raise AssertionError("third resolved owner above cursor or missing owner")


def reconstruct_state(
    inputs: Mapping[str, dict[str, object]], hashes: Mapping[str, str]
) -> CurrentState:
    r12, r20, r21 = (inputs[label] for label in ("R12", "R20", "R21"))
    expected: dict[str, object] = {
        "FAMILY_UPPER_BOUND": START_BOUND,
        "CURRENT_BOUND_OWNER_SET": list(OWNER_IDS),
        "NEXT_ACTIVE_BOUND": CURSOR_BOUND,
        "NEXT_ACTIVE_PROFILE": profile_id(CURSOR_PROFILE),
        "ANALYTIC_CLASS_CERTIFIED_BOUND": PLATEAU_BOUND,
        "CURRENT_PLATEAU_COMPLETELY_RESOLVED": True,
        "INCUMBENT": INCUMBENT,
    }
    for key, value in expected.items():
        if r21.get(key) != value:
            raise AssertionError(f"R21 owner/cursor authority mismatch: {key}")
    if r20.get("RESOLVED_LEDGER_COUNT") != 282:
        raise AssertionError("R20 ledger authority changed")
    bounds: dict[DegreeProfile, int] = {}
    for raw in _rows(r20["FINAL_RESOLVED_LEDGER"]):
        row = _object(raw)
        profile = decode_profile(row["PROFILE_ID"])
        if profile in bounds:
            raise AssertionError("duplicate resolved profile")
        bounds[profile] = _integer(row["CURRENT_BOUND"])
    if len(bounds) != 282:
        raise AssertionError("incomplete R20 resolved ledger")
    classes = _rows(r21["CLASS_CERTIFICATES"])
    if len(classes) != 1:
        raise AssertionError("R21 plateau certificate count changed")
    plateau = _object(classes[0])
    identities = _rows(plateau["PROFILE_IDENTITIES"])
    if (
        len(identities) != 57
        or plateau.get("CLASS_FAMILY_UPPER_BOUND") != PLATEAU_BOUND
        or plateau.get("COMPLETE_PLATEAU_COVERAGE") is not True
        or identities != r21.get("CURRENT_LOAD_BEARING_PLATEAU")
    ):
        raise AssertionError("complete retained R21 plateau changed")
    for raw in identities:
        profile = decode_profile(raw)
        if profile in bounds or profile == CURSOR_PROFILE:
            raise AssertionError("duplicate plateau profile or processed cursor")
        bounds[profile] = PLATEAU_BOUND
    assert_exact_owner_pair(bounds)

    owners: dict[DegreeProfile, Certificate] = {}
    lineage: list[dict[str, object]] = []
    for index, (profile, source_index) in enumerate(zip(OWNER_PROFILES, (8, 10), strict=True)):
        row = _object(_rows(r12["PROFILE_BOUNDS"])[source_index])
        attempt = _object(_rows(r20["OWNER_ATTEMPTS"])[index])
        proof = _object(_rows(attempt["ROUTES"])[0])
        if (
            decode_profile(row["PROFILE"]) != profile
            or row.get("REALIZABILITY") != "REALIZABLE"
            or row.get("SUPPORT_SOLVER_STATUS") != "OPTIMAL"
            or attempt.get("PROFILE_ID") != profile_id(profile)
            or attempt.get("CERTIFIED_OWNER_BOUND") != START_BOUND
            or attempt.get("REFINED_TRIANGLE_CAP") != 272
            or attempt.get("REFINED_S3") != 5_266_800
            or attempt.get("S4_FLOOR") != 112
            or proof.get("STATUS") != "INFEASIBLE"
            or proof.get("REFUTED_GRAPH_TRIANGLE_COUNT") != 273
            or proof.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND") != 272
            or bounds[profile] != START_BOUND
            or bound_from_cap(profile, 272, 112) != (5_266_800, START_BOUND)
        ):
            raise AssertionError("committed owner certificate does not reproduce its bound")
        cert = Certificate(
            profile,
            START_BOUND,
            INPUT_FILENAMES["R20"],
            f"OWNER_ATTEMPTS[{index}]",
            "REALIZABLE",
            5_266_800,
            112,
            272,
            ROUTES[0],
            row,
            f"R12.PROFILE_BOUNDS[{source_index}]",
        )
        triples, doubles = support_witness(cert)
        owners[profile] = cert
        lineage.append(
            {
                "PROFILE_ID": profile_id(profile),
                "DEGREE_PROFILE": list(profile),
                "SOURCE_RESULT": cert.source_result,
                "SOURCE_ROW": cert.source_row,
                "R20_LEDGER_ROW": f"FINAL_RESOLVED_LEDGER[{index}]",
                "WITNESS_SOURCE": cert.witness_source,
                "REALIZABILITY_STATUS": cert.realizability,
                "WITNESS_TRIPLES": [list(t) for t in triples],
                "WITNESS_DOUBLE_SUPPORTS": [list(p) for p in doubles],
                "WITNESS_VALIDATION": "PASS",
                "WEDGE_COUNT": overlap_wedge_count(profile),
                "PRIOR_DEGREE_CLASS_TRIANGLE_CAP": row["GRAPH_TRIANGLE_UPPER_BOUND"],
                "PRIOR_MOTIF_TRIANGLE_CAP": _object(row["MOTIF_SOLVER"])[
                    "SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND"
                ],
                "GRAPH_TRIANGLE_CAP": 272,
                "NONCORE_TRIANGLE_CAP": 250,
                "OPEN_WEDGE_FLOOR": 16,
                "S3": cert.s3,
                "S4_FLOOR": cert.s4,
                "S4_SCOPE": "ALL_REALIZATIONS_INCLUDING_S3_MAXIMIZERS",
                "FOURTH_ORDER_CREDIT": 64,
                "BOUND_LIMITING_RELAXATION": cert.relaxation,
                "EXACT_RELAXATION": {
                    "IDENTITY": "S1 - S2 + S3 - floor(4*S4/7)",
                    "S1": K20_S1,
                    "S2": K20_S2,
                    "S3": cert.s3,
                    "S4_FLOOR": cert.s4,
                    "VALUE": START_BOUND,
                },
                "COMMITTED_OPEN_WEDGE_PROOF": proof,
            }
        )
    return CurrentState(bounds, owners, tuple(lineage), hashes)


def current_state() -> CurrentState:
    inputs, hashes = committed_inputs()
    return reconstruct_state(inputs, hashes)


def assert_solver_scope(profile: DegreeProfile, bounds: Mapping[DegreeProfile, int]) -> None:
    maximum, owners = family_state(bounds)
    if profile == CURSOR_PROFILE or profile not in bounds:
        raise AssertionError("unresolved cursor/profile work forbidden")
    if bounds[profile] <= CURSOR_BOUND or maximum <= CURSOR_BOUND or profile not in owners:
        raise AssertionError("only current max/tied max owners above cursor may be refined")


def accepted_refutation_cap(proof: Mapping[str, object], cap: int) -> int | None:
    if proof.get("STATUS") != "INFEASIBLE":
        return None
    if (
        proof.get("CERTIFICATE_KIND") != "CP_SAT_INFEASIBLE"
        or proof.get("REFUTED_GRAPH_TRIANGLE_COUNT") != cap
        or proof.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND") != cap - 1
    ):
        raise AssertionError("refutation certificate identity mismatch")
    return cap - 1


def run_schedule(
    state: CurrentState,
    refine: Callable[[Certificate, Mapping[DegreeProfile, int]], dict[str, object]],
) -> Outcome:
    bounds = dict(state.bounds)
    attempts: list[dict[str, object]] = []
    steps: list[dict[str, object]] = []
    tried: set[DegreeProfile] = set()
    while True:
        family, owners = family_state(bounds)
        if family <= INCUMBENT:
            status = SUCCESS_A
            break
        if max(bounds.values()) <= CURSOR_BOUND:
            status = SUCCESS_B
            break
        if family < START_BOUND:
            status = SUCCESS_C
            break
        pending = [p for p in owners if p not in tried]
        if not pending or len(tried) >= MAX_OWNER_PROFILES:
            status = "NO_CERTIFIED_FAMILY_DROP"
            break
        owner = pending[0]
        assert_solver_scope(owner, bounds)
        cert = state.owners[owner]
        attempt = refine(cert, dict(bounds))
        tried.add(owner)
        attempts.append(attempt)
        candidate = attempt.get("CERTIFIED_OWNER_BOUND")
        if candidate is None:
            continue
        refined = _integer(candidate)
        if refined >= bounds[owner]:
            raise AssertionError("owner improvement must be strict")
        before = bounds[owner]
        bounds[owner] = refined
        after, next_owners = family_state(bounds)
        steps.append(
            {
                "STEP": len(steps) + 1,
                "PROFILE_ID": profile_id(owner),
                "START_OWNER_BOUND": before,
                "REFINED_OWNER_BOUND": refined,
                "FAMILY_BOUND_BEFORE": family,
                "FAMILY_BOUND_AFTER": after,
                "OWNER_SET_BEFORE": list(map(profile_id, owners)),
                "OWNER_SET_AFTER": list(map(profile_id, next_owners)),
                "CERTIFICATE": attempt,
            }
        )
    return Outcome(status, bounds, family, owners, tuple(attempts), tuple(steps))


def solver_child(request: Mapping[str, object]) -> dict[str, object]:
    state = current_state()
    profile = decode_profile(request["PROFILE_ID"])
    bounds = {
        decode_profile(p): _integer(v) for p, v in _object(request["EFFECTIVE_BOUNDS"]).items()
    }
    if bounds.keys() != state.bounds.keys():
        raise AssertionError("solver request omits or adds resolved profiles")
    if any(bounds[p] != value for p, value in state.bounds.items() if p not in state.owners):
        raise AssertionError("request mutates a non-owner certificate")
    if any(bounds[p] > value for p, value in state.bounds.items()):
        raise AssertionError("request weakens a committed bound")
    assert_solver_scope(profile, bounds)
    cert = state.owners[profile]
    triples, doubles = support_witness(cert)
    route = request["ROUTE"]
    if route == "WITNESS":
        result = witness_open_wedge_check(
            profile, triples, doubles, wall_limit_seconds=NATIVE_WITNESS_SECONDS
        )
        result["WITNESS_SOURCE"] = cert.witness_source
    elif route == ROUTES[0]:
        native = float(
            cast(float, request.get("REFUTATION_WALL_SECONDS", NATIVE_REFUTATION_SECONDS))
        )
        if not 0 < native <= MAX_NATIVE_REFUTATION_SECONDS:
            raise ValueError("refutation native wall limit outside bounded envelope")
        result = exact_support_triangle_refutation(
            profile,
            refuted_triangle_count=_integer(cert.triangle_cap),
            wall_limit_seconds=native,
        )
    elif route == ROUTES[1]:
        result = complement_route_attempt(profile, triples, doubles)
    elif route == ROUTES[2]:
        result = motif_triangle_bound(
            profile, triples, doubles, wall_limit_seconds=NATIVE_REFUTATION_SECONDS
        )
        result["STATUS"] = result["SOLVER_STATUS"]
        result["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] = result[
            "SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND"
        ]
    else:
        raise AssertionError("unknown owner-only solver route")
    result.update({"ROUTE": route, "PROFILE_ID": profile_id(profile)})
    return result


def bounded_solver_call(
    cert: Certificate,
    bounds: Mapping[DegreeProfile, int],
    route: str,
    *,
    deadline: float,
    refutation_wall_seconds: float = NATIVE_REFUTATION_SECONDS,
) -> dict[str, object]:
    assert_solver_scope(cert.profile, bounds)
    if not 0 < refutation_wall_seconds <= MAX_NATIVE_REFUTATION_SECONDS:
        raise ValueError("refutation native wall limit outside bounded envelope")
    native = NATIVE_COMPLEMENT_SECONDS if route == ROUTES[1] else NATIVE_REFUTATION_SECONDS
    if route == ROUTES[0]:
        native = refutation_wall_seconds
    external = native + EXTERNAL_GRACE_SECONDS
    if deadline - monotonic() < external:
        return {"ROUTE": route, "STATUS": "NOT_RUN_PROOF_WALL_BUDGET"}
    request = {
        "PROFILE_ID": profile_id(cert.profile),
        "ROUTE": route,
        "REFUTATION_WALL_SECONDS": refutation_wall_seconds,
        "EFFECTIVE_BOUNDS": {profile_id(p): b for p, b in bounds.items()},
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
    try:
        process = subprocess.run(
            [sys.executable, "-m", MODULE_NAME, "--solver-request", json.dumps(request)],
            cwd=repo_root(),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=external,
        )
    except subprocess.TimeoutExpired:
        return {
            "ROUTE": route,
            "PROFILE_ID": profile_id(cert.profile),
            "STATUS": "EXTERNAL_HARD_TIMEOUT",
            "EXTERNAL_HARD_TIMEOUT_SECONDS": external,
            "SUBPROCESS_WALL_SECONDS": monotonic() - started,
            "TERMINATION": "TASK_OWNED_CHILD_KILLED_AND_REAPED",
        }
    if process.returncode != 0:
        raise RuntimeError(f"owner solver child failed: {process.stderr[-2000:]}")
    result = _object(json.loads(process.stdout))
    result.update(
        {
            "EXTERNAL_HARD_TIMEOUT_SECONDS": external,
            "SUBPROCESS_WALL_SECONDS": monotonic() - started,
        }
    )
    return result


def refine_owner(
    cert: Certificate,
    bounds: Mapping[DegreeProfile, int],
    *,
    deadline: float,
    refutation_wall_seconds: float = NATIVE_REFUTATION_SECONDS,
) -> dict[str, object]:
    witness = bounded_solver_call(cert, bounds, "WITNESS", deadline=deadline)
    if witness.get("STATUS") != "PASS":
        raise RuntimeError("owner witness non-vacuity check did not pass")
    routes: list[dict[str, object]] = []
    cap = _integer(cert.triangle_cap)
    s4 = _integer(cert.s4)
    for route in ROUTES:
        proof = bounded_solver_call(
            cert, bounds, route, deadline=deadline, refutation_wall_seconds=refutation_wall_seconds
        )
        routes.append(proof)
        candidate = (
            accepted_refutation_cap(proof, cap)
            if route == ROUTES[0]
            else (
                _integer(proof["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
                if proof.get("STATUS") == "OPTIMAL"
                else None
            )
        )
        if candidate is not None and candidate < cap:
            # Retain only the one-triangle decrement needed to reach the cursor.
            refined_cap = cap - 1
            s3, bound = bound_from_cap(cert.profile, refined_cap, s4)
            return {
                "PROFILE_ID": profile_id(cert.profile),
                "START_BOUND": cert.bound,
                "START_TRIANGLE_CAP": cap,
                "REFINED_TRIANGLE_CAP": refined_cap,
                "REFINED_NONCORE_TRIANGLE_CAP": refined_cap - 22,
                "REFINED_S3": s3,
                "S4_FLOOR": s4,
                "CERTIFIED_OWNER_BOUND": bound,
                "BOUND_LIMITING_RELAXATION": route,
                "ROUTES": routes,
                "WITNESS_CHECK": witness,
                "LATER_ROUTES": "NOT_REQUIRED",
            }
    return {
        "PROFILE_ID": profile_id(cert.profile),
        "CERTIFIED_OWNER_BOUND": None,
        "ROUTES": routes,
        "WITNESS_CHECK": witness,
    }


def resume_bounds(state: CurrentState, previous: Mapping[str, object]) -> dict[DegreeProfile, int]:
    """Accept only observed strict owner certificates; never reset an improved owner."""

    if (
        previous.get("TASK_ID") != TASK_ID
        or previous.get("BASE_HEAD") != BASE_HEAD
        or previous.get("TASK_STATUS") != "NO_CERTIFIED_FAMILY_DROP"
        or previous.get("COMMITTED_INPUT_SHA256") != dict(state.input_hashes)
    ):
        raise AssertionError("resume task or immutable input authority mismatch")
    bounds = dict(state.bounds)
    for raw in _rows(previous["REFINEMENT_STEPS"]):
        step = _object(raw)
        profile = decode_profile(step["PROFILE_ID"])
        assert_solver_scope(profile, bounds)
        attempt = _object(step["CERTIFICATE"])
        cert = state.owners[profile]
        proofs = [_object(p) for p in _rows(attempt["ROUTES"])]
        if (
            attempt.get("BOUND_LIMITING_RELAXATION") != ROUTES[0]
            or not proofs
            or accepted_refutation_cap(proofs[-1], _integer(cert.triangle_cap))
            != attempt.get("REFINED_TRIANGLE_CAP")
        ):
            raise AssertionError("resume requires an exact-support refutation certificate")
        s3, bound = bound_from_cap(
            profile, _integer(attempt["REFINED_TRIANGLE_CAP"]), _integer(cert.s4)
        )
        if (
            attempt.get("REFINED_S3") != s3
            or step.get("REFINED_OWNER_BOUND") != bound
            or attempt.get("CERTIFIED_OWNER_BOUND") != bound
            or bound >= bounds[profile]
        ):
            raise AssertionError("resume owner certificate does not reproduce its bound")
        bounds[profile] = bound
    final: dict[DegreeProfile, int] = {}
    for raw in _rows(previous["FINAL_RESOLVED_LEDGER"]):
        row = _object(raw)
        profile = decode_profile(row["PROFILE_ID"])
        if profile in final:
            raise AssertionError("duplicate resumed ledger profile")
        final[profile] = _integer(row["CURRENT_BOUND"])
    if final != bounds or family_state(bounds)[0] != START_BOUND:
        raise AssertionError("resume changes an uncertified bound or a completed family")
    return bounds


def compute_result(
    *,
    previous: Mapping[str, object] | None = None,
    refutation_wall_seconds: float = NATIVE_REFUTATION_SECONDS,
) -> dict[str, object]:
    started = monotonic()
    prior_wall = (
        0.0 if previous is None else float(cast(float, previous["PROOF_ACTUAL_WALL_SECONDS"]))
    )
    deadline = started + PROOF_WALL_SECONDS - prior_wall
    primitives = canonical_primitive_preflight()
    runtime = solver_runtime_preflight()
    state = current_state()
    s4 = k20_min_s2_s4_lower_bound_certificate()
    if s4.s4_lower_bound != 112:
        raise AssertionError("universal S4 floor changed")
    effective = state if previous is None else replace(state, bounds=resume_bounds(state, previous))
    outcome = run_schedule(
        effective,
        lambda c, b: refine_owner(
            c, b, deadline=deadline, refutation_wall_seconds=refutation_wall_seconds
        ),
    )
    prior_attempts = (
        () if previous is None else tuple(_object(raw) for raw in _rows(previous["OWNER_ATTEMPTS"]))
    )
    prior_steps = (
        ()
        if previous is None
        else tuple(_object(raw) for raw in _rows(previous["REFINEMENT_STEPS"]))
    )
    outcome = replace(
        outcome,
        attempts=(*prior_attempts, *outcome.attempts),
        steps=(
            *prior_steps,
            *({**step, "STEP": i + 1 + len(prior_steps)} for i, step in enumerate(outcome.steps)),
        ),
    )
    calls = [row for attempt in outcome.attempts for row in _rows(attempt["ROUTES"])]
    solver_seconds = sum(
        float(cast(float, _object(r).get("SOLVER_WALL_TIME_SECONDS", 0.0))) for r in calls
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "TASK_STATUS": outcome.status,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "START_FAMILY_BOUND": START_BOUND,
        "OWNER_PROFILE_COUNT": len(state.owners),
        "OWNER_PROFILES": list(OWNER_IDS),
        "OWNER_CERTIFICATES": list(state.lineage),
        "START_OWNER_BOUNDS": {profile_id(p): c.bound for p, c in state.owners.items()},
        "REFINED_OWNER_BOUNDS": {profile_id(p): outcome.bounds[p] for p in state.owners},
        "COMMITTED_INPUT_SHA256": dict(state.input_hashes),
        "INPUT_AUTHORITY": "IMMUTABLE_BASE_HEAD_R12_R20_R21_GIT_BLOBS",
        "RESOLVED_LEDGER_COUNT": len(state.bounds),
        "EXACT_OWNER_PAIR_ASSERTION": "PASS",
        "NO_THIRD_OWNER_ABOVE_CURSOR": "PASS",
        "OWNER_ATTEMPTS": list(outcome.attempts),
        "REFINEMENT_STEPS": list(outcome.steps),
        "OWNER_TRANSITION_COUNT": len(outcome.steps),
        "OWNERS_REFINED_COUNT": len(outcome.steps),
        "NEXT_CURSOR_BOUND": CURSOR_BOUND,
        "NEXT_CURSOR_PROFILE": profile_id(CURSOR_PROFILE),
        "FAMILY_UPPER_BOUND": outcome.family_bound,
        "CURRENT_BOUND_OWNER_SET": list(map(profile_id, outcome.owners)),
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": max(0, outcome.family_bound - INCUMBENT),
        "FAMILY_STATUS": "CLOSED"
        if outcome.status == SUCCESS_A
        else "OPEN_STRICTLY_TIGHTENED"
        if outcome.family_bound < START_BOUND
        else "OPEN",
        "CERTIFIED_FAMILY_DROP": START_BOUND - outcome.family_bound,
        "CURSOR_GENUINELY_LOAD_BEARING": max(outcome.bounds.values()) <= CURSOR_BOUND,
        "MAX_RESOLVED_BOUND": max(outcome.bounds.values()),
        "FINAL_RESOLVED_LEDGER": [
            {"PROFILE_ID": profile_id(p), "CURRENT_BOUND": b}
            for p, b in sorted(
                outcome.bounds.items(), key=lambda item: (item[1], item[0]), reverse=True
            )
        ],
        "CANONICAL_PRIMITIVES": primitives,
        "CANONICAL_PRIMITIVE_STATUS": "PASS",
        "S4_CERTIFICATE": asdict(s4),
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_STATUS": "INFEASIBLE_CERTIFIED_OWNER_PAIR"
        if all(
            _object(a["CERTIFICATE"]).get("BOUND_LIMITING_RELAXATION") == ROUTES[0]
            for a in outcome.steps
        )
        and len(outcome.steps) == 2
        else "SEE_OWNER_ATTEMPTS",
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "INITIAL_NATIVE_REFUTATION_SECONDS": NATIVE_REFUTATION_SECONDS,
            "NATIVE_REFUTATION_SECONDS": refutation_wall_seconds,
            "NATIVE_COMPLEMENT_SECONDS": NATIVE_COMPLEMENT_SECONDS,
            "NATIVE_WITNESS_SECONDS_PER_SOLVE": NATIVE_WITNESS_SECONDS,
            "EXTERNAL_REFUTATION_TIMEOUT_SECONDS": refutation_wall_seconds + EXTERNAL_GRACE_SECONDS,
            "EXTERNAL_COMPLEMENT_TIMEOUT_SECONDS": NATIVE_COMPLEMENT_SECONDS
            + EXTERNAL_GRACE_SECONDS,
            "PROOF_WALL_SECONDS": PROOF_WALL_SECONDS,
            "MAX_RESOLVED_OWNER_PROFILES": MAX_OWNER_PROFILES,
            "CP_SAT_SEARCH_WORKERS": 1,
        },
        "SOLVER_ACTUAL_WALL_TIME": solver_seconds,
        "PROOF_ACTUAL_WALL_SECONDS": prior_wall + monotonic() - started,
        "ATTEMPT_NUMBER": 1 if previous is None else _integer(previous["ATTEMPT_NUMBER"]) + 1,
        "SOLVER_MODEL_SOURCE_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "PREVIOUS_ATTEMPT": None
        if previous is None
        else {
            key: previous[key]
            for key in (
                "TASK_STATUS",
                "FAMILY_UPPER_BOUND",
                "SOLVER_STATUS",
                "SOLVER_CONFIGURED_WALL_LIMIT",
                "SOLVER_ACTUAL_WALL_TIME",
                "PROOF_ACTUAL_WALL_SECONDS",
                "SOLVER_MODEL_SOURCE_SHA256",
                "RETRY_ATTRIBUTION",
            )
        },
        "SOLVER_CERTIFIED_BOUND": max(outcome.bounds[p] for p in state.owners),
        "SOLVER_CERTIFIED_BOUND_SCOPE": "RESOLVED_OWNER_PAIR_ONLY",
        "SOLVER_PROFILES_SENT": list(dict.fromkeys(str(a["PROFILE_ID"]) for a in outcome.attempts)),
        "CURSOR_PROFILE_SOLVES": 0,
        "NO_CURSOR_WORK_GUARD": "PASS",
        "PLATEAU_RERUN_COUNT": 0,
        "RETAINED_PLATEAU_BOUND": PLATEAU_BOUND,
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        "TIGHTENING_PRIORITY_ORDER": [
            *ROUTES,
            "D_LOOSE_CYCLE_PASCH_SHARED_VERTEX",
            "E_MINIMUM_S4_AT_S3_MAXIMIZERS",
            "F_HIGHER_ORDER_MULTIPLICITY",
        ],
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "RUNTIME_TRANSITION_OCCURRED": "NO",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solver-request")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--refutation-wall-seconds", type=float, default=NATIVE_REFUTATION_SECONDS)
    arguments = parser.parse_args()
    if arguments.solver_request is not None:
        print(json.dumps(solver_child(_object(json.loads(arguments.solver_request)))))
        return
    if arguments.output is not None and arguments.output.resolve() != result_path():
        raise ValueError("output must be the exact R22 result path")
    previous = _object(json.loads(result_path().read_text())) if arguments.resume else None
    result = compute_result(
        previous=previous, refutation_wall_seconds=arguments.refutation_wall_seconds
    )
    if arguments.output is not None:
        if arguments.output.resolve() != result_path():
            raise ValueError("output must be the exact R22 result path")
        arguments.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "FAMILY_UPPER_BOUND",
                    "CURRENT_BOUND_OWNER_SET",
                    "REFINED_OWNER_BOUNDS",
                    "REMAINING_GAP",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
