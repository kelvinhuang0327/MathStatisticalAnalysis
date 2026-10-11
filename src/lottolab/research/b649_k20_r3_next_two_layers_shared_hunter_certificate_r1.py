"""Shared nine-event Hunter certificates for the next two preserved R3 layers.

Every recovered vector has nine type-0 tickets, entirely outside the anchors.
Their 54 incidences on 40 labels force at least 14 pair collisions.  Reuse the
sealed Hunter theorem and exact counter, recounting only the four (0,0) rows.
The three nested-threshold cases certify one common integer correction; a
subset tree extends to the other residual events with nonnegative edge costs.
Replace the existing correction by its max with this floor, then take the
weakest represented vector per compressed member.  Replay all 1,427 members
and all 23 State terms, preserving the earlier certificates, Tail and aggregate.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from functools import cache
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_preserved_eleven_hunter_certificate_r1 as prior

TASK_ID = "B649_K20_R3_NEXT_TWO_LAYERS_SHARED_HUNTER_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-next-two-layers-shared-hunter-certificate-r1"
BASE_HEAD = "d9c35887e24f46be7abe615c9f3e0d6e60b01f90"
BASE_TREE = "39ff9b74e767ae16580409a7f91b02fbc3bfbc08"
BASE_RESULT_SHA256 = "386fb32251551fa09b152beb973b2bbcf1e86e8fa6159fddda2b04004b3038f0"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    prior.six.RESULTS + "b649-k20-r3-next-two-layers-shared-hunter-certificate-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
UPSTREAM_SHA256 = {
    **prior.UPSTREAM_SHA256,
    prior.RESULT_RELATIVE: BASE_RESULT_SHA256,
    "src/lottolab/research/b649_k20_r3_preserved_eleven_hunter_certificate_r1.py": (
        "28c80d2da1fa5a26d10b5005a2eb337c4d09389d36c545afced40adb8895957b"
    ),
}
CORRECTION_COMBINATION = "MAX(R6_PAIR, FOREST, EXISTING_R14, EXISTING_HUNTER, NINE_EVENT_HUNTER)"
CountVector = prior.CountVector
LedgerMember = prior.catalog.LedgerMember


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        name: sha256((REPO_ROOT / name).read_bytes()).hexdigest() for name in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError("immutable source fingerprint mismatch")
    return observed


@cache
def source_authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads((REPO_ROOT / prior.RESULT_RELATIVE).read_text()))
    if stored["TASK_ID"] != prior.TASK_ID or prior.verify_result(stored)["status"] != "PASS":
        raise AssertionError("prior Hunter certificate failed replay")
    return stored


def current_member_bounds(members: tuple[LedgerMember, ...]) -> dict[CountVector, int]:
    authority = source_authority()
    earlier = prior.current_member_bounds(members)
    bounds = prior.six.replaced_bounds(earlier, authority["MEMBER_CERTIFICATES"])
    replay = [
        {
            "member_id": prior.member_id(m.counts),
            "witness_counts": prior.sparse(m.counts),
            "represented_vector_count": m.represented_vector_count,
            "raw_bound": m.raw_bound,
            "prior_bound": earlier[m.counts],
            "final_bound": bounds[m.counts],
        }
        for m in members
    ]
    if authority["COMPLETE_REGION_MEMBERS"] != prior.catalog.normalized(replay):
        raise AssertionError("source catalog differs from its replay")
    return bounds


def target_layers(
    members: tuple[LedgerMember, ...], bounds: dict[CountVector, int]
) -> tuple[tuple[LedgerMember, ...], tuple[LedgerMember, ...]]:
    """Select the two largest distinct current bounds, never numeric bound inputs."""

    if set(bounds) != {m.counts for m in members}:
        raise AssertionError("source region coverage mismatch")
    levels = sorted(set(bounds.values()), reverse=True)[:2]
    if len(levels) != 2:
        raise AssertionError("two preserved layers are required")
    layers = tuple(tuple(m for m in members if bounds[m.counts] == level) for level in levels)
    previous = {
        prior.dense(row["witness_counts"])
        for rows in (
            *prior.earlier_certificates().values(),
            source_authority()["MEMBER_CERTIFICATES"],
        )
        for row in rows
    } | set(prior.six.sealed_top_band_bounds())
    if any(
        len(layer) != 11
        or sum(m.represented_vector_count for m in layer) != 12
        or any(m.counts in previous or bounds[m.counts] != m.raw_bound for m in layer)
        or any(m.final_bound != m.raw_bound for m in layer)
        for layer in layers
    ):
        raise AssertionError("two-layer coverage or preserved correction identity failed")
    return layers[0], layers[1]


def threshold_cases(
    floors: prior.Cells, collision_mass: int, event_count: int
) -> list[dict[str, Any]]:
    """Partition by the largest positive threshold; e1 >= ceil(Q / k)."""

    if collision_mass <= 0 or event_count < 2:
        raise ValueError("positive collision mass and at least two events required")
    cases: list[dict[str, Any]] = []
    for threshold in range(1, prior.family_pair_overlap_ceiling() + 1):
        e1 = (collision_mass + threshold - 1) // threshold
        ranks = (prior.rank_floor(e1), int(threshold >= 2), int(threshold >= 3))
        cases.append(
            {
                "case": ("e2=e3=0", "e2>0,e3=0", "e3>0")[threshold - 1],
                "e1_lower_bound": e1,
                "rank_lower_bounds": list(ranks),
                "hunter_floor": prior.tree_weight_floor(floors, ranks, event_count),
            }
        )
    return cases


@cache
def nine_event_proof() -> dict[str, Any]:
    cells = prior.type_cells(0)
    if cells != (0, 0, 0, prior.TICKET_SIZE):
        raise AssertionError("type-0 events are not entirely outside the anchors")
    rows = prior.exact_pair_rows(((0, 0),))
    floors = prior.pair_floors(rows)
    prior.require_safe_pair_floors(floors, rows)
    if len(rows) != prior.family_pair_overlap_ceiling() + 1 or any(
        prior.six.residual_pair_intersection(row[0], row[1], (row[2], row[3], row[4], row[5]))
        != row[6]
        for row in rows
    ):
        raise AssertionError("type-0 exact pair identity failed")
    event_count = 9
    incidences = event_count * cells[3]
    label_count = len(prior.CELL_LABELS[3])
    quotient, remainder = divmod(incidences, label_count)
    mass = prior.balanced_collision_mass(incidences, label_count)
    cases = threshold_cases(floors, mass, event_count)
    floor = min(int(row["hunter_floor"]) for row in cases)
    relaxation = prior.minimum_tree_correction(floors, mass, event_count)
    if floor != relaxation.correction:
        raise AssertionError("three-case proof differs from exact integer Hunter relaxation")
    return {
        "event_count": event_count,
        "type_index": 0,
        "type_cells": list(cells),
        "residual_event_definition": prior.RESIDUAL_EVENT_DEFINITION,
        "residual_event_size": prior.residual_event_size(0),
        "outside_incidences": incidences,
        "outside_label_count": label_count,
        "balanced_frequencies": [[quotient, label_count - remainder], [quotient + 1, remainder]],
        "collision_mass_floor": mass,
        "pair_rows": [list(row) for row in rows],
        "pair_floors": list(floors),
        "threshold_cases": cases,
        "hunter_floor": floor,
        "integer_minimizer": {
            "edge_counts": list(relaxation.edge_counts),
            "rank_floors": list(relaxation.rank_floors),
            "feasible_threshold_triples": relaxation.census_size,
        },
        "theorem_source": prior.TASK_ID,
        "extension_rule": "Extend subset tree to all residual events with nonnegative edges",
    }


def witness_analysis(
    vector: CountVector, support: tuple[tuple[int, ...], ...], proof: dict[str, Any]
) -> dict[str, Any]:
    n = int(proof["event_count"])
    subset = support[:n]
    if not prior.r8.validate_support_assignment(vector, support) or any(
        len(ticket) != prior.TICKET_SIZE or not set(ticket) <= set(prior.CELL_LABELS[3])
        for ticket in subset
    ):
        raise AssertionError("nine-event support witness is invalid")
    subset_vector = tuple(n if index == 0 else 0 for index in range(len(vector)))
    floors: prior.Cells = cast(prior.Cells, tuple(proof["pair_floors"]))
    rows = prior.exact_pair_rows(((0, 0),))
    values = {(row[0], row[1], (row[2], row[3], row[4], row[5])): row[6] for row in rows}
    witness = prior.witness_analysis(subset_vector, subset, floors, values)
    overlaps = {(a, b): len(set(subset[a]) & set(subset[b])) for a, b in combinations(range(n), 2)}
    subset_tree = prior.threshold_tree(n, overlaps)
    extended_tree = (*subset_tree, *((0, index) for index in range(n, len(support))))
    if (
        witness["collision_mass"] < proof["collision_mass_floor"]
        or witness["exact_tree_weight"] < witness["phi_tree_weight"]
        or witness["phi_tree_weight"] < proof["hunter_floor"]
        or prior.graph_rank(len(support), extended_tree) != len(support) - 1
        or len(extended_tree) != len(support) - 1
    ):
        raise AssertionError("witness contradicts the nine-event Hunter proof")
    return {**witness, "subset_tree": subset_tree, "extended_tree": extended_tree}


def certify_vector(
    member: LedgerMember, vector: CountVector, prior_bound: int, proof: dict[str, Any]
) -> dict[str, Any]:
    state = prior.catalog.rebuild_member(member)
    vector_state = prior.catalog.rebuild_member(
        replace(member, counts=vector, represented_vector_count=1)
    )
    n = int(proof["event_count"])
    if (
        prior.eleven.compression_signature(vector_state)
        != prior.eleven.compression_signature(state)
        or vector[0] != n
        or sum(vector) != prior.RESIDUAL_EVENT_COUNT
        or prior_bound != member.raw_bound
    ):
        raise AssertionError("represented vector compression or nine-event identity failed")
    # These preserved members carry no R14 or Hunter credit; all earlier batches
    # are excluded by target_layers and are preserved verbatim in the result.
    corrections = {
        "R6_PAIR": vector_state.residual_pair_union_penalty,
        "FOREST": vector_state.complementary_forest_floor,
        "EXISTING_R14": 0,
        "EXISTING_HUNTER": 0,
        "NINE_EVENT_HUNTER": int(proof["hunter_floor"]),
    }
    existing = prior.combine_corrections(
        {key: value for key, value in corrections.items() if key != "NINE_EVENT_HUNTER"}
    )
    uncorrected = (
        prior.r14.joint_constant() - vector_state.anchor_pair_s2 + vector_state.anchor_triple_s3
    )
    residual_sum = sum(
        count * prior.residual_event_size(index) for index, count in enumerate(vector) if count
    )
    combined = prior.combine_corrections(corrections)
    bound = prior.member_bound(uncorrected, combined)
    if (
        prior.anchor_union_size() + residual_sum != uncorrected
        or vector_state.applied_residual_union_penalty != existing
        or uncorrected - existing != prior_bound
        or bound >= prior_bound
    ):
        raise AssertionError("event identity or single correction replacement failed")
    support = prior.r12.construct_support_witness(vector)
    if support is None:
        raise AssertionError("represented vector has no exact support witness")
    witness = witness_analysis(vector, support, proof)
    return {
        "vector_id": prior.member_id(vector),
        "counts": prior.sparse(vector),
        "nine_event_indices": list(range(n)),
        "nine_event_types": [0] * n,
        "outside_incidences": n * prior.type_cells(0)[3],
        "collision_mass_floor": proof["collision_mass_floor"],
        "anchor_union": prior.anchor_union_size(),
        "residual_event_sum": residual_sum,
        "uncorrected_anchor_bound": uncorrected,
        "corrections": corrections,
        "prior_applied_correction": existing,
        "combined_correction": combined,
        "vector_new_bound": bound,
        "support_witness": support,
        "support_sha256": prior.digest(support),
        "witness_analysis": witness,
    }


def certify_member(
    member: LedgerMember, vectors: tuple[CountVector, ...], prior_bound: int, proof: dict[str, Any]
) -> dict[str, Any]:
    if (
        len(vectors) != member.represented_vector_count
        or len(set(vectors)) != len(vectors)
        or tuple(sorted(vectors)) != vectors
        or min(vectors) != member.counts
    ):
        raise AssertionError("compressed member does not cover its exact represented vectors")
    records = [certify_vector(member, vector, prior_bound, proof) for vector in vectors]
    correction = prior.member_correction(tuple(int(row["combined_correction"]) for row in records))
    bound = max(int(row["vector_new_bound"]) for row in records)
    if bound != prior.member_bound(int(records[0]["uncorrected_anchor_bound"]), correction):
        raise AssertionError("compressed member did not take the weakest vector correction")
    return {
        "member_id": prior.member_id(member.counts),
        "witness_counts": prior.sparse(member.counts),
        "represented_vector_count": len(vectors),
        "represented_vectors": [prior.sparse(vector) for vector in vectors],
        "vector_certificates": records,
        "member_prior_bound": prior_bound,
        "member_raw_bound": member.raw_bound,
        "member_certified_correction": correction,
        "member_new_bound": bound,
        "correction_combination": CORRECTION_COMBINATION,
    }


def recompute_family(state_bound: int) -> dict[str, Any]:
    authority = source_authority()
    # Reuse the established full family replay, replacing its target State with
    # our current source maximum before recording this task's starting maximum.
    family = prior.recompute_family(state_bound)
    terms = tuple(
        (str(row["stable_id"]), int(row["bound"])) for row in authority["FINAL_STATE_TERMS"]
    )
    classified = prior.six.classified_terms()
    start = prior.six.tail.family_maximum(family["tail_bound"], terms, classified)
    if (
        len(terms) != 23
        or len(dict(terms)) != 23
        or start != authority["FINAL_FAMILY_MAX_RECOMPUTATION"]
    ):
        raise AssertionError("starting complete 23-State family differs from source")
    return {**family, "start": start, "start_terms": terms}


def build_result() -> dict[str, Any]:
    fingerprints = verify_upstream_fingerprints()
    authority = source_authority()
    members = prior.six.region_members()
    priors = current_member_bounds(members)
    layers = target_layers(members, priors)
    cohort = layers[0] + layers[1]
    recovered = prior.catalog.r17.represented_vectors(
        tuple(prior.catalog.rebuild_member(m) for m in cohort)
    )
    flat = [vector for vectors in recovered.values() for vector in vectors]
    if (
        set(recovered) != {m.counts for m in cohort}
        or len(set(flat)) != len(flat)
        or len(flat) != 24
    ):
        raise AssertionError("exact 22-member/24-vector coverage failed")
    proof = nine_event_proof()
    records = [certify_member(m, recovered[m.counts], priors[m.counts], proof) for m in cohort]
    bounds = prior.six.replaced_bounds(priors, records)
    certified = {m.counts for m in cohort}
    preserved = {counts: bound for counts, bound in priors.items() if counts not in certified}
    if any(bounds[counts] != bound for counts, bound in preserved.items()):
        raise AssertionError("a preserved remainder bound changed")
    family = recompute_family(max(bounds.values()))
    if max(priors.values()) != dict(family["start_terms"])[prior.TARGET_STATE_ID]:
        raise AssertionError("source State maximum differs from region maximum")
    layer_rows = [
        {
            "prior_max": max(priors[m.counts] for m in layer),
            "new_max": max(bounds[m.counts] for m in layer),
            "member_count": len(layer),
            "represented_vector_count": sum(m.represented_vector_count for m in layer),
            "member_ids": [prior.member_id(m.counts) for m in layer],
        }
        for layer in layers
    ]
    result = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS",
        "REMAINING_TASK_MODEL": "最強模型",
        "TASK_BRANCH": TASK_BRANCH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
        "STATE_ID": prior.TARGET_STATE_ID,
        "REGION_SHA256": prior.catalog.region_fingerprint(members),
        "REGION_COMPRESSED_MEMBER_COUNT": len(members),
        "REGION_REPRESENTED_VECTOR_COUNT": sum(m.represented_vector_count for m in members),
        "LAYERS": layer_rows,
        "FIRST_LAYER_COVERAGE": [
            layer_rows[0]["member_count"],
            layer_rows[0]["represented_vector_count"],
        ],
        "SECOND_LAYER_COVERAGE": [
            layer_rows[1]["member_count"],
            layer_rows[1]["represented_vector_count"],
        ],
        "COHORT_MEMBER_COUNT": len(records),
        "REPRESENTED_VECTOR_COUNT": len(flat),
        "NINE_EVENT_PROOF": proof,
        "NINE_EVENT_PROOF_STATUS": "PASS",
        "COLLISION_MASS_STATUS": "PASS",
        "HUNTER_FLOOR": proof["hunter_floor"],
        "MEMBER_CERTIFICATES": records,
        "EARLIER_HUNTER_CERTIFICATES": authority["MEMBER_CERTIFICATES"],
        "EARLIER_R14_CERTIFICATES": prior.eleven_authority()["MEMBER_CERTIFICATES"],
        "EARLIER_SIX_R14_CERTIFICATES": prior.eleven_authority()["ORIGINAL_SIX_CERTIFICATES"],
        "EARLIER_TOP_BAND_CERTIFICATES_SHA256": prior.digest(
            tuple(sorted(prior.six.sealed_top_band_bounds().items()))
        ),
        "PRESERVED_MEMBER_COUNT": len(preserved),
        "PRESERVED_REMAINDER_MAX": max(preserved.values()),
        "COMPLETE_REGION_MEMBERS": [
            {
                "member_id": prior.member_id(m.counts),
                "witness_counts": prior.sparse(m.counts),
                "represented_vector_count": m.represented_vector_count,
                "raw_bound": m.raw_bound,
                "prior_bound": priors[m.counts],
                "final_bound": bounds[m.counts],
            }
            for m in members
        ],
        "NEW_FIRST_LAYER_MAX": layer_rows[0]["new_max"],
        "NEW_SECOND_LAYER_MAX": layer_rows[1]["new_max"],
        "FINAL_STATE_BOUND": max(bounds.values()),
        "START_STATE_TERMS": [{"stable_id": key, "bound": b} for key, b in family["start_terms"]],
        "FINAL_STATE_TERMS": [{"stable_id": key, "bound": b} for key, b in family["terms"]],
        "STATE_TERM_COUNT": len(family["terms"]),
        "FULL_23_STATE_RECOMPUTATION": "PASS",
        "NEXT_COMPETING_STATE": family["competitor"],
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
        "CURRENT_INCUMBENT": prior.catalog.r24.INCUMBENT,
        "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - prior.catalog.r24.INCUMBENT,
        "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
        "NON_DUPLICATE_CREDIT_STATUS": "PASS_MAX_SINGLE_REPLACEMENT",
        "DUPLICATE_CORRECTIONS": 0,
        "WITNESS_SOUNDNESS_STATUS": "PASS_24_EXACT_SUPPORT_WITNESSES",
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "PUSH_PR_MERGE": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }
    return prior.catalog.normalized(result)


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    verify_upstream_fingerprints()
    for member in result["MEMBER_CERTIFICATES"]:
        for row in member["vector_certificates"]:
            vector = prior.dense(row["counts"])
            support = tuple(
                tuple(int(label) for label in ticket) for ticket in row["support_witness"]
            )
            if (
                not prior.r8.validate_support_assignment(vector, support)
                or prior.digest(support) != row["support_sha256"]
            ):
                raise AssertionError("stored support witness or its fingerprint is invalid")
    if result != build_result():
        raise AssertionError("stored certificate differs from complete exact replay")
    return {"status": "PASS", "certificates": 22, "vectors": 24}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    options = parser.parse_args()
    if options.verify:
        result = cast(dict[str, Any], json.loads(RESULT_PATH.read_text(encoding="utf-8")))
        print(json.dumps(verify_result(result), sort_keys=True))
        return
    result = build_result()
    if options.write:
        RESULT_PATH.write_text(prior.encode(result), encoding="utf-8")
    keys = (
        "TASK_STATUS",
        "HUNTER_FLOOR",
        "NEW_FIRST_LAYER_MAX",
        "NEW_SECOND_LAYER_MAX",
        "FINAL_STATE_BOUND",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "REMAINING_GAP",
    )
    print(json.dumps({key: result[key] for key in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
