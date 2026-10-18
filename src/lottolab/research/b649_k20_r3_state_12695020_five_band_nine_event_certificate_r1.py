"""Nine-event Hunter certificates for all five highest bands of State 12695020.

Recover the complete immutable R24 region at its exact losses and compression
signatures. Reproduce the shared nine-event theorem from exact residual pairs,
balanced collisions and nested threshold forest ranks. Certify every vector of
the five bands, extend its tree to all eighteen events, and replace the existing
correction by max. Preserve every other member and all sealed certificates;
recompute the complete 23-State, classified and Tail Family from its bound map.
No census, solver, portfolio search or official-outcome enumeration runs.
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

from lottolab.research import b649_k20_r3_t6_two_member_eleven_event_hunter_r1 as prior
from lottolab.research import b649_k20_r3_type0_ge9_shared_hunter_family_r1 as shared

hunter, catalog, six = prior.hunter, prior.catalog, prior.six
r24 = catalog.r24
LedgerMember = catalog.LedgerMember
type CountVector = tuple[int, ...]
dense, sparse, digest, member_id = prior.dense, prior.sparse, prior.digest, prior.member_id
TASK_ID = "B649_K20_R3_STATE_12695020_FIVE_BAND_NINE_EVENT_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-state-12695020-five-band-nine-event-certificate-r1"
BASE_HEAD = "cda19c6da7d9a93fd120df6797652700e2893a21"
BASE_TREE = "8eab0f498383beb5ad6cb3ffe1d73067d41fa885"
BASE_RESULT_SHA256 = "56d48e21ce83f62da991c6b98f8d1d1b1970755fd1fb66e417acaa030bd77e96"
BASE_MODULE_RELATIVE = "src/lottolab/research/b649_k20_r3_t6_two_member_eleven_event_hunter_r1.py"
BASE_MODULE_SHA256 = "4483ad5e379d4ce3bbbcff072cc33fe98e47f41f20f8f4e1d04a7c4185cd74b0"
TARGET_STATE_ID = "state:s2-12695020-s3-735532"
REGION_SHA256 = "46023fc93f2fd7d9b211d29494d05d8f6bfd4867992b0121cd8db0b7def5cd5b"
EVENT_COUNT, BAND_COUNT = 9, 5
RESIDUAL_EVENT_DEFINITION = "R_i = E_i \\ (E_A \u222a E_B)"
CORRECTION_COMBINATION = "MAX(R6_PAIR, FOREST, CARRIED_VALID, NINE_EVENT_HUNTER)"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    six.RESULTS + "b649-k20-r3-state-12695020-five-band-nine-event-certificate-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
UPSTREAM_SHA256 = {
    **prior.UPSTREAM_SHA256,
    **shared.UPSTREAM_SHA256,
    **catalog.UPSTREAM_SHA256,
    **r24.UPSTREAM_SHA256,
    **r24.CARRIED_SHA256,
    prior.RESULT_RELATIVE: BASE_RESULT_SHA256,
    BASE_MODULE_RELATIVE: BASE_MODULE_SHA256,
    "src/lottolab/research/b649_k20_r3_type0_ge9_shared_hunter_family_r1.py": (
        "7c21d9860fa622f870726a17c178aaa63a0a6e30ef120b257a512417251086e7"
    ),
}


def verify_upstream_fingerprints() -> dict[str, str]:
    """Reject donor tampering even when all mathematical caches are warm."""

    observed = {p: sha256((REPO_ROOT / p).read_bytes()).hexdigest() for p in UPSTREAM_SHA256}
    if observed != UPSTREAM_SHA256:
        raise AssertionError("immutable source fingerprint mismatch")
    return observed


def verify_base_authority() -> dict[str, str]:
    prefix = ["git", "-C", str(REPO_ROOT)]
    tree = subprocess.check_output([*prefix, "rev-parse", f"{BASE_HEAD}^{{tree}}"], text=True)
    if tree.strip() != BASE_TREE:
        raise AssertionError("immutable base HEAD/TREE identity failed")
    for path, expected in (
        (prior.RESULT_RELATIVE, BASE_RESULT_SHA256),
        (BASE_MODULE_RELATIVE, BASE_MODULE_SHA256),
    ):
        blob = subprocess.check_output([*prefix, "show", f"{BASE_HEAD}:{path}"])
        if sha256(blob).hexdigest() != expected:
            raise AssertionError("immutable base certificate object failed")
    return {"HEAD": BASE_HEAD, "TREE": BASE_TREE, "RESULT_SHA256": BASE_RESULT_SHA256}


@cache
def source_authority() -> dict[str, Any]:
    verify_base_authority()
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads((REPO_ROOT / prior.RESULT_RELATIVE).read_text()))
    if (
        stored["TASK_ID"] != prior.TASK_ID
        or stored["FINAL_OWNER_IDS"] != [TARGET_STATE_ID]
        or prior.verify_stored_result()["status"] != "PASS"
    ):
        raise AssertionError("immutable predecessor identity or byte replay failed")
    return stored


@cache
def carried_certificates() -> tuple[tuple[str, CountVector, int, str], ...]:
    """Reuse all 335 sealed target certificates, without new R14 refinement."""

    rows = list(r24.carried_member_certificates(TARGET_STATE_ID))
    for record in catalog.r24_authority()["STATE_OWNER_CERTIFICATES"]:
        if record["owner_id"] != TARGET_STATE_ID:
            continue
        for witness in record["support_witnesses"]:
            vector = dense(witness["counts"])
            support = tuple(tuple(int(x) for x in t) for t in witness["support_witness"])
            if not hunter.r8.validate_support_assignment(vector, support):
                raise AssertionError("sealed R24 support witness failed")
        rows.append(
            (
                "R24",
                dense(record["member"]["witness_counts"]),
                int(record["member_new_bound"]),
                str(record["region_sha256"]),
            )
        )
    if len(rows) != 335 or len({r[1] for r in rows}) != len(rows):
        raise AssertionError("sealed target certificate coverage failed")
    return tuple(rows)


@cache
def region_members() -> tuple[LedgerMember, ...]:
    """Verify the exact R24 ledger, its digest, multiplicities and carried bounds."""

    verify_upstream_fingerprints()
    authority = source_authority()
    sealed = catalog.r24_authority()
    regions = [r for r in sealed["STATE_REGION_CERTIFICATES"] if r["owner_id"] == TARGET_STATE_ID]
    entries = [
        r for r in sealed["CARRIED_OWNER_REGION_CERTIFICATES"] if r["owner_id"] == TARGET_STATE_ID
    ]
    if len(regions) != 1 or len(entries) != 1:
        raise AssertionError("unique complete R24 target-region ledger required")
    region, entry = regions[0], entries[0]
    members = tuple(
        LedgerMember(
            dense(row["witness_counts"]),
            int(row["represented_vector_count"]),
            int(row["raw_bound"]),
            int(row["final_bound"]),
        )
        for row in region["complete_region_members"]
    )
    certified = {counts: bound for _, counts, bound, _ in carried_certificates()}
    if (
        len(members) != 1222
        or len({m.counts for m in members}) != len(members)
        or sum(m.represented_vector_count for m in members) != 1325
        or catalog.region_fingerprint(members) != REGION_SHA256
        or region["region_sha256"] != REGION_SHA256
        or entry["region_sha256"] != REGION_SHA256
        or entry["region_compressed_member_count"] != len(members)
        or entry["region_type_vector_count"] != 1325
        or any(region_id != REGION_SHA256 for _, _, _, region_id in carried_certificates())
        or not set(certified) <= {m.counts for m in members}
        or any(
            m.represented_vector_count < 1
            or m.final_bound > m.raw_bound
            or m.final_bound != certified.get(m.counts, m.raw_bound)
            for m in members
        )
        or sum(m.final_bound < m.raw_bound for m in members) != region["certified_member_count"]
        or region["certified_member_count"] != len(certified)
        or max(m.final_bound for m in members) != region["final_state_bound"]
        or max(m.final_bound for m in members)
        != dict((r["stable_id"], r["bound"]) for r in authority["FINAL_STATE_TERMS"])[
            TARGET_STATE_ID
        ]
    ):
        raise AssertionError("complete target-region identity, coverage or sealed bounds failed")
    return members


@cache
def represented_vectors() -> dict[CountVector, tuple[CountVector, ...]]:
    members = region_members()
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in members))
    flat = [v for vectors in recovered.values() for v in vectors]
    if (
        set(recovered) != {m.counts for m in members}
        or len(flat) != 1325
        or len(set(flat)) != len(flat)
        or any(len(recovered[m.counts]) != m.represented_vector_count for m in members)
    ):
        raise AssertionError("complete represented-vector coverage failed")
    for member in members:
        vectors = recovered[member.counts]
        if tuple(sorted(vectors)) != vectors or min(vectors) != member.counts:
            raise AssertionError("represented-vector canonical identity failed")
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(member))
        for vector in vectors:
            rebuilt = catalog.rebuild_member(
                replace(member, counts=vector, represented_vector_count=1)
            )
            if (
                hunter.eleven.compression_signature(rebuilt) != signature
                or len(vector) != len(member.counts)
                or sum(vector) != hunter.RESIDUAL_EVENT_COUNT
                or min(vector) < 0
            ):
                raise AssertionError("represented-vector compression signature failed")
    return recovered


def target_bands(
    members: tuple[LedgerMember, ...],
) -> tuple[tuple[int, tuple[LedgerMember, ...]], ...]:
    levels = sorted({m.final_bound for m in members}, reverse=True)[:BAND_COUNT]
    bands = tuple((b, tuple(m for m in members if m.final_bound == b)) for b in levels)
    if len(bands) != BAND_COUNT or any(
        len(rows) != 9
        or sum(m.represented_vector_count for m in rows) != 10
        or sum(m.represented_vector_count == 2 for m in rows) != 1
        or any(m.final_bound != m.raw_bound or m.counts[0] != EVENT_COUNT for m in rows)
        for _, rows in bands
    ):
        raise AssertionError("exact five-band 45-member/50-vector coverage failed")
    return bands


def nine_event_proof() -> dict[str, Any]:
    """Reproduce the theorem; the floor is an output of the threshold argument."""

    if (
        hunter.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.eleven.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.type_cells(0) != (0, 0, 0, hunter.TICKET_SIZE)
    ):
        raise AssertionError("source residual-event definition or type-0 identity failed")
    rows = hunter.exact_pair_rows(((0, 0),))
    ceiling = hunter.family_pair_overlap_ceiling()
    if len(rows) != ceiling + 1 or {r[2:6] for r in rows} != {
        (0, 0, 0, k) for k in range(ceiling + 1)
    }:
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
    incidences, labels = EVENT_COUNT * hunter.type_cells(0)[3], len(hunter.CELL_LABELS[3])
    quotient, remainder = divmod(incidences, labels)
    mass = hunter.balanced_collision_mass(incidences, labels)
    if (
        mass != (labels - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)
        or mass != incidences - labels
    ):
        raise AssertionError("balanced outside collision floor failed")
    rank_rows = hunter.verify_rank_floor_algebra(EVENT_COUNT)
    cases: list[dict[str, Any]] = []
    for threshold in range(1, ceiling + 1):
        edges = -(-mass // threshold)
        ranks = (hunter.rank_floor(edges), int(threshold >= 2), int(threshold >= 3))
        cases.append(
            {
                "case": ("e2=e3=0", "e2>0,e3=0", "e3>0")[threshold - 1],
                "e1_lower_bound": edges,
                "rank_lower_bounds": list(ranks),
                "hunter_floor": hunter.tree_weight_floor(floors, ranks, EVENT_COUNT),
            }
        )
    floor = min(int(r["hunter_floor"]) for r in cases)
    relaxation = hunter.minimum_tree_correction(floors, mass, EVENT_COUNT)
    if floor != relaxation.correction:
        raise AssertionError("nested threshold forest-rank Hunter inequality failed")
    inherited = shared.nine_event_proof()
    proof = {
        **inherited,
        "event_count": EVENT_COUNT,
        "type_cells": list(hunter.type_cells(0)),
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "residual_event_size": hunter.residual_event_size(0),
        "outside_incidences": incidences,
        "outside_label_count": labels,
        "balanced_frequencies": [[quotient, labels - remainder], [quotient + 1, remainder]],
        "collision_mass_floor": mass,
        "pair_rows": [list(r) for r in rows],
        "pair_floors": list(floors),
        "pair_overlap_ceiling": ceiling,
        "threshold_cases": cases,
        "rank_algebra_rows": rank_rows,
        "hunter_floor": floor,
        "integer_minimizer": {
            "edge_counts": list(relaxation.edge_counts),
            "rank_floors": list(relaxation.rank_floors),
            "feasible_threshold_triples": relaxation.census_size,
        },
        "floor_algebra": [
            (EVENT_COUNT - 1) * floors[0],
            hunter.rank_floor(mass),
            floors[1] - floors[0],
            floor,
        ],
    }
    if proof != inherited:
        raise AssertionError("shared nine-event theorem differs from independent derivation")
    return proof


@cache
def support_witness(vector: CountVector) -> tuple[tuple[int, ...], ...]:
    support = hunter.r12.construct_support_witness(vector)
    if support is None or not hunter.r8.validate_support_assignment(vector, support):
        raise AssertionError("represented vector has no valid support witness")
    return support


def certify_vector(
    member: LedgerMember, vector: CountVector, proof: dict[str, Any]
) -> dict[str, Any]:
    targets = tuple(m for _, rows in target_bands(region_members()) for m in rows)
    if (
        member not in targets
        or vector not in represented_vectors()[member.counts]
        or vector[0] != EVENT_COUNT
        or proof != nine_event_proof()
    ):
        raise AssertionError("represented vector or nine-event applicability failed")
    state = catalog.rebuild_member(replace(member, counts=vector, represented_vector_count=1))
    signature = hunter.eleven.compression_signature(state)
    types = tuple(i for i, n in enumerate(vector) for _ in range(n))
    ceiling = hunter.family_pair_overlap_ceiling()
    if (
        signature != hunter.eleven.compression_signature(catalog.rebuild_member(member))
        or len(types) != hunter.RESIDUAL_EVENT_COUNT
        or types[:EVENT_COUNT] != (0,) * EVENT_COUNT
    ):
        raise AssertionError("represented vector compression signature or event identity failed")
    for index in set(types):
        s, a, b, outside = hunter.type_cells(index)
        if s + a + b + outside != hunter.TICKET_SIZE or max(s + a, s + b) > ceiling:
            raise AssertionError("residual event type violates source anchor identity")
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    residual_sum = sum(n * hunter.residual_event_size(i) for i, n in enumerate(vector) if n)
    corrections = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "CARRIED_VALID": uncorrected - member.final_bound,
        "NINE_EVENT_HUNTER": int(proof["hunter_floor"]),
    }
    existing = hunter.combine_corrections(
        {k: v for k, v in corrections.items() if k != "NINE_EVENT_HUNTER"}
    )
    combined = hunter.combine_corrections(corrections)
    bound = hunter.member_bound(uncorrected, combined)
    if (
        hunter.anchor_union_size() + residual_sum != uncorrected
        or state.applied_residual_union_penalty
        != max(corrections["R6_PAIR"], corrections["FOREST"])
        or uncorrected - state.applied_residual_union_penalty != member.raw_bound
        or existing != uncorrected - member.final_bound
        or combined != max(corrections.values())
        or bound != uncorrected - combined
        or bound >= member.final_bound
    ):
        raise AssertionError("event arithmetic or max single correction replacement failed")
    support = support_witness(vector)
    witness = shared.prior.prior.witness_analysis(vector, support, proof)
    subset = tuple(frozenset(t) for t in support[:EVENT_COUNT])
    label_mass = sum(comb(sum(x in t for t in subset), 2) for x in hunter.CELL_LABELS[3])
    full_weight = 0
    tree = cast(tuple[tuple[int, int], ...], witness["extended_tree"])
    for left, right in tree:
        overlaps = tuple(
            len(set(support[left]) & set(support[right]) & set(c)) for c in hunter.CELL_LABELS
        )
        cost = six.residual_pair_intersection(
            types[left], types[right], cast(tuple[int, int, int, int], overlaps)
        )
        if cost < 0:
            raise AssertionError("tree extension has a negative residual edge")
        full_weight += cost
    if (
        not hunter.r8.validate_support_assignment(vector, support)
        or any(not t <= set(hunter.CELL_LABELS[3]) for t in subset)
        or label_mass != sum(len(a & b) for a, b in combinations(subset, 2))
        or label_mass != witness["collision_mass"]
        or label_mass < proof["collision_mass_floor"]
        or full_weight < witness["phi_tree_weight"]
        or witness["phi_tree_weight"] < combined
    ):
        raise AssertionError("support collision or full Hunter tree extension failed")
    return {
        "vector_id": member_id(vector),
        "counts": sparse(vector),
        "compression_signature": signature,
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "type0_count": vector[0],
        "applicability_status": "PASS",
        "nine_event_indices": list(range(EVENT_COUNT)),
        "nine_event_types": list(types[:EVENT_COUNT]),
        "outside_incidences": EVENT_COUNT * hunter.type_cells(0)[3],
        "collision_mass_floor": proof["collision_mass_floor"],
        "pair_overlap_ceiling": ceiling,
        "anchor_union": hunter.anchor_union_size(),
        "residual_event_sum": residual_sum,
        "uncorrected_anchor_bound": uncorrected,
        "corrections": corrections,
        "prior_applied_correction": existing,
        "combined_correction": combined,
        "vector_new_bound": bound,
        "support_witness": support,
        "support_sha256": digest(support),
        "witness_analysis": {**witness, "extended_tree_exact_weight": full_weight},
    }


def certify_member(
    member: LedgerMember, vectors: tuple[CountVector, ...], proof: dict[str, Any]
) -> dict[str, Any]:
    if (
        vectors != represented_vectors()[member.counts]
        or len(vectors) != member.represented_vector_count
    ):
        raise AssertionError("exact represented-vector member coverage failed")
    rows = [certify_vector(member, v, proof) for v in vectors]
    correction = hunter.member_correction(tuple(int(r["combined_correction"]) for r in rows))
    bound = max(int(r["vector_new_bound"]) for r in rows)
    if (
        correction != min(r["combined_correction"] for r in rows)
        or len({r["uncorrected_anchor_bound"] for r in rows}) != 1
        or bound != hunter.member_bound(int(rows[0]["uncorrected_anchor_bound"]), correction)
    ):
        raise AssertionError("compressed member did not use its weakest vector correction")
    return catalog.normalized(
        {
            "member_id": member_id(member.counts),
            "witness_counts": sparse(member.counts),
            "represented_vector_count": len(vectors),
            "represented_vectors": [sparse(v) for v in vectors],
            "compression_signature": hunter.eleven.compression_signature(
                catalog.rebuild_member(member)
            ),
            "vector_certificates": rows,
            "member_prior_bound": member.final_bound,
            "member_raw_bound": member.raw_bound,
            "member_certified_correction": correction,
            "member_new_bound": bound,
            "correction_combination": CORRECTION_COMBINATION,
        }
    )


def recompute_family(state_bound: int) -> dict[str, Any]:
    authority = source_authority()
    terms = tuple((str(r["stable_id"]), int(r["bound"])) for r in authority["FINAL_STATE_TERMS"])
    classified, tail = six.classified_terms(), six.sealed_tail_bound()
    aggregate = [{"stable_id": k, "bound": b} for k, b in classified if k == r24.AGGREGATE_ID]
    start = six.tail.family_maximum(tail, terms, classified)
    if (
        len(terms) != 23
        or len(dict(terms)) != 23
        or TARGET_STATE_ID not in dict(terms)
        or len(classified) != authority["CLASSIFIED_TERM_COUNT"]
        or digest(classified) != authority["CLASSIFIED_TERMS_SHA256"]
        or aggregate != authority["CLASSIFIED_AGGREGATE"]
        or tail != authority["TAIL_BOUND"]
        or start != authority["FINAL_FAMILY_MAX_RECOMPUTATION"]
    ):
        raise AssertionError("complete 23-State, classified aggregate or Tail source replay failed")
    replaced = tuple((k, state_bound if k == TARGET_STATE_ID else b) for k, b in terms)
    final = six.tail.family_maximum(tail, replaced, classified)
    all_terms = (*replaced, (r24.TAIL_ID, tail), *classified)
    maximum = max(b for _, b in all_terms)
    owners = sorted(k for k, b in all_terms if b == maximum)
    if (
        final["STATE_MAX_BOUND"] != max(b for _, b in replaced)
        or final["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] != max(b for _, b in classified)
        or final["R3_BOUND"] != maximum
        or final["OWNER_IDS"] != owners
    ):
        raise AssertionError("independent full Family maximum or owner recomputation failed")
    return {
        "start": start,
        "final": final,
        "start_terms": terms,
        "terms": replaced,
        "tail_bound": tail,
        "classified_count": len(classified),
        "classified_sha256": digest(classified),
        "aggregate": aggregate,
    }


def build_result() -> dict[str, Any]:
    fingerprints, identity = verify_upstream_fingerprints(), verify_base_authority()
    members, vectors, proof = region_members(), represented_vectors(), nine_event_proof()
    bands = target_bands(members)
    records = [certify_member(m, vectors[m.counts], proof) for _, rows in bands for m in rows]
    priors = {m.counts: m.final_bound for m in members}
    bounds = six.replaced_bounds(priors, records)
    targets = {m.counts for _, rows in bands for m in rows}
    if {v for v in priors if bounds[v] != priors[v]} != targets:
        raise AssertionError("exactly the five-band member bounds must change")
    remainder = tuple(m for m in members if m.counts not in targets)
    if any(bounds[m.counts] != m.final_bound for m in remainder) or any(
        bounds[v] != b for _, v, b, _ in carried_certificates()
    ):
        raise AssertionError("preserved remainder or sealed certificate changed")
    state_bound = max(bounds.values())
    if state_bound != max(
        [*(int(r["member_new_bound"]) for r in records), *(m.final_bound for m in remainder)]
    ):
        raise AssertionError("independent complete State maximum failed")
    family = recompute_family(state_bound)
    if max(priors.values()) != dict(family["start_terms"])[TARGET_STATE_ID]:
        raise AssertionError("source region maximum differs from State term")
    band_rows = [
        {
            "prior_bound": b,
            "member_ids": [member_id(m.counts) for m in rows],
            "member_count": len(rows),
            "vector_count": sum(len(vectors[m.counts]) for m in rows),
            "new_bound": max(bounds[m.counts] for m in rows),
        }
        for b, rows in bands
    ]
    return catalog.normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS",
            "REMAINING_TASK_MODEL": "最強模型",
            "TASK_BRANCH": TASK_BRANCH,
            "BASE_HEAD": BASE_HEAD,
            "BASE_TREE": BASE_TREE,
            "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
            "BASE_MODULE_SHA256": BASE_MODULE_SHA256,
            "IMMUTABLE_BASE_VERIFICATION": identity,
            "SOURCE_AUTHORITY_STATUS": "PASS_IMMUTABLE_OBJECTS_FINGERPRINTS_AND_BYTE_REPLAY",
            "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
            "STATE_ID": TARGET_STATE_ID,
            "REGION_IDENTITY": catalog.region_fingerprint(members),
            "REGION_SHA256": REGION_SHA256,
            "REGION_COMPRESSED_MEMBER_COUNT": len(members),
            "REGION_REPRESENTED_VECTOR_COUNT": sum(len(v) for v in vectors.values()),
            "REGION_COVERAGE_STATUS": "PASS_1222_MEMBERS_1325_DISTINCT_VECTORS_REPLAYED",
            "ALL_REPRESENTED_VECTORS_SHA256": digest(
                tuple((m.counts, vectors[m.counts]) for m in members)
            ),
            "FIVE_BANDS": band_rows,
            "FIVE_BAND_MEMBER_COUNT": len(records),
            "FIVE_BAND_VECTOR_COUNT": sum(r["represented_vector_count"] for r in records),
            "DOUBLE_VECTOR_MEMBER_IDS": [
                r["member_id"] for r in records if r["represented_vector_count"] == 2
            ],
            "DOUBLE_VECTOR_MEMBER_COVERAGE": "PASS_FIVE_MEMBERS_TEN_VECTORS",
            "NINE_EVENT_PROOF": proof,
            "NINE_EVENT_PROOF_STATUS": "PASS_EXACT_PAIRS_COLLISIONS_NESTED_THRESHOLD_TREE",
            "HUNTER_CORRECTION_FLOOR": proof["hunter_floor"],
            "MEMBER_CERTIFICATES": records,
            "NEW_FIVE_BAND_BOUNDS": [r["new_bound"] for r in band_rows],
            "NEW_FIVE_BAND_MAX": max(r["new_bound"] for r in band_rows),
            "PREVIOUS_SEALED_MEMBER_COUNT": len(carried_certificates()),
            "PREVIOUS_SEALED_CERTIFICATES_SHA256": digest(carried_certificates()),
            "PREVIOUS_CERTIFICATE_STATUS": "PASS_ALL_335_BOUNDS_AND_SEALED_SOURCE_BYTES_PRESERVED",
            "ALL_CARRIED_CERTIFICATES_SHA256": {
                p: h for p, h in fingerprints.items() if p.endswith(".json")
            },
            "PRESERVED_MEMBER_COUNT": len(remainder),
            "PRESERVED_VECTOR_COUNT": sum(len(vectors[m.counts]) for m in remainder),
            "PRESERVED_REMAINDER_MAX": max(bounds[m.counts] for m in remainder),
            "PRESERVED_MEMBER_BOUNDS_SHA256": digest(
                tuple(
                    (m.counts, m.represented_vector_count, m.raw_bound, bounds[m.counts])
                    for m in remainder
                )
            ),
            "COMPLETE_UPDATED_BOUNDS_SHA256": digest(
                tuple((m.counts, bounds[m.counts]) for m in members)
            ),
            "COMPLETE_REGION_MEMBERS": [
                {
                    "member_id": member_id(m.counts),
                    "witness_counts": sparse(m.counts),
                    "represented_vector_count": len(vectors[m.counts]),
                    "represented_vectors": [sparse(v) for v in vectors[m.counts]],
                    "compression_signature": hunter.eleven.compression_signature(
                        catalog.rebuild_member(m)
                    ),
                    "raw_bound": m.raw_bound,
                    "prior_bound": priors[m.counts],
                    "final_bound": bounds[m.counts],
                }
                for m in members
            ],
            "START_STATE_BOUND": max(priors.values()),
            "FINAL_TARGET_STATE_UB": state_bound,
            "FINAL_STATE_MEMBER_IDS": [member_id(v) for v, b in bounds.items() if b == state_bound],
            "START_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["start_terms"]],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["terms"]],
            "STATE_TERM_COUNT": len(family["terms"]),
            "FULL_23_STATE_RECOMPUTATION": "PASS",
            "TAIL_BOUND": family["tail_bound"],
            "CLASSIFIED_TERM_COUNT": family["classified_count"],
            "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
            "CLASSIFIED_AGGREGATE": family["aggregate"],
            "CLASSIFIED_MAX": family["final"]["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
            "START_FAMILY_MAX_RECOMPUTATION": family["start"],
            "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
            "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
            "FINAL_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
            "CURRENT_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - r24.INCUMBENT,
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_SINGLE_REPLACEMENT",
            "DUPLICATE_CORRECTIONS": sum(
                row["uncorrected_anchor_bound"] - row["vector_new_bound"]
                != max(row["corrections"].values())
                for r in records
                for row in r["vector_certificates"]
            ),
            "WITNESS_SOUNDNESS_STATUS": "PASS_50_LEGAL_SUPPORTS_AND_FULL_HUNTER_TREE_EXTENSIONS",
            "R7_CENSUS_REBUILD_CALLS": 0,
            "OUTCOME_ENUMERATION_USED": False,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    """Reject source, applicability, coverage, witness, bound and Family tampering."""

    verify_upstream_fingerprints()
    for member in result["MEMBER_CERTIFICATES"]:
        for row in member["vector_certificates"]:
            vector = dense(row["counts"])
            support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
            if (
                not hunter.r8.validate_support_assignment(vector, support)
                or digest(support) != row["support_sha256"]
            ):
                raise AssertionError("stored support witness or fingerprint is invalid")
    if result != build_result():
        raise AssertionError("stored certificate differs from complete exact replay")
    return {
        "status": "PASS",
        "members": 45,
        "vectors": 50,
        "region_members": 1222,
        "region_vectors": 1325,
    }


def encode(result: dict[str, Any]) -> str:
    return hunter.encode(result)


def verify_stored_result() -> dict[str, Any]:
    stored = RESULT_PATH.read_bytes()
    status = verify_result(cast(dict[str, Any], json.loads(stored)))
    if stored != encode(build_result()).encode():
        raise AssertionError("stored result bytes differ from encoded replay")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    options = parser.parse_args()
    if options.verify:
        print(json.dumps(verify_stored_result(), sort_keys=True))
        return
    result = build_result()
    if options.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    keys = (
        "TASK_STATUS",
        "FIVE_BAND_MEMBER_COUNT",
        "FIVE_BAND_VECTOR_COUNT",
        "HUNTER_CORRECTION_FLOOR",
        "NEW_FIVE_BAND_BOUNDS",
        "PRESERVED_REMAINDER_MAX",
        "FINAL_TARGET_STATE_UB",
        "START_COMPLETE_R3_UB",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
