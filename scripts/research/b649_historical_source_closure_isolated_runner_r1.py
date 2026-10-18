#!/usr/bin/env python3
"""Isolated pytest runner for historical sealed research test modules.

Prevents cross-test Python module pollution (e.g. sys.modules contamination)
between Group 6 (b649_min_s2_t249_dual_profile_composition_r1) and
Group 7 (b649_min_s2_two_tied_owner_exact_cert_r1) without modifying historical
source files, changing sealed results, or mutating any of the 28 SOURCE_PINS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypedDict, cast

TASK_ID = "B649_HISTORICAL_RESEARCH_CLOSURE_ISOLATION_R1"

SEALED_T249_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-min-s2-t249-dual-profile-composition-r1-result.json"
)
SEALED_TWO_TIED_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-min-s2-two-tied-owner-exact-cert-r1-result.json"
)

GROUP6_TEST_PATH = "tests/unit/test_b649_min_s2_t249_dual_profile_composition_r1.py"
GROUP7_TEST_PATH = "tests/unit/test_b649_min_s2_two_tied_owner_exact_cert_r1.py"

GROUP6_SOURCE_PATH = "src/lottolab/research/b649_min_s2_t249_dual_profile_composition_r1.py"
GROUP7_SOURCE_PATH = "src/lottolab/research/b649_min_s2_two_tied_owner_exact_cert_r1.py"

EXPECTED_SEALED_PIN_COUNT = 28
PREVIOUS_PACKET_ASSUMED_COUNT = 7

SEALED_BASE_HEAD = "d0785605aefeff33d55d2763e9e8660ba298762d"
SEALED_BASE_TREE = "d6e08905b87f1e8208ac7fe892f5b51278e1a9f7"

PIN_SEMANTIC_RESOLUTION = (
    "The previous Packet's value 7 was its asserted Group 6 runtime helper-closure count; "
    "it is not the sealed T249 result's source inventory. The sealed result stores 28 "
    "path-to-SHA identities under PROVENANCE.SOURCE_PINS. Runtime-loaded Research modules "
    "are measured from each isolated pytest child's sys.modules after the original tests run "
    "and are reported separately; neither runtime observation redefines the sealed pins."
)

RUNTIME_LOADED_HELPERS_MARKER = "RUNTIME_LOADED_HELPERS_JSON="


class RuntimeLoadedModule(TypedDict):
    module: str
    path: str
    inside_worktree: bool


class RuntimeLoadedHelpersRecord(TypedDict):
    process_id: int
    pytest_exit_code: int
    modules: list[RuntimeLoadedModule]


_ISOLATED_PYTEST_DRIVER = r"""
import json
import os
import sys
from pathlib import Path

import pytest

pytest_status = int(pytest.main(sys.argv[1:]))
root = Path.cwd().resolve()
modules = []
for name, module in sorted(sys.modules.copy().items()):
    if not name.startswith("lottolab.research."):
        continue
    source = getattr(module, "__file__", None)
    if source is None:
        continue
    source_path = Path(source).resolve()
    try:
        relative_path = source_path.relative_to(root).as_posix()
        inside_worktree = True
    except ValueError:
        relative_path = str(source_path)
        inside_worktree = False
    modules.append({"module": name, "path": relative_path, "inside_worktree": inside_worktree})

payload = {
    "process_id": os.getpid(),
    "pytest_exit_code": pytest_status,
    "modules": modules,
}
print("RUNTIME_LOADED_HELPERS_JSON=" + json.dumps(payload, sort_keys=True, separators=(",", ":")))
raise SystemExit(pytest_status)
"""

SEALED_28_PINS: tuple[str, ...] = (
    "src/lottolab/research/b649_k20_min_s2_class_dominance_or_descent_r13.py",
    "src/lottolab/research/b649_k20_min_s2_closed_form_owner_plateau_r31.py",
    "src/lottolab/research/b649_k20_min_s2_continued_multi_plateau_descent_r12.py",
    "src/lottolab/research/b649_k20_min_s2_current_bound_owner_refinement_r15.py",
    "src/lottolab/research/b649_k20_min_s2_current_cursor_class_owner_chase_r28.py",
    "src/lottolab/research/b649_k20_min_s2_current_cursor_dynamic_family_max_r30.py",
    "src/lottolab/research/b649_k20_min_s2_cursor_plateau_closure_r18.py",
    "src/lottolab/research/b649_k20_min_s2_dangerous_core_realizability_r5.py",
    "src/lottolab/research/b649_k20_min_s2_higher_order_closure_r2.py",
    "src/lottolab/research/b649_k20_min_s2_load_bearing_plateau_descent_r16.py",
    "src/lottolab/research/b649_k20_min_s2_nb_degree_cap_frontier_r1.py",
    "src/lottolab/research/b649_k20_min_s2_nb_w807_w786_batch_certificate_r1.py",
    "src/lottolab/research/b649_k20_min_s2_nb_w808_frontier_r1.py",
    "src/lottolab/research/b649_k20_min_s2_next_active_profile_exact_bound_r8.py",
    "src/lottolab/research/b649_k20_min_s2_next_distinct_plateau_r10.py",
    "src/lottolab/research/b649_k20_min_s2_r16_freeze_and_owner_refinement_r17.py",
    "src/lottolab/research/b649_k20_min_s2_realizable_core_class_bound_r4.py",
    "src/lottolab/research/b649_k20_min_s2_resolved_above_cursor_owner_chase_r20.py",
    "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py",
    "src/lottolab/research/b649_k20_min_s2_six_owner_batch_refinement_r26.py",
    "src/lottolab/research/b649_k20_min_s2_six_owner_cursor_crossover_r26.py",
    "src/lottolab/research/b649_k20_min_s2_ss332_owner_class_to_cursor_r29.py",
    "src/lottolab/research/b649_k20_min_s2_successive_class_dominance_r14.py",
    "src/lottolab/research/b649_k20_min_s2_topw12_coverage_repair_r1.py",
    "src/lottolab/research/b649_k20_min_s2_topw12_split_cap_certificate_r1.py",
    "src/lottolab/research/b649_min_s2_three_tied_owner_combined_authority_r1.py",
    "src/lottolab/research/b649_min_s2_two_tied_owner_exact_cert_r1.py",
    "src/lottolab/research/b649_official_any_prize_exact.py",
)


def get_repo_root() -> Path:
    """Return the repository / worktree root path."""
    return Path(__file__).resolve().parents[2]


def load_sealed_source_inventory(root: Path | None = None) -> dict[str, str]:
    """Load the exact path-to-SHA inventory from the sealed T249 result."""
    root_path = root or get_repo_root()
    sealed_result_file = root_path / SEALED_T249_RESULT_PATH
    if not sealed_result_file.is_file():
        raise FileNotFoundError(f"Sealed T249 result not found at {sealed_result_file}")

    parsed_result: object = json.loads(sealed_result_file.read_bytes())
    if not isinstance(parsed_result, dict):
        raise ValueError("Sealed T249 result must be a JSON object")
    result_data = cast(dict[str, object], parsed_result)
    provenance_value = result_data.get("PROVENANCE")
    if not isinstance(provenance_value, dict):
        raise ValueError("Sealed T249 result PROVENANCE must be an object")
    provenance = cast(dict[str, object], provenance_value)
    source_pins_value = provenance.get("SOURCE_PINS")
    if not isinstance(source_pins_value, dict):
        raise ValueError("Sealed PROVENANCE.SOURCE_PINS must be an object")
    source_pins: dict[str, str] = {}
    for path, digest in cast(dict[object, object], source_pins_value).items():
        if not isinstance(path, str) or not isinstance(digest, str):
            raise ValueError("Sealed SOURCE_PINS entries must map source paths to SHA-256 strings")
        source_pins[path] = digest
    return source_pins


def explain_pin_count_semantics(root: Path | None = None) -> dict[str, object]:
    """Return the sealed inventory and distinguish it from runtime module observations."""
    source_pins = load_sealed_source_inventory(root)
    inventory = [{"path": path, "sha256": digest} for path, digest in sorted(source_pins.items())]
    return {
        "SEALED_SOURCE_PIN_COUNT": EXPECTED_SEALED_PIN_COUNT,
        "SEALED_SOURCE_INVENTORY_COUNT": len(source_pins),
        "SEALED_SOURCE_INVENTORY": inventory,
        "PREVIOUS_PACKET_ASSUMED_COUNT": PREVIOUS_PACKET_ASSUMED_COUNT,
        "PREVIOUS_PACKET_ASSUMPTION_SEMANTICS": (
            "The earlier Packet's asserted runtime helper-closure count for Group 6; "
            "it is not a count read from the sealed result's SOURCE_PINS field."
        ),
        "SEALED_SOURCE_FIELD_SEMANTICS": (
            "PROVENANCE.SOURCE_PINS is the sealed T249 result's immutable source-path to "
            "SHA-256 map."
        ),
        "RUNTIME_LOADED_HELPERS_SEMANTICS": (
            "Measured independently in each isolated pytest subprocess from file-backed "
            "lottolab.research modules remaining in sys.modules after the original tests."
        ),
        "STATUS": "RESOLVED",
        "RESOLUTION_SUMMARY": PIN_SEMANTIC_RESOLUTION,
        "PINNED_INVENTORY_COUNT": len(source_pins),
        "PINS": inventory,
    }


def verify_sealed_pin_inventory(root: Path | None = None) -> dict[str, str]:
    """Verify that all 28 sealed SOURCE_PINS exist and match disk and git blob bytes."""
    root_path = root or get_repo_root()
    sealed_result_file = root_path / SEALED_T249_RESULT_PATH

    if not sealed_result_file.exists():
        raise FileNotFoundError(f"Sealed T249 result not found at {sealed_result_file}")

    source_pins = load_sealed_source_inventory(root_path)

    if len(source_pins) != EXPECTED_SEALED_PIN_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_SEALED_PIN_COUNT} sealed SOURCE_PINS, but found {len(source_pins)}"
        )

    if tuple(sorted(source_pins.keys())) != tuple(sorted(SEALED_28_PINS)):
        raise ValueError("Sealed SOURCE_PINS keys differ from expected canonical inventory")

    for rel_path, expected_sha in source_pins.items():
        file_path = root_path / rel_path
        if not file_path.is_file():
            raise FileNotFoundError(f"Pinned file does not exist on disk: {rel_path}")

        file_bytes = file_path.read_bytes()
        actual_sha = hashlib.sha256(file_bytes).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(
                f"Disk hash mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}"
            )

        historical_blob_id = subprocess.check_output(
            ["git", "rev-parse", f"{SEALED_BASE_HEAD}:{rel_path}"],
            cwd=root_path,
            text=True,
        ).strip()
        disk_blob_id = hashlib.sha1(
            f"blob {len(file_bytes)}\0".encode("ascii") + file_bytes
        ).hexdigest()
        if disk_blob_id != historical_blob_id:
            raise ValueError(
                f"Git blob mismatch for {rel_path}: expected {historical_blob_id}, "
                f"got {disk_blob_id}"
            )

        git_blob = subprocess.check_output(
            ["git", "-c", "core.fsmonitor=false", "show", f"{SEALED_BASE_HEAD}:{rel_path}"],
            cwd=root_path,
        )
        if file_bytes != git_blob:
            raise ValueError(f"Disk bytes do not match git blob at {SEALED_BASE_HEAD}:{rel_path}")

    return source_pins


def run_isolated_pytest(
    test_path: str | Path,
    extra_args: Sequence[str] | None = None,
    cwd: Path | None = None,
    env_override: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute a single test target in a dedicated, isolated Python pytest subprocess."""
    root_path = cwd or get_repo_root()
    test_rel = str(test_path)

    cmd = [
        sys.executable,
        "-c",
        _ISOLATED_PYTEST_DRIVER,
        test_rel,
        "-p",
        "no:cacheprovider",
        *(extra_args or []),
    ]

    run_env = os.environ.copy()
    existing_pythonpath = run_env.get("PYTHONPATH", "")
    src_dir = str(root_path / "src")
    if existing_pythonpath:
        run_env["PYTHONPATH"] = os.pathsep.join((src_dir, existing_pythonpath))
    else:
        run_env["PYTHONPATH"] = src_dir
    run_env["PYTHONDONTWRITEBYTECODE"] = "1"

    if env_override:
        run_env.update(env_override)

    proc = subprocess.run(
        cmd,
        cwd=root_path,
        env=run_env,
        capture_output=True,
        text=True,
    )
    return proc


def extract_runtime_loaded_helpers(stdout: str) -> RuntimeLoadedHelpersRecord:
    """Parse the actual file-backed Research module inventory emitted by a child."""
    marker_lines = [
        line for line in stdout.splitlines() if line.startswith(RUNTIME_LOADED_HELPERS_MARKER)
    ]
    if len(marker_lines) != 1:
        raise ValueError(
            f"Expected one {RUNTIME_LOADED_HELPERS_MARKER} record, found {len(marker_lines)}"
        )
    payload_value: object = json.loads(marker_lines[0][len(RUNTIME_LOADED_HELPERS_MARKER) :])
    if not isinstance(payload_value, dict):
        raise ValueError("Runtime helper record must be a JSON object")
    payload = cast(dict[str, object], payload_value)
    process_id = payload.get("process_id")
    pytest_exit_code = payload.get("pytest_exit_code")
    modules_value = payload.get("modules")
    if type(process_id) is not int:
        raise ValueError("Runtime helper record is missing an integer process_id")
    if type(pytest_exit_code) is not int:
        raise ValueError("Runtime helper record is missing an integer pytest_exit_code")
    if not isinstance(modules_value, list):
        raise ValueError("Runtime helper record contains malformed module identities")

    modules: list[RuntimeLoadedModule] = []
    for entry_value in cast(list[object], modules_value):
        if not isinstance(entry_value, dict):
            raise ValueError("Runtime helper record contains a non-object module identity")
        entry = cast(dict[str, object], entry_value)
        module_name = entry.get("module")
        path = entry.get("path")
        inside_worktree = entry.get("inside_worktree")
        if (
            not isinstance(module_name, str)
            or not isinstance(path, str)
            or not isinstance(inside_worktree, bool)
        ):
            raise ValueError("Runtime helper record contains malformed module identities")
        modules.append({"module": module_name, "path": path, "inside_worktree": inside_worktree})
    return {
        "process_id": process_id,
        "pytest_exit_code": pytest_exit_code,
        "modules": modules,
    }


def run_group6(
    extra_args: Sequence[str] | None = None, root: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run Group 6 tests in an isolated pytest subprocess."""
    return run_isolated_pytest(GROUP6_TEST_PATH, extra_args=extra_args, cwd=root)


def run_group7(
    extra_args: Sequence[str] | None = None, root: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run Group 7 tests in an isolated pytest subprocess."""
    return run_isolated_pytest(GROUP7_TEST_PATH, extra_args=extra_args, cwd=root)


def run_isolated_suite(
    order: Sequence[str] = ("group6", "group7"),
    extra_args: Sequence[str] | None = None,
    root: Path | None = None,
) -> dict[str, subprocess.CompletedProcess[str]]:
    """Run Group 6 and Group 7 in separate isolated subprocesses in the specified order."""
    results: dict[str, subprocess.CompletedProcess[str]] = {}
    for group in order:
        group_norm = group.strip().lower()
        if group_norm == "group6":
            results["group6"] = run_group6(extra_args=extra_args, root=root)
        elif group_norm == "group7":
            results["group7"] = run_group7(extra_args=extra_args, root=root)
        else:
            raise ValueError(f"Unknown group '{group}', expected 'group6' or 'group7'")
    return results


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for running historical research test modules in isolation."""
    parser = argparse.ArgumentParser(
        description="Isolated subprocess runner for historical sealed research tests"
    )
    parser.add_argument(
        "--order",
        default="group6,group7",
        help="Comma-separated execution order (e.g. 'group6,group7' or 'group7,group6')",
    )
    parser.add_argument(
        "--check-pins",
        action="store_true",
        help="Verify all 28 sealed SOURCE_PINS against disk and Git blob before running",
    )
    parser.add_argument(
        "--explain-semantics",
        action="store_true",
        help="Print the semantic distinction between 28 sealed pins and 7 assumption and exit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print stdout and stderr from subprocess test runs",
    )

    args, extra = parser.parse_known_args(argv)

    if args.explain_semantics:
        explanation = explain_pin_count_semantics()
        print(json.dumps(explanation, indent=2))
        return 0

    try:
        verified = verify_sealed_pin_inventory()
    except Exception as exc:
        print(f"ERROR verifying sealed pin inventory: {exc}", file=sys.stderr)
        return 1

    sealed_inventory = [
        {"path": path, "sha256": digest} for path, digest in sorted(verified.items())
    ]
    print(f"SEALED_SOURCE_INVENTORY_COUNT={len(sealed_inventory)}")
    print(
        "SEALED_SOURCE_INVENTORY_JSON="
        + json.dumps(sealed_inventory, sort_keys=True, separators=(",", ":"))
    )

    order = [item.strip() for item in args.order.split(",") if item.strip()]
    results = run_isolated_suite(order=order, extra_args=extra)

    failed = False
    for group_name, proc in results.items():
        status_str = "PASS" if proc.returncode == 0 else f"FAIL (exit {proc.returncode})"
        print(f"[{group_name.upper()}] Pytest subprocess status: {status_str}")
        try:
            runtime = extract_runtime_loaded_helpers(proc.stdout)
            modules = runtime["modules"]
            print(f"[{group_name.upper()}] RUNTIME_LOADED_HELPERS_COUNT={len(modules)}")
            print(
                f"[{group_name.upper()}] RUNTIME_LOADED_HELPERS_JSON="
                + json.dumps(runtime, sort_keys=True, separators=(",", ":"))
            )
            if any(not entry["inside_worktree"] for entry in modules):
                print(
                    f"[{group_name.upper()}] Runtime Research module resolved outside worktree",
                    file=sys.stderr,
                )
                failed = True
            if runtime["pytest_exit_code"] != proc.returncode:
                print(f"[{group_name.upper()}] Reported pytest exit code mismatch", file=sys.stderr)
                failed = True
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"[{group_name.upper()}] Runtime inventory unavailable: {exc}", file=sys.stderr)
            failed = True
        visible_stdout = "\n".join(
            line
            for line in proc.stdout.splitlines()
            if not line.startswith(RUNTIME_LOADED_HELPERS_MARKER)
        )
        if visible_stdout:
            print(visible_stdout)
        if proc.stderr and (args.verbose or proc.returncode != 0):
            print(proc.stderr, file=sys.stderr)
        if proc.returncode != 0:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
