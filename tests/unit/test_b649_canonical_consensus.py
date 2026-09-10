"""Focused tests for the deterministic B649 Goal-C consensus contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from tools.b649_operational_prediction_loop import (
    build_canonical_consensus_payload,
    canonical_consensus_path,
    iter_prediction_files,
    persist_canonical_consensus_if_ready,
    save_strategy_prediction,
    update_outcome,
)

from lottolab.domain.b649_canonical_consensus import (
    CANONICAL_CONSENSUS_METHOD_ID,
    CanonicalConsensusDecision,
    CanonicalConsensusInputError,
    build_canonical_consensus,
)

FROZEN_UPSTREAM_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "B649_OPERATIONAL_PREDICTION_LOOP_R1/predictions/115000087"
)


def _artifact(
    strategy_id: str,
    tickets: list[list[int]],
    *,
    run_id: str | None = None,
    **extra: object,
) -> dict[str, object]:
    artifact: dict[str, object] = {
        "strategy_id": strategy_id,
        "prediction_run_id": run_id or f"run-{strategy_id}",
        "draw_number": "115000087",
        "draw_date": "2026-09-08",
        "lottery_type": "BIG_LOTTO",
        "strategy_version": "v0.1",
        "history_cutoff": {
            "draw_number": "115000086",
            "draw_date": "2026-09-08",
        },
        "prediction_temporal_class": "PRE_DRAW",
        "history_sha256": "a" * 64,
        "tickets": [
            {"ticket_position": position, "predicted_numbers": ticket}
            for position, ticket in enumerate(tickets, start=1)
        ],
    }
    artifact.update(extra)
    return artifact


def _number_scores(decision: CanonicalConsensusDecision) -> tuple[int, ...]:
    return decision.number_scores


def test_equal_family_weight_ignores_native_ticket_count() -> None:
    decision = build_canonical_consensus(
        (
            _artifact(
                "native_two_ticket",
                [[1, 2, 3, 4, 5, 6], [1, 7, 8, 9, 10, 11]],
                native_ticket_count=999,
            ),
            _artifact(
                "native_one_ticket",
                [[1, 12, 13, 14, 15, 16]],
                native_ticket_count=1,
            ),
        )
    )

    scores = _number_scores(decision)
    assert decision.family_count == 2
    assert scores[0] == 2
    assert scores[6] == 1
    assert scores[11] == 1


def test_multiple_tickets_and_duplicate_appearances_add_no_family_weight() -> None:
    decision = build_canonical_consensus(
        (
            _artifact(
                "family_a",
                [[1, 2, 3, 4, 5, 6], [1, 1, 7, 8, 9, 10], [7, 7, 11, 12, 13, 14]],
            ),
            _artifact("family_b", [[1, 15, 16, 17, 18, 19]]),
        )
    )

    scores = _number_scores(decision)
    assert scores[0] == 2
    assert scores[6] == 1
    assert scores[10] == 1
    assert max(scores) == 2


def test_all_test_streams_collapse_into_one_correlated_family() -> None:
    decision = build_canonical_consensus(
        (
            _artifact("legacy_biglotto__test_asm__hash-a", [[4, 5, 6, 7, 8, 9]]),
            _artifact("legacy_biglotto__test_ces__hash-b", [[4, 10, 11, 12, 13, 14]]),
            _artifact("ordinary_strategy", [[4, 15, 16, 17, 18, 19]]),
        )
    )

    scores = _number_scores(decision)
    assert decision.family_count == 2
    test_family = next(family for family in decision.families if family.family_id == "test_family")
    assert test_family.source_strategy_ids == (
        "legacy_biglotto__test_asm__hash-a",
        "legacy_biglotto__test_ces__hash-b",
    )
    assert scores[3] == 2
    assert scores[4] == 1


def test_family_scores_cover_01_through_49_and_are_binary() -> None:
    decision = build_canonical_consensus(
        (
            _artifact("family_a", [[1, 2, 3, 4, 5, 6]]),
            _artifact("family_b", [[1, 7, 8, 9, 10, 11]]),
        )
    )

    assert len(decision.number_scores) == 49
    assert len(decision.deterministic_ranking) == 49
    assert all(len(family.number_presence) == 49 for family in decision.families)
    assert all(value in (0, 1) for family in decision.families for value in family.number_presence)
    assert decision.number_scores[0] == 2
    assert decision.number_scores[48] == 0


def test_score_descending_numeric_ascending_ranking_and_final_ticket() -> None:
    artifacts = [
        _artifact(f"family_{index}", [[26, 29, 12, 4, 16, 24, 25, 47]])
        for index in range(1, 4)
    ]
    artifacts.extend(
        (
            _artifact("family_4", [[26, 29, 12]]),
            _artifact("family_5", [[26, 29]]),
            _artifact("family_6", [[30]]),
            _artifact("family_7", [[31]]),
        )
    )

    decision = build_canonical_consensus(artifacts)

    assert decision.deterministic_ranking[:8] == (26, 29, 12, 4, 16, 24, 25, 47)
    assert decision.selected_ranked_numbers == (26, 29, 12, 4, 16, 24)
    assert decision.final_ticket == (4, 12, 16, 24, 26, 29)
    assert _number_scores(decision)[23] == 3
    assert _number_scores(decision)[24] == 3
    assert _number_scores(decision)[46] == 3


def test_extra_tickets_inside_an_existing_family_cannot_increase_its_influence() -> None:
    base = build_canonical_consensus(
        (
            _artifact("family_a", [[20, 21, 22, 23, 24, 25]]),
            _artifact("family_b", [[26, 27, 28, 29, 30, 31]]),
        )
    )
    extended = build_canonical_consensus(
        (
            _artifact(
                "family_a",
                [
                    [20, 21, 22, 23, 24, 25],
                    [20, 20, 32, 33, 34, 35],
                    [36, 37, 38, 39, 40, 41],
                ],
            ),
            _artifact("family_b", [[26, 27, 28, 29, 30, 31]]),
        )
    )

    assert base.number_scores[19] == 1
    assert extended.number_scores[19] == 1
    assert max(extended.number_scores) == 1


def test_payload_exposes_rule_metadata_provenance_and_no_outcome_dependency() -> None:
    payload = build_canonical_consensus_payload(
        [_artifact("family_a", [[1, 2, 3, 4, 5, 6]], prediction_path="fixture://a")]
    )

    assert payload["consensus_method"] == CANONICAL_CONSENSUS_METHOD_ID
    assert payload["prediction_temporal_class"] == "PRE_DRAW"
    assert payload["input_cutoff"] == {
        "draw_number": "115000086",
        "draw_date": "2026-09-08",
    }
    assert payload["family_definitions"]
    assert payload["family_scores"]
    assert len(cast(dict[str, int], payload["number_scores"])) == 49
    assert payload["final_ticket_count"] == 1
    assert payload["outcome_dependence"] == "NONE"
    assert "outcome" not in payload
    assert "result" not in payload
    input_artifacts = cast(list[dict[str, object]], payload["input_artifacts"])
    assert input_artifacts[0]["artifact_ref"] == "fixture://a"


def test_outcome_fields_are_not_consumed() -> None:
    plain = build_canonical_consensus_payload(
        [_artifact("family_a", [[1, 2, 3, 4, 5, 6]])]
    )
    with_outcome_fields = build_canonical_consensus_payload(
        [
            _artifact(
                "family_a",
                [[1, 2, 3, 4, 5, 6]],
                outcome={"main_numbers": [44, 45, 46, 47, 48, 49]},
                result={"score": 999},
            )
        ]
    )

    assert with_outcome_fields["number_scores"] == plain["number_scores"]
    assert with_outcome_fields["deterministic_ranking"] == plain["deterministic_ranking"]
    assert with_outcome_fields["final_recommended_ticket"] == plain["final_recommended_ticket"]


def test_post_draw_artifact_is_rejected() -> None:
    with pytest.raises(CanonicalConsensusInputError, match="PRE_DRAW"):
        build_canonical_consensus(
            [_artifact("family_a", [[1, 2, 3, 4, 5, 6]], prediction_temporal_class="POST_DRAW")]
        )


def test_frozen_115000087_pre_draw_inputs_reproduce_approved_ticket() -> None:
    paths = sorted(FROZEN_UPSTREAM_ROOT.glob("*/*.json"))
    assert len(paths) == 11
    artifacts: list[dict[str, object]] = []
    for path in paths:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)
        artifact = cast(dict[str, object], parsed)
        artifact["prediction_path"] = str(path)
        artifacts.append(artifact)

    payload = build_canonical_consensus_payload(artifacts)

    assert payload["family_count"] == 7
    assert payload["final_recommended_ticket"] == [4, 12, 16, 24, 26, 29]
    ranking = cast(list[dict[str, object]], payload["deterministic_ranking"])
    assert [(row["number"], row["score"]) for row in ranking[:8]] == [
        (26, 5),
        (29, 5),
        (12, 4),
        (4, 3),
        (16, 3),
        (24, 3),
        (25, 3),
        (47, 3),
    ]


def test_persisted_consensus_uses_existing_draw_directory_and_is_not_scored_as_prediction(
    tmp_path: Path,
) -> None:
    artifacts = (
        _artifact("family_a", [[1, 2, 3, 4, 5, 6]]),
        _artifact("legacy_biglotto__test_a__hash", [[1, 7, 8, 9, 10, 11]]),
    )
    for artifact in artifacts:
        save_strategy_prediction(tmp_path, artifact)

    expected_ids = tuple(cast(str, artifact["strategy_id"]) for artifact in artifacts)
    consensus_path = persist_canonical_consensus_if_ready(
        tmp_path,
        "115000087",
        expected_strategy_ids=expected_ids,
    )

    assert consensus_path == canonical_consensus_path(tmp_path, "115000087")
    assert consensus_path.is_file()
    assert len(iter_prediction_files(tmp_path, "115000087")) == 2
    assert persist_canonical_consensus_if_ready(
        tmp_path,
        "115000087",
        expected_strategy_ids=expected_ids,
    ) == consensus_path

    _outcome_path, score_paths = update_outcome(
        tmp_path,
        draw_number="115000087",
        main_numbers=(20, 21, 22, 23, 24, 25),
        special_number=49,
        source="test-owner-entry",
    )
    assert len(score_paths) == 2
