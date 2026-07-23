"""Task-owned Historical Results database fixture for local workspace tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.fixtures.historical.builder import (
    CUTOFF_DRAW_NUMBER,
    CUTOFF_MAIN_NUMBERS,
    CUTOFF_SPECIAL_NUMBERS,
    TARGET_DRAW_NUMBER,
    TARGET_MAIN_NUMBERS,
    build_baseline_envelope,
    build_draw_snapshot,
    build_envelope,
    build_portfolio,
    build_tickets,
    envelope_bytes,
)

from lottolab.domain.historical_results import HistoricalImportCommitResult, HistoricalRunImport
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultRepository,
)
from lottolab.normalization.historical_import import verify_and_normalize_historical_import


def persist_local_workspace_source(
    database: Path,
) -> tuple[HistoricalRunImport, HistoricalImportCommitResult]:
    """Create one synthetic source; callers authorize and own its exact path."""

    baseline = build_baseline_envelope()
    target_special = (49,)
    envelope: dict[str, Any] = build_envelope(
        strategy_descriptors=baseline["strategy_descriptors"],
        draw_snapshots=[
            build_draw_snapshot(
                draw_number=CUTOFF_DRAW_NUMBER,
                draw_date="2026-01-01",
                main_numbers=CUTOFF_MAIN_NUMBERS,
                special_numbers=CUTOFF_SPECIAL_NUMBERS,
            ),
            build_draw_snapshot(
                draw_number=TARGET_DRAW_NUMBER,
                draw_date="2026-01-10",
                main_numbers=TARGET_MAIN_NUMBERS,
                special_numbers=target_special,
            ),
        ],
        portfolios=[
            build_portfolio(
                strategy_id=str(descriptor["strategy_id"]),
                strategy_version=str(descriptor["strategy_version"]),
                replicate=int(descriptor["replicate"]),
                tickets=build_tickets(
                    target_main=TARGET_MAIN_NUMBERS,
                    target_special=target_special,
                ),
            )
            for descriptor in baseline["strategy_descriptors"][:3]
        ],
    )
    verified = verify_and_normalize_historical_import(envelope_bytes(envelope))
    assert verified.normalized_import is not None
    commit = SQLiteHistoricalResultRepository(database).commit_import(verified.normalized_import)
    return verified.normalized_import, commit


__all__ = ["persist_local_workspace_source"]
