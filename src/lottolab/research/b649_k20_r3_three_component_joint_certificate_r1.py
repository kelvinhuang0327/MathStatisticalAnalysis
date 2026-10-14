"""Joint six-member, immutable 47-member and Classified R12 Hunter certificate.

Independently enumerate the six-member twelve-event theorem, adopt the complete
byte-replayed components, and combine each residual correction by MAX once.
The complete State, classified and sealed Tail maps determine the Family UB.
No solver, census, portfolio search or official-outcome enumeration is used.
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

from lottolab.research import (
    b649_k20_r3_classified_r12_five_level_nine_event_certificate_r1 as donor,
)
from lottolab.research import (
    b649_k20_r3_state_13169800_forty_seven_shared_hunter_certificate_r1 as primary,
)

nine = donor.nine
hunter, catalog, six, r24 = primary.hunter, primary.catalog, primary.six, primary.r24
LedgerMember = catalog.LedgerMember
type CountVector = tuple[int, ...]
dense, sparse, digest, member_id = primary.dense, primary.sparse, primary.digest, primary.member_id
TASK_ID = "B649_K20_R3_THREE_COMPONENT_JOINT_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-three-component-joint-certificate-r1"
COMMON_SOURCE_HEAD = "5cfacd03b1026274577f6647083684b53b00bcae"
PRIMARY_BASE_HEAD = "f3a90b9367e40942022c05c6cf918ad758bd1bc9"
DONOR_HEAD = "28751d6cbb3088907a0595ff093f04e4cf4f9c29"
REPO_ROOT = Path(__file__).resolve().parents[3]
TARGET_STATE_ID = nine.TARGET_STATE_ID
REGION_SHA256 = nine.REGION_SHA256
REGION_MEMBER_COUNT, REGION_VECTOR_COUNT = 1222, 1325
PAIR_COSTS = (107800, 574000, 1691620, 3451651)
THEOREM = {12: (72, 32, 51257, 4915400)}
RESIDUAL_EVENT_DEFINITION = primary.RESIDUAL_EVENT_DEFINITION
CORRECTION_COMBINATION = "MAX(EXISTING_VALID_CORRECTIONS, TWELVE_EVENT_HUNTER)"
RESULT_RELATIVE = six.RESULTS + "b649-k20-r3-three-component-joint-certificate-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
SOURCE_IDENTITIES = {
    COMMON_SOURCE_HEAD: (
        primary.BASE_TREE,
        primary.prior.RESULT_RELATIVE,
        primary.BASE_RESULT_SHA256,
    ),
    PRIMARY_BASE_HEAD: (
        "0c11eb3e682766d29a0c72baba10cbd408ae9c86",
        primary.RESULT_RELATIVE,
        "55a820302c0cf41be04bb9e0e4ed87e84b68d560932e43ddd9a85a741ca633e1",
    ),
    DONOR_HEAD: (
        "9424a377f13775201082415b040fe35cac8083fd",
        donor.RESULT_RELATIVE,
        "6ce9b15bca0d5b15a3b5d89578e5c82874364649c68371223b794f13bf42e533",
    ),
}
SOURCE_FILES = {
    (
        "src/lottolab/research/"
        "b649_k20_r3_state_13169800_forty_seven_shared_hunter_certificate_r1.py"
    ): (
        "f3a90b9367e40942022c05c6cf918ad758bd1bc9",
        "a2505838614e3fb6d9ca99a42d44c1a33ba0afb8",
        "0fadd2e0557bc90eb2f47adbcac381f429d7f036104d8616e4010c20f70bae80",
    ),
    "tests/unit/test_b649_k20_r3_state_13169800_forty_seven_shared_hunter_certificate_r1.py": (
        "f3a90b9367e40942022c05c6cf918ad758bd1bc9",
        "65a9ae936895ec19efcd655f8bfda058589d05ec",
        "680d856a800c045fa714c97248407e2049dcd5dfbf3596d44fa27d3c6d673432",
    ),
    (
        "docs/research/matrix-native-results/"
        "b649-k20-r3-state-13169800-forty-seven-shared-hunter-certificate-r1-result.json"
    ): (
        "f3a90b9367e40942022c05c6cf918ad758bd1bc9",
        "d4fe94f67c5373a2afe084c0a366c1b6ec9d0083",
        "55a820302c0cf41be04bb9e0e4ed87e84b68d560932e43ddd9a85a741ca633e1",
    ),
    "src/lottolab/research/b649_k20_r3_classified_r12_five_level_nine_event_certificate_r1.py": (
        "28751d6cbb3088907a0595ff093f04e4cf4f9c29",
        "bad7e7e5f7b227f929fa03589cd3b902c00b1098",
        "f797e3e8f3871e35b08d45d12a8a1871c61b5d25db41b688933106c73dc4a232",
    ),
    "tests/unit/test_b649_k20_r3_classified_r12_five_level_nine_event_certificate_r1.py": (
        "28751d6cbb3088907a0595ff093f04e4cf4f9c29",
        "b5ec01f0f25c3188d4517bfda7b51c8a7fc9dea9",
        "bf76b5faefc468abb9981b3295a13a25af13fa350d1def52ae518aa1bb56aa58",
    ),
    (
        "docs/research/matrix-native-results/"
        "b649-k20-r3-classified-r12-five-level-nine-event-certificate-r1-result.json"
    ): (
        "28751d6cbb3088907a0595ff093f04e4cf4f9c29",
        "d2923c3f66cfc0c465cd9361b7732aa9c649e577",
        "6ce9b15bca0d5b15a3b5d89578e5c82874364649c68371223b794f13bf42e533",
    ),
}


@cache
def twelve_event_proof() -> dict[str, Any]:
    """Full integer minimum over C(n,2) >= e1 >= e2 >= e3 >= 0, sum e >= Q.

    For each outcome in k events, a tree induces at most k-1 edges. Summation
    proves Hunter's inequality for residual events. Descending Kruskal retains
    a spanning forest of every nested G_k={ij: overlap>=k}. Component ranks r_j
    imply e_k <= sum C(r_j+1,2) <= C(sum r_j+1,2), so rank(G_k)>=rho(e_k).
    Balancing outside frequencies minimizes sum_x C(d_x,2); overlap<=3 gives
    Q=e1+e2+e3. Enumerate every feasible threshold triple independently of the
    donor minimizer. The floor is the exact minimum of this relaxation, never
    the weaker three-case shortcut. Nonnegative edges extend the subset tree
    to all eighteen residual events without claiming additional correction.
    """

    event_count = 12
    if event_count not in THEOREM:
        raise AssertionError("unsupported Hunter event count")
    expected_incidences, expected_mass, expected_cases, expected_floor = THEOREM[event_count]
    if (
        hunter.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.eleven.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.type_cells(0) != (0, 0, 0, hunter.TICKET_SIZE)
    ):
        raise AssertionError("source residual-event definition or type-0 identity failed")
    rows = hunter.exact_pair_rows(((0, 0),))
    ceiling = hunter.family_pair_overlap_ceiling()
    if (
        ceiling != 3
        or len(rows) != ceiling + 1
        or {r[2:6] for r in rows} != {(0, 0, 0, k) for k in range(ceiling + 1)}
    ):
        raise AssertionError("exact type-0 pair row coverage failed")
    for row in rows:
        cells = (row[2], row[3], row[4], row[5])
        if (
            row[:2] != (0, 0)
            or six.residual_pair_intersection(0, 0, cells) != row[6]
            or hunter.outcome_count(
                hunter.realize_pair(hunter.type_cells(0), hunter.type_cells(0), cells),
                (hunter.ANCHOR_A, hunter.ANCHOR_B),
            )
            != row[6]
        ):
            raise AssertionError("exact residual pair inclusion/exclusion failed")
    floors = hunter.pair_floors(rows)
    hunter.require_safe_pair_floors(floors, rows)
    if tuple(floors) != PAIR_COSTS:
        raise AssertionError("exact type-0 pair costs failed")
    outside = set(range(hunter.POOL_SIZE)) - set(hunter.ANCHOR_A | hunter.ANCHOR_B)
    incidences, labels = event_count * hunter.type_cells(0)[3], len(outside)
    if outside != set(hunter.CELL_LABELS[3]) or labels != 40:
        raise AssertionError("outside universe differs from the anchor complement")
    quotient, remainder = divmod(incidences, labels)
    mass = hunter.balanced_collision_mass(incidences, labels)
    if (
        mass != (labels - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)
        or mass != incidences - labels
        or mass != expected_mass
        or incidences != expected_incidences
    ):
        raise AssertionError("balanced outside collision floor failed")
    capacity = comb(event_count, 2)
    ranks = tuple(
        next(r for r in range(event_count) if comb(r + 1, 2) >= e) for e in range(capacity + 1)
    )
    rank_rows = hunter.verify_rank_floor_algebra(event_count)
    if rank_rows != capacity + 1 or any(hunter.rank_floor(e) != r for e, r in enumerate(ranks)):
        raise AssertionError("independent least forest-rank identity failed")
    best: tuple[int, tuple[int, int, int]] | None = None
    cases = 0
    case_counts = [0, 0, 0]
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < mass:
                    continue
                rho = tuple(ranks[e] for e in (e1, e2, e3))
                value = (event_count - 1) * floors[0] + sum(
                    (floors[k + 1] - floors[k]) * rho[k] for k in range(ceiling)
                )
                if value != hunter.tree_weight_floor(floors, rho, event_count):
                    raise AssertionError("independent nested-threshold weight identity failed")
                candidate = (value, (e1, e2, e3))
                if best is None or candidate < best:
                    best = candidate
                cases += 1
                case_counts[2 if e3 else int(e2 > 0)] += 1
    relaxation = hunter.minimum_tree_correction(floors, mass, event_count)
    edge_counts = cast(tuple[int, int, int], relaxation.edge_counts)
    if (
        best != (relaxation.correction, edge_counts)
        or relaxation.correction != expected_floor
        or cases != expected_cases
        or cases != relaxation.census_size
        or tuple(ranks[e] for e in edge_counts) != relaxation.rank_floors
        or sum(case_counts) != cases
        or not all(case_counts)
    ):
        raise AssertionError("complete exact threshold integer minimization failed")
    return {
        "event_count": event_count,
        "type_index": 0,
        "type_cells": list(hunter.type_cells(0)),
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "residual_event_size": hunter.residual_event_size(0),
        "outside_labels": sorted(outside),
        "outside_incidences": incidences,
        "outside_label_count": labels,
        "balanced_frequencies": [[quotient, labels - remainder], [quotient + 1, remainder]],
        "collision_mass_floor": mass,
        "collision_identity": "Q = sum_x C(d_x,2) = e1+e2+e3",
        "pair_rows": [list(r) for r in rows],
        "pair_floors": list(floors),
        "pair_overlap_ceiling": ceiling,
        "rank_algebra_rows": rank_rows,
        "hunter_floor": relaxation.correction,
        "all_admissible_threshold_cases": cases,
        "admissible_case_counts": case_counts,
        "admissible_threshold_status": "PASS_COMPLETE_EXACT_INTEGER_MINIMIZATION",
        "integer_minimizer": {
            "edge_counts": list(relaxation.edge_counts),
            "rank_floors": list(relaxation.rank_floors),
            "feasible_threshold_triples": relaxation.census_size,
        },
        "floor_method": "FULL_EXACT_INTEGER_MINIMIZATION",
        "nested_threshold_inequality": "(n-1)*phi0 + sum_k rank(G_k)*(phi_k-phi_(k-1))",
        "rank_inequality": "e_k <= C(rank(G_k)+1,2); rank(G_k) >= rho(e_k)",
        "hunter_inequality": "|union R_i| <= sum_i |R_i| - sum_(ij in T) |R_i intersect R_j|",
        "extension_rule": "Extend the subset tree with nonnegative residual-pair edges",
    }


def verify_source_authority() -> dict[str, Any]:
    """Uncached immutable object and byte checks also protect warm replay caches."""

    prefix = ["git", "-C", str(REPO_ROOT)]
    identities: dict[str, Any] = {}
    for head, (tree, path, result_sha) in SOURCE_IDENTITIES.items():
        observed = subprocess.check_output(
            [*prefix, "show", "-s", "--format=%H %T", head], text=True
        )
        blob = subprocess.check_output([*prefix, "show", f"{head}:{path}"])
        if observed.strip() != f"{head} {tree}" or sha256(blob).hexdigest() != result_sha:
            raise AssertionError("immutable source HEAD/TREE/result authority failed")
        identities[head] = {"HEAD": head, "TREE": tree, "RESULT_SHA256": result_sha}
    for head in (PRIMARY_BASE_HEAD, DONOR_HEAD):
        if subprocess.run(
            [*prefix, "merge-base", "--is-ancestor", COMMON_SOURCE_HEAD, head]
        ).returncode:
            raise AssertionError("immutable component ancestry failed")
        parent = subprocess.check_output([*prefix, "show", "-s", "--format=%P", head], text=True)
        if parent.strip() != COMMON_SOURCE_HEAD:
            raise AssertionError("immutable component immediate lineage failed")
    if subprocess.run(
        [*prefix, "merge-base", "--is-ancestor", PRIMARY_BASE_HEAD, "HEAD"]
    ).returncode:
        raise AssertionError("joint checkout does not descend from PRIMARY")
    files: dict[str, Any] = {}
    for path, (head, expected_blob, expected_sha) in SOURCE_FILES.items():
        blob_id = subprocess.check_output(
            [*prefix, "rev-parse", f"{head}:{path}"], text=True
        ).strip()
        blob = subprocess.check_output([*prefix, "show", f"{head}:{path}"])
        if (
            blob_id != expected_blob
            or sha256(blob).hexdigest() != expected_sha
            or (REPO_ROOT / path).read_bytes() != blob
        ):
            raise AssertionError("component byte identity or donor tampering failed")
        files[path] = {"HEAD": head, "BLOB": blob_id, "SHA256": expected_sha}
    fingerprints = {
        **primary.verify_upstream_fingerprints(),
        **donor.verify_upstream_fingerprints(),
        **nine.verify_upstream_fingerprints(),
    }
    return {"identities": identities, "component_files": files, "upstream_sha256": fingerprints}


@cache
def source_components() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Mathematically replay the components and require their original bytes."""

    verify_source_authority()
    results: list[dict[str, Any]] = []
    for module in (primary, donor, nine):
        result = module.build_result()
        if module.RESULT_PATH.read_bytes() != module.encode(result).encode():
            raise AssertionError("component complete mathematical byte replay failed")
        results.append(result)
    return results[0], results[1], results[2]


@cache
def region_members() -> tuple[LedgerMember, ...]:
    """Adopt the nine-event predecessor bounds and replay its entire region."""

    source = source_components()[2]
    original = nine.region_members()
    bounds = six.replaced_bounds(
        {m.counts: m.final_bound for m in original}, source["MEMBER_CERTIFICATES"]
    )
    members = tuple(replace(m, final_bound=bounds[m.counts]) for m in original)
    rows = source["COMPLETE_REGION_MEMBERS"]
    if (
        len(members) != REGION_MEMBER_COUNT
        or len({m.counts for m in members}) != REGION_MEMBER_COUNT
        or sum(m.represented_vector_count for m in members) != REGION_VECTOR_COUNT
        or catalog.region_fingerprint(members) != REGION_SHA256
        or len(rows) != len(members)
        or max(bounds.values()) != source["FINAL_TARGET_STATE_UB"]
        or any(
            row["member_id"] != member_id(m.counts)
            or dense(row["witness_counts"]) != m.counts
            or row["raw_bound"] != m.raw_bound
            or row["final_bound"] != m.final_bound
            or row["represented_vector_count"] != m.represented_vector_count
            for m, row in zip(members, rows, strict=True)
        )
    ):
        raise AssertionError("complete six-member State region replay failed")
    return members


@cache
def represented_vectors() -> dict[CountVector, tuple[CountVector, ...]]:
    members = region_members()
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in members))
    flat = [v for vectors in recovered.values() for v in vectors]
    if (
        len(flat) != len(set(flat))
        or len(flat) != REGION_VECTOR_COUNT
        or set(recovered) != {m.counts for m in members}
        or recovered != nine.represented_vectors()
    ):
        raise AssertionError("complete represented-vector coverage failed")
    for m, row in zip(members, source_components()[2]["COMPLETE_REGION_MEMBERS"], strict=True):
        vectors = recovered[m.counts]
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(m))
        if (
            len(vectors) != m.represented_vector_count
            or tuple(sorted(vectors)) != vectors
            or min(vectors) != m.counts
            or tuple(dense(v) for v in row["represented_vectors"]) != vectors
            or catalog.normalized(signature) != row["compression_signature"]
            or any(
                hunter.eleven.compression_signature(
                    catalog.rebuild_member(replace(m, counts=v, represented_vector_count=1))
                )
                != signature
                for v in vectors
            )
        ):
            raise AssertionError("complete compression signature or vector identity failed")
    return recovered


def target_members(members: tuple[LedgerMember, ...]) -> tuple[LedgerMember, ...]:
    expected: set[CountVector] = set()
    for j in range(6):
        vector = [0] * 30
        vector[0], vector[1], vector[4], vector[20] = 12, j, 5 - j, 1
        expected.add(tuple(vector))
    targets = tuple(m for m in members if m.counts in expected)
    if (
        len(targets) != 6
        or {m.counts for m in targets} != expected
        or any(m.represented_vector_count != 1 for m in targets)
    ):
        raise AssertionError("exact six-member coverage failed")
    return targets


def existing_corrections(member: LedgerMember) -> tuple[dict[str, int], dict[str, Any]]:
    """Recover sealed credits; these six members have no carried R14/Hunter award."""

    state = catalog.rebuild_member(member)
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    carried = [row for row in nine.carried_certificates() if row[1] == member.counts]
    earlier_hunter = [
        row
        for row in source_components()[2]["MEMBER_CERTIFICATES"]
        if dense(row["witness_counts"]) == member.counts
    ]
    corrections = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "EXISTING_R14": 0,
        "EXISTING_HUNTER": max(
            (int(row["member_certified_correction"]) for row in earlier_hunter), default=0
        ),
        "CARRIED_VALID": uncorrected - member.final_bound,
    }
    if (
        member not in target_members(region_members())
        or corrections["FOREST"] != 4592000
        or uncorrected != 360089359
        or state.applied_residual_union_penalty
        != max(corrections["R6_PAIR"], corrections["FOREST"])
        or uncorrected - state.applied_residual_union_penalty != member.raw_bound
        or max(corrections.values()) != uncorrected - member.final_bound
        or carried
        or earlier_hunter
    ):
        raise AssertionError("six-member current forest, R14/Hunter or carried correction failed")
    return corrections, {
        "sealed_r14_matches": len(carried),
        "sealed_hunter_matches": len(earlier_hunter),
        "carried_catalog_size": len(nine.carried_certificates()),
        "prior_equals_raw": member.final_bound == member.raw_bound,
    }


@cache
def support_witness(vector: CountVector) -> tuple[tuple[int, ...], ...]:
    support = nine.support_witness(vector)
    if not hunter.r8.validate_support_assignment(vector, support):
        raise AssertionError("six-member legal support failed")
    return support


def certify_member(
    member: LedgerMember, vectors: tuple[CountVector, ...], proof: dict[str, Any]
) -> dict[str, Any]:
    if (
        member not in target_members(region_members())
        or vectors != represented_vectors()[member.counts]
        or vectors != (member.counts,)
        or proof != twelve_event_proof()
    ):
        raise AssertionError("complete six-member represented-vector applicability failed")
    vector = vectors[0]
    state = catalog.rebuild_member(member)
    types = tuple(i for i, count in enumerate(vector) for _ in range(count))
    n = int(proof["event_count"])
    if len(types) != 18 or vector[0] != n or types[:n] != (0,) * n:
        raise AssertionError("twelve-event residual subset identity failed")
    corrections, credit_coverage = existing_corrections(member)
    existing = hunter.combine_corrections(corrections)
    corrections["TWELVE_EVENT_HUNTER"] = int(proof["hunter_floor"])
    combined = hunter.combine_corrections(corrections)
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    residual_sum = sum(count * hunter.residual_event_size(i) for i, count in enumerate(vector))
    bound = hunter.member_bound(uncorrected, combined)
    if (
        uncorrected != hunter.anchor_union_size() + residual_sum
        or existing != uncorrected - member.final_bound
        or combined != max(corrections.values())
        or bound != uncorrected - combined
        or bound >= member.final_bound
    ):
        raise AssertionError("MAX single replacement or additive-credit mutation failed")
    support = support_witness(vector)
    witness = nine.shared.prior.prior.witness_analysis(vector, support, proof)
    subset = tuple(frozenset(t) for t in support[:n])
    mass = sum(comb(sum(x in t for t in subset), 2) for x in hunter.CELL_LABELS[3])
    tree = cast(tuple[tuple[int, int], ...], witness["extended_tree"])
    full_weight = 0
    for left, right in tree:
        cells = tuple(
            len(set(support[left]) & set(support[right]) & set(c)) for c in hunter.CELL_LABELS
        )
        cost = six.residual_pair_intersection(
            types[left], types[right], cast(tuple[int, int, int, int], cells)
        )
        if cost < 0:
            raise AssertionError("negative residual edge prevents Hunter extension")
        full_weight += cost
    if (
        mass != sum(len(a & b) for a, b in combinations(subset, 2))
        or mass != witness["collision_mass"]
        or mass < proof["collision_mass_floor"]
        or any(not t <= set(proof["outside_labels"]) for t in subset)
        or len(tree) != hunter.graph_rank(18, tree)
        or len(tree) != 17
        or full_weight < witness["phi_tree_weight"]
        or witness["phi_tree_weight"] < combined
    ):
        raise AssertionError("legal witness collision or full Hunter tree extension failed")
    row = {
        "counts": sparse(vector),
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "selected_event_indices": list(range(n)),
        "selected_event_types": list(types[:n]),
        "anchor_union": hunter.anchor_union_size(),
        "residual_event_sum": residual_sum,
        "uncorrected_anchor_bound": uncorrected,
        "corrections": corrections,
        "existing_credit_coverage": credit_coverage,
        "prior_applied_correction": existing,
        "combined_correction": combined,
        "vector_prior_bound": member.final_bound,
        "vector_new_bound": bound,
        "support_witness": support,
        "support_sha256": digest(support),
        "witness_analysis": {**witness, "extended_tree_exact_weight": full_weight},
    }
    return catalog.normalized(
        {
            "member_id": member_id(vector),
            "witness_counts": sparse(vector),
            "represented_vector_count": len(vectors),
            "represented_vectors": [sparse(v) for v in vectors],
            "member_prior_bound": member.final_bound,
            "member_raw_bound": member.raw_bound,
            "member_certified_correction": hunter.member_correction((combined,)),
            "member_new_bound": bound,
            "vector_certificates": [row],
            "correction_combination": CORRECTION_COMBINATION,
        }
    )


def recompute_family(state_bound: int) -> dict[str, Any]:
    p, d, _ = source_components()
    states = tuple((str(r["stable_id"]), int(r["bound"])) for r in p["FINAL_STATE_TERMS"])
    classified, tail = six.classified_terms(), six.sealed_tail_bound()
    if (
        len(states) != len(dict(states))
        or len(states) != 23
        or TARGET_STATE_ID not in dict(states)
        or dict(states)[primary.TARGET_STATE_ID] != p["FINAL_TARGET_STATE_UB"]
        or len(classified) != 56550
        or len(dict(classified)) != len(classified)
        or digest(classified) != p["CLASSIFIED_TERMS_SHA256"]
        or tail != p["TAIL_BOUND"]
        or tail != d["TAIL_BOUND"]
    ):
        raise AssertionError("complete 23 State/classified/Tail term coverage failed")
    start = six.tail.family_maximum(tail, states, classified)
    if start != p["FINAL_FAMILY_MAX_RECOMPUTATION"]:
        raise AssertionError("PRIMARY complete starting Family replay failed")
    updated_states = tuple((k, state_bound if k == TARGET_STATE_ID else b) for k, b in states)
    # Adopt the donor's recomputed aggregate bound; never add a correction.
    updated_classified = donor.replace_aggregate(classified, int(d["FINAL_R12_AGGREGATE_MAX"]))
    explicit = tuple((k, b) for k, b in classified if k != r24.AGGREGATE_ID)
    if (
        digest(updated_classified) != d["FINAL_CLASSIFIED_TERMS_SHA256"]
        or len(explicit) != d["PRESERVED_EXPLICIT_CLASSIFIED_TERM_COUNT"]
        or digest(explicit) != d["FINAL_EXPLICIT_CLASSIFIED_TERMS_SHA256"]
        or any(b != dict(states)[k] for k, b in updated_states if k != TARGET_STATE_ID)
    ):
        raise AssertionError("PRIMARY State or donor classified preservation failed")
    final = six.tail.family_maximum(tail, updated_states, updated_classified)
    all_terms = (*updated_states, (r24.TAIL_ID, tail), *updated_classified)
    maximum = max(b for _, b in all_terms)
    if (
        final["R3_BOUND"] != maximum
        or final["OWNER_IDS"] != sorted(k for k, b in all_terms if b == maximum)
        or final["STATE_MAX_BOUND"] != max(b for _, b in updated_states)
        or final["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] != max(b for _, b in updated_classified)
    ):
        raise AssertionError("independent complete Family maximum failed")
    return {
        "states": updated_states,
        "classified": updated_classified,
        "explicit": explicit,
        "tail": tail,
        "start": start,
        "final": final,
    }


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    p, d, source = source_components()
    members, vectors, proof = region_members(), represented_vectors(), twelve_event_proof()
    targets = target_members(members)
    records = [certify_member(m, vectors[m.counts], proof) for m in targets]
    priors = {m.counts: m.final_bound for m in members}
    bounds = six.replaced_bounds(priors, records)
    target_counts = {m.counts for m in targets}
    remainder = tuple(m for m in members if m.counts not in target_counts)
    if (
        len(records) != 6
        or sum(r["represented_vector_count"] for r in records) != 6
        or {v for v in priors if bounds[v] != priors[v]} != target_counts
        or len(remainder) != 1216
        or sum(len(vectors[m.counts]) for m in remainder) != 1319
        or any(bounds[m.counts] != m.final_bound for m in remainder)
    ):
        raise AssertionError("six-member or untouched region coverage failed")
    state_bound = max(bounds.values())
    family = recompute_family(state_bound)
    if (
        max(priors.values())
        != dict((r["stable_id"], r["bound"]) for r in p["FINAL_STATE_TERMS"])[TARGET_STATE_ID]
    ):
        raise AssertionError("six-member State source maximum failed")
    return catalog.normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS",
            "REMAINING_TASK_MODEL": "最強模型",
            "TASK_BRANCH": TASK_BRANCH,
            "COMMON_SOURCE_HEAD": COMMON_SOURCE_HEAD,
            "PRIMARY_BASE_HEAD": PRIMARY_BASE_HEAD,
            "DONOR_HEAD": DONOR_HEAD,
            "SOURCE_AUTHORITY": authority,
            "SOURCE_AUTHORITY_STATUS": "PASS_THREE_IMMUTABLE_IDENTITIES_AND_LINEAGE",
            "DONOR_BYTE_IDENTITY_STATUS": "PASS_THREE_BLOBS_BYTE_EXACT",
            "PRIMARY_CERTIFICATE_PRESERVATION": "PASS_ORIGINAL_THREE_BLOBS_AND_COMPLETE_REPLAY",
            "STATE_ID": TARGET_STATE_ID,
            "REGION_SHA256": REGION_SHA256,
            "REGION_MEMBER_COUNT": len(members),
            "REGION_VECTOR_COUNT": sum(len(v) for v in vectors.values()),
            "SIX_MEMBER_COVERAGE": "PASS_EXACT_SIX_MEMBERS_SIX_DISTINCT_VECTORS",
            "SIX_MEMBER_HUNTER_FLOOR": proof["hunter_floor"],
            "TWELVE_EVENT_PROOF": proof,
            "MEMBER_CERTIFICATES": records,
            "SIX_MEMBER_BOUNDS": [r["member_new_bound"] for r in records],
            "SIX_MEMBER_CURRENT_FOREST_CORRECTIONS": [
                r["vector_certificates"][0]["corrections"]["FOREST"] for r in records
            ],
            "SIX_MEMBER_STATE_UB": state_bound,
            "SIX_MEMBER_STATE_OWNER_IDS": [
                member_id(v) for v, b in bounds.items() if b == state_bound
            ],
            "PRESERVED_MEMBER_COUNT": len(remainder),
            "PRESERVED_VECTOR_COUNT": sum(len(vectors[m.counts]) for m in remainder),
            "PRESERVED_MEMBER_BOUNDS_SHA256": digest(
                tuple((m.counts, m.final_bound) for m in remainder)
            ),
            "PREDECESSOR_CERTIFICATES_SHA256": primary.json_digest(source["MEMBER_CERTIFICATES"]),
            "COMPLETE_UPDATED_BOUNDS_SHA256": digest(
                tuple((m.counts, bounds[m.counts]) for m in members)
            ),
            "COMPLETE_REGION_MEMBERS": [
                {
                    "member_id": member_id(m.counts),
                    "witness_counts": sparse(m.counts),
                    "raw_bound": m.raw_bound,
                    "prior_bound": m.final_bound,
                    "final_bound": bounds[m.counts],
                    "represented_vector_count": len(vectors[m.counts]),
                    "represented_vectors": [sparse(v) for v in vectors[m.counts]],
                    "compression_signature": hunter.eleven.compression_signature(
                        catalog.rebuild_member(m)
                    ),
                }
                for m in members
            ],
            "FORTY_SEVEN_MEMBER_PRESERVATION": "PASS_47_MEMBERS_47_VECTORS_989_MEMBER_REGION",
            "FORTY_SEVEN_MEMBER_STATE_UB": p["FINAL_TARGET_STATE_UB"],
            "FORTY_SEVEN_MEMBER_BOUNDS_SHA256": p["COMPLETE_UPDATED_BOUNDS_SHA256"],
            "FORTY_SEVEN_MEMBER_CERTIFICATES_SHA256": primary.json_digest(p["MEMBER_CERTIFICATES"]),
            "FORTY_SEVEN_MEMBER_TEN_EVENT_FLOOR": p["TEN_EVENT_FLOOR"],
            "FORTY_SEVEN_MEMBER_TWELVE_EVENT_FLOOR": p["TWELVE_EVENT_FLOOR"],
            "CLASSIFIED_DONOR_PRESERVATION": "PASS_ALL_29_LEVELS_183_VECTORS_15_TARGET_VECTORS",
            "CLASSIFIED_LEVEL_CERTIFICATES": d["LEVEL_CERTIFICATES"],
            "COMPLETE_CLASSIFIED_AGGREGATE_LEVELS": d["COMPLETE_AGGREGATE_LEVELS"],
            "PRESERVED_CLASSIFIED_AGGREGATE_LEVEL_COUNT": d["PRESERVED_AGGREGATE_LEVEL_COUNT"],
            "PRESERVED_CLASSIFIED_AGGREGATE_VECTOR_COUNT": d["PRESERVED_AGGREGATE_VECTOR_COUNT"],
            "PRESERVED_CLASSIFIED_EXPLICIT_TERM_COUNT": len(family["explicit"]),
            "PRESERVED_CLASSIFIED_EXPLICIT_TERMS_SHA256": digest(family["explicit"]),
            "FULL_23_STATE_RECOMPUTATION": "PASS",
            "STATE_TERM_COUNT": len(family["states"]),
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["states"]],
            "CLASSIFIED_RECOMPUTATION": "PASS_COMPLETE_AGGREGATE_AND_EXPLICIT_TERM_MAP",
            "CLASSIFIED_TERM_COUNT": len(family["classified"]),
            "FINAL_CLASSIFIED_TERMS": [
                {"stable_id": k, "bound": b} for k, b in family["classified"]
            ],
            "CLASSIFIED_TERMS_SHA256": digest(family["classified"]),
            "FINAL_CLASSIFIED_MAX": family["final"]["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
            "TAIL_RECOMPUTATION": "PASS_SEALED_UNIFORM_CORRECTION_SUBTRACTED_ONCE",
            "TAIL_BOUND": family["tail"],
            "START_FAMILY_MAX_RECOMPUTATION": family["start"],
            "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
            "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
            "FINAL_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
            "CANONICAL_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - r24.INCUMBENT,
            "STRICT_GAIN": int(family["start"]["R3_BOUND"]) - int(family["final"]["R3_BOUND"]),
            "DOUBLE_COUNT_STATUS": "PASS_MAX_SINGLE_REPLACEMENT_AND_COMPONENT_ADOPTION",
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "DUPLICATE_CORRECTIONS": sum(
                r["vector_certificates"][0]["uncorrected_anchor_bound"] - r["member_new_bound"]
                != max(r["vector_certificates"][0]["corrections"].values())
                for r in records
            ),
            "WITNESS_SOUNDNESS_STATUS": (
                "PASS_PRESERVED_COMPONENT_WITNESSES_AND_SIX_LEGAL_TREE_EXTENSIONS"
            ),
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "R7_CENSUS_REBUILD_CALLS": 0,
            "OUTCOME_ENUMERATION_USED": False,
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    verify_source_authority()
    for member in result["MEMBER_CERTIFICATES"]:
        for row in member["vector_certificates"]:
            support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
            if (
                not hunter.r8.validate_support_assignment(dense(row["counts"]), support)
                or digest(support) != row["support_sha256"]
            ):
                raise AssertionError("stored legal support or witness identity failed")
    if result != build_result():
        raise AssertionError("stored joint certificate differs from complete exact replay")
    return {"status": "PASS", "members": 6, "vectors": 6, "states": 23, "classified_terms": 56550}


def encode(result: dict[str, Any]) -> str:
    return hunter.encode(result)


def verify_stored_result() -> dict[str, Any]:
    stored = RESULT_PATH.read_bytes()
    status = verify_result(cast(dict[str, Any], json.loads(stored)))
    if stored != encode(build_result()).encode():
        raise AssertionError("joint result bytes differ from encoded replay")
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
        "SIX_MEMBER_HUNTER_FLOOR",
        "SIX_MEMBER_BOUNDS",
        "SIX_MEMBER_STATE_UB",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "REMAINING_GAP",
        "STRICT_GAIN",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
