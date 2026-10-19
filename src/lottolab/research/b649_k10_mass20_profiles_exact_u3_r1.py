"""Exact U3 census for every full-support K10 mass-20 profile.

Pair-graph isomorphism, higher-support orbit enumeration, legality, Burnside
cross-checks, and U3 arithmetic reuse the complete mass-14 enumerator.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import itertools
import json
import sys
from collections.abc import Sequence
from math import comb

from lottolab.research.b649_k10_mass14_profiles_exact_u3_r1 import (
    DRAW_SIZE,
    INCUMBENT_COUNT,
    POOL_SIZE,
    TICKET_COUNT,
    ProfileResult,
    ProfileSpec,
    _log,
    pair_graph_census,
    profile_arithmetic,
)
from lottolab.research.b649_k10_mass14_profiles_exact_u3_r1 import (
    _seal as _seal_result,
)
from lottolab.research.b649_k10_mass14_profiles_exact_u3_r1 import (
    build_profile_result as _shared_build_profile_result,
)


def derive_mass20_profiles() -> tuple[tuple[int, ...], ...]:
    """Derive mass-20 histograms by independent bounded products and partitions."""

    repeated_sizes = tuple(range(2, TICKET_COUNT + 1))
    incidence_excess = TICKET_COUNT * DRAW_SIZE - POOL_SIZE
    residual_overlap = 20 - incidence_excess

    def make_profile(repeated_counts: tuple[int, ...]) -> tuple[int, ...] | None:
        profile = [0] * (TICKET_COUNT + 1)
        for size, count in zip(repeated_sizes, repeated_counts, strict=True):
            profile[size] = count
        profile[1] = POOL_SIZE - sum(profile[2:])
        result = tuple(profile)
        if (
            profile[1] <= 0
            or sum(result) != POOL_SIZE
            or sum(size * count for size, count in enumerate(result)) != TICKET_COUNT * DRAW_SIZE
            or sum(comb(size, 2) * count for size, count in enumerate(result)) != 20
        ):
            return None
        return result

    # Reduce the defining equations to sum((r - 1) * n_r) = 11 and
    # sum(C(r - 1, 2) * n_r) = 9, then enumerate the bounded multiplicity box.
    direct_profiles: set[tuple[int, ...]] = set()
    bounds = tuple(range(incidence_excess // (size - 1) + 1) for size in repeated_sizes)
    for repeated_counts in itertools.product(*bounds):
        if (
            sum(
                (size - 1) * count
                for size, count in zip(repeated_sizes, repeated_counts, strict=True)
            )
            != incidence_excess
        ):
            continue
        if (
            sum(
                comb(size - 1, 2) * count
                for size, count in zip(repeated_sizes, repeated_counts, strict=True)
            )
            != residual_overlap
        ):
            continue
        profile = make_profile(repeated_counts)
        if profile is not None:
            direct_profiles.add(profile)

    # Independently enumerate non-increasing partitions of the incidence excess.
    partition_profiles: set[tuple[int, ...]] = set()

    def visit_partition(
        remaining: int, largest_part: int, overlap: int, parts: tuple[int, ...]
    ) -> None:
        if remaining == 0:
            if overlap == residual_overlap:
                repeated_counts = [0] * len(repeated_sizes)
                for part in parts:
                    repeated_counts[part - 1] += 1
                profile = make_profile(tuple(repeated_counts))
                if profile is not None:
                    partition_profiles.add(profile)
            return
        for part in range(min(largest_part, remaining, TICKET_COUNT - 1), 0, -1):
            next_overlap = overlap + comb(part, 2)
            if next_overlap <= residual_overlap:
                visit_partition(remaining - part, part, next_overlap, (*parts, part))

    visit_partition(incidence_excess, TICKET_COUNT - 1, 0, ())
    if direct_profiles != partition_profiles:
        raise ValueError(
            "independent mass-20 profile derivations disagree: "
            f"{sorted(direct_profiles)} != {sorted(partition_profiles)}"
        )
    # Pair-label multiplicity orders the profiles as the declared A/B/C set.
    return tuple(sorted(direct_profiles, key=lambda profile: profile[2]))


FROZEN_MASS20_PROFILES = (
    (0, 44, 1, 3, 0, 1, 0, 0, 0, 0, 0),
    (0, 44, 2, 0, 3, 0, 0, 0, 0, 0, 0),
    (0, 43, 4, 0, 1, 1, 0, 0, 0, 0, 0),
)


def _profile_specs(profiles: tuple[tuple[int, ...], ...]) -> tuple[ProfileSpec, ...]:
    """Translate derived histograms to the complete support-census model."""

    specs: list[ProfileSpec] = []
    for index, profile in enumerate(profiles):
        higher_counts = tuple(
            (size, profile[size]) for size in range(3, len(profile)) if profile[size]
        )
        if len(profile) != TICKET_COUNT + 1 or not higher_counts:
            raise ValueError(f"invalid derived mass-20 profile: {profile}")
        base_size, base_count = higher_counts[0]
        specs.append(
            ProfileSpec(
                name=f"PROFILE_{chr(ord('A') + index)}",
                profile=profile,
                pair_label_count=profile[2],
                support_size=base_size,
                higher_label_count=base_count,
                extra_higher_support_counts=higher_counts[1:],
            )
        )
    return tuple(specs)


def build_mass20_result(*, progress: bool = False) -> dict[str, object]:
    """Derive and close every full-support mass-20 profile by exact U3."""

    profiles = derive_mass20_profiles()
    if profiles != FROZEN_MASS20_PROFILES:
        raise ValueError(
            f"derived mass-20 profiles differ from the frozen list: {profiles} != "
            f"{FROZEN_MASS20_PROFILES}"
        )
    if progress:
        _log(f"MASS20_PROFILE_COUNT={len(profiles)} DERIVED_PROFILES={profiles}")

    specs = _profile_specs(profiles)
    outcomes: dict[str, ProfileResult] = {}
    for spec in specs:
        outcomes[spec.name] = _shared_build_profile_result(
            spec, progress=progress, verify_public_u3=False
        )

    survivors = [name for name, outcome in outcomes.items() if outcome.status == "SURVIVES_U3"]
    smallest = (
        min(survivors, key=lambda name: (outcomes[name].legal_class_count, name))
        if survivors
        else None
    )
    record: dict[str, object] = {name: outcome.as_record() for name, outcome in outcomes.items()}
    record.update(
        {
            "MASS20_PROFILE_COUNT": len(profiles),
            "MASS20_STATUS": "PARTIAL" if survivors else "CLOSED",
            "SMALLEST_SURVIVING_PROFILE": smallest,
            "K10_GLOBAL_OPTIMUM_STATUS": "UNKNOWN",
            "INCUMBENT_COUNT": INCUMBENT_COUNT,
        }
    )

    for spec in specs:
        result_record = outcomes[spec.name].as_record()
        census = pair_graph_census(TICKET_COUNT, spec.pair_label_count)
        if (
            result_record["PAIR_GRAPH_CLASS_COUNT"] != len(census.classes)
            or result_record["RETAINED_PAIR_GRAPH_CLASS_COUNT"] != len(census.classes)
            or result_record["PAIR_GRAPH_LABELED_TOTAL"] != census.labeled_total
        ):
            raise ValueError(f"{spec.name}: pair-graph census was incomplete")
        if profile_arithmetic(spec)["overlap_mass"] != 20:
            raise ValueError(f"{spec.name}: derived profile is not mass 20")

    return _seal_result(record)


def main(argv: Sequence[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments != ["mass20"]:
        raise SystemExit(f"unknown mode: {' '.join(arguments)}")
    print(json.dumps(build_mass20_result(progress=True), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
