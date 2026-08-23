"""Target-native port of the legacy frontend Bayesian strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/BayesianStrategy.js``.
Its frontend data is newest-first, while LottoLab causal histories are
oldest-first, so the adapter reverses the validated history before applying
the donor's Bayesian updating (combining prior frequency with conditional
transition probabilities). The donor emits one ascending six-number ticket; its
extra probability/report fields have no counterpart in the native single-ticket
response and are intentionally not invented here.
"""

from __future__ import annotations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_MIN_NUM = 1
_MAX_NUM = 49
_PICK = 6


class BigLottoFrontendBayesianAdapter(BetAdapter):
    """Reproduce ``BayesianStrategy.predict`` for Big Lotto single tickets."""

    strategy_id = "legacy_biglotto__frontend_bayesian_strategy__baa3045817fb"
    strategy_name = "大樂透 Frontend Bayesian 策略"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Apply the donor's newest-first Bayesian prior + likelihood transition semantics."""

        newest_first = tuple(reversed(history))
        total_draws = len(newest_first)

        frequency: dict[int, int] = {
            number: 0 for number in range(_MIN_NUM, _MAX_NUM + 1)
        }
        for draw in newest_first:
            for number in draw.numbers:
                if number in frequency:
                    frequency[number] += 1

        prior_prob = {
            number: frequency[number] / (total_draws * _PICK)
            for number in range(_MIN_NUM, _MAX_NUM + 1)
        }

        last_draw = newest_first[0].numbers

        transition_counts: dict[int, dict[int, int]] = {}
        for i in range(total_draws - 1):
            current = newest_first[i].numbers
            prev = newest_first[i + 1].numbers
            for p in prev:
                if p not in transition_counts:
                    transition_counts[p] = {}
                for c in current:
                    transition_counts[p][c] = transition_counts[p].get(c, 0) + 1

        probabilities: dict[int, float] = {}
        for i in range(_MIN_NUM, _MAX_NUM + 1):
            likelihood_score = 0.0
            for prev_num in last_draw:
                count = transition_counts.get(prev_num, {}).get(i, 0)
                total_occurrences = frequency[prev_num] if frequency[prev_num] > 0 else 1
                likelihood_score += count / total_occurrences
            probabilities[i] = prior_prob[i] * (1.0 + likelihood_score)

        total_prob = sum(probabilities.values())
        if total_prob > 0.0:
            for i in range(_MIN_NUM, _MAX_NUM + 1):
                probabilities[i] = probabilities[i] / total_prob
        else:
            uniform = 1.0 / (_MAX_NUM - _MIN_NUM + 1)
            for i in range(_MIN_NUM, _MAX_NUM + 1):
                probabilities[i] = uniform

        # In JS: Object.entries() enumerates integer-like keys in ascending order
        # and JS sort is stable, keeping ascending order for equal probabilities.
        ranked = sorted(
            probabilities.items(),
            key=lambda item: (-item[1], item[0]),
        )[:_PICK]
        return tuple(sorted(number for number, _probability in ranked))
