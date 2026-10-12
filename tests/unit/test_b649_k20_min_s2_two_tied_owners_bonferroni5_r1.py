"""Focused two-owner degree certificates, preservation and non-equivalent mutations."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from functools import cache
from itertools import combinations
from math import comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_two_tied_owners_bonferroni5_r1 as x

A, B = x.OWNER_SOURCES
EXPECTED = {
    A: (808, 7560, 313282914, 313389376, 2358, [22, 21, 21, 19, 19, 8]),
    B: (814, 7602, 313282956, 313388988, 2360, [22, 21, 21, 21, 18, 8]),
}
FINAL_OWNERS = ["66665555554421100000"]


@pytest.fixture(scope="module")
def authority() -> x.Authority:
    return x.load_authority()


@pytest.fixture(scope="module")
def result(authority: x.Authority) -> dict[str, object]:
    return x.compute_result(authority)


def proof_for(pid: str, auth: x.Authority) -> dict[str, object]:
    return x.object_row(x.rows(auth.r30["GROUP_ATTEMPTS"])[x.OWNER_SOURCES[pid][1]])


def test_immutable_base_and_transitive_source_identity(authority: x.Authority) -> None:
    assert x.chase.git("rev-parse", f"{x.BASE_HEAD}^{{tree}}").decode().strip() == x.BASE_TREE
    assert x.integration.pinned(x.BASE_HEAD, x.previous.RESULT_FILENAME, x.BASE_RESULT_SHA256) == (
        authority.sealed
    )
    for relative, expected in authority.provenance.items():
        blob = x.chase.git("show", f"{x.BASE_HEAD}:{relative}")
        assert (x.chase.ROOT / relative).read_bytes() == blob
        assert hashlib.sha256(blob).hexdigest() == expected
    assert (
        x.integration.family(
            authority.ledger, authority.inherited.inherited.inherited.inherited.inherited.inherited
        )
        == authority.sealed["FINAL_FAMILY"]
    )


def test_predecessor_source_tampering_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    target, original = Path(x.previous.__file__ or "").resolve(), Path.read_bytes

    def changed(path: Path) -> bytes:
        return original(path) + (b"\n# changed\n" if path == target else b"")

    x.load_authority.cache_clear()
    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", changed)
        with pytest.raises(AssertionError, match="source identity"):
            x.load_authority()


@pytest.mark.parametrize(
    ("triples", "missing", "expected"),
    [
        ((), (), 0),
        (((0, 1, 2),), (), 7),
        (((0, 1, 2),), ((3, 4),), 7),
        (((0, 1, 2),), ((0, 3),), 0),
        (((0, 1, 2), (2, 3, 4)), (), 28),
        (((0, 1, 2), (2, 3, 4)), ((0, 3),), 0),
    ],
)
def test_inherited_s5_identity_and_double_triple_weight(
    triples: tuple[x.identity.Support, ...], missing: tuple[x.identity.Pair, ...], expected: int
) -> None:
    edges = set(combinations(range(5), 2)) - set(missing)
    profile = x.identity.previous.local_profile(5, edges, triples)
    labels = [mask for mask, count in enumerate(profile) if mask for _ in range(count)]
    # Bounded distinct-label oracle for these six cases, no official-outcome enumeration.
    exact = 7 * sum(
        sum(m.bit_count() for m in q) >= 15
        and all(sum(bool(m & (1 << v)) for m in q) >= 3 for v in range(5))
        for q in combinations(labels, 7)
    )
    common, n2 = x.identity.s5_counts(tuple(range(5)), edges, triples)
    assert x.identity.s5_identity_value(common, n2) == exact == expected


def assert_caps() -> None:
    assert len({tuple(map(int, pid)) for pid in EXPECTED}) == 2
    for pid, (common, s5, _fifth, _lower, _j, h) in EXPECTED.items():
        cap = x.degree_s5_cap(pid)
        assert cap["D"] == list(map(int, pid))
        assert cap["G"] == [6 + v for v in map(int, pid)]
        assert [cap[k] for k in ("COMMON_PAIR_SUM_CAP", "N_2T_CAP", "S5_CAP")] == (
            [common, 136, s5]
        )
        assert [x.rows(raw)[5] for raw in x.rows(cap["THRESHOLD_CAPS"])] == h


@pytest.mark.parametrize("pid", EXPECTED)
def test_two_degree_sequences_and_independent_hk_optimization(pid: str) -> None:
    assert_caps()
    d = tuple(map(int, pid))

    @cache
    def visit(k: int, remaining: int, above: int) -> int:
        if k == 0:
            return 0 if remaining == 0 else -(10**9)
        high = [v for v in d if v >= k]
        low = [v for v in d if 0 < v < k]
        return max(
            (
                count * comb(k + 4, 2) + visit(k - 1, remaining - count, above + count)
                for count in range(remaining + 1)
                if 3 * (above + count) <= sum(high)
                and (len(high) >= 3 or above + count == 0)
                and all(above + count <= 22 - v for v in low)
            ),
            default=-(10**9),
        )

    cap = x.degree_s5_cap(d)
    assert visit(6, 22, 0) == cap["COMMON_PAIR_SUM_CAP"]
    assert sum(comb(v, 2) for v in d) == cap["N_2T_CAP"] == 136
    assert x.degree_s5_cap(tuple(reversed(d))) == cap


def test_fifth_order_bonferroni_for_all_winner_multiplicities() -> None:
    proof = x.identity.bonferroni_check()
    assert proof["R_CAP"] == comb(7, 2) // comb(3, 2) == 7
    for r in range(8):
        rhs = sum((-1) ** (k + 1) * comb(r, k) for k in range(1, 6))
        assert rhs >= int(r > 0)
        assert x.rows(x.rows(proof["TABLE"])[r]) == [r, rhs, int(r > 0), rhs - int(r > 0)]


def test_exact_integer_rounding_all_seven_residues() -> None:
    for s4 in range(292000, 292007):
        fourth, fifth = x.moment_bounds(5171904, s4, 7560)
        rational = x.event.K20_S1 - x.event.K20_S2 + 5171904 - Fraction(4 * s4, 7)
        assert fourth == -(-rational.numerator // rational.denominator)
        assert 0 <= fourth - rational < 1
        assert fifth == x.event.K20_S1 - x.event.K20_S2 + 5171904 - s4 + 7560


def assert_adoption(authority: x.Authority) -> None:
    for pid, (_common, s5, fifth, lower, j, _h) in EXPECTED.items():
        row, proof = authority.ledger[pid], proof_for(pid, authority)
        cert = x.owner_certificate(pid, row, proof)
        old = x.split.route_b_terms(x.split.profile_values(pid), row.cap, row.s4_base)
        new = x.rows(cert["ALL_T_TERMS"])
        assert new[:-1] == [list(t) for t in old[:-1]]
        assert x.rows(new[-1])[2:] == list(old[-1][2:])
        assert cert["OLD_T264_BOUND"] == 313398144
        assert cert["BONFERRONI5_T264_BOUND"] == cert["NEW_T264_BOUND"] == fifth
        assert cert["CERTIFIED_PROFILE_BOUND"] == cert["RETAINED_LOWER_T_MAX"] == lower
        assert cert["RETAINED_LOWER_T_COUNT"] == 242
        assert cert["RETAINED_TERMS_SHA256"] == x.digest(old[:-1])
        assert [x.rows(t)[0] for t in new] == list(range(22, 265))
        assert cert["W"] == 832 and cert["J"] == j
        assert cert["B"] == sum(v * (4 + v) for v in map(int, pid)) == 602
        assert cert["A_MAX"] == 200
        assert cert["EXISTING_S4_FLOOR"] == 286510
        assert len(new) == 243
        assert cert["CAP_SOURCE"] == row.source and cert["CAP_SOURCE_IDENTITY"] == proof
        assert x.integration.text(cert["ORIGINAL_CAP_SOURCE"]).endswith(
            f"GROUP_ATTEMPTS[{x.OWNER_SOURCES[pid][1]}]"
        )
        assert cert["NEW_T264_BOUND"] == min(
            old[-1][1], x.event.K20_S1 - x.event.K20_S2 + old[-1][5] - old[-1][4] + s5
        )
        # Independently check every original t rounding, not just the load-bearing cap.
        for _t, bound, _k, _a, s4, s3 in old:
            exact = x.event.K20_S1 - x.event.K20_S2 + s3 - Fraction(4 * s4, 7)
            assert bound == -(-exact.numerator // exact.denominator)


def test_two_certificates_all_t_preservation_and_max_not_sum(authority: x.Authority) -> None:
    assert_adoption(authority)


@pytest.mark.parametrize("pid", EXPECTED)
def test_cap_authority_identity_and_tampering(pid: str, authority: x.Authority) -> None:
    row, proof = authority.ledger[pid], proof_for(pid, authority)
    x.check_cap(pid, row, proof)
    for bad in (
        replace(row, cap=263),
        replace(row, cap=264.0),
        replace(row, source="other"),
        replace(row, s4_base=row.s4_base + 1),
    ):
        with pytest.raises(AssertionError, match="cap-source identity"):
            x.check_cap(pid, bad, proof)
    with pytest.raises(AssertionError, match="sealed ledger"):
        x.owner_certificate(pid, replace(row, bound=row.bound + 1), proof)
    for key in (
        "ATTEMPT_INDEX",
        "PROFILE_IDS",
        "STATUS",
        "CERTIFICATE_KIND",
        "ROUTE",
        "WEDGE_COUNT",
        "TARGET_TRIANGLE_CAP",
        "REFUTED_GRAPH_TRIANGLE_COUNT",
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND",
        "OPEN_WEDGE_CEILING_REFUTED",
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND",
    ):
        with pytest.raises(AssertionError, match="cap-source identity"):
            x.check_cap(pid, row, {**proof, key: None})


def assert_family(authority: x.Authority) -> None:
    result = x.compute_result(authority)
    start, final = x.object_row(result["START_FAMILY"]), x.object_row(result["FINAL_FAMILY"])
    assert start["FAMILY_UB"] == 313398144 and start["OWNER_IDS"] == sorted(EXPECTED)
    assert final["FAMILY_UB"] == 313397860 and final["OWNER_IDS"] == FINAL_OWNERS
    assert result["REMAINING_GAP"] == 133972
    coverage = x.object_row(final["COVERAGE"])
    assert start["COVERAGE"] == coverage
    assert [
        coverage[k]
        for k in (
            "ADMISSIBLE_PROFILE_COUNT",
            "RESOLVED_ROW_COUNT",
            "UNDER_CURSOR_PROFILE_COUNT",
            "UNCOVERED_PROFILE_COUNT",
        )
    ] == ([4844, 4647, 197, 0])
    assert (start["CURSOR_ID"], start["CURSOR_BOUND"]) == (
        final["CURSOR_ID"],
        final["CURSOR_BOUND"],
    )
    assert result["OTHER_PROFILE_ROWS_UNCHANGED"] == 4645
    assert result["OTHER_ROWS_SHA256"] == x.digest(
        {pid: row.bound for pid, row in authority.ledger.items() if pid not in EXPECTED}
    )
    assert result["INHERITED_CERTIFICATES"] == authority.sealed["INHERITED_CERTIFICATES"]
    assert result["PREDECESSOR_OWNER_CERTIFICATES"] == authority.sealed["OWNER_CERTIFICATES"]
    assert (
        result["EARLIER_OWNER_CERTIFICATES"] == authority.sealed["PREDECESSOR_OWNER_CERTIFICATES"]
    )
    assert result["S5_IDENTITY"] == authority.sealed["S5_IDENTITY"]
    assert x.object_row(result["S5_IDENTITY"])["TWO_TRIPLE_K5_WEIGHT"] == 28
    assert result["STS13_ROW_UNCHANGED"] is True
    ledger = dict(authority.ledger)
    for pid in EXPECTED:
        before = ledger[pid]
        cert = x.object_row(x.object_row(result["OWNER_CERTIFICATES"])[pid])
        ledger = x.integration.install(
            ledger, pid, x.integer(cert["CERTIFIED_PROFILE_BOUND"]), "test"
        )
        assert replace(ledger[pid], source=before.source, bound=before.bound) == before
        if pid != B:
            assert x.chase.family_state(ledger)[0] == 313398144
    for pid in ledger:
        if pid not in EXPECTED:
            assert ledger[pid] == authority.ledger[pid]
    bounds = {pid: row.bound for pid, row in ledger.items()}
    bounds[x.chase.prior.CURSOR_ID] = x.chase.prior.CURSOR_BOUND
    maximum = max(bounds.values())
    assert maximum == final["FAMILY_UB"]
    assert sorted(pid for pid, b in bounds.items() if b == maximum) == FINAL_OWNERS


def test_complete_4844_coverage_all_tied_owners_and_other_rows_preserved(
    authority: x.Authority,
) -> None:
    assert_family(authority)


def test_p2_sts13_and_recorded_owner_witnesses(
    authority: x.Authority, result: dict[str, object]
) -> None:
    sound = x.object_row(result["WITNESS_SOUNDNESS"])
    assert sound["STATUS"] == "PASS"
    witnesses = x.object_row(sound["WITNESSES"])
    recorded = {pid for pid in EXPECTED if authority.ledger[pid].realization is not None}
    assert set(witnesses) == {*recorded, "P2", "STS13"}
    assert sound["OWNER_REALIZATION_STATUS"] == {
        pid: "PASS" if pid in recorded else "NONE_RECORDED" for pid in EXPECTED
    }
    assert result["INHERITED_WITNESS_SOUNDNESS"] == authority.sealed["WITNESS_SOUNDNESS"]
    for name, raw in witnesses.items():
        w = x.object_row(raw)
        assert w["STATUS"] == "PASS" and x.integer(w["EXACT_S5"]) <= x.integer(w["S5_CAP"])
        if name in EXPECTED:
            assert w["PROFILE_ID"] == name and x.integer(w["TRIANGLES"]) <= 264
            assert x.integer(w["EXACT_MOMENT_UPPER_BOUND"]) <= EXPECTED[name][3]
    assert x.object_row(sound["STS13_EXACT_UNION"])["EXACT_ANY_PRIZE_UNION"] == 313263867


def test_witness_tripwire_rejects_unsound_owner_bound(authority: x.Authority) -> None:
    # Exercise certificate applicability using the existing legal P2 supports.
    # Reuse the inherited legal witnesses; no new realization is installed.
    seen = x.motif.realization_check(*x.split.witness_supports("P2"))
    pid, t = x.integration.text(seen["PROFILE_ID"]), x.integer(seen["TRIANGLES"])
    s4 = x.integer(seen["EXACT_S4_FROM_PINNED_LOCAL_TABLE"])
    row = x.Row(313500000, t, s4, "test")
    ledger = {**authority.ledger, pid: row}
    cert = {
        "ALL_T_TERMS": [[t, row.bound]],
        "EXISTING_S4_FLOOR": s4,
        "CERTIFIED_PROFILE_BOUND": row.bound,
    }
    x.witness_soundness(ledger, {pid: cert})
    cert["CERTIFIED_PROFILE_BOUND"] = 0
    with pytest.raises(AssertionError, match="legal owner witness"):
        x.witness_soundness(ledger, {pid: cert})


@pytest.mark.parametrize("first", ["motif", "successor"])
def test_historical_import_orders_in_fresh_process(first: str) -> None:
    predecessor, successor = x.motif.__name__, x.__name__
    order = (predecessor, successor) if first == "motif" else (successor, predecessor)
    script = (
        "import importlib; "
        f"importlib.import_module({order[0]!r}); importlib.import_module({order[1]!r}); "
        f"x=importlib.import_module({successor!r}); a=x.load_authority(); "
        "assert a.sealed['FINAL_COMPLETE_FAMILY_UB']==313398144; "
        "assert len(x.motif.historical_provenance())==27"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=x.chase.ROOT,
        env={**os.environ, "PYTHONPATH": str(x.chase.ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_certificate_result_and_lower_t_tampering_rejected(
    authority: x.Authority, result: dict[str, object]
) -> None:
    for pid in EXPECTED:
        row, proof = authority.ledger[pid], proof_for(pid, authority)
        cert = x.owner_certificate(pid, row, proof)
        for key in ("NEW_T264_BOUND", "CERTIFIED_PROFILE_BOUND", "EXISTING_S4_FLOOR"):
            with pytest.raises(AssertionError, match="tampered Bonferroni5"):
                x.verify_certificate({**cert, key: x.integer(cert[key]) + 1}, pid, row, proof)
        for key, field in (("DEGREE_S5_PROOF", "S5_CAP"), ("CAP_SOURCE_IDENTITY", "STATUS")):
            bad = copy.deepcopy(cert)
            x.object_row(bad[key])[field] = 0
            with pytest.raises(AssertionError, match="tampered Bonferroni5"):
                x.verify_certificate(bad, pid, row, proof)
        x.rows(x.rows(cert["ALL_T_TERMS"])[0])[1] = 0
        with pytest.raises(AssertionError, match="tampered Bonferroni5"):
            x.verify_certificate(cert, pid, row, proof)
    with pytest.raises(AssertionError, match="tampered immutable"):
        x.verify_result({**result, "FINAL_COMPLETE_FAMILY_UB": 313280310}, authority)
    x.verify_result(result, authority)
    if x.RESULT_PATH.exists():
        assert json.loads(x.RESULT_PATH.read_text()) == result
        with pytest.raises(AssertionError, match="already exists"):
            x.main()


MUTATIONS = {
    "s5_wrong_sign": ("identity", "s5_identity_value", "+ 2 * n2", "- 2 * n2"),
    "double_triple_weight14": ("identity", "s5_identity_value", "+ 2 * n2", "+ 0 * n2"),
    "copy_owner_a_degrees": (
        "caps",
        "degree_s5_cap",
        "d = split.profile_values(profile)",
        f"d = split.profile_values({A!r})",
    ),
    "drop_intersecting_pair_correction": (
        "caps",
        "degree_s5_cap",
        "common_cap + 2 * n2_cap",
        "common_cap",
    ),
    "wrong_high_incidence_divisor": ("caps", "degree_s5_cap", "sum(high) // 3", "sum(high) // 2"),
    "ignore_low_vertex_constraint": ("caps", "degree_s5_cap", "22 - max(low, default=0)", "22"),
    "wrong_s5_special_weight": ("caps", "degree_s5_cap", "7 * (common_cap", "6 * (common_cap"),
    "round_fourth_down": (
        "rounding",
        "moment_bounds",
        "-(-exact.numerator // exact.denominator)",
        "exact.numerator // exact.denominator",
    ),
    "sum_overlapping_credits": (
        "adoption",
        "owner_certificate",
        "min(old_bound, fifth)",
        "min(old_bound, fifth) - (4 * s4) // 7",
    ),
    "take_weaker_bound": (
        "adoption",
        "owner_certificate",
        "min(old_bound, fifth)",
        "max(old_bound, fifth)",
    ),
    "drop_lower_t": ("adoption", "owner_certificate", "[*lower, (t, new_bound", "[(t, new_bound"),
    "cap_term_as_profile_max": (
        "adoption",
        "owner_certificate",
        "max(term[1] for term in terms)",
        "new_bound",
    ),
    "sum_profile_terms": (
        "adoption",
        "owner_certificate",
        "max(term[1] for term in terms)",
        "sum(term[1] for term in terms)",
    ),
    "ignore_cap_source": (
        "source",
        "check_cap",
        'row.source != f"{nb.RESULT_FILENAME}:NB_CERTIFICATES[{index}]"',
        "False",
    ),
    "ignore_witness_bound": (
        "witness",
        "witness_soundness",
        'witness_bound > integer(cert["CERTIFIED_PROFILE_BOUND"])',
        "False",
    ),
    "omit_second_tied_owner": (
        "family",
        "compute_result",
        "in OWNER_SOURCES.items():",
        "in list(OWNER_SOURCES.items())[:-1]:",
    ),
    "omit_first_tied_owner": (
        "family",
        "compute_result",
        "in OWNER_SOURCES.items():",
        "in list(OWNER_SOURCES.items())[1:]:",
    ),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_targeted_non_equivalent_mutations_killed(
    name: str, authority: x.Authority, monkeypatch: pytest.MonkeyPatch
) -> None:
    guard_name, function, old, new = MUTATIONS[name]
    target = x.identity if guard_name == "identity" else x
    original = cast(Callable[..., object], getattr(target, function))
    source = inspect.getsource(original)
    assert source.count(old) == 1
    namespace: dict[str, object] = dict(original.__globals__)
    exec(compile(source.replace(old, new), f"<mutation:{name}>", "exec"), namespace)

    def guard() -> None:
        if guard_name == "identity":
            test_inherited_s5_identity_and_double_triple_weight(((0, 1, 2), (2, 3, 4)), (), 28)
        elif guard_name == "caps":
            assert_caps()
        elif guard_name == "rounding":
            test_exact_integer_rounding_all_seven_residues()
        elif guard_name == "source":
            test_cap_authority_identity_and_tampering(A, authority)
        elif guard_name == "witness":
            test_witness_tripwire_rejects_unsound_owner_bound(authority)
        elif guard_name == "family":
            assert_family(authority)
        else:
            assert_adoption(authority)

    guard()
    with monkeypatch.context() as patch:
        patch.setattr(target, function, namespace[function])
        with pytest.raises((AssertionError, pytest.fail.Exception)):
            guard()
    guard()


def test_incomplete_or_extra_profile_coverage_rejected(authority: x.Authority) -> None:
    family_auth = authority.inherited.inherited.inherited.inherited.inherited.inherited
    missing = dict(authority.ledger)
    del missing[A]
    with pytest.raises(AssertionError):
        x.integration.family(missing, family_auth)
    extra = {**authority.ledger, "00000000000000000000": authority.ledger[A]}
    with pytest.raises(AssertionError):
        x.integration.family(extra, family_auth)


def test_pinned_result_bytes_and_wrong_base_tree_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    path = x.chase.ROOT / x.chase.prior.RESULT_DIRECTORY / x.previous.RESULT_FILENAME
    original = Path.read_bytes

    def changed(target: Path) -> bytes:
        return original(target) + (b" " if target == path else b"")

    x.load_authority.cache_clear()
    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", changed)
        with pytest.raises(AssertionError, match="in-tree result differs"):
            x.load_authority()
    with monkeypatch.context() as patch:
        patch.setattr(x, "BASE_TREE", "0" * 40)
        with pytest.raises(AssertionError, match="base tree mismatch"):
            x.load_authority()
    x.load_authority.cache_clear()
