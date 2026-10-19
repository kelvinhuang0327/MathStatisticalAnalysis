from __future__ import annotations

import itertools
from collections.abc import Sequence

import numpy as np
import pytest

from lottolab.research.k_dpp_ticket_portfolio import select_k_dpp


def _fixed_gram_kernel(n: int, *, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    features = rng.normal(size=(n, n))
    return features @ features.T


def _exact_k_dpp_probabilities(l_kernel: np.ndarray, k: int) -> dict[frozenset[int], float]:
    """Independent oracle: P(S) proportional to det(L_S), the donor's target distribution."""
    n = l_kernel.shape[0]
    raw_mass = {
        frozenset(subset): float(np.linalg.det(l_kernel[np.ix_(subset, subset)]))
        for subset in itertools.combinations(range(n), k)
    }
    total = sum(raw_mass.values())
    return {subset: mass / total for subset, mass in raw_mass.items()}


@pytest.mark.parametrize(("n", "k"), [(1, 0), (1, 1), (5, 0), (5, 1), (5, 3), (5, 5), (8, 4)])
def test_returns_exactly_k_distinct_items(n: int, k: int) -> None:
    item_ids = tuple(range(n))
    kernel = _fixed_gram_kernel(n, seed=n * 100 + k)
    result = select_k_dpp(item_ids, l_kernel=kernel, k=k, seed=0)
    assert len(result) == k
    assert len(set(result)) == k
    assert set(result).issubset(item_ids)


def test_returns_distinct_items_for_non_integer_ids() -> None:
    item_ids = ("alpha", "beta", "gamma", "delta")
    kernel = _fixed_gram_kernel(4, seed=11)
    result = select_k_dpp(item_ids, l_kernel=kernel, k=2, seed=5)
    assert len(result) == 2
    assert set(result).issubset(item_ids)


def test_seeded_determinism_matches_for_int_seed() -> None:
    item_ids = tuple(range(6))
    kernel = _fixed_gram_kernel(6, seed=7)
    first = select_k_dpp(item_ids, l_kernel=kernel, k=3, seed=123)
    second = select_k_dpp(item_ids, l_kernel=kernel, k=3, seed=123)
    assert first == second


def test_seeded_determinism_matches_for_generator_seed() -> None:
    item_ids = tuple(range(6))
    kernel = _fixed_gram_kernel(6, seed=7)
    first = select_k_dpp(item_ids, l_kernel=kernel, k=3, seed=np.random.default_rng(123))
    second = select_k_dpp(item_ids, l_kernel=kernel, k=3, seed=np.random.default_rng(123))
    assert first == second


def test_k_zero_returns_empty_selection() -> None:
    item_ids = tuple(range(4))
    kernel = _fixed_gram_kernel(4, seed=3)
    assert select_k_dpp(item_ids, l_kernel=kernel, k=0, seed=1) == ()


def test_k_equals_n_returns_every_item() -> None:
    item_ids = tuple(range(4))
    kernel = _fixed_gram_kernel(4, seed=9)
    result = select_k_dpp(item_ids, l_kernel=kernel, k=4, seed=1)
    assert set(result) == set(item_ids)
    assert len(result) == 4


def test_rejects_negative_k() -> None:
    item_ids = tuple(range(3))
    kernel = np.eye(3)
    with pytest.raises(ValueError, match="k must be >= 0"):
        select_k_dpp(item_ids, l_kernel=kernel, k=-1, seed=0)


def test_rejects_k_greater_than_n() -> None:
    item_ids = tuple(range(3))
    kernel = np.eye(3)
    with pytest.raises(ValueError, match="exceeds ground set size"):
        select_k_dpp(item_ids, l_kernel=kernel, k=4, seed=0)


def test_rejects_duplicate_item_ids() -> None:
    with pytest.raises(ValueError, match="distinct"):
        select_k_dpp((1, 2, 2), l_kernel=np.eye(3), k=1, seed=0)


def test_rejects_non_square_kernel() -> None:
    item_ids = tuple(range(2))
    with pytest.raises(ValueError, match="square"):
        select_k_dpp(item_ids, l_kernel=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], k=1, seed=0)


def test_rejects_kernel_size_mismatch_with_item_ids() -> None:
    item_ids = tuple(range(3))
    with pytest.raises(ValueError, match="does not match len\\(item_ids\\)"):
        select_k_dpp(item_ids, l_kernel=np.eye(4), k=1, seed=0)


def test_rejects_ragged_kernel() -> None:
    item_ids = tuple(range(2))
    ragged: Sequence[Sequence[float]] = [[1.0, 0.0], [0.0]]
    with pytest.raises(ValueError, match="l_kernel"):
        select_k_dpp(item_ids, l_kernel=ragged, k=1, seed=0)


def test_rejects_non_symmetric_kernel() -> None:
    item_ids = tuple(range(2))
    with pytest.raises(ValueError, match="symmetric"):
        select_k_dpp(item_ids, l_kernel=[[1.0, 2.0], [0.0, 1.0]], k=1, seed=0)


def test_rejects_non_psd_kernel() -> None:
    item_ids = tuple(range(2))
    with pytest.raises(ValueError, match="positive semi-definite"):
        select_k_dpp(item_ids, l_kernel=[[1.0, 2.0], [2.0, 1.0]], k=1, seed=0)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_rejects_non_finite_kernel(bad_value: float) -> None:
    item_ids = tuple(range(2))
    with pytest.raises(ValueError, match="non-finite"):
        select_k_dpp(item_ids, l_kernel=[[1.0, 0.0], [0.0, bad_value]], k=1, seed=0)


def test_diagonal_kernel_returns_valid_selection() -> None:
    item_ids = tuple(range(5))
    kernel = np.diag([10.0, 0.1, 5.0, 0.2, 1.0])
    for seed in range(20):
        result = select_k_dpp(item_ids, l_kernel=kernel, k=2, seed=seed)
        assert len(result) == 2
        assert len(set(result)) == 2


def test_tiny_two_item_diagonal_matches_hand_computed_kdpp_oracle() -> None:
    """Donor-characterization fixture: L=diag(3,1) gives P({0})=3/4, P({1})=1/4 under
    the k-DPP target distribution P(S) proportional to det(L_S) for |S|=1, which is
    exactly what dppy.exact_sampling.k_dpp_eig_vecs_selector / proj_dpp_sampler_eig
    (pinned commit 0d34dd67deedfed1d66f555636067f8fb2b0aab7) are documented to sample.
    """
    item_ids = (0, 1)
    kernel = np.diag([3.0, 1.0])
    oracle = _exact_k_dpp_probabilities(kernel, k=1)
    assert oracle[frozenset({0})] == pytest.approx(0.75)
    assert oracle[frozenset({1})] == pytest.approx(0.25)

    num_trials = 3000
    counts = {frozenset({0}): 0, frozenset({1}): 0}
    for seed in range(num_trials):
        (chosen,) = select_k_dpp(item_ids, l_kernel=kernel, k=1, seed=seed)
        counts[frozenset({chosen})] += 1

    for subset, probability in oracle.items():
        empirical = counts[subset] / num_trials
        assert empirical == pytest.approx(probability, abs=0.05)


def test_selection_frequencies_match_exact_k_dpp_distribution() -> None:
    item_ids = tuple(range(4))
    kernel = _fixed_gram_kernel(4, seed=42)
    oracle = _exact_k_dpp_probabilities(kernel, k=2)
    assert sum(oracle.values()) == pytest.approx(1.0)

    num_trials = 4000
    counts: dict[frozenset[int], int] = dict.fromkeys(oracle, 0)
    for seed in range(num_trials):
        result = select_k_dpp(item_ids, l_kernel=kernel, k=2, seed=seed)
        counts[frozenset(result)] += 1

    for subset, probability in oracle.items():
        empirical = counts[subset] / num_trials
        assert empirical == pytest.approx(probability, abs=0.05)


def test_permutation_consistency_of_exact_probabilities() -> None:
    kernel = _fixed_gram_kernel(4, seed=99)
    k = 2
    original = _exact_k_dpp_probabilities(kernel, k)

    permutation = [2, 0, 3, 1]
    permuted_kernel = kernel[np.ix_(permutation, permutation)]
    permuted = _exact_k_dpp_probabilities(permuted_kernel, k)

    for permuted_subset, probability in permuted.items():
        original_subset = frozenset(permutation[i] for i in permuted_subset)
        assert original[original_subset] == pytest.approx(probability, abs=1e-9)


def test_rank_deficient_kernel_singleton_selection_is_valid() -> None:
    item_ids = tuple(range(3))
    vector = np.array([1.0, 2.0, 3.0])
    rank_one_kernel = np.outer(vector, vector)
    for seed in range(20):
        result = select_k_dpp(item_ids, l_kernel=rank_one_kernel, k=1, seed=seed)
        assert len(result) == 1
        assert result[0] in item_ids


def test_rank_deficient_kernel_rejects_k_above_rank() -> None:
    item_ids = tuple(range(3))
    vector = np.array([1.0, 2.0, 3.0])
    rank_one_kernel = np.outer(vector, vector)
    with pytest.raises(ValueError, match="numerical rank"):
        select_k_dpp(item_ids, l_kernel=rank_one_kernel, k=2, seed=0)
