"""Focused contract, oracle, and BIG_LOTTO-donor-parity tests for Wave 3 (cross-lottery ports)."""

from __future__ import annotations

import builtins
import inspect
import os
import pathlib
import socket
import sqlite3
import time
import urllib.request

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import powerlotto_wave3 as module
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave1 import (
    BigLottoDynamicFrequencyAdapter,
    BigLottoMustHitTop6Adapter,
)
from lottolab.strategies.adapters.powerlotto_wave1 import P638HistoryRow, P638StrategySpec
from lottolab.strategies.adapters.powerlotto_wave3 import (
    WAVE3_BLOCKED_STRATEGIES,
    WAVE3_STRATEGIES,
    WAVE3_STRATEGY_BY_ID,
)
from lottolab.strategies.powerlotto_second_zone import second_zone_predict

_EXPECTED_IDS = (
    "power_biglotto_deviation_2bet",
    "power_biglotto_p0_echo_2bet",
    "power_biglotto_graph_predictor_1bet",
    "power_biglotto_must_hit_top6_1bet",
    "power_biglotto_dynamic_frequency_1bet",
    "power_biglotto_hot_cooccurrence_1bet",
    "power_biglotto_attention_replay_1bet",
    "power_biglotto_zone_balance_5bet",
    "power_biglotto_gemini_phase2_7bet",
)
_EXPECTED_COUNTS = (2, 2, 1, 1, 1, 1, 1, 5, 7)
_EXPECTED_MIN_HISTORY = (100, 1, 1, 50, 200, 1, 1, 1, 100)


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


# ─── Module-level safety scans ──────────────────────────────────────────────


def test_module_source_has_no_forbidden_dependency_tokens() -> None:
    source = inspect.getsource(module)
    forbidden = (
        "import numpy",
        "from numpy",
        "import scipy",
        "from scipy",
        "import sqlite3",
        "from sqlite3",
        "import random",
        "from random",
        "import requests",
        "import httpx",
        "import urllib",
        "os.environ",
        "time.time(",
        "time.monotonic(",
        "datetime.now(",
        "open(",
    )
    for token in forbidden:
        assert token not in source, f"forbidden reference found: {token!r}"


def test_module_never_imports_a_biglotto_source_file() -> None:
    """This wave ports BIG_LOTTO algorithms; it must never import BIG_LOTTO code.

    Checks actual import statements only -- the module docstring legitimately
    references BIG_LOTTO strategy_ids and source files in prose for provenance.
    """

    import_lines = [
        line.strip()
        for line in inspect.getsource(module).splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    assert not any("biglotto" in line.casefold() for line in import_lines), import_lines


@pytest.mark.parametrize("spec", WAVE3_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_prediction_uses_no_database_network_filesystem_or_clock(
    spec: P638StrategySpec, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden during prediction")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    tickets = spec.predict_tickets(_history(max(spec.min_history, 600)), LotteryType.POWER_LOTTO)
    assert len(tickets) == spec.native_ticket_count


# ─── Generic contract tests over WAVE3_STRATEGIES ──────────────────────────


def test_wave3_selection_metadata_is_ordered_and_provenanced() -> None:
    assert tuple(spec.strategy_id for spec in WAVE3_STRATEGIES) == _EXPECTED_IDS
    assert tuple(spec.native_ticket_count for spec in WAVE3_STRATEGIES) == _EXPECTED_COUNTS
    assert tuple(spec.min_history for spec in WAVE3_STRATEGIES) == _EXPECTED_MIN_HISTORY
    assert all(spec.source_paths and spec.provenance for spec in WAVE3_STRATEGIES)
    assert len(WAVE3_BLOCKED_STRATEGIES) == 17
    assert all(entry.reason and entry.source_paths for entry in WAVE3_BLOCKED_STRATEGIES)
    assert not any("DEFERRED" in entry.reason for entry in WAVE3_BLOCKED_STRATEGIES)


def test_wave3_strategy_ids_do_not_collide_with_wave1_or_wave2() -> None:
    from lottolab.strategies.adapters.powerlotto_wave1 import WAVE1_STRATEGIES
    from lottolab.strategies.adapters.powerlotto_wave2 import WAVE2_STRATEGIES

    existing_ids = {spec.strategy_id for spec in WAVE1_STRATEGIES + WAVE2_STRATEGIES}
    new_ids = {spec.strategy_id for spec in WAVE3_STRATEGIES}
    assert existing_ids.isdisjoint(new_ids)
    assert len(new_ids) == len(WAVE3_STRATEGIES)


@pytest.mark.parametrize("spec", WAVE3_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave3_outputs_have_native_shape_and_are_repeatable(spec: P638StrategySpec) -> None:
    history = _history(max(spec.min_history, 600))

    first = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    second = spec.get_bets(history, LotteryType.POWER_LOTTO)
    assert first == second
    assert len(first) == spec.native_ticket_count

    expected_second_zone = second_zone_predict([{"special": row.second_number} for row in history])
    for first_zone, second_zone in first:
        assert len(first_zone) == 6
        assert len(set(first_zone)) == 6
        assert all(type(number) is int and 1 <= number <= 38 for number in first_zone)
        assert second_zone == expected_second_zone

    # Repeat call is byte-for-byte identical (pure function of causal history).
    third = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    assert first == third


@pytest.mark.parametrize("spec", WAVE3_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_wave3_insufficient_history_is_rejected(spec: P638StrategySpec) -> None:
    if spec.min_history == 0:
        pytest.skip("no positive min_history floor to violate")
    from lottolab.strategies.adapters.base import InsufficientHistory

    short_history = _history(spec.min_history - 1)
    with pytest.raises(InsufficientHistory):
        spec.predict_tickets(short_history, LotteryType.POWER_LOTTO)


# ─── Direct BIG_LOTTO-donor parity for the two pool-agnostic-as-written ports ──


def _biglotto_row(index: int, numbers: tuple[int, ...]) -> CausalDrawRow:
    return CausalDrawRow(
        draw=f"{index + 1:09d}",
        date=f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def test_must_hit_top6_matches_biglotto_donor_bit_for_bit_over_a_38_pool() -> None:
    """must_hit_top6's frequency-count logic never reads a pool bound, so a
    history confined to 1..38 must select the identical six numbers whether
    run through the original BIG_LOTTO donor helper or this P638 port.

    The donor's raw ``_predict`` returns ``Counter.most_common()`` insertion
    order (canonicalized to sorted order only later, by
    ``BetAdapter.get_one_bet_with_emission``); the P638 port's ``_ticket``
    helper sorts immediately. Both pipelines produce the same final legal
    ticket, so the parity check is on the selected set, plus an explicit
    check that the port's output is exactly the donor's set in sorted order.
    """

    history_p638 = _history(60)
    history_biglotto = tuple(
        _biglotto_row(index, row.numbers) for index, row in enumerate(history_p638)
    )

    donor_result = BigLottoMustHitTop6Adapter().get_one_bet(
        history_biglotto, LotteryType.BIG_LOTTO
    )[0]
    port_result = WAVE3_STRATEGY_BY_ID["power_biglotto_must_hit_top6_1bet"].predict_tickets(
        history_p638, LotteryType.POWER_LOTTO
    )[0][0]
    assert port_result == donor_result


def test_dynamic_frequency_matches_biglotto_donor_bit_for_bit_over_a_38_pool() -> None:
    """Same donor-parity argument as must_hit_top6: the window-scoring math
    never references a pool bound, so the selected set must match exactly."""

    history_p638 = _history(250)
    history_biglotto = tuple(
        _biglotto_row(index, row.numbers) for index, row in enumerate(history_p638)
    )

    donor_result = BigLottoDynamicFrequencyAdapter().get_one_bet(
        history_biglotto, LotteryType.BIG_LOTTO
    )[0]
    port_result = WAVE3_STRATEGY_BY_ID["power_biglotto_dynamic_frequency_1bet"].predict_tickets(
        history_p638, LotteryType.POWER_LOTTO
    )[0][0]
    assert port_result == donor_result
