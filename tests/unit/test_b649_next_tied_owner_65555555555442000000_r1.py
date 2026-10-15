"""Focused scientific checks; mutations exercise the actual bearing premises."""

from __future__ import annotations

import resource
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from lottolab.research import b649_next_tied_owner_65555555555442000000_r1 as c


@pytest.fixture(scope="module")
def result() -> Iterator[dict[str, object]]:
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("a solver, profile search, or old certificate was rerun")

    with (
        patch.object(c.frozen.split, "degree_configurations", forbidden),
        patch.object(c.frozen.split, "split_certificate", forbidden),
        patch.object(c.frozen.chase, "chase", forbidden),
        patch.object(c.frozen.chase, "refine", forbidden),
        patch.object(c.frozen, "compute_result", forbidden),
        patch.object(c.frozen.three, "compute_result", forbidden),
    ):
        yield c.compute_result()


def test_frozen_authority_and_exact_result(result: dict[str, object]) -> None:
    assert result["FROZEN_HEAD_TREE"] == result["FROZEN_RESULT_SHA256"] == "MATCH"
    assert result["SOURCE_T_CAP"] == 266
    assert result["SOURCE_S4_BASE"] == 112
    assert result["SOURCE_ROW_BOUND"] == 313392232
    assert c.RESULT_PATH.read_bytes() == c.frozen.two.render(result)


def test_full_profile_cap_and_exact_envelope(result: dict[str, object]) -> None:
    assert result["PROOF_SCOPE"] == "FULL_PROFILE"
    assert result["PROVED_T_CAP"] == result["RECTANGULAR_MAXIMUM"] == 252
    assert result["GOODMAN_CONSTANT"] == 290
    assert result["IDENTITY_POINTS_CHECKED"] == 41
    assert result["UNPROVED_ASSUMPTIONS"] == []
    assert result["ARGMAX_TERM"] == [252, 313266764, 402, 195, 227913, 5006960]
    assert result["EXPECTED_CAP265_BOUND"] == 313383464
    assert result["OWNER_DELTA"] == 125468
    assert result["BELOW_NEXT_COMPETITOR"] is True
    assert result["FAMILY_GAIN_CLAIMED"] == result["NEW_WINNING_OUTCOMES"] == 0
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"


@pytest.mark.parametrize(
    ("degree", "values", "message"),
    [(2, range(6), "low-core square"), (4, range(4), "high-core inequality")],
)
def test_core_capacity_is_load_bearing(degree: int, values: range, message: str) -> None:
    ranges = {d: range(7 - d) for d in (6, 5, 4, 2)}
    # Minimal illegal extensions: 5^2>16 at d=2, and 3(3-2)>0 at d=4.
    with pytest.raises(AssertionError, match=message):
        c.certify_coordinates({**ranges, degree: values}, range(1, 7))


def test_zero_capacity_is_load_bearing() -> None:
    # The added coordinate 7 contributes +7, breaking the nonpositive-zero step.
    with pytest.raises(AssertionError, match="zero coordinate is positive"):
        c.certify_coordinates({d: range(7 - d) for d in (6, 5, 4, 2)}, range(1, 8))


@pytest.mark.parametrize("name", ["CORE_SHIFT", "ZERO_SHIFT"])
def test_wrong_identity_coefficient_is_rejected(name: str) -> None:
    with patch.object(c, name, 3), pytest.raises(AssertionError, match="F polynomial"):
        c.theorem()


@pytest.mark.parametrize(
    ("field", "value"),
    [("STATUS", "UNKNOWN"), ("PROFILE_IDS", ["invalid-profile"])],
)
def test_cap_source_identity_rejected(result: dict[str, object], field: str, value: object) -> None:
    proof = c.frozen.object_row(result["R30_CAP_AUTHORITY"])
    with pytest.raises(AssertionError, match="R30 cap authority mismatch"):
        c.validate_cap_authority({**proof, field: value})


@pytest.mark.parametrize("index", [1, 2, 3, 4])
def test_route_b_rounding_and_integer_term_mutations(index: int) -> None:
    terms = c.route_b(265)
    bad = list(terms[-1])
    bad[index] += 1
    # Bound, K4 ceiling, contained allowance, and S4 credit each fail independently.
    term: c.Term = (bad[0], bad[1], bad[2], bad[3], bad[4], bad[5])
    with pytest.raises(AssertionError, match=r"rounding differs|integer terms differ"):
        c.validate_terms([*terms[:-1], term], 265)


def test_explicit_profile_is_nonempty_and_remainder_is_counted() -> None:
    seen = c.check_realization(*c.witness())
    assert seen["T_G"] == 198
    assert seen["T_H"] == 92
    assert seen["P_TERMS"] == [4, 0, 0, 0]
    assert seen["F"] == 202


def test_pair_linearity_negative_preserves_support_counts() -> None:
    triples, pairs = c.witness()
    with pytest.raises(AssertionError, match="share more than one label"):
        c.check_realization(triples, (*pairs[:-1], pairs[0]))


def test_ticket_capacity_negative_is_pair_linear() -> None:
    triples, pairs = c.witness()
    # A fresh unused pair preserves 22/27 counts and pair-linearity but overfills
    # ticket 4 and underfills ticket 18. It reaches the actual six-label check.
    with pytest.raises(AssertionError, match="exactly six labels"):
        c.check_realization(triples, (*pairs[:-1], (4, 19)))
