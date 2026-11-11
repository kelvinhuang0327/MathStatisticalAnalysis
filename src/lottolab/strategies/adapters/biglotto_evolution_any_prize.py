"""Evolution v0.5: chronological training and validation on any standard prize."""

# This adapter deliberately subclasses the frozen legacy engine and strategies
# to preserve its candidate generation while changing the scoring objective.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from datetime import date
from itertools import pairwise
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw, ReplayStrategy, ReplayTicket
from lottolab.strategies.adapters import biglotto_batch16 as legacy
from lottolab.strategies.adapters.base import (
    BetAdapterExecution,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
    validated_history,
)
from lottolab.strategies.adapters.biglotto_evolution_bounded import (
    BigLottoBoundedEvolutionAdapter,
    _BoundedDevelopmentEngine,
)
from lottolab.strategies.adapters.biglotto_evolution_causal import (
    _HOLDOUT_SIZE,
    _candidate_identity,
    _valid_ticket,
)
from lottolab.strategies.adapters.biglotto_evolution_strict import DevelopmentPredictionFailure

# Probability that one uniformly random 6/49 ticket wins at least one of the
# standard prizes, including exactly two main numbers plus the special number.
_ANY_PRIZE_BASELINE = 432824 / 13983816


def _wins_any_prize(
    ticket: list[int] | tuple[int, ...], main: tuple[int, ...] | list[int], special: int
) -> bool:
    hits = len(set(ticket).intersection(main))
    return hits >= 3 or (hits == 2 and special in ticket)


def _validated_prize_history(history: object, strategy_id: str) -> tuple[CausalDrawRow, ...]:
    """Validate every historical outcome; missing special numbers are unknown, not misses."""
    canonical = validated_history(history, strategy_id, lottery_type=LotteryType.BIG_LOTTO)
    assert type(history) is tuple  # enforced by validated_history
    raw_history = cast(tuple[CausalDrawRow, ...], history)
    result: list[CausalDrawRow] = []
    for index, (raw, row) in enumerate(zip(raw_history, canonical, strict=True)):
        special = raw.special_number
        if type(special) is not int or not 1 <= special <= 49 or special in row.numbers:
            raise InvalidOutput(
                f"{strategy_id}: invalid or missing historical special number at {index}"
            )
        result.append(CausalDrawRow(row.draw, row.date, row.numbers, special))
    try:
        keys = tuple((date.fromisoformat(row.date), int(row.draw)) for row in result)
    except ValueError as exc:
        raise InvalidOutput(
            f"{strategy_id}: history must use dated numeric draw identifiers"
        ) from exc
    if any(first >= second for first, second in pairwise(keys)):
        raise InvalidOutput(f"{strategy_id}: history must be strictly chronological")
    return tuple(result)


def _evaluate_any_prize(
    strategy: legacy._EvoStrategy,
    draws: list[list[int]],
    specials: tuple[int, ...],
    n_test: int = legacy._EVOLUTION_N_TEST,
) -> legacy._EvoMetrics:
    if len(draws) != len(specials):
        raise ValueError("development outcomes must align")
    total = len(draws)
    actual_n_test = min(n_test, total - legacy._EVOLUTION_MIN_TRAIN)
    if actual_n_test <= 0:
        raise DevelopmentPredictionFailure("INSUFFICIENT_DEVELOPMENT_HISTORY")
    sample_count = min(actual_n_test, 200)
    if sample_count == 1:
        indices = [legacy._EVOLUTION_MIN_TRAIN]
    else:
        step = (total - 1 - legacy._EVOLUTION_MIN_TRAIN) / (sample_count - 1)
        indices = [int(legacy._EVOLUTION_MIN_TRAIN + step * i) for i in range(sample_count)]
    wins: list[int] = []
    recent_overlap_count = 0
    for index in indices:
        try:
            prediction = strategy.predict(draws[:index], 6)
        except Exception as exc:
            raise DevelopmentPredictionFailure("PREDICTION_" + type(exc).__name__) from exc
        if not _valid_ticket(prediction):
            raise DevelopmentPredictionFailure("INVALID_TICKET")
        if len(set(prediction).intersection(draws[index - 1])) >= 4:
            recent_overlap_count += 1
        wins.append(int(_wins_any_prize(prediction, draws[index], specials[index])))
    rate = sum(wins) / len(wins)
    penalty = 0.5 if recent_overlap_count > len(indices) * 0.1 else 0.0
    # Legacy field names are retained for the engine interface; both values and
    # hits_array here represent the standard any-prize event, not main >= 3.
    return legacy._EvoMetrics(
        rate, rate - _ANY_PRIZE_BASELINE - penalty, recent_overlap_count > 0, wins
    )


class _AnyPrizeDevelopmentEngine(_BoundedDevelopmentEngine):
    def __init__(self, draws: list[list[int]], specials: tuple[int, ...], seed: int = 42) -> None:
        super().__init__(draws, seed)
        if len(draws) != len(specials):
            raise ValueError("development outcomes must align")
        self.specials = specials

    def evaluate_population(self, n_test: int = legacy._EVOLUTION_N_TEST) -> None:
        self.results = []
        rejected: set[str] = set()
        for candidate in self.population:
            key = _candidate_identity(candidate)
            if key in rejected:
                continue
            try:
                metrics = _evaluate_any_prize(candidate, self.draws, self.specials, n_test)
            except DevelopmentPredictionFailure as exc:
                rejected.add(key)
                self.development_failures[str(exc)] += 1
                continue
            result = legacy._EvoResult(
                name=candidate.name,
                strategy_ref=candidate,
                relative_random_edge=metrics.edge_ge3,
                hit_ge3=metrics.hit_ge3,
                leakage_flag=metrics.leakage_flag,
                hits_array=metrics.hits_array,
            )
            self.results.append(result)
            if result.relative_random_edge > 0.001 and not metrics.leakage_flag:
                self.hof_hits[self._strategy_key(candidate)] = metrics.hits_array
        if rejected:
            self.population = [s for s in self.population if _candidate_identity(s) not in rejected]
            self.results = [
                r for r in self.results if _candidate_identity(r.strategy_ref) not in rejected
            ]
            self.hall_of_fame = [
                r for r in self.hall_of_fame if _candidate_identity(r.strategy_ref) not in rejected
            ]


class BigLottoAnyPrizeEvolutionAdapter(BigLottoBoundedEvolutionAdapter):
    """Fixed-seed, frozen-candidate any-prize selection on past complete outcomes."""

    strategy_version = "v0.5"

    def _fit_candidates(
        self, development: tuple[CausalDrawRow, ...]
    ) -> tuple[legacy._EvoStrategy, ...]:
        specials: list[int] = []
        for row in development:
            special = row.special_number
            if type(special) is not int:
                raise InvalidOutput(f"{self.strategy_id}: missing development special number")
            specials.append(special)
        engine = _AnyPrizeDevelopmentEngine(
            [list(row.numbers) for row in development],
            tuple(specials),
            seed=42,
        )
        engine.initialize()
        for _ in range(10):
            engine.evolve_one_generation()
        self.last_development_failures = dict(engine.development_failures)
        candidates = [r.strategy_ref for r in engine.hall_of_fame] or list(engine.population)
        unique: dict[str, legacy._EvoStrategy] = {}
        for candidate in candidates:
            unique.setdefault(_candidate_identity(candidate), candidate)
        return tuple(unique.values())

    def _validation_scores(
        self, history: tuple[CausalDrawRow, ...], candidates: tuple[legacy._EvoStrategy, ...]
    ) -> tuple[tuple[int, int, str, legacy._EvoStrategy], ...]:
        first = len(history) - _HOLDOUT_SIZE
        draws = [list(row.numbers) for row in history]
        prefixes = tuple(draws[:index] for index in range(first, len(history)))
        scores: list[tuple[int, int, str, legacy._EvoStrategy]] = []
        for candidate in candidates:
            wins = 0
            for index in range(first, len(history)):
                try:
                    prediction = candidate.predict(prefixes[index - first], 6)
                except Exception:
                    break
                if not _valid_ticket(prediction):
                    break
                special = history[index].special_number
                if type(special) is not int:
                    raise InvalidOutput(f"{self.strategy_id}: missing validation special number")
                wins += int(_wins_any_prize(prediction, history[index].numbers, special))
            else:
                # Equal win counts use the deterministic full candidate identity;
                # no old main-number hit score participates in ranking.
                scores.append((wins, 0, _candidate_identity(candidate), candidate))
        return tuple(scores)

    def get_bets_with_emission(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[BetAdapterExecution, ...]:
        if lottery_type is not LotteryType.BIG_LOTTO:
            raise UnsupportedLotteryType(f"{self.strategy_id}: BIG_LOTTO required")
        rows = _validated_prize_history(history, self.strategy_id)
        if len(rows) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, got {len(rows)}"
            )
        predictions = self._predict_all(rows, lottery_type)
        minimum, maximum = self.native_ticket_count_bounds()
        if not minimum <= len(predictions) <= maximum or not all(
            _valid_ticket(t) for t in predictions
        ):
            raise InvalidOutput(f"{self.strategy_id}: invalid portfolio")
        return tuple(BetAdapterExecution(tuple(t), tuple(sorted(t)), None) for t in predictions)

    @staticmethod
    def _rows(history: tuple[ReplayDraw, ...], target: ReplayDraw) -> tuple[CausalDrawRow, ...]:
        if any(
            d.lottery_type is not LotteryType.BIG_LOTTO or d.sort_key >= target.sort_key
            for d in history
        ):
            raise ValueError("strategy requires strictly earlier BIG_LOTTO history")
        if any(a.sort_key >= b.sort_key for a, b in pairwise(history)):
            raise ValueError("history must be strictly chronological")
        return tuple(
            CausalDrawRow(d.draw_number, d.draw_date.isoformat(), d.main_numbers, d.special_number)
            for d in history
        )

    def expected_native_ticket_count(
        self, strategy: ReplayStrategy, history: tuple[ReplayDraw, ...], target: ReplayDraw
    ) -> int:
        if strategy.strategy_id != self.strategy_id:
            raise ValueError("strategy identity mismatch")
        return len(self.get_bets(self._rows(history, target), LotteryType.BIG_LOTTO))

    def get_replay_tickets(
        self, history: tuple[ReplayDraw, ...], target: ReplayDraw
    ) -> tuple[ReplayTicket, ...]:
        tickets = self.get_bets(self._rows(history, target), LotteryType.BIG_LOTTO)
        return tuple(ReplayTicket(i, ticket) for i, ticket in enumerate(tickets, 1))
