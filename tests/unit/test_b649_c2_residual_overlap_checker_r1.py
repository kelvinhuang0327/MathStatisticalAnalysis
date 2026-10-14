"""Bounded, single-process parity and replay tests; no portfolio scoring imports.

Real fixtures are frozen, not generated or selected by this checker:
base 0ba102858c9d5156b759a172fe0ab0fad01ab8c0,
b649-k20-c2-orbit-reduced-exact-n2-r1-result.json START.TICKETS_ORDERED,
run1/pairs/rep_0_1.out.json SHA256
f8dc03cdbc0066120b89f304ea1e7d064c0e2af9da8fd42d1fdeed1997fedb0f:
ties[0:4], g4_scored_sample[0:2], g4_pruned_sample[0:2], using only t1/t2.
The original contract SHA256 is
1b75a9e3fdf624d43ab0886eecf426fdcf9e6599b6282b3e651606100a53edb2.
Archived labels do not establish gain equality for these inputs. R is the
original C2 with ordered slots 0 and 1 removed. Eight pairs, <=20000 validations
each, cannot establish a global boundary or any K20 optimum.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from itertools import combinations
from typing import NoReturn, cast

import pytest

from lottolab.research import b649_c2_residual_overlap_checker_r1 as checker

Ticket = tuple[int, ...]

C2: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 21),
    (1, 6, 7, 8, 9, 22),
    (2, 6, 10, 11, 12, 23),
    (3, 10, 13, 14, 15, 22),
    (1, 11, 13, 16, 17, 24),
    (4, 6, 14, 16, 18, 25),
    (7, 10, 17, 18, 19, 21),
    (2, 8, 13, 19, 20, 25),
    (3, 7, 12, 16, 20, 26),
    (5, 8, 11, 15, 18, 26),
    (5, 9, 12, 14, 19, 24),
    (4, 9, 15, 17, 20, 23),
    (27, 29, 30, 31, 32, 33),
    (27, 34, 35, 36, 37, 38),
    (27, 39, 40, 41, 42, 43),
    (28, 29, 34, 39, 44, 45),
    (28, 30, 35, 40, 46, 47),
    (28, 31, 36, 41, 48, 49),
    (32, 37, 42, 44, 46, 48),
    (33, 38, 43, 45, 47, 49),
)
FIXED_REAL_PAIRS: tuple[tuple[Ticket, Ticket], ...] = (
    ((1, 2, 3, 4, 5, 21), (1, 6, 7, 8, 9, 22)),
    ((1, 5, 7, 22, 23, 25), (2, 4, 21, 22, 24, 26)),
    ((1, 5, 7, 22, 23, 25), (1, 3, 6, 8, 9, 21)),
    ((1, 6, 7, 8, 9, 22), (2, 4, 21, 22, 24, 26)),
    ((1, 21, 22, 29, 42, 49), (1, 5, 21, 32, 35, 39)),
    ((1, 4, 21, 22, 26, 32), (1, 6, 7, 22, 35, 48)),
    ((7, 18, 21, 22, 27, 30), (9, 10, 15, 16, 40, 44)),
    ((4, 16, 30, 32, 38, 43), (3, 22, 32, 37, 39, 49)),
)


def exhaustive_witnesses(
    r: Sequence[Sequence[int]],
    x: Sequence[int],
    y: Sequence[int],
    p: checker.Parameters,
) -> list[Ticket]:
    """Oracle enumerates U choose draw_size, without checker helpers or seeds."""
    xs, ys = set(x), set(y)
    rs = [set(t) for t in r]
    return [
        w
        for w in combinations(range(1, p.universe_size + 1), p.draw_size)
        if len(set(w) & xs) >= p.threshold
        and len(set(w) & ys) >= p.threshold
        and all(len(set(w) & t) < p.threshold for t in rs)
    ]


def assert_complete_zero(result: checker.OverlapResult) -> None:
    assert result.status == checker.Status.OVERLAP_ZERO_PROVEN
    assert result.witness is None and result.replay is None
    assert len(result.progress) == result.unique_seeds
    assert result.next_seed_index is None and result.next_extension_index is None
    assert all(
        row.state == "PRUNED_R"
        or (row.state == "EXHAUSTED" and row.checked_extensions == row.total_extensions)
        for row in result.progress
    )
    assert sum(row.checked_extensions for row in result.progress) == result.full_sets_checked


def test_all_scaled_ticket_pairs_against_exhaustive_oracle() -> None:
    p = checker.Parameters(7, 3, 4, 2, 2)
    r = ((1, 2, 3), (1, 4, 5))
    tickets = [t for t in combinations(range(1, 8), 3) if t not in r]
    counts: Counter[checker.Status] = Counter()
    for x, y in combinations(tickets, 2):
        expected = exhaustive_witnesses(r, x, y, p)
        result = checker.check_residual_overlap(r, x, y, parameters=p)
        counts[result.status] += 1
        assert result.status != checker.Status.UNKNOWN_BUDGET
        if expected:
            assert result.status == checker.Status.OVERLAP_POSITIVE
            assert result.witness in expected
            assert result.replay is not None and result.replay.valid
        else:
            assert_complete_zero(result)
        if result.full_sets_checked:
            # At one validation before any observed terminal result, unresolved
            # coverage remains, even when the exhaustive oracle knows it is zero.
            shorter = checker.check_residual_overlap(
                r,
                x,
                y,
                parameters=p,
                max_full_sets=result.full_sets_checked - 1,
            )
            assert shorter.status == checker.Status.UNKNOWN_BUDGET
            assert shorter.full_sets_checked == result.full_sets_checked - 1
            assert shorter.progress[-1].state == "PARTIAL"
            assert all(row.state in ("PRUNED_R", "EXHAUSTED") for row in shorter.progress[:-1])
        if result.status == checker.Status.OVERLAP_ZERO_PROVEN:
            # Reaching the budget exactly at finite exhaustion still proves zero.
            assert_complete_zero(
                checker.check_residual_overlap(
                    r,
                    x,
                    y,
                    parameters=p,
                    max_full_sets=result.full_sets_checked,
                )
            )
        # Coverage and seed dedup are checked even on W already covered by R.
        seeds = [set(s) for s in checker.seed_unions(x, y, parameters=p)]
        for w in combinations(range(1, 8), 4):
            ws = set(w)
            if len(ws & set(x)) >= 2 and len(ws & set(y)) >= 2:
                assert any(s <= ws for s in seeds)
    assert sum(counts.values()) == 528
    assert counts[checker.Status.OVERLAP_POSITIVE] > 0
    assert counts[checker.Status.OVERLAP_ZERO_PROVEN] > 0
    print("TOY_SCALED_528", dict(counts))


@pytest.mark.parametrize(
    ("x", "y", "r"),
    [
        ((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 7), ()),
        ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), ()),
        ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), ((1, 2, 3, 7, 8, 9),)),
        ((1, 2, 3, 4, 5, 6), (1, 2, 3, 7, 8, 9), ((1, 2, 3, 4, 5, 7),)),
    ],
)
def test_full_seven_set_oracle(
    x: Ticket,
    y: Ticket,
    r: tuple[Ticket, ...],
) -> None:
    p = checker.Parameters(universe_size=12, untouched_count=len(r))
    expected = exhaustive_witnesses(r, x, y, p)  # All C(12,7)=792 outcomes.
    result = checker.check_residual_overlap(r, x, y, parameters=p)
    if expected:
        assert result.status == checker.Status.OVERLAP_POSITIVE
        assert result.witness in expected
    else:
        assert_complete_zero(result)
    assert result.raw_seed_pairs == 400


def test_seed_dedup_keeps_every_extension_family() -> None:
    p = checker.Parameters(8, 6, 7, 3, 0)
    x, y = (1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 7)
    raw = [set(a) | set(b) for a in combinations(x, 3) for b in combinations(y, 3)]
    seeds = checker.seed_unions(x, y, parameters=p)
    assert len(raw) == 400 and len(seeds) < 400
    assert len(seeds) == len(set(seeds))
    expected_families = {w for w in combinations(range(1, 9), 7) if any(s <= set(w) for s in raw)}
    actual_families = {
        tuple(sorted((*s, *extra)))
        for s in seeds
        for extra in combinations([n for n in range(1, 9) if n not in s], 7 - len(s))
    }
    assert actual_families == expected_families


def test_seed_covered_by_r_prunes_all_supersets_with_zero_budget() -> None:
    p = checker.Parameters(8, 3, 7, 3, 1)
    r, x, y = ((1, 2, 4),), (1, 2, 3), (4, 5, 6)
    assert exhaustive_witnesses(r, x, y, p) == []
    result = checker.check_residual_overlap(r, x, y, parameters=p, max_full_sets=0)
    assert_complete_zero(result)
    assert result.full_sets_checked == 0
    assert result.progress[0].state == "PRUNED_R"


def test_last_extension_is_the_only_valid_witness() -> None:
    p = checker.Parameters(8, 3, 7, 3, 1)
    r, x, y = ((1, 2, 7),), (1, 2, 3), (4, 5, 6)
    expected = exhaustive_witnesses(r, x, y, p)
    assert expected == [(1, 2, 3, 4, 5, 6, 8)]
    result = checker.check_residual_overlap(r, x, y, parameters=p, max_full_sets=2)
    assert result.status == checker.Status.OVERLAP_POSITIVE
    assert result.witness == expected[0]
    assert result.full_sets_checked == 2
    assert result.progress[0].checked_extensions == result.progress[0].total_extensions == 2
    assert result.replay is not None and result.replay.valid


def test_budget_exit_immediately_before_witness_is_unknown() -> None:
    p = checker.Parameters(8, 3, 7, 3, 1)
    r, x, y = ((1, 2, 7),), (1, 2, 3), (4, 5, 6)
    result = checker.check_residual_overlap(r, x, y, parameters=p, max_full_sets=1)
    assert result.status == checker.Status.UNKNOWN_BUDGET
    assert result.witness is None and result.replay is None
    assert result.full_sets_checked == 1
    assert result.next_seed_index == 0 and result.next_extension_index == 1
    assert result.progress == (checker.SeedProgress((1, 2, 3, 4, 5, 6), 2, 1, "PARTIAL"),)
    with pytest.raises(TypeError, match="UNKNOWN_BUDGET is not a zero decision"):
        bool(result)


def test_zero_requires_exhaustion_and_allows_exact_budget_boundary() -> None:
    p = checker.Parameters(8, 3, 7, 3, 2)
    r, x, y = ((1, 2, 7), (4, 5, 8)), (1, 2, 3), (4, 5, 6)
    assert exhaustive_witnesses(r, x, y, p) == []
    for budget in (0, 1):
        result = checker.check_residual_overlap(r, x, y, parameters=p, max_full_sets=budget)
        assert result.status == checker.Status.UNKNOWN_BUDGET
        assert result.full_sets_checked == budget
    full = checker.check_residual_overlap(r, x, y, parameters=p, max_full_sets=2)
    assert_complete_zero(full)
    assert full.full_sets_checked == 2


def test_too_large_seed_has_empty_extension_family() -> None:
    p = checker.Parameters(6, 3, 4, 3, 0)
    result = checker.check_residual_overlap(
        (),
        (1, 2, 3),
        (4, 5, 6),
        parameters=p,
        max_full_sets=0,
    )
    assert_complete_zero(result)
    assert result.progress == (checker.SeedProgress((1, 2, 3, 4, 5, 6), 0, 0, "EXHAUSTED"),)


def test_replay_is_independent_of_search(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("replay must not call search, seeds or masks")

    monkeypatch.setattr(checker, "check_residual_overlap", forbidden)
    monkeypatch.setattr(checker, "seed_unions", forbidden)
    monkeypatch.setattr(checker, "_mask", forbidden)
    p = checker.Parameters(8, 3, 7, 3, 1)
    replay = checker.replay_witness(
        ((1, 2, 7),),
        (1, 2, 3),
        (4, 5, 6),
        (1, 2, 3, 4, 5, 6, 8),
        parameters=p,
    )
    assert replay == checker.WitnessReplay(True, True, True, True)


@pytest.mark.parametrize(
    ("w", "conditions"),
    [
        ((1, 2, 3, 4, 5, 6, 7), (True, True, True, False)),
        ((1, 2, 3, 4, 5, 6, 6), (False, True, True, True)),
        ((1, 2, 3, 4, 5, 6), (False, True, True, True)),
        ((1, 2, 3, 4, 5, 6, 9), (False, False, False, False)),
        ((True, 2, 3, 4, 5, 6, 8), (False, False, False, False)),
    ],
)
def test_replay_rejects_invalid_draw_or_r_coverage(
    w: Ticket,
    conditions: tuple[bool, bool, bool, bool],
) -> None:
    replay = checker.replay_witness(
        ((1, 2, 7),),
        (1, 2, 3),
        (4, 5, 6),
        w,
        parameters=checker.Parameters(8, 3, 7, 3, 1),
    )
    assert (replay.legal_draw, replay.hits_x, replay.hits_y, replay.uncovered_by_r) == conditions
    assert not replay.valid


@pytest.mark.parametrize(("x", "y"), [((1, 2, 3), (4, 5, 6)), ((4, 5, 6), (1, 2, 3))])
def test_replay_independently_rejects_each_missing_threshold(x: Ticket, y: Ticket) -> None:
    replay = checker.replay_witness(
        (),
        x,
        y,
        (1, 2, 3, 4),
        parameters=checker.Parameters(6, 3, 4, 3, 0),
    )
    assert replay.legal_draw and replay.uncovered_by_r
    assert replay.hits_x != replay.hits_y
    assert not replay.valid


@pytest.mark.parametrize(
    ("label", "bad"),
    [
        ("X", (1, 2, 3, 4, 5)),
        ("Y", (1, 2, 3, 4, 5, 5)),
        ("X", (0, 2, 3, 4, 5, 6)),
        ("Y", (1, 2, 3, 4, 5, 50)),
        ("X", (True, 2, 3, 4, 5, 6)),
        ("Y", (1, 2, 3, 4, 5, cast(int, 6.0))),
    ],
)
def test_rejects_illegal_x_or_y(label: str, bad: Ticket) -> None:
    x, y = FIXED_REAL_PAIRS[0]
    with pytest.raises(ValueError, match=label):
        checker.check_residual_overlap(
            C2[2:], bad if label == "X" else x, bad if label == "Y" else y
        )


@pytest.mark.parametrize("kind", ["short", "long", "duplicate_r", "bad_r", "x_in_r", "x_eq_y"])
def test_rejects_wrong_r_and_duplicate_tickets(kind: str) -> None:
    r = list(C2[2:])
    x, y = FIXED_REAL_PAIRS[0]
    if kind == "short":
        r.pop()
    elif kind == "long":
        r.append(C2[0])
    elif kind == "duplicate_r":
        r[0] = r[1]
    elif kind == "bad_r":
        r[0] = (1, 2, 3, 4, 5, 50)
    elif kind == "x_in_r":
        x = r[0]
    else:
        y = tuple(reversed(x))
    with pytest.raises(ValueError):
        checker.check_residual_overlap(r, x, y)
    with pytest.raises(ValueError):
        checker.replay_witness(r, x, y, (1, 2, 3, 4, 5, 6, 7))


@pytest.mark.parametrize("budget", [-1, 20_001, True, cast(int, 1.5)])
def test_rejects_invalid_budget(budget: int) -> None:
    with pytest.raises(ValueError, match="max_full_sets"):
        checker.check_residual_overlap(C2[2:], *FIXED_REAL_PAIRS[0], max_full_sets=budget)


@pytest.mark.parametrize(
    "overrides",
    [
        {"universe_size": 50},
        {"universe_size": True},
        {"ticket_size": 0},
        {"ticket_size": 7},
        {"threshold": 0},
        {"threshold": 7},
        {"draw_size": 2},
        {"draw_size": 50},
        {"untouched_count": -1},
        {"untouched_count": 19},
    ],
)
def test_rejects_invalid_parameters(overrides: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        checker.Parameters(**overrides)


def test_fixed_eight_real_cases_and_witness_replay() -> None:
    assert hashlib.sha256(json.dumps(C2, separators=(",", ":")).encode()).hexdigest() == (
        "6a537ea56c2741e1208dbbb4abf1064bc74508f2d356712920d348d11e3a4a24"
    )
    assert len(FIXED_REAL_PAIRS) == 8
    counts: Counter[checker.Status] = Counter()
    for i, (x, y) in enumerate(FIXED_REAL_PAIRS):
        result = checker.check_residual_overlap(C2[2:], x, y, max_full_sets=20_000)
        counts[result.status] += 1
        assert result.full_sets_checked <= 20_000 and result.raw_seed_pairs == 400
        if result.status == checker.Status.OVERLAP_POSITIVE:
            assert result.witness is not None
            # Separate direct set replay, not a call back into the search.
            w = set(result.witness)
            assert len(w) == len(result.witness) == 7 and w <= set(range(1, 50))
            assert len(w & set(x)) >= 3 and len(w & set(y)) >= 3
            assert all(len(w & set(r)) <= 2 for r in C2[2:])
            assert checker.replay_witness(C2[2:], x, y, result.witness).valid
        elif result.status == checker.Status.OVERLAP_ZERO_PROVEN:
            assert_complete_zero(result)
        else:
            assert result.status == checker.Status.UNKNOWN_BUDGET
            assert result.witness is None and result.full_sets_checked == 20_000
            assert result.progress[-1].state == "PARTIAL"
        print("REAL_CASE", i, result.status, result.full_sets_checked, result.witness)
    print("REAL_CASE_COUNTS", {status.value: counts[status] for status in checker.Status})
    assert sum(counts.values()) == 8
