"""Verify a third-party pre-draw seal before the existing score phase."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from lottolab.application.prospective_observer import (
    ProspectiveObservationStore,
    ScorePhaseRequest,
    ScoreSyncResult,
    ScoringPhaseService,
    repository_game_contracts,
)
from lottolab.domain.pre_outcome_target import PreOutcomeTargetRegistration
from lottolab.domain.prospective_observer import OfficialOutcome, PredictionRecord
from lottolab.infrastructure.k3_rfc3161 import TimestampProof, verify_timestamp


def prediction_seal_bytes(
    prediction: PredictionRecord, registration: PreOutcomeTargetRegistration
) -> bytes:
    """Bind prediction content, its recorded time, and the full target authority."""
    if (
        prediction.identity.lottery_type is not registration.target.lottery_type
        or prediction.identity.target_draw_number != registration.target.draw_number
        or prediction.identity.target_draw_date != registration.target.draw_date
        or prediction.causal_history != registration.causal_history
        or prediction.predicted_at < registration.registered_at
        or prediction.predicted_at >= registration.announcement.scheduled_at
    ):
        raise ValueError("prediction is not bound to the registered pre-draw target")
    document = {
        "schema_version": "K3_PREDICTION_PRE_DRAW_SEAL_V1",
        "registration": registration.canonical_dict(),
        "prediction": prediction.canonical_material(),
        "prediction_sha256": prediction.prediction_hash,
        "predicted_at": prediction.predicted_at.isoformat(),
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def score_timestamped_prediction(
    *,
    store: ProspectiveObservationStore,
    prediction: PredictionRecord,
    registration: PreOutcomeTargetRegistration,
    outcome: OfficialOutcome,
    proof: TimestampProof,
    openssl: Path,
    ca_file: Path,
    scratch_root: Path,
    clock: Callable[[], datetime],
) -> ScoreSyncResult:
    """Score after a valid independent pre-draw timestamp and exact target join.

    The caller must still verify the official or locally authenticated source
    of ``outcome``; timestamping alone establishes no outcome provenance.
    """
    payload = prediction_seal_bytes(prediction, registration)
    tsa_time = verify_timestamp(
        payload, proof, openssl=openssl, ca_file=ca_file, scratch_root=scratch_root
    )
    now = clock()
    if type(now) is not datetime or now.tzinfo is not UTC:
        raise ValueError("score clock must return UTC")
    if (
        tsa_time < prediction.predicted_at.replace(microsecond=0)
        or tsa_time >= registration.announcement.scheduled_at
        or now < registration.announcement.scheduled_at
        or now < tsa_time
    ):
        raise ValueError("timestamp or scoring time is not on the required side of the draw")
    return ScoringPhaseService(
        store=store, game_contracts=repository_game_contracts(), clock=clock
    ).sync(ScorePhaseRequest(prediction.identity, prediction.producer_fingerprint, outcome))
