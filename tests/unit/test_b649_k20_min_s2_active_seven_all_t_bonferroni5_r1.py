"""All-t semantic guards, mixed motif scope, full coverage and mutation rejection."""

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

from lottolab.research import b649_k20_min_s2_active_seven_all_t_bonferroni5_r1 as x

EXPECTED = {
    "66555555555333000000": (313274066, 747, 129, 7035),
    "66555555554442000000": (313273919, 726, 129, 6888),
    "65555555555532000000": (313273982, 735, 129, 6951),
    "66655555555421100000": (313276782, 783, 132, 7329),
    "66655555555332000000": (313276824, 789, 132, 7371),
    "66666555555311100000": (313282011, 826, 138, 7714),
    "66555555555431100000": (313273254, 728, 129, 6902),
}
MIXED = "66666555555311100000"


@pytest.fixture(scope="module")
def authority() -> x.Authority:
    return x.load_authority()


@pytest.fixture(scope="module")
def result(authority: x.Authority) -> dict[str, object]:
    return x.compute_result(authority)


def test_immutable_authority_and_exact_latest_seven(authority: x.Authority) -> None:
    assert x.BASE_HEAD == "8fa9c0e67f48aee7b8a51eb940eac565eeefecfe"
    assert x.chase.git("rev-parse", f"{x.BASE_HEAD}^{{tree}}").decode().strip() == x.BASE_TREE
    assert x.integration.pinned(x.BASE_HEAD, x.previous.RESULT_FILENAME, x.BASE_RESULT_SHA256) == (
        authority.sealed
    )
    for relative, expected in authority.provenance.items():
        blob = x.chase.git("show", f"{x.BASE_HEAD}:{relative}")
        assert (x.chase.ROOT / relative).read_bytes() == blob
        assert hashlib.sha256(blob).hexdigest() == expected
    assert (
        x.integration.family(authority.ledger, authority.family_authority)
        == (authority.sealed["FINAL_FAMILY"])
    )
    assert x.active_profiles(authority.ledger) == sorted(EXPECTED)
    assert len(authority.ledger) == 4647
    stale = authority.inherited.ledger
    assert sum(r.bound > x.chase.prior.CURSOR_BOUND for r in stale.values()) == 9
    with pytest.raises(AssertionError, match="latest seven"):
        x.compute_result(replace(authority, ledger=stale))


def assert_caps() -> None:
    for pid, (_bound, common, n2, s5) in EXPECTED.items():
        cap = x.degree_s5_cap(pid)
        assert cap["D"] == list(map(int, pid))
        assert cap["G"] == [6 + d for d in map(int, pid)]
        assert [cap[k] for k in ("COMMON_PAIR_SUM_CAP", "N_2T_CAP", "S5_CAP")] == ([common, n2, s5])
        assert cap["S5_CAP"] == 7 * (common + 2 * n2)
    binding = x.degree_s5_cap("66666666664200000000")
    assert [x.rows(r)[5] for r in x.rows(binding["THRESHOLD_CAPS"])] == ([22, 22, 20, 20, 18, 18])
    assert binding["S5_CAP"] == 8470
    two_high = x.degree_s5_cap("66555555555540000000")
    assert x.rows(x.rows(two_high["THRESHOLD_CAPS"])[-1])[5] == 0


@pytest.mark.parametrize("pid", EXPECTED)
def test_independent_degree_cap_optimization(pid: str) -> None:
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
    assert sum(d) == 66 and sum(comb(v, 2) for v in d) == cap["N_2T_CAP"]
    assert x.degree_s5_cap(tuple(reversed(d))) == cap


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
def test_independent_s5_identity_oracle(
    triples: tuple[tuple[int, ...], ...], missing: tuple[tuple[int, int], ...], expected: int
) -> None:
    edges = set(combinations(range(5), 2)) - set(missing)
    profile = x.identity.previous.local_profile(5, edges, triples)
    labels = [mask for mask, count in enumerate(profile) if mask for _ in range(count)]
    # Six bounded local label cases, independent of the S5 formula.
    exact = 7 * sum(
        sum(m.bit_count() for m in q) >= 15
        and all(sum(bool(m & (1 << v)) for m in q) >= 3 for v in range(5))
        for q in combinations(labels, 7)
    )
    common, n2 = x.identity.s5_counts(tuple(range(5)), edges, triples)
    assert x.identity.s5_identity_value(common, n2) == exact == expected


def test_bonferroni_every_winner_multiplicity() -> None:
    proof = x.identity.bonferroni_check()
    assert proof["R_CAP"] == 7
    for r in range(8):
        rhs = sum((-1) ** (k + 1) * comb(r, k) for k in range(1, 6))
        assert rhs >= int(r > 0)
        assert x.rows(x.rows(proof["TABLE"])[r]) == [r, rhs, int(r > 0), rhs - int(r > 0)]


def test_rounding_all_seven_residues() -> None:
    for s4 in range(292000, 292007):
        fourth, fifth = x.moment_bounds(5171904, s4, 7560)
        exact = x.event.K20_S1 - x.event.K20_S2 + 5171904 - Fraction(4 * s4, 7)
        assert fourth == -(-exact.numerator // exact.denominator)
        assert 0 <= fourth - exact < 1
        assert fifth == x.event.K20_S1 - x.event.K20_S2 + 5171904 - s4 + 7560


def assert_terms(auth: x.Authority) -> None:
    changes: list[tuple[str, int, int]] = []
    for pid, (expected, _common, _n2, s5) in EXPECTED.items():
        old = x.authoritative_terms(auth, pid)
        cert = x.profile_certificate(auth, pid)
        new = x.rows(cert["ALL_T_TERMS"])
        assert cert["CERTIFIED_PROFILE_BOUND"] == expected
        assert cert["AUTHORITATIVE_TERMS"] == [list(t) for t in old]
        assert cert["AUTHORITATIVE_TERMS_SHA256"] == x.digest(old)
        assert cert["LEGAL_T_COUNT"] == len(new) == auth.ledger[pid].cap - 21
        assert [x.rows(t)[0] for t in new] == list(range(22, auth.ledger[pid].cap + 1))
        for before, raw in zip(old, new, strict=True):
            after = x.rows(raw)
            t, bound, _k, _a, s4, s3 = before
            checked_s3, fourth = x.chase.r20.bound_from_cap(x.split.profile_values(pid), t, s4)
            fifth = x.event.K20_S1 - x.event.K20_S2 + s3 - s4 + s5
            assert fourth == bound and checked_s3 == s3
            assert after == [t, min(bound, fifth), *before[2:]]
            changes.extend(
                (pid, t, field)
                for field, (a, b) in enumerate(zip(before, after, strict=True))
                if a != b
            )
        assert cert["CERTIFIED_PROFILE_BOUND"] == max(x.integer(x.rows(t)[1]) for t in new)
        assert cert["CHANGED_T_TERM_COUNT"] == sum(
            before[1] != x.rows(after)[1] for before, after in zip(old, new, strict=True)
        )
    assert len(changes) == 436 and {field for _pid, _t, field in changes} == {1}
    assert {pid for pid, _t, _field in changes} == set(EXPECTED)


def test_all_legal_t_recompute_and_only_necessary_bound_fields(authority: x.Authority) -> None:
    assert_terms(authority)


def assert_mixed(auth: x.Authority) -> None:
    old = x.authoritative_terms(auth, MIXED)
    baseline = x.split.route_b_terms(x.split.profile_values(MIXED), 264, auth.ledger[MIXED].s4_base)
    assert old[:-1] == baseline[:-1]
    assert old[-2] == (263, 313394852, 483, 202, 281295, 5165552)
    assert old[-1] == (264, 313390632, 490, 202, 309456, 5177424)
    cert = x.profile_certificate(auth, MIXED)
    by_t = {x.integer(x.rows(t)[0]): x.rows(t) for t in x.rows(cert["ALL_T_TERMS"])}
    assert by_t[263][4] == 281295 and by_t[264][4] == 309456
    assert by_t[263][1] == 313282011 and by_t[264][1] == 313265722
    assert cert["ARGMAX_T"] == [263]
    assert cert["CERTIFIED_PROFILE_BOUND"] == 313282011
    assert cert["CERTIFIED_PROFILE_BOUND"] != 313265722


def test_negative_regression_cap_only_shortcut_and_motif_floor_spill(
    authority: x.Authority,
) -> None:
    assert_mixed(authority)
    # Strengthening a t=263 floor with the cap-only value must be rejected.
    sealed = copy.deepcopy(authority.sealed)
    cert = x.object_row(x.object_row(sealed["INHERITED_CERTIFICATES"])["T264_OWNER_CERTIFICATE"])
    x.rows(x.rows(cert["ALL_T_TERMS"])[-2])[4] = 309456
    with pytest.raises(AssertionError, match="mixed motif S4 floor scope"):
        x.authoritative_terms(replace(authority, sealed=sealed), MIXED)


def assert_family(auth: x.Authority) -> None:
    result = x.compute_result(auth)
    start, final = x.object_row(result["START_FAMILY"]), x.object_row(result["FINAL_FAMILY"])
    assert start["FAMILY_UB"] == 313395164
    assert final["FAMILY_UB"] == result["FINAL_COMPLETE_FAMILY_UB"] == 313394584
    assert final["OWNER_IDS"] == ["66544333333333332222"]
    assert final["NEXT_COMPETING_BOUND"] == 313393084
    assert final["CURRENT_INCUMBENT"] == 313263888
    assert result["REMAINING_GAP"] == 130696
    assert result["CHANGED_T_TERM_COUNT"] == 436
    assert result["SEVEN_NEW_PROFILE_BOUNDS"] == {p: v[0] for p, v in EXPECTED.items()}
    assert result["OTHER_PROFILE_ROWS_UNCHANGED"] == 4640
    assert start["COVERAGE"] == final["COVERAGE"]
    coverage = x.object_row(final["COVERAGE"])
    assert [
        coverage[k]
        for k in (
            "ADMISSIBLE_PROFILE_COUNT",
            "RESOLVED_ROW_COUNT",
            "UNDER_CURSOR_PROFILE_COUNT",
            "UNCOVERED_PROFILE_COUNT",
        )
    ] == [4844, 4647, 197, 0]
    assert (start["CURSOR_ID"], start["CURSOR_BOUND"]) == (
        final["CURSOR_ID"],
        final["CURSOR_BOUND"],
    )
    ledger = dict(auth.ledger)
    for pid, expected in EXPECTED.items():
        before = ledger[pid]
        ledger = x.integration.install(ledger, pid, expected[0], "test")
        assert replace(ledger[pid], source=before.source, bound=before.bound) == before
    assert result["OTHER_ROWS_FULL_SHA256"] == x.digest(
        [
            [p, r.bound, r.cap, r.s4_base, r.source, r.realization]
            for p, r in sorted(auth.ledger.items())
            if p not in EXPECTED
        ]
    )
    assert all(ledger[p] == auth.ledger[p] for p in ledger if p not in EXPECTED)
    full = {pid: row.bound for pid, row in ledger.items()}
    full[x.chase.prior.CURSOR_ID] = x.chase.prior.CURSOR_BOUND
    maximum = max(full.values())
    assert maximum == final["FAMILY_UB"]
    assert sorted(pid for pid, bound in full.items() if bound == maximum) == final["OWNER_IDS"]


def test_complete_family_and_all_preserved_authorities(authority: x.Authority) -> None:
    assert_family(authority)
    result = x.compute_result(authority)
    for key in (
        "INHERITED_CERTIFICATES",
        "PRESERVED_COMPETING_PROFILE_CERTIFICATES",
        "PRESERVED_OWNER_CERTIFICATE",
        "PREDECESSOR_OWNER_CERTIFICATES",
        "EARLIER_OWNER_CERTIFICATES",
        "OLDER_OWNER_CERTIFICATES",
        "STS13_CERTIFICATE_SHA256",
    ):
        assert result[key] == authority.sealed[key]
    assert result["PRIOR_OWNER_CERTIFICATES"] == authority.sealed["PROFILE_CERTIFICATES"]
    for pid in x.previous.PROFILE_SOURCES:
        row = authority.ledger[pid]
        assert row.bound == 313386188
        assert row.source == f"{x.previous.RESULT_FILENAME}:PROFILE_CERTIFICATES[{pid}]"
    assert authority.ledger[x.previous.PRESERVED_OWNER].bound == 313388704
    assert result["STS13_ROW_UNCHANGED"] is True


def test_p2_sts13_and_every_recorded_witness(
    authority: x.Authority, result: dict[str, object]
) -> None:
    sound = x.object_row(result["WITNESS_SOUNDNESS"])
    witnesses = x.object_row(sound["WITNESSES"])
    assert sound["STATUS"] == "PASS"
    recorded = {p for p, r in authority.ledger.items() if r.realization is not None}
    assert set(witnesses) == {*recorded, "P2", "STS13"}
    assert MIXED in recorded
    for raw in witnesses.values():
        w = x.object_row(raw)
        assert w["STATUS"] == "PASS" and x.integer(w["EXACT_S5"]) <= x.integer(w["S5_CAP"])
    assert x.object_row(sound["STS13_EXACT_UNION"])["EXACT_ANY_PRIZE_UNION"] == 313263867
    assert result["INHERITED_WITNESS_SOUNDNESS"] == authority.sealed["WITNESS_SOUNDNESS"]
    assert x.object_row(result["S5_IDENTITY"])["TWO_TRIPLE_K5_WEIGHT"] == 28


def witness_guard(auth: x.Authority) -> None:
    seen = x.motif.realization_check(*x.split.witness_supports("P2"))
    pid, t = x.integration.text(seen["PROFILE_ID"]), x.integer(seen["TRIANGLES"])
    floor = x.integer(seen["EXACT_S4_FROM_PINNED_LOCAL_TABLE"])
    cert: dict[str, object] = {
        "ALL_T_TERMS": [[t, 313500000, 0, 0, floor, 0]],
        "CERTIFIED_PROFILE_BOUND": 313500000,
    }
    x.witness_soundness(auth.ledger, {pid: cert})
    cert["CERTIFIED_PROFILE_BOUND"] = 0
    with pytest.raises(AssertionError, match="legal witness"):
        x.witness_soundness(auth.ledger, {pid: cert})


def test_witness_bound_tripwire(authority: x.Authority) -> None:
    witness_guard(authority)


def test_certificate_and_result_tampering(
    authority: x.Authority, result: dict[str, object]
) -> None:
    for pid in EXPECTED:
        cert = x.profile_certificate(authority, pid)
        for key in ("CERTIFIED_PROFILE_BOUND", "LEGAL_T_COUNT", "CHANGED_T_TERM_COUNT"):
            with pytest.raises(AssertionError, match="tampered all-t"):
                x.verify_certificate({**cert, key: x.integer(cert[key]) + 1}, authority, pid)
        for key in ("ALL_T_TERMS", "AUTHORITATIVE_TERMS"):
            bad = copy.deepcopy(cert)
            x.rows(x.rows(bad[key])[0])[1] = 0
            with pytest.raises(AssertionError, match="tampered all-t"):
                x.verify_certificate(bad, authority, pid)
        bad = copy.deepcopy(cert)
        x.object_row(bad["DEGREE_S5_PROOF"])["S5_CAP"] = 0
        with pytest.raises(AssertionError, match="tampered all-t"):
            x.verify_certificate(bad, authority, pid)
    for key in ("FINAL_COMPLETE_FAMILY_UB", "CHANGED_T_TERM_COUNT", "ACTIVE_SEVEN_PROFILE_IDS"):
        with pytest.raises(AssertionError, match="tampered immutable"):
            x.verify_result({**result, key: None}, authority)
    x.verify_result(result, authority)


def source_guard(auth: x.Authority) -> None:
    pid = next(iter(x.NB_SOURCES))
    ledger = {**auth.ledger, pid: replace(auth.ledger[pid], source="stale")}
    with pytest.raises(AssertionError, match="NB cap-source identity"):
        x.authoritative_terms(replace(auth, ledger=ledger), pid)


def test_cap_source_and_incomplete_coverage_rejected(authority: x.Authority) -> None:
    source_guard(authority)
    for pid in EXPECTED:
        ledger = dict(authority.ledger)
        del ledger[pid]
        with pytest.raises(AssertionError):
            x.integration.family(ledger, authority.family_authority)
        with pytest.raises(AssertionError, match="latest seven"):
            x.compute_result(replace(authority, ledger=ledger))
    extra = {**authority.ledger, "00000000000000000000": authority.ledger[MIXED]}
    with pytest.raises(AssertionError):
        x.integration.family(extra, authority.family_authority)


@pytest.mark.parametrize("kind", ["source", "result", "tree"])
def test_pinned_authority_tampering(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    path = (
        Path(x.previous.__file__ or "").resolve()
        if kind == "source"
        else x.chase.ROOT / x.chase.prior.RESULT_DIRECTORY / x.previous.RESULT_FILENAME
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


@pytest.mark.parametrize("first", ["motif", "successor"])
def test_historical_fresh_process_import_orders(first: str) -> None:
    order = (x.motif.__name__, x.__name__) if first == "motif" else (x.__name__, x.motif.__name__)
    script = (
        "import importlib; "
        f"importlib.import_module({order[0]!r}); importlib.import_module({order[1]!r}); "
        f"x=importlib.import_module({x.__name__!r}); a=x.load_authority(); "
        "assert a.sealed['FINAL_COMPLETE_FAMILY_UB']==313395164; "
        "assert x.compute_result(a)['FINAL_COMPLETE_FAMILY_UB']==313394584; "
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


def test_cli_verify_and_exact_byte_replay(result: dict[str, object]) -> None:
    assert json.loads(x.RESULT_PATH.read_bytes()) == result
    assert x.RESULT_PATH.read_bytes() == x.integration.render(result).encode("utf-8")
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
    assert json.loads(run.stdout) == {
        "RESULT_REPLAY_STATUS": "PASS",
        "FINAL_COMPLETE_FAMILY_UB": 313394584,
        "REMAINING_GAP": 130696,
        "CHANGED_T_TERM_COUNT": 436,
    }


MUTATIONS = {
    "wrong_s5_sign": ("identity", "s5_identity_value", "+ 2 * n2", "- 2 * n2"),
    "double_triple_weight14": ("identity", "s5_identity_value", "+ 2 * n2", "+ 0 * n2"),
    "copy_other_degrees": (
        "caps",
        "degree_s5_cap",
        "d = split.profile_values(profile)",
        "d = split.profile_values('66665555554431000000')",
    ),
    "drop_n2_correction": (
        "caps",
        "degree_s5_cap",
        "common_cap + 2 * n2_cap",
        "common_cap",
    ),
    "wrong_incidence_divisor": (
        "caps",
        "degree_s5_cap",
        "sum(high) // 3",
        "sum(high) // 2",
    ),
    "ignore_low_vertices": (
        "caps",
        "degree_s5_cap",
        "22 - max(low, default=0)",
        "22",
    ),
    "forget_three_high_vertices": (
        "caps",
        "degree_s5_cap",
        "sum(high) // 3 if len(high) >= 3 else 0",
        "sum(high) // 3",
    ),
    "wrong_n2_cap": (
        "caps",
        "degree_s5_cap",
        "sum(comb(v, 2) for v in d)",
        "sum(comb(v, 3) for v in d)",
    ),
    "wrong_neighbour_offset": (
        "caps",
        "degree_s5_cap",
        "comb(4 + k, 2)",
        "comb(3 + k, 2)",
    ),
    "wrong_special_weight": (
        "caps",
        "degree_s5_cap",
        "7 * (common_cap",
        "6 * (common_cap",
    ),
    "round_fourth_down": (
        "rounding",
        "moment_bounds",
        "-(-exact.numerator // exact.denominator)",
        "exact.numerator // exact.denominator",
    ),
    "take_weaker_bound": (
        "terms",
        "profile_certificate",
        "min(old_bound, fifth)",
        "max(old_bound, fifth)",
    ),
    "add_overlapping_credits": (
        "terms",
        "profile_certificate",
        "min(old_bound, fifth)",
        "min(old_bound, fifth) - (4 * s4) // 7",
    ),
    "update_only_cap_t": (
        "terms",
        "profile_certificate",
        "min(old_bound, fifth)",
        "min(old_bound, fifth) if t == row.cap else old_bound",
    ),
    "spill_cap_s4_to_all_t": (
        "terms",
        "profile_certificate",
        "moment_bounds(s3, s4, s5)",
        "moment_bounds(s3, old[-1][4], s5)",
    ),
    "cap_only_profile_max": (
        "mixed",
        "profile_certificate",
        "max(term[1] for term in terms)",
        "terms[-1][1]",
    ),
    "sum_profile_envelope": (
        "terms",
        "profile_certificate",
        "max(term[1] for term in terms)",
        "sum(term[1] for term in terms)",
    ),
    "drop_lower_t": (
        "terms",
        "profile_certificate",
        "in old:",
        "in old[-1:]:",
    ),
    "mutate_non_bound_field": (
        "terms",
        "profile_certificate",
        "terms.append((t, bound, k, a, s4, s3))",
        "terms.append((t, bound, k + 1, a, s4, s3))",
    ),
    "ignore_nb_cap_source": (
        "source",
        "authoritative_terms",
        'row.source != f"{nb.RESULT_FILENAME}:NB_CERTIFICATES[{NB_SOURCES[pid]}]"',
        "False",
    ),
    "ignore_witness_envelope": (
        "witness",
        "witness_soundness",
        'witness_bound > integer(cert["CERTIFIED_PROFILE_BOUND"])',
        "False",
    ),
    "omit_seventh_profile": (
        "family",
        "compute_result",
        "for pid in recovered:",
        "for pid in recovered[:-1]:",
    ),
    "family_from_changed_profiles_only": (
        "family",
        "compute_result",
        "family = integration.family(final, auth.family_authority)",
        'family = {**integration.family(final, auth.family_authority), "FAMILY_UB": '
        'max(integer(object_row(c)["CERTIFIED_PROFILE_BOUND"]) for c in certs.values())}',
    ),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_non_equivalent_mutations_rejected(
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
            test_independent_s5_identity_oracle(((0, 1, 2), (2, 3, 4)), (), 28)
        elif guard_name == "caps":
            assert_caps()
        elif guard_name == "rounding":
            test_rounding_all_seven_residues()
        elif guard_name == "mixed":
            assert_mixed(authority)
        elif guard_name == "source":
            source_guard(authority)
        elif guard_name == "witness":
            witness_guard(authority)
        elif guard_name == "family":
            assert_family(authority)
        else:
            assert_terms(authority)

    guard()
    with monkeypatch.context() as patch:
        patch.setattr(target, function, namespace[function])
        with pytest.raises((AssertionError, pytest.fail.Exception)):
            guard()
    guard()
