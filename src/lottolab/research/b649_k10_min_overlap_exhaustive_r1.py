"""Exhaustive K=10 minimum pairwise-overlap portfolios for BIG_LOTTO.

The overlap mass is ``sum_n C(r_n, 2)``. Scoring of a stored portfolio uses
``b649_official_any_prize_exact.evaluate_portfolio`` and nothing else.

``RECORD_PATH`` is the compact mass-11/mass-12 proof certificate. The full
enumeration artifacts stay in donor commit ``1ad73707`` and are located there
by path, git blob and SHA-256.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections import Counter
from collections.abc import Iterable
from math import comb
from pathlib import Path
from typing import cast

from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

POOL_SIZE = 49
DRAW_SIZE = 6
TICKET_COUNT = 10
EDGE_COUNT = 11
MAX_DEGREE = DRAW_SIZE
BASELINE_FRACTION = (536005, 1827672)
RECORD_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs/research/matrix-native-results/b649-k10-overlap-mass11-mass12-proof-certificate-r1.json"
)

Edge = tuple[int, int, int]


def minimum_overlap_derivation(
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    ticket_count: int = TICKET_COUNT,
) -> dict[str, object]:
    """Independent dynamic program for ``min sum C(r_n, 2)``.

    Incidences are placed one pool label at a time. ``C(r, 2)`` is strictly
    convex, and the recurrence tries every legal frequency, so the returned
    cost is the minimum. The histogram is recovered from the predecessor of
    one optimal placement; ``profile_unique`` checks that every other
    placement of the same cost has the same histogram.
    """

    slots = draw_size * ticket_count
    if slots < 0 or pool_size < 0 or ticket_count < 1:
        raise ValueError("invalid overlap parameters")
    infinite = slots * slots + 1
    cost = [[infinite] * (slots + 1) for _ in range(pool_size + 1)]
    choice = [[-1] * (slots + 1) for _ in range(pool_size + 1)]
    cost[0][0] = 0
    for label in range(pool_size):
        for used in range(slots + 1):
            if cost[label][used] >= infinite:
                continue
            for frequency in range(min(ticket_count, slots - used) + 1):
                updated = cost[label][used] + comb(frequency, 2)
                nxt = used + frequency
                if updated < cost[label + 1][nxt]:
                    cost[label + 1][nxt] = updated
                    choice[label + 1][nxt] = frequency
    minimum = cost[pool_size][slots]
    if minimum >= infinite:
        raise ValueError("no frequency placement exists")
    histogram: Counter[int] = Counter()
    used = slots
    for label in range(pool_size, 0, -1):
        frequency = choice[label][used]
        histogram[frequency] += 1
        used -= frequency
    profile_unique = _optimal_profile_is_unique(
        pool_size=pool_size,
        ticket_count=ticket_count,
        slots=slots,
        minimum=minimum,
        histogram=histogram,
    )
    return {
        "minimum_mass": minimum,
        "histogram": {str(frequency): histogram[frequency] for frequency in sorted(histogram)},
        "profile_unique": profile_unique,
        "slots": slots,
        "pool_size": pool_size,
    }


def _optimal_profile_is_unique(
    *,
    pool_size: int,
    ticket_count: int,
    slots: int,
    minimum: int,
    histogram: Counter[int],
) -> bool:
    """Every optimal placement has the same frequency histogram.

    A second recurrence keeps the set of histograms that achieve the minimum
    cost at the full slot count. Histograms are count-vectors of frequencies
    ``0..ticket_count``, which stay small because only minimum-cost states
    are retained.
    """

    empty = (0,) * (ticket_count + 1)
    best: list[dict[int, dict[tuple[int, ...], int]]] = [{} for _ in range(pool_size + 1)]
    best[0][0] = {empty: 0}
    for label in range(pool_size):
        layer: dict[int, dict[tuple[int, ...], int]] = {}
        for used, profiles in best[label].items():
            for profile, profile_cost in profiles.items():
                if profile_cost > minimum:
                    continue
                for frequency in range(min(ticket_count, slots - used) + 1):
                    updated = profile_cost + comb(frequency, 2)
                    if updated > minimum:
                        continue
                    nxt = list(profile)
                    nxt[frequency] += 1
                    key = tuple(nxt)
                    bucket = layer.setdefault(used + frequency, {})
                    previous = bucket.get(key)
                    if previous is None or updated < previous:
                        bucket[key] = updated
        best[label + 1] = layer
    finals = {
        profile
        for profile, profile_cost in best[pool_size].get(slots, {}).items()
        if profile_cost == minimum
    }
    expected = [0] * (ticket_count + 1)
    for frequency, count in histogram.items():
        expected[frequency] = count
    return finals == {tuple(expected)}


def assert_k10_minimum_profile() -> dict[str, object]:
    """The K=10 B649 minimum is mass 11, with 38 singles and 11 doubles."""

    derived = minimum_overlap_derivation()
    histogram = cast(dict[str, int], derived["histogram"])
    if (
        derived["minimum_mass"] != EDGE_COUNT
        or histogram.get("1") != 38
        or histogram.get("2") != 11
        or any(frequency not in {"1", "2"} for frequency in histogram)
    ):
        raise ValueError(f"corrected minimum-overlap profile: {derived}")
    if derived["profile_unique"] is not True:
        raise ValueError(f"minimum profile is not unique: {derived}")
    return derived


def parse_multig_line(line: str) -> tuple[int | None, tuple[Edge, ...]]:
    """Parse one ``multig -G`` or ``-T`` line into sorted ``(u, v, multiplicity)``."""

    parts = [int(token) for token in line.split()]
    if len(parts) < 2:
        raise ValueError(f"short multig line: {line!r}")
    vertex_count, edge_count = parts[0], parts[1]
    rest = parts[2:]
    group_size: int | None = None
    if len(rest) == 3 * edge_count + 1:
        group_size = rest[0]
        rest = rest[1:]
    elif len(rest) != 3 * edge_count:
        raise ValueError(f"cannot parse multig line: {line!r}")
    edges: list[Edge] = []
    for index in range(edge_count):
        left, right, multiplicity = rest[3 * index : 3 * index + 3]
        if left == right or multiplicity < 1:
            raise ValueError(f"loop or empty edge in {line!r}")
        if left > right:
            left, right = right, left
        edges.append((left, right, multiplicity))
    edges.sort()
    if len(edges) != len(set(edges)):
        raise ValueError(f"duplicate pair in {line!r}")
    if vertex_count < 0:
        raise ValueError(line)
    return group_size, tuple(edges)


def canonical_class_id(vertex_count: int, edges: tuple[Edge, ...], group_size: int | None) -> str:
    """Stable identity of one multig representative."""

    body = " ".join(f"{left} {right} {multiplicity}" for left, right, multiplicity in edges)
    group = "" if group_size is None else f" {group_size}"
    return f"{vertex_count} {len(edges)}{group} {body}".strip()


def class_set_sha256(class_ids: Iterable[str]) -> str:
    payload = "\n".join(sorted(class_ids)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def degrees_of(vertex_count: int, edges: tuple[Edge, ...]) -> tuple[int, ...]:
    degree = [0] * vertex_count
    for left, right, multiplicity in edges:
        degree[left] += multiplicity
        degree[right] += multiplicity
    return tuple(degree)


def graph_is_admissible(
    edges: tuple[Edge, ...],
    *,
    vertex_count: int = TICKET_COUNT,
    edge_count: int = EDGE_COUNT,
    max_degree: int = MAX_DEGREE,
) -> bool:
    if sum(multiplicity for _, _, multiplicity in edges) != edge_count:
        return False
    if any(
        left < 0 or right >= vertex_count or multiplicity < 1 for left, right, multiplicity in edges
    ):
        return False
    if any(left == right for left, right, _ in edges):
        return False
    return all(degree <= max_degree for degree in degrees_of(vertex_count, edges))


def portfolio_from_edges(
    edges: tuple[Edge, ...],
    *,
    vertex_count: int = TICKET_COUNT,
    draw_size: int = DRAW_SIZE,
) -> tuple[tuple[int, ...], ...]:
    """Deterministic tickets: one fresh number per multiedge end, then singletons.

    Vertices are tickets ``0..vertex_count-1``. Edge ``(u, v, m)`` contributes
    ``m`` distinct numbers shared by those two tickets. Remaining slots are
    private numbers, assigned in ticket order.
    """

    degree = list(degrees_of(vertex_count, edges))
    if any(item > draw_size for item in degree):
        raise ValueError("degree exceeds ticket size")
    tickets: list[list[int]] = [[] for _ in range(vertex_count)]
    number = 1
    for left, right, multiplicity in edges:
        for _ in range(multiplicity):
            tickets[left].append(number)
            tickets[right].append(number)
            number += 1
    for vertex, used in enumerate(degree):
        for _ in range(draw_size - used):
            tickets[vertex].append(number)
            number += 1
    portfolio = tuple(tuple(sorted(ticket)) for ticket in tickets)
    if len(set(portfolio)) != vertex_count:
        raise ValueError("reconstruction produced a duplicate ticket")
    return portfolio


def produces_duplicate_ticket(edges: tuple[Edge, ...], *, vertex_count: int = TICKET_COUNT) -> bool:
    """Two degree-6 tickets joined by multiplicity 6 are the same six numbers.

    Every number has frequency at most 2, so this is the only way two tickets
    can contain the same set.
    """

    degree = degrees_of(vertex_count, edges)
    return any(
        multiplicity == DRAW_SIZE and degree[left] == DRAW_SIZE and degree[right] == DRAW_SIZE
        for left, right, multiplicity in edges
    )


def canonical_portfolio_sha256(portfolio: tuple[tuple[int, ...], ...]) -> str:
    payload = json.dumps([list(ticket) for ticket in portfolio], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def relabel_numbers(
    portfolio: tuple[tuple[int, ...], ...],
    permutation: dict[int, int],
) -> tuple[tuple[int, ...], ...]:
    relabeled = tuple(
        tuple(sorted(permutation[number] for number in ticket)) for ticket in portfolio
    )
    return tuple(sorted(relabeled))


def permute_tickets(
    portfolio: tuple[tuple[int, ...], ...],
    order: tuple[int, ...],
) -> tuple[tuple[int, ...], ...]:
    return tuple(sorted(portfolio[index] for index in order))


def pair_intersection_histogram(portfolio: tuple[tuple[int, ...], ...]) -> dict[str, int]:
    counts: Counter[int] = Counter(
        len(set(left).intersection(right)) for left, right in itertools.combinations(portfolio, 2)
    )
    return {str(size): counts[size] for size in sorted(counts)}


def overlap_mass(portfolio: tuple[tuple[int, ...], ...]) -> int:
    return sum(
        len(set(left).intersection(right)) for left, right in itertools.combinations(portfolio, 2)
    )


def number_frequency(portfolio: tuple[tuple[int, ...], ...]) -> dict[str, int]:
    used = Counter(number for ticket in portfolio for number in ticket)
    histogram = Counter(used.values())
    unused = POOL_SIZE - len(used)
    if unused:
        histogram[0] += unused
    return {str(frequency): histogram[frequency] for frequency in sorted(histogram)}


def structure_of_edges(
    edges: tuple[Edge, ...], *, vertex_count: int = TICKET_COUNT
) -> dict[str, object]:
    """Higher-order invariants of one minimum-overlap multigraph."""

    degree = degrees_of(vertex_count, edges)
    multiplicity = Counter(item for _, _, item in edges)
    simple = {(left, right) for left, right, _ in edges}
    triangles = 0
    for first, second, third in itertools.combinations(range(vertex_count), 3):
        pairs = ((first, second), (first, third), (second, third))
        if all(tuple(sorted(pair)) in simple for pair in pairs):
            triangles += 1
    parallel_mass = sum(item - 1 for _, _, item in edges)
    return {
        "degree_sequence": list(sorted(degree, reverse=True)),
        "parallel_multiplicity_profile": {
            str(item): multiplicity[item] for item in sorted(multiplicity)
        },
        "parallel_extra_edges": parallel_mass,
        "underlying_triangles": triangles,
        "isolated_vertices": sum(1 for item in degree if item == 0),
    }


def edges_from_portfolio(portfolio: tuple[tuple[int, ...], ...]) -> tuple[Edge, ...]:
    edges: list[Edge] = []
    for left, right in itertools.combinations(range(len(portfolio)), 2):
        multiplicity = len(set(portfolio[left]).intersection(portfolio[right]))
        if multiplicity:
            edges.append((left, right, multiplicity))
    return tuple(edges)


def enumerate_small_multigraphs(
    vertex_count: int,
    edge_count: int,
    max_degree: int,
) -> tuple[str, ...]:
    """Independent generator for tests. Canonical form is the minimum edge list.

    Vertices are indistinguishable. Every loopless multiplicity matrix with
    total multiplicity ``edge_count`` and degree at most ``max_degree`` is
    reduced by trying every vertex permutation. Intended for ``n <= 6``.
    """

    if vertex_count > 6:
        raise ValueError("brute-force canonicalization is only for n<=6")
    pair_index = list(itertools.combinations(range(vertex_count), 2))
    found: set[str] = set()

    def walk(pair_at: int, remaining: int, degree: list[int], chosen: list[Edge]) -> None:
        if remaining == 0:
            found.add(_canonical_edge_string(vertex_count, tuple(chosen)))
            return
        if pair_at == len(pair_index):
            return
        left, right = pair_index[pair_at]
        walk(pair_at + 1, remaining, degree, chosen)
        room = min(remaining, max_degree - degree[left], max_degree - degree[right])
        for multiplicity in range(1, room + 1):
            degree[left] += multiplicity
            degree[right] += multiplicity
            chosen.append((left, right, multiplicity))
            walk(pair_at + 1, remaining - multiplicity, degree, chosen)
            chosen.pop()
            degree[left] -= multiplicity
            degree[right] -= multiplicity

    walk(0, edge_count, [0] * vertex_count, [])
    return tuple(sorted(found))


def _canonical_edge_string(vertex_count: int, edges: tuple[Edge, ...]) -> str:
    best: str | None = None
    for order in itertools.permutations(range(vertex_count)):
        rank = {vertex: index for index, vertex in enumerate(order)}
        mapped: list[Edge] = []
        for left, right, multiplicity in edges:
            a, b = rank[left], rank[right]
            if a > b:
                a, b = b, a
            mapped.append((a, b, multiplicity))
        mapped.sort()
        text = " ".join(f"{a} {b} {multiplicity}" for a, b, multiplicity in mapped)
        if best is None or text < best:
            best = text
    if best is None:
        raise ValueError("empty permutation")
    return best


def score_portfolio(portfolio: tuple[tuple[int, ...], ...]):
    """Canonical exact OFFICIAL_ANY_PRIZE. This is the only scoring entry point."""

    return evaluate_portfolio(portfolio)


def comparison_label(numerator: int, denominator: int) -> str:
    baseline_numerator, baseline_denominator = BASELINE_FRACTION
    left = numerator * baseline_denominator
    right = baseline_numerator * denominator
    if left > right:
        return "STRICT_IMPROVEMENT"
    if left == right:
        return "TIE"
    return "NO_IMPROVEMENT"


def load_record() -> dict[str, object]:
    return json.loads(RECORD_PATH.read_text(encoding="utf-8"))


__all__ = [
    "BASELINE_FRACTION",
    "EDGE_COUNT",
    "RECORD_PATH",
    "assert_k10_minimum_profile",
    "canonical_class_id",
    "canonical_portfolio_sha256",
    "class_set_sha256",
    "comparison_label",
    "edges_from_portfolio",
    "enumerate_small_multigraphs",
    "graph_is_admissible",
    "load_record",
    "minimum_overlap_derivation",
    "number_frequency",
    "overlap_mass",
    "pair_intersection_histogram",
    "parse_multig_line",
    "permute_tickets",
    "portfolio_from_edges",
    "relabel_numbers",
    "score_portfolio",
    "structure_of_edges",
]
