"""Fail-closed and compatibility tests for the generic pinned K20 runner."""

from __future__ import annotations

import hashlib
import itertools
import json
import subprocess
import sys
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import cast

import numpy as np
import pytest

import lottolab.research.b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1 as search
import lottolab.research.b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_runner as runner
from lottolab.research.b649_official_any_prize_exact import ExactPortfolioProbability

REPOSITORY = Path(__file__).resolve().parents[2]
R1_ARTIFACT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-sealed-v2-direct-official-any-prize-k20-terminal-r1.json"
)
R1_ARTIFACT_COMMIT = "03fadab9d88ad83372e45f19b6c5097e9132c1f1"
CHAMPION_ARTIFACT_PATH = (
    "docs/research/matrix-native-results/b649-k20-cross-swap-champion-r1.json"
)
CHAMPION_ARTIFACT_COMMIT = "3eabc0fe5f9fba884ece26321f83c627838d57c6"
CHAMPION_ARTIFACT_SHA256 = "68209ef129169214633cdd086e37143aa592beea841f2424834640b88e99eee9"
CHAMPION_ARTIFACT_BLOB = "5495809766d31473ba62de4cc93aea50f562d998"
CHAMPION_PORTFOLIO_SHA256 = "220450a945b54c87a29ff1b60cd46e6a0a93e12718b288ca517986d190b0b93c"
CHAMPION_OUTCOME_COUNT = 312_859_106
CHAMPION_FRACTION = "22347079/42950292"
TEST_TASK_ID = "GENERIC_RUNNER_TEST_TASK"
TEST_EXECUTION_ID = "GENERIC_RUNNER_TEST_EXECUTION"


def _git_blob(repository: Path, commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repository), "cat-file", "blob", f"{commit}:{path}"],
        check=True,
        capture_output=True,
    ).stdout


def _artifact_payload(repository: Path, commit: str, path: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads(_git_blob(repository, commit, path)))


def _run_task(
    repository: Path,
    checkpoint_path: Path,
    result_path: Path,
    *,
    source_commit: str = CHAMPION_ARTIFACT_COMMIT,
    source_path: str = CHAMPION_ARTIFACT_PATH,
    artifact_sha256: str = CHAMPION_ARTIFACT_SHA256,
    task_id: str = TEST_TASK_ID,
    execution_id: str = TEST_EXECUTION_ID,
) -> dict[str, object]:
    return runner.run_task(
        repository,
        source_commit=source_commit,
        source_path=source_path,
        artifact_sha256=artifact_sha256,
        task_id=task_id,
        execution_id=execution_id,
        checkpoint_path=checkpoint_path,
        result_path=result_path,
    )


def _temporary_git_artifact(
    tmp_path: Path, payload: dict[str, object]
) -> tuple[Path, str, bytes, str]:
    repository = tmp_path / "fixture-repository"
    repository.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.name", "Runner Test"], check=True
    )
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "runner-test@example.invalid"],
        check=True,
    )
    artifact_path = repository / CHAMPION_ARTIFACT_PATH
    artifact_path.parent.mkdir(parents=True)
    raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    artifact_path.write_bytes(raw)
    subprocess.run(["git", "-C", str(repository), "add", CHAMPION_ARTIFACT_PATH], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "--quiet", "-m", "fixture"], check=True
    )
    commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repository, commit, raw, CHAMPION_ARTIFACT_PATH


def _tickets(payload: dict[str, object]) -> list[list[object]]:
    raw = payload["TERMINAL_TICKETS"]
    assert isinstance(raw, list)
    return cast(list[list[object]], raw)


def test_generic_loader_matches_original_r1_scientific_incumbent() -> None:
    raw = _git_blob(REPOSITORY, R1_ARTIFACT_COMMIT, R1_ARTIFACT_PATH)
    generic = runner.load_and_verify_pinned_incumbent(
        REPOSITORY,
        source_commit=R1_ARTIFACT_COMMIT,
        source_path=R1_ARTIFACT_PATH,
        artifact_sha256=hashlib.sha256(raw).hexdigest(),
    )
    r1 = search.load_pinned_incumbent(REPOSITORY)
    assert generic.incumbent.portfolio == r1.portfolio
    assert generic.incumbent.portfolio_sha256 == r1.portfolio_sha256 == (
        "242a04c1236f53d74a939f24495868287a4ad63d63b20903fc91d5987b14a9bd"
    )
    assert generic.incumbent.outcome_count == r1.outcome_count == 312_850_818
    assert generic.incumbent.exact_fraction == r1.exact_fraction == "7448829/14316764"
    assert generic.exact.official_any_prize_outcome_count == r1.outcome_count


def test_verified_champion_is_accepted_and_exactly_recomputed() -> None:
    validated = runner.load_and_verify_pinned_incumbent(
        REPOSITORY,
        source_commit=CHAMPION_ARTIFACT_COMMIT,
        source_path=CHAMPION_ARTIFACT_PATH,
        artifact_sha256=CHAMPION_ARTIFACT_SHA256,
    )
    assert validated.artifact_blob == CHAMPION_ARTIFACT_BLOB
    assert validated.artifact_sha256 == CHAMPION_ARTIFACT_SHA256
    assert validated.incumbent.portfolio_sha256 == CHAMPION_PORTFOLIO_SHA256
    assert validated.incumbent.outcome_count == CHAMPION_OUTCOME_COUNT
    assert validated.incumbent.exact_fraction == CHAMPION_FRACTION
    assert validated.exact.official_any_prize_outcome_count == CHAMPION_OUTCOME_COUNT
    assert str(validated.exact.official_any_prize) == CHAMPION_FRACTION
    assert validated.exact.main_draw_count * validated.exact.special_count == 601_304_088
    assert len(validated.bound_fixture_hashes) > 0


@pytest.mark.parametrize(
    ("source_commit", "source_path"),
    [
        pytest.param(CHAMPION_ARTIFACT_COMMIT[:12], CHAMPION_ARTIFACT_PATH, id="abbreviated-sha"),
        pytest.param("HEAD", CHAMPION_ARTIFACT_PATH, id="ref-name"),
        pytest.param("g" * 40, CHAMPION_ARTIFACT_PATH, id="malformed-sha"),
        pytest.param("0" * 40, CHAMPION_ARTIFACT_PATH, id="missing-commit"),
        pytest.param(
            CHAMPION_ARTIFACT_COMMIT,
            "docs/research/matrix-native-results",
            id="tree-not-blob",
        ),
        pytest.param(
            CHAMPION_ARTIFACT_COMMIT,
            "docs/research/matrix-native-results/missing.json",
            id="missing-path",
        ),
        pytest.param(CHAMPION_ARTIFACT_COMMIT, "/absolute/incumbent.json", id="absolute-path"),
        pytest.param(CHAMPION_ARTIFACT_COMMIT, "../outside.json", id="path-traversal"),
        pytest.param(CHAMPION_ARTIFACT_COMMIT, "docs//artifact.json", id="empty-path-component"),
        pytest.param(CHAMPION_ARTIFACT_COMMIT, "", id="empty-path"),
    ],
)
def test_git_locator_fails_closed_before_checkpoint(
    tmp_path: Path, source_commit: str, source_path: str
) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    with pytest.raises(ValueError):
        _run_task(
            REPOSITORY,
            checkpoint,
            tmp_path / "result.json",
            source_commit=source_commit,
            source_path=source_path,
        )
    assert not checkpoint.exists()


def test_wrong_artifact_pin_fails_before_checkpoint(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    result = tmp_path / "result.json"
    with pytest.raises(ValueError, match="SHA-256"):
        _run_task(
            REPOSITORY,
            checkpoint,
            result,
            artifact_sha256="0" * 64,
        )
    assert not checkpoint.exists()
    assert not result.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_portfolio_sha",
        "ticket_count",
        "duplicate_ticket",
        "illegal_number",
        "bool_outcome_count",
        "fraction",
        "objective",
        "total_outcomes",
    ],
)
def test_committed_content_errors_fail_closed_before_checkpoint(
    tmp_path: Path, mutation: str
) -> None:
    payload = _artifact_payload(REPOSITORY, CHAMPION_ARTIFACT_COMMIT, CHAMPION_ARTIFACT_PATH)
    tickets = _tickets(payload)
    if mutation == "wrong_portfolio_sha":
        payload["TERMINAL_K20_PORTFOLIO_SHA256"] = "0" * 64
    elif mutation == "ticket_count":
        tickets.pop()
    elif mutation == "duplicate_ticket":
        tickets[1] = list(tickets[0])
    elif mutation == "illegal_number":
        tickets[0][0] = 0
    elif mutation == "bool_outcome_count":
        payload["TERMINAL_K20_OUTCOME_COUNT"] = True
    elif mutation == "fraction":
        payload["TERMINAL_K20_EXACT_PROBABILITY"] = "44694158/85900584"
    elif mutation == "objective":
        payload["SCIENTIFIC_OBJECTIVE"] = "M3_PLUS"
    elif mutation == "total_outcomes":
        payload["TOTAL_OFFICIAL_OUTCOMES"] = 601_304_087
    else:
        raise AssertionError(f"unhandled mutation: {mutation}")

    repository, commit, raw, path = _temporary_git_artifact(tmp_path, payload)
    checkpoint = tmp_path / "checkpoint.json"
    with pytest.raises(ValueError):
        _run_task(
            repository,
            checkpoint,
            tmp_path / "result.json",
            source_commit=commit,
            source_path=path,
            artifact_sha256=hashlib.sha256(raw).hexdigest(),
        )
    assert not checkpoint.exists()


def test_consistent_count_plus_one_is_rejected_by_independent_exact_recompute(
    tmp_path: Path,
) -> None:
    payload = _artifact_payload(REPOSITORY, CHAMPION_ARTIFACT_COMMIT, CHAMPION_ARTIFACT_PATH)
    count = cast(int, payload["TERMINAL_K20_OUTCOME_COUNT"]) + 1
    payload["TERMINAL_K20_OUTCOME_COUNT"] = count
    payload["TERMINAL_K20_EXACT_PROBABILITY"] = str(Fraction(count, 601_304_088))
    repository, commit, raw, path = _temporary_git_artifact(tmp_path, payload)
    checkpoint = tmp_path / "checkpoint.json"
    with pytest.raises(ValueError, match="canonical exact arbiter"):
        _run_task(
            repository,
            checkpoint,
            tmp_path / "result.json",
            source_commit=commit,
            source_path=path,
            artifact_sha256=hashlib.sha256(raw).hexdigest(),
        )
    assert not checkpoint.exists()


@pytest.mark.parametrize(
    ("task_id", "execution_id"),
    [
        pytest.param("bad-task", TEST_EXECUTION_ID, id="invalid-task-format"),
        pytest.param(search.TASK_ID, TEST_EXECUTION_ID, id="reused-r1-task-id"),
        pytest.param(TEST_TASK_ID, search.EXECUTION_ID, id="reused-r1-execution-id"),
        pytest.param(TEST_TASK_ID, "lowercase", id="invalid-execution-format"),
    ],
)
def test_run_id_rejection_precedes_checkpoint_creation(
    tmp_path: Path, task_id: str, execution_id: str
) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    with pytest.raises(ValueError):
        runner.run_task(
            REPOSITORY,
            source_commit=CHAMPION_ARTIFACT_COMMIT,
            source_path=CHAMPION_ARTIFACT_PATH,
            artifact_sha256=CHAMPION_ARTIFACT_SHA256,
            task_id=task_id,
            execution_id=execution_id,
            checkpoint_path=checkpoint,
            result_path=tmp_path / "result.json",
        )
    assert not checkpoint.exists()


def test_threshold_and_report_use_exact_generic_incumbent_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    portfolio = search.normalize_portfolio(
        tuple(itertools.islice(itertools.combinations(range(1, 50), 6), 20)),
        expected_ticket_count=20,
    )
    incumbent = search.Incumbent(
        portfolio=portfolio,
        portfolio_sha256=search.portfolio_sha256(portfolio),
        exact_fraction=CHAMPION_FRACTION,
        outcome_count=CHAMPION_OUTCOME_COUNT,
        source_commit=CHAMPION_ARTIFACT_COMMIT,
        source_path=CHAMPION_ARTIFACT_PATH,
        method="GENERIC_TEST_METHOD",
    )
    exact = ExactPortfolioProbability(
        main_draw_count=comb(49, 6),
        special_count=43,
        m3_plus_draw_count=4_805_642,
        official_any_prize_outcome_count=CHAMPION_OUTCOME_COUNT,
    )
    validated = runner.ValidatedIncumbent(
        incumbent=incumbent,
        artifact_blob=CHAMPION_ARTIFACT_BLOB,
        artifact_sha256=CHAMPION_ARTIFACT_SHA256,
        exact=exact,
        bound_fixture_hashes=("fixture-hash",),
    )
    monkeypatch.setattr(runner, "_canonical_draw_space", lambda: np.array([], dtype=np.uint64))
    def fake_load(
        *_args: object, **_kwargs: object
    ) -> runner.ValidatedIncumbent:
        return validated

    monkeypatch.setattr(runner, "load_and_verify_pinned_incumbent", fake_load)

    captured: dict[str, object] = {}

    def fake_sweep(
        source_portfolio: tuple[tuple[int, ...], ...], threshold: int, **kwargs: object
    ) -> search.SweepState:
        captured["portfolio"] = source_portfolio
        captured["threshold"] = threshold
        captured["task_id"] = kwargs["task_id"]
        return search.SweepState(
            task_id=cast(str, kwargs["task_id"]),
            search_definition_version=search.SEARCH_DEFINITION_VERSION,
            incumbent_sha256=search.portfolio_sha256(source_portfolio),
            incumbent_outcome_count=threshold,
            ticket_pair_index=0,
            move_index=0,
            raw_move_count=0,
            illegal_move_count=0,
            legal_move_count=0,
            duplicate_result_count=0,
            unique_legal_portfolio_count=0,
            bonferroni_pruned_count=0,
            survivor_count=0,
            exact_scored_count=0,
            seen_portfolio_hashes=set(),
            exact_records=[],
            best_exact_count=threshold,
            best_portfolio_sha256=search.portfolio_sha256(source_portfolio),
            best_portfolio=source_portfolio,
            audit_digest="test-audit",
            complete=False,
        )

    def fake_report(
        state: search.SweepState, *, fixture_exact_evaluations: int
    ) -> dict[str, object]:
        assert fixture_exact_evaluations == 1
        return {
            "TASK_ID": state.task_id,
            "INCUMBENT_SOURCE_COMMIT": search.INCUMBENT_SOURCE_COMMIT,
            "INCUMBENT_SOURCE_PATH": search.INCUMBENT_SOURCE_PATH,
            "INCUMBENT_EXACT_FRACTION": search.EXPECTED_INCUMBENT_FRACTION,
            "INCUMBENT_PORTFOLIO_SHA256": search.portfolio_sha256(state.best_portfolio),
            "INCUMBENT_OUTCOME_COUNT": state.incumbent_outcome_count,
            "EXECUTION_ID": search.EXECUTION_ID,
        }

    monkeypatch.setattr(search, "run_cross_swap_sweep", fake_sweep)
    monkeypatch.setattr(search, "_report", fake_report)
    result_path = tmp_path / "result.json"
    report = runner.run_task(
        REPOSITORY,
        source_commit=CHAMPION_ARTIFACT_COMMIT,
        source_path=CHAMPION_ARTIFACT_PATH,
        artifact_sha256=CHAMPION_ARTIFACT_SHA256,
        task_id=TEST_TASK_ID,
        execution_id=TEST_EXECUTION_ID,
        checkpoint_path=tmp_path / "checkpoint.json",
        result_path=result_path,
    )

    assert captured["threshold"] == CHAMPION_OUTCOME_COUNT
    assert captured["threshold"] != search.EXPECTED_INCUMBENT_OUTCOME_COUNT
    assert captured["task_id"] == TEST_TASK_ID
    assert report["TASK_ID"] == TEST_TASK_ID
    assert report["INCUMBENT_SOURCE_COMMIT"] == CHAMPION_ARTIFACT_COMMIT
    assert report["INCUMBENT_SOURCE_PATH"] == CHAMPION_ARTIFACT_PATH
    assert report["INCUMBENT_EXACT_FRACTION"] == CHAMPION_FRACTION
    assert report["INCUMBENT_PORTFOLIO_SHA256"] == incumbent.portfolio_sha256
    assert report["INCUMBENT_OUTCOME_COUNT"] == CHAMPION_OUTCOME_COUNT
    assert report["INCUMBENT_ARTIFACT_BLOB"] == CHAMPION_ARTIFACT_BLOB
    assert report["INCUMBENT_ARTIFACT_SHA256"] == CHAMPION_ARTIFACT_SHA256
    assert report["EXECUTION_ID"] == TEST_EXECUTION_ID
    assert report["SEARCH_DEFINITION_VERSION"] == search.SEARCH_DEFINITION_VERSION
    assert report["INCUMBENT_SOURCE_COMMIT"] != search.INCUMBENT_SOURCE_COMMIT
    assert report["INCUMBENT_SOURCE_PATH"] != search.INCUMBENT_SOURCE_PATH
    assert report["INCUMBENT_EXACT_FRACTION"] != search.EXPECTED_INCUMBENT_FRACTION
    assert json.loads(result_path.read_text()) == json.loads(json.dumps(report))


def test_cli_requires_all_generic_identity_and_output_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["generic-runner"])
    with pytest.raises(SystemExit):
        runner.main()
