"""Durable exact-anchor checkpoint and resume behavior on a synthetic N3 case."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/lottolab/research/b649_n3_exact"


def build(tmp_path: Path) -> Path:
    binary = tmp_path / "n3-resume-toy"
    subprocess.run(
        [
            "clang",
            "-std=c11",
            "-O2",
            "-DNT6=12",
            "-I",
            str(SOURCE),
            str(ROOT / "tests/native/b649_n3_resume_toy.c"),
            str(SOURCE / "n3_checkpoint.c"),
            str(SOURCE / "n3_solve.c"),
            str(SOURCE / "n3_solve_legacy.c"),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return binary


def invoke(binary: Path, mode: str, checkpoint: Path | None = None) -> dict:
    argv = [str(binary), mode]
    if checkpoint is not None:
        argv.append(str(checkpoint))
    result = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_uninterrupted_interrupted_resume_equivalence_and_fail_closed(tmp_path: Path) -> None:
    binary = build(tmp_path)
    checkpoint = tmp_path / "anchors.jsonl"

    uninterrupted = invoke(binary, "full")
    interrupted = invoke(binary, "partial", checkpoint)
    assert interrupted["CLOSED"] is False
    assert interrupted["CHECKPOINT_ANCHORS_RECORDED"] == 1

    lines = checkpoint.read_text().splitlines()
    metadata = lines[0].split("|")
    assert metadata[0] == "N3RESUME1"
    assert metadata[1] == "DESTROY_SET=0000000000000001,0000000000000002,0000000000000004"
    assert metadata[2] == f"TOTAL_ANCHORS={interrupted['A_BOUND_COUNT']}"
    assert metadata[3] == "F0=0"
    assert metadata[4].startswith("INPUT_SHA256=")
    assert metadata[5].startswith("ENGINE_SHA256=")
    assert metadata[6].startswith("SOLVER_CONFIG_SHA256=")
    assert len(metadata) == 8
    assert metadata[7] == "JOURNAL_PREFIX_SHA256=" + hashlib.sha256(
        "|".join(metadata[:7]).encode()
    ).hexdigest()

    resumed = invoke(binary, "resume", checkpoint)
    assert resumed["CLOSED"] is True
    assert resumed["BEST_F"] == uninterrupted["BEST_F"]
    assert resumed["TIE_COUNT"] == uninterrupted["TIE_COUNT"]
    assert resumed["TIES"] == uninterrupted["TIES"]
    assert resumed["TRIPLES_ACCOUNTED"] == uninterrupted["TRIPLES_ACCOUNTED"]
    assert resumed["CHECKPOINT_ANCHORS_RECORDED"] == resumed["A_BOUND_COUNT"]
    assert resumed["A_EXPLORED"] > 0

    all_lines = checkpoint.read_text().splitlines()
    records = [line.split("|") for line in all_lines[1:]]
    anchor_ids = [int(record[1]) for record in records]
    assert anchor_ids == list(range(interrupted["A_BOUND_COUNT"]))
    assert len(anchor_ids) == len(set(anchor_ids))
    previous = metadata[7].split("=", 1)[1]
    for line, record in zip(all_lines[1:], records):
        payload, digest = line.rsplit("|", 1)
        assert digest == hashlib.sha256(f"{previous}\n{payload}".encode()).hexdigest()
        previous = digest
    completed_records = sum(1 for record in records if record[2] == "C")
    assert completed_records == interrupted["A_EXPLORED"] + resumed["A_EXPLORED"]

    # A second toy input makes the first anchor reach 48 while the suffix
    # bound is 9, exercising durable proof records for the skipped suffix.
    prune_checkpoint = tmp_path / "pruned-suffix.jsonl"
    prune_full = invoke(binary, "full-prune")
    prune_partial = invoke(binary, "partial-prune", prune_checkpoint)
    prune_resumed = invoke(binary, "resume-prune", prune_checkpoint)
    assert prune_partial["CLOSED"] is False
    assert prune_resumed["CLOSED"] is True
    assert prune_resumed["BEST_F"] == prune_full["BEST_F"] == 48
    assert prune_resumed["TIE_COUNT"] == prune_full["TIE_COUNT"]
    assert prune_resumed["TIES"] == prune_full["TIES"]
    assert prune_resumed["TRIPLES_ACCOUNTED"] == prune_full["TRIPLES_ACCOUNTED"]
    assert any(line.split("|")[2] == "P" for line in prune_checkpoint.read_text().splitlines()[1:])

    assert invoke(binary, "bad-input", checkpoint)["DRIFT_FAIL_CLOSED"] == "PASS"
    assert invoke(binary, "bad-engine", checkpoint)["DRIFT_FAIL_CLOSED"] == "PASS"
    assert invoke(binary, "bad-config", checkpoint)["DRIFT_FAIL_CLOSED"] == "PASS"
    assert invoke(binary, "bad-destroy", checkpoint)["DRIFT_FAIL_CLOSED"] == "PASS"
    assert invoke(binary, "bad-f0", checkpoint)["DRIFT_FAIL_CLOSED"] == "PASS"

    corrupt = tmp_path / "corrupt.jsonl"
    shutil.copyfile(checkpoint, corrupt)
    damaged = corrupt.read_bytes()
    assert len(damaged) > len(lines[0]) + 10
    damaged = damaged[:-2] + (b"0" if damaged[-2:-1] != b"0" else b"1") + damaged[-1:]
    corrupt.write_bytes(damaged)
    result = subprocess.run(
        [str(binary), "resume", str(corrupt)], capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode != 0
    assert "prefix SHA256 mismatch" in result.stderr
