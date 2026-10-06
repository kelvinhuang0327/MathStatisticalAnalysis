"""Chase every committed resolved K20 minimum-S2 owner above the cursor (R20).

The input ledger is read from immutable BASE_HEAD Git blobs, including the
R15, R17 and R19 refinements. Every dispatch checks the full current maximum.
The unresolved cursor is a ceiling only and is never passed to a solver.
An exact-support INFEASIBLE result refutes the owner's own triangle cap;
neither a feasible objective nor an unproved cap is accepted as a refinement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from time import monotonic
from typing import cast

from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import solver_runtime_preflight
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    _owner_support_witness as committed_support_witness,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_current_bound_owner_refinement_r15 import canonical_primitive_preflight
from .b649_k20_min_s2_higher_order_closure_r2 import K20_S1, K20_S2
from .b649_k20_min_s2_next_distinct_plateau_r10 import (
    _motif_triangle_bound as motif_triangle_bound,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_r16_freeze_and_owner_refinement_r17 import (
    complement_route_attempt,
    exact_support_triangle_refutation,
    witness_open_wedge_check,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_INCUMBENT,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
    s3_sum_from_wedges_and_triangles,
)

DegreeProfile = tuple[int, ...]
Triple = tuple[int, int, int]
Pair = tuple[int, int]

TASK_ID = "B649_K20_MIN_S2_RESOLVED_ABOVE_CURSOR_OWNER_CHASE_R20"
TASK_BRANCH = "codex/b649-k20-min-s2-resolved-above-cursor-owner-chase-r20"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "e93fe01c53d182d54bcdddddfeb16271c90a53ea"
BASE_TREE = "9219c9271ef92bf5546fc11314e629b7c74a7384"
RESULT_FILENAME = "b649-k20-min-s2-resolved-above-cursor-owner-chase-r20-result.json"
MODULE_NAME = "lottolab.research.b649_k20_min_s2_resolved_above_cursor_owner_chase_r20"
CURSOR_PROFILE: DegreeProfile = tuple(map(int, "66666665442111111111"))
CURSOR_BOUND = 313_658_120
START_FAMILY_BOUND = 313_668_648
MAX_OWNER_PROFILES = 16
PROOF_WALL_LIMIT_SECONDS = 3600.0
NATIVE_SUPPORT_SECONDS = 60.0
NATIVE_COMPLEMENT_SECONDS = 90.0
NATIVE_MOTIF_SECONDS = 60.0
NATIVE_WITNESS_SECONDS = 30.0
EXTERNAL_CALL_GRACE_SECONDS = 30.0
RESULT_DIRECTORY = "docs/research/matrix-native-results"
INPUT_FILENAMES: dict[str, str] = {
    "R11": "b649-k20-min-s2-budgeted-multi-plateau-descent-r11-result.json",
    "R12": "b649-k20-min-s2-continued-multi-plateau-descent-r12-result.json",
    "R13": "b649-k20-min-s2-class-dominance-or-descent-r13-result.json",
    "R14": "b649-k20-min-s2-successive-class-dominance-r14-result.json",
    "R15": "b649-k20-min-s2-current-bound-owner-refinement-r15-result.json",
    "R16": "b649-k20-min-s2-load-bearing-plateau-descent-r16-result.json",
    "R17": "b649-k20-min-s2-r16-freeze-and-owner-refinement-r17-result.json",
    "R18": "b649-k20-min-s2-cursor-plateau-closure-r18-result.json",
    "R19": "b649-k20-min-s2-dual-owner-refinement-r19-result.json",
}
SUCCESS_A = "SUCCESS_A_FAMILY_CLOSED"
SUCCESS_B = "SUCCESS_B_ALL_RESOLVED_AT_OR_BELOW_CURSOR"
SUCCESS_C = "SUCCESS_C_STRICT_FAMILY_DROP_EXACT_REMAINING_RESOLVED_OWNERS"


@dataclass(frozen=True, slots=True)
class Certificate:
    profile: DegreeProfile
    bound: int
    source_result: str
    source_row: str
    realizability: str
    s3: int | None
    s4: int | None
    triangle_cap: int | None
    relaxation: str
    witness_row: dict[str, object] | None = None
    witness_source: str | None = None


@dataclass(frozen=True, slots=True)
class ChaseOutcome:
    status: str
    bounds: dict[DegreeProfile, int]
    attempts: tuple[dict[str, object], ...]
    steps: tuple[dict[str, object], ...]
    owners: tuple[DegreeProfile, ...]
    family_bound: int


def profile_id(profile: DegreeProfile) -> str:
    return "".join(map(str, profile))


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def result_path() -> Path:
    return repo_root() / RESULT_DIRECTORY / RESULT_FILENAME


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AssertionError("expected an object in the committed certificate")
    return cast(dict[str, object], value)


def _rows(value: object) -> list[object]:
    if not isinstance(value, list):
        raise AssertionError("expected a row list in the committed certificate")
    return cast(list[object], value)


def _int(value: object) -> int:
    if type(value) is not int:
        raise AssertionError("expected an exact integer certificate")
    return value


def _optional_int(value: object) -> int | None:
    return value if type(value) is int else None


def decode_profile(value: object) -> DegreeProfile:
    if isinstance(value, str) and value.isdecimal():
        profile = tuple(map(int, value))
    elif isinstance(value, list):
        profile = tuple(_int(d) for d in cast(list[object], value))
    else:
        raise AssertionError("malformed degree profile")
    if (
        len(profile) != 20
        or sum(profile) != 66
        or tuple(sorted(profile, reverse=True)) != profile
        or any(not 0 <= degree <= 6 for degree in profile)
    ):
        raise AssertionError("invalid minimum-S2 degree profile")
    return profile


def committed_results() -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    """Use Git blobs at the exact base, never working-file result authority."""

    results: dict[str, dict[str, object]] = {}
    hashes: dict[str, str] = {}
    for label, filename in INPUT_FILENAMES.items():
        relative = f"{RESULT_DIRECTORY}/{filename}"
        blob = subprocess.check_output(["git", "show", f"{BASE_HEAD}:{relative}"], cwd=repo_root())
        results[label] = _object(json.loads(blob))
        hashes[relative] = hashlib.sha256(blob).hexdigest()
    return results, hashes


def bound_from_cap(profile: DegreeProfile, cap: int, s4: int) -> tuple[int, int]:
    if cap < K20_TRIPLE_SUPPORT_COUNT or s4 < 0:
        raise AssertionError("invalid triangle cap or S4 floor")
    s3 = s3_sum_from_wedges_and_triangles(
        overlap_wedge_count(profile), cap - K20_TRIPLE_SUPPORT_COUNT
    )
    return s3, K20_S1 - K20_S2 + s3 - (4 * s4) // 7


def reconstruct_ledger(
    results: Mapping[str, dict[str, object]],
) -> dict[DegreeProfile, Certificate]:
    """Rebuild all 282 records, retaining the strongest committed certificate."""

    ledger: dict[DegreeProfile, Certificate] = {}
    for label, count in (("R11", 24), ("R12", 48)):
        rows = _rows(results[label]["PROFILE_BOUNDS"])
        if len(rows) != count:
            raise AssertionError(f"{label} profile count changed")
        for index, raw in enumerate(rows):
            row = _object(raw)
            profile = decode_profile(row["PROFILE"])
            if profile in ledger:
                raise AssertionError("duplicate resolved profile")
            source_row = f"PROFILE_BOUNDS[{index}]"
            ledger[profile] = Certificate(
                profile,
                _int(row["FAMILY_UPPER_BOUND"]),
                INPUT_FILENAMES[label],
                source_row,
                str(row["REALIZABILITY"]),
                _optional_int(row.get("S3_UPPER_BOUND")),
                _optional_int(row.get("S4_LOWER_BOUND")),
                _optional_int(row.get("GRAPH_TRIANGLE_UPPER_BOUND")),
                "R10_DEGREE_CLASS_OPEN_WEDGE_RELAXATION",
                row,
                f"{label}.{source_row}",
            )

    def add_classes(label: str, expected_total: int) -> None:
        result = results[label]
        raw_certificates = (
            [result["CLASS_DOMINANCE_CERTIFICATE"]]
            if label == "R13"
            else _rows(result["CLASS_CERTIFICATES"])
        )
        for index, raw in enumerate(raw_certificates):
            row = _object(raw)
            source_row = (
                "CLASS_DOMINANCE_CERTIFICATE" if label == "R13" else f"CLASS_CERTIFICATES[{index}]"
            )
            for raw_profile in _rows(row["PROFILE_IDENTITIES"]):
                profile = decode_profile(raw_profile)
                if profile in ledger:
                    raise AssertionError("class certificate repeats a resolved profile")
                ledger[profile] = Certificate(
                    profile,
                    _int(row["CLASS_FAMILY_UPPER_BOUND"]),
                    INPUT_FILENAMES[label],
                    source_row,
                    "CLASS_ENVELOPE_ONLY",
                    None,
                    None,
                    None,
                    "CERTIFIED_FINITE_CLASS_ENVELOPE",
                )
        if len(ledger) != expected_total:
            raise AssertionError(f"{label} complete ledger count changed")

    def refine(
        profile: DegreeProfile,
        label: str,
        source_row: str,
        bound: int,
        cap: int,
        s3: int,
        s4: int,
        relaxation: str,
    ) -> None:
        prior = ledger[profile]
        if bound >= prior.bound or bound_from_cap(profile, cap, s4) != (s3, bound):
            raise AssertionError("committed refinement does not reproduce a strict bound")
        ledger[profile] = replace(
            prior,
            bound=bound,
            triangle_cap=cap,
            s3=s3,
            s4=s4,
            source_result=INPUT_FILENAMES[label],
            source_row=source_row,
            relaxation=relaxation,
        )

    add_classes("R13", 76)
    add_classes("R14", 179)
    for index, raw in enumerate(_rows(results["R15"]["OWNER_PROFILE_BOUNDS"])):
        row = _object(raw)
        refine(
            decode_profile(row["PROFILE"]),
            "R15",
            f"OWNER_PROFILE_BOUNDS[{index}]",
            _int(row["FAMILY_UPPER_BOUND"]),
            _int(row["REFINED_GRAPH_TRIANGLE_UPPER_BOUND"]),
            _int(row["REFINED_S3_UPPER_BOUND"]),
            _int(row["S4_LOWER_BOUND_AT_S3_MAXIMIZERS"]),
            "R15_COMPLEMENT_TRIANGLE_CERTIFIED_LOWER_BOUND",
        )
    add_classes("R16", 227)
    r17 = results["R17"]
    refine(
        decode_profile(r17["CURRENT_OWNER_PROFILE"]),
        "R17",
        "OWNER_REFINED_BOUND",
        _int(r17["OWNER_REFINED_BOUND"]),
        _int(r17["REFINED_GRAPH_TRIANGLE_UPPER_BOUND"]),
        _int(r17["REFINED_S3_UPPER_BOUND"]),
        _int(r17["S4_LOWER_BOUND_AT_S3_MAXIMIZERS"]),
        "R17_EXACT_SUPPORT_OPEN_WEDGE_REFUTATION",
    )
    add_classes("R18", 282)
    r19 = results["R19"]
    for identity, raw in _object(r19["REFINED_OWNER_ROWS"]).items():
        row = _object(raw)
        profile = decode_profile(identity)
        s4 = ledger[profile].s4
        if s4 is None:
            raise AssertionError("refined owner lacks S4 floor")
        refine(
            profile,
            "R19",
            f"REFINED_OWNER_ROWS.{identity}",
            _int(row["FAMILY_UPPER_BOUND"]),
            _int(row["GRAPH_TRIANGLE_UPPER_BOUND"]),
            _int(row["S3_UPPER_BOUND"]),
            s4,
            "R19_EXACT_SUPPORT_OPEN_WEDGE_REFUTATION",
        )
    if r19["FAMILY_UPPER_BOUND"] != START_FAMILY_BOUND:
        raise AssertionError("committed family maximum changed")
    if r19["NEXT_CURSOR_PROFILE"] != profile_id(CURSOR_PROFILE):
        raise AssertionError("committed cursor profile changed")
    if r19["NEXT_CURSOR_BOUND"] != CURSOR_BOUND or CURSOR_PROFILE in ledger:
        raise AssertionError("cursor must remain unresolved")
    above = resolved_above_cursor(ledger)
    if len(above) != 14 or len(above) > MAX_OWNER_PROFILES:
        raise AssertionError("reconstructed above-cursor count differs from the packet")
    bounds = {p: cert.bound for p, cert in ledger.items()}
    family, owners = family_state(bounds)
    expected = (decode_profile("66665555555411100000"), decode_profile("66655555555521000000"))
    if family != START_FAMILY_BOUND or owners != expected:
        raise AssertionError("family maximum or tied owner set changed")
    if tuple(ledger[p].source_row for p in owners) != ("PROFILE_BOUNDS[8]", "PROFILE_BOUNDS[10]"):
        raise AssertionError("current owners are not R12 rows 8 and 10")
    if any(ledger[p].source_result != INPUT_FILENAMES["R12"] for p in owners):
        raise AssertionError("current owner source result changed")
    original_owners = {decode_profile(p) for p in _object(r19["REFINED_OWNER_ROWS"])}
    outside = {
        decode_profile(_object(row)["PROFILE"])
        for row in _rows(r19["RESOLVED_PROFILES_ABOVE_CURSOR_OUTSIDE_OWNER_SET"])
    }
    if set(above) != outside | original_owners or outside & original_owners:
        raise AssertionError("an R19 resolved-above-cursor profile was omitted")
    for cert in above.values():
        if cert.triangle_cap is None or cert.s4 is None:
            raise AssertionError("above-cursor certificate lacks cap or S4")
        if bound_from_cap(cert.profile, cert.triangle_cap, cert.s4) != (cert.s3, cert.bound):
            raise AssertionError("current S3/S4 certificate does not reproduce its bound")
    return ledger


def resolved_above_cursor(
    ledger: Mapping[DegreeProfile, Certificate],
) -> dict[DegreeProfile, Certificate]:
    return dict(
        sorted(
            ((p, cert) for p, cert in ledger.items() if cert.bound > CURSOR_BOUND),
            key=lambda item: (item[1].bound, item[0]),
            reverse=True,
        )
    )


def assert_no_omitted_owner(
    ledger: Mapping[DegreeProfile, Certificate],
    requested: Collection[DegreeProfile],
) -> None:
    if len(requested) != len(set(requested)) or set(requested) != set(
        resolved_above_cursor(ledger)
    ):
        raise AssertionError("resolved-above-cursor owner set is incomplete or duplicated")


def family_state(bounds: Mapping[DegreeProfile, int]) -> tuple[int, tuple[DegreeProfile, ...]]:
    if CURSOR_PROFILE in bounds:
        raise AssertionError("unresolved cursor occurs in resolved ledger")
    family = max(CURSOR_BOUND, *bounds.values())
    owners = tuple(sorted((p for p, bound in bounds.items() if bound == family), reverse=True))
    if family == CURSOR_BOUND:
        owners = (CURSOR_PROFILE, *owners)
    return family, owners


def assert_solver_scope(
    requested: DegreeProfile,
    ledger: Mapping[DegreeProfile, Certificate],
    bounds: Mapping[DegreeProfile, int],
) -> None:
    if requested == CURSOR_PROFILE or requested not in ledger:
        raise AssertionError("unresolved profiles must never be sent to a solver")
    if set(bounds) != set(ledger) or any(bounds[p] > ledger[p].bound for p in ledger):
        raise AssertionError("full resolved ledger was omitted or weakened")
    family, owners = family_state(bounds)
    if family <= CURSOR_BOUND or requested not in owners:
        raise AssertionError("only a current family-max owner may be sent to a solver")


def ledger_row(cert: Certificate) -> dict[str, object]:
    return {
        "PROFILE_ID": profile_id(cert.profile),
        "DEGREE_PROFILE": list(cert.profile),
        "SOURCE_RESULT": cert.source_result,
        "SOURCE_ROW": cert.source_row,
        "CURRENT_BOUND": cert.bound,
        "REALIZABILITY_STATUS": cert.realizability,
        "S3": cert.s3,
        "S4_FLOOR": cert.s4,
        "BOUND_LIMITING_RELAXATION": cert.relaxation,
        "GRAPH_TRIANGLE_CAP": cert.triangle_cap,
        "WEDGE_COUNT": overlap_wedge_count(cert.profile),
        "WITNESS_SOURCE": cert.witness_source,
    }


def support_witness(cert: Certificate) -> tuple[tuple[Triple, ...], tuple[Pair, ...]]:
    row = cert.witness_row
    if row is None:
        raise AssertionError("owner lacks a committed support witness")
    return committed_support_witness(row, cert.profile)


def run_owner_chase(
    ledger: Mapping[DegreeProfile, Certificate],
    refine: Callable[[Certificate, Mapping[DegreeProfile, int]], dict[str, object]],
) -> ChaseOutcome:
    """Switch immediately after each refinement; never dispatch a lower owner."""

    above = resolved_above_cursor(ledger)
    assert_no_omitted_owner(ledger, tuple(above))
    if len(above) > MAX_OWNER_PROFILES:
        raise AssertionError("owner profile budget exceeded")
    bounds = {p: cert.bound for p, cert in ledger.items()}
    attempts: list[dict[str, object]] = []
    steps: list[dict[str, object]] = []
    tried: set[tuple[DegreeProfile, int]] = set()
    while True:
        family, owners = family_state(bounds)
        if family <= K20_INCUMBENT:
            status = SUCCESS_A
            break
        if all(bounds[p] <= CURSOR_BOUND for p in above):
            status = SUCCESS_B
            break
        pending = tuple(p for p in owners if (p, bounds[p]) not in tried)
        if not pending:
            status = SUCCESS_C if family < START_FAMILY_BOUND else "NO_CERTIFIED_FAMILY_DROP"
            break
        owner = pending[0]
        assert_solver_scope(owner, ledger, bounds)
        cert = above[owner]
        attempt = refine(cert, dict(bounds))
        attempts.append(attempt)
        tried.add((owner, bounds[owner]))
        candidate = attempt.get("CERTIFIED_OWNER_BOUND")
        if candidate is None:
            continue
        refined_bound = _int(candidate)
        if refined_bound >= bounds[owner]:
            raise AssertionError("owner refinement is not strict")
        before_bound, before_owners = family, owners
        start_bound = bounds[owner]
        bounds[owner] = refined_bound
        after, after_owners = family_state(bounds)
        steps.append(
            {
                "STEP": len(steps) + 1,
                "PROFILE_ID": profile_id(owner),
                "START_OWNER_BOUND": start_bound,
                "REFINED_OWNER_BOUND": refined_bound,
                "FAMILY_BOUND_BEFORE": before_bound,
                "FAMILY_BOUND_AFTER": after,
                "OWNER_SET_BEFORE": list(map(profile_id, before_owners)),
                "OWNER_SET_AFTER": list(map(profile_id, after_owners)),
                "CERTIFICATE": attempt,
            }
        )
    return ChaseOutcome(status, bounds, tuple(attempts), tuple(steps), owners, family)


def _solver_child(request: Mapping[str, object]) -> dict[str, object]:
    results, _ = committed_results()
    ledger = reconstruct_ledger(results)
    owner = decode_profile(request["PROFILE_ID"])
    bounds = {p: cert.bound for p, cert in ledger.items()}
    for identity, raw in _object(request["EFFECTIVE_OWNER_BOUNDS"]).items():
        profile = decode_profile(identity)
        if profile not in ledger:
            raise AssertionError("request includes an unresolved profile")
        bounds[profile] = _int(raw)
    assert_solver_scope(owner, ledger, bounds)
    cert = ledger[owner]
    route = str(request["ROUTE"])
    started = monotonic()
    if route == "WITNESS":
        triples, doubles = support_witness(cert)
        value = witness_open_wedge_check(
            owner,
            triples,
            doubles,
            wall_limit_seconds=NATIVE_WITNESS_SECONDS,
        )
        value["WITNESS_SOURCE"] = cert.witness_source
    elif route == "A_EXACT_SUPPORT_OPEN_WEDGE_REFUTATION":
        value = exact_support_triangle_refutation(
            owner,
            refuted_triangle_count=_int(request["TRIANGLE_CAP"]),
            wall_limit_seconds=NATIVE_SUPPORT_SECONDS,
        )
        value["ROUTE"] = route
    elif route == "B_COMPLEMENT_TRIANGLE_LOWER_BOUND":
        triples, doubles = support_witness(cert)
        value = complement_route_attempt(owner, triples, doubles)
        value["ROUTE"] = route
        # The search status FEASIBLE alone is never accepted as proof in R20.
        if value.get("STATUS") != "OPTIMAL":
            value["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] = None
            value["CERTIFICATE_ACCEPTED"] = False
    elif route == "C_EXACT_NONCORE_TRIANGLE_CEILING":
        triples, doubles = support_witness(cert)
        value = motif_triangle_bound(
            owner, triples, doubles, wall_limit_seconds=NATIVE_MOTIF_SECONDS
        )
        value["ROUTE"] = route
        value["STATUS"] = value.get("SOLVER_STATUS")
        value["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] = (
            value.get("SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND")
            if value.get("STATUS") == "OPTIMAL"
            else None
        )
    else:
        raise AssertionError("unknown solver route")
    value["ACTUAL_CALL_WALL_SECONDS"] = monotonic() - started
    value["PROFILE_ID"] = profile_id(owner)
    return value


def bounded_solver_call(
    cert: Certificate,
    bounds: Mapping[DegreeProfile, int],
    route: str,
    *,
    deadline: float,
) -> dict[str, object]:
    remaining = deadline - monotonic()
    native = {
        "WITNESS": 2 * NATIVE_WITNESS_SECONDS,
        "A_EXACT_SUPPORT_OPEN_WEDGE_REFUTATION": NATIVE_SUPPORT_SECONDS,
        "B_COMPLEMENT_TRIANGLE_LOWER_BOUND": NATIVE_COMPLEMENT_SECONDS,
        "C_EXACT_NONCORE_TRIANGLE_CEILING": NATIVE_MOTIF_SECONDS,
    }[route]
    if remaining < native + EXTERNAL_CALL_GRACE_SECONDS:
        return {
            "ROUTE": route,
            "STATUS": "NOT_RUN_PROOF_WALL_BUDGET",
            "PROFILE_ID": profile_id(cert.profile),
        }
    request: dict[str, object] = {
        "ROUTE": route,
        "PROFILE_ID": profile_id(cert.profile),
        "TRIANGLE_CAP": cert.triangle_cap,
        "EFFECTIVE_OWNER_BOUNDS": {profile_id(p): bound for p, bound in bounds.items()},
    }
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONPATH": str(repo_root() / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    started = monotonic()
    try:
        process = subprocess.run(
            [sys.executable, "-m", MODULE_NAME, "--solver-request", json.dumps(request)],
            cwd=repo_root(),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=native + EXTERNAL_CALL_GRACE_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "ROUTE": route,
            "STATUS": "EXTERNAL_HARD_TIMEOUT",
            "PROFILE_ID": profile_id(cert.profile),
            "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": None,
            "ACTUAL_CALL_WALL_SECONDS": monotonic() - started,
            "TERMINATION": "SUBPROCESS_TIMEOUT_TASK_OWNED_CHILD_KILLED_AND_REAPED",
        }
    if process.returncode != 0:
        raise RuntimeError(f"solver child failed: {process.stderr[-4000:]}")
    result = _object(json.loads(process.stdout))
    result["EXTERNAL_HARD_TIMEOUT_SECONDS"] = native + EXTERNAL_CALL_GRACE_SECONDS
    result["SUBPROCESS_WALL_SECONDS"] = monotonic() - started
    return result


def compute_result() -> dict[str, object]:
    started = monotonic()
    primitives = canonical_primitive_preflight()
    runtime = solver_runtime_preflight()
    results, hashes = committed_results()
    ledger = reconstruct_ledger(results)
    above = resolved_above_cursor(ledger)
    deadline = started + PROOF_WALL_LIMIT_SECONDS

    def refine(cert: Certificate, bounds: Mapping[DegreeProfile, int]) -> dict[str, object]:
        assert_solver_scope(cert.profile, ledger, bounds)
        witness = bounded_solver_call(cert, bounds, "WITNESS", deadline=deadline)
        if witness.get("STATUS") != "PASS":
            raise AssertionError("exact support model lacks a passing witness check")
        routes: list[dict[str, object]] = []
        for route in (
            "A_EXACT_SUPPORT_OPEN_WEDGE_REFUTATION",
            "B_COMPLEMENT_TRIANGLE_LOWER_BOUND",
            "C_EXACT_NONCORE_TRIANGLE_CEILING",
        ):
            attempt = bounded_solver_call(cert, bounds, route, deadline=deadline)
            routes.append(attempt)
            cap = attempt.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND")
            if cap is not None and cert.triangle_cap is not None and _int(cap) < cert.triangle_cap:
                if cert.s4 is None:
                    raise AssertionError("owner lacks a certified S4 floor")
                s3, bound = bound_from_cap(cert.profile, _int(cap), cert.s4)
                value: dict[str, object] = {
                    "PROFILE_ID": profile_id(cert.profile),
                    "START_BOUND": bounds[cert.profile],
                    "START_TRIANGLE_CAP": cert.triangle_cap,
                    "REFINED_TRIANGLE_CAP": cap,
                    "REFINED_S3": s3,
                    "S4_FLOOR": cert.s4,
                    "CERTIFIED_OWNER_BOUND": bound,
                    "BOUND_LIMITING_RELAXATION": route,
                    "ROUTES": routes,
                    "WITNESS_CHECK": witness,
                    "LATER_ROUTES": "NOT_REQUIRED_CERTIFIED_OWNER_DROP",
                }
                print(
                    json.dumps(
                        {
                            "OWNER_REFINED": profile_id(cert.profile),
                            "BOUND": bound,
                            "STATUS": attempt["STATUS"],
                        }
                    ),
                    flush=True,
                )
                return value
        return {
            "PROFILE_ID": profile_id(cert.profile),
            "CERTIFIED_OWNER_BOUND": None,
            "ROUTES": routes,
            "WITNESS_CHECK": witness,
            "LATER_ROUTES": "NOT_RUN_REQUIRES_ADDITIONAL_STRUCTURAL_CERTIFICATE",
        }

    outcome = run_owner_chase(ledger, refine)
    remaining = sorted(
        (p for p in ledger if outcome.bounds[p] > CURSOR_BOUND),
        key=lambda p: (outcome.bounds[p], p),
        reverse=True,
    )
    refined_ids = {str(step["PROFILE_ID"]) for step in outcome.steps}
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_STATUS": outcome.status,
        "CURSOR_BOUND": CURSOR_BOUND,
        "CURSOR_PROFILE": profile_id(CURSOR_PROFILE),
        "COMMITTED_INPUT_SHA256": hashes,
        "INPUT_AUTHORITY": "IMMUTABLE_BASE_HEAD_GIT_BLOBS_ONLY",
        "RESOLVED_LEDGER_COUNT": len(ledger),
        "RESOLVED_ABOVE_CURSOR_COUNT": len(above),
        "RESOLVED_ABOVE_CURSOR_PROFILES": list(map(profile_id, above)),
        "RESOLVED_ABOVE_CURSOR_SET": [ledger_row(cert) for cert in above.values()],
        "NO_OMITTED_OWNER_ASSERTION": "PASS",
        "R12_ROWS_8_AND_10_OWNER_ASSERTION": "PASS",
        "REFINEMENT_STEPS": list(outcome.steps),
        "OWNER_ATTEMPTS": list(outcome.attempts),
        "OWNER_TRANSITION_COUNT": sum(
            step["OWNER_SET_BEFORE"] != step["OWNER_SET_AFTER"] for step in outcome.steps
        ),
        "OWNERS_REFINED_COUNT": len(refined_ids),
        "OWNERS_PROCESSED_COUNT": len({str(row["PROFILE_ID"]) for row in outcome.attempts}),
        "START_FAMILY_BOUND": START_FAMILY_BOUND,
        "END_FAMILY_BOUND": outcome.family_bound,
        "CURRENT_BOUND_OWNER_SET": list(map(profile_id, outcome.owners)),
        "REMAINING_RESOLVED_ABOVE_CURSOR_COUNT": len(remaining),
        "REMAINING_RESOLVED_ABOVE_CURSOR_PROFILES": list(map(profile_id, remaining)),
        "FINAL_RESOLVED_LEDGER": [
            {"PROFILE_ID": profile_id(p), "CURRENT_BOUND": bound}
            for p, bound in sorted(
                outcome.bounds.items(), key=lambda item: (item[1], item[0]), reverse=True
            )
        ],
        "FAMILY_UPPER_BOUND": outcome.family_bound,
        "INCUMBENT": K20_INCUMBENT,
        "REMAINING_GAP": max(0, outcome.family_bound - K20_INCUMBENT),
        "FAMILY_STATUS": "CLOSED" if outcome.status == SUCCESS_A else "OPEN_STRICTLY_TIGHTENED",
        "CANONICAL_PRIMITIVES": primitives,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_STATUS": "INFEASIBLE_CERTIFIED"
        if len(refined_ids) == len(above)
        else "PARTIAL_CERTIFICATES",
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "EXACT_SUPPORT_NATIVE_SECONDS": NATIVE_SUPPORT_SECONDS,
            "COMPLEMENT_NATIVE_SECONDS": NATIVE_COMPLEMENT_SECONDS,
            "EXACT_NONCORE_NATIVE_SECONDS": NATIVE_MOTIF_SECONDS,
            "WITNESS_CHECK_NATIVE_SECONDS_PER_SOLVE": NATIVE_WITNESS_SECONDS,
            "EXTERNAL_CALL_GRACE_SECONDS": EXTERNAL_CALL_GRACE_SECONDS,
            "PROOF_WALL_SECONDS": PROOF_WALL_LIMIT_SECONDS,
            "CP_SAT_SEARCH_WORKERS": 1,
            "MAX_OWNER_PROFILES": MAX_OWNER_PROFILES,
        },
        "SOLVER_ACTUAL_WALL_TIME": monotonic() - started,
        "SOLVER_CERTIFIED_BOUND": outcome.family_bound,
        "SOLVER_PROFILES_SENT": [row["PROFILE_ID"] for row in outcome.attempts],
        "CURSOR_PROFILE_SOLVES": 0,
        "NO_UNRESOLVED_CURSOR_WORK_GUARD": "PASS",
        "CURSOR_GENUINELY_LOAD_BEARING": outcome.family_bound == CURSOR_BOUND,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solver-request")
    arguments = parser.parse_args()
    if arguments.solver_request is not None:
        print(json.dumps(_solver_child(_object(json.loads(arguments.solver_request)))))
        return
    result = compute_result()
    result_path().write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "TASK_STATUS",
                    "OWNERS_REFINED_COUNT",
                    "END_FAMILY_BOUND",
                    "CURRENT_BOUND_OWNER_SET",
                    "REMAINING_RESOLVED_ABOVE_CURSOR_COUNT",
                    "SOLVER_ACTUAL_WALL_TIME",
                )
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
