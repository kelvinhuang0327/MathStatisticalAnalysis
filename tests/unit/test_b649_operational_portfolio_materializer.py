"""Focused tests for deterministic pre-outcome B649 portfolio materialization."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from lottolab.evidence.canonical_json import canonical_file_bytes, sha256_hex
from lottolab.infrastructure.b649_operational_portfolio_materializer import (
    PersistedPortfolioCandidate,
    PortfolioAuthorityConflictError,
    PortfolioMaterializationError,
    PortfolioMaterializationResult,
    materialize_portfolios,
    read_portfolio_if_present,
)

TARGET_DRAW = "209900001"
TARGET_DATE = "2099-01-02"
SCHEDULED_AT = "2099-01-02T12:30:00+00:00"
CUTOFF = {"draw_number": "209900000", "draw_date": "2099-01-01"}
STRATEGY_IDS = tuple(f"stream-{index:02d}" for index in range(11))


def _ticket(start: int) -> tuple[int, ...]:
    return tuple(range(start, start + 6))


def _prediction(strategy_id: str, index: int) -> dict[str, object]:
    tickets = (_ticket(index * 2 + 1), _ticket(index * 2 + 2), (40, 41, 42, 43, 44, 45))
    return {
        "schema_version": "b649-operational-prediction-v1",
        "task_id": "B649_OPERATIONAL_PREDICTION_LOOP_R1",
        "prediction_run_id": f"{TARGET_DRAW}-{strategy_id}-run",
        "lottery_type": "BIG_LOTTO",
        "draw_number": TARGET_DRAW,
        "draw_date": TARGET_DATE,
        "scheduled_at": SCHEDULED_AT,
        "prediction_created_at": f"2099-01-02T10:{index:02d}:00+00:00",
        "strategy_id": strategy_id,
        "strategy_version": "v1",
        "strategy_config": {},
        "history_cutoff": CUTOFF,
        "history_draw_count": 100,
        "history_sha256": "a" * 64,
        "history_caveat": "YES",
        "prediction_temporal_class": "PRE_DRAW",
        "availability": "AVAILABLE",
        "native_ticket_count": len(tickets),
        "tickets": [
            {"ticket_position": position, "predicted_numbers": list(ticket)}
            for position, ticket in enumerate(tickets, start=1)
        ],
    }


def _candidates(
    overrides: dict[str, object] | None = None,
    *,
    overridden_strategy: str = STRATEGY_IDS[0],
) -> tuple[PersistedPortfolioCandidate, ...]:
    result: list[PersistedPortfolioCandidate] = []
    for index, strategy_id in enumerate(STRATEGY_IDS):
        payload = _prediction(strategy_id, index)
        if overrides is not None and strategy_id == overridden_strategy:
            payload.update(overrides)
        raw = canonical_file_bytes(payload)
        result.append(
            PersistedPortfolioCandidate(
                strategy_id=strategy_id,
                source_relative_path=f"predictions/{TARGET_DRAW}/{strategy_id}/prediction.json",
                raw_bytes=raw,
                payload=payload,
            )
        )
    return tuple(result)


def _materialize(
    candidates: tuple[PersistedPortfolioCandidate, ...],
    destination: Path,
    pre_outcome_seal_check: Callable[[], bool] | None = None,
) -> PortfolioMaterializationResult:
    return materialize_portfolios(
        candidates=candidates,
        expected_strategy_ids=STRATEGY_IDS,
        target_draw_number=TARGET_DRAW,
        target_draw_date=TARGET_DATE,
        scheduled_at=SCHEDULED_AT,
        destination=destination,
        pre_outcome_seal_check=pre_outcome_seal_check,
    )


def _bucket(payload: dict[str, object], name: str) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], payload[name])


LIFECYCLE_OWNED_KEYS = ("post_outcome_scoring_status", "next_draw_rollover_status")


def test_materializes_exact_nested_buckets_and_preserves_pre_outcome_provenance(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "authority" / "final_portfolio_payload.json"

    result = _materialize(_candidates(), destination)
    payload = result.payload

    assert result.status == "CREATED"
    assert len(_bucket(payload, "k5")) == 5
    assert len(_bucket(payload, "k10")) == 10
    assert len(_bucket(payload, "k20")) == 20
    assert _bucket(payload, "k5") == _bucket(payload, "k10")[:5]
    assert _bucket(payload, "k10") == _bucket(payload, "k20")[:10]
    assert (
        len(
            {
                tuple(cast(list[int], row["predicted_numbers"]))
                for row in _bucket(payload, "k20")
            }
        )
        == 20
    )
    assert payload["candidate_count"] == 11
    assert payload["outcome_used"] == "NO"
    assert payload["target_result_used"] is False
    assert payload["portfolio_authority_locator"] == str(destination)
    assert payload["portfolio_status"] == "COMPLETE"
    assert destination.read_bytes() == canonical_file_bytes(payload)


def test_payload_and_health_have_no_outcome_or_rollover_ownership_keys(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "authority" / "final.json"

    result = _materialize(_candidates(), destination)

    for key in LIFECYCLE_OWNED_KEYS:
        assert key not in result.payload
        assert key not in result.health_dict()
    assert "pre_outcome_forecast_status" not in result.payload


def test_health_dict_nests_under_no_extra_wrapper_and_matches_payload(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "authority" / "final.json"

    result = _materialize(_candidates(), destination)
    health = result.health_dict()

    assert health["status"] == "CREATED"
    assert health["portfolio_status"] == "COMPLETE"
    assert health["k5"] == result.payload["k5"]
    assert health["k10"] == result.payload["k10"]
    assert health["k20"] == result.payload["k20"]
    assert health["candidate_count"] == 11


def test_materialization_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    candidates = _candidates()
    first_destination = tmp_path / "first" / "final.json"
    second_destination = tmp_path / "second" / "final.json"

    first = _materialize(candidates, first_destination)
    second = _materialize(candidates, second_destination)
    retry = _materialize(candidates, first_destination)

    assert first.payload["k5"] == second.payload["k5"]
    assert first.payload["k10"] == second.payload["k10"]
    assert first.payload["k20"] == second.payload["k20"]
    assert retry.status == "ALREADY_PRESENT"
    assert retry.payload == first.payload


def test_reuse_never_touches_candidates_or_rebuilds_payload(tmp_path: Path) -> None:
    """Regression guard for the known donor defect: reuse must never rebuild
    ``_build_payload`` and byte-compare. Passing an empty candidate sequence
    on the second call would raise (missing usable PRE_DRAW candidates) if
    the reuse path ever touched candidates again; it must not.
    """

    destination = tmp_path / "authority" / "final.json"
    first = _materialize(_candidates(), destination)

    retry = materialize_portfolios(
        candidates=(),
        expected_strategy_ids=STRATEGY_IDS,
        target_draw_number=TARGET_DRAW,
        target_draw_date=TARGET_DATE,
        scheduled_at=SCHEDULED_AT,
        destination=destination,
    )

    assert retry.status == "ALREADY_PRESENT"
    assert retry.payload == first.payload


def test_valid_existing_authority_is_reused_even_if_candidates_would_differ(
    tmp_path: Path,
) -> None:
    """A structurally valid, already-sealed authority is reused as-is -- it is
    never recomputed and byte-compared against what fresh candidates would
    produce, even when those candidates now describe different tickets.
    """

    destination = tmp_path / "authority" / "final.json"
    first = _materialize(_candidates(), destination)

    mutated = _candidates(overrides={"prediction_run_id": f"{TARGET_DRAW}-changed-run"})
    retry = _materialize(mutated, destination)

    assert retry.status == "ALREADY_PRESENT"
    assert retry.payload == first.payload


def test_structurally_invalid_existing_authority_is_rejected_not_silently_reused(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "authority" / "final.json"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b'{"schema_version":"wrong"}\n')
    original = destination.read_bytes()

    with pytest.raises(PortfolioAuthorityConflictError):
        _materialize(_candidates(), destination)

    assert destination.read_bytes() == original


def test_existing_authority_for_a_different_target_is_rejected(tmp_path: Path) -> None:
    destination = tmp_path / "authority" / "final.json"
    _materialize(_candidates(), destination)

    with pytest.raises(PortfolioAuthorityConflictError):
        materialize_portfolios(
            candidates=_candidates(),
            expected_strategy_ids=STRATEGY_IDS,
            target_draw_number="209900002",
            target_draw_date="2099-01-09",
            scheduled_at="2099-01-09T12:30:00+00:00",
            destination=destination,
        )


def test_outcome_or_scoring_input_is_rejected_without_writing_authority(
    tmp_path: Path,
) -> None:
    candidates = _candidates(overrides={"result": {"score": 6}})
    destination = tmp_path / "authority" / "final.json"

    with pytest.raises(PortfolioMaterializationError, match="forbidden"):
        _materialize(candidates, destination)

    assert not destination.exists()


def test_candidate_cutoff_must_precede_target(tmp_path: Path) -> None:
    candidates = _candidates(
        overrides={"history_cutoff": {"draw_number": TARGET_DRAW, "draw_date": TARGET_DATE}}
    )
    destination = tmp_path / "authority" / "final.json"

    with pytest.raises(PortfolioMaterializationError, match="cutoff"):
        _materialize(candidates, destination)

    assert not destination.exists()


def test_first_materialization_is_strictly_pre_outcome_at_publish(tmp_path: Path) -> None:
    destination = tmp_path / "authority" / "final.json"
    checks = iter((True, True))

    result = _materialize(_candidates(), destination, pre_outcome_seal_check=lambda: next(checks))

    assert result.status == "CREATED"
    assert destination.exists()


def test_first_materialization_after_outcome_is_not_created(tmp_path: Path) -> None:
    destination = tmp_path / "authority" / "final.json"

    result = _materialize(_candidates(), destination, pre_outcome_seal_check=lambda: False)

    assert result.status == "NOT_CREATED_AFTER_OUTCOME"
    assert result.payload["portfolio_status"] == "NOT_CREATED_AFTER_OUTCOME"
    for key in LIFECYCLE_OWNED_KEYS:
        assert key not in result.payload
    assert not destination.exists()


def test_temporal_boundary_flip_before_publish_fails_closed(tmp_path: Path) -> None:
    destination = tmp_path / "authority" / "final.json"
    checks = iter((True, False))

    result = _materialize(_candidates(), destination, pre_outcome_seal_check=lambda: next(checks))

    assert result.status == "NOT_CREATED_AFTER_OUTCOME"
    assert not destination.exists()
    assert not tuple(destination.parent.glob("*.tmp"))


def test_existing_sealed_portfolio_is_reused_after_outcome(tmp_path: Path) -> None:
    destination = tmp_path / "authority" / "final.json"
    first = _materialize(_candidates(), destination, pre_outcome_seal_check=lambda: True)
    original = destination.read_bytes()

    retry = _materialize(_candidates(), destination, pre_outcome_seal_check=lambda: False)

    assert first.status == "CREATED"
    assert retry.status == "ALREADY_PRESENT"
    assert retry.payload == first.payload
    assert destination.read_bytes() == original


def test_read_portfolio_if_present_is_read_only(tmp_path: Path) -> None:
    destination = tmp_path / "authority" / "final.json"

    assert read_portfolio_if_present(destination) is None
    assert not destination.parent.exists()

    created = _materialize(_candidates(), destination)
    read_back = read_portfolio_if_present(destination)

    assert read_back is not None
    assert read_back.status == "ALREADY_PRESENT"
    assert read_back.payload == created.payload
    assert destination.read_bytes() == canonical_file_bytes(created.payload)


def test_insufficient_distinct_tickets_raises_portfolio_error(tmp_path: Path) -> None:
    """The selector's own ValueError (too few distinct tickets for K5/K10/K20)
    must surface as this module's own error type, not a raw ValueError.
    """

    sparse: list[PersistedPortfolioCandidate] = []
    shared_ticket = [{"ticket_position": 1, "predicted_numbers": [1, 2, 3, 4, 5, 6]}]
    for index, strategy_id in enumerate(STRATEGY_IDS):
        payload = _prediction(strategy_id, index)
        payload["native_ticket_count"] = 1
        payload["tickets"] = shared_ticket
        sparse.append(
            PersistedPortfolioCandidate(
                strategy_id=strategy_id,
                source_relative_path=f"predictions/{TARGET_DRAW}/{strategy_id}/prediction.json",
                raw_bytes=canonical_file_bytes(payload),
                payload=payload,
            )
        )
    destination = tmp_path / "authority" / "final.json"

    with pytest.raises(PortfolioMaterializationError, match="distinct candidate tickets"):
        _materialize(tuple(sparse), destination)

    assert not destination.exists()


def test_candidate_manifest_records_exact_source_and_digest(tmp_path: Path) -> None:
    candidates = _candidates()
    destination = tmp_path / "authority" / "final.json"

    result = _materialize(candidates, destination)

    manifest = cast(list[dict[str, object]], result.payload["candidate_manifest"])
    by_strategy = {str(entry["strategy_id"]): entry for entry in manifest}
    for candidate in candidates:
        entry = by_strategy[candidate.strategy_id]
        assert entry["prediction_path"] == candidate.source_relative_path
        assert entry["prediction_sha256"] == sha256_hex(candidate.raw_bytes)
