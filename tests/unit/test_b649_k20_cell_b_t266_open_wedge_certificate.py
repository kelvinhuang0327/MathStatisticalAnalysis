"""Focused tests for the CELL_B T = 266 closed-form open-wedge certificate.

Nothing is solved. The frozen CELL_B model is built once, its pin checked, and its constraints
compared with the ones the proof uses. CELL_B structures come from a pure-Python
degree-preserving switch search with fixed seeds, steered into every boundary the proof names.
The census's own realization code recounts each of them. Small members of the same model family
(capacity 3, eight active tickets) are enumerated exhaustively. The enumerator is checked
against brute force where brute force is cheap.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import replace
from importlib import import_module
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.research import b649_k20_cell_b_t266_open_wedge_certificate as cert
from lottolab.research import b649_k20_fiber_near_top_s3_census as census
from lottolab.research import b649_k20_two_open_cells_targeted_solver as engine

PROFILE = cert.decode_profile(cert.PROFILE_ID)
C = cert.TICKET_CAPACITY
FULL = (0, 1, 2, 3)
INACTIVE = tuple(range(14, 20))
CERTIFICATE_SHA256 = "911628a1dfbaf8878d7291037ec378ea4e04010392db804b801f984c8269ea5b"
INT64_MIN, INT64_MAX = -(2**63), 2**63 - 1

Line = tuple[int, ...]
Pair = tuple[int, int]


def _pair(a: int, b: int) -> Pair:
    return (a, b) if a < b else (b, a)


# CELL_B structures: degree-preserving switches, accepted only when no conflict is added -----


def _switch_triples(
    profile: Sequence[int], rng: random.Random, avoid: Iterable[Pair] = ()
) -> tuple[Line, ...]:
    """Triple lines realizing ``profile``'s triple degrees, pairwise sharing one ticket at most,
    and covering no pair in ``avoid``."""

    banned = set(avoid)
    stubs = [v for v, d in enumerate(profile) for _ in range(d)]
    k = len(stubs) // 3
    triples = [[stubs[j], stubs[j + k], stubs[j + 2 * k]] for j in range(k)]
    cover = Counter(_pair(a, b) for t in triples for a, b in combinations(t, 2))

    def penalty(p: Pair) -> int:
        return max(0, cover[p] - 1) + (cover[p] if p in banned else 0)

    cost = sum(penalty(p) for p in list(cover))
    for _ in range(400_000):
        if cost == 0:
            return tuple(sorted(tuple(sorted(t)) for t in triples))
        i, j = rng.sample(range(k), 2)
        a, b = rng.choice(triples[i]), rng.choice(triples[j])
        if a in triples[j] or b in triples[i]:
            continue
        new_i = [b if x == a else x for x in triples[i]]
        new_j = [a if x == b else x for x in triples[j]]
        old = [_pair(x, y) for t in (triples[i], triples[j]) for x, y in combinations(t, 2)]
        new = [_pair(x, y) for t in (new_i, new_j) for x, y in combinations(t, 2)]
        keys = set(old) | set(new)
        before = sum(penalty(p) for p in keys)
        cover.subtract(old)
        cover.update(new)
        after = sum(penalty(p) for p in keys)
        if after <= before:
            triples[i], triples[j] = new_i, new_j
            cost += after - before
        else:
            cover.subtract(new)
            cover.update(old)
    raise AssertionError("switch search found no triple system")


def _switch_pairs(
    profile: Sequence[int],
    capacity: int,
    blocked: set[Pair],
    rng: random.Random,
    forced: Sequence[Pair] = (),
    forbid: Iterable[Pair] = (),
) -> tuple[Pair, ...]:
    """Pair lines realizing the pair degrees, avoiding ``blocked`` and ``forbid``, with every
    ``forced`` pair line included."""

    left = [capacity - d for d in profile]
    for a, b in forced:
        left[a] -= 1
        left[b] -= 1
    bad = blocked | set(forced) | set(forbid)
    stubs = [v for v, r in enumerate(left) for _ in range(r)]
    rng.shuffle(stubs)
    edges = [(stubs[2 * j], stubs[2 * j + 1]) for j in range(len(stubs) // 2)]
    multiplicity = Counter(_pair(*e) for e in edges if e[0] != e[1])

    def own(e: Pair) -> int:
        return int(e[0] == e[1] or _pair(*e) in bad)

    cost = sum(map(own, edges)) + sum(x - 1 for x in multiplicity.values() if x > 1)
    for _ in range(400_000):
        if cost == 0:
            return tuple(sorted([*forced, *(_pair(*e) for e in edges)]))
        i, j = rng.sample(range(len(edges)), 2)
        (a, b), (x, y) = edges[i], edges[j]
        if rng.random() < 0.5:
            x, y = y, x
        new = [(a, y), (x, b)]
        old_keys = [_pair(*e) for e in (edges[i], edges[j]) if e[0] != e[1]]
        new_keys = [_pair(*e) for e in new if e[0] != e[1]]
        keys = set(old_keys) | set(new_keys)
        before = own(edges[i]) + own(edges[j]) + sum(max(0, multiplicity[p] - 1) for p in keys)
        multiplicity.subtract(old_keys)
        multiplicity.update(new_keys)
        after = own(new[0]) + own(new[1]) + sum(max(0, multiplicity[p] - 1) for p in keys)
        if after <= before:
            edges[i], edges[j] = new[0], new[1]
            cost += after - before
        else:
            multiplicity.subtract(new_keys)
            multiplicity.update(old_keys)
    raise AssertionError("switch search found no pair-line graph")


def _structure(
    seed: int,
    avoid: Iterable[Pair] = (),
    forced: Sequence[Pair] = (),
    forbid: Iterable[Pair] = (),
) -> tuple[tuple[Line, ...], tuple[Pair, ...]]:
    rng = random.Random(seed)
    triples = _switch_triples(PROFILE, rng, avoid)
    blocked = {_pair(a, b) for t in triples for a, b in combinations(t, 2)}
    return triples, _switch_pairs(PROFILE, C, blocked, rng, forced, forbid)


def _census_count(triples: Sequence[Line], pairs: Sequence[Pair]) -> census.Realization:
    """The census's own triangle and open-wedge count of the same structure."""

    lines = cast(tuple[census.Triple, ...], tuple(sorted(triples)))
    structure = census.Structure(lines, tuple(sorted(pairs)))
    return census.realization(PROFILE, structure)


# Small members of the model family: exhaustive enumeration --------------------------------


def _triple_systems(profile: Sequence[int]) -> list[tuple[Line, ...]]:
    """Every set of triple lines with these triple degrees, any two sharing one ticket at most.

    The smallest ticket with degree left takes its remaining lines, each with itself as least
    member, in increasing order, so every set is produced once."""

    active = [v for v, d in enumerate(profile) if d]
    left, covered, chosen = list(profile), set[Pair](), list[Line]()
    found: list[tuple[Line, ...]] = []

    def extend() -> None:
        live = [v for v in active if left[v]]
        if not live:
            found.append(tuple(sorted(chosen)))
            return
        v = live[0]
        last = max((t for t in chosen if t[0] == v), default=None)
        for a, b in combinations([w for w in live if w > v], 2):
            line, pairs = (v, a, b), ((v, a), (v, b), (a, b))
            if (last is not None and line <= last) or any(p in covered for p in pairs):
                continue
            for x in line:
                left[x] -= 1
            covered.update(pairs)
            chosen.append(line)
            extend()
            chosen.pop()
            covered.difference_update(pairs)
            for x in line:
                left[x] += 1

    extend()
    return found


def _pair_graphs(
    profile: Sequence[int], capacity: int, blocked: set[Pair]
) -> list[tuple[Pair, ...]]:
    """Every set of pair lines with the pair degrees capacity - d, avoiding ``blocked``."""

    n = len(profile)
    left, used, chosen = [capacity - d for d in profile], set(blocked), list[Pair]()
    found: list[tuple[Pair, ...]] = []

    def extend() -> None:
        live = [v for v in range(n) if left[v]]
        if not live:
            found.append(tuple(sorted(chosen)))
            return
        v = live[0]
        last = max((p for p in chosen if p[0] == v), default=None)
        for w in live:
            p = (v, w)
            if w <= v or p in used or (last is not None and p <= last):
                continue
            used.add(p)
            chosen.append(p)
            left[v] -= 1
            left[w] -= 1
            extend()
            used.discard(p)
            chosen.pop()
            left[v] += 1
            left[w] += 1

    extend()
    return found


def _all_structures(
    profile: Sequence[int], capacity: int
) -> list[tuple[tuple[Line, ...], tuple[Pair, ...]]]:
    out: list[tuple[tuple[Line, ...], tuple[Pair, ...]]] = []
    for triples in _triple_systems(profile):
        blocked = {_pair(a, b) for t in triples for a, b in combinations(t, 2)}
        out += [(triples, pairs) for pairs in _pair_graphs(profile, capacity, blocked)]
    return out


# The frozen CELL_B cell and model --------------------------------------------------------


def _linear_form(terms: dict[int, int], lo: int, hi: int) -> tuple[object, ...]:
    """A linear constraint up to term order and an overall sign; int64 ends mean unbounded."""

    low = None if lo == INT64_MIN else lo
    high = None if hi == INT64_MAX else hi
    items = tuple(sorted((v, k) for v, k in terms.items() if k))
    if items and items[0][1] < 0:
        items = tuple((v, -k) for v, k in items)
        low, high = (None if high is None else -high), (None if low is None else -low)
    return items, low, high


@pytest.fixture(scope="module")
def frozen_model() -> Any:
    ceiling = census.wedge_count(PROFILE) - 3 * cert.TARGET_T
    return census.support_model((PROFILE,), ceiling)[0]


def test_cell_b_profile_target_and_ceiling_match_the_frozen_engine() -> None:
    (cell_b,) = [cell for cell in engine.TARGET_CELLS if cell.name == "CELL_B"]
    references = cert.FROZEN_REFERENCES
    assert (cell_b.profile_id, cell_b.t) == (cert.PROFILE_ID, cert.TARGET_T)
    assert engine.engine_sha256() == references["TWO_CELL_ENGINE_SHA256"]
    assert census.engine_sha256() == references["CENSUS_ENGINE_SHA256"]
    assert engine.MODEL_PROTO_SHA256["CELL_B"] == references["CELL_B_MODEL_PROTO_SHA256"]
    assert engine.INCUMBENT_COUNT == cert.INCUMBENT_COUNT
    assert census.decode_profile(cert.PROFILE_ID) == PROFILE
    assert cert.wedge_count(PROFILE, C) == census.wedge_count(PROFILE) == 831
    assert cell_b.ceiling == census.wedge_count(PROFILE) - 3 * cert.TARGET_T == 33
    record = cert.certificate()
    assert (record["W"], record["OPEN_WEDGE_CEILING"]) == (831, cell_b.ceiling)


def test_frozen_cell_b_model_contains_every_constraint_the_proof_uses(frozen_model: Any) -> None:
    """Any solution of the pinned model is a fiber structure whose open wedges each force their
    own indicator to 1, under a sum of at most 33. Extra model constraints only remove
    solutions, so they cannot weaken the infeasibility argument."""

    proto = frozen_model.Proto()
    pin = cert.FROZEN_REFERENCES["CELL_B_MODEL_PROTO_SHA256"]
    assert census.sha256_bytes(str(proto).encode()) == pin
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
    assert sum(name[0] == "t" for name in names) == len(t) == comb(14, 3)
    assert sum(name[0] == "o" for name in names) == len(o) == 20 * comb(19, 2)

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
        expected.append(_linear_form({**on_pairs, index[f"d{v}"]: 1}, C, C))
    for p in b:
        covering = {t[line]: 1 for line in t if set(p) <= set(line)}
        expected.append(_linear_form({**covering, b[p]: 1}, INT64_MIN, 1))
        uncovered = {x: -1 for x in covering}
        expected.append(_linear_form({e[p]: 1, **uncovered, b[p]: -1}, 0, 0))
    for (c, x, y), wedge in o.items():
        terms = {wedge: 1, e[_pair(c, x)]: -1, e[_pair(c, y)]: -1, e[(x, y)]: 1}
        expected.append(_linear_form(terms, -1, INT64_MAX))
    ceiling = census.wedge_count(PROFILE) - 3 * cert.TARGET_T
    expected.append(_linear_form(dict.fromkeys(o.values(), 1), INT64_MIN, ceiling))
    assert len(expected) == len(set(expected)) == 20 + 20 + 190 + 190 + 3420 + 1
    assert [form for form in expected if not present[form]] == []


# The closed-form derivation ----------------------------------------------------------------


def test_certificate_closes_cell_b_at_t266() -> None:
    record = cert.certificate()
    assert record["VERDICT"] == cert.INFEASIBLE
    assert record["PER_FULL_TICKET_MINIMUM"] == record["CLOSED_FORM_MINIMUM"] == 12
    assert record["OPEN_WEDGE_LOWER_BOUND"] == 48
    assert record["OPEN_WEDGE_CEILING"] == 33
    assert record["MAX_TRIANGLES"] == 261
    assert (record["FULL_TICKETS"], record["ACTIVE_TICKETS"], record["INACTIVE_TICKETS"]) == (
        4,
        14,
        6,
    )
    assert (record["M_MIN"], record["M_MAX"], record["PARTNER_DEGREES"]) == (6, 18, [2, 3, 5, 6])
    assert record["SOLVER_USED"] is False
    assert record["CERTIFICATE_SHA256"] == CERTIFICATE_SHA256


def test_relaxation_matches_the_raw_lemmas_and_its_closed_form() -> None:
    relax = cert.relaxation()
    incidence = sum(C + d for d in PROFILE if d)
    assert relax.active_incidence == incidence == 150
    points = list(relax.domain())
    assert len(points) == (5 + 4 + 2 + 1) * 7
    for d_u, s_u, m in points:
        active_edges, remainder = divmod(incidence - m, 2)
        g_u = C + d_u - s_u
        centred = comb(2 * C, 2) - (active_edges - 2 * C - g_u)
        assert remainder == 0
        assert relax.centred(d_u, s_u, m) == centred
        assert relax.ended(s_u, m) == m - s_u
        assert 2 * (centred + m - s_u) == 18 + 2 * d_u + 3 * m - 4 * s_u
    counts = {p: relax.centred(*p) + relax.ended(p[1], p[2]) for p in points}
    assert [p for p, count in counts.items() if count == min(counts.values())] == [(2, 4, 6)]
    assert relax.per_ticket_minimum() == relax.closed_form_minimum() == 12


def _closes(per_ticket: int) -> bool:
    return cert.decide(4 * per_ticket, 33) == cert.INFEASIBLE


def test_each_load_bearing_inequality_is_needed_and_l4_only_adds_margin() -> None:
    relax = cert.relaxation()
    assert _closes(relax.per_ticket_minimum())
    # L2 dropped (m may be 0): the bound collapses to 4 * 3 = 12.
    no_l2 = replace(relax, m_min=0).per_ticket_minimum()
    assert no_l2 == 3 and not _closes(no_l2)
    # L1's "u is active" dropped (u may have d = 0 and six inactive neighbours): 4 * 6 = 24.
    no_active_partner = replace(relax, partner_degrees=(0, *relax.partner_degrees))
    assert no_active_partner.per_ticket_minimum() == 6
    assert not _closes(no_active_partner.per_ticket_minimum())
    # s_u <= 6 - d_u weakened to s_u <= 6: 4 * 8 = 32 <= 33.
    wide = min(
        relax.centred(d, s, m) + relax.ended(s, m)
        for d in relax.partner_degrees
        for s in range(C + 1)
        for m in range(relax.m_min, relax.m_max + 1, 2)
    )
    assert wide == 8 and not _closes(wide)
    # L4 dropped: L3 alone still gives 4 * 10 = 40 > 33, so L4 only widens the margin 7 -> 15.
    l3_only = min(relax.centred(*point) for point in relax.domain())
    assert l3_only == 10 and _closes(l3_only)
    assert cert.decide(48, 48) == cert.INCOMPLETE
    assert cert.decide(48, 47) == cert.INFEASIBLE


@pytest.mark.parametrize("t", range(258, 268))
def test_the_bound_refutes_t_from_262_upwards_for_this_profile_only(t: int) -> None:
    ceiling = cert.wedge_count(PROFILE, C) - 3 * t
    assert (cert.decide(48, ceiling) == cert.INFEASIBLE) == (t >= 262)


# CELL_B structures --------------------------------------------------------------------------


def _check_cell_b(triples: Sequence[Line], pairs: Sequence[Pair]) -> cert.StructureLedger:
    ledger = cert.structure_ledger(PROFILE, C, triples, pairs)
    recount = _census_count(triples, pairs)
    assert (ledger.triangles, ledger.open_wedges) == (recount.triangles, recount.open_wedges)
    relax = cert.relaxation()
    domain = set(relax.domain())
    for row in ledger.tickets:
        point = (row.partner_degree, row.partner_inactive_neighbours, ledger.active_inactive_lines)
        assert point in domain
        assert row.partner_active_neighbours == C + point[0] - point[1]
        assert (row.centred, row.ended) == (relax.centred(*point), relax.ended(*point[1:]))
        assert row.centred + row.ended >= relax.per_ticket_minimum()
    assert [row.full_ticket for row in ledger.tickets] == list(FULL)
    assert ledger.open_wedges >= ledger.counted >= 48
    assert ledger.triangles <= 261
    return ledger


@pytest.mark.parametrize("seed", range(16))
def test_random_cell_b_structures_satisfy_every_lemma_exactly(seed: int) -> None:
    triples, pairs = _structure(seed)
    _check_cell_b(triples, pairs)


PARTNER_OF_TICKET_0 = {6: 1, 5: 4, 3: 11, 2: 12}


@pytest.mark.parametrize("m", [6, 18])
@pytest.mark.parametrize("d_u", sorted(PARTNER_OF_TICKET_0))
def test_boundary_structures_reach_every_partner_degree_and_m_extreme(d_u: int, m: int) -> None:
    """Ticket 0 misses u, all of u's pair lines go into I (s_u = 6 - d_u), and m is 6 (I is a
    K6) or 18 (no pair line inside A)."""

    u = PARTNER_OF_TICKET_0[d_u]
    forced: list[Pair] = [(u, i) for i in INACTIVE[: C - d_u]]
    if m == 6:
        forced += combinations(INACTIVE, 2)
        forbid: list[Pair] = []
    else:
        forbid = list(combinations(range(14), 2))
    triples, pairs = _structure(1000 + 10 * d_u + m, [(0, u)], forced, forbid)
    ledger = _check_cell_b(triples, pairs)
    row = ledger.tickets[0]
    assert (row.partner, row.partner_degree, row.partner_inactive_neighbours) == (u, d_u, C - d_u)
    assert ledger.active_inactive_lines == m
    assert 2 * (row.centred + row.ended) == 6 * d_u - 6 + 3 * m


def test_all_four_full_tickets_can_sit_at_the_per_ticket_minimum_together() -> None:
    """Every full ticket misses ticket 12 (d = 2), whose four pair lines all go into the K6 on
    I. Each counts exactly 12, so the counted families total exactly 48; the structure still
    has many more open wedges outside them."""

    forced = [*combinations(INACTIVE, 2), *((12, i) for i in INACTIVE[:4])]
    triples, pairs = _structure(7, [(f, 12) for f in FULL], forced)
    ledger = _check_cell_b(triples, pairs)
    assert [(r.partner, r.partner_inactive_neighbours) for r in ledger.tickets] == [(12, 4)] * 4
    assert [r.centred + r.ended for r in ledger.tickets] == [12] * 4
    assert ledger.counted == 48 < ledger.open_wedges


# Small members of the model family, exhaustively -------------------------------------------

# profile -> (capacity, structures, Counter of (d_u, s_u, m) over every full ticket)
SMALL_MEMBERS: dict[tuple[int, ...], tuple[int, int, dict[tuple[int, int, int], int]]] = {
    (2, 2, 2, 2, 2, 2, 0, 0, 0): (2, 30, {(2, 0, 0): 180}),
    (3, 3, 3, 3, 3, 2, 2, 2, 0): (3, 300, {(2, 1, 3): 1260, (3, 0, 3): 240}),
    (3, 3, 3, 2, 2, 2, 2, 1, 0, 0): (
        3,
        4896,
        {
            (1, 1, 4): 4320,
            (1, 2, 4): 1584,
            (1, 2, 6): 1296,
            (2, 0, 4): 1728,
            (2, 1, 4): 4464,
            (2, 1, 6): 1296,
        },
    ),
    (3, 3, 3, 3, 3, 3, 2, 1, 0, 0, 0): (3, 270, {(1, 2, 3): 1080, (2, 1, 3): 540}),
}


@pytest.mark.parametrize("profile", sorted(SMALL_MEMBERS))
def test_small_family_members_satisfy_every_lemma_exhaustively(profile: tuple[int, ...]) -> None:
    capacity, size, expected_rows = SMALL_MEMBERS[profile]
    structures = _all_structures(profile, capacity)
    assert len(structures) == len(set(structures)) == size
    rows = Counter[tuple[int, int, int]]()
    for triples, pairs in structures:
        ledger = cert.structure_ledger(profile, capacity, triples, pairs)
        for row in ledger.tickets:
            assert row.partner_inactive_neighbours <= capacity - row.partner_degree
            rows[
                row.partner_degree, row.partner_inactive_neighbours, ledger.active_inactive_lines
            ] += 1
        assert ledger.open_wedges >= ledger.counted
    assert rows == expected_rows


def test_the_enumerators_agree_with_brute_force() -> None:
    profile = (2, 2, 2, 2, 2, 2, 0, 0, 0)
    brute = sorted(
        chosen
        for chosen in combinations(list(combinations(range(6), 3)), 4)
        if Counter(v for line in chosen for v in line) == dict.fromkeys(range(6), 2)
        and len({p for line in chosen for p in combinations(line, 2)}) == 12
    )
    assert sorted(_triple_systems(profile)) == brute
    assert len(brute) == 30
    for profile, systems in (
        ((3, 3, 3, 3, 3, 3, 2, 1, 0, 0, 0), None),
        ((3, 3, 3, 2, 2, 2, 2, 1, 0, 0), 4),
    ):
        needs = [3 - d for d in profile]
        for triples in _triple_systems(profile)[:systems]:
            blocked = {_pair(a, b) for t in triples for a, b in combinations(t, 2)}
            usable = [
                p
                for p in combinations(range(len(profile)), 2)
                if p not in blocked and min(needs[v] for v in p)
            ]
            graphs = sorted(
                chosen
                for chosen in combinations(usable, sum(needs) // 2)
                if Counter(v for p in chosen for v in p) == {v: k for v, k in enumerate(needs) if k}
            )
            assert sorted(_pair_graphs(profile, 3, blocked)) == graphs != []


# Fail-closed inputs and the command line ----------------------------------------------------


def test_the_ledger_rejects_anything_outside_the_model() -> None:
    triples, pairs = _structure(0)
    first = triples[0]
    error = cert.CertificateError
    with pytest.raises(error, match="share two lines"):
        cert.overlap_graph(PROFILE, C, triples, (*pairs, (first[0], first[1])))
    with pytest.raises(error, match="degree-0 ticket"):
        cert.overlap_graph(PROFILE, C, ((first[0], first[1], 19), *triples[1:]), pairs)
    with pytest.raises(error, match="does not realize its degree"):
        cert.overlap_graph(PROFILE, C, triples, pairs[1:])
    with pytest.raises(error, match="malformed line"):
        cert.overlap_graph(PROFILE, C, ((1, 1, 2), *triples[1:]), pairs)
    with pytest.raises(error, match="malformed line"):
        cert.overlap_graph(PROFILE, C, triples, ((0, 20), *pairs[1:]))
    fano = ((0, 1, 2), (0, 3, 4), (0, 5, 6), (1, 3, 5), (1, 4, 6), (2, 3, 6), (2, 4, 5))
    assert len(cert.overlap_graph((3,) * 7, 3, fano, ())) == 7
    with pytest.raises(error, match="L1 needs"):
        cert.structure_ledger((3,) * 7, 3, fano, ())
    one, other = frozenset({(0, 1, 2)}), frozenset({(1, 0, 2)})
    assert cert.disjoint_union_size([one, other]) == 2
    with pytest.raises(error, match="share a wedge"):
        cert.disjoint_union_size([one, one | other])
    for bad in ("6666555555532200000", "56665555555322000000", "77665555555322000000"):
        with pytest.raises(error):
            cert.decode_profile(bad)


def test_the_l1_gate_fires_on_a_degree_preserving_graph_outside_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Swap edges 0-a and i-j for 0-i and a-j. Every degree stays the same, so W - 3T still
    holds, but full ticket 0 now has a neighbour in I. That is not a fiber structure."""

    triples, pairs = _structure(0)
    adjacency = [set(n) for n in cert.overlap_graph(PROFILE, C, triples, pairs)]
    i, j = next(p for p in pairs if set(p) <= set(INACTIVE))
    a = next(v for v in sorted(adjacency[0]) if j not in adjacency[v] and v != j)
    for x, y, z in ((0, a, i), (j, i, a)):
        adjacency[x].discard(y)
        adjacency[y].discard(x)
        adjacency[x].add(z)
        adjacency[z].add(x)
    doctored = tuple(frozenset(n) for n in adjacency)
    assert [len(n) for n in doctored] == [C + d for d in PROFILE]

    def doctored_graph(*_: object) -> cert.Adjacency:
        return doctored

    monkeypatch.setattr(cert, "overlap_graph", doctored_graph)
    with pytest.raises(cert.CertificateError, match="L1: full ticket 0"):
        cert.structure_ledger(PROFILE, C, triples, pairs)


def test_the_verdict_fails_closed_when_the_two_minimum_derivations_disagree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def disagreeing(_: cert.Relaxation) -> int:
        return 11

    monkeypatch.setattr(cert.Relaxation, "closed_form_minimum", disagreeing)
    record = cert.certificate()
    assert record["OPEN_WEDGE_LOWER_BOUND"] == 48
    assert record["VERDICT"] == cert.INCOMPLETE


def test_main_prints_the_certificate(capsys: pytest.CaptureFixture[str]) -> None:
    cert.main()
    out = capsys.readouterr().out
    assert f'"CERTIFICATE_SHA256": "{CERTIFICATE_SHA256}"' in out
    assert f'"VERDICT": "{cert.INFEASIBLE}"' in out
    assert Path(cert.__file__).name == "b649_k20_cell_b_t266_open_wedge_certificate.py"
