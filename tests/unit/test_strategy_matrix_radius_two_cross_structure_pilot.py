"""Focused deterministic checks for the cross-structure radius-two pilot."""

from __future__ import annotations

from fractions import Fraction

import pytest

import lottolab.research.strategy_matrix_radius_two_comparison as comparison
from lottolab.research.strategy_matrix_radius_two_comparison import (
    CROSS_STRUCTURE_EXCLUDED_STRUCTURE_ID,
    CROSS_STRUCTURE_MAX_STRUCTURES,
    _cross_structure_selection_only_payload,
    canonical_json_bytes,
    classify_cross_structure_family,
    classify_radius_two_outcome,
    derive_cross_structure_selection,
    deterministic_lowest_supported_k,
    deterministic_pilot_structure_ids,
)


def test_eligibility_is_sealed_without_calling_radius_two(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_evaluated(*args: object, **kwargs: object) -> None:
        raise AssertionError("radius-two evaluator must not run during eligibility")

    monkeypatch.setattr(comparison, "evaluate_registered_local_escape", fail_if_evaluated)
    selection = derive_cross_structure_selection()

    assert [record.candidate.source.structure_id for record in selection.audit_records] == [
        "BIG_LOTTO",
        "DAILY_539",
        "POWER_LOTTO_ZONE1",
    ]
    assert [candidate.source.structure_id for candidate in selection.selected] == [
        "BIG_LOTTO",
        "DAILY_539",
    ]
    assert [candidate.source.k for candidate in selection.selected] == [10, 10]


def test_power_lotto_zone1_is_excluded_from_new_execution() -> None:
    selection = derive_cross_structure_selection()

    power_record = next(
        record
        for record in selection.audit_records
        if record.candidate.source.structure_id == CROSS_STRUCTURE_EXCLUDED_STRUCTURE_ID
    )
    assert power_record.eligible is False
    assert power_record.reasons == ("EXCLUDED_ESTABLISHED_POWER_LOTTO_SIGNAL",)
    assert CROSS_STRUCTURE_EXCLUDED_STRUCTURE_ID not in {
        candidate.source.structure_id for candidate in selection.selected
    }


def test_structure_cap_is_stable_and_lexical() -> None:
    ids = (
        "Z_STRUCTURE",
        "DAILY_539",
        "BIG_LOTTO",
        "POWER_LOTTO_ZONE1",
        "A_STRUCTURE",
    )

    assert deterministic_pilot_structure_ids(ids) == (
        "A_STRUCTURE",
        "BIG_LOTTO",
        "DAILY_539",
    )
    assert len(deterministic_pilot_structure_ids(ids)) == CROSS_STRUCTURE_MAX_STRUCTURES


def test_lowest_supported_k_is_stable() -> None:
    assert deterministic_lowest_supported_k((20, 15, 10)) == 10

    with pytest.raises(ValueError, match="at least one integer"):
        deterministic_lowest_supported_k(())


def test_radius_two_row_classifications_are_exactly_typed() -> None:
    assert classify_radius_two_outcome(Fraction(1, 7)) == "RADIUS2_STRICT_IMPROVEMENT"
    assert classify_radius_two_outcome(Fraction(0)) == "RADIUS2_NO_IMPROVEMENT"
    assert classify_radius_two_outcome(Fraction(-1, 7)) == "RADIUS2_NO_IMPROVEMENT"
    assert classify_radius_two_outcome(None, resource_bound=True) == "RESOURCE_BOUND"


@pytest.mark.parametrize(
    ("classifications", "expected"),
    [
        (("RADIUS2_STRICT_IMPROVEMENT",), "CROSS_STRUCTURE_STRONG"),
        (
            ("RADIUS2_STRICT_IMPROVEMENT", "RADIUS2_NO_IMPROVEMENT"),
            "CROSS_STRUCTURE_MIXED",
        ),
        (("RADIUS2_NO_IMPROVEMENT",), "POWER_LOTTO_ONLY_SIGNAL"),
        (("RESOURCE_BOUND",), "RESOURCE_LIMITED"),
        ((), "NO_ELIGIBLE_ADDITIONAL_STRUCTURE"),
    ],
)
def test_cross_structure_family_classification(
    classifications: tuple[str, ...],
    expected: str,
) -> None:
    assert classify_cross_structure_family(classifications) == expected


def test_selection_payload_keeps_global_optimum_unknown() -> None:
    selection = derive_cross_structure_selection()
    payload = _cross_structure_selection_only_payload(selection)

    assert payload["global_optimum_status"] == "UNKNOWN"
    assert payload["selection_status"] == "SELECTION_SEALED_BEFORE_RADIUS2_EVALUATION"
    assert payload["selection_audit"]["selection_policy"][
        "row_selection_is_result_independent"
    ] is True


def test_selection_serialization_is_deterministic() -> None:
    first = _cross_structure_selection_only_payload(derive_cross_structure_selection())
    second = _cross_structure_selection_only_payload(derive_cross_structure_selection())

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
