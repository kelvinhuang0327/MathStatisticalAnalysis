"""Focused guards for the core-zero T<=256 theorem and the seven-row family recount."""

from __future__ import annotations

import random
from dataclasses import replace
from itertools import combinations
from typing import cast
from unittest.mock import patch

import pytest

from lottolab.research import b649_min_s2_next_owner_core_zero_t256_cert_r1 as c

six = c.six


@pytest.fixture(scope="module")
def authority() -> tuple[dict[str, object], dict[str, c.Row]]:
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
    ):
        return c.six_row_authority()


@pytest.fixture(scope="module")
def result(authority: tuple[dict[str, object], dict[str, c.Row]]) -> dict[str, object]:
    # Reuse only the genuine, digest-validated replay in the fixture above.
    with patch.object(c, "six_row_authority", return_value=authority):
        return c.compute_result()


def test_committed_result_is_reproduced_exactly(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.two.render(result)


def test_theorem_premises_and_cap() -> None:
    theorem = c.t256_theorem()
    assert theorem["STATUS"] == "PROVEN"
    assert theorem["TRIANGLE_CAP"] == theorem["SEPARABLE_MAXIMUM"] == 256
    assert (theorem["G_EDGES"], theorem["H_EDGES"]) == (93, 97)
    assert theorem["PHI_INCLUSION_EXCLUSION"] == theorem["PHI_GOODMAN"] == 298
    assert theorem["CONSTANT"] == 256
    assert theorem["SIGMA_RANGES"] == {"6": [0], "5": [0, 1], "4": [0, 1, 2]}
    assert theorem["ZETA_RANGE"] == list(range(7))
    assert theorem["CHAIN_COEFFICIENTS_A_Q"] == [-2, 0]
    assert theorem["EQUALITY_CONDITIONS"] == {"P": 0, "A": 0, "Q": [0], "ZETA": [0], "R": 0}
    assert theorem["IDENTITY_POINTS_CHECKED"] == 1 + 2 * 20


@pytest.mark.parametrize(
    ("degree", "values", "message"),
    [
        (4, range(4), r"q\^2 <= 2q"),
        (5, range(3), r"2r \+ q\^2"),
        (6, range(2), r"2r \+ q\^2"),
    ],
)
def test_widened_core_range_breaks_the_chain(degree: int, values: range, message: str) -> None:
    sigma, zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match=message):
        c.certify_cap({**sigma, degree: values}, zeta)


def test_separable_route_is_checked_independently() -> None:
    # The packet chain ignores this constant; only the separable maximum can catch it.
    with (
        patch.object(c, "CORE_TERM_CONSTANT", 3),
        pytest.raises(AssertionError, match="separable maximum exceeds 256"),
    ):
        c.certify_cap(*c.legal_ranges())


def test_widened_zero_range_breaks_the_chain() -> None:
    sigma, _zeta = c.legal_ranges()
    with pytest.raises(AssertionError, match=r"zeta\^2 <= 6 zeta"):
        c.certify_cap(sigma, range(8))


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("PROPOSED_CAP", 255, "premises"),
        ("TICKET_CAPACITY", 7, "premises"),
        ("TARGET_PROFILE", "66655555555440000000", "premises"),
        ("CORE_TERM_CONSTANT", 3, "e44 objective"),
        ("ZERO_TERM_CONSTANT", 5, "e44 objective"),
    ],
)
def test_tampered_constant_rejected(name: str, value: object, message: str) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match=message):
        c.t256_theorem()


def test_complement_split_is_a_graph_identity() -> None:
    rng = random.Random(20261011)
    positive = 0
    for k in (13, 10, 16):
        core, zero = list(range(k)), list(range(k, 20))
        for density in (0.2, 0.5, 0.8):
            for _ in range(4):
                g = {e for e in combinations(range(20), 2) if rng.random() < density}
                seen = c.complement_split(core, zero, g)
                p = c.integer(seen["P"])
                bare = (
                    len(zero) * c.integer(seen["M_EDGES"])
                    + len(core) * c.integer(seen["MZ_EDGES"])
                    - sum(
                        c.integer(s) * c.integer(h)
                        for s, h in zip(c.rows(seen["SIGMA"]), c.rows(seen["H_CORE"]), strict=True)
                    )
                    - sum(
                        c.integer(s) * c.integer(a)
                        for s, a in zip(c.rows(seen["ZETA"]), c.rows(seen["A_ZERO"]), strict=True)
                    )
                )
                assert seen["T_H"] == bare + p
                assert min(c.integer(v) for v in c.rows(seen["P_TERMS"])) >= 0
                positive += p > 0
    assert positive > 0  # P is exact, not decorative: dropping it breaks the identity


def test_recorded_realization_obeys_the_chain(result: dict[str, object]) -> None:
    seen = c.object_row(result["RECORDED_ROW_REALIZATION"])
    assert seen["PROFILE_ID"] == c.TARGET_PROFILE
    t, a, p = (c.integer(seen[k]) for k in ("TRIANGLES", "A", "P"))
    assert t <= 256 - 2 * a - p <= 256
    assert (t, seen["R"], seen["T_H"]) == (190, 12, 108)


def test_realization_of_another_profile_rejected() -> None:
    with pytest.raises(AssertionError, match="wrong profile"):
        c.realization_check(*c.three.witness())


def test_supplemental_superset() -> None:
    superset = c.superset_check()
    assert superset["COUNT"] == 471
    assert superset["MAX_F"] == superset["E44_GRAPHICAL_MAX_F"] == 256
    assert superset["E44_GRAPHICAL_SUBSET_COUNT"] == 94
    assert superset["ARGMAX"] == [[[0] * 13, [0] * 7]]
    assert superset["ROLE"] == "SUPPLEMENTAL_NOT_PROOF"


def test_route_b_envelope() -> None:
    terms, bound = c.route_b(256)
    old, old_bound = c.route_b(264)
    assert len(terms) == 235 and [t[0] for t in terms] == list(range(22, 257))
    assert terms[-1] == (256, 313327224, 428, 200, 244412, 5076848)
    assert bound == 313327224 and max(terms, key=lambda t: t[1]) == terms[-1]
    assert old_bound == 313398920 and terms == old[:235]


def test_tampered_route_b_term_rejected() -> None:
    real = c.r32.route_b_envelope

    def bumped(profile: tuple[int, ...], cap: int, base: int) -> list[c.Term]:
        terms = list(real(profile, cap, base))
        t, bound, k4, contained, s4, s3 = terms[-1]
        terms[-1] = (t, bound - 1, k4, contained, s4, s3)
        return terms

    with patch.object(c.r32, "route_b_envelope", bumped):
        with pytest.raises(AssertionError, match="implementations differ"):
            c.route_b(256)
        with (
            patch.object(c.split, "route_b_terms", bumped),
            pytest.raises(AssertionError, match="exact arithmetic"),
        ):
            c.route_b(256)


def test_family_recount(result: dict[str, object]) -> None:
    assert result["EXPECTED_VALUES_MATCH"] is True
    assert result["EXPECTED_VALUE_DIFFERENCES"] == {}
    assert (result["FAMILY_BOUND_BEFORE"], result["FAMILY_BOUND_AFTER"]) == (313398920, 313398532)
    assert result["FAMILY_BOUND_DELTA"] == 388
    assert result["NEXT_OWNER_IDS"] == ["66655555555521000000"]
    assert result["GAP_TO_INCUMBENT"] == 134644
    assert result["NEXT_COMPETING_BOUND"] == 313398248
    assert len(c.rows(result["NEXT_COMPETING_OWNER_IDS"])) == 3
    assert result["ROWS_CHANGED_FROM_SIX_ROW"] == [c.TARGET_PROFILE]
    assert result["LEDGER_ROWS"] == 4647 and result["CERTIFICATES_COMPOSED"] == 7
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    update = c.object_row(result["ROW_UPDATE"])
    before, after = c.object_row(update["BEFORE"]), c.object_row(update["AFTER"])
    assert (after["bound"], after["cap"]) == (313327224, 256)
    assert {k: v for k, v in before.items() if k not in ("bound", "cap", "source")} == {
        k: v for k, v in after.items() if k not in ("bound", "cap", "source")
    }


def test_six_row_status_preserved_verbatim(
    authority: tuple[dict[str, object], dict[str, c.Row]], result: dict[str, object]
) -> None:
    six_result, _ledger = authority
    preserved = c.object_row(result["PRESERVED_SIX_ROW_STATUS"])
    assert preserved == {k: six_result[k] for k in c.PRESERVED_SIX_ROW_FIELDS}
    assert preserved["AUTHORITY_JUDGE_STATUS"] == "VERIFIED_WITH_CAVEATS"
    assert preserved["DONOR_JUDGE_STATUS"] == "SELF_CHECK_ONLY"
    assert preserved["CURSOR_STATUS"] == "UNRESOLVED_AUTHORITY_UNCHANGED"


def test_ledger_not_mutated_by_update(
    authority: tuple[dict[str, object], dict[str, c.Row]],
) -> None:
    six_result, ledger = authority
    after = c.apply_seventh(ledger, 313327224, 256, "probe")
    assert c.two.full_digest(ledger) == six_result["FULL_ROWS_SHA256_AFTER"]
    assert [p for p in ledger if ledger[p] != after[p]] == [c.TARGET_PROFILE]


@pytest.mark.parametrize(
    ("bound", "cap"),
    [(313398920, 256), (313327224, 264), (313327224, 21), (313327224.0, 256)],
)
def test_non_tightening_update_rejected(
    authority: tuple[dict[str, object], dict[str, c.Row]], bound: object, cap: int
) -> None:
    with pytest.raises(AssertionError, match=r"tighten|exact integers"):
        c.apply_seventh(authority[1], cast(int, bound), cap, "probe")


def test_double_application_rejected(
    authority: tuple[dict[str, object], dict[str, c.Row]],
) -> None:
    once = c.apply_seventh(authority[1], 313327224, 256, "probe")
    with pytest.raises(AssertionError, match="tighten"):
        c.apply_seventh(once, 313327224, 256, "probe")


def test_tampered_six_row_replay_rejected(
    authority: tuple[dict[str, object], dict[str, c.Row]],
) -> None:
    ledger = dict(authority[1])
    other = "66655555555521000000"
    ledger[other] = replace(ledger[other], bound=ledger[other].bound - 1)
    with (
        patch.object(six, "five_row_ledger", return_value={}),
        patch.object(six, "apply_sixth", return_value=ledger),
        pytest.raises(AssertionError, match="does not reproduce 83ddad7a"),
    ):
        c.six_row_authority()


@pytest.mark.parametrize(("name", "width"), [("BASE_TREE", 40), ("SIX_RESULT_SHA256", 64)])
def test_wrong_authority_pin_rejected(name: str, width: int) -> None:
    with (
        patch.object(c, name, "0" * width),
        pytest.raises(AssertionError, match=r"tree|digest"),
    ):
        c.six_row_authority()


def test_provenance_pins_every_reused_module() -> None:
    provenance = c.module_provenance()
    assert len(provenance) == 9
    assert f"src/lottolab/research/{six.__name__.rsplit('.', 1)[1]}.py" in provenance
