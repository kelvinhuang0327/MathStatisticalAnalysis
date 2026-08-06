"""Parity and production-path tests for the CES/DMS/Greedy/MWSC adapters."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import builtins
import json
import os
import random
import socket
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

import lottolab.application.use_cases.generate_bet as generate_bet_module
from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_source_native_portfolios_wave26 import (
    CES_METHOD_ID,
    DMS_METHOD_ID,
    GREEDY_METHOD_ID,
    MWSC_METHOD_ID,
    LegacySourceNativeWave26Request,
    LegacySourceNativeWave26SourceError,
    generate_legacy_source_native_wave26_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetStatus,
    GeneratePortfolioReason,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters import biglotto_wave8
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_wave8 import (
    BigLottoCesThreeAdapter,
    BigLottoDmsThreeAdapter,
    BigLottoGreedyThreeAdapter,
    BigLottoMwscThreeAdapter,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]
FROZEN_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
MIGRATION_TASK = "BIGLOTTO_REHABILITATION_CES_DMS_GREEDY_MWSC_R1"

ADAPTER_METHODS: tuple[tuple[type[PortfolioBetAdapter], str], ...] = (
    (BigLottoCesThreeAdapter, CES_METHOD_ID),
    (BigLottoDmsThreeAdapter, DMS_METHOD_ID),
    (BigLottoGreedyThreeAdapter, GREEDY_METHOD_ID),
    (BigLottoMwscThreeAdapter, MWSC_METHOD_ID),
)
SOURCE_PROVENANCE: dict[
    type[PortfolioBetAdapter], tuple[str, str, str]
] = {
    BigLottoCesThreeAdapter: (
        "tools/test_ces.py",
        "test_ces",
        "78d17c530ab8cacf25146c5c39cb4017e3a3ffacde90a4e14ae07a8026b0bc22",
    ),
    BigLottoDmsThreeAdapter: (
        "tools/test_dms.py",
        "test_dms",
        "b63442289bd5862955075bdea70bc682e16b2fe885190d16367b7b2987234dd1",
    ),
    BigLottoGreedyThreeAdapter: (
        "tools/test_greedy_optimizer.py",
        "test_greedy",
        "82df7f878ece8f9daa86b3efc1208dd85440bab8a241308fcf7a2d14c7cd6db6",
    ),
    BigLottoMwscThreeAdapter: (
        "tools/test_mwsc.py",
        "test_mwsc",
        "ba37643d6a3b533d1e61dadf91f040e667d088e95a5163007d568931bcdc6033",
    ),
}


def _history(
    count: int,
    *,
    seed: int = 20260803,
    unpadded_offset: int | None = None,
) -> tuple[CausalDrawRow, ...]:
    rng = random.Random(seed + count)
    rows: list[CausalDrawRow] = []
    for index in range(1, count + 1):
        draw_number = (
            str(index + unpadded_offset)
            if unpadded_offset is not None
            else f"{index:09d}"
        )
        rows.append(
            CausalDrawRow(
                draw=draw_number,
                date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
                numbers=tuple(sorted(rng.sample(range(1, 50), 6))),
            )
        )
    return tuple(rows)


def _legacy_history(
    history: tuple[CausalDrawRow, ...],
) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(draw_number=row.draw, numbers=cast(Ticket, row.numbers))
        for row in history
    )


def _wave26_authority(
    method_id: str,
    target_draw_number: str,
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    return generate_legacy_source_native_wave26_portfolio(
        LegacySourceNativeWave26Request(
            legacy_method_id=method_id,
            target_draw_number=target_draw_number,
            history=_legacy_history(history),
        )
    ).tickets


def _frozen_reference(
    method_id: str,
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    return _wave26_authority(
        method_id,
        "reference-target-after-causal-cutoff",
        history,
    )


def _adapter(
    adapter_class: type[PortfolioBetAdapter],
) -> PortfolioBetAdapter:
    adapter_factory = cast(Callable[..., PortfolioBetAdapter], adapter_class)
    return adapter_factory(wave26_authority=_wave26_authority)


def _exact_seeded_history(
    count: int,
    *,
    seed: int,
    draw_offset: int,
) -> tuple[CausalDrawRow, ...]:
    rng = random.Random(seed)
    return tuple(
        CausalDrawRow(
            draw=str(index + draw_offset),
            date="2020-01-01",
            numbers=tuple(sorted(rng.sample(range(1, 50), 6))),
        )
        for index in range(count)
    )


@pytest.mark.parametrize(
    ("adapter_class", "method_id", "count", "seed", "draw_offset", "expected"),
    (
        (
            BigLottoCesThreeAdapter,
            CES_METHOD_ID,
            47,
            20261261,
            97,
            (
                (3, 21, 23, 28, 31, 48),
                (21, 25, 26, 27, 41, 48),
                (5, 26, 31, 33, 43, 48),
            ),
        ),
        (
            BigLottoDmsThreeAdapter,
            DMS_METHOD_ID,
            20,
            1,
            1,
            (
                (15, 26, 33, 36, 43, 48),
                (4, 10, 11, 12, 13, 16),
                (2, 15, 26, 32, 33, 36),
            ),
        ),
    ),
    ids=("ces-hot-cold-tie", "dms-insertion-order-tie"),
)
def test_wave8_pr84_corrective_regressions_match_wave26_bytes(
    adapter_class: type[PortfolioBetAdapter],
    method_id: str,
    count: int,
    seed: int,
    draw_offset: int,
    expected: tuple[tuple[int, ...], ...],
) -> None:
    history = _exact_seeded_history(
        count,
        seed=seed,
        draw_offset=draw_offset,
    )
    expected_bytes = json.dumps(expected, separators=(",", ":")).encode()

    actual = _adapter(adapter_class).get_bets(history, LotteryType.BIG_LOTTO)

    assert actual == expected
    assert _frozen_reference(method_id, history) == expected
    assert json.dumps(actual, separators=(",", ":")).encode() == expected_bytes


@pytest.mark.parametrize(
    ("adapter_class", "method_id", "count"),
    (
        (BigLottoCesThreeAdapter, CES_METHOD_ID, 1),
        (BigLottoCesThreeAdapter, CES_METHOD_ID, 20),
        (BigLottoCesThreeAdapter, CES_METHOD_ID, 100),
        (BigLottoCesThreeAdapter, CES_METHOD_ID, 500),
        (BigLottoDmsThreeAdapter, DMS_METHOD_ID, 20),
        (BigLottoDmsThreeAdapter, DMS_METHOD_ID, 21),
        (BigLottoDmsThreeAdapter, DMS_METHOD_ID, 100),
        (BigLottoDmsThreeAdapter, DMS_METHOD_ID, 500),
        (BigLottoGreedyThreeAdapter, GREEDY_METHOD_ID, 1),
        (BigLottoGreedyThreeAdapter, GREEDY_METHOD_ID, 20),
        (BigLottoGreedyThreeAdapter, GREEDY_METHOD_ID, 100),
        (BigLottoGreedyThreeAdapter, GREEDY_METHOD_ID, 500),
        (BigLottoMwscThreeAdapter, MWSC_METHOD_ID, 1),
        (BigLottoMwscThreeAdapter, MWSC_METHOD_ID, 20),
        (BigLottoMwscThreeAdapter, MWSC_METHOD_ID, 100),
        (BigLottoMwscThreeAdapter, MWSC_METHOD_ID, 500),
    ),
)
def test_wave8_matches_frozen_reference_across_history_boundaries(
    adapter_class: type[PortfolioBetAdapter],
    method_id: str,
    count: int,
) -> None:
    history = _history(count, seed=91000 + count)
    expected = _frozen_reference(method_id, history)
    actual = _adapter(adapter_class).get_bets(history, LotteryType.BIG_LOTTO)
    assert actual == expected
    assert len(actual) == 3
    assert len(actual) - len(set(actual)) == len(expected) - len(set(expected))


def test_wave8_preserves_randomized_non_zero_padded_draw_identity_semantics() -> None:
    history = _history(146, seed=99173, unpadded_offset=97)
    assert history[0].draw > history[-1].draw
    for adapter_class, method_id in ADAPTER_METHODS:
        assert _adapter(adapter_class).get_bets(
            history, LotteryType.BIG_LOTTO
        ) == _frozen_reference(method_id, history)


def test_wave8_minimum_history_and_boundary_closures() -> None:
    for adapter_class in (
        BigLottoCesThreeAdapter,
        BigLottoGreedyThreeAdapter,
        BigLottoMwscThreeAdapter,
    ):
        with pytest.raises(InsufficientHistory):
            _adapter(adapter_class).get_bets((), LotteryType.BIG_LOTTO)
        assert len(
            _adapter(adapter_class).get_bets(_history(1), LotteryType.BIG_LOTTO)
        ) == 3
    with pytest.raises(InsufficientHistory):
        _adapter(BigLottoDmsThreeAdapter).get_bets(
            _history(19), LotteryType.BIG_LOTTO
        )
    assert len(
        _adapter(BigLottoDmsThreeAdapter).get_bets(
            _history(20), LotteryType.BIG_LOTTO
        )
    ) == 3


def test_wave8_preserves_positional_order_and_duplicate_tickets() -> None:
    expected = (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
    )

    def frozen_stub(
        _method_id: str,
        _target_draw_number: str,
        _history: tuple[CausalDrawRow, ...],
    ) -> tuple[tuple[int, ...], ...]:
        return expected

    assert BigLottoCesThreeAdapter(wave26_authority=frozen_stub).get_bets(
        _history(1), LotteryType.BIG_LOTTO
    ) == expected


def test_wave8_preserves_native_closure_on_direct_and_production_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def closed_stub(
        _method_id: str,
        _target_draw_number: str,
        _history: tuple[CausalDrawRow, ...],
    ) -> tuple[tuple[int, ...], ...]:
        raise LegacySourceNativeWave26SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )

    monkeypatch.setattr(generate_bet_module, "_generate_wave26_portfolio", closed_stub)
    history = _history(30)
    with pytest.raises(
        LegacySourceNativeWave26SourceError,
        match="FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED",
    ):
        BigLottoCesThreeAdapter(wave26_authority=closed_stub).get_bets(
            history, LotteryType.BIG_LOTTO
        )
    result = build_production_generate_portfolio().execute(
        GenerateOneBetInput(
            strategy_id=BigLottoCesThreeAdapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    )
    assert result.status is GeneratePortfolioStatus.REPLAY_ERROR
    assert result.reason_code is GeneratePortfolioReason.REPLAY_ERROR
    assert result.numbers is None


@pytest.mark.parametrize(
    "adapter_class",
    tuple(adapter_class for adapter_class, _method_id in ADAPTER_METHODS),
)
def test_wave8_rejects_non_biglotto_requests(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    with pytest.raises(UnsupportedLotteryType):
        _adapter(adapter_class).get_bets(_history(50), LotteryType.POWER_LOTTO)


def test_wave8_uses_no_filesystem_database_clock_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)
    history = _history(60)
    for adapter_class, method_id in ADAPTER_METHODS:
        assert _adapter(adapter_class).get_bets(
            history, LotteryType.BIG_LOTTO
        ) == _frozen_reference(method_id, history)


def test_wave8_repeat_bytes_are_stable_within_and_across_hash_seeds() -> None:
    code = """
import json, random, sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput, build_production_generate_portfolio,
)
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave8 import (
    BigLottoCesThreeAdapter, BigLottoDmsThreeAdapter,
    BigLottoGreedyThreeAdapter, BigLottoMwscThreeAdapter,
)
rng = random.Random(20260803)
history = tuple(
    CausalDrawRow(
        draw=str(index + 97), date="2020-01-01",
        numbers=tuple(sorted(rng.sample(range(1, 50), 6))),
    )
    for index in range(60)
)
portfolio = build_production_generate_portfolio()
payload = [
    portfolio.execute(
        GenerateOneBetInput(
            strategy_id=cls.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    ).numbers
    for cls in (
        BigLottoCesThreeAdapter, BigLottoDmsThreeAdapter,
        BigLottoGreedyThreeAdapter, BigLottoMwscThreeAdapter,
    )
]
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
"""
    outputs: list[bytes] = []
    for hash_seed in ("1", "9173"):
        completed = subprocess.run(
            [sys.executable, "-B", "-c", code.format(src=str(REPO_ROOT / "src"))],
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            check=True,
            capture_output=True,
        )
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1]

    history = _history(60, seed=20260803, unpadded_offset=97)
    first = json.dumps(
        [
            _adapter(adapter_class).get_bets(history, LotteryType.BIG_LOTTO)
            for adapter_class, _method_id in ADAPTER_METHODS
        ],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    second = json.dumps(
        [
            _adapter(adapter_class).get_bets(history, LotteryType.BIG_LOTTO)
            for adapter_class, _method_id in ADAPTER_METHODS
        ],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert first == second


def test_wave8_target_identity_is_deterministic_and_collision_free() -> None:
    history = (
        CausalDrawRow("cutoff:lottolab-next-target", "2020-01-01", (1, 2, 3, 4, 5, 6)),
        CausalDrawRow(
            "cutoff:lottolab-next-target:next",
            "2020-01-02",
            (7, 8, 9, 10, 11, 12),
        ),
        CausalDrawRow("cutoff", "2020-01-03", (13, 14, 15, 16, 17, 18)),
    )
    target = biglotto_wave8._target_after_causal_cutoff(history)
    assert target == "cutoff:lottolab-next-target:next:next"
    assert target not in {row.draw for row in history}


def test_wave8_catalog_descriptors_are_canonical_and_exact() -> None:
    catalog = production_catalog()
    ids = [descriptor.strategy_id for descriptor in catalog]
    assert len(catalog) == 59
    for adapter_class, _method_id in ADAPTER_METHODS:
        source_path, source_symbol, source_sha256 = SOURCE_PROVENANCE[adapter_class]
        descriptor = catalog.get(adapter_class.strategy_id)
        assert ids.count(adapter_class.strategy_id) == 1
        assert descriptor.strategy_name == adapter_class.strategy_name
        assert descriptor.version == adapter_class.strategy_version
        assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
        assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
        assert descriptor.executable is True
        assert descriptor.min_history == adapter_class.min_history
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == 3
        assert descriptor.adapter_path == (
            "lottolab.strategies.adapters.biglotto_wave8:"
            f"{adapter_class.__name__}"
        )
        assert f"legacy_commit:{FROZEN_COMMIT}" in descriptor.provenance
        assert f"legacy_source:{source_path}" in descriptor.provenance
        assert f"legacy_symbol:{source_symbol}" in descriptor.provenance
        assert f"legacy_source_sha256:{source_sha256}" in descriptor.provenance
        assert f"migration_task:{MIGRATION_TASK}" in descriptor.provenance


def test_wave8_production_paths_preserve_portfolios_and_close_invalid_ids() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    history = _history(60)
    for adapter_class, method_id in ADAPTER_METHODS:
        one_result = one_bet.execute(
            GenerateOneBetInput(
                strategy_id=adapter_class.strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=history,
            )
        )
        assert one_result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
        assert one_result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
        portfolio_result = portfolio.execute(
            GenerateOneBetInput(
                strategy_id=adapter_class.strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=history,
            )
        )
        assert portfolio_result.status is GeneratePortfolioStatus.OK
        assert portfolio_result.reason_code is None
        assert portfolio_result.numbers == _frozen_reference(method_id, history)

    missing = portfolio.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__missing",
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    )
    assert missing.status is GeneratePortfolioStatus.STRATEGY_UNAVAILABLE
    assert missing.reason_code is GeneratePortfolioReason.UNKNOWN_STRATEGY

    dms_boundary = portfolio.execute(
        GenerateOneBetInput(
            strategy_id=BigLottoDmsThreeAdapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(19),
        )
    )
    assert dms_boundary.status is GeneratePortfolioStatus.INSUFFICIENT_HISTORY
    assert dms_boundary.reason_code is GeneratePortfolioReason.INSUFFICIENT_HISTORY
