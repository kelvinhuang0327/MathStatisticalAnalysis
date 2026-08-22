"""Target-native port of the legacy frontend Markov strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/MarkovStrategy.js``.
Its frontend data is newest-first, while LottoLab causal histories are
oldest-first, so the adapter reverses the validated history before applying
the donor's transition construction. The donor emits one ascending six-number
ticket; its extra probability/report fields have no counterpart in the native
single-ticket response and are intentionally not invented here.
"""

from __future__ import annotations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_MIN_NUM = 1
_MAX_NUM = 49
_PICK = 6


class BigLottoFrontendMarkovAdapter(BetAdapter):
    """Reproduce ``MarkovStrategy.predict`` for Big Lotto single tickets."""

    strategy_id = "legacy_biglotto__frontend_markov_strategy__2fc1cafea55c"
    strategy_name = "大樂透 Frontend Markov Chain"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Apply the donor's newest-first transition and ranking semantics."""

        newest_first = tuple(reversed(history))
        transition_matrix = {
            current: {next_number: 0 for next_number in range(_MIN_NUM, _MAX_NUM + 1)}
            for current in range(_MIN_NUM, _MAX_NUM + 1)
        }

        # The donor loops from the oldest source row toward the newest row,
        # counting every current-number -> next-number pair.
        for index in range(len(newest_first) - 1, 0, -1):
            current_draw = newest_first[index].numbers
            next_draw = newest_first[index - 1].numbers
            for current_number in current_draw:
                for next_number in next_draw:
                    transition_matrix[current_number][next_number] += 1

        last_draw = newest_first[0].numbers
        next_probabilities = {
            number: 0.0 for number in range(_MIN_NUM, _MAX_NUM + 1)
        }
        for previous_number in last_draw:
            transitions = transition_matrix[previous_number]
            total_transitions = sum(transitions.values()) or 1
            for next_number in range(_MIN_NUM, _MAX_NUM + 1):
                next_probabilities[next_number] += (
                    transitions[next_number] / total_transitions
                )

        total_probability = sum(next_probabilities.values())
        if total_probability > 0:
            next_probabilities = {
                number: probability / total_probability
                for number, probability in next_probabilities.items()
            }
        else:
            # This is the donor's reachable fallback when no latest-draw
            # number has an observed outgoing transition.
            uniform_probability = 1 / (_MAX_NUM - _MIN_NUM + 1)
            next_probabilities = dict.fromkeys(
                next_probabilities, uniform_probability
            )

        # Object.entries() enumerates integer-like keys in ascending order and
        # the donor's stable sort keeps that order for equal probabilities.
        ranked = sorted(
            next_probabilities.items(),
            key=lambda item: (-item[1], item[0]),
        )[:_PICK]
        return tuple(sorted(number for number, _probability in ranked))
