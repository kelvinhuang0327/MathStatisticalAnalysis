"""Standalone nine-event Hunter certificate for five Classified R12 levels.

Recover the aggregate's complete 29-level/183-vector ledger from sealed R12
losses, excluding exactly the three previously split levels. Certify all fifteen
vectors of the five highest levels, replacing residual credits by MAX once.
Preserve the 24 remaining levels, all 56,549 explicit classified terms, all 23
States and Tail. This component alone does not lower the complete R3 Family UB.
No R7 census, new classification, heavy solver or outcome enumeration runs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from functools import cache
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_state_12695020_five_band_nine_event_certificate_r1 as nine
from lottolab.research import b649_k20_r3_state_13169800_four_band_ten_event_hunter_r1 as prior

hunter, catalog, six, r24 = prior.hunter, prior.catalog, prior.six, prior.r24
r12, r6, r5, r16 = r24.r12, r24.r6, r24.r5, r24.r16
type CountVector = tuple[int, ...]
dense, sparse, digest = prior.dense, prior.sparse, prior.digest
TASK_ID = "B649_K20_R3_CLASSIFIED_R12_FIVE_LEVEL_NINE_EVENT_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-classified-r12-five-level-nine-event-certificate-r1"
BASE_HEAD = "5cfacd03b1026274577f6647083684b53b00bcae"
BASE_TREE = "fd5a8b3cf7aafe4617afad620ccfce196ee9b8ca"
BASE_RESULT_SHA256 = "f059ab046a75a3c7790ae979a84ff323d44a8e7e605ee1a6042e206b6d34c06a"
BASE_MODULE_RELATIVE = (
    "src/lottolab/research/b649_k20_r3_state_13169800_four_band_ten_event_hunter_r1.py"
)
BASE_MODULE_SHA256 = "4305d1b22d63dd93c5e3267ef420751457cfe087ea052204aee40a7f1dd5e736"
TARGET_ORDINALS = (25, 26, 27, 30, 32)
EVENT_COUNT = 9
RESIDUAL_EVENT_DEFINITION = "R_i = E_i \\ (E_A \u222a E_B)"
CORRECTION_COMBINATION = "MAX(R6_PAIR, FOREST, CARRIED_VALID, NINE_EVENT_HUNTER)"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    six.RESULTS + "b649-k20-r3-classified-r12-five-level-nine-event-certificate-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
UPSTREAM_SHA256 = {
    **prior.UPSTREAM_SHA256,
    **nine.UPSTREAM_SHA256,
    prior.RESULT_RELATIVE: BASE_RESULT_SHA256,
    BASE_MODULE_RELATIVE: BASE_MODULE_SHA256,
    "src/lottolab/research/b649_k20_r3_state_12695020_five_band_nine_event_certificate_r1.py": (
        "e674001380fc6e6de456be1f441f3354286dd6764e717465ac3d08f623aedd1c"
    ),
}


@dataclass(frozen=True)
class ClassifiedLevel:
    """One immutable aggregate level, with every vector recovered at its loss."""

    ordinal: int
    loss: int
    vectors: tuple[CountVector, ...]
    prior_bounds: tuple[int, ...]
    prior_corrections: tuple[int, ...]
    source_row: dict[str, Any]

    @property
    def prior_bound(self) -> int:
        return max(self.prior_bounds)


def verify_upstream_fingerprints() -> dict[str, str]:
    """Recheck immutable executing sources and results despite warm caches."""

    observed = {p: sha256((REPO_ROOT / p).read_bytes()).hexdigest() for p in UPSTREAM_SHA256}
    if observed != UPSTREAM_SHA256:
        raise AssertionError("immutable source fingerprint mismatch")
    return observed


def verify_base_authority() -> dict[str, str]:
    prefix = ["git", "-C", str(REPO_ROOT)]
    head = subprocess.check_output([*prefix, "rev-parse", BASE_HEAD], text=True).strip()
    tree = subprocess.check_output([*prefix, "rev-parse", f"{BASE_HEAD}^{{tree}}"], text=True)
    if head != BASE_HEAD or tree.strip() != BASE_TREE:
        raise AssertionError("immutable base HEAD/TREE identity failed")
    for path, expected in (
        (prior.RESULT_RELATIVE, BASE_RESULT_SHA256),
        (BASE_MODULE_RELATIVE, BASE_MODULE_SHA256),
    ):
        blob = subprocess.check_output([*prefix, "show", f"{BASE_HEAD}:{path}"])
        if sha256(blob).hexdigest() != expected:
            raise AssertionError("immutable base certificate object failed")
    return {"HEAD": head, "TREE": tree.strip(), "RESULT_SHA256": BASE_RESULT_SHA256}


@cache
def source_authority() -> dict[str, Any]:
    verify_base_authority()
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads((REPO_ROOT / prior.RESULT_RELATIVE).read_text()))
    if stored["TASK_ID"] != prior.TASK_ID or prior.verify_stored_result()["status"] != "PASS":
        raise AssertionError("immutable predecessor identity or byte replay failed")
    return stored


def canonical_baseline() -> int:
    """Derive the zero-loss baseline without the legacy R11 spectrum rebuild."""

    size0 = hunter.residual_event_size(0)
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    if losses != tuple(size0 - hunter.residual_event_size(i) for i in range(len(losses))):
        raise AssertionError("exact residual-size differences disagree with local losses")
    return hunter.anchor_union_size() + r12.OUTSIDE_TICKET_COUNT * size0


@cache
def aggregate_levels() -> tuple[ClassifiedLevel, ...]:
    """Recover all 183 vectors; parameterization never supplies census coverage."""

    verify_upstream_fingerprints()
    source = source_authority()
    sealed = cast(dict[str, Any], json.loads((REPO_ROOT / r24.R12_RESULT_RELATIVE).read_text()))
    rows = cast(list[dict[str, Any]], sealed["LOSS_LEVEL_ROWS"])
    splits = {int(r16.R12_OWNER_LOSS)} | {
        int(r["recovered_level"]) for r in catalog.r24_authority()["R12_AGGREGATE_RECOVERIES"]
    }
    if (
        sealed["TASK_ID"] != r12.TASK_ID
        or len(rows) != 32
        or [r["ordinal"] for r in rows] != list(range(1, 33))
        or len({r["local_loss"] for r in rows}) != 32
        or splits != {int(rows[i]["local_loss"]) for i in (0, 1, 23)}
    ):
        raise AssertionError("sealed R12 level identity or prior split coverage failed")
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    baseline = canonical_baseline()
    levels: list[ClassifiedLevel] = []
    for row in rows:
        loss = int(row["local_loss"])
        if loss in splits:
            continue
        vectors = tuple(
            sorted(r16.iter_interval_vectors(losses, r12.OUTSIDE_TICKET_COUNT, loss, loss))
        )
        envelopes = tuple(r6.type_count_envelope(v) for v in vectors)
        corrections = tuple(e.combined_pair_penalty for e in envelopes)
        bounds = tuple(baseline - loss - c for c in corrections)
        if (
            not vectors
            or len(vectors) != len(set(vectors))
            or len(vectors) != row["vector_count"]
            or row["witness_realized"] != len(vectors)
            or row["eliminated"] != 0
            or row["unwitnessed"] != 0
            or any(
                len(v) != len(losses)
                or min(v) < 0
                or sum(v) != r12.OUTSIDE_TICKET_COUNT
                or r12.local_loss(v, losses) != loss
                or e.local_loss != loss
                or e.combined_pair_penalty != max(e.pair_union_penalty, e.prior_forest_penalty)
                for v, e in zip(vectors, envelopes, strict=True)
            )
            or max(bounds) != row["maximum_vector_bound"]
            or min(corrections) != row["minimum_correction"]
        ):
            raise AssertionError(
                "complete R12 vector coverage, exact loss or existing credits failed"
            )
        levels.append(ClassifiedLevel(int(row["ordinal"]), loss, vectors, bounds, corrections, row))
    flat = [v for level in levels for v in level.vectors]
    aggregate = [{"stable_id": r24.AGGREGATE_ID, "bound": max(r.prior_bound for r in levels)}]
    if (
        len(levels) != 29
        or len(flat) != len(set(flat))
        or len(flat) != 183
        or aggregate != source["CLASSIFIED_AGGREGATE"]
    ):
        raise AssertionError("complete 29-level/183-vector aggregate identity failed")
    return tuple(levels)


def target_levels(levels: tuple[ClassifiedLevel, ...]) -> tuple[ClassifiedLevel, ...]:
    """Select the highest five sealed levels, then check exact vector identities."""

    targets = tuple(sorted(levels, key=lambda r: (-r.prior_bound, r.ordinal))[:5])
    if tuple(r.ordinal for r in targets) != TARGET_ORDINALS:
        raise AssertionError("exact five target levels failed")
    for k, level in enumerate(targets):
        expected: set[CountVector] = set()
        for a in range(3):
            v = [0] * len(r5.anchor_incidence_profiles())
            v[0], v[1], v[4], v[5], v[16] = 9, a, 2 - a, 7 - k, k
            expected.add(tuple(v))
        if (
            level not in aggregate_levels()
            or level.loss != 6_709_724 + 448 * k
            or len(level.vectors) != 3
            or set(level.vectors) != expected
            or set(level.prior_corrections) != {2_870_000}
            or set(level.prior_bounds) != {int(level.source_row["maximum_vector_bound"])}
        ):
            raise AssertionError(
                "exact fifteen-vector target loss or existing credit identity failed"
            )
    return targets


def nine_event_proof() -> dict[str, Any]:
    """Recount residual pairs, balanced collisions and the complete rank relaxation.

    Hunter follows pointwise: a tree induced by k present events has at most
    k-1 edges. Descending Kruskal retains a forest of every nested overlap graph
    G_j. If its components have ranks r_i, e_j <= sum C(r_i+1,2)
    <= C(sum r_i+1,2), so rank(G_j) >= rho(e_j). Outside frequencies give
    Q=sum_x C(d_x,2)=e1+e2+e3>=54-40=14. Minimize the weighted rank bound over
    every admissible nested threshold triple, without requiring realizability.
    """

    if hunter.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION or hunter.type_cells(0) != (
        0,
        0,
        0,
        hunter.TICKET_SIZE,
    ):
        raise AssertionError("source residual-event or type-0 identity failed")
    ceiling = hunter.family_pair_overlap_ceiling()
    rows = hunter.exact_pair_rows(((0, 0),))
    if ceiling != 3 or tuple(r[2:6] for r in rows) != tuple((0, 0, 0, k) for k in range(4)):
        raise AssertionError("complete exact pair row coverage failed")
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
            raise AssertionError("independent residual pair inclusion/exclusion failed")
    floors = hunter.pair_floors(rows)
    hunter.require_safe_pair_floors(floors, rows)
    outside = set(range(hunter.POOL_SIZE)) - set(hunter.ANCHOR_A | hunter.ANCHOR_B)
    labels, incidences = len(outside), EVENT_COUNT * hunter.type_cells(0)[3]
    quotient, remainder = divmod(incidences, labels)
    mass = (labels - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)
    if (
        outside != set(hunter.CELL_LABELS[3])
        or labels != 40
        or incidences != 54
        or mass != hunter.balanced_collision_mass(incidences, labels)
        or mass != incidences - labels
    ):
        raise AssertionError("balanced outside collision floor failed")
    capacity = comb(EVENT_COUNT, 2)
    ranks = tuple(
        next(r for r in range(EVENT_COUNT) if comb(r + 1, 2) >= e) for e in range(capacity + 1)
    )
    rank_rows = hunter.verify_rank_floor_algebra(EVENT_COUNT)
    if rank_rows != capacity + 1 or any(hunter.rank_floor(e) != r for e, r in enumerate(ranks)):
        raise AssertionError("independent threshold-rank identity failed")
    candidates: list[tuple[int, tuple[int, int, int]]] = []
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 >= mass:
                    rho = (ranks[e1], ranks[e2], ranks[e3])
                    weight = (EVENT_COUNT - 1) * floors[0] + sum(
                        (floors[k + 1] - floors[k]) * rho[k] for k in range(ceiling)
                    )
                    if weight != hunter.tree_weight_floor(floors, rho, EVENT_COUNT):
                        raise AssertionError("nested-threshold weight identity failed")
                    candidates.append((weight, (e1, e2, e3)))
    relaxation = hunter.minimum_tree_correction(floors, mass, EVENT_COUNT)
    floor, minimizing_edges = min(candidates)
    inherited = nine.nine_event_proof()
    if (
        floor != relaxation.correction
        or minimizing_edges != relaxation.edge_counts
        or len(candidates) != relaxation.census_size
        or floor != inherited["hunter_floor"]
        or list(floors) != inherited["pair_floors"]
        or [list(r) for r in rows] != inherited["pair_rows"]
        or mass != inherited["collision_mass_floor"]
    ):
        raise AssertionError("complete nine-event Hunter minimum failed")
    return {
        **inherited,
        "outside_labels": sorted(outside),
        "all_admissible_threshold_cases": len(candidates),
        "floor_method": "FULL_EXACT_INTEGER_MINIMIZATION",
    }


@cache
def support_witness(vector: CountVector) -> tuple[tuple[int, ...], ...]:
    support = r12.construct_support_witness(vector)
    if support is None or not hunter.r8.validate_support_assignment(vector, support):
        raise AssertionError("represented vector has no legal support witness")
    return support


def certify_vector(
    level: ClassifiedLevel, vector: CountVector, proof: dict[str, Any]
) -> dict[str, Any]:
    if (
        level not in target_levels(aggregate_levels())
        or vector not in level.vectors
        or vector[0] != EVENT_COUNT
        or proof != nine_event_proof()
    ):
        raise AssertionError("target level, vector or nine-event applicability failed")
    envelope = r6.type_count_envelope(vector)
    baseline = canonical_baseline()
    uncorrected = baseline - level.loss
    prior_bound = level.prior_bounds[level.vectors.index(vector)]
    types = tuple(i for i, n in enumerate(vector) for _ in range(n))
    residual_sum = sum(n * hunter.residual_event_size(i) for i, n in enumerate(vector) if n)
    corrections = {
        "R6_PAIR": envelope.pair_union_penalty,
        "FOREST": envelope.prior_forest_penalty,
        "CARRIED_VALID": uncorrected - prior_bound,
        "NINE_EVENT_HUNTER": int(proof["hunter_floor"]),
    }
    existing = hunter.combine_corrections(
        {k: v for k, v in corrections.items() if k != "NINE_EVENT_HUNTER"}
    )
    combined = hunter.combine_corrections(corrections)
    bound = hunter.member_bound(uncorrected, combined)
    if (
        envelope.local_loss != level.loss
        or types[:EVENT_COUNT] != (0,) * EVENT_COUNT
        or len(types) != hunter.RESIDUAL_EVENT_COUNT
        or hunter.anchor_union_size() + residual_sum != uncorrected
        or existing != envelope.combined_pair_penalty
        or uncorrected - existing != prior_bound
        or combined != max(corrections.values())
        or bound != uncorrected - combined
        or bound >= prior_bound
    ):
        raise AssertionError("exact loss, residual arithmetic or MAX single correction failed")
    support = support_witness(vector)
    witness = nine.shared.prior.prior.witness_analysis(vector, support, proof)
    subset = tuple(frozenset(t) for t in support[:EVENT_COUNT])
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
        not hunter.r8.validate_support_assignment(vector, support)
        or any(not t <= set(proof["outside_labels"]) for t in subset)
        or mass != sum(len(a & b) for a, b in combinations(subset, 2))
        or mass != witness["collision_mass"]
        or mass < proof["collision_mass_floor"]
        or len(tree) != hunter.graph_rank(len(support), tree)
        or len(tree) != len(support) - 1
        or full_weight < witness["phi_tree_weight"]
        or witness["phi_tree_weight"] < combined
    ):
        raise AssertionError("legal support collision or full Hunter tree extension failed")
    return catalog.normalized(
        {
            "vector_id": r24.r13.vector_id(vector, level.loss),
            "ordinal": level.ordinal,
            "counts": sparse(vector),
            "exact_loss": level.loss,
            "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
            "type0_count": vector[0],
            "applicability_status": "PASS",
            "nine_event_indices": list(range(EVENT_COUNT)),
            "nine_event_types": list(types[:EVENT_COUNT]),
            "anchor_union": hunter.anchor_union_size(),
            "residual_event_sum": residual_sum,
            "uncorrected_anchor_bound": uncorrected,
            "corrections": corrections,
            "prior_applied_correction": existing,
            "combined_correction": combined,
            "vector_prior_bound": prior_bound,
            "vector_new_bound": bound,
            "support_witness": support,
            "support_sha256": digest(support),
            "witness_analysis": {**witness, "extended_tree_exact_weight": full_weight},
        }
    )


def certify_level(
    level: ClassifiedLevel, vectors: tuple[CountVector, ...], proof: dict[str, Any]
) -> dict[str, Any]:
    if vectors != level.vectors or len(vectors) != 3 or len(set(vectors)) != 3:
        raise AssertionError("complete distinct represented-vector coverage failed")
    records = [certify_vector(level, v, proof) for v in vectors]
    correction = hunter.member_correction(tuple(int(r["combined_correction"]) for r in records))
    bound = max(int(r["vector_new_bound"]) for r in records)
    if correction != min(r["combined_correction"] for r in records) or bound != (
        records[0]["uncorrected_anchor_bound"] - correction
    ):
        raise AssertionError("level must take its weakest vector correction")
    return {
        "ordinal": level.ordinal,
        "exact_loss": level.loss,
        "source_level_row": level.source_row,
        "represented_vector_count": len(vectors),
        "represented_vectors": [sparse(v) for v in vectors],
        "vector_certificates": records,
        "level_prior_bound": level.prior_bound,
        "level_certified_correction": correction,
        "level_new_bound": bound,
        "correction_combination": CORRECTION_COMBINATION,
    }


def replace_aggregate(
    terms: tuple[tuple[str, int], ...], bound: int
) -> tuple[tuple[str, int], ...]:
    if (
        len(terms) != 56_550
        or len(dict(terms)) != len(terms)
        or r24.AGGREGATE_ID not in dict(terms)
    ):
        raise AssertionError("complete classified term identity or coverage failed")
    updated = tuple((k, bound if k == r24.AGGREGATE_ID else b) for k, b in terms)
    if [(k, b) for k, b in updated if k != r24.AGGREGATE_ID] != [
        (k, b) for k, b in terms if k != r24.AGGREGATE_ID
    ] or {k for (k, b), (_, new) in zip(terms, updated, strict=True) if b != new} != {
        r24.AGGREGATE_ID
    }:
        raise AssertionError("all explicit classified terms must be preserved")
    return updated


def recompute_family(aggregate_bound: int) -> dict[str, Any]:
    source = source_authority()
    states = tuple((str(r["stable_id"]), int(r["bound"])) for r in source["FINAL_STATE_TERMS"])
    classified, tail = six.classified_terms(), six.sealed_tail_bound()
    start = six.tail.family_maximum(tail, states, classified)
    if (
        len(states) != len(dict(states))
        or len(states) != 23
        or len(classified) != source["CLASSIFIED_TERM_COUNT"]
        or digest(classified) != source["CLASSIFIED_TERMS_SHA256"]
        or tail != source["TAIL_BOUND"]
        or start != source["FINAL_FAMILY_MAX_RECOMPUTATION"]
    ):
        raise AssertionError("complete source 23-State/classified/Tail replay failed")
    updated = replace_aggregate(classified, aggregate_bound)
    final = six.tail.family_maximum(tail, states, updated)
    terms = (*states, (r24.TAIL_ID, tail), *updated)
    maximum = max(b for _, b in terms)
    if (
        final["STATE_MAX_BOUND"] != max(b for _, b in states)
        or final["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] != max(b for _, b in updated)
        or final["R3_BOUND"] != maximum
        or final["OWNER_IDS"] != sorted(k for k, b in terms if b == maximum)
    ):
        raise AssertionError("independent standalone complete Family maximum failed")
    explicit = tuple((k, b) for k, b in classified if k != r24.AGGREGATE_ID)
    return {
        "states": states,
        "tail": tail,
        "start": start,
        "final": final,
        "classified_count": len(updated),
        "classified_sha256": digest(updated),
        "explicit_count": len(explicit),
        "explicit_sha256": digest(explicit),
        "explicit_max": max(b for _, b in explicit),
    }


def build_result() -> dict[str, Any]:
    fingerprints, identity = verify_upstream_fingerprints(), verify_base_authority()
    levels = aggregate_levels()
    targets, proof = target_levels(levels), nine_event_proof()
    certificates = [certify_level(level, level.vectors, proof) for level in targets]
    target_bounds = {int(r["ordinal"]): int(r["level_new_bound"]) for r in certificates}
    bounds = {r.ordinal: target_bounds.get(r.ordinal, r.prior_bound) for r in levels}
    remainder = tuple(r for r in levels if r.ordinal not in target_bounds)
    if (
        {r.ordinal for r in levels if bounds[r.ordinal] != r.prior_bound} != set(TARGET_ORDINALS)
        or len(remainder) != 24
        or sum(len(r.vectors) for r in remainder) != 168
        or any(bounds[r.ordinal] != r.prior_bound for r in remainder)
    ):
        raise AssertionError("exact five changed levels and all other aggregate levels failed")
    aggregate_bound = max(bounds.values())
    family = recompute_family(aggregate_bound)
    source = source_authority()
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
            "CLASSIFIED_LEVEL_COVERAGE": "PASS_ALL_29_LEVELS_183_DISTINCT_VECTORS",
            "AGGREGATE_ID": r24.AGGREGATE_ID,
            "AGGREGATE_LEVEL_COUNT": len(levels),
            "AGGREGATE_VECTOR_COUNT": sum(len(r.vectors) for r in levels),
            "AGGREGATE_VECTORS_SHA256": digest(tuple((r.ordinal, r.vectors) for r in levels)),
            "TARGET_VECTOR_COVERAGE": "PASS_FIVE_LEVELS_15_DISTINCT_VECTORS",
            "TARGET_LEVEL_ORDINALS": [r.ordinal for r in targets],
            "TARGET_VECTOR_COUNT": sum(len(r.vectors) for r in targets),
            "LEVEL_CERTIFICATES": certificates,
            "NINE_EVENT_PROOF": proof,
            "PAIR_COST_STATUS": "PASS_TWO_INDEPENDENT_EXACT_RESIDUAL_COUNTERS",
            "HUNTER_APPLICABILITY_STATUS": "PASS_ALL_15_TYPE0_NINE_EVENT_SUBSETS",
            "HUNTER_FLOOR_STATUS": "PASS_EXACT_COLLISION_AND_COMPLETE_THRESHOLD_RANK_MINIMUM",
            "HUNTER_CORRECTION_FLOOR": proof["hunter_floor"],
            "NEW_CLASSIFIED_LEVEL_BOUNDS": [target_bounds[r.ordinal] for r in targets],
            "PRESERVED_AGGREGATE_LEVEL_COUNT": len(remainder),
            "PRESERVED_AGGREGATE_VECTOR_COUNT": sum(len(r.vectors) for r in remainder),
            "PRESERVED_AGGREGATE_MAX": max(bounds[r.ordinal] for r in remainder),
            "PRESERVED_AGGREGATE_SHA256": digest(
                tuple((r.ordinal, r.loss, r.vectors, r.prior_bounds) for r in remainder)
            ),
            "COMPLETE_AGGREGATE_LEVELS": [
                {
                    "ordinal": r.ordinal,
                    "exact_loss": r.loss,
                    "source_level_row": r.source_row,
                    "represented_vector_count": len(r.vectors),
                    "represented_vectors": [sparse(v) for v in r.vectors],
                    "vector_prior_bounds": r.prior_bounds,
                    "vector_prior_corrections": r.prior_corrections,
                    "level_prior_bound": r.prior_bound,
                    "level_final_bound": bounds[r.ordinal],
                }
                for r in levels
            ],
            "START_AGGREGATE_MAX": max(r.prior_bound for r in levels),
            "FINAL_R12_AGGREGATE_MAX": aggregate_bound,
            "CLASSIFIED_TERM_COUNT": family["classified_count"],
            "CLASSIFIED_TERMS_ACCOUNTED": family["explicit_count"] + 1,
            "START_CLASSIFIED_TERMS_SHA256": source["CLASSIFIED_TERMS_SHA256"],
            "FINAL_CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
            "PRESERVED_EXPLICIT_CLASSIFIED_TERM_COUNT": family["explicit_count"],
            "START_EXPLICIT_CLASSIFIED_TERMS_SHA256": family["explicit_sha256"],
            "FINAL_EXPLICIT_CLASSIFIED_TERMS_SHA256": family["explicit_sha256"],
            "EXPLICIT_CLASSIFIED_PRESERVATION_STATUS": "PASS_ALL_56549_ORDERED_TERMS_UNCHANGED",
            "CLASSIFIED_TERMS_CHANGED": 1,
            "NEXT_EXPLICIT_CLASSIFIED_MAX": family["explicit_max"],
            "FINAL_CLASSIFIED_MAX": family["final"]["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
            "START_STATE_TERMS": source["FINAL_STATE_TERMS"],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["states"]],
            "STATE_TERM_COUNT": len(family["states"]),
            "STATE_PRESERVATION_STATUS": "PASS_ALL_23_STATES_UNCHANGED",
            "TAIL_BOUND": family["tail"],
            "TAIL_PRESERVATION_STATUS": "PASS_UNCHANGED",
            "START_FAMILY_MAX_RECOMPUTATION": family["start"],
            "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
            "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
            "FINAL_STANDALONE_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "STANDALONE_FAMILY_DISPOSITION": "COMPLETE_R3_UB_UNCHANGED_STATE_OWNER_PRESERVED",
            "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
            "CURRENT_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - r24.INCUMBENT,
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_SINGLE_REPLACEMENT",
            "DUPLICATE_CORRECTIONS": sum(
                v["uncorrected_anchor_bound"] - v["vector_new_bound"]
                != max(v["corrections"].values())
                for r in certificates
                for v in r["vector_certificates"]
            ),
            "WITNESS_SOUNDNESS_STATUS": "PASS_15_LEGAL_SUPPORTS_AND_FULL_HUNTER_TREE_EXTENSIONS",
            "R7_CENSUS_REBUILD_CALLS": 0,
            "NEW_CLASSIFICATION_CALLS": 0,
            "OUTCOME_ENUMERATION_USED": False,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    """Reject altered identities, coverage, levels, credits, supports or maxima."""

    verify_upstream_fingerprints()
    for level in result["LEVEL_CERTIFICATES"]:
        for row in level["vector_certificates"]:
            vector = dense(row["counts"])
            support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
            if (
                not hunter.r8.validate_support_assignment(vector, support)
                or digest(support) != row["support_sha256"]
            ):
                raise AssertionError("stored support witness or fingerprint is invalid")
    if result != build_result():
        raise AssertionError("stored certificate differs from complete exact replay")
    return {"status": "PASS", "levels": 5, "vectors": 15, "classified_terms": 56_550}


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
        "TARGET_VECTOR_COUNT",
        "HUNTER_CORRECTION_FLOOR",
        "NEW_CLASSIFIED_LEVEL_BOUNDS",
        "PRESERVED_AGGREGATE_MAX",
        "FINAL_CLASSIFIED_MAX",
        "START_COMPLETE_R3_UB",
        "FINAL_STANDALONE_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
