"""Independent integer reconstruction, complete local patterns, and adversarial seals."""

from __future__ import annotations

import copy
import hashlib
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import comb

import pytest

from lottolab.research import b649_min_s2_goodman_r2_t249_formal_cert_r1 as c

type Baseline = tuple[dict[str, int], dict[str, object], dict[str, object]]


@pytest.fixture(scope="module")
def baseline() -> Baseline:
    return c.baseline()


@pytest.fixture(scope="module")
def certificate() -> dict[str, object]:
    return c.compute_result()


def test_sealed_result_reproduced(certificate: dict[str, object]) -> None:
    assert c.RESULT_PATH.read_bytes() == c.render(certificate)
    assert (
        certificate["IMPLEMENTATION_SHA256"]
        == hashlib.sha256(
            c.authority.ROOT.joinpath(
                "src/lottolab/research/b649_min_s2_goodman_r2_t249_formal_cert_r1.py"
            ).read_bytes()
        ).hexdigest()
    )


def test_support_partition_and_goodman_graph_identity() -> None:
    profile = [int(d) for d in "66665555554421100000"]
    assert len(profile) == 20 and sum(profile) == 3 * 22
    assert sum(6 - d for d in profile) == 2 * 27
    assert sum(2 * d + (6 - d) for d in profile) == 2 * (3 * 22 + 27)
    assert sum(comb(6 + d, 2) for d in profile) == 829
    assert comb(20, 3) - 18 * 93 + 829 == 295
    # Exhaust all 1024 five-vertex simple graphs, counting actual triangles and independent triples.
    edges = tuple(combinations(range(5), 2))
    for bits in product((False, True), repeat=10):
        present = {edge for edge, active in zip(edges, bits, strict=True) if active}
        degrees = [sum(v in edge for edge in present) for v in range(5)]
        triangles = independent = 0
        for vertices in combinations(range(5), 3):
            induced = sum(edge in present for edge in combinations(vertices, 2))
            triangles += induced == 3
            independent += induced == 0
        assert triangles + independent == comb(5, 3) - 3 * len(present) + sum(
            comb(v, 2) for v in degrees
        )


@pytest.mark.parametrize("profile", ["66665555555411100000", "66665555554421000000", "0" * 20])
def test_wrong_profile_rejected(profile: str) -> None:
    with pytest.raises(AssertionError, match="wrong profile"):
        c.certify(profile)


def test_core_zero_accounting_all_m() -> None:
    model = c.premises()
    assert model["CORE_SIZE"] == 15 and model["ZERO_SIZE"] == 5
    for m, entry in enumerate(c.authority.items(model["M_ACCOUNTING"])):
        row = c.obj(entry)
        cross = c.integer(row["CROSS_EDGES"])
        zero = c.integer(row["ZERO_EDGES"])
        assert 2 * m + cross == 24
        assert m + cross + zero == 27
        assert zero <= 10 and 0 <= m <= 7
        assert 105 - 66 - m == row["CORE_NONEDGES"]
        assert 10 - zero == row["ZERO_NONEDGES"]


def test_low_incidence_universal_cases_independently() -> None:
    # Enumerate actual set intersections, not the implementation's bit-mask encoding.
    low = (0, 1, 2)
    intersections = tuple(frozenset(s) for n in range(1, 4) for s in combinations(low, n))
    templates: set[tuple[int, int]] = set()
    for n in range(1, 5):
        for supports in combinations_with_replacement(intersections, n):
            if [sum(v in s for s in supports) for v in low] != [2, 1, 1]:
                continue
            shadow_pairs = [pair for s in supports for pair in combinations(sorted(s), 2)]
            if len(shadow_pairs) != len(set(shadow_pairs)):
                continue
            mask = sum(
                1 << bit
                for bit, edge in enumerate(((0, 1), (0, 2), (1, 2)))
                if edge in shadow_pairs
            )
            hub_slots = sum(3 - len(s) for s in supports)
            templates.add((mask, hub_slots))
    assert templates == {(0, 8), (1, 5), (2, 5), (4, 5), (3, 2), (7, 2)}
    assert {mask for mask, hubs in templates if hubs >= 4} == set(c.incidence_masks())
    observed = {
        (c.integer(t["SHADOW_MASK"]), c.integer(t["R_HUB_CAPACITY"]))
        for t in c.incidence_templates()
    }
    assert observed == templates


@pytest.mark.parametrize("shadow", [3, 7])
def test_each_forbidden_incidence_rejected(shadow: int) -> None:
    with pytest.raises(AssertionError, match="invalid incidence restriction"):
        c.certify(shadows=tuple(sorted((*c.incidence_masks(), shadow))))


@pytest.mark.parametrize("bad", [(-1, 5, 5), (5, 0, 0), (0, 6, 0), (1, 2)])
def test_invalid_low_incidence_degrees_rejected(bad: tuple[int, ...]) -> None:
    with pytest.raises(AssertionError, match="invalid low incidence"):
        c.low_options(bad, 7, c.incidence_masks())


def test_all_vectors_and_zero_graphs_independent(certificate: dict[str, object]) -> None:
    enum = c.obj(c.obj(certificate["THEOREM"])["ENUMERATION"])
    vectors = list(c.zero_neighbour_vectors())
    assert len(vectors) == len(set(vectors)) == 2**6 * 3**2 * 5 * 6**2 == 103680
    assert vectors[0] == (0,) * 15
    assert vectors[-1] == (0,) * 4 + (1,) * 6 + (2, 2, 4, 5, 5)
    counts = [sum(sum(v) == 24 - 2 * m for v in vectors) for m in range(8)]
    assert counts == enum["RETAINED_VECTORS_BY_M"]
    assert hashlib.sha256(b"".join(bytes(v) for v in vectors)).hexdigest() == enum["VECTORS_SHA256"]
    assert enum["ZERO_MASKS_VISITED"] == 1024
    assert enum["ZERO_GRAPH_COUNTS_BY_M"] == [comb(10, 7 - m) for m in range(8)]
    assert enum["ZERO_DEGREE_CLASSES_BY_M"] == [4, 5, 5, 5, 4, 2, 1, 1]
    assert enum["RELAXED_STATES_BY_M"] == [16, 1245, 14690, 79085, 203344, 216562, 158942, 161710]


def test_eight_floors_independent_representative_arithmetic(certificate: dict[str, object]) -> None:
    # Exchange only equal-d tickets. Encode the correction with edge sets, not cached LowOption.
    zero_reps: list[set[tuple[int, ...]]] = [set() for _ in range(8)]
    z_pairs = tuple(combinations(range(5), 2))
    for active in product((False, True), repeat=10):
        f_edges = [edge for edge, bit in zip(z_pairs, active, strict=True) if bit]
        if len(f_edges) <= 7:
            zero_reps[7 - len(f_edges)].add(
                tuple(sorted(sum(v in edge for edge in f_edges) for v in range(5)))
            )
    low_pairs = ((0, 1), (0, 2), (1, 2))
    floors = [10**6] * 8
    states = [0] * 8
    visited = 0
    for ones, four_pair, two, one_pair in product(
        range(7),
        combinations_with_replacement(range(3), 2),
        range(5),
        combinations_with_replacement(range(6), 2),
    ):
        visited += 1
        b = (0,) * 4 + (0,) * (6 - ones) + (1,) * ones + four_pair + (two,) + one_pair
        if (24 - sum(b)) % 2 or not 0 <= (24 - sum(b)) // 2 <= 7:
            continue
        m = (24 - sum(b)) // 2
        low_b = b[-3:]
        p = [cap - cross for cap, cross in zip((4, 5, 5), low_b, strict=True)]
        h = [degree + cross for degree, cross in zip((6, 7, 7), low_b, strict=True)]
        a = sum((8 - degree + cross) * cross for degree, cross in zip(c.CORE, b, strict=True))
        s = sum(max(0, cross * (cross - 1) // 2 - 3 - m) for cross in b)
        for f in zero_reps[m]:
            for shadow in ((), (low_pairs[0],), (low_pairs[1],), (low_pairs[2],)):
                for bits in product((False, True), repeat=3):
                    pairs = [edge for edge, bit in zip(low_pairs, bits, strict=True) if bit]
                    if len(pairs) > m or any(edge in shadow for edge in pairs):
                        continue
                    if any(sum(v in edge for edge in pairs) > p[v] for v in range(3)):
                        continue
                    missing = [
                        edge for edge in low_pairs if edge not in shadow and edge not in pairs
                    ]
                    outside = [h[v] - sum(v in edge for edge in missing) for v in range(3)]
                    correction = sum(max(0, low_b[i] + low_b[j] - 5) for i, j in missing)
                    correction += sum(max(0, outside[i] + outside[j] - 12) for i, j in missing)
                    correction += len(missing) == 3
                    value = 272 - 16 * m - a - sum(degree**2 for degree in f) + s + correction
                    states[m] += 1
                    floors[m] = min(floors[m], value)
    assert visited == 4410
    assert states == [16, 270, 1545, 5380, 10284, 8976, 5924, 5989]
    assert floors == [59, 56, 55, 50, 52, 52, 50, 46]
    theorem = c.obj(certificate["THEOREM"])
    assert floors == c.obj(theorem["ENUMERATION"])["I_FLOORS"]
    assert theorem["I_FLOOR"] == 46 and theorem["T_CAP"] == 295 - min(floors) == 249


def test_removing_incidence_lemma_weakens_domain_not_just_constant() -> None:
    original = c.low_options((4, 5, 5), 0, c.incidence_masks())
    weakened = c.low_options((4, 5, 5), 0, (0, 1, 2, 3, 4, 7))
    assert {v.shadow for v in weakened} - {v.shadow for v in original} == {3, 7}
    assert min(v.core + v.mixed for v in weakened) < min(v.core + v.mixed for v in original)
    mutated = c.enumerate_relaxation((0, 1, 2, 3, 4, 7))
    assert mutated["LABELLED_VECTORS"] == 103680
    assert mutated["I_FLOORS"] == [37, 34, 33, 28, 30, 30, 40, 40]
    assert mutated["MIN_I"] == 28 < 46
    # Feeding that widened domain to the certificate must fail before adopting a cap.
    with pytest.raises(AssertionError, match="invalid incidence restriction"):
        c.certify(shadows=(0, 1, 2, 3, 4, 7))


def test_full_route_b_exact_rational_rounding(certificate: dict[str, object]) -> None:
    terms = c.route_b(c.TARGET, 249)
    assert len(terms) == 228 and [t[0] for t in terms] == list(range(22, 250))
    assert terms == c.route_b(c.TARGET, 265)[:228]
    assert [list(t) for t in terms] == c.obj(certificate["ROUTE_B"])["ALL_T_TERMS"]
    d = [int(v) for v in c.TARGET]
    degrees = [6 + v for v in d]
    w = sum(comb(v, 2) for v in degrees)
    c3 = sum(comb(v, 3) for v in degrees)
    amax = sum(v * (g - 2) for v, g in zip(d, degrees, strict=True)) // 3
    for t, bound, k4, contained, s4, s3 in terms:
        need = Fraction(c3 - (max(degrees) - 2) * (w - 3 * t), 4)
        assert k4 == max(0, -((-need.numerator) // need.denominator))
        assert contained == min(k4, amax)
        assert s4 == max(112, 679 * k4 - 231 * contained)
        assert s3 == 2800 * (w - 3 * t) + 7000 * 22 + 20272 * (t - 22)
        exact = 372228640 - 63838600 + s3 - Fraction(4 * s4, 7)
        assert 0 <= bound - exact < 1
    assert terms[-1] == (249, 313254468, 379, 198, 211603, 4985344)
    assert max(t[1] for t in terms) == 313254468
    assert 313397860 - max(t[1] for t in terms) == 143392
    assert 313263888 - max(t[1] for t in terms) == 9420 > 0
    assert certificate["STRICT_GAIN_EXCLUDED"] == "YES"


def test_source_and_base_hash_tamper_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = dict(c.SOURCE_PINS)
    altered = dict(original)
    altered["b649_k20_min_s2_route_b_current_owner_refinement_r32"] = "0" * 64
    monkeypatch.setattr(c, "SOURCE_PINS", altered)
    with pytest.raises(AssertionError, match="source-hash mismatch"):
        c.source_authority()
    monkeypatch.setattr(c, "SOURCE_PINS", original)
    monkeypatch.setattr(c, "BASE_TREE", "0" * 40)
    with pytest.raises(AssertionError, match="base tree mismatch"):
        c.source_authority()


def test_result_source_sha_tamper_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(c, "BASE_RESULT_SHA", "0" * 64)
    with pytest.raises(AssertionError, match="source-hash mismatch"):
        c.source_authority()


@pytest.mark.parametrize(
    "field,value", [("BOUND", 313394583), ("ID", c.TARGET), ("PROFILE_COUNT", 196)]
)
def test_wrong_cursor_rejected(baseline: Baseline, field: str, value: object) -> None:
    bounds, cursor, _ = baseline
    tampered = {**cursor, field: value}
    with pytest.raises(AssertionError, match="wrong cursor"):
        c.scenarios(bounds, tampered, cursor, 313254468)


def test_wrong_sealed_cursor_rejected(baseline: Baseline, monkeypatch: pytest.MonkeyPatch) -> None:
    sealed = copy.deepcopy(baseline[2])
    c.obj(sealed["CURSOR"])["BOUND"] = 0
    monkeypatch.setattr(c, "source_authority", lambda: sealed)
    with pytest.raises(AssertionError, match="wrong baseline cursor"):
        c.baseline()


def test_family_scenarios_independently(baseline: Baseline, certificate: dict[str, object]) -> None:
    before, cursor, _ = baseline
    original = copy.deepcopy(before)
    one = {**before, c.TARGET: 313254468}
    two = {**one, "66665555555331000000": 313218904, "66665555555411100000": 313353140}
    actual = c.obj(certificate["FAMILY_SCENARIOS"])
    for name, scenario, expected, ids in (
        ("SCENARIO_1", one, 313398144, ["66665555555331000000", "66665555555411100000"]),
        ("SCENARIO_2", two, 313396120, ["65555555555550000000"]),
    ):
        all_bounds = {**scenario, c.authority.string(cursor["ID"]): c.integer(cursor["BOUND"])}
        assert max(all_bounds.values()) == expected
        assert sorted(p for p, b in all_bounds.items() if b == expected) == ids
        row = c.obj(actual[name])
        assert row["FAMILY_BOUND"] == expected and row["OWNER_IDS"] == ids
        assert row["GAP"] == expected - 313263888
    assert c.obj(actual["SCENARIO_2"])["STATUS"] == "PROJECTED_ONLY"
    assert c.obj(actual["SCENARIO_2"])["FORMAL_T244_T259_AUTHORITY"] == "NOT_CLAIMED"
    assert before == original
    assert [p for p in before if before[p] != one[p]] == [c.TARGET]
    assert sorted(p for p in before if before[p] != two[p]) == sorted((c.TARGET, *c.PROJECTED_CAPS))


def test_inherited_caveats_and_historical_status_preserved(
    baseline: Baseline, certificate: dict[str, object]
) -> None:
    provenance = c.obj(certificate["BASE_AUTHORITY"])
    assert provenance["INHERITED_CAVEATS"] == baseline[2]["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
    assert provenance["CURSOR"] == baseline[1]
    historical = c.obj(certificate["HISTORICAL_R2"])
    assert historical["RESOURCE_CONFORMANCE"] == "REFUTED"
    assert historical["PROMOTED_AS_AUTHORITY"] == historical["HISTORICAL_U64_BOUND_USED"] == "NO"
    assert historical["BONFERRONI_5_USED"] == "NO"
    assert certificate["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
