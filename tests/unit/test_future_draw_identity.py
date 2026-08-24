"""Focused contracts for strict manual future-identity input and architecture."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from lottolab.application.future_draw_identity import (
    ScheduledDrawIdentityRecord,
    ScheduledDrawOutcomeState,
    normalized_announcement_sha256,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.pre_outcome_target_operational import (
    OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
    TargetAnnouncementAuthorityError,
    parse_owner_certified_future_draw_identity_input,
    select_owner_certified_future_draw_identity,
)


def _document(
    *,
    lottery_type: str = "BIG_LOTTO",
    draw_number: str = "209900001",
    draw_date: str = "2099-01-02",
    scheduled_at: str = "2099-01-02T12:30:00Z",
    source_locator: str = "https://www.taiwanlottery.com/schedule/209900001",
) -> dict[str, object]:
    return {
        "announcements": [
            {
                "schedule_timezone": "Asia/Taipei",
                "scheduled_at": scheduled_at,
                "source": {
                    "observed_at": "2099-01-01T01:00:00Z",
                    "source_id": "TAIWAN_LOTTERY_OFFICIAL_SCHEDULE",
                    "source_locator": source_locator,
                    "source_payload_sha256": "a" * 64,
                    "source_version": "taiwan-lottery-official-schedule-v1",
                },
                "target": {
                    "draw_date": draw_date,
                    "draw_number": draw_number,
                    "lottery_type": lottery_type,
                },
            }
        ],
        "schema_version": OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
    }


def _encoded(document: dict[str, object]) -> bytes:
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode()


def test_strict_parser_and_explicit_selector_preserve_official_identity() -> None:
    parsed = parse_owner_certified_future_draw_identity_input(
        _encoded(_document()),
        source_filename="owner-certified.json",
    )
    selected = select_owner_certified_future_draw_identity(
        parsed,
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number="209900001",
    )

    assert parsed.source_filename == "owner-certified.json"
    assert len(parsed.input_sha256) == 64
    assert parsed.announcements == (selected,)
    assert selected.target.lottery_type is LotteryType.BIG_LOTTO
    assert selected.target.draw_number == "209900001"
    assert selected.target.draw_date.isoformat() == "2099-01-02"
    assert selected.scheduled_at.isoformat() == "2099-01-02T12:30:00+00:00"
    assert selected.source.source_payload_sha256 == "a" * 64


def test_missing_draw_number_and_outcome_members_are_rejected() -> None:
    missing = _document()
    missing_target = cast(
        dict[str, object],
        cast(list[object], missing["announcements"])[0],
    )["target"]
    cast(dict[str, object], missing_target).pop("draw_number")

    with pytest.raises(TargetAnnouncementAuthorityError, match="fields"):
        parse_owner_certified_future_draw_identity_input(
            _encoded(missing),
            source_filename="missing.json",
        )

    outcome = _document()
    announcement = cast(
        dict[str, object],
        cast(list[object], outcome["announcements"])[0],
    )
    announcement["winning_numbers"] = [1, 2, 3, 4, 5, 6]
    with pytest.raises(TargetAnnouncementAuthorityError, match="fields"):
        parse_owner_certified_future_draw_identity_input(
            _encoded(outcome),
            source_filename="outcome.json",
        )


def test_invalid_lottery_timestamp_source_and_ambiguous_selector_are_rejected() -> None:
    invalid_timestamp = _document(scheduled_at="2099-01-02 12:30:00")
    with pytest.raises(TargetAnnouncementAuthorityError, match="UTC"):
        parse_owner_certified_future_draw_identity_input(
            _encoded(invalid_timestamp),
            source_filename="timestamp.json",
        )

    invalid_source = _document(source_locator="https://example.test/schedule")
    with pytest.raises(TargetAnnouncementAuthorityError, match="official"):
        parse_owner_certified_future_draw_identity_input(
            _encoded(invalid_source),
            source_filename="source.json",
        )

    parsed = parse_owner_certified_future_draw_identity_input(
        _encoded(_document(lottery_type="DAILY_539")),
        source_filename="daily539.json",
    )
    with pytest.raises(TargetAnnouncementAuthorityError, match="BIG_LOTTO"):
        select_owner_certified_future_draw_identity(
            parsed,
            lottery_type=LotteryType.DAILY_539,
            draw_number="209900001",
        )
    with pytest.raises(TargetAnnouncementAuthorityError, match="exactly one"):
        select_owner_certified_future_draw_identity(
            parsed,
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number="209900002",
        )


def test_derived_outcome_state_requires_an_exact_optional_completed_draw_identity() -> None:
    parsed = parse_owner_certified_future_draw_identity_input(
        _encoded(_document()),
        source_filename="owner-certified.json",
    )
    announcement = parsed.announcements[0]

    def build_record(
        outcome_state: ScheduledDrawOutcomeState,
        outcome_draw_internal_id: int | None,
    ) -> ScheduledDrawIdentityRecord:
        return ScheduledDrawIdentityRecord(
            internal_id=1,
            announcement=announcement,
            normalized_announcement_hash=normalized_announcement_sha256(announcement),
            ingestion_run_id="synthetic-run",
            created_at=datetime(2099, 1, 1, tzinfo=UTC),
            outcome_state=outcome_state,
            outcome_draw_internal_id=outcome_draw_internal_id,
        )

    with pytest.raises(ValueError, match="positive integer or None"):
        build_record(
            ScheduledDrawOutcomeState.NOT_POPULATED,
            0,
        )
    with pytest.raises(ValueError, match="disagree"):
        build_record(
            ScheduledDrawOutcomeState.POPULATED,
            None,
        )


def test_manual_sqlite_writer_is_reachable_only_from_root_cli_source() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    symbol = "SQLiteManualFutureDrawIdentitySupplementRepository"
    references = {
        path.relative_to(repository_root).as_posix()
        for root in (repository_root / "src" / "lottolab", repository_root / "tools")
        for path in root.rglob("*.py")
        if symbol in path.read_text(encoding="utf-8")
    }

    assert references == {
        "src/lottolab/infrastructure/persistence/future_draw_identity_repository.py",
        "src/lottolab/interfaces/cli/future_draw_identity.py",
    }
