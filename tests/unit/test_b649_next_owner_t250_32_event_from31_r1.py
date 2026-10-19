"""Focused acceptance tests for the 32-event B649 Family integration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from typing import Any

import pytest

from lottolab.research import b649_next_owner_t250_32_event_from31_r1 as candidate


@pytest.fixture(scope="module")
def replay() -> Iterator[
    tuple[
        dict[str, Any],
        dict[str, candidate.Row],
        dict[str, candidate.Row],
    ]
]:
    yield candidate.build_candidate()


def test_fixed_source_and_exact_31_event_prefix(
    replay: tuple[
        dict[str, Any],
        dict[str, candidate.Row],
        dict[str, candidate.Row],
    ],
) -> None:
    result, before_rows, after_rows = replay
    assert result["BASE"] == {
        "HEAD": candidate.BASE_HEAD,
        "TREE": candidate.BASE_TREE,
        "RESULT_PATH": candidate.BASE_RESULT_PATH,
        "RESULT_SHA256": candidate.BASE_RESULT_SHA256,
        "ROWS": candidate.BASE_ROWS,
        "EVENTS": candidate.BASE_EVENTS,
        "FULL_DIGEST": candidate.BASE_FULL_DIGEST,
        "BOUNDS_DIGEST": candidate.BASE_BOUNDS_DIGEST,
    }
    assert len(before_rows) == len(after_rows) == candidate.BASE_ROWS
    assert result["ROWS_BEFORE"] == result["ROWS_AFTER"] == candidate.BASE_ROWS
    assert result["EVENTS_BEFORE"] == candidate.BASE_EVENTS
    assert result["EVENTS_AFTER"] == candidate.BASE_EVENTS + 1
    assert result["NEW_EVENT_COUNT"] == 1
    assert result["DUPLICATE_EVENTS"] == 0
    assert result["EVENT_PREFIX_PARITY"] == "EXACT"

    raw = candidate.four.committed_blob(
        candidate.ROOT,
        candidate.BASE_HEAD,
        candidate.BASE_RESULT_PATH,
    )
    base_result = candidate.four.json_object(raw, "fixed Base result is invalid")
    history = result["EVENT_HISTORY"]
    assert history[:-1] == base_result["EVENT_HISTORY"]
    assert history[-1]["EVENT_ID"] == candidate.EVENT_ID


def test_one_target_row_and_exact_native_r32_route_b(
    replay: tuple[
        dict[str, Any],
        dict[str, candidate.Row],
        dict[str, candidate.Row],
    ],
) -> None:
    result, before_rows, after_rows = replay
    old = before_rows[candidate.PROFILE_ID]
    new = after_rows[candidate.PROFILE_ID]
    assert (old.cap, old.bound) == (264, 313_391_636)
    assert (new.cap, new.bound) == (250, 313_266_168)
    assert old.bound - new.bound == 125_468
    assert result["PROFILE"]["BEFORE_STATE_MISMATCH"] == 0

    changed = {
        profile_id
        for profile_id in before_rows
        if before_rows[profile_id] != after_rows[profile_id]
    }
    assert changed == {candidate.PROFILE_ID}
    assert result["PROFILE"]["CHANGED_ROWS"] == 1
    assert result["PROFILE"]["UNCHANGED_ROWS"] == 4_646

    route = result["ROUTE_B"]
    assert route["OLD_TERMS"] == 243
    assert route["NEW_TERMS"] == 229
    assert route["OLD_BOUND"] == 313_391_636
    assert route["NEW_BOUND"] == 313_266_168
    assert route["NEW_ARGMAX"] == [250, 313_266_168, 387, 199, 216_804, 5_000_016]
    assert route["TERM_MISMATCH_COUNT"] == 0
    assert route["STRUCTURE"] == {"W": 830, "U": 2_345, "TOP": 12, "A_MAX": 199}


def test_unchanged_class_and_recounted_family_frontier(
    replay: tuple[
        dict[str, Any],
        dict[str, candidate.Row],
        dict[str, candidate.Row],
    ],
) -> None:
    result, _before_rows, _after_rows = replay
    class_record = result["CLASS"]
    assert class_record["COUNT"] == 197
    assert class_record["BOUND_BEFORE"] == class_record["BOUND_AFTER"] == 313_258_872
    assert class_record["ID_SET_SHA256"] == candidate.CLASS_ID_SET_SHA256
    assert class_record["CLASS_MUTATIONS"] == 0

    before = result["FAMILY_FRONTIER_BEFORE"]
    after = result["FAMILY_FRONTIER_AFTER"]
    assert before["FAMILY_BOUND"] == result["FAMILY_BEFORE"] == 313_391_740
    assert after["FAMILY_BOUND"] == result["FAMILY_AFTER"] == 313_391_740
    assert result["FAMILY_GAIN"] == 0
    assert result["ALL_MAXIMIZING_OWNERS"] == [
        "66655555555331100000",
        "66655555555411110000",
    ]
    assert after["MAXIMIZING_OWNERS"] == result["ALL_MAXIMIZING_OWNERS"]
    assert result["NEXT_DISTINCT_BOUND"] == after["NEXT_DISTINCT_BOUND"]
    assert result["NEXT_DISTINCT_OWNERS"] == after["NEXT_DISTINCT_OWNERS"]
    assert result["NEXT_DISTINCT_BOUND"] < result["FAMILY_AFTER"]
    assert result["NEXT_DISTINCT_OWNERS"]


def test_canonical_digests_provenance_and_source_closure(
    replay: tuple[
        dict[str, Any],
        dict[str, candidate.Row],
        dict[str, candidate.Row],
    ],
) -> None:
    result, before_rows, after_rows = replay
    assert candidate.four.seven.two.full_digest(before_rows) == candidate.BASE_FULL_DIGEST
    assert (
        candidate.four.seven.two.bounds_digest(before_rows)
        == candidate.BASE_BOUNDS_DIGEST
    )
    assert result["FULL_DIGEST"] == candidate.four.seven.two.full_digest(after_rows)
    assert result["BOUNDS_DIGEST"] == candidate.four.seven.two.bounds_digest(after_rows)
    assert result["FULL_DIGEST"] != result["BASE"]["FULL_DIGEST"]
    assert result["BOUNDS_DIGEST"] != result["BASE"]["BOUNDS_DIGEST"]

    assert result["SCIENCE_PROVENANCE"] == candidate.SCIENCE_PROVENANCE
    assert result["SCIENCE_PROVENANCE"]["EVIDENCE_KIND"] == "TRANSCRIPT_ONLY"
    assert "REPORT_PATH" not in result["SCIENCE_PROVENANCE"]
    assert "REPORT_SHA256" not in result["SCIENCE_PROVENANCE"]

    assert result["SOURCE_CLOSURE_STATUS"] == "PASS"
    closure_paths = {item["PATH"] for item in result["SOURCE_CLOSURE"]}
    assert {
        "src/lottolab/research/b649_existing_four_owner_local_authority_r1.py",
        "src/lottolab/research/b649_nine_event_eight_profile_local_authority_r1.py",
        "src/lottolab/research/b649_sixteen_event_frozen_lineage_local_authority_r1.py",
        "src/lottolab/research/b649_triple_t262_31_event_family_integration_r1.py",
        "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py",
    }.issubset(closure_paths)
    assert result["SOURCE_SHA256"] == hashlib.sha256(
        (candidate.ROOT / candidate.SOURCE_PATH).read_bytes()
    ).hexdigest()
    assert result["TEST_SHA256"] == hashlib.sha256(
        (candidate.ROOT / candidate.TEST_PATH).read_bytes()
    ).hexdigest()

    encoded = candidate.serialize_result(result)
    assert json.loads(encoded.decode("utf-8")) == result
    for unstable_key in (
        "GIT_STATUS",
        "DIRTY_PATHS",
        "TIMESTAMP",
        "EXECUTION_ENVIRONMENT",
        "PYTHON_VERSION",
    ):
        assert unstable_key not in result


def test_all_required_negative_controls_reject_with_reasons(
    replay: tuple[
        dict[str, Any],
        dict[str, candidate.Row],
        dict[str, candidate.Row],
    ],
) -> None:
    result, _before_rows, _after_rows = replay
    negative = result["NEGATIVE_CONTROL_RESULTS"]
    assert set(negative) == {
        "WRONG_BASE_HEAD",
        "WRONG_BASE_TREE",
        "WRONG_BASE_RESULT_SHA",
        "WRONG_PROFILE",
        "WRONG_OLD_CAP",
        "UNSUPPORTED_CAP_249",
        "WRONG_NEW_BOUND",
        "WRONG_W",
        "WRONG_U",
        "WRONG_A_MAX",
        "MISSING_EVENT",
        "DUPLICATE_EVENT",
        "UNRELATED_ROW_MUTATION",
        "WRONG_CLASS",
        "WRONG_FAMILY",
        "MISSING_JUDGE_PROVENANCE",
        "CROSS_LINEAGE_IMPORT",
        "WRONG_PARENT",
        "WRONG_COMMITTED_PATHS",
        "UNEXPECTED_DIRTY_PATH",
    }
    for name, reason in negative.items():
        assert reason.startswith("REJECTED: "), name
        assert len(reason) > len("REJECTED: "), name
