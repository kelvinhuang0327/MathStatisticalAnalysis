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
