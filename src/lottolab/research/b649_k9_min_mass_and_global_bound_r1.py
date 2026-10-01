"""K=9 minimum overlap mass, its unlabeled census, and a mass>=6 upper bound.

Mass is ``sum_n C(r_n, 2)``, the same quantity as in the K=10 derivation.
Exact OFFICIAL_ANY_PRIZE scores come only from ``evaluate_portfolio``.
The mass>=6 argument does not list higher-mass portfolios. It reduces them,
by the existing exchange lemma, to the mass-5 census or to six multiplicity
profiles on all 49 labels, and bounds those six profiles with Bonferroni.
"""

from __future__ import annotations

import itertools
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from math import comb, factorial
from pathlib import Path
from typing import cast

from lottolab.research.b649_k1_k8_global_optimality import (
    PrizeEvent,
    independent_disjoint_pair_outcome_count,
    independent_single_outcome_count,
    outcome_space_size,
)
from lottolab.research.b649_k10_min_overlap_exhaustive_r1 import (
    class_set_sha256,
    degrees_of,
    graph_is_admissible,
    minimum_overlap_derivation,
    portfolio_from_edges,
    produces_duplicate_ticket,
)
from lottolab.research.b649_k10_overlap_mass12_bonferroni_screen_r1 import (
    _joint_count_from_regions,  # pyright: ignore[reportPrivateUsage]
    _joint_event_count,  # pyright: ignore[reportPrivateUsage]
    u3_outcome_count,
)
from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
    ticket_mask,
)

POOL_SIZE = 49
DRAW_SIZE = 6
TICKET_COUNT = 9
MASS5 = 5
MAX_DEGREE = DRAW_SIZE
OUTCOME_COUNT = outcome_space_size(PrizeEvent.OFFICIAL_ANY_PRIZE)
RECORD_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs/research/matrix-native-results/b649-k9-min-mass-and-global-bound-r1.json"
)
BASE_HEAD = "87841ac3e0aabaa95176b58d42519b70d5813707"
TASK_HEAD = "SINGLE_COMMIT_ON_87841ac3e0aabaa95176b58d42519b70d5813707"
FOCUSED_TESTS = "uv run pytest tests/unit/test_b649_k9_min_mass_and_global_bound_r1.py"
RUFF = (
    "uv run ruff check src/lottolab/research/b649_k9_min_mass_and_global_bound_r1.py "
    "tests/unit/test_b649_k9_min_mass_and_global_bound_r1.py"
)
PYRIGHT = (
    "uv run pyright src/lottolab/research/b649_k9_min_mass_and_global_bound_r1.py "
    "tests/unit/test_b649_k9_min_mass_and_global_bound_r1.py"
)

Edge = tuple[int, int, int]
Ticket = tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ClassWitness:
    """One mass-5 isomorphism class and the portfolio that realizes it."""

    class_id: str
    tickets: tuple[Ticket, ...]
    outcome_count: int


@dataclass(frozen=True, slots=True)
class K9Certificate:
    """Live census plus the mass>=6 comparison. Witnesses are re-scored by callers."""

    minimum_mass: int
    histogram: dict[str, int]
    profile_unique: bool
    class_ids: tuple[str, ...]
    class_set_sha256: str
    witnesses: tuple[ClassWitness, ...]
    optimum_count: int
    optimum_probability: Fraction
    tie_count: int
    optimum_class_id: str
    residual_bonferroni_ceiling: int
    mass_ge6_bound: int
    global_optimum_status: str
    remaining_gap: int


def _int_histogram(raw: object) -> dict[str, int]:
    if not isinstance(raw, dict):
        raise TypeError("frequency histogram is not a dict")
    counts: dict[str, int] = {}
    for frequency, count in cast(dict[object, object], raw).items():
        if not isinstance(frequency, str) or type(count) is not int:
            raise TypeError("frequency histogram changed shape")
        counts[frequency] = count
    return counts


def prove_k9_minimum_profile() -> dict[str, object]:
    """Call the K=10 derivation at K=9. Mass 5 with 44 singles and 5 doubles."""

    derived = minimum_overlap_derivation(ticket_count=TICKET_COUNT)
    counts = _int_histogram(derived["histogram"])
    minimum_mass = derived["minimum_mass"]
    slots = derived["slots"]
    pool_size = derived["pool_size"]
    if type(minimum_mass) is not int or type(slots) is not int or type(pool_size) is not int:
        raise TypeError(f"K=9 minimum-overlap profile changed: {derived}")
    if (
        minimum_mass != MASS5
        or counts.get("1") != 44
        or counts.get("2") != 5
        or any(frequency not in {"1", "2"} for frequency in counts)
        or derived["profile_unique"] is not True
    ):
        raise ValueError(f"K=9 minimum-overlap profile changed: {derived}")
    return {
        "minimum_mass": minimum_mass,
        "histogram": counts,
        "profile_unique": True,
        "slots": slots,
        "pool_size": pool_size,
    }


def _edge_text(edges: tuple[Edge, ...]) -> str:
    return " ".join(f"{left} {right} {multiplicity}" for left, right, multiplicity in edges)


def _parse_edge_text(text: str) -> tuple[Edge, ...]:
    if not text:
        return ()
    numbers = [int(part) for part in text.split()]
    if len(numbers) % 3 != 0:
        raise ValueError(f"illegal edge text: {text!r}")
    return tuple(
        (numbers[index], numbers[index + 1], numbers[index + 2])
        for index in range(0, len(numbers), 3)
    )


def canonical_edges(edges: tuple[Edge, ...]) -> tuple[Edge, ...]:
    """Lex-min edge list. A minimum-multiplicity edge is placed at ``(0, 1)``."""

    if not edges:
        return ()
    support = sorted({vertex for edge in edges for vertex in edge[:2]})
    index = {vertex: position for position, vertex in enumerate(support)}
    local: list[Edge] = []
    for left, right, multiplicity in edges:
        mapped_left, mapped_right = index[left], index[right]
        if mapped_left > mapped_right:
            mapped_left, mapped_right = mapped_right, mapped_left
        local.append((mapped_left, mapped_right, multiplicity))
    width = len(support)
    minimum = min(multiplicity for _, _, multiplicity in local)
    best: tuple[Edge, ...] | None = None
    seeds = [(left, right) for left, right, multiplicity in local if multiplicity == minimum]
    for left, right in seeds:
        for start, nxt in ((left, right), (right, left)):
            rest = [vertex for vertex in range(width) if vertex not in (start, nxt)]
            for perm in itertools.permutations(rest):
                rank = {start: 0, nxt: 1}
                for label, vertex in enumerate(perm, start=2):
                    rank[vertex] = label
                mapped: list[Edge] = []
                for old_left, old_right, multiplicity in local:
                    new_left, new_right = rank[old_left], rank[old_right]
                    if new_left > new_right:
                        new_left, new_right = new_right, new_left
                    mapped.append((new_left, new_right, multiplicity))
                mapped.sort()
                code = tuple(mapped)
                if best is None or code < best:
                    best = code
    if best is None:
        raise ValueError("canonical search did not label the support")
    return best


def _connected_components(
    max_degree: int, max_mass: int
) -> dict[int, tuple[tuple[Edge, ...], ...]]:
    """Unlabeled connected loopless multigraphs with no isolated vertex."""

    library: dict[int, list[tuple[Edge, ...]]] = defaultdict(list)
    for mass in range(1, max_mass + 1):
        seen: set[tuple[Edge, ...]] = set()
        for vertices in range(2, min(6, mass + 1) + 1):
            pairs = list(itertools.combinations(range(vertices), 2))

            def walk(
                pair_at: int,
                remaining: int,
                degree: list[int],
                chosen: list[Edge],
                *,
                vertices: int = vertices,
                pairs: list[tuple[int, int]] = pairs,
                seen: set[tuple[Edge, ...]] = seen,
            ) -> None:
                if remaining == 0:
                    if any(item == 0 for item in degree):
                        return
                    parent = list(range(vertices))

                    def find(vertex: int) -> int:
                        while parent[vertex] != vertex:
                            parent[vertex] = parent[parent[vertex]]
                            vertex = parent[vertex]
                        return vertex

                    for left, right, _multiplicity in chosen:
                        parent[find(left)] = find(right)
                    if len({find(vertex) for vertex in range(vertices)}) != 1:
                        return
                    seen.add(canonical_edges(tuple(chosen)))
                    return
                if pair_at == len(pairs):
                    return
                left, right = pairs[pair_at]
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

            walk(0, mass, [0] * vertices, [])
        library[mass] = sorted(seen)
    return {mass: tuple(components) for mass, components in library.items()}


def enumerate_unlabeled_multigraphs(
    vertex_count: int,
    edge_count: int,
    max_degree: int,
) -> tuple[str, ...]:
    """Canonical edge strings of loopless multigraphs with total multiplicity ``edge_count``.

    Components have at most six vertices because a connected support of multiplicity
    ``m`` has at most ``m + 1`` vertices. Isolates make up the rest of ``vertex_count``.
    """

    if vertex_count < 0 or edge_count < 0 or max_degree < 0:
        raise ValueError("enumeration parameters must be nonnegative")
    if edge_count == 0:
        return ("",) if vertex_count >= 0 else ()
    library = _connected_components(max_degree, edge_count)
    found: set[str] = set()

    def component_support(edges: tuple[Edge, ...]) -> int:
        return len({vertex for edge in edges for vertex in edge[:2]})

    def walk(remaining: int, minimum_mass: int, chosen: list[tuple[Edge, ...]]) -> None:
        if remaining == 0:
            if sum(component_support(edges) for edges in chosen) > vertex_count:
                return
            placed: list[Edge] = []
            cursor = 0
            for edges in chosen:
                shift: dict[int, int] = {}
                for left, right, _multiplicity in edges:
                    shift.setdefault(left, 0)
                    shift.setdefault(right, 0)
                for vertex in sorted(shift):
                    shift[vertex] = cursor
                    cursor += 1
                for left, right, multiplicity in edges:
                    new_left, new_right = shift[left], shift[right]
                    if new_left > new_right:
                        new_left, new_right = new_right, new_left
                    placed.append((new_left, new_right, multiplicity))
            found.add(_edge_text(canonical_edges(tuple(placed))))
            return
        for mass in range(minimum_mass, remaining + 1):
            for edges in library[mass]:
                if chosen and mass == sum(item for _, _, item in chosen[-1]) and edges < chosen[-1]:
                    continue
                chosen.append(edges)
                walk(remaining - mass, mass, chosen)
                chosen.pop()

    walk(edge_count, 1, [])
    return tuple(sorted(found))


def labeled_orbit_total(class_ids: Iterable[str], vertex_count: int) -> int:
    """Sum of orbit sizes on ``vertex_count`` labeled vertices, isolates included."""

    total = 0
    for class_id in class_ids:
        edges = _parse_edge_text(class_id)
        support = sorted({vertex for edge in edges for vertex in edge[:2]})
        width = len(support)
        index = {vertex: position for position, vertex in enumerate(support)}
        local = tuple(
            sorted(
                (index[left], index[right], multiplicity)
                if index[left] < index[right]
                else (index[right], index[left], multiplicity)
                for left, right, multiplicity in edges
            )
        )
        automorphisms = 0
        for perm in itertools.permutations(range(width)):
            mapped: list[Edge] = []
            for left, right, multiplicity in local:
                new_left, new_right = perm[left], perm[right]
                if new_left > new_right:
                    new_left, new_right = new_right, new_left
                mapped.append((new_left, new_right, multiplicity))
            if tuple(sorted(mapped)) == local:
                automorphisms += 1
        if automorphisms < 1:
            raise ValueError(f"class has no automorphism: {class_id}")
        total += factorial(vertex_count) // (factorial(vertex_count - width) * automorphisms)
    return total


def mass5_class_ids() -> tuple[str, ...]:
    """Legal K=9 mass-5 classes. Every admissible graph rebuilds nine distinct tickets."""

    class_ids = enumerate_unlabeled_multigraphs(TICKET_COUNT, MASS5, MAX_DEGREE)
    legal: list[str] = []
    for class_id in class_ids:
        edges = _parse_edge_text(class_id)
        if not graph_is_admissible(
            edges, vertex_count=TICKET_COUNT, edge_count=MASS5, max_degree=MAX_DEGREE
        ):
            continue
        if produces_duplicate_ticket(edges, vertex_count=TICKET_COUNT):
            continue
        if any(degree > MAX_DEGREE for degree in degrees_of(TICKET_COUNT, edges)):
            continue
        portfolio_from_edges(edges, vertex_count=TICKET_COUNT, draw_size=DRAW_SIZE)
        legal.append(class_id)
    if tuple(legal) != class_ids:
        raise ValueError("a mass-5 admissible graph did not rebuild nine distinct tickets")
    return class_ids


def witness_portfolio(class_id: str) -> tuple[Ticket, ...]:
    """Deterministic tickets for one canonical mass-5 edge list."""

    return portfolio_from_edges(
        _parse_edge_text(class_id), vertex_count=TICKET_COUNT, draw_size=DRAW_SIZE
    )


def _score_all(class_ids: Sequence[str]) -> tuple[ClassWitness, ...]:
    """Exact OFFICIAL_ANY_PRIZE count of one witness per class."""

    draws = all_main_draw_masks(POOL_SIZE, DRAW_SIZE)
    witnesses: list[ClassWitness] = []
    for class_id in class_ids:
        portfolio = witness_portfolio(class_id)
        outcome_count = evaluate_portfolio(
            portfolio, draws=draws
        ).official_any_prize_outcome_count
        witnesses.append(
            ClassWitness(class_id=class_id, tickets=portfolio, outcome_count=outcome_count)
        )
    return tuple(witnesses)


@cache
def _pair_joint_counts() -> tuple[int, ...]:
    """Outcomes on which two 6-subsets of intersection ``s`` both win, ``s = 0..6``."""

    counts: list[int] = []
    for size in range(DRAW_SIZE + 1):
        left = tuple(range(1, DRAW_SIZE + 1))
        right = tuple(range(1, size + 1)) + tuple(range(DRAW_SIZE + 1, 2 * DRAW_SIZE - size + 1))
        counts.append(_joint_event_count((ticket_mask(left), ticket_mask(right))))
    joints = tuple(counts)
    single = independent_single_outcome_count(PrizeEvent.OFFICIAL_ANY_PRIZE)
    disjoint = independent_disjoint_pair_outcome_count(PrizeEvent.OFFICIAL_ANY_PRIZE)
    if joints[0] != disjoint or joints[DRAW_SIZE] != single:
        raise ValueError(f"pair joints disagree with the K=1..8 counts: {joints}")
    differences = [joints[index + 1] - joints[index] for index in range(DRAW_SIZE)]
    if any(differences[index] > differences[index + 1] for index in range(DRAW_SIZE - 1)):
        raise ValueError(f"pair-joint counts are not convex: {joints}")
    return joints


def _residual_excess_partitions() -> tuple[tuple[int, ...], ...]:
    """Partitions of excess 5 that use at least one multiplicity ``r >= 3``.

    Each part is ``r - 1``. All 49 labels are used, so the excess is exactly 5.
    The all-ones partition is mass 5 and is not residual.
    """

    found: list[tuple[int, ...]] = []

    def walk(remaining: int, minimum: int, parts: list[int]) -> None:
        if remaining == 0:
            if any(part >= 2 for part in parts):
                found.append(tuple(sorted(parts, reverse=True)))
            return
        for part in range(minimum, remaining + 1):
            parts.append(part)
            walk(remaining - part, part, parts)
            parts.pop()

    walk(5, 1, [])
    return tuple(sorted(found))


def _support_choices(size: int) -> tuple[frozenset[int], ...]:
    return tuple(frozenset(choice) for choice in itertools.combinations(range(TICKET_COUNT), size))


def _residual_support_systems() -> Iterable[tuple[frozenset[int], ...]]:
    """Ticket supports of the repeated labels, one symmetry reduction per profile.

    The largest support is fixed as ``{0, ..., s-1}``. Identical smaller supports
    are generated as nondecreasing combinations, so every placement appears once
    after that relabeling.
    """

    pairs = _support_choices(2)
    triples = _support_choices(3)
    fixed_triple = frozenset((0, 1, 2))
    fixed_four = frozenset((0, 1, 2, 3))
    fixed_five = frozenset(range(5))
    fixed_six = frozenset(range(6))
    pair_index = {support: index for index, support in enumerate(pairs)}
    for chosen in itertools.combinations_with_replacement(range(len(pairs)), 3):
        yield (fixed_triple, pairs[chosen[0]], pairs[chosen[1]], pairs[chosen[2]])
    for second in triples:
        for pair in pairs:
            yield (fixed_triple, second, pair)
    for chosen in itertools.combinations_with_replacement(range(len(pairs)), 2):
        yield (fixed_four, pairs[chosen[0]], pairs[chosen[1]])
    for triple in triples:
        yield (fixed_four, triple)
    for pair in pairs:
        yield (fixed_five, pair)
    yield (fixed_six,)
    if pair_index[frozenset((0, 1))] != 0:
        raise ValueError("pair order changed")


def _regions_for_triple(
    supports: tuple[frozenset[int], ...], triple: tuple[int, int, int]
) -> tuple[int, ...]:
    specials = [0] * 7
    for support in supports:
        signature = 0
        for bit, ticket in enumerate(triple):
            if ticket in support:
                signature |= 1 << bit
        if signature:
            specials[signature - 1] += 1

    def specials_in(bit: int) -> int:
        return sum(
            specials[signature - 1]
            for signature in range(1, 8)
            if signature & (1 << bit)
        )

    privates = [DRAW_SIZE - specials_in(bit) for bit in range(3)]
    if min(privates) < 0:
        raise ValueError("repeated labels do not fit in a ticket")
    specials[0] += privates[0]
    specials[1] += privates[1]
    specials[3] += privates[2]
    return tuple(specials)


def _portfolio_from_supports(supports: tuple[frozenset[int], ...]) -> tuple[Ticket, ...]:
    """Legal tickets whose repeated labels are exactly ``supports``."""

    tickets: list[list[int]] = [[] for _ in range(TICKET_COUNT)]
    number = 1
    for support in supports:
        if len(support) < 2:
            raise ValueError("a repeated label needs two tickets")
        for ticket_index in sorted(support):
            tickets[ticket_index].append(number)
        number += 1
    for ticket in tickets:
        missing = DRAW_SIZE - len(ticket)
        if missing < 0:
            raise ValueError("repeated labels do not fit in a ticket")
        for _ in range(missing):
            ticket.append(number)
            number += 1
    if number - 1 != POOL_SIZE:
        raise ValueError("residual profile must use every label")
    portfolio = tuple(tuple(sorted(ticket)) for ticket in tickets)
    if len(set(portfolio)) != TICKET_COUNT:
        raise ValueError("residual profile reconstructed a duplicate ticket")
    return portfolio


def _bonferroni_of_supports(supports: tuple[frozenset[int], ...]) -> int:
    joints = _pair_joint_counts()
    pair_total = 0
    for left, right in itertools.combinations(range(TICKET_COUNT), 2):
        shared = sum(1 for support in supports if left in support and right in support)
        pair_total += joints[shared]
    triple_total = 0
    for triple in itertools.combinations(range(TICKET_COUNT), 3):
        regions = _regions_for_triple(supports, triple)
        triple_total += _joint_count_from_regions(regions, 3, POOL_SIZE, DRAW_SIZE, 3)
    single = independent_single_outcome_count(PrizeEvent.OFFICIAL_ANY_PRIZE)
    return TICKET_COUNT * single - pair_total + triple_total


@cache
def residual_bonferroni_ceiling() -> int:
    """Maximum third-order Bonferroni value over the six residual profiles."""

    partitions = _residual_excess_partitions()
    expected = (
        (2, 1, 1, 1),
        (2, 2, 1),
        (3, 1, 1),
        (3, 2),
        (4, 1),
        (5,),
    )
    if partitions != expected:
        raise ValueError(f"residual excess partitions changed: {partitions}")
    ceiling = 0
    seen = 0
    first: tuple[frozenset[int], ...] | None = None
    best: tuple[frozenset[int], ...] | None = None
    for supports in _residual_support_systems():
        seen += 1
        value = _bonferroni_of_supports(supports)
        if first is None:
            first = supports
        if value >= ceiling:
            ceiling = value
            best = supports
    # 3+2+2+2, 3+3+2, 4+2+2, 4+3, 5+2, and one 6-support.
    expected_seen = (
        comb(comb(TICKET_COUNT, 2) + 3 - 1, 3)
        + comb(TICKET_COUNT, 3) * comb(TICKET_COUNT, 2)
        + comb(comb(TICKET_COUNT, 2) + 2 - 1, 2)
        + comb(TICKET_COUNT, 3)
        + comb(TICKET_COUNT, 2)
        + 1
    )
    if seen != expected_seen:
        raise ValueError(f"residual support count changed: {seen} != {expected_seen}")
    if first is None or best is None:
        raise ValueError("residual scan was empty")
    for supports in (first, best):
        public = u3_outcome_count(_portfolio_from_supports(supports))
        if _bonferroni_of_supports(supports) != public:
            raise ValueError("region Bonferroni disagrees with u3_outcome_count")
    return ceiling


def compare_higher_mass(mass5_optimum: int, residual_ceiling: int) -> tuple[int, str, int]:
    """Uniform upper bound for every portfolio of overlap mass at least 6.

    Exchange, while an unused label exists, does not decrease OFFICIAL_ANY_PRIZE
    coverage and lowers the mass. It stops only when all 49 labels are used.
    That terminal portfolio is mass 5, or one of the residual profiles whose
    Bonferroni value is ``residual_ceiling``. Coverage of the original portfolio
    is at most the terminal coverage, hence at most the larger of the mass-5
    optimum and the residual ceiling.
    """

    if mass5_optimum < 0 or residual_ceiling < 0:
        raise ValueError("bounds must be nonnegative")
    bound = max(mass5_optimum, residual_ceiling)
    if bound <= mass5_optimum:
        return bound, "PROVEN", 0
    return bound, "UNKNOWN", bound - mass5_optimum


def build_certificate() -> K9Certificate:
    """Census, exact scores, and the mass>=6 comparison. This is the shipped entry."""

    profile = prove_k9_minimum_profile()
    minimum_mass = profile["minimum_mass"]
    if type(minimum_mass) is not int:
        raise TypeError("histogram missing")
    typed_histogram = _int_histogram(profile["histogram"])
    class_ids = mass5_class_ids()
    labeled = comb(comb(TICKET_COUNT, 2) + MASS5 - 1, MASS5)
    if labeled_orbit_total(class_ids, TICKET_COUNT) != labeled:
        raise ValueError("mass-5 class orbits do not cover every labeled multigraph")
    witnesses = _score_all(class_ids)
    optimum = max(witness.outcome_count for witness in witnesses)
    ties = sum(1 for witness in witnesses if witness.outcome_count == optimum)
    optimum_class = min(
        witness.class_id for witness in witnesses if witness.outcome_count == optimum
    )
    residual_ceiling = residual_bonferroni_ceiling()
    bound, status, gap = compare_higher_mass(optimum, residual_ceiling)
    return K9Certificate(
        minimum_mass=minimum_mass,
        histogram=typed_histogram,
        profile_unique=True,
        class_ids=class_ids,
        class_set_sha256=class_set_sha256(class_ids),
        witnesses=witnesses,
        optimum_count=optimum,
        optimum_probability=Fraction(optimum, OUTCOME_COUNT),
        tie_count=ties,
        optimum_class_id=optimum_class,
        residual_bonferroni_ceiling=residual_ceiling,
        mass_ge6_bound=bound,
        global_optimum_status=status,
        remaining_gap=gap,
    )


def certificate_payload(certificate: K9Certificate) -> dict[str, object]:
    """JSON-ready record. No mass>=6 class list is stored."""

    probability = certificate.optimum_probability
    return {
        "task_id": "B649_K9_MIN_MASS_AND_GLOBAL_BOUND_R1",
        "event": "OFFICIAL_ANY_PRIZE",
        "ticket_count": TICKET_COUNT,
        "minimum_mass": certificate.minimum_mass,
        "histogram": certificate.histogram,
        "profile_unique": certificate.profile_unique,
        "MASS5_CLASS_COUNT": len(certificate.class_ids),
        "class_set_sha256": certificate.class_set_sha256,
        "classes": [
            {
                "class_id": witness.class_id,
                "tickets": [list(ticket) for ticket in witness.tickets],
                "official_any_prize_outcome_count": witness.outcome_count,
            }
            for witness in certificate.witnesses
        ],
        "MASS5_OPTIMUM_COUNT": certificate.optimum_count,
        "MASS5_OPTIMUM_PROBABILITY": f"{probability.numerator}/{probability.denominator}",
        "MASS5_TIE_COUNT": certificate.tie_count,
        "optimum_class_id": certificate.optimum_class_id,
        "residual_bonferroni_ceiling": certificate.residual_bonferroni_ceiling,
        "MASS_GE6_BOUND": certificate.mass_ge6_bound,
        "GLOBAL_OPTIMUM_STATUS": certificate.global_optimum_status,
        "REMAINING_GAP": certificate.remaining_gap,
        "higher_mass_class_list": False,
        "BASE_HEAD": BASE_HEAD,
        "TASK_HEAD": TASK_HEAD,
        "TASK_STATUS": "COMPLETE",
        "FOCUSED_TESTS": FOCUSED_TESTS,
        "RUFF": RUFF,
        "PYRIGHT": PYRIGHT,
        "NEW_SEARCH_STARTED": "NO",
        "K20_TAKEOVER": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def write_record(certificate: K9Certificate, path: Path = RECORD_PATH) -> None:
    payload = certificate_payload(certificate)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_record(path: Path = RECORD_PATH) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError("K9 record is not an object")
    record: dict[str, object] = {}
    for key, value in cast(dict[object, object], loaded).items():
        if not isinstance(key, str):
            raise TypeError("K9 record key is not a string")
        record[key] = value
    return record


def handoff_lines(record: dict[str, object] | None = None) -> str:
    """The stable handoff block stored in the record."""

    source = load_record() if record is None else record
    keys = (
        "TASK_STATUS",
        "BASE_HEAD",
        "TASK_HEAD",
        "MASS5_CLASS_COUNT",
        "MASS5_OPTIMUM_COUNT",
        "MASS5_OPTIMUM_PROBABILITY",
        "MASS5_TIE_COUNT",
        "MASS_GE6_BOUND",
        "GLOBAL_OPTIMUM_STATUS",
        "REMAINING_GAP",
        "FOCUSED_TESTS",
        "RUFF",
        "PYRIGHT",
        "NEW_SEARCH_STARTED",
        "K20_TAKEOVER",
        "PRODUCTION_MUTATION",
    )
    lines = [f"{key}: {source[key]}" for key in keys]
    return "\n".join(lines)


__all__ = [
    "MAX_DEGREE",
    "OUTCOME_COUNT",
    "RECORD_PATH",
    "ClassWitness",
    "K9Certificate",
    "build_certificate",
    "canonical_edges",
    "certificate_payload",
    "compare_higher_mass",
    "enumerate_unlabeled_multigraphs",
    "handoff_lines",
    "labeled_orbit_total",
    "load_record",
    "mass5_class_ids",
    "prove_k9_minimum_profile",
    "residual_bonferroni_ceiling",
    "witness_portfolio",
    "write_record",
]
