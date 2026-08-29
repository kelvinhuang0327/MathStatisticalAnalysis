"""API contract tests for the read-only /api/v1/next-draw-recommendation/lifecycle route."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from lottolab.application.use_cases.get_next_draw_recommendation_lifecycle import (
    GetNextDrawRecommendationLifecycle,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_recommendation import NATIVE_TICKET_COUNT_BUCKETS
from lottolab.domain.next_draw_recommendation_seal import (
    NextDrawRecommendationSeal,
    SealedRecommendationBucket,
    SealedStrategyTickets,
    TicketSealStatus,
)
from lottolab.domain.pre_outcome_target import TargetSourceProvenance
from lottolab.domain.prospective_observer import ObservationTarget, OutcomePresenceAtPrediction
from lottolab.interfaces.api.app import create_app

PREFIX = "/api/v1/next-draw-recommendation/lifecycle"
TARGET = ObservationTarget(
    lottery_type=LotteryType.BIG_LOTTO, draw_number="115000090", draw_date=date(2099, 9, 1)
)
SCHEDULED_AT = datetime(2099, 9, 1, 8, 30, tzinfo=UTC)
SEALED_AT = datetime(2099, 8, 30, 10, 0, tzinfo=UTC)
NOW = datetime(2099, 8, 30, 6, 0, tzinfo=UTC)


class _Reader:
    def __init__(self, future: object | None = None) -> None:
        self._future = future

    def find_earliest_unpopulated_future(self, lottery_type, as_of):
        del lottery_type, as_of
        return self._future

    def find_earliest_unpopulated_due(self, lottery_type, as_of):
        del lottery_type, as_of
        return None

    def get_scheduled_draw(self, lottery_type, draw_number):
        del lottery_type, draw_number
        return self._future


def _future_record(target: ObservationTarget) -> object:
    return SimpleNamespace(announcement=SimpleNamespace(target=target))


class _PresenceProbe:
    def __init__(self, presence: OutcomePresenceAtPrediction) -> None:
        self._presence = presence

    def probe(self, target, *, as_of):
        from lottolab.domain.pre_outcome_target import OutcomePresenceAttestation

        return OutcomePresenceAttestation(
            target=target,
            presence=self._presence,
            attested_at=as_of,
            source=TargetSourceProvenance(
                source_id="official-presence-audit",
                source_version="v1",
                source_locator="https://example.test/audit",
                source_sha256="b" * 64,
                observed_at=as_of,
            ),
        )


class _SealReader:
    def __init__(self, seal: NextDrawRecommendationSeal | None = None) -> None:
        self._seal = seal

    def get_seal(self, target):
        return self._seal if self._seal is not None and self._seal.target == target else None


def _seal() -> NextDrawRecommendationSeal:
    ticket = SealedStrategyTickets(
        rank=1,
        strategy_id="s1",
        strategy_name="Strategy One",
        status=TicketSealStatus.OK,
        tickets=((1, 2, 3, 4, 5, 6),),
        detail="",
    )
    buckets = tuple(
        SealedRecommendationBucket(
            native_ticket_count=count,
            availability="AVAILABLE" if count == 1 else "UNAVAILABLE",
            total_candidate_count=1 if count == 1 else 0,
            ranked_strategy_ids=("s1",) if count == 1 else (),
            ranking_projection_sha256="c" * 64,
            sealed_tickets=(ticket,) if count == 1 else (),
        )
        for count in NATIVE_TICKET_COUNT_BUCKETS
    )
    return NextDrawRecommendationSeal.create(
        target=TARGET,
        target_scheduled_at=SCHEDULED_AT,
        sealed_at=SEALED_AT,
        target_registration_digest="d" * 64,
        evidence_artifact_sha256="e" * 64,
        causal_history_sha256="f" * 64,
        causal_history_draw_count=2,
        buckets=buckets,
    )


def _client(reader_factory) -> TestClient:
    return TestClient(
        create_app(
            next_draw_recommendation_evidence_factory=lambda: None,
            next_draw_recommendation_causal_history_factory=lambda lottery_type: (),
            next_draw_recommendation_lifecycle_reader_factory=reader_factory,
        )
    )


def test_lifecycle_route_returns_503_when_not_configured() -> None:
    # A factory that itself resolves to "unavailable" -- not a bare None,
    # which would instead fall back to create_app's real default composition
    # (and so hit the real local environment) rather than testing this path.
    client = _client(lambda: None)

    response = client.get(PREFIX)

    assert response.status_code == 503
    assert response.json()["error_code"] == "NEXT_DRAW_RECOMMENDATION_LIFECYCLE_UNAVAILABLE"


def test_lifecycle_route_reports_waiting_for_eligible_target() -> None:
    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=_Reader(None),
        outcome_presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_reader=_SealReader(),
        clock=lambda: NOW,
    )
    client = _client(lambda: use_case)

    response = client.get(PREFIX)

    assert response.status_code == 200
    body = response.json()
    assert body["lifecycle_state"] == "WAITING_FOR_ELIGIBLE_TARGET"
    assert body["target_draw_number"] is None
    assert body["sealed_buckets"] == []


def test_lifecycle_route_reports_target_available_with_no_sealed_data() -> None:
    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=_Reader(_future_record(TARGET)),
        outcome_presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_reader=_SealReader(),
        clock=lambda: NOW,
    )
    client = _client(lambda: use_case)

    response = client.get(PREFIX)

    assert response.status_code == 200
    body = response.json()
    assert body["lifecycle_state"] == "TARGET_AVAILABLE"
    assert body["target_draw_number"] == "115000090"
    assert body["target_draw_date"] == "2099-09-01"
    assert body["sealed_at"] is None
    assert body["sealed_buckets"] == []


def test_lifecycle_route_reports_predictions_sealed_with_full_sealed_buckets() -> None:
    seal = _seal()
    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=_Reader(_future_record(TARGET)),
        outcome_presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_reader=_SealReader(seal),
        clock=lambda: NOW,
    )
    client = _client(lambda: use_case)

    response = client.get(PREFIX)

    assert response.status_code == 200
    body = response.json()
    assert body["lifecycle_state"] == "PREDICTIONS_SEALED"
    assert body["target_draw_number"] == "115000090"
    assert body["sealed_at"] == "2099-08-30T10:00:00Z"
    assert body["target_scheduled_at"] == "2099-09-01T08:30:00Z"
    assert body["evidence_artifact_sha256"] == "e" * 64
    assert len(body["sealed_buckets"]) == len(NATIVE_TICKET_COUNT_BUCKETS)
    one_ticket_bucket = next(b for b in body["sealed_buckets"] if b["native_ticket_count"] == 1)
    assert one_ticket_bucket["sealed_tickets"] == [
        {
            "rank": 1,
            "strategy_id": "s1",
            "strategy_name": "Strategy One",
            "status": "OK",
            "tickets": [[1, 2, 3, 4, 5, 6]],
            "detail": "",
        }
    ]


def test_lifecycle_route_reports_outcome_available() -> None:
    seal = _seal()
    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=_Reader(_future_record(TARGET)),
        outcome_presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.PRESENT),
        seal_reader=_SealReader(seal),
        clock=lambda: NOW,
    )
    client = _client(lambda: use_case)

    response = client.get(PREFIX)

    assert response.status_code == 200
    assert response.json()["lifecycle_state"] == "OUTCOME_AVAILABLE"


def test_lifecycle_route_is_a_pure_get_with_no_request_body_effect() -> None:
    use_case = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=_Reader(_future_record(TARGET)),
        outcome_presence_probe=_PresenceProbe(OutcomePresenceAtPrediction.ABSENT),
        seal_reader=_SealReader(),
        clock=lambda: NOW,
    )
    client = _client(lambda: use_case)

    first = client.get(PREFIX).json()
    second = client.get(PREFIX).json()

    assert first == second
