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
    assert_causal_history,
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
