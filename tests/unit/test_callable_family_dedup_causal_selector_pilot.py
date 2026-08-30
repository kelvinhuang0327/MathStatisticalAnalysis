"""Focused tests for the fixed callable-family-dedup causal pilot."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any

import pytest
from tools import run_callable_family_dedup_causal_selector_pilot as pilot


def _binding(
    strategy_id: str,
    *,
    lottery_id: str = "P638",
    source_authority_id: str = "AUTH",
    native_ticket_count: int = 1,
    callable_identity: str = "callable:shared",
    strategy_version: str = "v1",
) -> pilot.CandidateBinding:
    return pilot.CandidateBinding(
        source_authority_id=source_authority_id,
        lottery_id=lottery_id,
        native_ticket_count=native_ticket_count,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        callable_identity=callable_identity,
        callable_label=f"module:{callable_identity}",
        resolution_authority="fixture",
    )


def test_authority_qualified_identity_grouping_and_static_representative() -> None:
    bindings = (_binding("z"), _binding("a"), _binding("m", callable_identity="other"))

    families = pilot.group_callable_families(bindings)

    assert len(families) == 2
    shared = next(family for family in families if family.family_key[3] == "callable:shared")
    assert [member.strategy_id for member in shared.members] == ["a", "z"]
    assert shared.representative.identity_key == ("AUTH", "P638", "a", "v1")


def test_representative_rule_has_no_performance_input_and_is_order_independent() -> None:
    bindings = (_binding("high_historical_score"), _binding("a_static_minimum"))
    external_scores = {"high_historical_score": 10_000, "a_static_minimum": -10_000}

    first = pilot.representative_identity_keys(bindings)
    external_scores = {key: -value for key, value in external_scores.items()}
    second = pilot.representative_identity_keys(tuple(reversed(bindings)))

    assert external_scores["high_historical_score"] == -10_000
    assert first == second == frozenset({("AUTH", "P638", "a_static_minimum", "v1")})


def test_p638_c01_c07_family_collapses_to_c01() -> None:
    versions = {
        "power_c01_recency_decay_1bet": "v0.1-p638-p173",
        "power_c02_gap_overdue_1bet": "v0.1-p638-p173",
        "power_c03_pair_centrality_1bet": "v0.1-p638-p176",
        "power_c04_zone_balanced_1bet": "v0.1-p638-p173",
        "power_c05_dispersion_match_1bet": "v0.1-p638-p176",
        "power_c06_regime_cusum_1bet": "v0.1-p638-p176",
        "power_c07_borda_ensemble_1bet": "v0.1-p638-p176",
    }
    bindings = tuple(
        _binding(
            strategy_id,
            source_authority_id="P638_CURRENT_REPLAY_AND_RANKING",
            callable_identity=(
                "callable-sha256:910e4d00093b63db80704405c33bac275651218096688218d9b2dd328bd2905f"
            ),
            strategy_version=versions[strategy_id],
        )
        for strategy_id in pilot.P638_C01_C07_STRATEGY_IDS
    )

    (family,) = pilot.group_callable_families(bindings)

    assert family.representative.strategy_id == "power_c01_recency_decay_1bet"
    assert len(family.members) == 7
    assert family.as_payload()["removed_sibling_count"] == 6


def test_callable_grouping_separates_cross_lottery_identities() -> None:
    bindings = (
        _binding("same", lottery_id="P638", callable_identity="callable:shared"),
        _binding("same", lottery_id="T539", callable_identity="callable:shared"),
    )

    families = pilot.group_callable_families(bindings)

    assert len(families) == 2
    assert {family.family_key[1] for family in families} == {"P638", "T539"}


def _runner() -> Any:
    return pilot.load_original_runner()


def _targets(count: int) -> tuple[Any, ...]:
    runner = _runner()
    return tuple(
        runner.TargetRef(
            draw_id=str(index + 1),
            draw_date=f"2026-{index + 1:06d}",
            order=index,
        )
        for index in range(count)
    )


def _candidate(strategy_id: str) -> Any:
    runner = _runner()
    return runner.Candidate(
        strategy_id=strategy_id,
        strategy_version="v1",
        display_name=strategy_id,
        native_ticket_count=1,
        minimum_history=0,
    )


def _outcome(strategy_id: str, target: Any, success: bool) -> Any:
    runner = _runner()
    return runner.TargetOutcome(
        strategy_id=strategy_id,
        strategy_version="v1",
        target=target,
        causal_cutoff_draw_id="0",
        causal_cutoff_date="1900-01-01",
        success=success,
        winning_ticket_count=int(success),
        ticket_count=1,
        prize_tier_counts=(int(success), 0, 0, 0),
    )


def _cell(outcomes_by_strategy: dict[str, list[bool]]) -> Any:
    runner = _runner()
    lengths = {len(outcomes) for outcomes in outcomes_by_strategy.values()}
    assert len(lengths) == 1
    targets = _targets(lengths.pop())
    outcomes = tuple(
        _outcome(strategy_id, target, success)
        for strategy_id, successes in outcomes_by_strategy.items()
        for target, success in zip(targets, successes, strict=True)
    )
    return runner.build_cell_data(
        lottery_id="T539",
        native_ticket_count=1,
        authority_targets=targets,
        candidates=tuple(_candidate(strategy_id) for strategy_id in outcomes_by_strategy),
        complete_outcomes=outcomes,
        coverage_exclusion_reason_target_ids={},
        source_authority_id="fixture",
        selection_tie_break=("STRATEGY_ID_ASC",),
    )


def test_strictly_before_target_window_excludes_current_and_future_outcomes() -> None:
    runner = _runner()
    cell = _cell({"a": [True, True, False, False], "b": [False, False, True, True]})

    evaluation = runner.evaluate_cell(cell, label="TEST", window=2)

    assert evaluation.steps[0].target.draw_id == "3"
    assert [target.draw_id for target in evaluation.steps[0].history_targets] == ["1", "2"]
    assert all(
        history.order < step.target.order
        for step in evaluation.steps
        for history in step.history_targets
    )


@pytest.mark.parametrize("window", [50, 300, 750])
def test_fixed_window_boundaries_use_exactly_w_prior_targets(window: int) -> None:
    runner = _runner()
    cell = _cell({"a": [False] * (window + 1)})

    evaluation = runner.evaluate_cell(cell, label=f"W{window}", window=window)

    assert evaluation.status == "COMPLETE"
    assert len(evaluation.steps) == 1
    assert len(evaluation.steps[0].history_targets) == window
    assert evaluation.steps[0].target.draw_id == str(window + 1)


def test_dedup_rolling_and_frozen_use_identical_original_target_set() -> None:
    runner = _runner()
    cell = _cell({"a": [True, False, True, False], "b": [False, True, False, True]})
    original = runner.evaluate_cell(cell, label="TEST", window=2)
    dedup = runner.evaluate_cell(
        replace(cell, candidates=(cell.candidates[0],)), label="TEST", window=2
    )

    assert original.rolling_target_ids == dedup.rolling_target_ids == ("3", "4")
    assert dedup.rolling_target_ids == dedup.frozen_target_ids


def test_deterministic_tie_break_runs_after_candidate_reduction() -> None:
    runner = _runner()
    cell = _cell({"z": [False, False, False], "a": [False, False, False]})

    evaluation = runner.evaluate_cell(cell, label="TEST", window=2)

    assert evaluation.frozen_strategy_id == "a"
    assert evaluation.steps[0].rolling_strategy_id == "a"


def test_missing_coverage_fails_closed() -> None:
    runner = _runner()
    targets = _targets(2)

    with pytest.raises(runner.PilotDataError, match="UNEXPLAINED_MISSING_STRATEGY_COVERAGE"):
        runner.build_cell_data(
            lottery_id="T539",
            native_ticket_count=1,
            authority_targets=targets,
            candidates=(_candidate("a"), _candidate("b")),
            complete_outcomes=(
                _outcome("a", targets[0], True),
                _outcome("a", targets[1], False),
                _outcome("b", targets[0], False),
            ),
            coverage_exclusion_reason_target_ids={},
            source_authority_id="fixture",
            selection_tie_break=("STRATEGY_ID_ASC",),
        )


def test_duplicate_replay_rows_fail_closed() -> None:
    runner = _runner()
    (target,) = _targets(1)
    duplicate = _outcome("a", target, True)

    with pytest.raises(runner.PilotDataError, match="DUPLICATE_REPLAY_ROW"):
        runner.build_cell_data(
            lottery_id="T539",
            native_ticket_count=1,
            authority_targets=(target,),
            candidates=(_candidate("a"),),
            complete_outcomes=(duplicate, duplicate),
            coverage_exclusion_reason_target_ids={},
            source_authority_id="fixture",
            selection_tie_break=("STRATEGY_ID_ASC",),
        )


def test_deterministic_family_payload_and_canonical_output() -> None:
    forward = pilot.group_callable_families((_binding("z"), _binding("a")))
    reverse = pilot.group_callable_families((_binding("a"), _binding("z")))
    first = {"families": [family.as_payload() for family in forward], "status": "COMPLETE"}
    second = {"status": "COMPLETE", "families": [family.as_payload() for family in reverse]}

    first_bytes = pilot.canonical_json_bytes(first)
    second_bytes = pilot.canonical_json_bytes(second)

    assert first_bytes == second_bytes
    assert first_bytes.endswith(b"\n")
    assert hashlib.sha256(first_bytes).hexdigest() == hashlib.sha256(second_bytes).hexdigest()
