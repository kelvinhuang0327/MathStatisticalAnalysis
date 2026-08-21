"""Target-native port of the frozen BIG_LOTTO Apriori predictor.

The donor is ``tools/predict_biglotto_apriori.py`` at legacy commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` (blob
``53222aacf71474fb25487ea625e0e9519760a75a``, SHA-256
``cda690ae84c2324b5f7d160a68e0ba3cf65d6073ecfc5c28ef48402b07018e7b``).
Its exact frozen-source behavior is retained by
``legacy_source_native_portfolios_wave7`` and the Wave-7 parity evidence.

The donor consumes recent-first history, mines singleton/pair/trio itemsets
with support count at least three, retains association rules with confidence
at least 0.4, and emits up to seven tickets from distinct antecedents in
source order. Successful retained executions contain every cardinality from
two through seven. There is no random fallback: too few rules fails closed
through the bounded portfolio contract.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw, ReplayStrategy
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

_STRATEGY_ID = "legacy_biglotto__predict_biglotto_apriori__cda690ae84c2"
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_HISTORY_WINDOW = 150
_MINIMUM_SUPPORT_COUNT = 3
_MINIMUM_CONFIDENCE = 0.4
_MAXIMUM_NATIVE_TICKET_COUNT = 7


@dataclass(frozen=True, slots=True)
class _Rule:
    antecedent: tuple[int, ...]
    consequent: int
    confidence: float


def _frequent_itemsets(
    history: tuple[tuple[int, ...], ...],
) -> dict[tuple[int, ...], int]:
    counts: defaultdict[tuple[int, ...], int] = defaultdict(int)
    for draw in history:
        numbers = sorted(draw)
        for number in numbers:
            counts[(number,)] += 1
        for pair in combinations(numbers, 2):
            counts[pair] += 1
        for trio in combinations(numbers, 3):
            counts[trio] += 1
    return {itemset: count for itemset, count in counts.items() if count >= _MINIMUM_SUPPORT_COUNT}


def _rules(frequent: dict[tuple[int, ...], int]) -> list[_Rule]:
    rules: list[_Rule] = []
    for itemset, support_union in frequent.items():
        if len(itemset) < 2:
            continue
        for consequent_tuple in combinations(itemset, 1):
            consequent = consequent_tuple[0]
            antecedent = tuple(sorted(set(itemset) - {consequent}))
            if antecedent not in frequent:
                continue
            confidence = support_union / frequent[antecedent]
            if confidence >= _MINIMUM_CONFIDENCE:
                rules.append(
                    _Rule(
                        antecedent=antecedent,
                        consequent=consequent,
                        confidence=confidence,
                    )
                )
    return sorted(rules, key=lambda rule: rule.confidence, reverse=True)


def _rule_ticket(
    *,
    target_rule: _Rule,
    rules: list[_Rule],
    bet_index: int,
) -> tuple[int, ...]:
    current = sorted(set((*target_rule.antecedent, target_rule.consequent)))
    while len(current) < _PICK_COUNT:
        last_number = current[-1]
        candidates = [
            rule
            for rule in rules
            if rule.consequent not in current
            and (
                rule.antecedent == (last_number,)
                or (len(rule.antecedent) == 1 and rule.antecedent[0] in current)
            )
        ]
        if candidates:
            candidates.sort(key=lambda rule: rule.confidence, reverse=True)
            next_number = candidates[0].consequent
        else:
            remaining = [
                number for number in range(_MIN_NUMBER, _MAX_NUMBER + 1) if number not in current
            ]
            if not remaining:
                break
            next_number = remaining[bet_index % len(remaining)]
        current.append(next_number)
        current = sorted(set(current))
    return tuple(sorted(current[:_PICK_COUNT]))


def _apriori_tickets(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    recent_first = tuple(draw.numbers for draw in reversed(history))[:_HISTORY_WINDOW]
    rules = _rules(_frequent_itemsets(recent_first))
    used_antecedents: set[tuple[int, ...]] = set()
    tickets: list[tuple[int, ...]] = []
    for index in range(_MAXIMUM_NATIVE_TICKET_COUNT):
        target_rule = next(
            (rule for rule in rules if rule.antecedent not in used_antecedents),
            None,
        )
        if target_rule is None:
            break
        used_antecedents.add(target_rule.antecedent)
        tickets.append(_rule_ticket(target_rule=target_rule, rules=rules, bet_index=index))
    return tuple(tickets)


class BigLottoAprioriPredictorAdapter(PortfolioBetAdapter):
    """Deterministic, source-ordered Apriori portfolio of two to seven tickets."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Apriori 關聯規則 2-7 注"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 7
    minimum_native_ticket_count = 2
    maximum_native_ticket_count = 7

    def expected_native_ticket_count(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> int:
        """Resolve the donor-derived count through replay's existing count seam."""

        del strategy, target
        causal_history = tuple(
            CausalDrawRow(
                draw=draw.draw_number,
                date=draw.draw_date.isoformat(),
                numbers=draw.main_numbers,
            )
            for draw in history
        )
        return len(self.get_bets(causal_history, LotteryType.BIG_LOTTO))

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _apriori_tickets(history)


__all__ = ["BigLottoAprioriPredictorAdapter"]
