"""Focused proof, coverage, arithmetic, provenance and mutation rejection checks."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from itertools import combinations, product
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_min_s2_t245_cursor41_joint_formal_authority_r1 as v


@pytest.fixture(scope="module")
def base() -> v.Document:
    return v.load_base()


@pytest.fixture(scope="module")
def result() -> v.Document:
    computed = v.compute_result()
    assert v.render(computed) == (v.ROOT / v.RESULT).read_bytes()
    return computed


def test_full_finite_domain_and_independent_recount(result: v.Document) -> None:
    proof = v.obj(result["T245_PROOF"])
    assert proof["REDUCED_MULTISETS"] == 6036
    assert proof["NECESSARY_STATES"] == proof["INDEPENDENT_RECOUNT"] == 2196583
    assert proof["UNIVERSAL_T_CAP"] == 245
    assert proof["STATES_PRUNED"] == 0
    coverage = cast(list[list[int]], proof["COMPLETE_MULTISET_COVERAGE"])
    assert len(coverage) == 6036
    assert sum(row[5] for row in coverage) == 2196583
    assert max(row[7] for row in coverage) == 245
    assert {tuple(row[:5]) for row in coverage} == set(v.histogram_multisets())
    assert proof["LEGAL_ATTAINMENT"] == "UNKNOWN"


def test_goodman_by_all_small_graphs() -> None:
    pairs = tuple(combinations(range(5), 2))
    for mask in range(1024):
        edges = tuple(p for i, p in enumerate(pairs) if mask >> i & 1)
        complement = tuple(p for p in pairs if p not in edges)
        degrees = [sum(x in p for p in edges) for x in range(5)]
        assert v.triangle_count(5, edges) + v.triangle_count(5, complement) == (
            10 - sum(d * (4 - d) for d in degrees) // 2
        )
        assert v.graphical(tuple(degrees))
        assert complement in v.zero_graphs()[tuple(degrees)]


def test_exact_split_identity_on_degree_realization() -> None:
    # Havel-Hakimi realizes graph degrees only, never a legal support system.
    d = v.common.profile(v.TARGET)
    residual = {i: 6 + degree for i, degree in enumerate(d)}
    neighbours = [set[int]() for _ in d]
    while any(residual.values()):
        ordered = sorted(residual, key=lambda i: (-residual[i], i))
        x = ordered[0]
        need = residual[x]
        residual[x] = 0
        for y in ordered[1 : need + 1]:
            assert residual[y] > 0
            residual[y] -= 1
            neighbours[x].add(y)
            neighbours[y].add(x)
    core = tuple(i for i, degree in enumerate(d) if degree)
    zeros = tuple(i for i, degree in enumerate(d) if not degree)
    m = tuple((x, y) for x, y in combinations(core, 2) if y not in neighbours[x])
    n = tuple((x, y) for x, y in combinations(zeros, 2) if y not in neighbours[x])
    sigma = {x: len(neighbours[x] & set(zeros)) for x in core}
    zeta = {z: len(neighbours[z] & set(core)) for z in zeros}
    t_m = sum({(a, b), (a, c), (b, c)} <= set(m) for a, b, c in combinations(core, 3))
    t_n = sum({(a, b), (a, c), (b, c)} <= set(n) for a, b, c in combinations(zeros, 3))
    c_z = sum(len(neighbours[x] & neighbours[y] & set(zeros)) for x, y in m)
    c_k = sum(len(neighbours[x] & neighbours[y] & set(core)) for x, y in n)
    edges = tuple((x, y) for x, y in combinations(range(20), 2) if y in neighbours[x])
    assert sum(sigma.values()) == sum(zeta.values())
    assert 2 * len(m) == 54 + sum(sigma.values())
    assert 2 * len(n) == sum(zeta.values()) - 10
    assert v.triangle_count(20, edges) == (
        231
        - 10 * sum(sigma.values())
        + sum(sigma[x] * (8 - d[x] + sigma[x]) for x in core)
        + sum(zeta[z] * (zeta[z] - 2) for z in zeros)
        - t_m
        - t_n
        - c_z
        - c_k
    )


def test_graphical_rejection() -> None:
    assert not v.graphical((4, 4, 0, 0, 0))
    assert not v.graphical((1, 0))
    assert not v.graphical((-1, 1))
    for degrees in product(range(5), repeat=5):
        assert v.graphical(degrees) == (degrees in v.zero_graphs())


def test_bipartite_capacity_rejects_old_249_state() -> None:
    bits = (12, 12, 12, 12, 12)
    patterns = v.low_patterns(bits)
    # Without the necessary L-H cut capacities this state's weaker bound is 249.
    penalty = v.low_minimum(patterns, (0, 0, 0, 0), 0)
    assert penalty == 6


def test_refined_triangle_classes_on_corner_graph() -> None:
    # Complement-core graph only: no label-support construction is claimed.
    edges = [(0, 2), (0, 3), (13, 14)]
    edges.extend((x, y) for x in (2, 3) for y in range(4, 15))
    edges.extend((0, y) for y in (6, 7))
    edges.extend((1, y) for y in range(8, 13))
    assert [sum(x in p for p in edges) for x in range(15)] == [
        4,
        5,
        12,
        12,
        2,
        2,
        3,
        3,
        3,
        3,
        3,
        3,
        3,
        3,
        3,
    ]
    assert v.triangle_count(15, edges) == 6
    assert v.low_minimum(v.low_patterns((12,) * 5), (0, 0, 0, 0), 0) == 6


def test_t245_and_cohort_facts(base: v.Document) -> None:
    f = v.facts(v.TARGET)
    assert (f["E"], f["W"], f["SUM_CHOOSE3_DEGREES"], f["GOODMAN_SUM"]) == (93, 825, 2299, 291)
    cursor = v.obj(base["CURSOR"])
    ids = v.cohort_ids(cursor)
    assert set(ids) == v.cohort_histograms() == v.cohort_recurrence()
    assert len(ids) == 41
    assert v.sha(("\n".join(ids) + "\n").encode("ascii")) == v.COHORT_SHA
    assert v.sha("\n".join(ids).encode("ascii")) != v.COHORT_SHA
    for pid in ids:
        facts = v.facts(pid)
        assert (facts["SUM_D"], facts["SUM_D_SQUARED"], facts["W"], facts["GOODMAN_SUM"]) == (
            66,
            244,
            785,
            251,
        )


def test_complete_route_b_exact_rounding(result: v.Document) -> None:
    e = v.obj(result["T245_ENVELOPE"])
    old, new = v.envelope(266), v.envelope(245)
    assert len(old) == 245 and len(new) == 224 and old[:224] == new
    assert max(t[1] for t in old) == 313394776
    assert max(t[1] for t in new) == e["NEW_BOUND"] == 313206768
    assert e["STRICT_GAIN_MARGIN"] == 57120
    assert e["STRICT_GAIN_EXCLUDED"] is True
    assert e["S5_ADOPTED"] is False
    for _, bound, _, _, s4, s3 in old:
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        assert 0 <= bound - exact < 1


def test_cohort_arithmetic_and_multiplicity(result: v.Document) -> None:
    p = v.obj(result["COHORT_PROOF"])
    assert p["UNIVERSAL_T_CAP"] == p["GOODMAN_IDENTITY"] == 251
    assert p["OPEN_WEDGES_MIN"] == 32
    assert p["INHERITED_S4_FLOOR"] == 112 and p["FOURTH_ORDER_CREDIT"] == 64
    assert p["S3_UPPER_BOUND"] == 4885888
    assert 372228640 - 63838600 + 4885888 - 64 == p["NEW_BOUND"] == 313275864
    assert p["DELTA"] == 118720
    assert v.multiplicity_premise()["MAX_WINNING_TICKETS"] == 7
    assert result["LEGAL_ATTAINMENT"] == result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"


def test_complete_family_scenarios_and_scope(base: v.Document, result: v.Document) -> None:
    before, cursor = v.replay_base(base)
    after = {p: v.integer(b) for p, b in v.obj(result["RESOLVED_ROW_BOUNDS"]).items()}
    revised = v.obj(result["CURSOR"])
    scenarios = v.obj(result["FOUR_SCENARIO_REPLAY"])
    assert [v.obj(scenarios[s])["FAMILY_BOUND"] for s in ("S0", "S1", "S2", "S3")] == [
        313394776,
        313394776,
        313394584,
        313392516,
    ]
    for name, rows, c in (
        ("S0", before, cursor),
        ("S1", before, revised),
        ("S2", after, cursor),
        ("S3", after, revised),
    ):
        all_bounds = {**rows, **v.obj(c["COARSE_BOUND_PROJECTION"])}
        maximum = max(v.integer(b) for b in all_bounds.values())
        assert maximum == v.obj(scenarios[name])["FAMILY_BOUND"]
        assert (
            sorted(p for p, b in all_bounds.items() if b == maximum)
            == v.obj(scenarios[name])["OWNER_IDS"]
        )
    assert v.obj(scenarios["S3"])["OWNER_IDS"] == ["65555555555541000000"]
    assert v.obj(scenarios["S3"])["STILL_OPEN_PROFILE_COUNT"] == 1561
    assert v.obj(scenarios["S3"])["GAP_TO_INCUMBENT"] == 128628
    assert result["FAMILY_DELTA"] == 2260
    assert len(before) == len(after) == 4647
    assert {p for p in before if before[p] != after[p]} == {v.TARGET}
    old_coarse, new_coarse = (
        v.obj(cursor["COARSE_BOUND_PROJECTION"]),
        v.obj(revised["COARSE_BOUND_PROJECTION"]),
    )
    assert len(old_coarse) == len(new_coarse) == 197
    assert {p for p in old_coarse if old_coarse[p] != new_coarse[p]} == set(v.cohort_ids(cursor))
    for key in cursor.keys() - {"BOUND", "COARSE_BOUND_PROJECTION"}:
        assert cursor[key] == revised[key]


@pytest.mark.parametrize("cap", [244, 246, 267, True])
def test_reject_wrong_cap(cap: int) -> None:
    with pytest.raises(ValueError, match="wrong T cap"):
        v.envelope(cap)


@pytest.mark.parametrize("parts", [(-1, 0, 0, 0), (0, 0, 0), (True, 0, 0, 0)])
def test_reject_invalid_correction(parts: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="invalid nonnegative correction"):
        v.correction(parts)


@pytest.mark.parametrize("fault", ["domain", "state_count", "cap", "correction"])
def test_reject_corrupt_finite_certificate(result: v.Document, fault: str) -> None:
    proof = deepcopy(v.obj(result["T245_PROOF"]))
    if fault == "domain":
        cast(list[object], proof["COMPLETE_MULTISET_COVERAGE"]).pop()
    elif fault == "state_count":
        proof["INDEPENDENT_RECOUNT"] = 2196582
    elif fault == "cap":
        proof["UNIVERSAL_T_CAP"] = 244
    else:
        v.obj(proof["FIRST_RELAXATION_ARGMAX"])["MIN_LOW_PENALTY"] = -1
    with pytest.raises(ValueError, match="incomplete finite domain or invalid correction"):
        v.validate_t245(proof)
    v.validate_t245(v.obj(result["T245_PROOF"]))


@pytest.mark.parametrize("fault", ["missing", "rounding", "k4", "s4"])
def test_reject_incomplete_or_inexact_terms(fault: str) -> None:
    terms = [list(t) for t in v.envelope(245)]
    if fault == "missing":
        terms.pop()
    else:
        column = {"rounding": 1, "k4": 2, "s4": 4}[fault]
        terms[-1][column] -= 1
    with pytest.raises(ValueError, match="incomplete terms or incorrect rounding"):
        v.validate_terms(245, terms)


@pytest.mark.parametrize("fault", ["wrong_hash", "wrong_head"])
def test_reject_source_mismatch(fault: str) -> None:
    with pytest.raises(ValueError, match=r"source SHA256|source commit"):
        v.immutable(v.R8_HEAD if fault == "wrong_hash" else "main", v.R8_SOURCE, "0" * 64)


@pytest.mark.parametrize("fault", ["membership", "duplicate", "missing"])
def test_reject_wrong_cohort(base: v.Document, fault: str) -> None:
    c = deepcopy(v.obj(base["CURSOR"]))
    ids = cast(list[str], c["PROFILE_IDS"])
    if fault == "missing":
        ids.pop()
    elif fault == "duplicate":
        ids[0] = ids[1]
    else:
        ids.remove(v.cohort_ids(c)[0])
        ids.append(v.TARGET)
    with pytest.raises(ValueError, match=r"cursor identity count|wrong cohort membership"):
        v.cohort_ids(c)


@pytest.mark.parametrize(
    "fault",
    [
        "missing_row",
        "duplicate_row",
        "neighbor_row",
        "duplicate_update",
        "wrong_row_cap",
        "wrong_row_bound",
        "missing_cursor_update",
        "duplicate_cursor_update",
        "wrong_cohort_update",
        "wrong_cursor_cap",
        "wrong_cursor_bound",
        "cursor_identity",
        "cursor_coverage",
        "cursor_bound",
    ],
)
def test_reject_unsafe_updates(base: v.Document, fault: str) -> None:
    rows, cursor = v.replay_base(base)
    row_items = list(rows.items())
    c = deepcopy(cursor)
    row_updates = [(v.TARGET, 245, 313206768)]
    cursor_updates = [(p, 251, 313275864) for p in v.cohort_ids(cursor)]
    if fault == "missing_row":
        row_items.pop()
    elif fault == "duplicate_row":
        row_items.append(row_items[0])
    elif fault == "neighbor_row":
        p, b = row_items[0]
        row_items[0] = (p, b - 1)
    elif fault == "duplicate_update":
        row_updates *= 2
    elif fault == "wrong_row_cap":
        row_updates[0] = (v.TARGET, 246, 313206768)
    elif fault == "wrong_row_bound":
        row_updates[0] = (v.TARGET, 245, 313206767)
    elif fault == "missing_cursor_update":
        cursor_updates.pop()
    elif fault == "duplicate_cursor_update":
        cursor_updates[0] = cursor_updates[1]
    elif fault == "wrong_cohort_update":
        unrelated = next(
            p for p in v.obj(cursor["COARSE_BOUND_PROJECTION"]) if p not in v.cohort_ids(cursor)
        )
        cursor_updates[0] = (unrelated, 251, 313275864)
    elif fault == "wrong_cursor_cap":
        p, _, b = cursor_updates[0]
        cursor_updates[0] = (p, 252, b)
    elif fault == "wrong_cursor_bound":
        p, cap, b = cursor_updates[0]
        cursor_updates[0] = (p, cap, b - 1)
    elif fault == "cursor_identity":
        cast(list[str], c["PROFILE_IDS"]).reverse()
    elif fault == "cursor_coverage":
        c["PARTITION"] = "altered"
    else:
        p = cursor_updates[0][0]
        v.obj(c["COARSE_BOUND_PROJECTION"])[p] = 313394583
    with pytest.raises(ValueError):
        v.apply_updates(row_items, c, base, row_updates, cursor_updates)


def test_reject_altered_base(base: v.Document) -> None:
    altered = deepcopy(base)
    altered["FAMILY_BOUND_AFTER"] = 313394775
    with pytest.raises(ValueError, match="altered Base authority"):
        v.replay_base(altered)


def test_reject_wrong_model() -> None:
    with pytest.raises(ValueError, match="wrong frozen model"):
        v.facts(v.TARGET, {**v.MODEL, "pair_linearity": False})


def test_rejects_invalid_result(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{}\n")
    with pytest.raises(ValueError, match="exact result replay mismatch"):
        v.verify_result(v.decode(path.read_bytes()))
