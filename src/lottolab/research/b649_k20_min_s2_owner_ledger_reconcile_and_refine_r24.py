"""Reconcile the post-R23 owner ledger, then refine only its resolved owners (R24).

R23's handoff named the owner 66655555555511100000 but separately reported an
owner set of 66665555555411100000 and 66655555555521000000. Rebuild the
complete post-R23 resolved ledger from committed result blobs only (R22's final
ledger plus R23's 69-profile class certificate), list every resolved profile at
or above the unresolved cursor with its committed certificate provenance, and
resolve both handoff fields against it. Then refine only the current max/tied
max resolved owners. The cursor is a ceiling and is never sent to a solver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
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

DegreeProfile = tuple[int, ...]
TASK_ID = "B649_K20_MIN_S2_OWNER_LEDGER_RECONCILE_AND_REFINE_R24"
TASK_BRANCH = "codex/b649-k20-min-s2-owner-ledger-reconcile-and-refine-r24"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "d063cad13371bde595fb93525cec4c4d08082f8e"
BASE_TREE = "2ed1651d1e4591d05373a5a21bcafe1a5ab9fa50"
START_BOUND = 313_653_976
INCUMBENT = 313_239_661
CURSOR_BOUND = 313_652_520
CURSOR_PROFILE: DegreeProfile = tuple(map(int, "66666665432211111111"))
HANDOFF_OWNER_FIELD = "66655555555511100000"
HANDOFF_OWNER_SET_FIELD = ("66665555555411100000", "66655555555521000000")
R22_LEDGER_COUNT = 339
R23_CLASS_COUNT = 69
R23_CLASS_BOUND = 313_631_576
EXPECTED_RESOLVED_COUNT = R22_LEDGER_COUNT + R23_CLASS_COUNT
MAX_OWNER_PROFILES = 16
PROOF_WALL_SECONDS = 3_600.0
NATIVE_REFUTATION_SECONDS = 900.0
NATIVE_COMPLEMENT_SECONDS = 90.0
NATIVE_MOTIF_SECONDS = 60.0
NATIVE_WITNESS_SECONDS = 30.0
EXTERNAL_GRACE_SECONDS = 30.0
EXTERNAL_KILL_AFTER_SECONDS = 5
RESULT_DIRECTORY = "docs/research/matrix-native-results"
RESULT_FILENAME = "b649-k20-min-s2-owner-ledger-reconcile-and-refine-r24-result.json"
MODULE_NAME = "lottolab.research.b649_k20_min_s2_owner_ledger_reconcile_and_refine_r24"
INPUT_FILENAMES = {
    "R12": "b649-k20-min-s2-continued-multi-plateau-descent-r12-result.json",
    "R20": "b649-k20-min-s2-resolved-above-cursor-owner-chase-r20-result.json",
    "R22": "b649-k20-min-s2-resolved-owner-pair-refinement-r22-result.json",
    "R23": "b649-k20-min-s2-unique-cursor-class-closure-r23-result.json",
}
INPUT_SHA256 = {
    "R12": "e36cf3010e077923a7c27efa83e3b9dc157b3e34e5458708eb70ce40998f77f0",
    "R20": "47afe9b8e5643f0123fcccfcf678689755106056e7b9b68a3431b837706113aa",
    "R22": "fea84b7d4cd814d231cc38ad2d98d682fd19ec2875de6fdf2ecac5c8e4256ef6",
    "R23": "327099e4b569bb7dfd512d4e8a47fb844ef9c487bb4e6a29e9a0e6f21381ee79",
}
ROUTES = (
    "A_EXACT_SUPPORT_OPEN_WEDGE_REFUTATION",
    "B_COMPLEMENT_TRIANGLE_LOWER_BOUND",
    "C_EXACT_NONCORE_TRIANGLE_CEILING",
)
LATER_ROUTES = (
    "D_LOOSE_CYCLE_PASCH_SHARED_VERTEX",
    "E_MINIMUM_S4_AT_S3_MAXIMIZERS",
    "F_HIGHER_ORDER_MULTIPLICITY",
)
SUCCESS_A = "SUCCESS_A_FAMILY_CLOSED"
SUCCESS_B = "SUCCESS_B_ALL_RESOLVED_AT_OR_BELOW_CURSOR"
SUCCESS_C = "SUCCESS_C_STRICT_FAMILY_TIGHTENING_EXACT_REMAINING_OWNERS"
NO_DROP = "NO_CERTIFIED_FAMILY_DROP"
_WITNESS_SOURCE = re.compile(r"R12\.PROFILE_BOUNDS\[(\d+)\]")


@dataclass(frozen=True, slots=True)
class CurrentState:
    bounds: Mapping[DegreeProfile, int]
    carriers: Mapping[DegreeProfile, str]
    certificates: Mapping[DegreeProfile, Certificate]
    above_cursor: tuple[dict[str, object], ...]
    handoff: dict[str, object]
    input_hashes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class Outcome:
    status: str
    bounds: Mapping[DegreeProfile, int]
    family_bound: int
    owners: tuple[DegreeProfile, ...]
    attempts: tuple[dict[str, object], ...]
    steps: tuple[dict[str, object], ...]
    dispatched: tuple[DegreeProfile, ...]


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
    """Read pinned result blobs at BASE_HEAD; working files are never authority."""

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


def at_or_above_cursor(bounds: Mapping[DegreeProfile, int]) -> tuple[DegreeProfile, ...]:
    return tuple(
        p
        for p, _ in sorted(bounds.items(), key=lambda item: (item[1], item[0]), reverse=True)
        if bounds[p] >= CURSOR_BOUND
    )


def assert_no_omitted_above_cursor(
    bounds: Mapping[DegreeProfile, int], listed: tuple[dict[str, object], ...]
) -> None:
    identities = [decode_profile(row["PROFILE_ID"]) for row in listed]
    if len(identities) != len(set(identities)):
        raise AssertionError("duplicate resolved-above-cursor row")
    if set(identities) != set(at_or_above_cursor(bounds)):
        raise AssertionError("a resolved profile at or above the cursor was omitted or invented")
    for row, profile in zip(listed, identities, strict=True):
        if row["BOUND"] != bounds[profile]:
            raise AssertionError("listed resolved-above-cursor bound differs from the ledger")


def assert_owner_claim(claim: tuple[str, ...], bounds: Mapping[DegreeProfile, int]) -> None:
    """Reject any reported owner set that is not exactly the recomputed maximum."""

    family, owners = family_state(bounds)
    if tuple(sorted(map(decode_profile, claim), reverse=True)) != tuple(
        sorted(owners, reverse=True)
    ):
        detail = {profile_id(p): bounds.get(p) for p in map(decode_profile, claim)}
        raise AssertionError(f"owner claim is not the family maximum {family}: {detail}")


def _committed_owner_attempts(
    inputs: Mapping[str, dict[str, object]],
) -> dict[DegreeProfile, tuple[str, int, dict[str, object]]]:
    """Latest committed certified owner attempt per profile (R22 supersedes R20)."""

    attempts: dict[DegreeProfile, tuple[str, int, dict[str, object]]] = {}
    for label in ("R20", "R22"):
        for index, raw in enumerate(_rows(inputs[label]["OWNER_ATTEMPTS"])):
            attempt = _object(raw)
            if attempt.get("CERTIFIED_OWNER_BOUND") is None:
                continue
            attempts[decode_profile(attempt["PROFILE_ID"])] = (label, index, attempt)
    return attempts


def _witness_source(inputs: Mapping[str, dict[str, object]], profile: DegreeProfile) -> str:
    for label, key in (("R22", "OWNER_CERTIFICATES"), ("R20", "RESOLVED_ABOVE_CURSOR_SET")):
        for raw in _rows(inputs[label][key]):
            row = _object(raw)
            if decode_profile(row["PROFILE_ID"]) == profile:
                return str(row["WITNESS_SOURCE"])
    raise AssertionError(f"no committed support witness source for {profile_id(profile)}")


def owner_certificate(
    inputs: Mapping[str, dict[str, object]], profile: DegreeProfile, bound: int
) -> tuple[Certificate, dict[str, object]]:
    """Rebuild one above-cursor certificate and its provenance row, or STOP."""

    found = _committed_owner_attempts(inputs).get(profile)
    if found is None:
        raise AssertionError(f"above-cursor bound lacks a committed owner certificate: {bound}")
    label, index, attempt = found
    proofs = [_object(raw) for raw in _rows(attempt["ROUTES"])]
    limiting = attempt.get("BOUND_LIMITING_RELAXATION")
    proof = next((p for p in proofs if p.get("ROUTE") == limiting), proofs[-1] if proofs else {})
    cap = _integer(attempt["REFINED_TRIANGLE_CAP"])
    s3 = _integer(attempt["REFINED_S3"])
    s4 = _integer(attempt["S4_FLOOR"])
    if (
        attempt.get("CERTIFIED_OWNER_BOUND") != bound
        or bound_from_cap(profile, cap, s4) != (s3, bound)
        or proof.get("STATUS") != "INFEASIBLE"
        or proof.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND") != cap
    ):
        raise AssertionError(f"committed owner certificate does not reproduce {bound}")
    source = _witness_source(inputs, profile)
    match = _WITNESS_SOURCE.fullmatch(source)
    if match is None:
        raise AssertionError(f"unsupported committed witness source {source}")
    row = _object(_rows(inputs["R12"]["PROFILE_BOUNDS"])[int(match.group(1))])
    if (
        decode_profile(row["PROFILE"]) != profile
        or row.get("REALIZABILITY") != "REALIZABLE"
        or row.get("SUPPORT_SOLVER_STATUS") != "OPTIMAL"
    ):
        raise AssertionError("committed realizability witness does not match the owner")
    cert = Certificate(
        profile,
        bound,
        INPUT_FILENAMES[label],
        f"OWNER_ATTEMPTS[{index}]",
        "REALIZABLE",
        s3,
        s4,
        cap,
        str(limiting),
        row,
        source,
    )
    triples, doubles = support_witness(cert)
    provenance: dict[str, object] = {
        "PROFILE_ID": profile_id(profile),
        "BOUND": bound,
        "SOURCE_RESULT": cert.source_result,
        "SOURCE_ROW": cert.source_row,
        "REALIZABILITY_STATUS": cert.realizability,
        "CERTIFICATE_KIND": proof.get("CERTIFICATE_KIND"),
        "BOUND_LIMITING_RELAXATION": limiting,
        "GRAPH_TRIANGLE_CAP": cap,
        "NONCORE_TRIANGLE_CAP": cap - K20_TRIPLE_SUPPORT_COUNT,
        "WEDGE_COUNT": overlap_wedge_count(profile),
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": proof.get("CERTIFIED_OPEN_WEDGE_LOWER_BOUND"),
        "S3": s3,
        "S4_FLOOR": s4,
        "EXACT_RELAXATION": {
            "IDENTITY": "S1 - S2 + S3 - floor(4*S4/7)",
            "S1": K20_S1,
            "S2": K20_S2,
            "S3": s3,
            "S4_FLOOR": s4,
            "VALUE": bound,
        },
        "WITNESS_SOURCE": source,
        "WITNESS_SUPPORT_COUNTS": [len(triples), len(doubles)],
    }
    return cert, provenance


def reconstruct_state(
    inputs: Mapping[str, dict[str, object]], hashes: Mapping[str, str]
) -> CurrentState:
    r22, r23 = inputs["R22"], inputs["R23"]
    r22_relative = f"{RESULT_DIRECTORY}/{INPUT_FILENAMES['R22']}"
    if r23.get("COMMITTED_INPUT_SHA256") != {r22_relative: INPUT_SHA256["R22"]}:
        raise AssertionError("R23 was not built on the pinned R22 ledger")
    if (
        r23.get("NEXT_ACTIVE_PROFILE") != profile_id(CURSOR_PROFILE)
        or r23.get("NEXT_ACTIVE_BOUND") != CURSOR_BOUND
        or r23.get("INCUMBENT") != INCUMBENT
    ):
        raise AssertionError("R23 cursor or incumbent authority changed")
    bounds: dict[DegreeProfile, int] = {}
    carriers: dict[DegreeProfile, str] = {}
    rows = _rows(r22["FINAL_RESOLVED_LEDGER"])
    if len(rows) != R22_LEDGER_COUNT:
        raise AssertionError("R22 final resolved ledger count changed")
    for index, raw in enumerate(rows):
        row = _object(raw)
        profile = decode_profile(row["PROFILE_ID"])
        if profile in bounds:
            raise AssertionError("duplicate resolved profile")
        bounds[profile] = _integer(row["CURRENT_BOUND"])
        carriers[profile] = f"R22.FINAL_RESOLVED_LEDGER[{index}]"
    classes = _rows(r23["CLASS_CERTIFICATES"])
    if len(classes) != 1:
        raise AssertionError("R23 class certificate count changed")
    plateau = _object(classes[0])
    identities = _rows(plateau["PROFILE_IDENTITIES"])
    if (
        len(identities) != R23_CLASS_COUNT
        or plateau.get("CLASS_FAMILY_UPPER_BOUND") != R23_CLASS_BOUND
        or plateau.get("COMPLETE_PLATEAU_COVERAGE") is not True
        or identities != r23.get("CURRENT_LOAD_BEARING_PLATEAU")
    ):
        raise AssertionError("complete R23 class certificate changed")
    for raw in identities:
        profile = decode_profile(raw)
        if profile in bounds:
            raise AssertionError("R23 class repeats a resolved profile")
        bounds[profile] = R23_CLASS_BOUND
        carriers[profile] = "R23.CLASS_CERTIFICATES[0]"
    if len(bounds) != EXPECTED_RESOLVED_COUNT:
        raise AssertionError("complete post-R23 resolved ledger count changed")
    family, owners = family_state(bounds)
    if family != START_BOUND or r23.get("FAMILY_UPPER_BOUND") != family:
        raise AssertionError(
            f"FAMILY_UPPER_BOUND mismatch: recomputed {family}, packet {START_BOUND}, "
            f"R23 {r23.get('FAMILY_UPPER_BOUND')}"
        )

    certificates: dict[DegreeProfile, Certificate] = {}
    above: list[dict[str, object]] = []
    for profile in at_or_above_cursor(bounds):
        cert, provenance = owner_certificate(inputs, profile, bounds[profile])
        certificates[profile] = cert
        above.append({**provenance, "LEDGER_CARRIER": carriers[profile]})
    assert_no_omitted_above_cursor(bounds, tuple(above))
    handoff = resolve_handoff_owner_fields(inputs, bounds, owners)
    return CurrentState(bounds, carriers, certificates, tuple(above), handoff, hashes)


def resolve_handoff_owner_fields(
    inputs: Mapping[str, dict[str, object]],
    bounds: Mapping[DegreeProfile, int],
    owners: tuple[DegreeProfile, ...],
) -> dict[str, object]:
    """Decide each inconsistent R23 handoff field from the rebuilt ledger only."""

    r22, r23 = inputs["R22"], inputs["R23"]
    owner_claim = (HANDOFF_OWNER_FIELD,)
    set_claim = HANDOFF_OWNER_SET_FIELD
    assert_owner_claim(owner_claim, bounds)
    try:
        assert_owner_claim(set_claim, bounds)
    except AssertionError:
        set_is_owner_set = False
    else:
        set_is_owner_set = True
    if set_is_owner_set or r23.get("CURRENT_BOUND_OWNER_SET") != list(owner_claim):
        raise AssertionError("handoff owner fields do not resolve to one committed owner set")
    if r22.get("OWNER_PROFILES") != list(set_claim):
        raise AssertionError("the owner-set field is not R22's refined owner pair")
    refined = _object(r22["REFINED_OWNER_BOUNDS"])
    return {
        "HANDOFF_OWNER_FIELD": HANDOFF_OWNER_FIELD,
        "HANDOFF_OWNER_FIELD_STATUS": "AUTHORITATIVE_MATCHES_RECOMPUTED_FAMILY_MAXIMUM",
        "HANDOFF_OWNER_FIELD_COMMITTED_SOURCE": "R23.CURRENT_BOUND_OWNER / CURRENT_BOUND_OWNER_SET",
        "HANDOFF_OWNER_SET_FIELD": list(set_claim),
        "HANDOFF_OWNER_SET_FIELD_STATUS": "NOT_CURRENT_OWNERS_REJECTED",
        "HANDOFF_OWNER_SET_FIELD_COMMITTED_SOURCE": "R22.OWNER_PROFILES (R23.R22_OWNER_IDS guard)",
        "HANDOFF_OWNER_SET_FIELD_CURRENT_BOUNDS": {p: bounds[decode_profile(p)] for p in set_claim},
        "HANDOFF_OWNER_SET_FIELD_R22_REFINED_BOUNDS": {p: refined[p] for p in set_claim},
        "AUTHORITATIVE_CURRENT_BOUND_OWNER_SET": list(map(profile_id, owners)),
        "RESOLUTION": (
            "The owner-set field repeats R22's two refined owner profiles, both now at "
            f"{bounds[decode_profile(set_claim[0])]:,} below the cursor; the committed "
            "R23 owner set and the rebuilt ledger agree on the single owner field."
        ),
    }


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
    """Refine the current maximum only; recompute the full ledger after each step."""

    bounds = dict(state.bounds)
    certificates = dict(state.certificates)
    attempts: list[dict[str, object]] = []
    steps: list[dict[str, object]] = []
    exhausted: set[DegreeProfile] = set()
    dispatched: list[DegreeProfile] = []
    while True:
        family, owners = family_state(bounds)
        if family <= INCUMBENT:
            status = SUCCESS_A
            break
        if max(bounds.values()) <= CURSOR_BOUND:
            status = SUCCESS_B
            break
        pending = [p for p in owners if p not in exhausted]
        if not pending or (pending[0] not in dispatched and len(dispatched) >= MAX_OWNER_PROFILES):
            status = SUCCESS_C if family < START_BOUND else NO_DROP
            break
        owner = pending[0]
        assert_solver_scope(owner, bounds)
        if owner not in dispatched:
            dispatched.append(owner)
        attempt = refine(certificates[owner], dict(bounds))
        attempts.append(attempt)
        candidate = attempt.get("CERTIFIED_OWNER_BOUND")
        if candidate is None:
            exhausted.add(owner)
            continue
        refined = _integer(candidate)
        if refined >= bounds[owner]:
            raise AssertionError("owner improvement must be strict")
        before = bounds[owner]
        bounds[owner] = refined
        certificates[owner] = replace(
            certificates[owner],
            bound=refined,
            triangle_cap=_integer(attempt["REFINED_TRIANGLE_CAP"]),
            s3=_integer(attempt["REFINED_S3"]),
        )
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
                "RESOLVED_AT_OR_ABOVE_CURSOR_AFTER": [
                    {"PROFILE_ID": profile_id(p), "BOUND": bounds[p]}
                    for p in at_or_above_cursor(bounds)
                ],
                "CERTIFICATE": attempt,
            }
        )
    return Outcome(status, bounds, family, owners, tuple(attempts), tuple(steps), tuple(dispatched))


def solver_child(request: Mapping[str, object]) -> dict[str, object]:
    state = current_state()
    profile = decode_profile(request["PROFILE_ID"])
    bounds = {
        decode_profile(p): _integer(v) for p, v in _object(request["EFFECTIVE_BOUNDS"]).items()
    }
    if bounds.keys() != state.bounds.keys():
        raise AssertionError("solver request omits or adds resolved profiles")
    if any(bounds[p] != b for p, b in state.bounds.items() if p not in state.certificates):
        raise AssertionError("request mutates a certificate outside the above-cursor owners")
    if any(bounds[p] > b for p, b in state.bounds.items()):
        raise AssertionError("request weakens a committed bound")
    assert_solver_scope(profile, bounds)
    cert = state.certificates[profile]
    cap = _integer(request["TRIANGLE_CAP"])
    if bound_from_cap(profile, cap, _integer(cert.s4))[1] != bounds[profile]:
        raise AssertionError("requested triangle cap does not reproduce the effective bound")
    triples, doubles = support_witness(cert)
    route = request["ROUTE"]
    if route == "WITNESS":
        result = witness_open_wedge_check(
            profile, triples, doubles, wall_limit_seconds=NATIVE_WITNESS_SECONDS
        )
        result["WITNESS_SOURCE"] = cert.witness_source
    elif route == ROUTES[0]:
        result = exact_support_triangle_refutation(
            profile, refuted_triangle_count=cap, wall_limit_seconds=NATIVE_REFUTATION_SECONDS
        )
    elif route == ROUTES[1]:
        result = complement_route_attempt(profile, triples, doubles)
    elif route == ROUTES[2]:
        result = motif_triangle_bound(
            profile, triples, doubles, wall_limit_seconds=NATIVE_MOTIF_SECONDS
        )
        result["STATUS"] = result["SOLVER_STATUS"]
        result["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] = result[
            "SOLVER_CERTIFIED_TRIANGLE_UPPER_BOUND"
        ]
    else:
        raise AssertionError("unknown owner-only solver route")
    result.update({"ROUTE": route, "PROFILE_ID": profile_id(profile)})
    return result


def native_seconds(route: str) -> float:
    return {
        "WITNESS": 2 * NATIVE_WITNESS_SECONDS,
        ROUTES[0]: NATIVE_REFUTATION_SECONDS,
        ROUTES[1]: NATIVE_COMPLEMENT_SECONDS,
        ROUTES[2]: NATIVE_MOTIF_SECONDS,
    }[route]


def bounded_solver_call(
    cert: Certificate, bounds: Mapping[DegreeProfile, int], route: str, *, deadline: float
) -> dict[str, object]:
    """Run one owner route in a child under GNU timeout; never trust the native limit."""

    assert_solver_scope(cert.profile, bounds)
    external = native_seconds(route) + EXTERNAL_GRACE_SECONDS
    if deadline - monotonic() < external + EXTERNAL_KILL_AFTER_SECONDS:
        return {"ROUTE": route, "STATUS": "NOT_RUN_PROOF_WALL_BUDGET"}
    request = {
        "PROFILE_ID": profile_id(cert.profile),
        "ROUTE": route,
        "TRIANGLE_CAP": cert.triangle_cap,
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
    command = [
        "timeout",
        "--signal=TERM",
        f"--kill-after={EXTERNAL_KILL_AFTER_SECONDS}s",
        f"{external}s",
        sys.executable,
        "-m",
        MODULE_NAME,
        "--solver-request",
        json.dumps(request),
    ]
    started = monotonic()
    process = subprocess.run(
        command,
        cwd=repo_root(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=external + EXTERNAL_KILL_AFTER_SECONDS + 10,
    )
    elapsed = monotonic() - started
    if process.returncode in (124, 137):
        return {
            "ROUTE": route,
            "PROFILE_ID": profile_id(cert.profile),
            "STATUS": "EXTERNAL_HARD_TIMEOUT",
            "EXTERNAL_HARD_TIMEOUT_SECONDS": external,
            "EXTERNAL_TIMEOUT_EXIT_CODE": process.returncode,
            "SUBPROCESS_WALL_SECONDS": elapsed,
        }
    if process.returncode != 0:
        raise RuntimeError(f"owner solver child failed: {process.stderr[-2000:]}")
    result = _object(json.loads(process.stdout))
    result.update(
        {
            "NATIVE_WALL_LIMIT_SECONDS": native_seconds(route),
            "EXTERNAL_HARD_TIMEOUT_SECONDS": external,
            "EXTERNAL_TIMEOUT_EXIT_CODE": process.returncode,
            "SUBPROCESS_WALL_SECONDS": elapsed,
        }
    )
    return result


def refine_owner(
    cert: Certificate, bounds: Mapping[DegreeProfile, int], *, deadline: float
) -> dict[str, object]:
    witness = bounded_solver_call(cert, bounds, "WITNESS", deadline=deadline)
    if witness.get("STATUS") != "PASS":
        raise RuntimeError("owner witness non-vacuity check did not pass")
    routes: list[dict[str, object]] = []
    cap = _integer(cert.triangle_cap)
    s4 = _integer(cert.s4)
    for route in ROUTES:
        proof = bounded_solver_call(cert, bounds, route, deadline=deadline)
        routes.append(proof)
        if route == ROUTES[0]:
            candidate = accepted_refutation_cap(proof, cap)
        elif proof.get("STATUS") == "OPTIMAL":
            candidate = _integer(proof["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
        else:
            candidate = None
        if candidate is not None and candidate < cap:
            s3, bound = bound_from_cap(cert.profile, candidate, s4)
            return {
                "PROFILE_ID": profile_id(cert.profile),
                "START_BOUND": cert.bound,
                "START_TRIANGLE_CAP": cap,
                "REFINED_TRIANGLE_CAP": candidate,
                "REFINED_NONCORE_TRIANGLE_CAP": candidate - K20_TRIPLE_SUPPORT_COUNT,
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
        "LATER_ROUTES": f"NOT_RUN: {', '.join(LATER_ROUTES)}",
    }


def compute_result() -> dict[str, object]:
    started = monotonic()
    deadline = started + PROOF_WALL_SECONDS
    primitives = canonical_primitive_preflight()
    runtime = solver_runtime_preflight()
    state = current_state()
    s4 = k20_min_s2_s4_lower_bound_certificate()
    if s4.s4_lower_bound != 112:
        raise AssertionError("universal S4 floor changed")
    outcome = run_schedule(state, lambda c, b: refine_owner(c, b, deadline=deadline))
    calls = [_object(r) for a in outcome.attempts for r in _rows(a["ROUTES"])]
    witness_calls = [_object(a["WITNESS_CHECK"]) for a in outcome.attempts]
    solver_seconds = sum(float(cast(float, r.get("SOLVER_WALL_TIME_SECONDS", 0.0))) for r in calls)
    final_above = [
        {"PROFILE_ID": profile_id(p), "BOUND": outcome.bounds[p]}
        for p in at_or_above_cursor(outcome.bounds)
    ]
    route_statuses = [str(r.get("STATUS")) for r in calls]
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "TASK_STATUS": outcome.status,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "INPUT_AUTHORITY": "IMMUTABLE_BASE_HEAD_R12_R20_R22_R23_GIT_BLOBS",
        "COMMITTED_INPUT_SHA256": dict(state.input_hashes),
        "PROFILE_SOLVERS_RERUN_FOR_RECONSTRUCTION": False,
        "RESOLVED_LEDGER_COUNT": len(state.bounds),
        "RESOLVED_LEDGER_COMPOSITION": {
            "R22.FINAL_RESOLVED_LEDGER": R22_LEDGER_COUNT,
            "R23.CLASS_CERTIFICATES[0]": R23_CLASS_COUNT,
        },
        "START_FAMILY_BOUND": START_BOUND,
        "FAMILY_UPPER_BOUND_RECOMPUTATION": "PASS",
        **state.handoff,
        "RESOLVED_AT_OR_ABOVE_CURSOR_COUNT": len(state.above_cursor),
        "RESOLVED_AT_OR_ABOVE_CURSOR_PROFILES": list(state.above_cursor),
        "NO_OMITTED_RESOLVED_ABOVE_CURSOR": "PASS",
        "NEXT_HIGHEST_RESOLVED_BOUND_BELOW_CURSOR": max(
            b for b in state.bounds.values() if b < CURSOR_BOUND
        ),
        "OWNER_ATTEMPTS": list(outcome.attempts),
        "REFINEMENT_STEPS": list(outcome.steps),
        "OWNER_TRANSITION_COUNT": sum(
            1 for s in outcome.steps if s["OWNER_SET_BEFORE"] != s["OWNER_SET_AFTER"]
        ),
        "OWNERS_REFINED_COUNT": len({s["PROFILE_ID"] for s in outcome.steps}),
        "OWNER_PROFILES_DISPATCHED": list(map(profile_id, outcome.dispatched)),
        "NEXT_CURSOR_BOUND": CURSOR_BOUND,
        "NEXT_CURSOR_PROFILE": profile_id(CURSOR_PROFILE),
        "FAMILY_UPPER_BOUND": outcome.family_bound,
        "CURRENT_BOUND_OWNER_SET": list(map(profile_id, outcome.owners)),
        "FINAL_RESOLVED_AT_OR_ABOVE_CURSOR": final_above,
        "MAX_RESOLVED_BOUND": max(outcome.bounds.values()),
        "CURSOR_GENUINELY_LOAD_BEARING": max(outcome.bounds.values()) <= CURSOR_BOUND,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": max(0, outcome.family_bound - INCUMBENT),
        "FAMILY_STATUS": "CLOSED"
        if outcome.status == SUCCESS_A
        else "OPEN_STRICTLY_TIGHTENED"
        if outcome.family_bound < START_BOUND
        else "OPEN",
        "CERTIFIED_FAMILY_DROP": START_BOUND - outcome.family_bound,
        "FINAL_RESOLVED_LEDGER": [
            {"PROFILE_ID": profile_id(p), "CURRENT_BOUND": b}
            for p, b in sorted(
                outcome.bounds.items(), key=lambda item: (item[1], item[0]), reverse=True
            )
        ],
        "CANONICAL_PRIMITIVES": primitives,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "S4_CERTIFICATE": asdict(s4),
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_STATUS": "INFEASIBLE_CERTIFIED"
        if outcome.steps
        and all(
            _object(s["CERTIFICATE"]).get("BOUND_LIMITING_RELAXATION") == ROUTES[0]
            for s in outcome.steps
        )
        else "SEE_OWNER_ATTEMPTS",
        "SOLVER_ROUTE_STATUSES": route_statuses,
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "NATIVE_REFUTATION_SECONDS": NATIVE_REFUTATION_SECONDS,
            "NATIVE_COMPLEMENT_SECONDS": NATIVE_COMPLEMENT_SECONDS,
            "NATIVE_MOTIF_SECONDS": NATIVE_MOTIF_SECONDS,
            "NATIVE_WITNESS_SECONDS_PER_SOLVE": NATIVE_WITNESS_SECONDS,
            "EXTERNAL_TIMEOUT_GRACE_SECONDS": EXTERNAL_GRACE_SECONDS,
            "EXTERNAL_REFUTATION_TIMEOUT_SECONDS": NATIVE_REFUTATION_SECONDS
            + EXTERNAL_GRACE_SECONDS,
            "EXTERNAL_KILL_AFTER_SECONDS": EXTERNAL_KILL_AFTER_SECONDS,
            "EXTERNAL_WRAPPER": "GNU timeout --signal=TERM",
            "PROOF_WALL_SECONDS": PROOF_WALL_SECONDS,
            "MAX_RESOLVED_OWNER_PROFILES": MAX_OWNER_PROFILES,
            "CP_SAT_SEARCH_WORKERS": 1,
        },
        "SOLVER_ACTUAL_WALL_TIME": solver_seconds,
        "SOLVER_WRAPPED_CALL_WALL_SECONDS": sum(
            float(cast(float, r.get("SUBPROCESS_WALL_SECONDS", 0.0)))
            for r in (*calls, *witness_calls)
        ),
        "PROOF_ACTUAL_WALL_SECONDS": monotonic() - started,
        "SOLVER_CERTIFIED_BOUND": max(
            (_integer(s["REFINED_OWNER_BOUND"]) for s in outcome.steps), default=None
        ),
        "SOLVER_CERTIFIED_BOUND_SCOPE": "RESOLVED_OWNER_PROFILES_ONLY",
        "SOLVER_PROFILES_SENT": list(map(profile_id, outcome.dispatched)),
        "CURSOR_PROFILE_SOLVES": 0,
        "NO_CURSOR_WORK_GUARD": "PASS",
        "PLATEAU_RERUN_COUNT": 0,
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        "TIGHTENING_PRIORITY_ORDER": [*ROUTES, *LATER_ROUTES],
        "SOLVER_MODEL_SOURCE_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "MODULE_FILE": str(Path(__file__).resolve()),
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "RUNTIME_TRANSITION_OCCURRED": "NO",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solver-request")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.solver_request is not None:
        print(json.dumps(solver_child(_object(json.loads(arguments.solver_request)))))
        return
    if not str(Path(__file__).resolve()).startswith(WORKTREE_PATH + "/"):
        raise RuntimeError("module resolved outside the exact R24 worktree")
    result = compute_result()
    if arguments.output is not None:
        if arguments.output.resolve() != result_path():
            raise ValueError("output must be the exact R24 result path")
        arguments.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "FAMILY_UPPER_BOUND",
                    "CURRENT_BOUND_OWNER_SET",
                    "SOLVER_ROUTE_STATUSES",
                    "SOLVER_ACTUAL_WALL_TIME",
                    "REMAINING_GAP",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
