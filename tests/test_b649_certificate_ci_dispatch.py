"""Exercise the workflow's actual shell; uv is stubbed only for dispatch."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import TypedDict, cast

import pytest

EXISTING = (
    "tests/unit/test_b649_three_max_profiles_shared_certificate_r2.py",
    "tests/unit/test_b649_min_s2_owner_a_exact_bound_r1.py",
    "tests/unit/test_b649_min_s2_owner_b_exact_bound_r1.py",
    "tests/unit/test_b649_min_s2_post_t256_next_owner_cap248_cert_r1.py",
    "tests/unit/test_b649_min_s2_t249_bonf5_single_row_composition_r1.py",
    "tests/unit/test_b649_min_s2_t249_dual_profile_composition_r1.py",
    "tests/unit/test_b649_min_s2_three_tied_owner_combined_authority_r1.py",
    "tests/unit/test_b649_min_s2_two_bonf5_owners_exact_composition_r1.py",
    "tests/unit/test_b649_min_s2_two_tied_owner_exact_cert_r1.py",
)
TARGETS = (
    "tests/unit/test_b649_min_s2_bonferroni5_target_cert_r1.py",
    "tests/unit/test_b649_min_s2_bonf5_tied_owners_cert_r1.py",
)
ISOLATED = (*EXISTING, *TARGETS)
UNRELATED = "tests/unit/test_unrelated_dispatch_fixture.py"


class Invocation(TypedDict):
    args: list[str]
    selected: list[str]
    pid: int


def _dispatch_script() -> str:
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
    marker = (
        "      - name: Run solver-free certificates and remaining tests in separate processes\n"
    )
    text = workflow.read_text()
    assert text.count(marker) == 1
    step = text.split(marker)[1]
    assert step.startswith("        run: |\n")
    lines: list[str] = []
    for line in step.splitlines(keepends=True)[1:]:
        if line.strip() and not line.startswith("          "):
            break
        lines.append(line)
    return dedent("".join(lines))


def _run_dispatch(
    tmp_path: Path, *, fail_path: str = "", absent_path: str = ""
) -> tuple[subprocess.CompletedProcess[str], list[Invocation]]:
    for path in (*ISOLATED, UNRELATED):
        if path != absent_path:
            fixture = tmp_path / path
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_text("# Dispatch fixture only; no scientific test is executed here.\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "uv"
    stub.write_text(
        f"#!{sys.executable}\n"
        + dedent(
            r"""
            import json
            import os
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            assert args[:2] == ["run", "pytest"], args
            explicit = [arg for arg in args[2:] if not arg.startswith("--")]
            ignored = {arg.removeprefix("--ignore=") for arg in args[2:]}
            selected = explicit or sorted(
                p.as_posix() for p in Path("tests").rglob("test_*.py")
                if p.as_posix() not in ignored
            )
            with Path(os.environ["DISPATCH_LOG"]).open("a") as log:
                log.write(json.dumps(
                    {"args": args, "selected": selected, "pid": os.getpid()}
                ) + "\n")
            sys.exit(23 if os.environ["DISPATCH_FAIL_PATH"] in selected else 0)
            """
        )
    )
    stub.chmod(0o755)
    log_path = tmp_path / "calls.jsonl"
    result = subprocess.run(
        ["/bin/bash", "-c", _dispatch_script()],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "DISPATCH_LOG": str(log_path),
            "DISPATCH_FAIL_PATH": fail_path,
        },
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    calls = [cast(Invocation, json.loads(line)) for line in log_path.read_text().splitlines()]
    return result, calls


def test_each_certificate_has_its_own_process_and_remainder_runs_once(tmp_path: Path) -> None:
    result, calls = _run_dispatch(tmp_path)
    assert result.returncode == 0, result.stderr
    assert [call["args"] for call in calls[:-1]] == [["run", "pytest", path] for path in ISOLATED]
    assert len({call["pid"] for call in calls}) == len(ISOLATED) + 1
    assert calls[-1]["args"] == ["run", "pytest", *(f"--ignore={path}" for path in ISOLATED)]
    assert calls[-1]["selected"] == [UNRELATED]
    assert [path for call in calls for path in call["selected"]] == [*ISOLATED, UNRELATED]


@pytest.mark.parametrize("fail_path", ISOLATED)
def test_certificate_failure_propagates_and_stops_dispatch(tmp_path: Path, fail_path: str) -> None:
    result, calls = _run_dispatch(tmp_path, fail_path=fail_path)
    assert result.returncode == 23, result.stderr
    attempted = ISOLATED[: ISOLATED.index(fail_path) + 1]
    assert [call["args"] for call in calls] == [["run", "pytest", path] for path in attempted]


@pytest.mark.parametrize("absent_path", TARGETS)
def test_absent_certificate_is_not_ignored(tmp_path: Path, absent_path: str) -> None:
    result, calls = _run_dispatch(tmp_path, absent_path=absent_path)
    assert result.returncode == 0, result.stderr
    present = [path for path in ISOLATED if path != absent_path]
    assert [call["args"] for call in calls[:-1]] == [["run", "pytest", path] for path in present]
    assert calls[-1]["args"] == ["run", "pytest", *(f"--ignore={path}" for path in present)]
    assert calls[-1]["selected"] == [UNRELATED]


def test_remainder_failure_propagates(tmp_path: Path) -> None:
    result, calls = _run_dispatch(tmp_path, fail_path=UNRELATED)
    assert result.returncode == 23, result.stderr
    assert len(calls) == len(ISOLATED) + 1
    assert calls[-1]["selected"] == [UNRELATED]
