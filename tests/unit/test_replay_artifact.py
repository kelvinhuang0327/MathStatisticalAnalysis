"""Closed-outcome tests for Replay canonical serialization and hashing.

Pure evidence-layer tests: no reader, no adapter, no use case — only
:mod:`lottolab.evidence.replay_artifact` against directly constructed domain
values.
"""

from __future__ import annotations

from datetime import date

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.domain.replay_predictions import (
    ReplayPredictionSnapshot,
    ReplaySourceMode,
    ReplayTarget,
)
from lottolab.evidence.replay_artifact import (
    ReplayArtifact,
    ReplayArtifactShapeError,
    ReplayArtifactTamperError,
    build_replay_artifact,
    build_replay_prediction_snapshot,
    causal_history_sha256,
    deserialize_replay_artifact,
    recompute_artifact_payload_sha256,
    recompute_snapshot_result_sha256,
    serialize_replay_artifact,
)

_STRATEGY_ID = "fixture_strategy"
_STRATEGY_IDENTITY = (_STRATEGY_ID, "Fixture Strategy", "v1")


def _history_row(number: str, day: int, main: tuple[int, ...], special: int) -> ReplayCausalDrawRow:
    return ReplayCausalDrawRow(
        draw_number=number,
        draw_date=date(2020, 1, day),
        main_numbers=main,
        special_number=special,
    )


def _history() -> tuple[ReplayCausalDrawRow, ...]:
    return (
        _history_row("1", 1, (1, 2, 3, 4, 5, 6), 44),
        _history_row("2", 2, (7, 8, 9, 10, 11, 12), 45),
    )


def _target() -> ReplayTarget:
    return ReplayTarget(draw_number="999", draw_date=date(2020, 1, 3))


def _ok_snapshot(
    *,
    main_numbers: tuple[int, ...] = (1, 2, 3, 4, 5, 6),
    history: tuple[ReplayCausalDrawRow, ...] | None = None,
) -> ReplayPredictionSnapshot:
    return build_replay_prediction_snapshot(
        dataset_id="DS1",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        target=_target(),
        strategy_id=_STRATEGY_ID,
        strategy_identity=_STRATEGY_IDENTITY,
        history_status="OK",
        history_reason_code=None,
        causal_history=history if history is not None else _history(),
        prediction_status="OK",
        prediction_reason_code=None,
        predicted_main_numbers=main_numbers,
    )


def _failure_snapshot() -> ReplayPredictionSnapshot:
    return build_replay_prediction_snapshot(
        dataset_id="DS1",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        target=_target(),
        strategy_id="unknown_strategy",
        strategy_identity=None,
        history_status="TARGET_NOT_FOUND",
        history_reason_code="TARGET_DRAW_NOT_FOUND",
        causal_history=None,
        prediction_status=None,
        prediction_reason_code=None,
        predicted_main_numbers=None,
    )


# --------------------------------------------------------------------------
# causal_history_sha256
# --------------------------------------------------------------------------


def test_causal_history_sha256_is_stable_for_the_same_history() -> None:
    history = _history()
    assert causal_history_sha256(history) == causal_history_sha256(history)


def test_causal_history_sha256_changes_when_a_row_changes() -> None:
    changed = (
        _history_row("1", 1, (1, 2, 3, 4, 5, 6), 44),
        _history_row("2", 2, (7, 8, 9, 10, 11, 13), 45),  # last number differs
    )
    assert causal_history_sha256(_history()) != causal_history_sha256(changed)


def test_causal_history_sha256_changes_when_special_number_changes() -> None:
    changed = (
        _history_row("1", 1, (1, 2, 3, 4, 5, 6), 44),
        _history_row("2", 2, (7, 8, 9, 10, 11, 12), 46),  # special differs only
    )
    assert causal_history_sha256(_history()) != causal_history_sha256(changed)


def test_causal_history_sha256_of_empty_history_does_not_crash() -> None:
    assert causal_history_sha256(()) == causal_history_sha256(())


# --------------------------------------------------------------------------
# build_replay_prediction_snapshot / snapshot invariants
# --------------------------------------------------------------------------


def test_ok_snapshot_carries_history_and_prediction_fields() -> None:
    snapshot = _ok_snapshot()
    assert snapshot.history_status == "OK"
    assert snapshot.history_reason_code is None
    assert snapshot.causal_history_count == 2
    assert snapshot.causal_history_sha256 == causal_history_sha256(_history())
    assert snapshot.prediction_status == "OK"
    assert snapshot.predicted_main_numbers == (1, 2, 3, 4, 5, 6)
    assert snapshot.strategy_version == "v1"
    assert snapshot.adapter_strategy_id == _STRATEGY_ID
    assert snapshot.source_mode.value == "TARGET_NATIVE"
    assert snapshot.cutoff_draw_number == _history()[-1].draw_number
    assert snapshot.cutoff_draw_date == _history()[-1].draw_date
    assert snapshot.cutoff_draw_number != snapshot.target_draw_number
    assert snapshot.cutoff_draw_date != snapshot.target_draw_date


def test_ok_snapshot_with_empty_history_has_no_cutoff() -> None:
    snapshot = _ok_snapshot(history=())
    assert snapshot.history_status == "OK"
    assert snapshot.causal_history_count == 0
    assert snapshot.causal_history_sha256 == causal_history_sha256(())
    assert snapshot.cutoff_draw_number is None
    assert snapshot.cutoff_draw_date is None
    assert snapshot.prediction_status == "OK"
    assert snapshot.predicted_main_numbers == (1, 2, 3, 4, 5, 6)


def test_failure_snapshot_has_no_prediction_or_history_payload() -> None:
    snapshot = _failure_snapshot()
    assert snapshot.history_status == "TARGET_NOT_FOUND"
    assert snapshot.history_reason_code == "TARGET_DRAW_NOT_FOUND"
    assert snapshot.causal_history_count is None
    assert snapshot.causal_history_sha256 is None
    assert snapshot.cutoff_draw_number is None
    assert snapshot.cutoff_draw_date is None
    assert snapshot.prediction_status is None
    assert snapshot.prediction_reason_code is None
    assert snapshot.predicted_main_numbers is None
    assert snapshot.strategy_version is None
    assert snapshot.adapter_strategy_id is None


# --------------------------------------------------------------------------
# Cutoff invariants
# --------------------------------------------------------------------------


def _snapshot(
    *,
    cutoff_draw_number: str | None,
    cutoff_draw_date: date | None,
    history_status: str,
    history_reason_code: str | None,
    causal_history_count: int | None,
    causal_history_sha256_value: str | None,
) -> ReplayPredictionSnapshot:
    return ReplayPredictionSnapshot(
        snapshot_schema_version="1.0.0",
        dataset_id="DS1",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        source_mode=ReplaySourceMode.TARGET_NATIVE,
        target_draw_number="999",
        target_draw_date=date(2020, 1, 3),
        cutoff_draw_number=cutoff_draw_number,
        cutoff_draw_date=cutoff_draw_date,
        strategy_id=_STRATEGY_ID,
        strategy_version=None,
        adapter_strategy_id=None,
        adapter_strategy_name=None,
        adapter_strategy_version=None,
        history_status=history_status,
        history_reason_code=history_reason_code,
        causal_history_count=causal_history_count,
        causal_history_sha256=causal_history_sha256_value,
        prediction_status=None,
        prediction_reason_code=None,
        predicted_main_numbers=None,
        result_sha256="0" * 64,
    )


def test_partial_cutoff_population_is_rejected() -> None:
    with pytest.raises(ValueError, match="cutoff_draw_number and cutoff_draw_date"):
        _snapshot(
            cutoff_draw_number="1",
            cutoff_draw_date=None,
            history_status="OK",
            history_reason_code=None,
            causal_history_count=1,
            causal_history_sha256_value="a" * 64,
        )


def test_ok_with_positive_count_and_no_cutoff_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires a cutoff"):
        _snapshot(
            cutoff_draw_number=None,
            cutoff_draw_date=None,
            history_status="OK",
            history_reason_code=None,
            causal_history_count=1,
            causal_history_sha256_value="a" * 64,
        )


def test_ok_with_zero_count_and_a_cutoff_is_rejected() -> None:
    with pytest.raises(ValueError, match="zero causal history must not carry a cutoff"):
        _snapshot(
            cutoff_draw_number="1",
            cutoff_draw_date=date(2020, 1, 1),
            history_status="OK",
            history_reason_code=None,
            causal_history_count=0,
            causal_history_sha256_value=causal_history_sha256(()),
        )


def test_non_ok_with_cutoff_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-OK history_status must not carry a cutoff"):
        _snapshot(
            cutoff_draw_number="1",
            cutoff_draw_date=date(2020, 1, 1),
            history_status="TARGET_NOT_FOUND",
            history_reason_code="TARGET_DRAW_NOT_FOUND",
            causal_history_count=None,
            causal_history_sha256_value=None,
        )


def test_cutoff_on_or_after_target_is_rejected() -> None:
    with pytest.raises(ValueError, match="strictly before the target"):
        _snapshot(
            cutoff_draw_number="999",
            cutoff_draw_date=date(2020, 1, 3),
            history_status="OK",
            history_reason_code=None,
            causal_history_count=1,
            causal_history_sha256_value="a" * 64,
        )


def test_snapshot_result_sha256_is_stable_for_identical_construction() -> None:
    assert _ok_snapshot().result_sha256 == _ok_snapshot().result_sha256


def test_snapshot_result_sha256_changes_when_prediction_changes() -> None:
    base = _ok_snapshot(main_numbers=(1, 2, 3, 4, 5, 6))
    other = _ok_snapshot(main_numbers=(10, 20, 30, 40, 41, 42))
    assert base.result_sha256 != other.result_sha256


def test_snapshot_result_sha256_changes_when_history_changes() -> None:
    other_history = (_history_row("1", 1, (1, 2, 3, 4, 5, 6), 44),)  # one row instead of two
    base = _ok_snapshot()
    other = _ok_snapshot(history=other_history)
    assert base.result_sha256 != other.result_sha256
    assert base.causal_history_sha256 != other.causal_history_sha256


def test_recompute_snapshot_result_sha256_matches_the_declared_hash() -> None:
    snapshot = _ok_snapshot()
    assert recompute_snapshot_result_sha256(snapshot) == snapshot.result_sha256


def test_recompute_snapshot_result_sha256_detects_a_forged_field() -> None:
    import dataclasses

    snapshot = _ok_snapshot()
    forged = dataclasses.replace(snapshot, predicted_main_numbers=(9, 9, 9, 9, 9, 9))
    assert recompute_snapshot_result_sha256(forged) != forged.result_sha256


# --------------------------------------------------------------------------
# ReplayArtifact construction invariants
# --------------------------------------------------------------------------


def test_build_replay_artifact_computes_a_stable_payload_sha256() -> None:
    artifact = build_replay_artifact(
        dataset_id="DS1",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=(_STRATEGY_ID,),
        targets=(_target(),),
        snapshots=(_ok_snapshot(),),
    )
    again = build_replay_artifact(
        dataset_id="DS1",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=(_STRATEGY_ID,),
        targets=(_target(),),
        snapshots=(_ok_snapshot(),),
    )
    assert artifact.payload_sha256 == again.payload_sha256
    assert artifact.snapshot_count == 1
    assert recompute_artifact_payload_sha256(artifact) == artifact.payload_sha256


def test_artifact_rejects_snapshot_count_mismatch() -> None:
    with pytest.raises(ValueError, match="snapshot_count"):
        ReplayArtifact(
            artifact_schema_version="1.0.0",
            dataset_id="DS1",
            dataset_version="1",
            lottery_type=LotteryType.BIG_LOTTO,
            strategy_ids=(_STRATEGY_ID,),
            targets=(_target(),),
            snapshots=(_ok_snapshot(), _ok_snapshot()),
            snapshot_count=1,
            payload_sha256="0" * 64,
        )


def test_artifact_rejects_duplicate_strategy_ids() -> None:
    with pytest.raises(ValueError, match="strategy_ids"):
        build_replay_artifact(
            dataset_id="DS1",
            dataset_version="1",
            lottery_type=LotteryType.BIG_LOTTO,
            strategy_ids=(_STRATEGY_ID, _STRATEGY_ID),
            targets=(_target(),),
            snapshots=(_ok_snapshot(), _ok_snapshot()),
        )


def test_artifact_rejects_duplicate_target_draw_numbers() -> None:
    with pytest.raises(ValueError, match="targets"):
        build_replay_artifact(
            dataset_id="DS1",
            dataset_version="1",
            lottery_type=LotteryType.BIG_LOTTO,
            strategy_ids=(_STRATEGY_ID,),
            targets=(_target(), _target()),
            snapshots=(_ok_snapshot(), _ok_snapshot()),
        )


# --------------------------------------------------------------------------
# Serialize / deserialize: byte stability, round trip, tamper detection
# --------------------------------------------------------------------------


def _artifact() -> ReplayArtifact:
    return build_replay_artifact(
        dataset_id="DS1",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=(_STRATEGY_ID,),
        targets=(_target(),),
        snapshots=(_ok_snapshot(),),
    )


def test_serialize_replay_artifact_is_byte_identical_across_calls() -> None:
    artifact = _artifact()
    assert serialize_replay_artifact(artifact) == serialize_replay_artifact(artifact)


def test_serialize_replay_artifact_has_no_null_bytes_or_timestamps() -> None:
    data = serialize_replay_artifact(_artifact())
    assert b"null" not in data
    assert b"produced_at" not in data
    assert b"timestamp" not in data


def test_round_trip_deserialize_equals_original_artifact() -> None:
    artifact = _artifact()
    restored = deserialize_replay_artifact(serialize_replay_artifact(artifact))
    assert restored == artifact


def test_round_trip_preserves_a_failure_snapshot_exactly() -> None:
    artifact = build_replay_artifact(
        dataset_id="DS1",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=("unknown_strategy",),
        targets=(_target(),),
        snapshots=(_failure_snapshot(),),
    )
    restored = deserialize_replay_artifact(serialize_replay_artifact(artifact))
    assert restored == artifact
    assert restored.snapshots[0].prediction_status is None


def _empty_history_artifact() -> ReplayArtifact:
    return build_replay_artifact(
        dataset_id="DS1",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=(_STRATEGY_ID,),
        targets=(_target(),),
        snapshots=(_ok_snapshot(history=()),),
    )


def test_serialize_omits_cutoff_keys_when_history_is_empty() -> None:
    data = serialize_replay_artifact(_empty_history_artifact())
    assert b"cutoff_draw_number" not in data
    assert b"cutoff_draw_date" not in data
    assert b"null" not in data


def test_round_trip_preserves_an_empty_history_ok_snapshot_exactly() -> None:
    artifact = _empty_history_artifact()
    restored = deserialize_replay_artifact(serialize_replay_artifact(artifact))
    assert restored == artifact
    assert restored.snapshots[0].cutoff_draw_number is None
    assert restored.snapshots[0].cutoff_draw_date is None


def test_deserialize_detects_tampering_in_a_present_cutoff_field() -> None:
    data = serialize_replay_artifact(_artifact())
    tampered = data.replace(b'"cutoff_draw_number":"2"', b'"cutoff_draw_number":"1"')
    assert tampered != data
    with pytest.raises(ReplayArtifactTamperError):
        deserialize_replay_artifact(tampered)


def test_deserialize_detects_tampering_in_a_string_field() -> None:
    data = serialize_replay_artifact(_artifact())
    tampered = data.replace(b'"dataset_id":"DS1"', b'"dataset_id":"DS2"')
    assert tampered != data
    with pytest.raises(ReplayArtifactTamperError):
        deserialize_replay_artifact(tampered)


def test_deserialize_detects_tampering_in_a_nested_snapshot_field() -> None:
    data = serialize_replay_artifact(_artifact())
    tampered = data.replace(
        b'"predicted_main_numbers":[1,2,3,4,5,6]',
        b'"predicted_main_numbers":[7,8,9,10,11,12]',
    )
    assert tampered != data
    with pytest.raises(ReplayArtifactTamperError):
        deserialize_replay_artifact(tampered)


def test_deserialize_rejects_a_payload_missing_required_keys() -> None:
    with pytest.raises(ReplayArtifactShapeError):
        deserialize_replay_artifact(b'{"artifact_schema_version":"1.0.0"}')


def test_deserialize_rejects_a_non_object_payload() -> None:
    with pytest.raises(ReplayArtifactShapeError):
        deserialize_replay_artifact(b"[1,2,3]")
