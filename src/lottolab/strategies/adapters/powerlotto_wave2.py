"""Pure POWER_LOTTO adapters for migration Wave 2.

Wave 1 (:mod:`lottolab.strategies.adapters.powerlotto_wave1`) ported every
POWER_LOTTO ``strategy_id`` that has a row in the sealed legacy replay corpus
(``strategy_prediction_replays.jsonl``). This wave ports POWER_LOTTO methods
that exist as developed, runnable donor code in the ``LotteryNewMeraged``
archive but were *never* backtested/logged in that corpus -- standalone
``tools/*.py`` researcher scripts and two read-only research prototypes
(P173/P176), each cross-verified against the real donor algorithm executed
under NumPy/SciPy (see the PR description for the verification methodology).

Every strategy here is a pure function of causal history:

* ``power_apriori_2bet`` / ``power_apriort_ext_4bet`` -- pair co-occurrence
  (Apriori-style) association mining, two independent donor families.
* ``lag_reversion_2bet`` -- per-number median inter-arrival interval vs.
  current lag ("overdue" score); named after the donor's own governance
  test IDs (``lag_reversion_2bet``, a real ``NEW_CANDIDATE`` the donor's own
  mini-backtest rejected for lack of edge, not for code-safety reasons).
* ``power_lead_lag_2bet`` -- pairwise adjacent-draw transition matrix.
* ``power_momentum_2bet`` -- short-window vs. long-window frequency burst.
* ``power_fourier_gap_rebound_2bet`` -- the donor's own enhancement of the
  Wave 1 Fourier-rhythm family with an added not-recently-hit bonus term.
* ``power_c01``..``power_c07`` -- the P173/P176 read-only research
  prototypes (recency-decay, gap-overdue, zone-balance, pair-centrality,
  dispersion-matching, CUSUM regime, and Borda ensemble). The donor's own
  OOS study found a NULL result (no edge surviving Bonferroni correction)
  for all seven; they are ported anyway because this project's migration
  policy counts developed methods regardless of legacy-side promotion
  decisions (paralleling the BIG_LOTTO catalog's own
  ``..._REGARDLESS_LEGACY_GOVERNANCE_V1`` policy) -- research value, not a
  recommendation.

Every strategy here reuses :func:`~.powerlotto_wave1.coerce_p638_history`,
:class:`~.powerlotto_wave1.P638StrategySpec`, and the DFT engine
(:func:`~.powerlotto_wave1.bluestein_dft`) from Wave 1 rather than
duplicating them, following the cross-wave private-helper-import convention
already used between the BIG_LOTTO wave adapter modules.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Mapping
from functools import lru_cache
from itertools import combinations, pairwise
from typing import Final

from lottolab.strategies.adapters.powerlotto_wave1 import (
    P638BlockedStrategy,
    P638FirstZoneTicket,
    P638FirstZoneTicketSet,
    P638HistoryRow,
    P638StrategySpec,
    bluestein_dft,
)

_POOL: Final = 38
_PICK: Final = 6

_APRIORI_WINDOW: Final = 200
_APRIORI_EXT_WINDOW: Final = 100
_APRIORI_EXT_MIN_HISTORY: Final = 50
_LAG_REVERSION_WINDOW: Final = 500
_LEAD_LAG_WINDOW: Final = 500
_MOMENTUM_SHORT_WINDOW: Final = 15
_MOMENTUM_LONG_WINDOW: Final = 500
_FOURIER_GAP_REBOUND_WINDOW: Final = 500
_GAP_REBOUND_RECENT_WINDOW: Final = 30
_GAP_REBOUND_THRESHOLD: Final = 1.2
_GAP_REBOUND_MIN_FREQ: Final = 3
_GAP_REBOUND_WEIGHT: Final = 1.5

_C01_HALF_LIFE: Final = 50
_C01_LOOKBACK: Final = 200
_C02_MEAN_GAP: Final = 6.333
_C04_TRAINING_SIZE: Final = 500
_C04_ZONE_LOW: Final = frozenset(range(1, 14))
_C04_ZONE_MID: Final = frozenset(range(14, 26))
_C04_ZONE_HIGH: Final = frozenset(range(26, 39))
# Iteration order of the donor's own `set(range(...))` zone objects, used
# (via Python's stable sort) as the tie-break order when frequency scores
# are equal. LOW/MID happen to iterate ascending; HIGH does not, because of
# CPython's hash-table sizing at exactly 13 small-int elements. Verified
# empirically on this repo's own Python 3.13 interpreter (matches the
# already-accepted precedent for the Wave 1 zone-gap donor's own frozenset
# quirk) rather than assumed.
_C04_ZONE_LOW_ITER: Final = tuple(sorted(_C04_ZONE_LOW))
_C04_ZONE_MID_ITER: Final = tuple(sorted(_C04_ZONE_MID))
_C04_ZONE_HIGH_ITER: Final = (32, 33, 34, 35, 36, 37, 38, 26, 27, 28, 29, 30, 31)
_C03_MIN_PAIR_COOCCURRENCE: Final = 2
_C06_CUSUM_THRESHOLD: Final = 2.0
_C06_CUSUM_SLACK: Final = 0.5
_C06_REGIME_WINDOWS: Final[Mapping[str, int]] = {"high": 50, "neutral": 100, "low": 200}


def _recent(
    history: tuple[P638HistoryRow, ...],
    window: int,
) -> tuple[P638HistoryRow, ...]:
    """Trailing window matching plain ``history[-window:]`` slicing semantics.

    Duplicated locally rather than imported from Wave 1 -- this file's own
    per-module ``_recent`` copy matches the existing convention already used
    between :mod:`.daily539_portfolio_phase2` and
    :mod:`.daily539_portfolio_frequency`, each of which independently defines
    the same trivial helper rather than sharing it across wave modules.
    """

    return history[-window:] if len(history) > window else history


def _ranked_chunks(scores: Mapping[int, float], n_bets: int) -> P638FirstZoneTicketSet:
    """Split a full descending ranking into ``n_bets`` consecutive 6-number chunks.

    Ties use ascending-number order, the same substitute this adapter family
    already uses everywhere else for NumPy's unstable default ``argsort`` (see
    :mod:`.powerlotto_wave1`): every donor this helper serves ranks via
    ``np.argsort(scores[1:])[::-1]``, whose tie order among equal scores is an
    implementation artifact, not part of the algorithm. Cross-execution against
    the real donors confirmed score vectors match exactly; only tied-score
    ordering can differ.
    """

    ranked = sorted(range(1, _POOL + 1), key=lambda number: (-scores[number], number))
    return tuple(
        tuple(sorted(ranked[index * _PICK : (index + 1) * _PICK])) for index in range(n_bets)
    )


def _ranked_single(scores: Mapping[int, float]) -> P638FirstZoneTicket:
    ranked = sorted(range(1, _POOL + 1), key=lambda number: (-scores[number], number))
    return tuple(sorted(ranked[:_PICK]))


# ---------------------------------------------------------------------------
# power_apriori_2bet -- donor tools/power_apriori_audit.py::apriori_predict
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4096)
def _apriori_scores(
    history: tuple[P638HistoryRow, ...],
    window: int = _APRIORI_WINDOW,
) -> dict[int, float]:
    recent = _recent(history, window)
    pair_counts: Counter[tuple[int, int]] = Counter()
    for row in recent:
        for pair in combinations(row.numbers, 2):
            pair_counts[pair] += 1
    top_pairs = sorted(pair_counts.items(), key=lambda item: item[1], reverse=True)[:50]
    scores = {number: 0.0 for number in range(1, _POOL + 1)}
    for (first, second), count in top_pairs:
        scores[first] += count
        scores[second] += count
    return scores


@lru_cache(maxsize=4096)
def _apriori_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return _ranked_chunks(_apriori_scores(history, _APRIORI_WINDOW), 2)


# ---------------------------------------------------------------------------
# power_apriori_ext_4bet -- donor tools/predict_power_best.py::apriori_nbets_power
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4096)
def _apriori_ext_tickets(
    history: tuple[P638HistoryRow, ...],
    n_bets: int = 4,
) -> P638FirstZoneTicketSet:
    """Iterative pair-extension with a used-number overlap cap.

    Distinct from :func:`_apriori_tickets`: instead of ranking all 38 numbers
    by top-pair association and slicing into fixed chunks, this donor grows
    each bet outward from one top pair by repeatedly adding the number that
    most often co-occurs with that pair, then rejects a candidate bet if it
    shares more than 2 numbers with any earlier accepted bet. This can
    legitimately yield fewer than ``n_bets`` tickets for some histories; the
    strategy contract's own ``native_ticket_count`` check turns that into a
    fail-closed :class:`InvalidOutput`, matching every other adapter's
    handling of a native ticket-count mismatch.
    """

    recent = _recent(history, _APRIORI_EXT_WINDOW)
    pair_freq: Counter[tuple[int, int]] = Counter()
    for row in recent:
        for pair in combinations(row.numbers, 2):
            pair_freq[pair] += 1
    top_pairs = [
        pair
        for pair, _ in sorted(pair_freq.items(), key=lambda item: item[1], reverse=True)[
            : n_bets * 3
        ]
    ]

    bets: list[P638FirstZoneTicket] = []
    used_numbers: set[int] = set()
    for pair in top_pairs:
        if len(bets) >= n_bets:
            break
        base = set(pair)
        extensions: Counter[int] = Counter()
        for row in recent:
            row_numbers = set(row.numbers)
            if base.issubset(row_numbers):
                for number in row_numbers - base:
                    extensions[number] += 1
        bet: list[int] = list(pair)
        for number, _ in sorted(extensions.items(), key=lambda item: item[1], reverse=True)[:4]:
            if number not in bet:
                bet.append(number)
            if len(bet) >= _PICK:
                break
        while len(bet) < _PICK:
            for number in range(1, _POOL + 1):
                if number not in bet:
                    bet.append(number)
                    break
        bet_head = bet[:_PICK]
        if len(set(bet_head) & used_numbers) <= 2:
            bets.append(tuple(sorted(bet_head)))
            used_numbers.update(bet_head[:3])
    return tuple(bets)


@lru_cache(maxsize=4096)
def _apriori_ext_4bet_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return _apriori_ext_tickets(history, 4)


# ---------------------------------------------------------------------------
# lag_reversion_2bet -- donor tools/power_lag_reversion.py::lag_reversion_predict
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4096)
def _lag_reversion_scores(
    history: tuple[P638HistoryRow, ...],
    window: int = _LAG_REVERSION_WINDOW,
) -> dict[int, float]:
    recent = _recent(history, window)
    last_seen: dict[int, int] = {}
    intervals: dict[int, list[int]] = {number: [] for number in range(1, _POOL + 1)}
    for index, row in enumerate(recent):
        for number in row.numbers:
            if number in last_seen:
                intervals[number].append(index - last_seen[number])
            last_seen[number] = index
    current_index = len(recent)
    fallback_median = _POOL / _PICK
    scores: dict[int, float] = {}
    for number in range(1, _POOL + 1):
        median_interval = (
            statistics.median(intervals[number]) if intervals[number] else fallback_median
        )
        current_lag = current_index - last_seen.get(number, -1)
        scores[number] = current_lag / (median_interval + 0.1)
    return scores


@lru_cache(maxsize=4096)
def _lag_reversion_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return _ranked_chunks(_lag_reversion_scores(history, _LAG_REVERSION_WINDOW), 2)


# ---------------------------------------------------------------------------
# power_lead_lag_2bet -- donor tools/power_lead_lag_audit.py::lead_lag_predict
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4096)
def _lead_lag_scores(
    history: tuple[P638HistoryRow, ...],
    window: int = _LEAD_LAG_WINDOW,
) -> dict[int, float]:
    recent = _recent(history, window)
    transition: dict[int, Counter[int]] = {number: Counter() for number in range(1, _POOL + 1)}
    for previous, current in pairwise(recent):
        for left in previous.numbers:
            transition[left].update(current.numbers)
    scores = {number: 0.0 for number in range(1, _POOL + 1)}
    last_numbers = history[-1].numbers
    for left in last_numbers:
        row = transition[left]
        for number in range(1, _POOL + 1):
            scores[number] += row.get(number, 0)
    return scores


@lru_cache(maxsize=4096)
def _lead_lag_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return _ranked_chunks(_lead_lag_scores(history, _LEAD_LAG_WINDOW), 2)


# ---------------------------------------------------------------------------
# power_momentum_2bet -- donor tools/power_momentum_audit.py::momentum_predict
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4096)
def _momentum_scores(
    history: tuple[P638HistoryRow, ...],
    short_window: int = _MOMENTUM_SHORT_WINDOW,
) -> dict[int, float]:
    """Recent-frequency burst vs. a fixed expected count.

    The donor also computes a long-window frequency table but never uses it
    in the final score -- dead code in the original, intentionally not
    reproduced here since it cannot affect output. ``avg_expected`` uses the
    ``short_window`` *parameter* value even when actual history is shorter
    (matching the donor exactly, not the truncated recent-window length).
    """

    recent = _recent(history, short_window)
    short_frequency: Counter[int] = Counter()
    for row in recent:
        short_frequency.update(row.numbers)
    avg_expected = (short_window * _PICK) / _POOL
    return {
        number: short_frequency.get(number, 0) / (avg_expected + 0.1)
        for number in range(1, _POOL + 1)
    }


@lru_cache(maxsize=4096)
def _momentum_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return _ranked_chunks(_momentum_scores(history, _MOMENTUM_SHORT_WINDOW), 2)


# ---------------------------------------------------------------------------
# power_fourier_gap_rebound_2bet
# donor tools/power_fourier_gap_rebound.py::fourier_gap_rebound_predict
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4096)
def _fourier_gap_rebound_scores(
    history: tuple[P638HistoryRow, ...],
    window: int = _FOURIER_GAP_REBOUND_WINDOW,
) -> dict[int, float]:
    """Donor-exact period-alignment score plus a not-recently-hit bonus.

    The donor's ``detect_dominant_period`` runs a full complex FFT at the
    causal window's own (unpadded, possibly odd) length and keeps only
    strictly-positive-frequency bins -- exactly the arbitrary-length exact
    port this file's sibling :func:`~.powerlotto_wave1._fourier_scores_exact`
    already established via :func:`bluestein_dft`, generalized here to a
    variable-length window instead of a fixed one. NumPy's even-length
    ``fftfreq`` marks the Nyquist bin negative (excluded by the donor's own
    ``xf > 0`` filter); for odd length there is no Nyquist bin, so the
    positive-frequency band is ``1 .. ceil(size/2) - 1`` inclusive either way.
    """

    recent = _recent(history, window)
    size = len(recent)
    scores = {number: 0.0 for number in range(1, _POOL + 1)}
    for number in range(1, _POOL + 1):
        raw = tuple(1.0 if number in row.numbers else 0.0 for row in recent)
        if sum(raw) < 2:
            continue
        mean = sum(raw) / size
        spectrum = bluestein_dft(tuple(value - mean for value in raw))
        positive_bound = math.ceil(size / 2)
        if positive_bound <= 1:
            continue
        dominant_index = max(
            range(1, positive_bound),
            key=lambda index: (abs(spectrum[index]), -index),
        )
        frequency = dominant_index / size
        if frequency == 0:
            continue
        period = 1.0 / frequency
        if not (2 < period < size / 2):
            continue
        last_hit = max(index for index, value in enumerate(raw) if value)
        gap = (size - 1) - last_hit
        scores[number] = 1.0 / (abs(gap - period) + 1.0)

    recent30 = _recent(history, _GAP_REBOUND_RECENT_WINDOW)
    frequency30: Counter[int] = Counter()
    for row in recent30:
        frequency30.update(row.numbers)
    last_seen_gap: dict[int, int] = {}
    window30 = len(recent30)
    for index, row in enumerate(recent30):
        for number in row.numbers:
            last_seen_gap[number] = window30 - 1 - index
    avg_gap = _POOL / _PICK
    for number in range(1, _POOL + 1):
        if frequency30.get(number, 0) < _GAP_REBOUND_MIN_FREQ or number not in last_seen_gap:
            continue
        gap = last_seen_gap[number]
        if gap > avg_gap * _GAP_REBOUND_THRESHOLD:
            bonus = _GAP_REBOUND_WEIGHT * (gap / avg_gap - _GAP_REBOUND_THRESHOLD + 1)
            scores[number] += bonus
    return scores


@lru_cache(maxsize=4096)
def _fourier_gap_rebound_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return _ranked_chunks(_fourier_gap_rebound_scores(history, _FOURIER_GAP_REBOUND_WINDOW), 2)


# ---------------------------------------------------------------------------
# power_c01 .. power_c07 -- donor analysis/power_lotto/p173, p176
# (read-only research prototypes; donor's own OOS study found a NULL result
# for all seven -- ported as developed methods regardless, per this module's
# docstring)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4096)
def _c01_recency_decay_ticket(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicket:
    lookback = _recent(history, _C01_LOOKBACK)
    scores = {number: 0.0 for number in range(1, _POOL + 1)}
    ln2 = math.log(2)
    for age, row in enumerate(reversed(lookback)):
        weight = math.exp(-ln2 * age / _C01_HALF_LIFE)
        for number in row.numbers:
            scores[number] += weight
    return _ranked_single(scores)


@lru_cache(maxsize=4096)
def _c01_recency_decay_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return (_c01_recency_decay_ticket(history),)


@lru_cache(maxsize=4096)
def _c02_gap_overdue_ticket(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicket:
    last_seen: dict[int, int] = {}
    for index, row in enumerate(history):
        for number in row.numbers:
            last_seen[number] = index
    n_prior = len(history)
    scores = {
        number: (n_prior - 1 - last_seen[number] if number in last_seen else n_prior)
        / _C02_MEAN_GAP
        for number in range(1, _POOL + 1)
    }
    return _ranked_single(scores)


@lru_cache(maxsize=4096)
def _c02_gap_overdue_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return (_c02_gap_overdue_ticket(history),)


@lru_cache(maxsize=4096)
def _c04_zone_targets(calibration: tuple[P638HistoryRow, ...]) -> tuple[int, int, int]:
    """Zone-count mode from the frozen first-500-draw calibration window.

    ``calibration`` must always be ``history[:_C04_TRAINING_SIZE]`` -- the
    dataset's earliest 500 draws -- which is stable across every prediction
    call because the replay harness always passes the full causal prefix
    from draw 1, never a rolling window (verified against
    ``research/powerlotto_wave1.py::run_replay``, which slices
    ``normalized_draws[:target_index]``).
    """

    low_counts: list[int] = []
    mid_counts: list[int] = []
    high_counts: list[int] = []
    for row in calibration:
        numbers = row.numbers
        low_counts.append(sum(1 for number in numbers if number in _C04_ZONE_LOW))
        mid_counts.append(sum(1 for number in numbers if number in _C04_ZONE_MID))
        high_counts.append(sum(1 for number in numbers if number in _C04_ZONE_HIGH))
    target_low = statistics.mode(low_counts)
    target_mid = statistics.mode(mid_counts)
    target_high = statistics.mode(high_counts)
    total = target_low + target_mid + target_high
    if total != _PICK:
        diff = _PICK - total
        target_mid = max(0, target_mid + diff)
        total = target_low + target_mid + target_high
        if total != _PICK:
            target_high = max(0, target_high + (_PICK - total))
    return (target_low, target_mid, target_high)


@lru_cache(maxsize=4096)
def _c04_zone_balanced_ticket(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicket:
    target_low, target_mid, target_high = _c04_zone_targets(history[:_C04_TRAINING_SIZE])
    frequency: Counter[int] = Counter()
    for row in history:
        frequency.update(row.numbers)
    low_ranked = sorted(_C04_ZONE_LOW_ITER, key=lambda number: -frequency.get(number, 0))
    mid_ranked = sorted(_C04_ZONE_MID_ITER, key=lambda number: -frequency.get(number, 0))
    high_ranked = sorted(_C04_ZONE_HIGH_ITER, key=lambda number: -frequency.get(number, 0))
    selected = low_ranked[:target_low] + mid_ranked[:target_mid] + high_ranked[:target_high]
    if len(selected) < _PICK:
        selected_set = set(selected)
        remaining = sorted(
            (number for number in range(1, _POOL + 1) if number not in selected_set),
            key=lambda number: -frequency.get(number, 0),
        )
        selected = selected + remaining[: _PICK - len(selected)]
    return tuple(sorted(selected[:_PICK]))


@lru_cache(maxsize=4096)
def _c04_zone_balanced_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return (_c04_zone_balanced_ticket(history),)


@lru_cache(maxsize=4096)
def _c03_pair_centrality_scores(history: tuple[P638HistoryRow, ...]) -> dict[int, float]:
    pair_counts: Counter[tuple[int, int]] = Counter()
    for row in history:
        for pair in combinations(row.numbers, 2):
            pair_counts[pair] += 1
    degree: dict[int, float] = defaultdict(float)
    for (first, second), count in pair_counts.items():
        if count >= _C03_MIN_PAIR_COOCCURRENCE:
            degree[first] += count
            degree[second] += count
    return degree


@lru_cache(maxsize=4096)
def _c03_pair_centrality_ticket(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicket:
    return _ranked_single(_c03_pair_centrality_scores(history))


@lru_cache(maxsize=4096)
def _c03_pair_centrality_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return (_c03_pair_centrality_ticket(history),)


def _draw_sum(numbers: tuple[int, ...]) -> int:
    return sum(numbers)


def _draw_span(numbers: tuple[int, ...]) -> int:
    return max(numbers) - min(numbers)


@lru_cache(maxsize=4096)
def _c05_dispersion_match_ticket(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicket:
    sums = [_draw_sum(row.numbers) for row in history]
    spans = [_draw_span(row.numbers) for row in history]
    if sums:
        target_sum = sum(sums) / len(sums)
        target_span = sum(spans) / len(spans)
    else:
        target_sum, target_span = 117.0, 25.0
    norm_sum = target_sum if target_sum > 0 else 117.0
    norm_span = target_span if target_span > 0 else 25.0

    selected: list[int] = []
    remaining = list(range(1, _POOL + 1))
    for _ in range(_PICK):
        best_number: int | None = None
        best_score = math.inf
        for number in remaining:
            trial = [*selected, number]
            trial_sum = _draw_sum(tuple(trial))
            trial_span = max(trial) - min(trial) if len(trial) > 1 else 0
            projected_sum = trial_sum + (_PICK - len(trial)) * (norm_sum / _PICK)
            projected_span = max(trial_span, norm_span * len(trial) / _PICK)
            score = (projected_sum - norm_sum) ** 2 / (norm_sum**2 + 1) + (
                projected_span - norm_span
            ) ** 2 / (norm_span**2 + 1)
            if score < best_score:
                best_score, best_number = score, number
        assert best_number is not None
        selected.append(best_number)
        remaining.remove(best_number)
    return tuple(sorted(selected))


@lru_cache(maxsize=4096)
def _c05_dispersion_match_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return (_c05_dispersion_match_ticket(history),)


@lru_cache(maxsize=4096)
def _c06_cusum_regime(history: tuple[P638HistoryRow, ...]) -> str:
    cusum = 0.0
    sums: list[int] = []
    mean, std = 117.0, 14.0
    for row in history:
        value = _draw_sum(row.numbers)
        sums.append(value)
        if len(sums) >= 10:
            mean = sum(sums) / len(sums)
            variance = sum((item - mean) ** 2 for item in sums) / len(sums)
            std = max(1.0, math.sqrt(variance))
        z_score = (value - mean) / std
        cusum = max(0.0, cusum + z_score - _C06_CUSUM_SLACK)
    if cusum > _C06_CUSUM_THRESHOLD:
        return "high"
    if sums and len(sums) >= 5 and sum(sums[-5:]) / 5 < mean - std:
        return "low"
    return "neutral"


@lru_cache(maxsize=4096)
def _c06_regime_ticket(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicket:
    window = _C06_REGIME_WINDOWS[_c06_cusum_regime(history)]
    recent = _recent(history, window)
    frequency: Counter[int] = Counter()
    for row in recent:
        frequency.update(row.numbers)
    scores = {number: float(frequency.get(number, 0)) for number in range(1, _POOL + 1)}
    return _ranked_single(scores)


@lru_cache(maxsize=4096)
def _c06_regime_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return (_c06_regime_ticket(history),)


def _c01_raw_ranking(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    lookback = _recent(history, _C01_LOOKBACK)
    scores = {number: 0.0 for number in range(1, _POOL + 1)}
    ln2 = math.log(2)
    for age, row in enumerate(reversed(lookback)):
        weight = math.exp(-ln2 * age / _C01_HALF_LIFE)
        for number in row.numbers:
            scores[number] += weight
    return tuple(sorted(range(1, _POOL + 1), key=lambda number: (-scores[number], number)))


def _c02_raw_ranking(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    scores = _c02_gap_overdue_scores(history)
    return tuple(sorted(range(1, _POOL + 1), key=lambda number: (-scores[number], number)))


@lru_cache(maxsize=4096)
def _c02_gap_overdue_scores(history: tuple[P638HistoryRow, ...]) -> dict[int, float]:
    last_seen: dict[int, int] = {}
    for index, row in enumerate(history):
        for number in row.numbers:
            last_seen[number] = index
    n_prior = len(history)
    return {
        number: (n_prior - 1 - last_seen[number] if number in last_seen else n_prior)
        / _C02_MEAN_GAP
        for number in range(1, _POOL + 1)
    }


def _c04_raw_ranking(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    target_low, target_mid, target_high = _c04_zone_targets(history[:_C04_TRAINING_SIZE])
    frequency: Counter[int] = Counter()
    for row in history:
        frequency.update(row.numbers)
    low_ranked = sorted(_C04_ZONE_LOW_ITER, key=lambda number: -frequency.get(number, 0))
    mid_ranked = sorted(_C04_ZONE_MID_ITER, key=lambda number: -frequency.get(number, 0))
    high_ranked = sorted(_C04_ZONE_HIGH_ITER, key=lambda number: -frequency.get(number, 0))
    selected = low_ranked[:target_low] + mid_ranked[:target_mid] + high_ranked[:target_high]
    if len(selected) < _PICK:
        selected_set = set(selected)
        remaining = sorted(
            (number for number in range(1, _POOL + 1) if number not in selected_set),
            key=lambda number: -frequency.get(number, 0),
        )
        selected = selected + remaining[: _PICK - len(selected)]
    selected_set = set(selected)
    tail = [number for number in range(1, _POOL + 1) if number not in selected_set]
    return tuple(selected) + tuple(tail)


def _c03_raw_ranking(history: tuple[P638HistoryRow, ...]) -> tuple[int, ...]:
    scores = _c03_pair_centrality_scores(history)
    return tuple(sorted(range(1, _POOL + 1), key=lambda number: (-scores.get(number, 0.0), number)))


@lru_cache(maxsize=4096)
def _c07_borda_ticket(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicket:
    rankings = (
        _c01_raw_ranking(history),
        _c02_raw_ranking(history),
        _c04_raw_ranking(history),
        _c03_raw_ranking(history),
    )
    borda: dict[int, float] = defaultdict(float)
    size = _POOL
    for ranking in rankings:
        for rank, number in enumerate(ranking):
            borda[number] += size - rank
    return _ranked_single(borda)


@lru_cache(maxsize=4096)
def _c07_borda_tickets(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    return (_c07_borda_ticket(history),)


_DONOR_SHA256 = "a867d33c130daa8de00363df5ee52ca926385a8ef2c17f03b161a8b6726adf43"

WAVE2_STRATEGIES: tuple[P638StrategySpec, ...] = (
    P638StrategySpec(
        strategy_id="power_apriori_2bet",
        strategy_version="v0.1-p638-wave2",
        native_ticket_count=2,
        min_history=10,
        source_paths=("tools/power_apriori_audit.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "apriori_predict's top-50-pair association scores, chunked into "
            "two consecutive 6-number blocks."
        ),
        _predictor=_apriori_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_apriori_ext_4bet",
        strategy_version="v0.1-p638-wave2",
        native_ticket_count=4,
        min_history=_APRIORI_EXT_MIN_HISTORY,
        source_paths=("tools/predict_power_best.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "apriori_nbets_power's iterative pair-extension with an overlap "
            "cap, at the donor script's own documented 4-bet default."
        ),
        _predictor=_apriori_ext_4bet_tickets,
    ),
    P638StrategySpec(
        strategy_id="lag_reversion_2bet",
        strategy_version="v0.1-p638-wave2",
        native_ticket_count=2,
        min_history=10,
        source_paths=("tools/power_lag_reversion.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "lag_reversion_predict's median-interval overdue score. Named "
            "after the donor's own P63/P64b governance test IDs, which "
            "recorded this as a real NEW_CANDIDATE their mini-backtest "
            "rejected for lack of edge, not for a code-safety reason."
        ),
        _predictor=_lag_reversion_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_lead_lag_2bet",
        strategy_version="v0.1-p638-wave2",
        native_ticket_count=2,
        min_history=10,
        source_paths=("tools/power_lead_lag_audit.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "lead_lag_predict's adjacent-draw transition matrix."
        ),
        _predictor=_lead_lag_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_momentum_2bet",
        strategy_version="v0.1-p638-wave2",
        native_ticket_count=2,
        min_history=10,
        source_paths=("tools/power_momentum_audit.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "momentum_predict's short-window frequency burst vs. fixed "
            "expected count."
        ),
        _predictor=_momentum_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_fourier_gap_rebound_2bet",
        strategy_version="v0.1-p638-wave2",
        native_ticket_count=2,
        min_history=100,
        source_paths=("tools/power_fourier_gap_rebound.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "fourier_gap_rebound_predict's exact-length FFT period score "
            "plus a not-recently-hit gap-rebound bonus; the donor's own "
            "documented enhancement of the Wave 1 Fourier-rhythm family."
        ),
        _predictor=_fourier_gap_rebound_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_c01_recency_decay_1bet",
        strategy_version="v0.1-p638-p173",
        native_ticket_count=1,
        min_history=10,
        source_paths=("analysis/power_lotto/p173_new_strategy_minimal_prototype_read_only.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P173 C01 exponential-decay weighted recency frequency. Donor's "
            "own OOS study: NULL result (no edge surviving Bonferroni)."
        ),
        _predictor=_c01_recency_decay_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_c02_gap_overdue_1bet",
        strategy_version="v0.1-p638-p173",
        native_ticket_count=1,
        min_history=10,
        source_paths=("analysis/power_lotto/p173_new_strategy_minimal_prototype_read_only.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P173 C02 gap/mean-gap overdue ratio over unbounded prior "
            "history. Donor's own OOS study: NULL result."
        ),
        _predictor=_c02_gap_overdue_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_c04_zone_balanced_1bet",
        strategy_version="v0.1-p638-p173",
        native_ticket_count=1,
        min_history=_C04_TRAINING_SIZE,
        source_paths=("analysis/power_lotto/p173_new_strategy_minimal_prototype_read_only.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P173 C04 zone-count-target-matched frequency, calibrated once "
            "from the dataset's first 500 draws. Donor's own OOS study: "
            "NULL result."
        ),
        _predictor=_c04_zone_balanced_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_c03_pair_centrality_1bet",
        strategy_version="v0.1-p638-p176",
        native_ticket_count=1,
        min_history=10,
        source_paths=("analysis/power_lotto/p176_advanced_feature_minimal_prototype_read_only.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P176 C03 pair-cooccurrence degree centrality over unbounded "
            "prior history. Donor's own OOS study: NULL result."
        ),
        _predictor=_c03_pair_centrality_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_c05_dispersion_match_1bet",
        strategy_version="v0.1-p638-p176",
        native_ticket_count=1,
        min_history=10,
        source_paths=("analysis/power_lotto/p176_advanced_feature_minimal_prototype_read_only.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P176 C05 greedy sum/span dispersion matching against the prior "
            "mean. Donor's own OOS study: NULL result."
        ),
        _predictor=_c05_dispersion_match_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_c06_regime_cusum_1bet",
        strategy_version="v0.1-p638-p176",
        native_ticket_count=1,
        min_history=10,
        source_paths=("analysis/power_lotto/p176_advanced_feature_minimal_prototype_read_only.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P176 C06 one-sided CUSUM regime detector feeding a "
            "regime-dependent frequency window. Donor's own OOS study: "
            "NULL result."
        ),
        _predictor=_c06_regime_tickets,
    ),
    P638StrategySpec(
        strategy_id="power_c07_borda_ensemble_1bet",
        strategy_version="v0.1-p638-p176",
        native_ticket_count=1,
        min_history=_C04_TRAINING_SIZE,
        source_paths=("analysis/power_lotto/p176_advanced_feature_minimal_prototype_read_only.py",),
        provenance=(
            f"POWER_LOTTO first-zone port from donor archive {_DONOR_SHA256}; "
            "P176 C07 equal-weight Borda aggregation of C01+C02+C04+C03 "
            "rankings. Donor's own OOS study: NULL result."
        ),
        _predictor=_c07_borda_tickets,
    ),
)

WAVE2_BLOCKED_STRATEGIES: tuple[P638BlockedStrategy, ...] = (
    P638BlockedStrategy(
        strategy_id="power_graph_synergy",
        reason=(
            "tools/power_graph_synergy.py::graph_clancy_predict calls "
            "community_louvain.best_partition() with no random_state, an "
            "unseeded RNG dependency; excluded per this project's standing "
            "invented/unseeded-RNG exclusion criterion (see "
            "biglotto-wave11-frequency-consensus-blocked precedent)."
        ),
        source_paths=("tools/power_graph_synergy.py",),
    ),
    P638BlockedStrategy(
        strategy_id="power_ultimate_5bet",
        reason=(
            "tools/predict_power_ultimate_5bet.py::generate_ultimate_5bet "
            "does its own inline DatabaseManager(...).get_all_draws(...) "
            "call rather than accepting history as a parameter; would need "
            "a DB-access refactor before it could be a pure function, and "
            "heavily overlaps the already-migrated power_orthogonal_5bet."
        ),
        source_paths=("tools/predict_power_ultimate_5bet.py",),
    ),
)

WAVE2_STRATEGY_BY_ID = {spec.strategy_id: spec for spec in WAVE2_STRATEGIES}

__all__ = [
    "WAVE2_BLOCKED_STRATEGIES",
    "WAVE2_STRATEGIES",
    "WAVE2_STRATEGY_BY_ID",
]
