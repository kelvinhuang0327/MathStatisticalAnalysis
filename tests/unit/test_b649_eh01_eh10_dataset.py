from __future__ import annotations

from pathlib import Path

import pytest

from lottolab.research.b649_eh01_eh10_dataset import (
    DEFAULT_SQLITE_PATH,
    DatasetAuthorityError,
    load_clean_b649_history,
)

pytestmark = pytest.mark.skipif(
    not DEFAULT_SQLITE_PATH.is_file(),
    reason=(
        "sealed BIGLOTTO_CANONICAL_FULL_HISTORY_BASELINE_R4 authority is not present "
        "on this machine"
    ),
)


def test_clean_history_matches_the_independently_audited_and_precedent_counts() -> None:
    # This exact (row_count, excluded_count, date_range) triple was
    # independently reached twice before this task: the 2026-08-12
    # contamination audit (memory: biglotto-uniformity-audit-and-baseline-
    # contamination) and the sealed REGIME_CHANGE_POINT_CUSUM_B649_V1 cell's
    # own `provenance` block
    # (docs/research/matrix-native-results/regime-changepoint-cusum-b649-v1-result.json).
    # A third independent hit here is strong evidence this loader has the
    # dataset-authority rule right, not a coincidence.
    history = load_clean_b649_history()
    assert history.row_count == 2138
    assert history.excluded_date_like_contaminants == 150
    assert history.draw_dates[0] == "2007-03-09"
    assert history.draw_dates[-1] == "2026-07-31"


def test_clean_history_is_strictly_ascending_by_date_with_no_duplicates() -> None:
    history = load_clean_b649_history()
    assert list(history.draw_dates) == sorted(history.draw_dates)
    assert len(set(history.draw_dates)) == len(history.draw_dates)
    assert len(set(history.draw_ids)) == len(history.draw_ids)


def test_every_main_number_sum_is_in_the_valid_big_lotto_range() -> None:
    # 6 distinct numbers from 1..49: minimum possible sum is 1+2+..+6=21,
    # maximum is 44+45+..+49=279.
    history = load_clean_b649_history()
    assert min(history.main_number_sums) >= 21
    assert max(history.main_number_sums) <= 279
    assert len(history.main_number_sums) == history.row_count


def test_logical_sha256_is_deterministic_across_repeated_loads() -> None:
    first = load_clean_b649_history()
    second = load_clean_b649_history()
    assert first.logical_sha256 == second.logical_sha256
    assert len(first.logical_sha256) == 64


def test_missing_file_raises_dataset_authority_error(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.sqlite"
    with pytest.raises(DatasetAuthorityError, match="STOP_DATASET_AUTHORITY_UNPINNED"):
        load_clean_b649_history(missing)
