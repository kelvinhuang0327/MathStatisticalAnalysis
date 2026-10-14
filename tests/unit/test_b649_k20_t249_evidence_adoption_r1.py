from __future__ import annotations

import json
from pathlib import Path

import pytest

from lottolab.research import b649_k20_t249_evidence_adoption_r1 as adoption

ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = (
    ROOT
    / "docs/research/matrix-native-results/"
    / "b649-k20-t249-evidence-adoption-r1-result.json"
)


@pytest.fixture(scope="module")
def sources() -> adoption.PinnedSources:
    return adoption.load_pinned_sources(ROOT)


@pytest.fixture(scope="module")
def evidence(sources: adoption.PinnedSources) -> dict[str, object]:
    return adoption.verify_adoption(sources)


@pytest.fixture(scope="module")
def result_record() -> dict[str, object]:
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def test_accepted_single_row_adoption_and_27_state_arithmetic(
    sources: adoption.PinnedSources,
    evidence: dict[str, object],
    result_record: dict[str, object],
) -> None:
    adoption.validate_result_status(result_record, evidence)
    assert sources.digests[adoption.FROZEN_RESULT_PATH] == adoption.FROZEN_RESULT_SHA256
    assert sources.digests[adoption.CERTIFICATE_RESULT_PATH] == adoption.CERTIFICATE_RESULT_SHA256
    assert sources.digests[adoption.R30_RESULT_PATH] == adoption.R30_RESULT_SHA256
    assert evidence["INTEGER_STATE_COUNT"] == 27
    states = evidence["INTEGER_STATES"]
    assert len(states) == 27
    assert min(state["ow_lower_bound"] for state in states) == 78
    assert evidence["ORIGINAL_CAP"] == 265
    assert evidence["NEW_CAP"] == 249
    assert evidence["PER_T_BEFORE_COUNT"] == 244
    assert evidence["PER_T_AFTER_COUNT"] == 228
    assert evidence["OLD_ROW_BOUND"] == 313256489
    assert evidence["NEW_ROW_BOUND"] == 313121137
    assert evidence["ROW_IMPROVEMENT"] == 135352
    assert evidence["INCUMBENT_MARGIN"] == 142751
    assert evidence["OTHER_ROWS_UNCHANGED"] is True
    original = sources.family["COMPLETE_PROFILE_BOUNDS"]
    proposed = evidence["PROPOSED_COMPLETE_PROFILE_BOUNDS"]
    assert len(proposed) == len(original) == 4844
    assert sum(row[0] == adoption.PROFILE_ID for row in proposed) == 1
    assert all(
        before == after
        for before, after in zip(original, proposed)
        if before[0] != adoption.PROFILE_ID
    )


def test_wrong_profile_id_rejected(sources: adoption.PinnedSources) -> None:
    with pytest.raises(adoption.AdoptionError, match="profile ID"):
        adoption.verify_adoption(sources, profile_id="65555555555541000001")


def test_wrong_source_sha_rejected(sources: adoption.PinnedSources) -> None:
    with pytest.raises(adoption.AdoptionError, match="source SHA"):
        adoption.verify_adoption(sources, source_sha256="0" * 64)


def test_wrong_original_cap_rejected(sources: adoption.PinnedSources) -> None:
    with pytest.raises(adoption.AdoptionError, match="historical R30 cap"):
        adoption.verify_adoption(sources, original_cap=264)


def test_t_cap_250_rejected(sources: adoption.PinnedSources) -> None:
    with pytest.raises(adoption.AdoptionError, match="accepted analytic T cap"):
        adoption.verify_adoption(sources, accepted_cap=250)


def test_ow_floor_77_rejected(sources: adoption.PinnedSources) -> None:
    with pytest.raises(adoption.AdoptionError, match="OW floor"):
        adoption.verify_adoption(sources, ow_floor=77)


def test_missing_e6_zero_wedge_correction_rejected() -> None:
    floors = dict(adoption.ZERO_GRAPH_CASE_FLOORS)
    del floors[6]
    with pytest.raises(adoption.AdoptionError, match="include e=0..6"):
        adoption.verify_integer_states(floors)


def test_duplicate_wedge_rejected() -> None:
    duplicate_wedges = (
        ("center-a", "left", "right"),
        ("center-a", "left", "right"),
        ("center-b", "left", "right"),
    )
    with pytest.raises(adoption.AdoptionError, match="same wedge"):
        adoption.verify_wedge_disjointness(3, 1, duplicate_wedges)


def test_non_target_row_update_rejected(sources: adoption.PinnedSources) -> None:
    with pytest.raises(adoption.AdoptionError, match="only the target"):
        adoption.verify_adoption(
            sources,
            row_updates={
                adoption.PROFILE_ID: adoption.NEW_ROW_BOUND,
                "65555555555541000001": 313000000,
            },
        )


def test_original_resource_cannot_be_promoted(
    evidence: dict[str, object],
    result_record: dict[str, object],
) -> None:
    changed = dict(result_record)
    changed["ORIGINAL_RESOURCE"] = "PASS"
    with pytest.raises(adoption.AdoptionError, match="ORIGINAL_RESOURCE"):
        adoption.validate_result_status(changed, evidence)


def test_wrong_new_row_bound_rejected(sources: adoption.PinnedSources) -> None:
    with pytest.raises(adoption.AdoptionError, match="new row bound"):
        adoption.verify_adoption(sources, declared_new_row_bound=313121138)


@pytest.mark.parametrize(
    "field",
    ("FROZEN_RESULT_SHA256", "PROOF_SOURCE_SHA256", "R30_LEDGER_SHA256"),
)
def test_each_pinned_input_sha_is_bound(
    evidence: dict[str, object], result_record: dict[str, object], field: str,
) -> None:
    changed = dict(result_record)
    changed[field] = "0" * 64
    with pytest.raises(adoption.AdoptionError, match=field):
        adoption.validate_result_status(changed, evidence)


@pytest.mark.parametrize(
    "field",
    (
        "TASK_ID", "FROZEN_HEAD", "FROZEN_TREE", "FROZEN_RESULT_PATH",
        "PROOF_SOURCE_PATH", "R30_LEDGER_PATH", "HISTORICAL_R30_LOCATOR",
        "HISTORICAL_T_CAP",
    ),
)
def test_fixed_source_identity_is_bound(
    evidence: dict[str, object], result_record: dict[str, object], field: str,
) -> None:
    changed = dict(result_record)
    current = changed[field]
    changed[field] = current + 1 if type(current) is int else f"{current}-changed"
    with pytest.raises(adoption.AdoptionError, match=field):
        adoption.validate_result_status(changed, evidence)


@pytest.mark.parametrize(
    ("path_field", "sha_field"),
    (
        ("FROZEN_RESULT_PATH", "FROZEN_RESULT_SHA256"),
        ("PROOF_SOURCE_PATH", "PROOF_SOURCE_SHA256"),
        ("R30_LEDGER_PATH", "R30_LEDGER_SHA256"),
    ),
)
def test_mutually_changed_source_path_and_sha_still_fail_closed(
    evidence: dict[str, object], result_record: dict[str, object],
    path_field: str, sha_field: str,
) -> None:
    changed = dict(result_record)
    changed[path_field] = f"untrusted/{path_field.lower()}.json"
    changed[sha_field] = "f" * 64
    with pytest.raises(adoption.AdoptionError):
        adoption.validate_result_status(changed, evidence)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("SOURCE_METHOD", "Recompute the formula from adjacent bounds."),
        ("SOURCE_COLUMN", "T"),
    ),
)
def test_row_bound_method_and_column_are_bound(
    evidence: dict[str, object], result_record: dict[str, object],
    field: str, replacement: str,
) -> None:
    changed = dict(result_record)
    changed["ROW_BOUND_EVIDENCE"] = dict(result_record["ROW_BOUND_EVIDENCE"])
    changed["ROW_BOUND_EVIDENCE"][field] = replacement
    with pytest.raises(adoption.AdoptionError, match=field):
        adoption.validate_result_status(changed, evidence)


def test_full_family_closure_cannot_be_promoted(
    evidence: dict[str, object], result_record: dict[str, object],
) -> None:
    changed = dict(result_record)
    changed["FULL_FAMILY_CLOSURE"] = "CLAIMED"
    with pytest.raises(adoption.AdoptionError, match="FULL_FAMILY_CLOSURE"):
        adoption.validate_result_status(changed, evidence)


BOUND_RESULT_FIELDS = (
    "TASK_ID", "FROZEN_HEAD", "FROZEN_TREE", "FROZEN_RESULT_PATH",
    "FROZEN_RESULT_SHA256", "PROOF_SOURCE_PATH", "PROOF_SOURCE_SHA256",
    "R30_LEDGER_PATH", "R30_LEDGER_SHA256", "HISTORICAL_R30_LOCATOR",
    "HISTORICAL_T_CAP", "ROW_BOUND_EVIDENCE.SOURCE_METHOD",
    "ROW_BOUND_EVIDENCE.SOURCE_COLUMN", "FULL_FAMILY_CLOSURE",
)


@pytest.mark.parametrize("field", BOUND_RESULT_FIELDS)
def test_required_source_method_column_and_scope_fields_cannot_be_missing(
    evidence: dict[str, object], result_record: dict[str, object], field: str,
) -> None:
    changed = dict(result_record)
    if field.startswith("ROW_BOUND_EVIDENCE."):
        del changed["ROW_BOUND_EVIDENCE"][field.split(".", 1)[1]]
    else:
        del changed[field]
    with pytest.raises(adoption.AdoptionError):
        adoption.validate_result_status(changed, evidence)


@pytest.mark.parametrize("field", BOUND_RESULT_FIELDS)
def test_required_source_method_column_and_scope_fields_reject_wrong_types(
    evidence: dict[str, object], result_record: dict[str, object], field: str,
) -> None:
    changed = dict(result_record)
    if field.startswith("ROW_BOUND_EVIDENCE."):
        changed["ROW_BOUND_EVIDENCE"] = dict(result_record["ROW_BOUND_EVIDENCE"])
        changed["ROW_BOUND_EVIDENCE"][field.split(".", 1)[1]] = 1
    else:
        changed[field] = "265" if field == "HISTORICAL_T_CAP" else 1
    with pytest.raises(adoption.AdoptionError):
        adoption.validate_result_status(changed, evidence)


def test_row_bound_evidence_must_be_an_object(
    evidence: dict[str, object], result_record: dict[str, object],
) -> None:
    changed = dict(result_record)
    changed["ROW_BOUND_EVIDENCE"] = []
    with pytest.raises(adoption.AdoptionError, match="ROW_BOUND_EVIDENCE"):
        adoption.validate_result_status(changed, evidence)
