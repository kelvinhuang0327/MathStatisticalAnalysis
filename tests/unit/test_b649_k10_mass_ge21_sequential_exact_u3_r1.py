"""Support-multiplicity tests for the remaining exact-U3 profile sequence."""

from __future__ import annotations

from math import comb
from typing import cast

from lottolab.research.b649_k10_mass14_profiles_exact_u3_r1 import (
    DRAW_SIZE,
    POOL_SIZE,
    TICKET_COUNT,
    profile_arithmetic,
)
from lottolab.research.b649_k10_mass_ge21_sequential_exact_u3_r1 import (
    PRIOR_CLOSED_PROFILES,
    build_remaining_profile_specs,
    derive_full_support_profiles,
    derive_remaining_full_support_profiles,
    validate_prior_closed_profile_sets,
)


def test_bounded_product_and_partition_derivations_cover_full_support_profiles() -> None:
    profiles = derive_full_support_profiles()

    assert len(profiles) == 54
    assert all(sum(profile) == POOL_SIZE == 49 for _mass, profile in profiles)
    assert all(
        sum(size * count for size, count in enumerate(profile)) == TICKET_COUNT * DRAW_SIZE == 60
        for _mass, profile in profiles
    )
    assert all(profile[0] == 0 and profile[1] > 0 for _mass, profile in profiles)
    assert all(
        mass == sum(comb(size, 2) * count for size, count in enumerate(profile))
        for mass, profile in profiles
    )


def test_mass11_through_mass20_sets_match_prior_records_without_censuses() -> None:
    profiles = derive_full_support_profiles()
    audit = validate_prior_closed_profile_sets(profiles)

    assert audit["STATUS"] == "PASS"
    assert audit["CENSUSES_RERUN"] is False
    checks_value = audit["MASS_PROFILE_CHECKS"]
    assert isinstance(checks_value, list)
    checks = cast(list[dict[str, object]], checks_value)
    assert len(checks) == 10
    masses: set[int] = set()
    for check in checks:
        mass = check.get("MASS")
        assert isinstance(mass, int)
        masses.add(mass)
    assert masses == set(PRIOR_CLOSED_PROFILES)


def test_remaining_profiles_are_mass_ordered_and_preserve_support_multiplicities() -> None:
    remaining = derive_remaining_full_support_profiles()
    specs = build_remaining_profile_specs()

    assert len(remaining) == len(specs) == 34
    assert remaining[0] == (
        21,
        (0, 42, 6, 0, 0, 0, 1, 0, 0, 0, 0),
    )
    assert remaining[-1] == (
        48,
        (0, 47, 0, 1, 0, 0, 0, 0, 0, 0, 1),
    )
    assert tuple(spec.pair_label_count for spec in specs[:3]) == (6, 2, 0)
    assert tuple(spec.higher_support_counts for spec in specs[:3]) == (
        ((6, 1),),
        ((3, 1), (4, 1), (5, 1)),
        ((3, 1), (4, 3)),
    )
    assert tuple(profile_arithmetic(spec)["overlap_mass"] for spec in specs[:3]) == (
        21,
        21,
        21,
    )


def test_new_larger_support_multiplicities_are_preserved() -> None:
    specs = {spec.name: spec for spec in build_remaining_profile_specs()}

    assert {
        name: (specs[name].pair_label_count, specs[name].higher_support_counts)
        for name in (
            "MASS26_PROFILE_A",
            "MASS31_PROFILE_A",
            "MASS32_PROFILE_A",
            "MASS39_PROFILE_A",
            "MASS47_PROFILE_A",
        )
    } == {
        "MASS26_PROFILE_A": (5, ((7, 1),)),
        "MASS31_PROFILE_A": (1, ((6, 2),)),
        "MASS32_PROFILE_A": (4, ((8, 1),)),
        "MASS39_PROFILE_A": (3, ((9, 1),)),
        "MASS47_PROFILE_A": (2, ((10, 1),)),
    }
