from datetime import date, timedelta
from random import Random

import pytest

from lottolab.application.biglotto_versioned_replay_bindings import (
    versioned_biglotto_replay_bindings,
)
from lottolab.application.historical_replay_adapters import (
    BigLottoReplayAdapter,
    ReplayStrategyBinding,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw
from lottolab.strategies.adapters.base import InsufficientHistory
from lottolab.strategies.adapters.biglotto_batch17 import BigLottoPredictBiglottoTripleStrikeAdapter
from lottolab.strategies.adapters.biglotto_triple_strike_original import (
    BigLottoTripleStrikeOriginalReplayAdapter,
)
from lottolab.strategies.catalog import UnknownStrategyError, production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

SOURCE_ID = "legacy_biglotto__backtest_biglotto_triple_strike_original__4a8297a758b9"
SOURCE_VERSION = "legacy-source-49a25effa62f-4a8297a758b9"


@pytest.fixture
def binding() -> ReplayStrategyBinding:
    return next(
        b
        for b in versioned_biglotto_replay_bindings()
        if (b.strategy.strategy_id, b.strategy.strategy_version) == (SOURCE_ID, SOURCE_VERSION)
    )


def _draws(count: int, tied: bool = False) -> tuple[ReplayDraw, ...]:
    rng = Random(167)
    draws = []
    for index in range(count):
        numbers = (1, 2, 3, 4, 5, 6) if tied else tuple(sorted(rng.sample(range(1, 50), 6)))
        draws.append(
            ReplayDraw(
                LotteryType.BIG_LOTTO,
                str(index + 1),
                date(2020, 1, 1) + timedelta(days=index),
                numbers,
                next(n for n in range(1, 50) if n not in numbers),
            )
        )
    return tuple(draws)


def test_exact_version_is_replay_only(binding: ReplayStrategyBinding) -> None:
    assert type(binding.implementation) is BigLottoTripleStrikeOriginalReplayAdapter
    assert binding.strategy.min_history == 500
    assert binding.strategy.native_ticket_count == 3
    registry = ExecutableRegistry(production_catalog())
    with pytest.raises(UnknownStrategyError):
        registry.load_adapter(SOURCE_ID, SOURCE_VERSION)
    live_id = "legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504"
    assert production_catalog().get(live_id).version == "v0.1"
    assert registry.load_adapter(live_id) is BigLottoPredictBiglottoTripleStrikeAdapter
    assert BigLottoPredictBiglottoTripleStrikeAdapter.min_history == 150


def test_499_prior_draws_are_ineligible(binding: ReplayStrategyBinding) -> None:
    draws = _draws(500)
    with pytest.raises(InsufficientHistory):
        BigLottoReplayAdapter((binding,)).generate(binding.strategy, draws[:-1], draws[-1])


# Ordered portfolios from the three pure source functions under CPython 3.9.6,
# NumPy 1.26.2 and SciPy 1.12.0. The constant history ties all 49 Fourier scores.
@pytest.mark.parametrize(
    ("prefix", "tied", "expected"),
    [
        (500, False, ((3, 19, 23, 28, 34, 44), (2, 12, 29, 35, 38, 40), (10, 13, 16, 24, 31, 45))),
        (501, False, ((13, 15, 28, 33, 34, 37), (2, 12, 29, 35, 38, 40), (10, 16, 19, 24, 31, 45))),
        (500, True, ((19, 20, 21, 22, 24, 49), (7, 8, 9, 10, 11, 12), (1, 2, 3, 4, 5, 6))),
    ],
)
def test_replay_matches_pinned_source(
    binding: ReplayStrategyBinding, prefix: int, tied: bool, expected: tuple[tuple[int, ...], ...]
) -> None:
    draws = _draws(prefix + 1, tied)
    replay = BigLottoReplayAdapter((binding,))
    tickets = replay.generate(binding.strategy, draws[:-1], draws[-1])
    assert tuple(ticket.ticket_position for ticket in tickets) == (1, 2, 3)
    assert tuple(ticket.main_numbers for ticket in tickets) == expected
