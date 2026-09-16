"""Safety checks for the no-overwrite canonical forecast writer."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from lottolab.infrastructure.b649_canonical_forecast_writer import (
    CanonicalForecastConflictError,
    CanonicalForecastWriterError,
    publish_staged,
    read_existing_bytes,
    stage_payload,
)


def test_stage_and_publish_creates_one_fsynced_no_overwrite_file(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "authority.json"
    payload = b'{"value":1}\n'

    staged = stage_payload(destination, payload)
    assert not destination.exists()
    assert staged.temporary.is_file()
    assert stat.S_IMODE(staged.temporary.stat().st_mode) == 0o600

    result = publish_staged(staged)

    assert result.status == "CREATED"
    assert destination.read_bytes() == payload
    assert read_existing_bytes(destination) == payload
    assert not staged.temporary.exists()
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert stat.S_IMODE(destination.parent.stat().st_mode) == 0o700


def test_existing_destination_is_never_overwritten(tmp_path: Path) -> None:
    destination = tmp_path / "authority.json"
    destination.write_bytes(b'{"old":true}\n')

    with pytest.raises(CanonicalForecastConflictError, match="appeared before staging"):
        stage_payload(destination, b'{"new":true}\n')
    assert destination.read_bytes() == b'{"old":true}\n'


def test_publish_race_reports_existing_and_preserves_competing_bytes(tmp_path: Path) -> None:
    destination = tmp_path / "authority.json"
    staged = stage_payload(destination, b'{"worker":1}\n')
    destination.write_bytes(b'{"other":2}\n')

    result = publish_staged(staged)

    assert result.status == "ALREADY_PRESENT"
    assert destination.read_bytes() == b'{"other":2}\n'
    assert not staged.temporary.exists()


def test_symlink_destination_and_symlink_parent_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(b"safe")
    link = tmp_path / "authority.json"
    link.symlink_to(target)
    with pytest.raises(CanonicalForecastConflictError, match="regular file"):
        read_existing_bytes(link)

    parent_target = tmp_path / "real-parent"
    parent_target.mkdir()
    parent_link = tmp_path / "linked-parent"
    parent_link.symlink_to(parent_target, target_is_directory=True)
    with pytest.raises(CanonicalForecastWriterError, match="non-directory"):
        stage_payload(parent_link / "authority.json", b"safe")


def test_destination_inside_git_worktree_is_rejected(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    with pytest.raises(CanonicalForecastWriterError, match="Git worktree"):
        stage_payload(tmp_path / "authority.json", b"safe")


def test_publish_rejects_tampered_staging_location(tmp_path: Path) -> None:
    destination = tmp_path / "authority.json"
    staged = stage_payload(destination, b"safe")
    outside = tmp_path / "outside"
    outside.mkdir()
    tampered = staged.__class__(destination, outside / staged.temporary.name, b"safe")
    with pytest.raises(CanonicalForecastWriterError, match="outside"):
        publish_staged(tampered)
    assert not destination.exists()
    assert staged.temporary.exists()
    staged.temporary.unlink()
