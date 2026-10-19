"""Focused guards for the sealed T<=256 (A) and T<=258 (B) certificate, with mutation checks."""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable, Sequence
from itertools import combinations, product
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from lottolab.research import b649_next_two_t256_t258_certificate_seal_r1 as c

A, B = c.PROFILE_A, c.PROFILE_B
Key = tuple[tuple[c.Subset, ...], c.Subset, tuple[int, ...], int]


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return c.compute_result()


@pytest.fixture(scope="module")
def main_keys() -> list[Key]:
    states = [s for s in c.zero_side_states(B) if s.phi > c.CLAIMED_CAPS[B]]
    return sorted(
        {c.canonical_b_key(s.sets(1), s.sets(4)[0], s.residual, sum(s.zeta)) for s in states}
    )


def test_module_is_loaded_from_this_worktree() -> None:
    here = Path(__file__).resolve().parents[2]
    assert here == c.ROOT
    assert Path(c.__file__).resolve().is_relative_to(here / "src")


def test_sealed_result_is_reproduced_exactly(result: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.render(result)


def test_caps_expected_values_and_no_family_authority(result: dict[str, object]) -> None:
    assert result["EXPECTED_VALUES_MATCH"] is True
    assert result["EXPECTED_VALUE_DIFFERENCES"] == {}
    assert result["CAPS"] == {
        A: {"CLAIMED": 256, "CERTIFIED_T_MAX": 253, "ROW_BOUND": 313_311_276, "STATUS": "PROVEN"},
        B: {"CLAIMED": 258, "CERTIFIED_T_MAX": 239, "ROW_BOUND": 313_328_812, "STATUS": "PROVEN"},
    }
    projection = cast(dict[str, object], result["FAMILY_PROJECTION"])
    assert projection["PROJECTED_FAMILY_BOUND"] == 313_391_636
    assert projection["PROJECTED_FAMILY_GAIN"] == 104
    assert projection["PROJECTED_OWNERS"] == [c.NEXT_OWNER]
    assert projection["FORMAL_FAMILY_AUTHORITY"] == result["FORMAL_FAMILY_AUTHORITY"]
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_CLAIMED"


def test_every_negative_control_is_rejected_by_a_real_check(result: dict[str, object]) -> None:
    negatives = cast(dict[str, str], result["NEGATIVE_CONTROLS"])
    assert len(negatives) == 17
    assert all(v.startswith("REJECTED: ") for v in negatives.values())
    assert "261 above the claimed cap 258" in negatives["B_WITHOUT_K6_LEMMA"]
    assert "253 does not support T<=252" in negatives["UNSUPPORTED_CAP_A_252"]
    assert "239 does not support T<=238" in negatives["UNSUPPORTED_CAP_B_238"]


def test_premises_and_identity_for_both_profiles() -> None:
    for profile, (k, z) in ((A, (15, 5)), (B, (16, 4))):
        facts = c.premises(profile)
        assert (facts["CORE_VERTICES"], facts["ZERO_VERTICES"]) == (k, z)
        assert (facts["G_EDGES"], facts["H_EDGES"], facts["SUM_D_SQUARED"]) == (93, 97, 328)
        assert facts["T_G_PLUS_T_H_INCLUSION_EXCLUSION"] == facts["T_G_PLUS_T_H_GOODMAN"] == 293
        assert (facts["IDENTITY_CONSTANT"], facts["LINEAR_R_COEFFICIENT"]) == (233, -4)
        assert c.identity_check(profile)["STATUS"] == "EXACT_ON_SUM_SIGMA_EQUALS_SUM_ZETA"
    assert c.premises(A)["SIGMA_CAPS"] == {"6": 0, "5": 1, "3": 3, "1": 5}
    assert c.premises(B)["SIGMA_CAPS"] == {"6": 0, "5": 1, "4": 2, "1": 4}


def test_identity_constant_mutation_is_rejected() -> None:
    triples, pairs = c.first_realization(A, 1)
    assert c.realization_check(A, triples, pairs)["T"] <= 256
    with patch.object(c, "IDENTITY_CONSTANT", 234):
        with pytest.raises(AssertionError, match="premises fail"):
            c.premises(A)
        with pytest.raises(AssertionError, match="identity fails"):
            c.realization_check(A, triples, pairs)


def test_complement_total_mutation_is_rejected() -> None:
    triples, pairs = c.first_realization(B, 2)
    with patch.object(c, "COMPLEMENT_TOTAL", 294):
        with pytest.raises(AssertionError, match="premises fail"):
            c.premises(B)
        with pytest.raises(AssertionError, match="complement split fails"):
            c.realization_check(B, triples, pairs)


def test_sigma_shift_mutation_is_rejected() -> None:
    with patch.object(c, "SIGMA_SHIFT", 3):
        with pytest.raises(AssertionError, match="premises fail"):
            c.premises(A)
        with pytest.raises(AssertionError, match="identity fails"):
            c.identity_check(B)


def test_zero_side_p_terms_are_load_bearing_for_a() -> None:
    original = c.zero_graph

    def without_z_terms(z: int, edges: Iterable[c.Pair], *, z_terms: bool = True) -> c.ZeroGraph:
        return original(z, edges, z_terms=False)

    assert max(s.phi for s in c.zero_side_states(A)) == 253
    with patch.object(c, "zero_graph", without_z_terms):
        top = max(s.phi for s in c.zero_side_states(A))
    assert top == 265
    with pytest.raises(AssertionError, match="does not support T<=256"):
        c.cap_supported(top, 256)


def test_crossing_balance_is_load_bearing() -> None:
    assert (c.separable_maximum(A), c.separable_maximum(B)) == (413, 377)


def test_k6_lemma_mutation_is_rejected() -> None:
    rows = c.b_main_certificate()
    assert len(rows) == 399 and c.worst_bound(rows) == 239
    with (
        patch.object(c, "K6_SLOTS", 0),
        pytest.raises(AssertionError, match="leaves 261 above the claimed cap 258"),
    ):
        c.b_main_certificate()


def test_optimised_k_side_bound_equals_the_reference(main_keys: list[Key]) -> None:
    assert len(main_keys) == 138
    for key in main_keys:
        assert c.k_side_lower_bound(*key) == c.k_side_lower_bound_reference(*key), key
    for key in main_keys[::10]:
        assert c.k_side_lower_bound(*key, k6_slots=0) == c.k_side_lower_bound_reference(
            *key, k6_slots=0
        )


def pruning_is_exact(prune: Callable[[Iterable[c.Option]], list[c.Option]]) -> bool:
    """Min of a block-monotone objective under a d6-slot floor, with and without pruning."""
    rng = random.Random(7)

    def value(choice: Sequence[c.Option]) -> int:
        local = [v for o in choice for v in o[2]]
        best = max(0, *(sum(s) - 3 * len(s) for n in (1, 2) for s in combinations(local, n)))
        return sum(o[1] for o in choice) + best

    def least(blocks: Sequence[Sequence[c.Option]]) -> int | None:
        values = [value(ch) for ch in product(*blocks) if sum(o[0] for o in ch) >= 3]
        return min(values) if values else None

    for _ in range(400):
        sizes = [rng.randint(1, 2) for _ in range(rng.randint(1, 3))]
        blocks = [
            [
                (rng.randint(0, 2), rng.randint(0, 6), tuple(rng.randint(0, 9) for _ in range(n)))
                for _ in range(rng.randint(1, 6))
            ]
            for n in sizes
        ]
        if least(blocks) != least([prune(b) for b in blocks]):
            return False
    return True


def test_pareto_pruning_is_exact_and_a_lossy_prune_is_caught() -> None:
    assert pruning_is_exact(c.pareto)
    assert not pruning_is_exact(lambda options: sorted(set(options))[:1])


def test_inflated_k_side_bound_is_caught_by_legal_realizations() -> None:
    sample = c.realization_sample(B, 3, 4, high_l_sigma=True, min_phi=258)
    assert sample["STATUS"] == "ALL_R5_LEGAL_AND_IDENTITY_EXACT"
    original = c.k_side_lower_bound

    def inflated(
        l_sets: Sequence[c.Subset],
        c_set: c.Subset,
        residual: Sequence[int],
        r: int,
        *,
        k6_slots: int | None = None,
    ) -> int:
        lb = original(l_sets, c_set, residual, r, k6_slots=k6_slots)
        assert lb is not None
        return lb + 60

    with (
        patch.object(c, "k_side_lower_bound", inflated),
        pytest.raises(AssertionError, match="K-side bound exceeds P_K"),
    ):
        c.realization_sample(B, 3, 4, high_l_sigma=True, min_phi=258)


def test_route_b_envelopes() -> None:
    a, b = c.route_b_summary(A, 256), c.route_b_summary(B, 258)
    assert (a["TERM_COUNT"], a["U"], a["BOUND"]) == (235, 2318, 313_311_276)
    assert (b["TERM_COUNT"], b["U"], b["BOUND"]) == (237, 2320, 313_328_812)
    assert a["ARGMAX_TERM"] == [256, 313_311_276, 432, 197, 247_821, 5_062_848]
    assert b["ARGMAX_TERM"] == [258, 313_328_812, 448, 197, 258_685, 5_086_592]
    assert a["OLD_BOUND"] == b["OLD_BOUND"] == 313_391_740
    assert (a["W"], a["A_MAX"], a["G_MAX"]) == (b["W"], b["A_MAX"], b["G_MAX"]) == (827, 197, 12)


def test_route_b_native_and_rational_mutations_are_rejected() -> None:
    with (
        patch.dict(c.r32.K4_WEIGHTS, {c.r32.WITH_TRIPLE: 449}),
        pytest.raises(AssertionError, match="Route-B terms differ"),
    ):
        c.route_b_terms(A, 256)
    with patch.object(c, "S4_BASE", 113), pytest.raises(AssertionError, match="Route-B terms"):
        c.route_b_terms(B, 258)


def test_provenance_and_base_pins_fail_closed() -> None:
    original = c.git

    def tampered(*args: str) -> bytes:
        if args[0] == "show" and args[1].endswith("_r5.py"):
            return b"# tampered\n"
        return original(*args)

    with (
        patch.object(c, "git", tampered),
        pytest.raises(AssertionError, match="reused source changed"),
    ):
        c.module_provenance()
    with (
        patch.object(c, "BASE_RESULT_SHA256", "0" * 64),
        pytest.raises(AssertionError, match="base result digest changed"),
    ):
        c.base_authority()


def test_generic_k_side_lemmas_on_random_graphs() -> None:
    assert c.generic_lemma_check(seed=23, trials=200)["STATUS"] == "PASS"
