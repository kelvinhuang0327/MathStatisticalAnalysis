"""Focused tests for the CELL_A overlap-rigidity certificate.

Nothing is solved and nothing is scored: CP-SAT's Solve, the census solve entry point and both
exact evaluators are replaced for this module by guards that fail any test calling them. The
frozen CELL_A model is built once, its pin checked, and its constraints compared with the four
families the proof uses. The incumbent and its T = 255 pair-switches (the two-cell suite's
``t255_classes`` rule) are recounted by the census's own realization code. Every labelled graph
on at most six vertices checks the general counts of steps B, C and E against a brute-force count.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from collections.abc import Iterator
from importlib import import_module
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_cell_a_overlap_rigidity_certificate as cert
from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_two_open_cells_targeted_solver as engine

ROOT = Path(__file__).resolve().parents[2]
PROFILE = cert.decode_profile(cert.PROFILE_ID)
SEQUENCE = cert.overlap_degrees(PROFILE)
H = frozenset(range(12))
U = frozenset(range(12, 20))
CEILING = 6
CERTIFICATE_SHA256 = "db91bb0689e978de16e33776fe975515c899c31396107b5908daed35d07d6c96"
INT64_MIN, INT64_MAX = -(2**63), 2**63 - 1

Pair = tuple[int, int]


def _pair(a: int, b: int) -> Pair:
    return (a, b) if a < b else (b, a)


@pytest.fixture(scope="module", autouse=True)
def no_solve_and_no_scoring() -> Iterator[None]:
    """Any CP-SAT solve or exact evaluation fails the test that makes it."""

    def refuse(*_: object, **__: object) -> NoReturn:
        raise AssertionError("a solve or exact-scoring call was made")

    cp_model: Any = import_module("ortools.sat.python.cp_model")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cp_model.CpSolver, "Solve", refuse)
        patch.setattr(cp_model.CpSolver, "solve", refuse)
        patch.setattr(census, "cp_sat_solve", refuse)
        patch.setattr(census, "official_evaluator", refuse)
        patch.setattr(engine, "exact_evaluator", refuse)
        yield


@pytest.fixture(scope="module")
def incumbent() -> census.Structure:
    tickets, _ = census.start_portfolio(ROOT)
    profile, structure = census.structure_from_tickets(tickets)
    assert profile == PROFILE
    return structure


@pytest.fixture(scope="module")
def t255_switches(incumbent: census.Structure) -> list[census.Structure]:
    """The incumbent's pair-switches at T = 255, by the two-cell suite's ``t255_classes`` rule,
    kept per labelled structure instead of per isomorphism class."""

    found: list[census.Structure] = []
    pairs = incumbent.pairs
    for (i, (a, b)), (j, (c, d)) in combinations(enumerate(pairs), 2):
        for new in (((a, c), (b, d)), ((a, d), (b, c))):
            switched = tuple(cast(census.Pair, tuple(sorted(e))) for e in new)
            rest = [p for k, p in enumerate(pairs) if k not in (i, j)]
            candidate = census.Structure(incumbent.triples, tuple(sorted([*rest, *switched])))
            try:
                if census.realization(PROFILE, candidate).triangles == 255:
                    found.append(candidate)
            except census.CensusError:
                continue
    assert found
    return found


@pytest.fixture(scope="module")
def frozen_model() -> Any:
    return census.support_model((PROFILE,), CEILING)[0]


def _graph(structure: census.Structure) -> cert.Graph:
    return cert.structure_graph(PROFILE, structure.triples, structure.pairs)


# Pins and the frozen model -----------------------------------------------------------------


def _blob(commit: str, module: Any) -> bytes:
    path = Path(module.__file__).resolve().relative_to(ROOT).as_posix()
    command = ["git", "-C", str(ROOT), "show", f"{commit}:{path}"]
    return subprocess.run(command, check=True, capture_output=True).stdout


def test_cell_a_target_and_pins_match_the_frozen_engine() -> None:
    references = cert.FROZEN_REFERENCES
    assert (engine.CELL_A.profile_id, engine.CELL_A.t) == (cert.PROFILE_ID, cert.TARGET_T)
    assert engine.SEARCH_CELLS == (engine.CELL_A,)
    assert engine.CELL_A.ceiling == census.wedge_count(PROFILE) - 3 * cert.TARGET_T == CEILING
    assert engine.engine_sha256() == references["TWO_CELL_ENGINE_SHA256"]
    assert census.engine_sha256() == references["CENSUS_ENGINE_SHA256"]
    assert engine.MODEL_PROTO_SHA256["CELL_A"] == references["CELL_A_MODEL_PROTO_SHA256"]
    base = references["BASE_COMMIT"]
    assert census.sha256_bytes(_blob(base, engine)) == references["TWO_CELL_ENGINE_SHA256"]
    assert census.sha256_bytes(_blob(base, census)) == references["CENSUS_ENGINE_SHA256"]
    assert census.decode_profile(cert.PROFILE_ID) == PROFILE
    assert SEQUENCE == (11,) * 12 + (7,) * 6 + (6,) * 2


def _linear_form(terms: dict[int, int], lo: int, hi: int) -> tuple[object, ...]:
    """A linear constraint up to term order and an overall sign; int64 ends mean unbounded."""

    low = None if lo == INT64_MIN else lo
    high = None if hi == INT64_MAX else hi
    items = tuple(sorted((v, k) for v, k in terms.items() if k))
    if items and items[0][1] < 0:
        items = tuple((v, -k) for v, k in items)
        low, high = (None if high is None else -high), (None if low is None else -low)
    return items, low, high


def _missing_premises(model: Any, ceiling: int) -> list[tuple[object, ...]]:
    """The proof's constraint forms that ``model`` lacks; every variable must be a d, t, b, e
    or o variable, d fixed to CELL_A's profile and the rest 0/1."""

    proto = model.Proto()
    names = [variable.name for variable in proto.variables]
    domains = [tuple(variable.domain) for variable in proto.variables]
    index = {name: i for i, name in enumerate(names)}
    assert len(index) == len(names)
    for v, d in enumerate(PROFILE):
        assert domains[index[f"d{v}"]] == (d, d)
    assert all(domains[i] == (0, 1) for i, name in enumerate(names) if name[0] != "d")
    active = [v for v, d in enumerate(PROFILE) if d]
    t = {line: index[f"t{line}"] for line in combinations(active, 3)}
    b = {p: index[f"b{p}"] for p in combinations(range(20), 2)}
    e = {p: index[f"e{p}"] for p in combinations(range(20), 2)}
    o = {
        (c, x, y): index[f"o{c}_{x}_{y}"]
        for c in range(20)
        for x, y in combinations([v for v in range(20) if v != c], 2)
    }
    assert len(names) == 20 + len(t) + len(b) + len(e) + len(o)
    assert (len(t), len(o)) == (comb(18, 3), 20 * comb(19, 2))

    helper: Any = import_module("ortools.sat.python.cp_model_helper")
    kinds = [name for name in dir(helper.ConstraintProto) if name.startswith("has_")]
    present = Counter[tuple[object, ...]]()
    for constraint in proto.constraints:
        flags = [kind for kind in kinds if getattr(constraint, kind)()]
        if flags == ["has_linear"] and not len(constraint.enforcement_literal):
            linear = constraint.linear
            domain = list(linear.domain)
            assert len(domain) == 2
            terms = dict(zip(linear.vars, linear.coeffs, strict=True))
            present[_linear_form(terms, domain[0], domain[1])] += 1

    expected: list[tuple[object, ...]] = []
    for v in range(20):
        on_triples = {t[line]: 1 for line in t if v in line}
        expected.append(_linear_form({**on_triples, index[f"d{v}"]: -1}, 0, 0))
        on_pairs = {b[p]: 1 for p in b if v in p}
        expected.append(_linear_form({**on_pairs, index[f"d{v}"]: 1}, 6, 6))
    for p in b:
        covering = {t[line]: 1 for line in t if set(p) <= set(line)}
        expected.append(_linear_form({**covering, b[p]: 1}, INT64_MIN, 1))
        uncovered = {x: -1 for x in covering}
        expected.append(_linear_form({e[p]: 1, **uncovered, b[p]: -1}, 0, 0))
    for (c, x, y), wedge in o.items():
        terms = {wedge: 1, e[_pair(c, x)]: -1, e[_pair(c, y)]: -1, e[(x, y)]: 1}
        expected.append(_linear_form(terms, -1, INT64_MAX))
    expected.append(_linear_form(dict.fromkeys(o.values(), 1), INT64_MIN, ceiling))
    assert len(expected) == len(set(expected)) == 20 + 20 + 190 + 190 + 3420 + 1
    return [form for form in expected if not present[form]]


def test_frozen_cell_a_model_contains_every_constraint_the_proof_uses(frozen_model: Any) -> None:
    """A solution of the pinned model is a fiber structure whose open wedges each force their own
    indicator to 1, under a sum of at most 6. Extra model rows only remove solutions."""

    pin = cert.FROZEN_REFERENCES["CELL_A_MODEL_PROTO_SHA256"]
    assert census.sha256_bytes(str(frozen_model.Proto()).encode()) == pin
    assert _missing_premises(frozen_model, CEILING) == []


def test_a_model_one_target_lower_does_not_give_the_ceiling_of_six() -> None:
    """At T = 269 the same rows bound the indicators by 9, not 6, and the proof stops at F."""

    lower = census.support_model((PROFILE,), census.wedge_count(PROFILE) - 3 * 269)[0]
    missing = _missing_premises(lower, CEILING)
    assert len(missing) == 1 and missing[0][2] == CEILING
    assert _missing_premises(lower, 9) == []
    with pytest.raises(cert.CertificateError, match="step F: m = 4 leaves 2 non-edges"):
        cert.derive(SEQUENCE, 9)


def test_indicators_bound_open_wedges_from_above_only(incumbent: census.Structure) -> None:
    """o >= e(c,a) + e(c,b) - e(a,b) - 1 forces o = 1 exactly on open wedges and leaves every
    other indicator free, so the ceiling bounds O and the proof never uses sum o = O."""

    graph = _graph(incumbent)
    forced = free = 0
    for c in range(20):
        for a, b in combinations([v for v in range(20) if v != c], 2):
            ca, cb, ab = (int(y in graph[x]) for x, y in ((c, a), (c, b), (a, b)))
            low = ca + cb - ab - 1
            assert (low == 1) == (ca == cb == 1 and not ab)
            forced += low == 1
            free += low <= 0
    assert forced == len(cert.open_wedges(graph)) == 6
    assert free == 20 * comb(19, 2) - 6


# The certificate and the incumbent ---------------------------------------------------------


def test_certificate_fixes_the_overlap_graph_of_cell_a() -> None:
    record = cert.certificate()
    assert record["CERTIFICATE_SHA256"] == CERTIFICATE_SHA256
    assert record["VERDICT"] == cert.RIGID
    assert record["DEGREE_SEQUENCE"] == "11^12 7^6 6^2"
    assert (record["W"], record["OPEN_WEDGE_CEILING"]) == (816, 6)
    assert (record["H_SIZE"], record["CROSS_DEGREE_GAP"], record["CROSS_EDGE_BOUND"]) == (12, 4, 3)
    assert record["CROSS_EDGE_CANDIDATES"] == [0, 2]
    assert record["REFUTED_CROSS_EDGES"] == {"2": 10}
    assert (record["TRIANGLES"], record["OPEN_WEDGES"]) == (270, 6)
    assert record["MAX_TRIANGLES_FOR_DEGREE_SEQUENCE"] == 270
    assert (record["F2_MATCHING_EDGES"], record["F3_TRIPLES_IN_H"]) == (6, 20)
    assert (record["STS_POINTS"], record["STS_BLOCKS"]) == (13, 26)
    assert record["SOLVER_USED"] is False
    not_claimed = cast(dict[str, str], record["NOT_CLAIMED"])
    assert not_claimed["CELL_A_SCORE_CLOSURE"] == "NOT_CLAIMED"
    assert not_claimed["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
    cert.verify_certificate(record)


def test_the_incumbent_realizes_the_rigid_graph_and_a_pointed_sts13(
    incumbent: census.Structure,
) -> None:
    ledger = cert.structure_ledger(incumbent.triples, incumbent.pairs)
    assert (ledger.wedges, ledger.triangles, ledger.open_wedges) == (816, 270, 6)
    assert (ledger.cross_edges, ledger.missing_pair) == (0, (18, 19))
    assert (len(ledger.matching), len(ledger.triples), ledger.blocks) == (6, 20, 26)
    realization = census.realization(PROFILE, incumbent)
    assert (realization.triangles, realization.open_wedges) == (270, 6)
    k8_minus_edge = [p for p in combinations(sorted(U), 2) if p != (18, 19)]
    rigid = cert.simple_graph(20, [*combinations(sorted(H), 2), *k8_minus_edge])
    assert _graph(incumbent) == rigid
    # C is tight here: the 12 edges between degree 7 and degree 6 each add 1, and 2O = 12.
    assert ledger.degree_gap_sum == 2 * ledger.open_wedges == 12


@pytest.mark.parametrize("n", range(1, 7))
def test_every_small_graph_satisfies_the_counting_identities(n: int) -> None:
    """B: O = W - 3T. C: sum |deg u - deg v| <= 2O. E: sum_H deg = 2 e(H) + m. Each against a
    brute-force count over all labelled graphs on n vertices."""

    pairs = list(combinations(range(n), 2))
    tight = 0
    for mask in range(1 << len(pairs)):
        edges = {p for k, p in enumerate(pairs) if mask >> k & 1}
        graph = cert.simple_graph(n, edges)
        degree = [sum(v in p for p in edges) for v in range(n)]
        opened = sum(
            _pair(c, a) in edges and _pair(c, b) in edges and (a, b) not in edges
            for c in range(n)
            for a, b in pairs
            if c not in (a, b)
        )
        triangles = sum({(a, b), (a, c), (b, c)} <= edges for a, b, c in combinations(range(n), 3))
        wedges = sum(comb(d, 2) for d in degree)
        gaps = sum(abs(degree[a] - degree[b]) for a, b in edges)
        ledger = cert.graph_ledger(graph)
        assert (ledger.wedges, ledger.triangles, ledger.open_wedges) == (wedges, triangles, opened)
        assert opened == wedges - 3 * triangles
        assert ledger.degree_gap_sum == gaps <= 2 * opened
        tight += gaps == 2 * opened > 0
        top = frozenset(v for v in range(n) if degree[v] == max(degree))
        inside, cross = cert.split_edges(graph, top)
        assert inside == sum(set(p) <= top for p in edges)
        assert cross == sum(len(set(p) & top) == 1 for p in edges)
        assert 2 * inside + cross == sum(degree[v] for v in top)
    assert tight or n < 3


# One semantic negative per load-bearing step -----------------------------------------------


def test_the_degree_gap_bound_cannot_be_halved() -> None:
    """C's factor 2 is needed: the incumbent itself and a three-leaf star reach 2O exactly. With
    it, D only gives m <= 3, so E and F carry the proof."""

    star = cert.graph_ledger(cert.simple_graph(4, [(0, 1), (0, 2), (0, 3)]))
    assert star.degree_gap_sum == 2 * star.open_wedges == 6 > star.open_wedges
    derivation = cert.derive(SEQUENCE, CEILING)
    assert (derivation.cross_gap, derivation.cross_edge_bound) == (4, 3)


def test_parity_not_the_gap_bound_removes_one_and_three_cross_edges(
    t255_switches: list[census.Structure],
) -> None:
    """4m <= 12 admits m = 0, 1, 2, 3; the even sum over H removes 1 and 3. With an odd sum the
    odd counts would be exactly the survivors, so parity comes from 2 e(H) + m."""

    assert cert.derive(SEQUENCE, CEILING).cross_edge_candidates == (0, 2)
    assert cert.cross_edge_candidates(12 * 11, 3, 12) == (0, 2)
    assert cert.cross_edge_candidates(12 * 11 + 1, 3, 12) == (1, 3)
    assert {cert.split_edges(_graph(s), H)[1] for s in t255_switches} == {2}


def _k12_minus_edge_with_two_cross_edges() -> cert.Graph:
    """CELL_A's degree sequence with m = 2: K12 - {0, 1}, cross edges 0-12 and 1-13, and on U
    the join of K4 on 14..17 with the 4-cycle 12-18-13-19."""

    edges = [p for p in combinations(range(12), 2) if p != (0, 1)]
    edges += [(0, 12), (1, 13)]
    edges += [p for p in combinations(range(12, 20), 2) if p not in ((12, 13), (18, 19))]
    return cert.simple_graph(20, edges)


def test_two_cross_edges_force_ten_open_wedges_inside_h(
    t255_switches: list[census.Structure],
) -> None:
    graph = _k12_minus_edge_with_two_cross_edges()
    assert cert.degrees(graph) == SEQUENCE
    assert cert.split_edges(graph, H) == (65, 2)
    ledger = cert.graph_ledger(graph)
    assert 4 * 2 <= ledger.degree_gap_sum <= 2 * ledger.open_wedges
    inside = {w for w in cert.open_wedges(graph) if w[0] in H and w[1:] == (0, 1)}
    assert inside == {(z, 0, 1) for z in range(2, 12)}
    assert ledger.open_wedges >= 10 > CEILING
    # Every T = 255 fixture switch is a degree-preserving fiber structure with m = 2: its one
    # non-edge in H carries the same ten wedges, and the ceiling refuses it.
    for structure in t255_switches:
        switched = _graph(structure)
        assert cert.degrees(switched) == SEQUENCE
        (x, y), *others = [p for p in combinations(sorted(H), 2) if p[1] not in switched[p[0]]]
        assert not others
        assert {(z, x, y) for z in H - {x, y}} <= cert.open_wedges(switched)
        assert (
            cert.graph_ledger(switched).open_wedges
            == census.realization(PROFILE, structure).open_wedges
            == 51
        )
        with pytest.raises(cert.CertificateError, match="outside CELL_A: 51 open wedges"):
            cert.structure_ledger(structure.triples, structure.pairs)
    assert cert.derive(SEQUENCE, CEILING).refuted == ((2, 10),)
    # The contradiction is strict: ten wedges refute m = 2 only below a ceiling of 10. At T = 268
    # the ceiling is 12, and step F fails closed.
    for ceiling in (10, census.wedge_count(PROFILE) - 3 * 268):
        with pytest.raises(cert.CertificateError, match="step F: m = 2 forces 10 open wedges"):
            cert.derive(SEQUENCE, ceiling)


@pytest.mark.parametrize(
    ("profile_id", "t"),
    [("66665555555322000000", 266), (cert.PROFILE_ID, 269), (cert.PROFILE_ID, 271)],
)
def test_the_certificate_covers_only_cell_a_at_t270(profile_id: str, t: int) -> None:
    with pytest.raises(cert.CertificateError, match="covers only CELL_A"):
        cert.certificate(profile_id, t)


def test_the_derivation_fails_closed_off_its_premises() -> None:
    # T = 271 leaves a ceiling of 3, below the forced graph's 6: no such graph has T > 270.
    with pytest.raises(cert.CertificateError, match="step G: the forced graph has 6 open"):
        cert.derive(SEQUENCE, census.wedge_count(PROFILE) - 3 * 271)
    cell_b = cert.overlap_degrees(cert.decode_profile("66665555555322000000"))
    with pytest.raises(cert.CertificateError, match="step E: the top degree 12 is not"):
        cert.derive(cell_b, 33)
    # G needs exactly two degree-6 tickets in U. With 7^4 6^4 on U, the m = 0 graph is K12 plus
    # K8 minus a two-edge matching, not K8 minus one edge, so the derivation stops at G.
    four_low = (11,) * 12 + (7,) * 4 + (6,) * 4
    two_missing = [p for p in combinations(sorted(U), 2) if p not in ((16, 17), (18, 19))]
    assert cert.degrees(cert.simple_graph(20, [*combinations(sorted(H), 2), *two_missing])) == (
        four_low
    )
    with pytest.raises(cert.CertificateError, match=r"step G: G\[U\] is not forced"):
        cert.derive(four_low, CEILING)
    with pytest.raises(cert.CertificateError, match="step B"):
        cert.derive(SEQUENCE, -1)
    with pytest.raises(cert.CertificateError, match="step B"):
        cert.derive((2, 1), 0)
    for value in ("5555555555551111110", "55555555555511111110", "15555555555511111100"):
        with pytest.raises(cert.CertificateError):
            cert.decode_profile(value)


def test_non_simple_inputs_are_refused(incumbent: census.Structure) -> None:
    with pytest.raises(cert.CertificateError, match="bad edge"):
        cert.simple_graph(3, [(1, 1)])
    with pytest.raises(cert.CertificateError, match="repeated edge"):
        cert.simple_graph(3, [(0, 1), (1, 0)])
    # A degree-preserving switch of pair lines 0-11 and 1-4 to 0-1 and 4-11 puts 0 and 1 on a
    # pair line and on the triple line (0, 1, 2): two shared lines.
    pairs = [p for p in incumbent.pairs if p not in ((0, 11), (1, 4))] + [(0, 1), (4, 11)]
    with pytest.raises(cert.CertificateError, match="two tickets share two lines"):
        cert.structure_graph(PROFILE, incumbent.triples, pairs)
    with pytest.raises(cert.CertificateError, match="does not realize its degree"):
        cert.structure_graph(PROFILE, incumbent.triples, incumbent.pairs[1:])
    # A triple line holding one ticket twice is the fiber form of a loop.
    looped = [(0, 0, 1), *incumbent.triples[1:]]
    with pytest.raises(cert.CertificateError, match=r"malformed line \(0, 0, 1\)"):
        cert.structure_graph(PROFILE, looped, incumbent.pairs)


@pytest.mark.parametrize(
    ("field", "value"),
    [("W", 817), ("TARGET_T", 271), ("TRIANGLES", 271), ("OPEN_WEDGES", 3), ("VERDICT", "PASS")],
)
def test_a_tampered_record_is_refused(field: str, value: object) -> None:
    record = cert.certificate()
    with pytest.raises(cert.CertificateError, match=field):
        cert.verify_certificate({**record, field: value})


def test_the_rigid_graph_does_not_fix_the_line_structure(incumbent: census.Structure) -> None:
    """Swapping tickets 0 and 1 keeps the overlap graph but moves lines: the certificate fixes
    the graph only, never the F3 decomposition or an exact count."""

    def swap(line: tuple[int, ...]) -> tuple[int, ...]:
        return tuple(sorted({0: 1, 1: 0}.get(v, v) for v in line))

    triples = sorted(map(swap, incumbent.triples))
    pairs = sorted(map(swap, incumbent.pairs))
    assert set(pairs) != set(incumbent.pairs) and set(triples) != set(incumbent.triples)
    assert cert.structure_graph(PROFILE, triples, pairs) == _graph(incumbent)
    moved = cert.structure_ledger(triples, pairs)
    assert moved.matching != cert.structure_ledger(incumbent.triples, incumbent.pairs).matching
    assert (moved.triangles, moved.open_wedges, moved.blocks) == (270, 6, 26)
    assert cert.NOT_CLAIMED["F3_DECOMPOSITION"] == "NOT_FIXED"
    assert cert.NOT_CLAIMED["EXACT_WIN_COUNT"] == "NOT_COMPUTED"


def test_the_solve_and_scoring_guards_are_live() -> None:
    cp_model: Any = import_module("ortools.sat.python.cp_model")
    with pytest.raises(AssertionError, match="solve or exact-scoring"):
        cp_model.CpSolver().Solve(cp_model.CpModel())
    with pytest.raises(AssertionError, match="solve or exact-scoring"):
        census.official_evaluator()


def test_main_prints_the_certificate(capsys: pytest.CaptureFixture[str]) -> None:
    cert.main()
    assert json.loads(capsys.readouterr().out)["CERTIFICATE_SHA256"] == CERTIFICATE_SHA256
