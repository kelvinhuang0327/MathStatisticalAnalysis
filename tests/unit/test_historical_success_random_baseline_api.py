"""HTTP contract for the exact official-six-number random-null baseline."""

# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownParameterType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from tests.fixtures.historical.success_window_builder import (
    build_success_observations,
    build_success_source,
    build_success_strategy,
)

from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessCriterion,
    HistoricalPrefixSuccessImportNotFoundError,
    HistoricalPrefixSuccessSourceObservation,
    HistoricalPrefixSuccessStrategyNotFoundError,
    HistoricalPrefixSuccessWindowSource,
)
from lottolab.application.historical_success_random_baseline import (
    INTERPRETATION_CAVEAT,
    LEGAL_TICKET_COUNT,
    NOMINAL_TICKET_COUNT_EQUIVALENT,
    RANDOM_BASELINE_POLICY_VERSION,
    HistoricalSuccessRandomBaselineCellIdentity,
    HistoricalSuccessRandomBaselineNotReadyReason,
    HistoricalSuccessRandomBaselineReadiness,
    HistoricalSuccessRandomBaselineResult,
    HistoricalSuccessRandomBaselineSamplingPolicy,
    portfolio_success_probability,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)
from lottolab.domain.strategy_success_evaluation import WindowKind
from lottolab.domain.strategy_success_measurement import DEFAULT_WINDOW_POLICY_VERSION
from lottolab.interfaces.api.app import create_app
from lottolab.interfaces.api.historical_prefix_success_windows import (
    HistoricalSuccessRandomBaselineResponse,
)

IMPORT_IDENTITY = "a" * 64
OPENAPI_PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "{strategy_id}/{strategy_version}/{replicate}/random-null-baseline"
)
PATH = (
    "/api/v1/historical-prefix-success-windows/strategies/"
    "strategy-a/v1/1/random-null-baseline"
)
QUERY = (
    f"?import_identity_sha256={IMPORT_IDENTITY}"
    "&prefix_count=1&criterion=M3_PLUS&window_kind=FULL_HISTORY"
)


class _Reader:
    def __init__(self, source: HistoricalPrefixSuccessWindowSource | None) -> None:
        self.source = source
        self.calls = 0

    def load_source(
        self, import_identity_sha256: str
    ) -> HistoricalPrefixSuccessWindowSource | None:
        assert import_identity_sha256 == IMPORT_IDENTITY
        self.calls += 1
        return self.source


class _Factory:
    def __init__(self, source: HistoricalPrefixSuccessWindowSource | None) -> None:
        self.reader = _Reader(source)
        self.calls = 0

    def __call__(self) -> _Reader:
        self.calls += 1
        return self.reader


def _raw_ticket_numbers(main_hits: int) -> tuple[int, ...]:
    values = list(range(1, main_hits + 1))
    filler = 8
    while len(values) < 6:
        values.append(filler)
        filler += 1
    return tuple(values)


def _with_raw_operands(
    observations: tuple[HistoricalPrefixSuccessSourceObservation, ...],
) -> tuple[HistoricalPrefixSuccessSourceObservation, ...]:
    return tuple(
        dataclasses.replace(
            observation,
            target_main_numbers=(1, 2, 3, 4, 5, 6),
            target_special_number=7,
            tickets=tuple(
                dataclasses.replace(
                    ticket,
                    main_numbers=_raw_ticket_numbers(ticket.main_hit_count),
                )
                for ticket in observation.tickets
            ),
        )
        for observation in observations
    )


def _source(
    observations: tuple[HistoricalPrefixSuccessSourceObservation, ...],
    *,
    strategy_id: str = "strategy-a",
) -> HistoricalPrefixSuccessWindowSource:
    return build_success_source(
        (
            build_success_strategy(
                strategy_id,
                observations=observations,
            ),
        )
    )


def _cell() -> HistoricalSuccessRandomBaselineCellIdentity:
    return HistoricalSuccessRandomBaselineCellIdentity(
        policy_version=RANDOM_BASELINE_POLICY_VERSION,
        import_identity_sha256=IMPORT_IDENTITY,
        dataset_sha256="e" * 64,
        source_artifact_sha256="d" * 64,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        window_kind=WindowKind.FULL_HISTORY,
        window_policy_version=DEFAULT_WINDOW_POLICY_VERSION,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )


def _not_ready(
    reason: HistoricalSuccessRandomBaselineNotReadyReason,
) -> HistoricalSuccessRandomBaselineResult:
    probability = portfolio_success_probability(
        HistoricalPrefixSuccessCriterion.M3_PLUS,
        1,
    )
    return HistoricalSuccessRandomBaselineResult(
        cell=_cell(),
        readiness=HistoricalSuccessRandomBaselineReadiness.NOT_READY,
        reason_codes=(reason,),
        sampling_policy=(
            HistoricalSuccessRandomBaselineSamplingPolicy
            .UNIFORM_IID_LEGAL_TICKETS_WITH_REPLACEMENT
        ),
        ticket_count_interpretation=NOMINAL_TICKET_COUNT_EQUIVALENT,
        legal_ticket_count=LEGAL_TICKET_COUNT,
        success_ticket_count=260_624,
        portfolio_success_probability=probability,
        eligible_observation_count=0,
        excluded_observation_count=0,
        observed_success_count=None,
        expected_successes=None,
        upper_tail_probability=None,
        observed_ticket_position_count=0,
        observed_distinct_ticket_count=0,
        observed_duplicate_ticket_count=0,
        observation_count_with_duplicates=0,
        interpretation_caveat=INTERPRETATION_CAVEAT,
    )


def _patch_result(
    monkeypatch: pytest.MonkeyPatch,
    result_or_error: HistoricalSuccessRandomBaselineResult | Exception,
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def operation(
        _self: EvaluateHistoricalPrefixSuccessWindows,
        **kwargs: object,
    ) -> HistoricalSuccessRandomBaselineResult:
        calls.append(kwargs)
        if isinstance(result_or_error, Exception):
            raise result_or_error
        return result_or_error

    monkeypatch.setattr(
        EvaluateHistoricalPrefixSuccessWindows,
        "get_random_null_baseline",
        operation,
    )
    return calls


def test_route_is_get_only_exact_and_serializes_authoritative_integers_as_strings() -> None:
    observations = _with_raw_operands(
        build_success_observations(
            1,
            outcome_factory=lambda _observation, position: (
                (3, False) if position == 1 else (0, False)
            ),
        )
    )
    factory = _Factory(_source(observations))
    app = create_app(historical_prefix_success_window_source_reader_factory=factory)
    operation = app.openapi()["paths"][OPENAPI_PATH]["get"]

    assert operation["operationId"] == "getHistoricalPrefixStrategyRandomNullBaseline"
    assert {
        (parameter["in"], parameter["name"], parameter["required"])
        for parameter in operation["parameters"]
    } == {
        ("path", "strategy_id", True),
        ("path", "strategy_version", True),
        ("path", "replicate", True),
        ("query", "import_identity_sha256", True),
        ("query", "prefix_count", True),
        ("query", "criterion", True),
        ("query", "window_kind", True),
    }
    assert factory.calls == 0
    client = TestClient(app)

    response = client.get(f"{PATH}{QUERY}")

    assert response.status_code == 200
    assert factory.calls == factory.reader.calls == 1
    payload = cast(dict[str, Any], response.json())
    assert payload["cell"] == {
        "policy_version": RANDOM_BASELINE_POLICY_VERSION,
        "import_identity_sha256": IMPORT_IDENTITY,
        "dataset_sha256": "e" * 64,
        "source_artifact_sha256": "d" * 64,
        "strategy_id": "strategy-a",
        "strategy_version": "v1",
        "replicate": 1,
        "window_kind": "FULL_HISTORY",
        "window_policy_version": DEFAULT_WINDOW_POLICY_VERSION,
        "prefix_count": 1,
        "criterion": "M3_PLUS",
    }
    assert payload["readiness"] == "READY"
    assert payload["reason_codes"] == []
    assert payload["observed_success_count"] == 1
    assert isinstance(payload["legal_ticket_count"], str)
    assert isinstance(payload["success_ticket_count"], str)
    for field in (
        "portfolio_success_probability",
        "expected_successes",
        "upper_tail_probability",
    ):
        assert isinstance(payload[field]["numerator"], str)
        assert isinstance(payload[field]["denominator"], str)
        assert len(payload[field]["decimal_18"].split(".")[1]) == 18
    assert client.post(f"{PATH}{QUERY}").status_code == 405


def test_route_forwards_the_exact_application_arguments_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_result(
        monkeypatch,
        _not_ready(HistoricalSuccessRandomBaselineNotReadyReason.NO_OBSERVATIONS),
    )
    factory = _Factory(None)
    client = TestClient(
        create_app(historical_prefix_success_window_source_reader_factory=factory)
    )

    response = client.get(f"{PATH}{QUERY}")

    assert response.status_code == 200
    assert calls == [
        {
            "import_identity_sha256": IMPORT_IDENTITY,
            "strategy_id": "strategy-a",
            "strategy_version": "v1",
            "replicate": 1,
            "window_kind": WindowKind.FULL_HISTORY,
            "prefix_count": 1,
            "criterion": HistoricalPrefixSuccessCriterion.M3_PLUS,
        }
    ]
    assert factory.calls == factory.reader.calls == 0


@pytest.mark.parametrize(
    "reason",
    tuple(HistoricalSuccessRandomBaselineNotReadyReason),
)
def test_every_not_ready_reason_is_closed_and_hides_result_fields(
    monkeypatch: pytest.MonkeyPatch,
    reason: HistoricalSuccessRandomBaselineNotReadyReason,
) -> None:
    _patch_result(monkeypatch, _not_ready(reason))
    response = TestClient(
        create_app(historical_prefix_success_window_source_reader_factory=_Factory(None))
    ).get(f"{PATH}{QUERY}")

    assert response.status_code == 200
    assert response.json()["readiness"] == "NOT_READY"
    assert response.json()["reason_codes"] == [reason.value]
    assert response.json()["observed_success_count"] is None
    assert response.json()["expected_successes"] is None
    assert response.json()["upper_tail_probability"] is None


def test_validation_and_unknown_query_parameters_precede_application_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_result(
        monkeypatch,
        _not_ready(HistoricalSuccessRandomBaselineNotReadyReason.NO_OBSERVATIONS),
    )
    client = TestClient(
        create_app(historical_prefix_success_window_source_reader_factory=_Factory(None))
    )
    invalid_urls = (
        f"{PATH}?import_identity_sha256=BAD&prefix_count=1"
        "&criterion=M3_PLUS&window_kind=LONG",
        f"{PATH}?import_identity_sha256={IMPORT_IDENTITY}&prefix_count=6"
        "&criterion=M3_PLUS&window_kind=LONG",
        f"{PATH}?import_identity_sha256={IMPORT_IDENTITY}&prefix_count=1"
        "&criterion=BAD&window_kind=LONG",
        f"{PATH}?import_identity_sha256={IMPORT_IDENTITY}&prefix_count=1"
        "&criterion=M3_PLUS&window_kind=BAD",
        f"{PATH}{QUERY}&limit=1",
    )

    assert [client.get(url).status_code for url in invalid_urls] == [422] * len(invalid_urls)
    assert calls == []


@pytest.mark.parametrize(
    ("failure", "status"),
    (
        (HistoricalPrefixSuccessImportNotFoundError(), 404),
        (HistoricalPrefixSuccessStrategyNotFoundError(), 404),
        (RuntimeError("internal detail must be sanitized"), 503),
    ),
)
def test_application_failures_keep_existing_sanitized_mapping(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    status: int,
) -> None:
    _patch_result(monkeypatch, failure)
    response = TestClient(
        create_app(historical_prefix_success_window_source_reader_factory=_Factory(None))
    ).get(f"{PATH}{QUERY}")

    assert response.status_code == status
    assert "internal detail" not in response.text


def test_absent_evaluator_is_not_configured() -> None:
    response = TestClient(create_app()).get(f"{PATH}{QUERY}")

    assert response.status_code == 503
    assert response.json()["error_code"] == (
        "HISTORICAL_PREFIX_SUCCESS_WINDOWS_NOT_CONFIGURED"
    )


def test_response_model_rejects_extra_malformed_exact_and_readiness_mutations() -> None:
    observations = _with_raw_operands(
        build_success_observations(
            1,
            outcome_factory=lambda _observation, position: (
                (3, False) if position == 1 else (0, False)
            ),
        )
    )
    payload = cast(
        dict[str, Any],
        TestClient(
            create_app(
                historical_prefix_success_window_source_reader_factory=(
                    _Factory(_source(observations))
                )
            )
        )
        .get(f"{PATH}{QUERY}")
        .json(),
    )

    mutations: list[Callable[[dict[str, Any]], None]] = [
        lambda value: value.__setitem__("unexpected", True),
        lambda value: value["portfolio_success_probability"].__setitem__("numerator", 1),
        lambda value: value["portfolio_success_probability"].__setitem__("denominator", "0"),
        lambda value: value["portfolio_success_probability"].update(
            numerator="2",
            denominator="4",
        ),
        lambda value: value["portfolio_success_probability"].__setitem__(
            "decimal_18", "0.1"
        ),
        lambda value: value["portfolio_success_probability"].__setitem__(
            "decimal_18", "0.000000000000000000"
        ),
        lambda value: value.__setitem__("readiness", "UNKNOWN"),
        lambda value: value.__setitem__("reason_codes", ["UNKNOWN"]),
        lambda value: value.__setitem__("sampling_policy", "UNKNOWN"),
        lambda value: value["cell"].__setitem__("window_kind", "UNKNOWN"),
        lambda value: value.__setitem__("expected_successes", None),
    ]
    for mutate in mutations:
        changed = copy.deepcopy(payload)
        mutate(changed)
        with pytest.raises(ValidationError):
            HistoricalSuccessRandomBaselineResponse.model_validate(changed)

    not_ready = HistoricalSuccessRandomBaselineResponse.from_result(
        _not_ready(HistoricalSuccessRandomBaselineNotReadyReason.NO_OBSERVATIONS)
    ).model_dump(mode="json")
    not_ready["observed_success_count"] = 0
    with pytest.raises(ValidationError):
        HistoricalSuccessRandomBaselineResponse.model_validate(not_ready)


def test_response_model_rejects_identity_and_exact_count_contradictions() -> None:
    payload = HistoricalSuccessRandomBaselineResponse.from_result(
        _not_ready(HistoricalSuccessRandomBaselineNotReadyReason.NO_OBSERVATIONS)
    ).model_dump(mode="json")

    for path, value in (
        (("cell", "import_identity_sha256"), "BAD"),
        (("cell", "prefix_count"), 2),
        (("legal_ticket_count",), "1"),
        (("success_ticket_count",), "1"),
    ):
        changed = copy.deepcopy(payload)
        target = changed
        for part in path[:-1]:
            target = cast(dict[str, Any], target[part])
        target[path[-1]] = value
        with pytest.raises(ValidationError):
            HistoricalSuccessRandomBaselineResponse.model_validate(changed)
