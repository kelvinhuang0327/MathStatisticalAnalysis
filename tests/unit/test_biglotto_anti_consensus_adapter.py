"""Mechanism-component parity for the native Anti-Consensus migration."""

# pyright: reportPrivateUsage=false
# Differential acceptance intentionally exercises retained/target components.

from __future__ import annotations

import json

import pytest

import lottolab.strategies.adapters.biglotto_anti_consensus as anti_module
from lottolab.application.legacy_history_native_portfolios import (
    LegacyNumpyRandomState,
)
from lottolab.application.legacy_history_native_portfolios_wave2 import (
    _anti_consensus as retained_anti_consensus,
)
from lottolab.application.legacy_history_native_portfolios_wave2 import (
    _anti_consensus_score as retained_anti_consensus_score,
)
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GeneratePortfolioReason,
    GeneratePortfolioStatus,
    build_production_generate_portfolio,
    run_cli_generate_portfolio,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    load_full_strategy_catalog,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_anti_consensus import (
    BigLottoAntiConsensusStrategyAdapter,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__anti_consensus_strategy__a454ddd26cef"
SOURCE_SHA256 = "a454ddd26cef405db5e9b4b4f5d2c0f5e1df14d291bbd0505d45be36a2cecc80"


def _history(count: int = 1) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date=f"2026-01-{index % 28 + 1:02d}",
            numbers=tuple(sorted(((index * 7 + offset * 8) % 49) + 1 for offset in range(6))),
        )
        for index in range(count)
    )


def _history_json(count: int = 1) -> str:
    return json.dumps(
        [
            {"draw": row.draw, "date": row.date, "numbers": list(row.numbers)}
            for row in _history(count)
        ]
    )


class _RecordingRng:
    def __init__(self, seed: int) -> None:
        self._delegate = anti_module._LegacyNumpyRandomState(seed)
        self.calls: list[tuple[tuple[int, ...], int]] = []

    def choice_without_replacement(
        self,
        values: list[int],
        size: int,
    ) -> list[int]:
        self.calls.append((tuple(values), size))
        return self._delegate.choice_without_replacement(values, size)


class _PrefixRng:
    """Deterministic fixture that makes positional duplicates unavoidable."""

    def __init__(self) -> None:
        self.call_count = 0

    def choice_without_replacement(
        self,
        values: list[int],
        size: int,
    ) -> list[int]:
        self.call_count += 1
        return values[:size]


def test_authoritative_identity_is_unique_cataloged_six_ticket_portfolio() -> None:
    retained = next(
        record
        for record in load_full_strategy_catalog().records
        if record.strategy_id == STRATEGY_ID
    )
    assert retained.legacy_method_id == "lottery_api/models/anti_consensus_strategy.py"
    assert retained.source_sha256 == SOURCE_SHA256
    assert retained.method_family == "folklore"

    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    assert sum(item.strategy_id == STRATEGY_ID for item in catalog) == 1
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count_bounds == (6, 6)
    assert descriptor.min_history == 1
    assert f"legacy_source_sha256:{SOURCE_SHA256}" in descriptor.provenance
    assert "rng_authority:HISTORICAL_REPLAY_SEED_ONLY_MISSING" in descriptor.provenance
    assert "donor_parity:MECHANISM_COMPONENT_PARITY" in descriptor.provenance

    registry = ExecutableRegistry(catalog)
    assert registry.load_adapter(STRATEGY_ID) is BigLottoAntiConsensusStrategyAdapter


@pytest.mark.parametrize(
    "numbers",
    (
        [1, 2, 3, 4, 5, 6],
        [4, 13, 14, 32, 40, 49],
        [6, 8, 18, 28, 38, 48],
        [32, 35, 39, 42, 46, 49],
    ),
)
def test_consensus_scoring_components_match_retained_donor(numbers: list[int]) -> None:
    assert anti_module._anti_consensus_score(numbers) == retained_anti_consensus_score(
        numbers
    )


@pytest.mark.parametrize("seed", (0, 42, 2**32 - 1))
def test_numpy_random_state_operations_match_retained_reference(seed: int) -> None:
    target = anti_module._LegacyNumpyRandomState(seed)
    retained = LegacyNumpyRandomState(seed)
    operations = (
        (list(range(32, 50)), 6),
        (list({4, 13, 14}), 2),
        (list(range(1, 32)), 2),
        (list(range(32, 50)), 4),
        (list(range(1, 32)), 2),
    )
    for population, size in operations:
        assert target.choice_without_replacement(
            population, size
        ) == retained.choice_without_replacement(population, size)


def test_rng_call_sequence_populations_and_distributions_are_exact() -> None:
    rng = _RecordingRng(20260820)

    tickets = anti_module._anti_consensus_tickets(rng)

    large = tuple(range(32, 50))
    unlucky = tuple({4, 13, 14})
    assert rng.calls[:9] == [
        (large, 6),
        (large, 6),
        (large, 6),
        (unlucky, 2),
        (large, 4),
        (unlucky, 2),
        (large, 4),
        (unlucky, 2),
        (large, 4),
    ]
    assert len(rng.calls) == 6009
    assert set(rng.calls[9::2]) == {(tuple(range(1, 32)), 2)}
    assert set(rng.calls[10::2]) == {(large, 4)}
    assert len(tickets) == 6


@pytest.mark.parametrize(
    ("seed", "history_count"),
    ((0, 1), (42, 17), (2**32 - 1, 120)),
)
def test_seeded_target_matches_retained_mechanism_components(
    seed: int,
    history_count: int,
) -> None:
    actual = BigLottoAntiConsensusStrategyAdapter(rng_seed=seed).get_bets(
        _history(history_count),
        LotteryType.BIG_LOTTO,
    )

    assert actual == retained_anti_consensus(seed)
    assert len(actual) == 6
    assert all(
        len(ticket) == 6
        and len(set(ticket)) == 6
        and tuple(sorted(ticket)) == ticket
        and all(1 <= number <= 49 for number in ticket)
        for ticket in actual
    )
    scores = [anti_module._anti_consensus_score(list(ticket)) for ticket in actual]
    assert scores == sorted(scores)


def test_rng_results_do_not_change_call_count_or_portfolio_cardinality() -> None:
    rng = _PrefixRng()

    tickets = anti_module._anti_consensus_tickets(rng)

    assert rng.call_count == 6009
    assert len(tickets) == 6
    assert len(set(tickets)) == 2
    assert tickets.count(tickets[0]) == 3
    assert tickets.count(tickets[-1]) == 3


def test_same_seed_is_deterministic_history_blind_and_rng_isolated() -> None:
    adapter = BigLottoAntiConsensusStrategyAdapter(rng_seed=7919)
    short = adapter.get_bets(_history(1), LotteryType.BIG_LOTTO)
    long = adapter.get_bets(_history(120), LotteryType.BIG_LOTTO)
    interleaved = BigLottoAntiConsensusStrategyAdapter(rng_seed=104729).get_bets(
        _history(9), LotteryType.BIG_LOTTO
    )
    repeated = adapter.get_bets(_history(1), LotteryType.BIG_LOTTO)

    assert short == long == repeated
    assert interleaved != short
    assert adapter.with_seed(7919).get_bets(
        _history(1), LotteryType.BIG_LOTTO
    ) == short


def test_malformed_insufficient_and_unsupported_inputs_fail_closed() -> None:
    adapter = BigLottoAntiConsensusStrategyAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_bets((), LotteryType.BIG_LOTTO)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(list(_history()), LotteryType.BIG_LOTTO)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(
            (
                CausalDrawRow(
                    draw="bad",
                    date="2026-01-01",
                    numbers=(1, 1, 2, 3, 4, 5),
                ),
            ),
            LotteryType.BIG_LOTTO,
        )
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(_history(), LotteryType.DAILY_539)
    for invalid_seed in (-1, True, 2**32):
        with pytest.raises(InvalidOutput):
            BigLottoAntiConsensusStrategyAdapter(rng_seed=invalid_seed)


def test_production_generation_injects_explicit_seed_and_preserves_full_portfolio() -> None:
    use_case = build_production_generate_portfolio()
    request = GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=_history(3),
        seed=37,
    )

    first = use_case.execute(request)
    second = use_case.execute(request)
    changed_seed = use_case.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=request.history,
            seed=38,
        )
    )
    missing_seed = use_case.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=request.history,
        )
    )

    assert first.status is GeneratePortfolioStatus.OK
    assert first.numbers is not None and len(first.numbers) == 6
    assert second == first
    assert changed_seed.status is GeneratePortfolioStatus.OK
    assert changed_seed.numbers != first.numbers
    assert missing_seed.status is GeneratePortfolioStatus.INVALID_OUTPUT
    assert missing_seed.reason_code is GeneratePortfolioReason.INVALID_OUTPUT


def test_cli_generation_seed_is_executable_not_a_fabricated_historical_fixture() -> None:
    first_text, first_ok = run_cli_generate_portfolio(
        strategy_id=STRATEGY_ID,
        seed=1234,
        history_json=_history_json(2),
    )
    second_text, second_ok = run_cli_generate_portfolio(
        strategy_id=STRATEGY_ID,
        seed=1234,
        history_json=_history_json(2),
    )
    changed_text, changed_ok = run_cli_generate_portfolio(
        strategy_id=STRATEGY_ID,
        seed=1235,
        history_json=_history_json(2),
    )
    first = json.loads(first_text)
    second = json.loads(second_text)
    changed = json.loads(changed_text)

    assert first_ok is second_ok is changed_ok is True
    assert first["status"] == "OK"
    assert first["seed"] == 1234
    assert len(first["numbers"]) == 6
    assert second["numbers"] == first["numbers"]
    assert changed["numbers"] != first["numbers"]


def test_rng_failure_has_no_alternate_predictor_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ExplodingRng:
        def choice_without_replacement(
            self,
            values: list[int],
            size: int,
        ) -> list[int]:
            del values, size
            raise RuntimeError("rng unavailable")

    def exploding_rng_factory(_seed: int) -> _ExplodingRng:
        return _ExplodingRng()

    monkeypatch.setattr(
        anti_module,
        "_LegacyNumpyRandomState",
        exploding_rng_factory,
    )

    with pytest.raises(RuntimeError, match="rng unavailable"):
        BigLottoAntiConsensusStrategyAdapter(rng_seed=7).get_bets(
            _history(), LotteryType.BIG_LOTTO
        )
