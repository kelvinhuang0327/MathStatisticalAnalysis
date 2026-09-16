"""Unit tests for change-aware verification preflight CLI and hermeticity scanner."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from tools.change_aware_verification import (
    CANONICAL_CURRENT_AUTHORITY_PATH,
    PINNED_SOURCE_REFRESH_RULE,
    REPO_ROOT,
    STRUCTURAL_VERIFICATION_COMMAND,
    format_text_output,
    generate_verification_plan,
    main,
    scan_test_file_hermeticity,
    scan_test_source_hermeticity,
)

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = WORKTREE_ROOT / "tools" / "change_aware_verification.py"
LEDGER_REL = CANONICAL_CURRENT_AUTHORITY_PATH
SOURCE_REL = "src/lottolab/research/synthetic_pinned_source.py"
TEST_REL = "tests/unit/test_synthetic_pinned_source.py"
PRODUCER_REL = "src/lottolab/research/historical_producer.py"
PRODUCER_TEST_REL = "tests/unit/test_historical_producer.py"
HIST_RESULT_REL = "docs/research/matrix-native-results/historical_producer.json"
RESULT_REL = "docs/research/matrix-native-results/imported-optimizer-integration-r1-result.json"
PACKAGED_REL = "src/lottolab/strategies/data/strategy_matrix_structural_v1.json"
DB_REL = "data/lottery_v2.db"
RENAMED_REL = "src/lottolab/research/renamed_pinned_source.py"
OLD_SOURCE = b"old-source-bytes\n"
NEW_SOURCE = b"new-source-bytes\n"
TEST_BYTES = b"def test_synthetic_pinned_source() -> None:\n    assert True\n"


def test_v001_application_path_triggers_architecture_test() -> None:
    plan = generate_verification_plan(["src/lottolab/application/b649_seal.py"])
    assert "V001" in plan.rules_triggered
    expected_arch = "uv run pytest -q tests/architecture/test_dependency_rules.py"
    assert expected_arch in plan.recommended_commands


def test_v001_unrelated_path_does_not_trigger_architecture_test() -> None:
    plan = generate_verification_plan(["src/lottolab/domain/rules.py"])
    assert "V001" not in plan.rules_triggered
    assert (
        "uv run pytest -q tests/architecture/test_dependency_rules.py"
        not in plan.recommended_commands
    )


def test_v001_multiple_application_paths_produce_architecture_command_once() -> None:
    plan = generate_verification_plan(
        [
            "src/lottolab/application/foo.py",
            "src/lottolab/application/bar.py",
            "src/lottolab/application/use_cases/baz.py",
        ]
    )
    arch_cmds = [
        cmd
        for cmd in plan.recommended_commands
        if "tests/architecture/test_dependency_rules.py" in cmd
    ]
    assert len(arch_cmds) == 1
    assert "V001" in plan.rules_triggered


def test_v002_changed_unit_test_paths_combine_deterministically() -> None:
    plan = generate_verification_plan(
        [
            "tests/unit/test_zeta.py",
            "tests/unit/test_alpha.py",
            "tests/unit/test_beta.py",
        ]
    )
    assert "V002" in plan.rules_triggered
    pytest_cmds = [cmd for cmd in plan.recommended_commands if "pytest" in cmd]
    assert len(pytest_cmds) == 1
    expected = (
        "uv run pytest -q tests/unit/test_alpha.py tests/unit/test_beta.py tests/unit/test_zeta.py"
    )
    assert pytest_cmds[0] == expected


def test_v003_changed_python_paths_produce_deterministic_ruff_command(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tools").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "other").mkdir(parents=True)

    (repo / "src" / "b.py").write_text("# src b")
    (repo / "src" / "a.py").write_text("# src a")
    (repo / "tools" / "t.py").write_text("# tool t")
    (repo / "other" / "o.py").write_text("# other o")

    plan = generate_verification_plan(
        ["tools/t.py", "src/b.py", "src/a.py", "other/o.py"],
        repo_root=repo,
    )
    assert "V003" in plan.rules_triggered
    ruff_cmds = [cmd for cmd in plan.recommended_commands if "ruff" in cmd]
    assert len(ruff_cmds) == 1
    assert ruff_cmds[0] == "uv run ruff check src/a.py src/b.py tools/t.py"


def test_v004_implementation_tool_paths_produce_pyright_plan(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tools").mkdir(parents=True)
    (repo / "tests" / "unit").mkdir(parents=True)

    (repo / "src" / "core.py").write_text("# core")
    (repo / "tools" / "tool.py").write_text("# tool")
    (repo / "tests" / "unit" / "test_core.py").write_text("# test core")

    plan = generate_verification_plan(
        ["src/core.py", "tools/tool.py", "tests/unit/test_core.py"],
        repo_root=repo,
    )
    assert "V004" in plan.rules_triggered
    pyright_cmds = [cmd for cmd in plan.recommended_commands if "pyright" in cmd]
    assert len(pyright_cmds) == 1
    assert pyright_cmds[0] == "uv run pyright src/core.py tools/tool.py"


def test_v005_adjacent_exact_unit_test_mapping_works_only_when_file_exists(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    app_dir = repo / "src" / "lottolab" / "application"
    unit_dir = repo / "tests" / "unit"
    app_dir.mkdir(parents=True)
    unit_dir.mkdir(parents=True)

    (app_dir / "has_test.py").write_text("# has test")
    (app_dir / "lacks_test.py").write_text("# lacks test")
    (unit_dir / "test_has_test.py").write_text("# test file")

    plan1 = generate_verification_plan(
        ["src/lottolab/application/has_test.py"],
        repo_root=repo,
    )
    assert "V005" in plan1.rules_triggered
    assert "uv run pytest -q tests/unit/test_has_test.py" in plan1.recommended_commands

    plan2 = generate_verification_plan(
        ["src/lottolab/application/lacks_test.py"],
        repo_root=repo,
    )
    assert "V005" not in plan2.rules_triggered
    assert not any("tests/unit/test_lacks_test.py" in cmd for cmd in plan2.recommended_commands)


def test_h001_direct_task_data_path_read() -> None:
    code = """
from pathlib import Path

def test_direct():
    data = Path(".task-data/example/file.json").read_bytes()
"""
    findings = scan_test_source_hermeticity(code, file_path="tests/unit/test_example.py")
    assert len(findings) == 1
    assert findings[0].rule_id == "H001"
    assert "Direct repository runtime read from '.task-data'" in findings[0].message
    assert findings[0].line == 5


def test_h001_assigned_task_data_path_then_later_read() -> None:
    code = """
from pathlib import Path

def test_assigned():
    p = Path(".task-data/example").resolve()
    text = p.read_text()
"""
    findings = scan_test_source_hermeticity(code, file_path="tests/unit/test_example.py")
    assert len(findings) == 1
    assert findings[0].rule_id == "H001"
    assert findings[0].line == 6


def test_h001_builtin_open_task_data() -> None:
    code = """
def test_open():
    with open(".task-data/example/file.json") as f:
        data = f.read()
"""
    findings = scan_test_source_hermeticity(code, file_path="tests/unit/test_example.py")
    assert len(findings) == 1
    assert findings[0].rule_id == "H001"
    assert "Direct repository runtime read from '.task-data' via open()" in findings[0].message
    assert findings[0].line == 3


def test_h002_path_home_input_dependency() -> None:
    code = """
from pathlib import Path

def test_home():
    cfg = (Path.home() / ".config" / "app.json").read_text()
"""
    findings = scan_test_source_hermeticity(code, file_path="tests/unit/test_example.py")
    assert len(findings) == 1
    assert findings[0].rule_id == "H002"
    assert findings[0].line == 5


def test_h002_expanduser_home_input_dependency() -> None:
    code = """
import os
from pathlib import Path

def test_expanduser():
    p = Path("~/.secret").expanduser()
    val = p.read_bytes()
    with open(os.path.expanduser("~/other.txt")) as f:
        pass
"""
    findings = scan_test_source_hermeticity(code, file_path="tests/unit/test_example.py")
    assert len(findings) == 2
    assert all(f.rule_id == "H002" for f in findings)


def test_h003_users_machine_path_read() -> None:
    code = """
from pathlib import Path

def test_users():
    p = Path("/Users/developer/file.json")
    return p.read_text()
"""
    findings = scan_test_source_hermeticity(code, file_path="tests/unit/test_example.py")
    assert len(findings) == 1
    assert findings[0].rule_id == "H003"
    assert findings[0].line == 6


def test_h003_home_machine_path_read() -> None:
    code = """
def test_home_linux():
    with open("/home/ci/data.txt") as f:
        return f.read()
"""
    findings = scan_test_source_hermeticity(code, file_path="tests/unit/test_example.py")
    assert len(findings) == 1
    assert findings[0].rule_id == "H003"
    assert findings[0].line == 3


def test_allowed_tmp_path_task_data_created_by_test() -> None:
    code = """
def test_tmp(tmp_path):
    p = tmp_path / ".task-data/example/file.json"
    p.parent.mkdir(parents=True)
    p.write_text("hello")
    assert p.read_text() == "hello"
"""
    findings = scan_test_source_hermeticity(code, file_path="tests/unit/test_example.py")
    assert len(findings) == 0


def test_allowed_repo_root_derived_from_tmp_path_task_data() -> None:
    code = """
def test_x(tmp_path):
    repo_root = tmp_path / "repo"
    artifact = repo_root / ".task-data/example/file.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("synthetic")
    assert artifact.read_text() == "synthetic"
"""
    findings = scan_test_source_hermeticity(code, file_path="tests/unit/test_example.py")
    assert len(findings) == 0


def test_allowed_task_data_string_in_assertion_or_message_only() -> None:
    code = """
def test_assertion():
    msg = "Path does not exist in .task-data/catalog"
    assert ".task-data" in msg
    assert msg.startswith("Path")
"""
    findings = scan_test_source_hermeticity(code, file_path="tests/unit/test_example.py")
    assert len(findings) == 0


def test_json_output_ordering_deterministic() -> None:
    plan1 = generate_verification_plan(
        ["tests/unit/test_b.py", "src/lottolab/application/foo.py", "tests/unit/test_a.py"]
    )
    plan2 = generate_verification_plan(
        ["tests/unit/test_a.py", "tests/unit/test_b.py", "src/lottolab/application/foo.py"]
    )
    j1 = json.dumps(plan1.to_dict(), indent=2)
    j2 = json.dumps(plan2.to_dict(), indent=2)
    assert j1 == j2
    parsed = json.loads(j1)
    assert parsed["changed_paths"] == sorted(parsed["changed_paths"])
    assert parsed["rules_triggered"] == sorted(parsed["rules_triggered"])


def test_duplicate_changed_paths_normalized_and_deduplicated() -> None:
    plan = generate_verification_plan(
        [
            "./src/lottolab/application/foo.py",
            "src/lottolab/application/foo.py",
            "src/lottolab/application/foo.py",
        ]
    )
    assert plan.changed_paths == ["src/lottolab/application/foo.py"]


def test_cli_invalid_mixed_input_modes_fail_clearly(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--changed-path", "src/foo.py", "--base-ref", "origin/main", "--head-ref", "HEAD"])
    assert rc == 64
    captured = capsys.readouterr()
    assert "Usage error: Cannot mix --changed-path with --base-ref/--head-ref." in captured.err


def test_cli_missing_modes_fail_clearly(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main([])
    assert rc == 64
    captured = capsys.readouterr()
    assert "Usage error" in captured.err


def test_git_range_mode_argument_array_subprocess_and_parsing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorded_commands: list[list[str]] = []

    class DummyProc:
        def __init__(
            self,
            returncode: int = 0,
            stdout: str | bytes = "",
            stderr: str | bytes = "",
        ) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def mock_run(cmd: Any, **kwargs: Any) -> DummyProc:
        assert isinstance(cmd, list)
        cmd_list = cast(list[str], cmd)
        recorded_commands.append(cmd_list)
        if len(cmd_list) >= 2 and cmd_list[1] == "diff":
            stdout = "M\tsrc/lottolab/application/foo.py\nM\ttests/unit/test_foo.py\n"
            if kwargs.get("text"):
                return DummyProc(stdout=stdout)
            return DummyProc(stdout=stdout.encode())
        empty: str | bytes = "" if kwargs.get("text") else b""
        return DummyProc(returncode=128, stdout=empty, stderr=empty)

    monkeypatch.setattr(subprocess, "run", mock_run)

    rc = main(
        [
            "--base-ref",
            "origin/main",
            "--head-ref",
            "codex/branch",
            "--repo-root",
            str(tmp_path),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    diff_cmds = [cmd for cmd in recorded_commands if len(cmd) >= 2 and cmd[1] == "diff"]
    assert diff_cmds == [
        [
            "git",
            "diff",
            "--name-status",
            "--diff-filter=ACDMRT",
            "origin/main...codex/branch",
        ]
    ]


def test_deleted_or_nonexistent_files_excluded_from_ruff_pyright(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "real.py").write_text("# real")

    plan = generate_verification_plan(
        ["src/real.py", "src/deleted_ghost.py"],
        repo_root=repo,
    )
    ruff_cmds = [c for c in plan.recommended_commands if "ruff" in c]
    pyright_cmds = [c for c in plan.recommended_commands if "pyright" in c]

    assert len(ruff_cmds) == 1
    assert "src/real.py" in ruff_cmds[0]
    assert "src/deleted_ghost.py" not in ruff_cmds[0]

    assert len(pyright_cmds) == 1
    assert "src/real.py" in pyright_cmds[0]
    assert "src/deleted_ghost.py" not in pyright_cmds[0]


def test_incident_regression_pr260_structural_shape_detected_and_corrected(tmp_path: Path) -> None:
    bad_code = """
from pathlib import Path

def test_campaign_seal_hidden_dependency(tmp_path):
    spec_path = tmp_path / "spec.json"
    real_spec = Path(
        ".task-data/BRANCH2_EXAMPLE/campaign_spec.json"
    ).resolve()
    spec_path.write_bytes(real_spec.read_bytes())
"""
    bad_test_file = tmp_path / "test_pr260_bad.py"
    bad_test_file.write_text(bad_code)

    findings_bad = scan_test_file_hermeticity(bad_test_file)
    assert len(findings_bad) == 1
    assert findings_bad[0].rule_id == "H001"
    assert "real_spec.read_bytes()" in findings_bad[0].message
    assert findings_bad[0].line == 9

    good_code = """
from pathlib import Path

def test_campaign_seal_corrected(tmp_path):
    repo_root = tmp_path / "repo"
    real_spec = (
        repo_root / ".task-data/BRANCH2_EXAMPLE/campaign_spec.json"
    ).resolve()
    real_spec.parent.mkdir(parents=True)
    real_spec.write_bytes(b"{}")
    spec_path = tmp_path / "spec.json"
    spec_path.write_bytes(real_spec.read_bytes())
"""
    good_test_file = tmp_path / "test_pr260_good.py"
    good_test_file.write_text(good_code)

    findings_good = scan_test_file_hermeticity(good_test_file)
    assert len(findings_good) == 0


def test_cli_exit_codes_and_formatting(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    test_dir = repo / "tests" / "unit"
    test_dir.mkdir(parents=True)

    bad_test = test_dir / "test_bad.py"
    bad_test.write_text("""
from pathlib import Path
def test_leak():
    p = Path(".task-data/foo.json")
    return p.read_bytes()
""")

    # Text output with violation -> exit 2
    rc = main(["--changed-path", "tests/unit/test_bad.py", "--repo-root", str(repo)])
    assert rc == 2
    captured = capsys.readouterr()
    assert "CHANGED_PATHS" in captured.out
    assert "RECOMMENDED_CHECKS" in captured.out
    assert "HERMETICITY_FINDINGS" in captured.out
    assert "[H001]" in captured.out

    # Clean file -> exit 0
    clean_test = test_dir / "test_clean.py"
    clean_test.write_text("""
def test_clean(tmp_path):
    p = tmp_path / "data.json"
    p.write_text("clean")
    assert p.read_text() == "clean"
""")
    rc_clean = main(["--changed-path", "tests/unit/test_clean.py", "--repo-root", str(repo)])
    assert rc_clean == 0
    captured_clean = capsys.readouterr()
    assert "HERMETICITY_FINDINGS\n  None" in captured_clean.out
    assert "PINNED_SOURCE_CONSUMERS\n  None" in captured_clean.out


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(repo: Path, relative: str, data: bytes) -> Path:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _synthetic_method(
    *,
    source_sha: str,
    test_sha: str,
    source_path: str = SOURCE_REL,
    test_path: str = TEST_REL,
) -> dict[str, Any]:
    return {
        "strategy_id": "SYNTHETIC_PINNED_V1",
        "source_files": [{"path": source_path, "sha256": source_sha}],
        "correctness_evidence": [{"path": test_path, "sha256": test_sha}],
        "producer": {"path": PRODUCER_REL, "sha256": "aa" * 32},
        "producer_correctness_evidence": {"path": PRODUCER_TEST_REL, "sha256": "bb" * 32},
    }


def _ledger_bytes(
    methods: list[dict[str, Any]],
    native_evidence: dict[str, Any] | None = None,
) -> bytes:
    payload = {
        "imported_optimizer_matrix": {
            "methods": methods,
            "native_evidence": native_evidence
            or {
                "historical": {
                    "evidence_class": "EXISTING_NATIVE_EXACT_EVIDENCE",
                    "path": HIST_RESULT_REL,
                    "sha256": "cc" * 32,
                }
            },
        }
    }
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


def _build_synthetic_repo(
    tmp_path: Path,
    *,
    source: bytes,
    pinned_source: bytes | None = None,
    test_bytes: bytes = TEST_BYTES,
    pinned_test: bytes | None = None,
) -> Path:
    repo = tmp_path / "repo"
    pin_source = source if pinned_source is None else pinned_source
    pin_test = test_bytes if pinned_test is None else pinned_test
    _write(repo, SOURCE_REL, source)
    _write(repo, TEST_REL, test_bytes)
    _write(repo, PRODUCER_REL, b"producer-current-bytes\n")
    _write(repo, PRODUCER_TEST_REL, b"producer-test-current-bytes\n")
    _write(repo, HIST_RESULT_REL, b"historical-current-bytes\n")
    _write(
        repo,
        RESULT_REL,
        json.dumps(
            {
                "producer": {"path": PRODUCER_REL, "sha256": "aa" * 32},
                "producer_correctness_evidence": {
                    "path": PRODUCER_TEST_REL,
                    "sha256": "bb" * 32,
                },
            },
            indent=2,
            sort_keys=True,
        ).encode("utf-8"),
    )
    _write(repo, PACKAGED_REL, b"{}\n")
    _write(repo, DB_REL, b"not-a-real-db")
    _write(
        repo,
        LEDGER_REL,
        _ledger_bytes(
            [_synthetic_method(source_sha=_sha256(pin_source), test_sha=_sha256(pin_test))]
        ),
    )
    return repo


def _fingerprints(repo: Path, relatives: list[str]) -> dict[str, tuple[int, bytes]]:
    return {rel: ((repo / rel).stat().st_mtime_ns, (repo / rel).read_bytes()) for rel in relatives}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_git(repo: Path) -> None:
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "preflight@example.com")
    _git(repo, "config", "user.name", "preflight")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "--no-verify", "-m", message)


def _run_preflight_process(repo: Path, extra: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "python", str(TOOL_PATH), "--repo-root", str(repo), *extra],
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_stale_pin_is_confirmed_mismatch_and_refresh_required(tmp_path: Path) -> None:
    repo = _build_synthetic_repo(tmp_path, source=NEW_SOURCE, pinned_source=OLD_SOURCE)
    plan = generate_verification_plan([SOURCE_REL], repo_root=repo)
    mismatches = [hit for hit in plan.pinned_source_consumers if hit.status == "confirmed_mismatch"]
    assert len(mismatches) == 1
    hit = mismatches[0]
    assert hit.source_path == SOURCE_REL
    assert hit.consumer_path == CANONICAL_CURRENT_AUTHORITY_PATH
    assert hit.consumer_id == "SYNTHETIC_PINNED_V1"
    assert hit.pin_kind == "source_files"
    assert hit.pinned_sha256 == _sha256(OLD_SOURCE)
    assert hit.snapshot_sha256 == _sha256(NEW_SOURCE)
    assert hit.pinned_sha256 != hit.snapshot_sha256
    assert PINNED_SOURCE_REFRESH_RULE in plan.rules_triggered
    assert STRUCTURAL_VERIFICATION_COMMAND in plan.recommended_commands
    assert f"uv run pytest -q {TEST_REL}" in plan.recommended_commands


def test_matching_refreshed_pin_is_affected_not_refresh_required(tmp_path: Path) -> None:
    repo = _build_synthetic_repo(tmp_path, source=NEW_SOURCE, pinned_source=NEW_SOURCE)
    plan = generate_verification_plan([SOURCE_REL], repo_root=repo)
    assert PINNED_SOURCE_REFRESH_RULE not in plan.rules_triggered
    assert not any(hit.status == "confirmed_mismatch" for hit in plan.pinned_source_consumers)
    affected = [hit for hit in plan.pinned_source_consumers if hit.status == "affected"]
    assert len(affected) == 1
    assert affected[0].source_path == SOURCE_REL
    assert affected[0].consumer_path == CANONICAL_CURRENT_AUTHORITY_PATH
    assert affected[0].pinned_sha256 == _sha256(NEW_SOURCE)
    assert affected[0].snapshot_sha256 == _sha256(NEW_SOURCE)
    assert STRUCTURAL_VERIFICATION_COMMAND in plan.recommended_commands


def test_unrelated_changed_path_is_not_a_pinned_source_hit(tmp_path: Path) -> None:
    repo = _build_synthetic_repo(tmp_path, source=NEW_SOURCE, pinned_source=NEW_SOURCE)
    _write(repo, "docs/unrelated.txt", b"unrelated\n")
    plan = generate_verification_plan(["docs/unrelated.txt"], repo_root=repo)
    assert plan.pinned_source_consumers == []
    assert PINNED_SOURCE_REFRESH_RULE not in plan.rules_triggered
    assert STRUCTURAL_VERIFICATION_COMMAND not in plan.recommended_commands


def test_historical_producer_and_native_evidence_are_not_current_source_mismatches(
    tmp_path: Path,
) -> None:
    repo = _build_synthetic_repo(tmp_path, source=NEW_SOURCE, pinned_source=NEW_SOURCE)
    plan = generate_verification_plan(
        [PRODUCER_REL, PRODUCER_TEST_REL, HIST_RESULT_REL, RESULT_REL],
        repo_root=repo,
    )
    assert PINNED_SOURCE_REFRESH_RULE not in plan.rules_triggered
    assert not any(hit.status == "confirmed_mismatch" for hit in plan.pinned_source_consumers)
    assert plan.pinned_source_consumers == []


def test_stale_correctness_evidence_pin_is_confirmed_mismatch(tmp_path: Path) -> None:
    new_test = b"def test_synthetic_pinned_source() -> None:\n    assert False\n"
    repo = _build_synthetic_repo(
        tmp_path,
        source=NEW_SOURCE,
        pinned_source=NEW_SOURCE,
        test_bytes=new_test,
        pinned_test=TEST_BYTES,
    )
    plan = generate_verification_plan([TEST_REL], repo_root=repo)
    mismatches = [hit for hit in plan.pinned_source_consumers if hit.status == "confirmed_mismatch"]
    assert len(mismatches) == 1
    assert mismatches[0].pin_kind == "correctness_evidence"
    assert mismatches[0].source_path == TEST_REL
    assert mismatches[0].pinned_sha256 == _sha256(TEST_BYTES)
    assert mismatches[0].snapshot_sha256 == _sha256(new_test)
    assert PINNED_SOURCE_REFRESH_RULE in plan.rules_triggered


def test_pinned_source_check_does_not_run_recommended_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = _build_synthetic_repo(tmp_path, source=NEW_SOURCE, pinned_source=OLD_SOURCE)

    def forbid(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(f"unexpected subprocess {args!r}")

    monkeypatch.setattr(subprocess, "run", forbid)
    plan = generate_verification_plan([SOURCE_REL], repo_root=repo)
    assert STRUCTURAL_VERIFICATION_COMMAND in plan.recommended_commands
    assert PINNED_SOURCE_REFRESH_RULE in plan.rules_triggered


def test_stale_pin_check_is_read_only(tmp_path: Path) -> None:
    repo = _build_synthetic_repo(tmp_path, source=NEW_SOURCE, pinned_source=OLD_SOURCE)
    watched = [LEDGER_REL, RESULT_REL, PACKAGED_REL, DB_REL]
    before = _fingerprints(repo, watched)
    generate_verification_plan([SOURCE_REL, TEST_REL], repo_root=repo)
    assert _fingerprints(repo, watched) == before


def test_real_canonical_artifacts_are_read_only_for_unrelated_path() -> None:
    watched = [
        REPO_ROOT / CANONICAL_CURRENT_AUTHORITY_PATH,
        REPO_ROOT / RESULT_REL,
        REPO_ROOT / PACKAGED_REL,
        REPO_ROOT / DB_REL,
    ]
    existing = [path for path in watched if path.is_file()]
    assert existing, "canonical current-authority artifacts must exist in the worktree"
    before = {path: (path.stat().st_mtime_ns, path.read_bytes()) for path in existing}
    plan = generate_verification_plan(["README.md"], repo_root=REPO_ROOT)
    assert PINNED_SOURCE_REFRESH_RULE not in plan.rules_triggered
    assert plan.pinned_source_consumers == []
    for path, (mtime_ns, data) in before.items():
        assert path.stat().st_mtime_ns == mtime_ns
        assert path.read_bytes() == data


def test_unreadable_matched_authority_is_not_pass(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    _write(repo, SOURCE_REL, NEW_SOURCE)
    _write(repo, LEDGER_REL, b"{not-json")
    rc = main(
        [
            "--changed-path",
            SOURCE_REL,
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert PINNED_SOURCE_REFRESH_RULE not in payload["rules_triggered"]
    assert payload["pinned_source_consumers"]
    assert payload["pinned_source_consumers"][0]["status"] == "unreadable"
    assert STRUCTURAL_VERIFICATION_COMMAND in payload["recommended_commands"]


def test_unsupported_matched_pin_is_not_pass(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    _write(repo, SOURCE_REL, NEW_SOURCE)
    _write(repo, TEST_REL, TEST_BYTES)
    _write(
        repo,
        LEDGER_REL,
        _ledger_bytes(
            [_synthetic_method(source_sha="not-a-sha256", test_sha=_sha256(TEST_BYTES))]
        ),
    )
    rc = main(
        [
            "--changed-path",
            SOURCE_REL,
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert PINNED_SOURCE_REFRESH_RULE not in payload["rules_triggered"]
    assert payload["pinned_source_consumers"][0]["status"] == "unsupported"
    assert payload["pinned_source_consumers"][0]["source_path"] == SOURCE_REL


def test_pinned_source_text_and_json_are_deterministic(tmp_path: Path) -> None:
    repo = _build_synthetic_repo(tmp_path, source=NEW_SOURCE, pinned_source=OLD_SOURCE)
    plan1 = generate_verification_plan([TEST_REL, SOURCE_REL], repo_root=repo)
    plan2 = generate_verification_plan([SOURCE_REL, TEST_REL], repo_root=repo)
    json1 = json.dumps(plan1.to_dict(), indent=2)
    json2 = json.dumps(plan2.to_dict(), indent=2)
    assert json1 == json2
    assert format_text_output(plan1) == format_text_output(plan2)
    parsed = json.loads(json1)
    assert parsed["changed_paths"] == sorted(parsed["changed_paths"])
    assert parsed["rules_triggered"] == sorted(parsed["rules_triggered"])
    assert parsed["pinned_source_consumers"] == sorted(
        parsed["pinned_source_consumers"],
        key=lambda hit: (
            hit["status"],
            hit["source_path"],
            hit["consumer_id"],
            hit["pin_kind"],
        ),
    )


def test_cli_process_stale_pin_reports_refresh_required(tmp_path: Path) -> None:
    repo = _build_synthetic_repo(tmp_path, source=NEW_SOURCE, pinned_source=OLD_SOURCE)
    proc = _run_preflight_process(
        repo,
        ["--changed-path", SOURCE_REL, "--format", "json"],
    )
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert PINNED_SOURCE_REFRESH_RULE in payload["rules_triggered"]
    mismatch = payload["pinned_source_consumers"][0]
    assert mismatch["status"] == "confirmed_mismatch"
    assert mismatch["source_path"] == SOURCE_REL
    assert mismatch["consumer_path"] == CANONICAL_CURRENT_AUTHORITY_PATH
    assert mismatch["pinned_sha256"] == _sha256(OLD_SOURCE)
    assert mismatch["snapshot_sha256"] == _sha256(NEW_SOURCE)
    assert STRUCTURAL_VERIFICATION_COMMAND in payload["recommended_commands"]


def test_cli_process_matching_pin_is_not_refresh_required(tmp_path: Path) -> None:
    repo = _build_synthetic_repo(tmp_path, source=NEW_SOURCE, pinned_source=NEW_SOURCE)
    proc = _run_preflight_process(
        repo,
        ["--changed-path", SOURCE_REL, "--format", "text"],
    )
    assert proc.returncode == 0
    assert PINNED_SOURCE_REFRESH_RULE not in proc.stdout
    assert "confirmed_mismatch" not in proc.stdout
    assert SOURCE_REL in proc.stdout
    assert CANONICAL_CURRENT_AUTHORITY_PATH in proc.stdout
    assert "[affected]" in proc.stdout


def test_git_range_deletion_of_pinned_source_is_confirmed_mismatch(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    repo = _build_synthetic_repo(tmp_path, source=NEW_SOURCE, pinned_source=NEW_SOURCE)
    _init_git(repo)
    _commit_all(repo, "base with pinned source")
    (repo / SOURCE_REL).unlink()
    _commit_all(repo, "delete pinned source")
    rc = main(
        [
            "--base-ref",
            "HEAD~1",
            "--head-ref",
            "HEAD",
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert SOURCE_REL in payload["changed_paths"]
    assert PINNED_SOURCE_REFRESH_RULE in payload["rules_triggered"]
    mismatch = next(
        hit
        for hit in payload["pinned_source_consumers"]
        if hit["source_path"] == SOURCE_REL
    )
    assert mismatch["status"] == "confirmed_mismatch"
    assert mismatch["pinned_sha256"] == _sha256(NEW_SOURCE)
    assert mismatch["snapshot_sha256"] is None


def test_git_range_rename_old_path_is_changed_and_mismatch_if_still_pinned(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    repo = _build_synthetic_repo(tmp_path, source=NEW_SOURCE, pinned_source=NEW_SOURCE)
    _init_git(repo)
    _commit_all(repo, "base with old path")
    _git(repo, "mv", SOURCE_REL, RENAMED_REL)
    _commit_all(repo, "rename pinned source")
    rc = main(
        [
            "--base-ref",
            "HEAD~1",
            "--head-ref",
            "HEAD",
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert SOURCE_REL in payload["changed_paths"]
    assert RENAMED_REL in payload["changed_paths"]
    assert PINNED_SOURCE_REFRESH_RULE in payload["rules_triggered"]
    mismatch = next(
        hit
        for hit in payload["pinned_source_consumers"]
        if hit["source_path"] == SOURCE_REL
    )
    assert mismatch["status"] == "confirmed_mismatch"
    assert mismatch["snapshot_sha256"] is None


def test_git_range_uses_head_snapshot_not_dirty_worktree(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    repo = _build_synthetic_repo(tmp_path, source=OLD_SOURCE, pinned_source=OLD_SOURCE)
    _init_git(repo)
    _commit_all(repo, "old pin")
    _write(repo, SOURCE_REL, NEW_SOURCE)
    _write(
        repo,
        LEDGER_REL,
        _ledger_bytes(
            [_synthetic_method(source_sha=_sha256(NEW_SOURCE), test_sha=_sha256(TEST_BYTES))]
        ),
    )
    _commit_all(repo, "refreshed pin")
    dirty = b"dirty-uncommitted-source\n"
    _write(repo, SOURCE_REL, dirty)
    rc = main(
        [
            "--base-ref",
            "HEAD~1",
            "--head-ref",
            "HEAD",
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert PINNED_SOURCE_REFRESH_RULE not in payload["rules_triggered"]
    hit = next(
        item
        for item in payload["pinned_source_consumers"]
        if item["source_path"] == SOURCE_REL
    )
    assert hit["status"] == "affected"
    assert hit["snapshot_sha256"] == _sha256(NEW_SOURCE)
    assert hit["snapshot_sha256"] != _sha256(dirty)
    assert hit["pinned_sha256"] == _sha256(NEW_SOURCE)
