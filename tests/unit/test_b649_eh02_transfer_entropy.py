from __future__ import annotations

import math

import pytest

from lottolab.research import b649_eh02_transfer_entropy as te

# ---------------------------------------------------------------------------
# Synthetic fixture (Authority A Sec. 13.3): the same required check the
# runner performs before any real data is read.
# ---------------------------------------------------------------------------


def _fixture_pairs() -> tuple[tuple[int, ...], tuple[int, ...]]:
    pairs = [(a, b) for a in range(3) for b in range(3)]
    return tuple(a for a, _ in pairs), tuple(b for _, b in pairs)


def test_synthetic_fixture_full_dependency_gives_exact_ln3() -> None:
    x_prev, y_prior = _fixture_pairs()
    x_next = y_prior  # perfect copy of the source: TE = MI = ln(3) exactly
    assert te.discrete_transfer_entropy(x_next, x_prev, y_prior) == pytest.approx(math.log(3))
    assert te.lagged_mutual_information(x_next, y_prior) == pytest.approx(math.log(3))


def test_synthetic_fixture_null_case_gives_exact_zero() -> None:
    x_prev, y_prior = _fixture_pairs()
    x_next = x_prev  # own-history copy, y irrelevant: TE = MI = 0 exactly
    assert te.discrete_transfer_entropy(x_next, x_prev, y_prior) == pytest.approx(0.0, abs=1e-12)
    assert te.lagged_mutual_information(x_next, y_prior) == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# Discrete plug-in transfer entropy / MI: general properties
# ---------------------------------------------------------------------------


def test_transfer_entropy_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        te.discrete_transfer_entropy((0, 1), (0,), (0, 1))


def test_transfer_entropy_rejects_empty_sample() -> None:
    with pytest.raises(te.Eh02DesignError):
        te.discrete_transfer_entropy((), (), ())


def test_mutual_information_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        te.lagged_mutual_information((0, 1, 2), (0, 1))


def test_transfer_entropy_is_nonnegative_on_a_larger_random_like_but_deterministic_sample() -> None:
    # A fixed pseudo-random-looking but fully deterministic sequence (no
    # random/time dependence allowed in this codebase) -- transfer entropy
    # is a KL divergence and must be >= 0 for any empirical distribution.
    n = 300
    x_prev = tuple((i * 7) % 3 for i in range(n))
    y_prior = tuple((i * 5 + 2) % 3 for i in range(n))
    x_next = tuple((x_prev[i] + y_prior[i]) % 3 for i in range(n))
    assert te.discrete_transfer_entropy(x_next, x_prev, y_prior) >= -1e-12


# ---------------------------------------------------------------------------
# Tie-break and causal tertile discretization
# ---------------------------------------------------------------------------


def test_tie_key_is_deterministic_and_context_lottery_draw_sensitive() -> None:
    a = te.tie_key(te.TARGET_SELF_CONTEXT, "BIG_LOTTO", 100)
    assert a == te.tie_key(te.TARGET_SELF_CONTEXT, "BIG_LOTTO", 100)
    assert a != te.tie_key(te.SOURCE_CONTEXT, "BIG_LOTTO", 100)
    assert a != te.tie_key(te.TARGET_SELF_CONTEXT, "DAILY_539", 100)
    assert a != te.tie_key(te.TARGET_SELF_CONTEXT, "BIG_LOTTO", 101)


def test_tie_key_rejects_unknown_context_or_bad_draw_id() -> None:
    with pytest.raises(ValueError):
        te.tie_key("NOT_A_CONTEXT", "BIG_LOTTO", 1)
    with pytest.raises(ValueError):
        te.tie_key(te.SOURCE_CONTEXT, "BIG_LOTTO", -1)


def test_causal_tertile_bins_early_positions_use_middle_bin_fallback() -> None:
    values = tuple(range(10))
    draw_ids = tuple(range(1000, 1010))
    bins = te.causal_tertile_bins(
        values, draw_ids, edge_context=te.TARGET_SELF_CONTEXT, lottery="BIG_LOTTO"
    )
    assert bins[0] == 1
    assert bins[1] == 1


def test_causal_tertile_bins_never_uses_current_or_future_values() -> None:
    # A value that would be an extreme outlier LATER must not affect an
    # EARLIER position's bin -- only strictly-prior values may.
    values = (10, 11, 12, 13, 14, 10_000)  # last value is a huge future outlier
    draw_ids = tuple(range(2000, 2006))
    bins_with_outlier = te.causal_tertile_bins(
        values, draw_ids, edge_context=te.SOURCE_CONTEXT, lottery="DAILY_539"
    )
    bins_without_outlier = te.causal_tertile_bins(
        values[:-1], draw_ids[:-1], edge_context=te.SOURCE_CONTEXT, lottery="DAILY_539"
    )
    assert bins_with_outlier[:-1] == bins_without_outlier


def test_causal_tertile_bins_strictly_increasing_series_trends_to_top_bin() -> None:
    values = tuple(range(60))
    draw_ids = tuple(range(3000, 3060))
    bins = te.causal_tertile_bins(
        values, draw_ids, edge_context=te.TARGET_SELF_CONTEXT, lottery="BIG_LOTTO"
    )
    assert bins[-1] == te.BIN_COUNT - 1
    assert bins[-10:] == tuple([te.BIN_COUNT - 1] * 10)


def test_causal_tertile_bins_supports_alternate_bin_count() -> None:
    values = tuple(range(40))
    draw_ids = tuple(range(4000, 4040))
    bins = te.causal_tertile_bins(
        values,
        draw_ids,
        edge_context=te.SOURCE_CONTEXT,
        lottery="POWER_LOTTO_ZONE1",
        bin_count=te.ALTERNATE_BIN_COUNT,
    )
    assert all(b in (0, 1) for b in bins)
    assert bins[-1] == 1


def test_causal_tertile_bins_ties_are_broken_deterministically_not_left_ambiguous() -> None:
    # All-equal history: every prior value ties: the tie_key ordering must
    # still deterministically produce a rank, never raise or vary by call.
    values = tuple([50] * 20)
    draw_ids = tuple(range(5000, 5020))
    bins_a = te.causal_tertile_bins(
        values, draw_ids, edge_context=te.TARGET_SELF_CONTEXT, lottery="BIG_LOTTO"
    )
    bins_b = te.causal_tertile_bins(
        values, draw_ids, edge_context=te.TARGET_SELF_CONTEXT, lottery="BIG_LOTTO"
    )
    assert bins_a == bins_b


# ---------------------------------------------------------------------------
# EDGE_ID-and-hypothesis-salted permutation generator
# ---------------------------------------------------------------------------


def test_perm_key_is_deterministic_and_fully_salt_sensitive() -> None:
    a = te.perm_key(te.EDGE_T539_TO_B649, "GLOBAL", 0, 5)
    assert a == te.perm_key(te.EDGE_T539_TO_B649, "GLOBAL", 0, 5)
    assert a != te.perm_key(te.EDGE_P638Z1_TO_B649, "GLOBAL", 0, 5)  # edge-sensitive
    assert a != te.perm_key(te.EDGE_T539_TO_B649, "ERA4", 0, 5)  # policy-sensitive
    assert a != te.perm_key(te.EDGE_T539_TO_B649, "GLOBAL", 1, 5)  # replicate-sensitive
    assert a != te.perm_key(te.EDGE_T539_TO_B649, "GLOBAL", 0, 6)  # index-sensitive


def test_perm_key_never_collides_with_eh01_eh10_shared_perm_key() -> None:
    # EH02's perm_key salts with the literal "EH02" tag and an EDGE_ID; the
    # shared EH01/EH10 module's perm_key never includes either, so for any
    # comparable (policy, replicate, integer) triple the two must differ.
    from lottolab.research import b649_eh01_eh10_shared as shared

    eh02_key = te.perm_key(te.EDGE_T539_TO_B649, "GLOBAL", 0, 100)
    eh01_key = shared.perm_key("GLOBAL", 0, 100)
    assert eh02_key != eh01_key


def test_perm_key_rejects_unknown_edge_policy_or_out_of_range_inputs() -> None:
    with pytest.raises(ValueError):
        te.perm_key("NOT_AN_EDGE", "GLOBAL", 0, 1)
    with pytest.raises(ValueError):
        te.perm_key(te.EDGE_T539_TO_B649, "NOT_A_POLICY", 0, 1)
    with pytest.raises(ValueError):
        te.perm_key(te.EDGE_T539_TO_B649, "GLOBAL", 999, 1)
    with pytest.raises(ValueError):
        te.perm_key(te.EDGE_T539_TO_B649, "GLOBAL", 0, 0)


def test_global_surrogate_order_is_a_true_permutation() -> None:
    order = te.global_surrogate_order(te.EDGE_T539_TO_B649, replicate=3, n=50)
    assert sorted(order) == list(range(50))


def test_global_surrogate_order_differs_by_edge_id_same_replicate() -> None:
    order_1 = te.global_surrogate_order(te.EDGE_T539_TO_B649, replicate=0, n=60)
    order_2 = te.global_surrogate_order(te.EDGE_P638Z1_TO_B649, replicate=0, n=60)
    assert order_1 != order_2


def test_global_surrogate_order_differs_by_replicate_with_high_probability() -> None:
    orders = {te.global_surrogate_order(te.EDGE_T539_TO_B649, b, n=80) for b in range(20)}
    assert len(orders) == 20


def test_era4_surrogate_order_is_a_true_permutation_and_keeps_era_membership() -> None:
    from lottolab.research.b649_eh01_eh10_shared import era4_assignment

    n = 400
    order = te.era4_surrogate_order(te.EDGE_P638Z1_TO_B649, replicate=5, n=n)
    assert sorted(order) == list(range(n))

    eras = era4_assignment(n)
    for position_0idx, source_0idx in enumerate(order):
        assert eras[position_0idx] == eras[source_0idx]


def test_era4_surrogate_order_differs_by_edge_id() -> None:
    order_1 = te.era4_surrogate_order(te.EDGE_T539_TO_B649, replicate=0, n=400)
    order_2 = te.era4_surrogate_order(te.EDGE_B649_TO_T539_REVERSE, replicate=0, n=400)
    assert order_1 != order_2


def test_apply_order_reindexes_values() -> None:
    values = (10, 20, 30, 40)
    order = (2, 0, 3, 1)
    assert te.apply_order(values, order) == (30, 10, 40, 20)


def test_assert_distinct_permutations_passes_and_fails_correctly() -> None:
    te.assert_distinct_permutations(((0, 1), (1, 0)), edge_id=te.EDGE_T539_TO_B649, policy="GLOBAL")
    with pytest.raises(te.Eh02DesignError):
        te.assert_distinct_permutations(
            ((0, 1), (0, 1)), edge_id=te.EDGE_T539_TO_B649, policy="GLOBAL"
        )


def test_permutation_ledger_digest_is_deterministic_edge_and_order_sensitive() -> None:
    orders = ((0, 1, 2), (2, 1, 0))
    d1 = te.permutation_ledger_digest(orders, edge_id=te.EDGE_T539_TO_B649, policy="GLOBAL")
    d2 = te.permutation_ledger_digest(orders, edge_id=te.EDGE_T539_TO_B649, policy="GLOBAL")
    d3 = te.permutation_ledger_digest(orders, edge_id=te.EDGE_P638Z1_TO_B649, policy="GLOBAL")
    assert d1 == d2
    assert d1 != d3
    assert len(d1) == 64


# ---------------------------------------------------------------------------
# Causal cross-series alignment
# ---------------------------------------------------------------------------


def test_build_qualifying_set_excludes_same_day_and_uses_strictly_prior() -> None:
    target_dates = ("2020-01-01", "2020-01-02", "2020-01-03", "2020-01-05")
    source_dates = ("2020-01-01", "2020-01-02", "2020-01-04")
    qs = te.build_qualifying_set(target_dates, source_dates)
    assert qs.target_indices == (1, 2, 3)
    assert qs.source_indices == (0, 1, 2)
    assert qs.same_day_excluded_count == 1
    assert qs.no_prior_count == 0


def test_build_qualifying_set_reports_no_prior_when_source_starts_later() -> None:
    target_dates = ("2000-01-01", "2000-06-01", "2001-01-01")
    source_dates = ("2000-12-01", "2001-06-01")
    qs = te.build_qualifying_set(target_dates, source_dates)
    # t=1 (2000-06-01): no source draw before it (source starts 2000-12-01) -> excluded
    # t=2 (2001-01-01): prior source is 2000-12-01 (idx 0) -> qualifies
    assert qs.target_indices == (2,)
    assert qs.source_indices == (0,)
    assert qs.no_prior_count == 1


def test_stale_source_indices_uses_at_or_before_cutoff() -> None:
    target_dates = ("2020-02-01",)
    source_dates = ("2020-01-01", "2020-01-04", "2020-01-05", "2020-01-31")
    # cutoff = 2020-02-01 - 4 days = 2020-01-28; last source <= cutoff is idx 2 (2020-01-05)
    result = te.stale_source_indices(target_dates, source_dates, (0,), stale_days=4)
    assert result == (2,)


def test_stale_source_indices_returns_none_when_no_draw_exists_that_early() -> None:
    target_dates = ("2020-01-10",)
    source_dates = ("2020-01-09",)
    result = te.stale_source_indices(target_dates, source_dates, (0,), stale_days=28)
    assert result == (None,)
