"""Persistence contracts for the create-once pre-outcome target authority."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import re
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Event, get_ident

import pytest

import lottolab.infrastructure.pre_outcome_target_store as store_module
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    CreateOnceOutcome,
    ObservationTarget,
    OutcomePresenceAtPrediction,
)
from lottolab.infrastructure.pre_outcome_target_store import (
    FileSystemPreOutcomeTargetAuthorityStore,
    PreOutcomeTargetAuthorityStoreCorruptionError,
)

_OBSERVED_AT = datetime(2026, 8, 13, 1, tzinfo=UTC)
_ATTESTED_AT = datetime(2026, 8, 13, 2, tzinfo=UTC)
_REGISTERED_AT = datetime(2026, 8, 13, 3, tzinfo=UTC)
_SCHEDULED_AT = datetime(2026, 8, 14, 12, 30, tzinfo=UTC)


def _source(*, digest: str = "1" * 64) -> TargetSourceProvenance:
    return TargetSourceProvenance(
        source_id="official-synthetic-schedule",
        source_version="v1",
        source_locator="fixture://official/schedule/100",
        source_sha256=digest,
        observed_at=_OBSERVED_AT,
    )


def _registration(
    *,
    lottery_type: LotteryType = LotteryType.BIG_LOTTO,
    draw_number: str = "100",
    draw_date: date = date(2026, 8, 14),
    source_digest: str = "1" * 64,
) -> PreOutcomeTargetRegistration:
    target = ObservationTarget(lottery_type, draw_number, draw_date)
    source = _source(digest=source_digest)
    return PreOutcomeTargetRegistration.create(
        announcement=TargetAnnouncement(
            target=target,
            schedule_timezone="Asia/Taipei",
            scheduled_at=_SCHEDULED_AT,
            source=source,
        ),
        absence_attestation=OutcomePresenceAttestation(
            target=target,
            presence=OutcomePresenceAtPrediction.ABSENT,
            attested_at=_ATTESTED_AT,
            source=source,
        ),
        causal_history=CausalHistoryRef(
            draw_count=1,
            last_draw_number="99",
            last_draw_date=date(2026, 8, 13),
            history_sha256="2" * 64,
        ),
        registered_at=_REGISTERED_AT,
    )


def _record_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("registration.json")))


def _canonical_json(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()


def _create_in_process(root: str, record: PreOutcomeTargetRegistration) -> str:
    return FileSystemPreOutcomeTargetAuthorityStore(root).create_registration(record).value


def test_registration_round_trip_is_canonical_and_restart_safe(tmp_path: Path) -> None:
    root = tmp_path / "authority"
    record = _registration()
    first = FileSystemPreOutcomeTargetAuthorityStore(root)

    assert first.get_registration(record.target) is None
    assert first.create_registration(record) is CreateOnceOutcome.INSERTED
    assert first.get_registration(record.target) == record

    restarted = FileSystemPreOutcomeTargetAuthorityStore(root)
    assert restarted.get_registration(record.target) == record
    path = _record_files(root)[0]
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "LOTTOLAB_PRE_OUTCOME_TARGET_AUTHORITY_STORE_V1"
    assert payload["record_type"] == "pre_outcome_target_registration"
    assert path.read_bytes() == _canonical_json(payload)


def test_exact_retry_is_no_op_and_preserves_first_bytes(tmp_path: Path) -> None:
    record = _registration()
    store = FileSystemPreOutcomeTargetAuthorityStore(tmp_path / "authority")
    assert store.create_registration(record) is CreateOnceOutcome.INSERTED
    path = _record_files(store.root)[0]
    before = path.read_bytes()

    assert store.create_registration(record) is CreateOnceOutcome.ALREADY_PRESENT
    assert path.read_bytes() == before


def test_different_canonical_retry_conflicts_without_mutation(tmp_path: Path) -> None:
    first = _registration()
    different = _registration(source_digest="3" * 64)
    store = FileSystemPreOutcomeTargetAuthorityStore(tmp_path / "authority")
    assert store.create_registration(first) is CreateOnceOutcome.INSERTED
    path = _record_files(store.root)[0]
    before = path.read_bytes()

    assert store.create_registration(different) is CreateOnceOutcome.CONFLICT
    assert path.read_bytes() == before
    assert store.get_registration(first.target) == first


def test_logical_keys_are_isolated_and_path_segments_are_derived(tmp_path: Path) -> None:
    root = tmp_path / "authority"
    records = (
        _registration(lottery_type=LotteryType.BIG_LOTTO, draw_number="100"),
        _registration(lottery_type=LotteryType.DAILY_539, draw_number="100"),
        _registration(draw_number="101"),
    )
    store = FileSystemPreOutcomeTargetAuthorityStore(root)
    for record in records:
        assert store.create_registration(record) is CreateOnceOutcome.INSERTED
    assert len(_record_files(root)) == len(records)
    assert all(store.get_registration(record.target) == record for record in records)
    assert all(
        re.fullmatch(r"[.a-z0-9_-]+", part)
        for path in _record_files(root)
        for part in path.relative_to(root).parts
    )


@pytest.mark.parametrize("unsafe_draw_number", ["../100", "100/../../escape", "100\\evil"])
def test_unsafe_draw_number_cannot_reach_store_path_material(
    tmp_path: Path,
    unsafe_draw_number: str,
) -> None:
    root = tmp_path / "authority"
    FileSystemPreOutcomeTargetAuthorityStore(root)

    with pytest.raises(ValueError, match="ASCII decimal digits"):
        _registration(draw_number=unsafe_draw_number)

    assert tuple(root.iterdir()) == ()


@pytest.mark.parametrize(
    "damage",
    [
        "malformed",
        "truncated",
        "duplicate",
        "missing",
        "unknown",
        "schema",
        "envelope_digest",
        "record_missing",
        "record_unknown",
        "record_schema",
        "registration_digest",
        "leading_whitespace",
        "key_order",
        "escaped_slash",
    ],
)
def test_malformed_or_noncanonical_accepted_record_fails_closed(
    tmp_path: Path,
    damage: str,
) -> None:
    record = _registration()
    store = FileSystemPreOutcomeTargetAuthorityStore(tmp_path / damage)
    assert store.create_registration(record) is CreateOnceOutcome.INSERTED
    path = _record_files(store.root)[0]
    if damage == "malformed":
        path.write_bytes(b'{"schema_version":')
    elif damage == "truncated":
        path.write_bytes(path.read_bytes()[:-7])
    elif damage == "duplicate":
        encoded = path.read_text(encoding="utf-8")
        path.write_text(encoded.replace("{", '{"schema_version":"duplicate",', 1))
    elif damage == "leading_whitespace":
        path.write_bytes(b" " + path.read_bytes())
    elif damage == "key_order":
        payload = json.loads(path.read_text(encoding="utf-8"))
        reversed_payload = {key: payload[key] for key in reversed(tuple(payload))}
        path.write_text(
            json.dumps(
                reversed_payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=False,
            )
            + "\n",
            encoding="utf-8",
        )
    elif damage == "escaped_slash":
        path.write_bytes(path.read_bytes().replace(b"fixture://", rb"fixture:\/\/", 1))
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if damage == "missing":
            del payload["record_type"]
        elif damage == "unknown":
            payload["unexpected"] = True
        elif damage == "schema":
            payload["schema_version"] = "UNKNOWN"
        elif damage == "envelope_digest":
            payload["envelope_sha256"] = "0" * 64
        else:
            if damage == "record_missing":
                del payload["record"]["outcome_binding_identity"]
            elif damage == "record_unknown":
                payload["record"]["unexpected"] = True
            elif damage == "record_schema":
                payload["record"]["schema_version"] = "UNKNOWN"
            else:
                payload["record"]["registration_digest"] = "0" * 64
            material = {
                "record": payload["record"],
                "record_type": payload["record_type"],
                "schema_version": payload["schema_version"],
            }
            payload["envelope_sha256"] = hashlib.sha256(_canonical_json(material)).hexdigest()
        path.write_bytes(_canonical_json(payload))
    before = path.read_bytes()

    with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError):
        store.get_registration(record.target)
    with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError):
        store.create_registration(record)
    assert path.read_bytes() == before


def test_record_copied_to_another_logical_key_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "authority"
    first = _registration(draw_number="100")
    second = _registration(draw_number="101")
    store = FileSystemPreOutcomeTargetAuthorityStore(root)
    assert store.create_registration(first) is CreateOnceOutcome.INSERTED
    assert store.create_registration(second) is CreateOnceOutcome.INSERTED
    first_path, second_path = _record_files(root)
    first_payload = json.loads(first_path.read_text(encoding="utf-8"))
    if first_payload["record"]["announcement"]["target"]["draw_number"] != "100":
        first_path, second_path = second_path, first_path
    second_path.write_bytes(first_path.read_bytes())

    assert store.get_registration(first.target) == first
    with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError, match="storage key"):
        store.get_registration(second.target)


def test_equal_concurrent_writers_install_exactly_one_value(tmp_path: Path) -> None:
    root = tmp_path / "authority"
    record = _registration()
    records = [record] * 8
    with ProcessPoolExecutor(
        max_workers=8,
        mp_context=multiprocessing.get_context("fork"),
    ) as executor:
        outcomes = tuple(executor.map(_create_in_process, [str(root)] * 8, records))

    assert outcomes.count(CreateOnceOutcome.INSERTED.value) == 1
    assert outcomes.count(CreateOnceOutcome.ALREADY_PRESENT.value) == 7
    assert FileSystemPreOutcomeTargetAuthorityStore(root).get_registration(record.target) == record


def test_equal_writer_accepts_winner_temporary_link_cleanup_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "authority"
    record = _registration()
    winner_store = FileSystemPreOutcomeTargetAuthorityStore(root)
    loser_store = FileSystemPreOutcomeTargetAuthorityStore(root)
    winner_linked = Event()
    allow_winner_cleanup = Event()
    winner_cleaned = Event()
    winner_thread_id = -1
    loser_thread_id = -1
    original_remove = (
        FileSystemPreOutcomeTargetAuthorityStore._remove_owned_temporary  # pyright: ignore[reportPrivateUsage]
    )
    original_listdir = os.listdir

    def delayed_remove(
        target_fd: int,
        temporary_name: str,
        descriptor: int,
    ) -> None:
        if get_ident() == winner_thread_id:
            winner_linked.set()
            assert allow_winner_cleanup.wait(timeout=5)
            original_remove(target_fd, temporary_name, descriptor)
            winner_cleaned.set()
            return
        original_remove(target_fd, temporary_name, descriptor)

    def list_after_winner_cleanup(path: int) -> list[str]:
        if get_ident() == loser_thread_id:
            allow_winner_cleanup.set()
            assert winner_cleaned.wait(timeout=5)
        return original_listdir(path)

    monkeypatch.setattr(
        FileSystemPreOutcomeTargetAuthorityStore,
        "_remove_owned_temporary",
        staticmethod(delayed_remove),
    )
    monkeypatch.setattr(store_module.os, "listdir", list_after_winner_cleanup)

    def create_as_winner() -> CreateOnceOutcome:
        nonlocal winner_thread_id
        winner_thread_id = get_ident()
        return winner_store.create_registration(record)

    def create_as_loser() -> CreateOnceOutcome:
        nonlocal loser_thread_id
        loser_thread_id = get_ident()
        return loser_store.create_registration(record)

    with ThreadPoolExecutor(max_workers=2) as executor:
        winner = executor.submit(create_as_winner)
        assert winner_linked.wait(timeout=5)
        loser = executor.submit(create_as_loser)
        outcomes = (winner.result(timeout=5), loser.result(timeout=5))

    assert outcomes == (
        CreateOnceOutcome.INSERTED,
        CreateOnceOutcome.ALREADY_PRESENT,
    )
    assert FileSystemPreOutcomeTargetAuthorityStore(root).get_registration(record.target) == record


def test_conflicting_concurrent_writers_preserve_one_canonical_value(
    tmp_path: Path,
) -> None:
    root = tmp_path / "authority"
    first = _registration(source_digest="3" * 64)
    second = _registration(source_digest="4" * 64)
    records = [first, second] * 4
    with ProcessPoolExecutor(
        max_workers=8,
        mp_context=multiprocessing.get_context("fork"),
    ) as executor:
        outcomes = tuple(executor.map(_create_in_process, [str(root)] * 8, records))

    assert outcomes.count(CreateOnceOutcome.INSERTED.value) == 1
    persisted = FileSystemPreOutcomeTargetAuthorityStore(root).get_registration(first.target)
    assert persisted in {first, second}
    assert persisted is not None
    for record, outcome in zip(records, outcomes, strict=True):
        if record == persisted:
            assert outcome in {
                CreateOnceOutcome.INSERTED.value,
                CreateOnceOutcome.ALREADY_PRESENT.value,
            }
        else:
            assert outcome == CreateOnceOutcome.CONFLICT.value


def test_symlink_root_and_intermediate_component_are_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root_link = tmp_path / "root-link"
    root_link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError, match="real directory"):
        FileSystemPreOutcomeTargetAuthorityStore(root_link)

    root = tmp_path / "authority"
    store = FileSystemPreOutcomeTargetAuthorityStore(root)
    record = _registration()
    lottery_path = root / record.target.lottery_type.value.lower()
    lottery_path.symlink_to(outside, target_is_directory=True)
    with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError, match="real directory"):
        store.create_registration(record)
    assert tuple(outside.iterdir()) == ()


def test_symlink_accepted_record_is_rejected_without_following(tmp_path: Path) -> None:
    root = tmp_path / "authority"
    record = _registration()
    store = FileSystemPreOutcomeTargetAuthorityStore(root)
    assert store.create_registration(record) is CreateOnceOutcome.INSERTED
    path = _record_files(root)[0]
    external = tmp_path / "external.json"
    external.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(external)

    with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError):
        store.get_registration(record.target)
    assert external.is_file()


def test_intermediate_directory_replaced_by_symlink_is_rejected_on_read(
    tmp_path: Path,
) -> None:
    root = tmp_path / "authority"
    record = _registration()
    store = FileSystemPreOutcomeTargetAuthorityStore(root)
    assert store.create_registration(record) is CreateOnceOutcome.INSERTED
    accepted = _record_files(root)[0]
    lottery_directory = accepted.parents[1]
    moved = tmp_path / "moved-lottery-directory"
    lottery_directory.rename(moved)
    lottery_directory.symlink_to(moved, target_is_directory=True)

    with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError, match="real directory"):
        store.get_registration(record.target)


def test_intermediate_component_replaced_after_startup_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "authority"
    record = _registration()
    store = FileSystemPreOutcomeTargetAuthorityStore(root)
    assert store.create_registration(record) is CreateOnceOutcome.INSERTED
    lottery_path = root / record.target.lottery_type.value.lower()
    moved = tmp_path / "moved-lottery-authority"
    lottery_path.rename(moved)
    lottery_path.symlink_to(moved, target_is_directory=True)

    with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError, match="real directory"):
        store.get_registration(record.target)
    with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError, match="real directory"):
        store.create_registration(record)


def test_non_directory_root_and_empty_root_are_rejected(tmp_path: Path) -> None:
    root_file = tmp_path / "root-file"
    root_file.write_text("not a directory", encoding="utf-8")
    with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError, match="real directory"):
        FileSystemPreOutcomeTargetAuthorityStore(root_file)
    with pytest.raises(ValueError, match="non-empty"):
        FileSystemPreOutcomeTargetAuthorityStore("")


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes are required")
def test_record_permissions_are_owner_only(tmp_path: Path) -> None:
    record = _registration()
    store = FileSystemPreOutcomeTargetAuthorityStore(tmp_path / "authority")
    assert store.create_registration(record) is CreateOnceOutcome.INSERTED
    assert _record_files(store.root)[0].stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("damage", ["mode", "extra_link"])
def test_accepted_record_metadata_tampering_fails_closed(
    tmp_path: Path,
    damage: str,
) -> None:
    record = _registration()
    store = FileSystemPreOutcomeTargetAuthorityStore(tmp_path / damage)
    assert store.create_registration(record) is CreateOnceOutcome.INSERTED
    path = _record_files(store.root)[0]
    if damage == "mode":
        path.chmod(0o640)
    else:
        os.link(path, tmp_path / "unauthorized-extra-link.json")

    with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError):
        store.get_registration(record.target)


def test_restart_accepts_complete_record_with_crash_orphan_temporary_link(
    tmp_path: Path,
) -> None:
    root = tmp_path / "authority"
    record = _registration()
    store = FileSystemPreOutcomeTargetAuthorityStore(root)
    assert store.create_registration(record) is CreateOnceOutcome.INSERTED
    path = _record_files(root)[0]
    orphan = path.parent / f".registration-{'a' * 32}.tmp"
    os.link(path, orphan)

    restarted = FileSystemPreOutcomeTargetAuthorityStore(root)
    assert restarted.get_registration(record.target) == record
    assert restarted.create_registration(record) is CreateOnceOutcome.ALREADY_PRESENT


def test_oversized_candidate_is_rejected_before_key_materialization(tmp_path: Path) -> None:
    root = tmp_path / "authority"
    store = FileSystemPreOutcomeTargetAuthorityStore(root)
    ordinary = _registration()
    oversized_source = replace(
        ordinary.announcement.source,
        source_locator="fixture://oversized/" + "x" * (2 * 1024 * 1024),
    )
    oversized = PreOutcomeTargetRegistration.create(
        announcement=replace(ordinary.announcement, source=oversized_source),
        absence_attestation=ordinary.absence_attestation,
        causal_history=ordinary.causal_history,
        registered_at=ordinary.registered_at,
    )

    with pytest.raises(
        PreOutcomeTargetAuthorityStoreCorruptionError,
        match="bounded size limit",
    ):
        store.create_registration(oversized)

    assert tuple(root.iterdir()) == ()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO fault injection requires POSIX")
def test_fifo_at_accepted_path_fails_closed_without_blocking(tmp_path: Path) -> None:
    record = _registration()
    store = FileSystemPreOutcomeTargetAuthorityStore(tmp_path / "authority")
    assert store.create_registration(record) is CreateOnceOutcome.INSERTED
    path = _record_files(store.root)[0]
    path.unlink()
    os.mkfifo(path, 0o600)

    with pytest.raises(
        PreOutcomeTargetAuthorityStoreCorruptionError,
        match="not a regular file",
    ):
        store.get_registration(record.target)


def test_temporary_name_collision_retries_without_removing_sentinel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = _registration(source_digest="3" * 64)
    competing = _registration(source_digest="4" * 64)
    store = FileSystemPreOutcomeTargetAuthorityStore(tmp_path / "authority")
    assert store.create_registration(existing) is CreateOnceOutcome.INSERTED
    record_directory = _record_files(store.root)[0].parent
    sentinel = record_directory / ".registration-collision.tmp"
    sentinel.write_text("not owned by this create attempt", encoding="utf-8")
    tokens = iter(("collision", "fresh"))

    def fake_token_hex(nbytes: int | None = None) -> str:
        del nbytes
        return next(tokens)

    monkeypatch.setattr(store_module.secrets, "token_hex", fake_token_hex)

    assert store.create_registration(competing) is CreateOnceOutcome.CONFLICT
    assert sentinel.read_text(encoding="utf-8") == "not owned by this create attempt"
    assert (
        tuple(
            path.name
            for path in record_directory.iterdir()
            if path.name.startswith(".registration-") and path != sentinel
        )
        == ()
    )


@pytest.mark.parametrize("swap_level", ["root", "intermediate"])
def test_synchronized_path_swap_cannot_redirect_accepted_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swap_level: str,
) -> None:
    safe_root = tmp_path / "safe-authority"
    outside_root = tmp_path / "outside-authority"
    safe_record = _registration(source_digest="3" * 64)
    outside_record = _registration(source_digest="4" * 64)
    safe_store = FileSystemPreOutcomeTargetAuthorityStore(safe_root)
    outside_store = FileSystemPreOutcomeTargetAuthorityStore(outside_root)
    assert safe_store.create_registration(safe_record) is CreateOnceOutcome.INSERTED
    assert outside_store.create_registration(outside_record) is CreateOnceOutcome.INSERTED

    if swap_level == "root":
        swapped_path = safe_root
        outside_path = outside_root
    else:
        lottery_key = safe_record.target.lottery_type.value.lower()
        swapped_path = safe_root / lottery_key
        outside_path = outside_root / lottery_key
    moved_path = tmp_path / f"moved-read-{swap_level}"
    real_open = os.open
    swapped = False

    def racing_open(
        path: str | bytes,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if path == "registration.json" and dir_fd is not None and not swapped:
            swapped_path.rename(moved_path)
            swapped_path.symlink_to(outside_path, target_is_directory=True)
            swapped = True
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(store_module.os, "open", racing_open)
    try:
        with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError):
            safe_store.get_registration(safe_record.target)
        assert swapped
    finally:
        if swapped_path.is_symlink():
            swapped_path.unlink()
            moved_path.rename(swapped_path)

    assert outside_store.get_registration(outside_record.target) == outside_record


@pytest.mark.parametrize("swap_level", ["root", "intermediate"])
def test_synchronized_path_swap_cannot_redirect_atomic_create(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swap_level: str,
) -> None:
    safe_root = tmp_path / "safe-authority"
    outside_root = tmp_path / "outside-authority"
    safe_record = _registration(source_digest="3" * 64)
    outside_record = _registration(source_digest="4" * 64)
    safe_store = FileSystemPreOutcomeTargetAuthorityStore(safe_root)
    outside_store = FileSystemPreOutcomeTargetAuthorityStore(outside_root)
    assert outside_store.create_registration(outside_record) is CreateOnceOutcome.INSERTED

    if swap_level == "root":
        swapped_path = safe_root
        outside_path = outside_root
    else:
        lottery_key = safe_record.target.lottery_type.value.lower()
        swapped_path = safe_root / lottery_key
        outside_path = outside_root / lottery_key
    moved_path = tmp_path / f"moved-create-{swap_level}"
    real_open = os.open
    swapped = False

    def racing_open(
        path: str | bytes,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if (
            isinstance(path, str)
            and path.startswith(".registration-")
            and flags & os.O_CREAT
            and dir_fd is not None
            and not swapped
        ):
            swapped_path.rename(moved_path)
            swapped_path.symlink_to(outside_path, target_is_directory=True)
            swapped = True
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(store_module.os, "open", racing_open)
    try:
        with pytest.raises(PreOutcomeTargetAuthorityStoreCorruptionError):
            safe_store.create_registration(safe_record)
        assert swapped
    finally:
        if swapped_path.is_symlink():
            swapped_path.unlink()
            moved_path.rename(swapped_path)

    assert safe_store.get_registration(safe_record.target) is None
    assert outside_store.get_registration(outside_record.target) == outside_record
