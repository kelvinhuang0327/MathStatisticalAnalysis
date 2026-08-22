"""Exact, dependency-free statistics for lottery uniformity/dependence testing.

Every function computes exact discrete-distribution probabilities (binomial,
hypergeometric, order statistics) using only the Python standard library —
this project ships no numpy/scipy dependency. Tail probabilities and power
are computed in log-space with a log-sum-exp reduction so they stay
numerically stable at the sample sizes real draw histories reach (order
10^3-10^4), where a naive `p ** k` underflows, or `math.comb(n, k)` overflows
a float, before the two terms are multiplied together.

Two-sided p-values use the standard discrete-exact-test definition — the
total probability mass of every outcome at least as unlikely as the one
observed — not a doubled one-sided tail, which over- or under-states
significance whenever the null distribution is skewed (as Binomial(n, p) is
for p far from 0.5, and as every hypergeometric/order-statistic distribution
here is away from its center).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

_TIE_TOLERANCE = 1e-9


def _log_binomial_pmf(n: int, k: int, p: float) -> float:
    """log P(X = k) for X ~ Binomial(n, p), or -inf outside [0, n]."""

    if not 0 <= k <= n:
        return -math.inf
    if p <= 0.0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if k == n else -math.inf
    log_coefficient = math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    return log_coefficient + k * math.log(p) + (n - k) * math.log1p(-p)


def _log_sum_exp(log_values: Sequence[float]) -> float:
    finite = [value for value in log_values if value != -math.inf]
    if not finite:
        return -math.inf
    top = max(finite)
    return top + math.log(math.fsum(math.exp(value - top) for value in finite))


def binomial_log_pmf_table(n: int, p: float) -> tuple[float, ...]:
    """log P(X = k) for k = 0..n, X ~ Binomial(n, p). Computed once, reused."""

    if n < 0:
        raise ValueError("n must be non-negative")
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must lie in [0, 1]")
    return tuple(_log_binomial_pmf(n, k, p) for k in range(n + 1))


def binomial_pmf(n: int, k: int, p: float) -> float:
    """Exact P(X = k) for X ~ Binomial(n, p)."""

    log_pmf = _log_binomial_pmf(n, k, p)
    return 0.0 if log_pmf == -math.inf else math.exp(log_pmf)


def two_sided_p_value_from_log_pmf_table(log_pmf_table: Sequence[float], k: int) -> float:
    """Exact two-sided p-value for outcome `k` given a precomputed log-pmf table."""

    if not 0 <= k < len(log_pmf_table):
        raise ValueError("k is outside the table's support")
    observed = log_pmf_table[k]
    at_least_as_extreme = [
        value for value in log_pmf_table if value <= observed + _TIE_TOLERANCE
    ]
    return min(1.0, math.exp(_log_sum_exp(at_least_as_extreme)))


def binomial_two_sided_exact_p_value(n: int, k: int, p: float) -> float:
    """Exact two-sided p-value: total mass of outcomes no more likely than `k`."""

    if not 0 <= k <= n:
        raise ValueError("k must lie in [0, n]")
    return two_sided_p_value_from_log_pmf_table(binomial_log_pmf_table(n, p), k)


def binomial_two_sided_exact_power(
    n: int, p_null: float, p_alt: float, *, alpha: float
) -> float:
    """Exact power, at significance `alpha`, of the two-sided exact test against `p_alt`.

    Enumerates the exact rejection region under `p_null` once, then sums the
    exact Binomial(n, p_alt) mass over it. This is the true finite-sample
    power of the exact test actually used elsewhere in this module, not a
    normal approximation to it.
    """

    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie in (0, 1)")
    null_table = binomial_log_pmf_table(n, p_null)
    alt_table = binomial_log_pmf_table(n, p_alt)
    rejection_region = [
        k
        for k in range(n + 1)
        if two_sided_p_value_from_log_pmf_table(null_table, k) <= alpha
    ]
    if not rejection_region:
        return 0.0
    return math.exp(_log_sum_exp([alt_table[k] for k in rejection_region]))


def hypergeometric_pmf(population_size: int, success_states: int, draws: int, k: int) -> float:
    """Exact P(X = k) for X ~ Hypergeometric(N, K, n): `draws` drawn without

    replacement from a population of `population_size` containing exactly
    `success_states` successes.
    """

    n_pop, k_succ, n_draw = population_size, success_states, draws
    low = max(0, n_draw - (n_pop - k_succ))
    high = min(n_draw, k_succ)
    if not low <= k <= high:
        return 0.0
    return (
        math.comb(k_succ, k)
        * math.comb(n_pop - k_succ, n_draw - k)
        / math.comb(n_pop, n_draw)
    )


def hypergeometric_mean(population_size: int, success_states: int, draws: int) -> float:
    return draws * success_states / population_size


def hypergeometric_variance(population_size: int, success_states: int, draws: int) -> float:
    n_pop, k_succ, n_draw = population_size, success_states, draws
    return (
        n_draw
        * (k_succ / n_pop)
        * ((n_pop - k_succ) / n_pop)
        * ((n_pop - n_draw) / (n_pop - 1))
    )


def order_statistic_pmf(population_size: int, sample_size: int, rank: int, value: int) -> float:
    """Exact P(X_(rank) = value): the `rank`-th smallest (1-indexed) of a

    `sample_size`-element subset drawn without replacement from
    {1, ..., population_size}.
    """

    n_pop, m_sample, k_rank, x = population_size, sample_size, rank, value
    if not 1 <= k_rank <= m_sample or not 1 <= x <= n_pop:
        return 0.0
    below, above = x - 1, n_pop - x
    if below < k_rank - 1 or above < m_sample - k_rank:
        return 0.0
    return (
        math.comb(below, k_rank - 1)
        * math.comb(above, m_sample - k_rank)
        / math.comb(n_pop, m_sample)
    )


def order_statistic_mean(population_size: int, sample_size: int, rank: int) -> float:
    """Exact E[X_(rank)] = rank * (population_size + 1) / (sample_size + 1)."""

    return rank * (population_size + 1) / (sample_size + 1)


def order_statistic_two_sided_p_value(
    population_size: int, sample_size: int, rank: int, observed_value: int
) -> float:
    pmf_by_value = {
        x: order_statistic_pmf(population_size, sample_size, rank, x)
        for x in range(1, population_size + 1)
    }
    observed = pmf_by_value[observed_value]
    return min(
        1.0,
        math.fsum(v for v in pmf_by_value.values() if v <= observed + _TIE_TOLERANCE),
    )


def holm_bonferroni_adjusted(p_values: Sequence[float]) -> tuple[float, ...]:
    """Standard Holm step-down adjusted p-values, returned in the input order.

    For p-values sorted ascending p_(1) <= ... <= p_(m), the adjusted value
    at rank i is max(adjusted_(i-1), min(1, (m - i + 1) * p_(i))) — a running
    maximum, so adjusted p-values are guaranteed non-decreasing in the sorted
    order.
    """

    count = len(p_values)
    order = sorted(range(count), key=lambda index: p_values[index])
    adjusted_in_sorted_order: list[float] = []
    running_max = 0.0
    for rank, index in enumerate(order):
        multiplier = count - rank
        candidate = min(1.0, multiplier * p_values[index])
        running_max = max(running_max, candidate)
        adjusted_in_sorted_order.append(running_max)
    result = [0.0] * count
    for rank, index in enumerate(order):
        result[index] = adjusted_in_sorted_order[rank]
    return tuple(result)


def finite_population_sum_mean(population_size: int, sample_size: int) -> float:
    """E[sum] for a size-`sample_size` simple random sample without replacement

    from {1, ..., population_size}.
    """

    return sample_size * (population_size + 1) / 2


def finite_population_sum_variance(population_size: int, sample_size: int) -> float:
    """Var[sum] for a size-`sample_size` simple random sample without replacement

    from {1, ..., population_size}, via the standard finite-population-correction
    formula: n * sigma^2 * (N - n) / (N - 1), sigma^2 = Var[Uniform{1..N}].
    """

    n_pop, n_sample = population_size, sample_size
    if n_pop <= 1:
        raise ValueError("population_size must be at least 2")
    population_variance = (n_pop * n_pop - 1) / 12
    return n_sample * population_variance * (n_pop - n_sample) / (n_pop - 1)


def normal_two_sided_p_value(observed: float, mean: float, variance: float) -> float:
    """Two-sided asymptotic-normal p-value: P(|Z| >= |observed - mean| / sd).

    Used only where this module documents an explicit asymptotic-normal
    (not exact discrete) test, backed by an exact mean/variance derived
    elsewhere in this module.
    """

    if variance <= 0.0:
        raise ValueError("variance must be positive")
    z = (observed - mean) / math.sqrt(variance)
    return math.erfc(abs(z) / math.sqrt(2.0))
