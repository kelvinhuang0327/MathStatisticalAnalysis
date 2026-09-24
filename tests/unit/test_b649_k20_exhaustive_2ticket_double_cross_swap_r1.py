"""Focused acceptance of the atomic double-cross-swap neighborhood and U3 pipeline."""

from __future__ import annotations

import itertools
import json
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_exhaustive_2ticket_double_cross_swap_r1 as search
from lottolab.research import b649_official_any_prize_exact as exact

u3 = search.u3
TOY = ((1, 2, 3, 4, 5, 6), (1, 2, 3, 7, 8, 9))


@pytest.fixture(scope="module")
def champion_neighborhood() -> search.Neighborhood:
    return search.enumerate_neighborhood(search.load_champion(Path(__file__).resolve().parents[2]))


@pytest.fixture(scope="module")
def toy() -> search.Neighborhood:
    return search.enumerate_neighborhood(TOY)


def test_atomic_two_element_exchange_without_single_swap_operator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("single-number operator must not be called")

    monkeypatch.setattr(u3, "apply_cross_swap", forbidden)
    move = search.DoubleCrossSwapMove(0, 1, (4, 5), (7, 8))
    changed = search.apply_double_cross_swap(TOY, move)
    assert changed.new_changed_tickets == ((1, 2, 3, 6, 7, 8), (1, 2, 3, 4, 5, 9))
    assert changed.portfolio == tuple(sorted(changed.new_changed_tickets))
    for old, new in zip(changed.old_changed_tickets, changed.new_changed_tickets, strict=True):
        assert len(set(old) - set(new)) == len(set(new) - set(old)) == 2


@pytest.mark.parametrize(
    "move",
    [
        search.DoubleCrossSwapMove(0, 0, (4, 5), (7, 8)),
        search.DoubleCrossSwapMove(1, 0, (7, 8), (4, 5)),
        search.DoubleCrossSwapMove(0, 2, (4, 5), (7, 8)),
        search.DoubleCrossSwapMove(0, 1, (4, 4), (7, 8)),
        search.DoubleCrossSwapMove(0, 1, (1, 4), (7, 8)),
        search.DoubleCrossSwapMove(0, 1, (4, 5), (7, 49)),
        search.DoubleCrossSwapMove(0, 1, (4, 5), (True, 8)),
    ],
)
def test_illegal_moves_are_rejected(move: search.DoubleCrossSwapMove) -> None:
    with pytest.raises(ValueError):
        search.apply_double_cross_swap(TOY, move)


def test_independent_toy_enumeration_and_determinism(toy: search.Neighborhood) -> None:
    # Independent set partition oracle, not a call to the production move constructor.
    expected = {
        tuple(
            sorted(
                (
                    tuple(sorted({1, 2, 3} | set(left))),
                    tuple(sorted({1, 2, 3} | ({4, 5, 6, 7, 8, 9} - set(left)))),
                )
            )
        )
        for left in itertools.combinations((4, 5, 6, 7, 8, 9), 3)
        if len(set(left) & {4, 5, 6}) == 1
    }
    assert toy.raw_count == comb(3, 2) ** 2 == 9
    assert {candidate.changed.portfolio for candidate in toy.candidates} == expected
    reordered = tuple(tuple(reversed(ticket)) for ticket in reversed(TOY))
    assert search.enumerate_neighborhood(reordered) == toy


def test_complete_identity_deduplication_and_unchanged_exclusion() -> None:
    overlap_two = search.enumerate_neighborhood(((1, 2, 3, 4, 5, 6), (1, 2, 7, 8, 9, 10)))
    assert overlap_two.raw_count == overlap_two.legal_count == 36
    assert overlap_two.family_size == overlap_two.duplicate_count == 18
    unchanged = search.enumerate_neighborhood(((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 7, 8)))
    assert unchanged.raw_count == unchanged.legal_count == 1
    assert unchanged.duplicate_count == unchanged.unchanged_count == 1
    assert unchanged.family_size == 0


def test_illegal_duplicate_ticket_result_is_accounted() -> None:
    origin = (*TOY, (1, 2, 3, 6, 7, 8))
    neighborhood = search.enumerate_neighborhood(origin)
    assert neighborhood.illegal_count > 0
    assert neighborhood.raw_count == neighborhood.legal_count + neighborhood.illegal_count
    assert neighborhood.legal_count == neighborhood.family_size + neighborhood.duplicate_count


def test_champion_structure_complete_legality_and_multiplicity(
    champion_neighborhood: search.Neighborhood,
) -> None:
    neighborhood = champion_neighborhood
    search.validate_champion_neighborhood(neighborhood)
    assert neighborhood.pair_overlaps == ((0, 97), (1, 93))
    assert sum(count for _, count in neighborhood.pair_overlaps) == 190
    assert neighborhood.raw_count == 97 * comb(6, 2) ** 2 + 93 * comb(5, 2) ** 2 == 31_125
    assert neighborhood.legal_count == neighborhood.family_size == 31_125
    assert neighborhood.illegal_count == neighborhood.duplicate_count == 0
    origin_counts = Counter(itertools.chain.from_iterable(neighborhood.origin))
    for candidate in neighborhood.candidates:
        portfolio = candidate.changed.portfolio
        assert len(portfolio) == len(set(portfolio)) == 20
        assert portfolio == tuple(sorted(portfolio))
        assert all(len(ticket) == len(set(ticket)) == 6 for ticket in portfolio)
        assert all(1 <= number <= 49 for ticket in portfolio for number in ticket)
        assert Counter(itertools.chain.from_iterable(portfolio)) == origin_counts
        assert len(set(neighborhood.origin) & set(portfolio)) == 18
        for old, new in zip(
            candidate.changed.old_changed_tickets,
            candidate.changed.new_changed_tickets,
            strict=True,
        ):
            assert len(set(old) - set(new)) == len(set(new) - set(old)) == 2


def test_champion_mismatch_stops(champion_neighborhood: search.Neighborhood) -> None:
    with pytest.raises(ValueError, match="STOP"):
        search.validate_champion_neighborhood(replace(champion_neighborhood, raw_count=31_124))


def test_u3_reuse_and_full_incremental_equality_for_both_champion_pair_classes(
    champion_neighborhood: search.Neighborhood,
) -> None:
    neighborhood = champion_neighborhood
    original = u3.full_u3_components(neighborhood.origin)
    fixtures: dict[int, search.Candidate] = {}
    for candidate in neighborhood.candidates:
        a, b = candidate.changed.old_changed_tickets
        fixtures.setdefault(len(set(a) & set(b)), candidate)
    assert set(fixtures) == {0, 1}
    for candidate in fixtures.values():
        changed = candidate.changed
        bound = u3.incremental_u3_components(
            neighborhood.origin,
            changed.portfolio,
            original,
            changed.old_changed_tickets,
            changed.new_changed_tickets,
        )
        assert bound == u3.full_u3_components(changed.portfolio)
        scored = search.canonical_exact_score(changed.portfolio)
        assert bound.u3 >= scored.official_any_prize_outcome_count
    assert search.evaluate_portfolio is exact.evaluate_portfolio


def _fake_exact(portfolio: u3.Portfolio) -> exact.ExactPortfolioProbability:
    # Controlled scoring seam only: exercise bookkeeping, not a scientific score.
    return exact.ExactPortfolioProbability(comb(49, 6), 43, 0, sum(portfolio[0]))


def test_every_unpruned_candidate_is_exact_scored_and_accounted(
    toy: search.Neighborhood,
    tmp_path: Path,
) -> None:
    seen: list[u3.Portfolio] = []

    def scorer(portfolio: u3.Portfolio) -> exact.ExactPortfolioProbability:
        seen.append(portfolio)
        return _fake_exact(portfolio)

    evaluations = search.run_sweep(
        toy, 0, checkpoint_path=tmp_path / "state.json", exact_scorer=scorer
    )
    assert seen == [candidate.changed.portfolio for candidate in toy.candidates]
    report = search.build_report(toy, 0, evaluations)
    assert report["FAMILY_SIZE"] == report["BONFERRONI_FAMILY_SIZE"] == toy.family_size
    assert report["BONFERRONI_PRUNED_COUNT"] == 0
    assert report["EXACTLY_RESCORED_COUNT"] == report["BONFERRONI_SURVIVOR_COUNT"] == 9
    assert report["NEIGHBORHOOD_COMPLETENESS"] == "PROVEN"
    assert report["RESULT"] == "STRICT_IMPROVEMENT_FOUND"
    best = max(_fake_exact(p).official_any_prize_outcome_count for p in seen)
    assert report["BEST_OUTCOME_COUNT"] == report["DELTA_FROM_STARTING_CHAMPION"] == best
    assert report["BEST_EXACT_FRACTION"] == str(Fraction(best, u3.TOTAL_OFFICIAL_OUTCOMES))


def test_pruning_boundary_and_family_size_is_accounting_only(
    toy: search.Neighborhood,
    tmp_path: Path,
) -> None:
    def must_not_score(portfolio: u3.Portfolio) -> exact.ExactPortfolioProbability:
        raise AssertionError("safe-pruned candidates must not be scored")

    assert u3.should_safe_prune(100, 100)
    assert not u3.should_safe_prune(101, 100)
    evaluations = search.run_sweep(
        toy,
        u3.TOTAL_OFFICIAL_OUTCOMES,
        checkpoint_path=tmp_path / "pruned.json",
        exact_scorer=must_not_score,
    )
    report = search.build_report(toy, u3.TOTAL_OFFICIAL_OUTCOMES, evaluations)
    assert report["FAMILY_SIZE"] == toy.family_size == 9
    assert report["BONFERRONI_PRUNED_COUNT"] == toy.family_size
    assert report["EXACTLY_RESCORED_COUNT"] == 0
    assert report["RESULT"] == (
        "NO_STRICT_IMPROVEMENT_IN_COMPLETE_DEFINED_DOUBLE_CROSS_SWAP_NEIGHBORHOOD"
    )
    # Bounds are exactly the reused, per-portfolio mathematical quantities.
    assert [evaluation.u3_outcome_count for evaluation in evaluations] == [
        u3.full_u3_components(candidate.changed.portfolio).u3 for candidate in toy.candidates
    ]


def test_checkpoint_resume_byte_determinism_and_completed_reuse(
    toy: search.Neighborhood,
    tmp_path: Path,
) -> None:
    resumed_path, direct_path = tmp_path / "resume.json", tmp_path / "direct.json"
    prefix = search.run_sweep(
        toy,
        0,
        checkpoint_path=resumed_path,
        exact_scorer=_fake_exact,
        max_candidates=3,
        checkpoint_every=2,
    )
    assert search.build_report(toy, 0, prefix)["NEIGHBORHOOD_COMPLETENESS"] == "NOT_PROVEN"
    resumed = search.run_sweep(
        toy,
        0,
        checkpoint_path=resumed_path,
        exact_scorer=_fake_exact,
        resume=True,
    )
    direct = search.run_sweep(toy, 0, checkpoint_path=direct_path, exact_scorer=_fake_exact)
    assert resumed == direct
    assert resumed_path.read_bytes() == direct_path.read_bytes()

    def no_repeat(portfolio: u3.Portfolio) -> exact.ExactPortfolioProbability:
        raise AssertionError("completed exact score was repeated")

    assert (
        search.run_sweep(
            toy,
            0,
            checkpoint_path=resumed_path,
            exact_scorer=no_repeat,
            resume=True,
        )
        == direct
    )
    with pytest.raises(ValueError, match="already exists"):
        search.run_sweep(toy, 0, checkpoint_path=resumed_path)


@pytest.mark.parametrize("corruption", ["identity", "order", "score", "bound", "complete"])
def test_corrupt_checkpoint_is_rejected(
    toy: search.Neighborhood,
    tmp_path: Path,
    corruption: str,
) -> None:
    path = tmp_path / "state.json"
    search.run_sweep(toy, 0, checkpoint_path=path, exact_scorer=_fake_exact, max_candidates=1)
    payload = cast(dict[str, object], json.loads(path.read_bytes()))
    rows = cast(list[dict[str, object]], payload["evaluations"])
    if corruption == "identity":
        cast(dict[str, object], payload["identity"])["family_size"] = 5817
    elif corruption == "order":
        rows[0]["candidate_sha256"] = toy.candidates[-1].sha256
    elif corruption == "score":
        rows[0]["exact_outcome_count"] = None
    elif corruption == "bound":
        rows[0]["u3_outcome_count"] = -1
    else:
        payload["complete"] = True
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        search.run_sweep(toy, 0, checkpoint_path=path, exact_scorer=_fake_exact, resume=True)


def test_external_checkpoint_mutation_is_rejected(toy: search.Neighborhood, tmp_path: Path) -> None:
    path = tmp_path / "state.json"

    def mutate(portfolio: u3.Portfolio) -> exact.ExactPortfolioProbability:
        path.write_text("{}")
        return _fake_exact(portfolio)

    with pytest.raises(ValueError, match="changed outside"):
        search.run_sweep(toy, 0, checkpoint_path=path, exact_scorer=mutate, checkpoint_every=1)


def test_exact_bound_violation_and_wrong_outcome_space_fail_closed(
    toy: search.Neighborhood,
    tmp_path: Path,
) -> None:
    for index, result in enumerate(
        (
            exact.ExactPortfolioProbability(comb(49, 6), 43, 0, u3.TOTAL_OFFICIAL_OUTCOMES),
            exact.ExactPortfolioProbability(1, 43, 0, 1),
        )
    ):

        def broken(
            portfolio: u3.Portfolio, result: exact.ExactPortfolioProbability = result
        ) -> exact.ExactPortfolioProbability:
            return result

        with pytest.raises((ValueError, AssertionError)):
            search.run_sweep(
                toy,
                0,
                checkpoint_path=tmp_path / f"broken{index}.json",
                exact_scorer=broken,
                max_candidates=1,
            )


def test_report_rejects_missing_survivor_score(toy: search.Neighborhood) -> None:
    with pytest.raises(ValueError, match="every U3 survivor"):
        search.build_report(toy, 0, [search.Evaluation(toy.candidates[0].sha256, 1, None)])


def test_empty_neighborhood_completes(tmp_path: Path) -> None:
    neighborhood = search.enumerate_neighborhood((TOY[0],))
    evaluations = search.run_sweep(neighborhood, 0, checkpoint_path=tmp_path / "empty.json")
    report = search.build_report(neighborhood, 0, evaluations)
    assert report["FAMILY_SIZE"] == report["RAW_MOVE_COUNT"] == 0
    assert report["NEIGHBORHOOD_COMPLETENESS"] == "PROVEN"
