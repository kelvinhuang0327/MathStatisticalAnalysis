from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from lottolab.infrastructure.b649_research_board_v2_reader import (
    B649_RESEARCH_BOARD_V2_ROOT_ENV,
    B649ResearchBoardV2DataError,
    B649ResearchBoardV2Reader,
)

V2_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/20261102/"
    "NUMBER2_D_LMS_HUMAN_BOARD_V2_INTEGRATION_20261102_R1"
)


def test_reader_verifies_source_and_preserves_all_v2_rows() -> None:
    dataset = B649ResearchBoardV2Reader(V2_ROOT).read()

    assert dataset.source_authority_commit == "fe3aa81d3844ac11d4360447c243e90fe4a6613a"
    assert dataset.observed_checkout_head == "b4e11ebd0981d549ce70055e70f8fbd0065cd2dd"
    assert dataset.method_version_count == 305
    assert dataset.inventory_count == 2968
    assert dataset.ranking_count == 2818
    assert dataset.metrics_availability_counts["UNAVAILABLE"] == 60
    assert dataset.metrics_availability_counts["NOT_APPLICABLE"] == 90
    assert dataset.comparable_group_count == 224
    assert dataset.duplicate_output_groups == 48
    assert dataset.windows == ("FULL", "RECENT_750", "RECENT_300", "RECENT_50")
    assert dataset.k_values == (2, 3, 5, 10, 15, 20)
    assert dataset.prize_metrics == ("OFFICIAL_ANY_PRIZE",)
    assert dataset.comparison_group_count == 504

    unavailable = next(
        row for row in dataset.method_records if row["metrics_availability"] == "UNAVAILABLE"
    )
    assert unavailable["metrics_unavailable_reason"]
    assert unavailable["successful_draws"] == ""
    assert unavailable["eligible_draws"] == ""
    assert unavailable["success_rate"] == ""
    not_applicable = next(
        row for row in dataset.method_records if row["metrics_availability"] == "NOT_APPLICABLE"
    )
    assert not_applicable["K"] == ""
    assert not_applicable["success_rate"] == ""

    assert all(
        not row[field]
        for row in dataset.method_records
        for field in (
            "owner_long_rank",
            "owner_middle_rank",
            "owner_short_rank",
            "owner_selected",
            "owner_reason",
        )
    )


def test_reader_rejects_an_output_that_fails_its_manifest_checksum(tmp_path: Path) -> None:
    for filename in ("source_manifest.json", "result.json", "integration_summary.json"):
        shutil.copyfile(V2_ROOT / filename, tmp_path / filename)
    with (tmp_path / "integration_summary.json").open("ab") as stream:
        stream.write(b" ")

    with pytest.raises(B649ResearchBoardV2DataError, match="checksum"):
        B649ResearchBoardV2Reader(tmp_path).read()


def test_reader_requires_an_absolute_configured_root(tmp_path: Path) -> None:
    with pytest.raises(B649ResearchBoardV2DataError, match="absolute"):
        B649ResearchBoardV2Reader(Path("relative-v2-root")).read()


def test_environment_factory_returns_none_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(B649_RESEARCH_BOARD_V2_ROOT_ENV, raising=False)

    assert B649ResearchBoardV2Reader.from_environment() is None
