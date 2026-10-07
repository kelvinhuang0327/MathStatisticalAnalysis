"""Certify R26 owner groups on their exact union of support models.

The 408-row R25 ledger is frozen input. No plateau enumeration, cheap owner
chase, ranked frontier search or unresolved cursor model is called. A signature
shares the structural moments and certificate, not an assumed isomorphism of
degree histograms: an allowed-assignment table explicitly covers every member.
After each proof the entire ledger is recomputed, including newly exposed owners.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from importlib import import_module
from itertools import combinations
from pathlib import Path
from time import monotonic, time
from typing import Any, cast

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
    INPUT_FILENAMES as R20_INPUTS,
)
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    bound_from_cap,
    decode_profile,
    profile_id,
    reconstruct_ledger,
    support_witness,
)

DegreeProfile = tuple[int, ...]
Pair = tuple[int, int]
Triple = tuple[int, int, int]
TASK_ID = "B649_K20_MIN_S2_SIX_OWNER_BATCH_REFINEMENT_R26"
TASK_BRANCH = "codex/b649-k20-min-s2-six-owner-batch-refinement-r26"
BASE_HEAD = "a990c5f0bc20c3f6dd56e92c6aedc75ca9dcac50"
BASE_TREE = "0efc56f9dc73963309efa3d89fa3f4d80f620d83"
START_FAMILY_BOUND = 313_650_504
INCUMBENT = 313_239_661
NEXT_CURSOR_BOUND = 313_637_848
NEXT_CURSOR_PROFILE = decode_profile("66666665422221111111")
OWNER_IDS = (
    "66666665444322000000",
    "66666664444431000000",
    "66666655544411100000",
    "66666655544331000000",
    "66666555555311100000",
    "66666555554421000000",
)
OWNERS = tuple(map(decode_profile, OWNER_IDS))
RESULT_DIRECTORY = "docs/research/matrix-native-results"
RESULT_FILENAME = "b649-k20-min-s2-six-owner-batch-refinement-r26-result.json"
R25_FILENAME = "b649-k20-min-s2-cursor-dynamic-owner-chase-r25-result.json"
R25_SHA256 = "5ac39ba68c10ad512eded98536f9859e22f5841769baa18c3ca7a91ace63de6c"
MODULE_NAME = "lottolab.research.b649_k20_min_s2_six_owner_batch_refinement_r26"
PROOF_WALL_SECONDS = 3_600.0
NATIVE_GROUP_SECONDS = 180.0
NATIVE_INDIVIDUAL_SECONDS = 120.0
EXTERNAL_GRACE_SECONDS = 15.0
EXTERNAL_KILL_SECONDS = 5
SUCCESS_A = "SUCCESS_A_FAMILY_CLOSED"
SUCCESS_B = "SUCCESS_B_ALL_RESOLVED_AT_OR_BELOW_CURSOR"
SUCCESS_C = "SUCCESS_C_STRICT_FAMILY_TIGHTENING_EXACT_REMAINING_OWNERS"
NO_DROP = "NO_CERTIFIED_FAMILY_TIGHTENING"


@dataclass(frozen=True, slots=True)
class State:
    bounds: Mapping[DegreeProfile, int]
    certificates: Mapping[DegreeProfile, Certificate]
    input_hashes: Mapping[str, str]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def object_row(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise AssertionError("expected certificate object")
    return cast(dict[str, object], raw)


def rows(raw: object) -> list[object]:
    if not isinstance(raw, list):
        raise AssertionError("expected certificate list")
    return cast(list[object], raw)


def integer(raw: object) -> int:
    if type(raw) is not int:
        raise AssertionError("expected exact integer")
    return raw


def committed_inputs() -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    filenames = {**R20_INPUTS}
    filenames.update(
        {
            "R20": "b649-k20-min-s2-resolved-above-cursor-owner-chase-r20-result.json",
            "R21": "b649-k20-min-s2-unique-cursor-plateau-r21-result.json",
            "R22": "b649-k20-min-s2-resolved-owner-pair-refinement-r22-result.json",
            "R23": "b649-k20-min-s2-unique-cursor-class-closure-r23-result.json",
            "R24": "b649-k20-min-s2-owner-ledger-reconcile-and-refine-r24-result.json",
            "R25": R25_FILENAME,
        }
    )
    inputs: dict[str, dict[str, object]] = {}
    hashes: dict[str, str] = {}
    for label, name in filenames.items():
        relative = f"{RESULT_DIRECTORY}/{name}"
        blob = subprocess.check_output(["git", "show", f"{BASE_HEAD}:{relative}"], cwd=repo_root())
        digest = hashlib.sha256(blob).hexdigest()
        if label == "R25" and digest != R25_SHA256:
            raise AssertionError("pinned R25 identity changed")
        inputs[label] = object_row(json.loads(blob))
        hashes[name] = digest
    return inputs, hashes


def family_state(bounds: Mapping[DegreeProfile, int]) -> tuple[int, tuple[DegreeProfile, ...]]:
    if not bounds or NEXT_CURSOR_PROFILE in bounds:
        raise AssertionError("cursor must remain unresolved")
    maximum = max(NEXT_CURSOR_BOUND, *bounds.values())
    owners = tuple(sorted((p for p, b in bounds.items() if b == maximum), reverse=True))
    if maximum == NEXT_CURSOR_BOUND:
        owners = (NEXT_CURSOR_PROFILE, *owners)
    return maximum, owners


def reconstruct_state(inputs: Mapping[str, dict[str, object]], hashes: Mapping[str, str]) -> State:
    r25 = inputs["R25"]
    if (
        r25.get("FAMILY_UPPER_BOUND") != START_FAMILY_BOUND
        or r25.get("CURRENT_BOUND_OWNER_SET") != list(OWNER_IDS)
        or r25.get("NEXT_CURSOR_BOUND") != NEXT_CURSOR_BOUND
        or r25.get("NEXT_CURSOR_PROFILE") != profile_id(NEXT_CURSOR_PROFILE)
        or r25.get("NO_CURSOR_WORK_GUARD") != "PASS"
        or r25.get("PLATEAU_RERUN_COUNT") != 0
    ):
        raise AssertionError("R25 authority or forbidden-work guard changed")
    bounds: dict[DegreeProfile, int] = {}
    for raw in rows(r25["FINAL_RESOLVED_LEDGER"]):
        row = object_row(raw)
        p = decode_profile(row["PROFILE_ID"])
        if p in bounds:
            raise AssertionError("duplicate resolved profile")
        bounds[p] = integer(row["CURRENT_BOUND"])
    if len(bounds) != 408 or family_state(bounds) != (START_FAMILY_BOUND, OWNERS):
        raise AssertionError("complete 408-row ledger or exact six-owner set changed")

    catalog = reconstruct_ledger(inputs)
    for label in ("R21", "R23"):
        for index, raw in enumerate(rows(inputs[label]["CLASS_CERTIFICATES"])):
            row = object_row(raw)
            for identity in rows(row["PROFILE_IDENTITIES"]):
                p = decode_profile(identity)
                if p in catalog:
                    raise AssertionError("committed classes overlap")
                catalog[p] = Certificate(
                    p,
                    integer(row["CLASS_FAMILY_UPPER_BOUND"]),
                    "b649-k20-min-s2-"
                    + (
                        "unique-cursor-plateau-r21-result.json"
                        if label == "R21"
                        else "unique-cursor-class-closure-r23-result.json"
                    ),
                    f"CLASS_CERTIFICATES[{index}]",
                    "CLASS_ENVELOPE_ONLY",
                    integer(row["S3_UPPER_BOUND"]),
                    integer(row["S4_LOWER_BOUND"]),
                    integer(row["GRAPH_TRIANGLE_UPPER_BOUND"]),
                    str(row["CLASS_CERTIFICATE_KIND"]),
                )
    if catalog.keys() != bounds.keys():
        raise AssertionError("certificate catalog omits a resolved ledger row")
    # Supply the shared structural values in early class records, without solving.
    for p, cert in tuple(catalog.items()):
        if cert.triangle_cap is not None or cert.realizability != "CLASS_ENVELOPE_ONLY":
            continue
        label = next(k for k, name in R20_INPUTS.items() if name == cert.source_result)
        result = inputs[label]
        row = (
            object_row(result["CLASS_DOMINANCE_CERTIFICATE"])
            if label == "R13"
            else object_row(rows(result["CLASS_CERTIFICATES"])[int(cert.source_row[19:-1])])
        )
        cap = integer(row["GRAPH_TRIANGLE_UPPER_BOUND"])
        floor = integer(row.get("S4_LOWER_BOUND", 112))
        s3, reproduced = bound_from_cap(p, cap, floor)
        if reproduced != cert.bound:
            raise AssertionError("class cap does not reproduce its committed bound")
        catalog[p] = replace(cert, triangle_cap=cap, s3=s3, s4=floor)
    for label in ("R20", "R22", "R24", "R25"):
        for index, raw in enumerate(rows(inputs[label]["OWNER_ATTEMPTS"])):
            row = object_row(raw)
            if row.get("CERTIFIED_OWNER_BOUND") is None:
                continue
            p = decode_profile(row["PROFILE_ID"])
            cap, s4 = integer(row["REFINED_TRIANGLE_CAP"]), integer(row["S4_FLOOR"])
            s3, bound = bound_from_cap(p, cap, s4)
            proof_rows = [object_row(r) for r in rows(row["ROUTES"])]
            if (s3, bound) != (row["REFINED_S3"], row["CERTIFIED_OWNER_BOUND"]) or not any(
                r.get("STATUS") == "INFEASIBLE"
                and r.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND") == cap
                for r in proof_rows
            ):
                raise AssertionError("committed owner proof does not reproduce its bound")
            catalog[p] = replace(
                catalog[p],
                bound=bound,
                triangle_cap=cap,
                s3=s3,
                s4=s4,
                source_result={
                    "R20": "b649-k20-min-s2-resolved-above-cursor-owner-chase-r20-result.json",
                    "R22": "b649-k20-min-s2-resolved-owner-pair-refinement-r22-result.json",
                    "R24": "b649-k20-min-s2-owner-ledger-reconcile-and-refine-r24-result.json",
                    "R25": R25_FILENAME,
                }[label],
                source_row=f"OWNER_ATTEMPTS[{index}]",
                relaxation=str(row["BOUND_LIMITING_RELAXATION"]),
            )
    for index, raw in enumerate(rows(r25["CHEAP_CERTIFICATES"])):
        row = object_row(raw)
        p = decode_profile(row["PROFILE_ID"])
        bound = integer(row["CERTIFIED_OWNER_BOUND"])
        if bound >= catalog[p].bound:
            continue
        envelope = object_row(row["PROFILE_ENVELOPE"])
        catalog[p] = replace(
            catalog[p],
            bound=bound,
            triangle_cap=integer(envelope["GRAPH_TRIANGLE_UPPER_BOUND"]),
            s3=integer(envelope["S3_UPPER_BOUND"]),
            s4=integer(envelope["S4_LOWER_BOUND"]),
            source_result=R25_FILENAME,
            source_row=f"CHEAP_CERTIFICATES[{index}]",
            relaxation="PINNED_R25_R13_OPTIMUM_NO_RERUN",
        )
    for p, cert in catalog.items():
        if cert.bound != bounds[p]:
            raise AssertionError(f"certificate/ledger mismatch: {profile_id(p)}")
        if (
            cert.triangle_cap is not None
            and cert.s4 is not None
            and bound_from_cap(p, cert.triangle_cap, cert.s4) != (cert.s3, cert.bound)
        ):
            raise AssertionError("structural envelope arithmetic mismatch")
    return State(bounds, catalog, hashes)


def current_state() -> State:
    return reconstruct_state(*committed_inputs())


def certificate_row(cert: Certificate) -> dict[str, object]:
    witness: object = {"STATUS": "CLASS_CERTIFICATE_DOES_NOT_ASSERT_INDIVIDUAL_REALIZABILITY"}
    if cert.witness_row is not None:
        triples, doubles = support_witness(cert)
        witness = {
            "STATUS": "PASS",
            "SOURCE": cert.witness_source,
            "TRIPLES": triples,
            "DOUBLES": doubles,
            "TRIPLE_SUPPORT_COUNT": len(triples),
            "DOUBLE_SUPPORT_COUNT": len(doubles),
        }
    return {
        "PROFILE_ID": profile_id(cert.profile),
        "SOURCE_RESULT": cert.source_result,
        "SOURCE_ROW": cert.source_row,
        "DEGREE_PROFILE": cert.profile,
        "CURRENT_BOUND": cert.bound,
        "TRIANGLE_CAP": cert.triangle_cap,
        "NONCORE_TRIANGLE_CAP": None if cert.triangle_cap is None else cert.triangle_cap - 22,
        "WEDGE_COUNT": overlap_wedge_count(cert.profile),
        "S3": cert.s3,
        "S4_FLOOR": cert.s4,
        "REALIZABILITY_WITNESS": witness,
        "BOUND_LIMITING_RELAXATION": cert.relaxation,
    }


def signature(cert: Certificate) -> tuple[int, ...]:
    if cert.triangle_cap is None or cert.s4 is None or cert.s3 is None:
        raise AssertionError("owner lacks structural certificate values")
    return (
        20,
        22,
        27,
        93,
        sum(d * d for d in cert.profile),
        overlap_wedge_count(cert.profile),
        cert.triangle_cap,
        cert.s3,
        cert.s4,
        cert.bound,
    )


def signature_groups(certificates: Sequence[Certificate]) -> tuple[tuple[Certificate, ...], ...]:
    groups: dict[tuple[int, ...], list[Certificate]] = defaultdict(list)
    for cert in certificates:
        groups[signature(cert)].append(cert)
    return tuple(tuple(group) for _, group in sorted(groups.items()))


def target_cap(cert: Certificate) -> int:
    if cert.triangle_cap is None or cert.s4 is None:
        raise AssertionError("target needs a structural cap and S4 floor")
    unit = cert.bound - bound_from_cap(cert.profile, cert.triangle_cap - 1, cert.s4)[1]
    required = (cert.bound - NEXT_CURSOR_BOUND + unit - 1) // unit
    cap = cert.triangle_cap - required
    if bound_from_cap(cert.profile, cap, cert.s4)[1] > NEXT_CURSOR_BOUND:
        raise AssertionError("target cannot reach cursor")
    return cap


def assert_solver_scope(
    profiles: Sequence[DegreeProfile], bounds: Mapping[DegreeProfile, int]
) -> None:
    family, owners = family_state(bounds)
    if (
        not profiles
        or len(set(profiles)) != len(profiles)
        or family <= NEXT_CURSOR_BOUND
        or any(p not in bounds or p not in owners or p == NEXT_CURSOR_PROFILE for p in profiles)
    ):
        raise AssertionError("only current resolved max/tied owners may enter a model")


def union_support_model(
    profiles: Sequence[DegreeProfile], ceiling: int
) -> tuple[Any, dict[Triple, Any], dict[Pair, Any], list[Any], list[Any]]:
    """Exact union of linear 22-triple/27-double supports, with open-wedge ceiling.

    A support realizes one row of the degree table. The indicator implications
    provide an existential encoding of O <= ceiling: each genuinely open wedge
    forces its indicator to 1, and every other indicator can be zero.
    """
    if not profiles or ceiling < 0 or NEXT_CURSOR_PROFILE in profiles:
        raise AssertionError("invalid or forbidden group model")
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
        # Nonadjacent endpoints have at least deg(a)+deg(b)-(20-2)
        # common neighbors. Every such common neighbor is an open-wedge center.
        # This redundant cut follows from the same exact graph, without assuming
        # a particular histogram or using a feasible objective as a proof.
        model.Add(sum(by_ends[(a, b)]) >= degrees[a] + degrees[b] - 6).OnlyEnforceIf(edge.Not())
    model.Add(sum(indicators) <= ceiling)
    return model, triples, doubles, degrees, indicators


def configured_solver(seconds: float) -> Any:
    cp_model: Any = import_module("ortools.sat.python.cp_model")
    solver: Any = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 649
    return solver


def witness_model_check(group: Sequence[Certificate]) -> dict[str, object]:
    profiles = tuple(c.profile for c in group)
    checks: list[dict[str, object]] = []
    for cert in group:
        if cert.witness_row is None:
            continue
        ts, ds = support_witness(cert)
        edges = {tuple(sorted(p)) for t in ts for p in combinations(t, 2)} | set(ds)
        triangles = sum(
            all(p in edges for p in combinations(t, 2)) for t in combinations(range(20), 3)
        )
        open_count = overlap_wedge_count(cert.profile) - 3 * triangles
        statuses: dict[str, str] = {}
        for label, ceiling in (("AT_WITNESS_COUNT", open_count), ("ONE_BELOW", open_count - 1)):
            model, tv, dv, degrees, _ = union_support_model(profiles, ceiling)
            for v, d in zip(degrees, cert.profile, strict=True):
                model.Add(v == d)
            for t, v in tv.items():
                model.Add(v == int(t in ts))
            for p, v in dv.items():
                model.Add(v == int(p in ds))
            solver = configured_solver(10.0)
            statuses[label] = str(solver.StatusName(solver.Solve(model)))
        if statuses != {"AT_WITNESS_COUNT": "OPTIMAL", "ONE_BELOW": "INFEASIBLE"}:
            raise AssertionError("union model fails committed witness nonvacuity")
        checks.append(
            {
                "PROFILE_ID": profile_id(cert.profile),
                "WITNESS_OPEN_WEDGES": open_count,
                "FIXED_WITNESS_STATUSES": statuses,
            }
        )
    return {"STATUS": "PASS" if checks else "NOT_APPLICABLE_CLASS_ENVELOPE", "CHECKS": checks}


def solve_group(profiles: Sequence[DegreeProfile], cap: int, seconds: float) -> dict[str, object]:
    wedge = overlap_wedge_count(profiles[0])
    ceiling = wedge - 3 * (cap + 1)
    model, _, _, _, indicators = union_support_model(profiles, ceiling)
    solver = configured_solver(seconds)
    status = str(solver.StatusName(solver.Solve(model)))
    return {
        "ROUTE": "A_EXACT_SUPPORT_UNION_OPEN_WEDGE_REFUTATION",
        "STATUS": status,
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE" if status == "INFEASIBLE" else "NOT_CERTIFIED",
        "PROFILE_IDS": list(map(profile_id, profiles)),
        "WEDGE_COUNT": wedge,
        "REFUTED_GRAPH_TRIANGLE_COUNT": cap + 1,
        "OPEN_WEDGE_CEILING_REFUTED": ceiling,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": cap if status == "INFEASIBLE" else None,
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": ceiling + 1 if status == "INFEASIBLE" else None,
        "OPEN_WEDGE_INDICATOR_COUNT": len(indicators),
        "SOLVER_WALL_TIME_SECONDS": float(solver.WallTime()),
        "SOLVER_CONFIGURED_WALL_LIMIT": seconds,
    }


def accepted_cap(
    proof: Mapping[str, object], profiles: Sequence[DegreeProfile], cap: int
) -> int | None:
    if proof.get("STATUS") != "INFEASIBLE":
        return None
    if (
        proof.get("CERTIFICATE_KIND") != "CP_SAT_INFEASIBLE"
        or proof.get("PROFILE_IDS") != list(map(profile_id, profiles))
        or proof.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND") != cap
        or proof.get("REFUTED_GRAPH_TRIANGLE_COUNT") != cap + 1
        or proof.get("OPEN_WEDGE_CEILING_REFUTED")
        != overlap_wedge_count(profiles[0]) - 3 * (cap + 1)
    ):
        raise AssertionError("group proof identity mismatch")
    return cap


def bounded_group(
    group: Sequence[Certificate], bounds: Mapping[DegreeProfile, int], deadline: float
) -> dict[str, object]:
    profiles = tuple(c.profile for c in group)
    assert_solver_scope(profiles, bounds)
    native = NATIVE_GROUP_SECONDS if len(group) > 1 else NATIVE_INDIVIDUAL_SECONDS
    seconds = min(native, deadline - monotonic() - EXTERNAL_GRACE_SECONDS - 1)
    if seconds <= 0:
        return {"STATUS": "PROOF_BUDGET_EXHAUSTED", "PROFILE_IDS": list(map(profile_id, profiles))}
    request = {
        "PROFILES": list(map(profile_id, profiles)),
        "CAP": target_cap(group[0]),
        "SECONDS": seconds,
        "BOUNDS": {profile_id(p): b for p, b in bounds.items()},
    }
    started = monotonic()
    env = {
        **os.environ,
        "PYTHONPATH": str(repo_root() / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
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


def run_batch(
    state: State,
    prove: Callable[[Sequence[Certificate], Mapping[DegreeProfile, int]], dict[str, object]],
) -> dict[str, object]:
    bounds = dict(state.bounds)
    catalog = dict(state.certificates)
    steps: list[dict[str, object]] = []
    attempts: list[dict[str, object]] = []
    exposed: set[DegreeProfile] = set()

    def attempt(group: Sequence[Certificate]) -> bool:
        before, _ = family_state(bounds)
        profiles = tuple(c.profile for c in group)
        assert_solver_scope(profiles, bounds)
        proof = prove(group, dict(bounds))
        attempts.append({"OWNER_CERTIFICATES": [certificate_row(c) for c in group], **proof})
        cap = accepted_cap(proof, profiles, target_cap(group[0]))
        if cap is None:
            return False
        for cert in group:
            s3, bound = bound_from_cap(cert.profile, cap, integer(cert.s4))
            if bound >= bounds[cert.profile] or bound > NEXT_CURSOR_BOUND:
                raise AssertionError("group refinement cannot reach its structural target")
            bounds[cert.profile] = bound
            catalog[cert.profile] = replace(
                cert,
                bound=bound,
                s3=s3,
                triangle_cap=cap,
                source_result=RESULT_FILENAME,
                source_row=f"GROUP_ATTEMPTS[{len(attempts) - 1}]",
                relaxation="A_EXACT_SUPPORT_UNION_OPEN_WEDGE_REFUTATION",
            )
        after, new_owners = family_state(bounds)
        steps.append(
            {
                "GROUP_PROFILE_IDS": list(map(profile_id, profiles)),
                "FAMILY_BOUND_BEFORE": before,
                "FAMILY_BOUND_AFTER": after,
                "MAX_RESOLVED_BOUND": max(bounds.values()),
                "OWNER_SET_AFTER": list(map(profile_id, new_owners)),
                "NEW_BOUND": bounds[profiles[0]],
                "TRIANGLE_CAP": cap,
                "COMPLETE_LEDGER_ROW_COUNT": len(bounds),
            }
        )
        return True

    while family_state(bounds)[0] > NEXT_CURSOR_BOUND:
        _, owners = family_state(bounds)
        exposed.update(p for p in owners if p not in OWNERS)
        groups = signature_groups([catalog[p] for p in owners])
        progress = False
        for group in groups:
            if attempt(group):
                progress = True
                continue
            # Preserve the inconclusive union before independent models.
            if len(group) > 1:
                for cert in group:
                    if attempts[-1].get("STATUS") == "PROOF_BUDGET_EXHAUSTED":
                        break
                    if attempt((cert,)):
                        progress = True
        if not progress:
            break
    family, owners = family_state(bounds)
    status = (
        SUCCESS_A
        if family <= INCUMBENT
        else SUCCESS_B
        if max(bounds.values()) <= NEXT_CURSOR_BOUND
        else SUCCESS_C
        if family < START_FAMILY_BOUND
        else NO_DROP
    )
    return {
        "TASK_STATUS": status,
        "FAMILY_UPPER_BOUND": family,
        "MAX_RESOLVED_BOUND": max(bounds.values()),
        "CURRENT_BOUND_OWNER_SET": list(map(profile_id, owners)),
        "CURRENT_BOUND_OWNER_CERTIFICATES": [
            certificate_row(catalog[p]) for p in owners if p in catalog
        ],
        "GROUP_ATTEMPTS": attempts,
        "GROUP_REFINEMENT_STEPS": steps,
        "NEWLY_EXPOSED_RESOLVED_OWNER_COUNT": len(exposed),
        "NEWLY_EXPOSED_RESOLVED_OWNER_PROFILES": list(
            map(profile_id, sorted(exposed, reverse=True))
        ),
        "REFINED_OWNER_BOUNDS": {profile_id(p): bounds[p] for p in OWNERS},
        "FINAL_RESOLVED_LEDGER": [
            {"PROFILE_ID": profile_id(p), "CURRENT_BOUND": b}
            for p, b in sorted(bounds.items(), key=lambda item: (item[1], item[0]), reverse=True)
        ],
    }


def compute_result(prior: dict[str, object] | None = None) -> dict[str, object]:
    started_epoch = (
        time() if prior is None else float(cast(float, prior["PROOF_STARTED_UNIX_TIME"]))
    )
    started = monotonic() - (time() - started_epoch)
    primitives = canonical_primitive_preflight()
    runtime = solver_runtime_preflight()
    s4 = k20_min_s2_s4_lower_bound_certificate()
    if (K20_S1, K20_S2, s4.s4_lower_bound) != (372_228_640, 63_838_600, 112):
        raise AssertionError("canonical primitive/S4 preflight changed")
    state = current_state()
    if coarse_profile_envelope(NEXT_CURSOR_PROFILE).family_upper_bound != NEXT_CURSOR_BOUND:
        raise AssertionError("frozen cursor arithmetic changed")
    groups = signature_groups([state.certificates[p] for p in OWNERS])
    witness_checks = (
        [witness_model_check(group) for group in groups]
        if prior is None
        else [object_row(r) for r in rows(prior["SIX_OWNER_UNION_NONVACUITY"])]
    )
    for check in witness_checks:
        if check["STATUS"] != "PASS" or len(rows(check["CHECKS"])) != 6:
            raise AssertionError("six-owner union nonvacuity check did not pass")

    cached = [] if prior is None else [object_row(r) for r in rows(prior["GROUP_ATTEMPTS"])]

    def prove(
        group: Sequence[Certificate], bounds: Mapping[DegreeProfile, int]
    ) -> dict[str, object]:
        if cached:
            proof = cached.pop(0)
            if proof["PROFILE_IDS"] != [profile_id(c.profile) for c in group]:
                raise AssertionError("preserved failed union identity changed")
            proof["PRESERVED_FROM_FIRST_EXECUTION"] = True
            return proof
        print(
            f"Proving {len(group)} owners at {group[0].bound}: cap {target_cap(group[0])}",
            file=sys.stderr,
            flush=True,
        )
        proof = bounded_group(group, bounds, started + PROOF_WALL_SECONDS)
        print(f"Group status {proof['STATUS']}", file=sys.stderr, flush=True)
        return proof

    outcome = run_batch(state, prove)
    attempts = [object_row(a) for a in rows(outcome["GROUP_ATTEMPTS"])]
    result: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "START_FAMILY_BOUND": START_FAMILY_BOUND,
        "OWNER_COUNT": 6,
        "OWNER_PROFILES": list(OWNER_IDS),
        "OWNER_CERTIFICATES": [certificate_row(state.certificates[p]) for p in OWNERS],
        "OWNER_SIGNATURE_GROUP_COUNT": len(groups),
        "OWNER_SIGNATURE_GROUPS": [
            {
                "SIGNATURE": signature(g[0]),
                "SIGNATURE_FIELDS": [
                    "N",
                    "TRIPLES",
                    "DOUBLES",
                    "EDGES",
                    "DEGREE_SQUARE_SUM",
                    "WEDGES",
                    "TRIANGLE_CAP",
                    "S3",
                    "S4_FLOOR",
                    "CURRENT_BOUND",
                ],
                "PROFILE_IDS": [profile_id(c.profile) for c in g],
                "COVERAGE": "EXACT_ALLOWED_ASSIGNMENT_UNION_OF_LISTED_HISTOGRAMS",
            }
            for g in groups
        ],
        "START_OWNER_BOUNDS": {p: START_FAMILY_BOUND for p in OWNER_IDS},
        "REQUIRED_REDUCTION": START_FAMILY_BOUND - NEXT_CURSOR_BOUND,
        "REDUCTION_PER_TRIANGLE": 11_872,
        "REQUIRED_TRIANGLE_REDUCTION": 2,
        "TARGET_TRIANGLE_CAP": 269,
        "SIX_OWNER_UNION_NONVACUITY": witness_checks,
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
            "EXTERNAL_GRACE_SECONDS": EXTERNAL_GRACE_SECONDS,
            "PROOF_WALL_SECONDS": PROOF_WALL_SECONDS,
            "CP_SAT_SEARCH_WORKERS": 1,
            "EXTERNAL_KILL_AFTER_SECONDS": EXTERNAL_KILL_SECONDS,
        },
        "SOLVER_ACTUAL_WALL_TIME": sum(
            float(cast(float, a.get("SOLVER_WALL_TIME_SECONDS", 0))) for a in attempts
        ),
        "SOLVER_STATUS": [a["STATUS"] for a in attempts],
        "PROOF_ACTUAL_WALL_SECONDS": monotonic() - started,
        "PROOF_STARTED_UNIX_TIME": started_epoch,
        "RESOLVED_LEDGER_COUNT": 408,
        "RESOLVED_PROFILE_COUNT_INCLUDING_FROZEN_CLASS": 484,
        "FROZEN_76_PROFILE_CLASS_BOUND": 313_628_776,
        "FROZEN_CLASS_AUTHORITY": "PINNED_R25",
        "PLATEAU_RERUN_COUNT": 0,
        "CHEAP_CHASE_RERUN_COUNT": 0,
        "CURSOR_PROFILE_SOLVES": 0,
        "NO_76_PLATEAU_RERUN_GUARD": "PASS",
        "NO_48_OWNER_CHEAP_CHASE_RERUN_GUARD": "PASS",
        "NO_CURSOR_WORK_GUARD": "PASS",
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        "INCUMBENT": INCUMBENT,
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "RUNTIME_TRANSITION_OCCURRED": "NO",
        "JUDGE_MODE": "NOT_APPLICABLE",
        "JUDGE_DISPATCH": "SUPPRESSED",
        **outcome,
    }
    result["SOLVER_CERTIFIED_BOUND"] = outcome["FAMILY_UPPER_BOUND"]
    result["SOLVER_CERTIFIED_BOUND_SCOPE"] = "COMPLETE_FAMILY_LEDGER_PLUS_UNRESOLVED_CURSOR"
    result["REMAINING_GAP"] = integer(outcome["FAMILY_UPPER_BOUND"]) - INCUMBENT
    result["CURSOR_GENUINELY_LOAD_BEARING"] = outcome["FAMILY_UPPER_BOUND"] == NEXT_CURSOR_BOUND
    result["FAMILY_STATUS"] = (
        "OPEN_CURSOR_LOAD_BEARING"
        if result["CURSOR_GENUINELY_LOAD_BEARING"]
        else "OPEN_STRICTLY_TIGHTENED"
        if outcome["TASK_STATUS"] == SUCCESS_C
        else "OPEN"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group-child")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume-failed-union", action="store_true")
    args = parser.parse_args()
    if args.group_child:
        request = object_row(json.loads(args.group_child))
        profiles = tuple(decode_profile(p) for p in rows(request["PROFILES"]))
        bounds = {decode_profile(p): integer(b) for p, b in object_row(request["BOUNDS"]).items()}
        baseline = current_state()
        if bounds.keys() != baseline.bounds.keys() or any(
            b > baseline.bounds[p] for p, b in bounds.items()
        ):
            raise AssertionError("child requires complete monotone resolved ledger")
        assert_solver_scope(profiles, bounds)
        print(
            json.dumps(
                solve_group(
                    profiles, integer(request["CAP"]), float(cast(float, request["SECONDS"]))
                )
            )
        )
        return
    output = args.output or repo_root() / RESULT_DIRECTORY / RESULT_FILENAME
    if output.resolve() != (repo_root() / RESULT_DIRECTORY / RESULT_FILENAME).resolve() or (
        output.exists() and not args.resume_failed_union
    ):
        raise AssertionError("only new exact R26 result output is authorized")
    prior: dict[str, object] | None = None
    if args.resume_failed_union:
        prior = object_row(json.loads(output.read_text()))
        if (
            prior.get("TASK_STATUS") != NO_DROP
            or prior.get("BASE_HEAD") != BASE_HEAD
            or len(rows(prior["GROUP_ATTEMPTS"])) != 1
            or object_row(rows(prior["GROUP_ATTEMPTS"])[0]).get("STATUS") != "UNKNOWN"
        ):
            raise AssertionError("resume only preserves the initial inconclusive union")
        # First launcher predated the explicit timestamp field. Its result mtime
        # marks proof completion, so retain the original elapsed wall budget.
        prior["PROOF_STARTED_UNIX_TIME"] = output.stat().st_mtime - float(
            cast(float, prior["PROOF_ACTUAL_WALL_SECONDS"])
        )
    result = compute_result(prior)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: result[k] for k in ("TASK_STATUS", "FAMILY_UPPER_BOUND", "CURRENT_BOUND_OWNER_SET")}
        )
    )


if __name__ == "__main__":
    main()
