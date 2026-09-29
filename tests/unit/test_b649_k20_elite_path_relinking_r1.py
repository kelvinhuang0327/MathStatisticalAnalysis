"""Focused tests for the K20 elite recombination and path-relinking pilot.

Search-logic tests use a 10-number / 4-number-ticket toy lottery whose complete
draw space is tiny, so every claim is compared with brute force through the
canonical ``evaluate_portfolio``. The real 49/6 checks reproduce the pinned
elites, check the winner-pattern histogram against the canonical evaluator and
recount every candidate reported in the committed result artifact.
"""

from __future__ import annotations

import dataclasses
import hashlib
import itertools
import json
import random
from collections.abc import Sequence
from math import comb
from pathlib import Path

import pytest

from lottolab.research import b649_k20_elite_path_relinking_r1 as rl
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
)

ROOT = Path(__file__).resolve().parents[2]
RESULT_ARTIFACT = ROOT / rl.RESULT_PATH

TOY = rl.LotterySpec(pool_size=10, draw_size=4, outright_matches=3)
TOY_DRAWS = all_main_draw_masks(TOY.pool_size, TOY.draw_size)
_TOY_TICKETS = list(itertools.combinations(range(1, TOY.pool_size + 1), TOY.draw_size))
TOY_POOL: rl.Portfolio = tuple(sorted(random.Random(7).sample(_TOY_TICKETS, 12)))
TOY_K = 4
TOY_A: rl.Portfolio = TOY_POOL[0:4]
TOY_B: rl.Portfolio = TOY_POOL[3:7]  # shares exactly one ticket with TOY_A: distance 3


def toy_count(portfolio: Sequence[Sequence[int]]) -> int:
    """Canonical count on the toy lottery: the brute-force oracle for every toy test."""

    return int(
        evaluate_portfolio(
            portfolio,
            pool_size=TOY.pool_size,
            draw_size=TOY.draw_size,
            outright_matches=TOY.outright_matches,
            draws=TOY_DRAWS,
        ).official_any_prize_outcome_count
    )


def toy_score(portfolio: rl.Portfolio) -> int:
    return toy_count(portfolio)


@pytest.fixture(scope="module")
def toy_histogram() -> rl.WinnerPatternHistogram:
    return rl.build_winner_pattern_histogram(TOY_POOL, lottery=TOY, draws=TOY_DRAWS)


@pytest.fixture(scope="module")
def draws() -> DrawMasks:
    return all_main_draw_masks(rl.BIG_LOTTO.pool_size, rl.BIG_LOTTO.draw_size)


@pytest.fixture(scope="module")
def elites(draws: DrawMasks) -> tuple[rl.EliteRecord, ...]:
    return rl.validate_elites(ROOT, draws=draws)


@pytest.fixture(scope="module")
def real_histogram(
    elites: tuple[rl.EliteRecord, ...], draws: DrawMasks
) -> rl.WinnerPatternHistogram:
    pool = rl.elite_ticket_pool(elite.portfolio for elite in elites if elite.valid)
    return rl.build_winner_pattern_histogram(pool, draws=draws)


def lattice(source: rl.Portfolio, target: rl.Portfolio) -> list[rl.Portfolio]:
    """Every portfolio a relinking path can visit, by independent set arithmetic."""

    common = set(source) & set(target)
    free = sorted((set(source) | set(target)) - common)
    return [
        tuple(sorted(common | set(extra)))
        for extra in itertools.combinations(free, len(source) - len(common))
    ]


# --- 1. elite identities ------------------------------------------------------------


def test_pinned_elites_reproduce_hash_and_canonical_count(
    elites: tuple[rl.EliteRecord, ...],
) -> None:
    by_label = {elite.label: elite for elite in elites}
    assert set(by_label) == {"ELITE_A", "ELITE_B", "ELITE_C"}
    assert by_label["ELITE_A"].valid, by_label["ELITE_A"].reason
    assert by_label["ELITE_B"].valid, by_label["ELITE_B"].reason
    for elite in elites:
        if not elite.valid:
            # ELITE_C lives only in an unpushed commit; an unreachable object is an exclusion.
            assert elite.label == "ELITE_C"
            pytest.skip(f"{elite.label} excluded: {elite.reason}")
        assert elite.sha256 == elite.spec.expected_sha256
        assert elite.canonical_count == elite.spec.expected_count
        assert rl.portfolio_sha256(elite.portfolio) == elite.spec.expected_sha256
        assert len(elite.portfolio) == rl.TICKET_COUNT


def test_a_tampered_or_mispinned_elite_is_excluded_not_used(draws: DrawMasks) -> None:
    spec = rl.ELITE_SPECS[1]
    genuine = rl.read_elite_tickets(spec, ROOT)
    tampered = [list(ticket) for ticket in genuine]
    replacement = next(number for number in range(1, 50) if number not in tampered[0])
    tampered[0][0] = replacement
    bad_hash = rl.validate_elite(spec, ROOT, draws=draws, tickets=tampered)
    assert not bad_hash.valid
    assert "sha256" in bad_hash.reason
    assert bad_hash.portfolio == ()

    wrong_count = dataclasses.replace(spec, expected_count=spec.expected_count + 1)
    mispinned = rl.validate_elite(wrong_count, ROOT, draws=draws)
    assert not mispinned.valid
    assert "canonical count" in mispinned.reason

    wrong_file = dataclasses.replace(spec, artifact_sha256="0" * 64)
    assert not rl.validate_elite(wrong_file, ROOT, draws=draws).valid

    short = rl.validate_elite(spec, ROOT, draws=draws, tickets=genuine[:19])
    assert not short.valid


def test_normalization_rejects_illegal_and_duplicate_input() -> None:
    with pytest.raises(rl.RelinkError):
        rl.normalize_ticket((1, 2, 3, 4, 5, 5))
    with pytest.raises(rl.RelinkError):
        rl.normalize_ticket((1, 2, 3, 4, 5, 50))
    with pytest.raises(rl.RelinkError):
        rl.normalize_portfolio([(1, 2, 3, 4, 5, 6), (6, 5, 4, 3, 2, 1)])
    assert rl.normalize_portfolio([(6, 5, 4, 3, 2, 1), (1, 2, 3, 4, 5, 7)]) == (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 7),
    )


# --- 2. union pool ------------------------------------------------------------------


def test_toy_union_pool_is_exactly_the_distinct_tickets() -> None:
    pool = rl.elite_ticket_pool([TOY_A, TOY_B])
    assert set(pool) == set(TOY_A) | set(TOY_B)
    assert len(pool) == 7
    assert pool == tuple(sorted(pool))
    assert len(set(pool)) == len(pool)
    assert rl.elite_ticket_pool([]) == ()


def test_real_union_pool_is_exactly_the_valid_elites_tickets(
    elites: tuple[rl.EliteRecord, ...],
) -> None:
    valid = [elite for elite in elites if elite.valid]
    pool = rl.elite_ticket_pool(elite.portfolio for elite in valid)
    members: list[set[rl.Ticket]] = [set(elite.portfolio) for elite in valid]
    expected: set[rl.Ticket] = set()
    common: set[rl.Ticket] = set(members[0])
    for member in members:
        expected |= member
        common &= member
    assert set(pool) == expected
    assert len(pool) == len(expected)
    if len(valid) == 3:
        assert len(pool) == 28
        assert len(common) == 13


# --- 3. monotone set distance -------------------------------------------------------


def test_every_path_move_reduces_set_distance_by_exactly_one() -> None:
    result = rl.relink_path(TOY_A, TOY_B, toy_score, beam_width=100, lottery=TOY)
    distance = rl.set_distance(TOY_A, TOY_B)
    assert distance == 3
    assert [layer.distance_to_target for layer in result.layers] == [3, 2, 1, 0]
    allowed = {rl.portfolio_sha256(state) for state in lattice(TOY_A, TOY_B)}
    for layer in result.layers:
        assert layer.beam
        for candidate in layer.beam:
            assert rl.set_distance(candidate.portfolio, TOY_B) == layer.distance_to_target
            assert candidate.sha256 in allowed
            assert len(candidate.portfolio) == TOY_K
    # a child differs from some parent by a single ticket swap toward the target
    for previous, current in itertools.pairwise(result.layers):
        parents = [set(candidate.portfolio) for candidate in previous.beam]
        for candidate in current.beam:
            state = set(candidate.portfolio)
            assert any(
                len(state - parent) == 1 and state - parent <= set(TOY_B) for parent in parents
            )
    assert result.reached_target
    assert result.layers[-1].beam[0].portfolio == TOY_B
    assert result.remove_set == tuple(sorted(set(TOY_A) - set(TOY_B)))
    assert result.add_set == tuple(sorted(set(TOY_B) - set(TOY_A)))


def test_identical_source_and_target_is_a_zero_length_path() -> None:
    result = rl.relink_path(TOY_A, TOY_A, toy_score, lottery=TOY)
    assert len(result.layers) == 1
    assert result.reached_target
    assert result.evaluations == 1
    assert result.generated == 0


# --- 4. exploratory may fall, BEST_EVER never does ----------------------------------


def _profile_scorer(target: rl.Portfolio, profile: dict[int, int]) -> rl.Scorer:
    def score(portfolio: rl.Portfolio) -> int:
        return profile[rl.set_distance(portfolio, target)]

    return score


def test_exploratory_state_may_decrease_but_best_ever_never_does() -> None:
    # distance 3 (source) -> 100, 2 -> 50, 1 -> 60, 0 (target) -> 70
    scorer = _profile_scorer(TOY_B, {3: 100, 2: 50, 1: 60, 0: 70})
    result = rl.relink_path(TOY_A, TOY_B, scorer, beam_width=4, lottery=TOY)
    exploratory = [layer.exploratory_best.count for layer in result.layers]
    best_ever = [layer.best_ever_count for layer in result.layers]
    assert exploratory == [100, 50, 60, 70]
    assert exploratory != sorted(exploratory, reverse=True)
    assert best_ever == [100, 100, 100, 100]
    assert best_ever == sorted(best_ever)
    assert result.best_ever.count == 100
    assert result.best_ever.portfolio == TOY_A


def test_best_ever_tracks_a_late_peak_and_is_monotone() -> None:
    scorer = _profile_scorer(TOY_B, {3: 10, 2: 5, 1: 30, 0: 20})
    result = rl.relink_path(TOY_A, TOY_B, scorer, beam_width=100, lottery=TOY)
    best_ever = [layer.best_ever_count for layer in result.layers]
    assert best_ever == [10, 10, 30, 30]
    assert result.best_ever.count == 30
    assert rl.set_distance(result.best_ever.portfolio, TOY_B) == 1


def test_best_ever_includes_states_the_beam_discarded() -> None:
    # Score by the identity of the swapped-in ticket so that one depth-1 state is a lone
    # outlier; a beam of 1 keeps only the top state but best_ever is over all evaluated.
    scorer = _profile_scorer(TOY_B, {3: 1, 2: 7, 1: 3, 0: 2})
    narrow = rl.relink_path(TOY_A, TOY_B, scorer, beam_width=1, lottery=TOY)
    assert all(len(layer.beam) == 1 for layer in narrow.layers)
    assert narrow.best_ever.count == 7


# --- 5. deterministic tie-break -----------------------------------------------------


def test_beam_tie_break_is_higher_count_then_lowest_sha() -> None:
    result = rl.relink_path(TOY_A, TOY_B, lambda _portfolio: 5, beam_width=2, lottery=TOY)
    first_layer_states = [
        tuple(sorted((set(TOY_A) - {out}) | {inc}))
        for out in sorted(set(TOY_A) - set(TOY_B))
        for inc in sorted(set(TOY_B) - set(TOY_A))
    ]
    expected = sorted({rl.portfolio_sha256(state) for state in first_layer_states})[:2]
    assert [c.sha256 for c in result.layers[1].beam] == expected
    assert result.layers[1].exploratory_best.sha256 == expected[0]

    def two_level(portfolio: rl.Portfolio) -> int:
        return 9 if TOY_POOL[4] in portfolio else 5

    layered = rl.relink_path(TOY_A, TOY_B, two_level, beam_width=3, lottery=TOY)
    beam = layered.layers[1].beam
    assert [c.count for c in beam] == sorted((c.count for c in beam), reverse=True)
    top_level = [c for c in beam if c.count == 9]
    assert [c.sha256 for c in top_level] == sorted(c.sha256 for c in top_level)
    assert all(TOY_POOL[4] in c.portfolio for c in top_level)


def test_relinking_is_deterministic_and_independent_of_input_order() -> None:
    def scorer(portfolio: rl.Portfolio) -> int:
        return toy_count(portfolio)

    baseline = rl.relink_path(TOY_A, TOY_B, scorer, beam_width=3, lottery=TOY)
    shuffled_a = list(TOY_A)
    shuffled_b = list(TOY_B)
    random.Random(3).shuffle(shuffled_a)
    random.Random(4).shuffle(shuffled_b)
    again = rl.relink_path(tuple(shuffled_a), tuple(shuffled_b), scorer, beam_width=3, lottery=TOY)
    assert again == baseline
    assert rl.relink_path(TOY_A, TOY_B, scorer, beam_width=3, lottery=TOY) == baseline


# --- 6. no state is scored twice within one path ------------------------------------


def test_no_duplicate_state_is_evaluated_twice_within_a_path() -> None:
    calls: dict[str, int] = {}

    def counting(portfolio: rl.Portfolio) -> int:
        digest = rl.portfolio_sha256(portfolio)
        calls[digest] = calls.get(digest, 0) + 1
        return toy_count(portfolio)

    result = rl.relink_path(TOY_A, TOY_B, counting, beam_width=100, lottery=TOY)
    assert calls
    assert max(calls.values()) == 1
    assert len(calls) == result.evaluations == len(lattice(TOY_A, TOY_B))
    # commutative orderings reach the same state: those repeats are counted, not re-scored
    assert result.deduplicated > 0
    assert result.generated == result.deduplicated + result.evaluations - 1
    assert sum(layer.evaluated for layer in result.layers[1:]) == result.evaluations - 1
    assert result.beam_expansions == sum(len(layer.beam) for layer in result.layers[:-1])


# --- 7. agreement with brute force --------------------------------------------------


def test_histogram_matches_canonical_evaluator_on_every_toy_subset(
    toy_histogram: rl.WinnerPatternHistogram,
) -> None:
    assert toy_histogram.total_outcomes == TOY.total_outcomes
    for size in (1, 2, 4, 7):
        for subset in itertools.combinations(TOY_POOL, size):
            assert toy_histogram.count(subset) == toy_count(subset)
    assert toy_histogram.count(()) == 0
    with pytest.raises(rl.RelinkError):
        toy_histogram.count(
            [(1, 2, 3, 4), (5, 6, 7, 8)] if (1, 2, 3, 4) not in TOY_POOL else [(9, 9, 9, 9)]
        )


@pytest.mark.parametrize("ticket_count", [1, 4, 6, 8, 11, 12])
def test_pool_solver_equals_brute_force_over_all_subsets(
    toy_histogram: rl.WinnerPatternHistogram, ticket_count: int
) -> None:
    solution = rl.solve_pool_exactly(toy_histogram, ticket_count, batch_size=64)
    scored = [
        (toy_count(subset), rl.portfolio_sha256(subset), subset)
        for subset in itertools.combinations(TOY_POOL, ticket_count)
    ]
    top = max(count for count, _sha, _subset in scored)
    winners = sorted((sha, subset) for count, sha, subset in scored if count == top)
    assert solution.subsets_evaluated == comb(len(TOY_POOL), ticket_count) == len(scored)
    assert solution.best.count == top
    assert solution.tie_count == len(winners)
    assert not solution.ties_truncated
    assert (solution.best.sha256, solution.best.portfolio) == winners[0]


def test_pool_solver_reports_truncated_ties_without_losing_the_maximum(
    toy_histogram: rl.WinnerPatternHistogram,
) -> None:
    full = rl.solve_pool_exactly(toy_histogram, 6)
    capped = rl.solve_pool_exactly(toy_histogram, 6, tie_cap=1)
    assert capped.best.count == full.best.count
    assert capped.tie_count == full.tie_count
    assert capped.ties_truncated == (full.tie_count > 1)


def test_wide_beam_path_equals_lattice_brute_force_and_narrow_beam_never_exceeds_it(
    toy_histogram: rl.WinnerPatternHistogram,
) -> None:
    def scorer(portfolio: rl.Portfolio) -> int:
        return toy_histogram.count(portfolio)

    states = lattice(TOY_A, TOY_B)
    assert len(states) == sum(comb(3, k) ** 2 for k in range(4))
    ranked = sorted(
        ((toy_count(state), rl.portfolio_sha256(state), state) for state in states),
        key=lambda item: (-item[0], item[1]),
    )
    wide = rl.relink_path(TOY_A, TOY_B, scorer, beam_width=len(states), lottery=TOY)
    assert (wide.best_ever.count, wide.best_ever.sha256) == (ranked[0][0], ranked[0][1])
    for layer in wide.layers:
        at_depth = [
            item for item in ranked if rl.set_distance(item[2], TOY_B) == layer.distance_to_target
        ]
        assert layer.exploratory_best.count == at_depth[0][0]
        assert layer.exploratory_best.sha256 == at_depth[0][1]
        assert len(layer.beam) == len(at_depth)
    for width in (1, 2, 3):
        narrow = rl.relink_path(TOY_A, TOY_B, scorer, beam_width=width, lottery=TOY)
        assert narrow.best_ever.count <= ranked[0][0]
        assert all(len(layer.beam) <= width for layer in narrow.layers)
        # depth 1 sees every single swap of the source, so its best is exact
        depth_one = [item for item in ranked if rl.set_distance(item[2], TOY_B) == 2]
        assert narrow.layers[1].exploratory_best.count == depth_one[0][0]
    # no path state can beat the exhaustive optimum over the union pool
    union_pool = rl.elite_ticket_pool([TOY_A, TOY_B])
    union_histogram = rl.build_winner_pattern_histogram(union_pool, lottery=TOY, draws=TOY_DRAWS)
    assert rl.solve_pool_exactly(union_histogram, TOY_K).best.count >= wide.best_ever.count


def test_probe_triple_is_a_deterministic_sha_keyed_triple_of_valid_positions() -> None:
    states = [
        rl.make_candidate(portfolio, toy_count(portfolio))
        for portfolio in itertools.combinations(TOY_POOL, 6)
    ][:60]
    seen: set[tuple[int, int, int]] = set()
    for state in states:
        triple = rl.probe_triple(state)
        assert triple == rl.probe_triple(state)
        assert triple == tuple(sorted(set(triple)))
        assert len(triple) == 3
        assert all(0 <= position < len(state.portfolio) for position in triple)
        # keyed by identity only: the count does not enter the choice
        assert triple == rl.probe_triple(dataclasses.replace(state, count=state.count + 1))
        seen.add(triple)
    assert len(seen) > 1


# --- real 49/6 evaluator and cycle stage --------------------------------------------


def test_real_histogram_matches_canonical_evaluator(
    elites: tuple[rl.EliteRecord, ...],
    real_histogram: rl.WinnerPatternHistogram,
    draws: DrawMasks,
) -> None:
    assert real_histogram.total_outcomes == rl.BIG_LOTTO.total_outcomes == 601_304_088
    for elite in elites:
        if elite.valid:
            assert real_histogram.count(elite.portfolio) == elite.canonical_count
    rng = random.Random(11)
    pool = real_histogram.pool
    for _ in range(2):
        subset = tuple(pool[i] for i in sorted(rng.sample(range(len(pool)), rl.TICKET_COUNT)))
        assert real_histogram.count(subset) == rl.canonical_count(subset, draws=draws)


def test_cycle_operator_is_refused_unless_its_sha256_matches() -> None:
    with pytest.raises(rl.EliteInputError):
        rl.load_cycle_operator(ROOT, sha256="0" * 64)


def test_cycle_probe_scores_one_triple_and_its_best_move_recounts_exactly(
    elites: tuple[rl.EliteRecord, ...],
    draws: DrawMasks,
) -> None:
    try:
        operator = rl.load_cycle_operator(ROOT)
    except rl.EliteInputError as error:
        pytest.skip(f"cycle operator unavailable: {error}")
    elite = next(e for e in elites if e.label == "ELITE_B")
    state = rl.make_candidate(elite.portfolio, elite.canonical_count or 0)
    probe = rl.probe_cycle(state, operator, draws)
    assert probe.indices == rl.probe_triple(state)
    assert probe.raw_attempts == 6**3 * 2
    assert 0 < probe.unique <= probe.legal <= probe.raw_attempts
    assert probe.best is not None
    assert len(probe.best_removed) == len(probe.best_added) == 3
    assert set(probe.best.portfolio) - set(state.portfolio) == set(probe.best_added)
    assert rl.canonical_count(probe.best.portfolio, draws=draws) == probe.best.count
    assert probe.improved == (probe.best.count > state.count)


# --- 8. the committed artifact ------------------------------------------------------


@pytest.mark.skipif(not RESULT_ARTIFACT.exists(), reason="result artifact not generated yet")
def test_every_reported_final_candidate_canonical_recounts_exactly(draws: DrawMasks) -> None:
    record = json.loads(RESULT_ARTIFACT.read_text())
    assert record["TASK_ID"] == rl.TASK_ID
    assert record["TASK_STATUS"] == "COMPLETE"
    assert record["PROTECTED_LANE_3_TOUCHED"] == "NO"
    assert record["GAIN_VS_PROTECTED_LANE_3"] == "NOT_EVALUATED"
    assert record["GLOBAL_OPTIMUM"] == "NOT_CLAIMED"
    module = ROOT / "src/lottolab/research/b649_k20_elite_path_relinking_r1.py"
    assert record["SOURCE_MODULE_SHA256"] == hashlib.sha256(module.read_bytes()).hexdigest()

    reported = [record["BEST_FINAL"], record["POOL"]["BEST"]]
    reported += [path["BEST_EVER"] for path in record["PATHS"]]
    reported += [layer["EXPLORATORY_BEST"] for path in record["PATHS"] for layer in path["LAYERS"]]
    seen: set[str] = set()
    for entry in reported:
        portfolio = rl.normalize_portfolio(
            entry["PORTFOLIO"], expected_ticket_count=rl.TICKET_COUNT
        )
        assert rl.portfolio_sha256(portfolio) == entry["SHA256"]
        if entry["SHA256"] in seen:
            continue
        seen.add(entry["SHA256"])
        assert rl.canonical_count(portfolio, draws=draws) == entry["COUNT"]

    best = record["BEST_FINAL"]
    assert best["COUNT"] == record["BEST_FINAL_COUNT"] == max(e["COUNT"] for e in reported)
    assert record["BEST_FINAL_CANONICAL_RECOUNT"] == best["COUNT"]
    assert record["BEST_CANONICAL_RECOUNT_STATUS"] == "PASS"
    assert record["BEST_PORTFOLIO_SHA256"] == best["SHA256"]
    assert record["BEST_DELTA"] == best["COUNT"] - record["BEST_INPUT_ELITE_COUNT"]
    assert record["BEST_INPUT_ELITE_COUNT"] == max(
        e["CANONICAL_COUNT"] for e in record["ELITES"] if e["VALID"]
    )
    gain = record["BEST_DELTA"] > 0
    assert record["RECOMBINATION_GAIN_ESTABLISHED"] == ("YES" if gain else "NO")

    assert record["POOL"]["SUBSETS_EVALUATED"] == record["POOL"]["SUBSETS_EXPECTED"]
    assert record["POOL"]["SUBSETS_EXPECTED"] == comb(
        record["ELITE_TICKET_POOL_SIZE"], rl.TICKET_COUNT
    )
    assert record["POOL_OPTIMALITY_STATUS"] in (rl.POOL_PROVEN_OPTIMAL, rl.POOL_NOT_PROVEN)
    assert record["EVALUATOR_PARITY"]["MISMATCHES"] == 0
    assert record["PATH_STAGE"]["RECOUNT_MISMATCHES"] == 0
    # every relinking state lies in the pool, so no path can exceed the proven pool optimum
    for path in record["PATHS"]:
        assert path["BEST_EVER"]["COUNT"] <= record["POOL"]["BEST"]["COUNT"]
        counts = [layer["BEST_EVER_COUNT"] for layer in path["LAYERS"]]
        assert counts == sorted(counts)
    cycle = record["CYCLE_STAGE"]
    if cycle["STATUS"] == "COMPLETE":
        assert all(used <= rl.CYCLE_PROBES_PER_PATH for used in cycle["PROBES_PER_PATH"].values())
