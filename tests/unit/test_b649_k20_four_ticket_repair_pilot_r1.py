"""Small exhaustive or controlled tests; never launch the scientific batch."""

from __future__ import annotations

import itertools
import random
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from lottolab.research import b649_k20_four_ticket_repair_pilot_r1 as pilot


def baseline() -> pilot.Portfolio:
    return pilot.SEALED_GEOMETRY_K20_VERSIONS["8.0.0"].tickets


def test_pinned_baseline_and_fixed_plan() -> None:
    entry = pilot.SEALED_GEOMETRY_K20_VERSIONS["8.0.0"]
    pilot.verify_sealed_geometry_portfolio(entry)
    assert entry.portfolio_sha256 == pilot.BASELINE_SHA
    assert entry.official_any_prize_probability * pilot.DENOMINATOR == pilot.BASELINE_COUNT
    plan = pilot.fixed_plan(pilot.Config())
    assert plan == pilot.fixed_plan(pilot.Config())
    destroys = plan["destroy_sets_zero_based_in_execution_order"]
    assert len(destroys) == len(set(destroys)) == 32
    assert all(
        len(d) == 4 and tuple(sorted(d)) == d and 0 <= min(d) <= max(d) < 20 for d in destroys
    )
    seeds = list(itertools.chain.from_iterable(plan["repair_seeds"]))
    assert len(seeds) == len(set(seeds)) == 256


@pytest.mark.parametrize(
    "tickets",
    [
        ((1, 2, 3, 4, 5, 6),),
        ((1, 2, 3, 4, 5, 5),) * 20,
        ((0, 2, 3, 4, 5, 6),) * 20,
        ((True, 2, 3, 4, 5, 6),) * 20,
        ((1, 2, 3, 4, 5, 50),) * 20,
        ((1, 2, 3, 4, 5, 6),) * 20,
    ],
)
def test_illegal_and_duplicate_tickets(tickets: pilot.Portfolio) -> None:
    assert not pilot.legal(tickets)
    assert pilot.legal(baseline())


def test_seven_event_independent_full_main_special_enumeration() -> None:
    # A small lottery with six main numbers plus one special; native event
    # is evaluated independently with Python sets for EVERY outcome.
    numbers = set(range(1, 13))
    portfolios = (
        ((1, 2, 3, 4, 5, 6),),
        ((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 6)),
        ((1, 2, 3, 4, 5, 6), (2, 4, 6, 7, 8, 9)),
    )
    for portfolio in portfolios:
        direct_count = sampled_count = 0
        for draw_tuple in itertools.combinations(sorted(numbers), 6):
            draw = set(draw_tuple)
            for special in numbers - draw:
                direct = any(
                    len(set(t) & draw) >= 3 or (len(set(t) & draw) == 2 and special in t)
                    for t in portfolio
                )
                samples = np.array(
                    [pilot.native.ticket_mask((*draw_tuple, special))], dtype=np.uint64
                )
                surrogate = bool(pilot.union_coverage(portfolio, samples)[0])
                assert direct == surrogate
                direct_count += direct
                sampled_count += surrogate
        assert direct_count == sampled_count
        assert 0 < direct_count < 5544


def test_special_rescue_failure_and_duplicate_union() -> None:
    ticket = (1, 2, 3, 4, 5, 6)
    # Two main hits; special supplies third. Then same draw, special outside.
    draw = (1, 2, 7, 8, 9, 10)
    samples = np.array([pilot.native.ticket_mask((*draw, s)) for s in (3, 11)], dtype=np.uint64)
    assert pilot.coverage(ticket, samples).tolist() == [True, False]
    single = pilot.union_coverage((ticket,), samples)
    assert np.array_equal(single, pilot.union_coverage((ticket, ticket), samples))
    # One main hit plus special still cannot supply three.
    assert not pilot.union_coverage(
        (ticket,), np.array([pilot.native.ticket_mask((1, 7, 8, 9, 10, 11, 2))], dtype=np.uint64)
    )[0]


def test_samples_uniform_size_and_determinism() -> None:
    config = replace(pilot.Config(), surrogate_seven_set_samples=160)
    first = pilot.seven_samples(config)
    assert np.array_equal(first, pilot.seven_samples(config))
    assert np.all(np.bitwise_count(first) == 7)
    assert np.all(first < (1 << 49))


def test_repair_determinism_legality_and_union() -> None:
    config = replace(pilot.Config(), surrogate_seven_set_samples=160, repair_ticket_pool_per_step=7)
    samples = pilot.seven_samples(config)

    def execute() -> tuple[pilot.Portfolio | None, list[pilot.Record]]:
        return pilot.repair(
            baseline(),
            (0, 3, 12, 18),
            912,
            samples,
            config,
            pilot.Budget(config, pilot.time.monotonic()),
        )

    result, steps = execute()
    assert (result, steps) == execute()
    assert result is not None and pilot.legal(result)
    retained = {t for i, t in enumerate(baseline()) if i not in (0, 3, 12, 18)}
    assert retained <= set(result)
    expected = [
        any((int(s) & pilot.native.ticket_mask(t)).bit_count() >= 3 for t in result)
        for s in samples
    ]
    assert pilot.union_coverage(result, samples).tolist() == expected
    assert all(
        s["selected_gain"] >= s["max_gain"] - 0.2 * (s["max_gain"] - s["min_gain"]) for s in steps
    )


def test_shortfall_bounded_attempts_and_empty_repair() -> None:
    config = replace(
        pilot.Config(),
        repair_ticket_pool_per_step=64,
        pool_attempt_limit=2,
        surrogate_seven_set_samples=8,
    )
    pool, attempts = pilot.ticket_pool(random.Random(1), set(), config)
    assert attempts == 2 and len(pool) == 2
    config = replace(config, pool_attempt_limit=0)
    result, steps = pilot.repair(
        baseline(),
        (0, 1, 2, 3),
        1,
        pilot.seven_samples(config),
        config,
        pilot.Budget(config, pilot.time.monotonic()),
    )
    assert result is None and steps[0]["pool_size"] == 0


def test_rcl_threshold_and_equal_gain_order() -> None:
    rng = random.Random(7)
    assert {pilot.choose_rcl([0, 79, 80, 100], rng, 0.2) for _ in range(100)} == {2, 3}
    assert pilot.choose_rcl([1, 1, 1], random.Random(9), 0.2) == random.Random(9).choice([0, 1, 2])


def test_proven_isomorphism_has_full_number_witness() -> None:
    left = baseline()
    mapping = list(range(49, 0, -1))
    right = pilot.canonical(tuple(tuple(mapping[n - 1] for n in t) for t in left))
    witness, nodes = pilot.prove_isomorphism(left, right)
    assert witness is not None and nodes > 0
    assert pilot.check_bijection(left, right, witness)
    assert not pilot.check_bijection(left, right, [1] * 49)
    assert pilot.prove_isomorphism(left, right, max_nodes=0)[0] is None


def test_same_invariants_cannot_replace_isomorphism_proof() -> None:
    # Three edges forming a triangle versus a star: same pairwise overlaps,
    # but different full incidence. Padding with unused numbers is implicit.
    left = ((1, 2), (2, 3), (1, 3))
    right = ((1, 2), (1, 3), (1, 4))
    assert pilot.prove_isomorphism(left, right)[0] is None


def test_rank_ties_use_canonical_lexicographic_order() -> None:
    records: list[pilot.Record] = [
        {"tickets": ((i,),), "status": "NOT_SELECTED", "surrogate_delta": gain}
        for i, gain in ((3, 4), (2, 5), (1, 5))
    ]
    chosen = pilot.rank_and_mark(records, 2)
    assert [r["tickets"] for r in chosen] == [((1,),), ((2,),)]
    assert [r["status"] for r in records] == ["NOT_SELECTED", "UNFINISHED", "UNFINISHED"]


def test_budget_time_memory_and_exact_call_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    config = replace(pilot.Config(), wall_seconds=4, max_exact_calls=1)
    clock = [0.0]
    budget = pilot.Budget(config, 0.0, clock=lambda: clock[0])
    budget.reserve_exact()
    with pytest.raises(pilot.BudgetStop, match="EXACT_CALL_LIMIT"):
        budget.reserve_exact()
    assert budget.calls == 1
    clock[0] = 4.0
    with pytest.raises(pilot.BudgetStop, match="WALL_CLOCK"):
        budget.check()
    clock[0] = 0.0
    monkeypatch.setattr(pilot, "peak_memory_bytes", lambda: config.memory_bytes)
    with pytest.raises(pilot.BudgetStop, match="MEMORY"):
        budget.check()


def test_filter_identity_duplicate_and_certificate_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    tickets = list(baseline())
    tickets[0] = (1, 2, 3, 4, 5, 49)
    candidate = pilot.canonical(tickets)
    old: pilot.Record = {
        "tickets": candidate,
        "status": "PROVEN_CLOSED",
        "exact_count": None,
        "upper_bound": pilot.BASELINE_COUNT,
    }

    def controlled_proof(_row: pilot.Record) -> pilot.Record:
        return {"kind": "controlled certificate"}

    monkeypatch.setattr(pilot, "validate_evidence", controlled_proof)
    records: list[pilot.Record] = [
        {"tickets": t, "status": "UNFINISHED"} for t in (baseline(), candidate, candidate)
    ]
    pilot.filter_proposals(
        records, baseline(), [old], pilot.Budget(pilot.Config(), pilot.time.monotonic())
    )
    assert [r["status"] for r in records] == [
        "BASELINE_OR_DUPLICATE",
        "PROVEN_CLOSED",
        "BASELINE_OR_DUPLICATE",
    ]
    assert records[1]["exact_count"] is None


def test_changed_original_evidence_rejected(tmp_path: Path) -> None:
    source = tmp_path / "original.json"
    source.write_bytes(b"{}")
    with pytest.raises(ValueError, match="original file changed"):
        pilot.validate_evidence(
            {"status": "KNOWN_EXACT", "evidence": {"path": str(source), "sha256": "wrong"}}
        )


def test_actual_direct_evidence_and_closure_domain() -> None:
    rows, metadata = pilot.read_history(pilot.HISTORY_ROOT)
    assert metadata["records"] == 5160
    known = next(r for r in rows if r["status"] == "KNOWN_EXACT")
    closed = next(r for r in rows if r["status"] == "PROVEN_CLOSED")
    assert pilot.validate_evidence(known)["kind"] == "FULL_OUTCOME_CENSUS_REUSED"
    proof = pilot.validate_evidence(closed)
    assert proof["exact_count"] is None and proof["upper_bound"] == pilot.BASELINE_COUNT
    forged = dict(closed, tickets=baseline())
    forged["evidence"] = dict(
        closed["evidence"], number_bijection_candidate_to_certificate=[1] * 49
    )
    with pytest.raises(ValueError, match="bijection"):
        pilot.validate_evidence(forged)


def test_interrupted_exact_limit_preserves_unfinished(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def complete_draws(_n: int, _k: int) -> pilot.Masks:
        # Zero-copy controlled seam, never sent to the real exact evaluator.
        return np.broadcast_to(np.array([0], dtype=np.uint64), (13983816,))

    def controlled_exact(
        _portfolio: pilot.Portfolio,
        *,
        draws: pilot.Masks,
        chunk_size: int,
    ) -> pilot.native.ExactPortfolioProbability:
        assert draws.size == 13983816 and chunk_size > 0
        return pilot.native.ExactPortfolioProbability(13983816, 43, 0, 123)

    monkeypatch.setattr(pilot.native, "all_main_draw_masks", complete_draws)
    monkeypatch.setattr(pilot.native, "evaluate_portfolio", controlled_exact)
    config = replace(pilot.Config(), max_exact_calls=1)
    budget = pilot.Budget(config, pilot.time.monotonic())
    records: list[pilot.Record] = [
        {"tickets": baseline(), "status": "UNFINISHED", "exact_rank": i} for i in (1, 2)
    ]
    with pytest.raises(pilot.BudgetStop, match="EXACT_CALL_LIMIT"):
        pilot.score_selected(records, budget, tmp_path, records)
    assert [r["status"] for r in records] == ["NEW_EXACT", "UNFINISHED"]
    assert budget.calls == 1
    assert (tmp_path / "candidates.jsonl").is_file()


def test_small_native_count_uses_full_generator() -> None:
    portfolio = ((1, 2, 3), (3, 4, 5))
    draws = pilot.native.all_main_draw_masks(7, 3)
    result = pilot.native.evaluate_portfolio(
        portfolio, pool_size=7, draw_size=3, draws=draws, outright_matches=3
    )
    count = 0
    for draw in itertools.combinations(range(1, 8), 3):
        for special in set(range(1, 8)) - set(draw):
            count += any(
                len(set(t) & set(draw)) >= 3 or (len(set(t) & set(draw)) == 2 and special in t)
                for t in portfolio
            )
    assert result.official_any_prize_outcome_count == count
    with pytest.raises(ValueError, match="complete"):
        pilot.native.evaluate_portfolio(portfolio, pool_size=7, draw_size=3, draws=draws[:2])


def test_single_batch_no_restart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Reject configuration changes before creating a marker or invoking evaluator.
    with pytest.raises(ValueError, match="fixed Packet"):
        pilot.run_batch(tmp_path, config=replace(pilot.Config(), seed=1))
    assert not (tmp_path / "batch_started.json").exists()

    def forbidden_draws(_n: int, _k: int) -> pilot.Masks:
        pytest.fail("source preflight must refuse before generating draws")

    monkeypatch.setattr(pilot.native, "all_main_draw_masks", forbidden_draws)
    monkeypatch.setattr(
        pilot,
        "source_identity",
        lambda: {"worktree": str(tmp_path), "branch": "wrong", "evaluator_git_blob": "wrong"},
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        pilot.run_batch(tmp_path)


def test_existing_batch_marker_refuses_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / ".task-data" / pilot.TASK_ID
    root.mkdir(parents=True)
    marker = root / "batch_started.json"
    marker.write_text("prior attempt; must stay unchanged")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        pilot,
        "source_identity",
        lambda: {
            "worktree": str(tmp_path),
            "branch": pilot.BRANCH,
            "evaluator_git_blob": pilot.EVALUATOR_BLOB,
        },
    )

    def git_base(*_args: str) -> str:
        return pilot.BASE_HEAD

    monkeypatch.setattr(pilot, "git", git_base)
    with pytest.raises(FileExistsError):
        pilot.run_batch(root)
    assert marker.read_text() == "prior attempt; must stay unchanged"
