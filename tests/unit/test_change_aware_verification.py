"""Unit tests for change-aware verification preflight CLI and hermeticity scanner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from tools.change_aware_verification import (
    generate_verification_plan,
    main,
    scan_test_file_hermeticity,
    scan_test_source_hermeticity,
)


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
        returncode = 0
        stdout = "src/lottolab/application/foo.py\ntests/unit/test_foo.py\n"
        stderr = ""

    def mock_run(cmd: Any, **kwargs: Any) -> DummyProc:
        assert isinstance(cmd, list)
        from typing import cast

        cmd_list = cast(list[str], cmd)
        recorded_commands.append(cmd_list)
        return DummyProc()

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
    assert len(recorded_commands) == 1
    assert recorded_commands[0] == [
        "git",
        "diff",
        "--name-only",
        "--diff-filter=ACMRT",
        "origin/main...codex/branch",
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
