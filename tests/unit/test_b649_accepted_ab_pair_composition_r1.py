from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, cast

import pytest

from lottolab.research import b649_accepted_ab_pair_composition_r1 as composition


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _case() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    profile_a = "66655555555511100000"
    profile_b = "66665555554431000000"
    other_owner = "12345678901234567890"
    other_row = "23456789012345678901"
    cursor_owner = "34567890123456789012"
    cursor_row = "45678901234567890123"
    resolved = [
        (profile_a, 800),
        (profile_b, 850),
        (other_owner, 900),
        (other_row, 600),
    ]
    cursor = [(cursor_owner, 900), (cursor_row, 700)]
    base: dict[str, object] = {
        "identity": {"commit": "base-commit", "tree": "base-tree", "result_sha256": "base-result"},
        "resolved_rows": resolved,
        "cursor_rows": cursor,
        "incumbent": 500,
        "recorded_family_bound": 900,
        "recorded_family_owners": sorted((other_owner, cursor_owner)),
    }
    donors: dict[str, dict[str, object]] = {}
    expected_donors: dict[str, dict[str, object]] = {}
    for label, profile, before, bound in (
        ("A", profile_a, 800, 700),
        ("B", profile_b, 850, 730),
    ):
        terms = [[22, bound - 10, 2, 3, 112, 17], [23, bound, 4, 5, 112, 19]]
        identity = {
            "commit": f"{label}-commit",
            "tree": f"{label}-tree",
            "source_sha256": f"{label}-source-sha",
            "result_sha256": f"{label}-result-sha",
        }
        donors[label] = {
            "identity": identity,
            "profile": profile,
            "before_bound": before,
            "current_cap": 264,
            "cap": 23,
            "bound": bound,
            "term_count": len(terms),
            "terms": terms,
            "term_columns": list(composition.TERM_COLUMNS),
            "terms_sha256": _digest(terms),
            "s4_floor": 112,
            "s5_used": False,
            "s5_artifact_value": "NOT_ADOPTED" if label == "A" else None,
            "acceptance_status": "VERIFIED_WITH_CAVEATS",
        }
        expected_donors[label] = {
            "identity": dict(identity),
            "profile": profile,
            "before_bound": before,
            "current_cap": 264,
            "cap": 23,
            "bound": bound,
            "term_count": len(terms),
            "argmax_t": [23],
            "envelope_sha256": _digest(terms),
            "accepted_terms_sha256": f"{label}-accepted-terms-sha",
            "s4_floor": 112,
            "s5_used": False,
            "s5_artifact_value": "NOT_ADOPTED" if label == "A" else None,
            "acceptance_status": "VERIFIED_WITH_CAVEATS",
            "caveat": f"{label} synthetic caveat",
        }
    acceptance = {"task_id": "SYNTHETIC_ACCEPTANCE", "sha256": "synthetic-acceptance-sha"}
    expected: dict[str, object] = {
        "acceptance": {
            "task_id": "SYNTHETIC_ACCEPTANCE",
            "sha256": "synthetic-acceptance-sha",
        },
        "base": {
            "commit": "base-commit",
            "tree": "base-tree",
            "result_sha256": "base-result",
            "resolved_count": 4,
            "cursor_count": 2,
        },
        "donors": expected_donors,
        "bound_artifact_digests": {"SYNTHETIC_INPUT_SHA256": "synthetic-artifact-sha"},
    }
    return base, donors, acceptance, expected


def test_composes_only_a_and_b_and_preserves_rows_and_cursor() -> None:
    base, donors, acceptance, expected = _case()

    result = composition.compose(base, donors, acceptance, expected)

    rows = result["RESOLVED_ROW_BOUNDS_AFTER"]
    assert isinstance(rows, dict)
    assert rows["66655555555511100000"] == 700
    assert rows["66665555554431000000"] == 730
    assert rows["12345678901234567890"] == 900
    assert rows["23456789012345678901"] == 600
    assert result["UPDATED_ROW_COUNT"] == 2
    assert result["UNCHANGED_ROW_COUNT"] == 2
    assert result["CURSOR_PROFILE_BOUNDS"] == {
        "34567890123456789012": 900,
        "45678901234567890123": 700,
    }
    assert result["CURSOR_MAXIMUM"] == 900
    assert result["FAMILY_MAXIMUM"] == 900
    assert result["ALL_OWNERS"] == ["12345678901234567890", "34567890123456789012"]
    assert result["GAP_TO_INCUMBENT"] == 400
    assert result["GAP_ABOVE_CURSOR"] == 0
    assert result["CERTIFICATE_SCOPE"] == "BASE_SPECIFIC"
    assert result["CURRENT_GLOBAL_LATEST_AUTHORITY"] == "NOT_CLAIMED"
    assert result["THREE_ROW_JOINT_CERTIFICATE_INCLUDED"] == "NO"


@pytest.mark.parametrize("field", ["commit", "tree", "result_sha256"])
def test_rejects_changed_mathematical_base_identity(field: str) -> None:
    base, donors, acceptance, expected = _case()
    base["identity"][field] = "changed-base-pin"  # type: ignore[index]

    with pytest.raises(ValueError, match=r"Base .* pin differs"):
        composition.compose(base, donors, acceptance, expected)


@pytest.mark.parametrize("field", ["task_id", "sha256"])
def test_rejects_changed_acceptance_identity(field: str) -> None:
    base, donors, acceptance, expected = _case()
    acceptance[field] = "changed-acceptance"  # type: ignore[index]

    with pytest.raises(ValueError, match="acceptance identity differs"):
        composition.compose(base, donors, acceptance, expected)


@pytest.mark.parametrize("field", ["commit", "tree", "source_sha256", "result_sha256"])
def test_rejects_changed_donor_source_or_result_pin(field: str) -> None:
    base, donors, acceptance, expected = _case()
    donors["A"]["identity"][field] = "changed-donor-artifact"  # type: ignore[index]

    with pytest.raises(ValueError, match=f"donor A {field} pin differs"):
        composition.compose(base, donors, acceptance, expected)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("profile", "99999999999999999999", "profile differs"),
        ("cap", 24, "cap differs"),
        ("current_cap", 263, "current cap differs"),
        ("term_count", 1, "term count differs"),
        ("s4_floor", 111, "S4 floor differs"),
        ("s5_used", True, "uses S5"),
        ("acceptance_status", "SELF_CHECK_ONLY", "acceptance status differs"),
    ],
)
def test_rejects_wrong_donor_premises(field: str, value: object, message: str) -> None:
    base, donors, acceptance, expected = _case()
    donors["A"][field] = value

    with pytest.raises(ValueError, match=message):
        composition.compose(base, donors, acceptance, expected)


def test_rejects_tampered_envelope_even_if_profile_metadata_is_unchanged() -> None:
    base, donors, acceptance, expected = _case()
    donors["A"]["terms"][1][4] = 111  # type: ignore[index]

    with pytest.raises(ValueError, match="envelope digest differs"):
        composition.compose(base, donors, acceptance, expected)


def test_rejects_envelope_term_count_drift() -> None:
    base, donors, acceptance, expected = _case()
    donors["A"]["terms"].pop()  # type: ignore[union-attr]

    with pytest.raises(ValueError, match="term count does not match"):
        composition.compose(base, donors, acceptance, expected)


def test_rejects_wrong_s5_artifact_disposition() -> None:
    base, donors, acceptance, expected = _case()
    donors["B"]["s5_artifact_value"] = 123

    with pytest.raises(ValueError, match="S5 artifact disposition differs"):
        composition.compose(base, donors, acceptance, expected)


def test_rejects_duplicate_resolved_and_cursor_profiles() -> None:
    for key in ("resolved_rows", "cursor_rows"):
        base, donors, acceptance, expected = _case()
        rows = cast(list[Any], base[key])
        rows.append(rows[0])
        with pytest.raises(ValueError, match=r"duplicate .* profile"):
            composition.compose(base, donors, acceptance, expected)


def test_rejects_extra_donor_scope() -> None:
    base, donors, acceptance, expected = _case()
    donors["C"] = copy.deepcopy(donors["A"])

    with pytest.raises(ValueError, match="exactly donors A and B"):
        composition.compose(base, donors, acceptance, expected)


def test_rejects_base_family_claim_that_does_not_match_aggregation() -> None:
    base, donors, acceptance, expected = _case()
    base["recorded_family_bound"] = 901

    with pytest.raises(ValueError, match="Base family maximum differs"):
        composition.compose(base, donors, acceptance, expected)
