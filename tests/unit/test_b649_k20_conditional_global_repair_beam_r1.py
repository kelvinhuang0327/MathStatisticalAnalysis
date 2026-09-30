"""Focused tests for the K20 conditional global repair beam.

Toy pools use a reference beam written straight from the Packet with brute-force marginals, and the
canonical evaluator, as oracles. One real destroy set that is neither in the pilot sample nor in the
parity sets exercises the real 49/6 space end to end at reduced width.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
from collections.abc import Sequence
from math import comb
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from lottolab.research import b649_k20_conditional_global_repair_beam_r1 as beam
from lottolab.research import b649_k20_five_ticket_exact_repair_r1 as five
from lottolab.research import b649_k20_global_residual_pool_repair_r1 as pool

# the global-pool tests' development set: neither in the pilot sample nor in the parity sets
DEV4 = (7, 11, 12, 14)
RESULT_PATH = beam.REPO_ROOT / beam.RESULT_RELATIVE_PATH
# (pool, frozen) toy cases: (15, 2) merges children and cuts between distinct coverages
TOY_CASES = ((14, 1), (15, 2), (14, 3))


def _toy_run(pool_size: int, frozen_size: int) -> tuple[five.Portfolio, beam.BeamRun]:
    universe = pool.build_universe(pool_size)
    remaining = beam.toy_remaining(pool_size, frozen_size)
    _, residual = pool.brute_force_marginals(pool_size, remaining)
    run = beam.run_beam(
        universe,
        remaining,
        beam.TOY_DEPTH,
        base_covered=comb(pool_size, 7) - residual,
        beam_width=beam.TOY_BEAM_WIDTH,
        expansion_width=beam.TOY_EXPANSION_WIDTH,
    )
    return remaining, run


@pytest.fixture(scope="module")
def reuse_document() -> dict[str, object]:
    return beam.read_reuse_artifact()


# ------------------------------------------------------------------ packet binding and reuse


def test_packet_constants_bind_width_children_and_depth() -> None:
    assert (beam.BEAM_WIDTH, beam.EXPANSION_WIDTH) == (8, 8)
    assert (beam.depth_for(4), beam.depth_for(5)) == (4, 5)
    with pytest.raises(ValueError, match="unsupported destroy size"):
        beam.depth_for(3)
    assert beam.REUSE_COMMIT == "b470fbfd2eae74bc3c567408746951a8f27c306a"
    assert five.START_COUNT == 313_239_661
    assert five.START_SHA256 == "7ce41ff21d5c0821f1d5dda683e23114086f5024fc6d98d4e574df5306659b1e"


def test_reuse_artifact_binds_the_same_six_sets_and_their_one_shot_top48(
    reuse_document: dict[str, object],
) -> None:
    sets, priors = beam.load_prior_sets(reuse_document)
    assert sets == pool.pilot_destroy_sets()
    assert sets == {
        4: ((12, 13, 17, 19), (0, 1, 14, 19), (1, 9, 15, 16)),
        5: ((2, 3, 4, 10, 11), (1, 7, 15, 16, 19), (5, 9, 10, 14, 17)),
    }
    assert len(priors) == 6
    for (size, positions), prior in priors.items():
        assert len(prior.top) == pool.GLOBAL_TOP_MARGINAL
        assert [entry.rank for entry in prior.top] == list(range(1, 49))
        assert prior.removed == five.destroy_positions(five.START_PORTFOLIO, positions).removed
        assert prior.best_count == five.START_COUNT and len(positions) == size
        assert prior.top_tickets <= prior.pool
    parity = pool.parity_destroy_sets()
    for size in beam.DESTROY_SIZES:
        assert not set(parity[size]) & set(sets[size])
    assert DEV4 not in sets[4] and DEV4 not in parity[4]


@pytest.mark.parametrize(
    "tamper",
    ["destroy_sets", "start_sha", "task_id", "top_rank", "removed_ticket", "missing_set"],
)
def test_reuse_binding_stops_on_any_drift(reuse_document: dict[str, object], tamper: str) -> None:
    document = copy.deepcopy(reuse_document)
    records = cast(list[dict[str, object]], document["PER_DESTROY_SET"])
    if tamper == "destroy_sets":
        document["DESTROY4_SETS"] = [
            [0, 1, 2, 3],
            *cast(list[object], document["DESTROY4_SETS"])[1:],
        ]
    elif tamper == "start_sha":
        document["START_SHA256"] = "0" * 64
    elif tamper == "task_id":
        document["TASK_ID"] = "SOMETHING_ELSE"
    elif tamper == "top_rank":
        cast(list[dict[str, object]], records[0]["GLOBAL_TOP"])[5]["RANK"] = 99
    elif tamper == "removed_ticket":
        records[1]["REMOVED_TICKETS"] = [[1, 2, 3, 4, 5, 6]]
    else:
        document["PER_DESTROY_SET"] = records[:-1]
    with pytest.raises(pool.StopConditionError) as stop:
        beam.load_prior_sets(document)
    assert stop.value.code == "REUSE_ARTIFACT_MISMATCH"


def test_a_missing_reuse_commit_is_its_own_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(beam, "REUSE_COMMIT", "0" * 40)
    with pytest.raises(pool.StopConditionError) as stop:
        beam.read_reuse_artifact()
    assert stop.value.code == "MISSING_REUSE_COMMIT"


def test_runtime_modules_resolve_inside_this_checkout(tmp_path: Path) -> None:
    files = beam.runtime_module_files()
    assert set(files) == {"CONDITIONAL_BEAM", "GLOBAL_RESIDUAL_POOL", "FIVE_TICKET_REPAIR"}
    assert all(
        Path(path).is_relative_to((beam.REPO_ROOT / "src").resolve()) for path in files.values()
    )
    with pytest.raises(pool.StopConditionError) as stop:
        beam.runtime_module_files(tmp_path)
    assert stop.value.code == "RUNTIME_MODULE_RESOLUTION_MISMATCH"


# ------------------------------------------------------------------ next tickets and beam order


def test_next_tickets_exclude_frozen_ones_and_break_ties_to_the_lexicographically_lowest() -> None:
    universe = pool.build_universe(8)
    tickets = [universe.ticket_at(i) for i in range(universe.tickets.shape[0])]
    marginals = np.full(len(tickets), 5, dtype=np.int32)
    high = [tickets[3], tickets[17], tickets[20], tickets[9]]
    for ticket in high:
        marginals[universe.index_of(ticket)] = 9
    frozen = [universe.index_of(tickets[17]), universe.index_of(tickets[0])]
    chosen = beam.next_ticket_indices(marginals, universe.tickets, frozen, 6)
    legal = sorted(
        (-int(marginals[i]), tickets[i]) for i in range(len(tickets)) if i not in set(frozen)
    )
    assert [universe.ticket_at(int(i)) for i in chosen] == [t for _, t in legal[:6]]
    assert all(int(i) not in frozen for i in chosen)
    assert [int(marginals[i]) for i in chosen[:3]] == [9, 9, 9]
    stats = beam.cutoff_stats(marginals, frozen, 5)
    assert (stats.above, stats.tied) == (3, len(tickets) - 4 - 1)
    with pytest.raises(ValueError, match="legal tickets"):
        beam.next_ticket_indices(marginals, universe.tickets, frozen, len(tickets) - 1)


def test_canonical_state_is_order_free_and_retention_is_coverage_then_identity() -> None:
    a, b, c = (1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 7), (2, 3, 4, 5, 6, 7)
    assert beam.canonical_state([c, (6, 5, 4, 3, 2, 1)]) == beam.canonical_state([a, c]) == (a, c)
    states = [
        beam.BeamState((b, c), 10),
        beam.BeamState((a, c), 10),
        beam.BeamState((a, b), 9),
        beam.BeamState((b,), 11),
    ]
    ordered = sorted(states, key=beam.retention_key)
    assert [state.tickets for state in ordered] == [(b,), (a, c), (b, c), (a, b)]


@pytest.mark.parametrize(("pool_size", "frozen_size"), TOY_CASES)
def test_beam_equals_the_reference_beam_and_the_canonical_evaluator(
    pool_size: int, frozen_size: int
) -> None:
    remaining, run = _toy_run(pool_size, frozen_size)
    reference = beam.reference_beam(
        pool_size, remaining, beam.TOY_DEPTH, beam.TOY_BEAM_WIDTH, beam.TOY_EXPANSION_WIDTH
    )
    for level, (ordered, kept, generated) in zip(run.levels, reference, strict=True):
        assert [(s.tickets, s.covered) for s in level.candidates] == ordered
        assert [(s.tickets, s.covered) for s in level.retained] == kept
        assert level.generated == generated
        assert level.generated - level.duplicates == level.unique
    geometry = five.Geometry(pool_size, 6, 3)
    recounter = five.CanonicalRecounter(geometry)
    for state in run.final.candidates:
        portfolio = five.normalize_portfolio((*remaining, *state.tickets), geometry=geometry)
        assert recounter.count(portfolio) == 7 * state.covered
    assert run.enumerations == 1 + sum(len(level.retained) for level in run.levels[:-1])
    assert all(e.tickets_scored == comb(pool_size, 6) for e in run.expansions)


def test_children_reached_twice_are_merged_and_keep_their_first_provenance() -> None:
    _, run = _toy_run(15, 2)
    assert run.duplicates > 0
    previous: dict[five.Portfolio, int] = {(): run.base_covered}
    for level in run.levels:
        for state in level.candidates:
            parent = cast(five.Portfolio, state.parent)
            assert parent in previous
            assert state.covered == previous[parent] + state.added_marginal
            assert state.tickets == beam.canonical_state((*parent, cast(five.Ticket, state.added)))
        previous = {state.tickets: state.covered for state in level.retained}


def test_a_wrong_base_coverage_stops_at_the_first_identity_check() -> None:
    universe = pool.build_universe(14)
    remaining = beam.toy_remaining(14, 1)
    _, residual = pool.brute_force_marginals(14, remaining)
    with pytest.raises(pool.StopConditionError) as stop:
        beam.run_beam(universe, remaining, 2, base_covered=comb(14, 7) - residual + 1)
    assert stop.value.code == "CONDITIONAL_ENUMERATION_IDENTITY_REFUTED"
    for depth, width, children in ((0, 8, 8), (1, 0, 8), (1, 8, 0)):
        with pytest.raises(ValueError, match="positive"):
            beam.run_beam(
                universe,
                remaining,
                depth,
                base_covered=0,
                beam_width=width,
                expansion_width=children,
            )


# ------------------------------------------------------------------ toy parity and its mutations


def test_toy_parity_has_zero_mismatches_and_every_guard_ran() -> None:
    tally = beam.run_toy_parity()
    families = cast(dict[str, dict[str, int]], tally.detail())
    assert tally.mismatches == 0 and tally.comparisons >= 150
    for guard in (
        "TOY_SOME_RETENTION_CUT_SEPARATES_DISTINCT_COVERAGES",
        "TOY_SOME_CHILD_WAS_DEDUPLICATED",
        "TOY_SOME_EXPANSION_CUT_INSIDE_A_TIE",
    ):
        assert families[guard] == {"COMPARISONS": 1, "MISMATCHES": 0}


def _highest_tie_break(
    marginals: pool.CountArray, tickets: pool.SubsetTable, frozen: Sequence[int], count: int
) -> pool.IndexArray:
    order = sorted(
        (i for i in range(marginals.size) if i not in set(frozen)),
        key=lambda i: (-int(marginals[i]), tuple(-int(v) for v in tickets[i])),
    )
    return np.array(order[:count], dtype=np.int64)


def _reversed_retention(state: beam.BeamState) -> tuple[int, tuple[tuple[int, ...], ...]]:
    return (-state.covered, tuple(tuple(-n for n in ticket) for ticket in state.tickets))


def _frozen_leak(
    marginals: pool.CountArray, tickets: pool.SubsetTable, frozen: Sequence[int], count: int
) -> pool.IndexArray:
    return pool.top_ticket_indices(marginals, tickets, count)


@pytest.mark.parametrize(
    "mutation", ["retention_ties_reversed", "tie_break_reversed", "frozen_leak"]
)
def test_toy_parity_catches_a_broken_beam(monkeypatch: pytest.MonkeyPatch, mutation: str) -> None:
    if mutation == "retention_ties_reversed":
        monkeypatch.setattr(beam, "retention_key", _reversed_retention)
    elif mutation == "tie_break_reversed":
        monkeypatch.setattr(beam, "next_ticket_indices", _highest_tie_break)
    else:
        monkeypatch.setattr(beam, "next_ticket_indices", _frozen_leak)
    try:
        tally = beam.run_toy_parity()
    except ValueError:  # a leaked frozen ticket makes an illegal portfolio in the recount
        return
    assert tally.mismatches > 0


# ------------------------------------------------------------------ the real 49/20 space


@pytest.fixture(scope="module")
def dev4() -> tuple[beam.DestroySetBeam, pool.ParityTally]:
    tally = pool.ParityTally()
    result = beam.beam_destroy_set(
        pool.build_universe(),
        4,
        DEV4,
        recounter=beam.CachedRecounter(five.CanonicalRecounter()),
        tally=tally,
        prior=None,
        beam_width=2,
        expansion_width=3,
        depth=2,
    )
    return result, tally


def test_real_expansions_score_the_complete_universe_conditionally(
    dev4: tuple[beam.DestroySetBeam, pool.ParityTally],
) -> None:
    result, _ = dev4
    run = result.run
    assert run.enumerations == 3 and sum(e.conditional for e in run.expansions) == 2
    assert run.tickets_scored == 3 * pool.TOTAL_TICKETS
    for expansion in run.expansions:
        assert expansion.identities["PASS"] is True
        assert expansion.residual_subsets == comb(49, 7) - expansion.parent.covered
        assert [c.position for c in expansion.children] == [1, 2, 3]
        marginals = [c.marginal for c in expansion.children]
        assert marginals == sorted(marginals, reverse=True)
        assert expansion.cutoff.above < 3 <= expansion.cutoff.above + expansion.cutoff.tied
    assert [len(level.retained) for level in run.levels] == [2, 2]
    assert run.levels[1].generated == 6


def test_real_inline_checks_ran_and_found_no_mismatch(
    dev4: tuple[beam.DestroySetBeam, pool.ParityTally],
) -> None:
    result, tally = dev4
    families = cast(dict[str, dict[str, int]], tally.detail())
    assert tally.mismatches == 0
    assert families["PILOT_ROOT_MARGINAL_EQUALS_DIRECT"]["COMPARISONS"] == 3
    assert families["PILOT_CONDITIONAL_MARGINAL_EQUALS_DIRECT"]["COMPARISONS"] == 6
    assert families["PILOT_RETAINED_STATE_COVERAGE_EQUALS_CANONICAL"]["COMPARISONS"] == 4
    assert families["PILOT_CONDITIONAL_MARGINAL_EQUALS_CANONICAL_DIFFERENCE"]["COMPARISONS"] == 2
    assert families["PILOT_FINAL_BEST_COUNT_TIE_EQUALS_CANONICAL"]["COMPARISONS"] >= 1
    assert result.depth0_top_matches_prior is False  # no prior was supplied for the dev set


def test_real_best_is_a_legal_recounted_portfolio(
    dev4: tuple[beam.DestroySetBeam, pool.ParityTally],
) -> None:
    result, _ = dev4
    best = result.run.best
    # the fixture stops at depth 2, so the portfolio is R plus two replacement tickets
    assert len(result.best_portfolio) == len(result.destroyed.remaining) + result.run.depth == 18
    assert len(set(result.best_portfolio)) == 18
    assert result.recount_of(best) == result.best_count == 7 * best.covered
    assert all(ticket not in result.destroyed.remaining for ticket in best.tickets)
    assert beam.ties_recounted(result)
    assert set(result.original_ranks) == {t for s in result.run.final.retained for t in s.tickets}
    assert all(1 <= rank <= pool.TOTAL_TICKETS for rank in result.original_ranks.values())


# ------------------------------------------------------------------ result document


def _fake_beam(
    size: int, positions: tuple[int, ...], extra: int, recount_extra: int
) -> beam.DestroySetBeam:
    """A beam whose only final state is the removed set, credited ``extra`` more 7-subsets."""

    destroyed = five.destroy_positions(five.START_PORTFOLIO, positions)
    state = beam.BeamState(
        beam.canonical_state(destroyed.removed), five.START_COUNT // 7 + extra, (), None, 0, 1
    )
    level = beam.BeamLevel(1, 1, 0, (state,), (state,))
    expansion = beam.Expansion(
        1,
        beam.BeamState((), 0),
        0,
        {"TICKETS_SCORED": pool.TOTAL_TICKETS, "PASS": True},
        (beam.NextTicket(destroyed.removed[0], 0, 0, 1),),
        beam.CutoffStats(0, 0, 1),
        1.0,
    )
    run = beam.BeamRun(destroyed.remaining, 0, 1, 8, 8, (expansion,), (level,))
    portfolio = five.normalize_portfolio((*destroyed.remaining, *state.tickets))
    return beam.DestroySetBeam(
        size=size,
        destroyed=destroyed,
        remaining_count=0,
        run=run,
        depth0_top_matches_prior=True,
        original_ranks={},
        recounts={portfolio: 7 * state.covered + recount_extra},
        best_portfolio=portfolio,
    )


def _document(beams: list[beam.DestroySetBeam], reuse: dict[str, object]) -> dict[str, object]:
    sets, priors = beam.load_prior_sets(reuse)
    return beam.build_result_document(
        sets=sets,
        priors=priors,
        beams=beams,
        start_record={},
        pins=[],
        reuse_record={},
        parity={
            "PARITY_SAMPLE_COUNT": 1,
            "PARITY_MISMATCHES": 0,
            "REAL_CONDITIONAL_MARGINAL_CHECKS": 100,
        },
        pilot_tally=pool.ParityTally(),
        wall_seconds=1.0,
        peak_memory=1,
        run_identity={"RUN_HEAD": "h", "RUN_TREE": "t", "RUN_TRACKED_TREE_CLEAN": "YES"},
        module_sha256="m",
        runtime_modules={},
        phase_seconds={},
        thread_env={},
    )


def _all_sets(extra: dict[int, int], recount_extra: int = 0) -> list[beam.DestroySetBeam]:
    order = [(size, p) for size in beam.DESTROY_SIZES for p in pool.pilot_destroy_sets()[size]]
    return [
        _fake_beam(size, p, extra.get(i, 0), recount_extra if i in extra else 0)
        for i, (size, p) in enumerate(order)
    ]


def test_document_reports_no_gain_when_the_beam_only_recovers_the_start(
    reuse_document: dict[str, object],
) -> None:
    document = _document(_all_sets({}), reuse_document)
    assert document["BEST_COUNT"] == five.START_COUNT and document["BEST_DELTA"] == 0
    assert document["SCIENTIFIC_RESULT"] == beam.RESULT_NO_IMPROVEMENT
    assert document["BEST_IS_START_PORTFOLIO"] is True
    assert document["BEST_SHA256"] == five.START_SHA256
    assert document["BEST_COUNT_TIE_COUNT"] == 6
    assert document["BEST_COUNT_TIE_DISTINCT_PORTFOLIOS"] == 1
    assert document["CANONICAL_RECOUNT_STATUS"] == "PASS"
    # the removed incumbent tickets sit far outside the one-shot top 48, yet that is no finding
    assert document["DID_WINNER_REQUIRE_TICKET_OUTSIDE_ORIGINAL_GLOBAL_TOP48"] == "YES"
    assert document["INTERACTION_AWARE_FINDING"] == beam.FINDING_NOT_ESTABLISHED
    assert document["CONDITIONAL_ENUMERATIONS"] == 6
    assert document["GLOBAL_TICKETS_SCORED"] == 6 * pool.TOTAL_TICKETS


def test_document_reports_a_gain_only_with_a_matching_canonical_recount(
    reuse_document: dict[str, object],
) -> None:
    improved = _document(_all_sets({4: 3}), reuse_document)
    assert improved["BEST_COUNT"] == five.START_COUNT + 21 and improved["BEST_DELTA"] == 21
    assert improved["BEST_DESTROY_SET"] == {"DESTROY_SIZE": 5, "POSITIONS": [1, 7, 15, 16, 19]}
    assert improved["SCIENTIFIC_RESULT"] == beam.RESULT_IMPROVED
    assert improved["INTERACTION_AWARE_FINDING"] == beam.FINDING_ESTABLISHED
    assert improved["BEST_COUNT_TIE_COUNT"] == 1
    miscounted = _document(_all_sets({4: 3}, recount_extra=7), reuse_document)
    assert miscounted["CANONICAL_RECOUNT_STATUS"] == "FAIL"
    assert miscounted["SCIENTIFIC_RESULT"] == beam.RESULT_NO_IMPROVEMENT
    assert miscounted["INTERACTION_AWARE_FINDING"] == beam.FINDING_NOT_ESTABLISHED


def test_document_needs_one_beam_per_pilot_set_in_sample_order(
    reuse_document: dict[str, object],
) -> None:
    beams = _all_sets({})
    with pytest.raises(ValueError, match="exactly one beam"):
        _document(beams[:-1], reuse_document)
    with pytest.raises(ValueError, match="exactly one beam"):
        _document([beams[1], beams[0], *beams[2:]], reuse_document)
    short = dataclasses.replace(beams[0], best_portfolio=beams[0].best_portfolio[:-1])
    with pytest.raises(ValueError, match="20-ticket"):
        _document([short, *beams[1:]], reuse_document)


def test_outside_top48_flag_follows_the_one_shot_top(reuse_document: dict[str, object]) -> None:
    _, priors = beam.load_prior_sets(reuse_document)
    prior = next(iter(priors.values()))
    inside = [entry.ticket for entry in prior.top[:4]]
    assert beam.requires_ticket_outside_top48(inside, prior) is False
    assert beam.requires_ticket_outside_top48([*inside[:3], prior.removed[0]], prior) is True
    rows = beam.classify_replacements([prior.removed[0]], prior, {prior.removed[0]: 5})
    assert rows[0]["IS_REMOVED_INCUMBENT_TICKET"] is True and rows[0]["ORIGINAL_GLOBAL_RANK"] == 5


# ------------------------------------------------------------------ runner guards


def test_pilot_refuses_to_overwrite_and_creates_nothing(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    output.write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        beam.run_pilot(tmp_path / "work", output)
    assert not (tmp_path / "work").exists()


def test_pilot_stops_before_scoring_when_parity_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def failing_parity(*_: object) -> dict[str, object]:
        return {
            "PARITY_SAMPLE_COUNT": 1,
            "PARITY_MISMATCHES": 1,
            "REAL_CONDITIONAL_MARGINAL_CHECKS": 100,
            "COVERAGE_MEETS_PACKET_MINIMUM": True,
        }

    def forbidden(*_: object, **__: object) -> beam.DestroySetBeam:
        raise AssertionError("a pilot set was scored after a parity failure")

    monkeypatch.setattr(beam, "run_parity", failing_parity)
    monkeypatch.setattr(beam, "beam_destroy_set", forbidden)
    output = tmp_path / "result.json"
    with pytest.raises(pool.StopConditionError) as stop:
        beam.run_pilot(tmp_path / "work", output)
    assert stop.value.code == "PARITY_MISMATCH" and not output.exists()


def test_command_line_reports_a_stop_condition_with_exit_code_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def stopped(*_: object) -> dict[str, object]:
        raise pool.StopConditionError("PARITY_MISMATCH", "forced")

    monkeypatch.setattr(beam, "run_pilot", stopped)
    code = beam.main(["pilot", "--workdir", str(tmp_path), "--output", str(tmp_path / "o.json")])
    assert code == 2 and "STOP: PARITY_MISMATCH" in capsys.readouterr().err


# ------------------------------------------------------------------ committed artifact


def test_result_artifact_is_self_consistent() -> None:
    if not RESULT_PATH.exists():
        pytest.skip("the pilot result has not been produced yet")
    document = cast(dict[str, object], json.loads(RESULT_PATH.read_text(encoding="utf-8")))
    records = cast(list[dict[str, object]], document["PER_DESTROY_SET"])
    assert document["TASK_ID"] == beam.TASK_ID and len(records) == 6
    assert document["PARITY_MISMATCHES"] == 0 and document["CANONICAL_RECOUNT_STATUS"] == "PASS"
    assert cast(int, document["REAL_CONDITIONAL_MARGINAL_CHECKS"]) >= 100
    enumerations = 0
    for record in records:
        levels = cast(list[dict[str, object]], record["LEVELS"])
        expansions = cast(list[dict[str, object]], record["EXPANSIONS"])
        size = cast(int, record["DESTROY_SIZE"])
        assert record["DEPTH"] == size and len(levels) == size
        assert len(expansions) == record["CONDITIONAL_ENUMERATIONS"]
        assert len(expansions) == 1 + sum(cast(int, lv["RETAINED_COUNT"]) for lv in levels[:-1])
        assert all(e["TICKETS_SCORED"] == pool.TOTAL_TICKETS for e in expansions)
        assert all(len(cast(list[object], e["NEXT_TICKETS"])) == 8 for e in expansions)
        assert record["BEAM_STATES_GENERATED"] == 8 * len(expansions)
        assert record["DEPTH0_TOP48_EQUALS_PRIOR_ARTIFACT"] is True
        assert record["FINAL_BEST_COUNT_TIES_CANONICALLY_RECOUNTED"] is True
        assert record["BEST_CANONICAL_RECOUNT"] == record["BEST_COUNT"]
        enumerations += len(expansions)
    assert document["CONDITIONAL_ENUMERATIONS"] == enumerations
    assert document["GLOBAL_TICKETS_SCORED"] == enumerations * pool.TOTAL_TICKETS
    best = max(cast(int, record["BEST_COUNT"]) for record in records)
    assert document["BEST_COUNT"] == best
    assert document["BEST_DELTA"] == best - five.START_COUNT
    winner = document["WINNER_REPLACEMENTS_VS_ONE_SHOT"]
    outside = any(
        not row["IN_ORIGINAL_GLOBAL_TOP48"] for row in cast(list[dict[str, object]], winner)
    )
    assert document["DID_WINNER_REQUIRE_TICKET_OUTSIDE_ORIGINAL_GLOBAL_TOP48"] == (
        "YES" if outside else "NO"
    )
    module = beam.REPO_ROOT / beam.MODULE_RELATIVE_PATH
    assert document["SOURCE_MODULE_SHA256"] == hashlib.sha256(module.read_bytes()).hexdigest()
