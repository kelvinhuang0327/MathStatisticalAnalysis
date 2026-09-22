"""Fixed-K probes for BIG_LOTTO OFFICIAL_ANY_PRIZE.

Probability claims in this package are fractions from
``b649_official_any_prize_exact.evaluate_portfolio``. Constructors only build
tickets. The shipped JSON is the inventory, discovery record, and stored
portfolios; ``render_handoff`` reads that record and does not keep a second
copy of the fractions.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any

from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

POOL_SIZE = 49
DRAW_SIZE = 6
SPECIAL_COUNT = POOL_SIZE - DRAW_SIZE
MAIN_DRAW_COUNT = comb(POOL_SIZE, DRAW_SIZE)
OUTCOME_COUNT = MAIN_DRAW_COUNT * SPECIAL_COUNT
TICKET_SLOTS = DRAW_SIZE

BASELINE_FRACTIONS: dict[int, tuple[int, int]] = {
    5: (547495, 3579191),
    10: (536005, 1827672),
    20: (22345625, 42950292),
}

RECORD_PATH = Path(__file__).with_name("b649_success_rate_frontier_r1.json")

FAMILY_STATUS = frozenset({"DONE", "PARTIAL", "NOT_FOUND", "EXHAUSTED", "WORTH_EXTENDING"})
NOVELTY_STATUS = frozenset(
    {"NEW", "STRONGER_VARIANT", "ALREADY_DONE", "SEMANTIC_DUPLICATE", "INCOMPATIBLE"}
)
COMPARISON_LABELS = frozenset({"STRICT_IMPROVEMENT", "TIE", "NO_IMPROVEMENT"})


def load_frontier_record() -> dict[str, Any]:
    """Load the shipped inventory, taxonomy, methods, and portfolios."""

    return json.loads(RECORD_PATH.read_text(encoding="utf-8"))


def canonical_portfolio_sha256(tickets: tuple[tuple[int, ...], ...] | list[list[int]]) -> str:
    """SHA-256 of the compact JSON list of lists, matching the sealed identity."""

    payload = json.dumps(
        [list(ticket) for ticket in tickets],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canon(tickets: list[tuple[int, ...]]) -> tuple[tuple[int, ...], ...]:
    """Sort each ticket and the portfolio. Reject illegal or duplicate tickets."""

    canonical = tuple(tuple(sorted(int(number) for number in ticket)) for ticket in tickets)
    for ticket in canonical:
        if len(ticket) != DRAW_SIZE or len(set(ticket)) != DRAW_SIZE:
            raise ValueError(f"illegal ticket: {ticket}")
        if any(number < 1 or number > POOL_SIZE for number in ticket):
            raise ValueError(f"illegal ticket: {ticket}")
    if len(set(canonical)) != len(canonical):
        raise ValueError("duplicate ticket")
    return tuple(sorted(canonical))


def intersection_histogram(portfolio: tuple[tuple[int, ...], ...]) -> dict[str, int]:
    counts: Counter[int] = Counter(
        len(set(left).intersection(right)) for left, right in combinations(portfolio, 2)
    )
    return {str(size): counts[size] for size in sorted(counts)}


def number_frequency(portfolio: tuple[tuple[int, ...], ...]) -> dict[str, int]:
    used: Counter[int] = Counter(number for ticket in portfolio for number in ticket)
    histogram: Counter[int] = Counter(used.values())
    unused = POOL_SIZE - len(used)
    if unused:
        histogram[0] += unused
    return {str(frequency): histogram[frequency] for frequency in sorted(histogram)}


def triple_structure(portfolio: tuple[tuple[int, ...], ...]) -> dict[str, int]:
    """Counts that pairwise overlap does not determine.

    ``numbers_in_exactly_3_tickets`` is a triple point. ``edge_triangles`` counts
    three tickets whose three pairwise shared numbers are three distinct doubles.
    """

    membership: dict[int, list[int]] = {}
    for index, ticket in enumerate(portfolio):
        for number in ticket:
            membership.setdefault(number, []).append(index)
    triple_numbers = sum(1 for tickets in membership.values() if len(tickets) == 3)
    pair_edges = {(tickets[0], tickets[1]) for tickets in membership.values() if len(tickets) == 2}
    triangles = 0
    for first, second, third in combinations(range(len(portfolio)), 3):
        pairs = ((first, second), (first, third), (second, third))
        if all(pair in pair_edges for pair in pairs):
            triangles += 1
    return {
        "numbers_in_exactly_3_tickets": triple_numbers,
        "edge_triangles": triangles,
    }


def pair_incidence(portfolio: tuple[tuple[int, ...], ...]) -> int:
    """Sum of pairwise intersection sizes. Equals ``sum_v C(r_v, 2)``."""

    return sum(len(set(left).intersection(right)) for left, right in combinations(portfolio, 2))


def minimum_pair_incidence(k: int) -> int:
    """Minimum of ``sum t_ij`` over k legal 6-subsets of a 49-set.

    ``C(r, 2)`` is strictly convex, so ``sum C(r_v, 2)`` is minimized when the
    multiplicities differ by at most one and as many numbers as possible are
    used. That integer program is what this function solves. It is a lower
    bound even when the minimum is not realizable.
    """

    if k < 1:
        raise ValueError("k must be positive")
    slots = TICKET_SLOTS * k
    if slots <= POOL_SIZE:
        return 0
    remaining = slots - POOL_SIZE
    base, extra = divmod(remaining, POOL_SIZE)
    low = 1 + base
    high = low + 1

    def choose_two(multiplicity: int) -> int:
        return multiplicity * (multiplicity - 1) // 2

    return (POOL_SIZE - extra) * choose_two(low) + extra * choose_two(high)


def _group_outcome_count(groups: list[tuple[int, int]]) -> int:
    """Exact winning-outcome count for numbers grouped by ticket membership.

    ``groups`` is a partition of ``1..49`` into ``(size, membership_mask)``.
    A ticket wins on every special when it takes at least 3 of the draw, and
    otherwise the rescued specials are the undrawn numbers that still belong
    to a ticket with exactly two hits.
    """

    if sum(size for size, _mask in groups) != POOL_SIZE:
        raise ValueError("groups must partition the pool")
    ticket_count = 0
    for _size, mask in groups:
        if mask:
            ticket_count = max(ticket_count, mask.bit_length())
    ways = 0
    winning = 0
    takes: list[int] = []

    def walk(index: int, remaining: int, hits: tuple[int, ...]) -> None:
        nonlocal ways, winning
        if index == len(groups):
            if remaining != 0:
                return
            multiplier = 1
            for (size, _mask), take in zip(groups, takes, strict=True):
                multiplier *= comb(size, take)
            ways += multiplier
            if any(hit >= 3 for hit in hits):
                winning += multiplier * SPECIAL_COUNT
                return
            rescue_mask = 0
            for ticket_index, hit in enumerate(hits):
                if hit == 2:
                    rescue_mask |= 1 << ticket_index
            if rescue_mask == 0:
                return
            rescued = 0
            for (size, mask), take in zip(groups, takes, strict=True):
                if mask & rescue_mask:
                    rescued += size - take
            winning += multiplier * rescued
            return
        size, mask = groups[index]
        for take in range(min(size, remaining) + 1):
            takes.append(take)
            if mask == 0:
                walk(index + 1, remaining - take, hits)
            else:
                updated = list(hits)
                bit = mask
                while bit:
                    low_bit = bit & -bit
                    updated[low_bit.bit_length() - 1] += take
                    bit ^= low_bit
                walk(index + 1, remaining - take, tuple(updated))
            takes.pop()

    walk(0, DRAW_SIZE, tuple(0 for _ in range(ticket_count)))
    if ways != MAIN_DRAW_COUNT:
        raise AssertionError("group enumeration missed part of the main-draw space")
    return winning


def two_ticket_union_outcomes(intersection: int) -> int:
    """Exact OFFICIAL_ANY_PRIZE outcome count of two tickets intersecting in ``intersection``."""

    if not 0 <= intersection <= DRAW_SIZE:
        raise ValueError("intersection must be in 0..6")
    only = DRAW_SIZE - intersection
    outside = POOL_SIZE - only - only - intersection
    groups = [
        (intersection, 0b11),
        (only, 0b01),
        (only, 0b10),
        (outside, 0b00),
    ]
    return _group_outcome_count([(size, mask) for size, mask in groups if size])


def pairwise_winning_intersections() -> dict[int, int]:
    """``|W_a ∩ W_b|`` by intersection size, from the two-ticket union identity."""

    single = two_ticket_union_outcomes(DRAW_SIZE)
    return {
        intersection: 2 * single - two_ticket_union_outcomes(intersection)
        for intersection in range(DRAW_SIZE + 1)
    }


def chord_inequality_holds(intersections: dict[int, int]) -> bool:
    """``I(t) >= I(0) + t (I(1)-I(0))`` for every intersection size.

    The right-hand side is the value of spreading ``t`` distinct size-1
    intersections. When it holds, every portfolio's pairwise term ``S2`` is at
    least the term of a design whose intersection sizes are only 0 and 1 and
    whose total incidence equals ``minimum_pair_incidence``.
    """

    slope = intersections[1] - intersections[0]
    return all(
        intersections[intersection] >= intersections[0] + intersection * slope
        for intersection in range(DRAW_SIZE + 1)
    )


def s2_lower_bound(k: int, intersections: dict[int, int]) -> int:
    """Minimum pairwise inclusion-exclusion subtraction for k tickets."""

    if not chord_inequality_holds(intersections):
        raise ValueError("chord inequality failed; S2 lower bound is not valid")
    pair_count = comb(k, 2)
    slope = intersections[1] - intersections[0]
    return pair_count * intersections[0] + slope * minimum_pair_incidence(k)


def disjoint_packing(k: int) -> tuple[tuple[int, ...], ...]:
    """k pairwise disjoint tickets. Realizable only for ``k <= 8``."""

    if not 1 <= k <= POOL_SIZE // DRAW_SIZE:
        raise ValueError("disjoint packing does not fit")
    return canon(
        [tuple(range(index * DRAW_SIZE + 1, (index + 1) * DRAW_SIZE + 1)) for index in range(k)]
    )


def affine_plane_lines() -> list[tuple[int, ...]]:
    """Lines of the affine plane AG(2,7): 56 subsets of 7 points labeled 1..49."""

    def label(x_coord: int, y_coord: int) -> int:
        return 1 + x_coord + 7 * y_coord

    lines: list[tuple[int, ...]] = []
    for slope in range(7):
        for intercept in range(7):
            lines.append(
                tuple(label((slope * x_coord + intercept) % 7, x_coord) for x_coord in range(7))
            )
    for column in range(7):
        lines.append(tuple(label(column, y_coord) for y_coord in range(7)))
    return lines


def affine_shortened_portfolio(k: int) -> tuple[tuple[int, ...], ...]:
    """First k lines of AG(2,7), each shortened by deleting its smallest point.

    Parallel classes have 7 lines. k=10 is one class plus three lines of the
    next class. k=20 continues into a third class. Deleting one point makes a
    legal 6-number ticket; it does not preserve every geometric intersection.
    """

    if k not in {10, 20}:
        raise ValueError("affine prototype is defined for k=10 and k=20")
    shortened: list[tuple[int, ...]] = []
    for line in affine_plane_lines()[:k]:
        ordered = tuple(sorted(line))
        shortened.append(ordered[1:])
    return canon(shortened)


def triangle_free_k10() -> tuple[tuple[int, ...], ...]:
    """11-edge triangle-free intersection graph on 10 vertices: C10 plus one chord.

    Eleven is ``minimum_pair_incidence(10)``. The chord joins vertices at
    distance 4, so it creates no triangle. Each edge is one shared number.
    """

    edges = [(index, (index + 1) % 10) for index in range(10)]
    edges.append((0, 4))
    return portfolio_from_simple_edges(edges, 10)


def portfolio_from_simple_edges(
    edges: list[tuple[int, int]],
    k: int,
) -> tuple[tuple[int, ...], ...]:
    """Each edge contributes one number shared by exactly those two tickets."""

    degree = [0] * k
    seen: set[tuple[int, int]] = set()
    for left, right in edges:
        pair = tuple(sorted((left, right)))
        if len(pair) != 2 or pair in seen or not 0 <= pair[0] < k:
            raise ValueError("edges must be a simple graph")
        seen.add(pair)
        degree[pair[0]] += 1
        degree[pair[1]] += 1
    if any(item > DRAW_SIZE for item in degree):
        raise ValueError("degree exceeds ticket size")
    numbers_needed = len(seen) + sum(DRAW_SIZE - item for item in degree)
    if numbers_needed > POOL_SIZE:
        raise ValueError("design does not fit in the pool")
    tickets: list[set[int]] = [set() for _ in range(k)]
    number = 1
    for left, right in sorted(seen):
        tickets[left].add(number)
        tickets[right].add(number)
        number += 1
    for index, private_slots in enumerate(DRAW_SIZE - item for item in degree):
        for _ in range(private_slots):
            tickets[index].add(number)
            number += 1
    return canon([tuple(sorted(ticket)) for ticket in tickets])


def one_number_exchange(
    portfolio: tuple[tuple[int, ...], ...],
    ticket_index: int,
    drop: int,
    add: int,
) -> tuple[tuple[int, ...], ...]:
    """Replace one number on one ticket. The pairwise cap is not enforced."""

    ticket = portfolio[ticket_index]
    if drop not in ticket or add in ticket:
        raise ValueError("exchange does not apply to this ticket")
    if not 1 <= add <= POOL_SIZE:
        raise ValueError("replacement is outside the pool")
    replaced = tuple(sorted(add if number == drop else number for number in ticket))
    updated = list(portfolio)
    updated[ticket_index] = replaced
    return canon(updated)


def random_minimum_s2_k10(rng: random.Random) -> tuple[tuple[int, ...], ...] | None:
    """One uniform attempt at an 11-edge simple graph with degrees at most 6."""

    edges: set[tuple[int, int]] = set()
    while len(edges) < 11:
        left, right = rng.sample(range(10), 2)
        edges.add((min(left, right), max(left, right)))
    try:
        portfolio = portfolio_from_simple_edges(list(edges), 10)
    except ValueError:
        return None
    histogram = intersection_histogram(portfolio)
    if histogram.get("1") == 11 and max(int(key) for key in histogram) <= 1:
        return portfolio
    return None


def random_minimum_s2_k20(rng: random.Random) -> tuple[tuple[int, ...], ...] | None:
    """One attempt at 22 triple points and 27 double points, every degree 6."""

    degree = [0] * 20
    used: set[tuple[int, int]] = set()
    triples: list[tuple[int, ...]] = []
    pairs: list[tuple[int, ...]] = []

    def place(width: int) -> tuple[int, ...] | None:
        order = sorted(range(20), key=lambda index: (degree[index], rng.random()))
        available = [index for index in order if degree[index] < DRAW_SIZE]
        for group in combinations(available[:14], width):
            ordered = tuple(sorted(group))
            group_pairs = list(combinations(ordered, 2))
            if any(pair in used for pair in group_pairs):
                continue
            return ordered
        return None

    for _ in range(22):
        group = place(3)
        if group is None:
            return None
        triples.append(group)
        for pair in combinations(group, 2):
            used.add(pair)
        for index in group:
            degree[index] += 1
    for _ in range(27):
        group = place(2)
        if group is None:
            return None
        pairs.append(group)
        used.add(group)
        for index in group:
            degree[index] += 1
    if degree != [DRAW_SIZE] * 20:
        return None
    tickets: list[set[int]] = [set() for _ in range(20)]
    number = 1
    for group in triples + pairs:
        for index in group:
            tickets[index].add(number)
        number += 1
    if number != POOL_SIZE + 1:
        return None
    return canon([tuple(sorted(ticket)) for ticket in tickets])


def comparison_label(numerator: int, denominator: int, k: int) -> str:
    """Exact comparison with the locked same-k baseline. No rounding."""

    baseline_numerator, baseline_denominator = BASELINE_FRACTIONS[k]
    left = numerator * baseline_denominator
    right = baseline_numerator * denominator
    if left > right:
        return "STRICT_IMPROVEMENT"
    if left == right:
        return "TIE"
    return "NO_IMPROVEMENT"


def score_portfolio(portfolio: tuple[tuple[int, ...], ...]) -> Any:
    """Canonical exact evaluation. This is the only probability entry point."""

    return evaluate_portfolio(portfolio)


def render_handoff(record: dict[str, Any] | None = None) -> str:
    """Nine-part handoff rendered only from the shipped record."""

    payload = load_frontier_record() if record is None else record
    lines: list[str] = []
    lines.append("1. CURRENT BEST BASELINE")
    for row in payload["baselines"]:
        lines.append(
            f"K{row['k']} {row['official_any_prize']} sha256={row['portfolio_sha256']} "
            f"source={row['source']} pair_incidence={row['pair_incidence']} "
            f"minimum_pair_incidence={row['minimum_pair_incidence']} "
            f"remainder_above_pairwise_floor={row['remainder_above_floor']} "
            f"number_frequency={row['number_frequency']} "
            f"triple_structure={row['triple_structure']}"
        )
    lines.append(
        "The chord bound says every portfolio's pairwise term is at least the "
        "term of these histograms. K5's union equals that pairwise floor "
        "(remainder 0). K10 sits 210525 outcomes above its floor and K20 sits "
        "4448710 outcomes above its floor. A portfolio with a heavier pairwise "
        "term beats the baseline only if its higher-order remainder exceeds "
        "that penalty. That inequality is not proved for every portfolio, so "
        "these floors are not optimality certificates."
    )
    lines.append("2. DISCOVERY COVERAGE")
    for family in payload["taxonomy"]:
        lines.append(f"{family['id']} searched={family['searched']} note={family['note']}")
    lines.append(f"DISCOVERY_SATURATION: {payload['discovery_saturation']}")
    for remaining in payload["remaining_high_value_families"]:
        lines.append(f"REMAINING: {remaining}")
    lines.append("3. TOP NEW METHODS")
    for method in payload["methods"][:10]:
        lines.append(
            f"{method['method_id']} novelty={method['novelty_status']} "
            f"prototyped={method['prototyped']} source={method['source']} "
            f"why={method['why']}"
        )
    lines.append("4. STRICT IMPROVEMENTS FOUND")
    improvements = [
        row for row in payload["prototypes"] if row["comparison_label"] == "STRICT_IMPROVEMENT"
    ]
    if not improvements:
        lines.append("None in the bounded prototypes below.")
    for row in improvements:
        lines.append(
            f"K{row['k']} {row['official_any_prize']} sha256={row['portfolio_sha256']} "
            f"method={row['method_id']}"
        )
    lines.append("5. USEFUL NEGATIVE RESULTS")
    for row in payload["negative_results"][:10]:
        lines.append(row["statement"])
    lines.append("6. TRUE PRE-DRAW SIGNAL OPPORTUNITIES")
    lines.append(payload["pre_draw_signal"])
    lines.append("7. BEST OPEN-SOURCE ASSETS TO IMPORT")
    for asset in payload["open_source_assets"][:10]:
        lines.append(f"{asset['name']} {asset['url']} use={asset['use']}")
    lines.append("8. NEXT 3 IMPLEMENTATION TASKS")
    for index, task in enumerate(payload["next_tasks"], start=1):
        lines.append(f"{index}. {task}")
    lines.append("9. SINGLE HIGHEST-VALUE NEXT TASK")
    lines.append(payload["primary_next_task"])
    return "\n".join(lines)


__all__ = [
    "BASELINE_FRACTIONS",
    "RECORD_PATH",
    "affine_shortened_portfolio",
    "canonical_portfolio_sha256",
    "chord_inequality_holds",
    "comparison_label",
    "disjoint_packing",
    "intersection_histogram",
    "load_frontier_record",
    "minimum_pair_incidence",
    "number_frequency",
    "one_number_exchange",
    "pair_incidence",
    "pairwise_winning_intersections",
    "random_minimum_s2_k10",
    "random_minimum_s2_k20",
    "render_handoff",
    "s2_lower_bound",
    "score_portfolio",
    "triangle_free_k10",
    "triple_structure",
    "two_ticket_union_outcomes",
]
