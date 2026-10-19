"""Independent finite-domain checks and falsifiable guards for the B/C Goodman proof."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from itertools import combinations, product
from math import comb
from typing import cast
from unittest.mock import patch

import pytest

from lottolab.research import b649_min_s2_tied_owners_bc_goodman_cert_r1 as c

Authority = tuple[dict[str, object], dict[str, c.Row]]


@pytest.fixture(scope="module")
def zero() -> c.ZeroProof:
    return c.zero_graphs()


@pytest.fixture(scope="module")
def proofs(zero: c.ZeroProof) -> dict[str, dict[str, object]]:
    return {p: c.theorem(p, zero) for p in c.TARGETS}


@pytest.fixture(scope="module")
def seven_authority() -> Authority:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("frozen replay called a scientific/search entrypoint")

    with (
        patch.object(c.prior, "compute_result", forbidden),
        patch.object(c.prior, "cap_theorem", forbidden),
        patch.object(c.prior.t256, "compute_result", forbidden),
        patch.object(c.prior.t256, "t256_theorem", forbidden),
        patch.object(c.three, "compute_result", forbidden),
        patch.object(c.three, "core_zero_theorem", forbidden),
        patch.object(c.split, "degree_configurations", forbidden),
        patch.object(c.split, "split_certificate", forbidden),
        patch.object(c.chase, "chase", forbidden),
        patch.object(c.chase, "refine", forbidden),
        patch.object(c.r32, "compute_result", forbidden),
    ):
        return c.prior.seven_row_authority()


@pytest.fixture(scope="module")
def authority(seven_authority: Authority) -> Authority:
    with patch.object(c.prior, "seven_row_authority", return_value=seven_authority):
        return c.frozen_authority()


@pytest.fixture(scope="module")
def result(authority: Authority) -> dict[str, object]:
    with patch.object(c, "frozen_authority", return_value=authority):
        return c.compute_result()


def havel_hakimi(degrees: Sequence[int]) -> bool:
    """Graphicality via vertex removal, independent of the verifier's Erdos-Gallai."""
    d = list(degrees)
    if any(type(v) is not int or not 0 <= v < len(d) for v in d):
        return False
    while d:
        d.sort(reverse=True)
        top = d.pop(0)
        if not top:
            return True
        if top > len(d):
            return False
        for i in range(top):
            d[i] -= 1
            if d[i] < 0:
                return False
    return True


@pytest.mark.parametrize(
    ("profile", "floor", "cap", "wedges", "raw", "counts", "floors"),
    [
        (
            c.PROFILE_B,
            56,
            239,
            112,
            20736,
            [1, 55, 510, 1642, 2612, 2593, 1720],
            [85, 77, 74, 69, 65, 61, 56],
        ),
        (
            c.PROFILE_C,
            58,
            237,
            118,
            19200,
            [1, 55, 465, 1441, 2477, 2458, 1418],
            [81, 74, 72, 68, 62, 58, 64],
        ),
    ],
)
def test_each_theorem(
    proofs: dict[str, dict[str, object]],
    profile: str,
    floor: int,
    cap: int,
    wedges: int,
    raw: int,
    counts: list[int],
    floors: list[int],
) -> None:
    p = proofs[profile]
    assert p["STATUS"] == "PROVEN"
    assert p["GOODMAN_INCLUSION_EXCLUSION"] == p["GOODMAN_DEGREE_PRODUCT"] == 295
    assert (p["G_EDGES"], p["H_EDGES"], p["W"]) == (93, 97, 829)
    assert p["I_LOWER_BOUND"] == floor and p["TRIANGLE_CAP"] == cap
    assert p["OPEN_WEDGE_LOWER_BOUND"] == wedges
    assert p["RAW_LABELLED_VECTORS_CHECKED"] == raw
    assert p["ACCEPTED_NECESSARY_VECTORS_BY_M"] == counts and p["I_FLOORS_BY_M"] == floors
    assert p["ATTAINMENT"] == p["RELAXED_MINIMIZERS_REALIZABLE"] == "NOT_ASSERTED"


@pytest.mark.parametrize("profile", c.TARGETS)
def test_entire_core_domain_with_independent_graphicality(
    profile: str, proofs: dict[str, dict[str, object]]
) -> None:
    d = [v for v in map(int, profile) if v]
    capacities = [6 - v for v in d]
    raw, counts = 0, [0] * 7
    for b in product(*(range(v + 1) for v in capacities)):
        raw += 1
        a = [r - s for r, s in zip(capacities, b, strict=True)]
        h = [7 - v + s for v, s in zip(d, b, strict=True)]
        assert c.split.graphical(a) == havel_hakimi(a)
        assert c.split.graphical(h) == havel_hakimi(h)
        if 6 <= sum(b) <= 18 and sum(b) % 2 == 0 and havel_hakimi(a) and havel_hakimi(h):
            counts[(18 - sum(b)) // 2] += 1
    assert raw == proofs[profile]["RAW_LABELLED_VECTORS_CHECKED"]
    assert counts == proofs[profile]["ACCEPTED_NECESSARY_VECTORS_BY_M"]


def test_entire_zero_domain_with_independent_edge_sets(zero: c.ZeroProof) -> None:
    slots = list(combinations(range(6), 2))
    minima, counts = [10**9] * 7, [0] * 7
    for mask in range(2**15):
        edges = {edge for i, edge in enumerate(slots) if mask & (1 << i)}
        degrees = [sum(v in e for e in edges) for v in range(6)]
        assert havel_hakimi(degrees)
        if len(edges) > 6:
            continue
        triangles = sum(
            all(e in edges for e in combinations(q, 2)) for q in combinations(range(6), 3)
        )
        m = 6 - len(edges)
        counts[m] += 1
        minima[m] = min(minima[m], 12 * len(edges) - sum(v**2 for v in degrees) + triangles)
    assert zero.graphs_checked == 32768
    assert zero.floors == tuple(minima) == (37, 30, 28, 24, 18, 10, 0)
    assert zero.counts == tuple(counts) == tuple(comb(15, 6 - m) for m in range(7))


def test_core_triangle_floor_on_every_five_vertex_graph_joined_to_k9() -> None:
    # 1024 distinct dense 14-vertex graphs exercise nonzero ell_i and both floor rules.
    slots = list(combinations(range(5), 2))
    for mask in range(2**10):
        small = {e for i, e in enumerate(slots) if mask >> i & 1}
        small_degrees = [sum(v in e for e in small) for v in range(5)]
        degrees = [13] * 9 + [9 + d for d in small_degrees]
        small_triangles = sum(
            all(e in small for e in combinations(q, 2)) for q in combinations(range(5), 3)
        )
        actual = comb(9, 3) + 5 * comb(9, 2) + 9 * len(small) + small_triangles
        floor = c.core_triangle_floor(degrees, comb(9, 2) + 9 * 5 + len(small))
        assert 0 < floor <= actual


def test_bad_core_graph_rejected() -> None:
    with pytest.raises(AssertionError, match="sum differs"):
        c.core_triangle_floor([1] * 14, 8)
    with pytest.raises(AssertionError, match="not graphical"):
        c.core_triangle_floor([13, 1] + [0] * 12, 7)


@pytest.mark.parametrize("profile", c.TARGETS)
def test_zero_triangle_term_is_load_bearing(profile: str, zero: c.ZeroProof) -> None:
    genuine = c.theorem(profile, zero)
    ablated = c.theorem(profile, replace(zero, floors=(0,) * 7))
    assert c.integer(ablated["TRIANGLE_CAP"]) > c.integer(genuine["TRIANGLE_CAP"])


def test_ccc_floor_is_load_bearing_for_b(zero: c.ZeroProof) -> None:
    with patch.object(c, "core_triangle_floor", return_value=0):
        assert c.theorem(c.PROFILE_B, zero)["TRIANGLE_CAP"] == 240
    assert c.theorem(c.PROFILE_B, zero)["TRIANGLE_CAP"] == 239


@pytest.mark.parametrize("profile", c.TARGETS)
@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("GOODMAN_CONSTANT", 294),
        ("TICKET_CAPACITY", 7),
        ("TRIPLE_SUPPORTS", 21),
        ("PAIR_SUPPORTS", 28),
    ],
)
def test_mutated_mathematical_premises_rejected(profile: str, name: str, value: int) -> None:
    with patch.object(c, name, value), pytest.raises(AssertionError, match="premises fail"):
        c.premises(profile)
    assert c.premises(profile)["GOODMAN_INCLUSION_EXCLUSION"] == 295


@pytest.mark.parametrize("profile", [c.OWNER_A, c.prior.TARGET_PROFILE, c.PROFILE_B[::-1]])
def test_other_profile_rejected(profile: str) -> None:
    with pytest.raises(AssertionError, match="exactly B and C"):
        c.premises(profile)


@pytest.mark.parametrize(
    ("profile", "cap", "peak"),
    [
        (c.PROFILE_B, 239, (239, 313165236, 303, 198, 159999, 4866624)),
        (c.PROFILE_C, 237, (237, 313147312, 288, 198, 149814, 4842880)),
    ],
)
def test_complete_route_b_per_profile(profile: str, cap: int, peak: c.Term) -> None:
    terms, bound = c.route_b(profile, cap, 112)
    old, old_bound = c.route_b(profile, 265, 112)
    assert [t[0] for t in terms] == list(range(22, cap + 1))
    assert terms[-1] == peak and bound == max(t[1] for t in terms) == peak[1]
    assert bound <= c.INCUMBENT and old_bound == 313398248
    assert terms == old[: cap - 21]
    assert all(term[4] >= 112 for term in terms)


@pytest.mark.parametrize("profile", c.TARGETS)
def test_correlated_route_b_mutation_rejected(profile: str) -> None:
    genuine = c.r32.route_b_envelope

    def bumped(d: tuple[int, ...], cap: int, base: int) -> list[c.Term]:
        terms = genuine(d, cap, base)
        t, bound, k4, contained, s4, s3 = terms[-1]
        terms[-1] = (t, bound - 1, k4, contained, s4, s3)
        return terms

    with patch.object(c.r32, "route_b_envelope", bumped):
        with pytest.raises(AssertionError, match="implementations differ"):
            c.route_b(profile, 237, 112)
        with (
            patch.object(c.split, "route_b_terms", bumped),
            pytest.raises(AssertionError, match="exact arithmetic"),
        ):
            c.route_b(profile, 237, 112)
    assert c.route_b(profile, 265, 112)[1] == c.FAMILY_BOUND


def test_content_addressed_result_exact_reproduction(result: dict[str, object]) -> None:
    payload = c.two.render(result)
    path = c.ROOT / c.RESULT_DIRECTORY / f"{c.RESULT_STEM}-{c.sha256(payload)}.json"
    assert path.read_bytes() == payload
    assert list(path.parent.glob(f"{c.RESULT_STEM}-*.json")) == [path]


def test_frozen_ledger_exact_two_row_recount(
    authority: Authority, result: dict[str, object]
) -> None:
    frozen, ledger = authority
    updates = {c.PROFILE_B: (313165236, 239), c.PROFILE_C: (313147312, 237)}
    after = c.apply_bc(ledger, updates)
    assert (
        c.two.full_digest(ledger)
        == frozen["FULL_ROWS_SHA256_AFTER"]
        == result["FULL_ROWS_SHA256_BEFORE"]
    )
    assert c.two.full_digest(after) == result["FULL_ROWS_SHA256_AFTER"]
    assert sorted(p for p in ledger if ledger[p] != after[p]) == sorted(c.TARGETS)
    assert len(after) == result["LEDGER_ROWS"] == 4647
    assert after[c.OWNER_A] == ledger[c.OWNER_A]
    assert c.three.family(after) == (313398248, [c.OWNER_A], 313398144)
    assert result["FAMILY_BOUND_BEFORE"] == result["FAMILY_BOUND_AFTER_BC_ONLY"] == 313398248
    assert result["FAMILY_DELTA_BC_ONLY"] == 0 and result["OWNER_A_UNMODIFIED"] == "YES"
    assert result["CURSOR_BOUND"] == c.chase.prior.CURSOR_BOUND == 313394584
    assert result["CERTIFICATES_COMPOSED"] == 10
    for p in c.TARGETS:
        assert after[p].s4_base == ledger[p].s4_base == 112
        assert after[p].realization == ledger[p].realization is None
    certificates = [c.object_row(r) for r in c.rows(result["PROFILES"])]
    assert all(
        r["THEOREM_STATUS"] == "PASS" and r["STRICT_GAIN_EXCLUDED"] is True for r in certificates
    )
    assert all(
        c.object_row(r["RECORDED_REALIZATION"])["STATUS"]
        == "NOT_AVAILABLE_FROZEN_ROW_HAS_NO_REALIZATION"
        for r in certificates
    )


def test_inherited_status_and_caveats_preserved(
    authority: Authority, result: dict[str, object]
) -> None:
    assert result["PRESERVED_T248_STATUS"] == {k: authority[0][k] for k in c.PRESERVED_T248_FIELDS}
    message = c.text(result["T248_AUTHORITY_COMMIT_MESSAGE"])
    assert message == c.chase.git("log", "-1", "--format=%B", c.BASE_HEAD).decode()
    assert c.T248_JUDGE_RECORD in message.splitlines()
    assert "SELF_CHECK_ONLY" in message and "Historical accepted Goodman U64" in message
    assert (
        c.object_row(result["HISTORICAL_SOURCE"])["STATUS"]
        == "SCIENTIFIC_PASS_RESOURCE_CONFORMANCE_FAIL"
    )
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    for name in (
        "EXISTING_CERTIFICATES_MUTATED",
        "FROZEN_LEDGER_MUTATED",
        "RUN1_MUTATED",
        "HEAVY_SEARCH_STARTED",
        "REMOTE_WRITE",
    ):
        assert result[name] == "NO"


def test_support_semantics_and_wrong_realization_rejected(authority: Authority) -> None:
    realization = authority[1][c.prior.TARGET_PROFILE].realization
    assert realization is not None
    triples, pairs = realization
    assert c.three.legal_degrees(triples, pairs)
    with pytest.raises(AssertionError, match="support counts"):
        c.realization_check(c.PROFILE_B, triples[:-1], pairs, 239)
    with pytest.raises(AssertionError, match="more than one label"):
        c.realization_check(c.PROFILE_C, (triples[0], *triples[1:-1], triples[0]), pairs, 237)
    with pytest.raises(AssertionError, match="wrong realization profile"):
        c.realization_check(c.PROFILE_B, triples, pairs, 239)


@pytest.mark.parametrize(
    "updates",
    [
        {c.PROFILE_B: (313165236, 239)},
        {c.OWNER_A: (313165236, 239), c.PROFILE_C: (313147312, 237)},
        {c.PROFILE_B: (313398248, 239), c.PROFILE_C: (313147312, 237)},
        {c.PROFILE_B: (313165236, 265), c.PROFILE_C: (313147312, 237)},
        {c.PROFILE_B: (313165236.0, 239), c.PROFILE_C: (313147312, 237)},
    ],
)
def test_invalid_updates_rejected(authority: Authority, updates: object) -> None:
    with pytest.raises(AssertionError, match=r"exactly B and C|tighten|exact integers"):
        c.apply_bc(authority[1], cast(dict[str, tuple[int, int]], updates))


def test_double_application_rejected(authority: Authority) -> None:
    updates = {c.PROFILE_B: (313165236, 239), c.PROFILE_C: (313147312, 237)}
    after = c.apply_bc(authority[1], updates)
    with pytest.raises(AssertionError, match="tighten"):
        c.apply_bc(after, updates)


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("BASE_TREE", "0" * 40, "tree mismatch"),
        ("T248_RESULT_SHA256", "0" * 64, "digest mismatch"),
        ("T248_JUDGE_RECORD", "Fresh-context Judge: VERIFIED", "Judge record missing"),
    ],
)
def test_mutated_authority_rejected(
    seven_authority: Authority, name: str, value: str, message: str
) -> None:
    with (
        patch.object(c.prior, "seven_row_authority", return_value=seven_authority),
        patch.object(c, name, value),
        pytest.raises(AssertionError, match=message),
    ):
        c.frozen_authority()


def test_mutated_t248_replay_rejected(seven_authority: Authority) -> None:
    genuine = c.prior.apply_eighth

    def drifted(ledger: dict[str, c.Row], bound: int, cap: int, source: str) -> dict[str, c.Row]:
        result = genuine(ledger, bound, cap, source)
        result[c.OWNER_A] = replace(result[c.OWNER_A], bound=result[c.OWNER_A].bound - 1)
        return result

    with (
        patch.object(c.prior, "seven_row_authority", return_value=seven_authority),
        patch.object(c.prior, "apply_eighth", drifted),
        pytest.raises(AssertionError, match="does not reproduce"),
    ):
        c.frozen_authority()
