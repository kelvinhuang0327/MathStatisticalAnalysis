"""Closed-outcome tests for the injected GenerateOneBet use case."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from lottolab.application.use_cases.generate_bet import (
    AdapterIdentityMismatchError,
    GenerateOneBet,
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetResult,
    GenerateOneBetStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.strategies.adapters import (
    BetAdapter,
    BigLottoSocialWisdomAntiPopularityAdapter,
    BigLottoZoneSplit3BetBet1Adapter,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    RejectPrediction,
    UnsupportedLotteryType,
)
from lottolab.strategies.catalog import StrategyCatalog, production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]
STRATEGY_ID = "fixture_generate_one_bet"
STRATEGY_NAME = "Fixture Generate One Bet"
STRATEGY_VERSION = "v1.0"


def _descriptor(
    *,
    strategy_id: str = STRATEGY_ID,
    strategy_name: str = STRATEGY_NAME,
    version: str = STRATEGY_VERSION,
) -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        version=version,
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.OBSERVATION,
        executable=False,
        min_history=1,
        provenance=("fixture:generate-one-bet",),
    )


def _history() -> tuple[CausalDrawRow, ...]:
    return (CausalDrawRow("1", "2026-01-01", (1, 2, 3, 4, 5, 6)),)


def _request(
    *,
    strategy_id: str = STRATEGY_ID,
    lottery_type: LotteryType = LotteryType.BIG_LOTTO,
) -> GenerateOneBetInput:
    return GenerateOneBetInput(
        strategy_id=strategy_id,
        lottery_type=lottery_type,
        history=_history(),
    )


class _OutcomeAdapter(BetAdapter):
    strategy_id = STRATEGY_ID
    strategy_name = STRATEGY_NAME
    strategy_version = STRATEGY_VERSION
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def __init__(self, outcome: str = "ok") -> None:
        self.outcome = outcome
        self.calls = 0

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        self.calls += 1
        if self.outcome == "rejected":
            raise RejectPrediction("raw reject detail must not escape")
        if self.outcome == "insufficient":
            raise InsufficientHistory("raw history detail must not escape")
        if self.outcome == "invalid":
            raise InvalidOutput("raw invalid detail must not escape")
        if self.outcome == "replay-error":
            raise RuntimeError("raw runtime detail must not escape")
        if self.outcome == "unsupported":
            raise UnsupportedLotteryType("raw unsupported detail must not escape")
        if self.outcome == "interrupt":
            raise KeyboardInterrupt("control-flow exceptions must propagate")
        return (49, 41, 35, 34, 33, 32)


class _WrongIdAdapter(_OutcomeAdapter):
    strategy_id = "wrong-id"


class _WrongNameAdapter(_OutcomeAdapter):
    strategy_name = "Wrong Name"


class _WrongVersionAdapter(_OutcomeAdapter):
    strategy_version = "wrong-version"


@pytest.mark.parametrize(
    ("outcome", "expected_status", "expected_reason"),
    [
        (
            "rejected",
            GenerateOneBetStatus.REJECTED,
            GenerateOneBetReason.REJECTED_BY_STRATEGY,
        ),
        (
            "insufficient",
            GenerateOneBetStatus.INSUFFICIENT_HISTORY,
            GenerateOneBetReason.INSUFFICIENT_HISTORY,
        ),
        (
            "invalid",
            GenerateOneBetStatus.INVALID_OUTPUT,
            GenerateOneBetReason.INVALID_OUTPUT,
        ),
        (
            "replay-error",
            GenerateOneBetStatus.REPLAY_ERROR,
            GenerateOneBetReason.REPLAY_ERROR,
        ),
    ],
)
def test_expected_adapter_outcomes_are_closed(
    outcome: str,
    expected_status: GenerateOneBetStatus,
    expected_reason: GenerateOneBetReason,
) -> None:
    use_case = GenerateOneBet(
        StrategyCatalog((_descriptor(),)),
        {STRATEGY_ID: _OutcomeAdapter(outcome)},
    )
    result = use_case.execute(_request())
    assert result.status is expected_status
    assert result.reason_code is expected_reason
    assert result.numbers is None
    assert result.special_number is None


def test_ok_result_is_canonical_and_typed() -> None:
    use_case = GenerateOneBet(
        StrategyCatalog((_descriptor(),)),
        {STRATEGY_ID: _OutcomeAdapter()},
    )
    result = use_case.execute(_request())
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers == (32, 33, 34, 35, 41, 49)
    assert result.special_number is None
    assert result.reason_code is None


def test_unknown_strategy_is_unavailable() -> None:
    use_case = GenerateOneBet(StrategyCatalog((_descriptor(),)), {})
    result = use_case.execute(_request(strategy_id="missing"))
    assert result.status is GenerateOneBetStatus.STRATEGY_UNAVAILABLE
    assert result.reason_code is GenerateOneBetReason.UNKNOWN_STRATEGY


def test_known_strategy_without_injected_adapter_is_unavailable() -> None:
    use_case = GenerateOneBet(StrategyCatalog((_descriptor(),)), {})
    result = use_case.execute(_request())
    assert result.status is GenerateOneBetStatus.STRATEGY_UNAVAILABLE
    assert result.reason_code is GenerateOneBetReason.ADAPTER_NOT_INJECTED


def test_unsupported_lottery_type_is_unavailable() -> None:
    use_case = GenerateOneBet(
        StrategyCatalog((_descriptor(),)),
        {STRATEGY_ID: _OutcomeAdapter()},
    )
    result = use_case.execute(_request(lottery_type=LotteryType.POWER_LOTTO))
    assert result.status is GenerateOneBetStatus.STRATEGY_UNAVAILABLE
    assert result.reason_code is GenerateOneBetReason.UNSUPPORTED_LOTTERY_TYPE


def test_adapter_raised_unsupported_lottery_type_is_unavailable() -> None:
    use_case = GenerateOneBet(
        StrategyCatalog((_descriptor(),)),
        {STRATEGY_ID: _OutcomeAdapter("unsupported")},
    )

    result = use_case.execute(_request())

    assert result.status is GenerateOneBetStatus.STRATEGY_UNAVAILABLE
    assert result.reason_code is GenerateOneBetReason.UNSUPPORTED_LOTTERY_TYPE
    assert result.numbers is None
    assert result.special_number is None


def test_non_exception_base_exception_propagates() -> None:
    use_case = GenerateOneBet(
        StrategyCatalog((_descriptor(),)),
        {STRATEGY_ID: _OutcomeAdapter("interrupt")},
    )

    with pytest.raises(KeyboardInterrupt, match="control-flow exceptions must propagate"):
        use_case.execute(_request())


@pytest.mark.parametrize(
    "adapter",
    [_WrongIdAdapter(), _WrongNameAdapter(), _WrongVersionAdapter()],
    ids=["strategy-id", "strategy-name", "strategy-version"],
)
def test_catalog_adapter_identity_mismatch_fails_at_construction(adapter: BetAdapter) -> None:
    with pytest.raises(AdapterIdentityMismatchError):
        GenerateOneBet(StrategyCatalog((_descriptor(),)), {STRATEGY_ID: adapter})


def test_injected_dependencies_are_isolated_and_not_mutated() -> None:
    descriptor = _descriptor()
    catalog = StrategyCatalog((descriptor,))
    adapter = _OutcomeAdapter()
    adapters = {STRATEGY_ID: adapter}
    catalog_before = catalog.list()
    adapters_before = dict(adapters)

    use_case = GenerateOneBet(catalog, adapters)
    result = use_case.execute(_request())

    assert result.status is GenerateOneBetStatus.OK
    assert adapter.calls == 1
    assert catalog.list() == catalog_before
    assert adapters == adapters_before


def test_adapter_mapping_is_a_construction_time_snapshot() -> None:
    catalog = StrategyCatalog((_descriptor(),))
    original_adapter = _OutcomeAdapter()
    adapters = {STRATEGY_ID: original_adapter}
    adapters_before_construction = dict(adapters)

    use_case = GenerateOneBet(catalog, adapters)

    assert adapters == adapters_before_construction
    adapters.clear()
    replacement_adapter = _OutcomeAdapter()
    adapters["replacement"] = replacement_adapter
    adapters_after_caller_mutation = dict(adapters)

    result = use_case.execute(_request())

    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers == (32, 33, 34, 35, 41, 49)
    assert original_adapter.calls == 1
    assert replacement_adapter.calls == 0
    assert adapters == adapters_after_caller_mutation


def test_production_descriptors_remain_observation_and_non_executable() -> None:
    catalog = production_catalog()
    adapters: dict[str, BetAdapter] = {
        BigLottoSocialWisdomAntiPopularityAdapter.strategy_id: (
            BigLottoSocialWisdomAntiPopularityAdapter()
        ),
        BigLottoZoneSplit3BetBet1Adapter.strategy_id: BigLottoZoneSplit3BetBet1Adapter(),
    }
    use_case = GenerateOneBet(catalog, adapters)
    for strategy_id in adapters:
        descriptor = catalog.get(strategy_id)
        assert descriptor.lifecycle_status is LifecycleStatus.OBSERVATION
        assert descriptor.executable is False
        assert descriptor.adapter_path is None

    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(),
        )
    )
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers == (4, 6, 11, 14, 15, 18)


def test_status_enum_is_closed_to_authorized_outcomes() -> None:
    assert {status.value for status in GenerateOneBetStatus} == {
        "OK",
        "REJECTED",
        "INSUFFICIENT_HISTORY",
        "STRATEGY_UNAVAILABLE",
        "INVALID_OUTPUT",
        "REPLAY_ERROR",
    }


@pytest.mark.parametrize(
    ("status", "numbers", "reason"),
    [
        (GenerateOneBetStatus.OK, None, None),
        (
            GenerateOneBetStatus.OK,
            (1, 2, 3, 4, 5, 6),
            GenerateOneBetReason.INVALID_OUTPUT,
        ),
        (
            GenerateOneBetStatus.REJECTED,
            (1, 2, 3, 4, 5, 6),
            GenerateOneBetReason.REJECTED_BY_STRATEGY,
        ),
        (GenerateOneBetStatus.REJECTED, None, None),
    ],
    ids=[
        "ok-without-numbers",
        "ok-with-reason",
        "failure-with-numbers",
        "failure-without-reason",
    ],
)
def test_result_invariants_reject_invalid_direct_construction(
    status: GenerateOneBetStatus,
    numbers: tuple[int, ...] | None,
    reason: GenerateOneBetReason | None,
) -> None:
    with pytest.raises(ValueError):
        GenerateOneBetResult(
            status=status,
            numbers=numbers,
            special_number=None,
            reason_code=reason,
        )


def test_result_invariants_allow_valid_direct_construction() -> None:
    valid_ok = GenerateOneBetResult(
        status=GenerateOneBetStatus.OK,
        numbers=(1, 2, 3, 4, 5, 6),
        special_number=None,
        reason_code=None,
    )
    valid_failure = GenerateOneBetResult(
        status=GenerateOneBetStatus.REJECTED,
        numbers=None,
        special_number=None,
        reason_code=GenerateOneBetReason.REJECTED_BY_STRATEGY,
    )

    assert valid_ok.numbers == (1, 2, 3, 4, 5, 6)
    assert valid_ok.reason_code is None
    assert valid_failure.numbers is None
    assert valid_failure.reason_code is GenerateOneBetReason.REJECTED_BY_STRATEGY


def test_input_and_result_models_are_frozen() -> None:
    request = _request()
    use_case = GenerateOneBet(
        StrategyCatalog((_descriptor(),)),
        {STRATEGY_ID: _OutcomeAdapter()},
    )
    result = use_case.execute(request)
    with pytest.raises(FrozenInstanceError):
        request.strategy_id = "changed"  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(FrozenInstanceError):
        result.numbers = None  # pyright: ignore[reportAttributeAccessIssue]


def test_import_does_not_load_or_mutate_executable_registry() -> None:
    code = (
        "import sys\n"
        "import lottolab.application.use_cases.generate_bet\n"
        "print('lottolab.strategies.executable_registry' in sys.modules)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == "False\n"
