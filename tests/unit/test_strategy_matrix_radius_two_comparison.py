"""Focused registration and evidence checks for the radius-two Matrix slice."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from typing import Any, cast

import pytest

from lottolab.research.exact_radius_two_local_escape import PackedWinningSpace
from lottolab.research.reference_e_exact_one_exchange_refinement import Portfolio
from lottolab.research.strategy_matrix_local_escape import (
    RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID,
    RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID,
    evaluate_registered_local_escape,
    local_escape_method_registration,
    registered_local_escape_methods,
)
from lottolab.research.strategy_matrix_radius_two_comparison import (
    EVALUATED_K_VALUES,
    EXPECTED_SOURCE_PORTFOLIO_SHA256,
    EXPECTED_SOURCE_PORTFOLIO_SHA256_BY_K,
    EXPECTED_SOURCE_Q,
    EXPECTED_SOURCE_Q_BY_K,
    OUTPUT_PATH,
    OUTPUT_RESULT_IDENTITY_SHA256,
    OUTPUT_SHA256,
    SOURCE_AUTHORITY_SHA256,
    STUDY_ID,
    SUPPORTED_K_EXECUTED_VALUES,
    SUPPORTED_K_OUTPUT_PATH,
    SUPPORTED_K_RESULT_IDENTITY_SHA256,
    SUPPORTED_K_REUSED_VALUES,
    SUPPORTED_K_STUDY_ID,
    SUPPORTED_K_TASK_ID,
    SUPPORTED_K_VALUES,
    TASK_ID,
    canonical_json_bytes,
    load_radius_one_certificate,
    load_reused_k20_row,
    portfolio_sha256,
    result_payload_sha256,
    supported_k_result_payload_sha256,
    validate_supported_k_output,
)


def _mapping(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _rows(value: object) -> list[dict[str, Any]]:
    assert isinstance(value, list)
    rows = cast(list[object], value)
    assert all(isinstance(row, dict) for row in rows)
    return [cast(dict[str, Any], row) for row in rows]


def _fraction(value: object) -> Fraction:
    mapping = _mapping(value)
    numerator = mapping.get("numerator")
    denominator = mapping.get("denominator")
    assert type(numerator) is int
    assert type(denominator) is int
    result = Fraction(numerator, denominator)
    assert mapping.get("exact") == f"{result.numerator}/{result.denominator}"
    return result


def _portfolio(value: object) -> Portfolio:
    assert isinstance(value, list)
    tickets: list[tuple[int, ...]] = []
    for raw_ticket in cast(list[object], value):
        assert isinstance(raw_ticket, list)
        raw_numbers = cast(list[object], raw_ticket)
        assert all(type(number) is int for number in raw_numbers)
        tickets.append(tuple(cast(list[int], raw_numbers)))
    return tuple(tickets)


def test_registry_distinguishes_exact_one_and_two_exchange_methods() -> None:
    registrations = registered_local_escape_methods()

    assert tuple(registration.method_id for registration in registrations) == (
        RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID,
        RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID,
    )
    assert tuple(registration.exchange_radius for registration in registrations) == (1, 2)
    assert registrations[0].exchange_semantics == "EXACT_ONE_NUMBER_EXCHANGE"
    assert registrations[1].exchange_semantics == (
        "EXACT_TWO_ONE_NUMBER_EXCHANGE_ENDPOINT"
    )
    assert all(
        registration.objective_id == "EXACT_M3_PLUS_FRACTION"
        and registration.global_optimum_status == "UNKNOWN"
        for registration in registrations
    )
    assert registrations[0].implementation_path.endswith(
        "reference_e_iterative_exact_one_exchange_ascent.py"
    )
    assert registrations[1].implementation_path.endswith(
        "exact_radius_two_local_escape.py"
    )


def test_registered_dispatch_preserves_both_exact_methods_on_small_space() -> None:
    seed: Portfolio = (
        (1, 2, 3, 4),
        (1, 2, 3, 5),
        (1, 2, 3, 6),
    )

    radius_one = evaluate_registered_local_escape(
        RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID,
        pool_size=8,
        draw_size=4,
        minimum_matches=3,
        seed_portfolio=seed,
    )
    radius_two = evaluate_registered_local_escape(
        RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID,
        pool_size=8,
        draw_size=4,
        minimum_matches=3,
        seed_portfolio=seed,
    )
    radius_two_repeat = evaluate_registered_local_escape(
        RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID,
        pool_size=8,
        draw_size=4,
        minimum_matches=3,
        seed_portfolio=seed,
    )

    assert radius_one.registration.exchange_radius == 1
    assert radius_two.registration.exchange_radius == 2
    assert radius_two_repeat == radius_two
    assert radius_one.seed_q == radius_two.seed_q == Fraction(16, 35)
    assert radius_one.terminal_q == radius_two.terminal_q == Fraction(47, 70)
    assert radius_one.move_count == 3
    assert radius_two.move_count == 2
    assert radius_one.unique_endpoints_evaluated == 182
    assert radius_two.unique_endpoints_evaluated == 2443
    assert radius_one.iterations[-1].accepted_move is False
    assert radius_two.iterations[-1].accepted_move is False
    assert all(
        iteration.single_replacement_endpoint_count is None
        and iteration.two_replacement_endpoint_count is None
        for iteration in radius_one.iterations
    )
    assert all(
        iteration.unique_endpoint_count
        == iteration.single_replacement_endpoint_count
        + iteration.two_replacement_endpoint_count
        for iteration in radius_two.iterations
        if iteration.single_replacement_endpoint_count is not None
        and iteration.two_replacement_endpoint_count is not None
    )


def test_registry_rejects_unknown_method_and_non_m3_objective() -> None:
    seed: Portfolio = ((1, 2, 3, 4),)

    with pytest.raises(ValueError, match="unregistered Strategy Matrix"):
        local_escape_method_registration("EXACT_RADIUS_N_NOT_REGISTERED")
    with pytest.raises(ValueError, match="frozen to exact M3_PLUS"):
        evaluate_registered_local_escape(
            RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID,
            pool_size=8,
            draw_size=4,
            minimum_matches=2,
            seed_portfolio=seed,
        )


def test_selected_radius_one_source_certificate_is_identity_pinned() -> None:
    certificate = load_radius_one_certificate()

    assert certificate.method_id == RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID
    assert certificate.structure_id == "POWER_LOTTO_ZONE1"
    assert certificate.k == 20
    assert certificate.portfolio_sha256 == EXPECTED_SOURCE_PORTFOLIO_SHA256
    assert portfolio_sha256(certificate.portfolio) == EXPECTED_SOURCE_PORTFOLIO_SHA256
    assert certificate.exact_q == EXPECTED_SOURCE_Q


@pytest.mark.parametrize("k", SUPPORTED_K_VALUES)
def test_each_supported_radius_one_source_certificate_is_identity_pinned(k: int) -> None:
    certificate = load_radius_one_certificate(k)

    assert certificate.k == k
    assert certificate.portfolio_sha256 == EXPECTED_SOURCE_PORTFOLIO_SHA256_BY_K[k]
    assert portfolio_sha256(certificate.portfolio) == (
        EXPECTED_SOURCE_PORTFOLIO_SHA256_BY_K[k]
    )
    assert certificate.exact_q == EXPECTED_SOURCE_Q_BY_K[k]


def test_radius_one_source_rejects_unregistered_k() -> None:
    with pytest.raises(ValueError, match="unsupported source radius-one k"):
        load_radius_one_certificate(5)


def test_k20_reuse_authority_is_exactly_pinned_without_execution() -> None:
    raw = OUTPUT_PATH.read_bytes()
    payload = _mapping(json.loads(raw))
    row = load_reused_k20_row()

    assert hashlib.sha256(raw).hexdigest() == OUTPUT_SHA256
    assert _mapping(payload["result_identity"])["sha256"] == (
        OUTPUT_RESULT_IDENTITY_SHA256
    )
    assert result_payload_sha256(payload) == OUTPUT_RESULT_IDENTITY_SHA256
    assert row["k"] == 20
    assert row["evidence_origin"] == "REUSED_CANONICAL_K20_RESULT"
    assert _fraction(row["exact_delta"]) == Fraction(5, 20757)
    assert row["radius2_move_count"] == 10
    assert row["unique_radius2_endpoints_evaluated"] == 78_724_800


def test_materialized_comparison_is_canonical_exact_and_identity_bound() -> None:
    assert OUTPUT_PATH.is_file(), "the required Matrix comparison result is not materialized"
    raw = OUTPUT_PATH.read_bytes()
    payload = _mapping(json.loads(raw))

    assert canonical_json_bytes(payload) == raw
    assert payload["study_id"] == STUDY_ID
    assert payload["task_id"] == TASK_ID
    assert result_payload_sha256(payload) == _mapping(payload["result_identity"])["sha256"]
    assert _mapping(payload["source_authority"])["sha256"] == SOURCE_AUTHORITY_SHA256

    contract = _mapping(payload["comparison_contract"])
    assert contract["supported_k_values"] == list(SUPPORTED_K_VALUES)
    assert contract["evaluated_k_values"] == list(EVALUATED_K_VALUES)
    assert contract["source_method_id"] == RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID
    assert contract["candidate_method_id"] == RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID

    registrations = _rows(payload["matrix_method_registration"])
    assert [(row["method_id"], row["exchange_radius"]) for row in registrations] == [
        (RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID, 1),
        (RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID, 2),
    ]

    rows = _rows(payload["rows"])
    assert len(rows) == 1
    row = rows[0]
    source_portfolio = _portfolio(row["source_reference_portfolio"])
    best_portfolio = _portfolio(row["best_radius2_portfolio"])
    input_q = _fraction(row["input_exact_objective"])
    best_q = _fraction(row["best_exact_radius2_objective"])
    delta = _fraction(row["exact_delta"])
    assert portfolio_sha256(source_portfolio) == EXPECTED_SOURCE_PORTFOLIO_SHA256
    assert portfolio_sha256(best_portfolio) == row["best_radius2_portfolio_sha256"]
    assert input_q == EXPECTED_SOURCE_Q
    assert delta == best_q - input_q
    assert row["accepted"] is (delta > 0)
    assert row["outcome_classification"] == (
        "RADIUS2_STRICT_IMPROVEMENT" if delta > 0 else "RADIUS2_NO_IMPROVEMENT"
    )
    assert row["global_optimum_status"] == "UNKNOWN"

    space = PackedWinningSpace.build(38, 6)
    assert space.exact_portfolio_q(source_portfolio) == input_q
    assert space.exact_portfolio_q(best_portfolio) == best_q

    certificate = _mapping(row["certificate"])
    certificate_identity = _mapping(certificate["certificate_identity"])
    certificate_body = dict(certificate)
    certificate_body.pop("certificate_identity")
    assert hashlib.sha256(canonical_json_bytes(certificate_body)).hexdigest() == (
        certificate_identity["sha256"]
    )
    trace = _rows(certificate["trace"])
    assert trace
    assert certificate["unique_endpoints_evaluated"] == sum(
        cast(int, iteration["unique_endpoint_count"]) for iteration in trace
    )
    assert trace[-1]["accepted_move"] is False
    assert _fraction(trace[-1]["best_endpoint_exact_q"]) <= _fraction(
        trace[-1]["input_exact_q"]
    )
    for iteration in trace:
        assert iteration["unique_endpoint_count"] == (
            cast(int, iteration["single_replacement_endpoint_count"])
            + cast(int, iteration["two_replacement_endpoint_count"])
        )

    summary = _mapping(payload["summary"])
    assert summary["evaluated_row_count"] == 1
    assert summary["radius2_strict_improvement_count"] == int(delta > 0)
    assert summary["radius2_no_improvement_count"] == int(delta <= 0)
    assert _fraction(summary["best_observed_delta"]) == delta


def test_materialized_supported_k_comparison_is_exact_typed_and_identity_bound() -> None:
    assert SUPPORTED_K_OUTPUT_PATH.is_file(), "supported-k result is not materialized"
    raw = SUPPORTED_K_OUTPUT_PATH.read_bytes()
    payload = validate_supported_k_output()

    assert canonical_json_bytes(payload) == raw
    assert payload["study_id"] == SUPPORTED_K_STUDY_ID
    assert payload["task_id"] == SUPPORTED_K_TASK_ID
    assert supported_k_result_payload_sha256(payload) == _mapping(
        payload["result_identity"]
    )["sha256"]
    assert _mapping(payload["result_identity"])["sha256"] == (
        SUPPORTED_K_RESULT_IDENTITY_SHA256
    )

    contract = _mapping(payload["comparison_contract"])
    assert contract["supported_k_values"] == list(SUPPORTED_K_VALUES)
    assert contract["combined_k_values"] == list(SUPPORTED_K_VALUES)
    assert contract["executed_exact_k_values"] == list(SUPPORTED_K_EXECUTED_VALUES)
    assert contract["reused_exact_k_values"] == list(SUPPORTED_K_REUSED_VALUES)
    assert contract["source_method_id"] == RADIUS_ONE_EXACT_ONE_EXCHANGE_METHOD_ID
    assert contract["candidate_method_id"] == RADIUS_TWO_EXACT_TWO_EXCHANGE_METHOD_ID

    rows = _rows(payload["rows"])
    assert [row["k"] for row in rows] == list(SUPPORTED_K_VALUES)
    assert rows[-1] == load_reused_k20_row()
    expected_rows = {
        10: {
            "certificate_sha256": (
                "55397812ac0f6fa98222b5f2aa59f0d2af3c9f03e7978bdb27cf32079e2df4f8"
            ),
            "delta": Fraction(310, 2_760_681),
            "endpoint_count": 3_470_400,
            "iteration_count": 2,
            "move_count": 1,
            "row_sha256": (
                "c8910359db896e3f70d9ad5c9d106f079aef15e550e745ea1a6d617b2dffbfda"
            ),
            "terminal_q": Fraction(90485, 250971),
        },
        15: {
            "certificate_sha256": (
                "81968eb01312219846eb4dc38965a436f0c8aa93e8f5f5439aaa91d36090fae0"
            ),
            "delta": Fraction(39, 920227),
            "endpoint_count": 7_970_400,
            "iteration_count": 2,
            "move_count": 1,
            "row_sha256": (
                "1e66512978fbcf1ada122f41aef0040604fa93657c925661968beb141d933728"
            ),
            "terminal_q": Fraction(465491, 920227),
        },
        20: {
            "certificate_sha256": (
                "0328162a8da6d6a1b511a35837e753d2a75aceebe5a432375fa839d711fe367d"
            ),
            "delta": Fraction(5, 20757),
            "endpoint_count": 78_724_800,
            "iteration_count": 11,
            "move_count": 10,
            "row_sha256": (
                "52c502a7bfb82f2d043199b71a2974da40c0d669cc8a005b9f98169984955492"
            ),
            "terminal_q": Fraction(579401, 920227),
        },
    }
    for row in rows:
        k = cast(int, row["k"])
        expected = expected_rows[k]
        certificate = _mapping(row["certificate"])
        trace = _rows(certificate["trace"])
        row_identity = _mapping(row["row_result_identity"])
        row_body = dict(row)
        row_body.pop("row_result_identity")

        assert row_identity["sha256"] == hashlib.sha256(
            canonical_json_bytes(row_body)
        ).hexdigest()
        assert row_identity["sha256"] == expected["row_sha256"]
        assert _mapping(certificate["certificate_identity"])["sha256"] == expected[
            "certificate_sha256"
        ]
        assert _fraction(row["best_exact_radius2_objective"]) == expected["terminal_q"]
        assert _fraction(row["exact_delta"]) == expected["delta"]
        assert trace[-1]["accepted_move"] is False
        assert row["terminal_best_endpoint"] == {
            "exact_q": trace[-1]["best_endpoint_exact_q"],
            "portfolio": trace[-1]["best_endpoint_portfolio"],
            "portfolio_sha256": trace[-1]["best_endpoint_portfolio_sha256"],
        }
        assert row["terminal_delta"] == trace[-1]["delta"]
        assert row["radius2_iteration_count"] == len(trace) == expected["iteration_count"]
        assert row["radius2_move_count"] == expected["move_count"] == sum(
            iteration["accepted_move"] is True for iteration in trace
        )
        assert row["unique_radius2_endpoints_evaluated"] == expected[
            "endpoint_count"
        ] == sum(cast(int, iteration["unique_endpoint_count"]) for iteration in trace)
        assert _fraction(row["input_exact_objective"]) == EXPECTED_SOURCE_Q_BY_K[k]
        assert row["global_optimum_status"] == "UNKNOWN"

    summary = _mapping(payload["summary"])
    result_by_k = _mapping(summary["result_by_k"])
    assert set(result_by_k) == {"10", "15", "20"}
    assert summary["strict_improvement_k_count"] == 3
    assert summary["no_improvement_k_count"] == 0
    assert summary["resource_bound_k_count"] == 0
    assert summary["family_cross_k_classification"] == "CROSS_K_STRONG"
    assert _mapping(payload["gate"])["predictive_success_claims"] == "NONE"

    metrics = _mapping(_mapping(payload["execution_metrics"])["by_k"])
    for k in SUPPORTED_K_EXECUTED_VALUES:
        row_metrics = _mapping(metrics[str(k)])
        assert cast(float, row_metrics["runtime_seconds"]) > 0
        assert cast(int, row_metrics["peak_memory_bytes"]) > 0
    assert _mapping(metrics["20"])["runtime_seconds"] is None
    assert _mapping(metrics["20"])["peak_memory_bytes"] is None


def test_canonical_json_is_independent_of_mapping_insertion_order() -> None:
    first = canonical_json_bytes({"z": [2, 1], "a": {"b": True}})
    second = canonical_json_bytes({"a": {"b": True}, "z": [2, 1]})

    assert first == second
    assert first.endswith(b"\n")
