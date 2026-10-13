"""Orbit reduction and engine slot mapping for the B649 K20 C2 exact N2 search.

The exact two-ticket (N2) neighborhood of a portfolio P is indexed by unordered
slot pairs {a, b}: remove tickets a and b, add any two distinct tickets. If a
number permutation sigma maps P onto itself, it maps the 18 untouched tickets of
{a, b} onto the 18 untouched tickets of the image pair, and it maps every legal
replacement of {a, b} bijectively onto a legal replacement of the image pair
with the same OFFICIAL_ANY_PRIZE count (the objective is symmetric in the 49
numbers). Searching one representative per slot-pair orbit therefore covers all
190 slot pairs exactly. That is load-bearing only through the explicit witness
recorded for every pair, which ``validate_mapping`` re-checks from scratch.

Slots here are the ORDERED C2 artifact slots. The exact N2 engine indexes the
normalized (sorted) portfolio instead, so every pair is also translated through
an explicit by-value ordered-to-engine slot permutation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any

POOL_SIZE = 49
TICKET_SIZE = 6
TICKET_COUNT = 20
HEAVY_MAX_NUMBER = 26
EXPECTED_GROUP_ORDER = 144
EXPECTED_RAW_SLOT_PAIRS = 190
EXPECTED_REPRESENTATIVES = 94
EXPECTED_CLASS_COUNTS = {"H-H": 66, "H-U": 24, "U-U": 4}
EXPECTED_ORBIT_SIZES = {1: 67, 2: 12, 6: 13, 9: 1, 12: 1}
C2_START_COUNT = 313_263_888
C2_ORDERED_SHA256 = "6a537ea56c2741e1208dbbb4abf1064bc74508f2d356712920d348d11e3a4a24"
C2_SORTED_SHA256 = "2372afa39eea13bc3f31788a4e1f11166663da85580c0bd50c8064f2f96929a5"
C2_CANONICAL_CLASS_ID = "e4b1941183c0583d479c1467d7ce9aadf164190a07734ec592a8cf6f45ee07d7"
C4_CANONICAL_CLASS_ID = "ef74855715fd27889606328cc6dedf48dfc77b7b7de228deaa8e1c477d753830"
C2_N1_DELTA0_TIE_SORTED_SHA256 = "008dbba16270a0d8b3d5deab103793677de25ab407c22fd1e9703345dc7ab2bc"

Ticket = tuple[int, ...]
SlotPair = tuple[int, int]


def compact_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def require_c2_start(portfolio: Sequence[Sequence[int]]) -> None:
    """Raise unless ``portfolio`` is the pinned C2 START in its original ticket order."""

    ordered = [list(ticket) for ticket in portfolio]
    normalized = sorted(sorted(ticket) for ticket in ordered)
    if compact_sha256(normalized) == C2_N1_DELTA0_TIE_SORTED_SHA256:
        raise ValueError("the C2 N1 delta-0 tie neighbor is not the C2 START")
    if compact_sha256(ordered) != C2_ORDERED_SHA256:
        raise ValueError("START ordered SHA-256 differs from the pinned C2 START")
    if compact_sha256(normalized) != C2_SORTED_SHA256:
        raise ValueError("START sorted SHA-256 differs from the pinned C2 START")


@dataclass(frozen=True, order=True)
class Automorphism:
    """A ticket-slot permutation with its number relabeling.

    ``slots[a]`` is the image of ordered slot ``a``; ``numbers[n - 1]`` is the
    image of number ``n``. Applying ``numbers`` to ticket ``a`` gives ticket
    ``slots[a]``.
    """

    slots: tuple[int, ...]
    numbers: tuple[int, ...]


def _tickets(portfolio: Sequence[Sequence[int]]) -> tuple[Ticket, ...]:
    tickets = tuple(tuple(sorted(ticket)) for ticket in portfolio)
    if len(tickets) != TICKET_COUNT:
        raise ValueError(f"portfolio must contain exactly {TICKET_COUNT} tickets")
    for ticket in tickets:
        if len(set(ticket)) != TICKET_SIZE or any(
            type(n) is not int or not 1 <= n <= POOL_SIZE for n in ticket
        ):
            raise ValueError("every ticket must hold six distinct numbers in 1..49")
    if len(set(tickets)) != TICKET_COUNT:
        raise ValueError("portfolio tickets must be distinct")
    return tickets


def ticket_class(ticket: Sequence[int]) -> str:
    if max(ticket) <= HEAVY_MAX_NUMBER:
        return "H"
    if min(ticket) > HEAVY_MAX_NUMBER:
        return "U"
    raise ValueError("ticket mixes the H (1..26) and U (27..49) supports")


def pair_class(portfolio: Sequence[Sequence[int]], pair: SlotPair) -> str:
    labels = sorted(ticket_class(portfolio[slot]) for slot in pair)
    return f"{labels[0]}-{labels[1]}"


def apply_numbers(numbers: Sequence[int], ticket: Sequence[int]) -> Ticket:
    return tuple(sorted(numbers[n - 1] for n in ticket))


def is_automorphism(portfolio: Sequence[Sequence[int]], element: Automorphism) -> bool:
    """Directly check that ``element`` maps every ticket onto its claimed image."""

    tickets = _tickets(portfolio)
    if sorted(element.slots) != list(range(TICKET_COUNT)):
        return False
    if sorted(element.numbers) != list(range(1, POOL_SIZE + 1)):
        return False
    return all(
        apply_numbers(element.numbers, tickets[a]) == tickets[element.slots[a]]
        for a in range(TICKET_COUNT)
    )


def _incidence(tickets: Sequence[Ticket]) -> dict[int, frozenset[int]]:
    incidence: dict[int, set[int]] = {n: set() for n in range(1, POOL_SIZE + 1)}
    for slot, ticket in enumerate(tickets):
        for n in ticket:
            incidence[n].add(slot)
    return {n: frozenset(slots) for n, slots in incidence.items()}


def automorphism_group(portfolio: Sequence[Sequence[int]]) -> tuple[Automorphism, ...]:
    """Return the full-support automorphism group, sorted, with closure checked.

    Requires every number to lie on at least one ticket, no two numbers to share
    a ticket set, and pairwise ticket overlaps of at most one number. Then each
    slot permutation fixes at most one number relabeling, and every shared
    number of two assigned slots must go to the shared number of their images,
    so backtracking keeps a partial injective number map and prunes on conflict.
    """

    tickets = _tickets(portfolio)
    incidence = _incidence(tickets)
    if any(not slots for slots in incidence.values()):
        raise ValueError("portfolio does not have full 49-number support")
    owner = {slots: n for n, slots in incidence.items()}
    if len(owner) != POOL_SIZE:
        raise ValueError("two numbers share a ticket set; the group would have a kernel")

    sets = [frozenset(t) for t in tickets]
    common: dict[SlotPair, int] = {}
    for a, b in combinations(range(TICKET_COUNT), 2):
        shared = sets[a] & sets[b]
        if len(shared) > 1:
            raise ValueError("two tickets share more than one number")
        if shared:
            (n,) = shared
            common[(a, b)] = common[(b, a)] = n
    invariant = [tuple(sorted(len(incidence[n]) for n in t)) for t in tickets]

    found: list[Automorphism] = []
    image = [-1] * TICKET_COUNT
    used = [False] * TICKET_COUNT
    sigma: dict[int, int] = {}
    sigma_inverse: dict[int, int] = {}

    def extend(a: int) -> None:
        if a == TICKET_COUNT:
            numbers: list[int] = []
            for n in range(1, POOL_SIZE + 1):
                target = frozenset(image[s] for s in incidence[n])
                if target not in owner:
                    return
                numbers.append(owner[target])
            element = Automorphism(tuple(image), tuple(numbers))
            if is_automorphism(tickets, element):
                found.append(element)
            return
        for candidate in range(TICKET_COUNT):
            if used[candidate] or invariant[candidate] != invariant[a]:
                continue
            added: list[int] = []
            consistent = True
            for b in range(a):
                source = common.get((a, b))
                target = common.get((candidate, image[b]))
                if (source is None) != (target is None):
                    consistent = False
                    break
                if source is None or target is None:
                    continue
                if source in sigma or target in sigma_inverse:
                    if sigma.get(source) != target or sigma_inverse.get(target) != source:
                        consistent = False
                        break
                    continue
                sigma[source] = target
                sigma_inverse[target] = source
                added.append(source)
            if consistent:
                image[a] = candidate
                used[candidate] = True
                extend(a + 1)
                used[candidate] = False
            for source in added:
                del sigma_inverse[sigma.pop(source)]
        image[a] = -1

    extend(0)
    group = tuple(sorted(found))
    _check_closure(group)
    return group


def compose(first: Automorphism, second: Automorphism) -> Automorphism:
    """Apply ``first`` then ``second``."""

    return Automorphism(
        tuple(second.slots[s] for s in first.slots),
        tuple(second.numbers[n - 1] for n in first.numbers),
    )


def _check_closure(group: Sequence[Automorphism]) -> None:
    members = set(group)
    identity = Automorphism(tuple(range(TICKET_COUNT)), tuple(range(1, POOL_SIZE + 1)))
    if identity not in members:
        raise ValueError("automorphism group lacks the identity")
    for first in group:
        for second in group:
            if compose(first, second) not in members:
                raise ValueError("automorphism set is not closed under composition")


def map_pair(element: Automorphism, pair: SlotPair) -> SlotPair:
    a, b = sorted((element.slots[pair[0]], element.slots[pair[1]]))
    return (a, b)


def all_slot_pairs() -> list[SlotPair]:
    return [(a, b) for a, b in combinations(range(TICKET_COUNT), 2)]


def burnside_pair_orbit_count(group: Sequence[Automorphism]) -> int:
    fixed = sum(
        sum(1 for pair in all_slot_pairs() if map_pair(element, pair) == pair) for element in group
    )
    if fixed % len(group):
        raise ValueError("Burnside sum is not divisible by the group order")
    return fixed // len(group)


def ordered_to_engine_slots(portfolio: Sequence[Sequence[int]]) -> tuple[int, ...]:
    """Map each ordered slot to its index in the normalized (sorted) portfolio, by value."""

    tickets = _tickets(portfolio)
    engine = sorted(tickets)
    position = {ticket: index for index, ticket in enumerate(engine)}
    mapping = tuple(position[ticket] for ticket in tickets)
    if sorted(mapping) != list(range(TICKET_COUNT)):
        raise ValueError("ordered-to-engine slot map is not a permutation")
    for slot, ticket in enumerate(tickets):
        if engine[mapping[slot]] != ticket:
            raise ValueError("ordered-to-engine slot map fails the by-value check")
    return mapping


def engine_pair(o2e: Sequence[int], pair: SlotPair) -> SlotPair:
    a, b = sorted((o2e[pair[0]], o2e[pair[1]]))
    return (a, b)


def build_mapping(portfolio: Sequence[Sequence[int]]) -> list[dict[str, Any]]:
    """One row per ordered slot pair: its orbit representative, witness and engine pairs."""

    tickets = _tickets(portfolio)
    group = automorphism_group(tickets)
    o2e = ordered_to_engine_slots(tickets)
    orbit_of: dict[SlotPair, SlotPair] = {}
    for pair in all_slot_pairs():
        orbit_of[pair] = min(map_pair(element, pair) for element in group)
    representatives = sorted(set(orbit_of.values()))
    orbit_index = {rep: index for index, rep in enumerate(representatives)}
    orbit_size = {rep: sum(1 for r in orbit_of.values() if r == rep) for rep in representatives}
    rows: list[dict[str, Any]] = []
    for pair in all_slot_pairs():
        rep = orbit_of[pair]
        witness = next(element for element in group if map_pair(element, pair) == rep)
        rows.append(
            {
                "ORDERED_PAIR": list(pair),
                "ENGINE_PAIR": list(engine_pair(o2e, pair)),
                "CLASS": pair_class(tickets, pair),
                "ORBIT_INDEX": orbit_index[rep],
                "ORBIT_SIZE": orbit_size[rep],
                "IS_REPRESENTATIVE": pair == rep,
                "REPRESENTATIVE_ORDERED_PAIR": list(rep),
                "REPRESENTATIVE_ENGINE_PAIR": list(engine_pair(o2e, rep)),
                "WITNESS_SLOTS": list(witness.slots),
                "WITNESS_NUMBERS": list(witness.numbers),
            }
        )
    return rows


def mapping_sha256(rows: Sequence[dict[str, Any]]) -> str:
    """SHA-256 of the compact UTF-8 JSON rows (separators ',' and ':', key order as built)."""

    return compact_sha256(list(rows))


def validate_mapping(
    portfolio: Sequence[Sequence[int]],
    rows: Sequence[dict[str, Any]],
    group: Sequence[Automorphism],
    *,
    expected_representatives: int = EXPECTED_REPRESENTATIVES,
) -> list[dict[str, Any]]:
    """Re-check every row from first principles; return the representative rows.

    Raises ValueError on a missing, duplicated or ambiguous pair, a witness that is
    not an automorphism or does not carry the pair to its representative, a wrong
    ordered-to-engine translation, two representatives in one orbit, or a
    representative count other than ``expected_representatives``.
    """

    tickets = _tickets(portfolio)
    engine = sorted(tickets)
    o2e = ordered_to_engine_slots(tickets)
    for element in group:
        if not is_automorphism(tickets, element):
            raise ValueError("group contains a non-automorphism")
    _check_closure(group)

    seen: set[SlotPair] = set()
    representative_rows: dict[SlotPair, dict[str, Any]] = {}
    members: dict[SlotPair, set[SlotPair]] = {}
    for row in rows:
        a, b = row["ORDERED_PAIR"]
        pair: SlotPair = (a, b)
        if not 0 <= a < b < TICKET_COUNT:
            raise ValueError(f"invalid ordered pair {pair}")
        if pair in seen:
            raise ValueError(f"duplicate ordered pair {pair}")
        seen.add(pair)
        ra, rb = row["REPRESENTATIVE_ORDERED_PAIR"]
        rep: SlotPair = (ra, rb)
        if not 0 <= ra < rb < TICKET_COUNT:
            raise ValueError(f"invalid representative {rep}")
        witness = Automorphism(tuple(row["WITNESS_SLOTS"]), tuple(row["WITNESS_NUMBERS"]))
        if not is_automorphism(tickets, witness):
            raise ValueError(f"witness for {pair} is not an automorphism")
        if map_pair(witness, pair) != rep:
            raise ValueError(f"witness does not carry {pair} to {rep}")
        for slots, raw_engine_slots in (
            (pair, row["ENGINE_PAIR"]),
            (rep, row["REPRESENTATIVE_ENGINE_PAIR"]),
        ):
            engine_slots = [int(e) for e in raw_engine_slots]
            if list(engine_pair(o2e, slots)) != engine_slots:
                raise ValueError(f"engine translation mismatch for {slots}")
            if sorted(engine[e] for e in engine_slots) != sorted(tickets[s] for s in slots):
                raise ValueError(f"engine pair {engine_slots} differs by value from {slots}")
        if row["CLASS"] != pair_class(tickets, pair):
            raise ValueError(f"class label mismatch for {pair}")
        if row["IS_REPRESENTATIVE"] != (pair == rep):
            raise ValueError(f"representative flag mismatch for {pair}")
        members.setdefault(rep, set()).add(pair)
        if pair == rep:
            representative_rows[rep] = row

    if seen != set(all_slot_pairs()):
        raise ValueError(f"mapping covers {len(seen)} of {EXPECTED_RAW_SLOT_PAIRS} slot pairs")
    if set(members) != set(representative_rows):
        raise ValueError("a representative pair has no row of its own")
    for rep, orbit in members.items():
        group_orbit = {map_pair(element, rep) for element in group}
        if orbit != group_orbit:
            raise ValueError(f"orbit of {rep} is incomplete or split")
    for row in rows:
        rep_row = representative_rows[tuple(row["REPRESENTATIVE_ORDERED_PAIR"])]
        if row["ORBIT_INDEX"] != rep_row["ORBIT_INDEX"]:
            raise ValueError(f"orbit index mismatch for {row['ORDERED_PAIR']}")
        if row["ORBIT_SIZE"] != len(members[tuple(row["REPRESENTATIVE_ORDERED_PAIR"])]):
            raise ValueError(f"orbit size mismatch for {row['ORDERED_PAIR']}")
    if len({row["ORBIT_INDEX"] for row in representative_rows.values()}) != len(members):
        raise ValueError("two orbits share an orbit index")
    reps = sorted(representative_rows)
    if len(reps) != expected_representatives:
        raise ValueError(f"{len(reps)} representatives, expected {expected_representatives}")
    return [representative_rows[rep] for rep in reps]
