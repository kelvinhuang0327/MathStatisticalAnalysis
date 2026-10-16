from __future__ import annotations

import json
from collections.abc import Sequence
from copy import deepcopy
from typing import cast

import pytest

from lottolab.research import (
    b649_k20_min_s2_cursor_197_class_local_certificate_r1 as certificate,
)


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return certificate.build_result()


def _profiles(result: dict[str, object]) -> tuple[certificate.Profile, ...]:
    raw_ids = result["PROFILE_IDS"]
    assert isinstance(raw_ids, list)
    profile_ids = cast(list[object], raw_ids)
    return tuple(certificate.r20.decode_profile(value) for value in profile_ids)


def _profile_rows(result: dict[str, object]) -> list[dict[str, object]]:
    raw_rows = result["PROFILE_BOUND_ROWS"]
    assert isinstance(raw_rows, list)
    return cast(list[dict[str, object]], raw_rows)


def test_frozen_sources_and_full_197_profile_result(result: dict[str, object]) -> None:
    assert result["BASE_HEAD"] == certificate.FROZEN_HEAD
    assert result["BASE_TREE"] == certificate.FROZEN_TREE
    assert result["FROZEN_HEAD_TREE_MATCH"] is True
    assert result["SIX_ROW_RESULT_SHA256"] == certificate.SIX_ROW_RESULT_SHA256
    assert result["SEVEN_ROW_RESULT_SHA256"] == certificate.SEVEN_ROW_RESULT_SHA256
    assert result["NINETEEN_EVENT_HEAD"] == certificate.NINETEEN_EVENT_HEAD
    assert result["NINETEEN_EVENT_TREE"] == certificate.NINETEEN_EVENT_TREE
    assert result["NINETEEN_EVENT_RESULT_SHA256"] == certificate.NINETEEN_EVENT_RESULT_SHA256
    assert result["COVERED_PROFILES"] == 197
    assert result["MISSING_PROFILES"] == 0
    assert result["DUPLICATE_PROFILES"] == 0
    assert result["COMPLETE_CLASS_COVERAGE"] is True
    proof = cast(dict[str, object], result["PROOF"])
    assert proof["EXACT_TERM_COUNT"] == 46_839
    assert proof["EXACT_TERM_COUNT_MATCH"] is True
    crosscheck = cast(dict[str, object], proof["INTEGER_RATIONAL_CROSSCHECK"])
    assert crosscheck["TERMS_CHECKED"] == 46_839
    assert crosscheck["STATUS"] == "PASS"


def test_wrong_frozen_source_identity_is_rejected() -> None:
    with pytest.raises(certificate.CertificateError, match="frozen HEAD identity"):
        certificate.verify_frozen_source_identity(frozen_head="0" * 40)
    with pytest.raises(certificate.CertificateError, match="expected 19-event result digest"):
        certificate.verify_frozen_source_identity(nineteen_event_result_sha256="0" * 64)


def test_wrong_nineteen_event_resolved_bound_is_rejected() -> None:
    authority = certificate.verify_frozen_source_identity()
    six = cast(dict[str, object], authority["SIX_RESULT"])
    seven = cast(dict[str, object], authority["SEVEN_RESULT"])
    nineteen_event = deepcopy(cast(dict[str, object], authority["NINETEEN_EVENT_RESULT"]))
    family_after = cast(dict[str, object], nineteen_event["FAMILY_AFTER"])
    family_after["NEXT_COMPETING_BOUND"] = 313_392_517
    with pytest.raises(certificate.CertificateError, match="19-event next resolved bound"):
        certificate.calculate_prospective_family_bound(
            six, seven, nineteen_event, certificate.EXPECTED_CLASS_BOUND
        )


def test_partition_omission_and_duplicate_are_rejected(result: dict[str, object]) -> None:
    profiles = _profiles(result)
    with pytest.raises(certificate.CertificateError, match="profile count"):
        certificate.validate_partition_profiles(profiles[:-1])
    duplicated = (*profiles[:-1], profiles[0])
    with pytest.raises(certificate.CertificateError, match="duplicate"):
        certificate.validate_partition_profiles(duplicated)


def test_wrong_partition_w_range_is_rejected(result: dict[str, object]) -> None:
    with pytest.raises(certificate.CertificateError, match="W range"):
        certificate.validate_partition_profiles(_profiles(result), expected_w_range=(773, 785))


def test_open_wedge_lower_bound_cannot_be_relaxed(result: dict[str, object]) -> None:
    profile = _profiles(result)[0]
    with pytest.raises(certificate.CertificateError, match="open-wedge lower bound"):
        certificate.max_triangles_from_open_wedge_floor(profile, open_wedge_floor=4)


def test_wrong_k4_ceiling_is_rejected(
    result: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = _profiles(result)[0]
    triangles = certificate.max_triangles_from_open_wedge_floor(profile)
    base_s4 = certificate.r28.profile_s4_floor(profile)
    original = certificate.r30.motif_s4_floor

    def lowered_k4(candidate: certificate.Profile, count: int) -> tuple[int, int]:
        k4, s4 = original(candidate, count)
        return k4 - 1, max(0, s4 - certificate.K4_MINIMUM_S4_WEIGHT)

    monkeypatch.setattr(certificate.r30, "motif_s4_floor", lowered_k4)
    with pytest.raises(certificate.CertificateError, match="K4 ceiling"):
        certificate.exact_term(profile, triangles, base_s4=base_s4)


def test_wrong_s4_credit_is_rejected(
    result: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = _profiles(result)[0]
    triangles = certificate.max_triangles_from_open_wedge_floor(profile)
    base_s4 = certificate.r28.profile_s4_floor(profile)
    original = certificate.r30.motif_s4_floor

    def inflated_s4(candidate: certificate.Profile, count: int) -> tuple[int, int]:
        k4, s4 = original(candidate, count)
        return k4, s4 + 1

    monkeypatch.setattr(certificate.r30, "motif_s4_floor", inflated_s4)
    with pytest.raises(certificate.CertificateError, match="S4 credit"):
        certificate.exact_term(profile, triangles, base_s4=base_s4)


def test_wrong_profile_and_class_maxima_are_rejected(result: dict[str, object]) -> None:
    rows = _profile_rows(result)
    first_terms = cast(Sequence[Sequence[int]], rows[0]["TERMS"])
    claimed_profile_max = cast(int, rows[0]["CLASS_BOUND_AFTER"])
    with pytest.raises(certificate.CertificateError, match="profile maximum"):
        certificate.verify_profile_maximum(first_terms, claimed_profile_max - 1)
    claimed_class_max = cast(int, result["CLASS_BOUND_AFTER"])
    with pytest.raises(certificate.CertificateError, match="class maximum"):
        certificate.verify_class_maximum(rows, claimed_class_max + 1)


def test_bound_claims_keep_local_class_and_family_projection_distinct(
    result: dict[str, object],
) -> None:
    assert result["CLASS_BOUND_BEFORE"] == 313_394_584
    assert result["CLASS_BOUND_AFTER"] == 313_258_872
    assert result["CLASS_DELTA"] == 135_712
    assert result["NEW_BOUND_BELOW_INCUMBENT"] is True
    assert result["FROZEN_FAMILY_BOUND"] == 313_398_532
    assert result["FROZEN_CLASS_ONLY_FAMILY_BOUND"] == 313_398_532
    assert result["NINETEEN_EVENT_FAMILY_BOUND"] == 313_394_584
    assert result["NINETEEN_EVENT_NEXT_RESOLVED_BOUND"] == 313_392_516
    assert result["NINETEEN_EVENT_NEXT_RESOLVED_OWNER"] == "65555555555541000000"
    assert result["NEW_CLASS_BOUND_CANDIDATE"] == 313_258_872
    assert result["PROSPECTIVE_FAMILY_BOUND"] == 313_392_516
    assert result["EXPECTED_PROSPECTIVE_BOUND_MATCH"] is True
    assert result["FORMAL_FAMILY_AUTHORITY"] == "NOT_ACCEPTED"
    assert result["FORMAL_AUTHORITY_STATUS"] == "NOT_ACCEPTED"
    assert result["INDEPENDENT_JUDGE_CLAIMED"] == "NO"


def test_saved_json_matches_recomputed_full_certificate(result: dict[str, object]) -> None:
    saved = json.loads(certificate.RESULT_PATH.read_text(encoding="utf-8"))
    for key in (
        "PROFILE_IDS",
        "PROFILE_BOUND_ROWS",
        "CLASS_BOUND_BEFORE",
        "CLASS_BOUND_AFTER",
        "CLASS_DELTA",
        "FROZEN_FAMILY_BOUND",
        "FROZEN_CLASS_ONLY_FAMILY_BOUND",
        "NINETEEN_EVENT_FAMILY_BOUND",
        "NINETEEN_EVENT_NEXT_RESOLVED_BOUND",
        "NEW_CLASS_BOUND_CANDIDATE",
        "PROSPECTIVE_FAMILY_BOUND",
        "SOURCE_SHA256",
        "TEST_SHA256",
        "FORMAL_FAMILY_AUTHORITY",
        "FORMAL_AUTHORITY_STATUS",
    ):
        assert saved[key] == result[key]
    verification = cast(dict[str, object], saved["VERIFICATION"])
    assert verification["FOCUSED_TEST_COMMAND"] == certificate.FOCUSED_TEST_COMMAND
    assert verification["FOCUSED_TEST_EXIT_CODE"] in (None, 0)
    assert verification["RUFF"] in ("NOT_RUN", "PASS")
    assert verification["PYRIGHT"] in ("NOT_RUN", "PASS")

