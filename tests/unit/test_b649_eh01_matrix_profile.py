from __future__ import annotations

import math
import random

import pytest

from lottolab.research import b649_eh01_matrix_profile as eh01


def _assert_results_match(bf: eh01.CausalProfileResult, opt: eh01.CausalProfileResult) -> None:
    assert bf.length == opt.length
    assert bf.eligible_query_count == opt.eligible_query_count
    assert bf.motif_distance == pytest.approx(opt.motif_distance, abs=1e-9)
    assert bf.motif_query_index == opt.motif_query_index
    assert bf.motif_neighbor_index == opt.motif_neighbor_index
    assert bf.motif_support_count == opt.motif_support_count
    assert bf.discord_distance == pytest.approx(opt.discord_distance, abs=1e-9)
    assert bf.discord_query_index == opt.discord_query_index
    assert bf.discord_neighbor_index == opt.discord_neighbor_index


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
@pytest.mark.parametrize("m", [3, 5, 10, 20])
def test_optimized_matches_bruteforce_on_random_series(seed: int, m: int) -> None:
    # This is the proposal's own required `synthetic_fixture_check`
    # (section 10.3 / STOP_SYNTHETIC_FIXTURE_FAIL): the optimized O(n^2)
    # incremental-dot-product implementation must agree exactly (to
    # floating point tolerance) with the literal-formula reference before
    # it is trusted at real B649 scale.
    rng = random.Random(seed)
    series = tuple(rng.randint(21, 279) for _ in range(120))
    bf = eh01.causal_profile_bruteforce(series, m)
    opt = eh01.causal_profile(series, m)
    _assert_results_match(bf, opt)


def test_optimized_matches_bruteforce_at_the_exact_eligibility_boundary() -> None:
    # num_windows == 2m exactly -> exactly one eligible query.
    rng = random.Random(99)
    m = 5
    series = tuple(rng.randint(21, 279) for _ in range(2 * m + m - 1))
    bf = eh01.causal_profile_bruteforce(series, m)
    opt = eh01.causal_profile(series, m)
    assert bf.eligible_query_count == 1
    _assert_results_match(bf, opt)


def test_both_implementations_raise_geometry_insufficient_one_below_boundary() -> None:
    rng = random.Random(99)
    m = 5
    series = tuple(rng.randint(21, 279) for _ in range(2 * m + m - 2))  # one short
    with pytest.raises(eh01.GeometryInsufficientError):
        eh01.causal_profile_bruteforce(series, m)
    with pytest.raises(eh01.GeometryInsufficientError):
        eh01.causal_profile(series, m)


def test_engineered_exact_tie_gives_matching_support_count_and_earliest_locations() -> None:
    # A length-3 triple [50, 60, 70] repeated three times, embedded in
    # noise that never itself reproduces that exact triple, forces a known
    # exact-zero-distance motif with a hand-countable support.
    rng = random.Random(123)

    def noise(k: int) -> list[int]:
        return [rng.randint(80, 279) for _ in range(k)]  # disjoint range from the motif's values

    series = [*noise(10), 50, 60, 70, *noise(15), 50, 60, 70, *noise(10), 50, 60, 70]
    series_t = tuple(series)
    bf = eh01.causal_profile_bruteforce(series_t, 3)
    opt = eh01.causal_profile(series_t, 3)
    _assert_results_match(bf, opt)
    assert opt.motif_distance == pytest.approx(0.0, abs=1e-9)
    assert opt.motif_support_count == 3  # 3 admissible pairs among the 3 occurrences


def test_causal_admissibility_never_uses_an_overlapping_or_future_candidate() -> None:
    # Directly checks the definition, not just agreement between the two
    # implementations: for every reported motif/discord neighbor, the
    # candidate window must end strictly before the query window starts.
    rng = random.Random(7)
    m = 10
    series = tuple(rng.randint(21, 279) for _ in range(150))
    result = eh01.causal_profile(series, m)
    assert result.motif_neighbor_index + m - 1 < result.motif_query_index
    assert result.discord_neighbor_index + m - 1 < result.discord_query_index


def test_constant_window_is_excluded_as_both_query_and_candidate() -> None:
    # A constant run of length >= m has undefined z-normalization and must
    # never appear as a query or a candidate, but the profile must still
    # be computable from the surrounding non-constant windows.
    rng = random.Random(55)
    m = 5
    constant_run = [150] * 6
    lead_noise = [rng.randint(21, 279) for _ in range(20)]
    tail_noise = [rng.randint(21, 279) for _ in range(30)]
    series = tuple([*lead_noise, *constant_run, *tail_noise])
    stats = eh01.compute_window_stats(series, m)
    constant_window_starts = [k for k, valid in enumerate(stats.valid) if not valid]
    assert constant_window_starts  # the fixture actually produced >=1 constant window

    result = eh01.causal_profile(series, m)
    for start in constant_window_starts:
        one_indexed = start + 1
        assert result.motif_query_index != one_indexed
        assert result.discord_query_index != one_indexed
        assert result.motif_neighbor_index != one_indexed
        assert result.discord_neighbor_index != one_indexed


def test_motif_and_discord_statistics_are_negation_and_identity_of_distance() -> None:
    rng = random.Random(3)
    series = tuple(rng.randint(21, 279) for _ in range(80))
    result = eh01.causal_profile(series, 5)
    assert result.motif_statistic == -result.motif_distance
    assert result.discord_statistic == result.discord_distance


def test_window_stats_population_std_ddof0_matches_hand_computation() -> None:
    series = (1, 2, 3, 4, 5)
    stats = eh01.compute_window_stats(series, 5)
    assert stats.mean[0] == pytest.approx(3.0)
    # population variance of 1..5 = mean((x-3)^2) = (4+1+0+1+4)/5 = 2.0
    assert stats.std[0] == pytest.approx(math.sqrt(2.0))
    assert stats.valid[0] is True


def test_window_stats_flags_constant_window_as_invalid() -> None:
    series = (7, 7, 7, 7)
    stats = eh01.compute_window_stats(series, 4)
    assert stats.valid[0] is False
    assert stats.std[0] == 0.0
