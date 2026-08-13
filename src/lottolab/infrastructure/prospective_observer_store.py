"""Durable create-once filesystem storage for prospective observations.

The final record name is installed with an atomic hard-link operation only
after a same-directory temporary file has been completely written and fsynced.
An interrupted writer can therefore leave either an ignored temporary file or
a complete accepted record; an already-visible accepted record is never
opened for writing or replaced.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TypeVar, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.prize_evaluation import PrizeEvaluationResult
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    CreateOnceOutcome,
    DiagnosticEvent,
    FrozenCohortRef,
    GameEvaluation,
    MatchedBaselineRef,
    ObservationTarget,
    OfficialOutcome,
    OutcomePresenceAtPrediction,
    PredictionAvailability,
    PredictionEntry,
    PredictionRecord,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveObservationIdentity,
    ProspectiveSelection,
    ScoreAvailability,
    ScoreEntry,
    ScoreRecord,
    TemporalProvenance,
    classify_temporal_provenance,
)

PROSPECTIVE_OBSERVATION_STORE_SCHEMA_VERSION = (
    "LOTTOLAB_PROSPECTIVE_OBSERVATION_STORE_V1"
)
_MAX_RECORD_BYTES = 16 * 1024 * 1024
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_T = TypeVar("_T")


class ProspectiveObservationStoreCorruptionError(RuntimeError):
    """An accepted record location or its durable authority is invalid."""


class FileSystemProspectiveObservationStore:
    """Caller-rooted, restart-safe implementation of the create-once port."""

    def __init__(self, root: str | Path) -> None:
        if not str(root):
            raise ValueError("root must be a non-empty filesystem path")
        self._root = Path(root).absolute()
        _materialize_directory(self._root)

    @property
    def root(self) -> Path:
        return self._root

    def get_prediction(
        self,
        identity: ProspectiveObservationIdentity,
    ) -> PredictionRecord | None:
        _require_identity(identity)
        path = self._record_path(identity, "prediction")
        return self._read_optional(
            path,
            identity=identity,
            record_type="prediction",
            decoder=_decode_prediction,
        )

    def create_prediction(self, record: PredictionRecord) -> CreateOnceOutcome:
        if type(record) is not PredictionRecord:
            raise ValueError("record must be a PredictionRecord")
        path = self._record_path(record.identity, "prediction")
        payload = _encode_prediction(record)
        return self._create_once(
            path,
            identity=record.identity,
            record_type="prediction",
            payload=payload,
            expected=record,
            decoder=_decode_prediction,
            equal=lambda existing, candidate: (
                existing.prediction_hash == candidate.prediction_hash
                and existing.canonical_material() == candidate.canonical_material()
            ),
        )

    def get_score(self, identity: ProspectiveObservationIdentity) -> ScoreRecord | None:
        _require_identity(identity)
        path = self._record_path(identity, "score")
        score = self._read_optional(
            path,
            identity=identity,
            record_type="score",
            decoder=_decode_score,
        )
        if score is None:
            return None
        self._require_prediction_link(score)
        return score

    def create_score(self, record: ScoreRecord) -> CreateOnceOutcome:
        if type(record) is not ScoreRecord:
            raise ValueError("record must be a ScoreRecord")
        self._require_prediction_link(record)
        path = self._record_path(record.identity, "score")
        payload = _encode_score(record)
        outcome = self._create_once(
            path,
            identity=record.identity,
            record_type="score",
            payload=payload,
            expected=record,
            decoder=_decode_score,
            equal=lambda existing, candidate: (
                existing.score_hash == candidate.score_hash
                and existing.canonical_material() == candidate.canonical_material()
            ),
        )
        if outcome is not CreateOnceOutcome.CONFLICT:
            persisted = self.get_score(record.identity)
            if persisted is None:
                raise ProspectiveObservationStoreCorruptionError(
                    "accepted score disappeared after durable creation"
                )
        return outcome

    def _record_path(
        self,
        identity: ProspectiveObservationIdentity,
        record_type: str,
    ) -> Path:
        _require_identity(identity)
        cohort_key = _digest_segment(
            {
                "cohort_id": identity.cohort_id,
                "cohort_version": identity.cohort_version,
            }
        )
        target_key = _digest_segment(identity.canonical_dict())
        directory = (
            self._root
            / identity.lottery_type.value.lower()
            / f"cohort-{cohort_key}"
            / f"target-{identity.target_draw_date.isoformat()}-{target_key}"
        )
        return directory / f"{record_type}.json"

    def _read_optional(
        self,
        path: Path,
        *,
        identity: ProspectiveObservationIdentity,
        record_type: str,
        decoder: Callable[[Mapping[str, object]], _T],
    ) -> _T | None:
        try:
            encoded = _read_regular_file(path)
        except FileNotFoundError:
            return None
        try:
            envelope = _decode_json_object(encoded)
            _expect_keys(
                envelope,
                {"envelope_sha256", "record", "record_type", "schema_version"},
                "envelope",
            )
            _expect_exact(
                envelope["schema_version"],
                PROSPECTIVE_OBSERVATION_STORE_SCHEMA_VERSION,
                "store schema_version",
            )
            _expect_exact(envelope["record_type"], record_type, "record_type")
            envelope_material = {
                "record": envelope["record"],
                "record_type": envelope["record_type"],
                "schema_version": envelope["schema_version"],
            }
            expected_envelope_hash = hashlib.sha256(
                _canonical_bytes(envelope_material)
            ).hexdigest()
            if (
                _string(envelope["envelope_sha256"], "envelope_sha256")
                != expected_envelope_hash
            ):
                raise ValueError("envelope_sha256 does not match the complete stored record")
            record = decoder(_object(envelope["record"], "record"))
            if record.identity != identity:  # type: ignore[attr-defined]
                raise ValueError("record identity does not match its storage key")
            return record
        except ProspectiveObservationStoreCorruptionError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ProspectiveObservationStoreCorruptionError(
                f"corrupt {record_type} record at {path}: {exc}"
            ) from exc

    def _create_once(
        self,
        path: Path,
        *,
        identity: ProspectiveObservationIdentity,
        record_type: str,
        payload: bytes,
        expected: _T,
        decoder: Callable[[Mapping[str, object]], _T],
        equal: Callable[[_T, _T], bool],
    ) -> CreateOnceOutcome:
        _materialize_directory(path.parent)
        temporary = path.parent / f".{record_type}-{secrets.token_hex(16)}.tmp"
        descriptor = -1
        installed = False
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
                0o600,
            )
            _write_all(descriptor, payload)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            try:
                os.link(temporary, path, follow_symlinks=False)
                installed = True
                _fsync_directory(path.parent)
            except FileExistsError:
                # The competing writer linked only fully written, fsynced bytes.
                # Fsyncing here also makes that directory entry durable before
                # this create call can report an idempotent success.
                _fsync_directory(path.parent)
        except OSError as exc:
            raise ProspectiveObservationStoreCorruptionError(
                f"cannot durably create {record_type} record at {path}: {exc}"
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise ProspectiveObservationStoreCorruptionError(
                    f"cannot remove completed temporary record {temporary}: {exc}"
                ) from exc
            else:
                _fsync_directory(path.parent)

        if installed:
            persisted = self._read_optional(
                path,
                identity=identity,
                record_type=record_type,
                decoder=decoder,
            )
            if persisted is None or not equal(persisted, expected):
                raise ProspectiveObservationStoreCorruptionError(
                    f"newly created {record_type} record failed exact read-after-write"
                )
            return CreateOnceOutcome.INSERTED

        existing = self._read_optional(
            path,
            identity=identity,
            record_type=record_type,
            decoder=decoder,
        )
        if existing is None:
            raise ProspectiveObservationStoreCorruptionError(
                f"competing {record_type} record disappeared"
            )
        return (
            CreateOnceOutcome.ALREADY_PRESENT
            if equal(existing, expected)
            else CreateOnceOutcome.CONFLICT
        )

    def _require_prediction_link(self, score: ScoreRecord) -> PredictionRecord:
        prediction = self.get_prediction(score.identity)
        if prediction is None:
            raise ProspectiveObservationStoreCorruptionError(
                "score requires an existing immutable prediction"
            )
        if score.prediction_hash != prediction.prediction_hash:
            raise ProspectiveObservationStoreCorruptionError(
                "score prediction link does not match immutable prediction"
            )
        prediction_entries = {entry.member_id: entry for entry in prediction.entries}
        if tuple(entry.member_id for entry in score.entries) != tuple(prediction_entries):
            raise ProspectiveObservationStoreCorruptionError(
                "score membership does not match immutable prediction"
            )
        if any(
            entry.prediction_hash != prediction_entries[entry.member_id].prediction_hash
            for entry in score.entries
        ):
            raise ProspectiveObservationStoreCorruptionError(
                "score entry link does not match immutable prediction"
            )
        for score_entry in score.entries:
            prediction_entry = prediction_entries[score_entry.member_id]
            if prediction_entry.availability is PredictionAvailability.UNAVAILABLE:
                if score_entry.availability is not ScoreAvailability.UNAVAILABLE_PREDICTION:
                    raise ProspectiveObservationStoreCorruptionError(
                        "unavailable prediction has an incompatible score state"
                    )
                continue
            if (
                score_entry.availability is not ScoreAvailability.SCORED
                or score_entry.evaluation is None
                or score_entry.evaluation.lottery_type is not score.identity.lottery_type
            ):
                raise ProspectiveObservationStoreCorruptionError(
                    "available prediction has an incompatible score evaluation"
                )
        return prediction


def _materialize_directory(path: Path) -> None:
    missing: list[Path] = []
    current = path
    while True:
        try:
            metadata = current.lstat()
        except FileNotFoundError as exc:
            missing.append(current)
            if current.parent == current:
                raise ProspectiveObservationStoreCorruptionError(
                    f"cannot resolve storage directory authority: {path}"
                ) from exc
            current = current.parent
            continue
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ProspectiveObservationStoreCorruptionError(
                f"storage path is not a real directory: {current}"
            )
        break
    for directory in reversed(missing):
        with suppress(FileExistsError):
            directory.mkdir(mode=0o700)
        metadata = directory.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ProspectiveObservationStoreCorruptionError(
                f"storage path is not a real directory: {directory}"
            )
        _fsync_directory(directory.parent)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | _CLOEXEC)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise ProspectiveObservationStoreCorruptionError(
                f"storage path is not a directory: {path}"
            )
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("record write made no progress")
        remaining = remaining[written:]


def _read_regular_file(path: Path) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | _NOFOLLOW | _CLOEXEC)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise ProspectiveObservationStoreCorruptionError(
            f"cannot open accepted record {path}: {exc}"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ProspectiveObservationStoreCorruptionError(
                f"accepted record is not a regular file: {path}"
            )
        if metadata.st_size > _MAX_RECORD_BYTES:
            raise ProspectiveObservationStoreCorruptionError(
                f"accepted record exceeds the bounded size limit: {path}"
            )
        chunks: list[bytes] = []
        remaining = _MAX_RECORD_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        encoded = b"".join(chunks)
        if len(encoded) > _MAX_RECORD_BYTES:
            raise ProspectiveObservationStoreCorruptionError(
                f"accepted record exceeds the bounded size limit: {path}"
            )
        return encoded
    finally:
        os.close(descriptor)


def _canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _digest_segment(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()[:32]


def _envelope(record_type: str, record: Mapping[str, object]) -> bytes:
    material = {
        "record": record,
        "record_type": record_type,
        "schema_version": PROSPECTIVE_OBSERVATION_STORE_SCHEMA_VERSION,
    }
    return _canonical_bytes(
        {
            **material,
            "envelope_sha256": hashlib.sha256(_canonical_bytes(material)).hexdigest(),
        }
    )


def _encode_prediction(record: PredictionRecord) -> bytes:
    return _envelope(
        "prediction",
        {
            **record.canonical_material(),
            "predicted_at": _datetime_text(record.predicted_at),
            "prediction_hash": record.prediction_hash,
        },
    )


def _encode_score(record: ScoreRecord) -> bytes:
    return _envelope(
        "score",
        {
            **record.canonical_material(),
            "scored_at": _datetime_text(record.scored_at),
            "score_hash": record.score_hash,
        },
    )


def _decode_json_object(encoded: bytes) -> Mapping[str, object]:
    def pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    try:
        decoded = json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=pairs_hook,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"invalid JSON constant: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ProspectiveObservationStoreCorruptionError(
            f"accepted record contains malformed JSON: {exc}"
        ) from exc
    return _object(decoded, "envelope")


def _decode_prediction(value: Mapping[str, object]) -> PredictionRecord:
    _expect_keys(
        value,
        {
            "causal_history",
            "cohort",
            "entries",
            "identity",
            "outcome_presence_at_start",
            "predicted_at",
            "prediction_hash",
            "producer_fingerprint",
            "schema_version",
            "temporal_provenance",
        },
        "prediction",
    )
    record = PredictionRecord(
        schema_version=_string(value["schema_version"], "prediction.schema_version"),
        identity=_decode_identity(_object(value["identity"], "prediction.identity")),
        cohort=_decode_cohort(_object(value["cohort"], "prediction.cohort")),
        producer_fingerprint=_decode_fingerprint(
            _object(value["producer_fingerprint"], "prediction.producer_fingerprint")
        ),
        causal_history=_decode_history(
            _object(value["causal_history"], "prediction.causal_history")
        ),
        outcome_presence_at_start=OutcomePresenceAtPrediction(
            _string(
                value["outcome_presence_at_start"],
                "prediction.outcome_presence_at_start",
            )
        ),
        temporal_provenance=TemporalProvenance(
            _string(value["temporal_provenance"], "prediction.temporal_provenance")
        ),
        predicted_at=_datetime(value["predicted_at"], "prediction.predicted_at"),
        entries=tuple(
            _decode_prediction_entry(_object(item, "prediction.entries[]"))
            for item in _array(value["entries"], "prediction.entries")
        ),
        prediction_hash=_string(value["prediction_hash"], "prediction.prediction_hash"),
    )
    record.causal_history.validate_against(
        ObservationTarget(
            lottery_type=record.identity.lottery_type,
            draw_number=record.identity.target_draw_number,
            draw_date=record.identity.target_draw_date,
        )
    )
    expected_provenance = classify_temporal_provenance(
        target_date=record.identity.target_draw_date,
        frozen_at=record.cohort.frozen_at,
        outcome_presence=record.outcome_presence_at_start,
    )
    if record.temporal_provenance is not expected_provenance:
        raise ValueError("prediction temporal provenance does not match its causal inputs")
    return record


def _decode_score(value: Mapping[str, object]) -> ScoreRecord:
    _expect_keys(
        value,
        {
            "entries",
            "identity",
            "outcome",
            "prediction_hash",
            "schema_version",
            "score_hash",
            "scored_at",
        },
        "score",
    )
    return ScoreRecord(
        schema_version=_string(value["schema_version"], "score.schema_version"),
        identity=_decode_identity(_object(value["identity"], "score.identity")),
        prediction_hash=_string(value["prediction_hash"], "score.prediction_hash"),
        outcome=_decode_outcome(_object(value["outcome"], "score.outcome")),
        scored_at=_datetime(value["scored_at"], "score.scored_at"),
        entries=tuple(
            _decode_score_entry(_object(item, "score.entries[]"))
            for item in _array(value["entries"], "score.entries")
        ),
        score_hash=_string(value["score_hash"], "score.score_hash"),
    )


def _decode_identity(value: Mapping[str, object]) -> ProspectiveObservationIdentity:
    _expect_keys(
        value,
        {
            "cohort_id",
            "cohort_version",
            "lottery_type",
            "target_draw_date",
            "target_draw_number",
        },
        "identity",
    )
    return ProspectiveObservationIdentity(
        lottery_type=LotteryType(_string(value["lottery_type"], "identity.lottery_type")),
        cohort_id=_string(value["cohort_id"], "identity.cohort_id"),
        cohort_version=_string(value["cohort_version"], "identity.cohort_version"),
        target_draw_number=_string(
            value["target_draw_number"], "identity.target_draw_number"
        ),
        target_draw_date=_date(value["target_draw_date"], "identity.target_draw_date"),
    )


def _decode_cohort(value: Mapping[str, object]) -> FrozenCohortRef:
    _expect_keys(
        value,
        {
            "authority_sha256",
            "checkpoint_provenance",
            "checkpoint_sizes",
            "cohort_id",
            "cohort_version",
            "frozen_at",
            "lottery_type",
            "member_ids",
        },
        "cohort",
    )
    return FrozenCohortRef(
        lottery_type=LotteryType(_string(value["lottery_type"], "cohort.lottery_type")),
        cohort_id=_string(value["cohort_id"], "cohort.cohort_id"),
        cohort_version=_string(value["cohort_version"], "cohort.cohort_version"),
        authority_sha256=_string(value["authority_sha256"], "cohort.authority_sha256"),
        frozen_at=_datetime(value["frozen_at"], "cohort.frozen_at"),
        member_ids=tuple(
            _string(item, "cohort.member_ids[]")
            for item in _array(value["member_ids"], "cohort.member_ids")
        ),
        checkpoint_sizes=tuple(
            _integer(item, "cohort.checkpoint_sizes[]")
            for item in _array(value["checkpoint_sizes"], "cohort.checkpoint_sizes")
        ),
        checkpoint_provenance=tuple(
            TemporalProvenance(_string(item, "cohort.checkpoint_provenance[]"))
            for item in _array(
                value["checkpoint_provenance"], "cohort.checkpoint_provenance"
            )
        ),
    )


def _decode_fingerprint(value: Mapping[str, object]) -> ProducerFingerprint:
    _expect_keys(
        value,
        {"dependencies", "digest", "producer_id", "producer_version", "schema_version"},
        "producer_fingerprint",
    )
    dependencies = tuple(
        _decode_dependency(_object(item, "producer_fingerprint.dependencies[]"))
        for item in _array(value["dependencies"], "producer_fingerprint.dependencies")
    )
    return ProducerFingerprint(
        schema_version=_string(value["schema_version"], "producer_fingerprint.schema_version"),
        producer_id=_string(value["producer_id"], "producer_fingerprint.producer_id"),
        producer_version=_string(
            value["producer_version"], "producer_fingerprint.producer_version"
        ),
        dependencies=dependencies,
        digest=_string(value["digest"], "producer_fingerprint.digest"),
    )


def _decode_dependency(value: Mapping[str, object]) -> ProducerDependency:
    _expect_keys(value, {"load_bearing_role", "locator", "source_sha256"}, "dependency")
    return ProducerDependency(
        locator=_string(value["locator"], "dependency.locator"),
        source_sha256=_string(value["source_sha256"], "dependency.source_sha256"),
        load_bearing_role=_string(value["load_bearing_role"], "dependency.load_bearing_role"),
    )


def _decode_history(value: Mapping[str, object]) -> CausalHistoryRef:
    _expect_keys(
        value,
        {"draw_count", "history_sha256", "last_draw_date", "last_draw_number"},
        "causal_history",
    )
    last_number = value["last_draw_number"]
    last_date = value["last_draw_date"]
    return CausalHistoryRef(
        draw_count=_integer(value["draw_count"], "causal_history.draw_count"),
        last_draw_number=(
            None if last_number is None else _string(last_number, "causal_history.last_draw_number")
        ),
        last_draw_date=(
            None if last_date is None else _date(last_date, "causal_history.last_draw_date")
        ),
        history_sha256=_string(value["history_sha256"], "causal_history.history_sha256"),
    )


def _decode_prediction_entry(value: Mapping[str, object]) -> PredictionEntry:
    _expect_keys(
        value,
        {
            "availability",
            "matched_baseline",
            "member_id",
            "prediction_hash",
            "selections",
            "unavailable_reason",
        },
        "prediction_entry",
    )
    baseline_value = value["matched_baseline"]
    reason = value["unavailable_reason"]
    return PredictionEntry(
        member_id=_string(value["member_id"], "prediction_entry.member_id"),
        availability=PredictionAvailability(
            _string(value["availability"], "prediction_entry.availability")
        ),
        selections=tuple(
            _decode_selection(_object(item, "prediction_entry.selections[]"))
            for item in _array(value["selections"], "prediction_entry.selections")
        ),
        matched_baseline=(
            None
            if baseline_value is None
            else _decode_baseline(_object(baseline_value, "prediction_entry.matched_baseline"))
        ),
        unavailable_reason=(
            None
            if reason is None
            else _string(reason, "prediction_entry.unavailable_reason")
        ),
        prediction_hash=_string(
            value["prediction_hash"], "prediction_entry.prediction_hash"
        ),
    )


def _decode_selection(value: Mapping[str, object]) -> ProspectiveSelection:
    _expect_keys(value, {"main_numbers", "special_number"}, "selection")
    special = value["special_number"]
    return ProspectiveSelection(
        main_numbers=tuple(
            _integer(item, "selection.main_numbers[]")
            for item in _array(value["main_numbers"], "selection.main_numbers")
        ),
        special_number=(
            None if special is None else _integer(special, "selection.special_number")
        ),
    )


def _decode_baseline(value: Mapping[str, object]) -> MatchedBaselineRef:
    _expect_keys(
        value,
        {
            "authority_sha256",
            "baseline_id",
            "baseline_version",
            "candidate_sizes",
            "lottery_type",
            "ticket_count",
        },
        "matched_baseline",
    )
    return MatchedBaselineRef(
        lottery_type=LotteryType(
            _string(value["lottery_type"], "matched_baseline.lottery_type")
        ),
        baseline_id=_string(value["baseline_id"], "matched_baseline.baseline_id"),
        baseline_version=_string(
            value["baseline_version"], "matched_baseline.baseline_version"
        ),
        authority_sha256=_string(
            value["authority_sha256"], "matched_baseline.authority_sha256"
        ),
        ticket_count=_integer(value["ticket_count"], "matched_baseline.ticket_count"),
        candidate_sizes=tuple(
            _integer(item, "matched_baseline.candidate_sizes[]")
            for item in _array(value["candidate_sizes"], "matched_baseline.candidate_sizes")
        ),
    )


def _decode_outcome(value: Mapping[str, object]) -> OfficialOutcome:
    _expect_keys(
        value,
        {
            "draw_date",
            "draw_number",
            "lottery_type",
            "main_numbers",
            "outcome_hash",
            "schema_version",
            "source_id",
            "source_sha256",
            "special_number",
        },
        "outcome",
    )
    special = value["special_number"]
    return OfficialOutcome(
        schema_version=_string(value["schema_version"], "outcome.schema_version"),
        lottery_type=LotteryType(_string(value["lottery_type"], "outcome.lottery_type")),
        draw_number=_string(value["draw_number"], "outcome.draw_number"),
        draw_date=_date(value["draw_date"], "outcome.draw_date"),
        main_numbers=tuple(
            _integer(item, "outcome.main_numbers[]")
            for item in _array(value["main_numbers"], "outcome.main_numbers")
        ),
        special_number=(
            None if special is None else _integer(special, "outcome.special_number")
        ),
        source_id=_string(value["source_id"], "outcome.source_id"),
        source_sha256=_string(value["source_sha256"], "outcome.source_sha256"),
        outcome_hash=_string(value["outcome_hash"], "outcome.outcome_hash"),
    )


def _decode_score_entry(value: Mapping[str, object]) -> ScoreEntry:
    _expect_keys(
        value,
        {"availability", "evaluation", "member_id", "prediction_hash"},
        "score_entry",
    )
    evaluation = value["evaluation"]
    return ScoreEntry(
        member_id=_string(value["member_id"], "score_entry.member_id"),
        prediction_hash=_string(value["prediction_hash"], "score_entry.prediction_hash"),
        availability=ScoreAvailability(
            _string(value["availability"], "score_entry.availability")
        ),
        evaluation=(
            None
            if evaluation is None
            else _decode_evaluation(_object(evaluation, "score_entry.evaluation"))
        ),
    )


def _decode_evaluation(value: Mapping[str, object]) -> GameEvaluation:
    _expect_keys(
        value,
        {"diagnostic_events", "lottery_type", "ticket_results"},
        "evaluation",
    )
    return GameEvaluation(
        lottery_type=LotteryType(
            _string(value["lottery_type"], "evaluation.lottery_type")
        ),
        ticket_results=tuple(
            _decode_prize_result(_object(item, "evaluation.ticket_results[]"))
            for item in _array(value["ticket_results"], "evaluation.ticket_results")
        ),
        diagnostic_events=tuple(
            _decode_diagnostic(_object(item, "evaluation.diagnostic_events[]"))
            for item in _array(value["diagnostic_events"], "evaluation.diagnostic_events")
        ),
    )


def _decode_prize_result(value: Mapping[str, object]) -> PrizeEvaluationResult:
    _expect_keys(
        value,
        {
            "is_winner",
            "lottery_type",
            "prize_rule_provenance",
            "prize_rule_version",
            "prize_tier",
            "prize_tier_order",
            "zone1_hits",
            "zone2_hit",
        },
        "prize_result",
    )
    tier = value["prize_tier"]
    tier_order = value["prize_tier_order"]
    return PrizeEvaluationResult(
        lottery_type=LotteryType(
            _string(value["lottery_type"], "prize_result.lottery_type")
        ),
        is_winner=_boolean(value["is_winner"], "prize_result.is_winner"),
        prize_tier=None if tier is None else _string(tier, "prize_result.prize_tier"),
        prize_tier_order=(
            None
            if tier_order is None
            else _integer(tier_order, "prize_result.prize_tier_order")
        ),
        zone1_hits=_integer(value["zone1_hits"], "prize_result.zone1_hits"),
        zone2_hit=_boolean(value["zone2_hit"], "prize_result.zone2_hit"),
        prize_rule_version=_string(
            value["prize_rule_version"], "prize_result.prize_rule_version"
        ),
        prize_rule_provenance=_string(
            value["prize_rule_provenance"], "prize_result.prize_rule_provenance"
        ),
    )


def _decode_diagnostic(value: Mapping[str, object]) -> DiagnosticEvent:
    _expect_keys(value, {"name", "occurred"}, "diagnostic_event")
    occurred = value["occurred"]
    return DiagnosticEvent(
        name=_string(value["name"], "diagnostic_event.name"),
        occurred=(
            None if occurred is None else _boolean(occurred, "diagnostic_event.occurred")
        ),
    )


def _expect_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"{label} fields differ; missing={missing}, unknown={unknown}")


def _expect_exact(value: object, expected: str, label: str) -> None:
    if value != expected or type(value) is not str:
        raise ValueError(f"unsupported {label}")


def _object(value: object, label: str) -> Mapping[str, object]:
    if type(value) is not dict:
        raise ValueError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], value)


def _array(value: object, label: str) -> Sequence[object]:
    if type(value) is not list:
        raise ValueError(f"{label} must be a JSON array")
    return cast(Sequence[object], value)


def _string(value: object, label: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{label} must be a string")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an exact integer")
    return value


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{label} must be a boolean")
    return value


def _date(value: object, label: str) -> date:
    text = _string(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{label} must use canonical ISO date text")
    return parsed


def _datetime(value: object, label: str) -> datetime:
    text = _string(value, label)
    if not text.endswith("Z"):
        raise ValueError(f"{label} must use canonical UTC text")
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{label} must use UTC")
    if _datetime_text(parsed) != text:
        raise ValueError(f"{label} must use canonical UTC text")
    return parsed


def _datetime_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _require_identity(value: object) -> None:
    if type(value) is not ProspectiveObservationIdentity:
        raise ValueError("identity must be a ProspectiveObservationIdentity")
