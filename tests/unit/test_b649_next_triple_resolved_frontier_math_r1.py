"""Arithmetic and adversarial checks supplement the universal written proof."""

import copy
import itertools
import json
import resource
from fractions import Fraction

import pytest

from lottolab.research import b649_next_triple_resolved_frontier_math_r1 as m

resource.setrlimit(resource.RLIMIT_CPU, (120, 120))


@pytest.fixture(scope="module")
def sources():
    capture = m.load_capture()
    authority, snapshots = m.source_authority(capture)
    return capture, authority, snapshots


def test_fixed_git_sources_and_actual_catalog_rows(sources):
    capture, authority, snapshots = sources
    assert authority["BASE_HEAD"] == m.BASE_HEAD
    assert authority["BASE_TREE"] == m.BASE_TREE
    assert (authority["BASE_EVENTS"], authority["BASE_ROWS"]) == (27, 4647)
    assert [s["PROFILE_ID"] for s in snapshots] == list(m.TARGETS)
    assert [s["ROW_SOURCE"].rsplit("[", 1)[1] for s in snapshots] == ["1616]", "1466]", "1450]"]
    assert all(
        (s["ORIGINAL_CAP"], s["S4_BASE"], s["OLD_BOUND"]) == (266, 112, 313391844)
        for s in snapshots
    )
    assert capture["exit_status"] == 0


@pytest.mark.parametrize("index", range(3))
def test_full_profile_analytic_constants_and_every_coordinate(sources, index):
    s = sources[2][index]
    p = m.premises(s)
    assert p["PHI_INCLUSION_EXCLUSION"] == p["PHI_GOODMAN"] == 290
    assert (p["CORE"], p["ZERO"], p["G_EDGES"], p["H_EDGES"]) == (15, 5, 93, 97)
    assert p["PROVED_T_CAP"] == 262
    for degree, values in p["SIGMA_RANGES"].items():
        d = int(degree)
        expected = {6: 0, 5: 0, 4: 4, 3: 12, 2: 24, 1: 40}[d]
        assert max(v * (v + 4 - d) for v in values) == expected
    assert all(q * q <= 8 * q - 12 for q in p["ZETA_RANGE"])


@pytest.mark.parametrize("index", range(3))
def test_split_identity_on_balanced_endpoint_and_interior_vectors(sources, index):
    s = sources[2][index]
    d = s["DEGREES"][:15]
    checked = 0
    # A small arithmetic audit; the written universal proof is the coverage argument.
    for total in range(10, 23):
        sigma = [0] * 15
        remaining = total
        for i in range(14, -1, -1):
            sigma[i] = min(6 - d[i], remaining)
            remaining -= sigma[i]
        if remaining:
            continue
        zeta = [2] * 5
        remaining = total - 10
        for i in range(5):
            extra = min(4, remaining)
            zeta[i] += extra
            remaining -= extra
        for remainder in (0, 1, 17):
            direct, upper = m.split_values(s, sigma, zeta, remainder)
            assert direct <= upper <= 262 - remainder
            checked += 1
    assert checked == 39


def test_goodman_and_remainder_on_all_four_vertex_graphs_and_partitions():
    # Independent graph observation, not a solver or a target-profile sample proof.
    edges = list(itertools.combinations(range(4), 2))
    count = 0
    for mask in range(1 << len(edges)):
        graph = {e for i, e in enumerate(edges) if mask & (1 << i)}
        for part in range(1 << 4):
            core = {v for v in range(4) if part & (1 << v)}
            seen = m.graph_identities(4, core, graph)
            assert min(seen["P_TERMS"]) >= 0
            count += 1
    assert count == 1024


@pytest.mark.parametrize("index", range(3))
def test_complete_integer_fraction_and_existing_route_b_recounts(sources, index):
    certificate = m.certify(sources[2][index])
    assert certificate["OLD_TERM_COUNT"] == 245
    assert certificate["FULL_TERM_COUNT"] == 241
    assert certificate["OLD_ARGMAX_TERM"] == [266, 313391844, 508, 195, 299887, 5173168]
    assert certificate["ARGMAX_TERM"] == [262, 313355996, 478, 195, 279517, 5125680]
    assert certificate["NEW_BOUND"] <= 313391740
    assert certificate["ROUTE_B_TERMS"] == certificate["OLD_ROUTE_B_TERMS"][:241]
    assert certificate["UNPROVED_ASSUMPTIONS"] == []
    assert certificate["T_ENDPOINT_ATTAINMENT"] == "NOT_ASSERTED"


@pytest.mark.parametrize("index", range(3))
def test_all_requested_negative_cases_are_rejected(sources, index):
    cases = m.negative_cases(sources[2][index])
    expected = {
        "Wrong Profile",
        "Wrong Degree Distribution",
        "Wrong Source Cap",
        "Invalid Capacity Constraint",
        "Invalid Cross-edge Balance",
        "Negative Remainder",
        "Incomplete Relaxation Coverage",
        "Wrong K4 Ceiling",
        "Wrong S4 Credit",
        "Wrong S4 Floor",
        "Wrong Contained Allowance",
        "Incomplete Route-B Domain",
        "Wrong Rounding",
    }
    assert set(cases) == expected
    assert set(cases.values()) == {"PASS"}
    print(
        json.dumps(
            {"PROFILE_ID": sources[2][index]["PROFILE_ID"], "NEGATIVES_REJECTED": len(cases)}
        )
    )


def test_source_capture_tampering_is_rejected(sources):
    capture = sources[0]
    for field, value in (("exit_status", 1), ("ended_at", None)):
        bad = copy.deepcopy(capture)
        bad[field] = value
        with pytest.raises(ValueError):
            m.validate_capture(bad)
    bad = copy.deepcopy(capture)
    bad["execution_identity"]["head"] = "0" * 40
    with pytest.raises(ValueError, match="Git objects"):
        m.validate_capture(bad)
    bad = copy.deepcopy(capture)
    bad["command"][-1] += "\nprint('tampered')"
    with pytest.raises(ValueError, match="extraction command"):
        m.validate_capture(bad)


def test_rounding_all_seven_credit_remainders():
    # Synthetic arithmetic cases are explicit because all real S4 floors divide by seven.
    for s4 in range(14):
        exact = Fraction(1000) - Fraction(4 * s4, 7)
        ceil = -((-exact.numerator) // exact.denominator)
        m.verify_rounding(1000, s4, ceil)
        if exact.denominator != 1:
            with pytest.raises(ValueError, match="rounding"):
                m.verify_rounding(1000, s4, exact.__floor__())


def test_result_preserves_scope_and_prospective_authority(sources):
    result = m.build_result(sources[0])
    assert result["THREE_PROFILE_FRONTIER_RESULT"] == "PROVED"
    assert result["NEW_BOUND_EACH"] == 313355996
    assert len(result["CERTIFICATES"]) == 3
    assert result["FAMILY_GAIN"] == "NOT_CLAIMED"
    assert (
        result["BASE_MAX_RESOLVED_BOUND"]
        == result["PROSPECTIVE_BASE_PLUS_CLASS197_MAX"]
        == 313392128
    )
    assert result["NEXT_PROSPECTIVE_BOUND"] == "UNKNOWN"
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"
    assert (
        result["NEW_WINNING_OUTCOMES"]
        == result["FAMILY_LEDGER_WRITES"]
        == result["SOLVER_CALLS"]
        == 0
    )
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
