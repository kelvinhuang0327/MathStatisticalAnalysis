"""Target-native port of the legacy frontend Monte Carlo strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/MonteCarloStrategy.js``.
It builds an ascending, frequency-weighted number pool, runs 10,000 simulated
six-number draws, and returns the six highest marginal inclusion counts.  The
legacy confidence, method, report, and probability-map fields have no
counterpart in LottoLab's native single-ticket response.

The production frontend StatisticsService exposes ``calculateFrequency`` as
an async method even though this donor consumes it synchronously.  The donor
algorithm was genuinely revived with a bounded synchronous statistics seam;
this adapter reproduces that frequency map from caller-supplied causal history
and never opens a database.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from typing import Final, Protocol

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_STRATEGY_ID: Final = "legacy_biglotto__frontend_monte_carlo_strategy__9d8fe030546e"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_SIMULATION_COUNT: Final = 10_000


class _RandomSource(Protocol):
    """The one random operation used by the donor's ``Math.random`` calls."""

    def random(self) -> float:
        """Return one unseeded value in the half-open interval [0, 1)."""

        ...


def _frequency_pool(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Build the donor's ascending pool with exact floored repeat counts."""

    frequency = Counter(number for row in history for number in row.numbers)
    total_draws = len(history)
    pool: list[int] = []
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        weight = 1 + (frequency.get(number, 0) / total_draws) * 10
        pool.extend([number] * math.floor(weight * 10))
    return tuple(pool)


class BigLottoFrontendMonteCarloAdapter(BetAdapter):
    """Reproduce ``MonteCarloStrategy.predict`` for one Big Lotto ticket."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Frontend Monte Carlo Strategy"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def __init__(self, rng: _RandomSource | None = None) -> None:
        # The source uses process-global, unseeded Math.random.  The module
        # default preserves that behavior; the narrow seam makes exact donor
        # parity testable without adding a production seed or dependency.
        self._rng: _RandomSource = random if rng is None else rng

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Run the donor's weighted 10,000-draw marginal simulation."""

        del lottery_type
        pool = _frequency_pool(history)
        simulation_results = {
            number: 0 for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        }

        for _ in range(_SIMULATION_COUNT):
            simulated_draw: set[int] = set()
            while len(simulated_draw) < _PICK_COUNT:
                random_index = math.floor(self._rng.random() * len(pool))
                simulated_draw.add(pool[random_index])
            for number in simulated_draw:
                simulation_results[number] += 1

        probabilities = {
            number: count / _SIMULATION_COUNT
            for number, count in simulation_results.items()
        }
        ranked = sorted(
            probabilities,
            key=lambda number: (-probabilities[number], number),
        )
        return tuple(sorted(ranked[:_PICK_COUNT]))


__all__ = ["BigLottoFrontendMonteCarloAdapter"]
