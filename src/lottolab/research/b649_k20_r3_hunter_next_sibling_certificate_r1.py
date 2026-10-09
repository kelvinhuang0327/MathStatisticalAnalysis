"""Hunter class-split spanning-tree certificate for the next K20 R3 sibling (R1).

Scope is exactly one R7 region member of the R24 ledger: state
``state:s2-12692531-s3-681744``, member ``[0,13][5,4][16,1]`` (13 fully outside
tickets, four of anchor type (0,1,1,4) and one of anchor type (1,0,0,5)).  The
committed Hunter certificate for ``[0,13][5,5]`` supplies the residual events,
the 7-set counter and the tree-rank primitives; none of its member values is an
input here, and that member is neither recomputed nor re-certified.

Every residual pair is floored by the exact R8 row minimum of its edge class:
an edge with a type-0 endpoint uses the (0,0), (0,5) and (0,16) rows, an edge
inside the five-ticket core uses the (5,5) and (5,16) rows.  Kruskal's tree on
those floors weighs ``sum_lambda width * rank(E_lambda)``, at least
``sum width * rho(|E_lambda|)``, and an exact finite census under the forced
label-collision mass gives the correction.  It is combined with the homogeneous
Hunter, forest, pair-sum and rational corrections by ``max``, never by a sum.
No portfolio search, solver or outcome enumeration runs, and no R3, R24 or R25
state is modified.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from hashlib import sha256
from itertools import combinations, product
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_anchor_incidence_bound_r5 as r5
from lottolab.research import b649_k20_r3_exact_anchor_neighborhood_envelope_r6 as r6
from lottolab.research import b649_k20_r3_frontier_realizability_bound_r8 as r8
from lottolab.research import b649_k20_r3_hunter_tree_member_certificate_r1 as hunter
from lottolab.research import b649_k20_r3_state_tail_owner_chase_r14 as r14

TASK_ID = "B649_K20_R3_HUNTER_NEXT_SIBLING_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-hunter-next-sibling-certificate-r1"
BASE_HEAD = "93cda12572b56aeba16cb057d4ff096386908e72"
BASE_TREE = "dc4f6dbf198fb91b2f0243d36a0167a9dad4d280"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS = "docs/research/matrix-native-results/"
MODULE_RELATIVE = "src/lottolab/research/b649_k20_r3_hunter_next_sibling_certificate_r1.py"
RESULT_RELATIVE = RESULTS + "b649-k20-r3-hunter-next-sibling-certificate-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
UPSTREAM_SHA256 = {
    hunter.MODULE_RELATIVE: "bddcd5b9f979ee2e2b620d3b3c9ff7a13f56cc4edc267a5715e8b4722c97ac53",
    hunter.RESULT_RELATIVE: "f657d7fc95f4096d5b34dab37b93ecfa6017011bfecb2ccd146ae89c443daa8a",
}

STATE_ID = hunter.STATE_ID
REGION_SHA256 = hunter.REGION_SHA256
MEMBER_ID = "[0,13][5,4][16,1]"
MEMBER_SPARSE: tuple[tuple[int, int], ...] = ((0, 13), (5, 4), (16, 1))
CERTIFIED_PRIOR_MEMBER_ID = hunter.MEMBER_ID
MEMBER_TYPE_CELLS: dict[int, tuple[int, int, int, int]] = {
    0: (0, 0, 0, 6),
    5: (0, 1, 1, 4),
    16: (1, 0, 0, 5),
}
RESIDUAL_EVENT_COUNT = hunter.RESIDUAL_EVENT_COUNT
MAXIMUM_PAIR_OVERLAP = hunter.MAXIMUM_PAIR_OVERLAP
OUTSIDE_TYPE = 0
OUTSIDE_INCIDENT = "OUTSIDE_INCIDENT"
CORE = "CORE"
CLASS_NAMES: tuple[str, str] = (OUTSIDE_INCIDENT, CORE)

# Packet values.  Each one is re-derived; none is an input to the certificate.
PACKET_REFERENCE = {
    "TARGET_RAW_BOUND": 355_722_220,
    "TARGET_RATIONAL_BOUND": 355_308_650,
    "R3_DURABLE_BOUND": 355_734_631,
    "CANONICAL_INCUMBENT": 313_263_888,
}

# One type-5 ticket of the committed [0,13][5,5] witness becomes a type-16 ticket.
WITNESS_OUTCOME_SET = hunter.CAP17_WITNESS_OUTCOME_SET
WITNESS_REPLACED_TICKET = (5, 9, 11, 12, 15, 18)
WITNESS_TYPE16_TICKET = (1, 10, 11, 12, 13, 14)

Cells = tuple[int, int, int, int]
Floors = tuple[int, int, int, int]
Nested = tuple[int, int, int]


def file_sha256(relative: str) -> str:
    return sha256((REPO_ROOT / relative).read_bytes()).hexdigest()


@cache
def verify_upstream_fingerprints() -> dict[str, str]:
    if hunter.REPO_ROOT != REPO_ROOT:
        raise AssertionError("the Hunter primitives load from a different tree")
    hunter.verify_upstream_fingerprints()
    observed = {relative: file_sha256(relative) for relative in UPSTREAM_SHA256}
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"Hunter fingerprint mismatch: {observed}")
    return observed


def member_counts() -> tuple[int, ...]:
    return hunter.dense_counts(MEMBER_SPARSE)


@cache
def member_type_cells() -> dict[int, Cells]:
    """Type cells read from R5, required equal to the pinned member types."""

    profiles = r5.anchor_incidence_profiles()
    cells = {
        index: (
            profiles[index].shared,
            profiles[index].a_only,
            profiles[index].b_only,
            profiles[index].outside,
        )
        for index, _ in MEMBER_SPARSE
    }
    if cells != MEMBER_TYPE_CELLS:
        raise AssertionError(f"R5 type cells differ from the pinned member types: {cells}")
    if hunter.dense_counts(hunter.SIBLING_SPARSE) != member_counts():
        raise AssertionError("the target is not the sibling named by the Hunter certificate")
    return cells


# ---------------------------------------------------------------- phase 1: ledger, events


@dataclass(frozen=True)
class LedgerMember:
    """Immutable R24 ledger view of the target member, its state and the R3 bound."""

    state_term: int
    region_member_count: int
    member_raw_bound: int
    member_final_bound: int
    member_represented_vector_count: int
    prior_member_final_bound: int
    ladder_final_bounds: tuple[int, ...]
    r3_bound: int
    r3_formula: str
    unclassified_tail_bound: int
    incumbent: int


def _ladder_member(counts: tuple[int, ...]) -> bool:
    return counts[0] == 13 and all(
        count == 0 for index, count in enumerate(counts) if index not in (0, 5, 16)
    )


@cache
def r24_ledger_member() -> LedgerMember:
    verify_upstream_fingerprints()
    stored = cast(
        dict[str, Any],
        json.loads((REPO_ROOT / hunter.R24_RESULT_RELATIVE).read_text(encoding="utf-8")),
    )
    regions = [
        region
        for region in cast(list[dict[str, Any]], stored["STATE_REGION_CERTIFICATES"])
        if region["owner_id"] == STATE_ID
    ]
    terms = [
        int(term["bound"])
        for term in cast(list[dict[str, Any]], stored["CURRENT_STATE_TERMS"])
        if term["stable_id"] == STATE_ID
    ]
    if len(regions) != 1 or len(terms) != 1 or regions[0]["region_sha256"] != REGION_SHA256:
        raise AssertionError("the R24 ledger does not hold exactly one pinned target region")
    members = cast(list[dict[str, Any]], regions[0]["complete_region_members"])
    by_counts = {
        hunter.dense_counts((int(cell), int(count)) for cell, count in member["witness_counts"]): (
            member
        )
        for member in members
    }
    if len(by_counts) != len(members):
        raise AssertionError("the R24 region repeats a member")
    target = by_counts[member_counts()]
    prior = by_counts[hunter.dense_counts(hunter.MEMBER_SPARSE)]
    ladder = sorted(
        (
            int(member["final_bound"])
            for counts, member in by_counts.items()
            if _ladder_member(counts)
        ),
        reverse=True,
    )
    return LedgerMember(
        state_term=terms[0],
        region_member_count=len(members),
        member_raw_bound=int(target["raw_bound"]),
        member_final_bound=int(target["final_bound"]),
        member_represented_vector_count=int(target["represented_vector_count"]),
        prior_member_final_bound=int(prior["final_bound"]),
        ladder_final_bounds=tuple(ladder),
        r3_bound=int(stored["R3_BOUND"]),
        r3_formula=str(stored["R3_FORMULA"]),
        unclassified_tail_bound=int(stored["UNCLASSIFIED_TAIL_BOUND"]),
        incumbent=int(stored["INCUMBENT"]),
    )


@cache
def prior_member_record() -> dict[str, Any]:
    """The committed [0,13][5,5] result, read for scope separation only."""

    verify_upstream_fingerprints()
    stored = cast(
        dict[str, Any],
        json.loads((REPO_ROOT / hunter.RESULT_RELATIVE).read_text(encoding="utf-8")),
    )
    if stored["MEMBER_ID"] != CERTIFIED_PRIOR_MEMBER_ID or stored["STATE_ID"] != STATE_ID:
        raise AssertionError("the committed Hunter result is not the pinned first member")
    return {
        "MEMBER_ID": stored["MEMBER_ID"],
        "CERTIFIED_MEMBER_BOUND": int(stored["CERTIFIED_MEMBER_BOUND"]),
        "HUNTER_CORRECTION": int(stored["HUNTER_CORRECTION"]),
        "RESULT_SHA256": UPSTREAM_SHA256[hunter.RESULT_RELATIVE],
    }


def event_decomposition() -> hunter.EventDecomposition:
    """The committed residual-event decomposition evaluated on the target member."""

    member_type_cells()
    return hunter.event_decomposition(MEMBER_SPARSE)


# ---------------------------------------------------------------- phase 2: pair table


def occurring_type_pairs(
    sparse: Sequence[tuple[int, int]] = MEMBER_SPARSE,
) -> tuple[tuple[int, int], ...]:
    """Type pairs that some residual pair of the member realizes."""

    counts = dict(sparse)
    types = sorted(counts)
    return tuple(
        (left, right)
        for left in types
        for right in types
        if left < right or (left == right and counts[left] >= 2)
    )


def edge_class(left_type: int, right_type: int) -> str:
    return OUTSIDE_INCIDENT if OUTSIDE_TYPE in (left_type, right_type) else CORE


def type_pair_rows(left_type: int, right_type: int) -> tuple[hunter.PairRow, ...]:
    """Recount one type pair with the 7-set counter and require equality with R8."""

    cells = member_type_cells()
    left, right = cells[left_type], cells[right_type]
    overlaps = hunter.feasible_cell_overlaps(left, right)
    independent = {
        overlap: hunter.residual_pair_intersection(left, right, overlap) for overlap in overlaps
    }
    table = r8._pair_event_correction_table(left_type, right_type)  # pyright: ignore[reportPrivateUsage]
    committed = {(row[0], row[1], row[2], row[3]): row[4] for row in table}
    if committed != independent:
        raise AssertionError(f"R8 pair table differs for types {(left_type, right_type)}")
    if set(r6.feasible_pair_overlap_vectors(left_type, right_type)) != set(overlaps):
        raise AssertionError("R6 and the independent overlap enumeration disagree")
    return tuple(
        hunter.PairRow(left_type, right_type, overlap, value)
        for overlap, value in sorted(independent.items())
    )


@cache
def independent_pair_rows() -> tuple[hunter.PairRow, ...]:
    return tuple(row for pair in occurring_type_pairs() for row in type_pair_rows(*pair))


def type_pair_edge_counts(
    sparse: Sequence[tuple[int, int]] = MEMBER_SPARSE,
) -> dict[tuple[int, int], int]:
    counts = dict(sparse)
    return {
        (left, right): comb(counts[left], 2) if left == right else counts[left] * counts[right]
        for left, right in occurring_type_pairs(sparse)
    }


def class_edge_counts(sparse: Sequence[tuple[int, int]] = MEMBER_SPARSE) -> tuple[int, int]:
    totals = dict.fromkeys(CLASS_NAMES, 0)
    for (left, right), count in type_pair_edge_counts(sparse).items():
        totals[edge_class(left, right)] += count
    if sum(totals.values()) != comb(RESIDUAL_EVENT_COUNT, 2):
        raise AssertionError("edge classes must partition the residual pairs")
    return totals[OUTSIDE_INCIDENT], totals[CORE]


def class_rows(rows: Sequence[hunter.PairRow], name: str) -> tuple[hunter.PairRow, ...]:
    return tuple(row for row in rows if edge_class(row.left_type, row.right_type) == name)


def class_pair_floors(rows: Sequence[hunter.PairRow]) -> tuple[Floors, Floors]:
    """phi_c(t) = min of every exact row of class c with total overlap t."""

    floors: list[Floors] = []
    for name in CLASS_NAMES:
        members = class_rows(rows, name)
        floor = hunter.pair_floor_by_overlap(members)
        hunter.require_safe_pair_floors(floor, members)
        floors.append(floor)
    return floors[0], floors[1]


def global_pair_floors(rows: Sequence[hunter.PairRow]) -> Floors:
    floors = hunter.pair_floor_by_overlap(rows)
    hunter.require_safe_pair_floors(floors, rows)
    return floors


def floor_setting_type_pairs(rows: Sequence[hunter.PairRow]) -> dict[str, list[list[int]]]:
    """For each class and total overlap, the type pairs whose row attains the floor."""

    floors = dict(zip(CLASS_NAMES, class_pair_floors(rows), strict=True))
    setters: dict[str, list[list[int]]] = {}
    for name in CLASS_NAMES:
        members = class_rows(rows, name)
        for total in range(MAXIMUM_PAIR_OVERLAP + 1):
            pairs = sorted(
                {
                    (row.left_type, row.right_type)
                    for row in members
                    if row.total_overlap == total
                    and row.residual_intersection == floors[name][total]
                }
            )
            setters[f"{name}_{total}"] = [list(pair) for pair in pairs]
    return setters


# ---------------------------------------------------------------- phase 3: collisions


def member_cell_incidences(sparse: Sequence[tuple[int, int]] = MEMBER_SPARSE) -> Cells:
    cells = member_type_cells()
    totals = [0, 0, 0, 0]
    for type_index, count in sparse:
        for cell, value in enumerate(cells[type_index]):
            totals[cell] += count * value
    return totals[0], totals[1], totals[2], totals[3]


# ---------------------------------------------------------------- phase 4: class tree rank


@dataclass(frozen=True)
class EdgeClass:
    """Residual pairs sharing one floor function phi_c(t), t the total pair overlap."""

    name: str
    edge_count: int
    floors: Floors


def member_edge_classes(
    sizes: tuple[int, int], floors: tuple[Floors, Floors]
) -> tuple[EdgeClass, ...]:
    return tuple(
        EdgeClass(name, size, floor)
        for name, size, floor in zip(CLASS_NAMES, sizes, floors, strict=True)
    )


@cache
def level_thresholds(classes: tuple[EdgeClass, ...]) -> tuple[int, ...]:
    for item in classes:
        if item.floors[0] < 0 or any(
            low > high for low, high in zip(item.floors, item.floors[1:], strict=False)
        ):
            raise AssertionError("class floors must be nonnegative and nondecreasing")
    return tuple(sorted({value for item in classes for value in item.floors}))


def level_edge_count(item: EdgeClass, threshold: int, nested: Nested) -> int:
    """#{e in c : phi_c(t_e) >= threshold} from e_k = #{e in c : t_e >= k}, phi_c monotone."""

    sizes = (item.edge_count, *nested)
    for level, value in enumerate(item.floors):
        if value >= threshold:
            return sizes[level]
    return 0


def class_tree_weight_floor(
    classes: tuple[EdgeClass, ...],
    nested_counts: Sequence[Nested],
    vertex_count: int = RESIDUAL_EVENT_COUNT,
) -> int:
    """sum_i (lambda_i - lambda_{i-1}) * rho(|E_lambda_i|) over the sorted class floors."""

    if sum(item.edge_count for item in classes) != comb(vertex_count, 2):
        raise AssertionError("edge classes must partition the complete graph")
    for item, nested in zip(classes, nested_counts, strict=True):
        if not item.edge_count >= nested[0] >= nested[1] >= nested[2] >= 0:
            raise ValueError("class counts must be nested and fit inside their class")
    total = previous = 0
    for threshold in level_thresholds(classes):
        size = sum(
            level_edge_count(item, threshold, nested)
            for item, nested in zip(classes, nested_counts, strict=True)
        )
        total += (threshold - previous) * hunter.rank_floor(size)
        previous = threshold
    return total


def nested_triples(capacity: int, mass: int) -> Iterator[Nested]:
    """Every capacity >= e1 >= e2 >= e3 >= 0 with e1 + e2 + e3 == mass."""

    for e1 in range(min(capacity, mass) + 1):
        for e2 in range(min(e1, mass - e1) + 1):
            e3 = mass - e1 - e2
            if e3 <= e2:
                yield e1, e2, e3


def class_count_vectors(classes: tuple[EdgeClass, ...], mass: int) -> Iterator[tuple[Nested, ...]]:
    if not classes:
        if mass == 0:
            yield ()
        return
    head, rest = classes[0], classes[1:]
    for head_mass in range(min(mass, MAXIMUM_PAIR_OVERLAP * head.edge_count) + 1):
        for triple in nested_triples(head.edge_count, head_mass):
            for tail in class_count_vectors(rest, mass - head_mass):
                yield (triple, *tail)


@dataclass(frozen=True)
class ClassTreeMinimum:
    correction: int
    edge_counts: tuple[Nested, ...]
    census_size: int


@cache
def minimum_class_tree_correction(
    classes: tuple[EdgeClass, ...],
    collision_floor: int,
    vertex_count: int = RESIDUAL_EVENT_COUNT,
) -> ClassTreeMinimum:
    """Exhaust nested class counts of total collision mass exactly Q.

    The objective is nondecreasing in every e_{c,k}.  Lowering the top nonzero
    count of one class keeps every class nested and lowers the mass by one, so
    the minimum over mass >= Q is attained at mass Q; the small-instance check
    ``verify_exact_mass_reduction`` replays this exhaustively.
    """

    capacity = MAXIMUM_PAIR_OVERLAP * sum(item.edge_count for item in classes)
    if not 0 <= collision_floor <= capacity:
        raise AssertionError("the collision relaxation is infeasible")
    best: tuple[int, tuple[Nested, ...]] | None = None
    census = 0
    for counts in class_count_vectors(classes, collision_floor):
        census += 1
        value = class_tree_weight_floor(classes, counts, vertex_count)
        if best is None or value < best[0]:
            best = (value, counts)
    if best is None:
        raise AssertionError("the collision relaxation is infeasible")
    return ClassTreeMinimum(correction=best[0], edge_counts=best[1], census_size=census)


@cache
def spanning_trees(vertex_count: int) -> tuple[tuple[tuple[int, int], ...], ...]:
    edges = tuple(combinations(range(vertex_count), 2))
    return tuple(
        tree
        for tree in combinations(edges, vertex_count - 1)
        if hunter.graph_rank(vertex_count, tree) == vertex_count - 1
    )


@cache
def verify_class_threshold_tree_lemma(
    class_floors: tuple[Floors, Floors], vertex_count: int = 4
) -> int:
    """Every outside-type vertex count and every overlap labelling 0..3 of K_n.

    Kruskal on the class floors is a maximum floor tree, its weight equals
    sum width * rank(E_lambda), and that is at least the census objective at
    the labelling's own nested class counts.
    """

    edges = tuple(combinations(range(vertex_count), 2))
    trees = spanning_trees(vertex_count)
    floor_of = dict(zip(CLASS_NAMES, class_floors, strict=True))
    checked = 0
    for outside_vertices in range(vertex_count + 1):
        names = {edge: OUTSIDE_INCIDENT if edge[0] < outside_vertices else CORE for edge in edges}
        classes = tuple(
            EdgeClass(name, sum(1 for edge in edges if names[edge] == name), floor_of[name])
            for name in CLASS_NAMES
        )
        thresholds = level_thresholds(classes)
        for labels in product(range(MAXIMUM_PAIR_OVERLAP + 1), repeat=len(edges)):
            overlap = dict(zip(edges, labels, strict=True))
            weight = {edge: floor_of[names[edge]][overlap[edge]] for edge in edges}
            kruskal = sum(weight[edge] for edge in hunter.threshold_tree(vertex_count, weight))
            best = max(sum(weight[edge] for edge in tree) for tree in trees)
            integral = previous = 0
            for threshold in thresholds:
                level = [edge for edge in edges if weight[edge] >= threshold]
                integral += (threshold - previous) * hunter.graph_rank(vertex_count, level)
                previous = threshold
            nested = tuple(
                cast(
                    Nested,
                    tuple(
                        sum(1 for edge in edges if names[edge] == name and overlap[edge] >= level)
                        for level in range(1, MAXIMUM_PAIR_OVERLAP + 1)
                    ),
                )
                for name in CLASS_NAMES
            )
            objective = class_tree_weight_floor(classes, nested, vertex_count)
            if not kruskal == best == integral >= objective:
                raise AssertionError(f"class threshold tree lemma fails on {overlap}")
            checked += 1
    return checked


@cache
def verify_exact_mass_reduction(class_floors: tuple[Floors, Floors], vertex_count: int = 4) -> int:
    """Small instances: the objective is monotone and min over mass >= Q is min at Q."""

    checked = 0
    edge_total = comb(vertex_count, 2)
    for core_vertices in range(vertex_count + 1):
        core_edges = comb(core_vertices, 2)
        classes = member_edge_classes((edge_total - core_edges, core_edges), class_floors)
        capacity = MAXIMUM_PAIR_OVERLAP * edge_total
        values: dict[tuple[Nested, ...], int] = {}
        for mass in range(capacity + 1):
            for counts in class_count_vectors(classes, mass):
                values[counts] = class_tree_weight_floor(classes, counts, vertex_count)
        for counts, value in values.items():
            for index, level in product(range(len(classes)), range(MAXIMUM_PAIR_OVERLAP)):
                raised = [list(nested) for nested in counts]
                raised[index][level] += 1
                bigger = tuple(cast(Nested, tuple(nested)) for nested in raised)
                if bigger in values and values[bigger] < value:
                    raise AssertionError("the class objective is not monotone")
        for floor in range(capacity + 1):
            at_least = min(
                value for counts, value in values.items() if sum(map(sum, counts)) >= floor
            )
            if at_least != minimum_class_tree_correction(classes, floor, vertex_count).correction:
                raise AssertionError("the exact-mass census misses the minimum")
            checked += 1
    return checked


@cache
def tree_rank_regressions(class_floors: tuple[Floors, Floors]) -> dict[str, int]:
    return {
        "RANK_ALGEBRA_ROWS": hunter.verify_rank_floor_algebra(),
        "RANK_FLOOR_EXHAUSTIVE_GRAPHS_ON_6_VERTICES": hunter.verify_rank_floor_exhaustively(
            hunter.rank_floor
        ),
        "CLASS_THRESHOLD_TREE_EXHAUSTIVE_K4_LABELLINGS": verify_class_threshold_tree_lemma(
            class_floors
        ),
        "EXACT_MASS_REDUCTION_K4_FLOORS_CHECKED": verify_exact_mass_reduction(class_floors),
    }


# ---------------------------------------------------------------- phase 5: certificate


@dataclass(frozen=True)
class SiblingMemberCertificate:
    state_id: str
    region_sha256: str
    member_sparse: tuple[tuple[int, int], ...]
    residual_event_count: int
    maximum_pair_overlap: int
    raw_union_bound: int
    pair_rows_sha256: str
    global_pair_floors: Floors
    class_edge_counts: tuple[int, int]
    class_pair_floors: tuple[Floors, Floors]
    cell_incidences: Cells
    cell_collision_floors: Cells
    collision_floor: int
    class_minimizer_counts: tuple[Nested, ...]
    homogeneous_hunter_correction: int
    class_hunter_correction: int
    pair_sum_correction: int
    forest_correction: int
    rational_correction: int
    certified_correction: int
    certified_member_bound: int


def rows_digest(rows: Sequence[hunter.PairRow]) -> str:
    payload = tuple(
        (row.left_type, row.right_type, row.overlap, row.residual_intersection) for row in rows
    )
    return hunter.digest(payload)


@cache
def rational_correction() -> int:
    return int(r14.moment_certificate(member_counts())["correction_lower_bound"])


def correction_terms(
    events: hunter.EventDecomposition, rational: int, homogeneous: int, class_split: int
) -> dict[str, int]:
    return {
        "R6_PAIR_SUM": events.r7_pair_sum_penalty,
        "R5_FOREST": events.r7_forest_floor,
        "R14_RATIONAL": rational,
        "HUNTER_HOMOGENEOUS": homogeneous,
        "HUNTER_CLASS_SPLIT": class_split,
    }


@cache
def build_certificate() -> SiblingMemberCertificate:
    verify_upstream_fingerprints()
    events = event_decomposition()
    rows = independent_pair_rows()
    global_floors = global_pair_floors(rows)
    floors = class_pair_floors(rows)
    sizes = class_edge_counts()
    incidences = member_cell_incidences()
    cell_floors = hunter.cell_collision_floors(incidences)
    collision_floor = sum(cell_floors)
    homogeneous = hunter.minimum_tree_correction(global_floors, collision_floor)
    split = minimum_class_tree_correction(member_edge_classes(sizes, floors), collision_floor)
    corrections = correction_terms(
        events, rational_correction(), homogeneous.correction, split.correction
    )
    certified = hunter.combine_corrections(corrections)
    return SiblingMemberCertificate(
        state_id=STATE_ID,
        region_sha256=REGION_SHA256,
        member_sparse=MEMBER_SPARSE,
        residual_event_count=RESIDUAL_EVENT_COUNT,
        maximum_pair_overlap=hunter.family_pair_overlap_ceiling(),
        raw_union_bound=events.raw_union_bound,
        pair_rows_sha256=rows_digest(rows),
        global_pair_floors=global_floors,
        class_edge_counts=sizes,
        class_pair_floors=floors,
        cell_incidences=incidences,
        cell_collision_floors=cell_floors,
        collision_floor=collision_floor,
        class_minimizer_counts=split.edge_counts,
        homogeneous_hunter_correction=homogeneous.correction,
        class_hunter_correction=split.correction,
        pair_sum_correction=corrections["R6_PAIR_SUM"],
        forest_correction=corrections["R5_FOREST"],
        rational_correction=corrections["R14_RATIONAL"],
        certified_correction=certified,
        certified_member_bound=events.raw_union_bound - certified,
    )


def verify_certificate(certificate: SiblingMemberCertificate) -> None:
    """Recheck every certificate field from exact inputs; raise on any deviation."""

    if (
        certificate.state_id != STATE_ID
        or certificate.region_sha256 != REGION_SHA256
        or certificate.member_sparse != MEMBER_SPARSE
    ):
        raise AssertionError("certificate source member differs from the pinned member")
    residual_tickets = sum(count for _, count in certificate.member_sparse)
    if certificate.residual_event_count != RESIDUAL_EVENT_COUNT or (
        residual_tickets != RESIDUAL_EVENT_COUNT
    ):
        raise AssertionError("the member has exactly 18 residual events")
    if certificate.maximum_pair_overlap != hunter.family_pair_overlap_ceiling():
        raise AssertionError("R3 portfolios have pair overlaps 0..3 only")
    events = event_decomposition()
    if certificate.raw_union_bound != events.raw_union_bound:
        raise AssertionError("raw union bound differs from the exact event decomposition")
    rows = independent_pair_rows()
    if certificate.pair_rows_sha256 != rows_digest(rows):
        raise AssertionError("pair rows digest differs")
    hunter.require_safe_pair_floors(certificate.global_pair_floors, rows)
    if certificate.global_pair_floors != global_pair_floors(rows):
        raise AssertionError("global pair floors differ from the exact row minima")
    for floors, name in zip(certificate.class_pair_floors, CLASS_NAMES, strict=True):
        hunter.require_safe_pair_floors(floors, class_rows(rows, name))
    if certificate.class_pair_floors != class_pair_floors(rows):
        raise AssertionError("class pair floors differ from the exact class row minima")
    if certificate.class_edge_counts != class_edge_counts():
        raise AssertionError("class edge counts differ from the member type counts")
    if certificate.cell_incidences != member_cell_incidences():
        raise AssertionError("cell incidences differ from the member type counts")
    floors = hunter.cell_collision_floors(certificate.cell_incidences)
    if certificate.cell_collision_floors != floors or certificate.collision_floor != sum(floors):
        raise AssertionError("collision floor differs from the balanced per-cell minimum")
    tree_rank_regressions(certificate.class_pair_floors)
    classes = member_edge_classes(certificate.class_edge_counts, certificate.class_pair_floors)
    split = minimum_class_tree_correction(classes, certificate.collision_floor)
    if (
        certificate.class_hunter_correction != split.correction
        or certificate.class_minimizer_counts != split.edge_counts
    ):
        raise AssertionError("class Hunter correction differs from the finite census minimum")
    if sum(map(sum, certificate.class_minimizer_counts)) != certificate.collision_floor:
        raise AssertionError("the minimizer does not carry the forced collision mass")
    if certificate.class_hunter_correction != class_tree_weight_floor(
        classes, certificate.class_minimizer_counts
    ):
        raise AssertionError("class Hunter correction is not the tree weight floor")
    homogeneous = hunter.minimum_tree_correction(
        certificate.global_pair_floors, certificate.collision_floor
    )
    if certificate.homogeneous_hunter_correction != homogeneous.correction:
        raise AssertionError("homogeneous Hunter correction differs from its census")
    if certificate.class_hunter_correction < certificate.homogeneous_hunter_correction:
        raise AssertionError("class floors dominate global floors, so must their minimum")
    expected = correction_terms(
        events,
        rational_correction(),
        certificate.homogeneous_hunter_correction,
        certificate.class_hunter_correction,
    )
    if (
        certificate.pair_sum_correction,
        certificate.forest_correction,
        certificate.rational_correction,
    ) != (expected["R6_PAIR_SUM"], expected["R5_FOREST"], expected["R14_RATIONAL"]):
        raise AssertionError("existing corrections differ from their committed sources")
    if certificate.certified_correction != hunter.combine_corrections(expected):
        raise AssertionError("corrections must be combined by max, never summed")
    if certificate.certified_member_bound != (
        certificate.raw_union_bound - certificate.certified_correction
    ):
        raise AssertionError("certified bound must subtract the combined correction once")


def certified_member_bound(state_id: str, counts: Sequence[int]) -> int:
    """Return the member bound only for the exact source state and member."""

    certificate = build_certificate()
    if state_id != certificate.state_id or tuple(counts) != hunter.dense_counts(
        certificate.member_sparse
    ):
        raise hunter.CertificateScopeError(
            f"the sibling certificate is valid only for {certificate.state_id} member {MEMBER_ID}"
        )
    verify_certificate(certificate)
    return certificate.certified_member_bound


# ---------------------------------------------------------------- phase 6: witness


@dataclass(frozen=True)
class WitnessAnalysis:
    member_sparse: tuple[tuple[int, int], ...]
    replaced_type: int
    inserted_type: int
    anchor_overlap: int
    maximum_pair_overlap: int
    residual_multiplicity: int
    anchor_hits_on_outcome_set: tuple[int, int]
    overlap_histogram: tuple[int, int, int, int]
    collision_mass: int
    label_collision_mass: int
    class_nested_counts: tuple[Nested, ...]
    census_objective: int
    floor_tree_weight: int
    exact_tree_weight: int
    exact_rows_match_table: bool


def witness_residual_tickets() -> tuple[tuple[int, ...], ...]:
    tickets = list(hunter.CAP17_WITNESS_RESIDUAL_TICKETS)
    tickets[tickets.index(WITNESS_REPLACED_TICKET)] = WITNESS_TYPE16_TICKET
    return tuple(tickets)


def witness_tickets() -> tuple[hunter.Ticket, ...]:
    return (
        hunter.ANCHOR_A,
        hunter.ANCHOR_B,
        *(frozenset(ticket) for ticket in witness_residual_tickets()),
    )


@cache
def witness_analysis() -> WitnessAnalysis:
    """Validate the explicit member portfolio and its exact residual pair structure."""

    portfolio = witness_tickets()
    if len(portfolio) != 20 or len(set(portfolio)) != 20:
        raise AssertionError("witness must hold 20 distinct tickets")
    if any(
        len(ticket) != hunter.TICKET_SIZE
        or not all(1 <= label <= hunter.POOL_SIZE for label in ticket)
        for ticket in portfolio
    ):
        raise AssertionError("witness tickets must hold six labels from 1..49")
    overlaps_all = [len(left & right) for left, right in combinations(portfolio, 2)]
    anchor_overlap = len(hunter.ANCHOR_A & hunter.ANCHOR_B)
    if max(overlaps_all) != anchor_overlap or anchor_overlap != r5.ANCHOR_OVERLAP:
        raise AssertionError("witness is not an R3 portfolio anchored on a maximum pair")
    profiles = r5.anchor_incidence_profiles()
    index_by_cells = {
        (profile.shared, profile.a_only, profile.b_only, profile.outside): index
        for index, profile in enumerate(profiles)
    }
    residual = portfolio[2:]
    types = [index_by_cells[hunter.ticket_cells(ticket)] for ticket in residual]
    sparse = tuple(sorted((index, types.count(index)) for index in set(types)))
    if sparse != MEMBER_SPARSE:
        raise AssertionError(f"witness types {sparse} are not the target member")
    replaced = index_by_cells[hunter.ticket_cells(frozenset(WITNESS_REPLACED_TICKET))]
    inserted = index_by_cells[hunter.ticket_cells(frozenset(WITNESS_TYPE16_TICKET))]
    outcome_set = WITNESS_OUTCOME_SET
    anchor_hits = (len(hunter.ANCHOR_A & outcome_set), len(hunter.ANCHOR_B & outcome_set))
    multiplicity = sum(1 for ticket in residual if len(ticket & outcome_set) >= hunter.WIN_HITS)
    if max(anchor_hits) >= hunter.WIN_HITS:
        raise AssertionError("the shared 7-set must lie outside both anchor events")

    rows = independent_pair_rows()
    table = {(row.left_type, row.right_type, row.overlap): row for row in rows}
    floor_of = dict(zip(CLASS_NAMES, class_pair_floors(rows), strict=True))
    pair_overlaps: dict[tuple[int, int], int] = {}
    pair_classes: dict[tuple[int, int], str] = {}
    floor_weights: dict[tuple[int, int], int] = {}
    exact_weights: dict[tuple[int, int], int] = {}
    rows_match = True
    for left, right in combinations(range(len(residual)), 2):
        overlap_cells = hunter.pair_cell_overlap(residual[left], residual[right])
        total = sum(overlap_cells)
        low, high = sorted((types[left], types[right]))
        name = edge_class(low, high)
        exact = hunter.outcome_count(
            (residual[left], residual[right]), (hunter.ANCHOR_A, hunter.ANCHOR_B)
        )
        pair_overlaps[(left, right)] = total
        pair_classes[(left, right)] = name
        floor_weights[(left, right)] = floor_of[name][total]
        exact_weights[(left, right)] = exact
        rows_match = rows_match and table[(low, high, overlap_cells)].residual_intersection == exact
    hunter.threshold_edge_counts(pair_overlaps.values())
    frequencies = [
        sum(1 for ticket in residual if label in ticket) for label in range(1, hunter.POOL_SIZE + 1)
    ]
    label_mass = sum(comb(value, 2) for value in frequencies)
    collision_mass = sum(pair_overlaps.values())
    if collision_mass != label_mass:
        raise AssertionError("witness collision identity failed")
    nested = tuple(
        cast(
            Nested,
            tuple(
                sum(
                    1
                    for edge, value in pair_overlaps.items()
                    if pair_classes[edge] == name and value >= level
                )
                for level in range(1, MAXIMUM_PAIR_OVERLAP + 1)
            ),
        )
        for name in CLASS_NAMES
    )
    classes = member_edge_classes(class_edge_counts(), class_pair_floors(rows))
    objective = class_tree_weight_floor(classes, nested)
    floor_tree = hunter.threshold_tree(len(residual), floor_weights)
    floor_weight = sum(floor_weights[edge] for edge in floor_tree)
    integral = previous = 0
    for threshold in level_thresholds(classes):
        level = [edge for edge, value in floor_weights.items() if value >= threshold]
        integral += (threshold - previous) * hunter.graph_rank(len(residual), level)
        previous = threshold
    if floor_weight != integral:
        raise AssertionError("witness Kruskal tree does not attain the class rank integral")
    exact_tree = hunter.threshold_tree(len(residual), exact_weights)
    exact_weight = sum(exact_weights[edge] for edge in exact_tree)
    histogram = tuple(
        sum(1 for value in pair_overlaps.values() if value == total)
        for total in range(MAXIMUM_PAIR_OVERLAP + 1)
    )
    return WitnessAnalysis(
        member_sparse=sparse,
        replaced_type=replaced,
        inserted_type=inserted,
        anchor_overlap=anchor_overlap,
        maximum_pair_overlap=max(overlaps_all),
        residual_multiplicity=multiplicity,
        anchor_hits_on_outcome_set=anchor_hits,
        overlap_histogram=(histogram[0], histogram[1], histogram[2], histogram[3]),
        collision_mass=collision_mass,
        label_collision_mass=label_mass,
        class_nested_counts=nested,
        census_objective=objective,
        floor_tree_weight=floor_weight,
        exact_tree_weight=exact_weight,
        exact_rows_match_table=rows_match,
    )


# ---------------------------------------------------------------- result


def _sparse_text(sparse: Sequence[tuple[int, int]]) -> list[list[int]]:
    return [[index, count] for index, count in sparse]


def level_table(classes: tuple[EdgeClass, ...], counts: Sequence[Nested]) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    previous = 0
    for threshold in level_thresholds(classes):
        size = sum(
            level_edge_count(item, threshold, nested)
            for item, nested in zip(classes, counts, strict=True)
        )
        table.append(
            {
                "THRESHOLD": threshold,
                "WIDTH": threshold - previous,
                "CLASS_MIN_OVERLAP": {
                    item.name: next(
                        (level for level, value in enumerate(item.floors) if value >= threshold),
                        None,
                    )
                    for item in classes
                },
                "EDGES_AT_MINIMIZER": size,
                "RHO_AT_MINIMIZER": hunter.rank_floor(size),
            }
        )
        previous = threshold
    return table


def type16_effect(
    events: hunter.EventDecomposition, rows: Sequence[hunter.PairRow]
) -> dict[str, Any]:
    sizes = dict(events.residual_event_sizes)
    floor_of = dict(zip(CLASS_NAMES, class_pair_floors(rows), strict=True))
    margins = [
        row.residual_intersection
        - floor_of[edge_class(row.left_type, row.right_type)][row.total_overlap]
        for row in rows
        if 16 in (row.left_type, row.right_type)
    ]
    setters = floor_setting_type_pairs(rows)
    without = [row for row in rows if 16 not in (row.left_type, row.right_type)]
    lowers_floor = class_pair_floors(without) != class_pair_floors(rows) or (
        global_pair_floors(without) != global_pair_floors(rows)
    )
    if lowers_floor or min(margins) < 0:
        raise AssertionError("the type-16 analysis changed")
    return {
        "TYPE16_CELLS": list(MEMBER_TYPE_CELLS[16]),
        "TYPE16_RESIDUAL_EVENT_SIZE": sizes[16],
        "TYPE5_RESIDUAL_EVENT_SIZE": sizes[5],
        "RESIDUAL_SIZE_DELTA_VS_TYPE5": sizes[16] - sizes[5],
        "NEW_TYPE_PAIRS": [[0, 16], [5, 16]],
        "ABSENT_TYPE_PAIR": {"PAIR": [16, 16], "REASON": "the member holds one type-16 ticket"},
        "TYPE16_ROW_COUNT": len(margins),
        "TYPE16_ROWS_LOWER_A_FLOOR": lowers_floor,
        "MINIMUM_TYPE16_ROW_MARGIN_ABOVE_CLASS_FLOOR": min(margins),
        "TYPE16_FLOOR_TIES": sorted(
            name for name, pairs in setters.items() if any(16 in pair for pair in pairs)
        ),
        "FLOOR_SETTING_TYPE_PAIRS": setters,
        "GLOBAL_FLOORS_EQUAL_CORE_FLOORS": global_pair_floors(rows) == floor_of[CORE],
    }


@cache
def build_result() -> dict[str, Any]:
    certificate = build_certificate()
    verify_certificate(certificate)
    ledger = r24_ledger_member()
    prior = prior_member_record()
    events = event_decomposition()
    rows = independent_pair_rows()
    witness = witness_analysis()
    lemma = hunter.seven_set_lemma_check()
    regressions = tree_rank_regressions(certificate.class_pair_floors)
    balanced_rows = hunter.verify_balanced_mass_exhaustively()
    classes = member_edge_classes(certificate.class_edge_counts, certificate.class_pair_floors)
    split = minimum_class_tree_correction(classes, certificate.collision_floor)
    homogeneous = hunter.minimum_tree_correction(
        certificate.global_pair_floors, certificate.collision_floor
    )
    single_class = minimum_class_tree_correction(
        (EdgeClass("ALL_PAIRS", comb(RESIDUAL_EVENT_COUNT, 2), certificate.global_pair_floors),),
        certificate.collision_floor,
    )
    if single_class.correction != homogeneous.correction:
        raise AssertionError("the exact-mass census disagrees with the committed >= Q census")
    existing = {
        "R6_PAIR_SUM": certificate.pair_sum_correction,
        "R5_FOREST": certificate.forest_correction,
        "R14_RATIONAL": certificate.rational_correction,
    }
    rational_bound = certificate.raw_union_bound - hunter.combine_corrections(existing)
    forest_bound = certificate.raw_union_bound - max(
        certificate.forest_correction, certificate.pair_sum_correction
    )
    if (
        ledger.member_raw_bound != forest_bound
        or ledger.member_final_bound != ledger.member_raw_bound
        or ledger.member_represented_vector_count != 1
    ):
        raise AssertionError("the R24 ledger member differs from the re-derived raw bound")
    if rational_bound != hunter.sibling_rational_bound():
        raise AssertionError("the rational bound differs from the committed sibling route")
    if certificate.certified_member_bound != (
        ledger.member_final_bound
        + max(certificate.forest_correction, certificate.pair_sum_correction)
        - certificate.certified_correction
    ):
        raise AssertionError("the R24 correction is subtracted more than once")
    if not witness.exact_rows_match_table or not (
        witness.exact_tree_weight
        >= witness.floor_tree_weight
        >= witness.census_objective
        >= certificate.class_hunter_correction
    ):
        raise AssertionError("the explicit member witness contradicts the certificate")
    if witness.collision_mass < certificate.collision_floor:
        raise AssertionError("the witness violates the certified collision floor")
    derived = {
        "TARGET_RAW_BOUND": ledger.member_raw_bound,
        "TARGET_RATIONAL_BOUND": rational_bound,
        "R3_DURABLE_BOUND": ledger.r3_bound,
        "CANONICAL_INCUMBENT": ledger.incumbent,
    }
    if derived != PACKET_REFERENCE:
        raise AssertionError(f"re-derived values differ from the packet: {derived}")
    if not certificate.certified_member_bound < rational_bound:
        raise AssertionError("the certificate does not strictly improve the rational bound")
    try:
        certified_member_bound(STATE_ID, hunter.dense_counts(hunter.MEMBER_SPARSE))
    except hunter.CertificateScopeError:
        pass
    else:
        raise AssertionError("the sibling certificate must not cover the first member")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "CERTIFIED_SINGLE_MEMBER_HUNTER_CLASS_SPLIT_TREE_BOUND",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "SOURCE_FINGERPRINT": {
            "MODULE": MODULE_RELATIVE,
            "MODULE_SHA256": file_sha256(MODULE_RELATIVE),
        },
        "UPSTREAM_SHA256": {**hunter.UPSTREAM_SHA256, **verify_upstream_fingerprints()},
        "STATE_ID": STATE_ID,
        "REGION_SHA256": REGION_SHA256,
        "MEMBER_ID": MEMBER_ID,
        "MEMBER_COUNTS": _sparse_text(MEMBER_SPARSE),
        "MEMBER_TYPE_CELLS": {
            str(index): list(cells) for index, cells in member_type_cells().items()
        },
        "ALREADY_CERTIFIED_MEMBER": {
            **prior,
            "RECOMPUTED": False,
            "COVERED_BY_THIS_CERTIFICATE": False,
        },
        "R24_LEDGER": {
            "STATE_TERM": ledger.state_term,
            "REGION_COMPRESSED_MEMBERS": ledger.region_member_count,
            "MEMBER_RAW_BOUND": ledger.member_raw_bound,
            "MEMBER_FINAL_BOUND": ledger.member_final_bound,
            "MEMBER_REPRESENTED_VECTOR_COUNT": ledger.member_represented_vector_count,
            "PRIOR_MEMBER_FINAL_BOUND": ledger.prior_member_final_bound,
            "LADDER_FINAL_BOUNDS": list(ledger.ladder_final_bounds),
            "R3_BOUND": ledger.r3_bound,
            "R3_FORMULA": ledger.r3_formula,
            "UNCLASSIFIED_TAIL_BOUND": ledger.unclassified_tail_bound,
        },
        "EVENT_DEFINITION_STATUS": "VERIFIED_EXACT_SAME_RESIDUAL_EVENTS",
        "EVENT_DEFINITION": {
            "SOURCE": "hunter.event_decomposition evaluated on the target member",
            "OUTCOME_MODEL": lemma,
            "RESIDUAL_EVENT": (
                "R_C = E_C minus (E_A union E_B): 7-sets X with |C n X| >= 3, "
                "|A n X| <= 2 and |B n X| <= 2, times 7 outcomes"
            ),
            "ANCHOR_UNION": events.anchor_union,
            "RESIDUAL_EVENT_SIZES": [list(row) for row in events.residual_event_sizes],
            "RESIDUAL_SUM": events.residual_sum,
            "RAW_UNION_BOUND_NO_CORRECTION": events.raw_union_bound,
            "ANCHOR_PAIR_S2": events.anchor_pair_s2,
            "ANCHOR_TRIPLE_S3": events.anchor_triple_s3,
            "COMMITTED_RAW_BOUND_REPLAY": (
                "raw - max(R5 forest, R6 pair sum) equals the R24 member raw and final bound"
            ),
        },
        "TYPE16_EFFECT": type16_effect(events, rows),
        "PAIR_TABLE_STATUS": f"VERIFIED_{len(rows)}_ROWS_INDEPENDENT_REPLAY_EQUALS_R8",
        "PAIR_TABLE": {
            "TYPE_PAIRS": [list(pair) for pair in occurring_type_pairs()],
            "TYPE_PAIR_EDGE_COUNTS": [
                [*pair, count] for pair, count in type_pair_edge_counts().items()
            ],
            "ROW_COUNT": len(rows),
            "ROWS": [
                [row.left_type, row.right_type, *row.overlap, row.residual_intersection]
                for row in rows
            ],
            "ROW_COLUMNS": ["left", "right", "shared", "a_only", "b_only", "outside", "value"],
            "ROWS_SHA256": certificate.pair_rows_sha256,
            "GLOBAL_PAIR_FLOORS": list(certificate.global_pair_floors),
            "EDGE_CLASSES": {
                OUTSIDE_INCIDENT: "a residual pair with a type-0 endpoint: (0,0), (0,5), (0,16)",
                CORE: "a residual pair inside the 4 type-5 and 1 type-16 tickets: (5,5), (5,16)",
            },
            "CLASS_EDGE_COUNTS": dict(zip(CLASS_NAMES, certificate.class_edge_counts, strict=True)),
            "CLASS_PAIR_FLOORS": {
                name: list(floors)
                for name, floors in zip(CLASS_NAMES, certificate.class_pair_floors, strict=True)
            },
            "FLOOR_RULE": "phi_c(t) = min of every exact row of class c with total overlap t",
            "FAMILY_SOURCE_CEILING": hunter.family_pair_overlap_ceiling(),
            "R6_OVERLAP_VECTORS_EQUAL": True,
        },
        "COLLISION_FLOOR_STATUS": f"VERIFIED_{certificate.collision_floor}",
        "COLLISION_FLOOR": {
            "CELL_INCIDENCES": list(certificate.cell_incidences),
            "CELL_LABELS": [len(labels) for labels in hunter.CELL_LABELS],
            "CELL_FLOORS": list(certificate.cell_collision_floors),
            "TOTAL": certificate.collision_floor,
            "IDENTITY": (
                "sum_{i<j} t_ij = sum_x C(d_x,2); t <= 3 gives sum_c (e_c1 + e_c2 + e_c3)"
            ),
            "BALANCED_MASS_EXHAUSTIVE_ROWS": balanced_rows,
        },
        "TREE_RANK_STATUS": "PROVED_CLASS_THRESHOLD_TREE_WITH_EXHAUSTIVE_REGRESSION",
        "TREE_RANK_PROOF": {
            "HUNTER_SOURCE": "committed Hunter inequality of " + hunter.MODULE_RELATIVE,
            "CLASS_THRESHOLD_TREE": (
                "Kruskal in decreasing phi_c(t_e) is nested over every level set "
                "E_lambda = {e : phi_c(e)(t_e) >= lambda}, so its phi-weight is "
                "sum_i (lambda_i - lambda_{i-1}) rank(E_lambda_i) over the sorted class floors"
            ),
            "LEVEL_SET_SIZE": (
                "phi_c nondecreasing, so |E_lambda| = sum_c e_c,k_c(lambda) with "
                "k_c(lambda) = min{t : phi_c(t) >= lambda} and e_c,0 = |c|"
            ),
            "RANK_FLOOR": "rank(E) >= rho(|E|), rho(e) = min{r : C(r+1,2) >= e} (committed)",
            **regressions,
        },
        "FINITE_MINIMISATION_STATUS": "EXACT_CENSUS_REPRODUCED",
        "TREE_MINIMUM": {
            "CENSUS": (
                f"{certificate.class_edge_counts[0]} >= e_O1 >= e_O2 >= e_O3 >= 0, "
                f"{certificate.class_edge_counts[1]} >= e_C1 >= e_C2 >= e_C3 >= 0, "
                f"total mass == {certificate.collision_floor}"
            ),
            "MASS_REDUCTION": (
                "objective nondecreasing in every e_c,k; lowering a class's top nonzero "
                "count keeps it nested, so mass >= Q reduces to mass == Q"
            ),
            "CENSUS_SIZE": split.census_size,
            "MINIMIZER_COUNTS": {
                name: list(counts)
                for name, counts in zip(CLASS_NAMES, split.edge_counts, strict=True)
            },
            "LEVELS": level_table(classes, split.edge_counts),
            "SINGLE_CLASS_REPLAY_EQUALS_COMMITTED_CENSUS": True,
            "HOMOGENEOUS_CENSUS_SIZE": homogeneous.census_size,
            "HOMOGENEOUS_MINIMIZER_E": list(homogeneous.edge_counts),
        },
        "CORRECTIONS": {
            **existing,
            "HUNTER_HOMOGENEOUS": certificate.homogeneous_hunter_correction,
            "HUNTER_CLASS_SPLIT": certificate.class_hunter_correction,
            "COMBINATION": "MAX_OF_VALID_LOWER_BOUNDS_NEVER_SUM",
            "CERTIFIED_CORRECTION": certificate.certified_correction,
        },
        "RAW_BOUND": ledger.member_raw_bound,
        "RATIONAL_BOUND": rational_bound,
        "HUNTER_CORRECTION": certificate.class_hunter_correction,
        "CERTIFIED_MEMBER_BOUND": certificate.certified_member_bound,
        "ADDITIONAL_REDUCTION_VS_RATIONAL": rational_bound - certificate.certified_member_bound,
        "REDUCTION_FROM_R24_LEDGER": ledger.member_final_bound - certificate.certified_member_bound,
        "WITNESS_SOUNDNESS_STATUS": "CONSISTENT",
        "WITNESS": {
            "ANCHORS": [sorted(hunter.ANCHOR_A), sorted(hunter.ANCHOR_B)],
            "OUTCOME_SET": sorted(WITNESS_OUTCOME_SET),
            "RESIDUAL_TICKETS": [list(ticket) for ticket in witness_residual_tickets()],
            "CONSTRUCTION": (
                f"committed [0,13][5,5] witness with type-{witness.replaced_type} ticket "
                f"{list(WITNESS_REPLACED_TICKET)} replaced by type-{witness.inserted_type} "
                f"ticket {list(WITNESS_TYPE16_TICKET)}"
            ),
            "MEMBER_COUNTS": _sparse_text(witness.member_sparse),
            "MAXIMUM_PAIR_OVERLAP": witness.maximum_pair_overlap,
            "ANCHOR_HITS_ON_OUTCOME_SET": list(witness.anchor_hits_on_outcome_set),
            "RESIDUAL_MULTIPLICITY": witness.residual_multiplicity,
            "OVERLAP_HISTOGRAM_0_TO_3": list(witness.overlap_histogram),
            "COLLISION_MASS": witness.collision_mass,
            "LABEL_COLLISION_MASS": witness.label_collision_mass,
            "CLASS_NESTED_COUNTS": {
                name: list(counts)
                for name, counts in zip(CLASS_NAMES, witness.class_nested_counts, strict=True)
            },
            "CENSUS_OBJECTIVE": witness.census_objective,
            "PHI_TREE_WEIGHT": witness.floor_tree_weight,
            "EXACT_MAXIMUM_TREE_WEIGHT": witness.exact_tree_weight,
            "EXACT_PAIRS_EQUAL_TABLE_ROWS": witness.exact_rows_match_table,
            "MEANING": (
                "On a real member portfolio: certificate <= census objective <= phi-tree "
                "weight <= exact maximum tree weight <= true union correction"
            ),
        },
        "R3_DURABLE_BOUND": ledger.r3_bound,
        "R3_DURABLE_BOUND_UNCHANGED": True,
        "R3_BOUND_CLAIM": "NONE",
        "STATE_TERM_CLAIM": "NONE",
        "CERTIFICATE_SCOPE": f"{STATE_ID} member {MEMBER_ID} only",
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the committed result JSON")
    arguments = parser.parse_args(argv)
    text = hunter.encode(build_result())
    if arguments.write:
        RESULT_PATH.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
