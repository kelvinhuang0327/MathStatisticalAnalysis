"""BigLotto native-strategy batch 18: two thin ports of frozen legacy
BACKTESTED/VERIFICATION methods (donor commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9``, the same frozen snapshot as
waves 1-14 and batches 15-17).

``BigLottoMarkovTriple4BetAdapter`` -- source
``tools/verify_markov_vs_triple_2bet.py`` (``strategy_id
legacy_biglotto__verify_markov_vs_triple_2bet__2094ee4bc361``, method_family
``markov``). The donor file independently backtests two complete two-ticket
strategies against the same baseline for comparison (``markov_2bet`` and
``triple_strike_2bet``); it never itself concatenates them. This port
bundles all four of the donor's own already-complete tickets into one
four-ticket portfolio, in the donor's own definition order (Markov bet 1,
Markov bet 2, Triple-Strike Fourier bet, Triple-Strike Cold bet) -- the
literal reading of "Markov 2-bet vs Triple-Strike 2-bet" as one combined
4-ticket identity, matching this card's pinned ``PORTFOLIO_4`` output shape.
No scoring math is invented: every ticket is exactly one of the donor's own
already-complete, already-verified 2-ticket outputs.

``BigLottoColdPool15Adapter`` -- source
``tools/backtest_biglotto_coldpool_15.py`` (``strategy_id
legacy_biglotto__backtest_biglotto_coldpool_15__2a80423e3cf5``, method_family
``hot_cold``). The donor's whole purpose is comparing its own 5-ticket
"P1+偏差互補+Sum" strategy at ``cold_pool_size=12`` against
``cold_pool_size=15``; it never merges them either. This port bundles both
complete 5-ticket runs into one ten-ticket portfolio (pool=12 first, pool=15
second, matching the donor's own ``bets12`` then ``bets15`` call order),
matching this card's pinned ``PORTFOLIO_10`` output shape. ``MIN_HISTORY =
300`` is the donor's own explicit constant (comment: "需要300期做 Sum 統計").

Both donors' own Fourier scoring function (``fourier_bet_biglotto`` /
``_bl_fourier_scores``) is structurally identical to ``biglotto_batch16.py``'s
already-verified ``_fourier_rhythm_scores``/``_fourier_rhythm_bet`` (same
``window=500`` default, same positive-frequency-bin peak-period score, same
``2 < period < window / 2`` gate, same argmax-keeps-first tie handling) --
confirmed by direct line-by-line comparison of all three donor files before
writing this port, not assumed from naming alone. Both functions are reused
unchanged from ``biglotto_batch16`` (cross-batch private-helper-import
convention, already established for this adapter family) rather than
re-derived a third time.

``BigLottoMarkovTriple4BetAdapter.min_history = 500``: the donor's own
``run_backtest`` only ever evaluates a history length once it exceeds 500
(``if target_idx <= 500: continue``); there is no separate named
"MIN_HISTORY" constant in this donor file, so this port adopts that implicit
backtest warm-up boundary -- also exactly the Fourier window size -- as the
floor, one below the donor's own first-tested length of 501.

Every donor-only randomness source is confirmed absent: neither donor
function referenced above touches ``np.random`` or any other RNG; the only
external randomness in either source file lives in ``main()``'s own
unrelated ``np.random.seed(42)`` backtest-reporting scaffold (unreachable
from either ported production entrypoint here). No algorithm was changed,
tuned, or "improved" during either port.

Both ports were verified against the real donor functions (copied verbatim
into a throwaway script, executed under a real numpy/scipy interpreter, the
donor's DB import never touched) on synthetic causal history: a
``random.Random``-seeded generator across lengths 90-1200 (3 seeds each) --
0 mismatches at or above either adapter's own ``min_history`` (500 / 300) --
plus this batch's own test module's 13 golden-fixture lengths individually
re-confirmed byte-for-byte against the same donor functions before being
pinned. A deterministic *arithmetic-progression* generator (fixed stride,
the convention ``biglotto_batch16.py``'s own test module uses) was tried
first for these same fixtures and rejected: it produces far more same-score
ties than realistic draw data, which makes ``fourier_bet_biglotto``/
``_bl_fourier_scores`` sensitive to ``biglotto_batch16.py``'s own
already-documented, already-accepted numpy-``argsort``-tie-break deviation
(see that module's docstring) far more often -- not a new discrepancy this
port introduces, just a data distribution this port's own golden fixtures
deliberately avoid so they stay a clean, exact donor match. Below
``min_history`` the underlying Fourier helper has a separate, narrower,
already-latent floating-point edge case at very short windows (<=80,
inherited from the already-merged ``biglotto_batch16.py`` helper, not
introduced here); both adapters' own ``min_history`` values keep it
structurally unreachable.
"""

# pyright: reportPrivateUsage=false
# (deliberate cross-batch private-helper-import convention -- see module
# docstring: reuses biglotto_batch16's already-verified Fourier functions
# rather than re-deriving them a third time)

from __future__ import annotations

from collections import Counter
from itertools import combinations
from statistics import mean, pstdev

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_batch16 import (
    _fourier_rhythm_bet,
    _fourier_rhythm_scores,
)

_MIN_NUM = 1
_MAX_NUM = 49
_PICK = 6

# -- BigLottoMarkovTriple4BetAdapter --------------------------------------
_MT4_MARKOV_WINDOW = 100
_MT4_COLD_WINDOW = 100
_MT4_MIN_HISTORY = 500

# -- BigLottoColdPool15Adapter ---------------------------------------------
_CP15_FOURIER_WINDOW = 500
_CP15_MARKOV_WINDOW = 30
_CP15_COLD_FREQ_WINDOW = 100
_CP15_SUM_WINDOW = 300
_CP15_DEV_WINDOW = 50
_CP15_BET5_FREQ_WINDOW = 100
_CP15_BET5_POOL_CAP = 18
_CP15_MIN_HISTORY = 300


# ---------------------------------------------------------------------------
# BigLottoMarkovTriple4BetAdapter
# ---------------------------------------------------------------------------


def _markov_2bet_scores(history: tuple[CausalDrawRow, ...]) -> Counter[int]:
    """Port ``markov_2bet``'s raw transition-count score (``window=100``,
    the donor's own default and only used value)."""

    recent = (
        history[-_MT4_MARKOV_WINDOW:]
        if len(history) >= _MT4_MARKOV_WINDOW
        else history
    )
    transitions: Counter[tuple[int, int]] = Counter()
    for index in range(len(recent) - 1):
        current_numbers = set(recent[index].numbers)
        next_numbers = recent[index + 1].numbers
        for next_number in next_numbers:
            for current_number in current_numbers:
                transitions[(current_number, next_number)] += 1

    last_draw = history[-1].numbers
    scores: Counter[int] = Counter()
    for current_number in last_draw:
        for number in range(_MIN_NUM, _MAX_NUM + 1):
            scores[number] += transitions.get((current_number, number), 0)
    return scores


def _markov_2bet(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Port ``markov_2bet``: top-6/next-6 slice of one descending ranking."""

    scores = _markov_2bet_scores(history)
    ranked = sorted(range(_MIN_NUM, _MAX_NUM + 1), key=lambda number: -scores[number])
    bet1 = tuple(sorted(ranked[0:_PICK]))
    bet2 = tuple(sorted(ranked[_PICK : 2 * _PICK]))
    return bet1, bet2


def _cold_bet_biglotto(
    history: tuple[CausalDrawRow, ...],
    exclude: frozenset[int],
) -> tuple[int, ...]:
    """Port ``cold_bet_biglotto`` (``window=100``, the donor's own default
    and only used value). Unlike ``biglotto_batch16``'s ``_cold_numbers_bet``
    (a different donor file's sum-constrained cold pool search), this
    donor's cold bet is a plain frequency-ascending pick with no sum
    constraint."""

    recent = (
        history[-_MT4_COLD_WINDOW:] if len(history) >= _MT4_COLD_WINDOW else history
    )
    frequency: Counter[int] = Counter(number for row in recent for number in row.numbers)
    candidates = [number for number in range(_MIN_NUM, _MAX_NUM + 1) if number not in exclude]
    sorted_cold = sorted(candidates, key=lambda number: frequency.get(number, 0))
    return tuple(sorted(sorted_cold[:_PICK]))


def _generate_markov_triple_4bet(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Port: Markov 2-bet plus Triple-Strike 2-bet (Fourier + Cold), bundled
    in the donor's own definition order (see module docstring)."""

    markov_bet1, markov_bet2 = _markov_2bet(history)
    fourier_bet = _fourier_rhythm_bet(history)
    cold_bet = _cold_bet_biglotto(history, exclude=frozenset(fourier_bet))
    return markov_bet1, markov_bet2, fourier_bet, cold_bet


class BigLottoMarkovTriple4BetAdapter(PortfolioBetAdapter):
    """Markov 2-bet (raw transition count) plus Triple-Strike 2-bet (Fourier
    rhythm + frequency-ascending cold), bundled as one four-ticket portfolio."""

    strategy_id = "legacy_biglotto__verify_markov_vs_triple_2bet__2094ee4bc361"
    strategy_name = "大樂透 Markov 2注 + Triple Strike 2注"
    strategy_version = "v0.1"
    min_history = _MT4_MIN_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 4

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _generate_markov_triple_4bet(history)


# ---------------------------------------------------------------------------
# BigLottoColdPool15Adapter
# ---------------------------------------------------------------------------


def _cp15_fourier_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Port ``_bl_fourier_scores`` (``window=500``) -- see module docstring:
    reuses ``biglotto_batch16``'s already-verified identical algorithm."""

    return _fourier_rhythm_scores(history)


def _cp15_markov_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Port ``_bl_markov_scores`` (``window=30``): normalized per-source-number
    transition probability, distinct from both ``_markov_2bet_scores`` above
    (different window, raw counts not normalized) and from
    ``biglotto_batch16``'s own Markov helper (different window, orthogonal
    exclusion semantics)."""

    recent = (
        history[-_CP15_MARKOV_WINDOW:]
        if len(history) >= _CP15_MARKOV_WINDOW
        else history
    )
    transitions: dict[int, Counter[int]] = {}
    for index in range(len(recent) - 1):
        for current_number in recent[index].numbers:
            bucket = transitions.setdefault(current_number, Counter())
            bucket.update(recent[index + 1].numbers)

    previous_numbers = history[-1].numbers
    scores: dict[int, float] = {}
    for previous_number in previous_numbers:
        bucket = transitions.get(previous_number, Counter())
        total = sum(bucket.values())
        if total > 0:
            for number, count in bucket.items():
                scores[number] = scores.get(number, 0.0) + count / total
    return scores


def _cp15_cold_sum_fixed(
    history: tuple[CausalDrawRow, ...],
    exclude: set[int],
    pool_size: int,
) -> tuple[int, ...]:
    """Port ``_bl_cold_sum_fixed``: cold pool (``window=100``) constrained to
    a *fixed* ``[mean-0.5sigma, mean+0.5sigma]`` sum-of-6 target over the
    trailing ``window=300`` draws -- no last-draw-conditional branching
    (contrast ``_cp15_bet5_sum_conditional`` below, which does branch)."""

    frequency: Counter[int] = Counter(
        number for row in history[-_CP15_COLD_FREQ_WINDOW:] for number in row.numbers
    )
    candidates = sorted(
        (number for number in range(_MIN_NUM, _MAX_NUM + 1) if number not in exclude),
        key=lambda number: frequency.get(number, 0),
    )
    pool = candidates[:pool_size]

    sums = [sum(row.numbers) for row in history[-_CP15_SUM_WINDOW:]]
    mu = mean(sums)
    sigma = pstdev(sums)
    low, high = mu - 0.5 * sigma, mu + 0.5 * sigma
    mid = mu

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


def _cp15_dev_complement_2bet(
    history: tuple[CausalDrawRow, ...],
    exclude: set[int],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Port ``_bl_dev_complement_2bet`` (``window=50``): hot deviation bet
    then cold deviation bet, each padded from the nearest-to-expected
    remainder when the primary rule yields fewer than six numbers."""

    recent = history[-_CP15_DEV_WINDOW:] if len(history) > _CP15_DEV_WINDOW else history
    expected = len(recent) * _PICK / _MAX_NUM
    frequency: Counter[int] = Counter()
    for row in recent:
        frequency.update(row.numbers)

    hot: list[tuple[int, float]] = []
    cold: list[tuple[int, float]] = []
    for number in range(_MIN_NUM, _MAX_NUM + 1):
        if number in exclude:
            continue
        deviation = frequency.get(number, 0) - expected
        if deviation > 1:
            hot.append((number, deviation))
        elif deviation < -1:
            cold.append((number, abs(deviation)))
    hot.sort(key=lambda item: -item[1])
    cold.sort(key=lambda item: -item[1])

    bet1 = [number for number, _deviation in hot[:_PICK]]
    used = set(bet1) | exclude
    if len(bet1) < _PICK:
        remainder = sorted(
            (number for number in range(_MIN_NUM, _MAX_NUM + 1) if number not in used),
            key=lambda number: abs(frequency.get(number, 0) - expected),
        )
        for number in remainder:
            if len(bet1) >= _PICK:
                break
            bet1.append(number)
            used.add(number)

    bet2: list[int] = []
    for number, _deviation in cold:
        if len(bet2) >= _PICK:
            break
        if number not in used:
            bet2.append(number)
            used.add(number)
    if len(bet2) < _PICK:
        for number in range(_MIN_NUM, _MAX_NUM + 1):
            if len(bet2) >= _PICK:
                break
            if number not in used:
                bet2.append(number)
                used.add(number)

    return tuple(sorted(bet1[:_PICK])), tuple(sorted(bet2[:_PICK]))


def _cp15_bet5_sum_conditional(
    history: tuple[CausalDrawRow, ...],
    pool: list[int],
) -> tuple[int, ...]:
    """Port ``_bl_bet5_sum_conditional``: last-draw-conditional sum target
    over a frequency-nearest-expected top-18 sub-pool of the remainder."""

    if len(pool) <= _PICK:
        return tuple(sorted(pool[:_PICK]))

    sums = [sum(row.numbers) for row in history[-_CP15_SUM_WINDOW:]]
    mu = mean(sums)
    sigma = pstdev(sums)
    last_sum = sum(history[-1].numbers)
    if last_sum < mu - 0.5 * sigma:
        low, high = mu, mu + sigma
    elif last_sum > mu + 0.5 * sigma:
        low, high = mu - sigma, mu
    else:
        low, high = mu - 0.5 * sigma, mu + 0.5 * sigma
    mid = (low + high) / 2.0

    frequency: Counter[int] = Counter(
        number for row in history[-_CP15_BET5_FREQ_WINDOW:] for number in row.numbers
    )
    expected = len(history[-_CP15_BET5_FREQ_WINDOW:]) * _PICK / _MAX_NUM
    pool_sorted = sorted(pool, key=lambda number: abs(frequency.get(number, 0) - expected))
    pool_candidates = (
        pool_sorted[:_CP15_BET5_POOL_CAP]
        if len(pool_sorted) > _CP15_BET5_POOL_CAP
        else pool_sorted
    )

    best_combo: tuple[int, ...] | None = None
    best_distance = float("inf")
    best_in_range = False
    for combo in combinations(pool_candidates, _PICK):
        combo_sum = sum(combo)
        in_range = low <= combo_sum <= high
        distance = abs(combo_sum - mid)
        if in_range and (not best_in_range or distance < best_distance):
            best_combo, best_distance, best_in_range = combo, distance, True
        elif not in_range and not best_in_range and distance < best_distance:
            best_combo, best_distance = combo, distance

    if best_combo is None:
        return tuple(sorted(pool_candidates[:_PICK]))
    return tuple(sorted(best_combo))


def _cp15_generate_5bet(
    history: tuple[CausalDrawRow, ...],
    cold_pool_size: int,
) -> tuple[tuple[int, ...], ...]:
    """Port ``generate_5bet``. ``neighbor_pool`` is kept as a real ``set``,
    built via the donor's own exact insertion order (iterate the last draw's
    numbers, then ``-1/0/+1`` per number): on this project's pinned CPython
    (int hashing is value-based and unrandomized), this reproduces the
    donor's own ``set``-iteration tie-break for ``bet1``'s ranking exactly,
    rather than substituting an explicit convention that could disagree with
    the donor whenever two candidates tie on score -- a real possibility
    here (unlike the 49-number Fourier ranking elsewhere in this file),
    since many neighbor-pool numbers legitimately score exactly ``0.0``.
    """

    previous_numbers = history[-1].numbers
    neighbor_pool: set[int] = set()
    for number in previous_numbers:
        for delta in (-1, 0, 1):
            neighbor = number + delta
            if _MIN_NUM <= neighbor <= _MAX_NUM:
                neighbor_pool.add(neighbor)

    fourier_scores = _cp15_fourier_scores(history)
    markov_scores = _cp15_markov_scores(history)
    fourier_max = max(fourier_scores.values()) or 1
    markov_max = max(markov_scores.values()) or 1
    scored = {
        number: fourier_scores.get(number, 0.0) / fourier_max
        + 0.5 * (markov_scores.get(number, 0) / markov_max)
        for number in neighbor_pool
    }
    ranked = sorted(neighbor_pool, key=lambda number: -scored[number])
    bet1 = tuple(sorted(ranked[:_PICK]))
    used = set(bet1)

    bet2 = _cp15_cold_sum_fixed(history, exclude=used, pool_size=cold_pool_size)
    used.update(bet2)

    bet3, bet4 = _cp15_dev_complement_2bet(history, exclude=used)
    used.update(bet3)
    used.update(bet4)

    remaining_pool = [number for number in range(_MIN_NUM, _MAX_NUM + 1) if number not in used]
    bet5 = _cp15_bet5_sum_conditional(history, remaining_pool)

    return bet1, bet2, bet3, bet4, bet5


def _generate_coldpool_compare_10bet(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    """Port ``backtest_compare``'s per-draw pair: the complete 5-ticket
    ``cold_pool_size=12`` portfolio, then the complete 5-ticket
    ``cold_pool_size=15`` portfolio, each computed independently from
    ``history`` exactly as the donor's own ``bets12``/``bets15`` calls do."""

    bets_pool_12 = _cp15_generate_5bet(history, cold_pool_size=12)
    bets_pool_15 = _cp15_generate_5bet(history, cold_pool_size=15)
    return bets_pool_12 + bets_pool_15


class BigLottoColdPool15Adapter(PortfolioBetAdapter):
    """P1+偏差互補+Sum 5-bet strategy at cold-pool sizes 12 and 15, bundled
    as one ten-ticket portfolio (pool=12 first, pool=15 second)."""

    strategy_id = "legacy_biglotto__backtest_biglotto_coldpool_15__2a80423e3cf5"
    strategy_name = "大樂透 冷號池 12 vs 15 比較 (10注)"
    strategy_version = "v0.1"
    min_history = _CP15_MIN_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 10

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _generate_coldpool_compare_10bet(history)


__all__ = ["BigLottoColdPool15Adapter", "BigLottoMarkovTriple4BetAdapter"]
