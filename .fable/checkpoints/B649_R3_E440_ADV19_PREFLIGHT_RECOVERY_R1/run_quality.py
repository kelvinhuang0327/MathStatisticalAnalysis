"""Run the Packet's focused quality checks in the external Python3.13 environment."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path("/private/tmp/adv19-recovery-ea4ub0bv")
    repo = root / "testrepo"
    worktree = Path("/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/B649_R3_E440_ADV19_PREFLIGHT_RECOVERY_R1")
    assert sys.version_info[:2] == (3, 13)
    os.umask(0o077)
    measured_umask = os.umask(0o077)
    assert measured_umask == 0o077
    env = os.environ.copy()
    env.update({"LOTTOLAB_DATA_DIR": str(root / "app-data"), "TMPDIR": str(root / "tmp"),
                "TMP": str(root / "tmp"), "TEMP": str(root / "tmp"),
                "XDG_CACHE_HOME": str(root / "cache"), "XDG_DATA_HOME": str(root / "xdg-data"),
                "PYTHONPYCACHEPREFIX": str(root / "bytecode"), "PYTHONDONTWRITEBYTECODE": "1",
                "RUFF_CACHE_DIR": str(root / "cache/ruff"), "PYTHONPATH": str(repo / "src")})
    files = ["tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py",
             "tests/unit/test_b649_min_s2_t249_dual_profile_composition_r1.py",
             "tests/unit/test_b649_t249_collection_isolation_r1.py"]
    binary = Path(sys.executable).parent
    commands = [
        ("ruff", [str(binary / "ruff"), "check", "--no-cache", *files], repo),
        ("pyright", [str(binary / "pyright"), "--pythonpath", sys.executable, "--pythonversion", "3.13",
                     *files], repo),
        ("external-diff-check", ["git", "diff", "--check", "e440d4298551ce93ef3ea9a9226143784afa3eff"], repo),
        ("worktree-diff-check", ["git", "diff", "--check", "e440d4298551ce93ef3ea9a9226143784afa3eff"], worktree),
    ]
    only_pyright = "--only-pyright" in sys.argv
    if only_pyright:
        commands = [command for command in commands if command[0] == "pyright"]
    results = []
    for name, argv, cwd in commands:
        result = subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True)
        record = {"name": name, "argv": argv, "cwd": str(cwd), "exit_code": result.returncode,
                  "stdout": result.stdout, "stderr": result.stderr}
        results.append(record)
        print("QUALITY_RESULT=" + json.dumps(record, sort_keys=True), flush=True)
    summary = {"python": sys.executable, "python_version": sys.version,
               "measured_umask": format(measured_umask, "04o"),
               "launcher_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "results": results}
    filename = "quality-pyright-final.json" if only_pyright else "quality-summary.json"
    (root / filename).write_text(json.dumps(summary, indent=2) + "\n")
    return 0 if all(record["exit_code"] == 0 for record in results) else 1


if __name__ == "__main__":
    sys.exit(main())
