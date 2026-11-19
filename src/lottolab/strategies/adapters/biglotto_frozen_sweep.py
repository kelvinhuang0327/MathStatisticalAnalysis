"""Six source-ordered configurations of the exhaustive BIG_LOTTO feature sweep."""

from __future__ import annotations

import math
from collections import Counter
from functools import lru_cache

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw, ReplayStrategy
from lottolab.strategies.adapters import biglotto_quad_strike as quad
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_apriori import _apriori_tickets
from lottolab.strategies.adapters.biglotto_batch16 import _gum_cluster_pivot_bets

type History = tuple[CausalDrawRow, ...]
type Portfolio = tuple[tuple[int, ...], ...]


def _two_tickets(ranking: list[int]) -> Portfolio:
    return tuple(sorted(ranking[:6])), tuple(sorted(ranking[6:12]))


def _frequent(history: History, window: int, killed: frozenset[int] = frozenset()) -> Portfolio:
    counts = Counter(n for row in history[-window:] for n in row.numbers if n not in killed)
    return _two_tickets([n for n, _ in counts.most_common(12)])


def _chaos_kills(history: History) -> frozenset[int]:
    last_seen = {n: -1 for n in range(1, 50)}
    entropies = []
    for i, row in enumerate(history):
        for n in row.numbers:
            last_seen[n] = i
        if i >= len(history) - 10:
            bins = [0] * 5
            for seen in last_seen.values():
                gap = i - seen
                bins[sum(gap > edge for edge in (5, 10, 20, 30))] += 1
            entropy = -sum((b / 49) * math.log2(b / 49) for b in bins if b)
            entropies.append(entropy)
    # Least-squares slope for the ten equally spaced snapshots.
    slope = sum((i - 4.5) * e for i, e in enumerate(entropies)) / 82.5
    if entropies[-1] < 2.0 and slope < 0:
        kill = 12
    elif entropies[-1] > 2.2 or slope > 0.02:
        kill = 6
    else:
        kill = 9
    return frozenset(sorted(last_seen, key=last_seen.__getitem__)[:kill])


@lru_cache(maxsize=1)
def _sweep(history: History) -> Portfolio:
    scores = quad._fourier_rhythm_scores(history)
    domain = 49 if max(n for row in history[-500:] for n in row.numbers) > 38 else 38
    ranks = [
        i + 1
        for i in reversed(
            quad._legacy_numpy_argsort(tuple(scores[n] for n in range(1, domain + 1)))
        )
    ]
    coverage = Counter(len({(n - 1) // 7 for n in row.numbers}) for row in history[-200:])
    typical = {zones for zones, _ in coverage.most_common(2)}
    clusters = _gum_cluster_pivot_bets(history, window=150, n_bets=6)
    pruned = [b for b in clusters if len({(n - 1) // 7 for n in b}) in typical]
    zonal = tuple(tuple(b) for b in (pruned or clusters)[:2])
    # The sweep replaces get_draws with its oldest-first history. Apriori takes
    # the first 150 rows of that input, irrespective of the current cutoff.
    associations = _apriori_tickets(tuple(reversed(history[:150])))[:2]
    return (
        *_frequent(history, 100),
        *_frequent(history, 300),
        *_two_tickets(ranks),
        *zonal,
        *_frequent(history, 100, _chaos_kills(history)),
        *associations,
    )


class ExhaustiveFeatureSweep(PortfolioBetAdapter):
    strategy_id = "legacy_biglotto__exhaustive_feature_sweep_v2__ff4096a9e7e5"
    strategy_name = "Exhaustive feature sweep, six two-ticket configurations"
    strategy_version = "legacy-source-49a25effa62f-ff4096a9e7e5"
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    min_history = 1999
    native_ticket_count = 12

    # Zonal pruning may retain one ticket, and Apriori stops if no new
    # antecedent remains. Keep every valid positional ticket the donor emitted.
    minimum_native_ticket_count = 9

    def expected_native_ticket_count(
        self, strategy: ReplayStrategy, history: tuple[ReplayDraw, ...], target: ReplayDraw
    ) -> int:
        rows = tuple(
            CausalDrawRow(d.draw_number, d.draw_date.isoformat(), d.main_numbers) for d in history
        )
        return len(self.get_bets(rows, LotteryType.BIG_LOTTO))

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        return _sweep(history)
