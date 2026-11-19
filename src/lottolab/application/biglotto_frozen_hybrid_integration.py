"""Replay the four local BIG_LOTTO selectors from the frozen hybrid benchmark."""

from collections import Counter

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter


class FrozenHybridIntegrationBenchmark(PortfolioBetAdapter):
    strategy_id = "legacy_biglotto__hybrid_integration_benchmark__5789ca885422"
    strategy_version = "legacy-source-49a25effa62f-5789ca885422"
    strategy_name = "大樂透 Hybrid Integration Benchmark"
    min_history = 1
    native_ticket_count = 12
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        # Source histories are recent-first. Unseen numbers tie at the full
        # history length, and equal scores retain ascending zone order.
        gaps = dict.fromkeys(range(1, 50), len(history))
        unseen = set(gaps)
        for age, row in enumerate(reversed(history)):
            for number in unseen.intersection(row.numbers):
                gaps[number] = age
                unseen.remove(number)
            if not unseen:
                break

        frequency = Counter(number for row in history[-50:] for number in row.numbers)
        # Each number contributes to five pairs on every legal six-number
        # draw. Its total pair co-occurrence therefore ranks as its count.
        entropy = Counter(number for row in history[-100:] for number in row.numbers)
        zones = (range(1, 17), range(17, 33), range(33, 50))
        portfolios = []
        for scores, descending in ((frequency, True), (gaps, True), (entropy, False)):
            zone_bets = []
            for zone in zones:
                ranked = sorted(zone, key=scores.__getitem__, reverse=descending)
                zone_bets.append(tuple(sorted(ranked[:6])))
            portfolios.append(tuple(zone_bets))
        frequency_bets, gap_bets, entropy_bets = portfolios
        mixed_bets = (frequency_bets[0], gap_bets[1], entropy_bets[2])
        return frequency_bets + gap_bets + entropy_bets + mixed_bets
