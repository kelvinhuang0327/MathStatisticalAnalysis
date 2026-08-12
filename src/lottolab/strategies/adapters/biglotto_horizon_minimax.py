"""Target-native port of the sealed B649 horizon-minimax research producer.

The donor is ``B649_NEXT_GENERATION_STRATEGY_RESEARCH_R1`` task tree
``eb5a18eab2807a89a2f3abd5411c3a28509a982d3060702e5f8cc85b0724ed5a``;
its ``research_strategies.py`` SHA-256 is
``616ca197a53bbabb9e43e42f004b64caab5be58cc51769d091a17a14dfc733ec``.
This port preserves the fixed 30/120/full-prefix horizons, ordinal rank
tie-breaks, consensus-first ticket order, and two-number overlap cap.  It is
deterministic and consumes only validated causal history.

The research result is historical evidence, not a claim of predictive
advantage.  No result rows, target outcomes, filesystem data, database state,
network input, or random source are consulted by this module.
"""

from __future__ import annotations

import math
from collections import Counter

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

_STRATEGY_ID = "b649_new_horizon_minimax_disagreement_r1"
_SHORT_HORIZON = 30
_MIDDLE_HORIZON = 120
_MAXIMUM_CROSS_TICKET_OVERLAP = 2


def _frequency_z_scores(
    history: tuple[CausalDrawRow, ...],
    horizon: int | None,
) -> dict[int, float]:
    """Return the donor-exact per-number frequency z-scores."""

    rule = BIG_LOTTO_RULE_CONTRACT
    selected = history if horizon is None else history[-horizon:]
    draw_count = len(selected)
    counts = Counter(number for draw in selected for number in draw.numbers)
    marginal_rate = rule.main_number_count / rule.main_number_max
    expected = draw_count * marginal_rate
    standard_deviation = math.sqrt(
        draw_count * marginal_rate * (1.0 - marginal_rate)
    )
    return {
        number: (counts.get(number, 0) - expected) / standard_deviation
        for number in range(rule.main_number_min, rule.main_number_max + 1)
    }


def _rank_desc(scores: dict[int, float]) -> dict[int, int]:
    """Assign donor-exact ordinal ranks with number-ascending ties."""

    ordered = sorted(scores, key=lambda number: (-scores[number], number))
    return {number: rank for rank, number in enumerate(ordered, start=1)}


def _horizon_minimax_disagreement(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Build the fixed consensus/disagreement two-ticket barbell."""

    rule = BIG_LOTTO_RULE_CONTRACT
    short = _frequency_z_scores(history, _SHORT_HORIZON)
    middle = _frequency_z_scores(history, _MIDDLE_HORIZON)
    full = _frequency_z_scores(history, None)
    score_sets = (short, middle, full)
    ranks = tuple(_rank_desc(scores) for scores in score_sets)
    number_range = range(rule.main_number_min, rule.main_number_max + 1)

    consensus_order = sorted(
        number_range,
        key=lambda number: (
            max(rank[number] for rank in ranks),
            sum(rank[number] for rank in ranks),
            -sum(scores[number] for scores in score_sets),
            number,
        ),
    )
    consensus = tuple(sorted(consensus_order[: rule.main_number_count]))
    consensus_set = set(consensus)

    disagreement_order = sorted(
        number_range,
        key=lambda number: (
            -abs(short[number] - full[number]),
            -abs(short[number] - middle[number]),
            -short[number],
            number,
        ),
    )
    disagreement_numbers: list[int] = []
    consensus_overlap = 0
    for number in disagreement_order:
        would_overlap = number in consensus_set
        if (
            would_overlap
            and consensus_overlap >= _MAXIMUM_CROSS_TICKET_OVERLAP
        ):
            continue
        disagreement_numbers.append(number)
        consensus_overlap += int(would_overlap)
        if len(disagreement_numbers) == rule.main_number_count:
            break

    disagreement = tuple(sorted(disagreement_numbers))
    return consensus, disagreement


class BigLottoHorizonMinimaxDisagreementAdapter(PortfolioBetAdapter):
    """Deterministic two-ticket horizon-minimax/disagreement portfolio."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Horizon Minimax Disagreement 2注"
    strategy_version = "v0.1"
    min_history = 200
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _horizon_minimax_disagreement(history)


__all__ = ["BigLottoHorizonMinimaxDisagreementAdapter"]
