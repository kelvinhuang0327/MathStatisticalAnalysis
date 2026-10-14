"""Selected-submultiset Hunter certificates for 106 compressed R3 members.

The immutable H0-70 result supplies the current bounds. For each represented
vector, choose its full multiset or delete one event; no optimal subset search
is needed. Every selected multiset receives independently checked exact pair
rows, balanced collision floors in all four anchor cells, and the complete
integer nested-threshold minimum. Descending Kruskal spans each threshold
graph. Its rank is at least rho(e), since e <= sum C(r_j+1,2) <= C(sum r_j+1,2).
The resulting tree extends to all eighteen residual events with nonnegative
intersection weights. On any outcome a tree induces at most k-1 edges on its
k present vertices, proving Hunter's union inequality pointwise. Combine
valid credits by MAX once, then take MAX over every compressed member's
represented vectors. Witnesses demonstrate legality, not universality.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from functools import cache
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_three_state_h0_seventy_member_certificate_r1 as h0

hunter, catalog, six, r24 = h0.hunter, h0.catalog, h0.six, h0.r24
primary = h0.joint.primary
LedgerMember = catalog.LedgerMember
type CountVector = tuple[int, ...]
type Cells = tuple[int, int, int, int]
type PairRow = tuple[int, int, int, int, int, int, int]
dense, sparse, digest, member_id = h0.dense, h0.sparse, h0.digest, h0.member_id
TASK_ID = "B649_K20_R3_THREE_STATE_TS_106_MEMBER_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-three-state-ts-106-member-certificate-r1"
BASE_HEAD = "93f7adf46a8ad08d1ec75a586f538f8814cc3cea"
BASE_TREE = "026f4bf985a474223270e38c35ca8a1652edf737"
BASE_RESULT_SHA256 = "993e1463a601bb6b36434c1096377e46d78ab2e00c5cc2c623a9c696e5d056ef"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = six.RESULTS + "b649-k20-r3-three-state-ts-106-member-certificate-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
TARGET_CUTOFF = 355274920
REGION_SPECS = {
    h0.joint.TARGET_STATE_ID: (1222, 1325, 33, 37, h0.joint.REGION_SHA256, 355243049),
    primary.TARGET_STATE_ID: (989, 1072, 35, 39, primary.REGION_SHA256, 355274108),
    h0.s135.TARGET_STATE_ID: (1427, 1543, 38, 40, h0.s135.REGION_SHA256, 355269698),
}
RESIDUAL_EVENT_DEFINITION = h0.RESIDUAL_EVENT_DEFINITION
CORRECTION_COMBINATION = "MAX(EXISTING_VALID_CREDITS, SELECTED_SUBMULTISET_HUNTER)"


def source_paths() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *h0.source_paths(),
                str(Path(h0.__file__).resolve().relative_to(REPO_ROOT)),
                h0.RESULT_RELATIVE,
                primary.RESULT_RELATIVE,
            }
        )
    )


def verify_source_authority() -> dict[str, Any]:
    """Check immutable Git objects and executing bytes even with warm caches."""
    prefix = ["git", "-C", str(REPO_ROOT)]
    observed = subprocess.check_output(
        [*prefix, "show", "-s", "--format=%H %T", BASE_HEAD], text=True
    ).strip()
    blob = subprocess.check_output([*prefix, "show", f"{BASE_HEAD}:{h0.RESULT_RELATIVE}"])
    if observed != f"{BASE_HEAD} {BASE_TREE}" or sha256(blob).hexdigest() != BASE_RESULT_SHA256:
        raise AssertionError("immutable BASE_HEAD/TREE/result SHA authority failed")
    if subprocess.run([*prefix, "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"]).returncode:
        raise AssertionError("checkout does not descend from the immutable base")
    fingerprints: dict[str, str] = {}
    for path in source_paths():
        immutable = subprocess.check_output([*prefix, "show", f"{BASE_HEAD}:{path}"])
        if (REPO_ROOT / path).read_bytes() != immutable:
            raise AssertionError(f"immutable executing source or sealed input changed: {path}")
        fingerprints[path] = sha256(immutable).hexdigest()
    return {
        "HEAD": BASE_HEAD,
        "TREE": BASE_TREE,
        "RESULT_SHA256": BASE_RESULT_SHA256,
        "upstream_sha256": fingerprints,
    }


@cache
def source_results() -> dict[str, dict[str, Any]]:
    """Adopt sealed predecessors unchanged; do not rebuild a census or certificate."""
    verify_source_authority()
    results = {
        name: cast(dict[str, Any], json.loads(module.RESULT_PATH.read_bytes()))
        for name, module in (("H0", h0), ("PRIMARY", primary), ("JOINT", h0.joint))
    }
    source = results["H0"]
    if (
        source["TASK_ID"] != h0.TASK_ID
        or source["FINAL_COMPLETE_R3_UB"] != 355368426
        or source["TARGET_MEMBER_COUNT"] != 70
        or source["TARGET_VECTOR_COUNT"] != 70
    ):
        raise AssertionError("immutable H0 predecessor identity failed")
    return results


def region_rows(state_id: str) -> list[dict[str, Any]]:
    if state_id == primary.TARGET_STATE_ID:
        return cast(list[dict[str, Any]], source_results()["PRIMARY"]["COMPLETE_REGION_MEMBERS"])
    return cast(
        list[dict[str, Any]],
        next(
            r["complete_region_members"]
            for r in source_results()["H0"]["REGIONS"]
            if r["state_id"] == state_id
        ),
    )


@cache
def region_members(state_id: str) -> tuple[LedgerMember, ...]:
    members = tuple(
        LedgerMember(
            dense(r["witness_counts"]),
            int(r["represented_vector_count"]),
            int(r["raw_bound"]),
            int(r["final_bound"]),
        )
        for r in region_rows(state_id)
    )
    mc, vc, _, _, fingerprint, _ = REGION_SPECS[state_id]
    terms = {r["stable_id"]: r["bound"] for r in source_results()["H0"]["FINAL_STATE_TERMS"]}
    if (
        len(members) != mc
        or len({m.counts for m in members}) != mc
        or sum(m.represented_vector_count for m in members) != vc
        or catalog.region_fingerprint(members) != fingerprint
        or max(m.final_bound for m in members) != terms[state_id]
        or any(m.final_bound > m.raw_bound for m in members)
    ):
        raise AssertionError("complete immutable region identity failed")
    return members


def target_members(state_id: str) -> tuple[LedgerMember, ...]:
    targets = tuple(m for m in region_members(state_id) if m.final_bound > TARGET_CUTOFF)
    if (len(targets), sum(m.represented_vector_count for m in targets)) != REGION_SPECS[state_id][
        2:4
    ]:
        raise AssertionError("exact 106-member/116-vector target coverage failed")
    return targets


@cache
def represented_vectors(state_id: str) -> dict[CountVector, tuple[CountVector, ...]]:
    members = region_members(state_id)
    recovered: dict[CountVector, tuple[CountVector, ...]] = {}
    for m, row in zip(members, region_rows(state_id), strict=True):
        vectors = tuple(dense(v) for v in row["represented_vectors"])
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(m))
        if (
            len(vectors) != m.represented_vector_count
            or vectors != tuple(sorted(vectors))
            or min(vectors) != m.counts
        ):
            raise AssertionError("immutable compression cardinality or canonical vector failed")
        for v in vectors:
            rebuilt = catalog.rebuild_member(replace(m, counts=v, represented_vector_count=1))
            if (
                len(v) != 30
                or min(v) < 0
                or sum(v) != 18
                or hunter.eleven.compression_signature(rebuilt) != signature
            ):
                raise AssertionError("represented-vector compression signature failed")
        recovered[m.counts] = vectors
    flat = [v for vs in recovered.values() for v in vs]
    if len(flat) != len(set(flat)) or len(flat) != REGION_SPECS[state_id][1]:
        raise AssertionError("complete represented-vector coverage failed")
    # Recover exactly the selected losses/signatures, never the R7 census.
    targets = target_members(state_id)
    independent = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in targets))
    if independent != {m.counts: recovered[m.counts] for m in targets}:
        raise AssertionError("independent target compressed-vector reconstruction failed")
    return recovered


@cache
def verified_pair_rows(pair: tuple[int, int]) -> tuple[PairRow, ...]:
    rows = hunter.exact_pair_rows((pair,))
    for row in rows:
        cells = cast(Cells, tuple(row[2:6]))
        left, right = hunter.realize_pair(
            hunter.type_cells(pair[0]), hunter.type_cells(pair[1]), cells
        )
        if (
            tuple(len(left & right & set(c)) for c in hunter.CELL_LABELS) != cells
            or six.residual_pair_intersection(*pair, cells) != row[6]
            or row[6] < 0
        ):
            raise AssertionError("exact type-pair realization or residual intersection failed")
    return rows


def pair_rows(u: CountVector) -> tuple[PairRow, ...]:
    return tuple(
        row for pair in hunter.occupied_type_pairs((u,)) for row in verified_pair_rows(pair)
    )


@cache
def subset_parameters(u: CountVector) -> tuple[tuple[PairRow, ...], Cells, Cells, Cells]:
    if len(u) != 30 or any(type(c) is not int or c < 0 for c in u) or not 2 <= sum(u) <= 18:
        raise AssertionError("selected subset requires integer counts and 2..18 events")
    rows = pair_rows(u)
    phi = cast(Cells, tuple(min(r[6] for r in rows if sum(r[2:6]) == k) for k in range(4)))
    hunter.require_safe_pair_floors(phi, rows)
    if phi != hunter.pair_floors(rows):
        raise AssertionError("exact residual pair floor failed")
    incidences = cast(
        Cells, tuple(sum(c * hunter.type_cells(i)[k] for i, c in enumerate(u)) for k in range(4))
    )
    floors: list[int] = []
    for total, labels in zip(incidences, hunter.CELL_LABELS, strict=True):
        q, r = divmod(total, len(labels))
        floors.append((len(labels) - r) * comb(q, 2) + r * comb(q + 1, 2))
    collision = cast(Cells, tuple(floors))
    if (
        incidences != hunter.cell_incidences(u)
        or collision != hunter.cell_collision_floors(incidences)
        or sum(collision) > 3 * comb(sum(u), 2)
    ):
        raise AssertionError("balanced cell collision lower bound failed")
    return rows, phi, incidences, collision


@cache
def rank_minimum(phi: Cells, q: int, n: int) -> int:
    """A cheap selection rule, checked by complete edge-triple enumeration below.

    For ranks a>=b>=c, the largest realizable edge counts are C(a+1,2),
    C(b+1,2), C(c+1,2). Their sum >=Q is exactly rank-triple feasibility.
    """
    return min(
        (n - 1) * phi[0] + (phi[1] - phi[0]) * a + (phi[2] - phi[1]) * b + (phi[3] - phi[2]) * c
        for a in range(n)
        for b in range(a + 1)
        for c in range(b + 1)
        if comb(a + 1, 2) + comb(b + 1, 2) + comb(c + 1, 2) >= q
    )


@cache
def select_subset(v: CountVector) -> CountVector:
    """Only full-vector and single-event-deletion candidates; no global-best claim."""
    candidates = [
        v,
        *(tuple(c - int(i == j) for i, c in enumerate(v)) for j, count in enumerate(v) if count),
    ]
    return min(
        candidates,
        key=lambda u: (
            -rank_minimum(subset_parameters(u)[1], sum(subset_parameters(u)[3]), sum(u)),
            sum(u),
            u,
        ),
    )


@cache
def threshold_minimum(phi: Cells, q: int, n: int) -> dict[str, Any]:
    capacity = comb(n, 2)
    ranks = tuple(min(r for r in range(n) if comb(r + 1, 2) >= e) for e in range(capacity + 1))
    best: tuple[int, tuple[int, int, int]] | None = None
    cases, strata = 0, [0, 0, 0]
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(max(0, q - e1 - e2), e2 + 1):
                value = (
                    (n - 1) * phi[0]
                    + (phi[1] - phi[0]) * ranks[e1]
                    + (phi[2] - phi[1]) * ranks[e2]
                    + (phi[3] - phi[2]) * ranks[e3]
                )
                candidate = value, (e1, e2, e3)
                best = candidate if best is None else min(best, candidate)
                cases += 1
                strata[2 if e3 else int(e2 > 0)] += 1
    inherited = hunter.minimum_tree_correction(phi, q, n)
    if best is None:
        raise AssertionError("selected subset collision relaxation is infeasible")
    if (
        best != (inherited.correction, inherited.edge_counts)
        or cases != inherited.census_size
        or best[0] != rank_minimum(phi, q, n)
        or hunter.verify_rank_floor_algebra(n) != capacity + 1
    ):
        raise AssertionError("complete exact Hunter threshold minimum failed")
    return {
        "hunter_floor": best[0],
        "all_admissible_threshold_cases": cases,
        "admissible_case_counts": strata,
        "integer_minimizer": {
            "edge_counts": list(best[1]),
            "rank_floors": [ranks[e] for e in best[1]],
        },
    }


@cache
def subset_proof(u: CountVector) -> dict[str, Any]:
    rows, phi, incidences, collision = subset_parameters(u)
    n = sum(u)
    return catalog.normalized(
        {
            "proof_id": digest(u),
            "selected_subset_counts": sparse(u),
            "event_count": n,
            "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
            "occupied_type_pairs": hunter.occupied_type_pairs((u,)),
            "pair_rows": rows,
            "pair_floors": phi,
            "pair_overlap_ceiling": hunter.family_pair_overlap_ceiling(),
            "cell_label_counts": [len(c) for c in hunter.CELL_LABELS],
            "cell_incidences": incidences,
            "cell_collision_floors": collision,
            "collision_mass_floor": sum(collision),
            "balanced_collision_proof": "Smoothing high>=low+2 reduces Q by high-low-1>0",
            "collision_identity": "sum_x C(d_x,2)=sum_cells Q_cell=e1+e2+e3",
            "rank_proof": "e_k<=sum_j C(r_j+1,2)<=C(sum_j r_j+1,2); rank>=rho(e_k)",
            "nested_threshold_proof": "Descending Kruskal spans every nested threshold graph",
            "pointwise_hunter_proof": "A tree induces at most k-1 edges on k present vertices",
            "extension_rule": "Extend subset tree to all 18 events using nonnegative intersections",
            **threshold_minimum(phi, sum(collision), n),
        }
    )


@cache
def sealed_vector_rows() -> dict[CountVector, tuple[dict[str, Any], ...]]:
    """Retain earlier legal supports and tighter per-vector certified bounds."""
    found: dict[CountVector, list[dict[str, Any]]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            row = cast(dict[str, Any], value)
            if "counts" in row and "support_witness" in row:
                v = dense(row["counts"])
                found.setdefault(v, []).append(row)
            for child in row.values():
                visit(child)
        elif isinstance(value, list):
            for child in cast(list[Any], value):
                visit(child)

    for path in (
        h0.RESULT_RELATIVE,
        primary.RESULT_RELATIVE,
        *(p for p in source_paths() if p.endswith(".json")),
    ):
        visit(json.loads((REPO_ROOT / path).read_bytes()))
    return {v: tuple(rows) for v, rows in found.items()}


def legal_support(v: CountVector) -> tuple[tuple[int, ...], ...]:
    rows = sealed_vector_rows().get(v, ())
    support = (
        tuple(tuple(int(x) for x in t) for t in rows[0]["support_witness"])
        if rows
        else hunter.r12.construct_support_witness(v)
    )
    if support is None or not hunter.r8.validate_support_assignment(v, support):
        raise AssertionError("legal support witness failed")
    return support


def witness_analysis(v: CountVector, u: CountVector, proof: dict[str, Any]) -> dict[str, Any]:
    support = legal_support(v)
    types = tuple(i for i, count in enumerate(v) for _ in range(count))
    indices = tuple(
        j for i in range(30) for j in [k for k, t in enumerate(types) if t == i][: u[i]]
    )
    selected = tuple(support[j] for j in indices)
    phi = cast(Cells, tuple(proof["pair_floors"]))
    values = {(r[0], r[1], tuple(r[2:6])): r[6] for r in proof["pair_rows"]}
    observed = hunter.witness_analysis(u, selected, phi, values)
    tickets = tuple(frozenset(t) for t in selected)
    cell_mass = [
        sum(comb(sum(x in t for t in tickets), 2) for x in cell) for cell in hunter.CELL_LABELS
    ]
    overlaps = {
        (a, b): len(tickets[a] & tickets[b]) for a, b in combinations(range(len(tickets)), 2)
    }
    subtree = cast(tuple[tuple[int, int], ...], hunter.threshold_tree(sum(u), overlaps))
    tree = (
        *((indices[a], indices[b]) for a, b in subtree),
        *((indices[0], j) for j in range(18) if j not in indices),
    )
    weight = 0
    for a, b in tree:
        cells = cast(
            Cells,
            tuple(len(set(support[a]) & set(support[b]) & set(c)) for c in hunter.CELL_LABELS),
        )
        cost = six.residual_pair_intersection(*sorted((types[a], types[b])), cells)
        if cost < 0:
            raise AssertionError("negative residual intersection prevents tree extension")
        weight += cost
    if (
        len(indices) != sum(u)
        or len(set(indices)) != len(indices)
        or tuple(types[j] for j in indices) != tuple(i for i, c in enumerate(u) for _ in range(c))
        or any(a < b for a, b in zip(cell_mass, proof["cell_collision_floors"], strict=True))
        or sum(cell_mass) != observed["collision_mass"]
        or observed["phi_tree_weight"] < proof["hunter_floor"]
        or weight < observed["phi_tree_weight"]
        or len(tree) != hunter.graph_rank(18, tree)
        or len(tree) != 17
    ):
        raise AssertionError("witness collision or subset-to-full Hunter tree applicability failed")
    return catalog.normalized(
        {
            **observed,
            "selected_event_indices": indices,
            "selected_event_types": [types[j] for j in indices],
            "cell_collision_mass": cell_mass,
            "subset_tree": subtree,
            "extended_tree": tree,
            "extended_tree_exact_weight": weight,
            "support_witness": support,
            "support_sha256": digest(support),
        }
    )


def certify_vector(member: LedgerMember, v: CountVector) -> dict[str, Any]:
    u = select_subset(v)
    if any(a > b for a, b in zip(u, v, strict=True)):
        raise AssertionError("selected event submultiset is not <= represented vector")
    state = catalog.rebuild_member(replace(member, counts=v, represented_vector_count=1))
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    residual = sum(c * hunter.residual_event_size(i) for i, c in enumerate(v))
    earlier = [
        int(r["vector_new_bound"])
        for r in sealed_vector_rows().get(v, ())
        if "vector_new_bound" in r
    ]
    prior_bound = min([member.final_bound, *earlier])
    credits = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "SEALED_VALID": uncorrected - member.final_bound,
        "SEALED_VECTOR": uncorrected - prior_bound,
    }
    existing = hunter.combine_corrections(credits)
    proof = subset_proof(u)
    credits["SUBSET_HUNTER"] = int(proof["hunter_floor"])
    combined = hunter.combine_corrections(credits)
    bound = min(prior_bound, uncorrected - combined)
    if (
        uncorrected != hunter.anchor_union_size() + residual
        or min(credits.values()) < 0
        or existing != uncorrected - prior_bound
        or combined != max(credits.values())
        or bound != hunter.member_bound(uncorrected, combined)
        or bound >= member.final_bound
    ):
        raise AssertionError(
            "MAX single replacement or existing certified credit preservation failed"
        )
    return catalog.normalized(
        {
            "counts": sparse(v),
            "selected_subset_counts": sparse(u),
            "proof_id": digest(u),
            "anchor_union": hunter.anchor_union_size(),
            "residual_event_sum": residual,
            "uncorrected_anchor_bound": uncorrected,
            "corrections": credits,
            "prior_applied_correction": existing,
            "combined_correction": combined,
            "vector_prior_bound": prior_bound,
            "vector_new_bound": bound,
            "witness_analysis": witness_analysis(v, u, proof),
        }
    )


def certify_member(state_id: str, member: LedgerMember) -> dict[str, Any]:
    vectors = represented_vectors(state_id)[member.counts]
    rows = [certify_vector(member, v) for v in vectors]
    correction = min(int(r["combined_correction"]) for r in rows)
    bound = max(int(r["vector_new_bound"]) for r in rows)
    if (
        len(rows) != member.represented_vector_count
        or member not in target_members(state_id)
        or len({r["uncorrected_anchor_bound"] for r in rows}) != 1
        or hunter.member_correction(tuple(r["combined_correction"] for r in rows)) != correction
        or bound != rows[0]["uncorrected_anchor_bound"] - correction
    ):
        raise AssertionError("complete compressed-vector MAX bound failed")
    return catalog.normalized(
        {
            "member_id": member_id(member.counts),
            "witness_counts": sparse(member.counts),
            "represented_vector_count": len(vectors),
            "represented_vectors": [sparse(v) for v in vectors],
            "member_prior_bound": member.final_bound,
            "member_raw_bound": member.raw_bound,
            "member_certified_correction": correction,
            "member_new_bound": bound,
            "vector_certificates": rows,
            "correction_combination": CORRECTION_COMBINATION,
        }
    )


@cache
def certify_region(state_id: str) -> dict[str, Any]:
    members, vectors = region_members(state_id), represented_vectors(state_id)
    targets = target_members(state_id)
    records = [certify_member(state_id, m) for m in targets]
    priors = {m.counts: m.final_bound for m in members}
    bounds = six.replaced_bounds(priors, records)
    target_counts = {m.counts for m in targets}
    remainder = tuple(m for m in members if m.counts not in target_counts)
    if {v for v in priors if bounds[v] != priors[v]} != target_counts or max(
        bounds.values()
    ) != REGION_SPECS[state_id][5]:
        raise AssertionError("exact State bound or untouched-member preservation failed")
    return {
        "state_id": state_id,
        "region_sha256": catalog.region_fingerprint(members),
        "region_member_count": len(members),
        "region_vector_count": sum(len(v) for v in vectors.values()),
        "target_member_count": len(records),
        "target_vector_count": sum(len(vectors[m.counts]) for m in targets),
        "member_certificates": records,
        "preserved_member_count": len(remainder),
        "preserved_vector_count": sum(len(vectors[m.counts]) for m in remainder),
        "preserved_member_bounds_sha256": digest(
            tuple((m.counts, m.final_bound) for m in remainder)
        ),
        "complete_updated_bounds_sha256": digest(
            tuple((m.counts, bounds[m.counts]) for m in members)
        ),
        "complete_region_members": [
            {**row, "prior_bound": m.final_bound, "final_bound": bounds[m.counts]}
            for m, row in zip(members, region_rows(state_id), strict=True)
        ],
        "start_state_bound": max(priors.values()),
        "final_state_bound": max(bounds.values()),
        "final_state_member_ids": [
            member_id(v) for v, b in bounds.items() if b == max(bounds.values())
        ],
    }


def recompute_family(regions: list[dict[str, Any]]) -> dict[str, Any]:
    source = source_results()["H0"]
    states = tuple((str(r["stable_id"]), int(r["bound"])) for r in source["FINAL_STATE_TERMS"])
    classified = tuple(
        (str(r["stable_id"]), int(r["bound"]))
        for r in source_results()["JOINT"]["FINAL_CLASSIFIED_TERMS"]
    )
    tail = six.sealed_tail_bound()
    if (
        len(states) != len(dict(states))
        or len(states) != 23
        or len(classified) != source["CLASSIFIED_TERM_COUNT"]
        or digest(classified) != source["CLASSIFIED_TERMS_SHA256"]
        or max(b for _, b in classified) != 355145504
        or tail != source["TAIL_BOUND"]
        or tail != 354039277
    ):
        raise AssertionError("complete State/Classified/Tail authority failed")
    start = six.tail.family_maximum(tail, states, classified)
    replacements = {str(r["state_id"]): int(r["final_state_bound"]) for r in regions}
    if set(replacements) != set(REGION_SPECS) or len(regions) != 3:
        raise AssertionError("exact three-State replacement coverage failed")
    updated = tuple((k, replacements.get(k, b)) for k, b in states)
    final = six.tail.family_maximum(tail, updated, classified)
    terms = (*updated, *classified, (r24.TAIL_ID, tail))
    maximum = max(b for _, b in terms)
    runner_up = max(b for _, b in terms if b < maximum)
    if (
        start != source["FINAL_FAMILY_MAX_RECOMPUTATION"]
        or start["R3_BOUND"] != 355368426
        or final["R3_BOUND"] != maximum
        or maximum != TARGET_CUTOFF
        or final["OWNER_IDS"] != ["state:s2-12692531-s3-681744"]
        or runner_up != 355274108
    ):
        raise AssertionError("complete R3 Family maximum, owner or runner-up failed")
    return {
        "start": start,
        "final": final,
        "start_states": states,
        "states": updated,
        "classified": classified,
        "tail": tail,
        "runner_up": runner_up,
    }


def build_result() -> dict[str, Any]:
    return _build_result(verify_source_authority())


def _build_result(authority: dict[str, Any]) -> dict[str, Any]:
    regions = [certify_region(sid) for sid in REGION_SPECS]
    family = recompute_family(regions)
    subsets = {
        select_subset(v)
        for sid in REGION_SPECS
        for m in target_members(sid)
        for v in represented_vectors(sid)[m.counts]
    }
    mc, vc = (
        sum(r["target_member_count"] for r in regions),
        sum(r["target_vector_count"] for r in regions),
    )
    if (mc, vc) != (106, 116) or r24.INCUMBENT != 313263888:
        raise AssertionError("complete target count or incumbent identity failed")
    return catalog.normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS",
            "REMAINING_TASK_MODEL": "最強模型",
            "TASK_BRANCH": TASK_BRANCH,
            "BASE_HEAD": BASE_HEAD,
            "BASE_TREE": BASE_TREE,
            "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
            "SOURCE_AUTHORITY": authority,
            "SOURCE_AUTHORITY_STATUS": "PASS_IMMUTABLE_OBJECTS_AND_EXECUTING_BYTES",
            "H0_PRESERVATION": "PASS_IMMUTABLE_SEALED_PREDECESSOR_AND_MAX_CREDITS",
            "SUBSET_SELECTION_RULE": "FULL_VECTOR_OR_DELETE_ONE_EVENT; GLOBAL_BEST_NOT_REQUIRED",
            "SUBSET_PROOFS": [subset_proof(u) for u in sorted(subsets)],
            "REGIONS": regions,
            "TARGET_MEMBER_COUNT": mc,
            "TARGET_VECTOR_COUNT": vc,
            "NEW_STATE_BOUNDS": {r["state_id"]: r["final_state_bound"] for r in regions},
            "PRESERVED_REMAINDER_STATUS": "PASS_EVERY_UNTOUCHED_MEMBER_AND_VECTOR",
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_NEVER_SUM",
            "SUBSET_VALIDITY_STATUS": "PASS_INTEGER_SUBMULTISETS_2_TO_18",
            "PAIR_FLOOR_STATUS": "PASS_EXACT_TYPE_PAIR_REALIZATIONS_AND_RESIDUAL_INTERSECTIONS",
            "COLLISION_FLOOR_STATUS": "PASS_BALANCED_INTEGER_FREQUENCIES_IN_ALL_FOUR_CELLS",
            "HUNTER_PROOF_STATUS": "PASS_COMPLETE_THRESHOLD_MINIMA_AND_FULL_TREE_EXTENSION",
            "WITNESS_SOUNDNESS_STATUS": "PASS_PRESERVED_LEGAL_SUPPORTS_AND_UNIVERSAL_PROOFS",
            "START_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["start_states"]],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["states"]],
            "STATE_TERM_COUNT": 23,
            "CLASSIFIED_TERM_COUNT": len(family["classified"]),
            "CLASSIFIED_TERMS_SHA256": digest(family["classified"]),
            "CLASSIFIED_MAX": 355145504,
            "TAIL_BOUND": family["tail"],
            "START_FAMILY_MAX_RECOMPUTATION": family["start"],
            "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
            "START_COMPLETE_R3_UB": 355368426,
            "FINAL_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
            "RUNNER_UP": family["runner_up"],
            "CURRENT_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": family["final"]["R3_BOUND"] - r24.INCUMBENT,
            "STRICT_GAIN": 355368426 - family["final"]["R3_BOUND"],
            "R7_CENSUS_REBUILD_CALLS": 0,
            "OUTCOME_ENUMERATION_USED": False,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    authority = verify_source_authority()
    if [r["state_id"] for r in result["REGIONS"]] != list(REGION_SPECS):
        raise AssertionError("exact three-State coverage failed")
    for region in result["REGIONS"]:
        sid = str(region["state_id"])
        targets = target_members(sid)
        records = region["member_certificates"]
        if [r["member_id"] for r in records] != [member_id(m.counts) for m in targets]:
            raise AssertionError("complete 106-member coverage failed")
        for record, member in zip(records, targets, strict=True):
            vectors = represented_vectors(sid)[member.counts]
            rows = record["vector_certificates"]
            if (
                record["represented_vectors"] != [sparse(v) for v in vectors]
                or len(rows) != len(vectors)
                or record["represented_vector_count"] != len(vectors)
            ):
                raise AssertionError("complete 116-vector compressed coverage failed")
            for row, v in zip(rows, vectors, strict=True):
                raw = row["selected_subset_counts"]
                if any(type(i) is not int or type(c) is not int for i, c in raw):
                    raise AssertionError("stored subset counts must be integers")
                u = dense(raw)
                if (
                    row["counts"] != sparse(v)
                    or any(a > b for a, b in zip(u, v, strict=True))
                    or not 2 <= sum(u) <= 18
                    or u != select_subset(v)
                    or raw != sparse(u)
                ):
                    raise AssertionError("stored selected subset applicability failed")
                if row["combined_correction"] != max(row["corrections"].values()):
                    raise AssertionError("corrections must combine by MAX, never SUM")
            if record["member_new_bound"] != max(r["vector_new_bound"] for r in rows):
                raise AssertionError("compressed member requires MAX over every vector")
    replay = _build_result(authority)
    # Encoding also rejects numerically equal float/bool tampering and extra keys.
    if encode(result) != encode(replay):
        raise AssertionError("stored result differs from complete exact certificate replay")
    return {"status": "PASS", "members": 106, "vectors": 116, "state_terms": 23}


def encode(result: dict[str, Any]) -> str:
    return hunter.encode(result)


def verify_stored_result() -> dict[str, Any]:
    stored = RESULT_PATH.read_bytes()
    status = verify_result(cast(dict[str, Any], json.loads(stored)))
    if stored != encode(build_result()).encode():
        raise AssertionError("stored result bytes differ from byte-exact replay")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_stored_result(), sort_keys=True))
        return
    result = build_result()
    if args.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    keys = (
        "TASK_STATUS",
        "TARGET_MEMBER_COUNT",
        "TARGET_VECTOR_COUNT",
        "NEW_STATE_BOUNDS",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "RUNNER_UP",
        "STRICT_GAIN",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
