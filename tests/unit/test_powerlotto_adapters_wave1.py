# pyright: reportPrivateUsage=false

"""Focused contract tests for the pure POWER_LOTTO Wave 1 adapters."""

from __future__ import annotations

import cmath
import itertools
import math
import random
from collections.abc import Mapping

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.powerlotto_wave1 import (
    WAVE1_BLOCKED_STRATEGIES,
    WAVE1_STRATEGIES,
    P638HistoryRow,
    P638StrategySpec,
    _acb_scores,
    _cold_ticket,
    _fft_complex_pow2,
    _fourier_rhythm_fixed_window_scores,
    _fourier_scores_exact,
    _ifft_complex_pow2,
    _markov_ticket,
    _midfreq_scores,
    _power_fourier_rhythm_tickets,
    _power_orthogonal_tickets,
    bluestein_dft,
    coerce_p638_history,
)
from lottolab.strategies.powerlotto_second_zone import second_zone_predict

_EXPECTED_IDS = (
    "zonal_entropy_2bet",
    "cold_complement_2bet",
    "midfreq_fourier_2bet",
    "fourier30_markov30_2bet",
    "midfreq_fourier_mk_3bet",
    "fourier_rhythm_3bet",
    "power_precision_3bet",
    "pp3_freqort_4bet",
    "power_fourier_rhythm_2bet",
    "power_orthogonal_5bet",
)
_EXPECTED_COUNTS = (2, 2, 2, 2, 3, 3, 3, 4, 2, 5)
_EXPECTED_MIN_HISTORY = (30, 10, 10, 30, 30, 10, 30, 30, 100, 30)


def _row(index: int) -> P638HistoryRow:
    numbers = tuple(sorted(((index * 7 + offset * 5) % 38) + 1 for offset in range(6)))
    assert len(set(numbers)) == 6
    return P638HistoryRow(
        draw=f"{index + 1:09d}",
        date=f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
        second_number=(index % 8) + 1,
    )


def _history(count: int) -> tuple[P638HistoryRow, ...]:
    return tuple(_row(index) for index in range(count))


def test_wave1_selection_metadata_is_ordered_and_provenanced() -> None:
    assert tuple(spec.strategy_id for spec in WAVE1_STRATEGIES) == _EXPECTED_IDS
    assert tuple(spec.native_ticket_count for spec in WAVE1_STRATEGIES) == _EXPECTED_COUNTS
    assert tuple(spec.min_history for spec in WAVE1_STRATEGIES) == _EXPECTED_MIN_HISTORY
    assert all(spec.source_paths and spec.provenance for spec in WAVE1_STRATEGIES)
    assert WAVE1_BLOCKED_STRATEGIES == ()


@pytest.mark.parametrize("spec", WAVE1_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave1_outputs_have_native_shape_and_are_repeatable(spec: P638StrategySpec) -> None:
    strategy = spec
    history = _history(500)

    first = strategy.predict_tickets(history, LotteryType.POWER_LOTTO)
    second = strategy.get_bets(history, LotteryType.POWER_LOTTO)

    assert first == second
    assert len(first) == strategy.native_ticket_count
    for ticket in first:
        assert type(ticket) is tuple
        assert len(ticket) == 2
        first_zone, second_zone = ticket
        assert first_zone == tuple(sorted(first_zone))
        assert len(set(first_zone)) == 6
        assert all(type(number) is int and 1 <= number <= 38 for number in first_zone)
        assert type(second_zone) is int and 1 <= second_zone <= 8
    assert {ticket[1] for ticket in first} == {
        second_zone_predict([{"special": row.second_number} for row in history])
    }


@pytest.mark.parametrize("spec", WAVE1_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave1_accepts_documented_mapping_coercion(spec: P638StrategySpec) -> None:
    history = _history(120)
    mapped: list[Mapping[str, object]] = [
        {
            "draw": row.draw,
            "date": row.date,
            "numbers": list(reversed(row.numbers)),
            "special": row.second_number,
            "lottery_type": "POWER_LOTTO",
        }
        for row in history
    ]

    typed = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    coerced = spec.predict_tickets(mapped, LotteryType.POWER_LOTTO)
    assert coerced == typed


@pytest.mark.parametrize("spec", WAVE1_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave1_rejects_non_power_lotto_context(spec: P638StrategySpec) -> None:
    with pytest.raises(UnsupportedLotteryType):
        spec.predict_tickets(_history(500), LotteryType.BIG_LOTTO)


@pytest.mark.parametrize("spec", WAVE1_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave1_enforces_strategy_minimum_history(spec: P638StrategySpec) -> None:
    minimum = spec.min_history
    with pytest.raises(InsufficientHistory):
        spec.predict_tickets(_history(max(0, minimum - 1)), LotteryType.POWER_LOTTO)


def test_coerce_history_is_immutable_and_fail_closed() -> None:
    row = _row(0)
    coerced = coerce_p638_history(
        [
            {
                "draw_number": 1,
                "draw_date": row.date,
                "main_numbers": list(row.numbers),
                "special": row.second_number,
            }
        ]
    )
    assert coerced == (
        P638HistoryRow(
            draw="1",
            date=row.date,
            numbers=row.numbers,
            second_number=row.second_number,
        ),
    )

    with pytest.raises(InvalidOutput):
        coerce_p638_history(
            [
                {
                    "draw": "1",
                    "date": row.date,
                    "numbers": [1, 1, 2, 3, 4, 5],
                    "special": row.second_number,
                }
            ]
        )

    with pytest.raises(UnsupportedLotteryType):
        coerce_p638_history(
            [
                {
                    "draw": "1",
                    "date": row.date,
                    "numbers": list(row.numbers),
                    "special": row.second_number,
                    "lottery_type": "BIG_LOTTO",
                }
            ]
        )


# ─── Exact arbitrary-length FFT machinery (Bluestein) ──────────────────────


def _naive_dft(values: tuple[complex, ...]) -> tuple[complex, ...]:
    """O(n^2) reference DFT: the textbook definition, no algorithmic tricks."""

    n = len(values)
    return tuple(
        sum(values[t] * cmath.exp(-2j * math.pi * k * t / n) for t in range(n))
        for k in range(n)
    )


@pytest.mark.parametrize("length", [1, 2, 3, 5, 7, 8, 13, 16, 100, 128, 499, 500, 501])
def test_bluestein_dft_matches_naive_dft(length: int) -> None:
    rng = random.Random(f"bluestein-{length}")
    signal = tuple(rng.uniform(-1.0, 1.0) for _ in range(length))
    got = bluestein_dft(signal)
    want = _naive_dft(tuple(complex(value) for value in signal))
    assert len(got) == length
    for actual, expected in zip(got, want, strict=True):
        assert abs(actual - expected) < 1e-9


def test_fft_pow2_round_trip() -> None:
    rng = random.Random("fft-pow2-round-trip")
    for length in (1, 2, 4, 8, 16, 32, 64, 128, 1024):
        values = tuple(complex(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(length))
        restored = _ifft_complex_pow2(_fft_complex_pow2(values))
        for original, recovered in zip(values, restored, strict=True):
            assert abs(original - recovered) < 1e-9


# ─── power_fourier_rhythm_2bet golden vectors ──────────────────────────────
#
# Independent oracle for the donor's fixed-window bitstream FFT
# (tools/power_fourier_rhythm.py::detect_dominant_period /
# fourier_rhythm_predict), built from the naive DFT above rather than the
# production Bluestein path, so this proves the *donor formula* -- window
# fixed at 500 with trailing zero-padding, strictly-positive frequency bins
# only, period gated to (2, window/2) -- is transcribed correctly, not just
# that Bluestein reproduces its own production sibling.


def _oracle_fourier_rhythm_scores(
    history: tuple[P638HistoryRow, ...], window: int = 500
) -> dict[int, float]:
    recent = history[-window:] if len(history) > window else history
    scores: dict[int, float] = {}
    for number in range(1, 39):
        bitstream = [0.0] * window
        for index, row in enumerate(recent):
            if number in row.numbers:
                bitstream[index] = 1.0
        if sum(bitstream) < 2:
            scores[number] = 0.0
            continue
        mean = sum(bitstream) / window
        spectrum = _naive_dft(tuple(complex(value - mean) for value in bitstream))
        half = window // 2
        dominant_index = max(range(1, half), key=lambda index: (abs(spectrum[index]), -index))
        period = window / dominant_index
        if not (2 < period < window / 2):
            scores[number] = 0.0
            continue
        last_hit = max(index for index, value in enumerate(bitstream) if value)
        gap = (window - 1) - last_hit
        scores[number] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def _oracle_power_fourier_rhythm_tickets(
    history: tuple[P638HistoryRow, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    scores = _oracle_fourier_rhythm_scores(history)
    ranked = sorted(range(1, 39), key=lambda number: (-scores[number], number))
    return (tuple(sorted(ranked[0:6])), tuple(sorted(ranked[6:12])))


@pytest.mark.parametrize("history_length", [100, 150, 299, 300, 500, 700])
def test_power_fourier_rhythm_matches_donor_formula_oracle(history_length: int) -> None:
    rng = random.Random(f"power-fourier-rhythm-{history_length}")
    history = tuple(
        P638HistoryRow(
            draw=f"{index + 1:09d}",
            date="2020-01-01",
            numbers=tuple(sorted(rng.sample(range(1, 39), 6))),
            second_number=rng.randint(1, 8),
        )
        for index in range(history_length)
    )
    scores = _fourier_rhythm_fixed_window_scores(history)
    oracle_scores = _oracle_fourier_rhythm_scores(history)
    assert scores.keys() == oracle_scores.keys()
    for number, score in scores.items():
        assert score == pytest.approx(oracle_scores[number], abs=1e-9)
    assert _power_fourier_rhythm_tickets(history) == _oracle_power_fourier_rhythm_tickets(history)


def test_power_fourier_rhythm_pads_short_history_with_trailing_zeros() -> None:
    """Fewer than 500 causal draws must not shrink the FFT window."""

    rng = random.Random("power-fourier-rhythm-short-history")
    history = tuple(
        P638HistoryRow(
            draw=f"{index + 1:09d}",
            date="2020-01-01",
            numbers=tuple(sorted(rng.sample(range(1, 39), 6))),
            second_number=rng.randint(1, 8),
        )
        for index in range(100)
    )
    scores = _fourier_rhythm_fixed_window_scores(history)
    assert scores == _oracle_fourier_rhythm_scores(history)
    # Every non-zero score must reflect a period strictly inside (2, 250);
    # a shrunk (unpadded) window would instead gate against (2, 50).
    for number, score in scores.items():
        if score > 0.0:
            assert 2 < 500 / _dominant_index_for(history, number) < 250


def _dominant_index_for(history: tuple[P638HistoryRow, ...], number: int) -> int:
    window = 500
    recent = history[-window:] if len(history) > window else history
    bitstream = [0.0] * window
    for index, row in enumerate(recent):
        if number in row.numbers:
            bitstream[index] = 1.0
    mean = sum(bitstream) / window
    spectrum = _naive_dft(tuple(complex(value - mean) for value in bitstream))
    half = window // 2
    return max(range(1, half), key=lambda index: (abs(spectrum[index]), -index))


def test_power_fourier_rhythm_native_ticket_shape() -> None:
    spec = next(
        spec for spec in WAVE1_STRATEGIES if spec.strategy_id == "power_fourier_rhythm_2bet"
    )
    rng = random.Random("power-fourier-rhythm-shape")
    history = tuple(
        {
            "draw": str(index + 1),
            "date": "2020-01-01",
            "numbers": sorted(rng.sample(range(1, 39), 6)),
            "special": rng.randint(1, 8),
        }
        for index in range(120)
    )
    tickets = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    assert len(tickets) == 2
    first_zone_numbers = [ticket[0] for ticket in tickets]
    assert len(set(first_zone_numbers[0]) | set(first_zone_numbers[1])) == 12
    assert not set(first_zone_numbers[0]) & set(first_zone_numbers[1])


# ─── power_orthogonal_5bet golden vectors ──────────────────────────────────
#
# Independent oracles for the donor's actual-length (unpadded) helper family
# (lottery_api/models/p128_wave2_phase2_adapters.py), reimplemented from the
# donor's literal formulas rather than by calling the production module.


def _oracle_midfreq_scores(
    history: tuple[P638HistoryRow, ...], window: int = 100
) -> dict[int, float]:
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    expected = w * 6 / 38
    freq: dict[int, int] = {}
    for row in recent:
        for number in row.numbers:
            freq[number] = freq.get(number, 0) + 1
    return {number: -abs(freq.get(number, 0) - expected) for number in range(1, 39)}


def _oracle_cold_top6(history: tuple[P638HistoryRow, ...], window: int = 100) -> tuple[int, ...]:
    recent = history[-window:] if len(history) >= window else history
    freq: dict[int, int] = {}
    for row in recent:
        for number in row.numbers:
            freq[number] = freq.get(number, 0) + 1
    ranked = sorted(range(1, 39), key=lambda number: (freq.get(number, 0), number))
    return tuple(sorted(ranked[:6]))


def _oracle_markov30_top6(history: tuple[P638HistoryRow, ...], window: int = 30) -> tuple[int, ...]:
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 2:
        return tuple(range(1, 7))
    transition: dict[int, dict[int, float]] = {number: {} for number in range(1, 39)}
    row_totals: dict[int, float] = {number: 0.0 for number in range(1, 39)}
    for previous, current in itertools.pairwise(recent):
        for a in previous.numbers:
            for b in current.numbers:
                transition[a][b] = transition[a].get(b, 0.0) + 1.0
                row_totals[a] += 1.0
    scores = {number: 0.0 for number in range(1, 39)}
    last_numbers = recent[-1].numbers
    for a in last_numbers:
        total = row_totals[a]
        if total == 0:
            continue
        for number in range(1, 39):
            scores[number] += transition[a].get(number, 0.0) / total
    ranked = sorted(range(1, 39), key=lambda number: (-scores[number], number))
    return tuple(sorted(ranked[:6]))


def _oracle_acb_scores(history: tuple[P638HistoryRow, ...], window: int = 100) -> dict[int, float]:
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    p = 6 / 38
    expected = w * p
    variance = w * p * (1 - p)
    sigma = math.sqrt(variance) if variance > 0 else 1.0
    freq: dict[int, int] = {}
    for row in recent:
        for number in row.numbers:
            freq[number] = freq.get(number, 0) + 1
    return {number: (expected - freq.get(number, 0)) / sigma for number in range(1, 39)}


def _oracle_fourier_scores_exact(
    history: tuple[P638HistoryRow, ...], window: int = 500
) -> dict[int, float]:
    """Independent reimplementation of the donor's ``_pl_fourier_scores``.

    Built from the naive DFT above, not the production Bluestein path: this
    proves the *donor formula* -- unpadded, causal-length ``rfft``, dominant
    bin from the strictly-positive-index one-sided spectrum, smallest-index
    tie-break -- is transcribed correctly, not just that Bluestein reproduces
    its own production sibling.
    """

    recent = history[-window:] if len(history) >= window else history
    size = len(recent)
    if size < 10:
        return {number: 0.0 for number in range(1, 39)}
    scores: dict[int, float] = {}
    for number in range(1, 39):
        raw = [1.0 if number in row.numbers else 0.0 for row in recent]
        if sum(raw) < 2:
            scores[number] = 0.0
            continue
        mean = sum(raw) / size
        spectrum = _naive_dft(tuple(complex(value - mean) for value in raw))
        power = [
            value.real * value.real + value.imag * value.imag for value in spectrum[: size // 2 + 1]
        ]
        if len(power) <= 1:
            scores[number] = 0.0
            continue
        dominant_index = max(range(1, len(power)), key=lambda index: (power[index], -index))
        period = size / dominant_index
        last_hit = max(index for index, value in enumerate(raw) if value)
        gap = (size - 1) - last_hit
        scores[number] = 1.0 / (abs(gap - period) + 1.0)
    return scores


@pytest.mark.parametrize("history_length", [30, 45, 99, 100, 250])
def test_power_orthogonal_matches_donor_formula_oracle(history_length: int) -> None:
    rng = random.Random(f"power-orthogonal-{history_length}")
    history = tuple(
        P638HistoryRow(
            draw=f"{index + 1:09d}",
            date="2020-01-01",
            numbers=tuple(sorted(rng.sample(range(1, 39), 6))),
            second_number=rng.randint(1, 8),
        )
        for index in range(history_length)
    )

    bet1, bet2, bet3, bet4, bet5 = _power_orthogonal_tickets(history)

    oracle_midfreq = _oracle_midfreq_scores(history)
    ranked_midfreq = sorted(range(1, 39), key=lambda number: (-oracle_midfreq[number], number))
    assert bet1 == tuple(sorted(ranked_midfreq[:6]))

    # bet2 (Fourier500) is donor-exact: the unpadded rfft dominant-bin
    # selection, checked against an independent naive-DFT oracle rather than
    # the production Bluestein path this strategy actually calls.
    oracle_fourier = _oracle_fourier_scores_exact(history)
    ranked_fourier = sorted(range(1, 39), key=lambda number: (-oracle_fourier[number], number))
    assert bet2 == tuple(sorted(ranked_fourier[:6]))

    assert bet3 == _oracle_cold_top6(history)
    assert bet4 == _oracle_markov30_top6(history)

    oracle_acb = _oracle_acb_scores(history)
    ranked_acb = sorted(range(1, 39), key=lambda number: (-oracle_acb[number], number))
    assert bet5 == tuple(sorted(ranked_acb[:6]))


def test_power_orthogonal_reuses_existing_helpers_directly() -> None:
    """Every position must be present, including position 2 (RSR-6's concern)."""

    history = _history(60)
    tickets = _power_orthogonal_tickets(history)
    assert len(tickets) == 5
    assert tickets[0] == _ranked_ticket_helper(_midfreq_scores(history))
    assert tickets[1] == _ranked_ticket_helper(_fourier_scores_exact(history, 500))
    assert tickets[2] == _cold_ticket(history, 100)
    assert tickets[3] == _markov_ticket(history, 30)
    assert tickets[4] == _ranked_ticket_helper(_acb_scores(history))


def test_power_orthogonal_tickets_are_deterministic_across_repeated_calls() -> None:
    history = _history(60)
    first = _power_orthogonal_tickets(history)
    second = _power_orthogonal_tickets(tuple(history))
    assert first == second
    assert _fourier_scores_exact(history, 500) == _fourier_scores_exact(tuple(history), 500)


def test_power_orthogonal_fourier_score_is_zero_for_short_history() -> None:
    """Fewer than 10 causal draws must hit the donor's zero-score branch, not raise."""

    rng = random.Random("power-orthogonal-fourier-short")
    history = tuple(
        P638HistoryRow(
            draw=f"{index + 1:09d}",
            date="2020-01-01",
            numbers=tuple(sorted(rng.sample(range(1, 39), 6))),
            second_number=rng.randint(1, 8),
        )
        for index in range(5)
    )
    scores = _fourier_scores_exact(history, 500)
    assert scores == {number: 0.0 for number in range(1, 39)}
    assert scores == _oracle_fourier_scores_exact(history)


def test_power_orthogonal_fourier_tie_break_prefers_ascending_number() -> None:
    """Numbers 1-3 share an identical all-appearances bitstream (tied nonzero
    score); every other number appears at most once (forced to the donor's
    zero-score branch), so the top-6 selection must fill its remaining slots
    by ascending number -- the donor's tie policy, not an accident of order.
    """

    fillers = iter(range(4, 39))
    history = tuple(
        P638HistoryRow(
            draw=f"{index + 1:09d}",
            date="2020-01-01",
            numbers=tuple(sorted((1, 2, 3, next(fillers), next(fillers), next(fillers)))),
            second_number=(index % 8) + 1,
        )
        for index in range(10)
    )
    scores = _fourier_scores_exact(history, 500)
    assert scores == _oracle_fourier_scores_exact(history)
    assert scores[1] == scores[2] == scores[3] > 0.0
    for number in range(4, 39):
        assert scores[number] == 0.0
    assert _ranked_ticket_helper(scores) == (1, 2, 3, 4, 5, 6)


def test_power_orthogonal_module_adds_no_external_dependency() -> None:
    import inspect

    import lottolab.strategies.adapters.powerlotto_wave1 as module

    source = inspect.getsource(module)
    assert "import numpy" not in source
    assert "import scipy" not in source


def _ranked_ticket_helper(scores: dict[int, float]) -> tuple[int, ...]:
    ranked = sorted(range(1, 39), key=lambda number: (-scores[number], number))
    return tuple(sorted(ranked[:6]))
