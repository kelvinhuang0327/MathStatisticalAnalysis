"""Focused causal and determinism checks for the rolling-selector pilot."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from tools import run_strategy_matrix_causal_rolling_selector_pilot as pilot


def _targets(count: int) -> tuple[pilot.TargetRef, ...]:
    return tuple(
        pilot.TargetRef(
            draw_id=str(index + 1),
            draw_date=f"2026-01-{index + 1:02d}",
            order=index,
        )
        for index in range(count)
    )


def _candidate(strategy_id: str) -> pilot.Candidate:
    return pilot.Candidate(
        strategy_id=strategy_id,
        strategy_version="v1",
        display_name=strategy_id,
        native_ticket_count=1,
        minimum_history=0,
    )


def _outcome(
    strategy_id: str,
    target: pilot.TargetRef,
    success: bool,
    *,
    cutoff: pilot.TargetRef | None = None,
) -> pilot.TargetOutcome:
    cutoff_target = cutoff or pilot.TargetRef(
        draw_id=str(target.order),
        draw_date=f"2025-12-{target.order + 1:02d}",
        order=target.order - 1,
    )
    return pilot.TargetOutcome(
        strategy_id=strategy_id,
        strategy_version="v1",
        target=target,
        causal_cutoff_draw_id=cutoff_target.draw_id,
        causal_cutoff_date=cutoff_target.draw_date,
        success=success,
        winning_ticket_count=int(success),
        ticket_count=1,
        prize_tier_counts=(int(success), 0, 0, 0),
    )


def _cell(
    a: list[bool],
    b: list[bool],
    *,
    missing_b: set[int] | None = None,
) -> pilot.CellData:
    targets = _targets(len(a))
    missing = missing_b or set()
    outcomes = [
        *(_outcome("a", target, success) for target, success in zip(targets, a, strict=True)),
        *(
            _outcome("b", target, success)
            for index, (target, success) in enumerate(zip(targets, b, strict=True))
            if index not in missing
        ),
    ]
    return pilot.build_cell_data(
        lottery_id="T539",
        native_ticket_count=1,
        authority_targets=targets,
        candidates=(_candidate("a"), _candidate("b")),
        complete_outcomes=outcomes,
        coverage_exclusion_reason_target_ids={
            "EXPLICIT_MISSING_COVERAGE": {targets[index].draw_id for index in missing}
        },
        source_authority_id="fixture",
        selection_tie_break=("STRATEGY_ID_ASC",),
    )


def test_exact_prior_window_boundary_and_first_eligible_target() -> None:
    cell = _cell([True, True, False, False], [False, False, True, True])

    evaluation = pilot.evaluate_cell(cell, label="TEST", window=2)

    assert evaluation.status == "COMPLETE"
    assert evaluation.steps[0].target.draw_id == "3"
    assert [target.draw_id for target in evaluation.steps[0].history_targets] == ["1", "2"]
    assert all(len(step.history_targets) == 2 for step in evaluation.steps)


def test_current_target_outcome_cannot_influence_its_selection() -> None:
    cell = _cell([True, True, False, False], [False, False, True, True])
    changed = _cell([True, True, True, False], [False, False, False, True])

    original = pilot.evaluate_cell(cell, label="TEST", window=2)
    mutated = pilot.evaluate_cell(changed, label="TEST", window=2)

    assert original.steps[0].rolling_strategy_id == mutated.steps[0].rolling_strategy_id
    assert original.steps[0].history_targets == mutated.steps[0].history_targets


def test_future_target_outcome_cannot_influence_earlier_selections() -> None:
    cell = _cell([True, True, False, False, False], [False, False, True, True, True])
    future_changed = _cell(
        [True, True, False, False, True],
        [False, False, True, True, False],
    )

    original = pilot.evaluate_cell(cell, label="TEST", window=2)
    mutated = pilot.evaluate_cell(future_changed, label="TEST", window=2)

    assert [step.rolling_strategy_id for step in original.steps[:-1]] == [
        step.rolling_strategy_id for step in mutated.steps[:-1]
    ]


def test_deterministic_tie_break_uses_ascending_strategy_id() -> None:
    cell = _cell([False, False, False], [False, False, False])

    evaluation = pilot.evaluate_cell(cell, label="TEST", window=2)

    assert evaluation.frozen_strategy_id == "a"
    assert evaluation.steps[0].rolling_strategy_id == "a"


def test_rolling_and_frozen_use_the_identical_target_set() -> None:
    evaluation = pilot.evaluate_cell(
        _cell([True, False, True, False], [False, True, False, True]),
        label="TEST",
        window=2,
    )

    assert evaluation.rolling_target_ids == evaluation.frozen_target_ids == ("3", "4")
    payload = pilot.experiment_payload(evaluation)
    assert payload["rolling_frozen_identical_target_set"] is True


def test_selector_switch_count_and_frequency_are_exact() -> None:
    evaluation = pilot.evaluate_cell(
        _cell(
            [True, True, False, False, False],
            [False, False, True, True, True],
        ),
        label="TEST",
        window=2,
    )

    assert [step.rolling_strategy_id for step in evaluation.steps] == ["a", "a", "b"]
    payload = pilot.experiment_payload(evaluation)
    assert payload["rolling_strategy_switch_count"] == 1
    assert payload["rolling_selection_frequency"] == {"a": 2, "b": 1}


def test_missing_strategy_coverage_is_explicit_and_fixed() -> None:
    cell = _cell(
        [True, False, True, False],
        [False, True, False, True],
        missing_b={1},
    )

    assert [target.draw_id for target in cell.comparable_targets] == ["1", "3", "4"]
    payload = pilot.experiment_payload(
        pilot.evaluate_cell(cell, label="TEST", window=2)
    )
    coverage = payload["coverage"]
    assert isinstance(coverage, dict)
    assert coverage["coverage_excluded_missing_target_count"] == 1
    assert coverage["coverage_exclusion_reason_target_counts"] == {
        "EXPLICIT_MISSING_COVERAGE": 1
    }


def test_unexplained_missing_strategy_coverage_fails_closed() -> None:
    targets = _targets(2)
    with pytest.raises(pilot.PilotDataError, match="UNEXPLAINED_MISSING_STRATEGY_COVERAGE"):
        pilot.build_cell_data(
            lottery_id="T539",
            native_ticket_count=1,
            authority_targets=targets,
            candidates=(_candidate("a"), _candidate("b")),
            complete_outcomes=(
                _outcome("a", targets[0], True),
                _outcome("a", targets[1], True),
                _outcome("b", targets[0], False),
            ),
            coverage_exclusion_reason_target_ids={},
            source_authority_id="fixture",
            selection_tie_break=("STRATEGY_ID_ASC",),
        )


def test_duplicate_replay_rows_fail_closed() -> None:
    targets = _targets(2)
    duplicate = _outcome("a", targets[0], True)
    with pytest.raises(pilot.PilotDataError, match="DUPLICATE_REPLAY_ROW"):
        pilot.build_cell_data(
            lottery_id="T539",
            native_ticket_count=1,
            authority_targets=targets,
            candidates=(_candidate("a"),),
            complete_outcomes=(duplicate, duplicate),
            coverage_exclusion_reason_target_ids={"MISSING": {"2"}},
            source_authority_id="fixture",
            selection_tie_break=("STRATEGY_ID_ASC",),
        )


def test_non_monotonic_strategy_rows_fail_closed() -> None:
    targets = _targets(2)
    with pytest.raises(pilot.PilotDataError, match="NON_MONOTONIC_TARGET_ORDER"):
        pilot.build_cell_data(
            lottery_id="T539",
            native_ticket_count=1,
            authority_targets=targets,
            candidates=(_candidate("a"),),
            complete_outcomes=(
                _outcome("a", targets[1], True),
                _outcome("a", targets[0], True),
            ),
            coverage_exclusion_reason_target_ids={},
            source_authority_id="fixture",
            selection_tie_break=("STRATEGY_ID_ASC",),
        )


def test_causal_cutoff_at_current_target_fails_closed() -> None:
    targets = _targets(1)
    leaked = replace(
        _outcome("a", targets[0], True),
        causal_cutoff_draw_id=targets[0].draw_id,
        causal_cutoff_date=targets[0].draw_date,
    )
    with pytest.raises(pilot.PilotDataError, match="CAUSAL_HISTORY_LEAKAGE"):
        pilot.build_cell_data(
            lottery_id="T539",
            native_ticket_count=1,
            authority_targets=targets,
            candidates=(_candidate("a"),),
            complete_outcomes=(leaked,),
            coverage_exclusion_reason_target_ids={},
            source_authority_id="fixture",
            selection_tie_break=("STRATEGY_ID_ASC",),
        )


def test_insufficient_window_is_explicitly_excluded() -> None:
    evaluation = pilot.evaluate_cell(
        _cell([True, False], [False, True]), label="LONG", window=2
    )
    payload = pilot.experiment_payload(evaluation)

    assert evaluation.status == "EXCLUDED"
    assert payload["required_comparable_target_count"] == 3
    assert payload["rolling_selector_primary_metric_result"] is None


def test_deterministic_rerun_and_canonical_serialization() -> None:
    cell = _cell([True, True, False, False], [False, False, True, True])
    first = pilot.experiment_payload(
        pilot.evaluate_cell(cell, label="TEST", window=2)
    )
    second = pilot.experiment_payload(
        pilot.evaluate_cell(cell, label="TEST", window=2)
    )

    assert first == second
    assert pilot.canonical_json_bytes(first) == pilot.canonical_json_bytes(second)
    assert pilot.canonical_json_bytes(cast_mapping(first)).endswith(b"\n")


def cast_mapping(value: dict[str, Any]) -> dict[str, Any]:
    return value
