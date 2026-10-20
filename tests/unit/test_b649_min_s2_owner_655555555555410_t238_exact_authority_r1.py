"""Focused exact proof, domain completeness, envelope and adoption rejection tests."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from itertools import combinations, product
from typing import cast

import pytest

from lottolab.research import b649_min_s2_owner_655555555555410_t238_exact_authority_r1 as v


@pytest.fixture(scope="module")
def base() -> v.Document:
    return v.load_base()


@pytest.fixture(scope="module")
def result() -> v.Document:
    value = v.compute_result()
    assert (v.ROOT / v.RESULT).read_bytes() == v.render(value)
    return value


def test_exact_base_and_inherited_certificates(base: v.Document, result: v.Document) -> None:
    pins = v.obj(result["PROVENANCE"])
    assert pins["BASE_HEAD"] == v.BASE_HEAD and pins["BASE_TREE"] == v.BASE_TREE
    assert pins["BASE_RESULT_SHA256"] == v.sha(v.render(base)) == v.BASE_SHA
    assert pins["BASE_JUDGE_VERDICT"] == "VERIFIED_WITH_CAVEATS"
    assert pins["CURRENT_T_CAP"] == 265 and pins["CURRENT_S5_AUTHORITY"] == "NOT_ADOPTED"
    assert result["INHERITED_COHORT_SHA256"] == v.sha(v.render(base["COHORT_PROOF"]))
    assert result["INHERITED_T245_SHA256"] == v.sha(v.render(base["T245_PROOF"]))
    assert result["HISTORICAL_R15"] == "NOT_VERIFIED"


def test_exact_domain_and_full_maximum(result: v.Document) -> None:
    proof = v.obj(result["T238_PROOF"])
    domain = cast(list[list[int]], proof["COMPLETE_DOMAIN"])
    assert len(domain) == len({tuple(r) for r in domain}) == 1296
    assert proof["INDEPENDENT_RECOUNT"] == 1296
    assert max(r[-2] for r in domain) == 238
    assert sum(r[-1] == 31 for r in domain) == 225
    assert proof["MAX_RAW_F"] == proof["MAX_GRAPHICAL_F"] == proof["UNIVERSAL_T_CAP"] == 238
    assert proof["ARGMAX_CONFIGURATIONS"] == [[0, 1, 5, 1, 1, 1, 1, 1, 1, 238, 31]]
    assert proof["INDEPENDENT_DOMAIN_AND_VALUES_EQUAL"] is True
    assert proof["STATES_PRUNED"] == 0 and proof["LEGAL_ATTAINMENT"] == "UNKNOWN"
    assert proof["DOMAIN_SHA256"] == v.sha(v.render(domain))


def test_exact_identity_on_graph_degree_realization() -> None:
    # A simple graph only, without any legal-support attainment assertion.
    residual = {i: 6 + d for i, d in enumerate(v.D)}
    adjacent = [set[int]() for _ in v.D]
    while any(residual.values()):
        ordered = sorted(residual, key=lambda i: (-residual[i], i))
        x = ordered[0]
        need, residual[x] = residual[x], 0
        for y in ordered[1 : need + 1]:
            assert residual[y] > 0
            residual[y] -= 1
            adjacent[x].add(y)
            adjacent[y].add(x)
    k, z = set(range(14)), set(range(14, 20))
    m = [(x, y) for x, y in combinations(sorted(k), 2) if y not in adjacent[x]]
    n = [(x, y) for x, y in combinations(sorted(z), 2) if y not in adjacent[x]]
    sigma = {x: len(adjacent[x] & z) for x in k}
    zeta = {u: len(adjacent[u] & k) for u in z}

    def triangles(vertices: set[int], edges: list[tuple[int, int]]) -> int:
        return sum(
            {(a, b), (a, c), (b, c)} <= set(edges) for a, b, c in combinations(sorted(vertices), 3)
        )

    parts = (
        triangles(k, m),
        triangles(z, n),
        sum(len(adjacent[x] & adjacent[y] & z) for x, y in m),
        sum(len(adjacent[x] & adjacent[y] & k) for x, y in n),
    )
    r = sum(sigma.values())
    assert r == sum(zeta.values())
    assert 2 * len(m) == 32 + r and 2 * len(n) == r - 6
    f = 239 - 10 * r + sum(sigma[x] * (7 - v.D[x] + sigma[x]) for x in k)
    f += sum(zeta[u] * (zeta[u] - 1) for u in z)
    edges = [(x, y) for x, y in combinations(range(20), 2) if y in adjacent[x]]
    missing = [(x, y) for x, y in combinations(range(20), 2) if y not in adjacent[x]]
    actual = triangles(set(range(20)), edges)
    assert actual == f - v.remainder(parts)
    assert actual + triangles(set(range(20)), missing) == 293


def test_graphical_implementations_on_all_five_vertex_lists() -> None:
    actual = set[tuple[int, ...]]()
    pairs = tuple(combinations(range(5), 2))
    for mask in range(1 << len(pairs)):
        edges = [p for i, p in enumerate(pairs) if mask >> i & 1]
        actual.add(tuple(sum(x in p for p in edges) for x in range(5)))
    for degrees in product(range(5), repeat=5):
        assert v.split.graphical(degrees) == v.havel_hakimi(degrees) == (degrees in actual)
    assert not v.havel_hakimi((-1, 1))


def test_equal_degree_symmetry_preserves_objective() -> None:
    # Each H5 cross row contributes 3*sigma, independent of which H5 is chosen.
    for q in range(12):
        assert (0,) * (11 - q) + (1,) * q == tuple(sorted((1,) * q + (0,) * (11 - q)))
    z = (1, 1, 1, 1, 2, 2)
    forward = v.record(2, 1, 5, z)
    assert forward == v.record(2, 1, 5, tuple(sorted(reversed(z))), independent=True)
    # The d=4 and d=1 vertices are distinct and cannot be quotiented together.
    a = v.record(2, 1, 4, (1, 1, 1, 1, 1, 2))
    b = v.record(2, 2, 3, (1, 1, 1, 1, 1, 2))
    assert a[-2] != b[-2]


def test_complete_envelopes_and_exact_ceiling(result: v.Document) -> None:
    e = v.obj(result["ENVELOPE"])
    old, new = v.envelope(265), v.envelope(238)
    assert len(old) == 244 and len(new) == 217 and old[:217] == new
    assert max(t[1] for t in old) == 313392516
    assert max(new, key=lambda t: t[1]) == (238, 313150736, 295, 197, 154798, 4849152)
    assert e["PROFILE_DELTA"] == 241780 and e["MARGIN_BELOW_INCUMBENT"] == 113152
    assert e["STRICT_GAIN_EXCLUDED"] is True and e["S5_ADOPTED"] is False
    assert v.facts()["CONTAINMENT_ALLOWANCE"] == 197
    assert all((4 * t[4]) % 7 == 0 for t in new)
    for _, bound, _, _, s4, s3 in old:
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        assert 0 <= bound - exact < 1
        assert bound == (7 * (372228640 - 63838600 + s3) - 4 * s4 + 6) // 7


def test_complete_family_replay(base: v.Document, result: v.Document) -> None:
    before = v.obj(base["RESOLVED_ROW_BOUNDS"])
    after = v.obj(result["RESOLVED_ROW_BOUNDS"])
    assert len(after) == len(before) == 4647
    assert {p for p in before if before[p] != after[p]} == {v.TARGET}
    assert after[v.TARGET] == 313150736
    assert result["CURSOR"] == base["CURSOR"]
    assert result["CURSOR_BOUNDS_CHANGED"] == 0 and result["CURSOR_ROWS"] == 197
    assert result["OTHER_RESOLVED_ROWS_UNCHANGED"] == 4646
    family = v.obj(result["FAMILY_AFTER"])
    all_bounds = {**after, **v.obj(v.obj(result["CURSOR"])["COARSE_BOUND_PROJECTION"])}
    maximum = max(v.integer(b) for b in all_bounds.values())
    assert maximum == family["FAMILY_BOUND"] == 313392412
    assert family["OWNER_IDS"] == sorted(p for p, b in all_bounds.items() if b == maximum)
    assert family["GAP_TO_INCUMBENT"] == 128524 and family["STILL_OPEN_PROFILE_COUNT"] == 1560
    assert result["FAMILY_DELTA"] == 104


@pytest.mark.parametrize("pid", ["66555555555431100000", "65555555555541000001", "bad"])
def test_rejects_wrong_profile(pid: str) -> None:
    with pytest.raises(ValueError):
        v.facts(pid)


@pytest.mark.parametrize("key", ["SUM_D", "W", "E", "GOODMAN_SUM", "SUM_CHOOSE3_DEGREES"])
def test_rejects_incorrect_degree_identity(key: str) -> None:
    value = v.facts()
    value[key] = v.integer(value[key]) + 1
    with pytest.raises(ValueError, match="degree identity"):
        v.validate_facts(value)


@pytest.mark.parametrize("mode", ["missing", "duplicate", "invalid_symmetry", "sign", "maximum"])
def test_rejects_damaged_enumeration(mode: str) -> None:
    value = deepcopy(v.enumeration())
    domain = cast(list[list[int]], value["COMPLETE_DOMAIN"])
    if mode == "missing":
        domain.pop()
    elif mode == "duplicate":
        domain[-1] = domain[0].copy()
    elif mode == "invalid_symmetry":
        for row in domain:
            if row[1] != row[2]:
                row[1], row[2] = row[2], row[1]
                break
    elif mode == "sign":
        domain[0][-2] = -domain[0][-2]
    else:
        value["UNIVERSAL_T_CAP"] = 237
    with pytest.raises(ValueError, match=r"enumeration|symmetry"):
        v.validate_enumeration(value)


@pytest.mark.parametrize(
    "parts", [(-1, 0, 0, 0), (0, -1, 0, 0), (0, 0, -1, 0), (0, 0, 0, -1), (0, 0, 0)]
)
def test_rejects_incorrect_correction_sign(parts: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="correction sign"):
        v.remainder(parts)


@pytest.mark.parametrize(
    "state",
    [
        (12, 0, 0, (2,) * 6),
        (0, 3, 3, (1,) * 6),
        (0, 0, 6, (1,) * 6),
        (0, 1, 5, (0, 1, 1, 1, 1, 2)),
        (2, 1, 5, (2, 1, 1, 1, 1, 2)),
    ],
)
def test_rejects_invalid_capacity_or_symmetry(state: tuple[int, int, int, tuple[int, ...]]) -> None:
    with pytest.raises(ValueError, match=r"capacity|symmetry"):
        v.record(*state)


@pytest.mark.parametrize(
    "mode", ["missing_first", "missing_last", "duplicate", "rounding", "s4_direction"]
)
def test_rejects_incomplete_terms_or_wrong_rounding(mode: str) -> None:
    terms = [list(t) for t in v.envelope(238)]
    if mode == "missing_first":
        terms.pop(0)
    elif mode == "missing_last":
        terms.pop()
    elif mode == "duplicate":
        terms[-1] = terms[0].copy()
    elif mode == "rounding":
        terms[-1][1] -= 1
    else:
        terms[-1][4] = -terms[-1][4]
    with pytest.raises(ValueError, match=r"T-domain|rounding"):
        v.validate_terms(238, terms)


def test_rejects_wrong_source_and_result_hashes() -> None:
    for path in (v.SPLIT_SOURCE, v.BASE_RESULT):
        with pytest.raises(ValueError, match="SHA256"):
            v.immutable(v.BASE_HEAD, path, "0" * 64)
    with pytest.raises(ValueError, match="commit"):
        v.immutable("2bdf3a6", v.BASE_RESULT, v.BASE_SHA)


def test_fractional_rounding_seam_rejects_floor() -> None:
    # Real S4 weights are all divisible by seven. A controlled arithmetic
    # input exercises the ceiling branch without adopting a new S4 floor.
    s3, s4 = 5000, 113
    exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
    floor = exact.numerator // exact.denominator
    ceiling = v.common.rounded_bound(s3, s4)
    assert exact.denominator == 7 and ceiling == floor + 1
    v.validate_rounding(s3, s4, ceiling)
    with pytest.raises(ValueError, match="rational ceiling"):
        v.validate_rounding(s3, s4, floor)


@pytest.mark.parametrize(
    "mode",
    [
        "missing_update",
        "duplicate_update",
        "wrong_profile",
        "wrong_bound",
        "missing_row",
        "duplicate_row",
        "altered_row",
        "cursor_bound",
        "cursor_identity",
        "cursor_coverage",
    ],
)
def test_rejects_ledger_or_cursor_tampering(base: v.Document, mode: str) -> None:
    before, cursor = v.replay_base(base)
    rows = list(before.items())
    modified = deepcopy(cursor)
    updates = [(v.TARGET, 313150736)]
    if mode == "missing_update":
        updates = []
    elif mode == "duplicate_update":
        updates *= 2
    elif mode == "wrong_profile":
        updates = [("66555555555431100000", 313150736)]
    elif mode == "wrong_bound":
        updates = [(v.TARGET, 313150735)]
    elif mode == "missing_row":
        rows.pop()
    elif mode == "duplicate_row":
        rows.append(rows[0])
    elif mode == "altered_row":
        rows[0] = (rows[0][0], rows[0][1] + 1)
    elif mode == "cursor_bound":
        bounds = v.obj(modified["COARSE_BOUND_PROJECTION"])
        pid = next(p for p in bounds if bounds[p] == 313275864)
        bounds[pid] = 313394584
    elif mode == "cursor_identity":
        cast(list[str], modified["PROFILE_IDS"]).pop()
    else:
        modified["PARTITION"] = {}
    with pytest.raises(ValueError, match=r"ledger|cursor"):
        v.apply_update(rows, modified, base, updates)


def test_rejects_mutated_base_result(base: v.Document) -> None:
    damaged = deepcopy(base)
    v.obj(damaged["RESOLVED_ROW_BOUNDS"])[v.TARGET] = 313150736
    with pytest.raises(ValueError, match="Base result SHA256"):
        v.replay_base(damaged)


def test_rejects_invalid_result_and_duplicate_json_keys(result: v.Document) -> None:
    damaged = deepcopy(result)
    damaged["TARGET_PROFILE"] = "66555555555431100000"
    with pytest.raises(ValueError, match="result mismatch"):
        v.verify_result(damaged)
    with pytest.raises(ValueError, match="duplicate JSON key"):
        v.decode(b'{"a":1,"a":2}')
