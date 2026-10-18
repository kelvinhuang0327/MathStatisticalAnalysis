"""Focused guards for the degree-square T<=248 theorem and the eight-row family recount."""

from __future__ import annotations

from dataclasses import replace
from typing import cast
from unittest.mock import patch

import pytest

from lottolab.research import b649_min_s2_post_t256_next_owner_cap248_cert_r1 as c

t256 = c.t256
Authority = tuple[dict[str, object], dict[str, c.Row]]


@pytest.fixture(scope="module")
def six_authority() -> Authority:
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
        patch.object(t256, "t256_theorem", forbidden),
        patch.object(t256, "compute_result", forbidden),
    ):
        return t256.six_row_authority()


@pytest.fixture(scope="module")
def authority(six_authority: Authority) -> Authority:
    # The genuine, digest-validated six-row replay above feeds the real seven-row rebuild.
    with patch.object(t256, "six_row_authority", return_value=six_authority):
        return c.seven_row_authority()


@pytest.fixture(scope="module")
def result(authority: Authority) -> dict[str, object]:
    with patch.object(c, "seven_row_authority", return_value=authority):
        return c.compute_result()


def test_committed_result_is_reproduced_exactly(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.two.render(result)


def test_theorem_premises_and_cap() -> None:
    theorem = c.cap_theorem()
    assert theorem["STATUS"] == "PROVEN"
    assert theorem["TRIANGLE_CAP"] == theorem["RELAXATION_MAXIMUM"] == 248
    assert (theorem["G_EDGES"], theorem["H_EDGES"]) == (93, 97)
    assert theorem["PHI_INCLUSION_EXCLUSION"] == theorem["PHI_GOODMAN"] == 298
    assert theorem["LEGAL_R"] == [6, 8, 10, 12, 14, 16, 18]
    assert theorem["ZETA_RANGE"] == [1, 2, 3, 4, 5, 6]
    assert theorem["MAX_BY_R"] == {
        "6": 245, "8": 247, "10": 248, "12": 242, "14": 238, "16": 236, "18": 236,
    }  # fmt: skip
    assert theorem["ARGMAX"] == [{"S1": 5, "S2": 4, "N5": 1, "R": 10}]
    assert theorem["SIGMA_VECTORS_CHECKED"] == 300
    assert theorem["CLOSED_FORM_IDENTITY"] == {"POINTS_CHECKED": 874, "STATUS": "PASS"}
    assert c.object_row(theorem["SUPPLEMENTAL_EXACT_Z_GRAPHS"])["MAXIMUM"] == 248
    assert c.object_row(theorem["ABLATION_RANGE_ONLY_ZETA"])["MAXIMUM"] == 258


def test_degree_square_lemma_is_exhaustive() -> None:
    exact, report = c.degree_square_lemma()
    lemma = c.lemma_bounds()
    assert report["GRAPHS_CHECKED"] == 2**15
    assert sorted(lemma) == list(range(7))
    # A star attains the lemma for e<=5; only e=6 (r=18) is slack.
    assert all(exact[e] == lemma[e] for e in range(6)) and exact[6] < lemma[6]


def test_widened_core_range_breaks_the_cap() -> None:
    sigma, _zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match="exceeds 248"):
        c.certify_cap({**sigma, 1: range(7)}, c.lemma_bounds())


def test_dropping_the_lemma_breaks_the_cap() -> None:
    sigma, _zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match="exceeds 248"):
        c.certify_cap(sigma, c.range_only_bounds())


def test_identity_check_catches_a_wrong_shift_without_premises() -> None:
    with (
        patch.object(c, "CORE_SHIFT", 3),
        pytest.raises(AssertionError, match="closed form differs"),
    ):
        c.identity_check()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("REDUCED_CONSTANT", 245),
        ("GOODMAN_CONSTANT", 297),
        ("CORE_SHIFT", 3),
        ("TICKET_CAPACITY", 7),
        ("TARGET_PROFILE", "66555555555531000000"),
    ],
)
def test_tampered_constant_rejected(name: str, value: object) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match="premises"):
        c.cap_theorem()


def test_recorded_realization_obeys_the_chain(result: dict[str, object]) -> None:
    seen = c.object_row(result["RECORDED_ROW_REALIZATION"])
    assert seen["PROFILE_ID"] == c.TARGET_PROFILE
    t, p, bound = (c.integer(seen[k]) for k in ("TRIANGLES", "P", "CHAIN_BOUND_WITHOUT_P"))
    assert t <= bound - p and bound <= 248
    assert (t, seen["R"], seen["T_H"]) == (191, 14, 107)


def test_realization_of_another_profile_rejected() -> None:
    with pytest.raises(AssertionError, match="wrong profile"):
        c.realization_check(*c.three.witness())


def test_route_b_envelope_and_required_improvement() -> None:
    terms, bound = c.route_b(248)
    old, old_bound = c.route_b(264)
    assert len(terms) == 227 and [t[0] for t in terms] == list(range(22, 249))
    assert terms[-1] == (248, 313255140, 369, 200, 204351, 4981872)
    assert bound == 313255140 and max(terms, key=lambda t: t[1]) == terms[-1]
    assert old_bound == 313398532 and terms == old[:227]
    needed = c.required_improvement(old)
    assert needed["BOUND_AT_CAP_263"] == 313389376
    assert needed["MIN_S4_FLOOR_AT_CAP_264"] == 285833


def test_tampered_route_b_term_rejected() -> None:
    real = c.r32.route_b_envelope

    def bumped(profile: tuple[int, ...], cap: int, base: int) -> list[c.Term]:
        terms = list(real(profile, cap, base))
        t, bound, k4, contained, s4, s3 = terms[-1]
        terms[-1] = (t, bound - 1, k4, contained, s4, s3)
        return terms

    with patch.object(c.r32, "route_b_envelope", bumped):
        with pytest.raises(AssertionError, match="implementations differ"):
            c.route_b(248)
        with (
            patch.object(c.split, "route_b_terms", bumped),
            pytest.raises(AssertionError, match="exact arithmetic"),
        ):
            c.route_b(248)


def test_family_recount(result: dict[str, object]) -> None:
    assert result["EXPECTED_VALUES_MATCH"] is True
    assert result["EXPECTED_VALUE_DIFFERENCES"] == {}
    assert (result["FAMILY_BOUND_BEFORE"], result["FAMILY_BOUND_AFTER"]) == (313398532, 313398248)
    assert result["FAMILY_BOUND_DELTA"] == 284
    assert result["NEXT_OWNER_IDS"] == [
        "66555555555531000000",
        "66655555554441000000",
        "66655555555422000000",
    ]
    assert result["GAP_TO_INCUMBENT"] == 134360
    assert result["PROFILE_BOUND_BELOW_INCUMBENT"] is True
    assert result["ROWS_CHANGED_FROM_SEVEN_ROW"] == [c.TARGET_PROFILE]
    assert result["LEDGER_ROWS"] == 4647 and result["CERTIFICATES_COMPOSED"] == 8
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    update = c.object_row(result["ROW_UPDATE"])
    before, after = c.object_row(update["BEFORE"]), c.object_row(update["AFTER"])
    assert (after["bound"], after["cap"]) == (313255140, 248)
    assert {k: v for k, v in before.items() if k not in ("bound", "cap", "source")} == {
        k: v for k, v in after.items() if k not in ("bound", "cap", "source")
    }


def test_inherited_status_preserved_verbatim(
    authority: Authority, result: dict[str, object]
) -> None:
    seven_result, _ledger = authority
    preserved = c.object_row(result["PRESERVED_T256_STATUS"])
    assert preserved == {k: seven_result[k] for k in preserved}
    six_status = c.object_row(preserved["PRESERVED_SIX_ROW_STATUS"])
    assert six_status["AUTHORITY_JUDGE_STATUS"] == "VERIFIED_WITH_CAVEATS"
    assert six_status["CURSOR_STATUS"] == "UNRESOLVED_AUTHORITY_UNCHANGED"
    assert result["T256_JUDGE_RECORD"] == c.T256_JUDGE_RECORD


def test_ledger_not_mutated_by_update(authority: Authority) -> None:
    seven_result, ledger = authority
    after = c.apply_eighth(ledger, 313255140, 248, "probe")
    assert c.two.full_digest(ledger) == seven_result["FULL_ROWS_SHA256_AFTER"]
    assert [p for p in ledger if ledger[p] != after[p]] == [c.TARGET_PROFILE]


@pytest.mark.parametrize(
    ("bound", "cap"),
    [(313398532, 248), (313255140, 264), (313255140, 21), (313255140.0, 248)],
)
def test_non_tightening_update_rejected(authority: Authority, bound: object, cap: int) -> None:
    with pytest.raises(AssertionError, match=r"tighten|exact integers"):
        c.apply_eighth(authority[1], cast(int, bound), cap, "probe")


def test_double_application_rejected(authority: Authority) -> None:
    once = c.apply_eighth(authority[1], 313255140, 248, "probe")
    with pytest.raises(AssertionError, match="tighten"):
        c.apply_eighth(once, 313255140, 248, "probe")


def test_tampered_seven_row_replay_rejected(six_authority: Authority) -> None:
    real = t256.apply_seventh

    def drifted(*args: object, **kwargs: object) -> dict[str, c.Row]:
        ledger = real(*args, **kwargs)  # type: ignore[arg-type]
        other = "66655555555422000000"
        ledger[other] = replace(ledger[other], bound=ledger[other].bound - 1)
        return ledger

    with (
        patch.object(t256, "six_row_authority", return_value=six_authority),
        patch.object(t256, "apply_seventh", drifted),
        pytest.raises(AssertionError, match="does not reproduce 6569a966"),
    ):
        c.seven_row_authority()


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("BASE_TREE", "0" * 40, "tree mismatch"),
        ("T256_RESULT_SHA256", "0" * 64, "digest mismatch"),
        ("T256_JUDGE_RECORD", "Fresh-context Judge: VERIFIED", "Judge record missing"),
    ],
)
def test_wrong_authority_pin_rejected(name: str, value: str, message: str) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match=message):
        c.seven_row_authority()


def test_provenance_pins_every_reused_module() -> None:
    provenance = c.module_provenance()
    assert len(provenance) == 10
    assert f"src/lottolab/research/{t256.__name__.rsplit('.', 1)[1]}.py" in provenance
