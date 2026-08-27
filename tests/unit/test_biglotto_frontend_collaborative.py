# pyright: reportPrivateUsage=false
"""Executable old/new parity for the legacy frontend Collaborative donor."""

from __future__ import annotations

import inspect
import sqlite3
from typing import Final

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetStatus,
    GeneratePortfolioReason,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters import (
    BigLottoFrontendCollaborativeHybridAdapter,
    CausalDrawRow,
)
from lottolab.strategies.adapters.base import (
    BetAdapter,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_frontend_collaborative import (
    _Consensus,
    _detect_consensus,
    _ExpertResult,
    _final_decision,
    _merge_candidates,
    _refine_candidates,
    _run_expert_groups,
    outcome_for_mode,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID: Final = "legacy_biglotto__frontend_collaborative_hybrid__97d79db161ba"
SOURCE_SHA256: Final = (
    "97d79db161bac5d83aa3c6f4738f33bad1183056fe26dc1dba593fdcb35447db"
)


class FormulaRandom:
    """Fixed equivalent of the donor execution's process-global Math.random."""

    def __init__(self) -> None:
        self.calls = 0

    def random(self) -> float:
        value = ((self.calls * 37) % 997) / 997
        self.calls += 1
        return value


def _row(draw: str, numbers: tuple[int, ...]) -> CausalDrawRow:
    return CausalDrawRow(draw, "2020-01-01", numbers)


def _history(
    length: int,
    multiplier: int = 1,
    step: int = 8,
) -> tuple[CausalDrawRow, ...]:
    """LottoLab's canonical oldest-first causal history."""

    return tuple(
        _row(
            f"stride-{index}",
            tuple(
                sorted(
                    ((index * multiplier + offset * step) % 49) + 1
                    for offset in range(6)
                )
            ),
        )
        for index in range(length)
    )


def _edge_history() -> tuple[CausalDrawRow, ...]:
    return (
        _row("edge-old", (1, 2, 3, 4, 5, 6)),
        _row("edge-new", (44, 45, 46, 47, 48, 49)),
    )


def _same_history() -> tuple[CausalDrawRow, ...]:
    return tuple(
        _row(f"same-{index}", (1, 2, 3, 4, 5, 49)) for index in range(20)
    )


# Captured by executing CollaborativeStrategy.js with the synchronous
# calculateFrequency/calculateMissingValues revival seam and FormulaRandom
# patched onto the single process-global Math.random stream.
HYBRID_GOLDENS: dict[
    str,
    tuple[tuple[CausalDrawRow, ...], tuple[int, ...], int, float, float],
] = {
    "minimum-1": (
        _history(1),
        (2, 9, 17, 25, 33, 41),
        112_531,
        0.17664262714542836,
        0.00026998373747266796,
    ),
    "short-10": (
        _history(10),
        (3, 11, 18, 19, 27, 43),
        82_608,
        0.07193051549598961,
        0.0004460310689141922,
    ),
    "medium-50": (
        _history(50),
        (1, 9, 10, 18, 42, 43),
        82_351,
        0.054087732218818296,
        0.008918809398529385,
    ),
    "long-301": (
        _history(301),
        (15, 16, 17, 24, 32, 48),
        82_420,
        0.036168468032282595,
        0.022996181022100853,
    ),
    "edge-1-49": (
        _edge_history(),
        (1, 2, 3, 4, 5, 14),
        95_286,
        0.11151413211825932,
        0.020965998928104048,
    ),
    "duplicate-expert-selection": (
        _same_history(),
        (1, 2, 3, 4, 5, 12),
        112_682,
        0.15592003588474193,
        0.07147849032102524,
    ),
}


@pytest.mark.parametrize("case", tuple(HYBRID_GOLDENS))
def test_hybrid_matches_executed_donor_golden(case: str) -> None:
    history, expected, expected_calls, probability_one, probability_49 = HYBRID_GOLDENS[case]
    rng = FormulaRandom()
    outcome = outcome_for_mode(tuple(reversed(history)), "hybrid", rng)

    assert outcome.numbers == expected
    assert outcome.confidence == 93
    assert outcome.probabilities[1] == pytest.approx(probability_one, rel=1e-14)
    assert outcome.probabilities[49] == pytest.approx(probability_49, rel=1e-14)
    assert rng.calls == expected_calls


@pytest.mark.parametrize(
    ("mode", "expected", "confidence"),
    [
        ("relay", (2, 3, 4, 9, 11, 27), 95),
        ("cooperative", (1, 2, 3, 11, 18, 27), 91),
        ("hybrid", (3, 11, 18, 19, 27, 43), 93),
        ("unknown-default", (3, 11, 18, 19, 27, 43), 93),
    ],
)
def test_direct_mode_dispatch_matches_executed_donor(
    mode: str,
    expected: tuple[int, ...],
    confidence: int,
) -> None:
    rng = FormulaRandom()
    outcome = outcome_for_mode(tuple(reversed(_history(10))), mode, rng)
    assert outcome.numbers == expected
    assert outcome.confidence == confidence
    assert rng.calls == 82_608


def test_mode_reports_match_executed_donor() -> None:
    history = tuple(reversed(_history(10)))
    relay = outcome_for_mode(history, "relay", FormulaRandom())
    cooperative = outcome_for_mode(history, "cooperative", FormulaRandom())
    hybrid = outcome_for_mode(history, "hybrid", FormulaRandom())

    assert relay.report == (
        "【接力模式】三階段協作過濾\n"
        "探索層: 25 個候選 → 精煉層: 12 個候選 → 決策層: 6 個候選\n"
        "專家組: statistical, probabilistic, sequential, feature, optimizer"
    )
    assert cooperative.report == (
        "【合作模式】11 個專家模型投票\n"
        "共識度: 中 (34.8%)\n"
        "高共識號碼: []"
    )
    assert hybrid.report == (
        "【混合模式】接力過濾 + 合作決策\n"
        "過濾流程: 49 → 25 → 15 → 6\n"
        "參與模型: 11 個"
    )


def test_expert_invocation_order_and_one_shared_rng_stream_match_donor_trace() -> None:
    newest_first = tuple(reversed(_history(10)))
    rng = FormulaRandom()

    statistical = _run_expert_groups(("statistical",), newest_first, rng)
    assert [(result.name, result.numbers) for result in statistical] == [
        ("Frequency", (1, 9, 10, 17, 18, 25)),
        ("Trend", (1, 10, 18, 26, 34, 42)),
        ("Combined", (2, 3, 11, 19, 27, 35)),
    ]
    assert rng.calls == 0

    probabilistic = _run_expert_groups(("probabilistic",), newest_first, rng)
    assert [(result.name, result.numbers) for result in probabilistic] == [
        ("Bayesian", (3, 11, 19, 27, 35, 43)),
        ("Deviation", (1, 2, 3, 4, 5, 6)),
        ("MonteCarlo", (1, 10, 17, 18, 25, 34)),
    ]
    assert rng.calls == 60_000

    sequential = _run_expert_groups(("sequential",), newest_first, rng)
    feature = _run_expert_groups(("feature",), newest_first, rng)
    assert [(result.name, result.numbers) for result in sequential + feature] == [
        ("Markov", (3, 11, 19, 27, 35, 43)),
        ("CoOccurrence", (2, 9, 17, 25, 33, 41)),
        ("FeatureWeighted", (2, 4, 12, 28, 36, 44)),
        ("RandomForest", (18, 41, 42, 43, 44, 45)),
    ]
    assert probabilistic[0].numbers == sequential[0].numbers
    assert rng.calls == 62_732

    optimizer = _run_expert_groups(("optimizer",), newest_first, rng)
    assert [(result.name, result.numbers) for result in optimizer] == [
        ("GeneticAlgorithm", (5, 12, 20, 27, 33, 36))
    ]
    assert rng.calls == 82_608


def _expert(numbers: tuple[int, ...], *, weight: float = 1.0) -> _ExpertResult:
    return _ExpertResult(
        name="synthetic",
        group="synthetic",
        weight=weight,
        numbers=numbers,
        probabilities={number: 0.0 for number in range(1, 50)},
        confidence=0.0,
    )


def _top_six_votes() -> dict[int, float]:
    votes = {number: 0.0 for number in range(1, 50)}
    for number in range(1, 7):
        votes[number] = 100 - number
    return votes


def test_consensus_high_and_low_boundaries_match_executed_donor_helpers() -> None:
    votes = _top_six_votes()
    high = _detect_consensus([_expert((1, 2, 3, 4, 5, 6)) for _ in range(4)], votes)
    assert high == _Consensus(1.0, (1, 2, 3, 4, 5, 6), ())

    low_results = [
        _expert((1, 11, 12, 13, 14, 15)),
        _expert((2, 16, 17, 18, 19, 20)),
        _expert((3, 21, 22, 23, 24, 25)),
        _expert((4, 26, 27, 28, 29, 30)),
        _expert((5, 31, 32, 33, 34, 35)),
        _expert((6, 36, 37, 38, 39, 40)),
        _expert((41, 42, 43, 44, 45, 46)),
        _expert((7, 8, 9, 10, 47, 48)),
        _expert((11, 21, 31, 41, 48, 49)),
        _expert((12, 22, 32, 42, 47, 49)),
    ]
    low = _detect_consensus(low_results, votes)
    assert low.level == pytest.approx(0.1)
    assert low.high_consensus == ()
    assert low.low_consensus == (1, 2, 3, 4, 5, 6)


def test_tie_and_final_decision_fallback_boundaries_match_donor_helpers() -> None:
    assert _merge_candidates([], 49, 25) == list(range(1, 26))
    assert _refine_candidates(list(range(12, 0, -1)), [], 6) == list(range(1, 7))

    candidates = list(range(1, 13))
    all_in = _expert((1, 2, 3, 4, 5, 6), weight=1.6)
    partial = _expert((2, 4, 6, 40, 41, 42), weight=1.6)
    assert _final_decision(candidates, [all_in]) == [1, 2, 3, 4, 5, 6]
    assert _final_decision(candidates, [partial]) == [2, 4, 6, 1, 3, 5]


def test_high_consensus_real_history_matches_executed_donor() -> None:
    rng = FormulaRandom()
    outcome = outcome_for_mode(tuple(reversed(_same_history())), "cooperative", rng)
    assert outcome.numbers == (1, 2, 3, 4, 5, 49)
    assert outcome.confidence == 92
    assert "共識度: 高 (78.8%)" in outcome.report
    assert rng.calls == 112_682


def test_adapter_reverses_oldest_first_history_and_emits_one_legal_ticket() -> None:
    history, expected, expected_calls, _probability_one, _probability_49 = HYBRID_GOLDENS[
        "short-10"
    ]
    rng = FormulaRandom()
    execution = BigLottoFrontendCollaborativeHybridAdapter(rng).get_one_bet_with_emission(
        history, LotteryType.BIG_LOTTO
    )
    assert execution.emitted_main_numbers == expected
    assert execution.legal_main_numbers == expected
    assert execution.special_number is None
    assert rng.calls == expected_calls


def test_minimum_history_is_insufficient_history() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoFrontendCollaborativeHybridAdapter(FormulaRandom()).get_one_bet(
            (), LotteryType.BIG_LOTTO
        )


def test_invalid_history_and_wrong_lottery_fail_closed() -> None:
    adapter = BigLottoFrontendCollaborativeHybridAdapter(FormulaRandom())
    invalid = (CausalDrawRow("bad", "bad", (1, 1, 2, 3, 4, 5)),)
    with pytest.raises(InvalidOutput):
        adapter.get_one_bet(invalid, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_one_bet(_history(1), LotteryType.DAILY_539)


def test_adapter_does_not_seed_or_consume_generate_request_seed() -> None:
    source = inspect.getsource(BigLottoFrontendCollaborativeHybridAdapter)
    assert "random.seed(" not in source
    assert "GenerateOneBetInput.seed" not in source


def test_catalog_registers_only_the_live_hybrid_descriptor() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    assert [item.strategy_id for item in catalog].count(STRATEGY_ID) == 1
    assert descriptor.strategy_id == BigLottoFrontendCollaborativeHybridAdapter.strategy_id
    assert descriptor.strategy_name == BigLottoFrontendCollaborativeHybridAdapter.strategy_name
    assert descriptor.version == BigLottoFrontendCollaborativeHybridAdapter.strategy_version
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
    assert descriptor.native_ticket_count == 1
    assert descriptor.min_history == 1
    assert descriptor.adapter_path == (
        "lottolab.strategies.adapters.biglotto_frontend_collaborative:"
        "BigLottoFrontendCollaborativeHybridAdapter"
    )
    assert f"legacy_source_sha256:{SOURCE_SHA256}" in descriptor.provenance
    assert "legacy_alias_remap:collaborative_relay_TO_collaborative_hybrid" in (
        descriptor.provenance
    )
    assert "legacy_alias_remap:collaborative_coop_TO_collaborative_hybrid" in (
        descriptor.provenance
    )
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLottoFrontendCollaborativeHybridAdapter
    )

    catalog_ids = [item.strategy_id for item in catalog]
    assert all("collaborative_relay" not in strategy_id for strategy_id in catalog_ids)
    assert all("collaborative_coop" not in strategy_id for strategy_id in catalog_ids)


def _request(history: tuple[CausalDrawRow, ...]) -> GenerateOneBetInput:
    return GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=history,
        seed=12345,
    )


def test_production_single_ticket_generation_path_is_reachable() -> None:
    result = build_production_generate_one_bet().execute(_request(_history(10)))
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers is not None
    assert len(result.numbers) == 6
    assert result.numbers == tuple(sorted(set(result.numbers)))
    assert all(1 <= number <= 49 for number in result.numbers)
    assert result.special_number is None
    assert result.reason_code is None


def test_portfolio_path_rejects_single_ticket_identity() -> None:
    result = build_production_generate_portfolio().execute(_request(_history(10)))
    assert result.status is GeneratePortfolioStatus.WRONG_RESPONSE_PATH
    assert result.numbers is None
    assert result.reason_code is GeneratePortfolioReason.STRATEGY_IS_NOT_PORTFOLIO


def test_production_generation_never_opens_a_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbidden_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Collaborative strategy must not open a database")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)
    result = build_production_generate_one_bet().execute(_request(_history(10)))
    assert result.status is GenerateOneBetStatus.OK


def test_adapter_contract_is_single_ticket_bet_adapter() -> None:
    assert issubclass(BigLottoFrontendCollaborativeHybridAdapter, BetAdapter)
