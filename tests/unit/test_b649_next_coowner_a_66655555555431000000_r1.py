"""Focused exact certificate, premise mutations, non-vacuity and frozen arithmetic."""

from __future__ import annotations

import json
import sys
from itertools import combinations
from unittest.mock import patch

import pytest

from lottolab.research import b649_next_coowner_a_66655555555431000000_r1 as c


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("proof/search entrypoint must not run during frozen ledger replay")

    with (
        patch.dict(sys.modules, {"ortools": None}),
        patch.object(c.frozen.split, "degree_configurations", forbidden),
        patch.object(c.frozen.split, "split_certificate", forbidden),
        patch.object(c.frozen.chase, "chase", forbidden),
        patch.object(c.frozen.chase, "refine", forbidden),
        patch.object(c.frozen, "t256_theorem", forbidden),
        patch.object(c.frozen.three, "core_zero_theorem", forbidden),
    ):
        return c.compute_result()


def test_exact_result_and_frozen_row(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.frozen.two.render(result)
    assert result["FROZEN_HEAD_TREE"] == result["FROZEN_RESULT_SHA256_CHECK"] == "MATCH"
    assert result["SOURCE_T_CAP"] == 264
    assert result["SOURCE_S4_BASE"] == 112
    assert result["SOURCE_ROW_BOUND"] == 313392412
    assert result["SOURCE_PROOF_LOCATOR"] == (
        "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1201]"
    )
    assert result["FROZEN_LEDGER_MUTATED"] is False


def test_full_relaxation_and_independent_analytic_cap(result: dict[str, object]) -> None:
    assert result["PROOF_SCOPE"] == "FULL_PROFILE"
    assert result["GOODMAN_CONSTANT"] == 296
    assert result["RELAXATION_STATE_COUNT"] == 1798
    assert result["PROVED_T_CAP"] == 248
    assert result["INDEPENDENT_ANALYTIC_CAP"] == 252
    assert result["UNPROVED_ASSUMPTIONS"] == []
    assert result["EXACT_PROFILE_MAXIMUM"] == "UNKNOWN"
    assert len(set(c.states())) == 1798
    # Symmetry reduction is also compared to the unfactored Cartesian product.
    reference = {
        (a, q, b, v, z)
        for a in range(9)
        for q in range(3)
        for b in range(4)
        for v in range(6)
        for z in c.combinations_with_replacement(range(1, 7), 6)
        if a + q + b + v == sum(z) and sum(z) % 2 == 0
    }
    assert reference == set(c.states())


def test_aggregation_keeps_all_three_degree5_units() -> None:
    # The d=5 core complement degree is 2+sigma, so a=1 contributes THREE.
    assert c.objective((1, 0, 0, 0, (1,) * 6)) == 240
    assert c.raw_f(c.CORE, (0,) * 3 + (1,) + (0,) * 10, (1,) * 6) == 240


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("ALLOW_ZERO_ZETA", 274),
        ("OMIT_EQUAL_SUMS", 458),
        ("OMIT_PARITY", 251),
        ("ALLOW_P_MINUS_ONE_AT_RELAXED_MAXIMUM", 249),
    ],
)
def test_removed_premises_produce_counterexamples(
    result: dict[str, object],
    name: str,
    expected: int,
) -> None:
    negatives = c.frozen.object_row(result["NEGATIVE_CASE_RESULTS"])
    assert negatives[name] == expected > 248


def test_stronger_unproved_cap_rejected() -> None:
    with patch.object(c, "PROVED_CAP", 247), pytest.raises(AssertionError, match="T248"):
        c.theorem()


def test_explicit_legal_target_realization(result: dict[str, object]) -> None:
    seen = c.frozen.object_row(result["NONVACUITY_REALIZATION"])
    assert (seen["T_G"], seen["T_H"], seen["P"], seen["F"]) == (238, 58, 4, 242)
    assert seen["P_TERMS"] == [4, 0, 0, 0]
    assert seen["A_ZERO"] == [0] * 6
    assert c.check_realization(*c.witness()) == seen


def test_pair_linearity_and_ticket_capacity_reject_real_mutations() -> None:
    triples, pairs = c.witness()
    with pytest.raises(ValueError, match="distinct"):
        c.check_realization(triples, (pairs[1], *pairs[1:]))
    with pytest.raises(ValueError, match="reuse a core ticket pair"):
        c.check_realization(triples, (triples[0][:2], *pairs[1:]))
    # Replace 0-19 by 1-19: no repeated pair, but ticket capacities become 5 and 7.
    with pytest.raises(ValueError, match="fill each ticket to six"):
        c.check_realization(triples, (*pairs[:-1], (1, 19)))


@pytest.mark.parametrize(
    ("sigma", "zeta", "message"),
    [
        ((0,) * 14, (0, 1, 1, 1, 1, 1), "zero cross-degree range"),
        ((0,) * 14, (1,) * 6, "balance"),
        ((0,) * 3 + (1,) + (0,) * 7 + (0, 0, 0), (1,) * 6, "balance"),
        ((1,) + (0,) * 13, (1,) * 6, "support capacity"),
        ((0,) * 11 + (2, 0, 5), (1, 1, 1, 1, 1, 2), "parity"),
    ],
)
def test_illegal_projection_rejected(
    sigma: tuple[int, ...], zeta: tuple[int, ...], message: str
) -> None:
    with pytest.raises(AssertionError, match=message):
        c.project(c.PROFILE, sigma, zeta)


def test_exact_graph_identity_on_all_1024_small_graphs() -> None:
    edges = list(combinations(range(5), 2))
    positive = 0
    for mask in range(1 << len(edges)):
        graph = {e for i, e in enumerate(edges) if mask & (1 << i)}
        seen = c.frozen.complement_split((0, 1, 2), (3, 4), graph)
        sigma = [c.frozen.integer(v) for v in c.frozen.rows(seen["SIGMA"])]
        zeta = [c.frozen.integer(v) for v in c.frozen.rows(seen["ZETA"])]
        hc = [c.frozen.integer(v) for v in c.frozen.rows(seen["H_CORE"])]
        hz = [c.frozen.integer(v) for v in c.frozen.rows(seen["A_ZERO"])]
        p = c.frozen.integer(seen["P"])
        bare = (
            2 * c.frozen.integer(seen["M_EDGES"])
            + 3 * c.frozen.integer(seen["MZ_EDGES"])
            - sum(x * y for x, y in zip(sigma, hc, strict=True))
            - sum(x * y for x, y in zip(zeta, hz, strict=True))
        )
        assert seen["T_H"] == bare + p
        assert p >= 0
        positive += p > 0
    assert positive > 0


def test_route_b_whole_envelope_and_no_family_claim(result: dict[str, object]) -> None:
    assert result["NEW_ADMISSIBLE_BOUND"] == 313249020
    assert result["OWNER_DELTA"] == 143392
    assert result["EXPECTED_BOUND_AT_CAP_263"] == 313383256
    assert result["ARGMAX_TERM"] == (248, 313249020, 370, 199, 205261, 4976272)
    assert result["BELOW_NEXT_COMPETITOR"] is True
    assert result["CERTIFIED_TERM_COUNT"] == 227
    assert len(c.frozen.rows(result["ALL_T_TERMS_THROUGH_SOURCE_CAP"])) == 243
    assert result["FAMILY_GAIN_CLAIMED"] == result["NEW_WINNING_OUTCOMES"] == 0
    assert result["HEAVY_SOLVER_STARTED"] == "NO"
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert json.loads(c.RESULT_PATH.read_bytes())["NEW_ADMISSIBLE_BOUND"] == 313249020


def test_rounding_and_domain_mutations_fail() -> None:
    original = c.frozen.r32.route_b_envelope

    def wrong_rounding(profile: tuple[int, ...], cap: int, base: int) -> list[c.Term]:
        terms = original(profile, cap, base)
        t, bound, k4, a, s4, s3 = terms[-1]
        return [*terms[:-1], (t, bound - 1, k4, a, s4, s3)]

    with (
        patch.object(c.frozen.r32, "route_b_envelope", wrong_rounding),
        pytest.raises(AssertionError, match="exact rounding"),
    ):
        c.route_b(248, 112)
    with (
        patch.object(c.frozen.r32, "route_b_envelope", return_value=original(c.PROFILE, 247, 112)),
        pytest.raises(AssertionError, match="missing triangle term"),
    ):
        c.route_b(248, 112)
