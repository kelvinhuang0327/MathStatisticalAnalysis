"""Focused definition and exact-score checks for the four-ticket 4-cycle pilot."""

from __future__ import annotations

import itertools
import json
import random
from collections.abc import Sequence
from math import comb
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from lottolab.research import b649_k20_four_ticket_cycle_r1 as cycle
from lottolab.research import b649_k20_three_ticket_single_number_cycle_r1 as ttc
from lottolab.research import b649_official_any_prize_exact as canonical
from lottolab.research.b649_official_any_prize_exact import DrawMasks

ROOT = Path(__file__).resolve().parents[2]
POOL_SIZE = 12
PORTFOLIO = ttc.normalize_portfolio(
    (
        (1, 7, 8, 9, 10, 11),
        (2, 6, 8, 9, 11, 12),
        (2, 7, 8, 9, 10, 11),
        (3, 7, 9, 10, 11, 12),
    ),
    pool_size=POOL_SIZE,
)
QUADRUPLE = (0, 1, 2, 3)
HISTORICAL_START_PORTFOLIO = (
    (1, 2, 34, 41, 42, 45),
    (1, 17, 22, 30, 33, 43),
    (2, 5, 33, 35, 40, 48),
    (3, 4, 10, 15, 26, 27),
    (3, 8, 13, 28, 31, 36),
    (3, 9, 16, 23, 29, 39),
    (4, 7, 12, 36, 39, 46),
    (4, 18, 20, 24, 28, 29),
    (5, 17, 25, 32, 41, 47),
    (6, 7, 9, 13, 18, 26),
    (6, 10, 11, 16, 24, 36),
    (6, 14, 20, 31, 37, 39),
    (7, 8, 10, 14, 19, 29),
    (8, 9, 11, 15, 20, 46),
    (11, 12, 18, 23, 27, 49),
    (12, 13, 15, 19, 24, 37),
    (16, 19, 26, 28, 46, 49),
    (21, 25, 30, 38, 45, 48),
    (21, 32, 40, 42, 43, 44),
    (22, 34, 35, 38, 44, 47),
)
FROZEN_ORIENTATIONS = {
    ("(0 1 2 3)", (1, 2, 3, 0)),
    ("(0 3 2 1)", (3, 0, 1, 2)),
    ("(0 1 3 2)", (1, 3, 0, 2)),
    ("(0 2 3 1)", (2, 0, 3, 1)),
    ("(0 2 1 3)", (2, 3, 1, 0)),
    ("(0 3 1 2)", (3, 2, 0, 1)),
}


@pytest.fixture(scope="module")
def draws12() -> DrawMasks:
    return canonical.all_main_draw_masks(POOL_SIZE, 6)


def _count(portfolio: Sequence[Sequence[int]], draws: DrawMasks) -> int:
    return int(
        canonical.evaluate_portfolio(
            portfolio, pool_size=POOL_SIZE, draws=draws
        ).official_any_prize_outcome_count
    )


def _oracle(spec: cycle.RawFourCycleSpec) -> frozenset[frozenset[int]] | None:
    """Use the named cycle and set arithmetic, independent of implementation images."""

    order = tuple(int(slot) for slot in spec.orientation.strip("()").split())
    successor = {order[index]: order[(index + 1) % 4] for index in range(4)}
    predecessor = {target: source for source, target in successor.items()}
    originals = [frozenset(PORTFOLIO[index]) for index in spec.quadruple]
    images = [
        (originals[slot] - {spec.numbers[slot]}) | {spec.numbers[predecessor[slot]]}
        for slot in range(4)
    ]
    if any(
        len(image) != 6 or image == original
        for image, original in zip(images, originals, strict=True)
    ):
        return None
    replaced = [frozenset(ticket) for ticket in PORTFOLIO]
    for index, image in zip(spec.quadruple, images, strict=True):
        replaced[index] = image
    if len(set(replaced)) != len(replaced):
        return None
    original_set = set(map(frozenset, PORTFOLIO))
    if len(original_set - set(replaced)) != 4 or len(set(replaced) - original_set) != 4:
        return None
    return frozenset(replaced)


def test_modules_resolve_to_this_checkout() -> None:
    assert Path(cycle.__file__).resolve().is_relative_to(ROOT / "src")
    assert Path(ttc.__file__).resolve().is_relative_to(ROOT / "src")
    assert Path(canonical.__file__).resolve().is_relative_to(ROOT / "src")


def test_frozen_family_is_exactly_the_six_single_four_cycles() -> None:
    assert cycle.CYCLE_ORIENTATIONS == 6
    assert {(item.name, item.successor) for item in cycle.ORIENTATIONS} == FROZEN_ORIENTATIONS
    assert {successor for _, successor in cycle.EXCLUDED_DOUBLE_TRANSPOSITIONS}.isdisjoint(
        {successor for _, successor in FROZEN_ORIENTATIONS}
    )
    for _, successor in FROZEN_ORIENTATIONS:
        visited = {0}
        position = successor[0]
        while position not in visited:
            visited.add(position)
            position = successor[position]
        assert position == 0 and len(visited) == 4
    assert cycle.raw_attempt_cap(20) == comb(20, 4) * 6**4 * 6 == 37_674_720
    assert cycle.PILOT_SEED == 20260930
    assert cycle.QUADRUPLE_SAMPLE_COUNT == 24
    assert cycle.PILOT_RAW_ATTEMPT_CEILING == 186_624


def test_every_raw_attempt_matches_the_independent_four_ticket_definition() -> None:
    raw = emitted = 0
    for spec in cycle.iter_quadruple_specs(PORTFOLIO, QUADRUPLE, pool_size=POOL_SIZE):
        raw += 1
        expected = _oracle(spec)
        actual = cycle.emit_spec(PORTFOLIO, spec, pool_size=POOL_SIZE)
        if expected is None:
            assert actual is None, spec
            continue
        assert actual is not None, spec
        emitted += 1
        assert frozenset(map(frozenset, actual.portfolio)) == expected
        assert actual.tickets_changed == len(actual.added) == 4
        assert set(actual.removed) == set(PORTFOLIO) - set(actual.portfolio)
        assert set(actual.added) == set(actual.portfolio) - set(PORTFOLIO)
    assert raw == 7776
    assert emitted > 0


def test_residual_scores_every_local_unique_candidate_and_matches_canonical_samples(
    draws12: DrawMasks,
) -> None:
    residual = cycle.build_subset_residual(PORTFOLIO, QUADRUPLE, pool_size=POOL_SIZE, draws=draws12)
    assert residual.outcome_count(PORTFOLIO) == _count(PORTFOLIO, draws12)
    assert residual.rest_won_draws + int(residual.pattern_draws.sum()) == comb(POOL_SIZE, 6)
    start = ttc.StartBinding(
        PORTFOLIO,
        POOL_SIZE,
        ttc.portfolio_sha256(PORTFOLIO, pool_size=POOL_SIZE),
        _count(PORTFOLIO, draws12),
    )
    scan = cycle.scan_quadruple(start, residual, QUADRUPLE)
    rows = cast(list[cycle.CandidateRow], scan["ROWS"])
    rejected = cast(dict[str, int], scan["REJECTED"])
    assert scan["RAW"] == 7776
    assert scan["LEGAL"] == len(rows) + cast(int, scan["LOCAL_DUPLICATES"])
    assert scan["RAW"] == cast(int, scan["LEGAL"]) + sum(rejected.values())
    assert len({row[0] for row in rows}) == len(rows)
    assert len(rows) > 20
    for sha, numbers, orientation, count in random.Random(20260930).sample(rows, 20):
        emission = cycle.emit_spec(
            PORTFOLIO,
            cycle.RawFourCycleSpec(QUADRUPLE, numbers, orientation),
            pool_size=POOL_SIZE,
        )
        assert emission is not None and emission.sha256 == sha
        assert count == _count(emission.portfolio, draws12)


def test_parity_sampling_is_deterministic_and_canonical_at_small_pool(
    draws12: DrawMasks,
) -> None:
    count = _count(PORTFOLIO, draws12)
    start = ttc.StartBinding(
        PORTFOLIO, POOL_SIZE, ttc.portfolio_sha256(PORTFOLIO, pool_size=POOL_SIZE), count
    )
    residual = cycle.build_subset_residual(PORTFOLIO, QUADRUPLE, pool_size=POOL_SIZE, draws=draws12)
    first = cycle.parity_quadruple(start, residual, QUADRUPLE, draws=draws12)
    second = cycle.parity_quadruple(start, residual, QUADRUPLE, draws=draws12)
    assert first == second
    assert first["START_MATCH"] is True
    samples = cast(list[dict[str, object]], first["SAMPLES"])
    assert len(samples) == 3
    assert all(sample["MATCH"] is True for sample in samples)


def test_frozen_quadruple_sample_is_distinct_and_reproducible() -> None:
    first = cycle.select_pilot_quadruples()
    assert first == cycle.select_pilot_quadruples()
    assert len(first) == len(set(first)) == 24
    assert all(0 <= i < j < k < fourth < 20 for i, j, k, fourth in first)
    assert first == tuple(
        random.Random(20260930).sample(list(itertools.combinations(range(20), 4)), 24)
    )


def test_rejection_accounting_accepts_missing_zero_categories_but_not_wrong_counts() -> None:
    recorded = {
        cycle.REJECT_ILLEGAL_TICKET: 48_418,
        cycle.REJECT_UNCHANGED_TICKET: 8_668,
        cycle.REJECT_DUPLICATE_TICKET: 0,
        cycle.REJECT_FEWER_THAN_FOUR_CHANGED: 0,
    }
    generator = {
        cycle.REJECT_ILLEGAL_TICKET: 48_418,
        cycle.REJECT_UNCHANGED_TICKET: 8_668,
    }
    assert cycle.rejection_counts_match(recorded, generator)
    assert not cycle.rejection_counts_match(
        recorded, {**generator, cycle.REJECT_ILLEGAL_TICKET: 48_419}
    )
    assert not cycle.rejection_counts_match(recorded, {**generator, "UNKNOWN": 0})


def test_current_v7_artifact_is_explicit_and_passed_to_the_canonical_binder(
    draws12: DrawMasks, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def bind(portfolio: Sequence[Sequence[int]], **kwargs: object) -> SimpleNamespace:
        captured["portfolio"] = tuple(tuple(ticket) for ticket in portfolio)
        captured.update(kwargs)
        return SimpleNamespace(
            portfolio=tuple(tuple(ticket) for ticket in portfolio),
            sha256=cycle.V7_BASELINE_SHA256,
            outcome_count=cycle.V7_BASELINE_OUTCOMES,
        )

    monkeypatch.setattr(cycle, "bind_explicit_incumbent", bind)
    start = cycle.load_current_v7_start(
        ROOT,
        Path(
            "docs/research/matrix-native-results/b649-k20-v7-three-ticket-global-repair-pilot-r1-result.json"
        ),
        draws=draws12,
    )

    assert len(start.portfolio) == 20
    assert start.sha256 == cycle.V7_BASELINE_SHA256
    assert start.outcome_count == cycle.V7_BASELINE_OUTCOMES
    assert captured["expected_sha256"] == cycle.V7_BASELINE_SHA256
    assert captured["expected_outcome_count"] == cycle.V7_BASELINE_OUTCOMES


def test_primary_start_fails_closed_without_the_v7_artifact_or_on_old_sha(
    draws12: DrawMasks, tmp_path: Path
) -> None:
    with pytest.raises(cycle.CycleError, match="explicit current-v7"):
        cycle.load_start(cycle.START_PRIMARY, ROOT, draws=draws12)

    old_artifact = tmp_path / "old-start.json"
    old_artifact.write_text(
        json.dumps(
            {
                "TASK_ID": cycle.V7_BASELINE_TASK_ID,
                "BEST_COUNT": cycle.V7_BASELINE_OUTCOMES,
                "BEST_SHA256": cycle.HISTORICAL_START_SHA256,
                "BEST_PORTFOLIO": [list(ticket) for ticket in HISTORICAL_START_PORTFOLIO],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(cycle.CycleError, match="sha256 does not match"):
        cycle.load_current_v7_start(tmp_path, old_artifact, draws=draws12)


def test_explicit_historical_incumbent_preserves_sealed_proposal_behavior(
    draws12: DrawMasks, monkeypatch: pytest.MonkeyPatch
) -> None:
    def historical_bind(
        portfolio: Sequence[Sequence[int]],
        *,
        pool_size: int,
        expected_sha256: str,
        expected_outcome_count: int,
        draws: DrawMasks,
    ) -> SimpleNamespace:
        assert pool_size == 49
        assert expected_sha256 == cycle.HISTORICAL_START_SHA256
        assert expected_outcome_count == cycle.HISTORICAL_START_COUNT
        return SimpleNamespace(
            portfolio=tuple(tuple(ticket) for ticket in portfolio),
            sha256=expected_sha256,
            outcome_count=expected_outcome_count,
        )

    monkeypatch.setattr(ttc, "bind_start", historical_bind)
    start = cycle.bind_explicit_incumbent(
        HISTORICAL_START_PORTFOLIO,
        expected_sha256=cycle.HISTORICAL_START_SHA256,
        expected_outcome_count=cycle.HISTORICAL_START_COUNT,
        draws=draws12,
    )
    expected_pilot_order = (
        (5, 12, 13, 17),
        (4, 9, 10, 17),
        (2, 3, 6, 14),
        (3, 4, 9, 15),
        (6, 14, 15, 17),
        (4, 12, 13, 19),
        (0, 2, 4, 17),
        (0, 3, 18, 19),
        (10, 11, 12, 19),
        (2, 8, 11, 15),
        (5, 14, 15, 17),
        (12, 13, 16, 19),
        (5, 6, 10, 18),
        (0, 2, 7, 16),
        (0, 3, 6, 15),
        (6, 12, 13, 14),
        (0, 7, 8, 18),
        (1, 6, 9, 18),
        (8, 9, 11, 18),
        (3, 9, 10, 11),
        (0, 6, 9, 10),
        (4, 5, 10, 17),
        (3, 5, 12, 19),
        (0, 5, 7, 10),
    )
    emission = cycle.emit_spec(
        start.portfolio,
        cycle.RawFourCycleSpec((2, 8, 11, 15), (5, 5, 37, 37), "(0 2 1 3)"),
        pool_size=49,
    )

    assert start.sha256 == cycle.HISTORICAL_START_SHA256
    assert start.outcome_count == cycle.HISTORICAL_START_COUNT
    assert cycle.select_pilot_quadruples() == expected_pilot_order
    assert emission is not None
    assert emission.sha256 == "292db85d03715ca7c66b37888b1a4d180284bec1d915b4d2cd744c57dcf27081"
