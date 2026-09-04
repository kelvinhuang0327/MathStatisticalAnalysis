"""BigLotto native-strategy Batch02 publication plus the current-main Markov
adapter. The four Batch02 adapters below are thin ports from donor commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9``; the Markov adapter was already
authoritative on current main and is preserved unchanged.

Source: ``tools/backtest_biglotto_markov_4bet.py`` -- ``generate_ts3_markov4``
(``strategy_id legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b``,
``method_family markov``). No algorithm was changed, tuned, or "improved"
during the port.

The Batch03 local Markov implementation is intentionally not present in this
module; current main remains the sole owner of that canonical ID, and no
evaluation lineage is transferred between the differing implementations.

``fourier_rhythm_bet`` (bet 1 of the donor's Triple-Strike baseline) is the
only donor function needing numeric reimplementation: the donor computes a
``scipy.fft.fft`` peak-frequency score; this port follows the pure-Python
DFT technique ``daily539_fourier4.py``'s ``_fourier_scores`` already
established for this adapter family (shared per-bin cos/sin sums computed
once, then each number's mean-subtracted coefficient recovered via the
algebraic identity ``hit_sum - mean * all_sum``, which preserves the same
exact-zero cancellation as numpy's ``series - series.mean()`` for a
constant bitstream), adapted for this donor's own frequency range: plain
``fft``/``fftfreq``'s strictly-positive bins with the Nyquist bin
*excluded* (``max_positive_bin = (width - 1) // 2``, not ``daily539_
fourier4``'s Nyquist-inclusive ``width // 2``), plus this donor's own
extra ``2 < period < window / 2`` acceptance gate before a number's score
is set to anything other than ``0.0``. Verified byte-for-byte against the
real donor executed under a numpy/scipy interpreter (donor's own DB import
stubbed out) across 16 history lengths from 150 to 1200 -- see this
adapter's test module for the golden fixtures and how they were produced.

One donor tie-break is intentionally not reproduced: the final ranking
(``np.argsort(scores[1:])[::-1]``) inherits numpy's default ``argsort``
sort kind, which numpy's own documentation does not guarantee is stable --
there is no single well-defined "donor tie-break" to replicate, only one
particular numpy build's unspecified behavior. This port breaks ties by
ascending number instead, the same documented, deterministic convention
this adapter family already uses in ``daily539_fourier4.py``'s
``_ranked_all``. Ties only arise between numbers that both score exactly
``0.0`` (having failed the hit-count or period-range gate) or, in
principle, between two numbers whose continuous-valued scores happen to
collide exactly; neither was ever observed across this port's own 16-length
verification sweep.

``cold_numbers_bet``'s own ``use_sum_constraint`` and ``pool_size``
parameters, and ``markov_orthogonal_bet``'s own ``markov_window``
parameter, are hardcoded to the donor's own defaults below because
``generate_triple_strike``/``generate_ts3_markov4`` -- the donor's only
production entrypoints, and the only call path this port exposes -- never
override them; the donor's own ``main()`` Phase-6 window-sensitivity sweep
that *does* vary ``markov_window`` is research/reporting code, not a second
production configuration.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import combinations
from math import cos, hypot, pi, sin, sqrt
from typing import Any, cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

_MIN_NUM = 1
_MAX_NUM = 49
_PICK = 6
_MIN_HISTORY = 150  # donor's own MIN_HISTORY_BUFFER
_FOURIER_WINDOW = 500
_COLD_WINDOW = 100
_COLD_POOL_SIZE = 12
_TAIL_WINDOW = 100
_MARKOV_WINDOW = 100
_SUM_WINDOW = 300


def _sum_target(history: tuple[CausalDrawRow, ...]) -> tuple[float, float]:
    """Port ``_sum_target``: a mean-reversion sum-range target derived from
    the trailing ``_SUM_WINDOW`` draws' own sum distribution."""

    recent = history[-_SUM_WINDOW:] if len(history) >= _SUM_WINDOW else history
    sums = [sum(row.numbers) for row in recent]
    mean = sum(sums) / len(sums)
    variance = sum((value - mean) ** 2 for value in sums) / len(sums)
    sigma = sqrt(variance)
    last_sum = sum(history[-1].numbers)
    if last_sum < mean - 0.5 * sigma:
        return mean, mean + sigma
    if last_sum > mean + 0.5 * sigma:
        return mean - sigma, mean
    return mean - 0.5 * sigma, mean + 0.5 * sigma


def _fourier_rhythm_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Port ``fourier_rhythm_bet``'s per-number score -- see module
    docstring for the pure-Python DFT technique and its one documented
    tie-break deviation."""

    recent = history[-_FOURIER_WINDOW:] if len(history) >= _FOURIER_WINDOW else history
    width = len(recent)
    max_positive_bin = (width - 1) // 2

    hit_positions_by_number: dict[int, tuple[int, ...]] = {
        number: tuple(index for index, row in enumerate(recent) if number in row.numbers)
        for number in range(_MIN_NUM, _MAX_NUM + 1)
    }

    all_cos_by_bin: list[float] = [0.0] * (max_positive_bin + 1)
    all_sin_by_bin: list[float] = [0.0] * (max_positive_bin + 1)
    for frequency_bin in range(1, max_positive_bin + 1):
        angle_scale = 2.0 * pi * frequency_bin / width
        total_cos = 0.0
        total_sin = 0.0
        for position in range(width):
            angle = angle_scale * position
            total_cos += cos(angle)
            total_sin += sin(angle)
        all_cos_by_bin[frequency_bin] = total_cos
        all_sin_by_bin[frequency_bin] = total_sin

    scores: dict[int, float] = {}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        hit_positions = hit_positions_by_number[number]
        if len(hit_positions) < 2:
            scores[number] = 0.0
            continue
        mean = len(hit_positions) / width

        best_magnitude = -1.0
        best_frequency_bin = 0
        for frequency_bin in range(1, max_positive_bin + 1):
            angle_scale = 2.0 * pi * frequency_bin / width
            hit_cos = 0.0
            hit_sin = 0.0
            for position in hit_positions:
                angle = angle_scale * position
                hit_cos += cos(angle)
                hit_sin += sin(angle)
            real = hit_cos - mean * all_cos_by_bin[frequency_bin]
            imaginary = hit_sin - mean * all_sin_by_bin[frequency_bin]
            magnitude = hypot(real, imaginary)
            if magnitude > best_magnitude:
                best_magnitude = magnitude
                best_frequency_bin = frequency_bin

        if best_frequency_bin == 0:
            scores[number] = 0.0
            continue
        period = width / best_frequency_bin
        if not (2.0 < period < width / 2.0):
            scores[number] = 0.0
            continue
        last_hit = hit_positions[-1]
        gap = (width - 1) - last_hit
        scores[number] = 1.0 / (abs(gap - period) + 1.0)

    return scores


def _fourier_rhythm_bet(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Port ``fourier_rhythm_bet`` (``window=500``, the donor's own
    default -- the only value ``generate_triple_strike`` ever uses)."""

    scores = _fourier_rhythm_scores(history)
    ranked = sorted(range(_MIN_NUM, _MAX_NUM + 1), key=lambda number: -scores[number])
    return tuple(sorted(ranked[:_PICK]))


def _cold_numbers_bet(
    history: tuple[CausalDrawRow, ...],
    exclude: frozenset[int],
) -> tuple[int, ...]:
    """Port ``cold_numbers_bet`` (``window=100, pool_size=12,
    use_sum_constraint=True`` -- the donor's own defaults and the only
    values ``generate_triple_strike`` ever uses)."""

    recent = history[-_COLD_WINDOW:] if len(history) >= _COLD_WINDOW else history
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    candidates = [number for number in range(_MIN_NUM, _MAX_NUM + 1) if number not in exclude]
    sorted_cold = sorted(candidates, key=lambda number: frequency.get(number, 0))

    if len(history) < 2 or _COLD_POOL_SIZE <= _PICK:
        return tuple(sorted(sorted_cold[:_PICK]))

    pool = sorted_cold[:_COLD_POOL_SIZE]
    low, high = _sum_target(history)
    mid = (low + high) / 2.0

    best_combo: tuple[int, ...] | None = None
    best_distance = float("inf")
    best_in_range = False
    for combo in combinations(pool, _PICK):
        combo_sum = sum(combo)
        in_range = low <= combo_sum <= high
        distance = abs(combo_sum - mid)
        if in_range and (not best_in_range or distance < best_distance):
            best_combo, best_distance, best_in_range = combo, distance, True
        elif not in_range and not best_in_range and distance < best_distance:
            best_combo, best_distance = combo, distance

    if best_combo is None:
        return tuple(sorted(pool[:_PICK]))
    return tuple(sorted(best_combo))


def _tail_balance_bet(
    history: tuple[CausalDrawRow, ...],
    exclude: frozenset[int],
) -> tuple[int, ...]:
    """Port ``tail_balance_bet`` (``window=100``, the donor's own default
    and the only value ``generate_triple_strike`` ever uses)."""

    recent = history[-_TAIL_WINDOW:] if len(history) >= _TAIL_WINDOW else history
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)

    tail_groups: dict[int, list[tuple[int, int]]] = {tail: [] for tail in range(10)}
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        if number not in exclude:
            tail_groups[number % 10].append((number, frequency.get(number, 0)))
    for tail in tail_groups:
        tail_groups[tail].sort(key=lambda item: item[1], reverse=True)

    available_tails = sorted(
        (tail for tail in range(10) if tail_groups[tail]),
        key=lambda tail: tail_groups[tail][0][1] if tail_groups[tail] else 0,
        reverse=True,
    )
    index_in_group = dict.fromkeys(range(10), 0)

    selected: list[int] = []
    while len(selected) < _PICK:
        added = False
        for tail in available_tails:
            if len(selected) >= _PICK:
                break
            if index_in_group[tail] < len(tail_groups[tail]):
                number, _count = tail_groups[tail][index_in_group[tail]]
                if number not in selected:
                    selected.append(number)
                    added = True
                index_in_group[tail] += 1
        if not added:
            break

    if len(selected) < _PICK:
        remaining = [
            number
            for number in range(_MIN_NUM, _MAX_NUM + 1)
            if number not in selected and number not in exclude
        ]
        remaining.sort(key=lambda number: frequency.get(number, 0), reverse=True)
        selected.extend(remaining[: _PICK - len(selected)])

    return tuple(sorted(selected[:_PICK]))


def _markov_orthogonal_bet(
    history: tuple[CausalDrawRow, ...],
    exclude: frozenset[int],
) -> tuple[int, ...]:
    """Port ``markov_orthogonal_bet`` (``markov_window=100``, the donor's
    own default and the only value ``generate_ts3_markov4`` ever uses)."""

    window = min(_MARKOV_WINDOW, len(history))
    recent = history[-window:]

    transitions: Counter[tuple[int, int]] = Counter()
    for i in range(len(recent) - 1):
        for previous_number in recent[i].numbers:
            for next_number in recent[i + 1].numbers:
                transitions[(previous_number, next_number)] += 1

    if len(history) < 2:
        candidates = [number for number in range(_MIN_NUM, _MAX_NUM + 1) if number not in exclude]
        return tuple(sorted(candidates[:_PICK]))

    last_draw_numbers = history[-1].numbers
    scores: Counter[int] = Counter()
    for previous_number in last_draw_numbers:
        for number in range(_MIN_NUM, _MAX_NUM + 1):
            scores[number] += transitions.get((previous_number, number), 0)

    candidates = [
        (number, scores[number])
        for number in range(_MIN_NUM, _MAX_NUM + 1)
        if number not in exclude
    ]
    candidates.sort(key=lambda item: -item[1])
    selected = [number for number, _score in candidates[:_PICK]]

    if len(selected) < _PICK:
        remaining = [
            number
            for number in range(_MIN_NUM, _MAX_NUM + 1)
            if number not in exclude and number not in selected
        ]
        selected.extend(remaining[: _PICK - len(selected)])

    return tuple(sorted(selected[:_PICK]))


def _generate_triple_strike(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Port ``generate_triple_strike`` (exact replica of the donor's
    already-verified Triple Strike 3-bet baseline)."""

    bet1 = _fourier_rhythm_bet(history)
    bet2 = _cold_numbers_bet(history, exclude=frozenset(bet1))
    bet3 = _tail_balance_bet(history, exclude=frozenset(bet1) | frozenset(bet2))
    return bet1, bet2, bet3


def _generate_ts3_markov4(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    """Port ``generate_ts3_markov4``: Triple Strike 3-bet baseline plus one
    Markov-transition orthogonal 4th bet restricted to numbers the first
    three bets did not already use."""

    bet1, bet2, bet3 = _generate_triple_strike(history)
    used = frozenset(bet1) | frozenset(bet2) | frozenset(bet3)
    bet4 = _markov_orthogonal_bet(history, exclude=used)
    return bet1, bet2, bet3, bet4


class BigLottoTs3Markov4betAdapter(PortfolioBetAdapter):
    """Triple Strike 3-bet baseline (Fourier rhythm / sum-constrained cold /
    tail balance) plus one Markov-transition orthogonal 4th bet, restricted
    to numbers the first three bets did not already use."""

    strategy_id = "legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b"
    strategy_name = "大樂透 Triple Strike + Markov 正交注4"
    strategy_version = "v0.1"
    min_history = _MIN_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 4

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _generate_ts3_markov4(history)


# ═════════════════════════════════════════════════════════════════════════
# legacy_biglotto__backtest_apriori__2abb53765703
# ═════════════════════════════════════════════════════════════════════════

_APRIORI_STRATEGY_ID = "legacy_biglotto__backtest_apriori__2abb53765703"
_APRIORI_WINDOW = 150
_APRIORI_MIN_SUPPORT = 3
_APRIORI_MIN_CONFIDENCE = 0.4
_APRIORI_NATIVE_TICKET_COUNT = 13


@dataclass(frozen=True, slots=True)
class _AprioriRule:
    antecedent: tuple[int, ...]
    consequent: int
    confidence: float


def _apriori_mine_frequent_itemsets(
    history: Sequence[CausalDrawRow], *, min_support: int
) -> dict[tuple[int, ...], int]:
    """Port of ``BigLottoAprioriPredictor.mine_frequent_itemsets``."""

    counts: Counter[tuple[int, ...]] = Counter()
    for row in history:
        nums = sorted(row.numbers)
        for number in nums:
            counts[(number,)] += 1
        for pair in combinations(nums, 2):
            counts[pair] += 1
        for trio in combinations(nums, 3):
            counts[trio] += 1
    return {itemset: count for itemset, count in counts.items() if count >= min_support}


def _apriori_generate_rules(
    frequent_itemsets: dict[tuple[int, ...], int], *, min_confidence: float
) -> list[_AprioriRule]:
    """Port of ``BigLottoAprioriPredictor.generate_rules``. Support is
    monotone under sub-itemsets, so every ``antecedent`` split from a
    qualifying itemset is guaranteed already present in
    ``frequent_itemsets``."""

    rules: list[_AprioriRule] = []
    for itemset, support_union in frequent_itemsets.items():
        if len(itemset) < 2:
            continue
        for consequent in itemset:
            antecedent = tuple(sorted(set(itemset) - {consequent}))
            support_antecedent = frequent_itemsets.get(antecedent)
            if support_antecedent is None:
                continue
            confidence = support_union / support_antecedent
            if confidence >= min_confidence:
                rules.append(
                    _AprioriRule(
                        antecedent=antecedent, consequent=consequent, confidence=confidence
                    )
                )
    return sorted(rules, key=lambda rule: rule.confidence, reverse=True)


def _apriori_fallback_random(
    strategy_id: str, history: Sequence[CausalDrawRow], bet_index: int
) -> random.Random:
    """Deterministic replacement for the donor's unseeded ``random.sample``
    fallback -- a local RNG derived from a canonical hash of the exact
    causal inputs, never touching the process-global ``random`` module
    (see module docstring NUMPY_SUBSTITUTION/RNG note)."""

    payload: dict[str, Any] = {
        "strategy_id": strategy_id,
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "bet_index": bet_index,
        "causal_history": [
            {"draw": row.draw, "date": row.date, "numbers": list(row.numbers)} for row in history
        ],
    }
    preimage = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(preimage.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big")
    return random.Random(seed)


def _apriori_backtest_bets(
    history: tuple[CausalDrawRow, ...], *, num_bets: int, window: int, strategy_id: str
) -> list[list[int]]:
    """Port of ``BacktestApriori.predict_for_backtest``."""

    recent_history = history[-window:]
    frequent = _apriori_mine_frequent_itemsets(recent_history, min_support=_APRIORI_MIN_SUPPORT)
    rules = _apriori_generate_rules(frequent, min_confidence=_APRIORI_MIN_CONFIDENCE)

    bets: list[list[int]] = []
    used_antecedents: set[tuple[int, ...]] = set()

    for bet_index in range(num_bets):
        target_rule: _AprioriRule | None = None
        for rule in rules:
            if rule.antecedent not in used_antecedents:
                target_rule = rule
                used_antecedents.add(rule.antecedent)
                break

        if target_rule is None:
            rng = _apriori_fallback_random(strategy_id, recent_history, bet_index)
            bets.append(sorted(rng.sample(range(1, _MAX_NUM + 1), 6)))
            continue

        current_numbers = sorted(set(target_rule.antecedent) | {target_rule.consequent})

        while len(current_numbers) < 6:
            last_number = current_numbers[-1]
            candidates = [
                rule
                for rule in rules
                if rule.consequent not in current_numbers
                and (
                    rule.antecedent == (last_number,)
                    or (len(rule.antecedent) == 1 and rule.antecedent[0] in current_numbers)
                )
            ]
            if candidates:
                candidates.sort(key=lambda rule: rule.confidence, reverse=True)
                best_next = candidates[0].consequent
            else:
                remaining = [n for n in range(1, _MAX_NUM + 1) if n not in current_numbers]
                if not remaining:
                    break
                best_next = remaining[bet_index % len(remaining)]
            current_numbers.append(best_next)
            current_numbers = sorted(set(current_numbers))

        bets.append(sorted(current_numbers[:6]))

    return bets


class BigLottoBacktestAprioriAdapter(PortfolioBetAdapter):
    """Apriori association-rule backtest predictor -- a 13-native-ticket
    portfolio. See module docstring for the inherited-mining and
    deterministic-fallback notes."""

    strategy_id = _APRIORI_STRATEGY_ID
    strategy_name = "大樂透 Apriori 關聯規則回測預測器"
    strategy_version = "v0.1"
    min_history = _APRIORI_WINDOW
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _APRIORI_NATIVE_TICKET_COUNT

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        bets = _apriori_backtest_bets(
            history,
            num_bets=_APRIORI_NATIVE_TICKET_COUNT,
            window=_APRIORI_WINDOW,
            strategy_id=self.strategy_id,
        )
        return tuple(tuple(bet) for bet in bets)


# ═════════════════════════════════════════════════════════════════════════
# legacy_biglotto__covering_strategy_research__214ecc206fc9
# ═════════════════════════════════════════════════════════════════════════

_COVERING_STRATEGY_ID = "legacy_biglotto__covering_strategy_research__214ecc206fc9"
_COVERING_MIN_HISTORY = 200
_COVERING_GROUP_SIZE = 5
_COVERING_NATIVE_TICKET_COUNT = 40


def _covering_zero_overlap(n_bets: int, *, seed: int) -> list[list[int]]:
    """Port of ``gen_zero_overlap``."""

    rng = random.Random(seed)
    take = min(6 * n_bets, _MAX_NUM)
    nums = rng.sample(range(1, _MAX_NUM + 1), take)
    bets: list[list[int]] = []
    for i in range(n_bets):
        start = i * 6
        if start + 6 <= len(nums):
            bets.append(sorted(nums[start : start + 6]))
        else:
            used = set(nums[:start])
            remaining = [n for n in range(1, _MAX_NUM + 1) if n not in used]
            rng.shuffle(remaining)
            bets.append(sorted(remaining[:6]))
    return bets


def _covering_anchor_k(n_bets: int, k_anchors: int, *, seed: int) -> list[list[int]]:
    """Port of ``gen_anchor_k``."""

    rng = random.Random(seed)
    all_nums = list(range(1, _MAX_NUM + 1))
    rng.shuffle(all_nums)
    anchors = sorted(all_nums[:k_anchors])
    remaining_pool = all_nums[k_anchors:]
    unique_per_bet = 6 - k_anchors

    bets: list[list[int]] = []
    for i in range(n_bets):
        start = i * unique_per_bet
        if start + unique_per_bet <= len(remaining_pool):
            unique = remaining_pool[start : start + unique_per_bet]
        else:
            used = {n for bet in bets for n in bet}
            fallback = [
                n
                for n in range(1, _MAX_NUM + 1)
                if n not in set(anchors) and n not in used
            ]
            rng.shuffle(fallback)
            unique = fallback[:unique_per_bet]
        bets.append(sorted(anchors + unique))
    return bets


def _covering_random_baseline(n_bets: int, *, seed: int) -> list[list[int]]:
    """Port of ``main()``'s inline random-baseline comparison arm."""

    rng = random.Random(seed)
    return [sorted(rng.sample(range(1, _MAX_NUM + 1), 6)) for _ in range(n_bets)]


def _covering_cooccurrence_guided(
    history: tuple[CausalDrawRow, ...], n_bets: int, *, window: int, seed: int
) -> list[list[int]]:
    """Port of ``gen_cooccurrence_guided``."""

    recent = history[-window:] if len(history) >= window else history
    cooc: dict[tuple[int, int], int] = defaultdict(int)
    for row in recent:
        nums = [n for n in row.numbers[:_PICK] if 1 <= n <= _MAX_NUM]
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                cooc[(nums[i], nums[j])] += 1
                cooc[(nums[j], nums[i])] += 1

    rng = random.Random(seed)
    used: set[int] = set()
    bets: list[list[int]] = []
    for _ in range(n_bets):
        candidates = [n for n in range(1, _MAX_NUM + 1) if n not in used]
        if len(candidates) < 6:
            rng.shuffle(candidates)
            bets.append(sorted(candidates[:6]))
            break

        avail = set(candidates)
        bet: list[int] = []
        scores = {n: sum(cooc.get((n, m), 0) for m in avail if m != n) for n in avail}
        first = max(avail, key=lambda x: scores[x])
        bet.append(first)
        avail.remove(first)
        while len(bet) < 6 and avail:
            pair_scores = {n: sum(cooc.get((n, b), 0) for b in bet) for n in avail}
            nxt = max(avail, key=lambda x: pair_scores[x])
            bet.append(nxt)
            avail.remove(nxt)
        bets.append(sorted(bet))
        used.update(bet)
    return bets


def _covering_fourier_rank(
    history: tuple[CausalDrawRow, ...], *, window: int = 500
) -> list[int]:
    """Port of ``gen_signal_guided``'s inner ``fourier_rhythm_bet`` --
    descending-by-score ranking of all 49 numbers via a periodicity score
    derived from each number's own binary appearance signal. See module
    docstring NUMPY_SUBSTITUTION note for the hand-rolled-DFT rationale."""

    recent = history[-window:] if len(history) >= window else history
    width = len(recent)
    max_positive_bin = (width - 1) // 2
    scores: dict[int, float] = {}

    if max_positive_bin >= 1:
        # Trig values depend only on (k, t), never on which number is being
        # scored -- hoisted out of the per-number loop below and computed
        # once (an exact reformulation, not an approximation: this is the
        # same direct-summation DFT, just without redundant `cos`/`sin`
        # calls repeated per number).
        cos_table = [[0.0] * width for _ in range(max_positive_bin + 1)]
        sin_table = [[0.0] * width for _ in range(max_positive_bin + 1)]
        for k in range(1, max_positive_bin + 1):
            angle_step = 2.0 * math.pi * k / width
            for t in range(width):
                angle = angle_step * t
                cos_table[k][t] = math.cos(angle)
                sin_table[k][t] = math.sin(angle)

        for number in range(1, _MAX_NUM + 1):
            bits = [1.0 if number in row.numbers else 0.0 for row in recent]
            hits = sum(bits)
            if hits < 2:
                continue
            mean = hits / width
            centered = [b - mean for b in bits]

            best_bin = 0
            best_magnitude = -1.0
            for k in range(1, max_positive_bin + 1):
                cos_row = cos_table[k]
                sin_row = sin_table[k]
                real = sum(centered[t] * cos_row[t] for t in range(width))
                imag = -sum(centered[t] * sin_row[t] for t in range(width))
                magnitude = math.hypot(real, imag)
                if magnitude > best_magnitude:
                    best_magnitude = magnitude
                    best_bin = k

            frequency = best_bin / width
            if frequency == 0:
                continue
            period = 1.0 / frequency
            if not (2 < period < width / 2):
                continue

            last_hit = max(t for t in range(width) if bits[t] == 1.0)
            gap = (width - 1) - last_hit
            scores[number] = 1.0 / (abs(gap - period) + 1.0)

    ranked = sorted(range(1, _MAX_NUM + 1), key=lambda n: scores.get(n, 0.0))
    ranked.reverse()
    return ranked


def _covering_signal_guided(history: tuple[CausalDrawRow, ...]) -> list[list[int]]:
    """Port of ``gen_signal_guided`` -- the donor's own "already-verified"
    strategy (TS3+M+FO): Fourier rhythm, anti-frequency, tail-group
    round-robin, recent Markov transition, then frequency-sorted leftovers
    -- five sequentially-exclusive 6-number bets."""

    f_rank = _covering_fourier_rank(history)
    bet1 = sorted(f_rank[:6])

    excl = set(bet1)
    freq100 = Counter(
        n for row in history[-100:] for n in row.numbers[:_PICK] if n <= _MAX_NUM
    )
    cands = sorted(
        (n for n in range(1, _MAX_NUM + 1) if n not in excl),
        key=lambda x: freq100.get(x, 0),
    )
    bet2 = sorted(cands[:6])

    excl |= set(bet2)
    tail_groups: dict[int, list[tuple[int, int]]] = {i: [] for i in range(10)}
    for n in range(1, _MAX_NUM + 1):
        if n not in excl:
            tail_groups[n % 10].append((n, freq100.get(n, 0)))
    for t in tail_groups:
        tail_groups[t].sort(key=lambda item: -item[1])

    sel3: list[int] = []
    avail_tails = sorted(
        (t for t in range(10) if tail_groups[t]),
        key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0,
        reverse=True,
    )
    idx_g = {t: 0 for t in range(10)}
    while len(sel3) < _PICK:
        added = False
        for t in avail_tails:
            if len(sel3) >= _PICK:
                break
            if idx_g[t] < len(tail_groups[t]):
                num, _count = tail_groups[t][idx_g[t]]
                if num not in sel3:
                    sel3.append(num)
                    added = True
                idx_g[t] += 1
        if not added:
            break
    if len(sel3) < _PICK:
        rem = [n for n in range(1, _MAX_NUM + 1) if n not in excl and n not in sel3]
        rem.sort(key=lambda x: -freq100.get(x, 0))
        sel3.extend(rem[: _PICK - len(sel3)])
    bet3 = sorted(sel3[:_PICK])

    excl |= set(bet3)
    # Donor: `history[-30:] if len(history) >= 30 else history` -- Python
    # slicing already returns the whole tuple when it is shorter than 30,
    # so the conditional is provably redundant; simplified to the direct
    # slice (same final value in every case, not a behavior change).
    recent30 = history[-30:]
    trans: Counter[tuple[int, int]] = Counter()
    for i in range(len(recent30) - 1):
        for p in recent30[i].numbers:
            for q in recent30[i + 1].numbers:
                trans[(p, q)] += 1
    last_row = history[-1]
    last_nums = last_row.numbers
    mk = {n: sum(trans.get((p, n), 0) for p in last_nums) for n in range(1, _MAX_NUM + 1)}
    mk_cands = sorted(
        (n for n in range(1, _MAX_NUM + 1) if n not in excl), key=lambda x: -mk[x]
    )
    bet4 = sorted(mk_cands[:6])

    excl |= set(bet4)
    left = sorted(
        (n for n in range(1, _MAX_NUM + 1) if n not in excl),
        key=lambda x: -freq100.get(x, 0),
    )
    bet5 = sorted(left[:6])

    return [bet1, bet2, bet3, bet4, bet5]


def _covering_strategy_portfolio(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    """Combine all eight ticket-batches ``main()`` computes for one draw
    into this candidate's native 40-ticket portfolio (see module docstring
    OUTPUT_SHAPE INFERENCE note)."""

    groups: list[list[list[int]]] = [
        _covering_zero_overlap(_COVERING_GROUP_SIZE, seed=42),
        _covering_anchor_k(_COVERING_GROUP_SIZE, 2, seed=42),
        _covering_anchor_k(_COVERING_GROUP_SIZE, 3, seed=42),
        _covering_anchor_k(_COVERING_GROUP_SIZE, 4, seed=42),
        _covering_random_baseline(_COVERING_GROUP_SIZE, seed=42),
        _covering_signal_guided(history),
        _covering_cooccurrence_guided(history, _COVERING_GROUP_SIZE, window=100, seed=42),
        _covering_zero_overlap(_COVERING_GROUP_SIZE, seed=len(history) % 10000),
    ]
    return tuple(tuple(bet) for group in groups for bet in group)


class BigLottoCoveringStrategyResearchAdapter(PortfolioBetAdapter):
    """Covering-strategy scientific-research portfolio -- a 40-native-ticket
    portfolio. See module docstring OUTPUT_SHAPE INFERENCE note: this
    candidate's 40-ticket composition is a disclosed, evidence-based
    inference (no single donor callable or separate materialization script
    produces 40 tickets directly), not a directly-observed single
    entrypoint.

    ``min_history=200`` matches ``main()``'s own dynamic-backtest default
    (``backtest_dynamic``'s ``min_hist=200``), the only minimum-history
    threshold explicitly present in the donor source.
    """

    strategy_id = _COVERING_STRATEGY_ID
    strategy_name = "大樂透 覆蓋策略科學研究組合"
    strategy_version = "v0.1"
    min_history = _COVERING_MIN_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _COVERING_NATIVE_TICKET_COUNT

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _covering_strategy_portfolio(history)


# ═════════════════════════════════════════════════════════════════════════
# legacy_biglotto__evolution_engine__3df019c31ce4
# ═════════════════════════════════════════════════════════════════════════

_EVOLUTION_STRATEGY_ID = "legacy_biglotto__evolution_engine__3df019c31ce4"
_EVOLUTION_MIN_HISTORY = 501
_EVOLUTION_MAX_NATIVE_TICKET_COUNT = 10
_EVOLUTION_SEED = 42
_EVOLUTION_POP_SIZE = 80
_EVOLUTION_N_GENERATIONS = 10
_EVOLUTION_N_TEST = 1500
_EVOLUTION_MIN_TRAIN = 500
_EVOLUTION_BASELINE_M3 = 0.0186


# ─── feature library (port of strategy_base.py's FeatureLibrary; only the
#     members generate_seed_population's 14 strategies actually reach --
#     zonal_density_score/gap_momentum are unused donor-side dead code) ────


def _evo_frequency(draws: list[list[int]], window: int | None = None) -> list[float]:
    d = draws[-window:] if window else draws
    freq = [0.0] * _MAX_NUM
    for row in d:
        for n in row:
            freq[n - 1] += 1
    return [f / len(d) for f in freq]


def _evo_build_binary_matrix(draws: list[list[int]]) -> list[list[int]]:
    mat = [[0] * _MAX_NUM for _ in range(len(draws))]
    for i, row in enumerate(draws):
        for n in row:
            mat[i][n - 1] = 1
    return mat


def _evo_gap_current(draws: list[list[int]]) -> list[int]:
    gaps = [0] * _MAX_NUM
    for j in range(_MAX_NUM):
        found = False
        for i in range(len(draws) - 1, -1, -1):
            if (j + 1) in draws[i]:
                gaps[j] = len(draws) - 1 - i
                found = True
                break
        if not found:
            gaps[j] = len(draws)
    return gaps


def _evo_gap_mean_std(draws: list[list[int]]) -> tuple[list[float], list[float]]:
    means = [0.0] * _MAX_NUM
    stds = [0.0] * _MAX_NUM
    for j in range(_MAX_NUM):
        positions = [i for i in range(len(draws)) if (j + 1) in draws[i]]
        if len(positions) >= 2:
            gaps = [positions[k + 1] - positions[k] for k in range(len(positions) - 1)]
            mean = sum(gaps) / len(gaps)
            variance = sum((g - mean) ** 2 for g in gaps) / len(gaps)
            means[j] = mean
            stds[j] = math.sqrt(variance)
        else:
            means[j] = float(len(draws))
            stds[j] = 0.0
    return means, stds


def _evo_gap_pressure(draws: list[list[int]]) -> list[float]:
    curr_gaps = _evo_gap_current(draws)
    means, stds = _evo_gap_mean_std(draws)
    pressure = [0.0] * _MAX_NUM
    for j in range(_MAX_NUM):
        if stds[j] > 0:
            pressure[j] = (curr_gaps[j] - means[j]) / stds[j]
    return pressure


def _evo_hot_cold_score(draws: list[list[int]], hot_w: int = 30, cold_w: int = 100) -> list[float]:
    hot = _evo_frequency(draws, hot_w)
    cold = _evo_frequency(draws, cold_w)
    return [h - c for h, c in zip(hot, cold, strict=True)]


def _evo_co_occurrence(draws: list[list[int]], window: int = 100) -> list[list[int]]:
    d = draws[-window:]
    comat = [[0] * _MAX_NUM for _ in range(_MAX_NUM)]
    for row in d:
        for i, a in enumerate(row):
            for b in row[i + 1 :]:
                comat[a - 1][b - 1] += 1
                comat[b - 1][a - 1] += 1
    return comat


def _evo_sum_trend(draws: list[list[int]], window: int = 30) -> list[int]:
    return [sum(row) for row in draws[-window:]]


def _evo_consecutive_pairs(draws: list[list[int]], window: int = 50) -> list[float]:
    d = draws[-window:]
    counts = [0.0] * _MAX_NUM
    for row in d:
        s = sorted(row)
        for i in range(len(s) - 1):
            if s[i + 1] - s[i] == 1:
                counts[s[i] - 1] += 1
                counts[s[i + 1] - 1] += 1
    return [c / len(d) for c in counts]


def _pearson_correlation(x: list[float], y: list[float]) -> float:
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    var_x = sum((v - mean_x) ** 2 for v in x) / n
    var_y = sum((v - mean_y) ** 2 for v in y) / n
    std_x = math.sqrt(var_x)
    std_y = math.sqrt(var_y)
    if std_x <= 0 or std_y <= 0:
        return 0.0
    covariance = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / n
    return covariance / (std_x * std_y)


def _evo_lag_autocorrelation(draws: list[list[int]], lag: int = 1) -> list[float]:
    bmat = _evo_build_binary_matrix(draws)
    n = len(draws)
    if n <= lag:
        return [0.0] * _MAX_NUM
    corrs = [0.0] * _MAX_NUM
    for j in range(_MAX_NUM):
        x = [float(bmat[t][j]) for t in range(lag, n)]
        y = [float(bmat[t][j]) for t in range(0, n - lag)]
        if _stdev(x) > 0 and _stdev(y) > 0:
            corrs[j] = _pearson_correlation(x, y)
    return corrs


def _stdev(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def _evo_fourier_phase(
    draws: list[list[int]], top_k: int = 3
) -> tuple[list[list[float]], list[list[float]]]:
    bmat = _evo_build_binary_matrix(draws)
    n = len(draws)
    phases = [[0.0] * top_k for _ in range(_MAX_NUM)]
    magnitudes = [[0.0] * top_k for _ in range(_MAX_NUM)]
    max_bin = n // 2
    if n == 0 or max_bin < 1:
        return phases, magnitudes

    # Trig values depend only on (k, t), never on which number's series is
    # being transformed -- hoisted out of the per-number loop (an exact
    # reformulation of the same direct-summation DFT, not an approximation).
    cos_table = [[0.0] * n for _ in range(max_bin + 1)]
    sin_table = [[0.0] * n for _ in range(max_bin + 1)]
    for k in range(1, max_bin + 1):
        angle_step = 2.0 * math.pi * k / n
        for t in range(n):
            angle = angle_step * t
            cos_table[k][t] = math.cos(angle)
            sin_table[k][t] = math.sin(angle)

    for j in range(_MAX_NUM):
        series = [float(bmat[t][j]) for t in range(n)]
        bin_real = [0.0] * (max_bin + 1)
        bin_imag = [0.0] * (max_bin + 1)
        bin_mag = [0.0] * (max_bin + 1)
        for k in range(1, max_bin + 1):
            cos_row = cos_table[k]
            sin_row = sin_table[k]
            real = sum(series[t] * cos_row[t] for t in range(n))
            imag = -sum(series[t] * sin_row[t] for t in range(n))
            bin_real[k] = real
            bin_imag[k] = imag
            bin_mag[k] = math.hypot(real, imag)
        ranked_bins = sorted(range(1, max_bin + 1), key=lambda k: bin_mag[k])
        ranked_bins = ranked_bins[-top_k:]
        ranked_bins.reverse()
        for ki, k in enumerate(ranked_bins):
            phases[j][ki] = math.atan2(bin_imag[k], bin_real[k])
            magnitudes[j][ki] = bin_mag[k]
    return phases, magnitudes


def _evo_markov_transition(draws: list[list[int]], order: int = 1) -> list[list[float]]:
    bmat = _evo_build_binary_matrix(draws)
    n = len(draws)
    trans = [[[0, 0], [0, 0]] for _ in range(_MAX_NUM)]
    for j in range(_MAX_NUM):
        for i in range(order, n):
            prev = bmat[i - order][j]
            curr = bmat[i][j]
            trans[j][prev][curr] += 1
    probs = [[0.0, 0.0] for _ in range(_MAX_NUM)]
    for j in range(_MAX_NUM):
        for s in range(2):
            total = trans[j][s][0] + trans[j][s][1]
            if total > 0:
                probs[j][s] = trans[j][s][1] / total
    return probs


def _evo_deviation_score(draws: list[list[int]], window: int = 100) -> list[float]:
    expected = 6.0 / _MAX_NUM
    freq = _evo_frequency(draws, window)
    return [(f - expected) / max(expected, 1e-10) for f in freq]


# ─── strategy population (port of strategy_generator.py) ───────────────────


class _EvoStrategy:
    """Port of ``BaseStrategy``."""

    name: str
    category: str
    params: dict[str, Any]

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        raise NotImplementedError

    def mutate(self, rng: random.Random) -> _EvoStrategy:
        return self


class _FrequencyStrategy(_EvoStrategy):
    def __init__(self, window: int = 50, mode: str = "hot", top_n: int = 6) -> None:
        self.params = {"window": window, "mode": mode, "top_n": top_n}
        self.category = "stable"
        self.name = f"Freq_{mode}_w{window}"

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        freq = _evo_frequency(draws, self.params["window"])
        ranked = sorted(range(_MAX_NUM), key=lambda i: freq[i])
        if self.params["mode"] == "hot":
            idx = ranked[-n_select:]
        elif self.params["mode"] == "cold":
            idx = ranked[:n_select]
        else:
            hot = ranked[-(n_select // 2) :] if n_select // 2 else []
            cold = ranked[: n_select - n_select // 2]
            idx = hot + cold
        return sorted(i + 1 for i in idx)[:n_select]

    def mutate(self, rng: random.Random) -> _FrequencyStrategy:
        s = copy.deepcopy(self)
        s.params["window"] = max(10, s.params["window"] + rng.randint(-20, 20))
        s.params["mode"] = rng.choice(["hot", "cold", "mixed"])
        s.name = f"Freq_{s.params['mode']}_w{s.params['window']}"
        return s


class _GapPressureStrategy(_EvoStrategy):
    def __init__(self, threshold: float = 1.0) -> None:
        self.params = {"threshold": threshold}
        self.category = "burst"
        self.name = f"GapPressure_t{threshold:.1f}"

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        pressure = _evo_gap_pressure(draws)
        candidates = [i for i in range(_MAX_NUM) if pressure[i] > self.params["threshold"]]
        if len(candidates) >= n_select:
            top = sorted(candidates, key=lambda i: pressure[i])[-n_select:]
        else:
            top = sorted(range(_MAX_NUM), key=lambda i: pressure[i])[-n_select:]
        return sorted(i + 1 for i in top)[:n_select]

    def mutate(self, rng: random.Random) -> _GapPressureStrategy:
        s = copy.deepcopy(self)
        s.params["threshold"] = max(0.1, s.params["threshold"] + rng.uniform(-0.5, 0.5))
        s.name = f"GapPressure_t{s.params['threshold']:.1f}"
        return s


class _MarkovStrategy(_EvoStrategy):
    def __init__(self, order: int = 1, weight_prev: float = 0.6) -> None:
        self.params = {"order": order, "weight_prev": weight_prev}
        self.category = "stable"
        self.name = f"Markov_o{order}_w{weight_prev:.1f}"

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        probs = _evo_markov_transition(draws, self.params["order"])
        bmat = _evo_build_binary_matrix(draws)
        last = bmat[-1]
        w = self.params["weight_prev"]
        scores = [0.0] * _MAX_NUM
        for j in range(_MAX_NUM):
            prev_state = last[j]
            scores[j] = probs[j][prev_state] * (w if prev_state == 1 else (1 - w))
        top = sorted(range(_MAX_NUM), key=lambda i: scores[i])[-n_select:]
        return sorted(i + 1 for i in top)

    def mutate(self, rng: random.Random) -> _MarkovStrategy:
        s = copy.deepcopy(self)
        s.params["order"] = rng.choice([1, 2, 3])
        s.params["weight_prev"] = min(
            0.9, max(0.1, s.params["weight_prev"] + rng.uniform(-0.2, 0.2))
        )
        s.name = f"Markov_o{s.params['order']}_w{s.params['weight_prev']:.1f}"
        return s


class _DeviationStrategy(_EvoStrategy):
    def __init__(self, window: int = 100, direction: str = "under") -> None:
        self.params = {"window": window, "direction": direction}
        self.category = "burst"
        self.name = f"Deviation_{direction}_w{window}"

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        dev = _evo_deviation_score(draws, self.params["window"])
        ranked = sorted(range(_MAX_NUM), key=lambda i: dev[i])
        idx = ranked[:n_select] if self.params["direction"] == "under" else ranked[-n_select:]
        return sorted(i + 1 for i in idx)

    def mutate(self, rng: random.Random) -> _DeviationStrategy:
        s = copy.deepcopy(self)
        s.params["window"] = max(20, s.params["window"] + rng.randint(-30, 30))
        s.params["direction"] = rng.choice(["under", "over"])
        s.name = f"Deviation_{s.params['direction']}_w{s.params['window']}"
        return s


class _FourierCycleStrategy(_EvoStrategy):
    def __init__(self, top_k: int = 3, phase_threshold: float = 0.5) -> None:
        self.params = {"top_k": top_k, "phase_threshold": phase_threshold}
        self.category = "conditional"
        self.name = f"Fourier_k{top_k}_p{phase_threshold:.1f}"

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        phases, mags = _evo_fourier_phase(draws, self.params["top_k"])
        scores = [0.0] * _MAX_NUM
        for j in range(_MAX_NUM):
            for k in range(self.params["top_k"]):
                phase_pred = math.cos(phases[j][k])
                scores[j] += mags[j][k] * max(0.0, phase_pred)
        top = sorted(range(_MAX_NUM), key=lambda i: scores[i])[-n_select:]
        return sorted(i + 1 for i in top)

    def mutate(self, rng: random.Random) -> _FourierCycleStrategy:
        s = copy.deepcopy(self)
        s.params["top_k"] = rng.choice([1, 2, 3, 5])
        s.params["phase_threshold"] = min(
            1.0, max(0.1, s.params["phase_threshold"] + rng.uniform(-0.3, 0.3))
        )
        s.name = f"Fourier_k{s.params['top_k']}_p{s.params['phase_threshold']:.1f}"
        return s


class _CoOccurrenceStrategy(_EvoStrategy):
    def __init__(self, window: int = 100, seed_count: int = 2) -> None:
        self.params = {"window": window, "seed_count": seed_count}
        self.category = "synergy"
        self.name = f"CoOccur_w{window}_s{seed_count}"

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        comat = _evo_co_occurrence(draws, self.params["window"])
        last = draws[-1]
        scores = [0.0] * _MAX_NUM
        for n in last[: self.params["seed_count"]]:
            for j in range(_MAX_NUM):
                scores[j] += comat[n - 1][j]
        for n in last:
            scores[n - 1] = 0.0
        top = sorted(range(_MAX_NUM), key=lambda i: scores[i])[-n_select:]
        return sorted(i + 1 for i in top)

    def mutate(self, rng: random.Random) -> _CoOccurrenceStrategy:
        s = copy.deepcopy(self)
        s.params["window"] = max(30, s.params["window"] + rng.randint(-30, 30))
        s.params["seed_count"] = rng.choice([1, 2, 3, 4])
        s.name = f"CoOccur_w{s.params['window']}_s{s.params['seed_count']}"
        return s


class _LagAutoCorrelationStrategy(_EvoStrategy):
    def __init__(self, lag: int = 1, threshold: float = 0.05) -> None:
        self.params = {"lag": lag, "threshold": threshold}
        self.category = "conditional"
        self.name = f"LagAC_l{lag}_t{threshold:.2f}"

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        corrs = _evo_lag_autocorrelation(draws, self.params["lag"])
        bmat = _evo_build_binary_matrix(draws)
        last = bmat[-1]
        scores = [0.0] * _MAX_NUM
        for j in range(_MAX_NUM):
            if corrs[j] > self.params["threshold"]:
                scores[j] = corrs[j] * (1.0 if last[j] else 0.5)
            elif corrs[j] < -self.params["threshold"]:
                scores[j] = abs(corrs[j]) * (1.0 if not last[j] else 0.3)
        if sum(1 for v in scores if v > 0) < n_select:
            freq = _evo_frequency(draws, 50)
            scores = [scores[i] + freq[i] * 0.01 for i in range(_MAX_NUM)]
        top = sorted(range(_MAX_NUM), key=lambda i: scores[i])[-n_select:]
        return sorted(i + 1 for i in top)

    def mutate(self, rng: random.Random) -> _LagAutoCorrelationStrategy:
        s = copy.deepcopy(self)
        s.params["lag"] = rng.choice([1, 2, 3, 5, 7, 10])
        s.params["threshold"] = min(
            0.2, max(0.01, s.params["threshold"] + rng.uniform(-0.03, 0.03))
        )
        s.name = f"LagAC_l{s.params['lag']}_t{s.params['threshold']:.2f}"
        return s


class _ConsecutivePatternStrategy(_EvoStrategy):
    def __init__(self, window: int = 50, weight: float = 0.3) -> None:
        self.params = {"window": window, "weight": weight}
        self.category = "conditional"
        self.name = f"ConsecPat_w{window}"

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        consec = _evo_consecutive_pairs(draws, self.params["window"])
        freq = _evo_frequency(draws, self.params["window"])
        w = self.params["weight"]
        scores = [w * consec[i] + (1 - w) * freq[i] for i in range(_MAX_NUM)]
        top = sorted(range(_MAX_NUM), key=lambda i: scores[i])[-n_select:]
        return sorted(i + 1 for i in top)

    def mutate(self, rng: random.Random) -> _ConsecutivePatternStrategy:
        s = copy.deepcopy(self)
        s.params["window"] = max(20, s.params["window"] + rng.randint(-20, 20))
        s.params["weight"] = min(0.95, max(0.05, s.params["weight"] + rng.uniform(-0.15, 0.15)))
        s.name = f"ConsecPat_w{s.params['window']}"
        return s


class _ZonalBalanceStrategy(_EvoStrategy):
    def __init__(self, zones: int = 5, window: int = 50) -> None:
        self.params = {"zones": zones, "window": window}
        self.category = "stable"
        self.name = f"Zonal_z{zones}_w{window}"

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        freq = _evo_frequency(draws, self.params["window"])
        z = self.params["zones"]
        zone_size = _MAX_NUM // z + 1
        selected: list[int] = []
        for zi in range(z):
            start = zi * zone_size
            end = min(start + zone_size, _MAX_NUM)
            if start >= end:
                continue
            zone_freq = freq[start:end]
            best = zone_freq.index(max(zone_freq)) + start
            selected.append(best + 1)
        while len(selected) < n_select:
            ranked_desc = sorted(range(_MAX_NUM), key=lambda i: freq[i], reverse=True)
            remaining = [i + 1 for i in ranked_desc if (i + 1) not in selected]
            if remaining:
                selected.append(remaining[0])
            else:
                break
        return sorted(selected[:n_select])

    def mutate(self, rng: random.Random) -> _ZonalBalanceStrategy:
        s = copy.deepcopy(self)
        s.params["zones"] = rng.choice([3, 4, 5, 6, 7])
        s.params["window"] = max(20, s.params["window"] + rng.randint(-20, 20))
        s.name = f"Zonal_z{s.params['zones']}_w{s.params['window']}"
        return s


class _SumTargetStrategy(_EvoStrategy):
    def __init__(self, window: int = 100, tolerance: int = 15) -> None:
        self.params = {"window": window, "tolerance": tolerance}
        self.category = "stable"
        self.name = f"SumTarget_w{window}_t{tolerance}"

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        sums = _evo_sum_trend(draws, self.params["window"])
        target_sum = sum(sums) / len(sums)
        freq = _evo_frequency(draws, self.params["window"])
        candidates = sorted(range(_MAX_NUM), key=lambda i: freq[i], reverse=True)[:20]
        best_combo: list[int] | None = None
        best_diff = float("inf")
        rng = random.Random(42)
        for _ in range(100):
            combo = sorted(n + 1 for n in rng.sample(candidates, n_select))
            diff = abs(sum(combo) - target_sum)
            if diff < best_diff:
                best_diff = diff
                best_combo = combo
        return best_combo or sorted(i + 1 for i in candidates[:n_select])

    def mutate(self, rng: random.Random) -> _SumTargetStrategy:
        s = copy.deepcopy(self)
        s.params["window"] = max(30, s.params["window"] + rng.randint(-30, 30))
        s.params["tolerance"] = max(5, s.params["tolerance"] + rng.randint(-5, 5))
        s.name = f"SumTarget_w{s.params['window']}_t{s.params['tolerance']}"
        return s


class _HotColdMixStrategy(_EvoStrategy):
    def __init__(self, hot_w: int = 30, cold_w: int = 100, hot_ratio: float = 0.5) -> None:
        self.params = {"hot_w": hot_w, "cold_w": cold_w, "hot_ratio": hot_ratio}
        self.category = "stable"
        self.name = f"HotCold_h{hot_w}_c{cold_w}_r{hot_ratio:.1f}"

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        hc = _evo_hot_cold_score(draws, self.params["hot_w"], self.params["cold_w"])
        n_hot = max(1, int(n_select * self.params["hot_ratio"]))
        n_cold = n_select - n_hot
        ranked = sorted(range(_MAX_NUM), key=lambda i: hc[i])
        hot_nums = [i + 1 for i in ranked[-n_hot:]] if n_hot else []
        cold_nums = [i + 1 for i in ranked[:n_cold]] if n_cold else []
        return sorted(set(hot_nums + cold_nums))[:n_select]

    def mutate(self, rng: random.Random) -> _HotColdMixStrategy:
        s = copy.deepcopy(self)
        s.params["hot_w"] = max(10, s.params["hot_w"] + rng.randint(-10, 10))
        s.params["cold_w"] = max(30, s.params["cold_w"] + rng.randint(-20, 20))
        s.params["hot_ratio"] = min(0.8, max(0.2, s.params["hot_ratio"] + rng.uniform(-0.2, 0.2)))
        s.name = (
            f"HotCold_h{s.params['hot_w']}_c{s.params['cold_w']}_r{s.params['hot_ratio']:.1f}"
        )
        return s


class _OddEvenBalanceStrategy(_EvoStrategy):
    def __init__(self, target_odd: int = 3, window: int = 50) -> None:
        self.params = {"target_odd": target_odd, "window": window}
        self.category = "stable"
        self.name = f"OddEven_o{target_odd}_w{window}"

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        freq = _evo_frequency(draws, self.params["window"])
        odds = [i for i in range(_MAX_NUM) if (i + 1) % 2 == 1]
        evens = [i for i in range(_MAX_NUM) if (i + 1) % 2 == 0]
        n_odd = self.params["target_odd"]
        n_even = n_select - n_odd
        odd_sorted = sorted(odds, key=lambda i: freq[i], reverse=True)[:n_odd]
        even_sorted = sorted(evens, key=lambda i: freq[i], reverse=True)[:n_even]
        return sorted(i + 1 for i in odd_sorted + even_sorted)

    def mutate(self, rng: random.Random) -> _OddEvenBalanceStrategy:
        s = copy.deepcopy(self)
        s.params["target_odd"] = rng.choice([2, 3, 4])
        s.params["window"] = max(20, s.params["window"] + rng.randint(-15, 15))
        s.name = f"OddEven_o{s.params['target_odd']}_w{s.params['window']}"
        return s


class _WeightedEnsembleStrategy(_EvoStrategy):
    def __init__(self, strategies: list[_EvoStrategy], weights: list[float] | None = None) -> None:
        names = "+".join(s.name[:10] for s in strategies[:3])
        self.name = f"Ensemble({names})"
        self.category = "synergy"
        self.strategies = strategies
        self.weights = weights or [1.0 / len(strategies)] * len(strategies)
        self.params = {"n_strategies": len(strategies), "weights": self.weights}

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        scores = [0.0] * _MAX_NUM
        for strat, w in zip(self.strategies, self.weights, strict=True):
            nums = strat.predict(draws, n_select=12)
            for n in nums:
                scores[n - 1] += w
        top = sorted(range(_MAX_NUM), key=lambda i: scores[i])[-n_select:]
        return sorted(i + 1 for i in top)

    def mutate(self, rng: random.Random) -> _WeightedEnsembleStrategy:
        s = copy.deepcopy(self)
        for i in range(len(s.weights)):
            s.weights[i] = max(0.05, s.weights[i] + rng.uniform(-0.15, 0.15))
        total = sum(s.weights)
        s.weights = [w / total for w in s.weights]
        if s.strategies:
            idx = rng.randrange(len(s.strategies))
            s.strategies[idx] = s.strategies[idx].mutate(rng)
        s.params["weights"] = s.weights
        return s


class _NegativeFilterStrategy(_EvoStrategy):
    def __init__(
        self, base_strategy: _EvoStrategy, kill_count: int = 5, kill_window: int = 30
    ) -> None:
        self.name = f"NegFilter({base_strategy.name[:15]})"
        self.category = "conditional"
        self.base = base_strategy
        self.params = {"kill_count": kill_count, "kill_window": kill_window}

    def predict(self, draws: list[list[int]], n_select: int = 6) -> list[int]:
        freq = _evo_frequency(draws, self.params["kill_window"])
        kill_count = self.params["kill_count"]
        kill_set = set(i + 1 for i in sorted(range(_MAX_NUM), key=lambda i: freq[i])[-kill_count:])
        candidates = self.base.predict(draws, n_select=n_select + kill_count)
        filtered = [n for n in candidates if n not in kill_set]
        if len(filtered) < n_select:
            ranked = sorted(range(_MAX_NUM), key=lambda i: freq[i])
            filtered_set = set(filtered)
            extras = [
                i + 1 for i in ranked if (i + 1) not in filtered_set and (i + 1) not in kill_set
            ]
            filtered.extend(extras[: n_select - len(filtered)])
        return sorted(filtered[:n_select])

    def mutate(self, rng: random.Random) -> _NegativeFilterStrategy:
        s = copy.deepcopy(self)
        s.params["kill_count"] = rng.choice([3, 5, 7, 10])
        s.params["kill_window"] = max(10, s.params["kill_window"] + rng.randint(-10, 10))
        s.base = s.base.mutate(rng)
        s.name = f"NegFilter({s.base.name[:15]})"
        return s


def _evo_generate_seed_population(rng: random.Random, size: int = 80) -> list[_EvoStrategy]:
    """Port of ``generate_seed_population``."""

    population: list[_EvoStrategy] = []

    for w in (30, 50, 100, 200):
        for m in ("hot", "cold", "mixed"):
            population.append(_FrequencyStrategy(window=w, mode=m))

    for t in (0.5, 1.0, 1.5, 2.0, 2.5):
        population.append(_GapPressureStrategy(threshold=t))

    for o in (1, 2, 3):
        for w in (0.3, 0.5, 0.7):
            population.append(_MarkovStrategy(order=o, weight_prev=w))

    for w in (50, 100, 200, 500):
        for d in ("under", "over"):
            population.append(_DeviationStrategy(window=w, direction=d))

    for k in (1, 2, 3, 5):
        population.append(_FourierCycleStrategy(top_k=k))

    for w in (50, 100):
        for sc in (1, 2):
            population.append(_CoOccurrenceStrategy(window=w, seed_count=sc))

    for lag in (1, 2, 3, 5, 7):
        population.append(_LagAutoCorrelationStrategy(lag=lag))

    for w in (30, 50, 100):
        population.append(_ConsecutivePatternStrategy(window=w))

    for z in (3, 4, 5, 7):
        population.append(_ZonalBalanceStrategy(zones=z))

    for w in (50, 100, 200):
        population.append(_SumTargetStrategy(window=w))

    for hr in (0.3, 0.5, 0.7):
        population.append(_HotColdMixStrategy(hot_ratio=hr))

    for o in (2, 3, 4):
        population.append(_OddEvenBalanceStrategy(target_odd=o))

    base_strats = population.copy()
    for _ in range(min(10, size // 4)):
        combo = rng.sample(range(len(base_strats)), 2)
        population.append(
            _WeightedEnsembleStrategy([base_strats[combo[0]], base_strats[combo[1]]])
        )

    for _ in range(min(5, size // 6)):
        base = rng.choice(base_strats)
        population.append(_NegativeFilterStrategy(base))

    return population[:size] if len(population) > size else population


# ─── evaluator (port of evaluator.py) ───────────────────────────────────────


@dataclass
class _EvoResult:
    name: str
    strategy_ref: _EvoStrategy
    relative_random_edge: float = -1.0
    hit_ge3: float = 0.0
    leakage_flag: bool = False
    hits_array: list[int] = field(default_factory=list[int])


@dataclass(frozen=True, slots=True)
class _EvoMetrics:
    hit_ge3: float
    edge_ge3: float
    leakage_flag: bool
    hits_array: list[int]


def _evo_evaluate_m3_edge(
    strategy: _EvoStrategy, draws: list[list[int]], n_test: int = 1500
) -> _EvoMetrics:
    """Port of ``StrategyEvaluator.evaluate_m3_edge``."""

    total = len(draws)
    actual_n_test = min(n_test, total - _EVOLUTION_MIN_TRAIN)
    if actual_n_test <= 0:
        return _EvoMetrics(hit_ge3=0.0, edge_ge3=-1.0, leakage_flag=False, hits_array=[])

    sample_count = min(actual_n_test, 200)
    if sample_count == 1:
        test_indices = [_EVOLUTION_MIN_TRAIN]
    else:
        # numpy.linspace(..., dtype=int) truncates each evenly spaced float
        # toward zero (not round-to-nearest) and does not deduplicate --
        # reproduced with int() truncation over a plain list, preserving
        # any duplicate indices exactly as linspace would.
        step = (total - 1 - _EVOLUTION_MIN_TRAIN) / (sample_count - 1)
        test_indices = [
            int(_EVOLUTION_MIN_TRAIN + step * i) for i in range(sample_count)
        ]

    hits_list: list[int] = []
    recent_overlap_count = 0
    for i in test_indices:
        train = draws[:i]
        actual = set(draws[i])
        last_draw: set[int] = set(draws[i - 1]) if i > 0 else set()
        try:
            predicted = set(strategy.predict(train, 6))
            if len(predicted & last_draw) >= 4:
                recent_overlap_count += 1
            hit = len(predicted & actual)
        except Exception:
            hit = 0
        hits_list.append(hit)

    m3_rate = sum(1 for h in hits_list if h >= 3) / len(hits_list)
    penalty = 0.5 if recent_overlap_count > len(test_indices) * 0.1 else 0.0
    edge = (m3_rate - _EVOLUTION_BASELINE_M3) - penalty

    return _EvoMetrics(
        hit_ge3=m3_rate,
        edge_ge3=edge,
        leakage_flag=recent_overlap_count > 0,
        hits_array=hits_list,
    )


def _evo_run_permutation_test(
    hits_array: list[int], rng: random.Random, n_permutations: int = 300
) -> float:
    """Port of ``StrategyEvaluator.run_permutation_test`` (Monte Carlo
    binomial proxy, matching the donor's own ``rng.binomial`` substitute for
    a full shuffle permutation test)."""

    if not hits_array:
        return 1.0
    actual_m3_count = sum(1 for h in hits_array if h >= 3)
    n_trials = len(hits_array)
    better_count = 0
    for _ in range(n_permutations):
        simulated = sum(1 for _ in range(n_trials) if rng.random() < _EVOLUTION_BASELINE_M3)
        if simulated >= actual_m3_count:
            better_count += 1
    return (better_count + 1) / (n_permutations + 1)


# ─── evolution engine (port of evolution_engine.py) ─────────────────────────


class _EvolutionEngine:
    """Port of ``EvolutionEngine``."""

    def __init__(self, draws: list[list[int]], seed: int = _EVOLUTION_SEED) -> None:
        self.draws = draws
        self.rng = random.Random(seed)
        self.eval_rng = random.Random(seed)
        self.population: list[_EvoStrategy] = []
        self.results: list[_EvoResult] = []
        self.hall_of_fame: list[_EvoResult] = []
        self.graveyard: list[str] = []
        self.generation = 0
        self.hof_hits: dict[str, list[int]] = {}

    def initialize(self, pop_size: int = _EVOLUTION_POP_SIZE) -> None:
        self.population = _evo_generate_seed_population(self.rng, pop_size)

    def evaluate_population(self, n_test: int = _EVOLUTION_N_TEST) -> None:
        self.results = []
        for strat in self.population:
            try:
                metrics = _evo_evaluate_m3_edge(strat, self.draws, n_test)
            except Exception:
                continue
            result = _EvoResult(
                name=strat.name,
                strategy_ref=strat,
                relative_random_edge=metrics.edge_ge3,
                hit_ge3=metrics.hit_ge3,
                leakage_flag=metrics.leakage_flag,
                hits_array=metrics.hits_array,
            )
            self.results.append(result)
            if result.relative_random_edge > 0.001 and not metrics.leakage_flag:
                self.hof_hits[self._strategy_key(strat)] = metrics.hits_array

    @staticmethod
    def _strategy_key(strategy: _EvoStrategy) -> str:
        payload = json.dumps(
            {"name": strategy.name, "params": _json_safe(strategy.params)}, sort_keys=True
        )
        return hashlib.md5(payload.encode("utf-8")).hexdigest()[:12]

    def select_survivors(self, keep_ratio: float = 0.5, elite_count: int = 5) -> None:
        if not self.results:
            return
        valid_results = [r for r in self.results if not r.leakage_flag]
        ranked = sorted(valid_results, key=lambda r: r.relative_random_edge, reverse=True)

        for elite in ranked[:elite_count]:
            if elite.relative_random_edge > 0:
                self.hall_of_fame.append(elite)

        n_keep = max(elite_count, int(len(ranked) * keep_ratio))
        survivors = ranked[:n_keep]
        eliminated = ranked[n_keep:] + [r for r in self.results if r.leakage_flag]
        for e in eliminated:
            self.graveyard.append(e.name)

        survivor_names = {r.name for r in survivors}
        self.population = [s for s in self.population if s.name in survivor_names]
        self.results = survivors

    def mutate_population(self, mutation_rate: float = 0.4) -> None:
        new_strats = [
            strat.mutate(self.rng) for strat in self.population if self.rng.random() < mutation_rate
        ]
        self.population.extend(new_strats)

    def crossover(self, n_offspring: int = 15) -> None:
        if len(self.population) < 2:
            return
        new_strats: list[_EvoStrategy] = []
        for _ in range(n_offspring):
            idx = self.rng.sample(range(len(self.population)), 2)
            s1, s2 = self.population[idx[0]], self.population[idx[1]]
            w0 = self.rng.uniform(0.3, 0.7)
            new_strats.append(_WeightedEnsembleStrategy([s1, s2], [w0, 1.0 - w0]))

        if len(self.population) >= 3:
            for _ in range(min(5, n_offspring // 2)):
                idx = self.rng.sample(range(len(self.population)), 3)
                strats = [self.population[i] for i in idx]
                gamma = [self.rng.gammavariate(1.0, 1.0) for _ in range(3)]
                total = sum(gamma)
                weights = [g / total for g in gamma]
                new_strats.append(_WeightedEnsembleStrategy(strats, weights))

        for _ in range(min(5, n_offspring // 3)):
            base = self.rng.choice(self.population)
            new_strats.append(
                _NegativeFilterStrategy(
                    base,
                    kill_count=self.rng.choice([3, 5, 7]),
                    kill_window=self.rng.choice([20, 30, 50]),
                )
            )

        self.population.extend(new_strats)

    def evolve_one_generation(self, n_test: int = _EVOLUTION_N_TEST) -> None:
        self.generation += 1
        self.evaluate_population(n_test)
        self.select_survivors()
        self.mutate_population()
        self.crossover()

    def run(
        self,
        n_generations: int = _EVOLUTION_N_GENERATIONS,
        n_test: int = _EVOLUTION_N_TEST,
        pop_size: int = _EVOLUTION_POP_SIZE,
    ) -> list[list[int]]:
        self.initialize(pop_size)
        for _ in range(n_generations):
            self.evolve_one_generation(n_test)
        return self._final_tickets()

    def _final_tickets(self) -> list[list[int]]:
        seen: set[str] = set()
        unique_hof: list[_EvoResult] = []
        for r in sorted(self.hall_of_fame, key=lambda x: x.relative_random_edge, reverse=True):
            key = self._strategy_key(r.strategy_ref)
            if key not in seen:
                seen.add(key)
                unique_hof.append(r)

        total_strategies = len(self.graveyard) + len(self.population)
        bonferroni_p = 0.05 / max(1, total_strategies)

        final_valid: list[tuple[_EvoResult, float]] = []
        for r in unique_hof:
            hits = self.hof_hits.get(self._strategy_key(r.strategy_ref), [])
            if hits:
                p_value = _evo_run_permutation_test(hits, self.eval_rng)
                if p_value < bonferroni_p or p_value < 0.05:
                    final_valid.append((r, p_value))

        if not final_valid:
            final_valid = [(r, 1.0) for r in unique_hof[:5]]

        final_valid.sort(key=lambda item: (item[1], -item[0].relative_random_edge))
        final_valid = final_valid[:_EVOLUTION_MAX_NATIVE_TICKET_COUNT]

        return [r.strategy_ref.predict(self.draws, 6) for r, _p in final_valid]


def _json_safe(value: object) -> object:
    if isinstance(value, list):
        items = cast("list[object]", value)
        return [_json_safe(item) for item in items]
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        return {key: _json_safe(item) for key, item in mapping.items()}
    return value


class BigLottoEvolutionEngineAdapter(PortfolioBetAdapter):
    """Strategy-population evolution engine -- a VARIABLE 1-to-10-native-
    ticket portfolio (closes below 10, down to 0, via the base class's own
    native ticket count check -- the same contract the live ``test_pce``
    adapter already proves portable, not a bespoke exception).

    ``min_history=501`` matches ``StrategyEvaluator``'s own hardcoded
    ``min_train=500`` (the evaluator needs ``total - min_train > 0`` or
    every strategy degenerates to an identical empty-result tie).
    """

    strategy_id = _EVOLUTION_STRATEGY_ID
    strategy_name = "大樂透 策略族群演化系統"
    strategy_version = "v0.1"
    min_history = _EVOLUTION_MIN_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _EVOLUTION_MAX_NATIVE_TICKET_COUNT
    minimum_native_ticket_count = 1
    maximum_native_ticket_count = _EVOLUTION_MAX_NATIVE_TICKET_COUNT

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        draws = [list(row.numbers) for row in history]
        engine = _EvolutionEngine(draws, seed=_EVOLUTION_SEED)
        tickets = engine.run()
        return tuple(tuple(ticket) for ticket in tickets)



__all__ = [
    "BigLottoBacktestAprioriAdapter",
    "BigLottoCoveringStrategyResearchAdapter",
    "BigLottoEvolutionEngineAdapter",
    "BigLottoTs3Markov4betAdapter",
]
