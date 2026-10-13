"""Independent degree/graph/term oracles and falsifiable certificate guards."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from math import ceil, comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_shared_neighbor_deficit_certificate_r1 as x

OWNER = "66555555555540000000"
STS13 = "55555555555511111100"
MIXED = "66666555555311100000"
BOUNDS_SHA = "07e72b19645da1013768cf88cb3f11af4b127f8f3366c0ec506cd67ca44d6cf6"


@pytest.fixture(scope="module")
def authority() -> x.Authority:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("new solver, R25/R30 execution or outcome enumeration")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(x.nb.r28, "bounded_batch", forbidden)
        patch.setattr(x.nb.r28, "solve_group", forbidden)
        patch.setattr(x.nb.r30, "evaluate_portfolio", forbidden)
        # The same solver entrypoints guarded by the immutable predecessor tests.
        from lottolab.research import b649_k20_min_s2_class_dominance_or_descent_r13 as r13
        from lottolab.research import b649_k20_min_s2_cursor_dynamic_owner_chase_r25 as r25

        patch.setattr(r13, "degree_class_open_wedge_relaxation", forbidden)
        patch.setattr(r25, "degree_class_open_wedge_relaxation", forbidden)
        return x.load_authority()


@pytest.fixture(scope="module")
def result(authority: x.Authority) -> dict[str, object]:
    return x.compute_result(authority)


def independent_q(g: Sequence[int]) -> tuple[int, ...]:
    answer: list[int] = []
    for v, own in enumerate(g):
        h = sorted((value for i, value in enumerate(g) if i != v), reverse=True)[:own]
        deficits = [max(own - degree, 0) for degree in h]
        answer.append(max(ceil(Fraction(sum(deficits), 2)), max(deficits, default=0)))
    return tuple(answer)


def independent_floor(pid: str, t: int) -> tuple[int, int, int]:
    d = tuple(map(int, pid))
    g = tuple(6 + v for v in d)
    w, u = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    b = sum(v * (gv - 2) for v, gv in zip(d, g, strict=True))
    delta = sum((max(g) - v) * q for v, q in zip(g, independent_q(g), strict=True))
    l_hat = (max(g) - 2) * (w - 3 * t) - delta
    k4 = max(0, ceil(Fraction(u - l_hat, 4)))
    floor = max(0, 231 * k4 - 63 * (b // 3) + 56 * (2 * u - l_hat - b))
    return l_hat, k4, floor


def assert_degree_proofs(auth: x.Authority) -> None:
    for pid in auth.active:
        row = auth.ledger[pid]
        proof = x.neighbor_deficit(pid, row.cap)
        g = tuple(6 + int(v) for v in pid)
        assert proof.d == tuple(map(int, pid)) and proof.g == g
        assert proof.q == independent_q(g)
        for i, own in enumerate(g):
            h = sorted(g[:i] + g[i + 1 :], reverse=True)[:own]
            assert proof.neighbors[i] == tuple(h)
            assert proof.deficits[i] == tuple(max(own - v, 0) for v in h)
        assert proof.w == sum(comb(v, 2) for v in g)
        assert proof.u == sum(comb(v, 3) for v in g)
        assert proof.b == sum(int(v) * (gv - 2) for v, gv in zip(pid, g, strict=True))
        assert proof.delta == sum(
            (max(g) - v) * q for v, q in zip(g, independent_q(g), strict=True)
        )
        assert proof.cap == min(row.cap, (proof.w - sum(independent_q(g))) // 3)


def test_exact_authority_and_bounded_adoption(
    authority: x.Authority, result: dict[str, object]
) -> None:
    assert x.BASE_HEAD == "a1e5dd3cc32a07f6f5c6e70482578aeb6c950aaf"
    assert x.chase.git("rev-parse", f"{x.BASE_HEAD}^{{tree}}").decode().strip() == x.BASE_TREE
    relative = f"{x.chase.prior.RESULT_DIRECTORY}/{x.previous.RESULT_FILENAME}"
    assert hashlib.sha256(x.pinned_file(relative)).hexdigest() == x.BASE_RESULT_SHA256
    assert len(authority.ledger) == 4647 and len(authority.active) == 78
    assert list(authority.active) == authority.sealed["ABOVE_INCUMBENT_PROFILE_IDS"]
    assert x.active_profiles(authority.ledger, authority.sealed) == authority.active
    assert (
        result["SOURCE_SHA256"] == hashlib.sha256(Path(x.__file__ or "").read_bytes()).hexdigest()
    )
    for path, sha in {**authority.provenance, **authority.inherited.result_provenance}.items():
        assert hashlib.sha256(x.pinned_file(path)).hexdigest() == sha
    assert result["SOLVER_CALLS"] == result["OUTCOME_ENUMERATIONS"] == 0


@pytest.mark.parametrize(
    "profile",
    [
        OWNER[::-1],
        OWNER[:-1],
        "x" + OWNER[1:],
        "7" + OWNER[1:],
        "0" * 20,
        (True, *tuple(map(int, OWNER))[1:]),
        (6.0, *tuple(map(int, OWNER))[1:]),
    ],
)
def test_invalid_degrees_and_order_rejected(profile: str | Sequence[int]) -> None:
    with pytest.raises(ValueError):
        x.profile_values(profile)


def test_all_active_degree_data_and_cap_proofs(authority: x.Authority) -> None:
    assert_degree_proofs(authority)
    for invalid in (21, 1000, True, 264.0):
        with pytest.raises(ValueError):
            x.neighbor_deficit(OWNER, cast(int, invalid))
    for pid in authority.active:
        proof = x.neighbor_deficit(pid, authority.ledger[pid].cap)
        for t in (21, proof.cap + 1, True):
            with pytest.raises(ValueError):
                x.s4_floor(proof, t)


def graph_deficit_check(n: int, edges: set[tuple[int, int]]) -> None:
    neighbors = [{u for u in range(n) if tuple(sorted((u, v))) in edges} for v in range(n)]
    g = [len(adj) for adj in neighbors]
    q = independent_q(g)
    ow = [sum(e not in edges for e in combinations(sorted(adj), 2)) for adj in neighbors]
    for v, adj in enumerate(neighbors):
        actual = sorted((g[u] for u in adj), reverse=True)
        highest = sorted((g[u] for u in range(n) if u != v), reverse=True)[: g[v]]
        assert all(a <= h for a, h in zip(actual, highest, strict=True))
        missing = [g[v] - 1 - len(neighbors[u] & adj) for u in adj]
        assert sum(missing) == 2 * ow[v]
        assert max(missing, default=0) <= ow[v]
        assert all(m >= max(g[v] - g[u], 0) for u, m in zip(adj, missing, strict=True))
        assert ow[v] >= q[v]
    triangles = sum(set(combinations(t, 2)) <= edges for t in combinations(range(n), 3))
    w = sum(comb(v, 2) for v in g)
    assert sum(ow) == w - 3 * triangles
    delta = sum((max(g) - v) * qv for v, qv in zip(g, q, strict=True))
    l_hat = (max(g) - 2) * (w - 3 * triangles) - delta
    assert sum((v - 2) * ov for v, ov in zip(g, ow, strict=True)) <= l_hat
    assert triangles <= (w - sum(q)) // 3


def test_universal_neighbor_proof_every_small_graph() -> None:
    # Includes both q branches, isolated vertices and repeated degree ties.
    for n in range(2, 6):
        pairs = tuple(combinations(range(n), 2))
        for mask in range(1 << len(pairs)):
            graph_deficit_check(n, {p for i, p in enumerate(pairs) if mask >> i & 1})


def test_every_recorded_realization_neighbor_and_weighted_inequalities(
    authority: x.Authority,
) -> None:
    supports = [row.realization for row in authority.ledger.values() if row.realization is not None]
    supports += [
        x.previous.split.witness_supports(k) for k in ("P2", "STS13", "CONDITIONAL", "TOP")
    ]
    supports += [x.previous.identity.previous.traded_witness()]
    for support in supports:
        assert support is not None
        triples, pairs = support
        edges = {e for tau in triples for e in combinations(tau, 2)}
        edges |= {cast(tuple[int, int], tuple(sorted(e))) for e in pairs}
        graph_deficit_check(20, edges)
        d = sorted((sum(v in tau for tau in triples) for v in range(20)), reverse=True)
        pid = "".join(map(str, d))
        q = x.neighbor_deficit(pid, authority.ledger[pid].cap)
        assert q.q == independent_q(q.g)


def test_exact_quartet_identity_and_nonnegative_slack() -> None:
    primitive = x.previous.motif
    count = 0
    pairs = tuple(combinations(range(4), 2))
    for mask in range(64):
        edges = {p for i, p in enumerate(pairs) if mask >> i & 1}
        triples = [t for t in combinations(range(4), 3) if set(combinations(t, 2)) <= edges]
        for tau in (None, *triples):
            m = primitive.classify(edges, tau)
            u, l_value, b = primitive.incidences(4, edges, () if tau is None else (tau,))
            assert 4 * m.k == u - l_value + m.p + 2 * m.c
            assert b == 3 * m.a + 2 * m.d1 + m.p1
            exact = primitive.local_weight(edges, tau)
            assert exact == 231 * m.k - 63 * m.a + 56 * (2 * u - l_value - b) + 56 * (m.p1 + m.c)
            lower = max(
                0,
                231 * max(0, ceil(Fraction(u - l_value, 4)))
                - 63 * (b // 3)
                + 56 * (2 * u - l_value - b),
            )
            assert exact >= lower
            count += 1
    assert count == primitive.local_identity_check()["LOCAL_CASES"] == 96
    assert primitive.local_weight(set(pairs), None) == 679
    assert primitive.local_weight(set(pairs), (0, 1, 2)) == 448


def assert_all_terms(auth: x.Authority) -> None:
    for pid in auth.active:
        cert = x.active_certificate(auth, pid)
        old = x.authoritative_terms(auth, pid)
        g = tuple(6 + int(v) for v in pid)
        cap = min(auth.ledger[pid].cap, (sum(comb(v, 2) for v in g) - sum(independent_q(g))) // 3)
        s5 = x.integer(x.object_row(cert["DEGREE_S5_PROOF"])["S5_CAP"])
        expected: list[x.Term] = []
        for t, bound, k, a, s4, s3 in old:
            if t > cap:
                continue
            l_hat, k4, floor = independent_floor(pid, t)
            used = max(s4, floor)
            fourth = ceil(Fraction(7 * (372228640 - 63838600 + s3) - 4 * used, 7))
            fifth = 372228640 - 63838600 + s3 - used + s5
            expected.append(
                (
                    t,
                    bound,
                    k,
                    a,
                    s4,
                    s3,
                    l_hat,
                    k4,
                    floor,
                    used,
                    fourth,
                    fifth,
                    min(bound, fourth, fifth),
                )
            )
        assert cert["ALL_T_TERMS"] == expected
        assert cert["ALL_T_TERMS_SHA256"] == x.digest(expected)
        assert cert["T_RANGE"] == [22, cap]
        assert cert["CERTIFIED_PROFILE_BOUND"] == max(term[-1] for term in expected)
        assert cert["ARGMAX_T"] == [
            term[0] for term in expected if term[-1] == cert["CERTIFIED_PROFILE_BOUND"]
        ]


def test_every_retained_t_independent_integer_and_rational_oracle(authority: x.Authority) -> None:
    assert_all_terms(authority)


def assert_noncap_maximum(auth: x.Authority) -> None:
    # All new real maxima are at their cap. Exercise MAX with the real predecessor
    # envelope at t=263, below its sealed cap 264, through a controlled input seam.
    old = x.authoritative_terms(auth, MIXED)
    sealed = x.object_row(x.object_row(auth.sealed["RESOLVED_CERTIFICATES"])[MIXED])
    s5 = x.integer(x.object_row(sealed["DEGREE_S5_PROOF"])["S5_CAP"])
    incoming: list[x.Term] = []
    for t, bound, k, a, s4, s3 in old:
        fourth, fifth = x.previous.moment_bounds(s3, s4, s5)
        incoming.append(
            (t, bound, k, a, s4, s3, 0, k, 0, s4, fourth, fifth, min(bound, fourth, fifth))
        )
    maximum = max(term[-1] for term in incoming)
    assert [term[0] for term in incoming if term[-1] == maximum] == [263]
    assert incoming[-1][0] == 264 and incoming[-1][-1] < maximum

    def retained_predecessor_terms(*_args: object) -> list[x.Term]:
        return incoming

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(x, "refine_terms", retained_predecessor_terms)
        cert = x.active_certificate(auth, MIXED)
    assert cert["CERTIFIED_PROFILE_BOUND"] == maximum
    assert cert["ARGMAX_T"] == [263]


def assert_rounding_seam(auth: x.Authority) -> None:
    # Current floors are multiples of seven. Nonmultiples exercise the general
    # rational-ceiling operation independently of that accidental divisibility.
    old = x.authoritative_terms(auth, OWNER)
    proof = x.neighbor_deficit(OWNER, auth.ledger[OWNER].cap)
    sealed = x.object_row(x.object_row(auth.sealed["RESOLVED_CERTIFICATES"])[OWNER])
    s5 = x.integer(x.object_row(sealed["DEGREE_S5_PROOF"])["S5_CAP"])
    for remainder in range(7):
        t, bound, k, a, s4, s3 = old[0]
        first: x.previous.Term = (t, bound, k, a, s4 + remainder, s3)
        term = x.refine_terms([first, *old[1:]], proof, s5)[0]
        exact = Fraction(7 * (372228640 - 63838600 + s3) - 4 * (s4 + remainder), 7)
        assert term[10] == ceil(exact)
        assert 0 <= term[10] - exact < 1


def test_noncap_maximum_and_all_rounding_residues(authority: x.Authority) -> None:
    assert_noncap_maximum(authority)
    assert_rounding_seam(authority)


def test_all_cap_reductions_and_exclusions(
    authority: x.Authority, result: dict[str, object]
) -> None:
    certs = x.object_row(result["ACTIVE_CERTIFICATES"])
    excluded = 0
    reductions: list[str] = []
    for pid, raw in certs.items():
        cert = x.object_row(raw)
        proof = x.object_row(cert["NEIGHBOR_DEFICIT_PROOF"])
        g = tuple(6 + int(v) for v in pid)
        w, total_q = sum(comb(v, 2) for v in g), sum(independent_q(g))
        cap = min(authority.ledger[pid].cap, (w - total_q) // 3)
        assert proof["NEW_TRIANGLE_CAP"] == cap
        values = x.rows(cert["EXCLUDED_T_VALUES"])
        assert values == list(range(cap + 1, authority.ledger[pid].cap + 1))
        assert all(w - 3 * x.integer(t) < total_q for t in values)
        assert x.integer(cert["LEGAL_T_COUNT"]) + len(values) == cert["OLD_T_TERM_COUNT"]
        excluded += len(values)
        if values:
            reductions.append(pid)
    assert len(reductions) == 11 and excluded == result["EXCLUDED_T_TERM_COUNT"] == 24
    assert reductions == result["CAP_REDUCTION_PROFILE_IDS"]
    assert result["OLD_ACTIVE_T_TERM_COUNT"] == 18968
    assert result["RETAINED_T_TERM_COUNT"] == 18944


def test_special_floor_scope_s5_and_sts13(
    authority: x.Authority, result: dict[str, object]
) -> None:
    certs = x.object_row(result["ACTIVE_CERTIFICATES"])
    for pid, raw in certs.items():
        cert = x.object_row(raw)
        sealed = x.object_row(x.object_row(authority.sealed["RESOLVED_CERTIFICATES"])[pid])
        assert cert["DEGREE_S5_PROOF"] == sealed["DEGREE_S5_PROOF"]
        assert cert["CAP_AUTHORITY"] == sealed["CAP_AUTHORITY"]
        assert cert["SPECIAL_CERTIFICATE_SHA256"] == sealed["SPECIAL_CERTIFICATE_SHA256"]
        old = x.authoritative_terms(authority, pid)
        baseline = x.previous.split.route_b_terms(
            x.profile_values(pid), authority.ledger[pid].cap, authority.ledger[pid].s4_base
        )
        assert all(a[4] == b[4] for a, b in zip(old[:-1], baseline[:-1], strict=True))
    sts = x.object_row(certs[STS13])
    term = cast(list[x.Term], sts["ALL_T_TERMS"])[-1]
    assert term[0] == 270 and term[4] == term[9] == 331240
    assert term[-1] == result["STS13_BOUND"] == 313263916
    assert x.object_row(sts["DEGREE_S5_PROOF"])["S5_CAP"] == 6860
    assert x.previous.identity.s5_identity_value((0,), 2) == 28
    assert result["S5_IDENTITY"] == authority.sealed["S5_IDENTITY"]
    # An inherited unspecified motif A cap remains null, not a guessed integer.
    for fields in cast(list[x.Term], x.object_row(certs["66655555555440000000"])["ALL_T_TERMS"]):
        if fields[0] == authority.ledger["66655555555440000000"].cap:
            assert fields[3] is None


def assert_family(auth: x.Authority, result: dict[str, object]) -> None:
    certs = x.object_row(result["ACTIVE_CERTIFICATES"])
    final = dict(auth.ledger)
    for pid, raw in certs.items():
        final[pid] = replace(
            final[pid], bound=x.integer(x.object_row(raw)["CERTIFIED_PROFILE_BOUND"])
        )
    frontier = x.object_row(result["FRONTIER_CERTIFICATES"])
    bounds = x.complete_bounds(final, frontier, auth)
    assert len(bounds) == 4844 and bounds == sorted(bounds)
    assert x.digest(bounds) == BOUNDS_SHA
    assert max(x.integer(row[1]) for row in bounds) == 313263916
    assert [row[0] for row in bounds if row[1] == 313263916] == [STS13]
    assert sum(final[p].bound < 313263888 for p in auth.active) == 77
    assert final[OWNER].bound == 313261872
    assert result["FINAL_COMPLETE_FAMILY_UB"] == 313263916
    assert result["FINAL_OWNER_IDS"] == [STS13] and result["REMAINING_GAP"] == 28


def test_complete_4844_replay_unchanged_rows_frontier_and_all_witnesses(
    authority: x.Authority, result: dict[str, object]
) -> None:
    assert_family(authority, result)
    assert result["COMPLETE_BOUNDS_SHA256"] == BOUNDS_SHA
    assert result["ACTIVE_PROFILE_COUNT"] == 78 and result["PROFILES_BELOW_INCUMBENT"] == 77
    assert result["UNCHANGED_RESOLVED_ROW_COUNT"] == 4569
    assert result["UNCHANGED_RESOLVED_ROWS_SHA256"] == x.digest(
        [
            x.previous.row_identity(pid, row)
            for pid, row in sorted(authority.ledger.items())
            if pid not in authority.active
        ]
    )
    assert result["FRONTIER_CERTIFICATES"] == authority.sealed["FRONTIER_CERTIFICATES"]
    assert result["FRONTIER_PROFILE_COUNT"] == 197
    assert result["SPECIAL_PER_T_CERTIFICATES_SHA256"] == x.digest(
        authority.sealed["SPECIAL_PER_T_CERTIFICATES"]
    )
    sound = x.object_row(result["WITNESS_SOUNDNESS"])
    old_sound = x.object_row(authority.sealed["WITNESS_SOUNDNESS"])
    assert sound["WITNESS_COUNT"] == 77
    assert sound["PRESERVED_WITNESS_RECORDS_SHA256"] == x.digest(old_sound["WITNESSES"])
    for name, raw in x.object_row(sound["CHECKS"]).items():
        check = x.object_row(raw)
        witness = x.object_row(x.object_row(old_sound["WITNESSES"])[name])
        assert x.integer(witness["EXACT_S4_FROM_PINNED_LOCAL_TABLE"]) >= x.integer(check["S4_USED"])
        assert x.integer(witness["EXACT_S5"]) <= x.integer(check["S5_CAP"])
        assert x.integer(witness["EXACT_MOMENT_UPPER_BOUND"]) <= x.integer(check["T_BOUND"])


def test_missing_profile_incorrect_cap_floor_and_authority_rejected(authority: x.Authority) -> None:
    missing = dict(authority.ledger)
    del missing[OWNER]
    with pytest.raises(AssertionError):
        x.compute_result(replace(authority, ledger=missing))
    for bad in (
        replace(authority.ledger[OWNER], cap=265),
        replace(authority.ledger[OWNER], s4_base=1000000),
        replace(authority.ledger[OWNER], source="other"),
    ):
        with pytest.raises(AssertionError, match="sealed row/cap/floor"):
            x.compute_result(replace(authority, ledger={**authority.ledger, OWNER: bad}))
    bad_special = copy.deepcopy(authority.inherited.special)
    x.rows(x.rows(bad_special[MIXED]["ALL_T_TERMS"])[-2])[4] = 309456
    bad = replace(authority, inherited=replace(authority.inherited, special=bad_special))
    with pytest.raises(AssertionError, match="leaked outside"):
        x.authoritative_terms(bad, MIXED)
    with pytest.raises(AssertionError, match="outside the active"):
        x.active_certificate(
            authority, next(p for p in authority.ledger if p not in authority.active)
        )


def test_source_identity_tampering_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.read_bytes
    target = Path(x.previous.__file__ or "").resolve()

    def changed(path: Path) -> bytes:
        return original(path) + (b"\n# mutation\n" if path == target else b"")

    x.load_authority.cache_clear()
    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", changed)
        with pytest.raises(AssertionError, match="immutable source/result bytes"):
            x.load_authority()


@pytest.mark.parametrize("first", ["motif", "predecessor", "successor"])
def test_fresh_process_import_order_and_byte_verification(first: str) -> None:
    names = {
        "motif": x.previous.motif.__name__,
        "predecessor": x.previous.__name__,
        "successor": x.__name__,
    }
    script = (
        "import importlib; "
        f"importlib.import_module({names[first]!r}); "
        f"x=importlib.import_module({x.__name__!r}); "
        "r=x.compute_result(); assert r['FINAL_COMPLETE_FAMILY_UB']==313263916; "
        f"assert r['COMPLETE_BOUNDS_SHA256']=={BOUNDS_SHA!r}; "
        "assert x.RESULT_PATH.read_bytes()==x.integration.render(r).encode('utf-8')"
    )
    run = subprocess.run(
        [sys.executable, "-c", script],
        cwd=x.chase.ROOT,
        env={**os.environ, "PYTHONPATH": str(x.chase.ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_exact_result_bytes_and_tampering(
    authority: x.Authority, result: dict[str, object]
) -> None:
    raw = x.RESULT_PATH.read_bytes()
    assert raw == x.integration.render(result).encode("utf-8")
    assert json.loads(raw) == json.loads(x.integration.render(result))
    x.verify_result(result, authority)
    for key, value in (
        ("FINAL_COMPLETE_FAMILY_UB", 313263888),
        ("EXCLUDED_T_TERM_COUNT", 23),
        ("COMPLETE_BOUNDS_SHA256", "bad"),
    ):
        with pytest.raises(AssertionError, match="tampered universal"):
            x.verify_result({**result, key: value}, authority)


MUTATIONS = {
    "omit_own_vertex_exclusion": ("degree", "neighbor_deficit", "g[:i] + g[i + 1 :]", "g"),
    "wrong_deficit_sign": ("degree", "neighbor_deficit", "max(own - h, 0)", "max(h - own, 0)"),
    "round_q_down": ("degree", "neighbor_deficit", "(sum(ds) + 1) // 2", "sum(ds) // 2"),
    "omit_max_deficit": ("degree", "neighbor_deficit", "max(ds, default=0)", "0"),
    "omit_half_sum": ("degree", "neighbor_deficit", "(sum(ds) + 1) // 2", "0"),
    "wrong_delta_weight": ("degree", "neighbor_deficit", "(max(g) - v) * qv", "v * qv"),
    "omit_q_cap": ("degree", "neighbor_deficit", "(w - sum(q)) // 3", "w // 3"),
    "ceil_triangle_cap": (
        "degree",
        "neighbor_deficit",
        "(w - sum(q)) // 3",
        "-(-(w - sum(q)) // 3)",
    ),
    "drop_sealed_cap": (
        "degree",
        "neighbor_deficit",
        "min(sealed_cap, (w - sum(q)) // 3)",
        "(w - sum(q)) // 3",
    ),
    "wrong_delta_sign": ("terms", "s4_floor", "- proof.delta", "+ proof.delta"),
    "round_k_down": ("terms", "s4_floor", "-(-(proof.u - l_hat) // 4)", "(proof.u - l_hat) // 4"),
    "wrong_B_floor": ("terms", "s4_floor", "proof.b // 3", "-(-proof.b // 3)"),
    "wrong_slack_sign": (
        "terms",
        "s4_floor",
        "2 * proof.u - l_hat - proof.b",
        "2 * proof.u + l_hat - proof.b",
    ),
    "add_pasch_credit": ("terms", "s4_floor", "231 * k4", "231 * k4 + 28"),
    "min_s4_floors": ("terms", "refine_terms", "max(s4, shared)", "min(s4, shared)"),
    "add_s4_floors": ("terms", "refine_terms", "max(s4, shared)", "s4 + shared"),
    "max_upper_bounds": (
        "terms",
        "refine_terms",
        "min(bound, fourth, fifth)",
        "max(bound, fourth, fifth)",
    ),
    "duplicate_credit": (
        "terms",
        "refine_terms",
        "min(bound, fourth, fifth)",
        "min(bound, fourth, fifth) - shared",
    ),
    "keep_impossible_t": ("terms", "refine_terms", "if t > proof.cap:", "if False:"),
    "drop_lower_t": ("terms", "refine_terms", "in old:", "in old[-1:]:"),
    "cap_only_maximum": (
        "terms",
        "active_certificate",
        "max(term[-1] for term in new)",
        "new[-1][-1]",
    ),
    "incorrect_fourth_rounding": (
        "terms",
        "refine_terms",
        "previous.moment_bounds(s3, used, s5)",
        "((7*(372228640-63838600+s3)-4*used)//7, 372228640-63838600+s3-used+s5)",
    ),
    "incomplete_family": (
        "family",
        "complete_bounds",
        "bounds = {pid: row.bound for pid, row in ledger.items()}",
        "bounds = {pid: row.bound for pid, row in ledger.items() if pid in auth.active}",
    ),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_semantic_mutations_killed(
    name: str, authority: x.Authority, result: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    guard_name, function, old, new = MUTATIONS[name]
    original = cast(Callable[..., object], getattr(x, function))
    source = inspect.getsource(original)
    assert source.count(old) == 1
    namespace: dict[str, object] = dict(original.__globals__)
    exec(compile(source.replace(old, new), f"<semantic-mutation:{name}>", "exec"), namespace)

    def guard() -> None:
        if guard_name == "degree":
            assert_degree_proofs(authority)
        elif guard_name == "family":
            assert_family(authority, result)
        else:
            assert_all_terms(authority)
            if name == "cap_only_maximum":
                assert_noncap_maximum(authority)
            if name == "incorrect_fourth_rounding":
                assert_rounding_seam(authority)

    guard()
    with monkeypatch.context() as patch:
        patch.setattr(x, function, namespace[function])
        with pytest.raises((AssertionError, ValueError)):
            guard()
    guard()
