"""Focused tests for deterministic pre-outcome B649 portfolio materialization."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from lottolab.evidence.canonical_json import canonical_file_bytes
from lottolab.infrastructure.b649_operational_portfolio_materializer import (
    PortfolioAuthorityConflictError,
    PortfolioMaterializationError,
    PortfolioMaterializationResult,
    materialize_portfolios,
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


def _write_candidates(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for index, strategy_id in enumerate(STRATEGY_IDS):
        path = root / "predictions" / TARGET_DRAW / strategy_id / "prediction.json"
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(canonical_file_bytes(_prediction(strategy_id, index)))
        path.chmod(0o600)
        paths.append(path)
    return tuple(paths)


def _materialize(
    candidates: tuple[Path, ...],
    destination: Path,
    upstream_locator: str,
    pre_outcome_seal_check: Callable[[], bool] | None = None,
) -> PortfolioMaterializationResult:
    return materialize_portfolios(
        candidate_paths=candidates,
        expected_strategy_ids=STRATEGY_IDS,
        target_draw_number=TARGET_DRAW,
        target_draw_date=TARGET_DATE,
        scheduled_at=SCHEDULED_AT,
        upstream_authority_locator=upstream_locator,
        destination=destination,
        pre_outcome_seal_check=pre_outcome_seal_check,
    )


def _bucket(payload: dict[str, object], name: str) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], payload[name])


def test_materializes_exact_nested_buckets_and_preserves_pre_outcome_provenance(
    tmp_path: Path,
) -> None:
    candidates = _write_candidates(tmp_path / "operation")
    destination = tmp_path / "authority" / "final_portfolio_payload.json"
    upstream_locator = str(tmp_path / "exact-upstream" / TARGET_DRAW)

    result = _materialize(candidates, destination, upstream_locator)
    payload = result.payload

    assert result.status == "CREATED"
    assert len(_bucket(payload, "k5")) == 5
    assert len(_bucket(payload, "k10")) == 10
    assert len(_bucket(payload, "k20")) == 20
    assert _bucket(payload, "k5") == _bucket(payload, "k10")[:5]
    assert _bucket(payload, "k10") == _bucket(payload, "k20")[:10]
    assert len(
        {
            tuple(cast(list[int], row["predicted_numbers"]))
            for row in _bucket(payload, "k20")
        }
    ) == 20
    assert payload["candidate_count"] == 11
    assert payload["outcome_used"] == "NO"
    assert payload["target_result_used"] is False
    assert payload["upstream_authority_locator"] == upstream_locator
    assert payload["portfolio_authority_locator"] == str(destination)
    assert destination.read_bytes() == canonical_file_bytes(payload)


def test_materialization_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path / "operation")
    first_destination = tmp_path / "first" / "final.json"
    second_destination = tmp_path / "second" / "final.json"
    upstream_locator = str(tmp_path / "upstream" / TARGET_DRAW)

    first = _materialize(candidates, first_destination, upstream_locator)
    second = _materialize(candidates, second_destination, upstream_locator)
    retry = _materialize(candidates, first_destination, upstream_locator)

    assert first.payload["k5"] == second.payload["k5"]
    assert first.payload["k10"] == second.payload["k10"]
    assert first.payload["k20"] == second.payload["k20"]
    assert retry.status == "ALREADY_PRESENT"
    assert retry.payload == first.payload


def test_outcome_or_scoring_input_is_rejected_without_writing_authority(
    tmp_path: Path,
) -> None:
    operation = tmp_path / "operation"
    candidates = _write_candidates(operation)
    first = candidates[0]
    raw = json.loads(first.read_text(encoding="utf-8"))
    raw["result"] = {"score": 6}
    first.write_bytes(json.dumps(raw, separators=(",", ":")).encode("utf-8"))
    destination = tmp_path / "authority" / "final.json"
    upstream_locator = str(tmp_path / "upstream" / TARGET_DRAW)

    with pytest.raises(PortfolioMaterializationError, match="forbidden"):
        _materialize(candidates, destination, upstream_locator)

    assert not destination.exists()


def test_competing_or_changed_authority_is_never_overwritten(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path / "operation")
    destination = tmp_path / "authority" / "final.json"
    upstream_locator = str(tmp_path / "upstream" / TARGET_DRAW)
    first = _materialize(candidates, destination, upstream_locator)
    original = destination.read_bytes()
    destination.write_bytes(b'{"different":true}\n')

    with pytest.raises(PortfolioAuthorityConflictError):
        _materialize(candidates, destination, upstream_locator)

    assert destination.read_bytes() != original
    assert first.payload["portfolio_authority_locator"] == str(destination)


def test_candidate_cutoff_must_precede_target(tmp_path: Path) -> None:
    operation = tmp_path / "operation"
    candidates = _write_candidates(operation)
    first = candidates[0]
    raw = json.loads(first.read_text(encoding="utf-8"))
    raw["history_cutoff"] = {"draw_number": TARGET_DRAW, "draw_date": TARGET_DATE}
    first.write_bytes(json.dumps(raw, separators=(",", ":")).encode("utf-8"))
    upstream_locator = str(tmp_path / "upstream" / TARGET_DRAW)

    with pytest.raises(PortfolioMaterializationError, match="cutoff"):
        _materialize(candidates, tmp_path / "authority" / "final.json", upstream_locator)



def test_first_materialization_is_strictly_pre_outcome_at_publish(
    tmp_path: Path,
) -> None:
    candidates = _write_candidates(tmp_path / "operation")
    destination = tmp_path / "authority" / "final.json"
    checks = iter((True, True))

    result = _materialize(
        candidates,
        destination,
        str(tmp_path / "upstream" / TARGET_DRAW),
        pre_outcome_seal_check=lambda: next(checks),
    )

    assert result.status == "CREATED"
    assert destination.exists()


def test_first_materialization_after_outcome_is_not_created(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path / "operation")
    destination = tmp_path / "authority" / "final.json"
    upstream_locator = str(tmp_path / "upstream" / TARGET_DRAW)

    result = _materialize(
        candidates,
        destination,
        upstream_locator,
        pre_outcome_seal_check=lambda: False,
    )

    assert result.status == "NOT_CREATED_AFTER_OUTCOME"
    assert result.payload["pre_outcome_forecast_status"] == "NOT_CREATED_AFTER_OUTCOME"
    assert result.payload["post_outcome_scoring_status"] == "NOT_DUE"
    assert result.payload["next_draw_rollover_status"] == "NOT_DUE"
    assert result.payload["upstream_authority_locator"] == upstream_locator
    assert not destination.exists()


def test_temporal_boundary_flip_before_publish_fails_closed(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path / "operation")
    destination = tmp_path / "authority" / "final.json"
    checks = iter((True, False))

    result = _materialize(
        candidates,
        destination,
        str(tmp_path / "upstream" / TARGET_DRAW),
        pre_outcome_seal_check=lambda: next(checks),
    )

    assert result.status == "NOT_CREATED_AFTER_OUTCOME"
    assert not destination.exists()
    assert not tuple(destination.parent.glob("*.tmp"))


def test_existing_sealed_portfolio_is_reused_after_outcome(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path / "operation")
    destination = tmp_path / "authority" / "final.json"
    upstream_locator = str(tmp_path / "upstream" / TARGET_DRAW)
    first = _materialize(
        candidates,
        destination,
        upstream_locator,
        pre_outcome_seal_check=lambda: True,
    )
    original = destination.read_bytes()

    retry = _materialize(
        candidates,
        destination,
        upstream_locator,
        pre_outcome_seal_check=lambda: False,
    )

    assert first.status == "CREATED"
    assert retry.status == "ALREADY_PRESENT"
    assert retry.payload == first.payload
    assert destination.read_bytes() == original
