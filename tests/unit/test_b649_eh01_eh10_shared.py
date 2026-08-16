from __future__ import annotations

import pytest

from lottolab.research import b649_eh01_eh10_shared as shared


def test_canonical_draw_id_has_no_sign_or_leading_zeroes() -> None:
    assert shared.canonical_draw_id(115000075) == "115000075"
    assert shared.canonical_draw_id(0) == "0"


def test_canonical_draw_id_rejects_negative_and_non_int() -> None:
    with pytest.raises(ValueError):
        shared.canonical_draw_id(-1)
    with pytest.raises(TypeError):
        shared.canonical_draw_id("5")  # type: ignore[arg-type]


def test_era4_assignment_is_four_contiguous_nondecreasing_blocks() -> None:
    eras = shared.era4_assignment(2138)
    assert eras[0] == 1
    assert eras[-1] == 4
    assert list(eras) == sorted(eras)  # nondecreasing, contiguous
    assert set(eras) == {1, 2, 3, 4}


def test_era4_assignment_blocks_differ_by_at_most_one_draw() -> None:
    eras = shared.era4_assignment(2138)
    sizes = [eras.count(e) for e in (1, 2, 3, 4)]
    assert max(sizes) - min(sizes) <= 1
    assert sum(sizes) == 2138


def test_era4_bounds_matches_era4_assignment() -> None:
    n = 2138
    eras = shared.era4_assignment(n)
    bounds = shared.era4_bounds(n)
    for era_number, (first, last) in enumerate(bounds, start=1):
        positions = [t for t, e in enumerate(eras, start=1) if e == era_number]
        assert (first, last) == (positions[0], positions[-1])


def test_perm_key_is_deterministic_and_policy_replicate_draw_sensitive() -> None:
    a = shared.perm_key("GLOBAL", 0, 100)
    b = shared.perm_key("GLOBAL", 0, 100)
    assert a == b  # deterministic
    assert a != shared.perm_key("GLOBAL", 1, 100)  # replicate-sensitive
    assert a != shared.perm_key("ERA4", 0, 100)  # policy-sensitive
    assert a != shared.perm_key("GLOBAL", 0, 101)  # draw_id-sensitive


def test_perm_key_rejects_unknown_policy_or_out_of_range_replicate() -> None:
    with pytest.raises(ValueError):
        shared.perm_key("NOT_A_POLICY", 0, 1)
    with pytest.raises(ValueError):
        shared.perm_key("GLOBAL", 999, 1)
    with pytest.raises(ValueError):
        shared.perm_key("GLOBAL", -1, 1)


def test_global_surrogate_order_is_a_true_permutation() -> None:
    draw_ids = tuple(range(1000, 1050))
    order = shared.global_surrogate_order(draw_ids, replicate=3)
    assert sorted(order) == list(range(len(draw_ids)))


def test_global_surrogate_order_differs_by_replicate_with_high_probability() -> None:
    draw_ids = tuple(range(1000, 1080))
    orders = {shared.global_surrogate_order(draw_ids, replicate=b) for b in range(20)}
    assert len(orders) == 20  # no accidental collisions among 20 replicates


def test_era4_surrogate_order_is_a_true_permutation_and_keeps_era_membership() -> None:
    n = 400
    draw_ids = tuple(range(1, n + 1))
    order = shared.era4_surrogate_order(draw_ids, replicate=5)
    assert sorted(order) == list(range(n))

    eras = shared.era4_assignment(n)
    for position_0_indexed, source_0_indexed in enumerate(order):
        # ERA4 only ever moves a value within its own era -- never across
        # an era boundary -- so the era membership must be preserved even
        # though position-within-era may change.
        assert eras[position_0_indexed] == eras[source_0_indexed]


def test_apply_order_reindexes_values_by_the_returned_permutation() -> None:
    values = (10, 20, 30, 40)
    order = (2, 0, 3, 1)
    assert shared.apply_order(values, order) == (30, 10, 40, 20)


def test_assert_distinct_permutations_passes_for_distinct_and_fails_for_duplicate() -> None:
    shared.assert_distinct_permutations(((0, 1), (1, 0)), policy="GLOBAL")
    with pytest.raises(ValueError):
        shared.assert_distinct_permutations(((0, 1), (0, 1)), policy="GLOBAL")


def test_raw_p_value_matches_locked_formula_and_bounds() -> None:
    surrogates = tuple([0.0] * 998 + [100.0])
    # exactly one surrogate (the 100.0) is >= a mid-range observed value
    assert shared.raw_p_value(50.0, surrogates) == (1 + 1) / 1000
    # every surrogate >= a very negative observed value
    all_exceed = tuple([1.0] * 999)
    assert shared.raw_p_value(-1.0, all_exceed) == (999 + 1) / 1000 == 1.0
    # no surrogate exceeds a very large observed value
    none_exceed = tuple([1.0] * 999)
    assert shared.raw_p_value(1000.0, none_exceed) == (0 + 1) / 1000


def test_raw_p_value_requires_exactly_999_surrogates() -> None:
    with pytest.raises(ValueError):
        shared.raw_p_value(1.0, (1.0, 2.0))


def test_holm_adjust_matches_hand_worked_example() -> None:
    # K=3, raw p-values 0.01, 0.02, 0.20 (already ascending, at original
    # positions 0, 1, 2). Step-down thresholds are (K-r+1): 3, 2, 1.
    # p_holm,(1) = 3*0.01 = 0.03
    # p_holm,(2) = max(0.03, 2*0.02) = max(0.03, 0.04) = 0.04
    # p_holm,(3) = max(0.04, 1*0.20) = 0.20
    result = shared.holm_adjust((0.01, 0.02, 0.20))
    assert result.holm_adjusted_p_values == pytest.approx((0.03, 0.04, 0.20))


def test_holm_adjust_enforces_monotonicity_via_running_max() -> None:
    # raw p-values out of order: the smallest raw p-value is at the end.
    # K=3 thresholds 3,2,1: sorted ascending order is (0.5 at idx2, 0.5 at idx0? )
    # Use a case where naive per-rank multiplication would be
    # non-monotonic without the running max.
    result = shared.holm_adjust((0.5, 0.001, 0.4))
    # sorted ascending: 0.001(idx1) -> *3=0.003; 0.4(idx2) -> *2=0.8; 0.5(idx0) -> *1=0.5
    # running max forces the last to stay >= 0.8 even though 1*0.5 < 0.8
    adjusted = result.holm_adjusted_p_values
    assert adjusted[1] == pytest.approx(0.003)
    assert adjusted[2] == pytest.approx(0.8)
    assert adjusted[0] == pytest.approx(0.8)  # rescued upward by the running max


def test_holm_adjust_clamps_at_one() -> None:
    result = shared.holm_adjust((0.9, 0.9, 0.9))
    assert all(p == 1.0 for p in result.holm_adjusted_p_values)


def test_holm_adjust_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        shared.holm_adjust(())


def test_permutation_ledger_digest_is_deterministic_and_order_sensitive() -> None:
    orders_a = ((0, 1, 2), (2, 1, 0))
    orders_b = ((2, 1, 0), (0, 1, 2))
    digest_a1 = shared.permutation_ledger_digest(orders_a, policy="GLOBAL")
    digest_a2 = shared.permutation_ledger_digest(orders_a, policy="GLOBAL")
    digest_b = shared.permutation_ledger_digest(orders_b, policy="GLOBAL")
    assert digest_a1 == digest_a2
    assert digest_a1 != digest_b  # replicate order matters
    assert len(digest_a1) == 64
