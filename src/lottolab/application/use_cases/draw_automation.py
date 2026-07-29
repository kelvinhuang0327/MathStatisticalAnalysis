"""Bounded provider synchronization use cases with canonical backend validation."""

from __future__ import annotations

import csv
import io

from lottolab.application.draw_automation import (
    AutomationNotConfiguredError,
    DrawProviderContractError,
    DrawProviderUnavailableError,
    DrawSyncRequest,
    DrawSyncResult,
    IngestionAuditContext,
    ProviderFetchResult,
)
from lottolab.application.ports import (
    DrawAutomationRepositoryFactory,
    DrawCsvParser,
    DrawDataProviderFactory,
)
from lottolab.domain.ingestion import IngestionOperationType


class _RunDrawSync:
    def __init__(
        self,
        provider_factory: DrawDataProviderFactory,
        repository_factory: DrawAutomationRepositoryFactory,
        parser: DrawCsvParser,
        operation_type: IngestionOperationType,
    ) -> None:
        self._provider_factory = provider_factory
        self._repository_factory = repository_factory
        self._parser = parser
        self._operation_type = operation_type

    def execute(self, request: DrawSyncRequest) -> DrawSyncResult:
        provider = self._provider_factory()
        if provider is None:
            self._record_failure(
                request,
                provider_id="NOT_CONFIGURED",
                provider_version="NOT_AVAILABLE",
                error_code="AUTOMATION_NOT_CONFIGURED",
            )
            raise AutomationNotConfiguredError("draw automation is not configured")
        try:
            fetched = provider.fetch_draws(
                lottery_type=request.lottery_type,
                date_from=request.date_from,
                date_to=request.date_to,
            )
        except DrawProviderContractError:
            self._record_failure(
                request,
                provider_id=provider.provider_id,
                provider_version=provider.provider_version,
                error_code="PROVIDER_CONTRACT_INVALID",
            )
            raise
        except DrawProviderUnavailableError:
            self._record_failure(
                request,
                provider_id=provider.provider_id,
                provider_version=provider.provider_version,
                error_code="PROVIDER_UNAVAILABLE",
            )
            raise
        except Exception as exc:
            self._record_failure(
                request,
                provider_id=provider.provider_id,
                provider_version=provider.provider_version,
                error_code="PROVIDER_UNAVAILABLE",
            )
            raise DrawProviderUnavailableError(
                "configured draw provider is unavailable"
            ) from exc
        try:
            self._validate_fetch(request, fetched)
            csv_text = _canonical_provider_csv(fetched)
            parsed = self._parser(csv_text, filename=fetched.provider_id)
            if not parsed.is_valid:
                raise DrawProviderContractError(
                    "provider rows failed canonical draw validation"
                )
        except DrawProviderContractError:
            self._record_failure(
                request,
                provider_id=fetched.provider_id,
                provider_version=fetched.provider_version,
                error_code="PROVIDER_CONTRACT_INVALID",
                fetched_count=len(fetched.records),
            )
            raise

        dates = tuple(record.draw_date for record in fetched.records)
        context = IngestionAuditContext(
            operation_type=self._operation_type,
            lottery_type=request.lottery_type,
            provider_id=fetched.provider_id,
            provider_version=fetched.provider_version,
            requested_start=request.date_from,
            requested_end=request.date_to,
            resolved_start=min(dates) if dates else None,
            resolved_end=max(dates) if dates else None,
            fetched_count=len(fetched.records),
        )
        committed = self._repository_factory().apply_automation_import(parsed, context)
        return DrawSyncResult(
            operation_type=self._operation_type,
            provider_id=fetched.provider_id,
            requested_start=request.date_from,
            requested_end=request.date_to,
            resolved_start=context.resolved_start,
            resolved_end=context.resolved_end,
            fetched_count=context.fetched_count,
            ingestion=committed,
        )

    def _record_failure(
        self,
        request: DrawSyncRequest,
        *,
        provider_id: str,
        provider_version: str,
        error_code: str,
        fetched_count: int = 0,
    ) -> None:
        self._repository_factory().record_automation_failure(
            IngestionAuditContext(
                operation_type=self._operation_type,
                lottery_type=request.lottery_type,
                provider_id=provider_id,
                provider_version=provider_version,
                requested_start=request.date_from,
                requested_end=request.date_to,
                resolved_start=None,
                resolved_end=None,
                fetched_count=fetched_count,
            ),
            error_code=error_code,
        )

    @staticmethod
    def _validate_fetch(request: DrawSyncRequest, fetched: ProviderFetchResult) -> None:
        if not fetched.provider_id.strip() or not fetched.provider_version.strip():
            raise DrawProviderContractError("provider identity is incomplete")
        identities: set[tuple[str, str]] = set()
        for record in fetched.records:
            if record.lottery_type is not request.lottery_type:
                raise DrawProviderContractError("provider returned a different lottery type")
            if not request.date_from <= record.draw_date <= request.date_to:
                raise DrawProviderContractError(
                    "provider returned a draw outside the requested range"
                )
            identity = (record.lottery_type.value, record.draw_number)
            if identity in identities:
                raise DrawProviderContractError("provider returned a duplicate draw identity")
            identities.add(identity)


class FetchDrawData(_RunDrawSync):
    def __init__(
        self,
        provider_factory: DrawDataProviderFactory,
        repository_factory: DrawAutomationRepositoryFactory,
        parser: DrawCsvParser,
    ) -> None:
        super().__init__(
            provider_factory,
            repository_factory,
            parser,
            IngestionOperationType.MANUAL_SYNC,
        )


class ScanMissingDraws(_RunDrawSync):
    def __init__(
        self,
        provider_factory: DrawDataProviderFactory,
        repository_factory: DrawAutomationRepositoryFactory,
        parser: DrawCsvParser,
    ) -> None:
        super().__init__(
            provider_factory,
            repository_factory,
            parser,
            IngestionOperationType.MISSING_DRAW_SCAN,
        )


class BackfillDrawRange(_RunDrawSync):
    def __init__(
        self,
        provider_factory: DrawDataProviderFactory,
        repository_factory: DrawAutomationRepositoryFactory,
        parser: DrawCsvParser,
    ) -> None:
        super().__init__(
            provider_factory,
            repository_factory,
            parser,
            IngestionOperationType.BOUNDED_BACKFILL,
        )


class ScheduledDrawSync(_RunDrawSync):
    def __init__(
        self,
        provider_factory: DrawDataProviderFactory,
        repository_factory: DrawAutomationRepositoryFactory,
        parser: DrawCsvParser,
    ) -> None:
        super().__init__(
            provider_factory,
            repository_factory,
            parser,
            IngestionOperationType.SCHEDULED_SYNC,
        )


def _canonical_provider_csv(fetched: ProviderFetchResult) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "lottery_type",
            "draw_number",
            "draw_date",
            "main_numbers",
            "special_numbers",
            "source",
        )
    )
    for record in sorted(
        fetched.records,
        key=lambda item: (item.draw_date, item.draw_number),
    ):
        writer.writerow(
            (
                record.lottery_type.value,
                record.draw_number,
                record.draw_date.isoformat(),
                "|".join(str(number) for number in record.main_numbers),
                "|".join(str(number) for number in record.special_numbers),
                record.source_reference or fetched.provider_id,
            )
        )
    return output.getvalue()
