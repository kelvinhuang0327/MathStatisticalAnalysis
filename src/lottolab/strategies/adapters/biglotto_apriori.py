"""Target-native port of the legacy Apriori association rule backtest strategy.

The donor (tools/backtest_apriori.py) evaluates 4 configurations with num_bets in
[1, 2, 3, 7] over a 150-draw causal window. The 4 configurations emit 1, 2, 3,
and 7 tickets respectively, flattened in declared loop order into a 13-ticket
native portfolio.

When sufficient frequent itemsets and rules exist (confidence >= 0.4, support >= 3),
tickets are constructed by chaining association rules or falling back to deterministic
modulo filler. When no distinct antecedent rule is available (e.g. on early or
insufficient history), the donor falls back to random sampling, preserved here via
the versioned target-stable MT19937 seed protocol derived deterministically from the
causal history boundary.
"""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import Final

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    PortfolioBetAdapter,
)

_STRATEGY_ID: Final = "legacy_biglotto__backtest_apriori__2abb53765703"
_PROTOCOL: Final = "legacy_source_native_wave7/v1"
_METHOD_ID: Final = "tools/backtest_apriori.py"
_SOURCE_SHA256: Final = "2abb537657035eec87da9863055f817d81ffafe83084f0f53858ad31327282a1"
_USER_SEED: Final = "biglotto-full-universe-source-native-wave7-v1"
_REPLICATE_ID: Final = 0

_WINDOW: Final = 150
_MIN_SUPPORT: Final = 3
_MIN_CONFIDENCE: Final = 0.4
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_CONFIGURATIONS: Final = (1, 2, 3, 7)
_NATIVE_TICKET_COUNT: Final = 13


@dataclass(frozen=True, slots=True)
class _Rule:
    antecedent: tuple[int, ...]
    consequent: int
    confidence: float


def _target_after_causal_cutoff(history: tuple[CausalDrawRow, ...]) -> str:
    """Return a deterministic request identity absent from the causal history."""
    if not history:
        return "1:lottolab-next-target"
    draw_ids = {row.draw for row in history}
    target = f"{history[-1].draw}:lottolab-next-target"
    while target in draw_ids:
        target = f"{target}:next"
    return target


def _seed_integer(target_draw_number: str) -> int:
    """Derive the frozen SHA-256 target-stable seed integer."""
    material = "|".join(
        (
            _PROTOCOL,
            _METHOD_ID,
            _SOURCE_SHA256,
            target_draw_number,
            str(_REPLICATE_ID),
            _USER_SEED,
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return int(digest, 16)


def _ticket(numbers: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(
            type(number) is not int or not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values
        )
    ):
        raise ValueError("FROZEN_APRIORI_INVALID_TICKET")
    return values


def _frequent_itemsets(
    history: tuple[tuple[int, ...], ...],
    *,
    min_support: int = _MIN_SUPPORT,
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
    return {itemset: count for itemset, count in counts.items() if count >= min_support}


def _rules(
    frequent: dict[tuple[int, ...], int],
    *,
    min_confidence: float = _MIN_CONFIDENCE,
) -> list[_Rule]:
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
            if confidence >= min_confidence:
                rules.append(
                    _Rule(
                        antecedent=antecedent,
                        consequent=consequent,
                        confidence=confidence,
                    )
                )
    return sorted(
        rules,
        key=lambda rule: rule.confidence,
        reverse=True,
    )


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
            candidates.sort(
                key=lambda rule: rule.confidence,
                reverse=True,
            )
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
    return _ticket(current[:_PICK_COUNT])


def _apriori_backtest_tickets(
    history: tuple[tuple[int, ...], ...],
    *,
    num_bets: int,
    rng: random.Random,
) -> list[tuple[int, ...]]:
    rules = _rules(_frequent_itemsets(history))
    used_antecedents: set[tuple[int, ...]] = set()
    bets: list[tuple[int, ...]] = []
    for index in range(num_bets):
        target_rule = next(
            (rule for rule in rules if rule.antecedent not in used_antecedents),
            None,
        )
        if target_rule is None:
            bets.append(_ticket(rng.sample(range(_MIN_NUMBER, _MAX_NUMBER + 1), _PICK_COUNT)))
            continue
        used_antecedents.add(target_rule.antecedent)
        bets.append(
            _rule_ticket(
                target_rule=target_rule,
                rules=rules,
                bet_index=index,
            )
        )
    return bets


def _apriori_portfolio(
    history: tuple[CausalDrawRow, ...],
    *,
    target_draw_number: str | None = None,
) -> tuple[tuple[int, ...], ...]:
    """Generate 13 positional tickets matching the 4 donor backtest configurations."""
    target = (
        target_draw_number
        if target_draw_number is not None
        else _target_after_causal_cutoff(history)
    )
    seed = _seed_integer(target)
    rng = random.Random()
    rng.seed(seed, version=2)

    history_slice = tuple(row.numbers for row in history[-_WINDOW:])
    tickets: list[tuple[int, ...]] = []
    for num_bets in _CONFIGURATIONS:
        tickets.extend(
            _apriori_backtest_tickets(
                history_slice,
                num_bets=num_bets,
                rng=rng,
            )
        )
    return tuple(tickets)


class BigLottoAprioriStrategyAdapter(PortfolioBetAdapter):
    """Thirteen-ticket positional portfolio port of BacktestApriori."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Apriori 關聯規則 13注組合"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _NATIVE_TICKET_COUNT

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _apriori_portfolio(history)


__all__ = [
    "BigLottoAprioriStrategyAdapter",
    "_apriori_portfolio",
]
