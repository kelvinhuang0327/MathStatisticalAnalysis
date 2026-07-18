"""Deterministic source-to-snapshot normalization contract."""

from lottolab.normalization.models import (
    DatasetNormalizationManifest,
    NormalizationFinding,
    NormalizationOutcome,
    NormalizationParameters,
    NormalizationResult,
    RecordMappingKind,
)
from lottolab.normalization.normalizer import (
    manifest_canonical_bytes,
    manifest_committed_bytes,
    normalize,
    snapshot_canonical_bytes,
    snapshot_committed_bytes,
    verify_replay,
)

__all__ = [
    "DatasetNormalizationManifest",
    "NormalizationFinding",
    "NormalizationOutcome",
    "NormalizationParameters",
    "NormalizationResult",
    "RecordMappingKind",
    "manifest_canonical_bytes",
    "manifest_committed_bytes",
    "normalize",
    "snapshot_canonical_bytes",
    "snapshot_committed_bytes",
    "verify_replay",
]
