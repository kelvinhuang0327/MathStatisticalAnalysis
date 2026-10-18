"""Uniform seven-class R6 correction for the K20 R3 unclassified tail (R1).

R24 (``27614636``) leaves the unclassified tail as the R3 owner at
``S1 - FIXED - 9,313,997 = 355,734,631``, a term with no residual-pair correction.
Every aggregate-feasible tail vector ``v`` already carries R6's correction

    correction(v) = max(ceil(P(v) / 9), forest(n_good(v)))
    P(v) = 1036 * Q_out(v) + sum over residual ticket pairs of the type-pair floor

with ``Q_out(v) >= 0``.  The 30 R5 anchor types are split into seven classes; each
type-pair floor is replaced by its class-pair minimum and each type loss by its
class minimum.  That relaxation depends only on the class counts of the 18
residual tickets, so it is minimized exactly over all C(24, 6) compositions.  A
composition is dropped only when its class-maximum loss is below the tail
cursor, since then no vector in it is a tail vector.  The minimum ``delta``
satisfies ``loss(v) - 9,313,997 + correction(v) >= delta`` for every tail vector,
so the tail term falls by ``delta`` and the R3 family maximum is recomputed over
the committed R24 state and classified terms.  No tail vector is enumerated for
the bound, nothing is searched, and no solver is used.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from hashlib import sha256
from itertools import combinations_with_replacement, product
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_tail_crossover_state_dynamic_chase_r24 as r24

r13, r12, r8, r6, r5 = r24.r13, r24.r12, r24.r8, r24.r6, r24.r5
CountVector = r24.CountVector
digest, sparse = r24.digest, r24.sparse

TASK_ID = "B649_K20_R3_TAIL_SEVEN_CLASS_UNIFORM_R6_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-tail-seven-class-uniform-r6-certificate-r1"
BASE_HEAD = "27614636ac4c20392619b3d9364d22bf2af9cff4"
BASE_TREE = "cd99dee2289867b45bc6142baed87d5e0dbab96a"
TAIL_START_LOSS = 9_313_997
START_R3_BOUND = START_TAIL_BOUND = 355_734_631
START_STATE_MAX_BOUND = 355_726_896
START_STATE_MAX_ID = "state:s2-13548976-s3-951748"
START_CLASSIFIED_MAX_BOUND = 355_468_904
RESIDUAL_TICKET_COUNT = r12.OUTSIDE_TICKET_COUNT
MAXIMUM_PAIR_OVERLAP = r12.MAXIMUM_PAIR_OVERLAP
REPO_ROOT = Path(__file__).resolve().parents[3]
RESEARCH = "src/lottolab/research/"
R24_RESULT_RELATIVE = r24.RESULTS + "b649-k20-r3-tail-crossover-state-dynamic-chase-r24-result.json"
RESULT_PATH = REPO_ROOT / (
    r24.RESULTS + "b649-k20-r3-tail-seven-class-uniform-r6-certificate-r1-result.json"
)
UPSTREAM_SHA256 = {
    RESEARCH + "b649_k20_r3_tail_crossover_state_dynamic_chase_r24.py": (
        "2a5e57a7319bd215f8cbc7f4db26453308a74c3f540c25787c44604aa39c8fd7"
    ),
    R24_RESULT_RELATIVE: "32182a3c3c803d95b3a7aee448f8ade3fadb291771affc9dca8beaab8147fc71",
    RESEARCH + "b649_k20_r3_exact_anchor_neighborhood_envelope_r6.py": (
        "a83f6f2a7091aedf034e0905d80993df5001382fedc297fdd503202665e6622c"
    ),
    RESEARCH + "b649_k20_r3_anchor_incidence_bound_r5.py": (
        "569d525f1e9905d043fe0f6132c936d5b260ba3d4b3a376da6c961db8aa5c435"
    ),
    RESEARCH + "b649_k20_outside_min_s2_global_penalty_bound_r1.py": (
        "7706e57e77df6e786e77c4824f3c72663fdae73b20aa5f6797192689f2b6ea62"
    ),
    RESEARCH + "b649_k20_r3_corrected_tail_min_loss_plateau_r12.py": (
        "4501b7a496d32a87bdbfa2d4e0951bca330a60feb8b799350cc0a76607008c92"
    ),
    RESEARCH + "b649_k20_r3_frontier_realizability_bound_r8.py": (
        "14884faf5b2e66c1f30d4e04e453ba5838b7f95815d70d8b7d45be47c5e9bd2b"
    ),
}

# The 30 R5 anchor types, (shared, a_only, b_only, outside), in seven classes.  The
# good class must stay the singleton {0}: the forest floor is indexed by its count.
TYPE_CLASSES: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("good", (0,)),
    ("zero_floor", (7, 10, 11, 13, 14, 15, 18, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29)),
    ("one_anchor_label", (1, 4)),
    ("two_one_side", (2, 8)),
    ("one_each_or_shared", (5, 16)),
    ("three_one_side", (3, 12)),
    ("three_mixed", (6, 9, 17, 19)),
)


@dataclass(frozen=True)
class ClassBounds:
    """Exact local-loss range of one anchor-type class."""

    name: str
    types: tuple[int, ...]
    minimum_loss: int
    maximum_loss: int


@dataclass(frozen=True)
class CompositionBound:
    """Relaxed loss surplus plus R6 correction for one class-count composition."""

    counts: tuple[int, ...]
    minimum_loss: int
    maximum_loss: int
    pair_floor_mass: int
    pair_correction: int
    forest_correction: int
    correction: int
    extra_loss: int
    lower_total: int


@dataclass(frozen=True)
class UniformCertificate:
    """Exact minimum of the relaxation over every composition that can reach the tail."""

    composition_count: int
    admitted_count: int
    screened_count: int
    screened_maximum_loss: int
    admitted_sha256: str
    forest_binding_count: int
    minimum: int
    minimizers: tuple[CompositionBound, ...]


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"R24 authority fingerprint mismatch: {observed}")
    r24.verify_upstream_fingerprints()
    return observed


@cache
def r24_authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads((REPO_ROOT / R24_RESULT_RELATIVE).read_text()))
    expected = {
        "TASK_ID": r24.TASK_ID,
        "BASE_HEAD": r24.BASE_HEAD,
        "TASK_STATUS": "SUCCESS_C",
        "R3_BOUND": START_R3_BOUND,
        "FINAL_OWNER_IDS": [r24.TAIL_ID],
        "NEXT_UNCLASSIFIED_LOSS": TAIL_START_LOSS,
        "UNCLASSIFIED_TAIL_BOUND": START_TAIL_BOUND,
        "STATE_MAX_BOUND": START_STATE_MAX_BOUND,
        "STATE_MAX_OWNER_IDS": [START_STATE_MAX_ID],
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": START_CLASSIFIED_MAX_BOUND,
        "INCUMBENT": r24.INCUMBENT,
    }
    if any(stored[key] != value for key, value in expected.items()):
        raise AssertionError("R24 authority differs from the R1 Packet")
    if r24.canonical_baseline() - TAIL_START_LOSS != START_TAIL_BOUND:
        raise AssertionError("the R24 tail arithmetic changed")
    return stored


def class_partition() -> tuple[tuple[int, ...], ...]:
    """Return the class type sets after checking they cover all 30 types exactly once."""

    classes = tuple(types for _, types in TYPE_CLASSES)
    flat = sorted(index for types in classes for index in types)
    if (
        len(classes) != 7
        or flat != list(range(len(r5.anchor_incidence_profiles())))
        or classes[0] != (0,)
    ):
        raise AssertionError("the seven classes do not partition the 30 anchor types")
    return classes


@cache
def class_bounds() -> tuple[ClassBounds, ...]:
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    return tuple(
        ClassBounds(
            name=name,
            types=types,
            minimum_loss=min(losses[index] for index in types),
            maximum_loss=max(losses[index] for index in types),
        )
        for (name, _), types in zip(TYPE_CLASSES, class_partition(), strict=True)
    )


def forced_overlap(left: int, right: int) -> int:
    """Labels two tickets of these types must share inside the four capacity cells."""

    profiles = r5.anchor_incidence_profiles()
    cells = tuple(
        (profile.shared, profile.a_only, profile.b_only, profile.outside)
        for profile in (profiles[left], profiles[right])
    )
    return sum(
        max(0, low + high - capacity)
        for low, high, capacity in zip(*cells, r6.CELL_LABEL_CAPACITIES, strict=True)
    )


def impossible_type_pairs() -> tuple[tuple[int, int, int], ...]:
    """R6's certificate-free type pairs, each with its forced pair overlap above 3."""

    count = len(r5.anchor_incidence_profiles())
    rows = tuple(
        (left, right, forced_overlap(left, right))
        for left in range(count)
        for right in range(left, count)
        if r6.type_pair_certificate(left, right) is None
    )
    forced = {
        (left, right)
        for left in range(count)
        for right in range(left, count)
        if forced_overlap(left, right) > MAXIMUM_PAIR_OVERLAP
    }
    if {(left, right) for left, right, _ in rows} != forced:
        raise AssertionError("an R6 impossible pair lacks the forced-overlap reason")
    return rows


def type_pair_floor(left: int, right: int) -> int:
    """R6's exact residual floor; a pair without a certificate gets the trivial floor 0."""

    certificate = r6.type_pair_certificate(left, right)
    return 0 if certificate is None else certificate.minimum_residual_intersection


@cache
def class_pair_floors() -> tuple[tuple[int, ...], ...]:
    """Minimum type-pair floor over every ordered type pair of two classes."""

    classes = class_partition()
    return tuple(
        tuple(
            min(type_pair_floor(left, right) for left in left_types for right in right_types)
            for right_types in classes
        )
        for left_types in classes
    )


def verify_forest_identity() -> tuple[int, ...]:
    """R6's frozen forest rows must equal R5's weighted-forest census by good count."""

    frozen = tuple(r6.PRIOR_FOREST_PENALTY_BY_GOOD_COUNT)
    census = tuple(case.outside_overlap_penalty for case in r5.anchor_tradeoff().cases)
    if frozen != census or len(frozen) != RESIDUAL_TICKET_COUNT + 1:
        raise AssertionError("the forest correction differs from the R5 census")
    if r6.PAIR_MULTIPLICITY_DIVISOR != RESIDUAL_TICKET_COUNT // 2:
        raise AssertionError("the pair-sum-to-union divisor changed")
    return frozen


def compositions(total: int, parts: int) -> Iterator[tuple[int, ...]]:
    """Every nonnegative composition of ``total`` into ``parts`` ordered parts."""

    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in compositions(total - first, parts - 1):
            yield (first, *rest)


def composition_bound(counts: Sequence[int]) -> CompositionBound:
    """Lower-bound loss(v) - L + correction(v) over every vector with these class counts."""

    bounds = class_bounds()
    floors = class_pair_floors()
    vector = tuple(counts)
    if len(vector) != len(bounds) or sum(vector) != RESIDUAL_TICKET_COUNT or min(vector) < 0:
        raise ValueError("a class composition must split the 18 residual tickets")
    minimum_loss = sum(count * row.minimum_loss for count, row in zip(vector, bounds, strict=True))
    maximum_loss = sum(count * row.maximum_loss for count, row in zip(vector, bounds, strict=True))
    mass = 0
    for left, left_count in enumerate(vector):
        mass += comb(left_count, 2) * floors[left][left]
        for right in range(left + 1, len(vector)):
            mass += left_count * vector[right] * floors[left][right]
    pair_correction = -(-mass // r6.PAIR_MULTIPLICITY_DIVISOR)
    forest = r6.PRIOR_FOREST_PENALTY_BY_GOOD_COUNT[vector[0]]
    correction = max(pair_correction, forest)
    extra = max(0, minimum_loss - TAIL_START_LOSS)
    return CompositionBound(
        counts=vector,
        minimum_loss=minimum_loss,
        maximum_loss=maximum_loss,
        pair_floor_mass=mass,
        pair_correction=pair_correction,
        forest_correction=forest,
        correction=correction,
        extra_loss=extra,
        lower_total=extra + correction,
    )


@cache
def uniform_certificate() -> UniformCertificate:
    verify_forest_identity()
    total = 0
    screened: list[int] = []
    admitted: list[CompositionBound] = []
    for counts in compositions(RESIDUAL_TICKET_COUNT, len(TYPE_CLASSES)):
        total += 1
        row = composition_bound(counts)
        # Safe only with the class maximum: every vector here has loss <= maximum_loss.
        if row.maximum_loss < TAIL_START_LOSS:
            screened.append(row.maximum_loss)
        else:
            admitted.append(row)
    if total != comb(RESIDUAL_TICKET_COUNT + len(TYPE_CLASSES) - 1, len(TYPE_CLASSES) - 1):
        raise AssertionError("the composition enumeration is incomplete")
    minimum = min(row.lower_total for row in admitted)
    return UniformCertificate(
        composition_count=total,
        admitted_count=len(admitted),
        screened_count=len(screened),
        screened_maximum_loss=max(screened),
        admitted_sha256=digest(tuple((row.counts, row.lower_total) for row in admitted)),
        forest_binding_count=sum(row.forest_correction > row.pair_correction for row in admitted),
        minimum=minimum,
        minimizers=tuple(row for row in admitted if row.lower_total == minimum),
    )


def class_counts(counts: Sequence[int]) -> tuple[int, ...]:
    classes = class_partition()
    return tuple(sum(counts[index] for index in types) for types in classes)


def composition_vectors(composition: Sequence[int]) -> Iterator[CountVector]:
    """Every 30-type count vector whose class counts equal ``composition``."""

    classes = class_partition()
    choices = (
        combinations_with_replacement(types, count)
        for types, count in zip(classes, composition, strict=True)
    )
    for picked in product(*choices):
        counts = [0] * len(r5.anchor_incidence_profiles())
        for indices in picked:
            for index in indices:
                counts[index] += 1
        yield tuple(counts)


def minimizer_realization(minimizer: CompositionBound) -> dict[str, Any]:
    """Exact R6 corrections of every tail vector in a minimizing composition."""

    losses = r6.local_losses(r5.anchor_incidence_profiles())
    vectors = tuple(composition_vectors(minimizer.counts))
    tail = [counts for counts in vectors if r12.local_loss(counts, losses) >= TAIL_START_LOSS]
    feasible = [counts for counts in tail if r6.aggregate_count_vector_is_feasible(counts)]
    actual = {
        counts: r12.local_loss(counts, losses)
        - TAIL_START_LOSS
        + r6.type_count_envelope(counts).combined_pair_penalty
        for counts in feasible
    }
    minimum = min(actual.values())
    if minimum < minimizer.lower_total:
        raise AssertionError("a tail vector falls below the uniform correction")
    argmin = sorted(counts for counts, value in actual.items() if value == minimum)
    witnesses = tuple(r12.construct_support_witness(counts) for counts in argmin)
    if any(
        witness is None or not r8.validate_support_assignment(counts, witness)
        for counts, witness in zip(argmin, witnesses, strict=True)
    ):
        raise AssertionError("a minimizing tail vector has no validated support witness")
    return {
        "class_counts": list(minimizer.counts),
        "type_vectors": len(vectors),
        "tail_vectors": len(tail),
        "aggregate_infeasible_tail_vectors": len(tail) - len(feasible),
        "minimum_actual_surplus_plus_correction": minimum,
        "relaxation_gap": minimum - minimizer.lower_total,
        "argmin_vectors": [sparse(counts) for counts in argmin],
        "argmin_support_witness_sha256": digest(witnesses),
        "argmin_witness_status": "R8_VALIDATED",
    }


def r24_vector_cross_check() -> dict[str, Any]:
    """Recorded R6 corrections of R24's realized vectors never undercut the relaxation."""

    records = cast(list[dict[str, Any]], r24_authority()["NEW_TAIL_VECTOR_STRUCTURAL_RECORDS"])
    checked = tight = eliminated = 0
    violations: list[str] = []
    for row in records:
        if row["r6_correction"] is None:
            eliminated += 1
            continue
        bound = composition_bound(class_counts(cast(list[int], row["counts"])))
        loss = int(row["local_loss"])
        checked += 1
        tight += bound.correction == int(row["r6_correction"])
        if (
            not bound.minimum_loss <= loss <= bound.maximum_loss
            or bound.pair_correction > int(row["pair_union_penalty"])
            or bound.correction > int(row["r6_correction"])
        ):
            violations.append(str(row["vector_id"]))
    if violations:
        raise AssertionError(f"the class relaxation exceeds R6 on {violations[:5]}")
    return {
        "checked_vectors": checked,
        "eliminated_vectors": eliminated,
        "violations": 0,
        "tight_vectors": tight,
    }


def family_maximum(
    tail: int, states: Sequence[tuple[str, int]], classified: Sequence[tuple[str, int]]
) -> dict[str, Any]:
    """Recompute the R3 maximum from raw terms, in R24's state/tail/classified order."""

    state = max(bound for _, bound in states)
    classified_maximum = max(bound for _, bound in classified)
    terms = [*states, (r24.TAIL_ID, tail), *classified]
    return {
        "STATE_MAX_BOUND": state,
        "UNCLASSIFIED_TAIL_BOUND": tail,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": classified_maximum,
        "R3_BOUND": max(state, tail, classified_maximum),
        "OWNER_IDS": list(r13.identify_owner_set(terms)),
    }


def committed_terms() -> tuple[tuple[tuple[str, int], ...], tuple[tuple[str, int], ...]]:
    stored = r24_authority()
    states = tuple(
        (str(row["stable_id"]), int(row["bound"]))
        for row in cast(list[dict[str, Any]], stored["CURRENT_STATE_TERMS"])
    )
    classified = tuple(
        (str(row["stable_id"]), int(row["bound"]))
        for row in cast(list[dict[str, Any]], stored["CURRENT_CLASSIFIED_TERMS"])
    )
    if (
        family_maximum(START_TAIL_BOUND, states, classified)
        != stored["FINAL_FAMILY_MAX_RECOMPUTATION"]
    ):
        raise AssertionError("R24's raw terms do not reproduce its family maximum")
    return states, classified


def composition_record(row: CompositionBound) -> dict[str, Any]:
    return {
        "class_counts": list(row.counts),
        "class_minimum_loss": row.minimum_loss,
        "class_maximum_loss": row.maximum_loss,
        "pair_floor_mass": row.pair_floor_mass,
        "pair_correction": row.pair_correction,
        "forest_correction": row.forest_correction,
        "correction": row.correction,
        "extra_loss": row.extra_loss,
        "lower_total": row.lower_total,
    }


def build_result() -> dict[str, Any]:
    stored = r24_authority()
    states, classified = committed_terms()
    baseline = r24.canonical_baseline()
    bounds = class_bounds()
    certificate = uniform_certificate()
    delta = certificate.minimum
    if delta <= 0 or certificate.screened_maximum_loss >= TAIL_START_LOSS:
        raise AssertionError("the uniform tail correction is not certified")
    tail = baseline - TAIL_START_LOSS - delta
    family = family_maximum(tail, states, classified)
    owners = cast(list[str], family["OWNER_IDS"])
    owner_classes = r24.owner_classes(tuple(owners))
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "CERTIFIED_UNIFORM_TAIL_CORRECTION",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "R24_AUTHORITY": {
            "authority_head": BASE_HEAD,
            "authority_task_id": stored["TASK_ID"],
            "authority_result_sha256": UPSTREAM_SHA256[R24_RESULT_RELATIVE],
        },
        "R24_AUTHORITY_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": verify_upstream_fingerprints(),
        "CANONICAL_PRIMITIVES": r24.canonical_primitives(),
        "TAIL_BASELINE": baseline,
        "TAIL_START_LOSS": TAIL_START_LOSS,
        "CLASS_PARTITION": [
            {
                "name": row.name,
                "types": list(row.types),
                "minimum_loss": row.minimum_loss,
                "maximum_loss": row.maximum_loss,
            }
            for row in bounds
        ],
        "CLASS_PARTITION_STATUS": "PASS_30_TYPES_EXACTLY_ONCE_GOOD_CLASS_SINGLETON",
        "CLASS_PAIR_FLOORS": [list(row) for row in class_pair_floors()],
        "PAIR_FLOOR_STATUS": "PASS_MINIMUM_OF_R6_TYPE_PAIR_FLOORS_OVER_EVERY_CLASS_TYPE_PAIR",
        "R6_IMPOSSIBLE_TYPE_PAIRS": [list(row) for row in impossible_type_pairs()],
        "IMPOSSIBLE_PAIR_POLICY": "TRIVIAL_ZERO_FLOOR_NO_TYPE_PAIR_INCOMPATIBILITY_USED",
        "PAIR_MULTIPLICITY_DIVISOR": r6.PAIR_MULTIPLICITY_DIVISOR,
        "FOREST_CORRECTION_BY_GOOD_COUNT": list(verify_forest_identity()),
        "FOREST_CORRECTION_STATUS": "PASS_EQUALS_R5_FOREST_CENSUS_COMBINED_BY_MAX",
        "COMPOSITIONS_TOTAL": certificate.composition_count,
        "COMPOSITIONS_ADMITTED": certificate.admitted_count,
        "COMPOSITIONS_SCREENED": certificate.screened_count,
        "SCREENED_MAXIMUM_CLASS_MAX_LOSS": certificate.screened_maximum_loss,
        "REACHABILITY_PROOF_STATUS": "PASS_SCREENED_ONLY_BY_CLASS_MAX_LOSS_BELOW_TAIL_START",
        "ADMITTED_COMPOSITIONS_SHA256": certificate.admitted_sha256,
        "FOREST_BINDING_ADMITTED_COMPOSITIONS": certificate.forest_binding_count,
        "UNIFORM_CORRECTION": delta,
        "MINIMIZING_COMPOSITIONS": [composition_record(row) for row in certificate.minimizers],
        "MINIMIZER_REALIZATION": [minimizer_realization(row) for row in certificate.minimizers],
        "R24_VECTOR_CROSS_CHECK": r24_vector_cross_check(),
        "PROOF": {
            "R6_CORRECTION": (
                "For an aggregate-feasible vector v, R6 subtracts max(ceil(P/9), forest(n_0)) "
                "with P = 1036*Q_out + sum over residual ticket pairs of the exact type-pair "
                "floor, Q_out >= 0."
            ),
            "CLASS_RELAXATION": (
                "Each pair inside class a has floor >= F[a][a], each pair across a,b has "
                "floor >= F[a][b] (minimum over all type pairs of the two classes, trivial 0 "
                "for certificate-free pairs); loss(v) >= sum n_c * min_loss(c)."
            ),
            "REACHABILITY": (
                "loss(v) <= sum n_c * max_loss(c); a composition is dropped only when that "
                "maximum is below the tail cursor, so no tail vector is dropped."
            ),
            "UNIFORM_BOUND": (
                "Every tail vector has loss(v) >= L and class composition n, hence "
                "loss(v) - L + correction(v) >= max(0, sum n_c*min_loss(c) - L) + "
                "max(ceil(F(n)/9), forest(n_0)) >= delta."
            ),
            "TAIL_TERM": "tail vector bound = S1 - FIXED - loss(v) - correction(v) <= S1 - "
            "FIXED - L - delta",
        },
        "START_TAIL_BOUND": START_TAIL_BOUND,
        "FINAL_TAIL_BOUND": tail,
        "TAIL_DROP": START_TAIL_BOUND - tail,
        "START_R3_BOUND": START_R3_BOUND,
        "FAMILY_MAX_RECOMPUTATION": family,
        "FINAL_R3_BOUND": family["R3_BOUND"],
        "R3_DROP": START_R3_BOUND - family["R3_BOUND"],
        "FINAL_OWNER_IDS": owners,
        "FINAL_BOUND_OWNER_CLASS": (
            owner_classes[0] if len(owner_classes) == 1 else "TIED_OWNER_SET"
        ),
        "STATE_TERM_COUNT": len(states),
        "CLASSIFIED_TERM_COUNT": len(classified),
        "INCUMBENT": r24.INCUMBENT,
        "REMAINING_GAP": family["R3_BOUND"] - r24.INCUMBENT,
        "SOLVER_STATUS": "NOT_USED_EXACT_FINITE_COMPOSITION_MINIMUM",
        "R7_CENSUS_REPLAYED": False,
        "PRIOR_TAIL_LEVELS_ENUMERATED": 0,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def encode(result: dict[str, Any]) -> str:
    return json.dumps(result, separators=(",", ":")) + "\n"


def replay_stored_result() -> dict[str, Any]:
    stored = cast(dict[str, Any], json.loads(RESULT_PATH.read_text(encoding="utf-8")))
    observed = cast(dict[str, Any], json.loads(encode(build_result())))
    mismatched = sorted(
        key for key in stored.keys() | observed.keys() if stored.get(key) != observed.get(key)
    )
    return {"mismatched_keys": mismatched, "status": "PASS" if not mismatched else "FAIL"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--replay", action="store_true")
    options = parser.parse_args()
    if options.replay:
        print(json.dumps(replay_stored_result(), indent=2))
        return
    result = build_result()
    if not options.no_write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key.isupper() and not isinstance(value, (dict, list))
            }
            | {
                "MINIMIZING_COMPOSITIONS": result["MINIMIZING_COMPOSITIONS"],
                "FINAL_OWNER_IDS": result["FINAL_OWNER_IDS"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
