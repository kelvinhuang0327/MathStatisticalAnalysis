"""Closed-outcome tests for the injected GenerateLiveZoneSplitBets use case."""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from lottolab.application.use_cases.generate_live_zone_split_bets import (
    GenerateLiveZoneSplitBets,
    GenerateLiveZoneSplitBetsInput,
    GenerateLiveZoneSplitBetsReason,
    GenerateLiveZoneSplitBetsResult,
    GenerateLiveZoneSplitBetsStatus,
    build_production_generate_live_zone_split_bets,
)
from lottolab.domain.strategies import LifecycleStatus
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.live.biglotto_zone_split import (
    LiveZoneSplitResult,
    MalformedSamplerOutput,
)

_POOL_SIZE = 49


def _result(
    *,
    bets: tuple[tuple[int, ...], ...] = ((1, 2, 3, 4, 5, 6),),
    coverage_rate: float | None = None,
    total_unique_numbers: int | None = None,
    method: str = "fixture-method",
    philosophy: str = "fixture-philosophy",
) -> LiveZoneSplitResult:
    all_numbers = {number for bet in bets for number in bet}
    if total_unique_numbers is None:
        total_unique_numbers = len(all_numbers)
    if coverage_rate is None:
        coverage_rate = round(len(all_numbers) / _POOL_SIZE, 4)
    return LiveZoneSplitResult(
        bets=bets,
        coverage_rate=coverage_rate,
        total_unique_numbers=total_unique_numbers,
        method=method,
        philosophy=philosophy,
    )


def _spy(outcome: object):
    calls: list[int] = []

    def generator(num_bets: int) -> LiveZoneSplitResult:
        calls.append(num_bets)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome  # type: ignore[return-value]

    return generator, calls


# --- 1. valid generator maps every field exactly ---------------------------


def test_execute_maps_valid_generator_output_to_ok_result() -> None:
    bets = ((1, 2, 3, 4, 5, 6), (10, 11, 12, 13, 14, 15), (20, 21, 22, 23, 24, 25))
    core_result = _result(bets=bets, method="m", philosophy="p")
    generator, calls = _spy(core_result)
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=3))

    assert calls == [3]
    assert result.status is GenerateLiveZoneSplitBetsStatus.OK
    assert result.bets == bets
    assert result.coverage_rate == core_result.coverage_rate
    assert result.total_unique_numbers == core_result.total_unique_numbers
    assert result.method == "m"
    assert result.philosophy == "p"
    assert result.reason_code is None


# --- 2. production builder returns structurally valid results --------------


@pytest.mark.parametrize("num_bets", [1, 3, 10])
def test_production_builder_returns_structurally_valid_results(num_bets: int) -> None:
    use_case = build_production_generate_live_zone_split_bets()

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=num_bets))

    assert result.status is GenerateLiveZoneSplitBetsStatus.OK
    assert result.reason_code is None
    assert result.bets is not None
    assert len(result.bets) == num_bets
    seen: set[int] = set()
    for bet in result.bets:
        assert len(bet) == 6
        assert len(set(bet)) == 6
        assert all(1 <= number <= 49 for number in bet)
        seen.update(bet)
    assert result.total_unique_numbers == len(seen)
    assert result.coverage_rate == round(len(seen) / _POOL_SIZE, 4)
    assert result.method
    assert result.philosophy


# --- 4. invalid inputs fail closed and never call the generator ------------


@pytest.mark.parametrize(
    "num_bets",
    [0, 11, -1, True, False, 3.0, "3"],
    ids=["zero", "above-max", "negative", "bool-true", "bool-false", "float", "string"],
)
def test_execute_rejects_invalid_num_bets_without_calling_generator(num_bets: object) -> None:
    generator, calls = _spy(_result())
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=num_bets))  # type: ignore[arg-type]

    assert calls == []
    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_REQUEST
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.INVALID_NUM_BETS
    assert result.bets is None


# --- 5. MalformedSamplerOutput maps to INVALID_OUTPUT/MALFORMED_OUTPUT -----


def test_execute_maps_malformed_sampler_output_to_invalid_output() -> None:
    generator, _ = _spy(MalformedSamplerOutput("bad sampler output"))
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=3))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT
    assert result.bets is None


# --- 6. unexpected exceptions map to EXECUTION_ERROR/EXECUTION_ERROR -------


def test_execute_maps_unexpected_exception_to_execution_error() -> None:
    generator, _ = _spy(RuntimeError("boom"))
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=3))

    assert result.status is GenerateLiveZoneSplitBetsStatus.EXECUTION_ERROR
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.EXECUTION_ERROR
    assert result.bets is None


# --- 7. wrong return type maps to INVALID_OUTPUT ----------------------------


def test_execute_rejects_wrong_generator_return_type() -> None:
    generator, _ = _spy({"not": "a LiveZoneSplitResult"})
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=3))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT


# --- 8. wrong bet count maps to INVALID_OUTPUT ------------------------------


def test_execute_rejects_wrong_bet_count() -> None:
    core_result = _result(bets=((1, 2, 3, 4, 5, 6),))
    generator, _ = _spy(core_result)
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=3))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT


# --- 9. invalid element type, duplicates, wrong count, out-of-range --------


@pytest.mark.parametrize(
    "bad_bets",
    [
        (("1", 2, 3, 4, 5, 6),),
        ((1, 1, 2, 3, 4, 5),),
        ((1, 2, 3, 4, 5),),
        ((1, 2, 3, 4, 5, 6, 7),),
        ((0, 2, 3, 4, 5, 6),),
        ((1, 2, 3, 4, 5, 50),),
        ([1, 2, 3, 4, 5, 6],),
        ((True, 2, 3, 4, 5, 6),),
    ],
    ids=[
        "wrong-element-type",
        "duplicate",
        "too-short",
        "too-long",
        "below-range",
        "above-range",
        "list-not-tuple",
        "bool-not-exact-int",
    ],
)
def test_execute_rejects_malformed_bet_contents(bad_bets: object) -> None:
    core_result = _result(bets=bad_bets)  # type: ignore[arg-type]
    generator, _ = _spy(core_result)
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=1))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT


# --- 10. inconsistent total_unique_numbers maps to INVALID_OUTPUT ----------


def test_execute_rejects_inconsistent_total_unique_numbers() -> None:
    core_result = _result(bets=((1, 2, 3, 4, 5, 6),), total_unique_numbers=99)
    generator, _ = _spy(core_result)
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=1))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT


# --- 11. inconsistent coverage_rate maps to INVALID_OUTPUT ------------------


def test_execute_rejects_inconsistent_coverage_rate() -> None:
    core_result = _result(bets=((1, 2, 3, 4, 5, 6),), coverage_rate=0.9999)
    generator, _ = _spy(core_result)
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=1))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT


# --- 12. empty method or philosophy maps to INVALID_OUTPUT -----------------


@pytest.mark.parametrize(
    "method,philosophy",
    [("", "p"), ("m", "")],
    ids=["empty-method", "empty-philosophy"],
)
def test_execute_rejects_empty_method_or_philosophy(method: str, philosophy: str) -> None:
    core_result = _result(method=method, philosophy=philosophy)
    generator, _ = _spy(core_result)
    use_case = GenerateLiveZoneSplitBets(generator)

    result = use_case.execute(GenerateLiveZoneSplitBetsInput(num_bets=1))

    assert result.status is GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT
    assert result.reason_code is GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT


# --- 13. result-model OK/failure invariants are mutation-sensitive ---------

_VALID_PAYLOAD: dict[str, object] = {
    "bets": ((1, 2, 3, 4, 5, 6),),
    "coverage_rate": 0.1224,
    "total_unique_numbers": 6,
    "method": "m",
    "philosophy": "p",
}


@pytest.mark.parametrize("missing_field", sorted(_VALID_PAYLOAD))
def test_ok_result_requires_every_payload_field(missing_field: str) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload[missing_field] = None
    with pytest.raises(ValueError):
        GenerateLiveZoneSplitBetsResult(
            status=GenerateLiveZoneSplitBetsStatus.OK,
            reason_code=None,
            **payload,  # type: ignore[arg-type]
        )


def test_ok_result_rejects_reason_code() -> None:
    with pytest.raises(ValueError):
        GenerateLiveZoneSplitBetsResult(
            status=GenerateLiveZoneSplitBetsStatus.OK,
            reason_code=GenerateLiveZoneSplitBetsReason.EXECUTION_ERROR,
            **_VALID_PAYLOAD,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("present_field", sorted(_VALID_PAYLOAD))
def test_failure_result_rejects_any_payload_field(present_field: str) -> None:
    payload: dict[str, object] = {key: None for key in _VALID_PAYLOAD}
    payload[present_field] = _VALID_PAYLOAD[present_field]
    with pytest.raises(ValueError):
        GenerateLiveZoneSplitBetsResult(
            status=GenerateLiveZoneSplitBetsStatus.INVALID_REQUEST,
            reason_code=GenerateLiveZoneSplitBetsReason.INVALID_NUM_BETS,
            **payload,  # type: ignore[arg-type]
        )


def test_failure_result_requires_reason_code() -> None:
    with pytest.raises(ValueError):
        GenerateLiveZoneSplitBetsResult(
            status=GenerateLiveZoneSplitBetsStatus.INVALID_REQUEST,
            reason_code=None,
            bets=None,
            coverage_rate=None,
            total_unique_numbers=None,
            method=None,
            philosophy=None,
        )


def test_result_invariants_allow_valid_direct_construction() -> None:
    ok = GenerateLiveZoneSplitBetsResult(
        status=GenerateLiveZoneSplitBetsStatus.OK,
        reason_code=None,
        **_VALID_PAYLOAD,  # type: ignore[arg-type]
    )
    failure = GenerateLiveZoneSplitBetsResult(
        status=GenerateLiveZoneSplitBetsStatus.INVALID_REQUEST,
        reason_code=GenerateLiveZoneSplitBetsReason.INVALID_NUM_BETS,
        bets=None,
        coverage_rate=None,
        total_unique_numbers=None,
        method=None,
        philosophy=None,
    )

    assert ok.bets == _VALID_PAYLOAD["bets"]
    assert ok.reason_code is None
    assert failure.bets is None
    assert failure.reason_code is GenerateLiveZoneSplitBetsReason.INVALID_NUM_BETS


def test_input_and_result_models_are_frozen() -> None:
    request = GenerateLiveZoneSplitBetsInput(num_bets=1)
    result = GenerateLiveZoneSplitBetsResult(
        status=GenerateLiveZoneSplitBetsStatus.OK,
        reason_code=None,
        **_VALID_PAYLOAD,  # type: ignore[arg-type]
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        request.num_bets = 2  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.bets = None  # type: ignore[misc]


# --- 14. input/execute surfaces expose no forbidden fields ------------------


def test_input_and_execute_surfaces_expose_no_forbidden_fields() -> None:
    forbidden = {"history", "seed", "strategy_id", "lottery_type", "sampler"}

    input_fields = {field.name for field in dataclasses.fields(GenerateLiveZoneSplitBetsInput)}
    assert input_fields == {"num_bets"}
    assert input_fields.isdisjoint(forbidden)

    execute_params = set(inspect.signature(GenerateLiveZoneSplitBets.execute).parameters) - {
        "self"
    }
    assert execute_params == {"request"}


# --- 16. production catalog remains exactly the existing three IDs ---------


def test_production_catalog_still_has_exactly_three_executable_strategies() -> None:
    online = production_catalog().list(lifecycle_status=LifecycleStatus.ONLINE)
    assert len(online) == 3
