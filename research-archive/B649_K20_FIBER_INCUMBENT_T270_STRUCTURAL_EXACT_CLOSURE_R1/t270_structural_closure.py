"""B649 K20 Fiber cell 55555555555511111100 / T=270: structural exact closure (R1).

Every legal realization of the cell is shown to be number/ticket-isomorphic to a
member of the 26-candidate 12+8 overlap-block family (commit 82e88ada); the exact
OFFICIAL_ANY_PRIZE count of every isomorphism class is then freshly recounted with
the canonical evaluator. The written proof is stored in result.json; every step
is also checked mechanically on the concrete objects below.

    nice -n 15 <repo>/.venv/bin/python <task-root>/t270_structural_closure.py
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import itertools  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import resource  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from collections.abc import Sequence  # noqa: E402
from math import comb, factorial  # noqa: E402
from pathlib import Path  # noqa: E402
from types import ModuleType  # noqa: E402
from typing import Any  # noqa: E402

for _thread_var in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_thread_var] = "1"

TASK_ID = "B649_K20_FIBER_INCUMBENT_T270_STRUCTURAL_EXACT_CLOSURE_R1"
TASK_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TASK_ROOT.parents[1]
RESULT_PATH = TASK_ROOT / "result.json"

AUTHORITY_MAIN = "75d2b23aab23499af6e867ebd2e77136ec87a76a"
K20_COUNT = 313_263_888
PORTFOLIO_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
BASELINE_REL = (
    "docs/research/matrix-native-results/b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
)
BASELINE_FILE_SHA256 = "3d5d3f8f2389b66a9b2c45b0e345b81a0d9dc59d08ca9223519be70a055e5a00"
EVALUATOR_REL = "src/lottolab/research/b649_official_any_prize_exact.py"
EVALUATOR_SHA256 = "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
SOURCE_WORKTREE = Path(
    "/Users/kelvin/.codex/worktrees/b649-k20-overlap-block-repartition-12-8-exhaustive-r1/"
    "MathStatisticalAnalysis"
)
OLD_FAMILY_COMMIT = "82e88ada111bf6d0999ac9c0c167a160a6ae5df8"
GENERATOR_REL = "src/lottolab/research/b649_k20_overlap_block_repartition_12_8_exhaustive_r1.py"
GENERATOR_SHA256 = "852c210bcf3b1916c4dad74ca44847eade5c71269e985644724dbc17e1192daa"
OLD_RESULT_REL = (
    "docs/research/matrix-native-results/"
    "b649-k20-overlap-block-repartition-12-8-exhaustive-r1-result.json"
)
OLD_RESULT_SHA256 = "0d948aa4556e9493e0c55d9fb8436c7b0aaaa9f2744bb9ecf85f16405c23cc1c"

PROFILE = "55555555555511111100"
CELL_T = 270
TICKETS = 20
TICKET_SIZE = 6
POOL = 49
TRIPLE_LABELS = 22
PAIR_LABELS = 27
STS_POINTS = 13
INF = 12  # local index of the point added to the twelve degree-11 tickets
CPU_LIMIT_SECONDS = 300
TARGET_NICE = 15

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type Block = tuple[int, int, int]


class StructuralGap(Exception):
    """A realization violates a step of the structural proof."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StructuralGap(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def portfolio_sha256(portfolio: Sequence[Sequence[int]]) -> str:
    payload = json.dumps([list(ticket) for ticket in portfolio], separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))


def git_blob(repo: Path, commit: str, rel: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{rel}"], check=True, capture_output=True
    ).stdout


def git_text(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


# ---------------------------------------------------------------- overlap graph


def holders(portfolio: Portfolio) -> dict[int, tuple[int, ...]]:
    owners: dict[int, list[int]] = {}
    for index, ticket in enumerate(portfolio):
        for number in ticket:
            owners.setdefault(number, []).append(index)
    return {number: tuple(indices) for number, indices in sorted(owners.items())}


def overlap_adjacency(portfolio: Portfolio) -> list[int]:
    sets = [set(ticket) for ticket in portfolio]
    adjacency = [0] * len(portfolio)
    for left, right in itertools.combinations(range(len(portfolio)), 2):
        if sets[left] & sets[right]:
            adjacency[left] |= 1 << right
            adjacency[right] |= 1 << left
    return adjacency


def _adjacent(adjacency: list[int], left: int, right: int) -> bool:
    return bool((adjacency[left] >> right) & 1)


def triangle_count(adjacency: list[int]) -> int:
    return sum(
        1
        for a, b, c in itertools.combinations(range(len(adjacency)), 3)
        if _adjacent(adjacency, a, b) and _adjacent(adjacency, a, c) and _adjacent(adjacency, b, c)
    )


def wedge_count(adjacency: list[int]) -> int:
    return sum(comb(row.bit_count(), 2) for row in adjacency)


def open_wedge_count_direct(adjacency: list[int]) -> int:
    """Count paths x-c-y with x, y non-adjacent, directly."""

    total = 0
    for row in adjacency:
        neighbours = [v for v in range(len(adjacency)) if (row >> v) & 1]
        total += sum(
            1 for x, y in itertools.combinations(neighbours, 2) if not _adjacent(adjacency, x, y)
        )
    return total


def edge_open_wedge_sum(adjacency: list[int]) -> int:
    """sum over edges uv of deg(u)+deg(v)-2-2|N(u)&N(v)| (each term counts open wedges on uv)."""

    degree = [row.bit_count() for row in adjacency]
    return sum(
        degree[u] + degree[v] - 2 - 2 * (adjacency[u] & adjacency[v]).bit_count()
        for u, v in itertools.combinations(range(len(adjacency)), 2)
        if _adjacent(adjacency, u, v)
    )


def cell_membership(portfolio: Portfolio) -> dict[str, Any]:
    """Exact cell domain: legality, support, overlap<=1, triple-degree profile, all-triangle T."""

    legal = (
        len(portfolio) == TICKETS
        and len({frozenset(ticket) for ticket in portfolio}) == TICKETS
        and all(
            len(ticket) == TICKET_SIZE
            and len(set(ticket)) == TICKET_SIZE
            and all(type(number) is int and 1 <= number <= POOL for number in ticket)
            for ticket in portfolio
        )
    )
    frequency = Counter(number for ticket in portfolio for number in ticket)
    triple_numbers = sum(frequency[number] == 3 for number in range(1, POOL + 1))
    pair_numbers = sum(frequency[number] == 2 for number in range(1, POOL + 1))
    support_ok = (
        all(frequency[number] in (2, 3) for number in range(1, POOL + 1))
        and triple_numbers == TRIPLE_LABELS
        and pair_numbers == PAIR_LABELS
    )
    max_overlap = max(
        len(set(left) & set(right)) for left, right in itertools.combinations(portfolio, 2)
    )
    triple_degrees = [sum(frequency[number] == 3 for number in ticket) for ticket in portfolio]
    profile = "".join(str(d) for d in sorted(triple_degrees, reverse=True))
    adjacency = overlap_adjacency(portfolio)
    triangles = triangle_count(adjacency)
    return {
        "LEGAL_DISTINCT_TICKETS": legal,
        "SUPPORT_22_TRIPLE_27_PAIR": support_ok,
        "MAX_PAIRWISE_OVERLAP": max_overlap,
        "TRIPLE_DEGREE_PROFILE": profile,
        "OVERLAP_GRAPH_TRIANGLES": triangles,
        "IN_CELL": legal
        and support_ok
        and max_overlap <= 1
        and profile == PROFILE
        and triangles == CELL_T,
    }


# ---------------------------------------------------------------- Phase 1


def phase1_general_proof() -> dict[str, Any]:
    """Arithmetic of the Phase-1 proof; valid for every graph of the cell (not per instance)."""

    triple_degree = [int(char) for char in PROFILE]
    # deg(v) = sum over the six numbers of v of (frequency - 1) = 2 t(v) + (6 - t(v)).
    degrees = [TICKET_SIZE + t for t in triple_degree]
    if degrees != [11] * 12 + [7] * 6 + [6] * 2:
        raise StructuralGap("degree sequence is not 11^12 7^6 6^2")
    edges = sum(degrees) // 2
    wedges = sum(comb(d, 2) for d in degrees)
    open_wedges = wedges - 3 * CELL_T
    high = degrees[:12]
    low = degrees[12:]
    # H-L edge uv: u-side term >= (11-1) - (deg(v)-1) >= 11 - max(low); v-side term >= 0.
    per_hl_edge_lower_bound = high[0] - max(low)
    c_upper = (2 * open_wedges) // per_hl_edge_lower_bound
    h_degree_sum = sum(high)
    c_feasible = [
        c
        for c in range(c_upper + 1)
        if (h_degree_sum - c) % 2 == 0 and (h_degree_sum - c) // 2 <= comb(12, 2)
    ]
    c2_edges_in_h = (h_degree_sum - 2) // 2
    c2_missing_pairs_in_h = comb(12, 2) - c2_edges_in_h
    c2_forced_open_wedges = 12 - 2  # each other H vertex is the centre of x-z-y
    c0_edges_in_h = h_degree_sum // 2
    c0_edges_in_l = sum(low) // 2
    k12_triangles = comb(12, 3)
    k8_minus_e_triangles = comb(8, 3) - (8 - 2)
    k8_minus_e_open_wedges = 8 - 2
    checks = {
        "EDGES_EQUAL_LABEL_EDGES": edges == 3 * TRIPLE_LABELS + PAIR_LABELS == 93,
        "W_EQUALS_816": wedges == 816,
        "O_EQUALS_6": open_wedges == 6,
        "HL_EDGE_TERM_AT_LEAST_4": per_hl_edge_lower_bound == 4,
        "C_AT_MOST_3": c_upper == 3,
        "C_IN_0_OR_2": c_feasible == [0, 2],
        "C2_EXCLUDED": c2_missing_pairs_in_h == 1 and c2_forced_open_wedges > open_wedges,
        "C0_H_IS_K12": c0_edges_in_h == comb(12, 2),
        "C0_L_IS_K8_MINUS_E": c0_edges_in_l == comb(8, 2) - 1,
        "T_CONSISTENT_270": k12_triangles + k8_minus_e_triangles == CELL_T,
        "O_CONSISTENT_6": 0 + k8_minus_e_open_wedges == open_wedges,
    }
    if not all(checks.values()):
        raise StructuralGap(f"Phase-1 arithmetic failed: {checks}")
    return {
        "GRAPH_DEGREES": "11^12, 7^6, 6^2",
        "EDGES": edges,
        "W": wedges,
        "THREE_T": 3 * CELL_T,
        "OPEN_WEDGES_O": open_wedges,
        "EDGE_SUM_EQUALS_2O": 2 * open_wedges,
        "HL_EDGE_TERM_LOWER_BOUND": per_hl_edge_lower_bound,
        "C_UPPER_FROM_4C_LE_2O": c_upper,
        "H_DEGREE_SUM": h_degree_sum,
        "C_FEASIBLE_AFTER_PARITY": c_feasible,
        "C2_EDGES_IN_H": c2_edges_in_h,
        "C2_FORCED_OPEN_WEDGES": c2_forced_open_wedges,
        "C0_EDGES_IN_H": c0_edges_in_h,
        "C0_EDGES_IN_L": c0_edges_in_l,
        "T_DECOMPOSITION": {"K12": k12_triangles, "K8_MINUS_E": k8_minus_e_triangles},
        "CHECKS": checks,
        "RESULT": "G = K12 disjoint-union (K8 - e), e joining the two degree-6 tickets",
    }


def phase1_instance_check(portfolio: Portfolio) -> dict[str, Any]:
    adjacency = overlap_adjacency(portfolio)
    degree = [row.bit_count() for row in adjacency]
    high = [v for v in range(TICKETS) if degree[v] == 11]
    low = [v for v in range(TICKETS) if degree[v] != 11]
    c = sum(_adjacent(adjacency, u, v) for u in high for v in low)
    open_direct = open_wedge_count_direct(adjacency)
    return {
        "DEGREE_SEQUENCE": sorted(degree, reverse=True) == [11] * 12 + [7] * 6 + [6] * 2,
        "W": wedge_count(adjacency),
        "T": triangle_count(adjacency),
        "O_DIRECT": open_direct,
        "EDGE_SUM": edge_open_wedge_sum(adjacency),
        "EDGE_SUM_EQUALS_2O": edge_open_wedge_sum(adjacency) == 2 * open_direct,
        "C_HL_EDGES": c,
    }


# ---------------------------------------------------------------- Phase 2


def is_sts(blocks: Sequence[Sequence[int]], points: int) -> bool:
    if len(blocks) != comb(points, 2) // 3:
        return False
    pairs = Counter(
        frozenset(pair) for block in blocks for pair in itertools.combinations(block, 2)
    )
    return (
        all(len(set(block)) == 3 and all(0 <= p < points for p in block) for block in blocks)
        and len(pairs) == comb(points, 2)
        and all(count == 1 for count in pairs.values())
    )


def decompose(portfolio: Portfolio) -> dict[str, Any]:
    """Check every Phase-1/Phase-2 claim on one realization and return its pointed STS(13)."""

    cell = cell_membership(portfolio)
    _require(cell["IN_CELL"], f"not a cell realization: {cell}")
    owner = holders(portfolio)
    adjacency = overlap_adjacency(portfolio)
    degree = [row.bit_count() for row in adjacency]
    frequency = {number: len(tickets) for number, tickets in owner.items()}
    triple_degree = [sum(frequency[n] == 3 for n in ticket) for ticket in portfolio]
    _require(
        all(degree[v] == TICKET_SIZE + triple_degree[v] for v in range(TICKETS)),
        "deg(v) != 6 + t(v)",
    )
    high = [v for v in range(TICKETS) if degree[v] == 11]
    low = [v for v in range(TICKETS) if degree[v] != 11]
    _require(len(high) == 12, "H does not have 12 tickets")
    high_set = set(high)
    _require(not any(_adjacent(adjacency, u, v) for u in high for v in low), "c = e(H, L) != 0")
    _require(
        all(_adjacent(adjacency, u, v) for u, v in itertools.combinations(high, 2)),
        "H is not K12",
    )
    six = [v for v in low if degree[v] == 6]
    seven = [v for v in low if degree[v] == 7]
    _require(len(six) == 2 and len(seven) == 6, "L degrees are not 7^6 6^2")
    l_non_edges = [
        (u, v) for u, v in itertools.combinations(low, 2) if not _adjacent(adjacency, u, v)
    ]
    _require(l_non_edges == [tuple(six)], "L is not K8 - e with e on the degree-6 pair")

    local = {ticket: index for index, ticket in enumerate(high)}
    h_triples: list[Block] = []
    h_pairs: list[tuple[int, int]] = []
    l_triples: list[tuple[int, ...]] = []
    l_pairs: list[tuple[int, ...]] = []
    for tickets in owner.values():
        in_h = all(t in high_set for t in tickets)
        in_l = not any(t in high_set for t in tickets)
        _require(in_h or in_l, "a label straddles H and L")
        if in_h:
            members = sorted(local[t] for t in tickets)
            if len(members) == 3:
                h_triples.append((members[0], members[1], members[2]))
            else:
                h_pairs.append((members[0], members[1]))
        elif len(tickets) == 3:
            l_triples.append(tuple(sorted(tickets)))
        else:
            l_pairs.append(tuple(sorted(tickets)))
    _require(len(h_triples) == 20 and len(h_pairs) == 6, "H labels are not 20 triples + 6 pairs")
    _require(
        sorted(p for pair in h_pairs for p in pair) == list(range(12)),
        "H pair labels are not a perfect matching",
    )
    blocks = tuple(sorted(h_triples + [(a, b, INF) for a, b in h_pairs]))
    _require(is_sts(blocks, STS_POINTS), "H plus the new point is not an STS(13)")

    _require(len(l_triples) == 2, "L does not have exactly two triple labels")
    _require(
        set(l_triples[0]).isdisjoint(l_triples[1])
        and set(l_triples[0]) | set(l_triples[1]) == set(seven),
        "L triple labels do not partition the six degree-7 tickets",
    )
    triangle_edges = {
        frozenset(edge) for triple in l_triples for edge in itertools.combinations(triple, 2)
    }
    forced_pair_edges = (
        {frozenset(edge) for edge in itertools.combinations(low, 2)}
        - {frozenset(six)}
        - triangle_edges
    )
    _require(
        len(l_pairs) == 21 and {frozenset(pair) for pair in l_pairs} == forced_pair_edges,
        "L pair labels are not the 21 forced edges",
    )
    return {
        "high": high,
        "low_degree6": six,
        "low_triples": sorted(l_triples),
        "sts_blocks": blocks,
        "owner": owner,
    }


# ---------------------------------------------------------------- STS(13) tools


def completion_table(blocks: Sequence[Sequence[int]], points: int) -> list[list[int]]:
    table = [[-1] * points for _ in range(points)]
    for block in blocks:
        for a, b in itertools.permutations(block, 2):
            table[a][b] = next(p for p in block if p != a and p != b)
    return table


def sts_isomorphisms(
    left: Sequence[Block],
    right: Sequence[Block],
    points: int,
    *,
    fixed: dict[int, int] | None = None,
    first_only: bool = False,
) -> list[tuple[int, ...]]:
    """All block-preserving point bijections left -> right (optionally with fixed images)."""

    if len(left) != len(right):
        return []
    left_table = completion_table(left, points)
    right_table = completion_table(right, points)
    right_blocks = {tuple(sorted(block)) for block in right}
    found: list[tuple[int, ...]] = []

    def propagate(mapping: list[int], inverse: list[int]) -> bool:
        changed = True
        while changed:
            changed = False
            mapped = [p for p in range(points) if mapping[p] >= 0]
            for a, b in itertools.combinations(mapped, 2):
                third = left_table[a][b]
                image = right_table[mapping[a]][mapping[b]]
                if mapping[third] < 0:
                    if inverse[image] >= 0:
                        return False
                    mapping[third] = image
                    inverse[image] = third
                    changed = True
                elif mapping[third] != image:
                    return False
        return True

    def search(mapping: list[int], inverse: list[int]) -> None:
        if not propagate(mapping, inverse):
            return
        free = [p for p in range(points) if mapping[p] < 0]
        if not free:
            if {tuple(sorted(mapping[p] for p in block)) for block in left} == right_blocks:
                found.append(tuple(mapping))
            return
        for image in range(points):
            if inverse[image] < 0:
                next_mapping, next_inverse = mapping.copy(), inverse.copy()
                next_mapping[free[0]] = image
                next_inverse[image] = free[0]
                search(next_mapping, next_inverse)
                if first_only and found:
                    return

    mapping, inverse = [-1] * points, [-1] * points
    for source, image in (fixed or {}).items():
        if mapping[source] >= 0 or inverse[image] >= 0:
            return []
        mapping[source] = image
        inverse[image] = source
    search(mapping, inverse)
    return found


def point_orbits(automorphisms: Sequence[Sequence[int]], points: int) -> list[list[int]]:
    orbits: list[list[int]] = []
    seen: set[int] = set()
    for p in range(points):
        if p not in seen:
            orbit = sorted({g[p] for g in automorphisms})
            seen.update(orbit)
            orbits.append(orbit)
    return orbits


def count_sts_with_fixed_point0_matching(points: int) -> int:
    """Labeled STS(points) on 0..points-1 that contain the blocks {0, 2i-1, 2i}."""

    if points % 6 not in (1, 3):
        raise ValueError("no STS of this order")
    uncovered = [0] * points
    for i in range(1, points):
        for j in range(1, points):
            if i != j:
                uncovered[i] |= 1 << j
    for i in range(1, points, 2):
        uncovered[i] &= ~(1 << (i + 1))
        uncovered[i + 1] &= ~(1 << i)

    def search() -> int:
        for i in range(1, points):
            row = uncovered[i]
            if row:
                break
        else:
            return 1
        j_bit = row & -row
        j = j_bit.bit_length() - 1
        i_bit = 1 << i
        candidates = row & uncovered[j]
        total = 0
        while candidates:
            k_bit = candidates & -candidates
            candidates ^= k_bit
            k = k_bit.bit_length() - 1
            uncovered[i] ^= j_bit | k_bit
            uncovered[j] ^= i_bit | k_bit
            uncovered[k] ^= i_bit | j_bit
            total += search()
            uncovered[i] ^= j_bit | k_bit
            uncovered[j] ^= i_bit | k_bit
            uncovered[k] ^= i_bit | j_bit
        return total

    return search()


def perfect_matchings(points: int) -> int:
    return factorial(points) // (2 ** (points // 2) * factorial(points // 2))


def relabel_blocks(
    blocks: Sequence[Sequence[int]], permutation: Sequence[int]
) -> tuple[Block, ...]:
    relabelled: list[Block] = []
    for block in blocks:
        a, b, c = sorted(permutation[p] for p in block)
        relabelled.append((a, b, c))
    return tuple(sorted(relabelled))


# ---------------------------------------------------------------- portfolio isomorphism


def portfolio_isomorphism(source: Portfolio, target: Portfolio) -> dict[str, list[int]] | None:
    """Explicit (ticket bijection, number permutation) with sigma(source) == target, or None.

    The ticket map is built from an isomorphism of pointed STS(13)s (infinity fixed) on H
    and from the unique L structure; the number map is then forced by ticket sets and the
    whole certificate is verified ticket by ticket.
    """

    src, dst = decompose(source), decompose(target)
    phis = sts_isomorphisms(
        src["sts_blocks"], dst["sts_blocks"], STS_POINTS, fixed={INF: INF}, first_only=True
    )
    if not phis:
        return None
    phi = phis[0]
    ticket_map = [-1] * TICKETS
    for local_index, ticket in enumerate(src["high"]):
        ticket_map[ticket] = dst["high"][phi[local_index]]
    for source_ticket, target_ticket in zip(src["low_degree6"], dst["low_degree6"], strict=True):
        ticket_map[source_ticket] = target_ticket
    for source_triple, target_triple in zip(src["low_triples"], dst["low_triples"], strict=True):
        for source_ticket, target_ticket in zip(source_triple, target_triple, strict=True):
            ticket_map[source_ticket] = target_ticket
    _require(sorted(ticket_map) == list(range(TICKETS)), "ticket map is not a bijection")
    number_by_tickets = {frozenset(tickets): number for number, tickets in dst["owner"].items()}
    number_map: dict[int, int] = {}
    for number, tickets in src["owner"].items():
        image = number_by_tickets.get(frozenset(ticket_map[t] for t in tickets))
        _require(image is not None, f"label {number} has no image")
        number_map[number] = image  # type: ignore[assignment]
    _require(
        sorted(number_map) == list(range(1, POOL + 1))
        and sorted(number_map.values()) == list(range(1, POOL + 1)),
        "number map is not a permutation of 1..49",
    )
    for index, ticket in enumerate(source):
        _require(
            sorted(number_map[n] for n in ticket) == sorted(target[ticket_map[index]]),
            "certificate does not map the source ticket onto the target ticket",
        )
    return {
        "TICKET_MAP": ticket_map,
        "NUMBER_MAP": [number_map[n] for n in range(1, POOL + 1)],
    }


def verify_certificate(
    source: Portfolio, target: Portfolio, certificate: dict[str, list[int]]
) -> bool:
    """Independent check: sigma maps ticket i of source onto ticket pi(i) of target."""

    ticket_map, number_map = certificate["TICKET_MAP"], certificate["NUMBER_MAP"]
    return (
        sorted(ticket_map) == list(range(len(source))) == list(range(len(target)))
        and sorted(number_map) == list(range(1, POOL + 1))
        and all(
            sorted(number_map[n - 1] for n in ticket) == sorted(target[ticket_map[i]])
            for i, ticket in enumerate(source)
        )
    )


def classify(portfolio: Portfolio, reps: dict[str, tuple[Block, ...]]) -> tuple[str, int]:
    """(STS class, point q) such that the pointed STS of the realization is iso to (rep, q)."""

    blocks = decompose(portfolio)["sts_blocks"]
    matches: list[tuple[str, int]] = []
    for name, rep in reps.items():
        phis = sts_isomorphisms(blocks, rep, STS_POINTS, first_only=True)
        if phis:
            matches.append((name, phis[0][INF]))
    _require(len(matches) == 1, f"STS(13) of the realization matches {len(matches)} classes")
    return matches[0]


# ---------------------------------------------------------------- authority


class AuthorityMismatch(Exception):
    """A pinned hash, path, or identity does not match."""


def _authority(condition: bool, message: str) -> None:
    if not condition:
        raise AuthorityMismatch(message)


def load_authority() -> dict[str, Any]:
    baseline_blob = git_blob(REPO_ROOT, AUTHORITY_MAIN, BASELINE_REL)
    _authority(sha256_bytes(baseline_blob) == BASELINE_FILE_SHA256, "baseline file SHA")
    baseline = json.loads(baseline_blob)
    start = tuple(tuple(ticket) for ticket in baseline["SEARCH_START_TICKETS"])
    _authority(portfolio_sha256(start) == PORTFOLIO_SHA256, "baseline portfolio SHA")
    evaluator_blob = git_blob(REPO_ROOT, AUTHORITY_MAIN, EVALUATOR_REL)
    _authority(sha256_bytes(evaluator_blob) == EVALUATOR_SHA256, "evaluator SHA at authority")
    generator_blob = git_blob(SOURCE_WORKTREE, OLD_FAMILY_COMMIT, GENERATOR_REL)
    _authority(sha256_bytes(generator_blob) == GENERATOR_SHA256, "generator SHA at old commit")
    old_blob = git_blob(SOURCE_WORKTREE, OLD_FAMILY_COMMIT, OLD_RESULT_REL)
    _authority(sha256_bytes(old_blob) == OLD_RESULT_SHA256, "old family result SHA")
    old_record = json.loads(old_blob)
    origin_main = git_text(REPO_ROOT, "rev-parse", "origin/main")
    return {
        "baseline_tickets": start,
        "old_record": old_record,
        "record": {
            "AUTHORITY_MAIN": AUTHORITY_MAIN,
            "LOCAL_ORIGIN_MAIN_REF": origin_main,
            "AUTHORITY_MAIN_EQUALS_LOCAL_ORIGIN_MAIN": origin_main == AUTHORITY_MAIN,
            "BASELINE_RESULT": BASELINE_REL,
            "BASELINE_FILE_SHA256_AT_AUTHORITY": sha256_bytes(baseline_blob),
            "BASELINE_PORTFOLIO_FIELD": "SEARCH_START_TICKETS",
            "BASELINE_PORTFOLIO_SHA256": portfolio_sha256(start),
            "BASELINE_RECORDED_START_COUNT": baseline.get("START_COUNT"),
            "BASELINE_RECORDED_FINAL_COUNT": baseline.get("FINAL_COUNT"),
            "EVALUATOR_SHA256_AT_AUTHORITY": sha256_bytes(evaluator_blob),
            "OLD_FAMILY_COMMIT": OLD_FAMILY_COMMIT,
            "GENERATOR_SHA256_AT_OLD_COMMIT": sha256_bytes(generator_blob),
            "OLD_RESULT_SHA256_AT_OLD_COMMIT": sha256_bytes(old_blob),
        },
    }


def import_evaluator() -> ModuleType:
    src = str(REPO_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import lottolab
    import lottolab.research.b649_official_any_prize_exact as evaluator

    _authority(
        Path(lottolab.__file__).resolve() == (REPO_ROOT / "src/lottolab/__init__.py").resolve(),
        f"lottolab resolved to {lottolab.__file__}",
    )
    path = Path(evaluator.__file__).resolve()
    _authority(path == (REPO_ROOT / EVALUATOR_REL).resolve(), f"evaluator resolved to {path}")
    _authority(sha256_bytes(path.read_bytes()) == EVALUATOR_SHA256, "imported evaluator SHA")
    return evaluator


def import_generator(evaluator: ModuleType) -> ModuleType:
    path = SOURCE_WORKTREE / GENERATOR_REL
    _authority(sha256_bytes(path.read_bytes()) == GENERATOR_SHA256, "on-disk generator SHA")
    spec = importlib.util.spec_from_file_location("b649_old_family_generator_82e88ada", path)
    _authority(spec is not None and spec.loader is not None, "generator import spec")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _authority(
        module.evaluate_portfolio is evaluator.evaluate_portfolio,
        "generator is not bound to the pinned evaluator",
    )
    return module


# ---------------------------------------------------------------- classification and family


def sts13_classification(generator: ModuleType) -> dict[str, Any]:
    classes = generator.build_sts13_classes()
    reps: dict[str, tuple[Block, ...]] = {
        "CYCLIC": tuple(classes.cyclic),
        "NONCYCLIC": tuple(classes.noncyclic),
    }
    info: dict[str, Any] = {}
    orbits: dict[str, list[list[int]]] = {}
    for name, rep in reps.items():
        automorphisms = sts_isomorphisms(rep, rep, STS_POINTS)
        orbits[name] = point_orbits(automorphisms, STS_POINTS)
        info[name] = {
            "BLOCKS": json.dumps([list(block) for block in rep], separators=(",", ":")),
            "VALID_STS13_GENERATOR_CHECK": bool(generator.is_valid_sts13(rep)),
            "VALID_STS13_INDEPENDENT_CHECK": is_sts(rep, STS_POINTS),
            "PASCH_COUNT": int(generator.pasch_count(rep)),
            "AUTOMORPHISM_GROUP_ORDER": len(automorphisms),
            "POINT_ORBITS": orbits[name],
        }
    cross = sts_isomorphisms(reps["CYCLIC"], reps["NONCYCLIC"], STS_POINTS, first_only=True)
    nonisomorphic = (
        not cross
        and not generator.sts13_are_isomorphic(reps["CYCLIC"], reps["NONCYCLIC"])
        and info["CYCLIC"]["PASCH_COUNT"] != info["NONCYCLIC"]["PASCH_COUNT"]
    )
    started = time.process_time()
    fixed_matching_completions = count_sts_with_fixed_point0_matching(STS_POINTS)
    mass_cpu = time.process_time() - started
    labeled_total = fixed_matching_completions * perfect_matchings(STS_POINTS - 1)
    class_mass = {
        name: factorial(STS_POINTS) // info[name]["AUTOMORPHISM_GROUP_ORDER"] for name in reps
    }
    mass_ok = all(
        factorial(STS_POINTS) % info[name]["AUTOMORPHISM_GROUP_ORDER"] == 0 for name in reps
    ) and labeled_total == sum(class_mass.values())
    valid = all(
        info[name]["VALID_STS13_GENERATOR_CHECK"] and info[name]["VALID_STS13_INDEPENDENT_CHECK"]
        for name in reps
    )
    return {
        "reps": reps,
        "orbits": orbits,
        "record": {
            "LITERATURE_AUTHORITY": (
                "Heinlein and Ostergard, Enumerating Steiner Triple Systems, arXiv:2303.01207: "
                "STS(13) has exactly two isomorphism classes (classification completeness)."
            ),
            "GENERATOR_REPRESENTATIVES": info,
            "GENERATOR_REPRESENTATIVES_VALID": valid,
            "GENERATOR_REPRESENTATIVES_NONISOMORPHIC": nonisomorphic,
            "NONISOMORPHISM_EVIDENCE": (
                "Pasch counts 13 vs 8 (an isomorphism invariant); exhaustive point-map search "
                "finds no isomorphism; generator sts13_are_isomorphic agrees"
            ),
            "INDEPENDENT_MASS_FORMULA_CHECK": {
                "METHOD": (
                    "Count labeled STS(13) on 0..12 containing the fixed blocks {0,2i-1,2i}; "
                    "Sym({1..12}) acts transitively on the 10395 perfect matchings at point 0, "
                    "so |labeled STS(13)| = 10395 * completions. Equality with "
                    "13!/|Aut(CYCLIC)| + 13!/|Aut(NONCYCLIC)| leaves no room for a third class."
                ),
                "FIXED_MATCHING_COMPLETIONS": fixed_matching_completions,
                "PERFECT_MATCHINGS_OF_12": perfect_matchings(STS_POINTS - 1),
                "LABELED_STS13_TOTAL": labeled_total,
                "CLASS_MASS": class_mass,
                "CLASS_MASS_SUM": sum(class_mass.values()),
                "STATUS": "PASS" if mass_ok else "FAIL",
                "CPU_SECONDS": round(mass_cpu, 3),
            },
            "STATUS": (
                "COMPLETE_TWO_CLASSES_LITERATURE_AND_INDEPENDENT_MASS_CHECK"
                if valid and nonisomorphic and mass_ok
                else "FAIL"
            ),
        },
        "ok": valid and nonisomorphic and mass_ok,
    }


EXPECTED_GENERATOR_INVARIANTS = {
    "TICKET_COUNT": 20,
    "LEGAL_DISTINCT_TICKETS": True,
    "FREQUENCY_PROFILE": {"2": 27, "3": 22},
    "ALL_NUMBER_FREQUENCIES_ARE_2_OR_3": True,
    "PAIRWISE_OVERLAP_HISTOGRAM": {"0": 97, "1": 93},
    "MAXIMUM_PAIRWISE_OVERLAP": 1,
}


def _orbit_of(orbits: list[list[int]], point: int) -> list[int]:
    return next(orbit for orbit in orbits if point in orbit)


def family_coverage(
    generator: ModuleType,
    classification: dict[str, Any],
    old_record: dict[str, Any],
    baseline: Portfolio,
) -> dict[str, Any]:
    reps = classification["reps"]
    orbits = classification["orbits"]
    candidates = generator.build_family_candidates()
    rows = {(row["STS_CLASS"], row["DELETED_POINT"]): row for row in old_record["CANDIDATE_COUNTS"]}
    family = {
        (c.sts_class, c.deleted_point): tuple(tuple(t) for t in c.tickets) for c in candidates
    }
    identities_ok = (
        set(family) == {(name, p) for name in reps for p in range(STS_POINTS)} == set(rows)
        and len(candidates) == 26
    )

    baseline_class, baseline_q = classify(baseline, reps)
    baseline_key = (baseline_class, min(_orbit_of(orbits[baseline_class], baseline_q)))
    class_rows: dict[tuple[str, int], dict[str, Any]] = {}
    for name in reps:
        for orbit in orbits[name]:
            key = (name, min(orbit))
            is_baseline = key == baseline_key
            class_rows[key] = {
                "CLASS_ID": f"{name}/orbit{min(orbit)}",
                "STS_CLASS": name,
                "DELETED_POINT_ORBIT": orbit,
                "RECOUNT_TARGET": (
                    "BASELINE_SEARCH_START_TICKETS"
                    if is_baseline
                    else f"FAMILY_CANDIDATE {name}/{min(orbit)}"
                ),
                "portfolio": baseline if is_baseline else family[key],
                "OLD_TABLE_COUNTS": sorted(
                    {rows[(name, p)]["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"] for p in orbit}
                ),
            }
            target = class_rows[key]["portfolio"]
            class_rows[key]["RECOUNT_TARGET_SHA256"] = portfolio_sha256(target)

    members: list[dict[str, Any]] = []
    for (name, point), tickets in sorted(family.items()):
        row = rows[(name, point)]
        cell = cell_membership(tickets)
        instance = phase1_instance_check(tickets)
        found_class, q = classify(tickets, reps)
        key = (name, min(_orbit_of(orbits[name], point)))
        certificate = portfolio_isomorphism(tickets, class_rows[key]["portfolio"])
        members.append(
            {
                "STS_CLASS": name,
                "DELETED_POINT": point,
                "PORTFOLIO_SHA256": portfolio_sha256(tickets),
                "SHA_MATCHES_OLD_ROW": portfolio_sha256(tickets) == row["PORTFOLIO_SHA256"],
                "GENERATOR_INVARIANTS_PASS": generator.structural_invariants(tickets)
                == EXPECTED_GENERATOR_INVARIANTS,
                "IN_CELL": cell["IN_CELL"],
                "PHASE1_INSTANCE": instance["DEGREE_SEQUENCE"]
                and instance["T"] == CELL_T
                and instance["O_DIRECT"] == 6
                and instance["EDGE_SUM_EQUALS_2O"]
                and instance["C_HL_EDGES"] == 0,
                "CLASSIFIED_AS": f"{found_class}/q={q}",
                "CLASSIFICATION_CONSISTENT": found_class == name
                and q in _orbit_of(orbits[name], point),
                "ISO_CLASS": class_rows[key]["CLASS_ID"],
                "OLD_TABLE_COUNT": row["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"],
                "CERTIFICATE_VERIFIED": certificate is not None
                and verify_certificate(tickets, class_rows[key]["portfolio"], certificate),
                "CERTIFICATE_TO_CLASS_TARGET": None
                if certificate is None
                else {k: json.dumps(v, separators=(",", ":")) for k, v in certificate.items()},
            }
        )
    member_checks = [
        "SHA_MATCHES_OLD_ROW",
        "GENERATOR_INVARIANTS_PASS",
        "IN_CELL",
        "PHASE1_INSTANCE",
        "CLASSIFICATION_CONSISTENT",
        "CERTIFICATE_VERIFIED",
    ]
    members_ok = all(all(m[check] for check in member_checks) for m in members)
    baseline_member = family[("NONCYCLIC", 5)]
    baseline_identity = sorted(baseline) == sorted(baseline_member)
    old_best_identity = old_record["BEST_PORTFOLIO"] == [list(t) for t in baseline_member]
    targets = [row["portfolio"] for row in class_rows.values()]
    classes_distinct = all(
        portfolio_isomorphism(left, right) is None
        for left, right in itertools.combinations(targets, 2)
    )
    return {
        "family": family,
        "class_rows": class_rows,
        "baseline_key": baseline_key,
        "ok": identities_ok
        and members_ok
        and baseline_identity
        and old_best_identity
        and classes_distinct,
        "record": {
            "FAMILY_IDENTITIES_COMPLETE_2x13": identities_ok,
            "OLD_RESULT_ROWS": len(rows),
            "OLD_RESULT_UNIQUE_SHA256_COUNT": old_record.get("CANDIDATES_UNIQUE_SHA256_COUNT"),
            "BASELINE_CELL_MEMBERSHIP": cell_membership(baseline),
            "BASELINE_CLASSIFIED_AS": f"{baseline_class}/q={baseline_q}",
            "BASELINE_ISO_CLASS": class_rows[baseline_key]["CLASS_ID"],
            "BASELINE_EQUALS_NONCYCLIC_5_TICKET_MULTISET": baseline_identity,
            "OLD_BEST_PORTFOLIO_EQUALS_NONCYCLIC_5": old_best_identity,
            "ISOMORPHISM_CLASS_COUNT": len(class_rows),
            "CLASS_TARGETS_PAIRWISE_NONISOMORPHIC": classes_distinct,
            "MEMBERS": members,
            "ALL_MEMBER_CHECKS_PASS": members_ok,
        },
    }


# ---------------------------------------------------------------- focused checks


def build_realization(blocks: Sequence[Block], deleted: int, rng: random.Random) -> Portfolio:
    """A cell realization built from (STS(13), deleted point) with random labels and order."""

    labels = list(range(1, POOL + 1))
    rng.shuffle(labels)
    supply = iter(labels)
    high: dict[int, list[int]] = {p: [] for p in range(STS_POINTS) if p != deleted}
    for block in blocks:
        number = next(supply)
        for p in block:
            if p != deleted:
                high[p].append(number)
    low: list[list[int]] = [[] for _ in range(8)]  # 0-2 triple A, 3-5 triple B, 6-7 degree six
    for triple in ((0, 1, 2), (3, 4, 5)):
        number = next(supply)
        for v in triple:
            low[v].append(number)
    for u, v in itertools.combinations(range(8), 2):
        if (u, v) == (6, 7) or (v < 3) or (3 <= u and v < 6):
            continue
        number = next(supply)
        low[u].append(number)
        low[v].append(number)
    _require(next(supply, None) is None, "realization did not use all 49 labels")
    tickets = [tuple(sorted(t)) for t in [*high.values(), *low]]
    rng.shuffle(tickets)
    return tuple(tickets)


def focused_checks(
    classification: dict[str, Any],
    family: dict[tuple[str, int], Portfolio],
    baseline: Portfolio,
    *,
    trials: int = 24,
    seed: int = 20261009,
) -> dict[str, Any]:
    reps = classification["reps"]
    orbits = classification["orbits"]
    rng = random.Random(seed)
    graph_rng = random.Random(seed + 1)

    edge_identity_ok = True
    for _ in range(60):
        n = graph_rng.randrange(4, 14)
        adjacency = [0] * n
        for u, v in itertools.combinations(range(n), 2):
            if graph_rng.random() < graph_rng.choice((0.3, 0.5, 0.8)):
                adjacency[u] |= 1 << v
                adjacency[v] |= 1 << u
        open_direct = open_wedge_count_direct(adjacency)
        edge_identity_ok &= edge_open_wedge_sum(adjacency) == 2 * open_direct
        edge_identity_ok &= open_direct == wedge_count(adjacency) - 3 * triangle_count(adjacency)

    fano = tuple(sorted({tuple(sorted((p + s) % 7 for p in (0, 1, 3))) for s in range(7)}))
    ag23 = tuple(
        sorted(
            (a, b, c)
            for a, b, c in itertools.combinations(range(9), 3)
            if (a // 3 + b // 3 + c // 3) % 3 == 0 and (a % 3 + b % 3 + c % 3) % 3 == 0
        )
    )
    small_cases = {
        "AUT_FANO_168": len(sts_isomorphisms(fano, fano, 7)) == 168,  # type: ignore[arg-type]
        "AUT_AG23_432": len(sts_isomorphisms(ag23, ag23, 9)) == 432,
        "STS7_FIXED_MATCHING_2": count_sts_with_fixed_point0_matching(7) == 2,
        "STS9_FIXED_MATCHING_8": count_sts_with_fixed_point0_matching(9) == 8,
    }

    random_ok = 0
    for _ in range(trials):
        name = rng.choice(sorted(reps))
        permutation = list(range(STS_POINTS))
        rng.shuffle(permutation)
        deleted = rng.randrange(STS_POINTS)
        realization = build_realization(relabel_blocks(reps[name], permutation), deleted, rng)
        found_class, q = classify(realization, reps)
        expected_orbit = _orbit_of(orbits[name], permutation.index(deleted))
        certificate = portfolio_isomorphism(realization, family[(found_class, q)])
        random_ok += int(
            cell_membership(realization)["IN_CELL"]
            and found_class == name
            and q in expected_orbit
            and certificate is not None
        )
    relabel_ok = 0
    for _ in range(trials):
        sigma = list(range(1, POOL + 1))
        rng.shuffle(sigma)
        relabelled = [tuple(sorted(sigma[n - 1] for n in ticket)) for ticket in baseline]
        rng.shuffle(relabelled)
        found_class, q = classify(tuple(relabelled), reps)
        relabel_ok += int(
            found_class == "NONCYCLIC"
            and q in _orbit_of(orbits["NONCYCLIC"], 5)
            and portfolio_isomorphism(tuple(relabelled), baseline) is not None
        )

    broken = [list(ticket) for ticket in baseline]
    spare = next(n for n in broken[1] if n not in broken[0])
    broken[0][broken[0].index(max(broken[0]))] = spare
    broken_portfolio = tuple(tuple(sorted(t)) for t in broken)
    try:
        decompose(broken_portfolio)
        negative_rejected = False
    except StructuralGap:
        negative_rejected = not cell_membership(broken_portfolio)["IN_CELL"]

    checks = {
        "EDGE_IDENTITY_RANDOM_GRAPHS_60": edge_identity_ok,
        **small_cases,
        "RANDOM_POINTED_STS_REALIZATIONS_MAPPED": f"{random_ok}/{trials}",
        "RANDOM_SIGMA49_BASELINE_RELABELS_MAPPED": f"{relabel_ok}/{trials}",
        "NON_CELL_PORTFOLIO_REJECTED": negative_rejected,
    }
    ok = (
        edge_identity_ok
        and all(small_cases.values())
        and random_ok == trials
        and relabel_ok == trials
        and negative_rejected
    )
    return {"ok": ok, "record": {**checks, "SEED": seed, "STATUS": "PASS" if ok else "FAIL"}}


# ---------------------------------------------------------------- proof text

PROOF: dict[str, str] = {
    "L0_DEGREE": (
        "22*3 + 27*2 = 120 = 20*6 and 22 + 27 = 49, so every number of 1..49 has frequency "
        "exactly 2 or 3. Overlap <= 1 means distinct numbers of a ticket v reach disjoint "
        "neighbour sets, so deg(v) = sum_{x in v}(f(x)-1) = 2t(v) + (6-t(v)) = 6 + t(v). "
        "Profile 5^12 1^6 0^2 gives degrees 11^12, 7^6, 6^2 and |E| = 93 = 3*22 + 27."
    ),
    "P1_S1_WEDGES": (
        "W = sum C(deg,2) = 12*55 + 6*21 + 2*15 = 816. T counts all triangles of G; each "
        "closes exactly 3 wedges and each closed wedge lies in exactly one triangle, so "
        "O = W - 3T = 816 - 810 = 6."
    ),
    "P1_S2_EDGE_IDENTITY": (
        "For an edge uv the open wedges with arm uv are: centre u, other end w in N(u)-{v}, "
        "w not in N(v), numbering (deg u - 1) - |N(u)&N(v)| because N(u)&N(v) is a subset of "
        "N(u)-{v}; symmetrically for centre v. An open wedge has exactly two arms, so "
        "sum_{uv in E}[deg u + deg v - 2 - 2|N(u)&N(v)|] = 2O = 12 with every summand >= 0."
    ),
    "P1_S3_HL_BOUND": (
        "H = the 12 degree-11 tickets, L = the other 8, c = e(H,L). For an edge uv, u in H, "
        "v in L: N(u)&N(v) is a subset of N(v)-{u}, so |N(u)&N(v)| <= deg v - 1 <= 6 and the "
        "u-side term is >= 10 - 6 = 4; the v-side term is >= 0. Dropping the other "
        "(nonnegative) summands: 4c <= 12, so c <= 3."
    ),
    "P1_S4_PARITY": "sum_{u in H} deg u = 132 = 2e(H) + c, so c is even: c in {0, 2}.",
    "P1_S5_C_EQUALS_2_EXCLUDED": (
        "c = 2 gives e(H) = 65 = C(12,2) - 1: exactly one pair x,y in H is non-adjacent and "
        "each of the other 10 H tickets is adjacent to both, giving 10 distinct open wedges "
        "x-z-y. O >= 10 > 6, a contradiction."
    ),
    "P1_S6_RESULT": (
        "c = 0: e(H) = 66, G[H] = K12; G[L] has degree sum 54, e(L) = 27 = C(8,2) - 1, so "
        "G[L] = K8 - e where e joins the two degree-6 tickets (the only L vertices below 7). "
        "Consistency: T = 220 + (56 - 6) = 270, O = 0 + 6 = 6. G = K12 disjoint-union (K8 - e)."
    ),
    "P2_S1_LABEL_SIDES": (
        "Tickets sharing a number are adjacent and c = 0, so every label lies wholly in H or in "
        "L. An H ticket (t = 5) carries 5 triple labels and 1 pair label, all inside H: "
        "12*5/3 = 20 triple supports and 12/2 = 6 pair supports. L carries 6*1/3 = 2 triple and "
        "(6*5 + 2*6)/2 = 21 pair labels (totals 22 and 27)."
    ),
    "P2_S2_MATCHING": (
        "Each H ticket lies in exactly one H pair label, so the 6 pair labels partition the 12 "
        "H tickets: a perfect matching."
    ),
    "P2_S3_STS13": (
        "G[H] = K12 with overlap <= 1, so any two H tickets share exactly one label: a linear "
        "space on the 12 H tickets with 20 lines of size 3 and 6 of size 2. Adding a new point "
        "inf to the 6 pair lines covers every pair of the 13 points exactly once with 26 "
        "triples: an STS(13) S with distinguished point inf. Conversely the H part (tickets, "
        "labels, incidences) is recovered from (S, inf) by deleting inf. H tickets use only H "
        "labels (5 + 1 = 6 numbers)."
    ),
    "P2_S4_L_UNIQUE": (
        "The 2 L triple labels contain only t >= 1 tickets, i.e. the six degree-7 tickets, each "
        "exactly once: two disjoint triples A, B partitioning them; the degree-6 tickets a, b "
        "carry none. Every edge of G[L] is realized by exactly one label; A and B take the 6 "
        "triangle edges, so the 21 pair labels are exactly the remaining 27 - 6 = 21 edges of "
        "K8 - ab. The L incidence structure is determined by (A, B, {a, b}) and any two choices "
        "are related by a ticket bijection: unique up to isomorphism (generator "
        "FIXED_EIGHT_TICKETS)."
    ),
    "P2_S5_INVARIANCE": (
        "OFFICIAL_ANY_PRIZE wins on (D, s), s not in D, iff some ticket t has |t&D| >= 3, or "
        "|t&D| = 2 and s in t. For sigma in Sym(1..49), (D, s) -> (sigma D, sigma s) is a "
        "bijection of the outcome space with |sigma t & sigma D| = |t&D| and sigma s in sigma t "
        "iff s in t, so count(sigma P) = count(P). Success is a union over tickets, so ticket "
        "order and relabelling are irrelevant. Portfolio SHA is not invariant and is not used "
        "as an identity."
    ),
    "P2_S6_COVERAGE": (
        "All 49 numbers are used, each in >= 2 tickets, and distinct numbers have distinct "
        "ticket sets (overlap <= 1); so a realization P is determined up to Sym(49) by its "
        "ticket-label incidence structure, which is (H part) + (L part) on disjoint labels. "
        "By P2_S3-S4 its isomorphism type is fixed by the pointed STS(13) (S, inf). By the "
        "classification S is isomorphic via some phi to a generator representative R_i "
        "(CYCLIC or NONCYCLIC), hence (S, inf) ~ (R_i, q) with q = phi(inf), and the generator "
        "candidate (R_i, q) has pointed STS isomorphic to (R_i, q). Therefore P = sigma(C) "
        "for a ticket bijection and sigma in Sym(49) with C a family member, and "
        "count(P) = count(C). The family takes all 13 deletion points of both representatives, "
        "so it covers every isomorphism type of the cell (in fact one per Aut(R_i)-orbit)."
    ),
    "P3_ACCOUNTING": (
        "Each family member carries an explicit verified (ticket map, number map) certificate "
        "onto its class recount target; each class target is freshly recounted with the "
        "pinned canonical evaluator, so every realization's exact count equals one recounted "
        "class count, and the cell maximum is the maximum over classes."
    ),
}


# ---------------------------------------------------------------- run


def fresh_recounts(
    evaluator: ModuleType, class_rows: dict[tuple[str, int], dict[str, Any]]
) -> None:
    draws = evaluator.all_main_draw_masks(POOL, TICKET_SIZE)
    for row in class_rows.values():
        started = time.process_time()
        result = evaluator.evaluate_portfolio(row["portfolio"], draws=draws)
        row["FRESH_CANONICAL_COUNT"] = int(result.official_any_prize_outcome_count)
        row["M3_PLUS_DRAW_COUNT"] = int(result.m3_plus_draw_count)
        row["RECOUNT_CPU_SECONDS"] = round(time.process_time() - started, 3)
        row["OLD_TABLE_MATCHES_FRESH"] = row["OLD_TABLE_COUNTS"] == [row["FRESH_CANONICAL_COUNT"]]


def _usage() -> dict[str, Any]:
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "CPU_SECONDS_SELF": round(own.ru_utime + own.ru_stime, 3),
        "CPU_SECONDS_CHILDREN": round(children.ru_utime + children.ru_stime, 3),
        "PEAK_RSS_BYTES": int(own.ru_maxrss),  # bytes on darwin
    }


def run(phase: str, trials: int) -> dict[str, Any]:
    started_wall = time.time()
    record: dict[str, Any] = {"TASK_ID": TASK_ID, "SCHEMA_VERSION": f"{TASK_ID}_V1"}
    unproved: list[str] = []
    try:
        authority = load_authority()
        record["CANONICAL_BASELINE"] = authority["record"]
        evaluator = import_evaluator()
        generator = import_generator(evaluator)
        baseline: Portfolio = authority["baseline_tickets"]
        record["EXACT_CELL_DOMAIN"] = {
            "TICKETS": TICKETS,
            "TICKET_SIZE": TICKET_SIZE,
            "POOL": "1..49",
            "SUPPORT": {"TRIPLE_LABELS": TRIPLE_LABELS, "PAIR_LABELS": PAIR_LABELS},
            "MAX_PAIRWISE_OVERLAP": 1,
            "TRIPLE_DEGREE_PROFILE": PROFILE,
            "OVERLAP_GRAPH_TRIANGLES_T_ALL_TRIANGLES": CELL_T,
        }
        phase1 = phase1_general_proof()
        classification = sts13_classification(generator)
        coverage = family_coverage(generator, classification, authority["old_record"], baseline)
        focused = focused_checks(classification, coverage["family"], baseline, trials=trials)
        record["STRUCTURAL_COMPLETENESS_PROOF"] = {
            "PROOF": PROOF,
            "PHASE1_ARITHMETIC": phase1,
            "PHASE1_PHASE2_CHECKED_ON_BASELINE": phase1_instance_check(baseline),
            "STATUS": "PROVED" if coverage["ok"] else "UNPROVED",
        }
        record["STS13_CLASSIFICATION_STATUS"] = classification["record"]
        record["REPRESENTATIVE_COVERAGE"] = coverage["record"]
        record["FOCUSED_CHECKS"] = focused["record"]
        if not classification["ok"]:
            unproved.append("STS13 representative validity / non-isomorphism / mass check failed")
        if not coverage["ok"]:
            unproved.append("family coverage or member certificate check failed")
        if not focused["ok"]:
            unproved.append("focused checks failed")
        if phase == "full":
            fresh_recounts(evaluator, coverage["class_rows"])
        rows = []
        for row in coverage["class_rows"].values():
            rows.append({k: v for k, v in row.items() if k != "portfolio"})
        counts = [r.get("FRESH_CANONICAL_COUNT") for r in rows]
        if phase == "full":
            cell_max = max(counts)
            baseline_row = coverage["class_rows"][coverage["baseline_key"]]
            old_match = all(r["OLD_TABLE_MATCHES_FRESH"] for r in rows)
            strict_gain = cell_max > K20_COUNT
            record["EXACT_SCORE_ACCOUNTING"] = {
                "CANONICAL_EVALUATOR": EVALUATOR_REL,
                "EVALUATION_FIELD": "official_any_prize_outcome_count",
                "ISOMORPHISM_CLASSES": rows,
                "FRESH_CANONICAL_RECOUNTS": len(rows),
                "BASELINE_FRESH_COUNT": baseline_row["FRESH_CANONICAL_COUNT"],
                "BASELINE_EQUALS_K20_COUNT": baseline_row["FRESH_CANONICAL_COUNT"] == K20_COUNT,
                "OLD_26_ROW_TABLE_CONSISTENT_WITH_FRESH": old_match,
                "MAX_ATTAINED_BY": [
                    r["CLASS_ID"] for r in rows if r["FRESH_CANONICAL_COUNT"] == cell_max
                ],
            }
            if baseline_row["FRESH_CANONICAL_COUNT"] != K20_COUNT or not old_match:
                unproved.append("EXACT_SCORE_MISMATCH")
            record["EXACT_CELL_MAX"] = cell_max
            record["ADMISSIBLE_CELL_UPPER_BOUND"] = cell_max
            record["STRICT_GAIN"] = (
                "YES_REQUIRES_INDEPENDENT_FRESH_RECOUNT" if strict_gain else "NO"
            )
            if strict_gain:
                record["TASK_STATUS"] = "COUNTEREXAMPLE_CANDIDATE_REQUIRES_FRESH_RECOUNT"
            elif not unproved and cell_max == K20_COUNT:
                record["TASK_STATUS"] = "PROVED_NO_STRICT_GAIN_WITHIN_DEFINED_PROFILE_T270_CELL"
            elif "EXACT_SCORE_MISMATCH" in unproved:
                record["TASK_STATUS"] = "EXACT_SCORE_MISMATCH"
            else:
                record["TASK_STATUS"] = "UNPROVED"
        else:
            record["TASK_STATUS"] = "STRUCTURE_PHASE_ONLY"
    except StructuralGap as gap:
        unproved.append(f"StructuralGap: {gap}")
        record["TASK_STATUS"] = "UNPROVED"
    except AuthorityMismatch as mismatch:
        unproved.append(f"AuthorityMismatch: {mismatch}")
        record["TASK_STATUS"] = "IMPLEMENTATION_OR_EXECUTION_DEFECT"
    record["UNPROVED_ITEMS"] = unproved
    record["GLOBAL_MIN_S2_FAMILY_STATUS"] = "NOT_CLOSED_BY_THIS_TASK"
    record["DEPENDENCY_SHA256"] = {
        "SCRIPT": sha256_bytes(Path(__file__).read_bytes()),
        "EVALUATOR": EVALUATOR_SHA256,
        "GENERATOR": GENERATOR_SHA256,
        "OLD_FAMILY_RESULT": OLD_RESULT_SHA256,
        "BASELINE_RESULT_FILE": BASELINE_FILE_SHA256,
        "BASELINE_PORTFOLIO": PORTFOLIO_SHA256,
    }
    record["RESOURCE"] = {
        **_usage(),
        "WALL_SECONDS": round(time.time() - started_wall, 3),
        "NICE": os.nice(0),
        "SCIENTIFIC_WORKERS": 1,
        "NUMERICAL_THREADS": 1,
        "CPU_RLIMIT_SECONDS": resource.getrlimit(resource.RLIMIT_CPU)[0],
        "FIBER_LOCKS_TOUCHED": "NONE",
    }
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("structure", "full"), default="full")
    parser.add_argument("--trials", type=int, default=24)
    args = parser.parse_args(argv)
    _, hard = resource.getrlimit(resource.RLIMIT_CPU)
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, hard))
    current = os.nice(0)
    if current < TARGET_NICE:
        os.nice(TARGET_NICE - current)
    record = run(args.phase, args.trials)
    if args.phase == "full":
        payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
        RESULT_PATH.write_text(payload, encoding="utf-8")
    summary_keys = (
        "TASK_STATUS",
        "EXACT_CELL_MAX",
        "ADMISSIBLE_CELL_UPPER_BOUND",
        "STRICT_GAIN",
        "UNPROVED_ITEMS",
        "RESOURCE",
    )
    print(json.dumps({k: record.get(k) for k in summary_keys}, indent=2, sort_keys=True))
    return (
        0
        if record["TASK_STATUS"]
        in (
            "PROVED_NO_STRICT_GAIN_WITHIN_DEFINED_PROFILE_T270_CELL",
            "STRUCTURE_PHASE_ONLY",
        )
        and not record["UNPROVED_ITEMS"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
