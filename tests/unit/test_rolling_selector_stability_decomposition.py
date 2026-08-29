"""Focused checks for the sealed rolling-selector stability decomposition."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from tools import analyze_rolling_selector_stability_decomposition as decomposition


def _delta(numerator: int, denominator: int = 1, *, decimal_12: str = "IGNORED") -> dict[str, Any]:
    return {
        "decimal_12": decimal_12,
        "denominator": denominator,
        "exact": f"{numerator}/{denominator}",
        "numerator": numerator,
    }


def _experiment(
    label: str,
    window: int,
    numerator: int | None,
    *,
    switch_count: int,
    dominant_strategy: str = "strategy_a",
    secondary_strategy: str | None = None,
) -> dict[str, Any]:
    if numerator is None:
        return {
            "absolute_paired_delta": None,
            "conclusion": "INCONCLUSIVE_FIXTURE",
            "frozen_baseline_strategy": None,
            "label": label,
            "rolling_selection_frequency": {},
            "rolling_selector_primary_metric_result": None,
            "rolling_strategy_switch_count": switch_count,
            "status": "EXCLUDED",
            "window": window,
        }
    frequencies = {dominant_strategy: 7}
    if secondary_strategy is not None:
        frequencies[secondary_strategy] = 3
    return {
        "absolute_paired_delta": _delta(numerator),
        "conclusion": "COMPLETE_FIXTURE",
        "frozen_baseline_strategy": "frozen_strategy",
        "label": label,
        "rolling_selection_frequency": frequencies,
        "rolling_selector_primary_metric_result": {"target_count": sum(frequencies.values())},
        "rolling_strategy_switch_count": switch_count,
        "status": "COMPLETE",
        "window": window,
    }


def _cell(
    lottery_id: str,
    k: int,
    signs: tuple[int | None, int | None, int | None],
    *,
    switches: tuple[int, int, int] = (1, 1, 1),
    dominant_strategies: tuple[str, str, str] = ("strategy_a", "strategy_a", "strategy_a"),
) -> dict[str, Any]:
    return {
        "cell_id": f"{lottery_id}:K{k}",
        "experiments": {
            source_label: _experiment(
                source_label,
                window,
                sign,
                switch_count=switch_count,
                dominant_strategy=dominant_strategy,
            )
            for (_, source_label, window), sign, switch_count, dominant_strategy in zip(
                decomposition.WINDOWS,
                signs,
                switches,
                dominant_strategies,
                strict=True,
            )
        },
        "lottery_id": lottery_id,
        "native_ticket_count": k,
    }


def _source(cells: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cells": cells,
        "schema_version": decomposition.SOURCE_SCHEMA_VERSION,
        "study_id": "FIXTURE_STUDY",
        "task_id": decomposition.SOURCE_TASK_ID,
        "windows": {source_label: window for _, source_label, window in decomposition.WINDOWS},
    }


@pytest.mark.parametrize(
    ("numerator", "denominator", "decimal_12", "expected"),
    [
        (1, 10**400, "-999.0", "POSITIVE"),
        (0, 1, "123.0", "ZERO"),
        (-1, 10**400, "999.0", "NEGATIVE"),
    ],
)
def test_exact_rational_delta_sign_ignores_decimal_field(
    numerator: int,
    denominator: int,
    decimal_12: str,
    expected: str,
) -> None:
    experiment = {
        "absolute_paired_delta": _delta(
            numerator,
            denominator,
            decimal_12=decimal_12,
        ),
        "status": "COMPLETE",
    }

    assert decomposition.classify_delta(experiment) == expected


def test_noncanonical_exact_fraction_fails_closed() -> None:
    experiment = {
        "absolute_paired_delta": {
            "decimal_12": "0.5",
            "denominator": 4,
            "exact": "2/4",
            "numerator": 2,
        },
        "status": "COMPLETE",
    }

    with pytest.raises(decomposition.DecompositionDataError, match="exact fraction mismatch"):
        decomposition.classify_delta(experiment)


def test_zero_and_nonzero_switches_are_kept_separate() -> None:
    cell = decomposition.decompose_cell(
        _cell("TEST", 1, (0, 0, 1), switches=(0, 2, 1))
    )
    windows = cell["windows"]

    assert windows[0]["classification"] == "ZERO"
    assert windows[0]["switch_activity"] == "ZERO_SWITCH"
    assert windows[0]["zero_result_accompanied_by_switch_count_zero"] is True
    assert windows[1]["classification"] == "ZERO"
    assert windows[1]["switch_activity"] == "SWITCHING_ACTIVE"
    assert windows[1]["zero_result_accompanied_by_switch_count_zero"] is False
    assert cell["switch_activity_profile"] == (
        "SWITCHING_ACTIVE_IN_AT_LEAST_ONE_AVAILABLE_WINDOW"
    )


def test_incomplete_window_is_inconclusive_and_not_available() -> None:
    cell = decomposition.decompose_cell(_cell("TEST", 2, (1, 1, None), switches=(3, 2, 0)))

    assert cell["available_window_count"] == 2
    assert cell["sign_pattern"] == {
        "W50": "POSITIVE",
        "W300": "POSITIVE",
        "W750": "INCONCLUSIVE",
    }
    assert cell["positive_repeats_across_two_or_more_available_windows"] is True
    assert cell["windows"][2]["switch_activity"] == "INCONCLUSIVE"


def test_repeated_positive_and_sign_reversal_are_independent_flags() -> None:
    cell = decomposition.decompose_cell(_cell("TEST", 3, (1, -1, 1)))

    assert cell["positive_repeats_across_two_or_more_available_windows"] is True
    assert cell["sign_reversal"] is True
    assert [
        (pair["from_window"], pair["to_window"])
        for pair in cell["sign_reversal_pairs"]
    ] == [("W50", "W300"), ("W300", "W750")]


def test_material_change_uses_exact_dominant_identity_sets_without_threshold() -> None:
    stable = decomposition.decompose_cell(
        _cell("TEST", 4, (1, 0, -1), dominant_strategies=("a", "a", "a"))
    )
    changed = decomposition.decompose_cell(
        _cell("TEST", 5, (1, 0, -1), dominant_strategies=("a", "b", "b"))
    )

    assert stable["dominant_identity_materially_changes_with_window"] == (
        "NO_DOMINANT_IDENTITY_STABLE"
    )
    assert changed["dominant_identity_materially_changes_with_window"] == (
        "YES_DOMINANT_IDENTITY_CHANGED"
    )


def test_source_sha_validation_accepts_seal_and_rejects_drift() -> None:
    source, actual_sha256, size = decomposition.load_source_result(
        decomposition.DEFAULT_SOURCE_JSON
    )

    assert source["task_id"] == decomposition.SOURCE_TASK_ID
    assert actual_sha256 == decomposition.SOURCE_RESULT_SHA256
    assert size > 0
    with pytest.raises(
        decomposition.DecompositionDataError,
        match="SOURCE_RESULT_IDENTITY_DRIFT",
    ):
        decomposition.load_source_result(
            decomposition.DEFAULT_SOURCE_JSON,
            expected_sha256="0" * 64,
        )


def test_output_order_and_bytes_are_deterministic() -> None:
    first_cell = _cell(
        "T539",
        3,
        (1, -1, 1),
        dominant_strategies=("z_strategy", "z_strategy", "z_strategy"),
    )
    second_cell = _cell("P638", 1, (-1, 0, 1), switches=(3, 0, 2))
    source_a = _source([first_cell, second_cell])
    source_b = deepcopy(source_a)
    source_b["cells"].reverse()
    for raw_cell in source_b["cells"]:
        raw_cell["experiments"] = dict(reversed(raw_cell["experiments"].items()))

    payload_a = decomposition.build_decomposition(source_a, enforce_sealed_shape=False)
    payload_b = decomposition.build_decomposition(source_b, enforce_sealed_shape=False)

    assert [cell["cell_id"] for cell in payload_a["cells"]] == ["P638:K1", "T539:K3"]
    assert decomposition.canonical_json_bytes(payload_a) == decomposition.canonical_json_bytes(
        payload_b
    )
    assert decomposition.render_report(payload_a) == decomposition.render_report(payload_b)


def test_sealed_source_complete_accounting_and_diagnostics() -> None:
    source, source_sha256, source_size = decomposition.load_source_result(
        decomposition.DEFAULT_SOURCE_JSON
    )
    payload = decomposition.build_decomposition(
        source,
        source_sha256=source_sha256,
        source_size_bytes=source_size,
    )
    aggregates = payload["aggregates"]
    overall = aggregates["overall"]

    assert overall["cell_count"] == 22
    assert overall["experiment_count"] == 66
    assert overall["available_experiment_count"] == 62
    assert overall["classification_counts"] == {
        "POSITIVE": 15,
        "ZERO": 31,
        "NEGATIVE": 16,
        "INCONCLUSIVE": 4,
    }
    assert overall["switch_activity_counts"] == {
        "SWITCHING_ACTIVE": 32,
        "ZERO_SWITCH": 30,
        "INCONCLUSIVE": 4,
    }
    assert aggregates["cell_switch_activity_profiles"] == {
        "SWITCHING_ACTIVE_IN_AT_LEAST_ONE_AVAILABLE_WINDOW": 12,
        "ZERO_SWITCH_ACROSS_ALL_AVAILABLE_WINDOWS": 9,
        "NO_AVAILABLE_WINDOWS": 1,
    }
    cell_profile_aggregates = {
        item["switch_activity_profile"]: item
        for item in aggregates["by_cell_switch_activity_profile"]
    }
    assert cell_profile_aggregates[
        "SWITCHING_ACTIVE_IN_AT_LEAST_ONE_AVAILABLE_WINDOW"
    ]["classification_counts"] == {
        "POSITIVE": 15,
        "ZERO": 4,
        "NEGATIVE": 16,
        "INCONCLUSIVE": 1,
    }
    assert cell_profile_aggregates["ZERO_SWITCH_ACROSS_ALL_AVAILABLE_WINDOWS"][
        "classification_counts"
    ] == {
        "POSITIVE": 0,
        "ZERO": 27,
        "NEGATIVE": 0,
        "INCONCLUSIVE": 0,
    }

    answers = {item["question_id"]: item["answer"] for item in payload["diagnostic_answers"]}
    assert answers[1]["zero_with_zero_switch_count"] == 30
    assert answers[1]["zero_with_nonzero_switch_count"] == 1
    assert answers[2]["classification_counts"] == {
        "POSITIVE": 15,
        "ZERO": 1,
        "NEGATIVE": 16,
        "INCONCLUSIVE": 0,
    }
    repeated_positive = {item["cell_id"] for item in answers[3]["cells"]}
    assert repeated_positive == {
        "P638:K2",
        "P638:K3",
        "T539:K1",
        "T539:K2",
        "T539:K3",
    }
    reversal_cells = {item["cell_id"] for item in answers[4]["cells"]}
    assert reversal_cells == {
        "B649:K3",
        "P638:K1",
        "P638:K2",
        "P638:K3",
        "P638:K4",
        "P638:K7",
        "T539:K1",
        "T539:K2",
        "T539:K3",
        "T539:K5",
    }
    assert answers[5]["positive_experiment_count"] == 15
    assert answers[5]["k1_to_k3_positive_count"] == 12
    assert answers[5]["k_at_maximum_positive_count"] == [3]
    assert answers[6]["global_maximum_switch_count"] == 889
    assert answers[6]["outcome_description"] == "MIXED_AMONG_THREE_LARGEST_EXPERIMENTS"
    assert [item["cell_id"] for item in answers[6]["three_largest_experiments"]] == [
        "T539:K3",
        "T539:K1",
        "T539:K2",
    ]
    assert {item["cell_id"] for item in answers[7]["candidates"]} == repeated_positive

    material_change_cells = {
        cell["cell_id"]
        for cell in payload["cells"]
        if cell["dominant_identity_materially_changes_with_window"]
        == "YES_DOMINANT_IDENTITY_CHANGED"
    }
    assert material_change_cells == {"P638:K1", "P638:K2", "T539:K1"}
