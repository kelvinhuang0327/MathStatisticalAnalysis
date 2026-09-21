"""Focused checks for the frozen B649 per-stream M3_PLUS authority artifact."""

from __future__ import annotations

from typing import cast

import pytest

from lottolab.research.b649_m3_plus_history_authority import (
    EXPECTED_STREAM_IDS,
    M3PlusObservation,
    artifact_content_sha256,
    load_artifact,
    m3_plus_success,
    observations_for_stream,
    validate_strictly_prior,
)


def test_artifact_has_exact_frozen_identity_and_truthful_coverage() -> None:
    payload = load_artifact()

    assert payload["stream_ids"] == list(EXPECTED_STREAM_IDS)
    assert payload["row_count"] == 9665
    assert payload["artifact_content_sha256"] == artifact_content_sha256(payload)
    assert payload["verification"] == {
        "exact_frozen_stream_identity": "PASS",
        "m3_plus_authority_resolved": "PASS",
        "prediction_outcome_alignment": "PASS_BY_DRAW_NUMBER_OFFICIAL_DATE",
        "duplicate_stream_draw": "PASS",
        "deterministic_ordering": "PASS",
        "strict_cutoff": "PASS",
        "target_prior_guard": "PASS",
        "trailing_window_coverage": "PASS_WITH_TRUTHFUL_GAPS",
        "candidate_outcome_validation": "NOT_RUN",
        "branch2_oos": "NOT_RUN",
        "production_runtime_or_scheduler_change": "NONE",
    }

    coverage_items = cast(list[dict[str, object]], payload["coverage"])
    coverage = {cast(str, item["stream_id"]): item for item in coverage_items}
    assert coverage[EXPECTED_STREAM_IDS[0]]["coverage_rate"] == "298/300"
    assert coverage[EXPECTED_STREAM_IDS[0]]["missing_draws"] == [
        {
            "draw_number": "115000084",
            "draw_date": "2026-09-01",
            "reason": "NO_EXACT_FROZEN_STREAM_FORECAST_EVIDENCE",
        },
        {
            "draw_number": "115000085",
            "draw_date": "2026-09-04",
            "reason": "NO_EXACT_FROZEN_STREAM_FORECAST_EVIDENCE",
        },
    ]
    assert all(
        coverage[stream_id]["coverage_rate"] == "297/300"
        for stream_id in EXPECTED_STREAM_IDS[1:6]
    )
    assert all(
        coverage[stream_id]["coverage_rate"] == "296/300"
        for stream_id in EXPECTED_STREAM_IDS[6:]
    )


def test_m3_plus_known_answers_use_native_ticket_sets() -> None:
    winning = (1, 2, 3, 4, 5, 6)

    assert m3_plus_success(((1, 2, 3, 4, 5, 6),), winning) is True
    assert m3_plus_success(((1, 2, 7, 8, 9, 10),), winning) is False
    assert m3_plus_success(
        ((7, 8, 9, 10, 11, 12), (1, 2, 3, 40, 41, 42)),
        winning,
    ) is True
    assert m3_plus_success((), winning) is False


def test_target_and_future_rows_fail_the_strict_prior_guard() -> None:
    payload = load_artifact()
    stream_id = EXPECTED_STREAM_IDS[0]
    observations = observations_for_stream(payload, stream_id)

    validated = validate_strictly_prior(
        observations,
        target_draw_number="115000087",
        target_draw_date="2026-09-11",
    )
    assert len(validated) == 880
    assert validated[-1].draw_number == "115000086"

    target_row = M3PlusObservation(
        draw_number="115000087",
        draw_date="2026-09-11",
        success=True,
    )
    future_row = M3PlusObservation(
        draw_number="115000088",
        draw_date="2026-09-15",
        success=False,
    )

    with pytest.raises(ValueError, match="strictly prior"):
        validate_strictly_prior(
            (*observations, target_row),
            target_draw_number="115000087",
            target_draw_date="2026-09-11",
        )
    with pytest.raises(ValueError, match="strictly prior"):
        validate_strictly_prior(
            (*observations, future_row),
            target_draw_number="115000087",
            target_draw_date="2026-09-11",
        )
