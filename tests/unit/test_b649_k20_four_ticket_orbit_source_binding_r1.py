from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from lottolab.research import b649_k20_four_ticket_orbit_source_binding_r1 as source_binding


def test_dependency_path_and_hash_are_pinned() -> None:
    resolved = source_binding._require_authorized_path(
        source_binding.ARCHIVED_DEPENDENCY_PATH,
        source_binding.ARCHIVED_DEPENDENCY_PATH,
        "ARCHIVED_THREE_TICKET_DEPENDENCY",
    )
    payload = source_binding._stable_bytes(resolved, "ARCHIVED_THREE_TICKET_DEPENDENCY")

    assert resolved == source_binding.ARCHIVED_DEPENDENCY_PATH
    assert (
        source_binding._verify_sha256(
            payload,
            source_binding.ARCHIVED_DEPENDENCY_SHA256,
            "ARCHIVED_THREE_TICKET_DEPENDENCY",
        )
        == source_binding.ARCHIVED_DEPENDENCY_SHA256
    )


def test_wrong_module_path_fails_closed() -> None:
    with pytest.raises(source_binding.SourceBindingError, match="WRONG_MODULE_PATH"):
        source_binding._require_authorized_path(
            Path(__file__),
            source_binding.ARCHIVED_DEPENDENCY_PATH,
            "ARCHIVED_THREE_TICKET_DEPENDENCY",
        )


def test_wrong_source_hash_fails_closed() -> None:
    payload = source_binding._stable_bytes(
        source_binding.ARCHIVED_DEPENDENCY_PATH, "ARCHIVED_THREE_TICKET_DEPENDENCY"
    )

    with pytest.raises(source_binding.SourceBindingError, match="SHA256_MISMATCH"):
        source_binding._verify_sha256(
            payload,
            "0" * 64,
            "ARCHIVED_THREE_TICKET_DEPENDENCY",
        )


def test_tampered_dependency_bytes_fail_closed() -> None:
    payload = bytearray(
        source_binding._stable_bytes(
            source_binding.ARCHIVED_DEPENDENCY_PATH, "ARCHIVED_THREE_TICKET_DEPENDENCY"
        )
    )
    payload[len(payload) // 2] ^= 1

    with pytest.raises(source_binding.SourceBindingError, match="SHA256_MISMATCH"):
        source_binding._verify_sha256(
            bytes(payload),
            source_binding.ARCHIVED_DEPENDENCY_SHA256,
            "ARCHIVED_THREE_TICKET_DEPENDENCY",
        )


def test_relocated_successor_import_binds_original_predicate_without_solver() -> None:
    script = r"""
import hashlib
import importlib
from pathlib import Path

binding = importlib.import_module(
    "lottolab.research.b649_k20_four_ticket_orbit_source_binding_r1"
)
evidence = binding.load_original_predicate_for_successor()

assert Path(binding.__file__).resolve() == evidence.binding_module_path
assert (
    hashlib.sha256(evidence.binding_module_path.read_bytes()).hexdigest()
    == evidence.binding_module_sha256
)
assert evidence.binding_module_path.is_relative_to(binding.SUCCESSOR_WORKTREE)
assert evidence.dependency_module.__name__ == binding.DEPENDENCY_IMPORT_NAME
assert Path(evidence.dependency_module.__file__).resolve() == evidence.dependency_path
assert evidence.dependency_path == binding.ARCHIVED_DEPENDENCY_PATH
assert evidence.dependency_sha256 == binding.ARCHIVED_DEPENDENCY_SHA256
assert evidence.predicate_module.ttc is evidence.dependency_module
assert evidence.predicate_path == binding.FROZEN_PREDICATE_PATH
assert evidence.predicate_sha256 == binding.FROZEN_PREDICATE_SHA256
assert evidence.driver_path == binding.ORIGINAL_DRIVER_PATH
assert evidence.driver_sha256 == binding.ORIGINAL_DRIVER_SHA256
assert evidence.driver_module.TTC == binding.ARCHIVED_DEPENDENCY_PATH
assert evidence.driver_module.REPO == binding.CANONICAL_REPOSITORY
assert evidence.official_path == binding.OFFICIAL_SOURCE_PATH
assert evidence.official_sha256 == binding.OFFICIAL_SOURCE_SHA256
assert evidence.execution_stage == "PREDICATE_IMPORTED_NO_SOLVER"
print("PASS: relocated binding imported the frozen predicate; solver not called")
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(source_binding.SUCCESSOR_WORKTREE / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=source_binding.SUCCESSOR_WORKTREE,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert completed.stdout.strip() == (
        "PASS: relocated binding imported the frozen predicate; solver not called"
    )
