from __future__ import annotations

from pathlib import Path

import pytest

from lottolab.infrastructure.biglotto_multi_ticket_projection_builder import (
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
        match=r"missing=135 unexpected=0",
    ):
        build_b649_projection_bytes(())


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
