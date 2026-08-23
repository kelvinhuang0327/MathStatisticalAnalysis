"""Acceptance coverage for the isolated Big Lotto pair-rule shadow."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import tools.b649_pair_rule_forward_shadow as shadow_module
from pytest import MonkeyPatch
from tools.b649_operational_prediction_loop import (
    LOTTERY_TYPE,
    HistorySnapshot,
    PredictionTarget,
)

NOW = datetime(2099, 1, 2, 10, 0, tzinfo=UTC)
SCHEDULED = datetime(2099, 1, 2, 12, 30, tzinfo=UTC)
HISTORY = HistorySnapshot(
    rows=(),
    cutoff_draw="209900000",
    cutoff_date="2099-01-01",
    draw_count=0,
    history_sha256="h" * 64,
)


def _portfolio_hash(tickets: tuple[tuple[int, ...], ...]) -> str:
    encoded = (
        json.dumps([list(ticket) for ticket in tickets], separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _target() -> PredictionTarget:
    return PredictionTarget(
        lottery_type=LOTTERY_TYPE,
        draw_number="209900001",
        draw_date="2099-01-02",
        scheduled_at=SCHEDULED.isoformat(),
    )


def _fake_component(
    strategy_id: str,
    *,
    allocation_count: int,
) -> tuple[dict[str, object], tuple[tuple[int, ...], ...]]:
    native_count = 5 if "orthogonal" in strategy_id else 10
    adapter_class = (
        "lottolab.strategies.adapters.biglotto_orthogonal_5bet:BigLottoOrthogonal5BetAdapter"
        if native_count == 5
        else "lottolab.strategies.adapters.biglotto_batch18:BigLottoColdPool15Adapter"
    )
    ordered = tuple(
        tuple(range((position % 40) + 1, (position % 40) + 7)) for position in range(20)
    )
    return (
        {
            "strategy_id": strategy_id,
            "adapter_class": adapter_class,
            "adapter_version": "v0.1",
            "native_ticket_count": native_count,
            "ordered20_constructor_version": "strategy_preserving_20_ticket/v1",
            "ordered20_seed_digest": "s" * 64,
            "allocation_prefix_count": allocation_count,
            "allocation_prefix_tickets": [list(ticket) for ticket in ordered[:allocation_count]],
            "ordered20_count": 20,
            "ordered20_sha256": _portfolio_hash(ordered),
        },
        ordered,
    )


def _fake_builder(
    strategy_id: str,
    *,
    history: HistorySnapshot,
    target: PredictionTarget,
    allocation_count: int,
) -> tuple[dict[str, object], tuple[tuple[int, ...], ...]]:
    del history, target
    return _fake_component(strategy_id, allocation_count=allocation_count)


def test_authority_is_the_exact_five_candidate_freeze() -> None:
    authority = shadow_module.load_shadow_authority()

    assert authority.freeze_sha256 == shadow_module.EXPECTED_FREEZE_SHA256
    assert [candidate.candidate_id for candidate in authority.candidates] == list(
        shadow_module.FROZEN_CANDIDATE_IDS
    )
    assert [candidate.candidate_id for candidate in authority.enabled_candidates] == list(
        shadow_module.READY_CANDIDATE_IDS
    )
    assert [candidate.candidate_id for candidate in authority.migration_blocked_candidates] == list(
        shadow_module.MIGRATION_BLOCKED_CANDIDATE_IDS
    )


def test_predraw_composes_only_ready_candidates_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(shadow_module, "_build_component", _fake_builder)
    shadow = shadow_module.PairRuleForwardShadow(tmp_path)

    first = shadow.run_pre_draw(_target(), HISTORY, observed_at=NOW)
    prediction_root = tmp_path / "predictions" / "209900001"

    assert first["status"] == "PREDRAW_COMPLETE"
    assert first["deadline_status"] == "READY"
    assert first["available_enabled_candidate_ids"] == list(shadow_module.READY_CANDIDATE_IDS)
    assert first["missing_enabled_candidate_ids"] == []
    assert first["migration_blocked_candidate_ids"] == list(
        shadow_module.MIGRATION_BLOCKED_CANDIDATE_IDS
    )
    assert sorted(path.name for path in prediction_root.glob("*.json")) == sorted(
        f"{candidate_id}.json" for candidate_id in shadow_module.READY_CANDIDATE_IDS
    )

    for candidate_id in shadow_module.READY_CANDIDATE_IDS:
        payload = json.loads((prediction_root / f"{candidate_id}.json").read_text(encoding="utf-8"))
        candidate = next(
            item
            for item in shadow_module.load_shadow_authority().candidates
            if item.candidate_id == candidate_id
        )
        assert payload["status"] == "AVAILABLE"
        assert len(payload["composed_ordered_tickets"]) == candidate.budget
        assert payload["component_a"]["allocation_prefix_count"] == candidate.a_tickets
        assert payload["component_b"]["allocation_prefix_count"] == candidate.b_tickets
        assert payload["prediction_temporal_class"] == "PRE_DRAW"
        assert payload["runtime_registry_sha256"] == shadow.load_authority().runtime_registry_sha256
        assert len(payload["a_only_same_budget_comparator_tickets"]) == candidate.budget
        assert len(payload["b_only_same_budget_comparator_tickets"]) == candidate.budget

    before = {path: path.read_bytes() for path in prediction_root.glob("*.json")}
    second = shadow.run_pre_draw(_target(), HISTORY, observed_at=NOW)
    after = {path: path.read_bytes() for path in prediction_root.glob("*.json")}
    assert second["available_enabled_candidate_ids"] == first["available_enabled_candidate_ids"]
    assert after == before


def test_deadline_records_missed_without_backfill_or_blocked_candidate_writes(
    tmp_path: Path,
) -> None:
    shadow = shadow_module.PairRuleForwardShadow(tmp_path)
    target = _target()

    health = shadow.run_pre_draw(
        target,
        HISTORY,
        observed_at=datetime(2099, 1, 2, 12, 31, tzinfo=UTC),
    )

    assert health["deadline_status"] == "MISSED_DEADLINE_NO_BACKFILL"
    assert health["available_enabled_candidate_ids"] == []
    assert health["missing_enabled_candidate_ids"] == list(shadow_module.READY_CANDIDATE_IDS)
    prediction_root = tmp_path / "predictions" / target.draw_number
    for candidate_id in shadow_module.READY_CANDIDATE_IDS:
        payload = json.loads((prediction_root / f"{candidate_id}.json").read_text(encoding="utf-8"))
        assert payload["status"] == "MISSED_DEADLINE_NO_BACKFILL"
    for candidate_id in shadow_module.MIGRATION_BLOCKED_CANDIDATE_IDS:
        assert not (prediction_root / f"{candidate_id}.json").exists()


def test_postdraw_scores_existing_shadow_predictions_only(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(shadow_module, "_build_component", _fake_builder)
    shadow = shadow_module.PairRuleForwardShadow(tmp_path)
    target = _target()
    shadow.run_pre_draw(target, HISTORY, observed_at=NOW)
    outcome = {
        "lottery_type": LOTTERY_TYPE,
        "draw_number": target.draw_number,
        "draw_date": target.draw_date,
        "main_numbers": [1, 2, 3, 4, 5, 6],
        "special_number": 7,
        "source": "test",
    }

    first = shadow.run_post_draw(target, outcome, observed_at=SCHEDULED)
    second = shadow.run_post_draw(target, outcome, observed_at=SCHEDULED)

    assert first["status"] == "POSTDRAW_COMPLETE"
    assert first["scored_enabled_candidate_ids"] == list(shadow_module.READY_CANDIDATE_IDS)
    assert second["scored_enabled_candidate_ids"] == first["scored_enabled_candidate_ids"]
    score_root = tmp_path / "scores" / target.draw_number
    assert len(tuple(score_root.glob("*.json"))) == len(shadow_module.READY_CANDIDATE_IDS)
    assert len((tmp_path / "comparison.jsonl").read_text(encoding="utf-8").splitlines()) == len(
        shadow_module.READY_CANDIDATE_IDS
    )


def test_runtime_registry_preserves_active_blocked_and_equivalent_identity() -> None:
    authority = shadow_module.load_shadow_authority()
    registry = json.loads(authority.runtime_registry_bytes.decode("utf-8"))

    assert registry["schema_version"] == shadow_module.RUNTIME_REGISTRY_SCHEMA_VERSION
    assert registry["freeze_sha256"] == authority.freeze_sha256
    assert [item["candidate_id"] for item in registry["candidates"]] == list(
        shadow_module.FROZEN_CANDIDATE_IDS
    )
    assert registry["active_candidate_ids"] == list(shadow_module.READY_CANDIDATE_IDS)
    assert registry["migration_blocked_candidate_ids"] == list(
        shadow_module.MIGRATION_BLOCKED_CANDIDATE_IDS
    )
    statuses = {item["candidate_id"]: item["activation_status"] for item in registry["candidates"]}
    assert {
        candidate_id
        for candidate_id, status in statuses.items()
        if status == "ACTIVE_IMPLEMENTATION_READY"
    } == set(shadow_module.READY_CANDIDATE_IDS)
    assert {
        candidate_id for candidate_id, status in statuses.items() if status == "MIGRATION_REQUIRED"
    } == set(shadow_module.MIGRATION_BLOCKED_CANDIDATE_IDS)
    groups = registry["equivalent_portfolio_groups"]
    assert groups[shadow_module.EQUIVALENT_GROUP_R3_R6_B20] == [
        shadow_module.READY_CANDIDATE_IDS[0],
        shadow_module.READY_CANDIDATE_IDS[2],
    ]


def test_component_execution_is_once_per_strategy_and_equivalent_pair_is_identical(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []

    def builder(
        strategy_id: str,
        *,
        history: HistorySnapshot,
        target: PredictionTarget,
        allocation_count: int,
    ) -> tuple[dict[str, object], tuple[tuple[int, ...], ...]]:
        del history, target
        calls.append((strategy_id, allocation_count))
        return _fake_component(strategy_id, allocation_count=allocation_count)

    monkeypatch.setattr(shadow_module, "_build_component", builder)
    shadow = shadow_module.PairRuleForwardShadow(tmp_path)
    shadow.run_pre_draw(_target(), HISTORY, observed_at=NOW, canonical_source_head="a" * 40)

    assert calls == [
        (shadow_module.ORTHOGONAL_STRATEGY_ID, 20),
        (shadow_module.COLDPOOL_STRATEGY_ID, 20),
    ]
    prediction_root = tmp_path / "predictions" / "209900001"
    r3 = json.loads(
        (prediction_root / "CURRENT-R3_BIDIRECTIONAL_RESCUE_FIRST-B20.json").read_text()
    )
    r6 = json.loads(
        (prediction_root / "CURRENT-R6_BALANCED_ALLOCATION_PERFORMANCE-B20.json").read_text()
    )
    assert r3["equivalent_portfolio_group_id"] == r6["equivalent_portfolio_group_id"]
    assert r3["composed_ordered_tickets"] == r6["composed_ordered_tickets"]
    assert r3["combined_portfolio_sha256"] == r6["combined_portfolio_sha256"]
    assert (
        r3["a_only_same_budget_comparator_tickets"] == r6["a_only_same_budget_comparator_tickets"]
    )
    assert (
        r3["b_only_same_budget_comparator_tickets"] == r6["b_only_same_budget_comparator_tickets"]
    )
    for candidate_id in shadow_module.MIGRATION_BLOCKED_CANDIDATE_IDS:
        assert not (prediction_root / f"{candidate_id}.json").exists()


def test_primary_gate_and_shadow_lock_never_generate_shadow_predictions(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(shadow_module, "_build_component", _fake_builder)
    shadow = shadow_module.PairRuleForwardShadow(tmp_path)
    gated = shadow.run_pre_draw(
        _target(), HISTORY, observed_at=NOW, primary_status="WAITING_FOR_PREDRAW"
    )
    assert gated["status"] == "SKIPPED_PRIMARY_NOT_READY"
    assert not (tmp_path / "predictions").exists()

    with shadow_module.ShadowProcessLock(tmp_path / shadow_module.SHADOW_LOCK_FILE):
        contended = shadow.run_pre_draw(_target(), HISTORY, observed_at=NOW)
    assert contended["status"] == "ALREADY_RUNNING"
    assert not (tmp_path / "predictions").exists()


def test_postdraw_scores_pair_and_same_budget_comparators_without_backfill(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(shadow_module, "_build_component", _fake_builder)
    shadow = shadow_module.PairRuleForwardShadow(tmp_path)
    target = _target()
    shadow.run_pre_draw(target, HISTORY, observed_at=NOW)
    outcome = {
        "lottery_type": LOTTERY_TYPE,
        "draw_number": target.draw_number,
        "draw_date": target.draw_date,
        "main_numbers": [1, 2, 3, 4, 5, 6],
        "special_number": 7,
        "revision": "fixture-r1",
    }
    first = shadow.run_post_draw(target, outcome, observed_at=SCHEDULED)
    assert first["scored_candidate_count"] == 3
    score = json.loads(
        (
            tmp_path
            / "scores"
            / target.draw_number
            / "CURRENT-R3_BIDIRECTIONAL_RESCUE_FIRST-B20.json"
        ).read_text()
    )
    assert set(score["portfolio_scores"]) == {"pair", "a_only", "b_only"}
    assert score["portfolio_scores"]["pair"]["ticket_count"] == 20
    assert score["portfolio_scores"]["a_only"]["ticket_count"] == 20
    assert score["portfolio_scores"]["b_only"]["ticket_count"] == 20
    assert "pair_minus_a" in score and "pair_minus_b" in score
    before = {
        path: path.read_bytes()
        for path in (tmp_path / "scores" / target.draw_number).glob("*.json")
    }
    second = shadow.run_post_draw(target, outcome, observed_at=SCHEDULED)
    after = {
        path: path.read_bytes()
        for path in (tmp_path / "scores" / target.draw_number).glob("*.json")
    }
    assert second["scored_enabled_candidate_ids"] == first["scored_enabled_candidate_ids"]
    assert after == before


def test_postdraw_missing_predictions_are_waiting_not_backfilled(tmp_path: Path) -> None:
    shadow = shadow_module.PairRuleForwardShadow(tmp_path)
    target = _target()
    outcome = {
        "draw_number": target.draw_number,
        "main_numbers": [1, 2, 3, 4, 5, 6],
        "special_number": 7,
    }

    health = shadow.run_post_draw(target, outcome, observed_at=SCHEDULED)

    assert health["status"] == "POSTDRAW_COMPLETE"
    assert health["deadline_status"] == "WAITING_FOR_SHADOW_PREDICTIONS"
    assert health["scored_candidate_count"] == 0
    assert not (tmp_path / "predictions").exists()
    assert not (tmp_path / "scores").exists()
