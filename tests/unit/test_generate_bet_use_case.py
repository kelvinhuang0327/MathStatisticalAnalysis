"""Closed-outcome tests for the injected GenerateOneBet use case."""

from __future__ import annotations

import json
import random
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import lottolab.strategies.adapters.biglotto_selected as biglotto_selected_module
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
    BigLottoDeviation2BetAdapter,
    BigLottoP02BetBet1Adapter,
    BigLottoP02BetBet2Adapter,
    BigLottoSocialWisdomAntiPopularityAdapter,
    BigLottoZoneSplit3BetBet1Adapter,
    BigLottoZoneSplit3BetBet2Adapter,
    BigLottoZoneSplit3BetBet3Adapter,
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


def _long_history(rows: int = 100) -> tuple[CausalDrawRow, ...]:
    """A history long enough to clear biglotto_deviation_2bet's min_history=100."""
    return tuple(
        CausalDrawRow(str(index), str(index), (1, 2, 3, 4, 5, 6)) for index in range(rows)
    )


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
        BigLottoZoneSplit3BetBet2Adapter.strategy_id: BigLottoZoneSplit3BetBet2Adapter(),
        BigLottoZoneSplit3BetBet3Adapter.strategy_id: BigLottoZoneSplit3BetBet3Adapter(),
        BigLottoDeviation2BetAdapter.strategy_id: BigLottoDeviation2BetAdapter(),
        BigLottoP02BetBet1Adapter.strategy_id: BigLottoP02BetBet1Adapter(),
        BigLottoP02BetBet2Adapter.strategy_id: BigLottoP02BetBet2Adapter(),
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

    bet2_result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=BigLottoZoneSplit3BetBet2Adapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(),
        )
    )
    assert bet2_result.status is GenerateOneBetStatus.OK
    assert bet2_result.numbers == (15, 16, 17, 21, 26, 31)

    bet3_result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=BigLottoZoneSplit3BetBet3Adapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(),
        )
    )
    assert bet3_result.status is GenerateOneBetStatus.OK
    assert bet3_result.numbers == (38, 41, 42, 44, 48, 49)


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


def test_build_production_generate_one_bet_registers_exactly_the_seven_approved_adapters() -> None:
    use_case = build_production_generate_one_bet()
    for strategy_id, expected_numbers_len, history in (
        (BigLottoSocialWisdomAntiPopularityAdapter.strategy_id, 6, _history()),
        (BigLottoZoneSplit3BetBet1Adapter.strategy_id, 6, _history()),
        (BigLottoZoneSplit3BetBet2Adapter.strategy_id, 6, _history()),
        (BigLottoZoneSplit3BetBet3Adapter.strategy_id, 6, _history()),
        (BigLottoDeviation2BetAdapter.strategy_id, 6, _long_history()),
        (BigLottoP02BetBet1Adapter.strategy_id, 6, _history()),
        (BigLottoP02BetBet2Adapter.strategy_id, 6, _history()),
    ):
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=history,
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


def test_production_use_case_executes_zone_bet2_and_closes_insufficient_history() -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=BigLottoZoneSplit3BetBet2Adapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(),
        )
    )
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers == (15, 16, 17, 21, 26, 31)
    assert result.special_number is None

    insufficient = use_case.execute(
        GenerateOneBetInput(
            strategy_id=BigLottoZoneSplit3BetBet2Adapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=(),
        )
    )
    assert insufficient.status is GenerateOneBetStatus.INSUFFICIENT_HISTORY
    assert insufficient.reason_code is GenerateOneBetReason.INSUFFICIENT_HISTORY
    assert insufficient.numbers is None


def test_production_use_case_returns_only_zone_bet3_and_closes_outcomes() -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=BigLottoZoneSplit3BetBet3Adapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(),
        )
    )
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers == (38, 41, 42, 44, 48, 49)
    assert result.special_number is None

    insufficient = use_case.execute(
        GenerateOneBetInput(
            strategy_id=BigLottoZoneSplit3BetBet3Adapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=(),
        )
    )
    assert insufficient.status is GenerateOneBetStatus.INSUFFICIENT_HISTORY
    assert insufficient.reason_code is GenerateOneBetReason.INSUFFICIENT_HISTORY
    assert insufficient.numbers is None

    unsupported = use_case.execute(
        GenerateOneBetInput(
            strategy_id=BigLottoZoneSplit3BetBet3Adapter.strategy_id,
            lottery_type=LotteryType.POWER_LOTTO,
            history=_history(),
        )
    )
    assert unsupported.status is GenerateOneBetStatus.STRATEGY_UNAVAILABLE
    assert unsupported.reason_code is GenerateOneBetReason.UNSUPPORTED_LOTTERY_TYPE
    assert unsupported.numbers is None


def test_production_use_case_maps_zone_bet3_producer_failure_to_replay_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_producer(_history: object) -> tuple[tuple[int, ...], ...]:
        raise RuntimeError("producer failure must not escape")

    monkeypatch.setattr(biglotto_selected_module, "_zone_split_bets", fail_producer)
    result = build_production_generate_one_bet().execute(
        GenerateOneBetInput(
            strategy_id=BigLottoZoneSplit3BetBet3Adapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(),
        )
    )

    assert result.status is GenerateOneBetStatus.REPLAY_ERROR
    assert result.reason_code is GenerateOneBetReason.REPLAY_ERROR
    assert result.numbers is None
    assert result.special_number is None


def test_production_use_case_executes_only_requested_p0_ticket_and_closes_outcomes() -> None:
    use_case = build_production_generate_one_bet()
    bet1 = use_case.execute(
        GenerateOneBetInput(
            strategy_id=BigLottoP02BetBet1Adapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(),
        )
    )
    bet2 = use_case.execute(
        GenerateOneBetInput(
            strategy_id=BigLottoP02BetBet2Adapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(),
        )
    )
    assert bet1.status is bet2.status is GenerateOneBetStatus.OK
    assert bet1.numbers == (7, 8, 9, 10, 11, 12)
    assert bet2.numbers == (1, 2, 3, 4, 5, 6)
    assert bet1.special_number is bet2.special_number is None

    for strategy_id in (
        BigLottoP02BetBet1Adapter.strategy_id,
        BigLottoP02BetBet2Adapter.strategy_id,
    ):
        insufficient = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=(),
            )
        )
        assert insufficient.status is GenerateOneBetStatus.INSUFFICIENT_HISTORY
        assert insufficient.reason_code is GenerateOneBetReason.INSUFFICIENT_HISTORY
        assert insufficient.numbers is None


def test_run_cli_generate_bet_unknown_strategy_is_fail_closed() -> None:
    output, ok = run_cli_generate_bet(
        strategy_id="does-not-exist", seed=1, history_json=_history_json()
    )
    assert ok is False
    payload = json.loads(output)
    assert payload["status"] == "STRATEGY_UNAVAILABLE"
    assert payload["reason_code"] == "UNKNOWN_STRATEGY"
    assert payload["numbers"] is None


def test_run_cli_generate_bet_executes_the_deviation_strategy() -> None:
    """End-to-end proof that the existing generate-bet CLI vertical executes
    the newly migrated biglotto_deviation_2bet strategy id without any CLI
    syntax change."""
    output, ok = run_cli_generate_bet(
        strategy_id=BigLottoDeviation2BetAdapter.strategy_id,
        seed=1,
        history_json=_history_json(_long_history()),
    )
    assert ok is True
    payload = json.loads(output)
    assert payload["strategy_id"] == BigLottoDeviation2BetAdapter.strategy_id
    assert payload["status"] == "OK"
    assert payload["numbers"] == [1, 2, 3, 4, 5, 6]


def test_run_cli_generate_bet_executes_p0_bet1_through_existing_vertical() -> None:
    output, ok = run_cli_generate_bet(
        strategy_id=BigLottoP02BetBet1Adapter.strategy_id,
        seed=23,
        history_json=_history_json(),
    )
    assert ok is True
    payload = json.loads(output)
    assert payload == {
        "lottery_type": "BIG_LOTTO",
        "numbers": [7, 8, 9, 10, 11, 12],
        "reason_code": None,
        "seed": 23,
        "status": "OK",
        "strategy_id": BigLottoP02BetBet1Adapter.strategy_id,
    }


def test_run_cli_generate_bet_returns_only_p0_bet2_through_existing_vertical() -> None:
    output, ok = run_cli_generate_bet(
        strategy_id=BigLottoP02BetBet2Adapter.strategy_id,
        seed=29,
        history_json=_history_json(),
    )
    assert ok is True
    payload = json.loads(output)
    assert payload == {
        "lottery_type": "BIG_LOTTO",
        "numbers": [1, 2, 3, 4, 5, 6],
        "reason_code": None,
        "seed": 29,
        "status": "OK",
        "strategy_id": BigLottoP02BetBet2Adapter.strategy_id,
    }


def test_run_cli_generate_bet_returns_only_zone_split_bet2() -> None:
    output, ok = run_cli_generate_bet(
        strategy_id=BigLottoZoneSplit3BetBet2Adapter.strategy_id,
        seed=31,
        history_json=_history_json(),
    )
    assert ok is True
    payload = json.loads(output)
    assert payload == {
        "lottery_type": "BIG_LOTTO",
        "numbers": [15, 16, 17, 21, 26, 31],
        "reason_code": None,
        "seed": 31,
        "status": "OK",
        "strategy_id": BigLottoZoneSplit3BetBet2Adapter.strategy_id,
    }


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
