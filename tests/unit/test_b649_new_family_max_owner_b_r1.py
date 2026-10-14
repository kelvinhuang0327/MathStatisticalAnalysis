"""Focused guards for the one-inequality T<=255 cap of 66665555554431000000."""

from __future__ import annotations

import random
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from math import comb
from unittest.mock import patch

import pytest

from lottolab.research import b649_new_family_max_owner_b_r1 as c

Authority = tuple[dict[str, object], dict[str, c.Row]]


@pytest.fixture(scope="module")
def authority() -> Authority:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("ledger replay executed a proof/search entrypoint")

    with (
        patch.object(c.split, "degree_configurations", forbidden),
        patch.object(c.split, "split_certificate", forbidden),
        patch.object(c.chase, "chase", forbidden),
        patch.object(c.chase, "refine", forbidden),
        patch.object(c.three, "core_zero_theorem", forbidden),
        patch.object(c.t256, "t256_theorem", forbidden),
        patch.object(c.t256, "superset_check", forbidden),
        patch.object(c.t256, "compute_result", forbidden),
    ):
        return c.frozen_authority()


@pytest.fixture(scope="module")
def result(authority: Authority) -> dict[str, object]:
    # Reuse only the genuine, digest-validated replay in the fixture above.
    with patch.object(c, "frozen_authority", return_value=authority):
        return c.compute_result()


def test_committed_result_is_reproduced_exactly(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.two.render(result)
    assert result["EXPECTED_VALUES_MATCH"] is True
    assert result["EXPECTED_VALUE_DIFFERENCES"] == {}


def test_frozen_authority_and_source_row(authority: Authority) -> None:
    frozen, ledger = authority
    assert (frozen["FAMILY_BOUND_AFTER"], frozen["NEXT_COMPETING_BOUND"]) == (313398532, 313398248)
    assert len(ledger) == 4647
    row = c.source_row(ledger)
    assert (row.bound, row.cap, row.s4_base) == (313395344, 264, 112)
    assert row.source == c.SOURCE_LABEL


def test_result_scope_fields(result: dict[str, object]) -> None:
    assert (result["PROVED_T_CAP"], result["MAX_SUFFICIENT_CAP_FOR_313395164"]) == (255, 263)
    assert (result["NEW_ADMISSIBLE_BOUND"], result["OWNER_BOUND_DELTA"]) == (313314492, 80852)
    assert result["PRIORITY_THRESHOLD_MET"] is True
    assert result["ROW_BELOW_INCUMBENT"] is False
    assert (result["FAMILY_GAIN_CLAIMED"], result["LEDGER_ROWS_CHANGED"]) == (0, 0)
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["HEAVY_SOLVER_STARTED"] == "NO" and result["SOLVER_CALLS"] == 0


def test_theorem_premises_and_cap() -> None:
    theorem = c.theorem()
    assert theorem["STATUS"] == "PROVEN" and theorem["PROOF_SCOPE"] == "FULL_PROFILE"
    assert theorem["TRIANGLE_CAP"] == theorem["SEPARABLE_MAXIMUM"] == 255
    assert (theorem["CORE_MAXIMUM"], theorem["ZERO_MAXIMUM"]) == (48, -36)
    assert (theorem["G_EDGES"], theorem["H_EDGES"], theorem["W"], theorem["J"]) == (
        93,
        97,
        831,
        2349,
    )
    assert theorem["PHI_INCLUSION_EXCLUSION"] == theorem["PHI_GOODMAN"] == 297
    assert (theorem["IDENTITY_CONSTANT"], theorem["ZETA_FLOOR"]) == (243, 1)
    assert (theorem["DEGREE_SUM"], theorem["DEGREE_SQUARE_SUM"]) == (66, 336)
    assert (theorem["CORE_VERTICES"], theorem["ZERO_VERTICES"]) == (14, 6)
    assert theorem["SIGMA_RANGES"] == {
        "6": [0],
        "5": [0, 1],
        "4": [0, 1, 2],
        "3": [0, 1, 2, 3],
        "1": [0, 1, 2, 3, 4, 5],
    }
    assert theorem["ZETA_RANGE"] == [1, 2, 3, 4, 5, 6]
    assert theorem["E44_IDENTITY_POINTS_CHECKED"] == 1 + 2 * 20
    assert theorem["EQUALITY"] == {
        "CORE_ARGMAX_SUM": [12],
        "ZERO_ARGMAX_SUMS": [6, 11, 16, 21, 26, 31, 36],
        "BALANCED": False,
        "ATTAINED": False,
    }


def test_zero_floor_is_the_load_bearing_inequality() -> None:
    sigma, _zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match=r"zeta\(zeta-7\) <= -6"):
        c.certify_cap(sigma, range(7))
    ablation = c.ablation()
    assert (ablation["SEPARABLE_MAXIMUM"], ablation["BALANCED_MAXIMUM"]) == (291, 279)
    assert ablation["SUFFICIENT_CAP"] == 263 and ablation["LOAD_BEARING"] is True


@pytest.mark.parametrize(("degree", "values"), [(4, range(4)), (3, range(5)), (1, range(7))])
def test_widened_core_range_breaks_the_cap(degree: int, values: range) -> None:
    sigma, zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match="separable maximum is not the proved cap"):
        c.certify_cap({**sigma, degree: values}, zeta)


def test_widened_zero_range_above_capacity_breaks_the_chain() -> None:
    sigma, _zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match=r"zeta\(zeta-7\) <= -6"):
        c.certify_cap(sigma, range(1, 8))


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("GOODMAN_CONSTANT", 298, "premises"),
        ("IDENTITY_CONSTANT", 244, "premises"),
        ("ZETA_FLOOR", 0, "premises"),
        ("TICKET_CAPACITY", 7, "premises"),
        ("TARGET_PROFILE", "66655555555511100000", "premises"),
        ("CORE_TERM_CONSTANT", 4, "split of -10r"),
        ("ZERO_TERM_CONSTANT", 6, "split of -10r"),
        ("ZERO_PENALTY", 7, r"zeta\(zeta-7\) <= -6"),
        ("PROVED_CAP", 254, "separable maximum is not the proved cap"),
    ],
)
def test_tampered_constant_rejected(name: str, value: object, message: str) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match=message):
        c.theorem()


def test_e44_objective_cross_check_detects_a_wrong_form() -> None:
    def linear_only(core: list[int], sigma: tuple[int, ...], zeta: tuple[int, ...]) -> int:
        return 243 + sum(sigma) - sum(zeta)

    with (
        patch.object(c, "decomposition", linear_only),
        pytest.raises(AssertionError, match="e44 objective"),
    ):
        c.e44_identity_points()


def test_supplemental_balanced_relaxation() -> None:
    sigma, zeta = c.legal_ranges()
    balanced = c.balanced_maximum(sigma, zeta)
    assert (balanced["MAXIMUM"], balanced["ARGMAX_R"]) == (253, 11)
    assert (balanced["CORE_STATES"], balanced["ZERO_STATES"]) == (1008, 462)
    assert balanced["ARGMAX_ZETA"] == [1, 1, 1, 1, 1, 6]
    assert balanced["ROLE"] == "SUPPLEMENTAL_NOT_PROOF"


def test_complement_split_is_a_graph_identity_on_this_partition() -> None:
    rng = random.Random(20261014)
    core, zero = list(range(14)), list(range(14, 20))
    positive = 0
    for density in (0.2, 0.45, 0.7, 0.9):
        for _ in range(4):
            g = {e for e in combinations(range(20), 2) if rng.random() < density}
            seen = c.t256.complement_split(core, zero, g)
            sigma = [c.integer(v) for v in c.rows(seen["SIGMA"])]
            zeta = [c.integer(v) for v in c.rows(seen["ZETA"])]
            h = [c.integer(v) for v in c.rows(seen["H_CORE"])]
            a = [c.integer(v) for v in c.rows(seen["A_ZERO"])]
            p = c.integer(seen["P"])
            bare = (
                6 * c.integer(seen["M_EDGES"])
                + 14 * c.integer(seen["MZ_EDGES"])
                - sum(s * v for s, v in zip(sigma, h, strict=True))
                - sum(s * v for s, v in zip(zeta, a, strict=True))
            )
            assert seen["T_H"] == bare + p
            positive += p > 0
    assert positive > 0  # P is exact, not decorative: dropping it breaks the identity


def test_recorded_realization_obeys_the_chain(result: dict[str, object]) -> None:
    seen = c.object_row(result["RECORDED_ROW_REALIZATION"])
    assert seen["PROFILE_ID"] == c.TARGET_PROFILE
    t, p = c.integer(seen["TRIANGLES"]), c.integer(seen["P"])
    assert t <= 255 - p <= 255
    assert (t, seen["R"], seen["T_H"], p) == (194, 10, 103, 6)


def test_realization_of_another_profile_rejected() -> None:
    with pytest.raises(AssertionError, match="wrong profile"):
        c.realization_check(*c.three.witness())


def test_route_b_envelope_and_sufficient_cap() -> None:
    terms, bound = c.route_b(255)
    old, old_bound = c.route_b(264)
    assert len(terms) == 234 and [t[0] for t in terms] == list(range(22, 256))
    assert terms[-1] == (255, 313314492, 423, 200, 241017, 5062176)
    assert bound == 313314492 and max(terms, key=lambda t: t[1]) == terms[-1]
    assert old_bound == 313395344 and terms == old[:234]
    assert c.sufficient_cap(old, 313395164) == 263
    assert c.route_b(263)[1] == 313386188 <= 313395164 < old_bound
    assert old[-1] == (264, 313395344, 490, 200, 286510, 5169024)


@pytest.mark.parametrize("cap", [21, 265])
def test_cap_outside_the_source_domain_rejected(cap: int) -> None:
    with pytest.raises(AssertionError, match="invalid triangle cap"):
        c.route_b(cap)


def test_unreachable_threshold_rejected() -> None:
    with pytest.raises(AssertionError, match="no cap meets the threshold"):
        c.sufficient_cap(c.route_b(264)[0], 310_000_000)


def test_rounding_profile() -> None:
    terms = c.route_b(255)[0]
    rounding = c.rounding_profile(terms)
    assert rounding["K4_CEILING_ACTIVE_TERMS"] == 57  # t = 199..255
    assert rounding["S4_CREDIT_INTEGRAL_TERMS"] == 234
    assert rounding["BOUND_CEILING_SLACK_TERMS"] == 0
    bumped = [(t, b, k4, a, s4 + 1, s3) for t, b, k4, a, s4, s3 in terms]
    with pytest.raises(AssertionError, match="S4 credit is not integral"):
        c.rounding_profile(bumped)


@pytest.mark.parametrize(("field", "delta"), [(1, -1), (1, 1), (2, 1), (3, -1), (4, 7)])
def test_tampered_route_b_term_rejected(field: int, delta: int) -> None:
    real = c.r32.route_b_envelope

    def tampered(profile: tuple[int, ...], cap: int, base: int) -> list[c.Term]:
        terms = [list(t) for t in real(profile, cap, base)]
        terms[-1][field] += delta
        return [(t[0], t[1], t[2], t[3], t[4], t[5]) for t in terms]

    with patch.object(c.r32, "route_b_envelope", tampered):
        with pytest.raises(AssertionError, match="implementations differ"):
            c.route_b(255)
        with (
            patch.object(c.split, "route_b_terms", tampered),
            pytest.raises(AssertionError, match="exact arithmetic"),
        ):
            c.route_b(255)


def test_floor_rounded_k4_envelope_rejected() -> None:
    # S4 is a multiple of 7 here, so the K4 ceiling is the rounding that moves bounds.
    real = c.r32.route_b_envelope

    def floored(profile: tuple[int, ...], cap: int, base: int) -> list[c.Term]:
        g = [6 + d for d in profile]
        w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
        out: list[c.Term] = []
        for t, *_rest in real(profile, cap, base):
            excess = Fraction(j - (max(g) - 2) * (w - 3 * t), 4)
            k4 = max(0, excess.numerator // excess.denominator)
            contained = min(k4, 200)
            s4 = max(base, 448 * contained + 679 * (k4 - contained))
            s3 = 2800 * w + 11872 * (t - 22) - 30800
            out.append((t, c.S1_MINUS_S2 + s3 - (4 * s4) // 7, k4, contained, s4, s3))
        return out

    p = c.split.profile_values(c.TARGET_PROFILE)
    wrong, right = floored(p, 255, 112), real(p, 255, 112)
    assert wrong[-1] == (255, 313314880, 422, 200, 240338, 5062176) != right[-1]
    assert all(a[1] >= b[1] for a, b in zip(wrong, right, strict=True))
    with (
        patch.object(c.r32, "route_b_envelope", floored),
        patch.object(c.split, "route_b_terms", floored),
        pytest.raises(AssertionError, match="exact arithmetic"),
    ):
        c.route_b(255)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SOURCE_CAP", 265),
        ("SOURCE_S4_BASE", 1680),
        ("SOURCE_ROW_BOUND", 313395343),
        (
            "SOURCE_LABEL",
            "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1199]",
        ),
    ],
)
def test_wrong_source_premise_rejected(authority: Authority, name: str, value: object) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match="frozen target row"):
        c.source_row(authority[1])


def test_source_row_of_another_profile_rejected(authority: Authority) -> None:
    with (
        patch.object(c, "TARGET_PROFILE", "66655555555511100000"),
        pytest.raises(AssertionError, match="frozen target row"),
    ):
        c.source_row(authority[1])


def test_cap_authority_pins_the_refutation() -> None:
    source = c.cap_authority()
    assert (source["STATUS"], source["CAP"], source["ATTEMPT"]) == (
        "INFEASIBLE",
        264,
        "GROUP_ATTEMPTS[3414]",
    )
    with (
        patch.object(c, "CAP_ATTEMPT_INDEX", 3415),
        pytest.raises(AssertionError, match="cap source is not"),
    ):
        c.cap_authority()
    with (
        patch.object(c, "R30_RESULT_SHA256", "0" * 64),
        pytest.raises(AssertionError, match="blob digest mismatch"),
    ):
        c.cap_authority()


@pytest.mark.parametrize(
    ("name", "width", "message"),
    [("FROZEN_TREE", 40, "frozen tree mismatch"), ("FROZEN_RESULT_SHA256", 64, "blob digest")],
)
def test_wrong_frozen_pin_rejected(name: str, width: int, message: str) -> None:
    with patch.object(c, name, "0" * width), pytest.raises(AssertionError, match=message):
        c.frozen_authority()


def test_tampered_seven_row_replay_rejected(authority: Authority) -> None:
    ledger = dict(authority[1])
    other = "66655555555521000000"
    ledger[other] = replace(ledger[other], bound=ledger[other].bound - 1)
    with (
        patch.object(c.t256, "six_row_authority", return_value=({}, {})),
        patch.object(c.t256, "apply_seventh", return_value=ledger),
        pytest.raises(AssertionError, match="does not reproduce 6569a966"),
    ):
        c.frozen_authority()


def test_provenance_pins_every_reused_module() -> None:
    provenance = c.module_provenance()
    assert len(provenance) == 10
    assert "src/lottolab/research/b649_min_s2_next_owner_core_zero_t256_cert_r1.py" in provenance
