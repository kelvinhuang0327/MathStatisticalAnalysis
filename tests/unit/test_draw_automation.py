"""Acceptance tests for bounded provider-triggered draw ingestion."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from lottolab.application.draw_automation import (
    AutomationNotConfiguredError,
    DrawProviderContractError,
    DrawSyncRequest,
    IngestionAuditContext,
    InvalidDrawSyncRequestError,
    ProviderDrawRecord,
    ProviderFetchResult,
)
from lottolab.application.draw_data import ImportCommitResult
from lottolab.application.use_cases.draw_automation import (
    BackfillDrawRange,
    FetchDrawData,
    ScanMissingDraws,
    ScheduledDrawSync,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import (
    DrawCsvParseResult,
    IngestionOperationType,
    IngestionRunStatus,
)
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv


class _Repository:
    def __init__(self) -> None:
        self.applied: list[tuple[DrawCsvParseResult, IngestionAuditContext]] = []
        self.failures: list[tuple[IngestionAuditContext, str]] = []

    def apply_automation_import(
        self,
        result: DrawCsvParseResult,
        context: IngestionAuditContext,
    ) -> ImportCommitResult:
        self.applied.append((result, context))
        return ImportCommitResult(
            run_id="run-1",
            status=IngestionRunStatus.SUCCESS,
            lottery_type=context.lottery_type,
            total_count=len(result.normalized_rows),
            inserted_count=len(result.normalized_rows),
            skipped_count=0,
            conflict_count=0,
            failed_count=0,
            first_draw_number=result.normalized_rows[0].draw_number,
            last_draw_number=result.normalized_rows[-1].draw_number,
            completed_at=datetime(2026, 7, 29, tzinfo=UTC),
        )

    def record_automation_failure(
        self,
        context: IngestionAuditContext,
        *,
        error_code: str,
    ) -> None:
        self.failures.append((context, error_code))


class _Provider:
    provider_id = "fixture-provider"
    provider_version = "fixture-v1"

    def __init__(self, records: tuple[ProviderDrawRecord, ...]) -> None:
        self._records = records
        self.requests: list[tuple[LotteryType, date, date]] = []

    def fetch_draws(
        self,
        *,
        lottery_type: LotteryType,
        date_from: date,
        date_to: date,
    ) -> ProviderFetchResult:
        self.requests.append((lottery_type, date_from, date_to))
        return ProviderFetchResult(
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            records=self._records,
        )


def _record(
    draw_number: str = "1001",
    *,
    draw_date: date = date(2026, 7, 29),
) -> ProviderDrawRecord:
    return ProviderDrawRecord(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=draw_number,
        draw_date=draw_date,
        main_numbers=(1, 3, 9, 17, 24, 49),
        special_numbers=(7,),
        source_reference="fixture",
    )


@pytest.mark.parametrize(
    ("use_case_type", "operation"),
    [
        (FetchDrawData, IngestionOperationType.MANUAL_SYNC),
        (ScanMissingDraws, IngestionOperationType.MISSING_DRAW_SCAN),
        (BackfillDrawRange, IngestionOperationType.BOUNDED_BACKFILL),
        (ScheduledDrawSync, IngestionOperationType.SCHEDULED_SYNC),
    ],
)
def test_each_trigger_uses_the_same_bounded_canonical_pipeline(
    use_case_type: type[
        FetchDrawData | ScanMissingDraws | BackfillDrawRange | ScheduledDrawSync
    ],
    operation: IngestionOperationType,
) -> None:
    repository = _Repository()
    provider = _Provider((_record(),))
    request = DrawSyncRequest(
        LotteryType.BIG_LOTTO,
        date(2026, 7, 28),
        date(2026, 7, 29),
    )

    result = use_case_type(lambda: provider, lambda: repository, parse_draw_csv).execute(
        request
    )

    assert provider.requests == [
        (LotteryType.BIG_LOTTO, date(2026, 7, 28), date(2026, 7, 29))
    ]
    parsed, context = repository.applied[0]
    assert parsed.is_valid
    assert parsed.normalized_rows[0].main_numbers == (1, 3, 9, 17, 24, 49)
    assert context.operation_type is operation
    assert context.resolved_start == context.resolved_end == date(2026, 7, 29)
    assert result.operation_type is operation
    assert repository.failures == []


def test_not_configured_is_explicit_and_append_only_audited() -> None:
    repository = _Repository()
    request = DrawSyncRequest(
        LotteryType.BIG_LOTTO,
        date(2026, 7, 29),
        date(2026, 7, 29),
    )

    with pytest.raises(AutomationNotConfiguredError, match="not configured"):
        FetchDrawData(lambda: None, lambda: repository, parse_draw_csv).execute(request)

    context, error_code = repository.failures[0]
    assert error_code == "AUTOMATION_NOT_CONFIGURED"
    assert context.provider_id == "NOT_CONFIGURED"
    assert context.fetched_count == 0
    assert repository.applied == []


def test_invalid_provider_identity_is_rejected_before_draw_writes_and_audited() -> None:
    repository = _Repository()
    provider = _Provider((_record("1001"), _record("1001")))
    request = DrawSyncRequest(
        LotteryType.BIG_LOTTO,
        date(2026, 7, 29),
        date(2026, 7, 29),
    )

    with pytest.raises(DrawProviderContractError, match="duplicate"):
        FetchDrawData(lambda: provider, lambda: repository, parse_draw_csv).execute(
            request
        )

    assert repository.applied == []
    context, error_code = repository.failures[0]
    assert error_code == "PROVIDER_CONTRACT_INVALID"
    assert context.fetched_count == 2


def test_range_is_capped_before_provider_or_repository_access() -> None:
    with pytest.raises(InvalidDrawSyncRequestError, match="366"):
        DrawSyncRequest(
            LotteryType.BIG_LOTTO,
            date(2025, 1, 1),
            date(2026, 7, 29),
        )
