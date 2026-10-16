"""Focused proof audits and negative controls; these tests are not the proof."""

import copy
import hashlib
import json
from fractions import Fraction

import pytest

from lottolab.research import b649_next_tied_resolved_frontier_math_r1 as m


@pytest.fixture(scope="module")
def result():
    record = json.loads(m.RESULT_PATH.read_bytes())
    digest = record.pop("RESULT_SHA256")
    assert (
        hashlib.sha256(
            json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == digest
    )
    record["RESULT_SHA256"] = digest
    assert record["PROOF_SHA256"] == m.sha(m.PROOF_PATH.read_bytes())
    return record


@pytest.mark.parametrize(
    "index,cap,bound,count", [(0, 224, 313015432, 203), (1, 222, 312995528, 201)]
)
def test_full_profile_certificate_arithmetic(result, index, cap, bound, count):
    saved = result["CERTIFICATES"][index]
    rebuilt = m.certify(saved["SOURCE_IDENTITY"])
    for key, value in rebuilt.items():
        assert saved[key] == value
    assert saved["PROVED_T_CAP"] == cap
    assert saved["NEW_BOUND"] == bound < m.OLD_BOUND
    assert saved["ROUTE_B_TERM_COUNT"] == count
    assert saved["ARGMAX_TERM"][0] == cap
    assert saved["R32_RECOUNT"] == "ALL_OLD_AND_NEW_TERMS_MATCH"
    assert saved["PROOF_SCOPE"] == "FULL_PROFILE"


def test_wrong_profile_rejected(result):
    source = copy.deepcopy(result["CERTIFICATES"][0]["SOURCE_IDENTITY"])
    source["PROFILE_ID"] = "0" * 20
    with pytest.raises(ValueError, match="wrong profile"):
        m.certify(source)


def test_wrong_histogram_rejected(result):
    source = copy.deepcopy(result["CERTIFICATES"][0]["SOURCE_IDENTITY"])
    # Preserve 20 vertices and the incidence sum while changing the histogram.
    source["DEGREES"][1] -= 1
    source["DEGREES"][13] += 1
    with pytest.raises(ValueError, match="wrong degree histogram"):
        m.certify(source)


@pytest.mark.parametrize("index", [0, 1])
def test_unsupported_t_cap_rejected(result, index):
    c = result["CERTIFICATES"][index]
    with pytest.raises(ValueError, match="unsupported T cap"):
        m.certify(c["SOURCE_IDENTITY"], claimed_cap=c["PROVED_T_CAP"] - 1)


def test_missing_support_capacity_rejected(result):
    source = copy.deepcopy(result["CERTIFICATES"][0]["SOURCE_IDENTITY"])
    source["SUPPORT_MODEL"].pop("TICKET_CAPACITY")
    with pytest.raises(ValueError, match="support/capacity"):
        m.certify(source)


def valid_split(result):
    d = tuple(result["CERTIFICATES"][0]["SOURCE_IDENTITY"]["DEGREES"])
    # Necessary-condition vector only; no support realization is claimed.
    sigma = (0,) * 11 + (1, 1, 4)
    zeta = (1,) * 6
    return d, sigma, zeta


def test_split_identity_and_majorant(result):
    d, sigma, zeta = valid_split(result)
    direct, majorant = m.split_values(d, sigma, zeta, 0)
    assert direct == 220
    assert majorant == 220
    assert direct <= majorant <= 224


def test_invalid_cross_edge_balance_rejected(result):
    d, sigma, zeta = valid_split(result)
    with pytest.raises(ValueError, match="cross-edge balance"):
        m.split_values(d, sigma, (*zeta[:-1], 2), 0)


def test_capacity_constraint_rejects_enlarged_core_range(result):
    d, sigma, zeta = valid_split(result)
    invalid = (1, *sigma[1:])  # A degree-six core ticket has no pair slot.
    with pytest.raises(ValueError, match="capacity constraint"):
        m.split_values(d, invalid, (*zeta[:-1], 2), 0)


def test_zero_lower_capacity_rejected(result):
    d, sigma, zeta = valid_split(result)
    with pytest.raises(ValueError, match="zero capacity"):
        m.split_values(d, sigma, (0, 2, *zeta[2:]), 0)


def test_negative_remainder_rejected(result):
    d, sigma, zeta = valid_split(result)
    with pytest.raises(ValueError, match="negative remainder"):
        m.split_values(d, sigma, zeta, -1)


def test_incomplete_coordinate_coverage_rejected(result):
    p = copy.deepcopy(result["CERTIFICATES"][0]["PREMISES"])
    p["CORE_COORDINATE_VALUES"]["2"].pop()
    with pytest.raises(ValueError, match="incomplete coordinate coverage"):
        m.verify_coordinate_coverage(p)


def test_missing_route_b_term_rejected(result):
    c = result["CERTIFICATES"][0]
    terms = copy.deepcopy(c["ROUTE_B_TERMS"])
    terms.pop(50)
    with pytest.raises(ValueError, match="missing Route-B term"):
        m.verify_route(tuple(c["SOURCE_IDENTITY"]["DEGREES"]), c["PROVED_T_CAP"], terms)


def test_incorrect_rounding_rejected(result):
    c = result["CERTIFICATES"][0]
    terms = copy.deepcopy(c["ROUTE_B_TERMS"])
    terms[-1][1] -= 1
    with pytest.raises(ValueError, match="incorrect ceiling/rounding"):
        m.verify_route(tuple(c["SOURCE_IDENTITY"]["DEGREES"]), c["PROVED_T_CAP"], terms)
    # At A's endpoint the K4 expression is 191.5, which must round UP.
    exact_k = Fraction(2286 - 10 * (824 - 3 * 224), 4)
    assert exact_k == Fraction(383, 2)
    assert c["ARGMAX_TERM"][2] == 192
    terms = copy.deepcopy(c["ROUTE_B_TERMS"])
    terms[-1][2] = 191
    with pytest.raises(ValueError, match="incorrect ceiling/rounding"):
        m.verify_route(tuple(c["SOURCE_IDENTITY"]["DEGREES"]), c["PROVED_T_CAP"], terms)


def test_algebra_as_polynomial_coefficients(result):
    # This checks equality of quadratic coefficients, without sampling graphs.
    # Direct F - balanced F = 2*(sum sigma - sum zeta).
    for c in result["CERTIFICATES"]:
        core = [d for d in c["SOURCE_IDENTITY"]["DEGREES"] if d]
        assert 290 - 3 * sum(7 - d for d in core) + 42 == 236
        assert all((4 - d) - (2 - d) == 2 for d in core)
        assert -8 - (-6) == -2
        assert all(q * (q - 6) <= q - 6 for q in range(1, 7))
        # Whole continuous intervals are covered by convexity; the endpoint
        # values also bound every integer in each legal coordinate range.
        for d in core:
            endpoint = max(0, (6 - d) * (9 - 2 * d))
            assert all(s * (s + 3 - d) <= endpoint for s in range(7 - d))


def test_frontier_and_scope_accounting(result):
    assert result["SINGLE_OWNER_UPDATE_FRONTIER"] == 313392232
    assert (
        result["HYPOTHETICAL_RESOLVED_FRONTIER_STRICT_DECREASE"] == "PROVED_FROM_SOLE_TIED_OWNERS"
    )
    assert result["FAMILY_GAIN_WITH_OLD_CURSOR"] == 0
    assert result["FAMILY_WITH_OLD_CURSOR"] == 313394584
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"
    assert result["FINITE_RELAXATION_SEARCH"] == "NOT_USED"
    assert result["NEW_WINNING_OUTCOMES"] == 0
