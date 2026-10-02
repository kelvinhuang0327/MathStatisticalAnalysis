from __future__ import annotations

import itertools
from fractions import Fraction
from math import comb

from lottolab.research.b649_k10_mass_ge13_global_bound_r1 import (
    INCIDENCE_EXCESS,
    INCUMBENT_OUTCOME_COUNT,
    _pair_event_counts,  # pyright: ignore[reportPrivateUsage]
    _profile_mass,  # pyright: ignore[reportPrivateUsage]
    _profile_triple_excess,  # pyright: ignore[reportPrivateUsage]
    _triple_table,  # pyright: ignore[reportPrivateUsage]
    cheap_profile_upper_bound,
    mass_ge13_profiles,
    number_multiplicity_profile,
    overlap_mass,
    profile_witness,
    second_moment_profile_upper_bound,
)
from lottolab.research.b649_k10_overlap_mass12_bonferroni_screen_r1 import (
    _joint_count_from_regions,  # pyright: ignore[reportPrivateUsage]
)


def test_mass_ge13_profiles_are_exactly_the_legal_all_used_profiles() -> None:
    profiles = mass_ge13_profiles()

    assert len(profiles) == 52
    assert all(profile[0] == 0 for profile in profiles)
    assert all(sum(profile) == 49 for profile in profiles)
    assert all(
        sum(frequency * profile[frequency] for frequency in range(11)) == 60
        for profile in profiles
    )
    assert all(
        sum((frequency - 1) * profile[frequency] for frequency in range(2, 11))
        == INCIDENCE_EXCESS
        for profile in profiles
    )
    masses = {_profile_mass(profile) for profile in profiles}
    assert min(masses) == 13
    assert max(masses) == 48
    assert all(mass >= 13 for mass in masses)


def test_each_profile_has_a_legal_distinct_ticket_realization() -> None:
    for profile in mass_ge13_profiles():
        tickets = profile_witness(profile)

        assert len(tickets) == 10
        assert len(set(tickets)) == 10
        assert all(len(ticket) == 6 and len(set(ticket)) == 6 for ticket in tickets)
        assert all(1 <= number <= 49 for ticket in tickets for number in ticket)
        assert number_multiplicity_profile(tickets) == profile
        assert overlap_mass(tickets) == _profile_mass(profile)
        triple_excess = 0
        for triple in itertools.combinations(range(10), 3):
            union: set[int] = set()
            for ticket_index in triple:
                union.update(tickets[ticket_index])
            triple_excess += 18 - len(union)
        assert triple_excess == _profile_triple_excess(profile)


def test_cheap_profile_screen_is_valid_and_all_profiles_reach_structure() -> None:
    profiles = mass_ge13_profiles()
    bounds = [cheap_profile_upper_bound(profile) for profile in profiles]

    assert len(bounds) == 52
    assert all(bound >= INCUMBENT_OUTCOME_COUNT for bound in bounds)
    assert max(bounds) == 182_166_320
    mass13 = next(profile for profile in profiles if _profile_mass(profile) == 13)
    assert second_moment_profile_upper_bound(mass13) == 181_749_680


def test_second_moment_pointwise_inequality_holds_for_all_winner_counts() -> None:
    for maximum_winners in range(1, 11):
        for winners in range(1, maximum_winners + 1):
            majorant = winners - Fraction(2, maximum_winners) * comb(winners, 2)
            assert majorant >= 1


def test_pair_and_triple_joint_tables_match_the_official_event_formulas() -> None:
    assert _pair_event_counts() == (
        107_800,
        574_000,
        1_695_988,
        3_469_942,
        6_224_512,
        10_776_332,
    )

    rows = set(_triple_table())
    regions = (0, 1, 1, 1, 1, 0, 4)
    joint = _joint_count_from_regions(regions, 3, 49, 6, 3)
    assert (5, 5, 4, 4, joint) in rows


def test_three_ticket_region_formula_matches_independent_small_enumeration() -> None:
    pool_size = 8
    draw_size = 3
    threshold = 2
    tickets = (
        frozenset((1, 2, 3)),
        frozenset((1, 2, 4)),
        frozenset((1, 5, 6)),
    )
    regions = [0] * 8
    for number in range(1, pool_size + 1):
        signature = sum(
            1 << index for index, ticket in enumerate(tickets) if number in ticket
        )
        if signature:
            regions[signature] += 1
    region_sizes = tuple(regions[1:])

    direct = 0
    labels = set(range(1, pool_size + 1))
    for main in itertools.combinations(labels, draw_size):
        main_set = set(main)
        for special in labels - main_set:
            winning_set = main_set | {special}
            if all(len(ticket & winning_set) >= threshold for ticket in tickets):
                direct += 1

    formula = _joint_count_from_regions(
        region_sizes,
        ticket_count=3,
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=threshold,
    )
    assert formula == direct
