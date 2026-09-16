"""Causal, finite-universe, and deterministic guards for R2 interactions."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from fractions import Fraction
from typing import cast

import pytest

from lottolab.evidence import canonical_json
from lottolab.research.historical_replay_meta_feature_interaction_discovery import (
    FEATURE_COUNT,
    FEATURE_DEFINITIONS,
    INTERACTION_CANDIDATE_COUNT,
    INTERACTION_RULES,
    PINNED_R1_RESULT_SHA256,
    R1_DISCOVERY_PARTITION,
    CorpusDraw,
    CorpusProfile,
    DiscoveryPartition,
    DrawFeatureFrame,
    DrawIdentity,
    HistoricalReplayDiscoveryCorpus,
    InteractionDiscoveryError,
    InteractionRule,
    R1DiscoveryAuthority,
    RunInventory,
    SelectionDirection,
    StrategyPrediction,
    StrategyTargetObservation,
    TemporalRobustness,
    TicketPrediction,
    build_feature_frames,
    candidate_universe_sha256,
    preregistration_payload,
    r1_discovery_authority_from_result,
    run_interaction_discovery,
    select_strategy,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _numbers(offset: int) -> tuple[int, ...]:
    return tuple(sorted(((offset + step) % 49) + 1 for step in range(6)))


def _corpus(
    draw_count: int,
    *,
    current_or_future_mutation: bool = False,
    prior_mutation: bool = False,
) -> HistoricalReplayDiscoveryCorpus:
    strategy_ids = ("strategy-a", "strategy-b", "strategy-c")
    start = date(2015, 1, 1)
    draws: list[CorpusDraw] = []
    previous = DrawIdentity(
        draw_date=(start - timedelta(days=1)).isoformat(),
        draw_number=99_999_999,
        draw_sha256=_sha("cutoff-before-corpus"),
    )
    for index in range(draw_count):
        target = DrawIdentity(
            draw_date=(start + timedelta(days=index)).isoformat(),
            draw_number=100_000_000 + index,
            draw_sha256=_sha(f"target-{index}"),
        )
        winning = _numbers(index * 3)
        observations: list[StrategyTargetObservation] = []
        for strategy_offset, strategy_id in enumerate(strategy_ids, start=1):
            first_numbers = _numbers(index + strategy_offset * 7)
            first_hit = len(set(first_numbers) & set(winning))
            if prior_mutation and index == 299 and strategy_id == "strategy-a":
                first_hit = 6
            if current_or_future_mutation and index >= 300 and strategy_id == "strategy-a":
                first_hit = 6 - first_hit
            tickets = [
                TicketPrediction(
                    native_position=1,
                    main_numbers=first_numbers,
                    ticket_sha256=_sha(f"{index}-{strategy_id}-1"),
                )
            ]
            if strategy_id == "strategy-b":
                tickets.append(
                    TicketPrediction(
                        native_position=2,
                        main_numbers=_numbers(index + 19),
                        ticket_sha256=_sha(f"{index}-{strategy_id}-2"),
                    )
                )
            observations.append(
                StrategyTargetObservation(
                    prediction=StrategyPrediction(
                        strategy_id=strategy_id,
                        strategy_version="v1",
                        tickets=tuple(tickets),
                    ),
                    first_ticket_main_hit_count=first_hit,
                )
            )
        if current_or_future_mutation and index >= 300:
            winning = _numbers(index * 3 + 23)
        draws.append(
            CorpusDraw(
                target=target,
                cutoff=previous,
                winning_main_numbers=winning,
                strategies=tuple(observations),
            )
        )
        previous = target
    profile = CorpusProfile(
        bounded_target_row_count=draw_count * len(strategy_ids),
        bounded_ticket_row_count=draw_count * 4,
        bounded_result_row_count=draw_count * 4,
        common_draw_count=draw_count,
        rows_excluded_outside_common_intersection=0,
        duplicate_native_ticket_position_count=0,
        result_version_extra_count=0,
        required_null_count=0,
        invalid_json_count=0,
        recomputed_hit_mismatch_count=0,
        causal_date_violation_count=0,
        run_inventory=(
            RunInventory(
                run_id="synthetic-reference-run",
                run_kind="REFERENCE_BASELINE",
                latest_status="COMPLETED",
                strategy_count=len(strategy_ids),
                target_row_count=draw_count * len(strategy_ids),
                distinct_target_count=draw_count,
            ),
        ),
    )
    return HistoricalReplayDiscoveryCorpus(
        source_run_id="synthetic-reference-run",
        source_run_kind="REFERENCE_BASELINE",
        source_dataset_identity="synthetic-dataset",
        source_dataset_sha256=_sha("synthetic-dataset"),
        source_rule_contract_id="synthetic-rule-contract",
        latest_run_status="COMPLETED",
        strategies=strategy_ids,
        draws=tuple(draws),
        profile=profile,
    )


def _partition(corpus: HistoricalReplayDiscoveryCorpus) -> DiscoveryPartition:
    return DiscoveryPartition(
        split_method="SYNTHETIC_R1_EQUIVALENT_SPLIT",
        total_assignment_count=len(corpus.draws),
        warmup_count=448,
        discovery_count=750,
        discovery_first_target=corpus.draws[448].target,
        discovery_last_target=corpus.draws[-1].target,
    )


def _authority(corpus: HistoricalReplayDiscoveryCorpus) -> R1DiscoveryAuthority:
    return R1DiscoveryAuthority(
        r1_result_sha256=PINNED_R1_RESULT_SHA256,
        source_database_sha256="a" * 64,
        source_dataset_identity=corpus.source_dataset_identity,
        source_dataset_sha256=corpus.source_dataset_sha256,
        source_run_id=corpus.source_run_id,
        source_run_kind=corpus.source_run_kind,
        strategy_ids=corpus.strategies,
        partition=_partition(corpus),
        benchmark_candidate_id="synthetic-r1-winner",
        benchmark_exact_rule="synthetic exact single-feature rule",
        benchmark_m2_delta_vs_pool=Fraction(1, 66),
        benchmark_avg_match_delta_vs_pool=Fraction(53, 1650),
    )


def _r1_result_payload() -> dict[str, object]:
    candidate_rules = [
        {
            "candidate_id": f"r1__{feature.feature_id}__{direction.casefold()}",
            "exact_rule": f"{direction}({feature.feature_id})",
            "feature": feature.canonical_dict(),
            "selection_direction": direction,
            "selection_unit": "CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE",
            "tie_breaker": "LEXICOGRAPHIC_STRATEGY_ID_ASC",
        }
        for feature in FEATURE_DEFINITIONS
        for direction in ("ARGMAX", "ARGMIN")
    ]
    benchmark_id = "r1__recent_avg_match_w010__argmin"
    performance = {
        "support_count": 750,
        "m2_delta_vs_pool": {"denominator": 66, "numerator": 1},
        "avg_match_delta_vs_pool": {"denominator": 1650, "numerator": 53},
    }
    return {
        "candidate_rule_count": 36,
        "candidate_rules": candidate_rules,
        "classification": "IGNORED_CONFIRMATION_CLASSIFICATION",
        "frozen_winner": {
            "confirmation": {"forbidden_label": "ignored"},
            "discovery": {
                "candidate_id": benchmark_id,
                "exact_rule": "ARGMIN(recent_avg_match_w010)",
                "performance": performance,
            },
        },
        "native_study_result": {
            "confirmation": {"forbidden_label": "ignored"},
            "spec": {
                "temporal_holdout_split": {
                    "confirmation_count": 300,
                    "confirmation_first_target": {
                        "draw_date": "2023-11-24",
                        "draw_number": 112000106,
                        "draw_sha256": "c" * 64,
                    },
                    "confirmation_last_target": {
                        "draw_date": "2026-05-15",
                        "draw_number": 115000053,
                        "draw_sha256": "d" * 64,
                    },
                    "discovery_count": 750,
                    "discovery_first_target": (
                        R1_DISCOVERY_PARTITION.discovery_first_target.canonical_dict()
                    ),
                    "discovery_last_target": (
                        R1_DISCOVERY_PARTITION.discovery_last_target.canonical_dict()
                    ),
                    "split_method": R1_DISCOVERY_PARTITION.split_method,
                    "total_assignment_count": 1498,
                    "warmup_count": 448,
                }
            },
            "winner": {
                "candidate_id": benchmark_id,
                "discovery_objective_values": [
                    {"denominator": 66, "numerator": 1},
                    {"denominator": 1650, "numerator": 53},
                ],
            },
        },
        "source": {
            "database_sha256": "a" * 64,
            "dataset_identity": "synthetic-dataset",
            "dataset_sha256": "b" * 64,
            "run_id": "synthetic-reference-run",
            "run_kind": "REFERENCE_BASELINE",
            "strategy_ids": ["strategy-a", "strategy-b"],
        },
    }


def test_interaction_universe_is_exact_finite_and_canonical() -> None:
    assert FEATURE_COUNT == 18
    assert INTERACTION_CANDIDATE_COUNT == 612
    assert len({rule.candidate_id for rule in INTERACTION_RULES}) == 612
    assert len(candidate_universe_sha256()) == 64

    pair_directions: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for rule in INTERACTION_RULES:
        pair = (rule.primary_feature.feature_id, rule.secondary_feature.feature_id)
        assert pair[0] < pair[1]
        pair_directions.setdefault(pair, set()).add(
            (rule.primary_direction.value, rule.secondary_direction.value)
        )
    assert len(pair_directions) == 153
    assert all(
        directions == {("MAX", "MAX"), ("MAX", "MIN"), ("MIN", "MAX"), ("MIN", "MIN")}
        for directions in pair_directions.values()
    )


def test_selector_uses_a_then_b_then_strategy_identity() -> None:
    corpus = _corpus(301)
    draw = corpus.draws[-1]
    primary = FEATURE_DEFINITIONS[0]
    secondary = FEATURE_DEFINITIONS[1]
    rule = InteractionRule(
        candidate_id="synthetic-interaction",
        primary_feature=primary,
        primary_direction=SelectionDirection.MAX,
        secondary_feature=secondary,
        secondary_direction=SelectionDirection.MIN,
    )
    frame = DrawFeatureFrame(
        draw=draw,
        feature_values={
            "strategy-a": {primary.feature_id: Fraction(2), secondary.feature_id: Fraction(9)},
            "strategy-b": {primary.feature_id: Fraction(2), secondary.feature_id: Fraction(4)},
            "strategy-c": {primary.feature_id: Fraction(1), secondary.feature_id: Fraction(1)},
        },
    )
    assert select_strategy(frame, rule) == "strategy-b"

    tied = DrawFeatureFrame(
        draw=draw,
        feature_values={
            "strategy-a": {primary.feature_id: Fraction(2), secondary.feature_id: Fraction(4)},
            "strategy-b": {primary.feature_id: Fraction(2), secondary.feature_id: Fraction(4)},
            "strategy-c": {primary.feature_id: Fraction(1), secondary.feature_id: Fraction(1)},
        },
    )
    assert select_strategy(tied, rule) == "strategy-a"


def test_current_and_future_labels_cannot_change_current_feature_frame() -> None:
    original = build_feature_frames(_corpus(302))
    mutated = build_feature_frames(_corpus(302, current_or_future_mutation=True))

    assert original[0].draw.target == mutated[0].draw.target
    assert original[0].feature_values == mutated[0].feature_values
    assert tuple(select_strategy(original[0], rule) for rule in INTERACTION_RULES) == tuple(
        select_strategy(mutated[0], rule) for rule in INTERACTION_RULES
    )


def test_strictly_prior_label_can_change_next_feature_frame() -> None:
    original = build_feature_frames(_corpus(301))
    mutated = build_feature_frames(_corpus(301, prior_mutation=True))

    assert (
        original[0].feature_values["strategy-a"]["recent_avg_match_w010"]
        != mutated[0].feature_values["strategy-a"]["recent_avg_match_w010"]
    )


def test_r1_projection_ignores_confirmation_and_classification_fields() -> None:
    original = _r1_result_payload()
    mutated = deepcopy(original)
    mutated["classification"] = "A_DIFFERENT_IGNORED_VALUE"
    frozen = mutated["frozen_winner"]
    assert isinstance(frozen, dict)
    frozen["confirmation"] = {"forbidden_label": "changed"}
    native = mutated["native_study_result"]
    assert isinstance(native, dict)
    native["confirmation"] = {"forbidden_label": "changed-again"}

    first = r1_discovery_authority_from_result(
        original,
        r1_result_sha256=PINNED_R1_RESULT_SHA256,
    )
    second = r1_discovery_authority_from_result(
        mutated,
        r1_result_sha256=PINNED_R1_RESULT_SHA256,
    )

    assert first == second
    assert first.projection_sha256 == second.projection_sha256


def test_preregistration_freezes_every_rule_without_outcome_labels() -> None:
    authority = r1_discovery_authority_from_result(
        _r1_result_payload(),
        r1_result_sha256=PINNED_R1_RESULT_SHA256,
    )
    payload = preregistration_payload(authority)
    text = str(payload).casefold()

    assert payload["feature_count"] == 18
    assert payload["interaction_candidate_count"] == 612
    raw_interaction_rules = payload["interaction_rules"]
    assert isinstance(raw_interaction_rules, list)
    interaction_rules = cast("list[object]", raw_interaction_rules)
    assert len(interaction_rules) == 612
    assert "main_hit_count" not in text
    assert "winning_main_numbers" not in text
    anti_leakage = payload["anti_leakage_contract"]
    assert isinstance(anti_leakage, dict)
    assert anti_leakage["confirmation_observation_count_loaded"] == 0


def test_full_discovery_execution_is_complete_deterministic_and_rejects_extra_rows() -> None:
    corpus = _corpus(1_198)
    authority = _authority(corpus)
    preregistration_sha256 = "c" * 64
    first = run_interaction_discovery(
        corpus,
        database_sha256="a" * 64,
        preregistration_sha256=preregistration_sha256,
        authority=authority,
    )
    second = run_interaction_discovery(
        corpus,
        database_sha256="a" * 64,
        preregistration_sha256=preregistration_sha256,
        authority=authority,
    )

    first_raw = canonical_json.canonical_file_bytes(first.canonical_dict())
    second_raw = canonical_json.canonical_file_bytes(second.canonical_dict())
    assert first.completed_count == 612
    assert len(first.evaluations) == 612
    assert first_raw == second_raw
    assert canonical_json.sha256_hex(first_raw) == canonical_json.sha256_hex(second_raw)
    assert first.winner.performance.support_count == 750
    assert tuple(first.winner.windows) == (50, 300, 750)
    ranked = sorted(
        first.evaluations,
        key=lambda item: (
            -item.performance.m2_delta_vs_pool,
            -item.performance.avg_match_delta_vs_pool,
            item.rule.candidate_id,
        ),
    )
    robust_ranked = [item for item in ranked if TemporalRobustness(item).passed]
    assert first.pooled_winner == ranked[0]
    assert first.robust_candidate_count == len(robust_ranked)
    assert first.winner == (robust_ranked[0] if robust_ranked else ranked[0])

    extra_target = DrawIdentity(
        draw_date=(
            date.fromisoformat(corpus.draws[-1].target.draw_date) + timedelta(days=1)
        ).isoformat(),
        draw_number=corpus.draws[-1].target.draw_number + 1,
        draw_sha256=_sha("post-discovery-confirmation-row"),
    )
    extra_draw = replace(
        corpus.draws[-1],
        target=extra_target,
        cutoff=corpus.draws[-1].target,
    )
    with pytest.raises(
        InteractionDiscoveryError,
        match="no confirmation rows",
    ):
        run_interaction_discovery(
            replace(corpus, draws=(*corpus.draws, extra_draw)),
            database_sha256="a" * 64,
            preregistration_sha256=preregistration_sha256,
            authority=authority,
        )
