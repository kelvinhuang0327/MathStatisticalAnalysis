"""Exact shared four-band R14 certificate and semantic mutation checks."""

from __future__ import annotations

import copy
import itertools
import json
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_k20_r3_state_13548976_multiband_shared_certificate_r1 as cert


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def test_immutable_source_and_all_eight_members(result: dict[str, Any]) -> None:
    assert result["BASE_HEAD"] == "3ad0f1b26d69b25c9c065c1d9ed8b7816f0350bd"
    assert result["BASE_TREE"] == "44d4edfd92703db5822e1c6a5e765ceb813e9dd4"
    assert result["BASE_RESULT_SHA256"] == (
        "bc69e67f5c85911b8eba9857ab933984eb27d28c3e3badfdd46bec59141687c1"
    )
    assert result["EIGHT_MEMBER_IDS"] == list(cert.TARGET_IDS)
    assert result["REPRESENTED_VECTOR_COVERAGE"] == [1] * 8
    assert result["REGION_COMPRESSED_MEMBER_COUNT"] == 1427
    assert result["REGION_REPRESENTED_VECTOR_COUNT"] == 1543
    assert result["REGION_SHA256"] == (
        "1eed0fb9bc975d825d42413dd07ebfad5296d00185118850a38512c8a94e1f63"
    )


def test_shared_exact_pair_rows_and_piecewise_moments(result: dict[str, Any]) -> None:
    common = result["COMMON_CERTIFICATE"]
    assert common["exact_pair_row_count"] == 65
    assert len({tuple(row[:6]) for row in common["exact_pair_rows"]}) == 65
    assert common["B_coefficients"] == [16_397_640, 1_162, -42]
    assert common["Q_coefficients"] == [70, 2]
    assert result["RESIDUAL_MOMENT_FLOORS"] == [
        48_442_240,
        48_442_240,
        49_309_204,
        49_309_204,
        50_176_084,
        50_176_084,
        51_148_160,
        51_148_160,
    ]
    assert result["R14_CORRECTIONS"] == [
        5_382_472,
        5_382_472,
        5_478_801,
        5_478_801,
        5_575_121,
        5_575_121,
        5_683_129,
        5_683_129,
    ]
    assert [row["outside_slope"] for row in common["slope_specializations"]] == [
        [433_006, 1],
        [433_006, 1],
        [433_006, 1],
        [433_006, 1],
        [433_006, 1],
        [433_006, 1],
        [434_322, 1],
        [434_322, 1],
    ]


def test_cross_band_slope_is_rejected_semantically() -> None:
    with pytest.raises(AssertionError, match="piecewise outside slope"):
        cert.require_piecewise_slope(cert.TARGET_VECTORS[0], Fraction(434_322))
    with pytest.raises(AssertionError, match="piecewise outside slope"):
        cert.require_piecewise_slope(cert.TARGET_VECTORS[-1], Fraction(433_006))


def test_corrections_replace_by_max_and_witnesses_remain_valid(
    result: dict[str, Any],
) -> None:
    for member in result["MEMBER_CERTIFICATES"]:
        assert member["represented_vector_count"] == 1
        row = member["vector_certificates"][0]
        values = row["corrections"]
        assert set(values) == {
            "R6_PAIR",
            "FOREST",
            "EXISTING_R14",
            "EXISTING_HUNTER",
            "NEW_R14",
        }
        assert row["combined_correction"] == max(values.values())
        assert row["uncorrected_anchor_bound"] - row["vector_new_bound"] == max(values.values())
        support = tuple(tuple(int(value) for value in ticket) for ticket in row["support_witness"])
        vector = cert.dense(member["witness_counts"])
        assert cert.r8.validate_support_assignment(vector, support)
        assert row["support_residual_pair_moment"] >= row["residual_pair_moment"]
        assert row["support_s4_pair_moment"] >= row["moment_certificate"]["s4_pairwise_lower_bound"]


def test_family_bounds_and_preserved_remainder_match_packet(result: dict[str, Any]) -> None:
    assert result["FOUR_NEW_BAND_BOUNDS"] == [
        354_230_418,
        354_133_641,
        354_036_873,
        353_928_417,
    ]
    assert result["PRESERVED_MEMBER_COUNT"] == 1419
    assert result["PRESERVED_MEMBER_BOUNDS_SHA256"] == (
        "5bf0973bd8c0bfc446364852511a83997d7b868361d7c0d366f9b656bb30e1c7"
    )
    assert result["COMPLETE_UPDATED_BOUNDS_SHA256"] == (
        "166c6535d886d0a8116fdf9389aef8996ae2472cee650ecbae746b8c188314b0"
    )
    assert result["START_COMPLETE_R3_UB"] == 355_594_890
    assert result["FINAL_COMPLETE_R3_UB"] == 355_593_098
    assert result["FINAL_OWNER_IDS"] == ["state:s2-13548976-s3-951748"]
    assert result["REMAINING_GAP"] == 42_329_210
    assert result["STATE_TERM_COUNT"] == 23
    assert result["TAIL_BOUND"] == 354_039_277
    assert result["CLASSIFIED_MAX"] == 355_468_904
    assert result["CLASSIFIED_TERM_COUNT"] == 56_550
    assert result["FULL_23_STATE_RECOMPUTATION"] == "PASS"
    assert result["PREVIOUS_CERTIFICATE_STATUS"] == "PASS_EXACT_SOURCE_REPLAY_AND_PRESERVATION"
    assert result["PREVIOUS_REGION_CERTIFICATES_SHA256"]
    assert result["PREVIOUS_NINE_ELEVEN_CERTIFICATES_SHA256"]


def test_pair_counter_mutation_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = cert.hunter.exact_pair_rows

    def wrong_counter(pairs: tuple[tuple[int, int], ...]) -> tuple[tuple[int, ...], ...]:
        rows = original(pairs)
        first_pair = pairs[0]
        return tuple((*row[:6], row[6] + 1) if row[:2] == first_pair else row for row in rows)

    monkeypatch.setattr(cert.hunter, "exact_pair_rows", wrong_counter)
    with pytest.raises(AssertionError, match="inclusion/exclusion"):
        cert.shared_pair_rows()


def test_floor_ceiling_mutation_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def floor_divide(value: int) -> int:
        return value // 9

    monkeypatch.setattr(cert.six, "ceiling_divide_by_9", floor_divide)
    with pytest.raises(AssertionError, match="independent exact residual moment"):
        cert.exact_moment_certificate(cert.TARGET_VECTORS[0])


def test_max_as_sum_mutation_is_rejected(
    monkeypatch: pytest.MonkeyPatch, result: dict[str, Any]
) -> None:
    member = next(
        item for item in cert.six.region_members() if item.counts == cert.TARGET_VECTORS[0]
    )

    def sum_corrections(values: Mapping[str, int]) -> int:
        return sum(values.values())

    monkeypatch.setattr(cert.hunter, "combine_corrections", sum_corrections)
    with pytest.raises(AssertionError, match="max single correction replacement"):
        cert.certify_member(
            member,
            cert.represented_vectors()[member.counts],
            member.raw_bound,
        )
    assert result["FINAL_COMPLETE_R3_UB"] == 355_593_098


def test_tampered_source_member_and_signature_are_rejected(
    monkeypatch: pytest.MonkeyPatch, result: dict[str, Any]
) -> None:
    source = copy.deepcopy(result)
    source["BASE_TREE"] = "0" * 40
    with pytest.raises(AssertionError, match="source identity"):
        cert.verify_result(source)

    member = next(
        item for item in cert.six.region_members() if item.counts == cert.TARGET_VECTORS[0]
    )
    with pytest.raises(AssertionError, match="prior bound"):
        cert.certify_member(
            member,
            cert.represented_vectors()[member.counts],
            member.raw_bound - 1,
        )

    signatures = itertools.count()

    def drifting_signature(_state: object) -> int:
        return next(signatures)

    monkeypatch.setattr(cert.hunter.eleven, "compression_signature", drifting_signature)
    with pytest.raises(AssertionError, match="compression signature"):
        cert.certify_member(
            member,
            cert.represented_vectors()[member.counts],
            member.raw_bound,
        )

    read_text = Path.read_text

    def tampered_source(path: Path, *args: Any, **kwargs: Any) -> str:
        text = read_text(path, *args, **kwargs)
        if path == cert.REPO_ROOT / cert.prior.RESULT_RELATIVE:
            payload = json.loads(text)
            payload["TASK_ID"] = "FOREIGN_SOURCE"
            return json.dumps(payload)
        return text

    monkeypatch.setattr(Path, "read_text", tampered_source)
    cert.prior_authority.cache_clear()
    try:
        with pytest.raises(AssertionError, match="immutable predecessor source identity"):
            cert.prior_authority()
    finally:
        cert.prior_authority.cache_clear()
