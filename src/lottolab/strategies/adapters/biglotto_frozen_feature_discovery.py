"""Three selections from the frozen feature-discovery retrospective's causal functions."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from functools import lru_cache
from itertools import pairwise

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter, RejectPrediction
from lottolab.strategies.adapters.biglotto_constraint_filter import _numpy_pairwise_sum
from lottolab.strategies.adapters.biglotto_wave12 import LegacyNumpyRandomState

type History = tuple[CausalDrawRow, ...]
type Ticket = tuple[int, ...]
NUMBERS = range(1, 50)


def _entropy_score(bits: list[int]) -> float:
    p = sum(bits) / len(bits)
    base = -(p * math.log2(p) + (1 - p) * math.log2(1 - p)) if 0 < p < 1 else 0.0
    contexts: defaultdict[tuple[int, ...], list[int]] = defaultdict(lambda: [0, 0])
    for i in range(3, len(bits)):
        contexts[tuple(bits[i - 3 : i])][bits[i]] += 1
    conditional = 0.0
    for counts in contexts.values():
        total = sum(counts)
        entropy = 0.0
        for count in counts:
            if count:
                prob = count / total
                entropy -= prob * math.log2(prob)
        conditional += total / (len(bits) - 3) * entropy
    current = contexts.get(tuple(bits[-3:]))
    next_prob = current[1] / sum(current) if current else p
    return (base - conditional) * 2 + next_prob * 3


def _structural(rows: History, scores: list[float]) -> Ticket:
    sums = [sum(row.numbers) for row in rows]
    mean = sum(sums) / len(sums)
    sd = math.sqrt(_numpy_pairwise_sum([(s - mean) ** 2 for s in sums]) / len(rows))
    trend = sum(sums[-5:]) / 5 - mean
    lower, upper = int(mean + 0.5 * trend - 0.3 * sd), int(mean + 0.5 * trend + 1.5 * sd)
    zone_mean = sum(n >= 34 for row in rows[-5:] for n in row.numbers) / 5
    zone_low, zone_high = max(1, int(zone_mean - 0.5)), min(6, int(zone_mean + 1.5))
    consec = sum(b == a + 1 for row in rows[-5:] for a, b in pairwise(sorted(row.numbers))) / 5
    total = _numpy_pairwise_sum(scores)
    weights = [s / total for s in scores]
    rng = LegacyNumpyRandomState(42)
    best = None
    best_score = -999.0
    pool = list(NUMBERS)
    for _ in range(100_000):
        bet = sorted(rng.choice_without_replacement(pool, 6, probabilities=weights))
        s = sum(bet)
        zone = sum(n >= 34 for n in bet)
        if not lower <= s <= upper or not zone_low <= zone <= zone_high:
            continue
        score = -abs(s - (mean + trend)) * 0.01 - abs(zone - zone_mean) * 0.5
        if consec > 0.5:
            score += sum(b == a + 1 for a, b in pairwise(bet)) * 0.3
        quality = 0.0
        for n in bet:
            quality += scores[n - 1]
        score += quality * 0.1
        if score > best_score:
            best_score, best = score, tuple(bet)
    if best is None:
        raise RejectPrediction("No sampled combination satisfied the source structural constraints")
    return best


@lru_cache(maxsize=1)
def _feature_tickets(history: History) -> tuple[Ticket, ...]:
    rows = history[-50:]
    freq = Counter(n for row in rows for n in row.numbers)
    long_freq = Counter(n for row in history[-200:] for n in row.numbers)
    entropy, structural, cold = {}, [], {}
    for n in NUMBERS:
        bits = [int(n in row.numbers) for row in rows]
        entropy[n] = _entropy_score(bits)
        gap = bits[::-1].index(1) if 1 in bits else len(rows)
        structural.append(freq[n] / (len(rows) * 6 / 49) * 0.4 + gap / 10 * 0.3 + 0.3)
        correction = max(0.0, long_freq[n] / 200 - freq[n] / len(rows))
        echo = 1.5 * (n in rows[-2].numbers) + 0.5 * (n in rows[-1].numbers)
        cold[n] = gap / (49 / 6) * 0.6 + correction * 5 + echo
    return (
        tuple(sorted(sorted(NUMBERS, key=entropy.__getitem__, reverse=True)[:6])),
        _structural(rows, structural),
        tuple(sorted(sorted(NUMBERS, key=cold.__getitem__, reverse=True)[:6])),
    )


class FeatureDiscovery(PortfolioBetAdapter):
    strategy_id = "legacy_biglotto__feature_discovery_and_retrospective__e2ea8b18945d"
    strategy_name = "Entropy, structural constraints and cold reversion with lag-two echo"
    strategy_version = "legacy-source-49a25effa62f-e2ea8b18945d"
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    min_history = 2131
    native_ticket_count = 3

    def _predict_all(self, history: History, lottery_type: LotteryType) -> tuple[Ticket, ...]:
        return _feature_tickets(history)
