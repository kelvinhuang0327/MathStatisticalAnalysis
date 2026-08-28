from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any, cast

import pytest

from lottolab.application.biglotto_l2_pairwise_prospective_shadow_capture import (
    BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_BUNDLE_SCHEMA_VERSION,
    BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_RECORD_SCHEMA_VERSION,
    ProspectiveCandidateRuntime,
    ProspectiveShadowBundleShapeError,
    ProspectiveShadowBundleTamperError,
    ProspectiveShadowCaptureRequest,
    _capture_prospective_shadow_bundle_with_runtime,  # pyright: ignore[reportPrivateUsage]
    deserialize_prospective_shadow_bundle,
    serialize_prospective_shadow_bundle,
    verify_prospective_shadow_bundle,
)
from lottolab.application.future_draw_identity import normalized_announcement_sha256
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
    OrderedCandidateEmission,
)
from lottolab.domain.pre_outcome_target import TargetAnnouncement, TargetSourceProvenance
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.evidence.canonical_json import (
    canonical_bytes,
    loads_canonical,
    self_key_removed_sha256,
)

TARGET_DRAW = "115000082"
HISTORY_CUTOFF = "115000081"
EXPECTED_IDS = ("C1", "C2", "C3", "C4", "C5", "C6", "C8", "C9", "C10")
REPOSITORY_HEAD = "a" * 40
REPOSITORY_TREE = "b" * 40
GENERATED_AT = datetime(2026, 8, 31, 1, tzinfo=UTC)
HISTORY: tuple[object, ...] = tuple(range(751))


def _capture(request: ProspectiveShadowCaptureRequest):
    bundle, _ = _capture_prospective_shadow_bundle_with_runtime(
        request,
        monotonic_ns=None,
    )
    return bundle


def _announcement() -> TargetAnnouncement:
    return TargetAnnouncement(
        target=ObservationTarget(
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number=TARGET_DRAW,
            draw_date=date(2026, 9, 1),
        ),
        schedule_timezone="Asia/Taipei",
        scheduled_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
        source=TargetSourceProvenance(
            source_id="synthetic_schedule",
            source_version="r1",
            source_locator="fixture://future-draw",
            source_sha256="c" * 64,
            observed_at=datetime(2026, 8, 31, tzinfo=UTC),
        ),
    )


def _method_id(candidate_id: str) -> str:
    return f"SYNTHETIC_PAIRWISE_METHOD_{candidate_id}"


def _signature(candidate_id: str) -> str:
    return hashlib.sha256(candidate_id.encode()).hexdigest()


def _emission(
    candidate_id: str,
    ticket: tuple[int, ...],
    *,
    method_id: str | None = None,
    strategy_version: str = "r1",
    target_draw: str = TARGET_DRAW,
    history_cutoff: str = HISTORY_CUTOFF,
) -> OrderedCandidateEmission:
    return OrderedCandidateEmission(
        schema_version=ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id=method_id or _method_id(candidate_id),
        strategy_version=strategy_version,
        replicate=1,
        target_draw=target_draw,
        history_cutoff=history_cutoff,
        emitted_main_numbers=ticket,
        auxiliary_operand_kind=AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
        auxiliary_operand_availability=AuxiliaryOperandAvailability.EXPLICITLY_MISSING,
        auxiliary_operand_value=None,
    )


def _runtime(
    candidate_id: str,
    *,
    ticket: tuple[int, ...] | None = None,
) -> ProspectiveCandidateRuntime:
    index = int(candidate_id[1:])
    selected_ticket = ticket or tuple(range(index, index + 6))

    def produce(
        history: tuple[object, ...],
        history_cutoff: str,
        /,
    ) -> OrderedCandidateEmission:
        assert history is HISTORY
        assert history_cutoff == HISTORY_CUTOFF
        return _emission(candidate_id, selected_ticket)

    return ProspectiveCandidateRuntime(
        candidate_id=candidate_id,
        method_id=_method_id(candidate_id),
        semantic_signature=_signature(candidate_id),
        strategy_version="r1",
        producer=produce,
    )


def _request(
    *,
    runtimes: tuple[ProspectiveCandidateRuntime, ...] | None = None,
) -> ProspectiveShadowCaptureRequest:
    return ProspectiveShadowCaptureRequest(
        announcement=_announcement(),
        history=HISTORY,
        history_cutoff=HISTORY_CUTOFF,
        expected_candidate_ids=EXPECTED_IDS,
        candidate_runtimes=runtimes
        or tuple(_runtime(candidate_id) for candidate_id in reversed(EXPECTED_IDS)),
        generated_at_utc=GENERATED_AT,
        repository_head=REPOSITORY_HEAD,
        repository_tree=REPOSITORY_TREE,
    )


def _assert_no_later_stage_keys(value: object) -> None:
    forbidden_fragments = ("outcome", "score", "report")
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        for key, item in mapping.items():
            assert isinstance(key, str)
            assert not any(fragment in key.casefold() for fragment in forbidden_fragments)
            _assert_no_later_stage_keys(item)
    elif isinstance(value, list):
        for item in cast(list[object], value):
            _assert_no_later_stage_keys(item)


def test_capture_is_repeatable_canonical_ordered_and_stops_at_seal() -> None:
    request = _request()

    first = _capture(request)
    second = _capture(request)
    first_bytes = serialize_prospective_shadow_bundle(first)
    second_bytes = serialize_prospective_shadow_bundle(second)

    assert first == second
    assert first_bytes == second_bytes
    assert first.bundle_sha256 == second.bundle_sha256
    assert first.schema_version == (BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_BUNDLE_SCHEMA_VERSION)
    assert tuple(record.candidate_id for record in first.predictions) == EXPECTED_IDS
    assert all(
        record.schema_version == BIGLOTTO_L2_PAIRWISE_PROSPECTIVE_SHADOW_RECORD_SCHEMA_VERSION
        for record in first.predictions
    )
    assert all(
        len(record.ticket) == 6
        and record.ticket == tuple(sorted(record.ticket))
        and len(set(record.ticket)) == 6
        and all(1 <= number <= 49 for number in record.ticket)
        for record in first.predictions
    )
    assert all(record.history_cutoff == HISTORY_CUTOFF for record in first.predictions)
    assert all(record.history_row_count == 751 for record in first.predictions)
    assert first.target_announcement_sha256 == normalized_announcement_sha256(request.announcement)

    parsed = loads_canonical(first_bytes)
    assert canonical_bytes(parsed) == first_bytes
    _assert_no_later_stage_keys(parsed)
    assert verify_prospective_shadow_bundle(first_bytes) == first


@pytest.mark.parametrize(
    "ticket",
    [
        (1, 1, 2, 3, 4, 5),
        (6, 5, 4, 3, 2, 1),
        (1, 2, 3, 4, 5),
    ],
)
def test_capture_rejects_nonlegal_ticket(ticket: tuple[int, ...]) -> None:
    runtimes = tuple(
        _runtime(candidate_id, ticket=ticket if candidate_id == "C1" else None)
        for candidate_id in EXPECTED_IDS
    )

    with pytest.raises(ValueError, match="six distinct sorted"):
        _capture(_request(runtimes=runtimes))


@pytest.mark.parametrize(
    ("mismatch", "message"),
    [
        ("method", "strategy_id"),
        ("version", "strategy_version"),
        ("target", "target_draw"),
        ("cutoff", "history_cutoff"),
    ],
)
def test_capture_rejects_candidate_identity_or_cutoff_mismatch(
    mismatch: str,
    message: str,
) -> None:
    first = _runtime("C1")

    def mismatched_producer(
        history: tuple[object, ...],
        history_cutoff: str,
        /,
    ) -> OrderedCandidateEmission:
        assert history is HISTORY
        assert history_cutoff == HISTORY_CUTOFF
        return _emission(
            "C1",
            (1, 2, 3, 4, 5, 6),
            method_id="DIFFERENT_METHOD" if mismatch == "method" else None,
            strategy_version="r2" if mismatch == "version" else "r1",
            target_draw="115000083" if mismatch == "target" else TARGET_DRAW,
            history_cutoff="115000080" if mismatch == "cutoff" else HISTORY_CUTOFF,
        )

    runtimes = (
        replace(first, producer=mismatched_producer),
        *(_runtime(candidate_id) for candidate_id in EXPECTED_IDS[1:]),
    )
    with pytest.raises(ValueError, match=message):
        _capture(_request(runtimes=runtimes))


def test_request_requires_exact_nine_candidate_set_and_common_history() -> None:
    complete = _request()

    with pytest.raises(ValueError, match="exactly nine"):
        replace(
            complete,
            expected_candidate_ids=EXPECTED_IDS[:-1],
            candidate_runtimes=complete.candidate_runtimes[:-1],
        )
    with pytest.raises(ValueError, match="common nine-candidate minimum"):
        replace(complete, history=HISTORY[:-1])


def test_bundle_rejects_byte_tampering() -> None:
    data = serialize_prospective_shadow_bundle(_capture(_request()))
    typed_payload = cast(dict[str, Any], loads_canonical(data))
    predictions = typed_payload["predictions"]
    assert isinstance(predictions, list)
    first = cast(dict[str, Any], predictions[0])
    first["ticket"] = [20, 21, 22, 23, 24, 25]
    tampered = canonical_bytes(typed_payload)

    with pytest.raises(ProspectiveShadowBundleTamperError, match="bundle digest"):
        deserialize_prospective_shadow_bundle(tampered)


def test_bundle_rejects_rehashed_ticket_with_stale_prediction_digest() -> None:
    data = serialize_prospective_shadow_bundle(_capture(_request()))
    payload = cast(dict[str, Any], loads_canonical(data))
    predictions = payload["predictions"]
    assert isinstance(predictions, list)
    first = cast(dict[str, Any], predictions[0])
    first["ticket"] = [20, 21, 22, 23, 24, 25]
    payload["bundle_sha256"] = self_key_removed_sha256(payload, "bundle_sha256")

    with pytest.raises(ProspectiveShadowBundleTamperError, match="prediction payload"):
        deserialize_prospective_shadow_bundle(canonical_bytes(payload))


def test_bundle_rejects_unknown_fields_and_noncanonical_bytes() -> None:
    data = serialize_prospective_shadow_bundle(_capture(_request()))
    payload = cast(dict[str, Any], loads_canonical(data))
    payload["unexpected"] = "field"

    with pytest.raises(ProspectiveShadowBundleShapeError, match="keys are not closed"):
        deserialize_prospective_shadow_bundle(canonical_bytes(payload))
    with pytest.raises(ProspectiveShadowBundleShapeError, match="exact LCJ-1"):
        deserialize_prospective_shadow_bundle(data + b"\n")


def test_every_required_record_field_is_present() -> None:
    data = serialize_prospective_shadow_bundle(_capture(_request()))
    payload = cast(dict[str, Any], loads_canonical(data))
    predictions = payload["predictions"]
    assert isinstance(predictions, list)
    required = {
        "candidate_id",
        "generated_at_utc",
        "history_cutoff",
        "lottery_type",
        "method_id",
        "prediction_payload_sha256",
        "repository_head",
        "repository_tree",
        "semantic_signature",
        "strategy_version",
        "target_announcement",
        "target_announcement_sha256",
        "target_draw",
        "ticket",
    }
    records = cast(list[object], predictions)
    assert all(
        isinstance(record, dict) and required <= cast(dict[str, Any], record).keys()
        for record in records
    )


def test_canonical_parser_result_remains_json_domain() -> None:
    bundle = _capture(_request())
    parsed: Any = loads_canonical(serialize_prospective_shadow_bundle(bundle))

    assert isinstance(parsed, dict)
    assert parsed["bundle_sha256"] == bundle.bundle_sha256
