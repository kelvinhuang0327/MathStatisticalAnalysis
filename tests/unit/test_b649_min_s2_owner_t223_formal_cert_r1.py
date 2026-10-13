"""Focused mathematical, identity, rounding and tamper gates for the T223 owner."""

from __future__ import annotations

import copy
import os
import subprocess
import sys
from fractions import Fraction
from itertools import combinations, product
from math import comb
from typing import cast

import pytest

from lottolab.research import b649_min_s2_owner_t223_formal_cert_r1 as m


@pytest.fixture(scope="module")
def authority() -> m.Document:
    return m.load_authority()


@pytest.fixture(scope="module")
def certificate(authority: m.Document) -> m.Document:
    return m.compute_result(authority)


def graph_fixture(mixed: bool = False) -> set[tuple[int, int]]:
    # Two explicit graph-only fixtures; neither is claimed to have a support decomposition.
    if mixed:
        core_h = {
            (0, 12),
            (1, 12),
            (2, 3),
            (2, 11),
            (2, 13),
            (3, 11),
            (3, 13),
            (4, 5),
            (4, 6),
            (4, 13),
            (5, 6),
            (5, 13),
            (6, 13),
            (7, 8),
            (7, 9),
            (7, 13),
            (8, 9),
            (8, 10),
            (9, 10),
            (10, 11),
            (10, 12),
            (10, 13),
            (11, 12),
            (11, 13),
            (12, 13),
        }
        zero_h = {(14, 15), (14, 16), (15, 16), (17, 18), (17, 19), (18, 19)}
        cross = {
            (2, 18),
            (3, 19),
            (4, 14),
            (5, 15),
            (6, 16),
            (7, 17),
            (8, 18),
            (9, 19),
            (10, 18),
            (10, 19),
            (11, 14),
            (11, 15),
            (12, 16),
            (12, 17),
            (13, 14),
            (13, 15),
            (13, 16),
            (13, 17),
        }
    else:
        core_h = {
            (0, 1),
            (2, 3),
            (2, 13),
            (3, 13),
            (4, 5),
            (4, 13),
            (5, 13),
            (6, 7),
            (6, 13),
            (7, 13),
            (8, 9),
            (8, 12),
            (9, 12),
            (10, 11),
            (10, 12),
            (10, 13),
            (11, 12),
            (11, 13),
            (12, 13),
        }
        zero_h: set[tuple[int, int]] = set()
        cross = {(12, 14), (12, 15), (13, 16), (13, 17), (13, 18), (13, 19)}
    return (
        (set(combinations(range(14), 2)) - core_h)
        | (set(combinations(range(14, 20), 2)) - zero_h)
        | cross
    )


def direct_triangles(vertices: tuple[int, ...], edges: set[tuple[int, int]]) -> int:
    return sum(
        (a, b) in edges and (a, c) in edges and (b, c) in edges
        for a, b, c in combinations(vertices, 3)
    )


def test_immutable_base_and_source_identity(authority: m.Document) -> None:
    assert m.git("rev-parse", f"{m.BASE_HEAD}^{{tree}}").decode().strip() == m.BASE_TREE
    assert m.sha(m.git("ls-tree", "-rz", m.BASE_HEAD)) == m.BASE_LS_TREE_SHA256
    assert authority["BASE_TREE_ENTRY_COUNT"] == 2239
    assert m.sha(m.render(authority["BASE_DOCUMENT"])) == m.BASE_RESULT_SHA256
    pins = m.obj(authority["SOURCE_PINS"])
    assert len(pins) == 27 and pins[m.SPLIT_SOURCE] == m.SPLIT_SHA256
    assert (
        m.obj(authority["R30_CAP_RECORD_VERBATIM"])["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == 266
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("TICKETS", 19),
        ("LABELS_PER_TICKET", 5),
        ("TRIPLES", 21),
        ("PAIRS", 28),
        ("PAIR_LINEARITY", False),
        ("TICKETS", 20.0),
        ("PAIR_LINEARITY", 1),
    ],
)
def test_weakened_model_rejected(field: str, value: object) -> None:
    model = {**m.MODEL, field: value}
    with pytest.raises(ValueError, match="support model"):
        m.model_facts(model=model)


def test_wrong_profile_rejected() -> None:
    with pytest.raises(ValueError, match="target profile"):
        m.model_facts("66555555555333000000")


def test_exact_model_algebra() -> None:
    facts = m.model_facts()
    assert (facts["G_EDGES"], facts["H_EDGES"], facts["PHI"]) == (93, 97, 291)
    assert (facts["WEDGES"], facts["THIRD_DEGREES"], facts["CONTAINED_K4_CAP"]) == (825, 2296, 196)
    assert comb(20, 3) - 18 * 97 + sum(comb(13 - d, 2) for d in m.D) == 291


@pytest.mark.parametrize("mixed", [False, True])
def test_split_identity_and_nonnegative_remainder(mixed: bool) -> None:
    edges = graph_fixture(mixed)
    observed = m.audit_graph(edges)
    all_vertices = tuple(range(20))
    h = set(combinations(all_vertices, 2)) - edges
    assert observed["T"] == direct_triangles(all_vertices, edges)
    assert observed["T"] == 291 - direct_triangles(all_vertices, h)
    assert observed["T"] == m.integer(observed["F"]) - m.integer(observed["P"])
    assert observed["SUPPORT_REALIZATION"] == "NOT_ASSERTED"
    if mixed:
        assert observed["P_TERMS"] == [14, 2, 10, 5]
        assert (observed["T"], observed["F"], observed["P"]) == (152, 183, 31)
    else:
        assert (observed["T"], observed["F"], observed["P"]) == (215, 223, 8)


def test_vertex_relabeling_preserves_coverage_and_identity() -> None:
    edges = graph_fixture(True)
    # Reverse each equal-degree core class; also permute all zeros independently.
    permutation = (1, 0, *range(9, 1, -1), 12, 11, 10, 13, 19, 18, 17, 16, 15, 14)
    relabelled = {
        (min(permutation[x], permutation[y]), max(permutation[x], permutation[y])) for x, y in edges
    }
    assert m.audit_graph(relabelled) == m.audit_graph(edges)
    # Moving a core vertex into Z changes its position but not the profile multiset.
    permutation2 = list(range(20))
    permutation2[0], permutation2[19] = 19, 0
    relabelled2 = {
        (min(permutation2[x], permutation2[y]), max(permutation2[x], permutation2[y]))
        for x, y in edges
    }
    d = [0] * 20
    for i, v in enumerate(m.D):
        d[permutation2[i]] = v
    assert m.audit_graph(relabelled2, tuple(d)) == m.audit_graph(edges)


def test_invalid_graph_and_pair_linear_supports_rejected() -> None:
    with pytest.raises(ValueError, match="simple canonical"):
        m.audit_graph(graph_fixture() | {(0, 0)})
    bad = graph_fixture()
    bad.remove((0, 2))
    with pytest.raises(ValueError, match="G degrees"):
        m.audit_graph(bad)
    triples, pairs = m.split.witness_supports("TOP")
    with pytest.raises(ValueError, match="wrong graph profile"):
        m.audit_supports(triples, pairs)
    with pytest.raises(ValueError):
        m.audit_supports((*triples[:-1], triples[0]), pairs)
    with pytest.raises(ValueError, match="distinct"):
        m.audit_supports(triples, (*pairs[:-1], pairs[0]))
    with pytest.raises(ValueError, match="reuse"):
        m.audit_supports(triples, (*pairs[:-1], triples[0][:2]))
    with pytest.raises(ValueError, match="22 triple"):
        m.audit_supports(triples[:-1], pairs)


def test_complete_domain_and_independent_maximum(certificate: m.Document) -> None:
    core, zero = m.primary_domains()
    assert (core, zero) == m.independent_domains()
    assert len(core) == len(set(core)) == 450
    assert len(zero) == len(set(zero)) == 462
    assert len(core) * len(zero) == 207900
    assert sum(sum(s) == sum(z) for s, z in product(core, zero)) == 2420
    enumeration = m.obj(certificate["ENUMERATION"])
    states = m.items(enumeration["STATES"])
    assert len(states) == 498
    # This is the independent polynomial evaluation, not the production objective call.
    values: list[int] = []
    for raw in states:
        row = m.obj(raw)
        s = tuple(m.integer(v) for v in m.items(row["SIGMA"]))
        z = tuple(m.integer(v) for v in m.items(row["ZETA"]))
        assert m.independently_necessary(s, z)
        value = 237 + sum(x * x + 3 * x - d * x for x, d in zip(s, m.D[:14], strict=True))
        value += sum(x * x - 7 * x for x in z)
        assert value == row["F"]
        values.append(value)
    assert max(values) == enumeration["MAX_F"] == certificate["NEW_PROVEN_T_CAP"] == 223
    assert (
        enumeration["LEGAL_SUPPORT_ATTAINMENT"]
        == certificate["LEGAL_SUPPORT_T223_ATTAINMENT"]
        == "UNKNOWN"
    )


def test_independent_state_set_covers_exact_pinned_necessary_states(
    certificate: m.Document,
) -> None:
    rows = m.items(m.obj(certificate["ENUMERATION"])["STATES"])
    pinned = [(c.sigma, c.zeta, c.f) for c in m.split.degree_configurations(m.D)]
    actual = [
        (
            tuple(m.integer(v) for v in m.items(m.obj(r)["SIGMA"])),
            tuple(m.integer(v) for v in m.items(m.obj(r)["ZETA"])),
            m.integer(m.obj(r)["F"]),
        )
        for r in rows
    ]
    assert actual == pinned


def test_missing_domain_and_wrong_objective_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = m.primary_domains
    core, zero = original()
    monkeypatch.setattr(m, "primary_domains", lambda: (core[:-1], zero))
    with pytest.raises(ValueError, match="canonical domain"):
        m.enumerate_certificate()
    monkeypatch.setattr(m, "primary_domains", original)
    original_f = m.split_f

    def wrong_f(s: m.Degrees, z: m.Degrees) -> int:
        return original_f(s, z) + 1

    monkeypatch.setattr(m, "split_f", wrong_f)
    with pytest.raises(ValueError, match="formula disagrees"):
        m.enumerate_certificate()


def test_missing_necessary_state_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = m.independently_necessary
    maximum_s = (0,) * 12 + (2, 4)

    def omit_maximum(s: m.Degrees, z: m.Degrees) -> bool:
        return s != maximum_s and original(s, z)

    monkeypatch.setattr(m, "independently_necessary", omit_maximum)
    with pytest.raises(ValueError, match="state verification differs"):
        m.enumerate_certificate()


@pytest.mark.parametrize(
    "sigma,zeta",
    [
        ((1,) + (0,) * 11 + (2, 4), (2, 1, 1, 1, 1, 1)),
        ((0,) * 12 + (3, 3), (1,) * 6),
        ((0,) * 12 + (2, 4), (0, 1, 1, 1, 1, 2)),
        ((0,) * 12 + (2, 4), (1, 1, 1, 1, 1, 2)),
        ((0,) * 12 + (2, 4), (1.0,) * 6),
    ],
)
def test_cross_degree_capacity_and_total_rejections(
    sigma: tuple[int, ...], zeta: tuple[int, ...]
) -> None:
    with pytest.raises(ValueError):
        m.split_f(sigma, zeta)


def test_graphical_and_gale_ryser_obstructions() -> None:
    assert not m.havel_hakimi((3, 3, 1, 1))
    assert not m.havel_hakimi((1, 1, 1))
    assert not m.havel_hakimi((-1, 0))
    assert m.havel_hakimi((2, 2, 2))
    assert not m.split.bipartite_graphical((3, 3, 0), (3, 3, 0))
    # Find a genuinely rejected equal-total state in the actual complete domain.
    core, zero = m.primary_domains()
    rejected = [
        (s, z)
        for s, z in product(core, zero)
        if sum(s) == sum(z) and not m.independently_necessary(s, z)
    ]
    assert len(rejected) == 2420 - 498
    for s, z in rejected:
        with pytest.raises(ValueError):
            m.split.configuration(m.D, s, z)


def test_all_route_b_terms_exact_rounding(certificate: m.Document) -> None:
    terms = m.items(certificate["ROUTE_B_TERMS"])
    assert len(terms) == 202
    assert [m.items(row)[0] for row in terms] == list(range(22, 224))
    for raw in terms:
        t, bound, q, c, s4, s3 = (m.integer(v) for v in m.items(raw))
        q_rational = Fraction(30 * t - 5954, 4)
        expected_q = max(0, -(-q_rational.numerator // q_rational.denominator))
        assert q == expected_q and c == min(q, 196)
        assert s4 == max(112, 448 * c + 679 * (q - c))
        value = Fraction(308390040 + 2279200 + 11872 * (t - 22)) - Fraction(4 * s4, 7)
        assert bound - 1 < value <= bound
        assert bound == -(-value.numerator // value.denominator)
        assert s3 == 2279200 + 11872 * (t - 22)
    assert m.items(terms[-1]) == [223, 313008408, 184, 184, 82432, 4665472]
    assert max(m.integer(m.items(row)[1]) for row in terms) == 313008408
    assert certificate["ENVELOPE_MAX_T"] == [223]
    assert certificate["PROFILE_BOUND_DELTA"] == 386756
    assert certificate["MARGIN_BELOW_INCUMBENT"] == 255480
    assert certificate["STRICT_GAIN_EXCLUDED"] == "YES"
    # Old cap crosses q=196; verify the heavier K4 branch as well.
    old = m.route_terms(266)
    assert old[-1][2] > 196 and old[-1][4] == 448 * 196 + 679 * (old[-1][2] - 196)


@pytest.mark.parametrize("cap", [21, 267, 223.0, True])
def test_route_domain_rejected(cap: int) -> None:
    with pytest.raises(ValueError, match="cap domain"):
        m.route_terms(cap)


def test_exact_single_row_family_and_cursor(authority: m.Document, certificate: m.Document) -> None:
    base = m.obj(authority["BASE_DOCUMENT"])
    before = m.obj(base["RESOLVED_ROW_BOUNDS"])
    after = m.obj(certificate["RESOLVED_ROW_BOUNDS"])
    assert len(before) == len(after) == 4647 and before.keys() == after.keys()
    assert [p for p in before if before[p] != after[p]] == [m.TARGET]
    assert after[m.TARGET] == 313008408
    assert certificate["CURSOR"] == base["CURSOR"]
    assert m.render(certificate["CURSOR"]) == m.render(base["CURSOR"])
    assert certificate["CURSOR_PROFILE_COUNT"] == 197 and certificate["CURSOR_BOUND"] == 313394584
    assert certificate["FAMILY_BOUND_BEFORE"] == certificate["FAMILY_BOUND_AFTER"] == 313395164
    assert certificate["FAMILY_DELTA"] == 0
    assert certificate["FAMILY_OWNER_IDS"] == ["65555555555532000000", "66555555555333000000"]
    assert certificate["GAP_TO_INCUMBENT"] == 131276
    assert certificate["STILL_OPEN_PROFILE_COUNT"] == 1566


@pytest.mark.parametrize("kind", ["missing", "duplicate", "other", "float"])
def test_ledger_input_tamper_rejected(authority: m.Document, kind: str) -> None:
    base = m.obj(authority["BASE_DOCUMENT"])
    frozen, cursor = m.replay_base(base)
    rows = list(frozen.items())
    if kind == "missing":
        rows.pop()
    elif kind == "duplicate":
        rows.append(rows[0])
    elif kind == "other":
        p, v = rows[0]
        rows[0] = (p, v - 1)
    else:
        p, v = rows[0]
        rows = cast(list[tuple[str, int]], [(p, float(v)), *rows[1:]])
    with pytest.raises(ValueError, match="ledger row"):
        m.compose(base, rows, cursor, [(m.TARGET, 313008408)])


@pytest.mark.parametrize(
    "updates",
    [
        [],
        [(m.TARGET, 313008408)] * 2,
        [("65555555555532000000", 313008408)],
        [(m.TARGET, 313008409)],
        [(m.TARGET, 313008408.0)],
    ],
)
def test_update_tamper_rejected(authority: m.Document, updates: list[tuple[str, int]]) -> None:
    base = m.obj(authority["BASE_DOCUMENT"])
    rows, cursor = m.replay_base(base)
    with pytest.raises(ValueError, match="single update"):
        m.compose(base, list(rows.items()), cursor, updates)


@pytest.mark.parametrize("kind", ["bound", "id", "member", "projection", "partition", "status"])
def test_entire_cursor_tamper_rejected(authority: m.Document, kind: str) -> None:
    base = m.obj(authority["BASE_DOCUMENT"])
    rows, original = m.replay_base(base)
    cursor = copy.deepcopy(original)
    if kind == "bound":
        cursor["BOUND"] = m.integer(cursor["BOUND"]) - 1
    elif kind == "id":
        cursor["ID"] = m.TARGET
    elif kind == "member":
        m.items(cursor["PROFILE_IDS"]).pop()
    elif kind == "projection":
        projection = m.obj(cursor["COARSE_BOUND_PROJECTION"])
        p = next(iter(projection))
        projection[p] = m.integer(projection[p]) - 1
    elif kind == "partition":
        cursor["PARTITION"] = {}
    else:
        cursor["STATUS"] = "RESOLVED"
    with pytest.raises(ValueError, match="cursor modification"):
        m.compose(base, list(rows.items()), cursor, [(m.TARGET, 313008408)])


def test_inherited_caveats_and_original_status_verbatim(
    authority: m.Document, certificate: m.Document
) -> None:
    base = m.obj(authority["BASE_DOCUMENT"])
    assert m.render(certificate["INHERITED_BASE_RESULT_VERBATIM"]) == m.render(base)
    caveat = m.obj(certificate["OWNER_A_HISTORICAL_REPORT_DIGEST_CAVEAT"])
    accepted_a = m.obj(m.obj(m.obj(base["PROVENANCE"])["A"])["ACCEPTANCE"])
    assert caveat["DECLARED_SHA256"] == accepted_a["REPORT_DECLARED_SHA256"]
    assert caveat["COMMITTED_MARKER_TEXT_SHA256"] == accepted_a["REPORT_COMMITTED_TEXT_SHA256"]
    assert caveat["DECLARED_SHA256"] != caveat["COMMITTED_MARKER_TEXT_SHA256"]
    assert caveat["REPAIR_CLAIM"] == "NONE; inherited discrepancy preserved"
    assert certificate["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert all(v == "NOT_VERIFIED" for v in m.obj(certificate["G01_TO_G18_AT_SEAL"]).values())


@pytest.mark.parametrize("kind", ["cap", "term", "state", "row", "cursor", "caveat"])
def test_sealed_result_tamper_rejected(certificate: m.Document, kind: str) -> None:
    changed = copy.deepcopy(certificate)
    if kind == "cap":
        changed["NEW_PROVEN_T_CAP"] = 224
    elif kind == "term":
        m.items(m.items(changed["ROUTE_B_TERMS"])[-1])[1] = 313008407
    elif kind == "state":
        m.items(m.obj(changed["ENUMERATION"])["STATES"]).pop()
    elif kind == "row":
        rows = m.obj(changed["RESOLVED_ROW_BOUNDS"])
        p = next(p for p in rows if p != m.TARGET)
        rows[p] = m.integer(rows[p]) - 1
    elif kind == "cursor":
        m.obj(changed["CURSOR"])["BOUND"] = 0
    else:
        changed["OWNER_A_HISTORICAL_REPORT_DIGEST_CAVEAT"] = {}
    with pytest.raises(ValueError, match="exact replay"):
        m.verify_result(changed)


def test_immutable_source_and_base_negative_seams(monkeypatch: pytest.MonkeyPatch) -> None:
    original = m.git

    def wrong_tree(*args: str) -> bytes:
        if args[0] == "rev-parse":
            return b"0000000000000000000000000000000000000000\n"
        return original(*args)

    monkeypatch.setattr(m, "git", wrong_tree)
    with pytest.raises(ValueError, match="Base tree"):
        m.load_authority()
    monkeypatch.setattr(m, "git", original)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        m.inherited.checked_blob(m.BASE_HEAD, m.SPLIT_SOURCE, "0" * 64)
    with pytest.raises(ValueError, match="duplicate JSON key"):
        m.inherited.decode(b'{"BOUND":1,"BOUND":2}')


def test_current_seal_and_real_cli(certificate: m.Document) -> None:
    path = m.ROOT / m.RESULT
    assert path.read_bytes() == m.render(certificate)
    env = {**os.environ, "PYTHONPATH": str(m.ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    process = subprocess.run(
        [sys.executable, "-B", "-m", m.__name__, "--verify"],
        cwd=m.ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert '"STATUS": "PASS"' in process.stdout
    assert '"PROFILE_BOUND": 313008408' in process.stdout
    assert '"FAMILY_BOUND": 313395164' in process.stdout


def test_write_refuses_to_overwrite_existing_seal() -> None:
    with pytest.raises(ValueError, match="refuse to overwrite"):
        m.main(["--write"])
