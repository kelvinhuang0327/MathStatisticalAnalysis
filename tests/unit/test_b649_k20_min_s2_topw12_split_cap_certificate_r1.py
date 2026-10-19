"""Eight correctness checks for the conditional split cap and complete family aggregate."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping

import pytest

from lottolab.research import b649_k20_min_s2_topw12_split_cap_certificate_r1 as x

CAPS = {
    "66666665444331000000": 247, "66666664444440000000": 261,
    "66666655544430000000": 261, "66666655544421000000": 252,
    "66666655444440000000": 260, "66666555555330000000": 261,
    "66666555555321000000": 251, "66666555554430000000": 260,
    "66666555544440000000": 259, "66665555555520000000": 261,
    "66665555555511000000": 256, "66665555555430000000": 259,
}  # fmt: skip


@pytest.fixture(scope="module")
def derived() -> dict[str, object]:
    return x.compute_result()


def certificates(result: Mapping[str, object]) -> list[dict[str, object]]:
    return [x.object_row(raw) for raw in x.rows(result["TOP_W_CERTIFICATES"])]


def test_legal_p2_counterexample_is_accepted() -> None:
    witness = x.analyze_realization(*x.witness_supports("P2"))
    assert witness["PROFILE_ID"] == x.SPECIAL
    assert witness["P_TERMS"] == [0, 0, 0, 2] and witness["P_TOTAL"] == 2
    assert witness["TRIANGLES"] == 250 and witness["F"] == 252
    assert witness["BRANCH"] == "A_NONNEGATIVE_P" and witness["P_FLOOR_USED"] == 0


def test_p12_requires_both_low_vertices_to_have_five_zero_neighbours() -> None:
    p = x.profile_values(x.SPECIAL)
    # The legal counterexample has sigma_A=sigma_B=4, not the required five.
    c = x.configuration(p, (0,) * 12 + (4, 4), (1, 1, 1, 1, 2, 2))
    with pytest.raises(ValueError, match="sigma_A=sigma_B=5"):
        x.conditional_p_floor(c)
    assert x.branch_bound(c) == (252, 0, "A_NONNEGATIVE_P")
    # One saturated low vertex does not establish the joint prerequisite either.
    c = next(c for c in x.degree_configurations(p) if c.sigma[-2:] == (4, 5))
    with pytest.raises(ValueError, match="sigma_A=sigma_B=5"):
        x.conditional_p_floor(c)


def test_conditional_p12_is_proved_under_full_premises() -> None:
    witness = x.analyze_realization(*x.witness_supports("CONDITIONAL"))
    assert witness["PROFILE_ID"] == x.SPECIAL and witness["F"] == 266
    assert witness["BRANCH"] == "B_CONDITIONAL_P12"
    assert witness["P_FLOOR_USED"] == 12 and x.integer(witness["P_TOTAL"]) >= 12
    dangerous = [c for c in x.degree_configurations(x.SPECIAL) if c.f > 256]
    assert len(dangerous) == 5
    assert {c.zeta for c in dangerous} == {
        (1, 1, 2, 2, 2, 2),
        (1, 1, 2, 2, 2, 4),
        (1, 1, 2, 2, 3, 3),
        (1, 2, 2, 2, 2, 3),
        (1, 2, 2, 2, 2, 5),
    }
    for c in dangerous:
        assert c.sigma[-2:] == (5, 5)
        assert x.conditional_p_floor(c) == 12 + sum(c.sigma[4:12])
        assert x.branch_bound(c)[0] <= 256


def test_special_profile_has_safe_cap_256(derived: dict[str, object]) -> None:
    cert = next(c for c in certificates(derived) if c["PROFILE_ID"] == x.SPECIAL)
    assert cert["P0_TRIANGLE_CAP"] == 266 and cert["TRIANGLE_CAP"] == 256
    assert cert["DEGREE_CONFIGURATION_COUNT"] == 161
    assert cert["BRANCH_COUNTS"] == {"A_NONNEGATIVE_P": 156, "B_CONDITIONAL_P12": 5}
    assert cert["BRANCH_MAXIMA"] == {"A_NONNEGATIVE_P": 256, "B_CONDITIONAL_P12": 254}
    assert cert["ALL_T_MAX_BOUND"] == 313_338_820


def test_top_profile_cap_261_is_sharp(derived: dict[str, object]) -> None:
    cert = next(c for c in certificates(derived) if c["PROFILE_ID"] == x.TOP)
    witness = x.analyze_realization(*x.witness_supports("TOP"))
    assert witness["TRIANGLES"] == cert["TRIANGLE_CAP"] == 261
    assert witness["P_TOTAL"] == 0 and cert["DEGREE_CONFIGURATION_COUNT"] == 101
    assert cert["ALL_T_MAX_BOUND"] == 313_387_144


def test_sts13_triangle_270_witness_is_not_excluded(derived: dict[str, object]) -> None:
    witness = x.analyze_realization(*x.witness_supports("STS13"))
    assert witness["PROFILE_ID"] == "55555555555511111100"
    assert witness["TRIANGLES"] == 270
    assert x.object_row(derived["STS13_RELAXATION"])["TRIANGLE_CAP"] == 276
    terms = x.route_b_terms(x.profile_values(x.text(witness["PROFILE_ID"])), 270, 112)
    assert terms[270 - 22][1] >= 313_263_888


def test_all_twelve_caps_and_every_integer_term_pass(derived: dict[str, object]) -> None:
    certs = certificates(derived)
    assert {x.text(c["PROFILE_ID"]): c["TRIANGLE_CAP"] for c in certs} == CAPS
    assert derived["TOPW12_CERTIFIED_COUNT"] == len(certs) == 12
    assert derived["DEGREE_CONFIGURATION_COUNT"] == 4316
    assert derived["ALL_T_INTEGER_TERMS_CHECKED"] == 2836
    assert derived["TOPW12_MAX"] == 313_387_144
    for c in certs:
        p = x.profile_values(x.text(c["PROFILE_ID"]))
        cap = x.integer(c["TRIANGLE_CAP"])
        terms = x.rows(c["ALL_T_TERMS"])
        assert [x.rows(term)[0] for term in terms] == list(range(22, cap + 1))
        assert terms == [list(term) for term in x.route_b_terms(p, cap, x.integer(c["S4_BASE"]))]
        assert c["ALL_T_MAX_BOUND"] == max(x.integer(x.rows(term)[1]) for term in terms)
        assert c["STATUS"] == "PASS"


def test_complete_family_maximum_is_recomputed_and_result_replays(
    derived: dict[str, object],
) -> None:
    base = x.pinned_authority()
    certs = certificates(derived)
    family = x.family_recompute(base, certs)
    assert family["PROFILE_COVERAGE_COUNT"] == 4844 and family["UNCOVERED_PROFILE_COUNT"] == 0
    assert family["BASE_COMPLETE_FAMILY_UB"] == 313_476_764
    assert family["FAMILY_TERMS"] == {
        "RESOLVED_LEDGER_W786_834": 313_404_784,
        "TOP_W835_837": 313_387_144,
        "UNRESOLVED_CURSOR_W785_COARSE": 313_394_584,
    }
    assert family["FINAL_COMPLETE_FAMILY_UB"] == 313_404_784
    assert family["REMAINING_GAP"] == 140_896
    assert family["FINAL_BOUND_OWNER_IDS"] == ["66665555554440000000", "66655555555530000000"]
    with pytest.raises(AssertionError, match="exactly the twelve"):
        x.family_recompute(base, certs[:-1])
    with pytest.raises(AssertionError, match="exactly the twelve"):
        x.family_recompute(base, [certs[0], *certs[1:-1], certs[0]])
    tampered = copy.deepcopy(base)
    x.object_row(tampered["COVERAGE_AFTER_REPAIR"])["UNCOVERED_PROFILE_COUNT"] = 1
    with pytest.raises(AssertionError, match="coverage partition"):
        x.family_recompute(tampered, certs)
    assert json.loads(x.RESULT_PATH.read_text(encoding="utf-8")) == derived
