"""Focused oracles for the seven-state higher-order outcome certificate."""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

from lottolab.research import (
    b649_k20_r3_seven_state_higher_order_bound_r9 as r9,
)


def _brute_relaxation_correction(
    outcome_count: int,
    exact_s1: int,
    s2_floor: int,
    maximum_multiplicity: int,
) -> int:
    best: int | None = None
    for histogram in itertools.product(range(outcome_count + 1), repeat=maximum_multiplicity + 1):
        if sum(histogram) != outcome_count:
            continue
        if sum(m * count for m, count in enumerate(histogram)) != exact_s1:
            continue
        s2 = sum(math.comb(m, 2) * count for m, count in enumerate(histogram))
        if s2 < s2_floor:
            continue
        correction = sum((m - 1) * count for m, count in enumerate(histogram) if m >= 2)
        best = correction if best is None else min(best, correction)
    if best is None:
        raise AssertionError("small histogram oracle found no feasible distribution")
    return best


def test_seven_state_identity_and_pinned_s4_facts() -> None:
    states = r9.load_certified_states()

    assert len(states) == 7
    assert tuple(state.identifier for state in states) == tuple(r9.r8.SUPPORT_WITNESS_BITMASKS)
    assert all(len(state.support_bitmasks) == 18 for state in states)
    assert tuple(state.prior_s4_witness for state in states[:6]) == (
        0,
        0,
        0,
        0,
        2016,
        2016,
    )
    assert all(state.prior_s4_proven for state in states[:6])
    assert states[-1].prior_s4_lower_bound == 4368
    assert states[-1].prior_s4_witness == 5208
    assert not states[-1].prior_s4_proven


def test_exact_single_event_count_matches_pair_diagonal_and_exposes_legacy_error() -> None:
    exact = r9.OUTCOME_MULTIPLICITY * sum(
        math.comb(r9.DRAW_SIZE, hits)
        * math.comb(r9.POOL_SIZE - r9.DRAW_SIZE, r9.OUTCOME_SET_SIZE - hits)
        for hits in range(r9.OUTRIGHT_MATCHES, r9.DRAW_SIZE + 1)
    )

    assert exact == 18_611_432
    assert exact == r9.SINGLE_TICKET_OUTCOMES
    assert r9.pair_intersection_count(r9.DRAW_SIZE) == exact
    assert r9.LEGACY_SINGLE_TICKET_OUTCOMES == 18_221_078
    assert r9.LEGACY_BASELINE_CORRECTION == 7_807_080


def test_native_multiplicity_histogram_matches_small_official_outcome_oracle(
    tmp_path: Path,
) -> None:
    r9.runtime_preflight()
    executable = r9.compile_native_counter(tmp_path)
    tickets = (
        sum(1 << label for label in range(6)),
        sum(1 << label for label in (0, 1, 2, 6, 7, 8)),
        sum(1 << label for label in (0, 2, 4, 6, 7, 8)),
        sum(1 << label for label in (1, 3, 4, 5, 7, 8)),
    )
    observed = r9.run_native_counter(
        executable,
        tickets,
        pool_size=9,
        set_size=7,
        threshold=3,
        anchor_count=2,
        outcome_multiplier=7,
        native_limit_seconds=5.0,
        external_timeout_seconds=10.0,
    )
    expected_full, expected_exclusive = r9.brute_force_official_histogram(
        tickets,
        pool_size=9,
        set_size=7,
        threshold=3,
        anchor_count=2,
    )

    assert observed["status"] == "OK"
    assert observed["subset_count"] == math.comb(9, 7)
    assert tuple(observed["full_histogram"]) == expected_full
    assert tuple(observed["anchor_exclusive_histogram"]) == expected_exclusive
    assert sum(observed["full_histogram"]) == math.comb(9, 7) * 7
    assert sum(observed["anchor_exclusive_histogram"]) == sum(expected_exclusive)


def test_joint_histogram_relaxation_matches_exhaustive_small_oracle() -> None:
    observed = r9.solve_histogram_relaxation(
        outcome_count=8,
        exact_s1=4,
        s2_lower_bound=2,
        maximum_multiplicity=3,
        native_limit_seconds=3.0,
    )
    expected = _brute_relaxation_correction(
        outcome_count=8,
        exact_s1=4,
        s2_floor=2,
        maximum_multiplicity=3,
    )

    assert observed["status"] == "OPTIMAL"
    assert observed["certified_correction_lower_bound"] == expected
    assert observed["incumbent_correction"] == expected
    histogram = observed["histogram"]
    assert histogram is not None
    assert sum(histogram) == 8
    assert sum(m * count for m, count in enumerate(histogram)) == 4
    assert sum(math.comb(m, 2) * count for m, count in enumerate(histogram)) >= 2
    moments = r9.multiplicity_moments(histogram)
    assert moments == observed["moments_of_joint_relaxation_histogram"]


def test_generated_seven_state_histograms_conserve_outcomes_and_moments() -> None:
    result = json.loads(r9.RESULT_PATH.read_text(encoding="utf-8"))
    assert result["STATE_COUNT"] == 7
    assert len(result["R3_LOAD_BEARING_STATES"]) == 7
    assert result["OUTCOME_CONSERVATION"]["official_outcomes"] == (r9.OFFICIAL_OUTCOME_COUNT)
    assert result["UPSTREAM_ARITHMETIC_AUDIT"]["exact_single_ticket_outcomes"] == 18_611_432
    assert result["UPSTREAM_ARITHMETIC_AUDIT"]["portfolio_s1_error_for_20_tickets"] == 7_807_080

    for state in result["R3_LOAD_BEARING_STATES"]:
        witness = state["witness_exact_histogram"]
        full = witness["full_portfolio_histogram"]
        exclusive = witness["anchor_exclusive_residual_histogram"]
        assert sum(full) == r9.OFFICIAL_OUTCOME_COUNT
        assert sum(exclusive) == r9.ANCHOR_EXCLUSIVE_OUTCOME_COUNT
        assert r9.multiplicity_moments(exclusive) == {
            int(order): value for order, value in witness["moments_s1_through_s18"].items()
        }
        assert witness["moments_s1_through_s18"]["1"] == state["residual_s1_exact"]
        assert witness["moments_s1_through_s18"]["2"] >= state["residual_s2_certified_lower_bound"]

        envelope = state["state_wide_joint_histogram_envelope"]
        histogram = envelope["histogram"]
        assert envelope["status"] == "OPTIMAL"
        assert histogram is not None
        assert sum(histogram) == r9.ANCHOR_EXCLUSIVE_OUTCOME_COUNT
        assert sum(m * count for m, count in enumerate(histogram)) == (state["residual_s1_exact"])
        assert (
            sum(math.comb(m, 2) * count for m, count in enumerate(histogram))
            >= state["residual_s2_certified_lower_bound"]
        )
        assert envelope["certified_correction_lower_bound"] == (envelope["incumbent_correction"])
