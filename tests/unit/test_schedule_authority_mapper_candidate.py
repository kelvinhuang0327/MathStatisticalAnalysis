"""TEST_ONLY contract checks for the named official schedule Provider mapper."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lottolab.application.future_draw_identity import normalized_announcement_sha256
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    SCHEDULE_GAME_CODE,
    SCHEDULE_URL,
    OfficialHttpsClient,
    TaiwanLotteryScheduleProvider,
    parse_official_b649_schedule,
)

TEST_ONLY = "TEST_ONLY"
AS_OF = datetime(2026, 11, 24, 4, 0, tzinfo=UTC)
DRAW_NUMBER = "115000120"
DRAW_DATE = "20261205"
_mapper_path = (
    Path(__file__).resolve().parents[2]
    / "src/lottolab/infrastructure/schedule_authority_mapper_candidate.py"
)
_mapper_name = "lottolab.infrastructure.schedule_authority_mapper_candidate"
_mapper_spec = importlib.util.spec_from_file_location(_mapper_name, _mapper_path)
assert _mapper_spec is not None and _mapper_spec.loader is not None
_mapper = importlib.util.module_from_spec(_mapper_spec)
sys.modules[_mapper_spec.name] = _mapper
_mapper_spec.loader.exec_module(_mapper)
EXPECTED_PROVIDER_ID = _mapper.EXPECTED_PROVIDER_ID
EXPECTED_PROVIDER_VERSION = _mapper.EXPECTED_PROVIDER_VERSION
EXPECTED_SOURCE_URL = _mapper.EXPECTED_SOURCE_URL
ScheduleAuthorityMappingError = _mapper.ScheduleAuthorityMappingError
map_official_schedule = _mapper.map_official_schedule
validate_official_schedule_binding = _mapper.validate_official_schedule_binding


def _body(*, dates: tuple[str, ...] = (DRAW_DATE,)) -> bytes:
    return json.dumps(
        {
            "evidence_label": TEST_ONLY,
            "rtCode": 0,
            "content": {
                "nextDrawDateList": [
                    {"gameCode": SCHEDULE_GAME_CODE, "drawTerm": DRAW_NUMBER, "drawDate": value}
                    for value in dates
                ]
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _provider(
    payload: bytes | None = None,
    *,
    source_url: str = SCHEDULE_URL,
    transport_error: Exception | None = None,
) -> tuple[TaiwanLotteryScheduleProvider, list[str]]:
    test_payload = _body() if payload is None else payload
    calls: list[str] = []

    def transport(request, _context, _timeout, _max_response_bytes):
        calls.append(request.full_url)
        if transport_error is not None:
            raise transport_error
        return test_payload

    provider = TaiwanLotteryScheduleProvider(
        https_client=OfficialHttpsClient(transport=transport),
        source_url=source_url,
    )
    return provider, calls


def _tamper_provider_result(
    provider: TaiwanLotteryScheduleProvider, field: str, value: object
) -> None:
    fetch = provider.fetch_schedule

    def tampered_fetch(*, observed_at):
        result = fetch(observed_at=observed_at)
        object.__setattr__(result, field, value)
        return result

    provider.fetch_schedule = tampered_fetch


def test_controlled_test_only_transport_runs_real_provider_parser_and_keeps_digests_separate() -> (
    None
):
    payload = _body()
    provider, calls = _provider(payload)
    bindings = map_official_schedule(provider, as_of=AS_OF)
    test_output = {"evidence_label": TEST_ONLY, "admission_count": len(bindings)}

    assert calls == [SCHEDULE_URL]
    assert test_output == {"evidence_label": TEST_ONLY, "admission_count": 1}
    binding = bindings[0]
    assert binding["evidence_label"] == "OFFICIAL_AUTHORITY"
    assert binding["authority_name"] == EXPECTED_PROVIDER_ID
    assert binding["provider_version"] == EXPECTED_PROVIDER_VERSION
    assert binding["source_url"] == EXPECTED_SOURCE_URL
    assert binding["source_payload_sha256"] == hashlib.sha256(payload).hexdigest()
    parsed = parse_official_b649_schedule(payload, observed_at=AS_OF, source_url=SCHEDULE_URL)
    assert binding["normalized_announcement_sha256"] == normalized_announcement_sha256(parsed[0])
    assert binding["schedule_authority_sha256"] == binding["normalized_announcement_sha256"]
    assert binding["source_payload_sha256"] != binding["normalized_announcement_sha256"]
    assert binding["target_draw_number"] == DRAW_NUMBER
    assert binding["target_draw_date"] == "2026-12-05"
    assert binding["scheduled_at"] == "2026-12-05T20:30:00+08:00"
    assert binding["timezone"] == "Asia/Taipei"
    assert binding["observed_at"] == "2026-11-24T04:00:00Z"
    validate_official_schedule_binding(binding)


def test_synthetic_or_self_labeled_json_cannot_enter_official_mapper() -> None:
    for forged in (
        {"evidence_label": "SYNTHETIC", "target_draw_number": DRAW_NUMBER},
        {
            "evidence_label": "OFFICIAL_AUTHORITY",
            "authority_name": EXPECTED_PROVIDER_ID,
            "source_payload_sha256": "a" * 64,
        },
    ):
        with pytest.raises(ScheduleAuthorityMappingError, match="named Taiwan Lottery Provider"):
            map_official_schedule(forged, as_of=AS_OF)  # type: ignore[arg-type]


def test_provider_endpoint_identity_must_match_pinned_source() -> None:
    provider, _calls = _provider(source_url="https://api.taiwanlottery.com/other/schedule")

    with pytest.raises(ScheduleAuthorityMappingError, match="Provider URL"):
        map_official_schedule(provider, as_of=AS_OF)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("provider_id", "UNTRUSTED_PROVIDER", "Provider identity"),
        ("source_payload_sha256", "0" * 64, "provenance conflicts"),
        ("observed_at", datetime(2026, 11, 23, 4, 0, tzinfo=UTC), "observation does not match"),
    ],
)
def test_provider_result_identity_digest_and_time_tampering_is_rejected(
    field: str,
    value: object,
    message: str,
) -> None:
    provider, _calls = _provider()
    _tamper_provider_result(provider, field, value)

    with pytest.raises(ScheduleAuthorityMappingError, match=message):
        map_official_schedule(provider, as_of=AS_OF)


def test_normalized_digest_or_target_content_tampering_is_rejected() -> None:
    provider, _calls = _provider()
    binding = map_official_schedule(provider, as_of=AS_OF)[0]
    for field, value in (
        ("normalized_announcement_sha256", "f" * 64),
        ("target_draw_number", "115000121"),
        ("target_draw_date", "2026-12-06"),
        ("authority_name", "UNTRUSTED_PROVIDER"),
    ):
        changed = dict(binding)
        changed[field] = value
        with pytest.raises(ScheduleAuthorityMappingError):
            validate_official_schedule_binding(changed)


def test_expired_schedule_is_not_admitted() -> None:
    provider, _calls = _provider(_body(dates=("20261124",)))
    after_draw = datetime(2026, 11, 24, 15, 0, tzinfo=UTC)

    with pytest.raises(ScheduleAuthorityMappingError, match="did not validate a schedule"):
        map_official_schedule(provider, as_of=after_draw)


def test_transport_timeout_is_not_admitted() -> None:
    provider, calls = _provider(transport_error=TimeoutError("TEST_ONLY timeout"))

    with pytest.raises(ScheduleAuthorityMappingError, match="did not validate a schedule"):
        map_official_schedule(provider, as_of=AS_OF)
    assert calls == [SCHEDULE_URL]


def test_conflicting_duplicate_target_is_not_admitted() -> None:
    provider, _calls = _provider(_body(dates=("20261205", "20261212")))

    with pytest.raises(ScheduleAuthorityMappingError, match="did not validate a schedule"):
        map_official_schedule(provider, as_of=AS_OF)
