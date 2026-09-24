"""Focused verification for the bounded K20 3-cycle VND."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import subprocess
from fractions import Fraction
from math import comb
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from lottolab.research import (
    b649_k20_3ticket_cyclic_cross_swap_vnd_r1 as vnd,
)
from lottolab.research import (
    b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1 as r4,
)
from lottolab.research import (
    b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_runner as r4_runner,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
)

REPOSITORY = Path(__file__).resolve().parents[2]
TOTAL_OUTCOMES = r4.TOTAL_OFFICIAL_OUTCOMES


def _ignore_call(*_args: object, **_kwargs: object) -> None:
    return None


def _patch_candidate_head_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    git_stdout = vnd._git_stdout

    def report_pinned_head(repository: Path, arguments: list[str]) -> str:
        if arguments == ["rev-parse", "HEAD"]:
            return vnd.BASE_COMMIT
        if arguments == ["rev-parse", "HEAD^{tree}"]:
            return vnd.BASE_TREE
        return git_stdout(repository, arguments)

    monkeypatch.setattr(vnd, "_git_stdout", report_pinned_head)


@pytest.fixture(scope="module")
def starting() -> vnd.StartingPortfolio:
    return vnd.load_run2_starting_portfolio(REPOSITORY)


def _fake_exact(outcome_count: int) -> ExactPortfolioProbability:
    return ExactPortfolioProbability(
        main_draw_count=comb(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE),
        special_count=BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE,
        m3_plus_draw_count=0,
        official_any_prize_outcome_count=outcome_count,
    )


def _first_legal_cycle(portfolio: r4.Portfolio) -> vnd.ThreeCycleCandidate:
    for move in vnd.iter_three_cycle_moves(20):
        try:
            return vnd.apply_three_cycle(portfolio, move)
        except ValueError:
            continue
    raise AssertionError("fixture portfolio has no legal 3-cycle")


def test_exact_base_identity_and_run2_start_reconstruction(
    starting: vnd.StartingPortfolio,
) -> None:
    base_commit = subprocess.run(
        ["git", "-C", str(REPOSITORY), "rev-parse", vnd.BASE_COMMIT],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    base_tree = subprocess.run(
        ["git", "-C", str(REPOSITORY), "rev-parse", f"{vnd.BASE_COMMIT}^{{tree}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert base_commit == vnd.BASE_COMMIT
    assert base_tree == vnd.BASE_TREE
    assert starting.run2_artifact_sha256 == vnd.R4_RUN2_SHA256
    assert starting.portfolio_sha256 == vnd.EXPECTED_R4_PORTFOLIO_SHA256
    assert starting.exact_outcome_count == 312_867_226
    assert starting.exact_fraction == "519713/998844"
    assert len(starting.portfolio) == 20
    assert len(set(starting.portfolio)) == 20


def test_raw_count_derives_from_complete_structural_product() -> None:
    ticket_triples = comb(20, 3)
    removal_choices = BIG_LOTTO_DRAW_SIZE**3
    orientations = len(vnd.ORIENTATIONS)
    assert ticket_triples == 1140
    assert removal_choices == 216
    assert orientations == 2
    assert vnd.raw_operation_count(20) == ticket_triples * removal_choices * orientations
    assert vnd.raw_operation_count(20) == 492_480
    assert vnd.raw_operation_count(2) == 0


def test_s3_reduction_has_two_new_cycles_and_transpositions_are_r4_swaps() -> None:
    classes = vnd.s3_permutation_classes()
    assert len(classes["IDENTITY"]) == 1
    assert len(classes["TRANSPOSITION"]) == 3
    assert len(classes["THREE_CYCLE"]) == 2
    assert set(classes["THREE_CYCLE"]) == {(1, 2, 0), (2, 0, 1)}

    tickets = (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
    )
    removed = (1, 7, 13)
    for permutation in classes["TRANSPOSITION"]:
        received = tuple(removed[index] for index in permutation)
        changed_positions = tuple(
            index
            for index, (before, after) in enumerate(zip(removed, received, strict=True))
            if before != after
        )
        assert len(changed_positions) == 2
        fixed = ({0, 1, 2} - set(changed_positions)).pop()
        assert received[fixed] == removed[fixed]
        first, second = changed_positions
        assert received[first] == removed[second]
        assert received[second] == removed[first]

        ticket_a, ticket_b = sorted((first, second))
        move_a = r4.CrossSwapMove(
            pair_index=0,
            move_index=0,
            ticket_a_index=ticket_a,
            ticket_b_index=ticket_b,
            number_from_a=removed[ticket_a],
            number_from_b=removed[ticket_b],
        )
        pair_result = r4.apply_cross_swap(tickets, move_a)
        updated: list[tuple[int, ...]] = list(tickets)
        for position, value in enumerate(received):
            updated[position] = tuple(
                sorted((set(tickets[position]) - {removed[position]}) | {value})
            )
        assert r4.normalize_portfolio(updated) == pair_result.portfolio


def test_only_the_two_cycle_orientations_are_exposed() -> None:
    assert vnd.ORIENTATIONS == ("CYCLE_FORWARD", "CYCLE_REVERSE")
    forward = vnd._PERMUTATION_BY_ORIENTATION["CYCLE_FORWARD"]
    reverse = vnd._PERMUTATION_BY_ORIENTATION["CYCLE_REVERSE"]
    assert forward == (1, 2, 0)
    assert reverse == (2, 0, 1)
    assert forward != reverse
    assert set(forward) == set(reverse) == {0, 1, 2}


def test_three_cycle_candidate_is_legal_unique_and_deterministic(
    starting: vnd.StartingPortfolio,
) -> None:
    candidate = _first_legal_cycle(starting.portfolio)
    assert len(candidate.portfolio) == 20
    assert len(set(candidate.portfolio)) == 20
    assert all(len(ticket) == BIG_LOTTO_DRAW_SIZE for ticket in candidate.portfolio)
    assert all(len(set(ticket)) == BIG_LOTTO_DRAW_SIZE for ticket in candidate.portfolio)
    assert all(
        1 <= number <= BIG_LOTTO_POOL_SIZE for ticket in candidate.portfolio for number in ticket
    )
    assert candidate.portfolio != starting.portfolio
    assert len(candidate.old_changed_indices) == len(candidate.new_changed_indices) == 3

    reordered = tuple(tuple(reversed(ticket)) for ticket in reversed(starting.portfolio))
    same = vnd.apply_three_cycle(reordered, candidate.move)
    assert same.portfolio == candidate.portfolio
    assert same.portfolio_sha256 == candidate.portfolio_sha256
    assert same.move.tie_key == candidate.move.tie_key
    deduplicator = r4.PortfolioDeduplicator()
    assert deduplicator.add(candidate.portfolio)
    assert not deduplicator.add(same.portfolio)


def test_noop_three_cycle_result_is_rejected() -> None:
    tickets = tuple(tuple(sorted((1, *(range(2 + index, 7 + index))))) for index in range(20))
    origin = r4.normalize_portfolio(tickets, expected_ticket_count=20)
    move = vnd.ThreeCycleMove((0, 1, 2), (0, 0, 0), "CYCLE_FORWARD")
    with pytest.raises(ValueError, match="no-op"):
        vnd.apply_three_cycle(origin, move)


def test_incremental_three_ticket_u3_is_safe_on_exact_scored_fixtures(
    starting: vnd.StartingPortfolio,
) -> None:
    draws = all_main_draw_masks(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)

    def exact_scorer(portfolio: r4.Portfolio) -> ExactPortfolioProbability:
        return evaluate_portfolio(portfolio, draws=draws)

    fixtures = vnd.select_three_cycle_bound_fixtures(
        starting.portfolio,
        exact_scorer=exact_scorer,
        fixture_count=3,
    )
    assert len(fixtures) >= 3
    assert all(bound >= exact for _, bound, exact in fixtures)
    assert any(bound > exact for _, bound, exact in fixtures)
    for candidate, bound, _exact in fixtures:
        full = r4.full_u3_components(candidate.portfolio)
        assert bound == full.u3


def test_complete_first_block_does_not_stop_after_first_exact_improvement(
    starting: vnd.StartingPortfolio,
    tmp_path: Path,
) -> None:
    exact_calls: list[str] = []

    def scorer(portfolio: r4.Portfolio) -> ExactPortfolioProbability:
        exact_calls.append(r4.portfolio_sha256(portfolio))
        return _fake_exact(1)

    state = vnd.scan_three_cycle_neighborhood(
        starting.portfolio,
        0,
        checkpoint_path=tmp_path / "scan.json",
        seen_hash_path=tmp_path / "seen.sha256",
        run2_artifact_sha256=starting.run2_artifact_sha256,
        round_number=1,
        exact_scorer=scorer,
        max_raw_operations=432,
    )
    assert not state.complete
    assert state.raw_operation_count == 432
    assert state.ticket_triple_index == 1
    assert state.best_exact_count == 1
    assert state.best_move is not None
    assert len(exact_calls) == state.exact_evaluation_count
    assert len(exact_calls) > 1
    assert state.raw_operation_count == state.illegal_operation_count + state.legal_operation_count


def test_tie_break_uses_ticket_triple_positions_then_forward_orientation(
    starting: vnd.StartingPortfolio,
    tmp_path: Path,
) -> None:
    exact_calls: list[str] = []

    def scorer(portfolio: r4.Portfolio) -> ExactPortfolioProbability:
        exact_calls.append(r4.portfolio_sha256(portfolio))
        return _fake_exact(7)

    state = vnd.scan_three_cycle_neighborhood(
        starting.portfolio,
        0,
        checkpoint_path=tmp_path / "scan.json",
        seen_hash_path=tmp_path / "seen.sha256",
        run2_artifact_sha256=starting.run2_artifact_sha256,
        round_number=1,
        exact_scorer=scorer,
        max_raw_operations=432,
    )
    assert state.best_move is not None
    base_components = r4.full_u3_components(starting.portfolio)
    affected_cache: dict[vnd.TicketTriple, r4.U3Components] = {}
    assert state.best_move.tie_key == min(
        move.tie_key
        for move in vnd.iter_three_cycle_moves(20)
        if move.ticket_triple == (0, 1, 2)
        and _candidate_is_exact_scored(starting.portfolio, move, base_components, affected_cache)
    )
    assert state.best_exact_count == 7
    assert len(exact_calls) == state.exact_evaluation_count
    assert len(exact_calls) > 1


def _candidate_is_exact_scored(
    portfolio: r4.Portfolio,
    move: vnd.ThreeCycleMove,
    base_components: r4.U3Components,
    affected_cache: dict[vnd.TicketTriple, r4.U3Components],
) -> bool:
    try:
        candidate = vnd.apply_three_cycle(portfolio, move)
    except ValueError:
        return False
    bound = vnd.incremental_three_ticket_u3(
        portfolio, candidate, base_components, affected_cache
    ).u3
    return not r4.should_safe_prune(bound, 0)


def test_checkpoint_resume_reproduces_partial_scan_state(
    starting: vnd.StartingPortfolio,
    tmp_path: Path,
) -> None:
    def scorer(_portfolio: r4.Portfolio) -> ExactPortfolioProbability:
        return _fake_exact(3)

    split_checkpoint = tmp_path / "split.json"
    split_seen = tmp_path / "split.seen"
    first = vnd.scan_three_cycle_neighborhood(
        starting.portfolio,
        0,
        checkpoint_path=split_checkpoint,
        seen_hash_path=split_seen,
        run2_artifact_sha256=starting.run2_artifact_sha256,
        round_number=2,
        exact_scorer=scorer,
        max_raw_operations=432,
    )
    assert first.raw_operation_count == 432
    resumed = vnd.scan_three_cycle_neighborhood(
        starting.portfolio,
        0,
        checkpoint_path=split_checkpoint,
        seen_hash_path=split_seen,
        run2_artifact_sha256=starting.run2_artifact_sha256,
        round_number=2,
        exact_scorer=scorer,
        resume=True,
        max_raw_operations=433,
    )
    uninterrupted_checkpoint = tmp_path / "uninterrupted.json"
    uninterrupted_seen = tmp_path / "uninterrupted.seen"
    uninterrupted = vnd.scan_three_cycle_neighborhood(
        starting.portfolio,
        0,
        checkpoint_path=uninterrupted_checkpoint,
        seen_hash_path=uninterrupted_seen,
        run2_artifact_sha256=starting.run2_artifact_sha256,
        round_number=2,
        exact_scorer=scorer,
        max_raw_operations=865,
    )
    assert resumed.raw_operation_count == uninterrupted.raw_operation_count == 865
    assert resumed.audit_digest == uninterrupted.audit_digest
    assert resumed.best_move == uninterrupted.best_move
    assert resumed.best_portfolio_sha256 == uninterrupted.best_portfolio_sha256
    assert resumed.exact_evaluation_count == uninterrupted.exact_evaluation_count
    assert split_seen.read_bytes() == uninterrupted_seen.read_bytes()


def _control_scan(
    origin: r4.Portfolio,
    exact_count: int,
    round_number: int,
    *,
    improve: bool,
) -> vnd.ScanCheckpoint:
    state = vnd._initial_scan_checkpoint(origin, exact_count, vnd.R4_RUN2_SHA256, round_number)
    state.complete = True
    if improve:
        candidate = _first_legal_cycle(origin)
        state.best_move = candidate.move
        state.best_portfolio = candidate.portfolio
        state.best_portfolio_sha256 = candidate.portfolio_sha256
        state.best_exact_count = exact_count + 1
        state.best_u3_count = r4.full_u3_components(candidate.portfolio).u3
    return state


def test_two_ticket_reclosure_runs_before_the_final_complete_scan(
    starting: vnd.StartingPortfolio,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    scan_count = 0

    def fake_start(_repository: Path) -> vnd.StartingPortfolio:
        return starting

    def fake_draws() -> object:
        return object()

    def fake_scan(
        portfolio: r4.Portfolio,
        exact_count: int,
        **kwargs: object,
    ) -> vnd.ScanCheckpoint:
        nonlocal scan_count
        scan_count += 1
        round_number = cast(int, kwargs["round_number"])
        events.append(f"scan-{round_number}")
        return _control_scan(
            r4.normalize_portfolio(portfolio, expected_ticket_count=20),
            exact_count,
            round_number,
            improve=scan_count == 1,
        )

    def fake_r4_scan(
        portfolio: r4.Portfolio,
        exact_count: int,
        **_kwargs: object,
    ) -> SimpleNamespace:
        events.append("r4-reclosure")
        normalized = r4.normalize_portfolio(portfolio, expected_ticket_count=20)
        return SimpleNamespace(
            complete=True,
            best_exact_count=exact_count,
            best_portfolio=normalized,
            best_portfolio_sha256=r4.portfolio_sha256(normalized),
        )

    monkeypatch.setattr(vnd, "load_run2_starting_portfolio", fake_start)
    monkeypatch.setattr(vnd, "scan_three_cycle_neighborhood", fake_scan)
    monkeypatch.setattr(vnd, "_write_manifest", _ignore_call)
    monkeypatch.setattr(vnd, "_write_json_result", _ignore_call)
    monkeypatch.setattr(r4_runner, "_canonical_draw_space", fake_draws)
    monkeypatch.setattr(r4, "run_cross_swap_sweep", fake_r4_scan)
    _patch_candidate_head_guard(monkeypatch)
    result = vnd.run_task(
        REPOSITORY,
        run_data_dir=tmp_path,
        canonical_result_path=REPOSITORY
        / "docs/research/b649-k20-3ticket-cyclic-cross-swap-vnd-r1-result.json",
        now_fn=lambda: 1.0,
    )
    assert events == ["scan-1", "r4-reclosure", "scan-2"]
    assert result["FINAL_DISPOSITION"] == "STRICT_IMPROVEMENT_FOUND_AND_VND_CONVERGED"
    assert result["COMBINED_LOCAL_OPTIMUM_STATUS"] == (
        "PROVEN_FOR_DEFINED_2TICKET_PLUS_3CYCLE_NEIGHBORHOODS"
    )
    assert result["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
    assert result["ACCEPTED_2TICKET_RECLOSURE_MOVES"] == 0
    assert len(cast(list[object], result["ACCEPTED_3TICKET_MOVES"])) == 1


def test_round_cap_and_wall_clock_cap_never_claim_combined_local_optimality(
    starting: vnd.StartingPortfolio,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def fake_start(_repository: Path) -> vnd.StartingPortfolio:
        return starting

    def fake_scan(
        portfolio: r4.Portfolio,
        exact_count: int,
        **kwargs: object,
    ) -> vnd.ScanCheckpoint:
        round_number = cast(int, kwargs["round_number"])
        events.append(f"scan-{round_number}")
        return _control_scan(
            r4.normalize_portfolio(portfolio, expected_ticket_count=20),
            exact_count,
            round_number,
            improve=True,
        )

    def fake_r4_scan(
        portfolio: r4.Portfolio,
        exact_count: int,
        **_kwargs: object,
    ) -> SimpleNamespace:
        events.append("r4-reclosure")
        normalized = r4.normalize_portfolio(portfolio, expected_ticket_count=20)
        return SimpleNamespace(
            complete=True,
            best_exact_count=exact_count,
            best_portfolio=normalized,
            best_portfolio_sha256=r4.portfolio_sha256(normalized),
        )

    monkeypatch.setattr(vnd, "load_run2_starting_portfolio", fake_start)
    monkeypatch.setattr(vnd, "scan_three_cycle_neighborhood", fake_scan)
    monkeypatch.setattr(vnd, "_write_manifest", _ignore_call)
    monkeypatch.setattr(vnd, "_write_json_result", _ignore_call)
    monkeypatch.setattr(r4_runner, "_canonical_draw_space", lambda: object())
    monkeypatch.setattr(r4, "run_cross_swap_sweep", fake_r4_scan)
    _patch_candidate_head_guard(monkeypatch)
    round_result = vnd.run_task(
        REPOSITORY,
        run_data_dir=tmp_path / "round-cap",
        canonical_result_path=REPOSITORY
        / "docs/research/b649-k20-3ticket-cyclic-cross-swap-vnd-r1-result.json",
        now_fn=lambda: 1.0,
    )
    assert round_result["VND_ROUNDS_COMPLETED"] == 4
    assert round_result["FINAL_DISPOSITION"] == "BOUNDED_PROGRESS_NOT_CONVERGED"
    assert round_result["COMBINED_LOCAL_OPTIMUM_STATUS"] == "NOT_PROVEN"
    assert round_result["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
    assert events == [
        "scan-1",
        "r4-reclosure",
        "scan-2",
        "r4-reclosure",
        "scan-3",
        "r4-reclosure",
        "scan-4",
        "r4-reclosure",
    ]

    events.clear()
    clock_calls = 0

    def deadline_after_completed_scan() -> float:
        nonlocal clock_calls
        clock_calls += 1
        return (
            0.0
            if clock_calls <= 3
            else float(vnd.WALL_CLOCK_CAP_SECONDS + clock_calls)
        )

    post_scan_time_result = vnd.run_task(
        REPOSITORY,
        run_data_dir=tmp_path / "time-cap-after-scan",
        canonical_result_path=REPOSITORY
        / "docs/research/b649-k20-3ticket-cyclic-cross-swap-vnd-r1-result.json",
        now_fn=deadline_after_completed_scan,
    )
    assert events == ["scan-1"]
    assert post_scan_time_result["VND_ROUNDS_COMPLETED"] == 1
    assert post_scan_time_result["FINAL_DISPOSITION"] == "BOUNDED_PROGRESS_NOT_CONVERGED"
    assert post_scan_time_result["COMBINED_LOCAL_OPTIMUM_STATUS"] == "NOT_PROVEN"
    assert post_scan_time_result["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
    assert post_scan_time_result["ACCEPTED_3TICKET_MOVES"] == []
    assert post_scan_time_result["FINAL_EXACT"] == starting.exact_outcome_count

    calls = 0

    def expired_clock() -> float:
        nonlocal calls
        calls += 1
        return 0.0 if calls == 1 else float(vnd.WALL_CLOCK_CAP_SECONDS + 1)

    time_result = vnd.run_task(
        REPOSITORY,
        run_data_dir=tmp_path / "time-cap",
        canonical_result_path=REPOSITORY
        / "docs/research/b649-k20-3ticket-cyclic-cross-swap-vnd-r1-result.json",
        now_fn=expired_clock,
    )
    assert time_result["VND_ROUNDS_COMPLETED"] == 0
    assert time_result["FINAL_DISPOSITION"] == "BOUNDED_PROGRESS_NOT_CONVERGED"
    assert time_result["COMBINED_LOCAL_OPTIMUM_STATUS"] == "NOT_PROVEN"
    assert time_result["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"


def test_exact_count_is_acceptance_authority_and_equal_scores_are_rejected(
    starting: vnd.StartingPortfolio,
    tmp_path: Path,
) -> None:
    exact_calls: list[str] = []

    def scorer(portfolio: r4.Portfolio) -> ExactPortfolioProbability:
        digest = r4.portfolio_sha256(portfolio)
        exact_calls.append(digest)
        return _fake_exact(0)

    equal_state = vnd.scan_three_cycle_neighborhood(
        starting.portfolio,
        0,
        checkpoint_path=tmp_path / "equal.json",
        seen_hash_path=tmp_path / "equal.seen",
        run2_artifact_sha256=starting.run2_artifact_sha256,
        round_number=1,
        exact_scorer=scorer,
        max_raw_operations=432,
    )
    assert equal_state.best_exact_count == 0
    assert equal_state.best_move is None
    assert len(exact_calls) == equal_state.exact_evaluation_count
    assert len(exact_calls) > 1

    # A zero incumbent makes legal candidates survive U3; the scorer's exact
    # integer result, rather than a floating score, then controls the winner.
    exact_calls.clear()
    strict_state = vnd.scan_three_cycle_neighborhood(
        starting.portfolio,
        0,
        checkpoint_path=tmp_path / "strict.json",
        seen_hash_path=tmp_path / "strict.seen",
        run2_artifact_sha256=starting.run2_artifact_sha256,
        round_number=1,
        exact_scorer=lambda portfolio: (
            exact_calls.append(r4.portfolio_sha256(portfolio)) or _fake_exact(9)
        ),
        max_raw_operations=432,
    )
    assert strict_state.best_exact_count == 9
    assert strict_state.best_move is not None
    assert len(exact_calls) == strict_state.exact_evaluation_count
    assert strict_state.best_exact_count > 0
    assert Fraction(strict_state.best_exact_count, TOTAL_OUTCOMES) > Fraction(0, TOTAL_OUTCOMES)


def test_global_optimum_status_is_always_unknown(
    starting: vnd.StartingPortfolio,
) -> None:
    assert vnd._new_vnd_state(starting, 1.0)["global_k20_optimum_status"] == "UNKNOWN"
