"""Focused schema and reconciliation checks for the four-donor successor."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

import pytest

from lottolab.research import b649_certified_four_donor_family_replay_r1 as family_replay
from lottolab.research import b649_four_donor_family_successor_r1 as successor


@pytest.fixture(scope="module")
def candidate() -> successor.Document:
    return successor.build_candidate()


def test_candidate_matches_consumer_schema_and_four_donor_family(
    candidate: successor.Document,
) -> None:
    rows, projection = successor.validate_consumer_schema(candidate)

    assert len(rows) == 4647
    assert len(projection) == 197
    assert candidate["INCUMBENT"] == 313263888
    assert candidate["FAMILY_UB"] == 313389300
    assert candidate["ALL_OWNER_IDS"] == ["65555555555433000000"]
    assert candidate["NEXT_DISTINCT_BOUND"] == 313388988
    assert candidate["NEXT_DISTINCT_OWNER_IDS"] == ["66666555544431000000"]
    assert candidate["OPEN_PROFILES"] == 1513
    assert candidate["FAMILY_BOUND"] == 313389300
    assert candidate["OWNER_IDS"] == ["65555555555433000000"]
    assert candidate["STILL_OPEN_PROFILE_COUNT"] == 1513
    assert candidate["FAMILY_AFTER"] == {
        "FAMILY_BOUND": 313389300,
        "OWNER_IDS": ["65555555555433000000"],
        "GAP_TO_INCUMBENT": 125412,
        "STILL_OPEN_PROFILE_COUNT": 1513,
        "RESOLVED_MAXIMUM": 313389300,
        "CURSOR_MAXIMUM": 313388984,
    }


def test_cursor_projection_and_donor_updates_are_exact(candidate: successor.Document) -> None:
    cursor = candidate["CURSOR"]
    assert isinstance(cursor, dict)
    assert cursor["PROFILE_COUNT"] == 197
    assert cursor["CURSOR_SUMMARY_BOUND"] == 313391784
    assert cursor["EFFECTIVE_CURSOR_MAX"] == 313388984

    audit = candidate["RESOLVED_LEDGER_AUDIT"]
    assert isinstance(audit, dict)
    assert audit["UPDATED_PROFILE_BOUNDS"] == {
        "66665555555321100000": 313329096,
        "65555555555432100000": 313122700,
        "65555555555511111000": 313364480,
        "55555555555443000000": 312835000,
    }
    assert audit["UPDATED_ROWS"] == 4
    assert audit["UNCHANGED_ROWS"] == 4643


def test_full_ledger_comparison_reconciles_the_t245_extra_row(
    candidate: successor.Document,
) -> None:
    comparison = candidate["MAIN_VS_SCIENCE_BASE"]
    assert isinstance(comparison, dict)
    rows = cast(list[object], comparison["DIFF_ROWS"])
    assert comparison["RECOMPUTED_DIFF_COUNT"] == len(rows)
    assert comparison["PREVIOUS_REPORTED_DIFF_COUNT"] == 32
    assert comparison["COUNT_DELTA"] == len(rows) - 32 == 1

    t245 = candidate["T245_CERTIFICATE"]
    assert isinstance(t245, dict)
    assert t245["PROFILE_ID"] == "66555555555431100000"
    assert t245["MAIN_BOUND"] == 313394776
    assert t245["SCIENCE_BASE_BOUND"] == 313206768
    assert t245["BOUND"] == t245["SCIENCE_BASE_BOUND"]
    assert t245["SOURCE_SHA256"] == (
        "a9a8571a236285110893e5131225f9533b3da414b58e194a2aa990e430561617"
    )


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("RESOLVED_ROW_BOUNDS", "66665555555321100000"), True),
        (("CURSOR", "PROFILE_COUNT"), True),
        (("CURSOR", "PROFILE_IDS"), []),
        (("CURSOR", "COARSE_BOUND_PROJECTION"), []),
        (("INCUMBENT",), True),
    ],
)
def test_consumer_schema_rejects_wrong_types(
    candidate: successor.Document,
    path: tuple[str | int, ...],
    replacement: Any,
) -> None:
    corrupted = deepcopy(candidate)
    target: Any = corrupted
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement

    with pytest.raises(ValueError):
        successor.validate_consumer_schema(corrupted)


def test_consumer_schema_rejects_missing_incumbent(candidate: successor.Document) -> None:
    corrupted = deepcopy(candidate)
    del corrupted["INCUMBENT"]

    with pytest.raises(ValueError):
        successor.validate_consumer_schema(corrupted)


def test_missing_sealed_evidence_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    working_file_attribute = "_working_file"
    original = getattr(successor, working_file_attribute)
    missing_path = (
        f"{successor.EVIDENCE_DIRECTORY}/t257-certified-commit-message.txt"
    )

    def missing(path: str) -> bytes:
        if path == missing_path:
            raise ValueError(f"missing/unsafe working file: {path}")
        return original(path)

    monkeypatch.setattr(successor, "_working_file", missing)
    with pytest.raises(ValueError, match="missing/unsafe working file"):
        successor.build_candidate()


def test_wrong_sealed_evidence_sha_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    working_file_attribute = "_working_file"
    original = getattr(successor, working_file_attribute)
    corrupted_path = (
        f"{successor.EVIDENCE_DIRECTORY}/t257-certified-commit-message.txt"
    )

    def corrupted(path: str) -> bytes:
        if path == corrupted_path:
            return original(path) + b"corruption"
        return original(path)

    monkeypatch.setattr(successor, "_working_file", corrupted)
    with pytest.raises(ValueError, match="working bytes differ"):
        successor.build_candidate()


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("ALL_OWNER_IDS",), []),
        (("NEXT_DISTINCT_BOUND",), 313388989),
        (("CURSOR", "PROFILE_IDS"), []),
        (("CURSOR", "COARSE_BOUND_PROJECTION", "66544333333333332222"), 313388985),
        (("DONORS", 0, "PROFILE"), "00000000000000000000"),
        (("DONORS", 0, "CERTIFIED_BOUND"), 313329097),
        (("MAIN_VS_SCIENCE_BASE", "DIFF_ROWS"), []),
        (("MAIN_VS_SCIENCE_BASE", "COUNT_DELTA"), 0),
        (("T245_CERTIFICATE", "BOUND"), 313206769),
        (("CANONICAL_MAIN_ADOPTION",), "ADOPTED"),
    ],
)
def test_verifier_rejects_candidate_mutations(
    candidate: successor.Document,
    path: tuple[str | int, ...],
    replacement: Any,
) -> None:
    corrupted = deepcopy(candidate)
    target: Any = corrupted
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement

    with pytest.raises(ValueError):
        successor.validate_candidate(corrupted, expected=candidate)


def test_duplicate_json_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate JSON key"):
        successor.parse_json(
            b'{"RESOLVED_ROW_BOUNDS":{"11111111111111111111":1,'
            b'"11111111111111111111":2}}',
            "duplicate resolved row",
        )


def test_family_summary_verifier_rejects_omitted_tied_owner() -> None:
    rows = {"owner-a": 10, "owner-b": 10, "next": 9}
    projection = {"cursor": 8}
    expected = family_replay.family_summary(rows, projection, 0)
    corrupted = deepcopy(expected)
    corrupted["ALL_OWNER_IDS"] = ["owner-a"]

    with pytest.raises(ValueError, match="ALL_OWNER_IDS"):
        successor.validate_family_summary(corrupted, rows, projection, 0)


def test_exact_result_render_is_stable(candidate: successor.Document) -> None:
    payload = successor.render(candidate)
    assert payload.endswith(b"\n")
    assert successor.parse_json(payload, "candidate round trip") == candidate
