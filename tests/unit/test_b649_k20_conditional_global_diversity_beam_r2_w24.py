"""Focused tests for the K20 conditional global diversity beam (width 24, signature first).

Toy lotteries use a reference diversity beam written from the frozen rule text with brute-force
marginals and explicit signature sets, R1's own ``run_beam`` and the canonical evaluator as
oracles. One real destroy set exercises the bitmap signature engine in the real 49/6 space.
"""

from __future__ import annotations

import dataclasses
import hashlib
import itertools
import json
import subprocess
from collections.abc import Callable, Sequence
from math import comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_conditional_global_diversity_beam_r2_w24 as div
from lottolab.research import b649_k20_conditional_global_repair_beam_r1 as r1
from lottolab.research import b649_k20_five_ticket_exact_repair_r1 as five
from lottolab.research import b649_k20_global_residual_pool_repair_r1 as pool

DEV4 = (7, 11, 12, 14)
# (pool, frozen, beam width, expansion width): cuts inside equal-coverage ties are frequent
TOY_CASES = ((14, 1, 2, 6), (14, 2, 3, 6), (15, 2, 3, 6), (15, 3, 4, 8), (16, 2, 2, 6))


def _state(tickets: Sequence[Sequence[int]], covered: int = 100) -> r1.BeamState:
    return r1.BeamState(r1.canonical_state(tickets), covered)


def _toy_matches_reference(
    pool_size: int, frozen_size: int, beam_width: int, expansion_width: int
) -> bool:
    """Module diversity beam equals the reference beam on every level of one toy case."""

    universe = pool.build_universe(pool_size)
    geometry = five.Geometry(pool_size, pool.TICKET_SIZE, pool.OUTRIGHT)
    remaining = r1.toy_remaining(pool_size, frozen_size)
    _, residual = pool.brute_force_marginals(pool_size, remaining)
    ran = div.run_policy_beam(
        universe,
        remaining,
        div.TOY_DEPTH,
        base_covered=comb(pool_size, 7) - residual,
        beam_width=beam_width,
        expansion_width=expansion_width,
        policy=div.POLICY_DIVERSITY,
        distance=div.SignatureDistance(remaining, geometry),
    )
    reference = div.reference_diversity_beam(
        pool_size, remaining, div.TOY_DEPTH, beam_width, expansion_width, div.POLICY_DIVERSITY
    )
    return all(
        [(s.tickets, s.covered) for s in level.candidates] == ordered
        and [(s.tickets, s.covered) for s in level.retained] == kept
        and level.generated == generated
        for level, (ordered, kept, generated) in zip(ran.run.levels, reference, strict=True)
    )


# ------------------------------------------------------------------ packet binding


def test_packet_constants_bind_width_children_depth_and_control() -> None:
    assert (div.BEAM_WIDTH, div.EXPANSION_WIDTH, div.CONTROL_BEAM_WIDTH) == (24, 8, 8)
    assert (r1.depth_for(4), r1.depth_for(5)) == (4, 5)
    assert div.TASK_ID == "B649_K20_CONDITIONAL_GLOBAL_DIVERSITY_BEAM_R2"
    assert (div.CONTROL_DESTROY_SIZE, div.CONTROL_POSITIONS) == (4, (12, 13, 17, 19))
    assert pool.pilot_destroy_sets()[4][0] == div.CONTROL_POSITIONS
    assert div.START_COUNT == 313_239_661
    assert div.START_SHA256 == "7ce41ff21d5c0821f1d5dda683e23114086f5024fc6d98d4e574df5306659b1e"
    assert hashlib.sha256(div.RULE_TEXT.encode()).hexdigest() == div.RULE_SHA256
    assert div.R1_RESULT_COMMIT.startswith("3cab702f") and div.R1_COMMIT.startswith("bf8f41d7")


def test_rule_text_states_every_packet_clause() -> None:
    text = div.RULE_TEXT
    for clause in (
        "BEAM_WIDTH is 24",
        "lowest canonical state SHA-256 first",
        "minimum distance to the already-retained states OF THE SAME TIE GROUP",
        "residual-coverage signature symmetric difference",
        "replacement-ticket-set symmetric difference",
        "lowest canonical state SHA-256.",
        "CONTROL",
        "BEAM_WIDTH 8",
    ):
        assert clause in text


def test_preregistration_file_embeds_the_rule_text_and_is_frozen_by_hash() -> None:
    path = div.REPO_ROOT / div.PREREGISTRATION_RELATIVE_PATH
    assert div.RULE_TEXT in path.read_text(encoding="utf-8")
    assert div.RULE_SHA256 in path.read_text(encoding="utf-8")


def test_the_r1_result_is_pinned_by_hash() -> None:
    document, digest = div.read_r1_result()
    assert digest == div.R1_RESULT_SHA256
    assert document["TASK_ID"] == r1.TASK_ID and document["BEST_COUNT"] == five.START_COUNT


def test_a_changed_r1_result_is_its_own_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(div, "R1_RESULT_SHA256", "0" * 64)
    with pytest.raises(pool.StopConditionError) as stop:
        div.read_r1_result()
    assert stop.value.code == "R1_RESULT_IDENTITY_MISMATCH"


def test_runtime_modules_resolve_inside_this_checkout(tmp_path: Path) -> None:
    files = div.runtime_module_files()
    assert set(files) == {
        "DIVERSITY_BEAM",
        "CONDITIONAL_BEAM_R1",
        "GLOBAL_RESIDUAL_POOL",
        "FIVE_TICKET_REPAIR",
    }
    assert all(
        Path(path).is_relative_to((div.REPO_ROOT / "src").resolve()) for path in files.values()
    )
    with pytest.raises(pool.StopConditionError) as stop:
        div.runtime_module_files(tmp_path)
    assert stop.value.code == "RUNTIME_MODULE_RESOLUTION_MISMATCH"


# ------------------------------------------------------------------ preregistration guard


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_preregistration_must_be_committed_clean_and_hold_the_rule(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    path = repo / div.PREREGISTRATION_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    _git(repo, "init", "-q")
    path.write_text("not the rule\n", encoding="utf-8")
    with pytest.raises(pool.StopConditionError) as stop:
        div.verify_preregistration(repo)
    assert stop.value.code == "PREREGISTRATION_RULE_MISMATCH"
    path.write_text(f"{div.RULE_TEXT}\n", encoding="utf-8")
    with pytest.raises(pool.StopConditionError) as stop:
        div.verify_preregistration(repo)
    assert stop.value.code == "PREREGISTRATION_NOT_COMMITTED"
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "freeze")
    frozen = div.verify_preregistration(repo)
    assert frozen["PREREGISTRATION_COMMITTED_AND_CLEAN_BEFORE_EXECUTION"] is True
    assert (
        frozen["RULE_SHA256"] == div.RULE_SHA256
        and len(str(frozen["PREREGISTRATION_COMMIT"])) == 40
    )
    path.write_text(f"{div.RULE_TEXT}\nedited after the freeze\n", encoding="utf-8")
    with pytest.raises(pool.StopConditionError) as stop:
        div.verify_preregistration(repo)
    assert stop.value.code == "PREREGISTRATION_NOT_COMMITTED"


# ------------------------------------------------------------------ distances and selection


def test_state_identity_is_the_compact_json_sha_of_the_sorted_replacement_tickets() -> None:
    tickets = ((7, 8, 9, 10, 11, 12), (1, 2, 3, 4, 5, 6))
    payload = json.dumps([[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]], separators=(",", ":"))
    assert div.state_sha256(tickets) == hashlib.sha256(payload.encode()).hexdigest()
    assert div.state_sha256(tickets) == div.state_sha256(tuple(reversed(tickets)))
    assert div.ticket_set_distance(tickets[:1], tickets) == 1
    assert div.ticket_set_distance(tickets, tickets) == 0


def _fake_distance(
    table: dict[frozenset[tuple[tuple[int, ...], ...]], tuple[int, int]],
) -> Callable[[r1.BeamState, r1.BeamState], tuple[int, int]]:
    def distance(first: r1.BeamState, second: r1.BeamState) -> tuple[int, int]:
        return table[frozenset((first.tickets, second.tickets))]

    return distance


def _group(count: int) -> list[r1.BeamState]:
    return [_state([(i + 1, i + 2, i + 3, i + 4, i + 5, i + 6)]) for i in range(count)]


def _by_sha(states: list[r1.BeamState]) -> list[r1.BeamState]:
    return sorted(states, key=lambda s: div.state_sha256(s.tickets))


def test_selection_keeps_the_lowest_sha_first_then_the_farthest_in_signature() -> None:
    group = _by_sha(_group(4))
    low, a, b, c = group
    table = {
        frozenset((low.tickets, a.tickets)): (5, 9),
        frozenset((low.tickets, b.tickets)): (50, 1),
        frozenset((low.tickets, c.tickets)): (7, 9),
        frozenset((a.tickets, b.tickets)): (0, 0),
        frozenset((a.tickets, c.tickets)): (0, 0),
        frozenset((b.tickets, c.tickets)): (0, 0),
    }
    chosen = div.select_diverse(group, 2, _fake_distance(table))
    assert chosen.selected == (low, b)
    assert chosen.min_signature == (None, 50) and chosen.min_ticket == (None, 1)
    three = div.select_diverse(group, 3, _fake_distance(table))
    assert three.selected[:2] == (low, b)
    # third pick: a and c are at (5 or 0, ...) / (7 or 0, ...) from {low, b}; min over retained
    assert three.selected[2] in (a, c)


def test_selection_maximises_the_minimum_distance_not_the_distance_to_the_first() -> None:
    group = _by_sha(_group(4))
    low, a, b, c = group
    table = {
        frozenset((low.tickets, a.tickets)): (10, 0),
        frozenset((low.tickets, b.tickets)): (10, 0),
        frozenset((low.tickets, c.tickets)): (9, 0),
        frozenset((a.tickets, b.tickets)): (1, 0),
        frozenset((a.tickets, c.tickets)): (8, 0),
        frozenset((b.tickets, c.tickets)): (8, 0),
    }
    chosen = div.select_diverse(group, 3, _fake_distance(table))
    # after {low, a}: c has min(9, 8) = 8 and b has min(10, 1) = 1, so c is third, b never needed
    assert chosen.selected == (low, a, c)
    assert chosen.min_signature == (None, 10, 8)


def test_secondary_distance_decides_only_when_the_primary_minimum_ties() -> None:
    group = _by_sha(_group(3))
    low, a, b = group
    tied = {
        frozenset((low.tickets, a.tickets)): (4, 1),
        frozenset((low.tickets, b.tickets)): (4, 3),
        frozenset((a.tickets, b.tickets)): (0, 0),
    }
    assert div.select_diverse(group, 2, _fake_distance(tied)).selected == (low, b)
    primary_first = {**tied, frozenset((low.tickets, a.tickets)): (5, 1)}
    assert div.select_diverse(group, 2, _fake_distance(primary_first)).selected == (low, a)


def test_swapping_the_two_distances_changes_a_selection_the_rule_decides() -> None:
    # the toy lotteries cannot tell the two distance orders apart (their ticket-set distances are
    # nearly constant), so the rank order of primary over secondary is pinned here
    group = _by_sha(_group(3))
    low, a, b = group
    table = {
        frozenset((low.tickets, a.tickets)): (9, 1),
        frozenset((low.tickets, b.tickets)): (2, 5),
        frozenset((a.tickets, b.tickets)): (0, 0),
    }
    distance = _fake_distance(table)

    def swapped(first: r1.BeamState, second: r1.BeamState) -> tuple[int, int]:
        primary, secondary = distance(first, second)
        return (secondary, primary)

    assert div.select_diverse(group, 2, distance).selected == (low, a)
    assert div.select_diverse(group, 2, swapped).selected == (low, b)


def test_the_lowest_sha_breaks_a_complete_tie() -> None:
    group = _by_sha(_group(4))
    flat = {
        frozenset(pair): (3, 3) for pair in itertools.combinations([s.tickets for s in group], 2)
    }
    chosen = div.select_diverse(group, 3, _fake_distance(flat))
    assert [s.tickets for s in chosen.selected] == [s.tickets for s in group[:3]]


def test_selection_is_independent_of_input_order() -> None:
    group = _by_sha(_group(6))
    table = {
        frozenset(pair): (hash(pair) % 7 + 1, hash(pair) % 5)
        for pair in itertools.combinations([s.tickets for s in group], 2)
    }
    distance = _fake_distance(table)
    expected = div.select_diverse(group, 4, distance).selected
    assert div.select_diverse(list(reversed(group)), 4, distance).selected == expected
    assert div.select_diverse(group[3:] + group[:3], 4, distance).selected == expected


def test_selection_validates_its_group_and_slots() -> None:
    group = _group(3)
    distance = _fake_distance({})
    with pytest.raises(ValueError, match="between 1 and"):
        div.select_diverse(group, 0, distance)
    with pytest.raises(ValueError, match="between 1 and"):
        div.select_diverse(group, 3, distance)
    mixed = [group[0], dataclasses.replace(group[1], covered=99), group[2]]
    with pytest.raises(ValueError, match="one exact coverage"):
        div.select_diverse(mixed, 2, distance)
    single = div.select_diverse(group, 1, distance)
    assert single.selected == (_by_sha(group)[0],) and single.pair_signature == ()


# ------------------------------------------------------------------ retention


def _levelled(covers: Sequence[int]) -> list[r1.BeamState]:
    """Candidates ordered like R1: coverage descending, then ascending sorted ticket tuple."""

    states = [
        _state([(i + 1, i + 2, i + 3, i + 4, i + 5, i + 6)], cover)
        for i, cover in enumerate(covers)
    ]
    return sorted(states, key=r1.retention_key)


def _no_distance(first: r1.BeamState, second: r1.BeamState) -> tuple[int, int]:
    return (hash((first.tickets, second.tickets)) % 11, 0)


def test_lowest_identity_policy_is_r1s_cut_and_reports_the_ties() -> None:
    candidates = _levelled([9, 9, 9, 9, 7, 7, 5])
    kept, ties = div.retain_states(1, candidates, 3, div.POLICY_LOWEST_IDENTITY, None)
    assert kept == tuple(candidates[:3])
    assert (ties.tie_groups, ties.max_group_size, ties.tied_states) == (2, 4, 6)
    assert (ties.cutoff_group_size, ties.cutoff_slots, ties.selection) == (4, 3, None)


def test_diversity_never_displaces_a_higher_coverage_group_and_keeps_fitting_groups_whole() -> None:
    candidates = _levelled([9, 9, 7, 7, 7, 7, 5])
    kept, ties = div.retain_states(2, candidates, 4, div.POLICY_DIVERSITY, _no_distance)
    top = [s for s in candidates if s.covered == 9]
    assert [s.tickets for s in kept[:2]] == [
        s.tickets for s in _by_sha(top)
    ]  # whole group, lowest SHA first
    assert {s.covered for s in kept} == {9, 7} and len(kept) == 4
    assert ties.selection is not None and ties.selection.group_size == 4
    assert ties.selection.slots == 2 and ties.selection.covered == 7
    assert (ties.cutoff_group_size, ties.cutoff_slots) == (4, 2)


def test_a_group_that_exactly_fills_the_beam_needs_no_diversity() -> None:
    candidates = _levelled([9, 9, 7, 7, 5, 5])
    kept, ties = div.retain_states(1, candidates, 4, div.POLICY_DIVERSITY, None)
    assert len(kept) == 4 and ties.selection is None and ties.cutoff_group_size == 0
    assert {s.covered for s in kept} == {9, 7}


def test_a_beam_wider_than_the_candidates_keeps_everything() -> None:
    candidates = _levelled([9, 9, 7])
    kept, ties = div.retain_states(1, candidates, 24, div.POLICY_DIVERSITY, None)
    assert len(kept) == 3 and ties.selection is None


def test_the_straddling_group_records_what_r1s_cut_would_have_kept() -> None:
    candidates = _levelled([7, 7, 7, 7, 7, 7])
    kept, ties = div.retain_states(3, candidates, 3, div.POLICY_DIVERSITY, _no_distance)
    selection = ties.selection
    assert selection is not None and len(selection.selected) == 3
    assert selection.r1_rule_keeps == tuple(s.tickets for s in candidates[:3])
    assert set(selection.saved) | set(selection.selected) >= set(selection.selected)
    assert len(selection.saved) == len(selection.dropped_that_r1_keeps)
    assert set(selection.saved).isdisjoint(selection.r1_rule_keeps)
    assert tuple(s.tickets for s in kept) == selection.selected


def test_retention_rejects_an_unknown_policy_and_a_missing_distance() -> None:
    candidates = _levelled([7, 7, 7])
    with pytest.raises(ValueError, match="unknown retention policy"):
        div.retain_states(1, candidates, 2, "RANDOM", None)
    with pytest.raises(ValueError, match="needs a distance function"):
        div.retain_states(1, candidates, 2, div.POLICY_DIVERSITY, None)


# ------------------------------------------------------------------ the signature engine


@pytest.mark.parametrize(("pool_size", "frozen_size"), [(12, 1), (13, 2), (14, 3)])
def test_signature_engine_equals_explicit_subset_enumeration(
    pool_size: int, frozen_size: int
) -> None:
    geometry = five.Geometry(pool_size, pool.TICKET_SIZE, pool.OUTRIGHT)
    remaining = r1.toy_remaining(pool_size, frozen_size)
    universe = pool.build_universe(pool_size)
    tickets = [universe.ticket_at(i) for i in range(0, universe.tickets.shape[0], 97)][:8]
    subsets = list(itertools.combinations(range(1, pool_size + 1), 7))

    def won(ticket_group: Sequence[five.Ticket]) -> frozenset[tuple[int, ...]]:
        return frozenset(
            subset
            for subset in subsets
            if any(len(set(ticket) & set(subset)) >= pool.OUTRIGHT for ticket in ticket_group)
        )

    distance = div.SignatureDistance(remaining, geometry)
    base = won(remaining)
    assert distance.engine.won_by_remaining == len(base)
    assert distance.engine.region.size == len(subsets) - len(base)
    for first, second in itertools.combinations(tickets, 2):
        a, b = _state([first]), _state([second])
        expected = len((won([first]) - base) ^ (won([second]) - base))
        assert distance(a, b) == (expected, 2)
        assert distance(a, a) == (0, 0)
        assert distance(b, a) == distance(a, b)
    assert distance.signatures_built == len(tickets)
    distance.release()
    assert not distance.cache


def test_signature_distance_equals_the_canonical_union_formula_on_toys() -> None:
    pool_size = 14
    geometry = five.Geometry(pool_size, pool.TICKET_SIZE, pool.OUTRIGHT)
    recounter = r1.CachedRecounter(five.CanonicalRecounter(geometry), geometry)
    remaining = r1.toy_remaining(pool_size, 2)
    universe = pool.build_universe(pool_size)
    distance = div.SignatureDistance(remaining, geometry)
    states: list[r1.BeamState] = []
    for tickets in ([universe.ticket_at(5)], [universe.ticket_at(900), universe.ticket_at(5)]):
        state = r1.canonical_state(tickets)
        states.append(r1.BeamState(state, recounter.count((*remaining, *state)) // 7))
    for first, second in itertools.combinations(states, 2):
        assert distance(first, second)[0] == div.canonical_signature_distance(
            recounter, remaining, first, second
        )


# ------------------------------------------------------------------ toy parity and falsifiability


@pytest.fixture(scope="module")
def toy_parity() -> tuple[pool.ParityTally, dict[str, int]]:
    return div.run_toy_parity()


def test_toy_parity_has_zero_mismatches_and_the_diversity_rule_actually_ran(
    toy_parity: tuple[pool.ParityTally, dict[str, int]],
) -> None:
    tally, seen = toy_parity
    assert tally.mismatches == 0 and tally.comparisons > 500
    assert seen["DIVERSITY_GROUPS"] > 0 and seen["STATES_SAVED_FROM_R1_CUT"] > 0
    families = cast(dict[str, dict[str, int]], tally.detail())
    for name in (
        "TOY_DIVERSITY_RETAINED_ORDER_EQUALS_REFERENCE",
        "TOY_LOWEST_IDENTITY_POLICY_EQUALS_R1_BEAM",
        "TOY_SIGNATURE_DISTANCE_EQUALS_CANONICAL_UNION_FORMULA",
        "TOY_RETAINED_STATE_COVERAGE_EQUALS_CANONICAL",
    ):
        assert families[name]["COMPARISONS"] > 0 and families[name]["MISMATCHES"] == 0


@pytest.mark.parametrize(("pool_size", "frozen", "width", "expansion"), TOY_CASES)
def test_module_beam_equals_the_reference_beam(
    pool_size: int, frozen: int, width: int, expansion: int
) -> None:
    assert _toy_matches_reference(pool_size, frozen, width, expansion)


def _all_toys_match() -> bool:
    return all(_toy_matches_reference(*case) for case in TOY_CASES)


@pytest.mark.parametrize(
    "mutation",
    [
        "sha_order_reversed",
        "secondary_distance_dropped",
        "primary_distance_dropped",
        "r1_cut_instead_of_diversity",
        "minimum_replaced_by_first_only",
    ],
)
def test_the_reference_comparison_catches_a_broken_rule(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    assert _all_toys_match()
    if mutation == "sha_order_reversed":

        def reversed_sha(tickets: Sequence[Sequence[int]]) -> str:
            # complement every hex digit: reverses the SHA order
            digest = div.portfolio_sha256(r1.canonical_state(tickets))
            return "".join(f"{15 - int(c, 16):x}" for c in digest)

        monkeypatch.setattr(div, "state_sha256", reversed_sha)
    elif mutation == "secondary_distance_dropped":

        def no_ticket_distance(first: Sequence[five.Ticket], second: Sequence[five.Ticket]) -> int:
            return 0

        monkeypatch.setattr(div, "ticket_set_distance", no_ticket_distance)
    elif mutation == "primary_distance_dropped":

        def no_bitmap_distance(first: div.PackedBits, second: div.PackedBits) -> int:
            return 0

        monkeypatch.setattr(div, "bitmap_distance", no_bitmap_distance)
    elif mutation == "r1_cut_instead_of_diversity":

        def r1_cut(
            group: Sequence[r1.BeamState],
            slots: int,
            distance: Callable[[r1.BeamState, r1.BeamState], tuple[int, int]],
        ) -> div.DiverseSelection:
            chosen = tuple(group[:slots])
            return div.DiverseSelection(chosen, (None,) * slots, (None,) * slots, (), ())

        monkeypatch.setattr(div, "select_diverse", r1_cut)
    else:

        def first_only(
            group: Sequence[r1.BeamState],
            slots: int,
            distance: Callable[[r1.BeamState, r1.BeamState], tuple[int, int]],
        ) -> div.DiverseSelection:
            ordered = sorted(group, key=lambda s: div.state_sha256(s.tickets))
            anchor = ordered[0]
            rest = sorted(
                ordered[1:], key=lambda s: (-distance(s, anchor)[0], -distance(s, anchor)[1])
            )
            chosen = (anchor, *rest[: slots - 1])
            return div.DiverseSelection(chosen, (None,) * slots, (None,) * slots, (), ())

        monkeypatch.setattr(div, "select_diverse", first_only)
    assert not _all_toys_match()


# ------------------------------------------------------------------ the real 49/6 space


@pytest.fixture(scope="module")
def dev4() -> tuple[div.DiversityBeam, pool.ParityTally]:
    tally = pool.ParityTally()
    result = div.diversity_destroy_set(
        pool.build_universe(),
        4,
        DEV4,
        recounter=r1.CachedRecounter(five.CanonicalRecounter()),
        tally=tally,
        prior=None,
        policy=div.POLICY_DIVERSITY,
        beam_width=2,
        expansion_width=3,
        depth=2,
    )
    return result, tally


def test_real_set_scores_the_complete_universe_and_every_inline_check_passes(
    dev4: tuple[div.DiversityBeam, pool.ParityTally],
) -> None:
    result, tally = dev4
    run = result.beam.run
    assert tally.mismatches == 0
    assert run.enumerations == 3 and run.tickets_scored == 3 * pool.TOTAL_TICKETS
    families = cast(dict[str, dict[str, int]], tally.detail())
    assert families["SIGNATURE_REGION_EQUALS_UNWON_SUBSETS_OF_R"]["COMPARISONS"] == 1
    assert families["PILOT_CONDITIONAL_MARGINAL_EQUALS_DIRECT"]["COMPARISONS"] == 6
    assert families["PILOT_RETAINED_STATE_COVERAGE_EQUALS_CANONICAL"]["COMPARISONS"] == 4
    assert result.policy == div.POLICY_DIVERSITY and len(result.ties) == run.depth == 2
    best = run.best
    assert result.beam.recount_of(best) == result.beam.best_count == 7 * best.covered
    assert r1.ties_recounted(result.beam)


def test_real_signature_distance_equals_the_canonical_union_formula() -> None:
    recounter = r1.CachedRecounter(five.CanonicalRecounter())
    remaining = five.destroy_positions(five.START_PORTFOLIO, DEV4).remaining
    distance = div.SignatureDistance(remaining)
    universe = pool.build_universe()
    tickets = r1.hashed_tickets(universe, "test:signature", 5)
    states: list[r1.BeamState] = []
    for group in ([tickets[0]], [tickets[1], tickets[2]], [tickets[0], tickets[3], tickets[4]]):
        canonical = r1.canonical_state(group)
        states.append(r1.BeamState(canonical, recounter.count((*remaining, *canonical)) // 7))
    assert distance.engine.won_by_remaining * 7 == recounter.count(remaining)
    for first, second in itertools.combinations(states, 2):
        fast, ticket_distance = distance(first, second)
        assert fast == div.canonical_signature_distance(recounter, remaining, first, second)
        assert ticket_distance == len(set(first.tickets) ^ set(second.tickets))
    assert distance(states[0], states[0]) == (0, 0)
    # states[2] contains states[0], so the second signature is a superset of the first
    assert distance(states[0], states[2])[0] > 0


# ------------------------------------------------------------------ result document


def _fake_dbeam(
    size: int, positions: tuple[int, ...], extra: int, recount_extra: int
) -> div.DiversityBeam:
    """A beam whose only final state is the removed set, credited ``extra`` more 7-subsets."""

    destroyed = five.destroy_positions(five.START_PORTFOLIO, positions)
    state = r1.BeamState(
        r1.canonical_state(destroyed.removed), five.START_COUNT // 7 + extra, (), None, 0, 1
    )
    level = r1.BeamLevel(1, 1, 0, (state,), (state,))
    expansion = r1.Expansion(
        1,
        r1.BeamState((), 0),
        0,
        {"TICKETS_SCORED": pool.TOTAL_TICKETS, "PASS": True},
        (r1.NextTicket(destroyed.removed[0], 0, 0, 1),),
        r1.CutoffStats(0, 0, 1),
        1.0,
    )
    run = r1.BeamRun(destroyed.remaining, 0, 1, 24, 8, (expansion,), (level,))
    portfolio = five.normalize_portfolio((*destroyed.remaining, *state.tickets))
    beam = r1.DestroySetBeam(
        size=size,
        destroyed=destroyed,
        remaining_count=0,
        run=run,
        depth0_top_matches_prior=True,
        original_ranks={},
        recounts={portfolio: 7 * state.covered + recount_extra},
        best_portfolio=portfolio,
    )
    ties = (div.LevelTies(1, 0, 1, 0, 0, 0, None),)
    return div.DiversityBeam(beam, ties, div.POLICY_DIVERSITY, (), 0, 0)


def _document(beams: list[div.DiversityBeam]) -> dict[str, object]:
    reuse = r1.read_reuse_artifact()
    sets, priors = r1.load_prior_sets(reuse)
    r1_document, _ = div.read_r1_result()
    return div.build_result_document(
        sets=sets,
        priors=priors,
        beams=beams,
        start_record={},
        pins=[],
        r1_document=r1_document,
        freeze={"RULE_SHA256": div.RULE_SHA256},
        control={"STATUS": "PASS", "PARITY_MISMATCHES": 0},
        r1_parity={
            "PARITY_SAMPLE_COUNT": 1,
            "PARITY_MISMATCHES": 0,
            "REAL_CONDITIONAL_MARGINAL_CHECKS": 100,
            "REAL_CONDITIONAL_MARGINAL_MISMATCHES": 0,
        },
        signature_parity={
            "PARITY_SAMPLE_COUNT": 1,
            "PARITY_MISMATCHES": 0,
            "REAL_SIGNATURE_CHECKS": 40,
        },
        pilot_tally=pool.ParityTally(),
        prior_r2={"AVAILABLE": False},
        wall_seconds=1.0,
        peak_memory=1,
        run_identity={"RUN_HEAD": "h", "RUN_TREE": "t", "RUN_TRACKED_TREE_CLEAN": "YES"},
        module_sha256="m",
        runtime_modules={},
        phase_seconds={},
        thread_env={},
    )


def _all_sets(extra: dict[int, int], recount_extra: int = 0) -> list[div.DiversityBeam]:
    order = [(size, p) for size in div.DESTROY_SIZES for p in pool.pilot_destroy_sets()[size]]
    return [
        _fake_dbeam(size, p, extra.get(i, 0), recount_extra if i in extra else 0)
        for i, (size, p) in enumerate(order)
    ]


def test_document_reports_no_improvement_when_the_beam_only_recovers_the_start() -> None:
    document = _document(_all_sets({}))
    assert document["BEST_COUNT"] == five.START_COUNT and document["BEST_DELTA"] == 0
    assert document["SCIENTIFIC_RESULT"] == div.RESULT_NO_IMPROVEMENT == "NO_IMPROVEMENT"
    assert document["BEST_IS_START_PORTFOLIO"] is True
    assert document["BEST_SHA256"] == five.START_SHA256
    assert document["BEST_COUNT_TIE_COUNT"] == 6
    assert document["BEST_CANONICAL_RECOUNT_STATUS"] == "PASS"
    assert document["CONDITIONAL_ENUMERATIONS"] == 6
    assert document["GLOBAL_TICKETS_SCORED"] == 6 * pool.TOTAL_TICKETS
    assert document["TIE_GROUPS_TOTAL"] == 0 and document["MAX_TIE_GROUP_SIZE"] == 1
    assert document["TIED_STATES_CONSIDERED"] == 0 == document["TIED_STATES_RETAINED_BY_DIVERSITY"]
    assert document["AVERAGE_COVERAGE_SIGNATURE_DISTANCE"] is None
    assert document["DID_DIVERSITY_SAVE_A_STATE_R1_WOULD_DROP"] == "NO"
    assert document["PARITY_MISMATCHES"] == 0
    assert document["PUSH"] == "NO" and document["PR"] == "NOT_CREATED"
    assert document["PRODUCTION_CHANGE"] == "NONE" and document["PROJECT_MEMORY_WRITTEN"] == "NO"
    assert document["FROZEN_RULE_TEXT"] == div.RULE_TEXT


def test_document_reports_an_improvement_only_with_a_matching_canonical_recount() -> None:
    improved = _document(_all_sets({4: 3}))
    assert improved["BEST_COUNT"] == five.START_COUNT + 21 and improved["BEST_DELTA"] == 21
    assert improved["BEST_DESTROY_SET"] == {"DESTROY_SIZE": 5, "POSITIONS": [1, 7, 15, 16, 19]}
    assert improved["SCIENTIFIC_RESULT"] == div.RESULT_IMPROVED == "IMPROVED"
    assert improved["BEST_COUNT_TIE_COUNT"] == 1
    miscounted = _document(_all_sets({4: 3}, recount_extra=7))
    assert miscounted["BEST_CANONICAL_RECOUNT_STATUS"] == "FAIL"
    assert miscounted["SCIENTIFIC_RESULT"] == div.RESULT_NO_IMPROVEMENT


def test_document_counts_inline_and_pre_pilot_parity_mismatches() -> None:
    beams = _all_sets({})
    reuse = r1.read_reuse_artifact()
    sets, priors = r1.load_prior_sets(reuse)
    r1_document, _ = div.read_r1_result()
    tally = pool.ParityTally()
    tally.check("INLINE", ok=False)
    document = div.build_result_document(
        sets=sets,
        priors=priors,
        beams=beams,
        start_record={},
        pins=[],
        r1_document=r1_document,
        freeze={},
        control={"PARITY_MISMATCHES": 2},
        r1_parity={
            "PARITY_SAMPLE_COUNT": 5,
            "PARITY_MISMATCHES": 3,
            "REAL_CONDITIONAL_MARGINAL_CHECKS": 100,
            "REAL_CONDITIONAL_MARGINAL_MISMATCHES": 0,
        },
        signature_parity={
            "PARITY_SAMPLE_COUNT": 7,
            "PARITY_MISMATCHES": 4,
            "REAL_SIGNATURE_CHECKS": 40,
        },
        pilot_tally=tally,
        prior_r2={},
        wall_seconds=1.0,
        peak_memory=1,
        run_identity={"RUN_HEAD": "h", "RUN_TREE": "t", "RUN_TRACKED_TREE_CLEAN": "YES"},
        module_sha256="m",
        runtime_modules={},
        phase_seconds={},
        thread_env={},
    )
    assert document["PARITY_MISMATCHES"] == 3 + 4 + 2 + 1
    assert document["PRE_PILOT_PARITY_MISMATCHES"] == 3 + 4
    assert document["PARITY_SAMPLE_COUNT"] == 12


def test_document_needs_one_beam_per_pilot_set_in_sample_order() -> None:
    beams = _all_sets({})
    with pytest.raises(ValueError, match="exactly one beam"):
        _document(beams[:-1])
    with pytest.raises(ValueError, match="exactly one beam"):
        _document([beams[1], beams[0], *beams[2:]])
    shorter = dataclasses.replace(beams[0].beam, best_portfolio=beams[0].beam.best_portfolio[:-1])
    with pytest.raises(ValueError, match="20-ticket"):
        _document([dataclasses.replace(beams[0], beam=shorter), *beams[1:]])


def test_best_path_differs_from_r1_unless_destroy_set_and_chain_agree() -> None:
    document = _document(_all_sets({}))
    r1_document, _ = div.read_r1_result()
    # the fake beams all end at the removed set, which is not R1's recorded winning chain
    assert document["DID_BEST_PATH_DIFFER_FROM_R1"] == "YES"
    assert document["R1_BEST_DESTROY_SET"] == r1_document["BEST_DESTROY_SET"]
    path = div.r1_best_path(r1_document)
    assert (
        path is not None
        and len(path) == cast(dict[str, int], r1_document["BEST_DESTROY_SET"])["DESTROY_SIZE"]
    )
    assert path[-1] == tuple(
        tuple(t) for t in cast(list[list[int]], r1_document["BEST_REPLACEMENT_TICKETS"])
    )
    assert all(len(state) == depth for depth, state in enumerate(path, start=1))


def test_tie_statistics_follow_the_selections() -> None:
    selection = div.TieSelection(
        level=2,
        covered=7,
        group_size=5,
        slots=3,
        selected=(((1, 2, 3, 4, 5, 6),), ((1, 2, 3, 4, 5, 7),), ((1, 2, 3, 4, 5, 8),)),
        selected_sha256=("a", "b", "c"),
        min_signature=(None, 10, 6),
        min_ticket=(None, 2, 1),
        pair_signature=(10, 6, 8),
        pair_ticket=(2, 1, 2),
        r1_rule_keeps=(((1, 2, 3, 4, 5, 6),), ((1, 2, 3, 4, 5, 7),), ((1, 2, 3, 4, 5, 9),)),
    )
    assert selection.saved == (((1, 2, 3, 4, 5, 8),),)
    assert selection.dropped_that_r1_keeps == (((1, 2, 3, 4, 5, 9),),)
    base = _fake_dbeam(4, pool.pilot_destroy_sets()[4][0], 0, 0)
    ties = (div.LevelTies(1, 2, 4, 6, 5, 3, selection),)
    stats = div.tie_statistics([dataclasses.replace(base, ties=ties)])
    assert stats["TIE_GROUPS_TOTAL"] == 2 and stats["MAX_TIE_GROUP_SIZE"] == 4
    assert stats["TIE_GROUPS_AT_CUTOFF"] == 1
    assert (stats["TIED_STATES_CONSIDERED"], stats["TIED_STATES_RETAINED_BY_DIVERSITY"]) == (5, 3)
    assert stats["TIED_STATES_DROPPED_BY_DIVERSITY"] == 2
    assert stats["AVERAGE_COVERAGE_SIGNATURE_DISTANCE"] == 8.0
    assert stats["AVERAGE_TICKET_SET_DISTANCE"] == 1.5
    assert stats["AVERAGE_PAIRWISE_COVERAGE_SIGNATURE_DISTANCE_AMONG_RETAINED"] == 8.0
    assert stats["DIVERSITY_SAVED_STATES"] == 1


# ------------------------------------------------------------------ control and runner guards


def test_control_comparison_detects_a_beam_that_is_not_r1s() -> None:
    r1_document, _ = div.read_r1_result()
    record = next(
        r
        for r in cast(list[dict[str, object]], r1_document["PER_DESTROY_SET"])
        if tuple(cast(list[int], r["POSITIONS"])) == div.CONTROL_POSITIONS
    )
    comparison = div.control_matches_r1(_fake_dbeam(4, div.CONTROL_POSITIONS, 0, 0), record)
    assert comparison["MATCH"] is False


def test_control_stops_when_r1_has_no_record_of_the_set(monkeypatch: pytest.MonkeyPatch) -> None:
    reuse = r1.read_reuse_artifact()
    _, priors = r1.load_prior_sets(reuse)
    document, _ = div.read_r1_result()
    emptied: dict[str, object] = {**document, "PER_DESTROY_SET": []}
    fake = _fake_dbeam(4, div.CONTROL_POSITIONS, 0, 0)

    def stub(*args: object, **kwargs: object) -> div.DiversityBeam:
        return fake

    monkeypatch.setattr(div, "diversity_destroy_set", stub)
    with pytest.raises(pool.StopConditionError) as stop:
        div.run_control(
            pool.build_universe(8),
            r1.CachedRecounter(five.CanonicalRecounter()),
            priors,
            emptied,
            pool.ParityTally(),
        )
    assert stop.value.code == "CONTROL_R1_MISMATCH"
    monkeypatch.undo()


def test_pilot_refuses_to_overwrite_and_creates_nothing(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    output.write_text("keep", encoding="utf-8")
    workdir = tmp_path / "work"
    with pytest.raises(FileExistsError):
        div.run_pilot(workdir, output)
    assert output.read_text(encoding="utf-8") == "keep" and not workdir.exists()


def test_pilot_stops_before_scoring_when_the_tree_is_dirty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        div,
        "_git_identity",
        lambda: {"RUN_HEAD": "h", "RUN_TREE": "t", "RUN_TRACKED_TREE_CLEAN": "NO"},
    )
    with pytest.raises(pool.StopConditionError) as stop:
        div.run_pilot(tmp_path / "work", tmp_path / "result.json")
    assert stop.value.code == "RUN_TREE_DIRTY"
    assert not (tmp_path / "result.json").exists()


@pytest.mark.parametrize(
    "broken",
    ["r1_mismatch", "signature_mismatch", "r1_coverage", "signature_coverage"],
)
def test_the_parity_gate_stops_the_pilot(broken: str) -> None:
    good_r1: dict[str, object] = {"PARITY_MISMATCHES": 0, "COVERAGE_MEETS_PACKET_MINIMUM": True}
    good_sig: dict[str, object] = {"PARITY_MISMATCHES": 0, "COVERAGE_MEETS_MINIMUM": True}
    div._gate(good_r1, good_sig)  # pyright: ignore[reportPrivateUsage]
    bad_r1 = {**good_r1, "PARITY_MISMATCHES": 1 if broken == "r1_mismatch" else 0}
    bad_r1["COVERAGE_MEETS_PACKET_MINIMUM"] = broken != "r1_coverage"
    bad_sig = {**good_sig, "PARITY_MISMATCHES": 1 if broken == "signature_mismatch" else 0}
    bad_sig["COVERAGE_MEETS_MINIMUM"] = broken != "signature_coverage"
    with pytest.raises(pool.StopConditionError) as stop:
        div._gate(bad_r1, bad_sig)  # pyright: ignore[reportPrivateUsage]
    assert stop.value.code == "PARITY_MISMATCH"


def test_command_line_reports_a_stop_condition_with_exit_code_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    def refuse(workdir: Path, output: Path) -> dict[str, object]:
        raise pool.StopConditionError("PARITY_MISMATCH", "forced")

    monkeypatch.setattr(div, "run_pilot", refuse)
    code = div.main(["pilot", "--workdir", str(tmp_path / "w"), "--output", str(tmp_path / "o")])
    assert code == 2 and "STOP: PARITY_MISMATCH: forced" in capsys.readouterr().err


# ------------------------------------------------------------------ the committed artifact


def test_result_artifact_is_self_consistent_when_present() -> None:
    path = div.REPO_ROOT / div.RESULT_RELATIVE_PATH
    if not path.exists():
        pytest.skip("the result has not been written yet")
    document = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    assert document["TASK_ID"] == div.TASK_ID and document["VARIANT"] == div.VARIANT
    assert document["TASK_STATUS"] == "COMPLETE" and document["PARITY_MISMATCHES"] == 0
    assert cast(int, document["REAL_CONDITIONAL_MARGINAL_CHECKS"]) >= 100
    assert document["CONTROL_R1_WIDTH8"] is not None
    assert cast(dict[str, object], document["CONTROL_R1_WIDTH8"])["STATUS"] == "PASS"
    assert document["FROZEN_RULE_TEXT"] == div.RULE_TEXT
    assert cast(dict[str, object], document["FROZEN_RULE"])["RULE_SHA256"] == div.RULE_SHA256
    improved = cast(int, document["BEST_COUNT"]) > div.START_COUNT
    assert document["SCIENTIFIC_RESULT"] == (
        div.RESULT_IMPROVED
        if improved and document["BEST_CANONICAL_RECOUNT_STATUS"] == "PASS"
        else div.RESULT_NO_IMPROVEMENT
    )
    assert document["BEST_DELTA"] == cast(int, document["BEST_COUNT"]) - div.START_COUNT
    assert document["BEST_CANONICAL_RECOUNT"] == document["BEST_COUNT"]
    sets = cast(list[dict[str, object]], document["PER_DESTROY_SET"])
    assert len(sets) == 6
    assert document["CONDITIONAL_ENUMERATIONS"] == sum(
        cast(int, s["CONDITIONAL_ENUMERATIONS"]) for s in sets
    )
    assert document["GLOBAL_TICKETS_SCORED"] == pool.TOTAL_TICKETS * cast(
        int, document["CONDITIONAL_ENUMERATIONS"]
    )
    assert document["TIED_STATES_RETAINED_BY_DIVERSITY"] == sum(
        cast(int, level["DIVERSITY_SELECTION"]["SLOTS"])  # type: ignore[index]
        for s in sets
        for level in cast(list[dict[str, object]], s["LEVELS"])
        if level["DIVERSITY_SELECTION"] is not None
    )
    assert (
        document["PUSH"] == "NO" and document["MERGE"] == "NO" and document["PR"] == "NOT_CREATED"
    )
    assert (document["PRODUCTION_CHANGE"], document["PROTECTED_LANE_3_TOUCHED"]) == ("NONE", "NO")
