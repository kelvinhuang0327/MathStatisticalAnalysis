from __future__ import annotations

from pathlib import Path

import pytest

from lottolab.application.biglotto_multi_ticket_records import (
    B649_AUTHORITY_MODE_FRESH_REPRODUCTION,
    B649_AUTHORITY_MODE_HISTORICAL_SEALED,
)
from lottolab.infrastructure.b649_dataset_authority import (
    APPROVED_FRESH_LOGICAL_DATASET_SHA256,
    LEGACY_PINNED_DATASET_SHA256,
    B649DatasetAuthorityError,
    validate_b649_dataset_sha256,
)
from lottolab.infrastructure.biglotto_multi_ticket_projection_builder import (
    B649ProjectionBuildError,
    build_b649_projection_bytes,
)


def test_legacy_pin_is_accepted_without_fresh_authority() -> None:
    assert (
        validate_b649_dataset_sha256(LEGACY_PINNED_DATASET_SHA256)
        == LEGACY_PINNED_DATASET_SHA256
    )
    assert (
        validate_b649_dataset_sha256(
            LEGACY_PINNED_DATASET_SHA256,
            authority_mode=B649_AUTHORITY_MODE_HISTORICAL_SEALED,
        )
        == LEGACY_PINNED_DATASET_SHA256
    )


def test_wrong_dataset_sha256_is_rejected() -> None:
    with pytest.raises(B649DatasetAuthorityError):
        validate_b649_dataset_sha256("0" * 64)


def test_fresh_identity_requires_explicit_fresh_authority() -> None:
    with pytest.raises(B649DatasetAuthorityError):
        validate_b649_dataset_sha256(APPROVED_FRESH_LOGICAL_DATASET_SHA256)
    with pytest.raises(B649DatasetAuthorityError):
        validate_b649_dataset_sha256(
            APPROVED_FRESH_LOGICAL_DATASET_SHA256,
            authority_mode=B649_AUTHORITY_MODE_HISTORICAL_SEALED,
        )


def test_fresh_identity_is_accepted_only_with_explicit_fresh_authority() -> None:
    assert (
        validate_b649_dataset_sha256(
            APPROVED_FRESH_LOGICAL_DATASET_SHA256,
            authority_mode=B649_AUTHORITY_MODE_FRESH_REPRODUCTION,
        )
        == APPROVED_FRESH_LOGICAL_DATASET_SHA256
    )
    with pytest.raises(B649DatasetAuthorityError):
        validate_b649_dataset_sha256(
            LEGACY_PINNED_DATASET_SHA256,
            authority_mode=B649_AUTHORITY_MODE_FRESH_REPRODUCTION,
        )


def test_builder_requires_explicit_fresh_authority_before_reading_report(
    tmp_path: Path,
) -> None:
    report = tmp_path / "fresh-report.json"
    report.write_text("{}", encoding="utf-8")

    with pytest.raises(
        B649ProjectionBuildError,
        match="explicit FRESH_CURRENT_CATALOG_REPRODUCTION_V1 authority",
    ):
        build_b649_projection_bytes(fresh_report_paths=(report,))
