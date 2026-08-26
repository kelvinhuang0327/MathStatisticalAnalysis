"""Parity and causal-contract tests for the target-native P20 constructor."""

from __future__ import annotations

from dataclasses import fields
from itertools import combinations

from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
    V1_PARITY_PORTFOLIO_SHA256,
    ConstructionTier,
    ConstructorFailure,
    ConstructorFailureReason,
    ConstructorRequest,
    ConstructorSuccess,
    construct_strategy_preserving_20_ticket,
    generate_seeded_candidate_pool,
    objective_constants,
)


def _request(
    raw_tickets: list[list[int]],
    **overrides: object,
) -> ConstructorRequest:
    values: dict[str, object] = {
        "draw_id": "115000070",
        "historical_cutoff_identity": "115000069",
        "raw_tickets": raw_tickets,
        "replicate_id": 0,
        "strategy_id": "fixture::tier_c",
        "user_seed": "unit-test",
    }
    values.update(overrides)
    return ConstructorRequest(**values)  # type: ignore[arg-type]


def _native_tickets(count: int) -> list[list[int]]:
    return [
        list(ticket)
        for ticket in list(combinations(range(1, 50), 6))[:count]
    ]


def test_frozen_ranked_signal_parity_hash_matches_legacy_p20() -> None:
    request = ConstructorRequest(
        strategy_id="fixture::ranked_signal",
        draw_id="115000070",
        replicate_id=3,
        raw_tickets=(
            (1, 7, 13, 19, 25, 31),
            (2, 8, 14, 20, 26, 32),
        ),
        historical_cutoff_identity="115000069",
        user_seed="p20c-parity-v1",
        number_scores={
            1: 9.5,
            2: 9.0,
            7: 8.5,
            8: 8.0,
            13: 7.5,
            14: 7.0,
            19: 6.5,
            20: 6.0,
            25: 5.5,
            26: 5.0,
            31: 4.5,
            32: 4.0,
        },
        ranked_numbers=(1, 2, 7, 8, 13, 14, 19, 20, 25, 26, 31, 32),
    )

    result = construct_strategy_preserving_20_ticket(request)

    assert type(result) is ConstructorSuccess
    assert len(result.tickets) == 20
    assert len(set(result.tickets)) == 20
    assert result.metadata.portfolio_sha256 == V1_PARITY_PORTFOLIO_SHA256
    assert result.metadata.seed_digest == (
        "f525648c05ca53a9858847303992c7a25132f6f306061547df53a14c06d0b406"
    )
    assert result.metadata.native_retained_count == 2
    assert result.metadata.constructed_ticket_count == 18
    assert (
        result.metadata.construction_tier
        == ConstructionTier.STRATEGY_RANKED_SIGNAL.value
    )


def test_native_duplicates_are_audited_and_constructor_is_deterministic() -> None:
    request = _request(
        [[6, 1, 5, 2, 4, 3], [1, 2, 3, 4, 5, 6]]
    )

    first = construct_strategy_preserving_20_ticket(request)
    second = construct_strategy_preserving_20_ticket(request)

    assert first == second
    assert type(first) is ConstructorSuccess
    assert first.metadata.native_input_count == 2
    assert first.metadata.native_valid_count == 1
    assert first.metadata.native_duplicate_count == 1
    assert first.metadata.native_retained_count == 1
    assert first.metadata.constructed_ticket_count == 19


def test_exact_twenty_native_tickets_are_canonical_and_not_reconstructed() -> None:
    forward = construct_strategy_preserving_20_ticket(
        _request(_native_tickets(20))
    )
    reverse = construct_strategy_preserving_20_ticket(
        _request(list(reversed(_native_tickets(20))))
    )

    assert type(forward) is ConstructorSuccess
    assert forward == reverse
    assert forward.metadata.construction_tier == ConstructionTier.NATIVE_COMPLETE.value
    assert forward.metadata.constructed_ticket_count == 0
    assert forward.metadata.effective_strategy_id == "fixture::tier_c"


def test_invalid_or_future_cutoff_fails_closed() -> None:
    equal = construct_strategy_preserving_20_ticket(
        _request(_native_tickets(1), historical_cutoff_identity="115000070")
    )
    future = construct_strategy_preserving_20_ticket(
        _request(_native_tickets(1), historical_cutoff_identity="115000071")
    )

    assert type(equal) is ConstructorFailure
    assert type(future) is ConstructorFailure
    assert equal.reason is ConstructorFailureReason.INVALID_CUTOFF
    assert future.reason is ConstructorFailureReason.INVALID_CUTOFF


def test_request_has_no_target_outcome_or_generic_context() -> None:
    field_names = {field.name for field in fields(ConstructorRequest)}

    assert "target_numbers" not in field_names
    assert "winning_numbers" not in field_names
    assert "actual_numbers" not in field_names
    assert "context" not in field_names
    assert "historical_cutoff_identity" in field_names


def test_version_and_objective_constants_are_frozen() -> None:
    assert CONSTRUCTOR_IDENTIFIER == "strategy_preserving_20_ticket/v1"
    assert objective_constants() == {
        "candidate_pool_size": 80,
        "constructor_identifier": "strategy_preserving_20_ticket/v1",
        "max_candidate_attempts": 4096,
        "max_overlap_penalty": 12.0,
        "number_concentration_penalty": 2.0,
        "parity_portfolio_sha256": V1_PARITY_PORTFOLIO_SHA256,
        "signal_score_weight": 100.0,
    }


def test_seeded_candidate_pool_reuses_frozen_mechanics_deterministically() -> None:
    signal_tickets = ((1, 2, 3, 4, 5, 6),)

    first = generate_seeded_candidate_pool(
        strategy_id="fixture::candidate-pool",
        draw_id="115000069",
        user_seed=7,
        signal_tickets=signal_tickets,
        required_count=19,
    )
    second = generate_seeded_candidate_pool(
        strategy_id="fixture::candidate-pool",
        draw_id="115000069",
        user_seed=7,
        signal_tickets=signal_tickets,
        required_count=19,
    )
    changed_seed = generate_seeded_candidate_pool(
        strategy_id="fixture::candidate-pool",
        draw_id="115000069",
        user_seed=8,
        signal_tickets=signal_tickets,
        required_count=19,
    )

    assert first == second
    assert first != changed_seed
    assert len(first) >= 19
    assert len(set(first)) == len(first)
    assert signal_tickets[0] not in first
