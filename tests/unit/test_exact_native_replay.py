"""Unit tests for the canonicalized exact-native BIG_LOTTO replay engine.

Uses the lower-level engine functions directly (catalog/draw-authority/
binding/cell), not :func:`replay_exact_native_target_range` -- that
orchestration also calls ``source_freeze``, which requires a clean git tree
and would make these tests fail during ordinary iteration on this task's own
branch. Git-tree-identity behavior is exercised by the integration suite
instead.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import cast

import pytest

from lottolab.application.use_cases.replay_exact_native_targets import (
    catalog_freeze,
    causal_row,
    load_authoritative_draws,
    replay_cell,
    runtime_bindings,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import (
    Draw,
    ExactNativeReplayError,
    WindowReaggregationEligibility,
    assert_causal_history,
    evaluate_window_reaggregation_eligibility,
    exact_native_descriptors,
    freeze_visible_draws,
    window_names_for_target,
)
from lottolab.domain.exact_native_replay import target_windows as compute_target_windows
from lottolab.domain.strategies import LifecycleStatus, ResponseShape, StrategyDescriptor
from lottolab.evidence.exact_native_replay_manifest import (
    canonical_json_bytes,
    history_fingerprint,
)
from lottolab.infrastructure.persistence.draw_schema import resolve_local_data_paths

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "replay"
    / "biglotto_exact_native_115000083_parity_slice.jsonl"
)
RUN_ID = "B649_K5_K10_K20_EXACT_NATIVE_REFRESH_115000083_R1"
MAX_VISIBLE_DRAW = "115000083"
EXPECTED_MAIN_NUMBERS = (9, 20, 23, 26, 36, 44)
EXPECTED_SPECIAL_NUMBER = 4


def _draw_data_path() -> Path:
    return resolve_local_data_paths().database


draw_authority_present = pytest.mark.skipif(
    not _draw_data_path().is_file(),
    reason="the real LottoLab draw-authority database is not present on this machine",
)


def _current_universe() -> tuple[Draw, ...]:
    loaded_draws, _authority = load_authoritative_draws(_draw_data_path())
    return freeze_visible_draws(
        loaded_draws,
        max_visible_draw=MAX_VISIBLE_DRAW,
        expected_main_numbers=EXPECTED_MAIN_NUMBERS,
        expected_special_number=EXPECTED_SPECIAL_NUMBER,
    )


# --- domain pure-function tests ---------------------------------------------


def _descriptor(**overrides: object) -> StrategyDescriptor:
    fields: dict[str, object] = {
        "strategy_id": "test__strategy__1",
        "strategy_name": "Test",
        "version": "v0.1",
        "lottery_types": (LotteryType.BIG_LOTTO,),
        "lifecycle_status": LifecycleStatus.ONLINE,
        "executable": True,
        "adapter_path": "lottolab.strategies.adapters.base:PortfolioBetAdapter",
        "response_shape": ResponseShape.PORTFOLIO,
        "native_ticket_count": 10,
    }
    fields.update(overrides)
    return StrategyDescriptor(**fields)  # type: ignore[arg-type]


def test_exact_native_descriptors_excludes_ranged_bounds_like_evolution_engine() -> None:
    """A variable-bounds strategy (Evolution Engine's real shape: bounds (1, 10),
    native_ticket_count 10) must never qualify for any fixed ticket count."""

    fixed = _descriptor(strategy_id="fixed_k10")
    ranged = _descriptor(
        strategy_id="ranged_k1_to_10",
        minimum_native_ticket_count=1,
        maximum_native_ticket_count=10,
    )
    result = exact_native_descriptors((fixed, ranged), native_ticket_counts=(5, 10, 20))
    assert [d.strategy_id for d in result] == ["fixed_k10"]


def test_exact_native_descriptors_excludes_single_ticket_and_wrong_count() -> None:
    single_ticket = _descriptor(
        strategy_id="single", response_shape=ResponseShape.SINGLE_TICKET, native_ticket_count=1
    )
    wrong_count = _descriptor(strategy_id="k7", native_ticket_count=7)
    ok = _descriptor(strategy_id="k5", native_ticket_count=5)
    result = exact_native_descriptors(
        (single_ticket, wrong_count, ok), native_ticket_counts=(5, 10, 20)
    )
    assert [d.strategy_id for d in result] == ["k5"]


def test_assert_causal_history_rejects_history_at_or_after_target() -> None:
    earlier = Draw("1", date(2020, 1, 1), (1, 2, 3, 4, 5, 6), 7)
    target = Draw("2", date(2020, 1, 2), (1, 2, 3, 4, 5, 6), 7)
    same_date = Draw("2", date(2020, 1, 2), (1, 2, 3, 4, 5, 6), 7)

    assert_causal_history(target, (earlier,))
    with pytest.raises(ExactNativeReplayError):
        assert_causal_history(target, (earlier, same_date))


def test_freeze_visible_draws_enforces_identity_guard() -> None:
    draws = (
        Draw("1", date(2020, 1, 1), (1, 2, 3, 4, 5, 6), 7),
        Draw("2", date(2020, 1, 2), (2, 3, 4, 5, 6, 7), 8),
        Draw("3", date(2020, 1, 3), (3, 4, 5, 6, 7, 8), 9),
    )
    visible = freeze_visible_draws(
        draws,
        max_visible_draw="2",
        expected_main_numbers=(2, 3, 4, 5, 6, 7),
        expected_special_number=8,
    )
    assert [d.draw_number for d in visible] == ["1", "2"]

    with pytest.raises(ExactNativeReplayError):
        freeze_visible_draws(
            draws,
            max_visible_draw="2",
            expected_main_numbers=(9, 9, 9, 9, 9, 9),
            expected_special_number=8,
        )


def test_target_windows_and_window_names_for_target() -> None:
    draws = tuple(
        Draw(str(i), date(2020, 1, 1) + timedelta(days=i), (1, 2, 3, 4, 5, 6), 7) for i in range(5)
    )
    windows = compute_target_windows(
        draws, window_order=("FULL", "RECENT_2"), window_sizes={"FULL": None, "RECENT_2": 2}
    )
    assert windows["FULL"]["observations_required"] == 5
    assert windows["RECENT_2"]["observations_required"] == 2
    assert windows["RECENT_2"]["draw_numbers"] == ["3", "4"]

    names_last = window_names_for_target(draws[-1], windows)
    assert set(names_last) == {"FULL", "RECENT_2"}
    names_first = window_names_for_target(draws[0], windows)
    assert names_first == ["FULL"]


def test_target_windows_cutoff_forward_regression_evicts_lower_bound() -> None:
    """Advancing the cutoff by one draw must evict exactly the old lower-bound
    member and add the new draw, for every fixed-size RECENT window, while
    FULL only grows. This is the @115000083 -> @115000084 rolling-window
    contract the K10 exact-native replay family depends on."""

    draws = tuple(
        Draw(str(i), date(2020, 1, 1) + timedelta(days=i), (1, 2, 3, 4, 5, 6), 7)
        for i in range(10)
    )
    window_order = ("FULL", "RECENT_4", "RECENT_2")
    window_sizes = {"FULL": None, "RECENT_4": 4, "RECENT_2": 2}

    windows_before = compute_target_windows(
        draws[:-1], window_order=window_order, window_sizes=window_sizes
    )
    windows_after = compute_target_windows(
        draws, window_order=window_order, window_sizes=window_sizes
    )

    new_draw = draws[-1].draw_number
    for name, size in (("RECENT_2", 2), ("RECENT_4", 4)):
        members_before = set(cast(list[str], windows_before[name]["draw_numbers"]))
        members_after = set(cast(list[str], windows_after[name]["draw_numbers"]))
        assert len(members_before) == size
        assert len(members_after) == size
        evicted = members_before - members_after
        added = members_after - members_before
        assert added == {new_draw}
        assert len(evicted) == 1
        assert (members_before - evicted) | added == members_after

        # Rolling-window invariant: actual_members == expected current-cutoff members
        expected_current = {draw.draw_number for draw in draws[-size:]}
        assert members_after == expected_current

    full_before = set(cast(list[str], windows_before["FULL"]["draw_numbers"]))
    full_after = set(cast(list[str], windows_after["FULL"]["draw_numbers"]))
    assert full_after - full_before == {new_draw}
    assert full_before - full_after == set()
    assert len(full_after) == len(full_before) + 1


def test_target_windows_rolling_invariants_and_stale_window_names() -> None:
    """Fixed RECENT_N membership is derived from the CURRENT cutoff:
    - len(new_members) == N
    - actual_members == expected current-cutoff members
    - coverage <= 1
    - unavailable_or_failure_count >= 0
    - stale persisted window_names on evidence rows are not current membership authority.
    """
    draws = tuple(
        Draw(str(i), date(2020, 1, 1) + timedelta(days=i), (1, 2, 3, 4, 5, 6), 7)
        for i in range(10)
    )
    window_sizes = {"FULL": None, "RECENT_4": 4, "RECENT_2": 2}
    windows_c = compute_target_windows(
        draws[:-1], window_order=("FULL", "RECENT_4", "RECENT_2"), window_sizes=window_sizes
    )
    windows_c_plus_1 = compute_target_windows(
        draws, window_order=("FULL", "RECENT_4", "RECENT_2"), window_sizes=window_sizes
    )

    recent_2_c = cast(list[str], windows_c["RECENT_2"]["draw_numbers"])
    recent_2_c_plus_1 = cast(list[str], windows_c_plus_1["RECENT_2"]["draw_numbers"])
    # In cutoff C, draw 7 was in RECENT_2:
    assert "7" in recent_2_c
    # In cutoff C+1, draw 7 was evicted from RECENT_2:
    assert "7" not in recent_2_c_plus_1
    assert recent_2_c_plus_1 == ["8", "9"]

    # Suppose a row was generated under cutoff C with stale window_names: ["RECENT_2", "FULL"]
    stale_row = {
        "target_draw_number": "7",
        "replay_status": "EXECUTION_FAILURE",
        "reason": "Old failure",
        "window_names": ["FULL", "RECENT_2"],  # stale!
    }
    current_rows = [
        stale_row,
        {"target_draw_number": "8", "replay_status": "COMPLETE"},
        {"target_draw_number": "9", "replay_status": "COMPLETE"},
    ]

    recent_2_draws = cast(list[str], windows_c_plus_1["RECENT_2"]["draw_numbers"])
    eligibility = evaluate_window_reaggregation_eligibility(
        window_name="RECENT_2",
        window_draw_numbers=recent_2_draws,
        evidence_rows=current_rows,
    )
    # Stale window_names did NOT cause draw 7 to be included in RECENT_2
    assert isinstance(eligibility, WindowReaggregationEligibility)
    assert eligibility.metric_status == "AVAILABLE"
    assert eligibility.rankable is True
    assert eligibility.failure_count == 0
    assert eligibility.available_observation_count == 2
    assert eligibility.requested_draw_count == 2
    assert eligibility.coverage <= 1.0
    assert eligibility.failure_count >= 0


def test_window_reaggregation_execution_failure_inside_window_invalidates() -> None:
    """EXECUTION_FAILURE inside window => metric_status = UNAVAILABLE, rankable = False."""
    rows = [
        {"target_draw_number": "8", "replay_status": "COMPLETE"},
        {
            "target_draw_number": "9",
            "replay_status": "EXECUTION_FAILURE",
            "reason": "InvalidOutput: fewer than six legal candidates",
        },
    ]
    eligibility = evaluate_window_reaggregation_eligibility(
        window_name="RECENT_2",
        window_draw_numbers=["8", "9"],
        evidence_rows=rows,
    )
    assert eligibility.metric_status == "UNAVAILABLE"
    assert eligibility.rankable is False
    assert eligibility.unavailable_reason == "InvalidOutput: fewer than six legal candidates"
    assert eligibility.failure_count == 1
    assert eligibility.available_observation_count == 1
    assert eligibility.coverage <= 1.0


def test_window_reaggregation_failure_outside_window_leaves_unaffected_window_available() -> None:
    """FULL-only historical EXECUTION_FAILURE does not invalidate an unaffected RECENT window."""
    rows = [
        {
            "target_draw_number": "2",
            "replay_status": "EXECUTION_FAILURE",
            "reason": "Historical donor crash",
        },
        {"target_draw_number": "8", "replay_status": "COMPLETE"},
        {"target_draw_number": "9", "replay_status": "COMPLETE"},
    ]
    full_eligibility = evaluate_window_reaggregation_eligibility(
        window_name="FULL",
        window_draw_numbers=[str(i) for i in range(10)],
        evidence_rows=rows,
    )
    recent_eligibility = evaluate_window_reaggregation_eligibility(
        window_name="RECENT_2",
        window_draw_numbers=["8", "9"],
        evidence_rows=rows,
    )

    # FULL contains target 2 -> UNAVAILABLE
    assert full_eligibility.metric_status == "UNAVAILABLE"
    assert full_eligibility.rankable is False
    assert full_eligibility.failure_count == 1

    # RECENT_2 contains only targets 8 and 9 -> AVAILABLE
    assert recent_eligibility.metric_status == "AVAILABLE"
    assert recent_eligibility.rankable is True
    assert recent_eligibility.failure_count == 0
    assert recent_eligibility.unavailable_reason is None
    assert recent_eligibility.available_observation_count == 2
    assert recent_eligibility.coverage == 1.0


def test_window_reaggregation_incomplete_observations_benign_exclusion() -> None:
    """WINDOW_INELIGIBLE_INCOMPLETE_OBSERVATIONS excludes observations from denominator
    without marking the window UNAVAILABLE."""
    rows = [
        {
            "target_draw_number": "8",
            "replay_status": "WINDOW_INELIGIBLE_INCOMPLETE_OBSERVATIONS",
            "reason": "InsufficientHistory: required 10, got 8",
        },
        {"target_draw_number": "9", "replay_status": "COMPLETE"},
    ]
    eligibility = evaluate_window_reaggregation_eligibility(
        window_name="RECENT_2",
        window_draw_numbers=["8", "9"],
        evidence_rows=rows,
    )
    assert eligibility.metric_status == "AVAILABLE"
    assert eligibility.rankable is True
    assert eligibility.failure_count == 0
    assert eligibility.excluded_observation_count == 1
    assert eligibility.available_observation_count == 1
    assert eligibility.requested_draw_count == 2
    # denominator = 2 - 1 = 1, available = 1, coverage = 1.0 <= 1.0
    assert eligibility.coverage == 1.0


def test_window_reaggregation_not_globally_cached_per_strategy() -> None:
    """Availability is evaluated per strategy x window and never cached globally."""
    rows = [
        {"target_draw_number": "1", "replay_status": "EXECUTION_FAILURE", "reason": "Err"},
        {"target_draw_number": "2", "replay_status": "COMPLETE"},
    ]
    res1 = evaluate_window_reaggregation_eligibility(
        window_name="W1",
        window_draw_numbers=["1", "2"],
        evidence_rows=rows,
    )
    assert res1.metric_status == "UNAVAILABLE"

    res2 = evaluate_window_reaggregation_eligibility(
        window_name="W2",
        window_draw_numbers=["2"],
        evidence_rows=rows,
    )
    assert res2.metric_status == "AVAILABLE"
    assert res2.rankable is True


# --- deterministic serialization --------------------------------------------


def test_canonical_json_bytes_is_stable_and_key_order_independent() -> None:
    built_one_order = {"b": 2, "a": 1, "c": None}
    built_other_order = {"a": 1, "c": None, "b": 2}
    bytes_one = canonical_json_bytes(built_one_order)
    bytes_other = canonical_json_bytes(built_other_order)
    assert bytes_one == bytes_other
    assert bytes_one.endswith(b"\n")
    assert b'"c":null' in bytes_one


def test_history_fingerprint_matches_fixtures_empty_history_row() -> None:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        first_row = json.loads(handle.readline())
    assert first_row["causal_history_length"] == 0
    assert history_fingerprint(()) == first_row["causal_history_fingerprint"]


@draw_authority_present
def test_replay_cell_is_deterministic_across_repeated_calls() -> None:
    descriptors, _universe = catalog_freeze()
    bindings = runtime_bindings(descriptors)
    all_draws = _current_universe()
    windows = compute_target_windows(all_draws)
    target_index = min(500, len(all_draws) - 1)
    target = all_draws[target_index]
    history = all_draws[:target_index]
    causal_rows = tuple(causal_row(d) for d in history)
    fingerprint = history_fingerprint(history)
    binding = bindings[0]

    row_a = replay_cell(
        binding,
        target,
        history,
        windows,
        RUN_ID,
        causal_rows=causal_rows,
        history_fingerprint=fingerprint,
    )
    row_b = replay_cell(
        binding,
        target,
        history,
        windows,
        RUN_ID,
        causal_rows=causal_rows,
        history_fingerprint=fingerprint,
    )
    assert canonical_json_bytes(row_a) == canonical_json_bytes(row_b)


# --- real-catalog behavior tests ---------------------------------------------


def test_current_exact_native_universe_is_seven_bindings_without_evolution_engine() -> None:
    descriptors, universe = catalog_freeze()
    assert len(descriptors) == 7
    strategy_ids = {descriptor.strategy_id for descriptor in descriptors}
    assert "legacy_biglotto__evolution_engine__3df019c31ce4" not in strategy_ids
    k5_count = cast(int, universe["k5_count"])
    k10_count = cast(int, universe["k10_count"])
    k20_count = cast(int, universe["k20_count"])
    assert k5_count + k10_count + k20_count == 7


def test_all_seven_bindings_load_without_error() -> None:
    descriptors, _universe = catalog_freeze()
    bindings = runtime_bindings(descriptors)
    assert len(bindings) == 7
    assert all(binding.binding_error is None for binding in bindings)


# --- monkeypatch unreachability ----------------------------------------------


@draw_authority_present
def test_evolution_engine_monkeypatch_targets_unreachable_over_fixture() -> None:
    """Falsifiable sentinel trace: every symbol the donor's
    ``_apply_runtime_optimizations()`` historically rebound on
    ``biglotto_batch16`` must see zero calls while replaying all 7 current
    bindings over the fixture's 20 targets. The exact-native filter
    structurally excludes Evolution Engine (see
    ``test_exact_native_descriptors_excludes_ranged_bounds_like_evolution_engine``),
    so this proves it, rather than merely inferring it."""

    import lottolab.strategies.adapters.biglotto_batch16 as b16

    sentinel_names = [
        "_evo_fourier_phase",
        "_evo_lag_autocorrelation",
        "_evo_frequency",
        "_evo_co_occurrence",
        "_evo_markov_transition",
        "_evo_deviation_score",
        "_evo_consecutive_pairs",
        "_evo_sum_trend",
        "_evo_hot_cold_score",
        "_evo_gap_pressure",
    ]
    call_counts: dict[str, int] = dict.fromkeys(sentinel_names, 0)
    call_counts["evaluate_population"] = 0
    originals = {name: getattr(b16, name) for name in sentinel_names}
    # Reaching into a private class to instrument it is exactly what this
    # falsifiability test requires; pyright's private-usage/signature checks
    # do not apply to deliberate, scoped monkeypatching for tracing.
    original_evaluate_population = b16._EvolutionEngine.evaluate_population  # pyright: ignore[reportPrivateUsage]

    def _make_wrapper(name: str, original: object):
        def wrapper(*args: object, **kwargs: object) -> object:
            call_counts[name] += 1
            return original(*args, **kwargs)  # type: ignore[operator]

        return wrapper

    def _wrapped_evaluate_population(self: object, *args: object, **kwargs: object) -> object:
        call_counts["evaluate_population"] += 1
        return original_evaluate_population(self, *args, **kwargs)  # pyright: ignore[reportArgumentType]

    for name in sentinel_names:
        setattr(b16, name, _make_wrapper(name, originals[name]))
    b16._EvolutionEngine.evaluate_population = _wrapped_evaluate_population  # pyright: ignore[reportPrivateUsage, reportAttributeAccessIssue]

    try:
        descriptors, _universe = catalog_freeze()
        bindings = runtime_bindings(descriptors)
        all_draws = _current_universe()
        windows = compute_target_windows(all_draws)
        target_indices = list(range(10)) + list(range(len(all_draws) - 10, len(all_draws)))
        for target_index in target_indices:
            target = all_draws[target_index]
            history = all_draws[:target_index]
            causal_rows = tuple(causal_row(d) for d in history)
            fingerprint = history_fingerprint(history)
            for binding in bindings:
                replay_cell(
                    binding,
                    target,
                    history,
                    windows,
                    RUN_ID,
                    causal_rows=causal_rows,
                    history_fingerprint=fingerprint,
                )
    finally:
        for name in sentinel_names:
            setattr(b16, name, originals[name])
        b16._EvolutionEngine.evaluate_population = original_evaluate_population  # pyright: ignore[reportPrivateUsage]

    for name, count in call_counts.items():
        assert count == 0, f"{name} was called {count} times; monkeypatch target reachable"
