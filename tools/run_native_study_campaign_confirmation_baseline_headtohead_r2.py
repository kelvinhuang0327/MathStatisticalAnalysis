"""Run and seal NATIVE_STUDY_CAMPAIGN_CONFIRMATION_BASELINE_HEADTOHEAD_R2."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import cast

from lottolab.evidence import canonical_json
from lottolab.research.native_study_campaign_confirmation_baseline_headtohead_r2 import (
    PAIRED_EVIDENCE_STATUS,
    PROMOTION_DECISION,
    R1_EXPECTED_RESULT_SHA256,
    SIGNIFICANCE_RESULT_STATUS,
    R2Execution,
    run_native_study_campaign_confirmation_baseline_headtohead_r2,
)

RESULT_OUTPUT = Path(
    "docs/research/matrix-native-results/"
    "native-study-campaign-confirmation-baseline-headtohead-r2-result.json"
)
HASH_OUTPUT = Path(
    "docs/research/matrix-native-results/"
    "native-study-campaign-confirmation-baseline-headtohead-r2-hash.json"
)


@dataclass(frozen=True, slots=True)
class _Arguments:
    r1_result: Path
    archive_database: Path
    result_output: Path
    hash_output: Path


def _parse_args() -> _Arguments:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--r1-result",
        required=True,
        type=Path,
        help="Canonical sealed R1 result whose SHA is fixed by this task.",
    )
    parser.add_argument(
        "--archive-database",
        required=True,
        type=Path,
        help="Read-only archived SQLite snapshot; data/lottery_v2.db is refused.",
    )
    parser.add_argument("--result-output", type=Path, default=RESULT_OUTPUT)
    parser.add_argument("--hash-output", type=Path, default=HASH_OUTPUT)
    namespace = parser.parse_args()
    return _Arguments(
        r1_result=cast(Path, namespace.r1_result),
        archive_database=cast(Path, namespace.archive_database),
        result_output=cast(Path, namespace.result_output),
        hash_output=cast(Path, namespace.hash_output),
    )


def _resolved_file(path: Path, *, label: str) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"{label} must be a regular file")
    return resolved


def _refuse_live_database(path: Path) -> Path:
    resolved = _resolved_file(path, label="archive database")
    if resolved.name == "lottery_v2.db" and resolved.parent.name == "data":
        raise ValueError("the R2 runner refuses a live/worktree data/lottery_v2.db")
    return resolved


def _write_exclusive(outputs: tuple[tuple[Path, bytes], ...]) -> None:
    resolved = tuple(path.resolve() for path, _raw in outputs)
    if len(set(resolved)) != len(resolved):
        raise ValueError("R2 output paths must be distinct")
    if any(path.exists() for path in resolved):
        raise FileExistsError("R2 output already exists; refusing to overwrite evidence")
    if any(not path.parent.is_dir() for path in resolved):
        raise FileNotFoundError("R2 output directory does not exist")
    for path, raw in outputs:
        with path.open("xb") as handle:
            handle.write(raw)


def _hash_document(
    execution: R2Execution,
    *,
    result_output: Path,
) -> dict[str, object]:
    result_bytes = execution.canonical_result_bytes()
    return {
        "canonical_result_byte_count": len(result_bytes),
        "canonical_result_file": result_output.name,
        "canonical_result_sha256": canonical_json.sha256_hex(result_bytes),
        "canonicalization": "LCJ-1",
        "default_evaluation_count": execution.default_evaluation_count,
        "deterministic_serialization": "PASS_IDENTICAL_BYTES_AND_HASHES",
        "promotion_decision": PROMOTION_DECISION,
        "r1_result_sha256": R1_EXPECTED_RESULT_SHA256,
        "winner_evaluation_count": execution.winner_evaluation_count,
    }


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _result_text(values: tuple[Fraction, Fraction]) -> str:
    return (
        f"AVG_MATCH_DELTA_VS_RANDOM={_fraction_text(values[0])};"
        f"M3_PLUS_OBSERVED_RATE={_fraction_text(values[1])}"
    )


def main() -> None:
    arguments = _parse_args()
    r1_result = _resolved_file(arguments.r1_result, label="R1 result")
    archive_database = _refuse_live_database(arguments.archive_database)
    execution = run_native_study_campaign_confirmation_baseline_headtohead_r2(
        r1_result=r1_result,
        archive_database=archive_database,
    )
    first_result_bytes = execution.canonical_result_bytes()
    second_result_bytes = execution.canonical_result_bytes()
    first_result_sha256 = canonical_json.sha256_hex(first_result_bytes)
    second_result_sha256 = canonical_json.sha256_hex(second_result_bytes)
    if first_result_bytes != second_result_bytes or first_result_sha256 != second_result_sha256:
        raise RuntimeError("deterministic resealing of existing R2 values failed")
    if execution.winner_evaluation_count != 0:
        raise RuntimeError("winner reevaluation count must remain zero")
    if execution.default_evaluation_count != 1:
        raise RuntimeError("default evaluation count must equal one")
    hash_bytes = canonical_json.canonical_bytes(
        _hash_document(execution, result_output=arguments.result_output)
    )
    _write_exclusive(
        (
            (arguments.result_output, first_result_bytes),
            (arguments.hash_output, hash_bytes),
        )
    )

    print(f"R1_RESULT_SHA256: {R1_EXPECTED_RESULT_SHA256}")
    print("WINNER_CONFIRMATION_RESULT: " + _result_text(execution.winner_confirmation_values))
    print("DEFAULT_CONFIRMATION_RESULT: " + _result_text(execution.default_confirmation_values))
    print("AVG_MATCH_HEAD_TO_HEAD_DELTA: " + _fraction_text(execution.head_to_head_deltas[0]))
    print("M3_PLUS_HEAD_TO_HEAD_DELTA: " + _fraction_text(execution.head_to_head_deltas[1]))
    print("POINT_ESTIMATE_CLASSIFICATION: " + execution.point_estimate_classification)
    print(f"PAIRED_EVIDENCE: {PAIRED_EVIDENCE_STATUS}")
    print(f"SIGNIFICANCE_RESULT: {SIGNIFICANCE_RESULT_STATUS}")
    print(f"PROMOTION_DECISION: {PROMOTION_DECISION}")
    print(f"WINNER_REEVALUATION_COUNT: {execution.winner_evaluation_count}")
    print(f"DEFAULT_EVALUATION_COUNT: {execution.default_evaluation_count}")
    print(f"CANONICAL_RESULT_SHA256: {first_result_sha256}")
    print("DETERMINISTIC_SERIALIZATION: PASS_IDENTICAL_BYTES_AND_HASHES")


if __name__ == "__main__":
    main()
