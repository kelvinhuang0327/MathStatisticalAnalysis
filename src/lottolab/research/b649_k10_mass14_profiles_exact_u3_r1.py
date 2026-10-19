"""Exact U3 closure of full-support K10 mass-14 through mass-17 profiles.

PROFILE_A ``(0, 40, 8, 0, 1, ...)`` is 8 pair supports plus 1 quadruple support.
PROFILE_B ``(0, 41, 5, 3, 0, ...)`` is 5 pair supports plus 3 triple supports.

Every singleton label sits in exactly one ticket, so a portfolio is fixed up to
number relabeling by its repeated-label supports on the ten ticket vertices. A
support-system isomorphism class is therefore a pair multigraph class plus an
orbit of the higher supports under that graph's full automorphism group,
including arbitrary permutations of the isolated ticket vertices.

The mass-13 helper ``enumerate_unlabeled_multigraphs`` caps connected components
at six vertices. That is exact for pair mass at most 5 and incomplete from pair
mass 6 up, so the pair graphs here come from an edge-addition closure instead.
Completeness is proven rather than assumed:

* the labeled-count identity ``sum(10! / |Aut|) == C(45 + e - 1, e)`` over the
  pair graph classes;
* the orbit count of the higher supports over every graph class, computed twice,
  once by explicit orbit growth and once by Burnside's lemma on cycle types.

The exact third-order Bonferroni numerator reuses the K9 pair-joint and
triple-region calculations and is checked against the public
``u3_outcome_count``. A profile is closed only when its exact maximum is at or
below the incumbent.
"""

from __future__ import annotations

import itertools
import json
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from hashlib import sha256
from math import comb, factorial, prod

from lottolab.research.b649_k1_k8_global_optimality import (
    PrizeEvent,
    independent_single_outcome_count,
)
from lottolab.research.b649_k9_min_mass_and_global_bound_r1 import (
    _pair_joint_counts,  # pyright: ignore[reportPrivateUsage]
    _regions_for_triple,  # pyright: ignore[reportPrivateUsage]
    enumerate_unlabeled_multigraphs,
)
from lottolab.research.b649_k10_overlap_mass12_bonferroni_screen_r1 import (
    _joint_count_from_regions,  # pyright: ignore[reportPrivateUsage]
    u3_outcome_count,
)
from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
)

TICKET_COUNT = 10
POOL_SIZE = 49
DRAW_SIZE = 6
INCUMBENT_COUNT = 176_345_645
EXACT_SCORE_MAX_WITNESSES = 8
OVERLAP_MASS = 14
PROGRESS_EVERY = 10

type Edge = tuple[int, int, int]
type Perm = tuple[int, ...]
type Support = tuple[int, ...]
type Adjacency = tuple[tuple[int, ...], ...]


@dataclass(frozen=True, slots=True)
class ProfileSpec:
    """A multiplicity histogram made of pair supports and higher supports."""

    name: str
    profile: tuple[int, ...]
    pair_label_count: int
    support_size: int
    higher_label_count: int
    extra_higher_support_counts: tuple[tuple[int, int], ...] = ()

    @property
    def higher_support_counts(self) -> tuple[tuple[int, int], ...]:
        """Counts of higher supports, grouped by support size."""

        counts = Counter({self.support_size: self.higher_label_count})
        for support_size, label_count in self.extra_higher_support_counts:
            counts[support_size] += label_count
        return tuple(sorted((size, count) for size, count in counts.items() if count))

    @property
    def repeated_support_counts(self) -> tuple[tuple[int, int], ...]:
        """Counts of all repeated-label supports, including pairs."""

        return ((2, self.pair_label_count), *self.higher_support_counts)

    @property
    def singleton_label_count(self) -> int:
        return TICKET_COUNT * DRAW_SIZE - sum(
            support_size * label_count for support_size, label_count in self.repeated_support_counts
        )


PROFILE_A = ProfileSpec("PROFILE_A", (0, 40, 8, 0, 1, 0, 0, 0, 0, 0, 0), 8, 4, 1)
PROFILE_B = ProfileSpec("PROFILE_B", (0, 41, 5, 3, 0, 0, 0, 0, 0, 0, 0), 5, 3, 3)
MASS14_PROFILES = (PROFILE_A, PROFILE_B)
MASS15_PROFILE_A = ProfileSpec("PROFILE_A", (0, 42, 3, 4, 0, 0, 0, 0, 0, 0, 0), 3, 3, 4)
MASS15_PROFILE_B = ProfileSpec("PROFILE_B", (0, 41, 6, 1, 1, 0, 0, 0, 0, 0, 0), 6, 3, 1, ((4, 1),))
MASS15_PROFILES = (MASS15_PROFILE_A, MASS15_PROFILE_B)


def derive_mass16_profiles() -> tuple[tuple[int, ...], ...]:
    """Derive mass-16 histograms by two independent bounded stdlib enumerations."""

    repeated_sizes = tuple(range(2, TICKET_COUNT + 1))
    excess = TICKET_COUNT * DRAW_SIZE - POOL_SIZE
    residual_overlap = 16 - excess

    def make_profile(repeated_counts: tuple[int, ...]) -> tuple[int, ...] | None:
        profile = [0] * (TICKET_COUNT + 1)
        for size, count in zip(repeated_sizes, repeated_counts, strict=True):
            profile[size] = count
        profile[1] = POOL_SIZE - sum(profile[2:])
        result = tuple(profile)
        if (
            profile[1] < 0
            or sum(result) != POOL_SIZE
            or sum(size * count for size, count in enumerate(result)) != TICKET_COUNT * DRAW_SIZE
            or sum(comb(size, 2) * count for size, count in enumerate(result)) != 16
        ):
            return None
        return result

    # Directly enumerate the bounded multiplicity box using the two reduced equations:
    # sum((r - 1) * n_r) = 11 and sum(C(r - 1, 2) * n_r) = 5.
    direct_profiles: set[tuple[int, ...]] = set()
    bounds = tuple(range(excess // (size - 1) + 1) for size in repeated_sizes)
    for repeated_counts in itertools.product(*bounds):
        if (
            sum(
                (size - 1) * count
                for size, count in zip(repeated_sizes, repeated_counts, strict=True)
            )
            != excess
        ):
            continue
        if (
            sum(
                comb(size - 1, 2) * count
                for size, count in zip(repeated_sizes, repeated_counts, strict=True)
            )
            != residual_overlap
        ):
            continue
        profile = make_profile(repeated_counts)
        if profile is not None:
            direct_profiles.add(profile)

    # Independently enumerate non-increasing partitions of the repeated-incidence excess.
    partition_profiles: set[tuple[int, ...]] = set()

    def visit_partition(
        remaining: int, largest_part: int, overlap: int, parts: tuple[int, ...]
    ) -> None:
        if remaining == 0:
            if overlap != residual_overlap:
                return
            repeated_counts = [0] * len(repeated_sizes)
            for part in parts:
                repeated_counts[part - 1] += 1
            profile = make_profile(tuple(repeated_counts))
            if profile is not None:
                partition_profiles.add(profile)
            return
        for part in range(min(largest_part, remaining, TICKET_COUNT - 1), 0, -1):
            next_overlap = overlap + comb(part, 2)
            if next_overlap <= residual_overlap:
                visit_partition(remaining - part, part, next_overlap, (*parts, part))

    visit_partition(excess, TICKET_COUNT - 1, 0, ())
    if direct_profiles != partition_profiles:
        raise ValueError(
            "independent mass-16 profile enumerations disagree: "
            f"{sorted(direct_profiles)} != {sorted(partition_profiles)}"
        )
    return tuple(sorted(direct_profiles, reverse=True))


def _mass16_profile_specs(profiles: tuple[tuple[int, ...], ...]) -> tuple[ProfileSpec, ...]:
    """Translate derived mass-16 histograms into the existing support census model."""

    specs: list[ProfileSpec] = []
    for index, profile in enumerate(profiles):
        higher_counts = tuple(
            (size, profile[size]) for size in range(3, len(profile)) if profile[size]
        )
        if len(profile) != TICKET_COUNT + 1 or not higher_counts:
            raise ValueError(f"invalid derived mass-16 profile: {profile}")
        base_size, base_count = higher_counts[0]
        specs.append(
            ProfileSpec(
                name=f"PROFILE_{chr(ord('A') + index)}",
                profile=profile,
                pair_label_count=profile[2],
                support_size=base_size,
                higher_label_count=base_count,
                extra_higher_support_counts=higher_counts[1:],
            )
        )
    return tuple(specs)


def derive_mass17_profiles() -> tuple[tuple[int, ...], ...]:
    """Derive mass-17 histograms by two independent bounded stdlib enumerations."""

    repeated_sizes = tuple(range(2, TICKET_COUNT + 1))
    excess = TICKET_COUNT * DRAW_SIZE - POOL_SIZE
    residual_overlap = 17 - excess

    def make_profile(repeated_counts: tuple[int, ...]) -> tuple[int, ...] | None:
        profile = [0] * (TICKET_COUNT + 1)
        for size, count in zip(repeated_sizes, repeated_counts, strict=True):
            profile[size] = count
        profile[1] = POOL_SIZE - sum(profile[2:])
        result = tuple(profile)
        if (
            profile[1] < 0
            or sum(result) != POOL_SIZE
            or sum(size * count for size, count in enumerate(result)) != TICKET_COUNT * DRAW_SIZE
            or sum(comb(size, 2) * count for size, count in enumerate(result)) != 17
        ):
            return None
        return result

    # The reduced equations are sum((r - 1) * n_r) = 11 and
    # sum(C(r - 1, 2) * n_r) = 6.
    direct_profiles: set[tuple[int, ...]] = set()
    bounds = tuple(range(excess // (size - 1) + 1) for size in repeated_sizes)
    for repeated_counts in itertools.product(*bounds):
        if (
            sum(
                (size - 1) * count
                for size, count in zip(repeated_sizes, repeated_counts, strict=True)
            )
            != excess
        ):
            continue
        if (
            sum(
                comb(size - 1, 2) * count
                for size, count in zip(repeated_sizes, repeated_counts, strict=True)
            )
            != residual_overlap
        ):
            continue
        profile = make_profile(repeated_counts)
        if profile is not None:
            direct_profiles.add(profile)

    # Independently enumerate non-increasing partitions of the repeated-incidence excess.
    partition_profiles: set[tuple[int, ...]] = set()

    def visit_partition(
        remaining: int, largest_part: int, overlap: int, parts: tuple[int, ...]
    ) -> None:
        if remaining == 0:
            if overlap != residual_overlap:
                return
            repeated_counts = [0] * len(repeated_sizes)
            for part in parts:
                repeated_counts[part - 1] += 1
            profile = make_profile(tuple(repeated_counts))
            if profile is not None:
                partition_profiles.add(profile)
            return
        for part in range(min(largest_part, remaining, TICKET_COUNT - 1), 0, -1):
            next_overlap = overlap + comb(part, 2)
            if next_overlap <= residual_overlap:
                visit_partition(remaining - part, part, next_overlap, (*parts, part))

    visit_partition(excess, TICKET_COUNT - 1, 0, ())
    if direct_profiles != partition_profiles:
        raise ValueError(
            "independent mass-17 profile enumerations disagree: "
            f"{sorted(direct_profiles)} != {sorted(partition_profiles)}"
        )
    return tuple(sorted(direct_profiles, reverse=True))


FROZEN_MASS17_PROFILES = (
    (0, 43, 2, 3, 1, 0, 0, 0, 0, 0, 0),
    (0, 42, 5, 0, 2, 0, 0, 0, 0, 0, 0),
    (0, 41, 7, 0, 0, 1, 0, 0, 0, 0, 0),
)
MASS17_PROFILES = FROZEN_MASS17_PROFILES


def _mass17_profile_specs(profiles: tuple[tuple[int, ...], ...]) -> tuple[ProfileSpec, ...]:
    """Translate frozen mass-17 histograms into the existing support census model."""

    specs: list[ProfileSpec] = []
    for index, profile in enumerate(profiles):
        higher_counts = tuple(
            (size, profile[size]) for size in range(3, len(profile)) if profile[size]
        )
        if len(profile) != TICKET_COUNT + 1 or not higher_counts:
            raise ValueError(f"invalid derived mass-17 profile: {profile}")
        base_size, base_count = higher_counts[0]
        specs.append(
            ProfileSpec(
                name=f"MASS17_PROFILE_{chr(ord('A') + index)}",
                profile=profile,
                pair_label_count=profile[2],
                support_size=base_size,
                higher_label_count=base_count,
                extra_higher_support_counts=higher_counts[1:],
            )
        )
    return tuple(specs)


# Diagnostic only: the upstream mass-13 profile, re-censused with the complete enumerator.
PROFILE_MASS13 = ProfileSpec("MASS13_RECHECK", (0, 40, 7, 2, 0, 0, 0, 0, 0, 0, 0), 7, 3, 2)


@dataclass(frozen=True, slots=True)
class SupportSystem:
    """Canonical repeated-label supports on a fixed set of ticket vertices."""

    vertex_count: int
    pair_supports: tuple[Support, ...]
    higher_supports: tuple[Support, ...]

    @property
    def class_id(self) -> str:
        """Stable support-class identity, retaining isolated ticket vertices."""

        return json.dumps(
            {
                "higher": [list(support) for support in self.higher_supports],
                "pairs": [list(support) for support in self.pair_supports],
                "tickets": self.vertex_count,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def profile_arithmetic(
    spec: ProfileSpec,
) -> dict[str, int | tuple[int, ...] | tuple[tuple[int, int], ...]]:
    """Return the load-bearing arithmetic implied by the frozen histogram."""

    labels = sum(spec.profile)
    incidences = sum(multiplicity * count for multiplicity, count in enumerate(spec.profile))
    overlap_mass = sum(
        comb(multiplicity, 2) * count
        for multiplicity, count in enumerate(spec.profile)
        if multiplicity >= 2
    )
    expected = [0] * len(spec.profile)
    expected[1] = spec.singleton_label_count
    for support_size, label_count in spec.repeated_support_counts:
        if support_size < 2 or support_size >= len(expected) or label_count < 0:
            raise ValueError(f"{spec.name}: invalid repeated-support count")
        expected[support_size] += label_count
    if tuple(expected) != spec.profile:
        raise ValueError(f"{spec.name}: support counts disagree with the histogram")
    return {
        "profile": spec.profile,
        "labels": labels,
        "ticket_incidences": incidences,
        "overlap_mass": overlap_mass,
        "pair_labels": spec.pair_label_count,
        "higher_support_counts": spec.higher_support_counts,
        "higher_labels": sum(count for _size, count in spec.higher_support_counts),
        "singleton_incidences": spec.singleton_label_count,
    }


# ---------------------------------------------------------------------------
# Pair multigraph classes: complete edge-addition closure with exact isomorphism.
# ---------------------------------------------------------------------------


def _refined_colors(adjacency: Adjacency) -> tuple[int, ...]:
    """Isomorphism-invariant vertex colors that are comparable across graphs.

    A hash collision can only weaken pruning: isomorphic vertices always share a
    color, and every mapping is re-checked against the exact adjacency.
    """

    width = len(adjacency)
    colors = tuple(sum(row) for row in adjacency)
    for _ in range(width):
        colors = tuple(
            hash(
                (
                    colors[vertex],
                    tuple(
                        sorted(
                            (colors[other], weight)
                            for other, weight in enumerate(adjacency[vertex])
                            if weight
                        )
                    ),
                )
            )
            for vertex in range(width)
        )
    return colors


def _isomorphisms(source: Adjacency, target: Adjacency) -> Iterator[Perm]:
    """Yield every weight-preserving vertex bijection from ``source`` to ``target``."""

    width = len(source)
    if width != len(target):
        return
    source_colors = _refined_colors(source)
    target_colors = _refined_colors(target)
    if sorted(source_colors) != sorted(target_colors):
        return
    domains = tuple(
        tuple(
            candidate for candidate in range(width) if target_colors[candidate] == source_colors[v]
        )
        for v in range(width)
    )
    order = tuple(sorted(range(width), key=lambda v: (len(domains[v]), -sum(source[v]), v)))
    mapping = [-1] * width
    used = [False] * width

    def extend(position: int) -> Iterator[Perm]:
        if position == width:
            yield tuple(mapping)
            return
        vertex = order[position]
        for candidate in domains[vertex]:
            if used[candidate]:
                continue
            if any(
                source[vertex][other] != target[candidate][mapping[other]]
                for other in order[:position]
            ):
                continue
            mapping[vertex] = candidate
            used[candidate] = True
            yield from extend(position + 1)
            used[candidate] = False
            mapping[vertex] = -1

    yield from extend(0)


def _isomorphic(left: Adjacency, right: Adjacency) -> bool:
    return next(_isomorphisms(left, right), None) is not None


def _child_graphs(adjacency: Adjacency, vertex_count: int) -> Iterator[Adjacency]:
    """Every graph reached by adding one unit of multiplicity, new vertices appended."""

    width = len(adjacency)
    options = [(left, right) for left in range(width) for right in range(left + 1, width)]
    if width + 1 <= vertex_count:
        options.extend((left, width) for left in range(width))
    if width + 2 <= vertex_count:
        options.append((width, width + 1))
    for left, right in options:
        new_width = max(width, right + 1)
        matrix = [[*row, *([0] * (new_width - width))] for row in adjacency]
        matrix.extend([0] * new_width for _ in range(new_width - width))
        matrix[left][right] += 1
        matrix[right][left] += 1
        yield tuple(tuple(row) for row in matrix)


@cache
def _graph_levels(vertex_count: int, max_edges: int) -> tuple[tuple[Adjacency, ...], ...]:
    """Isomorphism classes of loopless multigraphs for every total multiplicity 0..max_edges.

    Deleting one unit of multiplicity (and any vertex left isolated) from a graph
    with ``k + 1`` edges gives a graph with ``k`` edges, so the closure under
    one-edge addition reaches every class.
    """

    levels: list[tuple[Adjacency, ...]] = [((),)]
    for _ in range(max_edges):
        buckets: dict[tuple[int, tuple[int, ...]], list[Adjacency]] = {}
        for adjacency in levels[-1]:
            for child in _child_graphs(adjacency, vertex_count):
                key = (len(child), tuple(sorted(_refined_colors(child))))
                bucket = buckets.setdefault(key, [])
                if not any(_isomorphic(child, kept) for kept in bucket):
                    bucket.append(child)
        levels.append(tuple(sorted(item for bucket in buckets.values() for item in bucket)))
    return tuple(levels)


def _edges_of(adjacency: Adjacency) -> tuple[Edge, ...]:
    width = len(adjacency)
    return tuple(
        (left, right, adjacency[left][right])
        for left in range(width)
        for right in range(left + 1, width)
        if adjacency[left][right]
    )


@dataclass(frozen=True, slots=True)
class PairGraphClass:
    """One pair multigraph class on contiguous active vertices ``0..width-1``."""

    adjacency: Adjacency
    edges: tuple[Edge, ...]
    automorphisms: tuple[Perm, ...]

    @property
    def width(self) -> int:
        return len(self.adjacency)

    @property
    def max_degree(self) -> int:
        return max((sum(row) for row in self.adjacency), default=0)


@dataclass(frozen=True, slots=True)
class PairGraphCensus:
    """All pair graph classes plus the exact labeled-count identity that proves them complete."""

    vertex_count: int
    edge_count: int
    classes: tuple[PairGraphClass, ...]
    labeled_total: int
    expected_total: int


def _labeled_class_size(vertex_count: int, width: int, automorphism_count: int) -> int:
    numerator = factorial(vertex_count)
    denominator = automorphism_count * factorial(vertex_count - width)
    quotient, remainder = divmod(numerator, denominator)
    if remainder:
        raise ValueError("graph automorphism order does not divide the labeled orbit")
    return quotient


def pair_graph_census(vertex_count: int, edge_count: int) -> PairGraphCensus:
    """Enumerate every pair graph class and prove the list complete and duplicate-free."""

    if vertex_count < 2 or edge_count < 0:
        raise ValueError("census needs two vertices and a nonnegative edge count")
    classes: list[PairGraphClass] = []
    labeled_total = 0
    for adjacency in _graph_levels(vertex_count, edge_count)[edge_count]:
        automorphisms = tuple(sorted(_isomorphisms(adjacency, adjacency)))
        if not automorphisms:
            raise ValueError("pair graph has no identity automorphism")
        classes.append(PairGraphClass(adjacency, _edges_of(adjacency), automorphisms))
        labeled_total += _labeled_class_size(vertex_count, len(adjacency), len(automorphisms))
    expected_total = comb(comb(vertex_count, 2) + edge_count - 1, edge_count)
    if labeled_total != expected_total:
        raise ValueError(
            f"pair graph census is not complete: {labeled_total} != {expected_total} "
            f"labeled multigraphs for {edge_count} edges"
        )
    return PairGraphCensus(vertex_count, edge_count, tuple(classes), labeled_total, expected_total)


def _parse_edge_class(class_id: str) -> tuple[Edge, ...]:
    if not class_id:
        return ()
    values = tuple(int(value) for value in class_id.split())
    if len(values) % 3:
        raise ValueError(f"invalid canonical multigraph class: {class_id!r}")
    return tuple(
        (values[index], values[index + 1], values[index + 2]) for index in range(0, len(values), 3)
    )


def _adjacency_of(edges: Sequence[Edge]) -> Adjacency:
    width = max((right for _left, right, _multiplicity in edges), default=-1) + 1
    matrix = [[0] * width for _ in range(width)]
    for left, right, multiplicity in edges:
        matrix[left][right] = multiplicity
        matrix[right][left] = multiplicity
    return tuple(tuple(row) for row in matrix)


def legacy_enumerator_coverage(edge_count: int) -> dict[str, int]:
    """Labeled multigraphs covered by the mass-13 helper, against the exact total.

    The helper is called with no degree restriction so the comparison is against
    the full ``C(45 + e - 1, e)`` labeled multigraph count.
    """

    legacy = enumerate_unlabeled_multigraphs(TICKET_COUNT, edge_count, edge_count)
    covered = 0
    for class_id in legacy:
        adjacency = _adjacency_of(_parse_edge_class(class_id))
        automorphism_count = sum(1 for _ in _isomorphisms(adjacency, adjacency))
        covered += _labeled_class_size(TICKET_COUNT, len(adjacency), automorphism_count)
    expected = comb(comb(TICKET_COUNT, 2) + edge_count - 1, edge_count)
    complete = len(pair_graph_census(TICKET_COUNT, edge_count).classes)
    return {
        "edge_count": edge_count,
        "legacy_class_count": len(legacy),
        "complete_class_count": complete,
        "legacy_labeled_total": covered,
        "expected_labeled_total": expected,
        "labeled_multigraphs_missed": expected - covered,
    }


# ---------------------------------------------------------------------------
# Higher-support orbits under each graph's full automorphism group.
# ---------------------------------------------------------------------------


def _compose(left: Perm, right: Perm) -> Perm:
    return tuple(left[right[vertex]] for vertex in range(len(left)))


def _inverse(permutation: Perm) -> Perm:
    inverse = [0] * len(permutation)
    for source, target in enumerate(permutation):
        inverse[target] = source
    return tuple(inverse)


def _group_generators(automorphisms: tuple[Perm, ...]) -> tuple[Perm, ...]:
    """Select generators whose closure is exactly the enumerated automorphism group."""

    if not automorphisms:
        raise ValueError("automorphism list cannot be empty")
    width = len(automorphisms[0])
    identity = tuple(range(width))
    automorphism_set = set(automorphisms)
    if identity not in automorphism_set:
        raise ValueError("automorphism group lacks the identity")
    generators: list[Perm] = []
    closure = {identity}
    for candidate in automorphisms:
        if candidate in closure:
            continue
        generators.append(candidate)
        steps = tuple(
            dict.fromkeys(
                step for generator in generators for step in (generator, _inverse(generator))
            )
        )
        closure = {identity}
        pending = [identity]
        while pending:
            current = pending.pop()
            for step in steps:
                reached = _compose(step, current)
                if reached not in closure:
                    closure.add(reached)
                    pending.append(reached)
        if not closure.issubset(automorphism_set):
            raise ValueError("selected generators leave the automorphism group")
        if len(closure) == len(automorphism_set):
            break
    if len(closure) != len(automorphism_set):
        raise ValueError("selected generators do not span every automorphism")
    return tuple(generators)


def _full_group_generators(graph: PairGraphClass, vertex_count: int) -> tuple[Perm, ...]:
    """Generators of Aut(active graph) x Sym(isolated ticket vertices)."""

    width = graph.width
    if width > vertex_count:
        raise ValueError("pair graph exceeds the ticket vertex set")
    full: list[Perm] = [
        (*generator, *range(width, vertex_count))
        for generator in _group_generators(graph.automorphisms)
    ]
    isolated_count = vertex_count - width
    if isolated_count == 2:
        swap = list(range(vertex_count))
        swap[width], swap[width + 1] = swap[width + 1], swap[width]
        full.append(tuple(swap))
    elif isolated_count > 2:
        cycle = list(range(vertex_count))
        for offset in range(isolated_count):
            cycle[width + offset] = width + (offset + 1) % isolated_count
        full.append(tuple(cycle))
        swap = list(range(vertex_count))
        swap[width], swap[width + 1] = swap[width + 1], swap[width]
        full.append(tuple(swap))
    return tuple(dict.fromkeys(full))


def _multiset_rank_weights(domain_size: int, multiset_size: int) -> tuple[tuple[int, ...], ...]:
    """Precompute combinadic terms used to rank every multiset in a fixed state space."""

    return tuple(
        tuple(comb(value + position, position + 1) for value in range(domain_size))
        for position in range(multiset_size)
    )


def _multiset_rank(state: tuple[int, ...], rank_weights: tuple[tuple[int, ...], ...]) -> int:
    """Rank a sorted multiset without materializing the full state table."""

    return sum(rank_weights[position][value] for position, value in enumerate(state))


def _higher_support_orbits(
    vertex_count: int,
    support_size: int,
    label_count: int,
    generators: tuple[Perm, ...],
) -> tuple[tuple[tuple[int, ...], int], ...]:
    """Lexicographically minimal state and orbit size of every multiset orbit."""

    if label_count < 0:
        raise ValueError("higher label count must be nonnegative")
    if label_count == 0:
        return (((), 1),)
    supports = tuple(itertools.combinations(range(vertex_count), support_size))
    if not supports:
        return ()
    support_index = {support: index for index, support in enumerate(supports)}
    actions: list[tuple[int, ...]] = []
    for generator in generators:
        if len(generator) != vertex_count:
            raise ValueError("automorphism generator has the wrong vertex count")
        actions.append(
            tuple(
                support_index[tuple(sorted(generator[vertex] for vertex in support))]
                for support in supports
            )
        )

    state_count = comb(len(supports) + label_count - 1, label_count)
    rank_weights = _multiset_rank_weights(len(supports), label_count)
    seen = bytearray(state_count)
    orbits: list[tuple[tuple[int, ...], int]] = []
    for state in itertools.combinations_with_replacement(range(len(supports)), label_count):
        start_index = _multiset_rank(state, rank_weights)
        if seen[start_index]:
            continue
        seen[start_index] = 1
        size = 1
        pending = [state]
        while pending:
            current = pending.pop()
            for action in actions:
                image = tuple(sorted(action[index] for index in current))
                image_index = _multiset_rank(image, rank_weights)
                if not seen[image_index]:
                    seen[image_index] = 1
                    size += 1
                    pending.append(image)
        orbits.append((state, size))
    if sum(size for _state, size in orbits) != state_count:
        raise ValueError("orbit sizes do not partition the multiset states")
    return tuple(orbits)


def _higher_support_orbits_for_counts(
    vertex_count: int,
    support_counts: tuple[tuple[int, int], ...],
    generators: tuple[Perm, ...],
) -> tuple[tuple[tuple[Support, ...], int], ...]:
    """Enumerate joint orbits when higher labels have different support sizes."""

    groups = tuple((size, count) for size, count in support_counts if count)
    if any(size < 2 or size > vertex_count or count < 0 for size, count in groups):
        raise ValueError("invalid higher-support size or count")
    if not groups:
        return (((), 1),)
    if len(groups) == 1:
        support_size, label_count = groups[0]
        supports = tuple(itertools.combinations(range(vertex_count), support_size))
        return tuple(
            (tuple(supports[index] for index in state), orbit_size)
            for state, orbit_size in _higher_support_orbits(
                vertex_count, support_size, label_count, generators
            )
        )

    supports_by_group = tuple(
        tuple(itertools.combinations(range(vertex_count), support_size))
        for support_size, _count in groups
    )
    if any(not supports for supports in supports_by_group):
        return ()
    state_groups = tuple(
        tuple(itertools.combinations_with_replacement(range(len(supports)), label_count))
        for supports, (_support_size, label_count) in zip(supports_by_group, groups, strict=True)
    )
    radices = tuple(len(states) for states in state_groups)
    state_count = prod(radices)
    rank_weights = tuple(
        _multiset_rank_weights(len(supports), label_count)
        for supports, (_support_size, label_count) in zip(supports_by_group, groups, strict=True)
    )
    support_actions: list[tuple[tuple[int, ...], ...]] = []
    for supports in supports_by_group:
        support_index = {support: index for index, support in enumerate(supports)}
        actions: list[tuple[int, ...]] = []
        for generator in generators:
            if len(generator) != vertex_count:
                raise ValueError("automorphism generator has the wrong vertex count")
            actions.append(
                tuple(
                    support_index[tuple(sorted(generator[vertex] for vertex in support))]
                    for support in supports
                )
            )
        support_actions.append(tuple(actions))

    seen = bytearray(state_count)
    orbits: list[tuple[tuple[Support, ...], int]] = []

    def state_index(state: tuple[tuple[int, ...], ...]) -> int:
        rank = 0
        for group_index, _supports in enumerate(supports_by_group):
            rank = rank * radices[group_index] + _multiset_rank(
                state[group_index], rank_weights[group_index]
            )
        return rank

    for state in itertools.product(*state_groups):
        start_index = state_index(state)
        if seen[start_index]:
            continue
        seen[start_index] = 1
        size = 1
        pending = [state]
        while pending:
            current = pending.pop()
            for generator_index in range(len(generators)):
                image = tuple(
                    tuple(
                        sorted(
                            support_actions[group_index][generator_index][index] for index in group
                        )
                    )
                    for group_index, group in enumerate(current)
                )
                image_index = state_index(image)
                if not seen[image_index]:
                    seen[image_index] = 1
                    size += 1
                    pending.append(image)
        supports = tuple(
            support
            for group_index, group in enumerate(state)
            for support in (supports_by_group[group_index][index] for index in group)
        )
        orbits.append((supports, size))
    if sum(size for _supports, size in orbits) != state_count:
        raise ValueError("mixed-support orbit sizes do not partition the multiset states")
    return tuple(orbits)


def _partitions(total: int, largest: int | None = None) -> Iterator[tuple[int, ...]]:
    if total == 0:
        yield ()
        return
    cap = total if largest is None else min(largest, total)
    for part in range(cap, 0, -1):
        for rest in _partitions(total - part, part):
            yield (part, *rest)


def _symmetric_class_size(partition: tuple[int, ...]) -> int:
    denominator = 1
    for length, multiplicity in Counter(partition).items():
        denominator *= length**multiplicity * factorial(multiplicity)
    return factorial(sum(partition)) // denominator


def _cycle_type(permutation: Perm) -> tuple[int, ...]:
    seen = [False] * len(permutation)
    lengths: list[int] = []
    for start in range(len(permutation)):
        if seen[start]:
            continue
        length = 0
        vertex = start
        while not seen[vertex]:
            seen[vertex] = True
            vertex = permutation[vertex]
            length += 1
        lengths.append(length)
    return tuple(sorted(lengths))


@cache
def _fixed_multiset_count(cycle_type: tuple[int, ...], support_size: int, label_count: int) -> int:
    """Multisets of ``label_count`` supports fixed by any permutation of this cycle type."""

    vertex_count = sum(cycle_type)
    permutation = [0] * vertex_count
    start = 0
    for length in cycle_type:
        for offset in range(length):
            permutation[start + offset] = start + (offset + 1) % length
        start += length
    supports = tuple(itertools.combinations(range(vertex_count), support_size))
    index = {support: position for position, support in enumerate(supports)}
    induced = tuple(
        index[tuple(sorted(permutation[vertex] for vertex in support))] for support in supports
    )
    ways = [0] * (label_count + 1)
    ways[0] = 1
    for length in _cycle_type(induced):
        for total in range(length, label_count + 1):
            ways[total] += ways[total - length]
    return ways[label_count]


def burnside_orbit_count(
    graph: PairGraphClass, vertex_count: int, support_size: int, label_count: int
) -> int:
    """Orbit count of support multisets by Burnside, independent of explicit orbit growth."""

    return _burnside_orbit_count_for_counts(graph, vertex_count, ((support_size, label_count),))


def _burnside_orbit_count_for_counts(
    graph: PairGraphClass,
    vertex_count: int,
    support_counts: tuple[tuple[int, int], ...],
) -> int:
    """Burnside count for the joint action on all higher-support size groups."""

    isolated = vertex_count - graph.width
    partition_classes = tuple(
        (partition, _symmetric_class_size(partition)) for partition in _partitions(isolated)
    )
    total = 0
    for automorphism in graph.automorphisms:
        active_type = _cycle_type(automorphism)
        for partition, class_size in partition_classes:
            full_type = tuple(sorted((*active_type, *partition)))
            fixed_states = prod(
                _fixed_multiset_count(full_type, support_size, label_count)
                for support_size, label_count in support_counts
            )
            total += class_size * fixed_states
    quotient, remainder = divmod(total, len(graph.automorphisms) * factorial(isolated))
    if remainder:
        raise ValueError("Burnside sum is not divisible by the group order")
    return quotient


def _systems_for_graph(
    graph: PairGraphClass,
    vertex_count: int,
    support_size: int,
    higher_label_count: int,
) -> Iterator[tuple[SupportSystem, int]]:
    pair_supports = tuple(
        (left, right) for left, right, multiplicity in graph.edges for _ in range(multiplicity)
    )
    supports = tuple(itertools.combinations(range(vertex_count), support_size))
    orbits = _higher_support_orbits(
        vertex_count,
        support_size,
        higher_label_count,
        _full_group_generators(graph, vertex_count),
    )
    for state, orbit_size in orbits:
        yield (
            SupportSystem(vertex_count, pair_supports, tuple(supports[index] for index in state)),
            orbit_size,
        )


def _systems_for_profile_graph(
    graph: PairGraphClass, vertex_count: int, spec: ProfileSpec
) -> Iterator[tuple[SupportSystem, int]]:
    pair_supports = tuple(
        (left, right) for left, right, multiplicity in graph.edges for _ in range(multiplicity)
    )
    orbits = _higher_support_orbits_for_counts(
        vertex_count,
        spec.higher_support_counts,
        _full_group_generators(graph, vertex_count),
    )
    for higher_supports, orbit_size in orbits:
        yield SupportSystem(vertex_count, pair_supports, higher_supports), orbit_size


def enumerate_support_systems(
    vertex_count: int,
    pair_label_count: int,
    support_size: int,
    higher_label_count: int,
) -> Iterator[SupportSystem]:
    """Yield one representative of every structural support-system isomorphism class."""

    census = pair_graph_census(vertex_count, pair_label_count)
    for graph in census.classes:
        for system, _orbit_size in _systems_for_graph(
            graph, vertex_count, support_size, higher_label_count
        ):
            yield system


# ---------------------------------------------------------------------------
# Legality, reconstruction, and the exact third-order Bonferroni numerator.
# ---------------------------------------------------------------------------


def _support_sets(system: SupportSystem) -> tuple[frozenset[int], ...]:
    return tuple(frozenset(support) for support in system.pair_supports) + tuple(
        frozenset(support) for support in system.higher_supports
    )


def is_legal_support_system(system: SupportSystem, spec: ProfileSpec) -> bool:
    """Check incidence capacity, singleton completion, label total, and ticket uniqueness."""

    if system.vertex_count != TICKET_COUNT:
        return False
    if len(system.pair_supports) != spec.pair_label_count:
        return False
    higher_label_count = sum(count for _size, count in spec.higher_support_counts)
    if len(system.higher_supports) != higher_label_count:
        return False
    singleton_count = spec.singleton_label_count
    label_total = singleton_count + spec.pair_label_count + higher_label_count
    if singleton_count < 0 or label_total != POOL_SIZE:
        return False
    expected_higher_sizes = Counter(dict(spec.higher_support_counts))
    actual_higher_sizes = Counter(len(support) for support in system.higher_supports)
    if actual_higher_sizes != expected_higher_sizes or any(
        len(set(support)) != len(support) for support in system.higher_supports
    ):
        return False

    degrees = [0] * TICKET_COUNT
    repeated_label_masks = [0] * TICKET_COUNT
    for label_index, support in enumerate(_support_sets(system)):
        if (label_index < spec.pair_label_count and len(support) != 2) or any(
            not 0 <= vertex < TICKET_COUNT for vertex in support
        ):
            return False
        for vertex in support:
            degrees[vertex] += 1
            repeated_label_masks[vertex] |= 1 << label_index
    if any(degree > DRAW_SIZE for degree in degrees):
        return False
    if sum(DRAW_SIZE - degree for degree in degrees) != singleton_count:
        return False

    full_tickets = [vertex for vertex, degree in enumerate(degrees) if degree == DRAW_SIZE]
    return all(
        repeated_label_masks[left] != repeated_label_masks[right]
        for offset, left in enumerate(full_tickets)
        for right in full_tickets[offset + 1 :]
    )


def reconstruct_portfolio(system: SupportSystem, spec: ProfileSpec) -> tuple[tuple[int, ...], ...]:
    """Fill every residual incidence with a globally unique singleton label."""

    if not is_legal_support_system(system, spec):
        raise ValueError("cannot reconstruct an illegal support system")
    tickets: list[list[int]] = [[] for _ in range(system.vertex_count)]
    next_label = 1
    for support in _support_sets(system):
        for vertex in sorted(support):
            tickets[vertex].append(next_label)
        next_label += 1
    for ticket in tickets:
        for _ in range(DRAW_SIZE - len(ticket)):
            ticket.append(next_label)
            next_label += 1
    if next_label - 1 != POOL_SIZE:
        raise ValueError("support system did not use the complete label universe")

    portfolio = tuple(tuple(sorted(ticket)) for ticket in tickets)
    if len(set(portfolio)) != system.vertex_count:
        raise ValueError("support system reconstructs duplicate tickets")
    memberships = Counter(label for ticket in portfolio for label in ticket)
    expected_profile = Counter({1: spec.singleton_label_count})
    for multiplicity, count in spec.repeated_support_counts:
        expected_profile[multiplicity] += count
    if len(memberships) != POOL_SIZE or Counter(memberships.values()) != expected_profile:
        raise ValueError("reconstructed labels changed the multiplicity profile")
    return portfolio


def _bonferroni_of_supports(supports: tuple[frozenset[int], ...]) -> int:
    """Exact third-order Bonferroni numerator for fixed-size ticket supports."""

    pair_joints = _pair_joint_counts()
    pair_total = 0
    for left, right in itertools.combinations(range(TICKET_COUNT), 2):
        shared = sum(1 for support in supports if left in support and right in support)
        if shared >= len(pair_joints):
            raise ValueError("ticket pair has more shared labels than its capacity")
        pair_total += pair_joints[shared]

    triple_total = 0
    for triple in itertools.combinations(range(TICKET_COUNT), 3):
        regions = _regions_for_triple(supports, triple)
        triple_total += _joint_count_from_regions(regions, 3, POOL_SIZE, DRAW_SIZE, 3)
    single_total = TICKET_COUNT * independent_single_outcome_count(PrizeEvent.OFFICIAL_ANY_PRIZE)
    return single_total - pair_total + triple_total


def bonferroni_u3(system: SupportSystem, spec: ProfileSpec) -> int:
    """Compute the exact U3 bound for one legal K10 support system."""

    if not is_legal_support_system(system, spec):
        raise ValueError(f"U3 requires one legal {spec.name} K10 support system")
    return _bonferroni_of_supports(_support_sets(system))


def compare_incumbent(max_legal_u3: int, incumbent: int = INCUMBENT_COUNT) -> str:
    return "CLOSED_BY_EXACT_U3" if max_legal_u3 <= incumbent else "SURVIVES_U3"


def canonical_support_key(
    system: SupportSystem,
) -> tuple[tuple[Support, ...], tuple[Support, ...]]:
    """Small-instance reference canonicalizer used only by the brute-force test."""

    best: tuple[tuple[Support, ...], tuple[Support, ...]] | None = None
    for permutation in itertools.permutations(range(system.vertex_count)):
        pairs = tuple(
            sorted(tuple(sorted(permutation[vertex] for vertex in s)) for s in system.pair_supports)
        )
        higher = tuple(
            sorted(
                tuple(sorted(permutation[vertex] for vertex in s)) for s in system.higher_supports
            )
        )
        if best is None or (pairs, higher) < best:
            best = (pairs, higher)
    if best is None:
        raise ValueError("canonicalization requires at least one vertex permutation")
    return best


# ---------------------------------------------------------------------------
# Profile census and result assembly.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProfileResult:
    spec: ProfileSpec
    pair_graph_class_count: int
    retained_pair_graph_class_count: int
    pair_graph_labeled_total: int
    structural_orbit_count: int
    burnside_orbit_count: int
    legal_class_count: int
    max_legal_u3: int
    status: str
    maximizing_systems: tuple[SupportSystem, ...]
    parity_probes: tuple[dict[str, object], ...]
    exact_scores: tuple[dict[str, object], ...]
    best_exact_count: int | None

    @property
    def gap(self) -> int:
        return self.max_legal_u3 - INCUMBENT_COUNT

    def as_record(self) -> dict[str, object]:
        return {
            "PROFILE": self.spec.profile,
            "PAIR_GRAPH_CLASS_COUNT": self.pair_graph_class_count,
            "RETAINED_PAIR_GRAPH_CLASS_COUNT": self.retained_pair_graph_class_count,
            "PAIR_GRAPH_LABELED_TOTAL": self.pair_graph_labeled_total,
            "STRUCTURAL_SUPPORT_ORBIT_COUNT": self.structural_orbit_count,
            "BURNSIDE_ORBIT_COUNT": self.burnside_orbit_count,
            "LEGAL_SUPPORT_CLASS_COUNT": self.legal_class_count,
            "MAX_LEGAL_U3": self.max_legal_u3,
            "INCUMBENT_COUNT": INCUMBENT_COUNT,
            "GAP_VS_INCUMBENT": self.gap,
            "PROFILE_STATUS": self.status,
            "MAXIMIZING_CLASS_COUNT": len(self.maximizing_systems),
            "MAXIMIZING_SUPPORT_WITNESSES": (
                [_witness_record(system) for system in self.maximizing_systems]
                if self.status == "SURVIVES_U3"
                else []
            ),
            "PARITY_PROBES": list(self.parity_probes),
            "EXACT_SCORES_RUN": len(self.exact_scores),
            "BEST_EXACT_COUNT": self.best_exact_count,
            "EXACT_SCORE_RESULTS": list(self.exact_scores),
        }


def _witness_record(system: SupportSystem) -> dict[str, object]:
    return {
        "class_id": system.class_id,
        "pair_supports": [list(support) for support in system.pair_supports],
        "higher_supports": [list(support) for support in system.higher_supports],
    }


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def build_profile_result(
    spec: ProfileSpec, *, progress: bool = False, verify_public_u3: bool = True
) -> ProfileResult:
    arithmetic = profile_arithmetic(spec)
    if (
        arithmetic["labels"] != POOL_SIZE
        or arithmetic["ticket_incidences"] != TICKET_COUNT * DRAW_SIZE
        or arithmetic["singleton_incidences"] != spec.singleton_label_count
    ):
        raise ValueError(f"frozen profile arithmetic changed: {arithmetic}")

    census = pair_graph_census(TICKET_COUNT, spec.pair_label_count)
    # A pair-degree above the draw size can only grow once higher supports are added,
    # so those graph classes carry no legal support system.
    retained = tuple(graph for graph in census.classes if graph.max_degree <= DRAW_SIZE)
    state_count = prod(
        comb(comb(TICKET_COUNT, support_size) + label_count - 1, label_count)
        for support_size, label_count in spec.higher_support_counts
    )

    structural_orbits = 0
    burnside_orbits = 0
    legal_classes = 0
    maximum = -1
    maximizing: list[SupportSystem] = []
    legal_probes: list[SupportSystem] = []
    for graph_index, graph in enumerate(retained, start=1):
        graph_orbits = 0
        graph_states = 0
        for system, orbit_size in _systems_for_profile_graph(graph, TICKET_COUNT, spec):
            graph_orbits += 1
            graph_states += orbit_size
            if not is_legal_support_system(system, spec):
                continue
            legal_classes += 1
            if verify_public_u3 and len(legal_probes) < 2:
                legal_probes.append(system)
            value = bonferroni_u3(system, spec)
            if value > maximum:
                maximum = value
                maximizing = [system]
            elif value == maximum:
                maximizing.append(system)
        graph_burnside = _burnside_orbit_count_for_counts(
            graph, TICKET_COUNT, spec.higher_support_counts
        )
        if graph_states != state_count or graph_orbits != graph_burnside:
            raise ValueError(
                f"{spec.name}: orbit census disagrees with Burnside "
                f"({graph_orbits} != {graph_burnside}) or loses states "
                f"({graph_states} != {state_count}) for graph {graph.edges}"
            )
        structural_orbits += graph_orbits
        burnside_orbits += graph_burnside
        if progress and (graph_index % PROGRESS_EVERY == 0 or graph_index == len(retained)):
            _log(
                f"{spec.name} pair_graph_classes={graph_index}/{len(retained)} "
                f"structural_orbits={structural_orbits} legal_classes={legal_classes} "
                f"current_max_u3={maximum}"
            )

    if legal_classes == 0 or not maximizing:
        raise ValueError(f"{spec.name}: legal support census was empty")
    maximizing.sort(key=lambda system: system.class_id)
    status = compare_incumbent(maximum)

    probes: list[dict[str, object]] = []
    if verify_public_u3:
        for system in dict.fromkeys((*legal_probes, maximizing[0])):
            computed = bonferroni_u3(system, spec)
            public = u3_outcome_count(reconstruct_portfolio(system, spec))
            if computed != public:
                raise ValueError(
                    f"{spec.name}: support U3 disagrees with public u3_outcome_count: "
                    f"{computed} != {public}"
                )
            probes.append(
                {
                    "class_id": system.class_id,
                    "support_u3": computed,
                    "public_u3_outcome_count": public,
                }
            )

    exact_scores: list[dict[str, object]] = []
    best_exact_count: int | None = None
    if status == "SURVIVES_U3" and len(maximizing) <= EXACT_SCORE_MAX_WITNESSES:
        draws = all_main_draw_masks(POOL_SIZE, DRAW_SIZE)
        for system in maximizing:
            score = evaluate_portfolio(
                reconstruct_portfolio(system, spec), draws=draws
            ).official_any_prize_outcome_count
            if score > maximum:
                raise ValueError("exact score exceeded its third-order Bonferroni upper bound")
            if best_exact_count is None or score > best_exact_count:
                best_exact_count = score
            exact_scores.append(
                {"class_id": system.class_id, "official_any_prize_outcome_count": score}
            )

    return ProfileResult(
        spec=spec,
        pair_graph_class_count=len(census.classes),
        retained_pair_graph_class_count=len(retained),
        pair_graph_labeled_total=census.labeled_total,
        structural_orbit_count=structural_orbits,
        burnside_orbit_count=burnside_orbits,
        legal_class_count=legal_classes,
        max_legal_u3=maximum,
        status=status,
        maximizing_systems=tuple(maximizing),
        parity_probes=tuple(probes),
        exact_scores=tuple(exact_scores),
        best_exact_count=best_exact_count,
    )


def _seal(result: dict[str, object]) -> dict[str, object]:
    digest_input = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sealed = dict(result)
    sealed["RESULT_SHA256"] = sha256(digest_input).hexdigest()
    return sealed


def build_mass14_result(*, progress: bool = False) -> dict[str, object]:
    results = {spec.name: build_profile_result(spec, progress=progress) for spec in MASS14_PROFILES}
    survivors = [name for name, outcome in results.items() if outcome.status == "SURVIVES_U3"]
    smallest = (
        min(survivors, key=lambda name: (results[name].legal_class_count, name))
        if survivors
        else None
    )
    coverage = [legacy_enumerator_coverage(edges) for edges in (5, 7, 8)]
    record: dict[str, object] = {name: outcome.as_record() for name, outcome in results.items()}
    record.update(
        {
            "MASS14_STATUS": "PARTIAL" if survivors else "CLOSED",
            "SMALLEST_SURVIVING_PROFILE": smallest,
            "K10_GLOBAL_OPTIMUM_STATUS": "UNKNOWN",
            "INCUMBENT_COUNT": INCUMBENT_COUNT,
            "UPSTREAM_ENUMERATOR_COVERAGE": coverage,
        }
    )
    return _seal(record)


def build_mass15_result(*, progress: bool = False) -> dict[str, object]:
    """Compute exact-U3 closure for the two full-support mass-15 profiles."""

    results = {spec.name: build_profile_result(spec, progress=progress) for spec in MASS15_PROFILES}
    survivors = [name for name, outcome in results.items() if outcome.status == "SURVIVES_U3"]
    smallest = (
        min(survivors, key=lambda name: (results[name].legal_class_count, name))
        if survivors
        else None
    )
    record: dict[str, object] = {name: outcome.as_record() for name, outcome in results.items()}
    record.update(
        {
            "MASS15_STATUS": "PARTIAL" if survivors else "CLOSED",
            "SMALLEST_SURVIVING_PROFILE": smallest,
            "K10_GLOBAL_OPTIMUM_STATUS": "UNKNOWN",
            "INCUMBENT_COUNT": INCUMBENT_COUNT,
        }
    )
    return _seal(record)


def build_mass16_result(*, progress: bool = False) -> dict[str, object]:
    """Derive every full-support mass-16 profile and compute its exact U3 census."""

    profiles = derive_mass16_profiles()
    specs = _mass16_profile_specs(profiles)
    _log(f"MASS16_PROFILE_COUNT={len(profiles)} PROFILES={profiles}")
    results = {spec.name: build_profile_result(spec, progress=progress) for spec in specs}
    survivors = [name for name, outcome in results.items() if outcome.status == "SURVIVES_U3"]
    smallest = (
        min(survivors, key=lambda name: (results[name].legal_class_count, name))
        if survivors
        else None
    )
    record: dict[str, object] = {name: outcome.as_record() for name, outcome in results.items()}
    record.update(
        {
            "MASS16_PROFILE_COUNT": len(profiles),
            "MASS16_STATUS": "PARTIAL" if survivors else "CLOSED",
            "SMALLEST_SURVIVING_PROFILE": smallest,
            "K10_GLOBAL_OPTIMUM_STATUS": "UNKNOWN",
            "INCUMBENT_COUNT": INCUMBENT_COUNT,
        }
    )
    return _seal(record)


def build_mass17_result(*, progress: bool = False) -> dict[str, object]:
    """Freeze all full-support mass-17 profiles, then run exact-U3 closure."""

    profiles = derive_mass17_profiles()
    if profiles != FROZEN_MASS17_PROFILES:
        raise ValueError(
            "derived mass-17 profiles differ from the frozen Phase 0 list: "
            f"{profiles} != {FROZEN_MASS17_PROFILES}"
        )
    _log(f"MASS17_PROFILE_COUNT={len(profiles)} FROZEN_PROFILES={profiles}")
    specs = _mass17_profile_specs(profiles)
    results = {spec.name: build_profile_result(spec, progress=progress) for spec in specs}
    survivors = [name for name, outcome in results.items() if outcome.status == "SURVIVES_U3"]
    smallest = (
        min(survivors, key=lambda name: (results[name].legal_class_count, name))
        if survivors
        else None
    )
    record: dict[str, object] = {name: outcome.as_record() for name, outcome in results.items()}
    record.update(
        {
            "MASS17_PROFILE_COUNT": len(profiles),
            "MASS17_STATUS": "PARTIAL" if survivors else "CLOSED",
            "SMALLEST_SURVIVING_PROFILE": smallest,
            "K10_GLOBAL_OPTIMUM_STATUS": "UNKNOWN",
            "INCUMBENT_COUNT": INCUMBENT_COUNT,
        }
    )
    return _seal(record)


def build_mass13_recheck_result(*, progress: bool = False) -> dict[str, object]:
    """Diagnostic only: re-census the mass-13 profile with the complete pair enumerator."""

    outcome = build_profile_result(PROFILE_MASS13, progress=progress)
    return _seal(
        {
            "MASS13_RECHECK": outcome.as_record(),
            "UPSTREAM_RECORDED": {
                "LEGAL_SUPPORT_CLASS_COUNT": 426_948,
                "MAX_LEGAL_U3": 175_456_512,
                "PAIR_MULTIGRAPH_CLASS_COUNT": 554,
                "PROFILE_STATUS": "CLOSED_BY_EXACT_U3",
            },
            "K10_GLOBAL_OPTIMUM_STATUS": "UNKNOWN",
        }
    )


def main(argv: Sequence[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    mode = arguments[0] if arguments else "mass14"
    if mode == "mass14":
        result = build_mass14_result(progress=True)
    elif mode == "mass15":
        result = build_mass15_result(progress=True)
    elif mode == "mass16":
        result = build_mass16_result(progress=True)
    elif mode == "mass17":
        result = build_mass17_result(progress=True)
    elif mode == "mass13-recheck":
        result = build_mass13_recheck_result(progress=True)
    else:
        raise SystemExit(f"unknown mode: {mode}")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
