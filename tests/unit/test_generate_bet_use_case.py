"""Closed-outcome tests for the injected GenerateOneBet use case."""

from __future__ import annotations

import json
import random
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
    HistoryParseError,
    build_production_generate_one_bet,
    parse_history_json,
    render_result_json,
    run_cli_generate_bet,
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


def test_production_descriptors_are_promoted_online_and_executable() -> None:
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
        assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
        assert descriptor.executable is True
        assert descriptor.adapter_path is not None

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


def _history_json(rows: tuple[CausalDrawRow, ...] = _history()) -> str:
    return json.dumps(
        [{"draw": row.draw, "date": row.date, "numbers": list(row.numbers)} for row in rows]
    )


def test_parse_history_json_accepts_canonical_rows() -> None:
    parsed = parse_history_json(_history_json())
    assert parsed == _history()


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("not json", "not valid JSON"),
        ("{}", "must be a list"),
        ("[1]", "must be an object"),
        ('[{"date":"x","numbers":[1]}]', "draw must be a non-empty string"),
        ('[{"draw":"","date":"x","numbers":[1]}]', "draw must be a non-empty string"),
        ('[{"draw":"1","date":"","numbers":[1]}]', "date must be a non-empty string"),
        ('[{"draw":"1","date":"x","numbers":"bad"}]', "numbers must be a list of integers"),
        ('[{"draw":"1","date":"x","numbers":[1.5]}]', "numbers must be a list of integers"),
    ],
    ids=[
        "invalid-json",
        "not-a-list",
        "row-not-an-object",
        "missing-draw",
        "blank-draw",
        "blank-date",
        "numbers-not-a-list",
        "numbers-not-integers",
    ],
)
def test_parse_history_json_rejects_malformed_shapes(raw: str, message: str) -> None:
    with pytest.raises(HistoryParseError, match=message):
        parse_history_json(raw)


def test_render_result_json_is_canonical_and_sorted() -> None:
    ok_result = GenerateOneBetResult(
        status=GenerateOneBetStatus.OK,
        numbers=(1, 2, 3, 4, 5, 6),
        special_number=None,
        reason_code=None,
    )
    text = render_result_json(ok_result, strategy_id="fixture", seed=3)
    assert json.loads(text) == {
        "strategy_id": "fixture",
        "lottery_type": "BIG_LOTTO",
        "seed": 3,
        "status": "OK",
        "numbers": [1, 2, 3, 4, 5, 6],
        "reason_code": None,
    }
    assert text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))

    failure_result = GenerateOneBetResult(
        status=GenerateOneBetStatus.REJECTED,
        numbers=None,
        special_number=None,
        reason_code=GenerateOneBetReason.REJECTED_BY_STRATEGY,
    )
    failure_payload = json.loads(render_result_json(failure_result, strategy_id="fixture", seed=0))
    assert failure_payload["numbers"] is None
    assert failure_payload["reason_code"] == "REJECTED_BY_STRATEGY"


def test_build_production_generate_one_bet_registers_exactly_the_two_approved_adapters() -> None:
    use_case = build_production_generate_one_bet()
    for strategy_id, expected_numbers_len in (
        (BigLottoSocialWisdomAntiPopularityAdapter.strategy_id, 6),
        (BigLottoZoneSplit3BetBet1Adapter.strategy_id, 6),
    ):
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=_history(),
            )
        )
        assert result.status is GenerateOneBetStatus.OK
        assert result.numbers is not None
        assert len(result.numbers) == expected_numbers_len

    unregistered = use_case.execute(
        GenerateOneBetInput(
            strategy_id="some_other_strategy",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(),
        )
    )
    assert unregistered.status is GenerateOneBetStatus.STRATEGY_UNAVAILABLE
    assert unregistered.reason_code is GenerateOneBetReason.UNKNOWN_STRATEGY


def test_run_cli_generate_bet_unknown_strategy_is_fail_closed() -> None:
    output, ok = run_cli_generate_bet(
        strategy_id="does-not-exist", seed=1, history_json=_history_json()
    )
    assert ok is False
    payload = json.loads(output)
    assert payload["status"] == "STRATEGY_UNAVAILABLE"
    assert payload["reason_code"] == "UNKNOWN_STRATEGY"
    assert payload["numbers"] is None


def test_run_cli_generate_bet_propagates_history_parse_errors() -> None:
    with pytest.raises(HistoryParseError):
        run_cli_generate_bet(
            strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id,
            seed=1,
            history_json="not json",
        )


def test_run_cli_generate_bet_is_deterministic_and_preserves_global_random_state() -> None:
    random.seed(20260719)
    state_before = random.getstate()

    first, first_ok = run_cli_generate_bet(
        strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id,
        seed=99,
        history_json=_history_json(),
    )
    state_between = random.getstate()
    second, second_ok = run_cli_generate_bet(
        strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id,
        seed=99,
        history_json=_history_json(),
    )
    state_after = random.getstate()

    assert first == second
    assert first_ok is True
    assert second_ok is True
    assert state_before == state_between == state_after


def test_run_cli_generate_bet_seed_is_metadata_only_and_does_not_affect_numbers() -> None:
    random.seed(20260719)
    state_before = random.getstate()

    first, first_ok = run_cli_generate_bet(
        strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id,
        seed=1,
        history_json=_history_json(),
    )
    state_between = random.getstate()
    second, second_ok = run_cli_generate_bet(
        strategy_id=BigLottoZoneSplit3BetBet1Adapter.strategy_id,
        seed=2,
        history_json=_history_json(),
    )
    state_after = random.getstate()

    first_payload = json.loads(first)
    second_payload = json.loads(second)

    assert first_ok is True
    assert second_ok is True
    assert first_payload["seed"] == 1
    assert second_payload["seed"] == 2
    for key in ("strategy_id", "lottery_type", "status", "numbers", "reason_code"):
        assert first_payload[key] == second_payload[key]
    assert state_before == state_between == state_after
