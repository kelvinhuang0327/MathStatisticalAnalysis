"""Focused evidence for the complete-profile proof and frozen integer recount."""

from itertools import combinations
from unittest.mock import patch

import pytest

from lottolab.research import b649_frontier_owner_a_exact_bound_r1 as c


@pytest.fixture(scope="module")
def result():
    return c.compute_result()


def test_frozen_ledger_and_exact_reproduction(result):
    assert c.render(result) == c.RESULT.read_bytes()
    source = result["SOURCE"]
    assert source["LEDGER_ROWS"] == 4647
    assert (
        source["FULL_ROWS_SHA256"]
        == "70e2c1bb28f223566cb54799fd1b325368b90d58c5fc5001cacfbba9d2996de6"
    )
    assert (source["ORIGINAL_T_CAP"], source["ORIGINAL_S4_BASE"], source["ORIGINAL_ROW_BOUND"]) == (
        264,
        112,
        313398144,
    )


def test_unary_inequalities_and_complete_relaxation():
    theorem = c.theorem()
    assert theorem["GOODMAN_CONSTANT"] == 298
    assert theorem["ANALYTIC_CAP"] == 261
    assert c.relaxation()["COUNT"] == 2539
    assert c.relaxation()["MAXIMUM"] == 261
    # The complete loose relaxation attains 261; a cap of 260 needs another premise.
    sigma = (0,) * 11 + (3, 3, 5)
    assert c.relaxed_value(sigma, (1, 1, 1, 1, 1, 6)) == 261


@pytest.mark.parametrize("degrees", ["66655555555440000000", "6666555555533100000"])
def test_another_profile_rejected(degrees):
    with pytest.raises(AssertionError, match="profile premises"):
        c.theorem(degrees)


def test_zero_chord_is_load_bearing():
    with pytest.raises(AssertionError, match="zero chord"):
        c.theorem(zero_range=range(7))
    with pytest.raises(AssertionError, match="incomplete zero range"):
        c.theorem(zero_range=range(1, 6))


@pytest.mark.parametrize("coefficients", [(-3, 2, 6), (-2, 1, 6), (-2, 2, 5)])
def test_false_core_inequalities_rejected(coefficients):
    with pytest.raises(AssertionError, match="core inequality"):
        c.theorem(coefficients=coefficients)


def test_wrong_cap_detected():
    with patch.object(c, "CAP", 260), pytest.raises(AssertionError, match="analytic constant"):
        c.theorem()


def test_wrong_goodman_constant_detected():
    real_comb = c.comb
    with (
        patch.object(
            c,
            "comb",
            side_effect=lambda n, k: real_comb(n, k) - 3 if (n, k) == (20, 3) else real_comb(n, k),
        ),
        pytest.raises(AssertionError, match="Goodman"),
    ):
        c.theorem()


def test_bad_cross_degree_vectors_rejected():
    sigma = (0,) * 11 + (3, 3, 5)
    with pytest.raises(AssertionError, match="cross-degree sums"):
        c.relaxed_value(sigma, (1,) * 6)
    with pytest.raises(AssertionError, match="cross-degree ranges"):
        c.relaxed_value(sigma, (0, 1, 1, 1, 2, 6))


def test_recorded_support_has_nonzero_remainder(result):
    seen = result["RECORDED_SUPPORT_CHECK"]
    assert seen["TRIANGLES"] + seen["COMPLEMENT_TRIANGLES"] == 298
    assert seen["P"] == sum(seen["P_TERMS"]) > 0
    assert seen["TRIANGLES"] == seen["F"] - seen["P"]
    assert min(seen["P_TERMS"]) >= 0


def test_illegal_support_is_rejected(result):
    triples, pairs = result["SOURCE"]["ROW"]["realization"]
    with pytest.raises(AssertionError, match="support pair-linearity"):
        c.support_check(triples, [pairs[0]] * 27)
    with pytest.raises(AssertionError, match="wrong profile"):
        c.support_check(*c.frozen.three.witness())


def test_all_triangle_identity_cases_small_graphs():
    # An independent local enumeration validates Goodman and all four P terms.
    vertices, core, zero = range(5), {0, 1, 2}, {3, 4}
    edges = list(combinations(vertices, 2))

    def triangles(vs, es):
        return sum(all(e in es for e in combinations(t, 2)) for t in combinations(sorted(vs), 3))

    for mask in range(1 << len(edges)):
        g = {e for i, e in enumerate(edges) if mask & (1 << i)}
        h = set(edges) - g
        nb = {v: {w for w in vertices if tuple(sorted((v, w))) in g} for v in vertices}
        m = {e for e in h if set(e) <= core}
        mz = {e for e in h if set(e) <= zero}
        sigma = {v: len(nb[v] & zero) for v in core}
        zeta = {v: len(nb[v] & core) for v in zero}
        p = triangles(core, m) + triangles(zero, mz)
        p += sum(len(nb[x] & nb[y] & zero) for x, y in m)
        p += sum(len(nb[x] & nb[y] & core) for x, y in mz)
        bare = len(zero) * len(m) + len(core) * len(mz)
        bare -= sum(sigma[v] * sum(v in e for e in m) for v in core)
        bare -= sum(zeta[v] * sum(v in e for e in mz) for v in zero)
        assert triangles(vertices, h) == bare + p
        assert 2 * (triangles(vertices, g) + triangles(vertices, h)) == 20 - sum(
            len(nb[v]) * (4 - len(nb[v])) for v in vertices
        )


def test_integer_envelope_and_weakest_sufficient_cap(result):
    opt = result["OPTIMIZATION"]
    assert opt["NEW_ADMISSIBLE_BOUND"] == 313371452
    assert opt["STRICT_OWNER_BOUND_DELTA"] == 26692
    assert opt["ARGMAX_TERM"] == (261, 313371452, 467, 200, 270893, 5136208)
    assert opt["T_TERM_COUNT"] == 240
    assert [t[0] for t in opt["ALL_T_TERMS"]] == list(range(22, 262))
    assert opt["MINIMUM_SUFFICIENT_T_CAP"] == 263
    assert opt["THRESHOLD_TERM"][1] == 313389376 <= c.COMPETITOR
    assert opt["FAILED_WEAKER_CAP_TERM"][1] > c.COMPETITOR
    assert opt["OWNER_EXCLUSION_PROVED"] is False
    assert opt["FAMILY_BOUND_GAIN_CLAIMED"] == opt["NEW_WINNING_OUTCOMES"] == 0


def test_ceil_floor_error_rejected():
    original = c.frozen.r32.route_b_envelope

    def wrong(*args):
        terms = list(original(*args))
        t, bound, *tail = terms[-1]
        terms[-1] = (t, bound + 1, *tail)
        return terms

    with (
        patch.object(c.frozen.r32, "route_b_envelope", wrong),
        pytest.raises(AssertionError, match="independent Route-B"),
    ):
        c.route_b(261)


def test_duplicate_scope_and_no_ledger_write(result):
    assert result["DUPLICATE_CHECK"]["EXISTING_TARGET_CAPS_LE_261"] == []
    assert result["DUPLICATE_CHECK"]["STATUS"] == "NO_EXISTING_TARGET_CAP_CERTIFICATE"
    assert c.frozen.two.full_digest(c.authority()[1]) == result["SOURCE"]["FULL_ROWS_SHA256"]
