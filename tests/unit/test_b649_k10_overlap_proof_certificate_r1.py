# pyright: reportPrivateUsage=false
"""K10 overlap-mass 11/12 proof certificate: scope, shell coverage and fixed small counts.

Expected joint counts use the 7-number form of OFFICIAL_ANY_PRIZE (a ticket wins iff it
holds at least 3 of the 6 main numbers plus the special number; every 7-set is 7 outcomes),
which is independent of the main-draw/special enumeration under test.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from fractions import Fraction
from itertools import combinations
from math import comb
from typing import Any, cast

from lottolab.application.b649_sealed_geometry_portfolio import SEALED_GEOMETRY_PORTFOLIOS
from lottolab.research.b649_k10_min_overlap_exhaustive_r1 import (
    RECORD_PATH,
    canonical_portfolio_sha256,
    minimum_overlap_derivation,
    overlap_mass,
)
from lottolab.research.b649_k10_overlap_mass12_bonferroni_screen_r1 import (
    _joint_event_count,
    incumbent_outcome_count,
    prove_mass12_profiles,
    total_official_outcomes,
    u3_outcome_count,
)
from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

INCUMBENT = 176_345_645
SINGLE = 7 * sum(comb(6, k) * comb(43, 7 - k) for k in range(3, 7))
PAIR_DISJOINT = 7 * (comb(6, 3) ** 2 * 37 + 2 * comb(6, 3) * comb(6, 4))
# Two tickets sharing x: with x drawn each needs 2 of its 5 others, without x each needs 3.
PAIR_SHARE_ONE = 7 * (
    sum(comb(5, a) * comb(5, b) * comb(38, 6 - a - b) for a in (2, 3, 4) for b in range(2, 7 - a))
    + sum(comb(5, a) * comb(5, b) * comb(38, 7 - a - b) for a in (3, 4) for b in range(3, 8 - a))
)
TRIPLE_STAR = 7 * comb(5, 2) ** 3
TRIPLE_PATH = 7 * comb(5, 2) * comb(4, 1) * comb(5, 2)
TRIPLE_TRIANGLE = 7 * (
    comb(46, 4) - 3 * comb(42, 4) + 3 * comb(38, 4) - comb(34, 4) + 3 * 4 * comb(4, 2) ** 2
)


def load_record() -> Any:
    return json.loads(RECORD_PATH.read_text(encoding="utf-8"))


def _mask(ticket: Sequence[int]) -> int:
    return sum(1 << (number - 1) for number in ticket)


def _profiles_up_to(max_mass: int) -> dict[int, list[dict[str, int]]]:
    """Every K10 number-frequency histogram with overlap mass <= max_mass."""

    found: dict[int, list[dict[str, int]]] = {}

    def walk(frequency: int, slots: int, labels: int, mass: int, chosen: dict[int, int]) -> None:
        if frequency == 1:
            singles = 60 - slots
            if singles >= 0 and labels + singles <= 49:
                profile = {str(r): n for r, n in sorted({**chosen, 1: singles}.items()) if n}
                found.setdefault(mass, []).append(profile)
            return
        count = 0
        while mass + count * comb(frequency, 2) <= max_mass and slots + count * frequency <= 60:
            walk(
                frequency - 1,
                slots + count * frequency,
                labels + count,
                mass + count * comb(frequency, 2),
                {**chosen, frequency: count},
            )
            count += 1

    walk(10, 0, 0, 0, {})
    return found


def test_certificate_claims_stay_inside_mass_11_and_12() -> None:
    certificate = load_record()
    claims = certificate["claims"]
    assert claims["global_optimum_status"] == "UNKNOWN"
    assert claims["probability_gain"] == 0
    assert claims["product_version"] == "UNCHANGED"
    scope = "K=10 portfolios of distinct tickets with overlap mass 11 or 12"
    assert claims["proven_scope"] == scope
    shells = certificate["shells"]
    assert shells["mass_ge_13"] == {"status": "NOT_PROVEN"}
    mass11, mass12 = shells["mass_11"], shells["mass_12"]
    assert mass11["status"] == "EXHAUSTED_EXACT"
    assert mass11["enumeration"]["raw_classes"] == 89_262
    assert mass11["enumeration"]["duplicate_ticket_rejected"] == 64
    assert mass11["enumeration"]["legal_classes"] == 89_198
    assert mass11["exact_scoring"]["classes_scored"] == 89_198
    assert mass11["exact_scoring"]["classes_at_best"] == 1
    assert mass11["bonferroni_cross_certificate"]["survivors"] == 1
    assert mass12["status"] == "EXHAUSTED_BOUND_SCREEN"
    families = mass12["enumeration"]["families"]
    assert sum(item["legal_classes"] for item in families.values()) == 585_148
    screen = mass12["screen"]
    assert screen["classes_screened"] == screen["pruned"] == 585_148
    assert screen["survivors"] == 0
    assert screen["prune_rule"] == "U3 <= incumbent outcome count"
    assert screen["max_bound_gap_vs_incumbent"] < 0
    incumbent = certificate["incumbent"]
    sealed = SEALED_GEOMETRY_PORTFOLIOS[10]
    assert incumbent["portfolio_sha256"] == sealed.portfolio_sha256
    assert Fraction(incumbent["official_any_prize"]) == sealed.official_any_prize_probability
    assert incumbent["outcome_count"] == incumbent_outcome_count(536_005, 1_827_672) == INCUMBENT
    assert certificate["event"]["total_outcomes"] == total_official_outcomes() == comb(49, 6) * 43


def test_mass_11_and_12_shells_cover_every_number_frequency_profile() -> None:
    profiles = _profiles_up_to(12)
    assert sorted(profiles) == [11, 12]
    assert profiles[11] == [{"1": 38, "2": 11}]
    assert sorted(profiles[12], key=len) == [{"1": 36, "2": 12}, {"1": 39, "2": 9, "3": 1}]
    assert minimum_overlap_derivation()["histogram"] == profiles[11][0]
    proved = cast(dict[str, dict[str, int]], prove_mass12_profiles()["profiles"])
    certified = load_record()["shells"]["mass_12"]["profiles"]
    for family, profile in proved.items():
        numbers_used = certified[family].pop("numbers_used")
        assert certified[family] == profile
        assert numbers_used == sum(profile.values())
    assert sorted(proved.values(), key=len) == sorted(profiles[12], key=len)


def test_joint_counts_match_independent_closed_forms() -> None:
    assert SINGLE == 18_611_432
    assert (PAIR_DISJOINT, PAIR_SHARE_ONE) == (107_800, 574_000)
    assert (TRIPLE_TRIANGLE, TRIPLE_STAR, TRIPLE_PATH) == (20_272, 7_000, 2_800)
    cases = {
        ((1, 2, 3, 4, 5, 6),): SINGLE,
        ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12)): PAIR_DISJOINT,
        ((1, 2, 3, 4, 5, 6), (6, 7, 8, 9, 10, 11)): PAIR_SHARE_ONE,
        ((1, 3, 4, 5, 6, 7), (1, 2, 8, 9, 10, 11), (2, 3, 12, 13, 14, 15)): TRIPLE_TRIANGLE,
        ((1, 2, 3, 4, 5, 6), (1, 7, 8, 9, 10, 11), (1, 12, 13, 14, 15, 16)): TRIPLE_STAR,
        ((1, 4, 5, 6, 7, 8), (1, 2, 9, 10, 11, 12), (2, 13, 14, 15, 16, 17)): TRIPLE_PATH,
        ((1, 4, 5, 6, 7, 8), (1, 9, 10, 11, 12, 13), (20, 21, 22, 23, 24, 25)): 0,
    }
    for tickets, expected in cases.items():
        assert _joint_event_count([_mask(ticket) for ticket in tickets]) == expected, tickets


def test_sealed_k10_third_order_bound_dominates_its_exact_count() -> None:
    tickets = SEALED_GEOMETRY_PORTFOLIOS[10].tickets
    assert overlap_mass(tickets) == 11
    pairs = Counter(len(set(a) & set(b)) for a, b in combinations(tickets, 2))
    assert pairs == {0: 34, 1: 11}
    shapes: Counter[str] = Counter()
    for triple in combinations(tickets, 3):
        edges = sum(bool(set(a) & set(b)) for a, b in combinations(triple, 2))
        shapes["triangle" if edges == 3 else "path" if edges == 2 else "other"] += 1
    assert (shapes["triangle"], shapes["path"]) == (10, 4)
    expected_u3 = (
        10 * SINGLE
        - (pairs[0] * PAIR_DISJOINT + pairs[1] * PAIR_SHARE_ONE)
        + shapes["triangle"] * TRIPLE_TRIANGLE
        + shapes["path"] * TRIPLE_PATH
    )
    u3 = u3_outcome_count(tickets)
    assert u3 == expected_u3 == 176_349_040
    cross = load_record()["shells"]["mass_11"]["bonferroni_cross_certificate"]
    assert cross["survivor_u3_outcome_count"] == u3
    assert evaluate_portfolio(tickets).official_any_prize_outcome_count == INCUMBENT <= u3


def test_recorded_fixtures_reproduce_on_the_current_tree() -> None:
    shells = load_record()["shells"]
    runner_up = shells["mass_11"]["exact_scoring"]["runner_up"]
    tickets = tuple(tuple(ticket) for ticket in runner_up["tickets"])
    assert overlap_mass(tickets) == 11
    result = evaluate_portfolio(tickets)
    assert result.official_any_prize_outcome_count == runner_up["outcome_count"] < INCUMBENT
    assert str(result.official_any_prize) == runner_up["official_any_prize"]
    for family, closest in shells["mass_12"]["screen"]["closest_classes"].items():
        tickets = tuple(tuple(ticket) for ticket in closest["tickets"])
        assert overlap_mass(tickets) == 12
        frequency = Counter(Counter(number for ticket in tickets for number in ticket).values())
        profile = shells["mass_12"]["profiles"][family]
        assert {str(r): n for r, n in frequency.items()} == {
            key: value for key, value in profile.items() if key != "numbers_used"
        }
        bound = u3_outcome_count(tickets)
        assert bound == closest["u3_outcome_count"]
        assert bound - INCUMBENT == closest["bound_gap_vs_incumbent"] < 0
        assert len(canonical_portfolio_sha256(tickets)) == 64
