"""Focused complete-domain, arithmetic and malformed-certificate checks."""

from __future__ import annotations

import copy
import json
from itertools import combinations
from typing import cast

import pytest

from lottolab.research import b649_min_s2_666655555553211_t257_formal_r2 as c


@pytest.fixture(scope="module")
def result() -> c.Document:
    return cast(c.Document, json.loads((c.ROOT / c.RESULT).read_bytes()))


def test_deterministic_certificate_and_complete_recounts(result: c.Document) -> None:
    c.verify_result(result)
    a, b = c.enumerate_a(), c.enumerate_b()
    assert a == b and len(a) == len({state for state, _ in a}) == 2897
    assert max(c.integer(r["RAW"]) for _, r in a) == 280
    assert max(c.integer(r["UPPER"]) for _, r in a) == 257
    assert c.obj(result["ENUMERATION"])["STATES"] == [r for _, r in a]
    assert result["PROVEN_T_CAP"] == 257 and result["FULL_PROFILE_BOUND"] == 313329096
    assert result["PROFILE_DELTA"] == 62540 and result["STRICT_GAIN_EXCLUDED"] is False


def test_frozen_facts_and_full_route_b(result: c.Document) -> None:
    assert c.facts()["SUM_D"] == 66
    assert [c.facts()[k] for k in ("E", "W", "J", "GOODMAN", "A_MAX")] == [93, 830, 2345, 296, 199]
    old, new = c.envelope(264), c.envelope(257)
    assert len(old) == 243 and len(new) == 236 and old[:236] == new
    assert old[-1] == (264, 313391636, 492, 199, 288099, 5166224)
    assert new[-1] == (257, 313329096, 439, 199, 252112, 5083120)
    assert max(t[1] for t in old) == 313391636 and max(t[1] for t in new) == 313329096
    assert result["S5"] == "NOT_PINNED / NOT_USED"
    assert c.arithmetic_audit()["K4_WITH_TRIPLE"] == 448


def test_all_five_vertex_graphs_and_every_subset() -> None:
    # Real graph enumeration establishes non-vacuous floors against actual
    # triangles and induced edges, independently of both degree enumerators.
    edges = list(combinations(range(5), 2))
    signatures: set[c.Degrees] = set()
    for mask in range(1024):
        adjacency = [set[int]() for _ in range(5)]
        for bit, (i, j) in enumerate(edges):
            if mask & (1 << bit):
                adjacency[i].add(j)
                adjacency[j].add(i)
        ds = tuple(len(a) for a in adjacency)
        signatures.add(tuple(sorted(ds)))
        triangles = sum(
            j in adjacency[i] and k in adjacency[i] and k in adjacency[j]
            for i, j, k in combinations(range(5), 3)
        )
        assert c.graphical_eg(ds) and c.graphical_hh(ds)
        assert c.floors_a(ds) == c.floors_b(ds)
        assert max(c.floors_a(ds)) <= triangles
        for subset in range(32):
            selected = {i for i in range(5) if subset & (1 << i)}
            actual = sum(j in adjacency[i] for i, j in combinations(selected, 2))
            lower = max(0, sum(sorted(ds)[: len(selected)]) - sum(ds) // 2)
            assert lower <= actual
    assert len(signatures) == 31


def test_exact_split_identity_and_four_nonnegative_counts() -> None:
    # Arbitrary observed graph, with independent direct triangle counting.
    # The generic split identity does not require a realizable support profile.
    size, k = 20, 15
    g = [set[int]() for _ in range(size)]
    for i, j in combinations(range(size), 2):
        if (i * 17 + j * 31 + i * j) % 11 < 5:
            g[i].add(j)
            g[j].add(i)
    h = [set(range(size)) - {i} - g[i] for i in range(size)]
    core, zero = set(range(k)), set(range(k, size))
    me = [(i, j) for i, j in combinations(core, 2) if j in h[i]]
    ne = [(i, j) for i, j in combinations(zero, 2) if j in h[i]]
    tm = sum(j in h[i] and v in h[i] and v in h[j] for i, j, v in combinations(core, 3))
    tn = sum(j in h[i] and v in h[i] and v in h[j] for i, j, v in combinations(zero, 3))
    cz = sum(len(g[i] & g[j] & zero) for i, j in me)
    ck = sum(len(g[i] & g[j] & core) for i, j in ne)
    assert cz == sum(sum(j in h[i] for i, j in combinations(g[u] & core, 2)) for u in zero)
    assert ck == sum(sum(j in h[i] for i, j in combinations(g[x] & zero, 2)) for x in core)
    assert all(x >= 0 for x in (tm, tn, cz, ck))
    th = sum(j in h[i] and v in h[i] and v in h[j] for i, j, v in combinations(range(size), 3))
    mixed = 5 * len(me) + 15 * len(ne)
    mixed -= sum(len(g[x] & zero) * len(h[x] & core) for x in core)
    mixed -= sum(len(g[u] & core) * len(h[u] & zero) for u in zero)
    assert th == mixed + tm + tn + cz + ck
    tg = sum(j in g[i] and v in g[i] and v in g[j] for i, j, v in combinations(range(size), 3))
    assert tg + th == 1140 - sum(len(g[i]) * len(h[i]) for i in range(size)) // 2
    assert c.facts()["GOODMAN"] == 296
    assert 5 * 54 // 2 - 15 * 10 // 2 == 60
    assert 296 - 60 == 236


def test_complete_family_projection(result: c.Document) -> None:
    base = c.load_base()
    before = copy.deepcopy(base)
    p = c.projection(base, 313329096)
    assert base == before
    assert p == result["FAMILY_PROJECTION"]
    assert c.obj(p["BEFORE"])["BOUND"] == 313391636
    assert c.obj(p["AFTER"]) == {
        "BOUND": 313391560,
        "OWNER_IDS": ["65555555555432100000"],
        "GAP": 127672,
        "OPEN_COUNT": 1515,
    }
    assert p["DELTA"] == 76 and p["OTHER_ROWS_UNCHANGED"] == 4646
    assert p["CURSOR"] == base["CURSOR"]
    assert (
        result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
        == base["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
    )


@pytest.mark.parametrize(
    "profile", ["66655555555331100000", "6666555555532110000", "66665555555321100001"]
)
def test_reject_wrong_profile(profile: str) -> None:
    with pytest.raises(ValueError, match="wrong profile"):
        c.facts(profile)


@pytest.mark.parametrize("case", ["sum", "range", "length", "zero", "symmetry"])
def test_reject_wrong_cross_degrees(case: str) -> None:
    s, z = c.enumerate_a()[0][0]
    if case == "sum":
        s = (*s[:-1], s[-1] - 1)
    elif case == "range":
        s = (1, *s[1:])
    elif case == "length":
        s = s[:-1]
    elif case == "zero":
        z = (1, *z[1:])
    else:
        s = (*s[:4], 1, 0, *s[6:])
    with pytest.raises(ValueError):
        c.record_a((s, z))


def test_reject_missing_state(monkeypatch: pytest.MonkeyPatch) -> None:
    original = c.enumerate_a()
    monkeypatch.setattr(c, "enumerate_a", lambda: original[:-1])
    with pytest.raises(ValueError, match="missing states"):
        c.domain_certificate()


@pytest.mark.parametrize(
    "case",
    [
        "wrong_profile",
        "invalid_correction",
        "wrong_cap",
        "source_identity",
        "missing_state",
        "rounding",
        "cursor_mutation",
    ],
)
def test_reject_malformed_result(result: c.Document, case: str) -> None:
    bad = copy.deepcopy(result)
    if case == "wrong_profile":
        bad["TARGET_PROFILE"] = "66655555555331100000"
    elif case == "wrong_cap":
        bad["PROVEN_T_CAP"] = 258
    elif case == "source_identity":
        bad["BASE_RESULT_SHA256"] = "0" * 64
    elif case == "rounding":
        bad["FULL_PROFILE_BOUND"] = 313329095
    elif case == "cursor_mutation":
        cursor = c.obj(c.obj(bad["FAMILY_PROJECTION"])["CURSOR"])
        cursor["STATUS"] = "MUTATED"
    else:
        states = cast(list[c.Document], c.obj(bad["ENUMERATION"])["STATES"])
        if case == "missing_state":
            states.pop()
        else:
            states[0]["C_K"] = c.integer(states[0]["C_K"]) + 1
    with pytest.raises(ValueError, match="result/source/domain/correction"):
        c.verify_result(bad)


@pytest.mark.parametrize("case", ["S4_sign", "K4", "allowance", "S3", "rounding", "incomplete"])
def test_reject_wrong_route_b_term(case: str) -> None:
    terms = c.envelope(257)
    t, b, q, a, s4, s3 = terms[-1]
    if case == "incomplete":
        terms.pop()
    else:
        terms[-1] = (
            t,
            b + (8 * s4 // 7 if case == "S4_sign" else int(case == "rounding")),
            q + int(case == "K4"),
            a + int(case == "allowance"),
            s4,
            s3 + int(case == "S3"),
        )
    with pytest.raises(ValueError):
        c.verify_terms(terms, 257)


@pytest.mark.parametrize("cap", [256, 258, True])
def test_reject_wrong_cap(cap: int) -> None:
    with pytest.raises(ValueError, match="wrong cap"):
        c.envelope(cap)


@pytest.mark.parametrize("case", ["identity", "bound", "coverage"])
def test_reject_live_cursor_mutation(case: str) -> None:
    base = c.load_base()
    cursor = c.obj(base["CURSOR"])
    if case == "identity":
        cast(list[str], cursor["PROFILE_IDS"])[0] = "0" * 20
    elif case == "coverage":
        cursor["PARTITION"] = {}
    else:
        bounds = c.obj(cursor["COARSE_BOUND_PROJECTION"])
        first = next(iter(bounds))
        bounds[first] = c.integer(bounds[first]) - 1
    with pytest.raises(ValueError, match="cursor mutation"):
        c.projection(base, 313329096)
