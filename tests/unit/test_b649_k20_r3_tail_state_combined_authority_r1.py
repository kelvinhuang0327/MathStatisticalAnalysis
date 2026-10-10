"""Focused integration checks against the real immutable R24 and donor topology."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_tail_state_combined_authority_r1 as combined


def forbidden(*_: object, **__: object) -> NoReturn:
    pytest.fail("forbidden minimization, recertification, census, chase or solver")


def test_build_reuses_certificates_without_recertification(monkeypatch: pytest.MonkeyPatch) -> None:
    for module, names in (
        (combined.tail, ("uniform_certificate", "build_result", "minimizer_realization")),
        (
            combined.state,
            ("certify_member", "verify_member_certificate", "verify_result", "build_result"),
        ),
        (combined.state.r14, ("moment_certificate",)),
        (combined.r24, ("pinned_r7_census", "run_chase", "replay_stored_result")),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    result = combined.build_result()
    assert combined.__file__.startswith(str(combined.REPO_ROOT / "src"))
    assert result["TAIL_CERTIFIED_BOUND"] == 354_039_277
    assert result["STATE_CERTIFIED_BOUND"] == 355_637_030
    assert result["TARGET_STATE_ADOPTION"]["compressed_members"] == 1_427
    assert result["TARGET_STATE_ADOPTION"]["represented_vectors"] == 1_543
    assert result["TARGET_STATE_ADOPTION"]["adopted_certificates"] == 21
    assert result["TARGET_STATE_ADOPTION"]["carried_certificates"] == 62
    assert result["TARGET_STATE_ADOPTION"]["stored_witnesses_validated"] == 21
    assert result["TAIL_RECORDED_WITNESSES_VALIDATED"] == 2
    assert result["CANONICAL_PRIMITIVES"]["SINGLE_TICKET_ANY_PRIZE"] == 18_611_432
    assert result["NEW_STATE_CERTIFICATION_CALLS"] == result["TAIL_MINIMIZATION_CALLS"] == 0


def test_complete_catalog_retains_the_actual_competing_owner() -> None:
    result = combined.build_result()
    authority = combined.tail.r24_authority()
    before = authority["CURRENT_STATE_TERMS"]
    after = result["FINAL_STATE_TERMS"]
    assert result["START_STATE_TERMS"] == before
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    expected = [
        row | {"bound": 355_637_030} if row["stable_id"] == combined.state.TARGET_STATE_ID else row
        for row in before
    ]
    assert after == expected
    assert result["CHANGED_STATE_IDS"] == [combined.state.TARGET_STATE_ID]
    competing = "state:s2-12692531-s3-681744"
    assert max(row["bound"] for row in after) == result["FINAL_R3_FAMILY_BOUND"] == 355_722_668
    assert result["FINAL_OWNER_IDS"] == [competing]
    assert result["OWNER_TRANSITION"] == {
        "before": [combined.state.TARGET_STATE_ID],
        "after": [competing],
    }
    assert result["START_R3_FAMILY_BOUND"] == 355_726_896
    assert result["CURRENT_INCUMBENT"] == 313_263_888
    assert result["REMAINING_GAP"] == 42_458_780
    assert result["RESEARCH_EXPECTATION_MATCH"] is False
    assert result["PROJECTION_DIFFERENCE"] == 81_410
    assert result["CLASSIFIED_TERM_COUNT"] == 56_550
    classified = tuple(
        (row["stable_id"], row["bound"]) for row in authority["CURRENT_CLASSIFIED_TERMS"]
    )
    assert result["CLASSIFIED_TERMS_SHA256"] == combined.r24.digest(classified)
    assert result["CLASSIFIED_AGGREGATE"] == [
        {"stable_id": "carried-r12-other-levels", "bound": 355_468_904},
    ]
    assert result["CLASSIFIED_MAX"] == 355_468_904


@pytest.mark.parametrize("name", ["TAIL", "STATE"])
def test_source_commit_and_tree_are_exact(name: str) -> None:
    identities = combined.verify_sources()
    assert identities[name]["head"] == combined.SOURCE_PINS[name]["head"]
    assert identities[name]["tree"] == combined.SOURCE_PINS[name]["tree"]
    assert identities[name]["files_sha256"] == combined.SOURCE_PINS[name]["files"]


@pytest.mark.parametrize("surface", ["ancestry", "tree", "scope"])
def test_bad_git_authority_is_rejected(surface: str, monkeypatch: pytest.MonkeyPatch) -> None:
    original = combined.git_bytes

    def changed(*args: str) -> bytes:
        if surface == "ancestry" and args == (
            "merge-base",
            combined.BASE_HEAD,
            combined.STATE_DONOR_HEAD,
        ):
            return b"0" * 40 + b"\n"
        if surface == "tree" and args[0] == "show" and args[1] == "-s":
            return b"wrong tree\n"
        if surface == "scope" and args[0] == "diff":
            return original(*args) + b"src/unrelated.py\n"
        return original(*args)

    monkeypatch.setattr(combined, "git_bytes", changed)
    with pytest.raises(AssertionError, match=r"ancestry mismatch|identity mismatch|change scope"):
        combined.verify_sources()


SOURCE_FILES = tuple(
    path for pin in combined.SOURCE_PINS.values() for path in cast(dict[str, str], pin["files"])
)


@pytest.mark.parametrize("relative", SOURCE_FILES)
def test_source_and_result_tampering_is_rejected(
    relative: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_bytes

    def changed(path: Path) -> bytes:
        data = original(path)
        return data + b" " if path == combined.REPO_ROOT / relative else data

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(AssertionError, match="source/result identity mismatch"):
        combined.verify_sources()


@pytest.mark.parametrize(
    "defect",
    ["missing", "duplicate", "region", "vector_count", "ledger", "witness", "correction_sum"],
)
def test_invalid_state_adoption_is_rejected(defect: str) -> None:
    donor = combined.stored(combined.state.RESULT_PATH)
    records = donor["NEW_MEMBER_CERTIFICATES"]
    if defect == "missing":
        records.pop()
    elif defect == "duplicate":
        records[-1] = copy.deepcopy(records[0])
    elif defect == "region":
        donor["REGION_SHA256"] = "0" * 64
    elif defect == "vector_count":
        donor["REPRESENTED_VECTOR_COUNT"] -= 1
    elif defect == "ledger":
        donor["COMPLETE_REGION_MEMBERS"].pop()
    elif defect == "witness":
        support = records[0]["support_witnesses"][0]["support_witness"]
        support[0][1] = support[0][0]
    elif defect == "correction_sum":
        records[0]["member_certified_correction"] = (
            records[0]["prior_applied_correction"]
            + records[0]["minimum_vector_rational_correction"]
        )
    with pytest.raises(AssertionError):
        combined.adopt_state_certificate(donor)


def test_double_tail_credit_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = combined.stored

    def changed(path: Path) -> dict[str, Any]:
        result = original(path)
        if path == combined.tail.RESULT_PATH:
            result["FINAL_TAIL_BOUND"] -= result["UNIFORM_CORRECTION"]
        return result

    monkeypatch.setattr(combined, "stored", changed)
    with pytest.raises(AssertionError, match="Tail correction must be applied exactly once"):
        combined.build_result()


def test_omitted_competitor_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    states, classified = combined.tail.committed_terms()
    incomplete = tuple(row for row in states if row[0] != "state:s2-12692531-s3-681744")
    monkeypatch.setattr(combined.tail, "committed_terms", lambda: (incomplete, classified))
    with pytest.raises(AssertionError, match="complete 23-state catalog"):
        combined.build_result()


def test_tail_witness_tampering_is_rejected() -> None:
    result = combined.stored(combined.tail.RESULT_PATH)
    result["MINIMIZER_REALIZATION"][0]["argmin_support_witness_sha256"] = "0" * 64
    with pytest.raises(AssertionError, match="Tail witness identity or legality"):
        combined.validate_tail_witnesses(result)


@pytest.mark.parametrize(
    "key",
    [
        "FINAL_OWNER_IDS",
        "REMAINING_GAP",
        "SOURCE_IDENTITIES",
        "CLASSIFIED_TERMS_SHA256",
        "FINAL_STATE_TERMS",
        "WITNESS_SOUNDNESS_STATUS",
    ],
)
def test_complete_result_replay_rejects_tampered_fields(
    key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = combined.stored(combined.RESULT_PATH)
    tampered = copy.deepcopy(original)
    tampered[key] = "tampered"

    def replay() -> dict[str, Any]:
        return original

    monkeypatch.setattr(combined, "build_result", replay)
    with pytest.raises(AssertionError, match="not completely reproducible"):
        combined.verify_result(tampered)


def test_stored_result_completely_replays() -> None:
    result = combined.stored(combined.RESULT_PATH)
    assert combined.verify_result(result) == {"status": "PASS"}
    assert combined.RESULT_PATH.read_bytes() == combined.encode(combined.build_result()).encode()
    assert result == json.loads(combined.RESULT_PATH.read_text(encoding="utf-8"))
