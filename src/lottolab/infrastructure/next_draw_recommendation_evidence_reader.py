"""Read the packaged Next-Draw Recommendation evidence artifact (P1/P2)."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from lottolab.evidence.next_draw_recommendation_evidence import (
    NextDrawRecommendationEvidenceArtifact,
    RecommendationEvidenceArtifactTamperError,
)

_RESOURCE_NAME = "biglotto_next_draw_recommendation_evidence_v1.json"


class NextDrawRecommendationEvidenceUnavailableError(RuntimeError):
    """The packaged evidence artifact is absent, malformed, or tampered."""


class PackagedNextDrawRecommendationEvidenceReader:
    """Read only the exact named resource; never discover artifacts at runtime."""

    def read(self) -> NextDrawRecommendationEvidenceArtifact:
        return _read_packaged_artifact()


@lru_cache(maxsize=1)
def _read_packaged_artifact() -> NextDrawRecommendationEvidenceArtifact:
    resource = files("lottolab.strategies.data").joinpath(_RESOURCE_NAME)
    try:
        raw = resource.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise NextDrawRecommendationEvidenceUnavailableError(
            "the packaged Next-Draw Recommendation evidence artifact is unavailable"
        ) from exc
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NextDrawRecommendationEvidenceUnavailableError(
            "the packaged Next-Draw Recommendation evidence artifact is invalid JSON"
        ) from exc
    try:
        return NextDrawRecommendationEvidenceArtifact.from_canonical_dict(payload)
    except (RecommendationEvidenceArtifactTamperError, KeyError, ValueError) as exc:
        raise NextDrawRecommendationEvidenceUnavailableError(
            "the packaged Next-Draw Recommendation evidence artifact failed validation"
        ) from exc


__all__ = [
    "NextDrawRecommendationEvidenceUnavailableError",
    "PackagedNextDrawRecommendationEvidenceReader",
]
