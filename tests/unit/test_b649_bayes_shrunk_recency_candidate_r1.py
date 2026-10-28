from __future__ import annotations

import pytest

from lottolab.research.b649_bayes_shrunk_recency_candidate_r1 import (
    SUPPORTED_WINDOWS,
    BayesRecencyCandidateError,
    bayes_shrunk_recency_scores,
    portfolio_from_scores,
    predict_target_tickets,
    predict_tickets,
)


def _history(count: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(sorted(((draw_index * 7 + offset * 11) % 49) + 1 for offset in range(6)))
        for draw_index in range(count)
    )


def _draw_with_number(number: int | None) -> tuple[int, ...]:
    values = [] if number is None else [number]
    for candidate in range(1, 50):
        if number is None and candidate == 1:
            continue
        if candidate not in values:
            values.append(candidate)
        if len(values) == 6:
            return tuple(values)
    raise AssertionError("could not build a valid six-number draw")


def test_same_history_returns_identical_candidate_portfolio() -> None:
    history = _history(120)
    first = predict_tickets(
        history,
        ticket_count=3,
        window_size=50,
        half_life=50,
    )
    second = predict_tickets(
        history,
        ticket_count=3,
        window_size=50,
        half_life=50,
    )

    assert first == second


@pytest.mark.parametrize("ticket_count", (2, 3, 5))
def test_supported_native_research_portfolios_are_legal_and_distinct(
    ticket_count: int,
) -> None:
    portfolio = predict_tickets(
        _history(100),
        ticket_count=ticket_count,
        window_size=50,
        half_life=50,
    )

    assert len(portfolio) == ticket_count
    assert len(set(portfolio)) == ticket_count
    for ticket in portfolio:
        assert len(ticket) == 6
        assert ticket == tuple(sorted(ticket))
        assert len(set(ticket)) == 6
        assert all(1 <= number <= 49 for number in ticket)

    pairwise_overlaps = [
        len(set(left) & set(right))
        for index, left in enumerate(portfolio)
        for right in portfolio[index + 1 :]
    ]
    assert len(pairwise_overlaps) == ticket_count * (ticket_count - 1) // 2
    assert all(0 <= overlap <= 6 for overlap in pairwise_overlaps)


def test_fixed_windows_and_bounded_decay_candidates_are_accepted() -> None:
    history = _history(80)

    for window_size in SUPPORTED_WINDOWS:
        scores = bayes_shrunk_recency_scores(
            history,
            window_size=window_size,
            half_life=window_size / 2,
        )
        assert len(scores) == 49
        assert all(0.0 <= score <= 1.0 for score in scores)


def test_beta_prior_shrinks_sparse_recent_count_toward_older_rate() -> None:
    history = tuple(
        [_draw_with_number(1 if index < 80 else None) for index in range(100)]
        + [_draw_with_number(1 if index == 0 else None) for index in range(50)]
    )
    scores = bayes_shrunk_recency_scores(history, window_size=50, half_life=50)
    prior_mean = (80 + 0.5) / (100 + 1.0)
    recent_raw_rate = 1 / 50

    assert recent_raw_rate < scores[0] < prior_mean


def test_recent_observation_receives_more_weight_than_old_observation() -> None:
    older_history = tuple(_draw_with_number(1 if index < 30 else None) for index in range(100))
    recent_success = tuple([_draw_with_number(None) for _ in range(49)] + [_draw_with_number(1)])
    old_success = tuple([_draw_with_number(1)] + [_draw_with_number(None) for _ in range(49)])

    latest_score = bayes_shrunk_recency_scores(
        older_history + recent_success,
        window_size=50,
        half_life=25,
    )[0]
    oldest_score = bayes_shrunk_recency_scores(
        older_history + old_success,
        window_size=50,
        half_life=25,
    )[0]

    assert latest_score > oldest_score


def test_changing_target_or_future_results_cannot_change_current_prediction() -> None:
    draws = list(_history(100))
    target_index = 75
    baseline = predict_target_tickets(
        draws,
        target_index=target_index,
        ticket_count=3,
        window_size=50,
        half_life=50,
    )

    changed_target = list(draws)
    changed_target[target_index] = tuple(
        sorted((number % 49) + 1 for number in changed_target[target_index])
    )
    changed_future = [*changed_target, _history(101)[-1]]

    assert (
        predict_target_tickets(
            changed_target,
            target_index=target_index,
            ticket_count=3,
            window_size=50,
            half_life=50,
        )
        == baseline
    )
    assert (
        predict_target_tickets(
            changed_future,
            target_index=target_index,
            ticket_count=3,
            window_size=50,
            half_life=50,
        )
        == baseline
    )


def test_candidate_does_not_mutate_input_history() -> None:
    history = [list(row) for row in _history(90)]
    before = [list(row) for row in history]

    predict_tickets(
        history,
        ticket_count=2,
        window_size=50,
        half_life=100,
    )

    assert history == before


@pytest.mark.parametrize(
    ("window_size", "half_life", "ticket_count"),
    (
        (51, 50, 2),
        (50, 24, 2),
        (50, 3001, 2),
        (50, 50, 4),
    ),
)
def test_candidate_rejects_unregistered_window_decay_or_ticket_count(
    window_size: int,
    half_life: float,
    ticket_count: int,
) -> None:
    with pytest.raises(BayesRecencyCandidateError):
        predict_tickets(
            _history(60),
            ticket_count=ticket_count,
            window_size=window_size,
            half_life=half_life,
        )


def test_portfolio_selector_rejects_nonfinite_scores() -> None:
    with pytest.raises(BayesRecencyCandidateError):
        portfolio_from_scores((float("nan"),) + (0.1,) * 48, ticket_count=2)
