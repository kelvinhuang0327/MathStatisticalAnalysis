from __future__ import annotations

from pathlib import Path

import pytest

from lottolab.domain.biglotto_full_strategy_catalog import (
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.infrastructure.biglotto_multi_ticket_projection_builder import (
    METRICS_UNAVAILABLE_STRATEGY_IDS,
    B649ProjectionBuildError,
    build_b649_projection_bytes,
    expected_report_manifest,
)


def test_committed_evidence_pins_all_135_backtested_strategies() -> None:
    manifest = expected_report_manifest()

    assert len(manifest) == 53
    assert sum(len(report.strategy_ids) for report in manifest) == 135
    assert len({report.report_file_sha256 for report in manifest}) == 53
    assert len(
        {
            strategy_id
            for report in manifest
            for strategy_id in report.strategy_ids
        }
    ) == 135


def test_builder_refuses_incomplete_explicit_report_set() -> None:
    with pytest.raises(
        B649ProjectionBuildError,
        match=r"missing=133 unexpected=0",
    ):
        build_b649_projection_bytes(())


def test_metrics_unavailable_strategy_ids_are_pinned_backtested_replay_exact2() -> None:
    catalog = load_full_strategy_catalog()
    by_id = {record.strategy_id: record for record in catalog.records}

    assert len(METRICS_UNAVAILABLE_STRATEGY_IDS) == 2
    for strategy_id in METRICS_UNAVAILABLE_STRATEGY_IDS:
        record = by_id[strategy_id]
        assert record.reproduction_status is ReproductionStatus.BACKTESTED
        assert record.legacy_method_id in (
            "tools/backtest_biglotto_5bet_ts3markov.py",
            "tools/predict_biglotto_triple_strike.py",
        )


def test_manifest_still_pins_metrics_unavailable_strategy_provenance() -> None:
    manifest = expected_report_manifest()
    covered = {
        strategy_id for report in manifest for strategy_id in report.strategy_ids
    }
    # The manifest legitimately still carries exact2's pinned provenance
    # (used for the metrics-unavailable records' report_file_sha256); the
    # builder simply never requires it to be supplied through report_paths.
    assert covered >= METRICS_UNAVAILABLE_STRATEGY_IDS


def test_builder_rejects_symlinked_report_before_reading_it(
    tmp_path: Path,
) -> None:
    target = tmp_path / "report.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "report-link.json"
    link.symlink_to(target)

    with pytest.raises(
        B649ProjectionBuildError,
        match="regular non-symlink file",
    ):
        build_b649_projection_bytes((link,))
