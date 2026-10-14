"""Focused independent arithmetic, complete relaxation, mutation and Git-child checks."""

from __future__ import annotations

import copy
import json
import os
import subprocess
from collections import Counter
from fractions import Fraction
from itertools import combinations_with_replacement, product
from math import comb
from pathlib import Path

import pytest

from lottolab.research import b649_next_frontier_three_profile_bound_r1 as cert

IDS = ("66665555555421000000", "65555555555442000000", "66555555554433000000")
HISTOGRAMS = (
    {0: 6, 1: 1, 2: 1, 4: 1, 5: 7, 6: 4},
    {0: 6, 2: 1, 4: 2, 5: 10, 6: 1},
    {0: 6, 3: 2, 4: 2, 5: 8, 6: 2},
)


@pytest.fixture(scope="module")
def result():
    return cert.compute_result()


def hh(degrees):
    """Independent Havel-Hakimi, rather than the evaluator's edge inequalities."""
    d = sorted(degrees, reverse=True)
    while d:
        top = d.pop(0)
        if top == 0:
            return all(x == 0 for x in d)
        if top < 0 or top > len(d):
            return False
        for i in range(top):
            d[i] -= 1
        if any(x < 0 for x in d):
            return False
        d.sort(reverse=True)
    return True


def independent_states(pid):
    active = tuple(d for d in map(int, pid) if d)
    groups = sorted(set(active), reverse=True)
    # Start from every labelled sigma vector. Deduplication happens afterwards.
    signatures = {
        tuple(
            (d, tuple(sorted(s for x, s in zip(active, sigmas, strict=True) if x == d)))
            for d in groups
        )
        for sigmas in product(*(range(7 - d) for d in active))
    }
    zetas = tuple(
        z for z in combinations_with_replacement(range(1, 7), 6) if hh([6 - x for x in z])
    )
    goodman = 1140 - sum((6 + d) * (13 - d) for d in map(int, pid)) // 2
    states = []
    for signature in sorted(signatures):
        ds = [d for d, sigmas in signature for _ in sigmas]
        sigmas = [s for _, values in signature for s in values]
        if not hh([7 - d + s for d, s in zip(ds, sigmas, strict=True)]):
            continue
        r = sum(sigmas)
        for z in zetas:
            if sum(z) != r:
                continue
            # Test BOTH shores with the independent direct subset edge bounds.
            shores = ((sigmas, z), (z, sigmas))
            if not all(
                sum(sorted(a, reverse=True)[:k]) <= sum(min(k, b0) for b0 in b)
                for a, b in shores
                for k in range(1, len(a) + 1)
            ):
                continue
            ss = sum(s * (7 - d + s) for d, s in zip(ds, sigmas, strict=True))
            zs = sum(x * (x - 1) for x in z)
            states.append(
                {
                    "R": r,
                    "SIGMA_BY_D": [[d, list(s)] for d, s in signature],
                    "ZETA": list(z),
                    "SIGMA_SCORE": ss,
                    "ZETA_SCORE": zs,
                    "UPPER": goodman - 54 - 10 * r + ss + zs,
                }
            )
    return len(signatures), zetas, states


def independent_term(pid, t, floor=112):
    d = list(map(int, pid))
    g = [6 + x for x in d]
    w = sum(x * (x - 1) // 2 for x in g)
    j = sum(x * (x - 1) * (x - 2) // 6 for x in g)
    q = max(0, -(-(j - (max(g) - 2) * (w - 3 * t)) // 4))
    a = min(q, sum(x * (x + 4) for x in d) // 3)
    s4 = max(floor, 448 * a + 679 * (q - a))
    s3 = 2800 * w + 11872 * (t - 22) - 30800
    exact = Fraction(308390040 + s3) - Fraction(4, 7) * s4
    return [t, -(-exact.numerator // exact.denominator), q, a, s4, s3]


@pytest.mark.parametrize("index", range(3))
def test_exact_profile_facts(index, result):
    pid = IDS[index]
    f = result["PROFILES"][pid]["FACTS"]
    d = list(map(int, pid))
    assert Counter(d) == HISTOGRAMS[index]
    assert f["D_HISTOGRAM"] == {str(k): v for k, v in HISTOGRAMS[index].items()}
    assert sum(d) == f["DEGREE_SUM_D"] == 66
    assert sum(6 + x for x in d) == f["DEGREE_SUM_G"] == 186
    assert f["EDGES"] == 93 and (f["K"], f["Z"]) == (14, 6)
    assert f["WEDGES"] == (833, 824, 824)[index]
    assert f["GOODMAN"] == (299, 290, 290)[index]
    assert f["J"] == (2366, 2286, 2288)[index]
    assert f["A_MAX"] == (201, 195, 195)[index]
    assert sum(f["PAIR_DEGREES"]) == 54
    assert f["ASSUMPTIONS"] == {
        "TICKETS": 20,
        "LABELS_PER_TICKET": 6,
        "LABELS": 49,
        "TRIPLE_LABELS": 22,
        "PAIR_LABELS": 27,
        "PAIR_LINEARITY": True,
    }


@pytest.mark.parametrize("index", range(3))
def test_complete_independent_relaxation(index, result):
    pid = IDS[index]
    n, zetas, states = independent_states(pid)
    r = result["PROFILES"][pid]["RELAXATION"]
    assert n == r["SIGMA_SIGNATURES"] == (720, 330, 540)[index]
    assert zetas == cert.zeta_sequences() and len(zetas) == 102
    assert len(states) == r["RETAINED_STATE_COUNT"] == (920, 460, 708)[index]
    cap = max(s["UPPER"] for s in states)
    assert cap == r["CAP"] == (250, 222, 218)[index]
    expected_args = sorted(cert.render(s) for s in states if s["UPPER"] == cap)
    assert sorted(cert.render(s) for s in r["ALL_ARGMAX"]) == expected_args
    assert len(expected_args) == 1
    assert r["PER_R_MAXIMUM"] == {
        str(k): max(s["UPPER"] for s in states if s["R"] == k)
        for k in sorted({s["R"] for s in states})
    }
    assert cap <= result["SHARED_THEOREM"]["T_CAP"] == 250


@pytest.mark.parametrize("index", range(3))
def test_every_old_and_new_envelope_term(index, result):
    pid = IDS[index]
    p = result["PROFILES"][pid]
    old_cap = (263, 266, 266)[index]
    assert p["OLD_EFFECTIVE_CAP_COMPARISON_ONLY"] == old_cap
    for field, cap in (("OLD_ALL_T_TERMS", old_cap), ("NEW_ALL_T_TERMS", 250)):
        terms = [independent_term(pid, t) for t in range(22, cap + 1)]
        assert p[field] == terms
        best = max(r[1] for r in terms)
        prefix = "OLD" if field.startswith("OLD") else "NEW"
        assert p[prefix + "_BOUND"] == best
        assert p[prefix + "_ALL_ARGMAX"] == [r for r in terms if r[1] == best]
    assert p["NEW_ALL_ARGMAX"][0][0] == 250
    assert p["NEW_BOUND"] == (313275996, 313248840, 313248840)[index]
    assert p["OLD_BOUND"] == (313392308, 313392232, 313392232)[index]
    assert p["S5_USED"] is False


def test_base_authority_and_every_profile_s4_s5(result):
    base, auth = cert.fixed_authority()
    assert auth == result["S4_S5_AUTHORITY"]
    assert auth["S4_CONSTANTS"] == {
        "K20_REUSED_S4_LOWER_BOUND": 112,
        "SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND": 1680,
    }
    assert "profile.count(0) == 7" in auth["S4_FUNCTION_SOURCE"]
    for pid in IDS:
        assert auth["S4_FLOOR_BY_PROFILE"][pid] == 112
        assert pid not in base["CERTIFICATES_ADOPTED"]
        assert base["INHERITED_TARGET_BONFERRONI_5"]["PROFILE_ID"] != pid
    assert base["ALL_T_BONFERRONI_5_ADOPTION"] == "NOT_VERIFIED"
    for r in range(8):
        assert int(r > 0) <= r - comb(r, 2) + comb(r, 3) - Fraction(4, 7) * comb(r, 4)


def test_full_family_and_inherited_conditions(result):
    fixed = json.loads(cert.pinned_blob(cert.INPUT_HEAD, cert.INPUT_RESULT, cert.INPUT_SHA))
    before = result["RESOLVED_ROWS_BEFORE"]
    after = result["RESOLVED_ROWS_AFTER"]
    cursor = result["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    assert before == fixed["RESOLVED_ROWS_AFTER"]
    assert cursor == fixed["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    assert result["FAMILY_BEFORE"] == fixed["FAMILY_AFTER"]
    assert result["FAMILY_BEFORE"]["MAXIMUM"] == 313392308
    assert result["FAMILY_BEFORE"]["ALL_MAX_OWNERS"] == [IDS[0]]
    assert result["FAMILY_BEFORE"]["ALL_NEXT_DISTINCT_OWNERS"] == sorted(IDS[1:])
    assert len(before) == len(after) == 4647 and len(cursor) == 197
    assert set(before) == set(after) and not set(after) & set(cursor)
    assert sorted(p for p in before if before[p] != after[p]) == sorted(IDS)
    merged = {**after, **cursor}
    levels = sorted(set(merged.values()), reverse=True)
    assert result["FAMILY_AFTER"]["MAXIMUM"] == levels[0] == 313392128
    assert result["ALL_NEW_MAX_OWNERS"] == sorted(p for p, b in merged.items() if b == levels[0])
    assert result["ALL_NEW_MAX_OWNERS"] == ["66555555555521100000", "66655555554432000000"]
    assert result["NEXT_DISTINCT_BOUND"] == levels[1] == 313391920
    assert result["FAMILY_AFTER"]["ALL_NEXT_DISTINCT_OWNERS"] == ["66666555554411100000"]
    assert result["FAMILY_DELTA"] == 180 and max(cursor.values()) == 313391784
    # Leaving the highest owner unmodified must forbid an overall decrease.
    missing_highest = dict(after)
    missing_highest[IDS[0]] = before[IDS[0]]
    assert cert.family_summary(missing_highest, cursor)["MAXIMUM"] == 313392308
    assert result["FULL_ENVELOPE_TERM_COUNTS"] == {
        "NEW_PER_PROFILE": dict.fromkeys(IDS, 229),
        "NEW_TOTAL": 687,
        "OLD_PER_PROFILE": dict(zip(IDS, (242, 245, 245), strict=True)),
        "OLD_TOTAL": 732,
        "NEW_T_RANGE": [22, 250],
    }
    inherited = result["INHERITED_EXCLUSION"]
    assert inherited["INPUT_EXCLUSION_VERBATIM"] == fixed["INHERITED_EXCLUSION"]
    assert inherited["ORIGINAL_CONDITIONS_VERBATIM"]["COUNT"] == 282
    assert inherited["ORIGINAL_CONDITIONS_VERBATIM"]["W_RANGE"] == [822, 861]
    assert inherited["RECERTIFIED_THIS_ROUND"] is False
    assert result["PROJECTION_STATUS"] == "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION"
    assert result["PRIOR_REVIEW_CAVEAT"]["PRIOR_FIRST_JUDGE"].startswith("REFUTED:")


NEGATIVE_CASES = (
    "histogram",
    "wedge",
    "Goodman",
    "final_rounding",
    "K4_rounding",
    "Amax_floor",
    "shared_cap",
    "profile_cap",
    "missing_term",
    "duplicate_term",
    "S5",
    "input_identity",
    "base_identity",
    "source_identity",
    "cursor_row",
    "exclusion",
    "missing_highest_owner",
    "family_outcome",
    "S4_floor",
    "missing_argmax",
)


@pytest.mark.parametrize("defect", NEGATIVE_CASES)
def test_negative_payload_mutations(defect, result):
    bad = copy.deepcopy(result)
    p = bad["PROFILES"][IDS[0]]
    if defect == "histogram":
        p["FACTS"]["D_HISTOGRAM"]["5"] += 1
    elif defect == "wedge":
        p["FACTS"]["WEDGES"] = 836
    elif defect == "Goodman":
        p["FACTS"]["GOODMAN"] = 302
    elif defect == "final_rounding":
        p["NEW_ALL_T_TERMS"][-1][1] -= 1
    elif defect == "K4_rounding":
        p["NEW_ALL_T_TERMS"][-1][2] -= 1
    elif defect == "Amax_floor":
        p["FACTS"]["A_MAX"] += 1
    elif defect == "shared_cap":
        bad["SHARED_THEOREM"]["T_CAP"] -= 1
    elif defect == "profile_cap":
        p["RELAXATION"]["CAP"] -= 1
    elif defect == "missing_term":
        p["NEW_ALL_T_TERMS"].pop(100)
    elif defect == "duplicate_term":
        p["NEW_ALL_T_TERMS"][100] = p["NEW_ALL_T_TERMS"][99]
    elif defect == "S5":
        p["S5_USED"] = True
    elif defect == "input_identity":
        bad["INPUT_CERTIFICATE"]["TREE"] = "0" * 40
    elif defect == "base_identity":
        bad["MATHEMATICAL_BASE"]["HEAD"] = "0" * 40
    elif defect == "source_identity":
        bad["SOURCE_SHA256"] = "0" * 64
    elif defect == "cursor_row":
        bad["CURSOR_197_PRESERVED"]["ROW_BOUNDS"].pop(
            next(iter(bad["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]))
        )
    elif defect == "exclusion":
        bad["INHERITED_EXCLUSION"]["ORIGINAL_CONDITIONS_VERBATIM"]["W_RANGE"] = [822, 837]
    elif defect == "missing_highest_owner":
        bad["RESOLVED_ROWS_AFTER"][IDS[0]] = p["OLD_BOUND"]
    elif defect == "family_outcome":
        bad["FAMILY_AFTER"]["MAXIMUM"] = 313263888
    elif defect == "S4_floor":
        p["S4_FLOOR"] = 1680
    elif defect == "missing_argmax":
        p["NEW_ALL_ARGMAX"] = []
    with pytest.raises(ValueError, match="complete exact recomputation"):
        cert.validate_payload(bad, result)
    cert.validate_payload(result, result)


def test_actual_fractional_rounding_and_integer_k4_floor():
    # A's K4 numerator has residue 2 modulo 4 at t=249; its A_max uses floor(604/3).
    f = cert.profile_facts(IDS[0])
    n = f["J"] - 10 * (f["WEDGES"] - 747)
    assert n % 4 == 2 and cert.envelope_term(IDS[0], 249)[2] == n // 4 + 1
    assert sum(d * (d + 4) for d in f["D"]) == 604
    assert f["A_MAX"] == 201
    # The legal fixed floor is divisible by 7; 113 is a test seam only.
    row = cert.envelope_term(IDS[0], 22, 113)
    exact = Fraction(308390040 + row[5]) - Fraction(4 * 113, 7)
    assert exact.denominator == 7
    assert row[1] == exact.numerator // exact.denominator + 1
    assert row == independent_term(IDS[0], 22, 113)


@pytest.mark.parametrize("pid", IDS)
def test_negative_unadopted_s5(pid):
    base, _ = cert.fixed_authority()
    with pytest.raises(ValueError, match="no adopted S5"):
        cert.validate_s5(pid, base, True)
    modified = copy.deepcopy(base)
    modified["CERTIFICATES_ADOPTED"][pid] = 250
    with pytest.raises(ValueError, match="target S5 authority changed"):
        cert.validate_s5(pid, modified, False)


@pytest.mark.parametrize("defect", ("input_tree", "base_tree", "parent", "merge", "paths"))
def test_negative_identity(monkeypatch, defect):
    def fake_git(*args, **kwargs):
        if args == ("rev-parse", cert.INPUT_HEAD + "^{tree}"):
            return "bad-tree" if defect == "input_tree" else cert.INPUT_TREE
        if args == ("rev-parse", cert.BASE_HEAD + "^{tree}"):
            return "bad-tree" if defect == "base_tree" else cert.BASE_TREE
        if args == ("rev-parse", "HEAD"):
            return "child"
        if args[:1] == ("rev-list",):
            return (
                "child unrelated"
                if defect == "parent"
                else (
                    "child " + cert.INPUT_HEAD + " extra"
                    if defect == "merge"
                    else "child " + cert.INPUT_HEAD
                )
            )
        if args[:1] == ("diff-tree",):
            return "M\tcanonical-authority.json"
        raise AssertionError(args)

    monkeypatch.setattr(cert, "git", fake_git)
    with pytest.raises(ValueError):
        cert.verify_identity()


def test_negative_histogram_and_cap():
    with pytest.raises(ValueError, match="exact frontier histogram"):
        cert.profile_facts("66665555555511000000")
    for cap in (21, 278, 250.0, True):
        with pytest.raises(ValueError, match="T cap"):
            cert.envelope(IDS[0], cap)


def test_real_isolated_fixed_child_verifier(tmp_path, monkeypatch, result):
    """C12: actual Git child and full result verification, no inherited HEAD-gated replay.

    A disposable bare object repository uses the real input objects read-only.
    It writes only under pytest's OS temporary directory and creates no worktree.
    """
    scratch = tmp_path / "child.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(scratch)], check=True)
    objects = Path(cert.git("rev-parse", "--git-common-dir"))
    if not objects.is_absolute():
        objects = cert.ROOT / objects
    monkeypatch.setenv("GIT_ALTERNATE_OBJECT_DIRECTORIES", str(objects.resolve() / "objects"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "isolated.index"))

    def run(*args, data=None):
        return (
            subprocess.check_output(["git", *args], cwd=scratch, input=data, env=os.environ.copy())
            .decode()
            .strip()
        )

    run("read-tree", cert.INPUT_HEAD)
    for path in (cert.SOURCE, cert.TEST, cert.RESULT):
        contents = cert.render(result) if path == cert.RESULT else (cert.ROOT / path).read_bytes()
        oid = run("hash-object", "-w", "--stdin", data=contents)
        run("update-index", "--add", "--cacheinfo", "100644", oid, path)
    tree = run("write-tree")
    child = run(
        "-c",
        "user.name=Isolated verifier fixture",
        "-c",
        "user.email=fixture@invalid",
        "commit-tree",
        tree,
        "-p",
        cert.INPUT_HEAD,
        data=b"C12 disposable child fixture\n",
    )
    assert cert.verify_identity(child, scratch) == "FIXED_DIRECT_CHILD"
    cert.verify_result(child, scratch)
    assert cert.compute_result(child, scratch)["FAMILY_AFTER"] == result["FAMILY_AFTER"]


def test_stored_result_bytes():
    cert.verify_result()
