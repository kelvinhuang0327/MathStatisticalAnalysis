"""Independent full-envelope oracles, immutable authority and semantic mutations."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import replace
from fractions import Fraction
from functools import cache
from itertools import combinations
from math import comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_all_resolved_cursor_refinement_r1 as x
from lottolab.research import b649_k20_min_s2_class_dominance_or_descent_r13 as r13
from lottolab.research import b649_k20_min_s2_cursor_dynamic_owner_chase_r25 as r25

OWNER = "66555555555540000000"
MIXED = "66666555555311100000"
STS13 = "55555555555511111100"


@pytest.fixture(scope="module")
def authority() -> x.Authority:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("new solver, R25/R30 execution or outcome enumeration")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(x.nb.r28, "bounded_batch", forbidden)
        patch.setattr(x.nb.r28, "solve_group", forbidden)
        patch.setattr(x.nb.r30, "evaluate_portfolio", forbidden)
        patch.setattr(r13, "degree_class_open_wedge_relaxation", forbidden)
        patch.setattr(r25, "degree_class_open_wedge_relaxation", forbidden)
        return x.load_authority()


@pytest.fixture(scope="module")
def result(authority: x.Authority) -> dict[str, object]:
    return x.compute_result(authority)


def certificates(result: Mapping[str, object]) -> dict[str, object]:
    return x.object_row(result["RESOLVED_CERTIFICATES"])


def final_ledger(auth: x.Authority, result: Mapping[str, object]) -> dict[str, x.Row]:
    return {
        pid: replace(
            row, bound=x.integer(x.object_row(certificates(result)[pid])["CERTIFIED_PROFILE_BOUND"])
        )
        for pid, row in auth.ledger.items()
    }


def test_immutable_identity_and_inherited_authorities(
    authority: x.Authority, result: dict[str, object]
) -> None:
    assert x.BASE_HEAD == "dbc4c14d71eeb855920e973cfd8e859ca6041e7b"
    assert x.chase.git("rev-parse", f"{x.BASE_HEAD}^{{tree}}").decode().strip() == x.BASE_TREE
    assert (
        hashlib.sha256(
            x.pinned_file(f"{x.chase.prior.RESULT_DIRECTORY}/{x.previous.RESULT_FILENAME}")
        ).hexdigest()
        == x.BASE_RESULT_SHA256
    )
    assert result["PRESERVED_PREDECESSOR_RESULT"] == authority.sealed
    assert (
        x.integration.family(authority.ledger, authority.family_authority)
        == authority.sealed["FINAL_FAMILY"]
    )
    assert x.object_row(authority.sealed["FINAL_FAMILY"])["FAMILY_UB"] == 313394584
    assert len(authority.special) == result["SPECIAL_PER_T_PROFILE_COUNT"] == 25
    for relative, expected in {**authority.provenance, **authority.result_provenance}.items():
        assert hashlib.sha256(x.pinned_file(relative)).hexdigest() == expected
    assert result["SOLVER_CALLS"] == result["OUTCOME_ENUMERATIONS"] == 0


def test_complete_partition_and_sealed_frontier(authority: x.Authority) -> None:
    coverage = x.partition_check(authority.ledger, authority.frontier, authority.family_authority)
    assert [
        coverage[k]
        for k in (
            "ADMISSIBLE_PROFILE_COUNT",
            "RESOLVED_ROW_COUNT",
            "UNDER_CURSOR_PROFILE_COUNT",
            "EXCLUDED_HISTOGRAM_COUNT",
            "RAW_HISTOGRAM_COUNT",
            "UNCOVERED_PROFILE_COUNT",
        )
    ] == [4844, 4647, 197, 282, 5126, 0]
    profiles = [tuple(map(int, pid)) for pid in authority.frontier]
    assert min(sum(comb(6 + d, 2) for d in p) for p in profiles) == 774
    assert max(sum(comb(6 + d, 2) for d in p) for p in profiles) == 785
    assert x.chase.prior.ids_digest(profiles) == x.FRONTIER_SHA256
    assert not set(authority.ledger) & set(authority.frontier)
    for incomplete in (
        authority.frontier[:-1],
        (*authority.frontier[:-1], authority.frontier[0]),
        (*authority.frontier, authority.frontier[0]),
    ):
        with pytest.raises(AssertionError):
            x.partition_check(authority.ledger, incomplete, authority.family_authority)
    missing = dict(authority.ledger)
    del missing[OWNER]
    with pytest.raises(AssertionError):
        x.partition_check(missing, authority.frontier, authority.family_authority)
    as_row = {**authority.ledger, x.chase.prior.CURSOR_ID: authority.ledger[OWNER]}
    with pytest.raises(AssertionError):
        x.partition_check(as_row, authority.frontier, authority.family_authority)
    wrong_name = {**missing, "00000000000000000000": authority.ledger[OWNER]}
    with pytest.raises(ValueError, match="twenty integer degrees"):
        x.partition_check(wrong_name, authority.frontier, authority.family_authority)


def test_all_cap_provenance_independent_nb_floor(authority: x.Authority) -> None:
    kinds: Counter[str] = Counter()
    for pid, row in authority.ledger.items():
        x.assert_row(authority, pid)
        proof = authority.cap_proofs[pid]
        g = [6 + int(d) for d in pid]
        w = sum(comb(v, 2) for v in g)
        closed = sum(
            sum(min(own - 1, v - 1) for v in sorted(g[:i] + g[i + 1 :], reverse=True)[:own]) // 2
            for i, own in enumerate(g)
        )
        nb_cap = closed // 3
        r18_cap = (w - 5) // 3
        assert [proof[k] for k in ("W", "NB_CAP", "R18_CAP")] == [w, nb_cap, r18_cap]
        assert 22 <= row.cap <= w // 3
        kind = x.integration.text(proof["CLASS"])
        kinds[kind] += 1
        if kind == "NB_R18":
            assert min(nb_cap, r18_cap) <= row.cap
        elif kind == "R30_REFUTATION":
            identity = x.object_row(proof["IDENTITY"])
            assert identity["STATUS"] == "INFEASIBLE"
            assert identity["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == row.cap
            assert identity["REFUTED_GRAPH_TRIANGLE_COUNT"] == row.cap + 1
            assert pid in x.rows(identity["PROFILE_IDS"])
        elif kind == "R25_R13":
            sealed = x.object_row(proof["IDENTITY"])
            assert sealed["PROFILE_ID"] == pid
            assert x.object_row(sealed["R13_RELAXATION"])["SOLVER_STATUS"] == "OPTIMAL"
        else:
            assert kind == "ZERO_CORE_SPLIT"
            assert 0 in tuple(map(int, pid))
            assert x.integer(x.object_row(proof["IDENTITY"])["TRIANGLE_CAP"]) >= row.cap
    assert kinds == {"NB_R18": 4579, "R30_REFUTATION": 51, "R25_R13": 1, "ZERO_CORE_SPLIT": 16}


def independent_s5(pid: str) -> tuple[int, int, int, list[int]]:
    d = tuple(map(int, pid))
    hk: list[int] = []
    for k in range(1, 7):
        high = [v for v in d if v >= k]
        exclusions = [22 - v for v in d if 0 < v < k]
        hk.append(min([sum(high) // 3 if len(high) >= 3 else 0, *exclusions]))
    # C(4+minimum degree,2) starts at C(5,2); each increment k has weight k+3.
    common = 220 + sum((k + 3) * hk[k - 1] for k in range(2, 7))
    n2 = sum(v * (v - 1) // 2 for v in d)
    return common, n2, 7 * (common + 2 * n2), hk


def assert_s5_caps(authority: x.Authority) -> None:
    for pid in authority.ledger:
        proof = x.degree_s5_cap(pid)
        common, n2, s5, hk = independent_s5(pid)
        assert [proof[k] for k in ("COMMON_PAIR_SUM_CAP", "N_2T_CAP", "S5_CAP")] == [common, n2, s5]
        assert [x.rows(raw)[5] for raw in x.rows(proof["THRESHOLD_CAPS"])] == hk
    assert 0 not in x.profile_values(authority.frontier[0])
    assert x.degree_s5_cap(authority.frontier[0])["STATUS"] == "PASS"
    assert x.rows(x.rows(x.degree_s5_cap(OWNER)["THRESHOLD_CAPS"])[-1])[5] == 0


def test_s5_all_profiles_and_independent_threshold_optimization(authority: x.Authority) -> None:
    assert_s5_caps(authority)
    for pid in (OWNER, MIXED, STS13, "66666666664200000000", authority.frontier[0]):
        d = tuple(map(int, pid))

        @cache
        def optimum(k: int, remaining: int, above: int, d: tuple[int, ...] = d) -> int:
            if k == 0:
                return 0 if remaining == 0 else -(10**9)
            high = [v for v in d if v >= k]
            low = [v for v in d if 0 < v < k]
            return max(
                (
                    count * comb(k + 4, 2) + optimum(k - 1, remaining - count, above + count)
                    for count in range(remaining + 1)
                    if 3 * (above + count) <= sum(high)
                    and (len(high) >= 3 or above + count == 0)
                    and all(above + count <= 22 - v for v in low)
                ),
                default=-(10**9),
            )

        assert optimum(6, 22, 0) == x.degree_s5_cap(pid)["COMMON_PAIR_SUM_CAP"]


@pytest.mark.parametrize(
    ("triples", "expected"),
    [
        ((), 0),
        (((0, 1, 2),), 7),
        (((0, 1, 2), (2, 3, 4)), 28),
    ],
)
def test_independent_local_s5_identity(triples: tuple[tuple[int, ...], ...], expected: int) -> None:
    edges = set(combinations(range(5), 2))
    profile = x.identity.previous.local_profile(5, edges, triples)
    labels = [mask for mask, count in enumerate(profile) if mask for _ in range(count)]
    exact = 7 * sum(
        sum(m.bit_count() for m in q) >= 15
        and all(sum(bool(m & (1 << v)) for m in q) >= 3 for v in range(5))
        for q in combinations(labels, 7)
    )
    common, n2 = x.identity.s5_counts(tuple(range(5)), edges, triples)
    assert x.identity.s5_identity_value(common, n2) == exact == expected


def test_bonferroni_and_rounding() -> None:
    assert x.identity.bonferroni_check()["STATUS"] == "PASS"
    for r in range(21):
        partial = sum((-1) ** (k + 1) * comb(r, k) for k in range(1, 6))
        assert partial - int(r > 0) == (comb(r - 1, 5) if r else 0)
    for s4 in range(292000, 292007):
        fourth, fifth = x.moment_bounds(5171904, s4, 7560)
        exact = 372228640 - 63838600 + 5171904 - Fraction(4 * s4, 7)
        assert fourth == -(-exact.numerator // exact.denominator)
        assert 0 <= fourth - exact < 1
        assert fifth == 372228640 - 63838600 + 5171904 - s4 + 7560


def independent_refinement(auth: x.Authority, pid: str) -> tuple[list[x.Term], list[x.Term]]:
    old = x.authoritative_terms(auth, pid)
    s5 = independent_s5(pid)[2]
    new: list[x.Term] = []
    for t, bound, k, a, s4, s3 in old:
        fifth = 372228640 - 63838600 + s3 - s4 + s5
        new.append((t, min(bound, fifth), k, a, s4, s3))
    return old, new


def assert_terms(auth: x.Authority) -> None:
    for pid in (OWNER, MIXED, STS13, *x.previous.ACTIVE_IDS, auth.frontier[0]):
        if pid not in auth.ledger:
            continue
        old, new = independent_refinement(auth, pid)
        cert = x.resolved_certificate(auth, pid)
        assert cert["ALL_T_TERMS_SHA256"] == x.digest(new)
        assert cert["AUTHORITATIVE_TERMS_SHA256"] == x.digest(old)
        assert cert["CERTIFIED_PROFILE_BOUND"] == max(term[1] for term in new)
        assert cert["LEGAL_T_COUNT"] == len(new) == auth.ledger[pid].cap - 21
        assert cert["CHANGED_T_TERM_COUNT"] == sum(
            a[1] != b[1] for a, b in zip(old, new, strict=True)
        )


def test_all_1083326_resolved_terms_independent_oracle(
    authority: x.Authority, result: dict[str, object]
) -> None:
    count = 0
    for pid, raw in certificates(result).items():
        cert = x.object_row(raw)
        old, new = independent_refinement(authority, pid)
        g = [6 + int(v) for v in pid]
        w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
        amax = sum(int(v) * (4 + int(v)) for v in pid) // 3
        assert [t[0] for t in old] == list(range(22, authority.ledger[pid].cap + 1))
        for t, bound, k, a, s4, s3 in old:
            expected_k = max(0, -(-(j - (max(g) - 2) * (w - 3 * t)) // 4))
            floor = max(
                authority.ledger[pid].s4_base, 679 * expected_k - 231 * min(expected_k, amax)
            )
            assert s3 == 2800 * w + 11872 * (t - 22) - 30800
            assert s4 >= floor
            if t != authority.ledger[pid].cap or pid not in authority.special:
                assert (k, a, s4) == (expected_k, min(expected_k, amax), floor)
            assert bound <= 372228640 - 63838600 + s3 - 4 * s4 // 7
        assert cert["ALL_T_TERMS_SHA256"] == x.digest(new)
        assert cert["AUTHORITATIVE_TERMS_SHA256"] == x.digest(old)
        assert cert["CERTIFIED_PROFILE_BOUND"] == max(term[1] for term in new)
        count += len(new)
    assert count == result["TOTAL_T_TERM_COUNT"] == 1083326
    assert_terms(authority)


def assert_special_scope(auth: x.Authority) -> None:
    old = x.authoritative_terms(auth, MIXED)
    assert old[-2][0] == 263 and old[-2][4] == 281295
    assert old[-1][0] == 264 and old[-1][4] == 309456
    cert = x.resolved_certificate(auth, MIXED)
    assert cert["ARGMAX_T"] == [263]
    assert cert["CERTIFIED_PROFILE_BOUND"] == 313282011
    assert cert["CAP_T_NEW_BOUND"] == 313265722
    bad = copy.deepcopy(auth.special)
    x.rows(x.rows(bad[MIXED]["ALL_T_TERMS"])[-2])[4] = 309456
    with pytest.raises(AssertionError, match="leaked outside"):
        x.authoritative_terms(replace(auth, special=bad), MIXED)


def test_all_special_scope_and_null_motif_cap_preserved(authority: x.Authority) -> None:
    assert_special_scope(authority)
    for pid in authority.special:
        x.authoritative_terms(authority, pid)
    old = x.authoritative_terms(authority, "66655555555440000000")
    assert old[-1][3] is None
    new, _fifths = x.refine_terms(old, independent_s5("66655555555440000000")[2])
    assert new[-1][3] is None


def assert_frontier() -> None:
    for pid in ("66544333333333332222", "44444433333333333333"):
        cert = x.frontier_certificate(pid)
        p = tuple(map(int, pid))
        w = sum(comb(6 + d, 2) for d in p)
        terms = x.split.route_b_terms(p, w // 3, x.nb.r28.profile_s4_floor(p))
        assert cert["TRIANGLE_CAP"] == w // 3
        assert cert["LEGAL_T_COUNT"] == w // 3 - 21
        assert cert["ALL_T_TERMS_SHA256"] == x.digest(terms)
        assert cert["CERTIFIED_PROFILE_BOUND"] == max(term[1] for term in terms)


def test_complete_frontier_envelopes_and_eight_maximizers(
    authority: x.Authority, result: dict[str, object]
) -> None:
    frontier = x.object_row(result["FRONTIER_CERTIFICATES"])
    assert set(frontier) == set(authority.frontier)
    for pid, raw in frontier.items():
        cert = x.object_row(raw)
        p = tuple(map(int, pid))
        w = sum(comb(6 + d, 2) for d in p)
        terms = x.split.route_b_terms(p, w // 3, x.nb.r28.profile_s4_floor(p))
        assert cert["T_RANGE"] == [22, w // 3]
        assert cert["LEGAL_T_COUNT"] == len(terms)
        assert cert["ALL_T_TERMS_SHA256"] == x.digest(terms)
        assert cert["CERTIFIED_PROFILE_BOUND"] == max(term[1] for term in terms)
    maxima = sorted(
        pid
        for pid, raw in frontier.items()
        if x.object_row(raw)["CERTIFIED_PROFILE_BOUND"] == 313226448
    )
    assert result["FINAL_FRONTIER_MAX"] == 313226448 < x.INCUMBENT
    assert len(maxima) == result["FRONTIER_MAXIMIZER_COUNT"] == 8
    assert maxima == result["FRONTIER_MAXIMIZER_IDS"]
    assert all(
        x.object_row(frontier[p])["W"] == 785 and x.object_row(frontier[p])["ARGMAX_T"] == [261]
        for p in maxima
    )
    with pytest.raises(AssertionError, match="sound bound"):
        x.integration.install(authority.ledger, OWNER, 313226448, "cursor-as-resolved-row")


def assert_family(auth: x.Authority, result: dict[str, object]) -> None:
    final = final_ledger(auth, result)
    frontier = x.object_row(result["FRONTIER_CERTIFICATES"])
    family = x.family(final, frontier, auth)
    assert family["FAMILY_UB"] == 313283936
    assert family["OWNER_IDS"] == [OWNER]
    cursor = x.object_row(family["CURSOR_AUTHORITY"])
    assert cursor["SLOT"] == "CURSOR" and cursor["BOUND"] == 313226448
    assert cursor["PROFILE_COUNT"] == 197
    assert x.chase.prior.CURSOR_ID not in final
    all_bounds = {
        **{p: r.bound for p, r in final.items()},
        **{p: x.integer(x.object_row(c)["CERTIFIED_PROFILE_BOUND"]) for p, c in frontier.items()},
    }
    assert len(all_bounds) == 4844 and max(all_bounds.values()) == family["FAMILY_UB"]
    assert family["REMAINING_GAP"] == 20048


def test_family_regressions_all_78_survivors_and_incumbent(
    authority: x.Authority, result: dict[str, object]
) -> None:
    assert_family(authority, result)
    assert [
        result[k]
        for k in (
            "RESOLVED_ROW_COUNT",
            "CURSOR_PROFILE_COUNT",
            "CHANGED_RESOLVED_ROW_COUNT",
            "UNCHANGED_RESOLVED_ROW_COUNT",
            "FINAL_RESOLVED_MAX",
            "FINAL_COMPLETE_FAMILY_UB",
            "REMAINING_GAP",
            "INCUMBENT_PROFILE_BOUND",
        )
    ] == [4647, 197, 4640, 7, 313283936, 313283936, 20048, 313263916]
    certs = certificates(result)
    assert x.object_row(certs[OWNER])["ARGMAX_T"] == [264]
    assert result["FINAL_RESOLVED_OWNER_IDS"] == result["FINAL_OWNER_IDS"] == [OWNER]
    above = sorted(
        p
        for p, c in certs.items()
        if x.integer(x.object_row(c)["CERTIFIED_PROFILE_BOUND"]) > 313263888
    )
    assert len(above) == result["ABOVE_INCUMBENT_ROW_COUNT"] == 78
    assert result["ABOVE_INCUMBENT_PROFILE_IDS"] == above
    assert STS13 in above
    unchanged = {
        p
        for p, c in certs.items()
        if x.object_row(c)["CERTIFIED_PROFILE_BOUND"] == authority.ledger[p].bound
    }
    assert len(unchanged) == 7


def test_all_77_supports_remain_sound(authority: x.Authority, result: dict[str, object]) -> None:
    sound = x.object_row(result["WITNESS_SOUNDNESS"])
    witnesses = x.object_row(sound["WITNESSES"])
    recorded = {p for p, r in authority.ledger.items() if r.realization is not None}
    assert set(witnesses) == {*recorded, "P2", "CONDITIONAL", "TOP", "STS13", "TRADED_STS13"}
    assert len(witnesses) == sound["WITNESS_COUNT"] == 77
    for raw in witnesses.values():
        w = x.object_row(raw)
        pid = x.integration.text(w["PROFILE_ID"])
        assert x.integer(w["EXACT_S5"]) <= independent_s5(pid)[2]
        assert x.integer(w["EXACT_MOMENT_UPPER_BOUND"]) <= x.integer(
            x.object_row(certificates(result)[pid])["CERTIFIED_PROFILE_BOUND"]
        )
    assert x.object_row(sound["TRADED_STS13_EXACT_UNION"])["EXACT_ANY_PRIZE_UNION"] == 313263888
    assert x.object_row(sound["STS13_EXACT_UNION"])["EXACT_ANY_PRIZE_UNION"] == 313263867


def source_guard(auth: x.Authority) -> None:
    for update in ({"source": "tampered"}, {"cap": auth.ledger[OWNER].cap + 1}):
        bad_row = replace(auth.ledger[OWNER], **update)
        bad = replace(auth, ledger={**auth.ledger, OWNER: bad_row})
        with pytest.raises(AssertionError, match="row/cap/source"):
            x.resolved_certificate(bad, OWNER)
    proofs = copy.deepcopy(auth.cap_proofs)
    proofs[OWNER]["CLASS"] = "NB_R18"
    with pytest.raises(AssertionError, match="row/cap/source"):
        x.resolved_certificate(replace(auth, cap_proofs=proofs), OWNER)


def test_row_and_cap_proof_tampering(authority: x.Authority) -> None:
    source_guard(authority)


@pytest.mark.parametrize("kind", ["R30_REFUTATION", "R25_R13", "ZERO_CORE_SPLIT"])
def test_cap_source_semantic_tampering(
    kind: str, authority: x.Authority, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = next(p for p, proof in authority.cap_proofs.items() if proof["CLASS"] == kind)
    row = authority.cap_ledger[pid]
    sources = x.nb.load_cap_authorities()
    if kind == "R30_REFUTATION":
        proofs = copy.deepcopy(sources.proofs)
        index = x.integer(x.object_row(authority.cap_proofs[pid]["IDENTITY"])["ATTEMPT_INDEX"])
        proofs[index]["STATUS"] = "OPTIMAL"
        sources = replace(sources, proofs=proofs)
    elif kind == "R25_R13":
        cheap = copy.deepcopy(sources.cheap)
        for cert in cheap:
            if cert["PROFILE_ID"] == pid:
                x.object_row(cert["R13_RELAXATION"])["SOLVER_STATUS"] = "FEASIBLE"
        sources = replace(sources, cheap=cheap)
    else:
        original = x.source_certificate

        def tampered(locator: str, provenance: dict[str, str]) -> dict[str, object]:
            cert = original(locator, provenance)
            return {**cert, "TRIANGLE_CAP": row.cap - 1}

        monkeypatch.setattr(x, "source_certificate", tampered)
    with pytest.raises(AssertionError):
        x.recover_cap_proof(pid, row, sources, {})


def test_result_tampering(authority: x.Authority, result: dict[str, object]) -> None:
    with pytest.raises(AssertionError, match="tampered complete"):
        x.verify_result({**result, "FINAL_FRONTIER_MAX": 0}, authority)


@pytest.mark.parametrize("kind", ["source", "result", "tree", "special_json"])
def test_pinned_authority_tampering(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    filename = x.previous.RESULT_FILENAME if kind == "result" else x.identity.RESULT_FILENAME
    path = (
        Path(x.previous.__file__ or "").resolve()
        if kind == "source"
        else x.chase.ROOT / x.chase.prior.RESULT_DIRECTORY / filename
    )
    original = Path.read_bytes

    def changed(target: Path) -> bytes:
        return original(target) + (b" " if target == path else b"")

    x.load_authority.cache_clear()
    with monkeypatch.context() as patch:
        if kind == "tree":
            patch.setattr(x, "BASE_TREE", "0" * 40)
        else:
            patch.setattr(Path, "read_bytes", changed)
        with pytest.raises(AssertionError):
            x.load_authority()
    x.load_authority.cache_clear()


@pytest.mark.parametrize("first", ["motif", "predecessor", "successor"])
def test_fresh_process_import_orders(first: str) -> None:
    names = {"motif": x.motif.__name__, "predecessor": x.previous.__name__, "successor": x.__name__}
    script = (
        "import importlib; "
        f"importlib.import_module({names[first]!r}); "
        f"x=importlib.import_module({x.__name__!r}); r=x.compute_result(); "
        "assert r['FINAL_COMPLETE_FAMILY_UB']==313283936; "
        "assert r['FINAL_FRONTIER_MAX']==313226448; "
        "assert len(x.motif.historical_provenance())==27"
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


def test_cli_verify_exact_byte_replay(result: dict[str, object]) -> None:
    raw = x.RESULT_PATH.read_bytes()
    assert raw == x.integration.render(result).encode("utf-8")
    assert json.loads(raw) == result
    run = subprocess.run(
        [sys.executable, "-m", x.__name__, "--verify"],
        cwd=x.chase.ROOT,
        env={**os.environ, "PYTHONPATH": str(x.chase.ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout)["RESULT_REPLAY_STATUS"] == "PASS"


MUTATIONS = {
    "wrong_s5_sign": ("identity", "s5_identity_value", "+ 2 * n2", "- 2 * n2"),
    "double_triple_weight14": ("identity", "s5_identity_value", "+ 2 * n2", "+ 0 * n2"),
    "copy_other_degrees": (
        "caps",
        "degree_s5_cap",
        "d = profile_values(profile)",
        "d = profile_values('66665555554431000000')",
    ),
    "omit_two_triple_correction": (
        "caps",
        "degree_s5_cap",
        "common_cap + 2 * n2_cap",
        "common_cap",
    ),
    "wrong_incidence_floor": ("caps", "degree_s5_cap", "sum(high) // 3", "sum(high) // 2"),
    "ignore_low_vertex": ("caps", "degree_s5_cap", "22 - max(low, default=0)", "22"),
    "forget_three_high_vertices": (
        "caps",
        "degree_s5_cap",
        "sum(high) // 3 if len(high) >= 3 else 0",
        "sum(high) // 3",
    ),
    "wrong_neighbour_offset": ("caps", "degree_s5_cap", "comb(4 + k, 2)", "comb(3 + k, 2)"),
    "wrong_n2_cap": ("caps", "degree_s5_cap", "comb(v, 2)", "comb(v, 3)"),
    "wrong_weight7": ("caps", "degree_s5_cap", "7 * (common_cap", "6 * (common_cap"),
    "round_fourth_down": (
        "rounding",
        "moment_bounds",
        "-(-exact.numerator // exact.denominator)",
        "exact.numerator // exact.denominator",
    ),
    "take_weaker_bound": ("terms", "refine_terms", "min(bound, fifth)", "max(bound, fifth)"),
    "add_duplicate_credit": (
        "terms",
        "refine_terms",
        "min(bound, fifth)",
        "min(bound, fifth) - (4 * s4) // 7",
    ),
    "only_update_cap_t": (
        "terms",
        "refine_terms",
        "min(bound, fifth)",
        "min(bound, fifth) if t == old[-1][0] else bound",
    ),
    "drop_lower_t": ("terms", "refine_terms", "in old:", "in old[-1:]:"),
    "cap_only_profile_max": (
        "special",
        "resolved_certificate",
        "max(term[1] for term in new)",
        "new[-1][1]",
    ),
    "sum_profile_terms": (
        "terms",
        "resolved_certificate",
        "max(term[1] for term in new)",
        "sum(term[1] for term in new)",
    ),
    "alter_non_bound_field": ("terms", "refine_terms", "k, a, s4, s3))", "k + 1, a, s4, s3))"),
    "leak_motif_floor": (
        "special",
        "authoritative_terms",
        "terms = [(t, b, k, a, s4, s3) for t, b, k, a, s4, s3 in old]",
        "terms = [(t, b, k, a, old[-1][4], s3) for t, b, k, a, s4, s3 in old]",
    ),
    "skip_cap_source_guard": (
        "source",
        "assert_row",
        'proof["ROW_IDENTITY_SHA256"] != digest(row_identity(pid, row))',
        "False",
    ),
    "shrink_frontier_t_range": (
        "frontier",
        "frontier_certificate",
        "cap = w // 3",
        "cap = w // 3 - 1",
    ),
    "ceil_frontier_cap": ("frontier", "frontier_certificate", "cap = w // 3", "cap = -(-w // 3)"),
    "family_from_cursor_only": (
        "family",
        "family",
        "maximum = max(resolved_max, cursor_bound)",
        "maximum = cursor_bound",
    ),
    "family_from_resolved_only": (
        "family",
        "family",
        '"BOUND": cursor_bound,',
        '"BOUND": resolved_max,',
    ),
    "incomplete_frontier": (
        "family",
        "family",
        "coverage = partition_check(ledger, tuple(frontier), auth.family_authority)",
        "frontier = dict(list(frontier.items())[:-1]); "
        "coverage = partition_check(ledger, tuple(frontier), auth.family_authority)",
    ),
    "cursor_as_resolved_row": (
        "family",
        "family",
        "coverage = partition_check(ledger, tuple(frontier), auth.family_authority)",
        "ledger = {**ledger, chase.prior.CURSOR_ID: next(iter(ledger.values()))}; "
        "coverage = partition_check(ledger, tuple(frontier), auth.family_authority)",
    ),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_non_equivalent_semantic_mutations_killed(
    name: str, authority: x.Authority, result: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    guard_name, function, old, new = MUTATIONS[name]
    target = x.identity if guard_name == "identity" else x
    original = cast(Callable[..., object], getattr(target, function))
    source = inspect.getsource(original)
    assert source.count(old) == 1
    namespace: dict[str, object] = dict(original.__globals__)
    exec(compile(source.replace(old, new), f"<semantic-mutation:{name}>", "exec"), namespace)

    def guard() -> None:
        if guard_name == "identity":
            test_independent_local_s5_identity(((0, 1, 2), (2, 3, 4)), 28)
        elif guard_name == "caps":
            assert_s5_caps(authority)
        elif guard_name == "rounding":
            test_bonferroni_and_rounding()
        elif guard_name == "special":
            assert_special_scope(authority)
        elif guard_name == "source":
            source_guard(authority)
        elif guard_name == "frontier":
            assert_frontier()
        elif guard_name == "family":
            assert_family(authority, result)
        else:
            assert_terms(authority)

    guard()
    with monkeypatch.context() as patch:
        patch.setattr(target, function, namespace[function])
        errors = (
            (AssertionError, pytest.fail.Exception, ValueError)
            if name == "drop_lower_t"
            else (AssertionError, pytest.fail.Exception)
        )
        with pytest.raises(errors):
            guard()
    guard()
