"""Six current-owner R14 certificates: identities, credit, family, and tamper rejection."""

from __future__ import annotations

import copy
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, NoReturn

import pytest

from lottolab.research import b649_k20_r3_current_owner_six_member_r14_certificate_r1 as certificate
from lottolab.research import b649_k20_r3_joint_residual_envelope_r7 as r7
from lottolab.research import b649_k20_r3_state_tail_owner_chase_r14 as r14

PRIOR = 4_592_000
EXPECTED = (
    ("[0,12][4,5][25,1]", 5_628_293, 354_600_737),
    ("[0,12][1,1][4,4][25,1]", 5_629_537, 354_599_493),
    ("[0,12][1,2][4,3][25,1]", 5_630_160, 354_598_870),
    ("[0,12][1,3][4,2][25,1]", 5_630_160, 354_598_870),
    ("[0,12][1,4][4,1][25,1]", 5_629_537, 354_599_493),
    ("[0,12][1,5][25,1]", 5_628_293, 354_600_737),
)


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, solver, or enumeration")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    produced = certificate.build_result()
    assert produced["TASK_STATUS"] == "SUCCESS"
    return produced


def test_region_and_tied_owner_coverage(result: dict[str, Any]) -> None:
    assert Path(certificate.__file__ or "").is_relative_to(certificate.REPO_ROOT / "src")
    members = certificate.region_members()
    priors = certificate.current_member_bounds(members)
    owners = certificate.load_bearing_members(members, priors)
    assert result["REGION_IDENTITY"] == result["REGION_SHA256"] == certificate.REGION_SHA256
    assert result["REGION_COMPRESSED_MEMBER_COUNT"] == len(members) == 1_427
    assert result["REGION_REPRESENTED_VECTOR_COUNT"] == 1_543
    assert [certificate.member_id(member.counts) for member in owners] == [
        row[0] for row in EXPECTED
    ]
    assert all(member.represented_vector_count == 1 for member in owners)
    assert {priors[member.counts] for member in owners} == {max(priors.values())} == {355_637_030}
    assert len(owners) == len({member.counts for member in owners}) == 6


def test_residual_event_ceiling_and_max_combination(result: dict[str, Any]) -> None:
    records = result["MEMBER_CERTIFICATES"]
    assert [
        (row["member_id"], row["member_certified_correction"], row["member_new_bound"])
        for row in records
    ] == list(EXPECTED)
    for record in records:
        counts = certificate.dense(record["witness_counts"])
        moment = certificate.exact_residual_pair_moment(counts)
        ceiling = certificate.ceiling_divide_by_9(moment)
        assert record["residual_event_definition"] == certificate.RESIDUAL_EVENT_DEFINITION
        assert record["residual_pair_moment"] == moment
        assert moment % 9 != 0
        assert ceiling == math.ceil(Fraction(moment, 9))
        assert ceiling != moment // 9
        assert record["r14_correction"] == ceiling
        assert record["prior_applied_correction"] == PRIOR
        assert record["prior_applied_correction"] == max(
            record["r6_pair_correction"], record["forest_correction"]
        )
        combined = certificate.combine_corrections(
            record["r6_pair_correction"], record["forest_correction"], ceiling
        )
        assert combined == max(record["r6_pair_correction"], record["forest_correction"], ceiling)
        assert record["member_certified_correction"] == combined == max(PRIOR, ceiling)
        assert record["member_new_bound"] == certificate.member_bound(
            record["uncorrected_anchor_bound"], combined
        )
        assert record["member_new_bound"] != (record["uncorrected_anchor_bound"] - PRIOR - ceiling)
        assert record["member_raw_bound"] == record["uncorrected_anchor_bound"] - PRIOR
        pairs = certificate.occupied_type_pairs(counts)
        left, right = pairs[0]
        table_api = "_pair_event_correction_table"
        table = getattr(certificate.r8, table_api)(left, right)
        overlap = (table[0][0], table[0][1], table[0][2], table[0][3])
        assert certificate.residual_pair_intersection(left, right, overlap) == table[0][4]
        assert record["vector_certificate"]["correction_lower_bound"] == ceiling
        assert record["represented_vector_count"] == 1
        assert len(record["support_witness"]) == 18
        assert record["hunter_correction_applied"] is False


def test_no_duplicate_credit_and_no_hunter_correction(result: dict[str, Any]) -> None:
    source = Path(certificate.__file__ or "").read_text(encoding="utf-8")
    assert "HUNTER_HOMOGENEOUS" not in source
    assert "HUNTER_CLASS_SPLIT" not in source
    assert result["NON_DUPLICATE_CREDIT_STATUS"] == (
        "PASS_MAX_OF_R6_PAIR_FOREST_AND_R14_SINGLE_REPLACEMENT"
    )
    assert result["DUPLICATE_CORRECTIONS"] == 0
    assert result["CORRECTION_COMBINATION"] == "MAX(R6_PAIR, FOREST, R14_RATIONAL)"
    certified = [record["member_id"] for record in result["MEMBER_CERTIFICATES"]]
    assert len(certified) == len(set(certified)) == 6
    for record in result["MEMBER_CERTIFICATES"]:
        assert record["member_certified_correction"] == record["r14_correction"]
        assert record["member_new_bound"] == (
            record["uncorrected_anchor_bound"] - record["member_certified_correction"]
        )


def test_remainder_and_top_band_stay_unchanged(result: dict[str, Any]) -> None:
    sealed = certificate.sealed_top_band_bounds()
    assert len(sealed) == 21
    certified = {
        certificate.dense(record["witness_counts"]) for record in result["MEMBER_CERTIFICATES"]
    }
    assert certified.isdisjoint(sealed)
    rows = result["COMPLETE_REGION_MEMBERS"]
    assert len(rows) == 1_427
    unchanged = [row for row in rows if certificate.dense(row["witness_counts"]) not in certified]
    assert len(unchanged) == result["REMAINDER_MEMBER_COUNT"] == 1_421
    assert all(row["final_bound"] == row["prior_bound"] for row in unchanged)
    assert result["REMAINDER_MAX"] == max(row["final_bound"] for row in unchanged)
    by_counts = {certificate.dense(row["witness_counts"]): row for row in rows}
    for counts, bound in sealed.items():
        assert by_counts[counts]["final_bound"] == by_counts[counts]["prior_bound"] == bound
    assert result["TOP_BAND_CERTIFICATES_PRESERVED"] is True
    assert result["FULL_STATE_CATALOG_STATUS"] == "PASS_1427_OF_1427_1421_UNCHANGED"


def test_state_maximum_and_complete_family(result: dict[str, Any]) -> None:
    assert result["STATE_TERM_COUNT"] == len(result["FINAL_STATE_TERMS"]) == 23
    assert result["FINAL_STATE_BOUND"] == 355_630_646
    assert result["START_COMPLETE_R3_UB"] == 355_637_030
    assert result["FINAL_COMPLETE_R3_UB"] == 355_630_646
    assert result["FINAL_OWNER_IDS"] == ["state:s2-13548976-s3-951748"]
    assert result["CURRENT_INCUMBENT"] == 313_263_888
    assert result["REMAINING_GAP"] == 42_366_758
    assert result["REMAINING_GAP"] == result["FINAL_COMPLETE_R3_UB"] - result["CURRENT_INCUMBENT"]
    assert result["NEXT_BAND_COMPRESSED_MEMBERS"] == 11
    assert result["NEXT_BAND_REPRESENTED_VECTORS"] == 12
    assert result["TAIL_BOUND"] == 354_039_277
    assert result["CLASSIFIED_MAX"] == 355_468_904
    assert result["CLASSIFIED_AGGREGATE"] == [
        {"stable_id": "carried-r12-other-levels", "bound": 355_468_904}
    ]
    before = {row["stable_id"]: row["bound"] for row in result["START_STATE_TERMS"]}
    after = {row["stable_id"]: row["bound"] for row in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == 23
    changed = {key for key in before if before[key] != after[key]}
    assert changed == {"state:s2-13548976-s3-951748"}
    assert after["state:s2-13548976-s3-951748"] == 355_630_646
    others = sorted(
        ((bound, key) for key, bound in after.items() if key not in changed), reverse=True
    )
    assert others[0] == (355_628_469, "state:s2-13169800-s3-789320")
    assert result["FINAL_FAMILY_MAX_RECOMPUTATION"]["R3_BOUND"] == 355_630_646
    assert result["FINAL_FAMILY_MAX_RECOMPUTATION"]["STATE_MAX_BOUND"] == 355_630_646
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"
    assert certificate.summary(result)["FINAL_COMPLETE_R3_UB"] == 355_630_646


def test_committed_result_matches_replay(result: dict[str, Any]) -> None:
    stored = certificate.RESULT_PATH.read_text(encoding="utf-8")
    assert stored == certificate.encode(result)
    assert stored.endswith("\n")


def test_replay_rejects_tampered_witness_and_bound(result: dict[str, Any]) -> None:
    assert certificate.verify_result(result)["status"] == "PASS"
    witness = copy.deepcopy(result)
    ticket = witness["MEMBER_CERTIFICATES"][0]["support_witness"][0]
    ticket[0] = 99
    with pytest.raises(AssertionError, match="support witness"):
        certificate.verify_result(witness)
    bound = copy.deepcopy(result)
    bound["MEMBER_CERTIFICATES"][0]["member_new_bound"] += 1
    bound["COMPLETE_REGION_MEMBERS"][0]["final_bound"] += 1
    with pytest.raises(AssertionError, match=r"support witness|replay|catalog|differs"):
        certificate.verify_result(bound)


@pytest.mark.parametrize(
    "relative",
    [
        "src/lottolab/research/b649_k20_r3_state_tail_owner_chase_r14.py",
        "src/lottolab/research/b649_k20_r3_frontier_realizability_bound_r8.py",
    ],
)
def test_tampered_source_bytes_rejected(relative: str, monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.read_bytes

    def read(self: Path) -> bytes:
        data = original(self)
        if self.as_posix().endswith(relative):
            return data + b"\n"
        return data

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(AssertionError, match="fingerprint"):
        certificate.verify_upstream_fingerprints()


def test_certificate_does_not_call_census_or_solver(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(r7, "joint_residual_census", forbidden)
    monkeypatch.setattr(r14, "s4_child", forbidden)
    monkeypatch.setattr(certificate.r8, "support_model_status", forbidden)
    fresh = certificate.build_result()
    assert certificate.summary(fresh) == certificate.summary(result)
