"""Focused checks for sealed selector lineage attribution."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

import pytest
from tools import analyze_selector_lineage_attribution as attribution


def _record(
    strategy_id: str,
    binding_group_id: str,
    callable_family_id: str | None,
    *,
    classification: str = "DISTINCT_BINDING",
    resolution_status: str = "RESOLVED",
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "binding_group_id": binding_group_id,
        "callable_family_id": callable_family_id,
        "classification": classification,
        "resolution_status": resolution_status,
        "unresolved_reason": (
            None if resolution_status == "RESOLVED" else "FIXTURE_DYNAMIC_BINDING"
        ),
    }


def _index(*records: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], attribution.build_lineage_index({"records": list(records)}))


def _delta(
    numerator: int,
    denominator: int = 1,
    *,
    decimal_12: str = "SOURCE_SENTINEL",
) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "exact": f"{numerator}/{denominator}",
        "decimal_12": decimal_12,
    }


def _rolling_window(
    sign: str,
    delta: dict[str, Any] | None,
    *,
    switch_count: int,
    target_count: int,
) -> dict[str, Any]:
    return {
        "classification": sign,
        "rolling_minus_frozen_exact_delta": delta,
        "rolling_selection_target_count": target_count,
        "source_conclusion": "FIXTURE_CONCLUSION",
        "source_label": "SHORT",
        "source_status": "EXCLUDED" if sign == "INCONCLUSIVE" else "COMPLETE",
        "switch_count": switch_count,
        "window": 50,
        "window_label": "W50",
    }


def _pilot_experiment(
    delta: dict[str, Any] | None,
    frequencies: dict[str, int],
    *,
    switch_count: int,
    candidate_count: int,
    status: str = "COMPLETE",
) -> dict[str, Any]:
    return {
        "absolute_paired_delta": delta,
        "candidate_strategy_count": candidate_count,
        "conclusion": "FIXTURE_CONCLUSION",
        "label": "SHORT",
        "rolling_selection_frequency": frequencies,
        "rolling_strategy_switch_count": switch_count,
        "selection_trace_sha256": None if status == "EXCLUDED" else "a" * 64,
        "status": status,
        "window": 50,
    }


def test_exact_strategy_id_join_is_case_sensitive_and_does_not_infer_aliases() -> None:
    index = _index(
        _record("strategy_a", "binding:a", "callable:a"),
        _record("strategy_b", "binding:b", "callable:b"),
    )

    assert attribution.classify_transition("strategy_a", "strategy_b", index) == (
        "DISTINCT_BINDING"
    )
    assert attribution.classify_transition("Strategy_A", "strategy_b", index) == (
        "UNRESOLVED_LINEAGE"
    )


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (
            _record(
                "first",
                "binding:shared",
                "callable:shared",
                classification="IDENTICAL_BINDING",
            ),
            _record(
                "second",
                "binding:shared",
                "callable:shared",
                classification="IDENTICAL_BINDING",
            ),
            "SAME_BINDING",
        ),
        (
            _record(
                "first",
                "binding:first",
                "callable:shared",
                classification="SAME_CALLABLE_DIFFERENT_BINDING",
            ),
            _record(
                "second",
                "binding:second",
                "callable:shared",
                classification="SAME_CALLABLE_DIFFERENT_BINDING",
            ),
            "SAME_CALLABLE_DIFFERENT_BINDING",
        ),
        (
            _record("first", "binding:first", "callable:first"),
            _record("second", "binding:second", "callable:second"),
            "DISTINCT_BINDING",
        ),
        (
            _record("first", "binding:first", "callable:first"),
            _record(
                "second",
                "unresolved:second",
                None,
                classification="DYNAMIC_OR_UNRESOLVED",
                resolution_status="DYNAMIC_OR_UNRESOLVED",
            ),
            "UNRESOLVED_LINEAGE",
        ),
    ],
)
def test_transition_lineage_classes(
    first: dict[str, Any], second: dict[str, Any], expected: str
) -> None:
    index = _index(first, second)

    assert attribution.classify_transition("first", "second", index) == expected


def test_uniform_distinct_support_preserves_source_delta_and_resolves_all_switches() -> None:
    source_delta = _delta(1, 3, decimal_12="DO_NOT_RECOMPUTE")
    rolling = _rolling_window("POSITIVE", source_delta, switch_count=3, target_count=4)
    pilot = _pilot_experiment(
        deepcopy(source_delta),
        {"strategy_b": 2, "strategy_a": 2},
        switch_count=3,
        candidate_count=2,
    )
    index = _index(
        _record("strategy_a", "binding:a", "callable:a"),
        _record("strategy_b", "binding:b", "callable:b"),
    )

    result = attribution.attribute_experiment(
        rolling,
        pilot,
        ["strategy_a", "strategy_b"],
        index,
        cell_id="TEST:K1",
        lottery_id="TEST",
        k=1,
    )

    assert result["source_delta"] == source_delta
    assert result["source_delta"] is not source_delta
    assert result["lineage_resolved_switch_count"] == 3
    assert result["distinct_binding_transitions"] == 3
    assert result["unresolved_transitions"] == 0
    assert result["distinct_binding_switch_share"] == {
        "decimal_12": "1.000000000000",
        "denominator": 1,
        "exact": "1/1",
        "numerator": 1,
    }


def test_zero_switch_single_candidate_is_structurally_incapable() -> None:
    source_delta = _delta(0)
    result = attribution.attribute_experiment(
        _rolling_window("ZERO", source_delta, switch_count=0, target_count=4),
        _pilot_experiment(
            deepcopy(source_delta),
            {"strategy_a": 4},
            switch_count=0,
            candidate_count=1,
        ),
        ["strategy_a"],
        _index(_record("strategy_a", "binding:a", "callable:a")),
        cell_id="TEST:K1",
        lottery_id="TEST",
        k=1,
    )

    assert result["total_switch_count"] == 0
    assert result["lineage_resolved_switch_count"] == 0
    assert result["dominant_transition_family"] == "NO_SWITCH"
    assert result["distinct_binding_switch_share"] is None
    assert result["dynamic_diversity_capability"] == ("STRUCTURALLY_INCAPABLE_SINGLE_CANDIDATE")


def test_missing_strategy_id_fails_closed_as_unresolved_lineage() -> None:
    source_delta = _delta(-1)
    result = attribution.attribute_experiment(
        _rolling_window("NEGATIVE", source_delta, switch_count=2, target_count=4),
        _pilot_experiment(
            deepcopy(source_delta),
            {"strategy_a": 2, "Strategy_A": 2},
            switch_count=2,
            candidate_count=2,
        ),
        ["strategy_a", "Strategy_A"],
        _index(_record("strategy_a", "binding:a", "callable:a")),
        cell_id="TEST:K1",
        lottery_id="TEST",
        k=1,
    )

    assert result["lineage_resolved_switch_count"] == 0
    assert result["unresolved_transitions"] == 2
    assert result["missing_strategy_ids"] == ["Strategy_A"]
    assert result["distinct_binding_switch_share"] is None
    assert "MISSING_EXACT_STRATEGY_ID_JOIN" in result["unresolved_reasons"]


def test_hash_only_mixed_pair_classes_leave_every_switch_unresolved() -> None:
    source_delta = _delta(1)
    index = _index(
        _record(
            "parameter_a",
            "binding:a",
            "callable:shared",
            classification="SAME_CALLABLE_DIFFERENT_BINDING",
        ),
        _record(
            "parameter_b",
            "binding:b",
            "callable:shared",
            classification="SAME_CALLABLE_DIFFERENT_BINDING",
        ),
        _record("distinct", "binding:c", "callable:distinct"),
    )
    result = attribution.attribute_experiment(
        _rolling_window("POSITIVE", source_delta, switch_count=5, target_count=6),
        _pilot_experiment(
            deepcopy(source_delta),
            {"distinct": 2, "parameter_b": 2, "parameter_a": 2},
            switch_count=5,
            candidate_count=3,
        ),
        ["parameter_a", "parameter_b", "distinct"],
        index,
        cell_id="TEST:K1",
        lottery_id="TEST",
        k=1,
    )

    assert result["possible_transition_classes"] == [
        "SAME_CALLABLE_DIFFERENT_BINDING",
        "DISTINCT_BINDING",
    ]
    assert result["same_callable_different_binding_transitions"] == 0
    assert result["distinct_binding_transitions"] == 0
    assert result["unresolved_transitions"] == 5
    assert "MIXED_POSSIBLE_LINEAGE_CLASSES_WITHOUT_ENDPOINTS" in result["unresolved_reasons"]


def test_output_is_deterministic_across_input_mapping_order() -> None:
    source_delta = _delta(1, 2)
    rolling = _rolling_window("POSITIVE", source_delta, switch_count=3, target_count=4)
    index = _index(
        _record("strategy_a", "binding:a", "callable:a"),
        _record("strategy_b", "binding:b", "callable:b"),
    )
    first = attribution.attribute_experiment(
        rolling,
        _pilot_experiment(
            deepcopy(source_delta),
            {"strategy_b": 2, "strategy_a": 2},
            switch_count=3,
            candidate_count=2,
        ),
        ["strategy_b", "strategy_a"],
        index,
        cell_id="TEST:K1",
        lottery_id="TEST",
        k=1,
    )
    second = attribution.attribute_experiment(
        deepcopy(rolling),
        _pilot_experiment(
            deepcopy(source_delta),
            {"strategy_a": 2, "strategy_b": 2},
            switch_count=3,
            candidate_count=2,
        ),
        ["strategy_a", "strategy_b"],
        dict(reversed(list(index.items()))),
        cell_id="TEST:K1",
        lottery_id="TEST",
        k=1,
    )

    assert attribution.canonical_json_bytes(first) == attribution.canonical_json_bytes(second)


def test_sealed_sources_have_complete_conservative_accounting() -> None:
    rolling, pilot, lineage, source_identity = attribution.load_default_sources()
    payload = attribution.build_attribution(
        rolling,
        pilot,
        lineage,
        source_identity=source_identity,
    )
    aggregates = cast(dict[str, Any], payload["aggregates"])
    overall = cast(dict[str, Any], aggregates["overall"])

    assert overall["experiment_count"] == 66
    assert overall["switching_experiment_count"] == 32
    assert overall["total_switch_count"] == 5605
    assert overall["lineage_resolved_switch_count"] == 28
    assert overall["same_binding_transitions"] == 0
    assert overall["same_callable_different_binding_transitions"] == 0
    assert overall["distinct_binding_transitions"] == 28
    assert overall["unresolved_transitions"] == 5577

    by_sign = {
        cast(str, row["sign"]): row for row in cast(list[dict[str, Any]], aggregates["by_sign"])
    }
    assert (
        by_sign["POSITIVE"]["total_switch_count"],
        by_sign["POSITIVE"]["unresolved_transitions"],
    ) == (
        2635,
        2635,
    )
    assert (
        by_sign["NEGATIVE"]["total_switch_count"],
        by_sign["NEGATIVE"]["distinct_binding_transitions"],
        by_sign["NEGATIVE"]["unresolved_transitions"],
    ) == (2949, 28, 2921)
    assert (by_sign["ZERO"]["total_switch_count"], by_sign["ZERO"]["unresolved_transitions"]) == (
        21,
        21,
    )

    experiments = cast(list[dict[str, Any]], payload["experiments"])
    resolved = [row for row in experiments if row["lineage_resolved_switch_count"]]
    assert [(row["experiment_id"], row["distinct_binding_transitions"]) for row in resolved] == [
        ("B649:K3:W300", 28)
    ]
    assert len(cast(list[dict[str, Any]], payload["unresolved_rows"])) == 31

    candidates = cast(list[dict[str, Any]], payload["repeated_positive_candidate_cells"])
    assert [row["cell_id"] for row in candidates] == [
        "P638:K2",
        "P638:K3",
        "T539:K1",
        "T539:K2",
        "T539:K3",
    ]
    assert sum(cast(int, row["total_switch_count"]) for row in candidates) == 4454
    assert sum(cast(int, row["unresolved_transitions"]) for row in candidates) == 4454

    siblings = cast(dict[str, Any], payload["p638_c01_c07_bridge_family"])
    assert siblings["exact_lineage_join_count"] == 7
    assert siblings["pairwise_structural_classification"] == ("SAME_CALLABLE_DIFFERENT_BINDING")
    assert siblings["experiments_with_two_or_more_selected_siblings"] == 3
    assert siblings["sibling_selection_count"] == 815
    assert siblings["actual_sibling_transition_count"] is None

    zero_findings = cast(dict[str, Any], payload["zero_no_switch_structural_capability"])
    assert zero_findings["zero_no_switch_cell_count"] == 9
    assert zero_findings["structurally_incapable_cell_count"] == 9
    assert len(zero_findings["zero_switch_experiments_in_structurally_capable_cells"]) == 3

    quality = cast(dict[str, Any], payload["source_data_quality"])
    assert quality["unique_selected_strategy_id_count"] == 134
    assert quality["exact_joined_selected_strategy_id_count"] == 25
    assert quality["exact_resolved_selected_strategy_id_count"] == 22
    assert quality["missing_selected_strategy_id_count"] == 109
    assert quality["source_unresolved_selected_strategy_id_count"] == 3


def test_noncanonical_source_fraction_fails_closed() -> None:
    bad_delta = {
        "numerator": 2,
        "denominator": 4,
        "exact": "2/4",
        "decimal_12": "0.500000000000",
    }

    with pytest.raises(attribution.LineageAttributionError, match="exact fraction mismatch"):
        attribution.attribute_experiment(
            _rolling_window("POSITIVE", bad_delta, switch_count=1, target_count=2),
            _pilot_experiment(
                deepcopy(bad_delta),
                {"strategy_a": 1, "strategy_b": 1},
                switch_count=1,
                candidate_count=2,
            ),
            ["strategy_a", "strategy_b"],
            _index(
                _record("strategy_a", "binding:a", "callable:a"),
                _record("strategy_b", "binding:b", "callable:b"),
            ),
            cell_id="TEST:K1",
            lottery_id="TEST",
            k=1,
        )
