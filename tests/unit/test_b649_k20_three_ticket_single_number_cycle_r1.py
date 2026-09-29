"""Focused tests for the three-ticket single-number cycle family and its residual scorer.

The generator, dedup and 7-set tests are ported from the out-of-repository
producer ``test_three_ticket_cycle.py`` (sha256 7c5714c4…) with their
assertions unchanged. Every check compares the module with an independent
oracle written here (set arithmetic on tickets and 7-sets) or with the
canonical evaluator. The residual scorer is checked against the canonical
evaluator on v = 12 fixtures and on seeded 49/20 candidates.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
import random
from collections.abc import Sequence
from math import comb
from pathlib import Path

import pytest

from lottolab.research import b649_k20_three_ticket_single_number_cycle_r1 as ttc
from lottolab.research import b649_official_any_prize_exact as canonical
from lottolab.research.b649_official_any_prize_exact import DrawMasks

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ARTIFACT = (
    ROOT / "docs/research/matrix-native-results/b649-k20-cross-swap-champion-r1.json"
)
REFERENCE_SHA256 = "bc755e9b674e2ff37dac0fc8b52bb9f01bfd5a2bf90fc5f9f245dbb049c0ae86"

type Identity = frozenset[frozenset[int]]
type Triple = tuple[int, int, int]

V = 12
# Concentrated v=12 fixtures (every ticket holds >= 4 of {8..12}); each has strict winners.
FIXTURE_K3: ttc.Portfolio = ((2, 6, 9, 10, 11, 12), (2, 7, 8, 9, 10, 12), (5, 8, 9, 10, 11, 12))
FIXTURE_K6: ttc.Portfolio = (
    (1, 4, 9, 10, 11, 12),
    (2, 3, 8, 9, 10, 12),
    (3, 6, 8, 9, 11, 12),
    (4, 7, 8, 9, 10, 11),
    (5, 8, 9, 10, 11, 12),
    (7, 8, 9, 10, 11, 12),
)
FIXTURE_K20: ttc.Portfolio = ttc.SMALL_UNIVERSE_WINNABLE_K20_V12
# Mixed-sign fixture: its cycles include strict gains (+14) and strict losses (-14).
FIXTURE_K4_MIXED: ttc.Portfolio = (
    (1, 7, 8, 9, 10, 11),
    (2, 6, 8, 9, 11, 12),
    (2, 7, 8, 9, 10, 11),
    (3, 7, 9, 10, 11, 12),
)
ALL_FIXTURES = [FIXTURE_K3, FIXTURE_K4_MIXED, FIXTURE_K6, FIXTURE_K20]
ALL_IDS = ["K3", "K4mixed", "K6", "K20"]


def _p(tickets: Sequence[Sequence[int]], pool_size: int = V) -> ttc.Portfolio:
    return ttc.normalize_portfolio(tickets, pool_size=pool_size)


def _identity(portfolio: Sequence[Sequence[int]]) -> Identity:
    return frozenset(frozenset(ticket) for ticket in portfolio)


def _unique_emissions(portfolio: ttc.Portfolio) -> tuple[ttc.EmittedCycle, ...]:
    return ttc.deduped_emissions(e for _i, e in ttc.iter_emitted_cycles(portfolio, pool_size=V))


# --- independent oracles -------------------------------------------------------------


def oracle_cycle(
    portfolio: ttc.Portfolio,
    indices: Triple,
    numbers: Triple,
    direction: str,
) -> tuple[Identity | None, str | None]:
    """Definition-level cycle: set images, K distinct tickets, exactly three changed."""

    a, b, c = numbers
    ti, tj, tk = (frozenset(portfolio[x]) for x in indices)
    if direction == "forward":
        images = ((ti - {a}) | {c}, (tj - {b}) | {a}, (tk - {c}) | {b})
    else:
        images = ((ti - {a}) | {b}, (tj - {b}) | {c}, (tk - {c}) | {a})
    if any(len(image) != 6 for image in images):
        return None, "illegal_image"
    new = [frozenset(t) for t in portfolio]
    for position, image in zip(indices, images, strict=True):
        new[position] = image
    if len(set(new)) != len(new):
        return None, "duplicate_ticket"
    old_set = {frozenset(t) for t in portfolio}
    new_set = set(new)
    if len(old_set - new_set) != 3 or len(new_set - old_set) != 3:
        return None, "fewer_than_three_changed"
    return frozenset(new_set), None


def oracle_cover(ticket: Sequence[int], pool_size: int = V) -> set[frozenset[int]]:
    return {
        frozenset(seven)
        for seven in itertools.combinations(range(1, pool_size + 1), 7)
        if len(set(seven) & set(ticket)) >= 3
    }


def oracle_outcomes(portfolio: Sequence[Sequence[int]], pool_size: int = V) -> int:
    covered: set[frozenset[int]] = set()
    for ticket in portfolio:
        covered |= oracle_cover(ticket, pool_size)
    return 7 * len(covered)


@pytest.fixture(scope="module")
def draws12() -> DrawMasks:
    return canonical.all_main_draw_masks(V, 6)


@pytest.fixture(scope="module")
def draws49() -> DrawMasks:
    return canonical.all_main_draw_masks(49, 6)


def canonical_count(portfolio: Sequence[Sequence[int]], draws: DrawMasks) -> int:
    return canonical.evaluate_portfolio(
        [tuple(t) for t in portfolio], pool_size=V, draw_size=6, outright_matches=3, draws=draws
    ).official_any_prize_outcome_count


# --- environment ---------------------------------------------------------------------


def test_modules_resolve_to_this_checkout() -> None:
    assert Path(canonical.__file__).resolve().is_relative_to(ROOT / "src")
    assert Path(ttc.__file__).resolve().is_relative_to(ROOT / "src")


# --- raw family size ------------------------------------------------------------------


def test_raw_cap_is_c20_3_times_6_cubed_times_2_and_generator_emits_exactly_that() -> None:
    assert ttc.raw_attempt_cap(20) == comb(20, 3) * 6**3 * 2 == 492480 == ttc.K20_RAW_ATTEMPT_CAP
    assert ttc.count_raw_cycle_specs(ttc.k20_generator_portfolio(), pool_size=49) == 492480
    for k in (3, 4, 7):
        tickets = list(itertools.combinations(range(1, V + 1), 6))[: 5 * k : 5]
        assert ttc.count_raw_cycle_specs(_p(tickets), pool_size=V) == ttc.raw_attempt_cap(k)
    with pytest.raises(ttc.CycleError):
        ttc.raw_attempt_cap(2)


# --- generator legality, true three-ticket change, degeneracy -------------------------


@pytest.mark.parametrize("tickets", ALL_FIXTURES, ids=ALL_IDS)
def test_every_raw_attempt_matches_the_definition_oracle(tickets: ttc.Portfolio) -> None:
    portfolio = _p(tickets)
    reasons: dict[str, int] = {}
    emitted_count = 0
    for spec in ttc.iter_raw_cycle_specs(portfolio, pool_size=V):
        expected, reason = oracle_cycle(portfolio, spec.indices, spec.numbers, spec.direction)
        got = ttc.emit_spec(portfolio, spec, pool_size=V)
        if expected is None:
            assert got is None, (spec, reason)
            assert reason is not None
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        assert got is not None, spec
        emitted_count += 1
        assert _identity(got.portfolio) == expected
        assert got.portfolio == _p(got.portfolio)  # legal, normalized, K distinct
        assert len(got.portfolio) == len(portfolio)
        assert got.portfolio != portfolio
        assert got.removed == tuple(sorted(portfolio[x] for x in spec.indices))
        assert len(got.added) == 3 and not set(got.added) & set(portfolio)
        assert ttc.changes_exactly_three_tickets(portfolio, got.portfolio)
    assert emitted_count > 0
    if tickets is FIXTURE_K20:
        # every rejection class is exercised, so the oracle agreement is not vacuous
        assert set(reasons) == {"illegal_image", "duplicate_ticket", "fewer_than_three_changed"}


def test_two_ticket_degeneration_is_dropped() -> None:
    # a == c: Ti is unchanged and the move is a legal 2-ticket cross swap of Tj, Tk.
    portfolio = _p([(1, 2, 3, 4, 5, 6), (1, 7, 8, 9, 10, 11), (1, 2, 3, 4, 5, 12)])
    indices = (
        portfolio.index((1, 2, 3, 4, 5, 6)),
        portfolio.index((1, 7, 8, 9, 10, 11)),
        portfolio.index((1, 2, 3, 4, 5, 12)),
    )
    ti, tj, tk = (portfolio[x] for x in indices)
    images = ttc.cycled_tickets(ti, tj, tk, 2, 7, 2, "forward")
    assert images == (ti, (1, 2, 8, 9, 10, 11), (1, 3, 4, 5, 7, 12))
    two_ticket = _p([ti, (1, 2, 8, 9, 10, 11), (1, 3, 4, 5, 7, 12)])  # legal as a 2-ticket move ...
    assert len(set(portfolio) - set(two_ticket)) == 2
    # ... and therefore dropped from the three-ticket family
    assert ttc.emit_cycle(portfolio, indices, (2, 7, 2), "forward", pool_size=V) is None
    expected, reason = oracle_cycle(portfolio, indices, (2, 7, 2), "forward")
    assert expected is None and reason == "fewer_than_three_changed"


def test_both_directions_follow_the_formulas_and_are_generated_independently() -> None:
    ti, tj, tk = (1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), (1, 2, 7, 8, 13, 14)
    forward = ttc.cycled_tickets(ti, tj, tk, 3, 9, 13, "forward")
    reverse = ttc.cycled_tickets(ti, tj, tk, 3, 9, 13, "reverse")
    assert forward == ((1, 2, 4, 5, 6, 13), (3, 7, 8, 10, 11, 12), (1, 2, 7, 8, 9, 14))
    assert reverse == ((1, 2, 4, 5, 6, 9), (7, 8, 10, 11, 12, 13), (1, 2, 3, 7, 8, 14))

    portfolio = _p(FIXTURE_K20)
    per_key: dict[tuple[Triple, Triple], list[str]] = {}
    for spec in ttc.iter_raw_cycle_specs(portfolio, pool_size=V):
        per_key.setdefault((spec.indices, spec.numbers), []).append(spec.direction)
    assert all(sorted(dirs) == ["forward", "reverse"] for dirs in per_key.values())

    legal_by_key: dict[tuple[Triple, Triple], set[str]] = {}
    for _index, emission in ttc.iter_emitted_cycles(portfolio, pool_size=V):
        legal_by_key.setdefault((emission.indices, emission.numbers), set()).add(emission.direction)
    assert any(d == {"forward"} for d in legal_by_key.values())
    assert any(d == {"reverse"} for d in legal_by_key.values())
    assert any(d == {"forward", "reverse"} for d in legal_by_key.values())


# --- normalization, hashing, dedup ----------------------------------------------------


def test_hash_is_slot_and_number_order_invariant_and_matches_the_repository_identity() -> None:
    tickets: list[list[int]] = json.loads(REFERENCE_ARTIFACT.read_text())["TERMINAL_TICKETS"]
    assert ttc.portfolio_sha256(tickets, pool_size=49) == REFERENCE_SHA256
    shuffled = [list(reversed(t)) for t in reversed(tickets)]
    random.Random(3).shuffle(shuffled)
    assert ttc.portfolio_sha256(shuffled, pool_size=49) == REFERENCE_SHA256
    with pytest.raises(ttc.CycleError):
        ttc.normalize_portfolio([*tickets, tickets[0]], pool_size=49)
    with pytest.raises(ttc.CycleError):
        ttc.normalize_ticket([1, 1, 2, 3, 4, 5], pool_size=49)
    with pytest.raises(ttc.CycleError):
        ttc.normalize_ticket([0, 1, 2, 3, 4, 5], pool_size=49)


@pytest.mark.parametrize("tickets", ALL_FIXTURES, ids=ALL_IDS)
def test_dedup_keeps_one_first_occurrence_per_normalized_portfolio(tickets: ttc.Portfolio) -> None:
    portfolio = _p(tickets)
    emissions = [e for _i, e in ttc.iter_emitted_cycles(portfolio, pool_size=V)]
    identities = [_identity(e.portfolio) for e in emissions]
    unique = ttc.deduped_emissions(emissions)
    assert len(unique) == len(set(identities)) < len(emissions)  # duplicates really occur
    assert len({e.sha256 for e in unique}) == len(unique)
    first_seen: dict[Identity, int] = {}
    for position, identity in enumerate(identities):
        first_seen.setdefault(identity, position)
    position_of = {id(e): n for n, e in enumerate(emissions)}
    assert [position_of[id(e)] for e in unique] == sorted(first_seen.values())
    report = ttc.scan_cycle_family(portfolio, pool_size=V, mode=ttc.SCAN_EXHAUSTIVE_FAMILY)
    assert report.legal_emissions == len(emissions)
    assert report.unique_legal_portfolios == len(unique)


# --- exact 7-set residual delta -------------------------------------------------------


def test_seven_set_count_equals_canonical_official_any_prize_count(draws12: DrawMasks) -> None:
    scorer = ttc.SmallUniverseScorer(V)
    tickets = list(itertools.combinations(range(1, V + 1), 6))
    rng = random.Random(20260929)
    cases: list[Sequence[Sequence[int]]] = [
        rng.sample(tickets, rng.randint(1, 6)) for _ in range(40)
    ]
    cases += [FIXTURE_K3, FIXTURE_K6, FIXTURE_K20]
    for case in cases:
        portfolio = _p(case)
        count = canonical_count(portfolio, draws12)
        assert scorer.outcome_count(portfolio) == oracle_outcomes(portfolio) == count


@pytest.mark.parametrize("tickets", ALL_FIXTURES, ids=ALL_IDS)
def test_residual_delta_equals_direct_recompute_and_canonical_delta(
    tickets: ttc.Portfolio, draws12: DrawMasks
) -> None:
    portfolio = _p(tickets)
    universe = ttc.seven_sets(V)
    start = canonical_count(portfolio, draws12)
    assert oracle_outcomes(portfolio) == start
    unique = _unique_emissions(portfolio)
    report = ttc.scan_cycle_family(portfolio, pool_size=V, mode=ttc.SCAN_EXHAUSTIVE_FAMILY)
    winners = dict(report.strict_winners)
    # K20: every strict winner is covered below via the scan; sample the rest
    sample = random.Random(11).sample(list(unique), 120) if len(unique) > 120 else list(unique)
    signs: set[int] = set()
    for emission in sample:
        old_union, new_union, change = ttc.cycle_residual_delta(
            portfolio, emission, pool_size=V, universe=universe
        )
        b1, b2, b3 = ttc.residual_sets(
            portfolio,
            emission.indices,
            pool_size=V,
            universe=universe,
            tickets_override=(emission.added[0], emission.added[1], emission.added[2]),
        )
        assert ttc.inclusion_exclusion_union_size(b1, b2, b3) == len(b1 | b2 | b3) == new_union
        direct = oracle_outcomes(emission.portfolio) - start
        via_canonical = canonical_count(emission.portfolio, draws12) - start
        assert change == direct == via_canonical == 7 * (new_union - old_union)
        assert winners.get(emission.sha256, 0) == max(change, 0)
        signs.add((change > 0) - (change < 0))
    assert 1 in signs
    if tickets is FIXTURE_K4_MIXED:
        assert -1 in signs  # strict losses are compared too, not only gains
    # every scan-reported winner is a real strict gain under the canonical evaluator
    by_sha = {e.sha256: e for e in unique}
    for digest, change in report.strict_winners[:40]:
        assert canonical_count(by_sha[digest].portfolio, draws12) - start == change > 0


# --- safe upper bound -----------------------------------------------------------------


@pytest.mark.parametrize("tickets", ALL_FIXTURES, ids=ALL_IDS)
def test_sum_bound_is_an_upper_bound_and_pruning_keeps_every_strict_winner(
    tickets: ttc.Portfolio,
) -> None:
    portfolio = _p(tickets)
    universe = ttc.seven_sets(V)
    unpruned = ttc.scan_cycle_family(portfolio, pool_size=V, mode=ttc.SCAN_EXHAUSTIVE_FAMILY)
    pruned = ttc.scan_cycle_family(
        portfolio, pool_size=V, mode=ttc.SCAN_EXHAUSTIVE_FAMILY, prune_with_sum_bound=True
    )
    assert unpruned.strict_improvements_seen and unpruned.strict_improvements_seen > 0
    assert pruned.strict_winners == unpruned.strict_winners
    assert pruned.best_delta_f == unpruned.best_delta_f
    assert pruned.pruned_by_sum_bound + pruned.scored_candidates == pruned.unique_legal_portfolios

    unique = _unique_emissions(portfolio)
    sample = list(unique) if len(unique) <= 200 else random.Random(5).sample(list(unique), 200)
    for emission in sample:
        old_union = ttc.residual_union_size(
            portfolio, emission.indices, pool_size=V, universe=universe
        )
        residuals = ttc.residual_sets(
            portfolio,
            emission.indices,
            pool_size=V,
            universe=universe,
            tickets_override=(emission.added[0], emission.added[1], emission.added[2]),
        )
        new_union = ttc.inclusion_exclusion_union_size(*residuals)
        assert new_union <= ttc.sum_upper_bound(*residuals)
        if ttc.sum_bound_prunes(old_union, *residuals):
            assert new_union <= old_union


def test_pruning_is_exercised_on_the_k20_fixture() -> None:
    pruned = ttc.scan_cycle_family(
        _p(FIXTURE_K20), pool_size=V, mode=ttc.SCAN_EXHAUSTIVE_FAMILY, prune_with_sum_bound=True
    )
    assert pruned.pruned_by_sum_bound > 0
    assert pruned.strict_improvements_seen and pruned.strict_improvements_seen > 0


# --- partial, top-L and unscored scans never claim exhaustive no-improvement ----------


def _first_winner_attempt(portfolio: ttc.Portfolio) -> int:
    universe = ttc.seven_sets(V)
    for attempt_index, emission in ttc.iter_emitted_cycles(portfolio, pool_size=V):
        if ttc.cycle_residual_delta(portfolio, emission, pool_size=V, universe=universe)[2] > 0:
            return attempt_index
    raise AssertionError("fixture has no strict winner")


def test_prefix_without_a_winner_is_not_reported_as_family_no_improvement() -> None:
    portfolio = _p(FIXTURE_K20)
    first = _first_winner_attempt(portfolio)
    assert first > 0
    prefix = ttc.scan_cycle_family(
        portfolio, pool_size=V, mode=ttc.SCAN_PARTIAL, max_raw_attempts=first
    )
    assert prefix.raw_attempts_executed == first < prefix.raw_attempt_cap
    assert prefix.strict_improvements_seen == 0
    assert prefix.decision == ttc.DECISION_INCOMPLETE
    assert not prefix.exhaustive_no_improvement
    assert prefix.heuristic_restriction and "not a proof" in prefix.heuristic_restriction
    one_more = ttc.scan_cycle_family(
        portfolio, pool_size=V, mode=ttc.SCAN_PARTIAL, max_raw_attempts=first + 1
    )
    assert one_more.strict_improvements_seen == 1
    assert one_more.decision == ttc.DECISION_STRICT_FOUND
    with pytest.raises(ttc.CycleError):
        ttc.scan_cycle_family(
            portfolio, pool_size=V, mode=ttc.SCAN_PARTIAL, max_raw_attempts=ttc.K20_RAW_ATTEMPT_CAP
        )
    with pytest.raises(ttc.CycleError):
        ttc.scan_cycle_family(
            portfolio, pool_size=V, mode=ttc.SCAN_EXHAUSTIVE_FAMILY, max_raw_attempts=first
        )


def test_top_l_is_a_heuristic_restriction() -> None:
    portfolio = _p(FIXTURE_K20)
    report = ttc.scan_cycle_family(portfolio, pool_size=V, mode=ttc.SCAN_TOP_L, top_l=5)
    assert report.scored_candidates == 5
    assert report.heuristic_restriction and "heuristic restriction" in report.heuristic_restriction
    assert not report.exhaustive_no_improvement
    assert report.decision in {ttc.DECISION_INCOMPLETE, ttc.DECISION_STRICT_FOUND}


def test_exhaustive_no_improvement_only_for_a_complete_scored_family() -> None:
    # The saturated default start covers all 792 7-sets, so no strict winner can
    # exist: its complete-family "no improvement" is true but vacuous.
    saturated = ttc.small_universe_start_portfolio(V)
    assert ttc.SmallUniverseScorer(V).covered_seven_sets(saturated) == comb(V, 7)
    report = ttc.scan_cycle_family(saturated, pool_size=V, mode=ttc.SCAN_EXHAUSTIVE_FAMILY)
    assert report.raw_attempts_executed == ttc.K20_RAW_ATTEMPT_CAP
    assert report.decision == ttc.DECISION_FAMILY_NO_IMPROVEMENT
    assert report.exhaustive_no_improvement and not report.proves_full_n3_no_gain
    assert not report.is_complete_n3 and not report.is_full_three_ticket_joint_replacement

    with pytest.raises(ttc.CycleError):
        dataclasses.replace(report, raw_attempts_executed=report.raw_attempts_executed - 1)
    with pytest.raises(ttc.CycleError):
        dataclasses.replace(report, scan_mode=ttc.SCAN_PARTIAL, heuristic_restriction="prefix")
    with pytest.raises(ttc.CycleError):
        dataclasses.replace(report, scored_candidates=report.scored_candidates - 1)
    with pytest.raises(ttc.CycleError):
        dataclasses.replace(report, is_complete_n3=True)
    with pytest.raises(ttc.CycleError):
        dataclasses.replace(report, proves_full_n3_no_gain=True)
    with pytest.raises(ttc.CycleError):
        dataclasses.replace(report, exhaustive_no_improvement=False)


def test_above_v12_the_family_is_generated_but_never_scored_or_claimed() -> None:
    portfolio = _p(ttc.k20_generator_portfolio()[:4], pool_size=49)
    report = ttc.scan_cycle_family(portfolio, pool_size=49, mode=ttc.SCAN_EXHAUSTIVE_FAMILY)
    assert report.raw_attempts_executed == ttc.raw_attempt_cap(4)
    assert report.strict_improvements_seen is None
    assert report.decision == ttc.DECISION_UNSCORED
    assert not report.exhaustive_no_improvement
    with pytest.raises(ttc.CycleError):
        ttc.SmallUniverseScorer(49)
    with pytest.raises(ttc.CycleError):
        ttc.scan_cycle_family(portfolio, pool_size=49, mode=ttc.SCAN_TOP_L, top_l=3)


# --- exact residual scorer (TripleResidual) --------------------------------------------


def test_triple_specs_concatenate_to_the_family_in_order() -> None:
    portfolio = _p(FIXTURE_K6)
    concatenated = [
        spec
        for triple in itertools.combinations(range(len(portfolio)), 3)
        for spec in ttc.iter_triple_cycle_specs(
            portfolio, (triple[0], triple[1], triple[2]), pool_size=V
        )
    ]
    assert concatenated == list(ttc.iter_raw_cycle_specs(portfolio, pool_size=V))
    assert all(
        sum(1 for _s in ttc.iter_triple_cycle_specs(portfolio, t, pool_size=V))
        == ttc.TRIPLE_RAW_ATTEMPTS
        == 432
        for t in [(0, 1, 2), (1, 3, 5)]
    )
    with pytest.raises(ttc.CycleError):
        list(ttc.iter_triple_cycle_specs(portfolio, (2, 1, 0), pool_size=V))


@pytest.mark.parametrize("tickets", ALL_FIXTURES, ids=ALL_IDS)
def test_residual_scorer_equals_canonical_and_direct_recount_at_v12(
    tickets: ttc.Portfolio, draws12: DrawMasks
) -> None:
    portfolio = _p(tickets)
    scorer = ttc.SmallUniverseScorer(V)
    start = canonical_count(portfolio, draws12)
    triples = list(itertools.combinations(range(len(portfolio)), 3))
    if len(triples) > 60:
        triples = random.Random(12).sample(triples, 60)
    compared = canonical_checked = 0
    signs: set[int] = set()
    for i, j, k in triples:
        residual = ttc.build_triple_residual(portfolio, (i, j, k), pool_size=V, draws=draws12)
        assert residual.outcome_count((portfolio[i], portfolio[j], portfolio[k])) == start
        assert residual.rest_won_draws + int(residual.pattern_draws.sum()) == comb(V, 6)
        for spec in ttc.iter_triple_cycle_specs(portfolio, (i, j, k), pool_size=V):
            emission = ttc.emit_spec(portfolio, spec, pool_size=V)
            if emission is None:
                continue
            count = residual.outcome_count(emission.added)
            assert count == scorer.outcome_count(emission.portfolio)
            compared += 1
            signs.add((count > start) - (count < start))
            if compared % 7 == 0 or len(portfolio) < 20:
                assert count == canonical_count(emission.portfolio, draws12)
                canonical_checked += 1
    assert compared > 0 and canonical_checked > 0
    assert 1 in signs  # every fixture carries strict gains
    if tickets is FIXTURE_K4_MIXED:
        assert -1 in signs


def test_residual_scorer_refuses_tickets_outside_the_triple_universe(draws12: DrawMasks) -> None:
    portfolio = _p(FIXTURE_K6)
    residual = ttc.build_triple_residual(portfolio, (0, 1, 2), pool_size=V, draws=draws12)
    universe = set(residual.universe_numbers)
    assert universe == set(portfolio[0]) | set(portfolio[1]) | set(portfolio[2])
    outside = next(n for n in range(1, V + 1) if n not in universe)
    foreign = tuple(sorted([*sorted(universe)[:5], outside]))
    with pytest.raises(ttc.CycleError):
        residual.outcome_count((foreign, portfolio[1], portfolio[2]))
    with pytest.raises(ttc.CycleError):
        residual.outcome_count((portfolio[0], portfolio[1]))
    with pytest.raises(ttc.CycleError):
        ttc.build_triple_residual(portfolio, (0, 0, 2), pool_size=V, draws=draws12)


# --- 49/20 authority, parity, pilot selection -----------------------------------------


def test_v6_authority_reproduces_count_identity_and_probability(
    draws49: DrawMasks, tmp_path: Path
) -> None:
    start = ttc.load_v6_authority(ROOT, draws=draws49)
    assert start.outcome_count == ttc.STARTING_COUNT == 313_239_647
    assert start.sha256 == ttc.STARTING_PORTFOLIO_SHA256
    assert len(start.portfolio) == 20
    tampered = tmp_path / ttc.STARTING_DONOR_ARTIFACT
    tampered.parent.mkdir(parents=True)
    tampered.write_bytes((ROOT / ttc.STARTING_DONOR_ARTIFACT).read_bytes() + b" ")
    with pytest.raises(ttc.CycleError):
        ttc.load_v6_authority(tmp_path, draws=draws49)


def test_49_20_residual_parity_on_seeded_candidates(draws49: DrawMasks) -> None:
    start = ttc.load_v6_authority(ROOT, draws=draws49)
    triples = ttc.select_pilot_triples()[:2]
    residuals = {
        t: ttc.build_triple_residual(start.portfolio, t, pool_size=49, draws=draws49)
        for t in triples
    }
    parity = ttc.run_parity(start, residuals, triples, draws=draws49)
    assert parity["SAMPLE_COUNT"] == 6
    assert parity["MISMATCHES"] == 0
    assert parity["START_REPRODUCTION_MISMATCHES"] == 0
    assert parity == ttc.run_parity(start, residuals, triples, draws=draws49)  # deterministic


def test_pilot_triples_are_twenty_distinct_seeded_and_reproducible() -> None:
    triples = ttc.select_pilot_triples()
    assert triples == ttc.select_pilot_triples()
    assert len(triples) == len(set(triples)) == ttc.PILOT_TRIPLE_COUNT == 20
    assert all(0 <= i < j < k < 20 for i, j, k in triples)
    assert triples != ttc.select_pilot_triples(seed=ttc.PILOT_SEED + 1)
    assert ttc.PILOT_RAW_ATTEMPT_CEILING == 20 * 6**3 * 2 == 8640


def test_best_is_highest_count_then_lowest_normalized_sha() -> None:
    unique = sorted(_unique_emissions(_p(FIXTURE_K6)), key=lambda e: e.sha256)
    low, high = unique[0], unique[1]
    assert ttc.is_better(ttc.ScoredCandidate(low, 5), None)
    assert ttc.is_better(ttc.ScoredCandidate(high, 6), ttc.ScoredCandidate(low, 5))
    assert not ttc.is_better(ttc.ScoredCandidate(low, 5), ttc.ScoredCandidate(high, 6))
    assert ttc.is_better(ttc.ScoredCandidate(low, 6), ttc.ScoredCandidate(high, 6))
    assert not ttc.is_better(ttc.ScoredCandidate(high, 6), ttc.ScoredCandidate(low, 6))
