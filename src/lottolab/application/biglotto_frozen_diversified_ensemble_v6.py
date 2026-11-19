"""Historical Wave 58 three-ticket replay of DiversifiedEnsemble.predict_3bets."""

import math
import random
from collections import Counter
from functools import lru_cache

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_constraint_filter import _numpy_pairwise_sum
from lottolab.strategies.adapters.biglotto_wave10 import (
    _bayesian_desc_ticket,
    _betweenness_centrality,
    _calculate_ac_value,
    _degree_centrality,
    _detect_regime,
    _graph_adjacency,
    _v6_frequency_ticket,
)

type History = tuple[CausalDrawRow, ...]
type Ticket = tuple[int, ...]


def _entropy(numbers: Ticket) -> float:
    # The frozen feature analyzer sums the seven gap contributions left to right.
    total = 0.0
    previous = 0
    for number in (*numbers, 49):
        gap = number - previous
        if gap:
            probability = gap / 49
            total -= probability * math.log2(probability)
        previous = number
    return total


def _lower_bound(values: list[float]) -> float:
    mean = _numpy_pairwise_sum(values) / len(values)
    variance = _numpy_pairwise_sum([(value - mean) ** 2 for value in values]) / len(values)
    return mean - 1.5 * math.sqrt(variance)


@lru_cache(maxsize=1)
def _graph_pool(oldest: History) -> Ticket:
    # The caller supplies the same oldest 500 rows to every later target. The
    # donor visits them newest first, which also fixes edge insertion order.
    adjacency = _graph_adjacency(oldest[::-1], lookback=500)
    nodes = list(range(1, 50))
    degree = _degree_centrality(nodes, adjacency)
    between = _betweenness_centrality(nodes, adjacency)
    return tuple(sorted(nodes, key=lambda n: -(0.7 * degree[n] + 0.3 * between[n]))[:20])


def _tail_pool(recent: History) -> Ticket:
    frequencies = Counter(n % 10 for draw in recent for n in draw.numbers)
    # Counter breaks ties by first appearance in the newest-first history.
    hot = {tail for tail, _ in frequencies.most_common(5)}
    pool = tuple(n for n in (*range(1, 50, 2), *range(2, 50, 2)) if n % 10 in hot)
    return pool if len(pool) >= 12 else tuple(range(1, 50))


def _sample(
    rng: random.Random,
    pool: Ticket,
    ac_floor: float,
    entropy_floor: float,
    attempts: int,
    minimum_odds: int = 0,
) -> Ticket:
    for _ in range(attempts):
        ticket = tuple(sorted(rng.sample(pool, 6)))
        if (
            sum(n % 2 for n in ticket) >= minimum_odds
            and _calculate_ac_value(ticket) >= ac_floor
            and _entropy(ticket) >= entropy_floor
        ):
            return ticket
    return tuple(sorted(pool[:6]))


class FrozenDiversifiedEnsembleV6(PortfolioBetAdapter):
    strategy_id = "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d"
    strategy_version = "legacy-source-49a25effa62f-8caaac8fcb5d"
    strategy_name = "大樂透多樣化集成 V6"
    min_history = 1
    native_ticket_count = 3
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict_all(self, history: History, lottery_type: LotteryType) -> tuple[Ticket, ...]:
        # Wave 58 supplies the entire strict prefix explicitly. Its three main
        # tickets share one Python stream. No main-number selector draws from
        # the NumPy stream seeded alongside it in the donor.
        rng = random.Random(42)
        recent = history[-100:][::-1]
        ac_floor = _lower_bound([float(_calculate_ac_value(row.numbers)) for row in recent])
        entropy_floor = _lower_bound([_entropy(row.numbers) for row in recent])
        consensus = tuple(
            sorted(set(_bayesian_desc_ticket(history)) | set(_v6_frequency_ticket(history)))
        )
        odd_floor = 5 if _detect_regime(history) == "SKEWED" else 3
        return (
            _sample(rng, consensus, ac_floor, entropy_floor, 150),
            _sample(rng, _graph_pool(history[:500]), ac_floor, entropy_floor, 150),
            _sample(rng, _tail_pool(recent), ac_floor, entropy_floor, 200, odd_floor),
        )
