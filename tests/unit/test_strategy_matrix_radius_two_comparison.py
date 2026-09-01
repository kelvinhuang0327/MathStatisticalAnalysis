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
    EXPECTED_SOURCE_Q,
    OUTPUT_PATH,
    SOURCE_AUTHORITY_SHA256,
    STUDY_ID,
    SUPPORTED_K_VALUES,
    TASK_ID,
    canonical_json_bytes,
    load_radius_one_certificate,
    portfolio_sha256,
    result_payload_sha256,
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


def test_canonical_json_is_independent_of_mapping_insertion_order() -> None:
    first = canonical_json_bytes({"z": [2, 1], "a": {"b": True}})
    second = canonical_json_bytes({"a": {"b": True}, "z": [2, 1]})

    assert first == second
    assert first.endswith(b"\n")
