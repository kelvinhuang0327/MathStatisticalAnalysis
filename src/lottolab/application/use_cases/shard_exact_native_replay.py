"""Use case: orchestrate the exact-native BIG_LOTTO replay across N parallel shards.

Canonicalizes the POST-PR231 ``orchestrator.py``/``shard_worker.py`` pair:
computes deterministic target-index shard boundaries, executes each shard
through the tracked ``lottolab replay-biglotto-exact-native-shard`` console
command (never a raw script path or ``python -m``), merges shard evidence
files by strict byte concatenation in ascending shard order, and re-verifies
the draw authority is byte-unchanged across the whole run.

Byte-concatenating ascending shards is equivalent to one direct call to
:func:`lottolab.application.use_cases.replay_exact_native_targets.replay_exact_native_target_range`
over the full ``[0, N)`` range: both iterate the same targets in the same
order against the same causal history, with no cross-shard state. Sharding
exists for wall-clock parallelism, not for a different result.
"""

from __future__ import annotations

import json
import math
import subprocess
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from lottolab.application.use_cases.replay_exact_native_targets import (
    DEFAULT_EXPECTED_MAIN_NUMBERS,
    DEFAULT_EXPECTED_SPECIAL_NUMBER,
    DEFAULT_MAX_VISIBLE_DRAW,
    ExactNativeReplayRuntimeError,
    catalog_freeze,
    load_authoritative_draws,
    source_freeze,
)
from lottolab.domain.exact_native_replay import (
    DEFAULT_NATIVE_TICKET_COUNTS,
    DEFAULT_WINDOW_ORDER,
    DEFAULT_WINDOW_SIZES,
    freeze_visible_draws,
)
from lottolab.domain.exact_native_replay import target_windows as compute_target_windows
from lottolab.evidence.exact_native_replay_manifest import (
    EVIDENCE_FILENAME,
    METADATA_FILENAME,
    build_sealed_manifest,
    sha256_file,
    write_json_file,
)


@dataclass(frozen=True, slots=True)
class ShardBoundary:
    shard_index: int
    start_index: int
    end_index: int


def compute_shard_boundaries(total_targets: int, shard_count: int) -> tuple[ShardBoundary, ...]:
    """Deterministic, non-overlapping, ascending target-index shard ranges."""

    if shard_count < 1:
        raise ExactNativeReplayRuntimeError("shard_count must be >= 1")
    boundaries: list[ShardBoundary] = []
    for index in range(shard_count):
        start_i = math.floor(index * total_targets / shard_count)
        end_i = math.floor((index + 1) * total_targets / shard_count)
        boundaries.append(ShardBoundary(shard_index=index, start_index=start_i, end_index=end_i))
    return tuple(boundaries)


@dataclass(frozen=True, slots=True)
class ShardExactNativeReplayRequest:
    run_id: str
    draw_authority_db: Path
    repository_root: Path
    output_root: Path
    shard_count: int
    native_ticket_counts: tuple[int, ...] = DEFAULT_NATIVE_TICKET_COUNTS
    max_visible_draw: str = DEFAULT_MAX_VISIBLE_DRAW
    expected_main_numbers: tuple[int, ...] | None = DEFAULT_EXPECTED_MAIN_NUMBERS
    expected_special_number: int | None = DEFAULT_EXPECTED_SPECIAL_NUMBER
    window_order: tuple[str, ...] = DEFAULT_WINDOW_ORDER
    window_sizes: Mapping[str, int | None] = field(
        default_factory=lambda: dict(DEFAULT_WINDOW_SIZES)
    )


@dataclass(frozen=True, slots=True)
class ShardExactNativeReplayResult:
    evidence_path: Path
    manifest_path: Path
    total_rows: int
    binding_count: int
    shard_boundaries: tuple[ShardBoundary, ...]
    evidence_sha256: str
    db_sha256_before: str
    db_sha256_after: str


def _shard_command(
    request: ShardExactNativeReplayRequest, boundary: ShardBoundary, shard_output_dir: Path
) -> list[str]:
    """The tracked console-script invocation for one shard -- never a raw script path."""

    command = [
        "uv",
        "run",
        "--directory",
        str(request.repository_root),
        "lottolab",
        "replay-biglotto-exact-native-shard",
        "--run-id",
        request.run_id,
        "--draw-authority-db",
        str(request.draw_authority_db),
        "--output-dir",
        str(shard_output_dir),
        "--start-index",
        str(boundary.start_index),
        "--end-index",
        str(boundary.end_index),
        "--max-visible-draw",
        request.max_visible_draw,
    ]
    for count in request.native_ticket_counts:
        command += ["--native-ticket-count", str(count)]
    if request.expected_main_numbers is not None:
        command += ["--expected-main-numbers", ",".join(map(str, request.expected_main_numbers))]
    if request.expected_special_number is not None:
        command += ["--expected-special-number", str(request.expected_special_number)]
    return command


def run_sharded_exact_native_replay(
    request: ShardExactNativeReplayRequest,
) -> ShardExactNativeReplayResult:
    """Execute ``shard_count`` parallel shards and merge them into one sealed evidence file."""

    request.output_root.mkdir(parents=True, exist_ok=True)
    shards_dir = request.output_root / "shards"
    shards_dir.mkdir(parents=True, exist_ok=True)

    source = source_freeze(request.repository_root)
    descriptors, catalog_universe = catalog_freeze(
        native_ticket_counts=request.native_ticket_counts
    )
    loaded_draws, draw_authority = load_authoritative_draws(request.draw_authority_db)
    all_draws = freeze_visible_draws(
        loaded_draws,
        max_visible_draw=request.max_visible_draw,
        expected_main_numbers=request.expected_main_numbers,
        expected_special_number=request.expected_special_number,
    )
    windows = compute_target_windows(
        all_draws, window_order=request.window_order, window_sizes=request.window_sizes
    )
    later_present = any(
        int(draw.draw_number) > int(request.max_visible_draw) for draw in loaded_draws
    )
    total_targets = len(all_draws)
    boundaries = compute_shard_boundaries(total_targets, request.shard_count)

    db_sha_before = sha256_file(request.draw_authority_db)

    processes: list[tuple[ShardBoundary, subprocess.Popen[bytes], Path]] = []
    for boundary in boundaries:
        shard_dir = shards_dir / f"shard_{boundary.shard_index:03d}"
        shard_dir.mkdir(parents=True, exist_ok=True)
        command = _shard_command(request, boundary, shard_dir)
        stdout_log = (shard_dir / "stdout.log").open("ab")
        stderr_log = (shard_dir / "stderr.log").open("ab")
        proc = subprocess.Popen(command, stdout=stdout_log, stderr=stderr_log)
        processes.append((boundary, proc, shard_dir))

    failures: list[tuple[int, int]] = []
    for boundary, proc, _shard_dir in processes:
        exit_code = proc.wait()
        if exit_code != 0:
            failures.append((boundary.shard_index, exit_code))
    if failures:
        raise ExactNativeReplayRuntimeError(f"SHARD_EXECUTION_FAILURE: {failures}")

    shard_evidence_files: list[Path] = []
    total_rows = 0
    global_status: Counter[str] = Counter()
    binding_count = 0
    for boundary, _proc, shard_dir in processes:
        evidence_file = shard_dir / EVIDENCE_FILENAME
        metadata_file = shard_dir / METADATA_FILENAME
        if not evidence_file.is_file() or not metadata_file.is_file():
            raise ExactNativeReplayRuntimeError(
                f"shard {boundary.shard_index} missing required output files"
            )
        meta = cast(dict[str, object], json.loads(metadata_file.read_text(encoding="utf-8")))
        binding_count = cast(int, meta["binding_count"])
        expected_shard_rows = (boundary.end_index - boundary.start_index) * binding_count
        actual_line_count = 0
        with evidence_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                actual_line_count += 1
                row = json.loads(line)
                global_status[row["replay_status"]] += 1
        if actual_line_count != expected_shard_rows:
            raise ExactNativeReplayRuntimeError(
                f"shard {boundary.shard_index} evidence line count mismatch: "
                f"expected {expected_shard_rows}, got {actual_line_count}"
            )
        total_rows += actual_line_count
        shard_evidence_files.append(evidence_file)

    merged_path = request.output_root / EVIDENCE_FILENAME
    with merged_path.open("wb") as outfile:
        for evidence_file in shard_evidence_files:
            with evidence_file.open("rb") as infile:
                while True:
                    chunk = infile.read(1024 * 1024)
                    if not chunk:
                        break
                    outfile.write(chunk)

    db_sha_after = sha256_file(request.draw_authority_db)
    if db_sha_after != db_sha_before:
        raise ExactNativeReplayRuntimeError("CANONICAL_DB_IDENTITY_CHANGED")

    evidence_sha256 = sha256_file(merged_path)
    evidence_byte_size = merged_path.stat().st_size

    manifest = build_sealed_manifest(
        run_id=request.run_id,
        source=source,
        catalog=catalog_universe,
        draw_authority=draw_authority,
        max_visible_draw=request.max_visible_draw,
        later_draws_present_in_authority=later_present,
        visible_draw_count=total_targets,
        target_windows=windows,
        shard_count=request.shard_count,
        shard_boundaries=[
            {
                "shard_index": b.shard_index,
                "start_target_index": b.start_index,
                "end_target_index": b.end_index,
            }
            for b in boundaries
        ],
        evidence_sha256=evidence_sha256,
        evidence_byte_size=evidence_byte_size,
        evidence_record_count=total_rows,
        evidence_status_counts=dict(global_status),
        universe={
            "attempted_strategy_count": len(descriptors),
            "attempted_target_count_per_strategy": total_targets,
            "attempted_cell_count": total_rows,
        },
    )
    manifest_path = request.output_root / "sealed_manifest.json"
    write_json_file(manifest_path, manifest)

    return ShardExactNativeReplayResult(
        evidence_path=merged_path,
        manifest_path=manifest_path,
        total_rows=total_rows,
        binding_count=binding_count,
        shard_boundaries=boundaries,
        evidence_sha256=evidence_sha256,
        db_sha256_before=db_sha_before,
        db_sha256_after=db_sha_after,
    )


__all__ = [
    "ShardBoundary",
    "ShardExactNativeReplayRequest",
    "ShardExactNativeReplayResult",
    "compute_shard_boundaries",
    "run_sharded_exact_native_replay",
]
