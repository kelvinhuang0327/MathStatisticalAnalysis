"""Focused independent checks for the frozen model-probability evaluation."""

import math
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest

from lottolab.domain.prize_evaluation import evaluate_big_lotto_ticket
from lottolab.research import b649_frozen_min_overlap_success_probability as model
from lottolab.research.exact_coverage_fast_evaluator import (
    clear_cache,
    fast_exact_portfolio_coverage,
)

PORTFOLIO = ((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 7, 8))


def official_win(tickets, winning, special):
    return any(
        evaluate_big_lotto_ticket(
            predicted_main_numbers=t,
            predicted_special_number=None,
            winning_main_numbers=winning,
            winning_special_number=special,
        ).is_winner
        for t in tickets
    )


@pytest.mark.parametrize(
    "hits,special_hit", [(h, s) for h in range(7) for s in (False, True) if h < 6 or not s]
)
def test_frozen_prize_rule_and_conditional_special_integration(hits, special_hit):
    model.validate_contract()
    ticket = (1, 2, 3, 4, 5, 6)
    winning = tuple(range(1, hits + 1)) + tuple(range(7, 13 - hits))
    special = hits + 1 if special_hit else 49
    assert official_win((ticket,), winning, special) == (hits >= 3 or (hits == 2 and special_hit))
    exact_special_count = sum(
        official_win((ticket,), winning, s) for s in range(1, 50) if s not in winning
    )
    assert model.conditional_units((ticket,), winning)[0] == exact_special_count


def test_special_union_counts_each_eligible_number_once_and_excludes_main_numbers():
    winning = (1, 2, 9, 10, 11, 12)
    # Both tickets hit 1,2; remaining union is {3,4,5,6,7,8}, not 8 ticket incidences.
    assert model.conditional_units(PORTFOLIO, winning) == (6, 0, 0)
    draws = np.asarray([model.mask(winning)], dtype=np.uint64)
    assert model.score_masks((PORTFOLIO,), draws)[0].tolist() == [[6, 0, 0]]


def test_small_exhaustive_oracle_against_frozen_official_evaluator_and_existing_coverage():
    winning_sets = tuple(combinations(range(1, 13), 6))
    explicit_wins = sum(
        official_win(PORTFOLIO, w, s) for w in winning_sets for s in range(1, 13) if s not in w
    )
    exact = model.exact_small(PORTFOLIO, 12)
    assert exact[0] == Fraction(explicit_wins, math.comb(12, 6) * 6)
    assert 0 < exact[1] < exact[0] < 1  # Detect a vacuous toy where every draw wins.
    for index, threshold in ((1, 3), (2, 4)):
        assert exact[index] == fast_exact_portfolio_coverage(12, 6, threshold, PORTFOLIO)
    clear_cache()
    vector = model.score_masks(
        (PORTFOLIO,),
        np.asarray([model.mask(w) for w in winning_sets], dtype=np.uint64),
        pool_size=12,
    )[0]
    scalar = [model.conditional_units(PORTFOLIO, w, 12) for w in winning_sets]
    assert vector.tolist() == [list(v) for v in scalar]
    with pytest.raises(ValueError, match="SMALL_DOMAIN"):
        model.exact_small(PORTFOLIO, 49)


def test_consistent_relabeling_preserves_exact_probability_and_every_conditional_score():
    def permute(values):
        return tuple(sorted(13 - n for n in values))

    relabeled = tuple(permute(t) for t in PORTFOLIO)
    assert model.exact_small(PORTFOLIO, 12) == model.exact_small(relabeled, 12)
    for winning in combinations(range(1, 13), 6):
        assert model.conditional_units(PORTFOLIO, winning, 12) == model.conditional_units(
            relabeled, permute(winning), 12
        )


def test_fixed_seed_reproduction_legality_and_identical_portfolio_exact_zero():
    seed = model.target_seed("97000098")
    draws = model.sample_main_masks(np.random.Generator(np.random.PCG64(seed)), 2048)
    repeat = model.sample_main_masks(np.random.Generator(np.random.PCG64(seed)), 2048)
    assert np.array_equal(draws, repeat)
    assert np.all(np.bitwise_count(draws) == 6)
    assert np.all(draws < np.uint64(1 << 49))
    assert model.target_seed("97000101") != seed
    a, d = model.score_masks((PORTFOLIO, tuple(reversed(PORTFOLIO))), draws)
    moments = model.pair_moments(a, d)
    assert moments["sum_delta"] == moments["sumsq_delta"] == [0, 0, 0]
    assert moments["sum_a"] == moments["sum_d"]


def test_paired_error_uses_signed_within_target_variance_and_exact_equal_zero():
    n = model.SAMPLES_PER_TARGET
    a = np.zeros((n, 3), dtype=np.uint8)
    d = np.zeros_like(a)
    a[: n // 2, 0] = 43
    d[n // 2 : 3 * n // 4, 0] = 43
    row = {"by_k": {"10": {"identical_ticket_sets": False, "moments": model.pair_moments(a, d)}}}
    summary = model.summarize([row], 10)
    delta = summary["metrics"]["official_any_prize"]["delta"]
    assert delta["probability"] == -0.25
    expected_se = math.sqrt((0.75 - 0.25**2) / (n - 1))
    assert delta["mc_standard_error"] == pytest.approx(expected_se)
    row["by_k"]["10"] = {"identical_ticket_sets": True, "moments": model.pair_moments(a, a)}
    equal = model.summarize([row], 10)["metrics"]["official_any_prize"]["delta"]
    assert equal["hoeffding_97_5_interval"] == equal["mc_normal_95_interval"] == [0, 0]


def test_complete_frozen_cohort_identity_and_forced_subset():
    root = Path(__file__).resolve().parents[2]
    targets = model.load_frozen(root / model.INPUT_PATH)
    assert len(targets) == model.EXPECTED_TARGETS == 1761
    assert sum(t.candidate_count == 20 for t in targets) == 608
    assert all(
        set(t.portfolios[20][0]) == set(t.portfolios[20][1])
        for t in targets
        if t.candidate_count == 20
    )
    assert all(len(t.portfolios[k][arm]) == k for t in targets for k in model.KS for arm in (0, 1))
