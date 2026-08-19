"""Parity and contract tests for the BigLotto native-strategy batch 16
adapter (``backtest_biglotto_markov_4bet``'s ``generate_ts3_markov4``).

Golden fixtures below were produced by executing the REAL, byte-identical
donor source file (``tools/backtest_biglotto_markov_4bet.py``, extracted
from the pinned commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` via
``git show`` and confirmed by SHA-256 against the frozen legacy catalog's
own ``source_sha256``) under a real numpy/scipy interpreter, with only the
donor's own database import stubbed out (never touched by
``generate_ts3_markov4``). 16 history lengths x 1 strategy, 0 mismatches --
see this adapter module's own docstring for the pure-Python DFT technique
used to reproduce the donor's ``scipy.fft``-based bet 1 without numpy.
"""

# pyright: reportPrivateUsage=false
# (reachability check reads the registry's internal adapter map directly,
# the same established pattern test_biglotto_batch15_adapters.py already
# uses for the identical purpose)

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GeneratePortfolioStatus,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_batch16 import BigLottoTs3Markov4betAdapter
from lottolab.strategies.catalog import production_catalog

STRATEGY_ID = "legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b"


def _batch16_row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 17 is coprime with 49 (distinct
    from batch 15's stride 11 and wave 14's stride 8), so six consecutive
    steps always land on six distinct residues -- no collisions."""

    numbers = tuple(sorted(((index + step * 17) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"b16-{index:05d}",
        date=f"2019-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _batch16_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_batch16_row(i) for i in range(n))


# ─── golden fixtures: real donor output under numpy/scipy, 150..1200 ───────

TS3_MARKOV4_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    150: (
        (6, 7, 8, 23, 24, 25),
        (14, 15, 16, 17, 18, 26),
        (2, 3, 4, 5, 20, 21),
        (10, 19, 36, 38, 40, 42),
    ),
    151: (
        (1, 2, 18, 19, 35, 36),
        (13, 14, 15, 16, 17, 24),
        (3, 4, 5, 20, 21, 22),
        (7, 9, 26, 37, 39, 41),
    ),
    155: (
        (5, 6, 22, 23, 39, 40),
        (13, 14, 15, 16, 17, 18),
        (10, 24, 25, 41, 42, 43),
        (9, 11, 26, 28, 30, 45),
    ),
    160: (
        (10, 11, 27, 28, 44, 45),
        (7, 8, 9, 16, 17, 18),
        (12, 13, 14, 15, 30, 31),
        (1, 29, 33, 35, 46, 48),
    ),
    175: (
        (10, 11, 25, 26, 42, 43),
        (7, 8, 9, 16, 17, 18),
        (12, 13, 14, 15, 30, 46),
        (1, 29, 31, 33, 44, 48),
    ),
    200: (
        (1, 2, 18, 19, 35, 36),
        (13, 14, 15, 16, 17, 24),
        (3, 4, 5, 20, 21, 22),
        (7, 9, 26, 37, 39, 41),
    ),
    250: (
        (2, 3, 19, 20, 36, 37),
        (13, 14, 15, 16, 17, 18),
        (4, 5, 21, 22, 23, 40),
        (6, 8, 10, 25, 38, 42),
    ),
    300: (
        (3, 4, 20, 21, 37, 38),
        (13, 14, 15, 16, 17, 18),
        (5, 22, 23, 24, 40, 41),
        (7, 9, 11, 26, 39, 43),
    ),
    400: (
        (5, 6, 22, 23, 39, 40),
        (13, 14, 15, 16, 17, 18),
        (10, 24, 25, 41, 42, 43),
        (9, 11, 26, 28, 30, 45),
    ),
    499: (
        (6, 7, 23, 24, 40, 41),
        (13, 14, 15, 16, 17, 18),
        (10, 11, 25, 42, 43, 44),
        (8, 12, 27, 29, 31, 46),
    ),
    500: (
        (7, 8, 24, 25, 41, 42),
        (13, 14, 15, 16, 17, 18),
        (10, 11, 12, 43, 44, 45),
        (9, 26, 28, 30, 32, 47),
    ),
    501: (
        (8, 9, 25, 26, 42, 43),
        (7, 14, 15, 16, 17, 18),
        (10, 11, 12, 13, 44, 45),
        (27, 29, 31, 33, 46, 48),
    ),
    600: (
        (9, 10, 26, 27, 43, 44),
        (7, 8, 15, 16, 17, 18),
        (11, 12, 13, 14, 30, 45),
        (2, 28, 32, 34, 47, 49),
    ),
    750: (
        (12, 13, 29, 30, 46, 47),
        (9, 10, 11, 18, 19, 20),
        (1, 2, 14, 15, 16, 33),
        (3, 5, 31, 35, 37, 48),
    ),
    900: (
        (1, 15, 16, 32, 33, 49),
        (12, 13, 14, 21, 22, 23),
        (2, 3, 4, 5, 20, 36),
        (6, 8, 19, 34, 38, 40),
    ),
    1200: (
        (6, 7, 21, 22, 38, 39),
        (13, 14, 15, 16, 17, 18),
        (10, 11, 23, 24, 25, 42),
        (8, 12, 27, 29, 40, 44),
    ),
}


@pytest.mark.parametrize("length", sorted(TS3_MARKOV4_GOLDENS))
def test_ts3_markov4bet_golden(length: int) -> None:
    history = _batch16_history(length)
    tickets = BigLottoTs3Markov4betAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert tickets == TS3_MARKOV4_GOLDENS[length]


def test_ts3_markov4bet_bets_are_pairwise_disjoint_at_every_golden_length() -> None:
    """The donor's own exclude-chaining (bet2 excludes bet1, bet3 excludes
    bet1+bet2, bet4/Markov excludes all three) must hold at every golden
    length -- a legal 4-ticket portfolio should never repeat a number
    across its own tickets."""

    for length in TS3_MARKOV4_GOLDENS:
        history = _batch16_history(length)
        tickets = BigLottoTs3Markov4betAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        seen: set[int] = set()
        for ticket in tickets:
            assert seen.isdisjoint(ticket), f"length={length} tickets overlap: {tickets}"
            seen.update(ticket)


# ─── boundary / contract tests ──────────────────────────────────────────────


def test_rejects_insufficient_history() -> None:
    history = _batch16_history(149)
    with pytest.raises(InsufficientHistory):
        BigLottoTs3Markov4betAdapter().get_bets(history, LotteryType.BIG_LOTTO)


def test_accepts_exactly_min_history() -> None:
    history = _batch16_history(150)
    tickets = BigLottoTs3Markov4betAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(tickets) == 4


def test_rejects_wrong_lottery_type() -> None:
    history = _batch16_history(200)
    with pytest.raises(UnsupportedLotteryType):
        BigLottoTs3Markov4betAdapter().get_bets(history, LotteryType.POWER_LOTTO)


def test_repeated_execution_byte_equality() -> None:
    history = _batch16_history(500)
    first = BigLottoTs3Markov4betAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    second = BigLottoTs3Markov4betAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second


def test_each_ticket_is_a_legal_six_number_biglotto_bet() -> None:
    history = _batch16_history(300)
    tickets = BigLottoTs3Markov4betAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(tickets) == 4
    for ticket in tickets:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert all(1 <= number <= 49 for number in ticket)
        assert ticket == tuple(sorted(ticket))


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_production_catalog_declares_expected_shape() -> None:
    descriptor = production_catalog().get(STRATEGY_ID)
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count == 4
    assert descriptor.executable is True
    assert descriptor.min_history == 150
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)


def test_production_catalog_appends_batch16_last_and_preserves_prior_order() -> None:
    """Batch 16 adds exactly one descriptor, strictly after every
    pre-existing one (69 -> 71, with PR #149's unrelated composite
    descriptor landing in between, and PR #152 minimal dual bet appended
    after). SELECTED_INTAKE_SET03_R1 later appended 6 more descriptors
    after minimal dual bet, shifting this identity from -2 to -8; nothing
    before it moves."""

    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    assert len(all_ids) == 78
    assert STRATEGY_ID in all_ids
    assert all_ids[-8] == STRATEGY_ID
    assert all_ids.count(STRATEGY_ID) == 1
    assert all_ids[-9] == "legacy_composite__quick_predict_5bet_ts3_markov_freqort"
    assert all_ids[-7] == "legacy_biglotto__minimal_dual_bet_strategy__3c9657df7ff4"


def test_strategy_is_reachable_only_through_the_portfolio_response_path() -> None:
    portfolio = build_production_generate_portfolio()
    assert STRATEGY_ID in portfolio._adapters


def test_generate_portfolio_returns_complete_native_ticket_set() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_batch16_history(200),
        )
    )
    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers == TS3_MARKOV4_GOLDENS[200]
