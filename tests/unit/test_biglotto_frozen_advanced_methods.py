from __future__ import annotations

import random
from itertools import combinations, islice
from unittest.mock import Mock, call

import pytest

from lottolab.application import biglotto_frozen_advanced_methods as advanced
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, InvalidOutput

BIG = LotteryType.BIG_LOTTO
FIRST_DRAW = CausalDrawRow("1", "2007-01-01", (1, 2, 3, 4, 5, 6))


def test_selector_order_reinstantiation_and_history_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_classes = (
        advanced._ContextualBandit,
        advanced._CopulaAnalyzer,
        advanced._AnomalyDetector,
        advanced._GraphCooccurrence,
        advanced._AttentionScorer,
    )
    instances = []

    def factory(selector_type):
        def instantiate():
            instance = Mock(spec=selector_type)
            index = len(instances)
            instance.predict.return_value = tuple(range(index + 1, index + 7))
            instances.append((selector_type, instance))
            return instance

        return instantiate

    monkeypatch.setattr(advanced, "_METHODS", tuple(factory(cls) for cls in advanced._METHODS))
    rows = tuple(
        CausalDrawRow(str(i), "2007-01-01", numbers)
        for i, numbers in enumerate(islice(combinations(range(1, 50), 6), 1003))
    )
    recent = tuple(row.numbers for row in rows[-1:-1001:-1])
    portfolio = advanced.FrozenAdvancedMethodsBenchmark().get_bets(rows, BIG)
    assert [cls for cls, _ in instances] == [*expected_classes, *expected_classes]
    assert len({id(instance) for _, instance in instances}) == 10
    assert len(recent) == 1000
    offset = 0
    for index, (cls, instance) in enumerate(instances):
        if cls is not advanced._AttentionScorer:
            instance.train.assert_called_once_with(recent[:200])
        repetitions = 2 if index < 5 else 3
        assert instance.predict.call_args_list == [call(recent)] * repetitions
        expected_ticket = tuple(range(index + 1, index + 7))
        assert portfolio[offset : offset + repetitions] == (expected_ticket,) * repetitions
        offset += repetitions
    assert offset == 25


def test_training_failure_and_seeded_per_position_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    rejected_train = Mock(side_effect=ValueError)
    rejected_prediction = Mock(side_effect=ArithmeticError)
    numpy_seed = Mock(wraps=advanced.LegacyNumpyRandomState)
    monkeypatch.setattr(advanced._AnomalyDetector, "train", rejected_train)
    monkeypatch.setattr(advanced._CopulaAnalyzer, "predict", rejected_prediction)
    monkeypatch.setattr(advanced, "LegacyNumpyRandomState", numpy_seed)
    adapter = advanced.FrozenAdvancedMethodsBenchmark()
    python_state = random.getstate()
    for history in ((FIRST_DRAW,), (FIRST_DRAW, FIRST_DRAW)):
        output = adapter.get_bets(history, BIG)
        # A failed train leaves AnomalyDetector usable. A failed predict samples
        # once per bet from the same seed-42 stream across both selector blocks.
        assert [output[n] for n in (4, 5, 16, 17, 18)] == [(1, 2, 3, 4, 5, 6)] * 5
        assert [output[n] for n in (2, 3, 13, 14, 15)] == [
            (2, 8, 15, 16, 18, 41),
            (6, 7, 9, 35, 44, 48),
            (2, 3, 6, 14, 28, 38),
            (2, 13, 15, 33, 36, 39),
            (15, 27, 35, 42, 45, 46),
        ]
    assert random.getstate() == python_state
    assert numpy_seed.call_args_list == [call(42), call(42)]
    assert rejected_train.call_count == 4 and rejected_prediction.call_count == 10


def test_invalid_source_output_is_rejected_outside_exception_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = Mock(return_value=(1, 2, 2, 3, 4, 5))
    monkeypatch.setattr(advanced._ContextualBandit, "predict", invalid)
    with pytest.raises(InvalidOutput, match="illegal advanced-method source ticket"):
        advanced.FrozenAdvancedMethodsBenchmark().get_bets((FIRST_DRAW,), BIG)
    assert invalid.call_count == 1


def test_kendall_ties_use_padding_column_order_and_stable_ranking() -> None:
    selector = advanced._CopulaAnalyzer()
    history = (
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (1, 12, 13, 14, 15, 16),
        (2, 17, 18, 19, 20, 21),
    )
    selector.train(history)
    # For 100 padded rows these columns have 3 and 2 ones, with one joint one.
    # Swapping the divisors or taking their product changes the last bit.
    assert selector.tau[1][2].hex() == selector.tau[2][1].hex() == "0x1.930b7570fae13p-2"
    assert selector.tau[1][49] == selector.tau[49][1] == 0.0
    # All tau scores and frequencies tie in the untrained matrix.
    recent = ((21, 22, 23, 24, 25, 26), (1, 2, 3, 4, 5, 6))
    assert advanced._CopulaAnalyzer().predict(recent) == recent[0]


def test_pagerank_retains_the_frozen_blas_rounding_at_the_sixth_number() -> None:
    # This synthetic graph was evaluated with the NumPy 1.26.2 ARM OpenBLAS kernel.
    history = ((1, 3, 6, 8, 29, 38), (6, 7, 16, 23, 43, 45), (2, 23, 40, 42, 48, 49))
    selector = advanced._GraphCooccurrence()
    selector.train(history)
    assert tuple(sorted(selector.predict(history))) == (1, 3, 6, 8, 23, 29)
