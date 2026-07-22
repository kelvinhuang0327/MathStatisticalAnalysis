"""Pure target-native ports of the P541D_R2-selected BIG_LOTTO adapters."""

from __future__ import annotations

import hashlib
import json
import random

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    InvalidOutput,
    validated_history,
)

_ZONE_STRATEGY_ID = "biglotto_zone_split_3bet_bet1"
_SOCIAL_STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"
_ZONE_BET_COUNT = 3
_ZONE_OVERLAP_SIZE = 2
_SOCIAL_HISTORY_WINDOW = 50
_UNPOPULAR_BLEND = 0.7
_HISTORICAL_BLEND = 0.3


def _zone_split_pools() -> tuple[tuple[int, ...], ...]:
    """Return the three legacy candidate pools from the target rule contract."""

    rule = BIG_LOTTO_RULE_CONTRACT
    full_range = rule.main_number_max - rule.main_number_min + 1
    zone_size = full_range // _ZONE_BET_COUNT
    pools: list[tuple[int, ...]] = []
    for index in range(_ZONE_BET_COUNT):
        start = rule.main_number_min + index * zone_size
        end = rule.main_number_min + (index + 1) * zone_size - 1
        if index == _ZONE_BET_COUNT - 1:
            end = rule.main_number_max
        pool = tuple(
            range(
                max(rule.main_number_min, start - _ZONE_OVERLAP_SIZE),
                min(rule.main_number_max, end + _ZONE_OVERLAP_SIZE) + 1,
            )
        )
        if len(pool) < rule.main_number_count:
            pool = tuple(range(rule.main_number_min, rule.main_number_max + 1))
        pools.append(pool)
    return tuple(pools)


def _zone_seed_preimage(history: object) -> bytes:
    """Build the exact donor canonical-JSON seed preimage."""

    canonical_history = validated_history(history, _ZONE_STRATEGY_ID)
    payload = {
        "strategy_id": _ZONE_STRATEGY_ID,
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "causal_history": [
            {"draw": row.draw, "date": row.date, "numbers": list(row.numbers)}
            for row in canonical_history
        ],
    }
    try:
        canonical_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise InvalidOutput(f"{_ZONE_STRATEGY_ID}: history is not JSON-safe") from exc
    return canonical_json.encode("utf-8")


def _zone_seed_digest(history: object) -> str:
    """Return the SHA-256 hex digest for the donor seed preimage."""

    return hashlib.sha256(_zone_seed_preimage(history)).hexdigest()


def _zone_split_bets(history: object) -> tuple[tuple[int, ...], ...]:
    """Generate three sequential bets with exactly one history-derived RNG."""

    digest = bytes.fromhex(_zone_seed_digest(history))
    local_rng = random.Random(int.from_bytes(digest, byteorder="big", signed=False))
    return tuple(
        tuple(sorted(local_rng.sample(pool, BIG_LOTTO_RULE_CONTRACT.main_number_count)))
        for pool in _zone_split_pools()
    )


def _unpopular_scores() -> tuple[float, ...]:
    """Port the donor anti-popularity weights without NumPy."""

    rule = BIG_LOTTO_RULE_CONTRACT
    scores: list[float] = []
    for number in range(rule.main_number_min, rule.main_number_max + 1):
        score = 1.0
        if 1 <= number <= 31:
            if number == 1:
                score *= 0.3
            elif number in {7, 8}:
                score *= 0.35
            elif number == 9:
                score *= 0.4
            else:
                score *= 0.5
        else:
            score *= 1.5

        if number in {6, 16, 18, 26, 28, 36, 38, 46, 48}:
            score *= 0.7
        if number in {10, 20, 30, 40}:
            score *= 0.6
        if 42 <= number <= 49:
            score *= 1.8
        scores.append(score)

    total = sum(scores)
    return tuple(score / total for score in scores)


def _historical_frequency(history: tuple[CausalDrawRow, ...]) -> tuple[float, ...]:
    """Return donor-compatible normalized frequency over at most 50 newest rows."""

    rule = BIG_LOTTO_RULE_CONTRACT
    frequencies = [0.0] * (rule.main_number_max - rule.main_number_min + 1)
    for row in history[:_SOCIAL_HISTORY_WINDOW]:
        for number in row.numbers:
            if rule.main_number_min <= number <= rule.main_number_max:
                frequencies[number - rule.main_number_min] += 1.0

    total = sum(frequencies)
    if total > 0:
        return tuple(frequency / total for frequency in frequencies)
    uniform = 1.0 / len(frequencies)
    return tuple(uniform for _ in frequencies)


def _social_wisdom_prediction(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Score newest-first history with an explicit deterministic tie-break."""

    rule = BIG_LOTTO_RULE_CONTRACT
    unpopular = _unpopular_scores()
    if history:
        historical = _historical_frequency(history)
        combined = tuple(
            _UNPOPULAR_BLEND * unpopular_score + _HISTORICAL_BLEND * frequency
            for unpopular_score, frequency in zip(unpopular, historical, strict=True)
        )
    else:
        combined = unpopular

    ranked = sorted(
        range(rule.main_number_min, rule.main_number_max + 1),
        key=lambda number: (-combined[number - rule.main_number_min], number),
    )
    return tuple(sorted(ranked[: rule.main_number_count]))


class BigLottoSocialWisdomAntiPopularityAdapter(BetAdapter):
    """Deterministic, NumPy-free Social Wisdom anti-popularity adapter."""

    strategy_id = _SOCIAL_STRATEGY_ID
    strategy_name = "大樂透 Social Wisdom Anti-Popularity"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        return history[-_SOCIAL_HISTORY_WINDOW:]

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        newest_first = tuple(reversed(history))
        return _social_wisdom_prediction(newest_first)


class BigLottoZoneSplit3BetBet1Adapter(BetAdapter):
    """Deterministic Zone Split three-bet adapter returning generated bet one."""

    strategy_id = _ZONE_STRATEGY_ID
    strategy_name = "大樂透 Zone Split 3注（Replay Bet 1）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _zone_split_bets(history)[0]


_DEVIATION_STRATEGY_ID = "biglotto_deviation_2bet"
_DEVIATION_HISTORY_WINDOW = 50
_DEVIATION_HOT_THRESHOLD = 1
_DEVIATION_COLD_THRESHOLD = -1


def _deviation_complement_2bet(
    history: tuple[CausalDrawRow, ...],
    window: int = _DEVIATION_HISTORY_WINDOW,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Port of the donor's ``deviation_complement_2bet`` — (hot bet, cold complement bet).

    Bet one is numbers whose recent frequency exceeds expectation by a strict
    margin (trend continuation); bet two is the complement, numbers whose
    frequency falls short by a strict margin (mean reversion). The two bets
    pad differently when short of six candidates, exactly as the donor did:
    bet one pads by nearest-to-expected frequency, bet two pads by ascending
    unused number.
    """

    rule = BIG_LOTTO_RULE_CONTRACT
    recent = history[-window:] if len(history) > window else history
    total = len(recent)
    expected = total * rule.main_number_count / rule.main_number_max

    freq: dict[int, int] = {}
    for row in recent:
        for number in row.numbers:
            freq[number] = freq.get(number, 0) + 1

    hot: list[tuple[int, float]] = []
    cold: list[tuple[int, float]] = []
    for number in range(rule.main_number_min, rule.main_number_max + 1):
        deviation = freq.get(number, 0) - expected
        if deviation > _DEVIATION_HOT_THRESHOLD:
            hot.append((number, deviation))
        elif deviation < _DEVIATION_COLD_THRESHOLD:
            cold.append((number, abs(deviation)))

    hot.sort(key=lambda candidate: candidate[1], reverse=True)
    cold.sort(key=lambda candidate: candidate[1], reverse=True)

    bet1 = [number for number, _ in hot[: rule.main_number_count]]
    used = set(bet1)

    if len(bet1) < rule.main_number_count:
        nearest_expected = sorted(
            range(rule.main_number_min, rule.main_number_max + 1),
            key=lambda number: abs(freq.get(number, 0) - expected),
        )
        for number in nearest_expected:
            if number not in used and len(bet1) < rule.main_number_count:
                bet1.append(number)
                used.add(number)

    bet2: list[int] = []
    for number, _ in cold:
        if number not in used and len(bet2) < rule.main_number_count:
            bet2.append(number)
            used.add(number)

    if len(bet2) < rule.main_number_count:
        for number in range(rule.main_number_min, rule.main_number_max + 1):
            if number not in used and len(bet2) < rule.main_number_count:
                bet2.append(number)
                used.add(number)

    return (
        tuple(sorted(bet1[: rule.main_number_count])),
        tuple(sorted(bet2[: rule.main_number_count])),
    )


class BigLottoDeviation2BetAdapter(BetAdapter):
    """Deterministic frequency-deviation adapter returning the donor hot bet."""

    strategy_id = _DEVIATION_STRATEGY_ID
    strategy_name = "大樂透 Deviation 2注"
    strategy_version = "v0.1"
    min_history = 100
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return _deviation_complement_2bet(history)[0]


__all__ = [
    "BigLottoDeviation2BetAdapter",
    "BigLottoSocialWisdomAntiPopularityAdapter",
    "BigLottoZoneSplit3BetBet1Adapter",
]
