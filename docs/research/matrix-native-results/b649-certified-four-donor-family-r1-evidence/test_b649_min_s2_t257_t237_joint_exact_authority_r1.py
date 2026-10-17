from __future__ import annotations

from copy import deepcopy
from itertools import combinations
from typing import cast

import pytest

from lottolab.research import b649_min_s2_t257_t237_joint_exact_authority_r1 as cert


@pytest.fixture(scope="module")
def base() -> cert.Document:
    return cert.load_base()


def test_ceil_import_and_exact_fraction_rounding() -> None:
    terms = cert.fraction_terms(23)
    assert len(terms) == 2
    for triangles in (22, 23, 24, 50, 100, 237):
        fraction_term = cert.fraction_terms(triangles)[-1]
        integer_term = cert.integer_term(triangles)
        assert fraction_term == integer_term
    degrees = (3, 3, 2, 2, 2)
    assert cert.floors_b(degrees) == cert.floors_a(degrees)
    with pytest.raises(ValueError, match="ceiling"):
        cert.validate_rounding(5000, 113, 372228640 - 63838600 + 5000 - 65)


def test_base_outer_identity_and_upstream_lineage(base: cert.Document) -> None:
    assert cert.BASE_HEAD == "9acea1331e021a9623fa593997d90cfc89a69136"
    assert cert.BASE_TREE == "de577e8d6f3ccbe52e663c96ee1528c95a0ee7ec"
    assert cert.BASE_SHA == "9fbe17d020573835cd69f16296fee224ff4f83aef8b3e7a644f2ffaabdfe92c9"

    expected_upstream_head = "bee6acaaf9d2781e2aae560138d8be99fb4789ed"
    expected_upstream_tree = "7b382a405d8d734763b477aa88efafeba2e1ed9b"
    expected_upstream_sha = "bca4ad19aebb9808c952259d677a4a07381aa43392c38715c8265427960fe6f6"

    assert base["BASE_HEAD"] == cert.BASE_UPSTREAM_HEAD == expected_upstream_head
    assert base["BASE_TREE"] == cert.BASE_UPSTREAM_TREE == expected_upstream_tree
    assert base["BASE_RESULT_SHA256"] == cert.BASE_UPSTREAM_SHA == expected_upstream_sha
    cert.validate_base_upstream(base)


def test_rejects_wrong_base_outer_identity() -> None:
    with pytest.raises(ValueError, match="Base tree identity"):
        cert.load_base(base_tree="0" * 40)
    with pytest.raises(ValueError, match="immutable source SHA256"):
        cert.load_base(base_sha="0" * 64)


def test_rejects_wrong_base_upstream_identity(base: cert.Document) -> None:
    with pytest.raises(ValueError, match="Base upstream lineage identity"):
        cert.load_base(upstream_head="0" * 40)
    with pytest.raises(ValueError, match="Base upstream lineage identity"):
        cert.load_base(upstream_tree="0" * 40)
    with pytest.raises(ValueError, match="Base upstream lineage identity"):
        cert.load_base(upstream_sha="0" * 64)
    for key in ("BASE_HEAD", "BASE_TREE", "BASE_RESULT_SHA256"):
        corrupted = dict(base, **{key: "0" * 40})
        with pytest.raises(ValueError, match="Base upstream lineage identity"):
            cert.validate_base_upstream(corrupted)


def test_donor_report_hash_same_line_and_next_line() -> None:
    hash_value = "dd8cdc8ded41ecf93a8846aea1ae226979eb18d6c8a54f51c51b0e33066403e2"
    same_line = (
        "Fresh-context scientific Judge: VERIFIED_WITH_CAVEATS; G01-G17 PASS.\n"
        f"Exact judged tree: {cert.DONOR_TREE}\n"
        f"Sealed precommit report SHA256: {hash_value}\n"
        "Final disposition\n"
    )
    assert cert.parse_donor_report_hash(same_line) == hash_value

    next_line = (
        "Fresh-context scientific Judge: VERIFIED_WITH_CAVEATS; G01-G17 PASS.\n"
        f"Exact judged tree: {cert.DONOR_TREE}\n"
        "Sealed precommit report SHA256:\n"
        f"{hash_value}\n"
        "Final disposition\n"
    )
    assert cert.parse_donor_report_hash(next_line) == hash_value

    next_line_with_empty = f"Sealed precommit report SHA256:\n\n{hash_value}\n"
    assert cert.parse_donor_report_hash(next_line_with_empty) == hash_value


def test_rejects_empty_truncated_or_illegal_donor_hash() -> None:
    with pytest.raises(ValueError, match="T257 Judge report hash"):
        cert.parse_donor_report_hash("Sealed precommit report SHA256:")
    with pytest.raises(ValueError, match="T257 Judge report hash"):
        cert.parse_donor_report_hash("Sealed precommit report SHA256:\n")
    with pytest.raises(ValueError, match="T257 Judge report hash"):
        cert.parse_donor_report_hash("Sealed precommit report SHA256: 0123456789abcdef")
    with pytest.raises(ValueError, match="T257 Judge report hash"):
        cert.parse_donor_report_hash("Sealed precommit report SHA256:\n0123456789abcdef")
    with pytest.raises(ValueError, match="T257 Judge report hash"):
        cert.parse_donor_report_hash("Sealed precommit report SHA256: " + "g" * 64)
    with pytest.raises(ValueError, match="T257 Judge report hash"):
        cert.parse_donor_report_hash("Sealed precommit report SHA256:\n" + "z" * 64)
    with pytest.raises(ValueError, match="T257 Judge report hash"):
        cert.parse_donor_report_hash("Random commit message without header")


def test_correct_t257_donor_is_accepted() -> None:
    donor = cert.verify_donor()
    assert donor["HEAD"] == cert.DONOR_HEAD
    assert donor["TREE"] == donor["JUDGED_TREE"] == cert.DONOR_TREE
    assert donor["RESULT_SHA256"] == cert.DONOR_SHA
    assert donor["TARGET_PROFILE"] == cert.T257_PROFILE
    assert donor["PROVEN_T_CAP"] == 257
    assert donor["FULL_PROFILE_BOUND"] == 313329096
    assert donor["FRESH_JUDGE"] == "VERIFIED_WITH_CAVEATS"
    expected_hash = "dd8cdc8ded41ecf93a8846aea1ae226979eb18d6c8a54f51c51b0e33066403e2"
    assert donor["JUDGE_REPORT_SHA256"] == expected_hash


def test_rejects_wrong_donor_tree_and_sha() -> None:
    with pytest.raises(ValueError, match="T257 donor tree"):
        cert.verify_donor(tree="0" * 40)
    with pytest.raises(ValueError, match="immutable blob SHA256"):
        cert.verify_donor(result_sha="0" * 64)


def test_frozen_profile_facts_and_goodman_split() -> None:
    value = cert.facts()
    assert (value["SUM_D"], value["CORE_VERTICES"], value["ZERO_VERTICES"]) == (66, 15, 5)
    assert (value["E"], value["W"], value["SUM_CHOOSE3_DEGREES"], value["GOODMAN"]) == (
        93,
        821,
        2265,
        287,
    )
    assert value["A_MAX"] == 193
    with pytest.raises(ValueError, match="profile/model"):
        cert.facts("66665555555321100000")


def test_each_remainder_component_is_nonnegative() -> None:
    assert cert.nonnegative_remainder((0, 0, 0, 0)) == 0
    for parts in ((-1, 0, 0, 0), (0, -1, 0, 0), (0, 0, -1, 0), (0, 0, 0, -1)):
        with pytest.raises(ValueError, match="P sign"):
            cert.nonnegative_remainder(parts)


def test_wrong_k4_allowance_and_unsupported_s5_are_rejected() -> None:
    with pytest.raises(ValueError, match="contained K4 allowance"):
        cert.integer_term(237, a_max=194)
    with pytest.raises(ValueError, match="S5 authority"):
        cert.integer_term(237, s5_authority={"S5": 7434})


@pytest.mark.parametrize("profile", ["66665555555321100000", "65555555555432100001", "bad"])
def test_rejects_wrong_profile(profile: str) -> None:
    with pytest.raises(ValueError, match="profile/model"):
        cert.facts(profile)


def test_rejects_source_hash_mismatch() -> None:
    with pytest.raises(ValueError, match="SHA256"):
        cert.immutable_blob(cert.DONOR_HEAD, cert.DONOR_RESULT, "0" * 64)


def test_rejects_duplicate_or_missing_family_rows(base: cert.Document) -> None:
    with pytest.raises(ValueError, match="duplicate profile update"):
        cert.replay(base, ((cert.PROFILE, 313122700), (cert.PROFILE, 313122700)))
    with pytest.raises(ValueError, match="missing profile row"):
        cert.replay(base, (("00000000000000000000", 1),))


def test_rejects_changed_cursor(base: cert.Document) -> None:
    changed = deepcopy(base)
    cursor = cert.obj(changed["CURSOR"])
    projection = cert.obj(cursor["COARSE_BOUND_PROJECTION"])
    key = next(iter(projection))
    projection[key] = cert.integer(projection[key]) + 1
    with pytest.raises(ValueError, match=r"Base result/source hash|changed cursor"):
        cert.replay(changed, ())


def test_canonical_sigma_and_degrees() -> None:
    sample_sigma = (0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    canonical = cert.canonical_sigma(sample_sigma)
    assert canonical == (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0)


@pytest.fixture(scope="module")
def domain() -> cert.Document:
    return cert.enumeration()


def test_statistics_units_and_independent_recount(domain: cert.Document) -> None:
    rows = cast(list[cert.Document], domain["STATES"])
    unique_sigma = {tuple(cast(list[int], row["SIGMA"])) for row in rows}
    independent = cert.obj(domain["INDEPENDENT_RECOUNT"])
    assert sum(1 for _ in cert.raw_sigma_classes()) == domain["RAW_CLASS_STATES"] == 3960
    assert len(rows) == domain["CORE_ZERO_DEGREE_MATCHINGS"] == 3517
    assert len(unique_sigma) == domain["RETAINED_CLASS_STATES"] == 1491
    assert sum(cert.orbit_size(sigma) for sigma in unique_sigma) == 154050
    assert domain["LABELLED_CORE_STATES"] == independent["LABELLED_CORE_STATES"] == 154050
    assert domain["LABELLED_CORE_ZERO_DEGREE_MATCHINGS"] == 292300
    assert independent["LABELLED_CORE_ZERO_DEGREE_MATCHINGS"] == 292300
    assert (
        domain["COMPATIBLE_CLASS_GRAPH_PAIRS"]
        == independent["COMPATIBLE_CLASS_GRAPH_PAIRS"]
        == 100834
    )
    assert (
        domain["LABELLED_CORE_GRAPH_PAIRS"] == independent["LABELLED_CORE_GRAPH_PAIRS"] == 6727928
    )
    assert independent["RAW_LABELLED_SIGMA_STATES"] == 368640
    assert independent["CORE_ZERO_DEGREE_MATCHINGS"] == 3517
    assert domain["INDEPENDENT_STATE_FIELDS_EQUAL"] is True


def test_raw_and_corrected_maxima_are_distinct(domain: cert.Document) -> None:
    expected_raw = {
        "10": 233,
        "12": 237,
        "14": 237,
        "16": 235,
        "18": 235,
        "20": 233,
        "22": 235,
        "24": 235,
    }
    expected_corrected = {
        "10": 233,
        "12": 236,
        "14": 235,
        "16": 232,
        "18": 231,
        "20": 226,
        "22": 224,
        "24": 222,
    }
    assert domain["R_CLASS_RAW_MAXIMA"] == expected_raw
    assert domain["R_CLASS_CORRECTED_MAXIMA"] == expected_corrected
    assert domain["UNIVERSAL_T_CAP"] == max(expected_raw.values()) == 237
    assert domain["CORRECTED_RELAXATION_CAP"] == max(expected_corrected.values()) == 236
    rows = cast(list[cert.Document], domain["STATES"])
    for row in rows:
        parts = cast(list[int], row["P_PARTS"])
        assert cert.integer(row["UPPER"]) == cert.integer(row["RAW"]) - cert.nonnegative_remainder(
            parts
        )
    assert any(
        cert.integer(row["RAW"]) == 237 and sum(cast(list[int], row["P_PARTS"])) > 0 for row in rows
    )


def test_rejects_invalid_cross_degree(domain: cert.Document) -> None:
    row = cast(list[cert.Document], domain["STATES"])[0]
    sigma = list(cast(list[int], row["SIGMA"]))
    sigma[0] = 1
    with pytest.raises(ValueError, match="sigma capacity"):
        cert.validate_state((tuple(sigma), tuple(cast(list[int], row["ZETA"]))))


@pytest.mark.parametrize("mutation", ["missing_state", "wrong_remainder", "wrong_maxima"])
def test_rejects_incomplete_or_mislabelled_domain(domain: cert.Document, mutation: str) -> None:
    corrupted = deepcopy(domain)
    rows = cast(list[cert.Document], corrupted["STATES"])
    if mutation == "missing_state":
        rows.pop()
    elif mutation == "wrong_remainder":
        cast(list[int], rows[0]["P_PARTS"])[0] = -1
    else:
        corrupted["R_CLASS_RAW_MAXIMA"] = corrupted["R_CLASS_CORRECTED_MAXIMA"]
    with pytest.raises(ValueError, match="incomplete/mutated finite domain"):
        cert.validate_enumeration(corrupted)


def test_rejects_missing_zero_graph() -> None:
    masks = cert.zero_masks_b()
    next(iter(masks.values())).pop()
    with pytest.raises(ValueError, match="1024-mask inventory"):
        cert.independent_labelled_recount(masks)


def test_complete_route_b_exact_arithmetic() -> None:
    for cap, count in ((267, 246), (237, 216)):
        terms = cert.envelope(cap)
        assert len(terms) == count
        assert [row[0] for row in terms] == list(range(22, cap + 1))
        assert terms == cert.fraction_terms(cap) == cert.integer_terms(cap)
    terms = cert.envelope(237)
    assert max(row[1] for row in terms) == 313122700
    assert [row[0] for row in terms if row[1] == 313122700] == [237]


def test_rejects_route_b_sign_and_incomplete_t_range() -> None:
    terms = [list(row) for row in cert.envelope(237)]
    s4, s3 = terms[-1][4], terms[-1][5]
    terms[-1][1] = cert.ceil_div(7 * (372228640 - 63838600 + s3) + 4 * s4, 7)
    with pytest.raises(ValueError, match="missing/incorrect Route-B term"):
        cert.validate_terms(237, terms)
    with pytest.raises(ValueError, match="missing/incorrect Route-B term"):
        cert.validate_terms(237, cert.envelope(237)[:-1])


def test_rejects_missing_or_duplicate_resolved_rows(base: cert.Document) -> None:
    corrupted = deepcopy(base)
    cert.obj(corrupted["RESOLVED_ROW_BOUNDS"]).pop(cert.PROFILE)
    with pytest.raises(ValueError, match="resolved row count"):
        cert.replay(corrupted, ())
    with pytest.raises(ValueError, match="duplicate JSON key"):
        cert.decode(b'{"RESOLVED_ROW_BOUNDS":{"x":1,"x":2}}')


def test_full_family_projection_is_memory_only(base: cert.Document) -> None:
    before = cert.render(base)
    result = cert.family_replay(base, 313329096, 313122700)
    assert cert.render(base) == before
    assert result["FINAL_FAMILY_BOUND"] == 313391172
    assert result["FINAL_OWNER_IDS"] == ["65555555555511111000"]
    assert result["OTHER_ROWS_UNCHANGED"] == 4645
    assert result["CURSOR_PROFILES"] == 197
    assert result["CURSOR_PRESERVED"] is True


def test_triangle_floor_formulas_on_all_five_vertex_graphs() -> None:
    edges = tuple(combinations(range(5), 2))
    for mask in range(1 << len(edges)):
        adjacent = [set[int]() for _ in range(5)]
        for bit, (u, v) in enumerate(edges):
            if mask & (1 << bit):
                adjacent[u].add(v)
                adjacent[v].add(u)
        degrees = tuple(map(len, adjacent))
        triangles = sum(
            v in adjacent[u] and z in adjacent[u] and z in adjacent[v]
            for u, v, z in combinations(range(5), 3)
        )
        assert cert.floors_a(degrees) == cert.floors_b(degrees)
        assert 0 <= max(cert.floors_a(degrees)) <= triangles


def test_exact_core_zero_triangle_partition() -> None:
    adjacent = [set[int]() for _ in range(20)]
    remaining = [(degree + 6, vertex) for vertex, degree in enumerate(cert.D)]
    while remaining:
        remaining.sort(reverse=True)
        degree, vertex = remaining.pop(0)
        assert 0 <= degree <= len(remaining)
        for index in range(degree):
            other_degree, other = remaining[index]
            assert other_degree > 0
            adjacent[vertex].add(other)
            adjacent[other].add(vertex)
            remaining[index] = (other_degree - 1, other)
    assert tuple(map(len, adjacent)) == tuple(value + 6 for value in cert.D)
    sigma = [len(adjacent[x] & set(range(15, 20))) for x in range(15)]
    zeta = [len(adjacent[u] & set(range(15))) for u in range(15, 20)]
    parts = [0, 0, 0, 0]
    triangles = 0
    for triple in combinations(range(20), 3):
        a, b, c = triple
        if b in adjacent[a] and c in adjacent[a] and c in adjacent[b]:
            triangles += 1
        core = [x for x in triple if x < 15]
        zero = [x for x in triple if x >= 15]
        if len(core) in (0, 3):
            if b not in adjacent[a] and c not in adjacent[a] and c not in adjacent[b]:
                parts[0 if core else 1] += 1
        elif len(core) == 2:
            x, y = core
            u = zero[0]
            if y not in adjacent[x] and u in adjacent[x] and u in adjacent[y]:
                parts[2] += 1
        else:
            u, v = zero
            x = core[0]
            if v not in adjacent[u] and x in adjacent[u] and x in adjacent[v]:
                parts[3] += 1
    raw = 227 + sum(s * (s - d - 4) for s, d in zip(sigma, cert.CORE, strict=True))
    raw += sum(z * z for z in zeta)
    assert triangles == raw - cert.nonnegative_remainder(parts)
