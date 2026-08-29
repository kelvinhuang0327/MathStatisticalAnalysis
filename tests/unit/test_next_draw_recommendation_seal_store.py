"""Unit contracts for the durable create-once Next-Draw Recommendation seal store."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_recommendation import NATIVE_TICKET_COUNT_BUCKETS
from lottolab.domain.next_draw_recommendation_seal import (
    NextDrawRecommendationSeal,
    NextDrawRecommendationSealTamperError,
    SealedRecommendationBucket,
)
from lottolab.domain.prospective_observer import CreateOnceOutcome, ObservationTarget
from lottolab.infrastructure.next_draw_recommendation_seal_store import (
    FileSystemNextDrawRecommendationSealStore,
    NextDrawRecommendationSealStoreCorruptionError,
)

TARGET = ObservationTarget(
    lottery_type=LotteryType.BIG_LOTTO, draw_number="115000090", draw_date=date(2099, 9, 1)
)
OTHER_TARGET = ObservationTarget(
    lottery_type=LotteryType.BIG_LOTTO, draw_number="115000091", draw_date=date(2099, 9, 8)
)
SCHEDULED_AT = datetime(2099, 9, 1, 8, 30, tzinfo=UTC)
OTHER_SCHEDULED_AT = datetime(2099, 9, 8, 8, 30, tzinfo=UTC)
SEALED_AT = datetime(2099, 8, 30, 10, 0, tzinfo=UTC)


def _seal(
    target: ObservationTarget = TARGET,
    scheduled_at: datetime = SCHEDULED_AT,
    *,
    causal_history_draw_count: int = 2,
) -> NextDrawRecommendationSeal:
    buckets = tuple(
        SealedRecommendationBucket(
            native_ticket_count=count,
            availability="UNAVAILABLE",
            total_candidate_count=0,
            ranked_strategy_ids=(),
            ranking_projection_sha256="c" * 64,
            sealed_tickets=(),
        )
        for count in NATIVE_TICKET_COUNT_BUCKETS
    )
    return NextDrawRecommendationSeal.create(
        target=target,
        target_scheduled_at=scheduled_at,
        sealed_at=SEALED_AT,
        target_registration_digest="d" * 64,
        evidence_artifact_sha256="e" * 64,
        causal_history_sha256="f" * 64,
        causal_history_draw_count=causal_history_draw_count,
        buckets=buckets,
    )


def test_construction_performs_no_filesystem_io(tmp_path: Path) -> None:
    root = tmp_path / "seals"
    FileSystemNextDrawRecommendationSealStore(root)
    assert not root.exists()


def test_get_seal_on_an_empty_store_returns_none_without_creating_anything(
    tmp_path: Path,
) -> None:
    root = tmp_path / "seals"
    store = FileSystemNextDrawRecommendationSealStore(root)

    result = store.get_seal(TARGET)

    assert result is None
    assert not root.exists()


def test_create_then_get_round_trips_exactly(tmp_path: Path) -> None:
    store = FileSystemNextDrawRecommendationSealStore(tmp_path / "seals")
    seal = _seal()

    outcome = store.create_seal(seal)

    assert outcome is CreateOnceOutcome.INSERTED
    assert store.get_seal(TARGET) == seal


def test_second_create_for_the_same_target_reports_conflict_and_never_overwrites(
    tmp_path: Path,
) -> None:
    store = FileSystemNextDrawRecommendationSealStore(tmp_path / "seals")
    first = _seal()
    store.create_seal(first)
    record_path = FileSystemNextDrawRecommendationSealStore.record_path_for(store.root, TARGET)
    original_bytes = record_path.read_bytes()

    # A materially different seal for the exact same target.
    second = _seal(causal_history_draw_count=999)
    outcome = store.create_seal(second)

    assert outcome is CreateOnceOutcome.CONFLICT
    assert record_path.read_bytes() == original_bytes
    assert store.get_seal(TARGET) == first


def test_different_targets_are_stored_in_isolated_locations(tmp_path: Path) -> None:
    store = FileSystemNextDrawRecommendationSealStore(tmp_path / "seals")
    seal_a = _seal(TARGET, SCHEDULED_AT)
    seal_b = _seal(OTHER_TARGET, OTHER_SCHEDULED_AT)

    assert store.create_seal(seal_a) is CreateOnceOutcome.INSERTED
    assert store.create_seal(seal_b) is CreateOnceOutcome.INSERTED
    assert store.get_seal(TARGET) == seal_a
    assert store.get_seal(OTHER_TARGET) == seal_b


def test_record_is_durably_written_and_readable_by_a_fresh_store_instance(
    tmp_path: Path,
) -> None:
    root = tmp_path / "seals"
    seal = _seal()
    FileSystemNextDrawRecommendationSealStore(root).create_seal(seal)

    reopened = FileSystemNextDrawRecommendationSealStore(root)
    assert reopened.get_seal(TARGET) == seal


def test_tampered_record_bytes_fail_closed_on_read(tmp_path: Path) -> None:
    store = FileSystemNextDrawRecommendationSealStore(tmp_path / "seals")
    store.create_seal(_seal())
    record_path = FileSystemNextDrawRecommendationSealStore.record_path_for(store.root, TARGET)

    payload = json.loads(record_path.read_text(encoding="utf-8"))
    payload["causal_history_draw_count"] = 999999
    # The record was created read-only (0o444); restore write access to
    # simulate an out-of-band hand edit, exactly as an attacker or a bug
    # elsewhere in the system would have to.
    record_path.chmod(0o644)
    record_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(NextDrawRecommendationSealTamperError):
        store.get_seal(TARGET)


def test_record_path_that_is_a_directory_fails_closed_as_corruption(tmp_path: Path) -> None:
    root = tmp_path / "seals"
    record_path = FileSystemNextDrawRecommendationSealStore.record_path_for(root, TARGET)
    record_path.mkdir(parents=True)

    store = FileSystemNextDrawRecommendationSealStore(root)
    with pytest.raises(NextDrawRecommendationSealStoreCorruptionError):
        store.get_seal(TARGET)


def test_record_path_helper_is_stable_and_derived_only_from_target_identity(
    tmp_path: Path,
) -> None:
    root = tmp_path / "seals"
    path_a = FileSystemNextDrawRecommendationSealStore.record_path_for(root, TARGET)
    path_b = FileSystemNextDrawRecommendationSealStore.record_path_for(root, TARGET)
    path_other = FileSystemNextDrawRecommendationSealStore.record_path_for(root, OTHER_TARGET)

    assert path_a == path_b
    assert path_a != path_other
    assert root in path_a.parents
