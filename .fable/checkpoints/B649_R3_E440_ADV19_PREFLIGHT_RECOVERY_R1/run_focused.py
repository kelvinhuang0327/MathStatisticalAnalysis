"""Measured external focused launcher; preserves all IDs, outcomes and child failures."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from xml.etree import ElementTree

ADVANCED = "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py"
T249 = "tests/unit/test_b649_min_s2_t249_dual_profile_composition_r1.py"
REPORT = ".git/worktrees/B649_MIN_S2_AB_T242_T241_EXACT_FAMILY_AUTHORITY_R1/task-evidence/fresh-judge-report.md"
REPORT_SHA = "216340c3d1cd2b7724571d95e4c7951d731fd48d04996dd10d53e83b98e12a3b"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--case", choices=["advanced", "combined"], default="advanced")
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--allow-missing-report", action="store_true")
    args = parser.parse_args()
    assert sys.version_info[:2] == (3, 13)
    assert args.name and all(c.isalnum() or c in "-_" for c in args.name)
    os.umask(0o077)
    root, repo = args.runtime.resolve(strict=True), args.repo.resolve(strict=True)
    assert root.is_relative_to(Path("/private/tmp")) and "b649" not in str(root).casefold()
    assert not root.is_relative_to(repo)
    common = Path(subprocess.check_output(["git", "-C", str(repo), "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True).strip())
    report = common.parent / REPORT
    report_sha = hashlib.sha256(report.read_bytes()).hexdigest() if report.is_file() else None
    if not args.allow_missing_report:
        assert report_sha == REPORT_SHA, "Authentic sealed Judge report is required before pytest"
    env = os.environ.copy()
    for name in ["PYTEST_ADDOPTS", "PYTEST_CURRENT_TEST", "ADV11_HISTORICAL_CHILD_CONTEXT",
                 "B649_T249_CHILD_CONTEXT", "B649_T249_ISOLATED_CHILD", "B649_T249_TEST_TEMP_ROOT",
                 "B649_T249_CHILD_REPORT_PATH", "B649_T249_PRELOAD_PARENT_RESEARCH",
                 "B649_T249_REVERSE_ORDER", "PYTEST_PLUGINS"]:
        env.pop(name, None)
    env.update({"LOTTOLAB_DATA_DIR": str(root / "app-data"),
                "TMPDIR": str(root / "tmp"), "TMP": str(root / "tmp"), "TEMP": str(root / "tmp"),
                "XDG_CACHE_HOME": str(root / "cache"), "XDG_DATA_HOME": str(root / "xdg-data"),
                "PYTHONPYCACHEPREFIX": str(root / "bytecode"), "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(repo / "src") + os.pathsep + str(repo / "tests/unit"),
                "RUFF_CACHE_DIR": str(root / "cache/ruff"), "UV_CACHE_DIR": str(root / "cache/uv"),
                "PIP_CACHE_DIR": str(root / "cache/pip")})
    for name in ["app-data", "tmp", "cache", "xdg-data", "bytecode"]:
        path = root / name
        path.mkdir(mode=0o700, exist_ok=True)
        assert path.stat().st_mode & 0o777 == 0o700
    if args.reverse:
        env["B649_T249_REVERSE_ORDER"] = "1"
    paths = [ADVANCED] if args.case == "advanced" else [ADVANCED, T249]
    command = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "-vv", "-rs", "--tb=short",
               f"--basetemp={root / ('pytest-' + args.name)}",
               f"--junitxml={root / (args.name + '.xml')}"]
    if args.reverse:
        normal = json.loads((root / "combined-normal.summary.json").read_text())
        command += list(reversed([case["nodeid"] for case in normal["cases"]]))
    else:
        command += paths
    measured = {name: env[name] for name in ["LOTTOLAB_DATA_DIR", "TMPDIR", "TMP", "TEMP", "XDG_CACHE_HOME", "XDG_DATA_HOME", "PYTHONPYCACHEPREFIX", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH"]}
    launch = {"cwd": str(repo), "python": sys.executable, "python_version": sys.version,
              "pytest_version": importlib.metadata.version("pytest"), "env": measured,
              "effective_umask": "0077", "app_data_mode": oct((root / "app-data").stat().st_mode & 0o777),
              "historical_report": str(report), "historical_report_sha256": report_sha,
              "argv": command, "reverse": args.reverse, "started_at": time.time()}
    (root / (args.name + ".launch.json")).write_text(json.dumps(launch, indent=2) + "\n")
    print("MEASURED_LAUNCH=" + json.dumps(launch, sort_keys=True), flush=True)
    result = subprocess.run(command, cwd=repo, env=env, text=True, capture_output=True)
    print(result.stdout, end="", flush=True)
    print(result.stderr, end="", file=sys.stderr, flush=True)
    cases = []
    xml = root / (args.name + ".xml")
    if xml.is_file():
        for case in ElementTree.parse(xml).getroot().iter("testcase"):
            status, detail = "passed", ""
            for tag in ["error", "failure", "skipped"]:
                node = case.find(tag)
                if node is not None:
                    status, detail = tag, node.attrib.get("message", "") + "\n" + (node.text or "")
                    break
            nodeid = case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]
            cases.append({"nodeid": nodeid, "outcome": status, "detail": detail})
    expected_count = 19 if args.case == "advanced" else 46
    summary = {"exit_code": result.returncode, "counts": {s: sum(c["outcome"] == s for c in cases) for s in ["passed", "failure", "error", "skipped"]}, "total": len(cases), "expected_count": expected_count, "cases": cases}
    (root / (args.name + ".summary.json")).write_text(json.dumps(summary, indent=2) + "\n")
    print("FOCUSED_SUMMARY=" + json.dumps({k: v for k, v in summary.items() if k != "cases"}, sort_keys=True), flush=True)
    return result.returncode or (0 if len(cases) == expected_count else 2)


if __name__ == "__main__":
    sys.exit(main())
