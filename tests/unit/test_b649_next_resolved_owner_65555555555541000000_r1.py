"""Focused guards for the core-zero T<=238 cap of 65555555555541000000."""

from __future__ import annotations

import random
from dataclasses import replace
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import comb
from unittest.mock import patch

import pytest

from lottolab.research import b649_next_resolved_owner_65555555555541000000_r1 as c

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
    assert (row.bound, row.cap, row.s4_base, row.realization) == (313392516, 265, 112, None)
    assert row.source == c.SOURCE_LABEL


def test_next_competitor_level(authority: Authority) -> None:
    level = c.next_competitor(authority[1])
    assert (level["BOUND"], level["GAP_FROM_SOURCE_ROW"]) == (313392412, 104)
    assert level["OWNERS"] == ["66655555555431000000", "66665555544441000000"]
    owners = c.object_row(level["OWNER_ROWS"])
    assert all(
        (c.object_row(owners[p])["CAP"], c.object_row(owners[p])["S4_BASE"]) == (264, 112)
        for p in owners
    )
    assert level["FROZEN_ENTRIES_ABOVE_SOURCE_ROW"] == 19  # 18 rows and the cursor
    assert level["CURSOR_ABOVE_SOURCE_ROW"] is True
    assert level["SOURCE_ROW_IS_FROZEN_FAMILY_MAX"] is False


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("NEXT_COMPETITOR_BOUND", 313392413),
        ("NEXT_COMPETITOR_OWNERS", ["66655555555431000000"]),
        ("SOURCE_ROW_BOUND", 313392412),
    ],
)
def test_wrong_next_competitor_rejected(authority: Authority, name: str, value: object) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match="next competing"):
        c.next_competitor(authority[1])


def test_result_scope_fields(result: dict[str, object]) -> None:
    assert (result["PROVED_T_CAP"], result["SUFFICIENT_CAP_FOR_NEXT_COMPETITOR"]) == (238, 264)
    assert (result["NEW_ADMISSIBLE_BOUND"], result["OWNER_BOUND_DELTA"]) == (313150736, 241780)
    assert result["BELOW_NEXT_COMPETITOR"] is True
    assert result["ROW_BELOW_INCUMBENT"] is True
    assert result["PROOF_SCOPE"] == "FULL_PROFILE"
    assert (result["SOURCE_T_CAP"], result["SOURCE_S4_BASE"]) == (265, 112)
    assert c.text(result["SOURCE_PROOF_LOCATOR"]).endswith(":GROUP_ATTEMPTS[3397]")
    assert (result["FAMILY_GAIN_CLAIMED"], result["LEDGER_ROWS_CHANGED"]) == (0, 0)
    assert result["NEW_WINNING_OUTCOMES"] == 0
    counterfactual = c.object_row(result["FROZEN_FAMILY_COUNTERFACTUAL"])
    assert (counterfactual["FAMILY_IF_INSTALLED"], counterfactual["FAMILY_DELTA"]) == (313398532, 0)
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["HEAVY_SOLVER_STARTED"] == "NO" and result["SOLVER_CALLS"] == 0


def test_counterfactual_must_tighten(authority: Authority) -> None:
    with pytest.raises(AssertionError, match="update must tighten"):
        c.frozen_family_if_installed(authority[1], 313392516)


def test_theorem_premises_and_cap() -> None:
    theorem = c.theorem()
    assert theorem["STATUS"] == "PROVEN" and theorem["PROOF_SCOPE"] == "FULL_PROFILE"
    assert (theorem["TRIANGLE_CAP"], theorem["SEPARABLE_MAXIMUM"]) == (238, 240)
    assert (theorem["CORE_MAXIMUM"], theorem["ZERO_MAXIMUM"]) == (37, -36)
    assert (theorem["G_EDGES"], theorem["H_EDGES"], theorem["W"], theorem["J"]) == (
        93,
        97,
        827,
        2310,
    )
    assert theorem["PHI_INCLUSION_EXCLUSION"] == theorem["PHI_GOODMAN"] == 293
    assert (theorem["IDENTITY_CONSTANT"], theorem["ZETA_FLOOR"]) == (239, 1)
    assert (theorem["DEGREE_SUM"], theorem["DEGREE_SQUARE_SUM"]) == (66, 328)
    assert (theorem["CORE_VERTICES"], theorem["ZERO_VERTICES"]) == (14, 6)
    assert theorem["A_MAX_EXACT"] == "592/3"
    assert theorem["SIGMA_RANGES"] == {
        "6": [0],
        "5": [0, 1],
        "4": [0, 1, 2],
        "1": [0, 1, 2, 3, 4, 5],
    }
    assert theorem["ZETA_RANGE"] == [1, 2, 3, 4, 5, 6]
    assert theorem["CORE_CLASS_MAXIMA"] == {"6": 0, "5": 0, "4": 2, "1": 35}
    assert theorem["ZERO_DEFICIT_TABLE"] == {"1": 0, "2": 4, "3": 6, "4": 6, "5": 4, "6": 0}
    assert theorem["MIN_POSITIVE_ZERO_DEFICIT"] == 4
    assert theorem["E44_IDENTITY_POINTS_CHECKED"] == 1 + 2 * 20


def test_deficit_gap_excludes_239_and_240() -> None:
    assert c.theorem()["DEFICIT_GAP"] == {
        "LEVELS_EXCLUDED": [239, 240],
        "CORE_NEAR_TOP_R": {"0": [7], "1": [8]},
        "ZERO_NEAR_TOP_R": {"0": [6, 11, 16, 21, 26, 31, 36]},
        "BALANCED_CLASHES": 0,
    }


def test_balanced_relaxation_is_exact_with_a_unique_argmax() -> None:
    sigma, zeta = c.legal_ranges()
    balanced = c.balanced_maximum(sigma, zeta)
    assert (balanced["MAXIMUM"], balanced["ARGMAX_R"]) == (238, [6])
    assert (balanced["CORE_STATES"], balanced["ZERO_STATES"]) == (216, 462)
    assert balanced["ARGMAX_STATES"] == [[[0] * 12 + [1, 5], [1] * 6]]
    by_r = c.object_row(balanced["MAXIMUM_BY_R"])
    assert sorted(by_r) == sorted(str(r) for r in range(6, 19))
    assert max(c.integer(v) for r, v in by_r.items() if r != "6") == 236


def test_independent_recount_of_the_relaxation() -> None:
    # Direct per-class loops (d=6 has sigma 0); no module helper is used.
    best = -1
    top: list[tuple[int, int, int, tuple[int, ...]]] = []
    zero_by_sum: dict[int, list[tuple[int, ...]]] = {}
    for zeta in combinations_with_replacement(range(1, 7), 6):
        zero_by_sum.setdefault(sum(zeta), []).append(zeta)
    for ones, s4, s1 in product(range(12), range(3), range(6)):
        core = -ones + s4 * (s4 - 1) + s1 * (s1 + 2)
        for zeta in zero_by_sum.get(ones + s4 + s1, []):
            value = 239 + core + sum(v * (v - 7) for v in zeta)
            if value > best:
                best, top = value, []
            if value == best:
                top.append((ones, s4, s1, zeta))
    assert (best, top) == (238, [(0, 1, 5, (1, 1, 1, 1, 1, 1))])


def test_zero_floor_is_the_load_bearing_inequality() -> None:
    sigma, _zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match=r"zeta\(zeta-7\) <= -6"):
        c.certify_cap(sigma, range(7))
    ablation = c.ablation(264)
    assert (ablation["SEPARABLE_MAXIMUM"], ablation["BALANCED_MAXIMUM"]) == (276, 268)
    assert c.ablation(267)["LOAD_BEARING"] is True
    with pytest.raises(AssertionError, match="not load-bearing"):
        c.ablation(268)


@pytest.mark.parametrize(
    ("degree", "values", "message"),
    [
        (5, range(3), "deficit gap"),
        (4, range(4), "separable maximum"),
        (1, range(7), "separable maximum"),
    ],
)
def test_widened_core_range_breaks_the_cap(degree: int, values: range, message: str) -> None:
    sigma, zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match=message):
        c.certify_cap({**sigma, degree: values}, zeta)


def test_widened_d6_range_is_not_load_bearing() -> None:
    sigma, zeta = c.legal_ranges()
    widened = c.certify_cap({**sigma, 6: range(2)}, zeta)
    assert widened["SEPARABLE_MAXIMUM"] == 240
    assert c.object_row(widened["DEFICIT_GAP"])["BALANCED_CLASHES"] == 0


def test_widened_zero_range_above_capacity_breaks_the_chain() -> None:
    sigma, _zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match=r"zeta\(zeta-7\) <= -6"):
        c.certify_cap(sigma, range(1, 8))


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("GOODMAN_CONSTANT", 294, "premises"),
        ("IDENTITY_CONSTANT", 240, "premises"),
        ("ZETA_FLOOR", 0, "premises"),
        ("TICKET_CAPACITY", 7, "premises"),
        ("TARGET_PROFILE", "66665555554431000000", "premises"),
        ("CORE_TERM_CONSTANT", 4, "split of -10r"),
        ("ZERO_TERM_CONSTANT", 6, "split of -10r"),
        ("ZERO_PENALTY", 7, r"zeta\(zeta-7\) <= -6"),
        ("SEPARABLE_CAP", 241, "analytic chain cap"),
        ("PROVED_CAP", 237, "deficit gap"),
        ("PROVED_CAP", 239, "balanced maximum is not the proved cap"),
    ],
)
def test_tampered_constant_rejected(name: str, value: object, message: str) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match=message):
        c.theorem()


def test_e44_objective_cross_check_detects_a_wrong_form() -> None:
    def linear_only(core: list[int], sigma: tuple[int, ...], zeta: tuple[int, ...]) -> int:
        return 239 + sum(sigma) - sum(zeta)

    with (
        patch.object(c, "decomposition", linear_only),
        pytest.raises(AssertionError, match="e44 objective"),
    ):
        c.e44_identity_points()


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


def test_closed_form_on_degree_preserving_swaps_of_the_witness() -> None:
    # Any graph with degrees 6+d on this K/Z split obeys T = D - P (support premises aside).
    triples, pairs = c.witness()
    g = {c.t256.edge(x, y) for s in (*triples, *pairs) for x, y in combinations(s, 2)}
    degrees = c.split.profile_values(c.TARGET_PROFILE)
    witness_degrees = c.three.legal_degrees(triples, pairs)
    core = [v for v in range(20) if witness_degrees[v]]
    zero = [v for v in range(20) if not witness_degrees[v]]
    dc = [witness_degrees[v] for v in core]
    assert sorted(dc, reverse=True) == [d for d in degrees if d]
    rng = random.Random(238)
    checked = beyond = 0
    for _ in range(400):
        (a, b), (x, y) = rng.sample(sorted(g), 2)
        if len({a, b, x, y}) == 4 and not {c.t256.edge(a, y), c.t256.edge(x, b)} & g:
            g = (g - {(a, b), (x, y)}) | {c.t256.edge(a, y), c.t256.edge(x, b)}
        seen = c.t256.complement_split(core, zero, g)
        sigma = [c.integer(v) for v in c.rows(seen["SIGMA"])]
        zeta = [c.integer(v) for v in c.rows(seen["ZETA"])]
        t, p = c.integer(seen["T_G"]), c.integer(seen["P"])
        assert t == 293 - c.integer(seen["T_H"]) == c.decomposition(dc, sigma, zeta) - p
        checked += 1
        beyond += any(s > 6 - d for d, s in zip(dc, sigma, strict=True))
    assert checked == 400 and beyond > 0


def test_legal_witness_obeys_the_chain(result: dict[str, object]) -> None:
    seen = c.object_row(result["LEGAL_WITNESS_REALIZATION"])
    assert seen["PROFILE_ID"] == c.TARGET_PROFILE
    t, p = c.integer(seen["TRIANGLES"]), c.integer(seen["P"])
    assert t <= 238 - p <= 238
    assert (t, seen["R"], seen["D"], seen["T_H"], p) == (165, 18, 193, 128, 28)
    assert seen["P_TERMS"] == [12, 0, 11, 5]
    assert seen["ZETA"] == [3] * 6


def test_realization_of_another_profile_rejected() -> None:
    with pytest.raises(AssertionError, match="wrong profile"):
        c.realization_check(*c.three.witness())


def test_non_linear_support_rejected() -> None:
    triples, pairs = c.witness()
    broken = ((1, 4), *pairs[1:])  # (1,4) is already a shadow pair of (0,1,4)
    with pytest.raises(AssertionError, match="share more than one label"):
        c.realization_check(triples, broken)


def test_route_b_envelope_and_sufficient_cap() -> None:
    terms, bound = c.route_b(238)
    old, old_bound = c.route_b(265)
    assert len(terms) == 217 and [t[0] for t in terms] == list(range(22, 239))
    assert terms[-1] == (238, 313150736, 295, 197, 154798, 4849152)
    assert bound == 313150736 and max(terms, key=lambda t: t[1]) == terms[-1]
    assert old_bound == 313392516 and terms == old[:217]
    assert old[-1] == (265, 313392516, 498, 197, 292635, 5169696)
    assert c.sufficient_cap(old, 313392412) == 264
    assert c.route_b(264)[1] == 313383748 <= 313392412 < old_bound
    assert c.sufficient_cap(old, 313383748) == 264
    assert c.sufficient_cap(old, 313383747) == 263


@pytest.mark.parametrize("cap", [21, 266])
def test_cap_outside_the_source_domain_rejected(cap: int) -> None:
    with pytest.raises(AssertionError, match="invalid triangle cap"):
        c.route_b(cap)


def test_unreachable_threshold_rejected() -> None:
    with pytest.raises(AssertionError, match="no cap meets the threshold"):
        c.sufficient_cap(c.route_b(265)[0], 310_000_000)


def test_rounding_profile() -> None:
    terms = c.route_b(238)[0]
    rounding = c.rounding_profile(terms)
    assert rounding["K4_CEILING_ACTIVE_TERMS"] == 20  # odd t = 199..237
    assert rounding["A_MAX_FLOOR_BINDING_TERMS"] == 14  # t = 225..238
    assert rounding["A_MAX_RULE"] == "FLOOR(592/3)=197"
    assert rounding["S4_CREDIT_INTEGRAL_TERMS"] == 217
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
            c.route_b(238)
        with (
            patch.object(c.split, "route_b_terms", tampered),
            pytest.raises(AssertionError, match="exact arithmetic"),
        ):
            c.route_b(238)


def envelope(
    profile: tuple[int, ...], cap: int, base: int, *, floor_k4: bool, a_max: int
) -> list[c.Term]:
    """Route B with one rounding switched: K4 floor instead of ceiling, or a wrong A_MAX."""
    g = [6 + d for d in profile]
    w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    out: list[c.Term] = []
    for t in range(22, cap + 1):
        excess = Fraction(j - (max(g) - 2) * (w - 3 * t), 4)
        rounded = excess.numerator // excess.denominator
        k4 = max(0, rounded if floor_k4 else -((-excess.numerator) // excess.denominator))
        contained = min(k4, a_max)
        s4 = max(base, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        out.append((t, c.S1_MINUS_S2 + s3 - (4 * s4) // 7, k4, contained, s4, s3))
    return out


def test_envelope_helper_matches_the_frozen_rule() -> None:
    p = c.split.profile_values(c.TARGET_PROFILE)
    assert envelope(p, 238, 112, floor_k4=False, a_max=197) == c.r32.route_b_envelope(p, 238, 112)


@pytest.mark.parametrize(
    ("floor_k4", "a_max", "index", "wrong"),
    [
        (True, 197, -2, (237, 313141968, 287, 197, 149366, 4837280)),
        (False, 198, -1, (238, 313150868, 295, 198, 154567, 4849152)),
    ],
)
def test_mis_rounded_envelope_rejected(
    floor_k4: bool, a_max: int, index: int, wrong: c.Term
) -> None:
    p = c.split.profile_values(c.TARGET_PROFILE)
    right = c.r32.route_b_envelope(p, 238, 112)
    bad = envelope(p, 238, 112, floor_k4=floor_k4, a_max=a_max)
    assert bad[index] == wrong != right[index]

    def fake(profile: tuple[int, ...], cap: int, base: int) -> list[c.Term]:
        return envelope(profile, cap, base, floor_k4=floor_k4, a_max=a_max)

    with (
        patch.object(c.r32, "route_b_envelope", fake),
        patch.object(c.split, "route_b_terms", fake),
        pytest.raises(AssertionError, match="exact arithmetic"),
    ):
        c.route_b(238)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SOURCE_CAP", 264),
        ("SOURCE_S4_BASE", 1680),
        ("SOURCE_ROW_BOUND", 313392515),
        (
            "SOURCE_LABEL",
            "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1615]",
        ),
    ],
)
def test_wrong_source_premise_rejected(authority: Authority, name: str, value: object) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match="frozen target row"):
        c.source_row(authority[1])


def test_source_row_of_another_profile_rejected(authority: Authority) -> None:
    with (
        patch.object(c, "TARGET_PROFILE", "66655555555431000000"),
        pytest.raises(AssertionError, match="frozen target row"),
    ):
        c.source_row(authority[1])


@pytest.mark.parametrize("index", [3398, 2284])
def test_cap_authority_pins_the_refutation(index: int) -> None:
    source = c.cap_authority()
    assert (source["STATUS"], source["CAP"], source["ATTEMPT"]) == (
        "INFEASIBLE",
        265,
        "GROUP_ATTEMPTS[3397]",
    )
    # 2284 refutes this profile one level higher (T=267); 3398 is another attempt.
    with (
        patch.object(c, "CAP_ATTEMPT_INDEX", index),
        pytest.raises(AssertionError, match="cap source is not"),
    ):
        c.cap_authority()


def test_cap_authority_digest_pinned() -> None:
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
