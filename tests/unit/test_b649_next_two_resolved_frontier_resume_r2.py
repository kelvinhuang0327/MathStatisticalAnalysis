"""Independent recount, legal fixtures and live negative gates for the two-owner caps."""

from __future__ import annotations

import json
import random
from collections import Counter
from collections.abc import Sequence
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_next_two_resolved_frontier_resume_r2 as cert

type Record = dict[str, Any]
type Adjacency = list[set[int]]

A, B = cert.PROFILE_A, cert.PROFILE_B

# Scratch hill-climb/random legal realizations: vertex i has d=int(pid[i]); 'a-b-c' is one
# triple label and 'a-b' one pair label. Positive fixtures only; no certified bound uses them.
FIXTURES: dict[str, list[tuple[str, str, int]]] = {
    "66655555555331100000": [
        (
            "0-1-12 0-2-8 0-3-10 0-4-5 0-6-7 0-9-14 1-2-3 1-4-8 1-5-10 1-6-11 1-7-9 2-4-13 2-5-7 "
            "2-6-12 2-10-11 3-4-7 3-5-12 3-6-9 4-9-10 5-8-9 6-8-10 7-8-11",
            "3-11 4-19 5-17 6-19 7-12 8-15 9-16 10-16 11-14 11-19 12-13 12-15 13-15 13-17 13-18 "
            "13-19 14-15 14-16 14-17 14-18 15-17 15-18 16-17 16-18 16-19 17-18 18-19",
            180,
        ),
        (
            "0-1-11 0-2-10 0-3-6 0-4-8 0-5-7 0-9-12 1-2-14 1-3-4 1-5-12 1-7-10 1-8-9 2-3-11 "
            "2-4-13 2-5-9 2-6-7 3-7-9 3-8-10 4-5-10 4-6-11 5-6-8 6-9-10 7-8-12",
            "3-16 4-12 5-17 6-15 7-18 8-14 9-15 10-16 11-14 11-18 11-19 12-14 12-17 13-14 13-15 "
            "13-16 13-18 13-19 14-15 15-17 15-19 16-17 16-18 16-19 17-18 17-19 18-19",
            176,
        ),
        (
            "0-1-11 0-2-4 0-3-10 0-5-12 0-6-8 0-7-9 1-2-7 1-3-9 1-4-12 1-5-8 1-6-10 2-3-6 2-5-10 "
            "2-8-11 2-9-12 3-4-11 3-7-8 4-5-9 4-7-10 5-6-7 6-13-14 8-9-10",
            "3-5 4-8 6-11 7-12 9-11 10-12 11-12 13-15 13-16 13-17 13-18 13-19 14-15 14-16 14-17 "
            "14-18 14-19 15-16 15-17 15-18 15-19 16-17 16-18 16-19 17-18 17-19 18-19",
            243,
        ),
    ],
    "66655555555411110000": [
        (
            "0-1-11 0-2-3 0-4-7 0-6-10 0-8-9 0-13-14 1-2-10 1-3-8 1-4-6 1-5-15 1-7-9 2-4-5 2-6-9 "
            "2-7-8 2-11-12 3-4-9 3-5-11 3-6-7 4-8-10 5-6-8 5-9-10 7-10-11",
            "3-16 4-16 5-19 6-19 7-15 8-13 9-17 10-13 11-13 11-14 12-13 12-14 12-15 12-17 12-18 "
            "13-17 14-16 14-17 14-18 15-16 15-18 15-19 16-18 16-19 17-18 17-19 18-19",
            187,
        ),
        (
            "0-1-11 0-2-6 0-3-7 0-5-12 0-8-10 0-9-15 1-2-3 1-4-9 1-5-8 1-6-10 1-7-14 2-4-13 "
            "2-5-10 2-7-8 2-9-11 3-4-5 3-8-11 3-9-10 4-6-11 4-7-10 5-6-7 6-8-9",
            "3-12 4-18 5-19 6-16 7-12 8-18 9-18 10-17 11-15 11-19 12-14 12-18 12-19 13-14 13-15 "
            "13-16 13-17 13-19 14-15 14-16 14-17 15-16 15-17 16-17 16-18 17-19 18-19",
            174,
        ),
        (
            "0-1-10 0-2-4 0-3-11 0-5-13 0-6-8 0-7-9 1-2-14 1-3-8 1-4-7 1-5-11 1-6-9 2-3-7 2-6-10 "
            "2-8-9 2-12-15 3-4-6 3-5-9 4-8-11 4-9-10 5-6-7 5-8-10 7-10-11",
            "3-10 4-5 6-11 7-8 9-11 12-14 12-16 12-17 12-18 12-19 13-14 13-16 13-17 13-18 13-19 "
            "14-15 14-18 14-19 15-16 15-17 15-18 15-19 16-17 16-18 16-19 17-18 17-19",
            234,
        ),
    ],
}


type Realization = tuple[list[tuple[int, int, int]], list[tuple[int, int]], int]


def realizations(pid: str) -> list[Realization]:
    out: list[Realization] = []
    for triples, pairs, t in FIXTURES[pid]:
        tri = [(a, b, c) for a, b, c in (map(int, x.split("-")) for x in triples.split())]
        pr = [(a, b) for a, b in (map(int, x.split("-")) for x in pairs.split())]
        out.append((tri, pr, t))
    return out


@pytest.fixture(scope="module")
def result() -> Record:
    return cert.compute_result()


def ceiling(value: Fraction) -> int:
    quotient, remainder = divmod(value.numerator, value.denominator)
    return quotient + bool(remainder)


def own_term(pid: str, t: int, floor: int = 112) -> cert.Term:
    d = list(map(int, pid))
    g = [6 + x for x in d]
    w = sum(x * (x - 1) // 2 for x in g)
    opened = w - 3 * t
    k4 = max(0, ceiling(Fraction(sum(comb(x, 3) for x in g) - (max(g) - 2) * opened, 4)))
    a = min(k4, sum(x * (x + 4) for x in d) // 3)
    s4 = max(floor, 448 * a + 679 * (k4 - a))
    s3 = 2800 * opened + 20272 * (t - 22) + 154000
    exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
    return t, ceiling(exact), k4, a, s4, s3


def havel_hakimi(seq: Sequence[int]) -> bool:
    s = sorted(seq, reverse=True)
    if any(x < 0 for x in s) or sum(s) % 2:
        return False
    while s and s[0] > 0:
        k = s.pop(0)
        if k > len(s):
            return False
        for i in range(k):
            s[i] -= 1
        if any(x < 0 for x in s):
            return False
        s.sort(reverse=True)
    return True


def ryser(left: Sequence[int], right: Sequence[int]) -> bool:
    """Constructive greedy bipartite realization (independent of Gale-Ryser sums)."""
    if sum(left) != sum(right):
        return False
    rest = list(right)
    for a in sorted(left, reverse=True):
        order = sorted(range(len(rest)), key=lambda j: -rest[j])[:a]
        if len(order) < a or any(rest[j] <= 0 for j in order):
            return False
        for j in order:
            rest[j] -= 1
    return not any(rest)


def edge_floor(deg: Sequence[int], size: int) -> int:
    top = sorted(deg, reverse=True)[: len(deg) - size]
    return max(0, sum(deg) // 2 - sum(top))


def tri_floor(deg: Sequence[int]) -> int:
    n, e, d = len(deg), sum(deg) // 2, sorted(deg, reverse=True)
    best = max(0, ceiling(Fraction(sum(x * x for x in d) - n * e, 3)))
    for h in range(1, n + 1):
        need = sum(d[:h]) - sum(min(h, x) for x in d[h:])
        ell = max(0, ceiling(Fraction(need, 2)))
        weights = sorted(max(0, a + b - n) for a, b in combinations(d[:h], 2))
        best = max(best, sum(weights[:ell]) - 2 * comb(h, 3))
    return best


def adjacency(edges: Sequence[tuple[int, int]], n: int = 20) -> Adjacency:
    adj: Adjacency = [set() for _ in range(n)]
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    return adj


def triangles(adj: Adjacency, verts: Sequence[int]) -> int:
    return sum(
        1 for a, b, c in combinations(verts, 3) if b in adj[a] and c in adj[a] and c in adj[b]
    )


def two_shore(adj: Adjacency, xs: Sequence[int]) -> Record:
    """Exact (*) parts for one partition, P computed directly from the graph."""
    n = len(adj)
    xset = set(xs)
    ys = [v for v in range(n) if v not in xset]
    yset = set(ys)
    g = [len(a) for a in adj]
    h: Adjacency = [{u for u in range(n) if u != v and u not in adj[v]} for v in range(n)]
    s = [len(adj[v] & (yset if v in xset else xset)) for v in range(n)]
    x, y = len(xs), len(ys)
    q2 = y * sum(x - 1 - g[v] for v in xs) + x * sum(y - 1 - g[v] for v in ys)
    t_m, t_n = triangles(h, xs), triangles(h, ys)
    c_y = sum(len(adj[u] & adj[v] & yset) for u, v in combinations(xs, 2) if v in h[u])
    c_x = sum(len(adj[u] & adj[v] & xset) for u, v in combinations(ys, 2) if v in h[u])
    b0 = comb(n, 3) - sum(a * (n - 1 - a) for a in g) // 2
    score = sum(s[v] * (x - 1 - g[v] + s[v]) for v in xs) + sum(
        s[v] * (y - 1 - g[v] + s[v]) for v in ys
    )
    crossing = sum(s[v] for v in xs)
    assert crossing == sum(s[v] for v in ys) and q2 % 2 == 0
    return {
        "T": triangles(adj, range(n)),
        "RAW": b0 - q2 // 2 - 10 * crossing + score,
        "P": t_m + t_n + c_y + c_x,
        "T_M": t_m,
        "T_N": t_n,
        "C_Y_ON_E_M": c_y,
        "C_X_ON_E_N": c_x,
        "S": s,
        "M": [len(h[v] & xset) for v in xs],
        "N": [len(h[v] & yset) for v in ys],
    }


def legal_graph(
    pid: str, triples: Sequence[tuple[int, int, int]], pairs: Sequence[tuple[int, int]]
) -> tuple[Adjacency, set[tuple[int, int]]]:
    d = list(map(int, pid))
    assert len(triples) == 22 and len(pairs) == 27
    covered = [e for t in triples for e in combinations(sorted(t), 2)]
    pair_edges = [(min(a, b), max(a, b)) for a, b in pairs]
    assert all(len(set(t)) == 3 for t in triples) and all(a != b for a, b in pairs)
    assert len(set(covered + pair_edges)) == 66 + 27, "pair-linearity"
    assert [sum(v in t for t in triples) for v in range(20)] == d
    assert [sum(v in e for e in pairs) for v in range(20)] == [6 - x for x in d]
    return adjacency(covered + pair_edges), set(covered)


def test_input_replay_pins_and_frontier(result: Record) -> None:
    fixed, base, _ = cert.replay_input()
    assert cert.git("rev-parse", cert.INPUT_HEAD + "^{tree}") == cert.INPUT_TREE
    assert cert.git("rev-parse", cert.BASE_HEAD + "^{tree}") == cert.BASE_TREE
    assert result["FAMILY_BEFORE"] == fixed["FAMILY_AFTER"]
    assert result["FAMILY_BEFORE"]["MAXIMUM"] == 313391740
    assert result["FAMILY_BEFORE"]["ALL_MAX_OWNERS"] == [A, B]
    assert result["FAMILY_BEFORE"]["NEXT_DISTINCT_BOUND"] == 313391636
    assert result["EVALUATOR_SOURCE_PINS"] == fixed["EVALUATOR_SOURCE_PINS"]
    assert base["ALL_T_BONFERRONI_5_ADOPTION"] == "NOT_VERIFIED"
    assert fixed["INCUMBENT"] == result["INCUMBENT"] == 313263888


def test_independent_profile_facts(result: Record) -> None:
    expected = {A: ("6^3 5^8 3^2 1^2 0^5", 15, 5), B: ("6^3 5^8 4^1 1^4 0^4", 16, 4)}
    for pid, (histogram, k, z) in expected.items():
        d = list(map(int, pid))
        text = " ".join(f"{v}^{n}" for v, n in sorted(Counter(d).items(), reverse=True))
        g = [6 + x for x in d]
        facts = result["PROFILES"][pid]["FACTS"]
        assert text == histogram and sum(d) == 66 and sum(g) == 186
        assert facts["WEDGES"] == sum(x * (x - 1) // 2 for x in g) == 827
        assert facts["GOODMAN"] == 1140 - sum(x * (19 - x) for x in g) // 2 == 293
        assert (facts["K"], facts["Z"], facts["EDGES"]) == (k, z, 93)
        assert facts["A_MAX"] == 592 // 3 == 197 and facts["A_MAX_NUMERATOR"] == 592
        assert facts["J"] == sum(comb(x, 3) for x in g) and facts["G_MAX"] == 12
        cert.validate_facts(pid, facts)


def test_two_shore_identity_and_remainders_on_random_graphs() -> None:
    rng = random.Random(64920)
    for _ in range(120):
        p = rng.choice((0.2, 0.4, 0.6, 0.8))
        adj = adjacency([e for e in combinations(range(20), 2) if rng.random() < p])
        xs = sorted(rng.sample(range(20), rng.randrange(1, 20)))
        parts = two_shore(adj, xs)
        assert parts["RAW"] - parts["P"] == parts["T"]
        s, ys = parts["S"], [v for v in range(20) if v not in xs]
        assert cert.triangle_lower(tuple(parts["M"])) <= parts["T_M"]
        assert cert.triangle_lower(tuple(parts["N"])) <= parts["T_N"]
        assert sum(cert.subset_edge_lower(parts["N"], s[v]) for v in xs) <= parts["C_X_ON_E_N"]
        assert sum(cert.subset_edge_lower(parts["M"], s[v]) for v in ys) <= parts["C_Y_ON_E_M"]
    for _ in range(150):
        n = rng.randrange(3, 9)
        adj = adjacency([e for e in combinations(range(n), 2) if rng.random() < 0.55], n)
        deg = [len(a) for a in adj]
        assert cert.triangle_lower(tuple(deg)) == tri_floor(deg) <= triangles(adj, range(n))
        for size in range(n + 1):
            least = min(
                sum(1 for a, b in combinations(sub, 2) if b in adj[a])
                for sub in combinations(range(n), size)
            )
            assert cert.subset_edge_lower(deg, size) == edge_floor(deg, size) <= least


@pytest.mark.parametrize("pid", [A, B])
def test_legal_realization_fixtures_map_into_both_relaxations(pid: str) -> None:
    d = list(map(int, pid))
    kz, hilo = cert.kz_relaxation(pid), cert.hilo_relaxation(pid)
    cells = {(c[0], c[1]): c[4] for c in hilo["ALL_CELLS"]}
    cap = cert.certified_cap(pid)["CAP"]
    for triples, pairs, t in realizations(pid):
        adj, block = legal_graph(pid, triples, pairs)
        assert [len(a) for a in adj] == [6 + x for x in d]
        assert triangles(adj, range(20)) == t <= cap
        ks = [v for v in range(20) if d[v] > 0]
        exact = two_shore(adj, ks)
        assert exact["RAW"] - exact["P"] == t
        groups = sorted({d[v] for v in ks}, reverse=True)
        sigma_by_d = [(c, sorted(exact["S"][v] for v in ks if d[v] == c)) for c in groups]
        zeta = sorted(exact["S"][v] for v in range(20) if d[v] == 0)
        state = cert.kz_state(pid, sigma_by_d, zeta)
        assert cert.kz_state_row(state) in set(cert.kz_relaxation(pid)["RETAINED_STATE_ROWS"])
        assert state["WITHOUT_REMAINDER"] == exact["RAW"]
        low = state["REMAINDER_LOWER"]
        assert low["T_M"] <= exact["T_M"] and low["T_N"] <= exact["T_N"]
        assert low["C_K"] <= exact["C_X_ON_E_N"] and low["C_Z"] <= exact["C_Y_ON_E_M"]
        assert t <= state["UPPER"] <= kz["CAP"]
        his = [v for v in range(20) if d[v] >= cert.HI_MIN_D]
        split = two_shore(adj, his)
        assert split["RAW"] - split["P"] == t
        beta = pi = 0
        for v in range(20):
            shore = "HI" if v in his else "LO"
            other = [u for u in adj[v] if (u in his) != (v in his)]
            b = sum((min(u, v), max(u, v)) in block for u in other)
            cert.validate_hilo_choice(pid, shore, d[v], b, len(other) - b)
            assert (b, len(other) - b) in cert.hilo_choices(pid, shore, d[v])
            if shore == "HI":
                beta, pi = beta + b, pi + len(other) - b
        assert split["RAW"] <= cells[(beta, pi)] <= hilo["CAP"]


def kz_recount(pid: str) -> list[str]:
    """Independent K/Z enumeration by count vectors, Havel-Hakimi and greedy Ryser."""
    d = list(map(int, pid))
    k, z = sum(x > 0 for x in d), d.count(0)
    q2 = z * sum(k - 7 - x for x in d if x > 0) + k * z * (z - 7)
    constant = 1140 - sum((6 + x) * (13 - x) for x in d) // 2 - q2 // 2
    groups = sorted(Counter(x for x in d if x > 0).items(), reverse=True)

    def multisets(count: int, top: int, low: int = 0) -> list[tuple[int, ...]]:
        out: list[tuple[int, ...]] = []
        for vector in product(range(count + 1), repeat=top - low + 1):
            if sum(vector) == count:
                values = zip(range(low, top + 1), vector, strict=True)
                out.append(tuple(v for v, c in values for _ in range(c)))
        return out

    per_class = [multisets(n, min(z, 6 - v)) for v, n in groups]
    zetas = multisets(z, min(k, 6), max(0, 7 - z))
    rows: list[str] = []
    for parts in product(*per_class):
        pairs = [(v, s) for (v, _), part in zip(groups, parts, strict=True) for s in part]
        sigma = [s for _, s in pairs]
        m = [k - 7 - v + s for v, s in pairs]
        if not havel_hakimi(m):
            continue
        for zeta in zetas:
            if sum(zeta) != sum(sigma) or not havel_hakimi([6 - x for x in zeta]):
                continue
            if not ryser(sigma, list(zeta)):
                continue
            n = [z - 7 + x for x in zeta]
            raw = (
                constant
                - 10 * sum(sigma)
                + sum(s * a for s, a in zip(sigma, m, strict=True))
                + sum(x * a for x, a in zip(zeta, n, strict=True))
            )
            low = (
                tri_floor(m),
                tri_floor(n),
                sum(edge_floor(n, s) for s in sigma),
                sum(edge_floor(m, x) for x in zeta),
            )
            text = ",".join(
                f"{v}:" + "".join(map(str, p)) for (v, _), p in zip(groups, parts, strict=True)
            )
            rows.append(
                f"r={sum(sigma)};sigma={text};zeta={''.join(map(str, zeta))};raw={raw};"
                f"T_M={low[0]};T_N={low[1]};C_K={low[2]};C_Z={low[3]};upper={raw - sum(low)}"
            )
    return rows


def test_independent_kz_recount_and_coverage(result: Record) -> None:
    expected = {A: (1661, 253, 265, 6533), B: (1005, 267, 301, 3241)}
    for pid, (count, cap, no_remainder, equal_sums) in expected.items():
        rows = kz_recount(pid)
        ours = cert.kz_relaxation(pid)
        assert sorted(rows) == sorted(ours["RETAINED_STATE_ROWS"]) and len(rows) == count
        uppers = [int(r.rsplit("=", 1)[1]) for r in rows]
        raws = [int(r.split(";raw=")[1].split(";")[0]) for r in rows]
        assert max(uppers) == ours["CAP"] == cap and max(raws) == no_remainder
        assert ours["RANGE_STATES_WITH_EQUAL_CROSSING_SUMS"] == equal_sums
        assert (
            ours["RETAINED_STATE_COUNT"] + sum(ours["REJECTED_BY_FIRST_FAILED_CONDITION"].values())
            == equal_sums
        )
    a_cert = result["PROFILES"][A]["ADOPTED_K_Z_CERTIFICATE"]
    assert a_cert["SIGMA_SIGNATURES"] == 1 * 9 * comb(5, 2) * comb(7, 2) == 1890
    assert a_cert["ZETA_MULTISETS_IN_RANGE"] == comb(9, 5) == 126
    assert a_cert["PREMISES"]["SIGMA_RANGE_BY_D"] == {
        "6": [0, 0],
        "5": [0, 1],
        "3": [0, 3],
        "1": [0, 5],
    }
    assert a_cert["PREMISES"]["ZETA_RANGE"] == [2, 6] and a_cert["PREMISES"]["Q"] == 60
    [top] = a_cert["ALL_ARGMAX"]
    assert top["SIGMA_BY_D"] == [[6, [0, 0, 0]], [5, [0] * 8], [3, [0, 0]], [1, [5, 5]]]
    assert top["ZETA"] == [2] * 5 and top["UPPER"] == top["WITHOUT_REMAINDER"] == 253
    assert set(top["REMAINDER_LOWER"].values()) == {0}
    # Every state whose remainder-free value exceeds 253 is cut by its remainder bounds.
    raw_of = {s: int(s.split(";raw=")[1].split(";")[0]) for s in a_cert["RETAINED_STATE_ROWS"]}
    above = [s for s, raw in raw_of.items() if raw > 253]
    assert above and all(int(s.rsplit("=", 1)[1]) <= 253 for s in above)
    assert a_cert["ABLATION_CAPS"] == {
        "RANGE_AND_CROSSING_SUM_ONLY": 277,
        "NECESSARY_CONDITIONS_NO_REMAINDER": 265,
        "ONLY_C_K_REMAINDER": 259,
        "ONLY_C_Z_REMAINDER": 265,
        "ONLY_TRIANGLE_REMAINDERS": 263,
        "ALL_FOUR_REMAINDERS": 253,
    }
    assert a_cert["RETAINED_STATES_SHA256"] == cert.sha(cert.render(a_cert["RETAINED_STATE_ROWS"]))


def hilo_vertex_dp(pid: str) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], int]]:
    """Independent per-ticket dynamic programme over (beta, pi) for each shore."""
    d = list(map(int, pid))
    his = [v for v in range(20) if d[v] >= 4]
    los = [v for v in range(20) if d[v] < 4]

    def side(own: list[int], other: list[int]) -> dict[tuple[int, int], int]:
        table = {(0, 0): 0}
        mates = sum(d[u] > 0 for u in other)
        for v in own:
            offset = len(own) - 7 - d[v]
            step: dict[tuple[int, int], int] = {}
            for (beta, pi), score in table.items():
                for b in range(min(2 * d[v], mates) + 1):
                    for q in range(7 - d[v]):
                        s = b + q
                        if s <= len(other) and offset + s >= 0:
                            key = (beta + b, pi + q)
                            step[key] = max(step.get(key, -(10**9)), score + s * (offset + s))
            table = step
        return table

    return side(his, los), side(los, his)


def test_independent_hilo_vertex_dp(result: Record) -> None:
    for pid, cap, top in ((B, 260, [[7, 5], [7, 10]]), (A, 285, [[12, 6], [14, 8]])):
        hi, lo = hilo_vertex_dp(pid)
        ours = cert.hilo_relaxation(pid)
        constant = ours["PREMISES"]["UPPER_CONSTANT"]
        cells = sorted(set(hi) & set(lo))
        assert ours["ALL_CELLS"] == [
            [c[0], c[1], hi[c], lo[c], constant - 10 * (c[0] + c[1]) + hi[c] + lo[c]] for c in cells
        ]
        assert ours["SHORE_CELL_COUNTS"] == {"HI": len(hi), "LO": len(lo)}
        assert ours["CAP"] == cap and [[a["BETA"], a["PI"]] for a in ours["ALL_ARGMAX"]] == top
        for a in ours["ALL_ARGMAX"]:
            for side, best in (("HI", hi), ("LO", lo)):
                offset = {t["D"]: t["OFFSET"] for t in ours["CLASS_CHOICES"][side]}
                assert a[side + "_STATES"]
                for chosen in a[side + "_STATES"]:
                    flat = [(dv, b, q) for dv, ms in chosen for b, q in ms]
                    assert sum(b for _, b, _ in flat) == a["BETA"]
                    assert sum(q for _, _, q in flat) == a["PI"]
                    score = sum((b + q) * (offset[dv] + b + q) for dv, b, q in flat)
                    assert score == a[side + "_SCORE"] == best[(a["BETA"], a["PI"])]
    b_cert = result["PROFILES"][B]["ADOPTED_HI_LO_CERTIFICATE"]
    prem = b_cert["PREMISES"]
    assert (prem["HI_D"], prem["LO_D"]) == ([6, 6, 6, *[5] * 8, 4], [1, 1, 1, 1, 0, 0, 0, 0])
    assert prem["Q"] == 16 and prem["UPPER_CONSTANT"] == 277 and b_cert["CELL_COUNT"] == 66
    assert (
        max(c[0] for c in b_cert["ALL_CELLS"]) <= 8 and max(c[1] for c in b_cert["ALL_CELLS"]) <= 10
    )
    ranges = prem["RANGES_BY_SHORE_AND_D"]
    assert {v: (r["B_MAX"], r["Q_MAX"], r["OFFSET"]) for v, r in ranges["HI"].items()} == {
        "6": (4, 0, -1),
        "5": (4, 1, 0),
        "4": (4, 2, 1),
    }
    assert {v: (r["B_MAX"], r["Q_MAX"], r["OFFSET"]) for v, r in ranges["LO"].items()} == {
        "1": (2, 5, 0),
        "0": (0, 6, 1),
    }
    assert [list(c) for c in b_cert["CLASS_CHOICES"]["HI"][0]["CHOICES"]] == [
        [b, 0] for b in range(1, 5)
    ]


def test_adopted_caps_meet_stopping_cap(result: Record) -> None:
    caps = result["SHARED_THEOREM"]["PER_PROFILE_CAPS"]
    assert caps[A] == {
        "ADOPTED_SPLIT": "K/Z",
        "CAP": 253,
        "K_Z_CAP": 253,
        "HI_LO_CAP": 285,
        "DIAGNOSTIC_SPLIT": "HI/LO",
        "DIAGNOSTIC_CAP": 285,
        "STOPPING_CAP": 264,
        "MEETS_STOPPING_CAP": True,
    }
    assert caps[B]["ADOPTED_SPLIT"] == "HI/LO" and caps[B]["CAP"] == 260
    assert caps[B]["K_Z_CAP"] == 267 and caps[B]["DIAGNOSTIC_CAP"] == 267
    for pid in (A, B):
        p = result["PROFILES"][pid]
        assert p["OLD_CAP"] == 265 > p["NEW_CAP"] == caps[pid]["CAP"]
        assert max(t for _, _, t in realizations(pid)) <= p["NEW_CAP"]
    assert result["SHARED_THEOREM"]["SAMPLED_REALIZATIONS_USED_FOR_BOUNDS"] == 0


def test_base_authority_and_complete_old_and_new_envelopes(result: Record) -> None:
    expected = {A: (3394, 266, 232, 313284196), B: (3393, 265, 239, 313346736)}
    for pid, (attempt, nb, count, bound) in expected.items():
        p = result["PROFILES"][pid]
        auth = p["BASE_AUTHORITY"]
        assert auth["R30_ATTEMPT"]["ATTEMPT_INDEX"] == attempt
        assert auth["R30_ATTEMPT"]["REFUTED_GRAPH_TRIANGLE_COUNT"] == 266
        assert (auth["ACCEPTED_R30_CAP"], auth["NB_CAP"], auth["CLASS_CAP"]) == (265, nb, 274)
        assert auth["S4_BASE"] == 112 and auth["S5_USED"] is False
        old = [own_term(pid, t) for t in range(22, 266)]
        new = [own_term(pid, t) for t in range(22, p["NEW_CAP"] + 1)]
        assert p["OLD_ALL_T_TERMS"] == old and p["NEW_ALL_T_TERMS"] == new
        assert (p["OLD_TERM_COUNT"], p["NEW_TERM_COUNT"]) == (244, count)
        assert p["OLD_BOUND"] == max(t[1] for t in old) == 313391740
        assert p["NEW_BOUND"] == max(t[1] for t in new) == bound
        assert p["OLD_ALL_ARGMAX"] == [t for t in old if t[1] == p["OLD_BOUND"]] == [old[-1]]
        assert p["NEW_ALL_ARGMAX"] == [t for t in new if t[1] == bound] == [new[-1]]
        assert p["NEW_BOUND_WITH_S4_FLOOR_ZERO"] == max(
            own_term(pid, t, 0)[1] for t in range(22, p["NEW_CAP"] + 1)
        )
        assert p["ROW_DELTA"] == 313391740 - bound
    counts = result["FULL_ENVELOPE_TERM_COUNTS"]
    assert counts["OLD_TOTAL"] == 488 and counts["NEW_TOTAL"] == 471


def test_full_family_aggregation_and_preservation(result: Record) -> None:
    fixed, _, _ = cert.replay_input()
    raw: dict[str, int] = {}
    for combo in combinations_with_replacement(range(7), 20):
        if sum(combo) == 66:
            raw["".join(map(str, reversed(combo)))] = sum(comb(6 + x, 2) for x in combo)
    before, after = result["RESOLVED_ROWS_BEFORE"], result["RESOLVED_ROWS_AFTER"]
    cursor = result["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    assert len(raw) == 5126 and len(before) == len(after) == 4647 and len(cursor) == 197
    assert before == fixed["RESOLVED_ROWS"] and cursor == fixed["CURSOR_ROW_BOUNDS_AFTER"]
    assert set(cursor) == {p for p, w in raw.items() if w <= 785}
    assert all(cursor[p] <= fixed["CURSOR_ROW_BOUNDS_BEFORE"][p] for p in cursor)
    assert len(set(raw) - set(before) - set(cursor)) == 282
    assert {p for p in before if before[p] != after[p]} == {A, B}
    assert after[A] == 313284196 and after[B] == 313346736
    merged = after | cursor
    levels = sorted(set(merged.values()), reverse=True)
    assert result["FAMILY_AFTER"]["MAXIMUM"] == levels[0] == 313391636
    assert result["ALL_NEW_MAX_OWNERS"] == ["66665555555321100000"]
    assert result["NEXT_DISTINCT_BOUND"] == levels[1] == 313391560
    assert result["FAMILY_DELTA"] == 104 and result["GAP_TO_INCUMBENT"] == 127748
    assert result["TASK_STATUS"] == "PROVEN_FAMILY_GAIN"
    assert result["INHERITED_EXCLUSION"] == fixed["INHERITED_EXCLUSION"]
    assert result["LEDGER_PARTITION"]["EXCLUDED_COUNT"] == 282
    assert result["HISTORICAL_CERTIFICATES_RECERTIFIED"] is False
    assert result["SOLVER_CALLS"] == result["PORTFOLIOS_ENUMERATED"] == 0


@pytest.mark.parametrize(
    "pid", ["66655555555331100001", "66665555555321100000", "", "6665555555533110000"]
)
def test_negative_wrong_profile(pid: str) -> None:
    with pytest.raises(ValueError, match="wrong exact profile"):
        cert.profile_facts(pid)
    with pytest.raises(ValueError, match="wrong exact profile"):
        cert.kz_premises(pid)


@pytest.mark.parametrize("key,delta", [("WEDGES", 1), ("GOODMAN", -1), ("K", 1), ("Z", -1)])
def test_negative_wrong_wedge_goodman_or_kz(result: Record, key: str, delta: int) -> None:
    for pid in (A, B):
        facts = deepcopy(result["PROFILES"][pid]["FACTS"])
        facts[key] += delta
        with pytest.raises(ValueError, match="wrong profile fact: " + key):
            cert.validate_facts(pid, facts)


def test_negative_wrong_kz_partition_and_ranges() -> None:
    with pytest.raises(ValueError, match="wrong K/Z split"):
        cert.validate_kz_premises(A, cert.kz_premises(B))
    bad = deepcopy(cert.kz_premises(A))
    bad["SIGMA_RANGE_BY_D"]["1"] = [0, 4]  # B's z=4 bound misapplied to A
    with pytest.raises(ValueError, match="wrong sigma range"):
        cert.validate_kz_premises(A, bad)
    bad = deepcopy(cert.kz_premises(A))
    bad["ZETA_RANGE"] = [3, 6]  # B's 7-z misapplied to A
    with pytest.raises(ValueError, match="wrong zeta range"):
        cert.validate_kz_premises(A, bad)
    bad = deepcopy(cert.kz_premises(A))
    bad["Q"] = 59
    with pytest.raises(ValueError, match="wrong K/Z premises"):
        cert.validate_kz_premises(A, bad)
    zero8 = [0] * 8
    cases: list[tuple[list[tuple[int, list[int]]], list[int], str]] = [
        ([(6, [0, 0, 0]), (5, [2, *zero8[1:]]), (3, [0, 0]), (1, [0, 0])], [2] * 5, "sigma range"),
        ([(6, [0, 0, 0]), (5, zero8), (3, [0, 0]), (1, [0, 6])], [2] * 5, "sigma range"),
        ([(6, [0, 0, 0]), (5, zero8), (3, [0, 0]), (1, [5, 5])], [1, 2, 2, 2, 3], "zeta range"),
        ([(6, [0, 0, 0]), (5, zero8), (3, [0, 0]), (1, [5, 4])], [2] * 5, "crossing sums"),
        ([(5, zero8), (6, [0, 0, 0]), (3, [0, 0]), (1, [5, 5])], [2] * 5, "degree classes"),
    ]
    for sigma, zeta, message in cases:
        with pytest.raises(ValueError, match=message):
            cert.kz_state(A, sigma, zeta)
    with pytest.raises(ValueError, match="non-graphical M=H"):  # odd M degree sum
        cert.kz_state(A, [(6, [0, 0, 0]), (5, zero8), (3, [0, 1]), (1, [5, 5])], [2, 2, 2, 2, 3])


def test_negative_wrong_hilo_partition_and_ranges() -> None:
    bad = deepcopy(cert.hilo_premises(B))
    bad["HI_D"], bad["LO_D"] = bad["HI_D"][:-1], [4, *bad["LO_D"]]
    with pytest.raises(ValueError, match="wrong Hi/Lo partition"):
        cert.validate_hilo_premises(B, bad)
    bad = deepcopy(cert.hilo_premises(B))
    bad["RANGES_BY_SHORE_AND_D"]["HI"]["6"]["B_MAX"] = 12  # ignores LO block-mate capacity
    with pytest.raises(ValueError, match="wrong Hi/Lo range"):
        cert.validate_hilo_premises(B, bad)
    bad = deepcopy(cert.hilo_premises(B))
    bad["UPPER_CONSTANT"] += 1
    with pytest.raises(ValueError, match="wrong Hi/Lo premises"):
        cert.validate_hilo_premises(B, bad)
    for shore, v, b, q, message in (
        ("HI", 6, 0, 0, "complement degree"),
        ("HI", 6, 5, 0, "block-label range"),
        ("HI", 5, 0, 2, "pair-label range"),
        ("LO", 0, 1, 0, "block-label range"),
        ("LO", 1, 3, 0, "block-label range"),
        ("LO", 0, 0, 7, "pair-label range"),
        ("HI", 1, 0, 0, "shore membership"),
    ):
        with pytest.raises(ValueError, match=message):
            cert.validate_hilo_choice(B, shore, v, b, q)
        if (shore, v) != ("HI", 1):
            assert (b, q) not in cert.hilo_choices(B, shore, v)


def test_negative_relaxation_coverage(result: Record) -> None:
    a_cert = result["PROFILES"][A]["ADOPTED_K_Z_CERTIFICATE"]
    cert.validate_kz_coverage(A, a_cert)
    for case in ("drop_state", "count", "argmax", "signatures", "range"):
        bad = deepcopy(a_cert)
        if case == "drop_state":
            bad["RETAINED_STATE_ROWS"].pop()
        elif case == "count":
            bad["RETAINED_STATE_COUNT"] -= 1
        elif case == "argmax":
            bad["ALL_ARGMAX"] = []
        elif case == "signatures":
            bad["SIGMA_SIGNATURES"] -= 1
        else:
            bad["PREMISES"]["SIGMA_RANGE_BY_D"]["1"] = [0, 4]
        with pytest.raises(ValueError):
            cert.validate_kz_coverage(A, bad)
    b_cert = result["PROFILES"][B]["ADOPTED_HI_LO_CERTIFICATE"]
    cert.validate_hilo_coverage(B, b_cert)
    for case in ("drop_cell", "cell_count", "choices", "argmax"):
        bad = deepcopy(b_cert)
        if case == "drop_cell":
            bad["ALL_CELLS"].pop()
        elif case == "cell_count":
            bad["CELL_COUNT"] -= 1
        elif case == "choices":
            bad["CLASS_CHOICES"]["LO"][0]["CHOICES"] = bad["CLASS_CHOICES"]["LO"][0]["CHOICES"][1:]
        else:
            bad["ALL_ARGMAX"].pop()
        with pytest.raises(ValueError):
            cert.validate_hilo_coverage(B, bad)


@pytest.mark.parametrize(
    "pid,cap", [(A, 252), (A, 254), (A, 264), (B, 259), (B, 261), (B, 264), (A, True), (B, 260.0)]
)
def test_negative_illegal_cap(pid: str, cap: object) -> None:
    with pytest.raises(ValueError, match="wrong triangle cap"):
        cert.validate_cap(pid, cap)


def test_negative_swapped_split_adoption(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cert, "ADOPTED_SPLIT", {A: "HI/LO", B: "K/Z"})
    for pid in (A, B):
        with pytest.raises(ValueError, match="not the strongest certificate"):
            cert.certified_cap(pid)


def test_negative_s4_s5_authority(result: Record) -> None:
    _, base, _ = cert.replay_input()
    for pid in (A, B):
        auth = result["PROFILES"][pid]["BASE_AUTHORITY"]
        cert.validate_s4_s5(pid, base, auth)
        for key, value, message in (
            ("S4_BASE", 113, "S4 authority"),
            ("S4_BY_T", {"265": 300000}, "S4 authority"),
            ("S5_USED", True, "S5 authority"),
        ):
            with pytest.raises(ValueError, match=message):
                cert.validate_s4_s5(pid, base, auth | {key: value})
        for damaged in (
            base | {"ALL_T_BONFERRONI_5_ADOPTION": "VERIFIED"},
            base | {"CERTIFICATES_ADOPTED": [*base["CERTIFICATES_ADOPTED"], pid]},
            base | {"INHERITED_TARGET_BONFERRONI_5": {"PROFILE_ID": pid}},
        ):
            with pytest.raises(ValueError, match="S5 authority"):
                cert.validate_s4_s5(pid, damaged, auth)


def test_negative_wrong_base_s4_floor(result: Record, monkeypatch: pytest.MonkeyPatch) -> None:
    _, base, r30 = cert.replay_input()

    def damaged_floor(_: tuple[int, ...]) -> int:
        return 113

    monkeypatch.setattr(cert.route.r28, "profile_s4_floor", damaged_floor)
    for pid in (A, B):
        with pytest.raises(ValueError, match="S4 authority"):
            cert.validate_s4_s5(pid, base, result["PROFILES"][pid]["BASE_AUTHORITY"])
        with pytest.raises(ValueError, match="S4 authority"):
            cert.validate_s4_s5(pid, base, cert.base_authority(pid, r30))
    with pytest.raises(ValueError, match=r"floor applicability|S4 authority"):
        cert.compute_result()


@pytest.mark.parametrize(
    "column,delta,message",
    [
        (2, -1, "K4 ceiling"),
        (2, 1, "K4 ceiling"),
        (3, 1, "A_max contained-K4"),
        (3, -1, "A_max contained-K4"),
        (4, 112, "S4 MAX floor"),
        (4, -1, "S4 MAX floor"),
        (5, 1, "S3 identity"),
        (1, -1, "Fraction ceiling"),
        (1, 1, "Fraction ceiling"),
    ],
)
def test_negative_corrupted_rounding_or_term(
    result: Record, column: int, delta: int, message: str
) -> None:
    for pid in (A, B):
        p = result["PROFILES"][pid]
        terms = [list(t) for t in p["NEW_ALL_T_TERMS"]]
        terms[-1][column] += delta
        with pytest.raises(ValueError, match=message):
            cert.validate_envelope(pid, p["NEW_CAP"], 112, terms)


def test_negative_fraction_floor_on_nonintegral_credit() -> None:
    probe = cert.envelope(A, 253, 113)
    first = probe[0]
    exact = Fraction(308390040 + first[5]) - Fraction(4 * first[4], 7)
    assert exact.denominator == 7 and first[1] == exact.numerator // 7 + 1
    bad = [list(t) for t in probe]
    bad[0][1] = exact.numerator // 7
    with pytest.raises(ValueError, match="Fraction ceiling"):
        cert.validate_envelope(A, 253, 113, bad)


@pytest.mark.parametrize("at", [0, 100, -1])
def test_negative_missing_t_term(result: Record, at: int) -> None:
    for pid in (A, B):
        p = result["PROFILES"][pid]
        terms = list(p["NEW_ALL_T_TERMS"])
        terms.pop(at)
        with pytest.raises(ValueError, match="incomplete envelope"):
            cert.validate_envelope(pid, p["NEW_CAP"], 112, terms)
    with pytest.raises(ValueError, match="T cap range"):
        cert.validate_envelope(A, 21, 112, [])


def test_negative_missing_top_owner(result: Record) -> None:
    resolved = result["RESOLVED_ROWS_BEFORE"]
    cursor = result["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    new = {p: result["PROFILES"][p]["NEW_BOUND"] for p in (A, B)}
    for omitted in (A, B):
        partial = {p: b for p, b in new.items() if p != omitted}
        with pytest.raises(ValueError, match="both maximum owners required"):
            cert.replace_owners(resolved, partial, cert.PROFILE_IDS)
        actual = cert.family_summary(resolved | partial, cursor)
        assert actual["MAXIMUM"] == 313391740 and actual["ALL_MAX_OWNERS"] == [omitted]
        assert cert.family_status(result["FAMILY_BEFORE"], actual, partial) == (
            "NO_PROVEN_FAMILY_GAIN"
        )
    with pytest.raises(ValueError, match="strict owner tightening"):
        cert.replace_owners(resolved, new | {A: resolved[A]}, cert.PROFILE_IDS)
    with pytest.raises(ValueError, match="family row count"):
        cert.family_summary({p: b for p, b in resolved.items() if p != A}, cursor)


@pytest.mark.parametrize(
    "case", ["delete_resolved", "duplicate_resolved", "delete_cursor", "duplicate_cursor"]
)
def test_negative_deleted_or_duplicate_ledger_rows(result: Record, case: str) -> None:
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


def test_negative_duplicate_json_row() -> None:
    with pytest.raises(ValueError, match="duplicate JSON/ledger row"):
        cert.decode(b'{"rows":{"p":1,"p":2}}')


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
    ["profile", "cap", "term", "argmax", "ledger", "cursor", "exclusion", "gain", "status"],
)
def test_negative_complete_payload_tampering(result: Record, case: str) -> None:
    bad = deepcopy(result)
    if case == "profile":
        bad["PROFILES"].pop(B)
    elif case == "cap":
        bad["PROFILES"][A]["NEW_CAP"] -= 1
    elif case == "term":
        bad["PROFILES"][B]["NEW_ALL_T_TERMS"].pop(100)
    elif case == "argmax":
        bad["PROFILES"][A]["NEW_ALL_ARGMAX"] = []
    elif case == "ledger":
        bad["RESOLVED_ROWS_AFTER"][A] = bad["RESOLVED_ROWS_BEFORE"][A]
    elif case == "cursor":
        first = next(iter(bad["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]))
        bad["CURSOR_197_PRESERVED"]["ROW_BOUNDS"][first] += 1
    elif case == "exclusion":
        bad["INHERITED_EXCLUSION"]["ORIGINAL_CONDITIONS_VERBATIM"]["COUNT"] -= 1
    elif case == "gain":
        bad["FAMILY_DELTA"] += 1
    else:
        bad["TASK_STATUS"] = "NO_PROVEN_FAMILY_GAIN"
    with pytest.raises(ValueError, match="complete recomputation"):
        cert.validate_payload(bad, result)


def test_stored_result_exact_recomputation(result: Record) -> None:
    cert.verify_result()
    stored = json.loads((cert.ROOT / cert.RESULT).read_bytes())
    assert cert.render(stored) == cert.render(result)
    assert stored["TASK_STATUS"] == "PROVEN_FAMILY_GAIN"
