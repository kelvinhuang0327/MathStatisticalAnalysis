"""Focused mathematical, authority, arithmetic and falsifiability checks; no solver."""

from __future__ import annotations

import json
from dataclasses import replace
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from unittest.mock import patch

import pytest

from lottolab.research import b649_next_coowner_b_66665555544441000000_r1 as c


@pytest.fixture(scope="module")
def authority() -> dict[str, object]:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("authority replay invoked new research/search")

    with (
        patch.object(c.frozen.chase, "chase", forbidden),
        patch.object(c.frozen.chase, "refine", forbidden),
        patch.object(c.frozen.split, "degree_configurations", forbidden),
        patch.object(c.frozen.split, "split_certificate", forbidden),
        patch.object(c.frozen.three, "core_zero_theorem", forbidden),
        patch.object(c.frozen.three, "witness", forbidden),
        patch.object(c.frozen, "compute_result", forbidden),
    ):
        return c.authority()


def test_frozen_identity_and_exact_committed_result(authority: dict[str, object]) -> None:
    assert authority["FROZEN_HEAD_TREE"] == authority["FROZEN_RESULT_SHA256"] == "MATCH"
    assert authority["FROZEN_LEDGER_ROWS"] == 4647
    assert (
        authority["SOURCE_T_CAP"],
        authority["SOURCE_S4_BASE"],
        authority["SOURCE_ROW_BOUND"],
    ) == (
        264,
        112,
        313392412,
    )
    assert str(authority["SOURCE_LOCATOR"]).endswith("NB_CERTIFICATES[912]")
    with patch.object(c, "authority", return_value=authority):
        actual = c.compute_result()
    assert c.render(actual) == c.RESULT_PATH.read_bytes()
    assert actual["PROOF_SCOPE"] == "FULL_PROFILE"
    assert actual["NEW_ADMISSIBLE_BOUND"] == 313231096
    assert actual["OWNER_BOUND_DELTA"] == 161316
    assert actual["BELOW_NEXT_COMPETITOR"] is True
    assert actual["UNPROVED_ASSUMPTIONS"] == []
    assert actual["FAMILY_GAIN_CLAIMED"] == actual["NEW_WINNING_OUTCOMES"] == 0
    assert actual["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"


def test_goodman_is_derived_for_this_profile() -> None:
    facts = c.profile_facts()
    assert (facts["GOODMAN_CONSTANT"], facts["H_WEDGES"]) == (296, 902)
    assert (facts["G_EDGES"], facts["H_EDGES"]) == (93, 97)
    with pytest.raises(AssertionError, match="profile-specific"):
        c.profile_facts((*c.DEGREES[:-2], 1, 0))
    with patch.object(c, "GOODMAN", 298), pytest.raises(AssertionError, match="Goodman"):
        c.profile_facts()


def test_labelled_core_product_maps_onto_exact_multiset_superset() -> None:
    # Independent loops over ALL labelled core choices; no graphicality filter.
    zeros: dict[int, list[tuple[int, ...]]] = {}
    for z in combinations_with_replacement(range(1, 7), 6):
        zeros.setdefault(sum(z), []).append(z)
    compressed: set[c.State] = set()
    for binary in product(range(2), repeat=5):
        for q in product(range(3), repeat=4):
            for p in range(6):
                a, qs = sum(binary), tuple(sorted(q))
                r = a + sum(q) + p
                if r % 2 == 0:
                    compressed.update(c.State(a, qs, p, z) for z in zeros.get(r, []))
    states = list(c.configurations())
    assert len(states) == len(set(states)) == 1453
    assert set(states) == compressed


def test_exact_split_and_deficit_identity_over_complete_relaxation() -> None:
    states = list(c.configurations())
    for s in states:
        c.certify_state(s)
        assert len(s.sigma) == 14
        assert sum(s.sigma) == sum(s.zeta) == s.r
        assert all(v <= 6 - d for v, d in zip(s.sigma, c.CORE, strict=True))
        assert c.generic_split_objective(s) == c.objective(s) == 249 - c.deficit(s)
        assert c.deficit(s) >= 3
    assert max(map(c.objective, states)) == 246
    assert [s for s in states if c.objective(s) == 246] == [
        c.State(3, (2, 2, 2, 2), 5, (1, 1, 1, 1, 6, 6)),
    ]


def test_remainder_cardinality_identity_on_all_five_vertex_graphs() -> None:
    edges = list(combinations(range(5), 2))
    positive = [False] * 4
    for mask in range(1 << len(edges)):
        graph = {edge for i, edge in enumerate(edges) if mask & (1 << i)}
        for k in (2, 3):
            seen = c.graph_decomposition(5, k, graph)
            parts = c.frozen.rows(seen["P_PARTS"])
            positive = [
                old or c.frozen.integer(v) > 0 for old, v in zip(positive, parts, strict=True)
            ]
            assert seen["P"] == sum(c.frozen.integer(v) for v in parts)
    assert all(positive)  # Each of the four remainder summands is exercised.


@pytest.mark.parametrize("case", c.negative_cases())
def test_each_load_bearing_premise_rejects_its_countermodel(case: dict[str, object]) -> None:
    raw = c.frozen.object_row(json.loads(c.render(case["STATE"])))
    s = c.State(
        c.frozen.integer(raw["a"]),
        tuple(c.frozen.integer(v) for v in c.frozen.rows(raw["q"])),
        c.frozen.integer(raw["p"]),
        tuple(c.frozen.integer(v) for v in c.frozen.rows(raw["zeta"])),
    )
    premise = c.frozen.text(case["REMOVED_PREMISE"])
    assert c.premise_failures(s) == [premise]
    assert c.objective(s) == case["F"]
    assert c.objective(s) > 246
    with pytest.raises(AssertionError, match=premise):
        c.certify_state(s)


def test_cross_sum_and_binary_degree_five_are_guarded() -> None:
    s = c.State(3, (2, 2, 2, 2), 5, (1, 1, 1, 1, 6, 6))
    with pytest.raises(AssertionError, match="EQUAL_CROSS_EDGE_SUMS"):
        c.certify_state(replace(s, zeta=(1, 1, 1, 2, 6, 6)))
    assert "DEGREE_5_BINARY_CAPACITY" in c.premise_failures(replace(s, a=6))


def test_widening_parity_really_breaks_the_cap() -> None:
    assert max(c.objective(s) for s in c.configurations(even=False)) == 247
    assert max(c.objective(s) for s in c.configurations(p_max=6)) == 260
    assert max(c.objective(s) for s in c.configurations(q_max=3)) == 261
    assert max(c.objective(s) for s in c.configurations(z_min=0)) == 271
    assert max(c.objective(s) for s in c.configurations(z_max=7)) == 256


def test_route_b_every_integer_and_rational_term() -> None:
    terms = c.route_b(264)
    assert [t[0] for t in terms] == list(range(22, 265))
    assert terms[-1] == (264, 313392412, 490, 199, 286741, 5166224)
    assert terms[-2] == (263, 313383256, 483, 199, 281988, 5154352)
    new = c.route_b(246)
    assert new == terms[:225]
    assert max(new, key=lambda t: t[1]) == (246, 313231096, 355, 199, 195076, 4952528)
    for t, bound, k4, contained, s4, s3 in terms:
        assert 4 * k4 >= 2340 - 10 * (830 - 3 * t)
        assert k4 == 0 or 4 * (k4 - 1) < 2340 - 10 * (830 - 3 * t)
        assert contained == min(k4, 199)
        assert s4 == max(112, 448 * contained + 679 * (k4 - contained))
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        assert Fraction(bound - 1) < exact <= bound
    # All sealed weights/base are multiples of seven; their corrections are integral.
    assert all(Fraction(4 * term[4], 7).denominator == 1 for term in terms)
    # Arithmetic stress fixture only: a different base exercises a fractional credit.
    with patch.object(c, "S4_BASE", 113):
        _, bound, _, _, s4, s3 = c.route_b(22)[0]
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        assert s4 == 113 and Fraction(4 * s4, 7).denominator == 7
        assert Fraction(bound - 1) < exact < bound


def test_certificate_fails_under_controlled_formula_mutations() -> None:
    original = c.objective

    def wrong_objective(s: c.State) -> int:
        return original(s) + 1

    with (
        patch.object(c, "objective", side_effect=wrong_objective),
        pytest.raises(AssertionError, match="identity"),
    ):
        c.theorem()
    with patch.object(c, "PROVED_CAP", 245), pytest.raises(AssertionError, match="cap"):
        c.theorem()
    assert c.theorem()["PROVED_T_CAP"] == 246  # Both mutations restored.


def test_pinned_identity_fails_closed_before_replay() -> None:
    with (
        patch.object(c, "FROZEN_RESULT_SHA256", "0" * 64),
        patch.object(
            c.frozen, "six_row_authority", side_effect=AssertionError("should not replay")
        ),
        pytest.raises(AssertionError, match="frozen result digest"),
    ):
        c.authority()


def test_result_does_not_upgrade_judge_or_claim_family_gain() -> None:
    stored = json.loads(c.RESULT_PATH.read_bytes())
    assert stored["JUDGE_MODE"] == "SELF_CHECK_ONLY"
    assert stored["TASK_STATUS"] == "COMPLETE_SELF_CHECK_ONLY"
    assert stored["ATTAINMENT"] == "NOT_ASSERTED"
    assert stored["FAMILY_GAIN_CLAIMED"] == stored["NEW_WINNING_OUTCOMES"] == 0
    assert stored["HEAVY_SOLVER_STARTED"] == "NO"
    assert stored["PRODUCTION_MUTATION"] == "NONE"
