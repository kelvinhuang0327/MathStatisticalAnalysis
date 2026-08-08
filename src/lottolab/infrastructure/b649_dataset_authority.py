"""Closed dataset-authority contract for B649 materialization and projection."""

from __future__ import annotations

from typing import Final

from lottolab.application.biglotto_multi_ticket_records import (
    B649_AUTHORITY_MODE_FRESH_REPRODUCTION,
    B649_AUTHORITY_MODE_HISTORICAL_SEALED,
)

LEGACY_PINNED_DATASET_SHA256: Final = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
APPROVED_FRESH_LOGICAL_DATASET_SHA256: Final = (
    "b62a7b71a0c445a1c3532a72aade92b63824bd483aa5d97e4bf6dd32f7f6752e"
)


class B649DatasetAuthorityError(ValueError):
    """A B649 dataset identity is not authorized for the selected mode."""


def validate_b649_dataset_sha256(
    value: object,
    *,
    authority_mode: str | None = None,
) -> str:
    """Accept only the exact identity authorized by the explicit mode.

    Omitting the mode preserves the legacy contract and therefore accepts only
    the original pinned identity.  Fresh reproduction never occurs implicitly.
    """

    if authority_mode is None or authority_mode == B649_AUTHORITY_MODE_HISTORICAL_SEALED:
        expected = LEGACY_PINNED_DATASET_SHA256
    elif authority_mode == B649_AUTHORITY_MODE_FRESH_REPRODUCTION:
        expected = APPROVED_FRESH_LOGICAL_DATASET_SHA256
    else:
        raise B649DatasetAuthorityError(
            f"unknown B649 dataset authority mode: {authority_mode!r}"
        )
    if value != expected:
        raise B649DatasetAuthorityError(
            f"dataset_sha256 is not authorized for {authority_mode or 'legacy'}"
        )
    return expected


__all__ = [
    "APPROVED_FRESH_LOGICAL_DATASET_SHA256",
    "LEGACY_PINNED_DATASET_SHA256",
    "B649DatasetAuthorityError",
    "validate_b649_dataset_sha256",
]
