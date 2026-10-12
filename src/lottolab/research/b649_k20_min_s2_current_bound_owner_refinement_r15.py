"""Refine only the committed K20 S2 family-bound owner (R15).

The family ledger is reconstructed from the committed R11--R14 records.  The
solver is then restricted to the profile row that owns the current maximum;
the next ranked cursor is treated as a ceiling and is never sent to a solver.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from itertools import combinations
from math import ceil, comb
from pathlib import Path
from time import monotonic
from typing import Any, cast

from .b649_k20_min_s2_continued_multi_plateau_descent_r12 import (
    solver_runtime_preflight,
)
from .b649_k20_min_s2_dangerous_core_realizability_r5 import (
    K20_REUSED_S4_LOWER_BOUND,
    validate_k20_support_realization,
)
from .b649_k20_min_s2_higher_order_closure_r2 import (
    K20_S1,
    K20_S2,
    k20_min_s2_s4_lower_bound_certificate,
)
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import coarse_profile_envelope
from .b649_k20_min_s2_next_distinct_plateau_r10 import (
    _graph_triangle_count,  # pyright: ignore[reportPrivateUsage]
    _overlap_edges,  # pyright: ignore[reportPrivateUsage]
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_INCUMBENT,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_INCIDENCE_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
    s3_sum_from_wedges_and_triangles,
)

DegreeProfile = tuple[int, ...]
Triple = tuple[int, int, int]
Pair = tuple[int, int]

TASK_ID = "B649_K20_MIN_S2_CURRENT_BOUND_OWNER_REFINEMENT_R15"
BASE_HEAD = "32f53f78d6e4908586bc7437232e5e3c9180f63c"
BASE_TREE = "1af9ce9299a4e59338d7f0a8a7c574907d824028"
CURRENT_FAMILY_BOUND = 313_689_592
NEXT_CURSOR_BOUND = 313_675_592
INCUMBENT = K20_INCUMBENT
EXPECTED_RESOLVED_PROFILE_COUNT = 179
EXPECTED_OWNER_PROFILE: DegreeProfile = (
    6,
    6,
    6,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    5,
    1,
    1,
    1,
    0,
    0,
    0,
    0,
    0,
)
PROFILE_ROW_INDEX = 30
PROFILE_ROW_BOUND = 313_689_592
PROFILE_ROW_S3_BOUND = 5_299_616
PROFILE_ROW_S4_FLOOR = 112
PROFILE_ROW_TRIANGLE_BOUND = 275
NATIVE_S3_WALL_LIMIT_SECONDS = 90.0
EXTERNAL_HARD_TIMEOUT_SECONDS = 210
RESULT_FILENAME = "b649-k20-min-s2-current-bound-owner-refinement-r15-result.json"


@dataclass(frozen=True, slots=True)
class ProfileCertificate:
    """A profile-level row or a profile covered by a finite class certificate."""

    profile: DegreeProfile
    family_upper_bound: int
    certificate_source: str
    realizability: str
    s3_upper_bound: int | None = None
    s4_lower_bound: int | None = None
    graph_triangle_upper_bound: int | None = None
    support_solver_status: str = "NOT_APPLICABLE"
    row_index: int | None = None


@dataclass(frozen=True, slots=True)
class FamilyMaxLedger:
    """Reconstructed resolved-profile certificates and the unresolved cursor."""

    records: tuple[ProfileCertificate, ...]
    owner_profiles: tuple[ProfileCertificate, ...]
    family_upper_bound: int
    incumbent: int
    next_cursor_profile: DegreeProfile
    next_cursor_bound: int
    unresolved_suffix_bound: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_result(name: str) -> dict[str, object]:
    path = _repo_root() / "docs" / "research" / "matrix-native-results" / name
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"committed result {path} must be a JSON object")
    return cast(dict[str, object], value)


def _require_int(value: object, name: str) -> int:
    if type(value) is not int:
        raise AssertionError(f"{name} must be an integer")
    return value


def _require_float(value: object, name: str) -> float:
    if not isinstance(value, (int, float)):
        raise AssertionError(f"{name} must be numeric")
    return float(value)


def _profile(raw: object, *, name: str) -> DegreeProfile:
    if isinstance(raw, str):
        if len(raw) != K20_TICKET_COUNT or not raw.isdecimal():
            raise AssertionError(f"{name} must be a twenty-digit profile identity")
        values = tuple(int(value) for value in raw)
    elif isinstance(raw, list):
        values_raw = cast(list[object], raw)
        if len(values_raw) != K20_TICKET_COUNT or any(
            type(value) is not int for value in values_raw
        ):
            raise AssertionError(f"{name} must contain twenty integer degrees")
        values = tuple(cast(int, value) for value in values_raw)
    else:
        raise AssertionError(f"{name} must be a profile array or compact identity")
    if tuple(sorted(values, reverse=True)) != values:
        raise AssertionError(f"{name} must be nonincreasing")
    if any(not 0 <= degree <= K20_TICKET_CAPACITY for degree in values):
        raise AssertionError(f"{name} contains a degree outside 0..6")
    if sum(values) != K20_TRIPLE_INCIDENCE_COUNT:
        raise AssertionError(f"{name} must sum to 66")
    return values


def profile_identity(profile: DegreeProfile) -> str:
    return "".join(str(degree) for degree in profile)


def canonical_primitive_preflight() -> dict[str, int | str]:
    """Assert the packet-pinned single-ticket and K20 S1 values."""

    single_ticket_any_prize = K20_S1 // K20_TICKET_COUNT
    if (single_ticket_any_prize, K20_S1) != (18_611_432, 372_228_640):
        raise AssertionError("canonical S1 primitives changed")
    if single_ticket_any_prize * K20_TICKET_COUNT != K20_S1:
        raise AssertionError("single-ticket and K20 S1 values do not reconcile")
    return {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": single_ticket_any_prize,
        "K20_S1": K20_S1,
    }


def _profile_rows(
    result: dict[str, object], *, source: str, expected_count: int
) -> tuple[ProfileCertificate, ...]:
    raw_rows = result.get("PROFILE_BOUNDS")
    if not isinstance(raw_rows, list):
        raise AssertionError(f"{source} does not contain {expected_count} profile rows")
    rows = cast(list[object], raw_rows)
    if len(rows) != expected_count:
        raise AssertionError(f"{source} does not contain {expected_count} profile rows")
    records: list[ProfileCertificate] = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise AssertionError(f"{source} row {index} is malformed")
        row = cast(dict[str, object], raw)
        bound = _require_int(row.get("FAMILY_UPPER_BOUND"), f"{source}[{index}] bound")
        s3_raw = row.get("S3_UPPER_BOUND")
        s4_raw = row.get("S4_LOWER_BOUND")
        triangle_raw = row.get("GRAPH_TRIANGLE_UPPER_BOUND")
        rank_raw = row.get("RANK_INDEX")
        records.append(
            ProfileCertificate(
                profile=_profile(row.get("PROFILE"), name=f"{source}[{index}] profile"),
                family_upper_bound=bound,
                certificate_source=f"{source}.PROFILE_BOUNDS[{index}]",
                realizability=str(row.get("REALIZABILITY", "UNKNOWN")),
                s3_upper_bound=s3_raw if type(s3_raw) is int else None,
                s4_lower_bound=s4_raw if type(s4_raw) is int else None,
                graph_triangle_upper_bound=(triangle_raw if type(triangle_raw) is int else None),
                support_solver_status=str(row.get("SUPPORT_SOLVER_STATUS", "UNKNOWN")),
                row_index=rank_raw if type(rank_raw) is int else index,
            )
        )
    return tuple(records)


def _class_profile_records(
    certificate: dict[str, object], *, source: str, bound_field: str
) -> tuple[ProfileCertificate, ...]:
    identities = certificate.get("PROFILE_IDENTITIES")
    if not isinstance(identities, list):
        raise AssertionError(f"{source} lacks exact profile identities")
    bound = _require_int(certificate.get(bound_field), f"{source}.{bound_field}")
    return tuple(
        ProfileCertificate(
            profile=_profile(identity, name=f"{source} profile"),
            family_upper_bound=bound,
            certificate_source=source,
            realizability="CLASS_ENVELOPE_ONLY",
        )
        for identity in cast(list[object], identities)
    )


def reconstruct_family_max_ledger() -> FamilyMaxLedger:
    """Rebuild the R11--R14 ledger without profile enumeration or solver work."""

    r11 = _read_result("b649-k20-min-s2-budgeted-multi-plateau-descent-r11-result.json")
    r12 = _read_result("b649-k20-min-s2-continued-multi-plateau-descent-r12-result.json")
    r13 = _read_result("b649-k20-min-s2-class-dominance-or-descent-r13-result.json")
    r14 = _read_result("b649-k20-min-s2-successive-class-dominance-r14-result.json")

    if r11.get("TASK_STATUS") != "SUCCESS_C_PROFILE_CAP":
        raise AssertionError("R11 is not the committed profile-cap predecessor")
    if r12.get("TASK_STATUS") != "SUCCESS_C_PROFILE_CAP":
        raise AssertionError("R12 is not the committed profile-cap continuation")
    if r12.get("PRIOR_RESOLVED_PROFILE_COUNT") != 24:
        raise AssertionError("R12 does not extend the 24-profile R11 ledger")
    if r12.get("TOTAL_RESOLVED_PROFILE_COUNT") != 72:
        raise AssertionError("R12 does not report 72 resolved profiles")
    if r13.get("TOTAL_RESOLVED_PROFILE_COUNT") != 76:
        raise AssertionError("R13 does not report 76 resolved profiles")
    if r14.get("TASK_STATUS") != "SUCCESS_C_CLASS_DOMINANCE":
        raise AssertionError("R14 is not the committed current family handoff")
    if r14.get("TOTAL_RESOLVED_PROFILE_COUNT") != EXPECTED_RESOLVED_PROFILE_COUNT:
        raise AssertionError("R14 resolved-profile accounting changed")
    if r14.get("PRIOR_PROFILE_RERUN_COUNT") != 0:
        raise AssertionError("R14 reports a prior profile rerun")
    if r14.get("FULL_4850_PROFILE_CENSUS_REBUILT") is not False:
        raise AssertionError("R14 does not certify that the full profile census was skipped")

    records: list[ProfileCertificate] = [
        *_profile_rows(r11, source="R11", expected_count=24),
        *_profile_rows(r12, source="R12", expected_count=48),
    ]
    r13_certificate = r13.get("CLASS_DOMINANCE_CERTIFICATE")
    if not isinstance(r13_certificate, dict):
        raise AssertionError("R13 lacks its finite class certificate")
    records.extend(
        _class_profile_records(
            cast(dict[str, object], r13_certificate),
            source="R13.CLASS_DOMINANCE_CERTIFICATE",
            bound_field="CLASS_FAMILY_UPPER_BOUND",
        )
    )
    r14_certificates = r14.get("CLASS_CERTIFICATES")
    if not isinstance(r14_certificates, list):
        raise AssertionError("R14 lacks its finite class certificates")
    for index, raw_certificate in enumerate(cast(list[object], r14_certificates)):
        if not isinstance(raw_certificate, dict):
            raise AssertionError(f"R14 class certificate {index} is malformed")
        certificate = cast(dict[str, object], raw_certificate)
        square_sum = _require_int(certificate.get("SQUARE_SUM"), "R14 square sum")
        records.extend(
            _class_profile_records(
                certificate,
                source=f"R14.CLASS_CERTIFICATES[{index}].SQUARE_SUM={square_sum}",
                bound_field="CLASS_FAMILY_UPPER_BOUND",
            )
        )

    profiles = tuple(record.profile for record in records)
    if len(profiles) != EXPECTED_RESOLVED_PROFILE_COUNT:
        raise AssertionError("R11--R14 profile ledger has an unexpected size")
    if len(set(profiles)) != len(profiles):
        raise AssertionError("R11--R14 committed profile ledger contains duplicates")

    family_bound = max(record.family_upper_bound for record in records)
    if family_bound != CURRENT_FAMILY_BOUND:
        raise AssertionError("reconstructed family maximum disagrees with the packet")
    owners = tuple(record for record in records if record.family_upper_bound == family_bound)
    if not owners:
        raise AssertionError("family maximum has no profile owner")

    cursor = _profile(r14.get("NEXT_ACTIVE_PROFILE"), name="R14 next cursor")
    cursor_bound = _require_int(r14.get("NEXT_ACTIVE_BOUND"), "R14 next cursor bound")
    rank_lookup = r14.get("RANK_LOOKUP")
    if not isinstance(rank_lookup, dict):
        raise AssertionError("R14 lacks the ranked-frontier ledger")
    rank = cast(dict[str, object], rank_lookup)
    if r14.get("RANKED_FRONTIER_INVARIANT_STATUS") != "PASS":
        raise AssertionError("R14 ranked-frontier ordering was not certified")
    if rank.get("FULL_4850_PROFILE_CENSUS_REBUILT") is not False:
        raise AssertionError("R14 rebuilt the forbidden full profile census")
    if cursor_bound > NEXT_CURSOR_BOUND:
        raise AssertionError("an unresolved cursor exceeds the packet ceiling")
    if coarse_profile_envelope(cursor).family_upper_bound != cursor_bound:
        raise AssertionError("R14 cursor profile and cursor envelope disagree")

    return FamilyMaxLedger(
        records=tuple(records),
        owner_profiles=owners,
        family_upper_bound=family_bound,
        incumbent=_require_int(r14.get("INCUMBENT"), "R14 incumbent"),
        next_cursor_profile=cursor,
        next_cursor_bound=cursor_bound,
        unresolved_suffix_bound=cursor_bound,
    )


def assert_unresolved_suffix_bounded(ledger: FamilyMaxLedger) -> None:
    """Use R14's certified ranked cursor to bound every later unresolved row."""

    if ledger.unresolved_suffix_bound != ledger.next_cursor_bound:
        raise AssertionError("unresolved suffix bound differs from its first cursor")
    if ledger.unresolved_suffix_bound > NEXT_CURSOR_BOUND:
        raise AssertionError("an unresolved profile is above the packet cursor ceiling")


def assert_no_lower_cursor_work(
    ledger: FamilyMaxLedger,
    profiles_to_refine: Iterable[DegreeProfile],
    *,
    active_family_bound: int | None = None,
) -> None:
    """Allow only committed resolved profiles at the active family maximum."""

    requested = tuple(profiles_to_refine)
    bound = ledger.family_upper_bound if active_family_bound is None else active_family_bound
    resolved_by_profile = {record.profile: record for record in ledger.records}
    if not requested:
        raise AssertionError("the current family-bound owner set was not refined")
    if len(set(requested)) != len(requested):
        raise AssertionError("a profile was scheduled more than once")
    for profile in requested:
        record = resolved_by_profile.get(profile)
        if record is None or record.family_upper_bound != bound:
            raise AssertionError("lower-cursor or non-owner profile work is forbidden")
        if coarse_profile_envelope(profile).family_upper_bound <= ledger.next_cursor_bound:
            raise AssertionError("profile is at or below the unresolved cursor ceiling")


def _decode_support_rows(raw: object, *, support_size: int) -> tuple[tuple[int, ...], ...]:
    if isinstance(raw, str):
        if not raw:
            return ()
        rows: list[tuple[int, ...]] = []
        for encoded in raw.split(";"):
            values = tuple(int(value) for value in encoded.split(","))
            if len(values) != support_size:
                raise AssertionError("committed support witness row has the wrong arity")
            rows.append(values)
        return tuple(rows)
    if not isinstance(raw, list):
        raise AssertionError("committed support witness must use the R12 compact encoding")
    rows = []
    for raw_row in cast(list[object], raw):
        if not isinstance(raw_row, list):
            raise AssertionError("support witness row must be an array")
        values_raw = cast(list[object], raw_row)
        if len(values_raw) != support_size or any(type(value) is not int for value in values_raw):
            raise AssertionError("support witness row has the wrong arity or value type")
        rows.append(tuple(cast(int, value) for value in values_raw))
    return tuple(rows)


def _owner_source_row(owner: ProfileCertificate) -> dict[str, object]:
    source_parts = owner.certificate_source.split(".")
    if len(source_parts) != 2 or source_parts[1].startswith("CLASS_"):
        raise AssertionError("active owner has no exact committed profile row")
    source, row_designator = source_parts
    if not row_designator.startswith("PROFILE_BOUNDS[") or not row_designator.endswith("]"):
        raise AssertionError("active owner certificate source is not a profile row")
    row_index = int(row_designator[len("PROFILE_BOUNDS[") : -1])
    result_filename = {
        "R11": "b649-k20-min-s2-budgeted-multi-plateau-descent-r11-result.json",
        "R12": "b649-k20-min-s2-continued-multi-plateau-descent-r12-result.json",
    }.get(source)
    if result_filename is None:
        raise AssertionError("active owner source does not carry a reusable support witness")
    result = _read_result(result_filename)
    rows = cast(list[object], result["PROFILE_BOUNDS"])
    raw = rows[row_index]
    if not isinstance(raw, dict):
        raise AssertionError("the exact owner source row is malformed")
    row = cast(dict[str, object], raw)
    if _profile(row.get("PROFILE"), name="active owner source profile") != owner.profile:
        raise AssertionError("active owner source row no longer matches the profile ledger")
    if row.get("FAMILY_UPPER_BOUND") != owner.family_upper_bound:
        raise AssertionError("active owner source row no longer carries its ledger bound")
    if row.get("S3_UPPER_BOUND") != owner.s3_upper_bound:
        raise AssertionError("active owner S3 envelope changed")
    if row.get("S4_LOWER_BOUND") != owner.s4_lower_bound:
        raise AssertionError("active owner S4 envelope changed")
    if row.get("GRAPH_TRIANGLE_UPPER_BOUND") != owner.graph_triangle_upper_bound:
        raise AssertionError("active owner triangle ceiling changed")
    if row.get("REALIZABILITY") != "REALIZABLE" or row.get("SUPPORT_SOLVER_STATUS") != "OPTIMAL":
        raise AssertionError("the committed active owner witness is not proven realizable")
    return row


def _owner_support_witness(
    row: dict[str, object], profile: DegreeProfile
) -> tuple[tuple[Triple, ...], tuple[Pair, ...]]:
    triples = cast(
        tuple[Triple, ...], _decode_support_rows(row.get("WITNESS_TRIPLES"), support_size=3)
    )
    doubles = cast(
        tuple[Pair, ...], _decode_support_rows(row.get("WITNESS_DOUBLE_SUPPORTS"), support_size=2)
    )
    signature = validate_k20_support_realization(triples, doubles, profile)
    if asdict(signature) != row.get("WITNESS_MOTIFS"):
        raise AssertionError("the committed owner support witness signature changed")
    return triples, doubles


def _configured_solver(wall_limit_seconds: float) -> Any:
    from ortools.sat.python import cp_model

    solver: Any = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = wall_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 649
    solver.parameters.symmetry_level = 2
    solver.parameters.log_search_progress = False
    return solver


def _status_name(solver: Any, status_code: int) -> str:
    return str(solver.StatusName(status_code))


def _s3_upper_bound(
    profile: DegreeProfile,
    triples: Sequence[Triple],
    doubles: Sequence[Pair],
    previous_triangle_upper_bound: int,
) -> dict[str, object]:
    from ortools.sat.python import cp_model

    complement_degrees = tuple(K20_TICKET_COUNT - 1 - (6 + degree) for degree in profile)
    model: Any = cp_model.CpModel()
    edge_vars: dict[Pair, Any] = {
        pair: model.NewBoolVar(f"complement_edge_{pair[0]}_{pair[1]}")
        for pair in combinations(range(K20_TICKET_COUNT), 2)
    }
    for vertex, degree in enumerate(complement_degrees):
        incident = [
            variable
            for pair, variable in edge_vars.items()
            if vertex in pair
        ]
        model.Add(sum(incident) == degree)

    triangle_vars: dict[Triple, Any] = {}
    for triangle in combinations(range(K20_TICKET_COUNT), 3):
        variable = model.NewBoolVar(
            f"complement_triangle_{triangle[0]}_{triangle[1]}_{triangle[2]}"
        )
        triangle_edges = tuple(
            edge_vars[(min(first, second), max(first, second))]
            for first, second in combinations(triangle, 2)
        )
        for edge in triangle_edges:
            model.Add(variable <= edge)
        model.Add(variable >= sum(triangle_edges) - 2)
        triangle_vars[triangle] = variable

    support_edges = _overlap_edges(triples, doubles)
    complement_edges = {
        pair for pair in edge_vars if pair not in support_edges
    }
    for pair, variable in edge_vars.items():
        model.AddHint(variable, int(pair in complement_edges))
    for triangle, variable in triangle_vars.items():
        model.AddHint(
            variable,
            int(all(pair in complement_edges for pair in combinations(triangle, 2))),
        )

    # For an edge uv, |N(u) intersect N(v)| >= max(0, d(u)+d(v)-n).
    # Summing these pair and vertex inequalities supplies valid integer cuts.
    triangle_count = sum(triangle_vars.values())
    pair_codegree_floor = sum(
        max(0, complement_degrees[first] + complement_degrees[second] - K20_TICKET_COUNT)
        * edge_vars[first, second]
        for first, second in edge_vars
    )
    model.Add(3 * triangle_count >= pair_codegree_floor)
    for vertex in range(K20_TICKET_COUNT):
        incident_triangles = [
            variable for triangle, variable in triangle_vars.items() if vertex in triangle
        ]
        local_codegree_floor = sum(
            max(0, complement_degrees[vertex] + complement_degrees[other] - K20_TICKET_COUNT)
            * edge_vars[min(vertex, other), max(vertex, other)]
            for other in range(K20_TICKET_COUNT)
            if other != vertex
        )
        model.Add(2 * sum(incident_triangles) >= local_codegree_floor)
    model.Minimize(triangle_count)

    solver = _configured_solver(NATIVE_S3_WALL_LIMIT_SECONDS)
    status_code = solver.Solve(model)
    status = _status_name(solver, status_code)
    if status not in {"OPTIMAL", "FEASIBLE"}:
        raise RuntimeError(f"owner complement triangle bound failed with status {status}")
    incumbent = round(float(solver.ObjectiveValue()))
    triangle_floor = (
        incumbent
        if status == "OPTIMAL"
        else ceil(float(solver.BestObjectiveBound()))
    )
    if triangle_floor > incumbent:
        raise AssertionError("complement triangle lower bound exceeds its feasible witness")
    complement_edge_count = sum(complement_degrees) // 2
    complement_wedge_count = sum(comb(degree, 2) for degree in complement_degrees)
    graph_triangle_constant = (
        comb(K20_TICKET_COUNT, 3)
        - complement_edge_count * (K20_TICKET_COUNT - 2)
        + complement_wedge_count
    )
    graph_triangle_upper = graph_triangle_constant - triangle_floor
    old_graph_triangles = _graph_triangle_count(support_edges)
    complement_witness_triangles = _graph_triangle_count(frozenset(complement_edges))
    expected_constant = (
        comb(K20_TICKET_COUNT, 3)
        - complement_edge_count * (K20_TICKET_COUNT - 2)
        + complement_wedge_count
    )
    if graph_triangle_constant != expected_constant:
        raise AssertionError("complement graph degree identity is inconsistent")
    if old_graph_triangles + complement_witness_triangles != graph_triangle_constant:
        raise AssertionError("reused support witness failed complement triangle identity")
    if graph_triangle_upper > previous_triangle_upper_bound:
        raise AssertionError("the complement relaxation weakened the prior triangle cap")
    return {
        "STATUS": status,
        "CERTIFICATE_KIND": (
            "OPTIMAL_OBJECTIVE"
            if status == "OPTIMAL"
            else "CP_SAT_BEST_OBJECTIVE_LOWER_BOUND"
        ),
        "RELAXATION": "COMPLEMENT_SIMPLE_GRAPH_FIXED_DEGREES",
        "COMPLEMENT_DEGREES": list(complement_degrees),
        "COMPLEMENT_TRIANGLE_INCUMBENT": incumbent,
        "COMPLEMENT_TRIANGLE_CERTIFIED_LOWER_BOUND": triangle_floor,
        "GRAPH_TRIANGLE_UPPER_BOUND": graph_triangle_upper,
        "GRAPH_TRIANGLE_IDENTITY_CONSTANT": graph_triangle_constant,
        "COMPLEMENT_EDGE_COUNT": complement_edge_count,
        "COMPLEMENT_WEDGE_COUNT": complement_wedge_count,
        "REUSED_SUPPORT_WITNESS_GRAPH_TRIANGLES": old_graph_triangles,
        "REUSED_SUPPORT_WITNESS_COMPLEMENT_TRIANGLES": complement_witness_triangles,
        "PAIR_AND_VERTEX_CODEGREE_CUTS": "APPLIED",
        "SOLVER_WALL_TIME_SECONDS": float(solver.WallTime()),
    }


def _s4_lower_bound_for_s3_maximizers() -> dict[str, object]:
    certificate = k20_min_s2_s4_lower_bound_certificate()
    if certificate.s4_lower_bound != K20_REUSED_S4_LOWER_BOUND:
        raise AssertionError("the reused S4 certificate changed")
    return {
        "STATUS": "CERTIFIED_UNIVERSAL_FLOOR",
        "CERTIFIED_LOWER_BOUND": certificate.s4_lower_bound,
        "EXACT_PROFILE_SPECIFIC_MINIMUM": "NOT_COMPUTED",
        "APPLIES_TO_S3_MAXIMIZERS": True,
        "CERTIFICATE_SOURCE": "R2 triple-core contradiction certificate",
        "CERTIFICATE": asdict(certificate),
    }


def _reuse_prior_r15_s3_certificate(
    owner: ProfileCertificate,
) -> tuple[dict[str, object], float] | None:
    """Reuse the earlier R15 owner proof when its profile and ledger row match."""

    prior = _read_result(RESULT_FILENAME)
    if prior.get("TASK_ID") != TASK_ID or prior.get("BASE_HEAD") != BASE_HEAD:
        return None
    raw_owners = prior.get("OWNER_PROFILE_BOUNDS")
    if not isinstance(raw_owners, list):
        return None
    candidates: list[dict[str, object]] = []
    for raw in cast(list[object], raw_owners):
        if not isinstance(raw, dict):
            continue
        candidate = cast(dict[str, object], raw)
        if candidate.get("PROFILE") == profile_identity(owner.profile):
            candidates.append(candidate)
    if len(candidates) != 1:
        return None
    cached_owner = candidates[0]
    if (
        cached_owner.get("CERTIFICATE_SOURCE") != owner.certificate_source
        or cached_owner.get("ORIGINAL_FAMILY_UPPER_BOUND") != owner.family_upper_bound
        or cached_owner.get("REALIZABILITY") != "REALIZABLE"
        or cached_owner.get("SUPPORT_SOLVER_STATUS") != "OPTIMAL"
    ):
        return None
    raw_certificate = cached_owner.get("S3_CERTIFICATE")
    if not isinstance(raw_certificate, dict):
        return None
    certificate = cast(dict[str, object], raw_certificate)
    complement_degrees_raw = certificate.get("COMPLEMENT_DEGREES")
    if not isinstance(complement_degrees_raw, list):
        raise AssertionError("cached S3 certificate lacks complement degrees")
    complement_degrees = tuple(cast(list[int], complement_degrees_raw))
    expected_degrees = tuple(13 - degree for degree in owner.profile)
    if complement_degrees != expected_degrees:
        raise AssertionError("cached S3 certificate uses a different complement profile")
    complement_edge_count = sum(complement_degrees) // 2
    complement_wedge_count = sum(comb(degree, 2) for degree in complement_degrees)
    identity_constant = (
        comb(K20_TICKET_COUNT, 3)
        - complement_edge_count * (K20_TICKET_COUNT - 2)
        + complement_wedge_count
    )
    triangle_floor = _require_int(
        certificate.get("COMPLEMENT_TRIANGLE_CERTIFIED_LOWER_BOUND"),
        "cached complement triangle lower bound",
    )
    graph_triangle_upper = _require_int(
        certificate.get("GRAPH_TRIANGLE_UPPER_BOUND"), "cached graph triangle upper bound"
    )
    if certificate.get("CERTIFICATE_KIND") != "CP_SAT_BEST_OBJECTIVE_LOWER_BOUND":
        raise AssertionError("cached S3 certificate does not use a certified solver bound")
    if certificate.get("GRAPH_TRIANGLE_IDENTITY_CONSTANT") != identity_constant:
        raise AssertionError("cached S3 certificate triangle identity changed")
    if graph_triangle_upper != identity_constant - triangle_floor:
        raise AssertionError("cached S3 certificate does not reconcile its certified bound")
    previous_triangle_upper = owner.graph_triangle_upper_bound
    if previous_triangle_upper is None:
        raise AssertionError("cached owner has no prior graph triangle ceiling")
    if graph_triangle_upper > previous_triangle_upper:
        raise AssertionError("cached S3 certificate weakens the committed owner cap")
    witness_graph_triangles = _require_int(
        certificate.get("REUSED_SUPPORT_WITNESS_GRAPH_TRIANGLES"),
        "cached witness graph triangles",
    )
    witness_complement_triangles = _require_int(
        certificate.get("REUSED_SUPPORT_WITNESS_COMPLEMENT_TRIANGLES"),
        "cached witness complement triangles",
    )
    if witness_graph_triangles + witness_complement_triangles != identity_constant:
        raise AssertionError("cached support witness fails the complement identity")
    wedge_count = overlap_wedge_count(owner.profile)
    s3_upper = s3_sum_from_wedges_and_triangles(
        wedge_count, graph_triangle_upper - K20_TRIPLE_SUPPORT_COUNT
    )
    if cached_owner.get("REFINED_S3_UPPER_BOUND") != s3_upper:
        raise AssertionError("cached S3 sum does not reconcile to its graph bound")
    cached_family_bound = _require_int(
        cached_owner.get("FAMILY_UPPER_BOUND"), "cached owner family bound"
    )
    if cached_family_bound > owner.family_upper_bound:
        raise AssertionError("cached owner refinement exceeds its prior family bound")
    cached_elapsed = cached_owner.get("SOLVER_ACTUAL_WALL_TIME_SECONDS")
    elapsed = (
        _require_float(cached_elapsed, "cached owner elapsed wall")
        if isinstance(cached_elapsed, (int, float))
        else _require_float(prior.get("SOLVER_ACTUAL_WALL_TIME_SECONDS"), "cached R15 elapsed wall")
    )
    return certificate, elapsed


def compute_owner_refinement_result() -> dict[str, object]:
    """Prove the owner-only S3/S4 refinement and recompute the family maximum."""

    started = monotonic()
    primitives = canonical_primitive_preflight()
    ledger = reconstruct_family_max_ledger()
    assert_unresolved_suffix_bounded(ledger)
    # Runtime/version and hard-timeout capability are checked before model creation.
    runtime = solver_runtime_preflight()
    initial_owner_profiles = tuple(owner.profile for owner in ledger.owner_profiles)
    bound_overrides: dict[DegreeProfile, int] = {}
    refinement_by_profile: dict[DegreeProfile, dict[str, object]] = {}
    solver_statuses: list[str] = []

    while True:
        effective_bounds = [
            bound_overrides.get(record.profile, record.family_upper_bound)
            for record in ledger.records
        ]
        family_bound = max([*effective_bounds, ledger.unresolved_suffix_bound])
        if family_bound <= ledger.incumbent or family_bound <= ledger.next_cursor_bound:
            break

        active_owners = tuple(
            record
            for record in ledger.records
            if bound_overrides.get(record.profile, record.family_upper_bound) == family_bound
        )
        active_profiles = tuple(owner.profile for owner in active_owners)
        assert_no_lower_cursor_work(
            ledger, active_profiles, active_family_bound=family_bound
        )
        new_owners = tuple(
            owner for owner in active_owners if owner.profile not in refinement_by_profile
        )
        if len(new_owners) != len(active_owners):
            raise AssertionError("an already-refined profile remains at the active family maximum")

        for owner in new_owners:
            owner_row = _owner_source_row(owner)
            support_triples, support_doubles = _owner_support_witness(owner_row, owner.profile)
            if owner.graph_triangle_upper_bound is None:
                raise AssertionError("active profile row has no prior graph triangle ceiling")
            reused_s3 = _reuse_prior_r15_s3_certificate(owner)
            solver_started = monotonic()
            if reused_s3 is None:
                s3_result = _s3_upper_bound(
                    owner.profile,
                    support_triples,
                    support_doubles,
                    owner.graph_triangle_upper_bound,
                )
                owner_solver_elapsed = monotonic() - solver_started
            else:
                s3_result, owner_solver_elapsed = reused_s3
            solver_statuses.append(str(s3_result["STATUS"]))
            graph_triangle_upper = _require_int(
                s3_result.get("GRAPH_TRIANGLE_UPPER_BOUND"), "graph triangle upper bound"
            )
            s4_result = _s4_lower_bound_for_s3_maximizers()
            wedge_count = overlap_wedge_count(owner.profile)
            s3_upper = s3_sum_from_wedges_and_triangles(
                wedge_count, graph_triangle_upper - K20_TRIPLE_SUPPORT_COUNT
            )
            s4_floor = _require_int(
                s4_result.get("CERTIFIED_LOWER_BOUND"), "S4 lower bound"
            )
            fourth_order_credit = (4 * s4_floor) // 7
            owner_bound = K20_S1 - K20_S2 + s3_upper - fourth_order_credit
            if owner_bound > owner.family_upper_bound:
                raise AssertionError("owner refinement weakened the committed envelope")
            bound_overrides[owner.profile] = owner_bound
            refinement_by_profile[owner.profile] = {
                "PROFILE": profile_identity(owner.profile),
                "DEGREE_PROFILE": list(owner.profile),
                "CERTIFICATE_SOURCE": owner.certificate_source,
                "REALIZABILITY": owner.realizability,
                "SUPPORT_SOLVER_STATUS": owner.support_solver_status,
                "ORIGINAL_GRAPH_TRIANGLE_UPPER_BOUND": owner.graph_triangle_upper_bound,
                "ORIGINAL_S3_UPPER_BOUND": owner.s3_upper_bound,
                "ORIGINAL_S4_LOWER_BOUND": owner.s4_lower_bound,
                "ORIGINAL_FAMILY_UPPER_BOUND": owner.family_upper_bound,
                "SUPPORT_WITNESS_SOURCE": owner.certificate_source,
                "REFINED_GRAPH_TRIANGLE_UPPER_BOUND": graph_triangle_upper,
                "REFINED_S3_UPPER_BOUND": s3_upper,
                "S4_LOWER_BOUND_AT_S3_MAXIMIZERS": s4_floor,
                "EXACT_PROFILE_SPECIFIC_S4_MINIMUM": "NOT_COMPUTED",
                "FOURTH_ORDER_CREDIT": fourth_order_credit,
                "FAMILY_UPPER_BOUND": owner_bound,
                "SOLVER_ACTUAL_WALL_TIME_SECONDS": owner_solver_elapsed,
                "S3_CERTIFICATE_REUSED_FROM_PRIOR_R15_RESULT": reused_s3 is not None,
                "S3_CERTIFICATE": s3_result,
                "S4_CERTIFICATE": s4_result,
            }

    family_bound = max(
        [
            bound_overrides.get(record.profile, record.family_upper_bound)
            for record in ledger.records
        ]
        + [ledger.unresolved_suffix_bound]
    )
    family_status = (
        "CLOSED"
        if family_bound <= ledger.incumbent
        else "CURRENT_OWNER_ELIMINATED_CURSOR_LOAD_BEARING"
        if family_bound <= ledger.next_cursor_bound
        else "OPEN_STRICTLY_TIGHTENED"
    )
    if family_bound > ledger.family_upper_bound:
        raise AssertionError("refined family maximum exceeds the committed maximum")
    if family_bound > ledger.next_cursor_bound:
        raise AssertionError("owner refinement did not reach the cursor stop threshold")

    if solver_statuses and all(status == "OPTIMAL" for status in solver_statuses):
        overall_solver_status = "OPTIMAL"
    elif solver_statuses and all(status in {"OPTIMAL", "FEASIBLE"} for status in solver_statuses):
        overall_solver_status = "FEASIBLE"
    else:
        overall_solver_status = "FAILED"
    refined_owners = tuple(refinement_by_profile.values())
    if not refined_owners:
        raise AssertionError("no current bound owner received a refinement")

    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": (
            "SUCCESS_A_FAMILY_CLOSED"
            if family_status == "CLOSED"
            else "SUCCESS_B_CURSOR_LOAD_BEARING"
            if family_status == "CURRENT_OWNER_ELIMINATED_CURSOR_LOAD_BEARING"
            else "SUCCESS_B_OWNER_STRICTLY_TIGHTENED"
        ),
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "CURRENT_BOUND_OWNER_PROFILE_COUNT": len(ledger.owner_profiles),
        "CURRENT_BOUND_OWNER_PROFILES": [
            profile_identity(profile) for profile in initial_owner_profiles
        ],
        "REFINED_LOAD_BEARING_PROFILE_COUNT": len(refined_owners),
        "REFINED_LOAD_BEARING_PROFILES": [
            item["PROFILE"] for item in refined_owners
        ],
        "OWNER_PROFILE_BOUNDS": list(refined_owners),
        "RESOLVED_PROFILE_LEDGER_COUNT": len(ledger.records),
        "UNRESOLVED_SUFFIX_BOUND": ledger.unresolved_suffix_bound,
        "UNRESOLVED_SUFFIX_BOUND_STATUS": "PASS",
        "NEXT_CURSOR_PROFILE": profile_identity(ledger.next_cursor_profile),
        "NEXT_CURSOR_BOUND": ledger.next_cursor_bound,
        "LOWER_CURSOR_PROFILE_SOLVES": 0,
        "NO_LOWER_CURSOR_WORK_STATUS": "PASS",
        "FAMILY_UPPER_BOUND": family_bound,
        "INCUMBENT": ledger.incumbent,
        "REMAINING_GAP": max(0, family_bound - ledger.incumbent),
        "FAMILY_STATUS": family_status,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "CANONICAL_PRIMITIVES": primitives,
        "SOLVER_STATUS": overall_solver_status,
        "SOLVER_STATUS_BY_PROFILE": {
            cast(str, item["PROFILE"]): cast(dict[str, object], item["S3_CERTIFICATE"])["STATUS"]
            for item in refined_owners
        },
        "SOLVER_CERTIFICATE_KIND": "CP_SAT_BEST_OBJECTIVE_LOWER_BOUND",
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "NATIVE_S3_BOUND_WALL_SECONDS": NATIVE_S3_WALL_LIMIT_SECONDS,
            "EXTERNAL_HARD_TIMEOUT_SECONDS": EXTERNAL_HARD_TIMEOUT_SECONDS,
            "WORKERS": 1,
        },
        "SOLVER_ACTUAL_WALL_TIME_SECONDS": sum(
            cast(float, item["SOLVER_ACTUAL_WALL_TIME_SECONDS"])
            for item in refined_owners
        ),
        "SOLVER_ACTUAL_THIS_INVOCATION_WALL_TIME_SECONDS": monotonic() - started,
        "SOLVER_ATTEMPT_HISTORY": [
            {
                "ATTEMPT": "SUPPORT_MOTIF_MAXIMIZATION_EXPERIMENT",
                "STATUS": "FEASIBLE_LOOSE_BOUND",
                "NATIVE_CONFIGURED_WALL_LIMIT_SECONDS": 90,
                "EXTERNAL_HARD_TIMEOUT_SECONDS": 210,
                "INCUMBENT_OBJECTIVE": 234,
                "BEST_OBJECTIVE_BOUND": 407,
                "USED_FOR_FAMILY_PROOF": False,
            },
            {
                "ATTEMPT": "SECOND_OWNER_COMPLEMENT_MODEL_PILOT",
                "PROFILE": "66666555554421000000",
                "STATUS": "ABORTED_AFTER_IDENTITY_ASSERTION",
                "NATIVE_CONFIGURED_WALL_LIMIT_SECONDS": 25,
                "EXTERNAL_HARD_TIMEOUT_SECONDS": 40,
                "CERTIFIED_BOUND": None,
                "USED_FOR_FAMILY_PROOF": False,
            },
        ],
        "SOLVER_CUMULATIVE_OWNER_WALL_TIME_SECONDS": sum(
            cast(float, item["SOLVER_ACTUAL_WALL_TIME_SECONDS"])
            for item in refined_owners
        ),
        "SOLVER_ACTUAL_NATIVE_WALL_SECONDS_BY_PROFILE": {
            cast(str, item["PROFILE"]): _require_float(
                cast(dict[str, object], item["S3_CERTIFICATE"]).get("SOLVER_WALL_TIME_SECONDS"),
                "S3 native wall",
            )
            for item in refined_owners
        },
        "SOLVER_CERTIFIED_BOUND": family_bound,
        "S3_MAXIMIZATION_BY_PROFILE": {
            cast(str, item["PROFILE"]): item["S3_CERTIFICATE"] for item in refined_owners
        },
        "S4_MINIMIZATION_AT_S3_MAXIMIZERS_BY_PROFILE": {
            cast(str, item["PROFILE"]): item["S4_CERTIFICATE"] for item in refined_owners
        },
        "FULL_4850_PROFILE_CENSUS_REBUILT": False,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-result", required=True)
    args = parser.parse_args()
    result = compute_owner_refinement_result()
    output_path = Path(args.write_result)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    summary = {
        key: result[key]
        for key in (
            "TASK_STATUS",
            "CURRENT_BOUND_OWNER_PROFILE_COUNT",
            "CURRENT_BOUND_OWNER_PROFILES",
            "OWNER_PROFILE_BOUNDS",
            "NEXT_CURSOR_BOUND",
            "FAMILY_UPPER_BOUND",
            "INCUMBENT",
            "REMAINING_GAP",
            "FAMILY_STATUS",
            "SOLVER_STATUS",
            "SOLVER_ACTUAL_WALL_TIME_SECONDS",
            "SOLVER_CERTIFIED_BOUND",
        )
    }
    print(json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
