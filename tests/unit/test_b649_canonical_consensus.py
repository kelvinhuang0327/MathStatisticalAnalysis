"""Unit checks for the approved B649 eleven-stream consensus contract."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import cast

import pytest

from lottolab.domain.b649_canonical_consensus import (
    AGGREGATION_UNIT,
    CANONICAL_CONSENSUS_METHOD_ID,
    CORRELATED_FAMILY_POLICY,
    SCORE_DENOMINATOR,
    STREAM_WEIGHT_POLICY,
    TIE_BREAK,
    CanonicalConsensusInputError,
    StreamConsensusInput,
    build_canonical_consensus,
)

CREATED_AT = datetime(2026, 9, 8, 22, 7, tzinfo=UTC)


def _stream(
    strategy_id: str,
    tickets: tuple[tuple[int, ...], ...],
    *,
    created_at: datetime = CREATED_AT,
) -> StreamConsensusInput:
    return StreamConsensusInput(
        strategy_id=strategy_id,
        strategy_version="v0.1",
        native_ticket_count=len(tickets),
        prediction_run_id=f"run-{strategy_id}",
        source_relative_path=f"predictions/115000087/{strategy_id}/run.json",
        source_sha256=hashlib.sha256(strategy_id.encode()).hexdigest(),
        prediction_created_at=created_at,
        tickets=tickets,
    )


def test_contract_metadata_is_the_cto_approved_stream_policy() -> None:
    assert CANONICAL_CONSENSUS_METHOD_ID == "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS"
    assert AGGREGATION_UNIT == "NUMBER_LEVEL"
    assert STREAM_WEIGHT_POLICY == "EQUAL_STREAM_WEIGHT"
    assert CORRELATED_FAMILY_POLICY == "FULL_VOTE_PER_FROZEN_STREAM_NO_FAMILY_NORMALIZATION"
    assert SCORE_DENOMINATOR == 66
    assert TIE_BREAK == "SUPPORT_UNITS_DESC_NUMBER_ASC"


def test_native_ticket_positions_are_normalized_to_equal_stream_mass() -> None:
    decision = build_canonical_consensus(
        (
            _stream(
                "stream_two",
                (
                    (1, 2, 3, 4, 5, 6),
                    (1, 7, 8, 9, 10, 11),
                ),
            ),
            _stream("stream_one", ((1, 12, 13, 14, 15, 16),)),
        )
    )

    # Each stream contributes 6 * 6 = 36 support units in total, regardless
    # of whether its native prediction contains one or two tickets.
    assert sum(decision.support_units) == 72
    assert decision.number_scores[0] == 12
    assert decision.number_scores[6] == 3
    assert decision.number_scores[11] == 6


def test_repeated_ticket_positions_are_counted_and_duplicate_numbers_are_rejected() -> None:
    repeated = _stream(
        "repeated",
        (
            (20, 21, 22, 23, 24, 25),
            (20, 21, 22, 23, 24, 25),
        ),
    )
    decision = build_canonical_consensus((repeated,))
    assert decision.number_scores[19] == 6
    assert decision.final_ticket == (20, 21, 22, 23, 24, 25)

    with pytest.raises(CanonicalConsensusInputError, match="legal six-number"):
        _stream("illegal", ((1, 1, 2, 3, 4, 5),))


def test_ranking_is_full_49_number_support_descending_then_numeric_ascending() -> None:
    decision = build_canonical_consensus(
        (
            _stream("a", ((26, 29, 12, 4, 16, 24),)),
            _stream("b", ((26, 29, 12, 4, 16, 25),)),
        )
    )

    assert len(decision.deterministic_ranking) == 49
    assert decision.deterministic_ranking[:8] == (4, 12, 16, 26, 29, 24, 25, 1)
    assert decision.final_ticket == (4, 12, 16, 24, 26, 29)
    rows = decision.decision_fields()["final_decision_ranking"]
    assert isinstance(rows, list)
    assert rows[0] == {"rank": 1, "number": 4, "support_units": 12}


def test_stream_order_does_not_change_decision_or_manifest() -> None:
    streams = (
        _stream("z", ((1, 2, 3, 4, 5, 6),)),
        _stream("a", ((7, 8, 9, 10, 11, 12),)),
    )
    left = build_canonical_consensus(streams)
    right = build_canonical_consensus(tuple(reversed(streams)))
    assert left == right
    input_rows = cast(list[dict[str, object]], left.decision_fields()["stream_inputs"])
    assert [row["strategy_id"] for row in input_rows] == [
        "a",
        "z",
    ]


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"native_ticket_count": 4}, "divide"),
        ({"prediction_created_at": datetime(2026, 9, 8, 22, 7)}, "timezone-aware"),
        ({"source_sha256": "bad"}, "SHA-256"),
    ],
)
def test_stream_identity_and_temporal_fields_are_strict(
    kwargs: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "strategy_id": "strict",
        "strategy_version": "v0.1",
        "native_ticket_count": 1,
        "prediction_run_id": "run-strict",
        "source_relative_path": "predictions/run.json",
        "source_sha256": "a" * 64,
        "prediction_created_at": CREATED_AT,
        "tickets": ((1, 2, 3, 4, 5, 6),),
    }
    values.update(kwargs)
    with pytest.raises(CanonicalConsensusInputError, match=message):
        StreamConsensusInput(**values)  # type: ignore[arg-type]


def test_duplicate_stream_ids_are_rejected() -> None:
    stream = _stream("same", ((1, 2, 3, 4, 5, 6),))
    with pytest.raises(CanonicalConsensusInputError, match="unique"):
        build_canonical_consensus((stream, stream))
