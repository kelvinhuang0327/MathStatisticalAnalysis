"""Evolution Engine v0.2 with a frozen, chronologically held-out selector.

Evolution runs only on the development prefix. Candidate strategies are
frozen before the 50-period validation segment begins. Each validation
prediction uses a strictly earlier prefix; only after validation are candidates
ranked for the next outer target. The legacy v0.1 adapter is unchanged.
"""

from __future__ import annotations

import json
from typing import Any

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayBehavior, ReplayDraw, ReplayStrategy
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter, RejectPrediction
from lottolab.strategies.adapters.biglotto_batch16 import _EvolutionEngine, _EvoStrategy

_HOLDOUT_SIZE = 50
_SEED = 42
SEED_CONTRACT = "evolution-engine-local-seed-42-v1"


def _candidate_identity(strategy: _EvoStrategy) -> str:
    """Include full nested strategy identity, not truncated display names."""

    def describe(item: _EvoStrategy) -> dict[str, Any]:
        data: dict[str, Any] = {
            "class": type(item).__qualname__,
            "name": item.name,
            "params": item.params,
        }
        nested = getattr(item, "strategies", None)
        if nested is not None:
            data["strategies"] = [describe(child) for child in nested]
        base = getattr(item, "base", None)
        if base is not None:
            data["base"] = describe(base)
        return data

    return json.dumps(describe(strategy), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _valid_ticket(ticket: object) -> bool:
    return (
        type(ticket) in (list, tuple)
        and len(ticket) == 6
        and all(type(n) is int and 1 <= n <= 49 for n in ticket)
        and len(set(ticket)) == 6
    )


class BigLottoCausalEvolutionAdapter(PortfolioBetAdapter):
    """Evolve on development data; select frozen candidates on later data."""

    strategy_id = "legacy_biglotto__evolution_engine__3df019c31ce4"
    strategy_name = "大樂透 策略族群演化系統"
    strategy_version = "v0.2"
    min_history = 551
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 10
    minimum_native_ticket_count = 1
    maximum_native_ticket_count = 10
    replay_behavior = ReplayBehavior.SEEDED_STOCHASTIC
    replay_seed_contract = SEED_CONTRACT

    def __init__(self) -> None:
        self._cached_history: tuple[CausalDrawRow, ...] | None = None
        self._cached_portfolio: tuple[tuple[int, ...], ...] | None = None

    def _fit_candidates(self, development: tuple[CausalDrawRow, ...]) -> tuple[_EvoStrategy, ...]:
        engine = _EvolutionEngine([list(row.numbers) for row in development], seed=_SEED)
        engine.initialize()
        for _ in range(10):
            engine.evolve_one_generation()
        candidates = [result.strategy_ref for result in engine.hall_of_fame]
        if not candidates:
            candidates = list(engine.population)
        unique: dict[str, _EvoStrategy] = {}
        for candidate in candidates:
            unique.setdefault(_candidate_identity(candidate), candidate)
        return tuple(unique.values())

    def _validation_scores(
        self, history: tuple[CausalDrawRow, ...], candidates: tuple[_EvoStrategy, ...]
    ) -> tuple[tuple[int, int, str, _EvoStrategy], ...]:
        first = len(history) - _HOLDOUT_SIZE
        scores: list[tuple[int, int, str, _EvoStrategy]] = []
        draws = [list(row.numbers) for row in history]
        prefixes = tuple(draws[:index] for index in range(first, len(history)))
        for candidate in candidates:
            success = 0
            total_hits = 0
            for index in range(first, len(history)):
                prefix = prefixes[index - first]
                try:
                    prediction = candidate.predict(prefix, 6)
                except Exception:
                    break
                if not _valid_ticket(prediction):
                    break
                hits = len(set(prediction).intersection(history[index].numbers))
                success += int(hits >= 3)
                total_hits += hits
            else:
                scores.append((success, total_hits, _candidate_identity(candidate), candidate))
        return tuple(scores)

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        del lottery_type
        if history == self._cached_history and self._cached_portfolio is not None:
            return self._cached_portfolio
        development = history[:-_HOLDOUT_SIZE]
        candidates = self._fit_candidates(development)
        scores = self._validation_scores(history, candidates)
        ordered = sorted(scores, key=lambda row: (-row[0], -row[1], row[2]))
        predictions: list[tuple[int, ...]] = []
        draws = [list(row.numbers) for row in history]
        for _, _, _, candidate in ordered:
            try:
                prediction = candidate.predict(draws, 6)
            except Exception:
                continue
            if _valid_ticket(prediction):
                predictions.append(tuple(prediction))
            if len(predictions) == self.native_ticket_count:
                break
        if not predictions:
            raise RejectPrediction(f"{self.strategy_id}: no complete held-out candidate")
        portfolio = tuple(predictions)
        self._cached_history = history
        self._cached_portfolio = portfolio
        return portfolio

    def expected_native_ticket_count(
        self, strategy: ReplayStrategy, history: tuple[ReplayDraw, ...], target: ReplayDraw
    ) -> int:
        if strategy.strategy_id != self.strategy_id or any(
            d.sort_key >= target.sort_key for d in history
        ):
            raise ValueError("strategy or causal history mismatch")
        rows = tuple(
            CausalDrawRow(d.draw_number, d.draw_date.isoformat(), d.main_numbers) for d in history
        )
        return len(self.get_bets(rows, LotteryType.BIG_LOTTO))
