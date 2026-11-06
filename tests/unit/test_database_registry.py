from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from lottolab.infrastructure.persistence import database_registry as registry
from lottolab.interfaces.cli import database_registry as registry_cli
from lottolab.interfaces.cli.main import app as main_app

TASK_ID = "REGISTRY_TEST_TASK"
OTHER_TASK_ID = "OLD_REGISTRY_TASK"


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    root = tmp_path / "fake-canonical"
    directory = root / "data" / "databases"
    directory.mkdir(parents=True)
    _write_registry(directory / registry.REGISTRY_FILENAME)
    return root


def _write_registry(path: Path, *, writable: list[str] | None = None) -> bytes:
    payload = (
        json.dumps(
            {
                "version": 1,
                "read_databases": {"LOTTOLAB_TEST_DB": "test.sqlite3"},
                "writable_databases": writable if writable is not None else [],
            },
            indent=2,
        )
        + "\n"
    )
    raw = payload.encode("utf-8")
    path.write_bytes(raw)
    return raw


def _registry_hash(project: Path) -> str:
    return hashlib.sha256(registry.registry_path(project).read_bytes()).hexdigest()


def _row(before_hash: str, after_hash: str, *, task_id: str = OTHER_TASK_ID) -> dict[str, object]:
    return {
        "time_utc": "2026-11-06T00:00:00Z",
        "task_id": task_id,
        "file": registry.REGISTRY_FILENAME,
        "operation": "backfill",
        "before_sha256": before_hash,
        "after_sha256": after_hash,
        "authorization_path": "/tmp/authorization.txt",
        "tool": None,
        "status": "RECORDED",
        "evidence": [],
        "note": "",
    }


def _write_log(project: Path, rows: list[dict[str, object]]) -> None:
    path = registry.changelog_path(project)
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _authorization(tmp_path: Path, task_id: str = TASK_ID) -> Path:
    path = tmp_path / "authorization.txt"
    path.write_text(f"我授權 {task_id}\n", encoding="utf-8")
    return path


def _valid_backfill_entry(current_hash: str) -> dict[str, object]:
    return {
        "time": "2026-11-04T09:30:00Z",
        "task_id": "HISTORICAL_TASK",
        "before_sha256": "0" * 64,
        "after_sha256": current_hash,
        "evidence": ["evidence/old-change.txt"],
        "status": "RECORDED",
    }


def test_verify_no_changelog_is_read_only_and_creates_no_files(fake_project: Path) -> None:
    directory = registry.database_directory(fake_project)
    before = sorted(path.relative_to(fake_project).as_posix() for path in fake_project.rglob("*"))

    result = registry.verify_registry(fake_project)

    after = sorted(path.relative_to(fake_project).as_posix() for path in fake_project.rglob("*"))
    assert result.status == "NO_CHANGELOG"
    assert result.registry_sha256 == _registry_hash(fake_project)
    assert result.changelog_after_sha256 is None
    assert result.task_id is None
    assert before == after
    assert not (directory / "locks").exists()


def test_verify_ok_reports_registry_and_last_changelog_hash(fake_project: Path) -> None:
    current_hash = _registry_hash(fake_project)
    _write_log(fake_project, [_row("0" * 64, current_hash)])

    result = registry.verify_registry(fake_project)

    assert result.status == "OK"
    assert result.registry_sha256 == current_hash
    assert result.changelog_after_sha256 == current_hash
    assert result.task_id == OTHER_TASK_ID
    assert not (registry.database_directory(fake_project) / "locks").exists()


def test_verify_unrecorded_change_reports_both_hashes(fake_project: Path) -> None:
    _write_log(fake_project, [_row("0" * 64, "1" * 64)])

    result = registry.verify_registry(fake_project)

    assert result.status == "UNRECORDED_CHANGE"
    assert result.registry_sha256 == _registry_hash(fake_project)
    assert result.changelog_after_sha256 == "1" * 64
    assert result.task_id == OTHER_TASK_ID


@pytest.mark.parametrize("malformed", [False, True], ids=["disconnected-chain", "invalid-json"])
def test_verify_broken_chain(malformed: bool, fake_project: Path) -> None:
    current_hash = _registry_hash(fake_project)
    first = _row("0" * 64, "1" * 64)
    if malformed:
        registry.changelog_path(fake_project).write_text(
            json.dumps(first) + "\nnot-json\n", encoding="utf-8"
        )
    else:
        second = _row("2" * 64, current_hash, task_id="SECOND_TASK")
        _write_log(fake_project, [first, second])

    result = registry.verify_registry(fake_project)

    assert result.status == "BROKEN_CHAIN"
    assert result.exit_code == registry.VERIFY_EXIT_CODES["BROKEN_CHAIN"]
    assert not (registry.database_directory(fake_project) / "locks").exists()


def test_verify_empty_changelog_is_no_changelog(fake_project: Path) -> None:
    registry.changelog_path(fake_project).write_bytes(b"")

    result = registry.verify_registry(fake_project)

    assert result.status == "NO_CHANGELOG"


@pytest.mark.parametrize("case", ["missing", "relative", "wrong-task"])
def test_write_authorization_is_checked_before_lease(
    case: str, fake_project: Path, tmp_path: Path
) -> None:
    current_hash = _registry_hash(fake_project)
    _write_log(fake_project, [_row("0" * 64, current_hash)])
    auth = _authorization(tmp_path)
    if case == "missing":
        auth = tmp_path / "missing-authorization.txt"
    elif case == "relative":
        auth = Path("relative-authorization.txt")
    elif case == "wrong-task":
        auth = _authorization(tmp_path, "DIFFERENT_TASK")

    with pytest.raises(registry.RegistryError, match=r"authorization-file|authorization"):
        registry.add_writable(
            fake_project,
            "new.sqlite3",
            task_id=TASK_ID,
            authorization_file=auth,
        )

    assert not (registry.database_directory(fake_project) / "locks").exists()
    assert registry.verify_registry(fake_project).status == "OK"


def test_add_refuses_unverified_registry_and_releases_lease(
    fake_project: Path, tmp_path: Path
) -> None:
    with pytest.raises(registry.RegistryError, match="run backfill"):
        registry.add_writable(
            fake_project,
            "new.sqlite3",
            task_id=TASK_ID,
            authorization_file=_authorization(tmp_path),
        )

    lease = registry.database_directory(fake_project) / "locks" / registry.LEASE_FILENAME
    assert not lease.exists()
    assert registry.verify_registry(fake_project).status == "NO_CHANGELOG"


def test_lease_content_and_release(
    fake_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _registry_hash(fake_project)
    _write_log(fake_project, [_row("0" * 64, before)])
    auth = _authorization(tmp_path)
    verify = registry.verify_registry
    observed: dict[str, object] = {}

    def observe_lease(project_root: Path) -> registry.VerificationResult:
        lease = registry.database_directory(project_root) / "locks" / registry.LEASE_FILENAME
        payload = json.loads(lease.read_text(encoding="utf-8"))
        observed.update(cast(dict[str, object], payload))
        return verify(project_root)

    monkeypatch.setattr(registry, "verify_registry", observe_lease)
    registry.add_writable(fake_project, "new.sqlite3", task_id=TASK_ID, authorization_file=auth)

    assert observed["task_id"] == TASK_ID
    assert observed["mode"] == "WRITE"
    assert observed["authorization_path"] == str(auth)
    assert isinstance(observed["started_at"], str)
    assert isinstance(observed["expected_end_at"], str)
    assert not (
        registry.database_directory(fake_project) / "locks" / registry.LEASE_FILENAME
    ).exists()


def test_lease_conflict_reports_other_process_content_without_removing_lease(
    fake_project: Path, tmp_path: Path
) -> None:
    current_hash = _registry_hash(fake_project)
    _write_log(fake_project, [_row("0" * 64, current_hash)])
    locks = registry.database_directory(fake_project) / "locks"
    locks.mkdir()
    lease = locks / registry.LEASE_FILENAME
    other_content = json.dumps({"task_id": "OTHER", "mode": "WRITE"}) + "\n"
    child_code = (
        "import sys\n"
        "from pathlib import Path\n"
        "path=Path(sys.argv[1])\n"
        "with path.open('x', encoding='utf-8') as handle:\n"
        f"    handle.write({other_content!r})\n"
        "    handle.flush()\n"
        "print('READY', flush=True)\n"
        "sys.stdin.readline()\n"
    )
    process = subprocess.Popen(
        (sys.executable, "-B", "-c", child_code, str(lease)),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        ready = process.stdout.readline().strip()
        if ready != "READY":
            assert process.stderr is not None
            raise AssertionError(f"lease holder did not start: {process.stderr.read()}")
        with pytest.raises(registry.RegistryError) as error:
            registry.add_writable(
                fake_project,
                "new.sqlite3",
                task_id=TASK_ID,
                authorization_file=_authorization(tmp_path),
            )

        assert error.value.status == "WAITING_ON_LEASE"
        assert error.value.exit_code == 75
        assert "WAITING_ON_LEASE" in str(error.value)
        assert other_content.strip() in str(error.value)
        assert lease.read_text(encoding="utf-8") == other_content
    finally:
        if process.poll() is None and process.stdin is not None:
            process.stdin.write("release\n")
            process.stdin.flush()
            process.stdin.close()
        process.wait(timeout=10)


def test_write_rejects_symlinked_locks_directory(fake_project: Path, tmp_path: Path) -> None:
    current_hash = _registry_hash(fake_project)
    _write_log(fake_project, [_row("0" * 64, current_hash)])
    directory = registry.database_directory(fake_project)
    outside = tmp_path / "outside-locks"
    outside.mkdir()
    (directory / "locks").symlink_to(outside, target_is_directory=True)

    with pytest.raises(registry.RegistryError, match="must not be a symlink"):
        registry.add_writable(
            fake_project,
            "new.sqlite3",
            task_id=TASK_ID,
            authorization_file=_authorization(tmp_path),
        )

    assert list(outside.iterdir()) == []


def test_add_remove_preserve_other_fields_and_record_changelog(
    fake_project: Path, tmp_path: Path
) -> None:
    registry_file = registry.registry_path(fake_project)
    _write_registry(registry_file, writable=["existing.sqlite3"])
    initial_hash = _registry_hash(fake_project)
    _write_log(fake_project, [_row("0" * 64, initial_hash)])
    auth = _authorization(tmp_path)

    added = registry.add_writable(
        fake_project, "new.sqlite3", task_id=TASK_ID, authorization_file=auth
    )
    after_add = registry_file.read_text(encoding="utf-8")
    parsed_after_add = json.loads(after_add)
    assert parsed_after_add["version"] == 1
    assert parsed_after_add["read_databases"] == {"LOTTOLAB_TEST_DB": "test.sqlite3"}
    assert parsed_after_add["writable_databases"] == ["existing.sqlite3", "new.sqlite3"]
    assert '\n  "read_databases"' in after_add
    assert added.before_sha256 == initial_hash
    assert registry.verify_registry(fake_project).status == "OK"

    removed = registry.remove_writable(
        fake_project, "existing.sqlite3", task_id=TASK_ID, authorization_file=auth
    )
    parsed_after_remove = json.loads(registry_file.read_text(encoding="utf-8"))
    assert parsed_after_remove["writable_databases"] == ["new.sqlite3"]
    assert removed.before_sha256 == added.after_sha256
    assert registry.verify_registry(fake_project).status == "OK"

    with pytest.raises(registry.RegistryError, match="already writable"):
        registry.add_writable(fake_project, "new.sqlite3", task_id=TASK_ID, authorization_file=auth)
    with pytest.raises(registry.RegistryError, match="not writable"):
        registry.remove_writable(
            fake_project, "missing.sqlite3", task_id=TASK_ID, authorization_file=auth
        )

    rows = [
        cast(dict[str, object], json.loads(line))
        for line in registry.changelog_path(fake_project).read_text(encoding="utf-8").splitlines()
    ]
    add_row = rows[-2]
    remove_row = rows[-1]
    required = {
        "time_utc",
        "task_id",
        "file",
        "operation",
        "before_sha256",
        "after_sha256",
        "authorization_path",
        "tool",
        "status",
        "evidence",
        "note",
    }
    assert required <= add_row.keys()
    assert required <= remove_row.keys()
    assert add_row["operation"] == "add"
    assert remove_row["operation"] == "remove"
    assert add_row["status"] == remove_row["status"] == "RECORDED"
    assert add_row["authorization_path"] == str(auth)
    assert add_row["evidence"] == []
    assert isinstance(add_row["time_utc"], str)


def test_registry_hash_race_is_detected_before_replace(
    fake_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry_file = registry.registry_path(fake_project)
    before = _registry_hash(fake_project)
    _write_log(fake_project, [_row("0" * 64, before)])
    render_json = json.dumps

    def race_render(
        value: object,
        *,
        ensure_ascii: bool = True,
        sort_keys: bool = False,
        indent: int | str | None = None,
        separators: tuple[str, str] | None = None,
    ) -> str:
        rendered = render_json(
            value,
            ensure_ascii=ensure_ascii,
            sort_keys=sort_keys,
            indent=indent,
            separators=separators,
        )
        if isinstance(value, dict) and "writable_databases" in value:
            registry_file.write_bytes(registry_file.read_bytes() + b" ")
        return rendered

    monkeypatch.setattr(registry.json, "dumps", race_render)
    with pytest.raises(registry.RegistryError, match="REGISTRY_CHANGED_DURING_EDIT"):
        registry.add_writable(
            fake_project,
            "new.sqlite3",
            task_id=TASK_ID,
            authorization_file=_authorization(tmp_path),
        )

    assert registry.registry_path(fake_project).read_bytes().endswith(b" ")
    assert registry.verify_registry(fake_project).status == "UNRECORDED_CHANGE"


def test_crash_after_registry_replace_is_detected_by_verify(
    fake_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _registry_hash(fake_project)
    _write_log(fake_project, [_row("0" * 64, before)])
    changelog = registry.changelog_path(fake_project)
    real_open = registry.os.open

    def fail_changelog_open(path: str | os.PathLike[str], flags: int, mode: int = 0o777) -> int:
        if Path(path) == changelog:
            raise OSError("simulated crash before changelog append")
        return real_open(path, flags, mode)

    monkeypatch.setattr(registry.os, "open", fail_changelog_open)
    with pytest.raises(registry.RegistryError, match="cannot open changelog for append"):
        registry.add_writable(
            fake_project,
            "new.sqlite3",
            task_id=TASK_ID,
            authorization_file=_authorization(tmp_path),
        )

    assert registry.verify_registry(fake_project).status == "UNRECORDED_CHANGE"
    assert not (
        registry.database_directory(fake_project) / "locks" / registry.LEASE_FILENAME
    ).exists()


def test_partial_atomic_write_leaves_registry_unchanged(
    fake_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry_file = registry.registry_path(fake_project)
    original = registry_file.read_bytes()
    current_hash = hashlib.sha256(original).hexdigest()
    _write_log(fake_project, [_row("0" * 64, current_hash)])
    real_write = registry.os.write
    calls = 0

    def partial_then_fail(descriptor: int, payload: bytes | memoryview) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            return real_write(descriptor, payload[:7])
        raise OSError("simulated partial write failure")

    monkeypatch.setattr(registry.os, "write", partial_then_fail)
    with pytest.raises(registry.RegistryError, match="simulated partial write failure"):
        registry.add_writable(
            fake_project,
            "new.sqlite3",
            task_id=TASK_ID,
            authorization_file=_authorization(tmp_path),
        )

    assert registry_file.read_bytes() == original
    assert registry.verify_registry(fake_project).status == "OK"
    assert not list(registry_file.parent.glob(f".{registry.REGISTRY_FILENAME}.*.tmp"))


@pytest.mark.parametrize("invalid", ["disconnected", "wrong-final-hash"])
def test_backfill_rejects_disconnected_or_wrong_final_hash(
    invalid: str, fake_project: Path, tmp_path: Path
) -> None:
    current_hash = _registry_hash(fake_project)
    first = _valid_backfill_entry(current_hash)
    if invalid == "disconnected":
        second = {
            "time": "2026-11-05T09:48:00Z",
            "task_id": "SECOND_HISTORICAL_TASK",
            "before_sha256": "2" * 64,
            "after_sha256": current_hash,
            "evidence": ["evidence/second.txt"],
            "status": "RECORDED",
        }
        entries = [first, second]
    else:
        first["after_sha256"] = "f" * 64
        entries = [first]
    entries_file = tmp_path / "entries.json"
    entries_file.write_text(json.dumps(entries), encoding="utf-8")

    with pytest.raises(registry.RegistryError, match=r"backfill|after_sha256"):
        registry.backfill_changelog(
            fake_project,
            entries_file,
            task_id=TASK_ID,
            authorization_file=_authorization(tmp_path),
        )

    assert registry.verify_registry(fake_project).status == "NO_CHANGELOG"


def test_backfill_appends_normalized_entry_without_changing_registry(
    fake_project: Path, tmp_path: Path
) -> None:
    registry_file = registry.registry_path(fake_project)
    original = registry_file.read_bytes()
    current_hash = hashlib.sha256(original).hexdigest()
    entries_file = tmp_path / "entries.json"
    entries_file.write_text(json.dumps([_valid_backfill_entry(current_hash)]), encoding="utf-8")

    result = registry.backfill_changelog(
        fake_project,
        entries_file,
        task_id=TASK_ID,
        authorization_file=_authorization(tmp_path),
    )

    row = cast(dict[str, object], json.loads(registry.changelog_path(fake_project).read_text()))
    assert result.entries_written == 1
    assert registry_file.read_bytes() == original
    assert registry.verify_registry(fake_project).status == "OK"
    assert row["time_utc"] == "2026-11-04T09:30:00Z"
    assert row["task_id"] == "HISTORICAL_TASK"
    assert row["authorized_by_task_id"] == TASK_ID
    assert row["status"] == "RECORDED"
    assert row["evidence"] == ["evidence/old-change.txt"]
    assert set(row) >= {
        "time_utc",
        "task_id",
        "file",
        "operation",
        "before_sha256",
        "after_sha256",
        "authorization_path",
        "tool",
        "status",
        "evidence",
        "note",
    }


def test_cli_add_remove_and_backfill_commands_exit_zero(
    fake_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current_hash = _registry_hash(fake_project)
    _write_log(fake_project, [_row("0" * 64, current_hash)])
    auth = _authorization(tmp_path)
    monkeypatch.setattr(registry_cli, "canonical_project_root", lambda: fake_project)
    runner = CliRunner()

    added = runner.invoke(
        main_app,
        [
            "db-registry",
            "add-writable",
            "cli.sqlite3",
            "--task-id",
            TASK_ID,
            "--authorization-file",
            str(auth),
        ],
    )
    assert added.exit_code == 0
    assert "operation=add" in added.stdout

    removed = runner.invoke(
        main_app,
        [
            "db-registry",
            "remove-writable",
            "cli.sqlite3",
            "--task-id",
            TASK_ID,
            "--authorization-file",
            str(auth),
        ],
    )
    assert removed.exit_code == 0
    assert "operation=remove" in removed.stdout

    current_hash = _registry_hash(fake_project)
    entries_file = tmp_path / "entries-cli.json"
    entries_file.write_text(
        json.dumps(
            [
                {
                    "time": "2026-11-06T00:00:00Z",
                    "task_id": "CLI_HISTORY",
                    "before_sha256": current_hash,
                    "after_sha256": current_hash,
                    "evidence": ["evidence/cli.txt"],
                    "status": "RECORDED",
                }
            ]
        ),
        encoding="utf-8",
    )
    backfilled = runner.invoke(
        main_app,
        [
            "db-registry",
            "backfill",
            "--entries",
            str(entries_file),
            "--task-id",
            TASK_ID,
            "--authorization-file",
            str(auth),
        ],
    )
    assert backfilled.exit_code == 0
    assert "operation=backfill" in backfilled.stdout
    assert registry.verify_registry(fake_project).status == "OK"


def test_cli_write_lease_conflict_uses_dedicated_exit_code(
    fake_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current_hash = _registry_hash(fake_project)
    _write_log(fake_project, [_row("0" * 64, current_hash)])
    locks = registry.database_directory(fake_project) / "locks"
    locks.mkdir()
    lease = locks / registry.LEASE_FILENAME
    lease.write_text('{"task_id":"OTHER","mode":"WRITE"}\\n', encoding="utf-8")
    authorization = _authorization(tmp_path)
    monkeypatch.setattr(registry_cli, "canonical_project_root", lambda: fake_project)

    result = CliRunner().invoke(
        main_app,
        [
            "db-registry",
            "add-writable",
            "new.sqlite3",
            "--task-id",
            TASK_ID,
            "--authorization-file",
            str(authorization),
        ],
    )

    assert result.exit_code == 75
    assert "WAITING_ON_LEASE" in result.output
    assert '"task_id":"OTHER"' in result.output
    assert lease.exists()


@pytest.mark.parametrize(
    ("state", "expected_code"),
    [
        ("OK", 0),
        ("UNRECORDED_CHANGE", 2),
        ("NO_CHANGELOG", 3),
        ("BROKEN_CHAIN", 4),
    ],
)
def test_cli_verify_exit_codes(
    state: str,
    expected_code: int,
    fake_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_hash = _registry_hash(fake_project)
    changelog = registry.changelog_path(fake_project)
    if state == "OK":
        _write_log(fake_project, [_row("0" * 64, current_hash)])
    elif state == "UNRECORDED_CHANGE":
        _write_log(fake_project, [_row("0" * 64, "1" * 64)])
    elif state == "BROKEN_CHAIN":
        changelog.write_text("{invalid-json}\n", encoding="utf-8")

    monkeypatch.setattr(registry_cli, "canonical_project_root", lambda: fake_project)
    result = CliRunner().invoke(main_app, ["db-registry", "verify"])

    assert result.exit_code == expected_code
    assert f"status={state}" in result.stdout
    assert "registry_sha256=" in result.stdout
    assert "changelog_after_sha256=" in result.stdout
    assert "task_id=" in result.stdout
    assert not (registry.database_directory(fake_project) / "locks").exists()


def _database_snapshot(project: Path) -> dict[str, tuple[bytes, int, int]]:
    """Observe content and metadata, including unexpected lock/temp files."""
    return {
        path.relative_to(project).as_posix(): (
            path.read_bytes(),
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in project.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("operation", ["add", "remove", "backfill"])
@pytest.mark.parametrize(
    "sentence",
    [
        "我授權 {task}",
        "我授權 {task}\n",
        "我授權 {task}\r\n",
        "我授權 {task}\r",
        "我授權\n{task}\n",
        "我授權\r\n{task}\r\n",
        "我授權\t{task}",
        "我授權 {task}。允許本次操作。",
        "我授權 {task}，限本次操作。",  # noqa: RUF001
        "我授權 {task}；限本次操作。",  # noqa: RUF001
        "我授權 {task}：限本次操作。",  # noqa: RUF001
        "我授權 {task}！",  # noqa: RUF001
        "我授權 {task}？",  # noqa: RUF001
        "我授權 {task}、限本次操作。",
        "我授權 {task}.\n",
        "我授權 {task}: approved",
        "我授權 {task}; approved",
        "我授權 {task}, approved",
        "「我授權 {task}」",
        '"我授權 {task}"',
        "（我授權 {task}）",  # noqa: RUF001
        "我授權 {task})",
        "我授權 {task}]",
        "我授權 {task}!",
    ],
)
def test_authorization_accepts_exact_task_with_sentence_boundaries(
    operation: str, sentence: str, fake_project: Path, tmp_path: Path
) -> None:
    _write_registry(registry.registry_path(fake_project), writable=["existing.sqlite3"])
    current = _registry_hash(fake_project)
    _write_log(fake_project, [_row("0" * 64, current)])
    auth = _authorization(tmp_path)
    auth.write_text(sentence.format(task=TASK_ID), encoding="utf-8", newline="")
    entries = tmp_path / "entries.json"
    entry = _valid_backfill_entry(current)
    entry["before_sha256"] = current
    entries.write_text(json.dumps([entry]), encoding="utf-8")

    if operation == "add":
        result = registry.add_writable(
            fake_project, "new.sqlite3", task_id=TASK_ID, authorization_file=auth
        )
    elif operation == "remove":
        result = registry.remove_writable(
            fake_project, "existing.sqlite3", task_id=TASK_ID, authorization_file=auth
        )
    else:
        result = registry.backfill_changelog(
            fake_project, entries, task_id=TASK_ID, authorization_file=auth
        )
    assert result.operation == operation
    assert registry.verify_registry(fake_project).status == "OK"


@pytest.mark.parametrize("through_cli", [False, True], ids=["persistence", "cli"])
@pytest.mark.parametrize("operation", ["add", "remove", "backfill"])
@pytest.mark.parametrize(
    "sentence",
    [
        "我授權 {task}_OTHER",
        "我授權 PREFIX_{task}",
        "我授權 {task}-OTHER",
        "我授權 {task}.OTHER",
        "我授權 {task}/OTHER",
        "我授權 {task}+OTHER",
        "我授權 {task}OTHER",
        "我授權 {task}其他",
        "我授權 ANOTHER_TASK",
        "我授權 {task}0",
        "我授權 X{task}",
        "我授權 judge_r33",
        "不我授權 {task}",
        "我授權 {task}:OTHER",
    ],
)
def test_authorization_rejects_other_task_without_any_database_write(
    through_cli: bool,
    operation: str,
    sentence: str,
    fake_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_id = "JUDGE_R33"
    _write_registry(registry.registry_path(fake_project), writable=["existing.sqlite3"])
    current = _registry_hash(fake_project)
    _write_log(fake_project, [_row("0" * 64, current)])
    auth = _authorization(tmp_path)
    auth.write_text(sentence.format(task=task_id) + "\n", encoding="utf-8")
    # A valid self-loop history ensures backfill would mutate the log if authorized.
    entry = _valid_backfill_entry(current)
    entry["before_sha256"] = current
    entries = tmp_path / "entries.json"
    entries.write_text(json.dumps([entry]), encoding="utf-8")
    before = _database_snapshot(fake_project)
    paths_before = sorted(str(p.relative_to(fake_project)) for p in fake_project.rglob("*"))

    if through_cli:
        monkeypatch.setattr(registry_cli, "canonical_project_root", lambda: fake_project)
        args = {
            "add": ["add-writable", "new.sqlite3"],
            "remove": ["remove-writable", "existing.sqlite3"],
            "backfill": ["backfill", "--entries", str(entries)],
        }[operation]
        result = CliRunner().invoke(
            main_app,
            ["db-registry", *args, "--task-id", task_id, "--authorization-file", str(auth)],
        )
        assert result.exit_code == 1
        assert "AUTHORIZATION_REQUIRED" in result.output
    else:
        with pytest.raises(registry.RegistryError) as error:
            if operation == "add":
                registry.add_writable(
                    fake_project, "new.sqlite3", task_id=task_id, authorization_file=auth
                )
            elif operation == "remove":
                registry.remove_writable(
                    fake_project, "existing.sqlite3", task_id=task_id, authorization_file=auth
                )
            else:
                registry.backfill_changelog(
                    fake_project, entries, task_id=task_id, authorization_file=auth
                )
        assert error.value.status == "AUTHORIZATION_REQUIRED"
        assert error.value.exit_code == 1
    assert _database_snapshot(fake_project) == before
    assert sorted(str(p.relative_to(fake_project)) for p in fake_project.rglob("*")) == paths_before


@pytest.mark.parametrize("state", ["OK", "NO_CHANGELOG", "UNRECORDED_CHANGE", "BROKEN_CHAIN"])
def test_verify_preserves_all_file_content_and_metadata(state: str, fake_project: Path) -> None:
    if state == "OK":
        _write_log(fake_project, [_row("0" * 64, _registry_hash(fake_project))])
    elif state == "UNRECORDED_CHANGE":
        _write_log(fake_project, [_row("0" * 64, "1" * 64)])
    elif state == "BROKEN_CHAIN":
        registry.changelog_path(fake_project).write_text("{broken}\n", encoding="utf-8")
    before = _database_snapshot(fake_project)
    paths_before = sorted(str(p.relative_to(fake_project)) for p in fake_project.rglob("*"))
    assert registry.verify_registry(fake_project).status == state
    assert _database_snapshot(fake_project) == before
    assert sorted(str(p.relative_to(fake_project)) for p in fake_project.rglob("*")) == paths_before


def test_hard_exit_after_replace_is_detected_and_does_not_recover(
    fake_project: Path, tmp_path: Path
) -> None:
    _write_log(fake_project, [_row("0" * 64, _registry_hash(fake_project))])
    auth = _authorization(tmp_path)
    before = _database_snapshot(fake_project)
    child = """
import os, sys
from pathlib import Path
from lottolab.infrastructure.persistence import database_registry as registry
registry._append_changelog = lambda *args: os._exit(91)
registry.add_writable(Path(sys.argv[1]), 'new.sqlite3', task_id=sys.argv[2],
                      authorization_file=Path(sys.argv[3]))
"""
    result = subprocess.run(
        (sys.executable, "-B", "-c", child, str(fake_project), TASK_ID, str(auth)),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 91
    assert result.stdout == result.stderr == ""
    registry_key = "data/databases/" + registry.REGISTRY_FILENAME
    log_key = "data/databases/" + registry.CHANGELOG_FILENAME
    after = _database_snapshot(fake_project)
    assert after[registry_key][0] != before[registry_key][0]
    assert after[log_key] == before[log_key]
    assert registry.verify_registry(fake_project).status == "UNRECORDED_CHANGE"
    lease = registry.database_directory(fake_project) / "locks" / registry.LEASE_FILENAME
    assert lease.exists()
    with pytest.raises(registry.RegistryError) as error:
        registry.add_writable(
            fake_project, "retry.sqlite3", task_id=TASK_ID, authorization_file=auth
        )
    assert error.value.status == "WAITING_ON_LEASE"
    assert error.value.exit_code == 75
    assert _database_snapshot(fake_project) == after
