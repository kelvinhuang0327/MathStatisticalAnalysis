"""Replay the six frozen BIG_LOTTO Zone Split configurations in Wave 60 order."""

import math
import random
from collections import Counter

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_constraint_filter import _numpy_pairwise_sum

_ZONES = (range(1, 17), range(17, 33), range(33, 50))


def _sample(rng: random.Random, zone: range) -> tuple[int, ...]:
    return tuple(sorted(rng.sample(zone, 6)))


def _centered_zone(center: int) -> range:
    return range(max(1, center - 5), min(50, center + 6))


def _adaptive_centers(recent: tuple[CausalDrawRow, ...]) -> tuple[int, int, int]:
    numbers = [n for row in recent[:30] for n in row.numbers]
    # Integer values sum exactly. Match NumPy's float64 reduction order for std
    # before truncating the centers at the donor's integer boundaries.
    mean = sum(numbers) / len(numbers)
    centered = [n - mean for n in numbers]
    std = math.sqrt(_numpy_pairwise_sum([x * x for x in centered]) / len(numbers))
    return max(6, int(mean - std)), int(mean), min(44, int(mean + std))


class FrozenZoneSplitOptimizer(PortfolioBetAdapter):
    strategy_id = "legacy_biglotto__zone_split_optimizer__0bf85e3e1517"
    strategy_version = "legacy-source-49a25effa62f-0bf85e3e1517"
    strategy_name = "大樂透 Zone Split Optimizer"
    min_history = 1
    native_ticket_count = 18
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        return history[-50:]

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        # Wave 60 restarts one Python random stream per target and shares it
        # across the six variants. Frequency selects deterministically.
        rng = random.Random(42)
        recent = history[::-1]
        tickets = [_sample(rng, zone) for zone in _ZONES]
        counts = Counter(n for row in recent for n in row.numbers)
        for zone in _ZONES:
            ranked = sorted(zone, key=counts.__getitem__, reverse=True)
            tickets.append(tuple(sorted(ranked[:6])))

        for overlap in (3, 5):
            for center in (8, 24, 40):
                zone = range(max(1, center - 8 - overlap), min(49, center + 8 + overlap) + 1)
                tickets.append(_sample(rng, zone))

        phi = 1.618033988749895
        for i in (1, 2, 3):
            center = max(4, min(46, int(49 * (i / 4) ** (1 / phi))))
            tickets.append(_sample(rng, _centered_zone(center)))

        for center in _adaptive_centers(recent):
            tickets.append(_sample(rng, _centered_zone(center)))
        return tuple(tickets)
