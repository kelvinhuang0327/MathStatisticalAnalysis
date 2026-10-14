from __future__ import annotations

from copy import deepcopy

import pytest

from lottolab.research import b649_k20_t249_t251_verified_overlay_r1 as overlay


def test_verified_two_profile_overlay_and_query() -> None:
    result = overlay.build_verified_overlay()

    assert result.row_bound_overrides == {
        "65555555555541000000": 313121137,
        "66555555555531000000": 313142921,
    }
    assert result.row_bound_for("65555555555541000000") == 313121137
    assert result.row_bound_for("66555555555531000000") == 313142921
    assert result.row_bound_for("55555555555511111100") == 313263888
    assert overlay.query_row_bound("65555555555541000000") == 313121137
    assert result.family_max_owner_profile == "55555555555511111100"
    assert result.family_max_before == 313263888
    assert result.family_max_after == 313263888
    assert result.family_max_delta == 0
    assert result.other_rows_unchanged is True
    assert result.full_family_closure == "NOT_CLAIMED"
    assert result.global_optimum == "NOT_CLAIMED"


def _inject_result_mutation(monkeypatch, path: str, mutate) -> None:
    read_result = overlay._read_result

    def changed(root, relative_path, expected_sha256):
        value = read_result(root, relative_path, expected_sha256)
        if relative_path == path:
            value = deepcopy(value)
            mutate(value)
        return value

    monkeypatch.setattr(overlay, "_read_result", changed)


@pytest.mark.parametrize(
    "case",
    (
        "WRONG_T249_RESULT_SHA",
        "WRONG_T251_RESULT_SHA",
        "WRONG_PROFILE_MAPPING",
        "DUPLICATE_PROFILE",
        "THIRD_PROFILE_UPDATE",
        "WRONG_ROW_BOUND",
        "WRONG_BOUND_METHOD",
        "MISMATCHED_FROZEN_SOURCE",
        "FALSE_FAMILY_CLOSURE",
        "RESOURCE_HISTORY_PROMOTION",
    ),
)
def test_fail_closed_negative_matrix(case: str, monkeypatch) -> None:
    if case == "WRONG_T249_RESULT_SHA":
        monkeypatch.setattr(overlay, "T249_RESULT_SHA256", "0" * 64)
        with pytest.raises(overlay.OverlayValidationError, match="PINNED_RESULT_SHA_MISMATCH"):
            overlay.build_verified_overlay()
    elif case == "WRONG_T251_RESULT_SHA":
        monkeypatch.setattr(overlay, "T251_RESULT_SHA256", "0" * 64)
        with pytest.raises(overlay.OverlayValidationError, match="PINNED_RESULT_SHA_MISMATCH"):
            overlay.build_verified_overlay()
    elif case == "WRONG_PROFILE_MAPPING":
        updates = [("65555555555541000000", 313142921), ("66555555555531000000", 313121137)]
        with pytest.raises(overlay.OverlayValidationError, match="WRONG_ROW_BOUND_OR_PROFILE_MAPPING"):
            overlay.build_verified_overlay(updates)
    elif case == "DUPLICATE_PROFILE":
        updates = [("65555555555541000000", 313121137), ("65555555555541000000", 313121137)]
        with pytest.raises(overlay.OverlayValidationError, match="DUPLICATE_PROFILE"):
            overlay.build_verified_overlay(updates)
    elif case == "THIRD_PROFILE_UPDATE":
        updates = [
            ("65555555555541000000", 313121137),
            ("66555555555531000000", 313142921),
            ("55555555555511111100", 313000000),
        ]
        with pytest.raises(overlay.OverlayValidationError, match="THIRD_PROFILE_UPDATE"):
            overlay.build_verified_overlay(updates)
    elif case == "WRONG_ROW_BOUND":
        updates = [("65555555555541000000", 313121138), ("66555555555531000000", 313142921)]
        with pytest.raises(overlay.OverlayValidationError, match="WRONG_ROW_BOUND_OR_PROFILE_MAPPING"):
            overlay.build_verified_overlay(updates)
    elif case == "WRONG_BOUND_METHOD":
        _inject_result_mutation(
            monkeypatch,
            overlay.T251_RESULT_PATH,
            lambda value: value["PROVENANCE"].update({"SOURCE_METHOD": "Bonf64"}),
        )
        with pytest.raises(overlay.OverlayValidationError):
            overlay.build_verified_overlay()
    elif case == "MISMATCHED_FROZEN_SOURCE":
        _inject_result_mutation(
            monkeypatch,
            overlay.T251_RESULT_PATH,
            lambda value: value["PROVENANCE"].update({"FROZEN_TREE": "0" * 40}),
        )
        with pytest.raises(overlay.OverlayValidationError):
            overlay.build_verified_overlay()
    elif case == "FALSE_FAMILY_CLOSURE":
        _inject_result_mutation(
            monkeypatch,
            overlay.T249_RESULT_PATH,
            lambda value: value.update({"FULL_FAMILY_CLOSURE": "CLAIMED"}),
        )
        with pytest.raises(overlay.OverlayValidationError):
            overlay.build_verified_overlay()
    elif case == "RESOURCE_HISTORY_PROMOTION":
        _inject_result_mutation(
            monkeypatch,
            overlay.T249_RESULT_PATH,
            lambda value: value.update({"ORIGINAL_RESOURCE": "PASS"}),
        )
        with pytest.raises(overlay.OverlayValidationError):
            overlay.build_verified_overlay()
    else:
        raise AssertionError("unknown negative case: " + case)
