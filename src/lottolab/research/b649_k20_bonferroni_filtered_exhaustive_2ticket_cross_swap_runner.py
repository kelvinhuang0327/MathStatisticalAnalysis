# pyright: reportPrivateUsage=false
"""Run the R1 cross-swap search from any exact-verified, Git-pinned K20 artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast

from lottolab.research import (
    b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1 as search,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
)

_EXPECTED_TOTAL_OUTCOME_COUNT = 601_304_088
_SHA1_RE = re.compile(r"[0-9a-f]{40}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_GENERIC_ID_RE = re.compile(r"[A-Z0-9_]+\Z")


@dataclass(frozen=True, slots=True)
class ValidatedIncumbent:
    """An incumbent whose Git identity, content, exact score, and bounds passed."""

    incumbent: search.Incumbent
    artifact_blob: str
    artifact_sha256: str
    exact: ExactPortfolioProbability
    bound_fixture_hashes: tuple[str, ...]


def _git_result(repository: Path, arguments: list[str]) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ValueError("cannot access the repository Git object database") from exc


def _git_stdout(repository: Path, arguments: list[str], context: str) -> bytes:
    result = _git_result(repository, arguments)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"{context}: {detail or 'Git command failed'}")
    return result.stdout


def _validate_path_identity(source_path: str) -> None:
    if type(source_path) is not str or not source_path or "\x00" in source_path:
        raise ValueError("incumbent path must be a non-empty repository-relative path")
    if "\\" in source_path:
        raise ValueError("incumbent path must use repository-relative POSIX separators")
    posix_path = PurePosixPath(source_path)
    windows_path = PureWindowsPath(source_path)
    if posix_path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise ValueError("incumbent path must be repository-relative")
    if any(part in ("", ".", "..") for part in source_path.split("/")):
        raise ValueError("incumbent path contains an empty or traversing component")


def _validate_run_ids(task_id: str, execution_id: str) -> None:
    for name, value in (("task-id", task_id), ("execution-id", execution_id)):
        if type(value) is not str or _GENERIC_ID_RE.fullmatch(value) is None:
            raise ValueError(f"{name} must match ^[A-Z0-9_]+$")
        if value in {search.TASK_ID, search.EXECUTION_ID}:
            raise ValueError(f"{name} cannot reuse an R1 task or execution ID")


@cache
def _canonical_draw_space() -> DrawMasks:
    """Build the complete canonical main-draw space once per process."""

    return all_main_draw_masks(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)


def _read_git_artifact(
    repository: Path, source_commit: str, source_path: str
) -> tuple[str, bytes]:
    if type(source_commit) is not str or _SHA1_RE.fullmatch(source_commit) is None:
        raise ValueError("incumbent commit must be a full lowercase 40-character SHA")
    _validate_path_identity(source_path)

    try:
        repository_root = repository.resolve(strict=True)
    except OSError as exc:
        raise ValueError("repository path is unavailable") from exc
    if not repository_root.is_dir():
        raise ValueError("repository path must be a directory")

    resolved_commit = _git_stdout(
        repository_root,
        ["rev-parse", "--verify", f"{source_commit}^{{commit}}"],
        "incumbent commit is unavailable in this repository",
    ).decode("ascii", errors="replace").strip()
    if resolved_commit != source_commit:
        raise ValueError("incumbent commit identity did not resolve exactly")
    commit_type = _git_stdout(
        repository_root,
        ["cat-file", "-t", source_commit],
        "incumbent commit is unavailable in this repository",
    ).decode("ascii", errors="replace").strip()
    if commit_type != "commit":
        raise ValueError("incumbent commit does not identify a commit object")

    object_spec = f"{source_commit}:{source_path}"
    blob_type = _git_stdout(
        repository_root,
        ["cat-file", "-t", object_spec],
        "incumbent artifact path is unavailable in this commit",
    ).decode("ascii", errors="replace").strip()
    if blob_type != "blob":
        raise ValueError("incumbent artifact path must identify a Git blob")

    blob_oid = _git_stdout(
        repository_root,
        ["rev-parse", "--verify", object_spec],
        "cannot resolve incumbent artifact blob",
    ).decode("ascii", errors="replace").strip()
    if len(blob_oid) not in (40, 64) or re.fullmatch(r"[0-9a-f]+", blob_oid) is None:
        raise ValueError("Git returned an invalid incumbent blob identity")
    raw = _git_stdout(
        repository_root,
        ["cat-file", "blob", blob_oid],
        "cannot read incumbent artifact blob",
    )
    return blob_oid, raw


def load_and_verify_pinned_incumbent(
    repository: Path,
    *,
    source_commit: str,
    source_path: str,
    artifact_sha256: str,
) -> ValidatedIncumbent:
    """Load an explicitly authorized Git blob and independently exact-verify it."""

    if type(artifact_sha256) is not str or _SHA256_RE.fullmatch(artifact_sha256) is None:
        raise ValueError("incumbent artifact SHA-256 must be a full lowercase 64-character hash")

    artifact_blob, raw = _read_git_artifact(repository, source_commit, source_path)
    actual_artifact_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_artifact_sha256 != artifact_sha256:
        raise ValueError("incumbent artifact SHA-256 does not match its authorization pin")

    try:
        decoded: object = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("incumbent artifact is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("incumbent artifact root must be a JSON object")
    artifact = cast(dict[str, object], decoded)

    if artifact.get("SCIENTIFIC_OBJECTIVE") != "OFFICIAL_ANY_PRIZE":
        raise ValueError("incumbent objective is not OFFICIAL_ANY_PRIZE")

    raw_portfolio = artifact.get("TERMINAL_TICKETS")
    if not isinstance(raw_portfolio, list):
        raise ValueError("incumbent terminal tickets must be a JSON array")
    portfolio_tickets: list[list[int]] = []
    for raw_ticket in cast(list[object], raw_portfolio):
        if not isinstance(raw_ticket, list):
            raise ValueError("incumbent ticket must be a JSON array")
        portfolio_tickets.append(cast(list[int], raw_ticket))
    portfolio = search.normalize_portfolio(
        portfolio_tickets, expected_ticket_count=20
    )

    expected_portfolio_sha256 = artifact.get("TERMINAL_K20_PORTFOLIO_SHA256")
    outcome_count = artifact.get("TERMINAL_K20_OUTCOME_COUNT")
    fraction_text = artifact.get("TERMINAL_K20_EXACT_PROBABILITY")
    method = artifact.get("INCUMBENT_METHOD_ID")
    if type(expected_portfolio_sha256) is not str:
        raise ValueError("incumbent portfolio SHA-256 must be a string")
    if type(outcome_count) is not int:
        raise ValueError("incumbent outcome count must be an integer")
    if type(fraction_text) is not str:
        raise ValueError("incumbent exact fraction must be a string")
    if type(method) is not str:
        raise ValueError("incumbent method ID must be a string")

    artifact_total = artifact.get("TOTAL_OFFICIAL_OUTCOMES")
    if "TOTAL_OFFICIAL_OUTCOMES" in artifact and (
        type(artifact_total) is not int or artifact_total != _EXPECTED_TOTAL_OUTCOME_COUNT
    ):
        raise ValueError("incumbent total outcome space must equal 601304088")
    if search.TOTAL_OFFICIAL_OUTCOMES != _EXPECTED_TOTAL_OUTCOME_COUNT:
        raise ValueError("R1 exact evaluator outcome space is not the canonical 601304088")
    if not 0 <= outcome_count <= _EXPECTED_TOTAL_OUTCOME_COUNT:
        raise ValueError("incumbent outcome count is outside the canonical outcome space")
    if fraction_text != str(Fraction(outcome_count, _EXPECTED_TOTAL_OUTCOME_COUNT)):
        raise ValueError("incumbent exact fraction is not the canonical reduced count fraction")

    actual_portfolio_sha256 = search.portfolio_sha256(portfolio)
    if actual_portfolio_sha256 != expected_portfolio_sha256:
        raise ValueError("incumbent portfolio SHA-256 does not match its normalized tickets")

    incumbent = search.Incumbent(
        portfolio=portfolio,
        portfolio_sha256=actual_portfolio_sha256,
        exact_fraction=fraction_text,
        outcome_count=outcome_count,
        source_commit=source_commit,
        source_path=source_path,
        method=method,
    )
    draws = _canonical_draw_space()
    exact = search.verify_incumbent_exact(incumbent, draws=draws)
    exact_total = exact.main_draw_count * exact.special_count
    if (
        exact_total != _EXPECTED_TOTAL_OUTCOME_COUNT
        or exact_total != search.TOTAL_OFFICIAL_OUTCOMES
    ):
        raise ValueError("exact evaluator constructed a non-canonical outcome space")
    if exact.official_any_prize_outcome_count != outcome_count:
        raise ValueError("independent exact recompute disagrees with the incumbent outcome count")
    if str(exact.official_any_prize) != fraction_text:
        raise ValueError("independent exact recompute disagrees with the incumbent fraction")

    try:
        fixture_hashes = search.validate_bound_fixtures(
            portfolio,
            draws=draws,
            known_incumbent_exact=exact,
        )
    except (AssertionError, ValueError) as exc:
        raise ValueError("incumbent failed the required Bonferroni bound fixtures") from exc

    return ValidatedIncumbent(
        incumbent=incumbent,
        artifact_blob=artifact_blob,
        artifact_sha256=actual_artifact_sha256,
        exact=exact,
        bound_fixture_hashes=fixture_hashes,
    )


def _generic_report(
    state: search.SweepState,
    validated: ValidatedIncumbent,
    *,
    task_id: str,
    execution_id: str,
) -> dict[str, object]:
    incumbent = validated.incumbent
    report = search._report(
        state, fixture_exact_evaluations=len(validated.bound_fixture_hashes)
    )
    report.update(
        {
            "TASK_ID": task_id,
            "INCUMBENT_SOURCE_COMMIT": incumbent.source_commit,
            "INCUMBENT_SOURCE_PATH": incumbent.source_path,
            "INCUMBENT_PORTFOLIO_SHA256": incumbent.portfolio_sha256,
            "INCUMBENT_EXACT_FRACTION": str(validated.exact.official_any_prize),
            "INCUMBENT_OUTCOME_COUNT": validated.exact.official_any_prize_outcome_count,
            "INCUMBENT_METHOD": incumbent.method,
            "INCUMBENT_PORTFOLIO": incumbent.portfolio,
            "INCUMBENT_ARTIFACT_BLOB": validated.artifact_blob,
            "INCUMBENT_ARTIFACT_SHA256": validated.artifact_sha256,
            "EXECUTION_ID": execution_id,
            "SEARCH_DEFINITION_VERSION": search.SEARCH_DEFINITION_VERSION,
        }
    )
    return report


def run_task(
    repository: Path,
    *,
    source_commit: str,
    source_path: str,
    artifact_sha256: str,
    task_id: str,
    execution_id: str,
    checkpoint_path: Path,
    result_path: Path,
    resume: bool = False,
    checkpoint_every: int = 25,
    max_raw_moves: int | None = None,
) -> dict[str, object]:
    """Validate a dynamic incumbent, then run/resume the unchanged R1 engine."""

    _validate_run_ids(task_id, execution_id)
    validated = load_and_verify_pinned_incumbent(
        repository,
        source_commit=source_commit,
        source_path=source_path,
        artifact_sha256=artifact_sha256,
    )
    incumbent = validated.incumbent
    draws = _canonical_draw_space()
    state = search.run_cross_swap_sweep(
        incumbent.portfolio,
        validated.exact.official_any_prize_outcome_count,
        checkpoint_path=checkpoint_path,
        exact_scorer=lambda candidate: evaluate_portfolio(candidate, draws=draws),
        task_id=task_id,
        resume=resume,
        checkpoint_every=checkpoint_every,
        max_raw_moves=max_raw_moves,
        expected_ticket_count=20,
    )
    report = _generic_report(
        state, validated, task_id=task_id, execution_id=execution_id
    )
    search._write_json_atomically(result_path, report)
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incumbent-commit", required=True)
    parser.add_argument("--incumbent-path", required=True)
    parser.add_argument("--incumbent-artifact-sha256", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--result-path", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--max-raw-moves", type=int)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    repository = Path(__file__).resolve().parents[3]
    checkpoint_path = args.checkpoint_path
    result_path = args.result_path
    if not checkpoint_path.is_absolute():
        checkpoint_path = repository / checkpoint_path
    if not result_path.is_absolute():
        result_path = repository / result_path
    report = run_task(
        repository,
        source_commit=args.incumbent_commit,
        source_path=args.incumbent_path,
        artifact_sha256=args.incumbent_artifact_sha256,
        task_id=args.task_id,
        execution_id=args.execution_id,
        checkpoint_path=checkpoint_path,
        result_path=result_path,
        resume=args.resume,
        checkpoint_every=args.checkpoint_every,
        max_raw_moves=args.max_raw_moves,
    )
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
