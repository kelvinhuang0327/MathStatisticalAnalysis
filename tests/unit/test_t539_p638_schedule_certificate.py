"""DB-free acceptance for strict T539/P638 Owner schedule certificates."""

from __future__ import annotations

import hashlib
import json

import pytest

from lottolab.application.schedule_certificate import (
    OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION,
    OWNER_SCHEDULE_CERTIFYING_AUTHORITY,
    OfficialSupportArtifactType,
    ScheduleCertificateInputError,
)
from lottolab.application.schedule_sync import T539_SCHEDULE_GAME_CODE
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    OFFICIAL_SCHEDULE_SOURCE_ID,
    OFFICIAL_SCHEDULE_SOURCE_VERSION,
)
from lottolab.infrastructure.t539_p638_schedule_certificate import (
    parse_owner_schedule_certificate,
)

ARTIFACT = b"Official Taiwan Lottery future schedule: draw 9001 on 2099-01-02."


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()


def _certificate_input() -> dict[str, object]:
    return {
        "certification_reason": "OFFICIAL_AUTHORITY_ABSENT",
        "certified_at": "2099-01-01T01:00:00Z",
        "certifying_authority": OWNER_SCHEDULE_CERTIFYING_AUTHORITY,
        "draw_date": "2099-01-02",
        "draw_number": "9001",
        "lottery_type": LotteryType.DAILY_539.value,
        "official_game_code": T539_SCHEDULE_GAME_CODE,
        "official_source_id": OFFICIAL_SCHEDULE_SOURCE_ID,
        "official_source_locator": (
            "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/NextDrawDate"
        ),
        "official_source_observed_at": "2099-01-01T00:00:00Z",
        "official_source_version": OFFICIAL_SCHEDULE_SOURCE_VERSION,
        "schedule_timezone": "Asia/Taipei",
        "scheduled_at": "2099-01-02T12:30:00Z",
        "scheduled_local_time": "20:30:00",
        "source_period_identifier": "9001",
        "supporting_artifact_sha256": hashlib.sha256(ARTIFACT).hexdigest(),
        "supporting_artifact_type": (
            OfficialSupportArtifactType.OFFICIAL_TAIWAN_LOTTERY_HTTPS_PAYLOAD.value
        ),
    }


def _document(
    certificate_input: dict[str, object],
    *,
    input_sha256: str | None = None,
) -> bytes:
    payload = {
        "certificate_input": certificate_input,
        "certificate_input_sha256": (
            _canonical_sha256(certificate_input) if input_sha256 is None else input_sha256
        ),
        "schema_version": OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def _parse(
    certificate_input: dict[str, object],
    *,
    artifact: bytes = ARTIFACT,
    input_sha256: str | None = None,
):
    return parse_owner_schedule_certificate(
        _document(certificate_input, input_sha256=input_sha256),
        source_filename="owner-schedule-certificate.json",
        supporting_artifact=artifact,
    )


def test_valid_owner_certificate_binds_full_fact_and_both_exact_hashes() -> None:
    certificate_input = _certificate_input()
    encoded = _document(certificate_input)
    certificate = parse_owner_schedule_certificate(
        encoded,
        source_filename="owner-schedule-certificate.json",
        supporting_artifact=ARTIFACT,
    )

    assert certificate.fact.announcement.target.lottery_type is LotteryType.DAILY_539
    assert certificate.fact.announcement.target.draw_number == "9001"
    assert certificate.fact.official_game_code == T539_SCHEDULE_GAME_CODE
    assert certificate.fact.scheduled_local_time.isoformat() == "20:30:00"
    assert certificate.fact.announcement.scheduled_at.isoformat() == (
        "2099-01-02T12:30:00+00:00"
    )
    assert certificate.certificate_input_sha256 == _canonical_sha256(certificate_input)
    assert certificate.certificate_document_sha256 == hashlib.sha256(encoded).hexdigest()
    assert certificate.supporting_artifact_sha256 == hashlib.sha256(ARTIFACT).hexdigest()


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("certifying_authority", "PROJECT_OWNER:other"),
        ("official_game_code", 5134),
        ("source_period_identifier", "9002"),
        ("official_source_id", "UNOFFICIAL_SOURCE"),
        (
            "official_source_locator",
            "https://example.com/schedule/9001",
        ),
        (
            "official_source_locator",
            "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Daily539Result",
        ),
    ],
    ids=[
        "wrong-actor",
        "wrong-game-code",
        "wrong-source-period",
        "unofficial-source-id",
        "unofficial-host",
        "completed-result-locator",
    ],
)
def test_invalid_authority_identity_or_support_is_rejected(
    field: str,
    invalid_value: object,
) -> None:
    certificate_input = _certificate_input()
    certificate_input[field] = invalid_value

    with pytest.raises(ScheduleCertificateInputError):
        _parse(certificate_input)


def test_missing_required_field_is_rejected() -> None:
    certificate_input = _certificate_input()
    del certificate_input["draw_number"]

    with pytest.raises(ScheduleCertificateInputError):
        _parse(certificate_input)


def test_bad_supporting_sha256_is_rejected() -> None:
    certificate_input = _certificate_input()
    certificate_input["supporting_artifact_sha256"] = "f" * 64

    with pytest.raises(ScheduleCertificateInputError):
        _parse(certificate_input)


def test_bad_certificate_input_sha256_is_rejected() -> None:
    with pytest.raises(ScheduleCertificateInputError):
        _parse(_certificate_input(), input_sha256="0" * 64)


@pytest.mark.parametrize(
    ("field", "timestamp"),
    [
        ("official_source_observed_at", "2099-01-02T12:30:00Z"),
        ("certified_at", "2099-01-02T12:30:00Z"),
    ],
)
def test_observation_and_certification_must_strictly_precede_schedule(
    field: str,
    timestamp: str,
) -> None:
    certificate_input = _certificate_input()
    certificate_input[field] = timestamp

    with pytest.raises(ScheduleCertificateInputError):
        _parse(certificate_input)


def test_certification_cannot_precede_official_source_observation() -> None:
    certificate_input = _certificate_input()
    certificate_input["certified_at"] = "2098-12-31T23:59:59Z"

    with pytest.raises(ScheduleCertificateInputError):
        _parse(certificate_input)


def test_draw_number_must_be_explicit_in_exact_supporting_artifact() -> None:
    certificate_input = _certificate_input()
    artifact = b"Official Taiwan Lottery future schedule with no draw identity."
    certificate_input["supporting_artifact_sha256"] = hashlib.sha256(artifact).hexdigest()

    with pytest.raises(ScheduleCertificateInputError):
        _parse(certificate_input, artifact=artifact)


def test_manual_certificate_can_express_explicit_non_normal_draw_time() -> None:
    certificate_input = _certificate_input()
    certificate_input["scheduled_local_time"] = "21:15:00"
    certificate_input["scheduled_at"] = "2099-01-02T13:15:00Z"
    certificate = _parse(certificate_input)

    assert certificate.fact.scheduled_local_time.isoformat() == "21:15:00"
    assert certificate.fact.announcement.scheduled_at.isoformat() == (
        "2099-01-02T13:15:00+00:00"
    )


def test_duplicate_json_member_is_rejected() -> None:
    encoded = (
        b'{"schema_version":"LOTTOLAB_T539_P638_SCHEDULE_CERTIFICATE_V1",'
        b'"schema_version":"LOTTOLAB_T539_P638_SCHEDULE_CERTIFICATE_V1",'
        b'"certificate_input":{},"certificate_input_sha256":"'
        + b"0" * 64
        + b'"}'
    )

    with pytest.raises(ScheduleCertificateInputError):
        parse_owner_schedule_certificate(
            encoded,
            source_filename="owner-schedule-certificate.json",
            supporting_artifact=ARTIFACT,
        )
