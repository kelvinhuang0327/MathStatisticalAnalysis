"""Any-prize selection, complete outcomes, chronology, and replay boundaries."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from math import comb

import pytest

from lottolab.application.historical_replay_adapters import (
    BigLottoReplayAdapter,
    binding_from_implementation,
)
from lottolab.application.use_cases.generate_bet import HistoryParseError, parse_history_json
from lottolab.application.use_cases.replay_backfill import _OutcomeBlindAdapter
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.strategies.adapters import biglotto_batch16 as legacy
from lottolab.strategies.adapters import biglotto_evolution_any_prize as subject
from lottolab.strategies.adapters.base import CausalDrawRow, InvalidOutput


class Candidate(legacy._EvoStrategy):
    def __init__(self, name: str, ticket: tuple[int, ...]) -> None:
        self.name = name
        self.params = {"ticket": ticket}
        self.category = "test"
        self.ticket = ticket
        self.seen: list[list[list[int]]] = []

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        self.seen.append(draws)
        return list(self.ticket[:n_select])


def rows(n: int, special: int = 7) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            str(100000001 + i),
            (date(2020, 1, 1) + timedelta(days=i)).isoformat(),
            (1, 2, 3, 4, 5, 6),
            special,
        )
        for i in range(n)
    )


@pytest.mark.parametrize("hits", range(7))
@pytest.mark.parametrize("special_hit", [False, True])
def test_any_prize_matches_official_evaluator(hits: int, special_hit: bool) -> None:
    # Six main matches plus a seventh special cannot appear on a six-number ticket.
    if hits == 6 and special_hit:
        return
    ticket = tuple(
        sorted(
            (
                *range(1, hits + 1),
                *((7,) if special_hit else ()),
                *range(20, 20 + 6 - hits - special_hit),
            )
        )
    )
    actual = evaluate_lottery_prize(
        lottery_type=LotteryType.BIG_LOTTO,
        predicted_main_numbers=ticket,
        predicted_special_number=None,
        winning_main_numbers=(1, 2, 3, 4, 5, 6),
        winning_special_number=7,
    )
    assert subject._wins_any_prize(ticket, (1, 2, 3, 4, 5, 6), 7) == actual.is_winner
    assert subject._wins_any_prize(ticket, (1, 2, 3, 4, 5, 6), 7) == (
        hits >= 3 or (hits == 2 and special_hit)
    )


def test_baseline_counts_all_standard_wins() -> None:
    winners = sum(comb(6, hits) * comb(43, 6 - hits) for hits in range(3, 7))
    winners += comb(6, 2) * comb(42, 3)
    assert winners == 432824
    assert winners / comb(49, 6) == subject._ANY_PRIZE_BASELINE


def test_development_special_changes_score_only_after_prediction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(legacy, "_EVOLUTION_MIN_TRAIN", 3)
    candidate = Candidate("two-plus", (1, 2, 7, 20, 21, 22))
    draws = [[1, 2, 3, 4, 5, 6] for _ in range(4)]
    yes = subject._evaluate_any_prize(candidate, draws, (8, 8, 8, 7), n_test=1)
    no = subject._evaluate_any_prize(candidate, draws, (8, 8, 8, 8), n_test=1)
    assert yes.hit_ge3 == 1 and no.hit_ge3 == 0
    assert yes.hits_array == [1] and no.hits_array == [0]
    assert candidate.seen == [draws[:3], draws[:3]]


def test_validation_ranks_any_prize_and_never_passes_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a = Candidate("winner", (1, 2, 7, 20, 21, 22))
    b = Candidate("loser", (1, 2, 8, 20, 21, 22))
    adapter = subject.BigLottoAnyPrizeEvolutionAdapter()
    scores = adapter._validation_scores(rows(551), (a, b))
    assert [score[0] for score in scores] == [50, 0]
    assert [score[1] for score in scores] == [0, 0]
    assert [len(x) for x in a.seen] == list(range(501, 551))
    assert all(all(len(draw) == 6 and 7 not in draw for draw in prefix) for prefix in a.seen)
    monkeypatch.setattr(adapter, "_fit_candidates", lambda _: (a, b))
    assert adapter.get_bets(rows(551), LotteryType.BIG_LOTTO) == (a.ticket, b.ticket)


@pytest.mark.parametrize("special", [None, 0, 50, 1, True])
def test_missing_or_invalid_special_fails_closed(special: object) -> None:
    history = list(rows(551))
    history[500] = replace(history[500], special_number=special)  # type: ignore[arg-type]
    with pytest.raises(InvalidOutput, match="special number"):
        subject.BigLottoAnyPrizeEvolutionAdapter().get_bets(tuple(history), LotteryType.BIG_LOTTO)


def test_cache_key_includes_special_history(monkeypatch: pytest.MonkeyPatch) -> None:
    a = Candidate("a", (1, 2, 7, 20, 21, 22))
    b = Candidate("b", (1, 2, 8, 20, 21, 22))
    adapter = subject.BigLottoAnyPrizeEvolutionAdapter()
    monkeypatch.setattr(adapter, "_fit_candidates", lambda _: (a, b))
    first = adapter.get_bets(rows(551, 7), LotteryType.BIG_LOTTO)
    second = adapter.get_bets(rows(551, 8), LotteryType.BIG_LOTTO)
    assert first[0] == a.ticket and second[0] == b.ticket


def test_history_parser_retains_special_and_rejects_non_integer() -> None:
    parsed = parse_history_json(
        '[{"draw":"123","date":"2020-01-01","numbers":[1,2,3,4,5,6],"special_number":7}]'
    )
    assert parsed[0].special_number == 7
    with pytest.raises(HistoryParseError, match="special_number"):
        parse_history_json(
            '[{"draw":"123","date":"2020-01-01","numbers":[1,2,3,4,5,6],"special_number":true}]'
        )


def test_out_of_order_direct_history_is_rejected() -> None:
    history = list(rows(551))
    history[-1], history[-2] = history[-2], history[-1]
    with pytest.raises(InvalidOutput, match="strictly chronological"):
        subject.BigLottoAnyPrizeEvolutionAdapter().get_bets(tuple(history), LotteryType.BIG_LOTTO)


def test_replay_uses_past_specials_and_redacts_target(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = Candidate("winner", (1, 2, 7, 20, 21, 22))
    adapter = subject.BigLottoAnyPrizeEvolutionAdapter()
    monkeypatch.setattr(adapter, "_fit_candidates", lambda _: (candidate,))
    binding = binding_from_implementation(adapter)
    replay = _OutcomeBlindAdapter(BigLottoReplayAdapter((binding,)))
    history = tuple(
        ReplayDraw(
            LotteryType.BIG_LOTTO,
            row.draw,
            date.fromisoformat(row.date),
            row.numbers,
            row.special_number,
        )
        for row in rows(551)
    )
    target = ReplayDraw(LotteryType.BIG_LOTTO, "100001000", date(2025, 1, 1), (1, 2, 3, 4, 5, 6), 7)
    altered = replace(target, main_numbers=(10, 11, 12, 13, 14, 15), special_number=16)
    assert replay.generate(binding.strategy, history, target) == replay.generate(
        binding.strategy, history, altered
    )
    assert replay.expected_native_ticket_count(binding.strategy, history, target) == 1
    with pytest.raises(ValueError, match="strictly earlier"):
        replay.generate(binding.strategy, (*history, target), target)
