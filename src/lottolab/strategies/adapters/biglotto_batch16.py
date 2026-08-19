"""BigLotto native-strategy batch 16: single thin port of one frozen legacy
BACKTESTED method (donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``,
the same frozen snapshot as waves 1-14 and batch 15).

Source: ``tools/backtest_biglotto_markov_4bet.py`` -- ``generate_ts3_markov4``
(``strategy_id legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b``,
``method_family markov``). No algorithm was changed, tuned, or "improved"
during the port.

This batch was sized at 4 candidates by
``MATRIX_BASE_METHOD_UNIVERSE_COVERAGE_MAP_R1`` (the only Dataset-A rows
tagged ``under_covered_family``/``under_covered_family_sole_member``):
``cooccurrence_graph`` (neighbor), this method (markov), ``predict_
evolutionary_gum`` (regime), and ``anti_consensus_strategy`` (folklore).
Only this one is admitted here; the other three are documented as blocked
in this task's own evidence trail (not committed to source control -- see
the task handoff) rather than guessed at:

* ``cooccurrence_graph``'s 4-ticket output empirically requires its own
  unseeded ``np.random.choice`` fallback (``_mixed_predict``) to reach 4
  distinct tickets in the overwhelming majority of realistic history
  windows (verified: the three deterministic sub-methods alone reached at
  most 3 distinct tickets across a 20..600-length sweep on synthetic data,
  never 4) -- there is no fixed donor seed to reproduce faithfully, and
  inventing one would fabricate behavior the donor itself never pinned.
* ``predict_evolutionary_gum``'s BIG_LOTTO path is not self-contained: its
  only reachable recipe in this environment (no ``tools/data/
  frontier_library_BIG_LOTTO.json`` exists, so ``EvolutionaryGUM`` always
  falls back to its ``stable_recipe``) still delegates to
  ``StrategyLeaderboard.strat_cluster_pivot`` in a second donor file
  (``tools/strategy_leaderboard.py``) that was never part of the 221-method
  frozen legacy audit and has no independent identity/hash record --
  admitting it would silently expand this task's pinned source surface.
* ``anti_consensus_strategy``'s core method (``generate_anti_consensus_
  numbers``) does not use its own ``history`` parameter for number
  selection at all and draws every candidate via unseeded ``np.random.
  choice``; like ``cooccurrence_graph`` there is no donor-fixed seed to
  recover, only ones this port would have to invent.

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

from collections import Counter
from itertools import combinations
from math import cos, hypot, pi, sin, sqrt

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


__all__ = ["BigLottoTs3Markov4betAdapter"]
