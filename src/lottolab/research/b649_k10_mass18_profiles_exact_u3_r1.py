"""Exact U3 census for every full-support K10 mass-18 profile.

The pair multigraph census, legality checks, U3 arithmetic, and Burnside
implementation are reused from the complete mass-14 enumerator. PROFILE_A's
empty pair graph has S10 symmetry, so its mixed higher-support orbit census is
factored through the triple-support multiset stabilizer instead of allocating
the 1.9-billion-state Cartesian product.
"""

from __future__ import annotations

import itertools
import json
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from math import comb

from lottolab.research.b649_k10_mass14_profiles_exact_u3_r1 import (
    DRAW_SIZE,
    INCUMBENT_COUNT,
    POOL_SIZE,
    TICKET_COUNT,
    ProfileResult,
    ProfileSpec,
    Support,
    SupportSystem,
    _burnside_orbit_count_for_counts,
    _group_generators,
    _higher_support_orbits,
    _log,
    all_main_draw_masks,
    bonferroni_u3,
    compare_incumbent,
    evaluate_portfolio,
    is_legal_support_system,
    pair_graph_census,
    profile_arithmetic,
    reconstruct_portfolio,
)
from lottolab.research.b649_k10_mass14_profiles_exact_u3_r1 import (
    _seal as _seal_result,
)
from lottolab.research.b649_k10_mass14_profiles_exact_u3_r1 import (
    build_profile_result as _shared_build_profile_result,
)

# This module intentionally uses the complete enumerator's private orbit and
# group primitives; it does not call its legacy coverage helper.
# pyright: reportPrivateUsage=false


def derive_mass18_profiles() -> tuple[tuple[int, ...], ...]:
    """Derive mass-18 histograms by bounded products and partitions independently."""

    repeated_sizes = tuple(range(2, TICKET_COUNT + 1))
    incidence_excess = TICKET_COUNT * DRAW_SIZE - POOL_SIZE
    residual_overlap = 18 - incidence_excess

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
            or sum(comb(size, 2) * count for size, count in enumerate(result)) != 18
        ):
            return None
        return result

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
            "independent mass-18 profile derivations disagree: "
            f"{sorted(direct_profiles)} != {sorted(partition_profiles)}"
        )
    return tuple(sorted(direct_profiles, reverse=True))


FROZEN_MASS18_PROFILES = (
    (0, 44, 0, 4, 1, 0, 0, 0, 0, 0, 0),
    (0, 43, 3, 1, 2, 0, 0, 0, 0, 0, 0),
    (0, 42, 5, 1, 0, 1, 0, 0, 0, 0, 0),
)


def _profile_specs(profiles: tuple[tuple[int, ...], ...]) -> tuple[ProfileSpec, ...]:
    specs: list[ProfileSpec] = []
    for index, profile in enumerate(profiles):
        higher_counts = tuple(
            (size, profile[size]) for size in range(3, len(profile)) if profile[size]
        )
        if len(profile) != TICKET_COUNT + 1 or not higher_counts:
            raise ValueError(f"invalid derived mass-18 profile: {profile}")
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


def _symmetric_group_generators(vertex_count: int) -> tuple[tuple[int, ...], ...]:
    """Two permutations generating the full symmetric group on the vertices."""

    if vertex_count < 1:
        raise ValueError("the symmetric group needs at least one vertex")
    cycle = tuple((vertex + 1) % vertex_count for vertex in range(vertex_count))
    if vertex_count == 1:
        return ()
    swap = list(range(vertex_count))
    swap[0], swap[1] = swap[1], swap[0]
    return (cycle, tuple(swap))


def _multiset_support_stabilizer_generators(
    supports: tuple[Support, ...], vertex_count: int
) -> tuple[tuple[int, ...], ...]:
    """Generate the S(vertex_count) stabilizer of a support multiset.

    Active vertices are handled by exact backtracking over degree and pairwise
    codegree invariants, followed by an exact multiset-preservation check.
    Inactive vertices contribute an independent symmetric factor.
    """

    active = tuple(sorted({vertex for support in supports for vertex in support}))
    local_index = {vertex: index for index, vertex in enumerate(active)}
    local_supports = tuple(
        tuple(sorted(local_index[vertex] for vertex in support)) for support in supports
    )
    active_count = len(active)
    edge_counts = Counter(local_supports)
    degrees = [0] * active_count
    codegrees = [[0] * active_count for _ in range(active_count)]
    for support, multiplicity in edge_counts.items():
        for vertex in support:
            degrees[vertex] += multiplicity
        for left, right in itertools.combinations(support, 2):
            codegrees[left][right] += multiplicity
            codegrees[right][left] += multiplicity

    signatures = tuple(
        (degrees[vertex], tuple(sorted(codegrees[vertex]))) for vertex in range(active_count)
    )
    domains = tuple(
        tuple(
            candidate for candidate in range(active_count) if signatures[candidate] == signatures[v]
        )
        for v in range(active_count)
    )
    order = tuple(sorted(range(active_count), key=lambda v: (len(domains[v]), -degrees[v], v)))
    mapping = [-1] * active_count
    used = [False] * active_count
    automorphisms: list[tuple[int, ...]] = []

    def extend(position: int) -> None:
        if position == active_count:
            image_counts = Counter(
                tuple(sorted(mapping[vertex] for vertex in support))
                for support, multiplicity in edge_counts.items()
                for _ in range(multiplicity)
            )
            if image_counts == edge_counts:
                automorphisms.append(tuple(mapping))
            return
        vertex = order[position]
        for candidate in domains[vertex]:
            if used[candidate] or any(
                codegrees[vertex][other] != codegrees[candidate][mapping[other]]
                for other in order[:position]
            ):
                continue
            mapping[vertex] = candidate
            used[candidate] = True
            extend(position + 1)
            used[candidate] = False
            mapping[vertex] = -1

    extend(0)
    if not automorphisms:
        raise ValueError("support multiset has no identity automorphism")

    generators: list[tuple[int, ...]] = []
    for local_generator in _group_generators(tuple(sorted(set(automorphisms)))):
        full = list(range(vertex_count))
        for source, target in enumerate(local_generator):
            full[active[source]] = active[target]
        generators.append(tuple(full))

    inactive = tuple(vertex for vertex in range(vertex_count) if vertex not in local_index)
    if len(inactive) == 2:
        swap = list(range(vertex_count))
        swap[inactive[0]], swap[inactive[1]] = swap[inactive[1]], swap[inactive[0]]
        generators.append(tuple(swap))
    elif len(inactive) > 2:
        cycle = list(range(vertex_count))
        for offset, vertex in enumerate(inactive):
            cycle[vertex] = inactive[(offset + 1) % len(inactive)]
        generators.append(tuple(cycle))
        swap = list(range(vertex_count))
        swap[inactive[0]], swap[inactive[1]] = swap[inactive[1]], swap[inactive[0]]
        generators.append(tuple(swap))
    return tuple(dict.fromkeys(generators))


def _factored_symmetric_support_orbits(
    vertex_count: int,
    primary_size: int,
    primary_count: int,
    secondary_size: int,
) -> Iterator[tuple[tuple[Support, ...], int]]:
    """Enumerate two-color support-multiset orbits under S_n by stabilizers."""

    primary_supports = tuple(itertools.combinations(range(vertex_count), primary_size))
    primary_orbits = _higher_support_orbits(
        vertex_count,
        primary_size,
        primary_count,
        _symmetric_group_generators(vertex_count),
    )
    for primary_state, primary_orbit_size in primary_orbits:
        selected_primary = tuple(primary_supports[index] for index in primary_state)
        stabilizer = _multiset_support_stabilizer_generators(selected_primary, vertex_count)
        for secondary_state, secondary_orbit_size in _higher_support_orbits(
            vertex_count, secondary_size, 1, stabilizer
        ):
            secondary_supports = tuple(itertools.combinations(range(vertex_count), secondary_size))
            selected_secondary = tuple(secondary_supports[index] for index in secondary_state)
            yield (
                (*selected_primary, *selected_secondary),
                primary_orbit_size * secondary_orbit_size,
            )


def _build_factored_empty_pair_result(
    spec: ProfileSpec, *, progress: bool = False
) -> ProfileResult:
    """Compute PROFILE_A exactly without materializing its 1.9-billion states."""

    arithmetic = profile_arithmetic(spec)
    if (
        arithmetic["labels"] != POOL_SIZE
        or arithmetic["ticket_incidences"] != TICKET_COUNT * DRAW_SIZE
        or spec.pair_label_count != 0
        or spec.higher_support_counts != ((3, 4), (4, 1))
    ):
        raise ValueError(f"unexpected PROFILE_A arithmetic: {arithmetic}")

    census = pair_graph_census(TICKET_COUNT, 0)
    if len(census.classes) != 1:
        raise ValueError("empty pair graph census must have exactly one class")
    graph = census.classes[0]
    structural_orbits = 0
    legal_classes = 0
    maximum = -1
    maximizing: list[SupportSystem] = []
    represented_states = 0
    if progress:
        _log("PROFILE_A factoring triple-support orbits under the empty-graph S10 action")
    for higher_supports, orbit_size in _factored_symmetric_support_orbits(
        TICKET_COUNT, primary_size=3, primary_count=4, secondary_size=4
    ):
        structural_orbits += 1
        represented_states += orbit_size
        system = SupportSystem(TICKET_COUNT, (), higher_supports)
        if not is_legal_support_system(system, spec):
            continue
        legal_classes += 1
        value = bonferroni_u3(system, spec)
        if value > maximum:
            maximum = value
            maximizing = [system]
        elif value == maximum:
            maximizing.append(system)
        if progress and structural_orbits % 100 == 0:
            _log(
                f"PROFILE_A factored_orbits={structural_orbits} legal_classes={legal_classes} "
                f"current_max_u3={maximum}"
            )

    expected_states = comb(comb(TICKET_COUNT, 3) + 4 - 1, 4) * comb(TICKET_COUNT, 4)
    burnside_orbits = _burnside_orbit_count_for_counts(
        graph, TICKET_COUNT, spec.higher_support_counts
    )
    if represented_states != expected_states:
        raise ValueError(f"factored orbit sizes do not partition states: {represented_states}")
    if structural_orbits != burnside_orbits:
        raise ValueError(
            "factored orbit count disagrees with Burnside: "
            f"{structural_orbits} != {burnside_orbits}"
        )
    if legal_classes == 0 or not maximizing:
        raise ValueError("PROFILE_A legal support census was empty")

    maximizing.sort(key=lambda system: system.class_id)
    status = compare_incumbent(maximum)

    exact_scores: list[dict[str, object]] = []
    best_exact_count: int | None = None
    if status == "SURVIVES_U3" and len(maximizing) <= 8:
        draws = all_main_draw_masks(POOL_SIZE, DRAW_SIZE)
        for system in maximizing:
            score = evaluate_portfolio(
                reconstruct_portfolio(system, spec), draws=draws
            ).official_any_prize_outcome_count
            if score > maximum:
                raise ValueError("exact score exceeded its third-order Bonferroni upper bound")
            best_exact_count = score if best_exact_count is None else max(best_exact_count, score)
            exact_scores.append(
                {"class_id": system.class_id, "official_any_prize_outcome_count": score}
            )

    return ProfileResult(
        spec=spec,
        pair_graph_class_count=len(census.classes),
        retained_pair_graph_class_count=len(census.classes),
        pair_graph_labeled_total=census.labeled_total,
        structural_orbit_count=structural_orbits,
        burnside_orbit_count=burnside_orbits,
        legal_class_count=legal_classes,
        max_legal_u3=maximum,
        status=status,
        maximizing_systems=tuple(maximizing),
        parity_probes=(),
        exact_scores=tuple(exact_scores),
        best_exact_count=best_exact_count,
    )


def build_mass18_result(*, progress: bool = False) -> dict[str, object]:
    """Derive and close every full-support mass-18 profile by exact U3."""

    profiles = derive_mass18_profiles()
    if profiles != FROZEN_MASS18_PROFILES:
        raise ValueError(
            f"derived mass-18 profiles differ from the frozen list: {profiles} != "
            f"{FROZEN_MASS18_PROFILES}"
        )
    specs = _profile_specs(profiles)
    outcomes: dict[str, ProfileResult] = {}
    for spec in specs:
        if spec.pair_label_count == 0:
            outcome = _build_factored_empty_pair_result(spec, progress=progress)
        else:
            outcome = _build_shared_profile_result(spec, progress=progress)
        outcomes[spec.name] = outcome

    survivors = [name for name, outcome in outcomes.items() if outcome.status == "SURVIVES_U3"]
    smallest = (
        min(survivors, key=lambda name: (outcomes[name].legal_class_count, name))
        if survivors
        else None
    )
    record: dict[str, object] = {name: outcome.as_record() for name, outcome in outcomes.items()}
    record.update(
        {
            "MASS18_PROFILE_COUNT": len(profiles),
            "MASS18_STATUS": "PARTIAL" if survivors else "CLOSED",
            "SMALLEST_SURVIVING_PROFILE": smallest,
            "K10_GLOBAL_OPTIMUM_STATUS": "UNKNOWN",
            "INCUMBENT_COUNT": INCUMBENT_COUNT,
        }
    )
    return _seal_result(record)


def _build_shared_profile_result(spec: ProfileSpec, *, progress: bool) -> ProfileResult:
    """Call the unchanged complete pair-graph profile census."""

    return _shared_build_profile_result(spec, progress=progress, verify_public_u3=False)


def main(argv: Sequence[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] != "mass18":
        raise SystemExit(f"unknown mode: {arguments[0]}")
    print(json.dumps(build_mass18_result(progress=True), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
