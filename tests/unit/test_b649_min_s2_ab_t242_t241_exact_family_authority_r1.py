"""Focused universal proof, exhaustive local census, and authority mutation tests."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from itertools import combinations, product
from math import comb
from typing import cast

import pytest

from lottolab.research import b649_min_s2_ab_t242_t241_exact_family_authority_r1 as v


@pytest.fixture(scope="module")
def base() -> v.Document:
    return v.load_inputs()[0]


@pytest.fixture(scope="module")
def result() -> v.Document:
    value = v.compute_result()
    assert (v.ROOT / v.RESULT).read_bytes() == v.render(value)
    return value


def test_pinned_sources_and_original_dispositions(result: v.Document) -> None:
    pins = v.obj(result["PROVENANCE"])
    assert pins["BASE_HEAD"] == v.BASE_HEAD and pins["BASE_TREE"] == v.BASE_TREE
    assert pins["BASE_RESULT_SHA256"] == v.BASE_SHA
    assert pins["DONOR_HEAD"] == v.DONOR_HEAD and pins["DONOR_TREE"] == v.DONOR_TREE
    assert pins["DONOR_SOURCE_SHA256"] == v.DONOR_SOURCE_SHA
    assert pins["DONOR_RESULT_SHA256"] == v.DONOR_SHA
    assert pins["DONOR_ORIGINAL_STATUS"] == [
        "PROVEN_FAMILY_GAIN",
        "CONDITIONAL_PROJECTION",
        "NOT_CANONICAL_ADOPTION",
    ]
    assert pins["DONOR_B_SHARED_242_PROJECTION_ADOPTED"] is False
    assert result["HISTORICAL_R15"] == "NOT_VERIFIED"
    assert result["HISTORICAL_A14"] == "NOT_UPGRADED"
    assert result["LEGAL_ATTAINMENT"] == result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["HEAVY_SOLVER_STARTED"] == result["REMOTE_WRITE"] == "NO"
    assert v.obj(result["G01_TO_G18_AT_SEAL"]) == {f"G{i:02}": "PASS" for i in range(1, 19)}


@pytest.mark.parametrize("pid,j,cap,constant", [(v.A, 2339, 242, 5961), (v.B, 2340, 241, 5960)])
def test_exact_profiles_and_model(pid: str, j: int, cap: int, constant: int) -> None:
    facts = v.facts(pid)
    assert [facts[k] for k in ("SUM_D", "E", "W", "GOODMAN_SUM", "A_MAX")] == [
        66,
        93,
        830,
        296,
        199,
    ]
    assert facts["SUM_CHOOSE3_DEGREES"] == j
    v.validate_profile_binding(pid, cap, constant)


def test_exhaustive_graphicality_three_methods(result: v.Document) -> None:
    rows = cast(list[list[int]], result["ZERO_GRAPHICAL_CLASSIFICATION"])
    assert len(rows) == 462 and len({tuple(r[:6]) for r in rows}) == 462
    assert all(r[-3] == r[-2] == r[-1] for r in rows)
    assert sum(r[-1] for r in rows) == 102
    frequencies = cast(list[list[object]], result["ZERO_ZETA_AND_LABELLED_GRAPH_FREQUENCIES"])
    assert len(frequencies) == 102
    assert sum(v.integer(row[1]) for row in frequencies) == 32768
    # Every labelled list maps to one of the exhaustively checked multisets.
    for d in product(range(6), repeat=6):
        assert v.erdos_gallai(d) == v.havel_hakimi(d)
    assert not v.erdos_gallai((-1, 1)) and not v.havel_hakimi((6,) * 6)


@pytest.mark.parametrize(
    "pid,sigma_count,state_count,maxima",
    [
        (v.A, 648, 844, [242, 242, 238, 232, 228, 226, 220]),
        (v.B, 540, 683, [241, 235, 231, 229, 228, 226, 220]),
    ],
)
def test_complete_necessary_domains(
    pid: str, sigma_count: int, state_count: int, maxima: list[int]
) -> None:
    proof = v.enumeration(pid)
    rows = cast(list[list[int]], proof["COMPLETE_DOMAIN"])
    assert proof["CANONICAL_SIGMA"] == sigma_count
    assert len(rows) == proof["EQUAL_SUM_STATES"] == state_count
    assert len({tuple(r) for r in rows}) == state_count
    assert max(r[-1] for r in rows) == proof["UNIVERSAL_T_CAP"] == v.CAPS[pid]
    assert proof["INDEPENDENT_DOMAIN_AND_VALUES_EQUAL"] is True
    assert proof["DOMAIN_SHA256"] == v.sha(v.render(rows))
    assert v.obj(proof["R_CLASS_MAXIMA"]) == {
        str(r): m for r, m in zip(range(6, 19, 2), maxima, strict=True)
    }
    assert proof["LEGAL_ATTAINMENT"] == "UNKNOWN"
    assert all(sum(r[:14]) == sum(r[14:20]) for r in rows)
    for row in rows:
        assert all(
            0 <= sigma <= 6 - d for sigma, d in zip(row[:14], v.degrees(pid)[:14], strict=True)
        )
        assert v.erdos_gallai([6 - x for x in row[14:20]])
    if pid == v.A:
        assert proof["INDEPENDENT_LABELLED_GRAPH_CONFIGURATIONS"] == 1849624
        assert proof["LABELLED_DEGREE_SEQUENCE_CONFIGURATIONS"] == 787316


@pytest.mark.parametrize("pid", v.PROFILES)
def test_partition_identity_on_simple_graph_realization(pid: str) -> None:
    # A degree realization checks the identity, without claiming legal supports.
    degrees = [6 + d for d in v.degrees(pid)]
    remaining = degrees.copy()
    adj = [set[int]() for _ in degrees]
    while any(remaining):
        order = sorted(range(20), key=lambda i: (-remaining[i], i))
        x = order[0]
        need, remaining[x] = remaining[x], 0
        for y in order[1 : need + 1]:
            assert remaining[y] > 0
            remaining[y] -= 1
            adj[x].add(y)
            adj[y].add(x)

    def count_triangles(vertices: range, edges: set[tuple[int, int]]) -> int:
        return sum({(a, b), (a, c), (b, c)} <= edges for a, b, c in combinations(vertices, 3))

    for _ in range(6):
        edges = {(a, b) for a, b in combinations(range(20), 2) if b in adj[a]}
        missing = set(combinations(range(20), 2)) - edges
        m = {(a, b) for a, b in missing if b < 14}
        n = {(a, b) for a, b in missing if a >= 14}
        k, z = set(range(14)), set(range(14, 20))
        sigma = [len(adj[x] & z) for x in range(14)]
        zeta = [len(adj[u] & k) for u in range(14, 20)]
        r = sum(sigma)
        assert r == sum(zeta) and 2 * len(m) == 32 + r and 2 * len(n) == r - 6
        parts = (
            count_triangles(range(14), m),
            count_triangles(range(14, 20), n),
            sum(len(adj[x] & adj[y] & z) for x, y in m),
            sum(len(adj[u] & adj[w] & k) for u, w in n),
        )
        f = (
            242
            - 10 * r
            + sum(s * (7 - d + s) for s, d in zip(sigma, v.degrees(pid)[:14], strict=True))
        )
        f += sum(x * (x - 1) for x in zeta)
        actual = count_triangles(range(20), edges)
        assert all(p >= 0 for p in parts) and sum(parts) > 0
        assert actual == v.split_value(f, parts)
        assert actual + count_triangles(range(20), missing) == 296
        assert [len(a) for a in adj] == degrees
        # Deterministic two-switch gives another independent degree realization.
        for (a, b), (c, d) in combinations(sorted(edges), 2):
            if len({a, b, c, d}) == 4 and c not in adj[a] and d not in adj[b]:
                for x, y in ((a, b), (c, d)):
                    adj[x].remove(y)
                    adj[y].remove(x)
                for x, y in ((a, c), (b, d)):
                    adj[x].add(y)
                    adj[y].add(x)
                break


def test_exact_event_weights_and_bonferroni_polynomial() -> None:
    weights = v.local_weights()
    assert weights == {
        "S1": 372228640,
        "S2": 63838600,
        "OPEN_WEDGE": 2800,
        "PAIR_TRIANGLE": 20272,
        "SHARED_TRIPLE": 7000,
        "K4_PAIR": 679,
        "K4_WITH_TRIPLE": 448,
    }
    assert weights["S1"] == 20 * 7 * sum(comb(6, h) * comb(43, 7 - h) for h in range(3, 7))
    for q in range(8):
        assert 7 * (q - comb(q, 2) + comb(q, 3) - int(q > 0)) >= 4 * comb(q, 4)


@pytest.mark.parametrize(
    "pid,cap,terms,bound,delta",
    [
        (v.A, 242, 221, 313195248, 197164),
        (v.B, 241, 220, 313186092, 206320),
    ],
)
def test_every_old_and_new_route_b_term(
    pid: str, cap: int, terms: int, bound: int, delta: int, result: v.Document
) -> None:
    old, new = v.envelope(pid, 264), v.envelope(pid, cap)
    assert len(old) == 243 and len(new) == terms and old[:terms] == new
    assert max(t[1] for t in old) == 313392412
    assert max(t[1] for t in new) == bound and 313392412 - bound == delta
    for t, rounded, k, a, s4, s3 in old:
        assert k == max(0, -(-(30 * t - v.K4_CONSTANTS[pid]) // 4))
        assert a == min(k, 199) and s4 == max(112, 679 * k - 231 * a)
        assert s3 == 2800 * (830 - 3 * t) + 20272 * (t - 22) + 154000
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        assert 0 <= rounded - exact < 1
    if pid == v.A:
        assert new[-1][2:5] == (325, 199, 174706)
    value = v.obj(v.obj(result["PROFILES"])[pid])
    assert value["STRICT_GAIN_EXCLUDED"] is True
    assert v.integer(value["NEW_FULL_BOUND"]) < v.INCUMBENT


def test_exact_two_row_composition_and_entire_cursor(base: v.Document, result: v.Document) -> None:
    before, after = v.obj(base["RESOLVED_ROW_BOUNDS"]), v.obj(result["RESOLVED_ROW_BOUNDS"])
    assert len(before) == len(after) == 4647
    assert {p for p in before if before[p] != after[p]} == {v.A, v.B}
    assert after[v.A] == 313195248 and after[v.B] == 313186092
    assert result["OTHER_ROWS_UNCHANGED"] == 4645 and result["ROWS_UPDATED"] == 2
    assert result["CURSOR"] == base["CURSOR"] and result["CURSOR_PROFILES"] == 197
    assert result["CURSOR_PRESERVED"] is True
    assert v.obj(result["FAMILY_AFTER_A_ONLY"]) == {
        "FAMILY_BOUND": 313392412,
        "OWNER_IDS": [v.B],
        "GAP_TO_INCUMBENT": 128524,
        "STILL_OPEN_PROFILE_COUNT": 1559,
    }
    assert v.obj(result["FAMILY_AFTER_B_ONLY"]) == {
        "FAMILY_BOUND": 313392412,
        "OWNER_IDS": [v.A],
        "GAP_TO_INCUMBENT": 128524,
        "STILL_OPEN_PROFILE_COUNT": 1559,
    }
    assert result["FAMILY_AFTER_BOTH"] == {
        "FAMILY_BOUND": 313392308,
        "OWNER_IDS": ["66665555555421000000"],
        "GAP_TO_INCUMBENT": 128420,
        "STILL_OPEN_PROFILE_COUNT": 1558,
    }
    assert result["FAMILY_DELTA"] == 104
    inherited = v.obj(result["INHERITED_BASE_CAVEATS"])
    assert all(inherited[k] == base[k] for k in inherited)


@pytest.mark.parametrize(
    "pid,cap,constant",
    [
        (v.A, 241, 5961),
        (v.B, 242, 5960),
        (v.A, 242, 5960),
        (v.B, 241, 5961),
        ("65555555555541000000", 242, 5961),
    ],
)
def test_rejects_swapped_profile_cap_or_k4(pid: str, cap: int, constant: int) -> None:
    with pytest.raises(ValueError):
        v.validate_profile_binding(pid, cap, constant)


@pytest.mark.parametrize("key", list(v.MODEL))
def test_rejects_frozen_model_mutation(key: str) -> None:
    bad = dict(v.MODEL)
    bad[key] = False if key == "PAIR_LINEARITY" else v.integer(bad[key]) + 1
    with pytest.raises(ValueError, match="frozen support model"):
        v.facts(v.A, bad)


def test_rejects_wrong_graphicality_claim() -> None:
    zeta = (2, 2, 2, 2, 2, 6)
    assert not v.erdos_gallai(zeta) and v.erdos_gallai([6 - x for x in zeta])
    v.validate_zeta(zeta)
    with pytest.raises(ValueError, match="6-zeta"):
        v.validate_zeta(zeta, "zeta")
    with pytest.raises(ValueError, match="6-zeta is not graphical"):
        v.validate_zeta((1, 1, 1, 1, 1, 2))


@pytest.mark.parametrize(
    "parts", [(-1, 0, 0, 0), (0, -1, 0, 0), (0, 0, -1, 0), (0, 0, 0, -1), (0, 0, 0)]
)
def test_rejects_negative_p_counts(parts: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="nonnegative P"):
        v.remainder(parts)


def test_rejects_reversed_correction_sign() -> None:
    with pytest.raises(ValueError, match="P correction sign"):
        v.split_value(242, (1, 2, 3, 4), sign=1)


@pytest.mark.parametrize("pid", v.PROFILES)
@pytest.mark.parametrize("damage", ["missing", "duplicate", "maximum"])
def test_rejects_incomplete_canonical_domain(pid: str, damage: str) -> None:
    bad = deepcopy(v.enumeration(pid))
    rows = cast(list[list[int]], bad["COMPLETE_DOMAIN"])
    if damage == "missing":
        rows.pop()
    elif damage == "duplicate":
        rows[-1] = rows[0].copy()
    else:
        bad["UNIVERSAL_T_CAP"] = v.CAPS[pid] - 1
    with pytest.raises(ValueError, match="incomplete canonical"):
        v.validate_enumeration(pid, bad)


@pytest.mark.parametrize("pid", v.PROFILES)
@pytest.mark.parametrize("damage", ["missing", "rounding", "k4", "s3", "s4", "contained"])
def test_rejects_incomplete_or_corrupt_terms(pid: str, damage: str) -> None:
    terms = [list(t) for t in v.envelope(pid, v.CAPS[pid])]
    if damage == "missing":
        terms.pop(11)
    else:
        column = {"rounding": 1, "k4": 2, "contained": 3, "s4": 4, "s3": 5}[damage]
        terms[-1][column] += 1
    with pytest.raises(ValueError, match=r"T terms|rounding"):
        v.validate_terms(pid, v.CAPS[pid], terms)


def test_rejects_b_cap_downgrade_to_shared242() -> None:
    with pytest.raises(ValueError, match="T domain"):
        v.envelope(v.B, 242)


@pytest.mark.parametrize(
    "damage", ["duplicate_update", "missing_update", "wrong_bound", "duplicate_row", "missing_row"]
)
def test_rejects_bad_composition(damage: str, base: v.Document) -> None:
    rows, cursor = v.replay_base(base)
    pairs = list(rows.items())
    updates = [(p, v.BOUNDS[p]) for p in v.PROFILES]
    if damage == "duplicate_update":
        updates.append(updates[0])
    elif damage == "missing_update":
        updates.pop()
    elif damage == "wrong_bound":
        updates[-1] = (v.B, v.BOUNDS[v.A])
    elif damage == "duplicate_row":
        pairs.append(pairs[0])
    else:
        pairs.pop()
    with pytest.raises(ValueError, match="family row"):
        v.apply_updates(pairs, cursor, base, updates)


@pytest.mark.parametrize("damage", ["id", "bound", "coverage", "status"])
def test_rejects_cursor_mutation(damage: str, base: v.Document) -> None:
    rows, cursor = v.replay_base(base)
    bad = deepcopy(cursor)
    if damage == "id":
        cast(list[str], bad["PROFILE_IDS"])[0] = v.A
    elif damage == "bound":
        bounds = v.obj(bad["COARSE_BOUND_PROJECTION"])
        key = next(iter(bounds))
        bounds[key] = v.integer(bounds[key]) + 1
    elif damage == "coverage":
        bad["PARTITION"] = {}
    else:
        bad["STATUS"] = "MUTATED"
    with pytest.raises(ValueError, match="cursor mutation"):
        v.apply_updates(list(rows.items()), bad, base, [(p, v.BOUNDS[p]) for p in v.PROFILES])


@pytest.mark.parametrize(
    "head,tree,path,digest",
    [
        (v.BASE_HEAD, v.BASE_TREE, v.BASE_RESULT, "0" * 64),
        (v.DONOR_HEAD, v.DONOR_TREE, v.DONOR_SOURCE, "0" * 64),
        (v.DONOR_HEAD, v.DONOR_TREE, v.DONOR_RESULT, "0" * 64),
        (v.BASE_HEAD, v.DONOR_TREE, v.BASE_RESULT, v.BASE_SHA),
    ],
)
def test_rejects_source_hash_or_result_identity(
    head: str, tree: str, path: str, digest: str
) -> None:
    with pytest.raises(ValueError, match=r"identity|hash"):
        v.checked_blob(head, tree, path, digest)


@pytest.mark.parametrize("damage", ["swapped_profiles", "result_identity"])
def test_rejects_damaged_result(damage: str, result: v.Document) -> None:
    bad = deepcopy(result)
    if damage == "swapped_profiles":
        profiles = v.obj(bad["PROFILES"])
        profiles[v.A], profiles[v.B] = profiles[v.B], profiles[v.A]
    else:
        bad["SOURCE_SHA256"] = "0" * 64
    with pytest.raises(ValueError, match="result identity"):
        v.verify_result(bad)
