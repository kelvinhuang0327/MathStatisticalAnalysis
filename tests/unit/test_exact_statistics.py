from __future__ import annotations

import itertools
import math

import pytest

from lottolab.research.exact_statistics import (
    binomial_exact_minimum_detectable_lift,
    binomial_exact_upper_critical_value,
    binomial_lower_tail,
    binomial_one_sided_upper_exact_power,
    binomial_pmf,
    binomial_two_sided_exact_p_value,
    binomial_two_sided_exact_power,
    binomial_upper_tail,
    finite_population_sum_mean,
    finite_population_sum_variance,
    holm_bonferroni_adjusted,
    holm_step_down_rejections,
    hypergeometric_mean,
    hypergeometric_pmf,
    hypergeometric_variance,
    normal_two_sided_p_value,
    order_statistic_mean,
    order_statistic_pmf,
    order_statistic_two_sided_p_value,
)

_P0 = 7729 / 249711


def test_binomial_pmf_sums_to_one() -> None:
    n, p = 40, 0.15
    total = math.fsum(binomial_pmf(n, k, p) for k in range(n + 1))
    assert total == pytest.approx(1.0, abs=1e-12)


def test_binomial_two_sided_p_value_known_symmetric_case() -> None:
    # n=4, p=0.5: pmf = [1, 4, 6, 4, 1] / 16, exactly.
    assert binomial_two_sided_exact_p_value(4, 0, 0.5) == pytest.approx(2 / 16)
    assert binomial_two_sided_exact_p_value(4, 4, 0.5) == pytest.approx(2 / 16)
    assert binomial_two_sided_exact_p_value(4, 2, 0.5) == pytest.approx(1.0)


def test_binomial_two_sided_p_value_rejects_out_of_range_k() -> None:
    with pytest.raises(ValueError, match="k must lie in"):
        binomial_two_sided_exact_p_value(10, 11, 0.5)


def test_binomial_two_sided_p_value_is_larger_near_the_mean() -> None:
    n, p = 2138, 6 / 49
    mean = n * p
    near_mean_p = binomial_two_sided_exact_p_value(n, round(mean), p)
    far_from_mean_p = binomial_two_sided_exact_p_value(n, round(mean) + 60, p)
    assert near_mean_p > far_from_mean_p


def test_binomial_power_increases_away_from_the_null() -> None:
    n, p_null, alpha = 2138, 6 / 49, 0.05 / 49
    at_null = binomial_two_sided_exact_power(n, p_null, p_null, alpha=alpha)
    small_shift = binomial_two_sided_exact_power(n, p_null, p_null + 0.01, alpha=alpha)
    large_shift = binomial_two_sided_exact_power(n, p_null, p_null + 0.03, alpha=alpha)
    assert at_null <= alpha + 1e-9
    assert at_null < small_shift < large_shift
    assert large_shift <= 1.0


def test_holm_bonferroni_known_example() -> None:
    # Hand-computed: inputs in original order [0.01, 0.04, 0.03, 0.005].
    adjusted = holm_bonferroni_adjusted([0.01, 0.04, 0.03, 0.005])
    assert adjusted == pytest.approx([0.03, 0.06, 0.06, 0.02])


def test_holm_bonferroni_is_never_smaller_than_the_raw_p_value() -> None:
    raw = [0.001, 0.2, 0.03, 0.5, 0.0001]
    adjusted = holm_bonferroni_adjusted(raw)
    assert all(a >= r for a, r in zip(adjusted, raw, strict=True))


def test_holm_step_down_matches_adjusted_p_value_cutoff() -> None:
    raw = [0.01, 0.04, 0.03, 0.005]
    rejected = holm_step_down_rejections(raw, alpha=0.05)
    adjusted = holm_bonferroni_adjusted(raw)
    assert rejected == tuple(value <= 0.05 for value in adjusted)
    assert rejected == (True, False, False, True)


def test_holm_first_step_threshold_is_not_used_for_every_test() -> None:
    # Two tiny p-values and one moderate p-value. First-step alpha/3 would
    # reject only p < 0.05/3, but Holm still rejects the second after the
    # first is dropped.
    raw = [0.01, 0.02, 0.9]
    rejected = holm_step_down_rejections(raw, alpha=0.05)
    assert raw[1] > 0.05 / 3
    assert rejected == (True, True, False)


def test_binomial_upper_and_lower_tails_sum_past_the_observed_point() -> None:
    n, k, p = 20, 7, 0.3
    upper = binomial_upper_tail(n, k, p)
    lower_exclusive = binomial_lower_tail(n, k - 1, p)
    assert upper + lower_exclusive == pytest.approx(1.0, abs=1e-12)


def test_binomial_exact_upper_critical_values_for_p0() -> None:
    assert binomial_exact_upper_critical_value(50, _P0, 0.05) == 5
    assert binomial_exact_upper_critical_value(300, _P0, 0.05) == 15
    assert binomial_exact_upper_critical_value(750, _P0, 0.05) == 32
    assert binomial_exact_upper_critical_value(1412, _P0, 0.05) == 56


def test_one_sided_exact_power_is_the_upper_tail_at_the_critical_value() -> None:
    n, alpha = 50, 0.05
    k_star = binomial_exact_upper_critical_value(n, _P0, alpha)
    p_alt = 4.2250 * _P0
    assert binomial_one_sided_upper_exact_power(n, _P0, p_alt, alpha=alpha) == pytest.approx(
        binomial_upper_tail(n, k_star, p_alt), abs=1e-15
    )


@pytest.mark.parametrize(
    ("n", "alpha", "expected_lift"),
    [
        (50, 0.05, 4.2250),
        (300, 0.05, 1.9385),
        (750, 0.05, 1.5723),
        (1412, 0.05, 1.4191),
        (50, 0.05 / 21, 5.6831),
        (300, 0.05 / 21, 2.5254),
        (750, 0.05 / 21, 1.8934),
        (50, 0.05 / 28, 5.6831),
        (300, 0.05 / 28, 2.5254),
        (750, 0.05 / 28, 1.8934),
        (1412, 0.05 / 28, 1.6354),
    ],
)
def test_exact_mde_lift_fixtures(n: int, alpha: float, expected_lift: float) -> None:
    lift = binomial_exact_minimum_detectable_lift(n, _P0, alpha=alpha, power_target=0.80)
    assert lift == pytest.approx(expected_lift, abs=5e-5)
    assert binomial_one_sided_upper_exact_power(n, _P0, lift * _P0, alpha=alpha) >= 0.80 - 1e-9


def test_hypergeometric_pmf_sums_to_one() -> None:
    total = math.fsum(hypergeometric_pmf(49, 6, 6, k) for k in range(7))
    assert total == pytest.approx(1.0, abs=1e-12)


def test_hypergeometric_mean_matches_direct_computation() -> None:
    direct_mean = math.fsum(k * hypergeometric_pmf(49, 6, 6, k) for k in range(7))
    assert direct_mean == pytest.approx(hypergeometric_mean(49, 6, 6))


def test_hypergeometric_variance_matches_direct_computation() -> None:
    mean = hypergeometric_mean(49, 6, 6)
    direct_variance = math.fsum(
        ((k - mean) ** 2) * hypergeometric_pmf(49, 6, 6, k) for k in range(7)
    )
    assert direct_variance == pytest.approx(hypergeometric_variance(49, 6, 6))


@pytest.mark.parametrize("rank", [1, 2, 3, 4, 5, 6])
def test_order_statistic_pmf_sums_to_one(rank: int) -> None:
    total = math.fsum(order_statistic_pmf(49, 6, rank, x) for x in range(1, 50))
    assert total == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("rank", [1, 2, 3, 4, 5, 6])
def test_order_statistic_mean_matches_direct_computation(rank: int) -> None:
    direct_mean = math.fsum(x * order_statistic_pmf(49, 6, rank, x) for x in range(1, 50))
    assert direct_mean == pytest.approx(order_statistic_mean(49, 6, rank))


def test_order_statistic_two_sided_p_value_is_one_at_the_mean_rounded() -> None:
    mean = round(order_statistic_mean(49, 6, 1))
    p_value = order_statistic_two_sided_p_value(49, 6, 1, mean)
    assert 0.0 < p_value <= 1.0


def test_order_statistic_two_sided_p_value_smaller_at_extreme_value() -> None:
    # Rank-1 (smallest of six) being 44 is an extreme, near-impossible outcome.
    extreme = order_statistic_two_sided_p_value(49, 6, 1, 44)
    central = order_statistic_two_sided_p_value(49, 6, 1, round(order_statistic_mean(49, 6, 1)))
    assert extreme < central


def _brute_force_sums(population: int, sample_size: int) -> list[int]:
    combos = itertools.combinations(range(1, population + 1), sample_size)
    return [sum(combo) for combo in combos]


def test_finite_population_sum_mean_matches_brute_force_enumeration() -> None:
    population, sample_size = 9, 3
    all_sums = _brute_force_sums(population, sample_size)
    assert math.fsum(all_sums) / len(all_sums) == pytest.approx(
        finite_population_sum_mean(population, sample_size)
    )


def test_finite_population_sum_variance_matches_brute_force_enumeration() -> None:
    population, sample_size = 9, 3
    all_sums = _brute_force_sums(population, sample_size)
    mean = math.fsum(all_sums) / len(all_sums)
    brute_force_variance = math.fsum((s - mean) ** 2 for s in all_sums) / len(all_sums)
    assert brute_force_variance == pytest.approx(
        finite_population_sum_variance(population, sample_size)
    )


def test_finite_population_sum_variance_rejects_degenerate_population() -> None:
    with pytest.raises(ValueError, match="population_size must be at least 2"):
        finite_population_sum_variance(1, 1)


def test_normal_two_sided_p_value_is_one_at_the_mean() -> None:
    assert normal_two_sided_p_value(100.0, 100.0, 25.0) == pytest.approx(1.0)


def test_normal_two_sided_p_value_symmetric() -> None:
    above = normal_two_sided_p_value(105.0, 100.0, 25.0)
    below = normal_two_sided_p_value(95.0, 100.0, 25.0)
    assert above == pytest.approx(below)
    assert 0.0 < above < 1.0


def test_normal_two_sided_p_value_rejects_nonpositive_variance() -> None:
    with pytest.raises(ValueError, match="variance must be positive"):
        normal_two_sided_p_value(1.0, 0.0, 0.0)
