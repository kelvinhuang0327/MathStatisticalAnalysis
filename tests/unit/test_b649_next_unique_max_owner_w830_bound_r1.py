"""Independent W830 state recount, graph identities and executable rejection gates."""

from __future__ import annotations

import json
import random
from collections import Counter
from collections.abc import Sequence
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, product
from math import comb
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_next_unique_max_owner_w830_bound_r1 as cert

type Record = dict[str, Any]
type Adjacency = list[set[int]]
P = cert.PROFILE


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


def test_input_pins_and_complete_frontier(result: Record) -> None:
    assert cert.git("rev-parse", cert.INPUT_HEAD + "^{tree}") == cert.INPUT_TREE
    assert cert.git("rev-parse", cert.BASE_HEAD + "^{tree}") == cert.BASE_TREE
    assert result["FAMILY_BEFORE"]["MAXIMUM"] == 313391636
    assert result["FAMILY_BEFORE"]["ALL_MAX_OWNERS"] == [P]
    assert result["FAMILY_BEFORE"]["NEXT_DISTINCT_BOUND"] == 313391560
    assert result["FAMILY_BEFORE"]["ALL_NEXT_DISTINCT_OWNERS"] == ["65555555555432100000"]
    assert result["EVALUATOR_SOURCE_PINS"] == cert.upstream.r2.source_pins()


def test_independent_profile_facts(result: Record) -> None:
    d = list(map(int, P))
    g = [6 + x for x in d]
    facts = result["FACTS"]
    assert Counter(d) == {6: 4, 5: 7, 3: 1, 2: 1, 1: 2, 0: 5}
    assert len(d) == 20 and sum(d) == 66 and sum(x * x for x in d) == 334
    assert facts["EDGES"] == sum(g) // 2 == 93
    assert facts["WEDGES"] == sum(x * (x - 1) // 2 for x in g) == 830
    assert facts["GOODMAN"] == 1140 - sum(x * (19 - x) for x in g) // 2 == 296
    assert (facts["K"], facts["Z"]) == (15, 5)
    assert facts["J"] == sum(comb(x, 3) for x in g) == 2345
    assert facts["A_MAX_NUMERATOR"] == sum(x * (x + 4) for x in d) == 598
    assert facts["A_MAX"] == 598 // 3 == 199
    cert.validate_facts(P, facts)


def test_independent_recount_all_states_and_argmax(result: Record) -> None:
    rows = kz_recount(P)
    ours = result["K_Z_CERTIFICATE"]
    assert len(rows) == ours["RETAINED_STATE_COUNT"] == 2897
    assert sorted(rows) == sorted(ours["RETAINED_STATE_ROWS"])
    values = [int(r.rsplit("=", 1)[1]) for r in rows]
    assert max(values) == ours["CAP"] == 257
    assert ours["SIGMA_SIGNATURES"] == 1 * 8 * 4 * 5 * 21 == 3360
    assert ours["ZETA_MULTISETS_IN_RANGE"] == comb(9, 5) == 126
    assert ours["GRAPHICAL_ZETA_MULTISETS"] == 31
    assert ours["RANGE_STATES_WITH_EQUAL_CROSSING_SUMS"] == 11410
    assert ours["REJECTED_BY_FIRST_FAILED_CONDITION"] == {
        "bipartite crossing inequalities": 8,
        "non-graphical G[Z]": 3120,
        "non-graphical M=H[K]": 5385,
    }
    assert 2897 + sum(ours["REJECTED_BY_FIRST_FAILED_CONDITION"].values()) == 11410
    top_rows = [r for r in rows if int(r.rsplit("=", 1)[1]) == max(values)]
    assert top_rows == [cert.kz_state_row(s) for s in ours["ALL_ARGMAX"]]
    [top] = ours["ALL_ARGMAX"]
    assert top["R"] == 16 and top["ZETA"] == [2, 3, 3, 3, 5]
    assert top["SIGMA_BY_D"] == [
        [6, [0] * 4],
        [5, [0] * 5 + [1] * 2],
        [3, [0]],
        [2, [4]],
        [1, [5, 5]],
    ]
    assert top["WITHOUT_REMAINDER"] == 268
    assert top["REMAINDER_LOWER"] == {"T_M": 5, "T_N": 0, "C_K": 6, "C_Z": 0}
    assert ours["PREMISES"]["UPPER_CONSTANT"] == 236
    cert.validate_kz_coverage(P, ours)


def test_base_authority_and_every_envelope_term(result: Record) -> None:
    auth = result["BASE_AUTHORITY"]
    assert auth["R30_ATTEMPT"]["ATTEMPT_INDEX"] == 3738
    assert (auth["ACCEPTED_R30_CAP"], auth["NB_CAP"], auth["CLASS_CAP"]) == (264, 265, 275)
    assert auth["S4_BASE"] == 112 and auth["S4_BY_T"] == {} and auth["S5_USED"] is False
    assert result["S4_S5_AUTHORITY"]["K4_WEIGHTS_REEXECUTED"] == {
        "SIX_EDGES_WITH_CONTAINED_TRIPLE": 448,
        "SIX_EDGES_WITHOUT_CONTAINED_TRIPLE": 679,
    }
    assert (result["OLD_CAP"], result["NEW_CAP"]) == (264, 257)
    for prefix, cap, bound in (("OLD", 264, 313391636), ("NEW", 257, 313329096)):
        terms = [own_term(P, t) for t in range(22, cap + 1)]
        assert result[prefix + "_ALL_T_TERMS"] == terms
        assert result[prefix + "_BOUND"] == max(t[1] for t in terms) == bound
        assert result[prefix + "_ALL_ARGMAX"] == [t for t in terms if t[1] == bound] == [terms[-1]]
    assert result["FULL_ENVELOPE_TERM_COUNTS"] == {
        "OLD": 243,
        "NEW": 236,
        "OLD_T_RANGE": [22, 264],
        "NEW_T_RANGE": [22, 257],
    }
    assert result["OLD_ALL_ARGMAX"] == [(264, 313391636, 492, 199, 288099, 5166224)]
    assert result["NEW_ALL_ARGMAX"] == [(257, 313329096, 439, 199, 252112, 5083120)]
    assert result["NEW_BOUND_WITH_S4_FLOOR_ZERO"] == max(
        own_term(P, t, 0)[1] for t in range(22, 258)
    )


def test_complete_family_and_historical_preservation(result: Record) -> None:
    fixed = cert.decode(cert.blob(cert.INPUT_HEAD, cert.INPUT_RESULT))
    base = cert.decode(cert.blob(cert.BASE_HEAD, cert.BASE_RESULT))
    before, after = result["RESOLVED_ROWS_BEFORE"], result["RESOLVED_ROWS_AFTER"]
    cursor = result["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    assert before == fixed["RESOLVED_ROWS_AFTER"] and len(before) == len(after) == 4647
    assert cursor == fixed["CURSOR_197_PRESERVED"]["ROW_BOUNDS"] and len(cursor) == 197
    assert {p for p in before if before[p] != after[p]} == {P}
    assert after[P] == result["NEW_BOUND"]
    merged = after | cursor
    levels = sorted(set(merged.values()), reverse=True)
    assert result["FAMILY_AFTER"]["MAXIMUM"] == levels[0] == 313391560
    assert result["ALL_NEW_MAX_OWNERS"] == sorted(p for p, b in merged.items() if b == levels[0])
    assert result["ALL_NEW_MAX_OWNERS"] == ["65555555555432100000"]
    assert result["NEXT_DISTINCT_BOUND"] == levels[1]
    assert result["FAMILY_AFTER"]["ALL_NEXT_DISTINCT_OWNERS"] == sorted(
        p for p, b in merged.items() if b == levels[1]
    )
    assert result["FAMILY_DELTA"] == result["FAMILY_BEFORE"]["MAXIMUM"] - levels[0] == 76
    assert result["GAP_TO_INCUMBENT"] == levels[0] - 313263888 == 127672
    assert result["TASK_STATUS"] == "PROVEN_FAMILY_GAIN"
    assert result["LEDGER_PARTITION"]["EXCLUDED_COUNT"] == 282
    assert result["INHERITED_EXCLUSION"] == fixed["INHERITED_EXCLUSION"]
    assert result["INHERITED_CAVEATS_REFERENCE"] == fixed["INHERITED_CAVEATS_REFERENCE"]
    assert (
        result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
        == base["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
    )
    assert result["HISTORICAL_CERTIFICATES_RECERTIFIED"] is False
    assert result["SOLVER_CALLS"] == result["FULL_SUPPORT_GRAPHS_ENUMERATED"] == 0
    assert result["PORTFOLIOS_ENUMERATED"] == result["SAMPLED_REALIZATIONS_USED_FOR_BOUNDS"] == 0


@pytest.mark.parametrize("pid", ["66655555555331100000", "66665555555321100001", "", P[:-1]])
def test_negative_wrong_profile(pid: str) -> None:
    with pytest.raises(ValueError, match="wrong exact profile"):
        cert.profile_facts(pid)
    with pytest.raises(ValueError, match="wrong exact profile"):
        cert.kz_premises(pid)


@pytest.mark.parametrize("key,value", [("WEDGES", 827), ("GOODMAN", 293), ("K", 16), ("Z", 4)])
def test_negative_wrong_oracle(result: Record, key: str, value: int) -> None:
    with pytest.raises(ValueError, match="wrong profile fact: " + key):
        cert.validate_facts(P, result["FACTS"] | {key: value})


@pytest.mark.parametrize("case", ["partition", "sigma", "zeta", "constant"])
def test_negative_wrong_premises(case: str) -> None:
    bad = deepcopy(cert.kz_premises(P))
    if case == "partition":
        bad["Z"] = 4
    elif case == "sigma":
        bad["SIGMA_RANGE_BY_D"]["2"] = [0, 3]
    elif case == "zeta":
        bad["ZETA_RANGE"] = [3, 6]
    else:
        bad["UPPER_CONSTANT"] = 233
    with pytest.raises(ValueError):
        cert.validate_kz_premises(P, bad)


@pytest.mark.parametrize("case", ["sigma", "zeta", "sums", "classes", "graphical"])
def test_negative_invalid_states(result: Record, case: str) -> None:
    top = result["K_Z_CERTIFICATE"]["ALL_ARGMAX"][0]
    sig, zet = deepcopy(top["SIGMA_BY_D"]), list(top["ZETA"])
    if case == "sigma":
        sig[0][1][0] = 1
    elif case == "zeta":
        zet[0] = 1
    elif case == "sums":
        zet[-1] = 6
    elif case == "classes":
        sig.pop()
    else:
        sig[1][1][0] = 1
        zet[-1] = 6  # equal sums but odd degree parity
    with pytest.raises(ValueError):
        cert.kz_state(P, sig, zet)


@pytest.mark.parametrize(
    "case", ["drop_state", "count", "argmax", "signatures", "range", "remainder"]
)
def test_negative_relaxation_coverage(result: Record, case: str) -> None:
    bad = deepcopy(result["K_Z_CERTIFICATE"])
    if case == "drop_state":
        bad["RETAINED_STATE_ROWS"].pop()
    elif case == "count":
        bad["RETAINED_STATE_COUNT"] -= 1
    elif case == "argmax":
        bad["ALL_ARGMAX"] = []
    elif case == "signatures":
        bad["SIGMA_SIGNATURES"] -= 1
    elif case == "remainder":
        bad["ALL_ARGMAX"][0]["REMAINDER_LOWER"]["T_M"] += 1
    else:
        bad["PREMISES"]["SIGMA_RANGE_BY_D"]["2"] = [0, 3]
    with pytest.raises(ValueError):
        cert.validate_kz_coverage(P, bad)


@pytest.mark.parametrize("cap", [256, 258, 264, True, 257.0])
def test_negative_wrong_cap(cap: object) -> None:
    with pytest.raises(ValueError, match="wrong triangle cap"):
        cert.validate_cap(P, cap)


@pytest.mark.parametrize("case", ["floor", "by_t", "s5", "adopted", "all_t"])
def test_negative_s4_s5_authority(result: Record, case: str) -> None:
    base = cert.decode(cert.blob(cert.BASE_HEAD, cert.BASE_RESULT))
    auth = deepcopy(result["BASE_AUTHORITY"])
    if case == "floor":
        auth["S4_BASE"] = 113
    elif case == "by_t":
        auth["S4_BY_T"] = {"257": 300000}
    elif case == "s5":
        auth["S5_USED"] = True
    elif case == "adopted":
        base["CERTIFICATES_ADOPTED"][P] = 257
    else:
        base["ALL_T_BONFERRONI_5_ADOPTION"] = "VERIFIED"
    with pytest.raises(ValueError, match=r"S[45] authority"):
        cert.validate_s4_s5(P, base, auth)


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
def test_negative_wrong_rounding(result: Record, column: int, delta: int, message: str) -> None:
    bad = [list(t) for t in result["NEW_ALL_T_TERMS"]]
    bad[-1][column] += delta
    with pytest.raises(ValueError, match=message):
        cert.validate_envelope(P, result["NEW_CAP"], 112, bad)


def test_negative_fraction_floor() -> None:
    probe = cert.envelope(P, 257, 113)
    exact = Fraction(308390040 + probe[0][5]) - Fraction(4 * probe[0][4], 7)
    assert exact.denominator == 7
    bad = [list(t) for t in probe]
    bad[0][1] = exact.numerator // exact.denominator
    with pytest.raises(ValueError, match="Fraction ceiling"):
        cert.validate_envelope(P, 257, 113, bad)


@pytest.mark.parametrize("at", [0, 100, -1])
def test_negative_missing_t(result: Record, at: int) -> None:
    bad = list(result["NEW_ALL_T_TERMS"])
    bad.pop(at)
    with pytest.raises(ValueError, match="incomplete envelope"):
        cert.validate_envelope(P, 257, 112, bad)


def test_negative_missing_owner_and_wrong_family(result: Record) -> None:
    resolved = result["RESOLVED_ROWS_BEFORE"]
    cursor = result["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    with pytest.raises(ValueError, match="complete unique maximum owner"):
        cert.replace_owner(resolved, {}, [])
    with pytest.raises(ValueError, match="strict owner tightening"):
        cert.replace_owner(resolved, {P: resolved[P]}, [P])
    with pytest.raises(ValueError, match="family row count"):
        cert.family_summary({p: b for p, b in resolved.items() if p != P}, cursor)
    damaged_fields: list[tuple[str, object]] = [
        ("MAXIMUM", 313391560),
        ("ALL_MAX_OWNERS", []),
        ("NEXT_DISTINCT_BOUND", 0),
    ]
    for key, value in damaged_fields:
        with pytest.raises(ValueError, match="wrong family aggregation"):
            cert.validate_family(resolved, cursor, result["FAMILY_BEFORE"] | {key: value})
    assert cert.family_summary(resolved, cursor)["MAXIMUM"] == 313391636


@pytest.mark.parametrize(
    "case", ["delete_resolved", "duplicate_resolved", "delete_cursor", "duplicate_cursor"]
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
        bad["PROFILE_ID"] = "66655555555331100000"
    elif case == "cap":
        bad["NEW_CAP"] -= 1
    elif case == "term":
        bad["NEW_ALL_T_TERMS"].pop(100)
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

    # Use the actual verify_result reader; no committed or working file is changed.
    if cert.git("rev-parse", "HEAD") == cert.INPUT_HEAD:
        monkeypatch.setattr(Path, "read_bytes", damaged_read)
    else:
        original_blob = cert.blob

        def damaged_blob(head: str, path: str, repo: Path = cert.ROOT) -> bytes:
            return damaged if path == cert.RESULT else original_blob(head, path, repo)

        monkeypatch.setattr(cert, "blob", damaged_blob)
    with pytest.raises(ValueError, match="stored result differs from complete recomputation"):
        cert.verify_result()
