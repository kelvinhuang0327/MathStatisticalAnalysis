"""Structural certificate: every CELL_A solution at T = 270 has one overlap graph.

Scope. This module proves one statement, for one degree profile at one target: every solution of
the frozen CELL_A model (profile 55555555555511111100, T = 270) has overlap graph K12 disjoint
union (K8 minus one edge), so its triangle count is exactly 270. It fixes the overlap graph only.
It does not fix the F3 decomposition, does not count or bound exact wins, does not close CELL_A's
score and says nothing about the global K20 optimum. No solver is used.

The frozen model (read-only). The two-cell engine 40e88811 (base commit 03b5691f) searches CELL_A
with the census support model (census engine 479f3163, R28 ``support_union_model``) at the
open-wedge ceiling W - 3T. Its proto is pinned as 381ee9ef. The proof uses four constraint
families of that model and nothing else:

* ticket v lies on exactly d_v triple lines and 6 - d_v pair lines, with d_v fixed;
* two tickets share at most one line, and e(a, b) equals the number of lines holding both;
* every centre c and pair {a, b} has a 0/1 indicator o >= e(c,a) + e(c,b) - e(a,b) - 1;
* the indicators sum to at most W - 3T.

The overlap graph G of a solution joins two tickets that share a line, so e is its adjacency and
G is simple. A wedge is a centre with an unordered pair of its neighbours, open when the pair is
not adjacent. An open wedge forces its indicator to 1. An indicator may also be 1 on a closed
wedge, so the proof uses only O <= sum o <= W - 3T, never equality. The model's cut on
non-adjacent pairs, the engine's no-goods and its lex-leader rows only remove solutions; the
proof does not use them.

Proof.

* A. deg_G(v) = 2 d_v + (6 - d_v) = 6 + d_v, so G has degree sequence 11^12 7^6 6^2.
* B. W = sum C(deg, 2) = 12 * 55 + 6 * 21 + 2 * 15 = 816. A closed wedge lies in exactly one
  triangle and a triangle closes three wedges, so O = W - 3T in every simple graph. The model
  gives O <= 816 - 3 * 270 = 6.
* C. For an edge uv let x = |N(u) - N[v]| and y = |N(v) - N[u]|: the open wedges centred at u
  with end v, and centred at v with end u. Each open wedge is counted at both of its edges, so
  2O = sum (x + y). Both are at least 0 and x - y = deg u - deg v, so in every simple graph
  sum over edges |deg u - deg v| <= 2O.
* D. H holds the 12 tickets of degree 11 and U the other 8. A cross edge joins degree 11 to
  degree 7 or 6, so it adds at least 4 to the sum in C: 4m <= 2O <= 12, and m <= 3.
* E. sum over H of deg = 132 = 2 e(H) + m, so m is even: m = 0 or m = 2.
* F. m = 2 gives e(H) = 65 = C(12, 2) - 1, so G[H] = K12 - xy. Each of the other 10 tickets of H
  is adjacent to both x and y, so (z; x, y) is open for 10 centres z: O >= 10 > 6. So m = 0.
* G. With m = 0, G[H] is 11-regular on 12 vertices: K12. In G[U] the six degree-7 tickets are
  adjacent to every other ticket of U. Each degree-6 ticket is adjacent to those six and to
  nothing else, so G[U] = K8 - x'y' with x', y' the two tickets with d = 0. Hence
  T = C(12, 3) + C(8, 3) - 6 = 270 and O = 6. A simple graph with this degree sequence and
  T >= 270 has O <= 6, so it is this graph and T = 270: no such graph has T > 270.
* H. A line is a clique of G and no edge crosses H and U, so every line lies inside H or inside
  U. A ticket of H has d = 5, so it lies on five triple lines and one pair line. The pair lines
  inside H form a perfect matching F2 of six edges, and H holds 12 * 5 / 3 = 20 triple lines F3.
  Every pair of H lies on exactly one line, because G[H] = K12 and two tickets share at most one
  line. Add a point oo and the six triples {oo, a, b} for ab in F2. Then each pair of the 13
  points lies in exactly one of the 26 triples: an STS(13) whose blocks through oo are F2. No
  classification of STS(13) is used or claimed.

``derive`` carries out C-G in closed form on a degree sequence and a ceiling, and fails closed at
the first step that does not hold. ``structure_ledger`` checks every claim exactly on one
explicit structure. ``certificate`` records the derivation for CELL_A and its SHA-256 identity.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from math import comb

TASK_ID = "B649_CELL_A_OVERLAP_RIGIDITY_CERTIFICATE_R1"
PROFILE_ID = "55555555555511111100"
TARGET_T = 270
TICKET_COUNT = 20
TICKET_CAPACITY = 6
TRIPLE_LINES = 22
RIGID = "CELL_A_OVERLAP_GRAPH_RIGID_T270"

# Read-only authorities. Nothing here is imported; the tests check each pin against its bytes.
FROZEN_REFERENCES = {
    "BASE_COMMIT": "03b5691fac02c3a125c91cf4120b6219c3143b5e",
    "TWO_CELL_ENGINE_SHA256": "40e8881168512768257bdd03260008ea8e00b4fb8a56540536d76f35df307628",
    "CENSUS_ENGINE_SHA256": "479f3163659a91234d23637b697527224e947ae3268e49515cd609ca82ca6276",
    "CELL_A_MODEL_PROTO_SHA256": "381ee9ef753d6b1904fb7c5f8037a01eee0183f96963411e1eb56b303760fe89",
}

THEOREM = (
    "Every solution of the frozen CELL_A model (profile 55555555555511111100 at T = 270: ticket v "
    "on d_v triple lines and 6 - d_v pair lines, two tickets sharing at most one line, at most "
    "816 - 3 * 270 = 6 open wedges) has overlap graph K12 disjoint union (K8 minus the edge "
    "between its two d = 0 tickets), so exactly 270 triangles and 6 open wedges. Its pair lines "
    "inside the K12 are a perfect matching F2, and its 20 triple lines there together with "
    "{oo} + f for f in F2 form an STS(13)."
)
ASSUMPTIONS = (
    "each ticket v lies on exactly d_v triple lines and 6 - d_v pair lines, d_v fixed",
    "two tickets share at most one line and e(a, b) equals the number of lines holding both",
    "every centre c and pair {a, b} has a 0/1 indicator o >= e(c,a) + e(c,b) - e(a,b) - 1",
    "the indicators sum to at most W - 3T",
)
NOT_CLAIMED = {
    "F3_DECOMPOSITION": "NOT_FIXED",
    "STS13_CLASSIFICATION": "NOT_USED",
    "EXACT_WIN_COUNT": "NOT_COMPUTED",
    "CELL_A_SCORE_CLOSURE": "NOT_CLAIMED",
    "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
}

Graph = tuple[frozenset[int], ...]
Wedge = tuple[int, int, int]
Line = tuple[int, ...]
Pair = tuple[int, int]


class CertificateError(ValueError):
    """An input lies outside the theorem, or a proof step does not hold."""


def _pair(line: Line) -> Pair:
    a, b = line
    return a, b


def decode_profile(value: str) -> tuple[int, ...]:
    if len(value) != TICKET_COUNT or not value.isdecimal():
        raise CertificateError(f"malformed degree profile: {value!r}")
    profile = tuple(map(int, value))
    if (
        tuple(sorted(profile, reverse=True)) != profile
        or max(profile) > TICKET_CAPACITY
        or sum(profile) != 3 * TRIPLE_LINES
    ):
        raise CertificateError(f"not a minimum-S2 fiber degree profile: {value}")
    return profile


def overlap_degrees(profile: Sequence[int]) -> tuple[int, ...]:
    """A: ticket v meets 2 d_v tickets on its triple lines and 6 - d_v on its pair lines."""

    return tuple(TICKET_CAPACITY + d for d in profile)


# Simple graphs: the general counts of B and C ----------------------------------------------


def simple_graph(n: int, edges: Iterable[Pair]) -> Graph:
    """The adjacency of a simple graph on 0..n-1; CertificateError on a loop or a repeated edge."""

    adjacency: list[set[int]] = [set() for _ in range(n)]
    for a, b in edges:
        if a == b or not (0 <= a < n and 0 <= b < n):
            raise CertificateError(f"not a simple graph: bad edge {(a, b)!r}")
        if b in adjacency[a]:
            raise CertificateError(f"not a simple graph: repeated edge {(a, b)!r}")
        adjacency[a].add(b)
        adjacency[b].add(a)
    return tuple(frozenset(neighbours) for neighbours in adjacency)


def degrees(graph: Graph) -> tuple[int, ...]:
    return tuple(len(neighbours) for neighbours in graph)


def edge_list(graph: Graph) -> list[Pair]:
    return [(a, b) for a, neighbours in enumerate(graph) for b in sorted(neighbours) if b > a]


def wedge_total(graph: Graph) -> int:
    return sum(comb(len(neighbours), 2) for neighbours in graph)


def open_wedges(graph: Graph) -> frozenset[Wedge]:
    """Every (centre, a, b) with a < b both adjacent to the centre and not to each other."""

    return frozenset(
        (centre, a, b)
        for centre, neighbours in enumerate(graph)
        for a, b in combinations(sorted(neighbours), 2)
        if b not in graph[a]
    )


def triangle_count(graph: Graph) -> int:
    return sum(
        1
        for a, neighbours in enumerate(graph)
        for b in neighbours
        if b > a
        for c in neighbours & graph[b]
        if c > b
    )


def degree_gap_sum(graph: Graph) -> int:
    return sum(abs(len(graph[a]) - len(graph[b])) for a, b in edge_list(graph))


def split_edges(graph: Graph, part: frozenset[int]) -> tuple[int, int]:
    """(edges inside ``part``, edges with exactly one end in ``part``)."""

    inside = cross = 0
    for a, b in edge_list(graph):
        if a in part and b in part:
            inside += 1
        elif (a in part) != (b in part):
            cross += 1
    return inside, cross


@dataclass(frozen=True, slots=True)
class GraphLedger:
    wedges: int
    triangles: int
    open_wedges: int
    degree_gap_sum: int


def graph_ledger(graph: Graph) -> GraphLedger:
    """W, T and O by direct enumeration, with B's identity and C's edge split checked exactly."""

    opened = open_wedges(graph)
    wedges, triangles = wedge_total(graph), triangle_count(graph)
    if len(opened) != wedges - 3 * triangles:
        raise CertificateError("step B: open wedges differ from W - 3T")
    split = 0
    for u, v in edge_list(graph):
        x = len(graph[u] - graph[v] - {v})
        y = len(graph[v] - graph[u] - {u})
        if x - y != len(graph[u]) - len(graph[v]):
            raise CertificateError(f"step C: x - y differs from the degree gap on {(u, v)!r}")
        split += x + y
    if split != 2 * len(opened):
        raise CertificateError("step C: the edge split does not count each open wedge twice")
    gaps = degree_gap_sum(graph)
    if gaps > 2 * len(opened):
        raise CertificateError("step C: the degree gaps exceed 2O")
    return GraphLedger(wedges, triangles, len(opened), gaps)


# The closed-form derivation C-G ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Derivation:
    wedges: int
    ceiling: int
    top_degree: int
    top_count: int
    cross_gap: int
    cross_edge_bound: int
    cross_edge_candidates: tuple[int, ...]
    refuted: tuple[tuple[int, int], ...]
    other_count: int
    triangles: int
    open_wedges: int


def cross_edge_candidates(top_degree_sum: int, bound: int, top_count: int) -> tuple[int, ...]:
    """E: m <= bound with sum_H deg = 2 e(H) + m and 0 <= e(H) <= C(|H|, 2)."""

    return tuple(
        m
        for m in range(bound + 1)
        if (top_degree_sum - m) % 2 == 0 and 0 <= top_degree_sum - m <= 2 * comb(top_count, 2)
    )


def derive(degree_sequence: Sequence[int], ceiling: int) -> Derivation:
    """Steps C-G for a simple graph with this degree sequence and at most ``ceiling`` open wedges.

    Every step that does not hold for the given numbers raises CertificateError naming it.
    """

    sequence = sorted(degree_sequence, reverse=True)
    if not sequence or ceiling < 0 or sum(sequence) % 2:
        raise CertificateError("step B: no simple graph has this degree sequence and ceiling")
    wedges = sum(comb(d, 2) for d in sequence)
    top, h = sequence[0], sequence.count(sequence[0])
    rest = sequence[h:]
    if not rest:
        raise CertificateError("step D: every vertex has the top degree")
    gap = top - rest[0]
    bound = 2 * ceiling // gap
    if top != h - 1:
        raise CertificateError(f"step E: the top degree {top} is not |H| - 1 = {h - 1}")
    candidates = cross_edge_candidates(h * top, bound, h)
    refuted: list[tuple[int, int]] = []
    for m in candidates:
        if not m:
            continue
        # With top = |H| - 1, C(|H|, 2) - e(H) = m / 2 pairs of H are not adjacent.
        if m // 2 != 1:
            raise CertificateError(f"step F: m = {m} leaves {m // 2} non-edges in H; no bound")
        forced = h - 2
        if forced <= ceiling:
            raise CertificateError(
                f"step F: m = {m} forces {forced} open wedges, within the ceiling {ceiling}"
            )
        refuted.append((m, forced))
    # m = 0 is always a candidate here, since sum_H deg = |H| (|H| - 1) = 2 C(|H|, 2).
    u = len(rest)
    if rest != [u - 1] * (u - 2) + [u - 2] * 2:
        raise CertificateError("step G: G[U] is not forced to be K_u minus one edge")
    triangles = comb(h, 3) + comb(u, 3) - (u - 2)
    opened = u - 2
    if wedges - 3 * triangles != opened:
        raise CertificateError("step G: the forced graph contradicts O = W - 3T")
    if opened > ceiling:
        raise CertificateError(
            f"step G: the forced graph has {opened} open wedges, above the ceiling {ceiling}"
        )
    return Derivation(
        wedges=wedges,
        ceiling=ceiling,
        top_degree=top,
        top_count=h,
        cross_gap=gap,
        cross_edge_bound=bound,
        cross_edge_candidates=candidates,
        refuted=tuple(refuted),
        other_count=u,
        triangles=triangles,
        open_wedges=opened,
    )


@dataclass(frozen=True, slots=True)
class PointedExtension:
    triple_degree: int
    matching_edges: int
    triples: int
    points: int
    blocks: int


def pointed_extension(derivation: Derivation) -> PointedExtension:
    """H's counts: d = top - 6, |F2| = |H| / 2, |F3 on H| = |H| d / 3, and |H| + 1 points.

    That every pair lies in exactly one block is structural; ``structure_ledger`` checks it.
    """

    h, d = derivation.top_count, derivation.top_degree - TICKET_CAPACITY
    if TICKET_CAPACITY - d != 1 or h % 2:
        raise CertificateError("step H: the tickets of H do not each have one pair line")
    triples, matching = h * d // 3, h // 2
    return PointedExtension(d, matching, triples, h + 1, triples + matching)


# One explicit structure --------------------------------------------------------------------


def structure_graph(
    profile: Sequence[int], triples: Iterable[Line], pairs: Iterable[Line]
) -> Graph:
    """The overlap graph of a fiber structure; CertificateError unless it meets the premises."""

    n = len(profile)
    on_triples, on_pairs = Counter[int](), Counter[int]()
    edges: list[Pair] = []
    for size, lines, count in ((3, tuple(triples), on_triples), (2, tuple(pairs), on_pairs)):
        for line in lines:
            if len(line) != size or len(set(line)) != size or not all(0 <= v < n for v in line):
                raise CertificateError(f"malformed line {line!r}")
            count.update(line)
            edges += [(a, b) for a, b in combinations(sorted(line), 2)]
    for v, d in enumerate(profile):
        if on_triples[v] != d or on_pairs[v] != TICKET_CAPACITY - d:
            raise CertificateError(f"ticket {v} does not realize its degree")
    try:
        return simple_graph(n, edges)
    except CertificateError as error:
        raise CertificateError(f"two tickets share two lines: {error}") from error


@dataclass(frozen=True, slots=True)
class StructureLedger:
    wedges: int
    triangles: int
    open_wedges: int
    degree_gap_sum: int
    cross_edges: int
    missing_pair: Pair
    matching: tuple[Pair, ...]
    triples: tuple[Line, ...]
    blocks: int


def structure_ledger(triples: Iterable[Line], pairs: Iterable[Line]) -> StructureLedger:
    """Check A-H exactly on one CELL_A structure that the model's ceiling admits."""

    profile = decode_profile(PROFILE_ID)
    triples = tuple(tuple(sorted(t)) for t in triples)
    pairs = tuple(tuple(sorted(p)) for p in pairs)
    graph = structure_graph(profile, triples, pairs)
    if degrees(graph) != overlap_degrees(profile):
        raise CertificateError("step A: overlap degrees differ from 6 + d")
    ledger = graph_ledger(graph)
    ceiling = ledger.wedges - 3 * TARGET_T
    if ledger.open_wedges > ceiling:
        raise CertificateError(
            f"outside CELL_A: {ledger.open_wedges} open wedges exceed the ceiling {ceiling}"
        )
    top = max(degrees(graph))
    h = frozenset(v for v, d in enumerate(degrees(graph)) if d == top)
    u = frozenset(range(len(graph))) - h
    inside, m = split_edges(graph, h)
    if (top - max(len(graph[v]) for v in u)) * m > ledger.degree_gap_sum:
        raise CertificateError("step D: the cross edges exceed their share of the degree gaps")
    if 2 * inside + m != sum(len(graph[v]) for v in h):
        raise CertificateError("step E: sum_H deg differs from 2 e(H) + m")
    if m:
        raise CertificateError(f"step F: {m} edges cross H and U")
    if any(graph[v] != h - {v} for v in h):
        raise CertificateError("step G: G[H] is not complete")
    missing = [(a, b) for a, b in combinations(sorted(u), 2) if b not in graph[a]]
    if len(missing) != 1 or any(profile[v] for v in missing[0]):
        raise CertificateError("step G: G[U] is not K8 minus the edge between its d = 0 tickets")
    if ledger.triangles != TARGET_T:
        raise CertificateError(f"step G: {ledger.triangles} triangles, not {TARGET_T}")
    matching = tuple(_pair(p) for p in pairs if set(p) <= h)
    if sorted(v for p in matching for v in p) != sorted(h):
        raise CertificateError("step H: the pair lines inside H are not a perfect matching")
    inner = tuple(t for t in triples if set(t) <= h)
    point = len(graph)
    blocks = [*inner, *((a, b, point) for a, b in matching)]
    covered = Counter(p for block in blocks for p in combinations(block, 2))
    if set(covered) != set(combinations(sorted(h | {point}), 2)) or set(covered.values()) != {1}:
        raise CertificateError("step H: F3 on H with oo + F2 is not a Steiner triple system")
    return StructureLedger(
        wedges=ledger.wedges,
        triangles=ledger.triangles,
        open_wedges=ledger.open_wedges,
        degree_gap_sum=ledger.degree_gap_sum,
        cross_edges=m,
        missing_pair=missing[0],
        matching=matching,
        triples=inner,
        blocks=len(blocks),
    )


# The certificate ---------------------------------------------------------------------------


def _sequence_label(sequence: Sequence[int]) -> str:
    return " ".join(f"{d}^{k}" for d, k in sorted(Counter(sequence).items(), reverse=True))


def certificate(profile_id: str = PROFILE_ID, t: int = TARGET_T) -> dict[str, object]:
    """The derivation for CELL_A at T = 270, its verdict and its SHA-256 identity."""

    if (profile_id, t) != (PROFILE_ID, TARGET_T):
        raise CertificateError(
            f"this certificate covers only CELL_A {PROFILE_ID} at T = {TARGET_T}, "
            f"not {profile_id} at T = {t}"
        )
    profile = decode_profile(profile_id)
    sequence = overlap_degrees(profile)
    wedges = sum(comb(d, 2) for d in sequence)
    derivation = derive(sequence, wedges - 3 * t)
    extension = pointed_extension(derivation)
    record: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "PROFILE_ID": PROFILE_ID,
        "TARGET_T": TARGET_T,
        "THEOREM": THEOREM,
        "ASSUMPTIONS": list(ASSUMPTIONS),
        "FROZEN_REFERENCES": FROZEN_REFERENCES,
        "DEGREE_SEQUENCE": _sequence_label(sequence),
        "W": derivation.wedges,
        "OPEN_WEDGE_CEILING": derivation.ceiling,
        "H_SIZE": derivation.top_count,
        "CROSS_DEGREE_GAP": derivation.cross_gap,
        "CROSS_EDGE_BOUND": derivation.cross_edge_bound,
        "CROSS_EDGE_CANDIDATES": list(derivation.cross_edge_candidates),
        "REFUTED_CROSS_EDGES": {str(m): forced for m, forced in derivation.refuted},
        "CROSS_EDGES": 0,
        "OVERLAP_GRAPH": "K12 + (K8 - e), e joining the two d = 0 tickets",
        "TRIANGLES": derivation.triangles,
        "OPEN_WEDGES": derivation.open_wedges,
        "MAX_TRIANGLES_FOR_DEGREE_SEQUENCE": derivation.triangles,
        "H_TRIPLE_DEGREE": extension.triple_degree,
        "F2_MATCHING_EDGES": extension.matching_edges,
        "F3_TRIPLES_IN_H": extension.triples,
        "STS_POINTS": extension.points,
        "STS_BLOCKS": extension.blocks,
        "NOT_CLAIMED": NOT_CLAIMED,
        "SOLVER_USED": False,
        "VERDICT": RIGID,
    }
    body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return {**record, "CERTIFICATE_SHA256": hashlib.sha256(body).hexdigest()}


def verify_certificate(record: Mapping[str, object]) -> None:
    """Refuse a record that differs in any field from the re-derived certificate."""

    expected = certificate()
    differing = sorted(
        k for k in expected.keys() | record.keys() if record.get(k) != expected.get(k)
    )
    if differing:
        raise CertificateError(f"certificate differs from its derivation in {differing}")


def main() -> None:
    print(json.dumps(certificate(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
