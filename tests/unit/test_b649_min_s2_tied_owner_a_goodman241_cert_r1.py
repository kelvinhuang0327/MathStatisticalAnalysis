"""Focused mathematical, authority, arithmetic and single-row replay guards."""

from __future__ import annotations

import json
from collections.abc import Sequence
from itertools import combinations, product
from math import comb
from unittest.mock import patch

import pytest

from lottolab.research import b649_k20_min_s2_dangerous_core_realizability_r5 as r5
from lottolab.research import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32
from lottolab.research import b649_min_s2_tied_owner_a_goodman241_cert_r1 as c


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return c.compute_result()


@pytest.fixture(scope="module")
def base() -> c.LedgerView:
    return c.base_authority()[0]


def hh_graphical(degrees: Sequence[int]) -> bool:
    """Independent Havel-Hakimi oracle, including invalid range/parity checks."""
    work = list(degrees)
    if any(not 0 <= v < len(work) for v in work) or sum(work) % 2:
        return False
    while work:
        work.sort(reverse=True)
        degree = work.pop(0)
        if degree == 0:
            return True
        if degree > len(work) or any(v == 0 for v in work[:degree]):
            return False
        work[:degree] = [v - 1 for v in work[:degree]]
    return True


def triangles(vertices: Sequence[int], edges: set[c.Edge]) -> int:
    return sum(
        all(tuple(sorted(edge)) in edges for edge in combinations(t, 2))
        for t in combinations(vertices, 3)
    )


def recorded_supports() -> tuple[list[tuple[int, ...]], list[tuple[int, ...]]]:
    sealed = c.obj(
        json.loads(
            c.pinned(f"{c.RESULT_DIRECTORY}/{c.T248_FILENAME}", c.RESULT_PINS[c.T248_FILENAME])
        )
    )
    realization = c.items(c.obj(c.obj(sealed["ROW_UPDATE"])["AFTER"])["realization"])
    parts = [
        [tuple(c.integer(v) for v in c.items(s)) for s in c.items(part)] for part in realization
    ]
    assert len(parts) == 2
    return parts[0], parts[1]


def test_committed_result_exactly_reproduced(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.render(result)


def test_goodman_and_all_disjoint_floors(result: dict[str, object]) -> None:
    theorem = c.obj(result["THEOREM"])
    assert theorem["STATUS"] == "PROVEN" and theorem["CERTIFIED_T_CAP"] == 241
    assert theorem["GOODMAN_IDENTITY"] == {"STATUS": "PASS", "E": 93, "W": 829, "T_PLUS_I": 295}
    zero, core = c.obj(theorem["ZERO_GRAPHS"]), c.obj(theorem["CORE_DOMAIN"])
    assert zero["FLOORS_BY_M"] == [37, 30, 28, 24, 18, 10, 0]
    assert zero["COUNTS_BY_M"] == [comb(15, 6 - m) for m in range(7)]
    assert zero["GRAPHS_CHECKED"] == 9949
    assert core["FLOORS_BY_M"] == [85, 77, 74, 69, 62, 54, 55]
    assert core["INDEPENDENT_TRIPLE_FLOOR"] == 54
    assert core["CLASS_SORTED_VECTORS"] == 264 and core["LABELLED_VECTORS_COVERED"] == 24576
    assert core["ADMISSIBLE_LABELLED_COUNTS_BY_M"] == [1, 66, 605, 1959, 3123, 3114, 1837]
    assert theorem["ATTAINMENT"] == "NOT_ASSERTED"


def test_eg_against_independent_havel_hakimi() -> None:
    for degrees in product(range(4), repeat=4):
        assert c.graphical(degrees) == hh_graphical(degrees)
    assert c.graphical([2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    assert not c.graphical([3, 3, 0, 0])
    assert not c.graphical([-1, 1]) and not c.graphical([1, 0])


def test_class_quotient_covers_entire_labelled_domain(result: dict[str, object]) -> None:
    floors, counts, raw = [10**9] * 7, [0] * 7, 0
    z_floors = [37, 30, 28, 24, 18, 10, 0]
    for values in product(*(range(7 - d) for d in c.CORE)):
        raw += 1
        cross = sum(values)
        if not 6 <= cross <= 18 or cross % 2:
            continue
        m = (18 - cross) // 2
        a = [6 - d - b for d, b in zip(c.CORE, values, strict=True)]
        h = [7 - d + b for d, b in zip(c.CORE, values, strict=True)]
        if not hh_graphical(a) or not hh_graphical(h):
            continue
        # Independent CCC expression and CCZ summation over the full labelled domain.
        vertex_lower = [
            max(0, 25 - m - h[i] - sum(sorted(h[:i] + h[i + 1 :], reverse=True)[: 13 - h[i]]))
            for i in range(14)
        ]
        ccc = max(max(vertex_lower), (sum(vertex_lower) + 2) // 3)
        ccz = max(0, 6 * (25 - m) - sum(h[i] * values[i] for i in range(14)))
        floors[m] = min(floors[m], ccc + ccz + z_floors[m])
        counts[m] += 1
    core = c.obj(c.obj(result["THEOREM"])["CORE_DOMAIN"])
    assert raw == 24576 and floors == core["FLOORS_BY_M"]
    assert counts == core["ADMISSIBLE_LABELLED_COUNTS_BY_M"]


def test_pinned_support_semantics_and_actual_graph_inequalities() -> None:
    triples, pairs = recorded_supports()
    expected = tuple(sum(v in t for t in triples) for v in range(20))
    degrees, frozen_edges = c.validate_supports(triples, pairs, expected)
    assert r5.validate_k20_support_realization(triples, pairs, expected).triple_support_count == 22
    assert c.support_model()["STATUS"] == "PASS"
    edges = set(frozen_edges)
    complement = set(combinations(range(20), 2)) - edges
    t, independent = triangles(list(range(20)), edges), triangles(list(range(20)), complement)
    w = sum(comb(6 + d, 2) for d in degrees)
    assert t + independent == comb(20, 3) - 18 * len(edges) + w == 298
    core, zero = list(range(14)), list(range(14, 20))
    h = [sum((min(i, j), max(i, j)) in complement for j in core if j != i) for i in core]
    b = [sum((i, j) in edges for j in zero) for i in core]
    f = [sum((min(i, j), max(i, j)) in complement for j in zero if j != i) for i in zero]
    ccc, zzz = triangles(core, complement), triangles(zero, complement)
    ccz = sum(
        all(tuple(sorted(e)) in complement for e in combinations((i, j, z), 2))
        for i, j in combinations(core, 2)
        for z in zero
    )
    czz = sum(
        all(tuple(sorted(e)) in complement for e in combinations((i, z, w), 2))
        for i in core
        for z, w in combinations(zero, 2)
    )
    assert ccc + ccz + czz + zzz == independent
    assert c.ccc_floor(h, sum(h) // 2) <= ccc
    assert c.ccz_floor(h, b, sum(h) // 2) <= ccz
    assert c.zero_floor(f, sum(f) // 2, zzz) <= czz + zzz
    # A dense graph makes the CCC bound positive and sharp.
    assert c.ccc_floor([13] * 14, comb(14, 2)) == comb(14, 3)


@pytest.mark.parametrize(
    "defect", ["duplicate_pair", "reuse_core_pair", "wrong_arity", "wrong_profile"]
)
def test_illegal_supports_rejected(defect: str) -> None:
    triples, pairs = recorded_supports()
    expected = tuple(sum(v in t for t in triples) for v in range(20))
    if defect == "duplicate_pair":
        pairs[-1] = pairs[0]
    elif defect == "reuse_core_pair":
        pairs[-1] = triples[0][:2]
    elif defect == "wrong_arity":
        triples[0] = triples[0][:2]
    else:
        expected = c.PROFILE
    with pytest.raises(AssertionError):
        c.validate_supports(triples, pairs, expected)
    with pytest.raises(ValueError):
        r5.validate_k20_support_realization(triples, pairs, expected)


@pytest.mark.parametrize("defect", ["ccz", "zero", "eg", "ccc"])
def test_inequality_and_domain_mutations_detected(defect: str) -> None:
    if defect == "ccz":
        with patch.object(c, "ccz_floor", return_value=0):
            assert (
                c.integer(
                    c.independent_bound([37, 30, 28, 24, 18, 10, 0])["INDEPENDENT_TRIPLE_FLOOR"]
                )
                < 54
            )
            with pytest.raises(AssertionError, match="independent triple bound"):
                c.cap_theorem()
    elif defect == "zero":
        # Dropping the CZZ bound loses ten independent triples at the minimizing m=5.
        with (
            patch.object(c, "zero_floor", return_value=0),
            pytest.raises(AssertionError, match="independent triple bound"),
        ):
            c.cap_theorem()
    elif defect == "eg":
        # EG is a domain filter; dropping it happens to leave the global floor 54 unchanged.
        baseline = c.independent_bound([37, 30, 28, 24, 18, 10, 0])
        with patch.object(c, "graphical", return_value=True):
            expanded = c.independent_bound([37, 30, 28, 24, 18, 10, 0])
        assert expanded["ADMISSIBLE_CLASSES_BY_M"] != baseline["ADMISSIBLE_CLASSES_BY_M"]
        with (
            patch.object(c, "graphical", return_value=False),
            pytest.raises(AssertionError, match="domain incomplete"),
        ):
            c.independent_bound([37, 30, 28, 24, 18, 10, 0])
    else:
        # The CCC inequality is needed to reproduce the m=6 floor, though not the global 54.
        baseline = c.independent_bound([37, 30, 28, 24, 18, 10, 0])
        with patch.object(c, "ccc_floor", return_value=0):
            weakened = c.independent_bound([37, 30, 28, 24, 18, 10, 0])
        assert weakened["FLOORS_BY_M"] != baseline["FLOORS_BY_M"]
        assert c.ccc_floor([13] * 14, 91) == 364


def test_goodman_mutation_rejected() -> None:
    with patch.object(c, "GOODMAN_CONSTANT", 296), pytest.raises(AssertionError, match="Goodman"):
        c.goodman_identity()


def test_all_t_route_b_against_pinned_r32_and_old_authority(result: dict[str, object]) -> None:
    for cap in (241, 265):
        assert c.route_b(cap) == r32.route_b_envelope(c.PROFILE, cap, 112)
    terms = c.route_b(241)
    assert [t[0] for t in terms] == list(range(22, 242))
    assert terms[-1] == (241, 313183160, 318, 198, 170184, 4890368)
    assert max(t[1] for t in c.route_b(265)) == 313398248
    assert max(t[1] for t in terms) == result["PROFILE_BOUND"] == 313183160 < c.INCUMBENT
    assert result["PROFILE_MARGIN_TO_INCUMBENT"] == 80728


@pytest.mark.parametrize(("cap", "base"), [(21, 112), (277, 112), (241, -1), (True, 112)])
def test_invalid_route_b_domain_rejected(cap: int, base: int) -> None:
    with pytest.raises(AssertionError):
        c.route_b(cap, base)


def test_single_memory_row_and_two_complete_tied_rows_preserved(
    base: c.LedgerView, result: dict[str, object]
) -> None:
    old_bytes = c.render({"bounds": base.bounds, "owners": base.owner_rows})
    after = c.replace_owner(base, 313183160, 241)
    assert c.render({"bounds": base.bounds, "owners": base.owner_rows}) == old_bytes
    assert [p for p in base.bounds if base.bounds[p] != after.bounds[p]] == [c.TARGET_PROFILE]
    assert len(after.bounds) == 4647 and c.family(after) == (313398248, sorted(c.OTHER_OWNERS))
    assert (
        c.bounds_digest(base.bounds)
        == "935e17cf160cb883e22ee31d2327caaac29386545e49073b0e677fccd46375c3"
    )
    assert all(after.owner_rows[p] == base.owner_rows[p] for p in c.OTHER_OWNERS)
    assert after.cursor == base.cursor and after.status == base.status
    assert after.owner_rows[c.TARGET_PROFILE]["s4_base"] == 112
    assert after.owner_rows[c.TARGET_PROFILE]["realization"] is None
    assert result["FAMILY_DELTA"] == 0 and result["OTHER_TIED_OWNERS_PRESERVED"] == "YES"
    assert result["LEDGER_PERSISTENCE"] == "MEMORY_ONLY"


def test_double_update_and_owner_drift_rejected(base: c.LedgerView) -> None:
    once = c.replace_owner(base, 313183160, 241)
    with pytest.raises(AssertionError, match="double or mismatched"):
        c.replace_owner(once, 313183160, 241)
    drifted = c.LedgerView(
        {**base.bounds, c.OTHER_OWNERS[0]: 313398247}, base.owner_rows, base.cursor, base.status
    )
    with pytest.raises(AssertionError, match="owner drift"):
        c.replace_owner(drifted, 313183160, 241)


@pytest.mark.parametrize(("bound", "cap"), [(313183161, 241), (313183160, 242), (True, 241)])
def test_uncertified_replacement_rejected(base: c.LedgerView, bound: int, cap: int) -> None:
    with pytest.raises(AssertionError, match=r"certified|integers"):
        c.replace_owner(base, bound, cap)


@pytest.mark.parametrize("pin", ["tree", "result", "source"])
def test_tampered_authority_pins_rejected(pin: str) -> None:
    if pin == "tree":
        with patch.object(c, "BASE_TREE", "0" * 40), pytest.raises(AssertionError, match="tree"):
            c.base_authority()
    elif pin == "result":
        with (
            patch.dict(c.RESULT_PINS, {c.T248_FILENAME: "0" * 64}),
            pytest.raises(AssertionError, match="pin mismatch"),
        ):
            c.base_authority()
    else:
        with (
            patch.dict(c.SOURCE_PINS, {next(iter(c.SOURCE_PINS)): "0" * 64}),
            pytest.raises(AssertionError, match="pin mismatch"),
        ):
            c.support_model()
