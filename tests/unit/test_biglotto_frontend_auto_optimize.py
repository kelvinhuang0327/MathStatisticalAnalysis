# pyright: reportPrivateUsage=false
"""Executable old/new parity for the legacy frontend AutoOptimize donor."""

from __future__ import annotations

import sqlite3
from functools import cmp_to_key
from typing import Final, cast

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetStatus,
    build_production_generate_one_bet,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters import (
    BigLottoFrontendAutoOptimizeAdapter,
    CausalDrawRow,
)
from lottolab.strategies.adapters.base import (
    BetAdapter,
    InsufficientHistory,
    InvalidOutput,
    RejectPrediction,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_frontend_auto_optimize import (
    _CANDIDATE_ORDER,
    _CandidateScore,
    _compare_scores,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID: Final = "legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6"
SOURCE_SHA256: Final = (
    "a121d28125c6456dfd71c0f4f72e2b1f164e0e51cd175a4746decb49d129f952"
)


class FormulaRandom:
    """Fixed equivalent of the revived donor's process-global Math.random."""

    def __init__(self) -> None:
        self.calls = 0

    def random(self) -> float:
        value = ((self.calls * 37) % 997) / 997
        self.calls += 1
        return value


def _row(draw: str, numbers: tuple[int, ...]) -> CausalDrawRow:
    return CausalDrawRow(draw, "2020-01-01", numbers)


def _history(length: int, *, edge: bool = False) -> tuple[CausalDrawRow, ...]:
    """Return the canonical oldest-first history passed to LottoLab."""

    rows: list[CausalDrawRow] = []
    for index in range(length):
        if edge:
            numbers = (1, 2, 3, 4, 5, 6) if index % 2 == 0 else (44, 45, 46, 47, 48, 49)
        else:
            numbers = tuple(((index + offset * 8) % 49) + 1 for offset in range(6))
        rows.append(_row(str(index), tuple(sorted(numbers))))
    return tuple(rows)


# Captured from direct Node execution of AutoOptimizeStrategy.predict with the
# bounded synchronous StatisticsService-compatible revival seam, candidate-call
# context binding for getHot/getCold, and the same FormulaRandom stream.
DONOR_GOLDENS: dict[
    str,
    tuple[
        tuple[CausalDrawRow, ...],
        tuple[int, ...],
        str,
        int,
        tuple[tuple[str, float, float], ...],
    ],
] = {
    "single-split-30": (
        _history(30),
        (6, 14, 23, 31, 39, 47),
        "bayesian",
        1_258_893,
        (
            ("bayesian", 1 / 6, 1.0),
            ("markov", 1 / 6, 1.0),
            ("ensemble_boosting", 1 / 6, 1.0),
            ("ensemble_features", 1 / 6, 1.0),
            ("hot_cold", 1 / 6, 1.0),
            ("ensemble_weighted", 1 / 6, 5 / 6),
            ("deviation", 1 / 6, 4 / 6),
            ("collaborative_hybrid", 1 / 6, 4 / 6),
            ("ml_forest", 0.0, 4 / 6),
            ("statistical", 0.0, 2 / 6),
            ("frequency", 0.0, 1 / 6),
            ("montecarlo", 0.0, 1 / 6),
            ("sum_range", 0.0, 1 / 6),
            ("trend", 0.0, 0.0),
        ),
    ),
    "single-split-50": (
        _history(50),
        (2, 3, 4, 5, 6, 7),
        "deviation",
        2_091_646,
        (
            ("deviation", 0.3, 1.7),
            ("markov", 0.2, 1.2),
            ("ensemble_boosting", 0.2, 1.2),
            ("bayesian", 0.2, 1.0),
            ("ensemble_weighted", 0.2, 1.0),
            ("ensemble_features", 0.2, 1.0),
            ("collaborative_hybrid", 0.2, 1.0),
            ("ml_forest", 0.2, 0.8),
            ("hot_cold", 0.1, 0.7),
            ("trend", 0.1, 0.6),
            ("sum_range", 0.0, 0.4),
            ("statistical", 0.0, 0.4),
            ("montecarlo", 0.0, 0.3),
            ("frequency", 0.0, 0.2),
        ),
    ),
    "single-split-edge-1-49": (
        _history(30, edge=True),
        (44, 45, 46, 47, 48, 49),
        "montecarlo",
        1_607_581,
        (
            ("montecarlo", 0.5, 22 / 6),
            ("trend", 0.5, 3.0),
            ("bayesian", 0.5, 3.0),
            ("markov", 0.5, 3.0),
            ("deviation", 0.5, 3.0),
            ("ensemble_weighted", 0.5, 3.0),
            ("ml_forest", 0.5, 2.5),
            ("hot_cold", 0.5, 1.5),
            ("statistical", 1 / 3, 2.0),
            ("collaborative_hybrid", 1 / 6, 7 / 6),
            ("frequency", 0.0, 0.0),
            ("ensemble_boosting", 0.0, 0.0),
            ("ensemble_features", 0.0, 0.0),
            ("sum_range", 0.0, 0.0),
        ),
    ),
    "bounded-newest-500": (
        _history(501),
        (3, 12, 20, 28, 36, 44),
        "bayesian",
        2_090_598,
        (
            ("bayesian", 0.2, 1.2),
            ("markov", 0.2, 1.2),
            ("ensemble_weighted", 0.2, 1.2),
            ("ensemble_boosting", 0.2, 1.2),
            ("ensemble_features", 0.2, 1.2),
            ("collaborative_hybrid", 0.2, 1.2),
            ("deviation", 0.1, 1.1),
            ("trend", 0.1, 0.6),
            ("ml_forest", 0.0, 1.0),
            ("hot_cold", 0.0, 0.7),
            ("montecarlo", 0.0, 0.6),
            ("statistical", 0.0, 0.3),
            ("frequency", 0.0, 0.1),
            ("sum_range", 0.0, 0.1),
        ),
    ),
}


@pytest.mark.parametrize("case", tuple(DONOR_GOLDENS))
def test_auto_optimize_matches_executed_donor_internals(case: str) -> None:
    history, expected_numbers, expected_winner, expected_calls, expected_scores = (
        DONOR_GOLDENS[case]
    )
    rng = FormulaRandom()
    adapter = BigLottoFrontendAutoOptimizeAdapter(rng)

    effective_history = cast(
        tuple[CausalDrawRow, ...], adapter._history_window(history)
    )
    selection = adapter._select(effective_history)

    assert selection.test_size == (6 if len(effective_history) == 30 else 10)
    assert selection.validation_method == "single-split"
    assert tuple(score.strategy for score in selection.candidate_scores) == _CANDIDATE_ORDER
    assert selection.winner == expected_winner
    assert selection.final_numbers == expected_numbers
    assert [score.strategy for score in selection.ordered_scores] == [
        score[0] for score in expected_scores
    ]
    for actual, expected in zip(selection.ordered_scores, expected_scores, strict=True):
        assert actual.strategy == expected[0]
        assert actual.success_rate == pytest.approx(expected[1])
        assert actual.avg_hits == pytest.approx(expected[2])
        assert actual.total_tests == selection.test_size
    assert rng.calls == expected_calls


def test_minimum_boundary_and_native_contract() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoFrontendAutoOptimizeAdapter(FormulaRandom()).get_one_bet(
            _history(29), LotteryType.BIG_LOTTO
        )

    execution = BigLottoFrontendAutoOptimizeAdapter(FormulaRandom()).get_one_bet_with_emission(
        _history(30), LotteryType.BIG_LOTTO
    )
    assert execution.emitted_main_numbers == execution.legal_main_numbers
    assert len(execution.legal_main_numbers) == 6
    assert execution.special_number is None


def test_invalid_history_and_wrong_lottery_fail_closed() -> None:
    adapter = BigLottoFrontendAutoOptimizeAdapter(FormulaRandom())
    invalid = (_row("bad", (1, 1, 2, 3, 4, 5)),) * 30
    with pytest.raises(InvalidOutput):
        adapter.get_one_bet(invalid, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_one_bet(_history(30), LotteryType.DAILY_539)


def test_candidate_period_failure_keeps_period_in_denominator() -> None:
    class FailingAdapter(BetAdapter):
        strategy_id = "test-failing-candidate"
        strategy_name = "test-failing-candidate"
        strategy_version = "test"
        min_history = 1
        supported_lottery_types = (LotteryType.BIG_LOTTO,)

        def _predict(
            self,
            history: tuple[CausalDrawRow, ...],
            lottery_type: LotteryType,
        ) -> tuple[int, ...]:
            del history, lottery_type
            raise RuntimeError("candidate failure")

    adapter = BigLottoFrontendAutoOptimizeAdapter(FormulaRandom())
    adapter._candidate_adapters["frequency"] = FailingAdapter()
    selection = adapter._select(_history(30))
    frequency_score = next(
        score for score in selection.candidate_scores if score.strategy == "frequency"
    )
    assert frequency_score.success_rate == 0.0
    assert frequency_score.avg_hits == 0.0
    assert frequency_score.total_tests == 6
    assert selection.winner == "bayesian"


def test_selector_level_all_candidate_failure_has_no_fallback_reinterpretation() -> None:
    adapter = BigLottoFrontendAutoOptimizeAdapter(FormulaRandom())
    adapter.candidate_strategies = []
    with pytest.raises(RejectPrediction):
        adapter.get_one_bet(_history(30), LotteryType.BIG_LOTTO)


def test_stable_candidate_order_and_donor_comparator_tie_behavior() -> None:
    scores = (
        _CandidateScore("first", 0.50, 2.0, 6),
        _CandidateScore("second", 0.501, 2.0, 6),
        _CandidateScore("third", 0.501, 2.1, 6),
    )
    ordered = sorted(scores, key=cmp_to_key(_compare_scores))
    assert [score.strategy for score in ordered] == ["third", "first", "second"]


def test_private_kfold_boundary_matches_donor_rolling_prefix_shape() -> None:
    adapter = BigLottoFrontendAutoOptimizeAdapter(FormulaRandom())
    donor_train = tuple(reversed(_history(30)))
    donor_test = tuple(reversed(_history(15)))
    score = adapter._evaluate_strategy_kfold("frequency", donor_train, donor_test)
    assert score.strategy == "frequency"
    assert score.total_tests == 15


def test_repeat_invocation_with_fresh_process_stream_is_repeatable() -> None:
    history = _history(30)
    first_rng = FormulaRandom()
    second_rng = FormulaRandom()
    first = BigLottoFrontendAutoOptimizeAdapter(first_rng)._select(history)
    second = BigLottoFrontendAutoOptimizeAdapter(second_rng)._select(history)
    assert first == second
    assert first_rng.calls == second_rng.calls == 1_258_893


def test_catalog_identity_and_registry_are_exactly_one_live_descriptor() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    assert [item.strategy_id for item in catalog].count(STRATEGY_ID) == 1
    assert descriptor.strategy_id == BigLottoFrontendAutoOptimizeAdapter.strategy_id
    assert descriptor.strategy_name == BigLottoFrontendAutoOptimizeAdapter.strategy_name
    assert descriptor.version == BigLottoFrontendAutoOptimizeAdapter.strategy_version
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
    assert descriptor.native_ticket_count == 1
    assert descriptor.min_history == 30
    assert descriptor.adapter_path == (
        "lottolab.strategies.adapters.biglotto_frontend_auto_optimize:"
        "BigLottoFrontendAutoOptimizeAdapter"
    )
    assert f"legacy_source_sha256:{SOURCE_SHA256}" in descriptor.provenance
    assert "legacy_symbol:AutoOptimizeStrategy.predict" in descriptor.provenance
    assert "legacy_runtime:PredictionEngine.strategies.auto_optimize" in descriptor.provenance
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLottoFrontendAutoOptimizeAdapter
    )


def _request(history: tuple[CausalDrawRow, ...]) -> GenerateOneBetInput:
    return GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=history,
    )


def test_production_single_ticket_generation_path_is_reachable() -> None:
    result = build_production_generate_one_bet().execute(_request(_history(30)))
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers is not None
    assert len(result.numbers) == 6
    assert result.special_number is None


def test_production_generation_does_not_open_a_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("AutoOptimize must not open a database")

    monkeypatch.setattr(sqlite3, "connect", forbidden_connect)
    result = build_production_generate_one_bet().execute(_request(_history(30)))
    assert result.status is GenerateOneBetStatus.OK
