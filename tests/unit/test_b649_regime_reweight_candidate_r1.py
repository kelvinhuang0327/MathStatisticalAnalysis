from __future__ import annotations

import random
from datetime import date, timedelta

from lottolab.research.b649_k235_output_quality import evaluate_candidate_quality
from lottolab.research.b649_regime_reweight_candidate_r1 import (
    MINIMUM_HISTORY,
    HistoricalDraw,
    fit_switch_rule,
    forecast_from_history,
    predict_fixed_weight_tickets,
    predict_weighted_tickets,
    random_tickets,
    run_walk_forward_backtest,
)


def _draws(count: int, *, changed_from: int | None = None) -> tuple[HistoricalDraw, ...]:
    rng = random.Random(20261028)
    start = date(2020, 1, 1)
    draws: list[HistoricalDraw] = []
    for index in range(count):
        population = (
            range(1, 10) if changed_from is not None and index >= changed_from else range(1, 50)
        )
        numbers = tuple(sorted(rng.sample(population, 6)))
        draws.append(
            HistoricalDraw(
                draw_number=str(96000001 + index),
                draw_date=start + timedelta(days=index),
                main_numbers=numbers,
            )
        )
    return tuple(draws)


def test_cusum_signal_is_higher_for_a_strong_synthetic_change() -> None:
    stable = _draws(300)
    changed = _draws(300, changed_from=150)

    stable_signal = forecast_from_history(stable).cusum_statistic
    changed_signal = forecast_from_history(changed).cusum_statistic

    assert changed_signal > stable_signal * 1.5


def test_k235_portfolios_are_legal_and_reproducible() -> None:
    history = _draws(120)

    for ticket_count in (2, 3, 5):
        for preset_id in ("SHORT_HEAVY", "BALANCED", "LONG_HEAVY"):
            first = predict_weighted_tickets(history, ticket_count, preset_id)
            second = predict_weighted_tickets(history, ticket_count, preset_id)
            assert first == second
            assert evaluate_candidate_quality(first, ticket_count).is_valid

        fixed_first = predict_fixed_weight_tickets(history, ticket_count)
        fixed_second = predict_fixed_weight_tickets(history, ticket_count)
        random_first = random_tickets(history, ticket_count, replicate=7)
        random_second = random_tickets(history, ticket_count, replicate=7)
        assert fixed_first == fixed_second
        assert random_first == random_second
        assert evaluate_candidate_quality(fixed_first, ticket_count).is_valid
        assert evaluate_candidate_quality(random_first, ticket_count).is_valid


def test_future_draws_cannot_change_training_rule_or_target_forecast() -> None:
    draws = _draws(150)
    split = 100
    changed_future = list(draws)
    for index in range(split, len(draws)):
        changed_future[index] = HistoricalDraw(
            draw_number=draws[index].draw_number,
            draw_date=draws[index].draw_date,
            main_numbers=tuple(sorted(((index + offset) % 49) + 1 for offset in range(6))),
        )
    changed_draws = tuple(changed_future)

    contexts = {
        index: forecast_from_history(draws[:index]) for index in range(MINIMUM_HISTORY, len(draws))
    }
    changed_contexts = {
        index: forecast_from_history(changed_draws[:index])
        for index in range(MINIMUM_HISTORY, len(changed_draws))
    }
    training_indices = tuple(range(MINIMUM_HISTORY, split))
    original_fit = fit_switch_rule(draws, contexts, training_indices, ticket_count=3)
    changed_fit = fit_switch_rule(changed_draws, changed_contexts, training_indices, ticket_count=3)

    assert original_fit == changed_fit
    assert contexts[split].history_fingerprint == changed_contexts[split].history_fingerprint
    assert contexts[split].cusum_statistic == changed_contexts[split].cusum_statistic
    assert contexts[split].weighted_tickets_by_k == changed_contexts[split].weighted_tickets_by_k
    assert (
        contexts[split].fixed_weight_tickets_by_k
        == changed_contexts[split].fixed_weight_tickets_by_k
    )


def test_walk_forward_records_have_prior_cutoffs_and_frozen_training_boundary() -> None:
    draws = _draws(180)
    result = run_walk_forward_backtest(
        draws,
        evaluation_windows=(50,),
        random_replicates=4,
    )

    assert result["evaluation_windows"] == [50]
    rows = result["rows"]
    assert isinstance(rows, list) and len(rows) == 3
    records = result["target_records"]
    assert isinstance(records, list) and len(records) == 150
    for record in records:
        target_id = int(record["target_draw_number"])
        cutoff_id = int(record["feature_cutoff_draw_number"])
        train_last_id = int(record["training_last_target_draw_number"])
        assert cutoff_id < target_id
        assert train_last_id < int(rows[0]["evaluation_first_target_draw_number"])
        assert record["training_target_count"] == 80
