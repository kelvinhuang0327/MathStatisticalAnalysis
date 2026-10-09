"""Closed-form certificate: the K20 fiber cell CELL_B cannot reach T = 266.

Scope. This module proves one statement, for one degree profile: every fiber support structure
with triple-degree profile 66665555555322000000 has at least 48 open wedges. The frozen CELL_B
model at T = 266 allows at most 33, so it is infeasible. Nothing here is claimed for any other
profile. No solver is used.

The frozen model (read-only). The two-cell engine d9977ccc (commit f1f4e377) solves CELL_B with
the census support model (census engine 479f3163, R28 ``support_union_model``); its CELL_B proto
is pinned as f2d5946a. That model has 20 tickets. Ticket v lies on d_v triple lines and 6 - d_v
pair lines. Triple lines use only tickets with d > 0, and two tickets share at most one line. The
overlap graph G joins two tickets that share a line, so deg_G(v) = 6 + d_v. A wedge is a centre
with an unordered pair of its neighbours. It is open when that pair is not adjacent. Each
triangle closes three wedges, so open = W - 3T with W = sum C(6 + d_v, 2) = 831. The model has one
indicator o >= e(c,a) + e(c,b) - e(a,b) - 1 for every centre c and pair {a, b}, and bounds their
sum by W - 3T = 33. A model solution is therefore a structure with at most 33 open wedges.

Notation. F holds the 4 tickets with d = 6, A the 14 with d > 0 and I the 6 with d = 0. m counts
the pair lines between A and I. For v in A, s_v = |N(v) & I| and g_v = |N(v) & A| = 6 + d_v - s_v.

* L1. f in F lies on six triple lines and no pair line. Its 12 neighbours all lie in A - {f},
  which has 13 tickets, so f has exactly one active non-neighbour u = u_f. f has no neighbour
  in I.
* L2. A ticket of I has six pair lines, and I holds at most C(6, 2) = 15 lines, so
  m = 36 - 2 e(I) >= 6.
* L3. O_f is the set of open wedges centred at f. N(f) = A - {f, u}, so
  |O_f| = C(12, 2) - (e(A) - 12 - g_u). Also 2 e(A) = sum_A g_v = sum_A (6 + d_v) - m = 150 - m.
  Hence |O_f| = 3 + m/2 + g_u.
* L4. Q_f is the set of open wedges whose ends are f and a ticket i in I. f and i share no line,
  and no ticket of F has a neighbour in I. So |Q_f| = sum_i |N(i) & (A - {f, u})| = m - s_u.
* Distinct. O_f is centred at f. A centre of Q_f has a neighbour in I, so it lies outside F. Two
  Q families differ in their ends. The eight families O_f, Q_f are pairwise disjoint, so no
  wedge is counted twice.
* Bound. |O_f| + |Q_f| = 9 + d_u + 3m/2 - 2 s_u. Since s_u <= 6 - d_u, this is at least
  3 d_u - 3 + 3m/2. With d_u >= 2 (u is active) and m >= 6, it is at least 12. So
  open >= 4 * 12 = 48 > 33, and T <= (831 - 48) / 3 = 261.

``structure_ledger`` checks L1-L4 and distinctness as exact equalities on one explicit structure.
Its capacity parameter exists only so that small, exhaustively enumerable structures can test
the same lemmas. ``certificate`` derives the bound from the profile alone and records it.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from itertools import combinations
from math import comb

TASK_ID = "B649_K20_CELL_B_T266_OPEN_WEDGE_CERTIFICATE_R1"
PROFILE_ID = "66665555555322000000"
TARGET_T = 266
TICKET_COUNT = 20
TICKET_CAPACITY = 6
INFEASIBLE = "CELL_B_T266_CLOSED_FORM_INFEASIBLE"
INCOMPLETE = "PROOF_INCOMPLETE"

# Read-only authorities. Nothing here is imported; the tests check each pin against its bytes.
FROZEN_REFERENCES = {
    "SYMMETRY_ENGINE_COMMIT": "f1f4e37719928ceff8020dca78eb1e90a2ed545e",
    "TWO_CELL_ENGINE_SHA256": "d9977ccc4dab599f10c2d8e29844ceca6f1141ba8e87828a015e63426081438c",
    "CENSUS_ENGINE_SHA256": "479f3163659a91234d23637b697527224e947ae3268e49515cd609ca82ca6276",
    "CELL_B_MODEL_PROTO_SHA256": "f2d5946a254086e26ea843da8b49f083947a2d6faf89ea85adad74f840a71600",
}
INCUMBENT_COUNT = 313_263_888

THEOREM = (
    "Every fiber support structure with triple-degree profile 66665555555322000000 (20 tickets, "
    "ticket v on d_v triple lines on degree-positive tickets and 6 - d_v pair lines, any two "
    "tickets sharing at most one line) has at least 48 open wedges in its overlap graph, hence at "
    "most 261 triangles. The frozen CELL_B model at T = 266 admits at most 33 open wedges, so it "
    "is infeasible."
)

Line = tuple[int, ...]
Wedge = tuple[int, int, int]
Adjacency = tuple[frozenset[int], ...]


class CertificateError(ValueError):
    """A structure or a derivation step contradicts the proof's premises or lemmas."""


def decode_profile(value: str) -> tuple[int, ...]:
    if len(value) != TICKET_COUNT or not value.isdecimal():
        raise CertificateError(f"malformed degree profile: {value!r}")
    profile = tuple(map(int, value))
    if tuple(sorted(profile, reverse=True)) != profile or max(profile) > TICKET_CAPACITY:
        raise CertificateError(f"not a non-increasing fiber degree profile: {value}")
    return profile


def wedge_count(profile: Sequence[int], capacity: int) -> int:
    """W = sum C(capacity + d, 2): ticket v has overlap degree capacity + d_v."""

    return sum(comb(capacity + d, 2) for d in profile)


# One explicit structure: its overlap graph and the proof's wedge families -------------------


def overlap_graph(
    profile: Sequence[int], capacity: int, triples: Iterable[Line], pairs: Iterable[Line]
) -> Adjacency:
    """The overlap graph of a fiber support structure; CertificateError unless it is one."""

    n = len(profile)
    triples, pairs = tuple(triples), tuple(pairs)
    on_triples, on_pairs = Counter[int](), Counter[int]()
    adjacency: list[set[int]] = [set() for _ in range(n)]
    for size, lines, count in ((3, triples, on_triples), (2, pairs, on_pairs)):
        for line in lines:
            if len(line) != size or len(set(line)) != size or not all(0 <= v < n for v in line):
                raise CertificateError(f"malformed line {line!r}")
            if size == 3 and not all(profile[v] for v in line):
                raise CertificateError(f"triple line {line!r} uses a degree-0 ticket")
            count.update(line)
            for a, b in combinations(line, 2):
                if b in adjacency[a]:
                    raise CertificateError(f"tickets {a} and {b} share two lines")
                adjacency[a].add(b)
                adjacency[b].add(a)
    for v in range(n):
        if on_triples[v] != profile[v] or on_pairs[v] != capacity - profile[v]:
            raise CertificateError(f"ticket {v} does not realize its degree")
    return tuple(frozenset(neighbours) for neighbours in adjacency)


def open_wedges(adjacency: Adjacency) -> frozenset[Wedge]:
    """Every (centre, a, b) with a < b both adjacent to the centre and not to each other."""

    return frozenset(
        (centre, a, b)
        for centre, neighbours in enumerate(adjacency)
        for a, b in combinations(sorted(neighbours), 2)
        if b not in adjacency[a]
    )


def triangle_count(adjacency: Adjacency) -> int:
    return sum(
        1
        for a, neighbours in enumerate(adjacency)
        for b in neighbours
        if b > a
        for c in neighbours & adjacency[b]
        if c > b
    )


def disjoint_union_size(families: Sequence[frozenset[Wedge]]) -> int:
    """The size of the union, after proving that no wedge lies in two families."""

    total = sum(len(family) for family in families)
    if len(frozenset[Wedge]().union(*families)) != total:
        raise CertificateError("two counted wedge families share a wedge")
    return total


@dataclass(frozen=True, slots=True)
class TicketLedger:
    full_ticket: int
    partner: int
    partner_degree: int
    partner_inactive_neighbours: int
    partner_active_neighbours: int
    centred: int
    ended: int


@dataclass(frozen=True, slots=True)
class StructureLedger:
    triangles: int
    open_wedges: int
    active_inactive_lines: int
    active_edges: int
    counted: int
    tickets: tuple[TicketLedger, ...]


def structure_ledger(
    profile: Sequence[int], capacity: int, triples: Iterable[Line], pairs: Iterable[Line]
) -> StructureLedger:
    """Count O_f and Q_f on one structure and check L1-L4 and distinctness exactly."""

    adjacency = overlap_graph(profile, capacity, triples, pairs)
    full = [v for v, d in enumerate(profile) if d == capacity]
    active = frozenset(v for v, d in enumerate(profile) if d)
    inactive = frozenset(v for v, d in enumerate(profile) if not d)
    if not full or len(active) != 2 * capacity + 2:
        raise CertificateError("L1 needs a full ticket and exactly 2 * capacity + 2 active ones")
    opened = open_wedges(adjacency)
    triangles = triangle_count(adjacency)
    if len(opened) != wedge_count(profile, capacity) - 3 * triangles:
        raise CertificateError("open wedges differ from W - 3T")
    m = sum(len(adjacency[v] & inactive) for v in active)
    if m < capacity * len(inactive) - 2 * comb(len(inactive), 2):
        raise CertificateError("L2: too few lines between active and inactive tickets")
    active_edges = sum(len(adjacency[v] & active) for v in active) // 2
    if 2 * active_edges != sum(capacity + profile[v] for v in active) - m:
        raise CertificateError("2 e(A) differs from sum_A (capacity + d) - m")
    tickets: list[TicketLedger] = []
    families: list[frozenset[Wedge]] = []
    for f in full:
        missing = sorted(active - adjacency[f] - {f})
        if len(adjacency[f]) != 2 * capacity or not adjacency[f] <= active or len(missing) != 1:
            raise CertificateError(f"L1: full ticket {f} lacks a unique active non-neighbour")
        u = missing[0]
        s_u = len(adjacency[u] & inactive)
        g_u = len(adjacency[u]) - s_u
        centred = frozenset(w for w in opened if w[0] == f)
        ended = frozenset(
            w for w in opened if f in w[1:] and (w[2] if w[1] == f else w[1]) in inactive
        )
        if len(centred) != comb(2 * capacity, 2) - active_edges + 2 * capacity + g_u:
            raise CertificateError(f"L3 fails at full ticket {f}")
        if len(ended) != m - s_u:
            raise CertificateError(f"L4 fails at full ticket {f}")
        families += [centred, ended]
        tickets.append(TicketLedger(f, u, profile[u], s_u, g_u, len(centred), len(ended)))
    counted = disjoint_union_size(families)
    return StructureLedger(triangles, len(opened), m, active_edges, counted, tuple(tickets))


# The closed-form bound for CELL_B ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Relaxation:
    """The per-full-ticket count |O_f| + |Q_f| over every value the lemmas leave open."""

    capacity: int
    full_tickets: int
    active_incidence: int
    partner_degrees: tuple[int, ...]
    m_min: int
    m_max: int

    def centred(self, d_u: int, s_u: int, m: int) -> int:
        """L3: C(2c, 2) - e(A) + 2c + g_u, with 2 e(A) = active_incidence - m."""

        c = self.capacity
        twice = 2 * comb(2 * c, 2) - (self.active_incidence - m) + 4 * c + 2 * (c + d_u - s_u)
        if twice % 2:
            raise CertificateError("e(A) must be an integer")
        return twice // 2

    def ended(self, s_u: int, m: int) -> int:
        """L4."""

        return m - s_u

    def domain(self) -> Iterator[tuple[int, int, int]]:
        """d_u is an active degree, 0 <= s_u <= c - d_u, and m_min <= m <= m_max has L2's parity."""

        for d_u in self.partner_degrees:
            for s_u in range(self.capacity - d_u + 1):
                for m in range(self.m_min, self.m_max + 1, 2):
                    yield d_u, s_u, m

    def per_ticket_minimum(self) -> int:
        return min(self.centred(d, s, m) + self.ended(s, m) for d, s, m in self.domain())

    def closed_form_minimum(self) -> int:
        """s_u = c - d_u, d_u = min, m = m_min: the count rises in d_u and m and falls in s_u."""

        c = self.capacity
        twice = 2 * comb(2 * c, 2) - self.active_incidence + 2 * c + 6 * min(self.partner_degrees)
        return (twice + 3 * self.m_min) // 2


def relaxation() -> Relaxation:
    """CELL_B's relaxation, derived from its profile."""

    profile, c = decode_profile(PROFILE_ID), TICKET_CAPACITY
    active = [d for d in profile if d]
    inactive = len(profile) - len(active)
    partners = Counter(active)
    partners[c] -= 1
    return Relaxation(
        capacity=c,
        full_tickets=profile.count(c),
        active_incidence=sum(c + d for d in active),
        partner_degrees=tuple(sorted(d for d, k in partners.items() if k > 0)),
        m_min=max(0, c * inactive - 2 * comb(inactive, 2)),
        m_max=sum(c - d for d in active),
    )


def decide(lower_bound: int, ceiling: int) -> str:
    """Infeasible only when every structure has more open wedges than the cell allows."""

    return INFEASIBLE if lower_bound > ceiling else INCOMPLETE


def certificate() -> dict[str, object]:
    """The derivation for CELL_B at T = 266, its verdict and its SHA-256 identity."""

    profile = decode_profile(PROFILE_ID)
    c = TICKET_CAPACITY
    relax = relaxation()
    active = sum(1 for d in profile if d)
    wedges = wedge_count(profile, c)
    ceiling = wedges - 3 * TARGET_T
    per_ticket = relax.per_ticket_minimum()
    lower = relax.full_tickets * per_ticket
    premises = active == 2 * c + 2 and per_ticket == relax.closed_form_minimum()
    record: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "PROFILE_ID": PROFILE_ID,
        "TARGET_T": TARGET_T,
        "THEOREM": THEOREM,
        "FROZEN_REFERENCES": FROZEN_REFERENCES,
        "INCUMBENT_COUNT": INCUMBENT_COUNT,
        "W": wedges,
        "OPEN_WEDGE_CEILING": ceiling,
        "FULL_TICKETS": relax.full_tickets,
        "ACTIVE_TICKETS": active,
        "INACTIVE_TICKETS": len(profile) - active,
        "ACTIVE_INCIDENCE": relax.active_incidence,
        "PARTNER_DEGREES": list(relax.partner_degrees),
        "M_MIN": relax.m_min,
        "M_MAX": relax.m_max,
        "PER_FULL_TICKET_MINIMUM": per_ticket,
        "CLOSED_FORM_MINIMUM": relax.closed_form_minimum(),
        "OPEN_WEDGE_LOWER_BOUND": lower,
        "MAX_TRIANGLES": (wedges - lower) // 3,
        "SOLVER_USED": False,
        "VERDICT": decide(lower, ceiling) if premises else INCOMPLETE,
    }
    body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return {**record, "CERTIFICATE_SHA256": hashlib.sha256(body).hexdigest()}


def main() -> None:
    print(json.dumps(certificate(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
