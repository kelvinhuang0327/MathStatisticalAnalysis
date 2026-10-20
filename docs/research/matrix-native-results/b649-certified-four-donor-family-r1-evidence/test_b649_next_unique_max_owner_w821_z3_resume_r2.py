"""Independent Z=3 proof checks and live rejection gates for one resolved owner."""

from __future__ import annotations

import json
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_next_unique_max_owner_w821_z3_resume_r2 as cert

type Record = dict[str, Any]
type Adjacency = list[set[int]]
P = cert.PROFILE
Z_PAIRS = ((0, 1), (0, 2), (1, 2))


@pytest.fixture(scope="module")
def result() -> Record:
    return cert.compute_result()


def ceiling(value: Fraction) -> int:
    quotient, remainder = divmod(value.numerator, value.denominator)
    return quotient + bool(remainder)


def own_term(pid: str, triangles: int, floor: int = 112) -> cert.Term:
    degrees = list(map(int, pid))
    support = [6 + value for value in degrees]
    wedges = sum(value * (value - 1) // 2 for value in support)
    opened = wedges - 3 * triangles
    cubic = sum(comb(value, 3) for value in support)
    k4 = max(0, ceiling(Fraction(cubic - (max(support) - 2) * opened, 4)))
    contained = min(k4, sum(value * (value + 4) for value in degrees) // 3)
    s4 = max(floor, 448 * contained + 679 * (k4 - contained))
    s3 = 2800 * opened + 20272 * (triangles - 22) + 154000
    exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
    return triangles, ceiling(exact), k4, contained, s4, s3


def adjacency(edges: Sequence[tuple[int, int]], size: int = 20) -> Adjacency:
    graph: Adjacency = [set() for _ in range(size)]
    for left, right in edges:
        graph[left].add(right)
        graph[right].add(left)
    return graph


def triangles(graph: Adjacency, vertices: Sequence[int]) -> int:
    return sum(
        1
        for left, mid, right in combinations(vertices, 3)
        if mid in graph[left] and right in graph[left] and right in graph[mid]
    )


def two_shore(graph: Adjacency, left_shore: Sequence[int]) -> Record:
    """Direct complement-split parts. This is not evidence for the universal cap."""

    size = len(graph)
    left_set = set(left_shore)
    right = [vertex for vertex in range(size) if vertex not in left_set]
    right_set = set(right)
    degree = [len(neighbours) for neighbours in graph]
    complement: Adjacency = [
        {other for other in range(size) if other != vertex and other not in graph[vertex]}
        for vertex in range(size)
    ]
    crossing = [
        len(graph[vertex] & (right_set if vertex in left_set else left_set))
        for vertex in range(size)
    ]
    width, height = len(left_shore), len(right)
    twice = height * sum(width - 1 - degree[vertex] for vertex in left_shore) + width * sum(
        height - 1 - degree[vertex] for vertex in right
    )
    score = sum(
        crossing[vertex] * (width - 1 - degree[vertex] + crossing[vertex]) for vertex in left_shore
    ) + sum(crossing[vertex] * (height - 1 - degree[vertex] + crossing[vertex]) for vertex in right)
    goodman = comb(size, 3) - sum(value * (size - 1 - value) for value in degree) // 2
    total = sum(crossing[vertex] for vertex in left_shore)
    assert total == sum(crossing[vertex] for vertex in right) and twice % 2 == 0
    parts = {
        "T_M": triangles(complement, left_shore),
        "T_N": triangles(complement, right),
        "C_Y": sum(
            len(graph[left] & graph[right_vertex] & right_set)
            for left, right_vertex in combinations(left_shore, 2)
            if right_vertex in complement[left]
        ),
        "C_X": sum(
            len(graph[left] & graph[right_vertex] & left_set)
            for left, right_vertex in combinations(right, 2)
            if right_vertex in complement[left]
        ),
    }
    return {
        "T": triangles(graph, range(size)),
        "RAW": goodman - twice // 2 - (size // 2) * total + score,
        "P": sum(parts.values()),
        **parts,
    }


def own_patterns() -> list[Record]:
    grouped: dict[tuple[int, ...], set[frozenset[tuple[int, int]]]] = {}
    masks: dict[tuple[int, ...], int] = {}
    for mask in range(8):
        degree = [0, 0, 0]
        edges: list[tuple[int, int]] = []
        for bit, pair in enumerate(Z_PAIRS):
            if mask >> bit & 1:
                degree[pair[0]] += 1
                degree[pair[1]] += 1
                edges.append(pair)
        order = sorted(range(3), key=lambda vertex: (6 - degree[vertex], vertex))
        rank = {old: new for new, old in enumerate(order)}
        zeta = tuple(6 - degree[old] for old in order)
        present = {tuple(sorted((rank[left], rank[right]))) for left, right in edges}
        grouped.setdefault(zeta, set()).add(frozenset(set(Z_PAIRS) - present))
        masks[zeta] = masks.get(zeta, 0) + 1
    rows: list[Record] = []
    for zeta in sorted(grouped):
        assert len(grouped[zeta]) == 1
        hedges = [list(edge) for edge in sorted(next(iter(grouped[zeta])))]
        rows.append(
            {
                "ZETA": list(zeta),
                "H_EDGES": hedges,
                "T_N": 1 if len(hedges) == 3 else 0,
                "GRAPH_COUNT": masks[zeta],
            }
        )
    assert sum(row["GRAPH_COUNT"] for row in rows) == 8
    assert [row["ZETA"] for row in rows] == [[4, 4, 4], [4, 5, 5], [5, 5, 6], [6, 6, 6]]
    return rows


def own_weight(
    sigmas: Sequence[int], lows: Sequence[int], highs: Sequence[int], total: int
) -> int | None:
    if any(low > high for low, high in zip(lows, highs, strict=True)) or total < sum(lows):
        return None
    extra = total - sum(lows)
    base = sum(low * sigma for low, sigma in zip(lows, sigmas, strict=True))
    best = [-1] * (extra + 1)
    best[0] = 0
    rooms = (high - low for low, high in zip(lows, highs, strict=True))
    for room, sigma in zip(rooms, sigmas, strict=True):
        updated = [-1] * (extra + 1)
        for used, weight in enumerate(best):
            if weight < 0:
                continue
            for take in range(min(room, extra - used) + 1):
                updated[used + take] = max(updated[used + take], weight + take * sigma)
        best = updated
    if best[extra] < 0:
        return None
    return base + best[extra]


def own_shore(m1: int, n0: int, n1: int, n2: int) -> list[tuple[int, int, int]]:
    specs = [(6, 0), *[(5, 0)] * (11 - m1), *[(5, 1)] * m1]
    specs += [(1, 0)] * n0 + [(1, 1)] * n1 + [(1, 2)] * n2
    return [(sigma, 10 - degree + sigma, 6 + degree - sigma) for degree, sigma in specs]


def own_cy(n3: int, shore: Sequence[tuple[int, int, int]]) -> int | None:
    if n3 == 0:
        return 0
    sigmas = [sigma for sigma, _, _ in shore]
    lows = [max(0, n3 - complement) for _, complement, _ in shore]
    highs = [min(n3, inside) for _, _, inside in shore]
    if any(low > high for low, high in zip(lows, highs, strict=True)):
        return None
    pair_cap = comb(n3, 2)
    degree_cap = (n3 * min(4, n3 - 1)) // 2
    cut_cap = (4 * n3 - sum(lows)) // 2
    best: int | None = None
    for edges in range(min(pair_cap, degree_cap, cut_cap) + 1):
        weight = own_weight(sigmas, lows, highs, 4 * n3 - 2 * edges)
        if weight is None:
            continue
        value = 3 * (pair_cap - edges) + n3 * sum(sigmas) - weight
        best = value if best is None else min(best, value)
    return None if best is None else max(0, best)


def own_codegree(
    n3: int, n2: int, singles: int, pattern: Mapping[str, Any]
) -> tuple[int, int] | None:
    """Independent DP over individual vertices and their actual zero subsets."""
    zeta = tuple(int(value) for value in pattern["ZETA"])
    hedges = {tuple(edge) for edge in pattern["H_EDGES"]}
    states: dict[tuple[int, ...], int] = {(0, 0, 0): 0}
    for size in [3] * n3 + [2] * n2 + [1] * singles:
        updated: dict[tuple[int, ...], int] = {}
        for load, cost in states.items():
            for subset in combinations(range(3), size):
                after = tuple(load[i] + (i in subset) for i in range(3))
                if any(after[i] > zeta[i] for i in range(3)):
                    continue
                extra = sum(a in subset and b in subset for a, b in hedges)
                value = cost + extra
                updated[after] = min(updated.get(after, value), value)
        states = updated
    return (states[zeta], int(pattern["T_N"])) if zeta in states else None


def own_score(m1: int, n1: int, n2: int, n3: int, zeta: Sequence[int]) -> int:
    crossing = m1 + n1 + 2 * n2 + 3 * n3
    assert sum(zeta) == crossing
    expanded = (
        233
        - 10 * crossing
        + m1 * 1 * (10 - 5 + 1)
        + n1 * 1 * (10 - 1 + 1)
        + n2 * 2 * (10 - 1 + 2)
        + n3 * 3 * (10 - 1 + 3)
        + sum(value * (value - 4) for value in zeta)
    )
    reduced = 233 - 4 * m1 + 2 * n2 + 6 * n3 + sum(value * (value - 4) for value in zeta)
    assert expanded == reduced
    return reduced


def own_rows() -> list[str]:
    patterns = own_patterns()
    rows: list[tuple[tuple[Any, ...], str]] = []
    for m1 in range(12):
        for values in combinations_with_replacement(range(4), 5):
            counts = Counter(values)
            n0, n1, n2, n3 = (counts[i] for i in range(4))
            shore = own_shore(m1, n0, n1, n2)
            assert len(shore) == 17 - n3
            floor_y = own_cy(n3, shore)
            if floor_y is None:
                continue
            for pattern in patterns:
                zeta = [int(value) for value in pattern["ZETA"]]
                scored = own_codegree(n3, n2, m1 + n1, pattern)
                if scored is None:
                    continue
                floor_x, triangles_n = scored
                exact = own_score(m1, n1, n2, n3, zeta)
                upper = exact - floor_x - triangles_n - floor_y
                assert floor_x >= 0 and triangles_n >= 0 and floor_y >= 0
                key = (-upper, sum(zeta), tuple(zeta), m1, n3, n2, n1, n0)
                text = (
                    f"r={sum(zeta)};m1={m1};n={n0}{n1}{n2}{n3};"
                    f"zeta={''.join(map(str, zeta))};E={exact};cx={floor_x};"
                    f"tn={triangles_n};cy={floor_y};upper={upper}"
                )
                rows.append((key, text))
    return [text for _, text in sorted(rows)]


def test_two_shore_identity_and_nonnegative_remainders() -> None:
    rng = random.Random(64903)
    for _ in range(80):
        probability = rng.choice((0.25, 0.5, 0.75))
        graph = adjacency(
            [edge for edge in combinations(range(20), 2) if rng.random() < probability]
        )
        shore = sorted(rng.sample(range(20), 17))
        parts = two_shore(graph, shore)
        assert parts["RAW"] - parts["P"] == parts["T"]
        assert all(parts[key] >= 0 for key in ("T_M", "T_N", "C_Y", "C_X"))


def test_profile_structure_ranges_and_z5_rejection() -> None:
    degrees = list(map(int, P))
    support = [6 + value for value in degrees]
    facts = cert.profile_facts(P)
    assert Counter(degrees) == {6: 1, 5: 11, 1: 5, 0: 3}
    assert len(degrees) == 20 and sum(degrees) == 66
    assert facts["EDGES"] == sum(support) // 2 == 93
    assert facts["WEDGES"] == sum(comb(value, 2) for value in support) == 821
    assert facts["GOODMAN"] == comb(20, 3) - sum(value * (19 - value) for value in support) // 2
    assert facts["GOODMAN"] == 287
    assert (facts["K"], facts["Z"]) == (17, 3)
    assert facts["J"] == sum(comb(value, 3) for value in support) == 2270
    assert facts["A_MAX"] == sum(value * (value + 4) for value in degrees) // 3 == 193
    positive = [6 + value for value in degrees if value > 0]
    zeros = [6, 6, 6]
    twice = 3 * sum(16 - value for value in positive) + 17 * sum(-4 for _ in zeros)
    assert twice // 2 == 54
    premises = cert.kz_premises(P)
    assert premises["Q"] == 54 and premises["UPPER_CONSTANT"] == 233
    assert premises["SIGMA_RANGE_BY_D"] == {"6": [0, 0], "5": [0, 1], "1": [0, 3]}
    assert premises["ZETA_RANGE"] == [4, 6]
    assert premises["REJECTED_Z5_SIGMA_UPPER"] == "min(5,6-d)"
    assert premises["REJECTED_Z5_ZETA_LOWER"] == 2
    cert.validate_facts(P, facts)
    cert.validate_kz_premises(P, premises)


def test_independent_relaxation_and_hand_checked_argmax() -> None:
    patterns = {tuple(row["ZETA"]): row for row in own_patterns()}
    shipped = list(cert.z_patterns())
    assert [row["ZETA"] for row in shipped] == [list(zeta) for zeta in patterns]
    for row in shipped:
        ours = patterns[tuple(row["ZETA"])]
        assert row["H_EDGES"] == ours["H_EDGES"]
        assert row["T_N"] == ours["T_N"] and row["GRAPH_COUNT"] == ours["GRAPH_COUNT"]
    rows = own_rows()
    relaxation = cert.kz_relaxation(P)
    assert rows == relaxation["RETAINED_STATE_ROWS"]
    assert relaxation["SIGMA_SIGNATURES"] == 12 * 56 == 672
    assert relaxation["Z_GRAPHS_ENUMERATED"] == 8
    assert relaxation["RETAINED_STATE_COUNT"] == len(rows)
    assert len(rows) == 181
    assert relaxation["Z_GRAPH_SIGNATURE_PAIRS"] == 672 * 4
    assert relaxation["PAIRS_WITH_EQUAL_CROSSING_SUMS"] == 181
    assert relaxation["REJECTED_BEFORE_SCORING"] == 0
    assert relaxation["PER_ZETA_MAXIMUM"] == {"444": 257, "455": 264, "556": 264, "666": 254}
    assert relaxation["REJECTED_AFTER_SCORING"] == 0
    assert relaxation["RAW_RANGE_PAIR_COUNT_NOT_SCORED"] > len(rows)
    assert relaxation["CAP"] == max(int(row.rsplit("=", 1)[1]) for row in rows)
    assert relaxation["CAP"] < relaxation["SECANT_CAP_NOT_ADOPTED"]
    assert patterns[(4, 5, 5)]["H_EDGES"] == [[1, 2]]
    assert patterns[(5, 5, 6)]["H_EDGES"] == [[0, 2], [1, 2]]
    # zeta (4,5,5), one doubleton on its only complement edge: codegree 4+1.
    score_a = own_score(0, 0, 1, 4, (4, 5, 5))
    assert score_a == 233 + 2 * 1 + 6 * 4 + 5 + 5 == 269
    assert own_codegree(4, 1, 0, patterns[(4, 5, 5)]) == (5, 0)
    # The sigma-2 vertex can absorb the whole cut, so the C_Y expression reaches 0.
    assert min(3 * (6 - edges) + 8 - min(16 - 2 * edges, 4) * 2 for edges in range(7)) == 0
    # zeta (5,5,6), one singleton on the zeta-6 vertex: both H-edges have codegree 5.
    score_b = own_score(1, 0, 0, 5, (5, 5, 6))
    assert score_b == 233 - 4 + 6 * 5 + 5 + 5 + 12 == 281
    assert own_codegree(5, 0, 1, patterns[(5, 5, 6)]) == (10, 0)
    assert min(3 * (10 - edges) + 5 - min(19 - 2 * edges, 5) for edges in range(10)) == 7
    tops = [row for row in rows if int(row.rsplit("=", 1)[1]) == relaxation["CAP"]]
    assert tops == [
        "r=14;m1=0;n=0014;zeta=455;E=269;cx=5;tn=0;cy=0;upper=264",
        "r=16;m1=1;n=0005;zeta=556;E=281;cx=10;tn=0;cy=7;upper=264",
    ]
    assert relaxation["CAP"] == 264
    assert [cert.state_row(state) for state in relaxation["ALL_ARGMAX"]] == tops
    for diagnostic in relaxation["ARGMAX_GRAPHICALITY_DIAGNOSTICS_ONLY"]:
        assert diagnostic["ASSERTED_REALIZABLE"] is False
    assert relaxation["REALIZABILITY"].startswith("NOT_ASSERTED")
    cert.validate_kz_coverage(P, relaxation)
    for state in relaxation["ALL_ARGMAX"]:
        cert.check_sigma_zeta(P, state["SIGMA_BY_D"], state["ZETA"])


def test_non_graphical_zeta_is_outside_the_scored_domain() -> None:
    legal = [[6, [0]], [5, [0] * 11], [1, [3, 3, 3, 3, 3]]]
    with pytest.raises(ValueError, match="zeta outside the 8 graphs on Z"):
        cert.check_sigma_zeta(P, legal, [5, 5, 5])
    rows = cert.kz_relaxation(P)["RETAINED_STATE_ROWS"]
    assert all("zeta=555" not in row and "zeta=566" not in row for row in rows)


def test_independent_full_domain_without_feasibility_screens() -> None:
    states: set[tuple[int, ...]] = set()
    for m, n0, n1, n2, n3 in product(range(12), *[range(6)] * 4):
        if n0 + n1 + n2 + n3 != 5:
            continue
        for zeta in ((4, 4, 4), (4, 5, 5), (5, 5, 6), (6, 6, 6)):
            if m + n1 + 2 * n2 + 3 * n3 == sum(zeta):
                states.add((m, n0, n1, n2, n3, *zeta))
    relaxation = cert.kz_relaxation(P)
    shipped: set[tuple[int, ...]] = set()
    # Parse every serialized row, rather than inferring coverage from its count.
    for text in relaxation["RETAINED_STATE_ROWS"]:
        fields = dict(part.split("=", 1) for part in text.split(";"))
        shipped.add((int(fields["m1"]), *map(int, fields["n"]), *map(int, fields["zeta"])))
    assert shipped == states and len(states) == len(relaxation["RETAINED_STATE_ROWS"]) == 181


def test_greedy_cut_matches_independent_dp_on_every_signature() -> None:
    for values in combinations_with_replacement(range(4), 5):
        counts = Counter(values)
        n0, n1, n2, n3 = (counts[i] for i in range(4))
        for m in range(12):
            shore = own_shore(m, n0, n1, n2)
            sigmas = [s for s, _, _ in shore]
            lows = [max(0, n3 - a) for _, a, _ in shore]
            highs = [min(n3, g) for _, _, g in shore]
            for e in range(comb(n3, 2) + 1):
                cut = 4 * n3 - 2 * e
                assert cert.max_cut_weight(sigmas, lows, highs, cut) == own_weight(
                    sigmas, lows, highs, cut
                )
            assert cert.complement_edge_floor(n3, shore) == own_cy(n3, shore)


def test_cut_verifier_rejects_optimistic_mutation_and_restores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = cert.max_cut_weight

    def corrupt(s: Sequence[int], lo: Sequence[int], hi: Sequence[int], total: int) -> int | None:
        value = original(s, lo, hi, total)
        return None if value is None else value + 1

    with monkeypatch.context() as patch:
        patch.setattr(cert, "max_cut_weight", corrupt)
        with pytest.raises(AssertionError):
            test_greedy_cut_matches_independent_dp_on_every_signature()
    test_greedy_cut_matches_independent_dp_on_every_signature()


def test_counted_cy_floor_on_constructed_graphs() -> None:
    # Diagnostic of the counting inequality with every possible S graph (n3<=5).
    # The written degree/cut proof, not these examples, establishes universality.
    rng = random.Random(649264)
    for n3 in range(6):
        pairs = list(combinations(range(n3), 2))
        for mask in range(1 << len(pairs)):
            edges = [edge for bit, edge in enumerate(pairs) if mask >> bit & 1]
            graph = adjacency(edges, 17)
            for s in range(n3):
                for u in rng.sample(range(n3, 17), 4 - len(graph[s])):
                    graph[s].add(u)
                    graph[u].add(s)
            for u, v in combinations(range(n3, 17), 2):
                if rng.random() < 0.5:
                    graph[u].add(v)
                    graph[v].add(u)
            sigma = [3] * n3 + [rng.randrange(3) for _ in range(17 - n3)]
            zero_sets = [set(rng.sample(range(3), s)) for s in sigma]
            exact_cy = sum(
                len(zero_sets[u] & zero_sets[v])
                for u, v in combinations(range(17), 2)
                if v not in graph[u]
            )
            shore = [(sigma[u], 16 - len(graph[u]), len(graph[u])) for u in range(n3, 17)]
            bound = cert.complement_edge_floor(n3, shore)
            assert bound is not None and 0 <= bound <= exact_cy


@pytest.mark.parametrize(
    "pid",
    ["65555555555432100000", "66655555555331100000", "", P[:-1]],
)
def test_negative_wrong_profile(pid: str) -> None:
    with pytest.raises(ValueError, match="wrong exact profile"):
        cert.profile_facts(pid)
    with pytest.raises(ValueError, match="wrong exact profile"):
        cert.kz_premises(pid)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("D_HISTOGRAM", {"6": 1, "5": 10, "0": 5}),
        ("WEDGES", 820),
        ("GOODMAN", 286),
        ("K", 15),
        ("Z", 5),
    ],
)
def test_negative_wrong_facts(key: str, value: object) -> None:
    claimed = deepcopy(cert.profile_facts(P))
    claimed[key] = value
    with pytest.raises(ValueError, match="wrong profile fact: " + key):
        cert.validate_facts(P, claimed)


@pytest.mark.parametrize("case", ["sigma", "zeta", "partition", "z5_sigma", "z5_zeta"])
def test_negative_wrong_premises(case: str) -> None:
    bad = deepcopy(cert.kz_premises(P))
    if case == "sigma":
        bad["SIGMA_RANGE_BY_D"]["5"] = [0, 2]
    elif case == "zeta":
        bad["ZETA_RANGE"] = [3, 6]
    elif case == "partition":
        bad["K"], bad["Z"] = 15, 5
    elif case == "z5_sigma":
        bad["SIGMA_RANGE_BY_D"]["1"] = [0, 5]
    else:
        bad["ZETA_RANGE"] = [2, 6]
    with pytest.raises(ValueError, match=r"wrong (sigma range|zeta range|K/Z split)"):
        cert.validate_kz_premises(P, bad)


def test_negative_z5_sigma_zeta_and_crossing() -> None:
    sigma = [[6, [0]], [5, [0] * 11], [1, [0, 0, 0, 0, 4]]]
    with pytest.raises(ValueError, match="sigma range"):
        cert.check_sigma_zeta(P, sigma, [4, 4, 4])
    sigma = [[6, [0]], [5, [0] * 11], [1, [0, 0, 0, 0, 5]]]
    with pytest.raises(ValueError, match="sigma range"):
        cert.check_sigma_zeta(P, sigma, [5, 5, 5])
    sigma = [[6, [0]], [5, [0] * 10 + [2]], [1, [0] * 5]]
    with pytest.raises(ValueError, match="sigma range"):
        cert.check_sigma_zeta(P, sigma, [2, 4, 4])
    legal = [[6, [0]], [5, [0] * 11], [1, [0] * 5]]
    for zeta in ([2, 2, 2], [3, 3, 4], [4, 4, 2]):
        with pytest.raises(ValueError, match="zeta range"):
            cert.check_sigma_zeta(P, legal, zeta)
    z5_shape = [[6, [0]], [5, [0] * 10], [4, [1]], [3, [2]], [2, [3]], [1, [4]]]
    with pytest.raises(ValueError, match="sigma degree classes"):
        cert.check_sigma_zeta(P, z5_shape, [2, 3, 4, 5, 6])
    ordered = [[6, [0]], [5, [1] + [0] * 10], [1, [0] * 5]]
    with pytest.raises(ValueError, match="sigma canonical order"):
        cert.check_sigma_zeta(P, ordered, [4, 4, 5])
    with pytest.raises(ValueError, match="zeta canonical order"):
        cert.check_sigma_zeta(P, legal, [6, 4, 4])
    with pytest.raises(ValueError, match="crossing sums"):
        cert.check_sigma_zeta(P, legal, [4, 4, 5])


@pytest.mark.parametrize(
    "case",
    ["drop", "count", "argmax", "signatures", "graphs", "cap", "sha"],
)
def test_negative_relaxation_coverage(case: str) -> None:
    bad = deepcopy(cert.kz_relaxation(P))
    if case == "drop":
        bad["RETAINED_STATE_ROWS"].pop()
    elif case == "count":
        bad["RETAINED_STATE_COUNT"] -= 1
    elif case == "argmax":
        bad["ALL_ARGMAX"] = []
    elif case == "signatures":
        bad["SIGMA_SIGNATURES"] -= 1
    elif case == "graphs":
        bad["Z_GRAPHS_ENUMERATED"] = 32
    elif case == "cap":
        bad["CAP"] = 267
    else:
        bad["RETAINED_STATES_SHA256"] = "0" * 64
    with pytest.raises(ValueError, match=r"wrong K/Z|K/Z argmax"):
        cert.validate_kz_coverage(P, bad)


@pytest.mark.parametrize("cap", [263, 265, 267, 287, 303, True, 264.0])
def test_negative_wrong_cap(cap: object) -> None:
    with pytest.raises(ValueError, match="wrong triangle cap"):
        cert.validate_cap(P, cap)


def test_envelope_recomputes_every_term() -> None:
    relaxation = cert.kz_relaxation(P)
    floor = cert.route.r28.profile_s4_floor(tuple(map(int, P)))
    assert floor == 112
    new_terms = [own_term(P, triangles) for triangles in range(22, relaxation["CAP"] + 1)]
    assert cert.envelope(P, relaxation["CAP"], floor) == new_terms
    assert max(term[1] for term in new_terms) == new_terms[-1][1]
    assert [term for term in new_terms if term[1] == new_terms[-1][1]] == [new_terms[-1]]
    old_terms = [own_term(P, triangles) for triangles in range(22, 268)]
    assert cert.envelope(P, 267, floor) == old_terms
    assert old_terms[-1][1] == 313391172


def test_base_authority_and_family_aggregation(result: Record) -> None:
    fixed = cert.decode(cert.blob(cert.INPUT_HEAD, cert.INPUT_RESULT))
    base = cert.decode(cert.blob(cert.BASE_HEAD, cert.BASE_RESULT))
    degrees = tuple(map(int, P))
    auth = result["BASE_AUTHORITY"]
    nb_cap = cert.upstream.r2.nb.profile_nb_cap(degrees)[2]
    class_cap = cert.upstream.r2.nb.r18_cap(degrees)
    assert auth["OLD_CAP"] == min(auth["ACCEPTED_R30_CAP"], nb_cap, class_cap) == 267
    assert (auth["NB_CAP"], auth["CLASS_CAP"]) == (271, 272)
    assert auth["S4_BASE"] == 112 and auth["S4_BY_T"] == {} and auth["S5_USED"] is False
    cert.validate_s4_s5(P, base, auth)
    assert result["S4_S5_AUTHORITY"]["S5_ALL_T_ADOPTION"] == "NOT_VERIFIED"
    assert result["S4_S5_AUTHORITY"]["S5_USED"] is False
    assert P not in base["CERTIFICATES_ADOPTED"]
    assert base["INHERITED_TARGET_BONFERRONI_5"]["PROFILE_ID"] != P
    old_terms = [own_term(P, triangles) for triangles in range(22, result["OLD_CAP"] + 1)]
    new_terms = [own_term(P, triangles) for triangles in range(22, result["NEW_CAP"] + 1)]
    assert result["OLD_ALL_T_TERMS"] == old_terms
    assert result["NEW_ALL_T_TERMS"] == new_terms
    assert result["OLD_BOUND"] == max(term[1] for term in old_terms) == 313391172
    assert result["NEW_BOUND"] == max(term[1] for term in new_terms)
    assert result["OLD_ALL_ARGMAX"] == [
        term for term in old_terms if term[1] == result["OLD_BOUND"]
    ]
    assert result["NEW_ALL_ARGMAX"] == [
        term for term in new_terms if term[1] == result["NEW_BOUND"]
    ]
    for prefix, terms in (("OLD", old_terms), ("NEW", new_terms)):
        records: list[Record] = []
        for term in terms:
            if term[1] != max(row[1] for row in terms):
                continue
            value = Fraction(372228640 - 63838600 + term[5]) - Fraction(4 * term[4], 7)
            records.append(
                {
                    "T": term[0],
                    "NUMERATOR": value.numerator,
                    "DENOMINATOR": value.denominator,
                    "CEILING": ceiling(value),
                }
            )
        assert result[prefix + "_ARGMAX_EXACT_FRACTIONS"] == records
    assert result["FULL_ENVELOPE_TERM_COUNTS"] == {
        "OLD": len(old_terms),
        "NEW": len(new_terms),
        "OLD_T_RANGE": [22, result["OLD_CAP"]],
        "NEW_T_RANGE": [22, result["NEW_CAP"]],
    }
    zero = max(own_term(P, triangles, 0)[1] for triangles in range(22, result["NEW_CAP"] + 1))
    assert result["NEW_BOUND_WITH_S4_FLOOR_ZERO"] == zero
    assert result["S4_BASE_LOAD_BEARING"] is (zero != result["NEW_BOUND"])
    before = result["RESOLVED_ROWS_BEFORE"]
    after = result["RESOLVED_ROWS_AFTER"]
    cursor = result["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    assert before == fixed["RESOLVED_ROWS_AFTER"] and len(before) == len(after) == 4647
    assert cursor == fixed["CURSOR_197_PRESERVED"]["ROW_BOUNDS"] and len(cursor) == 197
    assert {profile for profile in before if before[profile] != after[profile]} == {P}
    assert after[P] == result["NEW_BOUND"] < before[P]
    merged = after | cursor
    levels = sorted(set(merged.values()), reverse=True)
    assert result["FAMILY_BEFORE"]["MAXIMUM"] == 313391172
    assert result["FAMILY_BEFORE"]["ALL_MAX_OWNERS"] == [P]
    assert result["FAMILY_BEFORE"]["NEXT_DISTINCT_BOUND"] == 313390396
    assert result["FAMILY_BEFORE"]["ALL_NEXT_DISTINCT_OWNERS"] == ["55555555555443000000"]
    assert result["FAMILY_AFTER"]["MAXIMUM"] == levels[0]
    assert result["ALL_NEW_MAX_OWNERS"] == sorted(
        profile for profile, bound in merged.items() if bound == levels[0]
    )
    assert result["NEXT_DISTINCT_BOUND"] == levels[1]
    assert result["FAMILY_AFTER"]["ALL_NEXT_DISTINCT_OWNERS"] == sorted(
        profile for profile, bound in merged.items() if bound == levels[1]
    )
    assert result["FAMILY_DELTA"] == 313391172 - levels[0]
    assert result["INCUMBENT"] == 313263888
    assert result["GAP_TO_INCUMBENT"] == levels[0] - 313263888
    improved = result["NEW_BOUND"] < before[P] and levels[0] < 313391172
    assert result["TASK_STATUS"] == ("PROVEN_FAMILY_GAIN" if improved else "NO_PROVEN_FAMILY_GAIN")
    if result["NEW_BOUND"] < 313390396:
        assert levels[0] == 313390396
        assert result["ALL_NEW_MAX_OWNERS"] == ["55555555555443000000"]
        assert result["FAMILY_DELTA"] == 776
        assert result["GAP_TO_INCUMBENT"] == 126508
    assert result["LEDGER_PARTITION"]["EXCLUDED_COUNT"] == 282
    assert result["INHERITED_EXCLUSION"] == fixed["INHERITED_EXCLUSION"]
    assert result["INHERITED_CAVEATS_REFERENCE"] == fixed["INHERITED_CAVEATS_REFERENCE"]
    assert (
        result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
        == base["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
    )
    assert result["HISTORICAL_CERTIFICATES_RECERTIFIED"] is False
    assert result["RESOLVED_4647_PRESERVED"] is True
    assert result["OTHER_RESOLVED_ROWS_UNCHANGED"] == 4646
    assert result["PROJECTION_STATUS"].startswith("CONDITIONAL_PROJECTION")
    assert result["GLOBAL_OPTIMUM"] == "UNKNOWN"
    assert result["PREDICTION_GAIN_CLAIMED"] is False
    assert result["FRESH_JUDGE"].endswith("VERDICT_EXTERNAL_TO_JSON")
    assert result["SOLVER_CALLS"] == result["FULL_SUPPORT_GRAPHS_ENUMERATED"] == 0
    assert result["PORTFOLIOS_ENUMERATED"] == result["SAMPLED_REALIZATIONS_USED_FOR_BOUNDS"] == 0
    assert "PASS" not in result["FRESH_JUDGE"]
    cert.validate_family(after, cursor, result["FAMILY_AFTER"])


@pytest.mark.parametrize("case", ["floor", "by_t", "s5", "adopted", "all_t"])
def test_negative_s4_s5(result: Record, case: str) -> None:
    base = cert.decode(cert.blob(cert.BASE_HEAD, cert.BASE_RESULT))
    auth = deepcopy(result["BASE_AUTHORITY"])
    if case == "floor":
        auth["S4_BASE"] = 111
    elif case == "by_t":
        auth["S4_BY_T"] = {"264": 1}
    elif case == "s5":
        auth["S5_USED"] = True
    elif case == "adopted":
        base["CERTIFICATES_ADOPTED"][P] = result["NEW_CAP"]
    else:
        base["ALL_T_BONFERRONI_5_ADOPTION"] = "VERIFIED"
    with pytest.raises(ValueError, match=r"S[45] authority"):
        cert.validate_s4_s5(P, base, auth)


@pytest.mark.parametrize(
    ("column", "delta", "message"),
    [
        (2, -1, "K4 ceiling"),
        (2, 1, "K4 ceiling"),
        (3, 1, "A_max contained-K4"),
        (3, -1, "A_max contained-K4"),
        (4, 1, "S4 MAX floor"),
        (4, -1, "S4 MAX floor"),
        (5, 1, "S3 identity"),
        (1, -1, "Fraction ceiling"),
        (1, 1, "Fraction ceiling"),
    ],
)
def test_negative_wrong_rounding(result: Record, column: int, delta: int, message: str) -> None:
    bad = [list(term) for term in result["NEW_ALL_T_TERMS"]]
    bad[-1][column] += delta
    with pytest.raises(ValueError, match=message):
        cert.validate_envelope(P, result["NEW_CAP"], result["BASE_AUTHORITY"]["S4_BASE"], bad)


def test_negative_fraction_floor() -> None:
    probe = cert.envelope(P, 22, 1)
    exact = Fraction(372228640 - 63838600 + probe[0][5]) - Fraction(4 * probe[0][4], 7)
    assert probe[0][4] == 1 and exact.denominator == 7
    bad = [list(probe[0])]
    bad[0][1] = exact.numerator // exact.denominator
    assert bad[0][1] != probe[0][1]
    with pytest.raises(ValueError, match="Fraction ceiling"):
        cert.validate_envelope(P, 22, 1, bad)


@pytest.mark.parametrize("at", [0, 100, -1])
def test_negative_missing_t(result: Record, at: int) -> None:
    bad = list(result["NEW_ALL_T_TERMS"])
    bad.pop(at)
    with pytest.raises(ValueError, match="incomplete envelope"):
        cert.validate_envelope(P, result["NEW_CAP"], result["BASE_AUTHORITY"]["S4_BASE"], bad)


def test_negative_missing_owner_and_family(result: Record) -> None:
    resolved = result["RESOLVED_ROWS_BEFORE"]
    cursor = result["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    with pytest.raises(ValueError, match="complete unique maximum owner"):
        cert.replace_owner(resolved, {}, [])
    with pytest.raises(ValueError, match="strict owner tightening"):
        cert.replace_owner(resolved, {P: resolved[P]}, [P])
    with pytest.raises(ValueError, match="family row count"):
        cert.family_summary(
            {profile: bound for profile, bound in resolved.items() if profile != P}, cursor
        )
    owners: list[str] = []
    damaged: tuple[tuple[str, object], ...] = (
        ("MAXIMUM", 0),
        ("ALL_MAX_OWNERS", owners),
        ("NEXT_DISTINCT_BOUND", 0),
    )
    for key, value in damaged:
        with pytest.raises(ValueError, match="wrong family aggregation"):
            cert.validate_family(resolved, cursor, result["FAMILY_BEFORE"] | {key: value})


@pytest.mark.parametrize(
    "case",
    ["delete_resolved", "duplicate_resolved", "delete_cursor", "duplicate_cursor"],
)
def test_negative_ledger_rows(result: Record, case: str) -> None:
    expected = (
        result["RESOLVED_ROWS_BEFORE"]
        if case.endswith("resolved")
        else result["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    )
    rows = list(expected.items())
    if case.startswith("delete"):
        rows.pop()
    else:
        rows[-1] = rows[0]
    with pytest.raises(ValueError, match="ledger row count/duplicate"):
        cert.checked_rows(rows, expected)


def test_negative_duplicate_json() -> None:
    with pytest.raises(ValueError, match="duplicate JSON/ledger row"):
        cert.decode(b'{"rows":{"p":1,"p":2}}')


def test_raw_box_is_not_the_scored_domain() -> None:
    low, high = cert.kz_premises(P)["ZETA_RANGE"]
    count = 0
    for m1 in range(12):
        for n0 in range(6):
            for n1 in range(6 - n0):
                for n2 in range(6 - n0 - n1):
                    n3 = 5 - n0 - n1 - n2
                    crossing = m1 + n1 + 2 * n2 + 3 * n3
                    count += sum(
                        sum(zeta) == crossing
                        for zeta in combinations_with_replacement(range(low, high + 1), 3)
                    )
    relaxation = cert.kz_relaxation(P)
    assert count == relaxation["RAW_RANGE_PAIR_COUNT_NOT_SCORED"]
    assert count != relaxation["RETAINED_STATE_COUNT"]


@pytest.mark.parametrize("kind", ["git", "input_result", "direct_source", "base", "r30"])
def test_negative_live_pin_corruption(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    if kind == "git":
        original = cert.git

        def damaged_git(*args: str, repo: Path = cert.ROOT) -> str:
            raw = original(*args, repo=repo)
            return "0" * 40 if args == ("rev-parse", cert.BASE_HEAD + "^{tree}") else raw

        monkeypatch.setattr(cert, "git", damaged_git)
        with pytest.raises(ValueError, match="Git TREE pin"):
            cert.compute_result()
        return
    target = {
        "input_result": cert.INPUT_RESULT,
        "direct_source": cert.direct.SOURCE,
        "base": cert.BASE_RESULT,
        "r30": cert.R30_PATH,
    }[kind]
    original_blob = cert.blob

    def damaged_blob(head: str, path: str, repo: Path = cert.ROOT) -> bytes:
        raw = original_blob(head, path, repo)
        return raw + b"\n" if path == target else raw

    monkeypatch.setattr(cert, "blob", damaged_blob)
    with pytest.raises(ValueError, match="SHA pin"):
        cert.compute_result()


@pytest.mark.parametrize(
    "case",
    [
        "profile",
        "cap",
        "term",
        "argmax",
        "ledger",
        "cursor",
        "exclusion",
        "gain",
        "family",
        "status",
    ],
)
def test_negative_complete_payload(result: Record, case: str) -> None:
    bad = deepcopy(result)
    if case == "profile":
        bad["PROFILE_ID"] = "65555555555432100000"
    elif case == "cap":
        bad["NEW_CAP"] -= 1
    elif case == "term":
        bad["NEW_ALL_T_TERMS"].pop(40)
    elif case == "argmax":
        bad["NEW_ALL_ARGMAX"] = []
    elif case == "ledger":
        bad["RESOLVED_ROWS_AFTER"][P] = bad["RESOLVED_ROWS_BEFORE"][P]
    elif case == "cursor":
        first = next(iter(bad["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]))
        bad["CURSOR_197_PRESERVED"]["ROW_BOUNDS"][first] += 1
    elif case == "exclusion":
        bad["INHERITED_EXCLUSION"]["ORIGINAL_CONDITIONS_VERBATIM"]["COUNT"] -= 1
    elif case == "gain":
        bad["FAMILY_DELTA"] += 1
    elif case == "family":
        bad["FAMILY_AFTER"]["ALL_MAX_OWNERS"] = []
    else:
        bad["TASK_STATUS"] = "NO_PROVEN_FAMILY_GAIN"
    with pytest.raises(ValueError, match="complete recomputation"):
        cert.validate_payload(bad, result)


def test_stored_result_exact_recomputation(result: Record) -> None:
    cert.verify_result()
    stored = json.loads((cert.ROOT / cert.RESULT).read_bytes())
    assert cert.render(stored) == cert.render(result)


@pytest.mark.parametrize("case", ["bytes", "source_hash", "test_hash", "family"])
def test_negative_stored_result_corruption(
    result: Record, case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = deepcopy(result)
    if case == "source_hash":
        bad["SOURCE_SHA256"] = "0" * 64
    elif case == "test_hash":
        bad["TEST_SHA256"] = "0" * 64
    elif case == "family":
        bad["FAMILY_AFTER"]["MAXIMUM"] -= 1
    damaged = cert.render(bad) + (b"\n" if case == "bytes" else b"")
    original = Path.read_bytes

    def damaged_read(path: Path) -> bytes:
        return damaged if path == cert.ROOT / cert.RESULT else original(path)

    if cert.git("rev-parse", "HEAD") == cert.INPUT_HEAD:
        monkeypatch.setattr(Path, "read_bytes", damaged_read)
    else:
        original_blob = cert.blob

        def damaged_blob(head: str, path: str, repo: Path = cert.ROOT) -> bytes:
            return damaged if path == cert.RESULT else original_blob(head, path, repo)

        monkeypatch.setattr(cert, "blob", damaged_blob)
    with pytest.raises(ValueError, match="stored result differs from complete recomputation"):
        cert.verify_result()
