"""Replay the original Wave 62 DiversifiedEnsemble.predict_3bets on a strict draw prefix."""

import math
import random
from collections import Counter
from ctypes import c_float
from itertools import combinations, pairwise
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw, ReplayTicket
from lottolab.strategies.adapters.base import (
    BetAdapterExecution,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
    _resolved_rule,
    _validated_lottery_numbers,
)
from lottolab.strategies.adapters.biglotto_constraint_filter import _numpy_pairwise_sum
from lottolab.strategies.adapters.biglotto_evolution_any_prize import (
    PrizeHistoryRow,
    _validated_prize_history,
)
from lottolab.strategies.adapters.biglotto_wave3 import (
    _unified_bayesian_ticket,
    _unified_frequency_ticket,
)
from lottolab.strategies.adapters.biglotto_wave10 import (
    _betweenness_centrality,
    _calculate_ac_value,
    _degree_centrality,
    _graph_adjacency,
    _v6_frequency_ticket,
)

type History = tuple[PrizeHistoryRow, ...]
type Ticket = tuple[int, ...]
type Graph = dict[int, dict[int, float]]
_NUMBERS = range(1, 50)


def _consensus_pool(history: History, degree: dict[int, float], pruned: set[int]) -> Ticket:
    votes = Counter(_unified_bayesian_ticket(history))
    if history[0].date < history[-1].date:
        votes.update(_unified_frequency_ticket(history))
    else:
        # If all dates tie, the donor's frequency selector takes its DESC branch.
        votes.update(sorted(_v6_frequency_ticket(history[::-1])))
    # The donor reads details.top_cluster_numbers. Its clustering result has no
    # such field, so the 50-draw minimum applies but clustering contributes no votes.
    votes.update(sorted(_NUMBERS, key=degree.__getitem__, reverse=True)[:15])
    triplets = Counter(t for row in history[-150:] for t in combinations(row.numbers, 3))
    repeated = Counter[int]()
    for triplet, count in triplets.items():
        if count >= 2:
            for n in triplet:
                repeated[n] += count
    scores = Counter({n: v * 5 + repeated[n] * 10 for n, v in votes.items() if n not in pruned})
    ranked = [n for n, _ in scores.most_common(12)]
    if len(ranked) < 8:
        ranked.extend(n for n in _NUMBERS if n not in scores and n not in pruned)
    return tuple(ranked[:8])


def _float32_sum(row: list[float]) -> float:
    # NumPy's contiguous reduction over one 49-column float32 transition row.
    partials = row[:8]
    for i in range(8, 48):
        lane = i % 8
        partials[lane] = c_float(partials[lane] + row[i]).value
    pairs = [c_float(a + b).value for a, b in zip(partials[::2], partials[1::2], strict=True)]
    left = c_float(pairs[0] + pairs[1]).value
    right = c_float(pairs[2] + pairs[3]).value
    return c_float(c_float(left + right).value + row[48]).value


def _gnn_base(history: History, graph: Graph) -> Ticket:
    recent = history[-250:]
    counts = Counter(n for row in recent for n in row.numbers)
    hot = Counter(n for row in recent[-30:] for n in row.numbers)
    age: dict[int, int] = {}
    for i, row in enumerate(reversed(recent)):
        for n in row.numbers:
            age.setdefault(n, i)

    features = []
    transitions = []
    for n in _NUMBERS:
        gap = age.get(n, len(recent))
        features.append(
            (
                c_float(counts[n] / len(recent)).value,
                c_float(min(1.0, gap / 30.0)).value,
                c_float(hot[n] / 10.0).value,
                float(hot[n] >= 5),
                float(gap >= 15),
            )
        )
        row = [c_float(graph[n].get(m, 0.0)).value for m in _NUMBERS]
        row[n - 1] = c_float(0.1).value
        total = _float32_sum(row)
        transitions.append([(j, c_float(v / total).value) for j, v in enumerate(row) if v])

    # Three float32 matrix products, with one fused multiply-add per source
    # column. Products of two float32 values are exact in Python's binary64.
    for _ in range(3):
        next_features = []
        for edges in transitions:
            flux = [0.0] * 5
            for j, weight in edges:
                for k, old in enumerate(features[j]):
                    flux[k] = c_float(weight * old + flux[k]).value
            next_features.append(tuple(flux))
        features = next_features
    scores = []
    for feature in features:
        score = 0.0
        for value in feature:
            score = c_float(score + value).value
        scores.append(score)
    return tuple(sorted(sorted(_NUMBERS, key=lambda n: -scores[n - 1])[:6]))


def _structural_flux_pool(
    history: History, graph: Graph, degree: dict[int, float], pruned: set[int]
) -> Ticket:
    base = _gnn_base(history, graph)
    specials = tuple(row.special_number for row in history)
    transitions = Counter(b for a, b in pairwise(specials) if a == specials[-1])
    denominator = transitions.total() + 1
    # The special synergy calls NetworkX without a weight argument. Unit
    # lengths preserve the original neighbor insertion order for shortest paths.
    unweighted = {n: dict.fromkeys(neighbors, 1.0) for n, neighbors in graph.items()}
    between = _betweenness_centrality(list(_NUMBERS), unweighted)
    injected = max(
        (n for n in _NUMBERS if n not in pruned and n not in base),
        key=lambda n: transitions[n] / denominator * 0.4 + between[n] * (1.0 - degree[n]) * 0.6,
    )
    return (*base[:-1], injected)


def _outlier_pool(history: History, degree: dict[int, float], rng: random.Random) -> Ticket:
    recent = Counter(n for row in history[-20:] for n in row.numbers)
    counts = Counter(n for row in history for n in row.numbers)
    max_recent, max_count = max(recent.values()), max(counts.values())
    activity = {n: 0.6 * (recent[n] / max_recent) + 0.4 * (counts[n] / max_count) for n in _NUMBERS}
    pool = sorted(_NUMBERS, key=lambda n: -(1.0 - degree[n]) * (activity[n] + 0.1))[:18]
    best, best_variance = (), -1.0
    for _ in range(50):
        ticket = tuple(sorted(rng.sample(pool, 6)))
        gaps = [b - a for a, b in pairwise(ticket)]
        mean = sum(gaps) / len(gaps)
        variance = _numpy_pairwise_sum([(g - mean) ** 2 for g in gaps]) / len(gaps)
        if variance > best_variance:
            best, best_variance = ticket, variance
    return best


def _stable_candidate(
    pool: Ticket, ac_floor: float, ac_ceiling: float, rng: random.Random
) -> Ticket:
    if len(pool) < 6:
        pool = tuple(_NUMBERS)
    for _ in range(500):
        ticket = tuple(sorted(rng.sample(pool, 6)))
        ac = _calculate_ac_value(ticket)
        if 5.5 <= ac <= 11 and ac_floor <= ac <= ac_ceiling:
            return ticket
    return tuple(sorted(rng.sample(pool, 6)))


class FrozenDiversifiedEnsemble(PortfolioBetAdapter):
    strategy_id = "legacy_biglotto__biglotto_diversified_ensemble__36dbfc14b360"
    strategy_version = "legacy-source-49a25effa62f-36dbfc14b360"
    strategy_name = "大樂透多樣化集成"
    min_history = 50
    minimum_history_closure_reason = "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
    native_ticket_count = 3
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def get_replay_tickets(
        self, history: tuple[ReplayDraw, ...], target: ReplayDraw
    ) -> tuple[ReplayTicket, ...]:
        target_key = target.sort_key
        if target.lottery_type is not LotteryType.BIG_LOTTO or any(
            row.lottery_type is not LotteryType.BIG_LOTTO or row.sort_key >= target_key
            for row in history
        ):
            raise InvalidOutput("Diversified Ensemble requires strictly earlier BIG_LOTTO draws")
        rows = tuple(
            PrizeHistoryRow(
                row.draw_number, row.draw_date.isoformat(), row.main_numbers, row.special_number
            )
            for row in history
        )
        bets = self.get_bets(rows, LotteryType.BIG_LOTTO)
        return tuple(ReplayTicket(i, ticket) for i, ticket in enumerate(bets, 1))

    def get_bets_with_emission(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[BetAdapterExecution, ...]:
        if lottery_type is not LotteryType.BIG_LOTTO:
            raise UnsupportedLotteryType(f"{self.strategy_id}: BIG_LOTTO required")
        rows = _validated_prize_history(history, self.strategy_id)
        if len(rows) < self.min_history:
            raise InsufficientHistory(self.minimum_history_closure_reason)
        rule = _resolved_rule(lottery_type, self.strategy_id)
        return tuple(
            BetAdapterExecution(
                ticket, _validated_lottery_numbers(ticket, self.strategy_id, rule), None
            )
            for ticket in self._predict_all(rows, lottery_type)
        )

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[Ticket, ...]:
        # Wave 62 supplies newest first; the donor stably sorts by date alone.
        rows = tuple(sorted(reversed(cast(History, history)), key=lambda row: row.date))
        graph = _graph_adjacency(rows, lookback=250)
        degree = _degree_centrality(list(_NUMBERS), graph)
        exposure = Counter(n for row in rows[-6:] for n in row.numbers)
        pruned = {n for n, count in exposure.items() if count >= 3}
        ac = [float(_calculate_ac_value(row.numbers)) for row in rows[-100:]]
        mean = _numpy_pairwise_sum(ac) / len(ac)
        std = math.sqrt(_numpy_pairwise_sum([(v - mean) ** 2 for v in ac]) / len(ac))
        floor, ceiling = mean - 1.2 * std, mean + 2.0 * std

        # All three positions consume the same target-local Python stream. The
        # donor seeds NumPy alongside it, but no selected number uses that stream.
        rng = random.Random(42)
        first = _stable_candidate(_consensus_pool(rows, degree, pruned), floor, ceiling, rng)
        second = _stable_candidate(
            _structural_flux_pool(rows, graph, degree, pruned), floor, ceiling, rng
        )
        # Removing pruned numbers from the donor's six-number outlier pool
        # triggers its fallback to the original six, so the pool is always intact.
        third = _stable_candidate(_outlier_pool(rows, degree, rng), floor, ceiling, rng)
        return first, second, third
