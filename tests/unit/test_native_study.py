"""Focused contract tests for the native finite-candidate Study/Trial runner."""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction

import pytest

from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessDrawIdentity,
    HistoricalPrefixTemporalHoldoutSplit,
)
from lottolab.evidence import canonical_json
from lottolab.research.base_method_evaluation import (
    BASE_METHOD_EVALUATOR_SEMANTIC_VERSION,
    ExposureKind,
    HitTierDefinition,
    LotteryMatchContract,
    MethodDrawObservation,
    MethodExposure,
    MethodIdentity,
    MethodTargetCoverage,
    OutputShape,
    ReplayStatus,
    WindowKind,
    evaluate_method,
)
from lottolab.research.native_study import (
    CanonicalValue,
    EvaluationValueField,
    ExactObjectiveValue,
    FrozenWinnerIdentity,
    NativeStudyContractError,
    NoCompletedTrialError,
    ObjectiveDirection,
    ObjectiveSpec,
    StudyResult,
    StudySpec,
    TrialEvaluation,
    TrialPruned,
    TrialSpec,
    TrialState,
    run_study,
)


def _observation(draw_number: int, *, hits: int = 0) -> MethodDrawObservation:
    return MethodDrawObservation(
        draw_id=str(draw_number),
        draw_date=f"2026-01-{draw_number:02d}",
        native_ticket_count=1,
        distinct_ticket_count=1,
        main_hit_counts=(hits,),
    )


def _observations(*draw_numbers: int, hits: int = 0) -> tuple[MethodDrawObservation, ...]:
    return tuple(_observation(item, hits=hits) for item in draw_numbers)


def _identity(observation: MethodDrawObservation) -> HistoricalPrefixSuccessDrawIdentity:
    draw_number = int(observation.draw_id)
    return HistoricalPrefixSuccessDrawIdentity(
        draw_number=draw_number,
        draw_date=observation.draw_date,
        draw_sha256=f"{draw_number:064x}",
    )


def _split(
    discovery: tuple[MethodDrawObservation, ...],
    confirmation: tuple[MethodDrawObservation, ...],
) -> HistoricalPrefixTemporalHoldoutSplit:
    return HistoricalPrefixTemporalHoldoutSplit(
        split_method="SYNTHETIC_FIXED_TEMPORAL_HOLDOUT",
        total_assignment_count=len(discovery) + len(confirmation),
        warmup_count=0,
        discovery_count=len(discovery),
        confirmation_count=len(confirmation),
        discovery_first_target=_identity(discovery[0]),
        discovery_last_target=_identity(discovery[-1]),
        confirmation_first_target=_identity(confirmation[0]),
        confirmation_last_target=_identity(confirmation[-1]),
    )


def _spec(
    discovery: tuple[MethodDrawObservation, ...],
    confirmation: tuple[MethodDrawObservation, ...],
    *,
    objectives: tuple[ObjectiveSpec, ...] | None = None,
    candidate_ids: tuple[str, ...] = ("candidate-a", "candidate-b", "candidate-c"),
    full_history_metadata: Mapping[str, CanonicalValue] | None = None,
) -> StudySpec:
    return StudySpec(
        study_id="synthetic-study-r1",
        objectives=(
            ObjectiveSpec("success_rate", ObjectiveDirection.MAXIMIZE),
        )
        if objectives is None
        else objectives,
        trials=tuple(
            TrialSpec(candidate_id, {"candidate_rank": index})
            for index, candidate_id in enumerate(candidate_ids, start=1)
        ),
        temporal_holdout_split=_split(discovery, confirmation),
        full_history_metadata=(
            {"description": "descriptive-only"}
            if full_history_metadata is None
            else full_history_metadata
        ),
    )


def _run_with_scores(
    scores: dict[str, tuple[ExactObjectiveValue, ...]],
    *,
    objectives: tuple[ObjectiveSpec, ...] | None = None,
    discovery: tuple[MethodDrawObservation, ...] | None = None,
    confirmation: tuple[MethodDrawObservation, ...] | None = None,
    full_history_metadata: Mapping[str, CanonicalValue] | None = None,
) -> StudyResult:
    resolved_discovery = _observations(1, 2, 3) if discovery is None else discovery
    resolved_confirmation = _observations(4, 5) if confirmation is None else confirmation
    spec = _spec(
        resolved_discovery,
        resolved_confirmation,
        objectives=objectives,
        full_history_metadata=full_history_metadata,
    )

    def evaluate_discovery(
        trial: TrialSpec, observations: tuple[MethodDrawObservation, ...]
    ) -> TrialEvaluation:
        assert observations is resolved_discovery
        return TrialEvaluation(
            scores[trial.candidate_id],
            {"descriptive_candidate": trial.candidate_id},
        )

    # Keep confirmation objective arity independent of the observation count.
    def fixed_confirmation(
        winner: FrozenWinnerIdentity,
        observations: tuple[MethodDrawObservation, ...],
    ) -> TrialEvaluation:
        assert observations is resolved_confirmation
        total_hits = sum(sum(item.main_hit_counts) for item in observations)
        value = ExactObjectiveValue(total_hits, max(1, len(observations) * 6))
        return TrialEvaluation(
            tuple(value for _ in spec.objectives),
            {"confirmed_candidate": winner.candidate_id},
        )

    return run_study(
        spec,
        discovery_observations=resolved_discovery,
        confirmation_observations=resolved_confirmation,
        evaluate_discovery=evaluate_discovery,
        evaluate_confirmation=fixed_confirmation,
    )


def test_repeated_identical_execution_has_identical_json_and_sha256() -> None:
    scores = {
        "candidate-a": (ExactObjectiveValue(1, 3),),
        "candidate-b": (ExactObjectiveValue(3, 4),),
        "candidate-c": (ExactObjectiveValue(1, 2),),
    }

    first = _run_with_scores(scores)
    second = _run_with_scores(scores)

    assert first == second
    assert first.canonical_json() == second.canonical_json()
    assert first.sha256 == second.sha256
    assert len(first.sha256) == 64
    assert first.sha256 == canonical_json.sha256_hex(first.canonical_json().encode("utf-8"))
    assert canonical_json.loads_canonical(first.canonical_json()) == first.canonical_dict()


def test_explicit_objective_order_then_canonical_candidate_id_breaks_ties() -> None:
    objectives = (
        ObjectiveSpec("primary", ObjectiveDirection.MAXIMIZE),
        ObjectiveSpec("cost", ObjectiveDirection.MINIMIZE),
    )
    scores = {
        "candidate-a": (ExactObjectiveValue(3, 4), ExactObjectiveValue(1, 4)),
        "candidate-b": (ExactObjectiveValue(3, 4), ExactObjectiveValue(1, 4)),
        "candidate-c": (ExactObjectiveValue(2, 3), ExactObjectiveValue(0)),
    }

    result = _run_with_scores(scores, objectives=objectives)

    assert result.winner.candidate_id == "candidate-a"
    assert result.winner.discovery_objective_values == (
        Fraction(3, 4),
        Fraction(1, 4),
    )


def test_failure_and_pruning_are_retained_in_canonical_trial_order() -> None:
    discovery = _observations(1, 2, 3)
    confirmation = _observations(4, 5)
    spec = _spec(discovery, confirmation)

    def evaluate_discovery(
        trial: TrialSpec, _observations: tuple[MethodDrawObservation, ...]
    ) -> TrialEvaluation:
        if trial.candidate_id == "candidate-a":
            raise RuntimeError("deterministic failure")
        if trial.candidate_id == "candidate-b":
            raise TrialPruned("dominated at discovery checkpoint")
        return TrialEvaluation((ExactObjectiveValue(2, 5),))

    result = run_study(
        spec,
        discovery_observations=discovery,
        confirmation_observations=confirmation,
        evaluate_discovery=evaluate_discovery,
        evaluate_confirmation=lambda _winner, _observations: TrialEvaluation(
            (ExactObjectiveValue(1, 2),)
        ),
    )

    assert tuple(item.state for item in result.trials) == (
        TrialState.FAILED,
        TrialState.PRUNED,
        TrialState.COMPLETE,
    )
    assert result.trials[0].failure_type == "RuntimeError"
    assert result.trials[1].detail == "dominated at discovery checkpoint"
    assert result.winner.candidate_id == "candidate-c"


def test_no_completed_trial_fails_closed_with_all_records_and_no_confirmation() -> None:
    discovery = _observations(1, 2, 3)
    confirmation = _observations(4, 5)
    spec = _spec(discovery, confirmation, candidate_ids=("candidate-a", "candidate-b"))
    confirmation_calls: list[str] = []

    def evaluate_discovery(
        trial: TrialSpec, _observations: tuple[MethodDrawObservation, ...]
    ) -> TrialEvaluation:
        if trial.candidate_id == "candidate-a":
            raise ValueError("failed")
        raise TrialPruned("pruned")

    def evaluate_confirmation(
        winner: FrozenWinnerIdentity,
        _observations: tuple[MethodDrawObservation, ...],
    ) -> TrialEvaluation:
        confirmation_calls.append(winner.candidate_id)
        return TrialEvaluation((ExactObjectiveValue(0),))

    with pytest.raises(NoCompletedTrialError) as caught:
        run_study(
            spec,
            discovery_observations=discovery,
            confirmation_observations=confirmation,
            evaluate_discovery=evaluate_discovery,
            evaluate_confirmation=evaluate_confirmation,
        )

    assert tuple(item.state for item in caught.value.trial_results) == (
        TrialState.FAILED,
        TrialState.PRUNED,
    )
    assert confirmation_calls == []


def test_split_rejects_overlap_before_any_evaluation() -> None:
    discovery = _observations(1, 2, 3)
    confirmation = _observations(3, 4)

    with pytest.raises(NativeStudyContractError, match="overlap or are reversed"):
        _spec(discovery, confirmation)


def test_split_rejects_reversed_discovery_and_confirmation() -> None:
    discovery = _observations(4, 5)
    confirmation = _observations(1, 2)

    with pytest.raises(NativeStudyContractError, match="overlap or are reversed"):
        _spec(discovery, confirmation)


@pytest.mark.parametrize(
    ("discovery", "message"),
    [
        (_observations(1, 2, 2), "duplicated or non-chronological"),
        (_observations(1, 3, 2), "duplicated or non-chronological"),
    ],
)
def test_split_rejects_duplicated_or_non_chronological_observations(
    discovery: tuple[MethodDrawObservation, ...], message: str
) -> None:
    confirmation = _observations(4, 5)
    spec = _spec(discovery, confirmation)
    discovery_calls: list[str] = []

    def evaluate_discovery(
        trial: TrialSpec, _observations: tuple[MethodDrawObservation, ...]
    ) -> TrialEvaluation:
        discovery_calls.append(trial.candidate_id)
        return TrialEvaluation((ExactObjectiveValue(0),))

    with pytest.raises(NativeStudyContractError, match=message):
        run_study(
            spec,
            discovery_observations=discovery,
            confirmation_observations=confirmation,
            evaluate_discovery=evaluate_discovery,
            evaluate_confirmation=lambda _winner, _observations: TrialEvaluation(
                (ExactObjectiveValue(0),)
            ),
        )
    assert discovery_calls == []


def test_split_rejects_observations_that_contradict_endpoint_identity() -> None:
    discovery = _observations(1, 2, 3)
    confirmation = _observations(4, 5)
    spec = _spec(discovery, confirmation)
    changed_discovery = (
        _observation(1),
        _observation(2),
        MethodDrawObservation("3", "2026-01-04", 1, 1, (0,)),
    )

    with pytest.raises(NativeStudyContractError, match=r"non-chronological|contradicts"):
        run_study(
            spec,
            discovery_observations=changed_discovery,
            confirmation_observations=confirmation,
            evaluate_discovery=lambda _trial, _observations: TrialEvaluation(
                (ExactObjectiveValue(0),)
            ),
            evaluate_confirmation=lambda _winner, _observations: TrialEvaluation(
                (ExactObjectiveValue(0),)
            ),
        )


def test_confirmation_observation_changes_cannot_change_the_frozen_winner() -> None:
    scores = {
        "candidate-a": (ExactObjectiveValue(2, 3),),
        "candidate-b": (ExactObjectiveValue(3, 4),),
        "candidate-c": (ExactObjectiveValue(1, 3),),
    }
    baseline_confirmation = _observations(4, 5, hits=0)
    mutated_confirmation = _observations(4, 5, hits=6)

    baseline = _run_with_scores(scores, confirmation=baseline_confirmation)
    mutated = _run_with_scores(scores, confirmation=mutated_confirmation)

    assert baseline.winner == mutated.winner
    assert baseline.winner.candidate_id == "candidate-b"
    assert baseline.trials == mutated.trials
    assert baseline.confirmation.objective_values != mutated.confirmation.objective_values


def test_confirmation_is_called_once_only_after_winner_and_parameters_are_frozen() -> None:
    discovery = _observations(1, 2, 3)
    confirmation = _observations(4, 5)
    raw_parameters: dict[str, CanonicalValue] = {"alpha": (1, 2)}
    trials = (
        TrialSpec("candidate-a", raw_parameters),
        TrialSpec("candidate-b", {"alpha": (3, 4)}),
    )
    raw_parameters["alpha"] = (99,)
    spec = StudySpec(
        study_id="freeze-order",
        objectives=(ObjectiveSpec("score", ObjectiveDirection.MAXIMIZE),),
        trials=trials,
        temporal_holdout_split=_split(discovery, confirmation),
    )
    events: list[str] = []

    def evaluate_discovery(
        trial: TrialSpec, observations: tuple[MethodDrawObservation, ...]
    ) -> TrialEvaluation:
        assert observations is discovery
        events.append(f"discovery:{trial.candidate_id}")
        score = (
            ExactObjectiveValue(2, 3)
            if trial.candidate_id == "candidate-b"
            else ExactObjectiveValue(1, 3)
        )
        return TrialEvaluation((score,))

    def evaluate_confirmation(
        winner: FrozenWinnerIdentity,
        observations: tuple[MethodDrawObservation, ...],
    ) -> TrialEvaluation:
        assert observations is confirmation
        assert winner.parameters["alpha"] == (3, 4)
        events.append(f"confirmation:{winner.candidate_id}")
        return TrialEvaluation((ExactObjectiveValue(0),))

    result = run_study(
        spec,
        discovery_observations=discovery,
        confirmation_observations=confirmation,
        evaluate_discovery=evaluate_discovery,
        evaluate_confirmation=evaluate_confirmation,
    )

    assert events == [
        "discovery:candidate-a",
        "discovery:candidate-b",
        "confirmation:candidate-b",
    ]
    assert result.spec.trials[0].parameters["alpha"] == (1, 2)
    assert result.confirmation.winner is result.winner


def test_changing_a_losing_trial_does_not_change_unrelated_trial_records() -> None:
    first = _run_with_scores(
        {
            "candidate-a": (ExactObjectiveValue(4, 5),),
            "candidate-b": (ExactObjectiveValue(1, 5),),
            "candidate-c": (ExactObjectiveValue(1, 2),),
        }
    )
    second = _run_with_scores(
        {
            "candidate-a": (ExactObjectiveValue(4, 5),),
            "candidate-b": (ExactObjectiveValue(2, 5),),
            "candidate-c": (ExactObjectiveValue(1, 2),),
        }
    )

    first_by_id = {item.candidate_id: item for item in first.trials}
    second_by_id = {item.candidate_id: item for item in second.trials}
    assert first.winner == second.winner
    assert first_by_id["candidate-a"] == second_by_id["candidate-a"]
    assert first_by_id["candidate-c"] == second_by_id["candidate-c"]
    assert first_by_id["candidate-b"] != second_by_id["candidate-b"]


def test_full_history_descriptive_values_never_affect_selection() -> None:
    scores = {
        "candidate-a": (ExactObjectiveValue(1, 2),),
        "candidate-b": (ExactObjectiveValue(1, 2),),
        "candidate-c": (ExactObjectiveValue(1, 3),),
    }

    favors_a = _run_with_scores(
        scores,
        full_history_metadata={"descriptive_favorite": "candidate-a", "score": 1},
    )
    favors_b = _run_with_scores(
        scores,
        full_history_metadata={"descriptive_favorite": "candidate-b", "score": 999},
    )

    assert favors_a.winner == favors_b.winner
    assert favors_a.winner.candidate_id == "candidate-a"
    assert favors_a.spec.full_history_metadata != favors_b.spec.full_history_metadata


def test_full_history_window_cannot_bind_a_selection_objective() -> None:
    with pytest.raises(NativeStudyContractError, match="descriptive-only"):
        ObjectiveSpec(
            "forbidden",
            ObjectiveDirection.MAXIMIZE,
            window_kind=WindowKind.FULL_HISTORY,
            metric_id="M1_PLUS",
        )


def test_existing_method_evaluation_record_is_composed_without_redefining_metrics() -> None:
    discovery = _observations(1, 2, 3)
    confirmation = _observations(4, 5)
    objective = ObjectiveSpec(
        "m2_success_rate",
        ObjectiveDirection.MAXIMIZE,
        window_kind=WindowKind.WINDOW_50,
        metric_id="M2_PLUS",
        value_field=EvaluationValueField.OBSERVED_VALUE,
    )
    spec = _spec(
        discovery,
        confirmation,
        objectives=(objective,),
        candidate_ids=("candidate-a", "candidate-b"),
    )
    contract = LotteryMatchContract(
        lottery_type="TOY",
        population_size=5,
        winning_number_count=2,
        ticket_number_count=2,
        hit_tiers=(HitTierDefinition("M2_PLUS", 2),),
    )

    def evaluation_for(
        candidate_id: str, observations: tuple[MethodDrawObservation, ...]
    ) -> object:
        hits = 0 if candidate_id == "candidate-a" else 2
        history = tuple(
            MethodDrawObservation(item.draw_id, item.draw_date, 1, 1, (hits,))
            for item in observations
        )
        identity = MethodIdentity(
            method_id=candidate_id,
            method_version="v1",
            method_family="synthetic-native-study",
            output_shape=OutputShape.SINGLE_OUTPUT,
            exposure=MethodExposure(ExposureKind.FIXED, 1, 1),
            target_coverage=MethodTargetCoverage(
                len(history), history[0].draw_id, history[-1].draw_id
            ),
            replay_status=ReplayStatus.BASELINE_RECORDED,
        )
        return evaluate_method(contract, identity, history)

    result = run_study(
        spec,
        discovery_observations=discovery,
        confirmation_observations=confirmation,
        evaluate_discovery=lambda trial, observations: evaluation_for(
            trial.candidate_id, observations
        ),
        evaluate_confirmation=lambda winner, observations: evaluation_for(
            winner.candidate_id, observations
        ),
    )

    assert result.winner.candidate_id == "candidate-b"
    assert result.winner.discovery_objective_values == (Fraction(1),)
    assert (
        result.trials[1].full_history_metadata["evaluator_semantic_version"]
        == BASE_METHOD_EVALUATOR_SEMANTIC_VERSION
    )


def test_trials_must_arrive_in_canonical_candidate_id_order() -> None:
    discovery = _observations(1, 2)
    confirmation = _observations(3, 4)

    with pytest.raises(NativeStudyContractError, match="canonical ascending"):
        StudySpec(
            study_id="bad-order",
            objectives=(ObjectiveSpec("score", ObjectiveDirection.MAXIMIZE),),
            trials=(TrialSpec("candidate-b"), TrialSpec("candidate-a")),
            temporal_holdout_split=_split(discovery, confirmation),
        )


def test_binary_float_objectives_and_metadata_fail_closed() -> None:
    with pytest.raises(NativeStudyContractError, match="binary floats are forbidden"):
        TrialEvaluation((0.5,))  # type: ignore[arg-type]
    with pytest.raises(NativeStudyContractError, match="immutable LCJ-1 values"):
        TrialSpec("candidate-a", {"alpha": 0.5})  # type: ignore[dict-item]
