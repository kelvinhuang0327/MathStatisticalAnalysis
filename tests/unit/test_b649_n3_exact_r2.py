"""Production native solver parity, admissibility, and controlled falsification."""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/lottolab/research/b649_n3_exact"


def build_and_run(tmp_path: Path, mutation: str | None = None) -> subprocess.CompletedProcess[str]:
    binary = tmp_path / "n3-toy"
    argv = ["clang", "-std=c11", "-O2", "-DNT6=12", "-I", str(SOURCE)]
    if mutation:
        argv.append(f"-D{mutation}")
    argv.extend(
        str(p)
        for p in (
            ROOT / "tests/native/b649_n3_toy.c",
            SOURCE / "n3_solve.c",
            SOURCE / "n3_solve_legacy.c",
        )
    )
    subprocess.run([*argv, "-o", str(binary)], check=True, capture_output=True, text=True)
    return subprocess.run([str(binary)], capture_output=True, text=True, timeout=45, check=False)


def test_exhaustive_brute_parity_bounds_cache_collisions_and_frontier(tmp_path: Path) -> None:
    result = build_and_run(tmp_path)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["BRUTE_CASES"] == 1200
    assert evidence["OLD_NEW_PARITY_CASES"] > 100
    assert evidence["BOUND_CHECKS"] == 1_188_000
    assert evidence["FRONTIER_CHECKS"] == 2400
    assert evidence["ZERO_INCUMBENT_CASES"] > 0
    assert evidence["MISMATCHES"] == 0
    print(json.dumps(evidence, sort_keys=True))


@pytest.mark.parametrize(
    ("mutation", "diagnostic"),
    [
        ("MUTANT_CONDITIONAL_BOUND", "BOUND_INADMISSIBLE"),
        ("MUTANT_PRUNE_EQUAL", "BRUTE_PARITY_MISMATCH"),
        ("MUTANT_CACHE_VALUE", "BRUTE_PARITY_MISMATCH"),
        ("MUTANT_SUFFIX_CUTOFF", "BRUTE_PARITY_MISMATCH"),
    ],
)
def test_mutations_are_rejected(tmp_path: Path, mutation: str, diagnostic: str) -> None:
    result = build_and_run(tmp_path, mutation)
    assert result.returncode != 0, "An invalid bound/cache/pruning rule escaped detection"
    assert diagnostic in result.stderr
    print(f"{mutation}: rejected: {result.stderr.strip()}")
    restored = build_and_run(tmp_path)
    assert restored.returncode == 0, restored.stderr


@pytest.mark.parametrize(
    "mutation", [None, "MUTANT_SHARED_LOWER_BOUND", "MUTANT_GEOMETRIC_LOWER_BOUND"]
)
def test_actual_lottery_overlap_lower_bound(tmp_path: Path, mutation: str | None) -> None:
    binary = tmp_path / "lower-toy"
    argv = ["clang", "-std=c11", "-O2", "-DNPOOL=12", "-I", str(SOURCE)]
    if mutation:
        argv.append(f"-D{mutation}")
    argv.extend(
        str(p)
        for p in (
            ROOT / "tests/native/b649_n3_lower_toy.c",
            SOURCE / "n3_lower.c",
            SOURCE / "n3_core.c",
        )
    )
    subprocess.run([*argv, "-o", str(binary)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=45, check=False)
    if mutation:
        assert result.returncode != 0
        assert "SHARED_BOUND_INADMISSIBLE" in result.stderr
        print(f"{mutation}: rejected: {result.stderr.strip()}")
    else:
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["LOTTERY_LOWER_BOUND_CHECKS"] == 80_000
        print(result.stdout.strip())


def test_full_pool49_geometric_counts_against_existing_exact_kernel(tmp_path: Path) -> None:
    binary = tmp_path / "full-geometry"
    argv = ["clang", "-std=c11", "-O2", "-I", str(SOURCE)]
    argv.extend(
        str(p)
        for p in (
            ROOT / "tests/native/b649_n3_geometry_full.c",
            SOURCE / "n3_lower.c",
            SOURCE / "n3_core.c",
            SOURCE / "n3_overlap.c",
        )
    )
    subprocess.run([*argv, "-o", str(binary)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=45, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["POOL49_GEOMETRY_CHECKS"] == 80
    print(result.stdout.strip())
