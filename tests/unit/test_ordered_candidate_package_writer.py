"""Adversarial atomic-writer tests for absent-root package sealing."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
    OrderedCandidateEmission,
)
from lottolab.domain.ordered_candidate_materialization import attempt_from_emission
from lottolab.evidence.canonical_json import sha256_hex
from lottolab.evidence.ordered_candidate_emission_artifact import (
    build_ordered_candidate_emission_artifact,
    serialize_ordered_candidate_emission_artifact,
)
from lottolab.evidence.ordered_candidate_emission_package import (
    OrderedCandidateEmissionFile,
    build_ordered_candidate_emission_package,
    sha256sums_bytes,
)
from lottolab.infrastructure import ordered_candidate_package_writer as writer_module
from lottolab.infrastructure.ordered_candidate_package_writer import (
    OrderedCandidatePackageCleanupError,
    OrderedCandidatePackageWriter,
    OrderedCandidatePackageWriterError,
)


def _package():
    emission = OrderedCandidateEmission(
        schema_version=ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="fixture_strategy",
        strategy_version="v1",
        replicate=1,
        target_draw="101",
        history_cutoff="100",
        emitted_main_numbers=(6, 1, 5, 2, 4, 3),
        auxiliary_operand_kind=AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
        auxiliary_operand_availability=(
            AuxiliaryOperandAvailability.EXPLICITLY_MISSING
        ),
        auxiliary_operand_value=None,
    )
    artifact = build_ordered_candidate_emission_artifact(emission)
    data = serialize_ordered_candidate_emission_artifact(artifact)
    file_hash = sha256_hex(data)
    attempt = attempt_from_emission(
        ordinal=0,
        target_ordinal=0,
        strategy_ordinal=0,
        emission=emission,
        emission_payload_sha256=artifact.payload_sha256,
        emission_file_sha256=file_hash,
    )
    assert attempt.emission_relative_path is not None
    emission_file = OrderedCandidateEmissionFile(
        relative_path=attempt.emission_relative_path,
        data=data,
        payload_sha256=artifact.payload_sha256,
        file_sha256=file_hash,
    )
    return build_ordered_candidate_emission_package(
        dataset_id="dataset",
        dataset_version="v1",
        source_snapshot_sha256_value="a" * 64,
        target_draws=("101",),
        strategy_ids=("fixture_strategy",),
        minimum_history_draws=1,
        maximum_history_draws=100,
        replicate=1,
        attempts=(attempt,),
        emission_files=(emission_file,),
    )


def _owner_parent(tmp_path: Path) -> Path:
    parent = tmp_path.resolve() / "owner-only"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    return parent


def test_seals_exact_tree_modes_and_checksums_then_never_mutates_again(
    tmp_path: Path,
) -> None:
    parent = _owner_parent(tmp_path)
    output = parent / "package"
    package = _package()

    OrderedCandidatePackageWriter().write_package(output, package)

    emission = output / package.emission_files[0].relative_path
    assert output.is_dir()
    assert (output / "manifest.json").read_bytes() == package.manifest_bytes
    assert emission.read_bytes() == package.emission_files[0].data
    assert (output / "SHA256SUMS").read_bytes() == sha256sums_bytes(package)
    for directory in [output, *[path for path in output.rglob("*") if path.is_dir()]]:
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    for file_path in [path for path in output.rglob("*") if path.is_file()]:
        assert stat.S_IMODE(file_path.stat().st_mode) == 0o600


@pytest.mark.parametrize("existing_name", ("package", ".package.p336-staging"))
def test_existing_final_or_staging_root_is_never_overwritten(
    tmp_path: Path,
    existing_name: str,
) -> None:
    parent = _owner_parent(tmp_path)
    existing = parent / existing_name
    existing.mkdir(mode=0o700)
    marker = existing / "owner.txt"
    marker.write_text("preserve", encoding="utf-8")

    with pytest.raises(OrderedCandidatePackageWriterError):
        OrderedCandidatePackageWriter().write_package(
            parent / "package",
            _package(),
        )

    assert marker.read_text(encoding="utf-8") == "preserve"


def test_symlink_parent_and_git_worktree_destinations_fail_closed(
    tmp_path: Path,
) -> None:
    real_parent = _owner_parent(tmp_path)
    link = tmp_path / "linked-parent"
    link.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(OrderedCandidatePackageWriterError):
        OrderedCandidatePackageWriter().write_package(
            link / "package",
            _package(),
        )
    with pytest.raises(OrderedCandidatePackageWriterError):
        OrderedCandidatePackageWriter().write_package(
            Path.cwd() / "forbidden-package",
            _package(),
        )

    assert not (real_parent / "package").exists()
    assert not (Path.cwd() / "forbidden-package").exists()


def test_failure_before_rename_removes_only_exact_recorded_task_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _owner_parent(tmp_path)
    output = parent / "package"
    staging = parent / ".package.p336-staging"

    def fail_rename(source: Path, destination: Path) -> None:
        assert source == staging
        assert destination == output
        raise OSError("injected rename failure")

    monkeypatch.setattr(os, "rename", fail_rename)

    with pytest.raises(OrderedCandidatePackageWriterError):
        OrderedCandidatePackageWriter().write_package(output, _package())

    assert not staging.exists()
    assert not output.exists()
    assert list(parent.iterdir()) == []


def test_unexpected_staging_content_stops_cleanup_without_deleting_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _owner_parent(tmp_path)
    output = parent / "package"
    staging = parent / ".package.p336-staging"
    original_value: object = getattr(writer_module, "_write_recorded_file", None)
    assert callable(original_value)
    original = cast(
        Callable[[Path, bytes, dict[Path, object]], None],
        original_value,
    )
    injected = False

    def inject_then_fail(
        path: Path,
        data: bytes,
        created: dict[Path, object],
    ) -> None:
        nonlocal injected
        original(path, data, created)
        if not injected:
            injected = True
            unexpected = staging / "unexpected"
            unexpected.write_bytes(b"foreign")
            raise OSError("injected post-write failure")

    monkeypatch.setattr(writer_module, "_write_recorded_file", inject_then_fail)

    with pytest.raises(OrderedCandidatePackageCleanupError):
        OrderedCandidatePackageWriter().write_package(output, _package())

    assert (staging / "unexpected").read_bytes() == b"foreign"
    assert not output.exists()
