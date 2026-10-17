"""Independent identity/domain/rounding checks and adversarial authority tests."""

from __future__ import annotations

import copy
import json
from itertools import combinations, combinations_with_replacement, product
from math import comb
from typing import cast

import pytest

from lottolab.research import b649_min_s2_two_tied_owner_exact_cert_r1 as c


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return c.compute_result()


@pytest.fixture(scope="module")
def authority() -> tuple[dict[str, int], dict[str, object]]:
    return c.frozen_authority()


def test_result_bytes_and_proof_binding(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.render(result)
    assert result["PROOF"] == c.__doc__


def test_exact_source_pins(result: dict[str, object]) -> None:
    assert c.git("rev-parse", f"{c.BASE_HEAD}^{{tree}}").decode().strip() == c.BASE_TREE
    pins = c.obj(result["PROVENANCE"])
    generic = c.obj(pins["GENERIC_THEOREM"])
    assert c.git("rev-parse", f"{c.GENERIC_HEAD}^{{tree}}").decode().strip() == c.GENERIC_TREE
    for path, digest in c.obj(pins["MODULE_SHA256"]).items():
        assert (c.ROOT / path).read_bytes() == c.blob(c.BASE_HEAD, path, c.string(digest))
    for prefix in ("SOURCE", "RESULT"):
        path = c.string(generic[prefix])
        raw = c.blob(c.GENERIC_HEAD, path, c.string(generic[f"{prefix}_SHA256"]))
        assert (c.ROOT / path).read_bytes() == raw
        assert (
            c.git("rev-parse", f"{c.GENERIC_HEAD}:{path}").decode().strip()
            == generic[f"{prefix}_BLOB"]
        )


@pytest.mark.parametrize("field", ["GENERIC_SOURCE_SHA", "GENERIC_RESULT_SHA", "BASE_TREE"])
def test_source_identity_tamper(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    monkeypatch.setattr(c, field, "0" * (40 if field == "BASE_TREE" else 64))
    with pytest.raises(AssertionError, match="mismatch"):
        c.provenance()


def test_frozen_result_tamper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(c, "FROZEN_SHA", "0" * 64)
    with pytest.raises(AssertionError, match="source-hash"):
        c.frozen_authority()


def test_a_general_theorem_domain(result: dict[str, object]) -> None:
    a = c.obj(c.obj(result["THEOREMS"])[c.PROFILE_A])
    configs = list(c.split.degree_configurations(c.PROFILE_A))
    assert len(configs) == 423 == a["DEGREE_CONFIGURATION_COUNT"]
    assert all(
        conf.profile.count(0) == 6 and conf.profile != c.split.profile_values(c.split.SPECIAL)
        for conf in configs
    )
    assert all(c.split.branch_bound(conf)[1:] == (0, "A_NONNEGATIVE_P") for conf in configs)
    assert max(conf.f for conf in configs) == 244 == a["TRIANGLE_CAP"]
    assert c.obj(c.obj(result["ROW_UPDATES"])[c.PROFILE_A])["STRICT_GAIN_EXCLUDED"] is True


def test_independent_model_and_shadow_budget() -> None:
    d = tuple(map(int, c.PROFILE_B))
    assert sorted(d) == [0] * 5 + [1] * 3 + [4] + [5] * 7 + [6] * 4
    assert sum(d) == 3 * 22 and sum(6 + v for v in d) // 2 == 3 * 22 + 27 == 93
    assert comb(20, 3) - 18 * 97 + sum(comb(13 - v, 2) for v in d) == 298
    assert 2 * 6 - (12 - 1) == 1
    assert (3 * 2 - 4 * 1) // 2 == 1
    assert all(
        2 * internal + high_incidence > 6 or internal <= 1
        for internal in range(4)
        for high_incidence in range(4, 7)
    )
    assert c.shadow_restriction()["LOW_SHADOW_EDGE_CAP"] == 1


def independent_graphical(degrees: tuple[int, ...]) -> bool:
    ordered = sorted(degrees, reverse=True)
    return (
        sum(ordered) % 2 == 0
        and all(0 <= v < len(ordered) for v in ordered)
        and all(
            sum(ordered[:k]) <= k * (k - 1) + sum(min(v, k) for v in ordered[k:])
            for k in range(1, len(ordered) + 1)
        )
    )


def independent_classes() -> set[tuple[int, ...]]:
    domain: set[tuple[int, ...]] = set()
    d = tuple(v for v in map(int, c.PROFILE_B) if v)
    for high_cross, middle, low in product(
        combinations_with_replacement((0, 1), 7),
        range(3),
        combinations_with_replacement(range(6), 3),
    ):
        sigma = (0,) * 4 + high_cross + (middle,) + low
        h = tuple(8 - v + s for v, s in zip(d, sigma, strict=True))
        pair = tuple(6 - v - s for v, s in zip(d, sigma, strict=True))
        if (
            10 <= sum(sigma) <= 24
            and sum(sigma) % 2 == 0
            and independent_graphical(h)
            and independent_graphical(pair)
        ):
            domain.add(sigma)
    return domain


def test_domains_independently_exhausted(result: dict[str, object]) -> None:
    domain = independent_classes()
    assert domain == {conf.sigma for conf in c.split.degree_configurations(c.PROFILE_B)}
    states = [
        (sigma, mask)
        for sigma in domain
        for mask in range(8)
        if mask.bit_count() <= 1 + (15 - sum(sigma[-3:])) // 2
    ]
    assert len(domain) == 339 and len(states) == 2565
    zeros = {
        frozenset(edge for i, edge in enumerate(combinations(range(5), 2)) if mask & (1 << i))
        for mask in range(1024)
    }
    assert len(zeros) == 1024
    for z in c.zero_graphs():
        assert frozenset(z.edges) in zeros
        assert independent_graphical(z.a)
        assert independent_graphical(tuple(4 - v for v in z.a))
        assert sum(z.zeta) == 10 + 2 * len(z.edges)
    b = c.obj(c.obj(result["THEOREMS"])[c.PROFILE_B])
    assert (b["CORE_CLASSES"], b["LOW_DEGREE_STATES"], b["ZERO_GRAPHS"]) == (339, 2565, 1024)
    assert b["GENERIC_CONFIGURATIONS"] == 764 and b["COMPATIBLE_CASES"] == 152731


def count_triangles(n: int, edges: set[c.Pair]) -> int:
    return sum(set(combinations(tri, 2)) <= edges for tri in combinations(range(n), 3))


def test_goodman_split_identity_independent_graphs() -> None:
    vertices, k, z = set(range(20)), set(range(15)), set(range(15, 20))
    universe = set(combinations(range(20), 2))
    for seed in range(9):
        g = {edge for i, edge in enumerate(sorted(universe)) if (i * 17 + seed * 13) % 23 < 11}
        h = universe - g
        hd = tuple(sum(v in edge for edge in h) for v in vertices)
        assert count_triangles(20, g) + count_triangles(20, h) == comb(20, 3) - 18 * len(h) + sum(
            comb(v, 2) for v in hd
        )
        m, n = {edge for edge in h if set(edge) <= k}, {edge for edge in h if set(edge) <= z}
        ng = {v: {u for u in vertices if tuple(sorted((u, v))) in g} for v in vertices}
        sigma, zeta = {v: len(ng[v] & z) for v in k}, {v: len(ng[v] & k) for v in z}
        core_t = sum(set(combinations(tri, 2)) <= m for tri in combinations(sorted(k), 3))
        zero_t = sum(set(combinations(tri, 2)) <= n for tri in combinations(sorted(z), 3))
        corrections = (
            sum(len(ng[i] & ng[j] & z) for i, j in m),
            sum(len(ng[i] & ng[j] & k) for i, j in n),
        )
        mixed = 5 * len(m) + 15 * len(n)
        mixed -= sum(sigma[v] * sum(v in edge for edge in m) for v in k)
        mixed -= sum(zeta[v] * sum(v in edge for edge in n) for v in z)
        assert min(corrections) >= 0
        assert count_triangles(20, h) == core_t + zero_t + mixed + sum(corrections)


def degree_graph(degrees: tuple[int, ...]) -> set[c.Pair]:
    """Deterministic Havel-Hakimi fixtures, without support-realization search."""
    remaining = list(enumerate(degrees))
    edges: set[c.Pair] = set()
    while remaining:
        remaining.sort(key=lambda pair: (-pair[1], pair[0]))
        v, degree = remaining.pop(0)
        assert 0 <= degree <= len(remaining)
        for i in range(degree):
            u, du = remaining[i]
            assert du > 0
            edges.add((min(u, v), max(u, v)))
            remaining[i] = (u, du - 1)
    return edges


def test_core_and_mixed_floors_on_all_core_classes() -> None:
    d = tuple(map(int, c.PROFILE_B[:15]))
    low_pairs = tuple(combinations(range(3), 2))
    for sigma in independent_classes():
        h = tuple(8 - v + s for v, s in zip(d, sigma, strict=True))
        m = degree_graph(h)
        assert tuple(sum(v in edge for edge in m) for v in range(15)) == h
        mask = sum(1 << bit for bit, (i, j) in enumerate(low_pairs) if (12 + i, 12 + j) not in m)
        actual_t = count_triangles(15, m)
        core_floor, mixed_floor = c.core_and_mixed_floors(sigma, mask)
        assert actual_t >= core_floor >= c.core_floor(h)
        for shift in (0, 3):
            gz = {i: {(v + i + shift) % 5 for v in range(sigma[i])} for i in range(15)}
            actual_mixed = sum(len(set(range(5)) - gz[i] - gz[j]) for i, j in m)
            assert actual_mixed >= mixed_floor >= 0


def test_b_per_e_results_and_shadow_ablation(result: dict[str, object]) -> None:
    b = c.obj(c.obj(result["THEOREMS"])[c.PROFILE_B])
    assert b["MINIMA_BY_ZERO_EDGES"] == [41, 42, 42, 41, 41, 44, 47, 54]
    assert b["ENUMERATED_MINIMUM"] == 41 and b["SUPPLEMENTAL_T_CAP"] == 257
    assert b["ADOPTED_COMPLEMENT_FLOOR"] == 39 and b["TRIANGLE_CAP"] == 259
    removed = c.obj(b["REMOVED_SHADOW_RESTRICTION"])
    assert removed["LOW_DEGREE_STATES"] == 2712
    assert min(c.integer(v) for v in c.items(removed["MINIMA_BY_ZERO_EDGES"])) == 23
    comparison = c.obj(b["PACKET_TABLE_COMPARISON_ONLY"])
    assert comparison["ORIGINAL_TABLE_REPRODUCED"] is False
    assert comparison["DIFFERENCES"] == {"3": {"PACKET": 39, "COMPUTED": 41}}
    assert result["ATTAINABILITY"] == "NOT_ESTABLISHED"


@pytest.mark.parametrize("profile", [c.PROFILE_A, "0" * 20, c.PROFILE_B[:-1]])
def test_wrong_b_profile(profile: str) -> None:
    with pytest.raises(AssertionError, match="profile"):
        c.shadow_restriction(profile)


def test_all_route_terms_independent(result: dict[str, object]) -> None:
    for p, cap in ((c.PROFILE_A, 244), (c.PROFILE_B, 259)):
        degree = tuple(6 + int(v) for v in p)
        w, u = (
            sum(v * (v - 1) // 2 for v in degree),
            sum(v * (v - 1) * (v - 2) // 6 for v in degree),
        )
        amax = sum(int(v) * (g - 2) for v, g in zip(p, degree, strict=True)) // 3
        independent: list[c.Term] = []
        for t in range(22, cap + 1):
            numerator = u - (max(degree) - 2) * (w - 3 * t)
            k4 = max(0, (numerator + 3) // 4)
            contained = min(amax, k4)
            s4 = max(112, 679 * k4 - 231 * contained)
            s3 = 2800 * w + 11872 * (t - 22) - 30800
            independent.append((t, 308_390_040 + s3 - (4 * s4) // 7, k4, contained, s4, s3))
        assert c.route_b(p, cap) == independent
        assert c.obj(result["ROUTE_B_ENVELOPES"])[p] == [list(t) for t in independent]
        assert c.obj(result["ROUTE_B_TERMS_CHECKED"])[p] == cap - 21
    assert c.route_b(c.PROFILE_B, 259)[-1] == (259, 313353140, 453, 200, 261387, 5112464)
    assert max(t[1] for t in c.route_b(c.PROFILE_A, 244)) == 313218904
    assert c.obj(result["ROUTE_B_TERMS_CHECKED"])[c.PROFILE_B] == 238


def test_official_rounding_tamper(monkeypatch: pytest.MonkeyPatch) -> None:
    original = c.official.route_b_envelope

    def tampered(p: tuple[int, ...], cap: int, base: int) -> list[c.Term]:
        terms = original(p, cap, base)
        t = terms[-1]
        terms[-1] = (t[0], t[1] + 1, *t[2:])
        return terms

    monkeypatch.setattr(c.official, "route_b_envelope", tampered)
    with pytest.raises(AssertionError, match="arithmetic"):
        c.route_b(c.PROFILE_B, 259)


@pytest.mark.parametrize("kind", ["bound", "profile", "cursor", "float"])
def test_integration_tamper(authority: tuple[dict[str, int], dict[str, object]], kind: str) -> None:
    bounds, sealed = authority
    cursor = c.obj(sealed["CURSOR"])
    updates: dict[str, object] = {c.PROFILE_A: 313218904, c.PROFILE_B: 313353140}
    tampered_cursor = copy.deepcopy(cursor)
    if kind == "bound":
        updates[c.PROFILE_B] = 313353141
    elif kind == "profile":
        updates["0" * 20] = updates.pop(c.PROFILE_B)
    elif kind == "cursor":
        tampered_cursor["PROFILE_COUNT"] = 196
    else:
        updates[c.PROFILE_B] = 313353140.0
    with pytest.raises(AssertionError, match=r"arithmetic|updates|cursor"):
        c.integrate(bounds, cast(dict[str, int], updates), tampered_cursor, cursor)


def test_truncated_envelope_and_cap_rejected() -> None:
    raw = [list(t) for t in c.route_b(c.PROFILE_B, 259)]
    with pytest.raises(AssertionError, match="completeness"):
        c.validate_envelope(c.PROFILE_B, 259, raw[1:])
    with pytest.raises(AssertionError, match="cap"):
        c.validate_envelope(c.PROFILE_B, 258, raw)


def test_duplicate_and_missing_row_rejected(
    authority: tuple[dict[str, int], dict[str, object]],
) -> None:
    original = list(authority[0].items())
    with pytest.raises(AssertionError, match="duplicate"):
        c.validate_rows([*original[:-1], original[0]])
    with pytest.raises(AssertionError, match="missing"):
        c.validate_rows([(p if p != c.PROFILE_A else "0" * 20, v) for p, v in original])
    with pytest.raises(AssertionError, match="duplicate JSON"):
        c.prior.decode(b'{"row":1,"row":2}')


def test_family_and_projection_independent(
    result: dict[str, object], authority: tuple[dict[str, int], dict[str, object]]
) -> None:
    before, sealed = authority
    cursor = c.obj(sealed["CURSOR"])
    after = {p: c.integer(v) for p, v in c.obj(result["RESOLVED_ROW_BOUNDS"]).items()}
    assert len(after) == 4647 and sorted(p for p in before if before[p] != after[p]) == sorted(
        c.TARGETS
    )
    others = sorted(set(before) - set(c.TARGETS))
    assert len(others) == 4645
    assert json.dumps([(p, before[p]) for p in others]) == json.dumps(
        [(p, after[p]) for p in others]
    )
    terms = [(bound, p) for p, bound in after.items()]
    terms.append((c.integer(cursor["BOUND"]), c.string(cursor["ID"])))
    best = max(bound for bound, _ in terms)
    assert best == result["FAMILY_BOUND_AFTER"] == 313397860
    assert sorted(p for bound, p in terms if bound == best) == result["NEW_OWNER_IDS"]
    assert result["NEW_OWNER_IDS"] == ["66665555554421100000"]
    assert c.integer(result["FAMILY_BOUND_BEFORE"]) - best == result["EXACT_DELTA"] == 284
    assert best - c.INCUMBENT == result["GAP_TO_INCUMBENT"] == 133972
    assert result["CURSOR"] == cursor
    assert result["CURSOR_SHA256_BEFORE"] == result["CURSOR_SHA256_AFTER"]
    assert c.obj(c.obj(result["ROW_UPDATES"])[c.PROFILE_B])["STRICT_GAIN_EXCLUDED"] is False
    assert (
        result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
        == sealed["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
    )
    assert result["FULL_METADATA_DIGEST_AFTER"] == sealed["FULL_METADATA_DIGEST_AFTER"]
    assert result["STILL_OPEN_PROFILE_COUNT"] == sum(v > c.INCUMBENT for v in after.values()) + 197
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
