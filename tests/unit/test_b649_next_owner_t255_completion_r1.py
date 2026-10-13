"""Focused guards for the T<=255 core-zero cap of 65555555555550000000 and its Route-B row."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from math import floor
from pathlib import Path
from unittest.mock import patch

import pytest

from lottolab.research import b649_next_owner_t255_completion_r1 as c

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
        patch.object(c.three, "witness", forbidden),
        patch.object(c.three, "compute_result", forbidden),
        patch.object(c.t256, "t256_theorem", forbidden),
        patch.object(c.t256, "compute_result", forbidden),
    ):
        return c.t256.six_row_authority()


@pytest.fixture(scope="module")
def result(authority: Authority) -> dict[str, object]:
    # Reuse only the genuine, digest-validated replay in the fixture above.
    with patch.object(c.t256, "six_row_authority", return_value=authority):
        return c.compute_result()


def test_committed_result_is_reproduced_exactly(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.two.render(result)


def test_headline_values(result: dict[str, object]) -> None:
    assert result["EXPECTED_VALUES_MATCH"] is True
    assert result["EXPECTED_VALUE_DIFFERENCES"] == {}
    assert result["TASK_STATUS"] == "COMPLETE_PROVED_SELF_CHECK_ONLY"
    assert (result["FROZEN_HEAD_TREE"], result["FROZEN_RESULT_SHA256_STATUS"]) == ("MATCH",) * 2
    assert result["T255_PROOF_SCOPE"] == "FULL_PROFILE"
    assert (result["OLD_BOUND"], result["NEW_CAP"], result["NEW_BOUND"]) == (
        313396120,
        255,
        313315656,
    )
    assert result["OWNER_BOUND_DELTA"] == result["STRICT_OWNER_BOUND_DELTA"] == 80464
    assert result["THRESHOLDS"] == [263, 263, 249]
    source = c.object_row(result["SOURCE_ROW"])
    assert (source["SOURCE_T_CAP"], source["SOURCE_S4_BASE"]) == (264, 1680)
    assert source["SOURCE_ROW_BOUND"] == 313396120
    for key, value in {
        "HEAVY_SOLVER_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "NEW_WINNING_OUTCOMES": 0,
        "FAMILY_BOUND_GAIN_CLAIMED": 0,
        "LEDGER_ROW_INSTALLED": "NO",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }.items():
        assert result[key] == value


def test_frozen_ledger_context(result: dict[str, object]) -> None:
    context = c.object_row(result["FROZEN_LEDGER_CONTEXT"])
    assert context["FROZEN_FAMILY_BOUND"] == 313398532
    assert context["FROZEN_FAMILY_OWNER_IDS"] == ["66655555555521000000"]
    assert context["TARGET_IN_CERTIFICATE_PROFILE_IDS"] is False
    above = [c.rows(r) for r in c.rows(context["ROWS_ABOVE_TARGET"])]
    assert len(above) == context["ROWS_ABOVE_TARGET_COUNT"]
    assert all(c.integer(r[0]) > c.SOURCE_BOUND for r in above)


def test_theorem_premises_and_cap() -> None:
    theorem = c.theorem()
    assert theorem["STATUS"] == "PROVEN"
    assert theorem["TRIANGLE_CAP"] == theorem["SEPARABLE_MAXIMUM"] == theorem["CONSTANT"] == 255
    assert (theorem["G_EDGES"], theorem["H_EDGES"], theorem["WEDGES"]) == (93, 97, 831)
    assert theorem["PHI_INCLUSION_EXCLUSION"] == theorem["PHI_GOODMAN"] == 297
    assert theorem["SIGMA_RANGES"] == {"6": [0], "5": [0, 1]}
    assert theorem["ZETA_RANGE"] == list(range(7))
    assert (theorem["R_COEFFICIENT"], theorem["CHAIN_COEFFICIENT_R"]) == (-8, -2)
    assert theorem["EQUALITY_CONDITIONS"] == {"P": 0, "R": 0, "ZETA": [0], "SIGMA": [0]}
    assert theorem["IDENTITY_POINTS_CHECKED"] == 1 + 2 * 20


@pytest.mark.parametrize(
    ("degree", "values"),
    [(6, range(2)), (5, range(3))],
)
def test_sigma_above_support_limit_breaks_the_chain(degree: int, values: range) -> None:
    sigma, zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match=r"sum sigma\*h = 2r"):
        c.certify_cap({**sigma, degree: values}, zeta)


def test_zeta_above_support_limit_breaks_the_chain() -> None:
    sigma, _zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match=r"zeta\^2 <= 6 zeta"):
        c.certify_cap(sigma, range(8))


def test_negative_range_rejected() -> None:
    sigma, zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match="unexpected range shape"):
        c.certify_cap({**sigma, 5: range(-1, 2)}, zeta)


def test_separable_route_is_checked_independently() -> None:
    # The cap chain ignores this constant; only the separable maximum can catch it.
    with (
        patch.object(c, "CORE_TERM_CONSTANT", 5),
        pytest.raises(AssertionError, match="separable maximum exceeds 255"),
    ):
        c.certify_cap(*c.legal_ranges())


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("PROVED_CAP", 254, "premises"),
        ("PROVED_CAP", 256, "premises"),
        ("GOODMAN_CONSTANT", 298, "premises"),
        ("TICKET_CAPACITY", 7, "premises"),
        ("TARGET_PROFILE", "66555555555540000000", "premises"),
        ("CORE_TERM_CONSTANT", 3, "e44 objective"),
        ("ZERO_TERM_CONSTANT", 5, "e44 objective"),
    ],
)
def test_tampered_constant_or_cap_rejected(name: str, value: object, message: str) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match=message):
        c.theorem()


def test_witness_attains_the_cap() -> None:
    seen = c.realization_check(*c.witness())
    assert (seen["TRIANGLES"], seen["R"], seen["P"], seen["T_H"]) == (255, 0, 0, 42)
    assert (seen["M_EDGES"], seen["MZ_EDGES"], seen["SLACK_TO_CAP"]) == (6, 0, 0)


def test_tampered_witness_packing_rejected() -> None:
    triples = list(c.CORE_TRIPLES)
    triples[0] = (1, 4, 9)
    with (
        patch.object(c, "CORE_TRIPLES", tuple(triples)),
        pytest.raises(AssertionError, match="witness packing changed"),
    ):
        c.witness()


def test_zero_ticket_in_a_triple_rejected() -> None:
    triples, pairs = c.witness()
    moved = [(1, 4, 13) if t == (1, 4, 8) else t for t in triples]
    with pytest.raises(AssertionError, match="six labels"):
        c.realization_check(moved, pairs)


def test_two_shared_labels_rejected() -> None:
    triples, pairs = c.witness()
    doubled = [(13, 14) if q == (13, 15) else q for q in pairs]
    with pytest.raises(AssertionError, match="share more than one label"):
        c.realization_check(triples, doubled)


def test_realization_of_another_profile_rejected() -> None:
    with pytest.raises(AssertionError, match="wrong profile"):
        c.realization_check(*c.three.witness())


def test_recorded_realization_obeys_the_chain(result: dict[str, object]) -> None:
    seen = c.object_row(result["RECORDED_ROW_REALIZATION"])
    assert seen["PROFILE_ID"] == c.TARGET_PROFILE
    t, r, p = (c.integer(seen[k]) for k in ("TRIANGLES", "R", "P"))
    assert t <= 255 - 2 * r - p <= 255
    assert (t, r, p, seen["T_H"], seen["SUM_ZETA_SQUARED"]) == (193, 10, 2, 104, 20)


def test_switch_family_exercises_the_remainder(result: dict[str, object]) -> None:
    family = c.object_row(result["SUPPLEMENTAL_SWITCH_FAMILY"])
    seen = [c.rows(x) for name in ("SPREAD", "STAR") for x in c.rows(family[name])]
    assert len(seen) == 12
    for r, t, z2, p in ([c.integer(v) for v in x] for x in seen):
        assert t == 255 - 8 * r + z2 - p <= 255 - 2 * r - p
    assert any(c.integer(x[3]) > 0 for x in seen)


def test_supplemental_superset() -> None:
    superset = c.superset_check()
    assert superset["COUNT"] == 201
    assert superset["MAX_F"] == superset["E44_GRAPHICAL_MAX_F"] == 255
    assert superset["E44_GRAPHICAL_SUBSET_COUNT"] == 49
    assert superset["ARGMAX"] == [[[0] * 13, [0] * 7]]
    assert superset["ROLE"] == "SUPPLEMENTAL_NOT_PROOF"


def test_route_b_envelope() -> None:
    terms, meta = c.route_b(255)
    old, old_meta = c.route_b(264)
    assert len(terms) == meta["TERM_COUNT"] == 234
    assert [t[0] for t in terms] == list(range(22, 256))
    assert terms[-1] == (255, 313315656, 420, 200, 238980, 5062176)
    assert meta["ARGMAX_TERM"] == list(terms[-1])
    assert meta["ALL_T_MAX_BOUND"] == 313315656 and meta["ROUNDING_RESIDUES"] == ["0"]
    assert old_meta["ALL_T_MAX_BOUND"] == 313396120 and terms == old[:234]


def test_route_b_formula_by_hand() -> None:
    # S1-S2 = 308390040; S3 = 2800*831 + 11872*(T-22) - 30800; K4 = ceil((30T-5970)/4).
    for t, bound, k4, contained, s4, s3 in c.independent_terms(255, 1680):
        assert s3 == 2800 * 831 + 11872 * (t - 22) - 30800
        assert k4 == max(0, -((5970 - 30 * t) // 4)) and contained == min(k4, 200)
        assert s4 == max(1680, 448 * contained + 679 * (k4 - contained))
        assert 7 * bound == 7 * (308390040 + s3) - 4 * s4


def test_thresholds() -> None:
    old, _meta = c.route_b(264)
    assert c.threshold(old, c.SOURCE_BOUND, strict=True)["CAP"] == 263
    assert c.threshold(old, c.CURSOR_BOUND, strict=False)["CAP"] == 263
    incumbent = c.threshold(old, c.INCUMBENT, strict=False)
    assert (incumbent["CAP"], incumbent["BOUND_AT_CAP"]) == (249, 313261884)
    assert incumbent["BOUND_AT_CAP_PLUS_1"] == 313270652


def test_cap_beyond_wedge_identity_rejected() -> None:
    with pytest.raises(AssertionError, match="wedge identity"):
        c.independent_terms(278, 1680)


def test_tampered_route_b_term_rejected() -> None:
    real = c.r32.route_b_envelope

    def bumped(profile: tuple[int, ...], cap: int, base: int) -> list[c.Term]:
        terms = list(real(profile, cap, base))
        t, bound, k4, contained, s4, s3 = terms[-1]
        terms[-1] = (t, bound - 1, k4, contained, s4, s3)
        return terms

    def bumped_mine(cap: int, base: int) -> list[c.Term]:
        return bumped(c.split.profile_values(c.TARGET_PROFILE), cap, base)

    with patch.object(c.r32, "route_b_envelope", bumped):
        with pytest.raises(AssertionError, match="implementations differ"):
            c.route_b(255)
        with patch.object(c.split, "route_b_terms", bumped):
            with pytest.raises(AssertionError, match="independent Route-B recount differs"):
                c.route_b(255)
            with (
                patch.object(c, "independent_terms", bumped_mine),
                pytest.raises(AssertionError, match="exact arithmetic"),
            ):
                c.route_b(255)


def floor_fraction(value: Fraction) -> int:
    return floor(value)


def test_wrong_k4_rounding_rejected() -> None:
    # (30*254-5970)/4 = 412.5: a floored K4 lowers S4 by 679 and raises the T=254 bound.
    with (
        patch.object(c, "ceil_fraction", floor_fraction),
        pytest.raises(AssertionError, match="independent Route-B recount differs"),
    ):
        c.route_b(255)


def test_wrong_s4_credit_rounding_rejected() -> None:
    # Base 1681 is not a multiple of 7, so floor(4*S4/7) and ceil(exact) now matter.
    terms, meta = c.route_b(255, 1681)
    residues = [Fraction(v) for v in c.rows(meta["ROUNDING_RESIDUES"])]
    assert all(0 <= v < 1 for v in residues) and Fraction(4, 7) in residues
    # floor(4*1681/7) = 960 = 4*1680/7, so the T=22 bound keeps its base-1680 value.
    assert terms[0][:2] == (22, 310685080) and terms[0][4] == 1681
    with (
        patch.object(c, "ceil_fraction", floor_fraction),
        pytest.raises(AssertionError, match="independent Route-B recount differs"),
    ):
        c.route_b(255, 1681)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SOURCE_ROW", c.SOURCE_ROW.replace("[1613]", "[1612]")),
        ("SOURCE_CAP", 255),
        ("SOURCE_BOUND", 313315656),
        ("SOURCE_S4_BASE", 1681),
    ],
)
def test_wrong_source_row_rejected(authority: Authority, name: str, value: object) -> None:
    with (
        patch.object(c.t256, "six_row_authority", return_value=authority),
        patch.object(c, name, value),
        pytest.raises(AssertionError, match="target row differs"),
    ):
        c.frozen_row(c.frozen_authority())


def test_tampered_ledger_replay_rejected(authority: Authority) -> None:
    six_result, ledger = authority
    tampered = dict(ledger)
    tampered[c.TARGET_PROFILE] = replace(tampered[c.TARGET_PROFILE], cap=255)
    with (
        patch.object(c.t256, "six_row_authority", return_value=(six_result, tampered)),
        pytest.raises(AssertionError, match="not reproduced"),
    ):
        c.frozen_row(c.frozen_authority())


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("FROZEN_TREE", "0" * 40, "frozen tree mismatch"),
        ("FROZEN_HEAD", "83ddad7ade4ae286d12890efdbf3ea7768103d5e", "frozen tree mismatch"),
        ("FROZEN_RESULT_SHA256", "0" * 64, "blob digest mismatch"),
    ],
)
def test_wrong_authority_pin_rejected(name: str, value: str, message: str) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match=message):
        c.frozen_authority()


def test_changed_working_seven_row_result_rejected(tmp_path: Path) -> None:
    # The pinned blob still resolves through git; only the working bytes differ.
    copy = tmp_path / c.SEVEN_RESULT_PATH
    copy.parent.mkdir(parents=True)
    copy.write_bytes((c.ROOT / c.SEVEN_RESULT_PATH).read_bytes() + b" ")
    with (
        patch.object(c, "ROOT", tmp_path),
        pytest.raises(AssertionError, match="seven-row result changed"),
    ):
        c.frozen_authority()


def test_provenance_pins_every_reused_module() -> None:
    provenance = c.module_provenance()
    assert len(provenance) == 10
    assert f"src/lottolab/research/{c.t256.__name__.rsplit('.', 1)[1]}.py" in provenance


def test_main_refuses_a_different_existing_result(tmp_path: Path) -> None:
    target = tmp_path / "result.json"
    target.write_bytes(b"{}\n")
    probe: dict[str, object] = {
        "PROVED_T_CAP": 255,
        "NEW_ADMISSIBLE_BOUND": 0,
        "STRICT_OWNER_BOUND_DELTA": 0,
        "THRESHOLDS": [],
        "EXPECTED_VALUES_MATCH": False,
    }
    with (
        patch.object(c.resource, "setrlimit"),
        patch.object(c, "compute_result", return_value=probe),
        patch.object(c, "RESULT_PATH", target),
        pytest.raises(AssertionError, match="existing exact result differs"),
    ):
        c.main()
    assert target.read_bytes() == b"{}\n"
